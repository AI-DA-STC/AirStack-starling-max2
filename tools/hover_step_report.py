#!/usr/bin/env python3
"""Write the record for a sim hover + 1 m step run (S5 / NEAR-786; ledger #18 = re-run of #17 with fixed tooling).

    tools/hover_step_report.py docs/record/<run>/ [--heavy DIR] [--record PATH] [--no-verdict-log]

Reads the artefacts that tools/sim_hover_step_run.sh leaves in the run folder plus the bag analysis written by
tools/hover_step_analysis.py (`bag_analysis.json`).  Every gate row is PASS / FAIL / UNVERIFIED; an info row never
passes or fails the run.  Evidence that is missing, garbled or merely implied is UNVERIFIED, never PASS.

Exit code: 0 PASS (every gate PASS), 2 INCOMPLETE (no FAIL, >= 1 UNVERIFIED), 1 FAIL (>= 1 gate FAIL).
Files read: bag_analysis.json, px4_arm_times.txt, run_meta.txt, clock_check.txt, armed_post.txt, verdicts.log,
isaac_evidence.txt, params_ulog.txt, test_stdout.log, analyze.txt, landing_evidence.txt, res_watch.log,
ulog_sysid_map.txt, status_pre.json, caveats.txt, step_response.png (figure, optional); heavy dir: hover_step_*/metadata.yaml.
Writes: <record>.md and one appended line in <run>/verdicts.log.

Thresholds come from MILESTONES §4 ("Starling model: spawn + hover + steps"): hover thrust setpoint 0.12-0.20,
steps settle < 3 s (+/-0.1 m, PX4 vehicle time), overshoot < 0.15 m, no ringing (0 band re-entries).
Sim-only (CLAUDE.md iron rule 9): nothing measured here is ported to the drone."""
from __future__ import annotations

import argparse
import dataclasses
import datetime
import json
import pathlib
import re
import statistics
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
BASE = {"hover_thrust": 0.155, "x_overshoot": 0.002, "x_settle": 2.75, "z_overshoot": 0.001, "z_settle": 0.75,
        "ascent_overshoot": 0.31, "ascent_settle": 7.9}          # ledger #3 (2026-10-19, echo method) — info rows only
EXPECT_PARAMS = {"SYS_AUTOSTART": 10090, "MAV_SYS_ID": 2, "MC_PITCHRATE_P": 0.032, "MC_ROLLRATE_P": 0.032,
                 "LNDMC_ROT_MAX": 300, "MPC_XY_VEL_MAX": 20, "MPC_THR_HOVER": 0.165, "IMU_GYRO_CUTOFF": 80,
                 "IMU_DGYRO_CUTOFF": 40, "MPC_Z_VEL_MAX_DN": 4, "MPC_ACC_HOR": 6}
GATED_PARAMS = ["SYS_AUTOSTART", "MC_PITCHRATE_P", "LNDMC_ROT_MAX", "MPC_XY_VEL_MAX", "MPC_THR_HOVER", "IMU_GYRO_CUTOFF"]
OVERSHOOT_MAX, SETTLE_MAX, THRUST_LO, THRUST_HI = 0.15, 3.0, 0.12, 0.20
SCALE_LO, SCALE_HI = 0.5, 3.0
MIN_THRUST_SAMPLES = 5
THRESHOLDS_LINE = ("**Thresholds:** 0.15 m / 3.0 s / 0 re-entries / thrust 0.12–0.20 come from MILESTONES §4 (set 2026-10-19 in "
                   "docs/superpowers/plans/2026-10-19-starling2max-sim.md, bracketed by the Iris reading of ledger #2 — 0.14 m / 3.6 s — "
                   "not derived from a flight requirement). Gated values are PX4 vehicle time; wall-clock values in brackets.")
FIXED_CAVEATS = [
    "Sim path: the commander's TwistStamped velocity command goes through MAVROS setpoint_velocity to PX4 SITL; the real drone flies "
    "the trajectory-setpoint path (px4_interface). The step numbers characterise the sim loop, not the drone.",
    "n = STEPS_PER_AXIS steps per axis (±1 m alternating), one Isaac launch, one commander process: a single-launch sample, not a campaign.",
    "The ±0.1 m settle time is shaped by the commander's braking law (goal_accel / goal_settle_s) as much as by PX4: the command itself "
    "ramps for most of the settle window (see `commander_ramp_s`), so it is a loop figure, not a plant figure.",
    "`vs #3 (echo method)` rows are informational: #3 (2026-10-19) flew CMU's 0.6 m/s / 3.0 m/s² profile, `cbf_sim.yaml` now flies "
    "2.0 / 6.0, and the echo traces start at the `ros2 topic pub` call, 1.5–3 s before the commander reacts.",
    "The commander's `landed, disarmed` lines and the panel are ACK logs, not an arming display (iron rules 2 and 5); the arming gate "
    "is the MAVROS `armed: false` x3 read after the flight.",
]


# ----------------------------------------------------------------------------- rows
@dataclasses.dataclass
class Row:
    check: str
    criterion: str
    measured: str
    baseline: str
    verdict: str
    gate: bool


def row(rows: list, check: str, crit: str, meas: str, base: str, ok, gate: bool = True) -> Row:
    """gate rows: ok True/False/None -> PASS/FAIL/UNVERIFIED. info rows (gate=False) are always `info`."""
    if gate:
        v = "UNVERIFIED" if ok is None else ("PASS" if ok else "FAIL")
    else:
        v = "info"
    r = Row(check, crit, meas, base, v, gate)
    rows.append(r)
    return r


