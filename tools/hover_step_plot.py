#!/usr/bin/env python3
"""Step-response figure for a sim hover + step run (S5 / NEAR-786, ledger #18).

    tools/hover_step_plot.py <run_dir>          -> <run_dir>/step_response.png

Reads bag_analysis.json (tools/hover_step_analysis.py) and the two CSVs tools/hover_step_bag.py dumps
(drone_1_odom.csv, drone_1_cmd.csv). One panel per event in panel_order(): the takeoff climb, every x step, every
z step, the landing. Each panel is a column of two axes that share one time axis: on top the measured position on the
COMMANDED axis against time since the command onset (goal line + ±0.1 m band when the event has a goal, the settled
value, the settle time); underneath the commander's own velocity command (a separate panel, never a second y-axis).
More than four panels wrap onto two rows. Bag times are wall seconds; the axis label carries the vehicle-time scale."""
from __future__ import annotations

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
    j = json.load(open(run_dir / "bag_analysis.json"))
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


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        print(__doc__.splitlines()[2].strip(), file=sys.stderr)
        return 2
    print(render(pathlib.Path(argv[0]).resolve()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
