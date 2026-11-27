# Step E judged (R52 limits; plan LS1_1P15_SWITCH.md section 3)

Training simulator, tier 1 (fast engine; Starling layer), CPU of the RTX 5090 workstation. Observed in the training simulator; not a flight result.

**What was played.** The R50 pilot networks (fitted on 1.6 m rows; `records/evidence/2026-11-27_ste_ls1_redesign_pilots/s1/`, R51: no refit) replayed at tag [1.15] m (game `configs/ste_l011/tag_1p15.toml`, `b2e09683…`), every gated and INFO cell, 1,000 games a cell on T44's starts (seed 110000), paired with step C's stored script games. Inputs: `sealed/`, `oracle_*.json` (sha256 in `inputs.sha256`); job code `code/`; logs `logs/`.

**Rule.** Gate file `configs/ste_ls1/distil_gates_1p15.toml` (`d5fdd013…`, owner R52): flips_max_games 31, cell margin 0.045, pooled 0.01, command error 0.05 / 0.05 / 0.005; headroom median ≤ 9 and ≤ 5 gated cells over 20 (plan, fixed before the run). FAIL if any gate limit is missed; else PASS if headroom holds; else MARGINAL.

**Team result and the ladder.** Each team's result is its deciding assembly at the worse of two seeds: Guard S1; Strike S2 (as at 1.6 m, S2 is the assembly after an S1 FAIL; Strike S1 has seed 1 only and does not decide). No assembly above these, no own-state check and no DAgger rescue was played at 1.15 m (R51: no refit), so a FAIL here is 'the 1.6 m networks fail at 1.15 m', not a 4.4 team FAIL after the ladder.

## Controls

| Team | Script-oracle arm (equal to the scripts game for game) | C4 analogue (fixed cells missed, need ≥ 15 of 30) |
|---|---|---|
| guard | PASS: 0 changed games in 150 cells | 26 of 30: PASS |
| strike | PASS: 0 changed games in 130 cells | 30 of 30: PASS |

## Assemblies at 1.15 m (1.6 m beside, the same networks)

| Assembly | Result | Gated cells | Over 31 | Max | Median | Over 20 | Pooled CI | Limit misses | Failed keys | At 1.6 m: result, max, median, over 20 |
|---|---|---|---|---|---|---|---|---|---|---|
| S1_guard_seed1 | **FAIL** | 150 | 12 | 68 | 5 | 25 | [-0.0027, -0.0012] | 19 | cell_margin, cmd_rmse_max, flips_max_games | PASS, 25, 3, 1 |
| S1_guard_seed2 | **FAIL** | 150 | 13 | 65 | 6 | 20 | [-0.0028, -0.0013] | 24 | cell_margin, cmd_rmse_max, flips_max_games | PASS, 24, 4, 1 |
| S2_strike_seed1 | **FAIL** | 130 | 2 | 34 | 2 | 3 | [-0.0006, +0.0002] | 2 | flips_max_games | PASS, 16, 3, 0 |
| S2_strike_seed2 | **FAIL** | 130 | 1 | 34 | 2 | 4 | [-0.0008, -0.0001] | 1 | flips_max_games | PASS, 15, 2, 0 |
| S1_strike_seed1 | **FAIL** | 130 | 5 | 90 | 2 | 8 | [-0.0009, +0.0001] | 10 | cell_margin, cmd_rmse_max, flips_max_games | FAIL, 31, 3, 3 |

Strike INFO cells (26, reported, not gated): S2_strike_seed1 max 11, median 2.5; S2_strike_seed2 max 11, median 2; S1_strike_seed1 max 30, median 2.5.

## Rungs and command error per skill (largest active-channel RMSE; limit 0.05)

| Assembly | Skill | Rung | Network | RMSE 1.15 m | RMSE 1.6 m |
|---|---|---|---|---|---|
| S1_guard_seed1 | guard_parked_ring | R2 | `B_guard_parked_ring` | 0.003 | 0.002 |
| S1_guard_seed1 | guard_mark_edge | R2 | `B_guard_mark_edge` | 0.042 | 0.007 |
| S1_guard_seed1 | guard_mirror | R2 | `B_guard_mirror` | 0.050 | 0.025 |
| S1_guard_seed1 | guard_field | R2 | `B_guard_field` | 0.068 | 0.011 |
| S1_guard_seed2 | guard_parked_ring | R2 | `B2_guard_parked_ring` | 0.003 | 0.002 |
| S1_guard_seed2 | guard_mark_edge | R2 | `B2_guard_mark_edge` | 0.043 | 0.007 |
| S1_guard_seed2 | guard_mirror | R2 | `B2_guard_mirror` | 0.053 | 0.026 |
| S1_guard_seed2 | guard_field | R2 | `B2_guard_field` | 0.066 | 0.010 |
| S2_strike_seed1 | strike_straight | R2 | `B_strike_straight` | 0.000 | 0.000 |
| S2_strike_seed1 | strike_flank | R2 | `B_strike_flank` | 0.037 | 0.027 |
| S2_strike_seed1 | strike_high | R2 | `B_strike_high` | 0.002 | 0.001 |
| S2_strike_seed1 | strike_low | R2 | `B_strike_low` | 0.003 | 0.002 |
| S2_strike_seed1 | strike_sacrifice | R3 | `A3_strike_sacrifice` | 0.027 | 0.021 |
| S2_strike_seed1 | strike_converge | R3 | `A3_strike_converge` | 0.033 | 0.032 |
| S2_strike_seed2 | strike_straight | R2 | `B2_strike_straight` | 0.000 | 0.000 |
| S2_strike_seed2 | strike_flank | R2 | `B2_strike_flank` | 0.038 | 0.027 |
| S2_strike_seed2 | strike_high | R2 | `B2_strike_high` | 0.001 | 0.001 |
| S2_strike_seed2 | strike_low | R2 | `B2_strike_low` | 0.002 | 0.001 |
| S2_strike_seed2 | strike_sacrifice | R3 | `A3s2_strike_sacrifice` | 0.027 | 0.021 |
| S2_strike_seed2 | strike_converge | R3 | `A3s2_strike_converge` | 0.033 | 0.031 |
| S1_strike_seed1 | strike_straight | R2 | `B_strike_straight` | 0.000 | 0.000 |
| S1_strike_seed1 | strike_flank | R2 | `B_strike_flank` | 0.037 | 0.027 |
| S1_strike_seed1 | strike_high | R2 | `B_strike_high` | 0.002 | 0.001 |
| S1_strike_seed1 | strike_low | R2 | `B_strike_low` | 0.003 | 0.002 |
| S1_strike_seed1 | strike_sacrifice | R2 | `B_strike_sacrifice` | 0.074 | 0.060 |
| S1_strike_seed1 | strike_converge | R2 | `B_strike_converge` | 0.075 | 0.076 |

## Team results

- **guard**: FAIL (deciding assembly S1, worse of seeds S1_guard_seed1, S1_guard_seed2; controls PASS)
- **strike**: FAIL (deciding assembly S2, worse of seeds S2_strike_seed1, S2_strike_seed2; controls PASS)

## Where the changed games are

**guard** (deciding seeds S1_guard_seed1, S1_guard_seed2; per cell the worse seed)

| Opponent | Cells | Max 1.15 m | Median 1.15 m | Max 1.6 m | Cells over 31 |
|---|---|---|---|---|---|
| strike_converge | 25 | 68 | 29 | 25 | 12 |
| strike_flank | 25 | 28 | 15 | 19 | 0 |
| strike_high | 25 | 16 | 2 | 6 | 0 |
| strike_low | 25 | 22 | 2 | 8 | 0 |
| strike_sacrifice | 25 | 32 | 11 | 16 | 1 |
| strike_straight | 25 | 17 | 4 | 12 | 0 |

Lopsided cells (scripts win under 100 or over 900 of 1,000 at 1.15 m): 22 of 150; median of the worse seed over them 0.5, over the other 128 cells 9.
Against D's noise 0.02 arm (the near-miss noise the gate must let through, C7): the network changes more games than that arm in 108 of 150 cells; the arm's own max is 19 and median 2, so the ruler still sees changes at 1.15 m.

**strike** (deciding seeds S2_strike_seed1, S2_strike_seed2; per cell the worse seed)

