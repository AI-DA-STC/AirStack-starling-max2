#!/usr/bin/env python3
"""Stand-in trainer (S2 Task 10, built in S2b Task 9): skrl IPPO, 2 Guard drones v 1 scripted Strike drone.

The stand-in is a PIPE TEST: it proves that the game, the skrl adapter, training, TensorBoard, saving, loading and
scoring connect, on each motion backend. It is never "the policy" and never a strategy of record.

  # PyTorch (tier 1), no Isaac: pure partner rules, or the Starling layer (exploratory drone model)
  train_standin.py --config configs/s2.toml --seed <s> --name <date>_s2b_standin_pure_seed<s> [--motion pure]
  train_standin.py --config configs/s2.toml --seed <s> --name <date>_s2b_standin_starling_seed<s> --motion starling
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
folder. Exit 0 = finished (stopped by the budget or the cap), 1 = crash, 2 = bad arguments or refused.
"""
from __future__ import annotations

import argparse
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
PRESET_OF = {"pure": "pure", "starling": "starling", "physics": "physics"}   # score.py's preset names
EVAL_SEED_OFFSET = 1000              # = [standin_gates] eval_seed_offset (the learning curve uses the same rule)
FIRST_LINE = "Stand-in (pipe test), not a strategy of record. Observed in the training simulator."


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
def make_parser(isaac: bool = False) -> argparse.ArgumentParser:
    """isaac=True leaves --device to Isaac Lab's launcher arguments (it adds its own)."""
    ap = argparse.ArgumentParser(description="Stand-in trainer (pipe test): skrl IPPO, 2 Guard v 1 Strike.")
    ap.add_argument("--config", default=str(CONFIGS / "s2.toml"), help="settings file holding [standin]")
    ap.add_argument("--s2b-config", default=str(CONFIGS / "s2b.toml"),
                    help="file holding [standin_s2b] (caps) and [tensorboard]")
    ap.add_argument("--game-config", default=str(CONFIGS / "s2_game.toml"))
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--name", required=True, help="run folder name under --runs-dir")
    ap.add_argument("--motion", choices=MOTIONS, default="pure")
    ap.add_argument("--timesteps-override", type=int, help="skrl timesteps (tests and smoke runs only)")
    ap.add_argument("--num-games-override", type=int, help="games per batch (tests and smoke runs only)")
    ap.add_argument("--cap-min-override", type=float, help="wall-clock cap in minutes (tests only)")
    ap.add_argument("--eval-games", type=int, default=256)
    ap.add_argument("--eval-every-updates", type=int, default=20)
    ap.add_argument("--eval-max-steps", type=int, help="steps per evaluation (default: the game length; tests)")
    ap.add_argument("--runs-dir", default=str(ROOT / "runs"))
    if not isaac:
        ap.add_argument("--device", default="cuda")
    return ap


