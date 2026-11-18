"""Render the videos a trainer left as data (NUS port Phase 5; lead, 18 Nov 2026: rendering off the training wall clock). CPU only:

    cd <svg_training>; unset PYTHONPATH; CUDA_VISIBLE_DEVICES= PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python \
        scripts/nus_render_pending.py --run-dir runs/nus_port/phase5/s51/seed1001 [--run-dir ...] [--format mp4] [--watch SECONDS]

Each ``<run>/videos/pending/<name>.npz`` (written by ``scripts/nus_selfplay_train.py --video-format deferred``) becomes
``<run>/videos/<name>.<format>`` through ``viz/replay.render_replay``; the data then moves to ``<run>/videos/rendered/``. ``--watch``
repeats every SECONDS until every run folder has its ``status.json`` (the trainer has stopped) and nothing is pending. Writes only
inside the run folders (runs/). No numeric literal other than 0, 1, -1, 2 (G2).
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def render_pending(run: Path, kind: str) -> list[Path]:
    from make_replay import FORMATS
    from nus_selfplay_train import load_recording
    from svg_training.viz.replay import render_replay
    done = []
    for data in sorted((run / "videos" / "pending").glob("*.npz")):
        out = render_replay(load_recording(data), run / "videos" / f"{data.stem}.{kind}", playback_label="replica", **FORMATS[kind])
        target = run / "videos" / "rendered" / data.name
        target.parent.mkdir(parents=True, exist_ok=True)
        data.replace(target)
        done.append(out)
        print(f"rendered {out}", flush=True)
    return done


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-dir", type=Path, action="append", required=True)
    parser.add_argument("--format", choices=("mp4", "gif"), default="mp4")
    parser.add_argument("--watch", type=float, help="poll interval in seconds; stop when every run has finished and nothing is pending")
    args = parser.parse_args(argv)
    while True:
        for run in args.run_dir:
            render_pending(run, args.format)
        finished = all((run / "status.json").exists() for run in args.run_dir)
        pending = any(any((run / "videos" / "pending").glob("*.npz")) for run in args.run_dir)
        if args.watch is None or (finished and not pending):
            return 0
        time.sleep(args.watch)


if __name__ == "__main__":
    raise SystemExit(main())
