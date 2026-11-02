#!/bin/bash
# One-drone teleop-frame flight (NEAR-789). SIM ONLY (iron rule 9).
# Runs INSIDE the robot container: tools/sim.sh test copies it to $S together with tools/teleop/frame.py and
# tools/teleop/teleop_frame.py (the relay).
# Usage: fly.sh [--check] <gap_s> [FRAC=0.25] [PUSH_S=2.0]
#   gap_s = settle after each yaw (test.env DURATION_S); push speed = FRAC x the commander's teleop_max_speed_mps.
# Flow: start the relay (Drive mode, BODY) in the background -> wait for /teleop_frame/status -> print
# `relay: stick_frame=<value>` from the relay's own start line -> takeoff -> retry start (as yaw_step/fly.sh) -> one rclpy
# program that publishes /svg/drone_1/teleop_command_stick (the relay's input; safe_teleop and the keyboard are not in the
# loop) at 20 Hz: for heading 0 90 180 270 it yaws there (closed loop on odometry, +-3 deg), settles gap_s, pushes
# forward (vx) for PUSH_S, releases and waits 3.5 s, stamping `[<unix s>] push <deg> onset|release heading=<deg>`; then it
# sets the relay's stick_frame to world (SetParameters), waits for `frame=world` in the status, yaws to 180 and pushes once
# more (`push world …`) -> land -> `landed:`.
# Heading convention (the same in gates.py and the test): operator heading h, 0 = +X, CLOCKWISE positive, [0, 360)
# (frame.heading_deg_from_yaw, the relay's status line). ENU yaw = -h. angular.z > 0 turns counter-clockwise, so it LOWERS h.
# Exit paths: the program publishes zeros for 1 s on normal exit, SIGINT/SIGTERM and any exception (try/finally); the
# bash trap publishes zeros on the stick topic again while the relay still runs, then stops the relay (it publishes a zero
# command itself on the way out). The commander's 0.5 s teleop_timeout_s zeroes the command anyway.
# fly-check: yes   (tools/sim.sh runs `fly.sh --check <args>` on the host before the stack starts: bad arguments never fly)
CHECK=0; [ "${1:-}" = --check ] && { CHECK=1; shift; }
bad(){ echo "fly.sh: $*" >&2; exit 2; }
[ $# -le 3 ] || bad "at most 3 arguments (gap frac push_s), got $# ($*)"
GAP=${1:-4}; FRAC=${2:-0.25}; PUSH=${3:-2.0}
NUM='[0-9]+([.][0-9]*)?'
[[ "$GAP" =~ ^$NUM$ ]] || bad "gap must be a number of seconds (got '$GAP')"
[[ "$FRAC" =~ ^$NUM$ ]] && awk -v f="$FRAC" 'BEGIN{exit !(f > 0 && f <= 1)}' || bad "FRAC must be a number in (0, 1] (got '$FRAC')"
[[ "$PUSH" =~ ^$NUM$ ]] && awk -v p="$PUSH" 'BEGIN{exit !(p > 0)}' || bad "PUSH_S must be a number of seconds > 0 (got '$PUSH')"
[ "$CHECK" = 1 ] && { echo "fly.sh: arguments ok (gap $GAP s, push $FRAC x teleop_max_speed_mps for $PUSH s)"; exit 0; }
HERE=$(cd "$(dirname "$0")" && pwd)
cd ~/AirStack/robot/ros_ws && source install/setup.bash >/dev/null 2>&1
STICK=/svg/drone_1/teleop_command_stick
# the yaml that diverts safe_teleop is a new file: a container that never rebuilt has no installed copy (checked before takeoff)
yaml="$(ros2 pkg prefix svg_ground_control 2>/dev/null)/share/svg_ground_control/config/teleop_single_ours.yaml"
[ -f "$yaml" ] || { echo "fly.sh: teleop_single_ours.yaml not installed — run bws && sws once"; exit 1; }
svc(){ timeout 20 ros2 service call /swarm_commander/$1 std_srvs/srv/Trigger 2>/dev/null | grep -o "success=[A-Za-z]*, message='[^']*'"; }
states(){ timeout 10 ros2 topic echo /svg/commander_status --once --field data 2>/dev/null | grep -v '^---' \
  | grep -oE '"(name|state)": *"[^"]*"|"position": *(\[[^]]*\]|null)' | tr -d '"' | sed 's/position: null/position: ?/' | paste -sd' '; }

# ---- the relay: ours from here on; every exit path publishes zeros and stops it
if pgrep -f 'teleop_frame\.py' >/dev/null 2>&1; then
  echo "[$(date +%T)] another teleop_frame relay is already running (pids $(pgrep -f 'teleop_frame\.py' | paste -sd' ')): two relays would both drive the commander — stop it (tools/sim.sh relay stop) and run the test again"
  exit 1
fi
RELAY_PID=""; CLEANED=0
cleanup() {
  [ "$CLEANED" = 1 ] && return; CLEANED=1
  if [ -n "$RELAY_PID" ] && kill -0 "$RELAY_PID" 2>/dev/null; then
    timeout 8 ros2 topic pub -t 10 -r 10 "$STICK" geometry_msgs/msg/TwistStamped "{header: {frame_id: map}}" >/dev/null 2>&1
    kill -TERM "$RELAY_PID" 2>/dev/null
    for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$RELAY_PID" 2>/dev/null || break; sleep 0.5; done
    kill -0 "$RELAY_PID" 2>/dev/null && kill -KILL "$RELAY_PID" 2>/dev/null
    echo "[$(date +%T)] relay stopped (zeros published on $STICK first)"
  fi
  # the relay's guard and mode lines, into the record before sim.sh deletes $S (a guard trip mid-push shows here)
  grep -E 'HEADING|heading guard|mode' "$HERE/teleop_frame.log" 2>/dev/null | tail -40 | sed 's/^/  relay log: /'
}
trap cleanup EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM
python3 "$HERE/teleop_frame.py" --drone drone_1 --stick-frame body > "$HERE/teleop_frame.log" 2>&1 &
RELAY_PID=$!
echo "[$(date +%T)] relay: started (pid $RELAY_PID, log $HERE/teleop_frame.log)"
st=$(timeout 30 ros2 topic echo --once --field data /teleop_frame/status 2>/dev/null | grep -m1 'frame=')
if [ -z "$st" ]; then
  echo "[$(date +%T)] relay status /teleop_frame/status not received within 30 s: nothing flown"
  tail -5 "$HERE/teleop_frame.log" 2>/dev/null | sed 's/^/  relay log: /'
  exit 1
fi
echo "[$(date +%T)] relay status: $st"
line=""; for _ in $(seq 1 20); do line=$(grep -m1 'teleop_frame: drone_1 stick_frame=' "$HERE/teleop_frame.log" 2>/dev/null) && break; sleep 0.5; done
sf=$(grep -o 'stick_frame=[a-z]*' <<< "$line" | head -1 | cut -d= -f2)
if [ -n "$sf" ]; then echo "[$(date +%T)] relay: stick_frame=$sf (start line: ${line##*teleop_frame: })"
else echo "[$(date +%T)] relay: start line not found in teleop_frame.log (the live mode is not on record)"; fi

# ---- fly
echo "[$(date +%T)] pre-takeoff: $(states)"
echo "[$(date +%T)] takeoff: $(svc takeoff)"
for i in $(seq 1 30); do sleep 3; r=$(svc start); case "$r" in success=True*) echo "[$(date +%T)] start: $r"; break;; esac
  [ "$i" = 30 ] && { echo "start never accepted: $r"; svc land; exit 1; }; done
