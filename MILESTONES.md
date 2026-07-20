# AirStack + Starling Max 2 Live Flight — Milestones & Runbook

> Canonical (markdown) version. The Word export is generated with
> `python3 tools/make_milestones_doc.py`. Last updated: 2026-07-20.
> Branch: `daniel/diffaero_ground_control` · Working copy: `~/AirStack-diffaero`

## 1. Objective

Replicate CMU AirLab's ground-controller workflow on our hardware: fly a ModalAI **Starling
Max 2** live, commanded by **AirStack** on a ground laptop, using **OptiTrack + Motive** mocap
as the indoor position source. CBF/swarm scenarios are out of scope for now — single-drone
takeoff / hover / land under mocap. The branch already contains the whole pipeline:
`natnet_ros2` (mocap driver), `mocap_bridge` (mocap → PX4 external vision), `px4_interface` +
`MicroXRCEAgent` (uXRCE-DDS flight link), and the swarm commander (takeoff/start/hold/land
services + software geofence).

## 2. Why milestones

Flight day is a long chain: Motive → natnet_ros2 → mocap_bridge → XRCE agent → WiFi → PX4
EKF2 → px4_interface → commander → motors. Each milestone adds **one** new link and proves it
before the next stacks on, so failures always localize to the link just added.
Sim proves the software and the operator (SITL runs real PX4 firmware); props-off stages prove
the links; hand-carry proves the stack's beliefs; only then does anything spin. Exit criteria
are observed facts, and each milestone is a re-entry point.

## 3. Status

| Milestone | Goal | Status |
|---|---|---|
| M1 Sim rehearsal | 3 SITL drones fly under the ground controller; teleop + geofence exercised | **COMPLETE 2026-07-20** |
| M2 Ground-station hardware prep | Host networking, Motive config, time sync, port checks | Partial |
| M3 Drone comms (props off) | Real PX4 topics on the laptop over WiFi (uXRCE-DDS) | Not started |
| M4 Mocap → EKF2 (props off) | OptiTrack pose fused by EKF2; frames verified | Not started |
| M5 Hand-carry preflight | RViz marker tracks the hand-carried drone | Not started |
| M6 First flight | Stable mocap-fused hover + landing | Not started |

## 4. Milestone 1 — record (2026-07-20)

### One-time setup performed
1. Cloned branch; `git submodule update --init`.
2. Copied gitignored `simulation/isaac-sim/docker/omni_pass.env` and `user.config.json` from the
   old checkout (trap: a failed `up` creates the missing mount source as a root-owned
   *directory* — `rmdir` it first).
3. `./airstack.sh image-build robot-desktop` — **required**: bakes `MicroXRCEAgent` into the
   image and pins `ROS_DOMAIN_ID=1` (overwrites the shared v0.18.0 robot image tag).
4. Applied `patches/0001-zed-camera-info-init-race.patch` (PegasusSimulator submodule) — see
   CLAUDE_NOTES.md §3.1.
5. Applied `patches/0002-swarm-commander-logger-severity-crash.patch` — see §4.4 below.
6. `.env`: `COMPOSE_PROFILES="desktop,isaac-sim"`, `AUTOLAUNCH="false"`, `NUM_ROBOTS="1"`.
7. First `bws` build: 59 packages, ~4 min.

### What was achieved
Takeoff/hover/land of 3 SITL drones via the commander services; keyboard teleop of drone_3;
an accidental geofence breach with correct latch behavior and full recovery; RViz markers as
the operational viewport (sim headless).

### Incidents & findings
- **Commander state machine:** IDLE —takeoff→ HOLDING —start→ ACTIVE —hold→ HOLDING.
  HOLDING ignores nominal inputs (that IS the freeze). Teleop only acts in ACTIVE, and
  keypresses go to the teleop node's own terminal (focus!).
- **Geofence breach:** teleop-flew drone_3 through y<min → all drones froze (orange), fence red,
  `start` refused. Recovery: `land` (fence-exempt) → `reset_fence` → `takeoff` → `start`.
  The fence freezes only — the RC kill switch is the only true motor cutoff.
