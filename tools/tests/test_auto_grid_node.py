# tools/tests/test_auto_grid_node.py — auto_grid rclpy node (sim only): source-level wiring + stub-rclpy behaviour
import json, math, pathlib, re, sys, types, unittest
from unittest import mock
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FOX = ROOT / "tools" / "teleop" / "foxglove"
sys.path.insert(0, str(FOX))
SRC_PATH = FOX / "auto_grid.py"


class _NS(types.SimpleNamespace):
    pass


class Point:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z


class Marker:
    ADD = 0
    LINE_LIST = 5

    def __init__(self):
        self.header = _NS(stamp=_NS(sec=0, nanosec=0), frame_id="")
        self.ns, self.id, self.type, self.action = "", 0, 0, 0
        self.pose = _NS(position=Point(), orientation=_NS(x=0.0, y=0.0, z=0.0, w=0.0))
        self.scale = _NS(x=0.0, y=0.0, z=0.0)
        self.color = _NS(r=0.0, g=0.0, b=0.0, a=0.0)
        self.lifetime = _NS(sec=0, nanosec=0)
        self.frame_locked = False
        self.points = []


class Odometry:
    def __init__(self):
        self.header = _NS(stamp=_NS(sec=0, nanosec=0), frame_id="")
        self.pose = _NS(pose=_NS(position=Point(), orientation=_NS(x=0.0, y=0.0, z=0.0, w=1.0)))


class String:
    def __init__(self, data=""):
        self.data = data


class _Pub:
    def __init__(self, topic):
        self.topic, self.sent = topic, []

    def publish(self, m):
        self.sent.append(m)


class _Logger:
    def __init__(self):
        self.lines = []

    def info(self, m): self.lines.append(m)
    def warn(self, m): self.lines.append(m)
    warning = warn
    def error(self, m): self.lines.append(m)


class Node:
    def __init__(self, name, **kw):
        self.name = name
        self.subs, self.pubs, self.timers, self.logger = {}, {}, [], _Logger()

    def create_subscription(self, typ, topic, cb, qos, **k): self.subs[topic] = cb
    def create_publisher(self, typ, topic, qos, **k):
        self.pubs[topic] = _Pub(topic)
        return self.pubs[topic]
    def create_timer(self, period, cb, **k): self.timers.append((period, cb))
    def get_logger(self): return self.logger
    def get_clock(self): return _NS(now=lambda: _NS(to_msg=lambda: _NS(sec=777, nanosec=1)))
    def destroy_node(self): pass


def _stub_modules():
    m = {n: types.ModuleType(n) for n in ("rclpy", "rclpy.node", "rclpy.signals", "geometry_msgs", "geometry_msgs.msg",
                                         "nav_msgs", "nav_msgs.msg", "std_msgs", "std_msgs.msg",
                                         "visualization_msgs", "visualization_msgs.msg")}
    m["rclpy.node"].Node = Node
    m["rclpy.signals"].SignalHandlerOptions = _NS(NO=0)
    m["geometry_msgs.msg"].Point = Point
    m["nav_msgs.msg"].Odometry = Odometry
    m["std_msgs.msg"].String = String
    m["visualization_msgs.msg"].Marker = Marker
    return m


with mock.patch.dict(sys.modules, _stub_modules()):
    sys.modules.pop("auto_grid", None)
    import auto_grid as AG
sys.modules.pop("auto_grid", None)


class Source(unittest.TestCase):
    SRC = SRC_PATH.read_text()

    def test_topics_and_frames_per_source(self):
        self.assertIn("/svg/commander_status", self.SRC)
        self.assertIn("/svg/viz/grid", self.SRC)
        self.assertIn('"map"', self.SRC)
        self.assertIn("/{drone}/cuvslam/odometry", self.SRC)
        self.assertIn("/{drone}/cuvslam/grid", self.SRC)
        self.assertIn("{drone}/cuvslam_odom", self.SRC)
        self.assertIn("--source", self.SRC)
        self.assertIn("--drone", self.SRC)

    def test_marker_look(self):
        self.assertIn("Marker.LINE_LIST", self.SRC)
        self.assertIn("0.02", self.SRC)
        self.assertIn("0.6", self.SRC)
        self.assertRegex(self.SRC, r"1\.0\s*/\s*RATE_HZ|create_timer\(1\.0")

    def test_signals_are_ours(self):
        self.assertIn("rclpy.init(signal_handler_options=SignalHandlerOptions.NO)", self.SRC)
        self.assertIn("signal.signal(signal.SIGTERM", self.SRC)
        self.assertIn("signal.signal(signal.SIGINT", self.SRC)
        self.assertRegex(self.SRC, r"spin_once\(node, timeout_sec=0\.05\)")


