# TROUBLESHOOTING — something misbehaves, find your symptom

> Unified symptom index for the whole rig (merged from the per-doc tables, 2026-09-07;
> updated for `yikuan/SVG_ground_control` 2026-10-07).
> Safety first: if the drone is AIRBORNE and misbehaving →
> [PREFLIGHT.md](PREFLIGHT.md) emergencies table FIRST, debug after.
>
> **First move on this branch, for anything ground-side:** `ros2 topic echo /svg/commander_status --once`
> — one JSON message with every drone's state, odometry freshness, the fence status, the
> live CBF gains and the last command's outcome ([BASESTATION.md](BASESTATION.md) §4).
> Panel-specific symptoms: [BASESTATION.md](BASESTATION.md) §7 · gamepad: [TELEOP.md](TELEOP.md) §10 ·
> CBF/scenarios: [SCENARIOS.md](SCENARIOS.md) §10.

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
| Isaac: no camera / `add_rtx_lidar_subgraph` import error | the Pegasus submodule renamed the lidar/camera APIs; only `ENABLE_LIDAR`/`ENABLE_CAMERA` runs are affected — run without them, or update the launch script's lazy imports |

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
| Takeoff refused: "no drone eligible (missing odometry or not IDLE)" | In order: **1.** commander stuck non-IDLE after an RC takeover / Ctrl-C → call `land` once (drone on floor); **2.** interfaces not running — RUNBOOK §B step 5; **3.** mocap bridge down → `./mocap.sh check`; **4.** config names a drone you don't have (`goal_single.yaml` ships as `drone_2`) |
| `takeoff` accepted, Interface column / `px4_interface` log shows **nothing** (no ack), drone sits | `target_system` ≠ the drone's `MAV_SYS_ID` — PX4 drops the command silently. Check the `px4_interface` startup line; `target_systems:=` on the interface launch ([CONFIG.md](CONFIG.md) §Protocol constants) |
| `takeoff` accepted, ack says **`DENIED`** | PX4 preflight refused (no fused position, EKF not ready, kill switch engaged) — QGC's message bar names it |
| Goal / speed / formation commands do nothing, no error | the running scenario has no retargetable goals — `goal_tracking.yaml` ships `scenario: random_goals`; use a `goal`-scenario config or `scenario:=goal` ([SCENARIOS.md](SCENARIOS.md) §9) |
| Startup WARN `formation_profiles set but scenario "X" has no retargetable goals; profiles ignored` | expected on `cbf_sim.yaml` (`antipodal`) and `goal_tracking.yaml` (`random_goals`) — add `scenario:=goal` to the launch ([SCENARIOS.md](SCENARIOS.md) §6) |
| `CBF emergency push-apart engaged` in the log / every LED red at once | drones already inside each other's safety bubbles — the solve is infeasible. **Land and investigate** ([SCENARIOS.md](SCENARIOS.md) §1) |
| An exempt / RC-flown drone is pushed backwards instead of through the gap | its exemption is not in effect: check the startup roster for `/cbf-exempt` on that name, that it is **ACTIVE** (climb-out and landing are never exempt), and the spelling in `cbf_exempt_drones` |
| Drone slows or refuses to approach a goal / another drone | the CBF is correcting it — Basestation CBF column `correcting`, LEDs red. Normal; raise `cbf_alpha` for later/harder yielding, or check `cbf_safety_radius_m` |
| Drone stops short of a goal that sits near the fence wall | `keep_in` braking envelope — the wall caps outward speed; a goal *past* the wall is clamped to it. Keep `fence_brake_accel_mps2 ≥ goal_accel_mps2` or the wall also caps cruise speed |
| Real drone hovers but never moves to a goal after the branch switch | `px4_interface` not rebuilt — it does not subscribe `trajectory_command` until rebuilt (`bws`), then relaunch the interfaces ([MIGRATION.md](MIGRATION.md) §6) |
| Landed but QGC still shows ARMED | Flip KILL (ch8 — harmless on the ground) or arm switch (ch5) down. History: the `land_speed_mps=0.3` era symptom — retuned to `0.6` ([CONFIG.md](CONFIG.md)); investigate if it recurs |
| QGC red "Disarming denied, not landed" once per landing | Cosmetic — the commander's premature one-shot disarm (fires ~15 cm up, always denied). PX4's auto-disarm does the real work ([MILESTONES.md](MILESTONES.md) §6 Fix 1 if it ever stops sufficing) |
| RC sticks ignored / fighting in Position/Altitude mode | Control-authority leak: PX4 v1.14 still consumes commander setpoints in those modes. Take over into **MANUAL** (or kill) only |
| Fence breach → everything frozen mid-air (`FENCE BREACH` chip) | `hold_all` behaviour, by design: freeze-hover, **still armed**, not a motor cut. Recover: `land` → `reset_fence` (or panel **Reset Fence**) → `takeoff` → `start`. Now also triggers when an **RC-flown** drone is airborne outside the box. `keep_in` configs never latch |
| Gamepad sticks do nothing | in order: `start` not called; drone not in `teleop_drones`; `safe_teleop` log says `REFUSING TO COMMAND` (axis guard — wrong controller profile, [TELEOP.md](TELEOP.md) §3); `/joy` stale (pad asleep/unplugged); container created before the `/dev/input` mount — recreate it |
| `safe_teleop` prints `pad: NO /joy` forever | `joy_node` cannot see the device: `ls /dev/input/js0` on the laptop, then inside the container. Missing in the container ⇒ created before the `/dev/input` bind mount — recreate it (`down` + `up`). Present but unreadable ⇒ add yourself to the `input` group and re-login |
| Yaw turns the wrong way on the first teleop flight | expected risk — sim cannot prove yaw sign (`px4_interface` negates the ENU yaw rate). Land, flip `yaw_sign` in the config's `safe_teleop` block, relaunch ([TELEOP.md](TELEOP.md) §2) |
| Hand-flown drone hovers ~30 cm up on `land` and never touches down | a reference clamped to the teleop-fence floor (`teleop_fence_min` z) — should not happen (only ACTIVE drones are clipped); if it does, `hold` → `land` again → kill if it persists, and note the bag |
| Drone drifts/sinks slowly during hand-flying, or keeps going after release | should be fixed on this branch (separate horizontal/vertical leash, ramp re-attaches to the published command) — if seen, note the bag and check `teleop_lead_m` / `teleop_accel_mps2` ([TELEOP.md](TELEOP.md) §7) |
| `hold` makes the drone continue forward before stopping | by design now — it brakes to a predicted stop point ahead instead of flying back to the call position |
| Startup WARNs about `drone_2`/`drone_3` (only 1 drone); Basestation roster shows two phantom agents with every cell `--` | the config still lists three drones — trim to `drone_1` ([MIGRATION.md](MIGRATION.md) §6) |
| Sim: "Battery unhealthy", won't arm | SITL battery drained — restart the Isaac spawn script |
| Sim: continuous `[timesync]` warnings | Sim below real-time; reduce load |

