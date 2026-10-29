#!/usr/bin/env bash
# tools/lib/stack.sh — the shared sim-stack phases (precheck up watch isaac interfaces ifgates odom_gates commander params
# copy_ulogs down status) and helpers, extracted from tools/sim_hover_step_run.sh. SIM ONLY (CLAUDE.md iron rule 9).
# SOURCE it, after the caller sets:  RUN OUT HEAVY S SCENARIO BAG_PREFIX CONFIG HEADLESS
#   optional: USE_STUDIO (default false: add use_foxglove_studio:=true to the commander launch), ISAAC_KIT_ARGS
# Hooks the caller may define:  bag_dump_hook <bag_dir> (down; non-zero = bag stays in the container)
#   ABORT_HOOK / REPORT_HOOK = names of functions run by abort_trap.
# Sourcing runs nothing else; a required variable unset -> "stack.sh: <VAR> unset" on stderr and return 2.
set -o pipefail            # no -e: every failure that matters is an explicit `|| fail`
for _v in RUN OUT HEAVY S SCENARIO BAG_PREFIX CONFIG HEADLESS; do
  [ -n "${!_v:-}" ] || { echo "stack.sh: $_v unset" >&2; return 2; }
done; unset _v
USE_STUDIO=${USE_STUDIO:-false}
ISAAC_KIT_ARGS=${ISAAC_KIT_ARGS:-}           # opt-in extra Kit args appended to the Isaac launch (default none)
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
TOOLS=$REPO/tools
R=airstack-robot-desktop-1; I=isaac-sim
NOISE='^(bash: cannot set terminal|bash: no job control|Sourcing|groups: cannot find name)'
BAGS=/root/AirStack/robot/ros_ws/bags        # inside $R; host path AirStack/robot/ros_ws/bags (gitignored)

ISAAC_CMD='PYTHONUNBUFFERED=1 DRONE_USD=/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd PX4_VEHICLE_MODEL=pegasus_starling2max NUM_ROBOTS=3 SVG_DOMAIN_ID=1 PLAY_SIM_ON_START=true ISAAC_SIM_HEADLESS='"$HEADLESS"' PYTHONPATH="$ISAAC_SIM_PYTHONPATH" /isaac-sim/python.sh /isaac-sim/AirStack/simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py --ext-folder ~/.local/share/ov/data/documents/Kit/shared/exts'"${ISAAC_KIT_ARGS:+ $ISAAC_KIT_ARGS}"
IF_CMD='cd ~/AirStack/robot/ros_ws && ./src/svg_ground_control/scripts/launch_sim_interfaces.sh 3'
CMD_CMD='cd ~/AirStack/robot/ros_ws && ros2 launch svg_ground_control ground_control.launch.py config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/'"$CONFIG"' scenario:='"$SCENARIO"' record_bag:=true bag_prefix:='"$BAG_PREFIX"
[ "$USE_STUDIO" = true ] && CMD_CMD="$CMD_CMD use_foxglove_studio:=true"
PARAM_KEYS="SYS_AUTOSTART MAV_SYS_ID MC_PITCHRATE_P MC_ROLLRATE_P LNDMC_ROT_MAX MPC_XY_VEL_MAX MPC_THR_HOVER IMU_GYRO_CUTOFF IMU_DGYRO_CUTOFF MPC_Z_VEL_MAX_DN MPC_ACC_HOR"

# ----------------------------------------------------------------------------------------------------- helpers
say()  { echo "[$(date '+%T %Z')] $*" | tee -a "$OUT/run.log"; }
note() { echo "$*" >> "$OUT/commands.sh"; }                # the exact commands used, for the record
nx()   { note "$*"; "$@"; }                                 # note + run a host command
fail() { say "FAIL ($PHASE): $*"
  if [ "${ALL_MODE:-0}" = 1 ] && [ "${STACK_UP:-0}" = 1 ] && [ "$PHASE" != down ]; then
    say "all: stack is up after a FAIL in $PHASE -> running down (ulogs + logs are copied, bag kept if present)"; STACK_UP=0; PHASE=down; down || true; fi
  exit 1; }
