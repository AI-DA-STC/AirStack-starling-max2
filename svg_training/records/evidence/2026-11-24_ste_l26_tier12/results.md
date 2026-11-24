Simulators: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); training simulator, tier 2 (the same command chain driving the Isaac Lab 2.3.2 rigid-body Starling in PhysX, PX4 1.14 cascade copy). Study tag on (P1). Observed in the training simulator; nothing here is a flight result. Estimate-error values: EXPLORATORY (T63). Option B: PROPOSED (P2 open).

# L2.6: scripted 3v3 cells, tier 1 against tier 2, under the new rules (tag 1.6 m and 1.15 m, landing, option B), estimate error off and nominal (INFO)

## Controls (read these first; any control not PASS, INFO or NOT_CHECKED: no number is reported)

| Control | Status | Detail |
|---|---|---|
| tag_fires_t2 | **PASS** | tier 2, l25_landing_gy_tag_10m: 7000 games: 3 tags each, all ended at step 1 |
| condition_base_1p6 | **PASS** | tier 2 v tier 1 game: ['starling.backend', 'starling.physics_params']; tier-1 estimate error off; tier-2 parameters differ from the off file besides state_error_* in []; flies its file (error off) |
| tier1_base_1p6 | **PASS** | ran starling (tier 1, want 1); non-finite wrench or setpoint 0; upset games 0 (INFO); T44 replay (CUDA tolerances {'replay_count_tol_cuda_games': 10, 'replay_differ_tol_cuda_games': 20}): EQUAL; ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| repeat_t1_base_1p6 | **PASS** | ('guard_mark_edge', 'strike_straight'): holds 808 / 808, 0 games end otherwise (0 in outcome or end step) |
| physics_agreement_base_1p6_launch1 | **PASS** | 7000 games x 6 drones x 20 ticks on isaaclab-2.3.2: largest gap 0.00896 m (limit 0.02 m) |
| tier2_base_1p6 | **PASS** | ran physics/isaaclab-2.3.2 (tier 2, want 2); non-finite wrench or setpoint 0; upset games 0 (INFO); no known answer; ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| repeat_t2_base_1p6 | **PASS** | ('guard_mark_edge', 'strike_straight'): holds 801 / 800, 3 games end otherwise (31 in outcome or end step) |
| known_t2 | **PASS** | guard_parked_centre v strike_straight holds 539 (band 507-569: T53 (L0.13) tier 2 guard_parked_centre v strike_straight 538/1000 (0.507-0.569), T44's first 1,000 starts; T64 (L1.8, v1 at 0) 541) |
| condition_landing_1p15 | **PASS** | tier 2 v tier 1 game: ['starling.backend', 'starling.physics_params']; tier-1 estimate error off; tier-2 parameters differ from the off file besides state_error_* in []; flies its file (error off) |
| tier1_landing_1p15 | **PASS** | ran starling (tier 1, want 1); non-finite wrench or setpoint 0; upset games 0 (INFO); no known answer; ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| repeat_t1_landing_1p15 | **PASS** | ('guard_mark_edge', 'strike_straight'): holds 442 / 442, 0 games end otherwise (0 in outcome or end step) |
| physics_agreement_landing_1p15_launch1 | **PASS** | 7000 games x 6 drones x 20 ticks on isaaclab-2.3.2: largest gap 0.00896 m (limit 0.02 m) |
| tier2_landing_1p15 | **PASS** | ran physics/isaaclab-2.3.2 (tier 2, want 2); non-finite wrench or setpoint 0; upset games 0 (INFO); no known answer; ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| repeat_t2_landing_1p15 | **PASS** | ('guard_mark_edge', 'strike_straight'): holds 382 / 382, 4 games end otherwise (21 in outcome or end step) |
| condition_landing_gy_1p15 | **PASS** | tier 2 v tier 1 game: ['starling.backend', 'starling.physics_params']; tier-1 estimate error off; tier-2 parameters differ from the off file besides state_error_* in []; flies its file (error off) |
| tier1_landing_gy_1p15 | **PASS** | ran starling (tier 1, want 1); non-finite wrench or setpoint 0; upset games 0 (INFO); no known answer; ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| repeat_t1_landing_gy_1p15 | **PASS** | ('guard_mark_edge', 'strike_straight'): holds 368 / 368, 0 games end otherwise (0 in outcome or end step) |
| physics_agreement_landing_gy_1p15_launch1 | **PASS** | 7000 games x 6 drones x 20 ticks on isaaclab-2.3.2: largest gap 0.00896 m (limit 0.02 m) |
| tier2_landing_gy_1p15 | **PASS** | ran physics/isaaclab-2.3.2 (tier 2, want 2); non-finite wrench or setpoint 0; upset games 0 (INFO); no known answer; ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| repeat_t2_landing_gy_1p15 | **PASS** | ('guard_mark_edge', 'strike_straight'): holds 307 / 307, 0 games end otherwise (29 in outcome or end step) |
| condition_landing_1p6 | **PASS** | tier 2 v tier 1 game: ['starling.backend', 'starling.physics_params']; tier-1 estimate error off; tier-2 parameters differ from the off file besides state_error_* in []; flies its file (error off) |
| tier1_landing_1p6 | **PASS** | ran starling (tier 1, want 1); non-finite wrench or setpoint 0; upset games 0 (INFO); holds [802, 534, 477, 807, 895, 716] v T70 (L2.5) group landing, CPU, same starts and seed [802, 534, 477, 807, 895, 716] (+-10): within; ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| repeat_t1_landing_1p6 | **PASS** | ('guard_mark_edge', 'strike_straight'): holds 802 / 802, 0 games end otherwise (0 in outcome or end step) |
| physics_agreement_landing_1p6_launch1 | **PASS** | 7000 games x 6 drones x 20 ticks on isaaclab-2.3.2: largest gap 0.00896 m (limit 0.02 m) |
| tier2_landing_1p6 | **PASS** | ran physics/isaaclab-2.3.2 (tier 2, want 2); non-finite wrench or setpoint 0; upset games 0 (INFO); no known answer; ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| repeat_t2_landing_1p6 | **PASS** | ('guard_mark_edge', 'strike_straight'): holds 777 / 776, 1 games end otherwise (32 in outcome or end step) |
| condition_base_1p6_copy | **PASS** | tier 2 v tier 1 game: ['starling.backend', 'starling.physics_params']; tier-1 estimate error off; tier-2 parameters differ from the off file besides state_error_* in []; flies its file (error off) |
| tier1_base_1p6_copy | **PASS** | ran starling (tier 1, want 1); non-finite wrench or setpoint 0; upset games 0 (INFO); T44 replay (CUDA tolerances {'replay_count_tol_cuda_games': 10, 'replay_differ_tol_cuda_games': 20}): EQUAL; ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| repeat_t1_base_1p6_copy | **PASS** | ('guard_mark_edge', 'strike_straight'): holds 808 / 808, 0 games end otherwise (0 in outcome or end step) |
| physics_agreement_base_1p6_copy_launch1 | **PASS** | 7000 games x 6 drones x 20 ticks on isaaclab-2.3.2: largest gap 0.00896 m (limit 0.02 m) |
| tier2_base_1p6_copy | **PASS** | ran physics/isaaclab-2.3.2 (tier 2, want 2); non-finite wrench or setpoint 0; upset games 0 (INFO); no known answer; ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| repeat_t2_base_1p6_copy | **PASS** | ('guard_mark_edge', 'strike_straight'): holds 801 / 800, 3 games end otherwise (31 in outcome or end step) |
| condition_landing_gy_1p15_err | **PASS** | tier 2 v tier 1 game: ['starling.backend', 'starling.physics_params', 'estimate_error.enabled', 'estimate_error.pos_sigma_m', 'estimate_error.pos_tau_s', 'estimate_error.vel_sigma_mps', 'estimate_error.vel_tau_s']; tier-1 estimate error on; tier-2 parameters differ from the off file besides state_error_* in []; flies its file (error on) |
| tier1_landing_gy_1p15_err | **PASS** | ran starling (tier 1, want 1); non-finite wrench or setpoint 0; upset games 0 (INFO); no known answer; ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| repeat_t1_landing_gy_1p15_err | **INFO** | ('guard_mark_edge', 'strike_straight'): holds 379 / 380, 23 games end otherwise (659 in outcome or end step) (INFO: each copy draws its own estimate error) |
| physics_agreement_landing_gy_1p15_err_launch1 | **PASS** | 7000 games x 6 drones x 20 ticks on isaaclab-2.3.2: largest gap 0.00809 m (limit 0.02 m) |
| tier2_landing_gy_1p15_err | **PASS** | ran physics/isaaclab-2.3.2 (tier 2, want 2); non-finite wrench or setpoint 0; upset games 0 (INFO); no known answer; ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| repeat_t2_landing_gy_1p15_err | **INFO** | ('guard_mark_edge', 'strike_straight'): holds 300 / 296, 32 games end otherwise (722 in outcome or end step) (INFO: each copy draws its own estimate error) |
| condition_landing_1p15_err | **PASS** | tier 2 v tier 1 game: ['starling.backend', 'starling.physics_params', 'estimate_error.enabled', 'estimate_error.pos_sigma_m', 'estimate_error.pos_tau_s', 'estimate_error.vel_sigma_mps', 'estimate_error.vel_tau_s']; tier-1 estimate error on; tier-2 parameters differ from the off file besides state_error_* in []; flies its file (error on) |
| tier1_landing_1p15_err | **PASS** | ran starling (tier 1, want 1); non-finite wrench or setpoint 0; upset games 0 (INFO); no known answer; ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| repeat_t1_landing_1p15_err | **INFO** | ('guard_mark_edge', 'strike_straight'): holds 429 / 431, 28 games end otherwise (663 in outcome or end step) (INFO: each copy draws its own estimate error) |
| physics_agreement_landing_1p15_err_launch1 | **PASS** | 7000 games x 6 drones x 20 ticks on isaaclab-2.3.2: largest gap 0.00809 m (limit 0.02 m) |
| tier2_landing_1p15_err | **PASS** | ran physics/isaaclab-2.3.2 (tier 2, want 2); non-finite wrench or setpoint 0; upset games 0 (INFO); no known answer; ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| repeat_t2_landing_1p15_err | **INFO** | ('guard_mark_edge', 'strike_straight'): holds 380 / 381, 43 games end otherwise (748 in outcome or end step) (INFO: each copy draws its own estimate error) |
| condition_landing_gy_1p6 | **PASS** | tier 2 v tier 1 game: ['starling.backend', 'starling.physics_params']; tier-1 estimate error off; tier-2 parameters differ from the off file besides state_error_* in []; flies its file (error off) |
| tier1_landing_gy_1p6 | **PASS** | ran starling (tier 1, want 1); non-finite wrench or setpoint 0; upset games 0 (INFO); holds [803, 534, 477, 808, 902, 716] v T70 (L2.5) group landing_gy, CPU, same starts and seed [803, 534, 477, 808, 902, 716] (+-10): within; ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| repeat_t1_landing_gy_1p6 | **PASS** | ('guard_mark_edge', 'strike_straight'): holds 803 / 803, 0 games end otherwise (0 in outcome or end step) |
| physics_agreement_landing_gy_1p6_launch1 | **PASS** | 7000 games x 6 drones x 20 ticks on isaaclab-2.3.2: largest gap 0.00896 m (limit 0.02 m) |
| tier2_landing_gy_1p6 | **PASS** | ran physics/isaaclab-2.3.2 (tier 2, want 2); non-finite wrench or setpoint 0; upset games 0 (INFO); no known answer; ctl_paired_starts PASS; tags_one_for_one PASS; no_nonfinite_actions PASS |
| repeat_t2_landing_gy_1p6 | **PASS** | ('guard_mark_edge', 'strike_straight'): holds 781 / 780, 1 games end otherwise (25 in outcome or end step) |

## Groups played

| Group | Decision |
|---|---|
| base_1p6 | protected (worst case 254 s) |
| landing_1p15 | protected (worst case 254 s) |
| landing_gy_1p15 | protected (worst case 764 s) |
| landing_1p6 | protected (worst case 263 s) |
| base_1p6_copy | fits what is left of the cap (worst case 263 s) |
| landing_gy_1p15_err | fits what is left of the cap (worst case 1121 s) |
| landing_1p15_err | fits what is left of the cap (worst case 263 s) |
| landing_gy_1p6 | fits what is left of the cap (worst case 1138 s) |

## Tier 1 against tier 2 (1000 starts per cell, T44's first; holds, Wilson 95 %)

**base_1p6** (base rules, tag 1.6 m (T44's game): the anchor, both tiers known): **the fast engine predicts tier 2 within T13's 0.10 in this rule set, not in every cell**; T13's 0.10 limit met in every cell; tier 2's own copy agreement 0.997.

| Cell (Guard v Strike) | Tier 1 | Tier 2 | Tier 2 minus tier 1 | Word | Same outcome (share of starts) | Closest approach, any pair, min (m), tier 1 / tier 2 |
|---|---|---|---|---|---|---|
| guard_mark_edge v strike_straight | 808/1000 (0.782-0.831) | 801/1000 (0.775-0.825) | -0.007 | tier 1 predicts tier 2 | 0.913 | 1.554 / 1.552 |
| guard_parked_centre v strike_straight | 534/1000 (0.503-0.565) | 539/1000 (0.508-0.570) | +0.005 | tier 1 predicts tier 2 | 0.993 | 1.573 / 1.570 |
| guard_parked_ring v strike_flank | 477/1000 (0.446-0.508) | 564/1000 (0.533-0.594) | +0.087 | tier 2 differs, inside T13's 0.10 | 0.913 | 1.576 / 1.574 |
| guard_field v strike_flank | 808/1000 (0.782-0.831) | 831/1000 (0.807-0.853) | +0.023 | tier 1 predicts tier 2 | 0.963 | 1.554 / 1.555 |
| guard_mark_edge v strike_low | 844/1000 (0.820-0.865) | 863/1000 (0.840-0.883) | +0.019 | tier 1 predicts tier 2 | 0.923 | 1.559 / 1.559 |
| guard_field v strike_straight | 716/1000 (0.687-0.743) | 721/1000 (0.692-0.748) | +0.005 | tier 1 predicts tier 2 | 0.975 | 1.554 / 1.552 |

**landing_1p15** (landing on, even split, tag 1.15 m (the ruled tag rule at the main-training radius)): **the fast engine predicts tier 2 within T13's 0.10 in this rule set, not in every cell**; T13's 0.10 limit met in every cell; tier 2's own copy agreement 0.996.

| Cell (Guard v Strike) | Tier 1 | Tier 2 | Tier 2 minus tier 1 | Word | Same outcome (share of starts) | Closest approach, any pair, min (m), tier 1 / tier 2 |
|---|---|---|---|---|---|---|
| guard_mark_edge v strike_straight | 442/1000 (0.411-0.473) | 382/1000 (0.352-0.413) | -0.060 | tier 1 predicts tier 2 | 0.906 | 1.115 / 1.125 |
| guard_parked_centre v strike_straight | 101/1000 (0.084-0.121) | 101/1000 (0.084-0.121) | +0.000 | tier 1 predicts tier 2 | 0.996 | 1.129 / 1.133 |
| guard_parked_ring v strike_flank | 331/1000 (0.303-0.361) | 331/1000 (0.303-0.361) | +0.000 | tier 1 predicts tier 2 | 1.000 | 1.131 / 1.133 |
| guard_field v strike_flank | 753/1000 (0.725-0.779) | 708/1000 (0.679-0.735) | -0.045 | tier 1 predicts tier 2 | 0.955 | 1.126 / 1.127 |
| guard_mark_edge v strike_low | 443/1000 (0.412-0.474) | 372/1000 (0.343-0.402) | -0.071 | tier 2 differs, inside T13's 0.10 | 0.925 | 1.125 / 1.130 |
| guard_field v strike_straight | 645/1000 (0.615-0.674) | 645/1000 (0.615-0.674) | +0.000 | tier 1 predicts tier 2 | 1.000 | 1.125 / 1.128 |

**landing_gy_1p15** (landing on, option B, tag 1.15 m (the filter acts before the tag: where option B can show)): **the fast engine does not predict tier 2 in this rule set (a gap larger than T13's 0.10)**; T13's 0.10 limit NOT met in every cell; tier 2's own copy agreement 1.000.

| Cell (Guard v Strike) | Tier 1 | Tier 2 | Tier 2 minus tier 1 | Word | Same outcome (share of starts) | Closest approach, any pair, min (m), tier 1 / tier 2 |
|---|---|---|---|---|---|---|
| guard_mark_edge v strike_straight | 368/1000 (0.339-0.398) | 307/1000 (0.279-0.336) | -0.061 | tier 2 differs, inside T13's 0.10 | 0.933 | 1.114 / 1.127 |
| guard_parked_centre v strike_straight | 101/1000 (0.084-0.121) | 99/1000 (0.082-0.119) | -0.002 | tier 1 predicts tier 2 | 0.992 | 1.125 / 1.122 |
| guard_parked_ring v strike_flank | 331/1000 (0.303-0.361) | 331/1000 (0.303-0.361) | +0.000 | tier 1 predicts tier 2 | 1.000 | 1.131 / 1.133 |
| guard_field v strike_flank | 700/1000 (0.671-0.728) | 659/1000 (0.629-0.688) | -0.041 | tier 1 predicts tier 2 | 0.959 | 1.127 / 1.129 |
| guard_mark_edge v strike_low | 432/1000 (0.402-0.463) | 315/1000 (0.287-0.344) | -0.117 | tier 2 differs by more than T13's 0.10 | 0.883 | 1.124 / 1.134 |
| guard_field v strike_straight | 630/1000 (0.600-0.659) | 618/1000 (0.587-0.648) | -0.012 | tier 1 predicts tier 2 | 0.988 | 1.123 / 1.128 |

**landing_1p6** (landing on, even split, tag 1.6 m (L2.5's 'landing' rule set)): **the fast engine predicts tier 2 within T13's 0.10 in this rule set, not in every cell**; T13's 0.10 limit met in every cell; tier 2's own copy agreement 0.999.

| Cell (Guard v Strike) | Tier 1 | Tier 2 | Tier 2 minus tier 1 | Word | Same outcome (share of starts) | Closest approach, any pair, min (m), tier 1 / tier 2 |
|---|---|---|---|---|---|---|
| guard_mark_edge v strike_straight | 802/1000 (0.776-0.826) | 777/1000 (0.750-0.802) | -0.025 | tier 1 predicts tier 2 | 0.915 | 1.553 / 1.552 |
| guard_parked_centre v strike_straight | 534/1000 (0.503-0.565) | 540/1000 (0.509-0.571) | +0.006 | tier 1 predicts tier 2 | 0.994 | 1.573 / 1.570 |
| guard_parked_ring v strike_flank | 477/1000 (0.446-0.508) | 564/1000 (0.533-0.594) | +0.087 | tier 2 differs, inside T13's 0.10 | 0.913 | 1.576 / 1.574 |
| guard_field v strike_flank | 807/1000 (0.781-0.830) | 809/1000 (0.783-0.832) | +0.002 | tier 1 predicts tier 2 | 0.958 | 1.554 / 1.554 |
| guard_mark_edge v strike_low | 895/1000 (0.874-0.913) | 878/1000 (0.856-0.897) | -0.017 | tier 1 predicts tier 2 | 0.945 | 1.558 / 1.559 |
| guard_field v strike_straight | 716/1000 (0.687-0.743) | 714/1000 (0.685-0.741) | -0.002 | tier 1 predicts tier 2 | 0.976 | 1.554 / 1.552 |

**base_1p6_copy** (base_1p6 played again, a later batch of the same launch: the between-batch copy noise (lead's review, 24 Nov 2026)): **the fast engine predicts tier 2 within T13's 0.10 in this rule set, not in every cell**; T13's 0.10 limit met in every cell; tier 2's own copy agreement 0.997.

| Cell (Guard v Strike) | Tier 1 | Tier 2 | Tier 2 minus tier 1 | Word | Same outcome (share of starts) | Closest approach, any pair, min (m), tier 1 / tier 2 |
|---|---|---|---|---|---|---|
| guard_mark_edge v strike_straight | 808/1000 (0.782-0.831) | 801/1000 (0.775-0.825) | -0.007 | tier 1 predicts tier 2 | 0.913 | 1.554 / 1.552 |
| guard_parked_centre v strike_straight | 534/1000 (0.503-0.565) | 539/1000 (0.508-0.570) | +0.005 | tier 1 predicts tier 2 | 0.993 | 1.573 / 1.570 |
| guard_parked_ring v strike_flank | 477/1000 (0.446-0.508) | 564/1000 (0.533-0.594) | +0.087 | tier 2 differs, inside T13's 0.10 | 0.913 | 1.576 / 1.574 |
| guard_field v strike_flank | 808/1000 (0.782-0.831) | 831/1000 (0.807-0.853) | +0.023 | tier 1 predicts tier 2 | 0.963 | 1.554 / 1.555 |
| guard_mark_edge v strike_low | 844/1000 (0.820-0.865) | 863/1000 (0.840-0.883) | +0.019 | tier 1 predicts tier 2 | 0.923 | 1.559 / 1.559 |
| guard_field v strike_straight | 716/1000 (0.687-0.743) | 721/1000 (0.692-0.748) | +0.005 | tier 1 predicts tier 2 | 0.975 | 1.554 / 1.552 |

**landing_gy_1p15_err** (landing on, option B, tag 1.15 m, estimate error nominal on both tiers (T63 values, EXPLORATORY)): **the fast engine does not predict tier 2 in this rule set (a gap larger than T13's 0.10)**; T13's 0.10 limit NOT met in every cell; tier 2's own copy agreement 0.968.

| Cell (Guard v Strike) | Tier 1 | Tier 2 | Tier 2 minus tier 1 | Word | Same outcome (share of starts) | Closest approach, any pair, min (m), tier 1 / tier 2 |
|---|---|---|---|---|---|---|
| guard_mark_edge v strike_straight | 379/1000 (0.349-0.409) | 300/1000 (0.272-0.329) | -0.079 | tier 2 differs, inside T13's 0.10 | 0.915 | 1.114 / 1.124 |
| guard_parked_centre v strike_straight | 112/1000 (0.094-0.133) | 98/1000 (0.081-0.118) | -0.014 | tier 1 predicts tier 2 | 0.980 | 1.126 / 1.130 |
| guard_parked_ring v strike_flank | 331/1000 (0.303-0.361) | 331/1000 (0.303-0.361) | +0.000 | tier 1 predicts tier 2 | 1.000 | 1.131 / 1.132 |
| guard_field v strike_flank | 702/1000 (0.673-0.730) | 660/1000 (0.630-0.689) | -0.042 | tier 1 predicts tier 2 | 0.958 | 1.126 / 1.125 |
| guard_mark_edge v strike_low | 435/1000 (0.405-0.466) | 307/1000 (0.279-0.336) | -0.128 | tier 2 differs by more than T13's 0.10 | 0.870 | 1.124 / 1.133 |
| guard_field v strike_straight | 630/1000 (0.600-0.659) | 622/1000 (0.592-0.652) | -0.008 | tier 1 predicts tier 2 | 0.990 | 1.122 / 1.125 |

**landing_1p15_err** (landing on, even split, tag 1.15 m, estimate error nominal on both tiers (T63 values, EXPLORATORY)): **the fast engine predicts tier 2 within T13's 0.10 in this rule set, not in every cell**; T13's 0.10 limit met in every cell; tier 2's own copy agreement 0.957.

| Cell (Guard v Strike) | Tier 1 | Tier 2 | Tier 2 minus tier 1 | Word | Same outcome (share of starts) | Closest approach, any pair, min (m), tier 1 / tier 2 |
|---|---|---|---|---|---|---|
| guard_mark_edge v strike_straight | 429/1000 (0.399-0.460) | 380/1000 (0.350-0.410) | -0.049 | tier 1 predicts tier 2 | 0.915 | 1.116 / 1.123 |
| guard_parked_centre v strike_straight | 111/1000 (0.093-0.132) | 105/1000 (0.087-0.126) | -0.006 | tier 1 predicts tier 2 | 0.984 | 1.128 / 1.131 |
| guard_parked_ring v strike_flank | 331/1000 (0.303-0.361) | 331/1000 (0.303-0.361) | +0.000 | tier 1 predicts tier 2 | 1.000 | 1.130 / 1.132 |
| guard_field v strike_flank | 752/1000 (0.724-0.778) | 707/1000 (0.678-0.734) | -0.045 | tier 1 predicts tier 2 | 0.955 | 1.126 / 1.126 |
| guard_mark_edge v strike_low | 452/1000 (0.421-0.483) | 374/1000 (0.345-0.404) | -0.078 | tier 2 differs, inside T13's 0.10 | 0.912 | 1.123 / 1.132 |
| guard_field v strike_straight | 645/1000 (0.615-0.674) | 646/1000 (0.616-0.675) | +0.001 | tier 1 predicts tier 2 | 0.999 | 1.124 / 1.125 |

**landing_gy_1p6** (landing on, option B, tag 1.6 m (L2.5's 'landing_gy' rule set; option B not testable there with scripted play, T70)): **the fast engine predicts tier 2 within T13's 0.10 in this rule set, not in every cell**; T13's 0.10 limit met in every cell; tier 2's own copy agreement 0.999.

| Cell (Guard v Strike) | Tier 1 | Tier 2 | Tier 2 minus tier 1 | Word | Same outcome (share of starts) | Closest approach, any pair, min (m), tier 1 / tier 2 |
|---|---|---|---|---|---|---|
| guard_mark_edge v strike_straight | 803/1000 (0.777-0.826) | 781/1000 (0.754-0.806) | -0.022 | tier 1 predicts tier 2 | 0.920 | 1.553 / 1.552 |
| guard_parked_centre v strike_straight | 534/1000 (0.503-0.565) | 540/1000 (0.509-0.571) | +0.006 | tier 1 predicts tier 2 | 0.994 | 1.573 / 1.570 |
| guard_parked_ring v strike_flank | 477/1000 (0.446-0.508) | 564/1000 (0.533-0.594) | +0.087 | tier 2 differs, inside T13's 0.10 | 0.913 | 1.576 / 1.574 |
| guard_field v strike_flank | 808/1000 (0.782-0.831) | 813/1000 (0.788-0.836) | +0.005 | tier 1 predicts tier 2 | 0.959 | 1.554 / 1.554 |
| guard_mark_edge v strike_low | 902/1000 (0.882-0.919) | 887/1000 (0.866-0.905) | -0.015 | tier 1 predicts tier 2 | 0.949 | 1.561 / 1.558 |
| guard_field v strike_straight | 716/1000 (0.687-0.743) | 715/1000 (0.686-0.742) | -0.001 | tier 1 predicts tier 2 | 0.975 | 1.554 / 1.552 |

## Rule effects on each tier

**copy_1p6** (copy, base_1p6 -> base_1p6_copy; between-batch noise (no rule changed)): both tiers agree in 6 of 6 cells (tier1: 0 outcomes and 0 outcomes or end steps changed, repeat copies 0 / 0 outcomes, between batches 0 outcomes, copy pair (no plumbing word); tier2: 0 outcomes and 0 outcomes or end steps changed, repeat copies 4 / 4 outcomes, between batches 0 outcomes, copy pair (no plumbing word)).

| Cell | Tier 1 | Tier 1 word | Tier 2 | Tier 2 word | Across tiers |
|---|---|---|---|---|---|
| guard_mark_edge v strike_straight | 808 -> 808 | no change detected | 801 -> 801 | no change detected | both tiers agree on the rule's effect |
| guard_parked_centre v strike_straight | 534 -> 534 | no change detected | 539 -> 539 | no change detected | both tiers agree on the rule's effect |
| guard_parked_ring v strike_flank | 477 -> 477 | no change detected | 564 -> 564 | no change detected | both tiers agree on the rule's effect |
| guard_field v strike_flank | 808 -> 808 | no change detected | 831 -> 831 | no change detected | both tiers agree on the rule's effect |
| guard_mark_edge v strike_low | 844 -> 844 | no change detected | 863 -> 863 | no change detected | both tiers agree on the rule's effect |
| guard_field v strike_straight | 716 -> 716 | no change detected | 721 -> 721 | no change detected | both tiers agree on the rule's effect |

**landing_1p6** (landing, base_1p6 -> landing_1p6; P7 (landing part)): both tiers agree in 5 of 6 cells (tier1: 72 outcomes and 815 outcomes or end steps changed, repeat copies 0 / 0 outcomes, between batches 0 outcomes, reached; tier2: 83 outcomes and 732 outcomes or end steps changed, repeat copies 4 / 4 outcomes, between batches 0 outcomes, reached).

| Cell | Tier 1 | Tier 1 word | Tier 2 | Tier 2 word | Across tiers |
|---|---|---|---|---|---|
| guard_mark_edge v strike_straight | 808 -> 802 | no change detected | 801 -> 777 | no change detected | both tiers agree on the rule's effect |
| guard_parked_centre v strike_straight | 534 -> 534 | no change detected | 539 -> 540 | no change detected | both tiers agree on the rule's effect |
| guard_parked_ring v strike_flank | 477 -> 477 | no change detected | 564 -> 564 | no change detected | both tiers agree on the rule's effect |
| guard_field v strike_flank | 808 -> 807 | no change detected | 831 -> 809 | no change detected | both tiers agree on the rule's effect |
| guard_mark_edge v strike_low | 844 -> 895 | raises the Guard team's hold | 863 -> 878 | no change detected | only tier 1 detects an effect |
| guard_field v strike_straight | 716 -> 716 | no change detected | 721 -> 714 | no change detected | both tiers agree on the rule's effect |

**option_b_1p15** (option B, landing_1p15 -> landing_gy_1p15; P2): both tiers agree in 6 of 6 cells (tier1: 179 outcomes and 1672 outcomes or end steps changed, repeat copies 0 / 0 outcomes, between batches 0 outcomes, reached; tier2: 224 outcomes and 1778 outcomes or end steps changed, repeat copies 4 / 4 outcomes, between batches 0 outcomes, reached).

| Cell | Tier 1 | Tier 1 word | Tier 2 | Tier 2 word | Across tiers |
|---|---|---|---|---|---|
| guard_mark_edge v strike_straight | 442 -> 368 | lowers the Guard team's hold | 382 -> 307 | lowers the Guard team's hold | both tiers agree on the rule's effect |
| guard_parked_centre v strike_straight | 101 -> 101 | no change detected | 101 -> 99 | no change detected | both tiers agree on the rule's effect |
| guard_parked_ring v strike_flank | 331 -> 331 | no change detected | 331 -> 331 | no change detected | both tiers agree on the rule's effect |
| guard_field v strike_flank | 753 -> 700 | no change detected | 708 -> 659 | no change detected | both tiers agree on the rule's effect |
| guard_mark_edge v strike_low | 443 -> 432 | no change detected | 372 -> 315 | no change detected | both tiers agree on the rule's effect |
| guard_field v strike_straight | 645 -> 630 | no change detected | 645 -> 618 | no change detected | both tiers agree on the rule's effect |

**option_b_1p15_err** (option B, landing_1p15_err -> landing_gy_1p15_err; P2): both tiers agree in 4 of 6 cells (tier1: 167 outcomes and 1701 outcomes or end steps changed, repeat copies 0 / 0 outcomes, between batches 0 outcomes, reached; tier2: 235 outcomes and 1892 outcomes or end steps changed, repeat copies 4 / 4 outcomes, between batches 0 outcomes, reached).

| Cell | Tier 1 | Tier 1 word | Tier 2 | Tier 2 word | Across tiers |
|---|---|---|---|---|---|
| guard_mark_edge v strike_straight | 429 -> 379 | no change detected | 380 -> 300 | lowers the Guard team's hold | only tier 2 detects an effect |
| guard_parked_centre v strike_straight | 111 -> 112 | no change detected | 105 -> 98 | no change detected | both tiers agree on the rule's effect |
| guard_parked_ring v strike_flank | 331 -> 331 | no change detected | 331 -> 331 | no change detected | both tiers agree on the rule's effect |
| guard_field v strike_flank | 752 -> 702 | no change detected | 707 -> 660 | no change detected | both tiers agree on the rule's effect |
| guard_mark_edge v strike_low | 452 -> 435 | no change detected | 374 -> 307 | lowers the Guard team's hold | only tier 2 detects an effect |
| guard_field v strike_straight | 645 -> 630 | no change detected | 646 -> 622 | no change detected | both tiers agree on the rule's effect |

**option_b_1p6** (option B, landing_1p6 -> landing_gy_1p6; P2): both tiers agree in 6 of 6 cells (tier1: 33 outcomes and 447 outcomes or end steps changed, repeat copies 0 / 0 outcomes, between batches 0 outcomes, reached; tier2: 32 outcomes and 387 outcomes or end steps changed, repeat copies 4 / 4 outcomes, between batches 0 outcomes, reached).

| Cell | Tier 1 | Tier 1 word | Tier 2 | Tier 2 word | Across tiers |
|---|---|---|---|---|---|
| guard_mark_edge v strike_straight | 802 -> 803 | no change detected | 777 -> 781 | no change detected | both tiers agree on the rule's effect |
| guard_parked_centre v strike_straight | 534 -> 534 | no change detected | 540 -> 540 | no change detected | both tiers agree on the rule's effect |
| guard_parked_ring v strike_flank | 477 -> 477 | no change detected | 564 -> 564 | no change detected | both tiers agree on the rule's effect |
| guard_field v strike_flank | 807 -> 808 | no change detected | 809 -> 813 | no change detected | both tiers agree on the rule's effect |
| guard_mark_edge v strike_low | 895 -> 902 | no change detected | 878 -> 887 | no change detected | both tiers agree on the rule's effect |
| guard_field v strike_straight | 716 -> 716 | no change detected | 714 -> 715 | no change detected | both tiers agree on the rule's effect |

**tag_1p15** (tag 1.15 m, landing_1p6 -> landing_1p15; main training radius after L2): both tiers agree in 6 of 6 cells (tier1: 1524 outcomes and 5490 outcomes or end steps changed, repeat copies 0 / 0 outcomes, between batches 0 outcomes, reached; tier2: 1745 outcomes and 5474 outcomes or end steps changed, repeat copies 4 / 4 outcomes, between batches 0 outcomes, reached).

| Cell | Tier 1 | Tier 1 word | Tier 2 | Tier 2 word | Across tiers |
|---|---|---|---|---|---|
| guard_mark_edge v strike_straight | 802 -> 442 | lowers the Guard team's hold | 777 -> 382 | lowers the Guard team's hold | both tiers agree on the rule's effect |
| guard_parked_centre v strike_straight | 534 -> 101 | lowers the Guard team's hold | 540 -> 101 | lowers the Guard team's hold | both tiers agree on the rule's effect |
| guard_parked_ring v strike_flank | 477 -> 331 | lowers the Guard team's hold | 564 -> 331 | lowers the Guard team's hold | both tiers agree on the rule's effect |
| guard_field v strike_flank | 807 -> 753 | lowers the Guard team's hold | 809 -> 708 | lowers the Guard team's hold | both tiers agree on the rule's effect |
| guard_mark_edge v strike_low | 895 -> 443 | lowers the Guard team's hold | 878 -> 372 | lowers the Guard team's hold | both tiers agree on the rule's effect |
| guard_field v strike_straight | 716 -> 645 | lowers the Guard team's hold | 714 -> 645 | lowers the Guard team's hold | both tiers agree on the rule's effect |

**error_1p15** (estimate error, landing_1p15 -> landing_1p15_err; L1 (the estimator)): both tiers agree in 6 of 6 cells (tier1: 71 outcomes and 3522 outcomes or end steps changed, repeat copies 0 / 28 outcomes, between batches 0 outcomes, reached; tier2: 82 outcomes and 4074 outcomes or end steps changed, repeat copies 4 / 43 outcomes, between batches 0 outcomes, reached).

| Cell | Tier 1 | Tier 1 word | Tier 2 | Tier 2 word | Across tiers |
|---|---|---|---|---|---|
| guard_mark_edge v strike_straight | 442 -> 429 | no change detected | 382 -> 380 | no change detected | both tiers agree on the rule's effect |
| guard_parked_centre v strike_straight | 101 -> 111 | no change detected | 101 -> 105 | no change detected | both tiers agree on the rule's effect |
| guard_parked_ring v strike_flank | 331 -> 331 | no change detected | 331 -> 331 | no change detected | both tiers agree on the rule's effect |
| guard_field v strike_flank | 753 -> 752 | no change detected | 708 -> 707 | no change detected | both tiers agree on the rule's effect |
| guard_mark_edge v strike_low | 443 -> 452 | no change detected | 372 -> 374 | no change detected | both tiers agree on the rule's effect |
| guard_field v strike_straight | 645 -> 645 | no change detected | 645 -> 646 | no change detected | both tiers agree on the rule's effect |

**error_gy_1p15** (estimate error, landing_gy_1p15 -> landing_gy_1p15_err; L1 (the estimator)): both tiers agree in 6 of 6 cells (tier1: 67 outcomes and 3572 outcomes or end steps changed, repeat copies 0 / 23 outcomes, between batches 0 outcomes, reached; tier2: 101 outcomes and 4054 outcomes or end steps changed, repeat copies 4 / 32 outcomes, between batches 0 outcomes, reached).

| Cell | Tier 1 | Tier 1 word | Tier 2 | Tier 2 word | Across tiers |
|---|---|---|---|---|---|
| guard_mark_edge v strike_straight | 368 -> 379 | no change detected | 307 -> 300 | no change detected | both tiers agree on the rule's effect |
| guard_parked_centre v strike_straight | 101 -> 112 | no change detected | 99 -> 98 | no change detected | both tiers agree on the rule's effect |
| guard_parked_ring v strike_flank | 331 -> 331 | no change detected | 331 -> 331 | no change detected | both tiers agree on the rule's effect |
| guard_field v strike_flank | 700 -> 702 | no change detected | 659 -> 660 | no change detected | both tiers agree on the rule's effect |
| guard_mark_edge v strike_low | 432 -> 435 | no change detected | 315 -> 307 | no change detected | both tiers agree on the rule's effect |
| guard_field v strike_straight | 630 -> 630 | no change detected | 618 -> 622 | no change detected | both tiers agree on the rule's effect |

Tier 2 is another drone model, not a correction of tier 1: a difference between the two is a difference between two simulators.
