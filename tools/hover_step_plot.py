#!/usr/bin/env python3
"""Step-response figure for a sim hover + 1 m step run (S5 / NEAR-786).

    tools/hover_step_plot.py docs/record/<run>/          -> docs/record/<run>/step_response.png

Reads bag_analysis.json (events, from tools/hover_step_bag.py) and the two CSVs it dumps (drone_1_odom.csv,
drone_1_cmd.csv). One small panel per event — takeoff climb, x step, z step, landing — measured position on the
event's axis against time since the command onset, with the settled value, the ±0.1 m settle band and the settle
time; underneath, the commander's own velocity command on the same time axis (a separate panel, never a second
y-axis). Four panels share one time scale so the responses can be compared by eye."""
import csv, json, pathlib, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = pathlib.Path(sys.argv[1]).resolve()
j = json.load(open(OUT / "bag_analysis.json"))
odom = [tuple(map(float, r)) for r in csv.reader(open(OUT / "drone_1_odom.csv")) if r and r[0] != "t_s"]
cmd = [tuple(map(float, r)) for r in csv.reader(open(OUT / "drone_1_cmd.csv")) if r and r[0] != "t_s"]
order = [("takeoff", "Takeoff climb (z)"), ("step_x", "x step +1 m"), ("step_z", "z step +1 m"), ("landing", "Landing descent (z)")]
events = {e["name"]: e for e in j["events"]}
INK, MUTED, MEAS, CMD, BAND = "#404040", "#5F6368", "#2F5D9E", "#8A8F94", "#2F5D9E"
WIN = 8.0

fig, axes = plt.subplots(2, 4, figsize=(13.5, 5.6), dpi=170, sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
fig.patch.set_facecolor("white")
for col, (name, title) in enumerate(order):
    ev = events.get(name); top, bot = axes[0, col], axes[1, col]
    for ax in (top, bot):
        ax.set_facecolor("white"); ax.grid(True, color="#E6E8EA", linewidth=0.8); ax.set_axisbelow(True)
        for sp in ("top", "right"): ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"): ax.spines[sp].set_color("#D0D3D6")
        ax.tick_params(colors=MUTED, labelsize=8)
    if not ev:
        top.set_title(title + " — not found", fontsize=10, color=INK); continue
    k = "xyz".index(ev["axis"]); t0 = ev["onset_s_from_bag_start"]
    seg = [(t - t0, p[k]) for t, *p in odom if t0 <= t <= t0 + WIN]
    cseg = [(t - t0, v[k]) for t, *v in cmd if t0 <= t <= t0 + WIN]
    final = ev["final_m"]
    top.axhspan(final - 0.1, final + 0.1, color=BAND, alpha=0.08, lw=0)
    top.axhline(final, color=MUTED, lw=0.8, ls=":")
    top.plot([t for t, _ in seg], [v for _, v in seg], color=MEAS, lw=1.8, solid_capstyle="round")
    top.axvline(ev["settle_s"], color=INK, lw=0.8, ls="--")
    top.text(ev["settle_s"] + 0.1, final + (0.12 if ev["moved_m"] >= 0 else -0.12) * (1 if ev["moved_m"] >= 0 else 1),
             f"settled {ev['settle_s']:.2f} s", fontsize=8, color=INK, va="bottom" if ev["moved_m"] >= 0 else "top")
    top.set_title(f"{title}\novershoot {ev['overshoot_m']:+.3f} m · settle {ev['settle_s']:.2f} s\nband re-entries {ev['band_reentries']}",
                  fontsize=9, color=INK, loc="left")
    top.set_ylabel(f"{ev['axis']} position (m)", fontsize=8.5, color=MUTED)
    bot.plot([t for t, _ in cseg], [v for _, v in cseg], color=CMD, lw=1.6)
    bot.axvline(ev["commander_ramp_s"], color=INK, lw=0.8, ls="--")
    bot.text(ev["commander_ramp_s"] + 0.1, 0.0, f"ramp {ev['commander_ramp_s']:.2f} s", fontsize=8, color=INK, va="bottom")
    bot.set_ylabel(f"commanded v{ev['axis']} (m/s)", fontsize=8.5, color=MUTED)
    bot.set_xlabel("time since command onset (s)", fontsize=8.5, color=MUTED)
    bot.set_xlim(0, WIN)
fig.suptitle(f"{OUT.name}: drone_1 step responses from the commander's rosbag (odometry {j['odom_rate_hz']} Hz)\n"
             "blue: measured position · shaded: ±0.1 m settle band · grey: the commander's velocity command", fontsize=10, color=INK, x=0.01, ha="left")
fig.text(0.01, 0.005, "Sim only, 2026-10-28, cbf_sim.yaml scenario:=goal (2.0 m/s / 6.0 m/s²). Settle = last sample outside ±0.1 m of the settled value, "
         "measured from the commander's first non-zero velocity command.", fontsize=7.5, color=MUTED)
fig.tight_layout(rect=(0, 0.03, 1, 0.92))
out = OUT / "step_response.png"
fig.savefig(out, facecolor="white"); print(out)
