#!/usr/bin/env bash
# Start the long-lived exploration container (detached) if it is not running: GPU, joined to the
# isaac-sim network namespace, X11 for Foxglove Studio / rviz, the exploration folder at /exploration.
set -euo pipefail
cd "$(dirname "$0")/.."
NAME=localisation-exploration
docker ps --format '{{.Names}}' | grep -qx isaac-sim || { echo "isaac-sim container is not up — run tools/sim_terminals.sh (or ./airstack.sh up) first"; exit 1; }
if docker ps --format '{{.Names}}' | grep -qx "$NAME"; then echo "$NAME already running"; exit 0; fi
docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" --gpus all --network container:isaac-sim --ipc host \
  -e ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-1}" -e RMW_IMPLEMENTATION=rmw_fastrtps_cpp \
  -e FASTRTPS_DEFAULT_PROFILES_FILE=/exploration/docker/fastdds.xml -e RERUN=0 \
  -e DISPLAY="${DISPLAY:-:1}" -e QT_X11_NO_MITSHM=1 -e XAUTHORITY=/.Xauthority -e NVIDIA_DRIVER_CAPABILITIES=all \
  -v "$HOME/.Xauthority:/.Xauthority:ro" -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v "$PWD":/exploration -w /exploration \
  localisation-exploration:cu12 sleep infinity >/dev/null
echo "$NAME started"
