#!/usr/bin/env python3
"""Pass checks for one validation step (run INSIDE the exploration container, sim running).
Prints: sim real-time factor over 10 s, left-image rate, saves a frame, ORB corner count, sky (top rows) mean.
Usage: python3 scripts/sim_check.py [drone] [out.png]"""
import sys, time, json
import numpy as np, cv2, rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import Image

drone = sys.argv[1] if len(sys.argv) > 1 else "drone_1"
out = sys.argv[2] if len(sys.argv) > 2 else f"results/check_{drone}.png"
rclpy.init(); n = Node("sim_check"); clk = []; imgs = []; frame = {}
be = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)
n.create_subscription(Clock, "/clock", lambda m: clk.append((time.time(), m.clock.sec + m.clock.nanosec * 1e-9)), be)
def on_img(m):
    imgs.append(time.time())
    if frame: return
    ch = {"mono8": 1, "rgb8": 3, "bgr8": 3, "rgba8": 4, "bgra8": 4}.get(m.encoding, 3)
    a = np.frombuffer(m.data, np.uint8)
    a = a.reshape(m.height, m.step // ch, ch)[:, :m.width] if ch > 1 else a.reshape(m.height, m.step)[:, :m.width]
    if m.encoding == "rgb8": a = cv2.cvtColor(a, cv2.COLOR_RGB2BGR)
    if m.encoding == "rgba8": a = cv2.cvtColor(a, cv2.COLOR_RGBA2BGR)
    frame["img"] = a.copy(); frame["enc"] = m.encoding
n.create_subscription(Image, f"/{drone}/sensors/front_stereo/left/image_rect", on_img, be)
t0 = time.time()
while time.time() - t0 < 10: rclpy.spin_once(n, timeout_sec=0.1)
res = {"drone": drone}
if len(clk) > 2:
    res["sim_time_s"] = round(clk[-1][1], 1); res["rtf"] = round((clk[-1][1] - clk[0][1]) / (clk[-1][0] - clk[0][0]), 2); res["clock_hz"] = round(len(clk) / 10, 1)
else: res["rtf"] = None; res["note"] = "no /clock in 10 s (sim not playing or not visible from here)"
res["image_hz"] = round(len(imgs) / 10, 1)
if frame:
    g = cv2.cvtColor(frame["img"], cv2.COLOR_BGR2GRAY) if frame["img"].ndim == 3 else frame["img"]
    cv2.imwrite(out, frame["img"])
    res.update(frame_png=out, size=f"{g.shape[1]}x{g.shape[0]}", orb_corners=len(cv2.ORB_create(2000).detect(g)),
               gray_mean=round(float(g.mean()), 1), gray_std=round(float(g.std()), 1), sky_top40_mean=round(float(g[:40].mean()), 1))
print(json.dumps(res))
rclpy.shutdown()