def overall_verdict(rows) -> str:
    gates = [r for r in rows if r.gate]
    if any(r.verdict == "FAIL" for r in gates):
        return "FAIL"
    if any(r.verdict == "UNVERIFIED" for r in gates):
        return "INCOMPLETE"
    return "PASS"


# ----------------------------------------------------------------------------- parsers
def read(out: pathlib.Path, name: str) -> str:
    p = out / name
    try:
        return p.read_text() if p.is_file() else ""
    except OSError:
        return ""


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def parse_kv(text: str) -> dict:
    """`key=value` lines (run_meta.txt, clock_check.txt, px4_arm_times.txt, isaac_evidence.txt tokens)."""
    out = {}
    for tok in re.findall(r"(\w+)=(\S+)", text):
        out.setdefault(tok[0], tok[1])
    return out


def parse_thrust_line(test_stdout: str):
    """The line AFTER `--- hover thrust samples`: >= 5 floats, all in [0, 1]; anything else -> None (no fallback)."""
    lines = test_stdout.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("--- hover thrust samples"):
            if i + 1 >= len(lines):
                return None
            vals = []
            for tok in lines[i + 1].split():
                v = num(tok)
                if v is None:
                    return None
                vals.append(v)
            if len(vals) < MIN_THRUST_SAMPLES or not all(0.0 <= v <= 1.0 for v in vals):
                return None
            return vals
    return None


def parse_armed_post(text: str):
    """Exactly drone_1..3 each with `armed: true|false`; any garbage or missing drone -> None."""
    found = {}
    for line in text.splitlines():
        m = re.match(r"^\s*(drone_[123]) armed: (true|false)\s*$", line)
        if m:
            found[m.group(1)] = m.group(2) == "true"
    if set(found) != {"drone_1", "drone_2", "drone_3"}:
        return None
    return found


def parse_params(text: str) -> dict:
    params = {}
    for m in re.finditer(r"^(\w+)[: ]+\s*(?:Double value is: |Integer value is: )?([-\d.eE+]+)", text, re.M):
        params[m.group(1)] = num(m.group(2))
    return params


def parse_echo_steps(analyze_txt: str, axis: str) -> list[dict]:
    """analyze_step.py lines for /tmp/step_<axis>[_k].txt (any hz); first line per trace file wins (hz=40 = #3's method)."""
    seen, out = set(), []
    for m in re.finditer(rf"^hz=(\S+) (\S*/step_{axis}(?:_(\d+))?\.txt) axis={axis}: (\d+) samples.*?overshoot past settled ([-+\d.]+) m \| "
                         rf"settled .*? after ([\d.]+) s", analyze_txt, re.M):
        if m.group(2) in seen:
            continue
        seen.add(m.group(2))
        out.append({"file": pathlib.Path(m.group(2)).name, "hz": m.group(1), "samples": int(m.group(4)),
                    "overshoot_m": float(m.group(5)), "settle_s": float(m.group(6))})
    return out


def git_head_short() -> str:
    try:
        r = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or "?"
    except Exception:
        return "?"


def dur(veh, wall) -> str:
    """Every duration: vehicle time first, wall in brackets."""
    if veh is None or wall is None:
        return "n/a"
    return f"{veh:.2f} s [{wall:.2f} s wall]"


