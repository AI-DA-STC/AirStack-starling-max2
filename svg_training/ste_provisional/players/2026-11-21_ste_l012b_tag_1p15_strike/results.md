Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator; nothing here is a flight result.

# L0.12 Best-response test: tag_1p15, exploiter strike

- Gate file sha256 `ace5e18d77c214ca0a3e31d3613a20c3291e0f873ff6d1c5b90b8fec246fb592`; reference sha256 `49014000d07e8b52ae579deb325dad53d98c5020f533026dfbff778f306b2296`; device cuda; 1000 evaluation games on T44's starts.

## Controls (read these first)

| Control | Phase | Status | Detail |
|---|---|---|---|
| ctl_reference_replay | before | **PASS** | guard_field v strike_straight: ok (holds 645 v T44 645, reaches 355 v 355; 0 of 1000 games differ (0 in outcome)); guard_field v strike_flank: ok (holds 766 v T44 766, reaches 234 v 234; 0 of 1000 games differ (0 in outcome)); guard_field v strike_high: ok (holds 645 v T44 645, reaches 355 v 355; 0 of 1000 games differ (0 in outcome)); guard_field v strike_low: ok (holds 645 v T44 645, reaches 355 v 355; 0 of 1000 games differ (0 in outcome)); guard_field v strike_sacrifice: ok (holds 716 v T44 716, reaches 284 v 284; 0 of 1000 games differ (0 in outcome)); guard_field v strike_converge: ok (holds 768 v T44 768, reaches 232 v 232; 0 of 1000 games differ (0 in outcome)) |
| ctl_untrained_is_still | before | **PASS** | untrained exploiter v zero script: holds 1000 v T44 1000, reaches 0 v 0; 0 of 1000 games differ (0 in outcome) |
| ctl_untrained_no_gain | before | **PASS** | untrained 0/1000 v best script 355/1000: gain -0.355, real False (must be False) |
| ctl_paired_starts | before | **PASS** | 1 start set(s), reference 5aeba7ab2b58 |
| tags_one_for_one | before | **PASS** | 0 games not one for one of 8000 |
| no_nonfinite_actions | before | **PASS** | 0 non-finite actions |
| tags_one_for_one_curve | curve | **PASS** | 0 games or actions wrong over the curve evaluations |
| no_nonfinite_actions_curve | curve | **PASS** | 0 games or actions wrong over the curve evaluations |
| ctl_reference_replay_final | final | **PASS** | guard_field v strike_straight: ok (holds 645 v T44 645, reaches 355 v 355; 0 of 1000 games differ (0 in outcome)); guard_field v strike_flank: ok (holds 766 v T44 766, reaches 234 v 234; 0 of 1000 games differ (0 in outcome)); guard_field v strike_high: ok (holds 645 v T44 645, reaches 355 v 355; 0 of 1000 games differ (0 in outcome)); guard_field v strike_low: ok (holds 645 v T44 645, reaches 355 v 355; 0 of 1000 games differ (0 in outcome)); guard_field v strike_sacrifice: ok (holds 716 v T44 716, reaches 284 v 284; 0 of 1000 games differ (0 in outcome)); guard_field v strike_converge: ok (holds 768 v T44 768, reaches 232 v 232; 0 of 1000 games differ (0 in outcome)) |
| ctl_paired_starts_final | final | **PASS** | 1 start set(s), reference 5aeba7ab2b58 |
| tags_one_for_one_final | final | **PASS** | 0 games not one for one of 8000 |
| no_nonfinite_actions_final | final | **PASS** | 0 non-finite actions |
| ctl_paired_starts_info | final | **PASS** | 1 start set(s), reference 5aeba7ab2b58 |
| tags_one_for_one_info | final | **PASS** | 0 games not one for one of 5000 |
| no_nonfinite_actions_info | final | **PASS** | 0 non-finite actions |

Recipe: **shaped Strike recipe**. Games that end inside a 0.6 s decision restart at the next decision boundary (LEAD CALL 21 Nov 2026): the ticks after the end are played, counted, never trained on.

## Result (reach rate against guard_field, Wilson 95 %)

| Player | Count | Guards left in holds (mean) | Length median / p90 (s) |
|---|---|---|---|
| trained exploiter | 103/1000 = 0.103 (0.086-0.123) | 1.0468227424749164 | 120.0 / 120.0 |
| untrained exploiter | 0/1000 = 0.000 (0.000-0.004) | | |
| best script (guard_field v strike_straight) | 355/1000 = 0.355 (0.326-0.385) | 0.0 | 2.5500000000000003 / 2.9000000000000004 |

