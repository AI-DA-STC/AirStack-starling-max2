Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator; not a flight result.

# 2026-11-21_ste_l012_best_response record

## Run notes

- **Never suspend the machine during a GPU job** (no closed lid, no sleep): the cap clock and the GPU-hour ledger are wall clock less the owner's gpu_pause.sh pauses only (tooling task L07-SUSPEND). Say here whether the machine was suspended during the runs.
- **Asymmetries stated before the runs** (gate file header): one training seed per side; the learner decides every 0.6 s while the scripts decide every 0.05 s (finding L011-F1); one network per drone; about 1 GPU-h per run. A gain is evidence; no gain is weak evidence.
- **Decision-boundary restart** (LEAD CALL 21 Nov 2026): a game that ends inside a 0.6 s decision restarts at the next decision boundary; the ticks after its end are played, counted (stale-tick share) and never trained on (T41's hold let the new game play the old held action).
- **Strike recipe** (LEAD CALL 21 Nov 2026, pre-registered in [trainer] strike_fallback): the T41 recipe if its pilot probe against g* shows at least one reach; else the shaped Strike recipe (the game's distance shaping 1.0, training reward only), also when neither probe shows a reach (LEAD CALL 21 Nov 2026, QC N-1: 3-update probes no longer stop the Strike runs). The parked-Guard probes are information only. The recipe of each run is in the tables below.
- **Run 0, the learner positive control** (LEAD CALL 21 Nov 2026, QC N-1; gate [run0]): the Strike recipe trained against the parked Guard at the budget and cap of a run of record, read at pre-listed checkpoints (reach rate at least scripted strike_straight's on the same starts minus 0.05). Strike runs need run 0 = PASS; if it reads FAIL the Strike runs are not launched and the Strike side is INCONCLUSIVE (the trainer did not learn the easy Strike task at the run budget). Guard runs do not depend on it.
- **Hours** (LEAD CALL 21 Nov 2026, QC N-3): nothing kills a run at --gpu-h during its final phase; the GPU-hours below are the ledger's real hours.
- **Resume** (by design): networks, optimisers, scalers, counters and the torch random state are restored at the last update boundary, but the training games restart from the run seed's first starts (the game generator is not checkpointed), so a resumed run is not identical to an uninterrupted run. Each run's job launches say whether it was resumed.

## Purpose

STE task L0.12 Best-response test (PLAN.md section 4): for each shortlisted variant of T44, an exploiter Strike team trained against the best scripted Guard g* and an exploiter Guard team trained against the best scripted Strike s*; the gain of each over the best script on T44's own starts, and the variant's category on the better of script and exploiter (LEAD CALL 21 Nov 2026).

## Config

- Gate file sha256 `6e2e606053a593185480f8671c406625dc844002395801023005945f58cfbc5b` (copy in each run folder: `gates.toml`).
- Band 0.2 (PROPOSED by the lead).
- Reference `configs/ste_l012/t44_reference.npz`, sha256 `4bc5e011071adced368b2a0025fc47499839e0bbc8d8d650207bd12c3da0f8b5`; T44's starts sha256 `5aeba7ab2b582f2973034c8203c17ed3e8239fef7029a1f991fe95b82369843c`; T44 gate sha256 `8bfbc2cb8f1d6551fb3060bc750c24f9b2220ebafb19fcd44e9e3baa1c24e5d4`.
- Game `configs/ste_l011/base.toml`, sha256 `96e0e7f61a49999da54eee81a544bf64c519cd80833f0dcdfa2a07edfc10cc4d`.
- Game `configs/ste_l011/tag_1p2.toml`, sha256 `60a225a1f6876407edac2a12ac1002a161971e7b4c7923a838e710723ee4e378`.
- Game `configs/ste_l011/tag_1p4.toml`, sha256 `ddcfa1f56fd533907651225260939426617a38db83aec5f94404b6b27202124f`.
- base guard: trainer settings {'algorithm': 'IPPO', 'decision_ticks': 12, 'num_games': 16384, 'game_steps_per_run': 550000000, 'rollouts': 32, 'learning_epochs': 5, 'mini_batches': 4, 'learning_rate': 0.0003, 'hidden': [128, 128], 'init_log_std': -1.6, 'frozen_log_std_axes': ['yaw'], 'zero_mean_init': True, 'discount_factor': 0.99, 'gae_lambda': 0.95, 'entropy_loss_scale': 0.0, 'value_loss_scale': 2.5, 'ratio_clip': 0.2, 'value_clip': 0.2, 'grad_norm_clip': 0.5, 'shaping_weight': 0.0, 'strike_fallback': {'shaping_weight': 1.0}, 'strike_fallback_label': 'shaped Strike recipe', 'checkpoint_every_updates': 1, 'curve_every_updates': 10, 'final_reserve_s': 600, 'final_reserve_factor': 2.0, 'clip_reserve_s': 120}
- base strike: trainer settings {'algorithm': 'IPPO', 'decision_ticks': 12, 'num_games': 16384, 'game_steps_per_run': 550000000, 'rollouts': 32, 'learning_epochs': 5, 'mini_batches': 4, 'learning_rate': 0.0003, 'hidden': [128, 128], 'init_log_std': -1.6, 'frozen_log_std_axes': ['yaw'], 'zero_mean_init': True, 'discount_factor': 0.99, 'gae_lambda': 0.95, 'entropy_loss_scale': 0.0, 'value_loss_scale': 2.5, 'ratio_clip': 0.2, 'value_clip': 0.2, 'grad_norm_clip': 0.5, 'shaping_weight': 1.0, 'strike_fallback': {'shaping_weight': 1.0}, 'strike_fallback_label': 'shaped Strike recipe', 'checkpoint_every_updates': 1, 'curve_every_updates': 10, 'final_reserve_s': 600, 'final_reserve_factor': 2.0, 'clip_reserve_s': 120}
- tag_1p2 guard: trainer settings {'algorithm': 'IPPO', 'decision_ticks': 12, 'num_games': 16384, 'game_steps_per_run': 550000000, 'rollouts': 32, 'learning_epochs': 5, 'mini_batches': 4, 'learning_rate': 0.0003, 'hidden': [128, 128], 'init_log_std': -1.6, 'frozen_log_std_axes': ['yaw'], 'zero_mean_init': True, 'discount_factor': 0.99, 'gae_lambda': 0.95, 'entropy_loss_scale': 0.0, 'value_loss_scale': 2.5, 'ratio_clip': 0.2, 'value_clip': 0.2, 'grad_norm_clip': 0.5, 'shaping_weight': 0.0, 'strike_fallback': {'shaping_weight': 1.0}, 'strike_fallback_label': 'shaped Strike recipe', 'checkpoint_every_updates': 1, 'curve_every_updates': 10, 'final_reserve_s': 600, 'final_reserve_factor': 2.0, 'clip_reserve_s': 120}
- tag_1p4 guard: trainer settings {'algorithm': 'IPPO', 'decision_ticks': 12, 'num_games': 16384, 'game_steps_per_run': 550000000, 'rollouts': 32, 'learning_epochs': 5, 'mini_batches': 4, 'learning_rate': 0.0003, 'hidden': [128, 128], 'init_log_std': -1.6, 'frozen_log_std_axes': ['yaw'], 'zero_mean_init': True, 'discount_factor': 0.99, 'gae_lambda': 0.95, 'entropy_loss_scale': 0.0, 'value_loss_scale': 2.5, 'ratio_clip': 0.2, 'value_clip': 0.2, 'grad_norm_clip': 0.5, 'shaping_weight': 0.0, 'strike_fallback': {'shaping_weight': 1.0}, 'strike_fallback_label': 'shaped Strike recipe', 'checkpoint_every_updates': 1, 'curve_every_updates': 10, 'final_reserve_s': 600, 'final_reserve_factor': 2.0, 'clip_reserve_s': 120}
- tag_1p4 strike: trainer settings {'algorithm': 'IPPO', 'decision_ticks': 12, 'num_games': 16384, 'game_steps_per_run': 550000000, 'rollouts': 32, 'learning_epochs': 5, 'mini_batches': 4, 'learning_rate': 0.0003, 'hidden': [128, 128], 'init_log_std': -1.6, 'frozen_log_std_axes': ['yaw'], 'zero_mean_init': True, 'discount_factor': 0.99, 'gae_lambda': 0.95, 'entropy_loss_scale': 0.0, 'value_loss_scale': 2.5, 'ratio_clip': 0.2, 'value_clip': 0.2, 'grad_norm_clip': 0.5, 'shaping_weight': 1.0, 'strike_fallback': {'shaping_weight': 1.0}, 'strike_fallback_label': 'shaped Strike recipe', 'checkpoint_every_updates': 1, 'curve_every_updates': 10, 'final_reserve_s': 600, 'final_reserve_factor': 2.0, 'clip_reserve_s': 120}

## Model parameter set

Tier 1 Starling layer: `params/real_exploratory_v0.toml` (fitted PX4 response, exploratory), sha256 `4c93543f51ab41ea5bb0f81e6d1b0512f662a3e10126ec2d85fc3bb008cecaa2`; safety filter on every pair, 1000 sweeps, check every 8.

## Commit

- base guard: `c8a1538df3f2bad07b952e5fdda7bbd448cce666` (diff sha256 e3b0c44298fc)
- base strike: `c8a1538df3f2bad07b952e5fdda7bbd448cce666` (diff sha256 e3b0c44298fc)
- tag_1p2 guard: `c8a1538df3f2bad07b952e5fdda7bbd448cce666` (diff sha256 e3b0c44298fc)
- tag_1p4 guard: `c8a1538df3f2bad07b952e5fdda7bbd448cce666` (diff sha256 e3b0c44298fc)
- tag_1p4 strike: `c8a1538df3f2bad07b952e5fdda7bbd448cce666` (diff sha256 e3b0c44298fc)

## Seeds

- base guard: training seed 120102; scoring starts T44's (seed 110000, loaded)
- base strike: training seed 120101; scoring starts T44's (seed 110000, loaded)
- tag_1p2 guard: training seed 120202; scoring starts T44's (seed 110000, loaded)
- tag_1p4 guard: training seed 120302; scoring starts T44's (seed 110000, loaded)
- tag_1p4 strike: training seed 120301; scoring starts T44's (seed 110000, loaded)

## Machine

- base guard: jeremychia-Legion-Pro-7-16IAX10H, NVIDIA GeForce RTX 5070 Ti Laptop GPU, torch 2.7.0+cu128; exit 0 (DONE); effective 1451 s of 0.75 h; job l012_base_guard (task L0.12), asked 0.75 GPU-h, used 0.404 GPU-h (shared ledger)
- base strike: jeremychia-Legion-Pro-7-16IAX10H, NVIDIA GeForce RTX 5070 Ti Laptop GPU, torch 2.7.0+cu128; exit 0 (DONE); effective 2126 s of 0.75 h; job l012_base_strike (task L0.12), asked 0.75 GPU-h, used 0.594 GPU-h (shared ledger)
- tag_1p2 guard: jeremychia-Legion-Pro-7-16IAX10H, NVIDIA GeForce RTX 5070 Ti Laptop GPU, torch 2.7.0+cu128; exit 0 (DONE); effective 1728 s of 0.75 h; job l012_tag_1p2_guard (task L0.12), asked 0.75 GPU-h, used 0.481 GPU-h (shared ledger)
- tag_1p4 guard: jeremychia-Legion-Pro-7-16IAX10H, NVIDIA GeForce RTX 5070 Ti Laptop GPU, torch 2.7.0+cu128; exit 0 (DONE); effective 1524 s of 0.75 h; job l012_tag_1p4_guard (task L0.12), asked 0.75 GPU-h, used 0.425 GPU-h (shared ledger)
- tag_1p4 strike: jeremychia-Legion-Pro-7-16IAX10H, NVIDIA GeForce RTX 5070 Ti Laptop GPU, torch 2.7.0+cu128; exit 0 (DONE); effective 2045 s of 0.75 h; job l012_tag_1p4_strike (task L0.12), asked 0.75 GPU-h, used 0.570 GPU-h (shared ledger)

## Games at once and steps per second

- base guard: 16384 training games, 6 drones per game, tier 1, NVIDIA GeForce RTX 5070 Ti Laptop GPU: median 396,236 game-steps/s; 88 updates, 553,648,128 game-steps (budget: 553,648,128 of 550,000,000 game-steps); evaluation 1000 games per cell
- base strike: 16384 training games, 6 drones per game, tier 1, NVIDIA GeForce RTX 5070 Ti Laptop GPU: median 340,703 game-steps/s; 88 updates, 553,648,128 game-steps (budget: 553,648,128 of 550,000,000 game-steps); evaluation 1000 games per cell
- tag_1p2 guard: 16384 training games, 6 drones per game, tier 1, NVIDIA GeForce RTX 5070 Ti Laptop GPU: median 340,259 game-steps/s; 88 updates, 553,648,128 game-steps (budget: 553,648,128 of 550,000,000 game-steps); evaluation 1000 games per cell
- tag_1p4 guard: 16384 training games, 6 drones per game, tier 1, NVIDIA GeForce RTX 5070 Ti Laptop GPU: median 378,283 game-steps/s; 88 updates, 553,648,128 game-steps (budget: 553,648,128 of 550,000,000 game-steps); evaluation 1000 games per cell
- tag_1p4 strike: 16384 training games, 6 drones per game, tier 1, NVIDIA GeForce RTX 5070 Ti Laptop GPU: median 322,193 game-steps/s; 88 updates, 553,648,128 game-steps (budget: 553,648,128 of 550,000,000 game-steps); evaluation 1000 games per cell

## Run 0 (learner positive control)

Run 0: **PASS** (PASS at the checkpoint of update 10); scripted 466/1000 = 0.466 (0.435–0.497); reads update 10: 478/1000 (`runs/2026-11-21_ste_l012_run0/learner_control.json`, sha256 188362a05c69).

Strike probes of the pilot (reaches / ended training games per update):

- {'side': 'strike', 'num_games': 16384}: 0/31614, 0/33417, 0/28208
- {'side': 'strike', 'opponent': 'guard_parked_centre', 'num_games': 16384}: 0/3, 9/42, 107/216
- {'side': 'strike', 'shaping_weight': 1.0, 'num_games': 16384}: 0/31614, 0/34051, 1/31384
- {'side': 'strike', 'shaping_weight': 1.0, 'opponent': 'guard_parked_centre', 'num_games': 16384}: 0/3, 12/51, 162/370
- recipe picked: {'recipe': 'shaped Strike recipe', 'bare_reaches': 0, 'fallback_reaches': 1, 'side_overrides_strike': {'shaping_weight': 1.0}, 'by_default': False, 'note': 'picked by the probes against g*; run 0 decides whether the Strike runs launch', 'bare_reaches_parked_info': 116, 'fallback_reaches_parked_info': 174, 'label': 'shaped Strike recipe'} (the learner positive control is run 0, above)

## Gates

Verdict: **INFO (every control PASS; the categories feed gate G0)**.

| Variant | Role | Strike side | Guard side | Better Strike reach upper | Better Guard hold upper | Category |
|---|---|---|---|---|---|---|
| base | reference | gain | gain | 0.665 | 0.929 | **worth learning** |
| tag_1p2 | shortlisted | - | weak (learned, below the script) | - | - | **incomplete: one side only** |
| tag_1p4 | shortlisted | gain | gain | 0.766 | 0.773 | **worth learning** |

| Variant | Side | Recipe | Trained exploiter | Untrained | Best script (cell) | Gain | Real | Paired (exploiter only / script only) | Guards left in holds (exploiter) | Length median (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| base | strike | shaped Strike recipe | 636/1000 = 0.636 (0.606–0.665) | 0/1000 = 0.000 (0.000–0.004) | 192/1000 = 0.192 (0.169–0.218) (guard_mark_edge v strike_straight) | +0.444 | True | 524 / 80 | 0.104 | 7.50 |
| base | guard | T41 recipe | 913/1000 = 0.913 (0.894–0.929) | 534/1000 = 0.534 (0.503–0.565) | 808/1000 = 0.808 (0.782–0.831) (guard_mark_edge v strike_straight) | +0.105 | True | 155 / 50 | 0.000 | 2.45 |
| tag_1p2 | guard | T41 recipe | 503/1000 = 0.503 (0.472–0.534) | 144/1000 = 0.144 (0.124–0.167) | 645/1000 = 0.645 (0.615–0.674) (guard_field v strike_straight) | -0.142 | False | 13 / 155 | 0.000 | 2.90 |
| tag_1p4 | strike | shaped Strike recipe | 740/1000 = 0.740 (0.712–0.766) | 0/1000 = 0.000 (0.000–0.004) | 328/1000 = 0.328 (0.300–0.358) (guard_mirror v strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info))) | +0.412 | True | 450 / 38 | 0.004 | 6.55 |
| tag_1p4 | guard | T41 recipe | 747/1000 = 0.747 (0.719–0.773) | 224/1000 = 0.224 (0.199–0.251) | 672/1000 = 0.672 (0.642–0.700) (guard_mirror v strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info))) | +0.075 | True | 235 / 160 | 0.000 | 3.30 |

