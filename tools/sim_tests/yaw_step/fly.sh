#!/bin/bash
# One-drone yaw-step flight (NEAR-789). SIM ONLY (iron rule 9): every gain the sweep sets is a sim-only value.
# Runs INSIDE the robot container: tools/sim.sh test copies it to $S together with tools/lib/changes_log.py.
# Usage: fly.sh <gap_s> [N_PER_DIRECTION=3] [RATE_RAD_S=1.0] [PULSE_S=1.0] [SWEEP=""]
#   SWEEP = ';'-separated gain sets "P=v,P=v;P=v" applied live over MAVROS before sets 1..k; set 0 = booted gains.
# Flow: takeoff -> retry start (as crossing/fly.sh, CMU's sim_cbf_crossing_test.sh flow) -> one rclpy program that
# publishes /svg/drone_1/teleop_command at 20 Hz (yaw pulses, the sweep, the patch-0007 turn-then-tap check) and
# prints wall stamps `[<unix s>] pulse k/i onset|release`, `turn onset|release`, `tap onset|release` for gates.py ->
# land -> `landed:`. Zeros are published for 1 s on normal exit, SIGINT/SIGTERM and any exception (try/finally); the
# commander's 0.5 s teleop_timeout_s zeroes the yaw rate anyway. A read-back that differs from the value set prints
# PARAM MISMATCH, stops the sweep, lands normally and exits 1. Every live change: one line in changes.log next to this
# script (format: tools/lib/changes_log.py; sim.sh copies it to docs/record/<run>/changes.log).
# fly-check: yes   (tools/sim.sh runs `fly.sh --check <args>` on the host before the stack starts: bad arguments never fly)
CHECK=0; [ "${1:-}" = --check ] && { CHECK=1; shift; }
bad(){ echo "fly.sh: $*" >&2; exit 2; }
[ $# -le 5 ] || bad "at most 5 arguments (gap N rate pulse sweep), got $# — a space inside SWEEP? ($*)"
GAP=${1:-20}; N=${2:-3}; RATE=${3:-1.0}; PULSE=${4:-1.0}; SWEEP=${5:-}
NUM='[0-9]+([.][0-9]*)?([eE][-+]?[0-9]+)?'; PV="MC_YAW(RATE)?_[A-Z]+=-?$NUM"; SET="$PV(,$PV)*"
[[ "$GAP" =~ ^$NUM$ ]] || bad "gap must be a number of seconds (got '$GAP')"
[[ "$N" =~ ^[1-9][0-9]*$ ]] || bad "N_PER_DIRECTION must be a whole number >= 1 (got '$N')"
[[ "$RATE" =~ ^$NUM$ ]] || bad "RATE_RAD_S must be a number (got '$RATE')"
[[ "$PULSE" =~ ^$NUM$ ]] || bad "PULSE_S must be a number (got '$PULSE')"
[ -z "$SWEEP" ] || [[ "$SWEEP" =~ ^$SET(\;$SET)*\;?$ ]] || bad "SWEEP must be 'P=v,P=v;P=v' with MC_YAW* names only (got '$SWEEP')"
[ "$CHECK" = 1 ] && { echo "fly.sh: arguments ok (gap $GAP, $N per direction, rate $RATE, pulse $PULSE, sweep '${SWEEP:-none}')"; exit 0; }
HERE=$(cd "$(dirname "$0")" && pwd)
cd ~/AirStack/robot/ros_ws && source install/setup.bash >/dev/null 2>&1
wait_s(){ sleep "$1"; }
svc(){ timeout 20 ros2 service call /swarm_commander/$1 std_srvs/srv/Trigger 2>/dev/null | grep -o "success=[A-Za-z]*, message='[^']*'"; }
states(){ timeout 10 ros2 topic echo /svg/commander_status --once --field data 2>/dev/null | grep -v '^---' \
  | grep -oE '"(name|state)": *"[^"]*"|"position": *(\[[^]]*\]|null)' | tr -d '"' | sed 's/position: null/position: ?/' | paste -sd' '; }
rm -f "$HERE/changes.log"
echo "[$(date +%T)] pre-takeoff: $(states)"
echo "[$(date +%T)] takeoff: $(svc takeoff)"
for i in $(seq 1 30); do wait_s 3; r=$(svc start); case "$r" in success=True*) echo "[$(date +%T)] start: $r"; break;; esac
  [ "$i" = 30 ] && { echo "start never accepted: $r"; svc land; exit 1; }; done
echo "[$(date +%T)] pulses: gap $GAP s (wall), $N per direction, rate $RATE rad/s, pulse $PULSE s, sweep '${SWEEP:-none}'"
# argv[1] carries "fly.sh": sim.sh's stop_fly (`pkill -f "fly\.sh"`) then stops this program too, never only the shell
CHANGES_LOG="$HERE/changes.log" PYTHONPATH="$HERE${PYTHONPATH:+:$PYTHONPATH}" \
  python3 - yaw_step/fly.sh "$GAP" "$N" "$RATE" "$PULSE" "$SWEEP" <<'PY'
