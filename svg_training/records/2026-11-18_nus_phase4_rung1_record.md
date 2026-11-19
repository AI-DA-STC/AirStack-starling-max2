Simulator: training simulator, tier 1 (the batched replica of the partner's 2-D game, units converted to metres at the owner's scale; games on GPU tensors). Not a flight result.

# 2026-11-18 NUS port, Phase 4 rung 1 (T18): the baseline, our replica of the partner's game (INFO)

| Item | Value |
|---|---|
| Purpose | Row 1 of the transfer ladder: every frozen policy and controller scored on the decided hangar geometry in the replica, 1,000 games per pair, from the one paired starts file. Row 1 is the baseline of every later row; its parked-Guard rows are the geometry check (reading rule 1) |
| Plan | `docs/plans/2026-11-18-nus-phase4-transfer-ladder.md` v2 with the owner's answers (INFO run: `gates.toml` has `gates = []` and the reading rules as text, written before the run) |
| Date, machine | 2026-11-18, home RTX 5090 workstation |
| Code | branch `nus-port-phase2` over `afe6b993`, working copy NOT committed (the lead commits); files in HANDOFF section 0. Rows 1, 2, 3a and 3 ran before the jump-row fix of the partner push (it touches rows 2.1 and 2.2 only); rows 2.1 and 2.2 ran after it. |
| Config and local files | `configs/nus_phase4.toml` (rows, pairs, counts), `configs/nus_hangar_game.toml` (generic game settings), the Starling parameter file `params/real_exploratory_v0.toml` (EXPLORATORY drone model, T5 = FAIL: it answers more slowly than the real drone, so rows 3 to 5 overstate the lag cost), git-ignored `configs/local/nus_rules.toml`, `nus_deploy.toml`, `nus_deploy_ref.toml`, `nus_hangar.toml` (no value is written here). sha256 prefixes at run time: deploy_ref `6d71c111959fd9b2`, deploy_w2 `c248c6bef3f6e17b`, game_config `3f771112bd3f0370`, hangar `b7f2870ee17d2d70`, rules `dd22cc28ce2042f3`, settings `298a08b9f56240a0`, starts `40c8cc59297f58d5` |
| Seeds | one seed for the paired starts file (`[ladder] seed`, PROPOSED): one seed, so no method claim (STANDARDS section 6.5) |

| Item | Value |
|---|---|
| Machine | home workstation, NVIDIA GeForce RTX 5090; torch 2.7.0+cu128; Python 3.11.18 |
| Games | 1000 per pair, 12 pairs, 6 drones per game, tier: replica (CPU/GPU tensors) |
| Throughput | 9,450,674 game-steps/s (56,704,044 drone-steps/s), 1000 games x 6 drones, replica (CPU/GPU tensors), NVIDIA GeForce RTX 5090 (a game-step is one replica step counted in ticks; the run time is kept in scores.json) |

Pairs: Guard {G19, P3G, ApfGuard, ParkedGuard} x Strike {S20, P3S, ApfStrike} (12 pairs; our scripted players read our observation, which the replica lacks, so they are not on this row). G19 and S20: the archive pair of T17; P3G and P3S: the Phase 3 pair (T16). ParkedGuard: Run 0's parked Guard (Guard 0 starts at the zone centre, every Guard commands zero).

## Checks of this rung

| Check | Result |
|---|---|
| Exact check against T16 (reading rule 3): on T16's 1,000 shared starts, `P3G` against `ApfStrike` and `ApfGuard` against `P3S` through the new replica path equal a fresh `play_arm` game by game, and equal T16's converted-arm counts | 0 games differ (Guard arm, 46/1000 reached, T16 46/1000); 0 differ (Strike arm, 1000/1000, T16 1000/1000). `phase3_outcome_parity.json` holds counts only, so "game by game" is against a fresh `play_arm` on the same starts; PASS |
| Reading rule 1: ParkedGuard holds at least the set limit against ApfStrike | held 0.000 of games: the geometry does not close the zone on its own; no stop |
| Cuda actor parity (INFO, plan D7): gate (a)'s error with the actors on cuda, all 24,000 observation rows per team, limit 0.02 units | Phase 3 pair 0.00744 (Guard) and 0.01045 (Strike); archive pair 0.00792 and 0.00946: all within the limit, equal to the CPU values; the policy can run on cuda inside the step |

