#!/usr/bin/env python3
# SIMULATOR ONLY: never point this at a real drone; real flights follow docs/PREFLIGHT.md and docs/RUNBOOK.md.
# (Those are the repository's own docs/ pages. The script checks this itself: see "Simulator check" below.)
"""Designed velocity-step session for ONE drone in the AirStack simulator (S1 Task 5). SIM ONLY (repository iron rule 9).

Inside the robot container (record_steps.sh copies this file and configs/s1.toml next to each other):
    python3 virtual_stick.py --config s1.toml [--drone drone_1] [--flown-json steps_flown.json]
  takeoff -> wait until the commander reports the drone ACTIVE ("holding takeoff position") -> start -> publish
  geometry_msgs/TwistStamped on /svg/<drone>/teleop_command (world ENU, frame_id "map") at 20 Hz wall:
  for each step of [steps] ZERO_GAP_S of zero, then the step for hold_s; ZERO_GAP_S of zero after the last one ->
  zeros -> land -> wait until the commander reports the drone IDLE. Every exit path publishes zeros and lands.
On the host (no ROS needed; rclpy is imported inside run_session only):
    python3 virtual_stick.py --config configs/s1.toml --print-plan
    python3 virtual_stick.py --config configs/s1.toml --plan-json runs/<name>/steps.json

Plan order: repeat, speed, axis, sign with signs [1, -1] — every + step is followed by its - twin, so the drone comes
back near its start after each pair and a -z step always follows the +z step of the same size.
Simulator check (first, before any publish or service call): every drone in /svg/commander_status must have mode
"sim" (the commander's per-drone `mode`, swarm_commander.py:1210), the target drone must be listed, and no topic name on
the domain may contain "/fmu/" (PX4's real-drone bridge; tools/sim.sh treats it as a real-drone signal too). A status
that cannot be read within STATUS_WAIT_S counts as a failure. A failure is a REFUSAL in capitals ("REAL DRONE MAY BE
PRESENT"), nothing is sent (no publish, no service call, not even land) and the exit code is 67. The check runs again
just before the first publish.
Safety (the configs fly with the fences off):
  - floor, predictive: a -z step is skipped unless z_onset - |vz| * hold_s * FLOOR_PREDICT_SCALE >= FLOOR_M +
    FLOOR_MARGIN_M; during a -z step the command is cut to zero once z - |vz| * (FLOOR_LAG_S + |vz| / FLOOR_DECEL_MPS2)
    < FLOOR_M (lag + braking distance);
  - one commander: before takeoff and during the steps, /svg/commander_status must have exactly one publisher, its
    messages must keep the pid/node of the first one (pinned), and /svg/<drone>/teleop_command must have no subscriber
    other than swarm_commander, the bag recorder (rosbag2_recorder*) and foxglove_bridge*;
  - freshness: odometry older than ODOM_STALE_S or commander status older than STATUS_STALE_S is a flight error.
Nothing is published on the teleop topic (zeros included) until the one-commander check has passed before takeoff.
A refusal before takeoff flies nothing (exit 1); a flight error after takeoff zeroes and lands (exit 4). A SECOND
COMMANDER or foreign status (more than one /svg/commander_status publisher, a status from another process, or an
unexpected teleop subscriber) is answered with NOTHING: no zeros and no land — /swarm_commander/land reaches every
commander on the domain — and exit 67 (record_steps.sh then leaves the simulator up and does not run `down`). `land` is
called whenever this stick has SENT a takeoff request (st["took_off"], set just before the call: a request that timed
out, or a signal during the call, may still have put the drone in the air; `land` on an IDLE drone is a harmless "no
airborne drone to land"). Precedence: a second commander (exit 67) always wins — then nothing is sent, not even land.
Times are wall seconds; the AirStack simulator ran about 1.9 times faster than wall clock in the S1 run (1.907, drifting
1.73-1.97: records/2026-11-15_s1_fit_v0_record.md) (vehicle = wall x scale).

Exit codes: 0 all steps flown and landed; 1 refused before the takeoff request (nothing sent); 2 bad arguments or
config; 3 stopped by SIGINT/SIGTERM (landed if a takeoff request was sent); 4 a flight error from the takeoff request on,
including a takeoff refused or unanswered (landed); 67 a second commander or foreign status on the domain, or the simulator
check failed (a real drone may be present) (nothing sent: no zeros, no land)."""
from __future__ import annotations

