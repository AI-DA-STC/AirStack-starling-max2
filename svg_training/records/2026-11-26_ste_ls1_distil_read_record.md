Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory). LS1.1 (the fit) ran on the GPU of the RTX 5090 workstation; LS1.2 (the copy check) on its CPU. Observed in the training simulator; not a flight result.

# 2026-11-26 STE LS1.1 distillation and LS1.2 copy check record

**Reviewed by two reviewers (numbers, reasoning), 26 Nov 2026.** Written by the technical writer (Sonnet 5.5) from the four run folders and the shared GPU-hour log; the reviewers' fixes applied by the analyst (Opus 5.5) after a check against the source (timing, rounding, GPU-hour accounting, steps per second, per-gate table, INFO cells, commit note). Every number below is copied from those files unless marked "computed for this record".

## Purpose

Jobs LS1.1 and LS1.2 of route 3, stage LS1 (plan `ste_learning/drafts/LS1_TASK_PLAN.md`; workflow `ste_learning/drafts/LS_EXECUTION_WORKFLOW.md` sections 3 and 5; rulings R38, R46 to R48 in `ste_learning/DISCUSSION_2026-11-19_20.md`). LS1.1: one skill network per team, fitted by supervised distillation to copy that team's hand-written scripts (`opponents/scripted.py`), 4 relabelling rounds (script share 1.0, 0.5, 0.25, 0.0), ledger row T93. LS1.2: the copy check, which plays the network against the scripts on the same cells and starts and reads the result against the owner's limits (R48), ledger row T94. Question: does each network copy its scripts within the limits? The gate decides; no limit is moved.

## Commit

| Job | Commit | Uncommitted diff at launch |
|---|---|---|
| LS1.1 (both sides) | `a57d1e69` (`svg_training: LS1 copy check: an end-to-end test with real controls outside --smoke; plan lines`, 26 Nov 2026 09:04:41 +08:00), from `code.json` | none (`diff_sha256` is the hash of the empty diff, `e3b0c442…`) |
| LS1.2 (both sides) | `e353d88d` (`svg_training: HANDOFF: M1-M3 merged, limits set (R48), LS1.1 running`, 09:53:38 +08:00), from `code.json` | present: `diff_sha256` `4c1ab19234cbd49e197d8128437bccab66fdffa9ea103923e87273dc496a8659` (not the empty diff). The diff itself is not stored in the run folders, so which working-tree changes ran in LS1.2 is not recoverable from them; the worktree HEAD now is `79a3e10c`. The diff is lost: the code of the read cannot be rebuilt from this record, and the read is of record on the strength of its controls (119 and 117 PASS, the oracle network equal to the scripts game for game included), not of a reproducible commit. The lead's check: the next commit on `development` after `e353d88d` (`2d10a868`) changes only records and pages, so the diff was most likely documents; the hash does not reproduce from that commit's changes. |

Branch `development`, worktree `~/AirStack-starling-max2-dev`.

## Config

