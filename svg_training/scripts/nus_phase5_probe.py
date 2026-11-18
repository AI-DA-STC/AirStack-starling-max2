"""Phase 5 pilot P0: throughput probe of the hangar game (plan docs/plans/2026-11-18-nus-phase5-retraining.md section 7, Task P-T1). INFO, no gates.

    cd <svg_training>; unset PYTHONPATH; PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/nus_phase5_probe.py \
        --games 1000,4096,16384,32768 --out runs/nus_port/phase5/p0/

Builds ``NusHangarGame`` with Phase 4 row 5's settings (``hangar.hangar_cfg`` + ``configs/nus_phase4.toml`` row "5": fitted Starling layer,
all-pairs safety filter on, 3-D, start-height jitter) and, for each arm (``parked_s20``: ParkedGuard v S20; ``random``: both teams uniform random
actions) and each game count in ascending order, plays the settings' warm-up ticks untimed, then times the settings' timed ticks
(``torch.cuda.synchronize`` on both sides). An arm stops at the first count that runs out of GPU memory (recorded, memory freed). Starts are drawn
in memory for every count with the Phase 4 starts rule (``NusReplica.reset(random_start=True)`` plus the ladder's start-height jitter), seeded;
nothing is read from or written to the Phase 4 starts file.

Output (``--out``, under ``runs/`` only; git-ignored): ``gates.toml`` (written first: ``gates = []``), ``probe.json`` rewritten after every
measurement (a killed run still leaves what it measured), and ``profile.txt`` (the profiler's table of the one profiled tick). ``probe.json``
holds per arm and count: seconds per tick, game-steps/s, drone-steps/s, peak GPU memory (bytes, allocated and reserved), the share of the
timed wall clock spent in the safety filter, and the pilots' game count by the plan's rule (``pilot_rule``, applied to every arm; the count
is the ``pilot_arm``'s, ``parked_s20`` by the lead's decision of 18 Nov 2026; the random arm is INFO), and the gatekeeper's side-by-side reading (18 Nov 2026: three seeds side by side only if seconds per tick at
``side_by_side_games`` is at most ``side_by_side_ratio`` x the value at ``side_by_side_ref_games``). ``--extend`` adds larger counts to an
existing ``probe.json`` with the same device, arms, ticks and seed (earlier entries are kept; an arm that already stopped is not extended). Filter share: the filter call is wrapped on the game's command chain (as ``NusHangarGame._wrap_filter`` does) with
``torch.cuda.synchronize`` and ``time.perf_counter`` on both sides, inside the timed ticks; the filter syncs at its first sweep anyway (its
early-stop check), so the extra syncs cost little. INFO: one tick at ``profile_games`` games is run under ``torch.profiler`` and the filter's
sweeps (``aten::einsum``, once per sweep), early-stop checks (``aten::nonzero``, one host sync each) and CUDA kernel launches are counted.

Exit 0 = every arm ran (an out-of-memory stop included); 3 = the probe's own deadline (``budget_hours``) stopped it (the result is still
written); 2 = refused (``probe.json`` exists, no CUDA device for ``--device cuda``). Tier 1 (PyTorch; no Isaac Sim). No numeric literal (G2):
counts and times come from ``configs/nus_phase5.toml`` ``[probe]``, lengths and speeds from the local files through ``nus/hangar.py``.
All results are observed in the training simulator (tier 1: fitted Starling response with the safety filter).
"""
from __future__ import annotations

import argparse
import datetime
import gc
import json
import platform
import subprocess
import sys
import time
import tomllib
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))

PHASE5_CONFIG = ROOT / "configs" / "nus_phase5.toml"
DEFAULT_OUT = ROOT / "runs" / "nus_port" / "phase5" / "p0"
ARMS = ("parked_s20", "random")
EXIT_REFUSED, EXIT_STOP = 2, 2 + 1
HOUR_S = datetime.timedelta(hours=1).total_seconds()
US_S = datetime.timedelta(microseconds=1).total_seconds()
FILTER_SCOPE = "svg_safety_filter"
SWEEP_OP, CHECK_OP = "aten::einsum", "aten::nonzero"
LAUNCH_OPS = ("cudaLaunchKernel", "cuLaunchKernel", "cudaLaunchKernelExC", "cuLaunchKernelEx")
SYNC_OPS = ("cudaStreamSynchronize", "cudaDeviceSynchronize", "cudaEventSynchronize", "cudaMemcpyAsync")
TIMING_METHOD = ("seconds per tick: time.perf_counter over the timed ticks with torch.cuda.synchronize before and after; filter share: the "
                 "game's command-chain filter call wrapped with torch.cuda.synchronize + time.perf_counter on both sides during the same timed "
                 "ticks, summed, divided by the timed wall clock")
