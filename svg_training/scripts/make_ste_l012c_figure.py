#!/usr/bin/env python
"""Figure of L0.12c (records T54, T55): the learning curves of the tag 1.15 m runs at L0.12b's budget (T51 Guard, T52
Strike, ABORTED) and at the longer budgets (T54 Guard 3x, T55 Strike 5x), one panel per side, with each long run's final
1,000-game result and the best script's on the scoring starts (Wilson 95 %). Observed in the training simulator.

    make_ste_l012c_figure.py --guard-short <run> --guard-long <run> --strike-short <run> --strike-long <run>
                             --guard-verdict <verdict.json> --strike-verdict <verdict.json>
                             --out docs/figures/ste_l012c/longer_runs.png [--csv docs/figures/ste_l012c/curve_reads.csv]

Curve reads are 256 games on the curve starts (seed 120900), a different start set from the 1,000 scoring starts, so the
curve and the final points are not the same measurement; the figure says so."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

GUARD_COLOUR = "#0072B2"           # Okabe-Ito blue: the Guard team (as make_ste_l012_figures.py)
STRIKE_COLOUR = "#E69F00"          # Okabe-Ito orange: the Strike team
INK, MUTED, GRID = "#1a1a1a", "#666666", "#e0e0e0"


def curve(run: Path) -> list[tuple[float, float]]:
    """(game-steps in billions, win share) per curve read of a run folder's curve.json."""
    return [(int(r["game_steps"]) / 1e9, int(r["k"]) / int(r["n"])) for r in json.loads((run / "curve.json").read_text())]


def final_steps(run: Path) -> float:
    """The game-steps (billions) at the end of training, from the run's results.json (where the final evaluation sits)."""
    return int(json.loads((run / "results.json").read_text())["game_steps"]) / 1e9


def side_result(verdict: Path, side: str) -> dict:
    """The trained and script rates with their Wilson intervals, from a verdict.json's tag_1p15 side."""
    g = json.loads(verdict.read_text())["variants"]["tag_1p15"]["sides"][side]["gain"]
    return {k: (g[k]["rate"], g[k]["ci"]) for k in ("trained", "script")}


def draw(panels: dict, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, (side, p) in zip(axes, panels.items()):
        colour = GUARD_COLOUR if side == "guard" else STRIKE_COLOUR
        team = "Guard team (holds)" if side == "guard" else "Strike team (reaches)"
        xs, ys = zip(*p["short"])
        ax.plot(xs, ys, color=colour, lw=2, ls="--", label=f"1x budget ({p['short_label']})")
        xs, ys = zip(*p["long"])
        ax.plot(xs, ys, color=colour, lw=2, label=f"{p['factor']} budget ({p['long_label']})")
        rate, (lo, hi) = p["result"]["trained"]
        ax.errorbar([p["final_x"]], [rate], yerr=[[rate - lo], [hi - rate]], fmt="o", ms=8, color=colour,
                    mec="white", mew=2, capsize=4, label=f"final, 1,000 games: {rate:.3f}")
        rate, (lo, hi) = p["result"]["script"]
        ax.axhspan(lo, hi, color=MUTED, alpha=0.15, lw=0)
        ax.axhline(rate, color=MUTED, lw=1.5, ls=":", label=f"best script, 1,000 games: {rate:.3f}")
        ax.set_title(team, color=INK, fontsize=11, loc="left")
        ax.set_xlabel("game-steps of training (billions)", color=MUTED)
        ax.grid(color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.legend(fontsize=8, frameon=False, loc="lower right" if side == "guard" else "upper left")
    axes[0].set_ylabel("share of games won", color=MUTED)
    axes[0].set_ylim(0, 1)
    fig.suptitle("Tag 1.15 m: longer training, same recipe (training simulator, tier 1; one seed per run)", fontsize=11,
                 color=INK, x=0.01, ha="left")
    fig.text(0.01, 0.005, "Lines: 256 curve games every 10 updates (curve starts). Points and grey band: 1,000 scoring "
             "starts, Wilson 95 %. Different start sets.", fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for name in ("guard-short", "guard-long", "strike-short", "strike-long"):
        ap.add_argument(f"--{name}", type=Path, required=True)
    ap.add_argument("--guard-verdict", type=Path, required=True)
    ap.add_argument("--strike-verdict", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--csv", type=Path, default=None)
    a = ap.parse_args(argv)
    panels = {
        "guard": {"short": curve(a.guard_short), "long": curve(a.guard_long), "factor": "3x",
                  "short_label": "T51", "long_label": "T54", "result": side_result(a.guard_verdict, "guard"),
                  "final_x": final_steps(a.guard_long)},
        "strike": {"short": curve(a.strike_short), "long": curve(a.strike_long), "factor": "5x",
                   "short_label": "T52, ABORTED", "long_label": "T55", "result": side_result(a.strike_verdict, "strike"),
                   "final_x": final_steps(a.strike_long)},
    }
    draw(panels, a.out)
    if a.csv is not None:
        a.csv.parent.mkdir(parents=True, exist_ok=True)
        with a.csv.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["side", "run", "game_steps_billion", "win_share"])
            for side, p in panels.items():
                for which in ("short", "long"):
                    for x, y in p[which]:
                        w.writerow([side, p[f"{which}_label"], f"{x:.4f}", f"{y:.4f}"])
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
