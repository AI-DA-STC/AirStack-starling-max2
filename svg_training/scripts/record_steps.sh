#!/usr/bin/env bash
# S1 Task 5: designed velocity-step session in the AirStack simulator. SIM ONLY (repository iron rule 9: nothing
# measured here goes to the drone).
#
# Usage: bash scripts/record_steps.sh [--dry-run] <name>        (--help: this text and the detached form)
#   <name> = a new run folder runs/<name>/ ([A-Za-z0-9][A-Za-z0-9_-]*, at most 64 characters)
#   --dry-run  runs the read-only refusal checks, then prints every command in order and creates nothing
# Detached (never tied to a terminal or a tool call's lifetime; SIGHUP and SIGPIPE are ignored):
#   setsid nohup bash scripts/record_steps.sh <name> > runs/<name>.out 2>&1 &
#   stop it with: kill -TERM <pid>   (it lands, brings the simulator down and writes runs/<name>/ABORTED.txt)
#
# Flow: refusals (run folder, GPU busy with a python/kit/isaac process, simulator or commander already running, the
# simulator's lock ~/flight_logs/sim/.sim_test.lock, real-drone/mocap bridge, port 8765, the bags folder) -> the lock
# taken -> steps.json -> preflight.txt -> tools/sim.sh up --headless (3 drones: `up` ignores NUM_ROBOTS,
# tools/sim.sh:94) -> host and container bag listings compared -> our commander (teleop_single_ours.yaml, scenario hover,
# record_bag, bag_prefix svg_s1_<name>; names only drone_1, the other two drones stay on the ground) -> real-drone check
# -> virtual_stick.py (takeoff, start, the [steps] of configs/s1.toml at 20 Hz, land) -> disarm check -> our commander
# stopped (the bag closes) -> logs and drone_1 ulog copied -> signals ignored from here -> sentinel -> the bag `down`
# would pick checked -> real-drone check -> tools/sim.sh down, then checked down -> our bag copied from
# ~/flight_logs/sim/_stack/ and verified (files and sizes) -> the original removed if down left it (guarded) -> sentinel
# removed -> pre-existing bags checked in place -> outside_writes.txt -> the lock released.
# INT / TERM / HUP or any failure before that point: the stick stopped (it lands whatever it may have taken off) ->
# zeros, land and the disarm wait if stick.log has this run's `pre-takeoff:` line OR drone_1 is armed — but never after a
# second commander, and only while ours is the one /svg/commander_status publisher (precedence: zero_land_wait) -> our
# commander stopped -> logs and ulog -> the same down sequence -> runs/<name>/ABORTED.txt.
# The stick's own simulator check failed (stick exit 67, "REAL DRONE MAY BE PRESENT"): the same as below, nothing sent.
# A SECOND COMMANDER or foreign status (stick exit 67), another commander alive in the robot container or any
# /svg/commander_status publisher after ours is stopped: nothing is sent (no zeros, no land — land reaches every
# commander on the domain), our commander is stopped by its bag_prefix, `down` is NOT run, exit 67.
#
# Other people's bags and sessions. `tools/sim.sh down` copies ONE bag to ~/flight_logs/sim/_stack/<bag>/ and removes its
# original only when its bag_dump_hook succeeds: the LAST name of `ls -d <bags>/svg_*` in the robot container
# (tools/lib/stack.sh:268-277; name order, not mtime). It also SIGINTs every ground_control.launch.py in the robot
# container (stack.sh:263). So: exit 66 before anything starts if a bag there is being written or sorts after ours; an
# empty sentinel svg_s1_<name>_00000000_000000 before every `down`, and `down` runs only if the name it will pick is
# the sentinel or this run's bag and no real-drone/mocap signal is present; our own commander is stopped by its
# bag_prefix only; after `down`, every pre-existing bag is checked still in place.
#
# Exit codes: 0 session complete; 1 session failed (cleaned up, simulator down, ABORTED.txt); 3 stopped by a signal
# (cleaned up, simulator down, ABORTED.txt); 5 SIMULATOR LEFT UP on purpose — `down` failed, was not verified, or would
# have picked a bag that is not ours (bring it down by hand: tools/sim.sh down, never --force); 64 usage; 65 refused
# before anything started (also when `up`'s own precheck refuses: then `down` is not run); 66 refused: the bags folder
# is missing, in use, or holds a bag `down` would pick instead of ours; 67 REAL-DRONE/MOCAP SIGNAL after the start:
# nothing more is done, the simulator is LEFT UP, `down` is not run; the same for a second commander (stick or host).
# Test hooks (tests only): --check-bag-path <name> <path> runs only the bag-removal guard (0 ok, 2 refused);
# SVG_TEST_SIM (fake sim.sh), SVG_TEST_RUNS (runs folder), SVG_TEST_HOST_BAGS (host bags folder), SVG_TEST_POLL_S.
set -uo pipefail
trap '' PIPE

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# SVG_STACK_REPO: the clone whose AirStack/ the containers mount (the live clone, docker-mounted) when this script runs
# from another checkout (the development worktree); default: the checkout this script is in.
REPO="${SVG_STACK_REPO:-$(cd "$ROOT/.." && pwd)}"
SIM="${SVG_TEST_SIM:-$REPO/tools/sim.sh}"
PY="${SVG_HOST_PY:-python3}"
RUNS="${SVG_TEST_RUNS:-$ROOT/runs}"
POLL_S="${SVG_TEST_POLL_S:-2}"
R=airstack-robot-desktop-1                            # = stack.sh:21
I=isaac-sim
BAGS=/root/AirStack/robot/ros_ws/bags                 # inside $R (= stack.sh:23); on the host the bind mount below
HOST_BAGS="${SVG_TEST_HOST_BAGS:-$REPO/AirStack/robot/ros_ws/bags}"
STACK_DIR="$HOME/flight_logs/sim/_stack"            # where `tools/sim.sh down` copies the bag it picks (tools/sim.sh:91)
SIM_LOCK="$HOME/flight_logs/sim/.sim_test.lock"     # the simulator's own lock (tools/sim.sh:235-242)
DRONE=drone_1
SYSID=2                                               # drone_i has MAV_SYS_ID i+1 (tools/lib/stack.sh:17)
CONFIG_YAML=teleop_single_ours.yaml
SCENARIO=hover
TELEOP=/svg/$DRONE/teleop_command
NOISE='^(bash: cannot set terminal|bash: no job control|Sourcing|groups: cannot find name)'
REAL_TOPICS='/fmu/|/poses|/pose$'                     # = stack.sh:90-92
# Published topics that are the simulator's or our own, never a real drone (L1.4 first run, 24 Nov 2026): the
# simulator's MAVROS (/drone_N/interface/mavros/...; the real drones fly uXRCE-DDS, /fmu/), and /fmu/in/ (a drone
# subscribes there; our commander's mocap_bridge publishes the relay). A real drone publishes /fmu/out/*; a mocap bridge
# publishes /drone_N/pose or /poses: both still stop the session. Topics with subscribers only are not counted.
OWN_TOPICS='/interface/mavros/|/fmu/in/'

