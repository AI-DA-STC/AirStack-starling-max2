#!/usr/bin/env python3
"""Stand-in trainer (S2 Task 10, built in S2b Task 9): skrl IPPO, 2 Guard drones v 1 scripted Strike drone.

The stand-in is a PIPE TEST: it proves that the game, the skrl adapter, training, TensorBoard, saving, loading and
scoring connect, on each motion backend. It is never "the policy" and never a strategy of record.

  # PyTorch (tier 1), no Isaac: pure partner rules, or the Starling layer (exploratory drone model)
  train_standin.py --config configs/s2.toml --seed <s> --name <date>_s2b_standin_pure_seed<s> [--motion pure]
  train_standin.py --config configs/s2.toml --seed <s> --name <date>_s2b_standin_starling_seed<s> --motion starling
  # a smoke run on any machine, CPU included (seconds; never a run of record). --device auto (default) = cuda if
  # PyTorch sees a GPU, else the cpu with a note
  train_standin.py --seed 1 --name smoke --smoke
  # Isaac Lab (tier 2): physics drone, headless, after scripts/isaac_preflight.sh. ON THE HOST: the container
  # image has skrl 1.4.3 and this trainer needs skrl 2.x (the host's conda env_isaaclab has 2.1.0); it refuses
  # (exit 2, before Isaac starts) on another skrl major version.
  PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/train_standin.py --headless \
      --config configs/s2.toml --seed <s> --name <date>_s2b_standin_physics_seed<s> --motion physics
  # the gate verdict over the three seeds' score.py outputs (no training)
  train_standin.py verdict --gates runs/<group>/gates.toml --scores runs/<a>,runs/<b>,runs/<c> --out runs/<group>

Settings: ``configs/s2.toml [standin]`` as committed (unchanged, pinned by tests/test_s2b_config.py). The game is
``configs/s2_game.toml`` on the committed neutral values ONLY (the local partner file is never read), with
``[rewards] shaping_weight`` from [standin]. ``--motion``: pure = pure partner rules; starling = the Starling layer
(fitted exploratory model); physics = the Starling layer's command chain flying the physics drone in an
``IsaacWorld`` (the drone's PX4 gains with the owner's SIM-ONLY yaw-rate gains; its line goes into interface.toml).
Wall-clock cap from ``configs/s2b.toml [standin_s2b]`` (45 min PyTorch, 180 min Isaac Lab); it counts TRAINING
time only (evaluation time is recorded beside it), and when reached the run stops at the next update and keeps
its last networks (written in train_result.json; not an abort).

``--settings standin_v2`` (S2b Task 9 runs of record, owner-approved 17 Nov 2026) reads ``configs/s2b.toml
[standin_v2]`` in place of [standin]: the same keys plus ``init_log_std`` (every policy's log std starts there),
``frozen_log_std_axes`` (per motion: the axes whose log std is never trained, by the same gradient hook as
``--diag-freeze-log-std-axes``) and skrl's defaults written down (passed to IPPO_CFG and checked against skrl's
effective values). The caps stay those of [standin_s2b]. The table name, file, sha256 and values go into
interface.toml, the TensorBoard settings text and train_result.json; such a run carries no [diagnostic] table, and
the ``--diag-*`` flags are refused with it. ``--stop-at`` / ``--stop-file``: an operator stop at the next update
boundary (final evaluation done, status ABORTED with the reason, exit 4), for runs with a deadline.

Strike team: ``SplitStrategy`` over the game slots by ``[standin] opponent_mix`` (first half strike_straight,
second half strike_flank). skrl IPPO: one Gaussian policy and one value network per Guard name, ``hidden`` ELU
layers, ``RunningStandardScaler`` on observations and values, the [standin] PPO settings, skrl's defaults for the
rest. Training runs ``[standin] game_steps_per_seed // num_games`` skrl timesteps (``--timesteps-override``).

Evaluation (the learning curve; the gates are scored afterwards with score.py): at the start, every
``--eval-every-updates`` (20) updates, and at the end, the current networks' MEAN actions play
``--eval-games`` (256) games against the same Strike mix, each slot's first game counted (core/play.py
``play_match``, core/metrics.py ``summarise``: the one metrics module). The evaluation games are the same every
time (their generator is reseeded with seed + 1000). Physics: the evaluation game flies on the first
``--eval-games`` slots of the training world (``WorldSlice``); the whole world's body state is saved before and
written back after, so training continues exactly where it stopped.

TensorBoard (``[tensorboard]`` of configs/s2b.toml; no cloud logging): skrl's own curves and, at every
evaluation, the ``game/`` scalars (``game/hold_rate`` and ``game/hold_rate/<Strike behaviour>``,
``game/timeout_win_share``, ``game/closest_cross_3d_min_m``, ``game/closest_cross_3d_p05_m``,
``game/filter_share``, ``game/game_steps_per_s``) plus the settings as text, all in ``runs/<name>/``
(step = skrl timestep; game-steps = timestep x num_games). Watch: ``tensorboard --logdir runs/`` on the host.

Writes ``runs/<name>/``: interface.toml (first, before training), agent.pt (at every evaluation and at the end),
curve.json (one entry per evaluation), train_result.json (at the end), the event files. Refuses an existing run
folder. Exit 0 = finished (stopped by the budget or the cap), 1 = crash, 2 = bad arguments or refused, 3 = ABORTED.

Phase 5 pilots (``--game nus_hangar``, Tasks P-T3/P-T4; plan docs/plans/2026-11-18-nus-phase5-retraining.md section 7; not gated,
INFO records). ``--settings pilot_p1 | pilot_p2 | pilot_p3_guard | pilot_p3_strike`` of ``--pilot-config`` (configs/nus_phase5.toml),
and only those tables, run on the NUS hangar game of Phase 4 row 5 (``nus/pilot.py``: local files through the ``nus/`` loaders, fresh
training starts per game, evaluations on the first games of the Phase 4 paired starts with mean actions). The table names the trained team
(``train_team``) and the opponent mix; ``--warm-start <run folder>`` loads a run of the same team and sizes; ``--no-eval-at-start`` skips
the first evaluation. The cap is a HARD wall-clock cap including the evaluations (the table's ``gpu_cap_hours``, never above what the
pilots' ledger ``[pilots] gpu_hours_log`` leaves of ``[pilots] total_gpu_hours``): one evaluation is estimated from a warm-up before
anything is written, a run whose cap cannot hold it is refused, and training stops at the first update after which the evaluations still
due would not fit; there is no --accept-long. Evaluations: at the start and half-way on ``eval_games_early`` games, at the end on
``eval_games``; ``agent_best.pt`` keeps the best one. Videos (one per evaluation, two for the final and the best) are rendered after the
GPU work into ``runs/<name>/videos/``; one line goes into the pilots' ledger. ``PYTORCH_CUDA_ALLOC_CONF`` is set to ``[pilots] alloc_conf``
(the shell's value is replaced and recorded). The default ``--game s2`` path is bit-identical to the code before these hooks
(tests/test_train_standin.py).

Non-finite guard (Task 9 fix round 1): after every update (one host read there) the run checks the rollout's
actions (the game's ``info["nonfinite_actions"]``), the last losses skrl tracked and every network weight and scaler
statistic; every evaluation checks its own actions. On the first NaN or inf the run is ABORTED: it stops, keeps the
last good ``agent.pt`` (from the last evaluation), writes ``train_result.json`` with ``status = "ABORTED"`` and the
reason, adds an "ABORTED" settings text to TensorBoard and exits 3. ``game/timeout_win_share`` equals
``game/hold_rate`` while walls keep the drones in (``keep_in``, the committed game): a Strike drone can then only
leave the game through a scheduled drop-out (none in the committed file), so the Guard team holds only by time-out.
"""
from __future__ import annotations

import argparse
import copy
import dataclasses
import datetime
import hashlib
import json
import math
import os
import pathlib
import subprocess
import sys
import time
import tomllib
import traceback
from typing import Any, Callable

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

CONFIGS = ROOT / "configs"
LOCAL_DIR = CONFIGS / "local"        # never read: every stand-in runs on the committed neutral values (--no-local)
MOTIONS = ("pure", "starling", "physics")
ACTION_AXES = {"vx": 0, "vy": 1, "vz": 2, "yaw": 3}   # order of the 4 action numbers
PRESET_OF = {"pure": "pure", "starling": "starling", "physics": "physics"}   # score.py's preset names
OPPONENT_SEED_OFFSET = 202          # the opponent team's seed = the run (or evaluation) seed + this (unchanged since S2b)
EVAL_SEED_OFFSET = 1000              # = [standin_gates] eval_seed_offset (the learning curve uses the same rule)
FIRST_LINE = "Stand-in (pipe test), not a strategy of record. Observed in the training simulator."
# --settings: which settings table the run uses, and where it lives. "standin" = configs/s2.toml [standin] as committed
# (pinned, the default); "standin_v2" = configs/s2b.toml [standin_v2], approved by the owner on 17 Nov 2026 for the
# S2b Task 9 runs of record (init log std, per-motion frozen log std axes, skrl's defaults written down).
SETTINGS_TABLES = {"standin": ("--config", "committed S2 table, pinned (plan D14)"),
                   "standin_v2": ("--s2b-config", "approved by the owner 17 Nov 2026 for the S2b Task 9 runs of record")}
# Phase 5 pilots (plan docs/plans/2026-11-18-nus-phase5-retraining.md section 7, Task P-T3): tables of configs/nus_phase5.toml,
# run on the NUS hangar game only (--game nus_hangar; nus/pilot.py). Not gated: INFO records.
PILOT_TABLES = ("pilot_p1", "pilot_p2", "pilot_p3_guard", "pilot_p3_strike", "pilot_p1b")
SETTINGS_TABLES.update({t: ("--pilot-config", "Phase 5 pilot table, PROPOSED (not gated, INFO record)") for t in PILOT_TABLES})
GAMES = ("s2", "nus_hangar")
SKRL_TABLE_KEYS = ("discount_factor", "gae_lambda", "entropy_loss_scale", "value_loss_scale", "ratio_clip",
                   "value_clip", "grad_norm_clip")       # skrl settings a table may write down; passed to IPPO_CFG


