Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator.

# L0.12 pilot

Machine NVIDIA GeForce RTX 5090 (jeremychia-X870-EAGLE-WIFI7), device cuda; gate sha256 `6c83762d689aa272`.

| Side | Games | Game-steps/s | s per update | Stale-tick share | Peak reserved (GiB) |
|---|---|---|---|---|---|
| strike | 8192 | 458,131 | 6.9 | 0.061 | 4.98 |
| strike | 16384 | 889,946 | 7.1 | 0.060 | 7.51 |
| strike | 32768 | 1,467,964 | 8.6 | 0.061 | 29.77 |
| guard | 8192 | 430,722 | 7.3 | 0.063 | 5.04 |
| guard | 16384 | 851,667 | 7.4 | 0.063 | 8.17 |
| guard | 32768 | 1,513,676 | 8.3 | 0.063 | 29.73 |

Evaluation batch (untrained, every cell to the end): strike 12 s (8 cells, 600 ticks), guard 2 s (7 cells, 100 ticks)

Controls on this device (INFO here; gated in every run):

- strike: ctl_reference_replay **PASS**: guard_mark_edge v strike_straight: ok (holds 808 v T44 808, reaches 192 v 192; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_flank: ok (holds 887 v T44 887, reaches 113 v 113; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_high: ok (holds 850 v T44 850, reaches 150 v 150; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_low: ok (holds 844 v T44 844, reaches 156 v 156; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_sacrifice: ok (holds 960 v T44 960, reaches 40 v 40; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_converge: ok (holds 974 v T44 974, reaches 26 v 26; 0 of 1000 games differ (0 in outcome))
- strike: ctl_untrained_is_first_skill **PASS**: untrained exploiter v strike_straight (free + first drone skill): holds 808 v T44 808, reaches 192 v 192; 0 of 1000 games differ (0 in outcome)
- strike: ctl_paired_starts **PASS**: 1 start set(s), reference 5aeba7ab2b58
- strike: tags_one_for_one **PASS**: 0 games not one for one of 8000
- strike: no_nonfinite_actions **PASS**: 0 non-finite actions
- guard: ctl_reference_replay **PASS**: guard_parked_centre v strike_straight: ok (holds 534 v T44 534, reaches 466 v 466; 0 of 1000 games differ (0 in outcome)); guard_parked_ring v strike_straight: ok (holds 523 v T44 523, reaches 477 v 477; 0 of 1000 games differ (0 in outcome)); guard_mark_edge v strike_straight: ok (holds 808 v T44 808, reaches 192 v 192; 0 of 1000 games differ (0 in outcome)); guard_mirror v strike_straight: ok (holds 796 v T44 796, reaches 204 v 204; 0 of 1000 games differ (0 in outcome)); guard_field v strike_straight: ok (holds 716 v T44 716, reaches 284 v 284; 0 of 1000 games differ (0 in outcome))
- guard: ctl_untrained_is_first_skill **PASS**: untrained exploiter v guard_parked_centre (free + first drone skill): holds 534 v T44 534, reaches 466 v 466; 0 of 1000 games differ (0 in outcome)
- guard: ctl_paired_starts **PASS**: 1 start set(s), reference 5aeba7ab2b58
- guard: tags_one_for_one **PASS**: 0 games not one for one of 7000
- guard: no_nonfinite_actions **PASS**: 0 non-finite actions

Run 0's checkpoint read (untrained Strike v the parked Guard, every game to its end): 1 s. Fill [trainer] game_steps_per_run at most the smallest of the runs' game-steps and what run 0 fits, at the chosen games and cap (LEAD CALL 21 Nov 2026, QC N-1, Q2).

| Side | Games | Run cap (h) | Training s | Game-steps | Updates | Game-steps run 0 fits (Strike) |
|---|---|---|---|---|---|---|
| strike | 8192 | 0.75 | 2088 | 956,742,678 | 304 | 937,426,944 |
| strike | 8192 | 0.9 | 2628 | 1,204,133,596 | 383 | 1,179,648,000 |
| strike | 8192 | 1.0 | 2988 | 1,369,060,874 | 435 | 1,343,225,856 |
| strike | 16384 | 0.75 | 2088 | 1,858,526,359 | 295 | 1,824,522,240 |
| strike | 16384 | 0.9 | 2628 | 2,339,097,104 | 372 | 2,296,381,440 |
| strike | 16384 | 1.0 | 2988 | 2,659,477,600 | 423 | 2,610,954,240 |
| strike | 32768 | 0.75 | 2088 | 3,065,636,629 | 244 | 3,019,898,880 |
| strike | 32768 | 0.9 | 2628 | 3,858,337,400 | 307 | 3,787,456,512 |
| strike | 32768 | 1.0 | 2988 | 4,386,804,581 | 349 | 4,315,938,816 |
| guard | 8192 | 0.75 | 2098 | 903,774,977 | 287 | - |
| guard | 8192 | 0.9 | 2638 | 1,136,365,078 | 361 | - |
| guard | 8192 | 1.0 | 2998 | 1,291,425,146 | 411 | - |
| guard | 16384 | 0.75 | 2098 | 1,787,032,603 | 284 | - |
| guard | 16384 | 0.9 | 2638 | 2,246,932,584 | 357 | - |
| guard | 16384 | 1.0 | 2998 | 2,553,532,571 | 406 | - |
| guard | 32768 | 0.75 | 2098 | 3,176,111,783 | 252 | - |
| guard | 32768 | 0.9 | 2638 | 3,993,496,841 | 317 | - |
| guard | 32768 | 1.0 | 2998 | 4,538,420,213 | 361 | - |

Strike learning probes (base; reaches / ended training games per update):

| Probe | Games | Per update |
|---|---|---|
| {'side': 'strike'} | 16384 | 3301/68580, 3753/73669, 3765/72498 |
| {'side': 'strike', 'opponent': 'guard_parked_centre'} | 16384 | 22250/49746, 27017/57572, 29157/59764 |
| {'side': 'strike', 'shaping_weight': 1.0} | 16384 | 3301/68580, 3951/74601, 4449/74954 |
| {'side': 'strike', 'shaping_weight': 1.0, 'opponent': 'guard_parked_centre'} | 16384 | 22250/49746, 27187/57892, 29488/60458 |

Strike recipe by the pre-registered rule ([trainer] strike_fallback): **{'recipe': 'T41 recipe', 'bare_reaches': 10819, 'fallback_reaches': 11701, 'side_overrides_strike': {}, 'by_default': False, 'note': 'picked by the probes against g*; run 0 decides whether the Strike runs launch', 'bare_reaches_parked_info': 78424, 'fallback_reaches_parked_info': 78925, 'label': 'T41 recipe'}**.

Learner positive control: run 0 (gate [run0]; LEAD CALL 21 Nov 2026, QC N-1), after this pilot: the gate's Strike recipe against the parked Guard at the budget and cap of a run of record, read at the pre-listed checkpoints. Strike runs of record need run 0 = PASS; Guard runs do not.

Hours (QC N-3): the cap reserve stops training, but nothing kills a run at --gpu-h during its final phase, so a run can use more than its asked hours; the ledger records the real hours.

| Run cap (h) | Pilot (h, this job) | Pilot + run 0 + 6 runs (h) | If run 0 FAILs: pilot + run 0 + 3 Guard runs (h) | L0.12 task cap (h) |
|---|---|---|---|---|
| 0.75 | 0.05 | 5.30 | 3.05 | 2.6 |
| 0.9 | 0.05 | 6.35 | 3.65 | 2.6 |
| 1.0 | 0.05 | 7.05 | 4.05 | 2.6 |

Worst-case final-phase timing ([pilot] timing_batches):

- base strike: main batch 11 s, INFO batch 2 s; reserve needed 268 s against the rule's 600 s