| File | sha256 | Role |
|---|---|---|
| `configs/ste_ls1/distil_gates.toml` | `5cce1245052f2e9ef87d6a3c83d2301f1161100ed818224b932b0248735ee6bb` | the limits (R48), the data mix, the net, the fit, the stop rules; passed as `--expect-gates-sha256`; a copy and its hash are in each run folder (`gates.toml`, `gates.sha256`) |
| `configs/ste_l3/skills_gates.toml` | `e16e77298833ca1a74b8154a175f88fe5b71f87c9559e565994db1a881060f5e` | the game (T44's base), the players |
| `configs/ste_ls1/cells.toml` | `464fa2db50ab78353604de25f0291e7ea0c3a16490d11425dd9190630ec221fd` | the cells and the permutation |
| `source/svg_training/opponents/scripted.py` | `b7ccafdeaa4b01c72f0ea9fa20a846e29556eaaa1c7223aee2191b76995bad3a` | the scripts |
| `configs/ste_l011/base.toml` | `96e0e7f61a49999da54eee81a544bf64c519cd80833f0dcdfa2a07edfc10cc4d` | the game file |

The pins are as listed in `distil_gates.toml` `[source]`. Limits (`[limits]`, owner R48 "accept recommended"): command RMSE on an active channel 0.05; unused channel largest output 0.05; zero-command skill largest output 0.005; games changed per cell (b + c of 1,000) 30; per-cell interval inside +-0.045; pooled interval inside +-0.01; end-time not gated. Controls: permuted codes and unfitted network each miss at least 15 cells; near-miss bias 0.05, turn 6.0 degrees, noise 0.02 (must pass), plus the owner's top-up rungs (Guard field range 1.5 m, record T91; Strike flank margin 0.9 m). Intervals: Newcombe paired hybrid, Bonferroni over the side's gated cells, alpha 0.05 (z per cell 3.5879 Guard, m = 150; 3.5504 Strike, m = 130; pooled 1.9600).

Fit settings (`distil_gates.toml`): net hidden [256, 256, 256], zeroed inputs [6, 7, 10, 11] (yaw sine and cosine, time left, team flag), 40 epochs, learning rate 0.001, batch 8,192, 2,000,000 kept rows per round, 4,096 games and 600 ticks per round, data mix uniform 0.5 / mix 0.25 / random 0.25, hold 12.

Trained networks (`fit_report.json`, same as the files on disk):

| Side | File | sha256 |
|---|---|---|
| Guard | `runs/2026-11-26_ste_ls11_distil_guard/skill_net_guard.pt` | `0ba9fc7605b953f40bd96a51eae40877c27d9c6c9473b36c48c7eb3ea18e5640` |
| Strike | `runs/2026-11-26_ste_ls11_distil_strike/skill_net_strike.pt` | `699011e29a74c5d923ec5c75f56df306ffa364fd43de22179bcf77e64b16540e` |

## Model parameter set

The tier-1 drone model of the pinned skills gate file's game (T44's base game). The run folders name the simulator string above, not a parameter file.

## Seeds

Data games and schedule 150001; opponent pool 150002; fit 150003; report 150004; clips 150005 (`distil_gates.toml`). The copy check plays T44's 1,000 starts (seed 110000, start set `5aeba7ab2b58`), hold 1, tick cap 2,400.

## Machine

Home RTX 5090 workstation; LS1.1 on CUDA (`device = "cuda"`), LS1.2 on the CPU (`CUDA_VISIBLE_DEVICES` empty), conda `env_isaaclab`. Both sides of each job ran side by side. Boot `2ff91543-c8a5-42d0-a41e-0de33a601111` for all four launches. The CPU thread cap of LS1.2 is not recorded in `cmd.txt`, `job.json` or `job.log` of either side (searched for a thread or `OMP` setting at review: none).

## Games at once

LS1.1: 4,096 games per round, 600 ticks. LS1.2: up to 6 cells of one opponent per batch, 1,000 games per cell (6,000 games per call).

| Side | LS1.2 cells | Batches (`progress.json` step) |
|---|---|---|
| Guard | 150 gated (30 fixed, 120 mixed) | 109 |
| Strike | 130 gated (30 fixed, 100 mixed) and 26 INFO against `guard_mark_inside` | 105 |

## Steps per second

LS1.1, training simulator tier 1 on the RTX 5090: `fit_report.json` `final.game_steps_per_s` is **34,062 game-steps per second (Guard)** and **52,005 (Strike)**: games x ticks over the seconds of the report's collection (`[report]` 1,024 games x 600 ticks, net-flown, `distil.report`), the whole loop of game, network, opponent pool and the scripts' labels, so a lower bound of the network's own speed; with 6 drones per game (the skills gate file's `[run] size` "3v3", passed to the report; drones out by a tag still counted) that is about 204,000 and 312,000 drone-steps per second (computed for this record). Guard's figure was measured beside Strike's last fit. Strike's was most likely measured alone: its four rounds end at about 568 s, after Guard's job ended at 567 s (computed from `fit_report.json` and `launches.jsonl`). Games per second of LS1.2 (CPU) not computed.

## Gates

The gate is `distil_gates.toml` `[limits]` read by `scripts/ste_ls1_equivalence.py`; verdict DISTILLED or NOT DISTILLED. LS1.1 has no gate of its own (its control is the label check).