## Results

Strike reach rate = 1 - hold rate, as k/n with the Wilson 95 % interval; lengths in metres, times in seconds; "at the local value" marks a value equal to a local (partner or owner) value (it stays in the git-ignored `scores.json`); the closest approaches of Guard and Strike that stay at a push radius are pinned by construction. "Start miss" counts a game with any pair inside the safety filter's keep-out at the start (reported, never repaired): partner starts put drones of one team close together in every game. "Contact" counts any pair (also team-mates, which pass through each other in the partner's rules) closer than the tier 1 contact distance. Rows 1 and 2.1 have no safety filter; the filter columns on them mean "inside the filter's keep-out", not a correction.

### Row 1

| Guard | Strike | Strike reach, k/n [95 % interval] | Reach time, median s | Closest approach Guard-Strike 3-D, min / p5 / p50 m | Rule breach | Filter breach | Contact | Start miss | Games whose outcome differs from the row before |
|---|---|---|---|---|---|---|---|---|---|
| G19 | S20 | 9/1000 [0.005, 0.017] | 10 | at the local value / at the local value / at the local value | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 1000/1000 [0.996, 1.000] | 1000/1000 [0.996, 1.000] | n/a |
| G19 | P3S | 971/1000 [0.959, 0.980] | 21 | 1.059 / at the local value / at the local value | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 954/1000 [0.939, 0.965] | 1000/1000 [0.996, 1.000] | n/a |
| G19 | ApfStrike | 175/1000 [0.153, at the local value] | 4 | 1.121 / at the local value / at the local value | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 991/1000 [0.983, 0.995] | 1000/1000 [0.996, 1.000] | n/a |
| P3G | S20 | 985/1000 [0.975, 0.991] | 13 | 0.986 / at the local value / at the local value | 1/1000 [0.000, 0.006] | 1000/1000 [0.996, 1.000] | 954/1000 [0.939, 0.965] | 1000/1000 [0.996, 1.000] | n/a |
| P3G | P3S | 993/1000 [0.986, 0.997] | 15 | 1.079 / 1.192 / at the local value | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 954/1000 [0.939, 0.965] | 1000/1000 [0.996, 1.000] | n/a |
| P3G | ApfStrike | 33/1000 [0.024, 0.046] | 4 | 1.127 / at the local value / at the local value | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 998/1000 [0.993, 0.999] | 1000/1000 [0.996, 1.000] | n/a |
| ApfGuard | S20 | 1000/1000 [0.996, 1.000] | 7 | 0.693 / 1.104 / at the local value | 20/1000 [0.013, 0.031] | 998/1000 [0.993, 0.999] | 907/1000 [0.887, 0.923] | 1000/1000 [0.996, 1.000] | n/a |
| ApfGuard | P3S | 1000/1000 [0.996, 1.000] | 5 | 0.692 / 1.077 / at the local value | 28/1000 [0.019, at the local value] | 1000/1000 [0.996, 1.000] | 862/1000 [0.839, 0.882] | 1000/1000 [0.996, 1.000] | n/a |
| ApfGuard | ApfStrike | 999/1000 [0.994, 1.000] | 5 | 0.521 / 0.852 / at the local value | 114/1000 [0.096, 0.135] | 999/1000 [0.994, 1.000] | 944/1000 [0.928, 0.957] | 1000/1000 [0.996, 1.000] | n/a |
| ParkedGuard | S20 | 1000/1000 [0.996, 1.000] | 5 | 1.183 / at the local value / 1.343 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 934/1000 [0.917, 0.948] | 1000/1000 [0.996, 1.000] | n/a |
| ParkedGuard | P3S | 991/1000 [0.983, 0.995] | 5 | at the local value / at the local value / 1.425 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 933/1000 [0.916, 0.947] | 1000/1000 [0.996, 1.000] | n/a |
| ParkedGuard | ApfStrike | 1000/1000 [0.996, 1.000] | 4 | 1.136 / at the local value / 1.201 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 953/1000 [0.938, 0.964] | 1000/1000 [0.996, 1.000] | n/a |

