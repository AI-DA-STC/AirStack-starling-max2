#!/usr/bin/env python3
"""Hover + step analysis of the sim hover-step bag CSVs (pure Python + numpy; no ROS).

Definitions (cite these in the record):
1. Onset   = the first commanded-velocity sample with |v| >= 0.10 m/s on an axis after >= 0.8 s without any
             sample >= 0.10 m/s on that axis; the ramp ends at the first sample >= 0.3 s later with |v| < 0.02 m/s.
2. Axis    = the COMMANDED axis; `moved_most_axis` is what the odometry actually did, `axis_mismatch` if they differ.
3. Window  = [onset, min(next onset >= 2 s later, onset + 8 s)]; tail = its last 0.5 s; final_m = mean of the tail.
4. Tail metrics reference final_m (what the drone settled at); goal metrics reference goal_m = start_m + commanded delta.
5. Settle  = time from onset to the FIRST in-band sample after the LAST excursion out of +/-band; re-entries count
             the extra entries into the band after the first one (0 = no ringing); saturated = still out at window end.
6. Time    = bag times are wall-clock seconds; vehicle time = wall x time_scale, time_scale = PX4 (arm->disarm) /
             bag (arm->disarm); velocity tracking differentiates odometry in wall time and divides by time_scale.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import statistics
import sys

import numpy as np

AXIS_NAMES = {1: "x", 2: "y", 3: "z"}
ONSET = 0.10
DONE = 0.02
QUIET_S = 0.8
MIN_RAMP_S = 0.3
WINDOW_S = 8.0
NEXT_ONSET_GAP_S = 2.0
TAIL_S = 0.5
TAKEOFF_PHASE_S = 15.0
MIN_SAMPLES = 20
LANDING_Z_M = 0.3
LAG_GRID = np.arange(-0.5, 1.0001, 0.025)


# ----------------------------------------------------------------------------- loaders
def _rows(path):
    with open(path, newline="") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if i == 0 and not line[0].isdigit() and not line[0] in "-+.":
                continue  # header
            yield line.split(",")


def load_xyz_csv(path) -> list[tuple[float, float, float, float]]:
    """`t_s,x,y,z` (odometry) or `t_s,vx,vy,vz` (velocity command) -> [(t, a, b, c), ...]."""
    return [(float(r[0]), float(r[1]), float(r[2]), float(r[3])) for r in _rows(path)]


def load_state_csv(path) -> list[tuple[float, bool, str]]:
    """`t_s,armed,mode` -> [(t, armed, mode), ...]."""
    return [(float(r[0]), bool(int(r[1])), r[2].strip()) for r in _rows(path)]


def load_px4_arm_times(path) -> dict | None:
    """Parse hover_step_timescale.py's `key=value` line. None if the file is missing or lacks arm_s/disarm_s."""
    p = pathlib.Path(path) if path is not None else None
    if p is None or not p.is_file():
        return None
    out: dict = {}
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for tok in line.split():
            if "=" not in tok:
                continue
            k, v = tok.split("=", 1)
            if k in ("arm_s", "disarm_s", "interval_s"):
                try:
                    out[k] = float(v)
                except ValueError:
                    pass
            elif k == "sysid":
                try:
                    out[k] = int(v)
                except ValueError:
                    out[k] = v
            else:
                out[k] = v
    if "arm_s" not in out or "disarm_s" not in out:
        return None
    out.setdefault("interval_s", out["disarm_s"] - out["arm_s"])
    out.setdefault("source", "?")
    out.setdefault("sysid", None)
    return out


# ----------------------------------------------------------------------------- arming / time scale
def arming_events(state) -> tuple[list[float], list[float], bool | None]:
    """(arm times, disarm times, armed at end) from the `armed` column's transitions."""
    arms: list[float] = []
    disarms: list[float] = []
    prev = None
    for t, armed, _mode in state:
        if prev is not None and armed != prev:
            (arms if armed else disarms).append(t)
        prev = armed
    return arms, disarms, (state[-1][1] if state else None)