usage() { echo "Usage: bash scripts/record_steps.sh [--dry-run] <name>   (--help for more)" >&2; exit 64; }
refuse() { echo "record_steps.sh: refused: $*" >&2; exit 65; }
refuse66() { echo "record_steps.sh: refused: $*" >&2
  [ "${DRY:-1}" = 0 ] && [ -d "${OUT:-/nonexistent}" ] && echo "refused=$(date -Is) $*" > "$OUT/REFUSED.txt"; exit 66; }
valid_name() { [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$ ]]; }

# bag_path_ok <name> <path>: the ONLY directory this script may delete in the robot container is the bag this run's
# commander wrote: $BAGS/svg_s1_<name>_<YYYYmmdd>_<HHMMSS>[_<n>] (bag_recorder.py naming), nothing else.
bag_path_ok() {
  valid_name "$1" || return 1
  [[ "$2" =~ ^/root/AirStack/robot/ros_ws/bags/svg_s1_${1}_[0-9]{8}_[0-9]{6}(_[0-9]+)?$ ]]
}

case "${1:-}" in
  --help|-h) sed -n '2,/^set -uo/p' "${BASH_SOURCE[0]}" | grep '^#' | sed 's/^# \{0,1\}//'; exit 0 ;;
  --check-bag-path)
    [ $# -eq 3 ] || usage
    if bag_path_ok "$2" "$3"; then echo "bag path ok: $3"; exit 0; fi
    echo "record_steps.sh: bag removal refused: '$3' is not $BAGS/svg_s1_$2_<YYYYmmdd>_<HHMMSS>[_n]" >&2; exit 2 ;;
esac

DRY=0
case "${1:-}" in --dry-run) DRY=1; shift ;; esac
[ $# -eq 1 ] || usage
NAME=$1
valid_name "$NAME" || usage
PREFIX=svg_s1_$NAME
OUT="$RUNS/$NAME"
D=/tmp/svg_s1_$NAME                                   # this run's scratch dir in the robot container
SENTINEL_NAME=${PREFIX}_00000000_000000               # empty dir: the svg_* name `down` picks when no bag of ours exists
SENTINEL=$BAGS/$SENTINEL_NAME
START=$(date +%s)
CMD_LAUNCH='cd ~/AirStack/robot/ros_ws && ros2 launch svg_ground_control ground_control.launch.py config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/'"$CONFIG_YAML"' scenario:='"$SCENARIO"' record_bag:=true bag_prefix:='"$PREFIX"
CMD_STICK="cd ~/AirStack/robot/ros_ws && source install/setup.bash >/dev/null 2>&1; python3 $D/virtual_stick.py --config $D/s1.toml --drone $DRONE --flown-json $D/steps_flown.json"

# bags_preflight: the bags folder may hold other people's recordings (svg_20261112_094546: the 12 November real flights).
# Refuse (66) if it is missing, if any svg_* entry changed after START (a recording in progress), or if any svg_* name
# would sort after the sentinel under C or en_US.UTF-8 (the robot image's LANG): `down` would pick it instead of ours.
# Sets PRE_BAGS = every entry of the folder, one per line.
bags_preflight() {
  local b loc busy_now late=""
  [ -d "$HOST_BAGS" ] || refuse66 "the bags folder $HOST_BAGS does not exist — cannot check other people's bags; nothing started"
  PRE_BAGS=$(ls -1A "$HOST_BAGS" 2>/dev/null)
  busy_now=$(find "$HOST_BAGS" -mindepth 1 -maxdepth 2 -path "$HOST_BAGS/svg_*" -newermt "@$START" 2>/dev/null \
    | sed "s|^$HOST_BAGS/||; s|/.*||" | sort -u | paste -sd' ')
  [ -z "$busy_now" ] || refuse66 "bag(s) in $HOST_BAGS changed after this script started ($(date -d "@$START" '+%F %T')): $busy_now — someone is recording; nothing started"
  while IFS= read -r b; do
    case "$b" in svg_*) ;; *) continue ;; esac
    for loc in C en_US.UTF-8; do
      [ "$(printf '%s\n' "$b" "$SENTINEL_NAME" | LC_ALL=$loc sort 2>/dev/null | tail -1)" = "$SENTINEL_NAME" ] || late="$late $b($loc)"
    done
  done <<< "$PRE_BAGS"
  [ -z "$late" ] || refuse66 "bag(s) in $HOST_BAGS sort after this run's bag names:$late — tools/sim.sh down would pick one of them instead of ours; nothing started"
}

# ------------------------------------------------------------------------------------- refusals (read-only, both modes)
[ -e "$OUT" ] && refuse "run folder $OUT already exists — choose a new name"
gpu=$(nvidia-smi --query-compute-apps=pid,name --format=csv,noheader 2>&1) || refuse "nvidia-smi failed ($gpu) — cannot tell whether the GPU is free"
busy=$(printf '%s\n' "$gpu" | awk -F', *' 'NF >= 2 && tolower($2) ~ /python|kit|isaac/')
[ -z "$busy" ] || refuse "GPU busy — a python/kit/isaac compute process holds it (a benchmark or another simulator): $(echo "$busy" | paste -sd';')"
{ pgrep -x MicroXRCEAgent || pgrep -f '^(bash|sh) .*mocap\.sh' || pgrep -x natnet_ros2; } >/dev/null 2>&1 \
  && refuse "a real-drone/mocap bridge is running on the laptop (MicroXRCEAgent, mocap.sh or natnet_ros2)"
ss -ltnp 2>/dev/null | grep -q ':8765 ' && refuse "port 8765 already in use (a foxglove_bridge is up)"
names=$(docker ps --format '{{.Names}}' 2>/dev/null)
if grep -qx "$I" <<< "$names" && docker exec "$I" pgrep -f 'svg_multi_drone_single_domain\.py' >/dev/null 2>&1; then
  refuse "the AirStack simulator is already running (Isaac launcher alive in $I) — tools/sim.sh down first"; fi
if grep -qx "$R" <<< "$names" && docker exec "$R" pgrep -f 'ground_control\.launch\.py' >/dev/null 2>&1; then
  refuse "a commander is already running in $R"; fi
