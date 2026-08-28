#!/usr/bin/env bash
# ops.sh — open every long-running piece of a REAL-DRONE AirStack session,
# each in its own terminal window (they must all stay running while you fly).
#
# What it opens (RUNBOOK.md §B is the manual version of the same flow):
#   IN THE ROBOT CONTAINER (docker exec):
#     [agent]      MicroXRCEAgent udp4 -p 8888 -v4        ← the drone link
#     [interfaces] ros2 launch svg_ground_control real_interfaces.launch.py drones:=…
#     [cockpit]    a spare container shell for the commander / service calls
#   ON THE LAPTOP (no container):
#     [mocap]      the OptiTrack pose bridge (./mocap.sh — see MOCAP.md)
#     [qgc]        QGroundControl ground station
#
# Usage:
#   ./ops.sh              start everything (skips the container bring-up if already up)
#   ./ops.sh stop         best-effort kill of the background pieces (or just close windows)
#   DRONES="drone_1,drone_2" ./ops.sh     more drones for the interfaces launch
#
# Overridable paths:
#   AIRSTACK_DIR   default ~/AirStack-starling-max2/AirStack  (for ./airstack.sh up)
#   QGC_APPIMAGE   default ~/QGroundControl-x86_64.AppImage

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRONES="${DRONES:-drone_1}"
AIRSTACK_DIR="${AIRSTACK_DIR:-$HOME/AirStack-starling-max2/AirStack}"
QGC_APPIMAGE="${QGC_APPIMAGE:-$HOME/QGroundControl-x86_64.AppImage}"
CONTAINER=airstack-robot-desktop-1

term() {  # term <title> <command…>  — one gnome-terminal window that stays open
    local title="$1"; shift
    # env -u …: VSCode/snap shells leak snap library paths that crash gnome-terminal
    env -u LD_LIBRARY_PATH -u GTK_PATH -u GTK_EXE_PREFIX -u GIO_MODULE_DIR -u LOCPATH \
        gnome-terminal --title="$title" -- \
        bash -c "$*; echo; echo '[$title exited — Enter to close]'; read" &
}

in_container() {  # quote a command for an interactive container shell (sources ROS env)
    printf 'docker exec -it %s bash -ic %q' "$CONTAINER" "$1"
}

cmd_start() {
    if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
        echo ">> robot container not running — bringing it up ($AIRSTACK_DIR)"
        (cd "$AIRSTACK_DIR" && ./airstack.sh up robot-desktop)
    fi

    echo ">> [agent] uXRCE-DDS agent (container) — wait for 'session established'"
    term "agent — drone link" "$(in_container 'MicroXRCEAgent udp4 -p 8888 -v4')"
    sleep 2

    echo ">> [mocap] pose bridge (laptop) — MOCAP.md"
    term "mocap bridge" "cd $REPO_DIR && ./mocap.sh"

    echo ">> [interfaces] real_interfaces drones:=$DRONES (container)"
    term "interfaces" "$(in_container "ros2 launch svg_ground_control real_interfaces.launch.py drones:=$DRONES")"

    echo ">> [cockpit] spare container shell (commander / service calls / topic checks)"
    term "cockpit — container shell" "$(in_container 'bash')"

    if [ -x "$QGC_APPIMAGE" ]; then
        echo ">> [qgc] QGroundControl (laptop)"
        term "QGroundControl" "$QGC_APPIMAGE"
    else
        echo "!! QGroundControl not found/executable at $QGC_APPIMAGE — skipped (set QGC_APPIMAGE=…)"
    fi

    cat <<EOF

All windows launched. Quick health checks (run in the cockpit window):
  ros2 topic hz /drone_1/fmu/out/vehicle_status     # ~30 Hz -> agent + drone link OK
  ros2 topic hz /drone_1/pose                       # Motive's rate -> mocap OK
Next steps (commander, RViz, flying): RUNBOOK.md §B steps 6-8.
Mocap looks dead? Laptop terminal: ./mocap.sh check
EOF
}

cmd_stop() {
    "$REPO_DIR/mocap.sh" stop || true
    # bracketed patterns so pkill can't match this wrapper shell's own cmdline
    docker exec "$CONTAINER" bash -c \
        'pkill -f "Micro[X]RCEAgent"; pkill -f "real_[i]nterfaces.launch"; true' 2>/dev/null || true
    pgrep -f QGroundControl >/dev/null && echo "QGC still open — close its window" || true
    echo "done (windows opened by ops.sh can simply be closed)"
}

case "${1:-start}" in
    start) cmd_start ;;
    stop)  cmd_stop ;;
    *) echo "usage: $0 [start|stop]   (env: DRONES, AIRSTACK_DIR, QGC_APPIMAGE)" >&2; exit 1 ;;
esac
