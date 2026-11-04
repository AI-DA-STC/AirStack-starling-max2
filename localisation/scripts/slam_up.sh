#!/usr/bin/env bash
# One command for the SLAM side of a sim session (run on the laptop AFTER the sim says "Ready for takeoff" x3):
#   1. exploration container up (joined to the Isaac network)
#   2. cuVSLAM node        -> log results/cuvslam_node.log
#   3. Foxglove bridge     -> ws://172.31.0.200:8766, log results/foxglove_bridge.log
#   3a. auto grid (Foxglove ground grid that grows with the drone): cuVSLAM copy here, Basestation copy in the robot container
#   3b. install the SVG Teleop panel (tools/teleop/foxglove/install.sh) before Studio starts
#   4. Foxglove Studio (its OWN instance, data dir foxglove/studio-data) pre-connected to that bridge.
#      First time only: Layouts -> Import from file -> /exploration/foxglove/cuvslam_slam_view.json. Remembered after that.
#      For the teleop strip import /teleop-foxglove/teleop-cuvslam.json (= tools/teleop/foxglove/teleop-cuvslam.json) once;
#      after that this script loads the shipped layout by itself (tools/teleop/foxglove/sync_layout.py) when it starts Studio.
# Stays in the FOREGROUND showing a live status line (every 3 s) and the node log; Ctrl-C shuts the SLAM side down
# (= scripts/slam_down.sh). Use --detach to return to the prompt instead (then stop with slam_down.sh).
set -euo pipefail
cd "$(dirname "$0")/.."
./docker/up.sh
C=localisation-exploration
# the bridge reaches the robot container through the laptop firewall (spec 2026-11-03 §5.8): warn, never refuse
. "$(cd .. && pwd)/tools/lib/firewall_probe.sh" 2>/dev/null || firewall_probe() { echo skip; }
case "$(firewall_probe)" in
  blocked) echo "WARNING: the container cannot reach the host (firewall) — the teleop strip will see no keys. Run: ${FIREWALL_FIX:-sudo ufw allow from 172.31.0.0/24}" ;;
  error)   echo "WARNING: firewall: not checked (probe failed: could not send from isaac-sim)" ;;
esac
# ex: run a command in the container; return ITS exit code (not grep's), hide the "Sourcing ..." banner lines
ex() { local out rc; out=$(docker exec -w /exploration "$C" bash -lc "$*" 2>&1); rc=$?; [ -n "$out" ] && grep -v '^Sourcing' <<<"$out"; return $rc; }
exd() { docker exec -d -w /exploration "$C" bash -lc "$*"; }

if ! ex 'pgrep -f "[c]uvslam_stereo_node.py" >/dev/null'; then
  exd 'python3 -u nodes/cuvslam_stereo_node.py > results/cuvslam_node.log 2>&1'
  echo "cuVSLAM node started (results/cuvslam_node.log)"
else echo "cuVSLAM node already running"; fi

if ! ex 'pgrep -f "[f]oxglove_bridge.*8766" >/dev/null'; then
  exd 'scripts/foxglove_bridge_isaac.sh > results/foxglove_bridge.log 2>&1'
  echo "Foxglove bridge started on ws://172.31.0.200:8766 (results/foxglove_bridge.log)"
else echo "Foxglove bridge already running"; fi

# --- auto grid: a Foxglove ground grid that grows with the drone (tools/teleop/foxglove/auto_grid.py); never fails this script
# cuVSLAM window: inside this container, plain fastdds.xml (NOT the bridge's peer profile); the bridge's cuvslam whitelist admits its topic
if ex 'test -f /teleop-foxglove/auto_grid.py'; then
  if ! ex 'pgrep -f "[a]uto_grid.py.*--source odom" >/dev/null'; then
    exd 'python3 -u /teleop-foxglove/auto_grid.py --source odom --drone drone_1 > results/auto_grid.log 2>&1' \
      && echo "auto grid (cuVSLAM window) started (results/auto_grid.log)" || echo "WARNING: auto grid (cuVSLAM window) did not start"
  else echo "auto grid (cuVSLAM window) already running"; fi