def compute_time_scale(px4_arm_s, px4_disarm_s, bag_arm_s, bag_disarm_s) -> float:
    """Vehicle seconds per bag (wall) second = PX4 arm->disarm interval / bag arm->disarm interval."""
    px4 = px4_disarm_s - px4_arm_s
    bag = bag_disarm_s - bag_arm_s
    if px4 <= 1.0 or bag <= 1.0:
        raise ValueError(f"arm->disarm interval too short: px4 {px4:.3f} s, bag {bag:.3f} s (need > 1.0 s each)")
    return px4 / bag


# ----------------------------------------------------------------------------- detector
def detect_events(cmd, onset=ONSET, done=DONE, quiet_s=QUIET_S, min_ramp_s=MIN_RAMP_S) -> list[dict]:
    """Per-axis velocity-command events: {axis (1/2/3), onset, ramp_end, peak_v}, sorted by (onset, axis).

    A sample is loud iff |v| >= onset. An onset is a loud sample with t - last_loud >= quiet_s while no event
    is open. ramp_end = first sample with t - onset >= min_ramp_s and |v| < done; after it last_loud = ramp_end.
    Loud samples that are not onsets only refresh last_loud; samples in [done, onset) touch nothing.
    """
    events: list[dict] = []
    for axis in (1, 2, 3):
        last_loud = -math.inf
        open_ev = None
        for row in cmd:
            t, v = row[0], row[axis]
            av = abs(v)
            if open_ev is not None:
                if t - open_ev["onset"] >= min_ramp_s and av < done:
                    open_ev["ramp_end"] = t
                    events.append(open_ev)
                    last_loud = t
                    open_ev = None
                else:
                    if av > abs(open_ev["peak_v"]):
                        open_ev["peak_v"] = v
                continue
            if av >= onset:
                if t - last_loud >= quiet_s:
                    open_ev = {"axis": axis, "onset": t, "ramp_end": None, "peak_v": v}
                else:
                    last_loud = t
        if open_ev is not None:  # command stream ended mid-event
            open_ev["ramp_end"] = cmd[-1][0]
            open_ev["truncated"] = True
            events.append(open_ev)
    events.sort(key=lambda e: (e["onset"], e["axis"]))
    return events


# ----------------------------------------------------------------------------- windows / naming
def event_window_end(events, i, window_s=WINDOW_S, gap_s=NEXT_ONSET_GAP_S) -> float:
    """End of event i's measurement window: the next onset >= gap_s later, capped at onset + window_s."""
    onset = events[i]["onset"]
    end = onset + window_s
    for e in events[i + 1:]:
        if e["onset"] >= onset + gap_s:
            end = min(end, e["onset"])
            break
    return end


def _odom_window(odom, t0, t1):
    return [r for r in odom if t0 <= r[0] <= t1]


def _tail(win, end, tail_s=TAIL_S):
    tail = [r for r in win if r[0] >= end - tail_s]
    return tail if tail else win[-1:]


def name_events(events, t_arm, odom, takeoff_phase_s=TAKEOFF_PHASE_S, step_delta_m=1.0) -> list[dict]:
    """Add `name` and `commanded_delta_m` (+/-step_delta_m for steps, None otherwise) to each event."""
    counts = {1: 0, 2: 0, 3: 0}
    takeoff_seen = False
    for i, e in enumerate(events):
        ax = AXIS_NAMES[e["axis"]]
        dt = e["onset"] - t_arm if t_arm is not None else None
        e["commanded_delta_m"] = None
        if dt is not None and 0.0 <= dt < takeoff_phase_s:
            if e["axis"] == 3 and e["peak_v"] > 0 and not takeoff_seen:
                e["name"] = "takeoff"
                takeoff_seen = True
            else:
                e["name"] = f"takeoff_lateral_{ax}"
            continue
        if e["axis"] == 3 and e["peak_v"] < 0:
            end = event_window_end(events, i)
            win = _odom_window(odom, e["onset"], end)
            if win:
                tail_z = statistics.fmean(r[3] for r in _tail(win, end))
                if tail_z < LANDING_Z_M:
                    e["name"] = "landing"
                    continue
        counts[e["axis"]] += 1
        e["name"] = f"step_{ax}_{counts[e['axis']]}"
        e["commanded_delta_m"] = step_delta_m if e["peak_v"] > 0 else -step_delta_m
    return events


