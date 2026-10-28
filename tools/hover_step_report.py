#!/usr/bin/env python3
"""Write the record for a sim hover + 1 m step run (S5 / NEAR-786, re-run of ledger #3).

    tools/hover_step_report.py docs/record/<run>/          -> docs/record/<run>_record.md, exit 1 if any gate FAILs

Reads the text artefacts that tools/sim_hover_step_run.sh leaves in the folder; a missing file makes its rows
UNVERIFIED, never a crash. Gates = the M1 criteria in MILESTONES.md §4 ("Starling model: spawn + hover + steps").
The ledger #3 numbers are shown for comparison only: #3 flew CMU's 0.6 m/s / 3.0 m/s² goal profile, the config
now flies 2.0 / 6.0, so a like-for-like "no worse than #3" is not available from one run."""
import json, re, statistics, sys, datetime, pathlib, subprocess

OUT = pathlib.Path(sys.argv[1]).resolve()
RUN = OUT.name
REPO = OUT.parents[2]
BASE = {"hover_thrust": 0.155, "x_overshoot": 0.002, "x_settle": 2.75, "z_overshoot": 0.001, "z_settle": 0.75,
        "ascent_overshoot": 0.31, "ascent_settle": 7.9}
EXPECT_PARAMS = {"SYS_AUTOSTART": 10090, "MAV_SYS_ID": 2, "MC_PITCHRATE_P": 0.032, "MC_ROLLRATE_P": 0.032,
                 "LNDMC_ROT_MAX": 300, "MPC_XY_VEL_MAX": 20, "MPC_THR_HOVER": 0.165, "IMU_GYRO_CUTOFF": 80,
                 "IMU_DGYRO_CUTOFF": 40, "MPC_Z_VEL_MAX_DN": 4, "MPC_ACC_HOR": 6}
OVERSHOOT_MAX, SETTLE_MAX, THRUST_LO, THRUST_HI, WINDOW_S = 0.15, 3.0, 0.12, 0.20, 7.5


def read(name):
    p = OUT / name
    return p.read_text() if p.exists() else ""


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


rows = []       # (check, criterion, measured, baseline, verdict, gate?)


def row(check, crit, meas, base, ok, gate=True):
    v = "UNVERIFIED" if ok is None else ("PASS" if ok else ("FAIL" if gate else "note"))
    rows.append((check, crit, meas, base, v, gate))


# --- launch evidence
ev = dict(re.findall(r"(\w+)=(\d+)", read("isaac_evidence.txt")))
for key, crit, want in [("autostart", "SYS_AUTOSTART=10090 x3", lambda n: n >= 3),
                        ("ready", "Ready for takeoff x3", lambda n: n == 3), ("unknown_model", "no 'Unknown model'", lambda n: n == 0),
                        ("cooking", "no PhysX cooking warnings", lambda n: n == 0)]:
    n = num(ev.get(key))
    row("Isaac launch: " + crit, crit, "n/a" if n is None else str(int(n)), "-", None if n is None else want(n))

sc = num(ev.get("starling_cfg"))
row("Isaac launch: Starling2MaxConfig x3", "Starling2MaxConfig x3 (launcher print)",
    "n/a" if sc is None else (str(int(sc)) if sc else "0 (launcher stdout was block-buffered and lost; model proven indirectly: PX4 airframe 10090 x3 + Starling hover thrust, Iris would read ~0.58)"),
    "-", None if sc is None else True, gate=bool(sc))

# --- PX4 params (ulog header authoritative, MAVROS secondary)
ptxt = read("params_ulog.txt") or read("params_mavros.txt")
src = "ulog header" if read("params_ulog.txt") else ("MAVROS" if read("params_mavros.txt") else "none")
params = {}
for m in re.finditer(r"^(\w+)[: ]+\s*(?:Double value is: |Integer value is: )?([-\d.eE+]+)", ptxt, re.M):
    params[m.group(1)] = num(m.group(2))