caveat() { echo "$*" >> "$OUT/caveats.txt"; say "CAVEAT: $*"; }
rx()   { docker exec "$R" bash -ic "$*" 2>&1 | grep -v -E "$NOISE" || true; }      # robot container, profile noise dropped
ix()   { docker exec "$I" bash -ic "$*" 2>&1 | grep -v -E "$NOISE" || true; }      # isaac container
# alive <container> <args regex>: a NON-zombie process whose command line matches (PID 1 in both containers is
# `sleep`, which never reaps, so pgrep alone keeps matching <defunct> leftovers of earlier sessions)
alive() { docker exec "$1" ps -eo stat,args 2>/dev/null | awk '$1 !~ /^Z/' | grep -qE -- "$2"; }
# wait_for <timeout s> <interval s> <description> <command…>: succeed when the command's stdout is a number >= $NEED
wait_for() { local t=$1 iv=$2 d=$3; shift 3; local el=0 n=0
  while :; do n=$("$@" 2>/dev/null | tail -1 | tr -dc '0-9'); n=${n:-0}
    [ "$n" -ge "${NEED:-1}" ] && { say "$d: $n (after ${el}s)"; return 0; }
    [ "$el" -ge "$t" ] && { say "$d: $n after ${el}s (timeout)"; return 1; }
    sleep "$iv"; el=$((el+iv)); done; }
json1() { local i; for i in 1 2 3 4 5 6; do rx "timeout 15 ros2 topic echo --once $1 --field data" | grep -m1 '^{' && return 0; sleep 3; done; return 1; }   # first JSON line, retried
count_log() { local n; n=$(docker exec "$1" grep -c "$2" "$3" 2>/dev/null | tail -1); echo "${n:-0}"; }   # grep -c prints 0 on no match
mavros_connected() { rx "timeout 10 ros2 topic echo --once /drone_$1/interface/mavros/state" | grep -q '^connected: true'; }
# phase_begin <phase> [files…]: marker in run.log + commands.sh ("(re-run)" when this phase ran before in this run
# dir), then truncate the phase's own output files. Never truncates run.log, commands.sh, verdicts.log, caveats.txt.
phase_begin() { local p=$1 tag="== phase $1 =="; shift
  [ "$p" = isaac ] && rm -f "$OUT/ulogs_copied.ok"
  grep -qF -- "$tag" "$OUT/run.log" 2>/dev/null && tag="== phase $p (re-run) =="
  say "$tag"; note "# $tag  $(date '+%F %T %Z')"
  local f; for f in "$@"; do : > "$OUT/$f"; done; }
isaac_evidence() {   # counts from isaac.log → isaac_evidence.txt (the report gates starling_cfg/autostart/ready/unknown_model/cooking)
  local tmp; tmp=$(mktemp)
  if docker exec "$I" bash -c "L=$S/isaac.log; echo model_line=\$(grep -c 'PX4 model: pegasus_starling2max' \$L) starling_cfg=\$(grep -c Starling2MaxConfig \$L) autostart=\$(grep -c 'SYS_AUTOSTART=10090' \$L) unknown_model=\$(grep -c 'Unknown model' \$L) cooking=\$(grep -ciE 'cook.*(warn|error)|(warn|error).*cook' \$L) ready=\$(grep -c 'Ready for takeoff' \$L)" > "$tmp" 2>/dev/null && [ -s "$tmp" ]; then
    mv "$tmp" "$OUT/isaac_evidence.txt"; tee -a "$OUT/run.log" < "$OUT/isaac_evidence.txt"
  else rm -f "$tmp"; say "WARN: could not read $S/isaac.log for isaac_evidence.txt"; fi; }


# ------------------------------------------------------------------------------------------------------ phases
precheck() {
  phase_begin precheck
  say "precheck: no real-drone bridge on the laptop, port 8765 free, drone battery out (sim shares domain 1)"
  say "WARN: Isaac start/stop can crash the WiFi firmware (iwlwifi) — use Ethernet or sit at the laptop"
  [ "$HEADLESS" = false ] && [ -z "${DISPLAY:-}" ] && fail "no DISPLAY for the Isaac window — use --headless" || true
  { pgrep -x MicroXRCEAgent || pgrep -f '^(bash|sh) .*mocap\.sh' || pgrep -x natnet_ros2 ; } 2>/dev/null && fail "a real-drone/mocap bridge is running on the laptop" || true
  ss -ltnp 2>/dev/null | grep -q ':8765 ' && fail "port 8765 already in use (stray foxglove_bridge)" || true
  nvidia-smi --query-gpu=name,memory.used --format=csv,noheader | tee -a "$OUT/run.log"
}

