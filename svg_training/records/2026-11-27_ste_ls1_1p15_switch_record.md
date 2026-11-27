Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory), played on the CPU of the RTX 5090 workstation (no GPU used). Observed in the training simulator; not a flight result.

# 2026-11-27 Route 3 at the 1.15 m tag: steps C0, C, B, D and E (record)

**Draft, reviewed by one reviewer when committed** (the decision page built on step D, `LS1_1P15_LIMIT_OPTIONS.md`,
has its own two reviews). Written by the lead (Opus 5.5) from the run folders and the evidence folder
`records/evidence/2026-11-27_ste_ls1_1p15_switch/`. Step E (the pilot networks replayed at 1.15 m) ran beside D, sealed;
the owner ruled the 1.15 m limits (R52, 27 Nov 2026, about 19:30: `flips_max_games` 31, the other 15 owner keys as R48)
and E was then judged once (section "E" below; two reviewers: numbers, completeness).

## Purpose

Owner ruling R51 (27 Nov 2026): route 3 moves to the 1.15 m tag (the bubble-touch tag) before the LS1 build. Plan and
marks written before any run: `ste_learning/drafts/LS1_1P15_SWITCH.md`. This record covers the steps that need no
ruling, and step E, judged after the ruling:

| Step | Question | Mark (plan section 3) | Result |
|---|---|---|---|
| C0 | Do T50's 1.15 m script games (played on the GPU) replay exactly on the CPU? | 30 of 30 fixed cells exact | **PASS**, 30 of 30 (outcome, end step, tags, Strike drones left, game for game) |
| C | The script games at 1.15 m in T94's batch layout, for the copy check | 1,000 games a cell (asserted); the C1 rule on the 30 fixed cells | **PASS** on both teams; every batch control PASS, `replay_t44` PASS on every fixed-cell batch (against T50's games) |
| B | How the game changes from 1.6 m to 1.15 m, cell by cell; the run 0 ceiling | INFO, no mark | below |
| D | The copy-limit calibration at 1.15 m (as T90) and its top-up (as T91) | the calibration's own controls | **PASS**: every control (Guard 450 batches, Strike 499, top-up 3 and 3) |
| E | Do the R50 pilot networks (fitted on 1.6 m rows, no refit) pass the copy check at 1.15 m? A transfer test | LS1_REDESIGN.md 4.4 with R52's limits; headroom median ≤ 9 and ≤ 5 cells over 20; worse of two seeds; controls: script-oracle arm 0 changed games, C4 analogue ≥ 15 of 30 fixed cells missed | **FAIL on both teams**, controls PASS (read valid) |

## Facts

