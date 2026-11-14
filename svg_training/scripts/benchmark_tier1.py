"""S0 tier 1 throughput sweep: appends one JSON line per (case, repeat) to --out.

PYTHONPATH=source python scripts/benchmark_tier1.py --config configs/s0_benchmark.toml --out runs/<run>/results.jsonl
    [--device cuda] [--only <case>] [--max-games <n>] [--min-warmup-s <seconds>]
Every row carries "code_sha" (rows.code_sha: the code and config this run used). A point that raises any exception
other than out-of-memory is written as one "crash" row and the sweep goes on; the exit code is then 1 at the end.
"""
import argparse
import json
import pathlib
import sys
import tomllib

import torch

from svg_training.bench.timing import existing_points, run_case
from svg_training.envs.tier1_bench import Tier1BenchCfg, Tier1BenchEnv


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--only", default=None, help="one case name")
    ap.add_argument("--max-games", type=int, default=None, help="drop num_games entries above this")
    ap.add_argument("--min-warmup-s", type=float, default=2.0, help="minimum warm-up seconds per repeat")
    args = ap.parse_args()

    with open(args.config, "rb") as f:
        config = tomllib.load(f)
    timing = config["timing"]
    cases = [c for c in config["tier1"] if args.only is None or c["name"] == args.only]
    if args.only is not None and not cases:
        print(f"no tier 1 case named {args.only!r}; valid names: {', '.join(c['name'] for c in config['tier1'])}")
        sys.exit(3)
    out = pathlib.Path(args.out)
    try:
        done = existing_points(out)
    except ValueError as e:
        print(f"error: {e}")
        sys.exit(1)
    out.parent.mkdir(parents=True, exist_ok=True)
    dev = args.device
    if not any(args.max_games is None or n <= args.max_games for c in cases for n in c["num_games"]):
        print(f"no points to run: --max-games {args.max_games} is below every num_games entry")
        sys.exit(3)

    crashed = []
    with open(out, "a") as fh:
        for case in cases:
            m = case["guards"] + case["strikes"]
            for n in sorted(case["num_games"]):
                if args.max_games is not None and n > args.max_games:
                    continue
                if (case["name"], n) in done:
                    print(f"skip {case['name']} {n}: already in {out}", flush=True)
                    continue

                def make_env(n=n, case=case):
                    return Tier1BenchEnv(Tier1BenchCfg(
                        num_games=n, guards=case["guards"], strikes=case["strikes"], world=case["world"],
                        n_obstacles=case["n_obstacles"], n_rays=case["n_rays"],
                        line_of_sight=case["line_of_sight"], device=dev))

                def step_of(env, n=n, m=m):
                    # random action drawn on the device inside the timed section (the policy's stand-in)
                    return lambda: env.step(torch.rand(n, m, 4, device=dev) * 2 - 1)

                rows = run_case(make_env, step_of, case, n, timing, dev, args.min_warmup_s)
                for r in rows:
                    fh.write(json.dumps(r) + "\n")
                fh.flush()
                if rows[0]["status"] == "oom":
                    print(f"{case['name']} games={n}: OOM", flush=True)
                elif rows[0]["status"] == "crash":
                    crashed.append((case["name"], n))
                    print(f"{case['name']} games={n}: CRASH {rows[0]['error']}", flush=True)
                else:
                    best = max(r["env_steps_per_s"] for r in rows)
                    print(f"{case['name']} games={n}: {best:,.0f} env steps/s", flush=True)
    if crashed:
        print(f"{len(crashed)} point(s) crashed: " + ", ".join(f"{c} {n}" for c, n in crashed), flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