up() {
  phase_begin up run_meta.txt
  note "cd $REPO/AirStack && ./airstack.sh up"
  (cd "$REPO/AirStack" && timeout 180 ./airstack.sh up) 2>&1 | tail -5 | tee -a "$OUT/run.log"
  for c in $I $R; do docker ps --format '{{.Names}} {{.Status}}' | grep -q "^$c Up" || fail "$c is not Up"; done
  nx docker exec "$I" mkdir -p "$S"; nx docker exec "$R" mkdir -p "$S"
  # the one command that settles the shared-domain guard: no real-drone or mocap topics on domain 1
  note "docker exec $R bash -ic 'ros2 daemon stop; ros2 topic list --no-daemon --spin-time 5' | grep -E '/fmu/|/poses|/pose\$'"
  local t; t=$(rx 'ros2 daemon stop >/dev/null 2>&1; ros2 topic list --no-daemon --spin-time 5' | grep -E '/fmu/|/poses|/pose$' || true)
  [ -z "$t" ] || fail "real-drone/mocap topics on domain 1: $t"
  note "git -C $REPO rev-parse HEAD; git -C $REPO status --porcelain -- tools | wc -l   # -> run_meta.txt"
  { echo "head=$(git -C "$REPO" rev-parse HEAD)"; echo "head_short=$(git -C "$REPO" rev-parse --short HEAD)"
    echo "dirty_tools=$(git -C "$REPO" status --porcelain -- tools | wc -l)"; echo "started=$(date -Is)"; echo "tz=$(date +%Z)"
    echo "run=$RUN"; echo "steps_per_axis=$STEPS_PER_AXIS"; } > "$OUT/run_meta.txt"
  tee -a "$OUT/run.log" < "$OUT/run_meta.txt"
  say "up: containers running, domain 1 clean"
}

watch() {
  [ -f "$OUT/.watch_pid" ] && kill -0 "$(cat "$OUT/.watch_pid")" 2>/dev/null && { kill "$(cat "$OUT/.watch_pid")" 2>/dev/null; sleep 1; }
  phase_begin watch res_watch.log
  note "nohup $REPO/localisation/scripts/sim_resources_watch.sh $OUT/res_watch.log &"
  nohup "$REPO/localisation/scripts/sim_resources_watch.sh" "$OUT/res_watch.log" >/dev/null 2>&1 &
  echo $! > "$OUT/.watch_pid"; sleep 3
  [ "$(wc -l < "$OUT/res_watch.log")" -ge 2 ] && say "watch: running (pid $(cat "$OUT/.watch_pid"))" || say "WARN: res_watch not writing"
}

isaac() {
  phase_begin isaac isaac_evidence.txt
  if alive "$I" svg_multi_drone_single_domain.py; then say "Isaac launcher already running; not relaunching"
    [ -f "$OUT/isaac.log.start" ] || date +%s > "$OUT/isaac.log.start"
  else
    docker exec "$I" bash -c ": > $S/isaac.log"      # a stale log from an earlier session would satisfy wait_for before the launch truncates it
    note "docker exec -d $I bash -ic '$ISAAC_CMD > $S/isaac.log 2>&1'"
    date +%s > "$OUT/isaac.log.start"
    docker exec -d "$I" bash -ic "$ISAAC_CMD > $S/isaac.log 2>&1"
  fi
  NEED=3 wait_for 600 5 "Ready for takeoff" count_log "$I" 'Ready for takeoff' "$S/isaac.log" || fail "Isaac not ready"
  isaac_evidence
  grep -q 'unknown_model=0' "$OUT/isaac_evidence.txt" || fail "PX4 reported Unknown model (airframe mount missing?)"
  local n; n=$(sed -n 's/.*starling_cfg=\([0-9]*\).*/\1/p' "$OUT/isaac_evidence.txt"); n=${n:-0}
  [ "$n" -ge 3 ] || say "WARN: Starling2MaxConfig printed $n times (report will mark it UNVERIFIED)"
  grep -q WIFI-ALERT "$OUT/res_watch.log" 2>/dev/null && say "!! WIFI-ALERT in res_watch.log — tell the user; the sim is still running" || true
}

