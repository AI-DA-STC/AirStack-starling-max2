Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator; not a flight result.

# 2026-11-22_ste_l012c_tag_1p15_guard record

## Run notes

- **Never suspend the machine during a GPU job** (no closed lid, no sleep): the cap clock and the GPU-hour ledger are wall clock less the owner's gpu_pause.sh pauses only (tooling task L07-SUSPEND). Say here whether the machine was suspended during the runs.
- **Asymmetries stated before the runs** (gate file header): one training seed per side; the learner decides every 0.6 s while the scripts decide every 0.05 s (finding L011-F1); one network per drone; about 1 GPU-h per run. A gain is evidence; no gain is weak evidence.
- **Decision-boundary restart** (LEAD CALL 21 Nov 2026): a game that ends inside a 0.6 s decision restarts at the next decision boundary; the ticks after its end are played, counted (stale-tick share) and never trained on (T41's hold let the new game play the old held action).
- **Strike recipe** (LEAD CALL 21 Nov 2026, pre-registered in [trainer] strike_fallback): the T41 recipe if its pilot probe against g* shows at least one reach; else the shaped Strike recipe (the game's distance shaping 1.0, training reward only), also when neither probe shows a reach (LEAD CALL 21 Nov 2026, QC N-1: 3-update probes no longer stop the Strike runs). The parked-Guard probes are information only. The recipe of each run is in the tables below.
- **Run 0, the learner positive control** (LEAD CALL 21 Nov 2026, QC N-1; gate [run0]): the Strike recipe trained against the parked Guard at the budget and cap of a run of record, read at pre-listed checkpoints (reach rate at least scripted strike_straight's on the same starts minus 0.05). Strike runs need run 0 = PASS; if it reads FAIL the Strike runs are not launched and the Strike side is INCONCLUSIVE (the trainer did not learn the easy Strike task at the run budget). Guard runs do not depend on it.
- **Hours** (LEAD CALL 21 Nov 2026, QC N-3): nothing kills a run at --gpu-h during its final phase; the GPU-hours below are the ledger's real hours.
- **Resume** (by design): networks, optimisers, scalers, counters and the torch random state are restored at the last update boundary, but the training games restart from the run seed's first starts (the game generator is not checkpointed), so a resumed run is not identical to an uninterrupted run. Each run's job launches say whether it was resumed.

## Purpose

STE task L0.12c: L0.12's best-response method on the variant(s) tag_1p15: an exploiter Strike team trained against the best scripted Guard g* and an exploiter Guard team trained against the best scripted Strike s*, g* and s* and the script baselines from the L0.12b scripted screen (configs/ste_l012b/screen_gates.toml) (on T44's own starts); the gain of each over the best script, the category on the better of script and exploiter, and the unchosen-tag shares (INFO).

## Config

- Gate file sha256 `b52dcc23580640c7a9d5a99f95e523eaa9c21b00125e3ff56172f6a5210d4c81` (copy in each run folder: `gates.toml`).
- Band 0.2 (PROPOSED by the lead).
- Reference `configs/ste_l012b/screen_reference.npz`, sha256 `49014000d07e8b52ae579deb325dad53d98c5020f533026dfbff778f306b2296`; T44's starts sha256 `5aeba7ab2b582f2973034c8203c17ed3e8239fef7029a1f991fe95b82369843c`; the L0.12b scripted screen (configs/ste_l012b/screen_gates.toml) gate sha256 `881375f054a78ae33c7fd330e271a4e3b27a0a1cf3d58eca4b893cdca8ce2479`.
- Game `configs/ste_l011/tag_1p15.toml`, sha256 `b2e09683f7088964a7d1ca15dfc9c98d1e04c15e96b14196d6971afb75f27580`.
- tag_1p15 guard: trainer settings {'algorithm': 'IPPO', 'decision_ticks': 12, 'num_games': 16384, 'game_steps_per_run': 1650000000, 'rollouts': 32, 'learning_epochs': 5, 'mini_batches': 4, 'learning_rate': 0.0003, 'hidden': [128, 128], 'init_log_std': -1.6, 'frozen_log_std_axes': ['yaw'], 'zero_mean_init': True, 'discount_factor': 0.99, 'gae_lambda': 0.95, 'entropy_loss_scale': 0.0, 'value_loss_scale': 2.5, 'ratio_clip': 0.2, 'value_clip': 0.2, 'grad_norm_clip': 0.5, 'shaping_weight': 0.0, 'strike_fallback': {'shaping_weight': 1.0}, 'strike_fallback_label': 'shaped Strike recipe', 'checkpoint_every_updates': 1, 'curve_every_updates': 10, 'final_reserve_s': 600, 'final_reserve_factor': 2.0, 'clip_reserve_s': 120}

## Model parameter set

Tier 1 Starling layer: `params/real_exploratory_v0.toml` (fitted PX4 response, exploratory), sha256 `4c93543f51ab41ea5bb0f81e6d1b0512f662a3e10126ec2d85fc3bb008cecaa2`; safety filter on every pair, 1000 sweeps, check every 8.

## Commit

- tag_1p15 guard: `c4a2c2cb4477cdb78f1b754d36288be965819d13` (diff sha256 e3b0c44298fc)

## Seeds

- tag_1p15 guard: training seed 120412; scoring starts T44's (seed 110000, loaded)

## Machine

- tag_1p15 guard: jeremychia-Legion-Pro-7-16IAX10H, NVIDIA GeForce RTX 5070 Ti Laptop GPU, torch 2.7.0+cu128; exit 0 (DONE); effective 5513 s of 2.7 h; job l012c_tag_1p15_guard (task L0.12), asked 2.7 GPU-h, used 1.533 GPU-h (shared ledger)

## Games at once and steps per second

- tag_1p15 guard: 16384 training games, 6 drones per game, tier 1, NVIDIA GeForce RTX 5070 Ti Laptop GPU: median 306,016 game-steps/s; 263 updates, 1,654,652,928 game-steps (budget: 1,654,652,928 of 1,650,000,000 game-steps); evaluation 1000 games per cell

## Gates

Verdict: **INFO (every control PASS; the categories feed gate G0)**.

| Variant | Role | Strike side | Guard side | Better Strike reach upper | Better Guard hold upper | Category |
|---|---|---|---|---|---|---|
| tag_1p15 | owner variant (bubble tag) | - | weak (learned, below the script) | - | - | **incomplete: one side only** |

| Variant | Side | Recipe | Trained exploiter | Untrained | Best script (cell) | Gain | Real | Paired (exploiter only / script only) | Guards left in holds (exploiter) | Length median (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| tag_1p15 | guard | T41 recipe | 572/1000 = 0.572 (0.541–0.602) | 101/1000 = 0.101 (0.084–0.121) | 645/1000 = 0.645 (0.615–0.674) (guard_field v strike_straight) | -0.073 | False | 45 / 118 | 0.000 | 2.90 |

Unchosen tags of the trained exploiter (INFO; pushed together = on the tag's tick the safety filter's correction closed the pair faster than the players' commands; filter active = the filter corrected either drone of the pair on that tick, an upper bound; at the filter edge = pair distance at most the filter distance plus the gate's margin, 1.11 m):

| Variant | Side | Cell | Tags | Pushed together (share) | Filter active (share) | At the edge (share) |
|---|---|---|---|---|---|---|
| tag_1p15 | guard | exploiter v strike_straight | 2379 | 0 (0.000) | 2375 (0.998) | 0 (0.000) |

## Figures and videos

- tag_1p15 guard: videos/tag_1p15_guard_game0_reach.gif: game 0, reach at 2.9 s (0.06 MB)
- tag_1p15 guard: videos/tag_1p15_guard_game2_hold.gif: game 2, hold at 2.6 s (0.05 MB)

## Reading

(The lead writes the reading after QC; numbers come from the tables above.)

## Ledger row

Ledger row: | T54 | 2026-11-21T23:41:37+08:00 | training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED); NVIDIA GeForce RTX 5070 Ti Laptop GPU | 2026-11-22_ste_l012c_tag_1p15_guard | STE L0.12c Best-response test: tag_1p15 Guard: weak (learned, below the script), gain -0.073, Guards left 0.000, 2.90 s median (category incomplete: one side only, set by the L0.12b scripted screen (configs/ste_l012b/screen_gates.toml)'s scripts); 1.533 GPU-h | INFO | records/2026-11-22_ste_l012c_tag_1p15_guard_record.md |


## Run notes added by the lead

- **(a) What this run is.** L0.12c (owner approval 21 Nov 2026): the trained Guard team at tag 1.15 m (the safety
  filter's 1.10 m keep-out + 0.05 m) with 3× the step budget of [record T51](2026-11-21_ste_l012b_best_response_record.md)
  (1.65 B game-steps), same recipe, a new training seed (120412). Gate file `configs/ste_l012c/guard_gates.toml`,
  written and QC'd twice before the run. Not suspended; one job at a time on the GPU.
- **(b) Figure and clips.** Learning curves at 1× and 3× with the final 1,000-game results:
  [longer_runs.png](../docs/figures/ste_l012c/longer_runs.png) (`scripts/make_ste_l012c_figure.py`; the curve reads in
  [curve_reads.csv](../docs/figures/ste_l012c/curve_reads.csv)). 2-D clips: [docs/media/ste_l012c](../docs/media/ste_l012c/README.md).
- **(c) Reading (lead; one seed, one opponent, one start set).** More training helped the Guard side: 572 holds of
  1,000 against 466 at 1× (T51), learned (untrained 101). It stays below the field Guards' script (645; intervals
  0.541–0.602 against 0.615–0.674 do not overlap; game for game the script wins 118 games the trained team loses, the
  reverse 45). The curve on the curve starts rose steadily to about 1 B game-steps (share 0.47–0.50 of the 256 curve games), then slowly
  (0.50 → 0.54 from 1.07 B to 1.57 B). The new seed tracked T51's curve (37/46/52/66/70/76 against 38/46/54/64/72/81 of
  256 at updates 10–60, 0.06–0.38 B). This is a match on the 256 curve games up to 0.38 B for two seeds only; T51's
  1,000-game score was not re-read, so it does not show that the 1× result repeats. Unchosen tags: 0 of 2,379 tags
  pushed together by the filter. Recipe: T41's ([TRAIN_A_GUARD](../docs/TRAIN_A_GUARD.md)).
- **(d) Category.** The two-file read (gate header "Reads"): `ste/exploit.variant_verdict` on this side and the Strike
  side of [record T55](2026-11-22_ste_l012c_tag_1p15_strike_record.md), band 0.2, gives **worth learning** (better Strike
  reach upper 0.385, better Guard hold upper 0.674, both above 0.2). That category is set by the scripts (QC I-8): both
  trained sides are below their scripts.
- **Commit after rebase.** The run's commit `418d5e3c` (field "Commit" above) was rebased onto `development` on 22 Nov
  2026 as `9d3d5d43`; `git diff 418d5e3c 9d3d5d43 -- svg_training/scripts svg_training/source svg_training/configs`
  is empty (same code and configs; only `development`'s status commit 4c0224da lies beneath it). The old commit stays
  reachable in this machine's reflog only.