Evaluation-only opponents (INFO; script baseline from the T44 reference, same starts):

| Run | Opponent | Trained exploiter | Best script | Gain | Real |
|---|---|---|---|---|---|
| tag_1p4 guard | strike_straight | 673/1000 = 0.673 (0.643–0.701) | 701/1000 = 0.701 (0.672–0.729) | -0.028 | False |

## Figures and videos

- base guard: videos/base_guard_game0_hold.gif: game 0, hold at 2.7 s (0.05 MB)
- base guard: videos/base_guard_game1_hold.gif: game 1, hold at 2.6 s (0.05 MB)
- base strike: videos/base_strike_game0_reach.gif: game 0, reach at 14.5 s (0.18 MB)
- base strike: videos/base_strike_game2_hold.gif: game 2, hold at 5.0 s (0.09 MB)
- tag_1p2 guard: videos/tag_1p2_guard_game0_reach.gif: game 0, reach at 2.9 s (0.06 MB)
- tag_1p2 guard: videos/tag_1p2_guard_game2_hold.gif: game 2, hold at 2.7 s (0.06 MB)
- tag_1p4 guard: videos/tag_1p4_guard_game0_reach.gif: game 0, reach at 3.6 s (0.07 MB)
- tag_1p4 guard: videos/tag_1p4_guard_game1_hold.gif: game 1, hold at 3.6 s (0.07 MB)
- tag_1p4 strike: videos/tag_1p4_strike_game0_reach.gif: game 0, reach at 7.9 s (0.13 MB)
- tag_1p4 strike: videos/tag_1p4_strike_game2_hold.gif: game 2, hold at 5.8 s (0.10 MB)

