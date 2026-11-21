Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator; not a flight result.

# 2026-11-22_ste_l012d_cross_tag record

## Purpose

STE task L0.12d Cross-tag check (INFO; spec ste_learning/drafts/L0_12d_CROSS_TAG_SPEC.md, written by the lead before any scoring): how well do the strategies trained at tag 1.6 m (T46, base variant) play when the tag is 1.15 m (the safety filter's 1.10 m keep-out + 0.05 m)? Scoring only, no training, on T44's 1,000 scoring starts. Feeds G0 row 1 (tag distance). X4 (guard_field at 1.6 m) separates the opponent from the tag: with C2, X2 and X3 it completes tag x opponent.

## Commit

`d20f18a4236e0bfa625d8665238ff21c771bad14` (diff sha256 e3b0c44298fc)

## Config

- Settings `configs/ste_l012d/cross_tag.toml`, sha256 `a296bf587b93a2656930f56d792f6570d44c6459d6e412bcf5b7906a5798bdbc` (copy in the run folder).
- T46 runs (read only, `/home/jeremychia/AirStack-starling-max2-l12/svg_training/runs`): Guard `2026-11-21_ste_l012_base_guard` (agent_final.pt `e981ac7e7045db4e2edc183087329667a6ab9f8b56ce3c19f65e98a8c077d22a`), Strike `2026-11-21_ste_l012_base_strike` (agent_final.pt `3c264ddd9face8e4f7622a6004b6573b280c85295eae6f5c2fd59894539ee187`); their gate file `6e2e606053a593185480f8671c406625dc844002395801023005945f58cfbc5b`.
- Games: controls C1, C2 `configs/ste_l011/base.toml` (`96e0e7f61a49999da54eee81a544bf64c519cd80833f0dcdfa2a07edfc10cc4d`); cross-tag cells X1–X3 and C3 `configs/ste_l011/tag_1p15.toml` (`b2e09683f7088964a7d1ca15dfc9c98d1e04c15e96b14196d6971afb75f27580`); X4 and C4 `configs/ste_l011/base.toml` (`96e0e7f61a49999da54eee81a544bf64c519cd80833f0dcdfa2a07edfc10cc4d`).
- L0.12b gate file `configs/ste_l012b/gates.toml` (`ace5e18d77c214ca0a3e31d3613a20c3291e0f873ff6d1c5b90b8fec246fb592`); references `configs/ste_l012/t44_reference.npz` (`4bc5e011071adced368b2a0025fc47499839e0bbc8d8d650207bd12c3da0f8b5`) and `configs/ste_l012b/screen_reference.npz` (`49014000d07e8b52ae579deb325dad53d98c5020f533026dfbff778f306b2296`), one start set `5aeba7ab2b582f2973034c8203c17ed3e8239fef7029a1f991fe95b82369843c`.
- Trained players held 12 ticks (0.6 s) as trained, mean actions; 1,000 games per cell; 2400 ticks (the game length).

## Model parameter set

Tier 1 Starling layer: `params/real_exploratory_v0.toml` (fitted PX4 response, exploratory), sha256 `4c93543f51ab41ea5bb0f81e6d1b0512f662a3e10126ec2d85fc3bb008cecaa2`; safety filter on every pair, 1000 sweeps, check every 8.

## Seeds

Scoring starts T44's (seed 110000, loaded); scripted players seed + 101 (Guard) / + 202 (Strike); one training seed per side (T46's); no training here. Clips: the clip seed's own starts (clip_seed 120950), CPU, not the 1,000 scoring starts.

## Machine

jeremychia-Legion-Pro-7-16IAX10H, NVIDIA GeForce RTX 5070 Ti Laptop GPU, torch 2.7.0+cu128, device cuda; exit 0 (DONE); effective 386 s of 0.2 h; job l012d_cross_tag (task L0.12), asked 0.2 GPU-h, used 0.119 GPU-h (shared ledger)

## Games at once and steps per second

