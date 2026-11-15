# Linear update — 2026-11-13, first real gamepad flight and two-drone gamepad flight

Instructions for the Linear agent, in the **nearlab** workspace, project **HTX-R2 Starling Flight Bring-up (M2–M8)**. Apply every step below. Delete nothing. Use the comments exactly as written. Change no title. Check Linear before each step: if a status or comment is already in place, do not repeat it. No issue is created.

Everything below is **real drones** (motion-capture positioning (mocap), AI.R STC hangar), on 2026-11-13, in two flights: the first gamepad flight (one Starling, `drone_2`) and the two-drone gamepad flight (`drone_2` hand-flown at the hovering `drone_1`, the older Starling). Times are +08.

Evidence lives in the repo https://github.com/AI-DA-STC/AirStack-starling-max2 (ledger rows #36 and #37 in `docs/record/LEDGER.md`; for #36 the videos `videos/xbox_teleop_real_1080p.mp4` (hangar camera) and `videos/xbox_teleop_ui.mp4` (Foxglove panel), both of the last 30 s of the flight; for #37 the videos `videos/cbf_teleop_two_drones_real_1080p.mp4` (hangar camera) and `videos/cbf_teleop_two_drones_ui.mp4` (Foxglove panel)) and in the laptop folder `~/flight_logs/2026-11-13/`.

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

**NEAR-831 "Change gains live from the panel in flight"**

> Real drones, 2026-11-13, flight 17:40:21 to 17:41:24 (ledger row #37). Two Starlings, `goal_two_ours.yaml`.
> One gain was changed from the panel in flight: the CBF radius, 0.55 → 0.90, at 17:40:36, while both drones hovered 2.5 m apart. It took effect: the measured closest approach was 1.76 m against the new 1.80 m keep-out.
> The other gains in the dropdown were not changed in flight.

## Part 3 · Comment only, status unchanged

**NEAR-840 "Two drones: formation and random goals with collision avoidance"**

> Real drones, 2026-11-13, flight 17:40:21 to 17:41:24, 59 s airborne (ledger row #37). The pass line was fixed before the flight: closest approach no less than 1.40 m centre to centre.
> `drone_1` (older Starling) hovered under the commander at 1.0 m. `drone_2` was hand-flown at it with the Logitech F310, three approaches along x. CBF radius 0.90 (keep-out 1.80 m), set from the panel in flight.
> Minimum separation 1.76 m: 0.04 m inside the keep-out, well above the pass line. Closer than 1.80 m for 9.0 s in total, never closer than 1.70 m. The filter held `drone_2` back and pushed `drone_1` away, up to 0.72 m, to 0.29 m from its +x fence wall. Heights 0.98 to 1.04 m. No emergency push-apart.
> One flight, one pilot. Not covered: approaches from another side, a height offset, both drones commanded to move, formations, random goals, a crossing (NEAR-951).
> No rosbag was recorded. The numbers come from both drones' own PX4 logs at 10 Hz.

**NEAR-839 "Set up each new Starling (one at a time, setup guide)"**

> The older Starling (`drone_1`) flew on 2026-11-13, and all four motors started on time in the three flights checked. On 2026-11-12 its front-right motor failed or started late in 5 of 7 arms. The cause is unknown. The owner flies it with a watcher on that motor.

## Part 4 · Findings for the owner to turn into issues

Do NOT create issues for these. List these in the sync record under "proposed, not created", one line each. None is fixed. The owner decides.

1. The commander gives no warning when no pad is sending commands. It holds position as if the sticks were centred (first attempt, 16:34:59). Check before takeoff: `ros2 topic hz /svg/drone_2/teleop_command` must show about 20 Hz.
2. The drone overshoots the commanded speed: peak horizontal speed 0.66 m/s against the 0.5 m/s stick cap.
3. An issue for the hand-flown demonstration, "one drone hand-flown at a hovering drone, held off by the collision filter", if the owner wants it tracked (ledger row #37).
4. With the stick held, the collision filter keeps pushing the hovering drone toward the wall behind it (0.29 m left at the end, ledger row #37). Let go once it resists.

## Part 5 · Write the sync record

Write a Markdown file named `2026-11-13-linear-synced.md`. State only what Linear now holds:

- the title and status of NEAR-831, NEAR-833, NEAR-834, NEAR-835, NEAR-839 and NEAR-840;
- each comment added here, and whether it was added now or already present;
- the progress of milestones M4, M5 and M7;
- the list from Part 4, marked "proposed, not created";
- anything not applied, and why;
- the totals per project for **all three** projects (HTX-R1, HTX-R2 and HTX-R3): total, Backlog, In Progress, Done, Canceled.
