#!/usr/bin/env bash
# S5 / NEAR-786 — re-run of ledger #3 (Starling hover + 1 m steps) driven WITHOUT a terminal: every long-running
# process is started with `docker exec -d … bash -ic` and writes its log inside its container (/tmp/hover_step),
# readiness is polled with grep/ros2, and everything is copied out at the end. SIM ONLY (iron rule 9).
#
#   tools/sim_hover_step_run.sh <phase> [run_name]        run_name default: sim_hover_step_run1
#   phases: precheck up watch isaac interfaces commander params fly collect down report | all | status
#
# Artefacts: docs/record/<run>/ (small text files, tracked) and ~/flight_logs/sim/<run>/ (ulogs + bag, never the
# repo). The record itself: docs/record/<run>_record.md, written by tools/hover_step_report.py.
# `all` stops at the first failing phase and leaves the containers UP for inspection; it never runs airstack.sh down.
# The flight tool and analyser come from AirStack/simulation/isaac-sim/tools (CMU's tree, copied, never edited);
# the copy's wait_s() is patched to a real sleep because /clock is not visible in the robot container.
set -eo pipefail
PHASE=${1:-all}; RUN=${2:-sim_hover_step_run1}
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
R=airstack-robot-desktop-1; I=isaac-sim; S=/tmp/hover_step
OUT=$REPO/docs/record/$RUN; HEAVY=$HOME/flight_logs/sim/$RUN
TOOLS=$REPO/AirStack/simulation/isaac-sim/tools
mkdir -p "$OUT" "$HEAVY"

ISAAC_CMD='PYTHONUNBUFFERED=1 DRONE_USD=/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd PX4_VEHICLE_MODEL=pegasus_starling2max NUM_ROBOTS=3 SVG_DOMAIN_ID=1 PLAY_SIM_ON_START=true ISAAC_SIM_HEADLESS=true PYTHONPATH="$ISAAC_SIM_PYTHONPATH" /isaac-sim/python.sh /isaac-sim/AirStack/simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py --ext-folder ~/.local/share/ov/data/documents/Kit/shared/exts'
IF_CMD='cd ~/AirStack/robot/ros_ws && ./src/svg_ground_control/scripts/launch_sim_interfaces.sh 3'
CMD_CMD='cd ~/AirStack/robot/ros_ws && ros2 launch svg_ground_control ground_control.launch.py config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/cbf_sim.yaml scenario:=goal record_bag:=true bag_prefix:=hover_step'

say()  { echo "[$(date +%T)] $*" | tee -a "$OUT/run.log"; }
note() { echo "$*" >> "$OUT/commands.sh"; }           # the exact commands used, for the record
fail() { say "FAIL ($PHASE): $*"; exit 1; }
rx()   { docker exec "$R" bash -ic "$*" 2>&1 | grep -v -E '^(bash: cannot set terminal|bash: no job control|Sourcing)' || true; }
ix()   { docker exec "$I" bash -ic "$*" 2>&1 | grep -v -E '^(bash: cannot set terminal|bash: no job control|Sourcing)' || true; }
# wait_for <timeout s> <interval s> <description> <command…>: succeed when the command's stdout is a number >= $NEED
wait_for() { local t=$1 iv=$2 d=$3; shift 3; local el=0 n=0
  while :; do n=$("$@" 2>/dev/null | tail -1 | tr -dc '0-9'); n=${n:-0}
    [ "$n" -ge "${NEED:-1}" ] && { say "$d: $n (after ${el}s)"; return 0; }
    [ "$el" -ge "$t" ] && { say "$d: $n after ${el}s (timeout)"; return 1; }
    sleep "$iv"; el=$((el+iv)); done; }
json1() { local i; for i in 1 2 3 4 5 6; do rx "timeout 15 ros2 topic echo --once $1 --field data" | grep -m1 '^{' && return 0; sleep 3; done; return 1; }   # first JSON line, retried
count_log() { local n; n=$(docker exec "$1" grep -c "$2" "$3" 2>/dev/null | tail -1); echo "${n:-0}"; }   # grep -c prints 0 on no match

