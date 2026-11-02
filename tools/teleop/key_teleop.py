#!/usr/bin/env python3
"""Keyboard teleop window: publishes sensor_msgs/Joy on /joy as a gamepad would, so CMU's safe_teleop flies
the drone with every safety it has (fences, hold on release, speed cap). Sim only (NEAR-789).

Runs inside the robot container (rclpy + Tk on the container's display); start it with `tools/sim.sh keys`.

    arrows forward/back + slide (pitch/roll) · W/S climb/descend · A/D turn · Space STOP · F Drive/Room mode · 1/2/3 = 25/50/100 % of top speed

Safety: a key counts as released on its release event, when the window loses focus or is minimised, or after
1 s with no event from it (a held key auto-repeats; a silent one had its release swallowed). It publishes at
20 Hz, so if it dies safe_teleop's 0.5 s /joy timeout stops the drone. Closing it, Ctrl-C, SIGTERM or an error
in its loop publish zeros first. It reads safe_teleop's live controller profile and dead zone, refuses a profile
that does not match, and warns while any other node publishes on /joy."""
from __future__ import annotations

import argparse
import pathlib
import signal
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import keymap as K  # noqa: E402

RATE_HZ = 20.0
DISCOVERY_S = 1.0            # let DDS discovery find other /joy publishers before the first count
FLIP_ANSWER_S = 2.0          # an F request unanswered this long was lost (sent before DDS matched): dropped, F works again
LIVE_READ_ANSWER_S = 5.0     # the same for the periodic safe_teleop parameter read
HELP = ("Arrows  ↑ / ↓  forward / back (pitch)      ← / →  slide left / right (roll)\n"
        "W / S  climb / descend      A / D  turn (yaw) left / right\n"
        "1 / 2 / 3  = 25 / 50 / 100 % of top speed.  No stick lock on the keyboard.\n"
        "Let go of every key and the drone holds.  Click away or minimise and every key is let go.")


