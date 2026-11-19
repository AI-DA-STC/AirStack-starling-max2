READ · TRAINING SIMULATOR ONLY: the NUS port's results, one table per question, each number beside its record and its caveat.

# NUS port results, by question

**For** the NUS team and anyone checking our numbers. Every number was observed in a training simulator; nothing
here has flown. The dated story is in [NUS_PORT](WHAT_WE_DID_DAY_BY_DAY.md); words in *italics* are in the [glossary](GLOSSARY.md).
This page replaces `NUS_PHASE4_RESULTS.md`.

**How to read the tables.**
- Your *defender* is our Guard team, your *attacker* our Strike team. A *Strike reach* is a game in which a Strike
  drone entered the zone (your sticky "reached" flag); a *hold* is a game that ran to the time-out with no reach.
- Counts are out of 1,000 games, with a Wilson 95 % interval in brackets. The pass marks (*gates*) were written down
  before each run; PASS and FAIL grade our copy against your code, never your code. INFO means "measured, no gate".
- *G19* and *S20* are the Guard of generation 19 and the Strike of generation 20 of your self-play seed 2, trained by
  us with your code on our hangar set-up. *P3G* and *P3S* are the Guard and Strike trained by us with your code against
  your scripted opponents (*APF*), on the same set-up. *ParkedGuard* is one Guard drone at the zone centre and every
  Guard drone commanding zero speed: the baseline.
- One seed and one set of starts per row: these tables measure transfer for these policies, not your method.
- T numbers are rows of [records/LEDGER.md](../records/LEDGER.md); each links its record ([how to read a
  record](../records/README.md)).

## Q1. Does our replica match your game?

| [![Row 1, our replica of your game: your G19 holds your S20](media/nus/phase4/row_1/G19_vs_S20_hold.gif)](media/nus/phase4/row_1/G19_vs_S20_hold.mp4) |
|:--:|
| Row 1, our replica of your game: your G19 holds your S20 (click for the full video) |

Yes, to the step, within the limit we set. `source/svg_training/nus/replica.py` is a batched PyTorch copy of your game:
the one-pass soft push, the Guard circle, 200 steps, the sticky reached flag and your random starts (Guard drones
inside a disc of half the zone radius; each Strike drone at the spawn distance on its own random bearing). We replayed
recordings of your own environment in it (100 episodes per set-up, random and rule-exercising actions).

| Check | Limit | 3 v 3 | 5 v 3 | Result |
|---|---|---|---|---|
| largest position error in one step | ≤ 1e-4 units | 3.8e-6 | 5.7e-6 | PASS |
| reached flag and step counter | equal | equal | equal | PASS |
| every rule exercised | ≥ 1 step each | yes | yes | PASS |

Evidence: T15, [record](../records/2026-11-17_nus_phase2_parity_record.md). Caveat: the check is step by step from
your recorded states. Over a whole game two independent float32 programs drift apart, so our own engine with your rules
(ladder row 2.1) matches row 1 to rounding, not game by game ([T19 record](../records/2026-11-18_nus_phase4_rung2_record.md)).

## Q2. Does the converted policy match yours?

Yes, within the limits we set. `nus/actor.py` reads your checkpoint files (msgpack, no JAX) and copies your bfloat16
rounding points; a plain float32 copy misses the action limit (0.022 and 0.030).

| Check | Limit | P3G / P3S (T16) | G19 / S20 (T17) | 24 entries of your 3 hangar lineages (R0) |
|---|---|---|---|---|
| largest action error, converted v your JAX, 24,000 observations per team | ≤ 0.02 units | Guard 0.0074, Strike 0.0105 | Guard 0.0079, Strike 0.0095 | 24 of 24 within; largest 0.0092 (10,800 rows each) |
| Strike reach v your scripted opponent, 1,000 shared starts | converted inside your JAX interval | JAX 48 [0.036, 0.063], converted 46 [0.035, 0.061] | JAX 166 [0.144, 0.190], converted 172 [0.150, 0.197] | — |
| G19 v S20, both converted v both JAX | inside | — | JAX 17 [0.011, 0.027], converted 15 [0.009, 0.025]; 8 games differ | — |
| Result | | PASS | PASS | PASS |

