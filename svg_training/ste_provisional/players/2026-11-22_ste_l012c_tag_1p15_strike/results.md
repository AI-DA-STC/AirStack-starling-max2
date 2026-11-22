Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator; nothing here is a flight result.

# L0.12 Best-response test: tag_1p15, exploiter strike

- Gate file sha256 `362b9126cab72a20577bd12508d3a8f2f9008a75847ea6c1f2f79d6f340dfee9`; reference sha256 `49014000d07e8b52ae579deb325dad53d98c5020f533026dfbff778f306b2296`; device cuda; 1000 evaluation games on T44's starts.

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
| trained exploiter | 134/1000 = 0.134 (0.114-0.157) | 1.008083140877598 | 120.0 / 120.0 |
| untrained exploiter | 0/1000 = 0.000 (0.000-0.004) | | |
| best script (guard_field v strike_straight) | 355/1000 = 0.355 (0.326-0.385) | 0.0 | 2.5500000000000003 / 2.9000000000000004 |

Learned: **True**. Gain over the best script: -0.221, real (intervals disjoint): **False**. Side: **weak (learned, below the script)**. Paired: exploiter won and script lost 1 games, the reverse 222.

Training: 438 updates, 2,755,657,728 game-steps (budget: 2,755,657,728 of 2,750,000,000 game-steps); median 320,446 game-steps/s at 16384 games, 6 drones per game, tier 1, NVIDIA GeForce RTX 5070 Ti Laptop GPU; stale-tick share 0.0012903228016567375.

## INFO: the exploiter against every script of the other team

| Cell | Holds | Reaches | Games |
|---|---|---|---|
| guard_parked_centre v exploiter | 448 | 552 | 1000 |
| guard_parked_ring v exploiter | 465 | 535 | 1000 |
| guard_mark_edge v exploiter | 761 | 239 | 1000 |
| guard_mirror v exploiter | 928 | 72 | 1000 |
| guard_field v exploiter | 866 | 134 | 1000 |

## INFO: unchosen tags (L0.12b)

Unchosen tags (INFO, L0.12b; LEAD CALL 21 Nov 2026 (L0.12b Q4)). Pushed together (the main share): on the tag's tick the safety filter's correction closed the Guard-Strike pair faster than the players' own commands (relative correction along the pair line below -1e-3 m/s), so the tag would not have happened on this tick without the filter. Filter active at the tag (an upper bound): the filter corrected either drone of the pair on the tag's tick (velocity change > 1e-3 m/s), braking included. At the filter edge: the 3-D pair distance was at most the filter distance (1.10 m) plus the gate file's [run] tag_edge_margin_m. Shares are of the tags of the finished first games of each cell.

| Batch | Cell | Tags | Pushed together (share) | Filter active at the tag, upper bound (share) | At the filter edge (share) | Closest tag pair (m) |
|---|---|---|---|---|---|---|
| final | guard_field v exploiter | 1826 | 194 of 1826 (0.106) | 320 of 1826 (0.175) | 0 of 1826 (0.000) | 1.13 |
| final | guard_field v zero | 2934 | 422 of 2934 (0.144) | 440 of 2934 (0.150) | 0 of 2934 (0.000) | 1.13 |
| final | guard_field v strike_straight | 2645 | 0 of 2645 (0.000) | 2645 of 2645 (1.000) | 0 of 2645 (0.000) | 1.12 |
| final | guard_field v strike_flank | 2766 | 0 of 2766 (0.000) | 2766 of 2766 (1.000) | 0 of 2766 (0.000) | 1.12 |
| final | guard_field v strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 2645 | 0 of 2645 (0.000) | 2645 of 2645 (1.000) | 0 of 2645 (0.000) | 1.13 |
| final | guard_field v strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 2645 | 0 of 2645 (0.000) | 2645 of 2645 (1.000) | 0 of 2645 (0.000) | 1.13 |
| final | guard_field v strike_sacrifice | 2661 | 2 of 2661 (0.001) | 2660 of 2661 (1.000) | 0 of 2661 (0.000) | 1.12 |
| final | guard_field v strike_converge | 2768 | 88 of 2768 (0.032) | 2634 of 2768 (0.952) | 0 of 2768 (0.000) | 1.12 |
| INFO | guard_parked_centre v exploiter | 185 | 4 of 185 (0.022) | 11 of 185 (0.059) | 0 of 185 (0.000) | 1.14 |
| INFO | guard_parked_ring v exploiter | 333 | 7 of 333 (0.021) | 17 of 333 (0.051) | 0 of 333 (0.000) | 1.14 |
| INFO | guard_mark_edge v exploiter | 1795 | 289 of 1795 (0.161) | 467 of 1795 (0.260) | 0 of 1795 (0.000) | 1.13 |
| INFO | guard_mirror v exploiter | 2130 | 201 of 2130 (0.094) | 512 of 2130 (0.240) | 0 of 2130 (0.000) | 1.13 |
| INFO | guard_field v exploiter | 1826 | 194 of 1826 (0.106) | 320 of 1826 (0.175) | 0 of 1826 (0.000) | 1.13 |

## Videos

- videos/tag_1p15_strike_game0_hold.gif: game 0, hold at 120.0 s (1.04 MB)
- videos/tag_1p15_strike_game1_hold.gif: game 1, hold at 120.0 s (0.99 MB)