- **CMU bug found & fixed (report upstream):** first *failed* service report crashed the
  commander (`ValueError: Logger severity cannot be changed between calls`) — rclpy caches log
  severity per call-site and `report()` used one line for both info and error. Fixed by
  splitting call-sites (patch 0002). The crash killed the commander with a drone airborne →
  on hardware, PX4 `COM_OBL_RC_ACT` + RC kill are non-negotiable.
- **Fix validated:** on a later run, `drone_2: arm -> success=False` logged as ERROR and the
  commander kept running.
- **SITL battery drain:** after ~20 min of hover PX4 reports `Preflight Fail: Battery unhealthy`
  and refuses to arm. Reset = Ctrl+C the Isaac spawn script and re-run it. Also observed: the
  commander proceeds with swarm takeoff even when one drone's arm fails (second upstream
  feedback item).

## 5. Milestone 1 re-run runbook

All "inside container" shells: `cd ~/AirStack-diffaero && ./airstack.sh connect <name> --command=bash`
(prompt must become `root@`). Paste one line at a time.

```bash
# T1 (host): stack up
cd ~/AirStack-diffaero && ./airstack.sh up && ./airstack.sh status

# T1 → isaac-sim container: spawn drones (single command, safe to paste whole)
NUM_ROBOTS=3 SVG_DOMAIN_ID=1 PLAY_SIM_ON_START=true ISAAC_SIM_HEADLESS=true \
PYTHONPATH="$ISAAC_SIM_PYTHONPATH" \
/isaac-sim/python.sh /isaac-sim/AirStack/simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py \
  --ext-folder ~/.local/share/ov/data/documents/Kit/shared/exts
# wait: "Spawning 3 drone(s) on ROS domain 1" + "Ready for takeoff!" x3

# T2 → robot container: interfaces
cd ~/AirStack/robot/ros_ws && bws && sws        # bws only if code changed
./src/svg_ground_control/scripts/launch_sim_interfaces.sh 3
# verify elsewhere: ros2 topic echo /drone_1/interface/mavros/state --once  → connected: true

# T3 → robot container: commander
ros2 launch svg_ground_control ground_control.launch.py

# T4 → robot container: RViz
rviz2 -d $(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/svg_drones.rviz

# T5 → robot container: cockpit
ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger
ros2 service call /swarm_commander/start   std_srvs/srv/Trigger
ros2 service call /swarm_commander/hold    std_srvs/srv/Trigger    # panic freeze
ros2 service call /swarm_commander/land    std_srvs/srv/Trigger
# teleop (needs start; click its terminal for focus):
#   ros2 run svg_ground_control keyboard_teleop --ros-args -p drone:=drone_3
# fence recovery: land → /swarm_commander/reset_fence → takeoff → start
```

## 6. Milestones 2–6 (to do)

Full details: `robot/ros_ws/src/svg_ground_control/experiment.md` Parts B & D.
Substitute `<LAPTOP_IP>` / `<MOTIVE_IP>`.

### M2 — Ground station prep (desk)
- robot container → `network_mode: host` (edit `robot/docker/docker-compose.yaml`: comment
  `networks:`/`ports:` of robot-desktop). Then `down` + `up robot-desktop`.
- Motive: rigid body named `drone_1`, **Up Axis = Z**, Broadcast ON, correct Local Interface.
- chrony/NTP: laptop + Motive PC (+ VOXL in M3).
- `ss -ulpn | grep -E '1510|1511'` must be clear (past lab outage = orphan on 1511).
- Done already: QGC AppImage; `~/PX4-Autopilot` SITL build.

