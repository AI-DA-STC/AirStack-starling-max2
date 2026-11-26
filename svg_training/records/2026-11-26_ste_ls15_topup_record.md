Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory), played on the CPU of the RTX 5090 workstation (no GPU used). Observed in the training simulator; not a flight result.

# 2026-11-26 STE LS1.5 top-up calibration record

**reviewed by one reviewer, 26 Nov 2026**. Written by the technical writer (Sonnet 5.5) from the two run folders, the
two config files and the gate file; every number below is copied from them unless marked "computed for this record".

## Purpose

Job LS1.5 of route 3, stage LS1 (plan `ste_learning/drafts/LS1_TASK_PLAN.md`), a top-up of the calibration read T90
(`records/2026-11-26_ste_ls15_calibration_record.md`). Owner ruling R48, 26 Nov 2026, on `LS1_LIMIT_OPTIONS.md`: "accept
recommended, top-up yes" (`ste_learning/DISCUSSION_2026-11-19_20.md`). Question: T90's largest field-range rung (1.3 m)
and flank-margin rung (0.4 m) moved too few games to show where a moved switch would fail the limits; with two larger
rungs of each, which is the smallest that fails with room under the limits? No gate: the run passes or fails nothing.
The chosen values are in `configs/ste_ls1/distil_gates.toml` (`[controls.near_miss.switch]`), see "Chosen values".

## Commit

Not recorded in the run folders (they hold no `code.json`; the job started 26 Nov 2026 08:27:38 +08:00). From `git log`
(not from the run files): the last commit before the launch was `54ec0402` (06:35:22), and `configs/ste_ls1/calibration_topup.toml`
was not yet committed when the job ran (it was first committed in `cb30ec45`, 08:45:00); its sha256 pin in the gate file
matches the file now. The worktree is `~/AirStack-starling-max2-dev`. No change of `scripts/ste_ls1_calibration.py` is claimed here.

## Config

| File | sha256 | Role |
|---|---|---|
| `configs/ste_ls1/calibration_topup.toml` | `0c3668db1460d5bd9bc7df307ec55f09977c706d291a0da084352d4771584b55` | a copy of `calibration.toml` with `field_range_m = [1.5, 1.8]` and `flank_margin_m = [0.6, 0.9]` (T90's were 1.2, 1.3 and 0.35, 0.4); passed as `--expect-sha256` |
| `configs/ste_ls1/cells.toml` | `464fa2db50ab78353604de25f0291e7ea0c3a16490d11425dd9190630ec221fd` | the cells, 1,000 games per cell |
| `configs/ste_l3/skills_gates.toml` | `e16e77298833ca1a74b8154a175f88fe5b71f87c9559e565994db1a881060f5e` | the game, the players, `ticks_cap` 2,400 |
| `source/svg_training/opponents/scripted.py` | `b7ccafdeaa4b01c72f0ea9fa20a846e29556eaaa1c7223aee2191b76995bad3a` | the scripts (unchanged) |

Pins as in each `results.json`. All other keys of `calibration_topup.toml` equal `calibration.toml` (a copy; not diffed
for this record). Intervals: Newcombe paired hybrid, Bonferroni over the side's gated cells, alpha 0.05 (z per cell
3.5879 Guard, m = 150; 3.5504 Strike, m = 130; pooled 1.9600).

## Model parameter set

The tier-1 drone model of the pinned skills gate file's game (T44's base game); the run folders name the simulator
string above, not a parameter file.

## Seeds

T44's 1,000 starts (seed 110000, start set `5aeba7ab2b58`), hold 1, tick cap 2,400. Moved-switch arms use no noise.

## Machine

The home RTX 5090 workstation; device `cpu`, `CUDA_VISIBLE_DEVICES` empty (`cmd.txt`); conda `env_isaaclab`. Both sides
ran side by side, one launch each, boot `2ff91543…`, exit 0.

## Games at once

