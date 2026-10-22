#!/usr/bin/env bash
# Score an estimate against a reference trajectory in a ROS 2 bag with evo (run INSIDE the
# exploration container). Usage: scripts/score_bag.sh <bag_dir> [ref_topic] [est_topic]
# Default ref = the drone's EKF2 odometry (labelled: NOT ground truth until the Isaac GT publisher exists).
set -euo pipefail
bag=${1:?usage: score_bag.sh <bag_dir> [ref_topic] [est_topic]}
ref=${2:-/drone_1/odometry_conversion/odometry}
est=${3:-/drone_1/cuvslam/odometry}
out="${bag%/}/evo"; mkdir -p "$out"
echo "== reference: $ref   (EKF2 on simulated GPS unless this is the GT topic)"
echo "== estimate : $est"
evo_traj bag2 "$bag" "$ref" "$est" --save_as_tum --no_warnings >/dev/null 2>&1 || true
mv -f ./*.tum "$out/" 2>/dev/null || true
echo "== APE (SE(3) aligned, translation)";
evo_ape bag2 "$bag" "$ref" "$est" -a --no_warnings --save_results "$out/ape_se3.zip" | tail -12
echo "== APE (unaligned, translation) — frame offset included";
evo_ape bag2 "$bag" "$ref" "$est" --no_warnings --save_results "$out/ape_raw.zip" | tail -12
echo "== RPE per 1 m (drift)";
evo_rpe bag2 "$bag" "$ref" "$est" -a --delta 1 --delta_unit m --no_warnings --save_results "$out/rpe_1m.zip" | tail -12
echo "results in $out"