import argparse
import json
import math
import signal
import sys
import threading
import time
import tomllib

ZERO_GAP_S = 2.0          # zero command before every step and after the last one (wall s)
RATE_HZ = 20.0            # publish rate of the virtual stick (wall), = the commander's control_rate_hz
FLOOR_M = 0.5             # odometry z (m) the drone must never be driven below
FLOOR_MARGIN_M = 0.3      # extra margin for the skip rule (m)
FLOOR_PREDICT_SCALE = 1.4  # time scale for the skip rule; below the measured 1.73-1.97, so the live cut rule backs it
FLOOR_LAG_S = 0.7         # sim velocity-loop lag used by the cut rule (s)
FLOOR_DECEL_MPS2 = 5.0    # braking used by the cut rule (m/s^2) = teleop_accel_mps2
ODOM_STALE_S = 1.0        # odometry older than this during the steps = flight error (wall s)
STATUS_STALE_S = 1.0      # commander status older than this during the steps = flight error (wall s)
STATUS_WAIT_S = 60.0      # commander status with the drone IDLE and odometry fresh
SUB_WAIT_S = 30.0         # the commander subscribed to the teleop topic
HOLD_WAIT_S = 90.0        # takeoff -> ACTIVE ("holding takeoff position")
START_TRIES, START_EVERY_S = 15, 2.0
LAND_WAIT_S = 60.0        # land -> IDLE (the commander disarms, then declares IDLE)
CALL_TIMEOUT_S = 20.0     # wait for a /swarm_commander/* service answer (wall s)
STATUS_TOPIC = "/svg/commander_status"
REAL_TOPIC_MARK = "/fmu/"     # any topic name containing this = a real drone's PX4 bridge may be on the domain
BENIGN_SUBSCRIBERS = ("rosbag2_recorder", "foxglove_bridge")   # read-only listeners of the teleop topic
AXES = {"x": 0, "y": 1, "z": 2}


# ------------------------------------------------------------------------------------------------- plan (no ROS)
def load_steps(path: str) -> dict:
    """The [steps] table of an S1 config (configs/s1.toml)."""
    with open(path, "rb") as f:
        return tomllib.load(f)["steps"]


def build_plan(steps: dict, gap_s: float = ZERO_GAP_S) -> list[dict]:
    """[steps] -> list of N step dicts (N = repeats x speeds x axes x signs), times in wall s from the first zero gap.

    Each dict: index (1-based), repeat (1-based), axis, sign, speed_mps, velocity_enu_mps (3,), zero_before_s,
    hold_s, onset_s, end_s. Raises ValueError on a config the session must not fly."""
    speeds, axes, signs = list(steps["speeds_mps"]), list(steps["axes"]), list(steps["signs"])
    hold_s, repeats = float(steps["hold_s"]), int(steps["repeats"])
    if signs != [1, -1]:
        raise ValueError(f"signs must be [1, -1] (each + step before its - twin), got {signs}")
    if not speeds or any(not (isinstance(s, (int, float)) and 0.0 < s <= 5.0) for s in speeds):
        raise ValueError(f"speeds_mps must be numbers in (0, 5], got {speeds}")
    if not axes or any(a not in AXES for a in axes):
        raise ValueError(f"axes must be a non-empty subset of x, y, z, got {axes}")
    if not (0.0 < hold_s <= 10.0) or repeats < 1:
        raise ValueError(f"hold_s must be in (0, 10] and repeats >= 1, got {hold_s}, {repeats}")
    plan, t = [], 0.0
    for rep in range(repeats):
        for speed in speeds:
            for axis in axes:
                for sign in signs:
                    v = [0.0, 0.0, 0.0]
                    v[AXES[axis]] = float(sign) * float(speed)
                    onset = t + gap_s
                    plan.append({"index": len(plan) + 1, "repeat": rep + 1, "axis": axis, "sign": int(sign),
                                 "speed_mps": float(speed), "velocity_enu_mps": v, "zero_before_s": gap_s,
                                 "hold_s": hold_s, "onset_s": onset, "end_s": onset + hold_s})
                    t = onset + hold_s
    return plan


