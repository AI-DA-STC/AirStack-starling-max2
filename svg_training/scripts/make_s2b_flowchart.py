#!/usr/bin/env python3
"""Flowchart for docs/S2B_RESULTS.md: one game, three ways to move the drones; S2b adds the physics drone.

Usage: python scripts/make_s2b_flowchart.py [out.png]   (default docs/figures/s2b_flow.png)
Draws boxes and arrows only; it reads no run data. Palette: scripts/make_s0_figures.py SERIES, as
scripts/make_s2_plug_in_flowchart.py. CPU only; no Isaac."""
import pathlib
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
BLUE, ORANGE, GREEN, GOLD = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, GREY = "#1f1f1f", "#6b6b6b"

# (key, x, y, w, h, colour, title, body); x, y = lower-left corner in figure units (0..16 x 0..9)
BOXES = [
    ("game", 0.4, 7.3, 15.2, 1.25, GREEN, "The game (core/game.py): the same for every backend",
     "rules, arenas, zone, observations, rewards, strategies, scoring tool and adapters; PyTorch, thousands of games"),
    ("pure", 0.4, 2.9, 4.4, 3.6, GREY, "Pure partner rules (pure)",
     "drones are points at fixed team\nspeeds, all at one height\n\npush-apart rule keeps the two\nteams "
     "apart\n\nPyTorch only (S2)"),
    ("chain", 5.4, 5.3, 10.2, 1.2, BLUE, "Command chain (models/command_chain.py), shared",
     "CMU's commander copy + the safety filter on every pair of drones -> trajectory setpoint"),
    ("fitted", 5.4, 2.9, 4.5, 1.75, GOLD, "Tier 1: fitted drone model",
     "real_exploratory_v0 (exploratory),\nfitted to one real flight;\nPyTorch only (S1, S2)"),
    ("drone", 10.5, 2.9, 5.1, 1.75, ORANGE, "Physics drone (S2b)",
     "PX4 1.14 cascade, drone's gains (yaw-rate\nSIM-ONLY) -> rotor model (motor lag,\nCAD rotor "
     "positions) -> one force + torque"),
    ("isaac", 10.5, 0.4, 2.45, 1.75, ORANGE, "Isaac Lab world",
     "PhysX rigid bodies\non the GPU; used for\nruns and clips"),
    ("torch", 13.15, 0.4, 2.45, 1.75, GREY, "PyTorch world",
     "reference: same\nequations, CPU tests;\nthe test oracle (T10)"),
]
# (from, to, from side, to side, label)
ARROWS = [("game", "pure", "bottom", "top", "pure"),
          ("game", "chain", "bottom", "top", "starling / physics"),
          ("chain", "fitted", "bottom", "top", "starling"),
          ("chain", "drone", "bottom", "top", "physics"),
          ("drone", "isaac", "bottom", "top", ""),
          ("drone", "torch", "bottom", "top", "")]


def _anchor(box, side, dx=0.0):
    _, x, y, w, h = box[:5]
    return {"top": (x + w / 2 + dx, y + h), "bottom": (x + w / 2 + dx, y), "right": (x + w, y + h / 2),
            "left": (x, y + h / 2)}[side]


def main(out: str) -> None:
    fig, ax = plt.subplots(figsize=(12, 6.75), dpi=150)
    ax.set_xlim(0, 16)
    ax.set_ylim(0.2, 9.3)
    ax.axis("off")
    boxes = {b[0]: b for b in BOXES}
    for key, x, y, w, h, colour, title, body in BOXES:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05,rounding_size=0.15",
                                    facecolor=colour + "22", edgecolor=colour, linewidth=2))
        ax.text(x + 0.15, y + h - 0.18, title, ha="left", va="top", fontsize=10.5, fontweight="bold", color=INK)
        ax.text(x + 0.15, y + h - 0.58, body, ha="left", va="top", fontsize=8.6, color=INK, linespacing=1.3)
    for a, b, sa, sb, label in ARROWS:
        if a == "game" and b == "chain":                       # aim at the chain's middle column
            p = (boxes["chain"][1] + boxes["chain"][3] / 2, boxes["game"][2])
            q = (p[0], boxes["chain"][2] + boxes["chain"][4])
        elif a == "chain":                                     # straight down onto each box below
            q = _anchor(boxes[b], sb)
            p = (q[0], boxes["chain"][2])
        elif a == "game":
            q = _anchor(boxes[b], sb)
            p = (q[0], boxes["game"][2])
        else:
            q = _anchor(boxes[b], sb)
            p = (q[0], boxes[a][2])
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=16, linewidth=1.6, color=INK))
        if label:
            ax.text(p[0] + 0.12, (p[1] + q[1]) / 2, label, ha="left", va="center", fontsize=8.6, color=GREY,
                    style="italic")
    ax.text(10.5 + 5.1 / 2, 2.55, "one of two worlds", ha="center", va="center", fontsize=8.2, color=GREY,
            style="italic", bbox=dict(facecolor="white", edgecolor="none", pad=1))
    ax.text(5.4 + 4.5 / 2, 1.3, "score.py --presets pure, starling or physics\npicks the backend; "
            "T13 plays the same\ngames on starling and physics", ha="center", va="center", fontsize=8.4,
            color=GREY)
    ax.text(8.0, 9.0, "One game, three ways to move the drones. S2b adds the physics drone (orange).",
            ha="center", va="center", fontsize=11, color=INK)
    out_p = pathlib.Path(out)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_p, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote {out_p}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "docs" / "figures" / "s2b_flow.png"))