# ----------------------------------------------------------------------------- rows from the run folder
def build_rows(out: pathlib.Path, heavy):
    out = pathlib.Path(out)
    heavy = pathlib.Path(heavy) if heavy is not None else None
    rows: list[Row] = []
    ctx: dict = {"run": out.name}

    # --- Isaac launch evidence
    ev = {k: num(v) for k, v in parse_kv(read(out, "isaac_evidence.txt")).items()}
    ctx["isaac_evidence"] = read(out, "isaac_evidence.txt").strip()
    for key, crit, want in [("autostart", "SYS_AUTOSTART=10090 x3", lambda n: n >= 3),
                            ("ready", "Ready for takeoff x3", lambda n: n == 3),
                            ("unknown_model", "no 'Unknown model'", lambda n: n == 0),
                            ("cooking", "no PhysX cooking warnings", lambda n: n == 0)]:
        n = ev.get(key)
        row(rows, "Isaac launch: " + crit, crit, "n/a" if n is None else str(int(n)), "-", None if n is None else want(n))
    sc = ev.get("starling_cfg")
    if not sc:   # 0 or missing: the launcher print was not captured — never PASS "indirectly"
        row(rows, "Isaac launch: Starling2MaxConfig x3", "Starling2MaxConfig x3 (launcher print)", "0 — launcher print not captured", "-", None)
    else:
        row(rows, "Isaac launch: Starling2MaxConfig x3", "Starling2MaxConfig x3 (launcher print)", str(int(sc)), "-", sc >= 3)

    # --- PX4 params: ulog header only
    ptxt = read(out, "params_ulog.txt")
    ctx["params_txt"] = ptxt.strip()
    params = parse_params(ptxt)
    for k in GATED_PARAMS:
        v = params.get(k)
        row(rows, f"PX4 {k} (ulog header)", f"= {EXPECT_PARAMS[k]}", "n/a" if v is None else f"{v:g}", "-",
            None if v is None else abs(v - EXPECT_PARAMS[k]) <= 1e-3 * max(1, abs(EXPECT_PARAMS[k])))

    # --- flight tool stdout
    t = read(out, "test_stdout.log")
    ctx["test_stdout"] = t.strip()
    times = re.findall(r"^\[(\d\d:\d\d:\d\d)\]", t, re.M)
    ctx["flight_span_utc"] = f"{times[0]}–{times[-1]}" if times else ""
    ctx["step_lines"] = re.findall(r"^\[\d\d:\d\d:\d\d\] (step [xz]\d*: goal .*)$", t, re.M)

    def yesno(cond):
        return ("yes" if cond else "no") if t else "n/a"
    tk = "takeoff: success=True" in t
    st = bool(re.search(r"start: success=True", t))
    ld = "land: success=True" in t and bool(re.search(r"landed: IDLE", t))
    row(rows, "takeoff accepted", "success=True", yesno(tk), "-", tk if t else None)
    row(rows, "start accepted (scenario goal)", "success=True", yesno(st), "-", st if t else None)
    row(rows, "land accepted + landed: IDLE", "land success=True and final state IDLE", yesno(ld), "-", ld if t else None)

    thrust = parse_thrust_line(t)
    ctx["thrust"] = thrust
    if thrust is None:
        row(rows, "hover thrust setpoint (MAVROS target_attitude)", f"{THRUST_LO:.2f}–{THRUST_HI:.2f}",
            f"n/a — no line of ≥ {MIN_THRUST_SAMPLES} in-range samples after the `--- hover thrust samples` header", f"{BASE['hover_thrust']} (#3); real drone 0.165", None)
    else:
        tm = statistics.median(thrust)
        ctx["thrust_median"] = tm
        row(rows, "hover thrust setpoint (MAVROS target_attitude)", f"{THRUST_LO:.2f}–{THRUST_HI:.2f}",
            f"median {tm:.3f} of {len(thrust)} samples (min {min(thrust):.3f}, max {max(thrust):.3f})", f"{BASE['hover_thrust']} (#3); real drone 0.165", THRUST_LO <= tm <= THRUST_HI)

    # --- bag analysis (tools/hover_step_analysis.py)
    try:
        bag = json.loads(read(out, "bag_analysis.json") or "{}")
    except json.JSONDecodeError:
        bag = {}
    if not isinstance(bag, dict):
        bag = {}
    ctx["bag"] = bag
    events = {e["name"]: e for e in bag.get("events", []) if isinstance(e, dict) and "name" in e}
    steps = bag.get("steps") or {}
    scale = bag.get("time_scale")
    src = bag.get("time_scale_source") or ""
    ctx["time_scale"], ctx["time_scale_source"] = scale, src
    px4t = parse_kv(read(out, "px4_arm_times.txt"))
    if not bag:
        row(rows, "time scale (PX4 s per wall s)", f"from px4_arm_times.txt, {SCALE_LO} < scale < {SCALE_HI}", "n/a — no bag_analysis.json", "-", None)
    elif src.startswith("px4_arm_times.txt") and scale is not None:
        meas = (f"{scale:.4f} ({src}; PX4 arm→disarm {bag.get('px4_arm_interval_s')} s vs bag {bag.get('bag_arm_interval_s')} s"
                + (f", ulog {px4t.get('source')}" if px4t.get("source") else "") + ")")
        row(rows, "time scale (PX4 s per wall s)", f"from px4_arm_times.txt, {SCALE_LO} < scale < {SCALE_HI}", meas, "1.0 = real time", SCALE_LO < scale < SCALE_HI)
    else:
        row(rows, "time scale (PX4 s per wall s)", f"from px4_arm_times.txt, {SCALE_LO} < scale < {SCALE_HI}",
            f"{src or 'assumed 1.0'} — vehicle-time values below equal wall time and are not verified", "1.0 = real time", None)

    for ax in ("x", "z"):
        s = steps.get(ax) if isinstance(steps, dict) else None
        base_ov, base_st = f"{BASE[ax + '_overshoot']:+.3f} m (#3)", f"{BASE[ax + '_settle']} s (#3, wall, echo)"
        echo = parse_echo_steps(read(out, "analyze.txt"), ax)
        if not s or not s.get("n"):
            why = "n/a — no bag_analysis.json" if not bag else f"n/a — no step_{ax}_* events in the bag"
            row(rows, f"{ax} step: overshoot max", f"< {OVERSHOOT_MAX} m", why, base_ov, None)
            row(rows, f"{ax} step: settle ±0.1 m vs goal (max of 0)", f"< {SETTLE_MAX} s (PX4 vehicle time)", why, base_st, None)
            row(rows, f"{ax} step: ringing", "0 band re-entries (±0.1 m)", why, "-", None)
            row(rows, f"{ax} step: commanded axis moved most", "odometry moved most on the commanded axis, every step", why, "-", None)
            if echo:
                row(rows, f"{ax} step: vs #3 (echo method)", "informational", "; ".join(f"{e['file']}: {e['overshoot_m']:+.3f} m / {e['settle_s']:.2f} s" for e in echo), f"{base_ov} / {base_st}", None, gate=False)
            continue
        n = s["n"]
        evs = [events[name] for name in s.get("names", []) if name in events]
        tail_ov = [abs(e["tail"]["overshoot_m"]) for e in evs if e.get("tail")]
        goal_ov = [abs(e["goal"]["overshoot_m"]) for e in evs if e.get("goal")]
        row(rows, f"{ax} step: overshoot max", f"< {OVERSHOOT_MAX} m",
            f"{s['overshoot_max_m']:.3f} m (tail-referenced max {max(tail_ov):.3f} m, goal-referenced max {max(goal_ov):.3f} m; n = {n})" if tail_ov and goal_ov else f"{s['overshoot_max_m']:.3f} m (n = {n})",
            base_ov, s["overshoot_max_m"] < OVERSHOOT_MAX)
        # settle: max over steps in vehicle time; wall value of that same step in brackets
        settled = [(e["vehicle_time"].get("settle_0p1_s"), e["goal"].get("settle_0p1_s"), e) for e in evs if e.get("goal") and e.get("vehicle_time")]
        worst = max((x for x in settled if x[0] is not None), key=lambda x: x[0], default=None)
        veh_max = s.get("settle_0p1_max_veh_s")
        if worst is None or veh_max is None:
            meas = "did not settle within the window" if s.get("any_saturated") else "n/a"
        else:
            med_veh = s.get("settle_0p1_median_veh_s")
            med_wall = statistics.median([x[1] for x in settled if x[1] is not None]) if settled else None
            meas = dur(veh_max, worst[1]) + f" max, median {dur(med_veh, med_wall)}; worst {worst[2]['name']}: commander ramp " \
                   f"{dur(worst[2]['vehicle_time'].get('commander_ramp_s'), worst[2].get('commander_ramp_s'))}, peak {worst[2]['commanded_peak_speed_mps']:.2f} m/s"
            if s.get("any_saturated"):
                meas += "; a step did not settle within the window"
        row(rows, f"{ax} step: settle ±0.1 m vs goal (max of {n})", f"< {SETTLE_MAX} s (PX4 vehicle time)", meas, base_st,
            None if veh_max is None else (veh_max < SETTLE_MAX and not s.get("any_saturated")))
        row(rows, f"{ax} step: ringing", "0 band re-entries (±0.1 m)",
            f"max {s['reentries_0p1_max']} re-entries over {n} steps (" + ", ".join(f"{e['name']}: {e['goal']['reentries_0p1']}" for e in evs if e.get("goal")) + ")",
            "-", s["reentries_0p1_max"] == 0)
        row(rows, f"{ax} step: commanded axis moved most", "odometry moved most on the commanded axis, every step",
            ("mismatch on " + ", ".join(f"{e['name']} (moved most: {e['moved_most_axis']})" for e in evs if e.get("axis_mismatch"))) if s.get("any_axis_mismatch") else
            "yes: " + ", ".join(f"{e['name']} → {e['moved_most_axis']}" for e in evs), "-", not s.get("any_axis_mismatch"))
        # info rows
        def med(key):
            v_veh = [e["vehicle_time"].get(key) for e in evs if e.get("vehicle_time") and e["vehicle_time"].get(key) is not None]
            v_wall = [e["goal"].get(key) for e in evs if e.get("goal") and e["goal"].get(key) is not None]
            return (statistics.median(v_veh), statistics.median(v_wall)) if v_veh and v_wall else (None, None)
        m05, m02 = med("settle_0p05_s"), med("settle_0p02_s")
        row(rows, f"{ax} step: settle ±0.05 / ±0.02 m vs goal (median)", "informational", f"{dur(*m05)} / {dur(*m02)}", "-", None, gate=False)
        row(rows, f"{ax} step: steady-state error max", "informational (|final − goal|)",
            f"{s.get('steady_state_error_max_m', 0):.3f} m (" + ", ".join(f"{e['name']}: {e['goal']['steady_state_error_m']:+.3f}" for e in evs if e.get("goal")) + ")", "-", None, gate=False)
        row(rows, f"{ax} step: velocity tracking", "informational (odometry velocity vs command; lag in vehicle time)",
            "; ".join(f"{e['name']}: lag {dur(e['vehicle_time'].get('lag_s'), e['velocity_tracking']['lag_s'])}, gain {e['velocity_tracking']['gain']:.2f}, residual {e['velocity_tracking']['residual_rms_mps']:.3f} m/s"
                      for e in evs if e.get("velocity_tracking") and e.get("vehicle_time")), "-", None, gate=False)
        row(rows, f"{ax} step: settle vs tail (old method)", "informational (±0.1 m around the settled value, #17's reference)",
            "; ".join(f"{e['name']}: {dur(e['vehicle_time'].get('settle_s'), e['tail'].get('settle_s'))}" + (" saturated" if e["tail"].get("saturated") else "") for e in evs if e.get("tail") and e.get("vehicle_time")),
            "-", None, gate=False)
        if echo:
            row(rows, f"{ax} step: vs #3 (echo method)", "informational (#3 flew 0.6 m/s / 3.0 m/s²; now 2.0 / 6.0; echo traces, wall time)",
                "; ".join(f"{e['file']} (hz={e['hz']}): overshoot {e['overshoot_m']:+.3f} m, settle {e['settle_s']:.2f} s" for e in echo)
                + f" — vs #3: {echo[0]['overshoot_m'] - BASE[ax + '_overshoot']:+.3f} m / {echo[0]['settle_s'] - BASE[ax + '_settle']:+.2f} s on the first step",
                f"{base_ov} / {base_st}", None, gate=False)

    tc = events.get("takeoff")
    if tc:
        row(rows, "takeoff climb", "informational", f"{dur(tc['vehicle_time'].get('settle_s'), tc['tail'].get('settle_s'))} settle vs tail, overshoot {tc['tail']['overshoot_m']:+.3f} m, "
            f"onset {tc['onset_s_after_arming']:.2f} s wall after arming, final z {tc['final_m']:.2f} m, commanded peak {tc['commanded_peak_speed_mps']:.2f} m/s"
            + (" (axis_mismatch flagged: the three takeoff axes move together — expected)" if tc.get("axis_mismatch") else ""),
            f"{BASE['ascent_overshoot']} m / {BASE['ascent_settle']} s (#3, echo method)", None, gate=False)
    lnd = events.get("landing")
    if lnd:
        row(rows, "landing descent", "informational", f"{lnd['moved_m']:+.3f} m at {lnd['commanded_peak_speed_mps']:.2f} m/s commanded peak, touchdown z {lnd['final_m']:.2f} m, "
            f"descent command ramp {dur(lnd['vehicle_time'].get('commander_ramp_s'), lnd.get('commander_ramp_s'))}", "-", None, gate=False)

    # --- landing / arming
    land = read(out, "landing_evidence.txt")
    ctx["landing_txt"] = land.strip()
    n1 = len(re.findall(r"landed, disarmed \(attempt 1\)", land))
    nany = len(re.findall(r"landed, disarmed", land))
    row(rows, "landing: 'landed, disarmed' x3 (commander ACK log, not an arming display)", "informational",
        f"{nany} 'landed, disarmed' ({n1} on attempt 1)" + ("; 'disarm not accepted' seen" if "disarm not accepted" in land else "") if land else "n/a", "#13: attempt 1 x3", None, gate=False)
    armed = parse_armed_post(read(out, "armed_post.txt"))
    ctx["armed_post"] = armed
    if armed is None:
        row(rows, "post-flight armed=false x3 (MAVROS state)", "armed: false for drone_1, drone_2, drone_3",
            "n/a — armed_post.txt does not hold three readable `drone_N armed: true|false` lines", "-", None)
    else:
        row(rows, "post-flight armed=false x3 (MAVROS state)", "armed: false for drone_1, drone_2, drone_3",
            ", ".join(f"{k} {'true' if v else 'false'}" for k, v in sorted(armed.items())), "-", not any(armed.values()))

    # --- run hygiene
    rw = read(out, "res_watch.log")
    wifi = rw.count("WIFI-ALERT")
    ctx["vram_mb"] = max((int(x) for x in re.findall(r"gpu (\d+)/", rw)), default=None)
    row(rows, "WiFi firmware alerts", "0 during the run", str(wifi) if rw else "n/a — no res_watch.log", "-", (wifi == 0) if rw else None)

    bagdir = None
    if heavy is not None and heavy.is_dir():
        bagdir = next((p for p in sorted(heavy.glob("hover_step_*")) if p.is_dir()), None)
    odom_msgs = bag.get("odom_msgs") or 0
    if bagdir is None:
        row(rows, "rosbag copied + readable", "bag dir with metadata.yaml under the heavy folder, drone_1 odometry > 0 msgs",
            f"n/a — no hover_step_* dir under {heavy if heavy is not None else 'the heavy folder'}", "-", None)
    else:
        bag_mb = sum(p.stat().st_size for p in bagdir.rglob("*") if p.is_file()) // 1_000_000
        has_meta = (bagdir / "metadata.yaml").is_file()
        row(rows, "rosbag copied + readable", "bag dir with metadata.yaml under the heavy folder, drone_1 odometry > 0 msgs",
            f"{bagdir.name}: {bag_mb} MB, metadata.yaml {'present' if has_meta else 'MISSING'}, {odom_msgs} drone_1 odometry msgs over {bag.get('duration_s', '?')} s"
            + (f" at {bag.get('odom_rate_hz')} Hz" if bag.get("odom_rate_hz") else ""), "-", has_meta and odom_msgs > 0)
    ulogs = [l.split() for l in read(out, "ulog_sysid_map.txt").splitlines() if l.strip()]
    sysids = sorted(u[0] for u in ulogs if u)
    row(rows, "PX4 ulogs one per sysid 2/3/4", "ulog_sysid_map.txt lists sysids 2, 3, 4 (drone_1/2/3)",
        f"{len(ulogs)} files, sysids {sysids}" if ulogs else "n/a — ulog_sysid_map.txt missing or empty", "-", (sysids == ["2", "3", "4"]) if ulogs else None)

    clock = parse_kv(read(out, "clock_check.txt")).get("clock_rc")
    row(rows, "/clock visible in the robot container", "informational (rc 0 = topic exists)",
        {"0": "yes (clock_rc=0)", "1": "no (clock_rc=1: the flight tool's wait_s is a real sleep)"}.get(clock, "n/a — no clock_check.txt"), "-", None, gate=False)

    meta = parse_kv(read(out, "run_meta.txt"))
    ctx["meta"] = meta
    now_head = git_head_short()
    ctx["report_head"] = now_head
    ran = meta.get("head_short") or "?"
    code = f"ran at {ran}" if ran == now_head else f"ran at {ran}, report at {now_head}"
    dirty = num(meta.get("dirty_tools"))
    if dirty:
        code += " (tools/ had uncommitted changes)"
    if not meta:
        code = f"n/a — no run_meta.txt; report at {now_head}"
    row(rows, "code that ran", "informational (run_meta.txt head vs git HEAD at report time)", code, "-", None, gate=False)

    history = [l for l in read(out, "verdicts.log").splitlines() if l.strip()]
    ctx["history"] = history
    row(rows, "driver verdict history", "informational (every earlier generation of this record, newest last)",
        "<br>".join(f"`{l}`" for l in history) if history else "none — first generation", "-", None, gate=False)

    try:
        pre = json.loads(read(out, "status_pre.json") or "{}")
    except json.JSONDecodeError:
        pre = {}
    ctx["tuning"] = pre.get("tuning", {}) if isinstance(pre, dict) else {}
    ctx["caveats"] = [l.strip() for l in read(out, "caveats.txt").splitlines() if l.strip()]
    ctx["analyze_txt"] = read(out, "analyze.txt").strip()
    ctx["heavy"] = heavy
    ctx["steps"] = steps
    ctx["events"] = events
    return rows, ctx


