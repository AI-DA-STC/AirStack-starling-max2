#!/usr/bin/env bash
# Open a shell in the exploration container (starts it via docker/up.sh if needed).
set -euo pipefail
cd "$(dirname "$0")/.."
docker ps --format '{{.Names}}' | grep -qx localisation-exploration || ./docker/up.sh
exec docker exec -it -w /exploration localisation-exploration bash "$@"
