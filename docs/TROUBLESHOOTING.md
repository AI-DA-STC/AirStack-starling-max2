# TROUBLESHOOTING — something misbehaves, find your symptom

> **What this is:** one symptom → fix index for the whole rig, by layer: ground software,
> mocap, flight/arming, simulation, drone/network. **Who reads it:** whoever is at the laptop
> when something goes wrong — pick the section for the layer that misbehaves, find the row,
> apply the fix, then add a row if you learned something new.
> Merged from the per-doc tables 2026-09-07; updated for `yikuan/SVG_ground_control_dev` @
> `b21d28c`, 2026-10-21.
> Safety first: if the drone is AIRBORNE and misbehaving →
> [PREFLIGHT.md](PREFLIGHT.md) emergencies table FIRST, debug after.
>
> **First move on this branch, for anything ground-side:** `ros2 topic echo /svg/commander_status --once`
> — one JSON message with every drone's state, odometry freshness, the fence status, the
> live CBF gains and the last command's outcome ([BASESTATION.md](BASESTATION.md) §4).
> Where else to look: the panel: [BASESTATION.md](BASESTATION.md) §7 · gamepad: [TELEOP.md](TELEOP.md) §10 ·
> CBF/scenarios: [SCENARIOS.md](SCENARIOS.md) §10 · **Sim (Isaac / PX4 SITL / MAVROS) →
> [§ Simulation](#simulation-isaac-sim--px4-sitl--mavros) below.**
>
> Names used here: "the commander" = `swarm_commander` (the ground-side node that flies the
> drones); "the panel" = the Foxglove SVG Basestation panel; "the real drone" = our Starling
> `drone_1`; the sim's four terminal tabs are the **Isaac Sim / Interfaces / Commander /
> Cockpit tabs** opened by `tools/sim_terminals.sh` ([RUNBOOK.md](RUNBOOK.md) §A0).

*(Unfamiliar term? → [GLOSSARY.md](GLOSSARY.md))*

## Bring-up / ground software

| Symptom | Cause / fix |
|---|---|
| `ros2` not found / empty topics / service call hangs "waiting" | Wrong shell — you're on the laptop host. `./airstack.sh connect robot` first (lands in the tmux `bringup` session, `root@` prompt) |
| tmux pane shows a bare `bash` prompt with no workspace / `sws_after_build` never returns | pane 0's `bws` never ran or failed — run `cd ~/AirStack/robot/ros_ws && bws && sws` in pane 0; the others source when `.build.lock` is released |
| Everything on the wrong DDS domain after a `./svg_teleop.sh` run | a tmux *server* inherits the env of the shell that started it — `./svg_teleop.sh stop`, then `tmux kill-server` inside the container, then relaunch (the script re-exports `ROS_DOMAIN_ID` per session) |
| `bws: command not found` | Wrong container (Isaac) or host shell |
| `omni_pass.env not found` on `up` | Re-run `./airstack.sh setup` to (re)generate it (press Enter at the API Token prompt) |
| "mounting … user.config.json … not a directory" | A failed `up` created a directory; `rmdir` it, then re-run `./airstack.sh setup` |
| `/fmu/*` topics look dead | `echo` needs `--qos-reliability best_effort` (`hz` takes no QoS flag here); and is the uXRCE agent running? |
| No odometry reaching the commander / Basestation row says `odom none` / takeoff refused | Per-drone interfaces not running — [RUNBOOK.md](RUNBOOK.md) §B step 5 (`real_interfaces.launch.py drones:=drone_1`) must be up |
| Basestation shows `NO COMMANDER` | commander not running, or Studio connected to the wrong source — bridge is `ws://localhost:8765`, started by the commander launch (`use_foxglove_bridge` default true) |
| Foxglove Studio cannot connect to `ws://localhost:8765` | the bridge is a node inside the commander launch — is it up? `use_foxglove_bridge:=false` passed? Port squatter: `ss -ltnp \| grep 8765`. The `gcs` container is NOT involved |
| Basestation buttons greyed, CBF row reads `live -- (no services)` | Studio is on a bag/file source, not the live WebSocket — normal when reviewing a recording |
| Two Basestation instances show different numbers | independent subscribers with their own settings — compare each one's `View` / `Drones` / `Modes` (gear icon) |
| Basestation's Cellular / Tailscale section appeared | something publishes `*/comms/cellular` or `*/cellular/odometry` on domain 1 — we have no cellular; find it before flying |
| Basestation panel missing from Studio's panel list | extensions load only at Studio start — run `foxglove/install.py` (host) then **restart Studio**; in-container Studio: the installer runs at `up` |
| The panel looks like the OLD one after a snapshot bump (3-gain dropdown, an "Agents" roster card still there) | the panel is copied into `~/.foxglove-studio` at container start only. Re-run `docker exec airstack-robot-desktop-1 python3 /root/AirStack/robot/ros_ws/src/svg_ground_control/foxglove/install.py`, then quit and relaunch Studio (with `use_foxglove_studio:=true` → relaunch the commander) |
| Basestation layout cut off / everything stacked left | old single-panel layout — Layouts → Import `svg_basestation.json` again |
| Basestation Goal card says frame "unconfirmed" | no status snapshot received yet — wait for the commander; goals sent before that may be offset by `drone_position_offsets` |
| Agent State `Cmd stream` reads `--` on a real drone that is clearly flying | the column watches `velocity_command` topics only; real drones on this branch publish `trajectory_command` — panel limitation, not the drone. Check `ros2 topic hz /drone_1/fmu/trajectory_command` instead ([BASESTATION.md](BASESTATION.md) §6) |
| RViz (fallback) empty + "Global Status: Error" on the real rig | `svg_drones.rviz` ships with Fixed Frame `map` (sim default) — set it to `world` |
| `led_controller` warns `no heartbeat from drone_1` | no LED strip / daemon on the drone — harmless; `use_led:=false` silences it. With a strip: udp/47901 blocked (`ufw`), or `svg-led` not running on the drone |
| A second `led_controller` exits at start ("address in use") | by design — one controller per port; `pgrep -af led_controller`, kill the stray |
| Weird/fake odometry on real topics | A `test/functional_*.py` is running — they publish fake odometry on the real topic names. **Never run them with the real stack up.** Kill it, restart the stack |
| A tool you `apt install`ed in the container is gone | Container apt installs (e.g. `apt install -y ros-jazzy-plotjuggler-ros`) **vanish on `airstack.sh down`/`up`** — that builds a fresh container — but survive a `restart`. Re-install it, or add it to the image if you need it every session |
| Commander dies: "Logger severity cannot be changed" | fixed upstream on this branch (patch 0002 retired) — if it ever recurs, a new call site regressed; report upstream |
| Commander launch: `teleop fence … must lie inside the geofence` / `ValueError` | the `teleop_fence_*` box pokes outside `fence_min/max` — fix the yaml ([TELEOP.md](TELEOP.md) §6) |
| Commander launch: "external drone may not also be CBF-exempt" | a name is in both `external_drones` and `cbf_exempt_drones` — pick one |
| A new commander launch killed the one that was running | `takeover_twins` (default true) — intended; it refuses only if the old one had a drone airborne. Add `takeover:=false` to keep both |
| `ros2 param set /swarm_commander …` refused | only the live list is settable (CBF gains, fence dynamics, goal law, teleop gains — [SCENARIOS.md](SCENARIOS.md) §3); gains must be > 0; everything else needs a relaunch |

## Mocap

| Symptom | Cause / fix |
|---|---|
| `/drone_1/pose` missing / 0 Hz | Is `./mocap.sh` running (laptop host terminal, NOT docker)? Then `./mocap.sh check` — its verdict names the culprit (Motive not streaming / wrong network / port 1511 squatter). Full table: [MOCAP.md](MOCAP.md) §5 |
| **Poses stop while the drone is AIRBORNE** | **Land or kill FIRST** ([PREFLIGHT.md](PREFLIGHT.md)), debug after — EKF2 drifts within seconds without vision |
| Bridge lists `cf1…` bodies but no `drone_1` | Rigid body not created/named yet in Motive — [MOCAP.md](MOCAP.md) §6.3; then restart the bridge (body list read once at startup) |
| `/drone_1/pose` at ~50 Hz, not 120+ | Normal — our Motive runs 50 Hz ([CONFIG.md](CONFIG.md); adjustable in Motive's camera settings) |
| Floor z reads ~1 m with the drone on the ground | Motive origin/ground-plane problem — STOP, recalibrate + frame hand-check ([MOCAP.md](MOCAP.md) §6.1) |
| natnet log: `Error getting Analog frame rate` | Harmless (legacy driver; no force plates on our rig). Ignore |

## Flight / arming

| Symptom | Cause / fix |
|---|---|
| PX4 won't arm indoors ("fuse failure" / "Not Ready") | No fused position source — mocap feed down or EKF2 params missing ([CONFIG.md](CONFIG.md) §PX4/EKF2, the `.params` file) |
| Takeoff refused: "no drone eligible (missing odometry or not IDLE)" | In order: **1.** commander stuck non-IDLE after an RC takeover / Ctrl-C → call `land` once (drone on floor); **2.** interfaces not running — RUNBOOK §B step 5; **3.** mocap bridge down → `./mocap.sh check`; **4.** config names a drone you don't have (CMU's 3-drone real configs; `goal_single.yaml` targeted `drone_2` at `cf719f0`, `drone_1` since `b21d28c`) |
| `takeoff` accepted, Interface column / `px4_interface` log shows **nothing** (no ack), drone sits | `target_system` ≠ the drone's `MAV_SYS_ID` — PX4 drops the command silently. Check the `px4_interface` startup line; `target_systems:=` on the interface launch ([CONFIG.md](CONFIG.md) §Protocol constants) |
| `takeoff` accepted, ack says **`DENIED`** | PX4 preflight refused (no fused position, EKF not ready, kill switch engaged) — QGC's message bar names it |
| Goal / speed / formation commands do nothing, no error | the running scenario has no retargetable goals — `cbf_sim.yaml` ships `antipodal`, and `scenario:=random_goals` / `head_on` / `random_walk` ignore goals (`goal_tracking.yaml` did too at `cf719f0`; it ships `goal` at `b21d28c`); use a `goal`-scenario config or `scenario:=goal` ([SCENARIOS.md](SCENARIOS.md) §10) |
| Startup WARN `formation_profiles set but scenario "X" has no retargetable goals; profiles ignored` | expected on `cbf_sim.yaml` (`antipodal`) or any launch with `scenario:=random_goals` (`goal_tracking.yaml` ships `goal` at `b21d28c`) — add `scenario:=goal` to the launch ([SCENARIOS.md](SCENARIOS.md) §6) |
| `CBF emergency push-apart engaged` in the log / every LED red at once | drones already inside each other's safety bubbles — the solve is infeasible. **Land and investigate** ([SCENARIOS.md](SCENARIOS.md) §1) |
| An exempt / RC-flown drone is pushed backwards instead of through the gap | its exemption is not in effect: check the startup roster for `/cbf-exempt` on that name, that it is **ACTIVE** (climb-out and landing are never exempt), and the spelling in `cbf_exempt_drones` |
| Drone slows or refuses to approach a goal / another drone | the CBF is correcting it — Basestation CBF column `correcting`, LEDs red. Normal; raise `cbf_alpha` for later/harder yielding, or check `cbf_safety_radius_m` |
| Drone stops short of a goal that sits near the fence wall | `keep_in` braking envelope — the wall caps outward speed; a goal *past* the wall is clamped to it. Keep `fence_brake_accel_mps2 ≥ goal_accel_mps2` or the wall also caps cruise speed |
| Real drone hovers but never moves to a goal after the branch switch | `px4_interface` not rebuilt — it does not subscribe `trajectory_command` until rebuilt (`bws`), then relaunch the interfaces ([MIGRATION.md](MIGRATION.md) §6) |
| **Landing ends with the drone still armed** — QGC shows ARMED after touchdown, or the log says `Disarming denied` / `disarm -> success=False`; in sim `mavros/state` `armed: true`, props spinning | Real drone and sim differ — read the REAL / SIM bullets right under this table. Real: flip KILL (ch8 — harmless on the ground) or the arm switch (ch5) down first, then read on |
| RC sticks ignored / fighting in Position/Altitude mode | Control-authority leak: PX4 v1.14 still consumes commander setpoints in those modes. Take over into **MANUAL** (or kill) only |
| Fence breach → everything frozen mid-air (`FENCE BREACH` chip) | `hold_all` behaviour, by design: freeze-hover, **still armed**, not a motor cut. Recover: `land` → `reset_fence` (or panel **Reset Fence**) → `takeoff` → `start`. Now also triggers when an **RC-flown** drone is airborne outside the box. `keep_in` configs never latch |
| Gamepad sticks do nothing | in order: `start` not called; drone not in `teleop_drones`; `safe_teleop` log says `REFUSING TO COMMAND` (axis guard — wrong controller profile, [TELEOP.md](TELEOP.md) §3); `/joy` stale (pad asleep/unplugged); container created before the `/dev/input` mount — recreate it |
| `safe_teleop` prints `pad: NO /joy` forever | `joy_node` cannot see the device: `ls /dev/input/js0` on the laptop, then inside the container. Missing in the container ⇒ created before the `/dev/input` bind mount — recreate it (`down` + `up`). Present but unreadable ⇒ add yourself to the `input` group and re-login |
| Yaw turns the wrong way on the first teleop flight | expected risk — sim cannot prove yaw sign (`px4_interface` negates the ENU yaw rate). Land, flip `yaw_sign` in the config's `safe_teleop` block, relaunch ([TELEOP.md](TELEOP.md) §2) |
| Hand-flown drone hovers ~30 cm up on `land` and never touches down | a reference clamped to the teleop-fence floor (`teleop_fence_min` z) — should not happen (only ACTIVE drones are clipped); if it does, `hold` → `land` again → kill if it persists, and note the bag |
| Drone drifts/sinks slowly during hand-flying, or keeps going after release | should be fixed on this branch (separate horizontal/vertical leash, ramp re-attaches to the published command) — if seen, note the bag and check `teleop_lead_m` / `teleop_accel_mps2` ([TELEOP.md](TELEOP.md) §7) |
| `hold` makes the drone continue forward before stopping | by design now — it brakes to a predicted stop point ahead instead of flying back to the call position |
| Startup WARNs about `drone_2`/`drone_3` with only one drone; the panel's Agent State / 3D view carry drones that never get odometry | the loaded config lists three drones (CMU's 3-drone real configs — `swarm_real`, `goal_tracking`, `goal_sequence`, …; `goal_single.yaml` is single-drone `drone_1` at `b21d28c`). Our `swarm_real_ours.yaml` / `goal_single_ours.yaml` are single-drone (`drone_1`) — fly those ([MIGRATION.md](MIGRATION.md) §6). (The old "Agents roster" card is gone since the 10-20 bump) |

