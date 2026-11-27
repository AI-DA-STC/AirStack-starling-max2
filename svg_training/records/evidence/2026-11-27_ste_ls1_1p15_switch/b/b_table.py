"""Step B (LS1_1P15_SWITCH.md): every scripted cell of the read, the side's win share at 1.6 m (T94's stored script
games) and at 1.15 m (step C). Writes b_table.json and b_table.md. usage: b_table.py"""
import json, sys
from pathlib import Path
import numpy as np
SVG = Path.home() / "AirStack-starling-max2-dev" / "svg_training"
sys.path.insert(0, str(SVG / "source"))
from svg_training.ste import scoring
from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
HERE = Path(__file__).parent
FOLD = {"1.6": "runs/2026-11-26_ste_ls12_read_{}", "1.15": "runs/2026-11-27_ste_ls12_1p15_scripts_{}"}
WIN = {"guard": GUARD_WIN, "strike": STRIKE_WIN}


def cells_of(side, tag):
    run = SVG / FOLD[tag].format(side)
    lay = json.loads((run / "layout.json").read_text())["batches"]
    out = {}
    for b in lay:
        if not b["name"].startswith(("c1_scripts", "c1m_scripts", "r2_scripts")):
            continue
        pg = scoring.load_batch(run / "games" / f"{b['name']}.npz")
        n = b["n"]
        for i, c in enumerate(b["cells"]):
            o = np.asarray(pg["outcome"])[i * n:(i + 1) * n]
            kind = "info" if b["name"].startswith("r2") else ("fixed" if b["name"].startswith("c1_") else "mixed")
            out[(kind, tuple(c["codes"]), c["opponent"])] = {"wins": int((o == WIN[side]).sum()), "n": n,
                                                             "mean_end": float(np.mean(pg["end_step"][i * n:(i + 1) * n]))}
    return out


res, md = {}, ["| Side | Kind | Codes | Opponent | wins at 1.6 m | wins at 1.15 m | change |", "|---|---|---|---|---|---|---|"]
for side in ("guard", "strike"):
    a, b = cells_of(side, "1.6"), cells_of(side, "1.15")
    rows = []
    for k in sorted(set(a) | set(b)):
        ra, rb = a.get(k), b.get(k)
        rows.append({"kind": k[0], "codes": list(k[1]), "opponent": k[2], "wins_1p6": ra and ra["wins"],
                     "wins_1p15": rb and rb["wins"], "end_1p6": ra and ra["mean_end"], "end_1p15": rb and rb["mean_end"]})
    res[side] = rows
    both = [r for r in rows if r["wins_1p6"] is not None and r["wins_1p15"] is not None]
    d = np.array([r["wins_1p15"] - r["wins_1p6"] for r in both])
    lop = sum(min(r["wins_1p15"], 1000 - r["wins_1p15"]) < 100 for r in rows if r["wins_1p15"] is not None)
    print(f"{side}: {len(rows)} cells ({len(both)} at both tags); wins change median {np.median(d):+.0f}, "
          f"min {d.min():+d}, max {d.max():+d}; cells within 100 of 0 or 1,000 at 1.15 m: {lop}")
    for r in rows:
        ch = "" if r["wins_1p6"] is None or r["wins_1p15"] is None else f"{r['wins_1p15'] - r['wins_1p6']:+d}"
        md.append(f"| {side} | {r['kind']} | {','.join(r['codes'])} | {r['opponent']} | {r['wins_1p6']} | {r['wins_1p15']} | {ch} |")
json.dump(res, open(HERE / "b_table.json", "w"), indent=1)
(HERE / "b_table.md").write_text("\n".join(md) + "\n")
print("done")
