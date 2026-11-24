#!/usr/bin/env python
"""STE task L2.5: read the parked-Guard screen's run folder by the frozen spec (INFO).

    ste_l25_read.py --run-dir runs/<date>_ste_l25_screen

Applies ste_learning/drafts/L2_5_SPEC.md ("Plumbing checks", "What a failed plumbing check withholds", "Reading words",
"Paired readout") to the run's own per-game arrays (``cells/<group>__b00.npz``, one batch per group) and cell rows
(``cells/<group>__b00.json``), and quotes the driver's H, R, g*, s* from ``results.json``. Writes ``l25_readings.md`` and
``l25_readings.json`` into the run folder. Nothing is played; numbers only, no new reading. Training simulator, tier 1:
results are "observed in the training simulator".

Words (spec): two hold counts are compared by their Wilson 95 % intervals, "above" / "below" only when the intervals do
not overlap, else "not distinguishable" ("no change detected" for an on v off comparison: no change larger than this
test can see, not "no effect"). Paired cells (same Guard and Strike script, same T44 starts, same player seeds, CPU
replay) are compared game by game: outcome changes hold -> reach, reach -> hold, any other, and games with the same
outcome whose end step changed."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))

from svg_training.core.metrics import wilson_interval  # noqa: E402
from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN  # noqa: E402

BASE = "ctl_reference_replay"
RULE_SETS = {"base": BASE, "landing": "landing", "gy": "gy", "landing_gy": "landing_gy"}   # name -> group
TAG_OFF = {"landing": "ctl_tag_off_landing", "landing_gy": "ctl_tag_off_landing_gy"}
STILL, RING = "guard_parked_centre", "guard_parked_ring"
PARKED = {"still": STILL, "ring": RING}
MOVING = ["guard_mark_edge", "guard_mirror", "guard_field"]
NAMED = "guard_mark_edge"                    # the spec's named comparator (T44's g* at 1.6 m, the L0.12 opponent)
SHORT = {"guard_mark_edge": "mark_edge", "guard_mirror": "mirror", "guard_field": "field"}
OPTION_B = {"gy", "landing_gy"}
LANDING = {"landing", "landing_gy"}
P_B_WORDS = "option B not shown to reach the game"
P_C_WORDS = "landing not shown to reach the game; no landing word (reading 4) is written"
RISK_YES = "the 1.6 m tag favours a Guard team that stands still, against scripted Strikes, in this rule set"
RISK_NO = "not seen with scripted Strikes in this rule set"
NO_CHANGE = "no change detected"
FILTER_BEFORE_TAG = "Guard–Strike filter activations before a tag: not shown (not recorded by the driver)"
NO_EFFECT_NOTE = ("\"No change detected\" means no change larger than this test can see, not \"no effect\" (Wilson 95 % "
                  "intervals at 1,000 games cannot see shifts under about 40–60 games).")
# reading 3 and 4 pairs: (name, rule on, rule off)
R3_PAIRS = [("landing_gy v landing", "landing_gy", "landing"), ("gy v base", "gy", "base")]
R4_PAIRS = [("landing v base", "landing", "base"), ("landing_gy v gy", "landing_gy", "gy")]
FILTER_COLS = ("filter_active_share", "pushed_tag_share", "filter_rate", "rule_breach_rate", "closest_cross_3d_m")


# ================================================================================================ loading
def load_group(run_dir: Path, name: str) -> dict:
    """{(guard, strike): {"row": the driver's cell row, "pg": the cell's per-game arrays}} of one group (one batch)."""
    meta = json.loads((run_dir / "cells" / f"{name}__b00.json").read_text())
    z = np.load(run_dir / "cells" / f"{name}__b00.npz")
    cells = [tuple(c) for c in meta["cells"]]
    n = len(z["outcome"]) // len(cells)
    rows = {(r["guard"], r["strike"]): r for r in meta["rows"]}
    return {c: {"row": rows[c], "pg": {k: z[k][i * n:(i + 1) * n] for k in z.files}} for i, c in enumerate(cells)}


def holds(cell: dict) -> tuple[int, int]:
    out = cell["pg"]["outcome"]
    return int(np.sum(out == GUARD_WIN)), int(len(out))


# ================================================================================================ the words
def compare(k1: int, k2: int, n1: int, n2: int) -> str:
    """'above' / 'below' when the Wilson 95 % intervals of k1/n1 and k2/n2 do not overlap, else 'not distinguishable'."""
    lo1, hi1 = wilson_interval(k1, n1)
    lo2, hi2 = wilson_interval(k2, n2)
    if lo1 > hi2:
        return "above"
    if hi1 < lo2:
        return "below"
    return "not distinguishable"


def _rate(k: int, n: int) -> dict:
    lo, hi = wilson_interval(k, n)
    return {"holds": k, "games": n, "rate": k / n if n else None, "ci": [lo, hi]}


def worst(group: dict, guard: str) -> dict:
    """The guard script's worst cell (lowest hold count over the Strike scripts; first in order on a tie)."""
    cells = [(holds(c), s) for (g, s), c in group.items() if g == guard]
    (k, n), s = min(cells, key=lambda x: x[0][0])
    return {"holds": k, "games": n, "strike": s}


