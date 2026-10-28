#!/usr/bin/env python3
"""Thin rosbag -> CSV dumper for the sim hover + step test (S5). Reader only; analysis lives in tools/hover_step_analyse.py.

Runs INSIDE the robot container (needs rosbag2_py + the message packages):
    docker cp tools/hover_step_bag.py airstack-robot-desktop-1:/tmp/
    docker exec airstack-robot-desktop-1 bash -ic 'python3 /tmp/hover_step_bag.py <bag_dir> <drone> <csv_prefix>'

Writes three CSVs, all with t_s = seconds since the bag's FIRST ODOMETRY message (receive/wall clock):
    <csv_prefix>_odom.csv   t_s,x,y,z          from /<drone>/odometry_conversion/odometry  pose.pose.position
    <csv_prefix>_cmd.csv    t_s,vx,vy,vz       from /<drone>/interface/mavros/setpoint_raw/local  .velocity
    <csv_prefix>_state.csv  t_s,armed,mode     from /<drone>/interface/mavros/state  (armed 0/1, mode unquoted)
and prints one JSON line: {"bag", "drone", "odom_msgs", "cmd_msgs", "state_msgs", "t0_unix", "csv": [three paths]}.
Exit 1 with a message on stderr if the bag holds no odometry for the drone."""
import json, sys
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

if len(sys.argv) != 4:
    sys.exit("usage: hover_step_bag.py <bag_dir> <drone> <csv_prefix>")
bag, drone, csv_prefix = sys.argv[1], sys.argv[2], sys.argv[3]
T_ODOM, T_SP, T_STATE = f"/{drone}/odometry_conversion/odometry", f"/{drone}/interface/mavros/setpoint_raw/local", f"/{drone}/interface/mavros/state"

r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=bag, storage_id="mcap"), rosbag2_py.ConverterOptions("", ""))
types = {t.name: get_message(t.type) for t in r.get_all_topics_and_types()}
odom, sp, state = [], [], []
while r.has_next():
    topic, data, t = r.read_next()
    if topic == T_ODOM:
        m = deserialize_message(data, types[topic]); p = m.pose.pose.position; odom.append((t / 1e9, p.x, p.y, p.z))
    elif topic == T_SP:
        m = deserialize_message(data, types[topic]); sp.append((t / 1e9, m.velocity.x, m.velocity.y, m.velocity.z))
    elif topic == T_STATE:
        m = deserialize_message(data, types[topic]); state.append((t / 1e9, bool(m.armed), m.mode))
if not odom:
    sys.exit(f"hover_step_bag.py: no odometry on {T_ODOM} in {bag}")
t0 = odom[0][0]

paths = [csv_prefix + "_odom.csv", csv_prefix + "_cmd.csv", csv_prefix + "_state.csv"]
with open(paths[0], "w") as f:
    f.write("t_s,x,y,z\n"); f.writelines(f"{t - t0:.3f},{x:.4f},{y:.4f},{z:.4f}\n" for t, x, y, z in odom)
with open(paths[1], "w") as f:
    f.write("t_s,vx,vy,vz\n"); f.writelines(f"{t - t0:.3f},{vx:.4f},{vy:.4f},{vz:.4f}\n" for t, vx, vy, vz in sp)
with open(paths[2], "w") as f:
    f.write("t_s,armed,mode\n"); f.writelines(f"{t - t0:.3f},{int(a)},{mode}\n" for t, a, mode in state)
print(json.dumps({"bag": bag, "drone": drone, "odom_msgs": len(odom), "cmd_msgs": len(sp), "state_msgs": len(state),
                  "t0_unix": t0, "csv": paths}))
