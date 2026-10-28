#!/usr/bin/env python3
"""Step-response figure for a sim hover + step run (S5 / NEAR-786, ledger #18).

    tools/hover_step_plot.py <run_dir>          -> <run_dir>/step_response.png
    tools/hover_step_plot.py --overlay RUN [RUN...] [--time-scale RUN=X]... [--label RUN=TEXT]... -o PNG
        every x / z step of several runs on one figure, goal-relative, in PX4 vehicle time (RUN = run dir, or a bare
        name under docs/record/; a run whose JSON has no time scale needs --time-scale RUN=X and is marked "(est.)")

Reads bag_analysis.json (tools/hover_step_analysis.py) and the two CSVs tools/hover_step_bag.py dumps
(drone_1_odom.csv, drone_1_cmd.csv). One panel per event in panel_order(): the takeoff climb, every x step, every
z step, the landing. Each panel is a column of two axes that share one time axis: on top the measured position on the
COMMANDED axis against time since the command onset (goal line + ±0.1 m band when the event has a goal, the settled
value, the settle time); underneath the commander's own velocity command (a separate panel, never a second y-axis).
More than four panels wrap onto two rows. Bag times are wall seconds; the axis label carries the vehicle-time scale."""
from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

INK, MUTED, MEAS, CMD, BAND, GRID, SPINE = "#404040", "#5F6368", "#2F5D9E", "#8A8F94", "#2F5D9E", "#E6E8EA", "#D0D3D6"
WIN = 8.0            # shared time axis length (s, wall); matches WINDOW_S in hover_step_analysis
MAX_COLS = 4         # panels per row before wrapping
PANEL_W, PANEL_H = 3.4, 5.6
_STEP = re.compile(r"^step_([xz])_(\d+)$")
_STEP_ANY = re.compile(r"^step_([xz])(?:_(\d+))?$")      # also the older run1 names step_x / step_z
RECORD_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "record"
RUN_COLOURS = ["#0072B2", "#E69F00", "#009E73"]          # Okabe-Ito blue / orange / bluish green: colour-blind safe, fixed run order
GATE_S = 3.0
LABEL_GAP_PT = 10.0   # minimum vertical gap between direct labels on one axis


def panel_order(events: list[dict]) -> list[tuple[str, str]]:
    """(name, title) per panel: takeoff, step_x_* (by k), step_z_* (by k), landing. Other events are not drawn."""
    names = {e["name"] for e in events}
    out = []
    if "takeoff" in names:
        out.append(("takeoff", "Takeoff climb (z)"))
    for axis in ("x", "z"):
        ks = sorted(int(m.group(2)) for n in names if (m := _STEP.match(n)) and m.group(1) == axis)
        out += [(f"step_{axis}_{k}", f"{axis} step {k}") for k in ks]
    if "landing" in names:
        out.append(("landing", "Landing descent (z)"))
    return out


def _load_xyz(path):
    with open(path, newline="") as fh:
        return [tuple(map(float, r)) for r in csv.reader(fh) if r and r[0] and r[0][0] in "0123456789-+."]


def _style(ax):
    ax.set_facecolor("white"); ax.grid(True, color=GRID, linewidth=0.8); ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(SPINE)
    ax.tick_params(colors=MUTED, labelsize=8)


