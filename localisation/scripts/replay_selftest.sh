#!/usr/bin/env bash
# Self-test of the NEAR-860 replay without Isaac: build a 20 s synthetic stereo bag (textured wall, known path),
# replay it twice offline, and check (1) every frame tracked, (2) the two replays are identical, (3) the path
# follows the known truth to < 5 cm RMSE. A tooling check, not a sim result. Run on the LAPTOP; ~1 min.
set -euo pipefail
cd "$(dirname "$0")/.."
docker run --rm --gpus all --network none -v "$PWD":/exploration -w /exploration localisation-exploration:cu12 bash -lc '
set -e
T=$(mktemp -d)
python3 scripts/make_synthetic_stereo_bag.py $T/bag 20 | tail -1
python3 scripts/replay_offline.py $T/bag $T/a.tum | tail -2
python3 scripts/replay_offline.py $T/bag $T/b.tum > /dev/null
python3 - "$T" <<"EOF"
import json, sys
import numpy as np
sys.path.insert(0, "scripts")
import compare_replay as CR
T = sys.argv[1]
st = json.load(open(f"{T}/a_stats.json"))
a, b = CR.load_tum(f"{T}/a.tum"), CR.load_tum(f"{T}/b.tum")
s = a[:, 0] - 1000.0
truth = np.c_[a[:, 0], 0 * s, -0.8 * np.sin(0.4 * s), -0.3 * np.sin(0.25 * s)]   # FLU: y = -x_opt, z = -y_opt
same, vs_truth = CR.compare(a, b), CR.compare(truth, a)
checks = [("every frame tracked", st["tracked"] == st["pairs"] == 500, f"{st["tracked"]}/{st["pairs"]}"),
          ("two replays identical", same["rmse_m"] == 0.0, f"RMSE {same["rmse_m"]:.6f} m"),
          ("path follows the truth", vs_truth["rmse_m"] < 0.05, f"RMSE {vs_truth["rmse_m"]:.3f} m (gate 0.05)")]
for name, ok, val in checks:
    print(f"{"PASS" if ok else "FAIL"}  {name}: {val}")
sys.exit(0 if all(ok for _, ok, _ in checks) else 1)
EOF
rm -rf $T' 2>&1 | grep -v '^Sourcing'
