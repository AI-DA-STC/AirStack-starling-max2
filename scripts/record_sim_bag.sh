#!/usr/bin/env bash
# Record the scoring bag for one sim flight (run INSIDE a ROS container on the sim domain, e.g.
# ./docker/run.sh). Usage: scripts/record_sim_bag.sh <name> [drone]
# Records: cuVSLAM odometry + status, the drone's EKF2 odometry (reference, NOT ground truth),
# /clock, commander status. Images are NOT recorded (render products are heavy).
set -euo pipefail
name=${1:?usage: record_sim_bag.sh <name> [drone]}
d=${2:-drone_1}
out=/exploration/results/bags/${name}
mkdir -p /exploration/results/bags
exec ros2 bag record -s mcap -o "$out" \
  /${d}/cuvslam/odometry /${d}/cuvslam/status \
  /${d}/odometry_conversion/odometry /${d}/interface/mavros/local_position/odom \
  /clock /svg/commander_status /tf /tf_static
