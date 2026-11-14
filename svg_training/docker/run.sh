#!/usr/bin/env bash
# Run a command (default: an interactive shell) in the training-simulator container.
# Usage: docker/run.sh [--print] [command...]    e.g. docker/run.sh bash scripts/run_s0.sh <name> <sha256>
# --print shows the docker run line and does not start anything.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
IMAGE=svg-training:isaaclab-2.3.2
V=svg-training-isaac  # prefix of the named volumes; same targets as NVIDIA's docker-compose.yaml (user = root)

PRINT=0
if [ "${1:-}" = "--print" ]; then
    PRINT=1
    shift
fi

if [ "$PRINT" -eq 0 ] && ! docker image inspect "$IMAGE" > /dev/null 2>&1; then
    echo "image $IMAGE not found: run docker/build.sh first" >&2
    exit 1
fi

ARGS=(docker run --rm --gpus all --entrypoint bash)
[ -t 0 ] && ARGS+=(-it)
ARGS+=(
    -v "$ROOT:/workspace/svg_training"
    -v "$V-cache-kit:/isaac-sim/kit/cache"
    -v "$V-cache-ov:/root/.cache/ov"
    -v "$V-cache-pip:/root/.cache/pip"
    -v "$V-cache-gl:/root/.cache/nvidia/GLCache"
    -v "$V-cache-compute:/root/.nv/ComputeCache"
    -v "$V-logs:/root/.nvidia-omniverse/logs"
    -v "$V-carb-logs:/isaac-sim/kit/logs/Kit/Isaac-Sim"
    -v "$V-data:/root/.local/share/ov/data"
    -v "$V-docs:/root/Documents"
    -e ACCEPT_EULA=Y -e PRIVACY_CONSENT=Y
    -e PYTHONDONTWRITEBYTECODE=1
    -e "HOST_UID=$(id -u)" -e "HOST_GID=$(id -g)"
)

# The container runs as root. Afterwards everything root created in the mounted project folder is handed back
# to the caller (find -user root, never following symlinks, never leaving the mount), and the command's own
# exit code is kept. The arguments are joined with spaces and run by bash -lc, like ssh does.
INNER='if [ "$#" -eq 0 ]; then set -- bash -i; fi
rc=0
bash -lc "$*" || rc=$?
find /workspace/svg_training -xdev -user root -exec chown -h "$HOST_UID:$HOST_GID" {} + 2>/dev/null || true
exit "$rc"'
ARGS+=("$IMAGE" -c "cd /workspace/svg_training && $INNER" svg-training-run "$@")

if [ "$PRINT" -eq 1 ]; then
    printf '%q ' "${ARGS[@]}"
    echo
    exit 0
fi
exec "${ARGS[@]}"