## Run notes added by the lead

- **In short.** Base (tag 1.6 m) and tag 1.4 m read **worth learning** on both sides: the trained Strike team gains
  +0.444 (base) and +0.412 (tag 1.4 m) over the best scripted player, the trained Guard team +0.105 and +0.075; all four
  gains are real (Wilson intervals apart). Tag 1.2 m is **incomplete: one side only**. Figure (trained, best script and
  untrained per variant and side): [best_response.png](../docs/figures/ste_l012/best_response.png). Clips (2-D with the
  height panel): [docs/media/ste_l012](../docs/media/ste_l012/README.md).
- **(a) Tag 1.2 m.** The scripts alone already sit above the 0.2 band on both sides (Guard team holds 645 of 1,000,
  Strike team reaches 355), so neither side is trivial at tag 1.2 m. Only the trained Strike team's reading is missing:
  its run stopped one update short of its budget ([record T47](2026-11-21_ste_l012_tag_1p2_strike_record.md), QC N-2).
  The lead did not re-run it: about 1 GPU-h on top of L0.12's 6, and it could not change the category. The trained Guard
  team (503) stays below the field Guards' script (645): weak.
- **(b) What the trained Strike team does at base** (lead's reading of the clip
  [base_trained_strike_game0_reach](../docs/media/ste_l012/base_trained_strike_game0_reach.gif)): the Strike drones
  climb to the 1.8 m height limit over the Guards at 1.2 m, two of them trade with Guards, and the last waits at the edge
  and slips in. Games last longer: median 7.5 s against 2.4 s for the scripts on the same starts. At tag 1.2 m the
  trained Strikes of the ABORTED run instead wait out the 120 s clock (786 of 1,000 games ran to the clock; T47, proves
  nothing).
