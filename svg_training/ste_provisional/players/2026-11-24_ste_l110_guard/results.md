Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator; nothing here is a flight result.

# L0.12 Best-response test: base_tagdraw, exploiter guard

- Gate file sha256 `ae597e378a475abfff2196a993a29ea664258ae76be324263a2738ed9906ddc0`; reference sha256 `4bc5e011071adced368b2a0025fc47499839e0bbc8d8d650207bd12c3da0f8b5`; device cuda; 1000 evaluation games on T44's starts.

## Controls (read these first)

| Control | Phase | Status | Detail |
|---|---|---|---|
| ctl_reference_replay | before | **PASS** | guard_parked_centre v strike_straight: ok (holds 534 v T44 534, reaches 466 v 466; 0 of 1000 games differ (0 in outcome)); guard_parked_ring v strike_straight: ok (holds 523 v T44 523, reaches 477 v 477; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_straight: ok (holds 808 v T44 808, reaches 192 v 192; 0 of 1000 games differ (0 in outcome)); guard_mirror v strike_straight: ok (holds 796 v T44 796, reaches 204 v 204; 0 of 1000 games differ (0 in outcome)); guard_field v strike_straight: ok (holds 716 v T44 716, reaches 284 v 284; 0 of 1000 games differ (0 in outcome)) |
| ctl_untrained_is_still | before | **PASS** | untrained exploiter v zero script: holds 534 v T44 534, reaches 466 v 466; 0 of 1000 games differ (0 in outcome) |
| ctl_untrained_no_gain | before | **PASS** | untrained 534/1000 v best script 808/1000: gain -0.274, real False (must be False) |
| ctl_paired_starts | before | **PASS** | 1 start set(s), reference 5aeba7ab2b58 |
| tags_one_for_one | before | **PASS** | 0 games not one for one of 7000 |
| no_nonfinite_actions | before | **PASS** | 0 non-finite actions |
| tags_one_for_one_curve | curve | **PASS** | 0 games or actions wrong over the curve evaluations |
| no_nonfinite_actions_curve | curve | **PASS** | 0 games or actions wrong over the curve evaluations |
| ctl_reference_replay_final | final | **PASS** | guard_parked_centre v strike_straight: ok (holds 534 v T44 534, reaches 466 v 466; 0 of 1000 games differ (0 in outcome)); guard_parked_ring v strike_straight: ok (holds 523 v T44 523, reaches 477 v 477; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_straight: ok (holds 808 v T44 808, reaches 192 v 192; 0 of 1000 games differ (0 in outcome)); guard_mirror v strike_straight: ok (holds 796 v T44 796, reaches 204 v 204; 0 of 1000 games differ (0 in outcome)); guard_field v strike_straight: ok (holds 716 v T44 716, reaches 284 v 284; 0 of 1000 games differ (0 in outcome)) |
| ctl_paired_starts_final | final | **PASS** | 1 start set(s), reference 5aeba7ab2b58 |
| tags_one_for_one_final | final | **PASS** | 0 games not one for one of 7000 |
| no_nonfinite_actions_final | final | **PASS** | 0 non-finite actions |
| ctl_paired_starts_info | final | **PASS** | 1 start set(s), reference 5aeba7ab2b58 |
| tags_one_for_one_info | final | **PASS** | 0 games not one for one of 6000 |
| no_nonfinite_actions_info | final | **PASS** | 0 non-finite actions |

Recipe: **T41 recipe**. Games that end inside a 0.6 s decision restart at the next decision boundary (LEAD CALL 21 Nov 2026): the ticks after the end are played, counted, never trained on.

Training opponent: strike_straight (the maximin pick (g* / s*)); discount factor 0.99 per decision; trained on `configs/ste_l1/base_err_tagdraw.toml`, scored on `configs/ste_l011/base.toml`; learning curve and scores at the 120 s clock: curves at different clocks (L1.13 arm A at 30 s; T52 and arm B at 120 s) are not comparable update by update.

## Result (hold rate against strike_straight, Wilson 95 %)

| Player | Count | Guards left in holds (mean) | Length median / p90 (s) |
|---|---|---|---|
| trained exploiter | 921/1000 = 0.921 (0.903-0.936) | 0.0 | 2.45 / 2.9000000000000004 |
| untrained exploiter | 534/1000 = 0.534 (0.503-0.565) | | |
| best script (guard_mark_edge v strike_straight) | 808/1000 = 0.808 (0.782-0.831) | 0.0 | 2.4000000000000004 / 2.9000000000000004 |

Learned: **True**. Gain over the best script: +0.113, real (intervals disjoint): **True**. Side: **gain**. Paired: exploiter won and script lost 154 games, the reverse 41.

Training: 88 updates, 553,648,128 game-steps (budget: 553,648,128 of 550,000,000 game-steps); median 1,049,511 game-steps/s at 16384 games, 6 drones per game, tier 1, NVIDIA GeForce RTX 5090; stale-tick share 0.08604868072451967.

## INFO: the exploiter against every script of the other team

| Cell | Holds | Reaches | Games |
|---|---|---|---|
| exploiter v strike_straight | 921 | 79 | 1000 |
| exploiter v strike_flank | 960 | 40 | 1000 |
| exploiter v strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 938 | 62 | 1000 |
| exploiter v strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 896 | 104 | 1000 |
| exploiter v strike_sacrifice | 930 | 70 | 1000 |
| exploiter v strike_converge | 928 | 72 | 1000 |

## Videos

- videos/base_tagdraw_guard_game0_hold.gif: game 0, hold at 2.7 s (0.05 MB)
- videos/base_tagdraw_guard_game1_hold.gif: game 1, hold at 2.6 s (0.05 MB)
