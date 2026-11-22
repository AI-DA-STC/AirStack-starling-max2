Simulator: training simulator, tier 2 (the same command chain driving the Isaac Lab 2.3.2 rigid-body Starling in PhysX, PX4 1.14 cascade copy, L1.1b estimate error per condition) beside tier 1 (fast engine; fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator; not a flight result. Estimate-error values: EXPLORATORY (T63, one flight log).

# 2026-11-23_ste_l18_tier2 record

Written by hand from the run folder's `results.json` / `results.md` / `controls.json` (`scripts/ste_tier2_score_l18.py`
writes no record); the tables are copied from `results.md`. Paired counts between the tier-2 conditions were computed by
the records writer from `games/*.npz`, checked by a numbers reviewer; they are not pre-registered.

## Purpose

STE task L1.8 (main track, INFO; spec `ste_learning/drafts/L1_8_SPEC.md`, sha256 `2566250139553e92…`, written before the
run): do T46's strategies trained at tag 1.6 m in tier 1 (Guard team holds 913 v strike_straight; Strike team reaches
636 v guard_mark_edge) keep their results on the tier-2 Isaac Lab drone, without and with the estimate error fitted in
L1.3 ([record T63](2026-11-23_ste_l13_fit_record.md), EXPLORATORY)? Conditions, base game, T44's 1,000 starts, every
player against every script of the other team: (1) tier 2, error off; (2) nominal error; (3) conservative error (2 ×
sigma, same taus; shares seeds with (2)); (4) the tier-1 reference from T46's and T44's files (no new run).

Pre-registered reading words: (1) v (4): "on the tier-2 drone with no estimate error the 1.6 m Guard team holds N (tier 1:
913)", a difference between two simulators, not an effect of the error. (2) and (3) v (1): a player cell whose Wilson
95 % interval does not overlap the error-off interval reads "the fitted estimate error changes the result: N against
M"; otherwise "the result holds with the estimate error (nominal / conservative)". Worst cell first.

## Commit

`f565cd23f64ce3f13614f04a314da28d6d97d091` on branch `ste-l1-8` (diff sha256 `e3b0c44298fc`, the empty diff),
committed 6 s before the launch after two code reviews.

## Config

- Settings `configs/ste_l1/tier2_score_l18.toml`, sha256 `0eb3c29e6142f9cbfe9fcaef800cb0dc478464699a233bd34a1b8f45cd8de551` (copy in the run folder).
- Parameter files (sha256): off `params/starling_physics_v1.toml` `e8968026995b…` (every `state_error_*` 0 = today's
  tier 2); nominal `params/starling_physics_v1_nominal.toml` `9963e39fbca0…` (position 0.0099 m / 1.2 s, velocity
  0.022 m/s / 1.3 s, attitude 0.0027 rad / 2.0 s); conservative `params/starling_physics_v1_conservative.toml`
  `dd7dc1886f83…` (0.0198 m, 0.044 m/s, 0.0054 rad, same taus). Each differs from v1 only in `state_error_*` (control).
- Players (agent_final.pt sha256): T46 base Guard `ste_provisional/players/2026-11-21_ste_l012_base_guard`
  `e981ac7e7045…` (trained v strike_straight); T46 base Strike `ste_provisional/players/2026-11-21_ste_l012_base_strike`
  `3c264ddd9fac…` (trained v guard_mark_edge).
- Game `configs/ste_l011/base.toml` (tag 1.6 m, 120 s, 2,400 ticks) with the Starling backend switched to the physics
  drone; T44's first 1,000 starts (seed 110000, start set `5aeba7ab2b58…`); 15 cells per condition (6 Guard-player cells,
  5 Strike-player cells, 2 script cells, 2 repeat copies of the script cells).

Command (`cmd.txt`): `scripts/ste_job.py launch --task L1.8 --name l18_tier2 --run-dir runs/2026-11-23_ste_l18_tier2
--min-s 1200.0 --gpu-h 0.9 --settings configs/ste_learning.toml --beat-s 60.0 -- python scripts/ste_tier2_score_l18.py
--settings configs/ste_l1/tier2_score_l18.toml --run-dir runs/2026-11-23_ste_l18_tier2 --cap-h 0.9 --headless`

## Model parameter set

