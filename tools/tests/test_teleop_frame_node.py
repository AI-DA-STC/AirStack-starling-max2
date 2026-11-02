# tools/tests/test_teleop_frame_node.py — teleop_frame relay node (NEAR-789, sim): safe_teleop stick -> BODY/WORLD -> commander
import math, pathlib, re, sys, types, unittest
from unittest import mock
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "teleop"))
SRC_PATH = HERE.parent / "teleop" / "teleop_frame.py"


# ---- minimal rclpy / message stubs: just enough to build the node and drive its callbacks without ROS ----
class _NS(types.SimpleNamespace):
    pass


def _vec():
    return _NS(x=0.0, y=0.0, z=0.0)


class TwistStamped:
    def __init__(self):
        self.header = _NS(stamp=_NS(sec=0, nanosec=0), frame_id="")
        self.twist = _NS(linear=_vec(), angular=_vec())


class Odometry:
    def __init__(self):
        self.header = _NS(stamp=_NS(sec=0, nanosec=0), frame_id="")
        self.pose = _NS(pose=_NS(position=_vec(), orientation=_NS(x=0.0, y=0.0, z=0.0, w=1.0)))


class String:
    def __init__(self, data=""):
        self.data = data


class SetParametersResult:
    def __init__(self, successful=False, reason=""):
        self.successful, self.reason = successful, reason


class Parameter:
    def __init__(self, name, type_=None, value=None):
        self.name, self.value = name, value


class _Pub:
    def __init__(self, topic):
        self.topic, self.sent = topic, []

    def publish(self, msg):
        self.sent.append(msg)


class _Logger:
    def __init__(self):
        self.lines = []

    def info(self, m): self.lines.append(m)
    def warn(self, m): self.lines.append(m)
    warning = warn
    def error(self, m): self.lines.append(m)


class Node:
    def __init__(self, name, parameter_overrides=None, **kw):
        self.name = name
        self._overrides = {p.name: p.value for p in (parameter_overrides or [])}
        self._params, self.subs, self.pubs, self.timers, self.param_cbs = {}, {}, {}, [], []
        self.logger = _Logger()

    def declare_parameter(self, name, value=None, *a, **k):
        self._params[name] = self._overrides.get(name, value)
        return Parameter(name, value=self._params[name])

    def get_parameter(self, name):
        return Parameter(name, value=self._params[name])

    def add_on_set_parameters_callback(self, cb):
        self.param_cbs.append(cb)

    def set(self, name, value):                     # what the parameter service does: callbacks, then store
        r = [cb([Parameter(name, value=value)]) for cb in self.param_cbs]
        if all(x.successful for x in r):
            self._params[name] = value
        return r[-1]

    def create_subscription(self, typ, topic, cb, qos, **k):
        self.subs[topic] = cb

    def create_publisher(self, typ, topic, qos, **k):
        self.pubs[topic] = _Pub(topic)
        return self.pubs[topic]

    def create_timer(self, period, cb, **k):
        self.timers.append((period, cb))

    def get_logger(self):
        return self.logger

    def get_clock(self):
        return _NS(now=lambda: _NS(to_msg=lambda: _NS(sec=0, nanosec=0)))

    def destroy_node(self):
        pass


def _stub_modules():
    m = {}
    for name in ("rclpy", "rclpy.node", "rclpy.signals", "rclpy.parameter", "rcl_interfaces", "rcl_interfaces.msg",
                 "geometry_msgs", "geometry_msgs.msg", "nav_msgs", "nav_msgs.msg", "std_msgs", "std_msgs.msg"):
        m[name] = types.ModuleType(name)
    m["rclpy.node"].Node = Node
    m["rclpy.signals"].SignalHandlerOptions = _NS(NO=0)
    m["rclpy.parameter"].Parameter = Parameter
    m["rcl_interfaces.msg"].SetParametersResult = SetParametersResult
    m["geometry_msgs.msg"].TwistStamped = TwistStamped
    m["nav_msgs.msg"].Odometry = Odometry
    m["std_msgs.msg"].String = String
    return m


with mock.patch.dict(sys.modules, _stub_modules()):
    sys.modules.pop("teleop_frame", None)
    import teleop_frame as TF
sys.modules.pop("teleop_frame", None)


