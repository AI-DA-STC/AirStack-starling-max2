Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator; nothing here is a flight result.

# L0.12 Best-response test: base, exploiter strike

- Gate file sha256 `e16e77298833ca1a74b8154a175f88fe5b71f87c9559e565994db1a881060f5e`; reference sha256 `4bc5e011071adced368b2a0025fc47499839e0bbc8d8d650207bd12c3da0f8b5`; device cuda; 1000 evaluation games on T44's starts.

## Controls (read these first)

| Control | Phase | Status | Detail |
|---|---|---|---|
| ctl_reference_replay | before | **PASS** | guard_mark_edge v strike_straight: ok (holds 808 v T44 808, reaches 192 v 192; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_flank: ok (holds 887 v T44 887, reaches 113 v 113; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_high: ok (holds 850 v T44 850, reaches 150 v 150; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_low: ok (holds 844 v T44 844, reaches 156 v 156; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_sacrifice: ok (holds 960 v T44 960, reaches 40 v 40; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_converge: ok (holds 974 v T44 974, reaches 26 v 26; 0 of 1000 games differ (0 in outcome)) |
| ctl_untrained_is_first_skill | before | **PASS** | untrained exploiter v strike_straight (free + first drone skill): holds 808 v T44 808, reaches 192 v 192; 0 of 1000 games differ (0 in outcome) |
| ctl_paired_starts | before | **PASS** | 1 start set(s), reference 5aeba7ab2b58 |
| tags_one_for_one | before | **PASS** | 0 games not one for one of 8000 |
| no_nonfinite_actions | before | **PASS** | 0 non-finite actions |
| tags_one_for_one_curve | curve | **PASS** | 0 games or actions wrong over the curve evaluations |
| no_nonfinite_actions_curve | curve | **PASS** | 0 games or actions wrong over the curve evaluations |
| ctl_reference_replay_final | final | **PASS** | guard_mark_edge v strike_straight: ok (holds 808 v T44 808, reaches 192 v 192; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_flank: ok (holds 887 v T44 887, reaches 113 v 113; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_high: ok (holds 850 v T44 850, reaches 150 v 150; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_low: ok (holds 844 v T44 844, reaches 156 v 156; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_sacrifice: ok (holds 960 v T44 960, reaches 40 v 40; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_converge: ok (holds 974 v T44 974, reaches 26 v 26; 0 of 1000 games differ (0 in outcome)) |
| ctl_paired_starts_final | final | **PASS** | 1 start set(s), reference 5aeba7ab2b58 |
| tags_one_for_one_final | final | **PASS** | 0 games not one for one of 8000 |
| no_nonfinite_actions_final | final | **PASS** | 0 non-finite actions |
| ctl_paired_starts_info | final | **PASS** | 1 start set(s), reference 5aeba7ab2b58 |
| tags_one_for_one_info | final | **PASS** | 0 games not one for one of 5000 |
| no_nonfinite_actions_info | final | **PASS** | 0 non-finite actions |

Recipe: **T41 recipe**. Games that end inside a 0.6 s decision restart at the next decision boundary (LEAD CALL 21 Nov 2026): the ticks after the end are played, counted, never trained on.

Training opponent: guard_mark_edge (the maximin pick (g* / s*)); discount factor 0.99 per decision; trained on `configs/ste_l011/base.toml`, scored on `configs/ste_l011/base.toml`; learning curve and scores at the 120 s clock: curves at different clocks (L1.13 arm A at 30 s; T52 and arm B at 120 s) are not comparable update by update.

## Result (reach rate against guard_mark_edge, Wilson 95 %)

| Player | Count | Guards left in holds (mean) | Length median / p90 (s) |
|---|---|---|---|
| trained exploiter | 176/1000 = 0.176 (0.154-0.201) | 0.0 | 3.3000000000000003 / 3.85 |
| untrained exploiter | 192/1000 = 0.192 (0.169-0.218) | | |
| best script (guard_mark_edge v strike_straight) | 192/1000 = 0.192 (0.169-0.218) | 0.0 | 2.4000000000000004 / 2.9000000000000004 |

Learned: **False**. Gain over the best script: -0.016, real (intervals disjoint): **False**. Side: **INCONCLUSIVE: the exploiter did not learn (trained not above untrained)**. Paired: exploiter won and script lost 86 games, the reverse 102.

Training: 88 updates, 553,648,128 game-steps (budget: 553,648,128 of 550,000,000 game-steps); median 568,879 game-steps/s at 16384 games, 6 drones per game, tier 1, NVIDIA GeForce RTX 5090; stale-tick share 0.07470571091680817.

## INFO: the exploiter against every script of the other team

| Cell | Holds | Reaches | Games |
|---|---|---|---|
| guard_parked_centre v exploiter | 346 | 654 | 1000 |
| guard_parked_ring v exploiter | 341 | 659 | 1000 |
| guard_mark_edge v exploiter | 824 | 176 | 1000 |
| guard_mirror v exploiter | 815 | 185 | 1000 |
| guard_field v exploiter | 795 | 205 | 1000 |

## Videos

- videos/base_strike_game0_reach.gif: game 0, reach at 3.8 s (0.07 MB)
- videos/base_strike_game1_hold.gif: game 1, hold at 2.8 s (0.05 MB)
