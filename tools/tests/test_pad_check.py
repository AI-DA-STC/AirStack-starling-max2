# tools/tests/test_pad_check.py — pad_check.main() run for real against a fake ROS (CHG-0066): fake rclpy, sensor_msgs
# and svg_ground_control modules (CMU's real controllers.py), a fake `ros2` on PATH that writes joy_node's log line and
# stays alive until it is stopped, and fixture /joy streams replayed as the subscription's messages. Time is a fake clock
# that advances with every spin, so a 15 s timeout costs no wall time. No ROS, no docker, no pad.
import importlib.util, json, os, pathlib, signal, sys, tempfile, time, types, unittest
from unittest import mock
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "teleop"))
import pad_core as P
import pad_check as PC

FIX = HERE / "fixtures" / "pad"
CONTROLLERS = HERE.parents[1] / "AirStack/robot/ros_ws/src/svg_ground_control/svg_ground_control/safe_teleop/controllers.py"
REST = [0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
FAKE_ROS2 = r'''#!/bin/bash
trap 'exit 0' INT TERM
if [ "${FAKE_OPENED}" = "__none__" ]; then
  echo "[ERROR] [0.0] [svg_pad_check_joy]: Could not get joystick with name Logitech Gamepad F310"
else
  echo "[INFO] [0.0] [svg_pad_check_joy]: Opened joystick: ${FAKE_OPENED}.  deadzone: 0.050000"
fi
echo "$*" > "$FAKE_DIR/joy.args"
echo $$ > "$FAKE_DIR/joy.pid"
while :; do sleep 0.05; done
'''


def fixture(name):
    return P.load_jsonl((FIX / name).read_text())


def held(axis=None, button=None, value=1.0):
    a, b = list(REST), [0] * 11
    if axis is not None:
        a[axis] = value
    if button is not None:
        b[button] = 1
    return [{"axes": a, "buttons": b}]


DEFAULT_STREAMS = {"rest": fixture("joy_rest.jsonl"), "let go": fixture("joy_rest.jsonl"),
                   "right stick UP": fixture("joy_right_up.jsonl"), "right stick LEFT": held(axis=3),
                   "left stick UP": held(axis=1), "left stick LEFT": held(axis=0), "press LB": held(button=4)}


class Joy:
    def __init__(self, axes=(), buttons=()):
        self.axes, self.buttons = list(axes), list(buttons)


class Info:
    def __init__(self, name):
        self.node_name, self.node_namespace = name, "/"


class FakeNode:
    def __init__(self, h):
        self.h = h

    def create_subscription(self, msg_type, topic, cb, qos):
        self.h.sub, self.h.sub_topic = cb, topic

    def get_publishers_info_by_topic(self, topic):
        return [Info(n) for n in (self.h.joy_pubs if topic == "/joy" else self.h.check_pubs)]

    def get_node_names_and_namespaces(self):
        return [("svg_pad_check", "/")]

    def destroy_node(self):
        self.h.destroyed = True


class Harness:
    """The fake ROS world; the pad's stream follows the check's own prompts (rest until a move is asked for)."""

    def __init__(self, tmp, streams=None, joy_pubs=(), check_pubs=("svg_pad_check_joy",)):
        self.tmp, self.t, self.sub, self.inited, self.destroyed = tmp, 0.0, None, False, False
        self.streams = dict(DEFAULT_STREAMS, **(streams or {}))
        self.state, self.idx, self.out = "rest", 0, []
        self.joy_pubs, self.check_pubs = list(joy_pubs), list(check_pubs)
        self.pidfile = os.path.join(tmp, "joy.pid")

    def clock(self):
        return self.t

    def say(self, line=""):
        self.out.append(line)
        for name, text in PC.PROMPTS.items():
            if line.endswith(text):
                self.state, self.idx = name, 0
        if line.strip() == "let go":
            self.state, self.idx = "let go", 0

    def spin_once(self, node, timeout_sec=None):
        if self.sub is not None:
            end = time.time() + 5                               # time starts when the fake joy_node is up
            while not os.path.exists(self.pidfile) and time.time() < end:
                time.sleep(0.005)
            stream = self.streams.get(self.state) or []
            if stream:
                s = stream[min(self.idx, len(stream) - 1)]; self.idx += 1
                self.sub(Joy(s["axes"], s["buttons"]))
        self.t += timeout_sec or 0.05

    def modules(self):
        rclpy = types.ModuleType("rclpy")
        rclpy.init = lambda **kw: setattr(self, "inited", True)
        rclpy.ok = lambda: self.inited
        rclpy.try_shutdown = lambda: setattr(self, "inited", False)
        rclpy.create_node = lambda name: FakeNode(self)
        rclpy.spin_once = self.spin_once
        signals = types.ModuleType("rclpy.signals")
        signals.SignalHandlerOptions = types.SimpleNamespace(NO="no")
        rclpy.signals = signals
        msg = types.ModuleType("sensor_msgs.msg"); msg.Joy = Joy
        sensor = types.ModuleType("sensor_msgs"); sensor.msg = msg
        spec = importlib.util.spec_from_file_location("svg_ground_control.safe_teleop.controllers", CONTROLLERS)
        ctrl = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {spec.name: ctrl}):          # dataclasses look the module up while it loads
            spec.loader.exec_module(ctrl)
        svg = types.ModuleType("svg_ground_control"); st = types.ModuleType("svg_ground_control.safe_teleop")
        svg.safe_teleop, st.controllers = st, ctrl
        return {"rclpy": rclpy, "rclpy.signals": signals, "sensor_msgs": sensor, "sensor_msgs.msg": msg,
                "svg_ground_control": svg, "svg_ground_control.safe_teleop": st,
                "svg_ground_control.safe_teleop.controllers": ctrl}