interfaces() {
  phase_begin interfaces odom_hz.txt topics_of_interest.txt clock_check.txt
  if alive "$R" launch_sim_interfaces.sh; then say "interfaces launcher already running; not relaunching"
  else docker exec "$R" bash -c ": > $S/interfaces.log"; note "docker exec -d $R bash -ic '$IF_CMD > $S/interfaces.log 2>&1'"; docker exec -d "$R" bash -ic "$IF_CMD > $S/interfaces.log 2>&1"; fi
  # readiness = each namespace's MAVROS reports connected: true (not raw HEARTBEAT lines, which a respawned mavros re-prints)
  note "for N in 1 2 3: docker exec $R bash -ic 'timeout 10 ros2 topic echo --once /drone_\$N/interface/mavros/state' | grep '^connected: true'"
  local N t0
  for N in 1 2 3; do t0=$SECONDS
    until mavros_connected "$N"; do
      [ $((SECONDS - t0)) -ge 120 ] && fail "drone_$N MAVROS never reported connected: true (120 s)"
      sleep 3; done
    say "drone_$N MAVROS connected (after ~$((SECONDS - t0))s)"; done
  [ "$(count_log "$R" 'exit code -11' "$S/interfaces.log")" = 0 ] || say "WARN: mavros segfault(s) in interfaces.log (respawned)"
  odom_gates
}

ifgates() { phase_begin ifgates odom_hz.txt topics_of_interest.txt clock_check.txt; odom_gates; }   # alias: gates only, no launch

odom_gates() {   # odometry from every drone (PX4's local position needs a few seconds after connect), rate, topics, /clock
  local N i t0
  note "for N in 1 2 3: docker exec $R bash -ic 'timeout 10 ros2 topic echo --once /drone_\$N/odometry_conversion/odometry --field pose.pose.position'  (retry <= 90 s)"
  for N in 1 2 3; do t0=$SECONDS; i=0
    until rx "timeout 10 ros2 topic echo --once /drone_$N/odometry_conversion/odometry --field pose.pose.position" | grep -q '^x:'; do
      i=$((i+1)); say "drone_$N odometry: not yet (attempt $i, $((SECONDS - t0)) s)"
      [ $((SECONDS - t0)) -ge 90 ] && fail "no odometry for drone_$N after 90 s"
      sleep 3; done
    say "drone_$N odometry: ok (after $((SECONDS - t0)) s)"; done
  note "docker exec $R bash -ic 'timeout 15 ros2 topic hz /drone_1/odometry_conversion/odometry -w 200'"
  rx 'timeout 15 ros2 topic hz /drone_1/odometry_conversion/odometry -w 200' | grep 'average rate' | tail -1 | tee "$OUT/odom_hz.txt" | tee -a "$OUT/run.log"
  rx 'ros2 topic list' | grep -E 'target_attitude|/clock$' | tee "$OUT/topics_of_interest.txt" | tee -a "$OUT/run.log" || true
  note "docker exec $R bash -ic 'ros2 topic info /clock; echo clock_rc=\$?'   # 0 = /clock exists, 1 = unknown topic"
  rx 'ros2 topic info /clock >/dev/null 2>&1; echo clock_rc=$?' | grep clock_rc > "$OUT/clock_check.txt"
  tee -a "$OUT/run.log" < "$OUT/clock_check.txt"
  say "interfaces: 3 drones with odometry"
}

