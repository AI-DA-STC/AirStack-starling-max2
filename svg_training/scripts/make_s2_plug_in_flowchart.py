#!/usr/bin/env python3
"""Flowchart for docs/PLUG_IN.md: the three layers of the S2 plug-in point and the two ways in.

Usage: python scripts/make_s2_plug_in_flowchart.py [out.png]   (default docs/figures/s2_plug_in_flow.png)
Draws boxes and arrows only; it reads no run data. Palette: scripts/make_s0_figures.py SERIES."""
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
    ("you_s", 0.4, 7.2, 6.6, 1.4, GREY, "Your strategy",
     "a scripted rule, a central planner\nor a trained network"),
    ("you_t", 9.0, 7.2, 6.6, 1.4, GREY, "Your training method",
     "skrl (IPPO, MAPPO) or any learner\nthat drives a Gymnasium vector env"),
    ("contract", 0.4, 4.4, 6.6, 2.0, BLUE, "Layer 2: the strategy contract",
     "core/strategy.py\nact(obs [N, drones, 69]) -> actions [N, drones, 4]\n"
     "reset(games [N]): these games just started\ncheck_strategy(...) names any broken rule"),
    ("adapters", 9.0, 4.4, 6.6, 2.0, ORANGE, "Layer 3: the adapters",
     "envs/skrl_adapter.py  SvgSkrlEnv: one agent per drone\n"
     "envs/gym_adapter.py  SvgTeamVectorEnv: one team,\nthe other team played by a fixed strategy"),
    ("score", 0.4, 1.6, 6.6, 1.9, GOLD, "scripts/score.py",
     "plays your strategy against the scripted ones\nin every arena size band; prints hold rates,\n"
     "closest approach (pure rules and Starling layer)"),
    ("game", 9.0, 1.6, 6.6, 1.9, GREEN, "Layer 1: the game (core/game.py)",
     "N games at once on one GPU, PyTorch only\npure partner rules, or with the Starling layer\n"
     "reset() and step(actions) on tensors"),
]
ARROWS = [("you_s", "contract", "write a class with act and reset"),
          ("you_t", "adapters", "wrap the game"),
          ("contract", "score", "--guard my_mod:MyGuard"),
          ("adapters", "game", "reset / step"),
          ("score", "game", "")]


def _anchor(box, side):
    _, x, y, w, h = box[:5]
    return {"top": (x + w / 2, y + h), "bottom": (x + w / 2, y), "right": (x + w, y + h / 2),
            "left": (x, y + h / 2)}[side]


def main(out: str) -> None:
    fig, ax = plt.subplots(figsize=(12, 6.75), dpi=150)
    ax.set_xlim(0, 16)
    ax.set_ylim(1.4, 9)
    ax.axis("off")
    boxes = {b[0]: b for b in BOXES}
    for key, x, y, w, h, colour, title, body in BOXES:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05,rounding_size=0.15",
                                    facecolor=colour + "22", edgecolor=colour, linewidth=2))
        ax.text(x + 0.2, y + h - 0.22, title, ha="left", va="top", fontsize=12, fontweight="bold", color=INK)
        ax.text(x + 0.2, y + h - 0.62, body, ha="left", va="top", fontsize=9.5, color=INK, linespacing=1.35)
    for a, b, label in ARROWS:
        if a == "score":
            p, q = _anchor(boxes[a], "right"), _anchor(boxes[b], "left")
        else:
            p, q = _anchor(boxes[a], "bottom"), _anchor(boxes[b], "top")
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=18, linewidth=1.8, color=INK))
        if label:
            ax.text(p[0] + 0.15, (p[1] + q[1]) / 2, label, ha="left", va="center", fontsize=9, color=GREY,
                    style="italic")
    ax.text((7.0 + 9.0) / 2, 2.55 + 0.25, "reset / step", ha="center", va="bottom", fontsize=9, color=GREY,
            style="italic")
    ax.text(8.0, 8.85, "Two ways in: score a strategy (left) or train one (right). Both end in the same game.",
            ha="center", va="center", fontsize=11, color=INK)
    out_p = pathlib.Path(out)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_p, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote {out_p}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "docs" / "figures" / "s2_plug_in_flow.png"))