def plan_total_s(plan: list[dict]) -> float:
    """Wall seconds from the first zero gap to the end of the zero after the last step (the same gap as before it)."""
    return plan[-1]["end_s"] + plan[-1]["zero_before_s"] if plan else 0.0


def format_plan(plan: list[dict]) -> str:
    n = len(plan)
    gap = plan[0]["zero_before_s"] if plan else ZERO_GAP_S
    lines = [f"step {s['index']:2d}/{n} repeat {s['repeat']} axis {s['axis']} sign {s['sign']:+d} speed "
             f"{s['speed_mps']:.2f} m/s zero {s['zero_before_s']:.1f} s then hold {s['hold_s']:.1f} s "
             f"onset {s['onset_s']:6.1f} s end {s['end_s']:6.1f} s" for s in plan]
    lines.append(f"plan: {n} steps, {gap:.1f} s zero before each and after the last, "
                 f"total {plan_total_s(plan):.1f} s wall (vehicle time = wall x the run's time scale, ~1.9)")
    return "\n".join(lines)


def plan_json(plan: list[dict], config_path: str, steps: dict) -> dict:
    return {"config": config_path, "steps_table": steps, "zero_gap_s": plan[0]["zero_before_s"],
            "hold_s": float(steps["hold_s"]), "rate_hz": RATE_HZ,
            "frame": "world ENU (frame_id map), /svg/<drone>/teleop_command",
            "time_base": "wall s from the first zero gap after start; vehicle time = wall x the run's time scale",
            "total_s": plan_total_s(plan), "steps": plan}


def floor_skip(z_m: float, vz_mps: float, hold_s: float) -> bool:
    """True when a descending step must not start: its predicted bottom would be below FLOOR_M + FLOOR_MARGIN_M."""
    return vz_mps < 0.0 and not (z_m - abs(vz_mps) * hold_s * FLOOR_PREDICT_SCALE >= FLOOR_M + FLOOR_MARGIN_M)


def floor_cut(z_m: float, vz_mps: float) -> bool:
    """True when a descending step must be cut now: lag + braking distance would take the drone below FLOOR_M."""
    return vz_mps < 0.0 and not (z_m - abs(vz_mps) * (FLOOR_LAG_S + abs(vz_mps) / FLOOR_DECEL_MPS2) >= FLOOR_M)


# --------------------------------------------------------------------------------------------------- flight (ROS)
class Stop(Exception):
    pass


def say(text: str) -> None:
    print("[%.6f] %s" % (time.time(), text), flush=True)


