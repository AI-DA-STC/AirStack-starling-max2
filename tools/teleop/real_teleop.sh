#!/usr/bin/env bash
# tools/teleop/real_teleop.sh — the REAL-drone gamepad front door, called through tools/real.sh.
# It checks the Logitech F310 pad inside the robot container and prepares the teleop config for one drone. It never
# starts the stack, a pane or a detached container process.
#
#   pad              the full pad check: static checks, then five stick moves (needs a terminal)
#   pad --static     the static checks only: no stick moves, no terminal needed
#   teleop drone_1   render the config for drone_1 on the laptop (tools/teleop/real_config.py), remove the old one in
#   teleop drone_2   the container, run the full pad check, and only after a PASS copy the new config to /tmp/svg_real/
#                    and print the diff, takeoff point and pane lines
#
# Exit: 0 PASS · 1 FAIL or refused · 2 cannot check (usage, docker or the robot container down, no terminal) · 3 Ctrl-C.
# Every decision is in tools/teleop/pad_core.py and real_config.py; tools/teleop/pad_check.py runs in the container.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SRC_YAML=$(cd "$HERE/../.." && pwd)/AirStack/robot/ros_ws/src/svg_ground_control/config/teleop_real_ours.yaml
R=airstack-robot-desktop-1
D=/tmp/svg_real                 # no regex characters: also a pkill pattern
NOISE='^(bash: cannot set terminal|bash: no job control|Sourcing|groups: cannot find name)'   # = tools/lib/stack.sh's
TMPD=""; CHECK_STARTED=0
cleanup() {
  [ -z "$TMPD" ] || rm -rf "$TMPD"
  [ "$CHECK_STARTED" = 0 ] || docker exec "$R" pkill -f __node:=svg_pad_check_joy >/dev/null 2>&1 || true   # backup: the check stops its own joy_node
}
trap cleanup EXIT

usage() {
  cat <<'USAGE'
usage: tools/real.sh pad [--static]   or   tools/real.sh teleop drone_1|drone_2
  tools/real.sh pad              check the Logitech F310 pad: static checks, then five stick moves (needs a terminal)
  tools/real.sh pad --static     the static checks only (no stick moves)
  tools/real.sh teleop drone_1   the full pad check, then the teleop config for drone_1 and the commands to run
  tools/real.sh teleop drone_2   the same for drone_2
real drone: it checks and prepares only. It starts nothing.
USAGE
}
die_usage() { usage >&2; echo "error: $*" >&2; exit 2; }
fail() { echo "PAD CHECK: FAIL — do not fly: $2"; exit "$1"; }

# guard: the first docker call. Refuses while Isaac Sim itself runs (the reverse of sim.sh's sim_only_guard: an idle
# isaac-sim container stays up after `sim.sh down`), and needs the robot container.
guard() {
  local names
  names=$(docker ps --format '{{.Names}}' 2>/dev/null) || fail 2 "docker is not answering (docker ps failed) — cannot check"
  if grep -qx isaac-sim <<< "$names"; then           # fail closed: only pgrep's 1 (no match) means "not running"
    local rc=0
    docker exec isaac-sim pgrep -f 'svg_multi_drone_single_domain\.py' >/dev/null 2>&1 || rc=$?
    case "$rc" in
      0) fail 1 "Isaac Sim running — real teleop refused" ;;
      1) ;;
      *) fail 2 "cannot tell whether Isaac Sim is running (docker exec isaac-sim pgrep exited $rc)" ;;
    esac
  fi
  grep -qx "$R" <<< "$names" \
    || fail 2 "the robot container ($R) is not running — start it: cd ~/AirStack-starling-max2/AirStack && ./airstack.sh up robot-desktop"
}

