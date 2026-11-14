"""S0 tier 2 throughput: one sweep point (case x num_games) in Isaac Lab, ARL Robot 1 stand-in airframe.

PYTHONPATH=source <isaaclab.sh -p> scripts/benchmark_tier2.py --headless --case t2_k2 --num-games 64
    --config configs/s0_benchmark.toml --out runs/<run>/results.jsonl
One process = one sweep point = [timing].repeats rows appended to --out. The scene is built once; each repeat
resets every drone to its spawn pose and times `timing.measure`. Exit codes: 0 ok or already done (resume: no app
launched), 1 crash or out of memory (a row with that status is appended), 2 asset cannot be loaded, --headless
missing or device not cuda (one line, no row). The process always leaves with os._exit after flushing: Kit's
shutdown would swallow the exit code on failure, and in the container it spun without returning on success.
Every row carries "code_sha" and the process seeds torch with 0 (torch.manual_seed(0)) before any random draw.
Resume: a point that already has a row in --out is skipped (no app launched). A "crash" or "oom" row counts as done;
delete that row from the results file to retry the point.
Before the app launches only the standard library, svg_training.bench.rows and isaaclab.app are imported; torch,
svg_training.bench.timing and compat/isaaclab_232.py are imported inside run(), after AppLauncher(args) returned.
"""
import argparse
import datetime
import json
import os
import pathlib
import sys
import tomllib
import traceback

AIRFRAME = "arl_robot_1"


def parse_case(cfg: dict, name: str, num_games: int) -> dict:
    """The [[tier2]] entry called `name`; KeyError if unknown, ValueError if num_games is not listed for it."""
    for case in cfg["tier2"]:
        if case["name"] == name:
            if num_games not in case["num_games"]:
                raise ValueError(f"num_games {num_games} not listed for {name}: {case['num_games']}")
            return case
    raise KeyError(name)


def make_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--case", required=True)
    ap.add_argument("--num-games", type=int, required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    return ap


def main() -> int:
    ap = make_parser()
    # Isaac imports only from here on, and the app is launched before any other isaaclab import.
    from isaaclab.app import AppLauncher
    AppLauncher.add_app_launcher_args(ap)
    args = ap.parse_args()
    if not args.headless:
        print("run with --headless", file=sys.stderr)
        return 2
    with open(args.config, "rb") as f:
        config = tomllib.load(f)
    try:
        case = parse_case(config, args.case, args.num_games)
    except (KeyError, ValueError) as e:
        print(f"bad --case/--num-games: {e!r}", file=sys.stderr)
        return 2

    if not str(args.device).startswith("cuda"):
        print("tier 2 runs on cuda only", file=sys.stderr)
        return 2
    from svg_training.bench.rows import existing_points  # standard library only: no torch before the app launches
    if (args.case, args.num_games) in existing_points(args.out):
        print(f"skip {args.case} {args.num_games}: already in {args.out}")
        return 0

    app_launcher = AppLauncher(args)
    simulation_app = app_launcher.app
    code = 1
    try:
        code = run(args, case, config["timing"])
    except BaseException:  # os._exit below would otherwise swallow the traceback
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        # simulation_app.close() is never called: in the container it spun for 30 min after the rows were written
        # (smoke run, 15 Nov 2026). Rows are closed and flushed by now; os._exit ends Kit with the process.
        os._exit(code)  # never returns; rows are already closed and flushed (append() uses `with open`)


def run(args, case: dict, timing: dict) -> int:
    """Everything that needs a running Isaac app."""
    import torch

    from svg_training.bench import timing as tm
    from svg_training.bench.rows import code_sha
    from svg_training.compat import isaaclab_232 as il

    torch.manual_seed(0)  # seed 0 for every case and repeat; set after the launcher, before any random draw

    device = args.device
    n, k = args.num_games, case["drones_per_game"]
    substeps, dt_s = case["substeps"], case["physics_dt_s"]
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    base = {"tier": 2, "case": case["name"], "num_games": n, "drones_per_game": k, "device": device,
            "gpu_name": tm.gpu_name(device), "commit": tm.git_commit(), "code_sha": code_sha(), "airframe": AIRFRAME,
            "physics_dt_s": dt_s, "substeps": substeps, "policy_dt_s": dt_s * substeps}

    def append(row: dict) -> None:
        row["date"] = datetime.datetime.now().isoformat(timespec="seconds")
        with open(out, "a") as fh:
            fh.write(json.dumps(row) + "\n")

    repeat = 0
    try:
        try:
            sim = il.make_sim(dt_s, substeps, device)
            scene, drones = il.build_scene(sim, n, k, physics_dt_s=dt_s)
            il.play(sim)
        except FileNotFoundError as e:  # no network or asset server unreachable
            print(f"cannot load USD: {e}", file=sys.stderr)
            return 2
        hover = il.hover_thrust_n(drones, device)  # k tensors [n, 1]
        hover_n = float(torch.cat(hover).mean().item())  # one host read, outside the timed section
        print(f"mass_kg={hover_n * 4 / il.GRAVITY_MPS2:.3f} hover_n={hover_n:.3f}", flush=True)
        gpu_index = torch.device(device).index or 0

        def step() -> dict:
            thrust = [h * (0.9 + 0.2 * torch.rand(n, 4, device=device)) for h in hover]  # hover +- 10 %
            il.step_scene(sim, scene, drones, thrust, substeps, dt_s)
            return il.reset_drones(scene, drones, only_out_of_bounds=True)

        for repeat in range(timing["repeats"]):
            il.reset_drones(scene, drones, only_out_of_bounds=False)
            r = tm.measure(step, timing["warmup_steps"], timing["timed_steps"], device,
                           min_timed_s=timing.get("min_timed_s", 0.0))
            env_sps = r["steps_per_s"] * n
            free_b, total_b = torch.cuda.mem_get_info(gpu_index)  # device-wide, sees the PhysX buffers
            append({**base, "repeat": repeat, "status": "ok", "env_steps_per_s": env_sps,
                    "drone_steps_per_s": env_sps * k, "peak_mem_mb": r["peak_mem_mb"],
                    "gpu_mem_used_mb": (total_b - free_b) / 2**20, "hover_n": hover_n,
                    "nan_count": r["nan_count"], "mean_reset_fraction": r["mean_reset_fraction"],
                    "timed_steps": r["timed_steps"], "timed_s": r["timed_s"]})
            print(f"{case['name']} games={n} repeat={repeat}: {env_sps:,.0f} env steps/s", flush=True)
        return 0
    except Exception as e:  # torch.OutOfMemoryError is an Exception
        oom = isinstance(e, torch.OutOfMemoryError) or "out of memory" in str(e).lower()
        append({**base, "repeat": repeat, "status": "oom" if oom else "crash", "env_steps_per_s": None,
                "drone_steps_per_s": None, "peak_mem_mb": None, "nan_count": None, "mean_reset_fraction": None,
                "gpu_mem_used_mb": None, "hover_n": None, "timed_steps": None, "timed_s": None, "error": repr(e)[:300]})
        print(f"{case['name']} games={n}: {'OOM' if oom else 'crash'}: {e!r}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())  # main only returns when no app was launched
