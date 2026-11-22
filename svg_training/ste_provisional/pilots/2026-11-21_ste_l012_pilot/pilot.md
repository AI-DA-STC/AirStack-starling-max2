Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator.

# L0.12 pilot

Machine NVIDIA GeForce RTX 5070 Ti Laptop GPU (jeremychia-Legion-Pro-7-16IAX10H), device cuda; gate sha256 `9220fd9f0eba545a`.

| Side | Games | Game-steps/s | s per update | Stale-tick share | Peak reserved (GiB) |
|---|---|---|---|---|---|
| strike | 8192 | 228,749 | 13.8 | 0.029 | 2.95 |
| strike | 16384 | 343,695 | 18.3 | 0.029 | 4.40 |
| strike | 32768 | 451,753 | 27.9 | 0.029 | 7.29 |
| guard | 8192 | 248,568 | 12.7 | 0.076 | 6.24 |
| guard | 16384 | 396,377 | 15.9 | 0.076 | 7.68 |
| guard | 32768 | 526,858 | 23.9 | 0.076 | 7.07 |

Evaluation batch (untrained, every cell to the end): strike 23 s (8 cells, 600 ticks), guard 3 s (7 cells, 100 ticks)

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

Run 0's checkpoint read (untrained Strike v the parked Guard, every game to its end): 27 s. Fill [trainer] game_steps_per_run at most the smallest of the runs' game-steps and what run 0 fits, at the chosen games and cap (LEAD CALL 21 Nov 2026, QC N-1, Q2).

| Side | Games | Run cap (h) | Training s | Game-steps | Updates | Game-steps run 0 fits (Strike) |
|---|---|---|---|---|---|---|
| strike | 8192 | 0.75 | 2077 | 475,081,933 | 151 | 393,216,000 |
| strike | 8192 | 0.9 | 2617 | 598,606,411 | 190 | 497,025,024 |
| strike | 8192 | 1.0 | 2977 | 680,956,062 | 216 | 566,231,040 |
| strike | 16384 | 0.75 | 2077 | 713,810,214 | 113 | 616,562,688 |
| strike | 16384 | 0.9 | 2617 | 899,405,640 | 143 | 773,849,088 |
| strike | 16384 | 1.0 | 2977 | 1,023,135,923 | 163 | 880,803,840 |
| strike | 32768 | 0.75 | 2077 | 938,231,515 | 75 | 843,055,104 |
| strike | 32768 | 0.9 | 2617 | 1,182,177,979 | 94 | 1,069,547,520 |
| strike | 32768 | 1.0 | 2977 | 1,344,808,955 | 107 | 1,220,542,464 |
| guard | 8192 | 0.75 | 2097 | 521,215,016 | 166 | - |
| guard | 8192 | 0.9 | 2637 | 655,441,902 | 208 | - |
| guard | 8192 | 1.0 | 2997 | 744,926,492 | 237 | - |
| guard | 16384 | 0.75 | 2097 | 831,150,153 | 132 | - |
| guard | 16384 | 0.9 | 2637 | 1,045,193,673 | 166 | - |
| guard | 16384 | 1.0 | 2997 | 1,187,889,353 | 189 | - |
| guard | 32768 | 0.75 | 2097 | 1,104,751,314 | 88 | - |
| guard | 32768 | 0.9 | 2637 | 1,389,254,492 | 110 | - |
| guard | 32768 | 1.0 | 2997 | 1,578,923,278 | 125 | - |

Strike learning probes (base; reaches / ended training games per update):

| Probe | Games | Per update |
|---|---|---|
| {'side': 'strike'} | 16384 | 0/31614, 0/33417, 0/28208 |
| {'side': 'strike', 'opponent': 'guard_parked_centre'} | 16384 | 0/3, 9/42, 107/216 |
| {'side': 'strike', 'shaping_weight': 1.0} | 16384 | 0/31614, 0/34051, 1/31384 |
| {'side': 'strike', 'shaping_weight': 1.0, 'opponent': 'guard_parked_centre'} | 16384 | 0/3, 12/51, 162/370 |

Strike recipe by the pre-registered rule ([trainer] strike_fallback): **{'recipe': 'shaped Strike recipe', 'bare_reaches': 0, 'fallback_reaches': 1, 'side_overrides_strike': {'shaping_weight': 1.0}, 'by_default': False, 'note': 'picked by the probes against g*; run 0 decides whether the Strike runs launch', 'bare_reaches_parked_info': 116, 'fallback_reaches_parked_info': 174, 'label': 'shaped Strike recipe'}**.

Learner positive control: run 0 (gate [run0]; LEAD CALL 21 Nov 2026, QC N-1), after this pilot: the gate's Strike recipe against the parked Guard at the budget and cap of a run of record, read at the pre-listed checkpoints. Strike runs of record need run 0 = PASS; Guard runs do not.

Hours (QC N-3): the cap reserve stops training, but nothing kills a run at --gpu-h during its final phase, so a run can use more than its asked hours; the ledger records the real hours.

| Run cap (h) | Pilot (h, this job) | Pilot + run 0 + 6 runs (h) | If run 0 FAILs: pilot + run 0 + 3 Guard runs (h) | L0.12 task cap (h) |
|---|---|---|---|---|
| 0.75 | 0.18 | 5.43 | 3.18 | 6.0 |
| 0.9 | 0.18 | 6.48 | 3.78 | 6.0 |
| 1.0 | 0.18 | 7.18 | 4.18 | 6.0 |

Worst-case final-phase timing ([pilot] timing_batches):

- tag_1p2 strike: main batch 94 s, INFO batch 74 s; reserve needed 577 s against the rule's 616 s
