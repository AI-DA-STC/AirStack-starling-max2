# Linear sync record — 2026-11-13

Verified against Linear after all changes.

## Existing issues

| Issue | Title | Status |
| --- | --- | --- |
| NEAR-790 | Hand-fly drone_1 with cuVSLAM running, record and score the flight | In Progress |
| NEAR-816 | Mocap stream end to end: laptop receives it at full rate for 10 min with no stalls, it reaches the drone's PX4, and moving the drone by hand moves the position the same way on every axis | Done |
| NEAR-817 | Record the new Motive version, IP and streaming settings in the lab docs and pictures | Done |
| NEAR-829 | Goal legs on the speed-limited profile | Done |
| NEAR-830 | Measure braking at the fence walls | Done |
| NEAR-951 | Two drones: formation and random goals | In Progress |

Existing titles were not changed.

## New issues

| Issue | Title | Project | Milestone | Status |
| --- | --- | --- | --- | --- |
| NEAR-953 | Two drones: figure-8 with collision avoidance | HTX-R2 Starling Flight Bring-up (M2–M8) | M7 · Multi-drone | In Progress |
| NEAR-954 | Sim: fly with the gamepad (Logitech F310), same pad check and profile as the real drone | HTX-R1 Swarm Sim Validation (Isaac) | None | In Progress |
| NEAR-955 | Isaac Lab: train in parallel with the Starling model and measure steps per second | HTX-R1 Swarm Sim Validation (Isaac) | None | In Progress |

All three are verified unassigned, with no due date. NEAR-953 is related to NEAR-951; NEAR-954 is related to NEAR-922.

### NEAR-953 description

Two real Starlings fly the figure-8 scenario together with the collision filter on. First in the sim, then on the real drones, with a recording and a pass line for minimum separation fixed beforehand.

### NEAR-954 description

The sim teleop is keyboard only. Fly the sim drone with the same pad, pad check and `xbox_usb` profile used on the real drone on 2026-11-13, so the sim and the real drone are flown the same way.

### NEAR-955 description

Find out how many copies of the Starling can be trained at once in Isaac Lab on the lab machine and how many policy steps per second that gives. Start from the Starling numbers already in the repo (mass, inertia, rotor positions, thrust and torque constants, motor time constant).

## Comments

All six comments below were added now; none was already present. Each was verified after posting. Linear renders the NEAR-860 reference in the last comment as an issue link.

### NEAR-816 — added now

2026-11-13. Closed by the owner. Every real flight from 2026-11-11 to 2026-11-13 ran on the stream at 240 Hz: it reached each drone's PX4, and each drone's position matched its own motion (checked from the flight logs on 2026-11-12). The dedicated 10-minute run was not done. On 2026-11-13 the laptop once received no mocap data until the stream was restarted. The cause was not established.

### NEAR-817 — added now

2026-11-13. Closed by the owner. Recorded in the repo: Motive PC 192.168.9.100, Motive 3.5.0.2, NatNet 4.5, broadcast, 240 Hz (docs/CONFIG.md and mocap/motion_capture.yaml). The pictures were not taken.

### NEAR-829 — added now

2026-11-13. Closed by the owner on one measured leg. Real drone, 2026-11-12 (ledger row 35), from the recording: a 0.94 m goal leg at 0.5 m/s. The drone was at speed within 0.5 s, cruised at about 0.5 m/s, braked, overshot the goal by 0.04 m and was settled about 5 s after the goal was sent. Legs at 1.0 m/s and longer legs were not measured.

### NEAR-830 — added now

2026-11-13. Closed by the owner. Measured on the teleop fence, real drone, 2026-11-13 (ledger row 36): three approaches into the wall at up to 0.66 m/s went at most 0.03 m past it. The main fence held the drone at the wall on 2026-11-11 (ledger row 33), but its braking distance was not measured: no recording was made that day.

### NEAR-951 — added now

2026-11-13. Planned for the week of 16 November: two real Starlings fly random goals with the collision filter on, with a recording and a pass line fixed beforehand.

### NEAR-790 — added now

2026-11-13. Planned for the week of 16 November, after NEAR-860.

## HTX-R2 milestone progress

| Milestone | Progress |
| --- | --- |
| R1 · New mocap and network pipeline | 100% |
| M4 · Goal flights with the braking fence | 75% |
| M7 · Multi-drone | 25% |

## Project totals

Counts include archived, non-trashed issues; grouped by exact status name.

| Project | Total | Backlog | In Progress | Done | Canceled |
| --- | ---: | ---: | ---: | ---: | ---: |
| HTX-R1 Swarm Sim Validation (Isaac) | 68 | 51 | 4 | 12 | 1 |
| HTX-R2 Starling Flight Bring-up (M2–M8) | 37 | 18 | 2 | 16 | 1 |
| HTX-R3 Multi-Drone Localisation (VO + UWB) | 17 | 16 | 0 | 1 | 0 |

## Not applied

None. All requested Linear changes were applied and verified. Nothing was deleted.