precheck() {
  say "precheck: no real-drone bridge on the laptop, port 8765 free, drone battery out (sim shares domain 1)"
  pgrep -af 'mocap\.sh|MicroXRCEAgent|natnet' && fail "a real-drone/mocap bridge is running on the laptop" || true
  ss -ltnp 2>/dev/null | grep -q ':8765 ' && fail "port 8765 already in use (stray foxglove_bridge)" || true
  nvidia-smi --query-gpu=name,memory.used --format=csv,noheader | tee -a "$OUT/run.log"
}

up() {
  note "cd $REPO/AirStack && ./airstack.sh up"
  (cd "$REPO/AirStack" && timeout 180 ./airstack.sh up) 2>&1 | tail -5 | tee -a "$OUT/run.log"
  for c in $I $R; do docker ps --format '{{.Names}} {{.Status}}' | grep -q "^$c Up" || fail "$c is not Up"; done
  docker exec "$I" mkdir -p "$S"; docker exec "$R" mkdir -p "$S"
  # the one command that settles the shared-domain guard: no real-drone or mocap topics on domain 1
  local t; t=$(rx 'ros2 daemon stop >/dev/null 2>&1; ros2 topic list --no-daemon --spin-time 5' | grep -E '/fmu/|/poses|/pose$' || true)
  [ -z "$t" ] || fail "real-drone/mocap topics on domain 1: $t"
  say "up: containers running, domain 1 clean"
}

watch() {
  note "nohup $REPO/localisation/scripts/sim_resources_watch.sh $OUT/res_watch.log &"
  nohup "$REPO/localisation/scripts/sim_resources_watch.sh" "$OUT/res_watch.log" >/dev/null 2>&1 &
  echo $! > "$OUT/.watch_pid"; sleep 3
  [ "$(wc -l < "$OUT/res_watch.log")" -ge 2 ] && say "watch: running (pid $(cat "$OUT/.watch_pid"))" || say "WARN: res_watch not writing"
}

isaac() {
  note "docker exec -d $I bash -ic '$ISAAC_CMD > $S/isaac.log 2>&1'"
  date +%s > "$OUT/isaac.log.start"
  docker exec -d "$I" bash -ic "$ISAAC_CMD > $S/isaac.log 2>&1"
  NEED=3 wait_for 600 5 "Ready for takeoff" count_log "$I" 'Ready for takeoff' "$S/isaac.log" || fail "Isaac not ready"
  docker exec "$I" bash -c "L=$S/isaac.log; echo model_line=\$(grep -c 'PX4 model: pegasus_starling2max' \$L) starling_cfg=\$(grep -c Starling2MaxConfig \$L) autostart=\$(grep -c 'SYS_AUTOSTART=10090' \$L) unknown_model=\$(grep -c 'Unknown model' \$L) cooking=\$(grep -ciE 'cook.*(warn|error)|(warn|error).*cook' \$L) ready=\$(grep -c 'Ready for takeoff' \$L)" | tee "$OUT/isaac_evidence.txt" | tee -a "$OUT/run.log"
  grep -q 'unknown_model=0' "$OUT/isaac_evidence.txt" || fail "PX4 reported Unknown model (airframe mount missing?)"
  grep -q WIFI-ALERT "$OUT/res_watch.log" 2>/dev/null && say "!! WIFI-ALERT in res_watch.log — tell the user; the sim is still running" || true
}

interfaces() {
  note "docker exec -d $R bash -ic '$IF_CMD > $S/interfaces.log 2>&1'"
  docker exec -d "$R" bash -ic "$IF_CMD > $S/interfaces.log 2>&1"
  NEED=3 wait_for 90 2 "MAVROS heartbeats" count_log "$R" 'CON: Got HEARTBEAT, connected' "$S/interfaces.log" || fail "MAVROS not connected x3"
  [ "$(count_log "$R" 'exit code -11' "$S/interfaces.log")" = 0 ] || say "WARN: mavros segfault(s) in interfaces.log"
  ifgates
  rx 'timeout 15 ros2 topic hz /drone_1/odometry_conversion/odometry -w 200' | grep 'average rate' | tail -1 | tee "$OUT/odom_hz.txt" | tee -a "$OUT/run.log"
  rx 'ros2 topic list' | grep -E 'target_attitude|/clock$' | tee "$OUT/topics_of_interest.txt" | tee -a "$OUT/run.log" || true
}

