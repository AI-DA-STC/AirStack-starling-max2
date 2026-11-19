Simulator: training simulator, tier 1 (the hangar game with the all-pairs safety filter, the commander copy, delay and lag of the EXPLORATORY fitted drone model, drones free in height; row 5 adds a start-height jitter). Not a flight result.

# 2026-11-18 NUS port, Phase 4 rung 5 (T23): drones free in height, with and without a start jitter (INFO)

| Item | Value |
|---|---|
| Purpose | Rows 5a and 5. Row 5a: height free, no jitter: the control that must equal row 4 game by game (plan F5: drones that start at one height and are never commanded up or down stay at it, so freeing the height alone changes nothing). Row 5: height free with the owner's start-height jitter (answer 5, 18 Nov 2026) that breaks the symmetry, so that the filter's escape can turn vertical |
| Plan | `docs/plans/2026-11-18-nus-phase4-transfer-ladder.md` v2 with the owner's answers (INFO run: each `gates.toml` has `gates = []` and the reading rules as text, written before the run) |
| Control shrunk | 5a ran the 12 core pairs only (owner, 18 Nov 2026 ~08:20, to save about 1.5 h; `configs/nus_phase4.toml` row 5a `blocks = ["core"]`). For the 12 scripted-player pairs (our Strike and our Guard blocks) row 5 has no 5a partner, so its "games that differ" column for those pairs is against row 4 (the nearest row that ran them; row 5a equals row 4 on the core pairs). The run-time estimate for 5a had been 9,326 s for these 12 pairs |
| Date, machine | 2026-11-18, row 5a 08:55 to 09:59, row 5 09:59 to 11:48 (+08:00), home RTX 5090 workstation, GPU otherwise idle |
| Code | branch `phase6-pass2` (current `main`, commit `fcbdfa72`) plus one uncommitted configuration edit (`configs/nus_phase4.toml`, row 5a `blocks = ["core"]`, owner's decision 18 Nov 2026 ~08:20); the lead commits. Rows 4, 5a, 5 and 6 ran one after the other in one detached chain (`runs/nus_port/phase4/chain_rows_4_to_6.log`, 5090 only), all exit 0 |
| Config and local files | `configs/nus_phase4.toml` (rows, pairs, counts), `configs/nus_hangar_game.toml` (generic game settings), the Starling parameter file `params/real_exploratory_v0.toml` (EXPLORATORY drone model, T5 = FAIL: it answers more slowly than the real drone, so rows 3 to 5 overstate the lag cost), git-ignored `configs/local/nus_rules.toml`, `nus_deploy.toml`, `nus_deploy_ref.toml`, `nus_hangar.toml` (no value is written here). sha256 prefixes at run time: deploy_ref `6d71c111959fd9b2`, deploy_w2 `c248c6bef3f6e17b`, game_config `3f771112bd3f0370`, hangar `b7f2870ee17d2d70`, rules `dd22cc28ce2042f3`, settings `64ae48cf4f51be37`, starts `40c8cc59297f58d5` |
| Seeds | one seed for the paired starts file (`[ladder] seed`, PROPOSED): one seed, so no method claim (STANDARDS section 6.5); the jitter (PROPOSED) is in `configs/nus_phase4.toml` and is drawn once into the starts file |

| Item | Value |
|---|---|
| Machine | home workstation, NVIDIA GeForce RTX 5090; torch 2.7.0+cu128; Python 3.11.18 |
| Games | 1000 per pair; 5a 12 pairs, 5 24 pairs; 6 drones per game, tier: tier 1 |
| Throughput | 5a 3,085 game-steps/s (18,510 drone-steps/s); 5 3,039 game-steps/s (18,234 drone-steps/s); 1000 games x 6 drones, tier 1, NVIDIA GeForce RTX 5090 |
| Run time | 5a 3,857 s (1.07 h) against its estimate of 9,326 s (2.59 h); 5 6,482 s (1.80 h) against 19,802 s (5.50 h): observed about 0.4 and 0.3 of the estimates |

## Checks of this rung

| Check | Result |
|---|---|
| Reading rule 2, row 5a against row 4, game by game (outcome), 12 core pairs x 1,000 games | **0 games differ in every one of the 12 pairs**: PASS (freeing the height alone changes nothing, as plan F5 expects) |
| Reading rule 1: ParkedGuard against ApfStrike (rows 5a, 5) | held 0.000 on both; no stop |
| Runner refusals | none; both exit 0 |

## Results

### Row 5a

| Guard | Strike | Strike reach, k/n [95 % interval] | Reach time, median s | Closest approach Guard-Strike 3-D, min / p5 / p50 m | Rule breach | Filter breach | Contact | Start miss | Games whose outcome differs from row 4 |
|---|---|---|---|---|---|---|---|---|---|
| G19 | S20 | 740/1000 [0.712, 0.766] | 33.650 | 0.901 / 1.054 / 1.092 | 7/1000 [0.003, 0.014] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| G19 | P3S | 1000/1000 [0.996, 1.000] | 5.500 | 0.595 / 1.000 / 1.057 | 51/1000 [0.039, 0.066] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| G19 | ApfStrike | 1000/1000 [0.996, 1.000] | 3.700 | 0.641 / 0.976 / 1.050 | 75/1000 [0.060, 0.093] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| P3G | S20 | 908/1000 [0.888, 0.924] | 22.200 | 0.926 / 1.056 / 1.096 | 7/1000 [0.003, 0.014] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| P3G | P3S | 1000/1000 [0.996, 1.000] | 5.250 | 0.570 / 0.999 / 1.060 | 52/1000 [at the local value, 0.068] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| P3G | ApfStrike | 1000/1000 [0.996, 1.000] | 3.700 | 0.646 / 0.979 / 1.054 | 76/1000 [0.061, 0.094] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | S20 | 1000/1000 [0.996, 1.000] | 8.450 | 0.893 / 1.031 / 1.068 | 13/1000 [0.008, 0.022] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | P3S | 1000/1000 [0.996, 1.000] | 5.250 | 0.603 / 1.006 / 1.057 | 47/1000 [0.036, 0.062] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | ApfStrike | 1000/1000 [0.996, 1.000] | at the local value | 0.503 / 0.964 / 1.057 | 79/1000 [0.064, 0.097] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | S20 | 556/1000 [0.525, 0.587] | 12.500 | 0.873 / 1.049 / 1.111 | 11/1000 [0.006, 0.020] | 1000/1000 [0.996, 1.000] | 923/1000 [0.905, 0.938] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | P3S | 1000/1000 [0.996, 1.000] | 4.300 | 0.682 / 0.987 / 1.074 | 59/1000 [0.046, 0.075] | 1000/1000 [0.996, 1.000] | 923/1000 [0.905, 0.938] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | ApfStrike | 1000/1000 [0.996, 1.000] | 3.650 | 0.526 / 0.943 / 1.059 | 106/1000 [0.088, 0.127] | 1000/1000 [0.996, 1.000] | 923/1000 [0.905, 0.938] | 1000/1000 [0.996, 1.000] | 0 |

| Guard | Strike | Same-team approach 3-D, min / p5 / p50 m | Filter corrections k/n [95 %] | Correction size mean / p95 m/s | Smoothness (change of the command per drone per tick) mean / p95 m/s | Guard 0 drift min / p50 / max m |
|---|---|---|---|---|---|---|
| G19 | S20 | 0.002 / 0.058 / 0.294 | 4597690/7196916 [0.638, 0.639] | 0.108 / 0.168 | at the local value / 0.007 | 0.312 / 1.025 / 3.148 |
| G19 | P3S | 0.002 / 0.058 / 0.294 | 561690/812532 [0.690, 0.692] | 0.179 / 0.237 | 0.006 / 0.008 | 0.274 / 0.878 / 1.904 |
| G19 | ApfStrike | 0.002 / 0.058 / 0.294 | 359308/511578 [0.701, 0.704] | 0.207 / 0.257 | 0.003 / 0.005 | 0.201 / 0.822 / 1.868 |
| P3G | S20 | 0.002 / 0.058 / 0.294 | 1902221/4195938 [0.453, 0.454] | 0.134 / 0.195 | at the local value / 0.007 | 0.369 / 1.129 / 1.977 |
| P3G | P3S | 0.002 / 0.058 / 0.294 | 483322/726732 [0.664, 0.666] | 0.184 / 0.237 | 0.007 / 0.009 | 0.307 / 0.891 / 1.734 |
| P3G | ApfStrike | 0.002 / 0.058 / 0.294 | 329768/479154 [0.687, 0.690] | 0.212 / 0.257 | 0.003 / 0.005 | 0.261 / 0.830 / 1.726 |
| ApfGuard | S20 | 0.002 / 0.058 / 0.294 | 634914/1002348 [0.632, 0.634] | 0.182 / 0.218 | 0.006 / 0.008 | 0.426 / 1.931 / 3.137 |
| ApfGuard | P3S | 0.002 / 0.058 / 0.294 | 449974/667962 [0.673, 0.675] | 0.193 / 0.237 | 0.006 / 0.008 | 0.307 / 1.435 / 2.804 |
| ApfGuard | ApfStrike | 0.002 / 0.058 / 0.294 | 410472/564546 [0.726, 0.728] | 0.216 / 0.255 | 0.002 / at the local value | 0.307 / 1.182 / 2.634 |
| ParkedGuard | S20 | 0.001 / 0.018 / 0.195 | 1140497/7827258 [0.145, 0.146] | 0.090 / 0.210 | 0.002 / 0.005 | 0.155 / 0.815 / 1.758 |
| ParkedGuard | P3S | 0.001 / 0.018 / 0.195 | 301342/545454 [0.551, 0.554] | 0.191 / 0.254 | 0.003 / 0.005 | 0.135 / 0.696 / 1.544 |
| ParkedGuard | ApfStrike | 0.001 / 0.018 / 0.195 | 279004/441252 [0.631, 0.634] | 0.212 / 0.269 | 0.000 / 0.001 | 0.120 / 0.673 / 1.492 |

### Row 5

| Guard | Strike | Strike reach, k/n [95 % interval] | Reach time, median s | Closest approach Guard-Strike 3-D, min / p5 / p50 m | Rule breach | Filter breach | Contact | Start miss | Games whose outcome differs from row 5a |
|---|---|---|---|---|---|---|---|---|---|
| G19 | S20 | 983/1000 [0.973, 0.989] | 25.300 | 0.889 / 1.056 / 1.094 | 5/1000 [0.002, 0.012] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 251 |
| G19 | P3S | 1000/1000 [0.996, 1.000] | 5.450 | 0.678 / 1.000 / 1.056 | 50/1000 [0.038, 0.065] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| G19 | ApfStrike | 1000/1000 [0.996, 1.000] | 3.700 | 0.732 / 0.981 / 1.050 | 73/1000 [0.058, 0.091] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| P3G | S20 | 924/1000 [0.906, 0.939] | 19.950 | 0.885 / 1.056 / 1.097 | 4/1000 [0.002, at the local value] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 56 |
| P3G | P3S | 1000/1000 [0.996, 1.000] | 5.250 | 0.767 / 0.998 / 1.060 | 52/1000 [at the local value, 0.068] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| P3G | ApfStrike | 1000/1000 [0.996, 1.000] | 3.700 | 0.718 / 0.981 / 1.054 | 67/1000 [0.053, 0.084] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | S20 | 1000/1000 [0.996, 1.000] | 8.400 | 0.884 / 1.031 / 1.068 | 12/1000 [0.007, 0.021] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | P3S | 1000/1000 [0.996, 1.000] | 5.200 | 0.713 / 0.998 / 1.057 | 52/1000 [at the local value, 0.068] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | ApfStrike | 1000/1000 [0.996, 1.000] | at the local value | 0.479 / 0.981 / 1.057 | 75/1000 [0.060, 0.093] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | S20 | 571/1000 [0.540, 0.601] | 13.050 | 0.879 / 1.052 / 1.115 | 6/1000 [0.003, 0.013] | 1000/1000 [0.996, 1.000] | 923/1000 [0.905, 0.938] | 1000/1000 [0.996, 1.000] | 67 |
| ParkedGuard | P3S | 1000/1000 [0.996, 1.000] | 4.300 | 0.647 / 1.000 / 1.077 | 52/1000 [at the local value, 0.068] | 1000/1000 [0.996, 1.000] | 923/1000 [0.905, 0.938] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | ApfStrike | 1000/1000 [0.996, 1.000] | 3.650 | 0.561 / 0.965 / 1.061 | 84/1000 [0.068, 0.103] | 1000/1000 [0.996, 1.000] | 923/1000 [0.905, 0.938] | 1000/1000 [0.996, 1.000] | 0 |
| G19 | strike_straight | 1000/1000 [0.996, 1.000] | 3.700 | 0.797 / 0.982 / 1.050 | 77/1000 [0.062, 0.095] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| G19 | strike_flank | 1000/1000 [0.996, 1.000] | 9.850 | 0.616 / 1.003 / 1.049 | 46/1000 [0.035, 0.061] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 202 |
| P3G | strike_straight | 1000/1000 [0.996, 1.000] | 3.700 | 0.799 / 0.983 / 1.054 | 73/1000 [0.058, 0.091] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| P3G | strike_flank | 1000/1000 [0.996, 1.000] | 8.550 | 0.643 / 1.010 / 1.053 | 34/1000 [0.024, 0.047] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 22 |
| ParkedGuard | strike_straight | 1000/1000 [0.996, 1.000] | 3.650 | 0.642 / 0.961 / 1.060 | 86/1000 [0.070, 0.105] | 1000/1000 [0.996, 1.000] | 923/1000 [0.905, 0.938] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | strike_flank | 1000/1000 [0.996, 1.000] | 6.150 | 0.678 / 1.005 / 1.055 | 47/1000 [0.036, 0.062] | 1000/1000 [0.996, 1.000] | 923/1000 [0.905, 0.938] | 1000/1000 [0.996, 1.000] | 55 |
| guard_mirror | S20 | 1000/1000 [0.996, 1.000] | 9.500 | 0.887 / 1.032 / 1.071 | 8/1000 [at the local value, 0.016] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 144 |
| guard_mirror | P3S | 1000/1000 [0.996, 1.000] | 4.500 | 0.625 / 1.008 / 1.063 | 35/1000 [0.025, 0.048] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 20 |
| guard_mirror | ApfStrike | 959/1000 [0.945, 0.970] | 3.650 | 0.711 / 0.990 / 1.062 | 64/1000 [0.050, 0.081] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 7 |
| guard_mark_edge | S20 | 1000/1000 [0.996, 1.000] | 14.250 | 0.907 / 1.038 / 1.075 | 8/1000 [at the local value, 0.016] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 6 |
| guard_mark_edge | P3S | 1000/1000 [0.996, 1.000] | 4.900 | 0.666 / 1.010 / 1.066 | 37/1000 [0.027, 0.051] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| guard_mark_edge | ApfStrike | 962/1000 [0.948, 0.972] | 3.650 | 0.707 / 0.985 / 1.061 | 65/1000 [0.051, 0.082] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 6 |

| Guard | Strike | Same-team approach 3-D, min / p5 / p50 m | Filter corrections k/n [95 %] | Correction size mean / p95 m/s | Smoothness (change of the command per drone per tick) mean / p95 m/s | Guard 0 drift min / p50 / max m |
|---|---|---|---|---|---|---|
| G19 | S20 | 0.003 / 0.058 / 0.294 | 1958055/3639348 [0.538, 0.539] | 0.098 / 0.157 | 0.003 / 0.005 | 0.330 / 0.978 / 1.959 |
| G19 | P3S | 0.003 / 0.058 / 0.294 | 511401/762318 [0.670, 0.672] | 0.179 / 0.237 | 0.006 / 0.008 | 0.268 / 0.876 / 1.876 |
| G19 | ApfStrike | 0.003 / 0.058 / 0.294 | 336778/489540 [0.687, 0.689] | 0.207 / 0.257 | 0.003 / 0.005 | 0.201 / 0.825 / 1.827 |
| P3G | S20 | 0.003 / 0.058 / 0.294 | 1213513/3524910 [0.344, 0.345] | 0.126 / 0.187 | at the local value / 0.006 | 0.372 / 1.107 / 1.990 |
| P3G | P3S | 0.003 / 0.058 / 0.294 | 457557/701436 [0.651, 0.653] | 0.184 / 0.236 | 0.007 / 0.009 | 0.307 / 0.889 / 1.702 |
| P3G | ApfStrike | 0.003 / 0.058 / 0.294 | 325610/475452 [0.684, 0.686] | 0.212 / 0.258 | 0.003 / 0.005 | 0.262 / 0.830 / 1.721 |
| ApfGuard | S20 | 0.003 / 0.058 / 0.294 | 626493/994974 [0.629, 0.631] | 0.181 / 0.217 | 0.006 / 0.008 | 0.426 / 1.924 / 3.132 |
| ApfGuard | P3S | 0.003 / 0.058 / 0.294 | 446409/664236 [0.671, 0.673] | 0.193 / 0.237 | 0.006 / 0.008 | 0.307 / 1.430 / 2.805 |
| ApfGuard | ApfStrike | 0.003 / 0.058 / 0.294 | 406513/562800 [0.721, 0.723] | 0.215 / 0.254 | 0.002 / at the local value | 0.307 / 1.182 / 3.046 |
| ParkedGuard | S20 | 0.001 / 0.018 / 0.195 | 922259/7660314 [0.120, 0.121] | 0.090 / 0.211 | 0.002 / 0.005 | 0.155 / 0.794 / 1.755 |
| ParkedGuard | P3S | 0.001 / 0.018 / 0.195 | 295119/545238 [0.540, 0.543] | 0.190 / 0.255 | 0.003 / 0.005 | 0.135 / 0.684 / 1.542 |
| ParkedGuard | ApfStrike | 0.001 / 0.018 / 0.195 | 274065/439542 [0.622, 0.625] | 0.211 / 0.269 | 0.000 / 0.001 | 0.120 / 0.655 / 1.426 |
| G19 | strike_straight | 0.003 / 0.058 / 0.294 | 340253/493044 [0.689, 0.691] | 0.207 / 0.258 | 0.003 / at the local value | 0.198 / 0.826 / 1.827 |
| G19 | strike_flank | 0.003 / 0.058 / 0.294 | 1053935/1241898 [0.848, 0.849] | 0.182 / 0.216 | 0.011 / 0.025 | 0.292 / 0.905 / 3.917 |
| P3G | strike_straight | 0.003 / 0.058 / 0.294 | 328266/478158 [0.685, 0.688] | 0.212 / 0.260 | 0.003 / 0.005 | 0.249 / 0.830 / 1.721 |
| P3G | strike_flank | 0.003 / 0.058 / 0.294 | 900429/1084410 [0.830, 0.831] | 0.187 / 0.222 | at the local value / 0.017 | 0.307 / 0.922 / 1.854 |
| ParkedGuard | strike_straight | 0.001 / 0.018 / 0.195 | 274179/439626 [0.622, 0.625] | 0.211 / 0.270 | 0.000 / 0.001 | 0.120 / 0.656 / 1.427 |
| ParkedGuard | strike_flank | 0.001 / 0.018 / 0.195 | 592308/822324 [0.719, 0.721] | 0.179 / 0.224 | 0.006 / 0.012 | 0.120 / 0.725 / 2.161 |
| guard_mirror | S20 | 0.003 / 0.058 / 0.294 | 790204/1318542 [0.598, at the local value] | 0.193 / 0.219 | 0.007 / at the local value | 0.491 / 1.698 / 2.603 |
| guard_mirror | P3S | 0.003 / 0.058 / 0.294 | 376796/619788 [0.607, 0.609] | 0.204 / 0.243 | 0.007 / at the local value | 0.256 / 1.098 / 2.404 |
| guard_mirror | ApfStrike | 0.003 / 0.058 / 0.294 | 462740/1043628 [0.442, 0.444] | 0.207 / 0.257 | 0.003 / 0.007 | 0.269 / 0.943 / 1.983 |
| guard_mark_edge | S20 | 0.003 / 0.058 / 0.294 | 999554/1702110 [0.587, 0.588] | 0.179 / 0.213 | 0.005 / 0.007 | 0.365 / 1.573 / 2.163 |
| guard_mark_edge | P3S | 0.003 / 0.058 / 0.294 | 482947/707430 [0.682, 0.684] | at the local value / 0.242 | 0.005 / 0.007 | 0.310 / 1.092 / 2.002 |
| guard_mark_edge | ApfStrike | 0.003 / 0.058 / 0.294 | 438462/1014510 [0.431, 0.433] | 0.213 / 0.257 | 0.001 / 0.002 | 0.269 / 0.940 / 1.957 |

For the 12 core pairs the last column of row 5 is against row 5a; for the 12 scripted-player pairs (our Strike and our Guard blocks) it is against row 4.

Reading (observed in the training simulator): the jitter changes the outcome mainly against S20. Strike reach, row 5a to row 5: G19/S20 740 to 983 of 1,000 (251 games differ), P3G/S20 908 to 924 (56 differ), ParkedGuard/S20 556 to 571 (67 differ). The pairs with P3S and ApfStrike were already at 1,000 of 1,000 and stay there (0 differ). Against row 4, our scripted players differ in a few games to a few hundred (G19/strike_flank 202, guard_mirror/S20 144, ParkedGuard/strike_flank 55); the reach rate of our two scripted Guards against S20 and P3S rises to 1,000 of 1,000. One seed; a 1 mm jitter is the size of the S2b test, a stand-in for the physics drone's own height differences.

## Videos

`runs/nus_port/phase4/row_5a/videos/` (15 files), `row_5/videos/` (27 files) (git-ignored; top-down, one frame per 8 ticks at 15 frames/s; the first Strike win and the first hold among the first 16 games of each pair).

## Limits

- Exploratory drone model; one seed; INFO measurements of frozen partner policies.
- The control row covers the 12 core pairs only (the owner's decision above); the scripted-player pairs are not checked game by game against a control.

## Ledger

Row `T23` (rows 5a and 5).

Watch the clips: [sub-test 5a videos](../docs/media/nus/README.md#test-5a), [Test 5 videos](../docs/media/nus/README.md#test-5).
