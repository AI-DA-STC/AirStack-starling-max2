"""Flowcharts for the STE learning track's front page (ste_learning/README.md).

Four pictures, drawn with matplotlib only. No data files are read: every number and every task name is copied from
ste_learning/PLAN.md (version 2, 20 Nov 2026) and, for decisions, ste_learning/DISCUSSION_2026-11-19_20.md.

* ``ste_learning/figures/architecture.png``: what is being built, the training loop and the path to the drones.
* ``ste_learning/figures/plan_phases.png``: the plan, phases L0 to L9 with their simulators and gates.
* ``ste_learning/figures/l0_tasks.png``: phase L0 step by step, four lanes of tasks ending in gate G0.
* ``ste_learning/figures/task_lifecycle.png``: how every task moves, who does each step, where the owner is asked.

Colour code: green = exists today in svg_training; blue = to build in this track; amber with a dashed border =
PROPOSED or OPEN, needs the owner's ruling; grey = outside svg_training, done by an AirStack session; red = human
gate, the owner decides. Each figure prints the part of the code it uses as a legend. Two legends differ in wording:
in plan_phases green marks phase L9 as "running now", and task_lifecycle adds a white chip for who does a step.

Each figure function checks its own drawing before saving: every label inside its box, no two labels overlapping,
no arrow through a label. A failed check raises, so a clipped or overlapping label cannot be saved unnoticed.

Run from svg_training/:
    unset PYTHONPATH; ~/miniconda3/envs/env_isaaclab/bin/python scripts/make_ste_learning_figures.py
One figure only:  ... scripts/make_ste_learning_figures.py architecture   (or plan_phases, l0_tasks, l0_progress, task_lifecycle)
Progress figure: edit ste_learning/status/l0_progress.toml, then  ... scripts/make_ste_learning_figures.py l0_progress
"""
from __future__ import annotations

import sys
import tomllib
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "ste_learning" / "figures"

# palette of scripts/make_overview_figures.py (the front page's figures)
INK = "#1f2933"
BODY = "#3e4c59"
MUTED = "#616e7c"
GREEN, GREEN_BG = "#2e7d32", "#e3f4e4"
RED, RED_BG = "#c62828", "#fde8e8"
AMBER, AMBER_BG = "#b7791f", "#fff4dc"
BLUE, BLUE_BG = "#1f5fa8", "#e6effa"
GREY, GREY_BG = "#7b8794", "#f2f4f6"
PANEL_BG = "#fafbfc"

W = 16.0  # figure width in inches; one data unit = one inch
DPI = 120
FS_TITLE, FS_SUB, FS_H, FS_B, FS_C = 20, 12.5, 14.5, 12.5, 11.5

# status -> (fill, edge, line style)
KIND = {
    "exists": (GREEN_BG, GREEN, "-"),
    "build": (BLUE_BG, BLUE, "-"),
    "open": (AMBER_BG, AMBER, (0, (4, 2.5))),
    "outside": (GREY_BG, GREY, "-"),
    "gate": (RED_BG, RED, "-"),
    "plain": ("white", MUTED, "-"),
}

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": FS_B, "text.color": INK})
warnings.filterwarnings("error", message=".*[Gg]lyph.*")

_TEXTS: list = []  # (artist, enclosing box (x, y, w, h) or None)
_SEGS: list = []   # arrow segments ((x0, y0), (x1, y1))


# ------------------------------------------------------------------------------------------------ drawing helpers
def new_fig(height: float):
    _TEXTS.clear()
    _SEGS.clear()
    fig = plt.figure(figsize=(W, height), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, height)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, fc, ec, lw=1.8, ls="-", r=0.07):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw,
                                ls=ls))


def txt(ax, x, y, s, size=FS_B, weight="normal", color=INK, ha="left", va="top", inside=None, style="normal"):
    t = ax.text(x, y, s, fontsize=size, weight=weight, color=color, ha=ha, va=va, linespacing=1.25, style=style)
    _TEXTS.append((t, inside))
    return t


def th(s: str, size: float) -> float:
    """Height in inches of a block of text (line count times line height)."""
    return (s.count("\n") + 1) * size / 72 * 1.25 + 0.04


def arrow(ax, p, q, color=INK, ls="-", lw=2.2, both=False):
    style = "<|-|>" if both else "-|>"
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=18, color=color, lw=lw, ls=ls,
                                 shrinkA=1, shrinkB=1))
    _SEGS.append((p, q))


def route(ax, pts, color=INK, lw=2.2):
    """An arrow that turns corners: straight lines through pts, the head on the last one."""
    xs, ys = [p[0] for p in pts[:-1]], [p[1] for p in pts[:-1]]
    ax.plot(xs, ys, color=color, lw=lw, solid_capstyle="round", solid_joinstyle="round")
    for a, b in zip(pts[:-2], pts[1:-1]):
        _SEGS.append((a, b))
    arrow(ax, pts[-2], pts[-1], color=color, lw=lw)


def diamond(ax, cx, cy, r, label=None, size=FS_C):
    ax.add_patch(Polygon([(cx - r, cy), (cx, cy + r), (cx + r, cy), (cx, cy - r)], closed=True, fc=RED_BG, ec=RED,
                         lw=2.2, joinstyle="round"))
    if label:
        txt(ax, cx, cy, label, size, "bold", RED, ha="center", va="center")


def chip(ax, x, y, w, h, kind, s, size=FS_C, on=None, weight="normal", color=INK):
    fc, ec, ls = KIND[kind]
    box(ax, x, y, w, h, fc, ec, lw=1.7, ls=ls, r=0.06)
    txt(ax, x + 0.12, y + h / 2, s, size, weight, color, va="center", inside=(x, y, w, h))


