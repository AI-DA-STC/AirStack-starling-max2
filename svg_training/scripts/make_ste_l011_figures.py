#!/usr/bin/env python
"""Figures of the L0.11 Screening sweep, drawn from the run's own results.json (STANDARDS section 7 rule 2: the numbers
plotted are the numbers in the table).

    make_ste_l011_figures.py --run-dir runs/<date>_ste_l011_screen [--out <folder>] [--allow-failed-controls]

Writes into <run>/figures/ (or --out):
- ``base_heatmap.png``: hold rate of the base case, scripted Guard (rows) x scripted Strike (columns);
- ``factors.png``: one panel per factor (team size, tag radius, guard survives a tag, zone radius, arena): the best
  scripted Guard's worst-case hold H and the best scripted Strike's worst-case reach R (the shortlist rule's numbers) at
  each level, the base case included;
- ``heatmaps_<factor>.png``: the hold-rate heatmap of every level of one factor, side by side.

Refuses (exit 2) while a control in results.json is not PASS: no result is read before the controls hold (gate file
[controls]); --allow-failed-controls draws anyway, with a red banner (debugging only). Exit 0 when written."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

GUARD_COLOUR = "#0072B2"           # Okabe-Ito blue: the Guard team (as viz/replay.py)
STRIKE_COLOUR = "#E69F00"          # Okabe-Ito orange: the Strike team
INK, MUTED = "#1a1a1a", "#666666"
SEQUENTIAL = "Blues"               # one hue, light to dark: hold rate 0 to 1
DPI = 120


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def matrix(rows: list[dict], guards: list[str], strikes: list[str]):
    import numpy as np
    m = np.full((len(guards), len(strikes)), np.nan)
    for r in rows:
        if r["hold_rate"] is not None and r["guard"] in guards and r["strike"] in strikes:
            m[guards.index(r["guard"]), strikes.index(r["strike"])] = r["hold_rate"]
    return m


def heatmap(ax, rows, guards, strikes, z_up, title, show_y=True):
    import numpy as np
    m = matrix(rows, guards, strikes)
    ax.imshow(np.ma.masked_invalid(m), cmap=SEQUENTIAL, vmin=0.0, vmax=1.0, aspect="auto")
    for i in range(len(guards)):
        for j in range(len(strikes)):
            v = m[i, j]
            text = "not\nplayed" if np.isnan(v) else f"{v:.2f}"
            ax.text(j, i, text, ha="center", va="center", fontsize=7,
                    color="white" if not np.isnan(v) and v > 0.6 else INK)
    ax.set_xticks(range(len(strikes)))
    ax.set_xticklabels([s.replace("strike_", "") + (" *" if s in z_up else "") for s in strikes], rotation=40,
                       ha="right", fontsize=7, color=INK)
    ax.set_yticks(range(len(guards)))
    ax.set_yticklabels([g.replace("guard_", "") for g in guards] if show_y else [], fontsize=7, color=INK)
    ax.set_title(title, fontsize=9, color=INK)
    ax.set_xlabel("Strike script", fontsize=8, color=MUTED)
    if show_y:
        ax.set_ylabel("Guard script", fontsize=8, color=MUTED)
    for side in ax.spines.values():
        side.set_visible(False)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--allow-failed-controls", action="store_true")
    a = ap.parse_args(argv)
    result = json.loads((a.run_dir / "results.json").read_text())
    if not result["controls_all_pass"] and not a.allow_failed_controls:
        bad = {k: v["status"] for k, v in result["controls"].items() if v["status"] != "PASS"}
        print(f"refused: controls not all PASS {bad}: no result is read before they hold", file=sys.stderr)
        return 2
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = a.out or a.run_dir / "figures"
    out.mkdir(parents=True, exist_ok=True)
    meta = result["meta"]
    groups = {g["name"]: g for g in result["groups"]}
    every_strike, every_guard = [], []
    for g in result["groups"]:
        for r in g["rows"]:
            every_guard += [r["guard"]] if r["guard"] not in every_guard else []
            every_strike += [r["strike"]] if r["strike"] not in every_strike else []
    z_label = meta["z_up_label"]
    z_up = set(meta["z_up_info"])
    guards = [x for x in every_guard]
    strikes = [x for x in every_strike if x != "zero"]
    banner = "" if result["controls_all_pass"] else "CONTROLS NOT ALL PASS: NOT FOR READING. "
    foot = (f"{banner}Training simulator, tier 1, safety filter on; {meta['games_per_cell']} games per cell; "
            f"* = {z_label}.")
    written = []

    # base case
    base = groups.get("base")
    if base and base["rows"]:
        fig, ax = plt.subplots(figsize=(7.0, 4.2), dpi=DPI)
        heatmap(ax, base["rows"], guards, strikes, z_up, "Hold rate, base case: 3v3, tag 1.6 m, zone 1.6 m, survive 0, 6.5 m")
        fig.text(0.01, 0.01, foot, fontsize=7, color="red" if banner else MUTED)
        fig.tight_layout(rect=(0, 0.04, 1, 1))
        written.append(out / "base_heatmap.png")
        fig.savefig(written[-1])
        plt.close(fig)

    # factors: H and R per level, and the heatmaps per level
    sl = {v["variant"]: v for v in result["shortlist"]["variants"] + result["shortlist"]["report_only"]}
    factors: dict[str, list[dict]] = {}
    for g in result["groups"]:
        if g["role"] == "sweep" and g["factor"] != "base case" and not g["cut"] and g["rows"]:
            factors.setdefault(g["factor"], []).append(g)
    if factors and base:
        fig, axes = plt.subplots(1, len(factors), figsize=(3.0 * len(factors), 3.2), dpi=DPI, sharey=True, squeeze=False)
        for ax, (factor, levels) in zip(axes[0], factors.items()):
            names = ["base"] + [g["name"] for g in levels]
            labels = ["base"] + [g["level"].split(" (")[0].split(";")[0].split(" with")[0] for g in levels]
            xs = list(range(len(names)))
            for key, colour, label in (("H", GUARD_COLOUR, "H: best Guard's worst hold"),
                                       ("R", STRIKE_COLOUR, "R: best Strike's worst reach")):
                ys = [sl.get(n, {}).get(key) for n in names]
                ys = [float("nan") if y is None else y for y in ys]
                ax.plot(xs, ys, color=colour, linewidth=2, marker="o", markersize=8, label=label)
            ax.set_xticks(xs)
            ax.set_xticklabels(labels, fontsize=7, rotation=30, ha="right", color=INK)
            ax.set_ylim(0, 1)
            ax.set_title(factor, fontsize=9, color=INK)
            ax.grid(axis="y", color="#e0e0e0", linewidth=0.8)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
        axes[0][0].set_ylabel(f"rate ({meta['games_per_cell']:,} games per cell)", fontsize=8, color=INK)
        axes[0][0].legend(fontsize=7, frameon=False, loc="upper left")
        fig.text(0.01, 0.01, foot, fontsize=7, color="red" if banner else MUTED)
        fig.tight_layout(rect=(0, 0.05, 1, 1))
        written.append(out / "factors.png")
        fig.savefig(written[-1])
        plt.close(fig)
        for factor, levels in factors.items():
            panels = [base] + levels
            fig, axes = plt.subplots(1, len(panels), figsize=(3.4 * len(panels), 3.6), dpi=DPI, squeeze=False)
            for k, (ax, g) in enumerate(zip(axes[0], panels)):
                title = "base" if g is base else g["level"]
                heatmap(ax, g["rows"], guards, strikes, z_up, title if len(title) < 40 else title[:37] + "...",
                        show_y=k == 0)
            fig.suptitle(f"Hold rate per level: {factor}", fontsize=10, color=INK)
            fig.text(0.01, 0.01, foot, fontsize=7, color="red" if banner else MUTED)
            fig.tight_layout(rect=(0, 0.05, 1, 0.95))
            written.append(out / f"heatmaps_{slug(factor)}.png")
            fig.savefig(written[-1])
            plt.close(fig)
    for path in written:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