import os, re, signal, subprocess, sys, threading, time

import rclpy
from geometry_msgs.msg import TwistStamped
try:
    from rclpy.signals import SignalHandlerOptions
except ImportError:          # older rclpy: no option, rclpy's own handler stays
    SignalHandlerOptions = None
import changes_log

GAP, N, RATE, PULSE = float(sys.argv[2]), int(float(sys.argv[3])), float(sys.argv[4]), float(sys.argv[5])
SWEEP = sys.argv[6] if len(sys.argv) > 6 else ""
TOPIC = "/svg/drone_1/teleop_command"
PNODE = "/drone_1/interface/mavros/param"
PSET, PPULL = "/drone_1/interface/mavros/param/set", "/drone_1/interface/mavros/param/pull"
LOG = os.environ.get("CHANGES_LOG", "changes.log")
TURN_RAD_S, TURN_S, TAP_MPS, TAP_S, SETTLE_S = 0.5, 3.14, 0.5, 1.5, 5.0     # patch-0007 check: +90 deg in real time (x the sim time scale in vehicle time), then 0.75 m east


class Stop(Exception):
    pass


def on_signal(signum, _frame):
    raise Stop(signal.Signals(signum).name)


def stamp(text):
    print("[%.6f] %s" % (time.time(), text), flush=True)


def say(text):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), text), flush=True)


cmd = {"wz": 0.0, "vx": 0.0}
lock = threading.Lock()


def set_cmd(wz=0.0, vx=0.0):
    with lock:
        cmd["wz"], cmd["vx"] = float(wz), float(vx)


