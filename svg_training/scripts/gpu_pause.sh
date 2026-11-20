#!/usr/bin/env bash
# Pause, resume or stop every svg_training / NUS GPU job, so the owner can use the GPU (owner, 18 Nov 2026: this PC is also for games).
#
#   scripts/gpu_pause.sh status     list the jobs (pid, state: T = paused, elapsed, command)
#   scripts/gpu_pause.sh pause      SIGSTOP every job: it keeps its GPU memory (a few GB of the 32) but uses no GPU compute
#   scripts/gpu_pause.sh resume     SIGCONT every job: it carries on where it stopped
#   scripts/gpu_pause.sh stop       SIGINT (then SIGCONT, so a paused job receives it): a full stop that frees the GPU memory
#
# What a stop does to each kind of job, and how to restart it:
#   - our self-play trainer (scripts/nus_selfplay_train.py): checkpoints at the next update boundary and exits (code 4, STOPPED);
#     resume = the SAME command again (it continues from <out>/self_play_state.json; the probe is not repeated).
#   - NUS's own trainer (C0, ma_skills/scripts/train.py through run_nus_job.sh): exits without a new checkpoint; its last checkpoint
#     (every 1,000 updates and at every selection evaluation) is kept, so up to about 1,000 updates are lost. Resume = the job's
#     command (~/nus_jax_runs/<job>.cmd.txt) with `checkpoint_path=<its hydra.run.dir>` added, through run_nus_job.sh under a new job
#     name. Prefer pause for C0.
#   - R0, N0 and scoring (scripts/nus_phase5_reference.py, nus_phase5_score.py): exit; rerun the same command (they take minutes).
#   - pilots (scripts/train_standin.py): see that script's own resume notes.
#   - the STE learning track's jobs (scripts/ste_*.py): checkpoint at the next step boundary and exit (code 4, interrupted); resume =
#     the SAME command again (source/svg_training/ste/run_contract.py).
# Every pause, resume and stop is appended to the pause log (one JSON line); every hard cap and GPU-hours count of our code subtracts
# the paused time (source/svg_training/nus/pauses.py; the STE track: source/svg_training/ste/pauses.py).
#
# Two pause logs, the same line in both (STE track, task L0.7):
#   - the legacy log of this copy's own worktree, <svg_training>/runs/nus_port/phase5/pauses.log (GPU_PAUSE_LOG replaces it): the NUS
#     code of that worktree reads it, as before;
#   - the ONE shared log, the same from every worktree: $SVG_SHARED_DIR/pauses.log if SVG_SHARED_DIR is set, else
#     <main clone>/svg_training/runs/shared/pauses.log (the main clone is the parent of git's common folder; the same rule as
#     source/svg_training/ste/shared.py). If that folder cannot be found the pause still happens and a warning is printed.
#
# Jobs are found from every worktree (by command line, pid file and executable, never by working folder). Environment (tests):
# GPU_PAUSE_PATTERN (extended regular expression on the command line; default: our trainers, scorers, pilots and clip tools, NUS's
# train.py and eval.py, and the STE track's job scripts scripts/ste_*.py), GPU_PAUSE_EXCLUDE (extended regular expression; a process
# found by the pattern whose command line matches it is left alone; default: the STE track's own launcher, wrapper and waiter,
# scripts/ste_job.py, which only watch a job; empty = no exclusion), GPU_PAUSE_PIDDIR (run_nus_job.sh's pid files, default
# ~/nus_jax_runs), GPU_PAUSE_EXE (executables of our conda environments), GPU_PAUSE_LOG (default
# <svg_training>/runs/nus_port/phase5/pauses.log), SVG_SHARED_DIR (the shared folder). Only Python processes match.
#
# Who paused (STE track, L07-C1b): every line's "by" is the user name, so a bare `gpu_pause.sh pause` is the OWNER's pause, and
# the STE launcher refuses to start a job while it is open. The lead (a Claude session) pausing only its own sibling jobs to
# run a solo job (ste_learning/AUTOMATION.md section 2.2) sets GPU_PAUSE_BY=lead (with GPU_PAUSE_PATTERN for those siblings):
# such a pause does not block a launch. GPU_PAUSE_BY: letters, digits, '.', '_', '-' only; empty = the user name.
# A resume or stop with GPU_PAUSE_BY=lead is refused (exit 2, before any signal or line) while an owner pause is open: it would
# continue the owner's jobs and close his pause in the log (L07-C1c; never end a pause the session did not make). The check is
# `scripts/ste_job.py owner-pauses`, run with GPU_PAUSE_PYTHON (default python3); if it cannot run, the lead's command is
# refused too. A bare resume or stop (the owner's) runs no check and works as before.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATTERN="${GPU_PAUSE_PATTERN:-nus_selfplay_train\.py|nus_phase5_reference\.py|nus_phase5_score\.py|train_standin\.py|nus_pilot_selfplay\.py|nus_isaac_clips\.py|make_s2b_video\.py|ma_skills/scripts/train\.py|ma_skills/scripts/eval\.py|scripts/ste_[a-z0-9_]+\.py}"
# The STE track's launcher, wrapper and waiter (scripts/ste_job.py launch | _run | wait) are named like its jobs but only watch one: a
# stopped wrapper could not record its job's exit code, and an interrupted one would lose it. They are never paused or stopped.
EXCLUDE="${GPU_PAUSE_EXCLUDE-scripts/ste_job\.py}"
# NUS's trainer renames its process (its command line no longer names the script), so two more routes find jobs: the live pids in
# run_nus_job.sh's pid files, and every GPU compute process whose executable is the python of our own conda environments (nus_jax,
# env_isaaclab; never Isaac Sim's kit python, which is the AirStack simulator, and never a game).
PIDDIR="${GPU_PAUSE_PIDDIR:-$HOME/nus_jax_runs}"
EXE="${GPU_PAUSE_EXE:-/miniconda3/envs/(nus_jax|env_isaaclab)/bin/python}"
LOG="${GPU_PAUSE_LOG:-$HERE/runs/nus_port/phase5/pauses.log}"
BY="${GPU_PAUSE_BY:-${USER:-unknown}}"                        # unset or empty: the user name, as before
if [ -n "${GPU_PAUSE_BY:-}" ] && [[ ! "$GPU_PAUSE_BY" =~ ^[A-Za-z0-9._-]+$ ]]; then    # it goes into a JSON line as it is
  echo "GPU_PAUSE_BY must be letters, digits, '.', '_' or '-' only, got '$GPU_PAUSE_BY': nothing was done" >&2
  exit 2
