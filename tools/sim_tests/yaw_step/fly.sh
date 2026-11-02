#!/bin/bash
# One-drone yaw-step flight (NEAR-789). SIM ONLY (iron rule 9): every gain the sweep sets is a sim-only value.
# Runs INSIDE the robot container: tools/sim.sh test copies it to $S together with tools/lib/px4_param_set.sh and
# tools/lib/changes_log.py.
# Usage: fly.sh <gap_s> [N_PER_DIRECTION=3] [RATE_RAD_S=1.0] [PULSE_S=1.0] [SWEEP=""]
#   SWEEP = ';'-separated gain sets "P=v,P=v;P=v" applied live over MAVROS before sets 1..k; set 0 = booted gains.
# Flow: takeoff -> retry start (as crossing/fly.sh, CMU's sim_cbf_crossing_test.sh flow) -> one rclpy program that
# publishes /svg/drone_1/teleop_command at 20 Hz (yaw pulses, the sweep, the patch-0007 turn-then-tap check) and
# prints wall stamps `[<unix s>] pulse k/i onset|release`, `turn onset|release`, `tap onset|release` for gates.py ->
# land -> `landed:`. Zeros are published for 1 s on normal exit, SIGINT/SIGTERM and any exception (try/finally); the
# commander's 0.5 s teleop_timeout_s zeroes the yaw rate anyway. Every sweep set and every restore goes through the shared
# helper `px4_param_set.sh 1 NAME VALUE <who> $HERE/changes.log` (CHG-0020; the same helper as `sim.sh param set`: sim
# PX4 only, read-back, one `drone_1/NAME` line in changes.log through tools/lib/changes_log.py; sim.sh empties that log
# after `up` and copies it to docs/record/<run>/changes.log). A set the helper does not confirm prints
# `PARAM MISMATCH|REFUSED|UNVERIFIED: …`, stops the sweep, lands normally and exits 1; a set cut short by a stop is
# logged here through the same formatter as UNVERIFIED.
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
echo "[$(date +%T)] pre-takeoff: $(states)"
echo "[$(date +%T)] takeoff: $(svc takeoff)"
for i in $(seq 1 30); do wait_s 3; r=$(svc start); case "$r" in success=True*) echo "[$(date +%T)] start: $r"; break;; esac
  [ "$i" = 30 ] && { echo "start never accepted: $r"; svc land; exit 1; }; done
echo "[$(date +%T)] pulses: gap $GAP s (wall), $N per direction, rate $RATE rad/s, pulse $PULSE s, sweep '${SWEEP:-none}'"
# argv[1] carries "fly.sh": sim.sh's stop_fly (`pkill -f "fly\.sh"`) then stops this program too, never only the shell
CHANGES_LOG="$HERE/changes.log" PARAM_HELPER="$HERE/px4_param_set.sh" PYTHONPATH="$HERE${PYTHONPATH:+:$PYTHONPATH}" \
  python3 - yaw_step/fly.sh "$GAP" "$N" "$RATE" "$PULSE" "$SWEEP" <<'PY'
import os, re, signal, subprocess, sys, threading, time

import rclpy
from rclpy.executors import SingleThreadedExecutor
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
DRONE = "drone_1"                         # the helper's <drone_n> is 1: changes.log lines read drone_1/NAME
HELPER = os.environ.get("PARAM_HELPER", "px4_param_set.sh")
HELPER_TIMEOUT_S = 300                    # the helper's own ros2 calls time out within 4 x 30 s + 120 s
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


# every ros2 call of this program and the helper discovers LOCALHOST only (the helper sets it too): a MAVROS on the lab
# subnet with the same name never answers. rclpy's own node (the teleop publisher) keeps the container's settings.
CHILD_ENV = dict(os.environ, ROS_AUTOMATIC_DISCOVERY_RANGE="LOCALHOST")
CHILD_ENV.pop("ROS_STATIC_PEERS", None)


def sh(line, timeout):
    try:
        r = subprocess.run(["bash", "-c", line], capture_output=True, text=True, timeout=timeout, env=CHILD_ENV)
        return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return 124, "timeout after %d s: %s" % (timeout, line)