echo "[$(date +%T)] pushes: settle $GAP s after each yaw, push $FRAC x teleop_max_speed_mps for $PUSH s"
# argv[1] carries "fly.sh": sim.sh's stop_fly (`pkill -f "fly\.sh"`) then stops this program too, never only the shell
PYTHONPATH="$HERE${PYTHONPATH:+:$PYTHONPATH}" python3 - teleop_frame/fly.sh "$GAP" "$FRAC" "$PUSH" <<'PY'
import math, os, re, signal, subprocess, sys, threading, time

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import TwistStamped
from nav_msgs.msg import Odometry
from std_msgs.msg import String
from rcl_interfaces.msg import Parameter, ParameterType, ParameterValue
from rcl_interfaces.srv import SetParameters
try:
    from rclpy.signals import SignalHandlerOptions
except ImportError:          # older rclpy: no option, rclpy's own handler stays
    SignalHandlerOptions = None
import frame as F            # tools/teleop/frame.py, copied next to fly.sh: the relay's own heading convention

GAP, FRAC, PUSH_S = float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
TOPIC = "/svg/drone_1/teleop_command_stick"   # the relay's input (safe_teleop's topic under teleop_single_ours.yaml)
OUT_TOPIC = "/svg/drone_1/teleop_command"     # the relay's output, the commander's input
ODOM = "/drone_1/odometry_conversion/odometry"
STATUS = "/teleop_frame/status"
RELAY, COMMANDER = "teleop_frame", "swarm_commander"
HEADINGS = (0, 90, 180, 270)
YAW_RATE, YAW_MIN_RATE, YAW_GAIN = 1.0, 0.15, 2.0     # rad/s; tapered inside the last ~29 deg so the +-3 deg stop holds
YAW_TOL_DEG, YAW_CAP_S = 3.0, 15.0
PARK_S = 3.5                  # gates read the parked point at release + 3 s
ODOM_FRESH_S = 0.5
SUB_WAIT_S, SUB_SETTLE_S = 30.0, 2.0
VMAX_FALLBACK = 2.0


