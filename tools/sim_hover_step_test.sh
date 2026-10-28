#!/bin/bash
# OURS (lives in tools/, not in CMU's AirStack/ tree). Sim acceptance test for a vehicle model
# (MILESTONES §4 "Starling model: spawn + hover + steps"): takeoff, wait until the commander
# accepts `start` (all drones holding), sample hover thrust, STEPS_PER_AXIS alternating ±1 m
# steps in x then in z, land. Prints the hover-thrust samples and writes odometry traces to
# /tmp/ascent.txt, /tmp/step_x_<k>.txt and /tmp/step_z_<k>.txt.
#
# Forked 2026-10-28 from AirStack/simulation/isaac-sim/tools/sim_hover_step_test.sh (left
# untouched there). Differences: the 2026-10-28 review found /clock is NOT visible in the robot
# container, so `wait_s` is a real sleep (the original echoed /clock with a timeout, which timed out
# silently and just happened to wait the right length); and the single x/z step became N
# alternating steps per axis (env STEPS_PER_AXIS, default 3: +1, -1, +1 m).
#
# The robot container mounts only robot/ros_ws, so tools/sim_hover_step_run.sh `docker cp`s this
# script and tools/analyze_step.py into the container (/tmp/) and runs it from an interactive
# shell (so ROS_DOMAIN_ID is pinned):
#   docker exec airstack-robot-desktop-1 bash -ic 'STEPS_PER_AXIS=3 /tmp/sim_hover_step_test.sh drone_1'
#   python3 /tmp/analyze_step.py /tmp/step_x_1.txt x 1.0 ; python3 /tmp/analyze_step.py /tmp/step_z_1.txt z 1.0
# Prereqs: Isaac spawn running, launch_sim_interfaces.sh N, and the commander launched with a
# `goal` scenario config (e.g. cbf_sim.yaml scenario:=goal).
# (no `set -u`: sourcing ROS setup.bash trips on unbound AMENT_* variables)
D=${1:-drone_1}
N=${STEPS_PER_AXIS:-3}
cd ~/AirStack/robot/ros_ws && source install/setup.bash >/dev/null 2>&1
wait_s(){ sleep "$1"; }
pos(){ timeout 15 ros2 topic echo --once /svg/commander_status --field data 2>/dev/null | head -1 | python3 -c "
import sys,json
j=json.loads(sys.stdin.read().strip()); d=[x for x in j['drones'] if x['name']=='$D'][0]
print(d['state'], d['position'][0], d['position'][1], d['position'][2])"; }
svc(){ timeout 20 ros2 service call /swarm_commander/$1 std_srvs/srv/Trigger 2>/dev/null | grep -o "success=[A-Za-z]*, message='[^']*'"; }
echo "[$(date +%T)] pre-takeoff: $(pos)"
echo "[$(date +%T)] takeoff: $(svc takeoff)"
timeout 25 ros2 topic echo /$D/odometry_conversion/odometry --field pose.pose.position 2>/dev/null > /tmp/ascent.txt   # climb trace for post-mortems
for i in $(seq 1 30); do          # up to ~90 s for all drones to reach their takeoff points
  wait_s 3
  r=$(svc start)
  case "$r" in success=True*) echo "[$(date +%T)] start: $r"; break;; esac
  [ "$i" = 30 ] && { echo "[$(date +%T)] start never accepted: $r"; svc land; exit 1; }
done
wait_s 8
echo "[$(date +%T)] hover: $(pos)"
echo "--- hover thrust samples (/$D/interface/mavros/setpoint_raw/target_attitude .thrust) ---"
timeout 5 ros2 topic echo /$D/interface/mavros/setpoint_raw/target_attitude --field thrust 2>/dev/null | grep -v '^---' | head -10 | tr '\n' ' '; echo
for k in $(seq 1 "$N"); do
  sgn=$([ $((k % 2)) -eq 1 ] && echo 1.0 || echo -1.0)
  read st x y z <<< "$(pos)"
  gx=$(python3 -c "print(round($x+($sgn),3))")
  echo "[$(date +%T)] step x$k: goal ($gx, $y, $z) delta $sgn"
  ros2 topic pub --once /svg/$D/goal_command geometry_msgs/msg/PoseStamped "{header: {frame_id: map}, pose: {position: {x: $gx, y: $y, z: $z}}}" >/dev/null 2>&1 &
  timeout 8 ros2 topic echo /$D/odometry_conversion/odometry --field pose.pose.position 2>/dev/null > /tmp/step_x_$k.txt
done
for k in $(seq 1 "$N"); do
  sgn=$([ $((k % 2)) -eq 1 ] && echo 1.0 || echo -1.0)
  read st x y z <<< "$(pos)"
  gz=$(python3 -c "print(round($z+($sgn),3))")
  echo "[$(date +%T)] step z$k: goal ($x, $y, $gz) delta $sgn"
  ros2 topic pub --once /svg/$D/goal_command geometry_msgs/msg/PoseStamped "{header: {frame_id: map}, pose: {position: {x: $x, y: $y, z: $gz}}}" >/dev/null 2>&1 &
  timeout 8 ros2 topic echo /$D/odometry_conversion/odometry --field pose.pose.position 2>/dev/null > /tmp/step_z_$k.txt
done
echo "[$(date +%T)] after steps: $(pos)"
echo "[$(date +%T)] land: $(svc land)"
wait_s 15
echo "[$(date +%T)] landed: $(pos)"
echo "traces: /tmp/ascent.txt /tmp/step_x_*.txt /tmp/step_z_*.txt  (analyse with /tmp/analyze_step.py <trace> <axis> <delta>)"
