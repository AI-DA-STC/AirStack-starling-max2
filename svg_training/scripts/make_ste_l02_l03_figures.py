#!/usr/bin/env python
"""Figures of L0.2 (T48, speed) and L0.3 (T49, transfer) from their run folders' results.json. Observed in the training
simulator; not a flight.

    make_ste_l02_l03_figures.py --l02 runs/<speed run> --l02-out docs/figures/ste_l02/speed.png
                                --l03 runs/<transfer run> --l03-out docs/figures/ste_l03/transfer.png

speed.png: training game-steps per second against games at once, tier 1 and tier 2, 3v3 only, log axes (one axis pair).
transfer.png: T41's holds on each arm with Wilson 95 % intervals; the parked control's Strike reaches beside them,
labelled as reaches."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter, NullFormatter  # noqa: E402

TIER_COLOUR = {1: "#1baf7a", 2: "#7b4fa8"}      # tier identity (not a team): validated pair, labelled directly
TIER_NAME = {1: "tier 1 (fast engine)", 2: "tier 2 (Isaac Lab physics drone)"}
GUARD_COLOUR, STRIKE_COLOUR = "#0072B2", "#E69F00"   # team colours as in every svg_training figure
INK, MUTED, GRID = "#1a1a1a", "#666666", "#e0e0e0"


def speed_rows(results: dict, size: str = "3v3") -> dict[int, list[tuple[int, float]]]:
    """Per tier, (games at once, training game-steps/s) of the points that fit, sorted by games."""
    out: dict[int, list[tuple[int, float]]] = {1: [], 2: []}
    for r in results["rows"]:
        if r.get("size") == size and r.get("status") == "fit":
            out[int(r["tier"])].append((int(r["games"]), float(r["learner"]["train_game_steps_per_s"])))
    return {t: sorted(v) for t, v in out.items()}


def speed_figure(results: dict, out: Path) -> None:
    rows = speed_rows(results)
    fig, ax = plt.subplots(figsize=(7.5, 4.6), dpi=150)
    for tier, pts in rows.items():
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        ax.plot(xs, ys, color=TIER_COLOUR[tier], linewidth=2, marker="o", markersize=7, zorder=3,
                markeredgecolor="white", markeredgewidth=1.2)
        for x, y in pts:
            ax.annotate(f"{y / 1000:,.0f}k", (x, y), textcoords="offset points", xytext=(0, 8), ha="center",
                        fontsize=7, color=INK)
        ax.annotate(TIER_NAME[tier], (xs[-1], ys[-1]), textcoords="offset points", xytext=(10, -3), fontsize=8,
                    color=INK, va="center")
    tested_t1 = max(p[0] for p in rows[1])
    ax.annotate(f"tier 1 not run above {tested_t1:,}\n(not a memory limit)", (tested_t1, rows[1][-1][1]),
                textcoords="offset points", xytext=(10, -26), fontsize=7, color=MUTED)
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xticks([1024, 2048, 4096, 8192, 16384])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_xlim(800, 60000)
    ax.set_xlabel("games at once (log scale)", fontsize=8, color=INK)
    ax.set_ylabel("training game-steps per second (log scale)", fontsize=8, color=INK)
    ax.grid(which="major", color=GRID, linewidth=0.8, zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=7, colors=INK)
    ax.set_title("L0.2: training speed with a learner in the loop, 3v3, the L0.11 base game\n"
                 "one RTX 5070 Ti laptop GPU; observed in the training simulator, not a flight", fontsize=9, color=INK)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)


ARM_LABEL = {"t1_cpu_t41": "T41 v S20, tier 1, CPU", "t1_cuda_t41": "T41 v S20, tier 1, CUDA (information only)",
             "t2_t41": "T41 v S20, tier 2", "t2_parked": "parked Guards v S20, tier 2 (control)"}


def transfer_figure(results: dict, out: Path) -> None:
    order = ["t1_cpu_t41", "t1_cuda_t41", "t2_t41", "t2_parked"]
    fig, ax = plt.subplots(figsize=(8.0, 3.9), dpi=150)
    for i, arm in enumerate(order):
        s = results["arms"][arm]["summary"]
        lo, hi = s["ci"]
        colour = STRIKE_COLOUR if s["counted"] == "reaches" else GUARD_COLOUR
        ax.plot([lo, hi], [i, i], color=colour, linewidth=2.5, solid_capstyle="round", zorder=2)
        ax.scatter([s["rate"]], [i], s=64, color=colour, edgecolor="white", linewidth=1.2, zorder=3)
        ax.text(hi + 0.01, i, f"{s['count']} / {s['games']} {s['counted']}", va="center", fontsize=7.5, color=INK)
    ax.axhline(2.5, color=GRID, linewidth=1)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([ARM_LABEL[a] for a in order], fontsize=8, color=INK)
    ax.set_ylim(len(order) - 0.5, -0.6)
    ax.set_xlim(0.4, 1.0)
    ax.set_xlabel("share of 1,000 paired starts, Wilson 95 % (axis starts at 0.4)\n"
                  "T41 rows: Guard team holds (blue); control row: Strike team reaches (orange)", fontsize=8, color=INK)
    pair = results.get("t2_v_t1_cpu") or {}
    if pair:
        ax.text(0.41, 2.5, f"paired by start, tier 2 against tier 1 CPU: lost {pair.get('lost_here')}, gained "
                f"{pair.get('gained_here')}; sign test p = {pair.get('sign_test_p', float('nan')):.3f}",
                va="center", fontsize=7, color=MUTED, backgroundcolor="white")
    ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", labelsize=7, colors=INK)
    ax.set_title("L0.3: STE Guard policy T41 (trained on tier 1) on the Isaac Lab drone without retraining\n"
                 "hangar game, 3v3; observed in the training simulator, not a flight", fontsize=9, color=INK)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--l02", type=Path)
    ap.add_argument("--l02-out", type=Path)
    ap.add_argument("--l03", type=Path)
    ap.add_argument("--l03-out", type=Path)
    a = ap.parse_args(argv)
    if a.l02 and a.l02_out:
        speed_figure(json.loads((a.l02 / "results.json").read_text()), a.l02_out)
        print(f"wrote {a.l02_out}")
    if a.l03 and a.l03_out:
        transfer_figure(json.loads((a.l03 / "results.json").read_text()), a.l03_out)
        print(f"wrote {a.l03_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
