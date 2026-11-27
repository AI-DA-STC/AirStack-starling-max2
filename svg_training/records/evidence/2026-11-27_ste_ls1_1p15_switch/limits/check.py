"""R48's limit set judged on a calibration read (1.6 m T90/T91 or 1.15 m step D), with the built gate rule
(scripts/ste_ls1_equivalence.py limit_failures / cell_failures / miss_count). Read-only on the run folders.

usage: check.py <main run dir> <top-up run dir> <distil gate file with the limits (R48: configs/ste_ls1/distil_gates.toml)>
                <distil gate file whose [read.near_miss_cells] to use> <out.json>

Reference games of a cell = the identity arm's games in that cell (the calibration's controls identity_no_flip and
replay_t44 PASS: identity equals the reference game for game, so this is the same set of games)."""
import json
import math
import sys
import tomllib
from pathlib import Path

import numpy as np

sys.path.insert(0, "scripts")
import ste_ls1_equivalence as eq  # noqa: E402
from svg_training.ste import cells  # noqa: E402

main_dir, top_dir, lim_file, nm_file, out = map(Path, sys.argv[1:6])
L = tomllib.loads(lim_file.read_text())
limits = L["limits"]
NM = tomllib.loads(nm_file.read_text())["read"]["near_miss_cells"]


def load(d):
    r = json.loads((d / "results.json").read_text())
    return r


def key(row):
    return (tuple(row["codes"]), row["opponent"])


def nm_keys(side):
    out = []
    for c in NM[side]:
        codes = c["codes"] * 3 if len(c["codes"]) == 1 else c["codes"]
        out.append((tuple(codes), c["opponent"]))
    return out


_cache = {}


def games(d, g):
    f = d / g["file"]
    if f not in _cache:
        _cache[f] = dict(np.load(f, allow_pickle=True))
    z = _cache[f]
    s, e = g["start"], g["stop"]
    place = s // (e - s)
    return {k: z[k][s:e] for k in ("outcome",)}, {k: z[k][place] for k in ("err_sum_sq", "err_max_abs", "err_label_max_abs", "err_count")}


def side_win(side):
    return eq.GUARD_WIN if side == "guard" else eq.STRIKE_WIN


def gated(rows):
    return [r for r in rows if r["kind"] != "info"]


def as_cell(r):
    return {"codes": r.get("codes"), "opponent": r["opponent"], "flips": r["flips"], "ci": r["ci_adjusted"],
            "end_time": r.get("end_time"), "b": r["b"], "c": r["c"]}


def margin_needed(ci):
    return max(-ci[0], ci[1])


def nm_errors(d, rows, active, zero, used_only=False):
    """Per-skill error table on these cells from the batch accumulators (per slot -> the code that slot flies)."""
    acc = {}
    for r in rows:
        _, e = games(d, r["games"])
        for slot, sk in enumerate(r["codes"]):
            a = acc.setdefault(sk, {"sum_sq": [0.0] * 4, "max_abs": [0.0] * 4, "count": 0})
            a["sum_sq"] = [x + float(y) for x, y in zip(a["sum_sq"], e["err_sum_sq"][slot])]
            a["max_abs"] = [max(x, float(y)) for x, y in zip(a["max_abs"], e["err_max_abs"][slot])]
            a["count"] += int(e["err_count"][slot])
    skills = {}
    for sk, a in acc.items():
        on = active[sk]
        rmse = [math.sqrt(s / a["count"]) if a["count"] else 0.0 for s in a["sum_sq"]]
        mx = list(a["max_abs"])
        if used_only:                      # the gate's C7: noise on used channels only, the parked skill unchanged
            rmse = [x if o else 0.0 for x, o in zip(rmse, on)]
            mx = [x if o else 0.0 for x, o in zip(mx, on)]
            if sk == zero:
                rmse, mx = [0.0] * 4, [0.0] * 4
        skills[sk] = {"rmse": rmse, "max_abs": mx, "active": on, "rows": a["count"]}
    return {"skills": skills, "zero_skill": zero}


def summarise_errors(errs, zero):
    sk = {s: e for s, e in errs["skills"].items() if e.get("rows") and e.get("rmse") is not None}
    rm = max([x for s, e in sk.items() if s != zero for x, o in zip(e["rmse"], e["active"]) if o] or [0.0])
    un = max([x for s, e in sk.items() if s != zero for x, o in zip(e["max_abs"], e["active"]) if not o] or [0.0])
    zs = max(sk[zero]["max_abs"]) if zero in sk else None
    return rm, un, zs