| Opponent | Cells | Max 1.15 m | Median 1.15 m | Max 1.6 m | Cells over 31 |
|---|---|---|---|---|---|
| guard_field | 26 | 7 | 1 | 5 | 0 |
| guard_mark_edge | 26 | 32 | 4.5 | 14 | 1 |
| guard_mirror | 26 | 34 | 4.5 | 15 | 1 |
| guard_parked_centre | 26 | 24 | 1 | 14 | 0 |
| guard_parked_ring | 26 | 23 | 1 | 16 | 0 |

Lopsided cells (scripts win under 100 or over 900 of 1,000 at 1.15 m): 30 of 130; median of the worse seed over them 1, over the other 100 cells 3.
Against D's noise 0.02 arm (the near-miss noise the gate must let through, C7): the network changes more games than that arm in 28 of 130 cells; the arm's own max is 31 and median 5, so the ruler still sees changes at 1.15 m.

## Failures (first 40 per assembly)

**S1_guard_seed1** (19 misses)

- cmd_rmse_max: guard_field vx rmse 0.0676861 > 0.05
- cmd_rmse_max: guard_field vy rmse 0.068224 > 0.05
- flips_max_games: guard_mirror+guard_mirror+guard_mirror@strike_sacrifice changed 32 games > 31
- flips_max_games: guard_mark_edge+guard_mark_edge+guard_mark_edge@strike_converge changed 65 games > 31
- flips_max_games: guard_mirror+guard_mirror+guard_mirror@strike_converge changed 63 games > 31
- flips_max_games: guard_field+guard_field+guard_field@strike_converge changed 34 games > 31
- flips_max_games: guard_mark_edge+guard_mark_edge+guard_mirror@strike_converge changed 59 games > 31
- cell_margin: guard_mark_edge+guard_mark_edge+guard_mirror@strike_converge interval [-0.045447, +0.010988] not inside +-0.045
- flips_max_games: guard_mark_edge+guard_mirror+guard_mirror@strike_converge changed 49 games > 31
- flips_max_games: guard_mirror+guard_mirror+guard_mark_edge@strike_converge changed 58 games > 31
- cell_margin: guard_mirror+guard_mirror+guard_mark_edge@strike_converge interval [-0.051769, +0.003426] not inside +-0.045
- flips_max_games: guard_parked_centre+guard_parked_centre+guard_mark_edge@strike_converge changed 44 games > 31
- cell_margin: guard_parked_centre+guard_parked_centre+guard_mark_edge@strike_converge interval [+0.010211, +0.060744] not inside +-0.045
- flips_max_games: guard_parked_centre+guard_mark_edge+guard_mark_edge@strike_converge changed 34 games > 31
- flips_max_games: guard_mark_edge+guard_mirror+guard_mark_edge@strike_converge changed 41 games > 31
- flips_max_games: guard_parked_centre+guard_mirror+guard_mark_edge@strike_converge changed 48 games > 31
- cell_margin: guard_parked_centre+guard_mirror+guard_mark_edge@strike_converge interval [-0.068994, -0.017503] not inside +-0.045
- flips_max_games: guard_mirror+guard_mark_edge+guard_mark_edge@strike_converge changed 68 games > 31
- cell_margin: guard_mirror+guard_mark_edge+guard_mark_edge@strike_converge interval [-0.061796, -0.002505] not inside +-0.045

**S1_guard_seed2** (24 misses)

- cmd_rmse_max: guard_mirror vx rmse 0.0527047 > 0.05
- cmd_rmse_max: guard_mirror vy rmse 0.0525362 > 0.05
- cmd_rmse_max: guard_field vx rmse 0.0654835 > 0.05
- cmd_rmse_max: guard_field vy rmse 0.0660439 > 0.05
- flips_max_games: guard_mirror+guard_mirror+guard_mirror@strike_sacrifice changed 32 games > 31
- flips_max_games: guard_mark_edge+guard_mark_edge+guard_mark_edge@strike_converge changed 59 games > 31
- flips_max_games: guard_mirror+guard_mirror+guard_mirror@strike_converge changed 57 games > 31
- cell_margin: guard_mirror+guard_mirror+guard_mirror@strike_converge interval [-0.048510, +0.006229] not inside +-0.045
- flips_max_games: guard_field+guard_field+guard_field@strike_converge changed 32 games > 31
- flips_max_games: guard_mark_edge+guard_mark_edge+guard_mirror@strike_converge changed 53 games > 31
- flips_max_games: guard_mark_edge+guard_mirror+guard_mirror@strike_converge changed 47 games > 31
- flips_max_games: guard_mark_edge+guard_mirror+guard_parked_centre@strike_converge changed 35 games > 31
- flips_max_games: guard_mirror+guard_mirror+guard_mark_edge@strike_converge changed 63 games > 31
- cell_margin: guard_mirror+guard_mirror+guard_mark_edge@strike_converge interval [-0.051889, +0.005588] not inside +-0.045
- flips_max_games: guard_parked_centre+guard_parked_centre+guard_mark_edge@strike_converge changed 65 games > 31
- cell_margin: guard_parked_centre+guard_parked_centre+guard_mark_edge@strike_converge interval [+0.027135, +0.086292] not inside +-0.045
- flips_max_games: guard_parked_centre+guard_mark_edge+guard_mark_edge@strike_converge changed 39 games > 31
- cell_margin: guard_parked_centre+guard_mark_edge+guard_mark_edge@strike_converge interval [-0.045184, +0.002027] not inside +-0.045
- flips_max_games: guard_mark_edge+guard_mirror+guard_mark_edge@strike_converge changed 52 games > 31
- cell_margin: guard_mark_edge+guard_mirror+guard_mark_edge@strike_converge interval [-0.052481, -0.000015] not inside +-0.045
- flips_max_games: guard_parked_centre+guard_mirror+guard_mark_edge@strike_converge changed 49 games > 31
- cell_margin: guard_parked_centre+guard_mirror+guard_mark_edge@strike_converge interval [-0.072276, -0.020408] not inside +-0.045
- flips_max_games: guard_mirror+guard_mark_edge+guard_mark_edge@strike_converge changed 65 games > 31
- cell_margin: guard_mirror+guard_mark_edge+guard_mark_edge@strike_converge interval [-0.056212, +0.001932] not inside +-0.045

**S2_strike_seed1** (2 misses)

- flips_max_games: strike_converge+strike_converge+strike_converge@guard_mark_edge changed 32 games > 31
- flips_max_games: strike_converge+strike_converge+strike_converge@guard_mirror changed 34 games > 31

**S2_strike_seed2** (1 misses)

- flips_max_games: strike_converge+strike_converge+strike_converge@guard_mirror changed 34 games > 31

**S1_strike_seed1** (10 misses)

- cmd_rmse_max: strike_sacrifice vx rmse 0.0735253 > 0.05
- cmd_rmse_max: strike_sacrifice vy rmse 0.0722092 > 0.05
- cmd_rmse_max: strike_converge vx rmse 0.0746968 > 0.05
- cmd_rmse_max: strike_converge vy rmse 0.0735235 > 0.05
- flips_max_games: strike_sacrifice+strike_sacrifice+strike_sacrifice@guard_parked_centre changed 44 games > 31
- cell_margin: strike_sacrifice+strike_sacrifice+strike_sacrifice@guard_parked_centre interval [-0.064556, -0.016706] not inside +-0.045
- flips_max_games: strike_sacrifice+strike_sacrifice+strike_sacrifice@guard_mark_edge changed 40 games > 31
- flips_max_games: strike_converge+strike_converge+strike_converge@guard_mark_edge changed 90 games > 31
- flips_max_games: strike_sacrifice+strike_sacrifice+strike_sacrifice@guard_mirror changed 41 games > 31
- flips_max_games: strike_converge+strike_converge+strike_converge@guard_mirror changed 80 games > 31

## Every cell (changed games at 1.15 m and 1.6 m per seed; script wins of the team at 1.6 m and 1.15 m; D noise 0.02)

**guard**

