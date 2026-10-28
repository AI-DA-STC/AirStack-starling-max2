# == phase precheck ==  2026-10-28 23:30:25 +08
# == phase up ==  2026-10-28 23:30:25 +08
cd /home/jeremychia/AirStack-starling-max2/AirStack && ./airstack.sh up
docker exec isaac-sim mkdir -p /tmp/hover_step
docker exec airstack-robot-desktop-1 mkdir -p /tmp/hover_step
docker exec airstack-robot-desktop-1 bash -ic 'ros2 daemon stop; ros2 topic list --no-daemon --spin-time 5' | grep -E '/fmu/|/poses|/pose$'
git -C /home/jeremychia/AirStack-starling-max2 rev-parse HEAD; git -C /home/jeremychia/AirStack-starling-max2 status --porcelain -- tools | wc -l   # -> run_meta.txt
# == phase watch ==  2026-10-28 23:30:31 +08
nohup /home/jeremychia/AirStack-starling-max2/localisation/scripts/sim_resources_watch.sh /home/jeremychia/AirStack-starling-max2/docs/record/sim_hover_step_run3/res_watch.log &
# == phase isaac ==  2026-10-28 23:30:34 +08
docker exec -d isaac-sim bash -ic 'PYTHONUNBUFFERED=1 DRONE_USD=/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd PX4_VEHICLE_MODEL=pegasus_starling2max NUM_ROBOTS=3 SVG_DOMAIN_ID=1 PLAY_SIM_ON_START=true ISAAC_SIM_HEADLESS=true PYTHONPATH="$ISAAC_SIM_PYTHONPATH" /isaac-sim/python.sh /isaac-sim/AirStack/simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py --ext-folder ~/.local/share/ov/data/documents/Kit/shared/exts > /tmp/hover_step/isaac.log 2>&1'
# == phase interfaces ==  2026-10-28 23:30:50 +08
docker exec -d airstack-robot-desktop-1 bash -ic 'cd ~/AirStack/robot/ros_ws && ./src/svg_ground_control/scripts/launch_sim_interfaces.sh 3 > /tmp/hover_step/interfaces.log 2>&1'
for N in 1 2 3: docker exec airstack-robot-desktop-1 bash -ic 'timeout 10 ros2 topic echo --once /drone_$N/interface/mavros/state' | grep '^connected: true'
for N in 1 2 3: docker exec airstack-robot-desktop-1 bash -ic 'timeout 10 ros2 topic echo --once /drone_$N/odometry_conversion/odometry --field pose.pose.position'  (retry <= 90 s)
docker exec airstack-robot-desktop-1 bash -ic 'timeout 15 ros2 topic hz /drone_1/odometry_conversion/odometry -w 200'
docker exec airstack-robot-desktop-1 bash -ic 'ros2 topic info /clock; echo clock_rc=$?'   # 0 = /clock exists, 1 = unknown topic
# == phase commander ==  2026-10-28 23:31:24 +08
docker exec -d airstack-robot-desktop-1 bash -ic 'cd ~/AirStack/robot/ros_ws && ros2 launch svg_ground_control ground_control.launch.py config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/cbf_sim.yaml scenario:=goal record_bag:=true bag_prefix:=hover_step > /tmp/hover_step/commander.log 2>&1'
docker exec airstack-robot-desktop-1 bash -ic 'timeout 15 ros2 topic echo --once /svg/commander_status --field data'  # -> status_pre.json
# == phase params ==  2026-10-28 23:31:32 +08
docker exec airstack-robot-desktop-1 bash -ic 'ros2 service list | grep /drone_1/interface/mavros/param; ros2 node list | grep /drone_1/interface/mavros'
docker exec airstack-robot-desktop-1 bash -ic 'ros2 service call /drone_1/interface/mavros/param/pull mavros_msgs/srv/ParamPull "{force_pull: false}"; ros2 param get <param node> <P>'
# == phase fly ==  2026-10-28 23:32:52 +08
docker cp /home/jeremychia/AirStack-starling-max2/tools/sim_hover_step_test.sh airstack-robot-desktop-1:/tmp/
docker cp /home/jeremychia/AirStack-starling-max2/tools/analyze_step.py airstack-robot-desktop-1:/tmp/
docker exec airstack-robot-desktop-1 bash -c rm -f /tmp/ascent.txt /tmp/step_x_*.txt /tmp/step_z_*.txt /tmp/drone_1_*.csv
timeout 720 docker exec airstack-robot-desktop-1 bash -ic 'STEPS_PER_AXIS=3 /tmp/sim_hover_step_test.sh drone_1'  # -> test_stdout.log (container clock, UTC)
for N in 1 2 3: docker exec airstack-robot-desktop-1 bash -ic 'timeout 10 ros2 topic echo --once /drone_$N/interface/mavros/state' | grep -oE '^armed: (true|false)'  # -> armed_post.txt
docker exec airstack-robot-desktop-1 grep -E 'touchdown at z=|landed, disarmed|disarm not accepted' /tmp/hover_step/commander.log  # -> landing_evidence.txt
# == phase collect ==  2026-10-28 23:35:32 +08
docker exec airstack-robot-desktop-1 python3 /tmp/analyze_step.py /tmp/<trace>.txt <axis> <delta> [hz]  (traces: ascent:z:1.2 step_x_1:x:1.0 step_z_1:z:1.0 step_x_2:x:-1.0 step_z_2:z:-1.0 step_x_3:x:1.0 step_z_3:z:1.0)  # -> analyze.txt
docker exec isaac-sim bash -c 'for f in /tmp/tmp*/log/*/*.ulg; do [ $(stat -c %Y $f) -gt 1793201434 ] && echo $f; done'  # -> ulog_list.txt
docker exec isaac-sim python3 -c "from pyulog import ULog; print(ULog(f, message_name_filter_list=['vehicle_local_position']).initial_parameters.get('MAV_SYS_ID'))"  # -> ulog_sysid_map.txt
docker cp isaac-sim:<ulog> /home/jeremychia/flight_logs/sim/sim_hover_step_run3/drone_<sid-1>_sysid<sid>_<basename>.ulg
docker exec isaac-sim python3 -c "from pyulog import ULog; p=ULog('/tmp/tmpk5x2uqc4/log/2026-10-28/15_30_45.ulg', message_name_filter_list=['vehicle_local_position']).initial_parameters; ..."  # -> params_ulog.txt
docker cp /home/jeremychia/AirStack-starling-max2/tools/hover_step_timescale.py isaac-sim:/tmp/
docker exec isaac-sim python3 /tmp/hover_step_timescale.py /tmp/tmpk5x2uqc4/log/2026-10-28/15_30_45.ulg  # -> px4_arm_times.txt
# == phase down ==  2026-10-28 23:35:37 +08
docker exec airstack-robot-desktop-1 pkill -INT -f ground_control.launch.py
docker exec airstack-robot-desktop-1 bash -c 'ls -d /root/AirStack/robot/ros_ws/bags/hover_step_* | tail -1'; docker cp airstack-robot-desktop-1:<bag> /home/jeremychia/flight_logs/sim/sim_hover_step_run3/
docker cp /home/jeremychia/AirStack-starling-max2/tools/hover_step_bag.py airstack-robot-desktop-1:/tmp/
docker exec airstack-robot-desktop-1 bash -ic 'python3 /tmp/hover_step_bag.py /root/AirStack/robot/ros_ws/bags/hover_step_20261028_153125 drone_1 /tmp/drone_1'; docker cp airstack-robot-desktop-1:/tmp/drone_1_{odom,cmd,state}.csv /home/jeremychia/AirStack-starling-max2/docs/record/sim_hover_step_run3/
docker exec airstack-robot-desktop-1 rm -rf /root/AirStack/robot/ros_ws/bags/hover_step_20261028_153125
docker exec airstack-robot-desktop-1 pkill -INT -f launch_sim_interfaces.sh
docker exec isaac-sim pkill -INT -f svg_multi_drone_single_domain.py
docker exec isaac-sim pkill -9 -x px4
docker exec airstack-robot-desktop-1 pkill -f position_setpoint_pub
# == phase analyse ==  2026-10-28 23:36:41 +08
python3 /home/jeremychia/AirStack-starling-max2/tools/hover_step_analysis.py --odom /home/jeremychia/AirStack-starling-max2/docs/record/sim_hover_step_run3/drone_1_odom.csv --cmd /home/jeremychia/AirStack-starling-max2/docs/record/sim_hover_step_run3/drone_1_cmd.csv --state /home/jeremychia/AirStack-starling-max2/docs/record/sim_hover_step_run3/drone_1_state.csv --px4-arm-times /home/jeremychia/AirStack-starling-max2/docs/record/sim_hover_step_run3/px4_arm_times.txt --step-delta 1.0 --drone drone_1 -o /home/jeremychia/AirStack-starling-max2/docs/record/sim_hover_step_run3/bag_analysis.json
python3 /home/jeremychia/AirStack-starling-max2/tools/hover_step_plot.py /home/jeremychia/AirStack-starling-max2/docs/record/sim_hover_step_run3
# == phase report ==  2026-10-28 23:36:42 +08
python3 /home/jeremychia/AirStack-starling-max2/tools/hover_step_report.py /home/jeremychia/AirStack-starling-max2/docs/record/sim_hover_step_run3 --heavy /home/jeremychia/flight_logs/sim/sim_hover_step_run3
# == phase report (re-run) ==  2026-10-29 01:41:30 +08
python3 /home/jeremychia/AirStack-starling-max2/tools/hover_step_report.py /home/jeremychia/AirStack-starling-max2/docs/record/sim_hover_step_run3 --heavy /home/jeremychia/flight_logs/sim/sim_hover_step_run3 --ledger 19
