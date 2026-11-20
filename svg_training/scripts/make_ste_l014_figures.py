#!/usr/bin/env python
"""Figures of L0.14 Crazyflie route check, drawn from the runs' own result files (STANDARDS section 7 rule 2: the numbers
plotted are the numbers in the tables of ste_learning/CRAZYFLIE_ROUTE.md).

    make_ste_l014_figures.py --response runs/<date>_ste_l014/response/results.json \\
        --arena runs/<date>_ste_l014/arena_fit/arena.json [--out ste_learning/figures]

Writes:
- ``l014_hold_by_delay.png``: T41's hold rate (Wilson 95 %) at each drone delay; the games lost and gained against the
  Starling cell, paired by start; the games in which a Guard drone and a Strike drone came closer than 1.10 m, 1.0 m and
  0.50 m (3-D), from per_game.npz beside the results file (three panels, one measure each);
- ``l014_step.png``: how far the drone trails the commanded path while flying a constant command, per delay;
- ``l014_arena_fit.png``: per team size and arena (the planner's default pairing), matches with at least one solver
  emergency, and matches whose closest airborne pair came inside 1.10 m, counts printed on the bars.
Exit 0 when written."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = "#0072B2"                                    # Okabe-Ito blue: the Guard team (as the other figures)
ARENA_COLOURS = {"square_6_5": "#0072B2", "circle_3_25": "#E69F00", "room": "#009E73"}   # validated (dataviz), fixed order
ARENA_NAMES = {"square_6_5": "6.5 m square", "circle_3_25": "3.25 m circle", "room": "Crazyflie room (~10 x 10 m)"}
DELAY_BLUES = ["#9ecae1", "#4292c6", "#08519c", "#08306b"]   # one hue, light to dark: short to long delay
INK, MUTED, GRID = "#1a1a1a", "#666666", "#e6e6e6"
DPI = 120
# Closest Guard-Strike approach (3-D) thresholds counted in part 1: the flight filter's distance (1.10 m, cbf_safety_radius_m
# 0.55 x 2), the hangar game's keep-out (1.0 m, the game's own rule_breach measure: min(keepout_guard_m, keepout_strike_m)),
# and the game's contact distance (0.50 m, nus_hangar_game.toml [contact_rules] contact_m: "a crash in flight").
CLOSE_M = ((1.10, "inside 1.10 m (filter distance)"), (1.0, "inside 1.0 m (the game's keep-out)"),
           (0.50, "inside 0.50 m (contact distance)"))


def _style(ax) -> None:
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelcolor=INK)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def closest_counts(resp: dict) -> dict:
    """{delay_s: {threshold_m: games whose closest Guard-Strike approach (3-D) was below it}}, from the run's per_game.npz
    (``resp["per_game_path"]``, set by main from the results file's folder)."""
    import numpy as np
    z = np.load(resp["per_game_path"])
    return {c["delay_s"]: {thr: int((z[f"delay_{c['delay_s']:.4f}__closest_cross_3d_m"] < thr).sum()) for thr, _ in CLOSE_M}
            for c in resp["cells"]}


def hold_by_delay(resp: dict, out: Path) -> Path:
    import matplotlib.pyplot as plt
    cells = resp["cells"]
    ref = cells[resp["reference_cell"]]
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(13.5, 3.8), dpi=DPI)
    x = list(range(len(cells)))
    h = [c["hold"] for c in cells]
    lo = [c["hold"] - c["ci"][0] for c in cells]
    hi = [c["ci"][1] - c["hold"] for c in cells]
    a1.errorbar(x, h, yerr=[lo, hi], fmt="o", color=GUARD, ms=8, capsize=4, lw=2)
    for k, c in enumerate(cells):
        a1.annotate(f"{c['holds']}/{c['games']}", (k, c["ci"][0]), textcoords="offset points", xytext=(0, -8), ha="center",
                    va="top", fontsize=8, color=INK)
    a1.set_xticks(x, [f"{c['delay_s']:.2f} s\ntrails {c['trailing_s']:.2f} s" for c in cells])
    a1.set_xlabel("drone delay in the model, and how late the drone flies", color=INK)
    a1.set_ylabel("Guard hold rate (Wilson 95 %)", color=INK)
    a1.set_ylim(0, 1.05)
    a1.set_xlim(-0.5, len(cells) - 0.5)
    a1.set_title(f"T41 v S20, {ref['games']} paired starts", fontsize=10, color=INK, loc="left")
    _style(a1)
    others = [c for c in cells if c is not ref]
    labels = [f"{c['delay_s']:.2f} s" for c in others]
    import numpy as np
    pos = np.arange(len(others))
    lost = [c["paired"]["lost_here"] if c.get("paired") else 0 for c in others]
    gained = [c["paired"]["gained_here"] if c.get("paired") else 0 for c in others]
    b1 = a2.bar(pos - 0.18, lost, 0.34, color="#08519c", label="held at the Starling delay, lost here")
    b2 = a2.bar(pos + 0.18, gained, 0.34, color="#9ecae1", label="lost at the Starling delay, held here")
    a2.bar_label(b1, color=INK, fontsize=8)
    a2.bar_label(b2, color=INK, fontsize=8)
    a2.set_xticks(pos, labels)
    a2.set_xlabel("drone delay in the model (s)", color=INK)
    a2.set_ylabel("games (same starts)", color=INK)
    a2.set_title(f"Change against {ref['delay_s']:.2f} s, game by game", fontsize=10, color=INK, loc="left")
    a2.legend(frameon=False, fontsize=8, loc="upper left")
    _style(a2)
    counts = closest_counts(resp)
    w = 0.8 / len(CLOSE_M)
    blues = ["#9ecae1", "#4292c6", "#08306b"]
    for j, (thr, label) in enumerate(CLOSE_M):
        vals = [counts[c["delay_s"]][thr] for c in cells]
        bars = a3.bar([k + (j - (len(CLOSE_M) - 1) / 2) * w for k in range(len(cells))], vals, w * 0.92, color=blues[j], label=label)
        a3.bar_label(bars, fontsize=7, color=INK, padding=1)
    a3.set_xticks(range(len(cells)), [f"{c['delay_s']:.2f} s" for c in cells])
    a3.set_ylim(0, max(max(v.values()) for v in counts.values()) * 1.45)
    a3.set_xlabel("drone delay in the model (s)", color=INK)
    a3.set_ylabel("games (of the cell's games)", color=INK)
    a3.set_title("Closest Guard-Strike approach, 3-D", fontsize=10, color=INK, loc="left")
    a3.legend(frameon=False, fontsize=7.5, loc="upper left")
    _style(a3)
    fig.text(0.01, 0.01, "Observed in the training simulator (tier 1, CPU). A sensitivity test, not a Crazyflie model.",
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    p = out / "l014_hold_by_delay.png"
    fig.savefig(p)
    plt.close(fig)
    return p


def step(resp: dict, out: Path) -> Path:
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.5, 3.4), dpi=DPI)
    for k, s in enumerate(resp["step"]):
        behind = [c - x for c, x in zip(s["cmd_x_m"], s["x_m"])]
        col = DELAY_BLUES[min(k + 1, len(DELAY_BLUES) - 1)] if len(resp["step"]) < len(DELAY_BLUES) else DELAY_BLUES[k]
        ax.plot(s["t_s"], behind, color=col, lw=2, label=f"delay {s['delay_s']:.2f} s")
        ax.annotate(f"{s['delay_s']:.2f} s", (s["t_s"][-1], behind[-1]), textcoords="offset points", xytext=(4, 0),
                    va="center", fontsize=8, color=INK)
    ax.set_xlabel("time since the command started (s)", color=INK)
    ax.set_ylim(0, None)
    ax.set_ylabel("behind the commanded path (m)", color=INK)
    ax.set_title("One drone, constant 0.5 m/s command from rest", fontsize=10, color=INK, loc="left")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    _style(ax)
    fig.tight_layout()
    p = out / "l014_step.png"
    fig.savefig(p)
    plt.close(fig)
    return p


