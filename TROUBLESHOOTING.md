# TROUBLESHOOTING — something misbehaves, find your symptom

> Unified symptom index for the whole rig (merged from the per-doc tables, 2026-09-07).
> Safety first: if the drone is AIRBORNE and misbehaving →
> [PREFLIGHT.md](PREFLIGHT.md) emergencies table FIRST, debug after.

*(Unfamiliar term? → [GLOSSARY.md](GLOSSARY.md))*

## Bring-up / ground software

| Symptom | Cause / fix |
|---|---|
| `ros2` not found / empty topics / service call hangs "waiting" | Wrong shell — you're on the laptop host. `./airstack.sh connect robot --command=bash` first (`root@` prompt) |
| `bws: command not found` | Wrong container (Isaac) or host shell |
| `omni_pass.env not found` on `up` | Re-run `./airstack.sh setup` to (re)generate it (press Enter at the API Token prompt) |
| "mounting … user.config.json … not a directory" | A failed `up` created a directory; `rmdir` it, then re-run `./airstack.sh setup` |
| `/fmu/*` topics look dead | `echo` needs `--qos-reliability best_effort` (`hz` takes no QoS flag here); and is the uXRCE agent running? |
| No odometry reaching the commander / RViz shows no drone marker | Per-drone interfaces not running — [RUNBOOK.md](RUNBOOK.md) §B step 5 (`real_interfaces.launch.py drones:=drone_1`) must be up |
| RViz empty + "Global Status: Error" on the real rig | `svg_drones.rviz` ships with Fixed Frame `map` (sim default) — set it to `world` |
| Weird/fake odometry on real topics | A `test/functional_*.py` is running — they publish fake odometry on the real topic names. **Never run them with the real stack up.** Kill it, restart the stack |
| A tool you `apt install`ed in the container is gone | Container apt installs (e.g. `apt install -y ros-jazzy-plotjuggler-ros`) **vanish on `airstack.sh down`/`up`** — that builds a fresh container — but survive a `restart`. Re-install it, or add it to the image if you need it every session |
| Commander dies: "Logger severity cannot be changed" | CMU bug — apply patch 0002 (`patches/`), rebuild `svg_ground_control` |

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
| Takeoff refused: "no drone eligible (missing odometry or not IDLE)" | In order: **1.** commander stuck non-IDLE after an RC takeover / Ctrl-C → call `land` once (drone on floor); **2.** interfaces not running — RUNBOOK §B step 5; **3.** mocap bridge down → `./mocap.sh check` |
| Landed but QGC still shows ARMED | Flip KILL (ch8 — harmless on the ground) or arm switch (ch5) down. History: the `land_speed_mps=0.3` era symptom — retuned to `0.6` ([CONFIG.md](CONFIG.md)); investigate if it recurs |
| QGC red "Disarming denied, not landed" once per landing | Cosmetic — the commander's premature one-shot disarm (fires ~15 cm up, always denied). PX4's auto-disarm does the real work ([MILESTONES.md](MILESTONES.md) §8 Fix 1 if it ever stops sufficing) |
| RC sticks ignored / fighting in Position/Altitude mode | Control-authority leak: PX4 v1.14 still consumes commander setpoints in those modes. Take over into **MANUAL** (or kill) only |
| Geofence breach → everything frozen mid-air | By design: freeze-hover, **still armed**, not a motor cut. Recover: `land` → `reset_fence` → `takeoff` → `start` |
| Teleop publishes but drone doesn't move | Commander holding — call `start`; click the teleop terminal for keyboard focus |
| Startup WARNs about `drone_2`/`drone_3` (only 1 drone) | Phantom drones from the un-trimmed 3-drone `swarm_real.yaml` — expected and harmless (trim deferred 2026-09-03, MILESTONES M6) |
| Sim: "Battery unhealthy", won't arm | SITL battery drained — restart the Isaac spawn script |
| Sim: continuous `[timesync]` warnings | Sim below real-time; reduce load |

## Drone-side / network

| Symptom | Cause / fix |
|---|---|
| QGC shows no vehicle | Drone's `gcs_ip` must equal the laptop's *current* hangar-LAN IP. Read back: `ssh root@<DRONE_IP> "grep gcs_ip /etc/modalai/voxl-mavlink-server.conf"` → fix → `systemctl restart voxl-mavlink-server`. Also check laptop `ufw` isn't blocking inbound UDP 14550 |
| Drone WiFi: `voxl-wifi station` "succeeds" but never connects | Legacy voxl-wifi mangles SSIDs **with spaces**. Spaced SSID → write `wpa_supplicant-mlan0.conf` manually with `wpa_passphrase` (MILESTONES M3-A); space-free SSIDs are fine |
| Drone WiFi gone after reboot; dmesg `Firmware Init Failed` / `Card is removed` | WLAN chip wedged — warm reboots don't clear it. **Cold power cycle** (battery + USB out, 10 s) |
| Drone `iw` prints usage instead of link info | Old iw needs explicit syntax: `iw dev mlan0 link` |
| Ctrl+C does nothing in `adb shell` | VOXL adbd doesn't forward signals — kill from a second shell (`adb shell pkill <cmd>`) or use self-terminating commands (`ping -c2 -w4`) |
| QGC shows wrong dates on the drone's flight logs | Drone clock unsynced (no NTP). Match logs by **size**; logs at `/data/px4/log/sessNNN/` (ssh — password in CONFIG.md), pull procedure: [RUNBOOK.md](RUNBOOK.md) §D |
