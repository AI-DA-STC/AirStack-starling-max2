#!/usr/bin/env bash
# GPU smoke test for the exploration image: import cuvslam + gtsam, run the SDK's own synthetic
# tracking tests (no dataset needed). Run from the host: ./scripts/smoke_test.sh
set -euo pipefail
cd "$(dirname "$0")/.."
docker run --rm --gpus all -e RERUN=0 -v "$PWD":/exploration -w /exploration localisation-exploration:cu12 bash -lc '
set -e
echo "== GPU"; nvidia-smi --query-gpu=name,driver_version,memory.used --format=csv,noheader
echo "== imports"; python3 -c "import cuvslam, gtsam, evo, numpy, scipy; print(\"cuvslam\", getattr(cuvslam, \"__version__\", \"?\"), \"gtsam\", \"ok\", \"numpy\", numpy.__version__, \"scipy\", scipy.__version__)"
echo "== cuVSLAM synthetic tests (python/test)"
cd data/cuVSLAM-src/python/test
python3 -m unittest -v test_bindings test_image_format test_tracking 2>&1 | tail -25
'