def arena_fit(arena: dict, out: Path) -> Path:
    """Two panels, one measure each, per team size and arena (the planner's default pairing): matches with a solver
    emergency; matches whose closest airborne pair came inside the 1.10 m filter distance (closest pair printed)."""
    import matplotlib.pyplot as plt
    import numpy as np
    rows = [c for c in arena["cases"] if c["kind"] == "pairing"]
    sizes = sorted({(c["defenders"], c["attackers"]) for c in rows}, key=lambda s: (s[0] + s[1], s[0]))
    arenas = [a for a in ARENA_COLOURS if any(c["arena"] == a for c in rows)]
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8), dpi=DPI, sharey=False)
    pos = np.arange(len(sizes))
    w = 0.8 / max(len(arenas), 1)

    def case(a, g, s):
        return next((c for c in rows if c["arena"] == a and (c["defenders"], c["attackers"]) == (g, s)), None)

    for ax, key, title in ((axes[0], "emergency_matches", "Matches with a solver emergency"),
                           (axes[1], "matches_closer_than_d_cc", "Matches whose closest pair came inside 1.10 m")):
        top = 0
        for k, a in enumerate(arenas):
            vals, labels = [], []
            for g, s in sizes:
                c = case(a, g, s)
                if c is None or c["summary"] is None:
                    vals.append(0)
                    labels.append("refused" if c and c["refused"] else "")
                    continue
                sm = c["summary"]
                vals.append(sm[key])
                top = max(top, sm["matches"])
                labels.append(f"{sm[key]}/{sm['matches']}" if key == "emergency_matches" else f"{sm[key]}")
            bars = ax.bar(pos + (k - (len(arenas) - 1) / 2) * w, vals, w * 0.92, color=ARENA_COLOURS[a], label=ARENA_NAMES[a])
            ax.bar_label(bars, labels=labels, fontsize=7, color=INK, padding=2)
        ax.set_xticks(pos, [f"{g}v{s}" for g, s in sizes])
        ax.set_xlabel("Guard drones v Strike drones", color=INK)
        ax.set_ylabel("matches", color=INK)
        ax.set_ylim(0, max(top, 1) * 1.25)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        _style(ax)
    axes[0].legend(frameon=False, fontsize=8, loc="upper left")
    fig.text(0.01, 0.01, "Crazyflie planner, 1.10 m filter distance, lag 0.6 s, default pairing; closest pairs in the "
             "page's table. Simulated matches on the planner's stand-in aircraft; not a flight result.",
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    p = out / "l014_arena_fit.png"
    fig.savefig(p)
    plt.close(fig)
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--response", required=True)
    ap.add_argument("--arena", required=True)
    ap.add_argument("--out", default=str(ROOT / "ste_learning" / "figures"))
    a = ap.parse_args(argv)
    import matplotlib
    matplotlib.use("Agg")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    resp = json.loads(Path(a.response).read_text())
    resp["per_game_path"] = str(Path(a.response).parent / "per_game.npz")
    for d, row in closest_counts(resp).items():
        print(f"delay {d:.4f} s: games with the closest Guard-Strike approach (3-D) " +
              ", ".join(f"under {thr:.2f} m: {n}" for thr, n in row.items()))
    arena = json.loads(Path(a.arena).read_text())
    for p in (hold_by_delay(resp, out), step(resp, out), arena_fit(arena, out)):
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
