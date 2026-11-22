Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator; nothing here is a flight result.

# L0.12 Best-response test: base, exploiter strike

- Gate file sha256 `84aea8592800f0d3fc205bbf879df9252ce3b6775fe3515b070d73ae9df80ef0`; reference sha256 `4bc5e011071adced368b2a0025fc47499839e0bbc8d8d650207bd12c3da0f8b5`; device cuda; 1000 evaluation games on T44's starts.

## Controls (read these first)

| Control | Phase | Status | Detail |
|---|---|---|---|
| ctl_reference_replay | before | **PASS** | guard_field v strike_straight: ok (holds 716 v T44 716, reaches 284 v 284; 0 of 1000 games differ (0 in outcome)); guard_field v strike_flank: ok (holds 808 v T44 808, reaches 192 v 192; 0 of 1000 games differ (0 in outcome)); guard_field v strike_high: ok (holds 734 v T44 734, reaches 266 v 266; 0 of 1000 games differ (0 in outcome)); guard_field v strike_low: ok (holds 739 v T44 739, reaches 261 v 261; 0 of 1000 games differ (0 in outcome)); guard_field v strike_sacrifice: ok (holds 862 v T44 862, reaches 138 v 138; 0 of 1000 games differ (0 in outcome)); guard_field v strike_converge: ok (holds 871 v T44 871, reaches 129 v 129; 0 of 1000 games differ (0 in outcome)) |
| ctl_untrained_is_still | before | **PASS** | untrained exploiter v zero script: holds 1000 v T44 1000, reaches 0 v 0; 0 of 1000 games differ (0 in outcome) |
| ctl_untrained_no_gain | before | **PASS** | untrained 0/1000 v best script 284/1000: gain -0.284, real False (must be False) |
| ctl_paired_starts | before | **PASS** | 1 start set(s), reference 5aeba7ab2b58 |
| tags_one_for_one | before | **PASS** | 0 games not one for one of 8000 |
| no_nonfinite_actions | before | **PASS** | 0 non-finite actions |
| tags_one_for_one_curve | curve | **PASS** | 0 games or actions wrong over the curve evaluations |
| no_nonfinite_actions_curve | curve | **PASS** | 0 games or actions wrong over the curve evaluations |
| ctl_reference_replay_final | final | **PASS** | guard_field v strike_straight: ok (holds 716 v T44 716, reaches 284 v 284; 0 of 1000 games differ (0 in outcome)); guard_field v strike_flank: ok (holds 808 v T44 808, reaches 192 v 192; 0 of 1000 games differ (0 in outcome)); guard_field v strike_high: ok (holds 734 v T44 734, reaches 266 v 266; 0 of 1000 games differ (0 in outcome)); guard_field v strike_low: ok (holds 739 v T44 739, reaches 261 v 261; 0 of 1000 games differ (0 in outcome)); guard_field v strike_sacrifice: ok (holds 862 v T44 862, reaches 138 v 138; 0 of 1000 games differ (0 in outcome)); guard_field v strike_converge: ok (holds 871 v T44 871, reaches 129 v 129; 0 of 1000 games differ (0 in outcome)) |
| ctl_paired_starts_final | final | **PASS** | 1 start set(s), reference 5aeba7ab2b58 |
| tags_one_for_one_final | final | **PASS** | 0 games not one for one of 8000 |
| no_nonfinite_actions_final | final | **PASS** | 0 non-finite actions |
| ctl_paired_starts_info | final | **PASS** | 1 start set(s), reference 5aeba7ab2b58 |
| tags_one_for_one_info | final | **PASS** | 0 games not one for one of 5000 |
| no_nonfinite_actions_info | final | **PASS** | 0 non-finite actions |

Recipe: **shaped Strike recipe**. Games that end inside a 0.6 s decision restart at the next decision boundary (LEAD CALL 21 Nov 2026): the ticks after the end are played, counted, never trained on.

Training opponent: guard_field (explicit, not the maximin pick); discount factor 0.99 per decision; trained on `configs/ste_l011/base.toml`, scored on `configs/ste_l011/base.toml`; learning curve and scores at the 120 s clock: curves at different clocks (L1.13 arm A at 30 s; T52 and arm B at 120 s) are not comparable update by update.

## Result (reach rate against guard_field, Wilson 95 %)

| Player | Count | Guards left in holds (mean) | Length median / p90 (s) |
|---|---|---|---|
| trained exploiter | 277/1000 = 0.277 (0.250-0.306) | 0.0 | 2.25 / 3.1 |
| untrained exploiter | 0/1000 = 0.000 (0.000-0.004) | | |
| best script (guard_field v strike_straight) | 284/1000 = 0.284 (0.257-0.313) | 0.0 | 2.0 / 2.9000000000000004 |

Learned: **True**. Gain over the best script: -0.007, real (intervals disjoint): **False**. Side: **weak (learned, below the script)**. Paired: exploiter won and script lost 6 games, the reverse 13.

Training: 88 updates, 553,648,128 game-steps (budget: 553,648,128 of 550,000,000 game-steps); median 431,307 game-steps/s at 16384 games, 6 drones per game, tier 1, NVIDIA GeForce RTX 5070 Ti Laptop GPU; stale-tick share 0.08784855857039943.

## INFO: the exploiter against every script of the other team

| Cell | Holds | Reaches | Games |
|---|---|---|---|
| guard_parked_centre v exploiter | 641 | 359 | 1000 |
| guard_parked_ring v exploiter | 624 | 376 | 1000 |
| guard_mark_edge v exploiter | 846 | 154 | 1000 |
| guard_mirror v exploiter | 824 | 176 | 1000 |
| guard_field v exploiter | 723 | 277 | 1000 |

## Videos

- videos/base_strike_game0_reach.gif: game 0, reach at 3.2 s (0.06 MB)
- videos/base_strike_game1_hold.gif: game 1, hold at 2.2 s (0.05 MB)
