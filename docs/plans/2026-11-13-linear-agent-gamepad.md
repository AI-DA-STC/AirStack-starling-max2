# Linear update — 2026-11-13, first real gamepad flight

Instructions for the Linear agent, in the **nearlab** workspace, project **HTX-R2 Starling Flight Bring-up (M2–M8)**. Apply every step below. Delete nothing. Use the comments exactly as written. Change no title. Check Linear before each step: if a status or comment is already in place, do not repeat it. No issue is created.

Everything below is the **real drone** (one Starling, `drone_2`, motion-capture positioning (mocap), AI.R STC hangar), on 2026-11-13. Times are +08.

Evidence lives in the repo https://github.com/AI-DA-STC/AirStack-starling-max2 (ledger row #36 in `docs/record/LEDGER.md`, videos `videos/xbox_teleop_real_1080p.mp4` (hangar camera) and `videos/xbox_teleop_ui.mp4` (Foxglove panel), both of the last 30 s of the flight) and in the laptop folder `~/flight_logs/2026-11-13/`.

## Part 1 · Set to Done, with its comment

**NEAR-833 "Check the yaw stick turns the drone the right way, slowly and low"**

> Real drone, 2026-11-13, flight 16:40:36 to 16:43:13 (ledger row #36). One Starling (`drone_2`), Logitech F310 pad, `tools/real.sh teleop drone_2`. The pass line was fixed before the flight.
> The measured heading followed the commanded heading both ways, within 3°: from −12° to −17° (right), to +11° (left), a 47° right turn to −44° in about one second, then back to 0°. Height 0.5 to 0.6 m.
> During the large turn the drone moved at most 0.05 m (pass line: under 0.3 m).
> That the drone turned the way the stick was pushed is the owner's report. It is not on video, and the stick itself was not recorded. The issue is closed on that report.
> No rosbag was recorded. The numbers come from the drone's own PX4 log at 10 Hz.

## Part 2 · Set to In Progress, each with its comment

**NEAR-834 "Gamepad fence test"**

> Real drone, 2026-11-13, ledger row #36. The pass line was fixed before the flight.
> Three approaches into the −y wall (at −1.5 m), at 0.44, 0.56 and 0.66 m/s. Furthest past the wall: 0.03 m (pass line: no more than 0.10 m). The commander logged "teleop fence keep-in: drone_2 limited on y" each time.
> Still to fly: the +x wall and the top at 1.8 m. The highest point flown was 0.99 m.
> No rosbag was recorded. The numbers come from the drone's own PX4 log at 10 Hz.

**NEAR-835 "Release-to-hold test and coast distance"**

> Real drone, 2026-11-13, ledger row #36. The pass line was fixed before the flight.
> Four releases from about 0.5 m/s, away from the walls: coast 0.05 to 0.28 m, stopped 0.9 to 1.6 s after release, then within 0.05 to 0.15 m for 5 s (pass line: stopped within 0.5 m and 2 s, then within 0.2 m for 5 s).
> From about 0.25 m/s: coast 0.01 to 0.15 m.
> Still to fly: unplugging the pad in flight (pass line: stop within 0.75 m).
> No rosbag was recorded. The numbers come from the drone's own PX4 log at 10 Hz.

## Part 3 · Comment only, status unchanged

None this time.

## Part 4 · Findings for the owner to turn into issues

Do NOT create issues for these. List these in the sync record under "proposed, not created", one line each. None is fixed. The owner decides.

1. The commander gives no warning when no pad is sending commands. It holds position as if the sticks were centred (first attempt, 16:34:59). Check before takeoff: `ros2 topic hz /svg/drone_2/teleop_command` must show about 20 Hz.
2. The drone overshoots the commanded speed: peak horizontal speed 0.66 m/s against the 0.5 m/s stick cap.

## Part 5 · Write the sync record

Write a Markdown file named `2026-11-13-linear-synced.md`. State only what Linear now holds:

- the title and status of NEAR-833, NEAR-834 and NEAR-835;
- each comment added here, and whether it was added now or already present;
- the progress of milestone M5;
- the list from Part 4, marked "proposed, not created";
- anything not applied, and why;
- the totals per project for **all three** projects (HTX-R1, HTX-R2 and HTX-R3): total, Backlog, In Progress, Done, Canceled.