# ----------------------------------------------------------------------------- verdict log + markdown
def append_verdict(out: pathlib.Path, verdict: str, rows, head_short: str) -> str:
    n_fail = sum(1 for r in rows if r.gate and r.verdict == "FAIL")
    n_unv = sum(1 for r in rows if r.gate and r.verdict == "UNVERIFIED")
    stamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    line = f"{stamp} head={head_short} verdict={verdict} fail={n_fail} unverified={n_unv}"
    with open(pathlib.Path(out) / "verdicts.log", "a") as fh:
        fh.write(line + "\n")
    return line


def _cell(s) -> str:
    """A markdown table cell: a literal `|` in the text would split the column."""
    return str(s).replace("|", "\\|").replace("\n", " ")


def _fmt(v, spec=".3f", suffix=""):
    return "n/a" if v is None else f"{v:{spec}}{suffix}"


def ledger_row(ctx, rows, verdict, today) -> str:
    run, bag, steps, events = ctx["run"], ctx["bag"], ctx["steps"], ctx["events"]
    ev = parse_kv(ctx["isaac_evidence"])
    parts = [f"`Starling2MaxConfig` ×{ev.get('starling_cfg', '?')}, `SYS_AUTOSTART` 10090 ×{ev.get('autostart', '?')}, `Ready for takeoff` ×{ev.get('ready', '?')}",
             "ulog `MC_PITCHRATE_P` 0.032 / `LNDMC_ROT_MAX` 300 / `MPC_XY_VEL_MAX` 20 / `MPC_THR_HOVER` 0.165" if ctx["params_txt"] else "ulog params n/a",
             f"hover thrust setpoint **{_fmt(ctx.get('thrust_median'))}** (#17: 0.153, real 0.165)",
             f"time scale **{_fmt(ctx.get('time_scale'), '.4f')}** PX4 s per wall s ({ctx.get('time_scale_source') or 'n/a'})",
             f"odometry {bag.get('odom_rate_hz', 'n/a')} Hz"]
    for ax in ("x", "z"):
        s = steps.get(ax) if isinstance(steps, dict) else None
        if not s or not s.get("n"):
            parts.append(f"{ax} steps: n/a")
            continue
        evs = [events[n] for n in s.get("names", []) if n in events]
        worst = max((e for e in evs if e.get("vehicle_time", {}).get("settle_0p1_s") is not None), key=lambda e: e["vehicle_time"]["settle_0p1_s"], default=None)
        wall = worst["goal"]["settle_0p1_s"] if worst else None
        m05 = statistics.median([e["vehicle_time"]["settle_0p05_s"] for e in evs if e.get("vehicle_time", {}).get("settle_0p05_s") is not None] or [None]) if evs else None
        vt = [e["velocity_tracking"] for e in evs if e.get("velocity_tracking")]
        lag = statistics.median([e["vehicle_time"]["lag_s"] for e in evs if e.get("vehicle_time", {}).get("lag_s") is not None] or [None]) if evs else None
        parts.append(f"{ax} steps ({s['n']}): overshoot max {s['overshoot_max_m']:.3f} m, settle ±0.1 m vs goal max **{_fmt(s.get('settle_0p1_max_veh_s'), '.2f', ' s')}** vehicle "
                     f"[{_fmt(wall, '.2f', ' s')} wall], median {_fmt(s.get('settle_0p1_median_veh_s'), '.2f', ' s')}, ±0.05 m median {_fmt(m05, '.2f', ' s')}, "
                     f"steady-state error max {s.get('steady_state_error_max_m', 0):.3f} m, velocity lag {_fmt(lag, '.2f', ' s')} / gain {_fmt(statistics.median([v['gain'] for v in vt]) if vt else None, '.2f')} / "
                     f"residual {_fmt(statistics.median([v['residual_rms_mps'] for v in vt]) if vt else None, '.3f', ' m/s')}; {s['reentries_0p1_max']} band re-entries max"
                     + ("; axis mismatch" if s.get("any_axis_mismatch") else ""))
    tc = events.get("takeoff")
    if tc:
        parts.append(f"takeoff climb {tc['tail']['overshoot_m']:+.3f} m / {_fmt(tc['vehicle_time'].get('settle_s'), '.2f', ' s')} vehicle")
    landing_row = next((r for r in rows if r.check.startswith("landing: 'landed, disarmed'")), None)
    armed_row = next((r for r in rows if r.check.startswith("post-flight armed")), None)
    parts.append(f"{landing_row.measured if landing_row else 'n/a'} (ACK log); MAVROS {armed_row.measured if armed_row else 'n/a'} ({armed_row.verdict if armed_row else 'n/a'})")
    wifi_row = next((r for r in rows if r.check.startswith("WiFi")), None)
    parts.append(f"{wifi_row.measured if wifi_row else 'n/a'} WiFi alerts")
    gens = len(ctx["history"]) + 1
    parts.append(f"driver verdict history: {gens} generation{'s' if gens != 1 else ''}, latest `{verdict}`")
    unv = [r.check for r in rows if r.gate and r.verdict == "UNVERIFIED"]
    fails = [r.check for r in rows if r.gate and r.verdict == "FAIL"]
    tail = f"**{verdict}** on the hover + step row of M1 (sim path, n = {steps.get('x', {}).get('n', '?') if isinstance(steps, dict) else '?'} per axis, one launch)"
    if unv:
        tail += "; UNVERIFIED: " + ", ".join(unv)
    if fails:
        tail += "; FAIL: " + ", ".join(fails)
    return (f"`| 18 | **M1 re-run of #17 with the fixed tooling: Starling hover + 1 m steps, {steps.get('x', {}).get('n', '?') if isinstance(steps, dict) else '?'} per axis (±1 m alternating), "
            f"gated in PX4 vehicle time** — `tools/sim_hover_step_run.sh all {run}`, `cbf_sim.yaml scenario:=goal`, `record_bag:=true` | Isaac launch log; PX4 ulog header (pyulog); "
            f"MAVROS `target_attitude` thrust samples; rosbag → `tools/hover_step_analysis.py` (commanded axis, goal-referenced, time scale from the ulog arm/disarm vs MAVROS state); "
            f"`tools/hover_step_report.py` fail-closed; record `docs/record/{run}_record.md` (link it from MILESTONES as `record/{run}_record.md`), artefacts `docs/record/{run}/`, bag + 3 ulogs (sysid 2/3/4 = drone_1/2/3) "
            f"in `~/flight_logs/sim/{run}/` | " + "; ".join(parts) + f". {tail}. Thresholds 0.15 m / 3 s / 0 re-entries are MILESTONES §4's (bracketed by the Iris #2 reading, not derived). "
            f"Sim-only (iron rule 9) | {today} |`")


