# Linear sync record — 2026-11-16

Workspace: nearlab. Team: NEAR Lab.

## Existing issues — verified final state

| Issue | Title | Status |
| --- | --- | --- |
| NEAR-790 | Hand-fly drone_1 with cuVSLAM running, record and score the flight | In Progress |
| NEAR-791 | Add a mapping mode to the cuVSLAM node | In Progress |
| NEAR-792 | Hand-fly a mapping loop and save the map | In Progress |
| NEAR-793 | Localise in the saved map from 5+ starting points | In Progress |
| NEAR-794 | Compare the localised position with the simulator's position | In Progress |
| NEAR-860 | Record the stereo camera images so a flight can be replayed through cuVSLAM | In Progress |
| NEAR-951 | Two drones: formation and random goals | Done |
| NEAR-953 | Two drones: figure-8 with collision avoidance | Done |

NEAR-790 and NEAR-860 retained In Progress. NEAR-791–NEAR-794 changed from Backlog to In Progress and remain in HTX-R1, milestone S5b · Map the construction site with cuVSLAM. NEAR-951 and NEAR-953 changed from In Progress to Done and remain in HTX-R2, milestone M7 · Multi-drone. Existing titles were not changed.

## Five new issues — verified final state

All five belong to HTX-R2 Starling Flight Bring-up (M2–M8), milestone M7 · Multi-drone, and are assigned to HweHuang Chia. Created in the order below. Relations are related-to, not blocking dependencies.

| Issue | Title | Project | Milestone | Status | Assignee | Related issues (including reciprocal relations) |
| --- | --- | --- | --- | --- | --- | --- |
| NEAR-984 | 26 November demo: three two-drone flights, run sheet and dress rehearsal | HTX-R2 Starling Flight Bring-up (M2–M8) | M7 · Multi-drone | In Progress | HweHuang Chia | NEAR-951, NEAR-953 |
| NEAR-985 | Random goals: re-pick a goal that lands inside the other drone's keep-out | HTX-R2 Starling Flight Bring-up (M2–M8) | M7 · Multi-drone | Backlog | HweHuang Chia | NEAR-951 |
| NEAR-986 | Third drone for the intruder demo: Crazyflie or DJI, tracked by motion capture | HTX-R2 Starling Flight Bring-up (M2–M8) | M7 · Multi-drone | Backlog | HweHuang Chia | NEAR-841, NEAR-987 |
| NEAR-987 | Make the Starlings see the third drone: its motion-capture position into the commander | HTX-R2 Starling Flight Bring-up (M2–M8) | M7 · Multi-drone | Backlog | HweHuang Chia | NEAR-986, NEAR-988 |
| NEAR-988 | Figure-8 with a hand-flown intruder: two Starlings and the third drone, recorded | HTX-R2 Starling Flight Bring-up (M2–M8) | M7 · Multi-drone | Backlog | HweHuang Chia | NEAR-953, NEAR-987 |

All eight existing issues listed above and all five new issues have no cycle and no due date, verified after updates. Cycle assignments automatically applied during status changes were cleared in a separate update. NEAR-841, referenced by a new relation, also had no cycle or due date when checked.

## Comments

### NEAR-791, NEAR-792, NEAR-793 and NEAR-794

Added now, once to each of these four issues; not already present. The same comment appears on each:

> 2026-11-16. Moved to In Progress by the owner as the next cuVSLAM step after NEAR-860 and NEAR-790. From now on, whenever a cuVSLAM issue is closed, the next cuVSLAM Backlog issue moves to In Progress, so three to four stay open.

### NEAR-951

Added now; not already present:

> 2026-11-16. Closed by the owner for random goals. The two real Starlings flew CMU's random_goals scenario with the collision filter on, at 2.0 m height and 0.5 m/s, and the owner reports it worked (config random_goals_two_ours.yaml, CHG-0071). No recording was saved, so the closest approach was not measured. Found offline before the flight: CMU's random goals can give the two drones goals closer than the 1.10 m keep-out, and they then stop side by side until landed; the fix is a new issue. Formations were not flown.

### NEAR-953

Added now; not already present:

> 2026-11-16. Closed by the owner. The two real Starlings flew CMU's figure-8 with the collision filter on: one shared eight of radius 1.5 m, tilted 30°, the drones in opposite directions meeting head-on at the crossing, at up to 2.0 m/s (CMU's speed), and the owner reports it worked (config figure_eight_two_ours.yaml, CHG-0075 to CHG-0080). CMU's code needed three drones; patch 0008 (CHG-0074) lets it fly with two. No recording was saved, so the closest approach was not measured.

All six added comments were read back and verified. Existing comments were preserved.

## Milestone progress

Linear's reported milestone progress after the updates:

| Project | Milestone | Progress |
| --- | --- | --- |
| HTX-R1 Swarm Sim Validation (Isaac) | S5b · Map the construction site with cuVSLAM | 25% |
| HTX-R2 Starling Flight Bring-up (M2–M8) | M7 · Multi-drone | 30% |

## Project totals

Verified after issue creation and status changes. Includes archived issues; archived-only queries returned zero for all four projects. Trashed issues are excluded. Status columns use the named statuses, not broader status types.

| Project | Total | Backlog | In Progress | Done | Canceled |
| --- | ---: | ---: | ---: | ---: | ---: |
| HTX-R1 Swarm Sim Validation (Isaac) | 67 | 47 | 7 | 12 | 1 |
| HTX-R2 Starling Flight Bring-up (M2–M8) | 42 | 22 | 1 | 18 | 1 |
| HTX-R3 Multi-Drone Localisation (VO + UWB) | 17 | 16 | 0 | 1 | 0 |
| Isaac Lab Pipeline for NUS Strategy Training | 20 | 10 | 1 | 9 | 0 |
| Total | 146 | 95 | 9 | 40 | 2 |

## Not applied / scope notes

No requested issue, status, comment, relation or cycle-clearance update remains unapplied. Nothing was deleted and no existing title was changed. The superseded 2026-11-15 file was not applied.

The future cuVSLAM handoff rule is recorded in the four requested comments; no automation was configured. The explicit instruction to leave NEAR-790 and NEAR-860 In Progress and start four further cuVSLAM issues leaves six named cuVSLAM issues In Progress, rather than the three-to-four aspiration expressed in the comment.