def read_safe_teleop(node, timeout_s=2.0):
    """{'teleop_controller': str, 'deadzone': float, 'max_speed_mps': float|None} from the running /safe_teleop, or None if it does not answer."""
    from rcl_interfaces.srv import GetParameters
    import rclpy
    cli = node.create_client(GetParameters, "/safe_teleop/get_parameters")
    if not cli.wait_for_service(timeout_sec=timeout_s):
        return None
    req = GetParameters.Request()
    req.names = ["teleop_controller", "deadzone", "max_speed_mps"]
    fut = cli.call_async(req)
    rclpy.spin_until_future_complete(node, fut, timeout_sec=timeout_s)
    if not fut.done() or fut.result() is None:
        return None
    vals = fut.result().values
    return {"teleop_controller": vals[0].string_value, "deadzone": vals[1].double_value or K.DEADZONE,
            "max_speed_mps": (vals[2].double_value or None) if len(vals) > 2 else None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--profile", default="dragonrise_usb", choices=sorted(K.PROFILES),
                    help="the teleop_controller safe_teleop runs (teleop_single.yaml: dragonrise_usb)")
    ap.add_argument("--topic", default="/joy")
    a = ap.parse_args(argv)

    import tkinter as tk
    import rclpy
    from rclpy.signals import SignalHandlerOptions
    from sensor_msgs.msg import Joy

    # Our own SIGINT/SIGTERM handling: rclpy's would invalidate the publisher under a still-open window, so the
    # zeros could not go out. A signal only sets a flag; the next tick publishes zeros and closes the window.
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    stop = {"now": False}
    signal.signal(signal.SIGINT, lambda *_: stop.update(now=True))
    signal.signal(signal.SIGTERM, lambda *_: stop.update(now=True))
    node = rclpy.create_node("key_teleop")

    live = read_safe_teleop(node)
    deadzone = K.DEADZONE
    max_speed = live["max_speed_mps"] if live is not None else None
    if live is not None:
        controller = live["teleop_controller"]
        if controller != a.profile:
            print("key_teleop: REFUSING — safe_teleop runs teleop_controller '%s' but this window would send the "
                  "'%s' layout (forward would move the wrong axis). Use: tools/sim.sh keys --profile %s"
                  % (controller, a.profile, controller), flush=True)
            node.destroy_node()
            rclpy.try_shutdown()
            return 2
        deadzone = live["deadzone"]
        info = "safe_teleop: %s, dead zone %.2f" % (controller, deadzone)
    else:
        info = "safe_teleop not found yet — start it first (TELEOP §4); assuming %s, dead zone %.2f" % (a.profile, deadzone)
    print("key_teleop: " + info, flush=True)

    end = time.monotonic() + DISCOVERY_S
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.1)
    pub = node.create_publisher(Joy, a.topic, 10)
    state = K.KeyState(a.profile, deadzone=deadzone)

    def publish(axes=None):
        msg = Joy()
        msg.header.stamp = node.get_clock().now().to_msg()
        msg.axes = axes if axes is not None else state.axes(time.monotonic())
        msg.buttons = state.buttons()
        pub.publish(msg)

    root = tk.Tk()
    root.title("Keyboard teleop — keep this window focused")
    mode_var, sentence_var, footer_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
    mode_label = tk.Label(root, textvariable=mode_var, font=("TkFixedFont", 13, "bold"), pady=4)
    mode_label.pack()
    tk.Label(root, textvariable=sentence_var, justify="left").pack()
    tk.Label(root, text=HELP, justify="left", font=("TkFixedFont", 11), padx=12, pady=8).pack()
    tk.Label(root, textvariable=footer_var, justify="left", font=("TkFixedFont", 11)).pack()
    status = tk.StringVar(value="hold (no key)")
    tk.Label(root, textvariable=status, font=("TkFixedFont", 14, "bold"), fg="#0072B2", pady=6).pack()
    tk.Label(root, text=info, fg="#5F6368").pack()
    warn = tk.StringVar(value="")
    tk.Label(root, textvariable=warn, fg="#B00020", pady=4).pack()

    from rcl_interfaces.msg import Parameter, ParameterType, ParameterValue
    from rcl_interfaces.srv import SetParameters
    from std_msgs.msg import String
    last_status = {"line": None, "rx": 0.0}
    node.create_subscription(String, "/teleop_frame/status",
                             lambda m: last_status.update(line=m.data, rx=time.monotonic()), 10)
    flip_cli = node.create_client(SetParameters, "/teleop_frame/set_parameters")
    flip_pending = {"fut": None, "target": None, "t": 0.0}

    def request_flip(status_dict):
        """Ask the relay for the other mode; never blocks (call_async, result checked in a later tick)."""
        if status_dict is None or flip_pending["fut"] is not None:
            print("key_teleop: F ignored — no relay status yet" if status_dict is None else "key_teleop: F ignored — previous request still open", flush=True)
            return
        target = K.flip_target(status_dict)
        if target is None:
            print("key_teleop: F ignored — relay has no input to flip", flush=True)
            return
        if not flip_cli.service_is_ready():           # a request sent before DDS matched is dropped and never answered
            print("key_teleop: F ignored — the relay's parameter service is not reachable yet; press F again", flush=True)
            return
        req = SetParameters.Request()
        req.parameters = [Parameter(name="stick_frame", value=ParameterValue(type=ParameterType.PARAMETER_STRING, string_value=target))]
        flip_pending.update(fut=flip_cli.call_async(req), target=target, t=time.monotonic())

    root.bind("<KeyPress>", lambda e: state.press(e.keysym, time.monotonic()))
    root.bind("<KeyRelease>", lambda e: state.release(e.keysym, time.monotonic()))
    root.bind("<FocusOut>", lambda e: state.all_up())
    root.bind("<Unmap>", lambda e: state.all_up())

    closed = {"done": False}
    last_count = {"t": 0.0, "n": 0}
    from rcl_interfaces.srv import GetParameters
    live_cli = node.create_client(GetParameters, "/safe_teleop/get_parameters")
    live_read = {"fut": None, "t": time.monotonic()}      # max_speed_mps follows the commander live (Foxglove dropdown)

    def drop(cli, fut):
        """Forget an unanswered request (rclpy keeps it in the client's pending list otherwise)."""
        try:
            cli.remove_pending_request(fut)
        except Exception:                            # older rclpy has no remove_pending_request: the future is just dropped
            pass

    def tick():
        nonlocal max_speed
        if stop["now"]:
            close()
            return
        try:
            publish()
            now = time.monotonic()
            status.set(state.status(now, max_speed))
            seen = last_status["line"] is not None and now - last_status["rx"] <= 2.0
            sd = K.parse_status(last_status["line"]) if last_status["line"] is not None else None
            bold, sentence, colour = K.header_lines(sd, seen)
            mode_var.set(bold)
            sentence_var.set(sentence)
            mode_label.configure(fg=colour)
            footer_var.set(K.footer_line(sd if seen else None))
            if state.flip_requested:
                state.flip_requested = False
                request_flip(sd if seen else None)
            fut = flip_pending["fut"]
            if fut is not None and fut.done():
                res = fut.result() if fut.exception() is None else None
                ok = bool(res and res.results and res.results[0].successful)
                print("key_teleop: F -> stick_frame=%s %s" % (flip_pending["target"], "accepted" if ok else "FAILED"), flush=True)
                flip_pending.update(fut=None, target=None)
            elif fut is not None and now - flip_pending["t"] > FLIP_ANSWER_S:
                print("key_teleop: F -> stick_frame=%s no answer in %.0f s — dropped; press F again" % (flip_pending["target"], FLIP_ANSWER_S), flush=True)
                drop(flip_cli, fut)
                flip_pending.update(fut=None, target=None)
            if live_read["fut"] is None and now - live_read["t"] >= 2.0 and live_cli.service_is_ready():
                req = GetParameters.Request()
                req.names = ["teleop_controller", "deadzone", "max_speed_mps"]
                live_read.update(fut=live_cli.call_async(req), t=now)
            elif live_read["fut"] is not None and live_read["fut"].done():
                if live_read["fut"].exception() is None:
                    vals = live_read["fut"].result().values
                    if len(vals) > 2:
                        max_speed = vals[2].double_value or max_speed
                        state.deadzone = vals[1].double_value or state.deadzone
                live_read["fut"] = None
            elif live_read["fut"] is not None and now - live_read["t"] > LIVE_READ_ANSWER_S:
                drop(live_cli, live_read["fut"])                 # lost request: drop it, the next read starts in 2 s
                live_read.update(fut=None, t=now)
            if now - last_count["t"] >= 1.0:
                n = max(0, node.count_publishers(a.topic) - 1)      # minus our own publisher
                if n != last_count["n"]:
                    print("key_teleop: %d other publisher(s) on %s" % (n, a.topic), flush=True)
                last_count.update(t=now, n=n)
                warn.set("WARNING: %d other publisher(s) on %s (a pad or joy_node?) — the drone mixes both" % (n, a.topic)
                         if n else "")
            rclpy.spin_once(node, timeout_sec=0.0)
        except Exception as e:                         # never a frozen window that looks alive
            print("key_teleop: loop error %s: %s — publishing zeros and closing" % (type(e).__name__, e), flush=True)
            close()
            return
        root.after(int(1000 / RATE_HZ), tick)

    def close():
        if closed["done"]:
            return
        closed["done"] = True
        state.all_up()
        for _ in range(5):                          # zeros first, so the drone holds before /joy goes quiet
            try:
                publish([0.0] * K.N_AXES)
            except Exception:
                break
            time.sleep(1.0 / RATE_HZ)
        print("key_teleop: closed, zeros published", flush=True)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    root.after(0, tick)
    print("key_teleop: window open (%s on %s); close it or Ctrl-C here to stop" % (a.profile, a.topic), flush=True)
    try:
        root.mainloop()
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