**Training stopped before its game-step budget** (cap reserve: 649 s left < final reserve 664 s at update 86): no side status is read from this run; `verdict` refuses it and it gets an ABORTED record (LEAD CALL 21 Nov 2026, QC N-2).

Training: 86 updates, 541,065,216 game-steps (cap reserve: 649 s left < final reserve 664 s at update 86); median 308,056 game-steps/s at 16384 games, 6 drones per game, tier 1, NVIDIA GeForce RTX 5070 Ti Laptop GPU; stale-tick share 0.0015189370443654611.

## INFO: the exploiter against every script of the other team

| Cell | Holds | Reaches | Games |
|---|---|---|---|
| guard_parked_centre v exploiter | 605 | 395 | 1000 |
| guard_parked_ring v exploiter | 623 | 377 | 1000 |
| guard_mark_edge v exploiter | 888 | 112 | 1000 |
| guard_mirror v exploiter | 931 | 69 | 1000 |
| guard_field v exploiter | 897 | 103 | 1000 |

## INFO: unchosen tags (L0.12b)

Unchosen tags (INFO, L0.12b; LEAD CALL 21 Nov 2026 (L0.12b Q4)). Pushed together (the main share): on the tag's tick the safety filter's correction closed the Guard-Strike pair faster than the players' own commands (relative correction along the pair line below -1e-3 m/s), so the tag would not have happened on this tick without the filter. Filter active at the tag (an upper bound): the filter corrected either drone of the pair on the tag's tick (velocity change > 1e-3 m/s), braking included. At the filter edge: the 3-D pair distance was at most the filter distance (1.10 m) plus the gate file's [run] tag_edge_margin_m. Shares are of the tags of the finished first games of each cell.

| Batch | Cell | Tags | Pushed together (share) | Filter active at the tag, upper bound (share) | At the filter edge (share) | Closest tag pair (m) |
|---|---|---|---|---|---|---|
| final | guard_field v exploiter | 1823 | 142 of 1823 (0.078) | 329 of 1823 (0.180) | 0 of 1823 (0.000) | 1.13 |
| final | guard_field v zero | 2934 | 422 of 2934 (0.144) | 440 of 2934 (0.150) | 0 of 2934 (0.000) | 1.13 |
| final | guard_field v strike_straight | 2645 | 0 of 2645 (0.000) | 2645 of 2645 (1.000) | 0 of 2645 (0.000) | 1.12 |
| final | guard_field v strike_flank | 2766 | 0 of 2766 (0.000) | 2766 of 2766 (1.000) | 0 of 2766 (0.000) | 1.12 |
| final | guard_field v strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 2645 | 0 of 2645 (0.000) | 2645 of 2645 (1.000) | 0 of 2645 (0.000) | 1.13 |
| final | guard_field v strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 2645 | 0 of 2645 (0.000) | 2645 of 2645 (1.000) | 0 of 2645 (0.000) | 1.13 |
| final | guard_field v strike_sacrifice | 2661 | 2 of 2661 (0.001) | 2660 of 2661 (1.000) | 0 of 2661 (0.000) | 1.12 |
| final | guard_field v strike_converge | 2768 | 88 of 2768 (0.032) | 2634 of 2768 (0.952) | 0 of 2768 (0.000) | 1.12 |
| INFO | guard_parked_centre v exploiter | 161 | 10 of 161 (0.062) | 11 of 161 (0.068) | 0 of 161 (0.000) | 1.15 |
| INFO | guard_parked_ring v exploiter | 243 | 17 of 243 (0.070) | 17 of 243 (0.070) | 0 of 243 (0.000) | 1.15 |
| INFO | guard_mark_edge v exploiter | 1793 | 208 of 1793 (0.116) | 465 of 1793 (0.259) | 0 of 1793 (0.000) | 1.13 |
| INFO | guard_mirror v exploiter | 1993 | 223 of 1993 (0.112) | 424 of 1993 (0.213) | 0 of 1993 (0.000) | 1.14 |
| INFO | guard_field v exploiter | 1823 | 142 of 1823 (0.078) | 329 of 1823 (0.180) | 0 of 1823 (0.000) | 1.13 |

## Videos

- videos/tag_1p15_strike_game0_hold.gif: game 0, hold at 120.0 s (1.02 MB)
- videos/tag_1p15_strike_game1_hold.gif: game 1, hold at 120.0 s (1.06 MB)