| Side | Verdict (`results.json`) | Failed limits |
|---|---|---|
| Guard | NOT DISTILLED | 18 |
| Strike | NOT DISTILLED | 98 |

Each limit (`results.json` `failures`, counted by limit for this record; values from `results.md` and `results.json`):

| Limit | Guard | Strike |
|---|---|---|
| command RMSE, active channel, 0.05 | FAIL (4: mirror x, y; field x, y) | FAIL (6: flank, sacrifice, converge, x and y) |
| unused channel largest output, 0.05 | PASS (0.0134) | PASS (0.0428) |
| zero-command skill largest output, 0.005 | FAIL (1: `guard_parked_centre` 0.0351) | not applicable (no zero-command skill) |
| games changed per cell, 30 | FAIL (12 of 150 cells) | FAIL (64 of 130 cells) |
| per-cell interval inside +-0.045 | FAIL (1 cell) | FAIL (27 cells) |
| pooled interval inside +-0.01 | PASS ([-0.0035, -0.0013]) | FAIL ([-0.0111, -0.0066]) |

`guard_parked_ring` (0.042, 0.037) and `guard_mark_edge`, and Strike's straight, high and low, pass the command limit.

## Commands

Both jobs launched by `scripts/ste_job.py launch` (from `cmd.txt`, home paths written `~/`), one job per side; settings `configs/ste_learning.toml`, `--beat-s 60.0`.

LS1.1 (`--task LS1.1 --name ls11_distil_<side> --min-s 60.0 --gpu-h 0.4`):

```
cd ~/AirStack-starling-max2-dev/svg_training && env -u PYTHONPATH -u CUDA_VISIBLE_DEVICES -u SVG_SHARED_DIR -u SVG_PAUSE_LEGACY_LOGS \
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True,max_split_size_mb:128 ~/miniconda3/envs/env_isaaclab/bin/python \
  scripts/ste_job.py launch --task LS1.1 --name ls11_distil_<side> --run-dir ~/AirStack-starling-max2-dev/svg_training/runs/2026-11-26_ste_ls11_distil_<side> \
  --min-s 60.0 --gpu-h 0.4 --settings configs/ste_learning.toml --beat-s 60.0 -- \
  ~/miniconda3/envs/env_isaaclab/bin/python scripts/ste_ls1_distil.py --gates configs/ste_ls1/distil_gates.toml --side <side> \
  --run-dir runs/2026-11-26_ste_ls11_distil_<side> --cap-h 0.4 \
  --expect-gates-sha256 5cce1245052f2e9ef87d6a3c83d2301f1161100ed818224b932b0248735ee6bb
```

LS1.2 (`--task LS1.2 --name ls12_read_<side> --min-s 600.0 --gpu-h 0.0`, `CUDA_VISIBLE_DEVICES=` set empty):

```
... scripts/ste_ls1_equivalence.py --gates configs/ste_ls1/distil_gates.toml --side <side> \
  --skill-net runs/2026-11-26_ste_ls11_distil_<side>/skill_net_<side>.pt --run-dir runs/2026-11-26_ste_ls12_read_<side> --cap-h 12 \
  --expect-gates-sha256 5cce1245052f2e9ef87d6a3c83d2301f1161100ed818224b932b0248735ee6bb
```

## Launch errors and re-launches

None. One launch each (`launches.jsonl`), exit 0 (`exit_code`), no stops. Times (+08:00, 26 Nov 2026):

| Job | Start | End | Wall |
|---|---|---|---|
| ls11_distil_guard | 09:51:45 | 10:01:12 | 567 s |
| ls11_distil_strike | 09:51:45 | 10:01:50 | 605 s |
| ls12_read_guard | 10:02:15 | 10:39:51 | 2,256 s |
| ls12_read_strike | 10:02:15 | 10:55:27 | 3,192 s |

(Wall computed for this record from `launches.jsonl`.)

## Timing

| Job | Effective seconds (`progress.json`) |
|---|---|
| LS1.1 Guard | 565.8 s |
| LS1.1 Strike | 603.4 s |
| LS1.2 Guard (CPU) | 2,255.2 s |
| LS1.2 Strike (CPU) | 3,190.7 s |

