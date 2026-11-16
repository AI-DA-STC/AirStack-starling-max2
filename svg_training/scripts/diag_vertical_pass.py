#!/usr/bin/env python3
"""Diagnosis for S2b Task 8 (T13): do Guard and Strike drones pass one over the other, and is a height difference
alone enough to break a scripted Guard's block? CPU only, PyTorch reference world; never starts Isaac Sim.

    PYTHONPATH=source python scripts/diag_vertical_pass.py --backend fitted|physics [--games 40]
        [--guard guard_mark_edge] [--strike strike_straight] [--strike-dz-m 0.0] [--seed 0]

One 2v1 game batch in the lab band (committed neutral values, no local file), the Starling layer on, the chosen
drone model: "fitted" = tier 1 (the exploratory fitted PX4 model), "physics" = the physics drone in the PyTorch
reference world (``TorchRigidBodyWorld``; Isaac Lab agreed with it to 0.001 m/s in T11). Game seed ``--seed``, band
lab, Guard strategy seed 101, Strike 202, as score.py. ``--strike-dz-m`` raises every Strike drone's start by that
many metres after the reset; to do that the script writes the game's position (``game.pos_m``) and restarts the
Starling layer's state through the game's private ``game._starling.reset(...)`` (a diagnosis only, not an interface).

Prints, over every game's FIRST game (until it ends):
  hold            share of games the Guard team held;
  largest height change   the largest |z - start height| of any one drone at any step (m);
  Strike wins with a pass Strike wins in which, at the step of the closest horizontal Guard-Strike approach, the
                  pair was under 0.55 m apart horizontally and more than 0.5 m apart in height (a looser test than
                  figure 2 of the T13 record, which asks for >= 0.84 m from the per-game minima).
Exit 0. Nothing is written.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.game import SvgGame  # noqa: E402
from svg_training.core.game_config import load_game_cfg  # noqa: E402
from svg_training.core.physics_layer import load_game_physics_params  # noqa: E402
from svg_training.models.rigid_body import TorchRigidBodyWorld  # noqa: E402
from svg_training.opponents.scripted import make_strategy  # noqa: E402

PASS_HORIZ_M, PASS_DZ_M = 0.55, 0.5
GUARDS, STRIKES = 2, 1


def run(backend: str, games: int, guard: str, strike: str, strike_dz_m: float, seed: int) -> dict:
    """One batch of 2v1 lab games on the CPU; returns the numbers the module docstring lists."""
    torch.manual_seed(0)
    dev, n, m = "cpu", games, GUARDS + STRIKES
    cfg, _ = load_game_cfg(local_dir=None, use_local=False)
    cfg = cfg.replace(**{"starling.enabled": True, "starling.backend": backend})
    world = None
    if backend == "physics":
        p = load_game_physics_params(cfg)
        world = TorchRigidBodyWorld(n, m, p.airframe, p.physics_dt_s, dev)
    game = SvgGame(cfg, n, GUARDS, STRIKES, device=dev, seed=seed, band=0, world=world)
    g = make_strategy(guard, "guard", cfg, n, dev, seed + 101)
    s = make_strategy(strike, "strike", cfg, n, dev, seed + 202)
    obs = game.reset()
    if strike_dz_m:
        pos = game.pos_m.clone()
        pos[:, GUARDS:, 2] += strike_dz_m
        game.pos_m = pos
        game._starling.reset(torch.ones(n, m, dtype=torch.bool), pos, game.yaw)   # private: diagnosis only
        obs = game._obs()
    start_z = game.pos_m[..., 2].clone()                                         # [N, M]
    everyone = torch.ones(n, dtype=torch.bool)
    g.reset(everyone)
    s.reset(everyone)
    done_at = torch.full((n,), -1)
    outcome = torch.zeros(n, dtype=torch.int8)
    max_dz = torch.zeros(n)
    best_h = torch.full((n,), float("inf"))       # closest horizontal Guard-Strike approach so far
    dz_at_best = torch.zeros(n)                   # their height difference at that step
    for t in range(1, game.ticks + 1):
        out = game.step({"guard": g.act(obs["guard"]), "strike": s.act(obs["strike"])})
        live = done_at < 0                                     # the slot's first game played this step
        # a game that ends on this step has already been reset (new starts in game.pos_m), so its positions are not
        # read on that step: only games still on after the step count
        use = live & ~out.done
        pos = game.pos_m
        z = pos[..., 2]
        max_dz = torch.where(use, torch.maximum(max_dz, (z - start_z).abs().amax(dim=1)), max_dz)
        gd, st = pos[:, :GUARDS], pos[:, GUARDS:]
        dh = (gd[:, :, None, :2] - st[:, None, :, :2]).norm(dim=-1)                # [N, G, S]
        dz = (gd[:, :, None, 2] - st[:, None, :, 2]).abs()
        flat_h, k = dh.flatten(1).min(dim=1)
        flat_dz = dz.flatten(1).gather(1, k[:, None])[:, 0]
        better = use & (flat_h < best_h)
        best_h = torch.where(better, flat_h, best_h)
        dz_at_best = torch.where(better, flat_dz, dz_at_best)
        first = live & out.done
        done_at = torch.where(first, torch.full_like(done_at, t), done_at)
        outcome = torch.where(first, out.outcome, outcome)
        g.reset(out.done)
        s.reset(out.done)
        obs = out.obs
        if bool((done_at >= 0).all()):
            break
    wins = outcome == 1
    passed = wins & (best_h < PASS_HORIZ_M) & (dz_at_best > PASS_DZ_M)
    return {"backend": backend, "guard": guard, "strike": strike, "strike_dz_m": strike_dz_m, "games": n,
            "hold": float((outcome == 2).float().mean()), "mean_end_step": float(done_at.float().mean()),
            "largest_height_change_m": float(max_dz.max()), "strike_wins": int(wins.sum()),
            "strike_wins_with_pass": int(passed.sum())}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--backend", choices=("fitted", "physics"), required=True)
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--guard", default="guard_mark_edge")
    ap.add_argument("--strike", default="strike_straight")
    ap.add_argument("--strike-dz-m", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    r = run(a.backend, a.games, a.guard, a.strike, a.strike_dz_m, a.seed)
    print(f"{r['backend']} {r['guard']} v {r['strike']}, Strike start +{r['strike_dz_m']} m, {r['games']} games: "
          f"hold {r['hold']:.3f}, mean end step {r['mean_end_step']:.0f}, largest height change of one drone "
          f"{r['largest_height_change_m']:.6f} m, Strike wins {r['strike_wins']}, with a pass "
          f"{r['strike_wins_with_pass']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
