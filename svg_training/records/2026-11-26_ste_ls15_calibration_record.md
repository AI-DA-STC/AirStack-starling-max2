Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory), played on the CPU of the RTX 5090 workstation (no GPU used). Observed in the training simulator; not a flight result.

# 2026-11-26 STE LS1.5 calibration read record

**reviewed by two reviewers (numbers, completeness), 26 Nov 2026**. Written by the analyst (Opus 5.5) from the two run folders;
every number below is copied from them unless marked "computed for this record".

## Purpose

Job LS1.5 of route 3, stage LS1 (task LS1-M1-T7; plan `ste_learning/drafts/LS1_TASK_PLAN.md`, sections 1 (C7) and 2;
workflow `ste_learning/drafts/LS_EXECUTION_WORKFLOW.md` section 5). Question: on the cells, starts and statistics of the
LS1 copy check (the equivalence read LS1.2), which sizes and kinds of command error change which games? The scripts
played against deliberately changed copies of themselves (random noise, a steady bias, a scale, turns, a steady output
on the parked skill, moved switch points), with no network, so that the owner can set the LS1 limits (ruling R38). No
gate: the run passes or fails nothing. The options read from it: `ste_learning/drafts/LS1_LIMIT_OPTIONS.md`.

## Commit

`58896354` (`svg_training: LS1-M1-T7 the paired statistics and the calibration read (job LS1.5)`, authored 25 Nov 2026
19:49:13 +08:00, committed 19:58:34 +08:00), the HEAD of `development` in the worktree `~/AirStack-starling-max2-dev`, from which both jobs ran. The run
folders hold no `code.json`; the commit is taken from git (the HEAD then and now; the first launch was at 20:40), not from
a recording of the run.

## Config

| File | sha256 | Role |
|---|---|---|
| `configs/ste_ls1/calibration.toml` | `b628fa0af36390ddf2830f08923f97c3f93d232663b1591155590a70af367d76` | the error ladders; passed as `--expect-sha256` and checked at every launch |
| `configs/ste_ls1/cells.toml` | `464fa2db50ab78353604de25f0291e7ea0c3a16490d11425dd9190630ec221fd` | the cells (20 mixed combinations per side), the permutation, the INFO opponent, 1,000 games per cell |
| `configs/ste_l3/skills_gates.toml` | `e16e77298833ca1a74b8154a175f88fe5b71f87c9559e565994db1a881060f5e` | the game (T44's base), the players, `ticks_cap` 2,400 |
| `source/svg_training/opponents/scripted.py` | `b7ccafdeaa4b01c72f0ea9fa20a846e29556eaaa1c7223aee2191b76995bad3a` | the scripts (unchanged; the changed scripts are `opponents/perturbed.py`) |
| `configs/ste_l012/t44_reference.npz` | `4bc5e011071adced368b2a0025fc47499839e0bbc8d8d650207bd12c3da0f8b5` | T44, the reference on the 30 gated fixed cells per side |

The pins are as recorded in each `results.json`. The ladders (`calibration.toml`): noise 0.01, 0.02, 0.05, 0.1 on all
four channels and 0.05 on each skill's used channels only; bias 0.01, 0.02, 0.05 on x and y, and 0.0025, 0.005, 0.01 on
the zero-command skill's cells only; scale 0.95 on x, y, z; turn 1.5°, 3°, 6° of x and y; moved switches: sacrifice
entry 0.6109 and 0.6981 rad (today 0.5236), converge gather 0.15 and 0.2 rad (today 0.1), field range 1.2 and 1.3 m
(today 1.1), flank margin 0.35 and 0.4 m (today 0.3). Intervals: Newcombe paired hybrid, Bonferroni over the side's gated
cells, alpha 0.05 (z per cell 3.5879 Guard, m = 150; 3.5504 Strike, m = 130; pooled 1.9600).

## Model parameter set

The tier-1 drone model of the pinned skills gate file's game (T44's base game, as every route 2 and route 3 read). The
run folders name the simulator string above, not a parameter file.