def render_md(out: pathlib.Path, rows, ctx, verdict: str, history: list) -> str:
    out = pathlib.Path(out)
    run = ctx["run"]
    meta = ctx.get("meta", {})
    started, tz = meta.get("started", "n/a"), meta.get("tz", "")
    span = ctx.get("flight_span_utc", "")
    today = datetime.date.today().isoformat()
    when = f"started {started} {tz}".rstrip() + (f"; flight {span} UTC (container clock)" if span else "; flight span n/a — UTC (container clock)")
    heavy = ctx.get("heavy")
    heavy_files = []
    if heavy is not None and pathlib.Path(heavy).is_dir():
        for p in sorted(pathlib.Path(heavy).iterdir()):
            size = sum(q.stat().st_size for q in p.rglob("*") if q.is_file()) if p.is_dir() else p.stat().st_size
            heavy_files.append(f"`{p.name}` ({size // 1_000_000} MB)")
    repo_files = sorted(p.name for p in out.iterdir() if p.is_file()) if out.is_dir() else []
    hz = ctx["bag"].get("odom_rate_hz")
    n_steps = {ax: (ctx["steps"].get(ax) or {}).get("n", 0) for ax in ("x", "z")} if isinstance(ctx["steps"], dict) else {}
    L = [f"RECORD · SIM — {run}. Sim-only (iron rule 9): none of these values is ported to the drone.", "",
         f"# {run} — Starling hover + 1 m steps (sim, {n_steps.get('x', 0)} per axis), gated in PX4 vehicle time ({when})", "",
         f"**Verdict: {verdict}.** Re-run of ledger #17 with the fixed tooling, for Linear NEAR-786 (milestone S5). Gates are the M1 criteria in "
         f"[MILESTONES.md](../MILESTONES.md) §4 (\"Starling model: spawn + hover + steps\"); PASS = every gate PASS, INCOMPLETE = no FAIL but "
         f"≥ 1 gate UNVERIFIED (evidence missing or unreadable), FAIL = any gate FAIL. Report generated {today} at repo `{ctx.get('report_head', '?')}`.", "",
         "## Setup", "",
         "| Item | Value |", "|---|---|",
         "| Sim | Isaac Sim headless, 3 Starling 2 Max (`DRONE_USD=starling2max.usd`, `PX4_VEHICLE_MODEL=pegasus_starling2max`), default flat world |",
         "| Airframe | `10090_pegasus_starling2max` (10-20: rate gains x0.5, gyro filters 80/40, `LNDMC_ROT_MAX` 300, MPC limits 20/10/4) — sim-only |",
         f"| Commander | CMU dev `b21d28c`, `cbf_sim.yaml scenario:=goal`, tuning {json.dumps(ctx['tuning']) if ctx.get('tuning') else 'n/a'}, `record_bag:=true` |",
         f"| Odometry rate | {hz:g} Hz (bag count over its duration) |" if hz else "| Odometry rate | n/a |",
         f"| Time scale | {_fmt(ctx.get('time_scale'), '.4f')} PX4 s per wall s ({ctx.get('time_scale_source') or 'n/a'}); gated durations are vehicle time, wall in brackets |",
         f"| Driver | `tools/sim_hover_step_run.sh` + `tools/sim_hover_step_test.sh` + `tools/analyze_step.py`, repo commit `{meta.get('head', meta.get('head_short', 'n/a'))}` "
         f"(`run_meta.txt`; tools/ uncommitted changes: {meta.get('dirty_tools', 'n/a')}); analysis `tools/hover_step_analysis.py`, report `tools/hover_step_report.py` |",
         f"| Started | {started} {tz} (laptop clock, `run_meta.txt`); flight {span or 'n/a'} UTC (container clock, `test_stdout.log`) |",
         f"| Host | laptop; `sim_resources_watch.sh` peak VRAM {ctx['vram_mb']} MB |" if ctx.get("vram_mb") else "| Host | laptop |",
         "", "## Pass/fail", "",
         "| Check | Criterion | Measured | #3 / expected | Verdict |", "|---|---|---|---|---|"]
    for r in rows:
        v = f"**{r.verdict}**" if r.verdict in ("FAIL", "UNVERIFIED") else r.verdict
        L.append("| " + " | ".join(_cell(x) for x in (r.check, r.criterion, r.measured, r.baseline, v)) + " |")
    L += ["", "Rows marked info are informational and never pass or fail the run.", "", THRESHOLDS_LINE, ""]
    if (out / "step_response.png").exists():
        L += [f"![drone_1 step responses from the rosbag]({run}/step_response.png)", "",
              "*Figure: measured position per event against time since the commander's first non-zero velocity command (wall s; the title names "
              "the vehicle-time scale), with the goal (dotted), the ±0.1 m band and the settle time; below each, the commander's own velocity command "
              "and the end of its ramp. Made by `tools/hover_step_plot.py` from `drone_1_odom.csv` / `drone_1_cmd.csv`.*", ""]
    L += ["## Driver verdict history", "",
          "Every generation of this record (`verdicts.log`, newest last; the last line is this one):", "", "```",
          "\n".join(history) if history else "none", "```", "",
          "## Evidence", "",
          "Isaac launch evidence:", "```", ctx.get("isaac_evidence") or "n/a", "```", "",
          "PX4 parameters (ulog header, sysid 2):", "```", ctx.get("params_txt") or "n/a", "```", "",
          "Flight tool stdout (times are UTC, container clock):", "```", ctx.get("test_stdout") or "n/a", "```", "",
          "Analyser (echo traces, #3's method, informational):", "```", ctx.get("analyze_txt") or "n/a", "```", "",
          "Bag analysis (`tools/hover_step_analysis.py`; onset/settle definitions in its docstring):", "```",
          json.dumps(ctx["bag"], indent=1) if ctx.get("bag") else "n/a", "```", "",
          "Landing (commander ACK log) and post-flight MAVROS state:", "```",
          ((ctx.get("landing_txt") or "n/a") + "\n" + ("\n".join(f"{k} armed: {'true' if v else 'false'}" for k, v in sorted(ctx["armed_post"].items())) if ctx.get("armed_post") else "armed_post.txt: unreadable")).strip(),
          "```", "",
          "## Files", "",
          f"- Repo (this folder, `docs/record/{run}/`): " + (", ".join(f"`{f}`" for f in repo_files) if repo_files else "nothing") + ".",
          f"- Not in the repo (`{heavy if heavy is not None else '~/flight_logs/sim/' + run}/`): " + (", ".join(heavy_files) if heavy_files else "nothing copied") + ".",
          "", "## Caveats", ""]
    L += [f"- {c}" for c in FIXED_CAVEATS]
    L += [f"- {c}" for c in ctx.get("caveats", [])]
    L += ["", "## Ledger row draft (MILESTONES.md §3c, #18)", "", ledger_row(ctx, rows, verdict, today), ""]
    return "\n".join(L)


