Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator; not a flight result.

# 2026-11-22_ste_l012c_tag_1p15_strike record

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

- Gate file sha256 `362b9126cab72a20577bd12508d3a8f2f9008a75847ea6c1f2f79d6f340dfee9` (copy in each run folder: `gates.toml`).
- Band 0.2 (PROPOSED by the lead).
- Reference `configs/ste_l012b/screen_reference.npz`, sha256 `49014000d07e8b52ae579deb325dad53d98c5020f533026dfbff778f306b2296`; T44's starts sha256 `5aeba7ab2b582f2973034c8203c17ed3e8239fef7029a1f991fe95b82369843c`; the L0.12b scripted screen (configs/ste_l012b/screen_gates.toml) gate sha256 `881375f054a78ae33c7fd330e271a4e3b27a0a1cf3d58eca4b893cdca8ce2479`.
- Game `configs/ste_l011/tag_1p15.toml`, sha256 `b2e09683f7088964a7d1ca15dfc9c98d1e04c15e96b14196d6971afb75f27580`.
- tag_1p15 strike: trainer settings {'algorithm': 'IPPO', 'decision_ticks': 12, 'num_games': 16384, 'game_steps_per_run': 2750000000, 'rollouts': 32, 'learning_epochs': 5, 'mini_batches': 4, 'learning_rate': 0.0003, 'hidden': [128, 128], 'init_log_std': -1.6, 'frozen_log_std_axes': ['yaw'], 'zero_mean_init': True, 'discount_factor': 0.99, 'gae_lambda': 0.95, 'entropy_loss_scale': 0.0, 'value_loss_scale': 2.5, 'ratio_clip': 0.2, 'value_clip': 0.2, 'grad_norm_clip': 0.5, 'shaping_weight': 1.0, 'strike_fallback': {'shaping_weight': 1.0}, 'strike_fallback_label': 'shaped Strike recipe', 'checkpoint_every_updates': 1, 'curve_every_updates': 10, 'final_reserve_s': 600, 'final_reserve_factor': 2.0, 'clip_reserve_s': 120}

## Model parameter set

Tier 1 Starling layer: `params/real_exploratory_v0.toml` (fitted PX4 response, exploratory), sha256 `4c93543f51ab41ea5bb0f81e6d1b0512f662a3e10126ec2d85fc3bb008cecaa2`; safety filter on every pair, 1000 sweeps, check every 8.

## Commit

- tag_1p15 strike: `418d5e3cb76d7a0061311a7183dbc0dd7a9313d6` (diff sha256 e3b0c44298fc)

## Seeds

- tag_1p15 strike: training seed 120411; scoring starts T44's (seed 110000, loaded)

## Machine

- tag_1p15 strike: jeremychia-Legion-Pro-7-16IAX10H, NVIDIA GeForce RTX 5070 Ti Laptop GPU, torch 2.7.0+cu128; exit 0 (DONE); effective 11138 s of 4.8 h; job l012c_tag_1p15_strike (task L0.12), asked 4.8 GPU-h, used 3.107 GPU-h (shared ledger)

## Games at once and steps per second

- tag_1p15 strike: 16384 training games, 6 drones per game, tier 1, NVIDIA GeForce RTX 5070 Ti Laptop GPU: median 320,446 game-steps/s; 438 updates, 2,755,657,728 game-steps (budget: 2,755,657,728 of 2,750,000,000 game-steps); evaluation 1000 games per cell

## Run 0 (learner positive control)

Run 0: **PASS** (PASS at the checkpoint of update 10); scripted 899/1000 = 0.899 (0.879–0.916); reads update 10: 960/1000 (`runs/2026-11-22_ste_l012c_run0/learner_control.json`, sha256 a05c0f0c6df9).

## Gates

Verdict: **INFO (every control PASS; the categories feed gate G0)**.

| Variant | Role | Strike side | Guard side | Better Strike reach upper | Better Guard hold upper | Category |
|---|---|---|---|---|---|---|
| tag_1p15 | owner variant (bubble tag) | weak (learned, below the script) | - | - | - | **incomplete: one side only** |

