#!/usr/bin/env python3
"""PX4 ulog -> one vehicle-time yaw CSV for tools/live/yaw_core.py (SIM ONLY, CLAUDE.md iron rule 9).

Usage:
    ulog_yaw_dump.py <ulog> -o <csv> [--params-out <txt>]

CSV: `# key=value` header (source, sysid, MC_YAW_P, MC_YAWRATE_P/I/D/K from initial_parameters, arm_s, disarm_s,
missing_topics) then the columns
    t_s,heading_ned_deg,x_ned,y_ned,yaw_rate_dps,ff_dps,yawspeed_sp_dps,yaw_sp_ned_deg
on the vehicle_local_position clock (~84 Hz in this SITL); t_s = timestamp / 1e6 = PX4 vehicle seconds since boot.
  heading_ned_deg  vehicle_local_position.heading (NED, wrapped +-180)
  yaw_rate_dps     vehicle_angular_velocity.xyz[2] (body z, FRD)
  ff_dps           vehicle_attitude_setpoint.yaw_sp_move_rate
  yawspeed_sp_dps  trajectory_setpoint.yawspeed
  yaw_sp_ned_deg   yaw of vehicle_attitude_setpoint.q_d (w, x, y, z)
Slower topics are sample-and-hold interpolated (previous value) onto the clock; NaN before a topic's first sample.
--params-out: `t_s name value` lines (vehicle time) of ULog.changed_parameters, filtered to MC_YAW*.

Exit codes: 0 ok, 2 usage / unreadable ulog, 3 a required topic missing (named on stderr), 4 pyulog not installed
(tools/sim.sh then retries inside the isaac-sim container). pyulog is imported inside main() only, so the host
unit tests import the pure helpers (to_deg, hold_onto, yaw_of_qd) without it.
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.dirname(HERE)):          # tools/ (repo) or the same dir (/tmp in the isaac-sim container)
    if _p not in sys.path:
        sys.path.insert(0, _p)

COLUMNS = "t_s,heading_ned_deg,x_ned,y_ned,yaw_rate_dps,ff_dps,yawspeed_sp_dps,yaw_sp_ned_deg"
GAIN_KEYS = ("MC_YAW_P", "MC_YAWRATE_P", "MC_YAWRATE_I", "MC_YAWRATE_D", "MC_YAWRATE_K")
REQUIRED = ("vehicle_local_position", "vehicle_angular_velocity")
SETPOINTS = ("vehicle_attitude_setpoint", "trajectory_setpoint")      # at least one: the pulse marker (U3)
TOPICS = REQUIRED + SETPOINTS + ("vehicle_status",)


def to_deg(rad):
    return np.degrees(np.asarray(rad, dtype=float))


def hold_onto(clock_s, t_src_s, v_src):
    """Value of the last source sample at or before each clock time; NaN before the first source sample."""
    clock_s = np.asarray(clock_s, dtype=float); t_src_s = np.asarray(t_src_s, dtype=float); v_src = np.asarray(v_src, dtype=float)
    out = np.full(len(clock_s), np.nan)
    if len(t_src_s) == 0:
        return out
    idx = np.searchsorted(t_src_s, clock_s, side="right") - 1
    ok = idx >= 0
    out[ok] = v_src[idx[ok]]
    return out


def yaw_of_qd(w, x, y, z):
    """Yaw (deg) of a PX4 quaternion q = (w, x, y, z) in NED; works on scalars and arrays."""
    w, x, y, z = (np.asarray(a, dtype=float) for a in (w, x, y, z))
    r = np.degrees(np.arctan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))
    return float(r) if r.ndim == 0 else r


def _fmt(v):
    return "nan" if v is None or (isinstance(v, float) and math.isnan(v)) else ("%.6f" % v)


def build(ulog):
    """(meta dict, rows array, missing optional topics) from an open pyulog.ULog; raises KeyError(topic) if required."""
    data = {}
    for d in ulog.data_list:
        if d.name in TOPICS and d.multi_id == 0:
            data[d.name] = d.data
    for name in REQUIRED:
        if name not in data:
            raise KeyError(name)
    if not any(s in data for s in SETPOINTS):
        raise KeyError(" or ".join(SETPOINTS))
    lp = data["vehicle_local_position"]
    clock = lp["timestamp"] / 1e6
    nan = np.full(len(clock), np.nan)
    av = data["vehicle_angular_velocity"]
    rate = hold_onto(clock, av["timestamp"] / 1e6, to_deg(av["xyz[2]"]))
    missing = [s for s in SETPOINTS if s not in data]
    if "vehicle_attitude_setpoint" in data:
        at = data["vehicle_attitude_setpoint"]; ta = at["timestamp"] / 1e6
        ff = hold_onto(clock, ta, to_deg(at["yaw_sp_move_rate"]))
        ysp = hold_onto(clock, ta, yaw_of_qd(at["q_d[0]"], at["q_d[1]"], at["q_d[2]"], at["q_d[3]"]))
    else:
        ff, ysp = nan, nan
    if "trajectory_setpoint" in data:
        ts = data["trajectory_setpoint"]
        sp = hold_onto(clock, ts["timestamp"] / 1e6, to_deg(ts["yawspeed"]))
    else:
        sp = nan
    rows = np.column_stack([clock, to_deg(lp["heading"]), lp["x"], lp["y"], rate, ff, sp, ysp])
    p = ulog.initial_parameters
    meta = {"source": None, "sysid": p.get("MAV_SYS_ID", "?")}
    for k in GAIN_KEYS:
        meta[k] = p.get(k)
    arm_s = disarm_s = None
    if "vehicle_status" in data:
        try:
            from hover_step_timescale import arming_transitions   # by import, never duplicated
            arm_s, disarm_s = arming_transitions(data["vehicle_status"]["timestamp"], data["vehicle_status"]["arming_state"])
        except ImportError:
            print("ulog_yaw_dump: hover_step_timescale.py not importable — arm_s/disarm_s = nan", file=sys.stderr)
    else:
        missing.append("vehicle_status")
    meta["arm_s"], meta["disarm_s"] = _fmt(arm_s), _fmt(disarm_s)
    meta["missing_topics"] = ",".join(missing) or "none"
    return meta, rows, missing


def param_changes(ulog):
    return [(ts / 1e6, name, val) for ts, name, val in ulog.changed_parameters if name.startswith("MC_YAW")]


def main(argv=None):
    ap = argparse.ArgumentParser(description="PX4 ulog -> vehicle-time yaw CSV (sim only)")
    ap.add_argument("ulog"); ap.add_argument("-o", "--out", required=True); ap.add_argument("--params-out")
    a = ap.parse_args(argv)
    try:
        from pyulog import ULog
    except ImportError:
        print("ulog_yaw_dump: pyulog not installed on this python (pip install pyulog)", file=sys.stderr)
        return 4
    try:
        ulog = ULog(a.ulog, message_name_filter_list=list(TOPICS))
    except Exception as exc:  # unreadable / not a ulog
        print("ulog_yaw_dump: cannot read %s: %s" % (a.ulog, exc), file=sys.stderr)
        return 2
    try:
        meta, rows, missing = build(ulog)
    except KeyError as exc:
        print("ulog_yaw_dump: required topic missing in %s: %s" % (a.ulog, exc.args[0]), file=sys.stderr)
        return 3
    meta["source"] = os.path.basename(a.ulog)
    tmp = a.out + ".tmp"
    with open(tmp, "w") as fh:
        for k, v in meta.items():
            fh.write("# %s=%s\n" % (k, v))
        fh.write(COLUMNS + "\n")
        for r in rows:
            fh.write(",".join(_fmt(float(v)) for v in r) + "\n")
    os.replace(tmp, a.out)                     # never a half-written CSV under the final name
    if a.params_out:
        with open(a.params_out, "w") as fh:
            fh.write("# MC_YAW* parameter changes of %s, t_s = PX4 vehicle time (s since boot); sim only\n" % meta["source"])
            for ts, name, val in param_changes(ulog):
                fh.write("%.6f %s %s\n" % (ts, name, val))
    if missing:
        print("ulog_yaw_dump: optional topics missing: %s (columns NaN)" % ",".join(missing), file=sys.stderr)
    print("ulog_yaw_dump: %d rows -> %s" % (len(rows), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
