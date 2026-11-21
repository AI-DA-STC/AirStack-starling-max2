Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator; not a flight result.

# 2026-11-21_ste_l012b_best_response record

## Run notes

- **Never suspend the machine during a GPU job** (no closed lid, no sleep): the cap clock and the GPU-hour ledger are wall clock less the owner's gpu_pause.sh pauses only (tooling task L07-SUSPEND). Say here whether the machine was suspended during the runs.
- **Asymmetries stated before the runs** (gate file header): one training seed per side; the learner decides every 0.6 s while the scripts decide every 0.05 s (finding L011-F1); one network per drone; about 1 GPU-h per run. A gain is evidence; no gain is weak evidence.
- **Decision-boundary restart** (LEAD CALL 21 Nov 2026): a game that ends inside a 0.6 s decision restarts at the next decision boundary; the ticks after its end are played, counted (stale-tick share) and never trained on (T41's hold let the new game play the old held action).
- **Strike recipe** (LEAD CALL 21 Nov 2026, pre-registered in [trainer] strike_fallback): the T41 recipe if its pilot probe against g* shows at least one reach; else the shaped Strike recipe (the game's distance shaping 1.0, training reward only), also when neither probe shows a reach (LEAD CALL 21 Nov 2026, QC N-1: 3-update probes no longer stop the Strike runs). The parked-Guard probes are information only. The recipe of each run is in the tables below.
- **Run 0, the learner positive control** (LEAD CALL 21 Nov 2026, QC N-1; gate [run0]): the Strike recipe trained against the parked Guard at the budget and cap of a run of record, read at pre-listed checkpoints (reach rate at least scripted strike_straight's on the same starts minus 0.05). Strike runs need run 0 = PASS; if it reads FAIL the Strike runs are not launched and the Strike side is INCONCLUSIVE (the trainer did not learn the easy Strike task at the run budget). Guard runs do not depend on it.
- **Hours** (LEAD CALL 21 Nov 2026, QC N-3): nothing kills a run at --gpu-h during its final phase; the GPU-hours below are the ledger's real hours.
- **Resume** (by design): networks, optimisers, scalers, counters and the torch random state are restored at the last update boundary, but the training games restart from the run seed's first starts (the game generator is not checkpointed), so a resumed run is not identical to an uninterrupted run. Each run's job launches say whether it was resumed.

## Purpose

STE task L0.12b: L0.12's best-response method on the variant(s) tag_1p15: an exploiter Strike team trained against the best scripted Guard g* and an exploiter Guard team trained against the best scripted Strike s*, g* and s* and the script baselines from the L0.12b scripted screen (configs/ste_l012b/screen_gates.toml) (on T44's own starts); the gain of each over the best script, the category on the better of script and exploiter, and the unchosen-tag shares (INFO).

## Config

- Gate file sha256 `ace5e18d77c214ca0a3e31d3613a20c3291e0f873ff6d1c5b90b8fec246fb592` (copy in each run folder: `gates.toml`).
- Band 0.2 (PROPOSED by the lead).
- Reference `configs/ste_l012b/screen_reference.npz`, sha256 `49014000d07e8b52ae579deb325dad53d98c5020f533026dfbff778f306b2296`; T44's starts sha256 `5aeba7ab2b582f2973034c8203c17ed3e8239fef7029a1f991fe95b82369843c`; the L0.12b scripted screen (configs/ste_l012b/screen_gates.toml) gate sha256 `881375f054a78ae33c7fd330e271a4e3b27a0a1cf3d58eca4b893cdca8ce2479`.
- Game `configs/ste_l011/tag_1p15.toml`, sha256 `b2e09683f7088964a7d1ca15dfc9c98d1e04c15e96b14196d6971afb75f27580`.
- tag_1p15 guard: trainer settings {'algorithm': 'IPPO', 'decision_ticks': 12, 'num_games': 16384, 'game_steps_per_run': 550000000, 'rollouts': 32, 'learning_epochs': 5, 'mini_batches': 4, 'learning_rate': 0.0003, 'hidden': [128, 128], 'init_log_std': -1.6, 'frozen_log_std_axes': ['yaw'], 'zero_mean_init': True, 'discount_factor': 0.99, 'gae_lambda': 0.95, 'entropy_loss_scale': 0.0, 'value_loss_scale': 2.5, 'ratio_clip': 0.2, 'value_clip': 0.2, 'grad_norm_clip': 0.5, 'shaping_weight': 0.0, 'strike_fallback': {'shaping_weight': 1.0}, 'strike_fallback_label': 'shaped Strike recipe', 'checkpoint_every_updates': 1, 'curve_every_updates': 10, 'final_reserve_s': 600, 'final_reserve_factor': 2.0, 'clip_reserve_s': 120}

## Model parameter set

Tier 1 Starling layer: `params/real_exploratory_v0.toml` (fitted PX4 response, exploratory), sha256 `4c93543f51ab41ea5bb0f81e6d1b0512f662a3e10126ec2d85fc3bb008cecaa2`; safety filter on every pair, 1000 sweeps, check every 8.

## Commit

- tag_1p15 guard: `db1948d1b1eb56b9f5a9285734bf233de6246d86` (diff sha256 e3b0c44298fc)

## Seeds

- tag_1p15 guard: training seed 120402; scoring starts T44's (seed 110000, loaded)

## Machine

- tag_1p15 guard: jeremychia-Legion-Pro-7-16IAX10H, NVIDIA GeForce RTX 5070 Ti Laptop GPU, torch 2.7.0+cu128; exit 0 (DONE); effective 1877 s of 0.85 h; job l012b_tag_1p15_guard (task L0.12), asked 0.85 GPU-h, used 0.523 GPU-h (shared ledger)

## Games at once and steps per second

- tag_1p15 guard: 16384 training games, 6 drones per game, tier 1, NVIDIA GeForce RTX 5070 Ti Laptop GPU: median 307,511 game-steps/s; 88 updates, 553,648,128 game-steps (budget: 553,648,128 of 550,000,000 game-steps); evaluation 1000 games per cell

## Run 0 (learner positive control)

Run 0: **PASS** (PASS at the checkpoint of update 10); scripted 899/1000 = 0.899 (0.879–0.916); reads update 10: 909/1000 (`runs/2026-11-21_ste_l012b_run0/learner_control.json`, sha256 5b30706e2270).

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
| tag_1p15 | owner variant (bubble tag) | - | weak (learned, below the script) | - | - | **incomplete: one side only** |

| Variant | Side | Recipe | Trained exploiter | Untrained | Best script (cell) | Gain | Real | Paired (exploiter only / script only) | Guards left in holds (exploiter) | Length median (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| tag_1p15 | guard | T41 recipe | 466/1000 = 0.466 (0.435–0.497) | 101/1000 = 0.101 (0.084–0.121) | 645/1000 = 0.645 (0.615–0.674) (guard_field v strike_straight) | -0.179 | False | 10 / 189 | 0.000 | 2.90 |

Unchosen tags of the trained exploiter (INFO; pushed together = on the tag's tick the safety filter's correction closed the pair faster than the players' commands; filter active = the filter corrected either drone of the pair on that tick, an upper bound; at the filter edge = pair distance at most the filter distance plus the gate's margin, 1.11 m):

| Variant | Side | Cell | Tags | Pushed together (share) | Filter active (share) | At the edge (share) |
|---|---|---|---|---|---|---|
| tag_1p15 | guard | exploiter v strike_straight | 2263 | 0 (0.000) | 2263 (1.000) | 0 (0.000) |

## Figures and videos

- tag_1p15 guard: videos/tag_1p15_guard_game0_reach.gif: game 0, reach at 2.9 s (0.06 MB)
- tag_1p15 guard: videos/tag_1p15_guard_game2_hold.gif: game 2, hold at 2.8 s (0.05 MB)

## Run notes added by the lead

- **Figure and clips.** The bubble tag beside L0.12's variants (trained, best script and untrained per side, Wilson
  95 %): [bubble.png](../docs/figures/ste_l012b/bubble.png), made by `scripts/make_ste_l012_figures.py` from both
  verdict files (the ABORTED sides show their script only). Clips: [docs/media/ste_l012b](../docs/media/ste_l012b/README.md).
- **(a) Why 1.15 m.** The owner's realism question: a tag the drones can really make. 1.15 m is the safety filter's
  1.10 m keep-out plus 0.05 m ("touching the bubble"), the same rule in the simulator and on the drones.
- **(b) Unchosen tags.** In the screen ([record T50](2026-11-21_ste_l012b_screen_record.md)) "pushed together" is 0–10 %
  per cell and 0 % for g* v s*; "filter active" is about 100 % at 1.15 m because the filter brakes nearly every close
  approach (an upper bound). So nearly every tag is one the players chose. For the trained Guard team: 0 of 2,263 tags
  pushed together (table above). The screen ran before QC fix 6; QC found 0 of 10,871 pushed tags lacking the flag, so
  the shares stand.
- **(c) The ABORTED Strike run** ([record T52](2026-11-21_ste_l012b_tag_1p15_strike_record.md)). The lead sized the
  0.85 h cap from L0.12's tag 1.6 / 1.4 / 1.2 m Strike timings plus 5 %. At 1.15 m a training update took 20.7 s against
  18.4–19.6 s in those runs, the controls batch 106 s against 95 s at most, and the measured final reserve was 664 s
  against the 640 s assumed: the run stopped at update 86 of 88. Lesson: size caps from timings measured on the same rule
  set (the screen's batch times). Not re-run (lead's recommendation; the owner asked).
- **(d) Reading for G0 (lead's, information).** At 1.15 m and 1.2 m learning did not beat the scripts: the trained Guard
  team stays below the field Guards' script (466 and 503 against 645), and the trained Strikes of both ABORTED runs wait
  out the clock. At 1.6 m and 1.4 m it did (T46). Tag 1.15 m stays "incomplete: one side only"; its scripts alone already
  sit above the gate's 0.2 band on both sides (Guard 645, Strike 355).
- **(e) 3-D clips** of the key games: pending task VID-1b.
- **Run 0** (the learner check): PASS at update 10, 909 of 1,000 reaches against Guards parked at the centre; the bar
  849 is the screen's own tag 1.15 m cell guard_parked_centre v strike_straight (899) less 0.05. The Strike probes printed
  above are L0.12's pilot, reused (gate file).
- **Suspend.** Not suspended: one launch per run, one boot; run 0 343 s effective against 345 s, Guard run 1,881 s
  against 1,882 s. GPU-hours: run 0 0.096, Guard run 0.523 (the 0.619 in the ledger row).
- **Commit.** The runs name the branch's commits before its rebase on development (same content).

## Ledger row

Ledger row: | T51 | 2026-11-21T15:52:59+08:00 | training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED); NVIDIA GeForce RTX 5070 Ti Laptop GPU | 2026-11-21_ste_l012b_best_response | STE L0.12b Best-response test: tag_1p15 Guard: weak (learned, below the script), gain -0.179, Guards left 0.000, 2.90 s median (category incomplete: one side only, set by the L0.12b scripted screen (configs/ste_l012b/screen_gates.toml)'s scripts); 0.619 GPU-h | INFO | records/2026-11-21_ste_l012b_best_response_record.md |

