#!/bin/bash
# dispatch.sh: run the lines of jobs.txt ("<log> <script> <args...>") in order, at most 4 pilot jobs at once.
# Lines appended later are picked up. A line starting with "#" is skipped. Stops when the file "STOP" exists.
P=$(cd "$(dirname "$0")" && pwd); cd "$P"; n=$(cat dispatch.log 2>/dev/null | wc -l)
while [ ! -f STOP ]; do
  total=$(wc -l < jobs.txt)
  if [ "$n" -lt "$total" ]; then
    if [ "$(pgrep -fc "python -u .*scratchpad/pilots/[a-z0-9_]*\.py")" -lt 4 ]; then
      n=$((n+1)); line=$(sed -n "${n}p" jobs.txt)
      case "$line" in "#"*|"") continue;; esac
      set -- $line; log=$1; shift
      echo "$(date +%H:%M) start $line" >> dispatch.log
      nohup ./run.sh "$@" > "logs/$log" 2>&1 &
      sleep 15
    else sleep 15; fi
  else sleep 30; fi
done
