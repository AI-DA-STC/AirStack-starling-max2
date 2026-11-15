# Linear sync record — 2026-11-11

Verified against live Linear in nearlab after applying the revised instructions. No titles changed. Nothing deleted. All requested changes are applied; nothing remains unapplied. Existing matching comments were not duplicated. Issue references rendered by Linear as rich mentions are shown below as their identifiers.

## Current titles and statuses

| Issue | Exact live title | Status |
|---|---|---|
| NEAR-814 | Network: laptop on the mocap subnet (192.168.9.x) with the route to the drone subnet; drone gets its WiFi address; both ping each other | Done |
| NEAR-815 | Set up the upgraded Motive: calibrate (wand, ground plane, axis convention) and create the Starling rigid body | Done |
| NEAR-816 | Mocap stream end to end: laptop receives it at full rate for 10 min with no stalls, it reaches the drone's PX4, and moving the drone by hand moves the position the same way on every axis | In Progress |
| NEAR-817 | Record the new Motive version, IP and streaming settings in the lab docs and pictures | In Progress |
| NEAR-818 | Re-run the drone setup script, then reboot the drone (never restart the flight software service) | Done |
| NEAR-819 | Confirm the drone ID matches the controller's target | Done |
| NEAR-820 | Confirm only one connection watchdog runs on the drone | Backlog |
| NEAR-821 | Check the controller's messages match the drone's PX4 version | Backlog |
| NEAR-822 | Hand-carry with props off: panel tracks the drone, estimator fuses mocap | Done |
| NEAR-823 | Props-off kill switch test | Done |
| NEAR-824 | Preflight card dry run with the new software | Backlog |
| NEAR-825 | First flight: takeoff, hover, land | Done |
| NEAR-826 | Landing test: settle on the ground, then disarm | Backlog |
| NEAR-829 | Goal legs on the speed-limited profile | In Progress |
| NEAR-830 | Measure braking at the fence walls | In Progress |

## Requested comments

### NEAR-814 — already present

Real drone, 2026-11-11. Laptop on the cable at 192.168.9.107, drone on WiFi at 10.40.2.10. Two things had to be fixed first. The laptop needed the route `10.40.2.0/23 via 192.168.9.1`, because its WiFi was on the office network. The laptop firewall blocked the drone's connection on UDP 8888 until a rule allowed 10.40.2.0/23. After that both sides ping each other and the drone link came up. The drone dials the laptop's cable address, not its WiFi address.

### NEAR-815 — already present

