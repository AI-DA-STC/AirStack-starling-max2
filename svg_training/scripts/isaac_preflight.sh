#!/usr/bin/env bash
# Check the network and the GPU before every Isaac Sim launch (S2b plan D13). Run it on the host, not in the container.
#
#   scripts/isaac_preflight.sh [--approved-headless | --approved-windowed] [--allow-siblings]
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
# --allow-siblings (owner, 18 Nov 2026: "parallelize the training"): a busy process whose command line is one of this
# folder's own training or recording scripts (SIBLING_PATTERN) does not block, as long as at least SIBLING_FREE_MIB of
# GPU memory is free; anything else (the AirStack simulator, a flight session, an unknown process) still exits 11.
# When both 10 and 11 hold, 10 is returned; both are printed.
set -u

GPU_MIB_MAX=1024   # owner, 18 Nov 2026: raised from 500 so the 5090's remote-desktop daemon (546-589 MiB) does not block
RD_PATTERN='gnome-remote-desktop|xrdp|x11vnc|vino|rustdesk|anydesk|teamviewer'
SIBLING_PATTERN='scripts/(train_standin|nus_selfplay_train|nus_phase5_reference|nus_phase5_probe|nus_phase4|nus_isaac_clips|make_s2b_video)\.py|run_nus_job\.sh|ma_skills/'
SIBLING_FREE_MIB=8192
# NUS's trainer renames its process, so its command line no longer names a script: a process whose executable is the python of our
# own conda environments (nus_jax for NUS's code, env_isaaclab for ours and Isaac Lab) is a sibling too. Isaac Sim's own kit python
# (the AirStack simulator) is not one of these, so it still blocks.
SIBLING_EXE_PATTERN="${SIBLING_EXE_PATTERN:-/miniconda3/envs/(nus_jax|env_isaaclab)/bin/python}"
APPROVED=""
SIBLINGS_OK=0
for arg in "$@"; do
    case "$arg" in
        --approved-headless) APPROVED="headless" ;;
        --approved-windowed) APPROVED="windowed" ;;
        --allow-siblings) SIBLINGS_OK=1 ;;
        *) echo "unknown argument: $arg (use --approved-headless, --approved-windowed or --allow-siblings)" >&2; exit 2 ;;
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

if [ "$SIBLINGS_OK" -eq 1 ] && [ -n "$BUSY" ]; then
    echo "== --allow-siblings: this folder's own jobs may share the GPU (at least $SIBLING_FREE_MIB MiB free)"
    REST=""
    SIBS=""
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        pid="${line%%,*}"
        args="$(ps -o args= -p "$pid" 2>/dev/null || true)"
        exe="$(readlink -f "/proc/$pid/exe" 2>/dev/null || true)"
        if { [ -n "$args" ] && printf '%s' "$args" | grep -q -E "$SIBLING_PATTERN"; } \
            || { [ -n "$exe" ] && printf '%s' "$exe" | grep -q -E "$SIBLING_EXE_PATTERN"; }; then
            echo "sibling (allowed): $line :: $args"
            SIBS="$SIBS$line"$'\n'
        else
            echo "not a sibling: $line :: ${args:-(command line unknown)}"
            REST="$REST$line"$'\n'
        fi
    done <<< "$BUSY"
    if [ -n "$SIBS" ] && [ -z "$REST" ]; then
        MEM="$(nvidia-smi --query-gpu=memory.total,memory.used --format=csv,noheader,nounits 2>/dev/null | head -1)"
        FREE="$(printf '%s' "$MEM" | awk -F', *' '{ print ($1 + 0) - ($2 + 0) }')"
        echo "GPU memory free: ${FREE:-unknown} MiB"
        if [ -n "$FREE" ] && [ "$FREE" -ge "$SIBLING_FREE_MIB" ]; then
            BUSY=""
        else
            echo "too little GPU memory free for a second job (need $SIBLING_FREE_MIB MiB)"
        fi
    fi
fi

if [ "$NET_BLOCKED" -eq 1 ]; then
    if [ -n "$APPROVED" ]; then
        echo "WARNING: WiFi only, with a remote-desktop program running. Going ahead under the owner's approval of"
        if [ "$APPROVED" = "headless" ]; then
            echo "16 November 2026 (~07:45, \"yes dont worry about wifi\"): headless Isaac launches in this state."
            echo "Extended to the home RTX 5090 by the owner on 18 November 2026 (\"wifi: yes\")."
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