Evidence: T16 [record](../records/2026-11-18_nus_phase3_conversion_record.md); T17
[record](../records/2026-11-18_nus_phase4_w3_reference_gates_record.md); R0, T29
[record](../records/2026-11-18_nus_phase5_r0_reference_record.md). Caveat: the Strike arms are saturated (your Strike
policies reach the zone in every game against your scripted Guards), so the Guard and G19 v S20 arms carry the
information.

**The same pair on three start sets.** One pair has three numbers on our pages. They come from different starts, and
their intervals overlap; the replica does not disagree with itself.

| Pair | Your evaluator: your starts, evaluation seed 20261118 | Your environment's starts, 1,000 games, seed 20261118: your JAX / converted | Our paired-starts file, seed 20261119 (ladder row 1) |
|---|---|---|---|
| G19 v S20 | 0.023 of 256 games [0.011, 0.050] | 17 / 15 (T17) | 9 [0.005, 0.017] (T18) |
| G19 v APF Strike | 0.168 of 256 games | 166 / 172 (T17) | 175 [0.153, 0.200] (T18) |
| P3G v APF Strike | 1 of 20 games | 48 / 46 (T16) | 33 [0.024, 0.046] (T18) |

First column: INFO, [self-play matrix record](../records/2026-11-18_nus_selfplay_matrix_record.md) and [Phase 2a record](../records/2026-11-17_nus_phase2a_training_record.md) (written after the fact).
Row 1: [T18 record](../records/2026-11-18_nus_phase4_rung1_record.md).

## Q3. What does each drone limit do?

| [![Row 4, our safety filter on every pair of drones: S20 reaches the zone](media/nus/phase4/row_4/G19_vs_S20_strike_win.gif)](media/nus/phase4/row_4/G19_vs_S20_strike_win.mp4) |
|:--:|
| Row 4, our safety filter on every pair of drones: S20 reaches the zone (click for the full video) |

The *transfer ladder*: the converted policies stay frozen, and each row changes the game towards our drones. 1,000
paired games per pair on one starts file. Rows 1–3 run without the safety filter (a measurement, not a training
setting); rows 4–6 restore it, as in flight.

| Row | What changes from the row before | Simulator | Ledger |
|---|---|---|---|
| 1 | nothing: your game (replica) on the hangar set-up | replica | T18 |
| 2.1 | our game engine, with your push and Guard circle | tier 1 | T19 |
| 2.2 | square walls (the 7.5 m hangar arena) instead of the Guard circle | tier 1 | T19 |
| 2 | **two changes:** our blocking push-apart instead of your soft push, and each action held for 12 ticks (0.60 s) | tier 1 | T19 |
| 3a | control: a drone that flies the held command exactly (must equal row 2) | tier 1 | T20 |
| 3 | drone response: a copy of CMU's commander, delay and lag of our *exploratory* drone model | tier 1 | T20 |
| 4 | the safety filter on every pair instead of the push-apart (**two effects**, below) | tier 1 | T22 |
| 5a | control: drones free in height, no jitter (must equal row 4; 12 core pairs only) | tier 1 | T23 |
| 5 | drones free in height, start heights jittered by ±1 mm | tier 1 | T23 |
| 6 | the physics drone: rigid-body Starlings in Isaac Lab | tier 2 | T24 |

**Strike reaches of 1,000** (lower is better for the Guard team; core pairs with intervals):