def _draw_panel(top, bot, ev, title, odom, cmd, time_scale):
    k = "xyz".index(ev["axis"])
    t0, win = ev["onset_s_from_bag_start"], min(float(ev.get("window_s") or WIN), WIN)
    seg = [(t - t0, p[k]) for t, *p in odom if t0 <= t <= t0 + win]
    cseg = [(t - t0, v[k]) for t, *v in cmd if t0 <= t <= t0 + win]
    final, tail, goal = ev["final_m"], ev["tail"], ev.get("goal")
    ref = goal["goal_m"] if goal else final
    up = (ev.get("commanded_delta_m") or ev.get("moved_m") or 0.0) >= 0

    top.axhspan(ref - 0.1, ref + 0.1, color=BAND, alpha=0.08, lw=0)
    top.axhline(final, color=MUTED, lw=0.8, ls="-", alpha=0.7)
    if goal:
        top.axhline(goal["goal_m"], color=INK, lw=0.9, ls=":")
        top.text(win - 0.1, goal["goal_m"], f"goal {goal['goal_m']:.3f} m", fontsize=7.5, color=INK, ha="right",
                 va="bottom" if up else "top", clip_on=True, in_layout=False)
    top.plot([t for t, _ in seg], [v for _, v in seg], color=MEAS, lw=1.8, solid_capstyle="round")
    settle = tail.get("settle_s")
    if settle is not None:
        top.axvline(settle, color=INK, lw=0.8, ls="--")
        top.text(settle + 0.1, 0.04 if up else 0.96, f"settled {settle:.2f} s wall\n{settle * time_scale:.2f} s vehicle",
                 fontsize=7.5, color=INK, va="bottom" if up else "top", transform=top.get_xaxis_transform(), in_layout=False)
        settle_txt = f"settle {settle:.2f} s = {settle * time_scale:.2f} s veh"
    else:
        settle_txt = "not settled"
    reent = goal["reentries_0p1"] if goal else tail["band_reentries"]
    if ev.get("axis_mismatch"):
        line3 = f"re-entries {reent} · moved most on {ev['moved_most_axis']} (mismatch)"
    elif goal:
        line3 = f"re-entries {reent} · ss error {goal['steady_state_error_m']:+.3f} m"
    else:
        line3 = f"re-entries {reent} · moved {ev['moved_m']:+.2f} m"
    delta = ev.get("commanded_delta_m")
    head = f"{title} ({delta:+.1f} m cmd)" if delta is not None and _STEP.match(ev["name"]) else title
    top.set_title(f"{head}\novershoot {tail['overshoot_m']:+.3f} m · {settle_txt}\n{line3}",
                  fontsize=8, color=INK, loc="left")
    top.set_ylabel(f"{ev['axis']} position (m)", fontsize=8.5, color=MUTED)

    bot.plot([t for t, _ in cseg], [v for _, v in cseg], color=CMD, lw=1.6)
    ramp = ev.get("commander_ramp_s")
    if ramp is not None:
        bot.axvline(ramp, color=INK, lw=0.8, ls="--")
        bot.text(ramp + 0.1, 0.06, f"ramp {ramp:.2f} s", fontsize=7.5, color=INK, va="bottom",
                 transform=bot.get_xaxis_transform(), in_layout=False)
    bot.set_ylabel(f"commanded v{ev['axis']} (m/s)", fontsize=8.5, color=MUTED)
    bot.set_xlabel("time since onset (wall s)", fontsize=7.5, color=MUTED)
    bot.set_xlim(0, WIN)


def render(run_dir: pathlib.Path, out: pathlib.Path | None = None) -> pathlib.Path:
    with open(run_dir / "bag_analysis.json") as fh:
        j = json.load(fh)
    odom, cmd = _load_xyz(run_dir / "drone_1_odom.csv"), _load_xyz(run_dir / "drone_1_cmd.csv")
    events = {e["name"]: e for e in j["events"]}
    order = panel_order(j["events"])
    time_scale = float(j.get("time_scale") or 1.0)
    xlabel = f"time since onset (wall s; vehicle time = wall × {time_scale:.3f})"

    n = max(len(order), 1)
    cols = n if n <= MAX_COLS else math.ceil(n / 2)
    prow = math.ceil(n / cols)
    fig_w, fig_h = PANEL_W * cols, PANEL_H * prow + 1.2
    fig, axes = plt.subplots(2 * prow, cols, figsize=(fig_w, fig_h), dpi=170, squeeze=False, layout="constrained",
                             gridspec_kw={"height_ratios": [2.2, 1] * prow})
    fig.get_layout_engine().set(w_pad=0.08, h_pad=0.08, hspace=0.04, wspace=0.02, rect=(0, 0.5 / fig_h, 1, 1 - (0.5 + 0.55) / fig_h))  # (l, b, w, h)
    fig.patch.set_facecolor("white")
    for ax in axes.flat:
        _style(ax)
    if not order:
        axes[0, 0].text(0.5, 0.5, "no takeoff / step / landing events in bag_analysis.json", transform=axes[0, 0].transAxes,
                        ha="center", va="center", fontsize=10, color=INK)
    for i, (name, title) in enumerate(order):
        r, c = divmod(i, cols)
        _draw_panel(axes[2 * r, c], axes[2 * r + 1, c], events[name], title, odom, cmd, time_scale)
    for i in range(len(order), prow * cols):          # unused slots on the wrapped row
        r, c = divmod(i, cols)
        axes[2 * r, c].set_axis_off(); axes[2 * r + 1, c].set_axis_off()

    steps = j.get("steps", {})
    nsteps = " · ".join(f"{a}: {s['n']} step(s)" for a, s in steps.items()) or "no steps"
    fig.text(0.01, 1 - 0.1 / fig_h, f"{run_dir.name}: {j.get('drone', 'drone_1')} step responses from the commander's rosbag "
                 f"(odometry {j.get('odom_rate_hz')} Hz; {nsteps}; vehicle time = wall × {time_scale:.3f}, {j.get('time_scale_source')})\n"
                 "blue: measured position on the commanded axis · dotted: goal · shaded: ±0.1 m band (about the goal, else the settled value) · "
                 "grey: the commander's velocity command",
                 fontsize=9, color=INK, ha="left", va="top")
    fig.text(0.5, 0.26 / fig_h, xlabel, fontsize=8.5, color=INK, ha="center", va="center")
    fig.text(0.01, 0.004, "Sim only. Onset = first commanded |v| ≥ 0.10 m/s after 0.8 s quiet; settle = first sample inside ±0.1 m after the last "
             "excursion, from onset; re-entries = extra entries into the band (0 = no ringing); overshoot is past the settled value.",
             fontsize=7.5, color=MUTED)
    out = out or run_dir / "step_response.png"
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


