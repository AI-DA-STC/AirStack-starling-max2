INTERNAL · the latest status of STE's own learning track and the NUS port, overwritten at every update by the `train-status` skill · [../README.md](../README.md); the history: [LOG.md](LOG.md)

**Status, 2026-11-24 13:30 (+08:00) (event: three tasks finished, L1.4, L1.5, L2.5)** · GPU 1 % / 32 W / 1.1 GB of 32.6 GB · 0 training processes · RTX 5090

**Main track:** L1 tasks done except L1.6 (waits on L1.3 + NEAR-962) and L1.9 training (held); L2.1–L2.5 done, L2.6 next · **Side track:** none

## Watch

![The L1.10 Strike team (tag drawn 1.5–1.7 m, estimate error) reaching the zone](../../records/evidence/2026-11-24_ste_l110/strike/base_tagdraw_strike_game0_reach.gif)

Latest clip (from the L1.10 Strike team, 07:30 digest); L1.4, L1.5 and L2.5 produced numbers and tables, no new clip.

## Plain summary of the three finished tasks

1. **L1.4 AirStack-simulator step logs** (T68, INFO): 36 of 36 velocity steps flown in the AirStack simulator ([record](../../records/2026-11-24_ste_l14_steps_record.md)). Corrected reading: the heights come from the simulator's PX4 clock, which runs about 2.5 times fast; they are not a descent limit.
2. **L1.5 training drone v AirStack simulator** (T69, INFO, 0.012 GPU-h): in tier 2 with the AirStack simulator's SIM-ONLY airframe, the training drone is within the simulator's per-step spread in 187 of 189 readings. The 0.05 s delay and the estimate error cannot be resolved here (about 0.1 s resolution). The L1.6 decision still needs L1.3 and NEAR-962 ([record](../../records/2026-11-24_ste_l15_compare_record.md)). Two reviewers.
3. **L2.5 parked-Guard control and scripted opponents under the new rules** (T70, INFO, 0 GPU-h, 46 min CPU; all 12 controls) ([record](../../records/2026-11-24_ste_l25_screen_record.md)). Two reviewers. Readings:
   - The parked-Guard risk was not seen with scripted Strikes: still Guard 432 v mark_edge about 805 in the worst cell. The tag raises the parked hold in 23 of 24 cells.
   - **Option B could not be tested at the 1.6 m tag with scripted play.** With the tag off it changes 11,429 of 12,000 games and removes most parked-Guard blocking (331 to 171, 752 to 86). Option B is 5.3 times slower on the CPU in long games.
   - Landing changes 2 of 30 cells, both against strike_low; the vertical part is not fitted.

**Also today:** Guard fixes in `scripts/record_steps.sh` (`f7e87089`, `452b260d`), each reviewed once. L3 note v2 (`ste_learning/drafts/L3_TWO_ROUTES_DESIGN.md`) after two design reviewers and the advisor.

## Phases

| Phase | What | Math library | Simulator | Where it stands |
|---|---|---|---|---|
| L1 Drone model | estimate error, drag, fits, speed, tag reads | PyTorch | fast engine; Isaac Lab; AirStack simulator (logs) | done except L1.6 (waits on L1.3 + NEAR-962) and L1.9 training (held) |
| L2 Game rules in training | option B, landing, drone loss, team sizes | PyTorch | fast engine; Isaac Lab | L2.1–L2.5 done; L2.6 next |
| L3 Learner (two routes) | pure RL and the mixed route, one learner | PyTorch | fast engine pilot, Isaac Lab smoke | note v2 written (two design reviewers and the advisor); first slice next |
| L4–L6 pipeline check | scoring suite, one seed per route, export | PyTorch | both | not started; cap 20 GPU-h (R23) |

## Phase L1 and L2, task by task

| Task | Where it stands |
|---|---|
| L1.0 5090 checks | done (23 Nov) |
| L1.1, L1.1b, L1.2, L1.3 drone model and fit | done (T62, T63) |
| L1.4 AirStack-simulator step logs | done (T68, INFO) |
| L1.5 training drone v AirStack simulator | done (T69, INFO) |
| L1.6 SIM-ONLY values decision | waits on L1.3 + NEAR-962 |
| L1.7 same effects in tier 1 | done (T65) |
| L1.8 T46 players on tier 2 | done (T64) |
| L1.9 1v1 read | screen done (T66); training held |
| L1.10 tag drawn 1.5–1.7 m | done (T67) |
| L1.11–L1.15 side track | done (T57–T61) |
| L2.1 filter option B, L2.3 landing drones, L2.4 drone loss and drawn team sizes | built, off by default |
| L2.5 parked-Guard control and scripted opponents | done (T70, INFO) |
| L2.6 tier 1 v tier 2 under the new rules | next |

## Other workstreams

| Work | Where it stands |
|---|---|
| Process | models by role and scaled reviews in CLAUDE.md; job/agent watchdog every 20 min |
| Documentation | HANDOFF §0 and this status updated 13:30; WORK_BREAKDOWN L2 build notes |

**Next** (no ruling needed): L3 first slice build (tier 1: skill dispatch + categorical head + tests); L2.6 spec (tier 1 v tier 2 under the new rules).

**Waiting on you** (one-word answers):
1. **1v1:** skip (lead's choice) / screen variants.
2. **L3 choice:** per team (lead's choice) / per drone.
3. **P2 option B: not ready to rule.** L2.5 could not measure it at 1.6 m; its convergence gate (PLAN L2 row) has no record yet; the drones fly the even split today (option B in flight needs the CMU proposal P6); and the L2.1 wall shortfall (0.39 m v 0.97 m) is not shown by L2.5. Lead proposes keeping the even split as the default and offering a 1.15 m CPU screen (0 GPU-h) when the 1.15 m main training nears.
4. **P7 landing:** lead proposes landing off in the L3–L6 pipeline check (it needs observation v0.3 so live drones can see a landing drone; v0.3 comes to you with the main training). Drawn sizes and drop-outs are not screened and not asked now.

**Usage:** since 07:30: GPU 0.012 GPU-h (L1.5); L2.5 0 GPU-h, 46 min CPU; L1.4 flown in the AirStack simulator (no GPU hours booked); Opus builders and Sonnet reviewers (two each for T69 and T70, one each for the Guard fixes); budget_l1_l2 **4.271 of 13.0 GPU-h** (own rows 0.731, carried 3.540; `scripts/ste_job.py status`). Checks: full suite 2,458 passed on `3103d4d0`; a second run on `d01bf39e` in progress. Advisor: Fable 5.2 on L3 note v2.

**Ready to push.** 49 commits on `development` (ahead of `origin/development`); mirror state not re-checked for this update; push from GitHub Desktop. `main` unchanged.
