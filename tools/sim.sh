#!/usr/bin/env bash
# tools/sim.sh — the one front door for the sim stack and the live tests. SIM ONLY (CLAUDE.md iron rule 9:
# nothing measured here is ported to the drone). Flags, not environment variables.
#
#   setup                  one-time host/container preparation (Foxglove layouts, tool copies)
#   doctor                 read-only health check of the host, containers and ports
#   up [--headless]        start the stack: precheck, watch, Isaac, MAVROS interfaces (window mode by default)
#   down                   stop the stack (commander, bag, interfaces, ulogs, Isaac); containers stay up
#   status                 what is running now
#   tabs                   open the terminal tabs for the stack
#   test <name> [--headless] [--no-pause] --ledger N --issue NEAR-nnn <run>
#                          run tools/sim_tests/<name> end to end; records land in docs/record/<run>/
#   figures                make the record figures of a finished run
#   check                  verify a finished run's record
#
# No argument, -h or an unknown subcommand prints this usage and exits 2; nothing is run.
set -o pipefail
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SIM_TESTS_DIR=${SIM_TESTS_DIR:-$REPO/tools/sim_tests}     # overridable for the unit tests only

usage() {
  cat <<'USAGE'
usage: tools/sim.sh <setup|doctor|up|down|status|tabs|test|figures|check> [flags]
  setup                                  one-time preparation (Foxglove layouts, tool copies)
  doctor                                 read-only health check
  up [--headless]                        start the sim stack (Isaac window unless --headless)
  down                                   stop the sim stack
  status                                 what is running
  tabs                                   open the terminal tabs
  test <name> [--headless] [--no-pause] --ledger N --issue NEAR-nnn <run>
                                         run tools/sim_tests/<name>; --ledger N = new LEDGER row, --issue = Linear id
  figures                                make the record figures of a run
  check                                  verify a run's record
sim only; flags, not environment variables.
USAGE
}

die_usage() { usage_line >&2; echo "error: $*" >&2; exit 2; }
usage_line() { echo "usage: tools/sim.sh test <name> [--headless] [--no-pause] --ledger N --issue NEAR-nnn <run>"; }

# parse_test_args <args…>: sets NAME LEDGER ISSUE RUN HEADLESS PAUSE USE_STUDIO; any violation exits 2 before any container call
parse_test_args() {
  NAME=""; LEDGER=""; ISSUE=""; RUN=""; HEADLESS=false; PAUSE=1
  while [ $# -gt 0 ]; do
    case "$1" in
      --headless) HEADLESS=true ;;
      --no-pause) PAUSE=0 ;;
      --ledger) { [ $# -ge 2 ] && [[ "$2" != --* ]]; } || die_usage "--ledger needs a value"; LEDGER=$2; shift ;;
      --issue)  { [ $# -ge 2 ] && [[ "$2" != --* ]]; } || die_usage "--issue needs a value";  ISSUE=$2;  shift ;;
      -*) die_usage "unknown flag: $1" ;;
      *) if [ -z "$NAME" ]; then NAME=$1; elif [ -z "$RUN" ]; then RUN=$1; else die_usage "unexpected argument: $1"; fi ;;
    esac
    shift
  done
  [ -n "$NAME" ] || die_usage "missing <name>"
  [ "$NAME" != _template ] && [[ "$NAME" =~ ^[A-Za-z0-9_]+$ ]] && [ -d "$SIM_TESTS_DIR/$NAME" ] \
    || die_usage "no such test: $NAME (need a directory tools/sim_tests/<name>, not _template)"
  [[ "$LEDGER" =~ ^[0-9]+$ ]] || die_usage "--ledger must be an integer (got '${LEDGER}')"
  [[ "$ISSUE" =~ ^NEAR-[0-9]+$ ]] || die_usage "--issue must look like NEAR-123 (got '${ISSUE}')"
  [ -n "$RUN" ] || die_usage "missing <run>"
  [[ "$RUN" =~ ^[A-Za-z0-9_]+$ ]] || die_usage "<run> must match [A-Za-z0-9_]+ (got '${RUN}')"
  [ "$HEADLESS" = true ] && PAUSE=0
  if [ "$HEADLESS" = true ]; then USE_STUDIO=false; else USE_STUDIO=true; fi
}

