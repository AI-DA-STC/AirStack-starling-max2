# Linear update — 2026-11-16, demo flights flown, cuVSLAM next steps

Instructions for the Linear agent, in the **nearlab** workspace (team NEAR Lab). Apply every step below. Delete nothing. Use the comments and titles exactly as written. Change no existing title. Check Linear before each step: if a status, comment or issue is already in place, do not repeat it. Assign every new issue to me (HweHuang Chia, the person who uploads this file). No issue touched here gets a cycle or a due date: if Linear adds an In Progress issue to a cycle, set the cycle back to none.

This file replaces `2026-11-15-linear-agent-demo-prep.md`, which was never applied. Do not apply that file.

The real-drone demo is on **26 November 2026**. It shows three flights: two drones with one flown by hand; two drones flying random goals with the collision filter; two drones flying a figure-8 with the collision filter. The software is CMU's commander (Yikuan's `svg_ground_control`) in the repo https://github.com/AI-DA-STC/AirStack-starling-max2, under `AirStack/robot/ros_ws/src/svg_ground_control/`.

## Part 1 · cuVSLAM: set four issues to In Progress (project HTX-R1, milestone S5b)

NEAR-790 and NEAR-860 stay In Progress. Set each issue below to **In Progress** and add this comment to each:

> 2026-11-16. Moved to In Progress by the owner as the next cuVSLAM step after NEAR-860 and NEAR-790. From now on, whenever a cuVSLAM issue is closed, the next cuVSLAM Backlog issue moves to In Progress, so three to four stay open.

- **NEAR-791** "Add a mapping mode to the cuVSLAM node"
- **NEAR-792** "Hand-fly a mapping loop and save the map"
- **NEAR-793** "Localise in the saved map from 5+ starting points"
- **NEAR-794** "Compare the localised position with the simulator’s position"

## Part 2 · Set to Done, each with its comment (project HTX-R2, milestone M7)

**NEAR-951 "Two drones: formation and random goals"**

> 2026-11-16. Closed by the owner for random goals. The two real Starlings flew CMU's random_goals scenario with the collision filter on, at 2.0 m height and 0.5 m/s, and the owner reports it worked (config random_goals_two_ours.yaml, CHG-0071). No recording was saved, so the closest approach was not measured. Found offline before the flight: CMU's random goals can give the two drones goals closer than the 1.10 m keep-out, and they then stop side by side until landed; the fix is a new issue. Formations were not flown.

**NEAR-953 "Two drones: figure-8 with collision avoidance"**

> 2026-11-16. Closed by the owner. The two real Starlings flew CMU's figure-8 with the collision filter on: one shared eight of radius 1.5 m, tilted 30°, the drones in opposite directions meeting head-on at the crossing, at up to 2.0 m/s (CMU's speed), and the owner reports it worked (config figure_eight_two_ours.yaml, CHG-0075 to CHG-0080). CMU's code needed three drones; patch 0008 (CHG-0074) lets it fly with two. No recording was saved, so the closest approach was not measured.

## Part 3 · Create five issues (project HTX-R2, milestone **M7 · Multi-drone**)

Create them in this order. "Done when" lines are targets, not results.

**1. "26 November demo: three two-drone flights, run sheet and dress rehearsal"** — status **In Progress**. Relate it to NEAR-951 and NEAR-953.

> The demo shows three flights on the two real Starlings: (1) one drone hovers while the other is flown by hand with the gamepad toward it, and the collision filter keeps them apart; (2) both drones fly CMU's random goals with the collision filter; (3) both drones fly CMU's figure-8 with the collision filter. All three were flown on 2026-11-16.
>
> Done when (target): one run sheet with the order, the cold-start commands, the go/no-go checks and who stands where; one full dress rehearsal before 26 November with all three flights recorded (rosbag and video) and the closest approach of each measured against a pass line written down before it flies.

**2. "Random goals: re-pick a goal that lands inside the other drone's keep-out"** — status **Backlog**. Relate it to NEAR-951.

> CMU's random_goals picks each drone's next goal on its own. Offline, in the lab's room size, two goals often land closer than the 1.10 m keep-out; the two drones then stop side by side and stay there until landed (median 13 s into a flight at 2.0 m height). Re-pick a goal that is within 1.10 m of the other drone's goal, as a recorded patch to CMU's code with a test.
>
> Done when (target): the patch and its test are in the repo, and an offline run of 5 minutes shows no stop.

**3. "Third drone for the intruder demo: Crazyflie or DJI, tracked by motion capture"** — status **Backlog**. Relate it to NEAR-841.

> CMU's demo has two drones flying the figure-8 while a person flies a third drone into their path, and the two dodge it. The lab has two Starlings. CMU's commander can track a drone it never controls (external_drones: "tracked for the safety filter but never commanded (e.g. RC-flown)"), so the third drone needs motion-capture markers and its own remote, not PX4.
>
> Compare a Crazyflie (the lab already flies them with CrazySwarm2 and motion capture) and a small DJI drone on: markers it can carry and how well Motive tracks it; how it is flown and stopped in an emergency; clashes with the Starlings' ROS 2 domain and the motion-capture stream; its size against the collision filter's keep-out; how its position would reach the commander.
>
> Done when (target): a short written comparison with a recommendation, for the owner to decide.

**4. "Make the Starlings see the third drone: its motion-capture position into the commander"** — status **Backlog**. Relate it to the issue created in step 3.

> Send the third drone's tracked position into CMU's commander as an external drone. First in the sim: a tracked object carried by hand in the room while sim Starlings dodge it, with no real drone flying. Then with the real Starlings, everyone outside the net.
>
> Done when (target): in the sim test, the sim Starlings move away from the hand-carried object, shown in a recording.

**5. "Figure-8 with a hand-flown intruder: two Starlings and the third drone, recorded"** — status **Backlog**. Relate it to NEAR-953 and to the issue created in step 4.

> The CMU intruder demo, recreated in the lab. Two real Starlings fly the figure-8 with the collision filter on while a pilot flies the third drone into their path.
>
> Done when (target): the flight is recorded on video and the owner has watched it; the minimum separation is measured against a pass line written down before the flight.

## Part 4 · Write the sync record

Write a Markdown file named `2026-11-16-linear-sync-record.md`. State only what Linear now holds:

- the title and status of NEAR-790, NEAR-791, NEAR-792, NEAR-793, NEAR-794, NEAR-860, NEAR-951 and NEAR-953;
- the NEAR id, title, project, milestone, status, assignee and relations of each of the five new issues;
- each comment added here, and whether it was added now or already present;
- the progress of milestones S5b (HTX-R1) and M7 (HTX-R2);
- anything not applied, and why;
- the totals per project for **all four** projects (HTX-R1, HTX-R2, HTX-R3 and Isaac Lab Pipeline for NUS Strategy Training): total, Backlog, In Progress, Done, Canceled.