SKRL_MAJOR = 2                       # skrl 2.x API (IPPO_CFG, "observations" inputs); the container has 1.4.3


# --------------------------------------------------------------------------------------------- small helpers
def skrl_version_problem() -> str | None:
    """None if the installed skrl has the 2.x API this script uses, else a one-line reason. Reads the package
    metadata only (imports neither skrl nor torch, so it can run before Isaac Sim starts)."""
    from importlib.metadata import PackageNotFoundError, version
    try:
        v = version("skrl")
    except PackageNotFoundError:
        return "skrl is not installed"
    if int(v.split(".")[0]) != SKRL_MAJOR:
        return (f"skrl {v} found; this trainer is written for skrl {SKRL_MAJOR}.x (host conda env_isaaclab has "
                f"2.1.0; the container image has 1.4.3)")
    return None


def git_commit() -> str:
    c = os.environ.get("SVG_COMMIT")        # docker/run.sh hands the host commit to the container
    if c:
        return c
    try:
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, timeout=20).stdout.strip() or "unknown"
        # "-dirty" when tracked files under svg_training/ have uncommitted changes (as docker/run.sh marks it)
        st = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no", "--", "."],
                            capture_output=True, text=True, timeout=20).stdout
        return head + ("-dirty" if st.strip() else "")
    except Exception:
        return "unknown"


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def table_text(text: str, name: str) -> str:
    """The text of TOML table [name]: its header line up to (not including) the next line starting with '['
    (the same rule as tests/test_s2b_config.py, so the sha256 here matches the pinned one)."""
    out, on = [], False
    for line in text.splitlines(keepends=True):
        if line.startswith("["):
            on = line.startswith(f"[{name}]")
        if on:
            out.append(line)
    return "".join(out)


def _toml_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int,)) and not isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        return repr(v) if math.isfinite(v) else ("nan" if math.isnan(v) else ("inf" if v > 0 else "-inf"))
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k} = {_toml_value(x)}" for k, x in v.items()) + " }"
    raise TypeError(f"cannot write {type(v).__name__} to TOML")


def to_toml(data: dict, header: str = "") -> str:
    """A flat writer: top-level scalars first, then one [table] per dict value (no nested tables inside)."""
    lines = [f"# {h}" for h in header.splitlines()] if header else []
    for k, v in data.items():
        if not isinstance(v, dict):
            lines.append(f"{k} = {_toml_value(v)}")
    for k, v in data.items():
        if isinstance(v, dict):
            lines += ["", f"[{k}]"] + [f"{k2} = {_toml_value(v2)}" for k2, v2 in v.items()]
    return "\n".join(lines) + "\n"


def effective_agent_cfg(cfg: Any, agent: str) -> dict:
    """The scalar settings of one agent from an EXPANDED skrl multi-agent config (skrl expands per agent name)."""
    out: dict = {}
    for f in dataclasses.fields(cfg):
        v = getattr(cfg, f.name)
        v = v.get(agent) if isinstance(v, dict) and agent in v else v
        if isinstance(v, (bool, int, float, str)) or v is None:
            out[f.name] = v
        elif isinstance(v, (tuple, list)) and all(isinstance(x, (int, float)) for x in v):
            out[f.name] = list(v)
    return out


def skrl_table_mismatch(effective: dict, table: dict, table_name: str) -> str | None:
    """None when every skrl setting the table writes down (SKRL_TABLE_KEYS) is skrl's effective value; else why not."""
    for k in SKRL_TABLE_KEYS:
        if k not in table:
            continue
        got = effective.get(k)
        if not isinstance(got, (int, float)) or isinstance(got, bool) or not math.isclose(float(got), float(table[k])):
            return f"skrl's effective {k} = {got!r} differs from [{table_name}] {k} = {table[k]}"
    return None


def mix_slices(mix: dict[str, float], n: int) -> list[tuple[str, slice]]:
    """{behaviour: share} (shares summing to 1, in file order) -> contiguous game slices of n games."""
    total = sum(mix.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"opponent_mix shares must sum to 1, got {total}")
    out, start, acc = [], 0, 0.0
    names = list(mix)
    for i, b in enumerate(names):
        acc += mix[b]
        stop = n if i == len(names) - 1 else round(acc * n)
        if stop <= start:
            raise ValueError(f"opponent_mix gives {b!r} no games out of {n}")
        out.append((b, slice(start, stop)))
        start = stop
    return out


# --------------------------------------------------------------------------------------------- the world slice
class WorldSlice:
    """The first ``num_games`` games of a bigger ``RigidBodyWorld`` (models/rigid_body.py protocol), so the
    evaluation game can fly in the training world (Isaac Lab builds one scene per process).

    Writes are padded to the full world (mask False outside the slice); ``step`` steps the WHOLE world. So the caller
    saves the world with ``snapshot`` before using the slice and writes it back after with ``restore``: the training
    bodies then continue exactly from where they were (the training drone sets its own wrench again before its next
    physics step). ``snapshot`` also parks the games outside the slice level and at rest, and the slice holds them
    there with a hover wrench (thrust = weight along body up, no torque), so they do not fall for the length of an
    evaluation (up to 60 s) while the slice flies."""

    def __init__(self, base, num_games: int) -> None:
        if num_games > base.num_games:
            raise ValueError(f"a slice of {num_games} games does not fit a world of {base.num_games}")
        self.base, self.num_games, self.drones = base, num_games, base.drones
        self.dt_s, self.label, self.device = base.dt_s, base.label, base.device

    def _pad(self, x):
        import torch
        rest = self.base.num_games - self.num_games
        return torch.cat((x, x.new_zeros(rest, *x.shape[1:])), dim=0) if rest else x

    def reset(self, mask, pos_m, quat_wxyz) -> None:
        q = self._pad(quat_wxyz)
        q[self.num_games:, :, 0] = 1.0                     # a valid unit quaternion where nothing is written
        self.base.reset(self._pad(mask), self._pad(pos_m), q)

    def write_state(self, mask, pos_m, quat_wxyz, lin_vel_mps, ang_vel_b_rad_s) -> None:
        q = self._pad(quat_wxyz)
        q[self.num_games:, :, 0] = 1.0
        self.base.write_state(self._pad(mask), self._pad(pos_m), q, self._pad(lin_vel_mps),
                              self._pad(ang_vel_b_rad_s))

    def apply_wrench_b(self, force_b, torque_b) -> None:
        f = self._pad(force_b)
        if self.base.num_games > self.num_games:
            from svg_training.models.physics_params import G_MPS2
            f[self.num_games:, :, 2] = self.base.a.mass_kg * G_MPS2       # hover: the parked games stay put
        self.base.apply_wrench_b(f, self._pad(torque_b))

    def step(self) -> None:
        self.base.step()

    def state(self):
        return tuple(t[:self.num_games] for t in self.base.state())

    def snapshot(self):
        """The whole world's body state (pos, quat, lin vel, body rates), to hand to ``restore``. Then parks the
        games outside the slice level and at rest where they are (one batched write)."""
        import torch
        snap = tuple(t.clone() for t in self.base.state())
        if self.base.num_games > self.num_games:
            pos, quat, lin, ang = snap
            out = torch.zeros(self.base.num_games, self.base.drones, dtype=torch.bool, device=pos.device)
            out[self.num_games:] = True
            level = torch.zeros_like(quat)
            level[..., 0] = 1.0
            self.base.write_state(out, pos, level, torch.zeros_like(lin), torch.zeros_like(ang))
        return snap

    def restore(self, snap) -> None:
        """Write the saved body state of every drone back (one batched write)."""
        import torch
        everything = torch.ones(self.base.num_games, self.base.drones, dtype=torch.bool, device=snap[0].device)
        self.base.write_state(everything, *snap)


# --------------------------------------------------------------------------------------------- the gate rule
def standin_verdict(tables: list[dict], gates: dict, trained_label: str = "trained", strict: bool = False) -> dict:
    """The [standin_gates] rule over score.py outputs (one table per training seed).

    tables: [{"seed": training seed, "preset": the preset the stand-in trained on ("pure", "starling", "physics"),
    "rows": scores.json rows}] where the rows hold the trained Guard (its spec is a run folder, i.e. any Guard name
    that is not a scripted one) and ``random``, both against each behaviour of gates["behaviours"], at 2v1, per band.
    Only rows of that preset count (a table may also hold other presets, scored as information). Counts are summed
    over the bands (3,000 games per condition at 1,000 per band), then Wilson 95 % (core/metrics.wilson_interval).
    PASS for one (seed, behaviour) when trained - random >= min_hold_rate_gain AND (if intervals_disjoint) trained
    lower bound > random upper bound. Verdict PASS when every behaviour of at least ``seeds_required`` seeds passes
    and no seed fails; else FAIL. strict: raise ValueError unless every condition has 3 bands of exactly
    ``eval_games_per_band`` games (runs of record)."""
    from svg_training.core.metrics import wilson_interval
    from svg_training.opponents.scripted import REGISTRY

    cells = []
    for t in tables:
        rows = [r for r in t["rows"] if r.get("size", "2v1") == "2v1" and r.get("preset") == t["preset"]]
        if not rows:
            raise ValueError(f"seed {t['seed']}: no 2v1 rows of preset {t['preset']!r} in the table")
        trained_names = {r["guard"] for r in rows if r["guard"] not in REGISTRY}
        if len(trained_names) != 1:
            raise ValueError(f"seed {t['seed']}: expected exactly one trained Guard in the table, got "
                             f"{sorted(trained_names)}")
        trained = next(iter(trained_names))
        for b in gates["behaviours"]:
            def agg(guard: str) -> dict:
                sel = [r for r in rows if r["guard"] == guard and r["strike"] == b]
                n = sum(int(r["games"]) for r in sel)
                k = sum(int(r["guard_wins"]) for r in sel)
                lo, hi = wilson_interval(k, n)
                return {"games": n, "guard_wins": k, "hold_rate": k / n if n else float("nan"), "ci_low": lo,
                        "ci_high": hi, "bands": len(sel)}
            tr, rd = agg(trained), agg("random")
            if strict:
                for who, x in (("trained", tr), ("random", rd)):
                    if x["bands"] != 3 or x["games"] != 3 * int(gates["eval_games_per_band"]):
                        raise ValueError(f"seed {t['seed']} {b} {who}: {x['bands']} bands, {x['games']} games; the "
                                         f"gate needs 3 bands of {gates['eval_games_per_band']}")
            gain = tr["hold_rate"] - rd["hold_rate"]
            ok_gain = bool(gain >= gates["min_hold_rate_gain"])
            ok_disjoint = bool(tr["ci_low"] > rd["ci_high"]) if gates.get("intervals_disjoint", True) else True
            enough = tr["games"] > 0 and rd["games"] > 0
            cells.append({"seed": t["seed"], "behaviour": b, "trained_guard": trained, trained_label: tr,
                          "random": rd, "gain": gain, "gain_ok": ok_gain, "intervals_disjoint": ok_disjoint,
                          "pass": bool(enough and ok_gain and ok_disjoint)})
    seeds = sorted({c["seed"] for c in cells})
    passed = [s for s in seeds if all(c["pass"] for c in cells if c["seed"] == s)]
    verdict = "PASS" if (len(passed) == len(seeds) and len(seeds) >= int(gates["seeds_required"])) else "FAIL"
    return {"verdict": verdict, "seeds": seeds, "seeds_passed": passed, "cells": cells, "gates": dict(gates)}


