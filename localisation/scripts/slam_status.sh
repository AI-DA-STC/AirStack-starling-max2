#!/usr/bin/env bash
# What is running on the SLAM side, and the tracker's last status line.
C=localisation-exploration
docker ps --format '{{.Names}}' | grep -qx "$C" || { echo "$C not running"; exit 0; }
docker exec -w /exploration "$C" bash -lc 'echo "node:    $(pgrep -f "[c]uvslam_stereo_node.py" >/dev/null && echo running || echo stopped)"; echo "bridge:  $(pgrep -f "[f]oxglove_bridge.*8766" >/dev/null && echo running || echo stopped)"; echo "studio:  $(pgrep -f "[f]oxglove-studio.*studio-data" >/dev/null && echo running || echo stopped)"; echo "bag:     $(pgrep -f "[r]os2 bag record" >/dev/null && echo recording || echo idle)"; timeout 12 ros2 topic echo --no-daemon --once /drone_1/cuvslam/status 2>/dev/null | head -1 | cut -c1-220' 2>&1 | grep -v '^Sourcing'
