#!/usr/bin/env python
"""STE task L2.6 Scripted games, tier 1 against tier 2, new rules (INFO; scoring only, no training). Settings, controls,
reading words and the reasons for each value: ``configs/ste_l2/l26_gates.toml``; spec ``ste_learning/drafts/L2_6_SPEC.md``;
tests ``tests/test_ste_l26.py``.

The same 7 scripted cells (6 main + one repeat copy) on T44's first 1,000 3v3 starts, played group by group: each group
is one rule set x one arm (estimate error off / nominal), first on tier 1 (fast engine, the group's tier-1 game file),
then on tier 2 (the group's tier-2 game file with the physics backend and the arm's parameter file), same starts and
seed. One Isaac world of 7,000 games x 6 drones for the whole run. Reads, per cell, whether tier 1 predicts tier 2
(Wilson intervals, T13's 0.10 gap) and, per rule pair, whether both tiers give the same word for the rule's effect.

    # after nvidia-smi and scripts/isaac_preflight.sh --approved-headless (exit 0), alone on the GPU:
    scripts/ste_job.py launch --task L2.6 --name l26_tier12 --run-dir runs/<date>_ste_l26_tier12 --min-s 1200 \\
        --gpu-h 1.5 --settings configs/ste_learning.toml -- <python> scripts/ste_tier12_l26.py \\
        --settings configs/ste_l2/l26_gates.toml --run-dir runs/<date>_ste_l26_tier12 --cap-h 1.5 --headless
    # smoke (not of record; known answers NOT_CHECKED): add --games 16 --max-ticks 200 (and a smaller --cap-h)

Order: every pinned file checked by sha256 (exit 2, nothing played); the protected groups' worst case against the cap
(exit 2 if it does not fit); Isaac Sim started headless before torch is imported; the Isaac world; tag_fires_t2 (a 10 m
tag on the landing + option B game, tier 2); then per group, in the gate file's order: a droppable group is played only
if its worst case (re-timed from this run's batches) fits what is left of the cap, else recorded "not played";
condition_<g>, the tier-1 batch, tier1_<g> (plumbing; known answer: T44 game for game or T70's counts), repeat_t1_<g>;
physics_agreement_<g>_launch<k> (L0.13's C-1a); the tier-2 batch, tier2_<g>, repeat_t2_<g>, known_t2 (base_1p6 only).
Only when every control passes: ``results.json`` (last) and ``results.md``.

Run contract (``ste/run_contract.py``): the same command resumes at the next batch not yet checked; SIGINT or SIGTERM
stops before the next tick (exit 4); the cap is effective seconds = --cap-h x 3600 (exit 3). Exit codes: 0 done; 2
refused; 3 cap; 4 stopped; 5 a non-finite value; 6 CONTROL_FAILED (terminal). ``--dry-cpu`` (tests only, never of
record): CPU, the PyTorch reference world instead of Isaac. Observed in the training simulator; nothing here is a
flight result."""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import time
import tomllib
import traceback
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

from ste_tier2_score_l18 import (_exact, _path, _sha, isaac_world_factory, paired,  # noqa: E402
                                 pre_isaac_problem as _l18_pre_isaac, torch_world_factory)

HOUR_S = 3600.0
SETTINGS_COPY, PINNED_SHA, CONTROLS_FILE, RESULTS, GAMES = "l26_gates.toml", "settings.sha256", "controls.json", \
    "results.json", "games"
PLAN_FILE = "plan.json"
PASS, FAIL, NONFINITE, INFO, NOT_CHECKED = "PASS", "FAIL", "NONFINITE", "INFO", "NOT_CHECKED"
SIZE, DRONES = "3v3", 6
KNOWN_SIZE = (1000, 2400)     # games x ticks of every known answer (T44, T53, T70): other sizes record NOT_CHECKED
OBSERVED = "observed in the training simulator"
SIMULATOR = {1: "training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, "
                "fitted PX4 response, exploratory)",
             2: "training simulator, tier 2 (the same command chain driving the Isaac Lab 2.3.2 rigid-body Starling in "
                "PhysX, PX4 1.14 cascade copy)"}
TIER2_KEYS = ["starling.backend", "starling.physics_params"]

# ---- the reading words (spec, fixed before the run)
PREDICTS = "tier 1 predicts tier 2"
INSIDE_T13 = "tier 2 differs, inside T13's 0.10"
BEYOND_T13 = "tier 2 differs by more than T13's 0.10"
GROUP_PREDICTS = "the fast engine predicts tier 2 in every scripted cell of this rule set"
GROUP_INSIDE = "the fast engine predicts tier 2 within T13's 0.10 in this rule set, not in every cell"
GROUP_NOT = "the fast engine does not predict tier 2 in this rule set (a gap larger than T13's 0.10)"
NO_GAMES = "no finished game on a tier: no word"
GROUP_NO_WORD = "no word for this rule set (a cell without finished games)"
RAISES, LOWERS, NO_CHANGE = "raises the Guard team's hold", "lowers the Guard team's hold", "no change detected"
AGREE = "both tiers agree on the rule's effect"
DISAGREE = "the tiers disagree on its direction"
ONLY_T1, ONLY_T2 = "only tier 1 detects an effect", "only tier 2 detects an effect"
NOT_SHOWN = "the rule not shown to reach this tier beyond copy noise: no word"
REASON_PROTECTED, REASON_FITS = "protected", "fits what is left of the cap"
REASON_OVER_CAP = "not played (projected over the cap)"
REASON_AFTER_DROP = "not played (an earlier group in the drop order was dropped)"

_KEYS = {
    "job": {"task", "what", "kind", "device", "games", "ticks_cap", "cap_h", "cap_check_every_ticks"},
    "reference": {"file", "sha256", "start_sha256", "variant"},
    "cells": {"main", "repeat"},
    "params": {"off", "nominal"},
    "games": None,
    "groups": {"name", "label", "tier1_game", "tier2_game", "arm", "protected", "tier1_known", "tier1_known_holds",
               "tier1_known_source"},
    "known": {"t1_count_tol_games", "t2_group", "t2_cell", "t2_holds_min", "t2_holds_max", "t2_source"},
    "controls": {"repeat_count_tol_games", "repeat_differ_tol_games", "agree_guard", "agree_strike", "agree_ticks",
                 "agree_max_m", "agree_seed", "tag_fires_game", "tag_fires_ticks"},
    "projection": {"tier1_s_per_tick", "tier2_s_per_tick", "option_b_factor_tier1", "option_b_factor_tier2", "fixed_s",
                   "safety_factor"},
    "reading": {"t13_gap", "rule_pairs"},
}
PAIR_KEYS = {"name", "rule", "ruling", "from", "to"}