def card(ax, x, y, w, h, kind, title, body="", chips=(), ts=FS_H, bs=FS_B, lw=2.0):
    """A status-coloured box: bold title, body text under it, status chips stacked up from the bottom."""
    fc, ec, ls = KIND[kind]
    box(ax, x, y, w, h, fc, ec, lw=lw, ls=ls)
    pad = 0.17
    ty = y + h - pad
    txt(ax, x + pad, ty, title, ts, "bold", inside=(x, y, w, h))
    ty -= th(title, ts) + 0.05
    if body:
        txt(ax, x + pad, ty, body, bs, color=BODY, inside=(x, y, w, h))
        ty -= th(body, bs)
    cy = y + 0.14
    for ckind, ctext in reversed(list(chips)):
        ch = th(ctext, FS_C) + 0.17
        chip(ax, x + 0.14, cy, w - 0.28, ch, ckind, ctext, on=kind)
        cy += ch + 0.09
    if chips and cy - 0.09 > ty + 0.02:
        raise AssertionError(f"card {title!r}: chips run into the body text ({cy - 0.09:.2f} > {ty:.2f})")


def header(ax, height, title, sub):
    txt(ax, 0.35, height - 0.3, title, FS_TITLE, "bold")
    txt(ax, 0.35, height - 0.82, sub, FS_SUB, color=MUTED)


def legend(ax, y, kinds=("exists", "build", "open", "outside", "gate"), relabel=None):
    """Colour code, one row; y = bottom of the row."""
    labels = {"exists": "exists today\nin svg_training",
              "build": "to build\nin this track",
              "open": "PROPOSED or OPEN:\nneeds the owner's ruling",
              "outside": "outside svg_training:\nan AirStack session",
              "gate": "human gate:\nthe owner decides"}
    labels.update(relabel or {})
    ax.plot([0.35, W - 0.35], [y + 0.78, y + 0.78], color="#d5dae0", lw=1.2)
    txt(ax, 0.35, y + 0.32, "Colour code", FS_C, "bold", MUTED, va="center")
    x = 1.75
    width = {"exists": 2.5, "build": 2.4, "open": 3.5, "outside": 3.2, "gate": 2.5, "plain": 2.5}
    scale = min(1.6, (W - 0.2 - x) / sum(width[k] for k in kinds))
    for k in kinds:
        fc, ec, ls = KIND[k]
        if k == "gate":
            diamond(ax, x + 0.28, y + 0.32, 0.22)
        else:
            box(ax, x, y + 0.13, 0.56, 0.38, fc, ec, lw=1.8, ls=ls, r=0.06)
        txt(ax, x + 0.7, y + 0.32, labels[k], FS_C, color=INK, va="center")
        x += width[k] * scale


# -------------------------------------------------------------------------------------------------------- checks
def _hits(seg, r):
    (x0, y0), (x1, y1) = seg
    for i in range(201):
        t = i / 200
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        if r[0] < x < r[2] and r[1] < y < r[3]:
            return True
    return False


def check(fig, ax, height, name):
    """Every label inside its box and inside the figure; no two labels overlap; no arrow through a label."""
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    inv = ax.transData.inverted()
    rects, bad = [], []
    for t, inside in _TEXTS:
        bb = t.get_window_extent(rend)
        (x0, y0), (x1, y1) = inv.transform((bb.x0, bb.y0)), inv.transform((bb.x1, bb.y1))
        label = t.get_text().replace("\n", " / ")
        rects.append((x0, y0, x1, y1, label))
        if x0 < 0.1 or x1 > W - 0.1 or y0 < 0.05 or y1 > height - 0.05:
            bad.append(f"outside the figure: {label!r}")
        if inside is not None:
            bx, by, bw, bh = inside
            m = 0.07
            if x0 < bx + m or x1 > bx + bw - m or y0 < by + m * 0.6 or y1 > by + bh - m * 0.6:
                bad.append(f"outside its box by {max(bx + m - x0, x1 - bx - bw + m, by - y0, y1 - by - bh):.2f} in: "
                           f"{label!r}")
    s = 0.03
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            if a[0] + s < b[2] - s and b[0] + s < a[2] - s and a[1] + s < b[3] - s and b[1] + s < a[3] - s:
                bad.append(f"labels overlap: {a[4]!r} and {b[4]!r}")
    for seg in _SEGS:
        for r in rects:
            if _hits(seg, (r[0] - 0.02, r[1] - 0.02, r[2] + 0.02, r[3] + 0.02)):
                bad.append(f"arrow {seg} crosses label {r[4]!r}")
    if bad:
        raise AssertionError(f"{name}: " + "; ".join(bad))


def save(fig, ax, height, name) -> Path:
    check(fig, ax, height, name)
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{name}.png"
    fig.savefig(p, facecolor="white")
    plt.close(fig)
    return p


