Simulator: training simulator, tier 1 (fast engine on the CPU; the hangar game of Phase 4 row 5: commander copy, safety filter on every pair, fitted PX4 response, exploratory), and the Crazyflie repository's offline planner (`plan_guard`, stand-in aircraft, CPU). Observed in the training simulator and in the planner; not a flight result.

# 2026-11-21_ste_l014_crazyflie_route record

## Purpose

STE task L0.14 Crazyflie route check (INFO, PLAN.md section 4; DISCUSSION §2.16; feeds P13 at gate G0). Part 1: the STE
Guard policy (T41) scored in its own hangar game with a later drone response beside the Starling's (a sensitivity test,
not a Crazyflie model). Part 2: which team sizes fit which arena at the Starling's 1.10 m filter distance, from the
Crazyflie repository's offline planner, run from a copy (that repository is read-only). Part 3 (a specification) is on
the page only. The plan was written on the page before the runs: [CRAZYFLIE_ROUTE.md](../ste_learning/CRAZYFLIE_ROUTE.md).

## Commit

`15f32606` (branch `ste-l0.14`) plus this task's uncommitted files (`configs/ste_l014.toml`,
`scripts/ste_l014_response_check.py`, `scripts/ste_l014_arena_fit.py`); the results files record `git_dirty: true`.
Crazyflie repository: `~/CrazySwarm2-with-Mocap_Strike-and-Guard` at `637c5343`, `git status --porcelain --ignored`
empty before and after every run (`repo_untouched: true` in both `arena.json`).

## Config

- `configs/ste_l014.toml`, committed sha256 `14d7263b45baf4d2e5d71f01cc6f1d86c9438885e6398a6f2d36c2e615d1a60d`.
- **Settings-hash note.** Part 1 and the main planner sweep recorded sha256 `b6e3de93e8d135ce…` (the file before the
  follow-up keys `followup_*` and `planner_strike_radius_m` were appended; the follow-up run recorded the committed
  `14d7263b…`). Checked: every recorded setting equals the committed file's value (part 1 `[response]` and
  `[step_probe]` equal; the main sweep lacks only the four follow-up keys).
- Part 1: T41 (`runs/nus_port/phase5/pilots/2026-11-19_nus_phase5_pilot_p1b_run4/agent.pt`, sha256 `c91bea51d7ec4032…`;
  same networks and scalers as `agent_best.pt`, checked) v S20, mean actions, one decision per 12 ticks; the first 1,000
  Phase 4 paired starts (all of them); at most 2,400 ticks per game.
- Part 2: `plan_guard` from a scratch copy (package sha256 `40d2d953b56eec7e…`); settings d_cc 1.10 m, cc_z_ratio 1.0
  (a sphere), speeds 0.33 m/s (Guard, defence) and 0.5 m/s (Strike, attack), height band 0.5–1.8 m, lag 0.6 s, `tag`
  rules with strike radius 1.6 m (the STE zone); hand-set marks (Guards on a 1.4 m ring, Strikes on a 2.75 m ring round
  the protected point at the room centre). Arenas: a 6.5 m square polygon (scratch `arena.yaml`), the planner's
  `arena_radius` 3.25 m circle, the Crazyflie room as surveyed.

## Model parameter set

Base: `params/real_exploratory_v0.toml` (sha256 `4c93543f51ab41ea…`, EXPLORATORY, `[px4] delay_s` 0.1482 s). Four
derived files in the run folder (`response/params/`), each differing from the base in `[px4] delay_s` only (checked on
reload) and headed SENSITIVITY SET: 0.1482 s (`79bdb2e0…`), 0.30 s (`9f3cbacb…`), 0.48 s (`2cd3a6c6…`), 0.56 s
(`1ae9e838…`). The 0.148 s cell plays the base file itself (the default path). Every drone in a cell gets the same
delay (both teams).

## Seeds

