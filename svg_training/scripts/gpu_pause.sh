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
# Every pause, resume and stop is appended to the pause log (one JSON line); every hard cap and GPU-hours count of our code subtracts
# the paused time (source/svg_training/nus/pauses.py).
#
# Environment (tests): GPU_PAUSE_PATTERN (extended regular expression on the command line; default: our trainers, scorers and pilots and
# NUS's train.py and eval.py), GPU_PAUSE_LOG (default <svg_training>/runs/nus_port/phase5/pauses.log). Only Python processes match.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATTERN="${GPU_PAUSE_PATTERN:-nus_selfplay_train\.py|nus_phase5_reference\.py|nus_phase5_score\.py|train_standin\.py|nus_pilot_selfplay\.py|ma_skills/scripts/train\.py|ma_skills/scripts/eval\.py}"
LOG="${GPU_PAUSE_LOG:-$HERE/runs/nus_port/phase5/pauses.log}"

jobs_pids() {
  local pid
  for pid in $(pgrep -f -- "$PATTERN" || true); do
    [ "$pid" = "$$" ] && continue
    case "$(ps -o comm= -p "$pid" 2>/dev/null || true)" in
      python*) echo "$pid" ;;
    esac
  done
}

log_event() {  # event, pids...
  local event="$1"; shift
  local list
  list="$(printf '%s,' "$@")"; list="[${list%,}]"
  mkdir -p "$(dirname "$LOG")"
  printf '{"event": "%s", "time": %s, "pids": %s, "by": "%s"}\n' "$event" "$(date +%s.%N)" "$list" "${USER:-unknown}" >> "$LOG"
}

cmd="${1:-status}"
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