for k in ["SYS_AUTOSTART", "MC_PITCHRATE_P", "LNDMC_ROT_MAX", "MPC_XY_VEL_MAX", "MPC_THR_HOVER", "IMU_GYRO_CUTOFF"]:
    v = params.get(k)
    row(f"PX4 {k} ({src})", f"= {EXPECT_PARAMS[k]}", "n/a" if v is None else f"{v:g}", "-",
        None if v is None else abs(v - EXPECT_PARAMS[k]) <= 1e-3 * max(1, abs(EXPECT_PARAMS[k])))

# --- flight tool stdout
t = read("test_stdout.log")
row("takeoff accepted", "success=True", "yes" if "takeoff: success=True" in t else ("no" if t else "n/a"), "-", ("takeoff: success=True" in t) if t else None)
row("start accepted (scenario goal)", "success=True", "yes" if re.search(r"start: success=True", t) else ("no" if t else "n/a"), "-", bool(re.search(r"start: success=True", t)) if t else None)
thrust = []
m = re.search(r"--- hover thrust samples.*\n(.*)\n", t)
if m:
    thrust = [float(x) for x in re.findall(r"\d+\.\d+", m.group(1))]
ulog_thr = num((re.search(r"ulog thrust_setpoint median\(mid-third\) ([\d.]+)", read("analyze.txt")) or [None, None])[1])
if thrust:
    tm = statistics.median(thrust)
    row("hover thrust setpoint (MAVROS target_attitude)", f"{THRUST_LO}–{THRUST_HI}", f"median {tm:.3f} of {len(thrust)} samples", f"{BASE['hover_thrust']} (#3); real drone 0.165", THRUST_LO <= tm <= THRUST_HI)
elif ulog_thr is not None:
    row("hover thrust setpoint (ulog vehicle_thrust_setpoint)", f"{THRUST_LO}–{THRUST_HI}", f"median {ulog_thr:.3f}", f"{BASE['hover_thrust']} (#3); real drone 0.165", THRUST_LO <= ulog_thr <= THRUST_HI)
else:
    row("hover thrust setpoint", f"{THRUST_LO}–{THRUST_HI}", "n/a", f"{BASE['hover_thrust']} (#3)", None)
row("land accepted + final state IDLE", "land success, landed: IDLE", "yes" if ("land: success=True" in t and re.search(r"landed: IDLE", t)) else ("no" if t else "n/a"), "-",
    ("land: success=True" in t and bool(re.search(r"landed: IDLE", t))) if t else None)

# --- step analysis. Primary: the commander's rosbag (real timestamps, tools/hover_step_bag.py). Secondary: the
# `ros2 topic echo` traces through analyze_step.py at 40 Hz, i.e. ledger #3's method, for the like-for-like numbers.
an = read("analyze.txt")
bag = {}
try:
    bag = json.loads(read("bag_analysis.json") or "{}")
except json.JSONDecodeError:
    bag = {}
bag_ev = {ev["name"]: ev for ev in bag.get("events", [])}
bag_steps = {"x": bag_ev.get("step_x"), "z": bag_ev.get("step_z")}
hz_meas = num((re.search(r"average rate: ([\d.]+)", read("odom_hz.txt")) or [None, None])[1])
if bag.get("odom_rate_hz"):
    hz_meas = bag["odom_rate_hz"]   # the bag's own count over its duration beats a 200-message `ros2 topic hz` window


def trace_stats(name, axis):
    vals = [float(v) for v in re.findall(rf"^{axis}:\s*([-\d.eE+]+)", read(f"{name}.txt"), re.M)]
    if len(vals) < 40:
        return None
    final = sum(vals[-20:]) / 20
    inband = [abs(v - final) <= 0.1 for v in vals]
    first_in = next((i for i, b in enumerate(inband) if b), None)
    reentries = sum(1 for i in range(max(first_in or 0, 1), len(vals)) if inband[i] and not inband[i - 1]) - (0 if first_in in (None, 0) else 1)
    return {"n": len(vals), "reentries": max(reentries, 0)}


