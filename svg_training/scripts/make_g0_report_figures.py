#!/usr/bin/env python
"""Figure of the G0 report (ste_learning/G0_REPORT.md): a top view of the game, drawn from the game files themselves.

    make_g0_report_figures.py [--base configs/ste_l011/base.toml] [--tag-file configs/ste_l011/tag_1p15.toml]
                              [--out docs/figures/g0_report/game_diagram.png]

Every length in the drawing is read from the two game files and the parameter file they name (no value is typed here):
the arena side, the keep-in square (half the side less the wall margin, a limit on x and on y), the zone radius (its
fraction of the side), the Guard start disc, the Strike start ring, the safety filter's distance (twice the commander's
per-drone safety radius in [starling_layer] params) and the two tag distances (1.6 m from base.toml, 1.15 m from
tag_1p15.toml). The files are read with tomllib only; the partner's local rules file is never opened. The drone positions are examples, not a
game. Training simulator rules; nothing here is a flight result."""
from __future__ import annotations

import argparse
import math
import tomllib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Circle, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GUARD_COLOUR = "#0072B2"           # Okabe-Ito blue: the Guard team (as make_ste_l012c_figure.py)
STRIKE_COLOUR = "#E69F00"          # Okabe-Ito orange: the Strike team
ZONE_COLOUR = "#009E73"            # Okabe-Ito bluish green: the zone
TAG_WIDE_COLOUR = "#CC79A7"        # Okabe-Ito reddish purple: tag 1.6 m
TAG_CLOSE_COLOUR = "#D55E00"       # Okabe-Ito vermillion: tag 1.15 m
INK, MUTED = "#1a1a1a", "#666666"


def game_values(base: Path, tag_file: Path) -> dict:
    """The lengths the diagram uses, in metres, derived from the two game files (tomllib, nothing else)."""
    b = tomllib.loads(base.read_text())
    t = tomllib.loads(tag_file.read_text())
    # the safety filter: the commander's per-drone safety radius in the Starling layer's parameter file; two drones keep
    # twice that apart, centre to centre (partner_rules.keepout_*_m is the push rule's distance, not the filter's)
    params = tomllib.loads((ROOT / b["starling_layer"]["params"]).read_text())
    side = float(b["arena"]["bands_m"]["lab"][0])
    return {
        "side_m": side,
        "keep_in_m": side / 2 - float(b["arena"]["wall_margin_m"]),
        "zone_m": float(b["arena"]["zone_radius_frac"][0]) * side,
        "guard_disc_m": float(b["starts"]["guard_disc_m"]),
        "strike_ring_m": float(b["starts"]["strike_ring_m"]),
        "filter_m": 2 * float(params["filter"]["safety_radius_m"]),
        "tag_wide_m": float(b["tag"]["radius_m"]),
        "tag_close_m": float(t["tag"]["radius_m"]),
        "start_height_m": float(b["arena"]["start_height_m"]),
        "height_band_m": tuple(float(v) for v in b["arena"]["height_band_m"]),
    }


