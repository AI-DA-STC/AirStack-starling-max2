INTERNAL · copies of the lab's project-tracker (Linear) items. Not needed to read or run anything here.

# Isaac Lab Pipeline for NUS Strategy Training: project plan (Linear milestones and issues)

NEAR Lab · Linear snapshot: 23 November 2026, after the S2b/S3 catch-up and the STE learning track's milestones and
issues were added ([instructions](../updates/2026-11-23-linear-agent-ste-track-and-catch-up.md),
[sync record](../synced/2026-11-23-linear-sync-record.md)). Before: [16 November](2026-11-16-project-plan-linear.md).

Linear is the source of truth: this file mirrors the project in Linear as of the snapshot above. Completed milestones
carry target dates (S0 and S1 kept the dates set on 16 Nov); no issue has a cycle or a due date. Each issue links to its
Linear page. The "In the repo" column says where the work stood in `svg_training/` on 23 November; it is not a Linear
field.

## Reconciliation notes

- 1 project (P-NEAR-31, team NEAR Lab), 18 milestones, 48 issues: 33 Done, 3 In Progress, 12 Backlog,
  0 Canceled. Every issue is assigned to the owner, with no cycle and no due date (read back by the Linear agent).
- 2026-11-23 sync: NEAR-970, NEAR-971 and NEAR-981 Done with comments; NEAR-975 In Progress (umbrella of the STE
  track); comments on NEAR-980, 968, 973, 962, 959, 972, 974; S3 dated 2026-11-20 (100 %); ten new milestones STE L0–L9
  (L0 dated 2026-11-22, 100 %); 28 new issues NEAR-991…1018 (STE L0: 14 Done; STE L1: 7 Done, 1 In Progress, 6 Backlog).
  Cycles the agent added automatically were removed.
- Known stale link: the NEAR-970 comment points at `docs/WHAT_WE_DID_DAY_BY_DAY.md`, renamed on 23 Nov to
  [NUS_PORT_REPORT.md](../../NUS_PORT_REPORT.md) (the uploaded file predates the rename).
- Owner decisions open in Linear: NEAR-968, NEAR-973, NEAR-980 (close or keep).
- Earlier syncs: [16 November snapshot](2026-11-16-project-plan-linear.md).

## Milestones

| Milestone | Target date | Linear progress |
|---|---|---|
| S0 · Measure training speed | 2026-11-15 | 50 % |
| S1 · Drone model and collision filter | 2026-11-15 | 67 % |
| S2 · Game and plug-in point | 2026-11-16 | 100 % |
| S2b · Game on Isaac Lab drones | — | 31 % |
| S3 · NUS strategy scored | 2026-11-20 | 100 % |
| S4 · Realistic worlds and physics cross-check | — | 0 % |
| S5 · Hand-over to AirStack | — | 0 % |
| Side quest · NEAR Lab strategies | — | 25 % |
| STE L0 · Game definition and feasibility | 2026-11-22 | 100 % |
| STE L1 · Drone model | — | 48 % |
| STE L2 · Game rules in the training copy | — | 0 % |
| STE L3 · Learner | — | 0 % |
| STE L4 · Evaluation suite and gates | — | 0 % |
| STE L5 · League self-play | — | 0 % |
| STE L6 · QC and export | — | 0 % |
| STE L7 · AirStack side | — | 0 % |
| STE L8 · Real flight | — | 0 % |
| STE L9 · Documentation | — | 0 % |

## Issues

