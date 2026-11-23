INTERNAL · copies of the lab's project-tracker (Linear) items. Not needed to read or run anything here.

# Linear update — 2026-11-23, catch-up on S2b and S3, and the STE learning track

Instructions for the Linear agent, in the **nearlab** workspace (team NEAR Lab), project **Isaac Lab Pipeline for
NUS Strategy Training** (P-NEAR-31). Apply every step below. Delete nothing. Use titles, descriptions and comments
exactly as written. Change no existing title. Check Linear before each step: if a status, comment, milestone or issue
is already in place, do not repeat it. Every issue in this project, old and new, is assigned to me (HweHuang Chia),
with **no cycle and no due date**; if Linear adds a cycle to an issue set to In Progress, remove it. Set a milestone
target date only where this file gives one. New issues need no completion date: Linear's own record of when an issue
was set to Done is enough.

Evidence is in the repo https://github.com/AI-DA-STC/AirStack-starling-max2, branch **`development`**, folder
`svg_training/` (`records/LEDGER.md`, `docs/S2B_RESULTS.md`, `docs/WHAT_WE_DID_DAY_BY_DAY.md`,
`docs/claude/HANDOFF.md`, `ste_learning/PLAN.md`, `ste_learning/WORK_BREAKDOWN.md`). Write "ledger row T8", never
"#T8". Every result below was observed in the training simulator, except T63, which is an analysis of real flight
logs; nothing here is a flight result.

## Part 1 · Set to Done, each with its comment

**NEAR-970: Get NUS's strategy and its rule details.** (milestone S3 · NUS strategy scored)

> 2026-11-23. Done. NUS shared its code (not trained checkpoints); STE installed the branch NUS named as the most
> recent on the lab's RTX 5090 workstation on 17 Nov, ledger row T35 (65 of NUS's 66 tests pass; NUS confirmed the
> one failure is an out-of-date test). The target said "on the laptop": the code stays on the 5090 by the owner's
> decision; the laptop works from the lab's own converted policies and settings files. NUS's game has no metres or
> seconds and NUS said to scale it to the arena, so STE chose a scale for the hangar. Details: `svg_training/docs/WHAT_WE_DID_DAY_BY_DAY.md` §1–3.

**NEAR-971: Score NUS's strategy: NUS's rules against Starling limits.** (milestone S3 · NUS strategy scored)

> 2026-11-23. Done, scored on the hangar set-up only (not per arena size). NUS's game was copied to PyTorch and
> checked against the original (ledger row T15 PASS), and STE-trained NUS-code policies converted (ledger rows T16–T17
> PASS); six tests then brought the game to Starling
> conditions one step at a time (ledger rows T18–T20 and T22–T24 INFO; T21 ABORTED, over time): the safety filter and
> free height break NUS's push-blocking, so the Strike team gets through far more often, and Isaac Lab's physics
> drones agree with the fast simulator. Retraining in STE conditions stopped at stage 5.1 (ledger row T43 FAIL: one
> seed of three missed the learner check and one scripted range) and the NUS route is paused (lead call D8, 20 Nov);
> STE's own learning track continues under NEAR-975.

**NEAR-981: Isaac Lab video of the game.** (milestone S2b)

> 2026-11-23. Done. Seven scripted games rendered headless on Isaac Lab Starlings (2 v 1 and 5 v 3, lab to large
> arenas; two in the construction-site world and one among blocks and columns, all as backdrops), captioned "training simulator", in
> `svg_training/docs/media/s2b_*` (S2b Task 6). Tool VID-1 then replays a run's key games in 3-D with the Starling's
> own look from a top and a 3-D camera (MP4 + GIF): L0.11's scripted games and the L0.12 trained teams, shown in
> `svg_training/ste_learning/G0_REPORT.md`. Clips are pictures, with no ledger row.

## Part 2 · Comment, keep the status

Each issue below should already have the status named in brackets; if Linear shows another, set it to that one.

**NEAR-980: Wrap the S2 game as an Isaac Lab environment with a PX4-like controller.** (status stays In Progress)

