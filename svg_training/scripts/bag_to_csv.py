#!/usr/bin/env python3
"""Dump the topics S1 needs from a rosbag2 (mcap) bag to CSV. Runs inside CMU's robot image (rosbag2_py), see extract_bag.sh.

Usage: bag_to_csv.py <bag_dir> <out_dir> [--drone drone_1] [--teleop-topic T] [--velocity-topic T] [--odom-topic T] [--status-topic T] [--bag-label PATH]
Writes into <out_dir> (must be absent or empty, else exit 1):
    teleop_command.csv, velocity_command.csv   t_wall_s,vx,vy,vz,yaw_rate   (TwistStamped: linear xyz m/s, angular z rad/s)
    odometry.csv                               t_wall_s,x,y,z,vx,vy,vz,qw,qx,qy,qz   (Odometry: position m, twist.linear m/s, quaternion wxyz)
    commander_status.csv                       t_wall_s,data   (std_msgs/String)
    manifest.json                              bag path, rows per topic, sha256 of this script
t_wall_s is the bag's receive time in seconds (float, wall clock). A topic absent from the bag gives no file and a printed note.

SIMULATOR ROUTE: describes the AirStack simulator, not the training model; see docs/S1_RESULTS.md
(STANDARDS §5 rule 10: the training model comes from real flight logs)."""
import argparse
import csv
import hashlib
import json
import pathlib
import sys

VERSION_SHA256 = hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()

TWIST_COLS = ["t_wall_s", "vx", "vy", "vz", "yaw_rate"]
ODOM_COLS = ["t_wall_s", "x", "y", "z", "vx", "vy", "vz", "qw", "qx", "qy", "qz"]
STATUS_COLS = ["t_wall_s", "data"]


def twist_row(msg, t):
    """(t_wall_s, vx, vy, vz, yaw_rate) from a TwistStamped-like message."""
    li, an = msg.twist.linear, msg.twist.angular
    return (t, li.x, li.y, li.z, an.z)


def odom_row(msg, t):
    """(t_wall_s, x, y, z, vx, vy, vz, qw, qx, qy, qz) from an Odometry-like message."""
    p, q, v = msg.pose.pose.position, msg.pose.pose.orientation, msg.twist.twist.linear
    return (t, p.x, p.y, p.z, v.x, v.y, v.z, q.w, q.x, q.y, q.z)


def status_row(msg, t):
    return (t, msg.data)


def read_bag(bag, wanted):
    """Yield (topic, message, t_wall_s) for topics in `wanted`, in bag order. Needs rosbag2_py (robot image)."""
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=bag, storage_id="mcap"), rosbag2_py.ConverterOptions("", ""))
    types = {t.name: get_message(t.type) for t in r.get_all_topics_and_types() if t.name in wanted}
    while r.has_next():
        topic, data, t_ns = r.read_next()
        if topic in types:
            yield topic, deserialize_message(data, types[topic]), t_ns / 1e9


def main(argv=None, reader=read_bag):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bag_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--bag-label", help="bag path to record in the manifest (default bag_dir; the wrapper passes the host path)")
    ap.add_argument("--drone", default="drone_1")
    ap.add_argument("--teleop-topic")
    ap.add_argument("--velocity-topic")
    ap.add_argument("--odom-topic")
    ap.add_argument("--status-topic", default="/svg/commander_status")
    a = ap.parse_args(argv)
    d = a.drone
    # name -> (topic, columns, row function)
    specs = {
        "teleop_command": (a.teleop_topic or f"/svg/{d}/teleop_command", TWIST_COLS, twist_row),
        "velocity_command": (a.velocity_topic or f"/{d}/interface/velocity_command", TWIST_COLS, twist_row),
        "odometry": (a.odom_topic or f"/{d}/odometry_conversion/odometry", ODOM_COLS, odom_row),
        "commander_status": (a.status_topic, STATUS_COLS, status_row),
    }
    out = pathlib.Path(a.out_dir)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        print(f"bag_to_csv: output folder {out} is not empty; refusing", file=sys.stderr)
        return 1
    out.mkdir(parents=True, exist_ok=True)

    by_topic = {topic: name for name, (topic, _, _) in specs.items()}
    rows = {name: [] for name in specs}
    for topic, msg, t in reader(a.bag_dir, by_topic):
        name = by_topic.get(topic)
        if name is not None:
            rows[name].append(specs[name][2](msg, t))

    for name, (topic, cols, _) in specs.items():
        if not rows[name]:
            print(f"note: no messages on {topic}; {name}.csv not written")
            continue
        with open(out / f"{name}.csv", "w", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(cols)
            w.writerows(rows[name])  # csv writes floats with repr: full precision
    manifest = {"bag": a.bag_label or a.bag_dir, "drone": d, "topics": {n: s[0] for n, s in specs.items()},
                "rows": {n: len(r) for n, r in rows.items()}, "script": "bag_to_csv.py", "script_sha256": VERSION_SHA256}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest["rows"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
