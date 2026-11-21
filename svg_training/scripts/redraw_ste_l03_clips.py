#!/usr/bin/env python3
"""VID-1c: re-draw the L0.3 (record T49) 2-D clips with the height panel (the standing rule: every 2-D clip carries
one), from the run folders' kept video slots (``arms/<arm>__video.npz``), on the CPU. No game is played again: the
positions are the ones the run kept.

    unset PYTHONPATH
    PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/redraw_ste_l03_clips.py \\
        --transfer-run <runs/2026-11-21_ste_l03_transfer> --cpu-run <runs/2026-11-21_ste_l03_cpu> \\
        [--out docs/media/ste_l03] [--work runs/<date>_ste_vid1c]

The clips are picked as the run picked them (``nus/pilot.eval_clips``: first Strike win, first hold, ``[clips]
per_arm`` per arm) and drawn by ``viz/replay.render_replay`` with the height panel, as the run's settings drew the MP4s
(the world's video speed, frames per second and dpi), then converted to GIFs as before (720 px wide, every frame kept),
replacing the published GIFs of the same names. Needs the NUS local files (``scripts/nus_install_provisional.sh``).
Exit 0 done, 2 refused (a missing file)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))

ARMS = ("t2_t41", "t2_parked", "t1_cuda_t41")                       # in the transfer run; t1_cpu_t41 in the CPU run
TIER = {"t1_cpu_t41": "tier1_cpu_t41", "t1_cuda_t41": "tier1_cuda_t41", "t2_t41": "tier2_t41",
        "t2_parked": "tier2_parked"}
KIND = {"hold": "hold", "strike_win": "reach"}
GIF_WIDTH = 720                                                     # as the published GIFs (README: 720 px)


def doc_name(arm: str, kind: str, slot: int) -> str:
    """The published GIF's name of a clip (docs/media/ste_l03/)."""
    return f"{TIER[arm]}_v_s20_{KIND[kind]}_slot{slot}.gif"


def main(argv=None) -> int:
    import numpy as np
    import torch
    import imageio.v2 as imageio

    from svg_training.bench.overlay import encode_gif
    from svg_training.core.game_config import TICK_S
    from svg_training.core.play import MatchResult
    from svg_training.nus import ladder
    from svg_training.nus import pilot as P
    from svg_training.ste import transfer as T
    from svg_training.viz.replay import render_replay

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--transfer-run", required=True)
    ap.add_argument("--cpu-run", required=True)
    ap.add_argument("--out", default=str(ROOT / "docs" / "media" / "ste_l03"))
    ap.add_argument("--work", default=str(ROOT / "runs" / "ste_vid1c_l03"))
    a = ap.parse_args(argv)
    tr, cpu, out, work = Path(a.transfer_run), Path(a.cpu_run), Path(a.out), Path(a.work)
    gates = T.load_gates(tr / "gates.toml")
    w5, w6 = T.worlds(gates)
    work.mkdir(parents=True, exist_ok=True)
    done = []
    for run, arm, world, g_name in ((cpu, "t1_cpu_t41", w5, "T41"), (tr, "t2_t41", w6, "T41"),
                                    (tr, "t2_parked", w6, gates["controls"]["parked_guard"]),
                                    (tr, "t1_cuda_t41", w5, "T41")):
        f = run / "arms" / f"{arm}__video.npz"
        if not f.is_file():
            print(f"refused: {f} missing", flush=True)
            return 2
        d = np.load(f)
        k = d["video"].shape[1]
        t = lambda x: torch.from_numpy(np.asarray(x)[:k])                # noqa: E731
        z = torch.zeros(k)
        res = MatchResult(t(d["outcome"]), t(d["end_step"]), z.long(), t(d["closest_cross_m"]), z, z.bool(), z,
                          z.bool(), steps_played=int(d["steps_played"]))
        clips = P.eval_clips(res, {"video": torch.from_numpy(d["video"])}, world)
        v = world.video
        for clip in clips[:int(gates["clips"]["per_arm"])]:
            rec = ladder.clip_recording(clip, world.geo, world.guards, world.strikes, g_name, gates["run"]["opponent"],
                                        arm, int(gates["run"]["eval_seed"]))
            mp4 = work / f"{arm}_{clip['kind']}_slot{clip['slot']}.mp4"
            render_replay(rec, mp4, speed=v["speed"], fps=v["fps"], dpi=v["dpi"],
                          playback_label=f"{v['speed'] * v['fps'] * TICK_S:g}x real time", height_panel=True)
            reader = imageio.get_reader(str(mp4))
            frames = [img for img in reader]
            reader.close()
            gif, info = encode_gif(frames, out / doc_name(arm, clip["kind"], clip["slot"]), fps=int(v["fps"]),
                                   max_mb=5.0, src_fps=int(v["fps"]), speed=1.0,
                                   widths=(GIF_WIDTH, 640, 560, 480))
            done.append(f"{gif.name}: {len(frames)} frames, {info}, {gif.stat().st_size / 1e6:.2f} MB")
            print(done[-1], flush=True)
    print(f"{len(done)} GIFs written", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