def run_session(plan: list[dict], drone: str, flown_json: str | None) -> int:
    import rclpy
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.qos import qos_profile_sensor_data
    from geometry_msgs.msg import TwistStamped
    from nav_msgs.msg import Odometry
    from std_msgs.msg import String
    from std_srvs.srv import Trigger
    try:
        from rclpy.signals import SignalHandlerOptions
    except ImportError:
        SignalHandlerOptions = None

    teleop_topic = f"/svg/{drone}/teleop_command"
    odom_topic = f"/{drone}/odometry_conversion/odometry"
    lock = threading.Lock()
    cmd = [0.0, 0.0, 0.0]
    seen = {"z": math.nan, "odom_t": -math.inf, "drone": None, "status": None, "status_t": -math.inf,
            "ident": None, "foreign": None}
    flown = []

    def on_signal(signum, _frame):
        raise Stop(signal.Signals(signum).name)

    if SignalHandlerOptions is not None:
        rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    else:
        rclpy.init()
    old_handlers = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)
    node = rclpy.create_node("svg_s1_virtual_stick")
    pub = node.create_publisher(TwistStamped, teleop_topic, 10)

    def set_cmd(v=(0.0, 0.0, 0.0)):
        with lock:
            cmd[:] = [float(c) for c in v]

    def message():
        m = TwistStamped()
        m.header.stamp = node.get_clock().now().to_msg()
        m.header.frame_id = "map"
        with lock:
            m.twist.linear.x, m.twist.linear.y, m.twist.linear.z = cmd
        return m

    def on_odom(msg):
        with lock:
            seen["z"], seen["odom_t"] = float(msg.pose.pose.position.z), time.monotonic()

    def on_status(msg):
        try:
            j = json.loads(msg.data)
        except ValueError:
            return
        ident = (j.get("pid"), j.get("node"))
        d = next((x for x in j.get("drones", []) if x.get("name") == drone), None)
        with lock:
            if seen["ident"] is None:
                seen["ident"] = ident              # pinned: every later snapshot must come from this process
            elif ident != seen["ident"]:
                seen["foreign"] = ident
                return
            seen["status"], seen["drone"], seen["status_t"] = j, d, time.monotonic()

    def drone_state():
        with lock:
            d = seen["drone"]
        return (d or {}).get("state")

    def odom():
        with lock:
            return seen["z"], time.monotonic() - seen["odom_t"]

    def one_commander():
        """None when exactly one commander is visible, else the reason. A reason that means a SECOND commander or a
        foreign process (not merely a missing one) is also stored in st["second"]: the session then sends nothing."""
        n_pub = node.count_publishers(STATUS_TOPIC)
        if n_pub > 1:
            st["second"] = f"{STATUS_TOPIC} has {n_pub} publishers (need exactly 1 commander)"
            return st["second"]
        if n_pub < 1:
            return f"{STATUS_TOPIC} has no publisher (our commander is gone)"
        subs = [i.node_name for i in node.get_subscriptions_info_by_topic(teleop_topic)]
        others = [n for n in subs if not n.startswith(BENIGN_SUBSCRIBERS)]
        if others == []:
            return f"{teleop_topic} has no swarm_commander subscriber (our commander is gone)"
        if others != ["swarm_commander"]:
            st["second"] = f"{teleop_topic} subscribers {sorted(subs)} (need swarm_commander once, plus only {BENIGN_SUBSCRIBERS})"
            return st["second"]
        with lock:
            if seen["foreign"] is not None:
                st["second"] = f"{STATUS_TOPIC} from a second process {seen['foreign']} (pinned {seen['ident']})"
                return st["second"]
        return None

    def health(in_flight=True):
        """None when the flight may go on, else the flight error."""
        z, age = odom()
        if age > ODOM_STALE_S:
            return f"odometry stale ({age:.2f} s)"
        with lock:
            s_age = time.monotonic() - seen["status_t"]
            active = bool((seen["status"] or {}).get("mission_active"))
        if s_age > STATUS_STALE_S:
            return f"commander status stale ({s_age:.2f} s)"
        why = one_commander()
        if why:
            return why
        if in_flight and (drone_state() != "ACTIVE" or not active):
            return f"{drone} state {drone_state()} / mission_active {active}"
        return None

    def wait_for(pred, timeout_s, every_s=0.1):
        t_end = time.monotonic() + timeout_s
        while time.monotonic() < t_end:
            if pred():
                return True
            time.sleep(every_s)
        return pred()

    def call(name, timeout_s=None):
        timeout_s = CALL_TIMEOUT_S if timeout_s is None else timeout_s
        cli = node.create_client(Trigger, f"/swarm_commander/{name}")
        try:
            if not cli.wait_for_service(timeout_sec=5.0):
                return False, "service not available"
            fut = cli.call_async(Trigger.Request())
            t_end = time.monotonic() + timeout_s
            while not fut.done() and time.monotonic() < t_end:
                time.sleep(0.05)
            res = fut.result() if fut.done() else None
            return (bool(res.success), res.message) if res is not None else (False, "no answer")
        finally:
            node.destroy_client(cli)

    st = {"took_off": False, "reached": 0, "may_publish": False, "second": None}

    def tick():
        """20 Hz: publish the current command — only once the one-commander check has passed (st["may_publish"])."""
        if st["may_publish"] and not st["second"]:
            pub.publish(message())

    node.create_subscription(Odometry, odom_topic, on_odom, qos_profile_sensor_data)
    node.create_subscription(String, STATUS_TOPIC, on_status, 10)
    node.create_timer(1.0 / RATE_HZ, tick)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    spin = threading.Thread(target=executor.spin, daemon=True)
    spin.start()

    def not_sim():
        """None when the commander says every drone is simulated and no /fmu/ topic is visible, else the reason.
        Anything that cannot be read counts as a reason (fail closed)."""
        with lock:
            status = seen["status"]
        if not isinstance(status, dict):
            return f"no readable {STATUS_TOPIC} (the drone's mode cannot be checked)"
        drones = status.get("drones")
        if not isinstance(drones, list) or not any(isinstance(x, dict) and x.get("name") == drone for x in drones):
            return f"{drone} is not in {STATUS_TOPIC} (its mode cannot be checked)"
        modes = {str(x.get("name")): x.get("mode") for x in drones if isinstance(x, dict)}
        bad = {n: m for n, m in modes.items() if m != "sim"}
        if bad:
            return "commander status mode " + ", ".join(f"{n} mode {m!r}" if m is not None else f"{n} mode None"
                                                         for n, m in sorted(bad.items())) + " (need \"sim\" for every drone)"
        try:
            names = [str(t[0]) for t in node.get_topic_names_and_types()]
        except Exception as e:  # noqa: BLE001 -- the topic list could not be read
            return f"topic list unreadable: {type(e).__name__}: {e}"
        real = sorted(t for t in names if REAL_TOPIC_MARK in t)
        if real:
            return f"real-drone topic(s) on the domain: {', '.join(real[:5])}"
        return None

    def refuse_real(why):
        say(f"!! REFUSED: REAL DRONE MAY BE PRESENT: {why} — NOTHING SENT (NO PUBLISH, NO SERVICE CALL); exit 67. "
            "THIS TOOL IS SIMULATOR ONLY: REAL FLIGHTS FOLLOW docs/PREFLIGHT.md AND docs/RUNBOOK.md")
        return 67

    def wait_until_t(t_abs, step):
        """Hold the current command until monotonic t_abs; a health failure returns the flight error."""
        while time.monotonic() < t_abs:
            why = health()
            if why:
                return f"{why} ({step})"
            time.sleep(0.01)
        return None

    def fly() -> int:
        # 0  simulator check, before anything is sent: a status that never arrives counts as a refusal
        wait_for(lambda: seen["status"] is not None, STATUS_WAIT_S, 0.05)
        why = not_sim()
        if why:
            return refuse_real(why)
        say(f"simulator check: {drone} mode sim, no {REAL_TOPIC_MARK} topic on the domain")
        # 1  commander up, drone IDLE with fresh odometry, one commander, the plan inside the commander's speed cap
        if not wait_for(lambda: (drone_state() == "IDLE" and bool((seen["drone"] or {}).get("odom_fresh"))),
                        STATUS_WAIT_S, 0.05):
            say(f"refused: {STATUS_TOPIC} never showed {drone} IDLE with fresh odometry in {STATUS_WAIT_S:.0f} s")
            return 1
        with lock:
            vmax = float(((seen["status"] or {}).get("tuning") or {}).get("teleop_max_speed_mps") or 0.0)
            scen, ident = (seen["status"] or {}).get("scenario"), seen["ident"]
        top = max(s["speed_mps"] for s in plan)
        say(f"commander: scenario={scen} teleop_max_speed_mps={vmax} (plan max {top} m/s); pinned pid/node {ident}")
        if top > vmax + 1e-6:
            say(f"refused: plan speed {top} m/s exceeds teleop_max_speed_mps {vmax} (the commander would cap it)")
            return 1
        if not wait_for(lambda: "swarm_commander" in [i.node_name for i in node.get_subscriptions_info_by_topic(teleop_topic)],
                        SUB_WAIT_S, 0.05):
            say(f"refused: swarm_commander not subscribed to {teleop_topic} within {SUB_WAIT_S:.0f} s")
            return 1
        why = one_commander()
        if why:
            say(f"refused: {why}")
            return 1
        me = node.get_name()
        others = sorted({i.node_name for i in node.get_publishers_info_by_topic(teleop_topic) if i.node_name != me})
        if others:
            say(f"refused: other publisher(s) on {teleop_topic}: {', '.join(others)} (a relay or keyboard would "
                "interleave with the steps)")
            return 1
        why = not_sim()                                   # again, just before the first publish and the takeoff call
        if why:
            return refuse_real(why)
        z0, age = odom()
        say(f"pre-takeoff: {drone} state={drone_state()} z={z0:.2f} m (odometry age {age:.2f} s); one commander: "
            "publishing from now on")
        st["may_publish"] = True

        # 2  takeoff -> ACTIVE ("holding takeoff position") -> start
        # "may be airborne" from the moment the request is sent: a timed-out but accepted request, or a signal during
        # the call, must still be landed (the pre-takeoff line above is what record_steps.sh keys its abort landing on)
        st["took_off"] = True
        ok, msg = call("takeoff")
        say(f"takeoff: success={ok} message={msg!r}")
        if not ok:
            return 4
        if not wait_for(lambda: drone_state() == "ACTIVE", HOLD_WAIT_S, 0.05):
            say(f"flight error: {drone} not ACTIVE (holding takeoff position) {HOLD_WAIT_S:.0f} s after takeoff "
                f"(state {drone_state()})")
            return 4
        z0, _ = odom()
        say(f"holding takeoff position: z={z0:.2f} m")
        for _ in range(START_TRIES):
            ok, msg = call("start")
            if ok:
                break
            time.sleep(START_EVERY_S)
        say(f"start: success={ok} message={msg!r}")
        if not ok or not wait_for(lambda: bool((seen["status"] or {}).get("mission_active")), 10.0, 0.05):
            say("flight error: start not accepted or mission_active never true")
            return 4
        why = health()
        if why:
            say(f"flight error before the first step: {why}")
            return 4

        # 3  the steps, on an absolute wall schedule from t0 (no drift)
        t0 = time.monotonic()
        say(f"steps: {len(plan)} steps start (t0); schedule in steps.json")
        for s in plan:
            set_cmd()
            why = wait_until_t(t0 + s["onset_s"], f"zero before step {s['index']}")
            if why:
                say(f"flight error: {why}")
                return 4
            v = s["velocity_enu_mps"]
            z, _ = odom()
            if floor_skip(z, v[2], s["hold_s"]):
                say(f"FLOOR GUARD: step {s['index']} not flown (z={z:.2f} m, predicted bottom "
                    f"{z - abs(v[2]) * s['hold_s'] * FLOOR_PREDICT_SCALE:.2f} m < {FLOOR_M + FLOOR_MARGIN_M:.2f} m)")
                flown.append(dict(index=s["index"], onset_unix_s=None, end_unix_s=None, cut=True, skipped=True,
                                  z_onset_m=z))
                continue
            set_cmd(v)
            rec = dict(index=s["index"], onset_unix_s=time.time(), end_unix_s=None, cut=False, skipped=False,
                       z_onset_m=z)
            flown.append(rec)
            st["reached"] = s["index"]
            say(f"step {s['index']}/{len(plan)} onset axis={s['axis']} sign={s['sign']:+d} speed={s['speed_mps']:.2f} "
                f"z={z:.2f}")
            while time.monotonic() < t0 + s["end_s"]:
                why = health()
                if why:
                    set_cmd()
                    say(f"flight error: {why} (during step {s['index']})")
                    return 4
                z, _ = odom()
                if not rec["cut"] and floor_cut(z, v[2]):
                    set_cmd()
                    rec["cut"] = True
                    say(f"FLOOR GUARD: step {s['index']} cut at z={z:.2f} m")
                time.sleep(0.01)
            set_cmd()
            rec["end_unix_s"] = time.time()
            say(f"step {s['index']}/{len(plan)} release z={odom()[0]:.2f}")
        why = wait_until_t(t0 + plan_total_s(plan), "zero after the last step")
        if why:
            say(f"flight error: {why}")
            return 4
        say("steps: done")
        return 0

    rc = 1
    try:
        rc = fly()
    except Stop as e:
        rc = 3
        say(f"stopped by {e}")
    except Exception as e:  # noqa: BLE001 -- zeros and a landing first, then the report
        rc = 4 if st["took_off"] else 1
        say(f"error: {type(e).__name__}: {e}")
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)      # the landing below must not be interrupted
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        set_cmd()
        if st["took_off"] and not st["second"]:
            # R4-m1: a takeoff that timed out or was interrupted gets here without health() having run since the
            # request — re-run the one-commander check before any zeros or land. A failed check or an unreadable count
            # counts as a second commander: send nothing, exit 67.
            try:
                why = one_commander()
            except Exception as e:  # noqa: BLE001 -- the count could not be read
                why = f"commander count unreadable: {type(e).__name__}: {e}"
            if why:
                st["second"] = f"{why} (re-check before the abort land)"
        if st["second"]:
            # zeros and land would reach the other commander too (land is served by every commander on the domain)
            st["may_publish"] = False
            rc = 67
            say(f"!! SECOND COMMANDER OR FOREIGN STATUS ON THE DOMAIN: {st['second']} — NOTHING SENT (NO ZEROS, NO LAND); "
                "exit 67")
        elif st["may_publish"]:
            for _ in range(int(RATE_HZ)):                  # 1 s of zeros from this thread too
                try:
                    pub.publish(message())
                except Exception:  # noqa: BLE001
                    break
                time.sleep(1.0 / RATE_HZ)
            say("zeros published")
        if st["took_off"] and not st["second"]:          # land what this stick may have taken off; never past a second commander
            ok, msg = call("land")
            say(f"land: success={ok} message={msg!r}")
            if wait_for(lambda: drone_state() == "IDLE", LAND_WAIT_S, 0.05):
                say(f"landed: {drone} IDLE z={odom()[0]:.2f} m")
            else:
                say(f"landed: NOT confirmed — {drone} state {drone_state()} after {LAND_WAIT_S:.0f} s")
                rc = rc if rc else 4
        say(f"steps reached: {st['reached']}/{len(plan)}")
        if flown_json:
            try:
                with open(flown_json, "w") as f:
                    json.dump({"drone": drone, "reached": st["reached"], "rc": rc, "steps": flown}, f, indent=1)
            except OSError as e:
                say(f"could not write {flown_json}: {e}")
        for step in (executor.shutdown, lambda: spin.join(5.0), node.destroy_node,
                     getattr(rclpy, "try_shutdown", rclpy.shutdown)):
            try:
                step()
            except Exception:  # noqa: BLE001
                pass
        for s, h in old_handlers.items():
            signal.signal(s, h)
        say(f"virtual_stick: exit {rc}")
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", required=True, help="S1 config with a [steps] table (configs/s1.toml)")
    ap.add_argument("--drone", default="drone_1")
    ap.add_argument("--print-plan", action="store_true", help="print the steps and exit (host, no ROS)")
    ap.add_argument("--plan-json", help="write the planned steps to this JSON file and exit (host, no ROS)")
    ap.add_argument("--flown-json", help="write the flown steps (wall onset/end, floor skips/cuts) here at the end")
    a = ap.parse_args(argv)
    if not a.drone.replace("_", "").isalnum():
        print(f"virtual_stick: bad --drone {a.drone!r}", file=sys.stderr)
        return 2
    try:
        steps = load_steps(a.config)
        plan = build_plan(steps)
    except (OSError, KeyError, ValueError, tomllib.TOMLDecodeError) as e:
        print(f"virtual_stick: bad config {a.config}: {e}", file=sys.stderr)
        return 2
    if a.print_plan or a.plan_json:
        if a.print_plan:
            print(format_plan(plan))
        if a.plan_json:
            with open(a.plan_json, "w") as f:
                json.dump(plan_json(plan, a.config, steps), f, indent=1)
        return 0
    print(format_plan(plan), flush=True)
    return run_session(plan, a.drone, a.flown_json)


if __name__ == "__main__":
    sys.exit(main())
