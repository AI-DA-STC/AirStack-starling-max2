"""Stage 2 (LS1_REDESIGN.md 4.4): the closed-loop deciding read of one assembly.

full_replay(side, assembly) plays T94's network batches with the assembly: the screen cells first (any over 30 -> stop,
FAIL), then every other batch; recomputes each cell's b + c and interval, the pooled row, the command-error table from
the labeller, the median and the over-20 count, and classifies PASS / MARGINAL / FAIL against the gate limits (R48,
the gate file's [limits]) and the headroom marks (median <= 9, at most 5 gated cells over 20)."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from harness import ctx_of, net_batches, check_layout, cells, eq

HERE = Path(__file__).parent
SVG = eq.ROOT
CAL_ARM = {"guard": "bias=0.01", "strike": "noise=0.05"}


def key(codes, opponent):
    return (tuple(codes), opponent)


def screen_cells(side: str) -> list:
    """Union of T94's 10 worst network cells (gated) and the 10 worst gated cells of the T90 arm nearest the team's
    binding error; written once to cells_screen.json before any pilot network plays."""
    path = HERE / "cells_screen.json"
    data = json.loads(path.read_text()) if path.is_file() else {}
    if side in data:
        return [key(c["codes"], c["opponent"]) for c in data[side]]
    t94 = json.loads((SVG / f"runs/2026-11-26_ste_ls12_read_{side}/results.json").read_text())["cells"]
    net = [c for c in t94 if c["arm"] == "net" and c["kind"] != "info"]
    worst_net = sorted(net, key=lambda c: -c["flips"])[:10]
    cal = json.loads((SVG / f"runs/2026-11-25_ste_ls15_calibration_{side}/results.json").read_text())["cells"]
    arm = [c for c in cal if c["arm"] == CAL_ARM[side] and c["kind"] != "info"]
    gated = {key(c["codes"], c["opponent"]) for c in net}
    worst_cal = [c for c in sorted(arm, key=lambda c: -c["flips"]) if key(c["codes"], c["opponent"]) in gated][:10]
    out, seen = [], set()
    for c in worst_net + worst_cal:
        k = key(c["codes"], c["opponent"])
        if k not in seen:
            seen.add(k); out.append({"codes": list(k[0]), "opponent": k[1]})
    data[side] = out
    path.write_text(json.dumps(data, indent=1))
    return [key(c["codes"], c["opponent"]) for c in out]


def classify(gated_rows, pooled, errors, limits):
    fails = eq.limit_failures(gated_rows, pooled, errors, limits)
    flips = sorted(r["flips"] for r in gated_rows)
    median = float(np.median(flips))
    over20 = sum(f > 20 for f in flips)
    head = median <= 9 and over20 <= 5
    verdict = "FAIL" if fails else ("PASS" if head else "MARGINAL")
    return verdict, fails, median, over20


def full_replay(side: str, net, tag: str, log=print, complete: bool = False) -> dict:
    """complete: play every batch even after a screen stop (for the rescue's 'completed in full')."""
    ctx = ctx_of(side)
    bs = net_batches(ctx)                      # gated (r1) and info (r2) network batches, T94's layout
    check_layout(ctx, bs)
    reader = eq.Reader(ctx, eq.plan_batches(ctx))
    ctx.net, ctx.net_sha = net, "pilot"
    scr = set(screen_cells(side))
    first = [b for b in bs if any(key(c.choice["flies"], c.opponent) in scr for c in b.cells)]
    rest = [b for b in bs if b not in first]
    rows, accs, arm_pgs, ref_pgs, kinds = [], [], {}, {}, {}
    players = list(ctx.spec.players)
    stopped = False
    t0 = time.time()
    for stage, group in (("screen", first), ("rest", rest)):
        if stopped and not complete:
            break
        for b in group:
            pg = eq.play_batch(ctx, b, reader, None, lambda: False)
            for i, c in enumerate(b.cells):
                mine = eq.exploit.slice_cell(pg, i, ctx.n)
                ref = reader.reference(c)
                e = eq.cell_entry(mine, ref, side, ctx.z_cell)
                row = {"kind": c.kind, "codes": list(c.choice["flies"]), "opponent": c.opponent, "b": int(e["b"]),
                       "c": int(e["c"]), "flips": int(e["flips"]), "diff": float(e["diff"]), "ci": e["ci"],
                       "screen": key(c.choice["flies"], c.opponent) in scr}
                rows.append(row)
                arm_pgs[c.index], ref_pgs[c.index], kinds[c.index] = mine, ref, c.kind
                if c.kind != cells.INFO:
                    accs.append(eq.acc_of(pg, i, players))
        if stage == "screen":
            bad = [r for r in rows if r["screen"] and r["kind"] != cells.INFO and r["flips"] > 30]
            log(f"  [{tag}] screen: {sum(r['screen'] for r in rows)} screen cells, {len(bad)} over 30 "
                f"({time.time() - t0:.0f} s)")
            if bad:
                stopped = True
    gated = [r for r in rows if r["kind"] != cells.INFO]
    gk = {k: v for k, v in kinds.items() if v != cells.INFO}
    read = eq.interval_step({k: arm_pgs[k] for k in gk}, {k: ref_pgs[k] for k in gk}, gk, side, ctx.alpha, ctx.m)
    errors = eq.arm_errors(ctx, accs)
    if stopped:
        verdict, fails = "FAIL", [f"screen stop: {sum(r['flips'] > 30 for r in gated)} screen cells over 30"]
        median = float(np.median([r["flips"] for r in gated])); over20 = sum(r["flips"] > 20 for r in gated)
        if complete:
            verdict, fails, median, over20 = classify(gated, read["pooled"]["all"], errors, ctx.g.limits)
            verdict = "FAIL"
    else:
        verdict, fails, median, over20 = classify(gated, read["pooled"]["all"], errors, ctx.g.limits)
    out = {"tag": tag, "side": side, "verdict": verdict, "screen_stop": stopped, "cells_played": len(rows),
           "gated_played": len(gated), "over30": sum(r["flips"] > 30 for r in gated),
           "max_flips": max(r["flips"] for r in gated), "median": median, "over20": over20,
           "pooled": read["pooled"]["all"], "failures": fails,
           "errors": {s: {"rmse": e.get("rmse"), "max_abs": e.get("max_abs"), "active": e.get("active"),
                          "rows": e.get("rows")} for s, e in errors["skills"].items()},
           "rows": rows, "seconds": time.time() - t0}
    log(f"  [{tag}] {side}: {verdict}; gated played {len(gated)}; over 30 {out['over30']}; max {out['max_flips']}; "
        f"median {median}; over 20 {over20}; pooled ci {[round(x, 4) for x in (out['pooled'] or {}).get('ci', [0, 0])]}; "
        f"failures {len(fails)} ({time.time() - t0:.0f} s)")
    return out


def pooled_contrib(rows, side, players, m):
    """c_k = (1/m) sum_cells diff x n_k,cell / 3 over gated cells."""
    g = [r for r in rows if r["kind"] != cells.INFO]
    return {s: sum(r["diff"] * r["codes"].count(s) / 3 for r in g) / max(m, 1) for s in players}


def trigger_set(rep: dict, players: list) -> set:
    """4.4's trigger set from a failing replay."""
    gated = [r for r in rep["rows"] if r["kind"] != cells.INFO]
    out = set()
    if rep["screen_stop"]:
        off = [r for r in gated if r["screen"] and r["flips"] > 30]
    else:
        off = [r for r in gated if r["flips"] > 30 or not (-0.045 <= r["ci"][0] and r["ci"][1] <= 0.045)]
    if off:
        cnt = {s: sum(s in r["codes"] for r in off) for s in players}
        half = {s for s, c in cnt.items() if c >= len(off) / 2}
        if half:
            out |= half
        else:
            top = max(cnt.values()); out |= {s for s, c in cnt.items() if c == top}
    for f in rep["failures"]:
        if f.startswith(("cmd_rmse_max", "cmd_unused_max_abs", "cmd_zero_skill_max_abs")):
            for s in players:
                if f" {s} " in f + " " or f": {s}" in f:
                    out.add(s)
        if f.startswith("pooled_margin"):
            m = len(gated)
            c = pooled_contrib(rep["rows"], rep["side"], players, m)
            sign = np.sign(sum(r["diff"] for r in gated))
            cand = {s: v for s, v in c.items() if np.sign(v) == sign}
            if cand:
                top = max(abs(v) for v in cand.values())
                out |= {s for s, v in cand.items() if abs(v) == top}
    return out
