#!/usr/bin/env bash
# One command for the SLAM side of a sim session (run on the laptop AFTER the sim says "Ready for takeoff" x3):
#   1. exploration container up (joined to the Isaac network)
#   2. cuVSLAM node        -> log results/cuvslam_node.log
#   3. Foxglove bridge     -> ws://172.31.0.200:8766, log results/foxglove_bridge.log
#   4. Foxglove Studio (its OWN instance, data dir foxglove/studio-data) pre-connected to that bridge.
#      First time only: Layouts -> Import from file -> /exploration/foxglove/cuvslam_slam_view.json. Remembered after that.
# Stays in the FOREGROUND showing a live status line (every 3 s) and the node log; Ctrl-C shuts the SLAM side down
# (= scripts/slam_down.sh). Use --detach to return to the prompt instead (then stop with slam_down.sh).
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

[ "${1:-}" = "--detach" ] && { echo "detached — stop later with scripts/slam_down.sh"; exit 0; }

echo
echo "================ SLAM side running — Ctrl-C here stops node + bridge + Studio ================"
trap 'echo; echo "Ctrl-C: shutting the SLAM side down..."; ./scripts/slam_down.sh; exit 0' INT TERM
docker exec -d -w /exploration "$C" bash -lc 'tail -n 0 -F results/cuvslam_node.log > /tmp/node_follow.log 2>&1' || true
while true; do
  docker ps --format '{{.Names}}' | grep -qx "$C" || { echo "container gone"; exit 1; }
  line=$(docker exec -w /exploration "$C" bash -lc '
    st="node:$(pgrep -f "[c]uvslam_stereo_node.py" >/dev/null && echo up || echo DOWN) bridge:$(pgrep -f "[f]oxglove_bridge.*8766" >/dev/null && echo up || echo DOWN) studio:$(pgrep -f "[f]oxglove-studio.*studio-data" >/dev/null && echo up || echo closed) bag:$(pgrep -f "[r]os2 bag record" >/dev/null && echo REC || echo idle)"
    js=$(timeout 2.5 ros2 topic echo --no-daemon --once /drone_1/cuvslam/status 2>/dev/null | head -1 | sed "s/^data: //; s/^'//; s/'$//")
    if [ -n "$js" ]; then python3 - "$st" "$js" <<PY
import json,sys
st,js=sys.argv[1],sys.argv[2]
try:
    d=json.loads(js); print(f"{st}  frames:{d[\"frames\"]} tracked:{d[\"tracked\"]} lost:{d[\"lost\"]} rate:{d[\"rate_hz\"]}Hz track_ms:{d[\"track_ms_p50\"]}")
except Exception: print(st, "status: (parse error)")
PY
    else echo "$st  (no tracker status yet)"; fi
    grep -vE "^\s*$" /tmp/node_follow.log 2>/dev/null | tail -n 3; : > /tmp/node_follow.log' 2>/dev/null | grep -v '^Sourcing')
  printf "%s  %s\n" "$(date +%H:%M:%S)" "$line"
  sleep 3
done
