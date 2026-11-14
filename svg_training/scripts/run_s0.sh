#!/usr/bin/env bash
# S0 front door: tests, tier 1 sweep, tier 2 sweep, then the record. See STANDARDS.md section 7 and 8.
# Usage: bash scripts/run_s0.sh [--dry-run] [--tier1-only] <name> <approved_config_sha256>
# Exit codes: 0 the record was written (whatever its verdict; with --tier1-only: tier 1 ran without a crashed point),
# 1 the record could not be written (or, with --tier1-only, a tier 1 point crashed), 64 bad arguments,
# 65 config differs from the approved one, 66 an Isaac/AirStack container is running, 67 the record already exists,
# 68 another process is using the GPU (python, kit, isaac or omni in nvidia-smi's compute-apps list),
# 130 interrupted (INT, TERM or HUP). A tier 1 crash or a stopped tier 2 sweep never ends the run early: the record
# is written and says FAIL.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# On this host: the conda env and the Isaac Lab clone. In the docker image (docker/Dockerfile) the image sets
# SVG_IN_CONTAINER, SVG_PY and SVG_ISAACLAB, and there is no conda.
PY="${SVG_PY:-$HOME/miniconda3/envs/env_isaaclab/bin/python}"
ISAACLAB="${SVG_ISAACLAB:-$HOME/IsaacLab/isaaclab.sh}"
IN_CONTAINER="${SVG_IN_CONTAINER:-0}"
CONFIG=configs/s0_benchmark.toml
SEEDS="0 for every case and repeat, both tiers (Tier1BenchCfg.seed default; torch.manual_seed(0) in tier 2)"
USAGE="Usage: bash scripts/run_s0.sh [--dry-run] [--tier1-only] <name YYYY-MM-DD_s0_label> <approved_config_sha256>"

DRY_RUN=0
TIER1_ONLY=0
NAME=""
APPROVED_SHA=""
RUN_DIR=""
RESULTS=""
STEP="starting"
CHILD=""
TESTS_PASSED="no"
TIER1_RC=0
TIER2_STOPPED=""
GPU_NAME="unknown"
COMMIT="unknown"
CODE_SHA="unknown"
GPU_APPS=""
GPU_BUSY=""
INTERRUPTED=0
FINISHED=0
CHILD_RC=0

# ---------------------------------------------------------------- helpers

step() {  # step <n> <text>
    STEP="[$1/9] $2"
    echo "$STEP"
}

die() {  # die <code> <message>
    echo "$2" >&2
    exit "$1"
}

result_rows() {
    if [ -f "$RESULTS" ]; then
        wc -l < "$RESULTS" | tr -d ' '
    else
        echo 0
    fi
}

# run_child <logfile> <command...>: run in the background, in its own process group (setsid), so the trap can stop
# the whole group; set CHILD_RC. Whatever of the group is left after a failed child is killed.
run_child() {
    local log="$1"
    shift
    CHILD_RC=0
    setsid "$@" >> "$log" 2>&1 &
    CHILD=$!
    wait "$CHILD" || CHILD_RC=$?
    if [ "$CHILD_RC" -ne 0 ]; then
        kill -KILL -- "-$CHILD" 2>/dev/null || true
    fi
    CHILD=""
}

# group_alive <pgid>: 0 if a process of that group is running (zombies do not count).
group_alive() {
    ps -eo pgid=,stat= | awk -v g="$1" '$1 == g && $2 !~ /^Z/ { f = 1 } END { exit !f }'
}

# stop_child: TERM to the child's process group, wait up to 30 s, then KILL the group.
stop_child() {
    [ -n "$CHILD" ] || return 0
    kill -TERM -- "-$CHILD" 2>/dev/null || kill -TERM "$CHILD" 2>/dev/null || true
    local i
    for i in $(seq 1 30); do
        group_alive "$CHILD" || break
        sleep 1
    done
    kill -KILL -- "-$CHILD" 2>/dev/null || true
}

# busy_gpu_procs: stdin = nvidia-smi compute-apps lines (pid, name); prints those that would disturb a timing:
# a name containing python, kit, isaac or omni (case-insensitive). Desktop processes such as
# gnome-remote-desktop-daemon are not printed.
busy_gpu_procs() {
    grep -iE 'python|kit|isaac|omni' || true
}

gpu_apps() {
    nvidia-smi --query-compute-apps=pid,name --format=csv,noheader 2>/dev/null || true
}