def verdict_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="train_standin.py verdict",
                                 description="The [standin_gates] verdict over the seeds' score.py outputs.")
    ap.add_argument("--gates", required=True, help="runs/<group>/gates.toml (a copy of [standin_gates])")
    ap.add_argument("--scores", required=True, help="comma list of score.py --out folders, one per seed")
    ap.add_argument("--out", required=True, help="folder for verdict.json")
    ap.add_argument("--allow-short", action="store_true",
                    help="sanity checks only: accept fewer games than [standin_gates] eval_games_per_band")
    a = ap.parse_args(argv)
    from svg_training.opponents.learned import is_run_folder, read_interface
    from svg_training.opponents.scripted import REGISTRY

    g = tomllib.loads(pathlib.Path(a.gates).read_text())
    gates = g.get("standin_gates", g)
    tables = []
    for d in [x.strip() for x in a.scores.split(",") if x.strip()]:
        sj = json.loads((pathlib.Path(d) / "scores.json").read_text())
        if sj["meta"].get("local_file"):
            print(f"refusing: {d} was scored with the local partner file; the stand-in uses --no-local",
                  file=sys.stderr)
            return 2
        seed = int(sj["meta"]["seed"]) - int(gates["eval_seed_offset"])
        runs = [x for x in sj["meta"].get("guards", []) if x not in REGISTRY]
        if len(runs) != 1 or not is_run_folder(runs[0]):
            print(f"refusing: {d}: expected one stand-in run folder among the Guard specs, got {runs}",
                  file=sys.stderr)
            return 2
        meta = read_interface(runs[0])
        if int(meta["seed"]) != seed:
            print(f"refusing: {d} was scored with seed {sj['meta']['seed']}; the run {runs[0]} trained with seed "
                  f"{meta['seed']}, so its evaluation seed is {int(meta['seed']) + int(gates['eval_seed_offset'])}",
                  file=sys.stderr)
            return 2
        tables.append({"seed": seed, "preset": meta["preset"], "rows": sj["rows"]})
    try:
        res = standin_verdict(tables, gates, strict=not a.allow_short)
    except ValueError as ex:
        print(f"refusing: {ex}", file=sys.stderr)
        return 2
    res["allow_short"] = bool(a.allow_short)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "verdict.json").write_text(json.dumps(res, indent=1))
    for c in res["cells"]:
        print(f"seed {c['seed']} {c['behaviour']}: trained {c['trained']['hold_rate']:.3f} "
              f"[{c['trained']['ci_low']:.3f}, {c['trained']['ci_high']:.3f}] vs random {c['random']['hold_rate']:.3f} "
              f"[{c['random']['ci_low']:.3f}, {c['random']['ci_high']:.3f}] gain {c['gain']:+.3f} -> "
              f"{'PASS' if c['pass'] else 'FAIL'}")
    print(f"verdict {res['verdict']} ({len(res['seeds_passed'])}/{len(res['seeds'])} seeds pass) -> "
          f"{out / 'verdict.json'}")
    return 0


# --------------------------------------------------------------------------------------------- arguments
# --------------------------------------------------------------------------------------------- the games
def build_games(args: argparse.Namespace, st: dict, motion: str, n: int, eval_sizes: list[int], guards: int, strikes: int, device: str,
                seed: int, eval_seed: int, world_factory: Callable | None, train_team: str = "guard", pilot_world: Any = None):
    """The training game, its opponent team, and one evaluation game per size with its opponent team and mix slices.

    ``--game s2``: the S2 game on the committed neutral values (``use_local=False``), the Strike team of ``[standin] opponent_mix`` (the code
    of S2b Task 9, moved here unchanged; the evaluation game is built first because building a game resets its world). ``--game nus_hangar``:
    Phase 4 row 5 through ``nus/pilot.py`` (fresh training starts; evaluation on the Phase 4 paired starts), the opponent team of the
    pilot table. Returns a namespace: cfg, game, train_opp, evals {size: (game, opponent strategy, slices)}, mix, prov_name,
    prov_sha256, local_file, physics_meta, eval_world."""
    import types

    from skrl.utils import set_seed

    from svg_training.core.game import SvgGame
    from svg_training.core.game_config import load_game_cfg
    from svg_training.core.starling_layer import resolve_params
    from svg_training.core.strategy import SplitStrategy
    from svg_training.opponents.scripted import make_strategy
    mix = {k: float(v) for k, v in st["opponent_mix"].items()}
    opp_team = "strike" if train_team == "guard" else "guard"
    if args.game == "nus_hangar":
        from svg_training.nus import pilot as nus_pilot
        cfg = pilot_world.cfg
        set_seed(seed)
        game, evals_g = nus_pilot.pilot_games(pilot_world, n, eval_sizes, device, seed, eval_seed)

        def opp_mix(num: int, seed0: int):
            sl = mix_slices(mix, num)
            return nus_pilot.mix_strategy(sl, opp_team, cfg, device, seed0), sl
        train_opp, _ = opp_mix(n, seed + OPPONENT_SEED_OFFSET)
        evals = {size: (g, *opp_mix(size, eval_seed + OPPONENT_SEED_OFFSET)) for size, g in evals_g.items()}
        local = "sha256 " + ", ".join(f"{k}={v}" for k, v in pilot_world.local_sha256.items())
        return types.SimpleNamespace(cfg=cfg, game=game, train_opp=train_opp, evals=evals, mix=mix, prov_name=pilot_world.game_file.name,
                                     prov_sha256=pilot_world.game_sha256, local_file=local, physics_meta={}, eval_world=None)
    e = eval_sizes[0]
    cfg, prov = load_game_cfg(args.game_config, local_dir=LOCAL_DIR, use_local=False)
    cfg = cfg.replace(**{"rewards.shaping_weight": float(st["shaping_weight"])})
    if motion in ("starling", "physics"):
        cfg = cfg.replace(**{"starling.enabled": True,
                             "starling.backend": "physics" if motion == "physics" else "fitted"})
    set_seed(seed)
    physics_meta: dict = {}
    world = eval_world = None
    if motion == "physics":
        from svg_training.core.physics_layer import load_game_physics_params
        from svg_training.models.physics_params import yaw_gains_text
        params = load_game_physics_params(cfg)
        world = world_factory(n, guards + strikes, params, device)
        eval_world = WorldSlice(world, e)
        pp = resolve_params(cfg.starling.physics_params)
        physics_meta = {"physics_params": cfg.starling.physics_params, "physics_params_sha256": sha256_file(pp),
                        "yaw_rate_gains": yaw_gains_text(params), "physics_dt_s": params.physics_dt_s,
                        "motor_lag": params.motor_lag, "rotor_geometry": params.rotor_geometry,
                        "world": world.label}
    # the evaluation game first: building a game resets its world, and the training game's reset must come last
    eval_game = SvgGame(cfg, e, guards, strikes, device=device, seed=eval_seed, world=eval_world)
    game = SvgGame(cfg, n, guards, strikes, device=device, seed=seed, world=world)

    def strike_mix(num: int, seed0: int) -> tuple[SplitStrategy, list[tuple[str, slice]]]:
        sl = mix_slices(mix, num)
        parts = [(make_strategy(b, "strike", cfg, s.stop - s.start, device, seed0 + j), s)
                 for j, (b, s) in enumerate(sl)]
        return SplitStrategy("strike", parts), sl

    train_strike, _ = strike_mix(n, seed + OPPONENT_SEED_OFFSET)
    eval_strike, eval_slices = strike_mix(e, eval_seed + OPPONENT_SEED_OFFSET)
    return types.SimpleNamespace(cfg=cfg, game=game, train_opp=train_strike, evals={e: (eval_game, eval_strike, eval_slices)}, mix=mix,
                                 prov_name=pathlib.Path(prov.game_file).name, prov_sha256=prov.game_sha256, local_file="none",
                                 physics_meta=physics_meta, eval_world=eval_world)


