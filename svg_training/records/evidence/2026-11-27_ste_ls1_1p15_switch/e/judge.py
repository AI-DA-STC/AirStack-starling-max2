"""Step E of ste_learning/drafts/LS1_1P15_SWITCH.md, judged once (plan section 3), after the owner ruled the 1.15 m
limits (R52, 27 Nov 2026). Reads E's sealed per-assembly files, the two script-oracle files, the 1.15 m gate file (R52's
limits, sha pinned below), step B's table (hold rates at 1.6 and 1.15 m) and step D's calibration (the noise 0.02 arm per
cell). Classifies as LS1_REDESIGN.md 4.4 with the built rule (scripts/ste_ls1_equivalence.py limit_failures /
cell_failures): FAIL if a gate limit is missed; else PASS if median changed games over gated cells <= 9 and at most 5
gated cells over 20 (headroom marks fixed in the plan, not moved); else MARGINAL. Team result: the worse of two seeds
(Guard S1; Strike S2 decides, Strike S1 is seed 1 only and reported). Controls: the script-oracle arm PASS; the C4
analogue misses at least unfitted_min_miss_cells of the 30 fixed cells. Read-only on its inputs.

usage (from svg_training/, PYTHONPATH=source):
  judge.py <E folder (sealed/ and oracle_*.json)> <D main run dir with SIDE> <out.json> <out.md>"""
import hashlib
import json
import sys
import tomllib
from pathlib import Path

import numpy as np

sys.path.insert(0, "scripts")
import ste_ls1_equivalence as eq  # noqa: E402

GATES = Path("configs/ste_ls1/distil_gates_1p15.toml")
GATES_SHA = "d5fdd0135e757f0fb0b462cc5291de476fb961745133508e360448ae5f91cfae"   # R52 filled
B_TABLE = Path("records/evidence/2026-11-27_ste_ls1_1p15_switch/b/b_table.json")
ASSEMBLIES = {"guard": [("S1", 1), ("S1", 2)], "strike": [("S2", 1), ("S2", 2), ("S1", 1)]}
DECIDES = {"guard": "S1", "strike": "S2"}
RANK = {"PASS": 0, "MARGINAL": 1, "FAIL": 2}
PILOTS = Path("records/evidence/2026-11-27_ste_ls1_redesign_pilots")   # the same networks judged at 1.6 m (s2/, s1/)
GAME = ("configs/ste_l011/tag_1p15.toml", "b2e09683f7088964a7d1ca15dfc9c98d1e04c15e96b14196d6971afb75f27580")

e_dir, d_dir, out_json, out_md = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
assert hashlib.sha256(GATES.read_bytes()).hexdigest() == GATES_SHA, "gate file is not R52's"
G = tomllib.loads(GATES.read_text())
limits, need_c4 = G["limits"], G["controls"]["unfitted_min_miss_cells"]


def key(codes, opp):
    return ("+".join(codes), opp)


def classify(gated, pooled, errors):
    fails = eq.limit_failures(gated, pooled, errors, limits)
    flips = [r["flips"] for r in gated]
    median, over20 = float(np.median(flips)), sum(f > 20 for f in flips)
    verdict = "FAIL" if fails else ("PASS" if median <= 9 and over20 <= 5 else "MARGINAL")
    return verdict, fails, median, over20


btab = json.loads(B_TABLE.read_text())
report = {"gates": str(GATES), "gates_sha256": GATES_SHA, "limits": limits, "controls": {}, "assemblies": {},
          "teams": {}, "cells": {}}
