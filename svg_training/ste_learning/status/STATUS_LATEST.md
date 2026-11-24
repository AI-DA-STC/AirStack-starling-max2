INTERNAL · the latest status of STE's own learning track and the NUS port, overwritten at every update by the `train-status` skill · [../README.md](../README.md); the history: [LOG.md](LOG.md)

**Status, 2026-11-24 18:20 (+08:00) (event: owner rulings R29–R33, L3 slice 2 merged, flight logs read)** · GPU not re-read for this update · RTX 5090

**Main track:** L2 done; L3 slice 2 merged, run 0 for the skills route next · **Side track:** none open

## Watch

![The L1.10 Strike team (tag drawn 1.5–1.7 m, estimate error) reaching the zone](../../records/evidence/2026-11-24_ste_l110/strike/base_tagdraw_strike_game0_reach.gif)

Latest clip kept from the 07:30 digest (L1.10 Strike team); the tasks below produced numbers and tables, no new clip for this page.

## Plain summary of what finished since 13:30

1. **L2.6 tier 1 v tier 2 under the new rules** (T71, INFO, 0.145 GPU-h, two reviewers) ([record](../../records/2026-11-24_ste_l26_tier12_record.md)): tier 1 agrees with tier 2 for scripted play at 1.6 m and at 1.15 m without option B (40 of 42 cell readings). Option B at 1.15 m lowers mark_edge v straight on both tiers. This is the evidence for P2, which the owner deferred (R31).
2. **CLIP-T2 side task:** the tier-2 clip script drew its starts on the GPU (CUDA); fixed (`record_games` takes `starts=`); the L0.13 clip caption is corrected. Run numbers are unaffected.
3. **Flight logs read (owner's 24 Nov logs).** [Survey](../../docs/notes/2026-11-24_flight_logs_survey.md): the figure-eight flight is a held-out check only; the planned-pushes flight (NEAR-962) is still needed.
   - **Figure-eight held-out check** (T72, INFO, two reviewers) ([record](../../records/2026-11-24_fig8_heldout_record.md)): at 2–3 m/s tier 1's exploratory model flies about half to two thirds of the real speed, likely its fitted acceleration limit (1.72 m/s²) against about 2.6 m/s² measured. Game speeds are inside the fitted range, so nothing is re-scored. NEAR-962 should add fast pushes and turns reaching 2–4 m/s².
   - **Crazyflie summary** ([note](../../docs/notes/2026-11-24_crazyflie_reports_summary.md), one reviewer): lag about 0.56 s with the PID controller v 0.08–0.10 s with Mellinger (a co-occurrence, not a proven cause); commanded gaps fall below the show's own 0.80 m separation minimum in 73 of 78 close events.
4. **L3 slice 2 merged** ([design](../drafts/L3_SLICE2_DESIGN.md)): two-level learner (`TwoLevelIPPO`) with per-head ratios, entropy and KL, p(free) = 0.5 start, skill lists in the checkpoint, the driver wired, the skills pilot wired, and the held-command arm script. QC ran once per step. Slice 1 merged earlier.

**Owner rulings R29–R33** (end of [DISCUSSION](../DISCUSSION_2026-11-19_20.md)):
- R29: 1v1 training skipped (the scripted 1v1 stays the demo).
- R30: "Team strategy, with individual drone skills which can adapt to the opponent's strategy": a two-level choice, a team head and a drone head.
- R31: P2 option B deferred; the even split stays the default.
- R32: landing off in the L3–L6 pipeline check.
- R33: no flight with the filter off: the planned-pushes flight flies one drone alone with the filter on.

## Phases

| Phase | What | Math library | Simulator | Where it stands |
|---|---|---|---|---|
| L1 Drone model | estimate error, drag, fits, speed, tag reads | PyTorch | fast engine; Isaac Lab; AirStack simulator (logs) | done except L1.6 (waits on L1.3 + NEAR-962); L1.9 training dropped (R29) |
| L2 Game rules in training | option B, landing, drone loss, team sizes | PyTorch | fast engine; Isaac Lab | done (L2.1–L2.6); P2 deferred (R31), landing off (R32) |
| L3 Learner (two routes) | pure RL and the mixed route, one learner | PyTorch | fast engine pilot, Isaac Lab smoke | slices 1 and 2 merged; step 4b (run 0, skills route) next, then slice 3 |
| L4–L6 pipeline check | scoring suite, one seed per route, export | PyTorch | both | not started; cap 20 GPU-h (R23) |

## Phase L1, L2 and L3, task by task

| Task | Where it stands |
|---|---|
| L1.0 5090 checks | done (23 Nov) |
| L1.1, L1.1b, L1.2, L1.3 drone model and fit | done (T62, T63) |
| L1.4 AirStack-simulator step logs | done (T68, INFO) |
| L1.5 training drone v AirStack simulator | done (T69, INFO) |
| L1.6 SIM-ONLY values decision | waits on L1.3 + NEAR-962 |
| L1.7 same effects in tier 1 | done (T65) |
| L1.8 T46 players on tier 2 | done (T64) |
| L1.9 1v1 read | screen done (T66); training dropped (R29) |
| L1.10 tag drawn 1.5–1.7 m | done (T67) |
| L1.11–L1.15 side track | done (T57–T61) |
| L2.1 filter option B, L2.3 landing drones, L2.4 drone loss and drawn team sizes | built, off by default |
| L2.5 parked-Guard control and scripted opponents | done (T70, INFO) |
| L2.6 tier 1 v tier 2 under the new rules | done (T71, INFO) |
| Figure-eight held-out check of the drone model | done (T72, INFO) |
| L3 slice 1 | merged |
| L3 slice 2 two-level learner, driver, skills pilot, held-command arm | merged |
| L3 step 4b run 0, skills route (skills Strike v guard_parked_centre; PASS at 900 or more of 1,000; lead's call) on branch `l3-run0` | next |
| L3 slice 3 absent-drone mask, opponent pool, tier 2 wiring | after step 4b |

## Other workstreams

| Work | Where it stands |
|---|---|
| Process | models by role and scaled reviews in CLAUDE.md; job/agent watchdog every 20 min |
| Documentation | HANDOFF §0 and this status updated 18:20; flight-log survey and Crazyflie summary notes |

**Next** (no ruling needed): L3 step 4b (run 0 for the skills route) on `l3-run0`; then slice 3 (absent-drone mask, opponent pool, tier 2 wiring); then the pipeline-check pilots.

**Waiting on you:**
1. **The planned-pushes flight (NEAR-962):** one drone alone, filter on, single-axis pushes from rest at 0.25–1.0 m/s plus a few fast pushes and turns; record `/svg/drone_N/teleop_command`; note the config, the PX4 build and `MPC_XY_VEL_MAX`.
2. **A look at the Crazyflie show's commanded gaps** below its own 0.80 m minimum, before the next Crazyflie flight.

No other decision is open.

**Usage:** since 13:30: GPU 0.145 GPU-h (L2.6); the figure-eight check and the flight-log notes ran on the CPU; Opus builders and Sonnet reviewers (two each for T71 and T72, one for the Crazyflie summary, QC once per L3 step); budget_l1_l2 (phases L1 + L2): used 4.439 of 13.0 GPU-h (own rows 0.899, carried 3.540) (`scripts/ste_job.py status`). Checks: full suite on `fa549048` 2,672 passed, 1 failed (a literals rule); fixed in `9a982c69` and re-run. Advisor: Fable 5.2 (advisor tool) at the morning's gate and the L2.5 recommendation; overloaded at the slice 2 fork, so the slice 2 design went to two reviewers instead; the builders called it at their own forks.

**Ready to push.** 18 commits on `development` ahead of `origin/development` (counted against GitHub at 18:25, this status commit included); push from GitHub Desktop. `main` unchanged.