Test-only options, so `of_record` is false in both `results.json` (title of `results.md`: "NOT of record"):
`--opponents`, `--arms`, `--mixed 0`. One cell per arm (the near-miss cell of that arm's player), 1,000 games.

| Side | Options | Batches | Cells played |
|---|---|---|---|
| Guard | `--opponents strike_straight --mixed 0 --arms field_range_m=1.5 field_range_m=1.8` | 3 (identity 5 cells, 2 arms of 1 cell) | the fixed cell `guard_field` x3 v `strike_straight` (cell index 4), per arm |
| Strike | `--opponents guard_mark_edge --mixed 0 --arms flank_margin_m=0.6 flank_margin_m=0.9` | 3 (identity 6 cells, 2 arms of 1 cell) | the fixed cell `strike_flank` x3 v `guard_mark_edge` (cell index 53), per arm |

## Steps per second

Not recorded (the calibration times batches, not ticks). Batch seconds from `timing.json`: Guard identity 5.6 s, each
arm 1.8 s; Strike identity 24.2 s, each arm 2.2 s.

## Gates

None (INFO).

## Commands

Launched with `scripts/ste_job.py launch --task LS1.5 --gpu-h 0.0 --min-s 5.0 --beat-s 60.0 --settings
configs/ste_learning.toml`, one job per side (`ls15_topup_guard`, `ls15_topup_strike`); child command (from `cmd.txt`,
home paths written `~/`):

```
~/miniconda3/envs/env_isaaclab/bin/python scripts/ste_ls1_calibration.py --calibration configs/ste_ls1/calibration_topup.toml \
  --side <side> --out runs/2026-11-26_ste_ls15_topup_<side> \
  --expect-sha256 0c3668db1460d5bd9bc7df307ec55f09977c706d291a0da084352d4771584b55 \
  <guard: --opponents strike_straight --mixed 0 --arms field_range_m=1.5 field_range_m=1.8>
  <strike: --opponents guard_mark_edge --mixed 0 --arms flank_margin_m=0.6 flank_margin_m=0.9>
```

## Launch errors and re-launches

None: one launch per side (`launches.jsonl`): Guard 26 Nov 08:27:38 to 08:27:48 (about 10 s), Strike 08:27:38 to 08:28:08
(about 30 s), both exit 0 (times computed for this record from the epoch times in `launches.jsonl`).

## Controls

Every batch PASS (`controls.json`, 3 of 3 per side; `job.log`): `ctl_paired_starts` (start set `5aeba7ab2b58`),
`tags_one_for_one`, `no_nonfinite_actions`, `all_games_finished`, `replay_t44` (Guard 5, Strike 6 gated fixed cells
equal T44 game for game), `identity_no_flip` (b = c = 0 on 5 and 6 cells).

## Results

Gate: none (INFO). Games changed = b + c of 1,000; net = \|c - b\|; difference = the arm's win share less the reference's
(negative: the changed copy wins less). With one cell per arm, the pooled point difference equals that cell's difference
(computed for this record from the table rows). The interval in the Difference column is the cell's plain Newcombe interval;
the arm's pooled interval in `results.md` is slightly different (for example Guard 1.5 m [-0.0544, -0.0296]). From `results.json` and `results.md`.

| Side | Rung | b | c | Games changed | Net \|c - b\| | Difference [95 %, plain] | Adjusted interval excludes 0 | RMSE (largest on a used channel) |
|---|---|---|---|---|---|---|---|---|
| Guard | field range 1.5 m | 42 | 0 | 42 | 42 games | -0.0420 [-0.0546, -0.0296] | yes | 0.1174 |
| Guard | field range 1.8 m | 62 | 0 | 62 | 62 games | -0.0620 [-0.0771, -0.0471] | yes | 0.1934 |
| Strike | flank margin 0.6 m | 20 | 8 | 28 | 12 games | -0.0120 [-0.0230, -0.0015] | no | 0.0550 |
| Strike | flank margin 0.9 m | 38 | 14 | 52 | 24 games | -0.0240 [-0.0387, -0.0100] | no | 0.1024 |

Unused-channel maximum 0.0000 on all four arms. Guard 1.5 m adjusted interval [-0.0654, -0.0191];
1.8 m [-0.0898, -0.0346]. Strike 0.6 m adjusted [-0.0337, +0.0083]; 0.9 m adjusted [-0.0521, +0.0022]. For comparison, T90's largest rungs (its RMSE, on T90's cells): field 1.3 m 0.0523, flank 0.4 m 0.0188.