def param_get(p):
    """Read only: drone_1's MAVROS value of p (the booted value, read before the sweep first sets p). Never sets."""
    _, out = sh("ros2 param get %s %s" % (PNODE, p), 30)
    m = re.search(r"value is:\s*([-+0-9.eE]+)", out)
    return float(m.group(1)) if m else None


def helper_set(p, val, who, old):
    """One set through px4_param_set.sh (it checks the sim PX4, sets, pulls, reads back and writes the changes.log line).
    Returns (kind, the parsed changes.log line): kind None = read back as set; "MISMATCH" / "REFUSED" (nothing sent) / "UNVERIFIED".
    A call cut short (SIGINT/SIGTERM, our timeout) may still have reached PX4: its line is written here, UNVERIFIED."""
    t = time.time()
    try:
        r = subprocess.run(["bash", HELPER, "1", p, repr(float(val)), who, LOG], capture_output=True, text=True,
                           timeout=HELPER_TIMEOUT_S, env=CHILD_ENV)
    except subprocess.TimeoutExpired:
        return "UNVERIFIED", changes_log.parse_change(changes_log.append_change(
            LOG, t, "%s/%s" % (DRONE, p), old, val, who + " timed-out",
            unverified="px4_param_set.sh killed after %d s, outcome unknown" % HELPER_TIMEOUT_S))
    except BaseException:
        changes_log.append_change(LOG, t, "%s/%s" % (DRONE, p), old, val, who + " interrupted before px4_param_set.sh returned",
                                  unverified="stopped while the set ran, outcome unknown")
        raise
    out = [l for l in r.stdout.splitlines() if l.strip()]
    for l in out[:-1] + r.stderr.splitlines():
        print("  helper: " + l, flush=True)            # indented: gates.py reads only fly.sh's own PARAM lines
    c = changes_log.parse_change(out[-1]) if out else None
    if c is None:                                      # no line from the helper: write one, nothing hides
        why = "px4_param_set.sh exit %d without a changes.log line: %s" % (r.returncode, (r.stderr.strip().splitlines() or ["no output"])[-1])
        if r.returncode in (2, 3):                     # bad arguments / no such parameter: nothing was sent
            c = changes_log.parse_change(changes_log.append_change(LOG, t, "%s/%s" % (DRONE, p), old, val, who, refused=why))
            return "REFUSED", c
        return "UNVERIFIED", changes_log.parse_change(changes_log.append_change(LOG, t, "%s/%s" % (DRONE, p), old, val, who, unverified=why))
    print(out[-1], flush=True)                         # the changes.log line
    kind = "MISMATCH" if c["mismatch"] else "REFUSED" if c["refused"] else "UNVERIFIED" if c["unverified"] or r.returncode else None
    return kind, c


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
current = {}                  # parameter -> the value the last confirmed set read back
booted = {}                   # parameter -> param_get() before the first sweep set (read only)
restored = {"done": False}


def set_and_log(gs, who, stop_on_fail):
    """Set (name, value) pairs through the helper, in order: one changes.log line each, also when interrupted (written
    by helper_set). Returns [(name, value, readback, kind, detail)] that did not take; with stop_on_fail the first one
    ends the set (the sweep), without it every pair is tried (the restore)."""
    bad = []
    for p, val in gs:
        new_touch = p not in touched
        if new_touch:
            touched[p] = booted.get(p)
        kind, c = helper_set(p, val, who, current.get(p, touched[p]))
        if touched.get(p) is None and c["old"] is not None:
            touched[p] = c["old"]
        if kind is None:
            current[p] = c["readback"]
        if kind == "REFUSED" and new_touch:
            del touched[p]                             # nothing was sent: nothing to restore
        if kind is not None:
            bad.append((p, val, c["readback"], kind, c["refused"] or c["unverified"] or ""))
            if stop_on_fail:
                break
    return bad


