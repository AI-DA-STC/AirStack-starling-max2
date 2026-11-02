#!/usr/bin/env python3
"""teleop_frame relay: safe_teleop's stick command -> BODY or WORLD frame -> the swarm commander (NEAR-789, sim only).

    /svg/{drone}/teleop_command_stick  (safe_teleop, 20 Hz, TwistStamped, stick axes)
        -> rotated by the drone heading when stick_frame=body (frame.py)
    /svg/{drone}/teleop_command        (what the swarm commander flies)
    /teleop_frame/status               (std_msgs/String, 5 Hz: frame, pending flip, heading, guard, input)

Runs inside the robot container; started by tools/sim.sh. stick_frame (body|world) is a live ROS parameter:
`ros2 param set /teleop_frame stick_frame world` (the keyboard window's F key does the same). A flip waits until
the stick is centred. In body mode the horizontal command is zeroed while the heading is stale or jumped
(frame.py's guard); climb and yaw rate always pass.

If this node stops, the commander hears nothing and holds after its 0.5 s timeout. Ctrl-C, SIGTERM or an
error publish one zero command first.

    python3 teleop_frame.py [--drone drone_1] [--stick-frame body|world]
"""
from __future__ import annotations

import argparse
import math
import pathlib
import signal
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import frame  # noqa: E402

import rclpy  # noqa: E402
from rclpy.node import Node  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402
from rclpy.signals import SignalHandlerOptions  # noqa: E402
from rcl_interfaces.msg import SetParametersResult  # noqa: E402
from geometry_msgs.msg import TwistStamped  # noqa: E402
from nav_msgs.msg import Odometry  # noqa: E402
from std_msgs.msg import String  # noqa: E402

NODE_NAME = "teleop_frame"
DEFAULTS = {
    "drone": "drone_1",
    "stick_frame": "body",
    "heading_stale_s": 0.2,
    "heading_jump_rad": 0.5,
    "input_topic_template": "/svg/{name}/teleop_command_stick",
    "output_topic_template": "/svg/{name}/teleop_command",
    "odometry_topic_template": "/{name}/odometry_conversion/odometry",
    "status_topic": "/teleop_frame/status",
    "status_rate_hz": 5.0,
}
FIXED_AT_START = ("drone", "input_topic_template", "output_topic_template", "odometry_topic_template",
                  "status_topic", "status_rate_hz")
QOS_DEPTH = 10


def topics_for(drone: str, params: dict) -> dict:
    """The three per-drone topics from the parameter templates ({name} = drone)."""
    return {
        "input": params["input_topic_template"].format(name=drone),
        "output": params["output_topic_template"].format(name=drone),
        "odometry": params["odometry_topic_template"].format(name=drone),
    }


