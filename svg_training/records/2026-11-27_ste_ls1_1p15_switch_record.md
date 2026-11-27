Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory), played on the CPU of the RTX 5090 workstation (no GPU used). Observed in the training simulator; not a flight result.

# 2026-11-27 Route 3 at the 1.15 m tag: steps C0, C, B and D (record)

**Draft, reviewed by one reviewer when committed** (the decision page built on step D, `LS1_1P15_LIMIT_OPTIONS.md`,
has its own two reviews). Written by the lead (Opus 5.5) from the run folders and the evidence folder
`records/evidence/2026-11-27_ste_ls1_1p15_switch/`. Step E (the pilot networks replayed at 1.15 m) ran beside D. Its
results are sealed until the owner rules the 1.15 m limits, so they are not in this record.

## Purpose

Owner ruling R51 (27 Nov 2026): route 3 moves to the 1.15 m tag (the bubble-touch tag) before the LS1 build. Plan and
marks written before any run: `ste_learning/drafts/LS1_1P15_SWITCH.md`. This record covers the steps that need no
ruling:

| Step | Question | Mark (plan section 3) | Result |
|---|---|---|---|
| C0 | Do T50's 1.15 m script games (played on the GPU) replay exactly on the CPU? | 30 of 30 fixed cells exact | **PASS**, 30 of 30 (outcome, end step, tags, Strike drones left, game for game) |
| C | The script games at 1.15 m in T94's batch layout, for the copy check | 1,000 games a cell (asserted); the C1 rule on the 30 fixed cells | **PASS** on both teams; every batch control PASS, `replay_t44` PASS on every fixed-cell batch (against T50's games) |
| B | How the game changes from 1.6 m to 1.15 m, cell by cell; the run 0 ceiling | INFO, no mark | below |
| D | The copy-limit calibration at 1.15 m (as T90) and its top-up (as T91) | the calibration's own controls | **PASS**: every control (Guard 450 batches, Strike 499, top-up 3 and 3) |

## Facts

| Item | Value |
|---|---|
| Machine | home RTX 5090 workstation, CPU only (32 threads); settings file `configs/ste_learning.toml` (the job launcher's) |
| Starts and seeds | T44's 1,000 starts (seed 110000); calibration noise seed 150101 (calibration files); no training, no learner seed |
| Games | 1,000 a cell; Guard 150 and Strike 130 gated cells (+26 Strike INFO cells) |
| GPU hours | **0** |
| Verdict | INFO: no step here has a pass mark except C0 and C (both PASS) and the controls (all PASS); the limits are the owner's (decision 1) |

## Commit and files

- Code: step C0 ran on `7d511274` (ended 08:29, before step A); step C and the ceiling launched on `20fbd511` (step A). D's first launch was also on `20fbd511`, and its
  relaunch at 09:20 on `fd3bbeca`, which changed tests and a plan note only. The top-up ran on `6aac9e9e`.
  `scripts/ste_ls1_calibration.py` is the same in all three.
- `configs/ste_ls1/skills_gates_1p15.toml` (sha256 `9d5bcf92…`), `calibration_1p15.toml` (`ebee6586…`),
  `calibration_topup_1p15.toml` (`6f06cf39…`), `distil_gates_1p15.toml` (`59d94d50…`, owner keys `FILL_R51`); game file
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

## Videos

None: no policy was trained. These are script and calibration plays.

## Ledger

T95 (D), T96 (D top-up), T97 (the run 0 ceiling) in `records/LEDGER.md`. C0 and C are scratch checks, recorded here.
