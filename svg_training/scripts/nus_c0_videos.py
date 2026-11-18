"""C0 videos (plan section 4.3; ``[gates.phase5_positive_control]`` videos = "NUS eval.py, two games per archived entry"): NUS's self-play
runner writes no GIFs, so each archived entry of the C0 runs is replayed with NUS's own ``ma_skills/scripts/eval.py`` (STANDARDS section 8).
Runs NUS's code in its own environment, CPU:

    cd <svg_training>; unset PYTHONPATH; python3 scripts/nus_c0_videos.py --clone <NUS clone> --outputs-dir <NUS outputs/hangar> \
        --runs <run> <run> <run> [--out runs/nus_port/phase5/c0/videos] [--python ~/miniconda3/envs/nus_jax/bin/python]

For each archived entry ``<run>/archive/<gggg>_<team>``: ``<out>/<run>/<entry>/ckpt/`` holds a link to the entry's best checkpoint
(``<run>/generations/<entry>/checkpoints/best/state.msgpack``, the parameters NUS archived) and a copy of that checkpoint's
``config.json`` with only the opponents changed: the entry's strongest opponent in its own archive evaluation (lowest win rate; a learned
entry of the other team, or APF alone), deterministic, as a fixed-opponent runner. ``eval.py`` then plays two games with GIFs into
``<out>/<run>/<entry>/eval/`` (``JAX_PLATFORMS=cpu``). ``<out>/videos.json`` lists the GIFs. NUS's tree is read, never written. No
partner code here; no numeric literal other than 0, 1, -1, 2 (G2).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = ROOT / "runs"   # tests patch it
DEFAULT_OUT = RUNS_ROOT / "nus_port" / "phase5" / "c0" / "videos"
DEFAULT_PYTHON = Path.home() / "miniconda3" / "envs" / "nus_jax" / "bin" / "python"
OTHER = {"defender": "attacker", "attacker": "defender"}
GAMES = 2
FIXED_RUNNER = "ma_skills.runner.fixed_opponent_runner.FixedOpponentRunner"


def _under_runs(path: Path) -> Path:
    resolved = Path(path).resolve()
    if RUNS_ROOT.resolve() not in (resolved, *resolved.parents):
        raise SystemExit(f"refusing: {resolved} is outside runs/")
    return resolved


def strongest_opponent(archive_entry: Path) -> str:
    """The opponent label (``generation_<k>`` or ``APF``) the entry did worst against in its own archive evaluation."""
    rows = json.loads((archive_entry / "metadata.json").read_text())["evaluation"]["rows"]
    return min(rows, key=lambda r: r["win_rate"])["opponent"]


def prepare(run_dir: Path, entry: Path, folder: Path) -> Path:
    best = run_dir / "generations" / entry.name / "checkpoints" / "best"
    team = entry.name.split("_")[-1]
    label = strongest_opponent(entry)
    pool = []
    if label != "APF":
        generation = int(label.split("_")[-1])
        pool = [str(run_dir / "archive" / f"{generation:04d}_{OTHER[team]}")]
    cfg = json.loads((best / "config.json").read_text())
    cfg |= {"opponent_pool_paths": pool, "opponent_checkpoint_path": None, "include_apf_in_pool": not pool,
            "opponent_action_mode": "deterministic", "eval_gif_episodes": GAMES}
    cfg["environment"]["runner"]["_target_"] = FIXED_RUNNER
    ckpt = folder / "ckpt"
    ckpt.mkdir(parents=True, exist_ok=True)
    (ckpt / "config.json").write_text(json.dumps(cfg, indent=2))
    link = ckpt / "state.msgpack"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(best / "state.msgpack")
    return ckpt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clone", required=True, type=Path)
    parser.add_argument("--outputs-dir", required=True, type=Path)
    parser.add_argument("--runs", required=True, nargs="+")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    args = parser.parse_args(argv)
    out = _under_runs(args.out)
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"} | {
        "PYTHONNOUSERSITE": "1", "WANDB_MODE": "disabled", "JAX_PLATFORMS": "cpu", "CUDA_VISIBLE_DEVICES": ""}
    summary = []
    for run in args.runs:
        run_dir = args.outputs_dir / run
        for entry in sorted(p for p in (run_dir / "archive").iterdir() if p.is_dir()):
            folder = out / run / entry.name
            ckpt = prepare(run_dir, entry, folder)
            done = subprocess.run([str(args.python), str(args.clone / "ma_skills" / "scripts" / "eval.py"), f"checkpoint_path={ckpt}",
                                   f"deployment_eval_episodes={GAMES}", "save_eval_gif=True", "jax.platform=cpu",
                                   "jax.preallocate=false", f"hydra.run.dir={folder / 'eval'}"],
                                  cwd=args.clone, env=env, capture_output=True, text=True)
            (folder / "eval.log").write_text(done.stdout + done.stderr)
            gifs = sorted(str(p) for p in (folder / "eval").rglob("*.gif"))
            summary.append({"run": run, "entry": entry.name, "opponent": strongest_opponent(entry), "exit": done.returncode, "gifs": gifs})
            print(f"{run}/{entry.name}: exit {done.returncode}, {len(gifs)} GIFs", flush=True)
    (out / "videos.json").write_text(json.dumps({"entries": summary}, indent=2) + "\n")
    return 0 if all(e["exit"] == 0 for e in summary) else 1


if __name__ == "__main__":
    raise SystemExit(main())