## Seeds

Starts: T44's 1,000 starts (seed 110000, start set `5aeba7ab2b58`), hold 1, tick cap 2,400. Noise: seed 150101 plus the
cell's index in the side's full cell list times the team size plus the drone slot (the same for every noise arm).

## Machine

The home RTX 5090 workstation (AMD Ryzen 9 9950X3D, 16 cores, 32 threads); device `cpu`, `CUDA_VISIBLE_DEVICES` empty
(`job.json` env); conda `env_isaaclab` (Python 3.11). Both sides ran side by side.

## Games at once

Up to 6 cells of one opponent per game batch (`chunk_cells` 6), 1,000 games per cell: up to 6,000 games per call.

| Side | Batches | Cell-plays | Games | Arms | Cells |
|---|---|---|---|---|---|
| Guard | 450 (30 reference, 30 identity, 390 ladder) | 2,100 | 2,100,000 | 18 (`layout.json`) | 150 gated (30 fixed, 120 mixed) |
| Strike | 499 (25 reference, 30 identity, 444 ladder) | 2,334 | 2,334,000 | 22 (3 zero-skill arms with no cell: the Strike team has no zero-command skill) | 156: 130 gated (30 fixed, 100 mixed), 26 INFO against `guard_mark_inside` |

## Steps per second

Not recorded (the calibration times batches, not ticks). Games per second over the sum of batch times (computed for
this record from `timing.json`): Guard 2,100,000 games in 7,741 s, about 271 games/s; Strike 2,334,000 in 7,446 s,
about 313 games/s. These sums include the slow batches before the first stop (below).

## Gates

None (INFO): the run passes or fails nothing; see Verdict.

## Commands

Launched by `scripts/ste_job.py launch --task LS1.5 --gpu-h 0.0 --min-s 1800.0 --beat-s 60.0 --settings
configs/ste_learning.toml`, one job per side (`ls15_calibration_guard`, `ls15_calibration_strike`), child command (from
`cmd.txt`, home paths written `~/`):

```
cd ~/AirStack-starling-max2-dev/svg_training && env -u PYTHONPATH -u SVG_SHARED_DIR -u SVG_PAUSE_LEGACY_LOGS \
  CUDA_VISIBLE_DEVICES= PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True,max_split_size_mb:128 \
  ~/miniconda3/envs/env_isaaclab/bin/python scripts/ste_job.py launch --task LS1.5 --name ls15_calibration_<side> \
  --run-dir ~/AirStack-starling-max2-dev/svg_training/runs/2026-11-25_ste_ls15_calibration_<side> --min-s 1800.0 \
  --gpu-h 0.0 --settings ~/AirStack-starling-max2-dev/svg_training/configs/ste_learning.toml --beat-s 60.0 -- \
  ~/miniconda3/envs/env_isaaclab/bin/python scripts/ste_ls1_calibration.py --calibration configs/ste_ls1/calibration.toml \
  --side <side> --out runs/2026-11-25_ste_ls15_calibration_<side> \
  --expect-sha256 b628fa0af36390ddf2830f08923f97c3f93d232663b1591155590a70af367d76
```

## Launch errors and re-launches

Launches (`launches.jsonl`, times +08:00; the same for both sides to the second unless shown):

| Launch | Start | End | Exit | Boot | What ended it |
|---|---|---|---|---|---|
| 1 | 25 Nov 20:40:17 | 21:29:29 | 4 (stopped on request) | `638a3ac9…` | a stop to cap the CPU threads (the lead's account; the run files record only the stop) |
| 2 | 21:30:19 | 22:08:03 | 4 (stopped on request) | `638a3ac9…` | the owner's pause of about 22:00 (the lead's account; the run files record only the stop) |
| 3 | 26 Nov 02:45:33 | Guard 03:42:59, Strike 03:27:48 | 0 (done) | `2ff91543…` (the machine had rebooted) | finished |

