#!/bin/bash
# M1 "CBF crossing" check: with the commander running a crossing scenario (cbf_sim.yaml default
# `antipodal`), takeoff, wait for `start`, then sample /svg/commander_status for DURATION s and
# report the minimum pairwise distance and whether the CBF was active / emergency fired. Lands.
# docker cp into the robot container, run from an interactive shell: bash -ic /tmp/sim_cbf_crossing_test.sh
DURATION=${1:-45}
cd ~/AirStack/robot/ros_ws && source install/setup.bash >/dev/null 2>&1
wait_s(){ timeout "$1" ros2 topic echo /clock >/dev/null 2>&1; }
svc(){ timeout 20 ros2 service call /swarm_commander/$1 std_srvs/srv/Trigger 2>/dev/null | grep -o "success=[A-Za-z]*, message='[^']*'"; }
echo "[$(date +%T)] takeoff: $(svc takeoff)"
for i in $(seq 1 30); do wait_s 3; r=$(svc start); case "$r" in success=True*) echo "[$(date +%T)] start: $r"; break;; esac
  [ "$i" = 30 ] && { echo "start never accepted: $r"; svc land; exit 1; }; done
timeout "$DURATION" ros2 topic echo /svg/commander_status --field data 2>/dev/null | grep -v '^---' > /tmp/cbf_status.txt
echo "[$(date +%T)] land: $(svc land)"
python3 - <<'PY'
import json, itertools, math
rows=[json.loads(l) for l in open('/tmp/cbf_status.txt') if l.strip().startswith('{')]
mind=9e9; active=set(); emergency=0; breach=0
for j in rows:
    P={d['name']:d['position'] for d in j['drones']}
    for a,b in itertools.combinations(P,2):
        dd=math.dist(P[a],P[b]); mind=min(mind,dd)
    active.update(j['cbf'].get('active',[])); emergency+=bool(j['cbf'].get('emergency')); breach+=bool(j.get('fence_breached'))
print(f"status samples {len(rows)} | min pairwise distance {mind:.2f} m (2r = 1.10) | CBF corrected: {sorted(active) or 'nobody'} | emergency samples {emergency} | fence-breach samples {breach}")
PY