### M3 — Drone comms (props off)
```bash
adb shell ip addr show wlan0                     # drone on the router subnet (udhcpc / voxl-wifi station)
adb push robot/ros_ws/src/svg_ground_control/scripts/voxl_setup_real_drone.sh /usr/bin/
adb shell                                        # then on the VOXL:
  chmod +x /usr/bin/voxl_setup_real_drone.sh
  voxl_setup_real_drone.sh drone_1 <LAPTOP_IP> 1 8888
  px4-microdds_client status                     # connected, Agent IP = <LAPTOP_IP>
# robot container (leave running):
MicroXRCEAgent udp4 -p 8888 -v4
# verify:
ros2 topic echo /drone_1/fmu/out/vehicle_status --qos-reliability best_effort --once
```

### M4 — Mocap → EKF2 (props off)
```bash
bws --packages-select natnet_ros2 && sws         # first build downloads NatNet SDK (internet)
ros2 launch natnet_ros2 natnet_ros2.launch.py serverIP:=<MOTIVE_IP> clientIP:=<LAPTOP_IP>
ros2 topic hz /drone_1/pose                      # ~ Motive rate, smooth under hand-carry
# PX4 params (QGC / px4-param) — MANDATORY (arm blocker indoors):
#   EKF2_EV_CTRL=11  EKF2_HGT_REF=3  EKF2_GPS_CTRL=0  EKF2_EV_DELAY≈50
# check voxl-vision-hub is not a second EV source (voxl-inspect-services)
ros2 launch svg_ground_control ground_control.launch.py \
  config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/swarm_real.yaml use_mocap:=true
ros2 topic hz  /drone_1/fmu/in/vehicle_visual_odometry
ros2 topic echo /drone_1/fmu/out/vehicle_odometry --once --qos-reliability best_effort --qos-durability volatile
# FRAME HAND-CHECK: North → position[0]↑, East → position[1]↑, lift → position[2]↓ (NED).
# Mirrored → px4_vio_frame: "modalai_flip" in swarm_real.yaml. Wrong frame = wall.
```

### M5 — Hand-carry preflight (nothing armed)
```bash
ros2 launch svg_ground_control real_interfaces.launch.py drones:=drone_1
# commander idle (from M4) — do NOT call takeoff; RViz red sphere must track the carried drone
ros2 bag record /drone_1/pose /drone_1/odometry_conversion/odometry
```

### M6 — First flight
- `swarm_real.yaml`: `drone_names: ["drone_1"]`, `drone_modes: "real"`, hover, fence inside the
  net, ≤ 1.0 m/s.
- PX4: RC kill mapped + tested; `COM_OBL_RC_ACT`; low-battery action.
- Preflight (mocap hz, odometry tracks reality, thumb on kill) → `takeoff` → hover → `land`.
- Post-flight: PlotJuggler diff `/drone_1/pose` vs `/drone_1/fmu/out/vehicle_odometry`.

## 7. Troubleshooting quick table

| Symptom | Cause / fix |
|---|---|
| `ros2` not found / empty topics / service call hangs | Host shell. `./airstack.sh connect robot --command=bash` first (`root@` prompt). |
| `omni_pass.env not found` on up | Gitignored file — copy from another checkout / template. |
| "mounting … user.config.json … not a directory" | Failed up made a directory; `rmdir` + copy the real file. |
| `bws: command not found` | Wrong container (Isaac) or host shell. |
| `/fmu/*` looks dead | Best-effort QoS: add `--qos-reliability best_effort`. |
| PX4 won't arm indoors ("fuse failure") | No fused position source — mocap feed / EKF2 params missing. |
| Mocap topic silent | Motive not streaming, wrong serverIP, body not named `drone_N`, or orphan on UDP 1510/1511. |
| Continuous `[timesync]` warnings (sim) | Sim below real-time; reduce load. |
| Teleop publishes but drone doesn't move | Commander HOLDING — call `start`; click teleop terminal for focus. |
| GEOFENCE BREACH, all frozen | By design: `land` → `reset_fence` → `takeoff` → `start`. |
| Commander dies: "Logger severity cannot be changed" | CMU bug — apply patch 0002, rebuild `svg_ground_control`. Report upstream. |
| Sim "Battery unhealthy", won't arm | SITL battery drained — restart the Isaac spawn script. |