def sh(line, timeout):
    try:
        r = subprocess.run(["bash", "-c", line], capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return 124, "timeout after %d s: %s" % (timeout, line)


def param_pull():
    sh('ros2 service call %s mavros_msgs/srv/ParamPull "{force_pull: true}"' % PPULL, 120)


def param_get(p):
    _, out = sh("ros2 param get %s %s" % (PNODE, p), 30)
    m = re.search(r"value is:\s*([-+0-9.eE]+)", out)
    return float(m.group(1)) if m else None


def param_set(p, v):
    """The mechanism that reported success, or None. Primary: the ParamSetV2 service (U1: field names unverified);
    fallback: `ros2 param set` on the MAVROS param node (U2). The read-back decides either way."""
    _, out = sh('ros2 service call %s mavros_msgs/srv/ParamSetV2 "{force_set: false, param_id: %s, value: {type: 3, double_value: %r}}"'
                % (PSET, p, float(v)), 30)
    if re.search(r"success=True", out):
        return "service %s (ParamSetV2)" % PSET
    _, out = sh("ros2 param set %s %s %r" % (PNODE, p, float(v)), 30)
    if "successful" in out.lower():
        return "ros2 param set %s" % PNODE
    return None


def parse_sweep(s):
    sets = []
    for part in s.split(";"):
        part = part.strip()
        if not part:
            continue
        g = []
        for kv in part.split(","):
            name, _, val = kv.partition("=")
            if not re.fullmatch(r"MC_YAW(RATE)?_[A-Z]+", name.strip()):
                raise ValueError("sweep: only MC_YAW* parameters may be set (got %r)" % name)
            g.append((name.strip(), float(val)))
        sets.append(g)
    return sets


touched = {}                  # parameter -> its booted value (read before this run first changed it), first-touch order
restored = {"done": False}


def set_and_log(gs, old, who):
    """Set (name, value) pairs, pull, read each back; one changes.log line per parameter, also when interrupted: an
    entry is listed BEFORE its call, because a call cut short by SIGINT/SIGTERM may still have reached PX4.
    Returns [(name, value, readback)] that did not take (no mechanism, no read-back or a different read-back)."""
    issued, rb = [], {}
    try:
        for p, val in gs:
            issued.append([time.time(), p, val, None])
            issued[-1][3] = param_set(p, val)
        param_pull()
        for _, p, _, _ in issued:
            rb[p] = param_get(p)
    finally:
        for t, p, val, how in issued:
            if p in rb:
                status = "via %s" % (how or "NO mechanism reported success")
            else:
                status = "interrupted before the read-back (via %s)" % (how or "a call that never returned")
            changes_log.append_change(LOG, t, p, old.get(p), val, "%s %s" % (who, status), readback=rb.get(p))
    bad = []
    for t, p, val, how in issued:
        r = rb.get(p)
        print("[%.6f] param %s set %r readback %r via %s" % (t, p, val, r, how), flush=True)
        if how is None or r is None or abs(r - val) > 1e-4 * max(1.0, abs(val)):
            bad.append((p, val, r))
    return bad


def apply_set(k, gs):
    """Gain set k of the sweep. True = every parameter read back as set."""
    param_pull()
    old = {p: param_get(p) for p, _ in gs}
    for p, _ in gs:
        touched.setdefault(p, old[p])
    bad = set_and_log(gs, old, "yaw_step fly.sh sweep set %d" % k)
    for p, val, r in bad:
        print("PARAM MISMATCH: %s set %r, read back %r -- sweep stopped" % (p, val, r), flush=True)
    return not bad


def restore_booted(why):
    """Every parameter the sweep touched back to its booted value, read back and logged (who = restore). A failure
    prints one `CAVEAT: ` line naming what the running PX4 is left with (sim.sh copies it into the record)."""
    if not touched or restored["done"]:
        return True
    restored["done"] = True
    gs = [(p, b) for p, b in touched.items() if b is not None]
    say("restoring the booted gains (%s): %s" % (why, ", ".join("%s=%g" % g for g in gs) or "none known"))
    param_pull()
    cur = {p: param_get(p) for p, _ in gs}
    bad = set_and_log(gs, cur, "restore (yaw_step fly.sh, %s)" % why)
    left = ["%s=%s (booted %s)" % (p, "?" if r is None else "%g" % r, "%g" % b) for p, b, r in bad]
    left += ["%s=? (booted value never read)" % p for p, b in touched.items() if b is None]
    if left:
        print("CAVEAT: the running PX4 is left with non-booted gains after the yaw_step sweep: %s" % ", ".join(left), flush=True)
        return False
    stamp("booted gains restored: %s" % ", ".join("%s=%g" % g for g in gs))
    return True


def hold(seconds):
    time.sleep(seconds)


def main(node, pub):
    sets = parse_sweep(SWEEP)
    for k, gs in enumerate([[]] + sets):
        if k > 0:
            say("set %d: %s" % (k, ", ".join("%s=%g" % g for g in gs)))
            if not apply_set(k, gs):
                return 1
            hold(3.0)
        for i in range(2 * N):
            sign = 1 if i % 2 == 0 else -1
            stamp("pulse %d/%d onset sign=%+d rate=%.3f" % (k, i + 1, sign, RATE))
            set_cmd(wz=sign * RATE)
            hold(PULSE)
            set_cmd()
            stamp("pulse %d/%d release" % (k, i + 1))
            hold(GAP)
    restore_booted("after the sweep, before the patch-0007 check")   # the turn, the tap and the landing fly the booted gains
    # patch-0007 turn-then-tap check (INFO in gates.py; never gated as a yaw pulse)
    stamp("turn onset sign=+1 rate=%.3f" % TURN_RAD_S)
    set_cmd(wz=TURN_RAD_S)
    hold(TURN_S)
    set_cmd()
    stamp("turn release")
    hold(SETTLE_S)
    stamp("tap onset vx=%.3f" % TAP_MPS)
    set_cmd(vx=TAP_MPS)
    hold(TAP_S)
    set_cmd()
    stamp("tap release")
    hold(SETTLE_S)
    return 0


if SignalHandlerOptions is not None:
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
else:
    rclpy.init()
signal.signal(signal.SIGTERM, on_signal)
signal.signal(signal.SIGINT, on_signal)
node = rclpy.create_node("svg_yaw_step_fly")
pub = node.create_publisher(TwistStamped, TOPIC, 10)


def message():
    m = TwistStamped()
    m.header.stamp = node.get_clock().now().to_msg()
    m.header.frame_id = "map"
    with lock:
        m.twist.angular.z, m.twist.linear.x = cmd["wz"], cmd["vx"]
    return m


node.create_timer(0.05, lambda: pub.publish(message()))
threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()
rc = 1
try:
    rc = main(node, pub)
except Stop as e:
    say("pulse program stopped by %s" % e)
except Exception as e:  # noqa: BLE001 -- any error: zeros first, then report
    say("pulse program error: %s: %s" % (type(e).__name__, e))
finally:
    set_cmd()
    for _ in range(20):          # 1 s of zeros from this thread too, in case the spin thread is gone
        try:
            pub.publish(message())
        except Exception:  # noqa: BLE001
            break
        time.sleep(0.05)
    say("pulse program done (rc %d); zeros published" % rc)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)       # a second stop must not cut the restore short
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        restore_booted("on exit (rc %d)" % rc)            # a stopped or mismatched sweep: no-op when already restored
    except Exception as e:  # noqa: BLE001
        print("CAVEAT: restoring the booted gains failed (%s: %s); the running PX4 may keep the sweep gains %s"
              % (type(e).__name__, e, ", ".join(touched)), flush=True)
    try:
        node.destroy_node()
        rclpy.shutdown()
    except Exception:  # noqa: BLE001
        pass
sys.exit(rc)
PY
rc=$?
echo "[$(date +%T)] land: $(svc land)"
wait_s 15
echo "[$(date +%T)] landed: $(states)"
exit $rc
