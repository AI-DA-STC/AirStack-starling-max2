"""Collect Stage 1 fits and Stage 2 replays into summary.md (tables) and summary.json."""
import json, glob, os
out = {"fits": [], "replays": []}
lines = ["## Stage 1 fits (own held-out rows; max over active channels; rounds 0 / 3)", "",
         "| Fit | Skill | Rung | Seed | Screen | r2 bias | r3 turn deg | r4 scale | r5 | r6 tail | r7 | Fit s |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for f in sorted(glob.glob("s1/*.json")):
    d = json.load(open(f))
    if "marks" not in d or "skill" not in d:
        continue
    m0, m3 = d["marks"]["0"], d["marks"]["3"]
    mx = lambda m, k: max(abs(x) for x in m[k]) if m[k] else float("nan")
    row = {"tag": d["tag"], "skill": d["skill"], "rung": d["rung"], "seed": d["seed"], "schedule": d["schedule"],
           "screen": d["screen_rmse"], "r2": [mx(m0, "r2_bias"), mx(m3, "r2_bias")], "r3": [m0["r3_turn_deg"], m3["r3_turn_deg"]],
           "r4": [m0["r4_scale"], m3["r4_scale"]], "r5": [mx(m0, "r5_rmse_debiased"), mx(m3, "r5_rmse_debiased")],
           "r6": [m0["r6_tail"], m3["r6_tail"]], "r7": [mx(m0, "r7_rmse"), mx(m3, "r7_rmse")], "secs": d["fit_seconds"]}
    out["fits"].append(row)
    rung = d["rung"] + (" const lr" if d["schedule"] == "const" else "")
    lines.append(f"| {d['tag']} | {d['skill']} | {rung} | {d['seed']} | {d['screen_rmse']:.4f} | {row['r2'][0]:.4f} / {row['r2'][1]:.4f} | "
                 f"{row['r3'][0]:+.2f} / {row['r3'][1]:+.2f} | {row['r4'][0]:.4f} / {row['r4'][1]:.4f} | {row['r5'][0]:.4f} / {row['r5'][1]:.4f} | "
                 f"{row['r6'][0]:.4f} / {row['r6'][1]:.4f} | {row['r7'][0]:.4f} / {row['r7'][1]:.4f} | {d['fit_seconds']:.0f} |")
lines += ["", "## Joint control arms (C-head, C-one): screen per skill", ""]
for f in sorted(glob.glob("s1/C*_*.json")):
    d = json.load(open(f))
    if "shape" in d:
        lines.append(f"- {d['tag']}: " + ", ".join(f"{k} {v:.4f}" for k, v in d["screen"].items()))
lines += ["", "## Stage 2 replays", "", "| Replay | Verdict | Gated | Over 30 | Max | Median | Over 20 | Pooled ci | Failures | Trigger set | Minutes |", "|---|---|---|---|---|---|---|---|---|---|---|"]
for f in sorted(glob.glob("s2/*.json")):
    d = json.load(open(f))
    if "verdict" not in d:
        continue
    ci = (d.get("pooled") or {}).get("ci") or [0, 0]
    out["replays"].append({k: d[k] for k in ("tag", "side", "verdict", "gated_played", "over30", "max_flips", "median", "over20", "failures", "assembly", "trigger_set")} | {"pooled_ci": ci, "seconds": d["seconds"]})
    lines.append(f"| {d['tag']} | {d['verdict']} | {d['gated_played']} | {d['over30']} | {d['max_flips']} | {d['median']:g} | {d['over20']} | "
                 f"[{ci[0]:+.4f}, {ci[1]:+.4f}] | {len(d['failures'])} | {', '.join(d['trigger_set']) or '—'} | {d['seconds']/60:.0f} |")
    lines.append(f"|  | assembly: {'; '.join(f'{k}={v}' for k, v in d['assembly'].items())} | | | | | | | | | |")
open("summary.md", "w").write("\n".join(lines) + "\n")
json.dump(out, open("summary.json", "w"), indent=1)
print("\n".join(lines))