> 2026-11-23. Built (S2b Tasks 1–8): rigid-body Starlings in Isaac Lab 2.3.2 flown by a copy of PX4 1.14's control
> loops with the drone's own gains (yaw-rate gains SIM-ONLY, owner ruling), scored on both simulators; it now carries
> the STE track's Isaac Lab work (ledger rows T53, T62, T64). Its "Done when" target is not fully met: the two physics
> worlds differ by 1.15 mm after 1 s against a 1 mm limit (ledger row T10 FAIL, accepted by the owner); step tests
> T11 FAIL; scripted games T13 FAIL (Strike drones pass over or under Guards; the owner kept this, option (a)). Speed
> T12 INFO: up to 262,190 drone-steps/s on the laptop, above S0's 20,000 line. The registered Isaac Lab task (Task 8b)
> is not built. Results: `svg_training/docs/S2B_RESULTS.md`. **Owner decides:** close as built, or keep open until
> Task 8b is built.

**NEAR-968: Stand-in trainer: prove the training pipe end to end.** (status stays Backlog)

> 2026-11-23. Result: ledger row T14 FAIL. The pipe worked end to end on Isaac Lab drones (2 seeds trained 100 M
> game-steps each, logged to TensorBoard, scored), but the Guards learned almost nothing: the gate asked for 20 more
> holds per 100 games than random Guards, and the seeds held 0 per 100 against straight Strikes and 7 and 13 per 100
> against flanking ones; seed 3 was not run (it cannot change the verdict). Since then the STE track's trainer showed
> training works on the same pipe, Isaac Lab included (ledger row T53 PASS: trained Guards hold 832 of 1,000, parked
> Guards 538). **Owner decides:** close as Done with the failed result, or keep open (seed 3 on the RTX 5090, or a new
> stand-in plan).

**NEAR-973: Cross-check the fast simulator against full drone physics in Isaac Lab.** (status stays Backlog)

> 2026-11-23. Results so far: ledger rows T10 FAIL (accepted), T11 FAIL, T12 INFO, T13 FAIL (scripted games: hold
> rates differ by more than 10 per 100 games in 36 of 60 cells, mostly because Strike drones pass over or under Guards
> on the physics drone). The trained players move between the two simulators far better: the same training on both
> gives 832 and 836 holds of 1,000 (ledger row T53, STE task L0.13), and the 1.6 m trained teams re-scored on Isaac
> Lab shift by −33 to +47 of 1,000 per cell, in both directions (ledger row T64, STE task L1.8). **Owner decides:**
> close as Done with the failed T13 result, or keep open for the cross-checks of later STE phases.

**NEAR-962: Fit the drone model from a planned-pushes real flight.** (status stays Backlog)

> 2026-11-23. A first fit from the 13 Nov flight log is done (ledger row T63, EXPLORATORY, STE task L1.3): while
> hovering, the drone's position estimate differs from the motion-capture position by about 1 cm (σ 0.0099 m, lasting
> about 1.2 s), its velocity by about 2 cm/s, its tilt by at most 0.003 rad; while moving the position spread reaches
> 2.5 cm. The planned-pushes flight is still needed. It should record: the motion-capture time on a clock synced with
> PX4; ULog at the highest rate for vehicle_local_position, vehicle_attitude, vehicle_visual_odometry and
> estimator_innovations; an independent reference if possible; hovers of at least 5 min on both drones; moving legs
> at known speeds; each log's checksum and EKF2_EV_DELAY / EKF2_EV_CTRL.

**NEAR-959: Measure training speed on the training workstation.** (status stays Backlog)

> 2026-11-23. The laptop's training speed with both teams playing is measured (ledger row T48, STE task L0.2): 3 v 3,
> fast simulator 51,000–208,000 and Isaac Lab 10,000–67,000 game-steps/s, Isaac Lab about 5× slower. On the RTX 5090
> the machine checks are done (23 Nov, STE task L1.0: same game results as the laptop, 2,213 tests pass; record
> `svg_training/records/2026-11-23_ste_l10_5090_checks_record.md`); its speed re-measure runs on an idle GPU with the
> STE L1.7 speed check, and closes this issue.

**NEAR-972: Games among obstacles and in the construction-site world.** (status stays Backlog)

> 2026-11-23. Order ruled by the owner at gate G0 (22 Nov, ruling R11): open arena until a trained team passes the
> opponent panel, then random blocks and columns, then the construction-site world. The STE learner (phase L3) is
> designed so obstacles can be added without a new network.

**NEAR-974: Export a strategy and fly it in the AirStack simulator.** (status stays Backlog)

> 2026-11-23. Unchanged. This is phase L7 of the STE learning track (milestone STE L7 · AirStack side): specs written
> in `svg_training/`, the build and the AirStack-simulator games by an AirStack session, with the owner's approval.

