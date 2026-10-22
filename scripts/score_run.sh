#!/usr/bin/env bash
# Score one recorded sim run against the drone's PX4 ulog. Run on the HOST (it uses docker cp + docker exec).
# Usage: scripts/score_run.sh <run_name> [drone_index] [ulog_path_in_isaac]   e.g. scripts/score_run.sh sim_cam_run2 1
# Needs: the isaac-sim container still up (the ulog lives there) and the exploration container running
# (./docker/run.sh in another terminal).
set -euo pipefail
cd "$(dirname "$0")/.."
run=${1:?usage: score_run.sh <run_name> [drone_index]}
idx=${2:-1}
sysid=$((idx + 1))
bag=results/bags/$run
[ -d "$bag" ] || { echo "no bag at $bag"; exit 1; }
# ulog: 3rd arg if given, else the sysid-matching ulog whose end time is closest to the bag's end time
# (several flights per sim session -> several ulogs; "newest" would score every bag against the last flight)
ulog=${3:-}
if [ -z "$ulog" ]; then
  bag_end=$(stat -c %Y "$bag"/*.mcap | sort -n | tail -1)
  ulog=$(docker exec isaac-sim bash -c 'for f in /tmp/tmp*/log/*/*.ulg; do echo "$(stat -c %Y "$f") $f"; done'     | awk -v b="$bag_end" '{d=$1-b; if(d<0)d=-d; print d, $2}' | sort -n | head -8 | cut -d" " -f2 | while read -r f; do
    s=$(docker exec isaac-sim python3 -c "from pyulog import ULog; print(ULog('$f', message_name_filter_list=['vehicle_local_position']).initial_parameters.get('MAV_SYS_ID'))")
    [ "$s" = "$sysid" ] && { echo "$f"; break; }
  done)
fi
[ -n "$ulog" ] || { echo "no ulog with MAV_SYS_ID=$sysid found in isaac-sim"; exit 1; }
echo "ulog for drone_$idx (sysid $sysid): $ulog"
docker cp "isaac-sim:$ulog" - | docker cp - "localisation-exploration:/exploration/$bag/"
docker exec localisation-exploration bash -lc "cd /exploration/$bag && mv -f \$(basename $ulog) drone_${idx}_sysid${sysid}.ulg \
  && evo_traj bag2 . /drone_${idx}/cuvslam/odometry --save_as_tum --no_warnings >/dev/null 2>&1 \
  && mv -f drone_${idx}_cuvslam_odometry.tum cuvslam_drone_${idx}.tum \
  && python3 /exploration/scripts/score_vs_ulog.py cuvslam_drone_${idx}.tum drone_${idx}_sysid${sysid}.ulg \
  && python3 /exploration/scripts/diag_axes.py cuvslam_drone_${idx}.tum drone_${idx}_sysid${sysid}.ulg | tail -1 \
  && chown -R 1000:1000 /exploration/results" 2>&1 | grep -v Sourcing
echo "see $bag/cuvslam_drone_${idx}_vs_ulog.json and $bag/cuvslam_drone_${idx}_diag.png"