- **(c) Guards left in holds stay about 0 for trained Guards**: no Guard is left in any hold of a trained Guard team
  (0.000 in each variant); in holds against a trained Strike team 0.104 Guards on average at base and 0.004 at tag
  1.4 m: at base 327 of the 364 holds leave no Guard and 37 ran to the 120 s clock (tag 1.4 m: 259 and 1 of 260).
  Holds are still one-for-one trades; this bears on finding L011-G0 (what a tag costs).
- **(d) Run 0 is the learner positive control** (QC N-1): PASS at its first read (update 10: 478 of 1,000 reaches
  against Guards parked at the centre; threshold 416 = scripted 466 less 0.05), so the Strike runs were launched.
- **(e) ENDED_EARLY.** Every `ENDED_EARLY` flag from the waiter came from the lead's `--min-s 1800`, set above the real
  run time of the runs it flagged; each run ended with exit 0. Not a fault.
- **(f) 3-D clips** of the key games: pending task VID-1b (the 3-D tool replays scripted games only; trained players
  need an extension).
- **Suspend.** The machine was not suspended: one launch per run, all on one boot; effective time is within 2–11 s of
  each launch's wall-clock span, except the ABORTED run (2,322 s against 2,372 s; the 50 s gap was not looked into).
- **GPU-hours** (shared ledger): pilot 0.178, run 0 0.061, base Guard 0.404, base Strike 0.594, tag 1.2 m Guard 0.481,
  tag 1.2 m Strike 0.659 (T47), tag 1.4 m Guard 0.425, tag 1.4 m Strike 0.570; 3.372 of the L0.12 cap of 6. The ledger
  row above counts the five runs of record and run 0 only.
