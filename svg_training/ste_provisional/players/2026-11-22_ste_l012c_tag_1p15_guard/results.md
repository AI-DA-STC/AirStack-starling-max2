Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator; nothing here is a flight result.

# L0.12 Best-response test: tag_1p15, exploiter guard

- Gate file sha256 `b52dcc23580640c7a9d5a99f95e523eaa9c21b00125e3ff56172f6a5210d4c81`; reference sha256 `49014000d07e8b52ae579deb325dad53d98c5020f533026dfbff778f306b2296`; device cuda; 1000 evaluation games on T44's starts.

## Controls (read these first)

| Control | Phase | Status | Detail |
|---|---|---|---|
| ctl_reference_replay | before | **PASS** | guard_parked_centre v strike_straight: ok (holds 101 v T44 101, reaches 899 v 899; 0 of 1000 games differ (0 in outcome)); guard_parked_ring v strike_straight: ok (holds 127 v T44 127, reaches 873 v 873; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_straight: ok (holds 422 v T44 422, reaches 578 v 578; 0 of 1000 games differ (0 in outcome)); guard_mirror v strike_straight: ok (holds 425 v T44 425, reaches 575 v 575; 0 of 1000 games differ (0 in outcome)); guard_field v strike_straight: ok (holds 645 v T44 645, reaches 355 v 355; 0 of 1000 games differ (0 in outcome)) |
| ctl_untrained_is_still | before | **PASS** | untrained exploiter v zero script: holds 101 v T44 101, reaches 899 v 899; 0 of 1000 games differ (0 in outcome) |
| ctl_untrained_no_gain | before | **PASS** | untrained 101/1000 v best script 645/1000: gain -0.544, real False (must be False) |
| ctl_paired_starts | before | **PASS** | 1 start set(s), reference 5aeba7ab2b58 |
| tags_one_for_one | before | **PASS** | 0 games not one for one of 7000 |
| no_nonfinite_actions | before | **PASS** | 0 non-finite actions |
| tags_one_for_one_curve | curve | **PASS** | 0 games or actions wrong over the curve evaluations |
| no_nonfinite_actions_curve | curve | **PASS** | 0 games or actions wrong over the curve evaluations |
| ctl_reference_replay_final | final | **PASS** | guard_parked_centre v strike_straight: ok (holds 101 v T44 101, reaches 899 v 899; 0 of 1000 games differ (0 in outcome)); guard_parked_ring v strike_straight: ok (holds 127 v T44 127, reaches 873 v 873; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_straight: ok (holds 422 v T44 422, reaches 578 v 578; 0 of 1000 games differ (0 in outcome)); guard_mirror v strike_straight: ok (holds 425 v T44 425, reaches 575 v 575; 0 of 1000 games differ (0 in outcome)); guard_field v strike_straight: ok (holds 645 v T44 645, reaches 355 v 355; 0 of 1000 games differ (0 in outcome)) |
| ctl_paired_starts_final | final | **PASS** | 1 start set(s), reference 5aeba7ab2b58 |
| tags_one_for_one_final | final | **PASS** | 0 games not one for one of 7000 |
| no_nonfinite_actions_final | final | **PASS** | 0 non-finite actions |
| ctl_paired_starts_info | final | **PASS** | 1 start set(s), reference 5aeba7ab2b58 |
| tags_one_for_one_info | final | **PASS** | 0 games not one for one of 6000 |
| no_nonfinite_actions_info | final | **PASS** | 0 non-finite actions |

Recipe: **T41 recipe**. Games that end inside a 0.6 s decision restart at the next decision boundary (LEAD CALL 21 Nov 2026): the ticks after the end are played, counted, never trained on.

## Result (hold rate against strike_straight, Wilson 95 %)

| Player | Count | Guards left in holds (mean) | Length median / p90 (s) |
|---|---|---|---|
| trained exploiter | 572/1000 = 0.572 (0.541-0.602) | 0.0 | 2.9000000000000004 / 3.0500000000000003 |
| untrained exploiter | 101/1000 = 0.101 (0.084-0.121) | | |
| best script (guard_field v strike_straight) | 645/1000 = 0.645 (0.615-0.674) | 0.0 | 2.5500000000000003 / 2.9000000000000004 |

Learned: **True**. Gain over the best script: -0.073, real (intervals disjoint): **False**. Side: **weak (learned, below the script)**. Paired: exploiter won and script lost 45 games, the reverse 118.

Training: 263 updates, 1,654,652,928 game-steps (budget: 1,654,652,928 of 1,650,000,000 game-steps); median 306,016 game-steps/s at 16384 games, 6 drones per game, tier 1, NVIDIA GeForce RTX 5070 Ti Laptop GPU; stale-tick share 0.066916919026538.

## INFO: the exploiter against every script of the other team

| Cell | Holds | Reaches | Games |
|---|---|---|---|
| exploiter v strike_straight | 572 | 428 | 1000 |
| exploiter v strike_flank | 818 | 182 | 1000 |
| exploiter v strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 497 | 503 | 1000 |
| exploiter v strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 485 | 515 | 1000 |
| exploiter v strike_sacrifice | 371 | 629 | 1000 |
| exploiter v strike_converge | 160 | 840 | 1000 |

## INFO: unchosen tags (L0.12b)

Unchosen tags (INFO, L0.12b; LEAD CALL 21 Nov 2026 (L0.12b Q4)). Pushed together (the main share): on the tag's tick the safety filter's correction closed the Guard-Strike pair faster than the players' own commands (relative correction along the pair line below -1e-3 m/s), so the tag would not have happened on this tick without the filter. Filter active at the tag (an upper bound): the filter corrected either drone of the pair on the tag's tick (velocity change > 1e-3 m/s), braking included. At the filter edge: the 3-D pair distance was at most the filter distance (1.10 m) plus the gate file's [run] tag_edge_margin_m. Shares are of the tags of the finished first games of each cell.

| Batch | Cell | Tags | Pushed together (share) | Filter active at the tag, upper bound (share) | At the filter edge (share) | Closest tag pair (m) |
|---|---|---|---|---|---|---|
| final | exploiter v strike_straight | 2379 | 0 of 2379 (0.000) | 2375 of 2379 (0.998) | 0 of 2379 (0.000) | 1.12 |
| final | zero v strike_straight | 1758 | 0 of 1758 (0.000) | 1758 of 1758 (1.000) | 0 of 1758 (0.000) | 1.13 |
| final | guard_parked_centre v strike_straight | 1758 | 0 of 1758 (0.000) | 1758 of 1758 (1.000) | 0 of 1758 (0.000) | 1.13 |
| final | guard_parked_ring v strike_straight | 1838 | 0 of 1838 (0.000) | 1838 of 1838 (1.000) | 0 of 1838 (0.000) | 1.13 |
| final | guard_mark_edge v strike_straight | 2235 | 28 of 2235 (0.013) | 2227 of 2235 (0.996) | 0 of 2235 (0.000) | 1.11 |
| final | guard_mirror v strike_straight | 2245 | 21 of 2245 (0.009) | 2234 of 2245 (0.995) | 0 of 2245 (0.000) | 1.12 |
| final | guard_field v strike_straight | 2645 | 0 of 2645 (0.000) | 2645 of 2645 (1.000) | 0 of 2645 (0.000) | 1.12 |
| INFO | exploiter v strike_straight | 2379 | 0 of 2379 (0.000) | 2375 of 2379 (0.998) | 0 of 2379 (0.000) | 1.12 |
| INFO | exploiter v strike_flank | 2810 | 0 of 2810 (0.000) | 2810 of 2810 (1.000) | 0 of 2810 (0.000) | 1.13 |
| INFO | exploiter v strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 2263 | 0 of 2263 (0.000) | 2257 of 2263 (0.997) | 0 of 2263 (0.000) | 1.13 |
| INFO | exploiter v strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 2207 | 1 of 2207 (0.000) | 2197 of 2207 (0.995) | 0 of 2207 (0.000) | 1.13 |
| INFO | exploiter v strike_sacrifice | 2111 | 1 of 2111 (0.000) | 2101 of 2111 (0.995) | 0 of 2111 (0.000) | 1.13 |
| INFO | exploiter v strike_converge | 1659 | 9 of 1659 (0.005) | 1450 of 1659 (0.874) | 0 of 1659 (0.000) | 1.13 |

## Videos

- videos/tag_1p15_guard_game0_reach.gif: game 0, reach at 2.9 s (0.06 MB)
- videos/tag_1p15_guard_game2_hold.gif: game 2, hold at 2.6 s (0.05 MB)
