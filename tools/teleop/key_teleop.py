#!/usr/bin/env python3
"""Keyboard teleop window: publishes sensor_msgs/Joy on /joy as a gamepad would, so CMU's safe_teleop flies
the drone with every safety it has (fences, hold on release, speed cap). Sim only (NEAR-789).

Runs inside the robot container (rclpy + Tk on the container's display); start it with `tools/sim.sh keys`.

    arrows forward/back + slide (pitch/roll) · W/S up/down · A/D turn · 1/2/3 = 25/50/100 % of top speed

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
HELP = ("Arrows  ↑ / ↓  forward / back (pitch)      ← / →  slide left / right (roll)\n"
        "W / S  up / down      A / D  turn left / right      (Shift/Ctrl and Q/E work too)\n"
        "1 / 2 / 3  = 25 / 50 / 100 % of top speed.  No stick lock on the keyboard.\n"
        "Let go of every key and the drone holds.  Click away or minimise and every key is let go.")


def read_safe_teleop(node, timeout_s=2.0):
    """{'teleop_controller': str, 'deadzone': float} from the running /safe_teleop, or None if it does not answer."""
    from rcl_interfaces.srv import GetParameters
    import rclpy
    cli = node.create_client(GetParameters, "/safe_teleop/get_parameters")
    if not cli.wait_for_service(timeout_sec=timeout_s):
        return None
    req = GetParameters.Request()
    req.names = ["teleop_controller", "deadzone"]
    fut = cli.call_async(req)
    rclpy.spin_until_future_complete(node, fut, timeout_sec=timeout_s)
    if not fut.done() or fut.result() is None:
        return None
    vals = fut.result().values
    return {"teleop_controller": vals[0].string_value, "deadzone": vals[1].double_value or K.DEADZONE}


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
    tk.Label(root, text=HELP, justify="left", font=("TkFixedFont", 11), padx=12, pady=8).pack()
    status = tk.StringVar(value="hold (no key)")
    tk.Label(root, textvariable=status, font=("TkFixedFont", 14, "bold"), fg="#0072B2", pady=6).pack()
    tk.Label(root, text=info, fg="#5F6368").pack()
    warn = tk.StringVar(value="")
    tk.Label(root, textvariable=warn, fg="#B00020", pady=4).pack()

    root.bind("<KeyPress>", lambda e: state.press(e.keysym, time.monotonic()))
    root.bind("<KeyRelease>", lambda e: state.release(e.keysym, time.monotonic()))
    root.bind("<FocusOut>", lambda e: state.all_up())
    root.bind("<Unmap>", lambda e: state.all_up())

    closed = {"done": False}
    last_count = {"t": 0.0, "n": 0}

    def tick():
        if stop["now"]:
            close()
            return
        try:
            publish()
            now = time.monotonic()
            status.set(state.status(now))
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
