# AirStack / Starling Max 2 — Claude Session Handoff Notes

> **Purpose of this file:** a new Claude (or human) session can read this one file and know
> everything established so far: the objective, what was found and fixed, what succeeded,
> the exact current state of every checkout on this machine, and what comes next.
> Written 2026-07-20 after a long working session. Companion document (human-oriented plan):
> the Word export (legacy, pre-migration content) can be regenerated via `python3 tools/make_milestones_doc.py`, but MILESTONES.md is canonical.

---

## 1. Objective

Replicate CMU AirLab's ground-controller work on our hardware: fly a **ModalAI Starling Max 2**
live, commanded by **AirStack** on the ground laptop, using **OptiTrack + Motive** mocap as the
indoor position source. CBF/swarm scenarios are OUT of scope for now — single-drone
takeoff / hover / land under mocap is the goal. User: Jeremy (robotics lab, Legion Pro 7 laptop,
RTX 5070 Ti 12 GB).

## 2. Repos / checkouts on this machine (layout as of 2026-07-20, post-migration)

| Path | What it is | Role |
|---|---|---|
| `~/AirStack-starling-max2` | this git repo (remote: AI-DA-STC/AirStack-starling-max2) | **THE ACTIVE SETUP.** Docs + patches + media at the root; `AirStack/` inside it is the **working folder** — the fixed code snapshot the stack actually runs from. Same path on every lab machine. |
| `~/AirStack-cmu` | real git clone of castacks/AirStack, branch `jeremy/local-fixes` (formerly at `~/AirStack-diffaero`) | Kept ONLY for the upstream PR to CMU: has the fix commits (`jeremy/local-fixes`; submodule branch `jeremy/camera-init-fix`) on top of `daniel/diffaero_ground_control` with full history. Not used to run the stack. |
| `~/AirStack` | clone of castacks/AirStack, `main` | Original pre-project copy. Camera-race fix + custom `airstack restart` CLI command (both uncommitted). Mostly historical. |
| `~/airstack-branches/{...}` | worktrees of the two SVG branches | Redundant. Removable with `git -C ~/AirStack worktree remove <path>`. |

**Migration note (2026-07-20, evening):** the working folder used to be `~/AirStack-diffaero`
(a CMU clone). Everything was consolidated: code snapshot + docs merged into the single
`AirStack-starling-max2` repo, the working folder became `~/AirStack-starling-max2/AirStack`,
and the old clone was renamed `~/AirStack-cmu`. Older narrative below may say
`~/AirStack-diffaero` — read it as "the folder now called `~/AirStack-cmu`". After the
migration the workspace must be recompiled once (`bws`) since build artifacts stayed in the
old folder.

**Why this branch:** `daniel/diffaero_ground_control` is the ONLY branch line containing the
real-drone + mocap pipeline: `svg_ground_control` (swarm commander, CBF filter, mocap_bridge,
geofence, takeoff/start/hold/land services), `natnet_ros2` (OptiTrack NatNet driver), and
`px4_interface` real-drone wiring. `main`/`develop` have **none** of this.
`yikuan/SVG_ground_control` is the older base of the same work.
The separate `modalai_interface` branch has a VOXL2 interface package but NO ground controller.

**Canonical guide (read it):** `~/AirStack-starling-max2/AirStack/robot/ros_ws/src/svg_ground_control/experiment.md`
— Part A (sim), Part B (real drone bring-up), Part C (tasks), Part D (first flight), Geofence,
Troubleshooting. Our milestones follow it.

## 3. History of findings & fixes (chronological)

### 3.1 The "erratic navigate" saga (earlier sessions, `~/AirStack` on main)
- Symptom: droan_local_planner paths degraded over a session; full `airstack down/up` cleared it.
- First diagnosis (WRONG but plausible): PX4 EKF drift, uncorrected (macvo unfused, Isaac ground
  truth unused). Mechanism exists in code but SITL's simulated GPS bounds drift — not the cause.
- **Real cause (from CMU, verified + applied):** OmniGraph race in Pegasus
  `spawn_zed_camera.py` (~line 224): the ROS2CameraInfoHelper's `execIn` was wired to
  `playback.outputs:tick`, an unordered sibling of the render-product creators. If it initialized
  before the right render product existed it latched mono **permanently** → `right/camera_info`
  never published → stereo_image_proc/disparity_expansion dead → droan flew without obstacle data.
