# == phase precheck ==  2026-11-02 19:59:48 +08
# == phase up ==  2026-11-02 19:59:49 +08
cd /home/jeremychia/AirStack-starling-max2/AirStack && ./airstack.sh up
docker exec isaac-sim mkdir -p /tmp/svg_test
docker exec airstack-robot-desktop-1 mkdir -p /tmp/svg_test
docker exec airstack-robot-desktop-1 bash -ic 'ros2 daemon stop; ros2 topic list --no-daemon --spin-time 5' | grep -E '/fmu/|/poses|/pose$'
git -C /home/jeremychia/AirStack-starling-max2 rev-parse HEAD; git -C /home/jeremychia/AirStack-starling-max2 status --porcelain -- tools | wc -l   # -> run_meta.txt
# == phase watch ==  2026-11-02 19:59:55 +08
nohup /home/jeremychia/AirStack-starling-max2/localisation/scripts/sim_resources_watch.sh /home/jeremychia/AirStack-starling-max2/docs/record/sim_yaw_sweep4/res_watch.log &
# == phase isaac ==  2026-11-02 19:59:58 +08
docker exec -d isaac-sim bash -ic 'PYTHONUNBUFFERED=1 DRONE_USD=/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd PX4_VEHICLE_MODEL=pegasus_starling2max NUM_ROBOTS=1 SVG_DOMAIN_ID=1 PLAY_SIM_ON_START=true ISAAC_SIM_HEADLESS=false PYTHONPATH="$ISAAC_SIM_PYTHONPATH" /isaac-sim/python.sh /isaac-sim/AirStack/simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py --ext-folder ~/.local/share/ov/data/documents/Kit/shared/exts > /tmp/svg_test/isaac.log 2>&1'
# == phase interfaces ==  2026-11-02 20:00:13 +08
docker exec -d airstack-robot-desktop-1 bash -ic 'cd ~/AirStack/robot/ros_ws && ./src/svg_ground_control/scripts/launch_sim_interfaces.sh 1 > /tmp/svg_test/interfaces.log 2>&1'
for N in 1: docker exec airstack-robot-desktop-1 bash -ic 'timeout 10 ros2 topic echo --once /drone_$N/interface/mavros/state' | grep '^connected: true'
for N in 1: docker exec airstack-robot-desktop-1 bash -ic 'timeout 10 ros2 topic echo --once /drone_$N/odometry_conversion/odometry --field pose.pose.position'  (retry <= 90 s)
docker exec airstack-robot-desktop-1 bash -ic 'timeout 15 ros2 topic hz /drone_1/odometry_conversion/odometry -w 200'
docker exec airstack-robot-desktop-1 bash -ic 'ros2 topic info /clock; echo clock_rc=$?'   # 0 = /clock exists, 1 = unknown topic
# == phase commander ==  2026-11-02 20:00:38 +08
docker exec -d airstack-robot-desktop-1 bash -ic 'cd ~/AirStack/robot/ros_ws && ros2 launch svg_ground_control ground_control.launch.py config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/teleop_single.yaml scenario:=hover record_bag:=true bag_prefix:=yaw_step > /tmp/svg_test/commander.log 2>&1'
poll <= 30 s every 2 s: docker exec airstack-robot-desktop-1 bash -ic 'timeout 8 ros2 topic echo --once /svg/commander_status --field data'  # last snapshot -> status_pre.json
# == phase params ==  2026-11-02 20:00:45 +08
docker exec airstack-robot-desktop-1 bash -ic 'ros2 service list | grep /drone_1/interface/mavros/param; ros2 node list | grep /drone_1/interface/mavros'
docker exec airstack-robot-desktop-1 bash -ic 'ros2 service call /drone_1/interface/mavros/param/pull mavros_msgs/srv/ParamPull "{force_pull: false}"; ros2 param get <param node> <P>'
# == phase snapshot ==  2026-11-02 20:01:04 +08
docker exec airstack-robot-desktop-1 bash -ic "timeout 120 ros2 service call /drone_1/interface/mavros/param/pull mavros_msgs/srv/ParamPull '{force_pull: false}'"
docker exec airstack-robot-desktop-1 bash -ic 'timeout 60 ros2 param dump /drone_1/interface/mavros/param' > /home/jeremychia/flight_logs/sim/sim_yaw_sweep4/params_start_drone_1.yaml
docker exec airstack-robot-desktop-1 bash -ic 'timeout 30 ros2 param dump /swarm_commander' > /home/jeremychia/flight_logs/sim/sim_yaw_sweep4/params_start_swarm_commander.yaml
# == phase metrics ==  2026-11-02 20:01:13 +08
docker exec airstack-robot-desktop-1 mkdir -p /tmp/svg_test
docker cp /home/jeremychia/AirStack-starling-max2/tools/live/metrics_core.py airstack-robot-desktop-1:/tmp/svg_test/
docker cp /home/jeremychia/AirStack-starling-max2/tools/live/metrics_node.py airstack-robot-desktop-1:/tmp/svg_test/
docker cp /home/jeremychia/AirStack-starling-max2/tools/live/bag_recompute.py airstack-robot-desktop-1:/tmp/svg_test/
docker cp /home/jeremychia/AirStack-starling-max2/tools/lib/px4_param_set.sh airstack-robot-desktop-1:/tmp/svg_test/
docker cp /home/jeremychia/AirStack-starling-max2/tools/lib/changes_log.py airstack-robot-desktop-1:/tmp/svg_test/
docker cp /home/jeremychia/AirStack-starling-max2/tools/sim_tests/yaw_step/metrics.py airstack-robot-desktop-1:/tmp/svg_test/
docker cp /home/jeremychia/AirStack-starling-max2/tools/sim_tests/yaw_step/fly.sh airstack-robot-desktop-1:/tmp/svg_test/
docker exec -d airstack-robot-desktop-1 bash -ic 'cd /tmp/svg_test && python3 metrics_node.py --test-dir /tmp/svg_test --csv /tmp/svg_test/metrics.csv > /tmp/svg_test/metrics_node.log 2>&1'
# == phase fly ==  2026-11-02 20:03:40 +08
docker exec -d airstack-robot-desktop-1 bash -ic 'bash /tmp/svg_test/fly.sh 20 2 1.0 1.0 MC_YAWRATE_P=0.25\,MC_YAWRATE_I=0.2\;MC_YAWRATE_P=0.35\,MC_YAWRATE_I=0.2\;MC_YAWRATE_P=0.35\,MC_YAWRATE_I=0.1\;MC_YAWRATE_P=0.45\,MC_YAWRATE_I=0.2 > /tmp/svg_test/test_stdout.log 2>&1'
for N in 1: docker exec airstack-robot-desktop-1 bash -ic 'timeout 10 ros2 topic echo --once /drone_$N/interface/mavros/state' | grep -oE '^armed: (true|false)'  # -> armed_post.txt
docker exec airstack-robot-desktop-1 bash -ic "timeout 120 ros2 service call /drone_1/interface/mavros/param/pull mavros_msgs/srv/ParamPull '{force_pull: true}'"
docker exec airstack-robot-desktop-1 bash -ic 'timeout 60 ros2 param dump /drone_1/interface/mavros/param' > /home/jeremychia/flight_logs/sim/sim_yaw_sweep4/params_end_drone_1.yaml
docker exec airstack-robot-desktop-1 bash -ic 'timeout 30 ros2 param dump /swarm_commander' > /home/jeremychia/flight_logs/sim/sim_yaw_sweep4/params_end_swarm_commander.yaml
python3 /home/jeremychia/AirStack-starling-max2/tools/lib/changes_log.py diff /home/jeremychia/flight_logs/sim/sim_yaw_sweep4 -o /home/jeremychia/AirStack-starling-max2/docs/record/sim_yaw_sweep4/params_diff.txt
docker exec airstack-robot-desktop-1 pkill -INT -f python3 metrics_node.py
# == phase collect ==  2026-11-02 20:14:24 +08
docker exec isaac-sim bash -c 'for f in /tmp/tmp*/log/*/*.ulg; do [ $(stat -c %Y $f) -gt 1793620798 ] && echo $f; done'  # -> ulog_list.txt
docker exec isaac-sim python3 -c "from pyulog import ULog; print(ULog(f, message_name_filter_list=['vehicle_local_position']).initial_parameters.get('MAV_SYS_ID'))"  # -> ulog_sysid_map.txt
docker cp isaac-sim:<ulog> /home/jeremychia/flight_logs/sim/sim_yaw_sweep4/drone_<sid-1>_sysid<sid>_<basename>.ulg
docker exec isaac-sim python3 -c "from pyulog import ULog; p=ULog('/tmp/tmpv56qeuox/log/2026-11-02/12_00_11.ulg', message_name_filter_list=['vehicle_local_position']).initial_parameters; ..."  # -> params_ulog.txt
docker cp /home/jeremychia/AirStack-starling-max2/tools/hover_step_timescale.py isaac-sim:/tmp/
docker exec isaac-sim python3 /tmp/hover_step_timescale.py /tmp/tmpv56qeuox/log/2026-11-02/12_00_11.ulg  # -> px4_arm_times.txt
python3 /home/jeremychia/AirStack-starling-max2/tools/live/ulog_yaw_dump.py /home/jeremychia/flight_logs/sim/sim_yaw_sweep4/drone_1_sysid2_12_00_11.ulg -o /home/jeremychia/flight_logs/sim/sim_yaw_sweep4/px4_drone_1.csv --params-out /home/jeremychia/AirStack-starling-max2/docs/record/sim_yaw_sweep4/px4_param_changes.txt
python3 /home/jeremychia/AirStack-starling-max2/tools/lib/changes_log.py ulog /home/jeremychia/flight_logs/sim/sim_yaw_sweep4/drone_1_sysid2_12_00_11.ulg -o /home/jeremychia/AirStack-starling-max2/docs/record/sim_yaw_sweep4/px4_param_changes_all.txt
# == phase down ==  2026-11-02 20:14:40 +08
docker exec airstack-robot-desktop-1 pkill -INT -f ground_control.launch.py
docker exec airstack-robot-desktop-1 bash -c 'ls -d /root/AirStack/robot/ros_ws/bags/yaw_step_* | tail -1'; docker cp airstack-robot-desktop-1:<bag> /home/jeremychia/flight_logs/sim/sim_yaw_sweep4/
docker exec airstack-robot-desktop-1 bash -ic 'python3 /tmp/svg_test/bag_recompute.py /root/AirStack/robot/ros_ws/bags/yaw_step_20261102_120039 --test-dir /tmp/svg_test --meta-from /tmp/svg_test/metrics.csv -o /tmp/svg_test/metrics_bag.csv'
docker exec airstack-robot-desktop-1 rm -rf /root/AirStack/robot/ros_ws/bags/yaw_step_20261102_120039
docker exec airstack-robot-desktop-1 pkill -INT -f launch_sim_interfaces.sh
docker exec isaac-sim pkill -INT -f svg_multi_drone_single_domain.py
docker exec isaac-sim pkill -9 -x px4
docker exec airstack-robot-desktop-1 pkill -f position_setpoint_pub
python3 /home/jeremychia/AirStack-starling-max2/tools/lib/report.py /home/jeremychia/AirStack-starling-max2/tools/sim_tests/yaw_step /home/jeremychia/AirStack-starling-max2/docs/record/sim_yaw_sweep4 --heavy /home/jeremychia/flight_logs/sim/sim_yaw_sweep4 --ledger 28 --issue NEAR-789