# --------------------------------------------------------------------------------------------- the run
def run(args: argparse.Namespace, world_factory: Callable | None = None) -> int:
    """Train one seed. world_factory(num_games, drones, params, device) -> RigidBodyWorld is required for
    --motion physics (IsaacWorld from __main__; a TorchRigidBodyWorld only from tests)."""
    problem = skrl_version_problem()
    if problem:
        print(f"refusing: {problem}", file=sys.stderr)
        return 2
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

    t_start = time.time()
    device = str(args.device)
    if device.startswith("cpu"):
        # Small CPU batches (tests, smoke runs): one thread. Measured 16 Nov 2026 on this laptop, 32 games 2v1:
        # 6 s with one thread against 83 s with torch's default 24 (thread start-up on tiny tensors).
        torch.set_num_threads(1)
    settings_path = pathlib.Path(args.config)
    settings_text = settings_path.read_text()
    s2 = tomllib.loads(settings_text)
    st = s2["standin"]
    s2b = tomllib.loads(pathlib.Path(args.s2b_config).read_text())
    caps, tb_cfg = s2b["standin_s2b"], s2b["tensorboard"]
    motion = args.motion
    if motion not in caps["motions"]:
        print(f"refusing: motion {motion!r} not in [standin_s2b] motions {caps['motions']}", file=sys.stderr)
        return 2
    if st["preset"] != "pure" or st["algorithm"] != "IPPO":
        print("refusing: [standin] preset must be 'pure' and algorithm 'IPPO' (as committed)", file=sys.stderr)
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
    guards, strikes = int(st["guards"]), int(st["strikes"])
    e = int(args.eval_games)
    if e < 2 or (motion == "physics" and e > n):
        print(f"refusing: --eval-games {e} must be >= 2 and (physics) <= the {n} training games", file=sys.stderr)
        return 2
    budget_game_steps = int(st["game_steps_per_seed"])
    timesteps = int(args.timesteps_override or budget_game_steps // n)
    cap_min = float(args.cap_min_override if args.cap_min_override is not None else
                    (caps["wall_clock_cap_min_isaac"] if motion == "physics" else caps["wall_clock_cap_min_torch"]))
    rollouts = int(st["rollouts"])
    seed = int(args.seed)
    eval_seed = seed + EVAL_SEED_OFFSET

    # ---- game (committed neutral values only) ----
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
    mix = {k: float(v) for k, v in st["opponent_mix"].items()}
    behaviours = list(mix)

    def strike_mix(num: int, seed0: int) -> tuple[SplitStrategy, list[tuple[str, slice]]]:
        sl = mix_slices(mix, num)
        parts = [(make_strategy(b, "strike", cfg, s.stop - s.start, device, seed0 + j), s)
                 for j, (b, s) in enumerate(sl)]
        return SplitStrategy("strike", parts), sl

    train_strike, _ = strike_mix(n, seed + 202)
    eval_strike, eval_slices = strike_mix(e, eval_seed + 202)
    env = SvgSkrlEnv(game, train_teams=("guard",), opponents={"strike": train_strike})
    names = env.possible_agents

    # ---- skrl IPPO ----
    models = make_models(names, list(st["hidden"]), device)
    memories = {a: RandomMemory(memory_size=rollouts, num_envs=n, device=device) for a in names}
    run_dir.mkdir(parents=True, exist_ok=True)
    write_interval = max(1, timesteps // 100)
    kw = skrl_kwargs_defaults(names)
    kw["observation_preprocessor_kwargs"] = {a: {"size": OBS_SPACE, "device": device} for a in names}
    kw["value_preprocessor_kwargs"] = {a: {"size": 1, "device": device} for a in names}
    agent_cfg = IPPO_CFG(rollouts=rollouts, learning_epochs=int(st["learning_epochs"]),
                         mini_batches=int(st["mini_batches"]), learning_rate=float(st["learning_rate"]),
                         observation_preprocessor={a: RunningStandardScaler for a in names},
                         value_preprocessor={a: RunningStandardScaler for a in names},
                         experiment={"directory": str(run_dir.parent), "experiment_name": run_dir.name,
                                     "write_interval": write_interval, "checkpoint_interval": 0},
                         **kw)
    agent = IPPO(possible_agents=names, models=models, memories=memories, observation_spaces=env.observation_spaces,
                 state_spaces=env.state_spaces, action_spaces=env.action_spaces, device=device, cfg=agent_cfg)

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
    meta = {
        "interface_version": INTERFACE_VERSION, "pipe_test": True, "what": "stand-in (pipe test), not a strategy "
        "of record; observed in the training simulator", "team": "guard", "guards": guards, "strikes": strikes,
        "algorithm": "IPPO", "motion": game.motion, "preset": PRESET_OF[motion],
        "world": physics_meta.get("world", "none"), "parameter_set": param_set,
        "game_config": pathlib.Path(prov.game_file).name, "game_config_sha256": prov.game_sha256,
        "local_file": "none", "settings_file": settings_path.name,
        "standin_table_sha256": hashlib.sha256(table_text(settings_text, "standin").encode()).hexdigest(),
        "seed": seed, "git_commit": commit, "tick_s": 0.05, "rate_hz": 20,
        "frames": "world ENU (x east, y north, z up); positions from the zone centre",
        "created": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "observation": {"dim": OBS_DIM, "view": cfg.obs_view, "pad_guards": cfg.pad_guards,
                        "pad_strikes": cfg.pad_strikes, **obs_layout},
        "action": {"order": ["vx", "vy", "vz", "yaw_rate"], "range": [-1.0, 1.0],
                   "guard_speed_mps": cfg.team_speed_mps("guard"), "strike_speed_mps": cfg.team_speed_mps("strike"),
                   "yaw_rate_max_rad_s": cfg.yaw_rate_max_rad_s,
                   "note": "velocity part capped at length 1, then times the team speed; vz ignored under pure rules"},
        "network": {"hidden": list(st["hidden"]), "activation": "ELU", "policy": "Gaussian, one log std per axis",
                    "observation_scaler": "RunningStandardScaler", "value_scaler": "RunningStandardScaler",
                    "one_network_per_guard_slot": True, "agent_file": AGENT_FILE},
        "training": {"num_games": n, "timesteps": timesteps, "game_steps_budget": budget_game_steps,
                     "wall_clock_cap_min": cap_min, "rollouts": rollouts,
                     "learning_epochs": int(st["learning_epochs"]), "mini_batches": int(st["mini_batches"]),
                     "learning_rate": float(st["learning_rate"]), "shaping_weight": float(st["shaping_weight"]),
                     "opponent_mix": mix, "eval_games": e, "eval_every_updates": int(args.eval_every_updates),
                     "eval_seed": eval_seed, "eval_max_steps": int(args.eval_max_steps or game.ticks),
                     "device": device},
    }
    if physics_meta:
        meta["physics"] = physics_meta
    (run_dir / INTERFACE_FILE).write_text(to_toml(meta, header=FIRST_LINE))

    # ---- TensorBoard: the game/ scalars and the settings text (skrl writes its own file beside it) ----
    tb = SummaryWriter(log_dir=str(run_dir), filename_suffix=".game")
    text_of = {"game_config_sha256": prov.game_sha256, "seed": str(seed), "backend": game.motion,
               "preset": PRESET_OF[motion]}
    for key in tb_cfg["settings_text"]:
        tb.add_text(f"settings/{key}", text_of[key], 0)
    table = "| setting | value |\n|---|---|\n" + "\n".join(
        f"| {k} | {x} |" for k, x in [*text_of.items(), ("algorithm", "IPPO"), ("num_games", n),
                                      ("timesteps", timesteps), ("wall_clock_cap_min", cap_min),
                                      ("git_commit", commit), ("pipe_test", "true"),
                                      *([("yaw_rate_gains", physics_meta["yaw_rate_gains"])] if physics_meta else [])])
    tb.add_text("settings", table, 0)
    tb.flush()

    # ---- the evaluation ----
    class LiveGuard:
        """The networks being trained, as a Guard strategy: mean action after the observation scaler."""
        team, name = "guard", "standin (current networks, mean action)"

        def reset(self, games) -> None:
            pass

        def act(self, obs):
            with torch.no_grad():
                out = [agent.policies[a].net(agent._observation_preprocessor[a](obs[:, k])).clamp(-1.0, 1.0)
                       for k, a in enumerate(names)]
            return torch.stack(out, dim=1)

    live = LiveGuard()
    curve: list[dict] = []
    clock = {"train_s": 0.0, "eval_s": 0.0, "last_train_s": 0.0, "last_timestep": 0}

    def evaluate(timestep: int) -> None:
        t0 = time.perf_counter()
        snap = eval_world.snapshot() if eval_world is not None else None
        eval_game.gen.manual_seed(eval_seed)                 # the same evaluation games every time
        res = play_match(eval_game, live, eval_strike, max_steps=args.eval_max_steps)
        if eval_world is not None:
            eval_world.restore(snap)
        entry: dict = {"timestep": timestep, "game_steps": timestep * n, "train_s": clock["train_s"]}
        rows = summarise(res, by=())
        overall = rows[0] if rows else None
        hold = {}
        for b, sl in eval_slices:
            r = summarise(res.slice(sl), by=())
            hold[b] = r[0] if r else None
        oc, es = res.outcome.cpu(), res.end_step.cpu()
        fin = oc != RUNNING
        n_fin = int(fin.sum())
        timeout = int(((oc == GUARD_WIN) & (es >= eval_game.ticks) & fin).sum())
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
            scal["game/game_steps_per_s"] = (timestep - clock["last_timestep"]) * n / d_train
        scal["game/eval_games_finished"] = float(n_fin)
        for tag, val in scal.items():
            if val is not None:
                tb.add_scalar(tag, val, timestep)
        tb.flush()
        clock["last_train_s"], clock["last_timestep"] = clock["train_s"], timestep
        entry.update({"finished": n_fin, "timeout_wins": timeout, "scalars": scal,
                      "per_behaviour": {b: r for b, r in hold.items()}, "overall": overall})
        curve.append(entry)
        (run_dir / "curve.json").write_text(json.dumps(curve, indent=1))
        agent.save(str(run_dir / AGENT_FILE))
        clock["eval_s"] += time.perf_counter() - t0
        hr = " ".join(f"{b} {scal.get(f'game/hold_rate/{b}', float('nan')):.3f}" for b in behaviours)
        print(f"[eval] timestep {timestep} game-steps {timestep * n:,} | hold {hr} | finished {n_fin}/{e} | "
              f"train {clock['train_s']:.0f} s eval {clock['eval_s']:.0f} s", flush=True)

    # ---- training ----
    class StandinTrainer(SequentialTrainer):
        """skrl's single multi-agent training loop (trainers/torch/base.py ``Trainer.train``), with the
        evaluation and the wall-clock cap checked after every update (training time only)."""
        stopped_by_cap = False
        timesteps_done = 0
        upset_games = None          # finished training games in which a live drone was upset (physics; D10)

        def train(self) -> None:
            self.agents.enable_training_mode(True)
            observations, infos = self.env.reset()
            states = self.env.state()
            total = self.cfg.timesteps
            self.upset_games = torch.zeros((), dtype=torch.long, device=device)
            for timestep in range(total):
                t0 = time.perf_counter()
                self.agents.pre_interaction(timestep=timestep, timesteps=total)
                with torch.no_grad():
                    actions, _ = self.agents.act(observations, states, timestep=timestep, timesteps=total)
                    nxt, rewards, terminated, truncated, infos = self.env.step(actions)
                    nxt_states = self.env.state()
                    self.upset_games = self.upset_games + (infos["upset"] & terminated[names[0]][:, 0]).sum()
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
                    if clock["train_s"] >= cap_min * 60.0:
                        self.stopped_by_cap = True
                        return
                    if updates % int(args.eval_every_updates) == 0 and timestep + 1 < total:
                        self.agents.enable_training_mode(False)
                        evaluate(timestep + 1)
                        self.agents.enable_training_mode(True)

    trainer = StandinTrainer(env=env, agents=agent, cfg={"timesteps": timesteps, "headless": True,
                                                         "disable_progressbar": True,
                                                         "close_environment_at_exit": False})
    print(f"stand-in (pipe test): motion {game.motion}, {n} games, {timesteps} timesteps "
          f"({timesteps * n:,} game-steps of {budget_game_steps:,}), cap {cap_min:g} min training time, "
          f"run folder {run_dir}", flush=True)
    evaluate(0)
    trainer.train()
    agent.enable_training_mode(False)
    evaluate(trainer.timesteps_done)
    if getattr(agent, "writer", None) is not None:
        agent.writer.flush()
        agent.writer.close()
    tb.close()
    result = {"what": FIRST_LINE, "motion": game.motion, "seed": seed, "num_games": n,
              "timesteps_planned": timesteps, "timesteps_done": trainer.timesteps_done,
              "game_steps_done": trainer.timesteps_done * n, "game_steps_budget": budget_game_steps,
              "updates_done": trainer.timesteps_done // rollouts,
              "stopped_by_wall_clock_cap": trainer.stopped_by_cap, "wall_clock_cap_min": cap_min,
              "train_s": clock["train_s"], "eval_s": clock["eval_s"], "total_s": time.time() - t_start,
              "evaluations": len(curve), "eval_to_train_time_ratio": clock["eval_s"] / max(clock["train_s"], 1e-9),
              "upset_training_games": int(trainer.upset_games) if trainer.upset_games is not None else 0,
              "nonfinite_count": int(game._starling.drone.nonfinite_count) if motion == "physics" else 0,
              "git_commit": commit, "device": device,
              "skrl_cfg": {k: (str(x) if not isinstance(x, (int, float, str, bool, type(None))) else x)
                           for k, x in dataclasses.asdict(agent.cfg).items() if not isinstance(x, dict)}}
    (run_dir / "train_result.json").write_text(json.dumps(result, indent=1))
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
    world = isaac.IsaacWorld(sim, n, m, params.airframe, params.physics_dt_s)
    isaac.physics_play(sim, world)                 # starts PhysX, writes the inertia, checks the read-back
    return world


def _main_cli() -> int:
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--motion", choices=MOTIONS, default="pure")
    known, _ = pre.parse_known_args(sys.argv[1:])
    if sys.argv[1:2] == ["verdict"] or known.motion != "physics":
        return main()
    # physics: Isaac Lab, headless only (S2b plan), started before torch is imported
    if "--headless" not in sys.argv[1:]:
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
