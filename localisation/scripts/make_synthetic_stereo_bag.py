#!/usr/bin/env python3
"""Write a small synthetic stereo bag for testing scripts/replay_bag.sh without Isaac (NEAR-860).

A rectified stereo pair (the sim ZED's settings: 640x480, fx 245.3, 12 cm baseline) looks at a textured wall
4 m ahead and slides sideways and up/down on a smooth path. For a wall facing the camera, the image is the
texture shifted by fx*t/Z, and the right image is the left one shifted by the disparity fx*B/Z. Topics and
frame names match the sim, so the cuVSLAM node runs on it unchanged. Not a sim result; a tooling test only.
Run INSIDE the exploration container: python3 scripts/make_synthetic_stereo_bag.py results/bags/synth_stereo [seconds]
"""
import sys

import cv2
import numpy as np
import rosbag2_py
from builtin_interfaces.msg import Time
from rclpy.serialization import serialize_message
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import CameraInfo, Image

W, H, FX, B, Z, HZ = 640, 480, 245.3, 0.12, 4.0, 25.0
CX, CY = W / 2.0, H / 2.0
NS = "/drone_1/sensors/front_stereo"


def texture(seed=7, size=(2400, 3200)):
    rng = np.random.default_rng(seed)
    img = np.zeros(size, np.float32)
    for scale in (4, 16, 64):                                  # multi-scale noise: corners at every size
        small = rng.random((size[0] // scale + 1, size[1] // scale + 1)).astype(np.float32)
        img += cv2.resize(small, (size[1], size[0]), interpolation=cv2.INTER_CUBIC)[: size[0], : size[1]]
    img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    return cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)


def view(tex, tx, ty):
    """Camera at (tx, ty) looking at the wall: crop of the texture shifted by fx*t/Z (sub-pixel)."""
    sx, sy = tex.shape[1] / 2 - CX + FX * tx / Z, tex.shape[0] / 2 - CY + FX * ty / Z
    m = np.float32([[1, 0, sx], [0, 1, sy]])
    return cv2.warpAffine(tex, m, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)


def info(stamp, frame, right):
    m = CameraInfo(); m.header.stamp = stamp; m.header.frame_id = frame
    m.width, m.height, m.distortion_model = W, H, "plumb_bob"
    m.d = [0.0] * 5
    m.k = [FX, 0.0, CX, 0.0, FX, CY, 0.0, 0.0, 1.0]
    m.r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    m.p = [FX, 0.0, CX, -FX * B if right else 0.0, 0.0, FX, CY, 0.0, 0.0, 0.0, 1.0, 0.0]
    return m


def image(stamp, frame, arr):
    m = Image(); m.header.stamp = stamp; m.header.frame_id = frame
    m.height, m.width, m.encoding, m.is_bigendian, m.step = H, W, "rgb8", 0, W * 3
    m.data = arr.tobytes()
    return m


def main():
    out = sys.argv[1]
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
    w = rosbag2_py.SequentialWriter()
    w.open(rosbag2_py.StorageOptions(uri=out, storage_id="mcap"), rosbag2_py.ConverterOptions("cdr", "cdr"))
    topics = {"/clock": "rosgraph_msgs/msg/Clock",
              f"{NS}/left/camera_info": "sensor_msgs/msg/CameraInfo", f"{NS}/right/camera_info": "sensor_msgs/msg/CameraInfo",
              f"{NS}/left/image_rect": "sensor_msgs/msg/Image", f"{NS}/right/image_rect": "sensor_msgs/msg/Image"}
    for i, (name, typ) in enumerate(topics.items()):
        w.create_topic(rosbag2_py.TopicMetadata(id=i, name=name, type=typ, serialization_format="cdr"))
    tex = texture()
    t0 = 1000.0                                                 # sim-like clock, seconds
    for k in range(int(seconds * HZ)):
        t = t0 + k / HZ
        ns = int(t * 1e9)
        stamp = Time(sec=int(t), nanosec=int(round((t - int(t)) * 1e9)) % 1_000_000_000)
        tx, ty = 0.8 * np.sin(0.4 * (t - t0)), 0.3 * np.sin(0.25 * (t - t0))
        w.write("/clock", serialize_message(Clock(clock=stamp)), ns)
        w.write(f"{NS}/left/camera_info", serialize_message(info(stamp, "drone_1/left", False)), ns)
        w.write(f"{NS}/right/camera_info", serialize_message(info(stamp, "drone_1/right", True)), ns)
        w.write(f"{NS}/left/image_rect", serialize_message(image(stamp, "drone_1/left", view(tex, tx, ty))), ns)
        w.write(f"{NS}/right/image_rect", serialize_message(image(stamp, "drone_1/right", view(tex, tx + B, ty))), ns)
    del w
    print(f"wrote {out}: {int(seconds * HZ)} stereo frames at {HZ:.0f} Hz, wall at {Z} m, disparity {FX * B / Z:.2f} px")


if __name__ == "__main__":
    main()