# ----------------------------------------------------------------------------------------------------- figure 1
def architecture() -> Path:
    """What is being built: the training loop inside svg_training, then the path to the drones.

    Build status follows ARCHITECTURE.md section 2 (exists, extend, new); a pending ruling (DISCUSSION section 3,
    PLAN section 5) is always drawn amber and dashed. Numbers: 1.10 m filter distance, 1.6 m PROPOSED tag radius,
    one decision every 0.6 s, real flights 1v1 with two drones (PLAN sections 2 and 3, DISCUSSION 2.9 and 2.10).
    """
    H = 16.1
    fig, ax = new_fig(H)
    header(ax, H, "What is being built: the training loop and the path to the drones",
           "Intended design of the STE learning track. Nothing in this track has been built or run yet; "
           "green marks parts that already exist in svg_training.")
    cx, cw = [0.55, 4.4, 8.25, 12.1], 3.3
    mid = [x + cw / 2 for x in cx]

    # panel: inside svg_training
    r1t, r1h = H - 2.55, 2.1
    r2t, r2h = r1t - r1h - 0.6, 2.85
    r3t, r3h = r2t - r2h - 0.7, 2.05
    r1b, r2b, r3b = r1t - r1h, r2t - r2h, r3t - r3h
    p_top, p_bot = H - 1.4, r3b - 0.25
    box(ax, 0.25, p_bot, W - 0.5, p_top - p_bot, PANEL_BG, MUTED, lw=1.2, r=0.1)
    txt(ax, 0.5, p_top - 0.2, "Inside svg_training: the training simulator, thousands of games at once on one GPU",
        FS_H, "bold")
    txt(ax, 0.5, p_top - 0.58, "One pass along the arrows is one decision, every 0.6 s of game time. "
        "A game repeats it until it ends, then the game resets.", FS_B, color=BODY)

    # row 1: sees -> policy -> command chain -> drone
    card(ax, cx[0], r1b, cw, r1h, "exists", "What each drone sees",
         "its own view: team-mates,\nopponents, the zone\n(the observation)",
         [("open", "version 0.3 layout: PROPOSED")])
    card(ax, cx[1], r1b, cw, r1h, "build", "One shared policy\nper team",
         "a Guard net and a Strike net:\none brain copied onto\nevery drone of the team")
    card(ax, cx[2], r1b, cw, r1h, "exists", "Command chain",
         "copy of CMU's commander,\nthen the safety filter:\ndrones stay 1.10 m apart",
         [("open", "filter option B: PROPOSED")])
    for i in range(3):
        arrow(ax, (cx[i] + cw, r1t - r1h / 2), (cx[i + 1], r1t - r1h / 2))

    # column 4, rows 1-2: the drone model in two versions
    dx, dy, dh = cx[3], r2b, r1t - r2b
    box(ax, dx, dy, cw, dh, "white", MUTED, lw=1.4)
    txt(ax, dx + 0.17, dy + dh - 0.15, "Drone model: two versions", FS_B, "bold", MUTED, inside=(dx, dy, cw, dh))
    t2h = 3.15
    t2y = dy + dh - 0.55 - t2h
    card(ax, dx + 0.13, t2y, cw - 0.26, t2h, "exists", "Starling physics drone", "in Isaac Lab (tier 2)",
         [("build", "estimator effect:\ndelay + noise"), ("exists", "PX4 control loops"),
          ("exists", "rotors"), ("build", "drag")], ts=13.5)
    card(ax, dx + 0.13, dy + 0.13, cw - 0.26, t2y - dy - 0.3, "exists", "Fast engine (tier 1)",
         "the quick-experiment\ntwin: same game, same\ncommand chain", ts=13.5)

    # row 2 (right to left): game rules -> reward; game reset feeds the first view
    card(ax, cx[2], r2b, cw, r2h, "exists", "Game rules", "who is out, who wins",
         [("open", "proximity tag at 1.6 m,\n1-for-1: PROPOSED"), ("build", "landing after a tag"),
          ("exists", "zone test: did a Strike\ndrone reach the zone?")])
    arrow(ax, (dx, r2t - r2h / 2), (cx[2] + cw, r2t - r2h / 2))
    rx, rw, rh = cx[1] + 1.45, cw - 1.45, 1.55
    ry = r2t - r2h / 2 - rh / 2
    card(ax, rx, ry, rw, rh, "build", "Reward", "the team wins\nor loses")
    arrow(ax, (cx[2], r2t - r2h / 2), (rx + rw, r2t - r2h / 2))
    card(ax, cx[0], r2t - 1.95, cw, 1.95, "exists", "Game reset", "a new game: team sizes\nand start positions",
         [("open", "team sizes: OPEN (gate G0)")])
    arrow(ax, (mid[0], r2t), (mid[0], r1b))

    # row 3: league <-> learner -> evaluation -> export
    card(ax, cx[0], r3b, cw, r3h, "build", "League",
         "the pool of opponents:\npast versions of the other\nteam, plus scripted players")
    card(ax, cx[1], r3b, cw, r3h, "build", "Learner (PPO)", "improves both nets from\nthe games just played",
         [("open", "where to train: cost\nre-checked at gate G0")])
    card(ax, cx[2], r3b, cw, r3h, "build", "Evaluation suite\nand gates",
         "fixed test games; pass\nmarks written before\neach run")
    card(ax, cx[3], r3b, cw, r3h, "build", "Export", "policy file\n+ interface file\n(what the policy expects)")
    arrow(ax, (cx[0] + cw, r3t - r3h / 2), (cx[1], r3t - r3h / 2), both=True)
    arrow(ax, (cx[1] + cw, r3t - r3h / 2), (cx[2], r3t - r3h / 2))
    arrow(ax, (cx[2] + cw, r3t - r3h / 2), (cx[3], r3t - r3h / 2))
    arrow(ax, (rx + rw / 2, ry), (rx + rw / 2, r3t))                      # reward -> learner
    ux = cx[1] + 0.3
    arrow(ax, (ux, r3t), (ux, r1b), color=BLUE)                           # learner -> policy
    txt(ax, ux + 0.13, r2t - r2h / 2, "improves\nboth nets", FS_C, color=BLUE, va="center")

    # boundary and human gate
    by = p_bot - 0.62
    ax.plot([0.25, mid[3] - 0.45], [by, by], color=GREY, lw=2.4, ls=(0, (5, 3)))
    ax.plot([mid[3] + 0.45, W - 0.25], [by, by], color=GREY, lw=2.4, ls=(0, (5, 3)))
    txt(ax, 0.5, by + 0.3, "Boundary of svg_training", FS_B, "bold", MUTED, va="center")
    txt(ax, mid[3] - 0.5, by + 0.3, "the owner approves the hand-over and any AirStack work", FS_C, color=RED,
        ha="right", va="center")
    diamond(ax, mid[3], by, 0.27)
    arrow(ax, (mid[3], r3b), (mid[3], by + 0.27))

    # panel: outside svg_training
    g_top = by - 0.45
    r4t, r4h = g_top - 0.75, 1.9
    r4b = r4t - r4h
    g_bot = r4b - 0.22
    box(ax, 0.25, g_bot, W - 0.5, g_top - g_bot, GREY_BG, GREY, lw=1.2, r=0.1)
    txt(ax, 0.5, g_top - 0.2, "Outside svg_training: specified here, built by an AirStack session", FS_H, "bold")
    chip(ax, 9.75, g_top - 0.62, 3.3, 0.46, "open", "the AirStack approach (D4): OPEN")
    arrow(ax, (mid[3], by - 0.27), (mid[3], r4t))
    card(ax, cx[3], r4b, cw, r4h, "outside", "Game node on the\nmission-control laptop",
         "runs the policy once per\ndrone, every 0.6 s")
    card(ax, cx[2], r4b, cw, r4h, "outside", "CMU commander\n+ flight filter",
         "the flight copy of the\ncommand chain")
    card(ax, cx[1], r4b, cw, r4h, "outside", "PX4 on each drone", "the drone's own control\nloops and estimator")
    card(ax, cx[0], r4b, cw, r4h, "outside", "Drones", "AirStack simulator first,\nthen real 1v1 (two drones)",
         [("gate", "each stage: the owner approves")])
    for i in (3, 2, 1):
        arrow(ax, (cx[i], r4t - r4h / 2), (cx[i - 1] + cw, r4t - r4h / 2))

    legend(ax, 0.12)
    return save(fig, ax, H, "architecture")