fi

shared_log() {  # the one shared pause log (header); prints nothing when the shared folder cannot be found
  local common
  if [ -n "${SVG_SHARED_DIR:-}" ]; then printf '%s\n' "$SVG_SHARED_DIR/pauses.log"; return 0; fi
  # git prints the common folder as a relative ".git" in the main clone and as an absolute path in a worktree
  common="$(cd "$HERE" && git rev-parse --git-common-dir 2>/dev/null)" || return 0
  common="$(cd "$HERE" && cd "$common" 2>/dev/null && pwd -P)" || return 0
  printf '%s\n' "$(dirname "$common")/svg_training/runs/shared/pauses.log"
}

is_python() {  # a live Python process (the executable, not the renamable command line)
  local exe
  exe="$(readlink -f "/proc/$1/exe" 2>/dev/null || true)"
  case "$(basename "${exe:-none}")" in python*) return 0 ;; esac
  return 1
}

is_tooling() {  # the command line matches GPU_PAUSE_EXCLUDE (the STE track's launcher, wrapper or waiter)
  local args
  [ -n "$EXCLUDE" ] || return 1
  args="$(tr '\0' ' ' < "/proc/$1/cmdline" 2>/dev/null)" || return 1
  [[ "$args" =~ $EXCLUDE ]]          # no pipe: with pipefail a reader that stops early would turn a match into a miss
}