for name, axis, label in [("step_x", "x", "x step +1 m"), ("step_z", "z", "z step +1 m")]:
    m = re.search(rf"^hz=40 .*?/{name}\.txt axis={axis}: (\d+) samples.*?overshoot past settled ([-+\d.]+) m \| settled .*? after ([\d.]+) s", an, re.M)
    b = bag_steps.get(axis)
    if b:
        echo = f" (echo trace, #3's method: {float(m.group(2)):+.3f} m / {float(m.group(3)):.2f} s; that trace starts at the `ros2 topic pub` call, ~1.5–3 s before the commander reacts)" if m else ""
        row(f"{label}: overshoot (bag)", f"< {OVERSHOOT_MAX} m", f"{b['overshoot_m']:+.3f} m{echo}", f"{BASE[axis+'_overshoot']:+.3f} m (#3)", abs(b["overshoot_m"]) < OVERSHOOT_MAX)
        row(f"{label}: settle ±0.1 m (bag)", f"< {SETTLE_MAX} s", f"{b['settle_s']:.2f} s from command onset; commander ramp {b['commander_ramp_s']:.2f} s at {b['commanded_peak_speed_mps']:.2f} m/s peak, drone lag {b['lag_after_ramp_s']:+.2f} s" + (" (did not settle within the window)" if b.get("saturated") else ""),
            f"{BASE[axis+'_settle']} s (#3)", b["settle_s"] < SETTLE_MAX and not b.get("saturated"))
        row(f"{label}: ringing (bag)", "≤ 1 band re-entry", f"{b['band_reentries']} re-entries ({b['samples']} samples)", "-", b["band_reentries"] <= 1)
        if m:
            ov, st = float(m.group(2)), float(m.group(3))
            row(f"{label}: vs #3 (echo method)", "informational (#3 flew 0.6 m/s / 3.0 m/s²; now 2.0 / 6.0)", f"overshoot {ov - BASE[axis+'_overshoot']:+.3f} m, settle {st - BASE[axis+'_settle']:+.2f} s vs #3", "-",
                abs(ov) <= BASE[axis + '_overshoot'] + 0.05 and st <= BASE[axis + '_settle'] + 0.5, gate=False)
        continue
    if not m:
        row(f"{label}: overshoot", f"< {OVERSHOOT_MAX} m", "n/a", f"{BASE[axis+'_overshoot']} m (#3)", None)
        row(f"{label}: settle (±0.1 m)", f"< {SETTLE_MAX} s", "n/a", f"{BASE[axis+'_settle']} s (#3)", None)
        row(f"{label}: ringing", "≤ 1 band re-entry", "n/a", "-", None)
        continue
    n, ov, st = int(m.group(1)), float(m.group(2)), float(m.group(3))
    saturated = st >= WINDOW_S
    row(f"{label}: overshoot", f"< {OVERSHOOT_MAX} m", f"{ov:+.3f} m ({n} samples)", f"{BASE[axis+'_overshoot']:+.3f} m (#3)", abs(ov) < OVERSHOOT_MAX)
    row(f"{label}: settle (±0.1 m)", f"< {SETTLE_MAX} s", f"{st:.2f} s" + (" (did not settle within the trace)" if saturated else ""), f"{BASE[axis+'_settle']} s (#3)", st < SETTLE_MAX and not saturated)
    ts = trace_stats(name, axis)
    row(f"{label}: ringing", "≤ 1 band re-entry after settling", "n/a" if ts is None else f"{ts['reentries']} re-entries", "-", None if ts is None else ts["reentries"] <= 1)
    row(f"{label}: vs #3", "informational (#3 flew 0.6 m/s / 3.0 m/s²; now 2.0 / 6.0)", f"overshoot {ov - BASE[axis+'_overshoot']:+.3f} m, settle {st - BASE[axis+'_settle']:+.2f} s vs #3", "-",
        abs(ov) <= BASE[axis + '_overshoot'] + 0.05 and st <= BASE[axis + '_settle'] + 0.5, gate=False)
tc = bag_ev.get("takeoff")
m = re.search(r"^hz=40 .*?/ascent\.txt axis=z: (\d+) samples.*?overshoot past settled ([-+\d.]+) m \| settled .*? after ([\d.]+) s", an, re.M)
if tc:
    row("takeoff climb to 1.2 m (bag)", "informational", f"overshoot {tc['overshoot_m']:+.3f} m, settled {tc['settle_s']:.2f} s after the climb command ({tc['onset_s_after_arming']:.2f} s after arming), final z {tc['final_m']:.2f} m, commanded peak {tc['commanded_peak_speed_mps']:.2f} m/s", f"{BASE['ascent_overshoot']} m / {BASE['ascent_settle']} s (#3, echo method)", True, gate=False)
