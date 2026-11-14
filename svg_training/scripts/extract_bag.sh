#!/usr/bin/env bash
# Bag -> CSV inside CMU's robot image (it has ROS 2 jazzy + rosbag2_py; the host has neither).
# Usage: bash scripts/extract_bag.sh <bag_dir> <out_dir> [bag_to_csv.py options, e.g. --drone drone_1]
# The bag is mounted read-only; out_dir must be absent or empty. Files come back owned by the caller.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${SVG_ROBOT_IMAGE:-airlab-docker.andrew.cmu.edu/airstack/airstack:v0.18.0_robot-x86-64_dev}"
if [ "$#" -lt 2 ]; then
    echo "Usage: bash scripts/extract_bag.sh <bag_dir> <out_dir> [bag_to_csv.py options]" >&2
    exit 64
fi
BAG="$(cd "$1" && pwd)"
OUT_ARG="$2"
shift 2
if [ -e "$OUT_ARG" ] && { [ ! -d "$OUT_ARG" ] || [ -n "$(ls -A "$OUT_ARG")" ]; }; then
    echo "extract_bag.sh: output folder $OUT_ARG is not empty; refusing" >&2
    exit 1
fi
mkdir -p "$OUT_ARG"
OUT="$(cd "$OUT_ARG" && pwd)"

INNER='source /opt/ros/jazzy/setup.bash
rc=0
python3 /scripts/bag_to_csv.py /bag /out --bag-label "$BAG_LABEL" "$@" || rc=$?
find /out -xdev -user root -exec chown -h "$HOST_UID:$HOST_GID" {} + 2>/dev/null || true
exit "$rc"'
docker run --rm --entrypoint bash \
    -e "HOST_UID=$(id -u)" -e "HOST_GID=$(id -g)" -e PYTHONDONTWRITEBYTECODE=1 -e "BAG_LABEL=$BAG" \
    -v "$BAG:/bag:ro" -v "$OUT:/out" -v "$ROOT/scripts/bag_to_csv.py:/scripts/bag_to_csv.py:ro" \
    "$IMAGE" -c "$INNER" extract-bag "$@"