# wait_gpu_idle: wait up to 60 s for python/kit/isaac/omni processes to leave the GPU; 0 if idle, else 1 and
# GPU_BUSY lists them.
wait_gpu_idle() {
    local i
    for i in $(seq 0 12); do
        GPU_BUSY="$(gpu_apps | busy_gpu_procs)"
        [ -z "$GPU_BUSY" ] && return 0
        [ "$i" -lt 12 ] && sleep 5
    done
    return 1
}

# ---------------------------------------------------------------- interrupt and error exit

write_aborted() {  # write_aborted <reason>
    mkdir -p records
    local aborted="records/${NAME}_ABORTED_record.md"
    local header="Simulator: training simulator, tiers 1 and 2 (stand-in drone models, no safety filter)"
    local again=0
    [ -f "$aborted" ] && again=1  # decided before the redirection below creates the file
    {
        if [ "$again" -eq 1 ]; then
            echo
            echo "## Another abort"
        else
            echo "$header"
            echo
        fi
        echo "ABORTED"
        echo
        echo "- Date-time: $(date -Iseconds)"
        echo "- Reason: $1"
        echo "- Step running: $STEP"
        echo "- Result rows so far: $(result_rows)"
        echo "- Run folder: $ROOT/$RUN_DIR"
    } >> "$aborted"
    echo "ABORTED: wrote $aborted" >&2
}

on_interrupt() {
    trap '' INT TERM HUP
    INTERRUPTED=1
    stop_child
    write_aborted "interrupted"
    exit 130
}

# EXIT handler: a script that leaves through an error before the record was written (or the sweep was finished)
# writes the ABORTED record. Not on a normal end, not after an interrupt (handled above), not in a dry run
# (the handler is installed after the dry run).
on_exit() {
    local rc=$?
    trap '' EXIT
    if [ "$INTERRUPTED" -eq 0 ] && [ "$FINISHED" -eq 0 ] && [ "$rc" -ne 0 ]; then
        stop_child
        write_aborted "left through an error (exit $rc)"
    fi
    return 0
}

# ---------------------------------------------------------------- step 1..3

parse_args() {
    local positional=()
    local arg
    for arg in "$@"; do
        case "$arg" in
            --dry-run) DRY_RUN=1 ;;
            --tier1-only) TIER1_ONLY=1 ;;
            *) positional+=("$arg") ;;
        esac
    done
    if [ "${#positional[@]}" -ne 2 ]; then
        die 64 "$USAGE"
    fi
    NAME="${positional[0]}"
    APPROVED_SHA="${positional[1]}"
    if ! [[ "$NAME" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}_s0_[a-z0-9_]+$ ]]; then
        die 64 "$USAGE"
    fi
    if ! [[ "$APPROVED_SHA" =~ ^[0-9a-fA-F]{64}$ ]]; then
        die 64 "$USAGE"
    fi
    RUN_DIR="runs/$NAME"
    RESULTS="$RUN_DIR/results.jsonl"
}

check_config_hash() {
    local actual
    actual="$(sha256sum "$CONFIG" | cut -d' ' -f1)"
    if [ "$actual" != "${APPROVED_SHA,,}" ]; then
        die 65 "config differs from the approved one: gates are fixed before a run (STANDARDS §7.1)"
    fi
}

check_no_container() {
    local names hit
    names="$(docker ps --format '{{.Names}}' 2>/dev/null)" || names=""
    hit="$(printf '%s\n' "$names" | grep -iE 'isaac|airstack' | head -n 1)" || hit=""
    if [ -n "$hit" ]; then
        die 66 "refusing to run: container '$hit' is running and would disturb the timings; stop it first"
    fi
}

check_gpu_idle() {
    GPU_APPS="$(gpu_apps)"
    local busy
    busy="$(printf '%s\n' "$GPU_APPS" | busy_gpu_procs)"
    if [ -n "$busy" ]; then
        printf '%s\n' "$busy" >&2
        die 68 "refusing to run: the processes above are using the GPU and would disturb the timings; stop them first"
    fi
}

# ---------------------------------------------------------------- command builders (used by dry run and real run)

tier1_cmd() {
    CMD=(env PYTHONPATH=source "$PY" scripts/benchmark_tier1.py --config "$CONFIG" --out "$RESULTS" --device cuda)
}

