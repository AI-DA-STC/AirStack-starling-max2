# RUNBOOK — start the pipeline fast

> **Who this is for:** anyone whose machine is already set up (README → "Setting up AirStack
> on a NEW machine") and who just wants to **run** things. No background, no debugging — that
> lives in [MILESTONES.md](MILESTONES.md) (plan + work log) and
> [CLAUDE_NOTES.md](CLAUDE_NOTES.md) (full history).
> Every code block says where it runs. **Never paste across a `connect` line** — it opens a
> new shell and swallows what follows.

**Prompt rule:** `jeremychia@…$` = laptop · `root@…#` = inside the robot container ·
`starling2-max…$` = on the drone (adb).

---

## A · Fly in SIMULATION (✅ validated 2026-07-20)

Five terminals, one job each. GPU required (Isaac Sim).

**T1 — stack + sim drones.** Laptop:
```bash
cd ~/AirStack-starling-max2/AirStack
./airstack.sh up
./airstack.sh connect isaac-sim --command=bash
```
Inside (one command, safe to paste whole):
```bash
NUM_ROBOTS=3 SVG_DOMAIN_ID=1 PLAY_SIM_ON_START=true ISAAC_SIM_HEADLESS=true \
PYTHONPATH="$ISAAC_SIM_PYTHONPATH" \
/isaac-sim/python.sh /isaac-sim/AirStack/simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py \
  --ext-folder ~/.local/share/ov/data/documents/Kit/shared/exts
```
Wait for `Ready for takeoff!` ×3. Leave running.

**T2 — interfaces.** Laptop: `cd ~/AirStack-starling-max2/AirStack && ./airstack.sh connect robot --command=bash`, then inside:
```bash
cd ~/AirStack/robot/ros_ws && bws && sws     # bws only if code changed
./src/svg_ground_control/scripts/launch_sim_interfaces.sh 3
```
Leave running.

**T3 — commander.** New container shell (same connect), inside:
```bash
ros2 launch svg_ground_control ground_control.launch.py
```
Leave running.

**T4 — RViz.** New container shell, inside:
```bash
rviz2 -d $(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/svg_drones.rviz
```

**T5 — cockpit.** New container shell, inside — one call at a time:
```bash
ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger   # arm + climb + hold
ros2 service call /swarm_commander/start   std_srvs/srv/Trigger   # scenario live
ros2 service call /swarm_commander/hold    std_srvs/srv/Trigger   # PANIC freeze
ros2 service call /swarm_commander/land    std_srvs/srv/Trigger   # descend + disarm
```
Geofence latched (fence red, drones frozen)? → `land`, then `/swarm_commander/reset_fence`,
then takeoff + start again.

---

## B · REAL DRONE session (mocap room)

> **Maturity (2026-07-22):** steps 1–3 validated (M3 complete — 24 `/drone_1/fmu/*` topics
> live) · step 4's driver launch validated, its exit test pending the `drone_1` rigid body in
> Motive · steps 5–8 pending M4/M5/M6 — including the one-time M4-A drone setup (EKF2 params
> + onboard VIO off) and the `swarm_real.yaml` single-drone trim. No Isaac Sim needed — do
> NOT start it.

**1 — Check today's IPs** (everything is DHCP; addresses drift). Laptop:
```bash
ip -4 -brief addr              # every interface + its IPv4, one line each
ping -c2 192.168.8.190         # Motive PC answers over the wire
ss -ulpn | grep -E ':(1510|1511)' || echo "ports clear"
```
Compare against the current values in **[CONFIG.md](CONFIG.md)** (the single source of truth
for every IP/SSID/name — including *what to do* when one has drifted). Quick version:
`wlp…` (WiFi) must match what the drone dials; `enp…` (Ethernet) feeds `clientIP:=` in step 4.
Drone's IP if needed (diagnostics only): `adb shell ip -4 addr show mlan0`, or read it from
the agent's `session established` log line. The drone auto-joins `AI.R STC Hangar-5G` at boot
— nothing to do. (WiFi missing after reboot + dmesg `Firmware Init Failed` → cold power
cycle: battery + USB out 10 s.)

**2 — Stack up (robot container only).** Laptop:
```bash
cd ~/AirStack-starling-max2/AirStack
./airstack.sh up robot-desktop
```

**3 — Agent** (the drone link). Container shell (`./airstack.sh connect robot --command=bash`), inside:
```bash
MicroXRCEAgent udp4 -p 8888 -v4
```
Wait for `session established`. Leave running. Verify in another container shell:
```bash
ros2 topic echo /drone_1/fmu/out/vehicle_status --qos-reliability best_effort --once
```
⚠️ Every `/fmu/*` echo/hz needs `--qos-reliability best_effort` or it looks dead.
(Before the agent starts, the drone-side `px4-microdds_client status` shows `Running,
disconnected` — that's normal, the drone is dialing out waiting for this agent.)

**4 — Mocap driver.** *Prereq: the `drone_1` rigid body exists in Motive BEFORE launching —
the driver reads the body list only at startup (create/rename later → Ctrl+C and relaunch).*
New container shell, inside (clientIP = laptop **Ethernet** IP):
```bash
ros2 launch natnet_ros2 natnet_ros2.launch.py serverIP:=192.168.8.190 clientIP:=192.168.8.112
```
Leave running. Verify: `ros2 topic hz /drone_1/pose` (~50 Hz, our Motive rate).

**5 — Per-drone interfaces** (turns `/fmu` traffic into the odometry the commander needs —
without this, RViz shows nothing and takeoff is refused). New container shell, inside:
```bash
ros2 launch svg_ground_control real_interfaces.launch.py drones:=drone_1
```
Leave running.

**6 — Commander + mocap bridge.** *One-time prereqs (MILESTONES M4-A/M6, pending on D0012):
EKF2 params set, onboard VIO disabled, and `swarm_real.yaml` trimmed to `drone_1` only —
with the shipped 3-drone config the commander still launches `drone_1` while configured for
phantom drone_2/3 (their hover slots, teleop/CBF roles) — trim BEFORE flying.* New container
shell, inside:
```bash
ros2 launch svg_ground_control ground_control.launch.py \
  config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/swarm_real.yaml use_mocap:=true
```
Leave running. Verify fusion (another shell):
```bash
ros2 topic hz  /drone_1/fmu/in/vehicle_visual_odometry --qos-reliability best_effort
ros2 topic echo /drone_1/fmu/out/vehicle_odometry --once --qos-reliability best_effort --qos-durability volatile
```
`out/…` producing positions = EKF2 fusing. Then the **frame hand-check** (before the day's
first flight — MILESTONES M4-B step 4): carry North → `position[0]`↑, East → `[1]`↑, up →
`[2]`↓.

**7 — RViz preflight (no arming).** New container shell: same `rviz2` command as sim T4.
Hand-carry the drone — its red sphere must track. Do NOT call takeoff during this check.

**8 — Fly** (only after M6's safety setup: fence fitted, RC kill tested, thumb on it):
same four service calls as sim T5.

**Shutdown** (either session type). Ctrl+C the launches, `exit` the containers, then laptop:
```bash
cd ~/AirStack-starling-max2/AirStack && ./airstack.sh down
```

---

## Pocket reference

| Thing | Rule |
|---|---|
| `ros2` / `bws` / `rviz2` | container only (`root@`) |
| `docker` / `airstack.sh` / `adb` / `ip addr` | laptop only (`jeremychia@`) |
| `/fmu/*` topics | always `--qos-reliability best_effort` |
| Long-running (leave open) | Isaac spawn · interfaces · agent · natnet · commander |
| Panic, in order | `hold` service → `land` service → **RC kill switch** |
| Container messages to ignore | `Workspace not built yet` (pre-bws) · `groups: … 992` · `unknown-robot` |
| Drone hotspot `VOXL-…` | never connect the laptop to it |