## Part 2b · Set to In Progress, with its comment

**NEAR-975: Train NEAR Lab's own Guard and Strike strategies (research).** Keep its milestone (Side quest). Set status **In Progress** (no cycle), with
this comment:

> 2026-11-23. This issue is now the umbrella of STE's own learning track (since 20 Nov 2026), planned in ten phases,
> each a milestone of this project: STE L0 · Game definition and feasibility (done, gate G0 ruled 22 Nov), STE L1 ·
> Drone model (in work), STE L2 · Game rules in the training copy, STE L3 · Learner, STE L4 · Evaluation suite and
> gates, STE L5 · League self-play, STE L6 · QC and export, STE L7 · AirStack side, STE L8 · Real flight, STE L9 ·
> Documentation. Plan: `svg_training/ste_learning/PLAN.md`. Nothing trained into a strategy yet; nothing flown.
> Terms used in these issues: "tier 1" = the fast training simulator, "tier 2" = Isaac Lab's physics drones;
> "ledger row Tnn" = a numbered test result in `svg_training/records/LEDGER.md`; G0 = the gate the owner ruled at the
> end of L0, with numbered rulings (R11) and decisions (D8, D9); P5 = the approved AirStack-simulator logs; "5090" =
> the lab's RTX 5090 training workstation.

## Part 2c · Set a milestone date

Milestone **S3 · NUS strategy scored**: after Part 1 both its issues are Done (100 %). Set its target date to
**2026-11-20**, the day the NUS route was paused (lead call D8). S2b stays open (NEAR-968, NEAR-973 and NEAR-980 are
not Done) and gets no date.

## Part 3 · Create ten milestones, after the existing ones, in this order

| Milestone | Description | Target date |
|---|---|---|
| **STE L0 · Game definition and feasibility** | Which game the track trains, whether it is worth learning, and whether Isaac Lab can train it and at what cost. Ended at gate G0, ruled by the owner on 22 Nov 2026. | 2026-11-22 |
| **STE L1 · Drone model** | Make the training drone realistic: the flight estimator's error, drag, a fit to real flight logs and a comparison with the AirStack simulator. Main reads at tag 1.6 m, with a 1.15 m side track. | none |
| **STE L2 · Game rules in the training copy** | The rules chosen at G0 in the training game: landing obstacles, drone loss and the second filter option with its convergence check. No issues yet: they are added when the phase starts. | none |
| **STE L3 · Learner** | The learner: the observation, an attention encoder, one shared actor per team, a team critic and PPO. No issues yet: they are added when the phase starts. | none |
| **STE L4 · Evaluation suite and gates** | The scoring suite and its pass/fail limits, calibrated on known players; the owner approves the limits. No issues yet: they are added when the phase starts. | none |
| **STE L5 · League self-play** | League training: pilots, then runs of record with three seeds. No issues yet: they are added when the phase starts. | none |
| **STE L6 · QC and export** | Scoring, cross-checks and the policy file handed over. No issues yet: they are added when the phase starts. | none |
| **STE L7 · AirStack side** | A trained strategy run in the AirStack simulator (real PX4 and EKF2); specs here, build by an AirStack session. No issues yet: they are added when the phase starts. | none |
| **STE L8 · Real flight** | A real 1 v 1 on two Starlings, with the owner's approval. No issues yet: they are added when the phase starts. | none |
| **STE L9 · Documentation** | Status, records, the results page and standards updates after each ruling; runs alongside the other phases. No issues yet: they are added when the phase starts. | none |

## Part 4 · Create issues

Each issue below: project **Isaac Lab Pipeline for NUS Strategy Training**, the milestone in its heading, the status
given, assigned to me, no cycle, no due date. Put the text in the issue body. No issues are created for STE L2–L9 now:
they are added when each phase starts.

### STE L0 · Game definition and feasibility (14 issues, all Done)

Create them in the order listed (the order the work was done, not the task numbers).