commander() {
  phase_begin commander status_pre.json bag_status_pre.json
  if alive "$R" swarm_commander && [ "$(count_log "$R" "SwarmCommander up | scenario=$SCENARIO" "$S/commander.log")" -ge 1 ]; then say "commander already up (scenario $SCENARIO); not relaunching"
  else docker exec "$R" bash -c ": > $S/commander.log"; note "docker exec -d $R bash -ic '$CMD_CMD > $S/commander.log 2>&1'"; docker exec -d "$R" bash -ic "$CMD_CMD > $S/commander.log 2>&1"; fi   # stale log -> stale count
  NEED=1 wait_for 60 2 "SwarmCommander up" count_log "$R" "SwarmCommander up | scenario=$SCENARIO" "$S/commander.log" || fail "commander not up with scenario=$SCENARIO"
  docker exec "$R" grep -E 'REFUSED|took over|Traceback' "$S/commander.log" && fail "commander refused/crashed (see commander.log)" || true
  note "poll <= 30 s every 2 s: docker exec $R bash -ic 'timeout 8 ros2 topic echo --once /svg/commander_status --field data'  # last snapshot -> status_pre.json"
  local t0=$SECONDS ok=0
  while :; do
    rx 'timeout 8 ros2 topic echo --once /svg/commander_status --field data' | grep -m1 '^{' > "$OUT/status_pre.json" || : > "$OUT/status_pre.json"
    if [ -s "$OUT/status_pre.json" ] && python3 - "$OUT/status_pre.json" "$SCENARIO" <<'PY' | tee -a "$OUT/run.log"
import json, sys
j = json.load(open(sys.argv[1])); st = [d["state"] for d in j["drones"]]; fr = [d.get("odom_fresh") for d in j["drones"]]
print("scenario", j["scenario"], "states", st, "fresh", fr, "tuning", j.get("tuning"))
sys.exit(0 if j["scenario"] == sys.argv[2] and st == ["IDLE"] * 3 and all(fr) else 1)
PY
    then ok=1; break; fi
    [ $((SECONDS - t0)) -ge 30 ] && break
    sleep 2
  done
  [ "$ok" = 1 ] || fail "commander_status is not scenario=$SCENARIO with 3 IDLE, odom-fresh drones after 30 s (see status_pre.json)"
  json1 /svg/bag_recorder/status | tee "$OUT/bag_status_pre.json" | tee -a "$OUT/run.log" || true
}

params() {   # secondary, read-only proof via MAVROS (names verified live); the ulog header in `collect` is authoritative
  phase_begin params params_mavros_names.txt params_mavros.txt
  note "docker exec $R bash -ic 'ros2 service list | grep /drone_1/interface/mavros/param; ros2 node list | grep /drone_1/interface/mavros'"
  rx 'ros2 service list | grep -E "/drone_1/interface/mavros/param"; ros2 node list | grep -E "/drone_1/interface/mavros"' | tee "$OUT/params_mavros_names.txt" >/dev/null
  if grep -q 'param/pull' "$OUT/params_mavros_names.txt"; then
    note "docker exec $R bash -ic 'ros2 service call /drone_1/interface/mavros/param/pull mavros_msgs/srv/ParamPull \"{force_pull: false}\"; ros2 param get <param node> <P>'"
    rx 'timeout 60 ros2 service call /drone_1/interface/mavros/param/pull mavros_msgs/srv/ParamPull "{force_pull: false}"' | tail -1 | tee -a "$OUT/run.log"
    local pnode; pnode=$(grep -m1 -E '^/drone_1/interface/mavros/param$|^/drone_1/interface/mavros$' "$OUT/params_mavros_names.txt" || true)
    : > "$OUT/params_mavros.txt"
    for p in SYS_AUTOSTART MC_PITCHRATE_P MC_ROLLRATE_P LNDMC_ROT_MAX MPC_XY_VEL_MAX MPC_THR_HOVER IMU_GYRO_CUTOFF IMU_DGYRO_CUTOFF MPC_Z_VEL_MAX_DN MPC_ACC_HOR; do
      [ -n "$pnode" ] && rx "timeout 10 ros2 param get $pnode $p" | sed "s/^/$p: /" >> "$OUT/params_mavros.txt"; done
    tee -a "$OUT/run.log" < "$OUT/params_mavros.txt"
    grep -q 'MC_PITCHRATE_P: .*0\.032' "$OUT/params_mavros.txt" && grep -q 'LNDMC_ROT_MAX: .*300' "$OUT/params_mavros.txt" \
      && say "params: 10-20 airframe confirmed via MAVROS" || say "params: MAVROS read inconclusive — ulog header will decide"
  else say "params: no MAVROS param service — ulog header will decide"; fi
}