The permuted-scripts table in each `results.md` (from T44, no play) is on 5 (Guard) and 6 (Strike) cells only, since
the run has no mixed cells; it is not a result of this read.

## Chosen values

Not written by this run: the choice is in the gate file (`configs/ste_ls1/distil_gates.toml`, sha256
`5cce1245052f2e9ef87d6a3c83d2301f1161100ed818224b932b0248735ee6bb`, which cites this record as "record T91"), with the
owner's "top-up yes" (R48). Its comments give the reason; each comment opens with `FIXED (owner, R48, 26 Nov 2026: "top-up yes"; ...)` and the text after it is quoted:

- `flank_margin_m = 0.9`: "the smallest top-up rung that fails with room under the limits above, record T91): 0.6
  failed only by RMSE 0.055 v 0.05 and pooled 0.012 v 0.01".
- `field_range_m = 1.5`: "the smallest top-up rung that fails with room under the limits above, record T91): RMSE
  0.117, 42 games, pooled 0.042".

Checked against the table and the limits of the same file (`cmd_rmse_max` 0.05, `flips_max_games` 30, `pooled_margin`
0.01; computed for this record): field 1.5 m: RMSE 0.1174 (> 0.05), 42 games (> 30), 0.042 (> 0.01); flank 0.6 m:
RMSE 0.0550 (> 0.05), 28 games (< 30), 0.012 (> 0.01); flank 0.9 m: RMSE 0.1024, 52 games, 0.024.

## Verdict

**INFO.** No pass or fail by design. Both runs complete (`complete: true`), every control PASS, exit 0.

## Videos

None: the calibration plays no network and writes no clips.

## GPU hours

0 GPU-h (`--gpu-h 0.0`, `CUDA_VISIBLE_DEVICES` empty).

## What this does not show

- One cell per arm and one set of starts (T44's); the rung that fails here may differ on other cells.
- A network's error: the moved switches are scripted, spread evenly over the game.
- Tier 2, or any flight.

## Evidence

Run folders (not in git), in `~/AirStack-starling-max2-dev/svg_training/runs/`: `2026-11-26_ste_ls15_topup_guard/` and
`2026-11-26_ste_ls15_topup_strike/` (`results.json`, `results.md`, `controls.json`, `layout.json`, `timing.json`,
`job.log`, `cmd.txt`, `launches.jsonl`, `batch_*.npz`). sha256:

| File | Guard | Strike |
|---|---|---|
| `results.json` | `52f41f35159b67bb9382cfa70ab9dc524e0e82b1f5d22a14cf1d2bbdf2bae1da` | `bedc64c53093fc49d5bf3feea821b405274529e672f6f891b85e82e52e50e096` |
| `results.md` | `88b88e68713a114cdd1861dfdb325b1a0e44c579d7559aeb4d7810fc12fd5c11` | `58311451b0e828b88d730544e10ba392b9a1e6e4b5e80af2c6bcf1ffe428a2c1` |
| `controls.json` | `fbf452f12078fce1b1c1991f222fd3c307e820b149cc5eb7f3bceac0eb6e3d25` | `697f6e79ecd9984822e5a50d74298a8deca07c8464c613ed43ffb97f2c99ea46` |

## Ledger row (T91)

| # | Date | Simulator | Run | What | Result | Record |
|---|---|---|---|---|---|---|
| T91 | 2026-11-26T08:28:08+08:00 | training simulator, tier 1 (fast engine; Starling layer); CPU | 2026-11-26_ste_ls15_topup_{guard,strike} | STE LS1.5 top-up calibration (owner R48): larger moved-switch rungs on the near-miss cells, 1,000 games each, T44's starts; test-only options (--opponents, --arms, --mixed 0), not of record; Guard field range 1.5 m: 42 games changed, net 42, RMSE 0.117; 1.8 m: 62, net 62, RMSE 0.193; Strike flank margin 0.6 m: 28 changed, net 12, RMSE 0.055; 0.9 m: 52, net 24, RMSE 0.102; chosen flank 0.9 and field 1.5 (gate file `distil_gates.toml`); every control PASS; 0 GPU-h | INFO | `records/2026-11-26_ste_ls15_topup_record.md` |