# ----------------------------------------------------------------------------- settle / tracking
def settle_after_last_excursion(seg, ref, band) -> tuple[float | None, int, bool]:
    """seg = [(t, v), ...]. -> (settle time from seg[0].t to the first in-band sample after the last excursion,
    band re-entries after the first entry, saturated = still out of band at the last sample)."""
    if not seg:
        return None, 0, False
    t0 = seg[0][0]
    inband = [abs(v - ref) <= band for _t, v in seg]
    reent = sum(1 for a, b in zip(inband, inband[1:]) if (not a) and b)
    if not inband[0]:
        reent -= 1
    reent = max(reent, 0)
    out_idx = [i for i, ok in enumerate(inband) if not ok]
    if not out_idx:
        return 0.0, reent, False
    last_out = out_idx[-1]
    if last_out == len(seg) - 1:
        return seg[-1][0] - t0, reent, True
    return seg[last_out + 1][0] - t0, reent, False


def _moving_average(v, n=5):
    kernel = np.ones(n)
    return np.convolve(v, kernel, mode="same") / np.convolve(np.ones_like(v), kernel, mode="same")


def velocity_tracking(odom_win, cmd, axis, time_scale) -> dict:
    """Measured velocity (vehicle time) vs the commanded velocity on `axis`: best lag (wall s), gain, residual RMS."""
    t = np.array([r[0] for r in odom_win], dtype=float)
    p = np.array([r[axis] for r in odom_win], dtype=float)
    if len(t) < 7 or np.ptp(t) <= 0:
        return {"lag_s": None, "gain": None, "residual_rms_mps": None}
    vm = _moving_average(np.gradient(p, t), 5) / time_scale
    t_cmd = np.array([r[0] for r in cmd], dtype=float)
    v_cmd = np.array([r[axis] for r in cmd], dtype=float)
    best_lag, best_rms = None, math.inf
    for lag in LAG_GRID:
        vc = np.interp(t - lag, t_cmd, v_cmd)
        rms = float(np.sqrt(np.mean((vm - vc) ** 2)))
        if rms < best_rms:
            best_lag, best_rms = float(lag), rms
    vc0 = np.interp(t, t_cmd, v_cmd)
    gain = float(np.max(np.abs(vm)) / max(np.max(np.abs(vc0)), 1e-6))
    return {"lag_s": round(best_lag, 3), "gain": round(gain, 3), "residual_rms_mps": round(best_rms, 3)}


# ----------------------------------------------------------------------------- measurement
def _scaled(v, s):
    return None if v is None else round(v * s, 3)


