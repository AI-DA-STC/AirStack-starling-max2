Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator; nothing here is a flight result.

# L1.10: L1.10's Guard team (trained with the tag drawn in 1.5-1.7 m and the estimate error) scored against every Strike script at the fixed 1.6 m tag, with and without the error (INFO)

## Controls (read these first; any control not PASS: no number is reported)

| Control | Status | Detail |
|---|---|---|
| own_replay | **PASS** | EQUAL {'outcome': 0, 'end_step': 0, 'tags': 0, 'strikes_left': 0, 'start_pos_m': 0, 'closest_3d_m': 0}; trained holds 921/1000 (record 921); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_base_err__strike_straight | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_base_err__strike_flank | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_base_err__strike_high | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_base_err__strike_low | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_base_err__strike_sacrifice | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_base_err__strike_converge | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| scripts_base__strike_straight | **PASS** | guard_parked_centre v strike_straight: ok (holds 534 v T44 534, reaches 466 v 466; 0 of 1000 games differ (0 in outcome)); guard_parked_ring v strike_straight: ok (holds 523 v T44 523, reaches 477 v 477; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_straight: ok (holds 808 v T44 808, reaches 192 v 192; 0 of 1000 games differ (0 in outcome)); guard_mirror v strike_straight: ok (holds 796 v T44 796, reaches 204 v 204; 0 of 1000 games differ (0 in outcome)); guard_field v strike_straight: ok (holds 716 v T44 716, reaches 284 v 284; 0 of 1000 games differ (0 in outcome)); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS; the player's cell v its own training opponent EQUALS own_replay's trained cell game for game {'outcome': 0, 'end_step': 0, 'tags': 0, 'strikes_left': 0, 'start_pos_m': 0, 'closest_3d_m': 0} |
| scripts_base__strike_flank | **PASS** | guard_parked_centre v strike_flank: ok (holds 450 v T44 450, reaches 550 v 550; 0 of 1000 games differ (0 in outcome)); guard_parked_ring v strike_flank: ok (holds 477 v T44 477, reaches 523 v 523; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_flank: ok (holds 887 v T44 887, reaches 113 v 113; 0 of 1000 games differ (0 in outcome)); guard_mirror v strike_flank: ok (holds 864 v T44 864, reaches 136 v 136; 0 of 1000 games differ (0 in outcome)); guard_field v strike_flank: ok (holds 808 v T44 808, reaches 192 v 192; 0 of 1000 games differ (0 in outcome)); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| scripts_base__strike_high | **PASS** | guard_parked_centre v strike_high: ok (holds 466 v T44 466, reaches 534 v 534; 0 of 1000 games differ (0 in outcome)); guard_parked_ring v strike_high: ok (holds 454 v T44 454, reaches 546 v 546; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_high: ok (holds 850 v T44 850, reaches 150 v 150; 0 of 1000 games differ (0 in outcome)); guard_mirror v strike_high: ok (holds 848 v T44 848, reaches 152 v 152; 0 of 1000 games differ (0 in outcome)); guard_field v strike_high: ok (holds 734 v T44 734, reaches 266 v 266; 0 of 1000 games differ (0 in outcome)); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| scripts_base__strike_low | **PASS** | guard_parked_centre v strike_low: ok (holds 430 v T44 430, reaches 570 v 570; 0 of 1000 games differ (0 in outcome)); guard_parked_ring v strike_low: ok (holds 424 v T44 424, reaches 576 v 576; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_low: ok (holds 844 v T44 844, reaches 156 v 156; 0 of 1000 games differ (0 in outcome)); guard_mirror v strike_low: ok (holds 847 v T44 847, reaches 153 v 153; 0 of 1000 games differ (0 in outcome)); guard_field v strike_low: ok (holds 739 v T44 739, reaches 261 v 261; 0 of 1000 games differ (0 in outcome)); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| scripts_base__strike_sacrifice | **PASS** | guard_parked_centre v strike_sacrifice: ok (holds 525 v T44 525, reaches 475 v 475; 0 of 1000 games differ (0 in outcome)); guard_parked_ring v strike_sacrifice: ok (holds 503 v T44 503, reaches 497 v 497; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_sacrifice: ok (holds 960 v T44 960, reaches 40 v 40; 0 of 1000 games differ (0 in outcome)); guard_mirror v strike_sacrifice: ok (holds 927 v T44 927, reaches 73 v 73; 0 of 1000 games differ (0 in outcome)); guard_field v strike_sacrifice: ok (holds 862 v T44 862, reaches 138 v 138; 0 of 1000 games differ (0 in outcome)); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| scripts_base__strike_converge | **PASS** | guard_parked_centre v strike_converge: ok (holds 986 v T44 986, reaches 14 v 14; 0 of 1000 games differ (0 in outcome)); guard_parked_ring v strike_converge: ok (holds 983 v T44 983, reaches 17 v 17; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_converge: ok (holds 974 v T44 974, reaches 26 v 26; 0 of 1000 games differ (0 in outcome)); guard_mirror v strike_converge: ok (holds 968 v T44 968, reaches 32 v 32; 0 of 1000 games differ (0 in outcome)); guard_field v strike_converge: ok (holds 871 v T44 871, reaches 129 v 129; 0 of 1000 games differ (0 in outcome)); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_tagdraw_err__strike_straight | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_tagdraw_err__strike_flank | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_tagdraw_err__strike_high | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_tagdraw_err__strike_low | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_tagdraw_err__strike_sacrifice | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_tagdraw_err__strike_converge | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |

## base_err: `configs/ste_l1/base_err_nominal.toml` (3v3, tag 1.6 m fixed, 120 s clock, nominal estimate error (main); response delay 0.1482 s; no screen reference for this game: script cells reported, not compared (INFO); one trained network, one start set; observed in the training simulator), worst cell first

| Opponent | Player's holds (Wilson 95 %) | Best script, same starts | Paired: player only / script only / both / neither | Player's games: reach / all Strike tagged / clock / other hold / unfinished | Median length (s) |
|---|---|---|---|---|---|
| strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 903/1000 (0.883-0.920) | guard_mark_edge 857/1000 (0.834-0.877) | 132 / 86 / 771 / 11 | 97 / 903 / 0 / 0 / 0 | 3.2 |
| strike_converge | 920/1000 (0.902-0.935) | guard_parked_ring 983/1000 (0.973-0.989) | 13 / 76 / 907 / 4 | 80 / 920 / 0 / 0 / 0 | 7.9 |
| strike_sacrifice | 922/1000 (0.904-0.937) | guard_mark_edge 961/1000 (0.947-0.971) | 30 / 69 / 892 / 9 | 78 / 922 / 0 / 0 / 0 | 3.8 |
| strike_straight | 928/1000 (0.910-0.942) | guard_mirror 811/1000 (0.786-0.834) | 157 / 40 / 771 / 32 | 72 / 928 / 0 / 0 / 0 | 2.5 |
| strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 936/1000 (0.919-0.950) | guard_mark_edge 850/1000 (0.827-0.871) | 142 / 56 / 794 / 8 | 64 / 936 / 0 / 0 / 0 | 3.0 |
| strike_flank | 962/1000 (0.948-0.972) | guard_mark_edge 888/1000 (0.867-0.906) | 108 / 34 / 854 / 4 | 38 / 962 / 0 / 0 / 0 | 3.0 |

Every cell of the batch (holds of the player's team; tag distance and closest approach over finished games; closest approach of any pair = per game min(tag distances, closest approach of pairs never tagged), as the tagged pair is removed on its tick):

| Cell (Guard v Strike) | Wins (Wilson 95 %) | Ends: reach / all Strike tagged / clock / other hold / unfinished | Tags | Tag distance min / median (m) | Closest approach, any pair, min / median (m) | Closest approach of pairs never tagged, min / median (m) |
|---|---|---|---|---|---|---|
| trained v strike_low | 903/1000 (0.883-0.920) | 97 / 903 / 0 / 0 / 0 | 2899 | 1.562 / 1.587 | 1.562 / 1.579 | 1.600 / 1.606 |
| guard_parked_centre v strike_low | 431/1000 (0.401-0.462) | 569 / 431 / 0 / 0 / 0 | 2416 | 1.576 / 1.589 | 1.576 / 1.584 | 1.600 / 1.606 |
| guard_parked_ring v strike_low | 427/1000 (0.397-0.458) | 573 / 427 / 0 / 0 / 0 | 2412 | 1.576 / 1.589 | 1.576 / 1.583 | 1.600 / 1.606 |
| guard_mark_edge v strike_low | 857/1000 (0.834-0.877) | 143 / 857 / 0 / 0 / 0 | 2851 | 1.559 / 1.585 | 1.559 / 1.575 | 1.600 / 1.607 |
| guard_mirror v strike_low | 857/1000 (0.834-0.877) | 143 / 857 / 0 / 0 / 0 | 2852 | 1.558 / 1.584 | 1.558 / 1.575 | 1.600 / 1.606 |
| guard_field v strike_low | 741/1000 (0.713-0.767) | 259 / 741 / 0 / 0 / 0 | 2741 | 1.559 / 1.582 | 1.559 / 1.572 | 1.600 / 1.608 |
| trained v strike_converge | 920/1000 (0.902-0.935) | 80 / 920 / 0 / 0 / 0 | 2918 | 1.559 / 1.591 | 1.559 / 1.583 | 1.600 / 1.603 |
| guard_parked_centre v strike_converge | 981/1000 (0.971-0.988) | 19 / 981 / 0 / 0 / 0 | 2981 | 1.574 / 1.590 | 1.574 / 1.584 | 1.600 / 1.604 |
| guard_parked_ring v strike_converge | 983/1000 (0.973-0.989) | 17 / 983 / 0 / 0 / 0 | 2983 | 1.573 / 1.590 | 1.573 / 1.585 | 1.600 / 1.604 |
| guard_mark_edge v strike_converge | 975/1000 (0.963-0.983) | 25 / 975 / 0 / 0 / 0 | 2974 | 1.549 / 1.590 | 1.549 / 1.582 | 1.600 / 1.604 |
| guard_mirror v strike_converge | 968/1000 (0.955-0.977) | 32 / 968 / 0 / 0 / 0 | 2968 | 1.552 / 1.590 | 1.552 / 1.582 | 1.600 / 1.604 |
| guard_field v strike_converge | 871/1000 (0.849-0.890) | 129 / 871 / 0 / 0 / 0 | 2871 | 1.552 / 1.590 | 1.552 / 1.583 | 1.600 / 1.604 |
| trained v strike_sacrifice | 922/1000 (0.904-0.937) | 78 / 922 / 0 / 0 / 0 | 2906 | 1.559 / 1.587 | 1.559 / 1.579 | 1.600 / 1.605 |
| guard_parked_centre v strike_sacrifice | 520/1000 (0.489-0.551) | 480 / 520 / 0 / 0 / 0 | 2520 | 1.572 / 1.588 | 1.572 / 1.582 | 1.600 / 1.606 |
| guard_parked_ring v strike_sacrifice | 508/1000 (0.477-0.539) | 492 / 508 / 0 / 0 / 0 | 2508 | 1.572 / 1.589 | 1.572 / 1.583 | 1.600 / 1.606 |
| guard_mark_edge v strike_sacrifice | 961/1000 (0.947-0.971) | 39 / 961 / 0 / 0 / 0 | 2959 | 1.553 / 1.585 | 1.553 / 1.574 | 1.600 / 1.606 |
| guard_mirror v strike_sacrifice | 929/1000 (0.911-0.943) | 71 / 929 / 0 / 0 / 0 | 2927 | 1.553 / 1.586 | 1.553 / 1.575 | 1.600 / 1.606 |
| guard_field v strike_sacrifice | 869/1000 (0.847-0.889) | 131 / 869 / 0 / 0 / 0 | 2864 | 1.552 / 1.584 | 1.552 / 1.575 | 1.600 / 1.607 |
| trained v strike_straight | 928/1000 (0.910-0.942) | 72 / 928 / 0 / 0 / 0 | 2927 | 1.558 / 1.586 | 1.558 / 1.579 | 1.600 / 1.606 |
| guard_parked_centre v strike_straight | 541/1000 (0.510-0.572) | 459 / 541 / 0 / 0 / 0 | 2535 | 1.572 / 1.588 | 1.572 / 1.582 | 1.600 / 1.606 |
| guard_parked_ring v strike_straight | 529/1000 (0.498-0.560) | 471 / 529 / 0 / 0 / 0 | 2523 | 1.573 / 1.588 | 1.573 / 1.582 | 1.600 / 1.606 |
| guard_mark_edge v strike_straight | 808/1000 (0.782-0.831) | 192 / 808 / 0 / 0 / 0 | 2806 | 1.552 / 1.584 | 1.552 / 1.575 | 1.600 / 1.607 |
| guard_mirror v strike_straight | 811/1000 (0.786-0.834) | 189 / 811 / 0 / 0 / 0 | 2809 | 1.553 / 1.585 | 1.553 / 1.576 | 1.600 / 1.607 |
| guard_field v strike_straight | 722/1000 (0.693-0.749) | 278 / 722 / 0 / 0 / 0 | 2722 | 1.553 / 1.582 | 1.553 / 1.573 | 1.600 / 1.608 |
| trained v strike_high | 936/1000 (0.919-0.950) | 64 / 936 / 0 / 0 / 0 | 2933 | 1.562 / 1.586 | 1.562 / 1.578 | 1.600 / 1.606 |
| guard_parked_centre v strike_high | 460/1000 (0.429-0.491) | 540 / 460 / 0 / 0 / 0 | 2449 | 1.576 / 1.589 | 1.576 / 1.583 | 1.600 / 1.606 |
| guard_parked_ring v strike_high | 456/1000 (0.425-0.487) | 544 / 456 / 0 / 0 / 0 | 2445 | 1.575 / 1.589 | 1.575 / 1.583 | 1.600 / 1.606 |
| guard_mark_edge v strike_high | 850/1000 (0.827-0.871) | 150 / 850 / 0 / 0 / 0 | 2847 | 1.557 / 1.585 | 1.557 / 1.575 | 1.600 / 1.607 |
| guard_mirror v strike_high | 849/1000 (0.825-0.870) | 151 / 849 / 0 / 0 / 0 | 2846 | 1.559 / 1.584 | 1.559 / 1.575 | 1.600 / 1.607 |
| guard_field v strike_high | 738/1000 (0.710-0.764) | 262 / 738 / 0 / 0 / 0 | 2738 | 1.559 / 1.582 | 1.559 / 1.572 | 1.600 / 1.608 |
| trained v strike_flank | 962/1000 (0.948-0.972) | 38 / 962 / 0 / 0 / 0 | 2962 | 1.564 / 1.589 | 1.564 / 1.582 | 1.600 / 1.605 |
| guard_parked_centre v strike_flank | 470/1000 (0.439-0.501) | 530 / 470 / 0 / 0 / 0 | 2457 | 1.575 / 1.590 | 1.575 / 1.585 | 1.600 / 1.605 |
| guard_parked_ring v strike_flank | 479/1000 (0.448-0.510) | 521 / 479 / 0 / 0 / 0 | 2465 | 1.574 / 1.590 | 1.574 / 1.585 | 1.600 / 1.605 |
| guard_mark_edge v strike_flank | 888/1000 (0.867-0.906) | 112 / 888 / 0 / 0 / 0 | 2887 | 1.556 / 1.587 | 1.556 / 1.578 | 1.600 / 1.606 |
| guard_mirror v strike_flank | 865/1000 (0.842-0.885) | 135 / 865 / 0 / 0 / 0 | 2862 | 1.558 / 1.587 | 1.558 / 1.579 | 1.600 / 1.606 |
| guard_field v strike_flank | 811/1000 (0.786-0.834) | 189 / 811 / 0 / 0 / 0 | 2811 | 1.554 / 1.584 | 1.554 / 1.575 | 1.600 / 1.607 |

Reading:

- The L1.10 Guard team (tag drawn 1.5-1.7 m, estimate error) holds 903 of 1,000 (0.883-0.920) against strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) (best Guard script guard_mark_edge: 857).
- The L1.10 Guard team (tag drawn 1.5-1.7 m, estimate error) holds 920 of 1,000 (0.902-0.935) against strike_converge (best Guard script guard_parked_ring: 983).
- The L1.10 Guard team (tag drawn 1.5-1.7 m, estimate error) holds 922 of 1,000 (0.904-0.937) against strike_sacrifice (best Guard script guard_mark_edge: 961).
- The L1.10 Guard team (tag drawn 1.5-1.7 m, estimate error) holds 928 of 1,000 (0.910-0.942) against strike_straight (best Guard script guard_mirror: 811).
- The L1.10 Guard team (tag drawn 1.5-1.7 m, estimate error) holds 936 of 1,000 (0.919-0.950) against strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) (best Guard script guard_mark_edge: 850).
- The L1.10 Guard team (tag drawn 1.5-1.7 m, estimate error) holds 962 of 1,000 (0.948-0.972) against strike_flank (best Guard script guard_mark_edge: 888).

## base: `configs/ste_l011/base.toml` (3v3, tag 1.6 m fixed, 120 s clock, no estimate error (INFO; T46's game); response delay 0.1482 s; one trained network, one start set; observed in the training simulator), worst cell first

| Opponent | Player's holds (Wilson 95 %) | Best script, same starts | Paired: player only / script only / both / neither | Player's games: reach / all Strike tagged / clock / other hold / unfinished | Median length (s) |
|---|---|---|---|---|---|
| strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 896/1000 (0.876-0.913) | guard_mirror 847/1000 (0.823-0.868) | 139 / 90 / 757 / 14 | 104 / 896 / 0 / 0 / 0 | 3.2 |
| strike_straight | 921/1000 (0.903-0.936) | guard_mark_edge 808/1000 (0.782-0.831) | 154 / 41 / 767 / 38 | 79 / 921 / 0 / 0 / 0 | 2.5 |
| strike_converge | 928/1000 (0.910-0.942) | guard_parked_centre 986/1000 (0.977-0.992) | 11 / 69 / 917 / 3 | 72 / 928 / 0 / 0 / 0 | 7.9 |
| strike_sacrifice | 930/1000 (0.912-0.944) | guard_mark_edge 960/1000 (0.946-0.970) | 32 / 62 / 898 / 8 | 70 / 930 / 0 / 0 / 0 | 3.8 |
| strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 938/1000 (0.921-0.951) | guard_mark_edge 850/1000 (0.827-0.871) | 141 / 53 / 797 / 9 | 62 / 938 / 0 / 0 / 0 | 3.0 |
| strike_flank | 960/1000 (0.946-0.970) | guard_mark_edge 887/1000 (0.866-0.905) | 111 / 38 / 849 / 2 | 40 / 960 / 0 / 0 / 0 | 3.0 |

Every cell of the batch (holds of the player's team; tag distance and closest approach over finished games; closest approach of any pair = per game min(tag distances, closest approach of pairs never tagged), as the tagged pair is removed on its tick):

| Cell (Guard v Strike) | Wins (Wilson 95 %) | Ends: reach / all Strike tagged / clock / other hold / unfinished | Tags | Tag distance min / median (m) | Closest approach, any pair, min / median (m) | Closest approach of pairs never tagged, min / median (m) |
|---|---|---|---|---|---|---|
| trained v strike_low | 896/1000 (0.876-0.913) | 104 / 896 / 0 / 0 / 0 | 2892 | 1.563 / 1.587 | 1.563 / 1.579 | 1.600 / 1.605 |
| guard_parked_centre v strike_low | 430/1000 (0.400-0.461) | 570 / 430 / 0 / 0 / 0 | 2417 | 1.577 / 1.589 | 1.577 / 1.584 | 1.600 / 1.606 |
| guard_parked_ring v strike_low | 424/1000 (0.394-0.455) | 576 / 424 / 0 / 0 / 0 | 2411 | 1.576 / 1.590 | 1.576 / 1.584 | 1.600 / 1.606 |
| guard_mark_edge v strike_low | 844/1000 (0.820-0.865) | 156 / 844 / 0 / 0 / 0 | 2840 | 1.559 / 1.585 | 1.559 / 1.575 | 1.600 / 1.607 |
| guard_mirror v strike_low | 847/1000 (0.823-0.868) | 153 / 847 / 0 / 0 / 0 | 2843 | 1.559 / 1.585 | 1.559 / 1.575 | 1.600 / 1.607 |
| guard_field v strike_low | 739/1000 (0.711-0.765) | 261 / 739 / 0 / 0 / 0 | 2739 | 1.560 / 1.582 | 1.560 / 1.572 | 1.600 / 1.608 |
| trained v strike_straight | 921/1000 (0.903-0.936) | 79 / 921 / 0 / 0 / 0 | 2921 | 1.559 / 1.587 | 1.559 / 1.578 | 1.600 / 1.606 |
| guard_parked_centre v strike_straight | 534/1000 (0.503-0.565) | 466 / 534 / 0 / 0 / 0 | 2529 | 1.573 / 1.588 | 1.573 / 1.582 | 1.600 / 1.606 |
| guard_parked_ring v strike_straight | 523/1000 (0.492-0.554) | 477 / 523 / 0 / 0 / 0 | 2518 | 1.574 / 1.588 | 1.574 / 1.582 | 1.600 / 1.606 |
| guard_mark_edge v strike_straight | 808/1000 (0.782-0.831) | 192 / 808 / 0 / 0 / 0 | 2806 | 1.554 / 1.584 | 1.554 / 1.575 | 1.600 / 1.606 |
| guard_mirror v strike_straight | 796/1000 (0.770-0.820) | 204 / 796 / 0 / 0 / 0 | 2794 | 1.554 / 1.585 | 1.554 / 1.575 | 1.600 / 1.606 |
| guard_field v strike_straight | 716/1000 (0.687-0.743) | 284 / 716 / 0 / 0 / 0 | 2716 | 1.554 / 1.582 | 1.554 / 1.573 | 1.600 / 1.607 |
| trained v strike_converge | 928/1000 (0.910-0.942) | 72 / 928 / 0 / 0 / 0 | 2927 | 1.564 / 1.591 | 1.564 / 1.582 | 1.600 / 1.603 |
| guard_parked_centre v strike_converge | 986/1000 (0.977-0.992) | 14 / 986 / 0 / 0 / 0 | 2986 | 1.574 / 1.590 | 1.574 / 1.584 | 1.600 / 1.604 |
| guard_parked_ring v strike_converge | 983/1000 (0.973-0.989) | 17 / 983 / 0 / 0 / 0 | 2983 | 1.574 / 1.590 | 1.574 / 1.585 | 1.600 / 1.604 |
| guard_mark_edge v strike_converge | 974/1000 (0.962-0.982) | 26 / 974 / 0 / 0 / 0 | 2974 | 1.550 / 1.590 | 1.550 / 1.582 | 1.600 / 1.604 |
| guard_mirror v strike_converge | 968/1000 (0.955-0.977) | 32 / 968 / 0 / 0 / 0 | 2967 | 1.551 / 1.590 | 1.551 / 1.582 | 1.600 / 1.604 |
| guard_field v strike_converge | 871/1000 (0.849-0.890) | 129 / 871 / 0 / 0 / 0 | 2871 | 1.552 / 1.590 | 1.552 / 1.583 | 1.600 / 1.604 |
| trained v strike_sacrifice | 930/1000 (0.912-0.944) | 70 / 930 / 0 / 0 / 0 | 2912 | 1.559 / 1.587 | 1.559 / 1.579 | 1.600 / 1.605 |
| guard_parked_centre v strike_sacrifice | 525/1000 (0.494-0.556) | 475 / 525 / 0 / 0 / 0 | 2525 | 1.573 / 1.589 | 1.573 / 1.583 | 1.600 / 1.606 |
| guard_parked_ring v strike_sacrifice | 503/1000 (0.472-0.534) | 497 / 503 / 0 / 0 / 0 | 2503 | 1.572 / 1.589 | 1.572 / 1.583 | 1.600 / 1.606 |
| guard_mark_edge v strike_sacrifice | 960/1000 (0.946-0.970) | 40 / 960 / 0 / 0 / 0 | 2958 | 1.552 / 1.586 | 1.552 / 1.575 | 1.600 / 1.606 |
| guard_mirror v strike_sacrifice | 927/1000 (0.909-0.942) | 73 / 927 / 0 / 0 / 0 | 2925 | 1.552 / 1.586 | 1.552 / 1.575 | 1.600 / 1.606 |
| guard_field v strike_sacrifice | 862/1000 (0.839-0.882) | 138 / 862 / 0 / 0 / 0 | 2858 | 1.552 / 1.585 | 1.552 / 1.575 | 1.600 / 1.606 |
| trained v strike_high | 938/1000 (0.921-0.951) | 62 / 938 / 0 / 0 / 0 | 2935 | 1.563 / 1.587 | 1.563 / 1.578 | 1.600 / 1.606 |
| guard_parked_centre v strike_high | 466/1000 (0.435-0.497) | 534 / 466 / 0 / 0 / 0 | 2457 | 1.577 / 1.588 | 1.577 / 1.583 | 1.600 / 1.606 |
| guard_parked_ring v strike_high | 454/1000 (0.423-0.485) | 546 / 454 / 0 / 0 / 0 | 2444 | 1.576 / 1.588 | 1.576 / 1.582 | 1.600 / 1.605 |
| guard_mark_edge v strike_high | 850/1000 (0.827-0.871) | 150 / 850 / 0 / 0 / 0 | 2848 | 1.559 / 1.584 | 1.559 / 1.575 | 1.600 / 1.606 |
| guard_mirror v strike_high | 848/1000 (0.824-0.869) | 152 / 848 / 0 / 0 / 0 | 2846 | 1.559 / 1.585 | 1.559 / 1.575 | 1.600 / 1.607 |
| guard_field v strike_high | 734/1000 (0.706-0.760) | 266 / 734 / 0 / 0 / 0 | 2734 | 1.559 / 1.582 | 1.559 / 1.572 | 1.600 / 1.608 |
| trained v strike_flank | 960/1000 (0.946-0.970) | 40 / 960 / 0 / 0 / 0 | 2960 | 1.564 / 1.589 | 1.564 / 1.582 | 1.600 / 1.605 |
| guard_parked_centre v strike_flank | 450/1000 (0.419-0.481) | 550 / 450 / 0 / 0 / 0 | 2435 | 1.575 / 1.590 | 1.575 / 1.585 | 1.600 / 1.605 |
| guard_parked_ring v strike_flank | 477/1000 (0.446-0.508) | 523 / 477 / 0 / 0 / 0 | 2464 | 1.576 / 1.590 | 1.576 / 1.586 | 1.600 / 1.605 |
| guard_mark_edge v strike_flank | 887/1000 (0.866-0.905) | 113 / 887 / 0 / 0 / 0 | 2886 | 1.555 / 1.587 | 1.555 / 1.578 | 1.600 / 1.606 |
| guard_mirror v strike_flank | 864/1000 (0.841-0.884) | 136 / 864 / 0 / 0 / 0 | 2863 | 1.556 / 1.587 | 1.556 / 1.579 | 1.600 / 1.605 |
| guard_field v strike_flank | 808/1000 (0.782-0.831) | 192 / 808 / 0 / 0 / 0 | 2808 | 1.554 / 1.584 | 1.554 / 1.575 | 1.600 / 1.607 |

Reading:

- The L1.10 Guard team (tag drawn 1.5-1.7 m, estimate error) holds 896 of 1,000 (0.876-0.913) against strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) (best Guard script guard_mirror: 847).
- The L1.10 Guard team (tag drawn 1.5-1.7 m, estimate error) holds 921 of 1,000 (0.903-0.936) against strike_straight (best Guard script guard_mark_edge: 808).
- The L1.10 Guard team (tag drawn 1.5-1.7 m, estimate error) holds 928 of 1,000 (0.910-0.942) against strike_converge (best Guard script guard_parked_centre: 986).
- The L1.10 Guard team (tag drawn 1.5-1.7 m, estimate error) holds 930 of 1,000 (0.912-0.944) against strike_sacrifice (best Guard script guard_mark_edge: 960).
- The L1.10 Guard team (tag drawn 1.5-1.7 m, estimate error) holds 938 of 1,000 (0.921-0.951) against strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) (best Guard script guard_mark_edge: 850).
- The L1.10 Guard team (tag drawn 1.5-1.7 m, estimate error) holds 960 of 1,000 (0.946-0.970) against strike_flank (best Guard script guard_mark_edge: 887).

## tagdraw_err: `configs/ste_l1/base_err_tagdraw.toml` (3v3, tag drawn per game in 1.5-1.7 m, 120 s clock, nominal estimate error (INFO; the training game); response delay 0.1482 s; no screen reference for this game: script cells reported, not compared (INFO); one trained network, one start set; observed in the training simulator), worst cell first

| Opponent | Player's holds (Wilson 95 %) | Best script, same starts | Paired: player only / script only / both / neither | Player's games: reach / all Strike tagged / clock / other hold / unfinished | Median length (s) |
|---|---|---|---|---|---|
| strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 879/1000 (0.857-0.898) | guard_mark_edge 856/1000 (0.833-0.876) | 130 / 107 / 749 / 14 | 121 / 879 / 0 / 0 / 0 | 3.2 |
| strike_straight | 918/1000 (0.899-0.933) | guard_mark_edge 819/1000 (0.794-0.842) | 148 / 49 / 770 / 33 | 82 / 918 / 0 / 0 / 0 | 2.5 |
| strike_sacrifice | 918/1000 (0.899-0.933) | guard_mark_edge 957/1000 (0.943-0.968) | 35 / 74 / 883 / 8 | 82 / 918 / 0 / 0 / 0 | 3.8 |
| strike_converge | 923/1000 (0.905-0.938) | guard_parked_ring 981/1000 (0.971-0.988) | 14 / 72 / 909 / 5 | 77 / 923 / 0 / 0 / 0 | 7.9 |
| strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 927/1000 (0.909-0.942) | guard_mirror 855/1000 (0.832-0.875) | 137 / 65 / 790 / 8 | 73 / 927 / 0 / 0 / 0 | 3.0 |
| strike_flank | 963/1000 (0.949-0.973) | guard_mark_edge 891/1000 (0.870-0.909) | 105 / 33 / 858 / 4 | 37 / 963 / 0 / 0 / 0 | 3.1 |

Every cell of the batch (holds of the player's team; tag distance and closest approach over finished games; closest approach of any pair = per game min(tag distances, closest approach of pairs never tagged), as the tagged pair is removed on its tick):

| Cell (Guard v Strike) | Wins (Wilson 95 %) | Ends: reach / all Strike tagged / clock / other hold / unfinished | Tags | Tag distance min / median (m) | Closest approach, any pair, min / median (m) | Closest approach of pairs never tagged, min / median (m) |
|---|---|---|---|---|---|---|
| trained v strike_low | 879/1000 (0.857-0.898) | 121 / 879 / 0 / 0 / 0 | 2861 | 1.474 / 1.583 | 1.474 / 1.574 | 1.504 / 1.600 |
| guard_parked_centre v strike_low | 425/1000 (0.395-0.456) | 575 / 425 / 0 / 0 / 0 | 2401 | 1.481 / 1.588 | 1.481 / 1.579 | 1.502 / 1.602 |
| guard_parked_ring v strike_low | 427/1000 (0.397-0.458) | 573 / 427 / 0 / 0 / 0 | 2408 | 1.478 / 1.588 | 1.478 / 1.582 | 1.501 / 1.604 |
| guard_mark_edge v strike_low | 856/1000 (0.833-0.876) | 144 / 856 / 0 / 0 / 0 | 2848 | 1.461 / 1.582 | 1.461 / 1.573 | 1.501 / 1.604 |
| guard_mirror v strike_low | 854/1000 (0.831-0.875) | 146 / 854 / 0 / 0 / 0 | 2847 | 1.463 / 1.585 | 1.463 / 1.574 | 1.501 / 1.607 |
| guard_field v strike_low | 751/1000 (0.723-0.777) | 249 / 751 / 0 / 0 / 0 | 2751 | 1.466 / 1.583 | 1.466 / 1.575 | 1.501 / 1.611 |
| trained v strike_straight | 918/1000 (0.899-0.933) | 82 / 918 / 0 / 0 / 0 | 2916 | 1.468 / 1.582 | 1.468 / 1.572 | 1.503 / 1.601 |
| guard_parked_centre v strike_straight | 532/1000 (0.501-0.563) | 468 / 532 / 0 / 0 / 0 | 2526 | 1.479 / 1.585 | 1.479 / 1.578 | 1.505 / 1.601 |
| guard_parked_ring v strike_straight | 522/1000 (0.491-0.553) | 478 / 522 / 0 / 0 / 0 | 2515 | 1.474 / 1.587 | 1.474 / 1.580 | 1.500 / 1.604 |
| guard_mark_edge v strike_straight | 819/1000 (0.794-0.842) | 181 / 819 / 0 / 0 / 0 | 2817 | 1.466 / 1.581 | 1.466 / 1.573 | 1.503 / 1.605 |
| guard_mirror v strike_straight | 817/1000 (0.792-0.840) | 183 / 817 / 0 / 0 / 0 | 2816 | 1.462 / 1.584 | 1.462 / 1.574 | 1.502 / 1.607 |
| guard_field v strike_straight | 730/1000 (0.702-0.757) | 270 / 730 / 0 / 0 / 0 | 2730 | 1.459 / 1.584 | 1.459 / 1.575 | 1.504 / 1.610 |
| trained v strike_sacrifice | 918/1000 (0.899-0.933) | 82 / 918 / 0 / 0 / 0 | 2896 | 1.471 / 1.582 | 1.471 / 1.574 | 1.502 / 1.602 |
| guard_parked_centre v strike_sacrifice | 524/1000 (0.493-0.555) | 476 / 524 / 0 / 0 / 0 | 2523 | 1.475 / 1.585 | 1.475 / 1.579 | 1.502 / 1.604 |
| guard_parked_ring v strike_sacrifice | 511/1000 (0.480-0.542) | 489 / 511 / 0 / 0 / 0 | 2510 | 1.477 / 1.587 | 1.477 / 1.580 | 1.501 / 1.604 |
| guard_mark_edge v strike_sacrifice | 957/1000 (0.943-0.968) | 43 / 957 / 0 / 0 / 0 | 2954 | 1.458 / 1.583 | 1.458 / 1.570 | 1.502 / 1.604 |
| guard_mirror v strike_sacrifice | 929/1000 (0.911-0.943) | 71 / 929 / 0 / 0 / 0 | 2927 | 1.458 / 1.584 | 1.458 / 1.575 | 1.503 / 1.605 |
| guard_field v strike_sacrifice | 864/1000 (0.841-0.884) | 136 / 864 / 0 / 0 / 0 | 2857 | 1.459 / 1.584 | 1.459 / 1.576 | 1.504 / 1.609 |
| trained v strike_converge | 923/1000 (0.905-0.938) | 77 / 923 / 0 / 0 / 0 | 2920 | 1.476 / 1.585 | 1.476 / 1.578 | 1.502 / 1.599 |
| guard_parked_centre v strike_converge | 979/1000 (0.968-0.986) | 21 / 979 / 0 / 0 / 0 | 2979 | 1.476 / 1.585 | 1.476 / 1.580 | 1.502 / 1.601 |
| guard_parked_ring v strike_converge | 981/1000 (0.971-0.988) | 19 / 981 / 0 / 0 / 0 | 2981 | 1.479 / 1.587 | 1.479 / 1.582 | 1.500 / 1.601 |
| guard_mark_edge v strike_converge | 962/1000 (0.948-0.972) | 38 / 962 / 0 / 0 / 0 | 2958 | 1.460 / 1.585 | 1.460 / 1.577 | 1.501 / 1.602 |
| guard_mirror v strike_converge | 955/1000 (0.940-0.966) | 45 / 955 / 0 / 0 / 0 | 2949 | 1.464 / 1.588 | 1.464 / 1.579 | 1.502 / 1.605 |
| guard_field v strike_converge | 869/1000 (0.847-0.889) | 131 / 869 / 0 / 0 / 0 | 2869 | 1.458 / 1.589 | 1.458 / 1.580 | 1.501 / 1.604 |
| trained v strike_high | 927/1000 (0.909-0.942) | 73 / 927 / 0 / 0 / 0 | 2923 | 1.473 / 1.581 | 1.473 / 1.572 | 1.504 / 1.601 |
| guard_parked_centre v strike_high | 458/1000 (0.427-0.489) | 542 / 458 / 0 / 0 / 0 | 2445 | 1.477 / 1.586 | 1.477 / 1.579 | 1.502 / 1.602 |
| guard_parked_ring v strike_high | 461/1000 (0.430-0.492) | 539 / 461 / 0 / 0 / 0 | 2448 | 1.478 / 1.589 | 1.478 / 1.582 | 1.502 / 1.604 |
| guard_mark_edge v strike_high | 846/1000 (0.822-0.867) | 154 / 846 / 0 / 0 / 0 | 2840 | 1.462 / 1.581 | 1.462 / 1.572 | 1.501 / 1.606 |
| guard_mirror v strike_high | 855/1000 (0.832-0.875) | 145 / 855 / 0 / 0 / 0 | 2851 | 1.467 / 1.585 | 1.467 / 1.575 | 1.500 / 1.607 |
| guard_field v strike_high | 749/1000 (0.721-0.775) | 251 / 749 / 0 / 0 / 0 | 2749 | 1.466 / 1.584 | 1.466 / 1.575 | 1.503 / 1.612 |
| trained v strike_flank | 963/1000 (0.949-0.973) | 37 / 963 / 0 / 0 / 0 | 2963 | 1.478 / 1.583 | 1.478 / 1.574 | 1.504 / 1.599 |
| guard_parked_centre v strike_flank | 447/1000 (0.416-0.478) | 553 / 447 / 0 / 0 / 0 | 2423 | 1.480 / 1.588 | 1.480 / 1.582 | 1.502 / 1.602 |
| guard_parked_ring v strike_flank | 478/1000 (0.447-0.509) | 522 / 478 / 0 / 0 / 0 | 2462 | 1.480 / 1.589 | 1.480 / 1.583 | 1.501 / 1.603 |
| guard_mark_edge v strike_flank | 891/1000 (0.870-0.909) | 109 / 891 / 0 / 0 / 0 | 2890 | 1.468 / 1.583 | 1.468 / 1.574 | 1.501 / 1.604 |
| guard_mirror v strike_flank | 868/1000 (0.846-0.888) | 132 / 868 / 0 / 0 / 0 | 2865 | 1.467 / 1.586 | 1.467 / 1.577 | 1.502 / 1.607 |
| guard_field v strike_flank | 812/1000 (0.787-0.835) | 188 / 812 / 0 / 0 / 0 | 2812 | 1.462 / 1.584 | 1.462 / 1.575 | 1.506 / 1.608 |

Reading:

- The L1.10 Guard team (tag drawn 1.5-1.7 m, estimate error) holds 879 of 1,000 (0.857-0.898) against strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) (best Guard script guard_mark_edge: 856).
- The L1.10 Guard team (tag drawn 1.5-1.7 m, estimate error) holds 918 of 1,000 (0.899-0.933) against strike_straight (best Guard script guard_mark_edge: 819).
- The L1.10 Guard team (tag drawn 1.5-1.7 m, estimate error) holds 918 of 1,000 (0.899-0.933) against strike_sacrifice (best Guard script guard_mark_edge: 957).
- The L1.10 Guard team (tag drawn 1.5-1.7 m, estimate error) holds 923 of 1,000 (0.905-0.938) against strike_converge (best Guard script guard_parked_ring: 981).
- The L1.10 Guard team (tag drawn 1.5-1.7 m, estimate error) holds 927 of 1,000 (0.909-0.942) against strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) (best Guard script guard_mirror: 855).
- The L1.10 Guard team (tag drawn 1.5-1.7 m, estimate error) holds 963 of 1,000 (0.949-0.973) against strike_flank (best Guard script guard_mark_edge: 891).
