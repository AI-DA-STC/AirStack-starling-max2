#!/usr/bin/env python3
"""metrics_node — live metrics for the SVG test driver. Sim-only: nothing here has seen a real flight.

Runs INSIDE the robot container only (rclpy, std_msgs, nav_msgs; Python 3.12). The driver docker-cps this
file, metrics_core.py and the test's metrics.py into /tmp/svg_test/ and starts it:
    python3 metrics_node.py --test-dir DIR --csv PATH [--publish-hz 10] [--commander /swarm_commander]
        [--status-topic /svg/commander_status] [--cbf-topic /svg/cbf_active]
        [--odom-template /{name}/odometry_conversion/odometry]
DIR/metrics.py defines SERIES, PARAMS (commander parameter names, read ONCE), REFERENCES (name -> number or
callable(params)), TRIGGER, DRONES. All formulas live in metrics_core.

Start-up: `ros2 param get` for every PARAMS entry (and drone_position_offsets), then wait <= 30 s for one status
message and one odometry per drone, then offset_sanity (odometry + offset vs the commander's own position).
Any failure prints `metrics_node: REFUSED — <reason>` and exits 4.

Running: one CSV row per trigger-drone odometry message (t_s = header.stamp - t0), using the latest pose of the
others; a timer at --publish-hz publishes std_msgs/Float64 on /svg/test/<column> (every column but t_s/phase), on
/svg/test/<reference>, and std_msgs/Int32 on /svg/test/phase; a 1 Hz stdout line
`[t=  12.0 s] phase=2 min_d=1.432 run_min=1.213 cbf=drone_1,drone_3 emerg=0`.

CSV schema: `# key=value` meta lines (sorted; every param, offsets, refs=<name>:<value>;..., t0_unix, trigger,
drones, started), then the column line from metrics_core.csv_header, then one row per trigger message (NaN = "nan").

Exit codes: 0 on SIGINT/SIGTERM (CSV flushed and closed), 4 refused to start, 2 bad arguments/test dir.
"""
import argparse
import datetime
import importlib.util
import json
import math
import os
import signal
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metrics_core as M  # noqa: E402

REFUSED_RC = 4
OFFSETS_PARAM = "drone_position_offsets"


def refuse(reason):
    print("metrics_node: REFUSED — %s" % reason, flush=True)
    sys.exit(REFUSED_RC)