CPU time (user plus system) is not recorded by the job files; the figures above are wall-clock seconds of the job. LS1.1 rounds (`fit_report.json`, `seconds`): Guard 63.5, 109.1, 155.5, 200.5 s; Strike 68.8, 120.5, 170.8, 208.4 s. Each is one round's own time, collection plus keep plus fit (`scripts/ste_ls1_distil.py`: the round's collection seconds plus its refit; `distil.round_summary`: "collection, keep and fit"); they grow because each refit fits all rows so far. The four values sum to 528.6 s (Guard) and 568.4 s (Strike) of the 565.8 s and 603.4 s jobs (computed for this record); the rest is start-up, the report and the clips.

## GPU hours

Summed from `~/AirStack-starling-max2/svg_training/runs/shared/gpu_hours.log` (60 s slices per job, computed for this record):

| Job | Seconds | GPU-h | Cap (`--gpu-h`) |
|---|---|---|---|
| `ls11_distil_guard` | 567.3 | 0.158 | 0.4 |
| `ls11_distil_strike` | 604.8 | 0.168 | 0.4 |
| LS1.1 both | 1,172.1 | 0.326 | 0.8 |

LS1.2: 0 GPU-h (`--gpu-h 0.0`, CPU; no LS1.2 line in the log). The earlier LS1.1 label-tolerance probe (0.0038 GPU-h, record T92) is not in these sums.

Two figures, two accountings: summed per job, the two jobs are 0.326 GPU-h. The budget ledger (`ste/budget.py`, the launch check `check_launch` and `scripts/ste_job.py status`) counts the union of the intervals, so the side-by-side overlap counts once: LS1.1 has used **0.172 GPU-h** (the two jobs alone 0.168, as Strike's interval covers Guard's, plus the 0.004 probe; `status`: "budget_ls used 0.172"), against the LS1.1 task cap of 0.8. The cap test uses the 0.172.

## Controls

**LS1.1** (`controls.json`, identical file on both sides): `ctl_labels_are_the_scripts` PASS; in each of the 4 rounds 0 of 2,000,000 kept rows differ from the scripts by more than `label_check_atol` 1e-05 (0 not bit-equal, largest |difference| 0).

**LS1.2** (`controls.json`): every control PASS, **119 of 119 on Guard and 117 of 117 on Strike**; no FAIL. They are, per side: the per-batch controls (paired starts, one-for-one tags, no non-finite actions, all games finished, `replay_t44` for the fixed cells), `ctl_scripts_equal_t44`, `ctl_scripts_mixed_play`, `ctl_oracle_net_equals_scripts`, `ctl_permuted_scripts_miss`, `ctl_unfitted_net_misses`, `ctl_permuted_net_misses` and the `ctl_near_miss_systematic_fails:*` controls (each known-error copy must read as failing a limit).

| Control | Guard | Strike |
|---|---|---|
| scripts equal T44 on fixed cells | 6 of 6 batches | 5 of 5 |
| scripted mixed cells play cleanly | 24 of 24 | 20 of 20 |
| oracle network equals the scripts game for game | 30 of 30 | 25 of 25 |
| permuted scripts miss (at least 15 cells) | 22 of 30 | 29 of 30 |
| unfitted network misses (at least 15) | 30 of 30 | 28 of 30 |
| permuted network misses (at least 15) | 24 of 30 | 29 of 30 |

## Results

Gate read: `results.json` / `results.md` of each LS1.2 folder. Games changed = b + c of 1,000; the pooled row is the mean difference (network less scripts, win share of the side) over the gated cells.

**Command error per skill** (network against script on the fixed cells; RMSE per channel x, y, z, yaw; `*` marks a failed limit; limits 0.05 on an active channel, 0.05 unused, 0.005 largest output of the zero-command skill):

