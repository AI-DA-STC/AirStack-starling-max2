#!/usr/bin/env python3
"""Figure of one plots.json plot, drawn from a test's metrics.csv (record Figure 1).

    plot_metrics.py <metrics.csv> --plots plots.json [--plot <id>] -o fig-1.png

The plot's series against t_s, its reference lines (dashed, at the values in the CSV header), shaded spans for phase 1
(takeoff) and phase 3 (land). House style of tools/hover_step_plot.py: white background, colour-blind-safe hues in a
fixed order, legend plus direct labels, a "Sim only" footer. Host-only: numpy + matplotlib (Agg)."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import metrics_core as M  # noqa: E402

INK, MUTED, GRID, SPINE = "#404040", "#5F6368", "#E6E8EA", "#D0D3D6"
COLOURS = ["#0072B2", "#E69F00", "#009E73"]          # Okabe-Ito blue / orange / bluish green, fixed series order
STYLES = ["-", "--", ":"]                            # a 4th+ series repeats the hues with another dash
MIN_COLOUR = "#CC79A7"                               # Okabe-Ito reddish purple: the running minimum is not d_12
PHASE_SPAN = {1: "#8A8F94", 3: "#C9A66B"}
PHASE_NAME = {1: "takeoff", 3: "land"}
LABEL_GAP_FRAC = 0.045
FOOTER = "Sim only (iron rule 9): not a drone result."


def _ref_value(meta, name):
    refs = meta.get("refs")
    if isinstance(refs, dict) and name in refs:
        return float(refs[name])
    if name in M.meta_refs(meta):                    # the CSV header's string form, parsed by metrics_core
        return M.meta_refs(meta)[name]
    try:
        return float(meta.get(name))
    except (TypeError, ValueError):
        return None


def _spans(t, phase, want):
    out, start = [], None
    for i, p in enumerate(phase):
        if p == want and start is None:
            start = t[i]
        if p != want and start is not None:
            out.append((start, t[i])); start = None
    if start is not None:
        out.append((start, t[-1]))
    return out


def plot(columns, rows, meta, plot_spec, out_png=None, title=None):
    """Draw and (when out_png is given) save; returns (fig, ax) so tests can inspect it. The caller closes the figure."""
    idx = {c: i for i, c in enumerate(columns)}
    series = list(plot_spec.get("series", []))
    missing = [s for s in series if s not in idx]
    if "t_s" not in idx or missing:
        raise ValueError("metrics.csv lacks column(s): %s" % ", ".join(missing or ["t_s"]))
    rows = np.asarray(rows, dtype=float)
    t = rows[:, idx["t_s"]]
    title = title or plot_spec.get("title") or plot_spec.get("id", "")
    fig, ax = plt.subplots(figsize=(8.0, 4.8), dpi=130, facecolor="white")
    ax.set_facecolor("white"); ax.grid(True, color=GRID, linewidth=0.8); ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(SPINE)
    ax.tick_params(colors=MUTED, labelsize=8)
    if "phase" in idx and len(t):
        phase = rows[:, idx["phase"]]
        for ph, colour in PHASE_SPAN.items():
            for k, (a, b) in enumerate(_spans(t, phase, ph)):
                ax.axvspan(a, b, color=colour, alpha=0.12, lw=0, label="phase %d (%s)" % (ph, PHASE_NAME[ph]) if k == 0 else None)
    ends = []
    for i, name in enumerate(series):
        y = rows[:, idx[name]]
        col = MIN_COLOUR if name.endswith("_running") else COLOURS[i % 3]
        ln, = ax.plot(t, y, color=col, ls=STYLES[(i // 3) % 3], lw=1.6, label=name)
        ok = np.where(~np.isnan(y))[0]
        if len(ok):
            ends.append((y[ok[-1]], t[ok[-1]], name, col))
    if "min_pair_distance" in idx and "phase" in idx:       # mark the closest approach of phase 2 (what the gate reads)
        d, ph = rows[:, idx["min_pair_distance"]], rows[:, idx["phase"]]
        ok2 = np.where((ph == 2) & ~np.isnan(d))[0]
        if len(ok2):
            k = ok2[int(np.argmin(d[ok2]))]
            ax.plot([t[k]], [d[k]], "o", color=INK, ms=5, zorder=5)
            ax.annotate("%.2f m @ %.1f s" % (d[k], t[k]), (t[k], d[k]), xytext=(8, -16), textcoords="offset points",
                        fontsize=8, color=INK, arrowprops=dict(arrowstyle="-", color=INK, lw=0.8))
    for name in plot_spec.get("refs", []):
        v = _ref_value(meta, name)
        if v is None:
            continue
        ax.axhline(v, color=INK, ls="--", lw=1.0, alpha=0.8, label="%s = %g" % (name, v))
        ax.annotate("%s %g" % (name, v), (0.0, v), xycoords=("axes fraction", "data"), xytext=(4, 3),
                    textcoords="offset points", ha="left", va="bottom", fontsize=7, color=INK)
    yr = plot_spec.get("y_range")
    if yr:
        ax.set_ylim(yr[0], yr[1])
    lo, hi = ax.get_ylim()
    gap = (hi - lo) * LABEL_GAP_FRAC
    last = None
    for y, x, name, colour in sorted(ends):                 # direct labels, nudged apart (data units)
        yy = y if last is None or y - last >= gap else last + gap
        ax.annotate(name, (x, yy), xytext=(4, 0), textcoords="offset points", fontsize=7, color=colour, va="center")
        last = yy
    ax.label_gap = gap
    ax.set_xlabel("t [s, wall]", color=INK, fontsize=9)
    ax.set_ylabel(title, color=INK, fontsize=9)
    ax.set_title("%s against time" % title, color=INK, fontsize=10, loc="left")
    ax.legend(fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=3)
    fig.text(0.01, 0.01, FOOTER, fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    if out_png:
        fig.savefig(out_png, facecolor="white")
    return fig, ax


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv")
    ap.add_argument("--plots", required=True)
    ap.add_argument("--plot", default=None, help="plot id (default: the first)")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args(argv)
    meta, columns, rows = M.read_metrics_csv(a.csv)
    spec_all = json.loads(pathlib.Path(a.plots).read_text())["plots"]
    spec = next((p for p in spec_all if p["id"] == a.plot), None) if a.plot else (spec_all[0] if spec_all else None)
    if spec is None:
        print("no such plot: %s" % (a.plot or "(plots.json is empty)"), file=sys.stderr)
        return 2
    fig, _ = plot(columns, rows, meta, spec, a.out, spec.get("title"))
    plt.close(fig)
    print("wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
