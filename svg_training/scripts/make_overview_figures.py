"""Overview figures for the front page (svg_training/README.md, "At a glance").

Two pictures, drawn with matplotlib, no data files needed (the numbers are copied from the records named below):

* ``docs/figures/overview_story.png``: what was done, from NUS's JAX training to the STE Guard policy.
* ``docs/figures/overview_tests.png``: the six tests (G19 vs S20, Strike reaches of 1,000; records T18-T24) and, in Test 5
  conditions, how often each Guard holds the zone (G19 17, Parked Guard 429 (T23), STE Guard policy 829 (T41)).

Run from svg_training/:  PYTHONPATH=source python scripts/make_overview_figures.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs" / "figures"

INK = "#1f2933"
MUTED = "#616e7c"
GREEN, GREEN_BG = "#2e7d32", "#e3f4e4"
RED, RED_BG = "#c62828", "#fde8e8"
AMBER, AMBER_BG = "#b7791f", "#fff4dc"
BLUE, BLUE_BG = "#1f5fa8", "#e6effa"
PURPLE, PURPLE_BG = "#6b3fa0", "#f0e9f8"
ORANGE, ORANGE_BG = "#c05621", "#fdeee3"
GREY, GREY_BG = "#7b8794", "#f2f4f6"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "text.color": INK})


def box(ax, x, y, w, h, fc, ec, lw=1.6, ls="-", r=0.025):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw,
                                ls=ls))


def arrow(ax, p, q, color=INK, ls="-", lw=2.0, rad=0.0):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=18, color=color, lw=lw, ls=ls,
                                 connectionstyle=f"arc3,rad={rad}", shrinkA=2, shrinkB=2))


def story() -> Path:
    fig, ax = plt.subplots(figsize=(16, 7.8), dpi=110)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 7.8)
    ax.axis("off")

    # three stage panels
    stages = [(0.2, 4.6, "NUS's world", "NUS's 2-D game · JAX", BLUE, BLUE_BG),
              (5.35, 4.6, "Copied into PyTorch", "same conditions · checked exact", PURPLE, PURPLE_BG),
              (10.5, 5.35, "STE drone conditions", "STE drone model (PyTorch) · Isaac Lab", ORANGE, ORANGE_BG)]
    for x, w, title, sub, c, bg in stages:
        box(ax, x, 0.85, w, 6.75, bg, c, lw=1.2, r=0.08)
        ax.text(x + 0.25, 7.2, title, fontsize=15, weight="bold", color=c, va="center")
        ax.text(x + 0.25, 6.8, sub, fontsize=10.5, color=MUTED, va="center")

    # 1 train with NUS's code
    box(ax, 0.55, 3.75, 3.9, 2.3, "white", BLUE)
    ax.text(0.8, 5.6, "1", fontsize=20, weight="bold", color=BLUE, va="center")
    ax.text(1.25, 5.6, "Train with NUS's code", fontsize=12.5, weight="bold", va="center")
    ax.text(0.8, 4.95, "STE ran NUS's self-play and\nfixed-opponent training (JAX)", fontsize=10.5, color=MUTED,
            va="center")
    ax.text(0.8, 4.15, "in NUS's flat 2-D game", fontsize=10.5, color=MUTED, va="center")
    # checkpoints chips
    for i, name in enumerate(["G19", "S20", "P3G", "P3S"]):
        cx = 0.75 + i * 0.95
        box(ax, cx, 2.75, 0.74, 0.55, BLUE, BLUE, r=0.12)
        ax.text(cx + 0.37, 3.02, name, fontsize=11, weight="bold", color="white", ha="center", va="center")
    ax.text(2.5, 2.45, "trained policies (checkpoints)", fontsize=10, color=MUTED, ha="center")
    ax.text(2.5, 1.6, "Guard team  ·  Strike team", fontsize=10, color=MUTED, ha="center")
    ax.text(2.5, 1.2, "(NUS: defender  ·  attacker)", fontsize=9.5, color=MUTED, ha="center")
    arrow(ax, (2.5, 3.75), (2.5, 3.33), BLUE)

    # 2 copy game, 3 convert policies
    for (y, n, t, s) in [(4.55, "2", "Copy NUS's game", "step by step, position error\n≤ 5.7e-6 (limit 1e-4)"),
                         (1.75, "3", "Convert the policies", "action error ≤ 0.0105\n(limit 0.02)")]:
        box(ax, 5.65, y, 4.0, 1.75, "white", PURPLE)
        ax.text(5.9, y + 1.35, n, fontsize=20, weight="bold", color=PURPLE, va="center")
        ax.text(6.35, y + 1.35, t, fontsize=12.5, weight="bold", va="center")
        ax.text(5.9, y + 0.62, s, fontsize=10.5, color=MUTED, va="center")
        box(ax, 8.75, y + 0.2, 0.75, 0.42, GREEN_BG, GREEN, r=0.1)
        ax.text(9.125, y + 0.41, "✓ exact", fontsize=8.5, color=GREEN, ha="center", va="center", weight="bold")
    arrow(ax, (4.6, 3.02), (5.6, 2.6), INK)
    arrow(ax, (4.45, 4.9), (5.6, 5.4), INK)

    # 4 test
    box(ax, 10.8, 4.25, 4.75, 2.1, "white", RED)
    ax.text(11.05, 5.95, "4", fontsize=20, weight="bold", color=RED, va="center")
    ax.text(11.5, 5.95, "Test NUS's policies", fontsize=12.5, weight="bold", va="center")
    ax.text(11.05, 5.35, "Tests 1–6: add one drone\ncondition at a time", fontsize=10.5, color=MUTED, va="center")
    ax.text(11.05, 4.6, "Strike reaches  9 → 979 / 1,000", fontsize=11.5, color=RED, weight="bold", va="center")
    box(ax, 14.45, 5.7, 0.95, 0.5, RED_BG, RED, r=0.1)
    ax.text(14.92, 5.95, "✗ fail", fontsize=10, color=RED, ha="center", va="center", weight="bold")
    arrow(ax, (9.7, 2.6), (10.75, 4.9), INK, rad=-0.15)

    # 5 retrain
    box(ax, 10.8, 2.45, 4.75, 1.3, "white", INK)
    ax.text(11.05, 3.3, "5", fontsize=20, weight="bold", color=INK, va="center")
    ax.text(11.5, 3.3, "Retrain in STE conditions", fontsize=12.5, weight="bold", va="center")
    ax.text(11.05, 2.75, "(safety filter, 3-D, drone lag)", fontsize=10.5, color=MUTED, va="center")
    arrow(ax, (13.17, 4.25), (13.17, 3.8), INK)

    # 5a STE Guard policy, 5b method port
    box(ax, 10.8, 1.05, 2.3, 1.1, GREEN_BG, GREEN, lw=2.0)
    ax.text(11.95, 1.85, "STE Guard policy", fontsize=11, weight="bold", ha="center", va="center", color=GREEN)
    ax.text(11.95, 1.52, "holds 829 / 1,000", fontsize=12.5, weight="bold", ha="center", va="center")
    ax.text(11.95, 1.2, "✓ works (pilot P1b)", fontsize=9.5, ha="center", va="center", color=GREEN)
    box(ax, 13.25, 1.05, 2.3, 1.1, GREY_BG, GREY, ls="--")
    ax.text(14.4, 1.85, "NUS's method", fontsize=11, weight="bold", ha="center", va="center", color=MUTED)
    ax.text(14.4, 1.52, "copied into PyTorch", fontsize=10, ha="center", va="center", color=MUTED)
    ax.text(14.4, 1.2, "5.1 FAIL; route paused", fontsize=9.5, ha="center", va="center", color=MUTED)
    arrow(ax, (12.4, 2.45), (12.0, 2.18), GREEN)
    arrow(ax, (14.0, 2.45), (14.4, 2.18), GREY, ls="--")

    # next
    ax.text(8.0, 0.4, "Since 20 Nov: STE trains its own teams in a game with a tag (see the overview page)",
            fontsize=11.5, color=MUTED, ha="center", va="center", style="italic")
    fig.tight_layout(pad=0.2)
    p = OUT / "overview_story.png"
    fig.savefig(p, facecolor="white")
    plt.close(fig)
    return p


def tests() -> Path:
    fig = plt.figure(figsize=(16, 6.6), dpi=110)
    gs = fig.add_gridspec(1, 2, width_ratios=[3.15, 1.0], wspace=0.18, left=0.065, right=0.985, top=0.84, bottom=0.27)
    ax = fig.add_subplot(gs[0, 0])
    tests_ = [("Test 1", "NUS's conditions\nin PyTorch", 9, GREEN),
              ("Test 2", "+ STE game engine\n0.6 s steps, walls,\nkeep-apart", 17, GREEN),
              ("Test 3", "+ drone delay\nand lag", 43, GREEN),
              ("Test 4", "+ safety filter\nno pushing", 740, AMBER),
              ("Test 5", "+ free height (3-D)\nover and under", 983, RED),
              ("Test 6", "Isaac Lab\nphysics drones", 979, RED)]
    xs = range(len(tests_))
    for i, (t, cond, v, c) in enumerate(tests_):
        ax.bar(i, v, width=0.62, color=c, alpha=0.88, zorder=3)
        ax.text(i, v + 22, f"{v}", ha="center", va="bottom", fontsize=17, weight="bold", color=c)
        ax.text(i, -95, t, ha="center", va="top", fontsize=12.5, weight="bold")
        ax.text(i, -175, cond, ha="center", va="top", fontsize=10, color=MUTED, linespacing=1.15)
    ax.set_xlim(-0.6, 5.6)
    ax.set_ylim(0, 1080)
    ax.set_xticks([])
    ax.set_yticks([0, 250, 500, 750, 1000])
    ax.tick_params(axis="y", colors=MUTED, labelsize=10)
    for s in ("top", "right", "bottom"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#c5cbd3")
    ax.grid(axis="y", color="#e4e7eb", zorder=0)
    ax.set_ylabel("Strike reaches the zone (of 1,000 games)", fontsize=11, color=MUTED)
    ax.set_title("G19 Guard vs S20 Strike in the STE drone game (PyTorch): one condition per test",
                 fontsize=13.5, weight="bold", loc="left", pad=14)
    ax.annotate("pushing no longer works", xy=(3, 740), xytext=(1.6, 640), fontsize=10.5, color=AMBER,
                arrowprops=dict(arrowstyle="-|>", color=AMBER, lw=1.4), ha="center")
    ax.annotate("Strikes pass over / under", xy=(4, 983), xytext=(2.75, 905), fontsize=10.5, color=RED,
                arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.4), ha="center")

    bx = fig.add_subplot(gs[0, 1])
    guards = [("G19\n(NUS's code)", 17, RED), ("Parked\nGuard", 429, AMBER), ("STE Guard\npolicy", 829, GREEN)]
    for i, (g, v, c) in enumerate(guards):
        bx.bar(i, v, width=0.6, color=c, alpha=0.88, zorder=3)
        bx.text(i, v + 22, f"{v}", ha="center", va="bottom", fontsize=17, weight="bold", color=c)
        bx.text(i, -95, g, ha="center", va="top", fontsize=10.5, weight="bold", linespacing=1.15)
    bx.set_xlim(-0.6, 2.6)
    bx.set_ylim(0, 1080)
    bx.set_xticks([])
    bx.set_yticks([0, 250, 500, 750, 1000])
    bx.tick_params(axis="y", colors=MUTED, labelsize=10)
    for s in ("top", "right", "bottom"):
        bx.spines[s].set_visible(False)
    bx.spines["left"].set_color("#c5cbd3")
    bx.grid(axis="y", color="#e4e7eb", zorder=0)
    bx.set_ylabel("Guard holds the zone (of 1,000 games)", fontsize=11, color=MUTED)
    bx.set_title("Test 5 conditions, vs S20:\nwho holds the zone?", fontsize=13.5, weight="bold", loc="left", pad=14)
    fig.text(0.065, 0.018, "Observed in the training simulator; nothing here has flown. Records: T18–T24 (tests), "
             "T23 (Parked Guard), T41 (STE Guard policy).", fontsize=9.5, color=MUTED)
    p = OUT / "overview_tests.png"
    fig.savefig(p, facecolor="white")
    plt.close(fig)
    return p


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for p in (story(), tests()):
        print("wrote", p)
