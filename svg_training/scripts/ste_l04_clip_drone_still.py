#!/usr/bin/env python3
"""STE task L0.4: a close still of the Starling as the S2b / NUS Isaac clips draw it, through their own code path
(``compat/isaaclab_232.IsaacWorld(visual="starling")``: physics bodies, the Starling USD under each, team paint and
ball), two drones (Guard, Strike) held 1 m up, headless.

    unset PYTHONPATH
    PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/ste_l04_clip_drone_still.py --headless \\
        --out runs/<date>_ste_l04_clip_drone [--name after_fix]

Writes ``<out>/<name>.png`` (raw) and ``<out>/<name>.json`` (the composed visibility of each drone prim). The camera
is the close view of ``scripts/make_ste_3d.py``'s still rows. Run at commit 5d353145 it shows the clips' drone before
the L0.4 fix (the physics box drawn over the Starling); after the fix, without the box. Not a measurement.
Exit 0 done, 1 crash, 11 GPU busy.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

STARLING_USD = ROOT / ".." / "AirStack" / "simulation" / "isaac-sim" / "assets" / "robots" / "starling2max.usd"
GUARD_SRGB = (0.0, 114 / 255, 178 / 255)            # as scripts/make_s2b_video.py GUARD_RGB
STRIKE_SRGB = (240 / 255, 95 / 255, 0.0)            # as scripts/make_s2b_video.py STRIKE_RENDER_RGB
CLIP_MARKER_RADIUS_M = 0.03 + 0.0094 * 6.5          # the S2b ball in the 6.5 m lab arena


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", default="clip_drone")
    a0, _ = ap.parse_known_args()
    pre = subprocess.run(["bash", str(ROOT / "scripts" / "isaac_preflight.sh"), "--approved-headless"],
                         capture_output=True, text=True)
    if pre.returncode != 0:
        print(pre.stdout[-800:], file=sys.stderr)
        return 11 if pre.returncode == 11 else 1
    from _isaac_app import start_headless
    args, _app = start_headless(ap, cameras=True)
    code = 1
    try:
        import imageio.v2 as imageio
        import torch
        from pxr import Usd, UsdGeom

        from svg_training.compat import isaaclab_232 as isaac
        from svg_training.core.game_config import load_game_cfg
        from svg_training.core.physics_layer import load_game_physics_params

        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        cfg, _ = load_game_cfg(use_local=False)
        cfg = cfg.replace(**{"starling.enabled": True, "starling.backend": "physics"})
        params = load_game_physics_params(cfg)
        sim = isaac.make_physics_sim(params.physics_dt_s, "cuda:0")
        isaac.spawn_world_lights(sun=True)
        isaac.spawn_floor()
        world = isaac.IsaacWorld(sim, 1, 2, params.airframe, params.physics_dt_s, visual="starling",
                                 slot_rgb=[GUARD_SRGB, STRIKE_SRGB], starling_usd=str(STARLING_USD.resolve()),
                                 marker_radius_m=CLIP_MARKER_RADIUS_M)
        st = isaac._stage()
        vis = {str(p.GetPath()): UsdGeom.Imageable(p).ComputeVisibility()
               for p in Usd.PrimRange(st.GetPrimAtPath("/World/envs/env_0/Drone_0"))
               if p.IsA(UsdGeom.Imageable) and str(p.GetPath()).count("/") <= 6}
        isaac.physics_play(sim, world)
        dev = world.device
        world.reset(torch.ones(1, 2, dtype=torch.bool, device=dev),
                    torch.tensor([[[0.0, 0.0, 1.0], [0.6, 0.0, 1.0]]], device=dev),
                    torch.tensor([1.0, 0.0, 0.0, 0.0], device=dev).expand(1, 2, 4).contiguous())
        o = world.scene.env_origins[0].cpu().tolist()
        look = (o[0] + 0.3, o[1], 1.0)
        frame = isaac.make_recorder(sim, (look[0], look[1] - 1.6, 1.8), look, (1280, 720))
        img = None
        for _ in range(60):
            img = frame()
        imageio.imwrite(str(out / f"{args.name}.png"), img)
        (out / f"{args.name}.json").write_text(json.dumps({"visibility": vis}, indent=1))
        print(json.dumps(vis, indent=1), flush=True)
        code = 0
    except BaseException:
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)


if __name__ == "__main__":
    sys.exit(main())
