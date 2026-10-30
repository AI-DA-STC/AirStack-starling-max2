#!/usr/bin/env python3
"""Replay a recorded flight's stereo images through cuVSLAM, offline and frame by frame (NEAR-860).

Reads the bag directly (no DDS, so no frame is dropped and the result does not depend on timing), pairs the
left and right images by header stamp, and runs every pair through the same make_tracker()/track_frame()
the live node uses (nodes/cuvslam_stereo_node.py). Writes a TUM path in the node's FLU-aligned odometry frame
and a stats JSON (frames, tracked, lost, rejected, track time).
Run INSIDE the exploration container:
  python3 scripts/replay_offline.py <bag_dir> <out.tum> [--drone drone_1] [--baseline 0]
"""
import argparse
import json
import os
import sys
import time

import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import CameraInfo, Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "nodes"))
from cuvslam_stereo_node import image_to_numpy, make_tracker, track_frame  # noqa: E402


def stamp_ns(msg):
    return msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec


def _reader(bag, topics):
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=bag, storage_id=""), rosbag2_py.ConverterOptions("cdr", "cdr"))
    r.set_filter(rosbag2_py.StorageFilter(topics=topics))
    return r


def camera_infos(bag, cam):
    """First left and right camera_info in the bag."""
    r = _reader(bag, [f"{cam}/left/camera_info", f"{cam}/right/camera_info"])
    info = {}
    while r.has_next() and len(info) < 2:
        topic, data, _ = r.read_next()
        info.setdefault("left" if "/left/" in topic else "right", deserialize_message(data, CameraInfo))
    if len(info) < 2:
        raise SystemExit(f"{bag}: no camera_info for both cameras under {cam}")
    return info["left"], info["right"]


def stereo_pairs(bag, cam, counts, slop_ns=1_000_000, keep_ns=2_000_000_000):
    """Stream (ts_ns, left Image, right Image) pairs, matched by header stamp within slop_ns, holding only
    images younger than keep_ns in memory. counts gets 'left'/'right' image totals."""
    r = _reader(bag, [f"{cam}/left/image_rect", f"{cam}/right/image_rect"])
    pending = {"left": {}, "right": {}}
    counts.update(left=0, right=0)
    while r.has_next():
        topic, data, _ = r.read_next()
        side = "left" if "/left/" in topic else "right"
        other = "right" if side == "left" else "left"
        msg = deserialize_message(data, Image)
        ts = stamp_ns(msg)
        counts[side] += 1
        match = min(pending[other], key=lambda x: abs(x - ts), default=None)
        if match is not None and abs(match - ts) <= slop_ns:
            om = pending[other].pop(match)
            yield (ts, msg, om) if side == "left" else (match, om, msg)
        else:
            pending[side][ts] = msg
        for s_ in pending:
            for old in [t for t in pending[s_] if t < ts - keep_ns]:
                del pending[s_][old]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bag"); ap.add_argument("out_tum")
    ap.add_argument("--drone", default="drone_1"); ap.add_argument("--baseline", type=float, default=0.0)
    a = ap.parse_args()
    cam = f"/{a.drone}/sensors/front_stereo"
    li, ri = camera_infos(a.bag, cam)
    tracker, b = make_tracker(li, ri, a.baseline)
    print(f"tracker ready: {li.width}x{li.height} fx={li.k[0]:.1f} baseline={b:.4f} m")
    counts = {}
    st = {"pairs": 0, "tracked": 0, "lost": 0, "rejected": 0, "out_of_order": 0, "baseline_m": b, "track_ms_mean": None}
    ms, last, first = [], None, None
    with open(a.out_tum, "w") as f:
        for ts, lm, rm in stereo_pairs(a.bag, cam, counts):
            st["pairs"] += 1
            first = ts if first is None else first
            if last is not None and ts <= last:
                st["out_of_order"] += 1                    # cuVSLAM needs strictly increasing stamps (as live)
                continue
            t0 = time.monotonic()
            try:
                res = track_frame(tracker, ts, image_to_numpy(lm), image_to_numpy(rm))
            except ValueError:
                st["rejected"] += 1
                continue
            ms.append((time.monotonic() - t0) * 1e3)
            last = ts
            if res is None:
                st["lost"] += 1
                continue
            st["tracked"] += 1
            t, q = res
            f.write(f"{ts / 1e9:.9f} {t[0]:.9f} {t[1]:.9f} {t[2]:.9f} {q[0]:.9f} {q[1]:.9f} {q[2]:.9f} {q[3]:.9f}\n")
    st["track_ms_mean"] = sum(ms) / len(ms) if ms else None
    st.update(left_images=counts["left"], right_images=counts["right"])
    span = (last - first) / 1e9 if last is not None and first is not None else 0.0
    st.update(span_s=span, pair_rate_hz=(st["pairs"] - 1) / span if span > 0 else None)
    with open(os.path.splitext(a.out_tum)[0] + "_stats.json", "w") as f:
        json.dump(st, f, indent=1)
    print(f"replay: {st['tracked']} tracked, {st['lost']} lost, {st['rejected']} rejected of {st['pairs']} pairs "
          f"({counts['left']} left / {counts['right']} right images); "
          f"track {st['track_ms_mean'] or 0:.1f} ms/frame")
    if st["pair_rate_hz"]:
        print(f"recording: {st['pairs']} pairs over {span:.1f} s = {st['pair_rate_hz']:.1f} Hz "
              f"(the sim camera runs ~25 Hz; much lower means the recorder dropped frames)")


if __name__ == "__main__":
    main()