| Side | Skill | RMSE x | RMSE y | RMSE z | RMSE yaw | Largest abs x, y |
|---|---|---|---|---|---|---|
| Guard | guard_parked_centre (zero-command) | 0.0094 | 0.0063 | 0.0001 | 0.0070 | 0.0351 *, 0.0345 * |
| Guard | guard_parked_ring | 0.0417 | 0.0369 | 0.0004 | 0.0072 | 0.2812, 0.3258 |
| Guard | guard_mark_edge | 0.0328 | 0.0329 | 0.0002 | 0.0023 | 0.3717, 0.3339 |
| Guard | guard_mirror | 0.0509 * | 0.0523 * | 0.0003 | 0.0041 | 0.8080, 0.5172 |
| Guard | guard_field | 0.0966 * | 0.0993 * | 0.0009 | 0.0065 | 1.5477, 1.4039 |
| Strike | strike_straight | 0.0225 | 0.0155 | 0.0046 | 0.0000 | 0.1242, 0.1129 |
| Strike | strike_flank | 0.3352 * | 0.3342 * | 0.0057 | 0.0000 | 1.5910, 1.5507 |
| Strike | strike_high | 0.0348 | 0.0315 | 0.0218 | 0.0000 | 0.1815, 0.2124 |
| Strike | strike_low | 0.0307 | 0.0277 | 0.0204 | 0.0000 | 0.2298, 0.2752 |
| Strike | strike_sacrifice | 0.2664 * | 0.2560 * | 0.0053 | 0.0000 | 1.7980, 1.8489 |
| Strike | strike_converge | 0.2030 * | 0.1902 * | 0.0079 | 0.0000 | 1.8980, 1.9989 |

Largest unused-channel |error|: Guard 0.0134 (fixed cells), Strike 0.0428; both under 0.05, and the zero-command rule applies to Guard's parked-centre skill only (Strike has none). (From `results.md`; the largest-abs-z/yaw columns are in `results.json`. Strike's yaw RMSE values are 0.9e-05 to 1.9e-05, all 0.0000 at four places.)

**Guard team** (verdict NOT DISTILLED; 18 failures: 1 zero-command, 4 command RMSE, 12 games changed, 1 cell margin):

| Kind | Limit | Failures |
|---|---|---|
| zero-command skill | 0.005 | `guard_parked_centre` largest |error| 0.0351 |
| command RMSE | 0.05 | mirror x 0.0509, y 0.0523; field x 0.0966, y 0.0993 |
| games changed | 30 | 12 cells: 11 against `strike_converge` (largest `guard_mark_edge+guard_mirror+guard_parked_centre` 64; 56 for `guard_parked_centre+guard_mirror+guard_mark_edge`; 54; 47; 39 ...; the fixed cell `guard_mirror` x3 31) and 1 against `strike_sacrifice` (fixed `guard_field` x3, 41 games, b = 8, c = 33) |
| cell margin | +-0.045 | 1 cell: fixed `guard_field` x3 @ `strike_sacrifice`, interval [+0.00147, +0.05056] |

10 of the 12 failing cells include `guard_mirror` and 10 include `guard_parked_centre` (computed for this record from the cell codes; most are mixed cells). Pooled: all -0.0024 [-0.0035, -0.0013] (inside +-0.01); fixed -0.0011 [-0.0028, +0.0007]; mixed -0.0027 [-0.0039, -0.0015]. The pooled limit does not fail on Guard.

**Strike team** (verdict NOT DISTILLED; 98 failures: 6 command RMSE, 64 games changed, 27 cell margin, 1 pooled margin):

| Kind | Limit | Failures |
|---|---|---|
| command RMSE | 0.05 | flank x 0.3352, y 0.3342; sacrifice x 0.2664, y 0.2560; converge x 0.2030, y 0.1902 |
| games changed | 30 | 64 cells (largest of all the mixed cell `strike_flank+strike_low+strike_flank` @ `guard_mirror` 130, b = 64, c = 66; largest fixed `strike_flank` x3 @ `guard_mirror` 122, @ `guard_parked_centre` 107 (b = 92, c = 15), @ `guard_parked_ring` 92; fixed `strike_sacrifice` x3 @ `guard_parked_centre` 97) |
| cell margin | +-0.045 | 27 cells (e.g. fixed `strike_flank` x3 @ `guard_parked_centre` [-0.1122, -0.0412]; @ `guard_parked_ring` [-0.0851, -0.0185]) |
| pooled margin | +-0.01 | pooled interval [-0.01113, -0.00661] not inside +-0.01 |