C1 batch 4.8 s; C2 batch 137.1 s; C4 batch 74.1 s; C3 batch 170.1 s (tier 1, 6 drones per game).

## Gates

Verdict: **INFO** (no pass/fail gate; the controls are gated: any control not PASS and no cross-tag number is reported).

| Control | What | Status |
|---|---|---|
| C1 | T46's base Guard evaluation batch replayed whole (base game): equal to its eval_final.npz game for game, trained Guard holds as recorded | **PASS** |
| C2 | T46's base Strike evaluation batch replayed whole (base game): equal to its eval_final.npz game for game, trained Strike reaches as recorded | **PASS** |
| C3 | every script cell of the 1.15 m batch equal to the L0.12b screen reference game for game, g* v s* holds as the screen | **PASS** |
| C4 | every script cell of X4's own base-game batch equal to T44's reference game for game, guard_field v strike_straight holds as T44 (716) | **PASS** |

Closest-approach tolerance 1e-06 m (0 on the CPU; same_seed_closest_tol_m on CUDA; `configs/ste_l011/gates.toml`, sha256 `8bfbc2cb8f1d6551fb3060bc750c24f9b2220ebafb19fcd44e9e3baa1c24e5d4`).

| Cell | What | Trained side's wins (Wilson 95 %) | Script cell, same starts | Paired: trained only / script only | Trained at 1.15 m | Guards left in holds | Length median (s) | Pushed together (share) | Filter active (share) |
|---|---|---|---|---|---|---|---|---|---|
| X1 | T46 base trained Guard team v s* at 1.15 m; game tag_1p15 | 195 of 1,000 (0.172–0.221) | guard_field v strike_straight: 645 of 1,000 (0.615–0.674) | 0 / 450 | 572 of 1,000 (0.541–0.602) | 0.000 | 2.90 | 0 (0.000) | 1892 (1.000) |
| X2 | g* at 1.15 m v T46 base trained Strike team; game tag_1p15 | 121 of 1,000 (0.102–0.143) | guard_field v strike_straight: 355 of 1,000 (0.326–0.385) | 0 / 234 | 134 of 1,000 (0.114–0.157) | 0.403 | 16.33 | 123 (0.051) | 1660 (0.683) |
| X3 | the base g* (the opponent it trained against) v T46 base trained Strike team (INFO); game tag_1p15 | 931 of 1,000 (0.914–0.945) | - | - / - | - | 0.406 | 8.95 | 32 (0.030) | 1000 (0.945) |
| X4 | guard_field v T46 base trained Strike team in the base game (tag 1.6 m); the T46 Strike team never trained against guard_field (INFO); game base | 85 of 1,000 (0.069–0.104) | guard_field v strike_straight: 284 of 1,000 (0.257–0.313) | 1 / 200 | - | 0.106 | 4.70 | 205 (0.074) | 261 (0.094) |

Trained at 1.15 m: T54 / T55 (L0.12c, trained at 1.15 m; evaluated on the same 1,000 starts).

## Figures and videos

Clips: the clip seed's own starts (clip_seed 120950), CPU, not the 1,000 scoring starts.

- X1: clips/X1/videos/tag_1p15_guard_game0_reach.gif: game 0, reach at 2.9 s (0.06 MB)
- X1: clips/X1/videos/tag_1p15_guard_game5_hold.gif: game 5, hold at 2.8 s (0.05 MB)
- X2: clips/X2/videos/tag_1p15_strike_game2_reach.gif: game 2, reach at 4.9 s (0.10 MB)
- X2: clips/X2/videos/tag_1p15_strike_game0_hold.gif: game 0, hold at 20.5 s (0.22 MB)

## Reading