Real drone, 2026-11-11. Motive 3.5.0.2 (NatNet 4.5) at 192.168.9.100, with a rigid body named drone_1. The owner recalibrated Motive during the session (owner's report). The axis check is recorded on NEAR-822.

### NEAR-818 — already present

Real drone, 2026-11-11. `voxl_setup_real_drone.sh drone_1 192.168.9.107 1 8888` ran on the drone, then the drone was rebooted (owner's report). The drone link connected afterwards.

### NEAR-822 — already present

Real drone, 2026-11-11. The owner carried the drone by hand with props off and checked the axes and the Foxglove view (owner's report). No numbers were recorded.

### NEAR-823 — already present

Real drone, 2026-11-11. Done with props off before the flight (owner's report). Earlier in the session the drone refused to arm with a kill-switch message while the switch was off. A drone reboot and a Motive recalibration cleared it (owner's report). The cause was not found.

### NEAR-825 — already present

Real drone, 2026-11-11, 16:57:33 to 16:59:54 (+08). First flight on this software. Config `swarm_real_ours.yaml`, scenario hover, one drone, mocap. Takeoff to (−0.5, 0, 0.5) m, "holding takeoff position" after 7 s, about 2 min 20 s in the air, then land. The commander logged touchdown and its disarm. QGroundControl showed DISARMED after landing (owner's report). No video. Two more short hover flights followed at 17:08 and 17:09, each ending in a landing and a logged disarm. Not done in any of them: the RC takeover to MANUAL and the `land` reset that this issue also asks for. The software saw no command acknowledgement from PX4 at any point (see NEAR-821). Logs: `~/flight_logs/2026-11-11/` on the lab laptop.

### NEAR-819 — already present

Real drone, 2026-11-11. Read back on the drone: `px4-param show MAV_SYS_ID` gives 1. The interface runs with target_system=1. They match, and the drone armed, flew and disarmed on those commands.

### NEAR-816 — already present

Real drone, 2026-11-11. The laptop receives the stream and forwards it to the drone's PX4 input topic. The hand check of the axes is done (owner's report). Not done: the 10-minute run with no stalls. Open point: Motive streamed at 50 Hz at the start of the session and at 240 Hz later. The flights in September used 50 Hz. The rate for flying is not decided.

### NEAR-817 — already present

2026-11-11. Recorded in the repo: Motive PC 192.168.9.100, Motive 3.5.0.2, NatNet 4.5, broadcast (docs/CONFIG.md and mocap/motion_capture.yaml, change CHG-0056). Not done: the streaming rate (see NEAR-816), the firewall and route steps, and the pictures.

### NEAR-820 — already present

2026-11-11. Not checked. The setup script installed and started `svg-microdds-watchdog` today. Whether the older `voxl-dds-retry` service is also running on this drone was not looked at.

### NEAR-821 — already present

2026-11-11. Finding: this drone does not publish the command-acknowledgement topic (`fmu/out/vehicle_command_ack` is absent from its topic list). The interface therefore logged no acknowledgement for any arm, takeoff or disarm command, on refused attempts and on the successful flight alike. The rule "no acknowledgement means the drone id is wrong" cannot be used on this drone.

### NEAR-826 — already present

Real drone, 2026-11-11. Not run as a test. For the record: all four flights today landed with `land_settle_s` 0.0, and each time the commander logged touchdown and "landed, disarmed (attempt 1)". QGroundControl showed DISARMED after the first landing (owner's report). The other three were not checked in QGroundControl, and the 2.0 s setting was not tried.

### NEAR-829 — already present

Real drone, 2026-11-11, 17:13:21 to 17:14:29 (+08). First goal flight on this software. Config `goal_single_ours.yaml`: speed 1.0 m/s, acceleration 3.0 m/s², fence `keep_in` ±2 m. After takeoff and Start, three goals were sent from the Foxglove panel at 0.5 m height: x = 1.00, then x = −1.00, then x = 2.00. The drone flew each one (owner's report; the commander logged each goal). No position recording was made, so the shape of the speed profile is not measured yet. That is why this stays In Progress. An earlier goal sent during a hover flight was ignored: the commander takes goals only in the goal scenario, and the panel does not warn about it.

### NEAR-830 — added now

Real drone, 2026-11-11, two goal flights with `goal_single_ours.yaml` (fence `keep_in`, x max 2.0 m, no margin, 1.0 m/s, brake 4.0 m/s²).

Flight 1, 17:14: one goal at x = 2.00, on the wall. The commander logged "drone_1 outside the fence (x>max), keep_in pushing it back" once.

Flight 2, 17:31:43 to 17:34:14: goals sent beyond the wall on purpose, at x = 2.10, 2.20, 2.40 and 2.50, with returns to x = 1.00 and 0.00 in between. Each time the fence limited the drone on x (85 "fence keep-in: drone_1 limited on x" lines, braking up to 4.0 m/s²) and the drone held at the wall instead of flying on to the goal. The owner watched it and reports that the geofence works.

Still open: the braking distance itself. The "outside the fence" message appeared 21 times in flight 2. It prints whenever the position is past x = 2.0 m by any amount, so the drone sat on the wall and crossed it slightly, again and again. No recording was running in either flight, so how far it went past the wall is not measured. Only the +x wall was tried.

The earlier NEAR-830 observation comment remains in Linear, unchanged. NEAR-830 was changed from Backlog to In Progress in this sync. Every other requested status was already in place. NEAR-824 was inspected for this record; no change was requested or made.

## Current milestone progress

Progress is Linear's displayed progress, not a percentage calculated from completed issue count. Counts below include archived issues.

| Milestone in HTX-R2 | Displayed progress | Total | Backlog | In Progress | Done | Canceled |
|---|---:|---:|---:|---:|---:|---:|
| R1 · New mocap and network pipeline | 63% | 4 | 0 | 2 | 2 | 0 |
| M2 · Drone setup and hand-carry, propellers off | 57% | 8 | 3 | 0 | 4 | 1 |
| M3 · First flight on the new software | 20% | 5 | 4 | 0 | 1 | 0 |
| M4 · Goal flights with the braking fence | 13% | 4 | 2 | 2 | 0 | 0 |

## Current project totals

All issues, including archived issues; trashed issues excluded.

| Project | Total | Backlog | In Progress | Done | Canceled |
|---|---:|---:|---:|---:|---:|
| HTX-R1 Swarm Sim Validation (Isaac) | 66 | 52 | 1 | 12 | 1 |
| HTX-R2 Starling Flight Bring-up (M2–M8) | 35 | 23 | 4 | 7 | 1 |
| HTX-R3 Multi-Drone Localisation (VO + UWB) | 17 | 16 | 0 | 1 | 0 |
