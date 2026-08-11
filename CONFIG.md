# CONFIG — current lab values & what to do when one changes

> **Single source of truth for every value that can drift.** Other docs reference values by
> name; the numbers live HERE. When something changes: update this file, do the "If it
> changes" action, commit.
> Last verified: **2026-08-11**.

## Network (all DHCP until we get static leases — requested from Wayne/Ryzal)

| Value | Current | How to check | Used by | If it changes → do this |
|---|---|---|---|---|
| **Laptop WiFi IP** | `192.168.0.192` (on `Mocap_QCGroundControl`, verified 2026-08-11; drone re-provisioned to it same day) | `ip -4 -brief addr` (the `wlp…` row) | Baked into the DRONE's dialer by the setup script | **The critical one.** Re-run on the drone: `voxl_setup_real_drone.sh drone_1 <new IP> 1 8888` |
| Laptop Ethernet IP | not in use since 2026-08-11 (single-network topology; NatNet arrives over WiFi). Fallback if poses stutter: wire laptop to the router's LAN port and use that IP as `clientIP:=` | `ip -4 -brief addr` (the `enp…` row) | — | — |
| Motive PC IP | `192.168.0.190` (on `Mocap_QCGroundControl` since 2026-08-11; was `192.168.8.190` on the old Ethernet LAN) | `ipconfig` on the Motive PC | `serverIP:=` arg of every natnet launch; ping test; QGC runs on this PC | Use the new value in the launch command; update Motive's Data Streaming → Local Interface |
| Drone WiFi IP | ⏳ TBD as of 2026-08-11 (old lease `192.168.10.155` is STALE — that was the Hangar network; re-check on `Mocap_QCGroundControl`) | `adb shell ip -4 addr show mlan0` or `voxl-my-ip`, or the agent's `session established` log line | Diagnostics only (ping) — the drone dials the laptop, nothing dials the drone | Nothing to reconfigure |

## Lab WiFi

| Value | Current | If it changes → do this |
|---|---|---|
| SSID (drone joins) | `Mocap_QCGroundControl` (changed 2026-08-11; previously `AI.R STC Hangar-5G`) | SSID **without** spaces → `voxl-wifi station '<SSID>' '<PASSWORD>'` works (proven 2026-08-11). SSID **with** spaces → manual `wpa_passphrase` method, MILESTONES M3-A step 1 (`voxl-wifi station` corrupts spaced SSIDs) |
| Password | (not stored in this repo) | Same as above |
| Drone WiFi interface | `mlan0` (station) / `uap0` (its own hotspot — never connect the laptop to it) | Hardware fact, won't change |

## Protocol constants (change only if deliberately reconfigured everywhere)

| Value | Current | Used by |
|---|---|---|
| uXRCE agent port | `8888` | Setup script arg **and** `MicroXRCEAgent udp4 -p 8888` — must match |
| DDS domain | `1` (= drone_1) | Setup script arg; container `.bashrc` pins it; sim uses the same. Each ADDITIONAL drone must get a UNIQUE domain ID and its own subnet IP when provisioned |
| NatNet ports | `1510` (cmd) / `1511` (data) | Motive defaults; per-session check: `ss -ulpn \| grep -E ':(1510\|1511)'` must be clear |

## Mocap / Motive

| Value | Current | If it changes → do this |
|---|---|---|
| Rigid body name | `drone_1` (⏳ not yet created as of 2026-07-22) | Must match everywhere — it names the topics (`/drone_1/pose`, `/drone_1/fmu/*`) and the swarm config. Rename → update Motive AND `swarm_real.yaml` `drone_names`; relaunch natnet (it reads the body list only at startup) |
| Motive frame rate | `50 Hz` | Informational — expected rate for `ros2 topic hz /drone_1/pose` |
| Streaming settings | Up Axis = Z · Broadcast ON · Local Interface = Motive IP | Re-check in Motive's Data Streaming pane whenever poses look wrong — reference photo: `pictures/check_motive_ip_address.jpg` |
| World frame | red = x ("East") · green = y ("North") · z up; origin = floor marker | Photos: `pictures/mocap_axis_1.png`, `pictures/mocap_axis_2.png` — used by the M4 frame hand-check |

## PX4 / EKF2 parameters (set once via QGC — QGC runs on the MOCAP PC)

Confirmed parameter set — applied in the 2026-07-29 QGC session, recorded here 2026-08-11.

| Value | Current | Why / If it changes → do this |
|---|---|---|
| `EKF2_EV_CTRL` | `11` | Always for mocap flight — horiz pos + vert pos + yaw; 3D-velocity bit OFF |
| `EKF2_GPS_CTRL` | `0` | Always for mocap flight |
| `SYS_HAS_MAG` | `0` | Always for mocap flight |
| `EKF2_HGT_REF` | `3` | Always for mocap flight |
| `EKF2_BARO_CTRL` | `0` | Indoor mocap only |
| `EKF2_MAG_TYPE` | `None` | Indoor mocap only |
| `EKF2_EV_DELAY` | `0.0 ms` | Tune ≈50 ms later if fusion lags |

> ⚠️ **Outdoor revert:** re-enable `EKF2_BARO_CTRL` and `EKF2_MAG_TYPE` (and GPS/mag params) before any outdoor/GPS flight.

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
| `"primary_static_gcs_ip"` | `192.168.0.190` (the Mocap PC; factory default was `192.168.8.10` = hotspot lease) | Set to the Mocap PC's current IP, then `systemctl restart voxl-mavlink-server`; QGC connects within seconds |
| `"primary_static_gcs_ip_port"` | `14550` | QGC's default listen port — leave it |

## Files & identities

| Value | Current |
|---|---|
| Working folder (laptop) | `~/AirStack-starling-max2/AirStack` |
| Real-run config | `<workspace>/src/svg_ground_control/config/swarm_real.yaml` (⚠️ still 3-drone as shipped — trim to `drone_1` before first flight, MILESTONES M6) |
| Drone identity | `starling2-max (D0012)` · image 1.8.08 · voxl-suite 1.6.4~beta5 |
| Drone factory backup | `/usr/bin/voxl-px4-start.FACTORY-ORIGINAL` (on drone) + `drone-backups/voxl-px4-start.original-D0012` in this repo (✅ both taken 2026-07-22, before the setup script ran) |

## 60-second fixes for the usual suspects

| Symptom | Fix |
|---|---|
| Drone WiFi gone after reboot (`dmesg`: `Firmware Init Failed`) | Cold power cycle: battery + USB out 10 s (warm reboot won't clear a wedged chip) |
| `/fmu/*` topics look dead | Add `--qos-reliability best_effort` to echo/hz; and is the agent running? |
| `/drone_1/pose` missing / 0 Hz | Motive streaming? body named `drone_1`? port 1511 squatter? wrong `clientIP` (must be the Ethernet IP)? |
| `ros2` empty / service call hangs "waiting" | You're in a laptop shell — `./airstack.sh connect robot --command=bash` first (`root@` prompt) |
| Everything else | Full symptom→fix table: [MILESTONES.md](MILESTONES.md) §7 |

## When static leases arrive (Wayne/Ryzal)

Update the Network table above, re-run the setup script once with the final laptop IP, and
the per-session IP checks in [RUNBOOK.md](RUNBOOK.md) §B step 1 become a formality.
