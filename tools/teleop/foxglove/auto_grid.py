#!/usr/bin/env python3
"""auto_grid: a ground grid for Foxglove that grows with the drone (sim only).

    --source odom --drone drone_1   /<drone>/cuvslam/odometry (Odometry) -> /<drone>/cuvslam/grid, frame <drone>/cuvslam_odom
    --source status                 /svg/commander_status (String JSON, every drone) -> /svg/viz/grid, frame map

Publishes a visualization_msgs/Marker LINE_LIST at 1 Hz whether or not the grid changed, so a late Studio sees it.
Nothing is published before the first position. Logic is in grid_core.py.

    python3 auto_grid.py --source odom --drone drone_1
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import signal
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from grid_core import GrowingGrid  # noqa: E402

import rclpy  # noqa: E402
from rclpy.node import Node  # noqa: E402
from rclpy.signals import SignalHandlerOptions  # noqa: E402
from geometry_msgs.msg import Point  # noqa: E402
from nav_msgs.msg import Odometry  # noqa: E402
from std_msgs.msg import String  # noqa: E402
from visualization_msgs.msg import Marker  # noqa: E402

NODE_NAME = "auto_grid"
RATE_HZ = 1.0
QOS_DEPTH = 10
LINE_WIDTH_M = 0.02
COLOR = (0x4F / 255.0, 0x7C / 255.0, 0xBB / 255.0, 0.6)     # #4f7cbb at alpha 0.6
STATUS_TOPIC = "/svg/commander_status"
STATUS_GRID_TOPIC = "/svg/viz/grid"
STATUS_FRAME = "map"
ODOM_TOPIC = "/{drone}/cuvslam/odometry"
ODOM_GRID_TOPIC = "/{drone}/cuvslam/grid"
ODOM_FRAME = "{drone}/cuvslam_odom"


def _xy(value):
    """(x, y) from a list/tuple of at least two finite numbers, else None."""
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        x, y = float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return None
    return (x, y) if math.isfinite(x) and math.isfinite(y) else None


class AutoGridNode(Node):
    def __init__(self, source: str = "odom", drone: str = "drone_1"):
        super().__init__(NODE_NAME)
        if source not in ("odom", "status"):
            raise ValueError("source %r; expected odom or status" % source)
        self.source = source
        self.grid = GrowingGrid()
        self.stamp = None
        if source == "odom":
            self.frame = ODOM_FRAME.format(drone=drone)
            topic = ODOM_GRID_TOPIC.format(drone=drone)
            self.create_subscription(Odometry, ODOM_TOPIC.format(drone=drone), self._on_odometry, QOS_DEPTH)
        else:
            self.frame = STATUS_FRAME
            topic = STATUS_GRID_TOPIC
            self.create_subscription(String, STATUS_TOPIC, self._on_status, QOS_DEPTH)
        self.pub = self.create_publisher(Marker, topic, QOS_DEPTH)
        self.create_timer(1.0 / RATE_HZ, self._on_timer)
        self.get_logger().info("auto_grid: %s -> %s frame=%s" % (source, topic, self.frame))

    def _feed(self, x: float, y: float) -> None:
        had = self.grid.cx is not None
        old = (self.grid.half, self.grid.cell)
        if self.grid.update(x, y) and had:
            self.get_logger().info("auto_grid: grew to half=%g m, cell=%g m (was %g, %g)"
                                   % (self.grid.half, self.grid.cell, old[0], old[1]))

    def _on_odometry(self, msg) -> None:
        p = msg.pose.pose.position
        self.stamp = msg.header.stamp
        self._feed(p.x, p.y)

    def _on_status(self, msg) -> None:
        try:
            data = json.loads(msg.data)
            drones = data.get("drones") if isinstance(data, dict) else None
            if not isinstance(drones, list):
                return
            for d in drones:
                xy = _xy(d.get("position")) if isinstance(d, dict) else None
                if xy is not None:
                    self._feed(*xy)
        except Exception as e:                      # a bad snapshot must never stop the node
            self.get_logger().warning("auto_grid: ignored a bad status message: %s" % e)

    def _on_timer(self) -> None:
        if self.grid.cx is None:
            return
        m = Marker()
        m.header.frame_id = self.frame
        m.header.stamp = self.stamp if (self.source == "odom" and self.stamp is not None) \
            else self.get_clock().now().to_msg()
        m.ns, m.id = "auto_grid", 0
        m.type, m.action = Marker.LINE_LIST, Marker.ADD
        m.pose.orientation.w = 1.0
        m.scale.x = LINE_WIDTH_M
        m.color.r, m.color.g, m.color.b, m.color.a = COLOR
        pts = []
        for a, b in self.grid.lines():
            pts.append(Point(x=a[0], y=a[1], z=0.0))
            pts.append(Point(x=b[0], y=b[1], z=0.0))
        m.points = pts
        self.pub.publish(m)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", choices=("odom", "status"), required=True)
    ap.add_argument("--drone", default="drone_1")
    a = ap.parse_args(argv)

    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    stop = {"now": False}
    signal.signal(signal.SIGINT, lambda *_: stop.update(now=True))
    signal.signal(signal.SIGTERM, lambda *_: stop.update(now=True))
    node = None
    code = 0
    try:
        node = AutoGridNode(source=a.source, drone=a.drone)
        while not stop["now"]:
            rclpy.spin_once(node, timeout_sec=0.05)
    except Exception as e:
        print("auto_grid: error %s: %s" % (type(e).__name__, e), flush=True)
        code = 1
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()
    return code


if __name__ == "__main__":
    sys.exit(main())
