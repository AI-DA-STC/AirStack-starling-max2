#!/usr/bin/env python3
"""Save one frame of a drone's left camera to a PNG (run inside the exploration container).
Usage: python3 scripts/grab_frame.py [drone] [out.png]   (default drone_1, results/frame_<drone>.png)"""
import sys, time
import numpy as np, cv2, rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image

drone = sys.argv[1] if len(sys.argv) > 1 else "drone_1"
out = sys.argv[2] if len(sys.argv) > 2 else f"results/frame_{drone}.png"
rclpy.init()
n = Node("grab_frame"); got = {}
def cb(m):
    if got: return
    ch = {"mono8": 1, "rgb8": 3, "bgr8": 3, "rgba8": 4, "bgra8": 4}[m.encoding]
    a = np.frombuffer(m.data, np.uint8).reshape(m.height, m.step // ch if ch > 1 else m.step, ch)[:, :m.width] if ch > 1 \
        else np.frombuffer(m.data, np.uint8).reshape(m.height, m.step)[:, :m.width]
    if m.encoding == "rgb8": a = cv2.cvtColor(a, cv2.COLOR_RGB2BGR)
    if m.encoding == "rgba8": a = cv2.cvtColor(a, cv2.COLOR_RGBA2BGR)
    cv2.imwrite(out, a); got["ok"] = (m.width, m.height, m.encoding)
n.create_subscription(Image, f"/{drone}/sensors/front_stereo/left/image_rect", cb,
                      QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT))
t0 = time.time()
while rclpy.ok() and not got and time.time() - t0 < 30: rclpy.spin_once(n, timeout_sec=0.5)
print("saved", out, got) if got else print("no image within 30 s")
rclpy.shutdown()