- **Fix (one line):** trigger `info_helper.inputs:execIn` from `right_nodes['create_rp'].outputs:execOut`.
  Validated end-to-end (3 init cycles; right/left camera_info ~29 Hz; disparity ~28 Hz).
  Upstream: CMU branch `fix/camera-init`, PR pending. Until merged, **every fresh checkout needs
  this fix re-applied** (done in both `~/AirStack` and `~/AirStack-diffaero`).
- Also added an `airstack restart <container>` command to `~/AirStack/airstack.sh` (docker restart
  one container in seconds while isaac-sim stays up; partial-name matching via find_container).
  Note: the active working folder’s `airstack.sh` does NOT have this command (it exists only in `~/AirStack`).
- Debugging subagent definitions were created in `~/AirStack/.claude/agents/` (ros-topic-debugger,
  container-stack-debugger, state-estimation-debugger, planner-debugger, sim-interface-debugger,
  build-debugger, system-test-runner).

### 3.2 Setting up the diffaero branch (2026-07-20)
- Fresh clones are missing two **gitignored** files → copy from `~/AirStack` (or the *_TEMPLATE
  files): `simulation/isaac-sim/docker/omni_pass.env` and `.../user.config.json`.
  Trap: a failed `up` auto-creates the missing mount source as a root-owned **directory** —
  `rmdir` it, then copy the real file.
- **Image rebuild is REQUIRED on this branch** (`./airstack.sh image-build robot-desktop`):
  it bakes `MicroXRCEAgent` into the robot image and pins `ROS_DOMAIN_ID=1` in the container
  .bashrc. The rebuild overwrites the shared `v0.18.0_robot-x86-64_dev` tag that `~/AirStack`
  main also uses (rebuild from `~/AirStack` to restore if main misbehaves).
- Container names in this checkout are prefixed `airstack-diffaero-*` (compose project = folder
  name). `./airstack.sh connect robot --command=bash` resolves regardless.
- `.env` must have: `COMPOSE_PROFILES="desktop,isaac-sim"`, `AUTOLAUNCH="false"`, `NUM_ROBOTS="1"`.

### 3.3 Milestone 1 — sim rehearsal (COMPLETE, 2026-07-20)
Flew 3 SITL drones under the SVG ground controller in Isaac Sim. Full runbook in the docx §5.
Terminal layout (all "inside container" via `./airstack.sh connect <name> --command=bash`):
1. **isaac-sim container:** `NUM_ROBOTS=3 SVG_DOMAIN_ID=1 PLAY_SIM_ON_START=true ISAAC_SIM_HEADLESS=true PYTHONPATH="$ISAAC_SIM_PYTHONPATH" /isaac-sim/python.sh /isaac-sim/AirStack/simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py --ext-folder ~/.local/share/ov/data/documents/Kit/shared/exts`
2. **robot container:** `cd ~/AirStack/robot/ros_ws && bws && sws && ./src/svg_ground_control/scripts/launch_sim_interfaces.sh 3`
3. **robot container:** `ros2 launch svg_ground_control ground_control.launch.py`
4. **robot container:** `rviz2 -d $(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/svg_drones.rviz`
5. **robot container (cockpit):** `ros2 service call /swarm_commander/{takeoff,start,hold,land} std_srvs/srv/Trigger`

Successes: takeoff/hover/land via services; keyboard teleop of drone_3; an accidental **geofence
breach** (drove drone_3 through y<min) → latch froze all drones exactly as designed → recovered
with land → reset_fence → takeoff. RViz markers (`/svg/viz/markers`) as the main viewport
(sim runs headless).

### 3.4 Bug found in CMU's code (FIXED locally — REPORT UPSTREAM, still open)
During breach recovery, drone_3's land command failed → first-ever FAILED service report →
`swarm_commander.py` `report()` (~line 588) used
`level = logger.info if ok else logger.error; level(msg)` — rclpy caches severity per
call-site, one line at two severities raises
`ValueError: Logger severity cannot be changed between calls` → **commander process died with an
aircraft still airborne**. Fixed in
`AirStack/robot/ros_ws/src/svg_ground_control/svg_ground_control/swarm_commander.py` (in the working folder)
by splitting into separate `if ok: ...info(...) else: ...error(...)` call-sites.
Rebuild with `bws --packages-select svg_ground_control`.
**TODO: send traceback + 4-line patch to CMU (branch owner) / open PR.**
Hardware lesson: commander is a single point of failure → PX4 `COM_OBL_RC_ACT` + RC kill switch
are non-negotiable before real flight.