# run_pad_check [--static]: copy the two files in, run the check, pass its exit code on
run_pad_check() {
  local flags=(-i) rc=0
  [ -t 0 ] && flags+=(-t)
  docker exec "$R" mkdir -p "$D" >/dev/null \
    && docker cp "$HERE/pad_core.py" "$R:$D/" >/dev/null \
    && docker cp "$HERE/pad_check.py" "$R:$D/" >/dev/null \
    || fail 2 "could not copy the pad check into $R"
  CHECK_STARTED=1
  trap 'echo "PAD CHECK: FAIL — do not fly: stopped (Ctrl-C) — the check did not finish"; exit 3' INT TERM
  # the container's bash -ic noise is filtered line by line; the exit code is the check's own (PIPESTATUS[0])
  set +e
  docker exec "${flags[@]}" "$R" bash -ic "python3 $D/pad_check.py --pad f310${1:+ $1}" 2>&1 \
    | grep --line-buffered -v -E "$NOISE"
  rc=${PIPESTATUS[0]}
  set -e
  case "$rc" in
    0|1|2|3) return "$rc" ;;
    *) fail 2 "the pad check ended with code $rc — cannot check" ;;
  esac
}

cmd_pad() {
  local static=""
  case "$#:${1:-}" in
    0:) ;;
    1:--static) static=--static ;;
    *) die_usage "pad takes only --static (got: $*)" ;;
  esac
  if [ -z "$static" ] && ! [ -t 0 ] && [ "${REAL_TELEOP_NO_TTY_OK:-0}" != 1 ]; then    # REAL_TELEOP_NO_TTY_OK: unit tests only
    fail 2 "the stick test needs a terminal (Ctrl-C must reach it) — run it in a terminal tab, or use: tools/real.sh pad --static"
  fi
  guard
  run_pad_check $static
}

# cmd_teleop drone_1|drone_2: render on the laptop first (a drifted source is refused before the operator moves a stick),
# remove the old config in the container, run the full pad check, and only after a PASS copy the new config in and
# print the operator block that real_config.py made.
cmd_teleop() {
  [ $# -eq 1 ] || die_usage "teleop takes one drone: drone_1 or drone_2"
  local drone=$1 msg out
  msg=$(python3 "$HERE/real_config.py" check-drone -- "$drone" 2>&1) || die_usage "${msg#error: }"
  if ! [ -t 0 ] && [ "${REAL_TELEOP_NO_TTY_OK:-0}" != 1 ]; then    # REAL_TELEOP_NO_TTY_OK: unit tests only
    fail 2 "the stick test needs a terminal (Ctrl-C must reach it) — run it in a terminal tab"
  fi
  TMPD=$(mktemp -d) || fail 2 "cannot check: no temporary directory on the laptop"; out=$TMPD/teleop_real_$drone.yaml
  local rc=0
  python3 "$HERE/real_config.py" render --drone "$drone" --source "$SRC_YAML" --out "$out" > "$TMPD/block.txt" 2> "$TMPD/err" || rc=$?
  case "$rc" in
    0) ;;
    1) fail 1 "the $drone config was not made: $(sed 's/^error: render refused — //' "$TMPD/err" | head -1)" ;;
    *) fail 2 "cannot check: $(sed 's/^error: cannot check — //' "$TMPD/err" | head -1)" ;;
  esac
  guard
  docker exec "$R" rm -f "$D/teleop_real_$drone.yaml" >/dev/null \
    || fail 2 "could not remove the old $drone config in $R"      # only a fresh PASS leaves a config behind
  run_pad_check || return $?
  docker cp "$out" "$R:$D/teleop_real_$drone.yaml" >/dev/null || fail 2 "could not copy the $drone config into $R"
  cat "$TMPD/block.txt"
}

SUB=${1:-}
case "$SUB" in
  pad) shift; rc=0; cmd_pad "$@" || rc=$?; exit "$rc" ;;
  teleop) shift; rc=0; cmd_teleop "$@" || rc=$?; exit "$rc" ;;
  ""|-h|--help) usage; exit 2 ;;
  *) die_usage "unknown subcommand: $SUB" ;;
esac
