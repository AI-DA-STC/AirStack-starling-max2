# Linear update — 2026-11-15, cuVSLAM next steps and the 26 November demo

Instructions for the Linear agent, in the **nearlab** workspace. Apply every step below. Delete nothing. Use the comments and titles exactly as written. Change no existing title. Check Linear before each step: if a status, comment or issue is already in place, do not repeat it. Every new issue is unassigned with no due date.

The real-drone demo is on **26 November 2026**. The code for random goals, the figure-8 and the hand-flown intruder is CMU's commander (Yikuan's `svg_ground_control`), vendored in the repo https://github.com/AI-DA-STC/AirStack-starling-max2 under `AirStack/robot/ros_ws/src/svg_ground_control/`.

## Part 1 · cuVSLAM: set four issues to In Progress (project HTX-R1, milestone S5b)

NEAR-790 and NEAR-860 stay In Progress. Set each issue below to **In Progress** and add this comment to each:

> 2026-11-15. Moved to In Progress by the owner as the next cuVSLAM step after NEAR-860 and NEAR-790. From now on, whenever a cuVSLAM issue is closed, the next cuVSLAM Backlog issue moves to In Progress, so three to four stay open.

- **NEAR-791** "Add a mapping mode to the cuVSLAM node"
- **NEAR-792** "Hand-fly a mapping loop and save the map"
- **NEAR-793** "Localise in the saved map from 5+ starting points"
- **NEAR-794** "Compare the localised position with the simulator’s position"

## Part 2 · Comments on the two existing demo flights (project HTX-R2, M7)

**NEAR-951 "Two drones: formation and random goals"**

> 2026-11-15. Part of the 26 November demo. Two real Starlings fly CMU's `random_goals` scenario with the collision filter on, inside the lab fence at up to 0.5 m/s, with a recording and a pass line fixed beforehand. The set-up and sim rehearsal are in the new issue "Random goals on two real Starlings: a set-up that fits the lab, rehearsed in sim first".

**NEAR-953 "Two drones: figure-8 with collision avoidance"**

> 2026-11-15. Part of the 26 November demo. CMU's `figure_eight` scenario needs exactly three drones and was flown at CMU with circles of radius 1.5 m at 2.0 m/s, which needs about 6 m of room. The fit to the lab and the third slot are in the new issue "Figure-8 on two real Starlings: fit the eight in the lab and fill the third slot".

## Part 3 · Create six issues (project HTX-R2, milestone **M7 · Multi-drone**)

Create them in this order. "Done when" lines are targets, not results.

**1. "Random goals on two real Starlings: a set-up that fits the lab, rehearsed in sim first"** — status **In Progress**. Relate it to NEAR-951.

> For the 26 November demo. Write a real-drone set-up file for CMU's `random_goals` scenario with every goal inside the lab fence (±2 m) and the speed capped at 0.5 m/s, then fly the same file in Isaac Sim before the real drones fly it.
>
> Done when (target): the set-up file is in the repo; one sim run of at least 3 minutes is recorded with the minimum separation between the drones; the pass line for the real flight is written down before it flies.

**2. "Figure-8 on two real Starlings: fit the eight in the lab and fill the third slot"** — status **In Progress**. Relate it to NEAR-953.

> For the 26 November demo. CMU's figure-8 is two touching circles, flown at CMU with radius 1.5 m at 2.0 m/s (about 6 m long). The lab fence allows about 4 m, so the radius drops to about 0.75 m at 0.5 m/s: one lap every 19 s, the two drones meeting at the crossing every 9 s. CMU's code refuses to start the figure-8 with fewer than three drones; one option to check is a third drone that exists only in the sim, parked away from the eight (CMU's `hybrid_squeeze.yaml` already mixes real and sim drones).
>
> Done when (target): the set-up file is in the repo; the eight fits inside the fence with margin; one sim run is recorded with the minimum separation at the crossing; the pass line for the real flight is written down before it flies.

**3. "Third drone for the intruder demo: Crazyflie or DJI, tracked by motion capture"** — status **In Progress**. Relate it to NEAR-841.

> Research. CMU's demo has two drones flying the figure-8 while a person flies a third drone into their path, and the two dodge it. The lab has only two Starlings. CMU's commander can track a drone it never controls (`external_drones`: "tracked for the safety filter but never commanded (e.g. RC-flown)"); the Starlings then do all the dodging. So the third drone needs motion-capture markers and its own remote, not PX4.
>
> Compare a Crazyflie (the lab already flies them with CrazySwarm2 and motion capture) and a small DJI drone on: markers it can carry and how well Motive tracks it; how it is flown and how it is stopped in an emergency; clashes with the Starlings' ROS 2 domain and the motion-capture stream; its size against the collision filter's keep-out; how its position would reach the commander.
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

**6. "26 November demo: run sheet, go/no-go checks and one dress rehearsal"** — status **Backlog**.

> The order of flights for the demo day, the checks that decide whether each flight goes, who stands where, and one full practice run before 26 November.
>
> Done when (target): the run sheet is written and one dress rehearsal has been flown.

## Part 4 · Write the sync record

Write a Markdown file named `2026-11-15-linear-sync-record.md`. State only what Linear now holds:

- the title and status of NEAR-790, NEAR-791, NEAR-792, NEAR-793, NEAR-794, NEAR-860, NEAR-951 and NEAR-953;
- the NEAR id, title, project, milestone, status and relations of each of the six new issues;
- each comment added here, and whether it was added now or already present;
- the progress of milestones S5b (HTX-R1) and M7 (HTX-R2);
- anything not applied, and why;
- the totals per project for **all three** projects (HTX-R1, HTX-R2 and HTX-R3): total, Backlog, In Progress, Done, Canceled.
