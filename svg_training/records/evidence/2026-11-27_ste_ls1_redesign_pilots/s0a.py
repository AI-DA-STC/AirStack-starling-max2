"""Stage 0a (LS1_REDESIGN.md 4.2): harness validation. The saved LS1.1 networks must reproduce T94 cell for cell
(marks: 44 on high,straight,high v guard_mark_edge; 122 on flank x3 v guard_mirror; Guard 64 on
mark_edge,mirror,parked_centre v strike_converge), and ScriptOracle must give 0 changed games, in T94's own batches."""
import json
import sys

from harness import ctx_of, net_batches, check_layout, replay, t94_rows, cells, eq

TARGET = {"strike": ["r1_net__guard_mark_edge_04", "r1_net__guard_mirror_00"],
          "guard": ["r1_net__strike_converge_01"]}
MARKS = {("strike", ("strike_high", "strike_straight", "strike_high"), "guard_mark_edge"): 44,
         ("strike", ("strike_flank",) * 3, "guard_mirror"): 122,
         ("guard", ("guard_mark_edge", "guard_mirror", "guard_parked_centre"), "strike_converge"): 64}
out, ok = {}, True
for side in ("strike", "guard"):
    ctx = ctx_of(side)
    bs = [b for b in net_batches(ctx) if b.name in TARGET[side]]
    check_layout(ctx, bs)
    saved = ctx.net
    t94 = t94_rows(side)
    print(f"== {side}: saved LS1.1 network in {[b.name for b in bs]}", flush=True)
    rows = replay(ctx, saved, bs)
    for r in rows:
        want = t94[(r["kind"], tuple(r["codes"]), r["opponent"])]
        same = (r["b"], r["c"]) == (want["b"], want["c"])
        ok &= same
        mark = MARKS.get((side, tuple(r["codes"]), r["opponent"]))
        if mark is not None:
            ok &= r["flips"] == mark
        print(f"  {','.join(r['codes'])} v {r['opponent']}: b+c {r['b']}+{r['c']}={r['flips']} "
              f"(T94 {want['b']}+{want['c']}={want['flips']}) {'SAME' if same else 'DIFFERS'}"
              + (f"  MARK {mark}: {'PASS' if r['flips'] == mark else 'FAIL'}" if mark is not None else ""), flush=True)
    out[side + "_saved"] = rows
    print(f"== {side}: ScriptOracle in the same batches", flush=True)
    oracle = cells.ScriptOracle(ctx.cfg, side, list(ctx.spec.players), ctx.spec.drones)
    rows = replay(ctx, oracle, bs)
    zero = all(r["flips"] == 0 for r in rows)
    ok &= zero
    print(f"  oracle max flips {max(r['flips'] for r in rows)}: {'PASS' if zero else 'FAIL'}", flush=True)
    out[side + "_oracle"] = rows
json.dump(out, open(__import__("pathlib").Path(__file__).parent / "s0a.json", "w"), indent=1)
print("0a", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
