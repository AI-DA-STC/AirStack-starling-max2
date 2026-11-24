#!/usr/bin/env python
"""STE task L1.8 T46's base players re-scored on the new tier 2 (INFO; scoring only, no training). Settings, controls and
the reasons for each value: ``configs/ste_l1/tier2_score_l18.toml``; tests: ``tests/test_ste_tier2_score_l18.py``.

T46's base Guard team (trained at tag 1.6 m against strike_straight, 913 of 1,000 holds) and base Strike team (against
guard_mark_edge, 636 of 1,000 reaches), each against every script of the other team, on TIER 2 (the same command chain
driving the Isaac Lab rigid-body Starling) under three estimate-error conditions of the L1.1b model: off (v1 at 0 =
today's tier 2), nominal (T63's EXPLORATORY proposal) and conservative (2 x T63's sigma); condition 4 is tier 1 (T46's
and T44's own per-game files, no new run). One batch layout for everything: the 11 player cells, the script cells and
the repeat cells (the script cells again, same starts and seed), on T44's first ``games`` starts; one Isaac world of
(cells x games) games x 6 drones for the whole run.

    # after nvidia-smi and scripts/isaac_preflight.sh --approved-headless (exit 0), alone on the GPU:
    scripts/ste_job.py launch --task L1.8 --name l18_tier2 --run-dir runs/<date>_ste_l18_tier2 --min-s 1200 \\
        --gpu-h 0.9 -- <python> scripts/ste_tier2_score_l18.py --settings configs/ste_l1/tier2_score_l18.toml \\
        --run-dir runs/<date>_ste_l18_tier2 --cap-h 0.9 --headless
    # smoke (not of record; the known answers are NOT_CHECKED): add --games 16 --max-ticks 200 and a smaller cap

Sizing (PROPOSED, laptop RTX 5070 Ti): 15 cells x 1,000 games = 15,000 games; a batch runs the whole 2,400 ticks (a hold
lasts to the clock), so 36 M game-steps per batch. Tier 2 at about 60,000 game-steps/s at this size (L0.2 T48: 61,187 at
16,384 games, scripted; T62: the error costs nothing measurable) = about 600 s per condition, 3 conditions about 1,800
s; the tier 1 replay about 120 s; Isaac start, the world and three C-1a checks about 200 s: about 0.6 GPU-h expected,
cap 0.9 (task L1.8 cap 1.2).

What it does, in order: every pinned file checked by sha256 (exit 2, nothing played); Isaac Sim started headless before
torch is imported; control tier1_replay (the batch on tier 1 equal to T46's eval_info.npz and T44's reference game for
game, the training-opponent cells at 913 and 636); the Isaac world; then per condition (off first): condition_<c>,
physics_agreement_<c>_launch<k> (L0.13's C-1a, every launch), the batch (kept in ``games/<c>.npz`` as soon as it is
played), tier2_<c>, repeat_<c> (gated in "off", INFO in the error conditions), known_<c> ("off": T53's band). Only when
every control passes: ``results.json`` (last) and ``results.md``.

Run contract (``ste/run_contract.py``): the same command resumes at the next batch not yet checked; SIGINT or SIGTERM
stops before the next tick (exit 4); the cap is effective seconds = --cap-h x 3600 (exit 3). Exit codes: 0 done; 2
refused; 3 cap; 4 stopped; 5 a non-finite action; 6 CONTROL_FAILED (terminal). ``--dry-cpu`` (tests only, never of
record): CPU, the PyTorch reference world instead of Isaac. Observed in the training simulator; nothing here is a flight
result."""
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

HOUR_S = 3600.0
SETTINGS_COPY, PINNED_SHA = "tier2_score.toml", "settings.sha256"
CONTROLS_FILE, RESULTS, GAMES = "controls.json", "results.json", "games"
PASS, FAIL, NONFINITE, INFO, NOT_CHECKED = "PASS", "FAIL", "NONFINITE", "INFO", "NOT_CHECKED"
PLAYER = {"guard": "t46_guard", "strike": "t46_strike"}      # the players' names in a cell
PLAYER_FILES = (("gates.toml", "gates_sha256"), ("agent_final.pt", "agent_sha256"), ("eval_final.npz", "eval_sha256"),
                ("eval_info.npz", "info_sha256"), ("results.json", "results_sha256"))
TIER1_BATCH = "tier1"
OBSERVED = "observed in the training simulator"
SIMULATOR = {1: "training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, "
                "fitted PX4 response, exploratory); study tag on (P1, PROPOSED)",
             2: "training simulator, tier 2 (the same command chain driving the Isaac Lab 2.3.2 rigid-body Starling in "
                "PhysX, PX4 1.14 cascade copy, L1.1b estimate error per condition); study tag on (P1, PROPOSED)"}