report = {"limits_file": str(lim_file), "near_miss_file": str(nm_file), "limits": limits, "sides": {}}
for side in ("guard", "strike"):
    mdir = Path(str(main_dir).replace("SIDE", side))
    tdir = Path(str(top_dir).replace("SIDE", side))
    R = load(mdir)
    zero = (R["labels"]["zero_skills"] or [None])[0]
    active = R["labels"]["active"]
    z_cell, z_pooled = R["intervals"]["z_cell"], R["intervals"]["z_pooled"]
    S = {"z_cell": z_cell, "arms": {}, "near_miss": {}}
    rows_by_arm = {}
    for r in R["cells"]:
        rows_by_arm.setdefault(r["arm"], []).append(r)
    ident = {key(r): r for r in rows_by_arm["identity"]}
    # copy's read: every gated cell, the full set
    for arm, rows in rows_by_arm.items():
        g = gated(rows)
        a = R["arms"][arm]
        fails = eq.limit_failures([as_cell(r) for r in g], a["pooled"]["all"], a["errors"], limits)
        rm, un, zs = summarise_errors(a["errors"], zero)
        S["arms"][arm] = {"cells": len(g), "flips_max": max(r["flips"] for r in g),
                          "flips_median": float(np.median([r["flips"] for r in g])),
                          "margin_needed_max": max(margin_needed(r["ci_adjusted"]) for r in g),
                          "pooled_ci": a["pooled"]["all"]["ci"] if a["pooled"]["all"] else None,
                          "rmse_active_max": rm, "unused_max": un, "zero_max": zs,
                          "verdict": "stops" if fails else "lets through",
                          "fail_keys": sorted({f.split(":")[0] for f in fails}), "n_fail": len(fails)}
    # near-miss cells
    want = nm_keys(side)
    for src_dir, src in ((mdir, R), (tdir, load(tdir) if (tdir / "results.json").is_file() else None)):
        if src is None:
            continue
        by = {}
        for r in src["cells"]:
            by.setdefault(r["arm"], []).append(r)
        sid = {key(r): r for r in by["identity"]}
        for arm, rows in by.items():
            if arm == "identity" or arm in S["near_miss"]:
                continue
            kind = src["arms"][arm]["kind"]
            nm = [r for r in gated(rows) if key(r) in want]
            if not nm:
                continue
            arm_w = {i: games(src_dir, r["games"])[0]["outcome"] == side_win(side) for i, r in enumerate(nm)}
            ref_w = {i: games(src_dir, sid[key(r)]["games"])[0]["outcome"] == side_win(side) for i, r in enumerate(nm)}
            pooled = cells.pooled_difference(arm_w, ref_w, z_pooled)
            noise = kind == "noise"
            errs = nm_errors(src_dir, nm, active, zero, used_only=noise)
            fails = eq.limit_failures([as_cell(r) for r in nm], pooled, errs, limits)
            rm, un, zs = summarise_errors(errs, zero)
            S["near_miss"][arm] = {"kind": kind, "cells": len(nm),
                                   "cell_list": [f"{'+'.join(r['codes'])}@{r['opponent']}: b{r['b']} c{r['c']}" for r in nm],
                                   "flips_max": max(r["flips"] for r in nm),
                                   "margin_needed_max": max(margin_needed(r["ci_adjusted"]) for r in nm),
                                   "pooled_needed": margin_needed(pooled["ci"]) if pooled else None,
                                   "pooled": pooled, "rmse_active_max": rm, "unused_max": un, "zero_max": zs,
                                   "outcome": "FAIL" if fails else "pass", "fail_keys": sorted({f.split(":")[0] for f in fails}),
                                   "failures": fails[:6]}
    # permuted (C3) and identity width
    perm = [{**as_cell(c), "codes": [c["code"]] * 3} for c in R["permuted"]["cells"]]
    S["permuted_miss"] = eq.miss_count(perm, limits)
    S["permuted_cells"] = len(perm)
    S["permuted_near"] = sorted(((margin_needed(c["ci_adjusted"]), c["flips"], f"{c['code']} flies {c['flies']} v {c['opponent']}")
                                 for c in R["permuted"]["cells"] if not eq.cell_failures({**as_cell(c), "codes": [c['code']] * 3}, limits)),
                                reverse=True)[:3]
    S["identity_width_max"] = max(margin_needed(r["ci_adjusted"]) for r in gated(rows_by_arm["identity"]))
    report["sides"][side] = S

Path(out).write_text(json.dumps(report, indent=1, default=float))
for side, S in report["sides"].items():
    print(f"== {side}: permuted miss {S['permuted_miss']}/{S['permuted_cells']}; identity width {S['identity_width_max']:.4f}")
    for arm, v in S["near_miss"].items():
        print(f"  NM {arm:28s} {v['cells']} cells flips {v['flips_max']:4d} cm {v['margin_needed_max']:.4f} "
              f"pm {v['pooled_needed']:.4f} rmse {v['rmse_active_max']:.4f} zero {v['zero_max']} -> {v['outcome']} {v['fail_keys']}")
    for arm, v in S["arms"].items():
        print(f"  ALL {arm:27s} flips {v['flips_max']:4d} cm {v['margin_needed_max']:.4f} rmse {v['rmse_active_max']:.4f} "
              f"un {v['unused_max']:.4f} z {v['zero_max']} -> {v['verdict']} {v['fail_keys']}")
