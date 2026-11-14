#!/usr/bin/env python3
"""Figures for docs/S0_RESULTS.md, generated from a run of record's results.jsonl.

Usage: python scripts/make_s0_figures.py runs/<run>/results.jsonl docs/figures/<prefix>
Writes <prefix>_tier1.png, <prefix>_tier2.png and <prefix>_sensing.png. Every value plotted is the mean of the
"ok" repeats of a point, exactly as records/<run>_record.md tabulates it; nothing is smoothed or fitted.
Palette: the dataviz skill's reference categorical slots 1-6 in fixed order (validated: light mode, adjacent
pairs; three slots sit below 3:1 contrast, so the record and docs/S0_RESULTS.md carry the same numbers as tables).
"""
import collections
import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"


def load(path):
    pts = collections.defaultdict(list)
    for line in open(path):
        r = json.loads(line)
        if r["status"] == "ok":
            pts[(r["case"], r["num_games"])].append(r)
    mean = {}
    for k, rs in pts.items():
        mean[k] = {f: sum(r[f] for r in rs) / len(rs) for f in ("env_steps_per_s", "drone_steps_per_s")}
    return mean


def human(v, _pos=None):
    for div, suf in ((1e6, " M"), (1e3, " k")):
        if v >= div:
            return f"{v / div:.3g}{suf}"
    return f"{v:g}"


def style(ax, title, xlabel, ylabel):
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=10)
    ax.set_xlabel(xlabel, color=INK2)
    ax.set_ylabel(ylabel, color=INK2)
    ax.grid(True, which="major", color=GRID, linewidth=0.8)
    ax.tick_params(colors=INK2)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)


def lines(mean, cases, field, title, ylabel, out):
    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=150)
    for i, (case, label) in enumerate(cases):
        xs = sorted(n for (c, n) in mean if c == case)
        ys = [mean[(case, n)][field] for n in xs]
        ax.plot(xs, ys, color=SERIES[i], linewidth=2, marker="o", markersize=6, label=label)
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{int(v):,}"))
    ax.yaxis.set_major_formatter(FuncFormatter(human))
    style(ax, title, "games at once (log scale)", ylabel)
    ax.legend(frameon=False, fontsize=9, loc="upper left", labelcolor=INK)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def sensing(mean, out, games=4096):
    rows = [("t1_5v3_open", "open arena"), ("t1_5v3_field", "construction-site-size distance field"),
            ("t1_5v3_prim10", "10 obstacles"), ("t1_5v3_prim50", "50 obstacles"),
            ("t1_5v3_prim10_los", "10 obstacles + line of sight"),
            ("t1_5v3_field_rays32", "distance field + 32 range rays"),
            ("t1_5v3_prim10_rays32", "10 obstacles + 32 range rays"),
            ("t1_5v3_prim10_rays64", "10 obstacles + 64 range rays"),
            ("t1_5v3_full", "full sensing (field + 10 obstacles + 32 rays + line of sight)")]
    rows = [(c, lab, mean[(c, games)]["env_steps_per_s"]) for c, lab in rows if (c, games) in mean]
    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=150)
    ys = list(range(len(rows)))[::-1]
    for y, (_c, lab, v) in zip(ys, rows):
        ax.plot([v], [y], marker="o", markersize=9, color=SERIES[0])
        ax.annotate(human(v), (v, y), xytext=(9, 0), textcoords="offset points", va="center", fontsize=9, color=INK)
    ax.set_yticks(ys, [lab for _c, lab, _v in rows], fontsize=9, color=INK)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(human))
    style(ax, f"Tier 1, 5 v 3, {games:,} games: the cost of each kind of sensing",
          "game-steps per second (log scale)", "")
    ax.set_xlim(left=min(v for *_x, v in rows) / 2, right=max(v for *_x, v in rows) * 4)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def main(results, prefix):
    mean = load(results)
    lines(mean, [("t1_1v1_open", "1 v 1, open"), ("t1_5v3_open", "5 v 3, open"),
                 ("t1_5v3_field", "5 v 3, distance field"), ("t1_5v3_prim10", "5 v 3, 10 obstacles"),
                 ("t1_5v3_prim10_rays32", "5 v 3, 10 obstacles + 32 rays"), ("t1_5v3_full", "5 v 3, full sensing")],
          "env_steps_per_s", "Tier 1 (PyTorch): speed against the number of games", "game-steps per second (log scale)",
          f"{prefix}_tier1.png")
    lines(mean, [("t2_k1", "1 drone per game"), ("t2_k2", "2 drones per game"), ("t2_k3", "3 drones per game"),
                 ("t2_k8", "8 drones per game")],
          "drone_steps_per_s", "Tier 2 (Isaac Lab, 200 Hz physics): speed against the number of games",
          "drone-steps per second (log scale)", f"{prefix}_tier2.png")
    sensing(mean, f"{prefix}_sensing.png")


if __name__ == "__main__":
    main(*sys.argv[1:3])
