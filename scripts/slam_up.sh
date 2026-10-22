#!/usr/bin/env bash
# One command for the SLAM side of a sim session (run on the laptop AFTER the sim says "Ready for takeoff" x3):
#   1. exploration container up (joined to the Isaac network)
#   2. cuVSLAM node        -> log results/cuvslam_node.log
#   3. Foxglove bridge     -> ws://172.31.0.200:8766, log results/foxglove_bridge.log
#   4. Foxglove Studio (its OWN instance, data dir foxglove/studio-data) pre-connected to that bridge.
#      First time only: Layouts -> Import from file -> /exploration/foxglove/cuvslam_slam_view.json. Remembered after that.
# Stop everything with scripts/slam_down.sh. Status: scripts/slam_status.sh
set -euo pipefail
cd "$(dirname "$0")/.."
./docker/up.sh
C=localisation-exploration
ex() { docker exec -w /exploration "$C" bash -lc "$*" 2>&1 | grep -v '^Sourcing'; }
exd() { docker exec -d -w /exploration "$C" bash -lc "$*"; }

if ! ex 'pgrep -f "[c]uvslam_stereo_node.py" >/dev/null'; then
  exd 'python3 -u nodes/cuvslam_stereo_node.py > results/cuvslam_node.log 2>&1'
  echo "cuVSLAM node started (results/cuvslam_node.log)"
else echo "cuVSLAM node already running"; fi

if ! ex 'pgrep -f "[f]oxglove_bridge.*8766" >/dev/null'; then
  exd 'scripts/foxglove_bridge_isaac.sh > results/foxglove_bridge.log 2>&1'
  echo "Foxglove bridge started on ws://172.31.0.200:8766 (results/foxglove_bridge.log)"
else echo "Foxglove bridge already running"; fi

for i in $(seq 1 20); do ex 'grep -q "tracker ready" results/cuvslam_node.log' && break; sleep 1; done
ex 'grep -m1 "tracker ready" results/cuvslam_node.log || echo "node not ready yet — is the sim playing with ENABLE_CAMERA=true CAMERA_DRONES=drone_1 ?"'

if ! ex 'pgrep -f "[f]oxglove-studio.*studio-data" >/dev/null'; then
  exd 'foxglove-studio --no-sandbox --user-data-dir=/exploration/foxglove/studio-data "foxglove://open?ds=foxglove-websocket&ds.url=ws://172.31.0.200:8766" > results/foxglove_studio.log 2>&1'
  echo "Foxglove Studio (SLAM instance) opening, connected to ws://172.31.0.200:8766"
  [ -n "$(ls -A foxglove/studio-data 2>/dev/null)" ] || echo "FIRST TIME: in that window do Layouts -> Import from file -> /exploration/foxglove/cuvslam_slam_view.json (remembered afterwards)"
else echo "Foxglove Studio (SLAM instance) already open"; fi
