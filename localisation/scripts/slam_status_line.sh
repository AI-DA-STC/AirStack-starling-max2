#!/usr/bin/env bash
# One status line for the SLAM side. Runs INSIDE the exploration container (called by slam_up.sh every 3 s).
# Prints: node:up bridge:up studio:up bag:idle  frames:N tracked:N lost:N rate:N Hz track_ms:N  + the last new node-log lines.
cd /exploration
up() { pgrep -f "$1" >/dev/null && echo "$2" || echo "$3"; }
st="node:$(up '[c]uvslam_stereo_node.py' up DOWN) bridge:$(up '[f]oxglove_bridge.*8766' up DOWN) studio:$(up '[f]oxglove-studio.*studio-data' up closed) bag:$(up '[r]os2 bag record' REC idle)"
# ros2 topic echo wraps the long JSON string over several YAML lines -> parse it as YAML, then as JSON
timeout 6 ros2 topic echo --no-daemon --once --full-length /drone_1/cuvslam/status > /tmp/st_raw.txt 2>/dev/null
python3 - "$st" /tmp/st_raw.txt <<'PY'
import json, sys, yaml
st = sys.argv[1]
raw = open(sys.argv[2]).read()
try:
    doc = next(d for d in yaml.safe_load_all(raw) if isinstance(d, dict) and "data" in d)
    d = json.loads(doc["data"])
    print(f"{st}  frames:{d['frames']} tracked:{d['tracked']} lost:{d['lost']} rate:{d['rate_hz']}Hz track_ms:{d['track_ms_p50']}")
except StopIteration:
    print(st, " (no tracker status yet)")
except Exception as e:
    print(st, f" status: (parse error: {e})")
PY
# new node-log lines since the last call (follower started by slam_up.sh)
grep -vE '^\s*$' /tmp/node_follow.log 2>/dev/null | tail -n 3
: > /tmp/node_follow.log 2>/dev/null || true