ifgates() {   # odometry from every drone (PX4's local position needs a few seconds after connect), rate, topics
  local N ok
  for N in 1 2 3; do ok=0
    for i in $(seq 1 18); do rx "timeout 10 ros2 topic echo --once /drone_$N/odometry_conversion/odometry --field pose.pose.position" | grep -q '^x:' && { ok=1; break; }; sleep 3; done
    [ "$ok" = 1 ] || fail "no odometry for drone_$N after 90 s"; done
  rx 'timeout 15 ros2 topic hz /drone_1/odometry_conversion/odometry -w 200' | grep 'average rate' | tail -1 | tee "$OUT/odom_hz.txt" | tee -a "$OUT/run.log"
  rx 'ros2 topic list' | grep -E 'target_attitude|/clock$' | tee "$OUT/topics_of_interest.txt" | tee -a "$OUT/run.log" || true
  say "interfaces: 3 drones with odometry"
}

commander() {
  if docker exec "$R" pgrep -f swarm_commander >/dev/null 2>&1 && [ "$(count_log "$R" 'SwarmCommander up | scenario=goal' "$S/commander.log")" -ge 1 ]; then say "commander already up (scenario goal); not relaunching"
  else note "docker exec -d $R bash -ic '$CMD_CMD > $S/commander.log 2>&1'"; docker exec -d "$R" bash -ic "$CMD_CMD > $S/commander.log 2>&1"; fi
  NEED=1 wait_for 60 2 "SwarmCommander up" count_log "$R" 'SwarmCommander up | scenario=goal' "$S/commander.log" || fail "commander not up with scenario=goal"
  docker exec "$R" grep -E 'REFUSED|took over|Traceback' "$S/commander.log" && fail "commander refused/crashed (see commander.log)" || true
  json1 /svg/commander_status > "$OUT/status_pre.json" || fail "no commander_status JSON"
  python3 - "$OUT/status_pre.json" <<'PY' | tee -a "$OUT/run.log"
import json, sys
j = json.load(open(sys.argv[1])); st = [d["state"] for d in j["drones"]]; fr = [d.get("odom_fresh") for d in j["drones"]]
print("scenario", j["scenario"], "states", st, "fresh", fr, "tuning", j.get("tuning"))
sys.exit(0 if j["scenario"] == "goal" and st == ["IDLE"] * 3 and all(fr) else 1)
PY
  json1 /svg/bag_recorder/status | tee "$OUT/bag_status_pre.json" | tee -a "$OUT/run.log" || true
}

params() {   # secondary, read-only proof via MAVROS (names verified live); the ulog header in `collect` is authoritative
  rx 'ros2 service list | grep -E "/drone_1/interface/mavros/param"; ros2 node list | grep -E "/drone_1/interface/mavros"' | tee "$OUT/params_mavros_names.txt" >/dev/null
  if grep -q 'param/pull' "$OUT/params_mavros_names.txt"; then
    rx 'timeout 60 ros2 service call /drone_1/interface/mavros/param/pull mavros_msgs/srv/ParamPull "{force_pull: false}"' | tail -1 | tee -a "$OUT/run.log"
    local pnode; pnode=$(grep -m1 -E '^/drone_1/interface/mavros/param$|^/drone_1/interface/mavros$' "$OUT/params_mavros_names.txt" || true)
    : > "$OUT/params_mavros.txt"
    for p in SYS_AUTOSTART MC_PITCHRATE_P MC_ROLLRATE_P LNDMC_ROT_MAX MPC_XY_VEL_MAX MPC_THR_HOVER IMU_GYRO_CUTOFF IMU_DGYRO_CUTOFF MPC_Z_VEL_MAX_DN MPC_ACC_HOR; do
      [ -n "$pnode" ] && rx "timeout 10 ros2 param get $pnode $p" | sed "s/^/$p: /" >> "$OUT/params_mavros.txt"; done
    cat "$OUT/params_mavros.txt" | tee -a "$OUT/run.log"
    grep -q 'MC_PITCHRATE_P: .*0\.032' "$OUT/params_mavros.txt" && grep -q 'LNDMC_ROT_MAX: .*300' "$OUT/params_mavros.txt" \
      && say "params: 10-20 airframe confirmed via MAVROS" || say "params: MAVROS read inconclusive — ulog header will decide"
  else say "params: no MAVROS param service — ulog header will decide"; fi
}

