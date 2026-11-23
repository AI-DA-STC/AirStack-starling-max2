READ FIRST · TRAINING SIMULATOR ONLY: what this folder is, what was done with NUS's code, and where to go next.

# svg_training: drone teams that learn in a simulator

**For** NUS researchers and anyone new here; no drone, ROS or Isaac knowledge is assumed. **STE**: the lab that wrote
this repository. *Italic* terms are defined in the [glossary](docs/GLOSSARY.md). Every number was observed in a
training simulator; nothing in this folder has flown. T numbers (T15, …) are rows of the [run ledger](records/LEDGER.md),
each with its record; PASS and FAIL mean a pass mark set before the run was met or missed, INFO means measured with
no pass mark.

**The rules and the main learnings on one page:** [overview](docs/OVERVIEW.md).

## At a glance: what was done

The whole story on one screen; sections 1–8 below give the numbers, caveats and records behind each line.

![What was done: train with NUS's code (JAX) in NUS's 2-D game; copy the game and convert the policies to PyTorch (checked exact); test NUS's policies under STE drone conditions (Strike reaches 9 to 979 of 1,000: they fail); retrain in STE conditions: the STE Guard policy holds 829 of 1,000; STE's copy of NUS's training method: stage 5.1 FAIL, route paused; since 20 November STE trains its own teams in a game with a tag](docs/figures/overview_story.png)

**The six tests** (G19 vs S20; the same 1,000 starts in every test), and on the right, in Test 5 conditions, how often
each Guard holds the zone:

![The six tests: Strike reaches of 1,000 games for G19 vs S20 rise from 9 (Test 1, NUS conditions) through 17 and 43 to 740 (Test 4, safety filter), 983 (Test 5, 3-D) and 979 (Test 6, Isaac Lab); in Test 5 conditions the Guard holds the zone in 17 (G19), 429 (Parked Guard) and 829 (STE Guard policy) of 1,000 games](docs/figures/overview_tests.png)

*Figures drawn by `scripts/make_overview_figures.py`.*

### The whole story

1. **Trained with NUS's code (JAX)**, in NUS's conditions. Gave G19, S20, P3G and P3S. *(Phase 2a)*
2. **Copied NUS's game into PyTorch.** Same conditions, checked it matches exactly. *(Phase 2)*
3. **Converted the policies to PyTorch.** Same conditions, checked they act the same. *(Phase 3)*
4. **Tested the policies, changing conditions one at a time.** Nothing was trained here. *(Phase 4)*

   | Test | Conditions | Strike reaches, of 1,000 |
   |---|---|---|
   | 1 | NUS's conditions, in PyTorch (the baseline) | 9 |
   | 2 | + STE game engine: 0.6 s decisions, walls, simple keep-apart | 17 |
   | 3 | + drone delay and lag | 43 |
   | 4 | + **safety filter**: no pushing | **740** |
   | 5 | + **3-D**: over and under | **983** |
   | 6 | same, on **Isaac Lab** physics drones (test only) | **979** |

   **Why it breaks:** NUS's Guards learned to **push** Strikes away, which STE drones cannot do (Test 4). In 3-D,
   Strikes also slip over or under (Test 5). ("Likely": Test 4 changes two things at once; see section 5.)
5. **Retraining, so a policy works in STE conditions.** *(Phase 5; paused on 20 November)*
   - **STE Guard policy (pilot P1b):** trained in **Test 5 conditions**, on the STE drone model in PyTorch, not in Isaac
     Lab. **Holds 829 of 1,000.** ✅ It learned a different defence: spread out inside the zone and the safety filter
     likely acts like a wall. On the Isaac Lab physics drones, without retraining, it holds 856 (831 in the PyTorch
     game on the same starts; [record](records/2026-11-21_ste_l03_transfer_record.md)).
   - **STE port of NUS's training method (PyTorch):** checked in NUS's conditions (stage 5.1): **FAIL** on the test fixed
     in advance. Two of three seeds pass every part and the policies are as strong as NUS's, but one seed fails two parts
     by small margins ([record](records/2026-11-19_nus_phase5_s51_method_match_record.md)). Under the plan this stops
     stage 5.2 (training with it in STE conditions); on 20 November STE paused this route.
6. **Since 20 November: STE's own training** in a game with a **tag** (a Guard drone close enough to a Strike drone
   takes it out, and both leave; rules set at gate G0, 22 November): a 6.5 m arena, tag distance 1.6 m first. At
   1.6 m, trained teams beat STE's hand-written tactics against the opponent they trained on in two of three cases;
   at 1.15 m they stay below them. The rules and these results, each with its record: [overview](docs/OVERVIEW.md).

**In one line:** trained in NUS's game, tested in the STE drone game in PyTorch (NUS's policies failed), retrained in STE drone conditions
(the STE Guard policy works), then STE's own game with a tag (see the [overview](docs/OVERVIEW.md)).