[ -f "$SIM_LOCK" ] && kill -0 "$(cat "$SIM_LOCK" 2>/dev/null)" 2>/dev/null && refuse "the simulator's lock $SIM_LOCK is held (pid $(cat "$SIM_LOCK"))"
compgen -G "$HOST_BAGS/${PREFIX}_*" >/dev/null && refuse "a bag $HOST_BAGS/${PREFIX}_* already exists"
compgen -G "$STACK_DIR/${PREFIX}_*" >/dev/null && refuse "a bag $STACK_DIR/${PREFIX}_* already exists"
bags_preflight
plan=$("$PY" "$ROOT/scripts/virtual_stick.py" --config "$ROOT/configs/s1.toml" --print-plan) || refuse "virtual_stick.py rejected configs/s1.toml"
PLAN_LINE=$(grep '^plan: ' <<< "$plan")
PLAN_S=$(sed -n 's/.*total \([0-9.]*\) s wall.*/\1/p' <<< "$PLAN_LINE"); PLAN_S=${PLAN_S%.*}
echo "$PLAN_LINE"

# ------------------------------------------------------------------------------------------------------- helpers
STAGE=0     # 0 nothing started, 1 up called, 2 commander launched, 3 stick started, 4 landed, 5 logs copied, 6 down done, 7 left up
BAG=""
CLEANING=0
COLLECTED=0
LOCKED=0
MOVED=""
LEFT_UP=""
say() { echo "[$(date '+%F %T %Z')] $*"; [ "$DRY" = 1 ] || echo "[$(date '+%F %T %Z')] $*" >> "$OUT/session.log"; }
# x <cmd…>: run a host command (logged in commands.sh), or print it in --dry-run
x() { if [ "$DRY" = 1 ]; then echo "DRY: $*"; return 0; fi; echo "$*" >> "$OUT/commands.sh"; "$@"; }
# rx "<shell>": a command in the robot container's interactive shell (ROS sourced), profile noise dropped
rx() { if [ "$DRY" = 1 ]; then echo "DRY: docker exec $R bash -ic \"$*\""; return 0; fi
  echo "docker exec $R bash -ic \"$*\"" >> "$OUT/commands.sh"
  docker exec "$R" bash -ic "$*" 2>&1 | grep -v -E "$NOISE" || true; }
# alive <container> <regex>: a non-zombie process whose command line matches (= stack.sh:48)
alive() { docker exec "$1" ps -eo stat,args 2>/dev/null | awk '$1 !~ /^Z/' | grep -qE -- "$2"; }
# wait_until <timeout s> <description> <shell test>: poll every POLL_S until the test succeeds
wait_until() { local t=$1 d=$2; shift 2
  if [ "$DRY" = 1 ]; then echo "DRY: wait <= ${t} s ($d): $*"; return 0; fi
  echo "# wait <= ${t} s ($d): $*" >> "$OUT/commands.sh"
  local t0=$SECONDS; until eval "$*" >/dev/null 2>&1; do
    [ $((SECONDS - t0)) -ge "$t" ] && { say "timeout after ${t} s: $d"; return 1; }; sleep "$POLL_S"; done
  say "$d (after $((SECONDS - t0)) s)"; }
armed_false() { rx "timeout 10 ros2 topic echo --once /$DRONE/interface/mavros/state" | grep -q '^armed: false'; }
log_count() { local n; n=$(docker exec "$R" grep -c -- "$1" "$D/commander.log" 2>/dev/null | tail -1); [ "${n:-0}" -ge 1 ]; }
# same_files <dir A> <dir B>: B holds metadata.yaml and exactly A's files with A's sizes
same_files() {
  [ -d "$1" ] && [ -f "$2/metadata.yaml" ] || return 1
  local a b
  a=$(cd "$1" && find . -type f -printf '%P %s\n' | LC_ALL=C sort) || return 1
  b=$(cd "$2" && find . -type f -printf '%P %s\n' | LC_ALL=C sort) || return 1
  [ -n "$a" ] && [ "$a" = "$b" ]
}

take_lock() {        # the simulator's lock, the way `tools/sim.sh test` takes it (tools/sim.sh:235-242)
  if [ "$DRY" = 1 ]; then echo "DRY: take $SIM_LOCK (pid of this script; released on every exit)"; return 0; fi
  mkdir -p "$(dirname "$SIM_LOCK")"
  if [ -f "$SIM_LOCK" ] && kill -0 "$(cat "$SIM_LOCK" 2>/dev/null)" 2>/dev/null; then refuse "the simulator's lock $SIM_LOCK is held (pid $(cat "$SIM_LOCK"))"; fi
  rm -f "$SIM_LOCK"
  ( set -C; echo $$ > "$SIM_LOCK" ) 2>/dev/null || refuse "could not take $SIM_LOCK"
  LOCKED=1
}
release_lock() { if [ "$LOCKED" = 1 ] && [ "$(cat "$SIM_LOCK" 2>/dev/null)" = "$$" ]; then rm -f "$SIM_LOCK"; fi; LOCKED=0; }

# realdrone_signal: 0 (and RD_WHAT) when a real-drone/mocap bridge runs on the laptop or real-drone/mocap topics are on
# the robot container's domain — the same tests as tools/sim.sh up (stack.sh:78, :90-92)
realdrone_signal() {
  RD_WHAT=""
  if [ "$DRY" = 1 ]; then
    echo "DRY: (real-drone check) pgrep -x MicroXRCEAgent || pgrep -f '^(bash|sh) .*mocap\\.sh' || pgrep -x natnet_ros2; docker exec $R bash -ic 'timeout 25 ros2 topic list -v --no-daemon --spin-time 5' | published only | grep -E '$REAL_TOPICS' | grep -vE '$OWN_TOPICS'"
    return 1; fi
  local p t
  p=$({ pgrep -x MicroXRCEAgent || pgrep -f '^(bash|sh) .*mocap\.sh' || pgrep -x natnet_ros2; } 2>/dev/null)
  t=$(rx 'timeout 25 ros2 topic list -v --no-daemon --spin-time 5' \
      | awk '/^Published topics:/{p=1; next} /^Subscribed topics:/{p=0} p && $1 == "*" {print $2}' \
      | grep -E "$REAL_TOPICS" | grep -vE "$OWN_TOPICS")
  [ -n "$p$t" ] || return 1
  RD_WHAT="bridge pids: $(echo ${p:-none}); topics: $(echo ${t:-none})"
}

die() { say "FAIL: $*"; cleanup "failure: $*"; exit 1; }