md = []
for side in ("guard", "strike"):
    oracle = json.loads((e_dir / f"oracle_{side}.json").read_text())
    c4 = json.loads((e_dir / "sealed" / f"c4_{side}.json").read_text())
    fixed = [r for r in c4["rows"] if r["kind"] == "fixed"]
    miss = sum(1 for r in fixed if eq.cell_failures(r, limits))
    report["controls"][side] = {"oracle_pass": bool(oracle["oracle_pass"]), "c4_fixed_cells": len(fixed),
                                "c4_miss": miss, "c4_pass": miss >= need_c4 and len(fixed) == 30}
    hold = {key(r["codes"], r["opponent"]): (r["wins_1p6"], r["wins_1p15"]) for r in btab[side]}
    D = json.loads(Path(d_dir.replace("SIDE", side), "results.json").read_text())
    d002 = {key(r["codes"], r["opponent"]): r["flips"] for r in D["cells"] if r["arm"] == "noise=0.02"}
    per_cell = {}
    for name, seed in ASSEMBLIES[side]:
        tag = f"{name}_{side}_seed{seed}"
        S = json.loads((e_dir / "sealed" / f"{tag}.json").read_text())
        gated = [r for r in S["rows"] if r["kind"] != "info"]
        info = [r for r in S["rows"] if r["kind"] == "info"]
        verdict, fails, median, over20 = classify(gated, S["pooled"], S["errors"])
        p16 = PILOTS / "s2" / f"{tag}.json"
        P = json.loads(p16.read_text()) if p16.is_file() else None
        rungs = {sk: json.loads((PILOTS / "s1" / f"{t}.json").read_text())["rung"] for sk, t in S["assembly"].items()}
        rm = {s: e.get("rmse") for s, e in S["errors"]["skills"].items()}
        report["assemblies"][tag] = {"side": side, "assembly": name, "seed": seed, "verdict": verdict,
                                     "gated": len(gated), "cells_all": len(S["rows"]), "tag_m": S["tag_m"],
                                     "max_flips": max(r["flips"] for r in gated), "median": median, "over20": over20,
                                     "over30": sum(r["flips"] > 30 for r in gated),
                                     "over31": sum(r["flips"] > 31 for r in gated),
                                     "pooled_ci": (S["pooled"] or {}).get("ci"), "n_fail": len(fails),
                                     "fail_keys": sorted({f.split(":")[0] for f in fails}), "failures": fails[:40],
                                     "rmse": rm, "assembly_tags": S["assembly"], "rungs": rungs,
                                     "info_cells": len(info),
                                     "info_max": max((r["flips"] for r in info), default=None),
                                     "info_median": float(np.median([r["flips"] for r in info])) if info else None,
                                     "at_1p6": None if P is None else {
                                         "verdict": P["verdict"], "screen_stop": P["screen_stop"],
                                         "gated_played": P["gated_played"], "max_flips": P["max_flips"],
                                         "median": P["median"], "over20": P["over20"],
                                         "rmse": {k: v.get("rmse") for k, v in P["errors"].items()}}}
        p_rows = {} if P is None else {key(r["codes"], r["opponent"]): r["flips"] for r in P["rows"]}
        for r in S["rows"]:
            k = key(r["codes"], r["opponent"])
            c = per_cell.setdefault(k, {"kind": r["kind"]})
            c[tag] = r["flips"]
            c[tag + "@1.6m"] = p_rows.get(k)
    for k, c in per_cell.items():
        c["hold_1p6"], c["hold_1p15"] = hold.get(k, (None, None))
        c["d_noise_0p02"] = d002.get(k)
    report["cells"][side] = {f"{a}@{b}": v for (a, b), v in per_cell.items()}
    dec = [t for t in report["assemblies"] if t.startswith(DECIDES[side] + "_" + side)]
    worst = max((report["assemblies"][t]["verdict"] for t in dec), key=RANK.get)
    ctl_ok = report["controls"][side]["oracle_pass"] and report["controls"][side]["c4_pass"]
    report["teams"][side] = {"deciding": DECIDES[side], "seeds": dec, "result": worst if ctl_ok else "VOID",
                             "controls_ok": ctl_ok,
                             "oracle_cells": sum(int(l.split(": ")[1].split(" cells")[0]) for l in
                                                 (e_dir / "logs" / f"oracle_{side}.log").read_text().splitlines()
                                                 if " cells, " in l and l.strip().startswith("c2_oracle"))}

# ---- markdown
def lopsided(c):
    h = c["hold_1p15"]
    return h is not None and (h < 100 or h > 900)


md.append("# Step E judged (R52 limits; plan LS1_1P15_SWITCH.md section 3)\n")
md.append("Training simulator, tier 1 (fast engine; Starling layer), CPU of the RTX 5090 workstation. Observed in the training "
          "simulator; not a flight result.\n")