| Guard | Strike | Same-team approach 3-D, min / p5 / p50 m | Filter corrections k/n [95 %] | Correction size mean / p95 m/s | Smoothness (change of the command per drone per tick) mean / p95 m/s | Guard 0 drift min / p50 / max m |
|---|---|---|---|---|---|---|
| G19 | S20 | 0.000 / 0.007 / 0.066 | n/a | n/a | at the local value / 0.005 | 0.345 / 1.124 / 1.867 |
| G19 | P3S | 0.001 / 0.017 / 0.149 | n/a | n/a | 0.006 / 0.007 | 0.418 / 0.937 / 1.986 |
| G19 | ApfStrike | 0.000 / 0.000 / 0.005 | n/a | n/a | 0.005 / 0.006 | 0.283 / 0.794 / 1.097 |
| P3G | S20 | 0.000 / 0.025 / 0.163 | n/a | n/a | 0.005 / 0.007 | 0.177 / 0.970 / 2.898 |
| P3G | P3S | 0.000 / 0.015 / 0.152 | n/a | n/a | 0.008 / 0.011 | at the local value / 0.899 / 1.339 |
| P3G | ApfStrike | 0.000 / 0.000 / 0.000 | n/a | n/a | at the local value / 0.007 | 0.358 / 1.054 / 1.367 |
| ApfGuard | S20 | 0.000 / 0.015 / 0.152 | n/a | n/a | 0.007 / at the local value | 0.978 / 2.058 / 3.160 |
| ApfGuard | P3S | 0.001 / 0.028 / 0.211 | n/a | n/a | 0.007 / at the local value | 0.840 / 1.686 / 2.828 |
| ApfGuard | ApfStrike | 0.000 / 0.000 / 0.090 | n/a | n/a | 0.003 / 0.009 | 0.735 / 1.318 / 3.302 |
| ParkedGuard | S20 | 0.000 / 0.016 / 0.179 | n/a | n/a | 0.001 / 0.002 | 0.000 / 0.000 / 0.000 |
| ParkedGuard | P3S | 0.001 / 0.017 / 0.157 | n/a | n/a | 0.003 / at the local value | 0.000 / 0.000 / 0.000 |
| ParkedGuard | ApfStrike | 0.001 / 0.017 / 0.175 | n/a | n/a | 0.000 / 0.000 | 0.000 / 0.000 / 0.000 |



Reading: the converted Strike policies (S20 and P3S) reach the zone in nearly every game against the scripted Guards and against the parked baseline, so the baseline is no use against them: ParkedGuard lets every Strike policy through (991 to 1000 of 1000). The trained Guards do better than the baseline only against S20 and ApfStrike: G19 holds S20 (9/1000 reach) and ApfStrike (175/1000), while P3G is strongest against ApfStrike (33/1000) and loses to S20 (985/1000). P3S beats both trained Guards.

## Videos

`runs/nus_port/phase4/row_1/videos/` (two games per pair, git-ignored; partner geometry; top-down, one frame per 8 ticks at 15 frames/s; the first Strike win and the first hold among the first 16 games of each pair.).

## Full suite

See HANDOFF section 0 (the lead's run after review).

## Limits

- Observed in the replica only: no drone model, no filter. One seed, one starts file.
- Safety filter off (STANDARDS section 6.2 exception, Phase 4 ladder): INFO measurements of frozen partner policies; nothing is trained, gated or exported from them.
- The replica's throughput counts replica steps in ticks; it is not comparable with the game rows.

## Ledger

Row `T18` in `records/LEDGER.md`.

Watch the clips: [Test 1 videos](../docs/media/nus/README.md#test-1).
