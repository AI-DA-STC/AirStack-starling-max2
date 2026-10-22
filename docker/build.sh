#!/usr/bin/env bash
# Build the exploration image on top of the CMU robot image. Context = data/ (for the wheel).
set -euo pipefail
cd "$(dirname "$0")/.."
docker build -f docker/Dockerfile -t localisation-exploration:cu12 data/
echo "built localisation-exploration:cu12"
