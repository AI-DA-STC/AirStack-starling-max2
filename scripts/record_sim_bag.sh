#!/usr/bin/env bash
# Record the scoring bag for one sim flight. Run INSIDE the exploration container (./docker/run.sh),
# which is joined to the Isaac network, so only Isaac-side topics + the cuVSLAM node are visible
# (MAVROS/commander topics live on the host network and are NOT recorded here — see TROUBLESHOOTING).
# Usage: scripts/record_sim_bag.sh <run_name> [drone]    (Ctrl-C to stop)
set -euo pipefail
name=${1:?usage: record_sim_bag.sh <run_name> [drone]}
d=${2:-drone_1}
mkdir -p /exploration/results/bags
exec ros2 bag record -s mcap -o "/exploration/results/bags/${name}" \
  /${d}/cuvslam/odometry /${d}/cuvslam/status /clock /${d}/sensors/front_stereo/left/camera_info
