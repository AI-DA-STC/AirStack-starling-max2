#!/usr/bin/env bash
# Check the network and the GPU before every Isaac Sim launch (S2b plan D13). Run it on the host, not in the container.
#
#   scripts/isaac_preflight.sh [--approved-headless | --approved-windowed]
#
# Prints `nvidia-smi`, the network state, the remote-desktop programs and the GPU compute processes (always, all
# four), then exits:
#   0   go;
#   10  BLOCKED: no Ethernet device is connected and a remote-desktop program is running. Starting Isaac Sim with a
#       window over remote desktop on WiFi has crashed this laptop's WiFi firmware (CLAUDE.md "Known trap").
#       --approved-headless / --approved-windowed turn this into a printed warning that cites the owner's approval
#       of 16 November 2026 for that kind of launch; use them only for that kind of launch;
#   11  the GPU is in use: a compute process other than this shell's holds more than 1024 MiB (the AirStack
#       simulator, a flight session or another run). The process list is printed for the lead to check;
#   2   unknown argument.
# When both 10 and 11 hold, 10 is returned; both are printed.
set -u

GPU_MIB_MAX=1024   # owner, 18 Nov 2026: raised from 500 so the 5090's remote-desktop daemon (546-589 MiB) does not block
RD_PATTERN='gnome-remote-desktop|xrdp|x11vnc|vino|rustdesk|anydesk|teamviewer'
APPROVED=""
for arg in "$@"; do
    case "$arg" in
        --approved-headless) APPROVED="headless" ;;
        --approved-windowed) APPROVED="windowed" ;;
        *) echo "unknown argument: $arg (use --approved-headless or --approved-windowed)" >&2; exit 2 ;;
    esac
done

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

NET_BLOCKED=0
if [ "$ETHERNET" -eq 0 ] && [ -n "$RD" ]; then
    NET_BLOCKED=1
fi

echo "== GPU compute processes over $GPU_MIB_MAX MiB (other than this shell's)"
APPS="$(nvidia-smi --query-compute-apps=pid,used_memory,process_name --format=csv,noheader,nounits 2>/dev/null || true)"
BUSY="$(printf '%s\n' "$APPS" | awk -F', *' -v me="$$" -v parent="$PPID" -v max="$GPU_MIB_MAX" \
    'NF >= 2 && $1 != me && $1 != parent && ($2 + 0) > max { print }')"
if [ -n "$BUSY" ]; then printf '%s\n' "$BUSY"; else echo "(none)"; fi

if [ "$NET_BLOCKED" -eq 1 ]; then
    if [ -n "$APPROVED" ]; then
        echo "WARNING: WiFi only, with a remote-desktop program running. Going ahead under the owner's approval of"
        if [ "$APPROVED" = "headless" ]; then
            echo "16 November 2026 (~07:45, \"yes dont worry about wifi\"): headless Isaac launches in this state."
        else
            echo "16 November 2026 (~07:50, \"u can allow window launches\"): windowed Isaac launches, WiFi-crash risk"
            echo "accepted by the owner."
        fi
    else
        echo "BLOCKED (exit 10): WiFi only, with a remote-desktop program running. Get on Ethernet or at the machine,"
        echo "or pass --approved-headless / --approved-windowed under the owner's approval."
        exit 10
    fi
fi
if [ -n "$BUSY" ]; then
    echo "GPU IN USE (exit 11): pid, MiB, process above. Check it is not the AirStack simulator or a flight session."
    exit 11
fi
echo "preflight OK (exit 0)"
exit 0
