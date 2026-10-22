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
  # Scene02's /World/construction_site_withrobot is itself a reference to this file (and Map_draft1 may be referenced too)
  for f in construction_site_withrobot.usd construction_site_raw.usd Map_draft1; do
    [ -e "$SRC/environments/construction_site/$f" ] && docker cp "$SRC/environments/construction_site/$f" "isaac-sim:$D/environments/construction_site/"
  done
  for f in Scene02_nohumans.usd Scene02.usd; do docker cp "$SRC/AI_training/Construction_site/$f" "isaac-sim:$D/AI_training/Construction_site/"; done
fi
# Landscape2_asset.usd / Landscape_asset.usd carry ABSOLUTE /home/... paths from the UE4 export -> rewrite to relative in the
# installed copy (needs usd-core: python3 -m venv /tmp/usdenv && /tmp/usdenv/bin/pip install usd-core). The user's originals are untouched.
H="$HOME/docker/isaac-sim/data/scenes/construction_site/environments/construction_site/Assets"
VENV="$HOME/.venvs/usd"      # persistent (not /tmp: wiped on reboot)
[ -x "$VENV/bin/python" ] || { python3 -m venv "$VENV" && "$VENV/bin/pip" install -q usd-core scipy numpy; }
"$VENV/bin/python" -I fix_abs_paths.py "$H/Landscape2_asset.usd" "$H/Landscape_asset.usd" || { echo "terrain asset fix FAILED"; exit 1; }
# flattened derivatives (crop_site.py: one copy per unique material, textures beside the file). Default = full site
# (all 5.5k objects, 25k prims, 137 materials: 3 drones + camera at 4.3 GB VRAM / RTF 1.4 headless on 2026-10-22);
# r40 = 40 m around the flight spot (4.8k prims, 68 materials) as the light fallback.
ARENA="$HOME/docker/isaac-sim/data/scenes/construction_site/construction_site_arena.usda"
[ -f build/construction_site_r40.usdc ] || "$VENV/bin/python" -I crop_site.py "$ARENA" build --radius 40
[ -f build/construction_site_full.usdc ] || { "$VENV/bin/python" -I crop_site.py "$ARENA" build --radius 1000 && mv build/construction_site_r1000.usdc build/construction_site_full.usdc; }
docker cp build/construction_site_r40.usdc "isaac-sim:$D/"; docker cp build/construction_site_full.usdc "isaac-sim:$D/"
docker exec isaac-sim rm -rf "$D/textures"; docker cp build/textures "isaac-sim:$D/"
docker exec isaac-sim bash -c "du -sh $D && ls $D"
echo "launch with:  ENV_USD=$D/construction_site_full.usdc  (or construction_site_r40.usdc for the 40 m crop; plus the usual Isaac tab line)"