def step_events(events: list[dict]) -> list[tuple[str, dict]]:
    """(axis, event) for every step event, x steps then z steps, each by step index (a bare step_x counts as index 0)."""
    found = []
    for e in events:
        m = _STEP_ANY.match(e.get("name", ""))
        if m:
            found.append((m.group(1), int(m.group(2) or 0), e))
    found.sort(key=lambda f: ("xz".index(f[0]), f[1]))
    return [(a, e) for a, _, e in found]


def run_time_scale(j: dict, override: float | None, run: str = "run") -> tuple[float, bool]:
    """(scale, estimated). An override wins and is marked estimated; a JSON scale whose source is 'assumed ...' is refused."""
    if override is not None:
        return float(override), True
    ts, src = j.get("time_scale"), str(j.get("time_scale_source") or "")
    if ts and not src.startswith("assumed"):
        return float(ts), False
    raise ValueError(f"{run}: no time scale (pass --time-scale {run}=<x>)")


def relative_trace(odom, ev: dict, time_scale: float, window_s: float = WIN) -> tuple[list[float], list[float]]:
    """(t_vehicle, y): position on the step's axis relative to its start, signed so the step reads as a +1 m command."""
    k = "xyz".index(ev["axis"]) + 1                      # odom rows are (t, x, y, z)
    t0 = ev["onset_s_from_bag_start"]
    window_s = min(window_s, float(ev.get("window_s") or window_s))      # the analysis stops a step where the next command starts
    seg = [r for r in odom if t0 <= r[0] <= t0 + window_s]
    if not seg:
        return [], []
    p0 = ev["start_m"] if ev.get("start_m") is not None else seg[0][k]
    sign = 1.0 if (ev.get("commanded_delta_m") or ev.get("moved_m") or 1.0) >= 0 else -1.0
    return [(r[0] - t0) * time_scale for r in seg], [(r[k] - p0) * sign for r in seg]


def spread_labels(pos: list[float], gap: float) -> list[float]:
    """Move 1-D label positions (any unit) apart to at least `gap`, keeping their order; returns positions in input order.
    Sorted ascending, each is pushed up to clear the one below, then the block is re-centred on its original mean."""
    order = sorted(range(len(pos)), key=lambda i: pos[i])
    new = []
    for i in order:
        new.append(pos[i] if not new else max(pos[i], new[-1] + gap))
    if new:
        shift = (sum(pos[i] for i in order) - sum(new)) / len(new)
        new = [v + shift for v in new]
        for a in range(1, len(new)):                     # re-centring can only widen gaps to the original side; re-check
            new[a] = max(new[a], new[a - 1] + gap)
    out = [0.0] * len(pos)
    for v, i in zip(new, order):
        out[i] = v
    return out