def say(text: str) -> None:
    print(f"[l26] {text}", flush=True)


def refuse(text: str) -> int:
    print(f"refused: {text}", file=sys.stderr, flush=True)
    return 2


def parser(isaac: bool = False) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--settings", type=Path, required=True)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--cap-h", type=float, required=True, help="cap in effective hours (= the launcher's --gpu-h)")
    ap.add_argument("--allow-code-change", action="store_true",
                    help="resume although the code differs from the first launch's (recorded in code.json)")
    ap.add_argument("--dry-cpu", action="store_true", help="tests only: CPU, the PyTorch reference world; never of record")
    ap.add_argument("--games", type=int, help="smoke: fewer starts per cell (stamped; known answers NOT_CHECKED)")
    ap.add_argument("--max-ticks", type=int, help="smoke: a shorter clock (stamped; known answers NOT_CHECKED)")
    if not isaac:
        ap.add_argument("--headless", action="store_true", help="required without --dry-cpu (Isaac Lab)")
    return ap


def pre_isaac_problem(argv: list[str]) -> tuple[int, str] | None:
    """Before Isaac Sim starts (standard library only): (exit code, why) or None (as L1.8's)."""
    return _l18_pre_isaac(argv)


# ================================================================================================ settings (stdlib only)
def load_settings(path: Path) -> dict:
    """The gate file with exactly its keys; ValueError names the first problem."""
    data = tomllib.loads(Path(path).read_text())
    unknown = sorted(set(data) - set(_KEYS))
    if unknown:
        raise ValueError(f"unknown section(s): {unknown}")
    for sec, keys in _KEYS.items():
        if sec == "groups":
            if not isinstance(data.get(sec), list) or not data[sec]:
                raise ValueError("[[groups]]: at least one")
            for g in data[sec]:
                _exact(g, keys, f"groups {g.get('name')}")
        elif keys is None:
            if not isinstance(data.get(sec), dict) or not data[sec]:
                raise ValueError(f"[{sec}] must be a table")
            for k, v in data[sec].items():
                _exact(v, {"file", "sha256"}, f"{sec}.{k}")
        else:
            _exact(data.get(sec), keys, sec)
    for k, v in data["params"].items():
        _exact(v, {"file", "sha256"}, f"params.{k}")
    for p in data["reading"]["rule_pairs"]:
        _exact(p, PAIR_KEYS, f"reading.rule_pairs {p.get('name')}")
    names = [g["name"] for g in data["groups"]]
    if len(set(names)) != len(names):
        raise ValueError(f"[[groups]] names must be distinct: {names}")
    for g in data["groups"]:
        for key in ("tier1_game", "tier2_game"):
            if g[key] not in data["games"]:
                raise ValueError(f"group {g['name']}: {key} {g[key]!r} is not in [games]")
        if g["arm"] not in data["params"]:
            raise ValueError(f"group {g['name']}: arm {g['arm']!r} is not in [params]")
        if g["tier1_known"] not in ("t44", "counts", "none"):
            raise ValueError(f"group {g['name']}: tier1_known must be t44, counts or none")
        if (g["tier1_known"] == "counts") != bool(g["tier1_known_holds"]) or \
                (g["tier1_known_holds"] and len(g["tier1_known_holds"]) != len(data["cells"]["main"])):
            raise ValueError(f"group {g['name']}: tier1_known_holds needs tier1_known 'counts', one count per main cell")
    prot = [g["protected"] for g in data["groups"]]
    if prot != sorted(prot, reverse=True):
        raise ValueError("protected groups come first in [[groups]] (a droppable group never runs before a protected one)")
    if data["known"]["t2_group"] != names[0] or tuple(data["known"]["t2_cell"]) not in map(tuple, data["cells"]["main"]):
        raise ValueError("known.t2_group must be the first group and known.t2_cell a main cell")
    if tuple(data["cells"]["repeat"]) not in map(tuple, data["cells"]["main"]):
        raise ValueError("cells.repeat must be a main cell")
    if data["controls"]["tag_fires_game"] not in data["games"]:
        raise ValueError("controls.tag_fires_game is not in [games]")
    for p in data["reading"]["rule_pairs"]:
        for end in ("from", "to"):
            if p[end] not in names:
                raise ValueError(f"rule pair {p['name']}: {end} {p[end]!r} names no group")
    j = data["job"]
    if not (int(j["games"]) > 0 and int(j["ticks_cap"]) > 0 and float(j["cap_h"]) > 0):
        raise ValueError("job.games, job.ticks_cap and job.cap_h must be above 0")
    return data


def pin_problems(s: dict) -> list[str]:
    """One line per pinned file that is missing or another (reference, game files, parameter files)."""
    want = [(_path(s["reference"]["file"]), s["reference"]["sha256"], "T44's reference")]
    want += [(_path(v["file"]), v["sha256"], f"game {k}") for k, v in s["games"].items()]
    want += [(_path(v["file"]), v["sha256"], f"parameter file {k}") for k, v in s["params"].items()]
    out = []
    for path, sha, what in want:
        if not path.is_file():
            out.append(f"{what} {path} is missing")
        elif _sha(path) != sha:
            out.append(f"{what} {path} has sha256 {_sha(path)}, the settings pin {sha}")
    return out


def layout(s: dict) -> SimpleNamespace:
    """The batch's cells: the main cells, then the repeat copy; repeat_pair = (copy index, its first's index)."""
    main = [tuple(c) for c in s["cells"]["main"]]
    rep = tuple(s["cells"]["repeat"])
    return SimpleNamespace(main=main, cells=main + [rep], repeat_pair=(len(main), main.index(rep)))


def game_cfg(s: dict, key: str):
    from svg_training.ste import exploit
    return exploit.load_game_cfg_file(_path(s["games"][key]["file"]))


def tier2_cfg(s: dict, game_key: str, arm: str):
    """A tier-2 game: the game file with the physics backend and the arm's parameter file."""
    return game_cfg(s, game_key).replace(**{"starling.backend": "physics",
                                            "starling.physics_params": s["params"][arm]["file"]})


def group_cfgs(s: dict, g: dict):
    return game_cfg(s, g["tier1_game"]), tier2_cfg(s, g["tier2_game"], g["arm"])


