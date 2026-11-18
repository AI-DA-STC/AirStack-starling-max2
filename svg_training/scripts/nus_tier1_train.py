"""Train one lineage of stage 5.2 (NUS port Phase 5, Task S4): our PyTorch copy of NUS's alternating best-response self-play
(``nus/selfplay.py``, ``nus/mappo.py``, unchanged apart from the environment) on the tier 1 hangar game (``nus/tier1_env.py``: Phase 4
row 5, the fitted Starling layer with the EXPLORATORY drone model, the all-pairs safety filter, 3-D, interface v0.2, one decision per
hold, run to the time-out). Conda ``env_isaaclab``; CUDA for runs of record, CPU for tests and the smoke:

    cd <svg_training>; unset PYTHONPATH; PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/nus_tier1_train.py \
        --seed 1001 --variant 5.1c --device cuda [--out runs/nus_port/phase5/s52/seed1001] [--filter-cuda-graph] [--probe-only]
    ... --smoke --device cpu                     # the CPU smoke of the whole path (not of record; [smoke] of the 5.2 settings)

What it does, in order:

1. **Batch shape** (plan P5-7): ``--variant`` ``nus`` (the copied method's), ``5.1b`` or ``5.1c`` (``[gates.phase5_method_variants]``:
   16,384 games per update, rounded up to equal blocks per slot, 47 or 16 updates per generation, the selection evaluations after the
   listed updates, the copied minibatch size in samples), by ``nus_selfplay_train.batch_shape``. 5.2 uses the cheapest variant whose 5.1
   verdict is PASS; this script does not choose it: a run of record names ``--variant`` and refuses to start while
   ``[gates.phase5_tier1_training]`` is not FROZEN (STANDARDS section 7: gates before a run). ``--smoke`` lifts both.
2. **Safety filter path**: the row's existing path (early stop) by default; ``--filter-cuda-graph`` turns on the opt-in fixed-shape CUDA
   graph path (``core/safety_filter_graph.py``: the fixed loop's answer bit for bit, which on CUDA differs from the early stop's rounding).
   ``run.json`` records which one; a resume with the other path is refused.
3. **Probe** (``--probe-updates``): updates of generation 1 and one selection evaluation in ``<out>/probe/``, timed; an ESTIMATE of the
   lineage in ``<out>/probe.json``; above the remaining cap a run refuses to start without ``--accept-long``.
4. **Cap** (plan section 8): ``[caps] training_gpu_hours`` of ``configs/nus_phase5_tier1.toml`` less the GPU-hours already in the stage's
   ``gpu_hours.log`` (group ``s52``; CUDA intervals, overlapping jobs counted once, paused time not counted). On CUDA the remaining cap is a
   pause-aware hard limit with a look-ahead of the longest update so far (with its selection evaluation): the run checkpoints and stops
   (exit 3, ABORTED) before an update that would pass it. Every run appends its interval to the log. SIGINT checkpoints at the next
   update boundary (exit 4, STOPPED); the same command resumes.
5. **Training curves** (STANDARDS section 7.2): one JSON line per update in ``<out>/train_log.jsonl`` from ``nus/tier1_metrics.training_row``.
6. **Videos inside the run** (STANDARDS section 8; owner: no separate re-record): the selection evaluation's own games are kept
   (``SelfPlay(record_games=...)``); one game per evaluation (against the slot the learner did worst against), and for each archived entry
   two games of its best evaluation against its strongest pool member (the first Strike win and the first hold). With ``deferred`` they are
   saved as data in ``<out>/videos/pending/`` and rendered off the clock by ``scripts/nus_render_pending.py``.
7. **interface.toml** (interface v0.2) beside every archived entry; **record draft** ``<out>/record_draft.md``.

Everything is written under runs/. Prints counts, rates and paths, never a partner value. No numeric literal other than 0, 1, -1, 2 (G2).
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import nus_selfplay_train as base  # noqa: E402  (batch shape, probe, cap and log helpers, recordings)

RUNS_ROOT = ROOT / "runs"   # tests patch it
STAGE_DIR = RUNS_ROOT / "nus_port" / "phase5" / "s52"
GATES = ROOT / "configs" / "nus_port.toml"
GROUP = "s52"
HOUR_S = base.HOUR_S
EXIT_REFUSED, EXIT_ABORTED, EXIT_STOPPED = base.EXIT_REFUSED, base.EXIT_ABORTED, base.EXIT_STOPPED
RUN_KEYS = ("seed", "variant", "shape", "filter_path", "critic_reached_flag", "interface_version", "not_of_record", "method_sha256")


def _under_runs(path: Path) -> Path:
    resolved = Path(path).resolve()
    if RUNS_ROOT.resolve() not in (resolved, *resolved.parents):
        raise SystemExit(f"refusing: {resolved} is outside runs/")
    return resolved


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _git_head() -> str:
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


# ------------------------------------------------------------------------------------------------ videos
def clip_of(recording: dict, slot: int, game: int, guards: int) -> dict:
    """One kept game of a selection evaluation as a Phase 4 clip dict (host tensors, metres): up to its first reach, or the whole game."""
    import torch
    from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
    frames = recording["frames"][:, slot, game]
    first = int(recording["first_tick"][slot, game])
    end = first if first >= 0 else frames.shape[0] - 1
    pos = frames[: end + 1]
    xy = pos[..., :2]
    closest = float(torch.cdist(xy[:, :guards], xy[:, guards:]).min())
    return {"slot": game, "kind": "strike_win" if first >= 0 else "hold", "outcome": STRIKE_WIN if first >= 0 else GUARD_WIN,
            "end_step": end, "closest_cross_m": closest, "pos_m": pos.clone()}


class Tier1Videos:
    """The video hooks of ``SelfPlay`` for the hangar game (module docstring, step 6) and the interface file of each archived entry."""

    def __init__(self, out: Path, kind: str, world, method, seed: int):
        self.out, self.kind, self.world, self.method, self.seed, self.paths = out, kind, world, method, int(seed), []

    def _names(self, sp, slot: int, team: str) -> tuple[str, str]:
        opponents = sp.state["active"]["opponents"]
        other = f"generation {opponents[slot]['generation']}" if slot < len(opponents) else "scripted APF"
        ours = f"trained g{sp.state['active']['generation']}"
        return (ours, other) if team == "guard" else (other, ours)

    def _recording(self, clip: dict, names: tuple[str, str]):
        from svg_training.nus import ladder
        w = self.world
        return ladder.clip_recording(clip, w.geo, w.guards, w.strikes, names[0], names[1], "hangar row 5, tier 1 (training simulator)",
                                     self.seed)

    def _emit(self, recording, name: str) -> None:
        if self.kind == "none":
            return
        if self.kind == "deferred":
            self.paths.append(str(base.save_recording(recording, self.out / "pending" / f"{name}.npz")))
            return
        from make_replay import FORMATS
        from svg_training.viz.replay import render_replay
        self.paths.append(str(render_replay(recording, self.out / f"{name}.{self.kind}", playback_label="tier 1", **FORMATS[self.kind])))

    def _best_dir(self, active: dict) -> Path:
        return self.out.parent / "generations" / f"{active['generation']:04d}_{active['team']}" / "best_clips"

    def on_selection(self, sp, result: dict) -> None:
        rec = sp.last_recording
        if rec is None:
            return
        active = sp.state["active"]
        rates = result["win_rates"]
        slot = min(range(len(rates)), key=lambda i: rates[i])
        names = self._names(sp, slot, active["team"])
        self._emit(self._recording(clip_of(rec, slot, 0, self.world.guards), names),
                   f"g{active['generation']:02d}_{active['team']}_update{active['update']:05d}")
        if active["best_rank"] is None or tuple(result["rank"]) > tuple(active["best_rank"]):   # this evaluation becomes the best
            folder = self._best_dir(active)
            shutil.rmtree(folder, ignore_errors=True)
            clips = [clip_of(rec, slot, j, self.world.guards) for j in range(rec["frames"].shape[2])]
            picks = [next((c for c in clips if c["kind"] == kind), None) for kind in ("strike_win", "hold")]
            picks = [c for c in picks if c is not None]
            used = {c["slot"] for c in picks}
            picks += [c for c in clips if c["slot"] not in used][: max(2 - len(picks), 0)]
            for c in picks:
                base.save_recording(self._recording(c, names), folder / f"game{c['slot']:02d}.npz")

    def on_archive(self, sp, entry: dict) -> None:
        active = sp.state["active"]
        folder = self._best_dir(active)
        for data in sorted(folder.glob("*.npz")):
            name = f"archive_g{entry['generation']:02d}_{entry['team']}_{data.stem}"
            if self.kind == "deferred":
                target = self.out / "pending" / f"{name}.npz"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(data, target)
                self.paths.append(str(target))
            elif self.kind != "none":
                self._emit(base.load_recording(data), name)
        self.write_interface(entry)

    def write_interface(self, entry: dict) -> None:
        from svg_training.nus.tier1_interface import build_tier1_interface, write_tier1_interface
        commit = _git_head()
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            return   # no git commit to name (a copy outside the repository): no interface file, the record says so
        w = self.world
        folder = Path(entry["path"])
        data = build_tier1_interface(team=entry["team"], cfg=w.cfg, guards=w.guards, strikes=w.strikes, decision_ticks=w.geo.hold_ticks,
                                     game_config=w.game_file, game_config_sha256=w.local_sha256["game_config"],
                                     params_sha256=w.local_sha256["drone_model_params"], local_sha256=w.local_sha256,
                                     compute_dtype=self.method.compute_dtype, source_commit=commit, seed=self.seed,
                                     generation=entry["generation"], checkpoint_sha256=_sha(folder / "actor.pt"))
        write_tier1_interface(folder / "interface.toml", data)


# ------------------------------------------------------------------------------------------------ record
def record_draft(out: Path, run: dict, sp, seconds: float, videos: list[str], status: str, inputs: dict, peak: dict) -> Path:
    commit = _git_head()
    dirty = bool(subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", "."], capture_output=True, text=True).stdout.strip())
    archive = sp.state["archive"]
    games = sum(json.loads((Path(e["path"]) / "metadata.json").read_text())["games_per_update"] for e in archive) * sp.updates
    ticks = games * sp.env.episode_steps * sp.env.hold
    head = "NOT OF RECORD (smoke)" if run["not_of_record"] else status
    lines = [f"# NUS port Phase 5, stage 5.2, seed {run['seed']}: training simulator, tier 1 (hangar game of Phase 4 row 5), record draft "
             f"({head})", "",
             "Observed in the training simulator, tier 1: the fitted Starling layer with the EXPLORATORY drone model (T5 = FAIL: it answers "
             "more slowly than the real drone), the all-pairs safety filter, 3-D. Nothing here is a flight result.", "",
             f"- Purpose: plan section 5, stage 5.2, our copy of NUS's alternating best-response self-play, variant `{run['variant']}`.",
             f"- Commit: `{commit}`{' plus uncommitted changes' if dirty else ''}.",
             "- Local files (sha256): " + ", ".join(f"`{k}` {v}" for k, v in sorted(inputs.items())) + ".",
             f"- Seed {run['seed']}; stage seeds seed + generation - 1. Machine `{platform.node()}`, device `{run['device']}`.",
             f"- Batch shape: {json.dumps(run['shape']) if run['shape'] else 'the copied method'}; drones per game {sp.env.num_actors}; "
             f"one decision per hold ({sp.env.hold} ticks); tier 1.",
             f"- Safety filter path: {run['filter_path']}.",
             f"- Observation: policy interface {run['interface_version']}; critic state: build_state plus the slot one-hot"
             f"{' plus the reached flag' if run['critic_reached_flag'] else ''}.",
             f"- Wall clock {seconds / HOUR_S:.3f} h; game-steps (ticks x games) per second over the training updates, ESTIMATE: "
             f"{ticks / max(seconds, 1):.0f}. Peak GPU memory: {json.dumps(peak)}.",
             "", "| Generation | Team | Games per update | Best update | Rank (geometric, worst, mean) |", "|---|---|---|---|---|"]
    for e in archive:
        meta = json.loads((Path(e["path"]) / "metadata.json").read_text())
        lines.append(f"| {e['generation']} | {e['team']} | {meta['games_per_update']} | {meta['best_update']} | {meta['best_rank']} |")
    lines += ["", "Training curves: `train_log.jsonl` (nus/tier1_metrics.training_row).", "", "Videos:"]
    lines += [f"- `{p}`" for p in videos] + ([] if videos else ["- none (state why)"])
    lines += ["", "Gates: none at training time; the gated checkpoints are scored by `scripts/nus_phase5_eval.py --stage 5.2`."]
    path = out / "record_draft.md"
    path.write_text("\n".join(lines) + "\n")
    return path


# ------------------------------------------------------------------------------------------------ main
def make_parser(settings: dict) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--variant", choices=tuple(base.STAGE), help="required for a run of record: the variant 5.1b / 5.1c chose (plan P5-7)")
    p.add_argument("--out", type=Path, help="default runs/nus_port/phase5/s52/seed<seed>")
    p.add_argument("--device", default="cpu")
    p.add_argument("--filter-cuda-graph", action="store_true", help="opt-in CUDA-graph safety filter (default off)")
    p.add_argument("--probe-only", action="store_true")
    p.add_argument("--probe-updates", type=int, default=int(settings["caps"]["probe_updates"]))
    p.add_argument("--accept-long", action="store_true")
    p.add_argument("--gpu-hours-log", type=Path, help="default runs/nus_port/phase5/s52/gpu_hours.log")
    p.add_argument("--pauses-log", type=Path, help="default runs/nus_port/phase5/pauses.log (scripts/gpu_pause.sh)")
    p.add_argument("--video-format", choices=("mp4", "gif", "deferred", "none"), default=str(settings["videos"]["format"]))
    p.add_argument("--method", type=Path, help="default configs/local/nus_method.toml")
    p.add_argument("--memory-fraction", type=float, help="CUDA only: torch.cuda.set_per_process_memory_fraction (side-by-side processes)")
    p.add_argument("--smoke", action="store_true", help="the [smoke] counts of configs/nus_phase5_tier1.toml: NOT OF RECORD")
    p.add_argument("--log-note")
    return p


def main(argv: list[str] | None = None) -> int:
    import torch

    from svg_training.nus import tier1_metrics as M
    from svg_training.nus.method_cfg import LOCAL_METHOD, load_method
    from svg_training.nus.pauses import PAUSES_LOG
    from svg_training.nus.selfplay import SelfPlay
    from svg_training.nus.tier1_env import NusTier1Env, load_tier1, tier1_world

    settings = load_tier1()
    args = make_parser(settings).parse_args(argv)
    out = _under_runs(args.out or STAGE_DIR / f"seed{args.seed}")
    log = _under_runs(args.gpu_hours_log or STAGE_DIR / "gpu_hours.log")
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise SystemExit("--device cuda but no CUDA device")
    if args.filter_cuda_graph and device.type != "cuda":
        print("[train] note: --filter-cuda-graph on the CPU runs the same blocks eagerly (no graph)", flush=True)
    if args.memory_fraction is not None:
        if device.type != "cuda":
            raise SystemExit("--memory-fraction applies to --device cuda only")
        base.apply_memory_fraction(args.memory_fraction, device)
    gates = tomllib.loads(GATES.read_text())["gates"]
    table = gates["phase5_tier1_training"]
    if not args.smoke:
        if args.variant is None:
            raise SystemExit("refusing: a run of record names its --variant (the cheapest 5.1 variant that PASSED; plan P5-7)")
        if not str(table.get("status", "")).startswith("FROZEN"):
            print(f"refusing: [gates.phase5_tier1_training] is {table.get('status')!r}, not FROZEN (gates are written before a run, "
                  "STANDARDS section 7)", file=sys.stderr)
            return EXIT_REFUSED
    args.variant = args.variant or "5.1c"   # the smoke overrides the shape anyway
    method_path = args.method or LOCAL_METHOD
    method = load_method(method_path)
    smoke = settings["smoke"] if args.smoke else None
    if smoke:
        method = dataclasses.replace(method, selection_games_per_opponent=int(smoke["selection_games_per_opponent"]))
    world = tier1_world(filter_cuda_graph=args.filter_cuda_graph)
    env = NusTier1Env(world, method, device=device, seed=args.seed)
    shape = base.batch_shape(args.variant, method, env.episode_steps, gates)
    generations = int(table["generations"])
    if smoke:
        updates = int(smoke["updates_per_generation"])
        shape = {**shape, "games_per_update": int(smoke["games_per_update"]), "updates_per_generation": updates,
                 "selection_after": (updates,)}
        shape.pop("minibatches", None)
        shape.pop("drop_remainder", None)
        generations = int(smoke["generations"])
    elif args.seed not in [int(s) for s in table["seeds"]]:
        raise SystemExit(f"seed {args.seed} is not one of the stage's seeds {table['seeds']} (plan P5-12)")
    run = {"seed": args.seed, "variant": args.variant, "shape": {k: list(v) if isinstance(v, tuple) else v for k, v in shape.items()},
           "filter_path": world.filter_path, "critic_reached_flag": env.critic_reached_flag, "interface_version": "0.2",
           "not_of_record": bool(smoke), "device": str(device), "generations": generations, "method_sha256": _sha(method_path)}
    out.mkdir(parents=True, exist_ok=True)
    run_file = out / "run.json"
    if run_file.exists():
        before = json.loads(run_file.read_text())
        differ = [k for k in RUN_KEYS if before.get(k) != run[k]]
        if differ:
            print(f"refusing to resume: {differ} differ from {run_file}", file=sys.stderr)
            return EXIT_REFUSED
    run_file.write_text(json.dumps(run, indent=2) + "\n")
    inputs = {**world.local_sha256, "method": _sha(method_path)}

    pauses = args.pauses_log or PAUSES_LOG
    cap = float(settings["caps"]["training_gpu_hours"])
    remaining = cap - base.logged_hours(log, GROUP, pauses)
    kw = base._kw(shape)
    if args.probe_updates > 0 and not (out / "self_play_state.json").exists():
        began = time.time()
        result = base.probe(method, env, args.seed, shape, out, args.probe_updates, generations, device)
        base.append_log(log, {"group": GROUP, "stage": GROUP, "seed": args.seed, "what": "probe", "note": args.log_note, "device": str(device),
                              "start": began, "end": time.time()})
        result |= {"cap_group": GROUP, "remaining_cap_hours": remaining, "within_cap": result["estimate_hours"] <= remaining,
                   "filter_path": world.filter_path, "not_of_record": bool(smoke)}
        (out / "probe.json").write_text(json.dumps(result, indent=2) + "\n")
        print(f"[probe] {result['seconds_per_update']:.3f} s per update at {result['games_per_update']} games; estimate "
              f"{result['estimate_hours']:.2f} h against {remaining:.2f} h left of the {GROUP} cap", flush=True)
        if args.probe_only:
            return 0
        if not result["within_cap"] and not args.accept_long:
            print("[probe] the estimate is above the remaining cap: refusing to start (--accept-long overrides)", flush=True)
            return EXIT_REFUSED
        remaining = cap - base.logged_hours(log, GROUP, pauses)
    elif args.probe_only:
        raise SystemExit("--probe-only needs --probe-updates above 0 and a fresh run folder")

    videos = Tier1Videos(out / "videos", args.video_format, world, method, args.seed)
    train_log = out / "train_log.jsonl"

    span = {"last": time.time(), "longest_s": 0.0}   # the longest update (with its selection evaluation): the cap's look-ahead

    def on_update(sp, metrics: dict) -> None:
        now = time.time()
        span["longest_s"], span["last"] = max(span["longest_s"], now - span["last"]), now
        active = sp.state["active"]
        row = M.training_row(metrics, sp.env.counters(), active["team"]) | {"generation": active["generation"], "update": active["update"],
                                                                            "time": time.time()}
        with train_log.open("a") as stream:
            stream.write(json.dumps(row) + "\n")

    sp = SelfPlay(method, env, args.seed, out, device=device, generations=generations, on_selection=videos.on_selection,
                  on_archive=videos.on_archive, on_update=on_update, record_games=int(settings["videos"]["games_searched"]), **kw)
    (out / "status.json").unlink(missing_ok=True)
    previous = base.install_stop_handler(sp)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    began_wall, began = time.time(), time.monotonic()
    # pause-aware hard cap with a look-ahead: stop when the next update (a whole game, plus a selection evaluation) would pass the cap
    span["last"] = began_wall
    should_stop = ((lambda: base.cap_reached(began_wall, remaining - span["longest_s"] / HOUR_S, pauses))
                   if device.type == "cuda" else None)
    from svg_training.nus.mappo import NonFiniteError
    try:
        sp.run(should_stop=should_stop)
    except NonFiniteError as exc:
        (out / "status.json").write_text(json.dumps({"status": "ABORTED: non-finite", "nonfinite_abort": True, "error": str(exc),
                                                     "archived": len(sp.state["archive"])}, indent=2) + "\n")
        raise
    finally:
        signal.signal(signal.SIGINT, previous)
        base.append_log(log, {"group": GROUP, "stage": GROUP, "seed": args.seed, "what": "train", "note": args.log_note, "device": str(device),
                              "start": began_wall, "end": time.time()})
    seconds = time.monotonic() - began
    gib = float(2 ** (2 * 2 * 2 + 2 * 2 * 2 + 2 * 2 * 2 + 2 * 2 + 2))
    peak = ({"allocated_gib": torch.cuda.max_memory_allocated() / gib, "reserved_gib": torch.cuda.max_memory_reserved() / gib}
            if device.type == "cuda" else {"allocated_gib": None, "reserved_gib": None})
    status = {"cap": "ABORTED: hard wall-clock cap reached (paused time not counted)", "interrupted": "STOPPED on request (resume: the "
              "same command)", None: "complete"}[sp.stopped]
    (out / "status.json").write_text(json.dumps({"status": status, "nonfinite_abort": False, "archived": len(sp.state["archive"]),
                                                 "not_of_record": bool(smoke)}, indent=2) + "\n")
    path = record_draft(out, run, sp, seconds, videos.paths, status, inputs, peak)
    print(f"[train] {status}; {len(sp.state['archive'])} generations archived; record draft {path}", flush=True)
    return {"cap": EXIT_ABORTED, "interrupted": EXIT_STOPPED, None: 0}[sp.stopped]


if __name__ == "__main__":
    raise SystemExit(main())