fly() {
  note "docker cp $TOOLS/{sim_hover_step_test.sh,analyze_step.py} $R:/tmp/  (wait_s patched to sleep in the copy)"
  docker cp "$TOOLS/sim_hover_step_test.sh" "$R:/tmp/"; docker cp "$TOOLS/analyze_step.py" "$R:/tmp/"
  if rx 'timeout 4 ros2 topic echo --once /clock >/dev/null 2>&1; echo rc=$?' | grep -q 'rc=124'; then say "/clock is visible; wait_s left as is"
  else docker exec "$R" sed -i 's|^wait_s(){.*|wait_s(){ sleep "$1"; }   # patched by sim_hover_step_run.sh: /clock not visible on this domain|' /tmp/sim_hover_step_test.sh
       echo "wait_s() in the copied test tool patched to a real sleep: /clock is not visible in the robot container, so the original (ros2 topic echo /clock under timeout) returned instantly" >> "$OUT/caveats.txt"; say "wait_s patched to sleep"; fi
  note "docker exec $R bash -ic '/tmp/sim_hover_step_test.sh drone_1'"
  say "fly: takeoff -> start -> hover thrust -> +1 m x -> +1 m z -> land (about 3-4 min)"
  timeout 480 docker exec "$R" bash -ic '/tmp/sim_hover_step_test.sh drone_1' 2>&1 | grep -v -E '^(bash: cannot set terminal|bash: no job control|Sourcing)' | tee "$OUT/test_stdout.log" || true
  grep -q 'landed:' "$OUT/test_stdout.log" || fail "test tool did not reach 'landed' (see test_stdout.log)"
  sleep 20
  for N in 1 2 3; do rx "timeout 10 ros2 topic echo --once /drone_$N/interface/mavros/state --field armed" | grep -m1 -E '^(true|false)$' | sed "s/^/drone_$N armed: /"; done | tee "$OUT/armed_post.txt" | tee -a "$OUT/run.log" || true
  docker exec "$R" grep -E 'touchdown at z=|landed, disarmed|disarm not accepted' "$S/commander.log" | tee "$OUT/landing_evidence.txt" | tee -a "$OUT/run.log" || true
  json1 /svg/commander_status > "$OUT/status_post.json" || true
}

