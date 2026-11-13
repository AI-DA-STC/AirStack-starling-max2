# Linear sync record — 2026-11-13, revised two-drone gamepad update

Workspace: nearlab. Project: HTX-R2 Starling Flight Bring-up (M2–M8).
No titles changed. No issues created. Nothing deleted.

## Current titles and statuses

| Issue | Title | Status |
| --- | --- | --- |
| NEAR-831 | Change gains live from the panel in flight | In Progress |
| NEAR-833 | Check the yaw stick turns the drone the right way, slowly and low | Done |
| NEAR-834 | Gamepad fence test | In Progress |
| NEAR-835 | Release-to-hold test and coast distance | In Progress |
| NEAR-839 | Set up each new Starling (one at a time, setup guide) | Backlog |
| NEAR-840 | Two drones: formation and random goals with collision avoidance | Done |

NEAR-831 changed from Backlog to In Progress. All other requested statuses were already in place or left unchanged as instructed.

## Comments

Three comments added now; three already present and not repeated. Earlier comments remain unchanged.

Storage exception: Linear automatically linked ledger references #36 and #37 to unrelated pull requests AI-DA-STC/drone-swarm-mc#36 and #37. Below, [automatically linked #36] and [automatically linked #37] denote those stored links. NEAR-951 in the new NEAR-840 comment is a link to that issue. All other wording below matches the stored comments.

### NEAR-831 — added now

Real drones, 2026-11-13, flight 17:40:21 to 17:41:24 (ledger row [automatically linked #37]). Two Starlings, `goal_two_ours.yaml`.
One gain was changed from the panel in flight: the CBF radius, 0.55 → 0.90, at 17:40:36, while both drones hovered 2.5 m apart. It took effect: the measured closest approach was 1.76 m against the new 1.80 m keep-out.
The other gains in the dropdown were not changed in flight.

### NEAR-833 — already present; not repeated

Real drone, 2026-11-13, flight 16:40:36 to 16:43:13 (ledger row [automatically linked #36]). One Starling (`drone_2`), Logitech F310 pad, `tools/real.sh teleop drone_2`. The pass line was fixed before the flight.
The measured heading followed the commanded heading both ways, within 3°: from −12° to −17° (right), to +11° (left), a 47° right turn to −44° in about one second, then back to 0°. Height 0.5 to 0.6 m.
During the large turn the drone moved at most 0.05 m (pass line: under 0.3 m).
That the drone turned the way the stick was pushed is the owner's report. It is not on video, and the stick itself was not recorded. The issue is closed on that report.
No rosbag was recorded. The numbers come from the drone's own PX4 log at 10 Hz.

### NEAR-834 — already present; not repeated

Real drone, 2026-11-13, ledger row [automatically linked #36]. The pass line was fixed before the flight.
Three approaches into the −y wall (at −1.5 m), at 0.44, 0.56 and 0.66 m/s. Furthest past the wall: 0.03 m (pass line: no more than 0.10 m). The commander logged "teleop fence keep-in: drone_2 limited on y" each time.
Still to fly: the +x wall and the top at 1.8 m. The highest point flown was 0.99 m.
No rosbag was recorded. The numbers come from the drone's own PX4 log at 10 Hz.

### NEAR-835 — already present; not repeated

Real drone, 2026-11-13, ledger row [automatically linked #36]. The pass line was fixed before the flight.
Four releases from about 0.5 m/s, away from the walls: coast 0.05 to 0.28 m, stopped 0.9 to 1.6 s after release, then within 0.05 to 0.15 m for 5 s (pass line: stopped within 0.5 m and 2 s, then within 0.2 m for 5 s).
From about 0.25 m/s: coast 0.01 to 0.15 m.
Still to fly: unplugging the pad in flight (pass line: stop within 0.75 m).
No rosbag was recorded. The numbers come from the drone's own PX4 log at 10 Hz.

### NEAR-840 — added now

Real drones, 2026-11-13, flight 17:40:21 to 17:41:24, 59 s airborne (ledger row [automatically linked #37]). The pass line was fixed before the flight: closest approach no less than 1.40 m centre to centre.
`drone_1` (older Starling) hovered under the commander at 1.0 m. `drone_2` was hand-flown at it with the Logitech F310, three approaches along x. CBF radius 0.90 (keep-out 1.80 m), set from the panel in flight.
Minimum separation 1.76 m: 0.04 m inside the keep-out, well above the pass line. Closer than 1.80 m for 9.0 s in total, never closer than 1.70 m. The filter held `drone_2` back and pushed `drone_1` away, up to 0.72 m, to 0.29 m from its +x fence wall. Heights 0.98 to 1.04 m. No emergency push-apart.
One flight, one pilot. Not covered: approaches from another side, a height offset, both drones commanded to move, formations, random goals, a crossing (NEAR-951).
No rosbag was recorded. The numbers come from both drones' own PX4 logs at 10 Hz.

### NEAR-839 — added now

The older Starling (`drone_1`) flew on 2026-11-13, and all four motors started on time in the three flights checked. On 2026-11-12 its front-right motor failed or started late in 5 of 7 arms. The cause is unknown. The owner flies it with a watcher on that motor.

## Milestone progress

Displayed Linear progress after this sync; distinct from simple completed-issue ratios.

| Milestone | Displayed progress | Total | Backlog | In Progress | Done | Canceled |
| --- | --- | --- | --- | --- | --- | --- |
| M4 · Goal flights with the braking fence | 19% | 4 | 1 | 3 | 0 | 0 |
| M5 · Gamepad flying on the real drone | 38% | 4 | 1 | 2 | 1 | 0 |
| M7 · Multi-drone | 20% | 5 | 4 | 0 | 1 | 0 |

## Proposed, not created

No issues created for these findings; none is recorded as fixed by this sync. Owner decides.

1. The commander gives no warning when no pad is sending commands. It holds position as if the sticks were centred (first attempt, 16:34:59). Check before takeoff: `ros2 topic hz /svg/drone_2/teleop_command` must show about 20 Hz.
2. The drone overshoots the commanded speed: peak horizontal speed 0.66 m/s against the 0.5 m/s stick cap.
3. An issue for the hand-flown demonstration, "one drone hand-flown at a hovering drone, held off by the collision filter", if the owner wants it tracked (ledger row #37).
4. With the stick held, the collision filter keeps pushing the hovering drone toward the wall behind it (0.29 m left at the end, ledger row #37). Let go once it resists.

## Not applied / exceptions

No requested status or comment remains unapplied. Three existing comments were not duplicated. Literal ledger references were automatically converted into unrelated pull request links, as noted above; exact literal rendering was therefore not preserved. No existing comments were edited in this sync.

## Project totals

Freshly verified after updates. All non-trashed issues, including archived. No other statuses returned.

| Project | Total | Backlog | In Progress | Done | Canceled |
| --- | --- | --- | --- | --- | --- |
| HTX-R1 Swarm Sim Validation (Isaac) | 66 | 52 | 1 | 12 | 1 |
| HTX-R2 Starling Flight Bring-up (M2–M8) | 36 | 19 | 7 | 9 | 1 |
| HTX-R3 Multi-Drone Localisation (VO + UWB) | 17 | 16 | 0 | 1 | 0 |