def load_test(test_dir):
    path = os.path.join(test_dir, "metrics.py")
    if not os.path.isfile(path):
        print("metrics_node: no metrics.py in %s" % test_dir, flush=True)
        sys.exit(2)
    spec = importlib.util.spec_from_file_location("svg_test_metrics", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def get_param(commander, name):
    try:
        r = subprocess.run(["ros2", "param", "get", commander, name], capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        refuse("`ros2 param get %s %s` timed out (is %s running?)" % (commander, name, commander))
    out = (r.stdout + r.stderr).strip()
    if r.returncode != 0 or not out or "not found" in out.lower() or "unable" in out.lower() or "could not" in out.lower():
        refuse("cannot read %s %s: no commander up? (%s)" % (commander, name, out.replace("\n", " ")[:160]))
    try:
        return M.parse_param_array(out) if "[" in out else M.parse_param_scalar(out)
    except ValueError as e:
        refuse("cannot parse %s %s: %s" % (commander, name, e))


def main():
    ap = argparse.ArgumentParser(description="live metrics node (container only)")
    ap.add_argument("--test-dir", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--publish-hz", type=float, default=10.0)
    ap.add_argument("--commander", default="/swarm_commander")
    ap.add_argument("--status-topic", default="/svg/commander_status")
    ap.add_argument("--cbf-topic", default="/svg/cbf_active")
    ap.add_argument("--odom-template", default="/{name}/odometry_conversion/odometry")
    args = ap.parse_args()

    sys.path.insert(0, args.test_dir)
    T = load_test(args.test_dir)
    drones, trigger = list(T.DRONES), T.TRIGGER
    series = list(T.SERIES)
    names = list(T.PARAMS)  # a list of names (a dict of stand-in values is accepted: its keys)
    if OFFSETS_PARAM not in names:
        names.append(OFFSETS_PARAM)

    params = {n: get_param(args.commander, n) for n in names}  # read ONCE; refuses (rc 4) when no commander is up
    try:
        offsets = M.offsets_by_drone(params[OFFSETS_PARAM], drones)
    except ValueError as e:
        refuse(str(e))
    calc_params = {k: v for k, v in params.items() if k != OFFSETS_PARAM}

    import rclpy
    from nav_msgs.msg import Odometry
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.qos import qos_profile_sensor_data
    from rclpy.signals import SignalHandlerOptions
    from std_msgs.msg import Float64, Int32, String

    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = rclpy.create_node("svg_metrics_node")
    state = {"raw": {}, "status": None, "tracker": None, "t0": None, "fh": None, "last": None,
             "cbf": "", "stop": False, "t_last": 0.0}
    columns = M.csv_columns(series)
    pub_cols = [c for c in columns if c not in ("t_s", "phase")]

    def on_odom(drone):
        def cb(msg):
            t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9  # header.stamp
            p, v = msg.pose.pose.position, msg.twist.twist.linear
            xyz, vel = (p.x, p.y, p.z), (v.x, v.y, v.z)
            state["raw"][drone] = (t, xyz, vel)
            tr = state["tracker"]
            if tr is None:
                return
            tr.update_odom(drone, t, xyz, vel)
            if drone == trigger and t >= state["t0"]:
                emit_row(t)
        return cb

    def emit_row(t):
        tr = state["tracker"]
        row = tr.row(t)
        ts = t - state["t0"]
        state["last"], state["t_last"] = row, ts
        state["fh"].write(M.format_row(ts, row["phase"], row, columns) + "\n")

    def on_status(msg):
        try:
            st = json.loads(msg.data)
        except ValueError:
            return
        state["status"] = st
        if state["tracker"] is not None:
            state["tracker"].update_status(st)

    def on_cbf(msg):
        state["cbf"] = msg.data
        if state["tracker"] is not None:
            state["tracker"].update_cbf(msg.data)

    for d in drones:
        node.create_subscription(Odometry, args.odom_template.format(name=d), on_odom(d), qos_profile_sensor_data)
    node.create_subscription(String, args.status_topic, on_status, 10)
    node.create_subscription(String, args.cbf_topic, on_cbf, 10)

    # ---- wait for one status + one odometry per drone
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline and (state["status"] is None or any(d not in state["raw"] for d in drones)):
        rclpy.spin_once(node, timeout_sec=0.2)
    if state["status"] is None:
        refuse("no message on %s within 30 s (is the commander publishing status?)" % args.status_topic)
    missing = [d for d in drones if d not in state["raw"]]
    if missing:
        refuse("no odometry within 30 s from %s (%s)" % (", ".join(missing), args.odom_template))
    spos = {d["name"]: d.get("position") for d in state["status"].get("drones", []) if d.get("position")}
    errs = M.offset_sanity(spos, {d: state["raw"][d][1] for d in drones}, offsets)
    if errs:
        refuse("offset sanity failed: " + "; ".join(errs))

    # ---- tracker, header, first state
    t0 = state["raw"][trigger][0]
    state["t0"] = t0
    refs = {}
    for k, v in getattr(T, "REFERENCES", {}).items():
        refs[k] = float(v(calc_params)) if callable(v) else float(v)
    meta = dict(params)
    meta.update({"offsets": [x for d in drones for x in offsets[d]],
                 "refs": ";".join("%s:%s" % (k, refs[k]) for k in refs),
                 "t0_unix": repr(t0), "trigger": trigger, "drones": ",".join(drones),
                 "started": datetime.datetime.now().astimezone().isoformat(timespec="seconds")})
    tr = M.Tracker(drones, offsets, calc_params, series)
    tr.update_status(state["status"])
    tr.update_cbf(state["cbf"])
    for d in drones:
        t, xyz, vel = state["raw"][d]
        tr.update_odom(d, t, xyz, vel)
    state["tracker"] = tr
    state["fh"] = open(args.csv, "w")
    state["fh"].write(M.csv_header(series, meta))
    state["fh"].flush()
    print("metrics_node: ready offsets=%s" % ",".join("%g" % x for d in drones for x in offsets[d]), flush=True)

    # ---- publishers and timers
    pubs = {c: node.create_publisher(Float64, "/svg/test/" + c, 10) for c in pub_cols}
    ref_pubs = {k: node.create_publisher(Float64, "/svg/test/" + k, 10) for k in refs}
    phase_pub = node.create_publisher(Int32, "/svg/test/phase", 10)

    def publish():
        row = state["last"]
        if row is None:
            return
        for c, p in pubs.items():
            p.publish(Float64(data=float(row.get(c, math.nan))))
        for k, p in ref_pubs.items():
            p.publish(Float64(data=refs[k]))
        phase_pub.publish(Int32(data=int(row["phase"])))

    run_name = next((s.name for s in series if s.running_min), None)

    def fmt(v):
        return "nan" if v is None or math.isnan(v) else "%.3f" % v

    def status_line():
        row = state["last"]
        if row is None:
            return
        md = row.get(run_name) if run_name else None
        rm = row.get(run_name + "_running") if run_name else None
        emerg = row.get("emergency", 1.0 if (state["status"] or {}).get("cbf", {}).get("emergency") else 0.0)
        print("[t=%6.1f s] phase=%d min_d=%s run_min=%s cbf=%s emerg=%d" % (
            state["t_last"], int(row["phase"]), fmt(md), fmt(rm), state["cbf"], int(emerg)), flush=True)
        state["fh"].flush()

    node.create_timer(1.0 / args.publish_hz, publish)
    node.create_timer(1.0, status_line)

    def stop(*_):
        state["stop"] = True
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    ex = SingleThreadedExecutor()
    ex.add_node(node)
    try:
        while not state["stop"]:
            ex.spin_once(timeout_sec=0.1)
    finally:
        state["fh"].flush()
        state["fh"].close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