# ----------------------------------------------------------------------------------------------------- figure 2
def plan_phases() -> Path:
    """The plan: phases L0 to L9 (PLAN.md section 3), the simulator each uses and where each ends.

    L0 is final and approved (owner, 20 Nov 2026); L1 to L9 are the intended path, re-baselined at gate G0 with budgets OPEN;
    L9 (documentation) already runs alongside. The L0 cap of 19 GPU-h is PLAN section 9.
    """
    rows = [  # id, name, content, simulator, ends at, kind, owner gate?
        ("L1", "Drone model", "estimator effect (delay + noise), drag, fit to flight logs",
         "Isaac Lab (tier 2);\nAirStack simulator logs", "the lead decides\n(exploratory)", "build", False),
        ("L2", "Game rules in the training copy", "rules chosen at G0, landing, drone loss, filter option B",
         "tier 1, then tier 2", "the owner rules on\nfilter option B (P2)", "build", True),
        ("L3", "Learner", "observation v0.3, shared policy, team critic, PPO",
         "tier 1 pilot,\ntier 2 smoke test", "the owner approves\nobservation v0.3", "build", True),
        ("L4", "Evaluation suite and gates", "test suite, gates file, calibration on known players",
         "tier 1 and tier 2", "the owner approves\nthe gate limits", "build", True),
        ("L5", "League self-play", "pilots, then runs of record (3 seeds)",
         "as ruled at G0", "the owner rules the\nbudget; gates frozen", "build", True),
        ("L6", "QC and export", "scoring, cross-checks, policy file",
         "tier 1 and tier 2", "the owner approves\nthe hand-over", "build", True),
        ("L7", "AirStack side", "specs written here; built and played by an AirStack session",
         "AirStack simulator\n(real PX4 + EKF2)", "the owner approves\nAirStack work (D4)", "outside", True),
        ("L8", "Real flight", "a real 1v1 game", "real Starlings\n(two drones)", "the owner approves\nthe flight",
         "outside", True),
    ]
    rh, gap = 1.06, 0.24
    fb, fh = 13.5, 15.5  # this figure has room for larger type than the others
    H = 20.0
    fig, ax = new_fig(H)
    header(ax, H, "The plan: phases L0 to L9, their simulators and their gates",
           "Phase L0 is approved (owner, 20 November 2026) and is the phase in work. L1 to L9 are the intended "
           "path; L9 (documentation) already runs. Task status: the status files.")
    px, pw, sx, sw, gx = 0.6, 8.2, 9.05, 3.2, 12.5
    spine = px + 0.55

    y = H - 1.5
    for x, s in ((px, "Phase and what it holds"), (sx, "Simulator"), (gx, "Ends at")):
        txt(ax, x + 0.05, y, s, fb, "bold", MUTED)
    y -= 0.42

    def sim_cell(yb, h, s):
        box(ax, sx, yb, sw, h, "white", "#c5cbd3", lw=1.3)
        txt(ax, sx + 0.17, yb + h / 2, s, fb, color=BODY, va="center", inside=(sx, yb, sw, h))

    def gate_cell(yb, h, s, owner):
        if owner:
            diamond(ax, gx + 0.3, yb + h / 2, 0.24)
        else:
            ax.add_patch(plt.Circle((gx + 0.3, yb + h / 2), 0.13, fc=GREY_BG, ec=GREY, lw=1.8))
        txt(ax, gx + 0.72, yb + h / 2, s, fb, color=INK if owner else BODY, va="center")

    def phase_cell(yb, h, kind, pid, name, content, badge=None, badge_kind="open"):
        fc, ec, ls = KIND[kind]
        box(ax, px, yb, pw, h, fc, ec, lw=2.0, ls=ls)
        box(ax, px + 0.15, yb + h - 0.56, 0.78, 0.42, ec, ec, r=0.08, lw=1.0)
        txt(ax, px + 0.54, yb + h - 0.35, pid, fh, "bold", "white", ha="center", va="center")
        txt(ax, px + 1.1, yb + h - 0.35, name, fh, "bold", va="center", inside=(px, yb, pw, h))
        txt(ax, px + 1.1, yb + h - 0.63, content, fb, color=BODY, inside=(px, yb, pw, h))
        if badge:
            bw = 3.0
            chip(ax, px + pw - bw - 0.15, yb + h - 0.56, bw, 0.42, badge_kind, badge, weight="bold")

    # approved (owner, 20 Nov 2026)
    h0 = 0.72
    y -= h0
    box(ax, px, y, pw, h0, RED_BG, RED, lw=2.0)
    txt(ax, px + 0.2, y + h0 / 2, "Approved, 20 Nov 2026: phase L0, with a cap of 19 GPU-h", fh, "bold", va="center",
        inside=(px, y, pw, h0))
    gate_cell(y, h0, "the owner approved\nphase L0", True)
    prev = y

    # L0
    hl0 = 1.3
    y -= gap + 0.12 + hl0
    phase_cell(y, hl0, "build", "L0", "Game definition and feasibility",
               "which game the track trains; is it worth learning;\ncan Isaac Lab train, and at what cost",
               badge="APPROVED, in work", badge_kind="build")
    sim_cell(y, hl0, "STE game engine (tier 1)\nand Isaac Lab (tier 2)")
    gate_cell(y, hl0, "gate G0", True)
    arrow(ax, (spine, prev), (spine, y + hl0))
    prev = y

    # gate G0, full width
    hg = 1.5
    y -= gap + 0.12 + hg
    box(ax, px, y, W - 2 * px + 0.05, hg, RED_BG, RED, lw=2.6)
    diamond(ax, px + 0.95, y + hg / 2, 0.58, "G0", 15)
    txt(ax, px + 1.85, y + hg - 0.2, "Gate G0: the owner rules on the game and the route, with numbers", 16.5, "bold")
    txt(ax, px + 1.85, y + hg - 0.66, "the tag and the zone  ·  what a tag costs  ·  team sizes  ·  where to train\n"
        "environments  ·  what the real demo must show  ·  which fleets fly  ·  the budget for L1 to L9", fb, color=BODY)
    arrow(ax, (spine, prev), (spine, y + hg))
    prev = y

    # intended path L1-L8, inside one amber dashed frame
    f_top = y - gap - 0.08
    f_h = 0.62 + len(rows) * (rh + gap)
    fc, ec, ls = KIND["open"]
    box(ax, px - 0.25, f_top - f_h, W - 2 * px + 0.55, f_h, "#fffaf0", ec, lw=1.8, ls=ls, r=0.1)
    txt(ax, px + 1.3, f_top - 0.3, "Intended path: tasks, order and budgets are re-baselined at gate G0. "
        "Budgets for L1 to L9: OPEN.", fb, "bold", AMBER, va="center")
    y = f_top - 0.62 + gap
    for pid, name, content, sim, ends, kind, owner in rows:
        y -= gap + rh
        phase_cell(y, rh, kind, pid, name, content)
        sim_cell(y, rh, sim)
        gate_cell(y, rh, ends, owner)
        arrow(ax, (spine, prev), (spine, y + rh))
        prev = y

    # L9 alongside
    h9 = 1.05
    y = f_top - f_h - 0.3 - h9
    fc, ec, ls = KIND["exists"]
    box(ax, px, y, W - 2 * px + 0.05, h9, fc, ec, lw=2.0)
    box(ax, px + 0.15, y + h9 - 0.56, 0.78, 0.42, ec, ec, r=0.08, lw=1.0)
    txt(ax, px + 0.54, y + h9 - 0.35, "L9", fh, "bold", "white", ha="center", va="center")
    txt(ax, px + 1.1, y + h9 - 0.35, "Documentation, running alongside every phase", fh, "bold", va="center")
    txt(ax, px + 1.1, y + h9 - 0.62, "status, records, results page, STANDARDS updates after rulings", fb,
        color=BODY)
    diamond(ax, gx + 0.3, y + h9 / 2, 0.24)
    txt(ax, gx + 0.72, y + h9 / 2, "reader pages: the\nowner's approval", fb, va="center")

    legend(ax, 0.12, relabel={"exists": "running now"})
    assert y > 1.05, y
    return save(fig, ax, H, "plan_phases")