def estimate_eval_s(built: Any, size: int, train_team: str, ticks: int, max_steps: int | None, device: str) -> float:
    """Seconds for one evaluation on the ``size``-game evaluation game: ``ticks`` ticks timed (after one untimed tick) with a zero-action
    trained team and the evaluation opponents, scaled to the evaluation length. The evaluation resets the game and both teams itself."""
    import torch

    from svg_training.opponents.scripted import make_strategy
    game, opp, _ = built.evals[size]
    zero = make_strategy("zero", train_team, built.cfg, size, device, 0)
    guard, strike = (zero, opp) if train_team == "guard" else (opp, zero)
    every = torch.ones(size, dtype=torch.bool, device=device)
    obs = game.reset()
    guard.reset(every)
    strike.reset(every)
    sync = torch.cuda.synchronize if torch.device(device).type == "cuda" else (lambda: None)
    t0 = 0.0
    for k in range(ticks + 1):
        if k == 1:
            sync()
            t0 = time.perf_counter()
        obs = game.step({"guard": guard.act(obs["guard"]), "strike": strike.act(obs["strike"])}).obs
    sync()
    return (time.perf_counter() - t0) / max(ticks, 1) * int(max_steps or game.ticks)


# --smoke (docs panel C3, owner 18 Nov 2026): the pipe test in seconds on a CPU (3-5 s measured 18 Nov on the 5090's CPU). It fills these
# settings unless the command line gives them; the run is a smoke run (train_result.json "smoke": true), never a run of record.
SMOKE = {"timesteps_override": 256, "num_games_override": 64, "eval_games": 64, "eval_max_steps": 200, "eval_every_updates": 4}
_PARSER_DEFAULTS = {"timesteps_override": None, "num_games_override": None, "eval_games": None, "eval_max_steps": None,
                    "eval_every_updates": 20}


def apply_smoke(args: argparse.Namespace) -> argparse.Namespace:
    """With --smoke: every SMOKE setting still at its parser default takes the smoke value. Without it: unchanged."""
    if getattr(args, "smoke", False):
        for key, value in SMOKE.items():
            if getattr(args, key) == _PARSER_DEFAULTS[key]:
                setattr(args, key, value)
    return args


def make_parser(isaac: bool = False) -> argparse.ArgumentParser:
    """isaac=True leaves --device to Isaac Lab's launcher arguments (it adds its own)."""
    ap = argparse.ArgumentParser(description="Stand-in trainer (pipe test): skrl IPPO, 2 Guard v 1 Strike.")
    ap.add_argument("--config", default=str(CONFIGS / "s2.toml"), help="settings file holding [standin]")
    ap.add_argument("--s2b-config", default=str(CONFIGS / "s2b.toml"),
                    help="file holding [standin_s2b] (caps) and [tensorboard]")
    ap.add_argument("--game-config", default=str(CONFIGS / "s2_game.toml"))
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--name", required=True, help="run folder name under --runs-dir")
    ap.add_argument("--motion", choices=MOTIONS, default=None,
                    help="pure (default for --game s2), starling (the only motion of --game nus_hangar), physics")
    ap.add_argument("--timesteps-override", type=int, help="skrl timesteps (tests and smoke runs only)")
    ap.add_argument("--num-games-override", type=int, help="games per batch (tests and smoke runs only)")
    ap.add_argument("--cap-min-override", type=float, help="wall-clock cap in minutes (tests only)")
    ap.add_argument("--smoke", action="store_true",
                    help="smoke run: the pipe test in seconds on a CPU (" + ", ".join(f"--{k.replace('_', '-')} {v}" for k, v in SMOKE.items())
                         + " unless given); never a run of record")
    ap.add_argument("--eval-games", type=int, default=None,
                    help="evaluation games (default 256 on --game s2; the pilot table's eval_games on --game nus_hangar)")
    ap.add_argument("--eval-every-updates", type=int, default=20)
    ap.add_argument("--eval-max-steps", type=int, help="steps per evaluation (default: the game length; tests)")
    ap.add_argument("--runs-dir", default=str(ROOT / "runs"))
    ap.add_argument("--settings", choices=list(SETTINGS_TABLES), default="standin",
                    help="settings table: standin = configs/s2.toml [standin] (default); standin_v2 = configs/s2b.toml "
                         "[standin_v2] (owner-approved 17 Nov 2026); not combinable with the --diag-* flags")
    ap.add_argument("--game", choices=GAMES, default="s2",
                    help="s2 = the S2 game on committed neutral values (default); nus_hangar = the NUS hangar game of Phase 4 row 5 "
                         "with a pilot table of --pilot-config (Phase 5 pilots; local files through the nus/ loaders)")
    ap.add_argument("--pilot-config", default=str(CONFIGS / "nus_phase5.toml"), help="file holding the pilot tables and [pilots]")
    ap.add_argument("--warm-start", help="run folder whose agent.pt starts the networks (same team, team sizes and hidden layers)")
    ap.add_argument("--no-eval-at-start", action="store_true", help="skip the evaluation at timestep 0")
    # A clean early stop for runs on a shared machine with a deadline: checked at every update boundary, like the cap.
    # The run then does its final evaluation (agent.pt = the networks at the stop), writes status ABORTED with the
    # reason in train_result.json and exits 4. Neither changes training; both are recorded.
    ap.add_argument("--stop-at", help="local time YYYY-MM-DDTHH:MM[:SS]: stop at the first update boundary after it")
    ap.add_argument("--stop-file", help="path: stop at the first update boundary at which this file exists")
    # Diagnosis only (S2b Task 9 Step B): change ONE setting the committed [standin] does not hold. A run using any of
    # these is never a run of record; interface.toml gets a [diagnostic] table and TensorBoard a "diagnostic" text.
    ap.add_argument("--diag-init-log-std", type=float, help="initial log std of every policy (skrl default 0)")
    ap.add_argument("--diag-discount", type=float, help="IPPO discount factor (skrl default 0.99)")
    ap.add_argument("--diag-entropy-scale", type=float, help="IPPO entropy loss scale (skrl default 0)")
    ap.add_argument("--diag-freeze-log-std-axes",
                    help="comma list of action axes (vx, vy, vz, yaw) whose log std stays at its initial value")
    if not isaac:
        ap.add_argument("--device", default="auto",
                        help="auto (default): cuda if PyTorch sees a GPU, else cpu with a note; or cpu, cuda, cuda:N")
    return ap


