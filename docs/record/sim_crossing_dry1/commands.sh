# == phase precheck ==  2026-10-29 22:51:56 +08
# == phase up ==  2026-10-29 22:51:56 +08
cd /home/jeremychia/AirStack-starling-max2/AirStack && ./airstack.sh up
docker exec isaac-sim mkdir -p /tmp/svg_test
docker exec airstack-robot-desktop-1 mkdir -p /tmp/svg_test
docker exec airstack-robot-desktop-1 bash -ic 'ros2 daemon stop; ros2 topic list --no-daemon --spin-time 5' | grep -E '/fmu/|/poses|/pose$'
git -C /home/jeremychia/AirStack-starling-max2 rev-parse HEAD; git -C /home/jeremychia/AirStack-starling-max2 status --porcelain -- tools | wc -l   # -> run_meta.txt
# == phase watch ==  2026-10-29 22:52:02 +08
nohup /home/jeremychia/AirStack-starling-max2/localisation/scripts/sim_resources_watch.sh /home/jeremychia/AirStack-starling-max2/docs/record/sim_crossing_dry1/res_watch.log &
# == phase isaac ==  2026-10-29 22:52:05 +08
docker exec -d isaac-sim bash -ic 'PYTHONUNBUFFERED=1 DRONE_USD=/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd PX4_VEHICLE_MODEL=pegasus_starling2max NUM_ROBOTS=3 SVG_DOMAIN_ID=1 PLAY_SIM_ON_START=true ISAAC_SIM_HEADLESS=true PYTHONPATH="$ISAAC_SIM_PYTHONPATH" /isaac-sim/python.sh /isaac-sim/AirStack/simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py --ext-folder ~/.local/share/ov/data/documents/Kit/shared/exts > /tmp/svg_test/isaac.log 2>&1'
# == phase interfaces ==  2026-10-29 22:52:21 +08
docker exec -d airstack-robot-desktop-1 bash -ic 'cd ~/AirStack/robot/ros_ws && ./src/svg_ground_control/scripts/launch_sim_interfaces.sh 3 > /tmp/svg_test/interfaces.log 2>&1'
for N in 1 2 3: docker exec airstack-robot-desktop-1 bash -ic 'timeout 10 ros2 topic echo --once /drone_$N/interface/mavros/state' | grep '^connected: true'
for N in 1 2 3: docker exec airstack-robot-desktop-1 bash -ic 'timeout 10 ros2 topic echo --once /drone_$N/odometry_conversion/odometry --field pose.pose.position'  (retry <= 90 s)
docker exec airstack-robot-desktop-1 bash -ic 'timeout 15 ros2 topic hz /drone_1/odometry_conversion/odometry -w 200'
docker exec airstack-robot-desktop-1 bash -ic 'ros2 topic info /clock; echo clock_rc=$?'   # 0 = /clock exists, 1 = unknown topic
# == phase commander ==  2026-10-29 22:52:53 +08
docker exec -d airstack-robot-desktop-1 bash -ic 'cd ~/AirStack/robot/ros_ws && ros2 launch svg_ground_control ground_control.launch.py config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/cbf_sim.yaml scenario:=antipodal record_bag:=true bag_prefix:=crossing > /tmp/svg_test/commander.log 2>&1'
poll <= 30 s every 2 s: docker exec airstack-robot-desktop-1 bash -ic 'timeout 8 ros2 topic echo --once /svg/commander_status --field data'  # last snapshot -> status_pre.json
# == phase params ==  2026-10-29 22:53:00 +08
docker exec airstack-robot-desktop-1 bash -ic 'ros2 service list | grep /drone_1/interface/mavros/param; ros2 node list | grep /drone_1/interface/mavros'
docker exec airstack-robot-desktop-1 bash -ic 'ros2 service call /drone_1/interface/mavros/param/pull mavros_msgs/srv/ParamPull "{force_pull: false}"; ros2 param get <param node> <P>'
# == phase metrics ==  2026-10-29 22:53:31 +08
docker exec airstack-robot-desktop-1 mkdir -p /tmp/svg_test
docker cp /home/jeremychia/AirStack-starling-max2/tools/live/metrics_core.py airstack-robot-desktop-1:/tmp/svg_test/
docker cp /home/jeremychia/AirStack-starling-max2/tools/live/metrics_node.py airstack-robot-desktop-1:/tmp/svg_test/
docker cp /home/jeremychia/AirStack-starling-max2/tools/live/bag_recompute.py airstack-robot-desktop-1:/tmp/svg_test/
docker cp /home/jeremychia/AirStack-starling-max2/tools/sim_tests/crossing/metrics.py airstack-robot-desktop-1:/tmp/svg_test/
docker cp /home/jeremychia/AirStack-starling-max2/tools/sim_tests/crossing/fly.sh airstack-robot-desktop-1:/tmp/svg_test/
docker exec -d airstack-robot-desktop-1 bash -ic 'cd /tmp/svg_test && python3 metrics_node.py --test-dir /tmp/svg_test --csv /tmp/svg_test/metrics.csv > /tmp/svg_test/metrics_node.log 2>&1'
# == phase fly ==  2026-10-29 22:54:02 +08
docker exec -d airstack-robot-desktop-1 bash -ic 'bash /tmp/svg_test/fly.sh 45 > /tmp/svg_test/test_stdout.log 2>&1'
for N in 1 2 3: docker exec airstack-robot-desktop-1 bash -ic 'timeout 10 ros2 topic echo --once /drone_$N/interface/mavros/state' | grep -oE '^armed: (true|false)'  # -> armed_post.txt
docker exec airstack-robot-desktop-1 pkill -INT -f python3 metrics_node.py
# == phase collect ==  2026-10-29 22:55:57 +08
docker exec isaac-sim bash -c 'for f in /tmp/tmp*/log/*/*.ulg; do [ $(stat -c %Y $f) -gt 1793285525 ] && echo $f; done'  # -> ulog_list.txt
docker exec isaac-sim python3 -c "from pyulog import ULog; print(ULog(f, message_name_filter_list=['vehicle_local_position']).initial_parameters.get('MAV_SYS_ID'))"  # -> ulog_sysid_map.txt
docker cp isaac-sim:<ulog> /home/jeremychia/flight_logs/sim/sim_crossing_dry1/drone_<sid-1>_sysid<sid>_<basename>.ulg
docker exec isaac-sim python3 -c "from pyulog import ULog; p=ULog('/tmp/tmp70scry7m/log/2026-10-29/14_52_16.ulg', message_name_filter_list=['vehicle_local_position']).initial_parameters; ..."  # -> params_ulog.txt
docker cp /home/jeremychia/AirStack-starling-max2/tools/hover_step_timescale.py isaac-sim:/tmp/
docker exec isaac-sim python3 /tmp/hover_step_timescale.py /tmp/tmp70scry7m/log/2026-10-29/14_52_16.ulg  # -> px4_arm_times.txt
# == phase down ==  2026-10-29 22:56:00 +08
docker exec airstack-robot-desktop-1 pkill -INT -f ground_control.launch.py
docker exec airstack-robot-desktop-1 bash -c 'ls -d /root/AirStack/robot/ros_ws/bags/crossing_* | tail -1'; docker cp airstack-robot-desktop-1:<bag> /home/jeremychia/flight_logs/sim/sim_crossing_dry1/
docker exec airstack-robot-desktop-1 bash -ic 'python3 /tmp/svg_test/bag_recompute.py /root/AirStack/robot/ros_ws/bags/crossing_20261029_145255 --test-dir /tmp/svg_test --meta-from /tmp/svg_test/metrics.csv -o /tmp/svg_test/metrics_bag.csv'
docker exec airstack-robot-desktop-1 rm -rf /root/AirStack/robot/ros_ws/bags/crossing_20261029_145255
docker exec airstack-robot-desktop-1 pkill -INT -f launch_sim_interfaces.sh
docker exec isaac-sim pkill -INT -f svg_multi_drone_single_domain.py
docker exec isaac-sim pkill -9 -x px4
docker exec airstack-robot-desktop-1 pkill -f position_setpoint_pub
python3 /home/jeremychia/AirStack-starling-max2/tools/lib/report.py /home/jeremychia/AirStack-starling-max2/tools/sim_tests/crossing /home/jeremychia/AirStack-starling-max2/docs/record/sim_crossing_dry1 --heavy /home/jeremychia/flight_logs/sim/sim_crossing_dry1 --ledger 20 --issue NEAR-787
