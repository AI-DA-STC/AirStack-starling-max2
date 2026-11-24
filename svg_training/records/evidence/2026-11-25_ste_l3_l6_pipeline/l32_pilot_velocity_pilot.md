Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator.

# L0.12 pilot

Machine NVIDIA GeForce RTX 5090 (jeremychia-X870-EAGLE-WIFI7), device cuda; gate sha256 `8d8d5b9e523f1d2e`.

| Side | Games | Game-steps/s | s per update | Stale-tick share | Peak reserved (GiB) |
|---|---|---|---|---|---|
| strike | 8192 | 506,041 | 6.2 | 0.005 | 5.29 |
| strike | 16384 | 978,683 | 6.4 | 0.005 | 7.04 |
| strike | 32768 | 1,700,586 | 7.4 | 0.005 | 29.75 |
| guard | 8192 | 468,852 | 6.7 | 0.050 | 4.86 |
| guard | 16384 | 858,709 | 7.3 | 0.050 | 7.80 |
| guard | 32768 | 1,447,887 | 8.7 | 0.050 | 29.76 |

Evaluation batch (untrained, every cell to the end): strike 11 s (8 cells, 600 ticks), guard 2 s (7 cells, 100 ticks)

Controls on this device (INFO here; gated in every run):

- strike: ctl_reference_replay **PASS**: guard_mark_edge v strike_straight: ok (holds 808 v T44 808, reaches 192 v 192; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_flank: ok (holds 887 v T44 887, reaches 113 v 113; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_high: ok (holds 850 v T44 850, reaches 150 v 150; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_low: ok (holds 844 v T44 844, reaches 156 v 156; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_sacrifice: ok (holds 960 v T44 960, reaches 40 v 40; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_converge: ok (holds 974 v T44 974, reaches 26 v 26; 0 of 1000 games differ (0 in outcome))
- strike: ctl_untrained_is_still **PASS**: untrained exploiter v zero script: holds 1000 v T44 1000, reaches 0 v 0; 0 of 1000 games differ (0 in outcome)
- strike: ctl_untrained_no_gain **PASS**: untrained 0/1000 v best script 192/1000: gain -0.192, real False (must be False)
- strike: ctl_paired_starts **PASS**: 1 start set(s), reference 5aeba7ab2b58
- strike: tags_one_for_one **PASS**: 0 games not one for one of 8000
- strike: no_nonfinite_actions **PASS**: 0 non-finite actions
- guard: ctl_reference_replay **PASS**: guard_parked_centre v strike_straight: ok (holds 534 v T44 534, reaches 466 v 466; 0 of 1000 games differ (0 in outcome)); guard_parked_ring v strike_straight: ok (holds 523 v T44 523, reaches 477 v 477; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_straight: ok (holds 808 v T44 808, reaches 192 v 192; 0 of 1000 games differ (0 in outcome)); guard_mirror v strike_straight: ok (holds 796 v T44 796, reaches 204 v 204; 0 of 1000 games differ (0 in outcome)); guard_field v strike_straight: ok (holds 716 v T44 716, reaches 284 v 284; 0 of 1000 games differ (0 in outcome))
- guard: ctl_untrained_is_still **PASS**: untrained exploiter v zero script: holds 534 v T44 534, reaches 466 v 466; 0 of 1000 games differ (0 in outcome)
- guard: ctl_untrained_no_gain **PASS**: untrained 534/1000 v best script 808/1000: gain -0.274, real False (must be False)
- guard: ctl_paired_starts **PASS**: 1 start set(s), reference 5aeba7ab2b58
- guard: tags_one_for_one **PASS**: 0 games not one for one of 7000
- guard: no_nonfinite_actions **PASS**: 0 non-finite actions

Run 0's checkpoint read (untrained Strike v the parked Guard, every game to its end): 16 s. Fill [trainer] game_steps_per_run at most the smallest of the runs' game-steps and what run 0 fits, at the chosen games and cap (LEAD CALL 21 Nov 2026, QC N-1, Q2).

| Side | Games | Run cap (h) | Training s | Game-steps | Updates | Game-steps run 0 fits (Strike) |
|---|---|---|---|---|---|---|
| strike | 8192 | 0.75 | 2089 | 1,057,317,495 | 336 | 833,617,920 |
| strike | 8192 | 0.9 | 2629 | 1,330,579,609 | 423 | 1,050,673,152 |
| strike | 8192 | 1.0 | 2989 | 1,512,754,352 | 481 | 1,195,376,640 |
| strike | 16384 | 0.75 | 2089 | 2,044,850,903 | 325 | 1,629,487,104 |
| strike | 16384 | 0.9 | 2629 | 2,573,339,538 | 409 | 2,044,723,200 |
| strike | 16384 | 1.0 | 2989 | 2,925,665,295 | 465 | 2,327,838,720 |
| strike | 32768 | 0.75 | 2089 | 3,553,189,360 | 282 | 2,894,069,760 |
| strike | 32768 | 0.9 | 2629 | 4,471,505,797 | 355 | 3,649,044,480 |
| strike | 32768 | 1.0 | 2989 | 5,083,716,756 | 404 | 4,152,360,960 |
| guard | 8192 | 0.75 | 2098 | 983,848,905 | 313 | - |
| guard | 8192 | 0.9 | 2638 | 1,237,029,195 | 393 | - |
| guard | 8192 | 1.0 | 2998 | 1,405,816,055 | 447 | - |
| guard | 16384 | 0.75 | 2098 | 1,801,930,560 | 286 | - |
| guard | 16384 | 0.9 | 2638 | 2,265,633,166 | 360 | - |
| guard | 16384 | 1.0 | 2998 | 2,574,768,237 | 409 | - |
| guard | 32768 | 0.75 | 2098 | 3,038,274,963 | 241 | - |
| guard | 32768 | 0.9 | 2638 | 3,820,134,181 | 304 | - |
| guard | 32768 | 1.0 | 2998 | 4,341,373,660 | 345 | - |

Strike learning probes (base; reaches / ended training games per update):

| Probe | Games | Per update |
|---|---|---|
| {'side': 'strike'} | 16384 | 0/31649, 0/33279, 0/27811 |
| {'side': 'strike', 'opponent': 'guard_parked_centre'} | 16384 | 0/4, 12/56, 98/190 |
| {'side': 'strike', 'shaping_weight': 1.0} | 16384 | 0/31649, 0/33566, 0/29195 |
| {'side': 'strike', 'shaping_weight': 1.0, 'opponent': 'guard_parked_centre'} | 16384 | 0/4, 17/69, 174/442 |

Strike recipe by the pre-registered rule ([trainer] strike_fallback): **{'recipe': 'shaped Strike recipe', 'bare_reaches': 0, 'fallback_reaches': 0, 'side_overrides_strike': {'shaping_weight': 1.0}, 'by_default': True, 'note': 'no reach in either probe against g*: the shaped fallback by default; run 0 decides whether the Strike runs launch', 'bare_reaches_parked_info': 110, 'fallback_reaches_parked_info': 191, 'label': 'shaped Strike recipe'}**.

Learner positive control: run 0 (gate [run0]; LEAD CALL 21 Nov 2026, QC N-1), after this pilot: the gate's Strike recipe against the parked Guard at the budget and cap of a run of record, read at the pre-listed checkpoints. Strike runs of record need run 0 = PASS; Guard runs do not.

Hours (QC N-3): the cap reserve stops training, but nothing kills a run at --gpu-h during its final phase, so a run can use more than its asked hours; the ledger records the real hours.

| Run cap (h) | Pilot (h, this job) | Pilot + run 0 + 6 runs (h) | If run 0 FAILs: pilot + run 0 + 3 Guard runs (h) | L0.12 task cap (h) |
|---|---|---|---|---|
| 0.75 | 0.06 | 5.31 | 3.06 | 1.8 |
| 0.9 | 0.06 | 6.36 | 3.66 | 1.8 |
| 1.0 | 0.06 | 7.06 | 4.06 | 1.8 |

Worst-case final-phase timing ([pilot] timing_batches):

- base strike: main batch 10 s, INFO batch 39 s; reserve needed 338 s against the rule's 600 s
