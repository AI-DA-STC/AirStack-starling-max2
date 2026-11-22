INTERNAL · DRAFT of 22 Nov 2026 for gate G0 (PLAN row L0.6, [G0_DECISION](../G0_DECISION.md) row 15). The costed plan for
phases L1–L9 that the lead brings to the walk-through. Budget for L1 + L2 ruled 13 GPU-h (owner, 22 Nov; [DISCUSSION §14](../DISCUSSION_2026-11-19_20.md#14-gate-g0-rulings-owner-22-nov-2026));
nothing else here is approved, and every hour is an estimate built from the measured rates below. Every rate was observed in the training simulator; nothing here is a flight result.

# L1–L9 costed plan (draft for gate G0)

*GPU-h*: one hour of the shared GPU. *B*: a billion game-steps (one game-step = one tick of one game).
*Tier 1*: the fast training simulator. *Tier 2*: Isaac Lab with the Starling as a physics drone.

## 1. One-screen summary

**The plan follows D3** (owner, 20 Nov: train in Isaac Lab, the fast engine for quick experiments and debugging only;
G0 recommendation 4: keep D3). Tier 2 trains the learner pilot, the league pilot and the runs of record. Tier 1 runs the
quick experiments (best-response reads, recipe tests) and the large scoring tables. **A12, RULED (owner, 22 Nov 2026):**
the fast engine (tier 1) is used for quick experiments and checks, main training in Isaac Lab: the training reads L1.9,
L1.10, L1.11, L1.13, L2.7, L2.8, L3.5 and L5.3 (about 5× cheaper, and comparable with L0's tier 1 numbers) and the tier-1
scoring L4.3, L6.1 and L6.2.

Other G0 rulings used (owner, 22 Nov 2026, all as the lead recommended): 3v3 main size, 1v1 trained and tested in L1, tag drawn within ±0.1 m in training,
Crazyflies first at Starling metres, Starling 1v1 demo, physical intercept in simulation only, 3 seeds of record.

The tag is 1.6 m for building the pipeline (G0 ruling R1, option (d)); the 1.15 m side track runs in L1–L2: L1.11 (Strike team trained against guard_field at 1.6 m, which separates the
opponent from the tag), L1.12 (T46's 1.6 m Guard team scored against every Strike script) and L1.13 (the
shorter-training-clock Strike run at 1.15 m); 1.15 m main training follows L2. At 1.6 m each trained team was scored against one
opponent: the Strike team fails against a second (85 of 1,000 against field Guards), and the Guard team is untested
against other Strike scripts ([T56](../../records/2026-11-22_ste_l012d_cross_tag_record.md)).
Tag 1.4 m has the same timings (T46). Tag 1.15 m is in section 4.

| Phase | Low – high GPU-h | Planning figure | Main cost |
|---|---|---|---|
| L1 Drone model, with the 1v1 and varied-tag reads | 3.3 – 6.8 (2.6 – 6.1 before L1.13) | 4.7 | two tier 1 best-response reads |
| L2 Game rules in the training copy | 1.7 – 3.9 | 2.5 | best-response read under the full rules |
| L3 Learner | 3.4 – 6.7 | 5 | tier 2 learner pilot |
| L4 Evaluation suite and gates | 0.7 – 4.5 | 2 | calibration on tier 2 |
| L5 League self-play, 3 seeds of record on tier 2 | 33 – at least 100 | 63 | runs of record (26–83) |
| L6 QC, export, intercept in simulation | 4.3 – 27 | 10 | scoring the runs of record on tier 2 |
| L7 AirStack side, L8 real flight, L9 docs | 0 (+ about 3 h of AirStack simulator time) | 0 | — |
| **Total** | **46 – at least 149** before L1.13 (about 47 – at least 150 with it) | **87** (about 88 with L1.13) | |

- **What drives the range:** the length of a league run (2–5 B game-steps per seed, PROPOSED) at the tier 2 rate
  (0.18–0.23 B per GPU-h, T53). The high end is "at least" because T41 trained about 4× slower against a learned
  opponent on tier 1 (R6). Whether that also happens on tier 2 is not known.
- **Against version 1's guess:** version 1 guessed about 60 GPU-h, 36 of them runs of record. The review's 3–10× warning
  holds at the low end only: tier 2 measured at about 5× the cost of tier 1 per game-step (T53).
- **Calendar (est.):** L1–L4 take about 3–4 weeks, bound by build work and owner gates. L5 takes about 1–2 weeks of the
  RTX 5090, bound by the GPU. L6 takes about 1 week. L7–L8 then depend on an AirStack session and flight slots: about
  2–4 more weeks.
- **Ruled at G0 (section 5):** L1 + L2 together, with a cap of 13 GPU-h plus about 1 h of AirStack simulator time
  (owner, 22 Nov 2026).

## 2. Rates used (IDs referenced below)

| ID | Rate | Arithmetic and source | Label |
|---|---|---|---|
| R1 | tier 1, 3v3, Guard side against a script, 16,384 games: **1.06–1.37 B per GPU-h** | 553.6 M game-steps in 0.404–0.523 GPU-h, whole runs ([T46](../../records/2026-11-21_ste_l012_best_response_record.md), [T51](../../records/2026-11-21_ste_l012b_best_response_record.md)) | MEASURED |
| R2 | tier 1, 3v3, Strike side against a script: **0.93–0.97 B per GPU-h** | 553.6 M in 0.570–0.594 GPU-h (T46) | MEASURED |
| R3 | tier 2, 3v3, Guard side: **0.23 B per GPU-h**; Strike side not run: about 0.18 (R3 × R2/R1). Plan rate **0.18–0.23** | 302 M in 1.289 GPU-h ([T53](../../records/2026-11-21_ste_l013_tier2_trains_record.md)) | MEASURED; Strike PROPOSED |
| R4 | tier 2 is slower than tier 1 per game-step: 4.9–5.3× at 3v3, 4.1× at 5v3, 7.2× at 2v1, 9.8× at 1v1; tier 2 at 5v3 is about 1.03× slower than at 3v3 | same games at once ([T48](../../records/2026-11-21_ste_l02_speed_record.md)) | MEASURED |
| R5 | tier 1 per game-step relative to 3v3: 1v1 2.9× faster, 5v3 1.34× slower | 393.6k, 99.6k against 133.7k game-steps/s, 4,096 games (T48) | MEASURED |
| R6 | against a learned opponent, tier 1: **0.27 B per GPU-h**, about 4× slower than R1 | 579 M in 2.14 h on the RTX 5090; older driver, hangar game, 32,768 games, opponent S20 a network ([T41](../../records/2026-11-19_nus_phase5_pilot_p1b_run4_record.md), [TRAIN_A_GUARD](../../docs/TRAIN_A_GUARD.md)) | MEASURED; cause OPEN |
| R7 | tier 1 scoring: about 0.001 GPU-h per 1,000-game condition for short games; up to 0.015 when games run to the 120 s clock | [T44](../../records/2026-11-21_ste_l011_screen_record.md): 0.305 h for 24 batches of up to 30 conditions; clock games 2.4 M game-steps at about 50k/s (T48) | MEASURED; clock case PROPOSED |
| R8 | tier 2 scoring: about 0.02 GPU-h per 1,000-game condition inside one running Isaac world (T53 arm t2: 335 s for every evaluation and 24 curve reads); 0.6 as separate small runs ([T49](../../records/2026-11-21_ste_l03_transfer_record.md): 1.24 h for 2 conditions). Rows use 0.02–0.1 for batched suites and 0.02–0.3 for small checks | T53, T49 | bracket MEASURED; row values PROPOSED |
| R9 | learning length: one side beats its training opponent's script at 1.6 m in 0.55 B (T46; for the Strike team against that opponent only, [T56](../../records/2026-11-22_ste_l012d_cross_tag_record.md)). NUS self-play: 153.6 M per generation, 8–20 generations = 1.2–3.1 B ([NUS Phase 2a](../../records/2026-11-17_nus_phase2a_training_record.md)). **League: 2–5 B per seed** | 6,000 updates × 25,600 game-steps per generation | league length PROPOSED |
| R10 | tag 1.15 m: about 1.1–1.3× slower per game-step | Guard 0.523 against 0.404 GPU-h (T51 against T46); Strike 6–13 % per update ([DISCUSSION](../DISCUSSION_2026-11-19_20.md) §9) | MEASURED |
| R11 | tag 1.15 m, more training (L0.12c, tier 1, laptop): Guard team at 3× (1.65 B) holds **572 of 1,000** against the best script's 645 (1× gave 466); Strike team at 5× (2.76 B) reaches **134 of 1,000** against 355. Curves (256 curve games): Guard 0.50 → 0.54 from 1.07 to 1.57 B, slowing; Strike 0.102 → 0.176 from 0.57 to 2.76 B, still rising. Rates: Guard 1.08 B per GPU-h, Strike 0.89 | 1.655 B in 1.533 GPU-h, 2.756 B in 3.107 GPU-h ([T54](../../records/2026-11-22_ste_l012c_tag_1p15_guard_record.md), [T55](../../records/2026-11-22_ste_l012c_tag_1p15_strike_record.md)) | MEASURED |

## 3. Phases L1–L9 under D3, tag 1.6 m

Machine: "laptop" means the run fits in 12 GB. Tier 1 used 1.3 GB at 8,192 games and tier 2 used 4.7 GB at 16,384
games (T48). Only running tier 2 seeds side by side needs the RTX 5090's 32 GB. Each world keeps 16,384 games: the
physics check reads 0.0166 m of its 0.02 m limit there (T53). Task IDs not in [WORK_BREAKDOWN](../WORK_BREAKDOWN.md)
are marked *new*.

### L1 Drone model, plus the early 1v1 and varied-tag reads (G0 rows 3, 8, 17)

Purpose: the estimator effect (delay and noise) and drag in tier 2; an exploratory fit to logs; the first 1v1 and
varied-tag reads.

| Task | GPU work | Tier | Machine | GPU-h | Arithmetic |
|---|---|---|---|---|---|
| L1.0 5090 checks and speed re-measure (*new*) | 5090 drills, T48 subset | 1, 2 | 5090 | 0.3 – 0.5 | T48 used 0.294 |
| L1.1 State delay and noise in tier 2 | smoke | 2 | laptop | 0.2 | WORK_BREAKDOWN |
| L1.2 Drag in tier 2 | smoke | 2 | laptop | 0.2 | WORK_BREAKDOWN |
| L1.3 Fit delay, noise and drag to real logs | CPU | — | — | 0 | — |
| L1.4 AirStack-simulator velocity-step logs | AirStack simulator | — | laptop | (about 1 h of simulator time) | owner P5 |
| L1.5 Tier 2 against the AirStack simulator | replay | 2 | laptop | 0.3 | WORK_BREAKDOWN |
| L1.6 Batched estimator (only if needed) | smoke | 2 | laptop | 0 – 0.5 | WORK_BREAKDOWN |
| L1.7 Same effects in tier 1, so quick experiments stay comparable (*new*) | short check | 1 | laptop | 0 – 0.1 | R7 |
| L1.8 T46's base policies re-scored on the new tier 2 (*new*) | 4 conditions | 2 | laptop | 0.1 – 1.2 | R8: 4 × 0.02–0.3 |
| L1.9 1v1 best-response read, both sides, trained at tag 1.6 m (*new*; L0.12 driver), plus a scripted 1v1 screen also at tag 1.15 m on the CPU (G0 row 8) | run 0 + Strike + Guard, 0.55 B each; tier 2 check | 1 (check 2) | laptop | 0.5 – 1.9 | run 0 0.1; 2 × 0.55 B at R1 × R5 (0.18 h each) to R2 (0.6 h each); check 0.05–0.6 |
| L1.10 Tag drawn within ±0.1 m (1.5–1.7 m), 3v3, both sides (*new*) | Guard + Strike, 0.55 B each, scored at the fixed tag | 1 | laptop | 1.0 – 1.2 | Guard 0.40–0.52 h + Strike 0.57–0.59 h (T46) |
| L1.13 Shorter-training-clock 1.15 m Strike run (*new*, G0 ruling R15): tests the "too few finished games" lead ([DISCUSSION §12](../DISCUSSION_2026-11-19_20.md#12-l012c-findings-22-nov-2026)) | Strike, base budget, shorter training game clock (value set in its spec) | 1 | laptop | about 0.7 | lead's estimate: T46 base Strike 0.594 GPU-h × 1.1–1.3 (R10); config cap 0.8 |
| **L1** | | | | **3.3 – 6.8** | 2.6 – 6.1 + L1.13 about 0.7 |
| L1.11 Strike team trained against guard_field at 1.6 m (*new*; inside the ruled 13 GPU-h, G0 ruling R15; not in the L1 sum or the 87): separates "field Guards are hard" from "1.15 m is hard" | Strike, 0.55 B | 1 | laptop | about 0.6 | R2 (T46 base Strike 0.594); config cap 0.7 |
| L1.12 T46's 1.6 m Guard team scored against every Strike script at 1.6 m (*new*; inside the ruled 13 GPU-h, G0 ruling R15; not in the L1 sum or the 87): its 913 is against strike_straight only | scoring, one condition per Strike script | 1 | laptop | minutes (under 0.1) | R7 |

L1.9, L1.10 and L1.13 are quick experiments on tier 1, as D3 allows (A12, ruled 22 Nov 2026). Training 1v1 on tier 2 would add about 3 GPU-h (2 × 0.55 B
at about 0.37 B per GPU-h: tier 2 at 1v1 is about 1.6× faster per game-step than at 3v3, T48).

Human gates: P5 (simulator time, when the owner is not flying); the SIM-ONLY values in tier 2; the NEAR-962 flight
before any fit is used for a run of record. L1.9 and L1.10 are lead calls (INFO, gates written first).

**Requirement (from L0.12d, T56):** every trained read in L1 is scored against every scripted opponent of the other
side (cross-play), and the worst cell is reported; one opponent is not enough: the 1.6 m Strike team's gain (+0.444, 636 reaches
against mark_edge) became 85 reaches against field Guards, below the script's 284. Plan-changing L1 reads also train against a pool of scripts, with two seeds (PROPOSED,
not costed).

### L2 Game rules in the training copy

Purpose: the rules ruled at G0 (filter option B, landing drones stay filter obstacles, drone loss), and whether the game
stays worth learning under all of them.

| Task | GPU work | Tier | GPU-h | Arithmetic |
|---|---|---|---|---|
| L2.1 Filter option B in the training copy | convergence statistic | 1 | 0.1 – 0.3 | WORK_BREAKDOWN 0.3 |
| L2.2 Tag rule (built in L0.9; varied radius built in L1.10) | — | — | 0 | — |
| L2.3 Landing drones stay filter obstacles | smoke | 1 | 0.1 – 0.2 | WORK_BREAKDOWN |
| L2.4 Drone loss and random team size | CPU | — | 0 | — |
| L2.5 Scripted re-screen under the new rules | about 250 conditions | 1 | 0.3 – 0.5 | L0.11 used 0.426 (T44) |
| L2.6 Scripted games, tier 1 against tier 2, new rules | 5–10 conditions | 2 | 0.2 – 1.5 | R8 |
| L2.7 3v3 best-response read under the full rules (*new*) | run 0 + Strike + Guard, 0.55 B each | 1 | 1.0 – 1.4 | R1, R2; run 0 0.06–0.1 |
| **L2** | | | **1.7 – 3.9** | all on the laptop |
| L2.8 Tag-distance curriculum pilot (*new*, optional: only on the 1.15 m route; not in the L2 sum or the 87; lower priority since L0.12d: the Strike result tracks the opponent, and the warm-start value is not tested): each side trained at 1.6 m, then the tag stepped down to 1.15 m from that checkpoint. Needs a load-from-checkpoint option in the STE driver (`scripts/ste_exploit_l012.py` resumes its own run only; `train_standin.py` has `--warm-start`) | run 0 + Guard 1.65 B + Strike 1.65–2.75 B at 1.15 m | 1 | 3.5 – 5.8 | R11: Guard 1.65 / 1.08 = 1.5 h; Strike 1.65–2.75 / 0.89 = 1.9–3.1 h; run 0 0.07; the 1.6 m stage 0 if T46's networks are reused (on the laptop, not in git), else up to 1.1 (R1, R2) |

Human gates: P2 (option B, ruled at the end of L2); P1 and P7 for runs of record.

### L3 Learner

Purpose: observation v0.3, attention encoder, shared actor, team critic and PPO; a quick tier 1 pilot, then the tier 2
pilot.

| Task | GPU work | Game-steps | Tier | GPU-h | Arithmetic |
|---|---|---|---|---|---|
| L3.1–L3.4 Observation, encoder and actor, team critic, PPO | CPU | — | — | 0 | — |
| L3.5 Quick pilot, both sides against scripts, sizes 1v1–3v3, drone loss | 2 runs | 0.55 – 1.1 B each | 1 | 0.85 – 3.1 | 2 × 0.55 / 1.3 to 2 × 1.1 / 0.7 (0.7 allows for the encoder, PROPOSED) |
| L3.6 Tier 2 path and pilot (Guard side against scripts) | smoke + 1 run | 0.55 B | 2 | 2.5 – 3.6 | 0.55 / 0.23 to 0.55 / 0.18, + smoke 0.1–0.5 |
| **L3** | | | | **3.4 – 6.7** | |

**Added at G0 (owner, 22 Nov 2026, ruling R18):** a training-settings sweep (learning rate, exploration, discount,
training game clock, decision period), run at 1.6 m and 1.15 m and costed in the L3 plan. Cost OPEN: not in the L3 sum,
the 87 or the 13.

Human gate: the owner approves observation v0.3.

### L4 Evaluation suite and gates

Purpose: the suite (STANDARDS §7.4 groups, 1v1, and one size outside the range), the gates file, and calibration on
known players.

| Task | GPU work | GPU-h | Arithmetic |
|---|---|---|---|
| L4.1 Suite, L4.2 Gates file | CPU | 0 | — |
| L4.3 Calibration: about 100 conditions on tier 1, about 30 on tier 2 | 1, 2 | 0.7 – 4.5 | R7: 100 × 0.001–0.015; R8: 30 × 0.02–0.1 |

Human gate: the owner approves the gate limits.

### L5 League self-play

Purpose: self-play with a pool of past opponents and scripts (D6), then 3 seeds of record trained on tier 2.

| Task | GPU work | Game-steps | Tier | Machine | GPU-h | Arithmetic |
|---|---|---|---|---|---|---|
| L5.1–L5.2 League, self-play trainer | CPU smoke | — | — | — | 0 | — |
| L5.3 Quick league pilot (cycling, pool mix) | 1 seed | 1 – 2 B | 1 | laptop | 1.0 – 7.4 | 1 / 1.0 to 2 / 0.27 (R1, R6) |
| L5.4 League pilot on tier 2 | 1 seed | 1 B | 2 | laptop | 4.3 – 5.6 | 1 / 0.23 to 1 / 0.18 |
| L5.5 Runs of record: 3 seeds, tag drawn within ±0.1 m | 3 runs | 2 – 5 B each (R9) | 2 | 5090 (side by side: 3 × 4.7 GB) | 26 – at least 83 | 3 × 2 / 0.23 to 3 × 5 / 0.18 |
| L5.6 Debugging allowance | — | — | 1, 2 | either | 2 – 4 | WORK_BREAKDOWN 4 |
| **L5** | | | | | **33 – at least 100** | planning 63: 1.5 B / 0.7 + 1 B / 0.2 + 3 × 3.5 B / 0.2 + 3 |

Each seed of record takes about 9–28 GPU-h. All three fit one 5090 weekday window (Monday to Friday evening); on the
laptop they would run one at a time and not fit a weekend. Human gates: gates frozen; P1 and P2 ruled; the owner rules
the L5 budget at its own gate.

**Requirement (from L0.12d, T56):** the league trains against a pool of opponents (scripts, then past selves); every
team is scored against every opponent and the worst cell is reported. No trained strategy is shown in the AirStack
simulator or flown until L5 passes this opponent panel (two seeds for plan-changing reads).

### L6 QC, export, and the physical intercept in simulation

Purpose: score the runs of record on tier 2 (tier 1 for the large tables), export the policy file, show the intercept in
simulation.

| Task | GPU work | Tier | GPU-h | Arithmetic |
|---|---|---|---|---|
| L6.1 Score runs of record: headline suite on tier 2, full suite and cross-play on tier 1 | 3 × 50 conditions; about 600 | 2, 1 | 3.6 – 24 | R8: 150 × 0.02–0.1; R7: 600 × 0.001–0.015 |
| L6.2 Cross-checks: tier 1 against tier 2; option B against even split | tier 1 side | 1 | 0.1 – 1 | R7 |
| L6.3 Export policy file and interface.toml | CPU | — | 0 | — |
| L6.4 Physical intercept in simulation only (*new*; G0 row 14; earlier DRAFT: [contact-tag track](../../docs/plans/2026-11-17-contact-tag-track.md)): strategy hands over to a terminal intercept at the tag distance | INFO games + 3-D clips | 2 | 0.3 – 1.5 | PROPOSED |
| L6.5 Final policies re-scored with a Crazyflie-like response (*new*; T45 method) | CPU or short GPU | 1 | 0 – 0.2 | T45 ran on the CPU |
| 3-D clips of key games (VID-1) | Isaac renders | 2 | 0.3 – 0.6 | L0.5 used 0.258 |
| **L6** | | | **4.3 – 27** | |

Human gate: the owner approves the hand-over.

### L7 AirStack side, L8 real flight, L9 documentation (0 training GPU-h)

| Task | What | Simulator or hardware | Human gate |
|---|---|---|---|
| L7.1 AirStack-side specs | game node, filter option B, game configs (written here; an AirStack session builds) | — | D4, owner |
| L7.2 AirStack-simulator 1v1 | the policy with real PX4 + EKF2 | about 2 h of AirStack simulator time | owner |
| L7.3 Crazyflie adapter and rule plug-in spec (*new*; G0 row 12) | for a session in the Crazyflie repository (35–50 h there, estimate, DISCUSSION §2.16) | — | owner |
| L8.1 Crazyflies at Starling metres (*new*), sizes that fit the arena | reported as "the game on Crazyflies", never as Starling evidence | real Crazyflies | owner, flight safety |
| L8.2 Starling 1v1 demo | proximity tag by motion capture, same rule as in simulation | real Starlings | owner, PREFLIGHT update |
| L9.1–L9.2 Running docs, results page | records, status, STANDARDS after rulings | — | owner, for reader pages |

## 4. How the total moves with the open G0 answers

"Tier 2 training rows" = L3.6, L5.4, L5.5: about 33–92 GPU-h at tag 1.6 m.

| Open answer | Effect | Total, GPU-h | Label |
|---|---|---|---|
| Base case: D3, tag 1.6 m or 1.4 m | — | 46 – at least 149 (planning 87) | as section 1 |
| **Tag 1.15 m** | L0.12c (R11): at 3× and 5× both trained sides stay below the scripts; the Strike curve was still rising slowly, so whether more steps or a different recipe closes the gap is not shown, and no cause is established ([DISCUSSION §12](../DISCUSSION_2026-11-19_20.md#12-l012c-findings-22-nov-2026)). The Guard strategy trained at 1.6 m does not carry over to 1.15 m (195 v 572; the Strike team against field Guards is level within the intervals, 121 v 134, [T56](../../records/2026-11-22_ste_l012d_cross_tag_record.md)), so a 1.15 m policy is trained at 1.15 m. Optional task L2.8, a curriculum pilot of 3.5–5.8 GPU-h (section 3), has lower priority since L0.12d. The training rows then need at least 3.3× the game-steps (R10, R11) | at least 135; no upper figure until a route at 1.15 m is shown | R11 MEASURED; the rest PROPOSED |
| **If the owner revisits D3 at G0: train on tier 1, check on tier 2** | the pilots and the league at R1–R6 instead of R3; tier 2 used for checks only | 16 – 104 (planning 37) | PROPOSED |
| League on tier 1, final fine-tune on tier 2 (between the two) | the route above + 3 seeds × 2 sides × 0.3 B at R3 | 24 – 114 | PROPOSED |
| **5v3 (and 2v1) in the trained range** | tier 2 training rows × 1.03 per step (R4) × 1.5–2 more steps for coverage | + 18 – 98 | PROPOSED; whether 8 drones fit 6.5 m is OPEN (T45) |
| **Realistic 3-D worlds (P10)**, one rung (E1 blocks) | one more set of runs of record + an environment group in the suite | + 26 – 83, plus build work | OPEN; cameras would need the 5090's memory |
| 5 seeds of record instead of 3 | L5.5 × 5/3 | + 17 – 55 | PROPOSED |
| Crazyflies need their own drone model and training (if L6.5 shows the policy does not tolerate the 0.48–0.56 s lag) | a tier 1 Crazyflie model + one more set of runs of record | + 6 – 56, plus 25–40 h of build work | OPEN |

## 5. Cap ruled at G0 (owner, 22 Nov 2026)

| Ruling | Cap | Arithmetic |
|---|---|---|
| **L1 + L2 together, tag option (d)** | **13 GPU-h + about 1 h of AirStack simulator time** | L1 high 6.1 before L1.13 + L2 high 3.9 = 10 base; L1.11 (about 0.6), L1.12 and the cross-play scoring (minutes each, R7): about 10.6–11; L1.13 (about 0.7, lead's estimate): about 11.3–11.7, rounded to 12; plus one confirming seed: 13 |

The owner's words and every other ruling: [DISCUSSION §14](../DISCUSSION_2026-11-19_20.md#14-gate-g0-rulings-owner-22-nov-2026). Before the ruling this section proposed 10 GPU-h for
L1 + L2 at tag 1.6 m (11 with the optional checks), 15 GPU-h for a 1.15 m route (L1 + L2.8) and 6.5 GPU-h for L1 alone;
L3–L9 stay OPEN, re-baselined later.

**What L1 delivers.** All results are observed in the training simulator.
- **The Isaac Lab Starling the plan trains on**, with the estimator's delay and noise and with drag (exploratory fit),
  compared with the AirStack simulator (P5); the same effects in the fast engine for quick experiments.
- **The 5090 checked and its speeds measured; T46's trained teams re-scored** on the new Isaac Lab drone.
- **A first 1v1 read:** a trained Strike team and a trained Guard team at 1v1 against scripts that hold 1,000 of 1,000.
  Does learning change the two-Starling demo size?
- **A first read of training with the tag drawn within ±0.1 m** (1.5–1.7 m), scored at the fixed tag.
- **The 1.15 m side track:** the Strike team trained against field Guards at 1.6 m, which separates the opponent from
  the tag (L1.11); T46's 1.6 m Guard team scored against every Strike script (L1.12); and the shorter-training-clock
  Strike run at 1.15 m (L1.13).

L1 does not deliver a league, a run of record, or anything flown. L2 adds option B's numbers for the P2 ruling and a
best-response read under the full rules.

## 6. Calendar (est.)

| Item | Estimate | Basis | Label |
|---|---|---|---|
| Work hours L1–L9 | about 280 h of session work | WORK_BREAKDOWN about 260 h, plus the *new* tasks | PROPOSED |
| Work pace | about 30–40 session-hours a day | L0: about 80 h estimated, mostly done 20–21 Nov | PROPOSED |
| GPU capacity | about 6–10 useful GPU-h a day while a session is alive; detached runs continue overnight | AUTOMATION; one machine at a time | PROPOSED |
| Binding constraint | L1–L4: build work and owner gates; L5: the GPU (planning 63 GPU-h ≈ 6–10 GPU-days) | — | PROPOSED |

| Week (est.) | Machine | Work |
|---|---|---|
| 23–27 Nov | 5090 (weekdays) | L1.0 first (G0 row 17); L1.1–L1.3, L1.7; L1.9 and L1.10 runs |
| 28–29 Nov | laptop (weekend) | L1.5, L1.8; L2.1–L2.5 builds; short runs that finish before Sunday night |
| 30 Nov – 11 Dec | 5090, laptop at weekends | L2.6–L2.7 and the P2 ruling; L3 (tier 2 pilot on a weekday); L4 |
| next 5090 weeks | 5090 | L5.3–L5.4 pilots; then L5.5, three seeds side by side in one weekday window |
| after L5 | per owner | L6; L7 and L8 with an AirStack session and flight slots |

Every rate except R6 is laptop-measured; the 5090's are PROPOSED equal until L1.0 (T41 ran on the 5090 at R6).

## 7. Assumptions and what is open

| # | Assumption | Label |
|---|---|---|
| A1 | Rates R1–R5, R7, R10 | MEASURED (T44, T46, T48, T51, T53) |
| A2 | Tier 2 Strike side trains at about 0.18 B per GPU-h | PROPOSED (R3 × R2/R1) |
| A3 | A league needs 2–5 B game-steps per seed at 3v3 | PROPOSED (R9 anchors) |
| A4 | A learned opponent may slow tier 2 as it slowed tier 1 in T41 (R6) | OPEN: the reason the high end is "at least" |
| A5 | Tag 1.15 m: neither side reached the scripts at 3× (Guard) and 5× (Strike); whether more steps or a new recipe closes the gap is not known | R11 MEASURED; route OPEN |
| A6 | Tier 2 scoring batched in one running world costs 0.02–0.1 GPU-h per 1,000-game condition | bracket MEASURED (T53, T49); values PROPOSED |
| A7 | 1v1 at 16,384 games is up to 2.9× cheaper per game-step on tier 1 | MEASURED at 4,096 games (T48); at 16,384 OPEN |
| A8 | The 5090 is at least as fast as the laptop, and three tier 2 seeds side by side fit its 32 GB | OPEN (L1.0) |
| A9 | GPU-h of L1.1, L1.2, L1.5, L1.6, L2.1, L2.3 and L5.6 are version 1's guesses (WORK_BREAKDOWN) | PROPOSED |
| A10 | 3-D worlds, 5v3 and a Crazyflie model are outside the base total | OPEN (section 4) |
| A11 | The physical intercept is shown in simulation only; nothing real intercepts | RULED (owner, 22 Nov 2026, G0 ruling R14; owner's proposal, DISCUSSION §11) |
| A12 | Tier 1 training reads (L1.9, L1.10, L1.11, L1.13, L2.7, L2.8, L3.5, L5.3) and tier 1 scoring (L4.3, L6.1, L6.2) fit D3's "quick experiments and debugging only" | RULED (owner, 22 Nov 2026): the fast engine for quick experiments and checks, main training in Isaac Lab |

Sources: [PLAN](../PLAN.md) §3, §5, §9, §13; [G0_DECISION](../G0_DECISION.md); [DISCUSSION](../DISCUSSION_2026-11-19_20.md)
§2.16, §3, §9, §11, §12; [WORK_BREAKDOWN](../WORK_BREAKDOWN.md); records cited per rate.

## Panel proposals to fold in (22 Nov 2026, not yet costed)

From the results-and-plan discussion ([DISCUSSION §12](../DISCUSSION_2026-11-19_20.md#12-l012c-findings-22-nov-2026)):
a 1.15 m check block in L1 (the 1.6 m Strike team against guard_field, minutes: **done**, L0.12d, [T56](../../records/2026-11-22_ste_l012d_cross_tag_record.md): 85 at 1.6 m, 121 at 1.15 m; a shorter-clock 1.15 m Strike run,
about 0.6 GPU-h (now L1.13, about 0.7, ruled 22 Nov 2026); a warm start from T46, as L2.8 but earlier); two seeds for plan-changing reads; a Guard-script pool for
Strike training (L5); flight-side gates in L7/L8 (separation under real lag, scoring at tag ± the real error, arena fit,
per-tag logging, height play). The lead re-costs the plan with these before the walk-through.

