#!/usr/bin/env python
"""STE task L1.7 speed re-measure on an idle RTX 5090 (the laptop's numbers of 23 Nov 2026 were taken under load).

Tier 1 (the fitted backend), the L0.11 base game, 3v3, random actions. Arms, alternated within each repeat on the GPU:
  off            configs/ste_l011/base.toml (no [estimate_error] table: today's game)
  nominal        configs/ste_l1/base_err_nominal.toml (L1.3 sigmas, T63, PROPOSED)
  conservative   configs/ste_l1/base_err_conservative.toml (2 x the sigmas)
  nominal_est    nominal with commander_reads = "estimate" (the commander copy and its filter read the estimate)
Sizes: 4,096 and 16,384 games. Timing as configs/ste_l1/model_check.toml [timing]. Writes results.json and results.md
into --out. INFO only, no gate. Observed in the training simulator; not a flight result.

    PYTHONPATH=source python records/evidence/2026-11-24_ste_l17_speed/measure_l17_speed.py --out runs/<dir> [--repeats 5]
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "source"))

import torch  # noqa: E402

from svg_training.bench.timing import measure  # noqa: E402
from svg_training.core.game import SvgGame  # noqa: E402
from svg_training.core.game_config import load_game_cfg  # noqa: E402

FILES = {"off": "configs/ste_l011/base.toml", "nominal": "configs/ste_l1/base_err_nominal.toml",
         "conservative": "configs/ste_l1/base_err_conservative.toml"}
TIMING = dict(warmup_steps=50, timed_steps=200, min_warmup_s=2.0, min_timed_s=3.0)
SEED = 1100


def arms() -> dict:
    out = {k: load_game_cfg(ROOT / v, use_local=False)[0] for k, v in FILES.items()}
    nom = out["nominal"]
    out["nominal_est"] = nom.replace(**{"estimate_error.commander_reads": "estimate"})
    assert not out["off"].estimate_error.enabled or not out["off"].estimate_error.error()
    for k in ("nominal", "conservative", "nominal_est"):
        assert out[k].estimate_error.enabled and out[k].estimate_error.error(), k
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--sizes", type=int, nargs="+", default=[4096, 16384])
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    device = "cuda"
    cfgs = arms()
    rows = []
    t0 = time.time()
    for games in args.sizes:
        for rep in range(args.repeats):
            for arm, cfg in cfgs.items():
                torch.manual_seed(SEED + rep)
                game = SvgGame(cfg, games, 3, 3, device=device, seed=SEED)
                game.reset(SEED)

                def step(game=game, games=games):
                    a = {"guard": torch.rand(games, 3, 4, device=device) * 2 - 1,
                         "strike": torch.rand(games, 3, 4, device=device) * 2 - 1}
                    game.step(a)
                    return {"pos": game.pos_m, "vel": game.vel_mps}

                r = measure(step, **TIMING, device=device)
                rows.append({"games": games, "repeat": rep, "arm": arm,
                             "game_steps_per_s": r["steps_per_s"] * games, "timed_s": r["timed_s"],
                             "nan_count": r["nan_count"]})
                print(f"{games} rep{rep} {arm}: {rows[-1]['game_steps_per_s']:,.0f} game-steps/s", flush=True)
                del game
                torch.cuda.empty_cache()
    summary = {}
    for games in args.sizes:
        base = None
        for arm in cfgs:
            v = [x["game_steps_per_s"] for x in rows if x["games"] == games and x["arm"] == arm]
            mean = sum(v) / len(v)
            if arm == "off":
                base = mean
            summary[f"{games}/{arm}"] = {"mean": mean, "min": min(v), "max": max(v),
                                         "cost_vs_off": None if arm == "off" else 1 - mean / base}
    res = {"task": "L1.7", "machine": platform.node(), "gpu": torch.cuda.get_device_name(0),
           "torch": torch.__version__, "timing": TIMING, "seed": SEED, "files": FILES, "rows": rows,
           "summary": summary, "wall_s": time.time() - t0}
    (args.out / "results.json").write_text(json.dumps(res, indent=2))
    lines = ["| Games | Arm | Mean game-steps/s | Min | Max | Cost against off |", "|---|---|---|---|---|---|"]
    for k, v in summary.items():
        g, a = k.split("/")
        c = "—" if v["cost_vs_off"] is None else f"{v['cost_vs_off']:+.1%}"
        lines.append(f"| {int(g):,} | {a} | {v['mean']:,.0f} | {v['min']:,.0f} | {v['max']:,.0f} | {c} |")
    (args.out / "results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