Pooled (the pooled row): all -0.0089 [-0.0111, -0.0066] (fails); fixed -0.0052 [-0.0081, -0.0024]; mixed -0.0100 [-0.0124, -0.0075]. 78 of the 91 cell-level failures (games changed and cell margin) involve `strike_flank` in the cell's codes (computed for this record from `results.md`; 52 of the 64 failing cells). By opponent the games-changed failures are spread over all five Guard opponents with `guard_mirror` 18, `guard_mark_edge` 16, `guard_parked_centre` 14, `guard_parked_ring` 14 and `guard_field` 2 (computed). Of the 64 games-changed cells, 14 are fixed cells (all three drones on one skill).

INFO cells (not gated, network arm only): 26 Strike cells against `guard_mark_inside` (`results.md`, arm `info`). Counted for this record from `results.json`: games changed 8 to 93, 16 of the 26 over 30 (12 of them with `strike_flank` in the codes; 13 of the 26 hold it), 4 with an interval outside +-0.045 (`strike_converge` x3, 71 games, [-0.0619, +0.0015]; `strike_flank+strike_low+strike_flank`, 83, [-0.0544, +0.0118]; two flank mixes at 62 and 65 games); mean difference -0.0069. They change no verdict; they show the same flank and converge picture against a Guard script that has no cell in T44's base variant (`cells.toml` `[info_opponents]`).

LS1.1 fit (`fit_report.json`): last-epoch loss by round, Guard 0.00871, 0.00687, 0.00580, 0.00464; Strike 0.02878, 0.03053, 0.02977, 0.02272. Net RMSE against the scripts on the data of the round before the refit (`prev_net_rmse`): Guard 0.0955, 0.0783, 0.0639; Strike 0.1861, 0.1747, 0.1721. Kept rows 2,000,000 per round; absent-mate share 0.226 to 0.229 (Guard) and 0.226 to 0.238 (Strike).

## Verdict

**NOT DISTILLED on both sides**, as the gate read it (`results.json` `verdict`; the last line of each `job.log`; exit 0). Both reads are of record (`of_record` true, `complete` true) and every control PASS, so the verdict stands. Guard fails narrowly on mirror (0.051 and 0.052 against 0.05), by about twice the limit on field (0.097, 0.099) and by about 7 times on the zero-command skill (0.035 against 0.005); Strike fails on its three hard skills (flank, sacrifice, converge) by about 4 to 7 times the command limit.

## Stop rule that now applies

`distil_gates.toml` `[stop]` (R47): "NOT DISTILLED: no limit is moved. One announced fix round is allowed. If it still fails, LS1 stops and the record says which skills do not copy and why." The one fix round may change only the data mix (`[data]`), the relabelling rounds (`[dagger]`), the network size (`[net] hidden`) and `[net] zeroed_inputs`; it cannot add network inputs (R47: added inputs are a named later build). Head training (LS1.4) starts only after DISTILLED on both sides. So: no limit is moved; the fix round is owner-announced and not yet run.

## Videos

2-D clips (LS1.1, `clips` in `distil_gates.toml`; 4 codes per side, scripts v network, game 0, speed 8, 10 fps), in `~/AirStack-starling-max2-dev/svg_training/runs/`:

- Guard: `2026-11-26_ste_ls11_distil_guard/videos/guard_guard_{parked_ring,field,mark_edge,mirror}_g0_{net,scripts}.gif`
- Strike: `2026-11-26_ste_ls11_distil_strike/videos/strike_strike_{sacrifice,converge,flank,straight}_g0_{net,scripts}.gif`

8 clips per side (4 per arm). No 3-D clips; no LS1.2 clips.

## Links