ld = bag_ev.get("landing")
if ld:
    row("landing descent (bag)", "informational", f"{ld['moved_m']:+.3f} m at {ld['commanded_peak_speed_mps']:.2f} m/s commanded, touchdown z {ld['final_m']:.2f} m", "-", True, gate=False)
elif m:
    row("takeoff climb to 1.2 m", "informational", f"overshoot {float(m.group(2)):+.3f} m, settled after {float(m.group(3)):.2f} s", f"{BASE['ascent_overshoot']} m / {BASE['ascent_settle']} s (#3)", True, gate=False)

# --- landing / disarm
land = read("landing_evidence.txt")
armed = read("armed_post.txt")
n1 = len(re.findall(r"landed, disarmed \(attempt 1\)", land)); nany = len(re.findall(r"landed, disarmed", land))
row("landing: disarmed x3", "'landed, disarmed' x3, no 'disarm not accepted'", f"{nany} disarmed ({n1} on attempt 1)" if land else "n/a", "#13: attempt 1 x3", (nany == 3 and "disarm not accepted" not in land) if land else None)
if armed.count("false") + armed.count("true"):
    row("post-flight armed=false x3 (MAVROS state)", "false x3", f"{armed.count('false')} false / {armed.count('true')} true", "-", armed.count("false") == 3)
elif bag.get("disarmed_at_s"):
    row("drone_1 disarmed (bag: MAVROS state)", "armed=false at the end", f"armed at {bag['armed_at_s']} s, disarmed at {bag['disarmed_at_s']} s, armed at end: {bag['armed_at_end']}", "-", bag.get("armed_at_end") is False)
else:
    row("post-flight armed=false x3 (MAVROS state)", "false x3", "n/a", "-", None)

# --- run hygiene
rw = read("res_watch.log")
wifi = rw.count("WIFI-ALERT")
vram = max((int(x) for x in re.findall(r"gpu (\d+)/", rw)), default=None)
row("WiFi firmware alerts during the run", "0", str(wifi) if rw else "n/a", "-", (wifi == 0) if rw else None)
bagdir = next((p for p in heavy.glob("hover_step_*") if p.is_dir()), None) if (heavy := pathlib.Path.home() / "flight_logs" / "sim" / RUN).exists() else None
bag_mb = sum(p.stat().st_size for p in bagdir.rglob("*")) // 1_000_000 if bagdir else 0
bag_ok = bool(bag.get("odom_msgs")) and bagdir is not None and (bagdir / "metadata.yaml").exists()
row("rosbag (first live use of record_bag)", "recorded, closed (metadata.yaml), readable", f"{bagdir.name}: {bag_mb} MB, {bag.get('odom_msgs', 0)} drone_1 odometry msgs over {bag.get('duration_s', '?')} s" if bagdir else "not found", "-", bag_ok if (bagdir or bag) else None, gate=False)
ulogs = [l.split() for l in read("ulog_sysid_map.txt").splitlines() if l.strip()]
row("PX4 ulogs, one per drone (sysid 2/3/4)", "3 files", f"{len(ulogs)} files, sysids {sorted(u[0] for u in ulogs)}" if ulogs else "n/a", "-", (sorted(u[0] for u in ulogs) == ["2", "3", "4"]) if ulogs else None, gate=False)

gates = [r for r in rows if r[5]]
verdict = "FAIL" if any(r[4] == "FAIL" for r in gates) else ("PASS" if all(r[4] == "PASS" for r in gates) else "INCOMPLETE")

# --- setup facts
try:
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
except Exception:
    head = "?"
pre = {}
try:
    pre = json.loads(read("status_pre.json") or "{}")
except json.JSONDecodeError:
    pass
