"""Step E of ste_learning/drafts/LS1_1P15_SWITCH.md (R51): last night's pilot networks replayed at the 1.15 m tag in
every gated and info network batch of the read (no screen list), paired with step C's stored script games.

SEALED (plan section 3): per-cell rows, the interval read and the command-error table go to sealed/<name>.json; the
log prints only batch names and seconds, never a changed-game count or a verdict. Judged once, after the owner rules
the 1.15 m limits.
usage:
  e_run.py <name> <side> <skill>=<fit tag> [...]   an assembly (as the R50 pilots' s2run.py)
  e_run.py <name> <side> --unfitted                the C4 analogue (unfitted R2 assembly, seed 150003, all-ones mask),
                                                   the 30 fixed gated cells (sealed too)
  e_run.py <name> <side> --oracle                  the script-oracle arm (stage c2): equals the scripted arm game for
                                                   game in every cell (a control, printed)"""
import json
import sys
import time
from pathlib import Path

import torch

import lsr
from harness import ctx_of, net_batches, cells, eq

torch.set_num_threads(6)
HERE = Path(__file__).parent
SEALED = HERE / "sealed"
SEALED.mkdir(exist_ok=True)
name, side, rest = sys.argv[1], sys.argv[2], sys.argv[3:]


def log(s):
    print(s, flush=True)


ctx = ctx_of(side)
batches_all = eq.plan_batches(ctx)
reader = eq.Reader(ctx, batches_all)
t_start = time.time()

if rest == ["--oracle"]:
    bs = [b for b in batches_all if b.stage == eq.STAGE_C2]
    ok = True
    for b in bs:
        t0 = time.perf_counter()
        pg = eq.play_batch(ctx, b, reader, None, lambda: False)
        ctl = eq.batch_control(ctx, b, pg, reader)
        ok &= ctl["status"] == "PASS"
        log(f"  {b.name}: {len(b.cells)} cells, {time.perf_counter() - t0:.0f} s, {ctl['status']} ({ctl['detail']})")
    json.dump({"name": name, "side": side, "oracle_pass": ok, "seconds": time.time() - t_start},
              open(HERE / f"{name}.json", "w"), indent=1)
    log(f"[{name}] script-oracle arm {side}: {'PASS' if ok else 'FAIL'}")
    sys.exit(0)

if rest == ["--unfitted"]:
    train, _ = lsr.load_rows(side, n_train=50_000)
    parts = {}
    for sk in lsr.SKILLS[side]:
        torch.manual_seed(150003)
        x, fr, ex = lsr.feats_chunked(train["obs"], train["slot"], side, sk, "R2")
        net = lsr.SkillMLP(x.shape[1], lsr.out_dim_of(sk), 1, [128, 128, 128], x.mean(0), x.std(0).clamp(min=0.01),
                           ((x == 0) | (x == 1)).all(0))
        net.register_buffer("out_mask", torch.ones(4))
        parts[sk] = (net.eval().requires_grad_(False), "R2")
    bs = [b for b in net_batches(ctx, info=False) if all(c.kind == cells.FIXED for c in b.cells)]
    assembly = {sk: "unfitted" for sk in parts}
else:
    parts = {}
    for spec in rest:
        sk, tag = spec.split("=")
        meta = json.loads((HERE / "s1" / f"{tag}.json").read_text())
        parts[sk] = (torch.load(HERE / "nets" / f"{tag}.pt", weights_only=False), meta["rung"])
    bs = net_batches(ctx)                     # gated (r1) and info (r2) network batches, every cell
    assembly = {sk: spec.split("=")[1] for sk, spec in zip(parts, rest)}

asm = lsr.Assembly(side, parts)
ctx.net, ctx.net_sha = asm, "pilot"
log(f"[{name}] {side}: {len(bs)} batches; " + ", ".join(f"{sk}@{r}" for sk, (_, r) in parts.items()))
rows, accs, arm_pgs, ref_pgs, kinds = [], [], {}, {}, {}
players = list(ctx.spec.players)
for b in bs:
    t0 = time.perf_counter()
    pg = eq.play_batch(ctx, b, reader, None, lambda: False)
    for i, c in enumerate(b.cells):
        mine = eq.exploit.slice_cell(pg, i, ctx.n)
        ref = reader.reference(c)
        e = eq.cell_entry(mine, ref, side, ctx.z_cell)
        rows.append({"kind": c.kind, "codes": list(c.choice["flies"]), "opponent": c.opponent, "b": int(e["b"]),
                     "c": int(e["c"]), "flips": int(e["flips"]), "diff": float(e["diff"]), "ci": e["ci"],
                     "ref_wins": int(eq._wins(ref, side).sum()), "arm_wins": int(eq._wins(mine, side).sum())})
        arm_pgs[c.index], ref_pgs[c.index], kinds[c.index] = mine, ref, c.kind
        if c.kind != cells.INFO:
            accs.append(eq.acc_of(pg, i, players))
    log(f"  {b.name}: {len(b.cells)} cells, {time.perf_counter() - t0:.0f} s")
gk = {k: v for k, v in kinds.items() if v != cells.INFO}
read = eq.interval_step({k: arm_pgs[k] for k in gk}, {k: ref_pgs[k] for k in gk}, gk, side, ctx.alpha, ctx.m)
errors = eq.arm_errors(ctx, accs)
out = {"name": name, "side": side, "assembly": assembly, "n": ctx.n, "tag_m": float(ctx.cfg.tag.radius_m),
       "rows": rows, "pooled": read["pooled"]["all"], "errors": errors, "seconds": time.time() - t_start}
json.dump(out, open(SEALED / f"{name}.json", "w"), indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
log(f"[{name}] sealed: {len(rows)} cells written ({time.time() - t_start:.0f} s); done")