class Stop(Exception):
    pass


def on_signal(signum, _frame):
    raise Stop(signal.Signals(signum).name)


def stamp(text):
    print("[%.6f] %s" % (time.time(), text), flush=True)


def say(text):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), text), flush=True)


cmd = {"wz": 0.0, "vx": 0.0}
seen = {"yaw": math.nan, "t": -1.0, "status": ""}
lock = threading.Lock()


def set_cmd(wz=0.0, vx=0.0):
    with lock:
        cmd["wz"], cmd["vx"] = float(wz), float(vx)


def heading_now():
    """Operator heading (deg, clockwise from +X) from the latest odometry, NaN when older than ODOM_FRESH_S."""
    with lock:
        yaw, t = seen["yaw"], seen["t"]
    return F.heading_deg_from_yaw(yaw) if time.monotonic() - t <= ODOM_FRESH_S else math.nan


def fmt(h):
    return "nan" if math.isnan(h) else "%.1f" % h


CHILD_ENV = dict(os.environ, ROS_AUTOMATIC_DISCOVERY_RANGE="LOCALHOST")
CHILD_ENV.pop("ROS_STATIC_PEERS", None)


def vmax():
    """The commander's teleop_max_speed_mps (read only), else VMAX_FALLBACK with a CAVEAT line."""
    try:
        r = subprocess.run(["bash", "-c", "ros2 param get /%s teleop_max_speed_mps" % COMMANDER], capture_output=True,
                           text=True, timeout=30, env=CHILD_ENV)
        m = re.search(r"value is:\s*([-+0-9.eE]+)", r.stdout)
        if m and float(m.group(1)) > 0:
            return float(m.group(1))
    except subprocess.TimeoutExpired:
        pass
    print("CAVEAT: teleop_frame fly.sh could not read /swarm_commander teleop_max_speed_mps; pushes used %.1f m/s x %.2f"
          % (VMAX_FALLBACK, FRAC), flush=True)
    return VMAX_FALLBACK


def wait_for_chain(node, pub):
    """True once the relay subscribes to TOPIC and the commander to OUT_TOPIC, then SUB_SETTLE_S more."""
    t_end = time.monotonic() + SUB_WAIT_S
    while time.monotonic() < t_end:
        a = [i.node_name for i in node.get_subscriptions_info_by_topic(TOPIC)]
        b = [i.node_name for i in node.get_subscriptions_info_by_topic(OUT_TOPIC)]
        if RELAY in a and COMMANDER in b and pub.get_subscription_count() > 0:
            say("%s subscribed to %s, %s to %s; %.0f s more before the first yaw" % (RELAY, TOPIC, COMMANDER, OUT_TOPIC, SUB_SETTLE_S))
            time.sleep(SUB_SETTLE_S)
            # a leftover safe_teleop or keyboard session also publishes here (zeros on a stale pad): it would interleave
            # with the pushes. Not a refusal: one CAVEAT line (sim.sh copies it into the record) and the flight goes on.
            me = node.get_name()
            others = sorted({"%s%s" % (i.node_namespace.rstrip("/") + "/" if i.node_namespace not in ("", "/") else "", i.node_name)
                             for i in node.get_publishers_info_by_topic(TOPIC) if i.node_name != me})
            if others:
                print("CAVEAT: other publisher(s) on %s: %s — their commands interleave with the test's pushes"
                      % (TOPIC, ", ".join(others)), flush=True)
            return True
        time.sleep(0.2)
    return False


def yaw_to(target):
    """Yaw to operator heading target (closed loop on odometry). (reached, heading)."""
    t_end = time.monotonic() + YAW_CAP_S
    while time.monotonic() < t_end:
        h = heading_now()
        if math.isnan(h):
            set_cmd()
            time.sleep(0.05)
            continue
        err = (target - h + 180.0) % 360.0 - 180.0           # + = turn clockwise = negative angular.z
        if abs(err) <= YAW_TOL_DEG:
            set_cmd()
            return True, h
        rate = min(YAW_RATE, max(YAW_MIN_RATE, YAW_GAIN * math.radians(abs(err))))
        set_cmd(wz=-math.copysign(rate, err))
        time.sleep(0.02)
    set_cmd()
    return False, heading_now()


def push(label, target, v):
    ok, h = yaw_to(target)
    say("yaw to %d: %s (heading %s)" % (target, "reached" if ok else "NOT reached in %.0f s" % YAW_CAP_S, fmt(h)))
    time.sleep(GAP)
    with lock:
        st = seen["status"]
    say("relay status before push %s: %s" % (label, st or "none"))
    stamp("push %s onset heading=%s" % (label, fmt(heading_now())))
    set_cmd(vx=v)
    time.sleep(PUSH_S)
    set_cmd()
    stamp("push %s release heading=%s" % (label, fmt(heading_now())))
    time.sleep(PARK_S)


