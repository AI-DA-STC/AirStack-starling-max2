"""Stage 1 per-skill fit (LS1_REDESIGN.md 4.3). usage:
  s1fit.py <tag> <side> <skill> <rung> [--hidden 128,128,128] [--steps 40000] [--seed 150003] [--schedule cos|const]
Writes nets/<tag>.pt (the module) and s1/<tag>.json (row marks per round, the eligibility screen, timing)."""
import argparse
import json
import time
from pathlib import Path

import torch

import lsr

ap = argparse.ArgumentParser()
ap.add_argument("tag"); ap.add_argument("side"); ap.add_argument("skill"); ap.add_argument("rung")
ap.add_argument("--hidden", default="128,128,128"); ap.add_argument("--steps", type=int, default=40000)
ap.add_argument("--seed", type=int, default=150003); ap.add_argument("--schedule", default="cos")
a = ap.parse_args()
torch.set_num_threads(6)
HERE = Path(__file__).parent
(HERE / "nets").mkdir(exist_ok=True); (HERE / "s1").mkdir(exist_ok=True)
t0 = time.time()
train, held = lsr.load_rows(a.side)
print(f"[{a.tag}] {a.side} {a.skill} {a.rung} hidden {a.hidden} steps {a.steps} seed {a.seed} {a.schedule}: "
      f"{train['obs'].shape[0]} training rows, loaded in {time.time() - t0:.0f} s", flush=True)
net, secs = lsr.fit_skill(train, a.side, a.skill, a.rung, hidden=[int(h) for h in a.hidden.split(",")],
                          steps=a.steps, seed=a.seed, schedule=a.schedule,
                          log=lambda s: print(f"[{a.tag}] {s}", flush=True))
k = lsr.SKILLS[a.side].index(a.skill)
mask = net.out_mask
del train
outs = {r: lsr.skill_out(net, held[r]["obs"], held[r]["slot"], a.side, a.skill, a.rung) for r in (0, 3)}
marks = {r: lsr.row_marks(outs[r], held[r], k, a.skill, mask) for r in (0, 3)}
screen = lsr.screen_value(outs[0], outs[3], held, k, mask)
torch.save(net, HERE / "nets" / f"{a.tag}.pt")
res = {"tag": a.tag, "side": a.side, "skill": a.skill, "rung": a.rung, "hidden": a.hidden, "steps": a.steps,
       "seed": a.seed, "schedule": a.schedule, "fit_seconds": secs, "screen_rmse": screen, "eligible": screen <= 0.10,
       "marks": {str(r): m for r, m in marks.items()}}
json.dump(res, open(HERE / "s1" / f"{a.tag}.json", "w"), indent=1)
for r in (0, 3):
    m = marks[r]
    print(f"[{a.tag}] round {r} ({m['rows']} rows): r2 bias {[round(x, 4) for x in m['r2_bias']]} r3 turn "
          f"{m['r3_turn_deg']:.2f} deg r4 scale {m['r4_scale']:.4f} r5 {[round(x, 4) for x in m['r5_rmse_debiased']]} "
          f"r6 {m['r6_tail']:.4f} r7 {[round(x, 4) for x in m['r7_rmse']]}", flush=True)
print(f"[{a.tag}] screen {screen:.4f} -> {'eligible' if screen <= 0.10 else 'NOT eligible'}; fit {secs:.0f} s; "
      f"total {time.time() - t0:.0f} s", flush=True)