def draw(v: dict, out: Path) -> None:
    half, keep, zone = v["side_m"] / 2, v["keep_in_m"], v["zone_m"]
    fig, ax = plt.subplots(figsize=(11, 7.2))
    ax.add_patch(Rectangle((-half, -half), 2 * half, 2 * half, fill=False, ec=INK, lw=2))
    ax.add_patch(Rectangle((-keep, -keep), 2 * keep, 2 * keep, fill=False, ec=MUTED, lw=1.2, ls="--"))
    ax.add_patch(Circle((0, 0), zone, color=ZONE_COLOUR, alpha=0.18, lw=0))
    ax.add_patch(Circle((0, 0), zone, fill=False, ec=ZONE_COLOUR, lw=2))
    ax.add_patch(Circle((0, 0), v["guard_disc_m"], color=GUARD_COLOUR, alpha=0.15, lw=0))
    ax.add_patch(Circle((0, 0), v["guard_disc_m"], fill=False, ec=GUARD_COLOUR, lw=1.2, ls=":"))
    ax.add_patch(Circle((0, 0), v["strike_ring_m"], fill=False, ec=STRIKE_COLOUR, lw=1.5, ls="-."))

    # example drones: one Guard inside the start disc, three Strikes on the start ring
    guard = (0.45 * v["guard_disc_m"], -0.35 * v["guard_disc_m"])
    for ang in (30, 150, 300):
        a = math.radians(ang)
        ax.plot(v["strike_ring_m"] * math.cos(a), v["strike_ring_m"] * math.sin(a), "^", ms=11, color=STRIKE_COLOUR,
                mec=INK, mew=0.8)
    ax.plot(*guard, "o", ms=11, color=GUARD_COLOUR, mec=INK, mew=0.8)
    for r, colour, ls in ((v["tag_wide_m"], TAG_WIDE_COLOUR, "-"), (v["tag_close_m"], TAG_CLOSE_COLOUR, "-"),
                          (v["filter_m"], INK, ":")):
        ax.add_patch(Circle(guard, r, fill=False, ec=colour, lw=1.6, ls=ls))

    # labels in text ink
    ax.annotate(f"zone, radius {zone:.2f} m", (0, zone), (0, zone + 0.25), ha="center", color=INK, fontsize=9)
    ax.text(0, -v["strike_ring_m"] + 0.15, f"Strike start ring, radius {v['strike_ring_m']:.2f} m", ha="center",
            color=INK, fontsize=9)
    ax.text(-half + 0.08, half + 0.1, f"arena {v['side_m']:.2f} m square", color=INK, fontsize=9)

    # scale bar: 1 m
    ax.plot([half - 1.3, half - 0.3], [-half + 0.55] * 2, color=INK, lw=3)
    ax.text(half - 0.8, -half + 0.65, "1 m", ha="center", color=INK, fontsize=9)

    handles = [
        Line2D([], [], color=ZONE_COLOUR, lw=2, label=f"zone (radius {zone:.2f} m; any height in "
               f"{v['height_band_m'][0]:.1f}–{v['height_band_m'][1]:.1f} m)"),
        Line2D([], [], color=GUARD_COLOUR, lw=1.2, ls=":", label=f"Guard start disc (radius {v['guard_disc_m']:.2f} m)"),
        Line2D([], [], color=STRIKE_COLOUR, lw=1.5, ls="-.", label=f"Strike start ring ({v['strike_ring_m']:.2f} m)"),
        Line2D([], [], color=MUTED, lw=1.2, ls="--", label=f"keep-in square (±{keep:.2f} m in x and y)"),
        Line2D([], [], marker="o", ls="", ms=9, color=GUARD_COLOUR, mec=INK, label="Guard drone (example position)"),
        Line2D([], [], marker="^", ls="", ms=9, color=STRIKE_COLOUR, mec=INK, label="Strike drone (example position)"),
        Line2D([], [], color=TAG_WIDE_COLOUR, lw=1.6, label=f"tag distance {v['tag_wide_m']:.2f} m round one Guard"),
        Line2D([], [], color=TAG_CLOSE_COLOUR, lw=1.6, label=f"tag distance {v['tag_close_m']:.2f} m round one Guard"),
        Line2D([], [], color=INK, lw=1.6, ls=":", label=f"safety filter {v['filter_m']:.2f} m round one Guard"),
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=False, fontsize=9,
              labelcolor=INK, title="All distances centre to centre", title_fontsize=9)
    ax.set_xlim(-half - 0.2, half + 0.2)
    ax.set_ylim(-half - 0.2, half + 0.4)
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)", color=INK)
    ax.set_ylabel("y (m)", color=INK)
    ax.tick_params(colors=INK)
    ax.set_title(f"The game seen from above (start height {v['start_height_m']:.1f} m); drawn from the game files",
                 color=INK, fontsize=11, loc="left")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--base", type=Path, default=ROOT / "configs/ste_l011/base.toml")
    p.add_argument("--tag-file", type=Path, default=ROOT / "configs/ste_l011/tag_1p15.toml")
    p.add_argument("--out", type=Path, default=ROOT / "docs/figures/g0_report/game_diagram.png")
    a = p.parse_args(argv)
    draw(game_values(a.base, a.tag_file), a.out)
    print(a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