def set_world(node):
    """stick_frame -> world through the relay's SetParameters service; True once the status says frame=world."""
    cli = node.create_client(SetParameters, "/%s/set_parameters" % RELAY)
    if not cli.wait_for_service(timeout_sec=10.0):
        say("relay set_parameters service not found: Room-mode push skipped")
        return False
    req = SetParameters.Request()
    req.parameters = [Parameter(name="stick_frame", value=ParameterValue(type=ParameterType.PARAMETER_STRING, string_value="world"))]
    fut = cli.call_async(req)
    t_end = time.monotonic() + 10.0
    while not fut.done() and time.monotonic() < t_end:
        time.sleep(0.05)
    res = fut.result() if fut.done() else None
    if res is None or not res.results or not res.results[0].successful:
        say("relay refused stick_frame=world (%s): Room-mode push skipped" % (res.results[0].reason if res and res.results else "no answer"))
        return False
    t_end = time.monotonic() + 5.0
    while time.monotonic() < t_end:
        with lock:
            st = seen["status"]
        if "frame=world" in st:
            say("relay status: frame=world (set through /%s/set_parameters)" % RELAY)
            return True
        time.sleep(0.1)
    say("relay status never showed frame=world within 5 s: Room-mode push skipped")
    return False


def main(node, pub):
    if not wait_for_chain(node, pub):
        say("relay or commander not subscribed within %.0f s (%s <- %s, %s <- %s): nothing flown"
            % (SUB_WAIT_S, RELAY, TOPIC, COMMANDER, OUT_TOPIC))
        return 1
    v = FRAC * vmax()
    say("push speed: %.2f x teleop_max_speed_mps = %.2f m/s for %.1f s" % (FRAC, v, PUSH_S))
    for h in HEADINGS:
        push(str(h), h, v)
    if not set_world(node):
        return 1
    push("world", 180, v)
    return 0


if SignalHandlerOptions is not None:
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
else:
    rclpy.init()
signal.signal(signal.SIGTERM, on_signal)
signal.signal(signal.SIGINT, on_signal)
node = rclpy.create_node("svg_teleop_frame_fly")
pub = node.create_publisher(TwistStamped, TOPIC, 10)


def on_odom(msg):
    q = msg.pose.pose.orientation
    yaw = F.yaw_from_quat(q.x, q.y, q.z, q.w)
    if not math.isnan(yaw):
        with lock:
            seen["yaw"], seen["t"] = yaw, time.monotonic()


def on_status(msg):
    with lock:
        seen["status"] = msg.data


def message():
    m = TwistStamped()
    m.header.stamp = node.get_clock().now().to_msg()
    m.header.frame_id = "map"
    with lock:
        m.twist.angular.z, m.twist.linear.x = cmd["wz"], cmd["vx"]
    return m


node.create_subscription(Odometry, ODOM, on_odom, qos_profile_sensor_data)
node.create_subscription(String, STATUS, on_status, 10)
node.create_timer(0.05, lambda: pub.publish(message()))
executor = SingleThreadedExecutor()      # CHG-0022: an executor we can stop
executor.add_node(node)
spin_thread = threading.Thread(target=executor.spin, daemon=True)
spin_thread.start()
rc = 1
try:
    rc = main(node, pub)
except Stop as e:
    say("push program stopped by %s" % e)
except Exception as e:  # noqa: BLE001 -- any error: zeros first, then report
    say("push program error: %s: %s" % (type(e).__name__, e))
finally:
    set_cmd()
    for _ in range(20):          # 1 s of zeros from this thread too, in case the spin thread is gone
        try:
            pub.publish(message())
        except Exception:  # noqa: BLE001
            break
        time.sleep(0.05)
    say("push program done (rc %d); zeros published" % rc)
    # CHG-0022 shutdown order: stop the executor, join its thread, destroy the node, then rclpy.
    for step in (lambda: executor.shutdown(), lambda: spin_thread.join(5.0), lambda: node.destroy_node(),
                 lambda: (rclpy.try_shutdown if hasattr(rclpy, "try_shutdown") else rclpy.shutdown)()):
        try:
            step()
        except Exception:  # noqa: BLE001
            pass
sys.exit(rc)
PY
rc=$?
if [ "$rc" -gt 1 ]; then
  sig=""; [ "$rc" -gt 128 ] && sig=" (signal $((rc - 128)))"
  echo "CAVEAT: the teleop_frame push program (python) died with exit code $rc$sig instead of 0/1; the landing below still ran"
fi
echo "[$(date +%T)] land: $(svc land)"
sleep 15
echo "[$(date +%T)] landed: $(states)"
cleanup
exit $rc