def condition_check(s: dict, g: dict) -> dict:
    """The group's tier-2 game differs from its tier-1 game in the backend and the parameter file only, plus (error
    arm only) the tier-1 estimate error, which the physics backend refuses; the parameter file differs from the off
    arm's only in state_error_* and flies its file's values; the tier-1 error is on exactly in the error arm."""
    import dataclasses

    from svg_training.core.physics_layer import load_game_physics_params
    from svg_training.models.physics_params import ERROR_KEYS
    from svg_training.ste import tier2_train as T
    c1, c2 = group_cfgs(s, g)
    diff = T.cfg_differences(c1, c2)
    err = g["arm"] != "off"
    core = [d for d in diff if not d.startswith("estimate_error.")]
    err_diff = [d for d in diff if d.startswith("estimate_error.")]
    p = load_game_physics_params(c2)
    off = load_game_physics_params(tier2_cfg(s, g["tier2_game"], "off"))
    other = [f.name for f in dataclasses.fields(p) if f.name not in ERROR_KEYS and f.name != "source"
             and getattr(p, f.name) != getattr(off, f.name)]
    want = tomllib.loads(_path(s["params"][g["arm"]]["file"]).read_text())["model"]
    flies = {k: getattr(p, k) for k in ERROR_KEYS}
    same = flies == {k: float(want[k]) for k in ERROR_KEYS}
    t2_error_on = any(v > 0 for v in flies.values())
    ok = (sorted(core) == sorted(TIER2_KEYS) and bool(err_diff) == err and c1.estimate_error.enabled == err
          and t2_error_on == err and not other and same)
    return {"status": PASS if ok else FAIL, "differs": diff, "params_differ_besides_error": other, "state_error": flies,
            "tier1_error": c1.estimate_error.enabled,
            "detail": f"tier 2 v tier 1 game: {diff}; tier-1 estimate error {'on' if c1.estimate_error.enabled else 'off'}; "
                      f"tier-2 parameters differ from the off file besides state_error_* in {other}; flies "
                      f"{'its file' if same else 'NOT its file'} ({'error on' if t2_error_on else 'error off'})"}


# ================================================================================================ the projection
def _share(s: dict, game_key: str) -> str:
    return game_cfg(s, game_key).filter.share


def worst_seconds(s: dict, g: dict, measured: dict | None = None, ticks: int | None = None) -> dict:
    """A group's worst case (every batch to the tick cap), per tier: the measured seconds per batch tick of this run's
    batches of the same tier and filter share where there are any, else the gate file's rate x the option B factor."""
    pr, ticks = s["projection"], int(ticks or s["job"]["ticks_cap"])
    out = {}
    for tier, key in ((1, "tier1_game"), (2, "tier2_game")):
        share = _share(s, g[key])
        rate = (measured or {}).get((tier, share))
        if rate is None:
            rate = float(pr[f"tier{tier}_s_per_tick"]) * (float(pr[f"option_b_factor_tier{tier}"])
                                                          if share != "equal" else 1.0)
        out[f"tier{tier}"] = rate * ticks
    return out


def launch_projection(s: dict, ticks: int | None = None) -> dict:
    """The protected groups' and all groups' worst cases (s) plus the fixed seconds, against the cap."""
    w = {g["name"]: sum(worst_seconds(s, g, ticks=ticks).values()) for g in s["groups"]}
    fixed = float(s["projection"]["fixed_s"])
    prot = fixed + sum(w[g["name"]] for g in s["groups"] if g["protected"])
    cap = float(s["job"]["cap_h"]) * HOUR_S
    return {"per_group_s": w, "protected_s": prot, "total_s": fixed + sum(w.values()), "cap_s": cap,
            "safety_factor": float(s["projection"]["safety_factor"]),
            "fits": prot * float(s["projection"]["safety_factor"]) <= cap}


def should_play(protected: bool, effective_s: float, worst_s: float, cap_s: float, safety: float,
                earlier_dropped: bool = False) -> bool:
    """A protected group always plays (the launch checked it fits); a droppable one only if no earlier group was dropped
    (the drop order is fixed) and its worst case fits what is left of the cap."""
    return protected or (not earlier_dropped and effective_s + worst_s * safety <= cap_s)


def replay_controls(s: dict) -> dict:
    """exploit.replay_ok's CUDA tolerances for the T44 replay (L0.13's values, the gate file's repeat tolerances);
    the CPU stays game for game."""
    c = s["controls"]
    return {"replay_count_tol_cuda_games": int(c["repeat_count_tol_games"]),
            "replay_differ_tol_cuda_games": int(c["repeat_differ_tol_games"])}


# ================================================================================================ the reading words
def _ci(k: int, n: int) -> tuple[float, float]:
    from svg_training.core.metrics import wilson_interval
    return wilson_interval(int(k), int(n))


def _apart(k1, n1, k2, n2) -> int:
    """+1 if the second interval lies above the first, -1 below, 0 if they overlap."""
    lo1, hi1 = _ci(k1, n1)
    lo2, hi2 = _ci(k2, n2)
    return 1 if lo2 > hi1 else -1 if hi2 < lo1 else 0


def predict_word(k1: int, n1: int, k2: int, n2: int, gap: float) -> str:
    """Tier 1 (k1 of n1 holds) against tier 2 (k2 of n2) in one cell: a gap above T13's first (BEYOND_T13), then
    overlapping Wilson intervals (PREDICTS), else INSIDE_T13. At 1,000 games overlap implies a gap under about 0.06."""
    if min(n1, n2) == 0:
        return NO_GAMES
    if abs(k2 / n2 - k1 / n1) > gap + 1e-12:
        return BEYOND_T13
    return PREDICTS if _apart(k1, n1, k2, n2) == 0 else INSIDE_T13


def group_word(words: list[str]) -> str:
    if NO_GAMES in words:
        return GROUP_NO_WORD
    if BEYOND_T13 in words:
        return GROUP_NOT
    return GROUP_PREDICTS if all(w == PREDICTS for w in words) else GROUP_INSIDE


def effect_word(k_from: int, n_from: int, k_to: int, n_to: int) -> str:
    if min(n_from, n_to) == 0:
        return NO_GAMES
    a = _apart(k_from, n_from, k_to, n_to)
    return RAISES if a > 0 else LOWERS if a < 0 else NO_CHANGE


def cross_word(w1: str, w2: str) -> str:
    if NO_GAMES in (w1, w2):
        return NO_GAMES
    if w1 == w2:
        return AGREE
    if NO_CHANGE in (w1, w2):
        return ONLY_T1 if w2 == NO_CHANGE else ONLY_T2
    return DISAGREE


def copy_floor(noises: list[dict]) -> dict:
    """The run's copy noise on one tier: per measure, the largest repeat-cell count over the tier's off-arm batches.
    Paired groups of one arm share their estimate-error draws slot by slot (models/estimator_effect.py keeps the streams
    aligned), so only the device's own jitter separates them, never the error's redraw (the repeat cell's own slot)."""
    keys = ("outcome_differs", "outcome_or_end_differs")
    return {k: max((int(x[k]) for x in noises), default=0) for k in keys}