# ----------------------------------------------------------------------------------------------------- figure 3
L0_IDS = ("L0.1", "L0.7", "L0.8", "L0.9", "L0.10", "L0.11", "L0.12", "L0.2", "L0.13", "L0.3", "L0.4", "L0.5",
          "L0.14", "L0.6")                                      # PLAN.md section 4, in the table's order
PROGRESS_FILE = Path(__file__).resolve().parents[1] / "ste_learning" / "status" / "l0_progress.toml"
# state -> (fill, edge, line style, word on the box). Colour-blind-safe: the states also differ in word, mark and
# edge style, so no state depends on telling two colours apart.
STATES = {
    "done": ("#9bd3a0", GREEN, "-", "\u2713 done"),
    "laptop_done": ("#e3f4e4", GREEN, (0, (4, 2.5)), "laptop done"),
    "running": ("#ffd479", AMBER, "-", "running"),
    "queued": ("#e4e7eb", GREY, "-", "queued"),
    "not_started": ("white", GREY, (0, (2, 2)), "not started"),
}


def load_l0_progress(path: Path = PROGRESS_FILE) -> dict:
    """Read and check the progress file; a wrong task ID, state, missing task or number raises ValueError."""
    data = tomllib.loads(Path(path).read_text())
    tasks = data.get("tasks", {})
    for tid, entry in tasks.items():
        if tid not in L0_IDS:
            raise ValueError(f"{path}: unknown task ID {tid!r}; the L0 tasks are {', '.join(L0_IDS)}")
        if entry.get("state") not in STATES:
            raise ValueError(f"{path}: task {tid}: unknown state {entry.get('state')!r}; "
                             f"use one of {', '.join(STATES)}")
        if "note" in entry and not isinstance(entry["note"], str):
            raise ValueError(f"{path}: task {tid}: note must be text")
    missing = [t for t in L0_IDS if t not in tasks]
    if missing:
        raise ValueError(f"{path}: no state for {', '.join(missing)}")
    for key in ("gpu_h_used", "gpu_h_cap"):
        if not isinstance(data.get(key), (int, float)):
            raise ValueError(f"{path}: {key} must be a number")
    if not isinstance(data.get("as_of"), str):
        raise ValueError(f"{path}: as_of must be a date written as text, like \"2026-11-21\"")
    return data


