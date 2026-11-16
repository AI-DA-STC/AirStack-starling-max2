#!/usr/bin/env bash
# Copy one run folder from the workstation back to the laptop (docs/WORKSTATION_SETUP.md). Run it ON THE LAPTOP.
# UNTESTED ON THE 5090: written and checked on the laptop with `bash -n` and --dry-run only (2026-11-17).
#
#   scripts/workstation/sync_results.sh [options] <workstation> <run-name>
#
#   <workstation>  the PC as ssh knows it: its Tailscale name, user@name, or an ssh config alias
#   <run-name>     the folder under runs/, e.g. 2026-11-18_s0_workstation (letters, digits, '.', '_', '-')
#
# Default (a run of this pipeline): copies
#   <workstation>:AirStack-starling-max2/svg_training/runs/<run-name>/  ->  ~/AirStack-starling-max2/svg_training/runs/<run-name>/
# and, into runs/<run-name>/_from_workstation/, the workstation's records/<run-name>_record.md (or its
# _ABORTED_record.md) and its records/LEDGER.md. Records and ledger rows are committed on the laptop only: move the
# record into records/ and copy its ledger row by hand, with the next free T number of the LAPTOP's ledger (the two
# ledgers number separately). Nothing is written into records/ by this script.
#
# Options:
#   --remote-runs DIR  the folder on the workstation that holds <run-name> (relative to its home, or absolute);
#                      default AirStack-starling-max2/svg_training/runs. Use it for other folders, e.g. a partner
#                      job's log folder; the records step is then skipped
#   --local-runs DIR   the folder on the laptop that receives <run-name>; default the laptop's svg_training/runs
#   --resume           copy into a local folder that already exists (to finish a copy that was cut off)
#   --check            ask rsync to list what it would copy, without copying (contacts the workstation)
#   --dry-run          print the commands; contact nothing, write nothing
#
# Exit codes: 0 copied (or listed); 1 rsync failed; 2 bad argument; 6 the local folder exists (see --resume).
set -euo pipefail

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; }

HERE="$(cd "$(dirname "$0")" && pwd)"
SVG="$(cd "$HERE/../.." && pwd)"
DRY=0
CHECK=0
RESUME=0
REMOTE_RUNS=""
LOCAL_RUNS="$SVG/runs"
POS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY=1 ;;
        --check) CHECK=1 ;;
        --resume) RESUME=1 ;;
        --remote-runs) REMOTE_RUNS="${2:?--remote-runs needs a folder}"; shift ;;
        --local-runs) LOCAL_RUNS="${2:?--local-runs needs a folder}"; shift ;;
        -h|--help) usage; exit 0 ;;
        -*) echo "unknown option: $1 (see --help)" >&2; exit 2 ;;
        *) POS+=("$1") ;;
    esac
    shift
done
[ ${#POS[@]} -eq 2 ] || { echo "need <workstation> <run-name> (see --help)" >&2; exit 2; }
WS="${POS[0]}"; NAME="${POS[1]}"
[[ "$NAME" =~ ^[A-Za-z0-9._-]+$ ]] && [ "$NAME" != "." ] && [ "$NAME" != ".." ] \
    || { echo "run name '$NAME': use letters, digits, '.', '_' or '-' (one folder, no '/')" >&2; exit 2; }
[[ "$WS" =~ ^[A-Za-z0-9._@-]+$ ]] || { echo "workstation '$WS': a host name, user@host or ssh alias" >&2; exit 2; }

RECORDS=1
if [ -n "$REMOTE_RUNS" ]; then
    RECORDS=0
else
    REMOTE_RUNS="AirStack-starling-max2/svg_training/runs"
fi
REMOTE_RECORDS="${REMOTE_RUNS%/runs}/records"
DEST="$LOCAL_RUNS/$NAME"
RSYNC=(rsync -av --partial)
[ "$CHECK" -eq 1 ] && RSYNC+=(--dry-run)

if [ "$DRY" -eq 0 ] && [ "$CHECK" -eq 0 ] && [ "$RESUME" -eq 0 ] && [ -d "$DEST" ] && [ -n "$(ls -A "$DEST")" ]; then
    echo "$DEST already exists and is not empty: use --resume to finish an earlier copy, or check the name" >&2
    exit 6
fi

run() {   # print a command, then run it unless this is a dry run
    printf '+'; printf ' %q' "$@"; echo
    [ "$DRY" -eq 1 ] || "$@"
}

[ "$DRY" -eq 1 ] && echo "DRY RUN: commands are printed; nothing is contacted or written."
[ "$CHECK" -eq 1 ] && echo "CHECK: rsync lists what it would copy and copies nothing."
[ "$DRY" -eq 1 ] || [ "$CHECK" -eq 1 ] || mkdir -p "$DEST"
run "${RSYNC[@]}" "$WS:$REMOTE_RUNS/$NAME/" "$DEST/"

if [ "$RECORDS" -eq 1 ]; then
    [ "$DRY" -eq 1 ] || [ "$CHECK" -eq 1 ] || mkdir -p "$DEST/_from_workstation"
    run "${RSYNC[@]}" --ignore-missing-args \
        "$WS:$REMOTE_RECORDS/${NAME}_record.md" "$WS:$REMOTE_RECORDS/${NAME}_ABORTED_record.md" \
        "$WS:$REMOTE_RECORDS/LEDGER.md" "$DEST/_from_workstation/"
    echo
    echo "next, on the laptop: move the record from $DEST/_from_workstation/ into records/, add its ledger row with"
    echo "the laptop ledger's next T number, then commit both (explicit paths, the live clone)."
fi
