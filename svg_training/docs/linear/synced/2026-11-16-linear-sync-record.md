INTERNAL · copies of the lab's project-tracker (Linear) items. Not needed to read or run anything here.

# Linear sync record — 2026-11-16

## Project

<project id="P-NEAR-31" /> — Isaac Lab Pipeline for NUS Strategy Training

| Milestone | Target date | Linear progress |
| --- | --- | --- |
| S0 · Measure training speed | 2026-11-15 | 50% |
| S1 · Drone model and collision filter | 2026-11-15 | 67% |
| S2 · Game and plug-in point | None | 14% |
| S3 · NUS strategy scored | None | 0% |
| S4 · Realistic worlds and physics cross-check | None | 0% |
| S5 · Hand-over to AirStack | None | 0% |
| Side quest · NEAR Lab strategies | None | 0% |

## Existing issue

<issue id="NEAR-955" /> — Isaac Lab: train in parallel with the Starling model and measure steps per second

Project: Isaac Lab Pipeline for NUS Strategy Training. Milestone: S0 · Measure training speed. Status: Done. Assignee: none. Cycle: none. Existing title unchanged.

Comment:

> 2026-11-16. Done for the laptop (RTX 5070 Ti), ledger row T1, 2026-11-15. Fast simulator, 5 Guard and 3 Strike drones with full sensing: about 48,000 games-steps per second. Isaac Lab full drone physics: up to 455,000 drone steps per second. These are simulator speeds with random actions, not training speeds. Not done: the training workstation (new issue in S0). Results: `svg_training/docs/S0_RESULTS.md`.

## New issues

All 17 new issues belong to Isaac Lab Pipeline for NUS Strategy Training and have no due date. S0–S5 and Side quest below refer to the full milestone names above.

| Issue | Title | Milestone | Status | Assignee | Cycle |
| --- | --- | --- | --- | --- | --- |
| <issue id="NEAR-959" /> | Measure training speed on the training workstation | S0 | Backlog | None | None |
| <issue id="NEAR-960" /> | Copy CMU's collision filter into the training simulator | S1 | Done | None | None |
| <issue id="NEAR-961" /> | Starling response model from the 13 Nov flight logs (exploratory) | S1 | Done | None | None |
| <issue id="NEAR-962" /> | Fit the drone model from a planned-pushes real flight | S1 | Backlog | None | None |
| <issue id="NEAR-963" /> | Game core: thousands of games at once, varied arena and zone sizes | S2 | In Progress | HweHuang Chia | Cycle 37 |
| <issue id="NEAR-964" /> | Check the drone model against the 12 Nov rosbag | S2 | In Progress | HweHuang Chia | Cycle 37 |
| <issue id="NEAR-965" /> | Faster collision filter, checked against CMU's | S2 | In Progress | HweHuang Chia | Cycle 37 |
| <issue id="NEAR-966" /> | Scoring tool and scripted opponents | S2 | In Progress | HweHuang Chia | Cycle 37 |
| <issue id="NEAR-967" /> | Plug-in point for a partner's strategy, with a written guide | S2 | Backlog | None | None |
| <issue id="NEAR-968" /> | Stand-in trainer: prove the training pipe end to end | S2 | Backlog | None | None |
| <issue id="NEAR-969" /> | S2 results page | S2 | Backlog | None | None |
| <issue id="NEAR-970" /> | Get NUS's strategy and its rule details | S3 | Backlog | None | None |
| <issue id="NEAR-971" /> | Score NUS's strategy: NUS's rules against Starling limits | S3 | Backlog | None | None |
| <issue id="NEAR-972" /> | Games among obstacles and in the construction-site world | S4 | Backlog | None | None |
| <issue id="NEAR-973" /> | Cross-check the fast simulator against full drone physics in Isaac Lab | S4 | Backlog | None | None |
| <issue id="NEAR-974" /> | Export a strategy and fly it in the AirStack simulator | S5 | Backlog | None | None |
| <issue id="NEAR-975" /> | Train NEAR Lab's own Guard and Strike strategies (research) | Side quest | Backlog | None | None |

Relations added:

- <issue id="NEAR-970" /> related to <issue id="NEAR-874" />.
- <issue id="NEAR-974" /> related to <issue id="NEAR-875" />.

Comment on NEAR-960:

> 2026-11-15. Built and checked against CMU's filter on 2,000 recorded scenes, ledger row T2: FAIL on 2 of 4 checks, accepted by the owner on the exact counts (13 and 109 scenes outside the limits; emergency decisions agree in 1,998 of 2,000). Results: `svg_training/docs/S1_RESULTS.md`.

Comment on NEAR-961:

> 2026-11-15. Fitted on the 13 Nov gamepad flight of drone_2 (ledger row 36): at up to 0.5 m/s the drone follows its command about 0.1–0.15 s late. Exploratory, no gates. The AirStack simulator was also fitted (ledger row T3, FAIL): its commander runs on the wall clock while the simulated PX4 runs about 1.9 times faster, so it is not used for training.

## Totals

Current non-archived, non-trashed project issues, including the moved issue:

| Project | Total | Backlog | In Progress | Done | Canceled |
| --- | --- | --- | --- | --- | --- |
| Isaac Lab Pipeline for NUS Strategy Training | 18 | 11 | 4 | 3 | 0 |
| HTX-R1 Swarm Sim Validation (Isaac) | 67 | 51 | 3 | 12 | 1 |
| HTX-R2 Starling Flight Bring-up (M2–M8) | 37 | 18 | 2 | 16 | 1 |
| HTX-R3 Multi-Drone Localisation (VO + UWB) | 17 | 16 | 0 | 1 | 0 |

## Not applied

None. Nothing deleted; no existing title changed.