Part 1: evaluation seed 1101 and opponent seed 1303 (T41's own). A second seed changes nothing: 32 games at seed 1102
gave the same 32 outcomes as at 1101 (fixed starts, deterministic players); so one policy, one opponent, 1,000 starts.
Part 2: the planner's own seeds 0–99 per case (start jitter and strategy draws), 0–5 for the all-pairings matrix.

## Machine

jeremychia-Legion-Pro-7-16IAX10H (laptop), CPU only (`CUDA_VISIBLE_DEVICES=""`), 0 GPU-h; torch 2.7.0+cu128, 4 threads;
planner under the system Python 3.12.3, numpy 2.4.6, scipy 1.17.1, pyyaml 6.0.1. The CPU was shared with another job
(load up to 24). The machine was not suspended.

## Games at once

Part 1: 1,000 games of 3 Guard v 3 Strike drones per cell, 4 cells, plus the control (16 games × 600 ticks, twice).
Part 2: one match at a time per planner process, 2 processes; 21 + 8 cases, 2,868 matches.

## Steps per second

Part 1: 729 s, 994 s, 1,417 s and 1,352 s per cell (0.148, 0.30, 0.48, 0.56 s), 4,570 s in all on a shared CPU: 3,293, 2,415, 1,693 and 1,775 game-steps per second (1,000 games × 2,400 ticks
played per cell, 6 drones per game, tier 1, CPU, 4 threads; drone-steps per second six times that). Part 2: 652 s (sweep) and 891 s (follow-up).

## Gates

Verdict: **INFO (no gate).** Controls:

| Control | Result |
|---|---|
| C-1 bit for bit: the default path and a derived file at the fitted delay, 16 games × 600 ticks, every output (outcome, end tick, closest approaches, rule breach, filter share, final positions and speeds) | PASS (no output differs) |
| C-2 every game finished, no non-finite action, every cell | PASS |
| Starling cell v T41's record (GPU) | 831 v 829 of 1,000 (INFO; Wilson intervals overlap) |
| Crazyflie repository untouched | PASS (status empty before and after, both runs) |
| Planner emergency counter fires on this machine (positive control: `plan_guard --matrix --rules all --seeds 4 --tau 0.6 --set d_cc=0.60`) | 2 of 80 cells flagged, both `pressure` rule sets; `--rules pressure --defense hunter --attack flood`, seed 1: solver emergency on 4 ticks |

## Results

**Part 1: T41 v S20, 1,000 paired starts per cell.**

| Delay (s) | Trails a 0.5 m/s path by (s) | Holds | Wilson 95 % | Lost / gained v 0.148 s (sign test p) | Games closer than 1.10 / 1.0 / 0.50 m | Closest (m, 3-D) | Filter share | Mean end tick |
|---|---|---|---|---|---|---|---|---|
| 0.148 (Starling) | 0.19 | 831 | [0.807, 0.853] | — | 198 / 7 / 0 | 0.85 | 33.5 % | 2,035 |
| 0.30 | 0.35 | 822 | [0.797, 0.844] | 35 / 26 (0.31) | 260 / 31 / 0 | 0.71 | 33.7 % | 2,012 |
| 0.48 (trails like the logged Crazyflie, ~0.56 s) | 0.57 | 791 | [0.765, 0.815] | 77 / 37 (0.0002) | 305 / 101 / 2 | 0.39 | 32.7 % | 1,946 |
| 0.56 | 0.73 | 768 | [0.741, 0.793] | 106 / 43 (2.5e-7) | 315 / 149 / 1 | 0.31 | 32.3 % | 1,890 |

1.10 m: the flight filter's distance; 1.0 m: the hangar game's keep-out (its `rule_breach` measure; T41's record 0.005);
0.50 m: the game's contact distance. Counts from `per_game.npz`. "Trails": the step probe, one drone, 0.5 m/s from
rest for 30 s, settled gap over 20–30 s divided by the speed.

**Part 2: the planner at 1.10 m.** 0 solver emergencies and 0 other safety failures in 2,868 matches:

| Cases | Matches | Guard (defence) wins | Closest pair (m) | Matches inside 1.10 m | Mean match (s) |
|---|---|---|---|---|---|
| 1v1, 2v1, 3v3, 5v3 × 6.5 m square (default pairing, seeds 0–99) | 4 × 100 | 0, 0, 99, 100 | 2.50, 1.47, 1.06, 1.06 | 0, 0, 91, 99 | 4.2, 4.1, 13.4, 10.3 |
| the same × 3.25 m circle | 4 × 100 | 0, 0, 99, 100 | 2.50, 1.27, 1.06, 1.07 | 0, 0, 81, 96 | 4.3, 4.3, 9.8, 6.9 |
| the same × Crazyflie room | 4 × 100 | 0, 99, 100, 100 | 2.50, 1.09, 1.07, 1.07 | 0, 85, 54, 98 | 8.3, 9.0, 16.9, 15.4 |
| 5v3, 6.5 m square, lag 0.15 s | 100 | 100 | 1.08 | 100 | 9.1 |
| all 16 pairings × seeds 0–5, each size, square / room | 8 × 96 | 0, 0, 60, 94 / 0, 48, 61, 94 | 1.02–2.32 | 0, 0, 68, 91 / 0, 23, 49, 92 | 4.0–9.5 |
| follow-up (a) finale flown, 3v3 and 5v3, square and room | 4 × 100 | 99, 100, 100, 100 | 1.05–1.06 | 95, 100, 66, 100 | 10.3–16.9 |
| follow-up (b) strike radius 2.4 m, the same | 4 × 100 | 74, 100, 100, 100 | 1.06–1.07 | 80, 100, 55, 98 | 10.4–17.0 |

DISCUSSION §2.16 (20 Nov) reports solver emergencies in 5 of 100 matches at 3v3 and 5v3 in the 6.5 m arena; this run
found 0 of 2,868 with a working counter (positive control). The 20 Nov marks, rules and protected-point settings were
not recorded; the finale and the 2.4 m strike radius were ruled out as the difference; only the `tag` rules were run at
1.10 m. Recovering the 20 Nov commands is an optional follow-up on the home RTX 5090 (lead's ruling, 21 Nov).

## Figures

- [l014_hold_by_delay.png](../ste_learning/figures/l014_hold_by_delay.png): hold rate per delay; games lost and gained
  start by start; games closer than 1.10 / 1.0 / 0.50 m.
- [l014_step.png](../ste_learning/figures/l014_step.png): the step probe per delay.
- [l014_arena_fit.png](../ste_learning/figures/l014_arena_fit.png): planner emergencies and matches inside 1.10 m per
  size and arena.

Drawn by `scripts/make_ste_l014_figures.py` from `response/results.json`, `response/per_game.npz` and
`arena_fit/arena.json`. No videos: part 1 renders no clips (an INFO sensitivity re-score of T41, whose videos are in
its own record); part 2 is the planner's text output.

## Deviations from the plan

- Four delays instead of two: a pure 0.56 s delay makes tier 1's drone trail by 0.73 s, so 0.48 s (trails 0.567 s)
  was added, chosen from the step probe before any game ran.
- Planner strike radius 1.6 m (the STE zone) instead of the planner's 2.4 m: the first launch at 2.4 m gave Strike wins
  in about a second (Strikes start 0.35 m outside it); stopped after 1v1 and 2v1, kept as
  `arena_fit_STOPPED_strike_radius_2.4/`; 2.4 m was later run as follow-up (b).
- Follow-up (a) and (b) added after the sweep found no emergency, written on the page before they ran.
- Hand-set marks: the planner's own marks are refused at 1.10 m in the small arenas (checked).
- The game's `rule_breach` is the 1.0 m keep-out, not 1.10 m; caught before hand-over; the page and this record report
  1.10, 1.0 and 0.50 m counts from `per_game.npz`.
- Part 1 and the planner sweep ran side by side on the CPU for a while.

## Limits

- One policy (T41), one opponent (S20), one game; every drone slowed, S20's included, so the change is not the Guard's
  alone. A pure delay on a Starling model with CMU's commander copy is not a Crazyflie model.
- The planner's "safe" uses the Crazyflie's 0.35 m floor and stand-in aircraft (a first-order lag); its matches are
  short (4–17 s) and 1v1 / 2v1 in the small arenas barely interact. Why pairs come to 1.02–1.09 m is not tested.
- Observed in the training simulator and in the planner; nothing here is a flight result or authorises a flight.

## Run folder

`runs/2026-11-21_ste_l014/`: `response/` (results.json, per_game.npz, params/), `arena_fit/` and `arena_fit_followup/`
(arena.json, cases/ with every match), `arena_fit_STOPPED_strike_radius_2.4/`, `positive_control/`, logs.