def measure_event(event, odom, cmd, end, time_scale=1.0, band=0.1) -> dict:
    """Measure one named event over [onset, end]. Returns the output-schema event dict, or
    {"name", "axis", "onset_s_from_bag_start", "skipped"} when the window has fewer than MIN_SAMPLES samples."""
    axis = event["axis"]
    ax = AXIS_NAMES[axis]
    onset = event["onset"]
    win = _odom_window(odom, onset, end)
    head = {"name": event["name"], "axis": ax, "onset_s_from_bag_start": round(onset, 3)}
    if len(win) < MIN_SAMPLES:
        return {**head, "skipped": f"fewer than {MIN_SAMPLES} samples"}
    delta = event.get("commanded_delta_m")
    moved = {a: abs(win[-1][a] - win[0][a]) for a in (1, 2, 3)}
    moved_most = max(moved, key=moved.get)
    tail = _tail(win, end)
    start = win[0][axis]
    final = statistics.fmean(r[axis] for r in tail)
    sign = (1.0 if delta > 0 else -1.0) if delta else (1.0 if final - start >= 0 else -1.0)
    vals = [r[axis] for r in win]
    peak = max(vals) if sign > 0 else min(vals)
    seg = [(r[0], r[axis]) for r in win]
    window_s = win[-1][0] - win[0][0]

    settle, reent, sat = settle_after_last_excursion(seg, final, band)
    tail_m = {"overshoot_m": round(max((peak - final) * sign, 0.0), 3), "settle_s": _scaled(settle, 1.0),
              "band_reentries": reent, "saturated": sat}

    goal = None
    if delta is not None:
        goal_m = start + delta
        g = {"goal_m": round(goal_m, 3), "overshoot_m": round(max((peak - goal_m) * sign, 0.0), 3),
             "steady_state_error_m": round((final - goal_m) * sign, 3)}
        for b, tag in ((0.1, "0p1"), (0.05, "0p05"), (0.02, "0p02")):
            s, r, sat_b = settle_after_last_excursion(seg, goal_m, b)
            g[f"settle_{tag}_s"] = _scaled(s, 1.0)
            g[f"reentries_{tag}"] = r
            if tag == "0p1":
                g["saturated_0p1"] = sat_b
        goal = g

    vt = velocity_tracking(win, cmd, axis, time_scale)
    ramp = event["ramp_end"] - onset
    veh = {"settle_s": _scaled(settle, time_scale), "commander_ramp_s": round(ramp * time_scale, 3),
           "settle_0p1_s": _scaled(goal["settle_0p1_s"], time_scale) if goal else None,
           "settle_0p05_s": _scaled(goal["settle_0p05_s"], time_scale) if goal else None,
           "settle_0p02_s": _scaled(goal["settle_0p02_s"], time_scale) if goal else None,
           "lag_s": _scaled(vt["lag_s"], time_scale)}
    return {**head,
            "moved_most_axis": AXIS_NAMES[moved_most], "axis_mismatch": moved_most != axis,
            "onset_s_after_arming": None,  # filled by analyse()
            "commanded_peak_speed_mps": round(abs(event["peak_v"]), 3), "commanded_delta_m": delta,
            "commander_ramp_s": round(ramp, 3),
            "start_m": round(start, 3), "final_m": round(final, 3), "peak_m": round(peak, 3),
            "moved_m": round(final - start, 3), "samples": len(win), "window_s": round(window_s, 3),
            "tail": tail_m, "goal": goal, "velocity_tracking": vt, "vehicle_time": veh}


def summarise_steps(events) -> dict:
    """Per commanded axis over the step_* events: n, names, max/median goal settle (+/-0.1 m, vehicle s),
    max overshoot (tail or goal), max |steady-state error|, max re-entries at +/-0.1, mismatch/saturation flags."""
    out: dict = {}
    for ax in ("x", "y", "z"):
        steps = [e for e in events if e["name"].startswith(f"step_{ax}_") and "skipped" not in e]
        if not steps:
            continue
        settles = [e["vehicle_time"]["settle_0p1_s"] for e in steps if e["vehicle_time"]["settle_0p1_s"] is not None]
        out[ax] = {
            "n": len(steps),
            "names": [e["name"] for e in steps],
            "settle_0p1_max_veh_s": max(settles) if settles else None,
            "settle_0p1_median_veh_s": round(statistics.median(settles), 3) if settles else None,
            "overshoot_max_m": max(max(e["tail"]["overshoot_m"], e["goal"]["overshoot_m"]) for e in steps),
            "steady_state_error_max_m": max(abs(e["goal"]["steady_state_error_m"]) for e in steps),
            "reentries_0p1_max": max(e["goal"]["reentries_0p1"] for e in steps),
            "any_axis_mismatch": any(e["axis_mismatch"] for e in steps),
            "any_saturated": any(e["goal"]["saturated_0p1"] or e["tail"]["saturated"] for e in steps),
        }
    return out