- Near-miss known-answer check (the lead's scratch evaluation, reported in chat; the diagnosis scratch files are saved in `records/evidence/2026-11-26_ste_ls1_fix_diagnosis/`): not a run of record, not read here; its numbers are not used in this record.
- `ste_learning/drafts/LS1_FIX_ROUND_PROPOSAL.md` (the analyst's diagnosis and the proposed fix round; reviewed with this record, not yet in git at the time of writing; not read for the numbers above).

## What this does not show

- Why the copy is poor beyond the failure list: the diagnosis is in the proposal, not here.
- Flight, tier 2, or any play other than T44's 1,000 starts per cell, one seed per network.
- Whether another fit would pass; the one allowed fix round has not run.

## Evidence

Run folders (not in git), `~/AirStack-starling-max2-dev/svg_training/runs/`: `2026-11-26_ste_ls11_distil_{guard,strike}/` (`fit_report.json`, `controls.json`, `skill_net_*.pt`, `data/round_{0..3}.pt`, `videos/`, `cmd.txt`, `launches.jsonl`, `job.json`, `code.json`, `gates.toml`, `gates.sha256`, `job.log`) and `2026-11-26_ste_ls12_read_{guard,strike}/` (`results.json`, `results.md`, `controls.json`, `layout.json`, `games/*.npz`, same job files). sha256 of the summary files (computed for this record):

| File | Guard | Strike |
|---|---|---|
| LS1.1 `fit_report.json` | `25fa06fbb447f5b644e0e817860d4a661823836714a18816b38e5e875fc2a798` | `f103cdc2a5d4cd6496848d3b3834a0e8c974b09ea395adcba82904fdf6b3fecc` |
| LS1.1 `controls.json` | `e519d3cef929bcafe90ad0873a837c09f1cb1e9da4cccb0a51b1be322e1805d5` | same |
| LS1.2 `results.json` | `25cb18884f10dcca3e56ef2493e9c1979218a65f1de6746591995bd0f56848a9` | `adf4c340d1d03cfc37ca2644ee69ded45be75aeeea2b57229ba9c14863392e10` |
| LS1.2 `controls.json` | `85417bdbf4e8ab95060551b2e993626a3e1d302893cc45187587893ac510e1bd` | `90391e8793f95cee2560aad9658842f13517421144f44cd4b787b1f52bc261b6` |

No evidence copies under `records/evidence/` yet: the hashes above can be checked only against the run folders, which are not in git (all of them matched `sha256sum` of the files on disk, re-run at review). Copying `results.json` and `fit_report.json` of each side to `records/evidence/` is left to the lead.

## Ledger rows (T93, T94)

| # | Date | Simulator | Run | What | Result | Record |
|---|---|---|---|---|---|---|
| T93 | 2026-11-26T10:01:50+08:00 | training simulator, tier 1; GPU | 2026-11-26_ste_ls11_distil_{guard,strike} | STE LS1.1 distillation: one skill network per team fitted to copy the 11 scripts, 4 relabelling rounds of 2,000,000 rows, 40 epochs, hidden 256x3, zeroed inputs 6, 7, 10, 11; gate file `distil_gates.toml` sha `5cce1245`; label control PASS (0 rows differ); networks sha256 `0ba9fc76…` (Guard), `699011e2…` (Strike); 8 2-D clips per side; code `a57d1e69`; exit 0; 0.168 GPU-h as the union of the two jobs (Strike's interval covers Guard's; summed per job 0.326: 0.158 Guard, 0.168 Strike); LS1.1 in all 0.172 with the T92 probe | INFO (fit; read by T94) | `records/2026-11-26_ste_ls1_distil_read_record.md` |
| T94 | 2026-11-26T10:55:27+08:00 | training simulator, tier 1; CPU | 2026-11-26_ste_ls12_read_{guard,strike} | STE LS1.2 copy check of the LS1.1 networks against the scripts, 1,000 games per cell on T44's starts: every control PASS (119 Guard, 117 Strike); Guard 18 limit failures (zero-command error 0.035 v 0.005; mirror RMSE 0.051-0.052, field 0.097-0.099 v 0.05; 12 cells over 30 games changed, 1 over the cell margin); Strike 98 (flank 0.33, sacrifice 0.26, converge 0.20 RMSE; 64 cells over 30 games, 27 over the cell margin, pooled row [-0.0111, -0.0066] v +-0.01); code `e353d88d` with a working-tree diff; 0 GPU-h | NOT DISTILLED (Guard and Strike); one announced fix round allowed (R47) | `records/2026-11-26_ste_ls1_distil_read_record.md` |
