#!/bin/bash
# tools/lib/px4_param_set.sh — set ONE PX4 parameter of a sim drone live through its MAVROS param node, read it back
# and write one changes.log line through the one formatter (changes_log.py, next to this file). SIM ONLY (iron rule 9).
# Runs INSIDE the robot container with ROS sourced: `tools/sim.sh param set` copies it and changes_log.py to
# /tmp/svg_param/ and runs it there (docs/CODING_STANDARD.md §3).
# Usage: px4_param_set.sh <drone_n> <NAME> <VALUE> <who> <log>
# Steps: (safety) every ros2 call discovers LOCALHOST only, and the MAVROS of /drone_N must talk to the sim PX4
# (fcu_url = udp://:<14540+N>@172.31.0.200:<14580+N>, launch_sim_interfaces.sh) or nothing is sent (REFUSED) ->
# ros2 param get (kind + old value) -> ros2 param set (fallback: ParamSetV2 service, force_set false — never forced:
# ledger #11, a forced set aborted mavros_node) -> ParamPull force_pull true -> ros2 param get (read-back) -> one line.
# The last stdout line is the changes.log line. Exit 0 = read back as set after a successful set and pull;
# 1 = read back differs (MISMATCH) or nothing confirmed it (UNVERIFIED <why>: no set mechanism reported success, the
# pull failed so the read-back is MAVROS's cache, or no read-back); 2 = bad arguments, or REFUSED (not the sim);
# 3 = the param node has no such parameter. Exit 2 for bad arguments and 3 send nothing and log nothing.
# UNVERIFIED until an owner session: does `ros2 param set` on the MAVROS param node reach PX4 (U1); the ParamSetV2
# field names (U2); fcu_url lives on /drone_N/interface/mavros/mavros_node (mavros_node.cpp declares it there).
set -u
bad(){ echo "px4_param_set: $*" >&2; exit 2; }
[ $# -eq 5 ] || bad "usage: px4_param_set.sh <drone_n> <NAME> <VALUE> <who> <log> (got $# arguments)"
N=$1; NAME=$2; VALUE=$3; WHO=$4; LOG=$5
[[ "$N" =~ ^[1-9]$ ]] || bad "drone must be 1-9 (got '$N')"
[[ "$NAME" =~ ^[A-Z][A-Z0-9_]{0,15}$ ]] || bad "NAME must be a PX4 parameter name, upper case, <= 16 characters (got '$NAME')"
[[ "$VALUE" =~ ^-?[0-9]+(\.[0-9]*)?([eE][-+]?[0-9]+)?$ ]] || bad "VALUE must be a number (got '$VALUE')"
[[ "$WHO" =~ ^[A-Za-z0-9_.@:+-]+$ ]] || bad "who must match [A-Za-z0-9_.@:+-]+ (got '$WHO')"
HERE=$(cd "$(dirname "$0")" && pwd)
M=/drone_$N/interface/mavros
P=$M/param

# SAFETY: the robot container is on the host network with discovery range SUBNET: a MAVROS on the lab subnet with the
# same name and domain would answer. This process only ever talks to participants on this machine.
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
unset ROS_STATIC_PEERS

# line [append options…]: one changes.log line through the formatter; prints it, returns the formatter's status
line(){ python3 "$HERE/changes_log.py" append --log "$LOG" --name "drone_$N/$NAME" --new "$VALUE" "$@"; }

SIM_FCU="udp://:$((14540 + N))@172.31.0.200:$((14580 + N))"
FCU=$(timeout 30 ros2 param get "$M/mavros_node" fcu_url 2>&1 | sed -nE 's/^String value is: *//p' | head -1)
if [ "$FCU" != "$SIM_FCU" ]; then
  why="$M/mavros_node fcu_url is '${FCU:-unreadable}', not the sim PX4 $SIM_FCU; nothing sent"
  line --who "$WHO" --refused "$why"       # printed: the last stdout line, which sim.sh copies to the host log
  echo "px4_param_set: REFUSED: $why" >&2
  exit 2
fi

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
PULL_OK=0
timeout 120 ros2 service call "$P/pull" mavros_msgs/srv/ParamPull "{force_pull: true}" 2>&1 | grep -q "success=True" && PULL_OK=1
read -r _ NEW <<<"$(get)"

WHY=""
[ -n "$VIA" ] || WHY="no set mechanism reported success"
[ -n "${NEW:-}" ] || WHY="${WHY:+$WHY; }no read-back"
[ "$PULL_OK" = 1 ] || [ -z "${NEW:-}" ] || WHY="${WHY:+$WHY; }param pull did not succeed, read-back is the MAVROS cache"
OUT=$(line --old "${OLD:-}" --who "$WHO (via ${VIA:-no mechanism})" --readback "${NEW:-}" ${WHY:+--unverified "$WHY"})
rc=$?
[ -n "$OUT" ] || { echo "px4_param_set: could not write the changes.log line to $LOG" >&2; exit 1; }
echo "$OUT"
[ $rc -eq 0 ] && exit 0
case "$OUT" in *" · MISMATCH"*) echo "PARAM MISMATCH: $NAME requested $VALUE, read back ${NEW:-nothing}" >&2 ;; esac
[ -z "$WHY" ] || echo "PARAM UNVERIFIED: $NAME requested $VALUE: $WHY" >&2
exit 1