def _state_key(ax, y):
    """Key of the progress figure: one swatch per state, one row; y = bottom of the row."""
    ax.plot([0.35, W - 0.35], [y + 0.78, y + 0.78], color="#d5dae0", lw=1.2)
    txt(ax, 0.35, y + 0.32, "State", FS_C, "bold", MUTED, va="center")
    x = 1.25
    for state, (fc, ec, ls, word) in STATES.items():
        box(ax, x, y + 0.13, 0.56, 0.38, fc, ec, lw=2.0, ls=ls, r=0.06)
        label = {"done": "\u2713 done", "laptop_done": "laptop done: laptop\npart done, 5090 part to do",
                 "running": "running now", "queued": "queued:\nnot started yet",
                 "not_started": "not started"}[state]
        txt(ax, x + 0.7, y + 0.32, label, FS_C, va="center")
        x += {"done": 1.9, "laptop_done": 3.3, "running": 2.2, "queued": 2.2, "not_started": 2.0}[state]


def l0_tasks() -> Path:
    """Phase L0 step by step: four lanes of tasks ending in L0.6, gate G0 (drawn by _draw_l0)."""
    return _draw_l0(None)


def l0_progress(progress_file: Path = PROGRESS_FILE, out_name: str = "l0_progress") -> Path:
    """The same flowchart, each task box coloured by its state in ste_learning/status/l0_progress.toml."""
    return _draw_l0(load_l0_progress(progress_file), out_name)


