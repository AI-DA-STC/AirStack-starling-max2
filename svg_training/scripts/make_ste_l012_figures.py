#!/usr/bin/env python
"""Figure of the L0.12 Best-response test (T46): for each variant and side, the trained exploiter, the best scripted
player and the untrained exploiter on T44's 1,000 starts, with Wilson 95 % intervals, on one axis (the side's own win
rate: reach the zone for the Strike team, hold for the Guard team). Observed in the training simulator.

    make_ste_l012_figures.py --verdict runs/<...>_verdict/verdict.json --out docs/figures/ste_l012/best_response.png
                             [--aborted <run>,...]

A side whose run is ABORTED (--aborted) shows its best script only, with a note: no trained number is read from it."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

GUARD_COLOUR = "#0072B2"           # Okabe-Ito blue: the Guard team (as viz/replay.py and make_ste_l011_figures.py)
STRIKE_COLOUR = "#E69F00"          # Okabe-Ito orange: the Strike team
INK, MUTED, GRID = "#1a1a1a", "#666666", "#e0e0e0"
TEAM = {"strike": ("Strike team", STRIKE_COLOUR), "guard": ("Guard team", GUARD_COLOUR)}
VARIANT = {"base": "base (tag 1.6 m)", "tag_1p4": "tag 1.4 m", "tag_1p2": "tag 1.2 m", "tag_1p15": "tag 1.15 m (bubble)"}
ORDER = list(VARIANT)                # widest tag first; a variant not listed goes last


def rows(verdict: dict, aborted: list[dict]) -> list[dict]:
    """One row per variant and side, widest tag first, Strike first; ABORTED sides keep their script only. ``verdict``
    may hold the variants of several verdict files (main merges them)."""
    cut = {(r["variant"], r["side"]): r for r in aborted}
    out = []
    names = sorted(verdict["variants"], key=lambda v: ORDER.index(v) if v in ORDER else len(ORDER))
    for v, e in ((v, verdict["variants"][v]) for v in names):
        for s in ("strike", "guard"):
            sr = e["sides"].get(s)
            if sr is not None:
                out.append({"variant": v, "side": s, "trained": sr["gain"]["trained"], "script": sr["gain"]["script"],
                            "untrained": sr["untrained"], "cell": sr["script_cell"], "note": None})
            elif (v, s) in cut:
                r = cut[(v, s)]
                out.append({"variant": v, "side": s, "trained": None, "script": r["script"], "untrained": None,
                            "cell": r["script"]["cell"], "note": f"trained: not read (run ABORTED, {r.get('record', 'T47')})"})
    return out


def draw(rs: list[dict], band: float, out: Path, title: str | None = None) -> None:
    fig, ax = plt.subplots(figsize=(9.0, 0.62 * len(rs) + 1.6), dpi=150)
    ax.axvspan(-0.02, band, color="#f0f0f0", zorder=0)
    ax.text(band / 2, -0.75, f"band: a side whose better rate\nstays below {band:g} (upper bound)\nmakes the game trivial\n"
            "for the other team", ha="center", va="center", fontsize=6.5, color=MUTED)
    for i, r in enumerate(rs):
        y = i
        name, colour = TEAM[r["side"]]
        for key, marker, face, size in (("untrained", "x", MUTED, 40), ("script", "D", "white", 46),
                                         ("trained", "o", colour, 64)):
            d = r[key]
            if d is None:
                continue
            k, n, (lo, hi) = d["k"], d["n"], d["ci"]
            dy = {"untrained": 0.0, "script": -0.16, "trained": 0.16}[key]
            ax.plot([lo, hi], [y + dy, y + dy], color=colour if key != "untrained" else MUTED, linewidth=2,
                    solid_capstyle="round", zorder=2)
            if key == "untrained":
                ax.scatter([k / n], [y + dy], marker=marker, s=size, color=MUTED, linewidth=1.4, zorder=3)
            else:
                ax.scatter([k / n], [y + dy], marker=marker, s=size, facecolor=face, edgecolor=colour,
                           linewidth=1.6 if key == "script" else 1.2, zorder=3)
            ax.text(hi + 0.012, y + dy, f"{k}", va="center", fontsize=7, color=MUTED if key == "untrained" else INK)
        if r["note"]:
            ax.text(0.5, y + 0.16, r["note"], va="center", fontsize=7.5, color=INK, style="italic")
    ax.set_yticks(range(len(rs)))
    ax.set_yticklabels([f"{VARIANT.get(r['variant'], r['variant'])}, {TEAM[r['side']][0]}" for r in rs], fontsize=8,
                       color=INK)
    ax.set_ylim(len(rs) - 0.4, -1.2)
    ax.set_xlim(-0.02, 1.0)
    ax.set_xlabel("win rate of that side on T44's 1,000 starts (Strike team: reach the zone; Guard team: hold),"
                  " Wilson 95 %", fontsize=8, color=INK)
    ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=1)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", labelsize=8, colors=INK)
    handles = [plt.Line2D([], [], marker="o", linestyle="", markerfacecolor=MUTED, markeredgecolor=MUTED,
                          label="trained exploiter (filled)"),
               plt.Line2D([], [], marker="D", linestyle="", markerfacecolor="white", markeredgecolor=MUTED,
                          markeredgewidth=1.6, label="best scripted player (hollow)"),
               plt.Line2D([], [], marker="x", linestyle="", color=MUTED, label="untrained exploiter"),
               plt.Line2D([], [], color=STRIKE_COLOUR, linewidth=3, label="Strike team"),
               plt.Line2D([], [], color=GUARD_COLOUR, linewidth=3, label="Guard team")]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=5, fontsize=7, frameon=False)
    ax.set_title((title or "L0.12 Best-response test") + ": trained exploiter v best script v untrained, per rule variant and side\n"
                 "training simulator, tier 1, 3v3; observed in the training simulator, not a flight", fontsize=9,
                 color=INK)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--verdict", type=Path, required=True, action="append", help="a verdict.json; repeat to compare")
    ap.add_argument("--aborted", default="", help="comma list of ABORTED run folders, each as <folder>[=<T number>]: "
                    "their best script only")
    ap.add_argument("--title", default=None)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    verdicts = [json.loads(v.read_text()) for v in a.verdict]
    if len({v["band"] for v in verdicts}) != 1:
        raise SystemExit("refused: the verdicts have different bands")
    verdict = {"band": verdicts[0]["band"], "variants": {k: e for v in verdicts for k, e in v["variants"].items()}}
    aborted = []
    for item in (x.strip() for x in a.aborted.split(",") if x.strip()):
        folder, _, number = item.partition("=")
        aborted.append({**json.loads((Path(folder) / "results.json").read_text()), "record": number or "T47"})
    rs = rows(verdict, aborted)
    draw(rs, verdict["band"], a.out, a.title)
    print(f"wrote {a.out} ({len(rs)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