# ----------------------------------------------------------------------------- top level
def analyse(odom, cmd, state, step_delta_m=1.0, px4_arm_times=None, drone="drone_1") -> dict:
    if not odom or not cmd:
        raise ValueError("odometry and command CSVs must both be non-empty")
    arms, disarms, armed_end = arming_events(state)
    t_arm = arms[0] if arms else cmd[0][0]  # no arm edge in the bag: count the takeoff phase from the first command
    bag_interval = None
    if arms:
        later = [d for d in disarms if d > arms[0]]
        if later:
            bag_interval = later[0] - arms[0]

    time_scale, src, px4_interval = 1.0, "assumed 1.0 (no px4_arm_times)", None
    if px4_arm_times is not None:
        px4_interval = px4_arm_times["disarm_s"] - px4_arm_times["arm_s"]
        if bag_interval is None:
            src = "assumed 1.0 (bag has no arm->disarm pair)"
        else:
            time_scale = compute_time_scale(px4_arm_times["arm_s"], px4_arm_times["disarm_s"], arms[0], arms[0] + bag_interval)
            src = f"px4_arm_times.txt (sysid {px4_arm_times.get('sysid')})"

    events = name_events(detect_events(cmd), t_arm, odom, step_delta_m=step_delta_m)
    measured, skipped = [], []
    for i, e in enumerate(events):
        m = measure_event(e, odom, cmd, event_window_end(events, i), time_scale=time_scale)
        if "skipped" in m:
            skipped.append(m)
            continue
        m["onset_s_after_arming"] = round(e["onset"] - arms[0], 3) if arms else None
        measured.append(m)

    duration = odom[-1][0] - odom[0][0]
    return {
        "drone": drone,
        "odom_msgs": len(odom), "cmd_msgs": len(cmd),
        "duration_s": round(duration, 2),
        "odom_rate_hz": round((len(odom) - 1) / duration, 2) if duration > 0 else None,
        "armed_at_s": [round(a, 3) for a in arms], "disarmed_at_s": [round(d, 3) for d in disarms],
        "armed_at_end": armed_end,
        "time_scale": round(time_scale, 4), "time_scale_source": src,
        "px4_arm_interval_s": round(px4_interval, 3) if px4_interval is not None else None,
        "bag_arm_interval_s": round(bag_interval, 3) if bag_interval is not None else None,
        "events": measured, "skipped_events": skipped,
        "steps": summarise_steps(measured),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 usage="%(prog)s --odom F --cmd F --state F [--px4-arm-times F] [--step-delta 1.0] [--drone drone_1] -o OUT.json")
    ap.add_argument("--odom", required=True)
    ap.add_argument("--cmd", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--px4-arm-times", default=None)
    ap.add_argument("--step-delta", type=float, default=1.0)
    ap.add_argument("--drone", default="drone_1")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args(argv)
    res = analyse(load_xyz_csv(a.odom), load_xyz_csv(a.cmd), load_state_csv(a.state),
                  step_delta_m=a.step_delta, px4_arm_times=load_px4_arm_times(a.px4_arm_times), drone=a.drone)
    pathlib.Path(a.out).write_text(json.dumps(res, indent=1) + "\n")
    print(f"{a.out}: {len(res['events'])} events, time_scale {res['time_scale']} ({res['time_scale_source']})")
    for ax, s in res["steps"].items():
        print(f"  step {ax}: n={s['n']} settle0p1 max {s['settle_0p1_max_veh_s']} veh-s, overshoot max {s['overshoot_max_m']} m, "
              f"reentries max {s['reentries_0p1_max']}, mismatch {s['any_axis_mismatch']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
