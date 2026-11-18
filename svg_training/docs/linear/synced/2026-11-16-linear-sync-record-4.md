INTERNAL · copies of the lab's project-tracker (Linear) items. Not needed to read or run anything here.

# Linear sync record 4 — 2026-11-16

Project: Isaac Lab Pipeline for NUS Strategy Training (<project id="P-NEAR-31" />).

## Milestones

| Milestone | Target date | Linear progress |
| --- | --- | --- |
| S0 · Measure training speed | 2026-11-15 | 50% |
| S1 · Drone model and collision filter | 2026-11-15 | 67% |
| S2 · Game and plug-in point | 2026-11-16 | 100% |
| S2b · Game on Isaac Lab drones | None | 6% |
| S3 · NUS strategy scored | None | 0% |
| S4 · Realistic worlds and physics cross-check | None | 0% |
| S5 · Hand-over to AirStack | None | 0% |
| Side quest · NEAR Lab strategies | None | 0% |

S2b is immediately after S2. Description:

> The S2 game on rigid-body Starling drones in Isaac Lab, with a PX4-like velocity controller using the real drone's gains, compared with the fast PyTorch simulator; the stand-in trainer on both simulators, logged to TensorBoard; an Isaac Lab video of the game.

## Issues

Milestone abbreviations below refer to the full names above.

| Issue | Title | Milestone | Status | Assignee | Cycle | Due date |
| --- | --- | --- | --- | --- | --- | --- |
| <issue id="NEAR-955" /> | Isaac Lab: train in parallel with the Starling model and measure steps per second | S0 | Done | HweHuang Chia | None | None |
| <issue id="NEAR-959" /> | Measure training speed on the training workstation | S0 | Backlog | HweHuang Chia | None | None |
| <issue id="NEAR-960" /> | Copy CMU's collision filter into the training simulator | S1 | Done | HweHuang Chia | None | None |
| <issue id="NEAR-961" /> | Starling response model from the 13 Nov flight logs (exploratory) | S1 | Done | HweHuang Chia | None | None |
| <issue id="NEAR-962" /> | Fit the drone model from a planned-pushes real flight | S1 | Backlog | HweHuang Chia | None | None |
| <issue id="NEAR-963" /> | Game core: thousands of games at once, varied arena and zone sizes | S2 | Done | HweHuang Chia | None | None |
| <issue id="NEAR-964" /> | Check the drone model against the 12 Nov rosbag | S2 | Done | HweHuang Chia | None | None |
| <issue id="NEAR-965" /> | Faster collision filter, checked against CMU's | S2 | Done | HweHuang Chia | None | None |
| <issue id="NEAR-966" /> | Scoring tool and scripted opponents | S2 | Done | HweHuang Chia | None | None |
| <issue id="NEAR-967" /> | Plug-in point for a partner's strategy, with a written guide | S2 | Done | HweHuang Chia | None | None |
| <issue id="NEAR-968" /> | Stand-in trainer: prove the training pipe end to end | S2b | Backlog | HweHuang Chia | None | None |
| <issue id="NEAR-969" /> | S2 results page | S2 | Done | HweHuang Chia | None | None |
| <issue id="NEAR-970" /> | Get NUS's strategy and its rule details | S3 | Backlog | HweHuang Chia | None | None |
| <issue id="NEAR-971" /> | Score NUS's strategy: NUS's rules against Starling limits | S3 | Backlog | HweHuang Chia | None | None |
| <issue id="NEAR-972" /> | Games among obstacles and in the construction-site world | S4 | Backlog | HweHuang Chia | None | None |
| <issue id="NEAR-973" /> | Cross-check the fast simulator against full drone physics in Isaac Lab | S2b | Backlog | HweHuang Chia | None | None |
| <issue id="NEAR-974" /> | Export a strategy and fly it in the AirStack simulator | S5 | Backlog | HweHuang Chia | None | None |
| <issue id="NEAR-975" /> | Train NEAR Lab's own Guard and Strike strategies (research) | Side quest | Backlog | HweHuang Chia | None | None |
| <issue id="NEAR-980" /> | Wrap the S2 game as an Isaac Lab environment with a PX4-like controller | S2b | In Progress | HweHuang Chia | None | None |
| <issue id="NEAR-981" /> | Isaac Lab video of the game | S2b | Backlog | HweHuang Chia | None | None |

## Comments

All eight comments below were added now; none was already present.

### NEAR-963 — added now

> 2026-11-16. Done. The game runs thousands of games at once with random arena (4–16 m) and zone sizes; NUS's rules are the main game, contact tags stay for the side quest; the Starling layer adds the fitted drone model and CMU's collision filter on every pair. Every part reviewed; a bug at the arena walls was found in review and fixed. Results: `svg_training/docs/S2_RESULTS.md`.

### NEAR-964 — added now

> 2026-11-16. Done with a FAIL, ledger row T5. Worst leg 0.120 m/s against a 0.10 m/s limit; the timing check failed mainly because of how the check fed the setpoint (joined as in the original fit, the three clean pushes fit within 0.05 m/s); the fourth leg is a 408 s gap in the recording. The model stays exploratory until a planned-pushes flight (NEAR-962).

### NEAR-965 — added now

> 2026-11-16. Done, ledger row T8 PASS: same answers as the full filter on all 2,000 test scenes, about 121,000 game-steps/s for 5 v 3 at 4,096 games (target 100,000), against 9,900 before; about 90,000 averaged over a whole game (information only). The speed-error limit was read at its 4 written decimals (owner's ruling). Ledger row T7 is an aborted first attempt, stopped to put in the wall fix.

### NEAR-966 — added now

> 2026-11-16. Done. Scoring tool and five scripted Guard and two scripted Strike tactics; reference runs ledger rows T6 and T9 (T9 on the fixed walls). Crowded 5 v 3 games still bring drones to 0.75–0.80 m near walls: a limit of CMU's filter, which does not know the walls, shared with the real commander.

### NEAR-967 — added now

> 2026-11-16. Done. skrl and Gymnasium adapters and the partner guide `svg_training/docs/PLUG_IN.md`, with runnable examples a test executes; checked by a newcomer read-through. The worked example with the stand-in trainer comes with NEAR-968.

### NEAR-969 — added now

> 2026-11-16. Done: `svg_training/docs/S2_RESULTS.md`, after a final review of the whole stage and one fix wave.

### NEAR-968 — added now

> 2026-11-16. Moved to S2b by the owner: it runs on both simulators (PyTorch as a control, then Isaac Lab), with TensorBoard logging, so training is proven on the simulator that matters.

### NEAR-973 — added now

> 2026-11-16. Moved from S4 to S2b: the owner pulled the Isaac Lab work forward.

## Not applied

None. All 20 project issues assigned to HweHuang Chia, with no cycle or due date. Automatically added cycles on the six completed issues and the new In Progress issue were removed and verified. Nothing deleted; no existing title changed.