copy_ulogs() {   # PX4 ulogs of THIS session (newer than isaac.log.start), one per MAV_SYS_ID 2/3/4 = drone_1/2/3 -> $HEAVY; must run BEFORE Isaac stops
  local START sid f sz; START=$(cat "$OUT/isaac.log.start" 2>/dev/null); START=${START:-0}
  note "docker exec $I bash -c 'for f in /tmp/tmp*/log/*/*.ulg; do [ \$(stat -c %Y \$f) -gt $START ] && echo \$f; done'  # -> ulog_list.txt"
  docker exec "$I" bash -c "for f in /tmp/tmp*/log/*/*.ulg; do [ -f \"\$f\" ] && [ \$(stat -c %Y \"\$f\") -gt $START ] && echo \"\$f\"; done" > "$OUT/ulog_list.txt" || true
  : > "$OUT/ulog_sysid_map.txt"
  note "docker exec $I python3 -c \"from pyulog import ULog; print(ULog(f, message_name_filter_list=['vehicle_local_position']).initial_parameters.get('MAV_SYS_ID'))\"  # -> ulog_sysid_map.txt"
  while read -r f; do [ -n "$f" ] || continue
    sid=$(docker exec "$I" python3 -c "from pyulog import ULog; print(ULog('$f', message_name_filter_list=['vehicle_local_position']).initial_parameters.get('MAV_SYS_ID'))" 2>/dev/null)
    sz=$(docker exec "$I" stat -c %s "$f" 2>/dev/null)
    case "$sid" in 2|3|4) echo "$sid $f ${sz:-0}" >> "$OUT/ulog_sysid_map.txt" ;; *) say "WARN: ulog $f has MAV_SYS_ID '$sid' (not 2/3/4) — skipped" ;; esac
  done < "$OUT/ulog_list.txt"
  sort -n -o "$OUT/ulog_sysid_map.txt" "$OUT/ulog_sysid_map.txt"; tee -a "$OUT/run.log" < "$OUT/ulog_sysid_map.txt"
  note "docker cp $I:<ulog> $HEAVY/drone_<sid-1>_sysid<sid>_<basename>.ulg"
  while read -r sid f sz; do [ -n "$f" ] || continue
    docker cp "$I:$f" "$HEAVY/drone_$((sid-1))_sysid${sid}_$(basename "$f")" || say "WARN: docker cp of $f failed"; done < "$OUT/ulog_sysid_map.txt"
  local have=""; for sid in 2 3 4; do ls "$HEAVY"/drone_*_sysid${sid}_*.ulg >/dev/null 2>&1 && have="$have $sid"; done
  if [ "$have" = " 2 3 4" ]; then touch "$OUT/ulogs_copied.ok"; say "ulogs copied for sysids 2 3 4 -> $HEAVY"
  else say "WARN: ulogs copied:${have:- none} (need 2 3 4)"; fi
}