_KEYS = {
    "job": {"task", "what", "kind", "device", "games", "ticks_cap", "cap_h", "cap_check_every_ticks"},
    "game": {"file", "sha256", "reference", "reference_sha256", "start_sha256", "reference_variant"},
    "guard_player": {"label", "dir", "variant", "own_wins", "own_source", *(k for _, k in PLAYER_FILES)},
    "strike_player": {"label", "dir", "variant", "own_wins", "own_source", *(k for _, k in PLAYER_FILES)},
    "cells": {"scripts", "repeat"},
    "controls": {"condition_difference", "gated_repeat_condition", "repeat_count_tol_games", "repeat_differ_tol_games",
                 "known_condition", "known_cell", "known_games", "known_holds_min", "known_holds_max", "known_source",
                 "agree_guard", "agree_strike", "agree_ticks", "agree_max_m", "agree_seed"},
    "tier1": {"source"},
    "conditions": {"name", "label", "params", "params_sha256"},
}


WHO = "scripts/ste_tier2_score_l18.py"         # named in a refusal of a skills gate file (STE L3)


def say(text: str) -> None:
    print(f"[l18] {text}", flush=True)


def refuse(text: str) -> int:
    print(f"refused: {text}", file=sys.stderr, flush=True)
    return 2


def parser(isaac: bool = False) -> argparse.ArgumentParser:
    """The command line; ``isaac`` leaves out --headless (Isaac Lab's launcher adds its own)."""
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


def _path(text: str) -> Path:
    p = Path(text)
    return p if p.is_absolute() else ROOT / p


def _sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _exact(table, keys: set, where: str) -> dict:
    if not isinstance(table, dict):
        raise ValueError(f"[{where}] must be a table")
    unknown, missing = sorted(set(table) - keys), sorted(keys - set(table))
    if unknown or missing:
        raise ValueError(f"[{where}]: unknown key(s) {unknown}, missing key(s) {missing}")
    return table


# ================================================================================================ settings (stdlib only)
def load_settings(path: Path) -> dict:
    """The settings file with exactly its keys; ValueError names the first problem."""
    data = tomllib.loads(Path(path).read_text())
    unknown = sorted(set(data) - set(_KEYS))
    if unknown:
        raise ValueError(f"unknown section(s): {unknown}")
    for sec in _KEYS:
        if sec != "conditions":
            _exact(data.get(sec), _KEYS[sec], sec)
    conds = data.get("conditions")
    if not isinstance(conds, list) or not conds:
        raise ValueError("[[conditions]]: at least one")
    for c in conds:
        _exact(c, _KEYS["conditions"], "conditions")
    names = [c["name"] for c in conds]
    if len(set(names)) != len(names) or not all(n.replace("_", "").isalnum() for n in names):
        raise ValueError(f"[[conditions]] names must be distinct letters, digits and '_': {names}")
    ctl = data["controls"]
    for key in ("gated_repeat_condition", "known_condition"):
        if ctl[key] != names[0]:
            raise ValueError(f"controls.{key} must be the first condition ({names[0]}): its gated controls fail fast")
    scripts = [tuple(c) for c in data["cells"]["scripts"]]
    if any(tuple(c) not in scripts for c in data["cells"]["repeat"]) or tuple(ctl["known_cell"]) not in scripts:
        raise ValueError("[cells] repeat and controls.known_cell must be among [cells] scripts")
    if any(PLAYER["guard"] in c or PLAYER["strike"] in c for c in scripts):
        raise ValueError("[cells] scripts must be scripts only")
    if not (0 < int(data["job"]["games"]) and 0 < int(data["job"]["ticks_cap"]) and float(data["job"]["cap_h"]) > 0):
        raise ValueError("job.games, job.ticks_cap and job.cap_h must be above 0")
    return data


def pin_problems(s: dict) -> list[str]:
    """One line per pinned file that is missing or another (players, game, reference, each condition's parameter file)."""
    want = []
    for side in ("guard", "strike"):
        p = s[f"{side}_player"]
        want += [(_path(p["dir"]) / name, p[key], f"the {side} player's {name}") for name, key in PLAYER_FILES]
    g = s["game"]
    want += [(_path(g["file"]), g["sha256"], "the game file"), (_path(g["reference"]), g["reference_sha256"], "T44's reference")]
    want += [(_path(c["params"]), c["params_sha256"], f"condition {c['name']}'s parameter file") for c in s["conditions"]]
    out = []
    for path, sha, what in want:
        if not path.is_file():
            out.append(f"{what} {path} is missing")
        elif _sha(path) != sha:
            out.append(f"{what} {path} has sha256 {_sha(path)}, the settings pin {sha}")
    return out


def condition_cfg(base, cond: dict):
    """A condition's game: the base game file with the physics backend and the condition's parameter file."""
    return base.replace(**{"starling.backend": "physics", "starling.physics_params": cond["params"]})


def layout(s: dict) -> SimpleNamespace:
    """The batch's cells (Guard, Strike): the Guard player v every Strike script, every Guard script v the Strike
    player, the script cells, the repeat cells; with the index of each kind."""
    from svg_training.ste import exploit
    gates = exploit.load_gates(_path(s["guard_player"]["dir"]) / "gates.toml")
    exploit.skills.require_velocity_learner(gates, WHO)                  # STE L3: the skills route is not wired here
    guards, strikes = list(gates.players["guards"]), list(gates.players["strikes"])
    scripts = [tuple(c) for c in s["cells"]["scripts"]]
    repeat = [tuple(c) for c in s["cells"]["repeat"]]
    cells = [(PLAYER["guard"], x) for x in strikes] + [(g, PLAYER["strike"]) for g in guards] + scripts + repeat
    first = len(strikes) + len(guards)
    return SimpleNamespace(cells=cells, guards=guards, strikes=strikes, scripts=scripts, repeat=repeat,
                           script_idx=list(range(first, first + len(scripts))),
                           repeat_pairs=[(first + len(scripts) + i, first + scripts.index(c)) for i, c in enumerate(repeat)])


