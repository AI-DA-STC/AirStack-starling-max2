# Linear snapshot: Isaac Lab Pipeline for NUS Strategy Training

> Snapshot of Linear as of the sync on 16 November 2026
> ([sync record](2026-11-16-linear-synced-isaac-lab-pipeline.md), from
> [these instructions](2026-11-16-linear-agent-isaac-lab-pipeline.md)). Linear is the source of truth; this page
> is refreshed after each sync. The "In the repo" column says where the work stands in this folder on that day.

Project P-NEAR-31, team NEAR Lab. 18 issues: 11 Backlog, 4 In Progress, 3 Done, 0 Canceled.

## Milestones

| Milestone | Target date | Linear progress |
|---|---|---|
| S0 · Measure training speed | 2026-11-15 | 50 % |
| S1 · Drone model and collision filter | 2026-11-15 | 67 % |
| S2 · Game and plug-in point | — | 14 % |
| S3 · NUS strategy scored | — | 0 % |
| S4 · Realistic worlds and physics cross-check | — | 0 % |
| S5 · Hand-over to AirStack | — | 0 % |
| Side quest · NEAR Lab strategies | — | 0 % |

## Issues

| Issue | Title | Milestone | Linear status | In the repo (16 Nov) |
|---|---|---|---|---|
| NEAR-955 | Isaac Lab: train in parallel with the Starling model and measure steps per second | S0 | Done | ledger row T1 ([S0 results](../S0_RESULTS.md)) |
| NEAR-959 | Measure training speed on the training workstation | S0 | Backlog | needs the workstation |
| NEAR-960 | Copy CMU's collision filter into the training simulator | S1 | Done | ledger row T2 ([S1 results](../S1_RESULTS.md)) |
| NEAR-961 | Starling response model from the 13 Nov flight logs (exploratory) | S1 | Done | exploratory record, no ledger row |
| NEAR-962 | Fit the drone model from a planned-pushes real flight | S1 | Backlog | needs a real flight |
| NEAR-963 | Game core: thousands of games at once, varied arena and zone sizes | S2 | In Progress | S2 Tasks 2–3 done and reviewed; Task 4 (Starling layer) building |
| NEAR-964 | Check the drone model against the 12 Nov rosbag | S2 | In Progress | ran: ledger row T5 = FAIL ([record](../../records/2026-11-15_s2_bag_check_record.md)); can be closed with that result |
| NEAR-965 | Faster collision filter, checked against CMU's | S2 | In Progress | S2 Task 7, next after Task 4 |
| NEAR-966 | Scoring tool and scripted opponents | S2 | In Progress | scripted opponents done (Task 5); scoring tool is Task 6 |
| NEAR-967 | Plug-in point for a partner's strategy, with a written guide | S2 | Backlog | S2 Task 9 |
| NEAR-968 | Stand-in trainer: prove the training pipe end to end | S2 | Backlog | S2 Task 10 |
| NEAR-969 | S2 results page | S2 | Backlog | S2 Task 11 |
| NEAR-970 | Get NUS's strategy and its rule details | S3 | Backlog | owner asks NUS; related to NEAR-874 |
| NEAR-971 | Score NUS's strategy: NUS's rules against Starling limits | S3 | Backlog | after S2 and NEAR-970 |
| NEAR-972 | Games among obstacles and in the construction-site world | S4 | Backlog | — |
| NEAR-973 | Cross-check the fast simulator against full drone physics in Isaac Lab | S4 | Backlog | — |
| NEAR-974 | Export a strategy and fly it in the AirStack simulator | S5 | Backlog | related to NEAR-875 |
| NEAR-975 | Train NEAR Lab's own Guard and Strike strategies (research) | Side quest | Backlog | — |

The four In Progress issues are assigned to the owner. Linear put them in **Cycle 37 (9–15 November)**, which had
already ended on the day of the sync: move them to the current cycle in Linear if they should show there.
