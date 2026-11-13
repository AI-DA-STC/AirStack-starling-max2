#!/usr/bin/env bash
# tools/teleop/real_teleop.sh — the REAL-drone gamepad front door, called through tools/real.sh.
# It checks the Logitech F310 pad inside the robot container. It never starts the stack, a pane or a
# detached container process.
#
#   pad            the full pad check: static checks, then five stick moves (needs a terminal)
#   pad --static   the static checks only: no stick moves, no terminal needed
#
# Exit: 0 PASS · 1 FAIL or refused · 2 cannot check (usage, docker or the robot container down, no terminal) · 3 Ctrl-C.
# Every decision is in tools/teleop/pad_core.py; tools/teleop/pad_check.py runs it in the container.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
R=airstack-robot-desktop-1
D=/tmp/svg_real                 # no regex characters: also a pkill pattern

usage() {
  cat <<'USAGE'
usage: tools/real.sh pad [--static]
  tools/real.sh pad            check the Logitech F310 pad: static checks, then five stick moves (needs a terminal)
  tools/real.sh pad --static   the static checks only (no stick moves)
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
  if grep -qx isaac-sim <<< "$names" && docker exec isaac-sim pgrep -f 'svg_multi_drone_single_domain\.py' >/dev/null 2>&1; then
    fail 1 "Isaac Sim running — real teleop refused"
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
  trap 'docker exec "$R" pkill -f __node:=svg_pad_check_joy >/dev/null 2>&1 || true' EXIT   # backup: the check stops its own joy_node
  trap 'echo "PAD CHECK: FAIL — do not fly: stopped (Ctrl-C) — the check did not finish"; exit 3' INT TERM
  docker exec "${flags[@]}" "$R" bash -ic "python3 $D/pad_check.py --pad f310${1:+ $1}" || rc=$?
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

SUB=${1:-}
case "$SUB" in
  pad) shift; rc=0; cmd_pad "$@" || rc=$?; exit "$rc" ;;
  ""|-h|--help) usage; exit 2 ;;
  *) die_usage "unknown subcommand: $SUB" ;;
esac
