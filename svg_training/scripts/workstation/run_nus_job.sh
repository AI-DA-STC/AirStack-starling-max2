#!/usr/bin/env bash
# Start one job of a partner's JAX trainer in the background, with a log (docs/WORKSTATION_SETUP.md).
# UNTESTED ON THE 5090: written and checked on the laptop with `bash -n` and --dry-run only (2026-11-17).
#
#   scripts/workstation/run_nus_job.sh [options] <partner-repo> <job-name> <trainer.py> [hydra overrides...]
#
#   <partner-repo>   the partner's code folder, unpacked from the private bundle
#   <job-name>       letters, digits, '.', '_' or '-'; names the log, e.g. 2026-11-18_guard_seed1
#   <trainer.py>     the script to run, relative to <partner-repo>
#   overrides        passed through unchanged (config name, team, step budget, ...). The values used so far are
#                    in the private bundle's NOTES, never in this repository.
#
# Always set, whatever the overrides say:
#   PYTHONNOUSERSITE=1                    packages in ~/.local stay out
#   WANDB_MODE=disabled, use_wandb=False  no cloud logging, ever
#   XLA_PYTHON_CLIENT_PREALLOCATE=false   JAX takes GPU memory as it needs it ...
#   XLA_PYTHON_CLIENT_MEM_FRACTION=<f>    ... up to this share of the GPU (also passed as jax.preallocate=false
#                                         jax.memory_fraction=<f>; --no-jax-overrides leaves those two out)
#
# Options:
#   --mem-fraction F    GPU memory share, default 0.60 (the 5090 is not shared with a simulator; the laptop used 0.30)
#   --env NAME          conda env, default nus_jax
#   --log-dir DIR       default ~/nus_jax_runs; writes <job>.log, <job>.pid and <job>.cmd.txt (refuses to overwrite)
#   --foreground        run in this terminal instead of the background (inside tmux)
#   --allow-shared-gpu  start even if another process holds more than 1024 MiB of GPU memory
#   --no-jax-overrides  do not append the two jax.* overrides (the environment variables are still set)
#   --dry-run           print what would run; run and write nothing
#
# Watch:  tail -f <log-dir>/<job>.log      Stop:  kill $(cat <log-dir>/<job>.pid)
#
# Exit codes: 0 started (or finished, with --foreground and success); 1 the job failed (--foreground);
#             2 bad argument or missing folder/script; 3 the env is missing; 6 the log already exists;
#             11 the GPU is in use (see --allow-shared-gpu).
set -euo pipefail

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; }