GATES_TEXT = "# Phase 5 pilot P0 (throughput probe): INFO run, no gates (plan section 7). Written before the run.\ngates = []\n"


def load_probe(path: Path | str | None = None) -> dict:
    """The ``[probe]`` table of ``configs/nus_phase5.toml``."""
    return tomllib.loads(Path(path or PHASE5_CONFIG).read_text())["probe"]


# ------------------------------------------------------------------------------------------------ the pilots' game-count rule (plan P0)
def pilot_rule(entries: list[dict], ratio: float, max_games: int) -> dict:
    """The largest measured count whose seconds per tick is at most ``ratio`` x the smallest count's (``entries`` in ascending order; the first
    entry is the base and must have been measured), and at most ``max_games``. ``games`` is None when the base was not measured."""
    out = {"games": None, "base_games": None, "base_seconds_per_tick": None, "ratio": ratio, "max_games": max_games}
    if not entries or entries[0]["status"] != "ok":
        return out
    base = entries[0]["seconds_per_tick"]
    good = [e["games"] for e in entries if e["status"] == "ok" and e["seconds_per_tick"] <= ratio * base and e["games"] <= max_games]
    out.update(games=max(good) if good else None, base_games=entries[0]["games"], base_seconds_per_tick=base)
    return out


def pilot_choice(per_arm: dict[str, dict], arm: str) -> int | None:
    """The pilots' game count: the rule's result for ``arm`` only (lead, 18 Nov 2026: ``parked_s20``, the arm closest to pilot P1 with the
    filter fully loaded); the other arms are INFO. None when that arm has no result."""
    return per_arm[arm]["games"] if arm in per_arm else None


PILOT_DECISION = ("lead, 18 Nov 2026: the pilots' game count is set by the parked_s20 arm only (closest to pilot P1, a Guard learner v S20; "
                  "the filter fully loaded); the random arm is INFO, because its smallest-count base is artificially cheap (the filter's early "
                  "stop ends its sweeps once random drones spread apart), so its ratios understate what a count costs")


# ------------------------------------------------------------------------------------------------ profiler counts
def profile_counts(events) -> dict:
    """Counts from ``torch.profiler`` events (``prof.events()``) of one tick: filter calls (``FILTER_SCOPE`` ranges on the host), sweeps
    (``aten::einsum``, once per sweep of ``filter_velocities``), early-stop checks (``aten::nonzero``, one host sync each), CUDA kernel launches and
    host-sync calls inside the filter and in the whole tick, and GPU kernel time (seconds) starting inside the filter windows and in the tick."""
    from torch.autograd import DeviceType
    host = [e for e in events if e.device_type == DeviceType.CPU]
    # device-side events, without the filter range's own GPU annotation (it spans the whole call and is not a kernel)
    gpu = [e for e in events if e.device_type == DeviceType.CUDA and e.name != FILTER_SCOPE]
    scopes = [(e.time_range.start, e.time_range.end) for e in host if e.name == FILTER_SCOPE]

    def inside(e) -> bool:
        return any(lo <= e.time_range.start and e.time_range.end <= hi for lo, hi in scopes)

    def count(name_set, pool) -> int:
        return sum(e.name in name_set for e in pool)
    in_filter = [e for e in host if inside(e)]
    gpu_in = [e for e in gpu if any(lo <= e.time_range.start <= hi for lo, hi in scopes)]
    return {"filter_calls": len(scopes), "sweeps": count({SWEEP_OP}, in_filter), "early_stop_checks": count({CHECK_OP}, in_filter),
            "aten_ops_filter_incl_nested": sum(e.name.startswith("aten::") for e in in_filter),
            "kernel_launches_filter": count(set(LAUNCH_OPS), in_filter), "kernel_launches_tick": count(set(LAUNCH_OPS), host),
            "host_sync_calls_filter": count(set(SYNC_OPS), in_filter), "host_sync_calls_tick": count(set(SYNC_OPS), host),
            "gpu_kernel_seconds_filter": sum(e.time_range.elapsed_us() for e in gpu_in) * US_S,
            "gpu_kernel_seconds_tick": sum(e.time_range.elapsed_us() for e in gpu) * US_S}