tier2_cmd() {  # tier2_cmd <case> <num_games>
    # TERM=xterm: isaaclab.sh runs `set -e` then `tabs 4`, which exits 1 when TERM=dumb
    # Host: through the conda env. In the container isaaclab.sh -p is called directly (no conda there).
    local launcher=(conda run -n env_isaaclab --no-capture-output)
    [ "$IN_CONTAINER" = "1" ] && launcher=()
    CMD=(timeout -k 60 1800 "${launcher[@]}" env TERM=xterm PYTHONPATH=source "$ISAACLAB" -p
         scripts/benchmark_tier2.py --headless --case "$1" --num-games "$2" --config "$CONFIG" --out "$RESULTS")
}

record_cmd() {
    CMD=("$PY" scripts/make_record.py --results "$RESULTS" --config "$CONFIG" --tests-passed "$TESTS_PASSED"
         --name "$NAME" --seeds "$SEEDS")
    if [ -n "$TIER2_STOPPED" ]; then
        CMD+=(--note "$TIER2_STOPPED")
    fi
    if [ -s "$RUN_DIR/retried_points.txt" ]; then
        CMD+=(--retried-file "$RUN_DIR/retried_points.txt")
    fi
    if [ -s "$RUN_DIR/overflow_points.txt" ]; then
        CMD+=(--flags-file "$RUN_DIR/overflow_points.txt")
    fi
}

# One line per tier 2 point, "case num_games drones_per_game", config order, num_games ascending.
tier2_points() {
    "$PY" -c '
import sys, tomllib
cfg = tomllib.load(open(sys.argv[1], "rb"))
for case in cfg["tier2"]:
    for n in sorted(case["num_games"]):
        print(case["name"], n, case["drones_per_game"])
' "$CONFIG"
}

# ---------------------------------------------------------------- dry run

dry_run() {
    local case_name n k
    echo "DRY: mkdir -p $RUN_DIR   (refuse if records/${NAME}_record.md exists; an existing $RESULTS is resumed)"
    echo "DRY: refuse (exit 68) if nvidia-smi --query-compute-apps lists a process matching python|kit|isaac|omni (checked before the start and before each tier 2 point; up to 60 s wait before a tier 2 point, then a crash row with note \"gpu busy\")"
    echo "DRY: write $RUN_DIR/preflight.txt (date-time, git commit, code_sha, config sha256, GPU compute apps, nvidia-smi, hostname); cp $CONFIG $RUN_DIR/s0_benchmark.toml"
    echo "DRY: $PY -m pytest -q -W error > $RUN_DIR/tests.txt"
    tier1_cmd
    echo "DRY: ${CMD[*]} >> $RUN_DIR/tier1.log"
    if [ "$TIER1_ONLY" -eq 1 ]; then
        echo "DRY: tier 1 only: no tier 2 sweep, no record"
        return 0
    fi
    while read -r case_name n k; do
        tier2_cmd "$case_name" "$n"
        echo "DRY: ${CMD[*]} >> $RUN_DIR/tier2_logs/${case_name}_${n}.log   (one summary line in $RUN_DIR/tier2.log; a non-zero exit with no row and no mass_kg= line in the log is an Isaac start-up crash: log moved to ${case_name}_${n}.startup_crash1.log, point run once more, line added to $RUN_DIR/retried_points.txt; no row afterwards: append an oom row if the log says out of memory, else a crash row, drones_per_game=$k; log mentions overflow: point added to $RUN_DIR/overflow_points.txt)"
    done < <(tier2_points)
    echo "DRY: if the first tier 2 point leaves no ok row: stop tier 2, go to the record with --note <reason>"
    TESTS_PASSED="<yes|no>"
    record_cmd
    echo "DRY: ${CMD[*]} [--note <reason, if tier 2 stopped>] [--flags-file $RUN_DIR/overflow_points.txt, if any point overflowed]"
}

# ---------------------------------------------------------------- steps 4..9

prepare_run_dir() {
    step 4 "run folder $RUN_DIR"
    if [ -f "records/${NAME}_record.md" ]; then
        die 67 "records/${NAME}_record.md already exists: a record is never overwritten"
    fi
    mkdir -p "$RUN_DIR/tier2_logs" records
    if [ -f "$RESULTS" ]; then
        echo "resuming: $RESULTS has $(result_rows) rows"
    fi
}