def _odom(x, y, sec=42, nsec=7):
    m = Odometry()
    m.header.stamp = _NS(sec=sec, nanosec=nsec)
    m.pose.pose.position = Point(x, y, 0.5)
    return m


def _status(*drones):
    return String(json.dumps({"drones": [{"name": n, "position": p} for n, p in drones]}))


class OdomMode(unittest.TestCase):
    def setUp(self):
        self.node = AG.AutoGridNode(source="odom", drone="drone_1")
        self.pub = self.node.pubs["/drone_1/cuvslam/grid"]
        self.tick = self.node.timers[0][1]

    def test_nothing_before_first_position(self):
        self.tick()
        self.assertEqual(self.pub.sent, [])

    def test_one_odometry_publishes_a_line_list_with_its_stamp(self):
        self.node.subs["/drone_1/cuvslam/odometry"](_odom(1.0, 2.0))
        self.tick()
        m = self.pub.sent[-1]
        self.assertEqual(m.header.frame_id, "drone_1/cuvslam_odom")
        self.assertEqual((m.header.stamp.sec, m.header.stamp.nanosec), (42, 7))
        self.assertEqual(m.type, Marker.LINE_LIST)
        self.assertGreater(len(m.points), 0)
        self.assertEqual(len(m.points) % 2, 0)
        self.assertTrue(all(p.z == 0.0 for p in m.points))
        self.assertAlmostEqual(m.scale.x, 0.02)
        self.assertAlmostEqual(m.color.a, 0.6)
        self.assertAlmostEqual(m.color.r, 0x4f / 255)
        self.assertAlmostEqual(m.color.b, 0xbb / 255)

    def test_publishes_every_tick_even_unchanged(self):
        self.node.subs["/drone_1/cuvslam/odometry"](_odom(1.0, 2.0))
        self.tick(); self.tick(); self.tick()
        self.assertEqual(len(self.pub.sent), 3)

    def test_growth_is_logged_once_per_growth(self):
        cb = self.node.subs["/drone_1/cuvslam/odometry"]
        cb(_odom(0, 0)); n = len(self.node.logger.lines)
        cb(_odom(1, 1))
        self.assertEqual(len(self.node.logger.lines), n)
        cb(_odom(30, 0))
        self.assertEqual(len(self.node.logger.lines), n + 1)
        self.assertIn("grid", self.node.logger.lines[-1])


class StatusMode(unittest.TestCase):
    def setUp(self):
        self.node = AG.AutoGridNode(source="status", drone="drone_1")
        self.pub = self.node.pubs["/svg/viz/grid"]
        self.cb = self.node.subs["/svg/commander_status"]
        self.tick = self.node.timers[0][1]

    def test_two_drones_feed_one_grid_in_map_with_clock_stamp(self):
        self.cb(_status(("drone_1", [0.0, 0.0, 1.0]), ("drone_2", [40.0, -3.0, 1.0])))
        self.tick()
        m = self.pub.sent[-1]
        self.assertEqual(m.header.frame_id, "map")
        self.assertEqual((m.header.stamp.sec, m.header.stamp.nanosec), (777, 1))
        self.assertEqual(len(m.points) % 2, 0)
        self.assertGreaterEqual(max(p.x for p in m.points), 40.0)       # drone_2 made it grow
        self.assertEqual(len(self.pub.sent), 1)

    def test_bad_json_neither_throws_nor_publishes(self):
        for bad in ("{not json", "[]", "null", '{"drones": 5}', '{"drones": [{"position": "x"}, 3, {"position": [null, 1]}]}'):
            self.cb(String(bad))
        self.tick()
        self.assertEqual(self.pub.sent, [])

    def test_missing_position_is_skipped(self):
        self.cb(_status(("drone_1", None), ("drone_2", [1.0, 1.0, 0.0])))
        self.tick()
        self.assertEqual(len(self.pub.sent), 1)


if __name__ == "__main__":
    unittest.main()
