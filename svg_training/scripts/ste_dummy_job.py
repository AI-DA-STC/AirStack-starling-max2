#!/usr/bin/env python3
"""A tiny stand-in for a training job (STE learning track, task L0.7): it counts steps and does nothing else.

It exists to prove the trainer contract (``source/svg_training/ste/run_contract.py``) and to drill the launcher and
the waiter (``scripts/ste_job.py``) on the CPU before any GPU job exists; the track's real jobs copy its pattern.
Step ``i`` (1, 2, ...) waits ``--step-s`` seconds and adds ``i`` to a running total, so a lost or repeated step shows
in the total, which is ``steps * (steps + 1) / 2`` at the end. Pure Python: no PyTorch, no GPU, no Isaac.

    python scripts/ste_dummy_job.py --run-dir runs/<name> --steps 120 --step-s 1 --cap-s 600 --checkpoint-every 10

Run the same command again and it resumes from ``<run-dir>/checkpoint.latest``. Exit codes (``run_contract.py``):
0 done (``<run-dir>/result.json`` written), 2 refused to start (bad arguments, or another copy holds the run folder),
3 stopped at the cap ``--cap-s`` (effective seconds: wall clock less the owner's pauses), 4 interrupted (SIGINT or
SIGTERM: checkpoint, then exit), 5 a non-finite value (``--nan-at-step`` injects one; the last good checkpoint stays).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))

from svg_training.ste import atomic  # noqa: E402
from svg_training.ste.run_contract import (EXIT_DONE, EXIT_FOR_STOP, EXIT_NONFINITE, EXIT_REFUSED,  # noqa: E402
                                           NonFiniteError, RunBusyError, RunGuard)

RESULT_NAME = "result.json"


def say(text: str) -> None:
    print(f"[dummy] {text}", flush=True)


def parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-dir", type=Path, required=True, help="the run folder (checkpoint, result)")
    parser.add_argument("--steps", type=int, required=True, help="how many steps to count")
    parser.add_argument("--step-s", type=float, required=True, help="seconds each step waits")
    parser.add_argument("--cap-s", type=float, required=True, help="cap in effective seconds (pauses not counted)")
    parser.add_argument("--checkpoint-every", type=int, required=True, help="save a checkpoint every this many steps")
    parser.add_argument("--nan-at-step", type=int, help="make the value of this step a NaN (the contract test)")
    return parser.parse_args(argv)                                  # a bad argument exits 2, which is EXIT_REFUSED


def run(args: argparse.Namespace, guard: RunGuard) -> int:
    resumed = guard.load_latest()
    step, total = (resumed.step, resumed.state["total"]) if resumed is not None else (0, 0.0)
    say(f"resumed from step {step} of {args.steps}" if resumed is not None else f"fresh start, {args.steps} steps")
    while step < args.steps:
        reason = guard.stop_reason()
        if reason is not None:
            guard.save(step, {"total": total})
            say(f"stopped ({reason}) at step {step}; checkpoint saved; the same command resumes")
            return EXIT_FOR_STOP[reason]
        time.sleep(args.step_s)
        value = math.nan if step + 1 == args.nan_at_step else float(step + 1)
        try:
            guard.check_finite(value=value)
        except NonFiniteError as err:
            say(f"non-finite value at step {step + 1} ({err}); the last good checkpoint is kept")
            return EXIT_NONFINITE
        step, total = step + 1, total + value
        say(f"step {step} total {total}")
        if step % args.checkpoint_every == 0:
            guard.save(step, {"total": total})
    guard.save(step, {"total": total})
    atomic.write_text(args.run_dir / RESULT_NAME, json.dumps({"steps": step, "total": total}) + "\n")
    say(f"done: {step} steps, total {total}")
    return EXIT_DONE


def main(argv: list[str] | None = None) -> int:
    args = parse(argv)
    if args.steps < 1 or args.checkpoint_every < 1 or args.step_s < 0 or not args.cap_s > 0:
        print("refused: --steps and --checkpoint-every must be 1 or more, --step-s 0 or more, --cap-s above 0",
              file=sys.stderr)
        return EXIT_REFUSED
    try:
        with RunGuard(args.run_dir, cap_s=args.cap_s) as guard:
            return run(args, guard)
    except RunBusyError as err:
        print(f"refused: {err}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    raise SystemExit(main())
