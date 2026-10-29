#!/bin/bash
# Three-drone CBF crossing flight (NEAR-787). Sim only (iron rule 9). Runs INSIDE the robot container.
# Usage: fly.sh [DURATION_S]   (default 45)
# Copied from CMU's AirStack/simulation/isaac-sim/tools/sim_cbf_crossing_test.sh (never edited there).
# Two differences: (1) wait_s is a real `sleep` -- the robot container has no /clock to wait on;
# (2) no analysis here -- the metrics node measures, gates.py judges. Output is the evidence stdout.
DURATION=${1:-45}
cd ~/AirStack/robot/ros_ws && source install/setup.bash >/dev/null 2>&1
wait_s(){ sleep "$1"; }
svc(){ timeout 20 ros2 service call /swarm_commander/$1 std_srvs/srv/Trigger 2>/dev/null | grep -o "success=[A-Za-z]*, message='[^']*'"; }
states(){ timeout 10 ros2 topic echo /svg/commander_status --once --field data 2>/dev/null | grep -v '^---' \
  | grep -oE '"(name|state)": *"[^"]*"|"position": *\[[^]]*\]' | tr -d '"' | paste -sd' '; }
echo "[$(date +%T)] pre-takeoff: $(states)"
echo "[$(date +%T)] takeoff: $(svc takeoff)"
for i in $(seq 1 30); do wait_s 3; r=$(svc start); case "$r" in success=True*) echo "[$(date +%T)] start: $r"; break;; esac
  [ "$i" = 30 ] && { echo "start never accepted: $r"; svc land; exit 1; }; done
echo "[$(date +%T)] window: $DURATION s"
wait_s "$DURATION"
echo "[$(date +%T)] land: $(svc land)"
wait_s 15
echo "[$(date +%T)] landed: $(states)"