collect() {
  local HZ; HZ=$(sed -n 's/.*average rate: \([0-9.]*\).*/\1/p' "$OUT/odom_hz.txt" 2>/dev/null | head -1); HZ=${HZ:-40}
  : > "$OUT/analyze.txt"
  for t in ascent:z:1.2 step_x:x:1.0 step_z:z:1.0; do IFS=: read -r f ax d <<<"$t"
    docker exec "$R" python3 /tmp/analyze_step.py /tmp/$f.txt $ax $d 40    2>&1 | sed 's/^/hz=40 /'   >> "$OUT/analyze.txt" || true
    docker exec "$R" python3 /tmp/analyze_step.py /tmp/$f.txt $ax $d "$HZ" 2>&1 | sed "s/^/hz=$HZ /" >> "$OUT/analyze.txt" || true
    docker cp "$R:/tmp/$f.txt" "$OUT/$f.txt" 2>/dev/null || true
    echo "$f samples: $(grep -c "^$ax:" "$OUT/$f.txt" 2>/dev/null || echo 0)" >> "$OUT/analyze.txt"; done
  cat "$OUT/analyze.txt" | tee -a "$OUT/run.log"
  # PX4 ulogs: this session's files (newer than isaac.log.start), one per MAV_SYS_ID 2/3/4 = drone_1/2/3; copied BEFORE Isaac stops
  local START; START=$(cat "$OUT/isaac.log.start")
  docker exec "$I" bash -c "for f in /tmp/tmp*/log/*/*.ulg; do [ \$(stat -c %Y \"\$f\") -gt $START ] && echo \"\$f\"; done" > "$OUT/ulog_list.txt" || true
  : > "$OUT/ulog_sysid_map.txt"
  while read -r f; do [ -n "$f" ] || continue
    sid=$(docker exec "$I" python3 -c "from pyulog import ULog; print(ULog('$f', message_name_filter_list=['vehicle_local_position']).initial_parameters.get('MAV_SYS_ID'))" 2>/dev/null)
    echo "$sid $f $(docker exec "$I" stat -c %s "$f")" >> "$OUT/ulog_sysid_map.txt"; done < "$OUT/ulog_list.txt"
  sort -n -o "$OUT/ulog_sysid_map.txt" "$OUT/ulog_sysid_map.txt"; cat "$OUT/ulog_sysid_map.txt" | tee -a "$OUT/run.log"
  local U1; U1=$(awk '$1==2{print $2}' "$OUT/ulog_sysid_map.txt" | tail -1)
  if [ -n "$U1" ]; then
    docker exec "$I" python3 -c "
from pyulog import ULog; p=ULog('$U1', message_name_filter_list=['vehicle_local_position']).initial_parameters
for k in ['SYS_AUTOSTART','MAV_SYS_ID','MC_PITCHRATE_P','MC_ROLLRATE_P','LNDMC_ROT_MAX','MPC_XY_VEL_MAX','MPC_THR_HOVER','IMU_GYRO_CUTOFF','IMU_DGYRO_CUTOFF','MPC_Z_VEL_MAX_DN','MPC_ACC_HOR']: print(k, p.get(k))" | tee "$OUT/params_ulog.txt" | tee -a "$OUT/run.log"
    docker exec "$I" python3 -c "
from pyulog import ULog; import statistics as s
u=ULog('$U1', message_name_filter_list=['vehicle_thrust_setpoint']); d=u.get_dataset('vehicle_thrust_setpoint').data
z=[-v for v in d['xyz[2]']]; mid=z[len(z)//3:2*len(z)//3]; print('ulog thrust_setpoint median(mid-third)', round(s.median(mid),3))" 2>&1 | tee -a "$OUT/analyze.txt" | tee -a "$OUT/run.log" || true
  else say "WARN: no sysid-2 ulog found for this session"; fi
  while read -r sid f sz; do [ -n "$f" ] && docker cp "$I:$f" "$HEAVY/drone_$((sid-1))_sysid${sid}_$(basename "$f")"; done < "$OUT/ulog_sysid_map.txt" || true
  ls -l "$HEAVY" | tee -a "$OUT/run.log"
}

down() {   # commander -> interfaces -> copy logs -> Isaac -> watch; containers stay up (no airstack.sh down)
  note "docker exec $R pkill -INT -f ground_control.launch.py; … launch_sim_interfaces.sh; docker exec $I pkill -INT -f svg_multi_drone_single_domain.py"
  docker exec "$R" pkill -INT -f ground_control.launch.py || true
  for i in $(seq 1 25); do docker exec "$R" pgrep -f ground_control.launch.py >/dev/null || break; sleep 1; done
  docker exec "$R" grep -E 'stopped: .*hover_step_|recorder exited|record_on_start' "$S/commander.log" | tee "$OUT/bag_evidence.txt" | tee -a "$OUT/run.log" || true
  docker exec "$R" pkill -INT -f launch_sim_interfaces.sh || true
  for i in $(seq 1 25); do docker exec "$R" pgrep -x mavros_node >/dev/null || break; sleep 1; done
  docker exec "$R" pgrep -x mavros_node >/dev/null && docker exec "$R" pkill -TERM -f 'sim_drone_interface|mavros_node|robot_interface|odometry_conversion' || true
  for f in commander interfaces; do docker cp "$R:$S/$f.log" "$OUT/$f.log" 2>/dev/null || true; done
  docker exec "$I" pkill -INT -f svg_multi_drone_single_domain.py || true
  for i in $(seq 1 40); do docker exec "$I" pgrep -f svg_multi_drone_single_domain.py >/dev/null || break; sleep 1; done
  if docker exec "$I" pgrep -f svg_multi_drone_single_domain.py >/dev/null; then
    docker exec "$I" pkill -TERM -f svg_multi_drone_single_domain.py; sleep 10
    docker exec "$I" pkill -KILL -f svg_multi_drone_single_domain.py || true; say "WARN: Isaac needed TERM/KILL"; fi
  docker exec "$I" pkill -9 -x px4 2>/dev/null && say "orphaned PX4 SITL instances killed (Isaac's exit leaves them)" || true
  docker exec "$R" pkill -f position_setpoint_pub 2>/dev/null || true     # the interface launch leaves these behind
  docker cp "$I:$S/isaac.log" "$OUT/isaac.log" 2>/dev/null || true
  docker exec "$I" bash -c "L=$S/isaac.log; echo model_line=\$(grep -c 'PX4 model: pegasus_starling2max' \$L) starling_cfg=\$(grep -c Starling2MaxConfig \$L) autostart=\$(grep -c 'SYS_AUTOSTART=10090' \$L) unknown_model=\$(grep -c 'Unknown model' \$L) cooking=\$(grep -ciE 'cook.*(warn|error)|(warn|error).*cook' \$L) ready=\$(grep -c 'Ready for takeoff' \$L)" > "$OUT/isaac_evidence.txt" 2>/dev/null || true
  sleep 30; grep WIFI-ALERT "$OUT/res_watch.log" 2>/dev/null | tee -a "$OUT/run.log" || say "no WIFI-ALERT during the run"
  [ -f "$OUT/.watch_pid" ] && { kill "$(cat "$OUT/.watch_pid")" 2>/dev/null || true; rm -f "$OUT/.watch_pid"; }
  local b; b=$(docker exec "$R" bash -c 'ls -d /root/AirStack/robot/ros_ws/bags/hover_step_* 2>/dev/null | tail -1')
  if [ -n "$b" ]; then docker cp "$R:$b" "$HEAVY/" && say "bag copied to $HEAVY/$(basename "$b")"; echo "$b" > "$OUT/bag_path.txt"
    docker cp "$REPO/tools/hover_step_bag.py" "$R:/tmp/"; rx "python3 /tmp/hover_step_bag.py $b drone_1" | grep -v '^Sourcing' > "$OUT/bag_analysis.json" || true
    python3 -c "import json,sys; j=json.load(open('$OUT/bag_analysis.json')); print('bag:', j['odom_msgs'], 'odom msgs @', j['odom_rate_hz'], 'Hz; disarmed at', j['disarmed_at_s']); [print(' ', s) for s in j['steps']]; print('  takeoff', j.get('takeoff_climb'))" | tee -a "$OUT/run.log" || say "WARN: bag analysis failed"
    docker exec "$R" rm -rf "$b"
  else say "WARN: no hover_step bag found"; fi
  for f in "$OUT"/*.log; do [ "$(stat -c %s "$f")" -gt 1000000 ] && { gzip -c "$f" > "$HEAVY/$(basename "$f").gz"; echo "too big for the repo: moved to $HEAVY/$(basename "$f").gz" > "$f"; } ; done; true
  say "down: stack stopped, containers left up"
}

report() { python3 "$REPO/tools/hover_step_report.py" "$OUT" | tee -a "$OUT/run.log"; }

status() {
  docker ps --format '{{.Names}} {{.Status}}' | grep -E "$I|$R" || echo "containers down"
  echo "ready: $(count_log "$I" 'Ready for takeoff' "$S/isaac.log")  heartbeats: $(count_log "$R" 'CON: Got HEARTBEAT, connected' "$S/interfaces.log")  commander: $(count_log "$R" 'SwarmCommander up' "$S/commander.log")"
  rx 'timeout 8 ros2 topic echo --once /svg/commander_status --field data' | head -c 400; echo
  [ -f "$OUT/.watch_pid" ] && kill -0 "$(cat "$OUT/.watch_pid")" 2>/dev/null && echo "watch alive: $(tail -1 "$OUT/res_watch.log")" || echo "watch not running"
}

case "$PHASE" in
  precheck|up|watch|isaac|interfaces|ifgates|commander|params|fly|collect|down|report|status) "$PHASE" ;;
  all) for p in precheck up watch isaac interfaces commander params fly collect down report; do PHASE=$p; say "== phase $p =="; "$p"; done ;;
  *) echo "usage: $0 precheck|up|watch|isaac|interfaces|commander|params|fly|collect|down|report|all|status [run_name]"; exit 2 ;;
esac
