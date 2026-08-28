#!/usr/bin/env python3
"""Republish named poses from motion_capture_tracking's /poses as per-body
geometry_msgs/PoseStamped topics (/<name>/pose), matching what natnet_ros2
would have published."""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from geometry_msgs.msg import PoseStamped
from motion_capture_tracking_interfaces.msg import NamedPoseArray


class PoseRelay(Node):
    def __init__(self):
        super().__init__('mocap_pose_relay')
        self.declare_parameter('bodies', ['drone_1'])
        names = self.get_parameter('bodies').value
        self.pubs = {n: self.create_publisher(PoseStamped, f'/{n}/pose', 10)
                     for n in names}
        # best-effort matches both reliable and best-effort publishers
        qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.sub = self.create_subscription(NamedPoseArray, '/poses', self.cb, qos)
        self.get_logger().info(f"relaying bodies: {names}")

    def cb(self, msg):
        for p in msg.poses:
            pub = self.pubs.get(p.name)
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