def _differ(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a, b = np.asarray(a), np.asarray(b)
    if a.dtype.kind == "f":
        return ~((a == b) | (np.isnan(a) & np.isnan(b)))
    return a != b


def paired(on: dict, off: dict) -> dict:
    """Discordant games of one paired cell: rule on (on) against rule off (off), game by game."""
    o1, o0 = on["pg"]["outcome"], off["pg"]["outcome"]
    same = o1 == o0
    return {"hold_to_reach": int(np.sum((o0 == GUARD_WIN) & (o1 == STRIKE_WIN))),
            "reach_to_hold": int(np.sum((o0 == STRIKE_WIN) & (o1 == GUARD_WIN))),
            "other_outcome": int(np.sum(~same & ~(((o0 == GUARD_WIN) & (o1 == STRIKE_WIN))
                                                  | ((o0 == STRIKE_WIN) & (o1 == GUARD_WIN))))),
            "same_outcome_end_step_changed": int(np.sum(same & _differ(on["pg"]["end_step"], off["pg"]["end_step"])))}


# ================================================================================================ the readings
def plumbing(groups: dict) -> dict:
    a, b = groups[TAG_OFF["landing"]], groups[TAG_OFF["landing_gy"]]
    pb = sum(int(np.sum(_differ(a[c]["pg"]["outcome"], b[c]["pg"]["outcome"])
                        | _differ(a[c]["pg"]["end_step"], b[c]["pg"]["end_step"])
                        | _differ(a[c]["pg"]["closest_3d_m"], b[c]["pg"]["closest_3d_m"]))) for c in a)
    land, base = groups["landing"], groups[BASE]
    pc = sum(int(np.sum(_differ(land[c]["pg"]["end_step"], base[c]["pg"]["end_step"])
                        | _differ(land[c]["pg"]["closest_3d_m"], base[c]["pg"]["closest_3d_m"]))) for c in land)
    games_b = sum(len(a[c]["pg"]["outcome"]) for c in a)
    games_c = sum(len(land[c]["pg"]["outcome"]) for c in land)
    return {"P-b": {"holds": pb > 0, "games_differ": pb, "games": games_b,
                    "compared": f"{TAG_OFF['landing']} v {TAG_OFF['landing_gy']}: outcome, end_step or closest_3d_m",
                    "words": "option B shown to reach the game" if pb > 0 else P_B_WORDS},
            "P-c": {"holds": pc > 0, "games_differ": pc, "games": games_c,
                    "compared": f"landing v {BASE}: end_step or closest_3d_m",
                    "words": "landing shown to reach the game" if pc > 0 else P_C_WORDS}}


def reading1(groups: dict, p_b: bool) -> dict:
    out = {}
    for rs, name in RULE_SETS.items():
        g = groups[name]
        entry = {"group": name, "known_from_t44": rs == "base", "words_withheld": (not p_b) and rs in OPTION_B}
        for label, parked in PARKED.items():
            w = worst(g, parked)
            vs = {}
            for m in MOVING:
                wm = worst(g, m)
                vs[m] = {"worst": wm, "word": _r1_word(label, compare(w["holds"], wm["holds"], w["games"], wm["games"]), m)}
            cells = []
            for (gg, s), c in g.items():
                if gg != parked:
                    continue
                k, n = holds(c)
                km, nm = holds(g[(NAMED, s)])
                cells.append({"strike": s, "parked": _rate(k, n), "mark_edge": _rate(km, nm),
                              "word": _r1_word(label, compare(k, km, n, nm), NAMED)})
            entry[label] = {"worst": w, "v": vs, "cells": cells}
        out[rs] = entry
    return out


def _r1_word(label: str, word: str, moving: str) -> str:
    tail = "not distinguishable from" if word == "not distinguishable" else word
    return f"{label} Guard {tail} {SHORT[moving]}"


def _change_word(subject: str, word: str, rule: str) -> str:
    if word == "above":
        return f"{rule} raises {subject}"
    if word == "below":
        return f"{rule} lowers it"
    return NO_CHANGE


def reading2(groups: dict, p_b: bool) -> dict:
    out = []
    for rs, off_name in TAG_OFF.items():
        on, off = groups[rs], groups[off_name]
        cells = []
        for c in off:
            k1, n1 = holds(on[c])
            k0, n0 = holds(off[c])
            cells.append({"guard": c[0], "strike": c[1], "with_tag": _rate(k1, n1), "without_tag": _rate(k0, n0),
                          "word": _change_word("the parked Guard's hold", compare(k1, k0, n1, n0), "the tag")})
        worst_words = {}
        for label, parked in PARKED.items():
            w1, w0 = worst(on, parked), worst(off, parked)
            worst_words[label] = {"with_tag": w1, "without_tag": w0, "word": _change_word(
                "the parked Guard's hold", compare(w1["holds"], w0["holds"], w1["games"], w0["games"]), "the tag")}
        out.append({"rule_set": rs, "tag_off_group": off_name, "withheld": (not p_b) and rs in OPTION_B,
                    "cells": cells, "worst": worst_words})
    return {"rule_sets": out}


def risk(r1: dict, r2: dict) -> dict:
    out = {}
    for r in r2["rule_sets"]:
        rs = r["rule_set"]
        v = r1[rs]["still"]["v"][NAMED]["word"]
        raises = r["worst"]["still"]["word"] == "the tag raises the parked Guard's hold"
        if v.startswith("still Guard below"):
            word = RISK_NO
        elif raises:
            word = RISK_YES
        else:
            word = None
        out[rs] = {"word": None if r["withheld"] else word, "reading1": v, "reading2": r["worst"]["still"]["word"],
                   "withheld": r["withheld"]}
    return out


def on_off(groups: dict, pairs: list, rule: str, withheld: dict) -> dict:
    out = []
    for name, on_rs, off_rs in pairs:
        on, off = groups[RULE_SETS[on_rs]], groups[RULE_SETS[off_rs]]
        cells, by_guard = [], {}
        total = {"hold_to_reach": 0, "reach_to_hold": 0, "other_outcome": 0, "same_outcome_end_step_changed": 0}
        for c in on:
            k1, n1 = holds(on[c])
            k0, n0 = holds(off[c])
            p = paired(on[c], off[c])
            cells.append({"guard": c[0], "strike": c[1], "on": _rate(k1, n1), "off": _rate(k0, n0),
                          "word": _change_word("the Guard team's hold", compare(k1, k0, n1, n0), rule), "paired": p,
                          "on_cols": {k: on[c]["row"].get(k) for k in FILTER_COLS},
                          "off_cols": {k: off[c]["row"].get(k) for k in FILTER_COLS}})
            g = by_guard.setdefault(c[0], dict.fromkeys(total, 0))
            for k in total:
                g[k] += p[k]
                total[k] += p[k]
        words = {}
        for cell in cells:
            words.setdefault(cell["guard"], {}).setdefault(cell["word"], 0)
            words[cell["guard"]][cell["word"]] += 1
        out.append({"name": name, "on": on_rs, "off": off_rs, "withheld": withheld.get(name, False), "cells": cells,
                    "words_by_guard": words, "paired_by_guard": by_guard, "paired_total": total})
    return {"pairs": out}


def read_run(run_dir: Path) -> dict:
    names = set(RULE_SETS.values()) | set(TAG_OFF.values())
    groups = {n: load_group(run_dir, n) for n in names}
    plumb = plumbing(groups)
    p_b, p_c = plumb["P-b"]["holds"], plumb["P-c"]["holds"]
    withheld = []
    if not p_b:
        withheld.append("P-b failed: reading 3 entirely; the option B rows of reading 2; reading 1's words for gy and "
                        "landing_gy; reading 4's landing_gy v gy pair")
    if not p_c:
        withheld.append("P-c failed: reading 4 entirely; reading 3's landing_gy v landing pair")
    r1 = reading1(groups, p_b)
    r2 = reading2(groups, p_b)
    r3 = on_off(groups, R3_PAIRS, "option B", {"landing_gy v landing": (not p_b) or (not p_c), "gy v base": not p_b})
    r3["withheld"] = not p_b
    r4 = on_off(groups, R4_PAIRS, "landing", {"landing v base": not p_c, "landing_gy v gy": (not p_c) or (not p_b)})
    r4["withheld"] = not p_c
    results = run_dir / "results.json"
    driver = {}
    if results.is_file():
        sl = json.loads(results.read_text())["shortlist"]
        for v in sl["variants"] + sl.get("info_reference", []):
            driver[v["variant"]] = {k: v.get(k) for k in ("H", "R", "g_star", "s_star")}
    return {"spec": "ste_learning/drafts/L2_5_SPEC.md", "run_dir": f"runs/{run_dir.name}", "plumbing": plumb, "withheld": withheld,
            "landing_label": None if p_c else "landing not shown to reach the game",
            "option_b_label": None if p_b else P_B_WORDS, "reading1": r1, "reading2": r2, "risk": risk(r1, r2),
            "reading3": r3, "reading4": r4, "driver_shortlist": driver, "filter_before_tag": FILTER_BEFORE_TAG,
            "no_effect_note": NO_EFFECT_NOTE}


# ================================================================================================ the page
def _pct(r: dict) -> str:
    return f"{r['holds']} ({100 * r['ci'][0]:.1f}–{100 * r['ci'][1]:.1f} %)"


def _w(w: dict) -> str:
    lo, hi = wilson_interval(w["holds"], w["games"])
    return f"{w['holds']} of {w['games']} v {w['strike']} ({100 * lo:.1f}–{100 * hi:.1f} %)"


def _num(v) -> str:
    return "n/a" if v is None else f"{v:.3f}"


def render(out: dict) -> str:
    L = ["# L2.5 readings (INFO): the parked-Guard screen read by its frozen spec", "",
         f"Spec `{out['spec']}`; run `{out['run_dir']}`. Training simulator, tier 1, scripted players, T44's 1,000 3v3 "
         "starts, CPU; observed in the training simulator. Hold = Guard team wins of 1,000 games (Wilson 95 %).", "",
         NO_EFFECT_NOTE, "", "## Plumbing checks (read first)", "",
         "| Check | Compared | Games that differ | Result |", "|---|---|---|---|"]
    for k in ("P-b", "P-c"):
        p = out["plumbing"][k]
        L.append(f"| {k} | {p['compared']} | {p['games_differ']} of {p['games']} | {p['words']} |")
    L += ["", "Withheld: " + ("; ".join(out["withheld"]) if out["withheld"] else "nothing (both checks hold)."), ""]
    L += ["## Reading 1: still Guard v the moving scripts", "",
          "Worst-cell hold of each parked script against each moving script's worst-cell hold; mark_edge is the named "
          "comparator. Base is T44's game (answer known), shown beside the new-rule sets.", "",
          "| Rule set | Parked | Its worst cell | v mark_edge (worst cell) | v mirror | v field |", "|---|---|---|---|---|---|"]
    for rs, e in out["reading1"].items():
        for label in PARKED:
            p = e[label]
            words = [f"{p['v'][m]['word']}: {_w(p['v'][m]['worst'])}" if not e["words_withheld"]
                     else f"(withheld) {_w(p['v'][m]['worst'])}" for m in MOVING]
            tag = " (T44, known)" if e["known_from_t44"] else ""
            L.append(f"| {rs}{tag} | {label} | {_w(p['worst'])} | " + " | ".join(words) + " |")
    L += ["", "Per Strike script, parked v mark_edge (same batch):", "",
          "| Rule set | Strike | still | mark_edge | word | ring | word |", "|---|---|---|---|---|---|---|"]
    for rs, e in out["reading1"].items():
        for cs, cr in zip(e["still"]["cells"], e["ring"]["cells"]):
            ws = cs["word"] if not e["words_withheld"] else "(withheld)"
            wr = cr["word"] if not e["words_withheld"] else "(withheld)"
            L.append(f"| {rs} | {cs['strike']} | {_pct(cs['parked'])} | {_pct(cs['mark_edge'])} | {ws} | "
                     f"{_pct(cr['parked'])} | {wr} |")
    d = out["driver_shortlist"]
    if d:
        L += ["", "The driver's maximin (results.json): " + "; ".join(
            f"{k}: H {v['H']}, R {v['R']}, g* {v['g_star']}, s* {v['s_star']}" for k, v in d.items()) + "."]
    L += ["", "## Reading 2: with and without the tag (parked Guards)", "",
          "| Rule set | Parked | Worst cell with the tag | Worst cell without | Word |", "|---|---|---|---|---|"]
    for r in out["reading2"]["rule_sets"]:
        for label, w in r["worst"].items():
            word = w["word"] if not r["withheld"] else "(withheld: " + P_B_WORDS + ")"
            L.append(f"| {r['rule_set']} | {label} | {_w(w['with_tag'])} | {_w(w['without_tag'])} | {word} |")
    L += ["", "| Rule set | Guard | Strike | With the tag | Without | Word |", "|---|---|---|---|---|---|"]
    for r in out["reading2"]["rule_sets"]:
        for c in r["cells"]:
            word = c["word"] if not r["withheld"] else "(withheld)"
            L.append(f"| {r['rule_set']} | {c['guard']} | {c['strike']} | {_pct(c['with_tag'])} | {_pct(c['without_tag'])}"
                     f" | {word} |")
    L += ["", "**The risk word** (landing and landing_gy, both readings needed):", ""]
    for rs, v in out["risk"].items():
        word = v["word"] if v["word"] else "no risk word: the two readings side by side"
        L.append(f"- {rs}: **{word}** (reading 1: {v['reading1']}; reading 2: {v['reading2']})"
                 + (" (withheld)" if v["withheld"] else ""))
    for title, key in (("Reading 3: option B on and off (P2)", "reading3"), ("Reading 4: landing on and off (P7, landing "
                                                                              "part)", "reading4")):
        L += ["", f"## {title}", ""]
        for p in out[key]["pairs"]:
            state = " (WITHHELD)" if p["withheld"] else ""
            L += [f"### {p['name']}{state}", "",
                  "Words counted per Guard script: " + "; ".join(
                      f"{g}: " + ", ".join(f"{w} × {n}" for w, n in ws.items()) for g, ws in p["words_by_guard"].items()),
                  "", "Paired readout (games of 1,000 per cell, summed): hold → reach / reach → hold / other outcome "
                      "change / same outcome, end step changed:", "",
                  "| Guard script | hold → reach | reach → hold | other | end step only |", "|---|---|---|---|---|"]
            for g, c in p["paired_by_guard"].items():
                L.append(f"| {g} | {c['hold_to_reach']} | {c['reach_to_hold']} | {c['other_outcome']} | "
                         f"{c['same_outcome_end_step_changed']} |")
            t = p["paired_total"]
            L += [f"| **all** | **{t['hold_to_reach']}** | **{t['reach_to_hold']}** | **{t['other_outcome']}** | "
                  f"**{t['same_outcome_end_step_changed']}** |", "",
                  f"| Guard | Strike | {p['on']} | {p['off']} | Word | h→r | r→h | filter active at tag (on / off) | "
                  "pushed (on / off) | filter rate (on / off) | breach (on / off) | closest 3-D m (on / off) |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|"]
            for c in p["cells"]:
                on, off = c["on_cols"], c["off_cols"]
                word = c["word"] if not p["withheld"] else "(withheld)"
                L.append(f"| {c['guard']} | {c['strike']} | {_pct(c['on'])} | {_pct(c['off'])} | {word} | "
                         f"{c['paired']['hold_to_reach']} | {c['paired']['reach_to_hold']} | "
                         + " | ".join(f"{_num(on[k])} / {_num(off[k])}" for k in FILTER_COLS) + " |")
            L.append("")
        if key == "reading3":
            L += [f"{FILTER_BEFORE_TAG}. The filter columns are the driver's: filter active on the tag's own tick (an "
                  "upper bound), pushed together on that tick, the share of live drone-steps the filter corrected (every "
                  "pair), the share of games with a breach of the 1.10 m keep-out among live drones, and the closest "
                  "3-D approach among live drones (it cannot see a landing drone).", ""]
    return "\n".join(L) + "\n"


def _jsonable(v):
    if isinstance(v, tuple):
        return list(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    raise TypeError(type(v).__name__)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-dir", type=Path, required=True)
    args = ap.parse_args(argv)
    out = read_run(args.run_dir)
    (args.run_dir / "l25_readings.json").write_text(json.dumps(out, indent=1, default=_jsonable) + "\n")
    (args.run_dir / "l25_readings.md").write_text(render(out))
    print(f"P-b: {out['plumbing']['P-b']['words']}; P-c: {out['plumbing']['P-c']['words']}; "
          f"written {args.run_dir / 'l25_readings.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
