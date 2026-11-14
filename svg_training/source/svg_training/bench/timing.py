"""Timing harness for the S0 throughput benchmark (both tiers).

`measure` times a step function; `run_case` builds the environment, measures it per repeat and returns result rows.
Throughput is environment steps per second (games x policy steps per second), drone-steps per second beside it.
"""
import datetime
import gc
import json
import math
import os
import pathlib
import subprocess
import time
from typing import Any, Callable

import torch

from svg_training.bench.rows import ROW_KEYS, code_sha, existing_points  # noqa: F401

ROOT = pathlib.Path(__file__).resolve().parents[3]  # svg_training/

# ROW_KEYS and existing_points live in rows.py (standard library only) and are re-exported here.



def _is_cuda(device: str) -> bool:
    return str(device).startswith("cuda")


def _idx(device: str) -> int:
    return torch.device(device).index or 0


def measure(step_fn: Callable[[], "dict | None"], warmup_steps: int, timed_steps: int, device: str,
            min_warmup_s: float = 2.0, min_timed_s: float = 0.0) -> dict:
    """Run the warm-up untimed, then time n calls of step_fn, n = timed_steps or more.

    The warm-up is at least warmup_steps steps AND at least min_warmup_s seconds (a cold GPU needs time to reach
    its clocks; 50 steps can last 25 ms). Its elapsed time is checked after a synchronise, and all of it happens
    before the clock starts. min_warmup_s=0 turns the time condition off.

    The timed window is at least timed_steps steps AND at least min_timed_s seconds. The number of timed steps n is
    decided before the clock starts, from the warm-up's own rate (warm-up steps run / warm-up seconds, read after a
    synchronise): n = max(timed_steps, ceil(min_timed_s * rate * 1.1)). min_timed_s=0 gives n = timed_steps exactly.
    The timed loop itself has no extra synchronise.

    The timed section includes a per-step finiteness check of every floating-point output (a training loop
    guards against NaN too), so the throughput reported contains that cost.
    The timed loop forces no host-device sync: the per-step non-finite flag and reset_fraction stay on the device
    as tensors and are read once after the clock stops. nan_count = timed steps in which any floating-point
    tensor of the returned dict has a NaN or infinity (a step returning None counts 0).
    Returns steps_per_s (n / elapsed), nan_count, mean_reset_fraction, peak_mem_mb (0 on CPU), timed_steps (the n
    actually run) and timed_s (elapsed seconds of the timed window).
    """
    cuda = _is_cuda(device)
    idx = _idx(device) if cuda else 0
    if cuda:
        torch.cuda.reset_peak_memory_stats(idx)
    need_rate = min_timed_s > 0
    w0 = time.perf_counter() if (min_warmup_s > 0 or need_rate) else 0.0
    warm_done = warmup_steps
    for _ in range(warmup_steps):
        step_fn()
    w1 = None
    if min_warmup_s > 0:
        while True:
            if cuda:
                torch.cuda.synchronize(idx)
            w1 = time.perf_counter()
            if w1 - w0 >= min_warmup_s:
                break
            extra = max(1, warmup_steps // 5)
            for _ in range(extra):
                step_fn()
            warm_done += extra
    elif need_rate:
        if cuda:
            torch.cuda.synchronize(idx)
        w1 = time.perf_counter()
    n = timed_steps
    if need_rate and w1 is not None and w1 > w0 and warm_done > 0:
        n = max(timed_steps, math.ceil(min_timed_s * (warm_done / (w1 - w0)) * 1.1))
    flags, resets = [], []
    if cuda:
        torch.cuda.synchronize(idx)  # warm-up work must be finished before the clock starts
    t0 = time.perf_counter()
    for _ in range(n):
        out = step_fn()
        if out is None:
            continue
        bad = None
        for v in out.values():
            if isinstance(v, torch.Tensor) and v.is_floating_point():
                b = ~torch.isfinite(v).all()
                bad = b if bad is None else bad | b
        if bad is not None:
            flags.append(bad)
        if "reset_fraction" in out:
            resets.append(out["reset_fraction"].float())
    if cuda:
        torch.cuda.synchronize(idx)  # all timed work must be finished before the clock stops
    elapsed = time.perf_counter() - t0
    nan_count = int(torch.stack(flags).sum().item()) if flags else 0
    mean_reset = float(torch.stack(resets).mean().item()) if resets else 0.0
    peak_mb = torch.cuda.max_memory_allocated(idx) / 2**20 if cuda else 0
    return {"steps_per_s": n / elapsed, "nan_count": nan_count,
            "mean_reset_fraction": mean_reset, "peak_mem_mb": float(peak_mb),
            "timed_steps": int(n), "timed_s": float(elapsed)}


_commit = None
_code = None


def _code_sha() -> str:
    """code_sha() of this folder, computed once per process."""
    global _code
    if _code is None:
        _code = code_sha(ROOT)
    return _code


def git_commit() -> str:
    """Short hash of HEAD of the repository containing this folder (read-only); "unknown" if unavailable."""
    global _commit
    if _commit is None and os.environ.get("SVG_COMMIT"):  # set by docker/run.sh: the container has no .git
        _commit = os.environ["SVG_COMMIT"]
    if _commit is None:
        try:
            res = subprocess.run(["git", "-C", str(ROOT.parent), "rev-parse", "--short", "HEAD"],
                                 capture_output=True, text=True, check=True, timeout=20)
            _commit = res.stdout.strip() or "unknown"
        except (OSError, subprocess.SubprocessError):
            _commit = "unknown"
    return _commit


def gpu_name(device: str) -> str:
    return torch.cuda.get_device_name(_idx(device)) if _is_cuda(device) else "cpu"


def _release(device: str) -> None:
    gc.collect()
    if _is_cuda(device):
        with torch.cuda.device(_idx(device)):
            torch.cuda.empty_cache()


def run_case(make_env: Callable[[], Any], step_of: Callable[[Any], Callable], case: dict, num_games: int,
             timing: dict, device: str, min_warmup_s: float = 2.0) -> list:
    """One row per repeat; the environment is built afresh per repeat, so each repeat pays its own warm-up.

    An out-of-memory error while building or stepping gives exactly one row with status "oom", repeat 0 and None
    for the measured fields. Any other exception gives exactly one row with status "crash" (repeat 0, None for the
    measured fields, key "error" = exception class and message), so one bad point does not end a sweep.
    min_warmup_s and timing["min_timed_s"] (default 0) are passed to `measure`; rows also carry timed_steps and timed_s.
    """
    if "guards" in case and "strikes" in case:
        drones = case["guards"] + case["strikes"]
    else:
        drones = case["drones_per_game"]
    base = {"tier": case.get("tier", 1), "case": case["name"], "num_games": num_games, "drones_per_game": drones,
            "device": device, "gpu_name": gpu_name(device), "commit": git_commit(),
            "code_sha": _code_sha(), "date": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
    rows, env, step, oom, crash = [], None, None, False, None
    try:
        for repeat in range(timing["repeats"]):
            env = make_env()
            step = step_of(env)
            r = measure(step, timing["warmup_steps"], timing["timed_steps"], device, min_warmup_s,
                        timing.get("min_timed_s", 0.0))
            env = step = None
            _release(device)
            env_sps = r["steps_per_s"] * num_games
            rows.append({**base, "repeat": repeat, "status": "ok", "env_steps_per_s": env_sps,
                         "drone_steps_per_s": env_sps * drones, "peak_mem_mb": r["peak_mem_mb"],
                         "nan_count": r["nan_count"], "mean_reset_fraction": r["mean_reset_fraction"],
                         "timed_steps": r["timed_steps"], "timed_s": r["timed_s"]})
    except torch.OutOfMemoryError:
        oom = True
    except Exception as e:  # noqa: BLE001 - one bad point must not end the sweep
        crash = f"{type(e).__name__}: {e}"[:300]
    if oom:  # outside the except block, so the traceback no longer keeps the environment alive
        env = step = None
        _release(device)
        return [{**base, "repeat": 0, "status": "oom", "env_steps_per_s": None, "drone_steps_per_s": None,
                 "peak_mem_mb": None, "nan_count": None, "mean_reset_fraction": None,
                 "timed_steps": None, "timed_s": None}]
    if crash is not None:  # outside the except block for the same reason
        env = step = None
        _release(device)
        return [{**base, "repeat": 0, "status": "crash", "env_steps_per_s": None, "drone_steps_per_s": None,
                 "peak_mem_mb": None, "nan_count": None, "mean_reset_fraction": None,
                 "timed_steps": None, "timed_s": None, "error": crash}]
    return rows