class MainRuns(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(); self.tmp = self._tmp.name
        os.makedirs(os.path.join(self.tmp, "bin"))
        f = pathlib.Path(self.tmp, "bin", "ros2"); f.write_text(FAKE_ROS2); f.chmod(0o755)
        self._sig = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGHUP)}

    def tearDown(self):
        for s, h in self._sig.items():
            signal.signal(s, h)
        self._tmp.cleanup()

    def run_main(self, *argv, opened="Logitech Gamepad F310", tty=True, extra=(), **kw):
        h = Harness(self.tmp, **kw)
        env = {"PATH": os.path.join(self.tmp, "bin") + ":" + os.environ["PATH"], "FAKE_DIR": self.tmp, "FAKE_OPENED": opened}
        patches = [mock.patch.dict(sys.modules, h.modules()), mock.patch.dict(os.environ, env),
                   mock.patch.object(PC, "clock", h.clock), mock.patch.object(PC, "say", h.say),
                   mock.patch.object(PC, "stdin_is_tty", lambda: tty),
                   mock.patch.object(PC, "read_input_devices", lambda: (FIX / "proc_x_mode.txt").read_text()),
                   mock.patch.object(PC, "driver_of", lambda js: "xpad"),
                   mock.patch.object(PC, "processes", lambda: []), mock.patch.object(PC, "kill_stale", lambda: None),
                   mock.patch.object(PC, "JOY_LOG", os.path.join(self.tmp, "joy.log"))] + list(extra)
        for p in patches:
            p.start()
        try:
            rc = PC.main(["--pad", "f310", *argv])
        finally:
            for p in reversed(patches):
                p.stop()
        return rc, h

    def assert_joy_stopped(self):
        pid = int(pathlib.Path(self.tmp, "joy.pid").read_text())
        end = time.time() + 3
        while time.time() < end:
            try:
                os.killpg(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.02)
        self.fail("the fake joy_node (process group %d) is still running" % pid)

    def test_full_pass(self):
        rc, h = self.run_main()
        self.assertEqual(rc, 0, h.out); self.assertEqual(h.out[-1], P.PASS_LINE)
        for n in ("right stick UP", "right stick LEFT", "left stick UP", "left stick LEFT", "press LB"):
            self.assertTrue(any(l.startswith("PASS %s:" % n) for l in h.out), (n, h.out))
        self.assertIn('PASS joy_node opened "Logitech Gamepad F310"; 8 axes 11 buttons', h.out)
        self.assertTrue(h.destroyed); self.assertFalse(h.inited)
        self.assert_joy_stopped()

    def test_the_private_joy_node_is_pinned_by_name_with_the_profiles_tuning(self):
        rc, h = self.run_main("--static")
        args = pathlib.Path(self.tmp, "joy.args").read_text().strip()
        self.assertEqual(args, "run joy joy_node --ros-args -r __node:=svg_pad_check_joy -r joy:=/svg_pad_check/joy "
                               "-p device_name:=Logitech Gamepad F310 -p deadzone:=0.05 -p autorepeat_rate:=20.0")
        self.assertEqual(h.sub_topic, "/svg_pad_check/joy")
        self.assert_joy_stopped()

    def test_static_only_pass(self):
        rc, h = self.run_main("--static", tty=False)
        self.assertEqual(rc, 0, h.out)
        self.assertEqual(h.out[-1], "PAD CHECK: STATIC PASS — the stick test is still to do: tools/real.sh pad")
        self.assertFalse(any("Push the" in l or "Press and hold" in l for l in h.out), h.out)
        self.assert_joy_stopped()

    def test_mode_on_at_the_left_stick_step(self):
        rc, h = self.run_main(streams={"left stick UP": fixture("joy_mode_on_left_up.jsonl")})
        self.assertEqual(rc, 1, h.out)
        self.assertEqual(h.out[-1], "PAD CHECK: FAIL — do not fly: MODE ON — press MODE (light off) and run again")
        self.assert_joy_stopped()

    def test_wrong_shape(self):
        six = [{"axes": [0.0] * 6, "buttons": [0] * 12}]
        rc, h = self.run_main(streams={"rest": six})
        self.assertEqual(rc, 1, h.out)
        self.assertEqual(h.out[-1], "PAD CHECK: FAIL — do not fly: 6 axes/12 buttons — not the X-mode layout (8/11)")
        self.assert_joy_stopped()

    def test_joy_node_opened_nothing(self):
        rc, h = self.run_main(opened="__none__", streams={"rest": []})
        self.assertEqual(rc, 1, h.out)
        self.assertEqual(h.out[-1], 'PAD CHECK: FAIL — do not fly: joy_node opened nothing within 5 s (name pin "Logitech Gamepad F310")')
        self.assert_joy_stopped()

    def test_joy_node_opened_another_name(self):
        rc, h = self.run_main(opened="Logitech Logitech Dual Action")
        self.assertEqual(rc, 1, h.out)
        self.assertIn('joy_node opened "Logitech Logitech Dual Action", not the pinned "Logitech Gamepad F310"', h.out[-1])
        self.assert_joy_stopped()

    def test_no_movement(self):
        rc, h = self.run_main(streams={"right stick UP": fixture("joy_rest.jsonl")},
                              extra=[mock.patch.object(PC, "STEP_S", 3.0)])
        self.assertEqual(rc, 1, h.out)
        self.assertEqual(h.out[-1], "PAD CHECK: FAIL — do not fly: NO MOVEMENT on right stick UP")
        self.assertLess(h.t, 2 + 5 + 1 + 3 + 1)                               # the injected 3 s, not 15 s
        self.assert_joy_stopped()

    def test_not_back_to_rest(self):
        rc, h = self.run_main(streams={"let go": held(axis=4)})
        self.assertEqual(rc, 1, h.out)
        self.assertEqual(h.out[-1], "PAD CHECK: FAIL — do not fly: the pad did not come back to rest within 10 s after "
                                    "right stick UP — let go of it and run again")
        self.assert_joy_stopped()

    def test_a_second_publisher_on_the_check_topic(self):
        rc, h = self.run_main("--static", check_pubs=("svg_pad_check_joy", "svg_pad_check_joy"))
        self.assertEqual(rc, 1, h.out)
        self.assertEqual(h.out[-1], "PAD CHECK: FAIL — do not fly: another publisher on the check topic — is a second pad check running?")
        self.assert_joy_stopped()

    def test_an_unexpected_error_is_cannot_check_and_stops_the_joy_node(self):
        boom = mock.patch.object(P, "judge_rest", side_effect=ValueError("boom"))
        rc, h = self.run_main("--static", extra=[boom])
        self.assertEqual(rc, 2, h.out)
        self.assertEqual(h.out[-1], "PAD CHECK: FAIL — do not fly: cannot check: ValueError: boom")
        self.assert_joy_stopped()

    def test_a_joy_publisher_refuses_before_any_joy_node_starts(self):
        rc, h = self.run_main("--static", joy_pubs=("joy_node",))
        self.assertEqual(rc, 1, h.out); self.assertIn("1 publisher(s) on /joy (/joy_node)", h.out[-1])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "joy.pid")))

    def test_ctrl_c_stops_the_joy_node_exit_3(self):
        def interrupt(*a, **k):
            raise KeyboardInterrupt
        rc, h = self.run_main("--static", extra=[mock.patch.object(P, "judge_rest", side_effect=interrupt)])
        self.assertEqual(rc, 3, h.out); self.assertIn("stopped (Ctrl-C)", h.out[-1])
        self.assert_joy_stopped()


if __name__ == "__main__":
    unittest.main()
