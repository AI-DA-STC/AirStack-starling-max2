#!/usr/bin/env python3
"""Figures for records/2026-11-15_s1_filter_parity_record.md (run T2), from the run's own data.

Usage: python scripts/make_s1_filter_figures.py [--prefix docs/figures/s1_t2]
Writes <prefix>_dv_hist.png and <prefix>_sweeps.png.

Run T2 saved no per-scene output, so this script RECOMPUTES it with the run's own code and settings
(scripts/filter_parity.py: seed 20261115, 2,000 scenes, 1,000 sweeps, float32, CPU, 8 threads; nothing
tuned), then checks all four recomputed gate numbers against the record's gate table and stops if they differ.
The sweeps figure recomputes the development-seed table (seed 1) of the Task 7 implementer's report, a local
working note that git ignores; the T2 record's Figures section and docs/S1_RESULTS.md Figure 2 give its result.
Palette and style() are copied from scripts/make_s0_figures.py.
"""
import argparse
import importlib.util
import re
import sys
from pathlib import Path

import matplotlib
import numpy as np
import torch

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "records/2026-11-15_s1_filter_parity_record.md"
RUN_SEED, RUN_SCENES, RUN_ITERATIONS = 20261115, 2000, 1000
DEV_SEED, DEV_SWEEPS = 1, [60, 100, 200, 300, 500, 1000, 1500, 2000]
DV_LIMIT, AGREE_LIMIT = 0.02, 0.99
DV_FLOOR = 1e-7  # differences below this (float32 rounding) are drawn in the first bin

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"


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


def load_parity():
    spec = importlib.util.spec_from_file_location("filter_parity", ROOT / "scripts/filter_parity.py")
    fp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fp)
    return fp


def record_gates():
    """Measured gate values from the record's gate table."""
    found = dict(re.findall(r"^\| `(\w+)` \| ([^|]+) \|", RECORD.read_text(), flags=re.M))
    return {k: float(v) for k, v in found.items()}


def recompute_run(fp):
    scenes = fp.make_scenes(RUN_SCENES, RUN_SEED)
    ref = fp.run_original(scenes)
    port = fp.run_port(scenes, RUN_ITERATIONS, torch.float32)
    ev = fp.evaluate(scenes, ref, port)
    rec = record_gates()
    for gate in ("max_abs_dv_mps", "constraint_residual_max", "emergency_agreement_min"):
        if f"{ev[gate]:.6g}" != f"{rec[gate]:.6g}":
            sys.exit(f"recomputed {gate} {ev[gate]:.6g} differs from the record's {rec[gate]:.6g}: not drawing")
    cross = fp.cross_team_check(scenes, port, RUN_ITERATIONS, torch.float32)["cross_team_corrections"]
    if cross != rec["cross_team_corrections"]:
        sys.exit(f"recomputed cross_team_corrections {cross} differs from the record's: not drawing")
    return scenes, ref, port, ev


