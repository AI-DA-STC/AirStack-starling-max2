#!/usr/bin/env bash
# Run a Python script with the Isaac Sim image's interpreter, pxr (USD) and the
# vendored Pegasus extension importable — no GPU, no Kit app, no running container.
#   tools/isaac_python.sh path/to/script.py [args...]      (paths relative to the repo root)
#   tools/isaac_python.sh -m unittest discover -s <dir>     (any python.sh argument works)
# Set ISAAC_PIP="pkg1 pkg2" to pip-install extras into the throw-away container first.
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../../../.." && pwd)          # AirStack-starling-max2 repo root
IMAGE=${ISAAC_IMAGE:-airlab-docker.andrew.cmu.edu/airstack/airstack:v0.18.0_isaac-sim}
docker run --rm --entrypoint "" -v "$REPO":/repo -w /repo -e ISAAC_PIP="${ISAAC_PIP:-}" "$IMAGE" bash -c '
  set -e
  PXR=$(find /isaac-sim -type d -name pxr 2>/dev/null | xargs -n1 dirname | sort -u | tr "\n" ":")
  LIBS=$(find /isaac-sim \( -name "libusd_*.so*" -o -name "libtf.so*" \) 2>/dev/null | xargs -n1 dirname | sort -u | tr "\n" ":")
  export PYTHONPATH="/repo/AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator:${PXR}${PYTHONPATH:-}"
  export LD_LIBRARY_PATH="${LIBS}${LD_LIBRARY_PATH:-}"
  if [ -n "$ISAAC_PIP" ]; then /isaac-sim/python.sh -m pip install -q $ISAAC_PIP; fi
  cd /repo && exec /isaac-sim/python.sh "$@"' _ "$@" 2>&1 | grep -v -E "^\[[0-9.]+s\]|^\[Warning\]|Warning: |^There was an error running python$"
exit "${PIPESTATUS[0]}"
