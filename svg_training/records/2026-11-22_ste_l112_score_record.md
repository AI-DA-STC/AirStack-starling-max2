Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator; not a flight result.

# 2026-11-22_ste_l112_score record

Written by hand from the run folder's `results.json` / `results.md` (no record writer covers `scripts/ste_score_matrix.py`
runs); the tables are copied from `results.md`.

## Purpose

STE task L1.12 (INFO; spec `ste_learning/drafts/L1_SIDE_TRACK_SPEC.md` v2, question Q3, written before any run): T46's
1.6 m-trained Guard team was scored against strike_straight only (913 of 1,000). Here it plays every one of the 6 Strike
scripts in the base game (tag 1.6 m, 120 s clock), scoring only, on T44's 1,000 scoring starts, against the best Guard
script's holds on the same starts (T44's cells, replayed), worst cell first.

## Commit

`c4fc15bdabdadbefa53fd7fb6c655ba5b23de439` with uncommitted changes (diff sha256 `4f61e05b04c5`; not the empty diff
`e3b0c44298fc`). The scoring tool `scripts/ste_score_matrix.py` was then a new file, not yet in git (the recorded diff
covers tracked files only); it was committed in `37e87e0e` at 19:03 the same day, after two code reviews and their fixes.
The code that ran is not shown identical to any commit: the recorded diff hash matches no commit from `37e87e0e`
to `531dccc7` (checked over every subset of the tracked files those commits change), and the untracked files are not
covered by it. The settings file it read is pinned by sha256 (below) and equals the committed file.

## Config

- Settings `configs/ste_l1/score_matrix_l112.toml`, sha256 `d1bb402c43f65a2c37da20fc520786059bf10106460ccb5b4064e0401ffb0f84` (copy in the run folder).
- Player: T46's base Guard team, `ste_provisional/players/2026-11-21_ste_l012_base_guard` (agent_final.pt `e981ac7e7045db4e2edc183087329667a6ab9f8b56ce3c19f65e98a8c077d22a`; eval_final.npz `80171ad73c6f251d5ab900b3117a41a865baba30695445f6a62a5d8eb9328961`); its gate file `6e2e606053a593185480f8671c406625dc844002395801023005945f58cfbc5b`; trained on the base game against strike_straight (the maximin pick).
- Game `configs/ste_l011/base.toml` (`96e0e7f61a49999da54eee81a544bf64c519cd80833f0dcdfa2a07edfc10cc4d`): tag 1.6 m, 120 s clock (2,400 ticks).
- Reference `configs/ste_l012/t44_reference.npz` (`4bc5e011071adced368b2a0025fc47499839e0bbc8d8d650207bd12c3da0f8b5`); one start set `5aeba7ab2b582f2973034c8203c17ed3e8239fef7029a1f991fe95b82369843c`.
- Trained players held 12 ticks (0.6 s) as trained, mean actions; 1,000 games per cell.

Command (`runs/2026-11-22_ste_l112_score/cmd.txt`, launch 1 of job l112_score):

```
scripts/ste_job.py launch --task L1.12 --name l112_score --run-dir runs/2026-11-22_ste_l112_score --min-s 60.0 --gpu-h 0.1 \
  --settings configs/ste_learning.toml --beat-s 60.0 -- python scripts/ste_score_matrix.py \
  --settings configs/ste_l1/score_matrix_l112.toml --run-dir runs/2026-11-22_ste_l112_score --cap-h 0.1
```

## Model parameter set

Tier 1 Starling layer: `params/real_exploratory_v0.toml` (fitted PX4 response, exploratory; `delay_s` 0.1482 from command
to motion), sha256 `4c93543f51ab41ea5bb0f81e6d1b0512f662a3e10126ec2d85fc3bb008cecaa2`; safety filter on every pair.

## Seeds

Scoring starts T44's (seed 110000, loaded); no training here; no clips (scoring only).

## Machine

jeremychia-Legion-Pro-7-16IAX10H, NVIDIA GeForce RTX 5070 Ti Laptop GPU, torch 2.7.0+cu128, device cuda; one launch
2026-11-22T18:01:01+08:00, exit 0 (DONE); effective 64 s of 0.1 h; job l112_score (task L1.12), asked 0.1 GPU-h, used
0.019 GPU-h (shared ledger). One job on the GPU at a time (no launch overlaps another L1 job); wall time 67 s against
effective 64 s, so no suspend or pause.

## Gates

Verdict: **INFO** (no pass/fail gate; the controls are gated: any control not PASS and no number is reported).

| Control | What | Status |
|---|---|---|
| own_replay | T46's Guard evaluation batch replayed whole: equal to its eval_final.npz game for game (7,000 games; outcome, end step, tags, Strikes left, starts, closest approach), trained holds 913 (record 913) | **PASS** |
| scripts_base_120s__strike_* (6) | for each Strike script, every Guard script cell equal to T44's reference game for game (0 of 1,000 games differ in every cell) | **PASS** (all 6) |

