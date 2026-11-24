#!/usr/bin/env python
"""STE task L2.6 follow-up clips (spec ste_learning/drafts/L2_6_SPEC.md, "Clips"; lead's decision 24 Nov 2026: a render
after the run, not a driver step). 2-D replays with the height panel (viz/replay.py) of the same starts on tier 1 and
tier 2: the same game file (tier 2 = the physics backend and the off parameter file, as the driver plays it), the same
clip seed, and the same starts: drawn once on the CPU from the clip seed (``clip_starts``) and given to both tiers, so
game i starts the same on both (CLIP-T2, 24 Nov 2026: tier 2 runs on CUDA, whose generator draws other starts from the
same seed). Same starts, same game file; the tag, strategy and estimator noise streams are each device's own. Own starts
from the clip seed (as L2.5's clips), never T44's scoring starts. The cells: landing + option B at 1.15 m,
guard_mark_edge v strike_low (the one cell beyond T13's 0.10 gap, T71) and guard_mark_edge v strike_straight (option B
lowers its hold on both tiers).

Which game is drawn (fixed before rendering, in this code): the first game index whose outcome differs between the two
tiers; if none, game 0. The same index on both tiers. Every game's outcome on both tiers goes to ``clips.json``.
``--tier1-only`` (CPU, no Isaac): the first reach and the first hold of each cell on tier 1. Used for T71 because the
tier-2 path here gave a reach in all 8 games of both cells (record T71). CLIP-T2 found the cause: tier 2 drew its own
starts on CUDA (other games than tier 1's); on the CPU starts tier 2 gives the tier-1 mix, on the CUDA starts every path
and both tiers give reaches (runs/2026-11-24_clip_t2_diag, clip worktree). Fixed here by ``clip_starts``.

    # after nvidia-smi and scripts/isaac_preflight.sh --approved-headless (exit 0), through the launcher (GPU-h logged):
    scripts/ste_job.py launch --task L2.6 --name l26_clips --run-dir runs/<date>_ste_l26_clips --min-s 30 --gpu-h 0.05 \\
        --settings configs/ste_learning.toml -- <python> scripts/ste_l26_clips.py --out-dir runs/<date>_ste_l26_clips \\
        --headless
    # tests only (tier 2 on the PyTorch reference world, CPU): --dry-cpu

Observed in the training simulator; nothing here is a flight result."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

GATES = ROOT / "configs" / "ste_l2" / "l26_gates.toml"
CELLS = (("landing_gy_1p15", "guard_mark_edge", "strike_low"),
         ("landing_gy_1p15", "guard_mark_edge", "strike_straight"))
CLIP_SEED = 260000            # the clips' own starts (never T44's scoring starts, seed 110000)
SPEED, FPS, DPI = 8, 10, 50   # as L2.5's clips: 8 game steps per frame at 10 frames/s = 4 x real time
RUNNING, STRIKE_WIN, GUARD_WIN = 0, 1, 2


def say(text: str) -> None:
    print(f"[l26 clips] {text}", flush=True)


def parser(isaac: bool = False) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--games", type=int, default=8, help="games recorded per cell and tier (the choice looks over them)")
    ap.add_argument("--max-ticks", type=int, default=2400, help="the game length (120 s); shorter only in tests")
    ap.add_argument("--dry-cpu", action="store_true", help="tests only: tier 2 on the PyTorch reference world, CPU")
    ap.add_argument("--tier1-only", action="store_true",
                    help="tier 1 only (CPU, no Isaac): the first reach and the first hold of each cell; tier 2 pending "
                         "(T71; the tier-2 start draw was CUDA's, fixed by CLIP-T2: clip_starts)")
    if not isaac:
        ap.add_argument("--headless", action="store_true", help="required without --dry-cpu (Isaac Lab)")
    return ap


def choose(t1: list[int], t2: list[int]) -> tuple[int, str]:
    """The game drawn: the first index finished on both tiers with different outcomes, else game 0."""
    for i, (a, b) in enumerate(zip(t1, t2)):
        if a != RUNNING and b != RUNNING and a != b:
            return i, "first game whose outcome differs between the tiers"
    return 0, "no game differs between the tiers: game 0"


def clip_starts(cfg, games: int):
    """The clip games' starts (starts_m [games, 6, 3] m, miss [games] bool): ``viz.replay.cpu_starts`` from CLIP_SEED
    (``record_games``' own CPU draw), so tier 1 is unchanged and tier 2 plays the same starts whatever its device.
    ``cfg``: the tier-1 game file."""
    from svg_training.viz.replay import cpu_starts
    return cpu_starts(cfg, games, 3, 3, CLIP_SEED, band=0)


def pick_tier1(t1: list[int]) -> list[int]:
    """Tier 1 only: the first reach, then the first hold (as ste_exploit_l012.pick_videos), where there are."""
    return [t1.index(code) for code in (STRIKE_WIN, GUARD_WIN) if code in t1]


def main(argv: list[str] | None = None) -> int:
    return run(parser().parse_args(list(sys.argv[1:] if argv is None else argv)))


def run(a: argparse.Namespace) -> int:
    if not a.dry_cpu and not a.tier1_only and not getattr(a, "headless", True):
        print("refused: tier 2 starts Isaac Lab: --headless", file=sys.stderr)
        return 2
    import torch  # noqa: F401  (after Isaac Sim has started, on the Isaac path)

    from svg_training.core.physics_layer import load_game_physics_params
    from svg_training.ste import atomic
    from svg_training.viz import replay
    import ste_tier12_l26 as drv
    from ste_tier2_score_l18 import isaac_world_factory, torch_world_factory
    s = drv.load_settings(GATES)
    problems = drv.pin_problems(s)
    if problems:
        print("refused: pinned file(s): " + "; ".join(problems), file=sys.stderr)
        return 2
    by = {g["name"]: g for g in s["groups"]}
    dev2 = "cpu" if a.dry_cpu else "cuda"
    factory = torch_world_factory if a.dry_cpu else isaac_world_factory
    a.out_dir.mkdir(parents=True, exist_ok=True)
    world, meta = None, {"what": "STE L2.6 follow-up clips: the same starts on tier 1 and tier 2", "seed": CLIP_SEED,
                         "games": a.games, "max_ticks": a.max_ticks, "dry_cpu": bool(a.dry_cpu),
                         "tier1_only": bool(a.tier1_only),
                         "rule": ("tier 1 only, the first reach and the first hold; tier 2 pending" if a.tier1_only
                                  else "the first game whose outcome differs between the tiers, else game 0"),
                         "starts": ("drawn once on the CPU from the seed, the same on both tiers (clip_starts, "
                                    "CLIP-T2); same starts, same game file; the tag, strategy and estimator noise "
                                    "streams are each device's own"),
                         "gates_sha256": drv._sha(GATES), "cells": []}
    for group, guard, strike in CELLS:
        g = by[group]
        cfg1, cfg2 = drv.game_cfg(s, g["tier1_game"]), drv.tier2_cfg(s, g["tier2_game"], "off")
        if world is None and not a.tier1_only:
            t0 = time.perf_counter()
            world = factory(a.games, 6, load_game_physics_params(cfg2), dev2)
            say(f"tier-2 world: {getattr(world, 'label', type(world).__name__)}, {a.games} games x 6 drones "
                f"({time.perf_counter() - t0:.0f} s)")
        recs, outcomes, starts = {}, {}, clip_starts(cfg1, a.games)
        tiers = ((1, cfg1, "cpu", None),) if a.tier1_only else ((1, cfg1, "cpu", None), (2, cfg2, dev2, world))
        for tier, cfg, dev, w in tiers:
            got = replay.record_games(cfg, 3, 3, guard, strike, num_games=a.games, seed=CLIP_SEED, band=0,
                                      max_steps=a.max_ticks, device=dev, world=w, starts=starts)
            recs[tier] = {r.game_index: r for r in got}
            outcomes[f"tier{tier}"] = [int(recs[tier][i].outcome) if i in recs[tier] else RUNNING
                                       for i in range(a.games)]
        if a.tier1_only:
            picks, why = [(1, i) for i in pick_tier1(outcomes["tier1"])], "tier 1 only: the first reach, the first hold"
        else:
            i, why = choose(outcomes["tier1"], outcomes["tier2"])
            picks = [(1, i), (2, i)]
        gifs = []
        for tier, i in picks:
            rec = recs[tier].get(i)
            if rec is None:
                say(f"{group} {guard} v {strike}: game {i} did not finish on tier {tier} within {a.max_ticks} ticks")
                continue
            kind = "reach" if rec.outcome == STRIKE_WIN else "hold"
            name = f"l26_{group}_{guard}_v_{strike}_tier{tier}_game{i}_{kind}.gif"
            path = replay.render_replay(rec, a.out_dir / name, speed=SPEED, fps=FPS, dpi=DPI,
                                 playback_label=f"{SPEED * FPS * 0.05:g}x real time, tier {tier}")
            gifs.append({"tier": tier, "game": i, "outcome": kind, "end_s": float(rec.end_time_s), "file": name,
                         "bytes": path.stat().st_size})
            say(f"{name}: {kind} at {rec.end_time_s:.1f} s ({path.stat().st_size / 1e6:.2f} MB)")
        meta["cells"].append({"group": group, "guard": guard, "strike": strike, "games": sorted({i for _, i in picks}), "why": why,
                              "outcomes": outcomes, "gifs": gifs})
    atomic.write_text(a.out_dir / "clips.json", json.dumps(meta, indent=1) + "\n")
    say(f"done: {a.out_dir / 'clips.json'}")
    return 0


def _isaac_cli() -> int:
    code = 1
    try:
        from _isaac_app import start_headless
        args, _app = start_headless(parser(isaac=True))
        args.headless = True
        code = run(args)
    except KeyboardInterrupt:
        code = 4
    except SystemExit as ex:
        code = ex.code if isinstance(ex.code, int) else 2
    except BaseException:  # noqa: BLE001
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)
    return code


if __name__ == "__main__":
    if "--dry-cpu" not in sys.argv[1:] and "--tier1-only" not in sys.argv[1:]:
        if "--headless" not in sys.argv[1:]:
            print("refused: tier 2 starts Isaac Lab: --headless", file=sys.stderr)
            sys.exit(2)
        _isaac_cli()
    sys.exit(main())
