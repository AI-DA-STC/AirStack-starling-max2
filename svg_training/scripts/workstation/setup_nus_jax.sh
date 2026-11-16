#!/usr/bin/env bash
# Make a separate conda env for a partner's JAX training code and run its CPU tests (docs/WORKSTATION_SETUP.md).
# UNTESTED ON THE 5090: written and checked on the laptop with `bash -n` and --dry-run only (2026-11-17).
#
#   scripts/workstation/setup_nus_jax.sh [--dry-run] [--env NAME] [--skip-gpu-check] <path-to-partner-repo>
#   scripts/workstation/setup_nus_jax.sh --help
#
# The partner's code is not in this repository: unpack it from the private bundle first (its NOTES say where).
# This script only installs it, in its own env, away from Isaac Lab's:
#   1 conda env `nus_jax`, Python 3.12 (stops if it already exists)
#   2 PYTHONNOUSERSITE=1 pip install -e '<path>[cuda13,test]' matplotlib
#       (PYTHONNOUSERSITE=1 keeps packages in ~/.local out of the env; on the laptop they leaked in without it)
#   3 the partner's own tests on the CPU: JAX_PLATFORMS=cpu pytest -q, from the partner folder
#   4 JAX lists its devices (uses the GPU for a moment; skip with --skip-gpu-check)
# Their logging service is never used: run jobs with run_nus_job.sh, which switches it off.
#
# Exit codes: 0 installed and the tests passed; 1 a step failed; 2 bad argument or no such folder;
#             3 conda not found; 4 the env already exists;
#             5 installed, but some partner tests failed: compare with the result the bundle's NOTES expect.
set -euo pipefail

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; }

DRY=0
ENV_NAME=nus_jax
GPU_CHECK=1
REPO=""
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY=1 ;;
        --env) ENV_NAME="${2:?--env needs a name}"; shift ;;
        --skip-gpu-check) GPU_CHECK=0 ;;
        -h|--help) usage; exit 0 ;;
        -*) echo "unknown argument: $1 (see --help)" >&2; exit 2 ;;
        *) [ -z "$REPO" ] || { echo "one folder only (got '$REPO' and '$1')" >&2; exit 2; }; REPO="$1" ;;
    esac
    shift
done
[ -n "$REPO" ] || { echo "give the partner's repository folder (see --help)" >&2; exit 2; }

if [ -d "$REPO" ]; then
    REPO="$(cd "$REPO" && pwd)"
    if [ ! -f "$REPO/setup.py" ] && [ ! -f "$REPO/pyproject.toml" ]; then
        echo "$REPO has no setup.py or pyproject.toml: is it the partner's repository folder?" >&2
        exit 2
    fi
elif [ "$DRY" -eq 1 ]; then
    echo "(dry run: $REPO does not exist yet; unpack the bundle before the real run)"
else
    echo "no such folder: $REPO (unpack the private bundle first)" >&2
    exit 2
fi

run() {   # print a command, then run it unless this is a dry run
    printf '+'; printf ' %q' "$@"; echo
    [ "$DRY" -eq 1 ] || "$@"
}

CONDA="$(command -v conda 2>/dev/null || true)"
[ -z "$CONDA" ] && [ -x "$HOME/miniconda3/bin/conda" ] && CONDA="$HOME/miniconda3/bin/conda"
if [ -n "$CONDA" ]; then
    CONDA_BASE="$("$CONDA" info --base)"
elif [ "$DRY" -eq 1 ]; then
    CONDA="$HOME/miniconda3/bin/conda"
    CONDA_BASE="$HOME/miniconda3"
    echo "(dry run: conda not found; assuming $CONDA_BASE)"
else
    echo "conda not found: install Miniconda first (https://docs.anaconda.com/miniconda/)" >&2
    exit 3
fi
PY="$CONDA_BASE/envs/$ENV_NAME/bin/python"
export PYTHONNOUSERSITE=1

echo "env: $ENV_NAME   python: $PY   code: $REPO"
[ "$DRY" -eq 1 ] && echo "DRY RUN: commands are printed, nothing is run or written."

echo; echo "== 1/4 conda env $ENV_NAME (Python 3.12)"
if [ "$DRY" -eq 0 ] && [ -d "$CONDA_BASE/envs/$ENV_NAME" ]; then
    echo "env $ENV_NAME already exists: stopping (remove it yourself, or use --env)" >&2
    exit 4
fi
run "$CONDA" create -y -n "$ENV_NAME" python=3.12

echo; echo "== 2/4 install the partner's code, editable, with CUDA 13 JAX and the test extras"
run env PYTHONNOUSERSITE=1 "$PY" -m pip install --upgrade pip
run env PYTHONNOUSERSITE=1 "$PY" -m pip install -e "$REPO[cuda13,test]" matplotlib

echo; echo "== 3/4 the partner's tests on the CPU"
echo "+ cd $REPO && PYTHONNOUSERSITE=1 JAX_PLATFORMS=cpu $PY -m pytest -q"
TESTS_OK=1
if [ "$DRY" -eq 0 ]; then
    (cd "$REPO" && PYTHONNOUSERSITE=1 JAX_PLATFORMS=cpu "$PY" -m pytest -q) || TESTS_OK=0
fi

echo; echo "== 4/4 JAX devices"
if [ "$GPU_CHECK" -eq 1 ]; then
    run env PYTHONNOUSERSITE=1 "$PY" -c 'import jax; print(jax.__version__, jax.devices())'
else
    echo "skipped (--skip-gpu-check)"
fi

if [ "$TESTS_OK" -eq 0 ]; then
    echo
    echo "installed, but some partner tests failed: compare with the result the bundle's NOTES expect" >&2
    exit 5
fi
echo
echo "done. Start jobs with scripts/workstation/run_nus_job.sh (see --help)."