Tier 2: the rigid-body Starling v1 (gains and airframe from the drone's file, never tuned) with the L1.1b estimate error
per condition; tier 1 (condition 4): `params/real_exploratory_v0.toml` (fitted response, exploratory).

## Machine

jeremychia-Legion-Pro-7-16IAX10H, NVIDIA GeForce RTX 5070 Ti Laptop GPU, torch 2.7.0+cu128, device cuda; one launch
2026-11-23T04:19:31+08:00 to 04:55:24, exit 0 (DONE), alone on the GPU; effective 2,142 s of the 0.9 h
cap; batches: tier-1 replay 197 s, off 616 s, nominal 637 s, conservative 619 s. GPU-hours: 0.598 (shared ledger, job
l18_tier2).

## Gates

Verdict: **INFO** (no gate; the controls are gated: any control not PASS, INFO or NOT_CHECKED and no number is reported).

| Control | What | Status |
|---|---|---|
| tier1_replay | T46's player cells equal its eval_info game for game; script and repeat cells equal T44; Guard v straight 913, mark_edge v Strike 636 | **PASS** |
| condition_off / nominal / conservative | each game differs from the base file only in the Starling backend and parameter file; each parameter file differs from v1 only in `state_error_*`, and flies its file's values | **PASS** (all 3) |
| physics_agreement (per condition) | 15,000 games × 6 drones × 20 ticks, Isaac Lab against the torch twin: largest gap 0.01661 / 0.01671 / 0.01606 m (limit 0.02 m) | **PASS** (all 3) |
| tier2_off / nominal / conservative | non-finite wrench or setpoint 0; upset games 0; paired starts, tags one for one, no non-finite actions | **PASS** (all 3) |
| repeat_off | two same-seed copies: guard_mark_edge v straight holds 800 / 805, 7 games end otherwise; guard_parked_centre v straight 541 / 537, 4 games (driver's tolerance 10 holds, 20 games); the spec asked for identical copies: see the lead's ruling under Run notes | **PASS** |
| known_off | guard_parked_centre v straight holds 541, inside T53's tier-2 band 507–569 | **PASS** |
| repeat_nominal / repeat_conservative | the same copies with the error on (each copy draws its own error): 75 and 35 games / 86 and 58 games end otherwise, holds within 6 | **INFO** |

## Results

Copied from `results.md` (1,000 starts per cell, Wilson 95 %):

| Cell (Guard v Strike) | Counted | Tier 1 | Tier 2 off | Tier 2 nominal | Tier 2 conservative | Tier 2 off minus tier 1 | Paired tier 1 / off: both, tier 1 only, off only, neither |
|---|---|---|---|---|---|---|---|
| t46_guard v strike_straight (training opponent) | holds | 913/1000 (0.894-0.929) | 881/1000 (0.859-0.900) | 886/1000 (0.865-0.904) | 890/1000 (0.869-0.908) | -32 | 866, 47, 15, 72 |
| t46_guard v strike_flank | holds | 953/1000 (0.938-0.964) | 920/1000 (0.902-0.935) | 927/1000 (0.909-0.942) | 911/1000 (0.892-0.927) | -33 | 910, 43, 10, 37 |
| t46_guard v strike_high | holds | 931/1000 (0.914-0.945) | 943/1000 (0.927-0.956) | 948/1000 (0.932-0.960) | 937/1000 (0.920-0.950) | +12 | 915, 16, 28, 41 |
| t46_guard v strike_low | holds | 923/1000 (0.905-0.938) | 942/1000 (0.926-0.955) | 934/1000 (0.917-0.948) | 921/1000 (0.903-0.936) | +19 | 912, 11, 30, 47 |
| t46_guard v strike_sacrifice | holds | 922/1000 (0.904-0.937) | 939/1000 (0.922-0.952) | 943/1000 (0.927-0.956) | 943/1000 (0.927-0.956) | +17 | 896, 26, 43, 35 |
| t46_guard v strike_converge | holds | 913/1000 (0.894-0.929) | 960/1000 (0.946-0.970) | 959/1000 (0.945-0.970) | 949/1000 (0.934-0.961) | +47 | 904, 9, 56, 31 |
| guard_parked_centre v t46_strike | reaches | 328/1000 (0.300-0.358) | 351/1000 (0.322-0.381) | 364/1000 (0.335-0.394) | 399/1000 (0.369-0.430) | +23 | 291, 37, 60, 612 |
| guard_parked_ring v t46_strike | reaches | 327/1000 (0.299-0.357) | 348/1000 (0.319-0.378) | 362/1000 (0.333-0.392) | 376/1000 (0.347-0.406) | +21 | 295, 32, 53, 620 |
| guard_mark_edge v t46_strike (training opponent) | reaches | 636/1000 (0.606-0.665) | 673/1000 (0.643-0.701) | 674/1000 (0.644-0.702) | 652/1000 (0.622-0.681) | +37 | 606, 30, 67, 297 |
| guard_mirror v t46_strike | reaches | 592/1000 (0.561-0.622) | 623/1000 (0.593-0.653) | 618/1000 (0.587-0.648) | 608/1000 (0.577-0.638) | +31 | 559, 33, 64, 344 |
| guard_field v t46_strike | reaches | 85/1000 (0.069-0.104) | 64/1000 (0.050-0.081) | 66/1000 (0.052-0.083) | 59/1000 (0.046-0.075) | -21 | 63, 22, 1, 914 |
| guard_mark_edge v strike_straight (script cell) | holds | 808/1000 (0.782-0.831) | 800/1000 (0.774-0.824) | 799/1000 (0.773-0.823) | 797/1000 (0.771-0.821) | -8 | 760, 48, 40, 152 |
| guard_parked_centre v strike_straight (script cell) | holds | 534/1000 (0.503-0.565) | 541/1000 (0.510-0.572) | 536/1000 (0.505-0.567) | 546/1000 (0.515-0.577) | +7 | 534, 0, 7, 459 |

Paired between the tier-2 conditions (wins in the first condition only / the second only; two-sided sign test p; records
writer's count from `games/*.npz`, checked by a numbers reviewer; **not pre-registered: 39 uncorrected tests**):

| Cell | off v nominal | off v conservative | nominal v conservative |
|---|---|---|---|
| t46_guard v strike_straight | 14 / 19 (0.49) | 20 / 29 (0.25) | 11 / 15 (0.56) |
| t46_guard v strike_flank | 12 / 19 (0.28) | 29 / 20 (0.25) | 21 / 5 (0.0025) |
| t46_guard v strike_high | 8 / 13 (0.38) | 24 / 18 (0.44) | 19 / 8 (0.052) |
| t46_guard v strike_low | 18 / 10 (0.18) | 39 / 18 (0.0075) | 23 / 10 (0.035) |
| t46_guard v strike_sacrifice | 10 / 14 (0.54) | 16 / 20 (0.62) | 9 / 9 (1) |
| t46_guard v strike_converge | 9 / 8 (1) | 23 / 12 (0.090) | 18 / 8 (0.076) |
| guard_parked_centre v t46_strike | 35 / 48 (0.19) | 38 / 86 (2e-5) | 21 / 56 (8e-5) |
| guard_parked_ring v t46_strike | 32 / 46 (0.14) | 50 / 78 (0.017) | 40 / 54 (0.18) |
| guard_mark_edge v t46_strike | 21 / 22 (1) | 47 / 26 (0.019) | 31 / 9 (0.0007) |
| guard_mirror v t46_strike | 24 / 19 (0.54) | 53 / 38 (0.14) | 32 / 22 (0.22) |
| guard_field v t46_strike | 3 / 5 (0.73) | 11 / 6 (0.33) | 10 / 3 (0.092) |
| guard_mark_edge v strike_straight (script) | 26 / 25 (1) | 41 / 38 (0.82) | 22 / 20 (0.88) |
| guard_parked_centre v strike_straight (script) | 14 / 9 (0.40) | 19 / 24 (0.54) | 6 / 16 (0.052) |

## Figures and videos

No clips: a scoring run (the players' own clips are in T46's record). A figure of the three conditions is not drawn yet.

## Ledger row

Ledger row: | T64 | 2026-11-23T04:19:31+08:00 | training simulator, tier 2 (Isaac Lab 2.3.2 rigid-body Starling, PX4 1.14 cascade copy, L1.1b estimate error off / nominal / conservative, EXPLORATORY values from T63) beside tier 1 (T46/T44 files); study tag on (P1, PROPOSED); NVIDIA GeForce RTX 5070 Ti Laptop GPU | 2026-11-23_ste_l18_tier2 | STE L1.8 T46's 1.6 m players re-scored on tier 2: error off, Guard v strike_straight holds 881 (tier 1 913), Strike v guard_mark_edge reaches 673 (636) (tier 1 v tier 2 off = a difference between two simulators); per-cell shifts −33 to +47 in both directions, no cell collapses; nominal and conservative intervals overlap error-off in every cell: the result holds with the estimate error (nominal / conservative), a test blind to shifts under about 40–60 games; worst cell guard_parked_centre v Strike 351 → 364 → 399 (paired off v conservative 38/86, not pre-registered); Strike v guard_field 64 / 66 / 59 (tier 1 85); controls PASS; 0.598 GPU-h | INFO | records/2026-11-23_ste_l18_tier2_record.md |

## Run notes added by the lead

- **Tier 2 off against tier 1 (pre-registered words; a difference between two simulators).** On the tier-2 drone with no
  estimate error the 1.6 m Guard team holds 881 (tier 1: 913) against strike_straight; the 1.6 m Strike team reaches 673
  (tier 1: 636) against guard_mark_edge. The difference goes both ways cell by cell (−33 to +47); the intervals
  separate in 2 of the 13 cells, the Guard team against strike_flank (953 → 920) and strike_converge (913 → 960), and the
  paired counts show shifts in more cells. Paired,
  the Guard team against straight loses 47 starts and gains 15; flank 43 / 10; converge 9 / 56; the Strike team against
  guard_field 22 / 1. No cell collapses; the results move by a few per cent per cell between the two drone models.
- **Estimate error (pre-registered words).** Every nominal and every conservative interval overlaps its error-off
  interval: **the result holds with the estimate error (nominal / conservative).** With 1,000 games per cell the test
  cannot see shifts smaller than about 40–60 games. Worst cell first: guard_parked_centre against the Strike team 351 →
  364 → 399 (paired off v conservative 38 / 86, p ≈ 2e-5: not pre-registered; see the next note); guard_parked_ring 348 → 362 →
  376.
- **Copy noise and the parked_centre cell (not pre-registered).** Two same-cell copies differ in which games end how
  (4–7 games flip with the error off, 35–86 with it on, each copy drawing its own error), but their totals stay within 6.
  The +48 of guard_parked_centre against the Strike team (off 351 → conservative 399; paired 38 / 86, p ≈ 2e-5) survives
  a Bonferroni correction across the 39 paired tests (0.05 / 39 = 0.0013), so it is not copy noise: a real but not
  pre-registered effect of the conservative error on that cell. Two more pairs pass the same line: that cell nominal v
  conservative (21 / 56, p ≈ 8e-5) and guard_mark_edge against the Strike team nominal v conservative (31 / 9,
  p ≈ 7e-4). A possible reading (not tested): with the error on, the parked script Guards' own drones drift too.
- **The Strike team against field Guards stays weak:** 64 / 66 / 59 (tier 1: 85).
- **Lead ruling on a control.** The spec asked for the two error-off copies to be identical; they differ in 7 and 4
  games and pass the driver's tolerance (10 holds, 20 games; L0.13's CUDA values). CUDA is not bit-exact here, as in
  L0.12d. The spec's word "identical" was too strict; accepted and recorded.
- **Limits.** The error reaches only the PX4 cascade copy: the game, the commander, the safety filter and the policy see
  the true state, so the effect on a real drone is untested and this is not a lower-bound claim. The conservative arm
  (0.0198 m) is below T63's moving spread (0.025 m); there is no speed-dependent lead and no 0.5 s tau arm. Tier 2 is not the AirStack simulator. Tag
  1.6 m only; one network per side; one start set; EXPLORATORY error values from one hover log; observed in the training
  simulator, nothing flown.
- **What it means for the plan.** L1.9 and L1.10 stay tier-1 reads; expect 3–5 % per-cell shifts in tier 2; a result near
  a gate gets a tier-2 re-score; L5.4 on tier 2 is not blocked; at 1.15 m, re-run later with a moving-error arm and
  policy-side error.
- **GPU-hours** (shared ledger): 0.598, charged to L1.8 (run cap 0.9, task cap 1.2).
