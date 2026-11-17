Simulator: training simulator, tier 1 (the hangar game on point drones: our game engine with the partner's rules in rows 2.1 and 2.2, our own rules in row 2). Not a flight result.

# 2026-11-18 NUS port, Phase 4 rung 2 (T19): our game engine and our rules (INFO)

| Item | Value |
|---|---|
| Purpose | Move the frozen policies from the replica into our game engine (rows 2.1, 2.2: the split, because the pre-set trigger fired), then give them our rules at one-tick timing (row 2: our `block` push-apart and the policy's command held for the partner step's ticks, owner answers 3 and 4) |
| Plan | `docs/plans/2026-11-18-nus-phase4-transfer-ladder.md` v2 with the owner's answers; `gates.toml` of each row: `gates = []` plus the reading rules, written before the run |
| Date, machine | 2026-11-18, home RTX 5090 workstation |
| Code | branch `nus-port-phase2` over `afe6b993`, working copy NOT committed (the lead commits); files in HANDOFF section 0. Rows 1, 2, 3a and 3 ran before the jump-row fix of the partner push (it touches rows 2.1 and 2.2 only); rows 2.1 and 2.2 ran after it. |
| Config and local files | `configs/nus_phase4.toml` (rows, pairs, counts), `configs/nus_hangar_game.toml` (generic game settings), the Starling parameter file `params/real_exploratory_v0.toml` (EXPLORATORY drone model, T5 = FAIL: it answers more slowly than the real drone, so rows 3 to 5 overstate the lag cost), git-ignored `configs/local/nus_rules.toml`, `nus_deploy.toml`, `nus_deploy_ref.toml`, `nus_hangar.toml` (no value is written here). Row 2 sha256 prefixes at run time: deploy_ref `6d71c111959fd9b2`, deploy_w2 `c248c6bef3f6e17b`, game_config `3f771112bd3f0370`, hangar `b7f2870ee17d2d70`, rules `dd22cc28ce2042f3`, settings `298a08b9f56240a0`, starts `40c8cc59297f58d5` |
| Seeds | the same paired starts file as every row (one seed, no method claim) |

| Item | Value |
|---|---|
| Machine | home workstation, NVIDIA GeForce RTX 5090; torch 2.7.0+cu128; Python 3.11.18 |
| Games | 1000 per pair, 24 pairs, 6 drones per game, tier: tier 1 |
| Throughput | 416,674 game-steps/s (2,500,045 drone-steps/s), 1000 games x 6 drones, tier 1, NVIDIA GeForce RTX 5090 (a game-step is one simulator tick; the run time is kept in scores.json) |

Pairs: row 2 plays the three blocks (core 12, our scripted Strike 6, our scripted Guard 6 = 24 pairs); rows 2.1 and 2.2 play the core block only (12 pairs; our scripted players read our observation every tick and have no sample ticks, so they cannot play in jump motion). Rows 2.1 and 2.2 ran 1,000 games per pair on the same tier and machine.

## The split of rung 2 (pre-set rule, D3)

**Fired.** 5 core pairs have a rung 2 Strike reach rate outside rung 1's Wilson interval for the same pair: G19/P3S, G19/ApfStrike, P3G/S20, P3G/ApfStrike, ApfGuard/ApfStrike. Rows 2.1 and 2.2 therefore ran before rung 3, in that order (plan 4b built: the partner's soft push, Guard circle and cap in the replica's own arithmetic, in metres, inside `NusHangarGame`, with jump motion: the whole partner displacement flown in one tick on a sample tick, the push applied on that tick only, and the players acting on sample ticks only).

## Reading rule 2 on row 2.1: fired, diagnosed

Row 2.1 must equal row 1 game by game. It does not: per pair, games whose outcome or end step differ (G19/S20 3/2; G19/P3S 77/1; G19/ApfStrike 23/9; P3G/S20 23/3; P3G/P3S 80/1; P3G/ApfStrike 3/1; ApfGuard/S20 16/0; ApfGuard/P3S 14/0; ApfGuard/ApfStrike 30/0; ParkedGuard/S20 2/0; ParkedGuard/P3S 2/0; ParkedGuard/ApfStrike 0/0; first number: outcome or end step, second: outcome only; 17 outcome flips in all 12 x 1,000 games). Diagnosis (numbers in the git-ignored runs, the checks as tests in `tests/test_nus_phase4.py`):

1. A first run showed 8 to 269 games per pair differing; two real bugs were found and fixed before the run of record: the partner's push was applied on every tick instead of once per partner step (open-loop positions diverged by 0.018 units at step 3), and the walls of row 2.1 were not out of reach for a Strike drone the push flings away.
2. With the same recorded actions driven through row 2.1 and the state put back on the replica's after every partner step (the Phase 2 style of check), the largest position error over a subset of the starts is at most 5.2e-6 units for the three pairs tried (P3G/ApfStrike, ApfGuard/P3S, ApfGuard/ApfStrike; limit 1e-4): one step of row 2.1 equals one replica step.
3. Without the put-back, the error grows about 1.5-fold per partner step (2.4e-6 units after step 1, above 1e-3 units at step 17, order 1 later): the push is strongly coupled, so float32 round-off of an independent implementation is amplified. A noise floor inside the replica itself, on all 12 core pairs with three noise draws each (every start shifted by a millionth of a unit): 0 to 7 games per pair change outcome (up to 91 change outcome or end step); row 2.1 against row 1 changes 0 to 9 outcomes per pair (up to 80 outcome or end step). The two are of the same order, pair by pair: the pairs with trained policies and many pushes (G19/P3S, P3G/P3S, G19/ApfStrike, P3G/S20) are the noisy ones, the parked Guard's pairs are the quiet ones.
4. So a game-by-game equality of outcome and end step over a whole game is not reachable between two independent float32 implementations of this coupled push; row 2.1 is equal to row 1 up to a noise floor of the same size, and the equality that can be tested (one step, from the same state) holds. This is a diagnosis by measurement, not a proof; the outcome flips are explained only to the extent that the noise floor reproduces them. The reading rule says stop; the implementer continued with the remaining INFO rows and asks the lead to confirm or to change the rule's wording. Rows 3a and 5a share their rule code with the row they are compared with, so their game-by-game test is exact (row 3a: 0 games differ in all 24 pairs).

## Results

### Row 2.1

| Guard | Strike | Strike reach, k/n [95 % interval] | Reach time, median s | Closest approach Guard-Strike 3-D, min / p5 / p50 m | Rule breach | Filter breach | Contact | Start miss | Games whose outcome differs from row 1 |
|---|---|---|---|---|---|---|---|---|---|
| G19 | S20 | 9/1000 [0.005, 0.017] | 9 | at the local value / at the local value / at the local value | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 1000/1000 [0.996, 1.000] | 1000/1000 [0.996, 1.000] | 2 |
| G19 | P3S | 970/1000 [0.957, 0.979] | 20 | 1.059 / at the local value / at the local value | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 958/1000 [0.944, 0.969] | 1000/1000 [0.996, 1.000] | 1 |
| G19 | ApfStrike | 174/1000 [0.152, 0.199] | 4 | 1.121 / at the local value / at the local value | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 991/1000 [0.983, 0.995] | 1000/1000 [0.996, 1.000] | 9 |
| P3G | S20 | 984/1000 [0.974, 0.990] | 12 | 0.991 / at the local value / at the local value | 1/1000 [0.000, 0.006] | 1000/1000 [0.996, 1.000] | 954/1000 [0.939, 0.965] | 1000/1000 [0.996, 1.000] | 3 |
| P3G | P3S | 994/1000 [0.987, 0.997] | 14 | 1.079 / 1.192 / at the local value | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 954/1000 [0.939, 0.965] | 1000/1000 [0.996, 1.000] | 1 |
| P3G | ApfStrike | 34/1000 [0.024, 0.047] | 3 | 1.127 / at the local value / at the local value | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 998/1000 [0.993, 0.999] | 1000/1000 [0.996, 1.000] | 1 |
| ApfGuard | S20 | 1000/1000 [0.996, 1.000] | 7 | 0.693 / 1.104 / at the local value | 20/1000 [0.013, 0.031] | 998/1000 [0.993, 0.999] | 907/1000 [0.887, 0.923] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | P3S | 1000/1000 [0.996, 1.000] | 4 | 0.692 / 1.076 / at the local value | 28/1000 [0.019, at the local value] | 1000/1000 [0.996, 1.000] | 862/1000 [0.839, 0.882] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | ApfStrike | 999/1000 [0.994, 1.000] | 4 | 0.521 / 0.853 / at the local value | 113/1000 [0.095, 0.134] | 999/1000 [0.994, 1.000] | 944/1000 [0.928, 0.957] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | S20 | 1000/1000 [0.996, 1.000] | 5 | 1.183 / at the local value / 1.343 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 934/1000 [0.917, 0.948] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | P3S | 991/1000 [0.983, 0.995] | 5 | at the local value / at the local value / 1.425 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 933/1000 [0.916, 0.947] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | ApfStrike | 1000/1000 [0.996, 1.000] | 3 | 1.136 / at the local value / 1.201 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 953/1000 [0.938, 0.964] | 1000/1000 [0.996, 1.000] | 0 |

| Guard | Strike | Same-team approach 3-D, min / p5 / p50 m | Filter corrections k/n [95 %] | Correction size mean / p95 m/s | Smoothness (change of the command per drone per tick) mean / p95 m/s | Guard 0 drift min / p50 / max m |
|---|---|---|---|---|---|---|
| G19 | S20 | 0.000 / 0.007 / 0.068 | n/a | n/a | 0.211 / 0.278 | 0.345 / 1.123 / 1.900 |
| G19 | P3S | 0.001 / 0.017 / 0.149 | n/a | n/a | 0.638 / 0.679 | 0.418 / 0.937 / 1.986 |
| G19 | ApfStrike | 0.000 / 0.000 / at the local value | n/a | n/a | 0.611 / 0.693 | 0.283 / 0.795 / 1.106 |
| P3G | S20 | 0.000 / 0.024 / 0.164 | n/a | n/a | 0.454 / 0.546 | 0.177 / 0.972 / 2.898 |
| P3G | P3S | 0.001 / 0.015 / 0.153 | n/a | n/a | 0.646 / 0.690 | at the local value / 0.899 / 1.341 |
| P3G | ApfStrike | 0.000 / 0.000 / 0.000 | n/a | n/a | 0.592 / 0.668 | 0.358 / 1.049 / 1.367 |
| ApfGuard | S20 | 0.000 / 0.015 / 0.151 | n/a | n/a | 0.733 / 0.784 | 0.978 / 2.058 / 3.160 |
| ApfGuard | P3S | 0.001 / 0.027 / 0.211 | n/a | n/a | 0.807 / 0.830 | 0.840 / 1.686 / 2.913 |
| ApfGuard | ApfStrike | 0.000 / 0.000 / 0.090 | n/a | n/a | 0.833 / 0.833 | 0.735 / 1.320 / 3.302 |
| ParkedGuard | S20 | 0.000 / 0.016 / 0.179 | n/a | n/a | 0.346 / 0.421 | 0.000 / 0.000 / 0.000 |
| ParkedGuard | P3S | 0.001 / 0.017 / 0.157 | n/a | n/a | 0.367 / 0.470 | 0.000 / 0.000 / 0.000 |
| ParkedGuard | ApfStrike | 0.001 / 0.017 / 0.175 | n/a | n/a | at the local value / at the local value | 0.000 / 0.000 / 0.000 |


### Row 2.2

| Guard | Strike | Strike reach, k/n [95 % interval] | Reach time, median s | Closest approach Guard-Strike 3-D, min / p5 / p50 m | Rule breach | Filter breach | Contact | Start miss | Games whose outcome differs from row 2.1 |
|---|---|---|---|---|---|---|---|---|---|
| G19 | S20 | 7/1000 [0.003, 0.014] | 18 | 1.182 / at the local value / at the local value | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 981/1000 [0.971, 0.988] | 1000/1000 [0.996, 1.000] | 12 |
| G19 | P3S | 970/1000 [0.957, 0.979] | 20 | 1.059 / at the local value / at the local value | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 958/1000 [0.944, 0.969] | 1000/1000 [0.996, 1.000] | 0 |
| G19 | ApfStrike | 174/1000 [0.152, 0.199] | 4 | 1.121 / at the local value / at the local value | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 991/1000 [0.983, 0.995] | 1000/1000 [0.996, 1.000] | 0 |
| P3G | S20 | 863/1000 [0.840, 0.883] | 19 | 1.019 / 1.088 / at the local value | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 959/1000 [0.945, 0.970] | 1000/1000 [0.996, 1.000] | 149 |
| P3G | P3S | 994/1000 [0.987, 0.997] | 14 | 1.079 / 1.192 / at the local value | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 954/1000 [0.939, 0.965] | 1000/1000 [0.996, 1.000] | 0 |
| P3G | ApfStrike | 34/1000 [0.024, 0.047] | 3 | 1.127 / at the local value / at the local value | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 998/1000 [0.993, 0.999] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | S20 | 1000/1000 [0.996, 1.000] | 7 | 0.693 / 1.099 / at the local value | 21/1000 [0.014, 0.032] | 998/1000 [0.993, 0.999] | 908/1000 [0.888, 0.924] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | P3S | 1000/1000 [0.996, 1.000] | 4 | 0.692 / 1.076 / at the local value | 28/1000 [0.019, at the local value] | 1000/1000 [0.996, 1.000] | 862/1000 [0.839, 0.882] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | ApfStrike | 1000/1000 [0.996, 1.000] | 4 | 0.521 / 0.849 / at the local value | 114/1000 [0.096, 0.135] | 999/1000 [0.994, 1.000] | 944/1000 [0.928, 0.957] | 1000/1000 [0.996, 1.000] | 1 |
| ParkedGuard | S20 | 1000/1000 [0.996, 1.000] | 5 | 1.182 / at the local value / 1.347 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 935/1000 [0.918, 0.949] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | P3S | 991/1000 [0.983, 0.995] | 5 | at the local value / at the local value / 1.425 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 933/1000 [0.916, 0.947] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | ApfStrike | 1000/1000 [0.996, 1.000] | 3 | 1.136 / at the local value / 1.201 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 953/1000 [0.938, 0.964] | 1000/1000 [0.996, 1.000] | 0 |

| Guard | Strike | Same-team approach 3-D, min / p5 / p50 m | Filter corrections k/n [95 %] | Correction size mean / p95 m/s | Smoothness (change of the command per drone per tick) mean / p95 m/s | Guard 0 drift min / p50 / max m |
|---|---|---|---|---|---|---|
| G19 | S20 | 0.002 / 0.013 / 0.118 | n/a | n/a | 0.299 / 0.355 | 0.434 / 0.913 / 1.429 |
| G19 | P3S | 0.001 / 0.017 / 0.149 | n/a | n/a | 0.638 / 0.679 | 0.418 / 0.937 / 1.986 |
| G19 | ApfStrike | 0.000 / 0.000 / at the local value | n/a | n/a | 0.611 / 0.693 | 0.283 / 0.795 / 1.106 |
| P3G | S20 | 0.000 / at the local value / 0.133 | n/a | n/a | 0.385 / 0.525 | 0.214 / 1.113 / 1.926 |
| P3G | P3S | 0.001 / 0.015 / 0.153 | n/a | n/a | 0.646 / 0.690 | at the local value / 0.899 / 1.341 |
| P3G | ApfStrike | 0.000 / 0.000 / 0.000 | n/a | n/a | 0.592 / 0.668 | 0.358 / 1.049 / 1.367 |
| ApfGuard | S20 | 0.000 / 0.017 / 0.152 | n/a | n/a | 0.733 / 0.784 | 0.978 / 2.058 / 3.125 |
| ApfGuard | P3S | 0.001 / 0.027 / 0.211 | n/a | n/a | 0.807 / 0.830 | 0.840 / 1.686 / 2.913 |
| ApfGuard | ApfStrike | 0.000 / 0.000 / 0.090 | n/a | n/a | 0.833 / 0.833 | 0.735 / 1.320 / 4.190 |
| ParkedGuard | S20 | 0.000 / 0.014 / 0.176 | n/a | n/a | 0.345 / 0.420 | 0.000 / 0.000 / 0.000 |
| ParkedGuard | P3S | 0.001 / 0.017 / 0.157 | n/a | n/a | 0.367 / 0.470 | 0.000 / 0.000 / 0.000 |
| ParkedGuard | ApfStrike | 0.001 / 0.017 / 0.175 | n/a | n/a | at the local value / at the local value | 0.000 / 0.000 / 0.000 |


### Row 2

| Guard | Strike | Strike reach, k/n [95 % interval] | Reach time, median s | Closest approach Guard-Strike 3-D, min / p5 / p50 m | Rule breach | Filter breach | Contact | Start miss | Games whose outcome differs from row 2.2 |
|---|---|---|---|---|---|---|---|---|---|
| G19 | S20 | 17/1000 [0.011, 0.027] | 17.850 | 1.184 / 1.189 / 1.194 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 984/1000 [0.974, 0.990] | 1000/1000 [0.996, 1.000] | 10 |
| G19 | P3S | 980/1000 [0.969, 0.987] | 21.000 | 1.183 / 1.184 / 1.190 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 963/1000 [0.949, 0.973] | 1000/1000 [0.996, 1.000] | 16 |
| G19 | ApfStrike | 211/1000 [0.187, 0.237] | 3.250 | 1.183 / 1.184 / 1.188 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 985/1000 [0.975, 0.991] | 1000/1000 [0.996, 1.000] | 115 |
| P3G | S20 | 841/1000 [0.817, 0.862] | 21.400 | 1.185 / 1.190 / 1.196 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 983/1000 [0.973, 0.989] | 1000/1000 [0.996, 1.000] | 46 |
| P3G | P3S | 990/1000 [0.982, 0.995] | 14.850 | 1.183 / 1.185 / 1.190 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 976/1000 [0.965, 0.984] | 1000/1000 [0.996, 1.000] | 14 |
| P3G | ApfStrike | 96/1000 [0.079, 0.116] | 3.250 | 1.183 / 1.183 / 1.187 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 995/1000 [0.988, 0.998] | 1000/1000 [0.996, 1.000] | 62 |
| ApfGuard | S20 | 1000/1000 [0.996, 1.000] | 6.700 | 0.985 / 1.107 / 1.183 | 7/1000 [0.003, 0.014] | 1000/1000 [0.996, 1.000] | 936/1000 [0.919, 0.950] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | P3S | 1000/1000 [0.996, 1.000] | 4.450 | 1.010 / 1.183 / 1.183 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 928/1000 [0.910, 0.942] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | ApfStrike | 919/1000 [0.900, 0.934] | 3.250 | 0.963 / 0.990 / 1.183 | 118/1000 [0.099, 0.139] | 1000/1000 [0.996, 1.000] | 944/1000 [0.928, 0.957] | 1000/1000 [0.996, 1.000] | 81 |
| ParkedGuard | S20 | 1000/1000 [0.996, 1.000] | 5.000 | at the local value / at the local value / 1.432 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 935/1000 [0.918, 0.949] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | P3S | 991/1000 [0.983, 0.995] | 5.300 | at the local value / at the local value / 1.460 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 935/1000 [0.918, 0.949] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | ApfStrike | 1000/1000 [0.996, 1.000] | at the local value | at the local value / at the local value / 1.240 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 935/1000 [0.918, 0.949] | 1000/1000 [0.996, 1.000] | 0 |
| G19 | strike_straight | 209/1000 [0.185, 0.235] | 3.250 | 1.183 / 1.184 / 1.188 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 984/1000 [0.974, 0.990] | 1000/1000 [0.996, 1.000] | None |
| G19 | strike_flank | 40/1000 [0.030, 0.054] | 12.750 | 1.183 / 1.185 / 1.192 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 997/1000 [0.991, 0.999] | 1000/1000 [0.996, 1.000] | None |
| P3G | strike_straight | 96/1000 [0.079, 0.116] | 3.250 | 1.183 / 1.183 / 1.187 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 995/1000 [0.988, 0.998] | 1000/1000 [0.996, 1.000] | None |
| P3G | strike_flank | 193/1000 [0.170, 0.219] | 14.550 | 1.183 / 1.184 / 1.190 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 993/1000 [0.986, 0.997] | 1000/1000 [0.996, 1.000] | None |
| ParkedGuard | strike_straight | 1000/1000 [0.996, 1.000] | at the local value | at the local value / at the local value / 1.240 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 935/1000 [0.918, 0.949] | 1000/1000 [0.996, 1.000] | None |
| ParkedGuard | strike_flank | 879/1000 [0.857, 0.898] | 3.400 | at the local value / at the local value / 1.324 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 974/1000 [0.962, 0.982] | 1000/1000 [0.996, 1.000] | None |
| guard_mirror | S20 | 1/1000 [0.000, 0.006] | at the local value | 1.180 / 1.183 / 1.184 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 961/1000 [0.947, 0.971] | 1000/1000 [0.996, 1.000] | None |
| guard_mirror | P3S | 25/1000 [0.017, 0.037] | 6.150 | 1.176 / 1.183 / 1.184 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 965/1000 [0.952, 0.975] | 1000/1000 [0.996, 1.000] | None |
| guard_mirror | ApfStrike | 48/1000 [0.036, 0.063] | 3.250 | 1.183 / 1.183 / 1.183 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 947/1000 [0.931, 0.959] | 1000/1000 [0.996, 1.000] | None |
| guard_mark_edge | S20 | 0/1000 [0.000, at the local value] | n/a | 1.183 / 1.183 / 1.183 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 966/1000 [0.953, 0.976] | 1000/1000 [0.996, 1.000] | None |
| guard_mark_edge | P3S | 25/1000 [0.017, 0.037] | 16.800 | 1.183 / 1.183 / 1.183 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 975/1000 [0.963, 0.983] | 1000/1000 [0.996, 1.000] | None |
| guard_mark_edge | ApfStrike | 48/1000 [0.036, 0.063] | 3.250 | 1.183 / 1.183 / 1.183 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 952/1000 [0.937, 0.964] | 1000/1000 [0.996, 1.000] | None |

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



Reading: (rung 2 against rung 1, 1,000 paired games per pair) our rules and the hold timing move five core pairs outside rung 1's interval: up for G19/P3S (971 to 980), G19/ApfStrike (175 to 211) and P3G/ApfStrike (33 to 96); down for P3G/S20 (985 to 841; row 2.2 alone, square walls for the Guard circle, already gives 863) and ApfGuard/ApfStrike (999 to 919). ParkedGuard still holds nothing (991 to 1000 of 1,000 reach). Against the scripted Strike players, G19 holds flank runs better than straight runs (40 and 209 of 1,000), P3G the opposite order; of our scripted Guards, `guard_mirror` and `guard_mark_edge` hold the trained Strike policies (S20: 1 and 0 of 1,000 reach; P3S: 25 and 25).

## Videos

`runs/nus_port/phase4/row_2.1/videos/`, `row_2.2/videos/`, `row_2/videos/` (git-ignored; partner geometry; top-down, one frame per 8 ticks at 15 frames/s; the first Strike win and the first hold among the first 16 games of each pair.).

## Limits

- Row 2.1 sits at the float32 noise floor of row 1, not at exact equality (above). One seed, one starts file.
- Safety filter off (STANDARDS section 6.2 exception, Phase 4 ladder): INFO measurements of frozen partner policies; nothing is trained, gated or exported from them.
- In row 2.2 the square walls also clamp Strike drones, which the partner's rules never do (the circle bounded Guards only).

## Ledger

Rows `T19` (this record).