Plumbing checks inside each control (paired starts, tags one for one, no non-finite actions): PASS. Closest-approach
tolerance 1e-06 m (`configs/ste_l011/gates.toml`, sha256 `8bfbc2cb8f1d6551fb3060bc750c24f9b2220ebafb19fcd44e9e3baa1c24e5d4`).

## Results

Copied from `results.md`; tag 1.6 m, 120 s clock; one trained network, one start set; worst cell first.

| Opponent | Player's holds (Wilson 95 %) | Best script, same starts | Paired: player only / script only / both / neither | Player's games: reach / all Strike tagged / clock / other hold / unfinished | Median length (s) |
|---|---|---|---|---|---|
| strike_straight | 913/1000 (0.894-0.929) | guard_mark_edge 808/1000 (0.782-0.831) | 155 / 50 / 758 / 37 | 87 / 913 / 0 / 0 / 0 | 2.5 |
| strike_converge | 913/1000 (0.894-0.929) | guard_parked_centre 986/1000 (0.977-0.992) | 8 / 81 / 905 / 6 | 87 / 913 / 0 / 0 / 0 | 7.8 |
| strike_sacrifice | 922/1000 (0.904-0.937) | guard_mark_edge 960/1000 (0.946-0.970) | 34 / 72 / 888 / 6 | 78 / 922 / 0 / 0 / 0 | 3.8 |
| strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 923/1000 (0.905-0.938) | guard_mirror 847/1000 (0.823-0.868) | 146 / 70 / 777 / 7 | 77 / 923 / 0 / 0 / 0 | 3.2 |
| strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 931/1000 (0.914-0.945) | guard_mark_edge 850/1000 (0.827-0.871) | 145 / 64 / 786 / 5 | 69 / 931 / 0 / 0 / 0 | 3.0 |
| strike_flank | 953/1000 (0.938-0.964) | guard_mark_edge 887/1000 (0.866-0.905) | 105 / 39 / 848 / 8 | 47 / 953 / 0 / 0 / 0 | 3.0 |

## Figures and videos

None in this run: scoring only. T46's own clips are in its record.

## Ledger row

Ledger row: | T57 | 2026-11-22T18:01:01+08:00 | training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED); NVIDIA GeForce RTX 5070 Ti Laptop GPU | 2026-11-22_ste_l112_score | STE L1.12 T46's 1.6 m-trained Guard team v all 6 Strike scripts (tag 1.6 m, scoring only): holds 913–953 of 1,000, worst 913 (straight, converge); above the best Guard script v straight (913 v 808), flank (953 v 887), low (923 v 847), high (931 v 850); below v converge (913 v 986), sacrifice (922 v 960); controls PASS; 0.019 GPU-h | INFO | records/2026-11-22_ste_l112_score_record.md |

## Run notes added by the lead

- **Reading (pre-registered words; one trained network, one start set; two reviewers).** Every cell's interval is clear
  of the best Guard script's on the same starts. Worst cell first:
  - The 1.6 m-trained Guard team holds 913 of 1,000 against strike_straight (best Guard script 808).
  - The 1.6 m-trained Guard team holds 913 of 1,000 against strike_converge (best Guard script 986).
  - The 1.6 m-trained Guard team holds 922 of 1,000 against strike_sacrifice (best Guard script 960).
  - The 1.6 m-trained Guard team holds 923 of 1,000 against strike_low (best Guard script 847).
  - The 1.6 m-trained Guard team holds 931 of 1,000 against strike_high (best Guard script 850).
  - The 1.6 m-trained Guard team holds 953 of 1,000 against strike_flank (best Guard script 887).
- **Worst cells.** The trained team's worst cell is 913, shared by straight and converge by coincidence: the two cells
  differ in 158 of 1,000 games. The best Guard script's worst cell is mark_edge's 808 (against straight).
- **Above the best script:** against straight, its training opponent (913 v 808; paired 155 v 50), and flank (953 v 887;
  105 v 39). Also against low (923 v 847; 146 v 70) and high (931 v 850; 145 v 64), but those two Strike scripts carry
  the z_up_info label: tier 1's vertical response is not fitted, so climbs and descents are not the drone's.
- **Below the best script:** converge (913 v 986; paired 8 v 81) and sacrifice (922 v 960; 34 v 72).
- **Code.** The scoring ran on code not yet committed (field "Commit" above); every control PASS, including the replay of
  T46's own 7,000 evaluation games game for game.
- **Limits.** Tier 1 with the fitted Starling response (`delay_s` 0.1482 command-to-motion), laptop RTX 5070 Ti, one
  training seed, T44's 1,000 starts; observed in the training simulator, nothing flown.
- **GPU-hours** (shared ledger, job l112_score): 0.019, charged to L1.12.
