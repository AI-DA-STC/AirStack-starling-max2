#!/usr/bin/env bash
# Host-side resource + WiFi watch for sim test steps. Run on the LAPTOP in its own terminal (or `&`):
#   scripts/sim_resources_watch.sh results/res_step2.log
# Every second: GPU memory/util, load average, Isaac /clock not needed here. Also tails the kernel log for the
# Intel WiFi firmware crash that killed the remote-desktop session on 2026-10-22 (iwlwifi "Error sending ..."),
# and ALERTS (does not kill) when VRAM > 11 GB or load1 > 20 or a WiFi error appears. Ctrl-C to stop.
log=${1:-/dev/stdout}
echo "# $(date '+%F %T') watch start; link: $(ip -br link | awk '$2=="UP"{print $1}' | tr '\n' ' ')" | tee -a "$log"
journalctl -kf -n 0 2>/dev/null | grep --line-buffered -E "iwlwifi.*(Error|error|reset|stuck)|blocked for more than" | while read -r l; do echo "$(date +%T) WIFI-ALERT $l" | tee -a "$log"; done &
jpid=$!
trap 'kill $jpid 2>/dev/null; exit 0' INT TERM
while true; do
  read -r gmem gtot gutil < <(nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits | tr -d ',' )
  load=$(cut -d' ' -f1 /proc/loadavg); avail=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
  flag=""
  [ "${gmem:-0}" -gt 11000 ] && flag="$flag VRAM-ALERT"
  [ "${load%.*}" -gt 20 ] 2>/dev/null && flag="$flag LOAD-ALERT"
  echo "$(date +%T) gpu ${gmem}/${gtot} MB ${gutil}%  load1 $load  ram_avail ${avail} MB$flag" | tee -a "$log"
  sleep 1
done
