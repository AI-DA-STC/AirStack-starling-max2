#!/usr/bin/env bash
# Install the SVG Teleop panel into Foxglove Studio's extensions folder (sim only, NEAR-789).
# Usage: install.sh [dest-dir]     default dest: ~/.foxglove-studio/extensions (where Studio 2.53.1 looks)
# Replaces its own folder <dest>/nearlab.svg-teleop-1.0.0 each time, so running it twice is the same as once.
# Only package.json and dist/ are copied: test/ stays out. slam_up.sh runs this inside the exploration container.
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)/svg-teleop"
DEST="${1:-$HOME/.foxglove-studio/extensions}/nearlab.svg-teleop-1.0.0"
rm -rf "$DEST"
mkdir -p "$DEST"
cp "$SRC/package.json" "$DEST/"
cp -r "$SRC/dist" "$DEST/"
echo "SVG Teleop panel installed in $DEST"