| Cell | Kind | S1_guard_seed1 1.15 / 1.6 | S1_guard_seed2 1.15 / 1.6 | wins 1.6 m | wins 1.15 m | D noise 0.02 |
|---|---|---|---|---|---|---|
| guard_mirror+guard_mark_edge+guard_mark_edge@strike_converge | mixed | 68 / 4 | 65 / 8 | 970 | 723 | 16 |
| guard_mark_edge+guard_mark_edge+guard_mark_edge@strike_converge | fixed | 65 / 4 | 59 / 2 | 974 | 727 | 12 |
| guard_parked_centre+guard_parked_centre+guard_mark_edge@strike_converge | mixed | 44 / 9 | 65 / 8 | 540 | 96 | 1 |
| guard_mirror+guard_mirror+guard_mirror@strike_converge | fixed | 63 / 12 | 57 / 12 | 968 | 727 | 15 |
| guard_mirror+guard_mirror+guard_mark_edge@strike_converge | mixed | 58 / 8 | 63 / 11 | 965 | 734 | 13 |
| guard_mark_edge+guard_mark_edge+guard_mirror@strike_converge | mixed | 59 / 10 | 53 / 7 | 970 | 787 | 13 |
| guard_mark_edge+guard_mirror+guard_mark_edge@strike_converge | mixed | 41 / 3 | 52 / 7 | 966 | 749 | 8 |
| guard_mark_edge+guard_mirror+guard_mirror@strike_converge | mixed | 49 / 8 | 47 / 10 | 967 | 729 | 11 |
| guard_parked_centre+guard_mirror+guard_mark_edge@strike_converge | mixed | 48 / 11 | 49 / 14 | 657 | 175 | 2 |
| guard_parked_centre+guard_mark_edge+guard_mark_edge@strike_converge | mixed | 34 / 3 | 39 / 7 | 660 | 187 | 5 |
| guard_mark_edge+guard_mirror+guard_parked_centre@strike_converge | mixed | 20 / 18 | 35 / 18 | 700 | 198 | 6 |
| guard_field+guard_field+guard_field@strike_converge | fixed | 34 / 1 | 32 / 1 | 871 | 768 | 1 |
| guard_mirror+guard_mirror+guard_mirror@strike_sacrifice | fixed | 32 / 6 | 32 / 9 | 927 | 483 | 4 |
| guard_mirror+guard_mark_edge+guard_mark_edge@strike_sacrifice | mixed | 27 / 3 | 30 / 1 | 959 | 615 | 5 |
| guard_mirror+guard_parked_centre+guard_mark_edge@strike_converge | mixed | 29 / 14 | 25 / 15 | 633 | 93 | 5 |
| guard_mirror+guard_mirror+guard_mirror@strike_flank | fixed | 28 / 19 | 25 / 18 | 864 | 549 | 7 |
| guard_mark_edge+guard_mark_edge+guard_mirror@strike_flank | mixed | 22 / 3 | 27 / 5 | 876 | 585 | 9 |
| guard_mirror+guard_parked_centre+guard_mirror@strike_flank | mixed | 21 / 13 | 25 / 11 | 733 | 325 | 8 |
| guard_mirror+guard_mark_edge+guard_parked_centre@strike_converge | mixed | 25 / 12 | 25 / 14 | 691 | 161 | 6 |
| guard_mirror+guard_mark_edge+guard_mark_edge@strike_flank | mixed | 23 / 9 | 15 / 8 | 870 | 564 | 12 |
| guard_mark_edge+guard_parked_centre+guard_mirror@strike_converge | mixed | 23 / 14 | 19 / 11 | 595 | 123 | 4 |
| guard_mirror+guard_mirror+guard_mirror@strike_low | fixed | 14 / 7 | 22 / 8 | 847 | 407 | 5 |
| guard_mark_edge+guard_parked_centre+guard_mark_edge@strike_converge | mixed | 22 / 6 | 17 / 10 | 633 | 98 | 4 |
| guard_parked_centre+guard_mirror+guard_mirror@strike_flank | mixed | 21 / 13 | 16 / 14 | 711 | 320 | 6 |
| guard_mark_edge+guard_parked_centre+guard_mirror@strike_flank | mixed | 21 / 8 | 18 / 6 | 721 | 329 | 8 |
| guard_mirror+guard_mirror+guard_mark_edge@strike_flank | mixed | 21 / 9 | 18 / 14 | 875 | 539 | 3 |
| guard_mirror+guard_mirror+guard_parked_centre@strike_converge | mixed | 21 / 25 | 20 / 24 | 691 | 189 | 8 |
| guard_parked_centre+guard_mirror+guard_mark_edge@strike_flank | mixed | 18 / 4 | 19 / 6 | 723 | 321 | 6 |
| guard_mirror+guard_mirror+guard_mark_edge@strike_sacrifice | mixed | 17 / 3 | 19 / 7 | 951 | 560 | 1 |
| guard_mirror+guard_mirror+guard_parked_centre@strike_flank | mixed | 16 / 13 | 18 / 10 | 676 | 299 | 9 |
| guard_mark_edge+guard_mirror+guard_mirror@strike_sacrifice | mixed | 18 / 6 | 16 / 5 | 927 | 497 | 5 |
| guard_mirror+guard_mirror+guard_mirror@strike_straight | fixed | 15 / 9 | 17 / 4 | 796 | 425 | 5 |
| guard_mark_edge+guard_mark_edge+guard_mark_edge@strike_flank | fixed | 12 / 4 | 17 / 1 | 887 | 607 | 19 |
| guard_parked_centre+guard_parked_centre+guard_mirror@strike_flank | mixed | 17 / 7 | 17 / 4 | 590 | 321 | 4 |
| guard_mark_edge+guard_mirror+guard_mark_edge@strike_sacrifice | mixed | 17 / 3 | 17 / 6 | 957 | 561 | 3 |
| guard_mirror+guard_parked_centre+guard_mirror@strike_converge | mixed | 17 / 18 | 12 / 19 | 585 | 112 | 5 |
| guard_mark_edge+guard_mirror+guard_mirror@strike_straight | mixed | 16 / 12 | 9 / 9 | 801 | 425 | 7 |
| guard_mark_edge+guard_mirror+guard_mirror@strike_flank | mixed | 16 / 10 | 10 / 11 | 859 | 564 | 5 |
| guard_mark_edge+guard_mirror+guard_mirror@strike_high | mixed | 11 / 2 | 16 / 4 | 852 | 397 | 1 |
| guard_mark_edge+guard_mark_edge+guard_mark_edge@strike_sacrifice | fixed | 16 / 3 | 16 / 3 | 960 | 610 | 3 |
| guard_parked_centre+guard_mirror+guard_mirror@strike_converge | mixed | 14 / 17 | 16 / 7 | 617 | 191 | 2 |
| guard_mirror+guard_parked_centre+guard_mark_edge@strike_flank | mixed | 15 / 1 | 14 / 4 | 731 | 349 | 6 |
| guard_mark_edge+guard_mirror+guard_mark_edge@strike_flank | mixed | 15 / 7 | 15 / 4 | 874 | 551 | 7 |
| guard_mirror+guard_mirror+guard_mirror@strike_high | fixed | 11 / 5 | 15 / 4 | 848 | 396 | 1 |
| guard_mark_edge+guard_mirror+guard_mirror@strike_low | mixed | 12 / 5 | 15 / 6 | 851 | 406 | 3 |
| guard_mirror+guard_mark_edge+guard_parked_centre@strike_sacrifice | mixed | 15 / 3 | 12 / 7 | 752 | 296 | 3 |
| guard_mirror+guard_mirror+guard_mark_edge@strike_straight | mixed | 13 / 9 | 14 / 7 | 800 | 423 | 2 |
| guard_mark_edge+guard_mirror+guard_mark_edge@strike_straight | mixed | 10 / 9 | 14 / 7 | 806 | 419 | 2 |
| guard_mark_edge+guard_mark_edge+guard_mirror@strike_low | mixed | 6 / 4 | 14 / 4 | 849 | 407 | 1 |
| guard_mark_edge+guard_mark_edge+guard_mirror@strike_sacrifice | mixed | 14 / 3 | 14 / 1 | 948 | 586 | 4 |
| guard_mark_edge+guard_mirror+guard_parked_centre@strike_sacrifice | mixed | 13 / 12 | 14 / 11 | 701 | 334 | 7 |
| guard_mirror+guard_mirror+guard_mark_edge@strike_low | mixed | 9 / 5 | 13 / 6 | 847 | 405 | 4 |
| guard_mark_edge+guard_mirror+guard_parked_centre@strike_flank | mixed | 12 / 6 | 8 / 4 | 675 | 305 | 3 |
| guard_mirror+guard_parked_centre+guard_mark_edge@strike_sacrifice | mixed | 9 / 7 | 12 / 7 | 791 | 315 | 4 |
| guard_mark_edge+guard_mark_edge+guard_mirror@strike_straight | mixed | 11 / 7 | 7 / 1 | 802 | 426 | 4 |
| guard_mirror+guard_mark_edge+guard_parked_centre@strike_flank | mixed | 11 / 7 | 9 / 7 | 684 | 291 | 5 |
| guard_mirror+guard_mirror+guard_parked_centre@strike_sacrifice | mixed | 11 / 16 | 8 / 13 | 703 | 330 | 1 |
| guard_mark_edge+guard_parked_centre+guard_mirror@strike_sacrifice | mixed | 11 / 7 | 9 / 7 | 729 | 326 | 8 |
| guard_parked_centre+guard_mark_edge+guard_mark_edge@strike_sacrifice | mixed | 9 / 1 | 11 / 0 | 783 | 397 | 0 |
| guard_parked_centre+guard_mirror+guard_mark_edge@strike_sacrifice | mixed | 11 / 4 | 11 / 3 | 768 | 320 | 1 |
| guard_mirror+guard_parked_centre+guard_mirror@strike_sacrifice | mixed | 11 / 13 | 11 / 7 | 721 | 319 | 5 |
| guard_mirror+guard_parked_centre+guard_parked_centre@strike_flank | mixed | 3 / 2 | 10 / 0 | 603 | 308 | 4 |
| guard_mark_edge+guard_mark_edge+guard_mirror@strike_high | mixed | 10 / 3 | 7 / 3 | 854 | 399 | 0 |
| guard_mirror+guard_mirror+guard_mark_edge@strike_high | mixed | 2 / 3 | 10 / 2 | 847 | 398 | 0 |
| guard_mark_edge+guard_mirror+guard_mark_edge@strike_high | mixed | 2 / 1 | 10 / 0 | 850 | 400 | 4 |
| guard_mark_edge+guard_parked_centre+guard_parked_centre@strike_converge | mixed | 10 / 3 | 10 / 3 | 497 | 98 | 6 |
| guard_mirror+guard_mark_edge+guard_mark_edge@strike_straight | mixed | 6 / 7 | 9 / 7 | 803 | 423 | 4 |
| guard_parked_centre+guard_mirror+guard_parked_centre@strike_flank | mixed | 9 / 4 | 9 / 3 | 562 | 290 | 1 |
| guard_mark_edge+guard_mirror+guard_mark_edge@strike_low | mixed | 9 / 2 | 8 / 5 | 850 | 405 | 1 |
| guard_mirror+guard_mark_edge+guard_mark_edge@strike_low | mixed | 6 / 1 | 9 / 1 | 845 | 407 | 2 |
| guard_mirror+guard_parked_centre+guard_parked_centre@strike_converge | mixed | 9 / 6 | 4 / 9 | 503 | 100 | 3 |
| guard_mirror+guard_parked_centre+guard_mirror@strike_straight | mixed | 7 / 6 | 8 / 6 | 652 | 197 | 1 |
| guard_field+guard_field+guard_field@strike_sacrifice | fixed | 8 / 2 | 7 / 2 | 862 | 716 | 3 |
| guard_mirror+guard_mirror+guard_parked_centre@strike_straight | mixed | 7 / 3 | 7 / 6 | 601 | 170 | 1 |
| guard_parked_ring+guard_parked_ring+guard_parked_ring@strike_sacrifice | fixed | 7 / 0 | 1 / 1 | 503 | 289 | 5 |
| guard_parked_centre+guard_mirror+guard_mirror@strike_sacrifice | mixed | 7 / 11 | 7 / 10 | 739 | 261 | 1 |
| guard_mark_edge+guard_mark_edge+guard_mark_edge@strike_straight | fixed | 4 / 3 | 6 / 2 | 808 | 422 | 4 |
| guard_parked_centre+guard_mirror+guard_mark_edge@strike_straight | mixed | 5 / 3 | 6 / 5 | 634 | 186 | 0 |
| guard_mark_edge+guard_parked_centre+guard_parked_centre@strike_flank | mixed | 3 / 2 | 6 / 1 | 579 | 278 | 5 |
| guard_mark_edge+guard_mark_edge+guard_mark_edge@strike_low | fixed | 6 / 3 | 3 / 0 | 844 | 407 | 1 |
| guard_mirror+guard_parked_centre+guard_mirror@strike_low | mixed | 2 / 3 | 6 / 7 | 580 | 133 | 0 |
| guard_mark_edge+guard_parked_centre+guard_mirror@strike_straight | mixed | 5 / 3 | 5 / 6 | 650 | 199 | 3 |
| guard_parked_centre+guard_mark_edge+guard_mark_edge@strike_flank | mixed | 5 / 5 | 1 / 2 | 717 | 341 | 3 |
| guard_parked_centre+guard_mirror+guard_mirror@strike_high | mixed | 5 / 4 | 1 / 4 | 577 | 140 | 1 |
| guard_parked_centre+guard_mirror+guard_parked_centre@strike_sacrifice | mixed | 5 / 2 | 3 / 3 | 604 | 270 | 0 |
| guard_mark_edge+guard_parked_centre+guard_mark_edge@strike_sacrifice | mixed | 5 / 3 | 4 / 1 | 796 | 319 | 1 |
| guard_parked_centre+guard_parked_centre+guard_mirror@strike_sacrifice | mixed | 4 / 10 | 5 / 8 | 631 | 277 | 1 |
| guard_parked_centre+guard_mirror+guard_parked_centre@strike_converge | mixed | 5 / 12 | 5 / 9 | 503 | 94 | 4 |
| guard_parked_centre+guard_mirror+guard_mirror@strike_straight | mixed | 4 / 6 | 4 / 7 | 631 | 188 | 1 |
| guard_mark_edge+guard_mirror+guard_parked_centre@strike_straight | mixed | 4 / 2 | 4 / 2 | 605 | 169 | 2 |
| guard_field+guard_field+guard_field@strike_flank | fixed | 4 / 3 | 4 / 2 | 808 | 766 | 1 |
| guard_mark_edge+guard_parked_centre+guard_mark_edge@strike_flank | mixed | 3 / 2 | 4 / 1 | 726 | 345 | 5 |
| guard_mirror+guard_mark_edge+guard_mark_edge@strike_high | mixed | 2 / 1 | 4 / 1 | 847 | 400 | 2 |
| guard_mirror+guard_mirror+guard_parked_centre@strike_low | mixed | 2 / 7 | 4 / 4 | 527 | 98 | 3 |
| guard_mirror+guard_mark_edge+guard_parked_centre@strike_straight | mixed | 2 / 3 | 3 / 2 | 603 | 170 | 1 |
| guard_mark_edge+guard_parked_centre+guard_mirror@strike_high | mixed | 3 / 4 | 2 / 2 | 608 | 145 | 0 |
| guard_parked_centre+guard_parked_centre+guard_mirror@strike_high | mixed | 3 / 0 | 1 / 0 | 488 | 55 | 2 |
| guard_parked_centre+guard_mirror+guard_mark_edge@strike_high | mixed | 3 / 5 | 1 / 4 | 576 | 141 | 1 |
| guard_mark_edge+guard_parked_centre+guard_mirror@strike_low | mixed | 0 / 2 | 3 / 3 | 578 | 133 | 1 |
| guard_mirror+guard_parked_centre+guard_mark_edge@strike_low | mixed | 1 / 4 | 3 / 3 | 576 | 132 | 0 |
| guard_mirror+guard_parked_centre+guard_parked_centre@strike_sacrifice | mixed | 3 / 3 | 3 / 7 | 580 | 182 | 1 |
| guard_mark_edge+guard_parked_centre+guard_parked_centre@strike_straight | mixed | 2 / 0 | 0 / 0 | 552 | 109 | 0 |
| guard_mirror+guard_parked_centre+guard_mark_edge@strike_straight | mixed | 2 / 4 | 1 / 7 | 650 | 197 | 0 |
| guard_mark_edge+guard_mark_edge+guard_mark_edge@strike_high | fixed | 2 / 0 | 2 / 1 | 850 | 402 | 2 |
| guard_mark_edge+guard_mirror+guard_parked_centre@strike_high | mixed | 1 / 1 | 2 / 3 | 564 | 127 | 0 |
| guard_mirror+guard_mirror+guard_parked_centre@strike_high | mixed | 1 / 1 | 2 / 1 | 563 | 126 | 0 |
| guard_mirror+guard_parked_centre+guard_mirror@strike_high | mixed | 2 / 4 | 1 / 5 | 616 | 144 | 0 |
| guard_mirror+guard_mark_edge+guard_parked_centre@strike_low | mixed | 2 / 6 | 2 / 5 | 529 | 99 | 3 |
| guard_parked_centre+guard_parked_centre+guard_mirror@strike_low | mixed | 2 / 1 | 1 / 1 | 459 | 39 | 2 |
| guard_parked_centre+guard_mirror+guard_mark_edge@strike_low | mixed | 2 / 1 | 1 / 3 | 554 | 111 | 1 |
| guard_parked_centre+guard_parked_centre+guard_mirror@strike_converge | mixed | 2 / 14 | 2 / 16 | 536 | 100 | 3 |
| guard_parked_centre+guard_mirror+guard_parked_centre@strike_straight | mixed | 1 / 3 | 1 / 4 | 549 | 107 | 0 |
| guard_mirror+guard_parked_centre+guard_parked_centre@strike_straight | mixed | 0 / 1 | 1 / 3 | 551 | 114 | 0 |
| guard_parked_centre+guard_parked_centre+guard_mark_edge@strike_flank | mixed | 1 / 0 | 0 / 0 | 605 | 315 | 2 |
| guard_parked_centre+guard_mirror+guard_parked_centre@strike_high | mixed | 1 / 2 | 1 / 3 | 467 | 50 | 1 |
| guard_mirror+guard_mark_edge+guard_parked_centre@strike_high | mixed | 0 / 1 | 1 / 1 | 565 | 127 | 0 |
| guard_parked_centre+guard_mirror+guard_mirror@strike_low | mixed | 1 / 2 | 1 / 5 | 548 | 109 | 1 |
| guard_mark_edge+guard_mirror+guard_parked_centre@strike_low | mixed | 1 / 5 | 1 / 2 | 527 | 97 | 3 |
| guard_mark_edge+guard_parked_centre+guard_parked_centre@strike_sacrifice | mixed | 1 / 3 | 1 / 2 | 585 | 178 | 2 |
| guard_parked_ring+guard_parked_ring+guard_parked_ring@strike_converge | fixed | 1 / 4 | 0 / 4 | 983 | 692 | 1 |
| guard_parked_centre+guard_parked_centre+guard_parked_centre@strike_straight | fixed | 0 / 0 | 0 / 0 | 534 | 101 | 1 |
| guard_parked_ring+guard_parked_ring+guard_parked_ring@strike_straight | fixed | 0 / 2 | 0 / 2 | 523 | 127 | 0 |
| guard_field+guard_field+guard_field@strike_straight | fixed | 0 / 0 | 0 / 0 | 716 | 645 | 0 |
| guard_parked_centre+guard_parked_centre+guard_mark_edge@strike_straight | mixed | 0 / 0 | 0 / 1 | 567 | 114 | 1 |
| guard_mark_edge+guard_parked_centre+guard_mark_edge@strike_straight | mixed | 0 / 2 | 0 / 2 | 648 | 195 | 0 |
| guard_parked_centre+guard_mark_edge+guard_mark_edge@strike_straight | mixed | 0 / 3 | 0 / 1 | 630 | 187 | 1 |
| guard_parked_centre+guard_parked_centre+guard_mirror@strike_straight | mixed | 0 / 2 | 0 / 0 | 567 | 115 | 0 |
| guard_parked_centre+guard_parked_centre+guard_parked_centre@strike_flank | fixed | 0 / 0 | 0 / 0 | 450 | 331 | 0 |
| guard_parked_ring+guard_parked_ring+guard_parked_ring@strike_flank | fixed | 0 / 2 | 0 / 1 | 477 | 331 | 0 |
| guard_parked_centre+guard_parked_centre+guard_parked_centre@strike_high | fixed | 0 / 0 | 0 / 0 | 466 | 31 | 0 |
| guard_parked_ring+guard_parked_ring+guard_parked_ring@strike_high | fixed | 0 / 1 | 0 / 0 | 454 | 55 | 2 |
| guard_field+guard_field+guard_field@strike_high | fixed | 0 / 0 | 0 / 0 | 734 | 645 | 0 |
| guard_mark_edge+guard_parked_centre+guard_parked_centre@strike_high | mixed | 0 / 0 | 0 / 0 | 487 | 51 | 0 |
| guard_parked_centre+guard_parked_centre+guard_mark_edge@strike_high | mixed | 0 / 0 | 0 / 0 | 493 | 54 | 0 |
| guard_mirror+guard_parked_centre+guard_mark_edge@strike_high | mixed | 0 / 2 | 0 / 3 | 607 | 145 | 0 |
| guard_mark_edge+guard_parked_centre+guard_mark_edge@strike_high | mixed | 0 / 2 | 0 / 2 | 605 | 146 | 0 |
| guard_parked_centre+guard_mark_edge+guard_mark_edge@strike_high | mixed | 0 / 4 | 0 / 4 | 576 | 141 | 0 |
| guard_mirror+guard_parked_centre+guard_parked_centre@strike_high | mixed | 0 / 4 | 0 / 6 | 485 | 53 | 1 |
| guard_parked_centre+guard_parked_centre+guard_parked_centre@strike_low | fixed | 0 / 0 | 0 / 0 | 430 | 16 | 0 |
| guard_parked_ring+guard_parked_ring+guard_parked_ring@strike_low | fixed | 0 / 2 | 0 / 2 | 424 | 34 | 1 |
| guard_field+guard_field+guard_field@strike_low | fixed | 0 / 0 | 0 / 0 | 739 | 645 | 0 |
| guard_parked_centre+guard_mirror+guard_parked_centre@strike_low | mixed | 0 / 5 | 0 / 2 | 424 | 29 | 1 |
| guard_mark_edge+guard_parked_centre+guard_parked_centre@strike_low | mixed | 0 / 0 | 0 / 0 | 447 | 35 | 0 |
| guard_parked_centre+guard_parked_centre+guard_mark_edge@strike_low | mixed | 0 / 0 | 0 / 0 | 463 | 37 | 0 |
| guard_mark_edge+guard_parked_centre+guard_mark_edge@strike_low | mixed | 0 / 0 | 0 / 0 | 576 | 133 | 1 |
| guard_parked_centre+guard_mark_edge+guard_mark_edge@strike_low | mixed | 0 / 0 | 0 / 1 | 551 | 115 | 1 |
| guard_mirror+guard_parked_centre+guard_parked_centre@strike_low | mixed | 0 / 2 | 0 / 6 | 441 | 35 | 1 |
| guard_parked_centre+guard_parked_centre+guard_parked_centre@strike_sacrifice | fixed | 0 / 0 | 0 / 0 | 525 | 210 | 4 |
| guard_parked_centre+guard_parked_centre+guard_mark_edge@strike_sacrifice | mixed | 0 / 3 | 0 / 1 | 698 | 283 | 3 |
| guard_parked_centre+guard_parked_centre+guard_parked_centre@strike_converge | fixed | 0 / 0 | 0 / 0 | 986 | 673 | 1 |