write_aborted() {
  [ "$DRY" = 1 ] && return 0
  local reached; reached=$(grep -oE 'step [0-9]+/[0-9]+ onset' "$OUT/stick.log" 2>/dev/null | tail -1)
  { echo "aborted=$(date -Is)"; echo "reason=$1"; echo "stage=${ABORT_STAGE:-$STAGE}   (0 nothing, 1 up, 2 commander, 3 stick, 4 landed, 5 logs copied, 6 down done)"; echo "step_reached=${reached:-none (no step started)}"
    [ -n "$LEFT_UP" ] && echo "SIMULATOR STILL UP: $LEFT_UP"
    grep -E 'landed:|FLOOR GUARD|flight error|refused' "$OUT/stick.log" 2>/dev/null
    [ -n "$MOVED" ] && echo "PRE-EXISTING BAG(S) NO LONGER IN PLACE:$MOVED"; } > "$OUT/ABORTED.txt"
}

# left_up <exit code> <WHY>: stop here with the simulator up — nothing is removed (bag original, sentinel), the owner
# brings the stack down by hand. Used when `down` failed or cannot be run safely.
left_up() {
  local code=$1; shift
  LEFT_UP="$*"; ABORT_STAGE=${ABORT_STAGE:-$STAGE}; STAGE=7
  say "!! SIMULATOR STILL UP — $LEFT_UP — NOTHING REMOVED (BAG ORIGINAL, SENTINEL). BRING IT DOWN BY HAND: tools/sim.sh down (NEVER --force)"
  write_aborted "simulator left up: $LEFT_UP"
  write_outside
  release_lock
  exit "$code"
}

stop_commander() {   # OUR commander only (its bag_prefix): SIGINT; the recorder writes metadata.yaml (<= 8 s grace); then the stick again
  local rc
  x docker exec "$R" pkill -INT -f "bag_prefix:=${PREFIX}( |\$)"
  wait_until 30 "our commander stopped" "! alive $R 'bag_prefix:=${PREFIX}( |\$)'"; rc=$?
  x docker exec "$R" pkill -INT -f "$D/virtual_stick.py"
  return $rc
}

remove_bag() {       # the original under AirStack/robot/ros_ws/bags (root-owned): only this run's, only after a verified copy
  local b=$1
  if [ "$DRY" = 1 ]; then echo "DRY: (guard) bash scripts/record_steps.sh --check-bag-path $NAME <bag> must pass, and runs/$NAME/<bag> must hold the original's files with the same sizes"
  elif ! bag_path_ok "$NAME" "$b"; then say "bag removal refused: '$b' is not this run's bag — left in place"; return 2; fi
  if [ "$DRY" = 0 ] && ! same_files "$HOST_BAGS/$(basename "$b")" "$OUT/$(basename "$b")"; then
    say "bag NOT removed: runs/$NAME/$(basename "$b") does not hold the original's files and sizes — original left at $b"; return 1; fi
  x docker exec "$R" rm -rf "${b:?}" && { [ "$DRY" = 1 ] || say "bag original removed: $b"; }
}

# collect_bag_after_down: AFTER a verified `tools/sim.sh down`, which copied our bag (the last svg_* name) to
# $STACK_DIR/<bag>/ and removed the original only if its bag_dump_hook succeeded (stack.sh:268-277). Copy it into
# runs/<name>/ from there, verified against the original's files and sizes (else docker cp from the container), remove
# the original if it is still there (guarded), remove the sentinel (rmdir: empty dirs only). Idempotent: COLLECTED=1 at
# the end.
collect_bag_after_down() {
  [ "$COLLECTED" = 1 ] && return 0
  local base orig rc=0 ok=0
  if [ "$DRY" = 1 ]; then
    BAG="$BAGS/${PREFIX}_<YYYYmmdd_HHMMSS>"; base=$(basename "$BAG")
    echo "DRY: cp -a $STACK_DIR/$base $OUT/   (the copy tools/sim.sh down made; verified: same files and sizes as $HOST_BAGS/$base; else docker cp $R:$BAG $OUT/)"
    echo "DRY: (only if $HOST_BAGS/$base still exists)"
    remove_bag "$BAG"
    echo "DRY: docker exec $R rmdir $SENTINEL"
    echo "DRY: (only if down copied the sentinel) rmdir $STACK_DIR/$SENTINEL_NAME"
    COLLECTED=1; return 0; fi
  if [ -z "$BAG" ]; then    # the commander log never named it: this run's prefix, on the host or in $STACK_DIR
    BAG=$( { ls -d "$HOST_BAGS/${PREFIX}_"* "$STACK_DIR/${PREFIX}_"* 2>/dev/null || true; } | grep -v '_00000000_000000$' \
      | sed 's|.*/||' | sort -u | tail -1)
    [ -n "$BAG" ] && BAG=$BAGS/$BAG
  fi
  if [ -z "$BAG" ]; then say "no $PREFIX bag (bags folder or $STACK_DIR)"; rc=1
  elif ! bag_path_ok "$NAME" "$BAG"; then say "bag path '$BAG' is not this run's — not copied"; BAG=""; rc=1
  else
    base=$(basename "$BAG"); orig="$HOST_BAGS/$base"
    if [ -f "$STACK_DIR/$base/metadata.yaml" ]; then
      rm -rf "${OUT:?}/${base:?}"
      if x cp -a "$STACK_DIR/$base" "$OUT/"; then
        if [ -e "$orig" ]; then same_files "$orig" "$OUT/$base" && ok=1; else same_files "$STACK_DIR/$base" "$OUT/$base" && ok=1; fi
      fi
      [ "$ok" = 1 ] || say "WARN: the copy from $STACK_DIR/$base does not match (files or sizes)"
    fi
    if [ "$ok" = 0 ] && [ -e "$orig" ]; then
      say "copying the bag from the robot container instead"
      rm -rf "${OUT:?}/${base:?}"
      x docker cp "$R:$BAG" "$OUT/" && same_files "$orig" "$OUT/$base" && ok=1
    fi
    if [ "$ok" = 1 ]; then say "bag copied and verified: runs/$NAME/$base ($(du -sh "$OUT/$base" | cut -f1))"
    else say "bag NOT copied/verified"; rc=1; fi
    if [ -e "$orig" ]; then
      if [ "$ok" = 1 ]; then remove_bag "$BAG" || rc=1; else say "bag original LEFT at $orig (no verified copy)"; fi
    else say "bag original already removed by tools/sim.sh down ($orig absent on the host)"; fi
  fi
  if [ -e "$HOST_BAGS/$SENTINEL_NAME" ] || docker exec "$R" test -d "$SENTINEL" 2>/dev/null; then
    x docker exec "$R" rmdir "${SENTINEL:?}" || say "WARN: sentinel $SENTINEL not removed (not empty, or the container is down)"; fi
  if [ -d "${STACK_DIR:?}/${SENTINEL_NAME:?}" ]; then x rmdir "${STACK_DIR:?}/${SENTINEL_NAME:?}" || say "WARN: $STACK_DIR/$SENTINEL_NAME not removed"; fi
  COLLECTED=1
  return $rc
}