- **Writer fixes before this record was written** (same branch, test first, `tests/test_ste_l012_record.py`): the
  ledger row in LEDGER.md's seven columns (date = the first launch), rounded numbers, "-" for a missing side instead of
  nan, and "run 0, above" in the probe note. No number changed.
- **Figure** made by `scripts/make_ste_l012_figures.py` from `runs/2026-11-21_ste_l012_verdict/verdict.json` (the
  ABORTED side from its run's results.json: best script only).
- Edited after the first write (same session, before any push): one sentence of the lead's notes removed (it
  overstated where the categories come from), the hold split in (c) and the figure line added; no number changed.
- **QC wording notes (21 Nov 2026, after independent QC; earlier notes not rewritten):**
  - (a) "neither side is trivial at tag 1.2 m" means: by the gate's 0.2 band, read on the scripts alone.
  - (b) The height-and-patience description is the lead's reading of one clip; no control run (such as a lower height
    cap) was made.
  - (c) Holds are one-for-one trades except against trained Strike teams, where some holds run to the 120 s clock: base
    37 of 364, tag 1.4 m 1 of 260; in the ABORTED tag 1.2 m Strike run 786 of 1,000 games ran to the clock with 1.123
    Guards left on average (information only, T47).
  - Effective-time gap of the ABORTED run: results.json's effective_s 2,321.8 s was written before the run's final
    write; progress.json ends at 2,370.8 s, which matches the 2,372 s wall-clock span: a recording-stage difference,
    not a suspend.

## Ledger row

Ledger row: | T46 | 2026-11-21T09:51:26+08:00 | training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED); NVIDIA GeForce RTX 5070 Ti Laptop GPU | 2026-11-21_ste_l012_best_response | STE L0.12 Best-response test: base Strike: gain, gain +0.444, Guards left 0.104, 7.50 s median; base Guard: gain, gain +0.105, Guards left 0.000, 2.45 s median (category worth learning, set by T44's scripts) / tag_1p2 Guard: weak (learned, below the script), gain -0.142, Guards left 0.000, 2.90 s median (category incomplete: one side only, set by T44's scripts) / tag_1p4 Strike: gain, gain +0.412, Guards left 0.004, 6.55 s median; tag_1p4 Guard: gain, gain +0.075, Guards left 0.000, 3.30 s median (category worth learning, set by T44's scripts); 2.535 GPU-h | INFO | records/2026-11-21_ste_l012_best_response_record.md |

