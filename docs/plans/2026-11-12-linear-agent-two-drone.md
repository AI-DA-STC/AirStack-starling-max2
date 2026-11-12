# Linear update — 2026-11-12, first real two-drone session

Instructions for the Linear agent, in the **nearlab** workspace, project **HTX-R2 Starling Flight Bring-up (M2–M8)**. Apply every step below. Delete nothing. Use the comments exactly as written. Change no title. Check Linear before each step: if a status, comment or issue is already in place, do not repeat it. The one new issue in Part 2 is unassigned with no due date.

Everything below is the **real drones** (two Starlings, motion-capture positioning (mocap), AI.R STC hangar), on 2026-11-12. Times are +08.

Evidence lives in the repo https://github.com/AI-DA-STC/AirStack-starling-max2 (ledger rows #34 and #35 in `docs/record/LEDGER.md`, videos `videos/cbf_drone_real_1080p.mp4` (hangar camera) and `videos/cbf_check_ui.mp4` (Foxglove panel), both of the 18:00:16 flight) and in the laptop folder `~/flight_logs/2026-11-12/`.

## Part 1 · Set to Done, with its comment

**NEAR-840 "Two drones: formation and random goals with collision avoidance"**

> Real drones, 2026-11-12. Two real drones took off, hovered and landed together for the first time (17:19:54).
> The collision filter was observed in two flights at radius 0.80 (keep-out 1.60 m).
> Recorded flight 17:45:24: minimum separation 1.52 m from odometry and 1.50 m from mocap. The hovering drone gave way up to 0.38 m. Height stayed within 1.97–2.04 m. No emergency push-apart.
> Flight 18:00:16: minimum 1.57 m, with the goal placed on the other drone's point for 9 s (hangar and panel videos).
> This is an observation. No gate was fixed beforehand. One approach only: one drone flown toward a hovering one, along one direction.
> Closed for collision avoidance by the owner's decision, 2026-11-12. Not flown: formations, random goals, both drones moving, a crossing, a recording at the config radius 0.55. These move to the new issue "Two drones: formation and random goals" in M7.
> Two attempts failed. At 16:42:47 the drones flew head-on at takeoff, because takeoff flies a straight line to the takeoff point and the drones stood on each other's sides. Closest was 1.04 m.
> At 16:48:52 the older drone's front-right motor did not start. It ran 7.5 m at up to 4.5 m/s, and both drones were killed by RC.

## Part 2 · Create one issue

Create this issue in project HTX-R2, milestone **M7 · Multi-drone**, status **Backlog**. Relate it to NEAR-840.

**"Two drones: formation and random goals"**

> The part of NEAR-840 that has not flown. Two real drones fly a formation and random goals with the collision filter on, both drones moving, including a crossing, with a recording. Also one recorded approach at the config radius 0.55 (keep-out 1.10 m). Fix the pass line for minimum separation before flying. Blocked while the older Starling is grounded (see the comment on NEAR-839).

## Part 3 · Comment only, status unchanged

**NEAR-839 "Set up each new Starling (one at a time, setup guide)"**

> 2026-11-12. The second Starling in use today is an older Starling Max 2 already in the lab (10.40.2.11, `MAV_SYS_ID` 1, `XRCE_DDS_KEY` 2), set up as `drone_1`. The Starling that flew on 2026-11-11 is now `drone_2` (`MAV_SYS_ID` 2, `XRCE_DDS_KEY` 1).
> The older drone is GROUNDED. Its front-right motor failed to start or started late in 5 of its last 7 arms on 2026-11-12, with two flips at takeoff (16:48:52 and 17:47:42). Cause unknown (ESC, motor, wiring or prop).

**NEAR-819 "Confirm the drone ID matches the controller’s target"**

> 2026-11-12. Both drones read back: older `MAV_SYS_ID` 1, newer 2. The interfaces run with target_systems 1,2. Both armed and flew on those commands.

**NEAR-826 "Landing test: settle on the ground, then disarm"**

> 2026-11-12. In the 16:42:47 flight PX4 rejected both disarm commands ("Disarming denied! Not landed") while the commander logged "landed, disarmed (attempt 1)". PX4 disarmed by itself 1.0 s and 1.6 s later. `land_settle_s` was 0.0.

**NEAR-831 "Change gains live from the panel in flight"**

> 2026-11-12. The CBF radius was changed from the panel on the ground between flights (0.55 → 0.85, later 0.55 → 0.80) and took effect. A commander restart resets it to the config value 0.55.
> Not yet done: a change while airborne.
> Finding: raising the radius while two drones are already inside the new keep-out triggers the emergency push-apart at once (seen on the ground, 14 warning lines).

## Part 4 · Findings for the owner to turn into issues

Do NOT create issues for these. List these in the sync record under "proposed, not created", one line each. None is fixed. The owner decides.

1. Takeoff flies a straight line to the configured takeoff point. A drone standing elsewhere is flown sideways to it. Two drones standing on each other's sides fly head-on. Nothing checks where the drones stand.
2. The fence does not act during the climb or the landing, only once a drone has reached its takeoff point. Takeoff points are not checked against the fence.
3. The collision filter has no floor. When it separates two drones vertically it can lower one into the ground.
4. The commander does not know when a drone has been killed or has disarmed. It keeps sending setpoints (about 50 s in attempt 2, about 12 minutes after the 17:47 flip until `land` was called). After any kill, call `land`.
5. The commander logs "landed, disarmed" even when PX4 refused the disarm.
6. Nothing checks that all four motors are running before lift-off.
7. Raising the CBF radius while two drones are already inside the new keep-out triggers the emergency push-apart at once (seen on the ground at 17:36:37, 14 warning lines).
8. Hardware: drone_1 (older Starling) front-right motor start fault. GROUNDED until fixed.

## Part 5 · Write the sync record

Write a Markdown file named `2026-11-12-linear-synced.md`. State only what Linear now holds:

- the title and status of NEAR-819, NEAR-826, NEAR-831, NEAR-839 and NEAR-840;
- the NEAR id, title, milestone and status of the new issue from Part 2;
- each comment added here, and whether it was added now or already present;
- the progress of milestones M2, M3, M4 and M7;
- the list from Part 4, marked "proposed, not created";
- anything not applied, and why;
- the totals per project for **all three** projects (HTX-R1, HTX-R2 and HTX-R3): total, Backlog, In Progress, Done, Canceled.