**strike**

| Cell | Kind | S2_strike_seed1 1.15 / 1.6 | S2_strike_seed2 1.15 / 1.6 | S1_strike_seed1 1.15 / 1.6 | wins 1.6 m | wins 1.15 m | D noise 0.02 |
|---|---|---|---|---|---|---|---|
| strike_converge+strike_converge+strike_converge@guard_mark_edge | fixed | 32 / 14 | 30 / 12 | 90 / 22 | 26 | 273 | 9 |
| strike_converge+strike_converge+strike_converge@guard_mirror | fixed | 34 / 10 | 34 / 11 | 80 / 31 | 32 | 273 | 24 |
| strike_sacrifice+strike_sacrifice+strike_sacrifice@guard_parked_centre | fixed | 18 / 9 | 24 / 8 | 44 / 18 | 475 | 790 | 20 |
| strike_sacrifice+strike_sacrifice+strike_sacrifice@guard_mirror | fixed | 16 / 3 | 13 / 2 | 41 / 19 | 73 | 517 | 10 |
| strike_sacrifice+strike_sacrifice+strike_sacrifice@guard_mark_edge | fixed | 11 / 3 | 12 / 2 | 40 / 7 | 40 | 390 | 17 |
| strike_converge+strike_converge+strike_converge@guard_parked_centre | fixed | 6 / 14 | 7 / 12 | 30 / 20 | 14 | 327 | 5 |
| strike_sacrifice+strike_sacrifice+strike_sacrifice@guard_parked_ring | fixed | 23 / 2 | 23 / 5 | 27 / 9 | 497 | 711 | 31 |
| strike_converge+strike_converge+strike_converge@guard_parked_ring | fixed | 10 / 16 | 8 / 15 | 27 / 24 | 17 | 308 | 7 |
| strike_flank+strike_flank+strike_flank@guard_mark_edge | fixed | 14 / 5 | 18 / 5 | 14 / 5 | 113 | 393 | 8 |
| strike_sacrifice+strike_sacrifice+strike_sacrifice@guard_field | fixed | 4 / 5 | 7 / 5 | 14 / 12 | 138 | 284 | 3 |
| strike_flank+strike_flank+strike_low@guard_mark_edge | mixed | 13 / 10 | 13 / 7 | 13 / 10 | 170 | 576 | 20 |
| strike_flank+strike_flank+strike_low@guard_mirror | mixed | 12 / 5 | 10 / 6 | 12 / 5 | 165 | 559 | 11 |
| strike_flank+strike_low+strike_flank@guard_mirror | mixed | 9 / 13 | 10 / 15 | 9 / 13 | 158 | 553 | 6 |
| strike_straight+strike_straight+strike_flank@guard_mirror | mixed | 8 / 7 | 10 / 4 | 8 / 7 | 164 | 515 | 16 |
| strike_converge+strike_converge+strike_converge@guard_field | fixed | 6 / 5 | 4 / 2 | 10 / 8 | 129 | 232 | 4 |
| strike_flank+strike_low+strike_flank@guard_mark_edge | mixed | 9 / 5 | 8 / 4 | 9 / 5 | 154 | 551 | 11 |
| strike_flank+strike_high+strike_low@guard_mark_edge | mixed | 9 / 5 | 6 / 1 | 9 / 5 | 173 | 616 | 11 |
| strike_straight+strike_straight+strike_flank@guard_mark_edge | mixed | 7 / 2 | 8 / 1 | 7 / 2 | 153 | 465 | 13 |
| strike_flank+strike_flank+strike_flank@guard_mirror | fixed | 8 / 10 | 6 / 12 | 8 / 10 | 136 | 451 | 10 |
| strike_high+strike_straight+strike_flank@guard_mirror | mixed | 8 / 4 | 8 / 2 | 8 / 4 | 162 | 540 | 10 |
| strike_high+strike_flank+strike_low@guard_mirror | mixed | 8 / 4 | 8 / 3 | 8 / 4 | 158 | 570 | 9 |
| strike_straight+strike_low+strike_low@guard_mark_edge | mixed | 5 / 2 | 7 / 3 | 5 / 2 | 184 | 643 | 11 |
| strike_low+strike_high+strike_flank@guard_mark_edge | mixed | 7 / 7 | 7 / 7 | 7 / 7 | 158 | 564 | 8 |
| strike_high+strike_flank+strike_low@guard_mark_edge | mixed | 7 / 3 | 7 / 3 | 7 / 3 | 179 | 596 | 10 |
| strike_flank+strike_low+strike_high@guard_mark_edge | mixed | 7 / 10 | 7 / 4 | 7 / 10 | 175 | 600 | 5 |
| strike_flank+strike_high+strike_high@guard_mirror | mixed | 7 / 4 | 7 / 3 | 7 / 4 | 166 | 559 | 5 |
| strike_flank+strike_high+strike_low@guard_mirror | mixed | 6 / 7 | 7 / 4 | 6 / 7 | 172 | 592 | 13 |
| strike_flank+strike_low+strike_high@guard_mirror | mixed | 5 / 6 | 7 / 7 | 5 / 6 | 168 | 574 | 10 |
| strike_flank+strike_straight+strike_straight@guard_mirror | mixed | 6 / 5 | 3 / 2 | 6 / 5 | 173 | 510 | 6 |
| strike_flank+strike_straight+strike_straight@guard_mark_edge | mixed | 3 / 0 | 5 / 0 | 3 / 0 | 151 | 492 | 10 |
| strike_flank+strike_straight+strike_high@guard_mark_edge | mixed | 5 / 5 | 5 / 2 | 5 / 5 | 177 | 545 | 8 |
| strike_high+strike_flank+strike_high@guard_mirror | mixed | 5 / 2 | 5 / 1 | 5 / 2 | 166 | 552 | 4 |
| strike_flank+strike_flank+strike_low@guard_parked_centre | mixed | 3 / 5 | 4 / 5 | 3 / 5 | 577 | 874 | 5 |
| strike_flank+strike_low+strike_flank@guard_parked_ring | mixed | 4 / 7 | 4 / 6 | 4 / 7 | 576 | 835 | 3 |
| strike_flank+strike_low+strike_high@guard_parked_ring | mixed | 4 / 8 | 2 / 7 | 4 / 8 | 566 | 910 | 2 |
| strike_flank+strike_high+strike_high@guard_mark_edge | mixed | 0 / 1 | 4 / 1 | 0 / 1 | 165 | 585 | 5 |
| strike_low+strike_straight+strike_low@guard_mark_edge | mixed | 4 / 4 | 4 / 2 | 4 / 4 | 190 | 619 | 4 |
| strike_low+strike_high+strike_straight@guard_mark_edge | mixed | 3 / 2 | 4 / 1 | 3 / 2 | 159 | 591 | 6 |
| strike_straight+strike_low+strike_high@guard_mark_edge | mixed | 4 / 2 | 3 / 1 | 4 / 2 | 170 | 626 | 7 |
| strike_flank+strike_straight+strike_high@guard_mirror | mixed | 4 / 7 | 4 / 8 | 4 / 7 | 182 | 549 | 8 |
| strike_low+strike_high+strike_straight@guard_mirror | mixed | 4 / 2 | 3 / 2 | 4 / 2 | 158 | 593 | 12 |
| strike_flank+strike_low+strike_flank@guard_field | mixed | 4 / 0 | 4 / 0 | 4 / 0 | 207 | 299 | 4 |
| strike_high+strike_flank+strike_high@guard_field | mixed | 4 / 0 | 3 / 0 | 4 / 0 | 233 | 322 | 1 |
| strike_straight+strike_straight+strike_flank@guard_field | mixed | 3 / 3 | 4 / 2 | 3 / 3 | 250 | 325 | 0 |
| strike_low+strike_high+strike_flank@guard_parked_centre | mixed | 3 / 3 | 2 / 2 | 3 / 3 | 585 | 934 | 4 |
| strike_low+strike_low+strike_low@guard_parked_ring | fixed | 3 / 5 | 3 / 6 | 3 / 5 | 576 | 966 | 0 |
| strike_straight+strike_low+strike_low@guard_parked_ring | mixed | 3 / 6 | 3 / 7 | 3 / 6 | 591 | 947 | 1 |
| strike_low+strike_straight+strike_low@guard_parked_ring | mixed | 3 / 4 | 2 / 3 | 3 / 4 | 590 | 950 | 5 |
| strike_flank+strike_flank+strike_low@guard_parked_ring | mixed | 2 / 8 | 3 / 6 | 2 / 8 | 568 | 835 | 4 |
| strike_high+strike_flank+strike_low@guard_parked_ring | mixed | 3 / 6 | 2 / 6 | 3 / 6 | 577 | 913 | 2 |
| strike_straight+strike_low+strike_high@guard_parked_ring | mixed | 3 / 5 | 1 / 4 | 3 / 5 | 564 | 942 | 1 |
| strike_low+strike_low+strike_low@guard_mark_edge | fixed | 3 / 4 | 3 / 3 | 3 / 4 | 156 | 593 | 3 |
| strike_high+strike_straight+strike_flank@guard_mark_edge | mixed | 3 / 2 | 3 / 1 | 3 / 2 | 146 | 515 | 10 |
| strike_high+strike_flank+strike_high@guard_mark_edge | mixed | 2 / 1 | 3 / 1 | 2 / 1 | 159 | 581 | 9 |
| strike_high+strike_low+strike_straight@guard_mark_edge | mixed | 3 / 1 | 3 / 2 | 3 / 1 | 151 | 589 | 7 |
| strike_straight+strike_low+strike_low@guard_mirror | mixed | 3 / 6 | 2 / 8 | 3 / 6 | 183 | 638 | 14 |
| strike_straight+strike_low+strike_high@guard_mirror | mixed | 3 / 4 | 0 / 1 | 3 / 4 | 169 | 619 | 12 |
| strike_flank+strike_flank+strike_flank@guard_field | fixed | 2 / 4 | 3 / 3 | 2 / 4 | 192 | 234 | 1 |
| strike_flank+strike_straight+strike_high@guard_field | mixed | 3 / 2 | 3 / 2 | 3 / 2 | 241 | 329 | 2 |
| strike_high+strike_flank+strike_low@guard_field | mixed | 3 / 1 | 3 / 0 | 3 / 1 | 227 | 325 | 2 |
| strike_high+strike_straight+strike_flank@guard_parked_centre | mixed | 2 / 2 | 0 / 4 | 2 / 2 | 531 | 887 | 6 |
| strike_flank+strike_low+strike_flank@guard_parked_centre | mixed | 2 / 4 | 2 / 4 | 2 / 4 | 588 | 858 | 2 |
| strike_low+strike_straight+strike_straight@guard_parked_centre | mixed | 1 / 3 | 2 / 2 | 1 / 3 | 573 | 949 | 12 |
| strike_high+strike_low+strike_straight@guard_parked_centre | mixed | 2 / 2 | 0 / 2 | 2 / 2 | 578 | 955 | 5 |
| strike_straight+strike_low+strike_straight@guard_parked_ring | mixed | 2 / 5 | 2 / 4 | 2 / 5 | 551 | 919 | 7 |
| strike_high+strike_low+strike_straight@guard_parked_ring | mixed | 2 / 5 | 2 / 6 | 2 / 5 | 574 | 932 | 6 |
| strike_high+strike_high+strike_high@guard_mark_edge | fixed | 2 / 0 | 2 / 0 | 2 / 0 | 150 | 598 | 2 |
| strike_high+strike_high+strike_high@guard_mirror | fixed | 2 / 0 | 0 / 0 | 2 / 0 | 152 | 604 | 2 |
| strike_low+strike_low+strike_low@guard_mirror | fixed | 2 / 3 | 2 / 3 | 2 / 3 | 153 | 593 | 8 |
| strike_straight+strike_low+strike_straight@guard_mirror | mixed | 2 / 5 | 1 / 5 | 2 / 5 | 148 | 603 | 13 |
| strike_high+strike_low+strike_straight@guard_mirror | mixed | 2 / 3 | 1 / 3 | 2 / 3 | 145 | 589 | 8 |
| strike_low+strike_high+strike_flank@guard_mirror | mixed | 2 / 1 | 2 / 2 | 2 / 1 | 165 | 557 | 9 |
| strike_high+strike_straight+strike_high@guard_mirror | mixed | 2 / 5 | 1 / 4 | 2 / 5 | 185 | 610 | 6 |
| strike_flank+strike_high+strike_high@guard_field | mixed | 2 / 0 | 2 / 2 | 2 / 0 | 244 | 326 | 1 |
| strike_high+strike_straight+strike_flank@guard_field | mixed | 1 / 1 | 2 / 2 | 1 / 1 | 238 | 325 | 2 |
| strike_flank+strike_low+strike_high@guard_field | mixed | 2 / 3 | 2 / 2 | 2 / 3 | 237 | 330 | 2 |
| strike_low+strike_low+strike_low@guard_parked_centre | fixed | 1 / 6 | 0 / 6 | 1 / 6 | 570 | 984 | 4 |
| strike_low+strike_straight+strike_low@guard_parked_centre | mixed | 1 / 4 | 1 / 4 | 1 / 4 | 595 | 971 | 3 |
| strike_straight+strike_low+strike_straight@guard_parked_centre | mixed | 1 / 2 | 0 / 1 | 1 / 2 | 550 | 934 | 4 |
| strike_high+strike_flank+strike_high@guard_parked_centre | mixed | 1 / 2 | 0 / 3 | 1 / 2 | 546 | 928 | 5 |
| strike_low+strike_high+strike_straight@guard_parked_centre | mixed | 1 / 4 | 1 / 3 | 1 / 4 | 574 | 964 | 5 |
| strike_high+strike_flank+strike_low@guard_parked_centre | mixed | 1 / 3 | 1 / 3 | 1 / 3 | 575 | 946 | 6 |
| strike_straight+strike_low+strike_high@guard_parked_centre | mixed | 1 / 3 | 1 / 1 | 1 / 3 | 563 | 954 | 1 |
| strike_high+strike_straight+strike_high@guard_parked_centre | mixed | 1 / 0 | 0 / 0 | 1 / 0 | 527 | 955 | 11 |
| strike_high+strike_straight+strike_flank@guard_parked_ring | mixed | 1 / 1 | 0 / 2 | 1 / 1 | 536 | 856 | 3 |
| strike_low+strike_straight+strike_straight@guard_parked_ring | mixed | 1 / 1 | 1 / 0 | 1 / 1 | 568 | 921 | 10 |
| strike_flank+strike_straight+strike_high@guard_parked_ring | mixed | 1 / 1 | 0 / 1 | 1 / 1 | 512 | 860 | 5 |
| strike_high+strike_flank+strike_high@guard_parked_ring | mixed | 1 / 0 | 1 / 1 | 1 / 0 | 551 | 897 | 2 |
| strike_low+strike_high+strike_straight@guard_parked_ring | mixed | 1 / 0 | 0 / 0 | 1 / 0 | 575 | 944 | 6 |
| strike_flank+strike_high+strike_low@guard_parked_ring | mixed | 1 / 4 | 1 / 1 | 1 / 4 | 574 | 912 | 3 |
| strike_low+strike_high+strike_flank@guard_parked_ring | mixed | 1 / 4 | 0 / 4 | 1 / 4 | 584 | 911 | 5 |
| strike_high+strike_straight+strike_high@guard_parked_ring | mixed | 1 / 0 | 0 / 0 | 1 / 0 | 531 | 926 | 4 |
| strike_straight+strike_straight+strike_straight@guard_mark_edge | fixed | 0 / 0 | 1 / 0 | 0 / 0 | 192 | 578 | 8 |
| strike_straight+strike_low+strike_straight@guard_mark_edge | mixed | 0 / 3 | 1 / 2 | 0 / 3 | 148 | 605 | 8 |
| strike_high+strike_straight+strike_high@guard_mark_edge | mixed | 1 / 1 | 1 / 1 | 1 / 1 | 182 | 610 | 3 |
| strike_low+strike_straight+strike_low@guard_mirror | mixed | 1 / 2 | 1 / 2 | 1 / 2 | 192 | 623 | 11 |
| strike_low+strike_straight+strike_straight@guard_mirror | mixed | 1 / 4 | 1 / 2 | 1 / 4 | 168 | 598 | 14 |
| strike_straight+strike_low+strike_low@guard_field | mixed | 1 / 2 | 0 / 3 | 1 / 2 | 266 | 366 | 1 |
| strike_flank+strike_straight+strike_straight@guard_field | mixed | 1 / 3 | 1 / 1 | 1 / 3 | 259 | 325 | 0 |
| strike_low+strike_straight+strike_low@guard_field | mixed | 1 / 0 | 1 / 0 | 1 / 0 | 257 | 366 | 3 |
| strike_straight+strike_low+strike_straight@guard_field | mixed | 1 / 1 | 1 / 1 | 1 / 1 | 269 | 366 | 1 |
| strike_flank+strike_flank+strike_low@guard_field | mixed | 1 / 4 | 1 / 3 | 1 / 4 | 201 | 293 | 2 |
| strike_low+strike_high+strike_straight@guard_field | mixed | 1 / 0 | 0 / 0 | 1 / 0 | 263 | 368 | 1 |
| strike_flank+strike_high+strike_low@guard_field | mixed | 1 / 3 | 1 / 4 | 1 / 3 | 239 | 330 | 1 |
| strike_straight+strike_low+strike_high@guard_field | mixed | 1 / 4 | 0 / 2 | 1 / 4 | 271 | 362 | 0 |
| strike_straight+strike_straight+strike_straight@guard_parked_centre | fixed | 0 / 0 | 0 / 0 | 0 / 0 | 466 | 899 | 17 |
| strike_flank+strike_flank+strike_flank@guard_parked_centre | fixed | 0 / 6 | 0 / 5 | 0 / 6 | 550 | 669 | 0 |
| strike_high+strike_high+strike_high@guard_parked_centre | fixed | 0 / 0 | 0 / 0 | 0 / 0 | 534 | 969 | 4 |
| strike_flank+strike_high+strike_high@guard_parked_centre | mixed | 0 / 1 | 0 / 1 | 0 / 1 | 548 | 918 | 2 |
| strike_straight+strike_low+strike_low@guard_parked_centre | mixed | 0 / 5 | 0 / 5 | 0 / 5 | 590 | 967 | 0 |
| strike_flank+strike_straight+strike_straight@guard_parked_centre | mixed | 0 / 0 | 0 / 0 | 0 / 0 | 475 | 846 | 19 |
| strike_flank+strike_straight+strike_high@guard_parked_centre | mixed | 0 / 0 | 0 / 0 | 0 / 0 | 516 | 886 | 8 |
| strike_flank+strike_high+strike_low@guard_parked_centre | mixed | 0 / 2 | 0 / 2 | 0 / 2 | 571 | 938 | 4 |
| strike_straight+strike_straight+strike_flank@guard_parked_centre | mixed | 0 / 4 | 0 / 2 | 0 / 4 | 485 | 843 | 10 |
| strike_flank+strike_low+strike_high@guard_parked_centre | mixed | 0 / 2 | 0 / 1 | 0 / 2 | 564 | 931 | 3 |
| strike_straight+strike_straight+strike_straight@guard_parked_ring | fixed | 0 / 0 | 0 / 0 | 0 / 0 | 477 | 873 | 11 |
| strike_flank+strike_flank+strike_flank@guard_parked_ring | fixed | 0 / 6 | 0 / 4 | 0 / 6 | 523 | 669 | 0 |
| strike_high+strike_high+strike_high@guard_parked_ring | fixed | 0 / 0 | 0 / 0 | 0 / 0 | 546 | 945 | 2 |
| strike_flank+strike_high+strike_high@guard_parked_ring | mixed | 0 / 2 | 0 / 1 | 0 / 2 | 551 | 896 | 3 |
| strike_flank+strike_straight+strike_straight@guard_parked_ring | mixed | 0 / 1 | 0 / 2 | 0 / 1 | 475 | 816 | 11 |
| strike_straight+strike_straight+strike_flank@guard_parked_ring | mixed | 0 / 1 | 0 / 1 | 0 / 1 | 485 | 824 | 6 |
| strike_low+strike_straight+strike_straight@guard_mark_edge | mixed | 0 / 4 | 0 / 3 | 0 / 4 | 170 | 602 | 8 |
| strike_straight+strike_straight+strike_straight@guard_mirror | fixed | 0 / 0 | 0 / 0 | 0 / 0 | 204 | 575 | 13 |
| strike_straight+strike_straight+strike_straight@guard_field | fixed | 0 / 0 | 0 / 0 | 0 / 0 | 284 | 355 | 0 |
| strike_high+strike_high+strike_high@guard_field | fixed | 0 / 0 | 0 / 0 | 0 / 0 | 266 | 355 | 0 |
| strike_low+strike_low+strike_low@guard_field | fixed | 0 / 0 | 0 / 2 | 0 / 0 | 261 | 355 | 0 |
| strike_low+strike_straight+strike_straight@guard_field | mixed | 0 / 0 | 0 / 0 | 0 / 0 | 262 | 366 | 2 |
| strike_high+strike_low+strike_straight@guard_field | mixed | 0 / 0 | 0 / 0 | 0 / 0 | 266 | 367 | 0 |
| strike_low+strike_high+strike_flank@guard_field | mixed | 0 / 4 | 0 / 4 | 0 / 4 | 232 | 329 | 1 |
| strike_high+strike_straight+strike_high@guard_field | mixed | 0 / 0 | 0 / 0 | 0 / 0 | 266 | 359 | 0 |
| strike_sacrifice+strike_sacrifice+strike_sacrifice@guard_mark_inside | info | 11 / 4 | 11 / 3 | 30 / 14 | 57 | 482 | 12 |
| strike_converge+strike_converge+strike_converge@guard_mark_inside | info | 5 / 24 | 4 / 23 | 11 / 38 | 52 | 58 | 3 |
| strike_flank+strike_flank+strike_flank@guard_mark_inside | info | 10 / 9 | 10 / 7 | 10 / 9 | 135 | 502 | 10 |
| strike_flank+strike_flank+strike_low@guard_mark_inside | info | 7 / 8 | 8 / 7 | 7 / 8 | 196 | 629 | 8 |
| strike_flank+strike_low+strike_flank@guard_mark_inside | info | 7 / 5 | 5 / 2 | 7 / 5 | 183 | 610 | 13 |
| strike_straight+strike_straight+strike_flank@guard_mark_inside | info | 7 / 1 | 2 / 0 | 7 / 1 | 160 | 560 | 7 |
| strike_flank+strike_straight+strike_straight@guard_mark_inside | info | 6 / 2 | 5 / 1 | 6 / 2 | 177 | 564 | 12 |
| strike_low+strike_high+strike_flank@guard_mark_inside | info | 5 / 5 | 4 / 4 | 5 / 5 | 197 | 625 | 6 |
| strike_flank+strike_straight+strike_high@guard_mark_inside | info | 2 / 5 | 4 / 2 | 2 / 5 | 195 | 618 | 7 |
| strike_high+strike_flank+strike_high@guard_mark_inside | info | 3 / 0 | 4 / 0 | 3 / 0 | 185 | 629 | 3 |
| strike_flank+strike_high+strike_high@guard_mark_inside | info | 3 / 5 | 2 / 4 | 3 / 5 | 182 | 628 | 0 |
| strike_high+strike_straight+strike_flank@guard_mark_inside | info | 3 / 1 | 2 / 1 | 3 / 1 | 173 | 594 | 11 |
| strike_high+strike_low+strike_straight@guard_mark_inside | info | 2 / 4 | 3 / 3 | 2 / 4 | 186 | 641 | 6 |
| strike_flank+strike_high+strike_low@guard_mark_inside | info | 3 / 9 | 1 / 8 | 3 / 9 | 203 | 651 | 6 |
| strike_straight+strike_low+strike_high@guard_mark_inside | info | 3 / 4 | 2 / 3 | 3 / 4 | 201 | 700 | 9 |
| strike_low+strike_low+strike_low@guard_mark_inside | info | 2 / 4 | 1 / 2 | 2 / 4 | 176 | 642 | 9 |
| strike_low+strike_straight+strike_low@guard_mark_inside | info | 2 / 6 | 0 / 6 | 2 / 6 | 244 | 691 | 5 |
| strike_high+strike_flank+strike_low@guard_mark_inside | info | 2 / 5 | 2 / 5 | 2 / 5 | 204 | 653 | 9 |
| strike_flank+strike_low+strike_high@guard_mark_inside | info | 2 / 6 | 0 / 6 | 2 / 6 | 202 | 647 | 9 |
| strike_straight+strike_low+strike_low@guard_mark_inside | info | 1 / 3 | 1 / 4 | 1 / 3 | 225 | 732 | 12 |
| strike_low+strike_high+strike_straight@guard_mark_inside | info | 1 / 5 | 1 / 5 | 1 / 5 | 203 | 637 | 6 |
| strike_straight+strike_straight+strike_straight@guard_mark_inside | info | 0 / 0 | 0 / 0 | 0 / 0 | 210 | 617 | 9 |
| strike_high+strike_high+strike_high@guard_mark_inside | info | 0 / 0 | 0 / 0 | 0 / 0 | 173 | 643 | 5 |
| strike_low+strike_straight+strike_straight@guard_mark_inside | info | 0 / 2 | 0 / 1 | 0 / 2 | 216 | 637 | 5 |
| strike_straight+strike_low+strike_straight@guard_mark_inside | info | 0 / 2 | 0 / 3 | 0 / 2 | 183 | 654 | 9 |
| strike_high+strike_straight+strike_high@guard_mark_inside | info | 0 / 2 | 0 / 0 | 0 / 2 | 219 | 664 | 8 |