class TeleopFrameNode(Node):
    def __init__(self, drone: str = DEFAULTS["drone"], stick_frame: str = DEFAULTS["stick_frame"],
                 now=time.monotonic):
        super().__init__(NODE_NAME, parameter_overrides=[Parameter("drone", value=drone),
                                                         Parameter("stick_frame", value=stick_frame)])
        self.now = now
        p = {name: self.declare_parameter(name, default).value for name, default in DEFAULTS.items()}
        if p["stick_frame"] not in frame.MODES:
            raise ValueError("stick_frame %r; expected one of %s" % (p["stick_frame"], frame.MODES))
        if not float(p["status_rate_hz"]) > 0.0:
            raise ValueError("status_rate_hz must be > 0, got %r" % p["status_rate_hz"])
        self.state = frame.FrameState(p["stick_frame"], stale_s=float(p["heading_stale_s"]),
                                      jump_rad=float(p["heading_jump_rad"]), input_silent_s=frame.INPUT_SILENT_S)
        self.topics = topics_for(p["drone"], p)
        self.last_frame_id = ""
        self._mode = self.state.mode
        self._guard = "ok"
        self._input = "none"

        self.out_pub = self.create_publisher(TwistStamped, self.topics["output"], QOS_DEPTH)
        self.status_pub = self.create_publisher(String, p["status_topic"], QOS_DEPTH)
        self.create_subscription(Odometry, self.topics["odometry"], self._on_odometry, QOS_DEPTH)
        self.create_subscription(TwistStamped, self.topics["input"], self._on_input, QOS_DEPTH)
        self.create_timer(1.0 / float(p["status_rate_hz"]), self._on_status_timer)
        self.add_on_set_parameters_callback(self._on_set_parameters)
        self.get_logger().info("teleop_frame: %s stick_frame=%s in=%s out=%s odom=%s"
                               % (p["drone"], p["stick_frame"], self.topics["input"], self.topics["output"],
                                  self.topics["odometry"]))

    # ---- callbacks ----
    def _on_odometry(self, msg) -> None:
        q = msg.pose.pose.orientation
        t = self.now()
        self.state.update_heading(frame.yaw_from_quat(q.x, q.y, q.z, q.w), t)
        self._log_episodes(t)

    def _on_input(self, msg) -> None:
        t = self.now()
        lin, ang = msg.twist.linear, msg.twist.angular
        vx, vy, vz, wz = self.state.command(lin.x, lin.y, lin.z, ang.z, t)
        out = TwistStamped()
        out.header.stamp = msg.header.stamp
        out.header.frame_id = msg.header.frame_id
        self.last_frame_id = msg.header.frame_id
        out.twist.linear.x, out.twist.linear.y, out.twist.linear.z = vx, vy, vz
        out.twist.angular.x, out.twist.angular.y, out.twist.angular.z = 0.0, 0.0, wz
        self.out_pub.publish(out)
        if self.state.mode != self._mode:
            self._mode = self.state.mode
            self.get_logger().info("teleop_frame: mode = %s" % self._mode)
        self._log_episodes(t)

    def _on_status_timer(self) -> None:
        t = self.now()
        self._log_episodes(t)
        self.status_pub.publish(String(data=self.state.status_line(t)))

    def _on_set_parameters(self, params) -> SetParametersResult:
        for prm in params:
            if prm.name in FIXED_AT_START:
                return SetParametersResult(successful=False,
                                           reason="%s is fixed at start; restart the relay" % prm.name)
            if prm.name == "stick_frame" and prm.value not in frame.MODES:
                return SetParametersResult(successful=False,
                                           reason="stick_frame %r; expected one of %s" % (prm.value, frame.MODES))
            if prm.name in ("heading_stale_s", "heading_jump_rad"):
                try:
                    ok = math.isfinite(float(prm.value)) and float(prm.value) > 0.0
                except (TypeError, ValueError):
                    ok = False
                if not ok:
                    return SetParametersResult(successful=False,
                                               reason="%s must be a number > 0, got %r" % (prm.name, prm.value))
        for prm in params:
            if prm.name == "stick_frame":
                had_pending = self.state.pending is not None
                self.state.request_mode(prm.value)
                if self.state.pending is not None:
                    self.get_logger().info("teleop_frame: mode -> %s (pending until centred)" % prm.value)
                elif had_pending:
                    self.get_logger().info("teleop_frame: mode -> %s (pending flip cancelled)" % prm.value)
                else:
                    self.get_logger().info("teleop_frame: mode -> %s (already)" % prm.value)
            elif prm.name == "heading_stale_s":
                self.state.stale_s = float(prm.value)
            elif prm.name == "heading_jump_rad":
                self.state.jump_rad = float(prm.value)
        return SetParametersResult(successful=True)

    # ---- helpers ----
    def _log_episodes(self, t: float) -> None:
        """One log line per episode: guard ok -> stale/jump, input ok -> none, and each return to normal."""
        s = self.state.status(t)
        if s["guard"] != self._guard:
            if s["guard"] == "stale":
                self.get_logger().warning("teleop_frame: HEADING STALE — horizontal command zeroed until the "
                                          "stick is centred and the heading is fresh")
            elif s["guard"] == "jump":
                self.get_logger().warning("teleop_frame: HEADING JUMP — horizontal command zeroed until the "
                                          "stick is centred and the heading is steady")
            else:
                self.get_logger().info("teleop_frame: heading guard ok")
            self._guard = s["guard"]
        if s["input"] != self._input:
            if s["input"] == "none":
                self.get_logger().warning("teleop_frame: input silent on %s" % self.topics["input"])
            else:
                self.get_logger().info("teleop_frame: input ok")
            self._input = s["input"]

    def publish_zero(self) -> None:
        out = TwistStamped()
        out.header.stamp = self.get_clock().now().to_msg()
        out.header.frame_id = self.last_frame_id
        self.out_pub.publish(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--drone", default=DEFAULTS["drone"])
    ap.add_argument("--stick-frame", default=DEFAULTS["stick_frame"], choices=frame.MODES)
    a = ap.parse_args(argv)

    # Our own SIGINT/SIGTERM handling (as key_teleop): rclpy's would invalidate the publisher before the zero
    # goes out. A signal only sets a flag; the spin loop below sees it within 50 ms.
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    stop = {"now": False}
    signal.signal(signal.SIGINT, lambda *_: stop.update(now=True))
    signal.signal(signal.SIGTERM, lambda *_: stop.update(now=True))
    node = None
    code = 0
    try:
        node = TeleopFrameNode(drone=a.drone, stick_frame=a.stick_frame)
        while not stop["now"]:
            rclpy.spin_once(node, timeout_sec=0.05)
    except Exception as e:
        print("teleop_frame: error %s: %s — publishing a zero command and stopping" % (type(e).__name__, e),
              flush=True)
        code = 1
    finally:
        if node is not None:
            try:
                node.publish_zero()
                print("teleop_frame: stopped, zero command published", flush=True)
            except Exception as e:
                print("teleop_frame: could not publish the zero command: %s" % e, flush=True)
            node.destroy_node()
        rclpy.try_shutdown()
    return code


if __name__ == "__main__":
    sys.exit(main())
