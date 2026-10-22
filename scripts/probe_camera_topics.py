#!/usr/bin/env python3
"""Probe the sim stereo topics: rate, stamps, camera_info K/P, baseline (run in the exploration container)."""
import sys, time, numpy as np, rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image, CameraInfo
d = sys.argv[1] if len(sys.argv) > 1 else "drone_1"
base = f"/{d}/sensors/front_stereo"
rclpy.init(); n = Node("probe"); qos = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)
st = {"L": [], "R": [], "infoL": None, "infoR": None}
n.create_subscription(Image, f"{base}/left/image_rect", lambda m: st["L"].append(m.header.stamp.sec + m.header.stamp.nanosec*1e-9), qos)
n.create_subscription(Image, f"{base}/right/image_rect", lambda m: st["R"].append(m.header.stamp.sec + m.header.stamp.nanosec*1e-9), qos)
n.create_subscription(CameraInfo, f"{base}/left/camera_info", lambda m: st.__setitem__("infoL", m), qos)
n.create_subscription(CameraInfo, f"{base}/right/camera_info", lambda m: st.__setitem__("infoR", m), qos)
t0 = time.time()
while time.time() - t0 < 10: rclpy.spin_once(n, timeout_sec=0.1)
for k in "LR":
    s = np.array(st[k]); print(f"{k}: {len(s)} frames in 10 s wall; stamp span {s[-1]-s[0]:.2f} s sim; mean dt {np.diff(s).mean()*1e3:.1f} ms; stamps strictly increasing: {bool(np.all(np.diff(s) > 0))}" if len(s) > 1 else f"{k}: {len(s)} frames")
if st["L"] and st["R"]:
    L, R = np.array(st["L"]), np.array(st["R"]); m = min(len(L), len(R)); print(f"L-R stamp mismatch max {np.abs(L[:m]-R[:m]).max()*1e3:.3f} ms")
for k in ("infoL", "infoR"):
    i = st[k]
    if i is None: print(k, "none"); continue
    K = np.array(i.k).reshape(3,3); P = np.array(i.p).reshape(3,4)
    print(f"{k}: {i.width}x{i.height} frame_id={i.header.frame_id} fx={K[0,0]:.3f} fy={K[1,1]:.3f} cx={K[0,2]:.3f} cy={K[1,2]:.3f} P[0,3]={P[0,3]:.4f} -> baseline={-P[0,3]/P[0,0] if P[0,0] else float('nan'):.4f} m  distortion={i.distortion_model} d={list(i.d)[:5]}")
rclpy.shutdown()
