Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory), L1.7 estimate error off / nominal / conservative (EXPLORATORY values from T63); NVIDIA GeForce RTX 5090. Observed in the training simulator; not a flight result.

# 2026-11-24_ste_l17_speed record

## Purpose

STE task L1.7 (main track, INFO, no gate): the speed cost of tier 1's estimate error, re-measured alone on an idle RTX
5090. The laptop's first numbers of 23 November 2026 were taken while another job shared the machine and were
unreadable (WORK_BREAKDOWN, L1.7). The budget it is read against: at most 10 % throughput loss (CODING_PRACTICES
section 9; INFO here).

## Commit

`9f9ce2d5` on `development` at launch (04:18:55; the measurement script was in the working tree, written for this run,
and first committed 3 min later in `242953c5`, unchanged since); measurement script
`records/evidence/2026-11-24_ste_l17_speed/measure_l17_speed.py` (sha256 `2ff7397fcb85…`, an evidence script, not pipeline
code). The script was written for this run (the laptop's was a session scratchpad, not committed).

## Config

- Arms, alternated inside each repeat: **off** `configs/ste_l011/base.toml` (no estimate error: today's game);
  **nominal** `configs/ste_l1/base_err_nominal.toml` (position 0.0099 m, velocity 0.022 m/s, T63, PROPOSED);
  **conservative** `configs/ste_l1/base_err_conservative.toml` (2 × the sigmas); **nominal_est** nominal with
  `commander_reads = "estimate"` (the commander copy and its filter read the estimate, as on the real drone). The
  script asserts the error is on in the three error arms and off in "off".
- 3v3, random actions, game seed 1100, torch seed 1100 + repeat; 4,096 and 16,384 games; 5 repeats per arm and size;
  timing as `configs/ste_l1/model_check.toml` [timing] (warm-up 50 steps and 2 s, timed 200 steps and 3 s).
- Launched by `scripts/ste_job.py launch --task L1.7 --gpu-h 0.1` alone on the GPU (nothing else running; the CPU
  screen of L1.9 started after it ended).

## Result (INFO)

| Games | Arm | Mean game-steps/s | Min | Max | Cost against off |
|---|---|---|---|---|---|
| 4,096 | off | 318,093 | 308,890 | 326,970 | — |
| 4,096 | nominal | 309,769 | 300,564 | 314,810 | +2.6% |
| 4,096 | conservative | 311,385 | 303,604 | 315,317 | +2.1% |
| 4,096 | nominal_est | 307,097 | 301,188 | 313,154 | +3.5% |
| 16,384 | off | 1,143,219 | 1,123,015 | 1,151,924 | — |
| 16,384 | nominal | 1,131,381 | 1,111,932 | 1,142,998 | +1.0% |
| 16,384 | conservative | 1,131,676 | 1,102,540 | 1,152,820 | +1.0% |
| 16,384 | nominal_est | 1,130,419 | 1,110,154 | 1,143,095 | +1.1% |

Cost = 1 − mean(arm) / mean(off), same size. The estimate error costs **about 1 % at 16,384 games and 2–3.5 % at
4,096**, inside the 10 % budget at both sizes; the min–max spread of "off" across repeats (about ±3 % at 4,096) is as
large as the cost there, so the 4,096 figures are an upper bound more than a measurement. Reading the estimate in the
commander adds no cost that this run can see. No NaN in any arm.

## What this does not show

Random actions, not a trained team; GPU only (the laptop's CPU figures are not re-measured); speed only, nothing about
game results (those are L1.8's, T64, on tier 2, and L1.9/L1.10's).

## GPU-hours

0.062 GPU-h logged (task cap 0.1); ledger `budget_l1_l2`: 3.602 of 13.0 used.

## Files

`records/evidence/2026-11-24_ste_l17_speed/`: `measure_l17_speed.py`, `results.json` (every repeat), `results.md`.
Run folder `runs/2026-11-24_ste_l17_speed/` (job.log, exit_code 0; not in git). No videos: a speed measurement plays no games of record
(STANDARDS §8 applies to training runs).
