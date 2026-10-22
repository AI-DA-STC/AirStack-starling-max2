#!/usr/bin/env bash
# Stop the SLAM side: Studio instance, bridge, node, and the exploration container.
set -euo pipefail
C=localisation-exploration
docker ps --format '{{.Names}}' | grep -qx "$C" || { echo "$C not running"; exit 0; }
docker exec "$C" bash -c 'pkill -INT -f "foxglove-studio.*studio-data"; pkill -INT -f "ros2 bag record"; pkill -INT -f foxglove_bridge; pkill -INT -f cuvslam_stereo_node.py; sleep 2' || true
docker rm -f "$C" >/dev/null && echo "$C stopped"
