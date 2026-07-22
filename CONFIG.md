# CONFIG — current lab values & what to do when one changes

> **Single source of truth for every value that can drift.** Other docs reference values by
> name; the numbers live HERE. When something changes: update this file, do the "If it
> changes" action, commit.
> Last verified: **2026-07-22**.

## Network (all DHCP until we get static leases — requested from Wayne/Ryzal)

| Value | Current | How to check | Used by | If it changes → do this |
|---|---|---|---|---|
| **Laptop WiFi IP** | `192.168.10.107` | `ip -4 -brief addr` (the `wlp…` row) | Baked into the DRONE's dialer by the setup script | **The critical one.** Re-run on the drone: `voxl_setup_real_drone.sh drone_1 <new IP> 1 8888` |
| Laptop Ethernet IP | `192.168.8.112` | `ip -4 -brief addr` (the `enp…` row) | `clientIP:=` arg of every natnet launch | Just use the new value in the launch command |
| Motive PC IP | `192.168.8.190` | `ipconfig` on the Motive PC | `serverIP:=` arg of every natnet launch; ping test | Use the new value in the launch command |
| Drone WiFi IP | `192.168.10.155` | `adb shell ip -4 addr show mlan0`, or the agent's `session established` log line | Diagnostics only (ping) — the drone dials the laptop, nothing dials the drone | Nothing to reconfigure |

## Lab WiFi

| Value | Current | If it changes → do this |
|---|---|---|
| SSID (drone joins) | `AI.R STC Hangar-5G` | Rewrite the drone's WiFi config — MILESTONES M3-A step 1 (manual `wpa_passphrase` method; do NOT use `voxl-wifi station`, it corrupts spaced SSIDs) |
| Password | (not stored in this repo) | Same as above |
| Drone WiFi interface | `mlan0` (station) / `uap0` (its own hotspot — never connect the laptop to it) | Hardware fact, won't change |

## Protocol constants (change only if deliberately reconfigured everywhere)

| Value | Current | Used by |
|---|---|---|
| uXRCE agent port | `8888` | Setup script arg **and** `MicroXRCEAgent udp4 -p 8888` — must match |
| DDS domain | `1` | Setup script arg; container `.bashrc` pins it; sim uses the same |
| NatNet ports | `1510` (cmd) / `1511` (data) | Motive defaults; per-session check: `ss -ulpn \| grep -E ':(1510\|1511)'` must be clear |

## Mocap / Motive

| Value | Current | If it changes → do this |
|---|---|---|
| Rigid body name | `drone_1` (⏳ not yet created as of 2026-07-22) | Must match everywhere — it names the topics (`/drone_1/pose`, `/drone_1/fmu/*`) and the swarm config. Rename → update Motive AND `swarm_real.yaml` `drone_names`; relaunch natnet (it reads the body list only at startup) |
| Motive frame rate | `50 Hz` | Informational — expected rate for `ros2 topic hz /drone_1/pose` |
| Streaming settings | Up Axis = Z · Broadcast ON · Local Interface = Motive IP | Re-check in Motive's Data Streaming pane whenever poses look wrong — reference photo: `pictures/check_motive_ip_address.jpg` |
| World frame | red = x ("East") · green = y ("North") · z up; origin = floor marker | Photos: `pictures/mocap_axis_1.png`, `pictures/mocap_axis_2.png` — used by the M4 frame hand-check |

## Files & identities

| Value | Current |
|---|---|
| Working folder (laptop) | `~/AirStack-starling-max2/AirStack` |
| Real-run config | `<workspace>/src/svg_ground_control/config/swarm_real.yaml` (⚠️ still 3-drone as shipped — trim to `drone_1` before first flight, MILESTONES M6) |
| Drone identity | `starling2-max (D0012)` · image 1.8.08 · voxl-suite 1.6.4~beta5 |
| Drone factory backup | `/usr/bin/voxl-px4-start.FACTORY-ORIGINAL` (on drone) + `drone-backups/` in this repo (⏳ both pending — take before running the setup script) |

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
