#!/usr/bin/env python3
"""bag_recompute — recompute the live metrics CSV from the recorded mcap bag. Sim-only.

Runs INSIDE the robot container (rosbag2_py, rclpy, message packages; Python 3.12), docker-cp'd next to
metrics_core.py and the test's metrics.py:
    python3 bag_recompute.py <bag_dir> --test-dir DIR --meta-from LIVE_CSV -o OUT_CSV
        [--status-topic ...] [--cbf-topic ...] [--odom-template ...]
Offsets, params and t0_unix come from the LIVE CSV header (--meta-from) and are never re-fetched. The bag is
replayed in bag order (odometry of every drone, the cbf topic, the status topic) through the same
metrics_core.Tracker; one row per trigger-drone odometry header.stamp (t_s = stamp - t0_unix). Output has the
live schema and meta plus source=bag:<dir>. Prints one JSON line
{"rows": n, "odom_msgs": {drone: n}, "status_msgs": n, "cbf_msgs": n}.
Exit codes: 0 ok, 1 error (unreadable bag/meta, or no trigger odometry in the bag, message on stderr).
"""
import argparse
import importlib.util
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metrics_core as M  # noqa: E402


def fail(msg):
    print("bag_recompute: " + msg, file=sys.stderr)
    sys.exit(1)


def parse_meta_value(v):
    if "," in v:
        return [float(x) for x in v.split(",")]
    try:
        return float(v)
    except ValueError:
        return v


def main():
    ap = argparse.ArgumentParser(description="recompute metrics CSV from a bag (container only)")
    ap.add_argument("bag_dir")
    ap.add_argument("--test-dir", required=True)
    ap.add_argument("--meta-from", required=True, help="live metrics.csv whose header holds offsets/params/t0_unix")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--status-topic", default="/svg/commander_status")
    ap.add_argument("--cbf-topic", default="/svg/cbf_active")
    ap.add_argument("--odom-template", default="/{name}/odometry_conversion/odometry")
    args = ap.parse_args()

    try:
        meta, _, _ = M.read_metrics_csv(args.meta_from)
    except (OSError, M.MetricsCsvError) as e:
        fail("cannot read live CSV header: %s" % e)
    path = os.path.join(args.test_dir, "metrics.py")
    if not os.path.isfile(path):
        fail("no metrics.py in %s" % args.test_dir)
    sys.path.insert(0, args.test_dir)
    spec = importlib.util.spec_from_file_location("svg_test_metrics", path)
    T = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(T)
    series, trigger = list(T.SERIES), T.TRIGGER
    drones = meta.get("drones", "").split(",") if meta.get("drones") else list(T.DRONES)
    try:
        offsets = M.meta_offsets(meta, drones)
        t0 = float(meta["t0_unix"])
        absent = [n for n in T.PARAMS if n != "drone_position_offsets" and n not in meta]
        if absent:
            fail("live CSV header lacks param(s) named in PARAMS: %s" % ", ".join(absent))
        params = {n: parse_meta_value(meta[n]) for n in T.PARAMS if n in meta}
    except (KeyError, ValueError) as e:
        fail("live CSV header incomplete: %r" % (e,))
    params.pop("drone_position_offsets", None)

    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    reader = rosbag2_py.SequentialReader()
    try:
        reader.open(rosbag2_py.StorageOptions(uri=args.bag_dir, storage_id="mcap"), rosbag2_py.ConverterOptions("", ""))
        types = {t.name: get_message(t.type) for t in reader.get_all_topics_and_types()}
    except Exception as e:  # rosbag2 raises plain RuntimeError for a missing/corrupt bag
        fail("cannot open bag %s: %s" % (args.bag_dir, e))
    odom_topics = {args.odom_template.format(name=d): d for d in drones}

    tr = M.Tracker(drones, offsets, params, series)
    columns = M.csv_columns(series)
    counts = {d: 0 for d in drones}
    n_status = n_cbf = 0
    lines = []
    while reader.has_next():
        topic, data, _ = reader.read_next()
        if topic in odom_topics:
            d = odom_topics[topic]
            m = deserialize_message(data, types[topic])
            t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9  # header.stamp
            p, v = m.pose.pose.position, m.twist.twist.linear
            tr.update_odom(d, t, (p.x, p.y, p.z), (v.x, v.y, v.z))
            counts[d] += 1
            if d == trigger and t >= t0:
                row = tr.row(t)
                lines.append(M.format_row(t - t0, row["phase"], row, columns))
        elif topic == args.status_topic:
            try:
                tr.update_status(json.loads(deserialize_message(data, types[topic]).data))
                n_status += 1
            except ValueError:
                pass
        elif topic == args.cbf_topic:
            tr.update_cbf(deserialize_message(data, types[topic]).data)
            n_cbf += 1
    if counts.get(trigger, 0) == 0:
        fail("no trigger odometry on %s in %s" % (args.odom_template.format(name=trigger), args.bag_dir))
    meta["source"] = "bag:" + args.bag_dir
    with open(args.out, "w") as fh:
        fh.write(M.csv_header(series, meta))
        fh.write("\n".join(lines) + ("\n" if lines else ""))
    print(json.dumps({"rows": len(lines), "odom_msgs": counts, "status_msgs": n_status, "cbf_msgs": n_cbf}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
