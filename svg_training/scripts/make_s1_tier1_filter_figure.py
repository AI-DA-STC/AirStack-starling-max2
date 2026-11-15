#!/usr/bin/env python3
"""Figure for records/2026-11-15_s1_tier1_fitted_filter_record.md (Task 8b): tier 1 game-steps per second against
games at once, one line per setting, one panel per case.

Usage: python scripts/make_s1_tier1_filter_figure.py runs/2026-11-15_s1_tier1_fitted_filter docs/figures/s1_t4_tier1_filter.png
Reads placeholder.jsonl, fitted_off.jsonl, fitted_f200.jsonl and fitted_f1000.jsonl from the run folder. Every value
is the mean of the "ok" repeats of a point, as make_s0_figures.load computes it and the record tabulates it.
Style and palette: scripts/make_s0_figures.py (same constants and helpers, imported). Prints the table it plotted.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from make_s0_figures import INK, SERIES, human, load, style  # noqa: E402

SETTINGS = [("placeholder.jsonl", "S0 placeholder model, no filter (reference)"),
            ("fitted_off.jsonl", "real-drone model, filter off"),
            ("fitted_f200.jsonl", "real-drone model, filter on, 200 sweeps (information only)"),
            ("fitted_f1000.jsonl", "real-drone model, filter on, 1,000 sweeps")]  # legend order = line order
CASES = [("t1_5v3_open", "5 Guard v 3 Strike, open arena"),
         ("t1_5v3_full", "5 v 3, distance field + 10 obstacles + 32 rays + line of sight")]


def main(run_dir, out):
    run = pathlib.Path(run_dir)
    data = {f: load(run / f) for f, _ in SETTINGS if (run / f).exists()}
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), dpi=150, sharey=True)
    for ax, (case, title) in zip(axes, CASES):
        for i, (f, label) in enumerate(SETTINGS):
            if f not in data:
                continue
            xs = sorted(n for (c, n) in data[f] if c == case)
            ys = [data[f][(case, n)]["env_steps_per_s"] for n in xs]
            ax.plot(xs, ys, color=SERIES[i], linewidth=2, marker="o", markersize=6, label=label,
                    linestyle="--" if f == "placeholder.jsonl" else "-")
            for n, y in zip(xs, ys):
                print(f"{case}\t{f}\t{n}\t{y:.0f}")
        ax.set_xscale("log", base=2)
        ax.set_yscale("log")
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{int(v):,}"))
        ax.yaxis.set_major_formatter(FuncFormatter(human))
        style(ax, title, "games at once (log scale)", "game-steps per second (log scale)" if ax is axes[0] else "")
    axes[1].legend(frameon=False, fontsize=8.5, loc="upper right", labelcolor=INK)  # right panel: empty above 100 k
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


if __name__ == "__main__":
    main(*sys.argv[1:3])