# ------------------------------------------------------------------------------------------------ the world
def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _context(st: dict):
    """Everything a count needs, read from the local files at call time (tests point the modules at marker files)."""
    from svg_training.core.game_config import load_game_cfg
    from svg_training.nus import hangar as H
    from svg_training.nus import strategy as strategy_module
    from svg_training.nus.deploy import apply_overrides, load_deploy
    from svg_training.nus.rules import load_rules
    settings = H.load_phase4()
    base, _ = load_game_cfg(H.HANGAR_GAME, use_local=False)
    deploy = load_deploy(strategy_module.DEPLOY_PATH)
    rules = apply_overrides(load_rules(strategy_module.RULES_PATH), deploy)
    hangar = H.load_hangar(H.LOCAL_HANGAR)
    rows = {r["id"]: r for r in settings["row"]}
    row = rows[st["row"]]
    H.check_row(row)
    cfg = H.hangar_cfg(base, rules, deploy, hangar, row)
    return types.SimpleNamespace(settings=settings, rules=rules, deploy=deploy, hangar=hangar, row=row, cfg=cfg,
                                 geo=H.geometry(rules, deploy, hangar, base), guards=rules.guard_count, strikes=rules.strike_count)


def _starts(ctx, n: int, seed: int):
    """[n, M, 2] starts in partner units and [n, M] start-height jitter (m), with the Phase 4 starts rule (``ladder.make_starts``), in memory."""
    import torch

    from svg_training.nus.replica import NusReplica
    gen = torch.Generator().manual_seed(seed)
    start = NusReplica(ctx.rules).reset(n, generator=gen, random_start=True).pos
    jitter = (torch.rand(n, start.shape[1], generator=gen) * 2 - 1) * ctx.settings["ladder"]["jitter_m"]
    return start, jitter


class RandomPlayer:
    """Uniform random actions in [-1, 1] for every drone of one team, every tick, from a generator on the device (no host read)."""

    def __init__(self, team: str, device, seed: int):
        import torch
        self.team, self.name = team, "random"
        self.gen = torch.Generator(device=device).manual_seed(seed)

    def reset(self, games) -> None:
        """Stateless."""

    def act(self, obs):
        """obs [N, team, obs_dim] -> actions [N, team, ACTION_WIDTH]."""
        import torch

        from svg_training.nus.strategy import ACTION_WIDTH
        return torch.rand(obs.shape[0], obs.shape[1], ACTION_WIDTH, generator=self.gen, device=obs.device) * 2 - 1


def _players(ctx, st: dict, arm: str, n: int, device: str, seed: int):
    from svg_training.nus.players import make_player
    if arm == "parked_s20":
        return (make_player(st["guard"], "guard", ctx.cfg, n, device, seed),
                make_player(st["strike"], "strike", ctx.cfg, n, device, seed))
    if arm == "random":
        return RandomPlayer("guard", device, seed), RandomPlayer("strike", device, seed + 1)
    raise ValueError(f"unknown arm {arm!r}; known: {ARMS}")


class FilterTimer:
    """Wraps the command chain's ``_filter`` on the instance (as ``NusHangarGame._wrap_filter`` does; the filter itself is unchanged): synchronized
    wall clock per call, a call count, and a ``torch.profiler.record_function`` range named ``FILTER_SCOPE``."""

    def __init__(self, chain, cuda: bool):
        import torch
        self.seconds, self.calls, self._cuda, self._torch = 0.0, 0, cuda, torch
        if chain is None or not chain.safety_filter:
            raise ValueError("the probe needs a game with the safety filter on (row 5)")
        inner = chain._filter

        def timed(nominal, pos_m):
            self._sync()
            t0 = time.perf_counter()
            with torch.profiler.record_function(FILTER_SCOPE):
                out = inner(nominal, pos_m)
            self._sync()
            self.seconds += time.perf_counter() - t0
            self.calls += 1
            return out
        chain._filter = timed

    def _sync(self) -> None:
        if self._cuda:
            self._torch.cuda.synchronize()

    def zero(self) -> None:
        self.seconds, self.calls = 0.0, 0


