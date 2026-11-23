Simulator: training simulator, tier 1 (the hangar game with the Starling layer's commander copy, delay and lag from the fitted, EXPLORATORY drone model; safety filter off, our push-apart kept). Not a flight result.

# 2026-11-18 NUS port, Phase 4 rung 3 (T20): the drone response (INFO)

| Item | Value |
|---|---|
| Purpose | Rows 3a and 3. Row 3a: the rung 3 layer with an identity drone (no commander, delay or lag; it flies the held command exactly): the control that must equal row 2. Row 3: the drone response (commander copy with ramp and leash, delay, lag, `real_exploratory_v0`), filter still off, push kept |
| Plan | `docs/archive/2026-11-18-nus-phase4-transfer-ladder.md` v2 with the owner's answers (action hold moved into rung 2, so there is no row 3h); `gates.toml`: `gates = []` plus the reading rules, written before each run |
| Date, machine | 2026-11-18, home RTX 5090 workstation |
| Code | branch `nus-port-phase2` over `afe6b993`, working copy NOT committed (the lead commits); files in HANDOFF section 0. Rows 1, 2, 3a and 3 ran before the jump-row fix of the partner push (it touches rows 2.1 and 2.2 only); rows 2.1 and 2.2 ran after it. |
| Layer swap | `SvgGame.__init__` builds the fitted Starling layer with the safety filter on and turns the push-apart off; `NusHangarGame` then replaces the private `self._starling` with `NusPushLayer` (filter off) or `NusIdentityLayer` and resets it to the starts. The push moves neither the velocity nor the commander's reference, so the commander pulls a pushed drone back |
| Config and local files | `configs/nus_phase4.toml` (rows, pairs, counts), `configs/nus_hangar_game.toml` (generic game settings), the Starling parameter file `params/real_exploratory_v0.toml` (EXPLORATORY drone model, T5 = FAIL: it answers more slowly than the real drone, so rows 3 to 5 overstate the lag cost), git-ignored `configs/local/nus_rules.toml`, `nus_deploy.toml`, `nus_deploy_ref.toml`, `nus_hangar.toml` (no value is written here). Row 3 sha256 prefixes at run time: deploy_ref `6d71c111959fd9b2`, deploy_w2 `c248c6bef3f6e17b`, game_config `3f771112bd3f0370`, hangar `b7f2870ee17d2d70`, rules `dd22cc28ce2042f3`, settings `0732011ef0733a3f`, starts `40c8cc59297f58d5` |

| Item | Value |
|---|---|
| Machine | home workstation, NVIDIA GeForce RTX 5090; torch 2.7.0+cu128; Python 3.11.18 |
| Games | 1000 per pair, 24 pairs, 6 drones per game, tier: tier 1 |
| Throughput | 280,932 game-steps/s (1,685,592 drone-steps/s), 1000 games x 6 drones, tier 1, NVIDIA GeForce RTX 5090 (a game-step is one simulator tick; the run time is kept in scores.json) |

All three blocks (24 pairs) on each row.

## Checks of this rung

| Check | Result |
|---|---|
| Reading rule 2, row 3a against row 2, game by game (outcome, end step and closest approach) | **0 games differ over all 24 pairs x 1,000 games**: PASS (an identity drone changes nothing) |
| Reading rule 1: ParkedGuard against ApfStrike | held 0.000; no stop |
| Guard 0 drift of the parked Guard (rows 3a, 3) | 0 in every game of every parked pair on both rows: nothing moves it (from rung 4 the filter may) |

## Results

### Row 3a

| Guard | Strike | Strike reach, k/n [95 % interval] | Reach time, median s | Closest approach Guard-Strike 3-D, min / p5 / p50 m | Rule breach | Filter breach | Contact | Start miss | Games whose outcome differs from row 2 |
|---|---|---|---|---|---|---|---|---|---|
| G19 | S20 | 17/1000 [0.011, 0.027] | 17.850 | 1.184 / 1.189 / 1.194 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 984/1000 [0.974, 0.990] | 1000/1000 [0.996, 1.000] | 0 |
| G19 | P3S | 980/1000 [0.969, 0.987] | 21.000 | 1.183 / 1.184 / 1.190 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 963/1000 [0.949, 0.973] | 1000/1000 [0.996, 1.000] | 0 |
| G19 | ApfStrike | 211/1000 [0.187, 0.237] | 3.250 | 1.183 / 1.184 / 1.188 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 985/1000 [0.975, 0.991] | 1000/1000 [0.996, 1.000] | 0 |
| P3G | S20 | 841/1000 [0.817, 0.862] | 21.400 | 1.185 / 1.190 / 1.196 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 983/1000 [0.973, 0.989] | 1000/1000 [0.996, 1.000] | 0 |
| P3G | P3S | 990/1000 [0.982, 0.995] | 14.850 | 1.183 / 1.185 / 1.190 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 976/1000 [0.965, 0.984] | 1000/1000 [0.996, 1.000] | 0 |
| P3G | ApfStrike | 96/1000 [0.079, 0.116] | 3.250 | 1.183 / 1.183 / 1.187 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 995/1000 [0.988, 0.998] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | S20 | 1000/1000 [0.996, 1.000] | 6.700 | 0.985 / 1.107 / 1.183 | 7/1000 [0.003, 0.014] | 1000/1000 [0.996, 1.000] | 936/1000 [0.919, 0.950] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | P3S | 1000/1000 [0.996, 1.000] | 4.450 | 1.010 / 1.183 / 1.183 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 928/1000 [0.910, 0.942] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | ApfStrike | 919/1000 [0.900, 0.934] | 3.250 | 0.963 / 0.990 / 1.183 | 118/1000 [0.099, 0.139] | 1000/1000 [0.996, 1.000] | 944/1000 [0.928, 0.957] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | S20 | 1000/1000 [0.996, 1.000] | 5.000 | at the local value / at the local value / 1.432 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 935/1000 [0.918, 0.949] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | P3S | 991/1000 [0.983, 0.995] | 5.300 | at the local value / at the local value / 1.460 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 935/1000 [0.918, 0.949] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | ApfStrike | 1000/1000 [0.996, 1.000] | at the local value | at the local value / at the local value / 1.240 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 935/1000 [0.918, 0.949] | 1000/1000 [0.996, 1.000] | 0 |
| G19 | strike_straight | 209/1000 [0.185, 0.235] | 3.250 | 1.183 / 1.184 / 1.188 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 984/1000 [0.974, 0.990] | 1000/1000 [0.996, 1.000] | 0 |
| G19 | strike_flank | 40/1000 [0.030, 0.054] | 12.750 | 1.183 / 1.185 / 1.192 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 997/1000 [0.991, 0.999] | 1000/1000 [0.996, 1.000] | 0 |
| P3G | strike_straight | 96/1000 [0.079, 0.116] | 3.250 | 1.183 / 1.183 / 1.187 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 995/1000 [0.988, 0.998] | 1000/1000 [0.996, 1.000] | 0 |
| P3G | strike_flank | 193/1000 [0.170, 0.219] | 14.550 | 1.183 / 1.184 / 1.190 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 993/1000 [0.986, 0.997] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | strike_straight | 1000/1000 [0.996, 1.000] | at the local value | at the local value / at the local value / 1.240 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 935/1000 [0.918, 0.949] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | strike_flank | 879/1000 [0.857, 0.898] | 3.400 | at the local value / at the local value / 1.324 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 974/1000 [0.962, 0.982] | 1000/1000 [0.996, 1.000] | 0 |
| guard_mirror | S20 | 1/1000 [0.000, 0.006] | at the local value | 1.180 / 1.183 / 1.184 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 961/1000 [0.947, 0.971] | 1000/1000 [0.996, 1.000] | 0 |
| guard_mirror | P3S | 25/1000 [0.017, 0.037] | 6.150 | 1.176 / 1.183 / 1.184 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 965/1000 [0.952, 0.975] | 1000/1000 [0.996, 1.000] | 0 |
| guard_mirror | ApfStrike | 48/1000 [0.036, 0.063] | 3.250 | 1.183 / 1.183 / 1.183 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 947/1000 [0.931, 0.959] | 1000/1000 [0.996, 1.000] | 0 |
| guard_mark_edge | S20 | 0/1000 [0.000, at the local value] | n/a | 1.183 / 1.183 / 1.183 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 966/1000 [0.953, 0.976] | 1000/1000 [0.996, 1.000] | 0 |
| guard_mark_edge | P3S | 25/1000 [0.017, 0.037] | 16.800 | 1.183 / 1.183 / 1.183 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 975/1000 [0.963, 0.983] | 1000/1000 [0.996, 1.000] | 0 |
| guard_mark_edge | ApfStrike | 48/1000 [0.036, 0.063] | 3.250 | 1.183 / 1.183 / 1.183 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 952/1000 [0.937, 0.964] | 1000/1000 [0.996, 1.000] | 0 |

| Guard | Strike | Same-team approach 3-D, min / p5 / p50 m | Filter corrections k/n [95 %] | Correction size mean / p95 m/s | Smoothness (change of the command per drone per tick) mean / p95 m/s | Guard 0 drift min / p50 / max m |
|---|---|---|---|---|---|---|
| G19 | S20 | 0.000 / 0.001 / 0.096 | n/a | n/a | 0.007 / 0.009 | 0.419 / 0.910 / 1.431 |
| G19 | P3S | 0.000 / 0.002 / 0.118 | n/a | n/a | 0.005 / 0.007 | 0.422 / 0.947 / 1.965 |
| G19 | ApfStrike | 0.000 / 0.000 / 0.000 | n/a | n/a | 0.003 / 0.005 | 0.206 / 0.890 / 1.216 |
| P3G | S20 | 0.000 / 0.003 / 0.108 | n/a | n/a | 0.005 / 0.008 | 0.214 / 1.111 / 2.011 |
| P3G | P3S | 0.000 / 0.001 / 0.118 | n/a | n/a | 0.007 / 0.011 | at the local value / 0.904 / 1.323 |
| P3G | ApfStrike | 0.000 / 0.000 / 0.000 | n/a | n/a | 0.003 / at the local value | 0.399 / 1.127 / 1.426 |
| ApfGuard | S20 | 0.000 / 0.020 / 0.185 | n/a | n/a | 0.006 / 0.008 | 1.090 / 2.158 / 3.954 |
| ApfGuard | P3S | 0.000 / 0.016 / 0.218 | n/a | n/a | 0.006 / 0.008 | 0.857 / 1.725 / 3.019 |
| ApfGuard | ApfStrike | 0.000 / 0.000 / 0.165 | n/a | n/a | 0.001 / 0.003 | 0.667 / 1.720 / 4.263 |
| ParkedGuard | S20 | 0.000 / 0.011 / 0.169 | n/a | n/a | 0.001 / 0.002 | 0.000 / 0.000 / 0.000 |
| ParkedGuard | P3S | 0.000 / 0.011 / 0.148 | n/a | n/a | 0.003 / at the local value | 0.000 / 0.000 / 0.000 |
| ParkedGuard | ApfStrike | 0.000 / 0.017 / 0.177 | n/a | n/a | 0.000 / 0.000 | 0.000 / 0.000 / 0.000 |
| G19 | strike_straight | 0.000 / 0.000 / 0.000 | n/a | n/a | 0.003 / 0.005 | 0.206 / 0.891 / 1.226 |
| G19 | strike_flank | 0.000 / 0.000 / 0.006 | n/a | n/a | 0.279 / 0.336 | 0.408 / 0.967 / 1.605 |
| P3G | strike_straight | 0.000 / 0.000 / 0.000 | n/a | n/a | 0.003 / 0.009 | 0.399 / 1.126 / 1.400 |
| P3G | strike_flank | 0.000 / 0.000 / 0.003 | n/a | n/a | 0.189 / 0.315 | 0.390 / 1.065 / 1.553 |
| ParkedGuard | strike_straight | 0.000 / 0.017 / 0.177 | n/a | n/a | 0.000 / 0.000 | 0.000 / 0.000 / 0.000 |
| ParkedGuard | strike_flank | 0.000 / 0.000 / 0.103 | n/a | n/a | 0.081 / 0.275 | 0.000 / 0.000 / 0.000 |
| guard_mirror | S20 | 0.000 / 0.002 / 0.109 | n/a | n/a | at the local value / at the local value | 1.456 / 1.940 / 2.051 |
| guard_mirror | P3S | 0.000 / 0.001 / 0.037 | n/a | n/a | at the local value / at the local value | 0.736 / 1.939 / 1.958 |
| guard_mirror | ApfStrike | 0.000 / 0.017 / 0.171 | n/a | n/a | 0.000 / 0.000 | 0.663 / 1.920 / 1.920 |
| guard_mark_edge | S20 | 0.000 / 0.002 / 0.111 | n/a | n/a | 0.003 / 0.003 | 1.591 / 1.596 / at the local value |
| guard_mark_edge | P3S | 0.000 / 0.000 / 0.033 | n/a | n/a | 0.003 / 0.003 | 1.266 / 1.594 / at the local value |
| guard_mark_edge | ApfStrike | 0.002 / 0.018 / 0.168 | n/a | n/a | 0.000 / 0.000 | 0.663 / at the local value / at the local value |


### Row 3

| Guard | Strike | Strike reach, k/n [95 % interval] | Reach time, median s | Closest approach Guard-Strike 3-D, min / p5 / p50 m | Rule breach | Filter breach | Contact | Start miss | Games whose outcome differs from row 3a |
|---|---|---|---|---|---|---|---|---|---|
| G19 | S20 | 43/1000 [0.032, 0.057] | 17.200 | 1.182 / 1.187 / 1.194 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 987/1000 [0.978, 0.992] | 1000/1000 [0.996, 1.000] | 38 |
| G19 | P3S | 1000/1000 [0.996, 1.000] | 13.100 | 1.178 / 1.181 / 1.184 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 955/1000 [0.940, 0.966] | 1000/1000 [0.996, 1.000] | 20 |
| G19 | ApfStrike | 408/1000 [0.378, 0.439] | 3.650 | 1.178 / 1.183 / 1.186 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 984/1000 [0.974, 0.990] | 1000/1000 [0.996, 1.000] | 219 |
| P3G | S20 | 926/1000 [0.908, 0.941] | 20.250 | 1.179 / 1.187 / 1.194 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 983/1000 [0.973, 0.989] | 1000/1000 [0.996, 1.000] | 111 |
| P3G | P3S | 1000/1000 [0.996, 1.000] | 9.650 | 1.177 / 1.180 / 1.185 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 976/1000 [0.965, 0.984] | 1000/1000 [0.996, 1.000] | 10 |
| P3G | ApfStrike | 294/1000 [0.267, 0.323] | 3.650 | 1.177 / 1.181 / 1.185 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 995/1000 [0.988, 0.998] | 1000/1000 [0.996, 1.000] | 208 |
| ApfGuard | S20 | 1000/1000 [0.996, 1.000] | 7.200 | 0.992 / 1.044 / 1.180 | 13/1000 [0.008, 0.022] | 1000/1000 [0.996, 1.000] | 949/1000 [0.934, 0.961] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | P3S | 1000/1000 [0.996, 1.000] | 4.600 | 1.032 / 1.180 / 1.181 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 924/1000 [0.906, 0.939] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | ApfStrike | 894/1000 [0.873, 0.912] | 3.650 | 0.817 / 0.996 / 1.180 | 72/1000 [0.058, 0.090] | 1000/1000 [0.996, 1.000] | 939/1000 [0.922, 0.952] | 1000/1000 [0.996, 1.000] | 97 |
| ParkedGuard | S20 | 1000/1000 [0.996, 1.000] | 5.350 | at the local value / at the local value / 1.432 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 934/1000 [0.917, 0.948] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | P3S | 997/1000 [0.991, 0.999] | 4.450 | at the local value / at the local value / 1.463 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 932/1000 [0.915, 0.946] | 1000/1000 [0.996, 1.000] | 6 |
| ParkedGuard | ApfStrike | 1000/1000 [0.996, 1.000] | 3.650 | at the local value / at the local value / 1.226 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 936/1000 [0.919, 0.950] | 1000/1000 [0.996, 1.000] | 0 |
| G19 | strike_straight | 385/1000 [0.355, 0.416] | 3.650 | 1.181 / 1.183 / 1.186 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 984/1000 [0.974, 0.990] | 1000/1000 [0.996, 1.000] | 190 |
| G19 | strike_flank | 54/1000 [0.042, 0.070] | 4.100 | 1.180 / 1.183 / 1.188 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 984/1000 [0.974, 0.990] | 1000/1000 [0.996, 1.000] | 56 |
| P3G | strike_straight | 287/1000 [0.260, 0.316] | 3.650 | 1.177 / 1.181 / 1.185 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 995/1000 [0.988, 0.998] | 1000/1000 [0.996, 1.000] | 205 |
| P3G | strike_flank | 349/1000 [0.320, 0.379] | 24.100 | 1.177 / 1.181 / 1.186 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 990/1000 [0.982, 0.995] | 1000/1000 [0.996, 1.000] | 320 |
| ParkedGuard | strike_straight | 1000/1000 [0.996, 1.000] | 3.650 | at the local value / at the local value / 1.226 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 936/1000 [0.919, 0.950] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | strike_flank | 876/1000 [0.854, 0.895] | 3.950 | at the local value / at the local value / 1.308 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 974/1000 [0.962, 0.982] | 1000/1000 [0.996, 1.000] | 5 |
| guard_mirror | S20 | 69/1000 [0.055, 0.086] | 16.200 | 1.158 / 1.180 / 1.182 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 965/1000 [0.952, 0.975] | 1000/1000 [0.996, 1.000] | 70 |
| guard_mirror | P3S | 80/1000 [0.065, 0.098] | 9.850 | 1.168 / 1.180 / 1.181 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 972/1000 [0.960, 0.981] | 1000/1000 [0.996, 1.000] | 75 |
| guard_mirror | ApfStrike | 39/1000 [0.029, 0.053] | 3.650 | 1.178 / 1.180 / 1.180 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 951/1000 [0.936, 0.963] | 1000/1000 [0.996, 1.000] | 9 |
| guard_mark_edge | S20 | 1000/1000 [0.996, 1.000] | 19.300 | 1.177 / 1.180 / 1.181 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 969/1000 [0.956, 0.978] | 1000/1000 [0.996, 1.000] | 1000 |
| guard_mark_edge | P3S | 999/1000 [0.994, 1.000] | 10.000 | 1.177 / 1.180 / 1.181 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 969/1000 [0.956, 0.978] | 1000/1000 [0.996, 1.000] | 974 |
| guard_mark_edge | ApfStrike | 38/1000 [0.028, 0.052] | 3.650 | 1.180 / 1.180 / 1.180 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 955/1000 [0.940, 0.966] | 1000/1000 [0.996, 1.000] | 10 |

| Guard | Strike | Same-team approach 3-D, min / p5 / p50 m | Filter corrections k/n [95 %] | Correction size mean / p95 m/s | Smoothness (change of the command per drone per tick) mean / p95 m/s | Guard 0 drift min / p50 / max m |
|---|---|---|---|---|---|---|
| G19 | S20 | 0.000 / 0.001 / 0.083 | n/a | n/a | at the local value / at the local value | 0.434 / 0.912 / 1.454 |
| G19 | P3S | 0.000 / 0.002 / 0.151 | n/a | n/a | 0.007 / 0.008 | 0.155 / 0.970 / 3.871 |
| G19 | ApfStrike | 0.000 / 0.000 / 0.000 | n/a | n/a | 0.002 / at the local value | 0.191 / 0.898 / 2.019 |
| P3G | S20 | 0.000 / at the local value / 0.104 | n/a | n/a | at the local value / 0.006 | 0.275 / 1.119 / 2.010 |
| P3G | P3S | 0.000 / 0.002 / 0.124 | n/a | n/a | 0.009 / 0.011 | 0.265 / 0.946 / 1.366 |
| P3G | ApfStrike | 0.000 / 0.000 / 0.000 | n/a | n/a | 0.002 / 0.006 | 0.278 / 1.104 / 1.477 |
| ApfGuard | S20 | 0.000 / 0.020 / 0.179 | n/a | n/a | 0.006 / 0.008 | 1.017 / 2.271 / 3.524 |
| ApfGuard | P3S | 0.000 / 0.019 / 0.225 | n/a | n/a | 0.006 / 0.008 | 0.811 / 1.739 / 2.670 |
| ApfGuard | ApfStrike | 0.000 / 0.000 / 0.183 | n/a | n/a | 0.001 / 0.003 | 0.783 / 1.663 / 4.729 |
| ParkedGuard | S20 | 0.000 / at the local value / 0.169 | n/a | n/a | 0.001 / 0.002 | 0.000 / 0.000 / 0.000 |
| ParkedGuard | P3S | 0.001 / 0.012 / 0.164 | n/a | n/a | 0.002 / at the local value | 0.000 / 0.000 / 0.000 |
| ParkedGuard | ApfStrike | 0.001 / 0.017 / 0.176 | n/a | n/a | 0.000 / 0.000 | 0.000 / 0.000 / 0.000 |
| G19 | strike_straight | 0.000 / 0.000 / 0.000 | n/a | n/a | 0.002 / at the local value | 0.191 / 0.895 / 1.465 |
| G19 | strike_flank | 0.000 / 0.000 / 0.000 | n/a | n/a | 0.027 / 0.030 | 0.276 / 0.983 / 1.646 |
| P3G | strike_straight | 0.000 / 0.000 / 0.000 | n/a | n/a | 0.003 / 0.006 | 0.278 / 1.085 / 1.474 |
| P3G | strike_flank | 0.000 / 0.000 / 0.000 | n/a | n/a | 0.018 / 0.025 | 0.292 / 1.096 / 1.610 |
| ParkedGuard | strike_straight | 0.001 / 0.017 / 0.176 | n/a | n/a | 0.000 / 0.000 | 0.000 / 0.000 / 0.000 |
| ParkedGuard | strike_flank | 0.000 / 0.000 / at the local value | n/a | n/a | 0.020 / 0.045 | 0.000 / 0.000 / 0.000 |
| guard_mirror | S20 | 0.000 / 0.002 / 0.101 | n/a | n/a | at the local value / 0.006 | 1.248 / 1.953 / 1.999 |
| guard_mirror | P3S | 0.000 / 0.001 / 0.047 | n/a | n/a | at the local value / 0.006 | 0.712 / 1.952 / 1.967 |
| guard_mirror | ApfStrike | 0.000 / 0.017 / 0.168 | n/a | n/a | 0.000 / 0.000 | 0.687 / 1.923 / 1.944 |
| guard_mark_edge | S20 | 0.000 / 0.003 / 0.133 | n/a | n/a | 0.005 / 0.006 | 1.263 / 1.598 / 1.631 |
| guard_mark_edge | P3S | 0.000 / 0.000 / 0.087 | n/a | n/a | 0.007 / 0.008 | 1.080 / 1.578 / 1.629 |
| guard_mark_edge | ApfStrike | 0.002 / 0.017 / 0.166 | n/a | n/a | 0.000 / 0.000 | 0.687 / 1.603 / 1.634 |



Reading: the drone response raises the Strike reach rate almost everywhere against the policy Guards: G19/S20 17 to 43, G19/ApfStrike 211 to 408, P3G/ApfStrike 96 to 294, P3G/S20 841 to 926 (P3S now reaches in 1000 of 1000 games against both trained Guards). Our scripted Guard `guard_mark_edge` goes from holding S20 (0 of 1,000 reach) to losing to it (1000 of 1000), and `guard_mirror` from 1 to 69: the Strike reach rate rises for both of our scripted Guards. The exploratory drone model answers more slowly than the real drone (T5 = FAIL), so this overstates the lag cost.

## Videos

`runs/nus_port/phase4/row_3a/videos/`, `row_3/videos/` (git-ignored; partner geometry; top-down, one frame per 8 ticks at 15 frames/s; the first Strike win and the first hold among the first 16 games of each pair.).

## Limits

- Safety filter off (STANDARDS section 6.2 exception, Phase 4 ladder): INFO measurements of frozen partner policies; nothing is trained, gated or exported from them.
- Exploratory drone model; one seed.

## Ledger

Row `T20`.

Watch the clips: [sub-test 3a videos](../docs/media/nus/README.md#test-3a), [Test 3 videos](../docs/media/nus/README.md#test-3).