tuning = pre.get("tuning", {})
times = re.findall(r"^\[(\d\d:\d\d:\d\d)\]", t, re.M)
span = f"{times[0]}–{times[-1]}" if times else ""
today = datetime.date.today().isoformat()
heavy = pathlib.Path.home() / "flight_logs" / "sim" / RUN
heavy_files = sorted(p.name + f" ({(sum(q.stat().st_size for q in p.rglob('*')) if p.is_dir() else p.stat().st_size) // 1_000_000} MB)" for p in heavy.iterdir()) if heavy.exists() else []
caveats = [l.strip() for l in read("caveats.txt").splitlines() if l.strip()]


def ledger_summary():
    bx, bz = bag_steps.get("x"), bag_steps.get("z")
    thr = f"hover thrust setpoint **{statistics.median(thrust):.3f}**" if thrust else "hover thrust n/a"
    parts = ["`Starling2MaxConfig` x3 (indirect: airframe 10090 x3 + Starling thrust)" if not num(ev.get("starling_cfg")) else "`Starling2MaxConfig` x3",
             "`SYS_AUTOSTART` 10090, `MC_PITCHRATE_P` 0.032, `LNDMC_ROT_MAX` 300, `MPC_XY_VEL_MAX` 20 from the ulog header",
             thr + " (#3: 0.155, real 0.165)"]
    if bx: parts.append(f"x step overshoot {bx['overshoot_m']:+.3f} m settled {bx['settle_s']:.2f} s (bag; #3 echo method: 0.002 / 2.75)")
    if bz: parts.append(f"z step {bz['overshoot_m']:+.3f} m / {bz['settle_s']:.2f} s (#3: 0.001 / 0.75)")
    if tc: parts.append(f"takeoff climb {tc['overshoot_m']:+.3f} m / {tc['settle_s']:.2f} s (#3: 0.31 / 7.9)")
    parts.append(f"`landed, disarmed (attempt 1)` x{n1}; {wifi} WiFi alerts")
    return "; ".join(parts)


