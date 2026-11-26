#!/bin/bash
# queue.sh <logfile> <script args...>: wait until fewer than 4 pilot jobs run, then run one (keeps the 4-job limit)
log=$1; shift
P=$(cd "$(dirname "$0")" && pwd)
while [ "$(pgrep -fc "scratchpad/pilots/s[0-9a-z_]*\.py")" -ge 4 ]; do sleep 20; done
exec "$P/run.sh" "$@" > "$P/$log" 2>&1