def is_script(cell: tuple) -> bool:
    return PLAYER["guard"] not in cell and PLAYER["strike"] not in cell


def pre_isaac_problem(argv: list[str]) -> tuple[int, str] | None:
    """Before Isaac Sim starts (standard library only): (exit code, why) or None."""
    if "--headless" not in argv:
        return 2, "the tier 2 batches start Isaac Lab: --headless (after scripts/isaac_preflight.sh --approved-headless)"
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--run-dir", type=Path)
    known, _ = pre.parse_known_args(argv)
    controls = known.run_dir / CONTROLS_FILE if known.run_dir is not None else None
    if controls is not None and controls.is_file():
        statuses = {v.get("status") for v in json.loads(controls.read_text()).values()}
        if NONFINITE in statuses:
            return 5, f"a non-finite value was recorded in {controls}: no retry"
        if FAIL in statuses:
            return 6, f"a control failed in {controls}: terminal, a new run needs a new run folder (CONTROL_FAILED)"
    return None


# ================================================================================================ the run
def main(argv: list[str] | None = None, world_factory=None) -> int:
    return run(parser().parse_args(list(sys.argv[1:] if argv is None else argv)), world_factory)


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
    try:
        ctx = Context(s, a, device, world_factory)
    except ValueError as err:
        return refuse(str(err))
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
    """Everything the run reads, loaded and checked (ValueError = refused, nothing played)."""

    def __init__(self, s: dict, a, device: str, world_factory):
        import numpy as np
        import torch

        from svg_training.ste import exploit, exploit_train, sweep
        self.s, self.a, self.device, self.np, self.exploit = s, a, device, np, exploit
        for side in ("guard", "strike"):      # STE L3: a skills player is refused before anything else is read
            exploit.skills.require_velocity_learner(exploit.load_gates(_path(s[f"{side}_player"]["dir"]) / "gates.toml"),
                                                    WHO)
        self.n = int(a.games or s["job"]["games"])
        self.ticks = int(a.max_ticks or s["job"]["ticks_cap"])
        self.lay = layout(s)
        g = s["game"]
        self.base = exploit.load_game_cfg_file(_path(g["file"]))
        self.ref = exploit.load_reference(_path(g["reference"]))
        if self.ref.start_sha256 != g["start_sha256"]:
            raise ValueError(f"T44's reference starts have sha256 {self.ref.start_sha256}, the settings pin {g['start_sha256']}")
        self.rv, self.seed = g["reference_variant"], int(self.ref.meta["seed"])
        self.players, self.info, self.own, self.opp, self.hold, self.tier1_counts = {}, {}, {}, {}, set(), {}
        for side in ("guard", "strike"):
            p = s[f"{side}_player"]
            pdir = _path(p["dir"])
            gates = exploit.load_gates(pdir / "gates.toml")
            if g["sha256"] != gates.games[gates.variants[p["variant"]]["game"]].sha256:
                raise ValueError(f"the {side} player's game is not {g['file']}")
            if gates.reference["sha256"] != g["reference_sha256"]:
                raise ValueError(f"the {side} player's reference is not {g['reference']}")
            if (list(gates.players["guards"]), list(gates.players["strikes"])) != (self.lay.guards, self.lay.strikes):
                raise ValueError(f"the {side} player's gate file lists other scripts than the Guard player's")
            if int(gates.run["eval_games"]) < self.n:
                raise ValueError(f"games {self.n} is above the {side} player's {gates.run['eval_games']} evaluation games")
            self.opp[side] = exploit.opponent_of(gates, p["variant"], side)
            others = self.lay.strikes if side == "guard" else self.lay.guards
            if self.opp[side] not in others:
                raise ValueError(f"the {side} player's training opponent {self.opp[side]} is not a scored script")
            mods = torch.load(pdir / "agent_final.pt", map_location=device, weights_only=False)
            team = exploit_train.team_from_modules(side, mods, list(gates.trainer["hidden"]), device)
            team.name = PLAYER[side]
            self.players[PLAYER[side]] = team
            self.hold.add(int(gates.trainer["decision_ticks"]))
            n_info = int(gates.run["eval_games"])
            with np.load(pdir / "eval_info.npz") as d:
                rec = {k: d[k] for k in d.files}
            if len(rec["outcome"]) != len(others) * n_info:
                raise ValueError(f"the {side} player's eval_info.npz holds {len(rec['outcome'])} games, not "
                                 f"{len(others)} x {n_info}")
            self.info[side] = {x: {k: v[j * n_info:j * n_info + self.n] for k, v in rec.items()}
                               for j, x in enumerate(others)}
            # the counts its results.json reports for the same cells (the record's numbers; checked equal below)
            rj = json.loads((pdir / "results.json").read_text())["info"]
            self.tier1_counts[side] = {x: rj[f"{x} v {exploit.EXPLOITER}" if side == "strike"
                                            else f"{exploit.EXPLOITER} v {x}"] for x in others}
            self.own[side] = int(p["own_wins"])
        if len(self.hold) != 1:
            raise ValueError(f"the two players hold their decisions for different ticks: {sorted(self.hold)}")
        self.hold = self.hold.pop()
        if self.n == int(s["job"]["games"]) and self.ticks == int(s["job"]["ticks_cap"]):
            for side in ("guard", "strike"):
                won = exploit.GUARD_WIN if side == "guard" else exploit.STRIKE_WIN
                for x, cnt in self.tier1_counts[side].items():
                    k = int(np.sum(self.info[side][x]["outcome"] == won))
                    if k != int(cnt["holds" if side == "guard" else "reaches"]):
                        raise ValueError(f"the {side} player's eval_info.npz v {x} counts {k}, its results.json {cnt}")
        self.tol = 0.0 if device == "cpu" else float(sweep.load_gates().controls["same_seed_closest_tol_m"])
        self.world_factory = world_factory or (torch_world_factory if a.dry_cpu else isaac_world_factory)
        self.world = None

    # ------------------------------------------------------------------------------------------- one batch
    def batch(self, cfg, world, should_stop) -> dict:
        return self.exploit.play_cells(cfg, "3v3", self.ref, self.lay.cells, self.n, self.device, self.seed, self.ticks,
                                       hold_ticks=self.hold, should_stop=should_stop, world=world, players=self.players)

    def cell(self, pg: dict, i: int) -> dict:
        return self.exploit.slice_cell(pg, i, self.n)

    # ------------------------------------------------------------------------------------------- controls
    def check_tier1(self, pg: dict) -> dict:
        from svg_training.ste import scoring
        from svg_training.viz import replay3d as r3
        ex = self.exploit
        rows, ok = {}, True
        for i, c in enumerate(self.lay.cells):
            if is_script(c):
                continue
            side = "guard" if c[0] == PLAYER["guard"] else "strike"
            x = c[1] if side == "guard" else c[0]
            chk = r3.check_against_record(self.cell(pg, i), self.info[side][x], tol_m=self.tol)
            rows[f"{c[0]} v {c[1]}"] = {"equal": chk["equal"], "mismatches": chk["mismatches"]}
            ok &= chk["equal"]
        scripts = scoring.check_script_cells(pg, self.lay.cells, self.ref, self.rv, self.n, self.ticks, is_script,
                                             phase="tier1")
        own = {}
        for side in ("guard", "strike"):
            c = (PLAYER["guard"], self.opp["guard"]) if side == "guard" else (self.opp["strike"], PLAYER["strike"])
            k, _ = scoring.win_count(self.cell(pg, self.lay.cells.index(c)), side)
            own[side] = {"k": k, "expected": self.own[side]}
            ok &= k == self.own[side]
        ok &= scripts["status"] == PASS
        status = NONFINITE if scripts["status"] == NONFINITE else PASS if ok else FAIL
        bad = [k for k, v in rows.items() if not v["equal"]]
        return {"status": status, "players": rows, "scripts": scripts["cells"], "own": own, "plumbing": scripts["plumbing"],
                "tol_m": self.tol,
                "detail": f"player cells v eval_info: {'EQUAL' if not bad else 'DIFFERENT ' + str(bad)}; script and repeat "
                          f"cells v T44: {scripts['status']}; Guard v {self.opp['guard']} holds {own['guard']['k']} "
                          f"(record {self.own['guard']}); {self.opp['strike']} v Strike reaches {own['strike']['k']} "
                          f"(record {self.own['strike']})"}

    def check_condition(self, cond: dict) -> dict:
        import dataclasses

        from svg_training.core.physics_layer import load_game_physics_params
        from svg_training.models.physics_params import ERROR_KEYS
        from svg_training.ste import tier2_train as T
        cfg = condition_cfg(self.base, cond)
        diff = T.cfg_differences(self.base, cfg)
        p = load_game_physics_params(cfg)
        v1 = load_game_physics_params(condition_cfg(self.base, {"params": "params/starling_physics_v1.toml"}))
        other = [f.name for f in dataclasses.fields(p) if f.name not in ERROR_KEYS and f.name != "source"
                 and getattr(p, f.name) != getattr(v1, f.name)]
        want = tomllib.loads(_path(cond["params"]).read_text())["model"]
        flies = {k: getattr(p, k) for k in ERROR_KEYS}
        same = flies == {k: float(want[k]) for k in ERROR_KEYS}
        sha_ok = _sha(_path(cond["params"])) == cond["params_sha256"]
        ok = diff == list(self.s["controls"]["condition_difference"]) and not other and same and sha_ok
        return {"status": PASS if ok else FAIL, "differs_from_base": diff, "differs_from_v1_besides_error": other,
                "state_error": flies, "params": cond["params"], "params_sha256": _sha(_path(cond["params"])),
                "detail": f"game differs from the base file in {diff}; parameters differ from v1 besides state_error_* in "
                          f"{other}; flies {flies} ({'= its file' if same else 'NOT its file'})"}

    def check_tier2(self, pg: dict, cond: str) -> dict:
        from svg_training.ste import scoring, tier2_train as T
        parts = scoring.plumbing_controls(pg, self.ref, self.n, cond)
        tier, nf = T.batch_tier(pg), int(pg["physics_nonfinite"])
        upsets = int(self.np.sum(pg["upset"])) if "upset" in pg else None
        status = scoring.control_status(parts, tier == 2 and nf == 0)
        return {"status": status, "tier": tier, "motion": str(pg["motion"]), "physics_nonfinite": nf, "upsets": upsets,
                "plumbing": parts, "detail": f"ran {pg['motion']} (tier {tier}); non-finite wrench or setpoint {nf}; upset "
                                             f"games {upsets} (INFO); " + "; ".join(f"{k} {v['status']}" for k, v in parts.items())}

    def check_repeat(self, pg: dict, cond: str) -> dict:
        from svg_training.viz import replay3d as r3
        c = self.s["controls"]
        gated = cond == c["gated_repeat_condition"]
        rows, ok = {}, True
        for i, j in self.lay.repeat_pairs:
            a, b = self.cell(pg, i), self.cell(pg, j)
            holds_a = int(self.np.sum(a["outcome"] == self.exploit.GUARD_WIN))
            holds_b = int(self.np.sum(b["outcome"] == self.exploit.GUARD_WIN))
            differ = int(self.np.sum(a["outcome"] != b["outcome"]))
            exact = r3.check_against_record(a, b, tol_m=self.tol)
            within = abs(holds_a - holds_b) <= int(c["repeat_count_tol_games"]) and differ <= int(c["repeat_differ_tol_games"])
            rows[f"{self.lay.cells[i][0]} v {self.lay.cells[i][1]}"] = {"holds": [holds_b, holds_a], "outcome_differs": differ,
                                                                         "exact_mismatches": exact["mismatches"],
                                                                         "exact_equal": exact["equal"], "within": within}
            ok &= within
        text = "; ".join(f"{k}: holds {v['holds'][0]} / {v['holds'][1]}, {v['outcome_differs']} games end otherwise, "
                         f"{'exactly equal' if v['exact_equal'] else 'not exactly equal ' + str(v['exact_mismatches'])}"
                         for k, v in rows.items())
        return {"status": (PASS if ok else FAIL) if gated else INFO, "info": not gated, "cells": rows,
                "tolerance": {"count": int(c["repeat_count_tol_games"]), "differ": int(c["repeat_differ_tol_games"])},
                "detail": text + ("" if gated else " (INFO: each copy draws its own estimate error)")}

    def check_known(self, pg: dict) -> dict:
        c = self.s["controls"]
        if self.a.smoke or self.n != int(c["known_games"]) or self.ticks != int(self.s["job"]["ticks_cap"]):
            return {"status": NOT_CHECKED, "detail": f"{self.n} games x {self.ticks} ticks: the known answer is for "
                                                     f"{c['known_games']} games x {self.s['job']['ticks_cap']} ticks"}
        return known_check(self.cell(pg, self.lay.cells.index(tuple(c["known_cell"]))), c, self.exploit.GUARD_WIN)

    def agreement(self, cfg) -> dict:
        from svg_training.ste import tier2_train as T
        c = self.s["controls"]
        g = SimpleNamespace(controls={k: c[k] for k in ("agree_guard", "agree_strike", "agree_ticks", "agree_max_m")},
                            run={"size": "3v3", "train_seed": int(c["agree_seed"])})
        return T.physics_agreement(g, cfg, self.world, self.device)

    # ------------------------------------------------------------------------------------------- the run
    def play(self, guard, launches: int) -> int:
        from svg_training.core.physics_layer import load_game_physics_params
        from svg_training.ste import scoring, sweep
        from svg_training.ste.run_contract import EXIT_CONTROL_FAILED, EXIT_FOR_STOP, STOP_CAP
        import ste_sweep_l011 as l011
        rd = self.a.run_dir
        (rd / GAMES).mkdir(exist_ok=True)
        controls = json.loads((rd / CONTROLS_FILE).read_text()) if (rd / CONTROLS_FILE).is_file() else {}
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
                write_md(rd, self, controls, None)
                say(f"{'NON-FINITE' if code == 5 else 'CONTROL FAILED'}: no number is reported (exit {code})")
            return code

        def stopped() -> int:
            save()
            reason = guard.stop_reason() or STOP_CAP
            say(f"stopped ({reason}); the same command resumes at the next batch not yet checked")
            return EXIT_FOR_STOP[reason]

        def played(name: str, cfg, world, check_key: str):
            """The batch ``name``: loaded when its control passed, else played and saved. (pg, seconds) or None."""
            path = rd / GAMES / f"{name}.npz"
            if controls.get(check_key, {}).get("status") in (PASS, NOT_CHECKED) and path.is_file():
                return scoring.load_batch(path), None
            say(f"batch {name}: {len(self.lay.cells)} cells x {self.n} games, {self.ticks} ticks on {self.device}")
            t0 = time.perf_counter()
            pg = self.batch(cfg, world, should_stop)
            took = time.perf_counter() - t0
            scoring.save_batch(path, pg)
            l011.write_json(path.with_suffix(".json"), {"cells": [list(c) for c in self.lay.cells], "games_per_cell": self.n,
                                                        "ticks_cap": self.ticks, "seconds": took,
                                                        "params": cfg.starling.physics_params,
                                                        "backend": cfg.starling.backend})
            return pg, took

        pgs = {}
        try:
            # ---- tier 1: the batch's layout replays T46's and T44's own games (condition 4's source)
            if self.a.smoke:
                if "tier1_replay" not in controls:
                    settle("tier1_replay", {"status": NOT_CHECKED, "detail": "smoke: not played"})
            else:
                got = played(TIER1_BATCH, self.base, None, "tier1_replay")
                if got[1] is not None:
                    code = settle("tier1_replay", {**self.check_tier1(got[0]), "seconds": got[1]})
                    if code is not None:
                        return code
            # ---- tier 2: every condition's settings and C-1a first (a failure there costs no batch), then the batches
            conds = [(c["name"], condition_cfg(self.base, c), c) for c in self.s["conditions"]]
            for name, cfg, cond in conds:
                if controls.get(f"condition_{name}", {}).get("status") != PASS:
                    code = settle(f"condition_{name}", self.check_condition(cond))
                    if code is not None:
                        return code
            todo = [(name, cfg) for name, cfg, _ in conds
                    if not (controls.get(f"tier2_{name}", {}).get("status") == PASS and (rd / GAMES / f"{name}.npz").is_file())]
            if todo:
                t0 = time.perf_counter()
                self.world = self.world_factory(len(self.lay.cells) * self.n, 6, load_game_physics_params(todo[0][1]),
                                                self.device)
                say(f"world: {getattr(self.world, 'label', type(self.world).__name__)}, "
                    f"{len(self.lay.cells) * self.n} games x 6 drones ({time.perf_counter() - t0:.0f} s)")
            for name, cfg in todo:
                ag = self.agreement(cfg)
                code = settle(f"physics_agreement_{name}_launch{launches}", {
                    "status": PASS if ag["pass"] else FAIL, **ag,
                    "detail": f"{ag['games']} games x {ag['drones']} drones x {ag['ticks']} ticks on {ag['world']}: "
                              f"largest gap {ag['max_gap_m']:.5f} m (limit {ag['limit_m']} m)"})
                if code is not None:
                    return code
            for name, cfg, _ in conds:
                pg, took = played(name, cfg, self.world, f"tier2_{name}")
                checks = [(f"tier2_{name}", lambda: self.check_tier2(pg, name)),
                          (f"repeat_{name}", lambda: self.check_repeat(pg, name))]
                if name == self.s["controls"]["known_condition"]:
                    checks.append((f"known_{name}", lambda: self.check_known(pg)))
                for key, check in checks:          # a resume after a stop between two of them computes the missing ones
                    if took is None and key in controls:
                        continue
                    code = settle(key, {**check(), "seconds": took})
                    if code is not None:
                        return code
                pgs[name] = pg
        except sweep.SweepStopped:
            return stopped()
        missing, bad = required_problems(controls, self.s, bool(self.a.smoke))
        if missing or bad:
            say(f"not published: missing controls {missing}, not passed {bad}")
            write_md(rd, self, controls, None)
            return EXIT_CONTROL_FAILED
        result = results_of(self, controls, pgs, guard)
        result["complete"] = True                                  # written last
        l011.write_json(rd / RESULTS, result)
        write_md(rd, self, controls, result)
        guard.save(len(controls), {**state, "done": sorted(controls), "phase": "done"})
        for line in result["readings"]:
            say(line)
        say(f"done: {rd / 'results.md'}")
        return 0


