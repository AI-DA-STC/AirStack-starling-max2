#!/usr/bin/env bash
# tools/lib/firewall_probe.sh — can the isaac-sim container reach the host over UDP? SOURCE it; sim.sh doctor and
# localisation/scripts/slam_up.sh both call it, so the logic exists once. SIM ONLY.
# The cuVSLAM Foxglove bridge (in the Isaac network) finds the robot container (host network) through the bridge
# at 172.31.0.1; the laptop firewall drops those packets unless:  sudo ufw allow from 172.31.0.0/24
# firewall_probe prints one word and returns 0:  ok | blocked | skip (isaac-sim not running or no docker)
# The host binds a UDP socket FIRST, the container sends one datagram to 172.31.0.1:<port>, the host waits
# FIREWALL_PROBE_TIMEOUT s (default 3). The socket is closed on every path. Read-only: nothing is changed.
FIREWALL_FIX='sudo ufw allow from 172.31.0.0/24'
firewall_probe() {
  command -v docker >/dev/null 2>&1 && docker exec isaac-sim true >/dev/null 2>&1 || { echo skip; return 0; }
  python3 - "${FIREWALL_PROBE_TIMEOUT:-3}" <<'PY'
import socket, subprocess, sys
timeout = float(sys.argv[1])
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.bind(("0.0.0.0", 0))
    port = s.getsockname()[1]
    send = ("import socket,sys; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); "
            "s.sendto(b'probe', (sys.argv[1], int(sys.argv[2])))")
    try:
        subprocess.run(["docker", "exec", "isaac-sim", "python3", "-c", send, "172.31.0.1", str(port)],
                       capture_output=True, timeout=timeout + 5)
    except (subprocess.SubprocessError, OSError):
        pass
    s.settimeout(timeout)
    try:
        s.recvfrom(64); print("ok")
    except (socket.timeout, OSError):
        print("blocked")
finally:
    s.close()
PY
}
