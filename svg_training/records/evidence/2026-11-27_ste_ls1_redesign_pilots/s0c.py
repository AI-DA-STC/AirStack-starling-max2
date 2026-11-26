"""Stage 0c (LS1_REDESIGN.md 4.2): blended-switch replay. usage: s0c.py <side> <skill> <w_m> [<w_m> ...]
Every T94 network batch holding <skill> is replayed with BlendNet (scripts for every other code), per width.
Driver check at w = 0: every cell at most 2 changed games. A width passes for the skill if every GATED cell holding it
has b + c <= 20 and its interval inside +-0.045. Writes s0c_<side>_<skill>.json (one entry per width)."""
import json
import sys
from pathlib import Path

from harness import ctx_of, net_batches, check_layout, replay, cells
from blend import BlendNet

side, skill, widths = sys.argv[1], sys.argv[2], [float(x) for x in sys.argv[3:]]
ctx = ctx_of(side)
bs = [b for b in net_batches(ctx) if any(skill in c.choice["flies"] for c in b.cells)]
check_layout(ctx, bs)
oracle = cells.ScriptOracle(ctx.cfg, side, list(ctx.spec.players), ctx.spec.drones)
out_file = Path(__file__).parent / f"s0c_{side}_{skill}_{'_'.join(str(w) for w in widths)}.json"
out = {}
for w in widths:
    print(f"== {side} {skill} w {w*100:g} cm: {len(bs)} batches", flush=True)
    rows = [r for r in replay(ctx, BlendNet(oracle, skill, w), bs) if skill in r["codes"]]
    gated = [r for r in rows if r["kind"] != cells.INFO]
    worst = max(gated, key=lambda r: r["flips"])
    passes = all(r["flips"] <= 20 and -0.045 <= r["ci"][0] and r["ci"][1] <= 0.045 for r in gated)
    over20 = sum(r["flips"] > 20 for r in gated)
    over30 = sum(r["flips"] > 30 for r in gated)
    info = {"w_m": w, "cells": len(rows), "gated": len(gated), "max_flips": worst["flips"],
            "worst": f"{','.join(worst['codes'])} v {worst['opponent']}", "over20": over20, "over30": over30,
            "median_flips": sorted(r["flips"] for r in gated)[len(gated) // 2], "passes": passes, "rows": rows}
    if w == 0:
        info["driver_check"] = all(r["flips"] <= 2 for r in rows)
    out[str(w)] = info
    print(f"   cells {len(rows)} (gated {len(gated)}): max {worst['flips']} ({info['worst']}), median "
          f"{info['median_flips']}, over 20: {over20}, over 30: {over30}; "
          + (f"DRIVER CHECK {'PASS' if info['driver_check'] else 'FAIL'}" if w == 0 else
             f"width {'PASSES' if passes else 'fails'}"), flush=True)
    json.dump(out, open(out_file, "w"), indent=1)
print("done")