tags_m = sorted({a["tag_m"] for a in report["assemblies"].values()})
md.append(f"**What was played.** The R50 pilot networks (fitted on 1.6 m rows; `{PILOTS}/s1/`, R51: no refit) replayed at "
          f"tag {tags_m} m (game `{GAME[0]}`, `{GAME[1][:8]}…`), every gated and INFO cell, 1,000 games a cell on T44's starts "
          "(seed 110000), paired with step C's stored script games. Inputs: `sealed/`, `oracle_*.json` (sha256 in "
          "`inputs.sha256`); job code `code/`; logs `logs/`.\n")
md.append(f"**Rule.** Gate file `{GATES}` (`{GATES_SHA[:8]}…`, owner R52): flips_max_games {limits['flips_max_games']}, "
          f"cell margin {limits['cell_margin']}, pooled {limits['pooled_margin']}, command error {limits['cmd_rmse_max']} / "
          f"{limits['cmd_unused_max_abs']} / {limits['cmd_zero_skill_max_abs']}; headroom median ≤ 9 and ≤ 5 gated cells over "
          "20 (plan, fixed before the run). FAIL if any gate limit is missed; else PASS if headroom holds; else MARGINAL.\n")
md.append("**Team result and the ladder.** Each team's result is its deciding assembly at the worse of two seeds: Guard S1; "
          "Strike S2 (as at 1.6 m, S2 is the assembly after an S1 FAIL; Strike S1 has seed 1 only and does not decide). No "
          "assembly above these, no own-state check and no DAgger rescue was played at 1.15 m (R51: no refit), so a FAIL "
          "here is 'the 1.6 m networks fail at 1.15 m', not a 4.4 team FAIL after the ladder.\n")
md.append("## Controls\n\n| Team | Script-oracle arm (equal to the scripts game for game) | C4 analogue (fixed cells "
          f"missed, need ≥ {need_c4} of 30) |\n|---|---|---|")
for side, c in report["controls"].items():
    md.append(f"| {side} | {'PASS' if c['oracle_pass'] else 'FAIL'}: 0 changed games in "
              f"{report['teams'][side]['oracle_cells']} cells | {c['c4_miss']} of {c['c4_fixed_cells']}: "
              f"{'PASS' if c['c4_pass'] else 'FAIL'} |")
md.append("\n## Assemblies at 1.15 m (1.6 m beside, the same networks)\n\n| Assembly | Result | Gated cells | Over 31 | Max | "
          "Median | Over 20 | Pooled CI | Limit misses | Failed keys | At 1.6 m: result, max, median, over 20 |\n"
          "|---|---|---|---|---|---|---|---|---|---|---|")
for tag, a in report["assemblies"].items():
    ci, b = a["pooled_ci"], a["at_1p6"]
    old = "—" if b is None else (f"{b['verdict']}{' (screen stop, ' + str(b['gated_played']) + ' cells)' if b['screen_stop'] else ''}"
                                 f", {b['max_flips']}, {b['median']:g}, {b['over20']}")
    md.append(f"| {tag} | **{a['verdict']}** | {a['gated']} | {a['over31']} | {a['max_flips']} | {a['median']:g} | "
              f"{a['over20']} | {'—' if ci is None else f'[{ci[0]:+.4f}, {ci[1]:+.4f}]'} | {a['n_fail']} | "
              f"{', '.join(a['fail_keys']) or '—'} | {old} |")
md.append("\nStrike INFO cells (26, reported, not gated): " + "; ".join(
    f"{t} max {a['info_max']}, median {a['info_median']:g}" for t, a in report["assemblies"].items() if a["info_cells"]) + ".\n")
md.append("## Rungs and command error per skill (largest active-channel RMSE; limit 0.05)\n")
md.append("| Assembly | Skill | Rung | Network | RMSE 1.15 m | RMSE 1.6 m |\n|---|---|---|---|---|---|")
for tag, a in report["assemblies"].items():
    old = (a["at_1p6"] or {}).get("rmse") or {}
    for sk, net in a["assembly_tags"].items():
        r_new, r_old = a["rmse"].get(sk), old.get(sk)
        f = lambda v: "—" if not v else f"{max(v):.3f}"  # noqa: E731
        md.append(f"| {tag} | {sk} | {a['rungs'][sk]} | `{net}` | {f(r_new)} | {f(r_old)} |")