## Drone-side / network

| Symptom | Cause / fix |
|---|---|
| QGC shows no vehicle | Drone's `gcs_ip` must equal the laptop's *current* hangar-LAN IP. Read back: `ssh root@<DRONE_IP> "grep gcs_ip /etc/modalai/voxl-mavlink-server.conf"` → fix → `systemctl restart voxl-mavlink-server`. Also check laptop `ufw` isn't blocking inbound UDP 14550 |
| After `voxl_setup_real_drone.sh`: QGC "params missing", sensor topics never publish, `px4-listener` empty | the script's PX4 restart wedged the SLPI flight core on this airframe — **reboot the drone** (always reboot after provisioning, never `systemctl restart voxl-px4`) |
| uXRCE client keeps dying / two things restarting it | both `svg-microdds-watchdog` (new script) and our `voxl-dds-retry.service` are active — keep one (`systemctl disable --now` the other), record in CONFIG.md |
| Drone WiFi: `voxl-wifi station` "succeeds" but never connects | Legacy voxl-wifi mangles SSIDs **with spaces**. Spaced SSID → write `wpa_supplicant-mlan0.conf` manually with `wpa_passphrase` (archived MILESTONES M3-A (`git show airstack-starling-max2:docs/MILESTONES.md`)); space-free SSIDs are fine |
| Drone WiFi gone after reboot; dmesg `Firmware Init Failed` / `Card is removed` | WLAN chip wedged — warm reboots don't clear it. **Cold power cycle** (battery + USB out, 10 s) |
| **Older Starling Max 2 only** (USB dongle, `wlan0`): boots on **`169.254.x.x`** instead of its DHCP address | Link-local fallback = never associated, *not* a DHCP fault. `wpa_supplicant` burns its 5 systemd starts in <1 s while `wlan0` doesn't exist until t≈9 s, then quits for good (`Start request repeated too quickly`). Fix = drop-in `/etc/systemd/system/wpa_supplicant.service.d/10-wait-for-wlan0.conf` with `StartLimitIntervalSec=0` + `RestartSec=5`. Recover now: `systemctl reset-failed wpa_supplicant && systemctl start wpa_supplicant` (plain `restart` will NOT work). Full writeup: [CLAUDE.md](../CLAUDE.md) |
| **Older Starling Max 2 only**: no `wlan0` at all, `lsmod` shows `8852bu` with refcount `0` | Kernel-builtin `option` serial driver stole the dongle and made it `/dev/ttyUSB0` (usb_modeswitch poisons `option1/new_id`). Check `readlink /sys/bus/usb/devices/1-1.4:1.0/driver` → must be `rtl8852bu`. Fix = `NoDriverLoading=1` in `/etc/usb_modeswitch.d/0bda:1a2b`. Live: unbind from `option`, bind to `rtl8852bu` — [CLAUDE.md](../CLAUDE.md) |
| Drone pings the router but **not the GCS**, firewall already off | Asymmetric routing, not a firewall. Laptop replies leave via the wrong NIC when the drone is on a different subnet. `sudo ip route add <drone_subnet> via 192.168.9.1 dev <gcs_nic>`; persist with `nmcli ... +ipv4.routes`. Proof trick with no root: `/proc/net/snmp` Icmp `InEchos`/`OutEchoReps` both rise ⇒ packets arrive and are answered — [CLAUDE.md](../CLAUDE.md) |
| Drone `iw` prints usage instead of link info | Old iw needs explicit syntax: `iw dev mlan0 link` |
| Ctrl+C does nothing in `adb shell` | VOXL adbd doesn't forward signals — kill from a second shell (`adb shell pkill <cmd>`) or use self-terminating commands (`ping -c2 -w4`) |
| QGC shows wrong dates on the drone's flight logs | Drone clock unsynced (no NTP). Match logs by **size**; logs at `/data/px4/log/sessNNN/` (ssh — password in CONFIG.md), pull procedure: [RUNBOOK.md](RUNBOOK.md) §D |