Each stop is in `job.log` ("stopped (interrupted); the same command resumes at the next batch not yet done"); each
relaunch resumed at the next batch not yet saved (the run contract: a partial batch is dropped, saved batches are kept;
`results.json` is built from the batch files only). Thread caps: the lead reports caps of 10 and then 8 threads, passed
through the environment; neither `cmd.txt` nor `job.json` (env: `CUDA_VISIBLE_DEVICES`, `PYTORCH_CUDA_ALLOC_CONF` only)
records them, so which launch ran under which cap is the lead's account, not the run files'; the thread setting of
launch 3 is unknown. Likewise the files do not record the reason for either stop (the 22:00 pause included) or for the
reboot: they show only the two "stopped (interrupted)" lines in `job.log`, exit 4 twice on boot `638a3ac9…`, and a new
boot `2ff91543…` for launch 3. The cause of the slow batches below is not established. What the files do show:
before the first stop some batches were very slow (Guard `batch_identity__strike_sacrifice_02` 835.4 s,
`..._01` 473.0 s; Strike `batch_reference__guard_mark_inside_00` 1,471.5 s, 6 cells each), and the first batches after
the restart took 17.3 s (Guard) and 35.2 s (Strike).

## Timing

| Side | Effective seconds (`progress.json`) | Sum of batch seconds (`timing.json`) | Wall clock, first launch to end |
|---|---|---|---|
| Guard | 8,656.7 s (2.40 h) | 7,741 s (2.15 h) | 7 h 03 min (4 h 38 min of it stopped) |
| Strike | 7,745.2 s (2.15 h) | 7,446 s (2.07 h) | 6 h 48 min (4 h 38 min stopped) |

The effective seconds equal the sum of the three launches' lengths to within 5 s (computed for this record from
`launches.jsonl`: Guard 8,661 s, Strike 7,750 s, about 4.6 s more than `progress.json` on each side).
The calibration file's estimate was "about 2 to 3 h per side on an idle CPU".

## Controls

Every batch PASS (`controls.json`: Guard 450 of 450, Strike 499 of 499; no FAIL in `job.log`):

| Control | Batches | Result |
|---|---|---|
| `ctl_paired_starts` | every batch | 1 start set, reference `5aeba7ab2b58` |
| `tags_one_for_one` | every batch | 0 games not one for one, both sides |
| `no_nonfinite_actions` | every batch | 0 non-finite actions |
| `all_games_finished` | every batch | 0 unfinished games |
| `replay_t44` | the identity batches with gated fixed cells (6 Guard, 5 Strike) | all 30 gated fixed cells per side equal T44 game for game |
| `identity_no_flip` | the 30 identity batches per side | b = c = 0 on every cell (Guard 150, Strike 156) |

## Results

Gate: none (INFO). Summary per arm, gated cells only (Guard 150, Strike 130; the switch and zero-skill arms on the cells
where their code flies); games changed = b + c per cell of 1,000; pooled = the mean difference over the gated cells with
its 95 % interval (negative: the changed copy wins less); RMSE = the largest RMSE of a skill on a channel it uses; largest net = the largest |c − b| in one cell. From
`results.json`; the medians and maxima over gated cells were computed for this record (the Strike team's `results.md`
rows include its 26 INFO cells).

**Guard team**