def _measure(ctx, n: int, arm: str, st: dict, device: str, warmup: int, timed: int, seed: int, deadline: float, profile: bool):
    """One arm at one game count: build, warm up, time. Returns (entry, profile dict or None). Raises ``torch.cuda.OutOfMemoryError``."""
    import torch

    from svg_training.nus.hangar_game import NusHangarGame
    from svg_training.nus.players import parks_guard0
    cuda = torch.device(device).type == "cuda"
    sync = torch.cuda.synchronize if cuda else (lambda: None)
    if cuda:
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
    guard, strike = _players(ctx, st, arm, n, device, seed)
    start, jitter = _starts(ctx, n, seed)
    game = NusHangarGame(ctx.cfg, ctx.geo, ctx.row, start, jitter, ctx.guards, ctx.strikes, device=device, seed=seed,
                         parked=parks_guard0(guard), video_slots=0, rules=ctx.rules)
    timer = FilterTimer(game._chain(), cuda)
    obs = game.reset()
    every = torch.ones(n, dtype=torch.bool, device=device)
    guard.reset(every)
    strike.reset(every)

    def tick(obs):     # play_match's step: act once per team, step, reset the strategies of the games that ended (S20 keeps per-game state)
        out = game.step({"guard": guard.act(obs["guard"]), "strike": strike.act(obs["strike"])})
        guard.reset(out.done)
        strike.reset(out.done)
        return out.obs

    sync()
    t0 = time.perf_counter()
    for _ in range(warmup):
        obs = tick(obs)
    sync()
    warm_s = time.perf_counter() - t0
    entry = {"games": n, "arm": arm, "warmup_ticks": warmup, "warmup_seconds_per_tick": warm_s / warmup if warmup else None,
             "ticks_planned": timed}
    remaining = deadline - time.monotonic()
    fit = timed if not warmup or warm_s / warmup * timed <= remaining else int(remaining / (warm_s / warmup))
    if fit < 1:
        entry.update(status="budget", seconds_per_tick=None, note="the timed ticks would pass the probe's deadline (estimate from the warm-up)")
        return entry, None
    timer.zero()
    sync()
    t0 = time.perf_counter()
    for _ in range(fit):
        obs = tick(obs)
    sync()
    seconds = time.perf_counter() - t0
    m = ctx.guards + ctx.strikes
    entry.update(status="ok", ticks_timed=fit, short=fit < timed, seconds_timed=seconds, seconds_per_tick=seconds / fit,
                 game_steps_per_s=n * fit / seconds, drone_steps_per_s=n * fit * m / seconds,
                 filter_seconds=timer.seconds, filter_calls=timer.calls, filter_share=timer.seconds / seconds,
                 peak_gpu_bytes=int(torch.cuda.max_memory_allocated()) if cuda else None,
                 peak_gpu_reserved_bytes=int(torch.cuda.max_memory_reserved()) if cuda else None)
    prof_out = None
    if profile:
        activities = [torch.profiler.ProfilerActivity.CPU] + ([torch.profiler.ProfilerActivity.CUDA] if cuda else [])
        timer.zero()
        sync()
        with torch.profiler.profile(activities=activities) as prof:
            t0 = time.perf_counter()
            obs = tick(obs)
            sync()
            tick_s = time.perf_counter() - t0
        prof_out = {"games": n, "arm": arm, "filter_iterations": ctx.cfg.starling.filter_iterations,
                    "filter_check_every": ctx.cfg.starling.filter_check_every, **profile_counts(prof.events()),
                    "tick_seconds_under_profiler": tick_s, "filter_seconds_under_profiler": timer.seconds,
                    "table": prof.key_averages().table(sort_by="cuda_time_total" if cuda else "cpu_time_total", row_limit=st["profile_table_rows"])}
    return entry, prof_out


