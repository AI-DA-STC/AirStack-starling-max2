Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator.

# L0.12 pilot

Machine NVIDIA GeForce RTX 5090 (jeremychia-X870-EAGLE-WIFI7), device cuda; gate sha256 `37e7dff182e5bb97`.

| Side | Games | Game-steps/s | s per update | Stale-tick share | Peak reserved (GiB) |
|---|---|---|---|---|---|
| strike | 8192 | 463,348 | 6.8 | 0.061 | 5.59 |
| strike | 16384 | 897,577 | 7.0 | 0.061 | 7.41 |
| strike | 32768 | 1,582,461 | 8.0 | 0.061 | 29.57 |
| guard | 8192 | 431,121 | 7.3 | 0.063 | 5.06 |
| guard | 16384 | 709,947 | 8.9 | 0.063 | 7.96 |
| guard | 32768 | 1,363,163 | 9.2 | 0.063 | 29.59 |

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
| strike | 8192 | 0.75 | 2088 | 967,451,982 | 308 | 946,864,128 |
| strike | 8192 | 0.9 | 2628 | 1,217,660,061 | 387 | 1,192,230,912 |
| strike | 8192 | 1.0 | 2988 | 1,384,465,446 | 440 | 1,355,808,768 |
| strike | 16384 | 0.75 | 2088 | 1,874,102,770 | 298 | 1,837,105,152 |
| strike | 16384 | 0.9 | 2628 | 2,358,794,168 | 375 | 2,308,964,352 |
| strike | 16384 | 1.0 | 2988 | 2,681,921,766 | 426 | 2,629,828,608 |
| strike | 32768 | 0.75 | 2088 | 3,304,112,709 | 263 | 3,246,391,296 |
| strike | 32768 | 0.9 | 2628 | 4,158,641,624 | 330 | 4,089,446,400 |
| strike | 32768 | 1.0 | 2988 | 4,728,327,567 | 376 | 4,643,094,528 |
| guard | 8192 | 0.75 | 2098 | 904,595,488 | 288 | - |
| guard | 8192 | 0.9 | 2638 | 1,137,400,807 | 362 | - |
| guard | 8192 | 1.0 | 2998 | 1,292,604,354 | 411 | - |
| guard | 16384 | 0.75 | 2098 | 1,489,638,893 | 237 | - |
| guard | 16384 | 0.9 | 2638 | 1,873,010,093 | 298 | - |
| guard | 16384 | 1.0 | 2998 | 2,128,590,893 | 338 | - |
| guard | 32768 | 0.75 | 2098 | 2,860,244,180 | 227 | - |
| guard | 32768 | 0.9 | 2638 | 3,596,352,273 | 286 | - |
| guard | 32768 | 1.0 | 2998 | 4,087,091,001 | 325 | - |

Strike learning probes (base; reaches / ended training games per update):

| Probe | Games | Per update |
|---|---|---|
| {'side': 'strike'} | 16384 | 3301/68580, 3637/73328, 3619/72670 |
| {'side': 'strike', 'opponent': 'guard_parked_centre'} | 16384 | 22250/49746, 27531/58183, 29624/60160 |
| {'side': 'strike', 'shaping_weight': 1.0} | 16384 | 3301/68580, 3917/74609, 4298/75551 |
| {'side': 'strike', 'shaping_weight': 1.0, 'opponent': 'guard_parked_centre'} | 16384 | 22250/49746, 27896/58632, 30321/61304 |

Strike recipe by the pre-registered rule ([trainer] strike_fallback): **{'recipe': 'T41 recipe', 'bare_reaches': 10557, 'fallback_reaches': 11516, 'side_overrides_strike': {}, 'by_default': False, 'note': 'picked by the probes against g*; run 0 decides whether the Strike runs launch', 'bare_reaches_parked_info': 79405, 'fallback_reaches_parked_info': 80467, 'label': 'T41 recipe'}**.

Learner positive control: run 0 (gate [run0]; LEAD CALL 21 Nov 2026, QC N-1), after this pilot: the gate's Strike recipe against the parked Guard at the budget and cap of a run of record, read at the pre-listed checkpoints. Strike runs of record need run 0 = PASS; Guard runs do not.

Hours (QC N-3): the cap reserve stops training, but nothing kills a run at --gpu-h during its final phase, so a run can use more than its asked hours; the ledger records the real hours.

| Run cap (h) | Pilot (h, this job) | Pilot + run 0 + 6 runs (h) | If run 0 FAILs: pilot + run 0 + 3 Guard runs (h) | L0.12 task cap (h) |
|---|---|---|---|---|
| 0.75 | 0.06 | 5.31 | 3.06 | 2.1 |
| 0.9 | 0.06 | 6.36 | 3.66 | 2.1 |
| 1.0 | 0.06 | 7.06 | 4.06 | 2.1 |

Worst-case final-phase timing ([pilot] timing_batches):

- base strike: main batch 12 s, INFO batch 2 s; reserve needed 268 s against the rule's 600 s