def required_problems(controls: dict, s: dict, smoke: bool) -> tuple[list, dict]:
    """Fail closed: (required controls missing, controls not passed). Required: tier1_replay; per condition
    condition_, tier2_, repeat_ and at least one physics_agreement_<c>_launch<k>; known_<known_condition>. PASS, INFO
    (repeat_ of an error condition) and, in a smoke only, NOT_CHECKED are accepted."""
    names = [c["name"] for c in s["conditions"]]
    want = {"tier1_replay", f"known_{s['controls']['known_condition']}"}
    want |= {f"{k}_{n}" for n in names for k in ("condition", "tier2", "repeat")}
    missing = sorted(want - set(controls))
    missing += [f"physics_agreement_{n}_launch<k>" for n in names
                if not any(k.startswith(f"physics_agreement_{n}_launch") for k in controls)]
    ok = {PASS, INFO} | ({NOT_CHECKED} if smoke else set())
    bad = {k: v["status"] for k, v in controls.items() if v["status"] not in ok}
    bad.update({k: INFO for k, v in controls.items() if v["status"] == INFO and not v.get("info")})
    return missing, bad


def known_check(cell_pg: dict, c: dict, guard_win: int) -> dict:
    """The known-answer cell's holds inside [known_holds_min, known_holds_max] (T53's Wilson 95 % interval)."""
    import numpy as np
    holds = int(np.sum(np.asarray(cell_pg["outcome"]) == guard_win))
    ok = int(c["known_holds_min"]) <= holds <= int(c["known_holds_max"])
    return {"status": PASS if ok else FAIL, "holds": holds, "band": [int(c["known_holds_min"]), int(c["known_holds_max"])],
            "source": c["known_source"],
            "detail": f"{c['known_cell'][0]} v {c['known_cell'][1]} holds {holds} (band {c['known_holds_min']}-"
                      f"{c['known_holds_max']}: {c['known_source']})"}