jobs_pids() {
  local pid exe f
  {
    for pid in $(pgrep -f -- "$PATTERN" || true); do
      [ "$pid" = "$$" ] || ! is_python "$pid" || is_tooling "$pid" || echo "$pid"
    done
    for f in "$PIDDIR"/*.pid; do
      [ -f "$f" ] || continue
      pid="$(tr -dc '0-9' < "$f")"
      exe="$(readlink -f "/proc/${pid:-0}/exe" 2>/dev/null || true)"   # a reused pid of another program is not ours
      [ -n "$pid" ] && [ -n "$exe" ] && printf '%s' "$exe" | grep -q -E -- "$EXE" && echo "$pid"
    done
    for pid in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -dc '0-9\n' || true); do
      exe="$(readlink -f "/proc/$pid/exe" 2>/dev/null || true)"
      [ -n "$exe" ] && printf '%s' "$exe" | grep -q -E -- "$EXE" && echo "$pid"
    done
  } | sort -un
  return 0
}

log_event() {  # event, pids...
  local event="$1"; shift
  local list line shared
  list="$(printf '%s,' "$@")"; list="[${list%,}]"
  # one line, built once (one clock reading): the same text goes to both logs, so a reader of both counts the event once
  line="$(printf '{"event": "%s", "time": %s, "pids": %s, "by": "%s"}' "$event" "$(date +%s.%N)" "$list" "$BY")"
  mkdir -p "$(dirname "$LOG")"
  printf '%s\n' "$line" >> "$LOG"
  shared="$(shared_log)"
  if [ -z "$shared" ]; then
    echo "warning: the shared pause log was not written (not inside a git repository and SVG_SHARED_DIR is not set); legacy log: $LOG" >&2
  elif [ "$(readlink -m -- "$shared")" != "$(readlink -m -- "$LOG")" ]; then
    { mkdir -p "$(dirname "$shared")" && printf '%s\n' "$line" >> "$shared"; } \
      || echo "warning: the shared pause log $shared could not be written; legacy log: $LOG" >&2
  fi
}

cmd="${1:-status}"
if [ "${GPU_PAUSE_BY:-}" = "lead" ] && { [ "$cmd" = "resume" ] || [ "$cmd" = "stop" ]; }; then
  set +e
  owners="$(env -u PYTHONPATH "${GPU_PAUSE_PYTHON:-python3}" "$HERE/scripts/ste_job.py" owner-pauses 2>&1)"
  rc=$?
  set -e
  if [ "$rc" -eq 2 ]; then
    echo "refused: the lead may not $cmd while an owner pause is open (it would end his pause too); nothing was done:" >&2
    printf '%s\n' "$owners" >&2
    exit 2
  elif [ "$rc" -ne 0 ]; then
    echo "refused: could not check for an open owner pause (exit $rc); nothing was done:" >&2
    printf '%s\n' "$owners" >&2
    exit 2
  fi
fi
mapfile -t PIDS < <(jobs_pids)
case "$cmd" in
  status)
    if [ "${#PIDS[@]}" -eq 0 ]; then echo "no GPU job of ours or NUS's is running"; exit 0; fi
    ps -o pid=,stat=,etime=,args= -p "$(IFS=,; echo "${PIDS[*]}")" | cut -c1-200
    ;;
  pause)
    for pid in "${PIDS[@]}"; do kill -STOP "$pid"; done
    log_event pause "${PIDS[@]}"
    echo "paused ${#PIDS[@]} job(s): ${PIDS[*]:-none}. They keep their GPU memory but use no GPU compute. Resume: $0 resume"
    ;;
  resume)
    for pid in "${PIDS[@]}"; do kill -CONT "$pid"; done
    log_event resume "${PIDS[@]}"
    echo "resumed ${#PIDS[@]} job(s): ${PIDS[*]:-none}"
    ;;
  stop)
    for pid in "${PIDS[@]}"; do kill -INT "$pid"; kill -CONT "$pid"; done
    log_event stop "${PIDS[@]}"
    echo "stopped ${#PIDS[@]} job(s): ${PIDS[*]:-none}."
    echo "To resume: our trainer - rerun the same command; NUS's C0 job - its ~/nus_jax_runs/<job>.cmd.txt command with"
    echo "checkpoint_path=<its hydra.run.dir> through run_nus_job.sh; R0/N0/scoring - rerun the same command (header of this script)."
    ;;
  *)
    echo "usage: $0 {status|pause|resume|stop}" >&2
    exit 2
    ;;
esac
