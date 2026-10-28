#!/usr/bin/env bash
# S5 / NEAR-786 — sim hover + 1 m step test (ledger #18 = re-run of #17 with fixed tooling), driven WITHOUT a
# terminal: every long-running process is started with `docker exec -d … bash -ic` and writes its log inside its
# container (/tmp/hover_step), readiness is polled with ros2, and everything is copied out at the end. SIM ONLY
# (CLAUDE.md iron rule 9: nothing measured here is ported to the drone).
#
#   tools/sim_hover_step_run.sh <phase> [run_name]        run_name default: sim_hover_step_run1
#   phases (in `all` order): precheck up watch isaac interfaces commander params fly collect down analyse report
#   extra:  all (the twelve above, stops at the first FAIL, containers left up)   status   ifgates (odometry gates only)
#
# Artefacts: docs/record/<run>/ (small text files, tracked; run.log = what happened, commands.sh = the commands used,
# run_meta.txt = which commit ran) and ~/flight_logs/sim/<run>/ (rosbag + PX4 ulogs, never the repo).
# The record itself (docs/record/<run>_record.md) is written by tools/hover_step_report.py in the `report` phase.
# The flight tool (tools/sim_hover_step_test.sh) and the echo analyser (tools/analyze_step.py) are OURS and are
# docker-cp'd into the robot container unchanged — nothing in CMU's AirStack/ tree is edited or patched.
# Re-running a phase truncates that phase's own output files and marks run.log/commands.sh "(re-run)";
# run.log, commands.sh, verdicts.log and caveats.txt are only ever appended to.
# Clocks: this script logs in the laptop's zone (SGT, labelled); container output (test_stdout.log, *.log) is UTC.
set -o pipefail            # no -e: every failure that matters is an explicit `|| fail`
PHASE=${1:-all}; RUN=${2:-sim_hover_step_run1}
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
R=airstack-robot-desktop-1; I=isaac-sim; S=/tmp/hover_step
OUT=$REPO/docs/record/$RUN; HEAVY=$HOME/flight_logs/sim/$RUN
TOOLS=$REPO/tools
STEPS_PER_AXIS=${STEPS_PER_AXIS:-3}          # alternating +1/-1 m steps per axis (tools/sim_hover_step_test.sh)
LEDGER=${LEDGER:-}                            # number of the NEW MILESTONES §3c row (passed to hover_step_report.py --ledger); empty = ? placeholder
ISAAC_KIT_ARGS=${ISAAC_KIT_ARGS:-}           # opt-in extra Kit args appended to the Isaac launch (default none)
NOISE='^(bash: cannot set terminal|bash: no job control|Sourcing|groups: cannot find name)'
BAGS=/root/AirStack/robot/ros_ws/bags        # inside $R; host path AirStack/robot/ros_ws/bags (gitignored)

ISAAC_CMD='PYTHONUNBUFFERED=1 DRONE_USD=/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd PX4_VEHICLE_MODEL=pegasus_starling2max NUM_ROBOTS=3 SVG_DOMAIN_ID=1 PLAY_SIM_ON_START=true ISAAC_SIM_HEADLESS=true PYTHONPATH="$ISAAC_SIM_PYTHONPATH" /isaac-sim/python.sh /isaac-sim/AirStack/simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py --ext-folder ~/.local/share/ov/data/documents/Kit/shared/exts'"${ISAAC_KIT_ARGS:+ $ISAAC_KIT_ARGS}"
IF_CMD='cd ~/AirStack/robot/ros_ws && ./src/svg_ground_control/scripts/launch_sim_interfaces.sh 3'
CMD_CMD='cd ~/AirStack/robot/ros_ws && ros2 launch svg_ground_control ground_control.launch.py config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/cbf_sim.yaml scenario:=goal record_bag:=true bag_prefix:=hover_step'
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
  if alive "$R" swarm_commander && [ "$(count_log "$R" 'SwarmCommander up | scenario=goal' "$S/commander.log")" -ge 1 ]; then say "commander already up (scenario goal); not relaunching"
  else docker exec "$R" bash -c ": > $S/commander.log"; note "docker exec -d $R bash -ic '$CMD_CMD > $S/commander.log 2>&1'"; docker exec -d "$R" bash -ic "$CMD_CMD > $S/commander.log 2>&1"; fi   # stale log -> stale count
  NEED=1 wait_for 60 2 "SwarmCommander up" count_log "$R" 'SwarmCommander up | scenario=goal' "$S/commander.log" || fail "commander not up with scenario=goal"
  docker exec "$R" grep -E 'REFUSED|took over|Traceback' "$S/commander.log" && fail "commander refused/crashed (see commander.log)" || true
  note "docker exec $R bash -ic 'timeout 15 ros2 topic echo --once /svg/commander_status --field data'  # -> status_pre.json"
  json1 /svg/commander_status > "$OUT/status_pre.json" || fail "no commander_status JSON"
  python3 - "$OUT/status_pre.json" <<'PY' | tee -a "$OUT/run.log" || fail "commander_status is not scenario=goal with 3 IDLE, odom-fresh drones (see status_pre.json)"