# ================================================================================================ results
def paired(a, b, won: int) -> dict:
    """Per start, wins of the counted side in run a and run b: both, a only, b only, neither (finished games only)."""
    import numpy as np
    a, b = np.asarray(a), np.asarray(b)
    from svg_training.core.rewards import RUNNING
    if (a == RUNNING).any() or (b == RUNNING).any():
        return {"note": "unfinished games: no paired counts"}
    wa, wb = a == won, b == won
    return {"both": int(np.sum(wa & wb)), "first_only": int(np.sum(wa & ~wb)), "second_only": int(np.sum(~wa & wb)),
            "neither": int(np.sum(~wa & ~wb))}


def results_of(ctx: Context, controls: dict, pgs: dict, guard) -> dict:
    from svg_training.ste import scoring
    ex, np = ctx.exploit, ctx.np
    conds = [c["name"] for c in ctx.s["conditions"]]
    rows, readings = [], []
    for i, c in enumerate(ctx.lay.cells):
        if i in [r for r, _ in ctx.lay.repeat_pairs]:
            continue                                                # repeats are a control, not a row
        if is_script(c):
            side, t1 = "guard", {k: np.asarray(v)[:ctx.n] for k, v in ctx.ref.cell(ctx.rv, *c).items()}
            t1_source = f"T44 reference, {c[0]} v {c[1]}"
        else:
            side = "guard" if c[0] == PLAYER["guard"] else "strike"
            x = c[1] if side == "guard" else c[0]
            t1, t1_source = ctx.info[side][x], f"T46 {side} player's eval_info.npz, v {x}"
        won = ex.GUARD_WIN if side == "guard" else ex.STRIKE_WIN
        k1, m1 = scoring.win_count(t1, side)                       # finished games only, as every tier 2 cell
        t2 = {}
        for name in conds:
            cp = ex.slice_cell(pgs[name], i, ctx.n)
            k, m = scoring.win_count(cp, side)
            t2[name] = {**scoring.rate(k, m), "end_reasons": scoring.end_reasons(cp, int(pgs[name]["game_ticks"])),
                        "length_median_s": scoring.length_median_s(cp), "tag_stats": scoring.tag_stats(cp),
                        "upsets": int(np.sum(cp["upset"])) if "upset" in cp else None}
        first = conds[0]
        base_out = ex.slice_cell(pgs[first], i, ctx.n)["outcome"]
        row = {"cell": list(c), "counted": "holds" if side == "guard" else "reaches", "script_cell": is_script(c),
               "training_opponent": (not is_script(c)) and (c == (PLAYER["guard"], ctx.opp["guard"])
                                                           or c == (ctx.opp["strike"], PLAYER["strike"])),
               "tier1": {**scoring.rate(k1, m1), "unfinished": ctx.n - m1, "source": t1_source}, "tier2": t2,
               "change": {f"{first}_minus_tier1": t2[first]["k"] - k1,
                          **{f"{nm}_minus_{first}": t2[nm]["k"] - t2[first]["k"] for nm in conds[1:]}},
               "paired": {f"tier1_v_{first}": paired(t1["outcome"], base_out, won),
                          **{f"{first}_v_{nm}": paired(base_out, ex.slice_cell(pgs[nm], i, ctx.n)["outcome"], won)
                             for nm in conds[1:]}}}
        rows.append(row)
        if row["training_opponent"]:
            readings.append(f"{cell_text(c)}: {row['counted']} tier 1 {k1}/{m1}; tier 2 " + ", ".join(
                f"{nm} {t2[nm]['k']}/{t2[nm]['n']}" for nm in conds) + f" (tier 2 off minus tier 1: "
                f"{t2[first]['k'] - k1:+d}; LABELLED: tier 2 is another drone model, not a correction of tier 1)")
    from ste_exploit_l012 import machine
    m = machine()
    return {"what": f"STE {ctx.s['job']['task']}: {ctx.s['job']['what']}; {OBSERVED}", "task": ctx.s["job"]["task"],
            "kind": ctx.s["job"]["kind"], "simulator": SIMULATOR, "controls": controls, "controls_pass": True,
            "conditions": [{**c, "state_error": controls[f"condition_{c['name']}"]["state_error"]}
                           for c in ctx.s["conditions"]],
            "tier1_source": ctx.s["tier1"]["source"], "rows": rows, "readings": readings,
            "players": {side: {**ctx.s[f"{side}_player"], "opponent": ctx.opp[side], "name": PLAYER[side]}
                        for side in ("guard", "strike")},
            "games": ctx.n, "ticks_cap": ctx.ticks, "seed": ctx.seed, "start_sha256": ctx.ref.start_sha256,
            "cells": [list(c) for c in ctx.lay.cells], "device": ctx.device, "dry_cpu": bool(ctx.a.dry_cpu),
            "smoke": bool(ctx.a.smoke), "batch_seconds": {k: v.get("seconds") for k, v in controls.items() if "seconds" in v},
            "effective_s": guard.effective_s(), "cap_h": ctx.a.cap_h, "machine": m, "gpu": m.get("gpu"),
            "code": json.loads((ctx.a.run_dir / "code.json").read_text()),
            "settings_sha256": _sha(ctx.a.settings)}


