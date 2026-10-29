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
PHASE=${1:-}; RUN=${2:-sim_hover_step_run1}            # no phase = usage (never an accidental `all`)
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
S=/tmp/hover_step
OUT=$REPO/docs/record/$RUN; HEAVY=$HOME/flight_logs/sim/$RUN
STEPS_PER_AXIS=${STEPS_PER_AXIS:-3}          # alternating +1/-1 m steps per axis (tools/sim_hover_step_test.sh)
LEDGER=${LEDGER:-}   # number of the NEW docs/record/LEDGER.md table-1 row (hover_step_report.py --ledger); empty = ? placeholder
ISSUE=${ISSUE:-}    # Linear issue id for that row (hover_step_report.py --issue NEAR-nnn); empty = ? placeholder
ISAAC_KIT_ARGS=${ISAAC_KIT_ARGS:-}           # opt-in extra Kit args appended to the Isaac launch (default none)
ISAAC_GUI=${ISAAC_GUI:-0}                    # 1 = open the Isaac Sim window (ISAAC_SIM_HEADLESS=false) so the flight can be watched / recorded
PAUSE_BEFORE_FLY=${PAUSE_BEFORE_FLY:-0}      # 1 = wait for Enter before the fly phase (start OBS / the screen recorder first)
HEADLESS=true; [ "$ISAAC_GUI" = 1 ] && HEADLESS=false
SCENARIO=goal; BAG_PREFIX=hover_step; CONFIG=cbf_sim.yaml          # the shared stack phases live in tools/lib/stack.sh
# shellcheck source=lib/stack.sh
source "$REPO/tools/lib/stack.sh" || exit $?

bag_dump_hook() {   # called by `down` with the bag dir inside $R; non-zero = the bag stays in the container
  local b=$1 f bagfail=0
  nx docker cp "$TOOLS/hover_step_bag.py" "$R:/tmp/"
  note "docker exec $R bash -ic 'python3 /tmp/hover_step_bag.py $b drone_1 /tmp/drone_1'; docker cp $R:/tmp/drone_1_{odom,cmd,state}.csv $OUT/"
  rx "python3 /tmp/hover_step_bag.py $b drone_1 /tmp/drone_1" | grep '^{' | tee -a "$OUT/run.log" || { bagfail=1; caveat "bag reader failed; bag left in the container at $b"; }
  for f in odom cmd state; do [ "$bagfail" = 1 ] || docker cp "$R:/tmp/drone_1_$f.csv" "$OUT/drone_1_$f.csv" || { bagfail=1; caveat "csv copy $f failed; bag left in the container at $b"; }; done
  return "$bagfail"
}

fly() {
  phase_begin fly test_stdout.log armed_post.txt landing_evidence.txt status_post.json
  alive "$R" swarm_commander || fail "commander is not running (run the commander phase first)"
  nx docker cp "$TOOLS/sim_hover_step_test.sh" "$R:/tmp/"
  nx docker cp "$TOOLS/analyze_step.py" "$R:/tmp/"
  nx docker exec "$R" bash -c 'rm -f /tmp/ascent.txt /tmp/step_x_*.txt /tmp/step_z_*.txt /tmp/drone_1_*.csv'   # no stale traces from an earlier flight
  note "timeout 720 docker exec $R bash -ic 'STEPS_PER_AXIS=$STEPS_PER_AXIS /tmp/sim_hover_step_test.sh drone_1'  # -> test_stdout.log (container clock, UTC)"
  if [ "$PAUSE_BEFORE_FLY" = 1 ]; then
    say "PAUSE_BEFORE_FLY=1: the stack is up and the drones are on their pads. Start the screen recorder now, then press Enter to fly."
    read -r _ < /dev/tty || fail "no terminal to wait on (PAUSE_BEFORE_FLY needs an interactive run)"
  fi
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
    ulog_header_params "$U1"
    USE=$U1
  else
    say "WARN: no sysid-2 (drone_1) ulog found for this session — params_ulog.txt stays empty (report: UNVERIFIED)"
    read -r SID USE _ < <(tail -1 "$OUT/ulog_sysid_map.txt"); [ -n "$USE" ] && WHO="drone_$((SID-1)) (FALLBACK: no drone_1 ulog)"
  fi
  if [ -n "$USE" ]; then px4_arm_times_of "$USE" "$SID" "$WHO"
  else rm -f "$OUT/px4_arm_times.txt"; say "WARN: no PX4 arm times (no ulog at all) — time-scale gate will be UNVERIFIED"; fi
  ls -l "$HEAVY" | tee -a "$OUT/run.log"
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
  note "python3 $TOOLS/hover_step_report.py $OUT --heavy $HEAVY${LEDGER:+ --ledger $LEDGER}${ISSUE:+ --issue $ISSUE}"
  python3 "$TOOLS/hover_step_report.py" "$OUT" --heavy "$HEAVY" ${LEDGER:+--ledger "$LEDGER"} ${ISSUE:+--issue "$ISSUE"} 2>&1 | tee -a "$OUT/run.log"; REPORT_RC=${PIPESTATUS[0]}
  case "$REPORT_RC" in
    0) say "report: PASS" ;;
    2) say "report: INCOMPLETE (>= 1 gate UNVERIFIED — see the record)" ;;
    1) fail "report: FAIL (see the record and verdicts.log)" ;;
    *) fail "report crashed (rc=$REPORT_RC)" ;;
  esac
}

ALL="precheck up watch isaac interfaces commander params fly collect down analyse report"
case "$PHASE" in
  precheck|up|watch|isaac|interfaces|ifgates|commander|params|fly|collect|down|analyse|report|all|status) ;;
  *) echo "usage: $0 precheck|up|watch|isaac|interfaces|commander|params|fly|collect|down|analyse|report | all | status | ifgates  [run_name]"
     echo "  all = the twelve phases in that order (stops at the first FAIL, containers left up); run_name default sim_hover_step_run1"
     echo "  env: STEPS_PER_AXIS (default 3), LEDGER, ISSUE, ISAAC_GUI=1 (Isaac window on), PAUSE_BEFORE_FLY=1 (Enter before the flight), ISAAC_KIT_ARGS"; exit 2 ;;
esac
[ "$PHASE" = status ] || mkdir -p "$OUT" "$HEAVY"
case "$PHASE" in
  all) ALL_MODE=1; for p in $ALL; do PHASE=$p; [ "$p" = isaac ] && STACK_UP=1; "$p"; [ "$p" = down ] && STACK_UP=0; done; say "all: done (report rc=$REPORT_RC)"; exit "$REPORT_RC" ;;
  *) "$PHASE" ;;
esac

