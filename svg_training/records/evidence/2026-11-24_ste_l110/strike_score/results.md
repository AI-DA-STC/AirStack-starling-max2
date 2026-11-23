Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator; nothing here is a flight result.

# L1.10: L1.10's Strike team (trained with the tag drawn in 1.5-1.7 m and the estimate error) scored against every Guard script at the fixed 1.6 m tag, with and without the error (INFO)

## Controls (read these first; any control not PASS: no number is reported)

| Control | Status | Detail |
|---|---|---|
| own_replay | **PASS** | EQUAL {'outcome': 0, 'end_step': 0, 'tags': 0, 'strikes_left': 0, 'start_pos_m': 0, 'closest_3d_m': 0}; trained reaches 687/1000 (record 687); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_base_err__guard_parked_centre | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_base_err__guard_parked_ring | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_base_err__guard_mark_edge | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_base_err__guard_mirror | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_base_err__guard_field | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| scripts_base__guard_parked_centre | **PASS** | guard_parked_centre v strike_straight: ok (holds 534 v T44 534, reaches 466 v 466; 0 of 1000 games differ (0 in outcome)); guard_parked_centre v strike_flank: ok (holds 450 v T44 450, reaches 550 v 550; 0 of 1000 games differ (0 in outcome)); guard_parked_centre v strike_high: ok (holds 466 v T44 466, reaches 534 v 534; 0 of 1000 games differ (0 in outcome)); guard_parked_centre v strike_low: ok (holds 430 v T44 430, reaches 570 v 570; 0 of 1000 games differ (0 in outcome)); guard_parked_centre v strike_sacrifice: ok (holds 525 v T44 525, reaches 475 v 475; 0 of 1000 games differ (0 in outcome)); guard_parked_centre v strike_converge: ok (holds 986 v T44 986, reaches 14 v 14; 0 of 1000 games differ (0 in outcome)); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| scripts_base__guard_parked_ring | **PASS** | guard_parked_ring v strike_straight: ok (holds 523 v T44 523, reaches 477 v 477; 0 of 1000 games differ (0 in outcome)); guard_parked_ring v strike_flank: ok (holds 477 v T44 477, reaches 523 v 523; 0 of 1000 games differ (0 in outcome)); guard_parked_ring v strike_high: ok (holds 454 v T44 454, reaches 546 v 546; 0 of 1000 games differ (0 in outcome)); guard_parked_ring v strike_low: ok (holds 424 v T44 424, reaches 576 v 576; 0 of 1000 games differ (0 in outcome)); guard_parked_ring v strike_sacrifice: ok (holds 503 v T44 503, reaches 497 v 497; 0 of 1000 games differ (0 in outcome)); guard_parked_ring v strike_converge: ok (holds 983 v T44 983, reaches 17 v 17; 0 of 1000 games differ (0 in outcome)); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| scripts_base__guard_mark_edge | **PASS** | guard_mark_edge v strike_straight: ok (holds 808 v T44 808, reaches 192 v 192; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_flank: ok (holds 887 v T44 887, reaches 113 v 113; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_high: ok (holds 850 v T44 850, reaches 150 v 150; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_low: ok (holds 844 v T44 844, reaches 156 v 156; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_sacrifice: ok (holds 960 v T44 960, reaches 40 v 40; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_converge: ok (holds 974 v T44 974, reaches 26 v 26; 0 of 1000 games differ (0 in outcome)); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS; the player's cell v its own training opponent EQUALS own_replay's trained cell game for game {'outcome': 0, 'end_step': 0, 'tags': 0, 'strikes_left': 0, 'start_pos_m': 0, 'closest_3d_m': 0} |
| scripts_base__guard_mirror | **PASS** | guard_mirror v strike_straight: ok (holds 796 v T44 796, reaches 204 v 204; 0 of 1000 games differ (0 in outcome)); guard_mirror v strike_flank: ok (holds 864 v T44 864, reaches 136 v 136; 0 of 1000 games differ (0 in outcome)); guard_mirror v strike_high: ok (holds 848 v T44 848, reaches 152 v 152; 0 of 1000 games differ (0 in outcome)); guard_mirror v strike_low: ok (holds 847 v T44 847, reaches 153 v 153; 0 of 1000 games differ (0 in outcome)); guard_mirror v strike_sacrifice: ok (holds 927 v T44 927, reaches 73 v 73; 0 of 1000 games differ (0 in outcome)); guard_mirror v strike_converge: ok (holds 968 v T44 968, reaches 32 v 32; 0 of 1000 games differ (0 in outcome)); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| scripts_base__guard_field | **PASS** | guard_field v strike_straight: ok (holds 716 v T44 716, reaches 284 v 284; 0 of 1000 games differ (0 in outcome)); guard_field v strike_flank: ok (holds 808 v T44 808, reaches 192 v 192; 0 of 1000 games differ (0 in outcome)); guard_field v strike_high: ok (holds 734 v T44 734, reaches 266 v 266; 0 of 1000 games differ (0 in outcome)); guard_field v strike_low: ok (holds 739 v T44 739, reaches 261 v 261; 0 of 1000 games differ (0 in outcome)); guard_field v strike_sacrifice: ok (holds 862 v T44 862, reaches 138 v 138; 0 of 1000 games differ (0 in outcome)); guard_field v strike_converge: ok (holds 871 v T44 871, reaches 129 v 129; 0 of 1000 games differ (0 in outcome)); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_tagdraw_err__guard_parked_centre | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_tagdraw_err__guard_parked_ring | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_tagdraw_err__guard_mark_edge | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_tagdraw_err__guard_mirror | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| plumbing_tagdraw_err__guard_field | **PASS** | no screen reference for this game: script cells reported, not compared (INFO); ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |

## base_err: `configs/ste_l1/base_err_nominal.toml` (3v3, tag 1.6 m fixed, 120 s clock, nominal estimate error (main); response delay 0.1482 s; no screen reference for this game: script cells reported, not compared (INFO); one trained network, one start set; observed in the training simulator), worst cell first

| Opponent | Player's reaches (Wilson 95 %) | Best script, same starts | Paired: player only / script only / both / neither | Player's games: reach / all Strike tagged / clock / other hold / unfinished | Median length (s) |
|---|---|---|---|---|---|
| guard_field | 39/1000 (0.029-0.053) | strike_straight 280/1000 (0.253-0.309) | 0 / 241 / 39 / 720 | 39 / 463 / 498 / 0 / 0 | 119.1 |
| guard_parked_ring | 194/1000 (0.171-0.220) | strike_low 573/1000 (0.542-0.603) | 39 / 418 / 155 / 388 | 194 / 8 / 798 / 0 / 0 | 120.0 |
| guard_parked_centre | 204/1000 (0.180-0.230) | strike_low 569/1000 (0.538-0.599) | 43 / 408 / 161 / 388 | 204 / 5 / 791 / 0 / 0 | 120.0 |
| guard_mirror | 591/1000 (0.560-0.621) | strike_straight 193/1000 (0.170-0.219) | 476 / 78 / 115 / 331 | 591 / 384 / 25 / 0 / 0 | 9.2 |
| guard_mark_edge | 681/1000 (0.651-0.709) | strike_straight 181/1000 (0.158-0.206) | 567 / 67 / 114 / 252 | 681 / 150 / 169 / 0 / 0 | 10.0 |

Every cell of the batch (reaches of the player's team; tag distance and closest approach over finished games; closest approach of any pair = per game min(tag distances, closest approach of pairs never tagged), as the tagged pair is removed on its tick):

| Cell (Guard v Strike) | Wins (Wilson 95 %) | Ends: reach / all Strike tagged / clock / other hold / unfinished | Tags | Tag distance min / median (m) | Closest approach, any pair, min / median (m) | Closest approach of pairs never tagged, min / median (m) |
|---|---|---|---|---|---|---|
| guard_field v trained | 39/1000 (0.029-0.053) | 39 / 463 / 498 / 0 / 0 | 2425 | 1.566 / 1.594 | 1.566 / 1.588 | 1.600 / 1.602 |
| guard_field v strike_straight | 280/1000 (0.253-0.309) | 280 / 720 / 0 / 0 / 0 | 2720 | 1.553 / 1.583 | 1.553 / 1.573 | 1.600 / 1.608 |
| guard_field v strike_flank | 195/1000 (0.172-0.221) | 195 / 805 / 0 / 0 / 0 | 2805 | 1.554 / 1.584 | 1.554 / 1.576 | 1.600 / 1.607 |
| guard_field v strike_high | 259/1000 (0.233-0.287) | 259 / 741 / 0 / 0 / 0 | 2741 | 1.558 / 1.583 | 1.558 / 1.573 | 1.600 / 1.609 |
| guard_field v strike_low | 255/1000 (0.229-0.283) | 255 / 745 / 0 / 0 / 0 | 2745 | 1.557 / 1.582 | 1.557 / 1.572 | 1.600 / 1.608 |
| guard_field v strike_sacrifice | 131/1000 (0.111-0.153) | 131 / 869 / 0 / 0 / 0 | 2864 | 1.552 / 1.584 | 1.552 / 1.575 | 1.600 / 1.607 |
| guard_field v strike_converge | 128/1000 (0.109-0.150) | 128 / 872 / 0 / 0 / 0 | 2872 | 1.551 / 1.590 | 1.551 / 1.583 | 1.600 / 1.604 |
| guard_parked_ring v trained | 194/1000 (0.171-0.220) | 194 / 8 / 798 / 0 / 0 | 1634 | 1.583 / 1.598 | 1.583 / 1.597 | 1.600 / 1.601 |
| guard_parked_ring v strike_straight | 474/1000 (0.443-0.505) | 474 / 526 / 0 / 0 / 0 | 2519 | 1.573 / 1.589 | 1.573 / 1.582 | 1.600 / 1.606 |
| guard_parked_ring v strike_flank | 521/1000 (0.490-0.552) | 521 / 479 / 0 / 0 / 0 | 2465 | 1.574 / 1.590 | 1.574 / 1.585 | 1.600 / 1.605 |
| guard_parked_ring v strike_high | 539/1000 (0.508-0.570) | 539 / 461 / 0 / 0 / 0 | 2451 | 1.575 / 1.589 | 1.575 / 1.583 | 1.600 / 1.606 |
| guard_parked_ring v strike_low | 573/1000 (0.542-0.603) | 573 / 427 / 0 / 0 / 0 | 2411 | 1.575 / 1.589 | 1.575 / 1.583 | 1.600 / 1.605 |
| guard_parked_ring v strike_sacrifice | 494/1000 (0.463-0.525) | 494 / 506 / 0 / 0 / 0 | 2506 | 1.572 / 1.589 | 1.572 / 1.583 | 1.600 / 1.606 |
| guard_parked_ring v strike_converge | 12/1000 (0.007-0.021) | 12 / 988 / 0 / 0 / 0 | 2988 | 1.572 / 1.590 | 1.572 / 1.584 | 1.600 / 1.604 |
| guard_parked_centre v trained | 204/1000 (0.180-0.230) | 204 / 5 / 791 / 0 / 0 | 1618 | 1.582 / 1.598 | 1.582 / 1.597 | 1.600 / 1.601 |
| guard_parked_centre v strike_straight | 459/1000 (0.428-0.490) | 459 / 541 / 0 / 0 / 0 | 2535 | 1.572 / 1.588 | 1.572 / 1.582 | 1.600 / 1.606 |
| guard_parked_centre v strike_flank | 545/1000 (0.514-0.576) | 545 / 455 / 0 / 0 / 0 | 2439 | 1.576 / 1.590 | 1.576 / 1.585 | 1.600 / 1.605 |
| guard_parked_centre v strike_high | 527/1000 (0.496-0.558) | 527 / 473 / 0 / 0 / 0 | 2463 | 1.575 / 1.588 | 1.575 / 1.583 | 1.600 / 1.606 |
| guard_parked_centre v strike_low | 569/1000 (0.538-0.599) | 569 / 431 / 0 / 0 / 0 | 2415 | 1.576 / 1.589 | 1.576 / 1.584 | 1.600 / 1.606 |
| guard_parked_centre v strike_sacrifice | 483/1000 (0.452-0.514) | 483 / 517 / 0 / 0 / 0 | 2517 | 1.572 / 1.588 | 1.572 / 1.582 | 1.600 / 1.606 |
| guard_parked_centre v strike_converge | 15/1000 (0.009-0.025) | 15 / 985 / 0 / 0 / 0 | 2985 | 1.574 / 1.590 | 1.574 / 1.584 | 1.600 / 1.604 |
| guard_mirror v trained | 591/1000 (0.560-0.621) | 591 / 384 / 25 / 0 / 0 | 1843 | 1.562 / 1.592 | 1.562 / 1.587 | 1.600 / 1.606 |
| guard_mirror v strike_straight | 193/1000 (0.170-0.219) | 193 / 807 / 0 / 0 / 0 | 2805 | 1.555 / 1.585 | 1.555 / 1.575 | 1.600 / 1.606 |
| guard_mirror v strike_flank | 134/1000 (0.114-0.157) | 134 / 866 / 0 / 0 / 0 | 2866 | 1.558 / 1.587 | 1.558 / 1.579 | 1.600 / 1.606 |
| guard_mirror v strike_high | 144/1000 (0.124-0.167) | 144 / 856 / 0 / 0 / 0 | 2854 | 1.559 / 1.585 | 1.559 / 1.576 | 1.600 / 1.607 |
| guard_mirror v strike_low | 143/1000 (0.123-0.166) | 143 / 857 / 0 / 0 / 0 | 2852 | 1.558 / 1.584 | 1.558 / 1.575 | 1.600 / 1.606 |
| guard_mirror v strike_sacrifice | 73/1000 (0.058-0.091) | 73 / 927 / 0 / 0 / 0 | 2926 | 1.553 / 1.586 | 1.553 / 1.576 | 1.600 / 1.606 |
| guard_mirror v strike_converge | 38/1000 (0.028-0.052) | 38 / 962 / 0 / 0 / 0 | 2961 | 1.554 / 1.590 | 1.554 / 1.582 | 1.600 / 1.604 |
| guard_mark_edge v trained | 681/1000 (0.651-0.709) | 681 / 150 / 169 / 0 / 0 | 1483 | 1.563 / 1.592 | 1.563 / 1.588 | 1.600 / 1.607 |
| guard_mark_edge v strike_straight | 181/1000 (0.158-0.206) | 181 / 819 / 0 / 0 / 0 | 2817 | 1.551 / 1.585 | 1.551 / 1.575 | 1.600 / 1.607 |
| guard_mark_edge v strike_flank | 110/1000 (0.092-0.131) | 110 / 890 / 0 / 0 / 0 | 2889 | 1.553 / 1.586 | 1.553 / 1.578 | 1.600 / 1.605 |
| guard_mark_edge v strike_high | 150/1000 (0.129-0.173) | 150 / 850 / 0 / 0 / 0 | 2847 | 1.557 / 1.585 | 1.557 / 1.575 | 1.600 / 1.607 |
| guard_mark_edge v strike_low | 141/1000 (0.121-0.164) | 141 / 859 / 0 / 0 / 0 | 2855 | 1.559 / 1.584 | 1.559 / 1.575 | 1.600 / 1.607 |
| guard_mark_edge v strike_sacrifice | 42/1000 (0.031-0.056) | 42 / 958 / 0 / 0 / 0 | 2956 | 1.551 / 1.586 | 1.551 / 1.575 | 1.600 / 1.605 |
| guard_mark_edge v strike_converge | 29/1000 (0.020-0.041) | 29 / 971 / 0 / 0 / 0 | 2969 | 1.551 / 1.590 | 1.551 / 1.582 | 1.600 / 1.604 |

Reading:

- The L1.10 Strike team (tag drawn 1.5-1.7 m, estimate error) reaches 39 of 1,000 (0.029-0.053) against guard_field (best Strike script strike_straight: 280).
- The L1.10 Strike team (tag drawn 1.5-1.7 m, estimate error) reaches 194 of 1,000 (0.171-0.220) against guard_parked_ring (best Strike script strike_low: 573).
- The L1.10 Strike team (tag drawn 1.5-1.7 m, estimate error) reaches 204 of 1,000 (0.180-0.230) against guard_parked_centre (best Strike script strike_low: 569).
- The L1.10 Strike team (tag drawn 1.5-1.7 m, estimate error) reaches 591 of 1,000 (0.560-0.621) against guard_mirror (best Strike script strike_straight: 193).
- The L1.10 Strike team (tag drawn 1.5-1.7 m, estimate error) reaches 681 of 1,000 (0.651-0.709) against guard_mark_edge (best Strike script strike_straight: 181).

## base: `configs/ste_l011/base.toml` (3v3, tag 1.6 m fixed, 120 s clock, no estimate error (INFO; T46's game); response delay 0.1482 s; one trained network, one start set; observed in the training simulator), worst cell first

| Opponent | Player's reaches (Wilson 95 %) | Best script, same starts | Paired: player only / script only / both / neither | Player's games: reach / all Strike tagged / clock / other hold / unfinished | Median length (s) |
|---|---|---|---|---|---|
| guard_field | 43/1000 (0.032-0.057) | strike_straight 284/1000 (0.257-0.313) | 0 / 241 / 43 / 716 | 43 / 438 / 519 / 0 / 0 | 120.0 |
| guard_parked_ring | 189/1000 (0.166-0.214) | strike_low 576/1000 (0.545-0.606) | 36 / 423 / 153 / 388 | 189 / 5 / 806 / 0 / 0 | 120.0 |
| guard_parked_centre | 201/1000 (0.177-0.227) | strike_low 570/1000 (0.539-0.600) | 39 / 408 / 162 / 391 | 201 / 6 / 793 / 0 / 0 | 120.0 |
| guard_mirror | 576/1000 (0.545-0.606) | strike_straight 204/1000 (0.180-0.230) | 466 / 94 / 110 / 330 | 576 / 393 / 31 / 0 / 0 | 9.2 |
| guard_mark_edge | 687/1000 (0.658-0.715) | strike_straight 192/1000 (0.169-0.218) | 567 / 72 / 120 / 241 | 687 / 144 / 169 / 0 / 0 | 10.0 |

Every cell of the batch (reaches of the player's team; tag distance and closest approach over finished games; closest approach of any pair = per game min(tag distances, closest approach of pairs never tagged), as the tagged pair is removed on its tick):

| Cell (Guard v Strike) | Wins (Wilson 95 %) | Ends: reach / all Strike tagged / clock / other hold / unfinished | Tags | Tag distance min / median (m) | Closest approach, any pair, min / median (m) | Closest approach of pairs never tagged, min / median (m) |
|---|---|---|---|---|---|---|
| guard_field v trained | 43/1000 (0.032-0.057) | 43 / 438 / 519 / 0 / 0 | 2395 | 1.567 / 1.594 | 1.567 / 1.588 | 1.600 / 1.602 |
| guard_field v strike_straight | 284/1000 (0.257-0.313) | 284 / 716 / 0 / 0 / 0 | 2716 | 1.554 / 1.582 | 1.554 / 1.573 | 1.600 / 1.607 |
| guard_field v strike_flank | 192/1000 (0.169-0.218) | 192 / 808 / 0 / 0 / 0 | 2808 | 1.554 / 1.584 | 1.554 / 1.575 | 1.600 / 1.607 |
| guard_field v strike_high | 266/1000 (0.240-0.294) | 266 / 734 / 0 / 0 / 0 | 2734 | 1.559 / 1.582 | 1.559 / 1.572 | 1.600 / 1.608 |
| guard_field v strike_low | 261/1000 (0.235-0.289) | 261 / 739 / 0 / 0 / 0 | 2739 | 1.560 / 1.582 | 1.560 / 1.572 | 1.600 / 1.608 |
| guard_field v strike_sacrifice | 138/1000 (0.118-0.161) | 138 / 862 / 0 / 0 / 0 | 2858 | 1.552 / 1.585 | 1.552 / 1.575 | 1.600 / 1.606 |
| guard_field v strike_converge | 129/1000 (0.110-0.151) | 129 / 871 / 0 / 0 / 0 | 2871 | 1.552 / 1.590 | 1.552 / 1.583 | 1.600 / 1.604 |
| guard_parked_ring v trained | 189/1000 (0.166-0.214) | 189 / 5 / 806 / 0 / 0 | 1615 | 1.582 / 1.598 | 1.582 / 1.597 | 1.600 / 1.601 |
| guard_parked_ring v strike_straight | 477/1000 (0.446-0.508) | 477 / 523 / 0 / 0 / 0 | 2518 | 1.574 / 1.588 | 1.574 / 1.582 | 1.600 / 1.606 |
| guard_parked_ring v strike_flank | 523/1000 (0.492-0.554) | 523 / 477 / 0 / 0 / 0 | 2464 | 1.576 / 1.590 | 1.576 / 1.586 | 1.600 / 1.605 |
| guard_parked_ring v strike_high | 546/1000 (0.515-0.577) | 546 / 454 / 0 / 0 / 0 | 2444 | 1.576 / 1.588 | 1.576 / 1.582 | 1.600 / 1.605 |
| guard_parked_ring v strike_low | 576/1000 (0.545-0.606) | 576 / 424 / 0 / 0 / 0 | 2411 | 1.576 / 1.590 | 1.576 / 1.584 | 1.600 / 1.606 |
| guard_parked_ring v strike_sacrifice | 497/1000 (0.466-0.528) | 497 / 503 / 0 / 0 / 0 | 2503 | 1.572 / 1.589 | 1.572 / 1.583 | 1.600 / 1.606 |
| guard_parked_ring v strike_converge | 17/1000 (0.011-0.027) | 17 / 983 / 0 / 0 / 0 | 2983 | 1.574 / 1.590 | 1.574 / 1.585 | 1.600 / 1.604 |
| guard_parked_centre v trained | 201/1000 (0.177-0.227) | 201 / 6 / 793 / 0 / 0 | 1603 | 1.582 / 1.598 | 1.582 / 1.597 | 1.600 / 1.601 |
| guard_parked_centre v strike_straight | 466/1000 (0.435-0.497) | 466 / 534 / 0 / 0 / 0 | 2529 | 1.573 / 1.588 | 1.573 / 1.582 | 1.600 / 1.606 |
| guard_parked_centre v strike_flank | 550/1000 (0.519-0.581) | 550 / 450 / 0 / 0 / 0 | 2435 | 1.575 / 1.590 | 1.575 / 1.585 | 1.600 / 1.605 |
| guard_parked_centre v strike_high | 534/1000 (0.503-0.565) | 534 / 466 / 0 / 0 / 0 | 2457 | 1.577 / 1.588 | 1.577 / 1.583 | 1.600 / 1.606 |
| guard_parked_centre v strike_low | 570/1000 (0.539-0.600) | 570 / 430 / 0 / 0 / 0 | 2417 | 1.577 / 1.589 | 1.577 / 1.584 | 1.600 / 1.606 |
| guard_parked_centre v strike_sacrifice | 475/1000 (0.444-0.506) | 475 / 525 / 0 / 0 / 0 | 2525 | 1.573 / 1.589 | 1.573 / 1.583 | 1.600 / 1.606 |
| guard_parked_centre v strike_converge | 14/1000 (0.008-0.023) | 14 / 986 / 0 / 0 / 0 | 2986 | 1.574 / 1.590 | 1.574 / 1.584 | 1.600 / 1.604 |
| guard_mirror v trained | 576/1000 (0.545-0.606) | 576 / 393 / 31 / 0 / 0 | 1864 | 1.558 / 1.592 | 1.558 / 1.587 | 1.600 / 1.605 |
| guard_mirror v strike_straight | 204/1000 (0.180-0.230) | 204 / 796 / 0 / 0 / 0 | 2794 | 1.554 / 1.585 | 1.554 / 1.575 | 1.600 / 1.606 |
| guard_mirror v strike_flank | 136/1000 (0.116-0.159) | 136 / 864 / 0 / 0 / 0 | 2863 | 1.556 / 1.587 | 1.556 / 1.579 | 1.600 / 1.605 |
| guard_mirror v strike_high | 152/1000 (0.131-0.176) | 152 / 848 / 0 / 0 / 0 | 2846 | 1.559 / 1.585 | 1.559 / 1.575 | 1.600 / 1.607 |
| guard_mirror v strike_low | 153/1000 (0.132-0.177) | 153 / 847 / 0 / 0 / 0 | 2843 | 1.559 / 1.585 | 1.559 / 1.575 | 1.600 / 1.607 |
| guard_mirror v strike_sacrifice | 73/1000 (0.058-0.091) | 73 / 927 / 0 / 0 / 0 | 2925 | 1.552 / 1.586 | 1.552 / 1.575 | 1.600 / 1.606 |
| guard_mirror v strike_converge | 32/1000 (0.023-0.045) | 32 / 968 / 0 / 0 / 0 | 2967 | 1.551 / 1.590 | 1.551 / 1.582 | 1.600 / 1.604 |
| guard_mark_edge v trained | 687/1000 (0.658-0.715) | 687 / 144 / 169 / 0 / 0 | 1473 | 1.564 / 1.592 | 1.564 / 1.588 | 1.600 / 1.606 |
| guard_mark_edge v strike_straight | 192/1000 (0.169-0.218) | 192 / 808 / 0 / 0 / 0 | 2806 | 1.554 / 1.584 | 1.554 / 1.575 | 1.600 / 1.606 |
| guard_mark_edge v strike_flank | 113/1000 (0.095-0.134) | 113 / 887 / 0 / 0 / 0 | 2886 | 1.555 / 1.587 | 1.555 / 1.578 | 1.600 / 1.606 |
| guard_mark_edge v strike_high | 150/1000 (0.129-0.173) | 150 / 850 / 0 / 0 / 0 | 2848 | 1.559 / 1.584 | 1.559 / 1.575 | 1.600 / 1.606 |
| guard_mark_edge v strike_low | 156/1000 (0.135-0.180) | 156 / 844 / 0 / 0 / 0 | 2840 | 1.559 / 1.585 | 1.559 / 1.575 | 1.600 / 1.607 |
| guard_mark_edge v strike_sacrifice | 40/1000 (0.030-0.054) | 40 / 960 / 0 / 0 / 0 | 2958 | 1.552 / 1.586 | 1.552 / 1.575 | 1.600 / 1.606 |
| guard_mark_edge v strike_converge | 26/1000 (0.018-0.038) | 26 / 974 / 0 / 0 / 0 | 2974 | 1.550 / 1.590 | 1.550 / 1.582 | 1.600 / 1.604 |

Reading:

- The L1.10 Strike team (tag drawn 1.5-1.7 m, estimate error) reaches 43 of 1,000 (0.032-0.057) against guard_field (best Strike script strike_straight: 284).
- The L1.10 Strike team (tag drawn 1.5-1.7 m, estimate error) reaches 189 of 1,000 (0.166-0.214) against guard_parked_ring (best Strike script strike_low: 576).
- The L1.10 Strike team (tag drawn 1.5-1.7 m, estimate error) reaches 201 of 1,000 (0.177-0.227) against guard_parked_centre (best Strike script strike_low: 570).
- The L1.10 Strike team (tag drawn 1.5-1.7 m, estimate error) reaches 576 of 1,000 (0.545-0.606) against guard_mirror (best Strike script strike_straight: 204).
- The L1.10 Strike team (tag drawn 1.5-1.7 m, estimate error) reaches 687 of 1,000 (0.658-0.715) against guard_mark_edge (best Strike script strike_straight: 192).

## tagdraw_err: `configs/ste_l1/base_err_tagdraw.toml` (3v3, tag drawn per game in 1.5-1.7 m, 120 s clock, nominal estimate error (INFO; the training game); response delay 0.1482 s; no screen reference for this game: script cells reported, not compared (INFO); one trained network, one start set; observed in the training simulator), worst cell first

| Opponent | Player's reaches (Wilson 95 %) | Best script, same starts | Paired: player only / script only / both / neither | Player's games: reach / all Strike tagged / clock / other hold / unfinished | Median length (s) |
|---|---|---|---|---|---|
| guard_field | 41/1000 (0.030-0.055) | strike_straight 267/1000 (0.241-0.295) | 0 / 226 / 41 / 733 | 41 / 426 / 533 / 0 / 0 | 120.0 |
| guard_parked_ring | 202/1000 (0.178-0.228) | strike_low 582/1000 (0.551-0.612) | 46 / 426 / 156 / 372 | 202 / 7 / 791 / 0 / 0 | 120.0 |
| guard_parked_centre | 208/1000 (0.184-0.234) | strike_low 578/1000 (0.547-0.608) | 45 / 415 / 163 / 377 | 208 / 6 / 786 / 0 / 0 | 120.0 |
| guard_mirror | 587/1000 (0.556-0.617) | strike_straight 181/1000 (0.158-0.206) | 481 / 75 / 106 / 338 | 587 / 387 / 26 / 0 / 0 | 9.2 |
| guard_mark_edge | 692/1000 (0.663-0.720) | strike_straight 175/1000 (0.153-0.200) | 578 / 61 / 114 / 247 | 692 / 151 / 157 / 0 / 0 | 10.0 |

Every cell of the batch (reaches of the player's team; tag distance and closest approach over finished games; closest approach of any pair = per game min(tag distances, closest approach of pairs never tagged), as the tagged pair is removed on its tick):

| Cell (Guard v Strike) | Wins (Wilson 95 %) | Ends: reach / all Strike tagged / clock / other hold / unfinished | Tags | Tag distance min / median (m) | Closest approach, any pair, min / median (m) | Closest approach of pairs never tagged, min / median (m) |
|---|---|---|---|---|---|---|
| guard_field v trained | 41/1000 (0.030-0.055) | 41 / 426 / 533 / 0 / 0 | 2387 | 1.478 / 1.595 | 1.478 / 1.582 | 1.501 / 1.597 |
| guard_field v strike_straight | 267/1000 (0.241-0.295) | 267 / 733 / 0 / 0 / 0 | 2733 | 1.462 / 1.578 | 1.462 / 1.570 | 1.503 / 1.604 |
| guard_field v strike_flank | 192/1000 (0.169-0.218) | 192 / 808 / 0 / 0 / 0 | 2808 | 1.466 / 1.582 | 1.466 / 1.574 | 1.501 / 1.606 |
| guard_field v strike_high | 257/1000 (0.231-0.285) | 257 / 743 / 0 / 0 / 0 | 2743 | 1.463 / 1.580 | 1.463 / 1.570 | 1.501 / 1.608 |
| guard_field v strike_low | 248/1000 (0.222-0.276) | 248 / 752 / 0 / 0 / 0 | 2752 | 1.467 / 1.581 | 1.467 / 1.572 | 1.503 / 1.606 |
| guard_field v strike_sacrifice | 136/1000 (0.116-0.159) | 136 / 864 / 0 / 0 / 0 | 2857 | 1.459 / 1.584 | 1.459 / 1.576 | 1.504 / 1.609 |
| guard_field v strike_converge | 129/1000 (0.110-0.151) | 129 / 871 / 0 / 0 / 0 | 2871 | 1.462 / 1.589 | 1.462 / 1.582 | 1.502 / 1.604 |
| guard_parked_ring v trained | 202/1000 (0.178-0.228) | 202 / 7 / 791 / 0 / 0 | 1625 | 1.492 / 1.594 | 1.492 / 1.590 | 1.502 / 1.596 |
| guard_parked_ring v strike_straight | 485/1000 (0.454-0.516) | 485 / 515 / 0 / 0 / 0 | 2508 | 1.477 / 1.584 | 1.477 / 1.578 | 1.502 / 1.602 |
| guard_parked_ring v strike_flank | 522/1000 (0.491-0.553) | 522 / 478 / 0 / 0 / 0 | 2462 | 1.480 / 1.589 | 1.480 / 1.583 | 1.501 / 1.603 |
| guard_parked_ring v strike_high | 540/1000 (0.509-0.571) | 540 / 460 / 0 / 0 / 0 | 2446 | 1.478 / 1.588 | 1.478 / 1.581 | 1.501 / 1.604 |
| guard_parked_ring v strike_low | 582/1000 (0.551-0.612) | 582 / 418 / 0 / 0 / 0 | 2401 | 1.477 / 1.590 | 1.477 / 1.583 | 1.501 / 1.605 |
| guard_parked_ring v strike_sacrifice | 490/1000 (0.459-0.521) | 490 / 510 / 0 / 0 / 0 | 2510 | 1.476 / 1.589 | 1.476 / 1.584 | 1.502 / 1.607 |
| guard_parked_ring v strike_converge | 11/1000 (0.006-0.020) | 11 / 989 / 0 / 0 / 0 | 2989 | 1.480 / 1.589 | 1.480 / 1.583 | 1.501 / 1.604 |
| guard_parked_centre v trained | 208/1000 (0.184-0.234) | 208 / 6 / 786 / 0 / 0 | 1606 | 1.490 / 1.595 | 1.490 / 1.591 | 1.500 / 1.596 |
| guard_parked_centre v strike_straight | 468/1000 (0.437-0.499) | 468 / 532 / 0 / 0 / 0 | 2526 | 1.479 / 1.585 | 1.479 / 1.578 | 1.505 / 1.601 |
| guard_parked_centre v strike_flank | 535/1000 (0.504-0.566) | 535 / 465 / 0 / 0 / 0 | 2449 | 1.480 / 1.590 | 1.480 / 1.583 | 1.501 / 1.603 |
| guard_parked_centre v strike_high | 536/1000 (0.505-0.567) | 536 / 464 / 0 / 0 / 0 | 2451 | 1.479 / 1.588 | 1.479 / 1.581 | 1.501 / 1.603 |
| guard_parked_centre v strike_low | 578/1000 (0.547-0.608) | 578 / 422 / 0 / 0 / 0 | 2404 | 1.480 / 1.591 | 1.480 / 1.584 | 1.503 / 1.606 |
| guard_parked_centre v strike_sacrifice | 467/1000 (0.436-0.498) | 467 / 533 / 0 / 0 / 0 | 2533 | 1.474 / 1.588 | 1.474 / 1.583 | 1.503 / 1.606 |
| guard_parked_centre v strike_converge | 14/1000 (0.008-0.023) | 14 / 986 / 0 / 0 / 0 | 2986 | 1.479 / 1.588 | 1.479 / 1.582 | 1.502 / 1.604 |
| guard_mirror v trained | 587/1000 (0.556-0.617) | 587 / 387 / 26 / 0 / 0 | 1850 | 1.474 / 1.591 | 1.474 / 1.584 | 1.503 / 1.603 |
| guard_mirror v strike_straight | 181/1000 (0.158-0.206) | 181 / 819 / 0 / 0 / 0 | 2816 | 1.461 / 1.581 | 1.461 / 1.571 | 1.502 / 1.604 |
| guard_mirror v strike_flank | 129/1000 (0.110-0.151) | 129 / 871 / 0 / 0 / 0 | 2870 | 1.465 / 1.584 | 1.465 / 1.575 | 1.501 / 1.603 |
| guard_mirror v strike_high | 154/1000 (0.133-0.178) | 154 / 846 / 0 / 0 / 0 | 2841 | 1.463 / 1.580 | 1.463 / 1.572 | 1.501 / 1.605 |
| guard_mirror v strike_low | 146/1000 (0.125-0.169) | 146 / 854 / 0 / 0 / 0 | 2847 | 1.463 / 1.585 | 1.463 / 1.574 | 1.501 / 1.607 |
| guard_mirror v strike_sacrifice | 76/1000 (0.061-0.094) | 76 / 924 / 0 / 0 / 0 | 2922 | 1.461 / 1.584 | 1.461 / 1.575 | 1.502 / 1.607 |
| guard_mirror v strike_converge | 36/1000 (0.026-0.049) | 36 / 964 / 0 / 0 / 0 | 2962 | 1.461 / 1.587 | 1.461 / 1.578 | 1.502 / 1.605 |
| guard_mark_edge v trained | 692/1000 (0.663-0.720) | 692 / 151 / 157 / 0 / 0 | 1472 | 1.475 / 1.597 | 1.475 / 1.585 | 1.503 / 1.604 |
| guard_mark_edge v strike_straight | 175/1000 (0.153-0.200) | 175 / 825 / 0 / 0 / 0 | 2821 | 1.462 / 1.581 | 1.462 / 1.571 | 1.503 / 1.604 |
| guard_mark_edge v strike_flank | 120/1000 (0.101-0.142) | 120 / 880 / 0 / 0 / 0 | 2879 | 1.465 / 1.584 | 1.465 / 1.573 | 1.502 / 1.603 |
| guard_mark_edge v strike_high | 154/1000 (0.133-0.178) | 154 / 846 / 0 / 0 / 0 | 2840 | 1.462 / 1.581 | 1.462 / 1.572 | 1.501 / 1.606 |
| guard_mark_edge v strike_low | 156/1000 (0.135-0.180) | 156 / 844 / 0 / 0 / 0 | 2837 | 1.465 / 1.584 | 1.465 / 1.574 | 1.503 / 1.606 |
| guard_mark_edge v strike_sacrifice | 43/1000 (0.032-0.057) | 43 / 957 / 0 / 0 / 0 | 2955 | 1.463 / 1.585 | 1.463 / 1.574 | 1.501 / 1.607 |
| guard_mark_edge v strike_converge | 34/1000 (0.024-0.047) | 34 / 966 / 0 / 0 / 0 | 2962 | 1.458 / 1.587 | 1.458 / 1.579 | 1.501 / 1.603 |

Reading:

- The L1.10 Strike team (tag drawn 1.5-1.7 m, estimate error) reaches 41 of 1,000 (0.030-0.055) against guard_field (best Strike script strike_straight: 267).
- The L1.10 Strike team (tag drawn 1.5-1.7 m, estimate error) reaches 202 of 1,000 (0.178-0.228) against guard_parked_ring (best Strike script strike_low: 582).
- The L1.10 Strike team (tag drawn 1.5-1.7 m, estimate error) reaches 208 of 1,000 (0.184-0.234) against guard_parked_centre (best Strike script strike_low: 578).
- The L1.10 Strike team (tag drawn 1.5-1.7 m, estimate error) reaches 587 of 1,000 (0.556-0.617) against guard_mirror (best Strike script strike_straight: 181).
- The L1.10 Strike team (tag drawn 1.5-1.7 m, estimate error) reaches 692 of 1,000 (0.663-0.720) against guard_mark_edge (best Strike script strike_straight: 175).