# stack_env: the variables lib/stack.sh needs, for the bare stack (up/down/status)
stack_env() {   # stack_env [nomk]
  RUN=_stack; OUT=$HOME/flight_logs/sim/_stack; HEAVY=$OUT; S=/tmp/svg_test
  SCENARIO=-; BAG_PREFIX=svg; CONFIG=cbf_sim.yaml
  [ "${1:-}" = nomk ] || mkdir -p "$OUT"
  # shellcheck source=lib/stack.sh
  source "$REPO/tools/lib/stack.sh" || exit $?
}

no_args() { [ $# -eq 0 ] || { usage_line >&2; echo "error: $SUB takes no arguments (got $1)" >&2; exit 2; }; }
not_yet() { echo "$1: not implemented yet ($2)" >&2; exit 2; }

# cmd_figures <name> <run>: the record figure (plot 1 of the test's plots.json) from the run's metrics.csv
cmd_figures() {
  [ $# -eq 2 ] || { echo "usage: tools/sim.sh figures <name> <run>" >&2; echo "error: figures needs exactly <name> <run>" >&2; exit 2; }
  local n=$1 r=$2
  [ -d "$SIM_TESTS_DIR/$n" ] && [[ "$r" =~ ^[A-Za-z0-9_]+$ ]] || { echo "error: no such test '$n' or bad run name '$r'" >&2; return 2; }
  python3 "$REPO/tools/live/plot_metrics.py" "$REPO/docs/record/$r/metrics.csv" --plots "$SIM_TESTS_DIR/$n/plots.json" -o "$REPO/docs/record/$r/fig-1.png"
}

# ----------------------------------------------------------------------------------------------- test flow
# stop_tail: the per-second line streamer (host tail of `docker exec … tail -f`) and its container-side process
stop_tail() { [ -n "${TAIL:-}" ] && kill "$TAIL" 2>/dev/null; TAIL=""; docker exec "$R" pkill -f "tail -n0 -f $S/metrics_node.log" >/dev/null 2>&1 || true; }

# metrics_stop: SIGINT the node (CSV flushed + closed), wait <= 10 s, TERM if needed, copy CSV + log out. Idempotent; also the ABORT_HOOK.
metrics_stop() {
  stop_tail
  [ "${METRICS_STARTED:-0}" = 1 ] || return 0                           # this run never started the node: nothing here is ours to stop
  docker exec "$R" pkill -f "fly\\.sh" >/dev/null 2>&1 || true        # an aborted run must not keep flying a script (harmless after a normal landing)
  [ ! -f "$HEAVY/.metrics_stopped" ] || return 0
  local i
  if alive "$R" 'python3 metrics_node\.py'; then
    nx docker exec "$R" pkill -INT -f 'python3 metrics_node.py' || true
    for i in $(seq 1 10); do alive "$R" 'python3 metrics_node\.py' || break; sleep 1; done
    alive "$R" 'python3 metrics_node\.py' && { say "WARN: metrics node still alive 10 s after SIGINT — TERM"; docker exec "$R" pkill -TERM -f 'python3 metrics_node.py' || true; sleep 3; }
  fi
  metrics_collect
}
metrics_collect() {
  docker cp "$R:$S/metrics.csv" "$OUT/metrics.csv" 2>/dev/null && say "metrics.csv copied ($(wc -l < "$OUT/metrics.csv") lines)" || say "WARN: no metrics.csv in the robot container"
  docker cp "$R:$S/metrics_node.log" "$OUT/metrics_node.log" 2>/dev/null || true
  local o; o=$(grep -m1 '^# offsets=' "$OUT/metrics.csv" 2>/dev/null | sed 's/^# offsets=//')
  [ -n "$o" ] && echo "offsets=$o" >> "$OUT/run_meta.txt" || true
  touch "$HEAVY/.metrics_stopped"
}

# bag_dump_hook <bag path in $R> (called by stack.sh down): recompute the metrics from the bag; non-zero = bag stays in the container
bag_dump_hook() {
  local b=$1
  note "docker exec $R bash -ic 'python3 $S/bag_recompute.py $b --test-dir $S --meta-from $S/metrics.csv -o $S/metrics_bag.csv'"
  docker exec "$R" bash -ic "python3 $S/bag_recompute.py $b --test-dir $S --meta-from $S/metrics.csv -o $S/metrics_bag.csv" 2>&1 | grep -v -E "$NOISE" | tee -a "$OUT/run.log"
  if [ "${PIPESTATUS[0]}" = 0 ] && docker cp "$R:$S/metrics_bag.csv" "$OUT/metrics_bag.csv" 2>/dev/null; then say "metrics_bag.csv copied"; return 0; fi
  caveat "bag recompute failed — live/offline cross-check missing (bag left in the robot container at $b)"; return 1
}

render_report() {   # the record + verdict banner; REPORT_RC = report.py's rc (0 PASS / 2 INCOMPLETE / 1 FAIL / 3 ABORTED)
  local RTMP; RTMP=$(mktemp)
  note "python3 $REPO/tools/lib/report.py $SIM_TESTS_DIR/$NAME $OUT --heavy $HEAVY --ledger $LEDGER --issue $ISSUE"
  python3 "$REPO/tools/lib/report.py" "$SIM_TESTS_DIR/$NAME" "$OUT" --heavy "$HEAVY" --ledger "$LEDGER" --issue "$ISSUE" 2>&1 | tee -a "$OUT/run.log" > "$RTMP"
  REPORT_RC=${PIPESTATUS[0]}
  cat "$RTMP"
  local v head; v=$(head -1 "$RTMP" | sed 's/:.*//'); head=$(sed -n 's/^HEADLINE: //p' "$RTMP" | head -1)
  case "$v" in
    PASS|FAIL|INCOMPLETE|ABORTED) say "========  VERDICT: $v — ${head:-n/a}  ========" ;;
    *) say "REPORT ERROR: report.py printed no verdict (rc=$REPORT_RC): $(head -1 "$RTMP")"; REPORT_RC=4 ;;
  esac
  rm -f "$RTMP"
}
# finish_report: REPORT_HOOK for abort/failure paths — the record, then the scratch dir in the robot container
finish_report() { rm -f "$HEAVY/.metrics_stopped"; render_report; [ "${OWN_SCRATCH:-0}" = 1 ] && docker exec "$R" rm -rf "$S" >/dev/null 2>&1; true; }

# one `sim.sh test` at a time: a second run would kill the first one's processes and scratch dir
SIM_LOCK=$HOME/flight_logs/sim/.sim_test.lock
take_lock() {
  mkdir -p "$(dirname "$SIM_LOCK")"
  if [ -f "$SIM_LOCK" ] && kill -0 "$(cat "$SIM_LOCK" 2>/dev/null)" 2>/dev/null; then
    echo "error: another sim.sh test is already running (pid $(cat "$SIM_LOCK"), lock $SIM_LOCK)" >&2; exit 2; fi
  rm -f "$SIM_LOCK"
  ( set -C; echo $$ > "$SIM_LOCK" ) 2>/dev/null || { echo "error: could not take $SIM_LOCK" >&2; exit 2; }
  trap 'rm -f "$SIM_LOCK"' EXIT
}

cmd_test() {
  take_lock
  OWN_SCRATCH=0; METRICS_STARTED=0
  local ISSUE_ARG=$ISSUE
  # shellcheck source=/dev/null
  source "$SIM_TESTS_DIR/$NAME/test.env"; ISSUE=$ISSUE_ARG          # test.env's ISSUE is the default; the flag wins
  S=/tmp/svg_test; OUT=$REPO/docs/record/$RUN; HEAVY=$HOME/flight_logs/sim/$RUN; ALL_MODE=1; STACK_UP=0; TAIL=""; REPORT_RC=0
  mkdir -p "$OUT" "$HEAVY"
  source "$REPO/tools/lib/stack.sh" || exit $?
  local TD=$SIM_TESTS_DIR/$NAME FIRST
  FIRST=$(python3 -c "
import json, sys
p = json.load(open(sys.argv[1]))['plots'][0]['series']
print(next((s for s in p if 'running' in s), p[0]))" "$TD/plots.json") || FIRST=min_pair_distance_running
  rm -f "$HEAVY/.metrics_stopped" "$OUT/aborted.txt"; METRICS_STARTED=0
  # 1  stack phases; the abort trap is armed from the commander phase on
  ABORT_HOOK=metrics_stop; REPORT_HOOK=finish_report; FAIL_HOOK=metrics_stop; FAIL_RC=4     # a wiring failure exits 4, a gate FAIL exits 1
  for PHASE in precheck up watch isaac interfaces commander params; do
    [ "$PHASE" = isaac ] && STACK_UP=1
    [ "$PHASE" = commander ] && arm_abort_trap
    "$PHASE"
  done
  # 2  copy-in
  PHASE=metrics
  phase_begin metrics
  OWN_SCRATCH=1                           # from here /tmp/svg_test in the robot container is this run's to delete
  nx docker exec "$R" mkdir -p "$S"
  for f in "$REPO/tools/live/metrics_core.py" "$REPO/tools/live/metrics_node.py" "$REPO/tools/live/bag_recompute.py" "$TD/metrics.py" "$TD/fly.sh"; do
    nx docker cp "$f" "$R:$S/" || fail "docker cp $f"; done
  # 3  metrics node: started before the flight, ready + liveness checked
  docker exec "$R" pkill -f 'python3 metrics_node.py' >/dev/null 2>&1 || true      # never two nodes publishing /svg/test/*
  docker exec "$R" bash -c ": > $S/metrics_node.log; rm -f $S/metrics.csv"
  METRICS_STARTED=1
  note "docker exec -d $R bash -ic 'cd $S && python3 metrics_node.py --test-dir $S --csv $S/metrics.csv > $S/metrics_node.log 2>&1'"
  docker exec -d "$R" bash -ic "cd $S && python3 metrics_node.py --test-dir $S --csv $S/metrics.csv > $S/metrics_node.log 2>&1"
  NEED=1 wait_for 90 2 "metrics node ready" count_log "$R" 'metrics_node: ready' "$S/metrics_node.log" || fail "metrics node refused: $(docker exec "$R" tail -3 "$S/metrics_node.log")"
  local hz; hz=$(rx "timeout 10 ros2 topic hz /svg/test/$FIRST -w 20" | sed -n 's/.*average rate: *\([0-9.]*\).*/\1/p' | tail -1)
  say "metrics liveness: /svg/test/$FIRST ${hz:-0} Hz"
  awk -v h="${hz:-0}" 'BEGIN{exit !(h+0 >= 5)}' || fail "metrics node is not publishing /svg/test/$FIRST (${hz:-0} Hz < 5)"
  say "layout: tools/sim_tests/$NAME/layout.json (import once in Studio if not installed by setup)"
  if [ "$PAUSE" = 1 ]; then
    say "Stack up, drones on their pads, plots live. Start OBS now, then press Enter to fly."
    read -r _ < /dev/tty || fail "no terminal to wait on (use --no-pause)"
  fi
  # 4  fly
  PHASE=fly
  phase_begin fly test_stdout.log armed_post.txt landing_evidence.txt status_post.json
  alive "$R" swarm_commander || fail "commander is not running"
  say "fly: tools/sim_tests/$NAME/fly.sh $DURATION_S s window (takeoff -> start -> window -> land)"
  note "docker exec -d $R bash -ic 'bash $S/fly.sh $DURATION_S > $S/test_stdout.log 2>&1'"
  docker exec -d "$R" bash -ic "bash $S/fly.sh $DURATION_S > $S/test_stdout.log 2>&1"
  docker exec "$R" tail -n0 -f "$S/metrics_node.log" & TAIL=$!
  sleep 3
  local el=0
  while alive "$R" 'fly\.sh'; do
    [ "$el" -ge $((DURATION_S + 240)) ] && { say "WARN: fly.sh still running after $el s — landing everything"; land_all_and_wait 60 || true; break; }
    sleep 2; el=$((el+2)); done
  stop_tail
  docker cp "$R:$S/test_stdout.log" "$OUT/" 2>/dev/null || say "WARN: no test_stdout.log"
  grep -q 'landed:' "$OUT/test_stdout.log" || say "WARN: fly.sh did not print landed:"
  # 5  post-flight evidence
  sleep 20
  note "for N in 1 2 3: docker exec $R bash -ic 'timeout 10 ros2 topic echo --once /drone_\$N/interface/mavros/state' | grep -oE '^armed: (true|false)'  # -> armed_post.txt"
  for N in 1 2 3; do rx "timeout 10 ros2 topic echo --once /drone_$N/interface/mavros/state" | grep -oE '^armed: (true|false)' | sed "s/^/drone_$N /"; done > "$OUT/armed_post.txt"
  tee -a "$OUT/run.log" < "$OUT/armed_post.txt"
  [ "$(wc -l < "$OUT/armed_post.txt")" = 3 ] || say "WARN: armed_post.txt does not hold three lines (armed gate will be UNVERIFIED)"
  grep -q 'armed: true' "$OUT/armed_post.txt" && say "!! a drone still reports armed: true 20 s after landing" || true
  docker exec "$R" grep -E 'touchdown at z=|landed, disarmed|disarm not accepted' "$S/commander.log" | tee "$OUT/landing_evidence.txt" | tee -a "$OUT/run.log" || true
  json1 /svg/commander_status > "$OUT/status_post.json" || say "WARN: no commander_status after the flight"
  # 6  ask for the OBS file while the plots are still live, then stop the node
  if [ "$PAUSE" = 1 ]; then
    say "Landed. Plots still live; the metrics node stops when you press Enter. OBS file name (Enter to skip):"
    local v; read -r v < /dev/tty || v=""
    echo "${v:-none recorded}" > "$OUT/video.txt"
  else echo "none (headless run)" > "$OUT/video.txt"; fi
  PHASE=metrics_stop
  metrics_stop
  # 7  ulogs, params, arm times, then the stack down (bag dump hook = bag recompute)
  PHASE=collect
  phase_begin collect ulog_list.txt ulog_sysid_map.txt params_ulog.txt px4_arm_times.txt
  copy_ulogs
  local U1 USE SID=2 WHO=drone_1; U1=$(awk '$1==2{print $2}' "$OUT/ulog_sysid_map.txt" | tail -1)
  if [ -n "$U1" ]; then ulog_header_params "$U1"; USE=$U1
  else
    say "WARN: no sysid-2 (drone_1) ulog for this session — params_ulog.txt stays empty (report: UNVERIFIED)"
    read -r SID USE _ < <(tail -1 "$OUT/ulog_sysid_map.txt"); [ -n "$USE" ] && WHO="drone_$((SID-1)) (FALLBACK: no drone_1 ulog)"
  fi
  if [ -n "$USE" ]; then px4_arm_times_of "$USE" "$SID" "$WHO"
  else rm -f "$OUT/px4_arm_times.txt"; say "WARN: no PX4 arm times (no ulog at all)"; fi
  PHASE=down; down; STACK_UP=0
  docker exec "$R" rm -rf "$S"
  rm -f "$HEAVY/.metrics_stopped"; OWN_SCRATCH=0
  FAIL_HOOK=""; REPORT_HOOK=""            # from here a render problem is the report's, not a wiring failure
  # 8  figure, record, verdict
  PHASE=report
  cmd_figures "$NAME" "$RUN" 2>&1 | tee -a "$OUT/run.log"; [ "${PIPESTATUS[0]}" = 0 ] || say "WARN: figure not made (record will show it missing)"
  render_report
  exit "$REPORT_RC"
}
cmd_setup()   { not_yet setup "Task 9"; }
cmd_doctor()  { not_yet doctor "Task 9"; }
cmd_check()   { not_yet check "Task 9"; }

SUB=${1:-}
case "$SUB" in
  ""|-h|--help) usage; exit 2 ;;
  setup|doctor|up|down|status|tabs|test|figures|check) shift ;;
  *) usage; exit 2 ;;
esac

case "$SUB" in
  up)
    HEADLESS=false
    for a in "$@"; do case "$a" in --headless) HEADLESS=true ;; *) usage_line >&2; echo "error: up: unknown flag $a" >&2; exit 2 ;; esac; done
    stack_env
    for PHASE in precheck up watch isaac interfaces; do "$PHASE"; done ;;
  down)   no_args "$@"; HEADLESS=false; stack_env; PHASE=down; down ;;
  status) no_args "$@"; HEADLESS=false; stack_env nomk; PHASE=status; status ;;
  tabs)   no_args "$@"; exec "$REPO/tools/sim_terminals.sh" ;;
  test)   parse_test_args "$@"; cmd_test ;;
  figures) cmd_figures "$@" ;;
  setup)  cmd_setup "$@" ;;
  doctor) cmd_doctor "$@" ;;
  check)  cmd_check "$@" ;;
esac
