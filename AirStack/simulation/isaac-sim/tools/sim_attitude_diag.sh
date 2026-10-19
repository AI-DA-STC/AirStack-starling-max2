#!/bin/bash
# Diagnostic: takeoff, record 25 s of attitude (roll/pitch deg), thrust and position for drone_1, then land.
# docker cp this file into the robot container (/tmp) and run: bash -ic /tmp/sim_attitude_diag.sh
cd ~/AirStack/robot/ros_ws && source install/setup.bash >/dev/null 2>&1
D=drone_1
timeout 20 ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger | grep -o "success=[A-Za-z]*"
timeout 25 ros2 topic echo /$D/interface/mavros/local_position/pose --field pose 2>/dev/null > /tmp/diag_pose.txt &
timeout 25 ros2 topic echo /$D/interface/mavros/setpoint_raw/target_attitude --field thrust 2>/dev/null > /tmp/diag_thrust.txt &
wait
timeout 20 ros2 service call /swarm_commander/land std_srvs/srv/Trigger | grep -o "success=[A-Za-z]*"
python3 - <<'PY'
import re, math
txt = open('/tmp/diag_pose.txt').read()
blocks = txt.split('---')
rows = []
for b in blocks:
    m = re.search(r'position:\s*x:\s*([-\d.e+]+)\s*y:\s*([-\d.e+]+)\s*z:\s*([-\d.e+]+)', b)
    q = re.search(r'orientation:\s*x:\s*([-\d.e+]+)\s*y:\s*([-\d.e+]+)\s*z:\s*([-\d.e+]+)\s*w:\s*([-\d.e+]+)', b)
    if not (m and q): continue
    x,y,z = map(float, m.groups()); qx,qy,qz,qw = map(float, q.groups())
    roll = math.degrees(math.atan2(2*(qw*qx+qy*qz), 1-2*(qx*qx+qy*qy)))
    pitch = math.degrees(math.asin(max(-1,min(1,2*(qw*qy-qz*qx)))))
    yaw = math.degrees(math.atan2(2*(qw*qz+qx*qy), 1-2*(qy*qy+qz*qz)))
    rows.append((x,y,z,roll,pitch,yaw))
n = len(rows); hz = n/25.0
print(f"pose samples {n} (~{hz:.0f} Hz)")
print(" t(s)   x      y      z     roll   pitch  yaw")
for i in range(0, n, max(1,int(hz))):
    x,y,z,r,p,yw = rows[i]; print(f"{i/hz:5.1f} {x:6.2f} {y:6.2f} {z:6.2f} {r:7.1f} {p:7.1f} {yw:7.1f}")
rs = [abs(r[3]) for r in rows]; ps=[abs(r[4]) for r in rows]
print(f"max |roll| {max(rs):.1f} deg, max |pitch| {max(ps):.1f} deg")
# dominant roll oscillation period: zero crossings
rr=[r[3] for r in rows]; zc=[i for i in range(1,n) if (rr[i-1]<0)!=(rr[i]<0)]
if len(zc)>2: print(f"roll zero-crossings {len(zc)} in 25 s -> ~{2*25/len(zc):.2f} s period")
th=[float(v) for v in re.findall(r'^([-0-9.e+]+)$', open('/tmp/diag_thrust.txt').read(), re.M)]
print(f"thrust samples {len(th)}: min {min(th):.2f} max {max(th):.2f} mean {sum(th)/len(th):.2f}") if th else print("no thrust samples")
PY
