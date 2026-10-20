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
TXT
;;
interfaces) cat <<'TXT'
After the sim says Ready for takeoff x3:

./src/svg_ground_control/scripts/launch_sim_interfaces.sh 3
TXT
;;
commander) cat <<'TXT'
Commander + Foxglove Studio (scenario:=antipodal|random_goals|head_on|goal ...):

ros2 launch svg_ground_control ground_control.launch.py \
  config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/cbf_sim.yaml \
  scenario:=random_goals use_foxglove_studio:=true

Studio: Open connection -> Foxglove WebSocket -> ws://localhost:8765; layout foxglove/svg_basestation.json
TXT
;;
cockpit) cat <<'TXT'
ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger    # wait for "holding takeoff position" x3
ros2 service call /swarm_commander/start   std_srvs/srv/Trigger
ros2 service call /swarm_commander/land    std_srvs/srv/Trigger
ros2 topic echo /drone_1/interface/mavros/state --once             # expect armed: false
ros2 param set /swarm_commander scenario_speed_mps 2.0             # live gains; see SCENARIOS.md §3
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