| Variant | Side | Recipe | Trained exploiter | Untrained | Best script (cell) | Gain | Real | Paired (exploiter only / script only) | Guards left in holds (exploiter) | Length median (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| tag_1p15 | strike | shaped Strike recipe | 134/1000 = 0.134 (0.114–0.157) | 0/1000 = 0.000 (0.000–0.004) | 355/1000 = 0.355 (0.326–0.385) (guard_field v strike_straight) | -0.221 | False | 1 / 222 | 1.008 | 120.00 |

Unchosen tags of the trained exploiter (INFO; pushed together = on the tag's tick the safety filter's correction closed the pair faster than the players' commands; filter active = the filter corrected either drone of the pair on that tick, an upper bound; at the filter edge = pair distance at most the filter distance plus the gate's margin, 1.11 m):

| Variant | Side | Cell | Tags | Pushed together (share) | Filter active (share) | At the edge (share) |
|---|---|---|---|---|---|---|
| tag_1p15 | strike | guard_field v exploiter | 1826 | 194 (0.106) | 320 (0.175) | 0 (0.000) |

## Figures and videos

- tag_1p15 strike: videos/tag_1p15_strike_game0_hold.gif: game 0, hold at 120.0 s (1.04 MB)
- tag_1p15 strike: videos/tag_1p15_strike_game1_hold.gif: game 1, hold at 120.0 s (0.99 MB)

## Reading

(The lead writes the reading after QC; numbers come from the tables above.)

## Ledger row

Ledger row: | T55 | 2026-11-22T01:13:38+08:00 | training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED); NVIDIA GeForce RTX 5070 Ti Laptop GPU | 2026-11-22_ste_l012c_tag_1p15_strike | STE L0.12c Best-response test: tag_1p15 Strike: weak (learned, below the script), gain -0.221, Guards left 1.008, 120.00 s median (category incomplete: one side only, set by the L0.12b scripted screen (configs/ste_l012b/screen_gates.toml)'s scripts); 3.181 GPU-h | INFO | records/2026-11-22_ste_l012c_tag_1p15_strike_record.md |


## Run notes added by the lead

- **(a) What this run is.** L0.12c (owner approval 21 Nov 2026): the trained Strike team at tag 1.15 m with 5× the
  step budget of the ABORTED [record T52](2026-11-21_ste_l012b_tag_1p15_strike_record.md) (2.75 B game-steps), same
  shaped recipe, a new training seed (120411). Gate file `configs/ste_l012c/strike_gates.toml`, QC'd twice. Run 0 PASS
  at update 10 (960 reaches against the parked Guard, bar 849). Cap 4.8 h; the run used 3.11 GPU-h (run 0 0.07), so it
  reached its budget with room; not suspended; one job at a time.
- **(b) Figure and clips.** [longer_runs.png](../docs/figures/ste_l012c/longer_runs.png);
  [docs/media/ste_l012c](../docs/media/ste_l012c/README.md).
- **(c) Reading (lead; one seed, one opponent, one start set).** More training did not close the gap: 134 reaches of
  1,000 against the field Guards, below the straight Strikes' script (355); game for game the script wins 222 games the
  trained team loses, the reverse 1. Learned (untrained 0). The curve on the curve starts rose to 0.129 (33 of 256) by
  0.19 B, fell to 0.102 (26) at 0.57 B, then rose slowly to 0.176 (45) at 2.76 B, still rising at the end
  ([curve_reads.csv](../docs/figures/ste_l012c/curve_reads.csv)). In the 1,000 scoring games
  (cell 0 of `eval_final.npz`, 1-for-1 tags) the Strike team ends with 1 drone in 793 games, 2 in 114, 3 in 51 and none
  in 42; 824 games run to the 120 s clock: it usually trades two Strikes for two Guards, then the last Strike waits out
  the clock against the last Guard (Guards left in holds 1.0) instead of running for the zone (numbers check, 22 Nov).
  At 5× the trained Strike team stays far below the script. Whether more training or a different recipe (for example a
  tag-distance curriculum from 1.6 m) closes the gap is not shown. No cause of the shortfall is established
  ([DISCUSSION §12](../ste_learning/DISCUSSION_2026-11-19_20.md#12-l012c-findings-22-nov-2026)).
- **(d) Unchosen tags.** 194 of 1,826 tags (10.6 %) in these games were pushed together by the filter (filter active at
  17.5 % of tags): slightly above the scripted screen's 0–10 % per tag 1.15 m cell (T50).
- **(e) Category.** With [record T54](2026-11-22_ste_l012c_tag_1p15_guard_record.md): **worth learning** by the band
  (set by the scripts, QC I-8); both trained sides below their scripts.
- **Commit after rebase.** The run's commit `418d5e3c` (field "Commit" above) was rebased onto `development` on 22 Nov
  2026 as `9d3d5d43`; `git diff 418d5e3c 9d3d5d43 -- svg_training/scripts svg_training/source svg_training/configs`
  is empty (same code and configs; only `development`'s status commit 4c0224da lies beneath it). The old commit stays
  reachable in this machine's reflog only.