| Title | Body |
|---|---|
| **L0.1 Track set-up: config and test skeleton** | The track's settings file `configs/ste_learning.toml`, its loader and tests (unknown keys and unlabelled values are refused). Done 20 Nov 2026; independent QC closed every finding. No run, no ledger row. |
| **L0.7 Process tooling and drills** | One shared GPU-pause log, a status helper, the trainer's resume and stop rules as tests, a wake-up drill and a resume drill. Laptop part done 20–21 Nov; RTX 5090 part done 23 Nov (`records/2026-11-23_ste_l10_5090_checks_record.md`). No ledger row. |
| **L0.8 Game spec sheet** | One page, `ste_learning/GAME_SPEC.md`, and `configs/ste_game.toml`: every game value with its status (FIXED, MEASURED, PROPOSED, OPEN) and source. Done 21 Nov; QC passed. No ledger row. |
| **L0.9 Tag rule for the study: 1-for-1, nearest pair first** | A Guard and a Strike drone closer than the tag distance both leave, nearest pair first; off by default, so earlier games are unchanged. Tests: drones 1.59 m apart tag at 1.6 m, 1.61 m apart do not. Done 21 Nov; QC passed. No ledger row. |
| **L0.10 Scripted players for the study** | New scripted Guards (parked at the centre, parked on a ring) and Strikes that use height and numbers (enter high or low, one sacrifices, all converge). Done 21 Nov; QC passed. No ledger row. |
| **L0.11 Screening sweep** | Scripted Guards against scripted Strikes, 369 cells × 1,000 games. At the base game (3 v 3, tag 1.6 m) scripted Guards hold 81 of 100 games; at tags 1.2 and 1.4 m 65 and 67. Shortlist: 1.6, 1.4 and 1.2 m. Ledger row T44 INFO, 0.305 GPU-h. |
| **L0.12 Best-response test: is the game worth learning?** | Short trainings of each side against the best script. At tag 1.6 m both trained teams beat the script (Strike +444 reaches per 1,000 games, Guard +105 holds): worth learning. At 1.15 m (the filter's 1.10 m keep-out plus 5 cm) both learned but stayed below the scripts (Guard 572 v 645 holds, Strike 134 v 355 reaches), and teams trained at 1.6 m do not carry over to 1.15 m. Ledger rows T46, T50, T51, T54–T56 INFO; T47, T52 ABORTED (stopped at the time cap). |
| **L0.2 Tier 2 speed in contested play** | Training speed with both teams playing, laptop, 3 v 3: fast simulator 51,000–208,000, Isaac Lab 10,000–67,000 game-steps/s; Isaac Lab about 5× slower. Ledger row T48 INFO, 0.294 GPU-h. |
| **L0.13 Does tier 2 train at all?** | The same Guard training on both simulators, 302 M game-steps each: Isaac Lab Guards hold 832 of 1,000 (parked Guards 538), fast-simulator Guards 836; Isaac Lab took about 5× the GPU time (1.29 v 0.24 GPU-h). Ledger row T53 PASS. |
| **L0.3 STE Guard policy in tier 2 without retraining** | The Guard policy trained on the fast simulator, played on Isaac Lab drones unchanged: 856 holds of 1,000 against 831 on the fast simulator. Ledger row T49 INFO, 1.240 GPU-h. |
| **L0.4 Side-by-side Starling render** | The Isaac Lab Starling beside the AirStack simulator's: found a grey physics box drawn over every drone in the clips since S2b; one-line fix. 0.028 GPU-h; no ledger row. |
| **L0.5 Starling video look fix** | Clips keep the Starling's own look, with the team shown by a ring (the owner chose the ring, decision D9). No ledger row. |
| **L0.14 Crazyflie route check** | With a Crazyflie-like lag (0.48–0.56 s instead of the Starling's 0.15 s) the STE Guard policy holds 768–791 of 1,000 against 831, and games where drones come within 1.0 m rise from 7 to 101–149. Page `ste_learning/CRAZYFLIE_ROUTE.md`. Ledger row T45 INFO, CPU only. |
| **L0.6 Gate G0** | The owner ruled gate G0 on 22 Nov 2026: a 1-for-1 tag, 1.6 m first and a 1.15 m side track; zone 1.6 m; 3 v 3 in a 6.5 m arena; 120 s games; main training in Isaac Lab; 13 GPU-h for L1 and L2. L0 used 13.77 of its 19 GPU-h. Record: `ste_learning/DISCUSSION_2026-11-19_20.md` §14. |

### STE L1 · Drone model (14 issues)

| Title | Status | Body |
|---|---|---|
| **L1.0 5090 checks and speed re-measure** | Done | The RTX 5090 gives the same game results as the laptop; drills pass; its test suite 2,213 passed, 0 failed (23 Nov). Record `records/2026-11-23_ste_l10_5090_checks_record.md`, no ledger row. The speed re-measure is deferred to an idle GPU (NEAR-959). |
| **L1.1 State delay and noise in tier 2** | Done | A delayed, noisy state fed to the Isaac Lab drone's controller, off by default; reshaped by L1.1b. Isaac Lab checks in ledger row T62 INFO. |
| **L1.1b Estimator model shape** | Done | The estimate error as slow, correlated noise per quantity (not a delay; attitude never delayed), seeded per game. Isaac Lab tests 7 pass, no measurable speed cost. Ledger row T62 INFO, 0.327 GPU-h. |
| **L1.1c Second-order estimate error** | Backlog | The real hover error swings back (T63), so a second-order error term fits better; add it, off by default, fitted from the NEAR-962 logs; plus a test that catches a flipped height sign in the log reader. |
| **L1.2 Drag in tier 2** | Done | A linear drag force on the Isaac Lab drone, off by default; checked in ledger row T62. The drag value is not fitted yet (L1.3). |
| **L1.3 Fit delay, noise and drag to real logs** | In Progress | First fit from the 13 Nov flight log, ledger row T63 (EXPLORATORY, flight-log analysis): while hovering, position error about 1 cm, velocity about 2 cm/s, tilt at most 0.003 rad, each lasting 1–2 s. Drag and the stage-1 limits are still to fit; the values are refitted on the NEAR-962 flight. |
| **L1.4 AirStack-simulator velocity-step logs** | Backlog | Velocity steps through the AirStack simulator's real PX4 and EKF2, about 1 h of simulator time; approved by the owner (P5); needs a session with the owner. |
| **L1.5 Tier 2 against the AirStack simulator** | Backlog | Isaac Lab drone against L1.4's steps, with and without the estimate error, each difference named. Needs the owner's ruling on SIM-ONLY values. |
| **L1.6 Batched estimator (only if needed)** | Backlog | A simplified batched estimator, only if L1.3, L1.5 and NEAR-962 show the simple error model is not enough. |
| **L1.7 Same effects in tier 1** | Done | The fast simulator gets the same estimate error, off by default, with a switch for what the commander copy reads. Built and reviewed by two code reviewers (23 Nov); no ledger row. Its speed cost is not settled: re-measure on an idle GPU. |
| **L1.8 T46's base policies re-scored on the new tier 2** | Done | The 1.6 m trained teams re-scored on Isaac Lab: per-cell shifts −33 to +47 of 1,000 against the fast simulator, both directions; with the measured estimate error no change was detected (this test cannot see shifts under about 40–60 games). Ledger row T64 INFO, 0.598 GPU-h. |
| **L1.9 1v1 best-response read at tag 1.6 m, plus a scripted 1v1 screen also at 1.15 m** | Backlog | Tooling built and reviewed (spec `ste_learning/drafts/L1_9_10_SPEC.md`); the runs are next on the RTX 5090; cap 1.6 GPU-h. |
| **L1.10 Tag drawn within 1.5–1.7 m, 3v3, both sides** | Backlog | Tooling built and reviewed (same spec); the runs follow L1.9; cap 1.7 GPU-h. |
| **L1 side track: 1.15 m tests (L1.11–L1.15)** | Done | Side track, added with the owner's go on 22 Nov: why the trained teams fall short at tag 1.15 m. (L1.11) A Strike team trained against the field Guards at 1.6 m reaches 277 of 1,000, level with the straight script's 284: the opponent, not the tag, held it back (ledger row T58). (L1.12) The 1.6 m Guard team holds 913–953 of 1,000 against all six Strike scripts (T57). (L1.13) A 30 s training clock lifts the 1.15 m Strike team to 199 of 1,000 against 145, just clearing the margin set before the run; a longer discount alone changed nothing (T59). (L1.14) Told time is short, it attacks earlier and reaches 152 v 103, still below the best script's 355 (T60). (L1.15) The results hold for response delays 0–0.30 s (T61). All INFO; about 2.6 GPU-h in all. |

## Part 5 · Write the sync record

Write a Markdown file named `2026-11-23-linear-sync-record.md`. State only what Linear now holds:

- every issue of the project: NEAR id, title, milestone, status, assignee, cycle, due date;
- each comment added here, and whether it was added now or already present;
- every milestone, old and new, with target date and progress;
- anything not applied, and why.

**Snapshot.** From this record the repo writes a new snapshot, `snapshots/2026-11-23-project-plan-linear.md`, so the
record must list every issue and milestone, not only the ones changed here.
