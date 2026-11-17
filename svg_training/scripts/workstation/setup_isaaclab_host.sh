#!/usr/bin/env bash
# Rebuild the laptop's host set-up for Isaac Lab on a workstation (docs/GETTING_STARTED.md step 5, host route).
# UNTESTED ON THE 5090: written and checked on the laptop with `bash -n` and --dry-run only (2026-11-17).
#
#   scripts/workstation/setup_isaaclab_host.sh [--dry-run] [--env NAME] [--isaaclab-dir DIR]
#                                              [--isaaclab-ref REF] [--skip-tests] [--help]
#
# What it builds (versions MEASURED on the laptop, 2026-11-17):
#   conda env `env_isaaclab` with Python 3.11; PyTorch 2.7.0 built for CUDA 12.8 (the RTX 5090 needs a CUDA 12.8+
#   build); Isaac Sim 5.1.0 from pip; Isaac Lab cloned to ~/IsaacLab and installed with its own `isaaclab.sh
#   --install`; then the pins in env_isaaclab_requirements.txt (skrl 2.1.0 and the rest).
# Why the host and not only the container: the S2b stand-in trainer needs skrl 2.x; the container image has 1.4.3.
#
# Isaac Lab version: --isaaclab-ref defaults to the tag v2.3.2. The laptop runs v2.3.2 plus 25 commits
# (f73c331738; none touch code tier 2 uses). To match the laptop exactly, pass --isaaclab-ref f73c331738.
# An existing --isaaclab-dir is never changed: the script stops if it is not at the requested commit.
#
# Steps, in order (each is printed before it runs; --dry-run prints them and runs nothing):
#   1 create the conda env (stops if it already exists)   2 PyTorch cu128   3 Isaac Sim 5.1.0
#   4 clone Isaac Lab at the ref                            5 isaaclab.sh --install
#   6 the pinned requirements                               7 version check (prints the GPU PyTorch sees)
#   8 compare with the laptop's package list                9 svg_training's CPU tests (skip: --skip-tests)
# The first Isaac Sim start asks you to accept NVIDIA's licence: read it and answer yes. This script does not
# accept it for you.
#
# Exit codes: 0 done; 1 a step failed (the failing command is the last one printed); 2 bad argument;
#             3 conda not found; 4 the env already exists; 5 the Isaac Lab folder exists at another commit.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SVG="$(cd "$HERE/../.." && pwd)"
REQS="$HERE/env_isaaclab_requirements.txt"
LAPTOP_FREEZE="$HERE/env_isaaclab_freeze_laptop.txt"
ISAACLAB_URL="https://github.com/isaac-sim/IsaacLab.git"
TORCH_INDEX="https://download.pytorch.org/whl/cu128"
NVIDIA_INDEX="https://pypi.nvidia.com"

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; }

DRY=0
ENV_NAME=env_isaaclab
ISAACLAB_DIR="$HOME/IsaacLab"
ISAACLAB_REF=v2.3.2
SKIP_TESTS=0
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY=1 ;;
        --env) ENV_NAME="${2:?--env needs a name}"; shift ;;
        --isaaclab-dir) ISAACLAB_DIR="${2:?--isaaclab-dir needs a path}"; shift ;;
        --isaaclab-ref) ISAACLAB_REF="${2:?--isaaclab-ref needs a tag or commit}"; shift ;;
        --skip-tests) SKIP_TESTS=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown argument: $1 (see --help)" >&2; exit 2 ;;
    esac
    shift
done

say() { echo; echo "== $*"; }
run() {   # print a command, then run it unless this is a dry run
    printf '+'; printf ' %q' "$@"; echo
    [ "$DRY" -eq 1 ] || "$@"
}

# conda: found on PATH or in ~/miniconda3. A dry run goes on without it and prints the default place.
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
PIP=("$PY" -m pip)

echo "env: $ENV_NAME   python: $PY"
echo "Isaac Lab: $ISAACLAB_DIR at $ISAACLAB_REF"
[ "$DRY" -eq 1 ] && echo "DRY RUN: commands are printed, nothing is run or written."