class Source(unittest.TestCase):
    SRC = SRC_PATH.read_text()

    def test_parameters_and_topics_named_as_in_the_spec(self):
        for name, default in (("drone", '"drone_1"'), ("stick_frame", '"body"'), ("heading_stale_s", "0.2"),
                              ("heading_jump_rad", "0.5"),
                              ("input_topic_template", '"/svg/{name}/teleop_command_stick"'),
                              ("output_topic_template", '"/svg/{name}/teleop_command"'),
                              ("odometry_topic_template", '"/{name}/odometry_conversion/odometry"'),
                              ("status_topic", '"/teleop_frame/status"'), ("status_rate_hz", "5.0")):
            self.assertRegex(self.SRC, r'"%s":\s*%s' % (re.escape(name), re.escape(default)), name)
        self.assertIn('"teleop_frame"', self.SRC)                                   # node name

    def test_status_published_at_5_hz_and_input_silence_is_reported(self):
        self.assertRegex(self.SRC, r'create_timer\(\s*1\.0\s*/\s*[^,]*status_rate_hz')
        self.assertTrue("INPUT_SILENT_S" in self.SRC or "input_silent_s" in self.SRC)
        self.assertIn("teleop_frame: input silent", self.SRC)

    def test_stick_frame_rejects_unknown_values(self):
        self.assertIn("add_on_set_parameters_callback", self.SRC)
        self.assertRegex(self.SRC, r"SetParametersResult\(successful=False")
        self.assertIn("MODES", self.SRC)

    def test_rclpy_signal_handlers_are_ours(self):
        self.assertIn("rclpy.init(signal_handler_options=SignalHandlerOptions.NO)", self.SRC)
        self.assertIn("signal.signal(signal.SIGTERM", self.SRC); self.assertIn("signal.signal(signal.SIGINT", self.SRC)
        main = self.SRC[self.SRC.index("def main("):]
        self.assertIn("publish_zero()", main)                                       # zeros on exit
        self.assertRegex(main, r"spin_once\(node, timeout_sec=0\.05\)")             # signal seen within 50 ms

    def test_topics_for(self):
        t = TF.topics_for("drone_2", {"input_topic_template": "/svg/{name}/teleop_command_stick", "output_topic_template": "/svg/{name}/teleop_command", "odometry_topic_template": "/{name}/odometry_conversion/odometry"})
        self.assertEqual(t, {"input": "/svg/drone_2/teleop_command_stick", "output": "/svg/drone_2/teleop_command", "odometry": "/drone_2/odometry_conversion/odometry"})


def _odom(yaw):
    m = Odometry()
    m.pose.pose.orientation = _NS(x=0.0, y=0.0, z=math.sin(yaw / 2), w=math.cos(yaw / 2))
    return m


def _cmd(vx, vy, vz, wz, frame_id="drone_1/base_link", sec=12):
    m = TwistStamped()
    m.header.stamp = _NS(sec=sec, nanosec=5)
    m.header.frame_id = frame_id
    m.twist.linear = _NS(x=vx, y=vy, z=vz)
    m.twist.angular = _NS(x=0.0, y=0.0, z=wz)
    return m


