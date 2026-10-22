#!/usr/bin/env bash
# A second Foxglove bridge INSIDE the exploration container (Isaac network), on port 8766, so Foxglove Studio
# on the laptop can see the Isaac-side topics (camera, /clock) and the cuVSLAM node (odometry, path, debug_image).
# Connect Studio to:  ws://172.31.0.200:8766   (the isaac-sim container IP, shared by this container)
# The commander's own bridge stays on ws://localhost:8765 for the swarm panel.
set -euo pipefail
exec ros2 run foxglove_bridge foxglove_bridge --ros-args -p port:=8766 -p use_sim_time:=true \
  -p topic_whitelist:='["^/clock$","^/drone_[0-9]+/cuvslam/.*","^/drone_[0-9]+/sensors/front_stereo/(left|right)/(image_rect|camera_info)$","^/tf$","^/tf_static$"]'
