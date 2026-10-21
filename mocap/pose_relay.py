#!/usr/bin/env python3
"""Republish named poses from motion_capture_tracking's /poses as per-body
geometry_msgs/PoseStamped topics (/<name>/pose), matching what natnet_ros2
would have published."""
# Provenance: the copy that flew the real-drone sessions (last edited 2026-09-18 in
# ~/mocap_ws/bridge/, merged here 2026-10-21). vs the 08-28 version: relays EVERY body
# Motive publishes when no list is given, sanitises body names into legal topic names,
# and declares `bodies` as a typed STRING_ARRAY (Jazzy rejects overrides of an empty
# [] default). Explicit lists (-p bodies:=[...] / MOCAP_BODIES) still work.
import re
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from rclpy.parameter import Parameter
from rclpy.exceptions import ParameterUninitializedException
from geometry_msgs.msg import PoseStamped
from motion_capture_tracking_interfaces.msg import NamedPoseArray


def sanitize(name):
    """Make a Motive rigid-body name legal as a ROS 2 topic segment.
    Clean names (drone_1, cf8, ...) are returned unchanged."""
    s = re.sub(r'[^A-Za-z0-9_]', '_', name)
    if not s or s[0].isdigit():
        s = 'b_' + s
    return s


class PoseRelay(Node):
    def __init__(self):
        super().__init__('mocap_pose_relay')
        # typed, no default: Jazzy rclpy infers BYTE_ARRAY from a [] default
        # and then rejects -p "bodies:=['x']" overrides
        self.declare_parameter('bodies', Parameter.Type.STRING_ARRAY)
        try:
            names = list(self.get_parameter('bodies').value)
        except ParameterUninitializedException:
            names = []
        self.dynamic = not names   # no bodies given -> relay every body seen
        self.pubs = {n: self._make_pub(n) for n in names}
        # best-effort matches both reliable and best-effort publishers
        qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.sub = self.create_subscription(NamedPoseArray, '/poses', self.cb, qos)
        if self.dynamic:
            self.get_logger().info("relaying ALL bodies published on /poses (dynamic)")
        else:
            self.get_logger().info(f"relaying bodies: {names}")

    def _make_pub(self, name):
        return self.create_publisher(PoseStamped, f'/{sanitize(name)}/pose', 10)

    def cb(self, msg):
        for p in msg.poses:
            pub = self.pubs.get(p.name)
            if pub is None and self.dynamic:
                pub = self.pubs[p.name] = self._make_pub(p.name)
                topic = sanitize(p.name)
                extra = f" (sanitized from '{p.name}')" if topic != p.name else ""
                self.get_logger().info(
                    f"discovered body '{p.name}' -> /{topic}/pose{extra}")
            if pub is not None:
                out = PoseStamped()
                out.header = msg.header
                out.pose = p.pose
                pub.publish(out)


def main():
    rclpy.init()
    rclpy.spin(PoseRelay())


if __name__ == '__main__':
    main()