def _draw_l0(progress, out_name: str = "l0_tasks") -> Path:
    """Phase L0 step by step: four lanes of tasks ending in L0.6, gate G0.

    Task names, order and GPU-hour caps are PLAN.md section 4, word for word; the questions of gate G0 are PLAN
    section 5; the phase cap (19 GPU-h) and the work estimate (about 80 hours) are PLAN sections 4 and 9.
    """
    H = 17.95
    fig, ax = new_fig(H)
    if progress is None:
        header(ax, H, "Phase L0 step by step: four lanes of tasks, one gate",
               "Phase L0 is approved (owner, 20 November 2026); task status is in the status files. "
               "Each box: task ID, plain name, cap in GPU-hours (hours of the shared graphics card).")
    else:
        header(ax, H, f"Phase L0 progress, {progress['as_of']}: GPU-h used {progress['gpu_h_used']:g} "
               f"of {progress['gpu_h_cap']:g} cap",
               "Each box is coloured by its state (see the key below). Source: ste_learning/status/l0_progress.toml; "
               "the task list is the one in PLAN.md section 4.")
    lx, lw_ = 0.3, 12.1          # lanes
    gx, gw = 12.95, 2.75         # gate column
    top = H - 1.4

    def task(x, yb, w, h, tid, name, cap, extra=None):
        fc, ec, ls = KIND["build"]
        if progress is None:
            box(ax, x, yb, w, h, fc, ec, lw=2.0)
        else:
            sfc, sec, sls, word = STATES[progress["tasks"][tid]["state"]]
            box(ax, x, yb, w, h, sfc, sec, lw=2.4, ls=sls)
            txt(ax, x + w - 0.14, yb + h - 0.19, word, FS_C, "bold", INK, ha="right", inside=(x, yb, w, h))
            note = progress["tasks"][tid].get("note")
            if note and tid != "L0.6":
                txt(ax, x + 0.16, yb + 0.78, note, 10, color=INK, style="italic", inside=(x, yb, w, h))
        txt(ax, x + 0.16, yb + h - 0.16, tid, FS_H, "bold", BLUE, inside=(x, yb, w, h))
        txt(ax, x + 0.16, yb + h - 0.5, name, FS_B, inside=(x, yb, w, h))
        chip(ax, x + 0.14, yb + 0.13, 1.42, 0.4, "plain", cap)
        if extra:
            chip(ax, x + 1.66, yb + 0.13, w - 1.8, 0.4, extra[0], extra[1])

    def lane(y_top, h, title, question):
        box(ax, lx, y_top - h, lw_, h, PANEL_BG, MUTED, lw=1.2, r=0.1)
        txt(ax, lx + 0.25, y_top - 0.18, title, FS_H, "bold", MUTED)
        txt(ax, lx + 1.25, y_top - 0.18, question, FS_H, "bold")

    # approved (owner, 20 Nov 2026)
    h0 = 0.78
    box(ax, lx, top - h0, lw_, h0, RED_BG, RED, lw=2.0)
    diamond(ax, lx + 0.45, top - h0 / 2, 0.24)
    txt(ax, lx + 0.9, top - h0 / 2, "Approved by the owner, 20 Nov 2026. Cap for the whole phase: at most "
        "19 GPU-h.", FS_H, "bold", va="center", inside=(lx, top - h0, lw_, h0))

    # lane A: two rows of four and three
    a_top = top - h0 - 0.3
    bw, bh, bg = 2.6, 1.82, 0.42
    xs = [lx + 0.25 + i * (bw + bg) for i in range(4)]
    a_h = 0.72 + bh + 0.75 + bh + 0.25
    lane(a_top, a_h, "Lane A", "Which game, and is it worth learning?")
    y1 = a_top - 0.72 - bh
    y2 = y1 - 0.75 - bh
    row1 = [("L0.1", "Track set-up: config\nand test skeleton", "0 GPU-h"),
            ("L0.7", "Process tooling\nand drills", "0 GPU-h"),
            ("L0.8", "Game spec sheet", "0 GPU-h"),
            ("L0.9", "Tag rule for the study:\n1-for-1, nearest pair\nfirst", "0 GPU-h")]
    row2 = [("L0.10", "Scripted players\nfor the study", "0 GPU-h"),
            ("L0.11", "Screening sweep (INFO)", "cap 3 GPU-h"),
            ("L0.12", "Best-response test:\nis the game worth\nlearning?", "cap 6 GPU-h")]
    for i, (tid, name, cap) in enumerate(row1):
        task(xs[i], y1, bw, bh, tid, name, cap)
        if i:
            arrow(ax, (xs[i - 1] + bw, y1 + bh / 2), (xs[i], y1 + bh / 2))
    for i, (tid, name, cap) in enumerate(row2):
        task(xs[i + 1], y2, bw, bh, tid, name, cap)
        if i:
            arrow(ax, (xs[i] + bw, y2 + bh / 2), (xs[i + 1], y2 + bh / 2))
    ym = y1 - 0.38
    route(ax, [(xs[3] + bw / 2, y1), (xs[3] + bw / 2, ym), (xs[1] + bw / 2, ym), (xs[1] + bw / 2, y2 + bh)])
    txt(ax, xs[0], y2 + bh - 0.05, "INFO = measured,\nno pass mark.\nL0.12 sorts each\nrule variant: trivial\n"
        "for one team, or\nworth learning.", FS_C, color=BODY)

    # lane B: three probes side by side, no order between them
    b_top = a_top - a_h - 0.3
    b_h = 0.72 + 1.5 + 0.5
    lane(b_top, b_h, "Lane B", "Can Isaac Lab train, and at what cost?")
    yb = b_top - 0.72 - 1.5
    w3 = (lw_ - 0.5 - 2 * bg) / 3
    xb = [lx + 0.25 + i * (w3 + bg) for i in range(3)]
    for x, (tid, name, cap) in zip(xb, [("L0.2", "Tier 2 speed in contested play", "cap 1.5 GPU-h"),
                                       ("L0.13", "Does tier 2 train at all?", "cap 6 GPU-h"),
                                       ("L0.3", "STE Guard policy in tier 2\nwithout retraining", "cap 1.5 GPU-h")]):
        task(x, yb, w3, 1.5, tid, name, cap)
    txt(ax, lx + lw_ - 0.25, b_top - 0.2, "L0.2 runs first: L0.13 uses its result", FS_C, color=BODY, ha="right")
    yk = yb - 0.25                                                   # all three results go to the gate
    for x in xb:
        ax.plot([x + w3 / 2, x + w3 / 2], [yb, yk], color=INK, lw=2.2, solid_capstyle="round")
        _SEGS.append(((x + w3 / 2, yb), (x + w3 / 2, yk)))
    route(ax, [(xb[0] + w3 / 2, yk), (gx, yk)])

    # lane C
    c_top = b_top - b_h - 0.3
    c_h = 0.72 + 1.5 + 0.25
    lane(c_top, c_h, "Lane C", "The Starling's look in videos")
    yc = c_top - 0.72 - 1.5
    task(xb[0], yc, w3, 1.5, "L0.4", "Side-by-side Starling render", "cap 0.2 GPU-h")
    task(xb[1], yc, w3, 1.5, "L0.5", "Starling video look fix", "cap 0.3 GPU-h")
    arrow(ax, (xb[0] + w3, yc + 0.75), (xb[1], yc + 0.75))
    diamond(ax, xb[2] + 0.3, yc + 0.75, 0.24)
    arrow(ax, (xb[1] + w3, yc + 0.75), (xb[2] + 0.06, yc + 0.75))
    txt(ax, xb[2] + 0.75, yc + 1.2, "L0.5 ends when the owner\nhas looked at the stills", FS_B, va="center")
    arrow(ax, (xb[2] + 0.54, yc + 0.75), (gx, yc + 0.75))

    # lane D: the Crazyflie route check (added 20 Nov 2026 with the owner's yes)
    d_top = c_top - c_h - 0.3
    d_h = 0.72 + 1.5 + 0.25
    lane(d_top, d_h, "Lane D", "Real flight on Crazyflies: is the route sound?")
    yd = d_top - 0.72 - 1.5
    task(xb[0], yd, w3, 1.5, "L0.14", "Crazyflie route check", "0 GPU-h")
    txt(ax, xb[1] + 0.1, yd + 1.15, "Two Starlings give a 1v1 game. The lab's many Crazyflies could\n"
        "show the programme's team sizes and play after a tag.\n"
        "A check only: nothing is built in the Crazyflie repository\n"
        "and nothing flies.", FS_C, color=BODY)
    route(ax, [(xb[0] + w3, yd + 0.3), (gx, yd + 0.3)])

    # gate column
    g_bot = d_top - d_h
    box(ax, gx, g_bot, gw, top - g_bot, RED_BG, RED, lw=2.6, r=0.1)
    if progress is not None:
        sfc, sec, sls, word = STATES[progress["tasks"]["L0.6"]["state"]]
        box(ax, gx + gw - 1.62, g_bot + 0.12, 1.5, 0.36, sfc, sec, lw=2.0, ls=sls, r=0.06)
        txt(ax, gx + gw - 0.87, g_bot + 0.3, word, FS_C, "bold", ha="center", va="center",
            inside=(gx + gw - 1.62, g_bot + 0.12, 1.5, 0.36))
    diamond(ax, gx + gw / 2, top - 0.75, 0.52, "G0", 15)
    txt(ax, gx + gw / 2, top - 1.42, "L0.6 Gate G0", 15.5, "bold", ha="center")
    txt(ax, gx + gw / 2, top - 1.82, "one decision page for\nthe owner, with every\nnumber from L0", FS_B,
        color=BODY, ha="center")
    qy = top - 2.95
    txt(ax, gx + 0.2, qy, "The owner rules on:", FS_B, "bold")
    qy -= 0.36
    for q in ("the tag and the zone", "what a tag costs", "team sizes", "where to train", "environments",
              "the real demo", "which fleets fly", "the budget for L1–L9"):
        qy -= 0.5
        chip(ax, gx + 0.18, qy, gw - 0.36, 0.42, "open", q)
    txt(ax, gx + 0.2, qy - 0.45, "After G0 the lead\nre-baselines phases\nL1 to L9: tasks,\norder and budgets.",
        FS_B, color=BODY)
    arrow(ax, (xs[3] + bw, y2 + bh / 2), (gx, y2 + bh / 2))

    txt(ax, lx, g_bot - 0.25, "L0 budget: at most 19 GPU-h, alone on the GPU for the speed and training probes. "
        "Work estimate: about 80 hours.", FS_B, "bold")
    if progress is None:
        legend(ax, 0.12, kinds=("build", "open", "gate"))
    else:
        _state_key(ax, 0.12)
    return save(fig, ax, H, out_name)