md.append("\n## Team results\n")
for side, t in report["teams"].items():
    md.append(f"- **{side}**: {t['result']} (deciding assembly {t['deciding']}, worse of seeds {', '.join(t['seeds'])}; "
              f"controls {'PASS' if t['controls_ok'] else 'FAIL, read void'})")
md.append("\n## Where the changed games are\n")
for side in ("guard", "strike"):
    dec = report["teams"][side]["seeds"]
    cells_ = {k: c for k, c in report["cells"][side].items() if c["kind"] != "info"}
    worst = lambda c: max(c.get(t) or 0 for t in dec)  # noqa: E731
    worst16 = lambda c: max((c.get(t + "@1.6m") or 0) for t in dec)  # noqa: E731
    md.append(f"**{side}** (deciding seeds {', '.join(dec)}; per cell the worse seed)\n")
    md.append("| Opponent | Cells | Max 1.15 m | Median 1.15 m | Max 1.6 m | Cells over 31 |\n|---|---|---|---|---|---|")
    for opp in sorted({k.split("@")[1] for k in cells_}):
        cs = [c for k, c in cells_.items() if k.endswith("@" + opp)]
        md.append(f"| {opp} | {len(cs)} | {max(map(worst, cs))} | {np.median(list(map(worst, cs))):g} | "
                  f"{max(map(worst16, cs))} | {sum(worst(c) > limits['flips_max_games'] for c in cs)} |")
    lop = [c for c in cells_.values() if lopsided(c)]
    rest = [c for c in cells_.values() if not lopsided(c)]
    md.append(f"\nLopsided cells (scripts win under 100 or over 900 of 1,000 at 1.15 m): {len(lop)} of {len(cells_)}; "
              f"median of the worse seed over them {np.median(list(map(worst, lop))) if lop else float('nan'):g}, over "
              f"the other {len(rest)} cells {np.median(list(map(worst, rest))):g}.")
    above = sum(worst(c) > (c["d_noise_0p02"] or 0) for c in cells_.values())
    md.append(f"Against D's noise 0.02 arm (the near-miss noise the gate must let through, C7): the network "
              f"changes more games than that arm in {above} of {len(cells_)} cells; the arm's own max is "
              f"{max(c['d_noise_0p02'] for c in cells_.values())} and median "
              f"{np.median([c['d_noise_0p02'] for c in cells_.values()]):g}, so the ruler still sees changes at 1.15 m.\n")
md.append("## Failures (first 40 per assembly)\n")
for tag, a in report["assemblies"].items():
    if a["failures"]:
        md.append(f"**{tag}** ({a['n_fail']} misses)\n")
        md += [f"- {f}" for f in a["failures"]]
        md.append("")
md.append("## Every cell (changed games at 1.15 m and 1.6 m per seed; script wins of the team at 1.6 m and 1.15 m; D noise 0.02)\n")
for side in ("guard", "strike"):
    tags = [t for t in report["assemblies"] if report["assemblies"][t]["side"] == side]
    md.append(f"**{side}**\n")
    md.append("| Cell | Kind | " + " | ".join(f"{t} 1.15 / 1.6" for t in tags) + " | wins 1.6 m | wins 1.15 m | D noise 0.02 |\n"
              "|---|---|" + "---|" * (len(tags) + 3))
    order = sorted(report["cells"][side].items(), key=lambda kv: (kv[1]["kind"] == "info", -max(kv[1].get(t) or 0 for t in tags)))
    for k, c in order:
        md.append(f"| {k} | {c['kind']} | " + " | ".join(f"{c.get(t)} / {c.get(t + '@1.6m')}" for t in tags)
                  + f" | {c['hold_1p6']} | {c['hold_1p15']} | {c['d_noise_0p02']} |")
    md.append("")
out_json.write_text(json.dumps(report, indent=1, default=float))
out_md.write_text("\n".join(md) + "\n")
for tag, a in report["assemblies"].items():
    print(f"{tag:22s} {a['verdict']:8s} max {a['max_flips']:3d} median {a['median']:4g} over20 {a['over20']:2d} "
          f"over30 {a['over30']} keys {a['fail_keys']}")
print(json.dumps(report["controls"]), json.dumps(report["teams"]))