def rule_reached(arm_change: bool, cells: int, differ_outcome: int, differ_any: int, noise_from: dict,
                 noise_to: dict) -> bool:
    """Did the rule reach this tier beyond copy noise? (spec, reading 5). ``noise_*``: the repeat cell's
    outcome_differs and outcome_or_end_differs in each batch. The arm changes (the estimate error): the error's copies
    differ more than the other arm's (adding the error and redrawing it cannot be told apart by changed games). Exact
    copies in both batches: at least one game changed in outcome or end step (L2.5's rule). Otherwise outcomes only:
    more than ``cells`` x the larger repeat outcome count (end-step jitter on CUDA is not measured; the x cells
    extrapolates from one repeat cell)."""
    if arm_change:
        return noise_to["outcome_or_end_differs"] > noise_from["outcome_or_end_differs"]
    if noise_from["outcome_or_end_differs"] == 0 and noise_to["outcome_or_end_differs"] == 0:
        return differ_any >= 1
    return differ_outcome > cells * max(noise_from["outcome_differs"], noise_to["outcome_differs"]) and differ_outcome >= 1


# ================================================================================================ the run
def main(argv: list[str] | None = None, world_factory=None) -> int:
    return run(parser().parse_args(list(sys.argv[1:] if argv is None else argv)), world_factory)


def load_batch(path: Path) -> dict:
    from svg_training.ste import scoring
    return scoring.load_batch(path)


def run(a: argparse.Namespace, world_factory=None) -> int:
    a.run_dir = a.run_dir.resolve()
    try:
        s = load_settings(a.settings)
    except (OSError, ValueError) as err:
        return refuse(f"settings {a.settings}: {err}")
    a.smoke = a.games is not None or a.max_ticks is not None
    if not (a.cap_h > 0 and math.isfinite(a.cap_h)):
        return refuse(f"--cap-h must be a finite number of hours above 0, got {a.cap_h!r}")
    cap = float(s["job"]["cap_h"])
    if (not a.smoke and abs(a.cap_h - cap) > 1e-9) or (a.smoke and a.cap_h > cap + 1e-9):
        return refuse(f"--cap-h {a.cap_h} differs from the settings' job.cap_h {cap} (a smoke may ask less)")
    if not a.dry_cpu and (ROOT / "runs").resolve() not in a.run_dir.parents:
        return refuse(f"{a.run_dir} is not under {ROOT / 'runs'}")
    if not a.dry_cpu and not getattr(a, "headless", True):
        return refuse("the tier 2 batches start Isaac Lab: --headless")
    n_full, ticks_full = int(s["job"]["games"]), int(s["job"]["ticks_cap"])
    for flag, value, full in (("--games", a.games, n_full), ("--max-ticks", a.max_ticks, ticks_full)):
        if value is not None and not 0 < value <= full:
            return refuse(f"{flag} {value}: a smoke plays between 1 and the settings' {full}")
    problems = pin_problems(s)
    if problems:
        return refuse("pinned file(s): " + "; ".join(problems))
    proj = launch_projection(s, ticks=a.max_ticks)
    if not a.smoke and not proj["fits"]:
        return refuse(f"the protected groups' worst case {proj['protected_s']:.0f} s x {proj['safety_factor']} does not "
                      f"fit the cap {proj['cap_s']:.0f} s")
    sha = _sha(a.settings)
    pinned = a.run_dir / PINNED_SHA
    if pinned.is_file() and pinned.read_text().strip() != sha:
        return refuse(f"the settings changed since the first launch in {a.run_dir}: a new pin means a new run folder")
    res = a.run_dir / RESULTS
    if res.is_file() and json.loads(res.read_text()).get("complete") is True:
        say(f"this run folder is done ({res}); nothing to do")
        return 0
    problem = pre_isaac_problem(["--headless", "--run-dir", str(a.run_dir)])
    if problem:
        print(problem[1], file=sys.stderr, flush=True)
        return problem[0]
    stamp = a.run_dir / "run.json"
    want = {"dry_cpu": bool(a.dry_cpu), "games": a.games, "max_ticks": a.max_ticks}
    if stamp.is_file() and {k: json.loads(stamp.read_text()).get(k) for k in want} != want:
        return refuse(f"{a.run_dir} was started as {json.loads(stamp.read_text())}: one kind of run per folder")

    import torch

    from svg_training.ste import atomic
    from svg_training.ste.run_contract import RunBusyError, RunGuard
    import ste_sweep_l011 as l011
    device = "cpu" if a.dry_cpu else str(s["job"]["device"])
    if device.startswith("cuda") and not torch.cuda.is_available():
        return refuse("the settings play on cuda and PyTorch sees no GPU")
    job = a.run_dir / "job.json"
    if job.is_file():
        gpu_h = float(json.loads(job.read_text()).get("gpu_h", 0))
        if abs(gpu_h - a.cap_h) > 1e-9:
            return refuse(f"the launcher asked for {gpu_h} GPU-h, --cap-h is {a.cap_h}: keep the two equal")
        if not device.startswith("cuda"):
            return refuse("a launched job on the CPU: runs of record play on the GPU (--dry-cpu is for tests)")
    ctx = Context(s, a, device, world_factory, proj)
    a.run_dir.mkdir(parents=True, exist_ok=True)
    try:
        with RunGuard(a.run_dir, cap_s=a.cap_h * HOUR_S) as guard:
            changed = l011.pin_code(a)
            if changed:
                return refuse(changed)
            if not pinned.is_file():
                shutil.copyfile(a.settings, a.run_dir / SETTINGS_COPY)
                atomic.write_text(pinned, sha + "\n")
                l011.write_json(stamp, {**want, "device": device, "cap_h": a.cap_h})
            state = guard.load_latest()
            launches = int((state.state if state is not None else {}).get("launches", 0)) + 1
            return ctx.play(guard, launches)
    except RunBusyError as err:
        return refuse(str(err))


