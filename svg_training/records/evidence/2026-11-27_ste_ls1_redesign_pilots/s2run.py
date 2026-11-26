"""Stage 2 runner. usage:
  s2run.py <name> <side> <skill>=<fit tag> [...]      a full replay of the assembly (screen first)
  s2run.py <name> <side> --unfitted                   the C4 analogue: an unfitted R2 assembly (seed 150003, all-ones
                                                      mask) plays the 30 fixed gated cells; mark: at least 15 miss
  add --complete to play every batch even after a screen stop.
Writes s2/<name>.json."""
import json
import sys
from pathlib import Path

import torch

import lsr
import stage2
from harness import ctx_of, net_batches, replay, cells, eq

torch.set_num_threads(6)
HERE = Path(__file__).parent
(HERE / "s2").mkdir(exist_ok=True)
name, side, rest = sys.argv[1], sys.argv[2], sys.argv[3:]
complete = "--complete" in rest
rest = [r for r in rest if r != "--complete"]


def log(s):
    print(s, flush=True)


if rest == ["--unfitted"]:
    train, _ = lsr.load_rows(side, n_train=50_000)
    parts = {}
    for k, sk in enumerate(lsr.SKILLS[side]):
        torch.manual_seed(150003)
        x, fr, ex = lsr.feats_chunked(train["obs"], train["slot"], side, sk, "R2")
        net = lsr.SkillMLP(x.shape[1], lsr.out_dim_of(sk), 1, [128, 128, 128], x.mean(0), x.std(0).clamp(min=0.01),
                           ((x == 0) | (x == 1)).all(0))
        net.register_buffer("out_mask", torch.ones(4))
        parts[sk] = (net.eval().requires_grad_(False), "R2")
    asm = lsr.Assembly(side, parts)
    ctx = ctx_of(side)
    bs = [b for b in net_batches(ctx, info=False) if all(c.kind == cells.FIXED for c in b.cells)]
    rows = replay(ctx, asm, bs, log=log)
    fixed = [r for r in rows if r["kind"] == cells.FIXED]
    miss = sum(eq.cell_failures(r, ctx.g.limits) != [] for r in fixed)
    out = {"name": name, "side": side, "fixed_cells": len(fixed), "miss": miss, "pass": miss >= 15, "rows": rows}
    log(f"[{name}] C4 analogue {side}: {miss} of {len(fixed)} fixed cells miss -> {'PASS' if miss >= 15 else 'FAIL'}")
else:
    parts = {}
    for spec in rest:
        sk, tag = spec.split("=")
        meta = json.loads((HERE / "s1" / f"{tag}.json").read_text())
        net = torch.load(HERE / "nets" / f"{tag}.pt", weights_only=False)
        parts[sk] = (net, meta["rung"])
    asm = lsr.Assembly(side, parts)
    log(f"[{name}] {side}: " + ", ".join(f"{sk}@{r}" for sk, (_, r) in parts.items()))
    out = stage2.full_replay(side, asm, name, log=log, complete=complete)
    out["assembly"] = {sk: spec.split("=")[1] for sk, spec in zip(parts, rest)}
    out["trigger_set"] = sorted(stage2.trigger_set(out, list(lsr.SKILLS[side]))) if out["verdict"] == "FAIL" else []
    log(f"[{name}] trigger set {out['trigger_set']}")
json.dump(out, open(HERE / "s2" / f"{name}.json", "w"), indent=1, default=float)
print("done")