- X1 (T46 base trained Guard team v s* at 1.15 m): 1.6 m strategy at 1.15 m: 195 of 1,000 (0.172–0.221) against the 1.15 m-trained team's 572 and the script's 645.
- X2 (g* at 1.15 m v T46 base trained Strike team): 1.6 m strategy at 1.15 m: 121 of 1,000 (0.102–0.143) against the 1.15 m-trained team's 134 and the script's 355.
- X3 (the base g* (the opponent it trained against) v T46 base trained Strike team (INFO)): 1.6 m strategy at 1.15 m: 931 of 1,000 (0.914–0.945) against guard_mark_edge, the opponent it trained against (INFO).
- X4 (guard_field v T46 base trained Strike team in the base game (tag 1.6 m); the T46 Strike team never trained against guard_field (INFO)): 1.6 m strategy at 1.6 m against guard_field, an opponent the T46 Strike team never trained against: 85 of 1,000 (0.069–0.104) against the script's 284 (INFO).
- One seed per side, one opponent, one start set; observed in the training simulator.

## Ledger row

Ledger row: | T56 | 2026-11-22T06:01:02+08:00 | training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED); NVIDIA GeForce RTX 5070 Ti Laptop GPU | 2026-11-22_ste_l012d_cross_tag | STE L0.12d Cross-tag check (1.6 m-trained T46 base players at tag 1.15 m; X4 = guard_field at 1.6 m): X1 195/1000 (1.15 m-trained 572, script 645); X2 121/1000 (1.15 m-trained 134, script 355); X3 931/1000; X4 85/1000 (script 284); controls C1–C4 PASS; 0.119 GPU-h | INFO | records/2026-11-22_ste_l012d_cross_tag_record.md |

## Run notes added by the lead

- **In short.** T46's 1.6 m-trained Strike team, reaches of 1,000 (one seed, one start set; trained against one
  opponent only):

  | Opponent | Tag 1.6 m | Tag 1.15 m |
  |---|---|---|
  | guard_mark_edge (its training opponent) | 636 (T46, C2) | 931 (X3) |
  | guard_field | 85 (X4; script 284) | 121 (X2; 1.15 m-trained T55 134; script 355) |

- **Strike side:** the opponent moves the Strike team's score far more than the tag does (one seed): against mark_edge the same network goes 636 → 931 when only the tag changes; part of that may come through the opponent itself (mark_edge holds 808 → 422 against straight Strikes). T46 and T55 changed the tag and the opponent together, so
  the earlier reading "the Strike team learns at 1.6 m but not at 1.15 m" is not supported. X3 does not show that 1.15 m
  is learnable either: mark_edge is weak at 1.15 m (the straight-Strike script also reaches 578 against it, C3).
- **Guard side: the earlier reading stands.** Same opponent (strike_straight) at both tags: trained 913 v script 808 at
  1.6 m, 572 v 645 at 1.15 m (one seed; budgets 1× and 3×). X1: the 1.6 m-trained Guard team at 1.15 m holds 195
  (1.15 m-trained 572, script 645, untrained 101): the Guard strategy does not carry over to 1.15 m. The Strike team
  against field Guards is level within the intervals (121, 0.102–0.143, v T55's 134, 0.114–0.157).
- **Paired games.** In X1, X2 and X4 the trained team wins 0, 0 and 1 games that the script loses: it wins only starts
  the script also wins (all but one game).
- **Limits.** Each trained team is overfit to one opponent by design; X3 and C2 use that opponent. The screen's "best
  script" was chosen against other scripts only. Between the tags mark_edge falls 808 → 422 holds, field 716 → 645.
  X2 matches T55 in wins only: median game 16.3 s and 0.40 Guards left in holds, against T55's 120 s and 1.0. Do not
  read it as "5× training added nothing".
- **Clips:** [docs/media/ste_l012d](../docs/media/ste_l012d/README.md) (clip seed's own starts, CPU; training
  simulator, not a flight).
- **Wording notes.** In C3's detail, "T44" names the L0.12b screen reference (T50); the label is hard-coded in
  `source/svg_training/ste/exploit.py:614`. The "Pushed together" and "Filter active" columns count tags; their
  denominators are X1 1,892, X2 2,432, X3 1,058 and X4 2,787 tags.
- **GPU-hours** (shared ledger): 0.119, charged to L0.12.