say "1/9 conda env $ENV_NAME (Python 3.11)"
if [ "$DRY" -eq 0 ] && [ -d "$CONDA_BASE/envs/$ENV_NAME" ]; then
    echo "env $ENV_NAME already exists at $CONDA_BASE/envs/$ENV_NAME: stopping (remove it yourself, or use --env)" >&2
    exit 4
fi
run "$CONDA" create -y -n "$ENV_NAME" python=3.11

say "2/9 PyTorch 2.7.0 for CUDA 12.8"
run "${PIP[@]}" install --upgrade pip
run "${PIP[@]}" install torch==2.7.0+cu128 torchvision==0.22.0+cu128 torchaudio==2.7.0 --index-url "$TORCH_INDEX"

say "3/9 Isaac Sim 5.1.0 (pip; about 15 GB of downloads)"
run "${PIP[@]}" install "isaacsim[all,extscache]==5.1.0" --extra-index-url "$NVIDIA_INDEX"

say "4/9 Isaac Lab at $ISAACLAB_REF"
if [ -d "$ISAACLAB_DIR/.git" ]; then
    WANT="$(git -C "$ISAACLAB_DIR" rev-parse --verify --quiet "$ISAACLAB_REF^{commit}" || true)"
    HAVE="$(git -C "$ISAACLAB_DIR" rev-parse HEAD)"
    if [ "$DRY" -eq 1 ] && { [ -z "$WANT" ] || [ "$WANT" != "$HAVE" ]; }; then
        echo "NOTE: $ISAACLAB_DIR exists at $(git -C "$ISAACLAB_DIR" describe --tags --always), not $ISAACLAB_REF:"
        echo "      a real run would stop here (exit 5) and change nothing. Move it or pass --isaaclab-dir."
    elif [ -z "$WANT" ] || [ "$WANT" != "$HAVE" ]; then
        echo "$ISAACLAB_DIR exists at $(git -C "$ISAACLAB_DIR" describe --tags --always), not $ISAACLAB_REF." >&2
        echo "This script never changes an existing Isaac Lab folder: move it or pass --isaaclab-dir." >&2
        exit 5
    else
        echo "$ISAACLAB_DIR is already at $ISAACLAB_REF: not cloned again"
    fi
elif [ -e "$ISAACLAB_DIR" ]; then
    echo "$ISAACLAB_DIR exists and is not a git clone: a real run stops here (exit 5)" >&2
    [ "$DRY" -eq 1 ] || exit 5
else
    run git clone "$ISAACLAB_URL" "$ISAACLAB_DIR"
    run git -C "$ISAACLAB_DIR" checkout --detach "$ISAACLAB_REF"
fi

say "5/9 isaaclab.sh --install (Isaac Lab's own installer, inside the env)"
run "$CONDA" run --no-capture-output -n "$ENV_NAME" bash -c "cd '$ISAACLAB_DIR' && ./isaaclab.sh --install"

say "6/9 pinned packages (env_isaaclab_requirements.txt; these win over what step 5 picked)"
run "${PIP[@]}" install -r "$REQS"

say "7/9 versions (uses the GPU for a moment; importing Isaac Sim may ask you to accept NVIDIA's licence: answer it)"
run "$PY" -c 'import torch, skrl, isaacsim; print("torch", torch.__version__, "cuda", torch.version.cuda); print("gpu", torch.cuda.is_available() and torch.cuda.get_device_name(0)); print("skrl", skrl.__version__)'

say "8/9 compare with the laptop's package list (differences only; information, not a failure)"
echo "+ $PY -m pip freeze | diff <laptop list without comments> -"
if [ "$DRY" -eq 0 ]; then
    diff <(grep -v '^#' "$LAPTOP_FREEZE" | sort) <("$PY" -m pip freeze | grep -v '^-e ' | sort) || true
fi

say "9/9 svg_training CPU tests"
if [ "$SKIP_TESTS" -eq 1 ]; then
    echo "skipped (--skip-tests)"
else
    echo "+ cd $SVG && $PY -m pytest -q"
    if [ "$DRY" -eq 0 ]; then
        (cd "$SVG" && "$PY" -m pytest -q)
    fi
fi

echo
echo "done. Next: docs/GETTING_STARTED.md step 5 hand fixes, then steps 6-7 (Isaac runs start with scripts/isaac_preflight.sh, headless)."