# ----------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("run_dir", help="docs/record/<run>/ with the driver's artefacts and bag_analysis.json")
    ap.add_argument("--heavy", default=None, help="bag + ulog folder (default ~/flight_logs/sim/<run>)")
    ap.add_argument("--record", default=None, help="markdown path (default <run_dir>/../<run>_record.md)")
    ap.add_argument("--no-verdict-log", action="store_true", help="do not append this verdict to <run_dir>/verdicts.log")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.run_dir).resolve()
    if not out.is_dir():
        print(f"not a directory: {out}", file=sys.stderr)
        return 2
    heavy = pathlib.Path(a.heavy).expanduser() if a.heavy else pathlib.Path.home() / "flight_logs" / "sim" / out.name
    rec = pathlib.Path(a.record) if a.record else out.parent / f"{out.name}_record.md"
    rows, ctx = build_rows(out, heavy)
    verdict = overall_verdict(rows)
    history = list(ctx.get("history", []))
    if not a.no_verdict_log:
        history.append(append_verdict(out, verdict, rows, ctx.get("meta", {}).get("head_short", "?")))
    rec.write_text(render_md(out, rows, ctx, verdict, history))
    print(f"{verdict}: {rec}")
    for r in rows:
        if r.gate and r.verdict != "PASS":
            print(f"  {r.verdict:10s} {r.check}: {r.measured}")
    return {"PASS": 0, "INCOMPLETE": 2}.get(verdict, 1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
