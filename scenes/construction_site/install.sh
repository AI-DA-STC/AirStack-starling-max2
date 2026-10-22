#!/usr/bin/env bash
# Install the construction-site arena where the isaac-sim container can see it.
# Layout under ~/docker/isaac-sim/data/scenes/construction_site (= /isaac-sim/.local/share/ov/data/scenes/construction_site):
#   construction_site_arena.usda                       <- this folder (wrapper: site + props, no Meerkat)
#   AI_training/Construction_site/Scene02*.usd         <- the user's scene (Documents/Meerkat_robot_JAZZY/...)
#   environments/construction_site/Assets/             <- its 600 asset USDs + 682 textures
# The data dir is root-owned, so everything goes in through the container (docker cp).
set -euo pipefail
SRC="${SCENE_SRC:-$HOME/Documents/Meerkat_robot_JAZZY/Simulation Files}"
D=/isaac-sim/.local/share/ov/data/scenes/construction_site
cd "$(dirname "$0")"
docker ps --format '{{.Names}}' | grep -qx isaac-sim || { echo "isaac-sim container is not up"; exit 1; }
docker exec isaac-sim mkdir -p "$D/AI_training/Construction_site" "$D/environments/construction_site"
docker cp construction_site_arena.usda "isaac-sim:$D/"
if ! docker exec isaac-sim test -d "$D/environments/construction_site/Assets"; then
  docker cp "$SRC/environments/construction_site/Assets" "isaac-sim:$D/environments/construction_site/"
  for f in Scene02_nohumans.usd Scene02.usd; do docker cp "$SRC/AI_training/Construction_site/$f" "isaac-sim:$D/AI_training/Construction_site/"; done
fi
docker exec isaac-sim bash -c "du -sh $D && ls $D"
echo "launch with:  ENV_USD=$D/construction_site_arena.usda  (plus the usual Isaac tab line)"
