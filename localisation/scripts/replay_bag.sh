#!/usr/bin/env bash
# Replay a recorded sim flight's stereo images through a fresh cuVSLAM node (NEAR-860). Run on the LAPTOP.
# Needs no Isaac and touches nothing live: a throwaway container with no network reads the bag directly and
# runs every stereo pair through the live node's own tracking code (scripts/replay_offline.py: no DDS, so no
# dropped frames and no timing effects), then compares the new path with the path cuVSLAM produced live
# during the flight (when the bag has one). When
# scripts/score_run.sh already copied the PX4 ulog into the bag folder, the replay is also scored against it.
# Usage: scripts/replay_bag.sh <run_name> [drone] [--out <name>]
# Writes results/bags/<out>/ (default <run>_replay): replay.log, cuvslam_<drone>_replay.tum (+ _stats.json),
# replay_vs_live.json, and cuvslam_<drone>_replay_vs_ulog.json if a ulog was there.
set -euo pipefail
cd "$(dirname "$0")/.."
run=""; d=drone_1; out=""
while [ $# -gt 0 ]; do
  case "$1" in
    --out) out=${2:?--out needs a name}; shift 2 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    -*) echo "unknown option $1" >&2; exit 2 ;;
    *) if [ -z "$run" ]; then run=$1; else d=$1; fi; shift ;;
  esac
done
[ -n "$run" ] || { echo "usage: scripts/replay_bag.sh <run_name> [drone] [--out <name>]" >&2; exit 2; }
out=${out:-${run}_replay}
bag=results/bags/$run
cam=/$d/sensors/front_stereo
[ -f "$bag/metadata.yaml" ] || { echo "no bag at $bag (metadata.yaml missing)" >&2; exit 2; }
for t in left/image_rect right/image_rect left/camera_info right/camera_info; do
  grep -q "name: $cam/$t\$" "$bag/metadata.yaml" || {
    echo "$bag has no $cam/$t — it was recorded without images (before NEAR-860), so it cannot be replayed" >&2; exit 2; }
done
[ ! -e "results/bags/$out" ] || { echo "results/bags/$out already exists — pick another --out" >&2; exit 2; }
C=localisation-replay
! docker ps -a --format '{{.Names}}' | grep -qx "$C" || { echo "container $C exists — another replay running? (docker rm -f $C)" >&2; exit 2; }

mkdir -p "results/bags/$out"
trap 'docker rm -f "$C" >/dev/null 2>&1 || true' EXIT
docker run -d --rm --name "$C" --gpus all --network none \
  -v "$PWD":/exploration -w /exploration localisation-exploration:cu12 sleep infinity >/dev/null
ex() { docker exec -w /exploration "$C" bash -lc "$*" 2>&1 | grep -v '^Sourcing' || true; }
o=results/bags/$out

echo "replaying $bag through cuVSLAM (offline, every frame) ..."
ex "python3 -u scripts/replay_offline.py $bag $o/cuvslam_${d}_replay.tum --drone $d 2>&1 | tee $o/replay.log" | grep -E 'tracker ready|replay:|recording:|Error|error' || true
[ -s "$o/cuvslam_${d}_replay.tum" ] || { echo "REPLAY FAILED: no poses — see $o/replay.log"; exit 1; }

if grep -q "name: /$d/cuvslam/odometry\$" "$bag/metadata.yaml"; then
  ex "cd $o && evo_traj bag2 ../$run /$d/cuvslam/odometry --save_as_tum --no_warnings >/dev/null 2>&1; mv -f ${d}_cuvslam_odometry.tum cuvslam_${d}_live.tum 2>/dev/null"
  if [ -s "$o/cuvslam_${d}_live.tum" ]; then
    ex "python3 scripts/compare_replay.py $o/cuvslam_${d}_live.tum $o/cuvslam_${d}_replay.tum --json $o/replay_vs_live.json"
  else echo "the bag's live cuVSLAM path is empty — no replay-vs-live comparison"; fi
else echo "the bag has no live cuVSLAM path — no replay-vs-live comparison"; fi

ulog=$(ls "$bag"/${d}_sysid*.ulg 2>/dev/null | head -1 || true)
if [ -n "$ulog" ]; then
  ex "python3 scripts/score_vs_ulog.py $o/cuvslam_${d}_replay.tum $ulog" | tail -3
else echo "no PX4 ulog in $bag (run scripts/score_run.sh $run first to score the replay against PX4)"; fi
ex "chown -R 1000:1000 /exploration/$o"
echo "done: $o"