else echo "Auto grid not started: run scripts/slam_down.sh, then scripts/slam_up.sh"; fi
# Basestation window: in the robot container (topic /svg/viz/grid, turn it on once in the 3D panel's settings)
GR=airstack-robot-desktop-1; GD=/tmp/svg_grid; GSRC="$(cd .. && pwd)/tools/teleop/foxglove"
if docker exec "$GR" mkdir -p "$GD" >/dev/null 2>&1; then
  if docker cp "$GSRC/auto_grid.py" "$GR:$GD/" >/dev/null 2>&1 && docker cp "$GSRC/grid_core.py" "$GR:$GD/" >/dev/null 2>&1; then
    if docker exec "$GR" pgrep -f 'svg_grid/auto_grid\.py' >/dev/null 2>&1; then echo "auto grid (Basestation window) already running"
    else
      docker exec -d "$GR" bash -ic "python3 $GD/auto_grid.py --source status > $GD/auto_grid.log 2>&1" \
        && echo "auto grid (Basestation window) started ($GR:$GD/auto_grid.log)" || echo "WARNING: auto grid (Basestation window) did not start"
    fi
  else echo "WARNING: auto grid (Basestation window): could not copy the files into $GR"; fi
else echo "WARNING: auto grid (Basestation window) skipped: the robot container ($GR) is not running"; fi
# --- end auto grid

for i in $(seq 1 20); do ex 'grep -q "tracker ready" results/cuvslam_node.log' && break; sleep 1; done
ex 'grep -m1 "tracker ready" results/cuvslam_node.log || echo "node not ready yet — is the sim playing with ENABLE_CAMERA=true CAMERA_DRONES=drone_1 ?"'

# the SVG Teleop panel: copied into the container's Studio extensions folder on every start (its home is lost on docker rm)
if ex 'test -f /teleop-foxglove/install.sh'; then ex 'bash /teleop-foxglove/install.sh' || echo "WARNING: teleop panel install failed"
else echo "Teleop panel not installed: run scripts/slam_down.sh, then scripts/slam_up.sh"; fi

if ! ex 'pgrep -f "[f]oxglove-studio.*studio-data" >/dev/null'; then
  # the shipped layout goes into Studio's store (only here: Studio is not running). Any failure means no id, never a stop.
  LAYOUT_ID=$(ex 'python3 /teleop-foxglove/sync_layout.py --store /exploration/foxglove/studio-data/studio-datastores --layout /teleop-foxglove/teleop-cuvslam.json --marker /exploration/results/teleop_layout.marker --backup-dir /exploration/results/layout_backups' 2>/dev/null | tail -n 1) || true
  [[ "$LAYOUT_ID" =~ ^[A-Za-z0-9_-]+$ ]] || LAYOUT_ID=""
  LAYOUT_ARG=""; [ -z "$LAYOUT_ID" ] || { LAYOUT_ARG="&layoutId=$LAYOUT_ID"; echo "Foxglove layout: teleop-cuvslam"; }
  exd "foxglove-studio --no-sandbox --user-data-dir=/exploration/foxglove/studio-data \"foxglove://open?ds=foxglove-websocket&ds.url=ws://172.31.0.200:8766${LAYOUT_ARG}\" > results/foxglove_studio.log 2>&1"
  echo "Foxglove Studio (SLAM instance) opening, connected to ws://172.31.0.200:8766"
  [ -n "$(ls -A foxglove/studio-data 2>/dev/null)" ] || echo "FIRST TIME: in that window do Layouts -> Import from file -> /exploration/foxglove/cuvslam_slam_view.json (remembered afterwards)"
else echo "Foxglove Studio (SLAM instance) already open. Restart Studio to load the panel (scripts/slam_down.sh, then scripts/slam_up.sh)"; fi

[ "${1:-}" = "--detach" ] && { echo "detached — stop later with scripts/slam_down.sh"; exit 0; }

echo
echo "================ SLAM side running — Ctrl-C here stops node + bridge + Studio ================"
trap 'echo; echo "Ctrl-C: shutting the SLAM side down..."; ./scripts/slam_down.sh; exit 0' INT TERM
docker exec -d -w /exploration "$C" bash -lc 'tail -n 0 -F results/cuvslam_node.log > /tmp/node_follow.log 2>&1' || true
set +e   # a failed status probe must not kill the loop (the trap above must stay armed)
while true; do
  docker ps --format '{{.Names}}' | grep -qx "$C" || { echo "container gone"; exit 1; }
  line=$(docker exec -w /exploration "$C" bash -lc 'scripts/slam_status_line.sh' 2>/dev/null | grep -v '^Sourcing')
  printf "%s  %s\n" "$(date +%H:%M:%S)" "${line:-(status probe failed)}"
  sleep 3
done
