#!/usr/bin/env python3
"""tools/teleop/pad_check.py — the Logitech F310 pad check for the REAL drone's gamepad teleop.

Runs IN the robot container (tools/real.sh copies it with pad_core.py to /tmp/svg_real/). It starts a PRIVATE joy_node
(node svg_pad_check_joy, topic /svg_pad_check/joy), so nothing it reads reaches safe_teleop or the commander. Every
decision is in pad_core.py; this file only gathers facts, prompts and cleans up. Its joy_node is stopped on every exit.

  python3 pad_check.py --pad f310 [--static] [--record FILE]

Exit: 0 PASS · 1 FAIL · 2 cannot check (no terminal for the stick test, ROS or the profile does not import) · 3 Ctrl-C.
"""
import argparse, json, os, signal, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pad_core as P

DISCOVERY_S = 2.0       # ROS graph discovery before the environment check
FIRST_MSG_S = 5.0       # joy_node must open the pad and publish within this
REST_S = 1.0            # rest samples for the static check
STEP_S = 15.0           # per guided move
COLLECT_S = 0.5         # samples kept after a move is seen
BACK_TO_REST_S = 10.0   # between moves
NODE = "svg_pad_check_joy"
TOPIC = "/svg_pad_check/joy"
JOY_LOG = "/tmp/svg_real/pad_check_joy.log"
PROMPTS = {"right stick UP": "Push the RIGHT stick UP all the way and hold it.",
           "right stick LEFT": "Push the RIGHT stick LEFT all the way and hold it.",
           "left stick UP": "Push the LEFT stick UP all the way and hold it.",
           "left stick LEFT": "Push the LEFT stick LEFT all the way and hold it.",
           "press LB": "Press and hold LB (the left shoulder button)."}


class Stop(Exception):
    def __init__(self, code, reason):
        super().__init__(reason)
        self.code, self.reason = code, reason


def say(line=""):
    print(line, flush=True)


def check(v):
    """Print a verdict line; a FAIL ends the check with exit 1."""
    say(v.line())
    if not v.ok:
        raise Stop(1, v.text)
    return v


def driver_of(js):
    try:
        return os.path.basename(os.readlink("/sys/class/input/%s/device/device/driver" % js))
    except OSError:
        return None


def processes():
    out, me = [], os.getpid()
    for pid in os.listdir("/proc"):
        if not pid.isdigit() or int(pid) == me:
            continue
        try:
            with open("/proc/%s/cmdline" % pid, "rb") as f:
                out.append(f.read().replace(b"\0", b" ").decode(errors="replace").strip())
        except OSError:
            pass
    return [p for p in out if p]