| Item | Value |
|---|---|
| Machine | home RTX 5090 workstation, CPU only (32 threads); settings file `configs/ste_learning.toml` (the job launcher's) |
| Starts and seeds | T44's 1,000 starts (seed 110000); calibration noise seed 150101 (calibration files); no training, no learner seed |
| Games | 1,000 a cell; Guard 150 and Strike 130 gated cells (+26 Strike INFO cells) |
| GPU hours | **0** |
| Verdict | C0 and C PASS; D's controls PASS; B INFO; E FAIL on both teams (a transfer result, plan section 3: not a failure of the design) with its controls PASS |

## Commit and files

- Code: step C0 ran on `7d511274` (ended 08:29, before step A); step C and the ceiling launched on `20fbd511` (step A). D's first launch was also on `20fbd511`, and its
  relaunch at 09:20 on `fd3bbeca`, which changed tests and a plan note only. The top-up ran on `6aac9e9e`.
  `scripts/ste_ls1_calibration.py` is the same in all three.
- `configs/ste_ls1/skills_gates_1p15.toml` (sha256 `9d5bcf92…`), `calibration_1p15.toml` (`ebee6586…`),
  `calibration_topup_1p15.toml` (`6f06cf39…`), `distil_gates_1p15.toml` (`59d94d50…` with the owner keys `FILL_R51` for
  steps C, D and E's runs; `d5fdd013…` with R52's values for E's judgement); game file
  `configs/ste_l011/tag_1p15.toml` (`b2e09683…`); reference `configs/ste_l012b/screen_reference.npz` (`49014000…`,
  variant `tag_1p15`), T44's 1,000 starts (seed 110000, `5aeba7ab…`).

## Runs

| Run folder (not in git) | What | Start, end (+08:00) | Exit | CPU |
|---|---|---|---|---|
| `runs/2026-11-27_ste_ls15_1p15_calibration_guard`, `..._strike` | D: the 1.15 m calibration through `ste_job.py launch --task LS1.5 --gpu-h 0` | 08:32:52, stopped 09:19 (SIGTERM, exit 4: CPU oversubscribed, load about 98 on 32 threads); relaunched 09:20:48 with `OMP_NUM_THREADS=8 MKL_NUM_THREADS=8` (noted in each folder's `THREADS_NOTE.txt`), resumed at the next batch; ended 13:39 | 0, 0 | 4.41 h Guard, 4.35 h Strike (batch seconds summed) |
| `runs/2026-11-27_ste_ls15_1p15_topup_guard`, `..._strike` | D top-up: field 1.5 and 1.8 m on `guard_field` v `strike_straight`; flank 0.6 and 0.9 m on `strike_flank` v `guard_field` (`--mixed 0`, not of record, as T91) | 13:44:54, 12 s (Guard) and 23 s (Strike) | 0, 0 | seconds |
| `runs/2026-11-27_ste_ls12_1p15_scripts_guard`, `..._strike` | C: the scripted stages (c1, c1m, r2), scratch driver `evidence/.../c/c.py` | started about 08:36 (batch seconds back from the end), ended 09:11:13 (Guard), 09:13:40 (Strike) | PASS | 0.61 h Guard, 0.65 h Strike (batch seconds summed) |
| `runs/2026-11-27_ste_l3_run0_ceiling_1p15` | B: the run 0 ceiling (`scripts/ste_l3_run0_ceiling.py --gates configs/ste_ls1/skills_gates_1p15.toml --games 1000 --device cpu --chunk 22`) | 08:37:45 to 11:40:56 | 0 | about 3 h wall clock, slowed by the shared CPU |

## Results

**B, the game at 1.15 m** (`evidence/.../b/b_table.md`, every fixed and mixed cell, 1.6 m from T44 and T94, 1.15 m
from T50 and step C). Every Guard cell loses wins (median −423 of 1,000, from −42 to −540). Every Strike cell gains
(median +376.5 over all 156 cells, from +6 to +507; over the 130 gated cells median +367.5, from +42 to +459). Of all
cells, 22 Guard and 31 Strike are fewer than 100 games from 0 or 1,000 at 1.15 m. The
parked Guards collapse: `guard_parked_centre` holds 101 against `strike_straight` (534 at 1.6 m), 31 against `strike_high`
and 16 against `strike_low`.

**B, the run 0 ceiling** (`evidence/.../b/run0_ceiling_1p15_results.md`). Strike team against `guard_parked_centre`:
the best constant choice is `strike_low` ×3 with 984/1000 (95 % CI 0.974 to 0.990; at 1.6 m the best choice reached 604, `strike_low`+`strike_low`+`strike_straight`, T79). The untrained
team (`strike_straight` ×3) gets 899/1000 (Wilson upper bound 0.916). The pre-registered rule gives the mark
(984 − 50) / 1000 = **0.934** (MARK_SET; 0.554 at 1.6 m). The mark is 18 games above the untrained team's upper bound,
so run 0 against the parked Guard is close to trivial at 1.15 m. That is owner decision 3 of the plan. The mark is not
written into any gate file. All 5 controls PASS.

**D, the calibration.** The per-arm tables are in each folder's `results.md`. What they mean for the limits, judged
with the gate's own rule against R48's values and beside the 1.6 m read: `ste_learning/drafts/LS1_1P15_LIMIT_OPTIONS.md`
(the check script and its outputs in `evidence/.../limits/`; the same script reproduces the 1.6 m page's section 6
exactly). In short: every near-miss check of the gate still comes out as it must under R48, and the same small errors
change more games at 1.15 m (Strike noise 0.02: up to 31 games in a cell, 27 at 1.6 m).

**Not measured (plan step C).** The natural share of rows with a team-mate absent at 1.15 m (`absent_min_share` 0.2 was
set from 0.22 and 0.27 at 1.6 m) was not measured. The 1.6 m figure is a share of distillation rows. Step C's stored
games keep one record per game, not the tick a drone was lost, so they cannot give it. It moves to the build's CPU
smoke at 1.15 m (the LS1.0 analogue), which makes the rows.

**E, the pilot networks at 1.15 m** (`evidence/.../e/e_judged.md`, every cell; judge `e/judge.py`, inputs `e/sealed/`
with sha256 in `e/inputs.sha256`; job code `e/code/`, logs `e/logs/`). Jobs ran 09:16 to 13:03 beside D, 2 at a time,
6 threads each (about 6.8 CPU job-hours summed, 3 h 47 min wall clock; dispatcher log `e/code/dispatch.log`). The same networks passed at 1.6 m
(`ste_learning/drafts/LS1_REDESIGN_PILOT_RESULTS.md`).

| Assembly (rungs) | 1.15 m result | Max | Median | Over 20 | Over 31 | Failed limits | 1.6 m (max, median) |
|---|---|---|---|---|---|---|---|
| Guard S1 seed 1 (all R2) | **FAIL** | 68 | 5 | 25 | 12 | games, cell interval, command error (field 0.068) | PASS (25, 3) |
| Guard S1 seed 2 | **FAIL** | 65 | 6 | 20 | 13 | games, cell interval, command error (field 0.066, mirror 0.053) | PASS (24, 4) |
| Strike S2 seed 1 (sacrifice, converge R3) | **FAIL** | 34 | 2 | 3 | 2 | games only | PASS (16, 3) |
| Strike S2 seed 2 | **FAIL** | 34 | 2 | 4 | 1 | games only | PASS (15, 2) |
| Strike S1 seed 1 (all R2; reported, does not decide) | **FAIL** | 90 | 2 | 8 | 5 | games, cell interval, command error (sacrifice 0.074, converge 0.075) | FAIL (31, 3) |

Pooled intervals inside ±0.01 in every assembly. Controls: the script-oracle arm equals the scripts game for game
(150 Guard and 130 Strike cells); the C4 analogue misses 26 of 30 (Guard) and 30 of 30 (Strike). Team results (worse
of two seeds): **Guard FAIL, Strike FAIL**. No higher assembly, own-state check or DAgger rescue was played at 1.15 m
(R51: no refit), so this is "the 1.6 m networks do not carry to 1.15 m", not a 4.4 team FAIL after the ladder. Over 30
and over 31 are the same count in every assembly: 30 or 31 makes no difference here.

Where the changed games are. Guard: 12 of the 13 cells over 31 at the worse seed are against `strike_converge` (max 68;
at 1.6 m the max against converge was 25); one is `guard_mirror` ×3 against `strike_sacrifice` (32). Guard wins against
converge fall from 1.6 m to 1.15 m by a median 409 a cell (103 to 540; step B). Command error rose most for `guard_field` (0.011 → 0.068) and
`guard_mark_edge` (0.007 → 0.042): the states with opposite drones 1.15 to 1.6 m apart, rare in the 1.6 m fit rows, that
the plan named. Strike S2: only `strike_converge` ×3 against `guard_mirror` (34) and `guard_mark_edge` (32 at seed 1);
every Strike skill's command error stays under 0.04. Lopsided cells (scripts win under 100 or over 900): 22 Guard, 30
Strike; median over the rest 9 (Guard) and 3 (Strike). D's noise 0.02 arm on the same cells: max 19 Guard, 31 Strike,
so the ruler still sees changes at 1.15 m; the Guard networks change more games than that arm in 108 of 150 cells,
the Strike networks in 28 of 130. The 26 Strike INFO cells: max 11 (S2), 30 (S1).

What E says for the owner's decisions 2 and 8 (from the 1.6 m pilot page). **Decision 2** (R3 inputs for
`strike_sacrifice` and `strike_converge`): at 1.15 m, as at 1.6 m, those two skills miss the command-error limit at R2
(0.074, 0.075) and meet it at R3 (0.027, 0.033), and the worst cell falls from 90 to 34 games. **Decision 8**
(`guard_field` at R2, the nearest-first list): E does not test it against R1, since no R1 field network was replayed.
It shows that the R2 field network, fitted on 1.6 m rows, has the largest command error of any Guard skill at 1.15 m,
while its own cells change at most 34 games; the Guard team's failure is mostly the mark_edge and mirror networks
against converge.

Reviews: numbers (independent recompute from the sealed files: no discrepancy in 280 gated cells, both controls, team
results, the hold-rate and noise columns); completeness (2 blockers, 5 should-fix, 4 nits on the judgement output: rung
table, tag and game named, the ladder note, INFO cells, per-opponent and lopsided summaries, the noise column read, the
full cell table; all folded into `e/judge.py` and its output before this record). Remark of the numbers reviewer: S2
seed 2 was played although seed 1 had failed (4.4 ends an assembly at a seed-1 FAIL); every E job ran at once by plan,
and this changes no result.

## Videos

None: no policy was trained. These are script and calibration plays, and E replays existing pilot networks (their
1.6 m clips are on the pilot page; E's 1.15 m clips are not rendered: a FAIL read with no reader page).

## Ledger

T95 (D), T96 (D top-up), T97 (the run 0 ceiling) in `records/LEDGER.md`. C0, C and E are scratch checks (as the 1.6 m
pilots), recorded here.
