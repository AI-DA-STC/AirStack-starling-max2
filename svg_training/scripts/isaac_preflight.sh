#!/usr/bin/env bash
# Check the network and the GPU before every Isaac Sim launch (S2b plan D13). Run it on the host, not in the container.
#
#   scripts/isaac_preflight.sh
#
# Prints `nvidia-smi` and the network state, then exits:
#   0   go;
#   10  BLOCKED: no Ethernet device is connected and a remote-desktop program is running. Starting Isaac Sim with a
#       window over remote desktop on WiFi has crashed this laptop's WiFi firmware (CLAUDE.md "Known trap"). The
#       owner may approve headless launches in this state; the caller records that approval, this script does not;
#   11  the GPU is in use: a compute process other than this shell's holds more than 500 MiB (the AirStack
#       simulator, a flight session or another run). The process list is printed for the lead to check.
set -u

GPU_MIB_MAX=500
RD_PATTERN='gnome-remote-desktop|xrdp|x11vnc|vino|rustdesk|anydesk|teamviewer'

echo "== nvidia-smi"
nvidia-smi 2>&1 || echo "(nvidia-smi failed)"

echo "== network (nmcli -t -f TYPE,STATE device)"
NET="$(nmcli -t -f TYPE,STATE device 2>&1 || true)"
printf '%s\n' "$NET"
ETHERNET=0
if printf '%s\n' "$NET" | grep -q '^ethernet:connected'; then
    ETHERNET=1
fi

echo "== remote-desktop programs (pgrep -a -f '$RD_PATTERN')"
RD="$(pgrep -a -f "$RD_PATTERN" 2>/dev/null || true)"
# pgrep -f also matches a shell whose own command line holds the pattern (this script's caller, for example)
RD="$(printf '%s\n' "$RD" | grep -v -E "^($$|$PPID) " | grep -v -F "pgrep" | sed '/^$/d' || true)"
if [ -n "$RD" ]; then printf '%s\n' "$RD"; else echo "(none)"; fi

if [ "$ETHERNET" -eq 0 ] && [ -n "$RD" ]; then
    echo "BLOCKED (exit 10): WiFi only, with a remote-desktop program running. Get on Ethernet or at the machine,"
    echo "or have the owner approve a headless launch in this state."
    exit 10
fi

echo "== GPU compute processes over $GPU_MIB_MAX MiB (other than this shell's)"
APPS="$(nvidia-smi --query-compute-apps=pid,used_memory,process_name --format=csv,noheader,nounits 2>/dev/null || true)"
BUSY="$(printf '%s\n' "$APPS" | awk -F', *' -v me="$$" -v parent="$PPID" -v max="$GPU_MIB_MAX" \
    'NF >= 2 && $1 != me && $1 != parent && ($2 + 0) > max { print }')"
if [ -n "$BUSY" ]; then
    printf '%s\n' "$BUSY"
    echo "GPU IN USE (exit 11): pid, MiB, process above. Check it is not the AirStack simulator or a flight session."
    exit 11
fi
echo "(none)"
echo "preflight OK (exit 0)"
exit 0