### NUS's conditions vs STE drone conditions

| | NUS's game (original) | STE drones | Added in |
|---|---|---|---|
| **How a drone moves** | a point; each step it simply jumps to its new position, no inertia | a drone given a **speed command** through CMU's commander, with the **delay and lag** of a real Starling; it speeds up and slows down gradually | Test 3 |
| **Decision timing** | one action per game step | one action held for **0.6 s** (scale: 1 unit = 0.4 m, 1 step = 0.6 s) | Test 2 |
| **Contact between drones** | drones may touch; overlapping drones **push each other apart**, so a Guard can shove a Strike away | **no contact allowed.** Test 2 uses a simple keep-apart rule between opposing drones; Test 4 uses the real **safety filter** from the flight software: every pair, team-mates too, slows or swerves to stay **1.10 m apart** | Tests 2 and 4 |
| **Height** | flat 2-D plane | **free height (3-D)**: drones fly at about 1.2 m, but the filter can move them up or down, so Strikes can pass **over or under** Guards | Test 5 |
| **Arena** | open plane, no walls (Guards kept inside a circle of 8 units) | the **7.5 m hangar**, with walls | Test 2 |
| **Physics** | none (simple maths) | **Isaac Lab**: full rigid-body Starling drones with a PX4-style controller | Test 6 |

## 1. Overview

STE flies small indoor drones (ModalAI *Starling* 2 Max) with CMU's flight software, AirStack. This folder holds a
drone-team game that runs thousands of copies at once on one graphics card (GPU): a Guard team holds a circular zone,
a Strike team tries to reach it. It was used to test policies trained with NUS's self-play code under STE drone conditions, and to train a Guard team
in those conditions. Since 20 November 2026 STE also trains its own teams in a game with a tag (section 6.3).