class Context:
    """Everything the run reads, loaded once."""

    def __init__(self, s: dict, a, device: str, world_factory, proj: dict):
        import numpy as np

        from svg_training.ste import exploit, sweep
        self.s, self.a, self.device, self.np, self.ex, self.proj = s, a, device, np, exploit, proj
        self.n = int(a.games or s["job"]["games"])
        self.ticks = int(a.max_ticks or s["job"]["ticks_cap"])
        self.full = (self.n, self.ticks) == KNOWN_SIZE and not a.smoke
        self.lay = layout(s)
        self.ref = exploit.load_reference(_path(s["reference"]["file"]))
        if self.ref.start_sha256 != s["reference"]["start_sha256"]:
            raise ValueError(f"T44's starts have sha256 {self.ref.start_sha256}, the settings pin "
                             f"{s['reference']['start_sha256']}")
        self.seed = int(self.ref.meta["seed"])
        self.tol = 0.0 if device == "cpu" else float(sweep.load_gates().controls["same_seed_closest_tol_m"])
        self.world_factory = world_factory or (torch_world_factory if a.dry_cpu else isaac_world_factory)
        self.world = None
        self.measured: dict = {}

    def batch(self, cfg, world, should_stop, cells=None, ticks=None) -> dict:
        return self.ex.play_cells(cfg, SIZE, self.ref, cells or self.lay.cells, self.n, self.device, self.seed,
                                  ticks or self.ticks, should_stop=should_stop, world=world)

    def cell(self, pg: dict, i: int) -> dict:
        return self.ex.slice_cell(pg, i, self.n)

    def holds(self, pg: dict, i: int) -> int:
        return int(self.np.sum(self.cell(pg, i)["outcome"] == self.ex.GUARD_WIN))

    # ------------------------------------------------------------------------------------------- controls
    def check_batch(self, pg: dict, tier: int, g: dict, phase: str) -> dict:
        """Plumbing (paired starts, one for one, no non-finite action), the tier the batch ran, and the tier-1 known answer."""
        from svg_training.ste import scoring, tier2_train as T
        parts = scoring.plumbing_controls(pg, self.ref, self.n, phase)
        ran, nf = T.batch_tier(pg), int(pg["physics_nonfinite"])
        upsets = int(self.np.sum(pg["upset"])) if "upset" in pg else None
        known, known_ok, kdetail = None, True, "no known answer"
        if tier == 1 and g["tier1_known"] == "t44":
            rule, want = replay_controls(self.s), self.ex.starts_sha(self.ref.starts_m[:self.n])
            known = {}
            for i, c in enumerate(self.lay.cells):
                theirs = {k: self.np.asarray(v)[:self.n] for k, v in self.ref.cell(self.s["reference"]["variant"], *c).items()}
                same, text = self.ex.replay_ok(self.cell(pg, i), theirs, self.device, rule, ticks_cap=self.ticks)
                same &= pg["start_sha256"][i] == want
                known[f"{c[0]} v {c[1]} ({i})"] = {"equal": bool(same), "detail": text}
                known_ok &= bool(same)
            kdetail = (f"T44 replay ({'game for game' if not str(self.device).startswith('cuda') else 'CUDA tolerances ' + str(rule)}): "
                       f"{'EQUAL' if known_ok else 'DIFFERENT ' + str([k for k, v in known.items() if not v['equal']])}")
        elif tier == 1 and g["tier1_known"] == "counts":
            if self.full:
                tol = int(self.s["known"]["t1_count_tol_games"])
                got = [self.holds(pg, i) for i in range(len(self.lay.main))]
                bad = [(c, k, w) for c, k, w in zip(self.lay.main, got, g["tier1_known_holds"]) if abs(k - w) > tol]
                known, known_ok = {"holds": got, "expected": g["tier1_known_holds"], "tol": tol}, not bad
                kdetail = f"holds {got} v {g['tier1_known_source']} {g['tier1_known_holds']} (+-{tol}): " + \
                          ("within" if not bad else f"OUTSIDE {bad}")
            else:
                kdetail = "known counts NOT_CHECKED (test size)"
        ok = ran == tier and nf == 0 and known_ok
        return {"status": scoring.control_status(parts, ok), "tier": ran, "physics_nonfinite": nf, "upsets": upsets,
                "plumbing": parts, "known": known,
                "detail": f"ran {pg['motion']} (tier {ran}, want {tier}); non-finite wrench or setpoint {nf}; upset games "
                          f"{upsets} (INFO); {kdetail}; " + "; ".join(f"{k} {v['status']}" for k, v in parts.items())}

    def repeat_noise(self, pg: dict) -> dict:
        i, j = self.lay.repeat_pair
        a, b = self.cell(pg, i), self.cell(pg, j)
        ha, hb = self.holds(pg, i), self.holds(pg, j)
        differ = int(self.np.sum(a["outcome"] != b["outcome"]))
        differ_end = int(self.np.sum((a["outcome"] != b["outcome"]) | (a["end_step"] != b["end_step"])))
        return {"holds": [hb, ha], "outcome_differs": differ, "outcome_or_end_differs": differ_end}

    def check_repeat(self, pg: dict, g: dict) -> dict:
        c = self.s["controls"]
        r = self.repeat_noise(pg)
        gated = g["arm"] == "off"
        within = abs(r["holds"][0] - r["holds"][1]) <= int(c["repeat_count_tol_games"]) and \
            r["outcome_differs"] <= int(c["repeat_differ_tol_games"])
        status = (PASS if within else FAIL) if gated else INFO
        return {"status": status, "info": not gated, **r,
                "detail": f"{self.lay.cells[self.lay.repeat_pair[1]]}: holds {r['holds'][0]} / {r['holds'][1]}, "
                          f"{r['outcome_differs']} games end otherwise ({r['outcome_or_end_differs']} in outcome or end "
                          f"step)" + ("" if gated else " (INFO: each copy draws its own estimate error)")}

    def check_known_t2(self, pg: dict) -> dict:
        k = self.s["known"]
        if not self.full:
            return {"status": NOT_CHECKED, "detail": f"{self.n} games x {self.ticks} ticks: the band is for the full size"}
        holds = self.holds(pg, self.lay.main.index(tuple(k["t2_cell"])))
        ok = int(k["t2_holds_min"]) <= holds <= int(k["t2_holds_max"])
        return {"status": PASS if ok else FAIL, "holds": holds, "band": [k["t2_holds_min"], k["t2_holds_max"]],
                "detail": f"{k['t2_cell'][0]} v {k['t2_cell'][1]} holds {holds} (band {k['t2_holds_min']}-"
                          f"{k['t2_holds_max']}: {k['t2_source']})"}

    def agreement(self, cfg) -> dict:
        from svg_training.ste import tier2_train as T
        c = self.s["controls"]
        gates = SimpleNamespace(controls={k: c[k] for k in ("agree_guard", "agree_strike", "agree_ticks", "agree_max_m")},
                                run={"size": SIZE, "train_seed": int(c["agree_seed"])})
        return T.physics_agreement(gates, cfg, self.world, self.device)

    # ------------------------------------------------------------------------------------------- the run
    def play(self, guard, launches: int) -> int:
        from svg_training.core.physics_layer import load_game_physics_params
        from svg_training.ste import scoring, sweep
        from svg_training.ste.run_contract import EXIT_CONTROL_FAILED, EXIT_FOR_STOP, STOP_CAP
        import ste_sweep_l011 as l011
        rd = self.a.run_dir
        (rd / GAMES).mkdir(exist_ok=True)
        controls = json.loads((rd / CONTROLS_FILE).read_text()) if (rd / CONTROLS_FILE).is_file() else {}
        plan = json.loads((rd / PLAN_FILE).read_text()) if (rd / PLAN_FILE).is_file() else {}
        every, seen = int(self.s["job"]["cap_check_every_ticks"]), [0]
        state = {"launches": launches}

        def should_stop() -> bool:
            if guard.stop_requested:
                return True
            seen[0] += 1
            return seen[0] % every == 0 and guard.cap_reached()

        def save() -> None:
            guard.save(len(controls), {**state, "done": sorted(controls)})

        def settle(key: str, ctl: dict) -> int | None:
            controls[key] = ctl
            l011.write_json(rd / CONTROLS_FILE, controls)
            say(f"{key} {ctl['status']}: {ctl['detail'][:400]}")
            save()
            code = scoring.ending({key: ctl})
            if code is not None:
                write_md(rd, self, controls, plan, None)
                say(f"{'NON-FINITE' if code == 5 else 'CONTROL FAILED'}: no number is reported (exit {code})")
            return code

        def played(name: str, cfg, world, check_key: str, cells=None, ticks=None):
            path = rd / GAMES / f"{name}.npz"
            if controls.get(check_key, {}).get("status") in (PASS, INFO, NOT_CHECKED) and path.is_file():
                return scoring.load_batch(path), None
            say(f"batch {name}: {len(cells or self.lay.cells)} cells x {self.n} games, up to {ticks or self.ticks} ticks "
                f"on {self.device}")
            t0 = time.perf_counter()
            pg = self.batch(cfg, world, should_stop, cells=cells, ticks=ticks)
            took = time.perf_counter() - t0
            scoring.save_batch(path, pg)
            l011.write_json(path.with_suffix(".json"), {"cells": [list(c) for c in (cells or self.lay.cells)],
                                                        "games_per_cell": self.n, "seconds": took,
                                                        "steps_played": int(pg["steps_played"]),
                                                        "motion": str(pg["motion"]),
                                                        "physics_nonfinite": int(pg["physics_nonfinite"]),
                                                        "backend": cfg.starling.backend,
                                                        "params": cfg.starling.physics_params})
            return pg, took

        def note_rate(tier: int, share: str, path: Path) -> None:
            meta = json.loads(path.with_suffix(".json").read_text()) if path.with_suffix(".json").is_file() else None
            if meta and meta.get("seconds") and meta.get("steps_played"):
                r = float(meta["seconds"]) / max(int(meta["steps_played"]), 1)
                self.measured[(tier, share)] = max(r, self.measured.get((tier, share), 0.0))

        pgs: dict = {}
        try:
            first_t2 = tier2_cfg(self.s, self.s["groups"][0]["tier2_game"], "off")
            t0 = time.perf_counter()
            self.world = self.world_factory(len(self.lay.cells) * self.n, DRONES, load_game_physics_params(first_t2),
                                            self.device)
            say(f"world: {getattr(self.world, 'label', type(self.world).__name__)}, {len(self.lay.cells) * self.n} "
                f"games x {DRONES} drones ({time.perf_counter() - t0:.0f} s)")
            # ---- tier 2 first contact with landing and option B: a 10 m tag, zero v zero, every game 3 tags at step 1
            c = self.s["controls"]
            tf_cfg = tier2_cfg(self.s, c["tag_fires_game"], "off")
            got = played("tag_fires_t2", tf_cfg, self.world, "tag_fires_t2",
                         cells=[("zero", "zero")] * len(self.lay.cells), ticks=int(c["tag_fires_ticks"]))
            if got[1] is not None or "tag_fires_t2" not in controls:
                from svg_training.ste import tier2_train as T
                ok, text = sweep.check_tag_fires(got[0], 3, 3)
                ok &= T.batch_tier(got[0]) == 2 and int(got[0]["physics_nonfinite"]) == 0
                code = settle("tag_fires_t2", {"status": PASS if ok else FAIL, "seconds": got[1],
                                               "detail": f"tier 2, {c['tag_fires_game']}: {text}"})
                if code is not None:
                    return code
            for g in self.s["groups"]:
                name = g["name"]
                if name not in plan:
                    worst = sum(worst_seconds(self.s, g, self.measured or None, ticks=self.ticks).values())
                    dropped = any(not v["played"] for v in plan.values())
                    go = should_play(g["protected"], guard.effective_s(), worst, guard.cap_s,
                                     float(self.s["projection"]["safety_factor"]), earlier_dropped=dropped)
                    plan[name] = {"played": go, "worst_s": worst, "effective_s_at_decision": guard.effective_s(),
                                  "measured_s_per_tick": {f"tier{k[0]}_{k[1]}": v for k, v in self.measured.items()},
                                  "reason": REASON_PROTECTED if g["protected"] else REASON_FITS if go else
                                  REASON_AFTER_DROP if dropped else REASON_OVER_CAP}
                    l011.write_json(rd / PLAN_FILE, plan)
                    say(f"group {name}: {plan[name]['reason']} (worst case {worst:.0f} s)")
                if not plan[name]["played"]:
                    continue
                if controls.get(f"condition_{name}", {}).get("status") != PASS:
                    code = settle(f"condition_{name}", condition_check(self.s, g))
                    if code is not None:
                        return code
                cfg1, cfg2 = group_cfgs(self.s, g)
                for tier, cfg, world in ((1, cfg1, None), (2, cfg2, self.world)):
                    bname = f"{name}_t{tier}"
                    if tier == 2:
                        akey = f"physics_agreement_{name}_launch{launches}"
                        need = not (controls.get(f"tier2_{name}", {}).get("status") == PASS
                                    and (rd / GAMES / f"{bname}.npz").is_file())
                        if need and akey not in controls:
                            ag = self.agreement(cfg)
                            code = settle(akey, {"status": PASS if ag["pass"] else FAIL, **ag,
                                                 "detail": f"{ag['games']} games x {ag['drones']} drones x {ag['ticks']} "
                                                           f"ticks on {ag['world']}: largest gap {ag['max_gap_m']:.5f} m "
                                                           f"(limit {ag['limit_m']} m)"})
                            if code is not None:
                                return code
                    pg, took = played(bname, cfg, world, f"tier{tier}_{name}")
                    note_rate(tier, cfg.filter.share, rd / GAMES / f"{bname}.npz")
                    checks = [(f"tier{tier}_{name}", lambda: self.check_batch(pg, tier, g, bname)),
                              (f"repeat_t{tier}_{name}", lambda: self.check_repeat(pg, g))]
                    if tier == 2 and name == self.s["known"]["t2_group"]:
                        checks.append(("known_t2", lambda: self.check_known_t2(pg)))
                    for key, check in checks:
                        if took is None and key in controls:
                            continue
                        code = settle(key, {**check(), "seconds": took})
                        if code is not None:
                            return code
                    pgs[bname] = pg
        except sweep.SweepStopped:
            save()
            reason = guard.stop_reason() or STOP_CAP
            say(f"stopped ({reason}); the same command resumes at the next batch not yet checked")
            return EXIT_FOR_STOP[reason]
        bad = {k: v["status"] for k, v in controls.items() if v["status"] not in (PASS, INFO, NOT_CHECKED)
               or (v["status"] == INFO and not v.get("info"))}
        if bad:
            say(f"not published: controls not passed {bad}")
            write_md(rd, self, controls, plan, None)
            return EXIT_CONTROL_FAILED
        result = results_of(self, controls, plan, pgs, guard)
        result["complete"] = True                                    # written last
        l011.write_json(rd / RESULTS, result)
        write_md(rd, self, controls, plan, result)
        guard.save(len(controls), {**state, "done": sorted(controls), "phase": "done"})
        for g in result["groups"]:
            say(f"{g['name']}: {g['word'] if g['played'] else g['reason']}")
        say(f"done: {rd / 'results.md'}")
        return 0


