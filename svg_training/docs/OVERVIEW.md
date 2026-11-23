READ · TRAINING SIMULATOR ONLY: the two games' rules and the seven main learnings so far, each with its record.

# Overview: the game and what the work has shown

Two teams of drones play one game: a Guard team holds a circular zone and a Strike team tries to reach it. STE first
tested how controllers trained in NUS's game (policies) do under STE's drone conditions; there, NUS's Guard team
likely lost its main tool, pushing Strike drones aside. These tests measure how those trained policies carry over to
STE's drones, not NUS's training method. STE then trains its own teams in a game with a *tag* (a game rule: a Guard
drone close enough to a Strike drone takes it out). Against the opponent they trained on, these teams beat STE's
*hand-written tactics* (scripted teams, no training) at a 1.6 m tag, and stay below them at 1.15 m. Every result
was observed in a training simulator, except one analysis of real flight logs.

> **Training simulator only. Nothing here has flown. A tag is a game rule, not a contact.**

## The two games

| | NUS's game, as the NUS port ran it (hangar scale) | STE's game (rules set at gate G0, 22 November 2026) |
|---|---|---|
| Teams | 3 Guard v 3 Strike drones | 3 v 3 for training (other sizes for scoring: game spec sheet) |
| Space | 2-D: all drones in one plane; no walls; Guards kept inside a 3.2 m circle | 3-D, in a 6.5 m square arena (height rules: game spec sheet) |
| Zone | circle of 1.6 m radius at the centre | circle of 1.6 m radius at the centre |
| Starts | Strike drones 3.2 m from the centre | Strike drones 2.75 m from the centre (Guard starts: game spec sheet) |
| Game length | 200 steps of 0.60 s = 120 s | 120 s |
| How a Guard stops a Strike | a soft push keeps the teams apart; pushing a Strike aside is allowed | a 1-for-1 tag: a Guard within the tag distance of a Strike takes it out and leaves too |
| Tag distance (centre to centre) | none | 1.6 m (1.15 m in later training) |
| Safety filter (the flight software's collision filter: drones give way to keep about 1.10 m apart) | none in NUS's game; STE added it in its fourth test | on every pair of drones, both teams |
| Speeds | Guard 0.33 m/s, Strike 0.50 m/s (0.20 and 0.30 m per step) | Guard 0.33 m/s, Strike 0.50 m/s |
| Decisions | one per 0.60 s step | one per 0.6 s (a working value: game spec sheet) |
| Full values | [README section 3](../README.md#3-the-game-nus-2-d-game-vs-ste-drone-set-up), [NUS port report section 3](NUS_PORT_REPORT.md#3-phase-0-answers-and-the-hangar-geometry) | [game spec sheet](../ste_learning/GAME_SPEC.md) (every value with its label and source) |

At the 1.15 m tag, the band between the filter's 1.10 m and the tag is 5 cm. In a real Starling's flight logs the
position estimate differs from motion capture by about 1 cm in hover, its spread reaches about 2.5 cm per axis while
moving, and between two drones the errors add, so a tag judged on the estimate would not be clean at that edge
([flight-log analysis](../records/2026-11-23_ste_l13_fit_record.md)); judging tags on motion capture avoids it.

![STE's game seen from above: the 6.5 m arena, the 1.6 m zone, the 2.75 m Strike start ring and the tag distances](figures/g0_report/game_diagram.png)

**Figure 1.** STE's game seen from above; the game itself is 3-D. It shows the arena, the zone, the Strike start ring,
the two tag distances and the filter distance; the Guard start disc, keep-in square and heights it also shows are
working values. Drawn from the game files by `scripts/make_g0_report_figures.py`.

![Left: Strike reaches per 1,000 games in Tests 1 to 6; right: Guard holds against S20 for G19, a parked Guard and the STE Guard policy](figures/overview_tests.png)

**Figure 2.** Left: how often S20 reached the zone against G19 in Tests 1 to 6, as STE's conditions were added one
per test. Right: in Test 5's conditions, how often each Guard team holds the zone against S20. Drawn by
`scripts/make_overview_figures.py`.

## Seven learnings

Counts are games out of 1,000. *G19* (Guard) and *S20* (Strike) are policies STE trained in NUS's game with NUS's own
code. *Tests 1 to 6* play G19 against S20 while STE's conditions are added one at a time: NUS's game copied to STE's
PyTorch code (1); STE's game engine with 0.6 s decisions and walls (2); the drone's delay and lag (3); the safety
filter (4); free height (5); Isaac Lab physics drones (6). The *fast engine* is STE's point-drone simulator; *Isaac
Lab* simulates the Starling as a rigid body. A *seed* is one training run from one random start.

| Learning | Number | Evidence |
|---|---|---|
| 1. The safety filter and free height likely break NUS's push-blocking: with each added condition S20 reaches the zone more often against G19, and in Test 5's conditions Guards parked in the zone hold more games than G19 | S20 reaches: 9, 17, 43 (Tests 1–3), 740 (filter), 983 (free height), 979 (Isaac Lab); in Test 5, parked Guards hold 429, G19 17 | T18 [record](../records/2026-11-18_nus_phase4_rung1_record.md), T19 [record](../records/2026-11-18_nus_phase4_rung2_record.md), T20 [record](../records/2026-11-18_nus_phase4_rung3_record.md), T22 [record](../records/2026-11-18_nus_phase4_rung4_2_record.md), T23 [record](../records/2026-11-18_nus_phase4_rung5_record.md), T24 [record](../records/2026-11-18_nus_phase4_rung6_record.md) |
| 2. STE's drone conditions can be trained for: STE's own simple trainer made a Guard team that holds the zone against S20 in Test 5's conditions (NUS's 7.5 m hangar game with the filter and free height, no tag) | trained Guards hold 829; parked Guards 429 | T41 [record](../records/2026-11-19_nus_phase5_pilot_p1b_run4_record.md), T23 [record](../records/2026-11-18_nus_phase4_rung5_record.md) |
| 3. STE's copy of NUS's training method narrowly missed its check set before the run; on 20 November STE paused that route (training with NUS's method) and trains its own teams | 2 of 3 seeds passed every part; the third missed two parts by small margins | T43 [record](../records/2026-11-19_nus_phase5_s51_method_match_record.md); [discussion record](../ste_learning/DISCUSSION_2026-11-19_20.md) |
| 4. At the 1.6 m tag, trained teams beat the best hand-written tactic against the opponent they trained on; the Guard team also stays above it against four of the six Strike tactics | trained Guards hold 913, best hand-written 808; trained Strikes reach 636, best hand-written 192 | T46 [record](../records/2026-11-21_ste_l012_best_response_record.md), T57 [record](../records/2026-11-22_ste_l112_score_record.md) |
| 5. A Strike team trained against Guards that spread to the zone edge facing the nearest Strike (field Guards) only draws level with the best hand-written Strike tactic there; against the other Guard tactics it is clearly below only against the two parked ones | trained Strikes reach 277, best hand-written 284 | T58 [record](../records/2026-11-22_ste_l111_strike_record.md) |
| 6. At the 1.15 m tag both sides learn, but stay below the best hand-written tactic against the opponent they trained on | trained Guards hold 572, hand-written 645; trained Strikes reach 134, hand-written 355 | T54 [record](../records/2026-11-22_ste_l012c_tag_1p15_guard_record.md), T55 [record](../records/2026-11-22_ste_l012c_tag_1p15_strike_record.md), T56 [record](../records/2026-11-22_ste_l012d_cross_tag_record.md) |
| 7. Isaac Lab drones train as well as the fast engine at about 5× the GPU time; teams trained on the fast engine shift a little on Isaac Lab drones; a real drone's position estimate is close to motion capture in hover | Guards trained on Isaac Lab hold 832, on the fast engine 836; shifts of −33 to +47 per matchup; about 1 cm in hover (flight-log analysis) | T53 [record](../records/2026-11-21_ste_l013_tier2_trains_record.md), T64 [record](../records/2026-11-23_ste_l18_tier2_record.md), T63 [record](../records/2026-11-23_ste_l13_fit_record.md) |

## What has not been done

- Nothing has flown: no trained team has played on real drones.
- One seed per side; another seed could land elsewhere.
- Each trained team is scored mainly against the opponent it trained on.
- No strategy is ready to deploy.

Open work is tracked in the [status page](../ste_learning/status/STATUS_LATEST.md) and in Linear.

## Where to read more

[Game spec sheet](../ste_learning/GAME_SPEC.md) · [gate G0 report](../ste_learning/G0_REPORT.md) ·
[NUS port report](NUS_PORT_REPORT.md) · [what was found in the NUS port](WHAT_WE_FOUND.md) · [glossary](GLOSSARY.md)