class Relay(unittest.TestCase):
    def setUp(self):
        self.t = 100.0
        self.node = TF.TeleopFrameNode(drone="drone_1", stick_frame="body", now=lambda: self.t)
        self.out = self.node.pubs["/svg/drone_1/teleop_command"]
        self.status = self.node.pubs["/teleop_frame/status"]
        self.odom_cb = self.node.subs["/drone_1/odometry_conversion/odometry"]
        self.in_cb = self.node.subs["/svg/drone_1/teleop_command_stick"]
        self.tick = [cb for period, cb in self.node.timers if abs(period - 0.2) < 1e-9][0]

    def test_wiring_and_start_line(self):
        self.assertEqual(self.node.name, "teleop_frame")
        self.assertTrue(any("teleop_frame: drone_1 stick_frame=body in=/svg/drone_1/teleop_command_stick "
                            "out=/svg/drone_1/teleop_command" in l for l in self.node.logger.lines), self.node.logger.lines)

    def test_body_output_is_rotated(self):
        self.odom_cb(_odom(math.pi))
        self.t += 0.05
        self.in_cb(_cmd(1.0, 0.0, 0.3, 0.7))
        m = self.out.sent[-1]
        self.assertAlmostEqual(m.twist.linear.x, -1.0, 6); self.assertAlmostEqual(m.twist.linear.y, 0.0, 6)
        self.assertAlmostEqual(m.twist.linear.z, 0.3, 6); self.assertAlmostEqual(m.twist.angular.z, 0.7, 6)
        self.assertEqual((m.twist.angular.x, m.twist.angular.y), (0.0, 0.0))
        self.assertEqual(m.header.frame_id, "drone_1/base_link"); self.assertEqual(m.header.stamp.sec, 12)
        self.tick()
        line = self.status.sent[-1].data
        for part in ("frame=body", "guard=ok", "input=ok", "heading_deg=180.0"):
            self.assertIn(part, line)

    def test_input_silence_is_reported(self):
        self.odom_cb(_odom(0.0))
        self.in_cb(_cmd(0.0, 0.0, 0.0, 0.0))
        self.tick(); self.assertIn("input=ok", self.status.sent[-1].data)
        self.t += 1.5
        self.odom_cb(_odom(0.0))
        self.tick(); self.tick()
        self.assertIn("input=none", self.status.sent[-1].data)
        self.assertEqual(sum("teleop_frame: input silent" in l for l in self.node.logger.lines), 1)   # once per episode

    def test_stale_heading_zeroes_horizontal_and_logs_once(self):
        self.odom_cb(_odom(0.0))
        self.t += 0.5
        self.in_cb(_cmd(1.0, 0.5, 0.3, 0.7)); self.in_cb(_cmd(1.0, 0.5, 0.3, 0.7))
        m = self.out.sent[-1]
        self.assertEqual((m.twist.linear.x, m.twist.linear.y), (0.0, 0.0))
        self.assertAlmostEqual(m.twist.linear.z, 0.3, 6); self.assertAlmostEqual(m.twist.angular.z, 0.7, 6)
        self.tick(); self.assertIn("guard=stale", self.status.sent[-1].data)
        self.assertEqual(sum("teleop_frame: HEADING STALE" in l for l in self.node.logger.lines), 1)

    def test_heading_jump_logged(self):
        self.odom_cb(_odom(0.0)); self.odom_cb(_odom(1.0))
        self.in_cb(_cmd(1.0, 0.0, 0.0, 0.0))
        self.assertEqual(self.out.sent[-1].twist.linear.x, 0.0)
        self.assertTrue(any("teleop_frame: HEADING JUMP" in l for l in self.node.logger.lines))

    def test_stick_frame_param_validated_and_flip_waits_for_centre(self):
        r = self.node.set("stick_frame", "nose")
        self.assertFalse(r.successful); self.assertIn("nose", r.reason)
        self.assertEqual(self.node.get_parameter("stick_frame").value, "body")
        self.odom_cb(_odom(math.pi))
        self.assertTrue(self.node.set("stick_frame", "world").successful)
        self.assertTrue(any("teleop_frame: mode -> world (pending until centred)" in l for l in self.node.logger.lines))
        self.in_cb(_cmd(1.0, 0.0, 0.0, 0.0))                        # still pushed: still BODY
        self.assertAlmostEqual(self.out.sent[-1].twist.linear.x, -1.0, 6)
        self.in_cb(_cmd(0.0, 0.0, 0.0, 0.0))                        # centred: flip applies
        self.assertTrue(any("teleop_frame: mode = world" in l for l in self.node.logger.lines))
        self.in_cb(_cmd(1.0, 0.0, 0.0, 0.0))
        self.assertAlmostEqual(self.out.sent[-1].twist.linear.x, 1.0, 6)

    def test_thresholds_live(self):
        self.assertTrue(self.node.set("heading_stale_s", 0.7).successful)
        self.assertTrue(self.node.set("heading_jump_rad", 1.5).successful)
        self.assertEqual((self.node.state.stale_s, self.node.state.jump_rad), (0.7, 1.5))
        self.assertFalse(self.node.set("heading_stale_s", 0.0).successful)
        self.assertEqual(self.node.state.stale_s, 0.7)
        self.assertFalse(self.node.set("drone", "drone_2").successful)              # topics are fixed at start
        self.assertEqual(self.node.get_parameter("drone").value, "drone_1")

    def test_zero_published_on_exit(self):
        self.in_cb(_cmd(0.4, 0.0, 0.0, 0.0))
        self.node.publish_zero()
        m = self.out.sent[-1]
        self.assertEqual((m.twist.linear.x, m.twist.linear.y, m.twist.linear.z, m.twist.angular.z), (0.0, 0.0, 0.0, 0.0))
        self.assertEqual(m.header.frame_id, "drone_1/base_link")

    def test_cli_seeds_parameters(self):
        n = TF.TeleopFrameNode(drone="drone_3", stick_frame="world", now=lambda: self.t)
        self.assertEqual((n.get_parameter("drone").value, n.get_parameter("stick_frame").value), ("drone_3", "world"))
        self.assertEqual(n.state.mode, "world")
        self.assertIn("/svg/drone_3/teleop_command", n.pubs)


if __name__ == "__main__":
    unittest.main()
