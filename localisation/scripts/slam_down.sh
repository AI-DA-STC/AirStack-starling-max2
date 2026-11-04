#!/usr/bin/env bash
# Stop the SLAM side: Studio instance, bridge, node, and the exploration container.
set -euo pipefail
C=localisation-exploration
# the Basestation auto grid lives in the robot container (the exploration copy dies with its container); absent is fine
docker exec airstack-robot-desktop-1 pkill -TERM -f 'svg_grid/auto_grid\.py' >/dev/null 2>&1 || true
docker ps --format '{{.Names}}' | grep -qx "$C" || { echo "$C not running"; exit 0; }
docker exec "$C" bash -c 'pkill -INT -f "foxglove-studio.*studio-data"; pkill -INT -f "ros2 bag record"; pkill -INT -f foxglove_bridge; pkill -INT -f cuvslam_stereo_node.py; sleep 2' || true
docker rm -f "$C" >/dev/null && echo "$C stopped"
