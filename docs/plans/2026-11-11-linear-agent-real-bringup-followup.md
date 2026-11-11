# Linear follow-up — 2026-11-11, mocap rate decided, fence videos, ledger row

Instructions for the Linear agent, in the **nearlab** workspace, project **HTX-R2 Starling Flight Bring-up (M2–M8)**. They follow `2026-11-11-linear-agent-real-bringup.md`, which is already applied. Add the three comments below exactly as written. Change no status and no title. Delete nothing. If a comment is already present, do not add it again.

Everything below is the real drone (Starling 2 Max D0012, motion-capture positioning (mocap)), 2026-11-11. Evidence lives in the repo https://github.com/AI-DA-STC/AirStack-starling-max2.

## Part 1 · Comments

**NEAR-816 "Mocap stream end to end: laptop receives it at full rate for 10 min with no stalls, it reaches the drone’s PX4, and moving the drone by hand moves the position the same way on every axis"**

> 2026-11-11. The rate is decided: Motive stays at 240 Hz for the Starling (owner). The repo records it (docs/CONFIG.md, mocap/motion_capture.yaml, change CHG-0057). Today's flights ran at 240 Hz as measured on the laptop before the first flight. Still not done: the 10-minute run with no stalls, now to be done at 240 Hz.

**NEAR-825 "First flight: takeoff, hover, land"**

> 2026-11-11. The flights of this day are now ledger row #33 in the repo, the first REAL row on this software (docs/record/LEDGER.md).

**NEAR-830 "Measure braking at the fence walls"**

> 2026-11-11. Two videos of the fence test flight (17:31:43 to 17:34:14) are in the repo: the hangar camera (`videos/geofence_test_real_1080p.mp4`, 3 min) and the Foxglove panel (`videos/geofence_test_ui.mp4`, 28 s). They show the drone holding at the wall. They do not give the braking distance, which still needs a position recording.

## Part 2 · Write the sync record

Write a Markdown file named `2026-11-11-linear-synced-2.md`. State only what Linear now holds:

- the title and status of NEAR-816, NEAR-825 and NEAR-830;
- each comment added here, and whether it was added now or already present;
- anything not applied, and why;
- the totals per project for **all three** projects (HTX-R1, HTX-R2 and HTX-R3): total, Backlog, In Progress, Done, Canceled.