def cell_text(c) -> str:
    return f"{c[0]} v {c[1]}"


def _ci(r: dict) -> str:
    lo, hi = r["ci"]
    return "-" if lo is None else f"{lo:.3f}-{hi:.3f}"


def write_md(run_dir: Path, ctx: Context, controls: dict, result: dict | None) -> None:
    from svg_training.ste import atomic
    lines = [f"Simulator: {SIMULATOR[2]}; tier 1 column: {SIMULATOR[1]}. {OBSERVED.capitalize()}; nothing here is a flight "
             f"result. Estimate-error values: EXPLORATORY (T63, one flight log).", "",
             f"# {ctx.s['job']['task']}: {ctx.s['job']['what']} (INFO)", "",
             "## Controls (read these first; any control not PASS, INFO or NOT_CHECKED: no number is reported)", "",
             "| Control | Status | Detail |", "|---|---|---|"]
    lines += [f"| {k} | **{v['status']}** | {v['detail']} |" for k, v in controls.items()]
    if result is not None:
        conds = [c["name"] for c in result["conditions"]]
        first = conds[0]
        lines += ["", "## Conditions", "", "| Condition | Parameter file | state_error (sigma, tau) |", "|---|---|---|"]
        lines += [f"| {c['name']}: {c['label']} | `{c['params']}` | " + ", ".join(
            f"{k.removeprefix('state_error_')} {v:g}" for k, v in c["state_error"].items()) + " |"
            for c in result["conditions"]]
        lines += ["", f"## Wins per cell ({result['games']} starts per cell, T44's first; {result['ticks_cap']} ticks), "
                  "Wilson 95 %", "",
                  f"| Cell (Guard v Strike) | Counted | Tier 1 | " + " | ".join(f"Tier 2 {nm}" for nm in conds) +
                  f" | Tier 2 {first} minus tier 1 | Paired tier 1 / {first}: both, tier 1 only, {first} only, neither |",
                  "|---|---|---|" + "---|" * len(conds) + "---|---|"]
        for r in result["rows"]:
            mark = " (training opponent)" if r["training_opponent"] else " (script cell)" if r["script_cell"] else ""
            p = r["paired"][f"tier1_v_{first}"]
            pt = "-" if "note" in p else f"{p['both']}, {p['first_only']}, {p['second_only']}, {p['neither']}"
            lines.append(f"| {cell_text(r['cell'])}{mark} | {r['counted']} | {r['tier1']['k']}/{r['tier1']['n']} "
                         f"({_ci(r['tier1'])}) | " + " | ".join(f"{r['tier2'][nm]['k']}/{r['tier2'][nm]['n']} "
                                                               f"({_ci(r['tier2'][nm])})" for nm in conds) +
                         f" | {r['change'][f'{first}_minus_tier1']:+d} | {pt} |")
        lines += ["", "Tier 2 is another drone model (the Isaac Lab rigid-body Starling under the PX4 cascade copy), not "
                  "a correction of tier 1: the 'minus tier 1' column is a difference between two simulators, LABELLED so.",
                  "", "Reading:", ""] + [f"- {x}." for x in result["readings"]]
    atomic.write_text(run_dir / "results.md", "\n".join(lines) + "\n")


# ================================================================================================ worlds
def isaac_world_factory(n: int, m: int, params, device: str):
    """IsaacWorld of n games x m drones (Isaac Sim already started), as scripts/ste_tier2_l013.py."""
    from svg_training.compat import isaaclab_232 as isaac
    sim = isaac.make_physics_sim(params.physics_dt_s, device)
    world = isaac.IsaacWorld(sim, n, m, params.airframe, params.physics_dt_s)
    isaac.physics_play(sim, world)
    return world


def torch_world_factory(n: int, m: int, params, device: str):
    from svg_training.ste import tier2_train as T
    return T.torch_world_factory(n, m, params, device)


def _isaac_cli() -> int:
    """Isaac Sim starts headless before torch is imported; the process leaves through os._exit (Kit's shutdown swallows
    exit codes). Ctrl-C during the start exits 4."""
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
    except BaseException:  # noqa: BLE001  (any failure: printed; the waiter reads FAILED)
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)          # never simulation_app.close() (it swallows exit codes)
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