# ----------------------------------------------------------------------------------------------------- figure 4
def task_lifecycle() -> Path:
    """How every task moves: the nine steps of PLAN.md section 6, who does each, and where the owner is asked.

    Human gates H1 to H9 are PLAN section 7; the 30-minute status and the limit under it are PLAN sections 8 and 10.
    """
    H = 13.3
    fig, ax = new_fig(H)
    header(ax, H, "How every task moves: nine steps, from design check to merge",
           "The white line in each box names who does the step. The lead is the main Claude session; "
           "the other names are its agents.")
    bw, bh, gx_, gy_ = 3.25, 2.55, 0.42, 0.72
    xs = [0.4 + i * (bw + gx_) for i in range(3)]
    top = H - 1.4
    ys = [top - bh - r * (bh + gy_) for r in range(3)]
    steps = [
        ("1", "Design check", "interfaces reviewed against\nthe architecture page", "ste-architect (read-only)", None),
        ("2", "Develop", "test first; new behaviour sits\nbehind a setting that is\noff by default",
         "ste-software-engineer", None),
        ("3", "Gate written", "metric, games, seeds and\ncontrols fixed and hashed\nbefore any run",
         "ste-test-qc-engineer + lead", None),
        ("4", "Test run", "pre-flight check, budget,\nlaunch with a watcher", "lead with ste-orchestrator", None),
        ("5", "Debug", "evidence first; one fix\nat a time", "lead + ste-software-engineer",
         "two aborted runs: gate H8"),
        ("6", "Validate", "controls first, then the result\nagainst the frozen gate", "ste-test-qc-engineer", None),
        ("7", "QC", "merge checklist: tests, record,\nvideos, gate unchanged", "ste-test-qc-engineer", None),
        ("8", "Document", "record, ledger row, status,\nthe right document sections", "ste-technical-writer", None),
        ("9", "Merge", "rebase, tests, fast-forward\nmerge to main", "lead", "reader pages: the owner's yes"),
    ]
    fc, ec, _ = KIND["build"]
    for k, (n, title, body, who, gate) in enumerate(steps):
        x, y = xs[k % 3], ys[k // 3]
        box(ax, x, y, bw, bh, fc, ec, lw=2.0)
        ax.add_patch(plt.Circle((x + 0.42, y + bh - 0.42), 0.26, fc=ec, ec=ec))
        txt(ax, x + 0.42, y + bh - 0.42, n, FS_H, "bold", "white", ha="center", va="center")
        txt(ax, x + 0.82, y + bh - 0.42, title, 15.5, "bold", va="center", inside=(x, y, bw, bh))
        txt(ax, x + 0.18, y + bh - 0.82, body, FS_B, color=BODY, inside=(x, y, bw, bh))
        cy = y + 0.14
        if gate:
            chip(ax, x + 0.14, cy, bw - 0.28, 0.42, "gate", gate)
            cy += 0.51
        chip(ax, x + 0.14, cy, bw - 0.28, 0.42, "plain", who, color=MUTED)
        if k % 3:
            arrow(ax, (xs[k % 3 - 1] + bw, y + bh / 2), (x, y + bh / 2))
    for r in (0, 1):  # wrap to the next row
        ym = ys[r] - gy_ / 2
        route(ax, [(xs[2] + bw / 2, ys[r]), (xs[2] + bw / 2, ym), (xs[0] + bw / 2, ym), (xs[0] + bw / 2, ys[r + 1] + bh)])

    # human gates
    hx = xs[2] + bw + 0.5
    hw = W - 0.35 - hx
    hb = ys[2]
    box(ax, hx, hb, hw, top - hb, RED_BG, RED, lw=2.4, r=0.1)
    diamond(ax, hx + 0.45, top - 0.5, 0.26)
    txt(ax, hx + 0.9, top - 0.5, "Where the automation\nstops for the owner", FS_H, "bold", va="center",
        inside=(hx, hb, hw, top - hb))
    gates = [("H1 Direction", "a result changes the route"),
             ("H2 Soundness", "the idea does not hold as framed"),
             ("H3 Rules", "a fixed rule, or an open ruling"),
             ("H4 Outside svg_training", "any AirStack work"),
             ("H5 Outward", "messages, pushes, reader pages"),
             ("H6 Budget", "a cap would be exceeded"),
             ("H7 NUS", "NUS changes direction"),
             ("H8 Stuck", "two aborted runs on one task"),
             ("H9 Safety", "anything that matters for flights")]
    gy = top - 1.2
    stepy = (gy - hb - 0.2) / len(gates)
    for name, what in gates:
        txt(ax, hx + 0.25, gy, name, FS_B, "bold", RED, inside=(hx, hb, hw, top - hb))
        txt(ax, hx + 0.25, gy - 0.28, what, FS_B, color=INK, inside=(hx, hb, hw, top - hb))
        gy -= stepy

    # heartbeat and the limit
    sb = hb - 0.4 - 1.18
    box(ax, 0.4, sb, W - 0.75, 1.18, "white", MUTED, lw=1.6)
    txt(ax, 0.62, sb + 1.02, "Status every 30 minutes, and at once when a run finishes, a gate gives its verdict, "
        "something fails or a human gate is reached.", FS_B, "bold")
    txt(ax, 0.62, sb + 0.68, "Written by ste-technical-writer. Each human gate is asked as one question, with "
        "options, costs and a recommendation; work that is not blocked keeps running.\nLimit: nothing is scored, "
        "launched or reported when no Claude session is alive. Training jobs already started keep running.",
        FS_B, color=BODY)
    legend(ax, 0.12, kinds=("build", "plain", "gate"),
           relabel={"build": "a step of every task\n(to run in this track)", "plain": "who does the step"})
    return save(fig, ax, H, "task_lifecycle")


FIGURES = {"architecture": architecture, "plan_phases": plan_phases, "l0_tasks": l0_tasks, "l0_progress": l0_progress,
           "task_lifecycle": task_lifecycle}

if __name__ == "__main__":
    names = sys.argv[1:] or list(FIGURES)
    for name in names:
        print("wrote", FIGURES[name]())