**Landing ends with the drone still armed — detail**

- **REAL drone** — fly the `_ours` configs: `land_settle_s` 0.0 (the landing flown 2026-09-03)
  and `land_speed_mps` 0.6 (0.3 left the drone armed on the ground — archive ledger #21, the
  reason CMU's shipped `swarm_real.yaml` 0.3 must not be flown). One red "Disarming denied" per
  landing was the known one-shot behaviour; PX4's own `COM_DISARM_LAND` finishes the job. Still
  armed after that: KILL or arm switch down, then investigate — never approach a spinning
  drone. Confirm **DISARMED in QGC** every time (iron rule 2). The settle/retry code path is
  exercised on the real drone only through the M3 landing sub-test
  ([MILESTONES.md](MILESTONES.md) M3); the retry is inert there (`px4_interface.disarm()` reports
  success on send) — the ACK in the `px4_interface` log is the only evidence.
- **SIM** — `cbf_sim.yaml` runs the settle + retry: `land_settle_s` 2.0 keeps the descent
  commanded on the ground, then DISARM; a denied DISARM is resent every `land_disarm_retry_s`
  (1 s) up to `land_disarm_retries` (5). Expected log: `touchdown … settling 2.0 s` →
  `landed, disarmed (attempt 1)`; failure: ERROR `disarm not accepted after 5 tries`. The 10-20
  refusals came from PX4's land detector seeing the body rock on the floor (a PhysX contact
  artefact — ledger #9); the sim airframe carries **`LNDMC_ROT_MAX` 300 since 2026-10-20**
  (**sim-only — never port to the drone**; the real drone's params set 30). If it recurs: `param show
  LNDMC_ROT_MAX` in the PX4 shell (airframe mount stale?), land from a hover rather than
  mid-leg, and use the knob `ros2 param set /swarm_commander land_settle_s 4.0` before landing
  again. Three clean landings with DISARM accepted first time: ledger #13.

## Simulation (Isaac Sim / PX4 SITL / MAVROS)

Sim-only rows. Isaac Sim runs the physics, PX4 SITL is the real flight firmware running on
the laptop, MAVROS is the sim-only bridge between PX4 SITL and ROS 2 (the real drone uses
`px4_interface` instead). The sim airframe's deviations (rate gains ×0.5, gyro filters 80/40,
`LNDMC_ROT_MAX` 300, motor lag off), the MAVROS respawn and `cbf_sim.yaml`'s speeds / landing
settle + retry are **sim-only — never port to the drone** (iron rule 9). The most destructive
mistake comes first.

| Symptom | Cause / fix |
|---|---|
| Commander tab spams red `[foxglove_bridge] Failed to load schemaDefinition for topic "/poses" (motion_capture_tracking_interfaces/msg/NamedPoseArray): package not found` while `./mocap.sh` runs | Harmless, and silenced since 2026-10-21: `ground_control.launch.py` gives the Foxglove bridge a `topic_whitelist` that skips `/poses`. Why it was harmless: `/poses` is the laptop receiver's raw topic in a message type the container lacks; nothing in the container reads it — the relay turns it into the per-body `/drone_N/pose`, which is what `mocap_bridge` (→ PX4) and the panel use. If the spam is back, the commander was launched from an older launch file |
| **Pressed Stop ▶ Play in the Isaac window to reset the drones → everything dead** (MAVROS `connected: false`, `VER: unicast request timeout`, panel `LINK/EKF/POWER NO DATA`, commander alive but blind) | **Not a reset — don't** ([MILESTONES.md](MILESTONES.md) §3c #6). Recover = full restart: Ctrl-C in the **Isaac Sim tab**, relaunch (RUNBOOK §A1), then Ctrl-C + relaunch the **Interfaces tab**, then the **Commander tab**, in that order. Why, and how to bring drones home without a restart: detail below |
| Interfaces tab shows `[ERROR] [mavros_node-N]: process has died … exit code -11` (or -6); commander repeats `drone_N: odometry stale, commanding zero velocity` | that drone's MAVROS crashed. **Since 2026-10-20 the sim launch respawns `mavros_node` after 2 s** (`interface_bringup/launch/mavros_px4.launch.xml`, sim-only) — odometry and the panel come back on their own, but PX4 is already on its offboard-loss failsafe: two-command recovery in the detail below |
| Drone sits armed after touchdown: `disarm -> success=False` ×5, `disarm not accepted after 5 tries`, log shows `touchdown … settling` | → "Landing ends with the drone still armed", SIM bullet (Flight / arming above). Quick check: `param show LNDMC_ROT_MAX` in the PX4 shell must read 300 (sim airframe since 10-20) |
| Starling looks hollow — props, legs and electronics visible, no body | your checkout has the 10-19 asset, built by a decimation that deleted whole body parts. Fixed in the repo 2026-10-20 (ledger #9) — `git pull`, relaunch the sim. To rebuild the asset yourself: command in the detail below |
| Starling wobbles / shivers in pitch while hovering (props visibly rocking fore-aft) | a rate-loop limit cycle (pitch rate ±270 deg/s at 9 Hz), not a scene problem. Fixed 2026-10-20 by halving the sim airframe's rate gains (ledger #10). If it is back, the airframe mount is stale: `param show MC_PITCHRATE_P` in the PX4 shell should read 0.032 |
| "Battery unhealthy", won't arm | SITL battery drained — restart the Isaac spawn script (Isaac Sim tab) |
| Continuous `[timesync]` warnings | sim below real-time; reduce load |
| No camera / `add_rtx_lidar_subgraph` import error at launch | the Pegasus submodule renamed the lidar/camera APIs; only `ENABLE_LIDAR`/`ENABLE_CAMERA` runs are affected — run without them, or update the launch script's lazy imports |
| dmesg shows `robot_interface[...]: segfault ... in libstdc++` after Ctrl-C of the Interfaces tab | a shutdown race in CMU's `robot_interface_node` destructor, seen only at SIGINT (2026-10-20). Cosmetic — nothing was flying through it. Not fixed; the node is shared with the real-drone path, so it is reported, not patched (MILESTONES §6 "Sim debt") |

**Hollow drone — rebuilding the asset.** Needs CMU's 98 MB `isaac_sim/starlingmax2.usd`
(gitignored); run from the repo root, then relaunch the sim:
`AirStack/simulation/isaac-sim/tools/isaac_python.sh AirStack/simulation/isaac-sim/tools/clean_starling_usd.py /repo/isaac_sim/starlingmax2.usd /repo/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd`

**Stop ▶ Play — detail.** Pegasus kills PX4 ×3 on Stop and relaunches on Play, but the OLD
vehicles' physics callbacks survive and call the closed MAVLink link every step (the Isaac log
floods with `'NoneType' object has no attribute 'recv_match'`); the new PX4s never connect
(observed 2026-10-20). To get drones home without a restart: `hold` → formation `home` → wait
→ `land`.

**MAVROS died — detail.** 2026-10-20: twice on drone_3 — one unexplained segfault mid-flight,
one abort during forced `param/set` writes (never use `force_set` on MAVROS param writes).
After the respawn PX4 ignores the commander (offboard-loss failsafe, 1 s), so:
`ros2 topic echo /drone_N/interface/mavros/state --once`; if `mode` is not OFFBOARD →
`ros2 service call /drone_N/interface/mavros/set_mode mavros_msgs/srv/SetMode "{custom_mode: AUTO.LAND}"`,
then the commander's `land` once to reset it (iron rule 3). A MAVROS that dies every 2 s at
startup is a config error — read the first death's lines. Root cause of the segfault is still
open (no core dumps: the host's `core_pattern` is apport) — MILESTONES §6 "Sim debt".

## Drone-side / network

| Symptom | Cause / fix |
|---|---|
| QGC shows no vehicle | Drone's `gcs_ip` must equal the laptop's *current* hangar-LAN IP. Read back: `ssh root@<DRONE_IP> "grep gcs_ip /etc/modalai/voxl-mavlink-server.conf"` → fix → `systemctl restart voxl-mavlink-server`. Also check laptop `ufw` isn't blocking inbound UDP 14550 |
| After `voxl_setup_real_drone.sh`: QGC "params missing", sensor topics never publish, `px4-listener` empty | the script's PX4 restart wedged the SLPI flight core on this airframe — **reboot the drone** (always reboot after provisioning, never `systemctl restart voxl-px4`) |
| uXRCE client keeps dying / two things restarting it | both `svg-microdds-watchdog` (new script) and our `voxl-dds-retry.service` are active — keep one (`systemctl disable --now` the other), record in CONFIG.md |
| Drone WiFi: `voxl-wifi station` "succeeds" but never connects | Legacy voxl-wifi mangles SSIDs **with spaces**. Spaced SSID → write `wpa_supplicant-mlan0.conf` manually with `wpa_passphrase` (archived MILESTONES M3-A (`git show airstack-starling-max2:docs/MILESTONES.md`)); space-free SSIDs are fine |
| Drone WiFi gone after reboot; dmesg `Firmware Init Failed` / `Card is removed` | WLAN chip wedged — warm reboots don't clear it. **Cold power cycle** (battery + USB out, 10 s) |
| **Older Starling Max 2 only** (USB dongle, `wlan0`): boots on **`169.254.x.x`** instead of its DHCP address | Link-local fallback = never associated, *not* a DHCP fault: `wpa_supplicant` burns its 5 systemd starts in <1 s while `wlan0` doesn't exist until t≈9 s, then quits for good. Fix = the `10-wait-for-wlan0.conf` drop-in (`StartLimitIntervalSec=0` + `RestartSec=5`). Recover now: `systemctl reset-failed wpa_supplicant && systemctl start wpa_supplicant` (plain `restart` will NOT work). Full writeup: [CLAUDE.md](../CLAUDE.md) |
| **Older Starling Max 2 only**: no `wlan0` at all, `lsmod` shows `8852bu` with refcount `0` | Kernel-builtin `option` serial driver stole the dongle and made it `/dev/ttyUSB0` (usb_modeswitch poisons `option1/new_id`). Check `readlink /sys/bus/usb/devices/1-1.4:1.0/driver` → must be `rtl8852bu`. Fix = `NoDriverLoading=1` in `/etc/usb_modeswitch.d/0bda:1a2b`. Live: unbind from `option`, bind to `rtl8852bu` — [CLAUDE.md](../CLAUDE.md) |
| Drone pings the router but **not the GCS**, firewall already off | Asymmetric routing, not a firewall. Laptop replies leave via the wrong NIC when the drone is on a different subnet. `sudo ip route add <drone_subnet> via 192.168.9.1 dev <gcs_nic>`; persist with `nmcli ... +ipv4.routes`. Proof trick with no root: `/proc/net/snmp` Icmp `InEchos`/`OutEchoReps` both rise ⇒ packets arrive and are answered — [CLAUDE.md](../CLAUDE.md) |
| Drone `iw` prints usage instead of link info | Old iw needs explicit syntax: `iw dev mlan0 link` |
| Ctrl+C does nothing in `adb shell` | VOXL adbd doesn't forward signals — kill from a second shell (`adb shell pkill <cmd>`) or use self-terminating commands (`ping -c2 -w4`) |
| QGC shows wrong dates on the drone's flight logs | Drone clock unsynced (no NTP). Match logs by **size**; logs at `/data/px4/log/sessNNN/` (ssh — password in CONFIG.md), pull procedure: [RUNBOOK.md](RUNBOOK.md) §D |
| Need the drone's IP (RUNBOOK §B step 0's `ssh`, §D `scp`) | router admin page (`http://192.168.9.1:8080`), or `adb shell voxl-my-ip`, or the agent's `session established` line. The drone auto-joins SSID `StarlingMax2` at boot (moved from RUNBOOK §B step 1, 2026-10-21) |
| WiFi missing after reboot + dmesg `Firmware Init Failed` | cold power cycle: battery + USB out 10 s (moved from RUNBOOK §B step 1, 2026-10-21 — same fix as the `Card is removed` row above) |