**Policies named on these pages.** NUS's code calls the teams `defender` and `attacker`: here, defender (Guard team)
and attacker (Strike team), then Guard and Strike. NUS shared its code, not trained checkpoints, so STE trained the
NUS-code policies itself with that code. Full definitions: [glossary, policies](docs/GLOSSARY.md#policies).

| Label | NUS run folder → entry | Trained by | Code / simulator / library |
|---|---|---|---|
| G19 | `2026-11-17_selfplay_3v3_seed2` → `archive/0019_defender` | STE, using NUS's code (NUS gave no checkpoints) | NUS self-play runner / NUS 2-D game / JAX |
| S20 | same run → `archive/0020_attacker` | STE, using NUS's code | same |
| P3G | `2026-11-17_fixed_apf_3v3_defender` | STE, using NUS's code | NUS fixed-opponent runner / NUS 2-D game / JAX |
| P3S | `2026-11-17_fixed_apf_3v3_attacker` | STE, using NUS's code | same |
| APF defender / APF attacker | NUS's scripted `apf` opponent (config `scripted_opponent: apf`) | written by NUS, no training | ported to PyTorch by STE |
| Parked Guard | — | STE baseline, no training | every Guard drone commands zero speed from its start point; one starts at the zone centre |
| STE Guard policy | `pilot_p1b` run 4 | STE | skrl IPPO / STE drone model, Test 5 conditions / PyTorch |

G19 = Guard of generation 19 and S20 = Strike of generation 20 of self-play seed 2; P3G and P3S = the Guard and Strike
converted in Phase 3 (each trained against NUS's scripted opponent); IPPO = independent PPO, one learner per drone.
The STE drone model and Test 5 conditions are defined in section 3, pilot P1b in section 6.

## 2. Porting NUS's code

The port ran in numbered phases. STE installed NUS's `area-denial-continuous-space-self-play` code (commit `2d2b904`) unchanged, trained the policies
above with it on the STE *hangar set-up* (1 unit = 0.40 m, 1 step = 0.60 s, a 7.5 m square arena), then copied the
game and the trained policies into the STE pipeline (PyTorch). Each copy was checked against NUS's code; every PASS
grades the copy, never NUS's code.

**Why NUS's JAX code was converted to PyTorch.** STE's game engine, STE's drone model (delay and lag), the copy of the
safety filter and Isaac Lab all run in PyTorch on the GPU. Testing NUS's policies under STE drone conditions means
running them inside that same loop. Keeping the policies in JAX would move data between two libraries at every step
and hold both libraries' memory on one GPU; that route was not tried. Converted policies also run without NUS's code
installed, so the tests can be replayed from this repository alone. Retraining in STE conditions needs NUS's training
method in the same library as the game. The conversion was checked before any other test: the same game step by step
(Phase 2) and the same actions (Phase 3).

| Phase | What | Simulator | Result | Evidence |
|---|---|---|---|---|
| 1 | NUS's code, installed | NUS 2-D game (JAX) | 65 of NUS's 66 tests pass; the one failure checks an older Guard safety distance, which NUS confirmed is out of date | [record](records/2026-11-17_nus_phase1_install_record.md) (INFO, written after the fact) |
| 2a | policies trained with NUS's code: 3 self-play seeds × 8 generations (NUS default 32), seed 2 continued to 20 | NUS 2-D game (JAX) | G19 v S20: Strike reaches the zone in 0.023 of 256 games (NUS's evaluator and starts) | [training](records/2026-11-17_nus_phase2a_training_record.md), [matrix](records/2026-11-18_nus_selfplay_matrix_record.md) (INFO, after the fact) |
| 2 | the game, copied to PyTorch | Copy of NUS 2-D game (PyTorch) | the same game step by step: position error ≤ 5.7e-6 units (limit 1e-4). PASS | T15, [record](records/2026-11-17_nus_phase2_parity_record.md), [the copy checked](docs/WHAT_WE_FOUND.md#1-copy-of-nus-2-d-game-pytorch-matches-nus-2-d-game-jax) |
| 3 | the policies, converted to PyTorch | Copy of NUS 2-D game (PyTorch) | action error ≤ 0.0105 units (limit 0.02); reach counts inside the 95 % interval of NUS's code. PASS | T16, [record](records/2026-11-18_nus_phase3_conversion_record.md); T17, [record](records/2026-11-18_nus_phase4_w3_reference_gates_record.md); [the conversion checked](docs/WHAT_WE_FOUND.md#2-converted-policies-match-the-jax-originals) |

### The same match in NUS's JAX code and in the PyTorch copy

Each match-up was played on the same 1,000 starts with NUS's JAX policies and with the converted PyTorch policies.
Three ways of playing:

- **NUS's JAX game**: NUS's own game and NUS's JAX policies, end to end;
- **PyTorch copy + JAX policies**: the Copy of NUS 2-D game (PyTorch), with NUS's JAX policies choosing every action;
- **PyTorch copy + converted**: the Copy of NUS 2-D game (PyTorch) with the converted PyTorch policies.

| Match-up (Guard vs Strike) | NUS's JAX game | PyTorch copy + JAX policies | PyTorch copy + converted | Games that differ | Evidence |
|---|:-:|:-:|:-:|:-:|---|
| P3G vs APF attacker | not run | 48 | 46 | 6 | T16, [record](records/2026-11-18_nus_phase3_conversion_record.md) |
| APF defender vs P3S | not run | 1,000 | 1,000 | 0 | T16, [record](records/2026-11-18_nus_phase3_conversion_record.md) |
| G19 vs S20 | 17 | 17 | 15 | 8 | T17, [record](records/2026-11-18_nus_phase4_w3_reference_gates_record.md); T42, [record](records/2026-11-19_nus_pair_g19_p3s_jax_vs_pytorch_record.md) |
| G19 vs P3S | 991 | 991 | 991 | 2 | T42, [record](records/2026-11-19_nus_pair_g19_p3s_jax_vs_pytorch_record.md) |

*Strike reaches the zone, of 1,000 games. "Games that differ": games whose outcome with the converted policies differs from
the JAX policies (in NUS's JAX game where it was run, otherwise in the PyTorch copy). The counts agree within chance.*

**What the policy names mean:**

| Name | Team | What it is |
|---|---|---|
| **P3G** | Guard | trained against NUS's scripted attacker (the set-up of NUS's October report); trained by STE with NUS's code |
| **P3S** | Strike | trained against NUS's scripted defender; trained by STE with NUS's code |
| **G19** | Guard | from NUS's self-play (Guard and Strike trained in turns), generation 19; trained by STE with NUS's code |
| **S20** | Strike | the same self-play run, generation 20 |
| **APF attacker** | Strike | NUS's scripted Strike: hand-written rules (a potential field), no learning |
| **APF defender** | Guard | NUS's scripted Guard: hand-written rules, no learning |

**Videos** (one game each; the two in a row are not the same start; click for the full video):

| Match-up | NUS's JAX game | Copy of NUS 2-D game (PyTorch) |
|---|:-:|:-:|
| **P3G vs APF attacker**<br>Guard holds | <a href="docs/media/nus/nus_fixed_guard_vs_scripted_strike.mp4"><img src="docs/media/nus/nus_fixed_guard_vs_scripted_strike.gif" width="320" alt="P3G vs APF attacker, NUS JAX game"></a> | <a href="docs/media/nus/phase3/guard_game0.mp4"><img src="docs/media/nus/phase3/guard_game0.gif" width="320" alt="P3G vs APF attacker, PyTorch copy"></a> |
| **APF defender vs P3S**<br>Strike reaches the zone | <a href="docs/media/nus/nus_fixed_strike_vs_scripted_guard.mp4"><img src="docs/media/nus/nus_fixed_strike_vs_scripted_guard.gif" width="320" alt="APF defender vs P3S, NUS JAX game"></a> | <a href="docs/media/nus/phase3/strike_game0.mp4"><img src="docs/media/nus/phase3/strike_game0.gif" width="320" alt="APF defender vs P3S, PyTorch copy"></a> |
| **G19 vs S20**<br>Guard holds | <a href="docs/media/nus/nus_selfplay_s2_g19_vs_s2_s20.mp4"><img src="docs/media/nus/nus_selfplay_s2_g19_vs_s2_s20.gif" width="320" alt="G19 vs S20, NUS JAX game"></a> | <a href="docs/media/nus/w3/archive_arm_G19_vs_S20_game0.mp4"><img src="docs/media/nus/w3/archive_arm_G19_vs_S20_game0.gif" width="320" alt="G19 vs S20, PyTorch copy"></a> |

**Same start, side by side** (left: NUS's JAX game; right: Copy of NUS 2-D game (PyTorch) with the converted policies;
click for the full video):

| Match-up | Same start: NUS's JAX game (left), PyTorch copy (right) |
|---|:-:|
| **G19 vs S20**, game 139<br>Guard holds in both | <a href="docs/media/nus/pairs/g19_vs_s20_game139_same_start.mp4"><img src="docs/media/nus/pairs/g19_vs_s20_game139_same_start.gif" width="640" alt="G19 vs S20, game 139, NUS JAX game and PyTorch copy side by side"></a> |
| **G19 vs P3S**, game 0<br>Strike reaches the zone in both | <a href="docs/media/nus/pairs/g19_vs_p3s_game0_same_start.mp4"><img src="docs/media/nus/pairs/g19_vs_p3s_game0_same_start.gif" width="640" alt="G19 vs P3S, game 0, NUS JAX game and PyTorch copy side by side"></a> |

The paths start equal and drift apart slowly in long games: in G19 vs S20 game 0 the drones are 0.04 units apart at step
100 and 0.53 at step 200. The drift also appears with NUS's JAX policies in the PyTorch copy, so the conversion does not
cause it; likely small number differences that grow over many steps (not tested by a control). In NUS's own JAX game,
every G19 vs S20 game the Guard team holds has a Strike drone go more than 10 units from the zone centre (game 139: one
Strike drone near x = −15 m in both games). S20's drones wandering away is S20's own behaviour, not an effect of the copy.
More clips: [G19 vs S20 game 0](docs/media/nus/pairs/g19_vs_s20_game0_same_start.mp4),
[G19 vs P3S game 121, a Guard hold](docs/media/nus/pairs/g19_vs_p3s_game121_same_start.mp4).

P3G and P3S used NUS's learning settings with two changes: 3,000 updates per team (76.8 million environment steps,
about 6.5 minutes; NUS's default has no practical limit) and the hangar arena (start distance and Guard boundary 8 units
instead of 20). Their strength is therefore not directly comparable with the policies in NUS's October report.

## 3. The game: NUS 2-D game vs STE drone set-up

This section compares the two set-ups of the NUS port's tests (sections 4–6.2); neither has a tag. STE's own game since
gate G0 (22 November 2026) adds a tag and plays in a 6.5 m arena: its rules are in the [overview](docs/OVERVIEW.md).
In the NUS port, both sides play the same Strike vs Guard game: 3 Guard drones hold a zone of 1.6 m radius (NUS: 4
units) at the centre, 3 Strike drones, 1.5 times as fast, try to reach it, and a game lasts 200 steps (120 s on the hangar set-up).
They differ in how the drones move and meet. The STE column is the set-up of Test 5 (the STE Guard policy was trained
in it) and Test 6 (the same on the Isaac Lab physics drones); the tests of section 4 add its conditions one at a time,
and the table says where each enters.

| | NUS 2-D game | STE drone set-up |
|---|---|---|
| Movement | point drones that jump each step by a move up to the team's cap (Guard 0.5, Strike 0.75 units: 0.20 m and 0.30 m per step on the hangar set-up) | each speed command goes through a copy of CMU's commander, then the delay and lag of a model fitted to one Starling flight log (from Test 3; exploratory: it answers more slowly than the real drone); in Test 6, rigid-body Starling models flown by a copy of PX4's control loops. Same team speeds: Guard 0.333 m/s, Strike 0.50 m/s |
| Contact | a soft push keeps the teams apart within each step (1.2 m around a Guard drone, 1.0 m around a Strike drone, on the hangar set-up), so pushing a Strike drone aside is allowed; team-mates may overlap | no contact: the safety filter makes both drones of any close pair give way, team-mates included, keeping them 1.10 m apart (from Test 4; Tests 2–3 use the push-apart). It acts on speed commands, not positions, so drones can come closer: 1.083 m in a test on the STE drone model; with the STE Guard policy in Test 5 conditions the closest Guard–Strike approach was 0.87 m in 3-D, and 0.5 % of games had a rule breach (closer than 1.10 m) |
| Height | 2-D: every drone in one plane | every drone at 1.2 m in Tests 2–4; free height from Test 5: the policies send no vertical command, but with a ±1 mm start jitter the filter's give-way can turn vertical, and drones pass over or under each other |
| Arena and walls | no walls; Guard drones kept inside a circle of 8 units (3.2 m), Strike drones start 8 units (3.2 m) from the centre (`defender_boundary` and `spawn_distance` 8.0 on the hangar set-up; NUS's defaults are 20 units) | the hangar box: a 7.5 m square with walls at ±3.75 m (from sub-test 2.2), inside the hangar's usable flying box of about 7.6 m × 7.9 m; the same zone and starts. Flying it would first need the flight software's keep-in fence (±3.25 m today) moved |
| Decision rate | one action per step; NUS's game has no seconds, and STE's scale makes a step 0.60 s | one action per 0.60 s, held for 12 ticks of 0.05 s (from Test 2) while the commander and the filter act every tick |
| Simulator / library | NUS 2-D game, JAX (NUS's code); for Test 1, STE's Copy of NUS 2-D game in PyTorch | STE game engine and STE drone model, PyTorch (Tests 2–5); Isaac Lab physics drones on Isaac Sim 5.1 (Test 6) |
| One game | [![G19 vs S20 · NUS 2-D game (JAX) · Guard holds](docs/media/nus/nus_selfplay_s2_g19_vs_s2_s20.gif)](docs/media/nus/nus_selfplay_s2_g19_vs_s2_s20.mp4)<br>G19 vs S20 · NUS 2-D game (JAX) · Guard holds | [![G19 vs S20 · Test 5: STE drone model + free height · Strike reaches the zone](docs/media/nus/phase4/row_5/G19_vs_S20_strike_win.gif)](docs/media/nus/phase4/row_5/G19_vs_S20_strike_win.mp4)<br>G19 vs S20 · Test 5: STE drone model + free height · Strike reaches the zone |

Values: [NUS port report, NUS's game](docs/NUS_PORT_REPORT.md#1-the-nus-code-three-branches) and
[the hangar geometry](docs/NUS_PORT_REPORT.md#3-phase-0-answers-and-the-hangar-geometry). Click a picture for the
full video. Terms, one line each (all in the [glossary](docs/GLOSSARY.md)):

- *Copy of NUS 2-D game*: STE's batched PyTorch copy of NUS's game, checked step by step against it (section 2).
- *STE game engine*: STE's batched game in PyTorch; in Test 2 with NUS's speeds, zone and scoring, square walls and the push-apart.
- *Push-apart*: an STE rule that cuts short a move that would bring a drone within 1.10 m of an opposing drone (Tests 2–3).
- *STE drone model*: a point drone that follows its speed command through a copy of CMU's commander (the AirStack
  program that turns speed commands into drone instructions), then the delay and lag of a model fitted to one Starling
  flight log (exploratory: it answers more slowly than the real drone).
- *Safety filter*: CMU's collision filter in the flight software; when two drones come close it makes both give way,
  keeping them 1.10 m apart.
- *Isaac Lab physics drones*: rigid-body Starling models in NVIDIA Isaac Lab (a robot-learning framework on NVIDIA's
  Isaac Sim simulator), flown by a copy of PX4's control loops (PX4: the drone's flight software).
- *Test 5 conditions*: the hangar game of Test 5 (STE drone model, safety filter on every pair, free height), the game
  the STE Guard policy was trained in.

## 4. Testing NUS's policies in the STE drone game (simulation) in PyTorch

Phase 4 scored the converted policies (G19, S20, P3G, P3S: trained by STE with NUS's code), frozen, in six tests; each test adds one real-drone condition (Tests 2 and 4
change two things at once; [test results](docs/WHAT_WE_FOUND.md#3-six-tests-towards-ste-drones)). 1,000 games per
pair, the same 1,000 starts in every test.

| Test | Played in | G19 v S20: Strike reaches of 1,000 | Evidence |
|---|---|---|---|
| 1 | Copy of NUS 2-D game, in PyTorch | 9 | T18, [record](records/2026-11-18_nus_phase4_rung1_record.md) |
| 2 | STE game engine (PyTorch), NUS rules, action held for each 0.6 s step | 17 | T19, [record](records/2026-11-18_nus_phase4_rung2_record.md) |
| 3 | STE drone model (PyTorch): + Starling delay and lag | 43 | T20, [record](records/2026-11-18_nus_phase4_rung3_record.md) |
| 4 | STE drone model: + safety filter on every drone pair | 740 | T22, [record](records/2026-11-18_nus_phase4_rung4_2_record.md) |
| 5 | STE drone model: + free height (3-D) | 983 | T23, [record](records/2026-11-18_nus_phase4_rung5_record.md) |
| 6 | Isaac Lab physics drones (Isaac Sim 5.1) | 979 | T24, [record](records/2026-11-18_nus_phase4_rung6_record.md) |

Terms: [the game, section 3](#3-the-game-nus-2-d-game-vs-ste-drone-set-up). The records call the tests "ladder rows": Test N = ladder row N.

<a id="fig-1"></a>
![Strike reach rate along Tests 1 to 6; the axis says "row": row N = Test N](docs/figures/nus_phase4_ladder.png)

*Figure 1. Strike reach rate (with a Wilson 95 % confidence interval) of 12 pairs, G19, P3G, APF defender and Parked
Guard against S20, P3S and APF attacker, Tests 1–6 (the axis says "row": row N = Test N); dashed: the Parked Guard.
T18–T24.*

## 5. Why performance drops

- **No physical contact: the safety filter.** The NUS-code Guards likely hold by pushing Strike drones aside, which
  NUS's game allows. The safety filter makes *both* drones of every close pair give way, team-mates included, so
  pushing likely stops working (Test 4: 43 → 740). "Likely": Test 4 changes two things at once (no push, and no
  stacking of team-mates), and the two have not been split yet.
- **Drones pass above and below each other: 3-D.** With free height, Strike drones pass over or under the Guards
  (Test 5: 983); the horizontal closest approach falls while the 3-D one stays at 1.09 m.
- The Isaac Lab physics drones agree with the STE drone model (Test 6: 979). These numbers measure how policies
  trained for NUS's game transfer to STE drones, not NUS's method. Caveats beside each number:
  [test results](docs/WHAT_WE_FOUND.md#3-six-tests-towards-ste-drones).

## 6. Training in STE conditions

*Brought up to date on 23 November 2026:* sections 6.1 and 6.2 describe the NUS port's training (to 20 November);
section 6.3 STE's own training since.

Two different things were taken from NUS's code, and they must not be confused:

| What | What it is | Converted to PyTorch | Checked by |
|---|---|---|---|
| NUS's **trained policies** (G19, S20, P3G, P3S) | the finished "brains" of the drones: given what a drone sees, which way to fly | Phase 3 | Tests T16, T17, T42: same results as in JAX |
| NUS's **training method** (`train_self_play`) | the recipe that makes such policies: Guard and Strike take turns learning against each other and against the archived earlier policies (multi-agent PPO with an archive pool) | Phase 5 ("the STE port of NUS's training method", records: "route (b)") | stage 5.1, below |

In the NUS port no policy was trained in Isaac Lab: Isaac Lab was used only to test policies (Test 6), and every
training run used the STE game engine in PyTorch (the Copy of NUS 2-D game, or the STE drone model in Test 5
conditions). STE's own track has since trained a Guard team on the Isaac Lab drones (section 6.3).

### 6.1 Stage 5.1: does the STE port of NUS's training method work in NUS's own game?

The STE port trained from scratch in the Copy of NUS 2-D game (NUS's conditions, no STE drone condition), 3 times with
different random seeds (1001, 2001, 3001), 8 turns each (Guard, Strike, Guard, …; about 13 hours on the RTX 5090). Its
24 policies were then scored against the 24 policies that NUS's own code produced in the same game, on a test written
down before any result was seen (so the test cannot be bent to fit the result):

| Part | Rule fixed in advance | Why this rule | Result |
|---|---|---|---|
| a | every seed finishes all 8 turns, no numerical failure | the method runs | pass: 3 of 3 |
| b | in turns 1–6, the learner never fails two turns of the same team in a row (a turn fails when the new policy wins 50 % or less against some policy it trained against) | the method keeps learning | **fail**: seed 3001, Strike turns 4 and 6; the other two seeds have no failed turn |
| c | each policy's score against NUS's scripted opponent (APF, hand-written rules) lies inside the range of NUS's 12 policies of the same team | the policies behave like NUS's against a fixed yardstick | **fail**: 23 of 24 inside; seed 3001's Guard of turn 7 holds the zone in 0.909 of games, NUS's range 0.922–0.989 |
| d | each seed's mean strength against NUS's lineages, compared with NUS's own seeds: the 95 % interval of the difference contains 0 | the policies are as strong as NUS's | pass for both teams (Guard +0.157 [−0.008, +0.323]; Strike −0.020 [−0.464, +0.424]) |

The verdict rule, also fixed in advance: any failed part is a FAIL, and a FAIL is final (three more seeds were allowed
only for an unclear result, not for a FAIL). Before the port was scored, the test was checked both ways: it **passes**
NUS's own code run with 3 new seeds (C0) and it **fails** untrained policies (N0). Evidence: T43,
[record](records/2026-11-19_nus_phase5_s51_method_match_record.md); T30, T33.

**What the FAIL means.** The port learns, and its policies are about as strong as NUS's (part d). Two of the three
seeds pass every part. The failure sits in one seed and in small margins. It does **not** show that the conversion is
broken. It also does not show that the port equals NUS's method: three seeds cannot tell whether the port has such bad
turns more often than NUS's code (NUS's own seed 1 also had one failed turn, T38). The honest reading: not proven equal,
not proven broken.

**What follows from it.** The plan made stage 5.2, training with the STE port of NUS's training method in STE drone
conditions, depend on a 5.1 PASS, so stage 5.2 did not start (its training environment is built). On 20 November STE
paused this route and went on with its own training: the STE Guard policy below, then STE's own game (section 6.3).

### 6.2 The STE Guard policy: a Guard trained in STE drone conditions

The STE Guard policy was the first policy trained in STE drone conditions. It is not a new game: it plays the
game of Test 5, the same game NUS's policies were tested in. What is STE's own is the trainer and its settings:

| | STE Guard policy (pilot P1b) | NUS's policies (G19, S20) |
|---|---|---|
| Game rules | NUS's hangar game: zone, start distance, game length, win rule | the same |
| Conditions | Test 5: STE drone model (Starling delay and lag), safety filter, free height (3-D), one decision per 0.6 s | NUS 2-D game |
| Trainer | STE's stand-in trainer (skrl IPPO: one PPO learner per Guard drone) | NUS's self-play MAPPO |
| Who it learns against | S20 only (fixed, not learning) | each other, in turns |
| Reward | +1 if the Guard team holds the zone to the end, −1 if a Strike drone reaches it; nothing in between | NUS's reward, with a distance term |
| What the drone sees | STE's observation format (the lab's policy interface) | NUS's observation layout |
| Training | 2.1 h on the RTX 5090, one seed | 8–20 turns per seed |

Two fixes from the first pilot (P1, 0 holds of 1,000) made it work: the untrained Guards start by standing still, and
they decide once per 0.6 s (as NUS's policies do in the tests) so the end-of-game reward is not discounted away.
Result: it holds the zone against S20 in **829 of 1,000** games in Test 5 conditions, against 429 for the Parked Guard
(an STE baseline that does not move) and 17 for NUS's G19 (evidence: T41,
[record](records/2026-11-19_nus_phase5_pilot_p1b_run4_record.md)). Its Guards spread out across the zone and the
safety filter likely acts as a wall around each one (read from the videos, not tested). On the Isaac Lab physics
drones, without retraining, it holds 856 of 1,000 against 831 in the PyTorch game on the same starts (evidence: T49,
[record](records/2026-11-21_ste_l03_transfer_record.md)). Limits: one seed, one opponent. Details: [the result](docs/WHAT_WE_FOUND.md#7-ste-guard-policy-trained-in-test-5-conditions),
[training recipe](docs/TRAIN_A_GUARD.md), [training method results](docs/WHAT_WE_FOUND.md#6-ste-port-of-nus-training-method-stage-51-fail).

### 6.3 STE's own training, since 20 November 2026

STE now trains its own Guard and Strike teams in its own game: the same zone, speeds and 120 s game, with the safety
filter on every pair, in a 6.5 m arena, and with a **tag**: a Guard drone within the tag distance of a Strike drone
takes it out and both leave. The rules were set at gate G0 (the owner's decision point, 22 November): 1.6 m first,
1.15 m in later training. What the first runs showed, each observed in the training simulator against the opponent
the team trained on: at 1.6 m, trained teams beat STE's hand-written tactics in two of three cases and draw level in
the third; at 1.15 m both sides stay below them; a Guard team trains as well on the Isaac Lab drones as in the fast
PyTorch engine, at about 5 times the GPU time. Numbers, figures and limits on one page: [overview](docs/OVERVIEW.md);
the plan and its working folder: [ste_learning/](ste_learning/README.md). Nothing has flown.

## Watch it

Top-down view: Guard team blue circles, Strike team orange triangles, the zone green. The pictures play here; click
one for the full video. Observed in the training simulator; nothing here has flown. All 275 clips of the NUS port,
each with a preview that plays in the page: [videos of the NUS port](docs/media/nus/README.md).

| | |
|---|---|
| [![G19 vs S20 · NUS 2-D game (JAX) · Guard holds](docs/media/nus/nus_selfplay_s2_g19_vs_s2_s20.gif)](docs/media/nus/nus_selfplay_s2_g19_vs_s2_s20.mp4)<br>G19 vs S20 · NUS 2-D game (JAX) · Guard holds | [![G19 vs S20 · Test 1: Copy of NUS 2-D game (PyTorch) · Guard holds](docs/media/nus/phase4/row_1/G19_vs_S20_hold.gif)](docs/media/nus/phase4/row_1/G19_vs_S20_hold.mp4)<br>G19 vs S20 · Test 1: Copy of NUS 2-D game (PyTorch) · Guard holds |
| [![G19 vs S20 · Test 4: STE drone model + safety filter · Strike reaches the zone](docs/media/nus/phase4/row_4/G19_vs_S20_strike_win.gif)](docs/media/nus/phase4/row_4/G19_vs_S20_strike_win.mp4)<br>G19 vs S20 · Test 4: STE drone model + safety filter · Strike reaches the zone | [![G19 vs S20 · Test 5: STE drone model + free height · Strike reaches the zone](docs/media/nus/phase4/row_5/G19_vs_S20_strike_win.gif)](docs/media/nus/phase4/row_5/G19_vs_S20_strike_win.mp4)<br>G19 vs S20 · Test 5: STE drone model + free height · Strike reaches the zone |
| [![G19 vs S20 · Test 6: Isaac Lab physics drones · Strike reaches the zone](docs/media/nus/isaac/g19_vs_s20_strike_win_1.gif)](docs/media/nus/isaac/g19_vs_s20_strike_win_1.mp4)<br>G19 vs S20 · Test 6: Isaac Lab physics drones · Strike reaches the zone | [![G19 vs S20 · Test 6: Isaac Lab physics drones · Guard holds (21 of 1,000)](docs/media/nus/isaac/open_g19_vs_s20_hold_1.gif)](docs/media/nus/isaac/open_g19_vs_s20_hold_1.mp4)<br>G19 vs S20 · Test 6: Isaac Lab physics drones · Guard holds (21 of 1,000) |
| [![Parked Guard vs S20 · Test 5: STE drone model + free height · Guard holds (429 of 1,000)](docs/media/nus/phase4/row_5/ParkedGuard_vs_S20_hold.gif)](docs/media/nus/phase4/row_5/ParkedGuard_vs_S20_hold.mp4)<br>Parked Guard vs S20 · Test 5: STE drone model + free height · Guard holds (429 of 1,000) | [![STE Guard policy vs S20 · Test 5 conditions · Guard holds (829 of 1,000)](docs/media/nus/pilots/p1b_run4_final_t1472_best_hold_slot0.gif)](docs/media/nus/pilots/p1b_run4_final_t1472_best_hold_slot0.mp4)<br>STE Guard policy vs S20 · Test 5 conditions · Guard holds (829 of 1,000) |

## 7. Next steps and open questions

*Brought up to date on 23 November 2026.* STE's learning track ([ste_learning/](ste_learning/README.md)): its first
phase, L0, settled which game to train and whether Isaac Lab can train it, and closed at gate G0 on 22 November; its
second, L1, makes the training drone more like the real Starling. Where the work stands: the
[status page](ste_learning/status/STATUS_LATEST.md). Work on the STE port of NUS's training method is paused after
its stage 5.1 FAIL (20 November).
Five questions to NUS:

1. Is any rule that matters missing from the Copy of NUS 2-D game (PyTorch)?
2. Would NUS retrain with its own code under action hold, delay, the safety filter and free height?
3. Is `train_self_play` (no APEX) the right baseline for the STE port of NUS's training method?
4. Is 3 v 3 in 3-D with no drop-outs the right first goal?
5. Should any NUS setting change for a slower environment?

## 8. Run it yourself

Commands for every level, with what each must print: [how to run it yourself](docs/RUN_IT_YOURSELF.md). Badges:
`none` = any laptop, no GPU; `GPU` = an NVIDIA GPU; `Isaac` = NVIDIA Isaac Lab 2.3.2 on Isaac Sim 5.1.0.

| Level | What | Needs | Time | Verified from a fresh clone |
|---|---|---|---|---|
| A | watch the games | `none` | 5 min | yes |
| B | install, run the tests, score a strategy | `none` (Python 3.11, any CPU) | ~5 min + ~10 min tests | yes (0 failed) |
| C | the same at full size | `GPU` | ~1 h | not yet |
| D | repeat Tests 1–5 from the PROVISIONAL files (the converted weights and STE settings, committed only so the numbers can be repeated) | `none` | under 2 min for Test 1 (CPU) | yes (Test 1) |
| E | Test 6 and the Isaac Lab clips | `GPU` `Isaac` | hours | not yet |
| F | train the STE Guard policy: [training recipe](docs/TRAIN_A_GUARD.md) | `none` for the CPU check, `GPU` for the run | 2 min (CPU check); 2.1 h (RTX 5090) | not yet (the CPU check ran in a lab worktree) |

| Page | What it holds |
|---|---|
| [What we found](docs/WHAT_WE_FOUND.md) | every result, with its caveat and record |
| [NUS port report](docs/NUS_PORT_REPORT.md) | the NUS port, phase by phase |
| [The game](docs/THE_GAME.md) | the pipeline in one picture; the game as an RL environment |
| [Plug in your code](docs/PLUG_IN_YOUR_CODE.md) | connect a strategy or a training method, and score it |
| [Glossary](docs/GLOSSARY.md) | every term: NUS terms and the terms used here |
| [Run ledger](records/LEDGER.md) | every run, one row each ([how to read a record](records/README.md)) |
| [Map of the pages](docs/README.md) | every page with its label, and the history |

Files marked INTERNAL are STE's working notes and AI-assistant set-up; they are not needed. AI coding assistants did
much of this work; every number links to the record of the run that produced it.