| Guard v Strike | 1 | 2.1 | 2.2 | 2 | 3a | 3 | 4 | 5a | 5 | 6 |
|---|---|---|---|---|---|---|---|---|---|---|
| G19 v S20 | 9 [.005, .017] | 9 | 7 [.003, .014] | 17 [.011, .027] | 17 | 43 [.032, .057] | 740 [.712, .766] | 740 | 983 [.973, .989] | 979 [.968, .986] |
| G19 v ApfStrike | 175 [.153, .200] | 174 | 174 | 211 [.187, .237] | 211 | 408 [.378, .439] | 1000 | 1000 | 1000 | 1000 |
| P3G v S20 | 985 [.975, .991] | 984 | 863 [.840, .883] | 841 [.817, .862] | 841 | 926 [.908, .941] | 908 [.888, .924] | 908 | 924 [.906, .939] | 928 [.910, .942] |
| P3G v ApfStrike | 33 [.024, .046] | 34 | 34 | 96 [.079, .116] | 96 | 294 [.267, .323] | 1000 | 1000 | 1000 | 1000 |
| ParkedGuard v S20 | 1000 | 1000 | 1000 | 1000 | 1000 | 1000 | 556 [.525, .587] | 556 | 571 [.540, .601] | 524 [.493, .555] |

**All pairs, counts only** (same rows; "—" = not run: our scripted players need our observation, so they start at
row 2, and row 5a ran the core pairs only):

| Guard | Strike | 1 | 2.1 | 2.2 | 2 | 3a | 3 | 4 | 5a | 5 | 6 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| G19 | P3S | 971 | 970 | 970 | 980 | 980 | 1000 | 1000 | 1000 | 1000 | 1000 |
| P3G | P3S | 993 | 994 | 994 | 990 | 990 | 1000 | 1000 | 1000 | 1000 | 1000 |
| ApfGuard | S20 / P3S / ApfStrike | 1000 / 1000 / 999 | 1000 / 1000 / 999 | 1000 / 1000 / 1000 | 1000 / 1000 / 919 | 1000 / 1000 / 919 | 1000 / 1000 / 894 | 1000 / 1000 / 1000 | 1000 / 1000 / 1000 | 1000 / 1000 / 1000 | 1000 / 1000 / 1000 |
| ParkedGuard | P3S / ApfStrike | 991 / 1000 | 991 / 1000 | 991 / 1000 | 991 / 1000 | 991 / 1000 | 997 / 1000 | 1000 / 1000 | 1000 / 1000 | 1000 / 1000 | 1000 / 1000 |
| G19 | strike_straight / strike_flank | — | — | — | 209 / 40 | 209 / 40 | 385 / 54 | 1000 / 798 | — | 1000 / 1000 | 1000 / 1000 |
| P3G | strike_straight / strike_flank | — | — | — | 96 / 193 | 96 / 193 | 287 / 349 | 1000 / 978 | — | 1000 / 1000 | 1000 / 1000 |
| guard_mirror | S20 / P3S / ApfStrike | — | — | — | 1 / 25 / 48 | 1 / 25 / 48 | 69 / 80 / 39 | 856 / 980 / 960 | — | 1000 / 1000 / 959 | 1000 / 1000 / 961 |
| guard_mark_edge | S20 / P3S / ApfStrike | — | — | — | 0 / 25 / 48 | 0 / 25 / 48 | 1000 / 999 / 38 | 994 / 1000 / 958 | — | 1000 / 1000 / 962 | 1000 / 1000 / 945 |

Records: rows [1](../records/2026-11-18_nus_phase4_rung1_record.md), [2.1, 2.2, 2](../records/2026-11-18_nus_phase4_rung2_record.md),
[3a, 3](../records/2026-11-18_nus_phase4_rung3_record.md), [4](../records/2026-11-18_nus_phase4_rung4_2_record.md) (a
first attempt stopped as too long, T21 ABORTED: [record](../records/2026-11-18_nus_phase4_rung4_record.md)),
[5a, 5](../records/2026-11-18_nus_phase4_rung5_record.md), [6](../records/2026-11-18_nus_phase4_rung6_record.md).

<a id="fig-1"></a>
![Strike reach rate by ladder row](figures/nus_phase4_ladder.png)

*Figure 1. Strike reach rate (Wilson 95 % interval) of the 12 core pairs along rows 1–6, one panel per Strike player,
one line per Guard player; the dashed line is ParkedGuard. Made by `scripts/make_nus_phase4_figures.py` from the rows'
scores; ledger T18–T24.*