| Arm | Games changed median / largest | Largest net (games) | Pooled [95 %] | RMSE |
|---|---|---|---|---|
| identity | 0 / 0 | 0 | +0.0000 | 0 |
| noise 0.01 / 0.02 / 0.05 / 0.1 | 1 / 6; 3 / 11; 7.5 / 21; 15 / 37 | 6; 6; 10; 16 | −0.0003; −0.0005; −0.0015; −0.0034 [−0.0044, −0.0024] | 0.0058; 0.0116; 0.0289; 0.0578 |
| noise 0.05, used channels only | 6 / 20 | 9 | −0.0016 [−0.0022, −0.0011] | 0.0289 |
| bias 0.01 / 0.02 / 0.05 | 9 / 31; 17 / 63; 38 / 150 | 15; 21; 63 | −0.0001; −0.0009; −0.0044 [−0.0070, −0.0017] | 0.0100; 0.0200; 0.0500 |
| parked-skill bias 0.0025 / 0.005 / 0.01 (6 cells) | 2 / 9; 5.5 / 15; 12.5 / 21 | 5; 9; 15 | +0.0000; +0.0003; −0.0017 [−0.0047, +0.0014] | (largest output 0.0025; 0.005; 0.01) |
| scale 0.95 | 17 / 49 | 25 | −0.0066 [−0.0080, −0.0051] | 0.0354 |
| turn 1.5° / 3° / 6° | 9 / 34; 17 / 52; 30.5 / 94 | 13; 12; 23 | −0.0001; −0.0005; −0.0020 [−0.0043, +0.0002] | 0.0185; 0.0371; 0.0741 |
| field range 1.2 / 1.3 m (6 cells) | 1 / 3; 7 / 9 | 1; 8 | −0.0005; −0.0050 [−0.0075, −0.0025] | 0.0217; 0.0523 |

**Strike team**

| Arm | Games changed median / largest | Largest net (games) | Pooled [95 %] | RMSE |
|---|---|---|---|---|
| identity | 0 / 0 | 0 | +0.0000 | 0 |
| noise 0.01 / 0.02 / 0.05 / 0.1 | 5 / 18; 8 / 27; 13 / 37; 18 / 56 | 14; 21; 25; 32 | −0.0004; −0.0029; −0.0050; −0.0062 [−0.0077, −0.0047] | 0.0057; 0.0114; 0.0284; 0.0564 |
| noise 0.05, used channels only | 13 / 37 | 25 | −0.0050 [−0.0061, −0.0039] | 0.0284 |
| bias 0.01 / 0.02 / 0.05 | 9 / 20; 13 / 24; 31 / 58 | 13; 14; 20 | −0.0029; −0.0042; −0.0071 [−0.0095, −0.0046] | 0.0099; 0.0198; 0.0492 |
| scale 0.95 | 17 / 43 | 32 | −0.0096 [−0.0113, −0.0080] | 0.0355 |
| turn 1.5° / 3° / 6° | 10 / 21; 19.5 / 38; 38 / 75 | 10; 13; 23 | +0.0003; +0.0009; +0.0001 [−0.0027, +0.0028] | 0.0186; 0.0371; 0.0742 |
| sacrifice entry 0.6109 / 0.6981 rad (5 cells) | 7 / 12; 17 / 22 | 12; 12 | +0.0024; −0.0016 [−0.0056, +0.0024] | 0.1298; 0.1756 |
| converge gather 0.15 / 0.2 rad (5 cells) | 14 / 23; 29 / 30 | 8; 6 | −0.0004; +0.0040 [−0.0011, +0.0091] | 0.1329; 0.2327 |
| flank margin 0.35 / 0.4 m (65 cells) | 4 / 15; 5 / 20 | 7; 12 | −0.0004; −0.0012 [−0.0019, −0.0005] | 0.0095; 0.0188 |

Every cell's b, c, intervals (plain and corrected), sign-test p and end-step statistics, and the command-error table per
skill and channel, are in `results.json`.

**Labels** (the identity arm's, M2-T3's rule): Guard: zero-command skill `guard_parked_centre`; the other four skills use
channels 0 and 1. Strike: no zero-command skill; `strike_high` and `strike_low` use channels 0, 1, 2, the other four 0
and 1.