def apply_set(k, gs):
    """Gain set k of the sweep. True = every parameter read back as set through px4_param_set.sh."""
    bad = set_and_log(gs, "yaw_step-sweep-set-%d" % k, stop_on_fail=True)
    for p, val, r, kind, why in bad:
        print("PARAM %s: %s/%s set %r, read back %s%s -- sweep stopped"
              % (kind, DRONE, p, val, "n/a" if r is None else "%g" % r, (": " + why) if why else ""), flush=True)
    return not bad


def restore_booted(why):
    """Every parameter the sweep touched back to its booted value through the helper (who = restore-…). A failure
    prints one `CAVEAT: ` line naming what the running PX4 is left with (sim.sh copies it into the record)."""
    if not touched or restored["done"]:
        return True
    gs = [(p, b) for p, b in touched.items() if b is not None]
    say("restoring the booted gains (%s): %s" % (why, ", ".join("%s=%g" % g for g in gs) or "none known"))
    bad = set_and_log(gs, "restore-yaw_step-" + re.sub(r"[^A-Za-z0-9_.-]+", "-", why).strip("-"), stop_on_fail=False)
    left = ["%s=%s (booted %g, %s)" % (p, "?" if r is None else "%g" % r, b, kind) for p, b, r, kind, _ in bad]
    left += ["%s=? (booted value never read)" % p for p, b in touched.items() if b is None]
    restored["done"] = True                            # only once it ran to the end: a restore cut short runs again on exit
    if left:
        print("CAVEAT: the running PX4 may be left with non-booted gains after the yaw_step sweep (restore not confirmed): %s"
              % ", ".join(left), flush=True)
        return False
    stamp("booted gains restored: %s" % ", ".join("%s=%g" % g for g in gs))
    return True


def hold(seconds):
    time.sleep(seconds)


def main(node, pub):
    sets = parse_sweep(SWEEP)
    for p in dict.fromkeys(name for gs in sets for name, _ in gs):
        booted[p] = param_get(p)                        # read only: what a cut-short first set is restored to
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
    restore_booted("after the sweep before the patch-0007 check")   # the turn, the tap and the landing fly the booted gains
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
executor = SingleThreadedExecutor()      # CHG-0022: an executor we can stop; bare rclpy.spin in a thread was still running at exit
executor.add_node(node)
spin_thread = threading.Thread(target=executor.spin, daemon=True)
spin_thread.start()
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
        restore_booted("on exit rc %d" % rc)            # a stopped or mismatched sweep: no-op when already restored
    except Exception as e:  # noqa: BLE001
        print("CAVEAT: restoring the booted gains failed (%s: %s); the running PX4 may keep the sweep gains %s"
              % (type(e).__name__, e, ", ".join(touched)), flush=True)
    # CHG-0022 shutdown order: stop the executor, join its thread, destroy the node, then rclpy. A spin thread still
    # running at interpreter exit made the C++ runtime abort (`terminate called without an active exception`).
    for step in (lambda: executor.shutdown(), lambda: spin_thread.join(5.0), lambda: node.destroy_node(),
                 lambda: (rclpy.try_shutdown if hasattr(rclpy, "try_shutdown") else rclpy.shutdown)()):
        try:
            step()
        except Exception:  # noqa: BLE001
            pass
    if spin_thread.is_alive():
        print("CAVEAT: the yaw_step spin thread did not stop within 5 s of executor.shutdown(); the python may abort at exit",
              flush=True)
sys.exit(rc)
PY
rc=$?
# CHG-0022: the program itself only ever exits 0 or 1; anything else (134 = abort, 139 = segfault, 128+n = a signal) is a crash
if [ "$rc" -gt 1 ]; then
  sig=""; [ "$rc" -gt 128 ] && sig=" (signal $((rc - 128)))"
  echo "CAVEAT: the yaw_step pulse program (python) died with exit code $rc$sig instead of 0/1 -- the C++ runtime aborting at shutdown (\`terminate called without an active exception\`) or a crash; the landing below still ran"
fi
echo "[$(date +%T)] land: $(svc land)"
wait_s 15
echo "[$(date +%T)] landed: $(states)"
exit $rc
