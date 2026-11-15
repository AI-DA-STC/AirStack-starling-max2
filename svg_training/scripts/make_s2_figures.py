#!/usr/bin/env python3
"""Figures for the S2 records: one function per figure (Task 6 now; Tasks 7, 8 and 10 add theirs).

  make_s2_figures.py scripted_reference runs/<run> docs/figures/s2_scripted_reference.png
  make_s2_figures.py closest_cross runs/<run> docs/figures/s2_scripted_reference_closest.png
  make_s2_figures.py filter_speed runs/<run> docs/figures/s2_filter_speed.png

Every value plotted is read from the run's own files as the run's script wrote them (``scores.json`` /
``per_game.npz`` from ``scripts/score.py``; ``speed.json`` / ``selection.json`` from ``scripts/filter_speed.py``); nothing is smoothed or fitted. Style and palette: ``scripts/make_s0_figures.py`` (imported). Each function
prints the table it plotted.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tomllib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from make_s0_figures import INK, INK2, SERIES, style  # noqa: E402

BANDS = ("lab", "middle", "large")
BAND_LABEL = {"lab": "lab\n4–6 m", "middle": "middle\n6–10 m", "large": "large\n10–16 m"}
PRESET_TITLE = {"pure": "pure partner rules", "starling": "with Starling layer"}
STRIKE_MARK = {"strike_straight": ("o", "straight"), "strike_flank": ("s", "flank")}


def _panels(rows: list[dict]) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    for r in rows:
        if (r["preset"], r["size"]) not in keys:
            keys.append((r["preset"], r["size"]))
    return keys


def scripted_reference(run_dir: str, out: str) -> None:
    """Hold rate with its Wilson 95 % interval per band; one panel per preset x size; colour = Guard strategy,
    marker = Strike strategy."""
    rows = json.loads((pathlib.Path(run_dir) / "scores.json").read_text())["rows"]
    panels = _panels(rows)
    guards = list(dict.fromkeys(r["guard"] for r in rows))
    strikes = list(dict.fromkeys(r["strike"] for r in rows))
    pairs = [(g, s) for g in guards for s in strikes]
    ncol = 2
    nrow = (len(panels) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(13, 4.6 * nrow), dpi=150, sharey=True, squeeze=False)
    width = 0.8
    for ax, (preset, size) in zip(axes.flat, panels):
        for j, (g, s) in enumerate(pairs):
            xs, ys, lo, hi = [], [], [], []
            for bi, band in enumerate(BANDS):
                r = next((r for r in rows if (r["preset"], r["size"], r["guard"], r["strike"], r["band"])
                          == (preset, size, g, s, band)), None)
                if r is None or r["hold_rate"] is None:
                    continue
                xs.append(bi - width / 2 + width * (j + 0.5) / len(pairs))
                ys.append(100 * r["hold_rate"])
                lo.append(100 * (r["hold_rate"] - r["ci_low"]))
                hi.append(100 * (r["ci_high"] - r["hold_rate"]))
                print(f"{preset}\t{size}\t{g}\t{s}\t{band}\t{r['hold_rate']:.4f}\t{r['ci_low']:.4f}\t"
                      f"{r['ci_high']:.4f}\t{r['games']}")
            colour = SERIES[guards.index(g) % len(SERIES)]
            marker = STRIKE_MARK.get(s, ("^", s))[0]
            ax.errorbar(xs, ys, yerr=[lo, hi], fmt=marker, color=colour, markersize=6, capsize=2, linewidth=1.2,
                        markerfacecolor=colour if strikes.index(s) == 0 else "white")
        ax.set_xticks(range(len(BANDS)), [BAND_LABEL[b] for b in BANDS])
        ax.set_ylim(-3, 103)
        style(ax, f"{PRESET_TITLE.get(preset, preset)}, {size[0]} Guard v {size[-1]} Strike", "arena size band",
              "hold rate, % of games (95 % interval)" if ax in axes[:, 0] else "")
    for ax in list(axes.flat)[len(panels):]:
        ax.set_visible(False)
    handles = [Line2D([], [], color=SERIES[i % len(SERIES)], marker="o", linestyle="", label=f"Guard: {g}")
               for i, g in enumerate(guards)]
    handles += [Line2D([], [], color=INK2, marker=STRIKE_MARK.get(s, ("^", s))[0], linestyle="",
                       markerfacecolor=INK2 if k == 0 else "white", label=f"Strike: {STRIKE_MARK.get(s, (0, s))[1]}")
                for k, s in enumerate(strikes)]
    fig.legend(handles=handles, loc="lower center", ncol=len(handles), frameon=False, fontsize=9, labelcolor=INK)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(out)
    plt.close(fig)


def closest_cross(run_dir: str, out: str, field: str = "closest_cross_m") -> None:
    """How close Guard and Strike drones came: share of games whose closest opposite approach is at or below a
    distance (cumulative), per band, pure partner rules against the Starling layer, all strategy pairs pooled;
    one panel per size. The keep-out (1.10 m, committed neutral value) is marked. field: "closest_cross_m"
    (horizontal) or "closest_cross_3d_m" (3-D; runs scored after 16 November 2026)."""
    run = pathlib.Path(run_dir)
    rows = json.loads((run / "scores.json").read_text())["rows"]
    pg = np.load(run / "per_game.npz")
    sizes = list(dict.fromkeys(r["size"] for r in rows))
    presets = list(dict.fromkeys(r["preset"] for r in rows))
    fig, axes = plt.subplots(1, len(sizes), figsize=(6.5 * len(sizes), 4.6), dpi=150, sharey=True, squeeze=False)
    for ax, size in zip(axes[0], sizes):
        for pi, preset in enumerate(presets):
            for bi, band in enumerate(BANDS):
                vals = []
                for key in pg.files:
                    p, sz, _g, _s, b, f = key.split("|")
                    if (p, sz, b, f) == (preset, size, band, field):
                        oc = pg[key.replace(field, "outcome")]
                        v = pg[key][oc > 0]
                        vals.append(v[np.isfinite(v)])
                if not vals:
                    continue
                v = np.sort(np.concatenate(vals))
                ax.step(v, np.arange(1, v.size + 1) / v.size * 100, where="post", color=SERIES[bi],
                        linestyle="-" if pi == len(presets) - 1 else "--", linewidth=1.6,
                        label=f"{band}, {PRESET_TITLE.get(preset, preset)}")
                print(f"{preset}\t{size}\t{band}\tgames {v.size}\tmin {v[0]:.3f}\tp05 {np.quantile(v, 0.05):.3f}"
                      f"\tp50 {np.quantile(v, 0.5):.3f}\tat or under 1.10 m {np.mean(v <= 1.10):.3f}")
        ax.axvline(1.10, color=INK2, linewidth=1, linestyle=":")
        ax.text(1.12, 3, "keep-out 1.10 m", color=INK2, fontsize=8)
        ax.set_xlim(0, 4)
        what = "3-D" if field == "closest_cross_3d_m" else "horizontal"
        style(ax, f"{size[0]} Guard v {size[-1]} Strike", f"closest Guard–Strike approach in a game, {what} (m)",
              "games at or below, %" if ax is axes[0, 0] else "")
    axes[0, -1].legend(frameon=False, fontsize=8, loc="lower right", labelcolor=INK)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def filter_speed(run_dir: str, out: str) -> None:
    """Game-steps per second against the filter's sweep budget, one line per check_every; filled marker = that
    sweep count passes all five accuracy gates, open marker = it fails; the speed target and the step with the
    filter replaced by a pass-through drawn as horizontal lines."""
    run = pathlib.Path(run_dir)
    speed = json.loads((run / "speed.json").read_text())
    sel = json.loads((run / "selection.json").read_text())
    target = tomllib.loads((run / "gates.toml").read_text())["filter_speed_gates"]["game_steps_per_s_min"]
    accurate = set(sel["accurate_iterations"])
    rows = speed["rows"]
    ks = list(dict.fromkeys(r["check_every"] for r in rows))
    fig, ax = plt.subplots(figsize=(8.5, 5.0), dpi=150)
    for ci, k in enumerate(ks):
        pts = sorted((r["iterations"], r["game_steps_per_s"]) for r in rows
                     if r["check_every"] == k and r["game_steps_per_s"] is not None)
        if not pts:
            continue
        xs, ys = zip(*pts)
        label = "fixed loop (check_every 0)" if k == 0 else f"early stop, check every {k} sweeps"
        ax.plot(xs, ys, color=SERIES[ci], linewidth=1.8, label=label)
        for x, y in pts:
            ax.plot([x], [y], marker="o", markersize=8, color=SERIES[ci],
                    markerfacecolor=SERIES[ci] if x in accurate else "white", markeredgewidth=1.6)
            print(f"check_every {k}\titerations {x}\tgame-steps/s {y:.0f}\taccuracy "
                  f"{'PASS' if x in accurate else 'FAIL'}")
    full_path = run / "fullgame.json"                     # INFO: the same candidates over one whole game
    if full_path.exists():
        full = json.loads(full_path.read_text())["rows"]
        for ci, k in enumerate(ks):
            pts = sorted((r["iterations"], r["game_steps_per_s"]) for r in full if r["check_every"] == k)
            if not pts:
                continue
            xs, ys = zip(*pts)
            ax.plot(xs, ys, color=SERIES[ci], linewidth=1.4, linestyle="--", marker="x", markersize=7,
                    label=f"check every {k} sweeps, whole game from reset (INFO)")
            for x, y in pts:
                print(f"whole game: check_every {k}\titerations {x}\tgame-steps/s {y:.0f}")
    ax.axhline(target, color=INK2, linewidth=1, linestyle=":")
    ax.text(560, target * 0.86, f"target {target:,.0f}", color=INK2, fontsize=8)
    base = speed["baseline"]["game_steps_per_s"]
    if base:
        ax.axhline(base, color=INK2, linewidth=1, linestyle="--")
        ax.text(95, base * 1.08, f"filter skipped (pass-through) {base:,.0f}", color=INK2, fontsize=8)
    ax.set_xscale("log")
    ax.set_yscale("log")
    its = sorted({r["iterations"] for r in rows})
    ax.set_xticks(its)
    ax.set_xticklabels([str(i) for i in its])
    ax.minorticks_off()
    handles, labels = ax.get_legend_handles_labels()
    handles += [Line2D([], [], marker="o", color=INK2, linestyle="", markersize=7),
                Line2D([], [], marker="o", color=INK2, markerfacecolor="white", linestyle="", markersize=7)]
    labels += ["sweep count passes all five accuracy gates", "sweep count fails an accuracy gate"]
    ax.legend(handles, labels, frameon=False, fontsize=8, loc="lower left", labelcolor=INK)
    style(ax, f"Safety filter speed: 5 Guard v 3 Strike, {speed['context']['case']['num_games']:,} games, "
              "Starling layer on", "sweep budget (iterations)", "game-steps per second")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def closest_cross_3d(run_dir: str, out: str) -> None:
    """closest_cross on the 3-D distance."""
    closest_cross(run_dir, out, field="closest_cross_3d_m")


FIGURES = {"scripted_reference": scripted_reference, "closest_cross": closest_cross,
           "closest_cross_3d": closest_cross_3d, "filter_speed": filter_speed}

if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in FIGURES:
        sys.exit(f"usage: make_s2_figures.py {{{','.join(FIGURES)}}} <run dir> <out.png>")
    FIGURES[sys.argv[1]](sys.argv[2], sys.argv[3])