DRY=0
FOREGROUND=0
ALLOW_SHARED=0
JAX_OVERRIDES=1
MEM=0.60
ENV_NAME=nus_jax
LOG_DIR="$HOME/nus_jax_runs"
GPU_MIB_MAX=1024   # owner, 18 Nov 2026: same as isaac_preflight.sh; the 5090's remote-desktop daemon (546-589 MiB) passes
POS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY=1 ;;
        --foreground) FOREGROUND=1 ;;
        --allow-shared-gpu) ALLOW_SHARED=1 ;;
        --no-jax-overrides) JAX_OVERRIDES=0 ;;
        --mem-fraction) MEM="${2:?--mem-fraction needs a number}"; shift ;;
        --env) ENV_NAME="${2:?--env needs a name}"; shift ;;
        --log-dir) LOG_DIR="${2:?--log-dir needs a folder}"; shift ;;
        -h|--help) usage; exit 0 ;;
        --) shift; POS+=("$@"); break ;;
        -*) if [ ${#POS[@]} -ge 3 ]; then POS+=("$1"); else echo "unknown option: $1 (see --help)" >&2; exit 2; fi ;;
        *) POS+=("$1") ;;
    esac
    shift
done
if [ ${#POS[@]} -lt 3 ]; then
    echo "need <partner-repo> <job-name> <trainer.py> (see --help)" >&2
    exit 2
fi
REPO="${POS[0]}"; JOB="${POS[1]}"; TRAINER="${POS[2]}"
OVERRIDES=("${POS[@]:3}")

[[ "$JOB" =~ ^[A-Za-z0-9._-]+$ ]] && [ "$JOB" != "." ] && [ "$JOB" != ".." ] \
    || { echo "job name '$JOB': use letters, digits, '.', '_' or '-'" >&2; exit 2; }
awk -v f="$MEM" 'BEGIN { exit !(f + 0 > 0 && f + 0 <= 0.95) }' \
    || { echo "--mem-fraction '$MEM' must be above 0 and at most 0.95" >&2; exit 2; }
if [ "$DRY" -eq 0 ]; then
    [ -d "$REPO" ] || { echo "no such folder: $REPO" >&2; exit 2; }
    [ -f "$REPO/$TRAINER" ] || { echo "no such script: $REPO/$TRAINER" >&2; exit 2; }
fi

CONDA="$(command -v conda 2>/dev/null || true)"
[ -z "$CONDA" ] && [ -x "$HOME/miniconda3/bin/conda" ] && CONDA="$HOME/miniconda3/bin/conda"
if [ -n "$CONDA" ]; then
    PY="$("$CONDA" info --base)/envs/$ENV_NAME/bin/python"
else
    PY="$HOME/miniconda3/envs/$ENV_NAME/bin/python"
fi
if [ "$DRY" -eq 0 ] && [ ! -x "$PY" ]; then
    echo "no python at $PY: run setup_nus_jax.sh first" >&2
    exit 3
fi

LOG="$LOG_DIR/$JOB.log"
PIDF="$LOG_DIR/$JOB.pid"
CMDF="$LOG_DIR/$JOB.cmd.txt"
ENVV=(PYTHONNOUSERSITE=1 WANDB_MODE=disabled XLA_PYTHON_CLIENT_PREALLOCATE=false "XLA_PYTHON_CLIENT_MEM_FRACTION=$MEM")
CMD=("$PY" "$TRAINER" "${OVERRIDES[@]}" use_wandb=False)
[ "$JAX_OVERRIDES" -eq 1 ] && CMD+=(jax.preallocate=false "jax.memory_fraction=$MEM")

echo "job:  $JOB"
echo "dir:  $REPO"
echo "log:  $LOG"
echo "+ cd $REPO && env ${ENVV[*]} ${CMD[*]}"
if [ "$DRY" -eq 1 ]; then
    echo "DRY RUN: nothing started, nothing written. A real run first checks nvidia-smi for other GPU users."
    exit 0
fi

if [ -e "$LOG" ]; then
    echo "$LOG already exists: pick a new job name (a log is never overwritten)" >&2
    exit 6
fi
if [ "$ALLOW_SHARED" -eq 0 ] && command -v nvidia-smi > /dev/null 2>&1; then
    BUSY="$(nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits 2>/dev/null \
            | awk -F', ' -v m="$GPU_MIB_MAX" '$3 + 0 > m')"
    if [ -n "$BUSY" ]; then
        echo "the GPU is in use (more than $GPU_MIB_MAX MiB):" >&2
        printf '%s\n' "$BUSY" >&2
        echo "stop those first, or pass --allow-shared-gpu" >&2
        exit 11
    fi
fi

mkdir -p "$LOG_DIR"
{
    echo "started $(date -Is) on $(hostname)"
    echo "cd $REPO && env ${ENVV[*]} ${CMD[*]}"
} > "$CMDF"
cd "$REPO"
if [ "$FOREGROUND" -eq 1 ]; then
    echo "running in the foreground; output also goes to the log"
    set +e
    env "${ENVV[@]}" "${CMD[@]}" 2>&1 | tee "$LOG"
    STATUS="${PIPESTATUS[0]}"
    [ "$STATUS" -eq 0 ] || { echo "job exited with $STATUS" >&2; exit 1; }
    exit 0
fi
nohup env "${ENVV[@]}" "${CMD[@]}" > "$LOG" 2>&1 < /dev/null &
echo "$!" > "$PIDF"
echo "started, pid $(cat "$PIDF")"
echo "watch: tail -f $LOG"
echo "stop:  kill \$(cat $PIDF)"