# ================================================================================================ results
def _cell_rate(ctx: Context, pg: dict, i: int) -> dict:
    from svg_training.ste import scoring
    cp = ctx.cell(pg, i)
    k, m = scoring.win_count(cp, "guard")
    return {**scoring.rate(k, m), "unfinished": ctx.n - m, "tag_stats": scoring.tag_stats(cp),
            "length_median_s": scoring.length_median_s(cp),
            "upsets": int(ctx.np.sum(cp["upset"])) if "upset" in cp else None}


def _differ(ctx: Context, a: dict, b: dict, outcome_only: bool = False) -> int:
    """Games of the main cells whose outcome (or end step, unless ``outcome_only``) differ between two batches."""
    m = len(ctx.lay.main) * ctx.n
    d = a["outcome"][:m] != b["outcome"][:m]
    return int(ctx.np.sum(d if outcome_only else d | (a["end_step"][:m] != b["end_step"][:m])))


def results_of(ctx: Context, controls: dict, plan: dict, pgs: dict, guard) -> dict:
    s, np = ctx.s, ctx.np
    gap = float(s["reading"]["t13_gap"])
    groups = []
    for g in s["groups"]:
        name = g["name"]
        if not plan.get(name, {}).get("played"):
            groups.append({"name": name, "label": g["label"], "played": False, "reason": plan.get(name, {}).get("reason")})
            continue
        p1, p2 = pgs[f"{name}_t1"], pgs[f"{name}_t2"]
        floor2 = 1.0 - ctx.repeat_noise(p2)["outcome_differs"] / ctx.n
        cells, words = [], []
        for i, c in enumerate(ctx.lay.main):
            r1, r2 = _cell_rate(ctx, p1, i), _cell_rate(ctx, p2, i)
            o1, o2 = ctx.cell(p1, i)["outcome"], ctx.cell(p2, i)["outcome"]
            word = predict_word(r1["k"], r1["n"], r2["k"], r2["n"], gap)
            words.append(word)
            cells.append({"cell": list(c), "tier1": r1, "tier2": r2, "gap": (r2["k"] / r2["n"] - r1["k"] / r1["n"]) if min(r1["n"], r2["n"]) else None,
                          "word": word, "agreement": float(np.mean(o1 == o2)),
                          "paired_holds": paired(o1, o2, ctx.ex.GUARD_WIN)})
        groups.append({"name": name, "label": g["label"], "arm": g["arm"], "played": True, "cells": cells,
                       "word": group_word(words), "tier2_copy_agreement": floor2,
                       "t13_limit_met": all(x["gap"] is not None and abs(x["gap"]) <= gap + 1e-12 for x in cells)})
    played = {g["name"] for g in groups if g["played"]}
    pairs = []
    for p in s["reading"]["rule_pairs"]:
        if not (p["from"] in played and p["to"] in played):
            pairs.append({**p, "read": False, "reason": "a group was not played"})
            continue
        reach = {}
        by = {g["name"]: g for g in s["groups"]}
        arm_change = by[p["from"]]["arm"] != by[p["to"]]["arm"]
        for tier in (1, 2):
            a, b = pgs[f"{p['from']}_t{tier}"], pgs[f"{p['to']}_t{tier}"]
            if arm_change:                             # the error's own copies against the off arm's
                na, nb = ctx.repeat_noise(a), ctx.repeat_noise(b)
            else:                                      # same arm: the tier's run-wide device jitter (spec, reading 5)
                na = nb = copy_floor([ctx.repeat_noise(pgs[f"{x}_t{tier}"]) for x in played
                                      if by[x]["arm"] == "off"])
            d_any, d_out = _differ(ctx, a, b), _differ(ctx, a, b, outcome_only=True)
            reach[tier] = {"games_differ": d_any, "outcomes_differ": d_out, "copy_noise_from": na, "copy_noise_to": nb,
                           "arm_change": arm_change,
                           "beyond_noise": rule_reached(arm_change, len(ctx.lay.main), d_out, d_any, na, nb)}
        cells = []
        for i, c in enumerate(ctx.lay.main):
            row = {"cell": list(c)}
            for tier in (1, 2):
                a, b = pgs[f"{p['from']}_t{tier}"], pgs[f"{p['to']}_t{tier}"]
                ka, na = _cell_rate(ctx, a, i)["k"], _cell_rate(ctx, a, i)["n"]
                kb, nb = _cell_rate(ctx, b, i)["k"], _cell_rate(ctx, b, i)["n"]
                oa, ob = ctx.cell(a, i)["outcome"], ctx.cell(b, i)["outcome"]
                word = effect_word(ka, na, kb, nb) if reach[tier]["beyond_noise"] else NOT_SHOWN
                row[f"tier{tier}"] = {"from": ka, "to": kb, "n": [na, nb], "word": word,
                                      "hold_to_reach": int(np.sum((oa == ctx.ex.GUARD_WIN) & (ob == ctx.ex.STRIKE_WIN))),
                                      "reach_to_hold": int(np.sum((oa == ctx.ex.STRIKE_WIN) & (ob == ctx.ex.GUARD_WIN)))}
            w1, w2 = row["tier1"]["word"], row["tier2"]["word"]
            row["cross"] = cross_word(w1, w2) if NOT_SHOWN not in (w1, w2) else NOT_SHOWN
            cells.append(row)
        pairs.append({**p, "read": True, "reach": {f"tier{k}": v for k, v in reach.items()}, "cells": cells,
                      "agree_cells": sum(r["cross"] == AGREE for r in cells)})
    from ste_exploit_l012 import machine
    m = machine()
    return {"what": f"STE {s['job']['task']}: {s['job']['what']}; {OBSERVED}", "task": s["job"]["task"],
            "kind": s["job"]["kind"], "simulator": SIMULATOR, "controls_pass": True, "groups": groups, "rule_pairs": pairs,
            "plan": plan, "projection": ctx.proj, "games": ctx.n, "ticks_cap": ctx.ticks, "seed": ctx.seed,
            "start_sha256": ctx.ref.start_sha256, "cells": [list(c) for c in ctx.lay.cells], "device": ctx.device,
            "dry_cpu": bool(ctx.a.dry_cpu), "smoke": bool(ctx.a.smoke),
            "batch_seconds": {k: v.get("seconds") for k, v in controls.items() if v.get("seconds") is not None},
            "effective_s": guard.effective_s(), "cap_h": ctx.a.cap_h, "machine": m, "gpu": m.get("gpu"),
            "code": json.loads((ctx.a.run_dir / "code.json").read_text()), "settings_sha256": _sha(ctx.a.settings)}


