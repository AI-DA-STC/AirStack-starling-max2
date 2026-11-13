# Linear update — 2026-11-13, close four issues and open the work for the week of 16 November

Instructions for the Linear agent, in the **nearlab** workspace. Apply every step below. Delete nothing. Use the comments and titles exactly as written. Change no existing title. Check Linear before each step: if a status, comment or issue is already in place, do not repeat it. Every new issue is unassigned with no due date.

Evidence for the closures is in the repo https://github.com/AI-DA-STC/AirStack-starling-max2 (`docs/record/LEDGER.md`, ledger rows 33, 35, 36 and 37) and in the laptop folders `~/flight_logs/2026-11-12/` and `~/flight_logs/2026-11-13/`.

## Part 1 · Set to Done, each with its comment (project HTX-R2)

The owner closes these four on 2026-11-13. Each comment says what was done and what was not.

**NEAR-816 "Mocap stream end to end: laptop receives it at full rate for 10 min with no stalls, it reaches the drone’s PX4, and moving the drone by hand moves the position the same way on every axis"**

> 2026-11-13. Closed by the owner. Every real flight from 2026-11-11 to 2026-11-13 ran on the stream at 240 Hz: it reached each drone's PX4, and each drone's position matched its own motion (checked from the flight logs on 2026-11-12). The dedicated 10-minute run was not done. On 2026-11-13 the laptop once received no mocap data until the stream was restarted. The cause was not established.

**NEAR-817 "Record the new Motive version, IP and streaming settings in the lab docs and pictures"**

> 2026-11-13. Closed by the owner. Recorded in the repo: Motive PC 192.168.9.100, Motive 3.5.0.2, NatNet 4.5, broadcast, 240 Hz (docs/CONFIG.md and mocap/motion_capture.yaml). The pictures were not taken.

**NEAR-829 "Goal legs on the speed-limited profile"**

> 2026-11-13. Closed by the owner on one measured leg. Real drone, 2026-11-12 (ledger row 35), from the recording: a 0.94 m goal leg at 0.5 m/s. The drone was at speed within 0.5 s, cruised at about 0.5 m/s, braked, overshot the goal by 0.04 m and was settled about 5 s after the goal was sent. Legs at 1.0 m/s and longer legs were not measured.

**NEAR-830 "Measure braking at the fence walls"**

> 2026-11-13. Closed by the owner. Measured on the teleop fence, real drone, 2026-11-13 (ledger row 36): three approaches into the wall at up to 0.66 m/s went at most 0.03 m past it. The main fence held the drone at the wall on 2026-11-11 (ledger row 33), but its braking distance was not measured: no recording was made that day.

## Part 2 · Set to In Progress, each with its comment

**NEAR-951 "Two drones: formation and random goals"** (HTX-R2, M7)

> 2026-11-13. Planned for the week of 16 November: two real Starlings fly random goals with the collision filter on, with a recording and a pass line fixed beforehand.

**NEAR-790 "Hand-fly drone_1 with cuVSLAM running, record and score the flight"** (HTX-R1)

> 2026-11-13. Planned for the week of 16 November, after NEAR-860.

## Part 3 · Create three issues, status In Progress

**"Two drones: figure-8 with collision avoidance"** — project HTX-R2, milestone **M7 · Multi-drone**. Relate it to NEAR-951.

> Two real Starlings fly the figure-8 scenario together with the collision filter on. First in the sim, then on the real drones, with a recording and a pass line for minimum separation fixed beforehand.

**"Sim: fly with the gamepad (Logitech F310), same pad check and profile as the real drone"** — project HTX-R1, no milestone. Relate it to NEAR-922.

> The sim teleop is keyboard only. Fly the sim drone with the same pad, pad check and `xbox_usb` profile used on the real drone on 2026-11-13, so the sim and the real drone are flown the same way.

**"Isaac Lab: train in parallel with the Starling model and measure steps per second"** — project HTX-R1, no milestone.

> Find out how many copies of the Starling can be trained at once in Isaac Lab on the lab machine and how many policy steps per second that gives. Start from the Starling numbers already in the repo (mass, inertia, rotor positions, thrust and torque constants, motor time constant).

## Part 4 · Write the sync record

Write a Markdown file named `2026-11-13-linear-synced-3.md`. State only what Linear now holds:

- the title and status of NEAR-790, NEAR-816, NEAR-817, NEAR-829, NEAR-830 and NEAR-951;
- the NEAR id, title, project, milestone and status of each of the three new issues;
- each comment added here, and whether it was added now or already present;
- the progress of milestones R1, M4 and M7 of HTX-R2;
- anything not applied, and why;
- the totals per project for **all three** projects (HTX-R1, HTX-R2 and HTX-R3): total, Backlog, In Progress, Done, Canceled.