write_preflight() {
    step 5 "preflight"
    local sha
    sha="$(sha256sum "$CONFIG" | cut -d' ' -f1)"
    if [ -n "${SVG_COMMIT:-}" ]; then  # set by docker/run.sh: the container has no .git
        COMMIT="$SVG_COMMIT"
    else
        COMMIT="$(git -C "$ROOT/.." rev-parse --short HEAD 2>/dev/null)" || COMMIT="unknown"
    fi
    [ -n "$COMMIT" ] || COMMIT="unknown"
    CODE_SHA="$(PYTHONPATH=source "$PY" -c 'from svg_training.bench.rows import code_sha; print(code_sha())' 2>/dev/null)" || CODE_SHA=""
    [ -n "$CODE_SHA" ] || CODE_SHA="unknown"
    GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n 1)" || GPU_NAME=""
    [ -n "$GPU_NAME" ] || GPU_NAME="unknown"
    {
        echo "date-time: $(date -Iseconds)"
        echo "git commit (svg_training/ is tracked; -dirty = uncommitted changes under svg_training/ at the start of the run): $COMMIT"
        echo "code_sha: $CODE_SHA"
        echo "config sha256: $sha"
        echo "hostname: $(hostname)"
        echo "in container (SVG_IN_CONTAINER): $IN_CONTAINER"
        echo "PY: $PY"
        echo "ISAACLAB: $ISAACLAB"
        echo "--- GPU compute apps (pid, name; all of them) ---"
        printf '%s\n' "${GPU_APPS:-none}"
        echo "--- nvidia-smi ---"
        nvidia-smi 2>&1 || echo "nvidia-smi failed"
    } > "$RUN_DIR/preflight.txt"
    cp "$CONFIG" "$RUN_DIR/s0_benchmark.toml"
}

run_tests() {
    step 6 "tests"
    run_child_overwrite "$RUN_DIR/tests.txt" "$PY" -m pytest -q -W error
    if [ "$CHILD_RC" -eq 0 ]; then
        TESTS_PASSED="yes"
    else
        TESTS_PASSED="no"
        echo "tests FAILED (exit $CHILD_RC): continuing, the record will say FAIL"
    fi
}

run_child_overwrite() {  # like run_child, but the log is rewritten
    : > "$1"
    run_child "$@"
}

run_tier1() {
    step 7 "tier 1 sweep"
    tier1_cmd
    run_child "$RUN_DIR/tier1.log" "${CMD[@]}"
    TIER1_RC="$CHILD_RC"
    if [ "$TIER1_RC" -eq 3 ]; then
        echo "tier 1: nothing matched (exit 3)"
        TIER1_RC=0
    elif [ "$TIER1_RC" -ne 0 ]; then
        echo "tier 1 FAILED (exit $TIER1_RC; a crashed point does not stop the sweep): going on to tier 2 and the record"
    fi
}

has_row() {  # has_row <case> <num_games>: 0 if the results file has a row for the point
    PYTHONPATH=source "$PY" -c '
import sys
from svg_training.bench.rows import existing_points
sys.exit(0 if (sys.argv[2], int(sys.argv[3])) in existing_points(sys.argv[1]) else 1)
' "$RESULTS" "$1" "$2"
}

has_ok_row() {  # has_ok_row <case> <num_games>: 0 if the results file has an ok row for the point
    PYTHONPATH=source "$PY" -c '
import json, sys
case, n = sys.argv[2], int(sys.argv[3])
ok = False
for line in open(sys.argv[1]):
    if line.strip():
        r = json.loads(line)
        ok = ok or (r.get("case") == case and r.get("num_games") == n and r.get("status") == "ok")
sys.exit(0 if ok else 1)
' "$RESULTS" "$1" "$2"
}

append_crash_row() {  # append_crash_row <case> <num_games> <drones_per_game> <status> <note>
    PYTHONPATH=source "$PY" -c '
import json, sys
from svg_training.bench.rows import ROW_KEYS
out, case, n, k, status, note, gpu, commit, sha, date = sys.argv[1:]
row = {key: None for key in ROW_KEYS}
row.update(tier=2, case=case, num_games=int(n), drones_per_game=int(k), repeat=0, status=status,
           device="cuda:0", gpu_name=gpu, commit=commit, code_sha=sha, date=date, note=note)
with open(out, "a") as fh:
    fh.write(json.dumps(row) + "\n")
' "$RESULTS" "$1" "$2" "$3" "$4" "$5" "$GPU_NAME" "$COMMIT" "$CODE_SHA" "$(date -Iseconds)"
}

