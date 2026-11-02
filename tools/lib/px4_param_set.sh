#!/bin/bash
# tools/lib/px4_param_set.sh — set ONE PX4 parameter of a sim drone live through its MAVROS param node, read it back
# and write one changes.log line through the one formatter (changes_log.py, next to this file). SIM ONLY (iron rule 9).
# Runs INSIDE the robot container with ROS sourced: `tools/sim.sh param set` copies it and changes_log.py to
# /tmp/svg_param/ and runs it there (docs/CODING_STANDARD.md §3).
# Usage: px4_param_set.sh <drone_n> <NAME> <VALUE> <who> <log>
# Steps: ros2 param get (kind + old value) -> ros2 param set (fallback: ParamSetV2 service, force_set false — never
# forced: ledger #11, a forced set aborted mavros_node) -> ParamPull force_pull true -> ros2 param get (read-back) ->
# one line. The last stdout line is the changes.log line. Exit 0 = read back as set; 1 = read back differs (MISMATCH
# on the line, PARAM MISMATCH on stderr); 2 = bad arguments (nothing sent); 3 = the node has no such parameter.
# UNVERIFIED until an owner session: does `ros2 param set` on the MAVROS param node reach PX4 (U1); the ParamSetV2
# field names (U2). The read-back after a forced pull decides either way.
set -u
bad(){ echo "px4_param_set: $*" >&2; exit 2; }
[ $# -eq 5 ] || bad "usage: px4_param_set.sh <drone_n> <NAME> <VALUE> <who> <log> (got $# arguments)"
N=$1; NAME=$2; VALUE=$3; WHO=$4; LOG=$5
[[ "$N" =~ ^[1-9]$ ]] || bad "drone must be 1-9 (got '$N')"
[[ "$NAME" =~ ^[A-Z][A-Z0-9_]{0,15}$ ]] || bad "NAME must be a PX4 parameter name, upper case, <= 16 characters (got '$NAME')"
[[ "$VALUE" =~ ^-?[0-9]+(\.[0-9]*)?([eE][-+]?[0-9]+)?$ ]] || bad "VALUE must be a number (got '$VALUE')"
[[ "$WHO" =~ ^[A-Za-z0-9_.@:+-]+$ ]] || bad "who must match [A-Za-z0-9_.@:+-]+ (got '$WHO')"
HERE=$(cd "$(dirname "$0")" && pwd)
P=/drone_$N/interface/mavros/param

# get: "<Kind> <value>" of NAME on the param node; empty when it has none
get(){ timeout 30 ros2 param get "$P" "$NAME" 2>&1 | sed -nE 's/^(Double|Integer) value is: *([-+0-9.eE]+).*/\1 \2/p' | head -1; }

read -r KIND OLD <<<"$(get)"
[ -n "${KIND:-}" ] || { echo "px4_param_set: $P has no $NAME (sim stack up? name right?)" >&2; exit 3; }
if [ "$KIND" = Integer ]; then
  [[ "$VALUE" =~ ^-?[0-9]+$ ]] || bad "$NAME is an Integer parameter; VALUE must be a whole number (got '$VALUE')"
  TYPE=2; FIELD=integer_value
else
  [[ "$VALUE" =~ [.eE] ]] || VALUE=$VALUE.0       # `ros2 param set … 2` would send an integer to a Double parameter
  TYPE=3; FIELD=double_value
fi

VIA=""
if timeout 30 ros2 param set "$P" "$NAME" "$VALUE" 2>&1 | grep -q "Set parameter successful"; then
  VIA="ros2 param set"
elif timeout 30 ros2 service call "$P/set" mavros_msgs/srv/ParamSetV2 \
      "{force_set: false, param_id: $NAME, value: {type: $TYPE, $FIELD: $VALUE}}" 2>&1 | grep -q "success=True"; then
  VIA="ParamSetV2"
fi
timeout 120 ros2 service call "$P/pull" mavros_msgs/srv/ParamPull "{force_pull: true}" >/dev/null 2>&1 || true
read -r _ NEW <<<"$(get)"

LINE=$(python3 "$HERE/changes_log.py" append --log "$LOG" --name "drone_$N/$NAME" --old "${OLD:-}" --new "$VALUE" \
       --who "$WHO (via ${VIA:-no mechanism reported success})" --readback "${NEW:-}")
rc=$?
[ -n "$LINE" ] || { echo "px4_param_set: could not write the changes.log line to $LOG" >&2; exit 1; }
echo "$LINE"
[ -n "$VIA" ] || echo "px4_param_set: WARN neither ros2 param set nor ParamSetV2 reported success; the read-back decides" >&2
if [ $rc -ne 0 ]; then
  echo "PARAM MISMATCH: $NAME requested $VALUE, read back ${NEW:-nothing}" >&2
  exit 1
fi
exit 0
