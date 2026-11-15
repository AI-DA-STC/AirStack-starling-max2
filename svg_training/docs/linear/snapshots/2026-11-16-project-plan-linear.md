# Isaac Lab Pipeline for NUS Strategy Training: project plan (Linear milestones and issues)

NEAR Lab · Linear snapshot: 16 November 2026, after the project was created
([instructions](../updates/2026-11-16-linear-agent-isaac-lab-pipeline.md),
[sync record](../synced/2026-11-16-linear-sync-record.md)), its issues were taken out of cycles
([instructions](../updates/2026-11-16-linear-agent-remove-cycles.md),
[sync record](../synced/2026-11-16-linear-sync-record-2.md)) and every issue was assigned to the owner
([instructions](../updates/2026-11-16-linear-agent-assign-all.md),
[sync record](../synced/2026-11-16-linear-sync-record-3.md)).

Linear is the source of truth: this file mirrors the project in Linear as of the snapshot above. Only completed
milestones carry target dates; no issue has a cycle or a due date (owner, 16 November). Each issue links to its
Linear page. The "In the repo" column says where the work stood in `svg_training/` on the snapshot date; it is not
a Linear field.

## Reconciliation notes

- 1 project (P-NEAR-31, team NEAR Lab, project lead: the owner), 7 milestones, 18 issues: 3 Done, 4 In Progress,
  11 Backlog, 0 Canceled. Every issue is assigned to the owner.
- 2026-11-16 third sync: the 14 unassigned issues were assigned to the owner. Nothing else changed.
- 2026-11-16 second sync: NEAR-963…966 taken out of Cycle 37 (which had ended); no issue has a cycle or a due date.
- 2026-11-16 first sync: project and milestones created; NEAR-955 moved in from HTX-R1 (S0, Done, with comment);
  17 new issues NEAR-959…975; NEAR-960 and NEAR-961 Done with comments; relations NEAR-970 ↔ NEAR-874 and
  NEAR-974 ↔ NEAR-875. Milestone progress below is Linear's displayed figure at this sync.

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

| Issue | Title | Milestone | Status | In the repo (16 Nov) |
|---|---|---|---|---|
| [NEAR-955](https://linear.app/nearlab/issue/NEAR-955) | Isaac Lab: train in parallel with the Starling model and measure steps per second | S0 | Done | ledger row T1 ([S0 results](../../S0_RESULTS.md)) |
| [NEAR-959](https://linear.app/nearlab/issue/NEAR-959) | Measure training speed on the training workstation | S0 | Backlog | needs the workstation |
| [NEAR-960](https://linear.app/nearlab/issue/NEAR-960) | Copy CMU's collision filter into the training simulator | S1 | Done | ledger row T2 ([S1 results](../../S1_RESULTS.md)) |
| [NEAR-961](https://linear.app/nearlab/issue/NEAR-961) | Starling response model from the 13 Nov flight logs (exploratory) | S1 | Done | exploratory record, no ledger row |
| [NEAR-962](https://linear.app/nearlab/issue/NEAR-962) | Fit the drone model from a planned-pushes real flight | S1 | Backlog | needs a real flight |
| [NEAR-963](https://linear.app/nearlab/issue/NEAR-963) | Game core: thousands of games at once, varied arena and zone sizes | S2 | In Progress | S2 Tasks 2–4 done and reviewed |
| [NEAR-964](https://linear.app/nearlab/issue/NEAR-964) | Check the drone model against the 12 Nov rosbag | S2 | In Progress | ran: ledger row T5 = FAIL ([record](../../../records/2026-11-15_s2_bag_check_record.md)); can be closed with that result |
| [NEAR-965](https://linear.app/nearlab/issue/NEAR-965) | Faster collision filter, checked against CMU's | S2 | In Progress | S2 Task 7: accuracy half done; speed run waits on the owner's gate ruling |
| [NEAR-966](https://linear.app/nearlab/issue/NEAR-966) | Scoring tool and scripted opponents | S2 | In Progress | scripted opponents done (Task 5); scoring tool building (Task 6) |
| [NEAR-967](https://linear.app/nearlab/issue/NEAR-967) | Plug-in point for a partner's strategy, with a written guide | S2 | Backlog | S2 Task 9 |
| [NEAR-968](https://linear.app/nearlab/issue/NEAR-968) | Stand-in trainer: prove the training pipe end to end | S2 | Backlog | S2 Task 10 |
| [NEAR-969](https://linear.app/nearlab/issue/NEAR-969) | S2 results page | S2 | Backlog | S2 Task 11 |
| [NEAR-970](https://linear.app/nearlab/issue/NEAR-970) | Get NUS's strategy and its rule details | S3 | Backlog | owner asks NUS; related to NEAR-874 |
| [NEAR-971](https://linear.app/nearlab/issue/NEAR-971) | Score NUS's strategy: NUS's rules against Starling limits | S3 | Backlog | after S2 and NEAR-970 |
| [NEAR-972](https://linear.app/nearlab/issue/NEAR-972) | Games among obstacles and in the construction-site world | S4 | Backlog | — |
| [NEAR-973](https://linear.app/nearlab/issue/NEAR-973) | Cross-check the fast simulator against full drone physics in Isaac Lab | S4 | Backlog | — |
| [NEAR-974](https://linear.app/nearlab/issue/NEAR-974) | Export a strategy and fly it in the AirStack simulator | S5 | Backlog | related to NEAR-875 |
| [NEAR-975](https://linear.app/nearlab/issue/NEAR-975) | Train NEAR Lab's own Guard and Strike strategies (research) | Side quest | Backlog | — |
