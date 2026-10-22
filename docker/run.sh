#!/usr/bin/env bash
# Start (or exec into) the exploration container: GPU, JOINED TO THE ISAAC CONTAINER NETWORK NAMESPACE
# (--network container:isaac-sim) because the Isaac ROS 2 bridge lives on the 172.31.0.0/24 docker network and
# its DDS discovery never reaches host-network containers (verified 2026-10-22). Requires isaac-sim to be up.
# the exploration folder mounted at /exploration. ROS_DOMAIN_ID defaults to 1 (the sim's SVG_DOMAIN_ID).
set -euo pipefail
cd "$(dirname "$0")/.."
NAME=localisation-exploration
DOMAIN=${ROS_DOMAIN_ID:-1}
if docker ps --format '{{.Names}}' | grep -qx "$NAME"; then
  exec docker exec -it -e ROS_DOMAIN_ID="$DOMAIN" "$NAME" bash
fi
docker run -it --rm --name "$NAME" --gpus all --network container:isaac-sim --ipc host \
  -e ROS_DOMAIN_ID="$DOMAIN" -e RMW_IMPLEMENTATION=rmw_fastrtps_cpp \
  -e FASTRTPS_DEFAULT_PROFILES_FILE=/exploration/docker/fastdds.xml -e RERUN=0 \
  -v "$PWD":/exploration \
  -w /exploration \
  localisation-exploration:cu12 bash "$@"
