#!/usr/bin/env python3
"""Print the PX4 arm/disarm times of a ulog (vehicle-time scale for the step report).

Usage:
    hover_step_timescale.py <ulog>

Output (one line on stdout, PX4 boot-time seconds):
    arm_s=<.6f> disarm_s=<.6f> interval_s=<.6f> source=<basename> sysid=<n>

Exit codes: 0 = ok, 2 = usage / unreadable ulog, 3 = no arm->disarm pair in vehicle_status.

pyulog is imported inside main() only: the host python has no pyulog, the
isaac-sim container's does. Consumed by tools/hover_step_report.py
(load_px4_arm_times, same tokens) and tools/sim_hover_step_run.sh (collect).
"""
import os
import sys

ARMING_STATE_DISARMED = 1  # PX4 v1.14 vehicle_status.arming_state
ARMING_STATE_ARMED = 2


def arming_transitions(timestamps_us, arming_state):
    """First 1->2 (arm) and the first subsequent 2->1 (disarm) transition, in seconds.

    Returns (arm_s, disarm_s); either may be None when the transition never happens.
    """
    arm_s = None
    disarm_s = None
    prev = None
    for ts, st in zip(timestamps_us, arming_state):
        st = int(st)
        if prev is not None:
            if arm_s is None and prev == ARMING_STATE_DISARMED and st == ARMING_STATE_ARMED:
                arm_s = ts / 1e6
            elif arm_s is not None and prev == ARMING_STATE_ARMED and st == ARMING_STATE_DISARMED:
                disarm_s = ts / 1e6
                break
        prev = st
    return arm_s, disarm_s


def format_line(arm_s, disarm_s, source, sysid):
    return (f"arm_s={arm_s:.6f} disarm_s={disarm_s:.6f} "
            f"interval_s={disarm_s - arm_s:.6f} "
            f"source={os.path.basename(source)} sysid={sysid}")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if len(argv) != 1:
        print("usage: hover_step_timescale.py <ulog>", file=sys.stderr)
        return 2
    path = argv[0]
    from pyulog import ULog  # container-only dependency
    try:
        ulog = ULog(path, message_name_filter_list=["vehicle_status"])
    except Exception as exc:  # unreadable / not a ulog
        print(f"hover_step_timescale: cannot read {path}: {exc}", file=sys.stderr)
        return 2
    sysid = ulog.initial_parameters.get("MAV_SYS_ID", "?")
    status = next((d for d in ulog.data_list if d.name == "vehicle_status"), None)
    if status is None:
        print(f"hover_step_timescale: no vehicle_status in {path}", file=sys.stderr)
        return 3
    arm_s, disarm_s = arming_transitions(status.data["timestamp"], status.data["arming_state"])
    if arm_s is None or disarm_s is None:
        print(f"hover_step_timescale: no arm->disarm pair in {path} "
              f"(arm_s={arm_s} disarm_s={disarm_s})", file=sys.stderr)
        return 3
    print(format_line(arm_s, disarm_s, path, sysid))
    return 0


if __name__ == "__main__":
    sys.exit(main())