import json, sys
j = json.load(open(sys.argv[1])); st = [d["state"] for d in j["drones"]]; fr = [d.get("odom_fresh") for d in j["drones"]]
print("scenario", j["scenario"], "states", st, "fresh", fr, "tuning", j.get("tuning"))
sys.exit(0 if j["scenario"] == "goal" and st == ["IDLE"] * 3 and all(fr) else 1)
PY
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

fly() {
  phase_begin fly test_stdout.log armed_post.txt landing_evidence.txt status_post.json
  alive "$R" swarm_commander || fail "commander is not running (run the commander phase first)"
  nx docker cp "$TOOLS/sim_hover_step_test.sh" "$R:/tmp/"
  nx docker cp "$TOOLS/analyze_step.py" "$R:/tmp/"
  nx docker exec "$R" bash -c 'rm -f /tmp/ascent.txt /tmp/step_x_*.txt /tmp/step_z_*.txt /tmp/drone_1_*.csv'   # no stale traces from an earlier flight
  note "timeout 720 docker exec $R bash -ic 'STEPS_PER_AXIS=$STEPS_PER_AXIS /tmp/sim_hover_step_test.sh drone_1'  # -> test_stdout.log (container clock, UTC)"
  say "fly: takeoff -> start -> hover thrust -> $STEPS_PER_AXIS alternating +/-1 m steps in x, then in z -> land (about 3-5 min)"
  timeout 720 docker exec "$R" bash -ic "STEPS_PER_AXIS=$STEPS_PER_AXIS /tmp/sim_hover_step_test.sh drone_1" 2>&1 | grep -v -E "$NOISE" | tee "$OUT/test_stdout.log" || true
  grep -q 'landed:' "$OUT/test_stdout.log" || fail "test tool did not reach 'landed' (see test_stdout.log)"
  sleep 20
  note "for N in 1 2 3: docker exec $R bash -ic 'timeout 10 ros2 topic echo --once /drone_\$N/interface/mavros/state' | grep -oE '^armed: (true|false)'  # -> armed_post.txt"
  for N in 1 2 3; do rx "timeout 10 ros2 topic echo --once /drone_$N/interface/mavros/state" | grep -oE '^armed: (true|false)' | sed "s/^/drone_$N /"; done > "$OUT/armed_post.txt"
  tee -a "$OUT/run.log" < "$OUT/armed_post.txt"
  [ "$(wc -l < "$OUT/armed_post.txt")" = 3 ] || say "WARN: armed_post.txt does not hold three lines (report will mark the armed gate UNVERIFIED)"
  grep -q 'armed: true' "$OUT/armed_post.txt" && say "!! a drone still reports armed: true 20 s after landing" || true
  note "docker exec $R grep -E 'touchdown at z=|landed, disarmed|disarm not accepted' $S/commander.log  # -> landing_evidence.txt"
  docker exec "$R" grep -E 'touchdown at z=|landed, disarmed|disarm not accepted' "$S/commander.log" | tee "$OUT/landing_evidence.txt" | tee -a "$OUT/run.log" || true
  json1 /svg/commander_status > "$OUT/status_post.json" || say "WARN: no commander_status after the flight"
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

collect() {   # echo-trace analysis (#3's method), ulogs, PX4 params from the ulog header, PX4 arm/disarm times
  phase_begin collect analyze.txt ulog_list.txt ulog_sysid_map.txt params_ulog.txt px4_arm_times.txt
  local HZ k d t f ax; HZ=$(sed -n 's/.*average rate: \([0-9.]*\).*/\1/p' "$OUT/odom_hz.txt" 2>/dev/null | head -1); HZ=${HZ:-40}
  local traces="ascent:z:1.2"
  for k in $(seq 1 "$STEPS_PER_AXIS"); do d=$([ $((k % 2)) -eq 1 ] && echo 1.0 || echo -1.0); traces="$traces step_x_$k:x:$d step_z_$k:z:$d"; done
  note "docker exec $R python3 /tmp/analyze_step.py /tmp/<trace>.txt <axis> <delta> [hz]  (traces: $traces)  # -> analyze.txt"
  for t in $traces; do IFS=: read -r f ax d <<<"$t"
    docker exec "$R" python3 /tmp/analyze_step.py "/tmp/$f.txt" "$ax" "$d" 40    2>&1 | sed 's/^/hz=40 /'   >> "$OUT/analyze.txt" || true
    docker exec "$R" python3 /tmp/analyze_step.py "/tmp/$f.txt" "$ax" "$d" "$HZ" 2>&1 | sed "s/^/hz=$HZ /" >> "$OUT/analyze.txt" || true
    docker cp "$R:/tmp/$f.txt" "$OUT/$f.txt" 2>/dev/null || say "WARN: no trace /tmp/$f.txt in the robot container"
    echo "$f samples: $(grep -c "^$ax:" "$OUT/$f.txt" 2>/dev/null)" >> "$OUT/analyze.txt"; done
  tee -a "$OUT/run.log" < "$OUT/analyze.txt"
  copy_ulogs
  local U1 USE SID="2" WHO="drone_1"; U1=$(awk '$1==2{print $2}' "$OUT/ulog_sysid_map.txt" | tail -1)
  if [ -n "$U1" ]; then
    note "docker exec $I python3 -c \"from pyulog import ULog; p=ULog('$U1', message_name_filter_list=['vehicle_local_position']).initial_parameters; ...\"  # -> params_ulog.txt"
    docker exec "$I" python3 -c "
from pyulog import ULog; p=ULog('$U1', message_name_filter_list=['vehicle_local_position']).initial_parameters
for k in '$PARAM_KEYS'.split(): print(k, p.get(k))" | tee "$OUT/params_ulog.txt" | tee -a "$OUT/run.log" || say "WARN: ulog header read failed"
    USE=$U1
  else
    say "WARN: no sysid-2 (drone_1) ulog found for this session — params_ulog.txt stays empty (report: UNVERIFIED)"
    read -r SID USE _ < <(tail -1 "$OUT/ulog_sysid_map.txt"); [ -n "$USE" ] && WHO="drone_$((SID-1)) (FALLBACK: no drone_1 ulog)"
  fi
  if [ -n "$USE" ]; then
    nx docker cp "$TOOLS/hover_step_timescale.py" "$I:/tmp/"
    note "docker exec $I python3 /tmp/hover_step_timescale.py $USE  # -> px4_arm_times.txt"
    local line; line=$(docker exec "$I" python3 /tmp/hover_step_timescale.py "$USE" 2>>"$OUT/run.log"); local rc=$?
    if [ "$rc" = 0 ] && [ -n "$line" ]; then
      { echo "# PX4 arm/disarm times of $WHO, MAV_SYS_ID $SID, ulog $USE (vehicle time, s since PX4 boot)"; echo "$line"; } > "$OUT/px4_arm_times.txt"
      tee -a "$OUT/run.log" < "$OUT/px4_arm_times.txt"
      [ "$SID" = 2 ] || caveat "px4_arm_times.txt comes from $WHO's ulog, not drone_1's"
    else rm -f "$OUT/px4_arm_times.txt"; say "WARN: no PX4 arm times (hover_step_timescale.py rc=$rc) — time-scale gate will be UNVERIFIED"; fi
  else rm -f "$OUT/px4_arm_times.txt"; say "WARN: no PX4 arm times (no ulog at all) — time-scale gate will be UNVERIFIED"; fi
  ls -l "$HEAVY" | tee -a "$OUT/run.log"
}

down() {   # commander -> bag out -> interfaces -> ulogs (if not yet) -> Isaac -> orphans -> watch; containers stay up (no airstack.sh down)
  phase_begin down bag_evidence.txt bag_path.txt
  local i b
  nx docker exec "$R" pkill -INT -f ground_control.launch.py || true
  for i in $(seq 1 25); do alive "$R" ground_control.launch.py || break; sleep 1; done
  alive "$R" ground_control.launch.py && say "WARN: commander still alive 25 s after SIGINT" || true
  docker exec "$R" grep -E 'stopped: .*hover_step_|recorder exited|record_on_start' "$S/commander.log" | tee "$OUT/bag_evidence.txt" | tee -a "$OUT/run.log" || true
  # the rosbag: written root-owned under the repo (AirStack/robot/ros_ws/bags, gitignored) -> heavy dir, CSVs out, then (and only then) removed
  note "docker exec $R bash -c 'ls -d $BAGS/hover_step_* | tail -1'; docker cp $R:<bag> $HEAVY/"
  b=$(docker exec "$R" bash -c "ls -d $BAGS/hover_step_* 2>/dev/null | tail -1")
  [ -n "$b" ] && echo "$b" > "$OUT/bag_path.txt"
  local bagfail=0
  if [ -z "$b" ]; then caveat "no hover_step bag found in the robot container ($BAGS)"
  elif docker cp "$R:$b" "$HEAVY/" && [ -f "$HEAVY/$(basename "$b")/metadata.yaml" ]; then
    say "bag copied to $HEAVY/$(basename "$b")"
    nx docker cp "$TOOLS/hover_step_bag.py" "$R:/tmp/"
    note "docker exec $R bash -ic 'python3 /tmp/hover_step_bag.py $b drone_1 /tmp/drone_1'; docker cp $R:/tmp/drone_1_{odom,cmd,state}.csv $OUT/"
    rx "python3 /tmp/hover_step_bag.py $b drone_1 /tmp/drone_1" | grep '^{' | tee -a "$OUT/run.log" || { bagfail=1; caveat "bag reader failed; bag left in the container at $b"; }
    for f in odom cmd state; do [ "$bagfail" = 1 ] || docker cp "$R:/tmp/drone_1_$f.csv" "$OUT/drone_1_$f.csv" || { bagfail=1; caveat "csv copy $f failed; bag left in the container at $b"; }; done
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

analyse() {   # host side: bag CSVs (+ PX4 arm times) -> bag_analysis.json -> step_response.png
  phase_begin analyse bag_analysis.json
  for f in odom cmd state; do [ -s "$OUT/drone_1_$f.csv" ] || fail "missing $OUT/drone_1_$f.csv (run the down phase first)"; done
  [ -f "$OUT/px4_arm_times.txt" ] || say "WARN: no px4_arm_times.txt — analysis assumes time scale 1.0 (report: time-scale gate UNVERIFIED)"
  nx python3 "$TOOLS/hover_step_analysis.py" --odom "$OUT/drone_1_odom.csv" --cmd "$OUT/drone_1_cmd.csv" --state "$OUT/drone_1_state.csv" \
     --px4-arm-times "$OUT/px4_arm_times.txt" --step-delta 1.0 --drone drone_1 -o "$OUT/bag_analysis.json" 2>&1 | tee -a "$OUT/run.log"
  [ "${PIPESTATUS[0]}" = 0 ] && [ -s "$OUT/bag_analysis.json" ] || fail "analysis (tools/hover_step_analysis.py)"
  nx python3 "$TOOLS/hover_step_plot.py" "$OUT" 2>&1 | tee -a "$OUT/run.log"; [ "${PIPESTATUS[0]}" = 0 ] || say "WARN: plot failed"
  python3 -c "
import json, sys; j = json.load(open(sys.argv[1]))
print('time_scale', j.get('time_scale'), '(' + str(j.get('time_scale_source')) + ')  events', len(j.get('events', [])))
for ax, s in sorted((j.get('steps') or {}).items()): print(' ', ax, json.dumps(s, sort_keys=True))" "$OUT/bag_analysis.json" | tee -a "$OUT/run.log" || true
}

REPORT_RC=0
report() {   # the record; exit 0 PASS / 2 INCOMPLETE (both let `all` finish) / 1 FAIL / other = crash
  phase_begin report
  note "python3 $TOOLS/hover_step_report.py $OUT --heavy $HEAVY${LEDGER:+ --ledger $LEDGER}"
  python3 "$TOOLS/hover_step_report.py" "$OUT" --heavy "$HEAVY" ${LEDGER:+--ledger "$LEDGER"} 2>&1 | tee -a "$OUT/run.log"; REPORT_RC=${PIPESTATUS[0]}
  case "$REPORT_RC" in
    0) say "report: PASS" ;;
    2) say "report: INCOMPLETE (>= 1 gate UNVERIFIED — see the record)" ;;
    1) fail "report: FAIL (see the record and verdicts.log)" ;;
    *) fail "report crashed (rc=$REPORT_RC)" ;;
  esac
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

ALL="precheck up watch isaac interfaces commander params fly collect down analyse report"
case "$PHASE" in
  precheck|up|watch|isaac|interfaces|ifgates|commander|params|fly|collect|down|analyse|report|all|status) ;;
  *) echo "usage: $0 precheck|up|watch|isaac|interfaces|commander|params|fly|collect|down|analyse|report | all | status | ifgates  [run_name]"
     echo "  all = the twelve phases in that order (stops at the first FAIL, containers left up); run_name default sim_hover_step_run1"
     echo "  env: STEPS_PER_AXIS (default 3), ISAAC_KIT_ARGS (extra Isaac Kit args, default none)"; exit 2 ;;
esac
[ "$PHASE" = status ] || mkdir -p "$OUT" "$HEAVY"
case "$PHASE" in
  all) ALL_MODE=1; for p in $ALL; do PHASE=$p; [ "$p" = isaac ] && STACK_UP=1; "$p"; [ "$p" = down ] && STACK_UP=0; done; say "all: done (report rc=$REPORT_RC)"; exit "$REPORT_RC" ;;
  *) "$PHASE" ;;
esac