# check_preexisting: every entry of the preflight listing must still be in the bags folder after `down`
check_preexisting() {
  local b
  if [ "$DRY" = 1 ]; then echo "DRY: check every entry of runs/$NAME/preflight.txt is still in $HOST_BAGS ($(echo $PRE_BAGS))"; return 0; fi
  MOVED=""
  while IFS= read -r b; do [ -n "$b" ] || continue; [ -e "$HOST_BAGS/$b" ] || MOVED="$MOVED $b"; done <<< "$PRE_BAGS"
  if [ -n "$MOVED" ]; then say "!! WARNING: PRE-EXISTING BAG(S) NO LONGER IN $HOST_BAGS:$MOVED — LOOK IN $STACK_DIR/"
  else say "pre-existing entries of the bags folder all still in place: $(echo $PRE_BAGS)"; fi
}

copy_ulog() {        # drone_1's PX4 ulog(s) of this session (MAV_SYS_ID 2, newer than START) — before Isaac stops
  local list f sid n=0
  if [ "$DRY" = 1 ]; then
    echo "DRY: docker exec $I bash -c 'for f in /tmp/tmp*/log/*/*.ulg; do [ \$(stat -c %Y \$f) -gt $START ] && echo \$f; done'"
    echo "DRY: docker exec $I python3 -c \"from pyulog import ULog; print(ULog(f, message_name_filter_list=['vehicle_local_position']).initial_parameters.get('MAV_SYS_ID'))\""
    echo "DRY: docker cp $I:/tmp/tmp<id>/log/<date>/<time>.ulg $OUT/drone_1_sysid${SYSID}_<time>.ulg"
    return 0; fi
  list=$(docker exec "$I" bash -c "for f in /tmp/tmp*/log/*/*.ulg; do [ -f \"\$f\" ] && [ \$(stat -c %Y \"\$f\") -gt $START ] && echo \"\$f\"; done; true")
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    sid=$(docker exec "$I" python3 -c "from pyulog import ULog; print(ULog('$f', message_name_filter_list=['vehicle_local_position']).initial_parameters.get('MAV_SYS_ID'))" 2>/dev/null)
    echo "$sid $f" >> "$OUT/ulog_sysid_map.txt"
    [ "$sid" = "$SYSID" ] || continue
    x docker cp "$I:$f" "$OUT/drone_1_sysid${SYSID}_$(basename "$f")" && n=$((n+1))
  done <<< "$list"
  [ "$n" -ge 1 ] && say "drone_1 ulog copied ($n file(s))" || say "WARN: no drone_1 (MAV_SYS_ID $SYSID) ulog of this session found"
}

copy_logs() {
  local f
  for f in commander.log stick.log steps_flown.json; do
    x docker cp "$R:$D/$f" "$OUT/$f" 2>/dev/null || say "WARN: no $f in $R:$D"; done
}

stick_said() { docker exec "$R" grep -qE -- "$1" "$D/stick.log" 2>/dev/null; }   # a line of this run's stick.log
# stick67_why <has-line command...>: the capitals reason for a stick exit 67 (its own simulator check, or a second commander)
stick67_why() {
  if "$@" 'REAL DRONE MAY BE PRESENT'; then
    echo "STICK REFUSED: REAL DRONE MAY BE PRESENT (its simulator check failed) — NOTHING SENT BY THE STICK; tools/sim.sh down NOT RUN"
  else
    echo "SECOND COMMANDER OR FOREIGN STATUS SEEN BY THE STICK — NO ZEROS, NO LAND SENT; DRONE_1 MAY STILL BE IN THE AIR IN ISAAC; tools/sim.sh down NOT RUN"
  fi
}
host_stick_said() { grep -qE -- "$1" "$OUT/stick.log" 2>/dev/null; }                 # the same, on the host copy

# status_publishers: how many /svg/commander_status publishers the robot container's domain shows ("unknown" if the
# answer is neither `Unknown topic` nor `Publisher count: N`)
status_publishers() {
  local info n
  info=$(rx 'timeout 25 ros2 topic info --no-daemon --spin-time 5 /svg/commander_status')
  if grep -q '^Unknown topic' <<< "$info"; then echo 0; return; fi
  n=$(sed -n 's/^Publisher count: *\([0-9]*\).*/\1/p' <<< "$info" | head -1); echo "${n:-unknown}"
}

# zero_land_wait (abort path): stop the stick (on SIGINT it zeroes and lands whatever it may have taken off), then the
# host's own zeros, land and disarm wait.
# PRECEDENCE — read top to bottom, the first that applies wins:
#   1. the stick saw a SECOND COMMANDER or foreign status (stick.log `SECOND COMMANDER` / `exit 67`): send NOTHING — no
#      zeros, no land (/swarm_commander/land is served by every commander on the domain) — stop ours, left_up 67;
#   2. more than our one commander publishes /svg/commander_status now (or the count cannot be read): send nothing; the
#      other-commander check before `down` then stops at 67;
#   3. this run's drone MAY be airborne — stick.log has this run's `pre-takeoff:` line (logged just before the takeoff
#      request; a request that timed out, or a signal or kill during it, may still have put the drone up) OR MAVROS says
#      drone_1 `armed: true`: zeros, land, bounded disarm wait;
#   4. otherwise nothing flew: nothing is sent.
zero_land_wait() {
  local n
  if [ "$STAGE" -ge 3 ]; then
    x docker exec "$R" pkill -INT -f "$D/virtual_stick.py"
    wait_until 100 "virtual_stick.py exited (on SIGINT it zeroes and lands whatever it may have taken off)" "! alive $R virtual_stick"
    if [ "$DRY" = 0 ] && alive "$R" virtual_stick; then x docker exec "$R" pkill -KILL -f "$D/virtual_stick.py"; fi
  fi
  if [ "$DRY" = 1 ]; then
    echo "DRY: (abort landing, in this order) SECOND COMMANDER in $D/stick.log -> nothing sent, exit 67; /svg/commander_status publishers != 1 -> nothing sent; 'pre-takeoff:' in stick.log OR $DRONE armed: true -> zeros on $TELEOP, /swarm_commander/land, wait <= 60 s for armed: false; else nothing sent"
    return 0; fi
  if [ "$STAGE" -ge 3 ] && stick_said 'SECOND COMMANDER|virtual_stick: exit 67'; then          # 1
    stop_commander || true
    copy_logs
    left_up 67 "$(stick67_why stick_said)"
  fi
  if ! { [ "$STAGE" -ge 3 ] && stick_said 'pre-takeoff:'; } \
     && ! rx "timeout 10 ros2 topic echo --once /$DRONE/interface/mavros/state" | grep -q '^armed: true'; then   # 4
    say "no takeoff request by this run's stick and $DRONE not armed: no zeros and no land sent"; return 0; fi
  n=$(status_publishers)
  if [ "$n" != 1 ]; then                                                                           # 2
    say "!! /svg/commander_status shows $n publisher(s), not our one commander — NO ZEROS, NO LAND SENT (land would reach them)"
    return 0; fi
  rx "timeout 6 ros2 topic pub -t 20 -r 20 $TELEOP geometry_msgs/msg/TwistStamped '{header: {frame_id: map}}'" >/dev/null   # 3
  rx "timeout 20 ros2 service call /swarm_commander/land std_srvs/srv/Trigger" | tail -1
  wait_until 60 "$DRONE disarmed (MAVROS armed: false)" armed_false || say "WARN: $DRONE disarm NOT confirmed within 60 s — the simulator is stopped anyway (sim only)"
}