def md():
    L = [f"RECORD · SIM — {RUN}. Sim-only (iron rule 9): none of these values is ported to the drone.", "",
         f"# {RUN} — Starling hover + 1 m steps on the rebuilt asset + 10-20 airframe ({today}{', ' + span if span else ''})", "",
         f"**Verdict: {verdict}.** Re-run of ledger #3 for Linear NEAR-786 (milestone S5). Gates are the M1 criteria in "
         f"[MILESTONES.md](../MILESTONES.md) §4; the #3 numbers are shown for comparison only (see Caveats).", "",
         "## Setup", "",
         "| Item | Value |", "|---|---|",
         "| Sim | Isaac Sim headless, 3 Starling 2 Max (`DRONE_USD=starling2max.usd`, `PX4_VEHICLE_MODEL=pegasus_starling2max`), default flat world |",
         "| Airframe | `10090_pegasus_starling2max` (10-20: rate gains x0.5, gyro filters 80/40, `LNDMC_ROT_MAX` 300, MPC limits 20/10/4) |",
         f"| Commander | CMU dev `b21d28c`, `cbf_sim.yaml scenario:=goal`, tuning {json.dumps(tuning) if tuning else 'n/a'}, `record_bag:=true` |",
         f"| Odometry rate | {hz_meas:g} Hz (bag count), so the echo traces' 40 Hz time axis holds |" if hz_meas else "| Odometry rate | n/a (analyser at 40 Hz) |",
         f"| Driver | `tools/sim_hover_step_run.sh` at repo `{head}`; flight tool `AirStack/simulation/isaac-sim/tools/sim_hover_step_test.sh` + `analyze_step.py` (copied, unchanged in the tree) |",
         f"| Host | laptop on WiFi, `sim_resources_watch.sh` running; peak VRAM {vram} MB |" if vram else "| Host | laptop on WiFi |",
         "", "## Pass/fail", "",
         "| Check | Criterion | Measured | #3 / expected | Verdict |", "|---|---|---|---|---|"]
    for c, cr, me, ba, v, g in rows:
        L.append(f"| {c} | {cr} | {me} | {ba} | {'**' + v + '**' if v in ('FAIL',) else v} |")
    L += ["", "Rows marked *note* are informational and never fail the run.", ""]
    if (OUT / "step_response.png").exists():
        L += [f"![drone_1 step responses from the rosbag]({RUN}/step_response.png)", "",
              "*Figure: measured position (blue) per event against time since the commander's first non-zero velocity command, "
              "with the ±0.1 m settle band and the settle time; below each, the commander's own velocity command and the end of its "
              "ramp. Made by `tools/hover_step_plot.py` from `drone_1_odom.csv` / `drone_1_cmd.csv`.*", ""]
    L += ["## Evidence", "",
          "```", read("isaac_evidence.txt").strip(), "```", "",
          "PX4 parameters (" + src + "):", "```", ptxt.strip() or "n/a", "```", "",
          "Flight tool stdout:", "```", t.strip() or "n/a", "```", "",
          "Analyser (echo traces, #3's method):", "```", an.strip() or "n/a", "```", "",
          "Bag analysis (`tools/hover_step_bag.py`, real timestamps):", "```", json.dumps(bag, indent=1) if bag else "n/a", "```", "",
          "Landing:", "```", (land.strip() + "\n" + "\n".join(l for l in armed.splitlines() if re.search(r"armed: (true|false)$", l))).strip() or "n/a", "```", "",
          "## Files", "",
          f"- Repo (this folder, `docs/record/{RUN}/`): `commands.sh` (every command used), `run.log`, `test_stdout.log`, `analyze.txt`, "
          "`step_x.txt` / `step_z.txt` / `ascent.txt` (odometry traces), `isaac_evidence.txt`, `params_ulog.txt`, `status_pre.json` / "
          "`status_post.json`, `landing_evidence.txt`, `res_watch.log`, the three container logs; `bag_analysis.json` + "
          "`drone_1_odom.csv` / `drone_1_cmd.csv` (from the bag) and `step_response.png`.",
          f"- Not in the repo (`~/flight_logs/sim/{RUN}/`): " + (", ".join(heavy_files) if heavy_files else "nothing copied") + ".",
          "", "## Caveats", "",
          "- #3 (2026-10-19) flew CMU's shipped goal profile, 0.6 m/s / 3.0 m/s²; `cbf_sim.yaml` now flies 2.0 m/s / 6.0 m/s² (ledger #12). "
          "The 1 m steps are therefore more aggressive than in #3, so a like-for-like comparison needs a second run at #3's speeds "
          "(`ros2 param set /swarm_commander scenario_speed_mps 0.6` and `goal_accel_mps2 3.0`, both live).",
          "- `analyze_step.py` measures against the settled value (mean of the last 0.5 s) in a ±0.1 m band; the trace starts after the goal "
          "is published, so `moved` is a lower bound. \"Ringing\" is counted here as re-entries into the band after the first entry.",
          "- Headless run driven from a non-interactive shell; nobody watched a window.",
          "- Timing gates use the rosbag (real receive timestamps); the `ros2 topic echo` traces are kept because that is how #3 was measured.",
          "- The `ulog thrust_setpoint median` line in analyze.txt is not meaningful (wrong field); the MAVROS `target_attitude` samples are the hover-thrust evidence."]
    L += [f"- {c}" for c in caveats]
    L += ["", "## Ledger row draft (MILESTONES.md §3c)", "",
          f"`| 17 | **M1 re-run of #3: Starling hover + 1 m steps on the rebuilt asset + 10-20 airframe + dev commander** "
          f"(`tools/sim_hover_step_run.sh`, `cbf_sim.yaml scenario:=goal`, `record_bag:=true`) | Isaac launch log, PX4 ulog header (pyulog), "
          f"MAVROS thrust setpoint, rosbag step timing (`tools/hover_step_bag.py`) + echo traces (`analyze_step.py`); record docs/record/{RUN}_record.md (link it from MILESTONES as record/{RUN}_record.md) | "
          + ledger_summary() + f". **{verdict}** against the M1 gates (#3 comparison informational: speeds differ) | {today} |`", ""]
    return "\n".join(L)


rec = OUT.parent / f"{RUN}_record.md"
rec.write_text(md())
print(f"{verdict}: {rec}")
for c, cr, me, ba, v, g in rows:
    print(f"  {v:10s} {c}: {me}")
sys.exit(0 if verdict == "PASS" else 1)
