#!/usr/bin/env bash
# One tab of the sim session (opened by tools/sim_terminals.sh, usable alone):
# print the commands for this tab's role, then drop into the right container.
# No tmux: whatever you start here lives in this tab — keep the tab open.
#
#   tools/sim_tab.sh isaac | interfaces | commander | cockpit
role="${1:-}"
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
case "$role" in
    isaac)      container=isaac-sim ;;
    interfaces|commander|cockpit) container=airstack-robot-desktop-1 ;;
    *) echo "usage: $(basename "$0") isaac|interfaces|commander|cockpit"; exec bash ;;
esac

bold=$'\e[1m'; dim=$'\e[2m'; off=$'\e[0m'
echo "${bold}== $role  ($container) ==${off}"
case "$role" in
isaac) cat <<'TXT'
Paste to start the sim (Starling 2 Max model, window on; ISAAC_SIM_HEADLESS=true for none):

DRONE_USD=/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd PX4_VEHICLE_MODEL=pegasus_starling2max \
NUM_ROBOTS=3 SVG_DOMAIN_ID=1 PLAY_SIM_ON_START=true ISAAC_SIM_HEADLESS=false \
PYTHONPATH="$ISAAC_SIM_PYTHONPATH" \
/isaac-sim/python.sh /isaac-sim/AirStack/simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py \
  --ext-folder ~/.local/share/ov/data/documents/Kit/shared/exts

Wait for "Ready for takeoff!" x3. NEVER press Stop/Play in the Isaac window (TROUBLESHOOTING).

Camera world (optional, stereo VO runs - localisation/README.md): put this in front of the line above:
ENV_USD=/isaac-sim/.local/share/ov/data/scenes/construction_site/construction_site_full.usdc ENABLE_CAMERA=true CAMERA_DRONES=drone_1
Keep localisation/scripts/sim_resources_watch.sh running on the laptop (Isaac start/stop has crashed the WiFi firmware).
TXT
;;
interfaces) cat <<'TXT'
After the sim says Ready for takeoff x3:

./src/svg_ground_control/scripts/launch_sim_interfaces.sh 3

Only after NEW entry points/files (e.g. a snapshot bump), rebuild first: bws && sws
(.py/.yaml edits need no rebuild — symlink install).
TXT
;;
commander) cat <<'TXT'
Commander + Foxglove Studio (scenario:= hover|goal|random_walk|random_goals|head_on|antipodal|squeeze|goal_sequence|figure_eight):

ros2 launch svg_ground_control ground_control.launch.py \
  config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/cbf_sim.yaml \
  scenario:=random_goals use_foxglove_studio:=true

Studio opens already connected to ws://localhost:8765. First time: import the layout
/root/AirStack/robot/ros_ws/src/svg_ground_control/foxglove/svg_basestation.json (BASESTATION.md §2).
TXT
;;
cockpit) cat <<'TXT'
ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger    # wait for "holding takeoff position" x3 (~30 s)
ros2 service call /swarm_commander/start   std_srvs/srv/Trigger
ros2 service call /swarm_commander/hold    std_srvs/srv/Trigger    # freeze in a hover first
ros2 service call /swarm_commander/land    std_srvs/srv/Trigger    # from the hover, never mid-leg
#   commander log per drone: "touchdown at z=... settling 2.0 s before disarm" -> "landed, disarmed (attempt 1)"
ros2 topic echo /drone_1/interface/mavros/state --once             # expect armed: false
ros2 param set /swarm_commander scenario_speed_mps 1.0             # live gains (yaml default 2.0); see SCENARIOS.md §3
TXT
;;
esac
echo "${dim}(workspace is sourced by the container's bashrc; ROS_DOMAIN_ID=1 is set there)${off}"
echo

if ! docker ps --format '{{.Names}}' | grep -qx "$container"; then
    echo "container '$container' is not running — in another tab: cd $repo/AirStack && ./airstack.sh up"
    exec bash
fi
docker exec -it "$container" bash
echo "(left $container — tab kept open; press Enter for a laptop shell)"
exec bash
