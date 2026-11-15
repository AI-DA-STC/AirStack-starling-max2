#!/usr/bin/env python
"""Probe: closest Guard–Strike approach, horizontal against 3-D, with the Starling layer (S2 Task 6, not a run of
record).

  PYTHONPATH=source python scripts/probe_closest_3d.py [--games 1000] [--steps 300] [--device cuda]

Plays 2 Guard v 1 Strike in the lab band (game seed 0, Guard seed 101, Strike seed 202, the settings of the scripted
reference run T6) for random v strike_flank and guard_mark_edge v strike_flank, and prints per game, over each
slot's first game, the closest opposite approach horizontally and in 3-D, the height gap at the closest horizontal
moment, and the Strike drone's height range. These are the "probe" numbers of
records/2026-11-16_s2_scripted_reference_record.md; they were produced by this same code from a scratch copy
before it was committed (16 November 2026, 1,000 games, 300 steps, cuda). The game's own
``info["closest_cross_3d_m"]`` now gives the 3-D value directly; this script reads positions after each step
instead, so games that end on a step are left out of that step (as in the original probe).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.game import SvgGame  # noqa: E402
from svg_training.core.game_config import load_game_cfg  # noqa: E402
from svg_training.opponents.scripted import make_strategy  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--games", type=int, default=1000)
    ap.add_argument("--steps", type=int, default=300)
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args()
    cfg = load_game_cfg(use_local=False)[0].replace(**{"starling.enabled": True})
    n, dev = a.games, a.device
    for gspec, sspec in (("random", "strike_flank"), ("guard_mark_edge", "strike_flank")):
        game = SvgGame(cfg, n, 2, 1, device=dev, seed=0, band=0)
        g = make_strategy(gspec, "guard", cfg, n, dev, 101)
        s = make_strategy(sspec, "strike", cfg, n, dev, 202)
        obs = game.reset()
        fin = torch.zeros(n, dtype=torch.bool, device=dev)
        h2 = torch.full((n,), float("inf"), device=dev)
        d3 = h2.clone()
        dz_at = torch.zeros(n, device=dev)
        zmin = torch.full((n,), 9.0, device=dev)
        zmax = torch.zeros(n, device=dev)
        for _ in range(a.steps):
            out = game.step({"guard": g.act(obs["guard"]), "strike": s.act(obs["strike"])})
            p = game.pos_m
            act = ~fin & ~out.done                       # first game still running after this step
            d = p[:, :2, None, :] - p[:, None, 2:, :]     # Guard drones x the Strike drone, [N, 2, 1, 3]
            hd = d[..., :2].norm(dim=-1).amin(dim=(1, 2))
            dd = d.norm(dim=-1).amin(dim=(1, 2))
            closer = hd < h2
            hflat = d[..., :2].norm(dim=-1).reshape(n, -1)
            dz = d[..., 2].abs().reshape(n, -1).gather(1, hflat.argmin(1, keepdim=True))[:, 0]
            dz_at = torch.where(act & closer, dz, dz_at)
            h2 = torch.where(act, torch.minimum(h2, hd), h2)
            d3 = torch.where(act, torch.minimum(d3, dd), d3)
            zmin = torch.where(act, torch.minimum(zmin, p[:, 2:, 2].amin(1)), zmin)
            zmax = torch.where(act, torch.maximum(zmax, p[:, 2:, 2].amax(1)), zmax)
            fin |= out.done
            obs = out.obs

        def q(t: torch.Tensor) -> list[float]:
            t = t[torch.isfinite(t)]
            return [round(float(torch.quantile(t, x)), 3) for x in (0, .01, .05, .5)]

        print(gspec, sspec, "horizontal min/p1/p5/p50", q(h2), "3-D", q(d3),
              "vertical gap at closest horizontal p50", q(dz_at)[-1], "max", float(dz_at.max()),
              "strike z range", float(zmin.min()), float(zmax.max()), flush=True)


if __name__ == "__main__":
    main()