# --------------------------------------------------------------------------------------------- the run
def run(args: argparse.Namespace, world_factory: Callable | None = None) -> int:
    """Train one seed. world_factory(num_games, drones, params, device) -> RigidBodyWorld is required for
    --motion physics (IsaacWorld from __main__; a TorchRigidBodyWorld only from tests)."""
    problem = skrl_version_problem()
    if problem:
        print(f"refusing: {problem}", file=sys.stderr)
        return 2
    apply_smoke(args)
    import torch
    from skrl.memories.torch import RandomMemory
    from skrl.multi_agents.torch.ippo import IPPO, IPPO_CFG
    from skrl.resources.preprocessors.torch import RunningStandardScaler
    from skrl.trainers.torch import SequentialTrainer
    from skrl.utils import set_seed
    from torch.utils.tensorboard import SummaryWriter

    from svg_training.core.game import SvgGame
    from svg_training.core.game_config import load_game_cfg
    from svg_training.core.metrics import summarise
    from svg_training.core.observations import INTERFACE_VERSION, OBS_DIM, ObsView
    from svg_training.core.play import play_match
    from svg_training.core.rewards import GUARD_WIN, RUNNING
    from svg_training.core.starling_layer import resolve_params
    from svg_training.core.strategy import SplitStrategy
    from svg_training.envs.skrl_adapter import SvgSkrlEnv, skrl_kwargs_defaults
    from svg_training.opponents.learned import AGENT_FILE, INTERFACE_FILE, OBS_SPACE, make_models
    from svg_training.opponents.scripted import make_strategy

    from svg_training.devices import resolve_device

    t_start = time.time()
    device = resolve_device(str(args.device))     # auto -> cuda or cpu (with a note); explicit devices unchanged
    args.device = device
    if device.startswith("cpu"):
        # Small CPU batches (tests, smoke runs): one thread. Measured 16 Nov 2026 on this laptop, 32 games 2v1:
        # 6 s with one thread against 83 s with torch's default 24 (thread start-up on tiny tensors).
        torch.set_num_threads(1)
    table_name = str(args.settings)
    nus = args.game == "nus_hangar"
    if nus != (table_name in PILOT_TABLES):
        print(f"refusing: --game nus_hangar takes a pilot table ({', '.join(PILOT_TABLES)}) and a pilot table needs --game "
              f"nus_hangar; got --game {args.game} --settings {table_name}", file=sys.stderr)
        return 2
    if nus:
        from svg_training.nus import pilot as nus_pilot
        pilots = nus_pilot.load_pilots(args.pilot_config)
        # P0's memory note: with the 5090 shell's PYTORCH_CUDA_ALLOC_CONF (expandable_segments:True,max_split_size_mb:128, ~/.bashrc) the
        # caching allocator reserved most of the card; expandable segments alone keep the reserve near what is allocated (P0 memory
        # smoke, 18 Nov 2026). The pilot's value replaces the shell's, before CUDA starts; the shell's value is recorded.
        alloc_before = os.environ.get("PYTORCH_CUDA_ALLOC_CONF", "none")
        os.environ["PYTORCH_CUDA_ALLOC_CONF"] = str(pilots["alloc_conf"])
    settings_path = pathlib.Path({"--config": args.config, "--s2b-config": args.s2b_config,
                                  "--pilot-config": args.pilot_config}[SETTINGS_TABLES[table_name][0]])
    settings_text = settings_path.read_text()
    st = tomllib.loads(settings_text)[table_name]
    standin_text = pathlib.Path(args.config).read_text()          # the committed [standin], hashed in every run
    diag_flags = [f for f in ("diag_init_log_std", "diag_discount", "diag_entropy_scale", "diag_freeze_log_std_axes")
                  if getattr(args, f) is not None]
    if table_name != "standin" and diag_flags:
        print(f"refusing: --settings {table_name} is a run-of-record table; the --diag-* flags "
              f"({', '.join(diag_flags)}) belong to diagnosis runs on the default table", file=sys.stderr)
        return 2
    stop_at = None
    if args.stop_at:
        try:
            stop_at = datetime.datetime.fromisoformat(args.stop_at).timestamp()
        except ValueError:
            print(f"refusing: --stop-at {args.stop_at!r} is not YYYY-MM-DDTHH:MM[:SS]", file=sys.stderr)
            return 2
    s2b = tomllib.loads(pathlib.Path(args.s2b_config).read_text())
    caps, tb_cfg = s2b["standin_s2b"], s2b["tensorboard"]
    motion = args.motion or ("starling" if nus else "pure")
    if nus and motion != "starling":
        print(f"refusing: --game nus_hangar plays Phase 4 row 5 (the fitted Starling layer): --motion starling, not {motion!r}",
              file=sys.stderr)
        return 2
    if motion not in caps["motions"]:
        print(f"refusing: motion {motion!r} not in [standin_s2b] motions {caps['motions']}", file=sys.stderr)
        return 2
    if st["preset"] != ("nus_hangar" if nus else "pure") or st["algorithm"] != "IPPO":
        print(f"refusing: [{table_name}] preset must be {'nus_hangar' if nus else 'pure'!r} and algorithm 'IPPO' (as committed)",
              file=sys.stderr)
        return 2
    frozen_table = st.get("frozen_log_std_axes")
    if frozen_table is not None and motion not in frozen_table:
        print(f"refusing: [{table_name}] frozen_log_std_axes names no axes for motion {motion!r}", file=sys.stderr)
        return 2
    if tb_cfg.get("cloud_logging", False):
        print("refusing: [tensorboard] cloud_logging must be false", file=sys.stderr)
        return 2
    if motion == "physics" and world_factory is None:
        print("refusing: --motion physics needs a world (run as __main__ with --headless: IsaacWorld)",
              file=sys.stderr)
        return 2
    run_dir = pathlib.Path(args.runs_dir) / args.name
    if run_dir.exists() and any(run_dir.iterdir()):
        print(f"refusing: {run_dir} exists and is not empty (a run is never overwritten)", file=sys.stderr)
        return 2

    n = int(args.num_games_override or st["num_games"])
    train_team = str(st.get("train_team", "guard"))
    opp_team = "strike" if train_team == "guard" else "guard"
    warm_meta = None
    if nus:
        from svg_training.nus import hangar as nus_hangar
        if int(args.seed) == int(nus_hangar.load_phase4()["ladder"]["seed"]):
            print("refusing: the seed is the Phase 4 starts seed; training never draws the scoring starts", file=sys.stderr)
            return 2
        pw = nus_pilot.pilot_world(float(st["shaping_weight"]))           # the local files, through the nus/ loaders
        guards, strikes = pw.guards, pw.strikes
        tps = nus_pilot.decision_ticks(st.get("decision_ticks"), pw)     # game ticks per learner decision (P1b: the deploy hold)
    else:
        tps = 1
        guards, strikes = int(st["guards"]), int(st["strikes"])
    if args.warm_start:
        warm_file = pathlib.Path(args.warm_start) / "interface.toml"
        warm_meta = tomllib.loads(warm_file.read_text()) if warm_file.is_file() else None
        if (warm_meta is None or warm_meta.get("team") != train_team or warm_meta.get("guards") != guards
                or warm_meta.get("strikes") != strikes or warm_meta.get("network", {}).get("hidden") != list(st["hidden"])):
            print(f"refusing: --warm-start {args.warm_start} is not a {train_team} run with {guards} v {strikes} drones and hidden "
                  f"{list(st['hidden'])}", file=sys.stderr)
            return 2
    e = int(args.eval_games if args.eval_games is not None else (st["eval_games"] if nus else 256))
    if e < 2 or (motion == "physics" and e > n):
        print(f"refusing: --eval-games {e} must be >= 2 and (physics) <= the {n} training games", file=sys.stderr)
        return 2
    budget_game_steps = int(st["game_steps_per_seed"])
    timesteps = int(args.timesteps_override or budget_game_steps // (n * tps))
    cap_min = float(args.cap_min_override if args.cap_min_override is not None else
                    (caps["wall_clock_cap_min_isaac"] if motion == "physics" else caps["wall_clock_cap_min_torch"]))
    if nus:   # a hard wall-clock cap INCLUDING the evaluations; never above the pilots' budget left in the ledger; never raised
        logged_h = nus_pilot.logged_hours(nus_pilot.GPU_HOURS_LOG)
        cap_s = nus_pilot.effective_cap_s(st["gpu_cap_hours"], pilots["total_gpu_hours"], logged_h)
        if args.cap_min_override is not None:
            cap_s = min(cap_s, float(args.cap_min_override) * 60.0)
        cap_min = cap_s / 60.0
        e_early = min(int(st["eval_games_early"]), e)
        eval_at_start = bool(st["eval_at_start"]) and not args.no_eval_at_start
        mid_planned = bool(st["mid_evaluation"])
    rollouts = int(st["rollouts"])
    seed = int(args.seed)
    eval_seed = seed + EVAL_SEED_OFFSET

    # ---- games (s2: committed neutral values only; nus_hangar: Phase 4 row 5 from the local files) ----
    eval_sizes = sorted({e} | ({e_early} if nus and (eval_at_start or mid_planned) else set())) if nus else [e]
    if nus:
        # one evaluation, estimated BEFORE anything is written: the final evaluation game's first ticks with a zero-action trained
        # team (the cost is the filter's, per tick); a pilot whose cap cannot hold one evaluation is refused (no --accept-long)
        try:
            built = build_games(args, st, motion, n, eval_sizes, guards, strikes, device, seed, eval_seed, world_factory,
                                train_team, pw)
        except ValueError as ex:
            print(f"refusing: {ex}", file=sys.stderr)
            return 2
        est_eval_s = estimate_eval_s(built, e, train_team, int(pilots["estimate_ticks"]), args.eval_max_steps, device)
        print(f"estimate: one evaluation about {est_eval_s:.0f} s; cap {cap_s:.0f} s (table {st['gpu_cap_hours']} h, pilots' ledger "
              f"{logged_h:.3f} of {pilots['total_gpu_hours']} h used)", flush=True)
        due = 1 + int(eval_at_start)          # the evaluations that run whatever happens: the start one (if any) and the final one
        if cap_s < est_eval_s * due:
            print(f"refusing: the cap left ({cap_s:.0f} s) cannot hold the {due} evaluation(s) that always run (about "
                  f"{est_eval_s * due:.0f} s)", file=sys.stderr)
            return 2
    else:
        built = build_games(args, st, motion, n, eval_sizes, guards, strikes, device, seed, eval_seed, world_factory, train_team)
    cfg, game, train_opp = built.cfg, built.game, built.train_opp
    eval_game, eval_strike, eval_slices = built.evals[e]
    physics_meta, eval_world, mix = built.physics_meta, built.eval_world, built.mix
    behaviours = list(mix)
    env = SvgSkrlEnv(game, train_teams=(train_team,), opponents={opp_team: train_opp})
    if tps > 1:          # P1b: one decision per tps ticks, the action held in between (nus/pilot.py DecisionHoldEnv)
        env = nus_pilot.DecisionHoldEnv(env, tps)
    names = env.possible_agents

    # ---- skrl IPPO ----
    models = make_models(names, list(st["hidden"]), device)
    diag = {k: v for k, v in (("init_log_std", args.diag_init_log_std), ("discount_factor", args.diag_discount),
                              ("entropy_loss_scale", args.diag_entropy_scale)) if v is not None}
    # The initial log std and the frozen axes come from the --diag-* flags (diagnosis, default table) or from the
    # settings table ([standin_v2]); the two are never combined (refused above). One code path applies them.
    init_log_std = diag.get("init_log_std", st.get("init_log_std"))
    if args.diag_freeze_log_std_axes:
        freeze_axes = [x.strip() for x in args.diag_freeze_log_std_axes.split(",") if x.strip()]
    else:
        freeze_axes = list(frozen_table[motion]) if frozen_table is not None else []
    if init_log_std is not None:
        with torch.no_grad():
            for a in names:
                models[a]["policy"].log_std.fill_(float(init_log_std))
    zero_mean = bool(nus and st.get("zero_mean_init", False))
    if zero_mean:        # P1b: the start policy is the standing-still Guard (mean action 0); the log std stays as set
        for a in names:
            nus_pilot.zero_mean_head(models[a]["policy"])
    if args.diag_freeze_log_std_axes or freeze_axes:
        # The log std is one Parameter [4] per policy, so requires_grad cannot be set per axis. A gradient hook zeroes the
        # frozen entries of its gradient on every backward pass, from the first update on. skrl's Adam (no weight
        # decay) then keeps both moment estimates of those entries at exactly 0, so its step m / (sqrt(v) + eps) is
        # exactly 0, and the global grad-norm clip only rescales (0 stays 0): the entries keep their initial value
        # bit for bit, also inside an update's epochs (a re-fill after each update would let them move in between).
        axes = freeze_axes
        bad = [x for x in axes if x not in ACTION_AXES]
        if bad or not axes:
            print(f"refusing: frozen log std axes (--diag-freeze-log-std-axes or [{table_name}]) come from "
                  f"{list(ACTION_AXES)}, got {axes}", file=sys.stderr)
            return 2
        keep = torch.ones(4, device=device)
        for x in axes:
            keep[ACTION_AXES[x]] = 0.0
        for a in names:
            models[a]["policy"].log_std.register_hook(lambda g, k=keep: g * k)
        if args.diag_freeze_log_std_axes:
            diag["freeze_log_std_axes"] = axes
    extra_cfg = {k: float(st[k]) for k in SKRL_TABLE_KEYS if k in st}           # written down in the table
    extra_cfg.update({k: v for k, v in diag.items() if k in ("discount_factor", "entropy_loss_scale")})
    memories = {a: RandomMemory(memory_size=rollouts, num_envs=n, device=device) for a in names}
    write_interval = max(1, timesteps // 100)
    kw = skrl_kwargs_defaults(names)
    kw["observation_preprocessor_kwargs"] = {a: {"size": OBS_SPACE, "device": device} for a in names}
    kw["value_preprocessor_kwargs"] = {a: {"size": 1, "device": device} for a in names}
    agent_cfg = IPPO_CFG(rollouts=rollouts, learning_epochs=int(st["learning_epochs"]),
                         mini_batches=int(st["mini_batches"]), learning_rate=float(st["learning_rate"]), **extra_cfg,
                         observation_preprocessor={a: RunningStandardScaler for a in names},
                         value_preprocessor={a: RunningStandardScaler for a in names},
                         experiment={"directory": str(run_dir.parent), "experiment_name": run_dir.name,
                                     "write_interval": write_interval, "checkpoint_interval": 0},
                         **kw)
    # The table's written-down skrl values must be skrl's effective ones. Checked on a copy expanded exactly as IPPO
    # expands its cfg (MultiAgent base __init__: cfg.expand(possible_agents=...)), BEFORE the run folder is made.
    probe = copy.deepcopy(agent_cfg)
    probe.expand(possible_agents=list(names))
    mismatch = skrl_table_mismatch(effective_agent_cfg(probe, names[0]), st, table_name)
    if mismatch:
        print(f"refusing: {mismatch}", file=sys.stderr)
        return 2
    run_dir.mkdir(parents=True, exist_ok=True)
    agent = IPPO(possible_agents=names, models=models, memories=memories, observation_spaces=env.observation_spaces,
                 state_spaces=env.state_spaces, action_spaces=env.action_spaces, device=device, cfg=agent_cfg)
    if args.warm_start:          # checked above: same team, team sizes and hidden layers
        agent.load(str(pathlib.Path(args.warm_start) / AGENT_FILE))

    # ---- interface.toml, before training (STANDARDS §3 rule 1) ----
    v = ObsView()
    obs_layout = {"own_pos": [v.own_pos.start, v.own_pos.stop], "own_vel": [v.own_vel.start, v.own_vel.stop],
                  "sin_cos_yaw": [v.sin_cos_yaw.start, v.sin_cos_yaw.stop], "zone_radius": [v.zone_radius, v.zone_radius + 1],
                  "arena_half": [v.arena_half, v.arena_half + 1], "time_left": [v.time_left, v.time_left + 1],
                  "team": [v.team, v.team + 1], "alive": [v.alive, v.alive + 1],
                  "slots": [v.SLOTS_FROM, v.SLOTS_FROM + 7 * (cfg.pad_guards + cfg.pad_strikes)],
                  "zone_centre": [v.zone_centre.start, v.zone_centre.stop]}
    if motion == "pure":
        param_set = "none (pure rules)"
    else:
        pf = resolve_params(cfg.starling.params)
        param_set = (f"{cfg.starling.params} (exploratory; commander and safety filter), sha256 {sha256_file(pf)}")
        if motion == "physics":
            param_set += (f"; physics drone {physics_meta['physics_params']} sha256 "
                          f"{physics_meta['physics_params_sha256']}")
    commit = git_commit()
    import skrl
    c0 = effective_agent_cfg(agent.cfg, names[0])   # the effective per-agent settings (skrl expands them per name)
    keys = ("rollouts", "learning_epochs", "mini_batches", "discount_factor", "gae_lambda", "learning_rate",
            "entropy_loss_scale", "value_loss_scale", "ratio_clip", "value_clip", "grad_norm_clip", "kl_threshold",
            "time_limit_bootstrap", "random_timesteps", "learning_starts", "mixed_precision")
    skrl_settings = {f"skrl_{k}": ("none" if c0.get(k) is None else c0.get(k)) for k in keys if k in c0}
    skrl_settings["skrl_version"] = skrl.__version__
    mismatch = skrl_table_mismatch(c0, st, table_name)          # the same rule on the agent itself (never expected)
    if mismatch:
        raise RuntimeError(mismatch)
    effective_log_std = 0.0 if init_log_std is None else float(init_log_std)     # 0.0 = learned.py's zeros
    settings_sha = hashlib.sha256(table_text(settings_text, table_name).encode()).hexdigest()
    meta = {
        "interface_version": INTERFACE_VERSION, "pipe_test": True, "what": "stand-in (pipe test), not a strategy "
        "of record; observed in the training simulator", "team": train_team, "guards": guards, "strikes": strikes,
        "algorithm": "IPPO", "motion": game.motion, "preset": "nus_hangar" if nus else PRESET_OF[motion], "game": args.game,
        "world": physics_meta.get("world", "none"), "parameter_set": param_set,
        "game_config": built.prov_name, "game_config_sha256": built.prov_sha256,
        "local_file": built.local_file, "settings_file": settings_path.name,
        "standin_table_sha256": hashlib.sha256(table_text(standin_text, "standin").encode()).hexdigest(),
        "settings_table": table_name, "settings_table_sha256": settings_sha,
        "settings_table_status": SETTINGS_TABLES[table_name][1],
        "seed": seed, "git_commit": commit, "tick_s": 0.05, "rate_hz": 20,
        "frames": "world ENU (x east, y north, z up); positions from the zone centre",
        "created": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "observation": {"dim": OBS_DIM, "view": cfg.obs_view, "pad_guards": cfg.pad_guards,
                        "pad_strikes": cfg.pad_strikes, **obs_layout},
        "action": {"order": ["vx", "vy", "vz", "yaw_rate"], "range": [-1.0, 1.0],
                   "guard_speed_mps": cfg.team_speed_mps("guard"), "strike_speed_mps": cfg.team_speed_mps("strike"),
                   "yaw_rate_max_rad_s": cfg.yaw_rate_max_rad_s,
                   "note": "velocity part capped at length 1, then times the team speed; vz ignored under pure rules"},
        "network": {"hidden": list(st["hidden"]), "activation": "ELU",
                    "policy": "Gaussian, mean through Tanh (in [-1, 1]), one log std per axis; sampled actions clipped",
                    "observation_scaler": "RunningStandardScaler", "value_scaler": "RunningStandardScaler",
                    "one_network_per_guard_slot": True, "agent_file": AGENT_FILE},
        "training": {"num_games": n, "timesteps": timesteps, "game_steps_budget": budget_game_steps,
                     "wall_clock_cap_min": cap_min, "rollouts": rollouts,
                     "learning_epochs": int(st["learning_epochs"]), "mini_batches": int(st["mini_batches"]),
                     "learning_rate": float(st["learning_rate"]), "shaping_weight": float(st["shaping_weight"]),
                     "opponent_mix": mix, "eval_games": e, "eval_every_updates": int(args.eval_every_updates),
                     "eval_seed": eval_seed, "eval_max_steps": int(args.eval_max_steps or game.ticks),
                     "device": device, "init_log_std": effective_log_std, "frozen_log_std_axes": freeze_axes,
                     "stop_at": args.stop_at or "none", "stop_file": args.stop_file or "none", **skrl_settings},
    }
    if nus:     # the pilot's own fields (Phase 5): its game row, evaluations, hard cap and warm start
        meta["training"].update({"train_team": train_team, "nus_row": pw.row["id"], "eval_games_early": e_early,
                                 "eval_at_start": eval_at_start, "mid_evaluation": mid_planned, "gpu_cap_hours": float(st["gpu_cap_hours"]),
                                 "cap_s_effective": cap_s, "estimate_eval_s": est_eval_s, "warm_start": args.warm_start or "none",
                                 "pytorch_cuda_alloc_conf": os.environ.get("PYTORCH_CUDA_ALLOC_CONF", "none"),
                                 "pytorch_cuda_alloc_conf_replaced": alloc_before, "decision_ticks": tps,
                                 "zero_mean_init": zero_mean})
    if table_name != "standin":
        meta["settings_values"] = dict(st)          # the whole table as read (the committed [standin] is pinned)
    if physics_meta:
        meta["physics"] = physics_meta
    if diag:
        meta["diagnostic"] = {"note": "DIAGNOSTIC run: settings outside the committed [standin]; never a run of record",
                              **diag}
    (run_dir / INTERFACE_FILE).write_text(to_toml(meta, header=FIRST_LINE))

    # ---- TensorBoard: the game/ scalars and the settings text (skrl writes its own file beside it) ----
    tb = SummaryWriter(log_dir=str(run_dir), filename_suffix=".game")
    text_of = {"game_config_sha256": built.prov_sha256, "seed": str(seed), "backend": game.motion,
               "preset": "nus_hangar" if nus else PRESET_OF[motion]}
    for key in tb_cfg["settings_text"]:
        tb.add_text(f"settings/{key}", text_of[key], 0)
    tb.add_text("settings/settings_table", f"[{table_name}] of {settings_path.name} (sha256 {settings_sha}): "
                f"{SETTINGS_TABLES[table_name][1]}", 0)
    table = "| setting | value |\n|---|---|\n" + "\n".join(
        f"| {k} | {x} |" for k, x in [*text_of.items(), ("algorithm", "IPPO"), ("num_games", n),
                                      ("timesteps", timesteps), ("wall_clock_cap_min", cap_min),
                                      ("git_commit", commit), ("pipe_test", "true"),
                                      ("settings_table", f"[{table_name}] of {settings_path.name}"),
                                      ("settings_table_sha256", settings_sha),
                                      ("init_log_std", effective_log_std), ("frozen_log_std_axes", freeze_axes),
                                      ("game_steps_budget", budget_game_steps),
                                      *[(f"DIAGNOSTIC {k}", x) for k, x in diag.items()],
                                      ("hidden", list(st["hidden"])), ("policy mean", "Tanh"),
                                      *skrl_settings.items(),
                                      *([("yaw_rate_gains", physics_meta["yaw_rate_gains"])] if physics_meta else [])])
    tb.add_text("settings", table, 0)
    if diag:
        tb.add_text("diagnostic", "DIAGNOSTIC run, never a run of record: " + ", ".join(f"{k} = {x}" for k, x in
                                                                                    diag.items()), 0)
    tb.flush()

    # ---- the evaluation ----
    class LiveGuard:
        """The networks being trained, as a strategy of the trained team (the Guard team on --game s2): mean action after the
        observation scaler."""
        team, name = train_team, "standin (current networks, mean action)"

        def reset(self, games) -> None:
            pass

        mean_abs_max = None       # largest |mean action| of this evaluation (before the clamp), device tensor

        def act(self, obs):
            with torch.no_grad():
                raw = torch.stack([agent.policies[a].net(agent._observation_preprocessor[a](obs[:, k]))
                                   for k, a in enumerate(names)], dim=1)
            m = raw.abs().amax()
            self.mean_abs_max = m if self.mean_abs_max is None else torch.maximum(self.mean_abs_max, m)
            return raw.clamp(-1.0, 1.0)

    class NonFiniteAbort(Exception):
        """NaN or inf found: the run is ABORTED (module docstring)."""

    last_loss: dict[str, float] = {}
    _track = agent.track_data

    def track_data(tag: str, value: float) -> None:          # keep the latest value of every skrl-tracked number
        last_loss[tag] = value
        _track(tag, value)

    agent.track_data = track_data

    def check_finite(rollout_nonfinite, where: str) -> None:
        """One host read: actions of the rollout, every weight and scaler statistic; then the tracked losses."""
        bad = [rollout_nonfinite > 0]
        for a in names:
            for mod in (agent.policies[a], agent.values[a], agent._observation_preprocessor[a],
                        agent._value_preprocessor[a]):
                for t in list(mod.parameters()) + list(mod.buffers()):
                    if t.is_floating_point():
                        bad.append(~torch.isfinite(t).all())
        if bool(torch.stack(bad).any()):
            what = []
            if int(rollout_nonfinite) > 0:
                what.append(f"{int(rollout_nonfinite)} drone-steps with non-finite actions")
            for a in names:
                for nm, mod in (("policy", agent.policies[a]), ("value", agent.values[a]),
                                ("observation scaler", agent._observation_preprocessor[a]),
                                ("value scaler", agent._value_preprocessor[a])):
                    if any(t.is_floating_point() and not bool(torch.isfinite(t).all())
                           for t in list(mod.parameters()) + list(mod.buffers())):
                        what.append(f"{a} {nm} weights")
            raise NonFiniteAbort(f"{where}: non-finite " + ", ".join(what))
        lossy = [k for k, x in last_loss.items() if k.startswith("Loss") and not math.isfinite(x)]
        if lossy:
            raise NonFiniteAbort(f"{where}: non-finite " + ", ".join(lossy))

    live = LiveGuard()
    live_eval = nus_pilot.HeldStrategy(live, tps) if tps > 1 else live     # the evaluation on the training's decision schedule
    curve: list[dict] = []
    clock = {"train_s": 0.0, "eval_s": 0.0, "last_train_s": 0.0, "last_timestep": 0}

    best = {"score": None, "label": None}
    clips_of: dict[str, list] = {}          # nus_hangar: the kept slots' clips of every evaluation, rendered after the GPU work

    def evaluate(timestep: int, kind: str = "periodic") -> None:
        t0 = time.perf_counter()
        snap = eval_world.snapshot() if eval_world is not None else None
        size = e_early if nus and kind in ("start", "mid") else e
        game_e, opp_e, slices_e = built.evals[size]
        game_e.gen.manual_seed(eval_seed)                    # the same evaluation games every time
        live.mean_abs_max = None
        if live_eval is not live:
            live_eval.restart()
        res = play_match(game_e, *((live_eval, opp_e) if train_team == "guard" else (opp_e, live_eval)), max_steps=args.eval_max_steps)
        if eval_world is not None:
            eval_world.restore(snap)
        check_finite(res.nonfinite_actions.sum(), f"evaluation at timestep {timestep}")
        entry: dict = {"timestep": timestep, "game_steps": timestep * n * tps, "train_s": clock["train_s"]}
        rows = summarise(res, by=())
        overall = rows[0] if rows else None
        hold = {}
        for b, sl in slices_e:
            r = summarise(res.slice(sl), by=())
            hold[b] = r[0] if r else None
        oc, es = res.outcome.cpu(), res.end_step.cpu()
        fin = oc != RUNNING
        n_fin = int(fin.sum())
        timeout = int(((oc == GUARD_WIN) & (es >= game_e.ticks) & fin).sum())
        scal: dict[str, float] = {}
        if overall is not None:
            scal["game/hold_rate"] = overall["hold_rate"]
            scal["game/timeout_win_share"] = timeout / n_fin
            if overall["closest_cross_3d_m"] is not None:
                scal["game/closest_cross_3d_min_m"] = overall["closest_cross_3d_m"]
                scal["game/closest_cross_3d_p05_m"] = overall["closest_cross_3d_p05_m"]
            scal["game/filter_share"] = overall["filter_rate"]
        for b, r in hold.items():
            if r is not None:
                scal[f"game/hold_rate/{b}"] = r["hold_rate"]
        d_train = clock["train_s"] - clock["last_train_s"]
        if d_train > 0:
            scal["game/game_steps_per_s"] = (timestep - clock["last_timestep"]) * n * tps / d_train
        scal["game/eval_games_finished"] = float(n_fin)
        scal["standin/mean_action_abs_max"] = float(live.mean_abs_max)
        for tag, val in scal.items():
            if val is not None:
                tb.add_scalar(tag, val, timestep)
        tb.flush()
        clock["last_train_s"], clock["last_timestep"] = clock["train_s"], timestep
        entry.update({"finished": n_fin, "timeout_wins": timeout, "scalars": scal,
                      "per_behaviour": {b: r for b, r in hold.items()}, "overall": overall, "kind": kind, "eval_games": size})
        curve.append(entry)
        (run_dir / "curve.json").write_text(json.dumps(curve, indent=1))
        agent.save(str(run_dir / AGENT_FILE))
        if nus:      # videos of every evaluation; the best evaluation for the trained team: Guard hold rate, or Strike reach rate
            label = f"{kind}_t{timestep}"
            clips_of[label] = nus_pilot.eval_clips(res, game_e.extras(), pw)
            score = None if overall is None else (overall["hold_rate"] if train_team == "guard" else 1.0 - overall["hold_rate"])
            if best["label"] is None or (score is not None and (best["score"] is None or score > best["score"])):
                best.update(score=score, label=label)
                agent.save(str(run_dir / "agent_best.pt"))
        clock["eval_s"] += time.perf_counter() - t0
        hr = " ".join(f"{b} {scal.get(f'game/hold_rate/{b}', float('nan')):.3f}" for b in behaviours)
        print(f"[eval {kind}, {size} games] timestep {timestep} game-steps {timestep * n * tps:,} | hold {hr} | finished {n_fin}/{size} | "
              f"train {clock['train_s']:.0f} s eval {clock['eval_s']:.0f} s", flush=True)

    # ---- training ----
    class StandinTrainer(SequentialTrainer):
        """skrl's single multi-agent training loop (trainers/torch/base.py ``Trainer.train``), with the
        evaluation and the wall-clock cap checked after every update (training time only)."""
        stopped_by_cap = False
        stop_reason = None          # an operator stop (--stop-at, --stop-file): status ABORTED, exit 4
        timesteps_done = 0
        upset_games = None          # finished training games in which a live drone was upset (physics; D10)

        def train(self) -> None:
            self.agents.enable_training_mode(True)
            observations, infos = self.env.reset()
            states = self.env.state()
            total = self.cfg.timesteps
            self.upset_games = torch.zeros((), dtype=torch.long, device=device)
            nonfinite = torch.zeros((), dtype=torch.long, device=device)
            for timestep in range(total):
                t0 = time.perf_counter()
                self.agents.pre_interaction(timestep=timestep, timesteps=total)
                with torch.no_grad():
                    actions, _ = self.agents.act(observations, states, timestep=timestep, timesteps=total)
                    nxt, rewards, terminated, truncated, infos = self.env.step(actions)
                    nxt_states = self.env.state()
                    self.upset_games = self.upset_games + (infos["upset"] & terminated[names[0]][:, 0]).sum()
                    nonfinite = nonfinite + infos["nonfinite_actions"].sum()
                    self.agents.record_transition(observations=observations, states=states, actions=actions,
                                                  rewards=rewards, next_observations=nxt, next_states=nxt_states,
                                                  terminated=terminated, truncated=truncated, infos=infos,
                                                  timestep=timestep, timesteps=total)
                self.agents.post_interaction(timestep=timestep, timesteps=total)
                observations, states = nxt, nxt_states
                clock["train_s"] += time.perf_counter() - t0
                self.timesteps_done = timestep + 1
                if (timestep + 1) % rollouts == 0:                       # an update just ran
                    updates = (timestep + 1) // rollouts
                    check_finite(nonfinite, f"update {updates} (timestep {timestep + 1})")
                    nonfinite = torch.zeros_like(nonfinite)
                    if nus:       # hard wall-clock cap incl. evaluations: stop while the evaluations still due fit
                        update_s = clock["train_s"] - clock.get("train_at_update", 0.0)
                        clock["train_at_update"] = clock["train_s"]
                        elapsed = time.time() - t_start
                        if pilot_state["mid_pending"] and nus_pilot.must_stop(elapsed, 2 * est_eval_s + update_s, cap_s):
                            pilot_state["mid_pending"] = False
                            pilot_state["mid_note"] = f"half-way evaluation dropped at update {updates}: no room under the cap"
                        if nus_pilot.must_stop(elapsed, est_eval_s + update_s, cap_s):
                            self.stopped_by_cap = True
                            return
                    elif clock["train_s"] >= cap_min * 60.0:
                        self.stopped_by_cap = True
                        return
                    if stop_at is not None and time.time() >= stop_at:
                        self.stop_reason = f"stopped by the operator: stop time {args.stop_at} reached"
                        return
                    if args.stop_file and os.path.exists(args.stop_file):
                        self.stop_reason = f"stopped by the operator: stop file {args.stop_file} present"
                        return
                    if nus:
                        if pilot_state["mid_pending"] and clock["train_s"] >= pilot_state["half_train_s"] and timestep + 1 < total:
                            pilot_state["mid_pending"] = False
                            self.agents.enable_training_mode(False)
                            evaluate(timestep + 1, "mid")
                            self.agents.enable_training_mode(True)
                    elif updates % int(args.eval_every_updates) == 0 and timestep + 1 < total:
                        self.agents.enable_training_mode(False)
                        evaluate(timestep + 1)
                        self.agents.enable_training_mode(True)

    trainer = StandinTrainer(env=env, agents=agent, cfg={"timesteps": timesteps, "headless": True,
                                                         "disable_progressbar": True,
                                                         "close_environment_at_exit": False})
    print(f"stand-in (pipe test): motion {game.motion}, {n} games, {timesteps} timesteps "
          f"({timesteps * n * tps:,} game-steps of {budget_game_steps:,}), cap {cap_min:g} min "
          f"{'wall clock incl. evaluations (hard)' if nus else 'training time'}, "
          f"run folder {run_dir}", flush=True)
    status, abort_reason = "FINISHED", None
    if nus:   # the half-way evaluation: when the training time reaches half of what the cap leaves after the planned evaluations
        planned = 1 + int(eval_at_start) + int(mid_planned)
        pilot_state = {"mid_pending": mid_planned, "half_train_s": nus_pilot.mid_point_s(cap_s, est_eval_s, planned), "mid_note": None}
    try:
        if not args.no_eval_at_start and (not nus or eval_at_start):
            evaluate(0, "start")
        trainer.train()
        agent.enable_training_mode(False)
        evaluate(trainer.timesteps_done, "final")
        if trainer.stop_reason:
            status, abort_reason = "ABORTED", trainer.stop_reason
            tb.add_text("status", f"ABORTED: {trainer.stop_reason}; agent.pt is the networks at the stop",
                        trainer.timesteps_done)
            print(f"ABORTED: {trainer.stop_reason} (final evaluation done, agent.pt kept)", file=sys.stderr,
                  flush=True)
    except NonFiniteAbort as ex:
        status, abort_reason = "ABORTED", str(ex)
        tb.add_text("status", f"ABORTED: {ex}; agent.pt is the last evaluation's networks", trainer.timesteps_done)
        print(f"ABORTED: {ex} (agent.pt kept from the last evaluation)", file=sys.stderr, flush=True)
    except BaseException as ex:      # a crash, an out-of-memory error or Ctrl-C: the pilots' ledger still gets the hours, then re-raise
        if nus:
            nus_pilot.append_gpu_hours(nus_pilot.GPU_HOURS_LOG, args.name, t_start, time.time(),
                                       note=f"{table_name}, CRASHED: {type(ex).__name__}")
        raise
    if getattr(agent, "writer", None) is not None:
        agent.writer.flush()
        agent.writer.close()
    tb.close()
    gpu_end = time.time()
    videos: list[str] = []
    render_s = 0.0
    if nus:      # videos after the GPU work (STANDARDS section 8): one per evaluation, two for the final and the best
        nus_pilot.free_gpu_cache()
        t_render = time.perf_counter()
        names_vs = ("standin", "/".join(mix)) if train_team == "guard" else ("/".join(mix), "standin")
        final_label = next((lb for lb in reversed(list(clips_of)) if lb.startswith("final")), None)
        for lb, clips in clips_of.items():
            count = int(pilots["videos_final_best"]) if lb in (final_label, best["label"]) else int(pilots["videos_per_evaluation"])
            tag = lb + ("_final" if lb == final_label and not lb.startswith("final") else "") + ("_best" if lb == best["label"] else "")
            videos += [str(v) for v in nus_pilot.render_clips(clips, run_dir / "videos", tag, count, pw, *names_vs, seed)]
        render_s = time.perf_counter() - t_render
        nus_pilot.append_gpu_hours(nus_pilot.GPU_HOURS_LOG, args.name, t_start, gpu_end,
                                   note=f"{table_name}, {status}, videos rendered after the end ({render_s:.0f} s, CPU)")
    result = {"what": FIRST_LINE, "status": status, "abort_reason": abort_reason,
              "motion": game.motion, "seed": seed, "num_games": n,
              "timesteps_planned": timesteps, "timesteps_done": trainer.timesteps_done,
              "game_steps_done": trainer.timesteps_done * n * tps, "game_steps_budget": budget_game_steps,
              "updates_done": trainer.timesteps_done // rollouts,
              "stopped_by_wall_clock_cap": trainer.stopped_by_cap, "wall_clock_cap_min": cap_min,
              "stopped_by_operator": trainer.stop_reason is not None,
              "settings_table": table_name, "settings_file": settings_path.name,
              "settings_table_sha256": settings_sha, "settings_table_status": SETTINGS_TABLES[table_name][1],
              "settings_values": dict(st), "init_log_std": effective_log_std, "frozen_log_std_axes": freeze_axes,
              "train_s": clock["train_s"], "eval_s": clock["eval_s"], "total_s": time.time() - t_start,
              "evaluations": len(curve), "eval_to_train_time_ratio": clock["eval_s"] / max(clock["train_s"], 1e-9),
              "upset_training_games": int(trainer.upset_games) if trainer.upset_games is not None else 0,
              "nonfinite_count": int(game._starling.drone.nonfinite_count) if motion == "physics" else 0,
              "git_commit": commit, "device": device, "smoke": bool(getattr(args, "smoke", False)),
              "skrl_settings": skrl_settings, "train_team": train_team,
              **({"game": "nus_hangar", "cap_s_effective": cap_s, "estimate_eval_s": est_eval_s, "gpu_seconds": gpu_end - t_start,
                  "render_s": render_s, "videos": videos, "best_evaluation": best["label"], "mid_note": pilot_state["mid_note"],
                  "pytorch_cuda_alloc_conf": os.environ.get("PYTORCH_CUDA_ALLOC_CONF", "none"),
                  "pytorch_cuda_alloc_conf_replaced": alloc_before,
                  "peak_gpu_bytes": int(torch.cuda.max_memory_allocated()) if device.startswith("cuda") else None,
                  "peak_gpu_reserved_bytes": int(torch.cuda.max_memory_reserved()) if device.startswith("cuda") else None}
                 if nus else {}),
              "last_tracked": {k: x for k, x in last_loss.items()}}
    (run_dir / "train_result.json").write_text(json.dumps(result, indent=1, default=str))
    if status == "ABORTED":
        return 4 if trainer.stop_reason else 3
    print(f"done: {result['game_steps_done']:,} game-steps "
          f"({'stopped by the wall-clock cap' if trainer.stopped_by_cap else 'budget reached'}), train "
          f"{clock['train_s']:.0f} s, eval {clock['eval_s']:.0f} s -> {run_dir}", flush=True)
    return 0


def main(argv: list[str] | None = None, world_factory: Callable | None = None) -> int:
    """In-process entry (tests): no Isaac. ``world_factory`` is the test hook for --motion physics."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["verdict"]:
        return verdict_main(argv[1:])
    try:
        args = make_parser().parse_args(argv)
    except SystemExit as ex:
        return int(ex.code or 0) if ex.code not in (None, 0) else 0
    return run(args, world_factory)


def _isaac_world_factory(n: int, m: int, params, device: str):
    """IsaacWorld of n games x m drones (Isaac Sim already started by __main__)."""
    from svg_training.compat import isaaclab_232 as isaac
    sim = isaac.make_physics_sim(params.physics_dt_s, device)
    if "--windowed" not in sys.argv[1:]:
        world = isaac.IsaacWorld(sim, n, m, params.airframe, params.physics_dt_s)
    else:                                          # screenshots only: Starling look, lights, floor, view on game 0
        world = isaac.windowed_world(sim, n, m, params.airframe, params.physics_dt_s, str(WINDOW_STARLING_USD))
    isaac.physics_play(sim, world)                 # starts PhysX, writes the inertia, checks the read-back
    return world


# --windowed only: the AirStack Starling model, read-only (as scripts/make_s2b_video.py)
WINDOW_STARLING_USD = (pathlib.Path(__file__).resolve().parents[1] / ".." / "AirStack" / "simulation" / "isaac-sim"
                       / "assets" / "robots" / "starling2max.usd").resolve()


def _main_cli() -> int:
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--motion", choices=MOTIONS, default="pure")
    known, _ = pre.parse_known_args(sys.argv[1:])
    if sys.argv[1:2] == ["verdict"] or known.motion != "physics":
        return main()
    # physics: Isaac Lab, headless only (S2b plan), started before torch is imported
    if "--headless" not in sys.argv[1:] and "--windowed" not in sys.argv[1:]:   # --windowed: screenshots only
        print("refused: --motion physics runs Isaac Lab: add --headless (after "
              "scripts/isaac_preflight.sh)", file=sys.stderr)
        return 2
    problem = skrl_version_problem()
    if problem:                                 # before Isaac Sim starts
        print(f"refusing: {problem}", file=sys.stderr)
        return 2
    from _isaac_app import start_headless
    args, _app = start_headless(make_parser(isaac=True))
    code = 1
    try:
        code = run(args, _isaac_world_factory)
    except BaseException:
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)          # never simulation_app.close() (it swallows exit codes in the container)
    return code


if __name__ == "__main__":
    try:
        rc = _main_cli()
    except SystemExit:
        raise
    except BaseException:
        traceback.print_exc()
        rc = 1
    sys.exit(rc)
