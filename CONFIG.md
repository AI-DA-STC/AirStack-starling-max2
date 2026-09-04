# CONFIG — current lab values & what to do when one changes

> **Single source of truth for every value that can drift.** Other docs reference values by
> name; the numbers live HERE. When something changes: update this file, do the "If it
> changes" action, commit.
> Last verified: **2026-09-03** (flight rows) / 2026-08-28 (mocap rows) / 2026-08-11 (drone/WiFi rows).
>
> ⚠️ **2026-08-27 network change:** the lab moved to the **AI.R STC hangar wired LAN**
> (`192.168.9.x`) for mocap — the 08-11 single-WiFi-network topology below is superseded
> for the mocap path. Mocap now runs through `./mocap.sh` on the laptop ([MOCAP.md](MOCAP.md));
> drone/WiFi rows still describe the 08-11 state and need re-verification on the new network.

## Network (all DHCP until we get static leases — requested from Wayne/Ryzal)

| Value | Current | How to check | Used by | If it changes → do this |
|---|---|---|---|---|
| **Laptop IP the drone dials** | on the hangar LAN this is the laptop **Ethernet** IP `192.168.9.107` (08-11 WiFi-era value was `192.168.0.192`) | `ip -4 -brief addr` | Baked into the DRONE's dialer by the setup script | **The critical one.** Re-provision every drone: [RUNBOOK](RUNBOOK.md) §B step 0 (`ssh root@<DRONE_IP>` → `voxl_setup_real_drone.sh <body> <laptop IP> <domain> 8888`) |
| Laptop Ethernet IP | `192.168.9.107` (AI.R STC hangar wired LAN — **back in use since 2026-08-27, this is the mocap path**; laptop WiFi sits on `192.168.10.x`) | `ip -4 -brief addr` (the `enp…` row) | mocap bridge listens here; `clientIP:=` if natnet_ros2 is ever used | Nothing to reconfigure for `./mocap.sh` (it listens on all interfaces); update `clientIP:=` only for natnet_ros2 |
| Motive PC IP | `192.168.9.124` (hangar wired LAN, verified 2026-08-28; was `.9.100` earlier on 08-27 — **the hangar assigns IPs by switch port**, so re-check each session; `192.168.0.190` was the 08-11 WiFi-era value) | `ipconfig` on the Motive PC, or `ping` from laptop | `mocap/motion_capture.yaml` `hostname:`; `serverIP:=` for natnet_ros2 | Update `mocap/motion_capture.yaml` in this repo (and commit); `./mocap.sh check` to confirm packets flow |
| Drone WiFi IP | ⏳ TBD as of 2026-08-11 (old lease `192.168.10.155` is STALE — that was the Hangar network; re-check on `Mocap_QCGroundControl`) | `adb shell ip -4 addr show mlan0` or `voxl-my-ip`, or the agent's `session established` log line | Diagnostics only (ping) — the drone dials the laptop, nothing dials the drone | Nothing to reconfigure |
| **Starling 1 IP (hangar network)** | `192.168.9.10` (2026-08-28) | ping it; or router admin page (row below) | SSH target for re-provisioning ([RUNBOOK](RUNBOOK.md) §B step 0) | IPs are assigned by the router — check the admin page or ask Jeremy Chia |
| Drone SSH login | user `root` · password `oelinux123` (ModalAI factory default — **verified by login 2026-09-01**; the previously-noted `AI.DA@STEngineering` is REJECTED by Starling 1, that credential belongs to something else) (⚠️ lab-LAN device credential stored here deliberately — keep this repo private) | `ssh root@<DRONE_IP>` | RUNBOOK §B step 0 re-provisioning; pulling `.ulg` flight logs from `/data/px4/log/` | Update here if the image/password ever changes |
| Router admin page | `http://192.168.9.1:8080` (hangar router — shows every device's current IP) | open in a browser on the hangar LAN | The authority for ALL drifting IPs; alternatively contact **Jeremy Chia** | — |

## Lab WiFi

| Value | Current | If it changes → do this |
|---|---|---|
| SSID (drone joins) | `motive` (hangar network — observed on Starling 1 via `voxl-wifi getmode` 2026-08-28; previously `Mocap_QCGroundControl` 08-11, `AI.R STC Hangar-5G` before that) | SSID **without** spaces → `voxl-wifi station '<SSID>' '<PASSWORD>'` works (proven 2026-08-11). SSID **with** spaces → manual `wpa_passphrase` method, MILESTONES M3-A step 1 (`voxl-wifi station` corrupts spaced SSIDs) |
| Password | (not stored in this repo) | Same as above |
| Drone WiFi interface | `mlan0` (station) / `uap0` (its own hotspot, SSID `Starling_1_demo_mode` on Starling 1 — never connect the laptop to it) | Hardware fact, won't change |

## Protocol constants (change only if deliberately reconfigured everywhere)

| Value | Current | Used by |
|---|---|---|
| uXRCE agent port | `8888` | Setup script arg **and** `MicroXRCEAgent udp4 -p 8888` — must match |
| DDS domain | `1` (= drone_1) | Setup script arg; container `.bashrc` pins it; sim uses the same. Each ADDITIONAL drone must get a UNIQUE domain ID and its own subnet IP when provisioned |
| NatNet ports | `1510` (cmd) / `1511` (data) | Motive defaults; per-session check: `ss -ulpn \| grep -E ':(1510\|1511)'` must be clear |

## Mocap / Motive

| Value | Current | If it changes → do this |
|---|---|---|
| Rigid body name | `drone_1` (✅ exists — streaming confirmed 2026-08-27, alongside `cf1`/`cf8`) | Must match everywhere — it names the topics (`/drone_1/pose`, `/drone_1/fmu/*`), `MOCAP_BODIES` for `./mocap.sh`, and the swarm config. Rename → update Motive AND `swarm_real.yaml` `drone_names`; restart the bridge (body list read only at startup) |
| Motive frame rate | `50 Hz` (2026-08-28; briefly 240 Hz on 08-27 after a profile edit — it drifts with profile changes) | Informational — expected rate for `ros2 topic hz /drone_1/pose` |
| Streaming settings | Up Axis = Z · Local Interface = Motive IP · **transmission is effectively BROADCAST** (`BroadcastInsteadOfMulticast="true"` in the Motive profile overrides the GUI's "Multicast" — discovered 2026-08-27) | This is WHY natnet_ros2 gets no data and `./mocap.sh` is the receiver — full story [MOCAP.md](MOCAP.md) §3. Re-check the pane whenever poses look wrong: `pictures/check_motive_ip_address.jpg` |
| Pose receiver | `./mocap.sh` on the laptop ([MOCAP.md](MOCAP.md)) — NOT natnet_ros2 in the container | Diagnose with `./mocap.sh check` (6-second wire test with plain-English verdict) |
| World frame | red = x ("East") · green = y ("North") · z up; origin = floor marker | Photos: `pictures/mocap_axis_1.png`, `pictures/mocap_axis_2.png` — used by the M4 frame hand-check |

## PX4 / EKF2 parameters (set once via QGC — since 2026-09-01 QGC runs on the LAPTOP; it ran on the Mocap PC before that)

Confirmed parameter set — applied in the 2026-07-29 QGC session, recorded here 2026-08-11.

| Value | Current | Why / If it changes → do this |
|---|---|---|
| `EKF2_EV_CTRL` | `11` | Always for mocap flight — horiz pos + vert pos + yaw; 3D-velocity bit OFF |
| `EKF2_GPS_CTRL` | `0` | Always for mocap flight |
| `SYS_HAS_MAG` | `0` | Always for mocap flight |
| `EKF2_HGT_REF` | `3` | Always for mocap flight |
| `EKF2_BARO_CTRL` | `0` | Indoor mocap only |
| `EKF2_MAG_TYPE` | `None` | Indoor mocap only |
| `EKF2_EV_DELAY` | `50 ms` (✅ applied — in the .params export 2026-09-04; was 0.0) | Mocap-over-network latency compensation |

> ⚠️ **Outdoor revert:** re-enable `EKF2_BARO_CTRL` and `EKF2_MAG_TYPE` (and GPS/mag params) before any outdoor/GPS flight.

**📦 The canonical full parameter set lives in this repo: [`starling_1_indoor_params.params`](starling_1_indoor_params.params)**
(872-param QGC export from Starling 1, PX4 v1.14, 2026-09-04 — includes every row in the tables above and below).
To set up a drone: QGC → Vehicle Setup → Parameters → **Tools ⋮ → Load from file** → this file
→ reboot PX4 → spot-check `EKF2_EV_CTRL=11` and `RC_MAP_KILL_SW=8` by read-back. Procedure: MILESTONES M4-A.

Flight-log-verified additions (2026-09-01/03 sessions):

| Value | Current | Why / If it changes → do this |
|---|---|---|
| `RC_MAP_KILL_SW` | `8` | Kill switch on ch8 — mapped + verified 2026-09-01. NEVER fly without it |
| `COM_RC_OVERRIDE` | `1` | Stick override for auto modes only — sticks do NOT kick offboard out (takeover = flip to MANUAL, see RUNBOOK §C) |
| `COM_OBL_RC_ACT` | `1` | Offboard-loss → Position mode when RC present |
| `MPC_THR_HOVER` | `0.165` (✅ retuned 2026-09-04 — was factory 0.13; true hover measured 0.165–0.17 from flight logs) | Improves takeoff crispness + landing detection |

## Ground-side flight parameters (svg_ground_control config yamls — lab-validated values)

| Value | Current | Why / If it changes → do this |
|---|---|---|
| `land_speed_mps` | **`0.6`** in goal_single/goal_tracking (**validated 2026-09-03**) | The shipped `0.3` caused **armed-on-ground landings**: slow touchdown bounces past PX4's land-detector window, auto-disarm never fires. 0.6 plants the gear firmly. If landings ever stay armed again → RC arm-switch down + see MILESTONES backlog (LANDED_SETTLE fix) |
| `hover_positions` z | `0.5` m in the goal configs AND drone_1's `swarm_real.yaml` slot (drone_2/3 slots stay 1.2) — low-and-safe test height | Takeoff target AND initial goal. Raise toward 1.0–1.2 m if station-keeping wobbles in ground effect |
| `fence` in `goal_single.yaml` | tight **±0.7 m in X/Y** (ceiling 2.8 m) — deliberate safe default | Widen to your arena before bigger goal flights (`goal_tracking.yaml` uses ±2 m XY / 0–2 m Z) — floats only, inside the net |
| After every landing | confirm **DISARMED in QGC** | The commander's "landed, disarmed" log is optimistic; QGC is the only arming truth on this v1.14 drone |

## Drone-side voxl-vision-hub config (`/etc/modalai/voxl-vision-hub.conf` on the drone)

Required values for mocap flight — cross-reference MILESTONES M4-A.

| Value | Required | Why / If it changes → do this |
|---|---|---|
| `"en_vio"` | `false` | EKF2 must use mocap, not VIO. After editing the file: `systemctl restart voxl-vision-hub` |
| `"offboard_mode"` | `"off"` | vision-hub must not inject offboard commands. Same restart after editing |

## Drone-side voxl-mavlink-server config (`/etc/modalai/voxl-mavlink-server.conf`) — QGC link

The drone PUSHES MAVLink to a fixed GCS IP; QGC itself needs no configuration (it listens on
UDP 14550). ✅ Set 2026-08-11 (drone→Mocap PC ping verified 3–7 ms).

| Value | Current | If it changes → do this |
|---|---|---|
| `"primary_static_gcs_ip"` | the **laptop's** hangar-LAN IP, `192.168.9.107` (QGC moved to the laptop for the 09-01→03 flight sessions and connected — ⚠️ value inferred from that, verify by read-back on the drone; history: `192.168.0.190` = Mocap PC 08-11, factory `192.168.8.10`) | Set to the QGC machine's current IP, then `systemctl restart voxl-mavlink-server`; QGC connects within seconds |
| `"primary_static_gcs_ip_port"` | `14550` | QGC's default listen port — leave it |

## Files & identities

| Value | Current |
|---|---|
| Working folder (laptop) | `~/AirStack-starling-max2/AirStack` |
| Real-run config | `<workspace>/src/svg_ground_control/config/swarm_real.yaml` (still 3-drone; trim to `drone_1` is OPTIONAL — deferred 2026-09-03, phantom drone_2/3 WARNs are harmless. Goal flights use `goal_single.yaml`/`goal_tracking.yaml`, already single-drone) |
| Drone identity | `starling2-max (D0012)` · image 1.8.08 · voxl-suite 1.6.4~beta5 |
| Drone factory backup | `/usr/bin/voxl-px4-start.FACTORY-ORIGINAL` (on drone) + `drone-backups/voxl-px4-start.original-D0012` in this repo (✅ both taken 2026-07-22, before the setup script ran) |

## 60-second fixes for the usual suspects

| Symptom | Fix |
|---|---|
| Drone WiFi gone after reboot (`dmesg`: `Firmware Init Failed`) | Cold power cycle: battery + USB out 10 s (warm reboot won't clear a wedged chip) |
| `/fmu/*` topics look dead | Add `--qos-reliability best_effort` to echo/hz; and is the agent running? |
| `/drone_1/pose` missing / 0 Hz | Is `./mocap.sh` running on the laptop? Then `./mocap.sh check` — its verdict names the culprit (Motive not streaming / wrong network / port 1511 squatter). Full table: [MOCAP.md](MOCAP.md) §5 |
| `ros2` empty / service call hangs "waiting" | You're in a laptop shell — `./airstack.sh connect robot --command=bash` first (`root@` prompt) |
| Everything else | Full symptom→fix table: [MILESTONES.md](MILESTONES.md) §7 |

## When static leases arrive (Wayne/Ryzal)

Update the Network table above, re-run the setup script once with the final laptop IP, and
the per-session IP checks in [RUNBOOK.md](RUNBOOK.md) §B step 1 become a formality.