### 3.5 Lab day 1 (2026-07-22) — M2 room half + M3 comms bring-up (the WiFi saga)

**Network topology discovered (TWO routers — laptop is the bridge):**
- Mocap LAN (wired): Motive PC **192.168.8.190**, laptop Ethernet **192.168.8.112**. NatNet rides this.
- Hangar WiFi: SSID `AI.R STC Hangar` = **192.168.10.x** (laptop WiFi **.10.107**); drone joined
  the **-5G** sibling (2.4 GHz inaudible from bench) as **.10.155** on interface **mlan0**.
- Drone's own hotspot (`uap0`, `VOXL-1856926599`) is **192.168.8.1/24 — same digits as the mocap
  LAN**: never connect the laptop to it (subnet clash). Forget it in Ubuntu WiFi settings.
- The two networks never route to each other; ROS in the container (host networking) sees both
  laptop interfaces and is the junction. natnet `clientIP:=192.168.8.112` (ETHERNET), uXRCE agent
  IP for the drone = **192.168.10.107** (WiFi). All DHCP — re-check every lab day.

**M2 room half:** natnet driver connected to Motive first try (50 Hz framerate; `Error getting
Analog frame rate` = harmless; old Crazyflie bodies cf1–cf10 listed). **`drone_1` rigid body not
yet created in Motive** → exit test (`/drone_1/pose` hz + hand-carry) still PENDING.

**M3 drone bring-up (COMPLETE ✅ same day, second half):** PX4 healthy (101 uORB topics, actuators 820 Hz).
CONFIRMED for M4: `voxl-open-vins-server` (~67% CPU) + `voxl-vision-hub` running = onboard VIO
feeding PX4 — must be stopped for mocap sessions. VOXL clock is years off (no NTP) — fix before
log comparisons. Drone hostname `starling2-max (D0012)`, image 1.8.08, voxl-suite 1.6.4~beta5
(LEGACY wpa_supplicant path, no NetworkManager).

**The WiFi saga (2 hours — all now in MILESTONES troubleshooting):**
1. `voxl-wifi station` on this legacy image has a **quoting bug with spaced SSIDs**: it wrote the
   wpa_passphrase ERROR STRING ("Passphrase must be 8..63 characters") into
   `/etc/wpa_supplicant/wpa_supplicant-mlan0.conf` instead of a network block. Root cause of
   every "won't connect" symptom, including the boot-time service failure (unit was enabled;
   it died parsing garbage).
2. Mid-saga the WLAN chip firmware **wedged** (`Firmware Init Failed`, `Card is removed: -2`,
   interfaces vanished): warm reboots don't reset the chip — **cold power cycle** (battery+USB
   out 10 s) fixed it.
3. Working fix: write the conf manually (`printf` header + `wpa_passphrase 'AI.R STC Hangar-5G'
   '<pw>' >>`), `systemctl restart wpa_supplicant@mlan0`, association takes >10 s, then
   `dhcpcd mlan0`. Survives reboots now that the conf parses.
4. adb quirks: Ctrl+C not forwarded (use `-c2 -w4` deadlines or `adb shell pkill`); old `iw`
   needs explicit `iw dev mlan0 link`; drone is headless (cat/less/vi only).

