Simulator: training simulator, tier 2 (Isaac Lab physics drones: rigid-body Starlings, headless; safety filter on, drones free in height with the start jitter). Not a flight result.

# 2026-11-18 NUS port, Phase 4 rung 6 (T24): the physics drone (INFO)

| Item | Value |
|---|---|
| Purpose | Row 6: row 5's settings with the drone changed from the fitted response model to the Isaac Lab rigid-body Starling (`drone = "physics"`, the plan's rung 6). 24 pairs, 1,000 games each, the same paired starts file |
| Plan | `docs/plans/2026-11-18-nus-phase4-transfer-ladder.md` v2 with the owner's answers (INFO run: each `gates.toml` has `gates = []` and the reading rules as text, written before the run) |
| Pre-flight | `scripts/isaac_preflight.sh --approved-headless` exit 0 at 11:48 (+08:00; `runs/nus_port/phase4/preflight_row6.txt`, 5090 only); headless Isaac Lab, no AirStack simulator up, GPU otherwise idle |
| Date, machine | 2026-11-18, 11:48 to 13:54 (+08:00), home RTX 5090 workstation |
| Code | branch `phase6-pass2` (current `main`, commit `fcbdfa72`) plus one uncommitted configuration edit (`configs/nus_phase4.toml`, row 5a `blocks = ["core"]`, owner's decision 18 Nov 2026 ~08:20); the lead commits. Rows 4, 5a, 5 and 6 ran one after the other in one detached chain (`runs/nus_port/phase4/chain_rows_4_to_6.log`, 5090 only), all exit 0 |
| Config and local files | `configs/nus_phase4.toml` (rows, pairs, counts), `configs/nus_hangar_game.toml` (generic game settings), the Starling parameter file `params/real_exploratory_v0.toml` (EXPLORATORY drone model, T5 = FAIL: it answers more slowly than the real drone, so rows 3 to 5 overstate the lag cost), git-ignored `configs/local/nus_rules.toml`, `nus_deploy.toml`, `nus_deploy_ref.toml`, `nus_hangar.toml` (no value is written here). sha256 prefixes at run time: deploy_ref `6d71c111959fd9b2`, deploy_w2 `c248c6bef3f6e17b`, game_config `3f771112bd3f0370`, hangar `b7f2870ee17d2d70`, rules `dd22cc28ce2042f3`, settings `64ae48cf4f51be37`, starts `40c8cc59297f58d5` |
| Seeds | one seed for the paired starts file (`[ladder] seed`, PROPOSED): one seed, so no method claim (STANDARDS section 6.5) |

| Item | Value |
|---|---|
| Machine | home workstation, NVIDIA GeForce RTX 5090; torch 2.7.0+cu128; Python 3.11.18 |
| Games | 1000 per pair, 24 pairs, 6 drones per game, tier: tier 2 (Isaac Lab physics drone) |
| Throughput | 2,654 game-steps/s (15,925 drone-steps/s), 1000 games x 6 drones, tier 2, NVIDIA GeForce RTX 5090 |
| Run time | 7,536 s (2.09 h) against the warm-up estimate of 16,422 s (4.56 h): the observed time was 0.46 of the estimate |

## Checks of this rung

| Check | Result |
|---|---|
| Reading rule 4: upsets | **0 of 1,000 in every one of the 24 pairs** (an upset: a live drone of the game tipped past 60 degrees or its state turned non-finite; `core/game.py` D10); no stop |
| Reading rule 4: non-finite wrench | none: the upset flag above also covers a non-finite drone state, and the runner refuses to score a non-finite action; exit 0 |
| Reading rule 4: contact | the Contact column is the game's own definition and equals rows 4 and 5 pair by pair; the scores keep no separate physical-contact counter, so none is reported here |
| Reading rule 1: ParkedGuard against ApfStrike | held 0.000; no stop |

## Results

| Guard | Strike | Strike reach, k/n [95 % interval] | Reach time, median s | Closest approach Guard-Strike 3-D, min / p5 / p50 m | Rule breach | Filter breach | Contact | Start miss | Games whose outcome differs from row 5 |
|---|---|---|---|---|---|---|---|---|---|
| G19 | S20 | 979/1000 [0.968, 0.986] | 26.750 | 1.043 / 1.085 / 1.097 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 16 |
| G19 | P3S | 1000/1000 [0.996, 1.000] | 5.550 | 0.918 / 1.067 / 1.096 | 3/1000 [0.001, 0.009] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| G19 | ApfStrike | 1000/1000 [0.996, 1.000] | 3.450 | 0.777 / 1.040 / 1.076 | 8/1000 [at the local value, 0.016] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| P3G | S20 | 928/1000 [0.910, 0.942] | 19.500 | 1.047 / 1.080 / 1.099 | 0/1000 [0.000, at the local value] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 68 |
| P3G | P3S | 1000/1000 [0.996, 1.000] | 5.400 | 0.917 / 1.067 / 1.097 | 4/1000 [0.002, at the local value] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| P3G | ApfStrike | 1000/1000 [0.996, 1.000] | 3.450 | 0.858 / 1.041 / 1.079 | 6/1000 [0.003, 0.013] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | S20 | 1000/1000 [0.996, 1.000] | 6.550 | 0.883 / 1.047 / 1.085 | 7/1000 [0.003, 0.014] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | P3S | 1000/1000 [0.996, 1.000] | 4.950 | 0.675 / 1.038 / 1.072 | 10/1000 [0.005, 0.018] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | ApfStrike | 1000/1000 [0.996, 1.000] | at the local value | 0.779 / 1.024 / 1.054 | 14/1000 [0.008, 0.023] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | S20 | 524/1000 [0.493, 0.555] | 11.600 | 0.993 / 1.093 / 1.142 | 1/1000 [0.000, 0.006] | 1000/1000 [0.996, 1.000] | 923/1000 [0.905, 0.938] | 1000/1000 [0.996, 1.000] | 247 |
| ParkedGuard | P3S | 1000/1000 [0.996, 1.000] | 4.300 | 0.802 / 1.060 / 1.108 | 6/1000 [0.003, 0.013] | 1000/1000 [0.996, 1.000] | 923/1000 [0.905, 0.938] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | ApfStrike | 1000/1000 [0.996, 1.000] | at the local value | 0.810 / 1.040 / 1.083 | 11/1000 [0.006, 0.020] | 1000/1000 [0.996, 1.000] | 923/1000 [0.905, 0.938] | 1000/1000 [0.996, 1.000] | 0 |
| G19 | strike_straight | 1000/1000 [0.996, 1.000] | 3.450 | 0.777 / 1.040 / 1.075 | 9/1000 [0.005, 0.017] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| G19 | strike_flank | 1000/1000 [0.996, 1.000] | 10.150 | 0.730 / 1.062 / 1.093 | 4/1000 [0.002, at the local value] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| P3G | strike_straight | 1000/1000 [0.996, 1.000] | 3.450 | 0.903 / 1.041 / 1.079 | 5/1000 [0.002, 0.012] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| P3G | strike_flank | 1000/1000 [0.996, 1.000] | 9.050 | 0.730 / 1.068 / 1.094 | 4/1000 [0.002, at the local value] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | strike_straight | 1000/1000 [0.996, 1.000] | at the local value | 0.862 / 1.041 / 1.083 | 12/1000 [0.007, 0.021] | 1000/1000 [0.996, 1.000] | 923/1000 [0.905, 0.938] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | strike_flank | 1000/1000 [0.996, 1.000] | 6.300 | 0.761 / 1.052 / 1.096 | 6/1000 [0.003, 0.013] | 1000/1000 [0.996, 1.000] | 924/1000 [0.906, 0.939] | 1000/1000 [0.996, 1.000] | 0 |
| guard_mirror | S20 | 1000/1000 [0.996, 1.000] | 7.950 | 0.925 / 1.055 / 1.096 | 1/1000 [0.000, 0.006] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| guard_mirror | P3S | 1000/1000 [0.996, 1.000] | 4.400 | 0.785 / 1.043 / 1.093 | 7/1000 [0.003, 0.014] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| guard_mirror | ApfStrike | 961/1000 [0.947, 0.971] | 3.300 | 0.564 / 1.027 / 1.067 | 15/1000 [0.009, 0.025] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 38 |
| guard_mark_edge | S20 | 1000/1000 [0.996, 1.000] | 13.650 | 0.915 / 1.051 / 1.095 | 1/1000 [0.000, 0.006] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| guard_mark_edge | P3S | 1000/1000 [0.996, 1.000] | 4.950 | 0.822 / 1.046 / 1.089 | 6/1000 [0.003, 0.013] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| guard_mark_edge | ApfStrike | 945/1000 [0.929, 0.958] | 3.300 | 0.730 / 1.027 / 1.068 | 17/1000 [0.011, 0.027] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 31 |

| Guard | Strike | Same-team approach 3-D, min / p5 / p50 m | Filter corrections k/n [95 %] | Correction size mean / p95 m/s | Smoothness (change of the command per drone per tick) mean / p95 m/s | Guard 0 drift min / p50 / max m |
|---|---|---|---|---|---|---|
| G19 | S20 | 0.006 / 0.058 / 0.294 | 2035235/3830970 [0.531, 0.532] | 0.093 / 0.148 | at the local value / 0.006 | 0.362 / 1.011 / 1.782 |
| G19 | P3S | 0.006 / 0.058 / 0.294 | 495336/793584 [0.623, 0.625] | 0.168 / 0.196 | 0.007 / 0.009 | 0.315 / 0.923 / 2.505 |
| G19 | ApfStrike | 0.006 / 0.058 / 0.294 | 314291/473718 [0.662, 0.665] | 0.188 / 0.214 | at the local value / 0.005 | 0.178 / 0.899 / 2.083 |
| P3G | S20 | 0.006 / 0.058 / 0.294 | 1235493/3461250 [0.356, 0.357] | 0.118 / 0.183 | 0.005 / 0.008 | 0.492 / 1.122 / 1.910 |
| P3G | P3S | 0.006 / 0.058 / 0.294 | 451293/723396 [0.623, 0.625] | 0.171 / 0.204 | 0.008 / at the local value | 0.407 / 0.927 / 1.689 |
| P3G | ApfStrike | 0.006 / 0.058 / 0.294 | 312896/460260 [0.678, 0.681] | 0.191 / 0.216 | at the local value / 0.006 | 0.290 / 0.900 / 1.686 |
| ApfGuard | S20 | 0.006 / 0.058 / 0.294 | 504995/811968 [0.621, 0.623] | 0.184 / 0.210 | 0.007 / 0.009 | 0.576 / 1.763 / 2.938 |
| ApfGuard | P3S | 0.006 / 0.058 / 0.294 | 428335/637248 [0.671, 0.673] | 0.193 / 0.216 | 0.007 / 0.009 | 0.436 / 1.555 / 2.671 |
| ApfGuard | ApfStrike | 0.006 / 0.058 / 0.294 | 360385/509400 [0.706, 0.709] | 0.210 / 0.233 | 0.003 / 0.005 | 0.382 / 1.350 / 4.950 |
| ParkedGuard | S20 | 0.001 / 0.018 / 0.196 | 896815/8059776 [0.111, 0.111] | 0.073 / 0.236 | 0.003 / 0.006 | 0.119 / 0.706 / 1.328 |
| ParkedGuard | P3S | 0.001 / 0.018 / 0.196 | 203698/528006 [0.384, 0.387] | 0.181 / 0.227 | at the local value / 0.005 | 0.119 / 0.703 / 1.351 |
| ParkedGuard | ApfStrike | 0.001 / 0.018 / 0.196 | 211608/404382 [0.522, 0.525] | 0.194 / 0.223 | 0.000 / 0.001 | 0.119 / 0.692 / 1.335 |
| G19 | strike_straight | 0.006 / 0.058 / 0.294 | 321331/479346 [0.669, 0.672] | 0.188 / 0.214 | at the local value / 0.005 | 0.178 / 0.900 / 2.044 |
| G19 | strike_flank | 0.006 / 0.058 / 0.294 | 1110444/1327944 [0.836, 0.837] | 0.173 / at the local value | 0.017 / 0.038 | 0.316 / 0.948 / 2.970 |
| P3G | strike_straight | 0.006 / 0.058 / 0.294 | 315889/461982 [0.682, 0.685] | 0.192 / 0.217 | at the local value / 0.006 | 0.290 / 0.899 / 1.686 |
| P3G | strike_flank | 0.006 / 0.058 / 0.294 | 942318/1138260 [0.827, 0.829] | 0.179 / 0.212 | 0.014 / 0.027 | 0.376 / 0.972 / 1.685 |
| ParkedGuard | strike_straight | 0.001 / 0.018 / 0.196 | 213344/404934 [0.525, 0.528] | 0.194 / 0.225 | 0.000 / 0.001 | 0.119 / 0.694 / 1.340 |
| ParkedGuard | strike_flank | 0.001 / 0.018 / 0.196 | 576322/868656 [0.662, 0.664] | 0.164 / 0.205 | at the local value / 0.024 | 0.118 / 0.714 / 1.328 |
| guard_mirror | S20 | 0.006 / 0.058 / 0.294 | 714507/1192164 [0.598, at the local value] | 0.190 / 0.219 | 0.008 / 0.012 | 0.391 / 1.665 / 2.347 |
| guard_mirror | P3S | 0.006 / 0.058 / 0.294 | 318364/571152 [0.556, 0.559] | 0.196 / 0.226 | 0.008 / 0.011 | 0.239 / 1.211 / 2.128 |
| guard_mirror | ApfStrike | 0.006 / 0.058 / 0.294 | 506148/992898 [0.509, 0.511] | 0.193 / 0.229 | at the local value / 0.008 | 0.257 / 1.061 / 2.270 |
| guard_mark_edge | S20 | 0.006 / 0.058 / 0.294 | 975908/1601916 [0.608, 0.610] | 0.175 / 0.207 | 0.006 / 0.008 | 0.593 / 1.551 / 2.004 |
| guard_mark_edge | P3S | 0.006 / 0.058 / 0.294 | 503123/731340 [0.687, 0.689] | 0.194 / 0.219 | 0.006 / 0.007 | 0.257 / 1.187 / 1.797 |
| guard_mark_edge | ApfStrike | 0.006 / 0.058 / 0.294 | 536016/1229832 [0.435, 0.437] | 0.199 / 0.230 | 0.002 / 0.003 | 0.257 / 1.057 / 1.923 |

Reading (observed in the training simulator; one seed): against row 5 (fitted drone), the physics drone changes few outcomes. Strike reach is 1,000 of 1,000 in 19 of 24 pairs on row 6, and the other five are against S20 and, for our two scripted Guards, ApfStrike (row 5 to row 6): G19/S20 983 to 979 (16 games differ), P3G/S20 924 to 928 (68), ParkedGuard/S20 571 to 524 (247 differ, the largest change), guard_mirror/ApfStrike 959 to 961 (38), guard_mark_edge/ApfStrike 962 to 945 (31). The rule breach count is lower on row 6 than on row 5 in all 24 pairs (e.g. G19/ApfStrike 73 to 8 of 1,000; G19/S20 5 to 0), and the smallest Guard-Strike closest approach is larger in 20 of 24. Along the ladder the Strike reach rate for the core pairs is, row 3 to row 4 to row 5 to row 6: G19/S20 43, 740, 983, 979; P3G/S20 926, 908, 924, 928; ParkedGuard/S20 1,000, 556, 571, 524 (each of 1,000).

## Isaac Lab camera clips

Presentation only (no gates, not a measurement). `scripts/nus_isaac_clips.py` with `configs/nus_isaac_clips.toml` plays the Phase 4 players on the row 6 game (physics drones, Starling visual, the first 16 paired starts) and records an oblique camera view, headless with cameras on (preflight exit 0, GPU free). Each recorded game repeats its dry run exactly (position difference 0, same end step and outcome) and has no upset. Six clips are in `runs/nus_port/isaac_clips/` (git-ignored; MP4 up to 10 MB, GIF up to 2 MB, each with a sidecar TOML; no overlay or sidecar states the arena size):

| Clip | Players | Shows | MP4 / GIF |
|---|---|---|---|
| `g19_vs_s20_strike_win_1`, `_2` | G19 v S20 | Strike reaches the zone at 24.1 s and at 28.7 s (no hold among the 16 candidates: 979 of 1,000 reach in the row) | 0.95 / 1.89 MB, 1.09 / 1.77 MB |
| `parked_vs_s20_strike_win_1`, `parked_vs_s20_hold_1` | ParkedGuard v S20 | a Strike win at 8.1 s and a full game the Guard holds | 0.36 / 1.75 MB, 3.90 / 1.92 MB |
| `g19_vs_apf_strike_win_1`, `_2` | G19 v ApfStrike | two Strike wins (ApfStrike reaches in 1,000 of 1,000) | 0.24 / 0.97 MB, 0.21 / 0.76 MB |

## Videos

`runs/nus_port/phase4/row_6/videos/` (27 files, git-ignored; top-down, one frame per 8 ticks at 15 frames/s; the first Strike win and the first hold among the first 16 games of each pair, drawn from the recorded positions of the physics drones).

## Limits

- Tier 2 on one seed; INFO measurements of frozen partner policies; nothing is trained, gated or exported.
- The physics drone reproduces the Starling model of the training simulator, not a flight: the rows stay a measure of transfer inside the training simulator.

## Ledger

Row `T24`.