# other_commander: 0 (and OC_WHAT) when, after ours is stopped, any ground_control.launch.py / swarm_commander process
# that is not this run's (bag_prefix) is alive in the robot container, or /svg/commander_status has any publisher on the
# domain (a commander on another station). A topic-info read that gives neither answer counts as present (fail closed).
other_commander() {
  OC_WHAT=""
  if [ "$DRY" = 1 ]; then
    echo "DRY: (other-commander check) docker exec $R ps -eo stat,args | grep -E 'ground_control\.launch\.py|swarm_commander' (not bag_prefix:=$PREFIX); docker exec $R bash -ic 'timeout 25 ros2 topic info --no-daemon --spin-time 5 /svg/commander_status' -> Publisher count must be 0"
    return 1; fi
  local procs n
  procs=$(docker exec "$R" ps -eo stat,args 2>/dev/null | awk '$1 !~ /^Z/' | grep -E 'ground_control\.launch\.py|swarm_commander' \
    | grep -vE -- "bag_prefix:=${PREFIX}( |$)")
  n=$(status_publishers)
  echo "other-commander check: processes=[$(echo $procs)] /svg/commander_status publishers=$n" >> "$OUT/session.log"
  [ -z "$procs" ] && [ "$n" = 0 ] && return 1
  OC_WHAT="processes: $(echo ${procs:-none}); /svg/commander_status publishers: $n"
}

# sim_down: no real-drone signal -> no other commander (I2) -> sentinel -> the name `down` will pick must be the
# sentinel or this run's bag -> tools/sim.sh down -> exit 0 AND no Isaac launcher / px4 left in the isaac container (stack.sh:284-288). Any failure:
# left_up (exit 5 / 67) — the bag original and the sentinel stay, nothing is removed. Never `down --force`.
sim_down() {
  local pick rc
  if [ "$DRY" = 1 ]; then
    realdrone_signal
    other_commander
    echo "DRY: docker exec $R mkdir -p $SENTINEL"
    echo "DRY: docker exec $R bash -c 'ls -d $BAGS/svg_* 2>/dev/null | tail -1'   (= stack.sh:269; must be the sentinel or this run's bag, else no down: exit 5)"
    x "$SIM" down
    echo "DRY: verify down: exit 0, and no '$I' process svg_multi_drone_single_domain.py or px4 (else SIMULATOR STILL UP: exit 5)"
    STAGE=6; return 0; fi
  if realdrone_signal; then left_up 67 "REAL-DRONE/MOCAP SIGNAL BEFORE tools/sim.sh down ($RD_WHAT) — down NOT RUN"; fi
  if docker exec "$R" true 2>/dev/null; then
    if other_commander; then
      left_up 67 "OTHER COMMANDER PRESENT BEFORE tools/sim.sh down ($OC_WHAT) — down would SIGINT it; down NOT RUN. IT MAY BE OUR OWN COMMANDER THAT DID NOT STOP (its swarm_commander node does not carry bag_prefix): check with docker exec $R ps -eo pid,args | grep -E 'ground_control|swarm_commander'"; fi
    x docker exec "$R" mkdir -p "$SENTINEL" || left_up 5 "SENTINEL $SENTINEL NOT CREATED — tools/sim.sh down NOT RUN"
    pick=$(docker exec "$R" bash -c "ls -d $BAGS/svg_* 2>/dev/null | tail -1")
    echo "docker exec $R bash -c 'ls -d $BAGS/svg_* 2>/dev/null | tail -1'   # -> $pick" >> "$OUT/commands.sh"
    if [ "$pick" != "$SENTINEL" ] && ! bag_path_ok "$NAME" "$pick"; then
      left_up 5 "tools/sim.sh down WOULD PICK '${pick:-nothing}' (NOT THIS RUN'S) — down NOT RUN"; fi
    say "tools/sim.sh down will pick $pick (this run's)"
  else say "robot container not running: tools/sim.sh down cannot touch any bag or commander there"; fi
  echo "$SIM down" >> "$OUT/commands.sh"
  "$SIM" down 2>&1 | tee "$OUT/sim_down.log"; rc=${PIPESTATUS[0]}
  [ "$rc" = 0 ] || left_up 5 "tools/sim.sh down EXITED $rc"
  if alive "$I" 'svg_multi_drone_single_domain\.py' || alive "$I" '(^|/)px4( |$)'; then
    left_up 5 "tools/sim.sh down EXITED 0 BUT THE ISAAC LAUNCHER OR PX4 STILL RUNS IN $I"; fi
  say "tools/sim.sh down: exit 0, no Isaac launcher or px4 left in $I"
  STAGE=6
}