def dv_histogram(ref, port, ev, out):
    s_idx = ev["subset"]
    dv = np.maximum(ev["dv"][s_idx], DV_FLOOR)
    seq = ref["sweeps"][s_idx] > 200  # the original needed its sequential (Gauss-Seidel) phase
    bins = np.logspace(np.log10(DV_FLOOR), np.log10(5.0), 50)
    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=150)
    ax.hist([dv[~seq], dv[seq]], bins=bins, stacked=True, color=[SERIES[0], SERIES[1]],
            label=[f"solved in CMU's parallel phase ({int((~seq).sum())} scenes)",
                   f"needed CMU's sequential phase ({int(seq.sum())} scenes)"])
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.axvline(DV_LIMIT, color=INK, linestyle="--", linewidth=1.2)
    top_of = ax.get_xaxis_transform()  # x in data, y in axes fraction
    ax.text(DV_LIMIT * 0.92, 0.60, f"limit {DV_LIMIT} m/s", transform=top_of, ha="right", fontsize=9, color=INK)
    disagree = sorted((k for k in ev["emergency_disagree"] if k in set(s_idx.tolist())), key=lambda k: ev["dv"][k])
    if disagree:
        ax.plot([ev["dv"][k] for k in disagree], [1.6] * len(disagree), "v", color=INK, markersize=6)
        ax.text(0.03, 0.42, "\u25bc " + ", ".join(f"scene {k} ({ev['dv'][k]:.2f} m/s)" for k in disagree)
                + ":\nCMU converged, the port used the push-apart", transform=top_of, ha="left", va="center",
                fontsize=8, color=INK)
    style(ax, "Run T2: largest velocity difference per scene, port against CMU's filter",
          f"max |Δv| in the scene, m/s (log scale; below {DV_FLOOR:g} drawn at {DV_FLOOR:g})",
          "scenes (log scale)")
    ax.legend(frameon=False, fontsize=9, loc="upper left", bbox_to_anchor=(0.30, 0.98), labelcolor=INK)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def sweeps_figure(fp, out):
    scenes = fp.make_scenes(RUN_SCENES, DEV_SEED)
    ref = fp.run_original(scenes)
    rows = []
    for k in DEV_SWEEPS:
        ev = fp.evaluate(scenes, ref, fp.run_port(scenes, k, torch.float32))
        rows.append((k, ev["max_abs_dv_mps"], ev["emergency_agreement_min"]))
        print(f"dev seed {DEV_SEED}, {k} sweeps: max dv {ev['max_abs_dv_mps']:.4g}, agreement "
              f"{ev['emergency_agreement_min']:.4f}")
    ks, dvs, agr = (np.array(c) for c in zip(*rows))
    fig, (top, bot) = plt.subplots(2, 1, figsize=(9, 7.4), dpi=150, sharex=True)
    top.plot(ks, dvs, color=SERIES[0], linewidth=2, marker="o", markersize=6)
    top.axhline(DV_LIMIT, color=INK, linestyle="--", linewidth=1.2)
    top.annotate(f"limit {DV_LIMIT} m/s", (ks[0], DV_LIMIT), xytext=(0, 4), textcoords="offset points",
                 fontsize=9, color=INK)
    top.set_yscale("log")
    top.set_ylim(0.01, 10)
    style(top, f"Development seed {DEV_SEED} (2,000 scenes): what more sweeps buy", "",
          "max |Δv| on scenes CMU solved, m/s (log)")
    bot.plot(ks, agr, color=SERIES[2], linewidth=2, marker="o", markersize=6)
    bot.axhline(AGREE_LIMIT, color=INK, linestyle="--", linewidth=1.2)
    bot.annotate(f"limit {AGREE_LIMIT}", (ks[-1], AGREE_LIMIT), xytext=(0, -14), textcoords="offset points",
                 ha="right", fontsize=9, color=INK)
    style(bot, "", "sweeps per call (log scale)", "emergency agreement")
    for ax in (top, bot):
        ax.axvline(RUN_ITERATIONS, color=INK2, linewidth=1, linestyle=":")
    bot.annotate(f"chosen: {RUN_ITERATIONS}", (RUN_ITERATIONS, bot.get_ylim()[0]), xytext=(4, 6),
                 textcoords="offset points", fontsize=9, color=INK2)
    bot.set_xscale("log")
    bot.set_xticks(ks, [str(k) for k in ks])
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--prefix", default=str(ROOT / "docs/figures/s1_t2"))
    a = p.parse_args(argv)
    fp = load_parity()
    torch.set_num_threads(min(8, torch.get_num_threads()))  # as the run
    print(f"run T2 saved no per-scene output: recomputing seed {RUN_SEED}, {RUN_ITERATIONS} sweeps, no tuning")
    _scenes, ref, port, ev = recompute_run(fp)
    print("recomputed gate numbers equal the record's")
    dv_histogram(ref, port, ev, f"{a.prefix}_dv_hist.png")
    sweeps_figure(fp, f"{a.prefix}_sweeps.png")
    print(f"wrote {a.prefix}_dv_hist.png and {a.prefix}_sweeps.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