**Reading, row by row** ([Figure 1](#fig-1)), with the caveat beside each claim:

| Row | What we observed | Caveat |
|---|---|---|
| 1 | G19 holds S20 (9); ParkedGuard lets everything through (991–1,000), so the geometry alone does not close the zone | one starts file, one seed |
| 2.1–2.2 | our engine with your rules equals row 1 to rounding; square walls mostly cost P3G against S20 (985 → 863) | the walls also clamp Strike drones, which your circle never does |
| 2 | G19 v S20 9 → 17; G19 v ApfStrike 174 → 211 | two changes in one row (push-apart and action hold); not split |
| 3 | lag raises Strike reaches for most pairs (G19 v S20 17 → 43; G19 v ApfStrike 211 → 408) | the exploratory drone model answers more slowly than the real drone (its check against a real flight is T5 FAIL), so row 3 likely overstates the cost of lag |
| 4 | G19 v S20 43 → 740; both trained Guards concede every game to ApfStrike; ParkedGuard v S20 1,000 → 556 | **likely, not tested:** see "Row 4 changes two things" below; and the filter caveat below |
| 5a | equals row 4 in all 12,000 games, as it must | equal for one fixed batch shape (filter caveat) |
| 5 | G19 v S20 740 → 983 (251 games differ); horizontal closest approach falls (median 1.09 → 0.93 m, smallest 0.27 m) while the 3-D one stays at 1.09 m: drones pass over or under | a ±1 mm jitter, the exploratory drone model, and the filter caveat |
| 6 | Isaac Lab agrees with tier 1: G19 v S20 983 → 979 (16 games differ), P3G v S20 924 → 928; no drone tipped over in 24,000 games; fewer rule breaches than row 5 in every pair | frozen policies only; see Q4 |

**Row 4 changes two things.** The filter replaces the push *and* keeps team-mates 1.10 m apart, which your game
allows. Your Guards do stack: in row 1 the median per-game closest same-team approach for G19 v S20 is 0.066 m (T18
record, second table), and every start already has a pair inside the 1.10 m keep-out (*start miss* 1,000 of 1,000).
So the jump 43 → 740 has at least two candidate causes: (a) both drones of a close pair give way, so a Guard cannot push
a Strike drone off its path; (b) Guards can no longer stack, and the filter scatters the packed start. Two control rows
would split them, neither run yet: 4b, the filter between teams only; 4c, only the Strike drone yields.

**The filter caveat (rows 4–6).** Rows 4–6 ran the filter on a GPU with an early stop (a convergence check every 8
sweeps). On a GPU its answer for one game depends on how many other games are still sweeping, and in about 40 % of
games (ParkedGuard v S20, ticks 30–33) it does not converge in 1,000 sweeps; there, tiny rounding differences grow to
m/s (T31, [record](../records/2026-11-18_filter_cuda_graph_record.md)). So rows 4–6 cannot be repeated game by game at
another batch size or on another GPU; "5a = 4 in every game" holds for one fixed batch. How much the counts move is
not measured yet (re-scoring rows 4 and 5 with the fixed loop would show it).

**The Contact column of the records is not a crash count.** It counts games in which *any* two drones, team-mates
included, come closer than 0.50 m. Your start puts the three Guard drones in a disc of 0.8 m radius, so 853 of the
1,000 starts already hold such a pair (923 with the parked layout); rows 4–6 read exactly that. For Guard–Strike
closeness read the closest-approach column: on rows 4–6 its median is 1.05–1.14 m in every pair, and every pair with
one of your policies stays at 0.57 m or more.

## Q4. Does Isaac Lab agree with our fast drone model?

| [![Row 6, Isaac Lab Starlings: S20 reaches the zone, as on tier 1](media/nus/isaac/g19_vs_s20_strike_win_1.gif)](media/nus/isaac/g19_vs_s20_strike_win_1.mp4) |
|:--:|
| Row 6, Isaac Lab Starlings: S20 reaches the zone, as on tier 1 (click for the full video) |

For these frozen policies, yes: row 6 (tier 2, rigid-body Starlings flown by a copy of PX4's control loops) against
row 5 (tier 1), same starts.

| Pair | Row 5, tier 1 | Row 6, Isaac Lab | Games that differ |
|---|---|---|---|
| G19 v S20 | 983 [.973, .989] | 979 [.968, .986] | 16 |
| P3G v S20 | 924 [.906, .939] | 928 [.910, .942] | 68 |
| ParkedGuard v S20 (largest change) | 571 [.540, .601] | 524 [.493, .555] | 247 |

Evidence: T23 [record](../records/2026-11-18_nus_phase4_rung5_record.md), T24
[record](../records/2026-11-18_nus_phase4_rung6_record.md). Caveats: one seed; tier 1 still uses the exploratory drone
model; agreement for frozen policies says nothing yet about a policy trained on tier 1.

## Q5. What does a Guard team that stands still do?

| [![Row 5, a parked Guard team holds S20 off](media/nus/phase4/row_5/ParkedGuard_vs_S20_hold.gif)](media/nus/phase4/row_5/ParkedGuard_vs_S20_hold.mp4) |
|:--:|
| Row 5, a parked Guard team holds S20 off (click for the full video) |

On rows 4–6 it holds more games against S20 than either trained Guard: the filter's keep-out around a still drone acts
as a wall.

| Guard v S20, holds of 1,000 | Row 4 | Row 5 | Row 6 |
|---|---|---|---|
| ParkedGuard | 444 [.413, .475] | 429 | 476 |
| G19 | 260 [.234, .288] | 17 | 21 |
| P3G | 92 | 76 | 72 |

Holds are 1,000 minus the Strike reaches of Q3 (same records). Caveats: G19 and P3G were trained in a game without the
filter, so this measures transfer, not your method. ParkedGuard v S20 is exactly the case where the filter often does
not converge (Q3, filter caveat). Whether a learner finds this "filter as a wall" defence is open (Q7).

## Q6. Does our copy of your training method behave like yours?

**In progress: the test is calibrated; our copy has no result yet.** We are porting your alternating best-response multi-agent PPO with the archive pool
(`train_self_play`, no APEX) to PyTorch. Before any of our seeds is scored, a test was fixed in advance:

| Step | What | Status (18 Nov 2026) | Evidence |
|---|---|---|---|
| R0 | your 3 hangar lineages (24 archived entries) converted and scored as a 12 × 12 matrix at 1,000 games per pairing | PASS: 24 of 24 converted within 0.02 units | T29, [record](../records/2026-11-18_nus_phase5_r0_reference_record.md) |
| N0 | untrained actors scored as if they were "our copy": the test must fail them | PASS: the test failed them (Guard difference −0.366 [−0.499, −0.234], Strike −0.594 [−0.848, −0.341]) | T30, [record](../records/2026-11-18_nus_phase5_n0_negative_control_record.md) |
| C0 | your own code, 3 new seeds, scored as if it were "our copy": the test must pass it | PASS: Guard difference −0.027 [−0.171, +0.117], Strike +0.108 [−0.150, +0.366]; all 24 entries inside the scripted range | T33, [record](../records/2026-11-19_nus_phase5_c0_positive_control_record.md) |
| 5.1 | our copy, 3 seeds × 8 generations | running | — |

**The test in plain words** (plan [§4.3](plans/2026-11-18-nus-phase5-retraining.md)): every seed finishes; the
learner does not fail two generations in a row; each entry's score against your scripted opponents lies inside the
range of your 12 entries; and each lineage's mean strength against your other lineages, averaged over 3 seeds, is not
told apart from yours by a two-sample interval (with a cap on how much noisier our seeds may be). We dropped an earlier
per-cell rule ("every cross-play cell inside your 95 % interval"): it would fail your own seeds against each other.

What we will not claim, even after a PASS: that our copy "matches", "reproduces" or "is equivalent to" your method.
The claim is only that a pre-registered screen for a broken learner, 3 seeds a side, does not tell them apart. N0 shows
the test fails a learner that learned nothing; C0 shows it does not fail your own code with new seeds. With three seeds
a side it catches only large differences.

## Q7. Can we train a Guard team on our drone model?

| [![Pilot P1b, our own learner: the Guards spread across the zone and hold S20 off](media/nus/pilots/p1b_run4_final_t1472_best_hold_slot0.gif)](media/nus/pilots/p1b_run4_final_t1472_best_hold_slot0.mp4) |
|:--:|
| Pilot P1b, our own learner: the Guards spread across the zone and hold S20 off (click for the full video) |

**First signal, not yet a gated result.** Stage 5.2 (your method on tier 1 with drone lag, the all-pairs filter and 3-D)
has not started. Short pilots with our simple stand-in learner (skrl IPPO, one seed, no gates) asked whether it finds the
"filter as a wall" defence quickly. **Pilot P1b, once its set-up was fixed, did:** its Guard team holds the zone against
S20 in 829 of 1,000 games on the Phase 4 paired starts, against 429 for a Guard that parks at the centre (likely the
filter acting as a wall around each Guard, read from the videos, not tested by a control). One seed, one opponent:

| Pilot | What | Result | Evidence |
|---|---|---|---|
| P0 | speed of the hangar game with the filter | INFO: the filter takes 89–99 % of each tick | T25, [record](../records/2026-11-18_nus_phase5_pilot_p0_record.md) |
| P1 | 3 Guard learners v S20, 236 M game-steps | INFO, signal not met: 0 holds of 1,000 [0.000, 0.004]. Its set-up was faulty: γ 0.99 per 0.05 s tick, a hold rewarded only at the 2,400-tick time-out (no training game reached it), and a non-zero starting mean action | T26, [record](../records/2026-11-18_nus_phase5_pilot_p1_record.md) |
| P1b | P1 fixed (zero-mean start, one decision per 0.60 s, no shaping) | runs 1–3 ABORTED (a shared GPU starved runs 1 and 2; run 3 stopped for a reboot). **Run 4, alone on the GPU: INFO, signal met: 829 holds of 1,000 [0.804, 0.851]** (parked Guard 429; the bar was a lower bound above 0.460). [Videos](media/nus/pilots/) | T32, T39, T40, **T41**, [record](../records/2026-11-19_nus_phase5_pilot_p1b_run4_record.md) |
| P2 | Guard learners v scripted Strike mix, warm start from P1 | ABORTED twice before any update (a warm start from P1 told us nothing) | T27, T28, [record](../records/2026-11-18_nus_phase5_pilot_p2_record.md) |

P1 tested a mis-set learner. P1b shows that a simple learner can find a wall-like defence against S20 on our drone
model; it does not show how that Guard does against other Strike behaviours (P2, not run), in self-play, or in Isaac Lab.

## Q8. Limits

- One seed per ladder row and one starts file: no claim about your method.
- G19 and S20 come from 8-generation self-play (`self_play.generations=8`; seed 2 continued to 20); your default is 32.
- Phase 1, Phase 2a, Run 0 and the self-play matrix are INFO records written after the fact from their logs and
  outputs ([Phase 1](../records/2026-11-17_nus_phase1_install_record.md), [Phase 2a](../records/2026-11-17_nus_phase2a_training_record.md), [Run 0](../records/2026-11-17_nus_run0_record.md), [matrix](../records/2026-11-18_nus_selfplay_matrix_record.md)). Their evaluations used 20 or
  256 games per pair, below our 1,000.
- Rows 3–6 use the exploratory drone model (T5 FAIL), which answers more slowly than the real drone.
- Rows 4–6 depend on the filter's batch size on a GPU (Q3).
- Your network has no padding, so a policy plays 3 v 3 only (read from your code). Your answer: the method does not
  support drones dropping out. Your answer: a policy trained with one config usually works only with that config.
- The hangar set-up (0.40 m per unit, 0.60 s per step, 7.5 m arena, 1.2 m height) is ours, not yours.
- The converted G19, S20, P3G and P3S weights and our local settings files are in the repository marked PROVISIONAL (trained by us
  with your code, 8 generations, hangar set-up), only so that our numbers can be repeated. You will retrain.
- Contact between drones (a *tag*) is a separate track; this port is contact-free.
