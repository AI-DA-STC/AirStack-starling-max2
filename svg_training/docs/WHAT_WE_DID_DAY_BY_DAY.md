REFERENCE · TRAINING SIMULATOR ONLY: the NUS port as a dated log, phase by phase. Results by finding: WHAT_WE_FOUND.md.

# What we did, day by day

**For** NUS researchers and anyone new to the work: what STE did with NUS's code, phase by phase. **STE**: the lab
that wrote this repository. Results by finding: [what we found](WHAT_WE_FOUND.md); how to repeat them:
[how to run it yourself](RUN_IT_YOURSELF.md). Every number was **observed in the training simulator** (NUS's 2-D
game, STE's copy of it, or the STE game with Starling-like drones). Nothing here has flown. The old name of this page,
`NUS_PORT.md`, points here.

NUS agreed (18 November 2026) that its code details, its game settings and STE's results on its code may be published
here ([STANDARDS §2](../STANDARDS.md#2-wording)). NUS's source code stays in NUS's repository: these pages describe it
in words and cite `file:line`. The converted G19, S20, P3G and P3S and STE's local settings files are in this
repository marked PROVISIONAL, only so the numbers can be repeated. Terms: NUS's `defender` is the defender (Guard
team) here, NUS's `attacker` the attacker (Strike team); NUS calls its game "area denial". The policies and the six
tests are defined in the [glossary](GLOSSARY.md#policies); the records number the tests as ladder rows (Test N =
ladder row N). Last updated 19 November 2026: Phase 5 in progress (§12).

## At a glance

| Phase | What | Maths library | Simulator | Result | Evidence |
|---|---|---|---|---|---|
| 0 | STE's questions to NUS | — | — | answered 17 Nov (§3) | §3 |
| 1 | NUS's code installed | JAX | NUS 2-D game | 65 of NUS's 66 tests pass; the one failure checks an older Guard distance (NUS confirmed it is out of date); INFO | [record](../records/2026-11-17_nus_phase1_install_record.md) |
| 2a | policies trained by STE with NUS's code on the hangar set-up (NUS shared code, not trained checkpoints) | JAX | NUS 2-D game | speed check, fixed-opponent runs, Run 0, self-play 3 seeds × 8 generations and seed 2 to 20; INFO | [training](../records/2026-11-17_nus_phase2a_training_record.md), [Run 0](../records/2026-11-17_nus_run0_record.md), [matrix](../records/2026-11-18_nus_selfplay_matrix_record.md) |
| 2 | NUS's game copied to PyTorch: the Copy of NUS 2-D game | PyTorch | Copy of NUS 2-D game (PyTorch) | T15 PASS: same game step by step | [the copy checked](WHAT_WE_FOUND.md#1-copy-of-nus-2-d-game-pytorch-matches-nus-2-d-game-jax) |
| 3 | the policies converted to PyTorch | PyTorch (JAX for the reference) | Copy of NUS 2-D game (PyTorch) | T16 PASS; T17 PASS on G19 / S20 | [the conversion checked](WHAT_WE_FOUND.md#2-converted-policies-match-the-jax-originals) |
| 4 | six tests: the game brought towards STE drones, one test at a time | PyTorch; Isaac Lab for Test 6 | Copy of NUS 2-D game, STE drone model, Isaac Lab physics drones | INFO, T18–T20, T22–T24 (T21 ABORTED): G19 v S20 Strike reaches 9 → 17 → 43 → 740 → 983 → 979 of 1,000 | [test results](WHAT_WE_FOUND.md#3-six-tests-towards-ste-drones) |
| 5 | training in STE conditions: the STE port of NUS's training method (PyTorch), and STE pilots | PyTorch | Copy of NUS 2-D game, then STE drone model | in progress: R0 PASS, N0 PASS, C0 PASS; stage 5.1 running; the STE Guard policy (pilot P1b) holds S20 in 829 of 1,000 | §12 |
| 6 | these documents | — | — | 18–19 Nov | — |

*STE drone model (PyTorch)*: the fast STE game with a drone model fitted to one Starling flight log ("tier 1" in the
records); *Isaac Lab physics drones*: rigid-body Starling models in Isaac Lab ("tier 2"); *hangar*: STE's flight
room (§3); *Starling*: ModalAI Starling 2 Max, STE's small indoor drone.

## 1. The NUS code: three branches

| Branch | What it is | What STE did |
|---|---|---|
| `area-denial-continuous-space-self-play` (commit `2d2b904`) | continuous 2-D moves, ensemble self-play; the one NUS named as the most recent | **used**: installed, tested, trained, converted, scored |
| `area-denial-self-play` | the older version, discrete actions | read only |
| `smackx-self-play` | continuous actions plus robustness experiments on SMAX (a StarCraft-style benchmark) | read only |

**NUS's game, as read by STE** (the Copy of NUS 2-D game reproduces it step by step, §6):

- Drones are points in a plane. Each step a drone moves by a displacement up to its team's cap: Guard 0.5, Strike 0.75
  units (the 1.5 speed ratio of [STANDARDS §4](../STANDARDS.md#4-game-specification-version-0)).
- A Strike drone *reaches the zone* when its centre is inside the zone radius (4 units); the flag stays set. A game is
  200 steps.
- Opposite teams are kept apart by a soft push in the same step: push radius = twice the body radius (1.0 unit) plus
  the team's safety distance (Guard 1.0, Strike 0.5), so 3.0 units around a Guard drone and 2.5 around a Strike drone;
  a drone's whole move in one step, push included, is capped at 1.0 unit. Team-mates may overlap. Guard drones stay
  inside a circle (default 20 units). No walls, no height, no drone dynamics.
- Random starts (the ones used here): Guard drones inside a disc of half the zone radius; each Strike drone at the
  spawn distance (default 20 units) on its own random bearing. The fixed layout instead puts the Strike drones in a
  small cluster on the ring.
- Scripted opponent (`scripted_opponent: apf`, artificial potential field; the *APF defender* and *APF attacker*):
  the Strike controller is pulled to the zone and pushed from Guards (gains 1.0 and 24.0); the Guard controller moves
  towards the nearest Strike drone.
- Observation: 9 numbers per drone (itself, team-mates, opponents: the zone's direction and distance now, at the
  previous step and of the last move), then the zone radius and the reached flag: 56 for 3 v 3. No padding: a 3 v 3
  policy plays 3 v 3 only. Policy: two dense layers, two residual blocks (LayerNorm, Mish), tanh scaled to the team
  speed and projected onto a disc; bfloat16. Training: alternating multi-agent PPO against an archive of up to 15
  earlier policies plus one scripted slot; 6,000 updates per generation.

## 2. Phase 1: NUS's code installed (17 November 2026)

`scripts/workstation/setup_nus_jax.sh` built a conda environment (Python 3.12, jax 0.10.2, flax 0.12.8, CUDA 13 JAX)
and ran NUS's tests on the CPU: **65 of NUS's 66 tests pass** (42.8 s). The one failure expects the Guard safety
distance of an older specification; NUS's config has used another value since commit `7509c36`, and NUS confirmed the
test is out of date. INFO ([record](../records/2026-11-17_nus_phase1_install_record.md), written after the fact).

## 3. Phase 0 answers and the hangar geometry

NUS's game has no metres or seconds. NUS's answers (17 November 2026):

| Question | NUS's answer | What STE did |
|---|---|---|
| metres per unit, seconds per step | the units were scaled to the arena; pick a zone radius that suits the arena | the scale was fitted to the STE hangar (below) |
| which Guard safety value | both configs work, but a policy trained with one config usually works only with that config | every reference policy is trained on the exact geometry it is scored on |
| a drone that drops out | the method does not support drones colliding or being disabled | a fixed team size for the whole game |

**The hangar geometry.** STE chose 0.40 m per unit after a review of training balance, drone dynamics and the flight
software. A first proposal of 0.2 m per unit failed three ways: the zone (0.8 m) would sit inside the flight software's
1.10 m keep-out, so one parked Guard drone could close it; the safety filter would become a much larger push than
NUS's; and the start ring would lie outside the fence.

| Item | Value |
|---|---|
| Scale | 0.40 m per unit; 0.60 s per step (12 simulator ticks of 0.05 s) |
| Speeds | Strike 0.75 × 0.40 / 0.60 = 0.50 m/s; Guard 0.333 m/s |
| Game length; zone | 200 steps = 120 s; NUS's default 4 units = 1.6 m radius, at the arena centre |
| Arena | square, **7.5 m** side (walls at ±3.75 m), inside the hangar's usable flying box |
| Starts | spawn distance 8 units (3.2 m) and Guard circle 8 units (`spawn_distance=8.0`, `defender_boundary=8.0`); Guard start disc as NUS's |
| Teams; height | 3 v 3 fixed (5 v 3 does not fit the hangar); 1.2 m for all drones |

The hangar's usable flying box (measured 17 November 2026, 1.0 m inside the free floor) is about 7.6 m × 7.9 m,
0.5–5.0 m high. The flight software's keep-in fence is ±3.25 m today, so flying this game would need it moved first.
At this scale NUS's push radii are 1.2 m (Guard) and 1.0 m (Strike), close to the 1.10 m keep-out.

**Run 0** (before any training; NUS's environment, CPU, 1,000 games per cell, seed 12345, limits set in advance): the
APF attacker beat mirror Guards on the zone rim in 0.067 [0.053, 0.084] of games (median reach step 24) and beat the
APF defender, a parked Guard and static Guards in every game, so the zone was neither too easy nor too hard. Limit:
NUS's code has one scripted Strike behaviour, so only the Guard side was varied ([record](../records/2026-11-17_nus_run0_record.md)).

## 4. Phase 2a: training with NUS's code (17–18 November 2026)

NUS shared its code, not trained checkpoints, so STE trained the reference policies with that code. Every job ran
through `scripts/workstation/run_nus_job.sh` (cloud logging off). INFO runs, no gates ([record](../records/2026-11-17_nus_phase2a_training_record.md), written after the fact).

| Run | Setting | Observed |
|---|---|---|
| Speed | NUS's `benchmark_self_play_2048`, 3 v 3 against the fixed APF opponents | 0.0565 s per update of 25,600 game-steps: about 453,000 game-steps/s |
| Fixed opponent (NUS's default geometry; hangar) | 3,000 updates per team, about 6.5 min each | Guard held 20 of 20 evaluation games; 19 of 20 on the hangar. Strike reached in 20 of 20 on both. The hangar pair is **P3G** and **P3S** (run folders `2026-11-17_fixed_apf_3v3_defender` and `…_attacker`) |
| Self-play, hangar | `train_self_play`, 3 seeds × 8 generations (`self_play.generations=8`; NUS's default is 32), 6,000 updates per generation; seed 2 continued to 20 (run folder `2026-11-17_selfplay_3v3_seed2`) | §5 |

NUS's self-play runner wrote no GIFs even with `save_eval_gif=True` (NUS may know a flag that was missed); clips were
rendered afterwards with NUS's `ma_skills/scripts/eval.py` (§9). Two jobs started in the same second share one output
folder, so each job gets its own `hydra.run.dir`.

## 5. Self-play: who beats whom

Each archived policy played every policy of the other team, 256 games per pair, NUS's evaluator, deterministic
actions, evaluation seed 20261118 ([Figure 1](#figure-1); [record](../records/2026-11-18_nus_selfplay_matrix_record.md), written after the fact). Strike win = 1 − Guard hold.

<a id="figure-1"></a>
![Strike win rate for every Guard policy against every Strike policy](figures/nus_selfplay_matrix.png)

*Figure 1. Strike win rate for each Guard policy (rows) against each Strike policy (columns): seeds 1 and 3 to
generation 8, seed 2 to generation 20, 256 games per pair, hangar geometry, NUS 2-D game. Red: the Strike team wins;
blue: the Guard team holds. Made by `scripts/make_nus_selfplay_figures.py` from STE's matrix file.*

Go/no-go after 8 generations (set before the run): no learner failed two generations in a row (PASS); final cross-play
mean 0.668, inside 0.2–0.8 (PASS). No single pair is balanced (every cell ≤ 0.008 or ≥ 0.988), and within a seed the
later generation mostly beats every earlier one ("last mover wins").

**Seed 2 to 20 generations.** Generations 1–12 keep the last-mover cycle. From generation 13 it stops in the Guard
team's favour: Guards 13–19 hold every earlier Strike policy (worst 0.06), and about 0.95 of all cells stay
near-shutouts. With 8 generations per seed (NUS's default is 32) and one seed continued, this describes these runs,
not NUS's method.

| Final policy | Against the other seeds' policies | Against NUS's scripted opponent |
|---|---|---|
| seed 2 Guard generation 19 (**G19**, `archive/0019_defender`) | mean Strike win 0.042 over 8 Strike policies (worst 0.13) | concedes 0.168 to the APF attacker |
| seed 2 Strike generation 20 (**S20**, `archive/0020_attacker`) | mean Strike win 0.726 over 8 Guard policies | beats the APF defender 1.00 |
| G19 against S20 | Strike win 0.023 | — |

G19 and S20 became the reference pair for Phases 3 and 4. Re-running old cells gave differences up to 0.047 (cause not
tested).

## 6. Phase 2: the Copy of NUS 2-D game (T15, 17 November 2026)

`source/svg_training/nus/replica.py` copies NUS's game in batched PyTorch (the "replica" of the records).
Recordings of NUS's own environment were replayed in it: largest position error per step 3.8e-6 units (3 v 3) and
5.7e-6 (5 v 3), limit 1e-4. **T15 PASS** ([record](../records/2026-11-17_nus_phase2_parity_record.md);
[the copy checked](WHAT_WE_FOUND.md#1-copy-of-nus-2-d-game-pytorch-matches-nus-2-d-game-jax)).

## 7. Phase 3: the policies, converted (T16 and T17, 18 November 2026)

`nus/actor.py` loads NUS checkpoints (msgpack, no JAX) with NUS's bfloat16 rounding points; `nus.strategy:NusPolicy`
rebuilds NUS's 56-number observation from STE's and holds each action for 12 ticks
([plug in a trained NUS policy](PLUG_IN_YOUR_CODE.md#plug-in-a-trained-nus-policy)). Largest action error 0.0105 units
(limit 0.02); outcomes inside the 95 % interval of NUS's code. **T16 PASS** ([record](../records/2026-11-18_nus_phase3_conversion_record.md)), **T17 PASS**
on G19 / S20 ([record](../records/2026-11-18_nus_phase4_w3_reference_gates_record.md);
[the conversion checked](WHAT_WE_FOUND.md#2-converted-policies-match-the-jax-originals)).

## 8. Phase 4: six tests towards STE drones

The converted policies stay frozen. Each test changes one thing on the way from NUS's game to STE drones, except
Test 2 (the STE push-apart and the 12-tick hold) and Test 4 (the safety filter replaces the push and also keeps
team-mates apart). 1,000 paired games per pair from one starts file, one seed, so no method claim. Tests 1–3 run
without the safety filter (a measurement only); Tests 4–6 restore it. Full table, figure and reading:
[test results](WHAT_WE_FOUND.md#3-six-tests-towards-ste-drones); [plan](plans/2026-11-18-nus-phase4-transfer-ladder.md)
(the plan says "transfer ladder").

| Strike reaches of 1,000 | Test 1: Copy of NUS 2-D game | Test 2: STE game engine, hold | Test 3: + delay and lag | Test 4: + safety filter | Test 5: + free height | Test 6: Isaac Lab physics drones |
|---|---|---|---|---|---|---|
| G19 v S20 | 9 | 17 | 43 | 740 | 983 | 979 |
| G19 v APF attacker | 175 | 211 | 408 | 1000 | 1000 | 1000 |
| Parked Guard v S20 | 1000 | 1000 | 1000 | 556 | 571 | 524 |

Records T18–T20, T22–T24 (T21 ABORTED). Tests 4–6 ran the filter on a GPU, where its answer depends on the batch size
([record](../records/2026-11-18_filter_cuda_graph_record.md)), so a repeat agrees within intervals, not game by game.

## 9. Videos

Every clip is published: NUS's 2-D game, the Copy of NUS 2-D game, every test top-down, and Isaac Lab clips of Test 6
(a second set in a world with props, a backdrop only). One line per clip: [videos of the NUS port](media/nus/README.md).
NUS's renderer draws Guard drones D0–D2 blue and Strike drones A0–A2 red; STE's, blue circles and orange triangles.

| | |
|---|---|
| ![G19 vs S20 · NUS 2-D game (JAX) · Guard holds](media/nus/nus_selfplay_s2_g19_vs_s2_s20.gif) | ![APF defender vs P3S · NUS 2-D game (JAX) · Strike reaches the zone](media/nus/nus_fixed_strike_vs_scripted_guard.gif) |
| *G19 vs S20 · NUS 2-D game (JAX) · Guard holds for 200 steps.* | *APF defender vs P3S · NUS 2-D game (JAX) · Strike reaches the zone at about step 7.* |
| ![G19 vs S20 · Test 6: Isaac Lab physics drones · Strike reaches the zone](media/nus/isaac/g19_vs_s20_strike_win_1.gif) | ![Parked Guard vs S20 · Test 6: Isaac Lab physics drones · Guard holds](media/nus/isaac/parked_vs_s20_hold_1.gif) |
| *G19 vs S20 · Test 6: Isaac Lab physics drones · Strike reaches the zone at 24.1 s (979 of 1,000 in this test; 4× real time).* | *Parked Guard vs S20 · Test 6: Isaac Lab physics drones · Guard holds for 120 s (476 of 1,000 held; 8× real time).* |

Before-and-after pairs on the same start (Tests 3 → 4 and 4 → 5): [how to run it yourself, level A](RUN_IT_YOURSELF.md#a-watch-the-games)
and [videos of the NUS port](media/nus/README.md).

## 10. What it means for flight

Nothing here has flown. In the training simulator only:

- G19 keeps most of its strength through Tests 1–2; drone lag costs it against simpler Strike behaviour (Test 3).
- **With the safety filter on every pair, Strike reaches for G19 v S20 rise from 43 to 740 of 1,000** (Test 4).
  Likely reading, not yet tested: the NUS-code Guards hold by pushing, and the filter makes both drones of a close
  pair give way; it also keeps team-mates 1.10 m apart, which NUS's game allows. A Guard policy meant for flight
  likely has to be trained with the filter in the loop.
- **Height is a way past the Guards** (Test 5: 983), with a ±1 mm start jitter, the exploratory drone model and the
  filter caveat of §8. Either a policy is trained in 3-D with the filter, or the flight side locks the height (a change
  to the flight software, not assumed).
- **The Isaac Lab physics drones agree with the STE drone model** for these frozen policies (983 and 979; no drone
  tipped over in 24,000 games).
- In Tests 4–6 a Guard team that stands still holds more games than G19 or P3G (444, 429, 476 of 1,000 against S20).
  Both were trained in a game without the filter, so this measures transfer, not NUS's method.
- 3 v 3 needs six drones and STE has two; a drone that drops out ends the game (NUS's method does not support it).

## 11. Limits

Phases 1 and 2a, Run 0 and the self-play matrix ran with NUS's code before STE kept ledger rows for it; their records
were written afterwards from the logs and outputs, and their numbers are INFO (20 or 256 games per pair, below the
1,000 used here). The other limits (one seed, 8 generations, STE's hangar values, the exploratory drone model, the
filter's batch dependence) sit in [what we found, limits](WHAT_WE_FOUND.md#8-limits).

<a id="12-next-steps-the-phase-5-plan"></a>
## 12. Phase 5: training in STE conditions (in progress)

**Why.** Phase 4 shows that policies trained for NUS's game do not transfer to STE drones as they are. Three routes
were weighed: (a) NUS retrains with action hold, delay and STE's rules in its own code, and STE repeats Phases 3–4 on
the result; (b) STE ports NUS's training method to PyTorch and trains on Starling-like drones (the *STE port of NUS's
training method (PyTorch)*, "route (b)" in the records); (c) STE fine-tunes the converted policies, which needs the
same check of the method first. STE chose (b), and asks whether NUS would also do (a)
([question 2](../README.md#6-next-steps-and-open-questions)).

| Decision | What |
|---|---|
| Method | NUS's `train_self_play`: alternating best-response multi-agent PPO with the archive pool and the scripted slot, no APEX |
| First check (stage 5.1) | in 2-D, on the Copy of NUS 2-D game, with NUS's observation layout: the port, 3 seeds × 8 generations, scored against the 3 NUS-code hangar self-play seeds by a test written in advance |
| Then (stages 5.2, 5.3), planned | on the hangar set-up of §3: train on the STE drone model with drone lag and delay, the safety filter on every pair and 3-D, keeping NUS's reward; cross-check on the Isaac Lab physics drones ([plan](plans/2026-11-18-nus-phase5-retraining.md)) |

**The stage 5.1 test.** Every seed finishes; the learner does not fail two generations in a row; each entry's score
against NUS's scripted opponent lies inside the range of the 12 NUS-code entries; and each seed's mean strength
against the other seeds, over 3 seeds, is not told apart from the NUS code's by a pooled two-sample interval, with a
cap on how much noisier the port's seeds may be. It replaced an earlier per-cell rule (every cross-play cell inside the
NUS 95 % interval), which would fail the NUS code's own seeds against each other. Even a PASS will mean only that this
screen for a broken learner does not tell the port apart from NUS's code; it will not mean "equivalent".

| Step | Status (19 Nov 2026) | Evidence |
|---|---|---|
| R0: the 24 NUS-code hangar entries converted and scored as the reference | PASS: 24 of 24 within 0.02 units (largest 0.0092); seed values match the 256-game matrix | T29, [record](../records/2026-11-18_nus_phase5_r0_reference_record.md) |
| N0: untrained actors scored as the port: the test must fail them | PASS: it failed them, both intervals excluding 0 | T30, [record](../records/2026-11-18_nus_phase5_n0_negative_control_record.md) |
| C0: NUS's code, seeds 101, 201, 301, scored as the port: the test must pass them | PASS: both intervals contain 0 (Guards −0.027, Strikes +0.108) | T33, [record](../records/2026-11-19_nus_phase5_c0_positive_control_record.md) |
| Stage 5.1: the port, seeds 1001, 2001, 3001 | running, not yet a result | — |
| Pilots (short runs, no gates): STE's simple stand-in trainer against S20, with the filter | P0 INFO (speed); P1 INFO, 0 holds of 1,000: its set-up was faulty (γ 0.99 per tick, a hold rewarded only at the 2,400-tick time-out, a non-zero starting mean); the fixed P1b: runs 1–3 ABORTED (starved GPU, reboot), run 4 INFO, **829 holds of 1,000** against S20 (Parked Guard 429), its signal met: the **STE Guard policy** ([training recipe](TRAIN_A_GUARD.md)); P2 ABORTED twice | T25–T28, T32, T39–T41; [the STE Guard policy](WHAT_WE_FOUND.md#7-ste-guard-policy-trained-in-test-5-conditions) |
| A faster safety-filter path on the GPU (opt-in, off by default) | INFO; it showed the existing filter's GPU answer depends on the batch size, and about 40 % of Parked Guard v S20 games do not converge in 1,000 sweeps (ticks 30–33) | T31, [record](../records/2026-11-18_filter_cuda_graph_record.md) |

P1 tested a mis-set learner; it does not show that a learner cannot find the "filter as a wall" defence.

**The contact-tag track** (a Guard drone touching a Strike drone) is separate: this port is contact-free, and the
programme's design review (FR&PDR) treats contact separately ([plan](plans/2026-11-17-contact-tag-track.md), DRAFT).

## How to run it again

[How to run it yourself](RUN_IT_YOURSELF.md), levels D and E: rebuild the local files from a NUS clone (they come out
byte-identical to STE's) or use the PROVISIONAL files, then repeat a test; level F: [training recipe](TRAIN_A_GUARD.md).
Every script and flag: [training scripts, NUS jobs](TRAINING.md#nus-jobs).
