"""Stage 0e (LS1_REDESIGN.md 4.2, INFO, calibration, no mark; changes nothing): the scripts fly with every allowed
kind of row error at once (T90's CommandPerturbation, nested per slot, innermost first: noise on the skill's active
channels -> bias +b on x, y -> turn +0.5 deg -> scale 0.99 on vx, vy, vz), on every gated cell of <side>, paired with
T94's stored script games. guard_parked_centre is not wrapped. Noise seed per slot: 150101 + cell index x 3 + slot.
The realised RMSE / bias / turn / scale per skill are not computed here (the configured sizes are reported).
usage: s0e.py <side>"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

from harness import ctx_of, net_batches, check_layout, cells, eq
from svg_training.opponents import perturbed
from svg_training.opponents.scripted import make_strategy

side = sys.argv[1]
H = {"strike": 0.0173, "guard": 0.0260}[side]
BIAS = {"strike": 0.005, "guard": 0.003}[side]
TURN, SCALE, NOISE_SEED = 0.5, 0.99, 150101
ctx = ctx_of(side)
bs = [b for b in net_batches(ctx, info=False)]
check_layout(ctx, bs)
reader = eq.Reader(ctx, eq.plan_batches(ctx))
held = torch.load(eq.ROOT / f"runs/2026-11-26_ste_ls11_distil_{side}/data/round_0.pt", map_location="cpu",
                  weights_only=True)
active = {sk: (held["label"][:, k].abs().amax(0) > 0).tolist() for k, sk in enumerate(ctx.spec.players)}
del held
print(f"{side}: h {H} bias {BIAS} turn {TURN} scale {SCALE}; active {active}", flush=True)
off = eq.exploit.GUARD_SEED_OFFSET if side == cells.SIDES[0] else eq.exploit.STRIKE_SEED_OFFSET
s = ctx.seed + off


def member(cell, skill, slot):
    script = make_strategy(skill, side, ctx.cfg, ctx.n, ctx.device, s)
    if skill == "guard_parked_centre":
        return script
    ch = tuple(i for i, a in enumerate(active[skill]) if a)
    seed = NOISE_SEED + cell.index * ctx.spec.drones + slot
    w = perturbed.CommandPerturbation(script, "noise", H, seed, ch)
    w = perturbed.CommandPerturbation(w, "bias", BIAS, seed, perturbed.XY)
    w = perturbed.CommandPerturbation(w, "turn", TURN, seed, perturbed.XY)
    return perturbed.CommandPerturbation(w, "scale", SCALE, seed, (0, 1, 2))


rows = []
for b in bs:
    t0 = time.perf_counter()
    players = {}
    for cell in b.cells:
        name = f"{cells.CAL_PREFIX}combined:{cell.choice['name']}@{cell.opponent}"
        flies = list(cell.choice["flies"])
        if len(set(flies)) == 1:
            players[name] = member(cell, flies[0], 0)
            players[name].name = name
        else:
            players[name] = cells.Composite(side, [member(cell, sk, m) for m, sk in enumerate(flies)], ctx.cfg, ctx.n,
                                            ctx.device, s, name=name)
    pairs = [cells.cell_of(side, name, c.opponent) for name, c in zip(players, b.cells)]
    pg = eq.exploit.play_cells(ctx.cfg, ctx.g.skills_gates.run["size"], ctx.ref, pairs, ctx.n, ctx.device, ctx.seed,
                               ctx.ticks, hold_ticks=eq.HOLD_TICKS, should_stop=lambda: False, players=players)
    for i, c in enumerate(b.cells):
        e = eq.cell_entry(eq.exploit.slice_cell(pg, i, ctx.n), reader.reference(c), side, ctx.z_cell)
        rows.append({"kind": c.kind, "codes": list(c.choice["flies"]), "opponent": c.opponent, "b": int(e["b"]),
                     "c": int(e["c"]), "flips": int(e["flips"]), "ci": e["ci"]})
    print(f"  {b.name}: {len(b.cells)} cells {time.perf_counter() - t0:.1f} s, max flips "
          f"{max(r['flips'] for r in rows[-len(b.cells):])}", flush=True)
f = [r["flips"] for r in rows]
print(f"== 0e {side}: {len(rows)} gated cells; over 30: {sum(x > 30 for x in f)}; over 20: {sum(x > 20 for x in f)}; "
      f"median {sorted(f)[len(f) // 2]}; max {max(f)}; interval outside +-0.045: "
      f"{sum(not (-0.045 <= r['ci'][0] and r['ci'][1] <= 0.045) for r in rows)}", flush=True)
for r in sorted(rows, key=lambda x: -x["flips"])[:10]:
    print(f"   {r['flips']:4d}  {','.join(r['codes'])} v {r['opponent']}", flush=True)
json.dump(rows, open(Path(__file__).parent / f"s0e_{side}.json", "w"), indent=1)
print("done")
