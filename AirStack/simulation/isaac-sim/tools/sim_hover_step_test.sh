#!/bin/bash
# Sim acceptance test for a vehicle model (MILESTONES M1 "hover + steps"): takeoff, wait until
# the commander accepts `start` (all drones holding), sample hover thrust, 1 m step in x then
# z, land. Prints the hover-thrust samples and writes odometry traces to /tmp/step_{x,z}.txt.
#
# The robot container mounts only robot/ros_ws, so copy the two tools in first (laptop):
#   docker cp AirStack/simulation/isaac-sim/tools/sim_hover_step_test.sh airstack-robot-desktop-1:/tmp/
#   docker cp AirStack/simulation/isaac-sim/tools/analyze_step.py       airstack-robot-desktop-1:/tmp/
# then run INSIDE the container from an interactive shell (so ROS_DOMAIN_ID is pinned):
#   bash -ic '/tmp/sim_hover_step_test.sh drone_1'
#   python3 /tmp/analyze_step.py /tmp/step_x.txt x 1.0 ; python3 /tmp/analyze_step.py /tmp/step_z.txt z 1.0
# Prereqs: Isaac spawn running, launch_sim_interfaces.sh N, and the commander launched with a
# `goal` scenario config (e.g. cbf_sim.yaml scenario:=goal).
# (no `set -u`: sourcing ROS setup.bash trips on unbound AMENT_* variables)
D=${1:-drone_1}
cd ~/AirStack/robot/ros_ws && source install/setup.bash >/dev/null 2>&1
wait_s(){ timeout "$1" ros2 topic echo /clock >/dev/null 2>&1; }
pos(){ timeout 15 ros2 topic echo --once /svg/commander_status --field data 2>/dev/null | head -1 | python3 -c "
import sys,json
j=json.loads(sys.stdin.read().strip()); d=[x for x in j['drones'] if x['name']=='$D'][0]
print(d['state'], d['position'][0], d['position'][1], d['position'][2])"; }
svc(){ timeout 20 ros2 service call /swarm_commander/$1 std_srvs/srv/Trigger 2>/dev/null | grep -o "success=[A-Za-z]*, message='[^']*'"; }
echo "[$(date +%T)] pre-takeoff: $(pos)"
echo "[$(date +%T)] takeoff: $(svc takeoff)"
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
read st x y z <<< "$(pos)"
gx=$(python3 -c "print(round($x+1.0,3))")
echo "[$(date +%T)] step x: goal ($gx, $y, $z)"
ros2 topic pub --once /svg/$D/goal_command geometry_msgs/msg/PoseStamped "{header: {frame_id: map}, pose: {position: {x: $gx, y: $y, z: $z}}}" >/dev/null 2>&1 &
timeout 8 ros2 topic echo /$D/odometry_conversion/odometry --field pose.pose.position 2>/dev/null > /tmp/step_x.txt
read st x y z <<< "$(pos)"
gz=$(python3 -c "print(round($z+1.0,3))")
echo "[$(date +%T)] step z: goal ($x, $y, $gz)"
ros2 topic pub --once /svg/$D/goal_command geometry_msgs/msg/PoseStamped "{header: {frame_id: map}, pose: {position: {x: $x, y: $y, z: $gz}}}" >/dev/null 2>&1 &
timeout 8 ros2 topic echo /$D/odometry_conversion/odometry --field pose.pose.position 2>/dev/null > /tmp/step_z.txt
echo "[$(date +%T)] after steps: $(pos)"
echo "[$(date +%T)] land: $(svc land)"
wait_s 15
echo "[$(date +%T)] landed: $(pos)"
echo "traces: /tmp/step_x.txt /tmp/step_z.txt  (analyse with /tmp/analyze_step.py)"