write_outside() {    # every path written outside svg_training/ by this run
  [ "$DRY" = 1 ] && { echo "DRY: write $OUT/outside_writes.txt"; return 0; }
  local b
  {
    echo "# Paths written outside svg_training/ by run $NAME (record_steps.sh, $(date -Is)). AirStack simulator, sim only."
    [ -n "$LEFT_UP" ] && echo "SIMULATOR STILL UP: $LEFT_UP — the bag original and the sentinel were NOT removed"
    echo "$SIM_LOCK   the simulator's lock, held by this script (pid $$) from before up to its exit, then removed"
    echo "$STACK_DIR/   tools/sim.sh up/down: run.log commands.sh run_meta.txt res_watch.log isaac.log isaac_evidence.txt ulog lists, commander/interfaces logs, caveats.txt"
    find "$STACK_DIR" -maxdepth 1 -type f -newermt "@$START" 2>/dev/null | sed 's/^/    /'
    echo "$HOME/flight_logs/sim/uncollected_<date>/   tools/sim.sh down's ulog guard: every PX4 ulog of this session not under ~/flight_logs/sim (all 3 drones)"
    find "$HOME"/flight_logs/sim/uncollected_* -type f -newermt "@$START" 2>/dev/null | sed 's/^/    /'
    if [ -n "$BAG" ]; then
      if [ -e "$HOST_BAGS/$(basename "$BAG")" ]; then echo "$HOST_BAGS/$(basename "$BAG")/   this run's bag (commander's bag recorder) — STILL PRESENT (not removed)"
      else echo "$HOST_BAGS/$(basename "$BAG")/   this run's bag (commander's bag recorder); copied into runs/$NAME/, original removed"; fi
      [ -d "$STACK_DIR/$(basename "$BAG")" ] && echo "$STACK_DIR/$(basename "$BAG")/   tools/sim.sh down's copy of this run's bag (kept; same content as runs/$NAME/$(basename "$BAG"))"
    else echo "$HOST_BAGS/${PREFIX}_*   no bag of this run was found"; fi
    echo "$HOST_BAGS/$SENTINEL_NAME/   empty sentinel dir for tools/sim.sh down — removed: $( [ -e "$HOST_BAGS/$SENTINEL_NAME" ] && echo NO || echo yes)"
    if [ -n "$MOVED" ]; then for b in $MOVED; do
      echo "$HOST_BAGS/$b   PRE-EXISTING ENTRY NO LONGER IN PLACE AFTER tools/sim.sh down — LOOK IN $STACK_DIR/$b/"; done
    elif [ "$STAGE" = 6 ]; then echo "pre-existing entries of $HOST_BAGS (preflight.txt): all still in place after tools/sim.sh down"
    else echo "pre-existing entries of $HOST_BAGS (preflight.txt): not checked (tools/sim.sh down not run)"; fi
    echo "$I container: /tmp/svg_test/isaac.log (sim.sh), /tmp/tmp*/log/<date>/*.ulg (PX4 ulogs; gone when Isaac stops)"
    echo "$R container: /tmp/svg_test/interfaces.log (sim.sh); $D/ (stick, s1.toml, commander.log, stick.log, steps_flown.json)"
  } > "$OUT/outside_writes.txt"
}

cleanup() {          # every exit path after the start: land, our commander, logs/ulog, the checked down, bag, checks
  [ "$CLEANING" = 1 ] && return 0; CLEANING=1
  trap '' INT TERM HUP
  local why=$1
  ABORT_STAGE=$STAGE
  say "cleanup ($why) at stage $STAGE"
  if [ "$STAGE" -ge 1 ] && [ "$STAGE" -lt 6 ]; then
    [ "$STAGE" -ge 2 ] && [ "$STAGE" -lt 4 ] && zero_land_wait
    if [ "$STAGE" -ge 2 ] && [ "$STAGE" -lt 5 ]; then
      stop_commander || say "WARN: our commander still alive; tools/sim.sh down stops it"
      copy_logs; copy_ulog
      x docker exec "$R" rm -rf "${D:?}"
    fi
    sim_down                                   # exits through left_up when down cannot run safely or fails
  fi
  if [ "$STAGE" = 6 ]; then collect_bag_after_down; check_preexisting; fi
  [ "$DRY" = 1 ] && return 0
  write_aborted "$why"
  write_outside
}

on_signal() { say "ABORT: $1 received"; cleanup "signal $1"; exit 3; }
on_exit() { local rc=$?
  if [ "$STAGE" -ge 1 ] && [ "$STAGE" -lt 6 ] && [ "$CLEANING" = 0 ]; then cleanup "unexpected exit (rc $rc)"; fi
  release_lock; }

# ---------------------------------------------------------------------------------------------------------- session
take_lock
if [ "$DRY" = 0 ]; then
  trap on_exit EXIT
  trap 'on_signal INT' INT; trap 'on_signal TERM' TERM; trap 'on_signal HUP' HUP
  mkdir -p "$OUT"
  { echo "name=$NAME"; echo "pid=$$"; echo "started=$(date -Is)"; echo "start_epoch=$START"; echo "head=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)"; echo "script_head=$(git -C "$ROOT" rev-parse HEAD 2>/dev/null)"; echo "stack_repo=$REPO"
    echo "s1_toml_sha256=$(sha256sum "$ROOT/configs/s1.toml" | cut -d' ' -f1)"; echo "virtual_stick_sha256=$(sha256sum "$ROOT/scripts/virtual_stick.py" | cut -d' ' -f1)"
    echo "commander_config=$CONFIG_YAML scenario=$SCENARIO bag_prefix=$PREFIX drone=$DRONE"
    echo "gpu_before=$(nvidia-smi --query-gpu=name,memory.used --format=csv,noheader 2>/dev/null)"; } > "$OUT/session_meta.txt"
fi
say "record_steps.sh $NAME: AirStack simulator, sim only; $PLAN_LINE"
x "$PY" "$ROOT/scripts/virtual_stick.py" --config "$ROOT/configs/s1.toml" --plan-json "$OUT/steps.json" || die "steps.json not written"

# 0  preflight: the bags folder, checked again right before up (a recording may have started since the refusals)
bags_preflight
if [ "$DRY" = 1 ]; then echo "DRY: write $OUT/preflight.txt (ls -la $HOST_BAGS: $(echo $PRE_BAGS))"
else
  { echo "# $HOST_BAGS before tools/sim.sh up, $(date -Is); start_epoch=$START"
    echo "# checked: no svg_* entry changed after the start; every svg_* sorts before $SENTINEL_NAME (C and en_US.UTF-8)"
    ls -la --time-style=full-iso "$HOST_BAGS" 2>&1; } > "$OUT/preflight.txt"
fi

# 1  the stack: precheck, containers, Isaac (3 drones, headless), MAVROS interfaces
STAGE=1
if [ "$DRY" = 1 ]; then x "$SIM" up --headless
else
  echo "$SIM up --headless" >> "$OUT/commands.sh"
  "$SIM" up --headless 2>&1 | tee "$OUT/sim_up.log"; rc=${PIPESTATUS[0]}
  if grep -qE 'FAIL \(precheck\)|FAIL \(up\): real-drone' "$OUT/sim_up.log"; then
    STAGE=0
    if grep -qi 'real-drone' "$OUT/sim_up.log"; then
      say "!! REAL-DRONE/MOCAP SIGNAL FOUND BY tools/sim.sh up — NOTHING STARTED BY THIS SCRIPT, tools/sim.sh down NOT RUN"
    else say "tools/sim.sh up refused at its precheck — nothing started, tools/sim.sh down not run"; fi
    { echo "refused=$(date -Is)"; grep -E 'FAIL \((precheck|up)\)' "$OUT/sim_up.log"; } > "$OUT/REFUSED.txt"; exit 65
  fi
  [ "$rc" = 0 ] || die "tools/sim.sh up failed (rc $rc, see sim_up.log)"