def stop_joy(proc):
    if proc is None or proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGINT)
        proc.wait(timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass


def interrupted(*_):
    raise KeyboardInterrupt


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pad", default="f310", choices=sorted(P.PADS))
    ap.add_argument("--static", action="store_true", help="the checks that need no operator action only")
    ap.add_argument("--record", metavar="FILE", help="write every /joy sample as JSON lines")
    a = ap.parse_args(argv)
    spec = P.PADS[a.pad]
    joy, node, rec, rclpy = None, None, None, None
    for sig in (signal.SIGTERM, signal.SIGHUP):                    # a closed terminal or a kill also stops our joy_node
        signal.signal(sig, interrupted)
    try:
        if not a.static and not sys.stdin.isatty():
            raise Stop(2, "the stick test needs a terminal — run it in a terminal tab (or --static)")
        try:
            import rclpy
            from rclpy.signals import SignalHandlerOptions
            from sensor_msgs.msg import Joy
            from svg_ground_control.safe_teleop.controllers import get_controller
            profile = get_controller(spec.profile)
        except Exception as e:                                    # ImportError, KeyError: cannot check
            raise Stop(2, "cannot check — ROS or the %s profile did not import (%s)" % (spec.profile, e))
        mapping = profile.mapping_parameters()
        drv = dict(profile.drivers[0].parameters)
        rec = open(a.record, "w") if a.record else None

        # 1  USB + driver: no ROS needed
        try:
            with open("/proc/bus/input/devices") as f:
                devs = P.parse_input_devices(f.read())
        except OSError:
            devs = []
        verdicts, js = P.judge_usb(devs, spec)
        for v in verdicts:
            check(v)
        check(P.judge_driver(driver_of(js), spec))

        # 2  nothing else may read the pad into the stack
        rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
        node = rclpy.create_node("svg_pad_check")
        end = time.monotonic() + DISCOVERY_S
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.1)
        pubs = ["%s/%s" % (i.node_namespace.rstrip("/"), i.node_name) for i in node.get_publishers_info_by_topic("/joy")]
        nodes = ["%s/%s" % (ns.rstrip("/"), n) for n, ns in node.get_node_names_and_namespaces()]
        check(P.judge_environment(pubs, nodes, processes()))

        # 3  our own joy_node, pinned by name, on a private topic
        try:                                                       # a stale one from a check that was killed hard
            subprocess.run(["pkill", "-f", "__node:=" + NODE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass
        samples = []

        def on_joy(m):
            s = {"t": time.monotonic(), "axes": [float(x) for x in m.axes], "buttons": [int(b) for b in m.buttons]}
            samples.append(s)
            if rec:
                rec.write(json.dumps(dict(s, phase=phase[0])) + "\n")
        phase = ["static"]
        node.create_subscription(Joy, TOPIC, on_joy, 50)
        os.makedirs(os.path.dirname(JOY_LOG), exist_ok=True)
        log = open(JOY_LOG, "w")
        cmd = ["ros2", "run", "joy", "joy_node", "--ros-args", "-r", "__node:=" + NODE, "-r", "joy:=" + TOPIC,
               "-p", "device_name:=" + spec.sdl_name,
               "-p", "deadzone:=%s" % float(drv.get("deadzone", 0.05)),
               "-p", "autorepeat_rate:=%s" % float(drv.get("autorepeat_rate", 20.0))]
        joy = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                               env=dict(os.environ, RCUTILS_LOGGING_BUFFERED_STREAM="1"))

        def spin_for(seconds, until=None):
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                rclpy.spin_once(node, timeout_sec=0.05)
                if until is not None and until():
                    return True
            return False

        def opened():
            with open(JOY_LOG, errors="replace") as f:
                return P.parse_opened_name(f.read())
        spin_for(FIRST_MSG_S, lambda: bool(samples) and opened() is not None)
        o = P.judge_opened(opened(), spec)
        if not o.ok:
            check(o)
        if not samples:
            check(P.Verdict(False, "joy_node opened the pad but published nothing within 5 s"))
        sh = P.judge_shape(len(samples[-1]["axes"]), len(samples[-1]["buttons"]), spec)
        if not sh.ok:
            check(sh)
        say("PASS %s; %s" % (o.text, sh.text))
        del samples[:]
        spin_for(REST_S)
        rest = check(P.judge_rest(list(samples), spec)).data
        if a.static:
            say("PAD CHECK: STATIC PASS — the stick test is still to do: tools/real.sh pad")
            return 0

        # 4  guided: the operator moves each stick once
        steps = P.steps_for(spec, mapping)
        say()
        say("Stick test: %d moves. Do not press MODE. Let go after each PASS." % len(steps))
        for n, step in enumerate(steps, 1):
            phase[0] = step.name
            say("%d/%d  %s" % (n, len(steps), PROMPTS[step.name]))
            del samples[:]
            if not spin_for(STEP_S, lambda: any(P.movement(s, rest) for s in samples)):
                check(P.judge_step(step, list(samples), rest, spec))          # NO MOVEMENT on <step>
            spin_for(COLLECT_S)
            check(P.judge_step(step, list(samples), rest, spec))
            say("     let go")
            phase[0] = "back to rest"
            calm = {"since": None}

            def settled():
                if not samples:
                    return False
                if P.at_rest(samples[-1], rest):
                    calm["since"] = calm["since"] or time.monotonic()
                    return time.monotonic() - calm["since"] >= 0.3
                calm["since"] = None
                return False
            if not spin_for(BACK_TO_REST_S, settled):
                raise Stop(1, "the pad did not come back to rest within 10 s after %s — let go of it and run again" % step.name)
        say(P.PASS_LINE)
        return 0
    except Stop as s:
        say(P.fail_line(s.reason))
        return s.code
    except KeyboardInterrupt:
        say(P.fail_line("stopped (Ctrl-C) — the check did not finish"))
        return 3
    finally:
        stop_joy(joy)
        if rec:
            rec.close()
        if node is not None:
            node.destroy_node()
        if rclpy is not None and rclpy.ok():
            rclpy.try_shutdown()


if __name__ == "__main__":
    sys.exit(main())