run_tier2() {
    step 8 "tier 2 sweep"
    local case_name n k first=1 rc log status note
    mkdir -p "$RUN_DIR/tier2_logs"
    while read -r case_name n k; do
        echo "tier 2: $case_name num_games=$n"
        log="$RUN_DIR/tier2_logs/${case_name}_${n}.log"
        rc=0
        status=""
        note=""
        if wait_gpu_idle; then
            tier2_cmd "$case_name" "$n"
            run_child "$log" "${CMD[@]}"
            rc="$CHILD_RC"
            # Isaac Sim start-up crash (owner approved 15 Nov 2026): non-zero exit, no row, and the log never reached
            # the "mass_kg=" line (printed after Isaac started and the scene was built): run the point once more.
            if [ -z "$status" ] && [ "$rc" -ne 0 ] && ! has_row "$case_name" "$n" && ! grep -q '^mass_kg=' "$log" 2>/dev/null; then
                echo "  start-up crash (exit $rc): retrying once"
                mv "$log" "${log%.log}.startup_crash1.log"
                echo "$case_name $n: start-up crash (exit $rc), retried once" >> "$RUN_DIR/retried_points.txt"
                if wait_gpu_idle; then
                    tier2_cmd "$case_name" "$n"
                    run_child "$log" "${CMD[@]}"
                    rc="$CHILD_RC"
                else
                    status="crash"
                    note="gpu busy"
                    rc=-1
                    echo "  GPU busy (60 s wait): $GPU_BUSY"
                    printf 'gpu busy: %s\n' "$GPU_BUSY" >> "$log"
                fi
            fi
        else
            status="crash"
            note="gpu busy"
            rc=-1
            echo "  GPU busy (60 s wait): $GPU_BUSY"
            printf 'gpu busy: %s\n' "$GPU_BUSY" >> "$log"
        fi
        if [ -f "$log" ] && grep -qi 'overflow' "$log"; then
            echo "  log mentions overflow: flagged in $RUN_DIR/overflow_points.txt"
            echo "$case_name $n" >> "$RUN_DIR/overflow_points.txt"
        fi
        if ! has_row "$case_name" "$n" && [ "$rc" -ne 2 ]; then
            if [ -z "$status" ]; then
                if [ -f "$log" ] && grep -qiE 'out of memory|PxgCudaDeviceMemoryAllocator|fail to allocate' "$log"; then
                    status="oom"
                    note="out of memory in log (exit code $rc)"
                else
                    status="crash"
                    note="exit code $rc"
                    [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ] && note="timeout (exit code $rc)" || true
                fi
            fi
            echo "  no row written (exit $rc): appending a $status row ($note)"
            append_crash_row "$case_name" "$n" "$k" "$status" "$note"
        fi
        echo "$case_name $n: exit $rc, ok row: $(has_ok_row "$case_name" "$n" && echo yes || echo no), log $log" >> "$RUN_DIR/tier2.log"
        if [ "$first" -eq 1 ] && ! has_ok_row "$case_name" "$n"; then
            TIER2_STOPPED="tier 2 stopped after its first point ($case_name at $n games left no ok row; exit $rc${note:+, $note}; see $log): the remaining tier 2 points were not run"
            echo "$TIER2_STOPPED"
            return 0
        fi
        first=0
    done < <(tier2_points)
}

write_record() {
    step 9 "record"
    if [ "$TIER1_ONLY" -eq 1 ]; then
        echo "tier 1 only: no record written; results in $RESULTS"
        FINISHED=1
        return 0
    fi
    record_cmd
    local out rc=0
    out="$("${CMD[@]}" 2>&1)" || rc=$?
    echo "$out"
    if [ "$rc" -ne 0 ]; then
        die 1 "make_record failed (exit $rc): no record written"
    fi
    FINISHED=1
    echo "record: records/${NAME}_record.md"
    grep -E '\*\*(PASS|FAIL)\*\*' "records/${NAME}_record.md" | head -n 1 || true
}

# ---------------------------------------------------------------- main

main() {
    step 1 "arguments"
    parse_args "$@"
    step 2 "config hash"
    check_config_hash
    step 3 "no Isaac/AirStack container running"
    check_no_container
    if [ "$DRY_RUN" -eq 0 ]; then
        echo "checking that no other process is using the GPU"
        check_gpu_idle
    fi

    if [ "$DRY_RUN" -eq 1 ]; then
        echo "dry run: nothing below is executed or created"
        dry_run
        exit 0
    fi

    trap on_interrupt INT TERM HUP
    prepare_run_dir
    trap on_exit EXIT
    write_preflight
    run_tests
    run_tier1
    if [ "$TIER1_ONLY" -eq 0 ]; then
        run_tier2
    fi
    write_record
    if [ "$TIER1_ONLY" -eq 1 ] && [ "$TIER1_RC" -ne 0 ]; then
        exit 1
    fi
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then  # sourced by a test: define the functions only
    main "$@"
fi