def overlay(runs, scales: dict[str, float], labels: dict[str, str], out: pathlib.Path,
            estimated: frozenset | set = frozenset()) -> pathlib.Path:
    """One figure, x steps left and z steps right, one hue per run (in the given order). runs = [(name, run_dir)]."""
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.6), dpi=170, sharey=True, layout="constrained")
    fig.patch.set_facecolor("white")
    for ax in axes:
        _style(ax)
        ax.axhspan(0.9, 1.1, color=MUTED, alpha=0.12, lw=0)
        ax.axhline(1.0, color=INK, lw=0.9, ls=":")
        ax.axvline(GATE_S, color=INK, lw=0.8, ls="--")
        ax.text(GATE_S + 0.1, 0.3, "3 s gate", fontsize=8, color=INK, va="bottom", transform=ax.get_xaxis_transform())
        ax.text(0.2, 1.0, "goal 1.0 m", fontsize=8, color=INK, va="bottom")
        ax.set_xlabel("time since step onset (PX4 vehicle s)", fontsize=9, color=MUTED)
    axes[0].set_title("x steps", fontsize=10, color=INK, loc="left")
    axes[1].set_title("z steps", fontsize=10, color=INK, loc="left")
    axes[0].set_ylabel("position along the commanded axis, relative to onset (m)", fontsize=9, color=MUTED)
    handles, ends = [], {}
    for i, (name, run_dir) in enumerate(runs):
        colour = RUN_COLOURS[i % len(RUN_COLOURS)]
        j = json.loads((pathlib.Path(run_dir) / "bag_analysis.json").read_text())
        odom = _load_xyz(pathlib.Path(run_dir) / "drone_1_odom.csv")
        evs = step_events(j["events"])
        last = {}
        label = labels.get(name, name)
        for axis, ev in evs:
            t, y = relative_trace(odom, ev, scales[name])
            if t:
                axes["xz".index(axis)].plot(t, y, color=colour, lw=1.3, alpha=0.8)
                last[axis] = (t[-1], y[-1], label, colour)
        for axis, item in last.items():                  # one direct label per run per axis (its last step's last sample)
            ends.setdefault(axis, []).append(item)
        est = " (est.)" if name in estimated else ""
        text = f"{label} · {name} · n={"+".join(str(sum(1 for ax, _ in evs if ax == k)) for k in "xz")} (x+z) · scale {scales[name]:.3f}{est}"
        handles.append(plt.Line2D([], [], color=colour, lw=2, label=text))
    fig.canvas.draw()                                    # axes size is final: place the direct labels, then spread them apart
    for axis, items in ends.items():                     # one label per run at its last sample, >= LABEL_GAP_PT apart
        ax = axes["xz".index(axis)]
        y0, y1 = ax.get_ylim()
        h_pt = ax.get_window_extent().height * 72.0 / fig.dpi
        ypt = [(y - y0) / (y1 - y0) * h_pt for _, y, _, _ in items]
        for (tx, y, label, colour), yp, yn in zip(items, ypt, spread_labels(ypt, LABEL_GAP_PT)):
            ax.annotate(label, (tx, y), xytext=(4, yn - yp), textcoords="offset points",
                        fontsize=8, color=colour, va="center", annotation_clip=False)
    axes[0].legend(handles=handles, loc="lower right", fontsize=8, frameon=False, labelcolor=INK)
    fig.text(0.01, 0.004, "Sim only. tools/hover_step_plot.py --overlay … ; onset/settle definitions in tools/hover_step_analysis.py",
             fontsize=7.5, color=MUTED)
    fig.get_layout_engine().set(rect=(0, 0.03, 1, 0.97))
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


def _kv(items, what, parser) -> dict[str, str]:
    d = {}
    for it in items or []:
        key, sep, val = it.partition("=")
        if not sep or not key:
            parser.error(f"{what} expects RUN=VALUE, got {it!r}")
        d[key] = val
    return d


def _main_overlay(argv) -> int:
    ap = argparse.ArgumentParser(prog="hover_step_plot.py --overlay", description="Overlay the step responses of several runs.")
    ap.add_argument("runs", nargs="+", help="run directory, or a bare name under docs/record/")
    ap.add_argument("--time-scale", action="append", metavar="RUN=X", help="vehicle/wall time scale for a run (marked est.)")
    ap.add_argument("--label", action="append", metavar="RUN=TEXT", help="legend label for a run")
    ap.add_argument("-o", "--out", required=True, type=pathlib.Path)
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0) if e.code in (0, None) else 2
    ts, labels = _kv(a.time_scale, "--time-scale", ap), _kv(a.label, "--label", ap)
    runs, scales, est = [], {}, set()
    try:
        for r in a.runs:
            p = pathlib.Path(r)
            if not p.exists() and p.name == r:
                p = RECORD_DIR / r
            p = p.resolve()
            j = json.loads((p / "bag_analysis.json").read_text())
            override = float(ts[p.name]) if p.name in ts else None
            scales[p.name], was_est = run_time_scale(j, override, p.name)
            if was_est:
                est.add(p.name)
            runs.append((p.name, p))
        known = {n for n, _ in runs}
        for what, d in (("--time-scale", ts), ("--label", labels)):
            bad = sorted(set(d) - known)
            if bad:
                raise ValueError(f"{what}: unknown run name(s) {', '.join(bad)} (runs given: {', '.join(sorted(known))})")
    except (ValueError, OSError) as e:
        print(e, file=sys.stderr)
        return 2
    print(overlay(runs, scales, labels, a.out, est))
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--overlay":
        return _main_overlay(argv[1:])
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        print(__doc__.splitlines()[2].strip(), file=sys.stderr)
        return 2
    print(render(pathlib.Path(argv[0]).resolve()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