# ------------------------------------------------------------------------------------------------ the run
def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--games", help="comma list of game counts, ascending (default: the settings')")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--device", default="cuda")
    p.add_argument("--arms", help="comma list of arms (default: the settings')")
    p.add_argument("--warmup-ticks", type=int)
    p.add_argument("--timed-ticks", type=int)
    p.add_argument("--budget-hours", type=float)
    p.add_argument("--profile-games", type=int, help="game count whose one extra tick is profiled (0: none)")
    p.add_argument("--seed", type=int)
    p.add_argument("--extend", action="store_true",
                   help="add larger counts to an existing probe.json (same device, arms, ticks and seed; earlier entries are kept as they are)")
    return p


def _meta(ctx, st: dict, args, counts: list[int], arms: list[str], device: str) -> dict:
    import torch

    from svg_training.nus import hangar as H
    from svg_training.nus import players, strategy as strategy_module
    from svg_training.nus.rules import file_sha256
    sha = {"rules": file_sha256(strategy_module.RULES_PATH), "deploy_w2": file_sha256(strategy_module.DEPLOY_PATH),
           "deploy_ref": file_sha256(players.DEPLOY_REF), "hangar": file_sha256(H.LOCAL_HANGAR), "settings": file_sha256(PHASE5_CONFIG),
           "phase4": file_sha256(H.PHASE4_CONFIG), "game_config": file_sha256(H.HANGAR_GAME)}
    cuda = torch.device(device).type == "cuda"
    return {"purpose": "Phase 5 pilot P0 throughput probe (INFO, not of record)", "commit": _git_head(), "machine": platform.node(),
            "python": platform.python_version(), "torch": torch.__version__, "device": device,
            "gpu": torch.cuda.get_device_name(torch.device(device)) if cuda else None, "row": st["row"], "arms": arms, "games": counts,
            "warmup_ticks": args.warmup_ticks, "timed_ticks": args.timed_ticks, "seed": args.seed, "budget_hours": args.budget_hours,
            "drones_per_game": ctx.guards + ctx.strikes, "tier": "tier 1 (fitted Starling layer, all-pairs safety filter, 3-D)",
            "filter_iterations": ctx.cfg.starling.filter_iterations, "filter_check_every": ctx.cfg.starling.filter_check_every,
            "filter_timing_method": TIMING_METHOD, "sha256": sha, "date": datetime.datetime.now().isoformat(timespec="seconds")}


def side_by_side_rule(entries: list[dict], ref_games: int, games: int, ratio: float) -> dict:
    """The gatekeeper's rule for three seeds side by side (18 Nov 2026): seconds per tick at ``games`` (three seeds' games in one process) at
    most ``ratio`` x the value at ``ref_games`` (one seed). ``passes`` is None when either count was not measured."""
    spt = {e["games"]: e["seconds_per_tick"] for e in entries if e["status"] == "ok"}
    out = {"games": games, "ref_games": ref_games, "ratio": ratio, "seconds_per_tick_ratio": None, "passes": None}
    if games in spt and ref_games in spt:
        out.update(seconds_per_tick_ratio=spt[games] / spt[ref_games], passes=spt[games] <= ratio * spt[ref_games])
    return out


def main(argv: list[str] | None = None) -> int:
    import torch

    from svg_training.nus.outputs import require_under_runs
    args = make_parser().parse_args(argv)
    out = require_under_runs(args.out)
    st = load_probe()
    counts = [int(x) for x in args.games.split(",")] if args.games else list(st["games"])
    arms = args.arms.split(",") if args.arms else list(st["arms"])
    for name, key in (("warmup_ticks", "warmup_ticks"), ("timed_ticks", "timed_ticks"), ("budget_hours", "budget_hours"),
                      ("profile_games", "profile_games"), ("seed", "seed")):
        if getattr(args, name) is None:
            setattr(args, name, st[key])
    if counts != sorted(counts) or not counts or any(a not in ARMS for a in arms):
        print(f"refusing: counts must be ascending and arms among {ARMS}", file=sys.stderr)
        return EXIT_REFUSED
    have = (out / "probe.json").exists()
    if have != args.extend:
        print(f"refusing: {out / 'probe.json'} exists (a probe is never overwritten; --extend adds larger counts)" if have
              else f"refusing: --extend needs an existing {out / 'probe.json'}", file=sys.stderr)
        return EXIT_REFUSED
    device = args.device
    cuda = torch.device(device).type == "cuda"
    if cuda and not torch.cuda.is_available():
        print("refusing: --device cuda but no CUDA device", file=sys.stderr)
        return EXIT_REFUSED
    ctx = _context(st)
    if args.extend:
        result = json.loads((out / "probe.json").read_text())
        if result["meta"]["device"] != device or any(a not in result["arms"] for a in arms):
            print("refusing: --extend must use the probe's device and arms", file=sys.stderr)
            return EXIT_REFUSED
        for key in ("warmup_ticks", "timed_ticks", "seed"):     # the added counts are timed the same way as the others
            setattr(args, key, result["meta"][key])
        if any(result["arms"][a] and counts[0] <= result["arms"][a][-1]["games"] for a in arms):
            print("refusing: --extend adds only counts larger than every count already in the probe", file=sys.stderr)
            return EXIT_REFUSED
        result["meta"].setdefault("extensions", []).append({"games": counts, "arms": arms, "budget_hours": args.budget_hours, "commit": _git_head(),
                                                             "date": datetime.datetime.now().isoformat(timespec="seconds")})
        args.profile_games = 0
    else:
        out.mkdir(parents=True, exist_ok=True)
        (out / "gates.toml").write_text(GATES_TEXT)
        result = {"meta": _meta(ctx, st, args, counts, arms, device), "arms": {a: [] for a in arms}, "profile": None, "pilot": None}
    deadline = time.monotonic() + args.budget_hours * HOUR_S
    started = time.perf_counter()
    wall_before = result["meta"].get("wall_seconds") or 0.0

    def write(stopped: str | None = None) -> None:
        names = list(result["arms"])
        per_arm = {a: pilot_rule(result["arms"][a], st["pilot_ratio"], st["pilot_max_games"]) for a in names}
        result["pilot"] = {"games": pilot_choice(per_arm, st["pilot_arm"]), "arm": st["pilot_arm"], "per_arm": per_arm,
                           "rule": "largest count whose seconds per tick <= pilot_ratio x the smallest count's, at most pilot_max_games, "
                                   "in the pilot arm; the other arms are INFO", "decision": PILOT_DECISION}
        result["side_by_side"] = {a: side_by_side_rule(result["arms"][a], st["side_by_side_ref_games"], st["side_by_side_games"],
                                                       st["side_by_side_ratio"]) for a in names}
        result["meta"]["wall_seconds"] = wall_before + time.perf_counter() - started
        result["meta"]["stopped"] = stopped
        (out / "probe.json").write_text(json.dumps(result, indent=2) + "\n")

    write()
    stopped = None
    for arm in arms:
        entries = result["arms"][arm]
        if entries and entries[-1]["status"] != "ok":
            print(f"{arm}: the probe already stopped this arm ({entries[-1]['status']}); no larger count is tried", flush=True)
            continue
        previous = entries[-1] if entries else None
        for n in counts:
            remaining = deadline - time.monotonic()
            predicted = (previous["seconds_per_tick"] * n / previous["games"] * args.warmup_ticks) if previous else 0.0
            if remaining <= 0 or predicted > remaining:
                entries.append({"games": n, "arm": arm, "status": "budget", "seconds_per_tick": None,
                                "note": "the probe's deadline passed, or the warm-up alone would pass it (scaled from the previous count)"})
                stopped = "budget"
                break
            oom = None
            try:
                entry, prof = _measure(ctx, n, arm, st, device, args.warmup_ticks, args.timed_ticks, args.seed, deadline,
                                       profile=arm == arms[0] and n == args.profile_games)
            except torch.cuda.OutOfMemoryError as exc:
                oom = str(exc).splitlines()[0] if str(exc) else "CUDA out of memory"
            if oom is not None:      # free outside the except block (the traceback holds the frames' tensors)
                gc.collect()
                if cuda:
                    torch.cuda.empty_cache()
                entries.append({"games": n, "arm": arm, "status": "oom", "seconds_per_tick": None, "error": oom})
                print(f"{arm} {n} games: out of memory; the arm stops here", flush=True)
                write()
                break
            if prof is not None:
                (out / "profile.txt").write_text(prof.pop("table") + "\n")
                result["profile"] = prof
            entries.append(entry)
            if entry["status"] != "ok":
                stopped = "budget"
                write(stopped)
                break
            previous = entry
            print(f"{arm} {n} games: {entry['seconds_per_tick']:.4f} s/tick, {entry['game_steps_per_s']:.0f} game-steps/s, "
                  f"filter share {entry['filter_share']:.3f}, peak {entry['peak_gpu_bytes']} B", flush=True)
            write()
        if stopped:
            break
    write(stopped)
    print(f"wrote {out / 'probe.json'}: pilots' game count {result['pilot']['games']} ({stopped or 'complete'})", flush=True)
    return EXIT_STOP if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