down() {   # commander -> bag out -> interfaces -> ulogs (if not yet) -> Isaac -> orphans -> watch; containers stay up (no airstack.sh down)
  phase_begin down bag_evidence.txt bag_path.txt
  trap '' INT      # a second Ctrl-C must not re-enter the abort handler against a half-dismantled stack
  local i b
  nx docker exec "$R" pkill -INT -f ground_control.launch.py || true
  for i in $(seq 1 25); do alive "$R" ground_control.launch.py || break; sleep 1; done
  alive "$R" ground_control.launch.py && say "WARN: commander still alive 25 s after SIGINT" || true
  docker exec "$R" grep -E "stopped: .*${BAG_PREFIX}_|recorder exited|record_on_start" "$S/commander.log" | tee "$OUT/bag_evidence.txt" | tee -a "$OUT/run.log" || true
  # the rosbag: written root-owned under the repo (AirStack/robot/ros_ws/bags, gitignored) -> heavy dir, CSVs out, then (and only then) removed
  note "docker exec $R bash -c 'ls -d $BAGS/${BAG_PREFIX}_* | tail -1'; docker cp $R:<bag> $HEAVY/"
  b=$(docker exec "$R" bash -c "ls -d $BAGS/${BAG_PREFIX}_* 2>/dev/null | tail -1")
  [ -n "$b" ] && echo "$b" > "$OUT/bag_path.txt"
  local bagfail=0
  if [ -z "$b" ]; then caveat "no ${BAG_PREFIX} bag found in the robot container ($BAGS)"
  elif docker cp "$R:$b" "$HEAVY/" && [ -f "$HEAVY/$(basename "$b")/metadata.yaml" ]; then
    say "bag copied to $HEAVY/$(basename "$b")"
    declare -F bag_dump_hook >/dev/null && { bag_dump_hook "$b" || bagfail=1; }      # hook non-zero = bag LEFT in the container
    [ "$bagfail" = 1 ] || nx docker exec "$R" rm -rf "$b"
  else say "WARN: bag copy failed — bag LEFT in the container at $b"; echo "bag copy failed; bag left at $b" >> "$OUT/caveats.txt"; fi
  nx docker exec "$R" pkill -INT -f launch_sim_interfaces.sh || true
  for i in $(seq 1 25); do alive "$R" mavros_node || break; sleep 1; done
  alive "$R" mavros_node && { say "WARN: interface nodes still alive 25 s after SIGINT — TERM"; docker exec "$R" pkill -TERM -f 'sim_drone_interface|mavros_node|robot_interface|odometry_conversion' || true; }
  for f in commander interfaces; do docker cp "$R:$S/$f.log" "$OUT/$f.log" 2>/dev/null || say "WARN: no $f.log in the robot container"; done
  [ -f "$OUT/ulogs_copied.ok" ] && say "ulogs already copied (collect)" || copy_ulogs      # BEFORE Isaac stops: /tmp/tmp*/log vanishes with it
  nx docker exec "$I" pkill -INT -f svg_multi_drone_single_domain.py || true
  for i in $(seq 1 40); do alive "$I" svg_multi_drone_single_domain.py || break; sleep 1; done
  if alive "$I" svg_multi_drone_single_domain.py; then
    docker exec "$I" pkill -TERM -f svg_multi_drone_single_domain.py; sleep 10
    docker exec "$I" pkill -KILL -f svg_multi_drone_single_domain.py || true; say "WARN: Isaac needed TERM/KILL"; fi
  if alive "$I" '(^|/)px4( |$)'; then nx docker exec "$I" pkill -9 -x px4 || true; say "orphaned PX4 SITL instances killed (Isaac's exit leaves them)"; fi
  nx docker exec "$R" pkill -f position_setpoint_pub || true     # the interface launch leaves these behind
  docker cp "$I:$S/isaac.log" "$OUT/isaac.log" 2>/dev/null || say "WARN: no isaac.log in the isaac container"
  isaac_evidence
  sleep 30; grep WIFI-ALERT "$OUT/res_watch.log" 2>/dev/null | tee -a "$OUT/run.log" || say "no WIFI-ALERT during the run"
  [ -f "$OUT/.watch_pid" ] && { kill "$(cat "$OUT/.watch_pid")" 2>/dev/null || true; rm -f "$OUT/.watch_pid"; }
  for f in "$OUT"/*.log; do case "$(basename "$f")" in run.log|verdicts.log) continue;; esac
    [ "$(stat -c %s "$f")" -gt 1000000 ] && { gzip -c "$f" > "$HEAVY/$(basename "$f").gz"; echo "too big for the repo: moved to $HEAVY/$(basename "$f").gz" > "$f"; say "$(basename "$f") > 1 MB: gzipped to $HEAVY"; } ; done; true
  say "down: stack stopped, containers left up"
}

status() {
  docker ps --format '{{.Names}} {{.Status}}' | grep -E "$I|$R" || echo "containers down"
  echo "ready: $(count_log "$I" 'Ready for takeoff' "$S/isaac.log")  (isaac launcher alive: $(alive "$I" svg_multi_drone_single_domain.py && echo yes || echo no))"
  local N; for N in 1 2 3; do echo "drone_$N connected: $(mavros_connected "$N" && echo yes || echo no)"; done
  echo "commander: up count $(count_log "$R" 'SwarmCommander up' "$S/commander.log")  (alive: $(alive "$R" swarm_commander && echo yes || echo no))"
  echo "bag recorder: $(rx 'timeout 8 ros2 topic echo --once /svg/bag_recorder/status --field data' | head -c 200)"
  [ -f "$OUT/.watch_pid" ] && kill -0 "$(cat "$OUT/.watch_pid")" 2>/dev/null && echo "watch alive: $(tail -1 "$OUT/res_watch.log")" || echo "watch not running"
  [ -f "$OUT/verdicts.log" ] && tail -1 "$OUT/verdicts.log" || echo "no verdicts yet"
  grep head_short "$OUT/run_meta.txt" 2>/dev/null || echo "no run_meta (up not run)"
}

# ----------------------------------------------------------------------------------------------- ulog helpers
ulog_header_params() {   # $1 = ulog path inside $I; PX4 params from its header -> $OUT/params_ulog.txt (authoritative)
  local u=$1
  note "docker exec $I python3 -c \"from pyulog import ULog; p=ULog('$u', message_name_filter_list=['vehicle_local_position']).initial_parameters; ...\"  # -> params_ulog.txt"
  docker exec "$I" python3 -c "
from pyulog import ULog; p=ULog('$u', message_name_filter_list=['vehicle_local_position']).initial_parameters
for k in '$PARAM_KEYS'.split(): print(k, p.get(k))" | tee "$OUT/params_ulog.txt" | tee -a "$OUT/run.log" || say "WARN: ulog header read failed"
}

px4_arm_times_of() {   # $1 = ulog path in $I, $2 = MAV_SYS_ID, $3 = who -> $OUT/px4_arm_times.txt (vehicle time)
  local USE=$1 SID=$2 WHO=$3
    nx docker cp "$TOOLS/hover_step_timescale.py" "$I:/tmp/"
    note "docker exec $I python3 /tmp/hover_step_timescale.py $USE  # -> px4_arm_times.txt"
    local line; line=$(docker exec "$I" python3 /tmp/hover_step_timescale.py "$USE" 2>>"$OUT/run.log"); local rc=$?
    if [ "$rc" = 0 ] && [ -n "$line" ]; then
      { echo "# PX4 arm/disarm times of $WHO, MAV_SYS_ID $SID, ulog $USE (vehicle time, s since PX4 boot)"; echo "$line"; } > "$OUT/px4_arm_times.txt"
      tee -a "$OUT/run.log" < "$OUT/px4_arm_times.txt"
      [ "$SID" = 2 ] || caveat "px4_arm_times.txt comes from $WHO's ulog, not drone_1's"
    else rm -f "$OUT/px4_arm_times.txt"; say "WARN: no PX4 arm times (hover_step_timescale.py rc=$rc) — time-scale gate will be UNVERIFIED"; fi
}

no_flight_established() {   # 0 ONLY when positively no flight: a non-empty topic list (no daemon) without drone_1's MAVROS state topic. Present, empty list, error or timeout = assume flying
  local l; l=$(rx 'timeout 25 ros2 topic list --no-daemon --spin-time 5')
  [ -n "$l" ] || return 1
  ! echo "$l" | grep -q '^/drone_1/interface/mavros/state$'
}

land_all_and_wait() {   # $1 = bound (s), real: land via the commander, poll MAVROS armed (drones 1-3); 0 = all false, 1 = bound hit (overshoot <= one 10 s read)
  local bound=$1 deadline=$((SECONDS + $1)) N all
  note "docker exec $R bash -ic 'ros2 service call /swarm_commander/land std_srvs/srv/Trigger'"
  rx 'timeout 4 ros2 service call /swarm_commander/land std_srvs/srv/Trigger' | tail -1 | tee -a "$OUT/run.log"
  while :; do all=1
    for N in 1 2 3; do
      [ "$SECONDS" -ge "$deadline" ] && return 1
      rx "timeout 10 ros2 topic echo --once /drone_$N/interface/mavros/state" | grep -qE '^armed: false' || all=0; done
    [ "$all" = 1 ] && return 0
    [ "$SECONDS" -ge "$deadline" ] && return 1
    sleep 1; done
}

abort_trap() {   # Ctrl-C: land everything, then stop the stack and report; exit 3 either way
  trap '' INT; ALL_MODE=0
  say "ABORT: Ctrl-C — landing"
  local landed=0 flew=1
  if ! no_flight_established; then land_all_and_wait 30 && landed=1      # fail safe: in doubt, land
  else flew=0; landed=1; say "ABORTED: aborted before flight (MAVROS state topic has no publisher) — stopping the stack"; fi
  [ -n "${ABORT_HOOK:-}" ] && declare -F "$ABORT_HOOK" >/dev/null && "$ABORT_HOOK"
  { echo "aborted=$(date -Is)"; [ "$flew" = 0 ] && echo "aborted before flight"; } > "$OUT/aborted.txt"
  if [ "$landed" = 1 ]; then
    trap '' INT; copy_ulogs; down
    [ -n "${REPORT_HOOK:-}" ] && declare -F "$REPORT_HOOK" >/dev/null && "$REPORT_HOOK"
    exit 3
  fi
  say "DRONES STILL ARMED — stack left up; land by hand: docker exec $R bash -ic 'ros2 service call /swarm_commander/land std_srvs/srv/Trigger', then tools/sim.sh down"
  exit 3
}
arm_abort_trap() { trap abort_trap INT; }