fi
if [ "$DRY" = 1 ]; then echo "DRY: compare ls -1A $HOST_BAGS with docker exec $R ls -1A $BAGS (the bind mount)"
else
  [ "$(ls -1A "$HOST_BAGS" 2>&1)" = "$(docker exec "$R" ls -1A "$BAGS" 2>&1)" ] \
    || die "the host bags folder $HOST_BAGS and the container's $BAGS list different entries (bind mount?)"
fi

# 2  the commander with the bag recorder (teleop_single_ours.yaml names drone_1 only)
STAGE=2
x docker exec "$R" mkdir -p "$D"
x docker exec "$R" bash -c ": > $D/commander.log"
x docker exec -d "$R" bash -ic "$CMD_LAUNCH > $D/commander.log 2>&1"
wait_until 60 "SwarmCommander up | scenario=$SCENARIO" "log_count 'SwarmCommander up | scenario=$SCENARIO'" || die "commander not up"
wait_until 30 "bag recorder: recording all topics to $BAGS/${PREFIX}_*" "log_count 'recording all topics to $BAGS/${PREFIX}_'" || die "bag recorder did not start"
if [ "$DRY" = 0 ]; then
  docker exec "$R" grep -E 'REFUSED|Traceback' "$D/commander.log" && die "commander refused or crashed (commander.log)"
  BAG=$(docker exec "$R" grep -oE "recording all topics to $BAGS/${PREFIX}_[0-9_]+" "$D/commander.log" | tail -1 | sed 's/^recording all topics to //')
  bag_path_ok "$NAME" "$BAG" || die "bag path '$BAG' from commander.log is not $BAGS/${PREFIX}_<ts>"
  say "bag: $BAG"
fi

# 3  the virtual stick: takeoff, start, the steps, land (detached; polled from here)
if realdrone_signal; then
  stop_commander || true
  left_up 67 "REAL-DRONE/MOCAP SIGNAL BEFORE THE FLIGHT ($RD_WHAT) — NOTHING FLOWN, OUR COMMANDER STOPPED, tools/sim.sh down NOT RUN"
fi
x docker cp "$ROOT/scripts/virtual_stick.py" "$R:$D/virtual_stick.py" || die "docker cp virtual_stick.py"
x docker cp "$ROOT/configs/s1.toml" "$R:$D/s1.toml" || die "docker cp s1.toml"
STAGE=3
x docker exec -d "$R" bash -ic "$CMD_STICK > $D/stick.log 2>&1"
BOUND=$(( ${PLAN_S:-182} + 300 ))      # plan + takeoff (<= 90 s), start retries (<= 30 s), landing (<= 60 s), margin
if [ "$DRY" = 1 ]; then echo "DRY: wait <= ${BOUND} s (virtual_stick.py exits): alive $R virtual_stick; progress = new 'step k/36' lines of $D/stick.log"
else
  echo "# wait <= ${BOUND} s for virtual_stick.py to exit" >> "$OUT/commands.sh"
  t0=$SECONDS; last=""; sleep "$POLL_S"
  while alive "$R" virtual_stick; do
    [ $((SECONDS - t0)) -ge "$BOUND" ] && die "virtual_stick.py still running after $BOUND s (watchdog)"
    l=$(docker exec "$R" grep -E 'step [0-9]+/[0-9]+ onset|takeoff:|holding takeoff|start:|land:|FLOOR GUARD|error|refused|REFUSED' "$D/stick.log" 2>/dev/null | tail -1)
    [ "$l" != "$last" ] && [ -n "$l" ] && { say "stick: $l"; last=$l; }
    sleep "$POLL_S"; done
fi
if [ "$DRY" = 0 ]; then
  docker cp "$R:$D/stick.log" "$OUT/stick.log" 2>/dev/null
  STICK_RC=$(sed -n 's/.*virtual_stick: exit \([0-9]*\).*/\1/p' "$OUT/stick.log" | tail -1); STICK_RC=${STICK_RC:-unknown}
  say "virtual_stick.py exit $STICK_RC; $(grep -E 'landed:|steps reached' "$OUT/stick.log" | paste -sd' ')"
  if [ "$STICK_RC" = 67 ]; then
    stop_commander || true
    copy_logs
    left_up 67 "$(stick67_why host_stick_said)"
  fi
  [ "$STICK_RC" = 0 ] || die "virtual_stick.py exit $STICK_RC (see stick.log)"
fi
wait_until 60 "$DRONE disarmed (MAVROS armed: false)" armed_false || die "$DRONE still armed 60 s after the stick's landing"
STAGE=4

# 4  our commander stopped (the bag closes), logs + ulog, then — signals ignored, the drone is down — the checked
#    `down`, our bag from _stack, the checks
stop_commander || die "our commander did not stop within 30 s (the bag may be open)"
copy_logs
copy_ulog
x docker exec "$R" rm -rf "${D:?}"
STAGE=5
trap '' INT TERM HUP
sim_down
collect_bag_after_down || die "bag not collected (see session.log)"
check_preexisting
write_outside
[ "$DRY" = 1 ] && echo "DRY: on INT/TERM/HUP or any failure before the down sequence: pkill -INT the stick (it zeroes and lands whatever it may have taken off) -> unless a second commander was seen (then nothing is sent, exit 67) and only while ours is the one commander: if stick.log has this run's 'pre-takeoff:' line OR $DRONE is armed, zeros on $TELEOP, /swarm_commander/land, wait <= 60 s for armed: false -> our commander stopped -> logs, ulog -> the same down sequence (real-drone check, other-commander check, sentinel, pick check, down, verify) -> bag from $STACK_DIR, verified -> guarded removal -> sentinel removed -> pre-existing bags checked -> runs/$NAME/ABORTED.txt + outside_writes.txt; INT/TERM/HUP are ignored from the down sequence on"
if [ "$DRY" = 0 ]; then
  echo "finished=$(date -Is)" >> "$OUT/session_meta.txt"
  say "done: runs/$NAME/ (bag, drone_1 ulog, steps.json, steps_flown.json, logs, preflight.txt, outside_writes.txt)"
  [ -n "$MOVED" ] && say "!! WARNING: PRE-EXISTING BAG(S) NO LONGER IN $HOST_BAGS:$MOVED — SEE outside_writes.txt"
fi
exit 0