def _m(r: dict) -> str:
    v = r["tag_stats"].get("closest_any_pair_min_m")
    return "-" if v is None else f"{v:.3f}"


def _r(r: dict) -> str:
    lo, hi = r["ci"]
    return f"{r['k']}/{r['n']}" + ("" if lo is None else f" ({lo:.3f}-{hi:.3f})")


def write_md(run_dir: Path, ctx: Context, controls: dict, plan: dict, result: dict | None) -> None:
    from svg_training.ste import atomic
    lines = [f"Simulators: {SIMULATOR[1]}; {SIMULATOR[2]}. Study tag on (P1). {OBSERVED.capitalize()}; nothing here is a "
             "flight result. Estimate-error values: EXPLORATORY (T63). Option B: PROPOSED (P2 open).", "",
             f"# {ctx.s['job']['task']}: {ctx.s['job']['what']} (INFO)", "",
             "## Controls (read these first; any control not PASS, INFO or NOT_CHECKED: no number is reported)", "",
             "| Control | Status | Detail |", "|---|---|---|"]
    lines += [f"| {k} | **{v['status']}** | {v['detail']} |" for k, v in controls.items()]
    lines += ["", "## Groups played", "", "| Group | Decision |", "|---|---|"]
    lines += [f"| {k} | {v['reason']} (worst case {v['worst_s']:.0f} s) |" for k, v in plan.items()]
    if result is not None:
        lines += ["", f"## Tier 1 against tier 2 ({result['games']} starts per cell, T44's first; holds, Wilson 95 %)", ""]
        for g in result["groups"]:
            if not g["played"]:
                lines += [f"**{g['name']}**: {g['reason']}.", ""]
                continue
            lines += [f"**{g['name']}** ({g['label']}): **{g['word']}**; T13's 0.10 limit "
                      f"{'met' if g['t13_limit_met'] else 'NOT met'} in every cell; tier 2's own copy agreement "
                      f"{g['tier2_copy_agreement']:.3f}.", "",
                      "| Cell (Guard v Strike) | Tier 1 | Tier 2 | Tier 2 minus tier 1 | Word | Same outcome (share of starts) "
                      "| Closest approach, any pair, min (m), tier 1 / tier 2 |",
                      "|---|---|---|---|---|---|---|"]
            lines += [f"| {c['cell'][0]} v {c['cell'][1]} | {_r(c['tier1'])} | {_r(c['tier2'])} | {'-' if c['gap'] is None else format(c['gap'], '+.3f')} | "
                      f"{c['word']} | {c['agreement']:.3f} | {_m(c['tier1'])} / {_m(c['tier2'])} |" for c in g["cells"]]
            lines.append("")
        lines += ["## Rule effects on each tier", ""]
        for p in result["rule_pairs"]:
            if not p["read"]:
                lines += [f"**{p['name']}** ({p['rule']}): not read ({p['reason']}).", ""]
                continue
            reach = "; ".join(f"{k}: {v['outcomes_differ']} outcomes and {v['games_differ']} outcomes or end steps changed, "
                              f"repeat copies {v['copy_noise_from']['outcome_differs']} / "
                              f"{v['copy_noise_to']['outcome_differs']} outcomes, "
                              f"{'reached' if v['beyond_noise'] else 'NOT shown to reach'}" for k, v in p["reach"].items())
            lines += [f"**{p['name']}** ({p['rule']}, {p['from']} -> {p['to']}; {p['ruling']}): both tiers agree in "
                      f"{p['agree_cells']} of {len(p['cells'])} cells ({reach}).", "",
                      "| Cell | Tier 1 | Tier 1 word | Tier 2 | Tier 2 word | Across tiers |", "|---|---|---|---|---|---|"]
            lines += [f"| {c['cell'][0]} v {c['cell'][1]} | {c['tier1']['from']} -> {c['tier1']['to']} | {c['tier1']['word']} "
                      f"| {c['tier2']['from']} -> {c['tier2']['to']} | {c['tier2']['word']} | {c['cross']} |"
                      for c in p["cells"]]
            lines.append("")
        lines += ["Tier 2 is another drone model, not a correction of tier 1: a difference between the two is a "
                  "difference between two simulators."]
    atomic.write_text(run_dir / "results.md", "\n".join(lines) + "\n")


# ================================================================================================ Isaac
def _isaac_cli() -> int:
    """Isaac Sim starts headless before torch is imported; the process leaves through os._exit (as L1.8)."""
    code = 1
    try:
        from _isaac_app import start_headless
        args, _app = start_headless(parser(isaac=True))
        args.headless = True
        code = run(args)
    except KeyboardInterrupt:
        code = 4
    except SystemExit as ex:
        code = ex.code if isinstance(ex.code, int) else 2
    except BaseException:  # noqa: BLE001
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)
    return code


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--dry-cpu" not in argv:
        problem = pre_isaac_problem(argv)
        if problem:
            print(f"refused: {problem[1]}" if problem[0] == 2 else problem[1], file=sys.stderr)
            sys.exit(problem[0])
        _isaac_cli()
    sys.exit(main())