| Issue | Title | Milestone | Status | In the repo (23 Nov) |
|---|---|---|---|---|
| [NEAR-955](https://linear.app/nearlab/issue/NEAR-955) | Isaac Lab: train in parallel with the Starling model and measure steps per second | S0 | Done | ledger row T1 ([S0 results](../../S0_RESULTS.md)) |
| [NEAR-959](https://linear.app/nearlab/issue/NEAR-959) | Measure training speed on the training workstation | S0 | Backlog | laptop speed T48 (STE L0.2); 5090 speed re-measure with STE L1.7 |
| [NEAR-960](https://linear.app/nearlab/issue/NEAR-960) | Copy CMU's collision filter into the training simulator | S1 | Done | ledger row T2 ([S1 results](../../S1_RESULTS.md)) |
| [NEAR-961](https://linear.app/nearlab/issue/NEAR-961) | Starling response model from the 13 Nov flight logs (exploratory) | S1 | Done | exploratory record, no ledger row |
| [NEAR-962](https://linear.app/nearlab/issue/NEAR-962) | Fit the drone model from a planned-pushes real flight | S1 | Backlog | first fit T63 (STE L1.3, exploratory); the planned-pushes flight still needed |
| [NEAR-963](https://linear.app/nearlab/issue/NEAR-963) | Game core: thousands of games at once, varied arena and zone sizes | S2 | Done | S2 Tasks 2–4; closed with S2 |
| [NEAR-964](https://linear.app/nearlab/issue/NEAR-964) | Check the drone model against the 12 Nov rosbag | S2 | Done | ledger row T5 = FAIL ([record](../../../records/2026-11-15_s2_bag_check_record.md)) |
| [NEAR-965](https://linear.app/nearlab/issue/NEAR-965) | Faster collision filter, checked against CMU's | S2 | Done | ledger row T8 PASS |
| [NEAR-966](https://linear.app/nearlab/issue/NEAR-966) | Scoring tool and scripted opponents | S2 | Done | ledger rows T6, T9 |
| [NEAR-967](https://linear.app/nearlab/issue/NEAR-967) | Plug-in point for a partner's strategy, with a written guide | S2 | Done | [PLUG_IN_YOUR_CODE.md](../../PLUG_IN_YOUR_CODE.md) |
| [NEAR-968](https://linear.app/nearlab/issue/NEAR-968) | Stand-in trainer: prove the training pipe end to end | S2b | Backlog | T14 FAIL; owner decides close or keep |
| [NEAR-969](https://linear.app/nearlab/issue/NEAR-969) | S2 results page | S2 | Done | [S2 results](../../S2_RESULTS.md) |
| [NEAR-970](https://linear.app/nearlab/issue/NEAR-970) | Get NUS's strategy and its rule details | S3 | Done | T35; [NUS port report](../../NUS_PORT_REPORT.md) |
| [NEAR-971](https://linear.app/nearlab/issue/NEAR-971) | Score NUS's strategy: NUS's rules against Starling limits | S3 | Done | T15–T24, T43; NUS route paused (D8) |
| [NEAR-972](https://linear.app/nearlab/issue/NEAR-972) | Games among obstacles and in the construction-site world | S4 | Backlog | order ruled at G0 (R11) |
| [NEAR-973](https://linear.app/nearlab/issue/NEAR-973) | Cross-check the fast simulator against full drone physics in Isaac Lab | S2b | Backlog | T10–T13; T53, T64; owner decides close or keep |
| [NEAR-974](https://linear.app/nearlab/issue/NEAR-974) | Export a strategy and fly it in the AirStack simulator | S5 | Backlog | = STE phase L7 |
| [NEAR-975](https://linear.app/nearlab/issue/NEAR-975) | Train NEAR Lab's own Guard and Strike strategies (research) | Side quest | In Progress | umbrella of the STE learning track ([ste_learning](../../../ste_learning/README.md)) |
| [NEAR-980](https://linear.app/nearlab/issue/NEAR-980) | Wrap the S2 game as an Isaac Lab environment with a PX4-like controller | S2b | In Progress | S2b Tasks 1–8 built; Task 8b not built; owner decides close or keep |
| [NEAR-981](https://linear.app/nearlab/issue/NEAR-981) | Isaac Lab video of the game | S2b | Done | S2b Task 6; VID-1 3-D clips |
| [NEAR-991](https://linear.app/nearlab/issue/NEAR-991) | L0.1 Track set-up: config and test skeleton | STE L0 | Done | no ledger row |
| [NEAR-992](https://linear.app/nearlab/issue/NEAR-992) | L0.7 Process tooling and drills | STE L0 | Done | no ledger row |
| [NEAR-993](https://linear.app/nearlab/issue/NEAR-993) | L0.8 Game spec sheet | STE L0 | Done | no ledger row |
| [NEAR-994](https://linear.app/nearlab/issue/NEAR-994) | L0.9 Tag rule for the study: 1-for-1, nearest pair first | STE L0 | Done | no ledger row |
| [NEAR-995](https://linear.app/nearlab/issue/NEAR-995) | L0.10 Scripted players for the study | STE L0 | Done | no ledger row |
| [NEAR-996](https://linear.app/nearlab/issue/NEAR-996) | L0.11 Screening sweep | STE L0 | Done | T44 INFO |
| [NEAR-997](https://linear.app/nearlab/issue/NEAR-997) | L0.12 Best-response test: is the game worth learning? | STE L0 | Done | T46, T50, T51, T54–T56 INFO; T47, T52 ABORTED |
| [NEAR-998](https://linear.app/nearlab/issue/NEAR-998) | L0.2 Tier 2 speed in contested play | STE L0 | Done | T48 INFO |
| [NEAR-999](https://linear.app/nearlab/issue/NEAR-999) | L0.13 Does tier 2 train at all? | STE L0 | Done | T53 PASS |
| [NEAR-1000](https://linear.app/nearlab/issue/NEAR-1000) | L0.3 STE Guard policy in tier 2 without retraining | STE L0 | Done | T49 INFO |
| [NEAR-1001](https://linear.app/nearlab/issue/NEAR-1001) | L0.4 Side-by-side Starling render | STE L0 | Done | no ledger row |
| [NEAR-1002](https://linear.app/nearlab/issue/NEAR-1002) | L0.5 Starling video look fix | STE L0 | Done | no ledger row |
| [NEAR-1003](https://linear.app/nearlab/issue/NEAR-1003) | L0.14 Crazyflie route check | STE L0 | Done | T45 INFO |
| [NEAR-1004](https://linear.app/nearlab/issue/NEAR-1004) | L0.6 Gate G0 | STE L0 | Done | [G0 report](../../../ste_learning/G0_REPORT.md); rulings in DISCUSSION §14 |
| [NEAR-1005](https://linear.app/nearlab/issue/NEAR-1005) | L1.0 5090 checks and speed re-measure | STE L1 | Done | [5090 checks record](../../../records/2026-11-23_ste_l10_5090_checks_record.md); speed re-measure deferred |
| [NEAR-1006](https://linear.app/nearlab/issue/NEAR-1006) | L1.1 State delay and noise in tier 2 | STE L1 | Done | T62 INFO |
| [NEAR-1007](https://linear.app/nearlab/issue/NEAR-1007) | L1.1b Estimator model shape | STE L1 | Done | T62 INFO |
| [NEAR-1008](https://linear.app/nearlab/issue/NEAR-1008) | L1.1c Second-order estimate error | STE L1 | Backlog | no ledger row |
| [NEAR-1009](https://linear.app/nearlab/issue/NEAR-1009) | L1.2 Drag in tier 2 | STE L1 | Done | T62 INFO; drag value not fitted yet |
| [NEAR-1010](https://linear.app/nearlab/issue/NEAR-1010) | L1.3 Fit delay, noise and drag to real logs | STE L1 | In Progress | T63 EXPLORATORY (flight-log analysis); refit on NEAR-962 |
| [NEAR-1011](https://linear.app/nearlab/issue/NEAR-1011) | L1.4 AirStack-simulator velocity-step logs | STE L1 | Backlog | needs an AirStack-simulator session with the owner |
| [NEAR-1012](https://linear.app/nearlab/issue/NEAR-1012) | L1.5 Tier 2 against the AirStack simulator | STE L1 | Backlog | after L1.4 |
| [NEAR-1013](https://linear.app/nearlab/issue/NEAR-1013) | L1.6 Batched estimator (only if needed) | STE L1 | Backlog | only if L1.3, L1.5 and NEAR-962 show the need |
| [NEAR-1014](https://linear.app/nearlab/issue/NEAR-1014) | L1.7 Same effects in tier 1 | STE L1 | Done | built and reviewed; speed re-measure on an idle GPU |
| [NEAR-1015](https://linear.app/nearlab/issue/NEAR-1015) | L1.8 T46's base policies re-scored on the new tier 2 | STE L1 | Done | T64 INFO |
| [NEAR-1016](https://linear.app/nearlab/issue/NEAR-1016) | L1.9 1v1 best-response read at tag 1.6 m, plus a scripted 1v1 screen also at 1.15 m | STE L1 | Backlog | tooling built; runs on the RTX 5090 |
| [NEAR-1017](https://linear.app/nearlab/issue/NEAR-1017) | L1.10 Tag drawn within 1.5–1.7 m, 3v3, both sides | STE L1 | Backlog | tooling built; runs after L1.9 |
| [NEAR-1018](https://linear.app/nearlab/issue/NEAR-1018) | L1 side track: 1.15 m tests (L1.11–L1.15) | STE L1 | Done | T57–T61 INFO |
