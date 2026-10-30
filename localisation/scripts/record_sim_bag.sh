#!/usr/bin/env bash
# Record the scoring bag for one sim flight. Run INSIDE the exploration container (./docker/run.sh),
# which is joined to the Isaac network, so only Isaac-side topics + the cuVSLAM node are visible
# (MAVROS/commander topics live on the host network and are NOT recorded here — see TROUBLESHOOTING).
# Since NEAR-860 the bag also holds both stereo images and both camera_infos, so the flight can be replayed
# through cuVSLAM later (scripts/replay_bag.sh). zstd-compressed mcap; ~8 GB raw per 3 min at 640x480 rgb, 25 Hz.
# Usage: scripts/record_sim_bag.sh <run_name> [drone]    (Ctrl-C to stop)
set -euo pipefail
name=${1:?usage: record_sim_bag.sh <run_name> [drone]}
d=${2:-drone_1}
mkdir -p /exploration/results/bags
# ros2 runs as root in the container; hand the folder back to the laptop user afterwards so it can be deleted/moved in Files
trap 'chown -R 1000:1000 "/exploration/results/bags/${name}" 2>/dev/null || true' EXIT
cam=/${d}/sensors/front_stereo
ros2 bag record -s mcap --storage-preset-profile zstd_fast -o "/exploration/results/bags/${name}" \
  /${d}/cuvslam/odometry /${d}/cuvslam/status /clock \
  ${cam}/left/camera_info ${cam}/right/camera_info ${cam}/left/image_rect ${cam}/right/image_rect || true
