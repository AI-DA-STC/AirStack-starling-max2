"""Train one lineage of our PyTorch copy of NUS's alternating best-response self-play on the replica (NUS port Phase 5, task M7; stage
5.1 and its batch-shape variants 5.1b and 5.1c). Conda ``env_isaaclab``; CUDA for runs of record, CPU for tests:

    cd <svg_training>; unset PYTHONPATH; PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/nus_selfplay_train.py \
        --seed 1001 --variant nus --device cuda [--out runs/nus_port/phase5/s51/seed1001] [--probe-only] [--accept-long]

What it does, in order:

1. **Batch shape.** ``nus``: the copied method's (games per update from the slot formula, the method's updates, minibatches and
   selection interval). ``5.1b`` / ``5.1c``: ``[gates.phase5_method_variants]`` of ``configs/nus_port.toml`` - games per update
   (rounded up to equal blocks per slot), updates per generation and the updates after which the learner is evaluated; the minibatch
   keeps the copied method's size in samples (its minimum batch x steps / its minibatches), so the minibatch count is the samples of
   an update over that size (the few samples a permutation leaves over are dropped).
2. **Probe** (``--probe-updates``, default from ``configs/nus_phase5_method.toml``): that many updates of generation 1 and one selection
   evaluation in ``<out>/probe/``, timed; an ESTIMATE of the whole lineage (every generation's updates plus its evaluations, the
   evaluation cost scaled by the pool's slot count) in ``<out>/probe.json``.
3. **Cap** (plan section 8): the stage group's cap less the GPU-hours already in its ``gpu_hours.log`` (CUDA entries; overlapping jobs
   counted once; paused time, ``scripts/gpu_pause.sh``, not counted). An estimate above the remaining cap refuses to start without
   ``--accept-long``; during the run the remaining cap is a hard limit on the wall clock less paused time (the run checkpoints and
   stops, exit 3, ABORTED). Each run appends its interval to the log. SIGINT (``gpu_pause.sh stop``) checkpoints at the next update
   boundary and exits 4 (STOPPED); the same command resumes.
4. **Training** (``nus/selfplay.py``): resumable from ``<out>`` (run the same command again).
5. **Videos** (STANDARDS section 8, plan 4.3): one replica game at every selection evaluation (against the slot the learner did worst
   against) and two per archived entry (the first Strike win and the first hold among the first ``games_searched`` games against its
   strongest pool member), top-down, ``viz/replay.render_replay``, into ``<out>/videos/``.
6. **Record draft** ``<out>/record_draft.md`` (training simulator, the replica; commit, local files by sha256, seeds, machine, games at
   once, game-steps per second, the archive, the videos).

Everything is written under runs/. Prints counts, rates and paths, never a partner value. No numeric literal other than 0, 1, -1, 2
(G2).
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import platform
import subprocess
import sys
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

RUNS_ROOT = ROOT / "runs"   # tests patch it
STAGE_DIR = RUNS_ROOT / "nus_port" / "phase5"
CONFIG = ROOT / "configs" / "nus_phase5_method.toml"
GATES = ROOT / "configs" / "nus_port.toml"
STAGE = {"nus": "s51", "5.1b": "s51b", "5.1c": "s51c"}
CAP_GROUP = {"nus": "s51", "5.1b": "variants", "5.1c": "variants"}
HOUR_S = datetime.timedelta(hours=1).total_seconds()
EXIT_REFUSED, EXIT_ABORTED, EXIT_STOPPED = 2, 2 + 1, 2 + 2


def _under_runs(path: Path) -> Path:
    resolved = Path(path).resolve()
    if RUNS_ROOT.resolve() not in (resolved, *resolved.parents):
        raise SystemExit(f"refusing: {resolved} is outside runs/")
    return resolved


# ------------------------------------------------------------------------------------------------ batch shape
def batch_shape(variant: str, method, episode_steps: int, gates: dict) -> dict:
    """The run's batch shape (see the module docstring, step 1). An empty dict keeps the copied method's own shape."""
    if variant == "nus":
        return {}
    table = gates["phase5_method_variants"]
    key = STAGE[variant]
    games = int(table["games_per_update"])
    minibatch_samples = method.minimum_rollout_batch * episode_steps // method.ppo_minibatches
    return {"games_per_update": games, "updates_per_generation": int(table["updates_per_generation"][key]),
            "selection_after": tuple(int(u) for u in table["selection_evaluations_after_update"][key]),
            "minibatches": max(1, round(games * episode_steps / minibatch_samples)), "drop_remainder": True,
            "minibatch_samples": minibatch_samples}


# ------------------------------------------------------------------------------------------------ GPU-hours log and cap
def logged_hours(log: Path, group: str, pauses: Path | None = None) -> float:
    """GPU-hours of one stage group in the log: the union of its CUDA intervals (overlapping jobs counted once) less the paused time."""
    from svg_training.nus.pauses import PAUSES_LOG, logged_gpu_hours
    return logged_gpu_hours(log, group, pauses or PAUSES_LOG)


def append_log(log: Path, row: dict) -> None:
    from svg_training.nus.pauses import append_row
    append_row(log, row)


def cap_reached(start: float, hours: float, pauses: Path, now: float | None = None) -> bool:
    """True once the wall clock since ``start`` (unix seconds) less the paused time reaches ``hours`` (the hard cap)."""
    from svg_training.nus.pauses import effective_seconds
    return effective_seconds(start, time.time() if now is None else now, pauses) >= hours * HOUR_S


def apply_memory_fraction(fraction: float, device) -> None:
    """Cap this process's share of the GPU's memory (side-by-side processes, plan section 10); the call needs a device index."""
    import torch
    index = device.index if device.index is not None else torch.cuda.current_device()
    torch.cuda.set_per_process_memory_fraction(fraction, index)


def install_stop_handler(sp):
    """SIGINT (scripts/gpu_pause.sh stop, or Ctrl-C) asks the run to checkpoint and return at the next update boundary. Returns the
    previous handler (restore it when the run returns)."""
    import signal
    previous = signal.getsignal(signal.SIGINT)

    def handler(signum, frame):
        sp.stop_requested = True
        print("[train] stop requested: checkpointing at the next update boundary", flush=True)

    signal.signal(signal.SIGINT, handler)
    return previous


# ------------------------------------------------------------------------------------------------ videos
def record_games(env, learner, pool, slot: int, games: int, generator):
    """``games`` replica games of the learner (mean action) against pool slot ``slot``, from fresh starts: positions (T + 1, games, M,
    2) and the step each game was first reached (-1 if never)."""
    import torch
    team = learner.team
    state = env.reset(pool.slots * games, generator)
    rows = slice(slot * games, (slot + 1) * games)
    frames = [state.game.pos[rows].clone()]
    first = torch.full((games,), -1, dtype=torch.long, device=env.device)
    with torch.no_grad():
        for t in range(env.episode_steps):
            guard_obs, strike_obs = env.observe(state)
            own, _ = learner.act(guard_obs if team == "guard" else strike_obs, None, deterministic=True)
            other = pool.actions(state, games)
            g_act, s_act = (own, other) if team == "guard" else (other, own)
            state, out = env.step(state, g_act, s_act, learner.gamma)
            frames.append(state.game.pos[rows].clone())
            first = torch.where((first < 0) & out.first_reach[rows], torch.full_like(first, t + 1), first)
    return torch.stack(frames).cpu(), first.cpu()


def to_recording(frames, first: int, env, team: str, game_index: int, opponent: str):
    """A ``viz.replay.Recording`` of one game in metres, one frame per simulator tick (linear interpolation within a held step)."""
    import numpy as np
    import torch
    from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
    from svg_training.viz.replay import Recording
    deploy, g = env.deploy, env.guard_count
    steps = first if first >= 0 else frames.shape[0] - 1
    ticks = [frames[0]]
    for t in range(steps):
        for sub in range(1, deploy.hold_ticks + 1):
            ticks.append(frames[t] + (frames[t + 1] - frames[t]) * (sub / deploy.hold_ticks))
    units = torch.stack(ticks)
    height = torch.full((*units.shape[:2], 1), deploy.flying_height_m)
    pos_m = torch.cat((units * deploy.metres_per_unit, height), dim=-1).numpy()
    closest = float(np.linalg.norm(pos_m[:, :g, None, :2] - pos_m[:, None, g:, :2], axis=-1).min())
    half = float(np.abs(pos_m[:, :, :2]).max()) * (1 + 1 / (2 * 2))
    names = ("trained policy", opponent) if team == "guard" else (opponent, "trained policy")
    return Recording(pos_m, np.ones(pos_m.shape[:2], bool), np.zeros(2), env.rules.area_radius * deploy.metres_per_unit, half,
                     STRIKE_WIN if first >= 0 else GUARD_WIN, pos_m.shape[0] - 1, g, env.strike_count, "replica",
                     "replica of the partner's 2-D game", names[0], names[1], 0, game_index, closest)


class Videos:
    """The two video hooks of ``SelfPlay`` (STANDARDS section 8)."""

    def __init__(self, out: Path, kind: str, games_searched: int):
        self.out, self.kind, self.games_searched, self.paths = out, kind, games_searched, []

    def _render(self, recording, name: str) -> None:
        from make_replay import FORMATS
        from svg_training.viz.replay import render_replay
        if self.kind == "none":
            return
        path = render_replay(recording, self.out / f"{name}.{self.kind}", playback_label="replica", **FORMATS[self.kind])
        self.paths.append(str(path))

    def _label(self, sp, slot: int) -> str:
        opponents = sp.state["active"]["opponents"]
        return f"generation {opponents[slot]['generation']}" if slot < len(opponents) else "scripted APF"

    def on_selection(self, sp, result: dict) -> None:
        from svg_training.nus.selfplay import _seeded
        active = sp.state["active"]
        slot = min(range(len(result["win_rates"])), key=lambda i: result["win_rates"][i])
        frames, first = record_games(sp.env, sp.learner, sp.pool, slot, 1, _seeded(sp.env.device, sp.seed, active["generation"], active["update"] + 1, 2))
        rec = to_recording(frames[:, 0], int(first[0]), sp.env, active["team"], 0, self._label(sp, slot))
        self._render(rec, f"g{active['generation']:02d}_{active['team']}_update{active['update']:05d}")

    def on_archive(self, sp, entry: dict) -> None:
        from svg_training.nus.selfplay import _seeded
        actor = sp.load_actor(entry)
        sp.learner.actor.load_state_dict(actor.state_dict())   # the archived best, not the last update
        slot = entry["strongest_slot"]
        frames, first = record_games(sp.env, sp.learner, sp.pool, slot, self.games_searched,
                                     _seeded(sp.env.device, sp.seed, entry["generation"], 0, 2))
        reached = [i for i in range(self.games_searched) if first[i] >= 0]
        held = [i for i in range(self.games_searched) if first[i] < 0]
        picks = ([reached[0]] if reached else []) + ([held[0]] if held else [])
        picks += [i for i in range(self.games_searched) if i not in picks][: 2 - len(picks)]
        for i in picks:
            rec = to_recording(frames[:, i], int(first[i]), sp.env, entry["team"], i, self._label(sp, slot))
            self._render(rec, f"archive_g{entry['generation']:02d}_{entry['team']}_game{i:02d}")


# ------------------------------------------------------------------------------------------------ probe and record
def probe(method, env, seed: int, shape: dict, out: Path, updates: int, generations: int, device) -> dict:
    """Time ``updates`` updates of generation 1 and one selection evaluation; ESTIMATE the lineage's wall clock."""
    import torch
    from svg_training.nus.selfplay import SelfPlay
    cuda = torch.device(device).type == "cuda"
    if cuda:
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
    folder = out / "probe"
    sp = SelfPlay(method, env, seed, folder, device=device, generations=generations, **_kw(shape))
    timed = min(updates, sp.updates - 1)   # the generation must stay open for the evaluation that follows
    if timed < 1:
        raise SystemExit("the probe needs at least two updates per generation")
    began = time.monotonic()
    sp.run(max_updates=timed)
    if cuda:
        torch.cuda.synchronize()
    per_update = (time.monotonic() - began) / max(sp.state["active"]["update"], 1)
    began = time.monotonic()
    sp.evaluate()
    if cuda:
        torch.cuda.synchronize()
    per_slot_evaluation = (time.monotonic() - began) / sp.pool.slots
    gib = float(2 ** (2 * 2 * 2 + 2 * 2 * 2 + 2 * 2 * 2 + 2 * 2 + 2))   # bytes in a GiB (2^30)
    peak = ({"peak_allocated_gib": torch.cuda.max_memory_allocated() / gib, "peak_reserved_gib": torch.cuda.max_memory_reserved() / gib}
            if cuda else {"peak_allocated_gib": None, "peak_reserved_gib": None})
    total = 0.0
    for generation in range(1, generations + 1):
        slots = min(generation // 2, method.max_learned_opponents) + 1   # earlier entries of the other team, plus APF
        total += sp.updates * per_update + len(sp.selection_after) * per_slot_evaluation * slots
    return {"updates_timed": sp.state["active"]["update"], "seconds_per_update": per_update,
            "seconds_per_evaluation_slot": per_slot_evaluation, "games_per_update": sp.state["active"]["games"],
            "estimate_hours": total / HOUR_S, "estimate_hours_three_seeds_one_after_another": (2 + 1) * total / HOUR_S,
            "side_by_side": "not measured: three seeds in one process were not probed", **peak,
            "selection_evaluation_seconds_one_slot": per_slot_evaluation, "estimate": "ESTIMATE: generations x (updates x seconds per update + evaluations x "
            "seconds per evaluation slot x slots)", "device": str(device)}


def _kw(shape: dict) -> dict:
    keys = ("games_per_update", "updates_per_generation", "selection_after", "minibatches", "drop_remainder")
    return {k: shape[k] for k in keys if k in shape}


def _sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record_draft(out: Path, args, shape: dict, sp, seconds: float, videos: list[str], status: str, inputs: dict[str, Path]) -> Path:
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", "."], capture_output=True, text=True).stdout.strip())
    archive = sp.state["archive"]
    steps = sum(json.loads((Path(e["path"]) / "metadata.json").read_text())["games_per_update"] for e in archive) * sp.updates
    steps *= sp.env.episode_steps
    lines = [f"# NUS port Phase 5, stage {STAGE[args.variant]}, seed {args.seed}: training simulator (replica of NUS's 2-D game), "
             f"record draft ({status})", "",
             "Observed in the training simulator (the replica, 2-D, no safety filter, plan P5-10). Nothing here is a flight result.", "",
             f"- Purpose: plan section 4.3, our copy of NUS's alternating best-response self-play, variant `{args.variant}`.",
             f"- Commit: `{commit}`{' plus uncommitted changes' if dirty else ''}.",
             f"- Local files (sha256): " + ", ".join(f"`{k}` {_sha(p)}" for k, p in inputs.items()) + ".",
             f"- Seed {args.seed}; stage seeds seed + generation - 1. Machine `{platform.node()}`, device `{args.device}`.",
             f"- Batch shape: {json.dumps(shape) if shape else 'the copied method'}; drones per game {sp.env.num_actors}; tier: replica.",
             f"- Wall clock {seconds / HOUR_S:.3f} h; game-steps per second (training updates only, ESTIMATE) "
             f"{steps / max(seconds, 1):.0f} at the games per update listed below.",
             "", "| Generation | Team | Games per update | Best update | Rank (geometric, worst, mean) |", "|---|---|---|---|---|"]
    for e in archive:
        meta = json.loads((Path(e["path"]) / "metadata.json").read_text())
        lines.append(f"| {e['generation']} | {e['team']} | {meta['games_per_update']} | {meta['best_update']} | {meta['best_rank']} |")
    lines += ["", "Videos:"] + [f"- `{p}`" for p in videos] + ([] if videos else ["- none (state why)"])
    lines += ["", "Gates: none at training time; the 5.1 statistics are scored afterwards (`nus/crossplay.py`, M8)."]
    path = out / "record_draft.md"
    path.write_text("\n".join(lines) + "\n")
    return path


# ------------------------------------------------------------------------------------------------ main
def main(argv: list[str] | None = None) -> int:
    import torch

    from svg_training.nus.deploy import apply_overrides, load_deploy
    from svg_training.nus.method_cfg import LOCAL_METHOD, load_method
    from svg_training.nus.players import DEPLOY_REF
    from svg_training.nus.replica_train import NusTrainEnv
    from svg_training.nus.rules import LOCAL_RULES, load_rules
    from svg_training.nus.selfplay import SelfPlay

    settings = tomllib.loads(CONFIG.read_text())
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--variant", required=True, choices=tuple(STAGE))
    parser.add_argument("--out", type=Path, help="default runs/nus_port/phase5/<stage>/seed<seed>")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--probe-only", action="store_true")
    parser.add_argument("--probe-updates", type=int, default=int(settings["caps"]["probe_updates"]))
    parser.add_argument("--accept-long", action="store_true")
    parser.add_argument("--gpu-hours-log", type=Path, help="default runs/nus_port/phase5/<cap group>/gpu_hours.log")
    parser.add_argument("--video-format", choices=("mp4", "gif", "none"), default=str(settings["videos"]["format"]))
    parser.add_argument("--rules", type=Path, default=LOCAL_RULES)
    parser.add_argument("--deploy", type=Path, default=DEPLOY_REF)
    parser.add_argument("--method", type=Path, default=LOCAL_METHOD)
    parser.add_argument("--generations", type=int, help="tests only: fewer generations (not of record)")
    parser.add_argument("--log-note", help="a note on this run's gpu_hours.log rows (e.g. smoke)")
    parser.add_argument("--pauses-log", type=Path, help="default runs/nus_port/phase5/pauses.log (scripts/gpu_pause.sh)")
    parser.add_argument("--memory-fraction", type=float, help="CUDA only: torch.cuda.set_per_process_memory_fraction for side-by-side processes")
    args = parser.parse_args(argv)

    out = _under_runs(args.out or STAGE_DIR / STAGE[args.variant] / f"seed{args.seed}")
    group = CAP_GROUP[args.variant]
    log = _under_runs(args.gpu_hours_log or STAGE_DIR / group / "gpu_hours.log")
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise SystemExit("--device cuda but no CUDA device")
    if args.memory_fraction is not None:
        if device.type != "cuda":
            raise SystemExit("--memory-fraction applies to --device cuda only")
        apply_memory_fraction(args.memory_fraction, device)
    gates = tomllib.loads(GATES.read_text())["gates"]
    deploy = load_deploy(args.deploy)
    method = load_method(args.method)
    frozen = int(gates["phase5_method_match"]["generations"])
    generations = args.generations or frozen
    if args.generations is None and method.generations != frozen:
        raise SystemExit("the method file's generations differ from the frozen gate's")
    env = NusTrainEnv(apply_overrides(load_rules(args.rules), deploy), deploy, method, device=device)
    shape = batch_shape(args.variant, method, env.episode_steps, gates)
    out.mkdir(parents=True, exist_ok=True)

    from svg_training.nus.pauses import PAUSES_LOG
    pauses = args.pauses_log or PAUSES_LOG
    remaining = float(settings["caps"][group]) - logged_hours(log, group, pauses)
    if args.probe_updates > 0 and not (out / "self_play_state.json").exists():
        began = time.time()
        result = probe(method, env, args.seed, shape, out, args.probe_updates, generations, device)
        append_log(log, {"group": group, "stage": STAGE[args.variant], "seed": args.seed, "what": "probe", "note": args.log_note, "device": str(device),
                         "start": began, "end": time.time()})
        result |= {"cap_group": group, "remaining_cap_hours": remaining, "within_cap": result["estimate_hours"] <= remaining}
        (out / "probe.json").write_text(json.dumps(result, indent=2) + "\n")
        print(f"[probe] {result['seconds_per_update']:.3f} s per update at {result['games_per_update']} games; estimate "
              f"{result['estimate_hours']:.2f} h against {remaining:.2f} h left of the {group} cap", flush=True)
        if args.probe_only:
            return 0
        if not result["within_cap"] and not args.accept_long:
            print("[probe] the estimate is above the remaining cap: refusing to start (--accept-long overrides)", flush=True)
            return EXIT_REFUSED
        remaining = float(settings["caps"][group]) - logged_hours(log, group, pauses)
    elif args.probe_only:
        raise SystemExit("--probe-only needs --probe-updates above 0 and a fresh run folder")

    videos = Videos(out / "videos", args.video_format, int(settings["videos"]["games_searched"]))
    sp = SelfPlay(method, env, args.seed, out, device=device, generations=generations, on_selection=videos.on_selection,
                  on_archive=videos.on_archive, **_kw(shape))
    import signal
    previous_handler = install_stop_handler(sp)
    began_wall, began = time.time(), time.monotonic()
    should_stop = (lambda: cap_reached(began_wall, remaining, pauses)) if device.type == "cuda" else None  # pause-aware hard cap
    from svg_training.nus.mappo import NonFiniteError
    try:
        sp.run(should_stop=should_stop)
    except NonFiniteError as exc:   # 5.1-a counts non-finite aborts (nus_phase5_score.py reads status.json)
        (out / "status.json").write_text(json.dumps({"status": "ABORTED: non-finite", "nonfinite_abort": True, "error": str(exc),
                                                     "archived": len(sp.state["archive"])}, indent=2) + "\n")
        raise
    finally:
        signal.signal(signal.SIGINT, previous_handler)
        append_log(log, {"group": group, "stage": STAGE[args.variant], "seed": args.seed, "what": "train", "note": args.log_note, "device": str(device),
                         "start": began_wall, "end": time.time()})
    seconds = time.monotonic() - began
    status = {"cap": "ABORTED: hard wall-clock cap reached (paused time not counted)", "interrupted": "STOPPED on request (resume: "
              "the same command)", None: "complete"}[sp.stopped]
    inputs = {"rules": args.rules, "deploy": args.deploy, "method": args.method}
    (out / "status.json").write_text(json.dumps({"status": status, "nonfinite_abort": False, "archived": len(sp.state["archive"])},
                                                indent=2) + "\n")
    path = record_draft(out, args, shape, sp, seconds, videos.paths, status, inputs)
    print(f"[train] {status}; {len(sp.state['archive'])} generations archived; record draft {path}", flush=True)
    return {"cap": EXIT_ABORTED, "interrupted": EXIT_STOPPED, None: 0}[sp.stopped]


if __name__ == "__main__":
    raise SystemExit(main())
