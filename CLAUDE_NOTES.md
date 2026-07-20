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
- **M4 Mocap → EKF2, props off:** `bws --packages-select natnet_ros2` (first build downloads
  NatNet SDK, needs internet); launch with lab IPs; verify `/drone_1/pose` ~180 Hz smooth;
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
Motive ──NatNet UDP 1510/1511──► natnet_ros2 ──► /drone_1/pose (PoseStamped, ~180 Hz)
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
- [ ] M2 tasks (see §5). M3+ need the drone and the mocap room.
- [ ] Optional cleanup: remove redundant worktrees under `~/airstack-branches/`.
- [ ] When CMU's `fix/camera-init` merges: pull + submodule update makes our camera fix redundant.

## 8. Related persistent memory (Claude auto-memory)

`~/.claude/projects/-home-jeremychia/memory/` — entries `airstack-starling-project`,
`airstack-pose-drift` (camera-race resolution), `mocap-multicast-freeze` (port 1511 lesson).
This file is the detailed companion; memory entries point here.