**The `voxl_setup_real_drone.sh` plan (as agreed — executed same day, see next paragraph):** backups agreed —
on-drone `cp /usr/bin/voxl-px4-start /usr/bin/voxl-px4-start.FACTORY-ORIGINAL` + `adb pull` a
copy to `drone-backups/voxl-px4-start.original-D0012` in this repo. Script edits ONLY the
`microdds_client start` line (-h/-p/-n), pins domain, disables onboard agent; makes its own
timestamped .bak. FULL revert = restore FACTORY-ORIGINAL copy + `px4-param reset
UXRCE_DDS_DOM_ID` (or XRCE_DDS_DOM_ID) + `px4-param save` (the script ALSO flash-saves the
domain param — file restore alone doesn't undo it) + `systemctl enable --now
voxl-microdds-agent` + `systemctl restart voxl-px4`.
**M3 COMPLETE ✅ (2026-07-22, second half of lab day 1):** backups taken exactly as above
(FACTORY-ORIGINAL on drone + `drone-backups/voxl-px4-start.original-D0012` committed), script
pushed via `adb push` and run: `voxl_setup_real_drone.sh drone_1 192.168.10.107 1 8888`.
Notes from the run: `voxl-microdds-agent` unit doesn't exist on this image (script warns +
skips — nothing to disable, and the revert recipe's `enable --now` line will just no-op);
immediately after, `px4-microdds_client status` says `PX4 server not running` = PX4 still
rebooting (~30 s); then `Running, disconnected` with correct Agent IP/port = correct pre-agent
state (drone dials out). Agent started in the robot container → `session established
address: 192.168.10.155`, all 24 `/drone_1/fmu/*` topics appeared,
`/drone_1/fmu/out/vehicle_odometry` echoed live messages (`quality: 0`, no position — normal,
EKF2 has no source until M4; corrected the old "stays silent" claim in MILESTONES).
Evidence screenshots in `pictures/`: `voxel_setup_px4_restart_and_client_status.png`,
`successful_airstack_connected_to_drone_microuxre.png`,
`successful_read_of_drone_1_vehicle_odom.png`.

**Architecture teachings from today (for onboarding):** drone needs NO ROS (PX4's built-in XRCE
client → laptop agent creates the `/drone_1/fmu/*` topics laptop-side; drone's dormant ROS Foxy
must never share the domain — cross-distro RTPS crash); MAVROS is sim-only, uXRCE-DDS is the
hardware path (native px4_msgs 1:1, needed for the vehicle_visual_odometry timestamp=0 trick);
offboard mode is entered automatically by the commander's takeoff service, never manually;
laptop = gathers + repackages + shuttles, never fuses (EKF2 fuses onboard).

## 4. Key operational gotchas (bite repeatedly)

1. **ros2 anything only works INSIDE the robot container.** `./airstack.sh connect robot
   --command=bash`; prompt `root@` = container (right), `jeremychia@` = host (wrong, empty topic
   lists, service calls hang "waiting for service"). Host is domain 0; drones are domain 1.
2. **Paste one line at a time** — `connect` opens an interactive shell; block-pastes spray
   commands into the wrong shell and leave garbage in the input buffer (Ctrl+C clears).
3. `bws`/`sws` = AirStack bash functions (colcon build --symlink-install / source install) defined
   in `robot/docker/.bashrc`; exist only in robot containers. Build artifacts persist on host.
4. **Commander state machine:** IDLE —takeoff→ HOLDING —start→ ACTIVE —hold→ HOLDING.
   HOLDING ignores nominal inputs (that's the freeze). Teleop only works in ACTIVE, and
   keypresses go to the teleop node's own terminal (focus!).
5. `/fmu/*` topics (real drone, uXRCE-DDS) are best-effort QoS — `ros2 topic echo/hz` needs
   `--qos-reliability best_effort` or they look dead.
6. Sim-only noise: `[timesync] time jump` warnings = sim below real-time (GPU load);
   `Preflight Fail: Battery unhealthy` after ~20 min hover = SITL battery drained → Ctrl+C and
   re-run the Isaac spawn script.
7. apt installs in containers (e.g. PlotJuggler: `apt install -y ros-jazzy-plotjuggler-ros`)
   vanish on `down`/`up` (fresh container), survive `restart`.
8. NatNet launch defaults are **CMU's lab IPs** — always override `serverIP:=<MOTIVE_IP>
   clientIP:=<LAPTOP_IP>`. Ports 1510/1511; check for orphan processes squatting them
   (`ss -ulpn | grep -E '1510|1511'`) — a past lab outage was exactly this.

## 5. The milestone plan (details + commands in the docx and experiment.md)

> Statuses below are from the original 2026-07-20 write-up — for CURRENT state see §3.5 and
> the MILESTONES.md status table (as of 2026-07-22: M2 desk ✅ / room nearly; M3 ✅ banked).

- **M1 Sim rehearsal — DONE** (see 3.3).
- **M2 Ground-station hardware prep — NEXT (desk, no drone):** robot container to
  `network_mode: host` (edit `robot/docker/docker-compose.yaml`: comment `networks:`/`ports:` of
  robot-desktop); Motive rigid body named exactly `drone_1`, streaming **Up Axis = Z**, Broadcast
  ON; chrony/NTP across laptop + Motive PC; port 1510/1511 check.
  Already done: QGC AppImage (~/Downloads), PX4 SITL standalone build (~/PX4-Autopilot).
- **M3 Drone comms, props off:** drone on LAN (adb, DHCP/voxl-wifi); push + run
  `voxl_setup_real_drone.sh drone_1 <LAPTOP_IP> 1 8888` on the VOXL (points PX4 uXRCE client at
  laptop, disables onboard agent); ground: `MicroXRCEAgent udp4 -p 8888 -v4`; verify
  `/drone_1/fmu/out/vehicle_status` arrives (best_effort QoS).
- **M4 Mocap → EKF2, props off:** `bws --packages-select natnet_ros2` (SDK is vendored in the
  repo — no internet needed, see MILESTONES §3b); launch with lab IPs; verify `/drone_1/pose`
  ~50 Hz smooth (our Motive rate);
  PX4 params `EKF2_EV_CTRL=11, EKF2_HGT_REF=3, EKF2_GPS_CTRL=0, EKF2_EV_DELAY≈50`
  (**mandatory — indoors PX4 refuses to arm without a fused position source**); check
  voxl-vision-hub isn't a second EV source; commander with `swarm_real.yaml use_mocap:=true`;
  verify `fmu/in/vehicle_visual_odometry` streams and `fmu/out/vehicle_odometry` appears;
  **frame hand-check** (North → position[0]↑, East → position[1]↑, lift → position[2]↓ (NED);
  mirrored → `px4_vio_frame: "modalai_flip"`). A wrong frame flies into a wall.
- **M5 Hand-carry preflight:** all flight-day nodes + `real_interfaces.launch.py drones:=drone_1`,
  commander idle (NO takeoff), RViz red sphere must track the hand-carried drone; record bag.
- **M6 First flight:** `drone_names: ["drone_1"]`, `drone_modes: "real"`, hover, fence inside net,
  ≤1.0 m/s; RC kill mapped/tested; `COM_OBL_RC_ACT`; then the same three service calls as sim.
  Geofence freezes only — RC kill is the sole motor cutoff.

## 6. Mocap data path (the two packages that matter)

```
Motive ──NatNet UDP 1510/1511──► natnet_ros2 ──► /drone_1/pose (PoseStamped, ~50 Hz — our Motive rate)
                                                     │
                                               mocap_bridge  (svg_ground_control; launched by
                                                     │        ground_control.launch.py use_mocap:=true;
                                                     ▼        timestamp=0 trick, pose-only, enu_to_ned
                                 /drone_1/fmu/in/vehicle_visual_odometry      or modalai_flip frame)
                                                     │ MicroXRCEAgent ──WiFi──► VOXL2 PX4 EKF2
                                                     ▼
                                 /drone_1/fmu/out/vehicle_odometry → px4_interface →
                                 /drone_1/odometry_conversion/odometry → swarm_commander
```

## 7. Open items

- [ ] Report the swarm_commander logging crash + fix upstream to CMU (traceback in docx §4.4).
- [ ] Ask CMU to confirm `daniel/diffaero_ground_control` is the branch behind their report
      (assumed from code archaeology; high confidence, unconfirmed by authors).
- [ ] M2 room half (`drone_1` rigid body in Motive + exit test); M4–M6 need the drone and the mocap room. M3 ✅ done 2026-07-22.
- [ ] Optional cleanup: remove redundant worktrees under `~/airstack-branches/`.
- [ ] When CMU's `fix/camera-init` merges: pull + submodule update makes our camera fix redundant.

## 8. Related persistent memory (Claude auto-memory)

`~/.claude/projects/-home-jeremychia/memory/` — entries `airstack-starling-project`,
`airstack-pose-drift` (camera-race resolution), `mocap-multicast-freeze` (port 1511 lesson).
This file is the detailed companion; memory entries point here.