**The permuted scripts** (from T44, no play; code k flies code perm[k], 30 gated fixed cells): Guard (perm `[1, 2, 3, 4,
0]`) 19 cells with the corrected interval excluding 0, 24 at plain alpha; Strike (`[1, 2, 3, 4, 5, 0]`) 21 and 25. Largest:
Guard `guard_parked_ring` flown as `guard_mark_edge` v `strike_sacrifice`, +0.4570 (21 lost, 478 won); Strike
`strike_sacrifice` flown as `strike_converge` v `guard_parked_ring`, −0.4800 (492 lost, 12 won). Full tables:
`results.md`.

## Verdict

**INFO.** No pass or fail by design: the owner sets the LS1 limits from this read (R38). Both runs complete
(`complete: true`), every control PASS, exit 0.

## Videos

None: the calibration plays no network and writes no clips (a CPU read of the scripts against changed scripts).

## GPU hours

0 GPU-h (both jobs launched with `--gpu-h 0.0`, `CUDA_VISIBLE_DEVICES` empty; no LS1.5 line in the shared GPU-hour
ledger).

## What this does not show

- A network's error: the injected errors are spread evenly over every tick, drone and skill; a fitted network's error is
  systematic and concentrated (switch points, rarely visited states, fewer live drones).
- More than one set of starts: T44's 1,000 starts per cell; one noise realisation (seed 150101).
- A steady output on an unused channel (vz, yaw rate); the moved switches beyond their two rungs.
- Tier 2, or any flight.

## Evidence

Run folders (not in git), in `~/AirStack-starling-max2-dev/svg_training/runs/`: `2026-11-25_ste_ls15_calibration_guard/`
and `2026-11-25_ste_ls15_calibration_strike/` (`results.json`, `results.md`, `controls.json`, `layout.json`,
`timing.json`, `job.log`, `cmd.txt`, `launches.jsonl`, `job.json`, `progress.json`, `exit_code*`, and the
`batch_*.npz` files). sha256 of the summary files:

| File | Guard | Strike |
|---|---|---|
| `results.json` | `d271dc75504362a9f7e2b06f020f2b45e4c673b26b499840afd0b60f2a2f3967` | `868e8b41ac0b2b72b004558502164abb8b46ec27caa3da292012838b3ffb6561` |
| `results.md` | `1f16b2a6f7dbb475047d626614460fe1079749db6ce4ddf43d9891879600105e` | `356c55aebb8c6ed3bdfa890160c3deb61bb2835accd0e93f1321cca264d88501` |
| `controls.json` | `9b73063f6c66756e89ed68718a6599e88d69b4858b2ad1a7c912db0250582f11` | `106c989634769b59a20e621f3efd0369c8261d2b973ad7b86a649e8cfee2a598` |
| `layout.json` | `ef2929fc45ea638a7425cbcc8cae9682894da270084a1cae0ca6d936e4674d6b` | `2b3595fb4ac91910cd4ac35c4691aa778a7d77671e53120ee8ac49adc6c1e47d` |
| `timing.json` | `6869f3fac88b8de8b83373a890e2a774336c77b37751dd0f55b3b16b32734c14` | `5c05479a879bcfd99fb57f6d5d316ae4d598c7b1f0c203b071dcebbeb806f628` |

No evidence copies under `records/evidence/` yet (the lead's step at review).

## Ledger row (T90)

| # | Date | Simulator | Run | What | Result | Record |
|---|---|---|---|---|---|---|
| T90 | 2026-11-26T03:42:59+08:00 | training simulator, tier 1 (fast engine; Starling layer); CPU | 2026-11-25_ste_ls15_calibration_{guard,strike} | STE LS1.5 calibration read: the scripts v changed scripts (noise, bias, scale, turn, parked-skill bias, moved switches), 2,100,000 (Guard) and 2,334,000 (Strike) games on the LS1 read's cells and T44's starts; every control PASS (450 and 499 batches); two stops and a reboot, resumed from saved batches; 0 GPU-h | INFO | `records/2026-11-26_ste_ls15_calibration_record.md` |
