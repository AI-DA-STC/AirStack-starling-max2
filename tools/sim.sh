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
      --ledger) [ $# -ge 2 ] || die_usage "--ledger needs a value"; LEDGER=$2; shift ;;
      --issue)  [ $# -ge 2 ] || die_usage "--issue needs a value";  ISSUE=$2;  shift ;;
      -*) die_usage "unknown flag: $1" ;;
      *) if [ -z "$NAME" ]; then NAME=$1; elif [ -z "$RUN" ]; then RUN=$1; else die_usage "unexpected argument: $1"; fi ;;
    esac
    shift
  done
  [ -n "$NAME" ] || die_usage "missing <name>"
  [ "$NAME" != _template ] && [[ "$NAME" =~ ^[A-Za-z0-9_]+$ ]] && [ -d "$REPO/tools/sim_tests/$NAME" ] \
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

not_yet() { echo "$1: not implemented yet ($2)" >&2; exit 2; }
cmd_test()    { not_yet test "Task 8"; }
cmd_figures() { not_yet figures "Task 8"; }
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
  down)   stack_env; PHASE=down; HEADLESS=false; down ;;
  status) HEADLESS=false; stack_env nomk; PHASE=status; status ;;
  tabs)   exec "$REPO/tools/sim_terminals.sh" ;;
  test)   parse_test_args "$@"; cmd_test ;;
  figures) cmd_figures "$@" ;;
  setup)  cmd_setup "$@" ;;
  doctor) cmd_doctor "$@" ;;
  check)  cmd_check "$@" ;;
esac
