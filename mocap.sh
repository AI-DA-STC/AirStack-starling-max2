#!/usr/bin/env bash
# mocap.sh — OptiTrack -> ROS 2 pose bridge for the AI.R STC hangar.
#
# Why this exists: our Motive server sends pose data as UDP *broadcast*, which
# the NatNet-SDK-based natnet_ros2 driver physically cannot receive (it only
# listens on the multicast group address). This bridge uses the open-source
# parser (motion_capture_tracking), which hears broadcast and multicast alike,
# plus a small relay that republishes each rigid body as /<name>/pose — the
# exact topics the AirStack pipeline (mocap_bridge.py -> PX4 EKF2) expects.
# Full story, diagrams and troubleshooting: MOCAP.md in this repo.
#
# Runs on the LAPTOP (not inside the robot container). Publishes on
# ROS_DOMAIN_ID=1 with shared-memory transport disabled, so the host-network
# robot container sees the topics exactly as if they were published inside it.
#
# Usage:
#   ./mocap.sh setup    one-time: clone + patch + build (~/mocap_ws, internet needed)
#   ./mocap.sh          run the bridge (Ctrl+C stops everything)
#   ./mocap.sh check    no-ROS network probe: is mocap data reaching this laptop?
#   ./mocap.sh stop     kill a bridge left running in a lost terminal
#   ./mocap.sh status   show whether the bridge processes are up
#
# Config lives in mocap/ next to this script:
#   motion_capture.yaml  Motive PC IP (drifts with DHCP -> see CONFIG.md)
#   pose_relay.py        /poses -> /<body>/pose republisher
#   fastdds.xml          UDP-only DDS profile (same one the container uses)
# Rigid bodies to relay (space-separated, must match Motive's body names):
#   MOCAP_BODIES="drone_1 drone_2" ./mocap.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOCAP_WS="${MOCAP_WS:-$HOME/mocap_ws}"
MOCAP_BODIES="${MOCAP_BODIES:-drone_1}"
ROS_DISTRO_EXPECTED=jazzy

# Pinned upstream versions (what we tested on 2026-08-27):
MCT_REPO="https://github.com/IMRCLab/motion_capture_tracking.git"
MCT_COMMIT="64d3af2456e534cd5e587b98ef2f15dd8ad35e8c"
PATCH_FILE="$REPO_DIR/patches/0003-libmotioncapture-natnet-4.2-modeldef-segfault.patch"

# --- helpers -----------------------------------------------------------------

ros_env() {
    # miniconda's python breaks colcon/rosidl and rclpy — keep it out entirely
    PATH="$(echo "$PATH" | tr ':' '\n' | grep -v miniconda | paste -sd:)"
    export PATH
    unset CONDA_PREFIX CONDA_DEFAULT_ENV PYTHONPATH || true
    # ROS setup.bash reads unset vars — relax `set -u` around the source
    set +u
    # shellcheck disable=SC1091
    source "/opt/ros/$ROS_DISTRO_EXPECTED/setup.bash"
    set -u
}

bridge_env() {
    ros_env
    set +u
    # shellcheck disable=SC1091
    source "$MOCAP_WS/install/setup.bash"
    set -u
    export ROS_DOMAIN_ID=1
    export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
    export FASTRTPS_DEFAULT_PROFILES_FILE="$REPO_DIR/mocap/fastdds.xml"
}

need_setup() {
    [ ! -f "$MOCAP_WS/install/setup.bash" ]
}

# --- commands ----------------------------------------------------------------

cmd_setup() {
    if [ ! -d "/opt/ros/$ROS_DISTRO_EXPECTED" ]; then
        echo "ERROR: ROS 2 $ROS_DISTRO_EXPECTED not found at /opt/ros/$ROS_DISTRO_EXPECTED" >&2
        exit 1
    fi
    ros_env

    local src="$MOCAP_WS/src/motion_capture_tracking"
    if [ ! -d "$src/.git" ]; then
        echo ">> cloning motion_capture_tracking (pinned $MCT_COMMIT)"
        mkdir -p "$MOCAP_WS/src"
        git clone "$MCT_REPO" "$src"
    fi
    git -C "$src" fetch --quiet origin "$MCT_COMMIT" 2>/dev/null || true
    git -C "$src" checkout --quiet "$MCT_COMMIT"
    echo ">> fetching submodules (libmotioncapture and friends — this is the slow part)"
    git -C "$src" submodule update --init --recursive --quiet

    local lmc="$src/motion_capture_tracking/deps/libmotioncapture"
    if git -C "$lmc" apply --reverse --check "$PATCH_FILE" 2>/dev/null; then
        echo ">> NatNet 4.2 patch already applied"
    else
        echo ">> applying NatNet 4.2 model-definition patch (see patches/, MOCAP.md)"
        git -C "$lmc" apply "$PATCH_FILE"
    fi

    echo ">> building (two steps: messages first, then the node)"
    cd "$MOCAP_WS"
    colcon build --packages-select motion_capture_tracking_interfaces \
        --cmake-args -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE=/usr/bin/python3
    set +u
    # shellcheck disable=SC1091
    source "$MOCAP_WS/install/setup.bash"
    set -u
    colcon build --packages-select motion_capture_tracking \
        --cmake-args -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE=/usr/bin/python3

    echo ">> done. Run the bridge with: $REPO_DIR/mocap.sh"
}

cmd_run() {
    if need_setup; then
        echo "Bridge not built yet — run: $0 setup" >&2
        exit 1
    fi
    bridge_env
    # body names become quoted python-list entries — restrict to safe charset
    if ! echo "$MOCAP_BODIES" | grep -qE '^[A-Za-z0-9_ ]+$'; then
        echo "ERROR: MOCAP_BODIES may only contain letters, digits, _ and spaces (got: $MOCAP_BODIES)" >&2
        exit 1
    fi
    local bodies_py
    bodies_py="[$(echo "$MOCAP_BODIES" | sed "s/[^ ]*/'&'/g; s/ /,/g")]"
    echo ">> starting mocap bridge (bodies: $MOCAP_BODIES) — Ctrl+C stops both nodes"
    trap 'kill 0' EXIT
    ros2 run motion_capture_tracking motion_capture_tracking_node --ros-args \
        -r __node:=motion_capture_tracking \
        --params-file "$REPO_DIR/mocap/motion_capture.yaml" &
    /usr/bin/python3 "$REPO_DIR/mocap/pose_relay.py" --ros-args \
        -p "bodies:=$bodies_py" &
    wait
}

cmd_check() {
    exec /usr/bin/python3 "$REPO_DIR/mocap/probe.py"
}

cmd_stop() {
    # SIGKILL for the receiver: it blocks in recv() and turns SIGTERM into a
    # noisy abort; there is no state to clean up.
    pkill -9 -f motion_capture_tracking_node 2>/dev/null && echo "stopped mocap node" || true
    pkill -f pose_relay.py 2>/dev/null && echo "stopped relay" || true
    sleep 1
    cmd_status
}

cmd_status() {
    # apport (the crash reporter) briefly holds the node path in its argv —
    # don't count it as the bridge
    if pgrep -af 'motion_capture_tracking_node|pose_relay.py' | grep -v apport; then
        echo "bridge is RUNNING"
    else
        echo "bridge is not running"
    fi
}

case "${1:-run}" in
    setup)  cmd_setup ;;
    run)    cmd_run ;;
    check)  cmd_check ;;
    stop)   cmd_stop ;;
    status) cmd_status ;;
    *) echo "usage: $0 [setup|run|check|stop|status]" >&2; exit 1 ;;
esac
