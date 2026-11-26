#!/bin/bash
# after.sh "<job line>" <file> [<file> ...]: when every file exists, put the job line next in jobs.txt
P=$(cd "$(dirname "$0")" && pwd); cd "$P"; line=$1; shift
for f in "$@"; do until [ -f "$f" ]; do sleep 20; done; done
n=$(wc -l < dispatch.log)
python3 - "$n" "$line" <<'PY'
import sys
n, line = int(sys.argv[1]), sys.argv[2]
lines = open("jobs.txt").read().splitlines()
lines.insert(n, line)
open("jobs.new", "w").write("\n".join(lines) + "\n")
PY
mv jobs.new jobs.txt
echo "$(date +%H:%M) queued next: ${line%% *}" >> dispatch.log.after
