Simulator: training simulator, tier 1 (the hangar game with the all-pairs safety filter in place of the push-apart, the Starling layer's commander copy, delay and lag from the fitted, EXPLORATORY drone model). Not a flight result.

# 2026-11-18 NUS port, Phase 4 rung 4 (T22): the all-pairs safety filter instead of the push (INFO)

| Item | Value |
|---|---|
| Purpose | Row 4 of the transfer ladder: the one change from row 3 is `separation`, from our block push to the all-pairs safety filter (height still pinned, drone response as in row 3). 24 pairs (all three blocks), 1,000 games each, the paired starts of every earlier row |
| Plan | `docs/plans/2026-11-18-nus-phase4-transfer-ladder.md` v2 with the owner's answers (INFO run: each `gates.toml` has `gates = []` and the reading rules as text, written before the run) |
| Earlier attempt | `records/2026-11-18_nus_phase4_rung4_record.md` (T21, ABORTED, no score): that first start was stopped by hand after 7 minutes because the warm-up estimate was over the 2 h foreground limit. This record is the completed run, started afterwards in the background with `--accept-long` |
| Date, machine | 2026-11-18, started 05:52, finished 08:55 (+08:00), home RTX 5090 workstation, GPU otherwise idle |
| Code | branch `phase6-pass2` (current `main`, commit `fcbdfa72`) plus one uncommitted configuration edit (`configs/nus_phase4.toml`, row 5a `blocks = ["core"]`, owner's decision 18 Nov 2026 ~08:20); the lead commits. Rows 4, 5a, 5 and 6 ran one after the other in one detached chain (`runs/nus_port/phase4/chain_rows_4_to_6.log`, 5090 only), all exit 0 |
| Config and local files | `configs/nus_phase4.toml` (rows, pairs, counts), `configs/nus_hangar_game.toml` (generic game settings), the Starling parameter file `params/real_exploratory_v0.toml` (EXPLORATORY drone model, T5 = FAIL: it answers more slowly than the real drone, so rows 3 to 5 overstate the lag cost), git-ignored `configs/local/nus_rules.toml`, `nus_deploy.toml`, `nus_deploy_ref.toml`, `nus_hangar.toml` (no value is written here). sha256 prefixes at run time: deploy_ref `6d71c111959fd9b2`, deploy_w2 `c248c6bef3f6e17b`, game_config `3f771112bd3f0370`, hangar `b7f2870ee17d2d70`, rules `dd22cc28ce2042f3`, settings `64ae48cf4f51be37`, starts `40c8cc59297f58d5` |
| Seeds | one seed for the paired starts file (`[ladder] seed`, PROPOSED): one seed, so no method claim (STANDARDS section 6.5) |

| Item | Value |
|---|---|
| Machine | home workstation, NVIDIA GeForce RTX 5090; torch 2.7.0+cu128; Python 3.11.18 |
| Games | 1000 per pair, 24 pairs, 6 drones per game, tier: tier 1 |
| Throughput | 3,084 game-steps/s (18,504 drone-steps/s), 1000 games x 6 drones, tier 1, NVIDIA GeForce RTX 5090 (a game-step is one simulator tick) |
| Run time | 10,895 s (3.03 h) against the warm-up estimate of 22,548 s (6.26 h): the observed time was about half the estimate (the warm-up times the first ticks, where the filter is slowest) |

## Checks of this rung

| Check | Result |
|---|---|
| Reading rule 1: ParkedGuard against ApfStrike | held 0.000 of games; no stop |
| Reading rule 2 | no control row here; row 4 is the partner of control row 5a (rung 5 record) |
| Runner refusals | none (no non-finite action); exit 0 |

## Results

| Guard | Strike | Strike reach, k/n [95 % interval] | Reach time, median s | Closest approach Guard-Strike 3-D, min / p5 / p50 m | Rule breach | Filter breach | Contact | Start miss | Games whose outcome differs from row 3 |
|---|---|---|---|---|---|---|---|---|---|
| G19 | S20 | 740/1000 [0.712, 0.766] | 33.650 | 0.901 / 1.054 / 1.092 | 7/1000 [0.003, 0.014] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 717 |
| G19 | P3S | 1000/1000 [0.996, 1.000] | 5.500 | 0.595 / 1.000 / 1.057 | 51/1000 [0.039, 0.066] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| G19 | ApfStrike | 1000/1000 [0.996, 1.000] | 3.700 | 0.641 / 0.976 / 1.050 | 75/1000 [0.060, 0.093] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 592 |
| P3G | S20 | 908/1000 [0.888, 0.924] | 22.200 | 0.926 / 1.056 / 1.096 | 7/1000 [0.003, 0.014] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 112 |
| P3G | P3S | 1000/1000 [0.996, 1.000] | 5.250 | 0.570 / 0.999 / 1.060 | 52/1000 [at the local value, 0.068] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| P3G | ApfStrike | 1000/1000 [0.996, 1.000] | 3.700 | 0.646 / 0.979 / 1.054 | 76/1000 [0.061, 0.094] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 706 |
| ApfGuard | S20 | 1000/1000 [0.996, 1.000] | 8.450 | 0.893 / 1.031 / 1.068 | 13/1000 [0.008, 0.022] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | P3S | 1000/1000 [0.996, 1.000] | 5.250 | 0.603 / 1.006 / 1.057 | 47/1000 [0.036, 0.062] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 0 |
| ApfGuard | ApfStrike | 1000/1000 [0.996, 1.000] | at the local value | 0.503 / 0.964 / 1.057 | 79/1000 [0.064, 0.097] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 106 |
| ParkedGuard | S20 | 556/1000 [0.525, 0.587] | 12.500 | 0.873 / 1.049 / 1.111 | 11/1000 [0.006, 0.020] | 1000/1000 [0.996, 1.000] | 923/1000 [0.905, 0.938] | 1000/1000 [0.996, 1.000] | 444 |
| ParkedGuard | P3S | 1000/1000 [0.996, 1.000] | 4.300 | 0.682 / 0.987 / 1.074 | 59/1000 [0.046, 0.075] | 1000/1000 [0.996, 1.000] | 923/1000 [0.905, 0.938] | 1000/1000 [0.996, 1.000] | 3 |
| ParkedGuard | ApfStrike | 1000/1000 [0.996, 1.000] | 3.650 | 0.526 / 0.943 / 1.059 | 106/1000 [0.088, 0.127] | 1000/1000 [0.996, 1.000] | 923/1000 [0.905, 0.938] | 1000/1000 [0.996, 1.000] | 0 |
| G19 | strike_straight | 1000/1000 [0.996, 1.000] | 3.700 | 0.716 / 0.978 / 1.050 | 78/1000 [0.063, 0.096] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 615 |
| G19 | strike_flank | 798/1000 [0.772, 0.822] | 10.100 | 0.586 / 0.999 / 1.049 | 53/1000 [0.041, 0.069] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 768 |
| P3G | strike_straight | 1000/1000 [0.996, 1.000] | 3.700 | 0.723 / 0.971 / 1.054 | 76/1000 [0.061, 0.094] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 713 |
| P3G | strike_flank | 978/1000 [0.967, 0.985] | 9.600 | 0.609 / 1.007 / 1.053 | 37/1000 [0.027, 0.051] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 643 |
| ParkedGuard | strike_straight | 1000/1000 [0.996, 1.000] | 3.650 | 0.526 / 0.938 / 1.059 | 107/1000 [0.089, 0.128] | 1000/1000 [0.996, 1.000] | 923/1000 [0.905, 0.938] | 1000/1000 [0.996, 1.000] | 0 |
| ParkedGuard | strike_flank | 945/1000 [0.929, 0.958] | 6.350 | 0.655 / 0.987 / 1.054 | 63/1000 [0.050, 0.080] | 1000/1000 [0.996, 1.000] | 923/1000 [0.905, 0.938] | 1000/1000 [0.996, 1.000] | 179 |
| guard_mirror | S20 | 856/1000 [0.833, 0.876] | 8.850 | 0.912 / 1.032 / 1.071 | 8/1000 [at the local value, 0.016] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 799 |
| guard_mirror | P3S | 980/1000 [0.969, 0.987] | 4.500 | 0.575 / 1.008 / 1.062 | 36/1000 [0.026, 0.049] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 904 |
| guard_mirror | ApfStrike | 960/1000 [0.946, 0.970] | 3.650 | 0.733 / 0.975 / 1.062 | 72/1000 [0.058, 0.090] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 921 |
| guard_mark_edge | S20 | 994/1000 [0.987, 0.997] | 17.200 | 0.927 / 1.040 / 1.077 | 7/1000 [0.003, 0.014] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 6 |
| guard_mark_edge | P3S | 1000/1000 [0.996, 1.000] | 4.900 | at the local value / 1.011 / 1.066 | 35/1000 [0.025, 0.048] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 1 |
| guard_mark_edge | ApfStrike | 958/1000 [0.944, 0.969] | 3.650 | 0.635 / 0.973 / 1.061 | 76/1000 [0.061, 0.094] | 1000/1000 [0.996, 1.000] | 853/1000 [0.830, 0.874] | 1000/1000 [0.996, 1.000] | 920 |

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
| G19 | strike_straight | 0.002 / 0.058 / 0.294 | 361895/514080 [0.703, 0.705] | 0.207 / 0.258 | 0.003 / 0.005 | 0.198 / 0.824 / 1.921 |
| G19 | strike_flank | 0.002 / 0.058 / 0.293 | 4271732/4457580 [0.958, 0.958] | 0.175 / 0.217 | 0.014 / 0.032 | 0.292 / 0.930 / 4.002 |
| P3G | strike_straight | 0.002 / 0.058 / 0.294 | 336163/485472 [0.691, 0.694] | 0.213 / 0.258 | 0.003 / 0.005 | 0.250 / 0.833 / 1.726 |
| P3G | strike_flank | 0.002 / 0.058 / 0.293 | 1828557/2010084 [0.909, 0.910] | 0.189 / 0.227 | 0.011 / 0.021 | 0.307 / 0.947 / 1.723 |
| ParkedGuard | strike_straight | 0.001 / 0.018 / 0.195 | 278764/441162 [0.630, 0.633] | 0.212 / 0.270 | 0.000 / 0.001 | 0.120 / 0.670 / 1.473 |
| ParkedGuard | strike_flank | 0.001 / 0.018 / 0.195 | 1371628/1600806 [0.856, 0.857] | 0.147 / 0.226 | 0.007 / 0.030 | 0.120 / 0.743 / 2.345 |
| guard_mirror | S20 | 0.002 / 0.058 / 0.294 | 2755624/3318576 [0.830, 0.831] | 0.216 / 0.226 | 0.007 / 0.009 | 0.493 / 1.746 / 2.603 |
| guard_mirror | P3S | 0.002 / 0.058 / 0.294 | 633499/875112 [0.723, 0.725] | 0.218 / 0.243 | 0.007 / at the local value | 0.290 / 1.101 / 2.426 |
| guard_mirror | ApfStrike | 0.002 / 0.058 / 0.294 | 888839/1040382 [0.854, 0.855] | 0.235 / 0.255 | 0.003 / 0.007 | 0.269 / 0.950 / 1.996 |
| guard_mark_edge | S20 | 0.002 / 0.058 / 0.294 | 1629084/2657352 [0.612, 0.614] | 0.184 / 0.217 | 0.005 / 0.006 | 0.360 / 1.593 / 2.202 |
| guard_mark_edge | P3S | 0.002 / 0.058 / 0.294 | 517104/740496 [0.697, 0.699] | 0.201 / 0.241 | 0.005 / 0.007 | 0.310 / 1.099 / 2.183 |
| guard_mark_edge | ApfStrike | 0.002 / 0.058 / 0.294 | 921618/1070106 [0.861, 0.862] | 0.233 / 0.256 | 0.001 / 0.002 | 0.269 / 0.945 / 2.013 |

Reading (observed in the training simulator; causes are hypotheses, not tested): replacing the push by the safety filter raises the Strike reach rate against both policy Guards: G19/S20 43 to 740 of 1,000, G19/ApfStrike 408 to 1,000, P3G/ApfStrike 294 to 1,000, ApfGuard/ApfStrike 894 to 1,000. It lowers the reach rate where the Guard stands still: ParkedGuard/S20 1,000 to 556 of 1,000. The filter moves the parked Guard (Guard 0 drift above 0 in every parked pair; it was 0 on row 3, where nothing moves it). The rule breach count, 0 on row 3 for G19 against P3S and ApfStrike, is 51 and 75 of 1,000 here. Against P3S the outcomes equal row 3 game by game for G19, P3G and ApfGuard (0 differ) and differ in 3 games for ParkedGuard. One seed; the drone model is exploratory.

## Videos

`runs/nus_port/phase4/row_4/videos/` (33 files, git-ignored; top-down, one frame per 8 ticks at 15 frames/s; the first Strike win and the first hold among the first 16 games of each pair).

## Limits

- Exploratory drone model (it answers more slowly than the real drone); one seed.
- INFO measurements of frozen partner policies: nothing is trained, gated or exported from them.

## Ledger

Row `T22`.

Watch the clips: [Test 4 videos](../docs/media/nus/README.md#test-4).
