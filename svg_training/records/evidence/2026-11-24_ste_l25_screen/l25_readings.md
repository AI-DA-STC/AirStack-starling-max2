# L2.5 readings (INFO): the parked-Guard screen read by its frozen spec

Spec `ste_learning/drafts/L2_5_SPEC.md`; run `runs/2026-11-24_ste_l25_screen`. Training simulator, tier 1, scripted players, T44's 1,000 3v3 starts, CPU; observed in the training simulator. Hold = Guard team wins of 1,000 games (Wilson 95 %).

"No change detected" means no change larger than this test can see, not "no effect" (Wilson 95 % intervals at 1,000 games cannot see shifts under about 40–60 games).

## Plumbing checks (read first)

| Check | Compared | Games that differ | Result |
|---|---|---|---|
| P-b | ctl_tag_off_landing v ctl_tag_off_landing_gy: outcome, end_step or closest_3d_m | 11429 of 12000 | option B shown to reach the game |
| P-c | landing v ctl_reference_replay: end_step or closest_3d_m | 6978 of 30000 | landing shown to reach the game |

Withheld: nothing (both checks hold).

## Reading 1: still Guard v the moving scripts

Worst-cell hold of each parked script against each moving script's worst-cell hold; mark_edge is the named comparator. Base is T44's game (answer known), shown beside the new-rule sets.

| Rule set | Parked | Its worst cell | v mark_edge (worst cell) | v mirror | v field |
|---|---|---|---|---|---|
| base (T44, known) | still | 430 of 1000 v strike_low (40.0–46.1 %) | still Guard below mark_edge: 808 of 1000 v strike_straight (78.2–83.1 %) | still Guard below mirror: 796 of 1000 v strike_straight (77.0–82.0 %) | still Guard below field: 716 of 1000 v strike_straight (68.7–74.3 %) |
| base (T44, known) | ring | 424 of 1000 v strike_low (39.4–45.5 %) | ring Guard below mark_edge: 808 of 1000 v strike_straight (78.2–83.1 %) | ring Guard below mirror: 796 of 1000 v strike_straight (77.0–82.0 %) | ring Guard below field: 716 of 1000 v strike_straight (68.7–74.3 %) |
| landing | still | 432 of 1000 v strike_low (40.2–46.3 %) | still Guard below mark_edge: 802 of 1000 v strike_straight (77.6–82.6 %) | still Guard below mirror: 796 of 1000 v strike_straight (77.0–82.0 %) | still Guard below field: 716 of 1000 v strike_straight (68.7–74.3 %) |
| landing | ring | 426 of 1000 v strike_low (39.6–45.7 %) | ring Guard below mark_edge: 802 of 1000 v strike_straight (77.6–82.6 %) | ring Guard below mirror: 796 of 1000 v strike_straight (77.0–82.0 %) | ring Guard below field: 716 of 1000 v strike_straight (68.7–74.3 %) |
| gy | still | 431 of 1000 v strike_low (40.1–46.2 %) | still Guard below mark_edge: 808 of 1000 v strike_straight (78.2–83.1 %) | still Guard below mirror: 799 of 1000 v strike_straight (77.3–82.3 %) | still Guard below field: 716 of 1000 v strike_straight (68.7–74.3 %) |
| gy | ring | 424 of 1000 v strike_low (39.4–45.5 %) | ring Guard below mark_edge: 808 of 1000 v strike_straight (78.2–83.1 %) | ring Guard below mirror: 799 of 1000 v strike_straight (77.3–82.3 %) | ring Guard below field: 716 of 1000 v strike_straight (68.7–74.3 %) |
| landing_gy | still | 432 of 1000 v strike_low (40.2–46.3 %) | still Guard below mark_edge: 803 of 1000 v strike_straight (77.7–82.6 %) | still Guard below mirror: 798 of 1000 v strike_straight (77.2–82.2 %) | still Guard below field: 716 of 1000 v strike_straight (68.7–74.3 %) |
| landing_gy | ring | 426 of 1000 v strike_low (39.6–45.7 %) | ring Guard below mark_edge: 803 of 1000 v strike_straight (77.7–82.6 %) | ring Guard below mirror: 798 of 1000 v strike_straight (77.2–82.2 %) | ring Guard below field: 716 of 1000 v strike_straight (68.7–74.3 %) |

Per Strike script, parked v mark_edge (same batch):

| Rule set | Strike | still | mark_edge | word | ring | word |
|---|---|---|---|---|---|---|
| base | strike_straight | 534 (50.3–56.5 %) | 808 (78.2–83.1 %) | still Guard below mark_edge | 523 (49.2–55.4 %) | ring Guard below mark_edge |
| base | strike_flank | 450 (41.9–48.1 %) | 887 (86.6–90.5 %) | still Guard below mark_edge | 477 (44.6–50.8 %) | ring Guard below mark_edge |
| base | strike_high | 466 (43.5–49.7 %) | 850 (82.7–87.1 %) | still Guard below mark_edge | 454 (42.3–48.5 %) | ring Guard below mark_edge |
| base | strike_low | 430 (40.0–46.1 %) | 844 (82.0–86.5 %) | still Guard below mark_edge | 424 (39.4–45.5 %) | ring Guard below mark_edge |
| base | strike_sacrifice | 525 (49.4–55.6 %) | 960 (94.6–97.0 %) | still Guard below mark_edge | 503 (47.2–53.4 %) | ring Guard below mark_edge |
| base | strike_converge | 986 (97.7–99.2 %) | 974 (96.2–98.2 %) | still Guard not distinguishable from mark_edge | 983 (97.3–98.9 %) | ring Guard not distinguishable from mark_edge |
| landing | strike_straight | 534 (50.3–56.5 %) | 802 (77.6–82.6 %) | still Guard below mark_edge | 524 (49.3–55.5 %) | ring Guard below mark_edge |
| landing | strike_flank | 451 (42.0–48.2 %) | 879 (85.7–89.8 %) | still Guard below mark_edge | 477 (44.6–50.8 %) | ring Guard below mark_edge |
| landing | strike_high | 467 (43.6–49.8 %) | 843 (81.9–86.4 %) | still Guard below mark_edge | 454 (42.3–48.5 %) | ring Guard below mark_edge |
| landing | strike_low | 432 (40.2–46.3 %) | 895 (87.4–91.3 %) | still Guard below mark_edge | 426 (39.6–45.7 %) | ring Guard below mark_edge |
| landing | strike_sacrifice | 523 (49.2–55.4 %) | 963 (94.9–97.3 %) | still Guard below mark_edge | 502 (47.1–53.3 %) | ring Guard below mark_edge |
| landing | strike_converge | 986 (97.7–99.2 %) | 972 (96.0–98.1 %) | still Guard not distinguishable from mark_edge | 983 (97.3–98.9 %) | ring Guard not distinguishable from mark_edge |
| gy | strike_straight | 534 (50.3–56.5 %) | 808 (78.2–83.1 %) | still Guard below mark_edge | 523 (49.2–55.4 %) | ring Guard below mark_edge |
| gy | strike_flank | 450 (41.9–48.1 %) | 891 (87.0–90.9 %) | still Guard below mark_edge | 477 (44.6–50.8 %) | ring Guard below mark_edge |
| gy | strike_high | 467 (43.6–49.8 %) | 852 (82.9–87.3 %) | still Guard below mark_edge | 454 (42.3–48.5 %) | ring Guard below mark_edge |
| gy | strike_low | 431 (40.1–46.2 %) | 847 (82.3–86.8 %) | still Guard below mark_edge | 424 (39.4–45.5 %) | ring Guard below mark_edge |
| gy | strike_sacrifice | 524 (49.3–55.5 %) | 962 (94.8–97.2 %) | still Guard below mark_edge | 502 (47.1–53.3 %) | ring Guard below mark_edge |
| gy | strike_converge | 986 (97.7–99.2 %) | 963 (94.9–97.3 %) | still Guard above mark_edge | 983 (97.3–98.9 %) | ring Guard not distinguishable from mark_edge |
| landing_gy | strike_straight | 534 (50.3–56.5 %) | 803 (77.7–82.6 %) | still Guard below mark_edge | 524 (49.3–55.5 %) | ring Guard below mark_edge |
| landing_gy | strike_flank | 451 (42.0–48.2 %) | 884 (86.3–90.2 %) | still Guard below mark_edge | 477 (44.6–50.8 %) | ring Guard below mark_edge |
| landing_gy | strike_high | 467 (43.6–49.8 %) | 845 (82.1–86.6 %) | still Guard below mark_edge | 454 (42.3–48.5 %) | ring Guard below mark_edge |
| landing_gy | strike_low | 432 (40.2–46.3 %) | 902 (88.2–91.9 %) | still Guard below mark_edge | 426 (39.6–45.7 %) | ring Guard below mark_edge |
| landing_gy | strike_sacrifice | 524 (49.3–55.5 %) | 963 (94.9–97.3 %) | still Guard below mark_edge | 502 (47.1–53.3 %) | ring Guard below mark_edge |
| landing_gy | strike_converge | 986 (97.7–99.2 %) | 965 (95.2–97.5 %) | still Guard above mark_edge | 983 (97.3–98.9 %) | ring Guard not distinguishable from mark_edge |

The driver's maximin (results.json): landing: H 0.802, R 0.198, g* guard_mark_edge, s* strike_straight; gy: H 0.808, R 0.192, g* guard_mark_edge, s* strike_straight; landing_gy: H 0.803, R 0.197, g* guard_mark_edge, s* strike_straight; ctl_reference_replay: H 0.808, R 0.192, g* guard_mark_edge, s* strike_straight; ctl_tag_off_landing: H 0.0, R 1.0, g* guard_parked_centre, s* strike_straight; ctl_tag_off_landing_gy: H 0.0, R 1.0, g* guard_parked_centre, s* strike_straight.

## Reading 2: with and without the tag (parked Guards)

| Rule set | Parked | Worst cell with the tag | Worst cell without | Word |
|---|---|---|---|---|
| landing | still | 432 of 1000 v strike_low (40.2–46.3 %) | 0 of 1000 v strike_straight (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing | ring | 426 of 1000 v strike_low (39.6–45.7 %) | 0 of 1000 v strike_straight (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing_gy | still | 432 of 1000 v strike_low (40.2–46.3 %) | 0 of 1000 v strike_straight (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing_gy | ring | 426 of 1000 v strike_low (39.6–45.7 %) | 0 of 1000 v strike_straight (0.0–0.4 %) | the tag raises the parked Guard's hold |

| Rule set | Guard | Strike | With the tag | Without | Word |
|---|---|---|---|---|---|
| landing | guard_parked_centre | strike_straight | 534 (50.3–56.5 %) | 0 (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing | guard_parked_centre | strike_flank | 451 (42.0–48.2 %) | 331 (30.3–36.1 %) | the tag raises the parked Guard's hold |
| landing | guard_parked_centre | strike_high | 467 (43.6–49.8 %) | 0 (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing | guard_parked_centre | strike_low | 432 (40.2–46.3 %) | 0 (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing | guard_parked_centre | strike_sacrifice | 523 (49.2–55.4 %) | 0 (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing | guard_parked_centre | strike_converge | 986 (97.7–99.2 %) | 0 (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing | guard_parked_ring | strike_straight | 524 (49.3–55.5 %) | 0 (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing | guard_parked_ring | strike_flank | 477 (44.6–50.8 %) | 752 (72.4–77.8 %) | the tag lowers it |
| landing | guard_parked_ring | strike_high | 454 (42.3–48.5 %) | 0 (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing | guard_parked_ring | strike_low | 426 (39.6–45.7 %) | 0 (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing | guard_parked_ring | strike_sacrifice | 502 (47.1–53.3 %) | 0 (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing | guard_parked_ring | strike_converge | 983 (97.3–98.9 %) | 0 (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing_gy | guard_parked_centre | strike_straight | 534 (50.3–56.5 %) | 0 (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing_gy | guard_parked_centre | strike_flank | 451 (42.0–48.2 %) | 171 (14.9–19.6 %) | the tag raises the parked Guard's hold |
| landing_gy | guard_parked_centre | strike_high | 467 (43.6–49.8 %) | 0 (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing_gy | guard_parked_centre | strike_low | 432 (40.2–46.3 %) | 0 (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing_gy | guard_parked_centre | strike_sacrifice | 524 (49.3–55.5 %) | 0 (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing_gy | guard_parked_centre | strike_converge | 986 (97.7–99.2 %) | 0 (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing_gy | guard_parked_ring | strike_straight | 524 (49.3–55.5 %) | 0 (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing_gy | guard_parked_ring | strike_flank | 477 (44.6–50.8 %) | 86 (7.0–10.5 %) | the tag raises the parked Guard's hold |
| landing_gy | guard_parked_ring | strike_high | 454 (42.3–48.5 %) | 0 (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing_gy | guard_parked_ring | strike_low | 426 (39.6–45.7 %) | 0 (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing_gy | guard_parked_ring | strike_sacrifice | 502 (47.1–53.3 %) | 0 (0.0–0.4 %) | the tag raises the parked Guard's hold |
| landing_gy | guard_parked_ring | strike_converge | 983 (97.3–98.9 %) | 0 (0.0–0.4 %) | the tag raises the parked Guard's hold |

**The risk word** (landing and landing_gy, both readings needed):

- landing: **not seen with scripted Strikes in this rule set** (reading 1: still Guard below mark_edge; reading 2: the tag raises the parked Guard's hold)
- landing_gy: **not seen with scripted Strikes in this rule set** (reading 1: still Guard below mark_edge; reading 2: the tag raises the parked Guard's hold)

## Reading 3: option B on and off (P2)

### landing_gy v landing

Words counted per Guard script: guard_parked_centre: no change detected × 6; guard_parked_ring: no change detected × 6; guard_mark_edge: no change detected × 6; guard_mirror: no change detected × 6; guard_field: no change detected × 6

Paired readout (games of 1,000 per cell, summed): hold → reach / reach → hold / other outcome change / same outcome, end step changed:

| Guard script | hold → reach | reach → hold | other | end step only |
|---|---|---|---|---|
| guard_parked_centre | 0 | 1 | 0 | 126 |
| guard_parked_ring | 0 | 0 | 0 | 146 |
| guard_mark_edge | 44 | 52 | 0 | 1412 |
| guard_mirror | 27 | 40 | 0 | 1402 |
| guard_field | 0 | 4 | 0 | 117 |
| **all** | **71** | **97** | **0** | **3203** |

| Guard | Strike | landing_gy | landing | Word | h→r | r→h | filter active at tag (on / off) | pushed (on / off) | filter rate (on / off) | breach (on / off) | closest 3-D m (on / off) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| guard_parked_centre | strike_straight | 534 (50.3–56.5 %) | 534 (50.3–56.5 %) | no change detected | 0 | 0 | 0.066 / 0.066 | 0.028 / 0.028 | 0.021 / 0.021 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_centre | strike_flank | 451 (42.0–48.2 %) | 451 (42.0–48.2 %) | no change detected | 0 | 0 | 0.098 / 0.098 | 0.000 / 0.000 | 0.036 / 0.036 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_centre | strike_high | 467 (43.6–49.8 %) | 467 (43.6–49.8 %) | no change detected | 0 | 0 | 0.078 / 0.077 | 0.029 / 0.029 | 0.018 / 0.018 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_centre | strike_low | 432 (40.2–46.3 %) | 432 (40.2–46.3 %) | no change detected | 0 | 0 | 0.093 / 0.092 | 0.033 / 0.032 | 0.031 / 0.031 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_centre | strike_sacrifice | 524 (49.3–55.5 %) | 523 (49.2–55.4 %) | no change detected | 0 | 1 | 0.050 / 0.050 | 0.032 / 0.033 | 0.019 / 0.019 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_centre | strike_converge | 986 (97.7–99.2 %) | 986 (97.7–99.2 %) | no change detected | 0 | 0 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_straight | 524 (49.3–55.5 %) | 524 (49.3–55.5 %) | no change detected | 0 | 0 | 0.058 / 0.058 | 0.029 / 0.029 | 0.019 / 0.019 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_flank | 477 (44.6–50.8 %) | 477 (44.6–50.8 %) | no change detected | 0 | 0 | 0.082 / 0.082 | 0.000 / 0.000 | 0.030 / 0.030 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_high | 454 (42.3–48.5 %) | 454 (42.3–48.5 %) | no change detected | 0 | 0 | 0.071 / 0.070 | 0.031 / 0.031 | 0.016 / 0.016 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_low | 426 (39.6–45.7 %) | 426 (39.6–45.7 %) | no change detected | 0 | 0 | 0.080 / 0.080 | 0.034 / 0.034 | 0.033 / 0.032 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_sacrifice | 502 (47.1–53.3 %) | 502 (47.1–53.3 %) | no change detected | 0 | 0 | 0.049 / 0.049 | 0.027 / 0.027 | 0.018 / 0.018 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_converge | 983 (97.3–98.9 %) | 983 (97.3–98.9 %) | no change detected | 0 | 0 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_straight | 803 (77.7–82.6 %) | 802 (77.6–82.6 %) | no change detected | 6 | 7 | 0.353 / 0.351 | 0.273 / 0.274 | 0.250 / 0.250 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_flank | 884 (86.3–90.2 %) | 879 (85.7–89.8 %) | no change detected | 4 | 9 | 0.331 / 0.328 | 0.267 / 0.268 | 0.255 / 0.254 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_high | 845 (82.1–86.6 %) | 843 (81.9–86.4 %) | no change detected | 6 | 8 | 0.325 / 0.324 | 0.258 / 0.262 | 0.242 / 0.242 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_low | 902 (88.2–91.9 %) | 895 (87.4–91.3 %) | no change detected | 6 | 13 | 0.386 / 0.387 | 0.244 / 0.246 | 0.258 / 0.258 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_sacrifice | 963 (94.9–97.3 %) | 963 (94.9–97.3 %) | no change detected | 2 | 2 | 0.306 / 0.307 | 0.230 / 0.230 | 0.224 / 0.224 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_converge | 965 (95.2–97.5 %) | 972 (96.0–98.1 %) | no change detected | 20 | 13 | 0.119 / 0.113 | 0.100 / 0.095 | 0.200 / 0.200 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_straight | 798 (77.2–82.2 %) | 796 (77.0–82.0 %) | no change detected | 4 | 6 | 0.324 / 0.317 | 0.253 / 0.249 | 0.234 / 0.234 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_flank | 861 (83.8–88.1 %) | 857 (83.4–87.7 %) | no change detected | 6 | 10 | 0.296 / 0.295 | 0.234 / 0.233 | 0.240 / 0.239 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_high | 842 (81.8–86.3 %) | 841 (81.7–86.2 %) | no change detected | 4 | 5 | 0.294 / 0.293 | 0.235 / 0.238 | 0.226 / 0.226 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_low | 899 (87.9–91.6 %) | 898 (87.8–91.5 %) | no change detected | 9 | 10 | 0.352 / 0.353 | 0.222 / 0.223 | 0.243 / 0.243 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_sacrifice | 927 (90.9–94.2 %) | 925 (90.7–94.0 %) | no change detected | 0 | 2 | 0.245 / 0.251 | 0.168 / 0.171 | 0.183 / 0.183 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_converge | 971 (95.9–98.0 %) | 968 (95.5–97.7 %) | no change detected | 4 | 7 | 0.061 / 0.059 | 0.052 / 0.049 | 0.135 / 0.134 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_straight | 716 (68.7–74.3 %) | 716 (68.7–74.3 %) | no change detected | 0 | 0 | 0.117 / 0.117 | 0.057 / 0.058 | 0.064 / 0.064 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_flank | 808 (78.2–83.1 %) | 807 (78.1–83.0 %) | no change detected | 0 | 1 | 0.119 / 0.119 | 0.065 / 0.065 | 0.063 / 0.063 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_high | 732 (70.4–75.9 %) | 732 (70.4–75.9 %) | no change detected | 0 | 0 | 0.124 / 0.124 | 0.067 / 0.068 | 0.064 / 0.064 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_low | 744 (71.6–77.0 %) | 744 (71.6–77.0 %) | no change detected | 0 | 0 | 0.171 / 0.170 | 0.073 / 0.074 | 0.075 / 0.075 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_sacrifice | 863 (84.0–88.3 %) | 863 (84.0–88.3 %) | no change detected | 0 | 0 | 0.127 / 0.127 | 0.066 / 0.066 | 0.066 / 0.066 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_converge | 875 (85.3–89.4 %) | 872 (85.0–89.1 %) | no change detected | 0 | 3 | 0.102 / 0.102 | 0.070 / 0.072 | 0.058 / 0.058 | 0.000 / 0.000 | 1.600 / 1.600 |

### gy v base

Words counted per Guard script: guard_parked_centre: no change detected × 6; guard_parked_ring: no change detected × 6; guard_mark_edge: no change detected × 6; guard_mirror: no change detected × 6; guard_field: no change detected × 6

Paired readout (games of 1,000 per cell, summed): hold → reach / reach → hold / other outcome change / same outcome, end step changed:

| Guard script | hold → reach | reach → hold | other | end step only |
|---|---|---|---|---|
| guard_parked_centre | 1 | 2 | 0 | 39 |
| guard_parked_ring | 1 | 0 | 0 | 32 |
| guard_mark_edge | 45 | 45 | 0 | 1327 |
| guard_mirror | 28 | 39 | 0 | 1274 |
| guard_field | 1 | 5 | 0 | 117 |
| **all** | **76** | **91** | **0** | **2789** |

| Guard | Strike | gy | base | Word | h→r | r→h | filter active at tag (on / off) | pushed (on / off) | filter rate (on / off) | breach (on / off) | closest 3-D m (on / off) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| guard_parked_centre | strike_straight | 534 (50.3–56.5 %) | 534 (50.3–56.5 %) | no change detected | 0 | 0 | 0.052 / 0.052 | 0.015 / 0.014 | 0.014 / 0.014 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_centre | strike_flank | 450 (41.9–48.1 %) | 450 (41.9–48.1 %) | no change detected | 0 | 0 | 0.098 / 0.098 | 0.000 / 0.000 | 0.025 / 0.025 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_centre | strike_high | 467 (43.6–49.8 %) | 466 (43.5–49.7 %) | no change detected | 0 | 1 | 0.063 / 0.063 | 0.016 / 0.016 | 0.013 / 0.013 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_centre | strike_low | 431 (40.1–46.2 %) | 430 (40.0–46.1 %) | no change detected | 0 | 1 | 0.071 / 0.071 | 0.019 / 0.019 | 0.013 / 0.013 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_centre | strike_sacrifice | 524 (49.3–55.5 %) | 525 (49.4–55.6 %) | no change detected | 1 | 0 | 0.046 / 0.046 | 0.029 / 0.029 | 0.014 / 0.014 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_centre | strike_converge | 986 (97.7–99.2 %) | 986 (97.7–99.2 %) | no change detected | 0 | 0 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_straight | 523 (49.2–55.4 %) | 523 (49.2–55.4 %) | no change detected | 0 | 0 | 0.048 / 0.048 | 0.017 / 0.017 | 0.013 / 0.013 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_flank | 477 (44.6–50.8 %) | 477 (44.6–50.8 %) | no change detected | 0 | 0 | 0.082 / 0.082 | 0.000 / 0.000 | 0.022 / 0.022 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_high | 454 (42.3–48.5 %) | 454 (42.3–48.5 %) | no change detected | 0 | 0 | 0.059 / 0.059 | 0.021 / 0.021 | 0.011 / 0.011 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_low | 424 (39.4–45.5 %) | 424 (39.4–45.5 %) | no change detected | 0 | 0 | 0.062 / 0.062 | 0.022 / 0.023 | 0.011 / 0.011 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_sacrifice | 502 (47.1–53.3 %) | 503 (47.2–53.4 %) | no change detected | 1 | 0 | 0.045 / 0.045 | 0.024 / 0.024 | 0.013 / 0.013 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_converge | 983 (97.3–98.9 %) | 983 (97.3–98.9 %) | no change detected | 0 | 0 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_straight | 808 (78.2–83.1 %) | 808 (78.2–83.1 %) | no change detected | 5 | 5 | 0.316 / 0.318 | 0.270 / 0.273 | 0.219 / 0.219 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_flank | 891 (87.0–90.9 %) | 887 (86.6–90.5 %) | no change detected | 5 | 9 | 0.325 / 0.324 | 0.266 / 0.268 | 0.230 / 0.229 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_high | 852 (82.9–87.3 %) | 850 (82.7–87.1 %) | no change detected | 5 | 7 | 0.302 / 0.303 | 0.260 / 0.266 | 0.223 / 0.222 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_low | 847 (82.3–86.8 %) | 844 (82.0–86.5 %) | no change detected | 5 | 8 | 0.294 / 0.293 | 0.258 / 0.260 | 0.223 / 0.223 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_sacrifice | 962 (94.8–97.2 %) | 960 (94.6–97.0 %) | no change detected | 3 | 5 | 0.298 / 0.297 | 0.230 / 0.230 | 0.203 / 0.202 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_converge | 963 (94.9–97.3 %) | 974 (96.2–98.2 %) | no change detected | 22 | 11 | 0.113 / 0.107 | 0.098 / 0.091 | 0.196 / 0.197 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_straight | 799 (77.3–82.3 %) | 796 (77.0–82.0 %) | no change detected | 4 | 7 | 0.298 / 0.294 | 0.249 / 0.247 | 0.206 / 0.206 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_flank | 863 (84.0–88.3 %) | 864 (84.1–88.4 %) | no change detected | 7 | 6 | 0.269 / 0.268 | 0.217 / 0.219 | 0.214 / 0.214 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_high | 853 (83.0–87.4 %) | 848 (82.4–86.9 %) | no change detected | 4 | 9 | 0.281 / 0.279 | 0.239 / 0.240 | 0.209 / 0.208 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_low | 846 (82.2–86.7 %) | 847 (82.3–86.8 %) | no change detected | 9 | 8 | 0.271 / 0.269 | 0.233 / 0.235 | 0.209 / 0.209 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_sacrifice | 928 (91.0–94.2 %) | 927 (90.9–94.2 %) | no change detected | 1 | 2 | 0.239 / 0.244 | 0.166 / 0.169 | 0.171 / 0.170 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_converge | 972 (96.0–98.1 %) | 968 (95.5–97.7 %) | no change detected | 3 | 7 | 0.058 / 0.055 | 0.050 / 0.046 | 0.134 / 0.133 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_straight | 716 (68.7–74.3 %) | 716 (68.7–74.3 %) | no change detected | 0 | 0 | 0.110 / 0.109 | 0.056 / 0.057 | 0.044 / 0.044 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_flank | 809 (78.3–83.2 %) | 808 (78.2–83.1 %) | no change detected | 0 | 1 | 0.118 / 0.118 | 0.065 / 0.065 | 0.047 / 0.047 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_high | 734 (70.6–76.0 %) | 734 (70.6–76.0 %) | no change detected | 0 | 0 | 0.113 / 0.113 | 0.067 / 0.068 | 0.047 / 0.047 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_low | 740 (71.2–76.6 %) | 739 (71.1–76.5 %) | no change detected | 0 | 1 | 0.118 / 0.118 | 0.073 / 0.074 | 0.049 / 0.049 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_sacrifice | 863 (84.0–88.3 %) | 862 (83.9–88.2 %) | no change detected | 0 | 1 | 0.121 / 0.121 | 0.065 / 0.066 | 0.047 / 0.047 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_converge | 872 (85.0–89.1 %) | 871 (84.9–89.0 %) | no change detected | 1 | 2 | 0.100 / 0.100 | 0.070 / 0.072 | 0.049 / 0.049 | 0.000 / 0.000 | 1.600 / 1.600 |

Guard–Strike filter activations before a tag: not shown (not recorded by the driver). The filter columns are the driver's: filter active on the tag's own tick (an upper bound), pushed together on that tick, the share of live drone-steps the filter corrected (every pair), the share of games with a breach of the 1.10 m keep-out among live drones, and the closest 3-D approach among live drones (it cannot see a landing drone).


## Reading 4: landing on and off (P7, landing part)

### landing v base

Words counted per Guard script: guard_parked_centre: no change detected × 6; guard_parked_ring: no change detected × 6; guard_mark_edge: no change detected × 5, landing raises the Guard team's hold × 1; guard_mirror: no change detected × 5, landing raises the Guard team's hold × 1; guard_field: no change detected × 6

Paired readout (games of 1,000 per cell, summed): hold → reach / reach → hold / other outcome change / same outcome, end step changed:

| Guard script | hold → reach | reach → hold | other | end step only |
|---|---|---|---|---|
| guard_parked_centre | 2 | 4 | 0 | 579 |
| guard_parked_ring | 1 | 3 | 0 | 650 |
| guard_mark_edge | 41 | 72 | 0 | 1086 |
| guard_mirror | 38 | 73 | 0 | 994 |
| guard_field | 8 | 12 | 0 | 415 |
| **all** | **90** | **164** | **0** | **3724** |

| Guard | Strike | landing | base | Word | h→r | r→h | filter active at tag (on / off) | pushed (on / off) | filter rate (on / off) | breach (on / off) | closest 3-D m (on / off) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| guard_parked_centre | strike_straight | 534 (50.3–56.5 %) | 534 (50.3–56.5 %) | no change detected | 0 | 0 | 0.066 / 0.052 | 0.028 / 0.014 | 0.021 / 0.014 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_centre | strike_flank | 451 (42.0–48.2 %) | 450 (41.9–48.1 %) | no change detected | 0 | 1 | 0.098 / 0.098 | 0.000 / 0.000 | 0.036 / 0.025 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_centre | strike_high | 467 (43.6–49.8 %) | 466 (43.5–49.7 %) | no change detected | 0 | 1 | 0.077 / 0.063 | 0.029 / 0.016 | 0.018 / 0.013 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_centre | strike_low | 432 (40.2–46.3 %) | 430 (40.0–46.1 %) | no change detected | 0 | 2 | 0.092 / 0.071 | 0.032 / 0.019 | 0.031 / 0.013 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_centre | strike_sacrifice | 523 (49.2–55.4 %) | 525 (49.4–55.6 %) | no change detected | 2 | 0 | 0.050 / 0.046 | 0.033 / 0.029 | 0.019 / 0.014 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_centre | strike_converge | 986 (97.7–99.2 %) | 986 (97.7–99.2 %) | no change detected | 0 | 0 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_straight | 524 (49.3–55.5 %) | 523 (49.2–55.4 %) | no change detected | 0 | 1 | 0.058 / 0.048 | 0.029 / 0.017 | 0.019 / 0.013 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_flank | 477 (44.6–50.8 %) | 477 (44.6–50.8 %) | no change detected | 0 | 0 | 0.082 / 0.082 | 0.000 / 0.000 | 0.030 / 0.022 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_high | 454 (42.3–48.5 %) | 454 (42.3–48.5 %) | no change detected | 0 | 0 | 0.070 / 0.059 | 0.031 / 0.021 | 0.016 / 0.011 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_low | 426 (39.6–45.7 %) | 424 (39.4–45.5 %) | no change detected | 0 | 2 | 0.080 / 0.062 | 0.034 / 0.023 | 0.032 / 0.011 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_sacrifice | 502 (47.1–53.3 %) | 503 (47.2–53.4 %) | no change detected | 1 | 0 | 0.049 / 0.045 | 0.027 / 0.024 | 0.018 / 0.013 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_converge | 983 (97.3–98.9 %) | 983 (97.3–98.9 %) | no change detected | 0 | 0 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_straight | 802 (77.6–82.6 %) | 808 (78.2–83.1 %) | no change detected | 11 | 5 | 0.351 / 0.318 | 0.274 / 0.273 | 0.250 / 0.219 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_flank | 879 (85.7–89.8 %) | 887 (86.6–90.5 %) | no change detected | 17 | 9 | 0.328 / 0.324 | 0.268 / 0.268 | 0.254 / 0.229 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_high | 843 (81.9–86.4 %) | 850 (82.7–87.1 %) | no change detected | 11 | 4 | 0.324 / 0.303 | 0.262 / 0.266 | 0.242 / 0.222 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_low | 895 (87.4–91.3 %) | 844 (82.0–86.5 %) | landing raises the Guard team's hold | 0 | 51 | 0.387 / 0.293 | 0.246 / 0.260 | 0.258 / 0.223 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_sacrifice | 963 (94.9–97.3 %) | 960 (94.6–97.0 %) | no change detected | 0 | 3 | 0.307 / 0.297 | 0.230 / 0.230 | 0.224 / 0.202 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_converge | 972 (96.0–98.1 %) | 974 (96.2–98.2 %) | no change detected | 2 | 0 | 0.113 / 0.107 | 0.095 / 0.091 | 0.200 / 0.197 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_straight | 796 (77.0–82.0 %) | 796 (77.0–82.0 %) | no change detected | 10 | 10 | 0.317 / 0.294 | 0.249 / 0.247 | 0.234 / 0.206 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_flank | 857 (83.4–87.7 %) | 864 (84.1–88.4 %) | no change detected | 12 | 5 | 0.295 / 0.268 | 0.233 / 0.219 | 0.239 / 0.214 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_high | 841 (81.7–86.2 %) | 848 (82.4–86.9 %) | no change detected | 12 | 5 | 0.293 / 0.279 | 0.238 / 0.240 | 0.226 / 0.208 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_low | 898 (87.8–91.5 %) | 847 (82.3–86.8 %) | landing raises the Guard team's hold | 1 | 52 | 0.353 / 0.269 | 0.223 / 0.235 | 0.243 / 0.209 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_sacrifice | 925 (90.7–94.0 %) | 927 (90.9–94.2 %) | no change detected | 3 | 1 | 0.251 / 0.244 | 0.171 / 0.169 | 0.183 / 0.170 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_converge | 968 (95.5–97.7 %) | 968 (95.5–97.7 %) | no change detected | 0 | 0 | 0.059 / 0.055 | 0.049 / 0.046 | 0.134 / 0.133 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_straight | 716 (68.7–74.3 %) | 716 (68.7–74.3 %) | no change detected | 1 | 1 | 0.117 / 0.109 | 0.058 / 0.057 | 0.064 / 0.044 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_flank | 807 (78.1–83.0 %) | 808 (78.2–83.1 %) | no change detected | 2 | 1 | 0.119 / 0.118 | 0.065 / 0.065 | 0.063 / 0.047 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_high | 732 (70.4–75.9 %) | 734 (70.6–76.0 %) | no change detected | 2 | 0 | 0.124 / 0.113 | 0.068 / 0.068 | 0.064 / 0.047 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_low | 744 (71.6–77.0 %) | 739 (71.1–76.5 %) | no change detected | 2 | 7 | 0.170 / 0.118 | 0.074 / 0.074 | 0.075 / 0.049 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_sacrifice | 863 (84.0–88.3 %) | 862 (83.9–88.2 %) | no change detected | 0 | 1 | 0.127 / 0.121 | 0.066 / 0.066 | 0.066 / 0.047 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_converge | 872 (85.0–89.1 %) | 871 (84.9–89.0 %) | no change detected | 1 | 2 | 0.102 / 0.100 | 0.072 / 0.072 | 0.058 / 0.049 | 0.000 / 0.000 | 1.600 / 1.600 |

### landing_gy v gy

Words counted per Guard script: guard_parked_centre: no change detected × 6; guard_parked_ring: no change detected × 6; guard_mark_edge: no change detected × 5, landing raises the Guard team's hold × 1; guard_mirror: no change detected × 5, landing raises the Guard team's hold × 1; guard_field: no change detected × 6

Paired readout (games of 1,000 per cell, summed): hold → reach / reach → hold / other outcome change / same outcome, end step changed:

| Guard script | hold → reach | reach → hold | other | end step only |
|---|---|---|---|---|
| guard_parked_centre | 0 | 2 | 0 | 590 |
| guard_parked_ring | 0 | 3 | 0 | 652 |
| guard_mark_edge | 38 | 77 | 0 | 1126 |
| guard_mirror | 32 | 69 | 0 | 1050 |
| guard_field | 9 | 13 | 0 | 422 |
| **all** | **79** | **164** | **0** | **3840** |

| Guard | Strike | landing_gy | gy | Word | h→r | r→h | filter active at tag (on / off) | pushed (on / off) | filter rate (on / off) | breach (on / off) | closest 3-D m (on / off) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| guard_parked_centre | strike_straight | 534 (50.3–56.5 %) | 534 (50.3–56.5 %) | no change detected | 0 | 0 | 0.066 / 0.052 | 0.028 / 0.015 | 0.021 / 0.014 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_centre | strike_flank | 451 (42.0–48.2 %) | 450 (41.9–48.1 %) | no change detected | 0 | 1 | 0.098 / 0.098 | 0.000 / 0.000 | 0.036 / 0.025 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_centre | strike_high | 467 (43.6–49.8 %) | 467 (43.6–49.8 %) | no change detected | 0 | 0 | 0.078 / 0.063 | 0.029 / 0.016 | 0.018 / 0.013 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_centre | strike_low | 432 (40.2–46.3 %) | 431 (40.1–46.2 %) | no change detected | 0 | 1 | 0.093 / 0.071 | 0.033 / 0.019 | 0.031 / 0.013 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_centre | strike_sacrifice | 524 (49.3–55.5 %) | 524 (49.3–55.5 %) | no change detected | 0 | 0 | 0.050 / 0.046 | 0.032 / 0.029 | 0.019 / 0.014 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_centre | strike_converge | 986 (97.7–99.2 %) | 986 (97.7–99.2 %) | no change detected | 0 | 0 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_straight | 524 (49.3–55.5 %) | 523 (49.2–55.4 %) | no change detected | 0 | 1 | 0.058 / 0.048 | 0.029 / 0.017 | 0.019 / 0.013 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_flank | 477 (44.6–50.8 %) | 477 (44.6–50.8 %) | no change detected | 0 | 0 | 0.082 / 0.082 | 0.000 / 0.000 | 0.030 / 0.022 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_high | 454 (42.3–48.5 %) | 454 (42.3–48.5 %) | no change detected | 0 | 0 | 0.071 / 0.059 | 0.031 / 0.021 | 0.016 / 0.011 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_low | 426 (39.6–45.7 %) | 424 (39.4–45.5 %) | no change detected | 0 | 2 | 0.080 / 0.062 | 0.034 / 0.022 | 0.033 / 0.011 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_sacrifice | 502 (47.1–53.3 %) | 502 (47.1–53.3 %) | no change detected | 0 | 0 | 0.049 / 0.045 | 0.027 / 0.024 | 0.018 / 0.013 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_parked_ring | strike_converge | 983 (97.3–98.9 %) | 983 (97.3–98.9 %) | no change detected | 0 | 0 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_straight | 803 (77.7–82.6 %) | 808 (78.2–83.1 %) | no change detected | 10 | 5 | 0.353 / 0.316 | 0.273 / 0.270 | 0.250 / 0.219 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_flank | 884 (86.3–90.2 %) | 891 (87.0–90.9 %) | no change detected | 14 | 7 | 0.331 / 0.325 | 0.267 / 0.266 | 0.255 / 0.230 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_high | 845 (82.1–86.6 %) | 852 (82.9–87.3 %) | no change detected | 10 | 3 | 0.325 / 0.302 | 0.258 / 0.260 | 0.242 / 0.223 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_low | 902 (88.2–91.9 %) | 847 (82.3–86.8 %) | landing raises the Guard team's hold | 2 | 57 | 0.386 / 0.294 | 0.244 / 0.258 | 0.258 / 0.223 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_sacrifice | 963 (94.9–97.3 %) | 962 (94.8–97.2 %) | no change detected | 1 | 2 | 0.306 / 0.298 | 0.230 / 0.230 | 0.224 / 0.203 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mark_edge | strike_converge | 965 (95.2–97.5 %) | 963 (94.9–97.3 %) | no change detected | 1 | 3 | 0.119 / 0.113 | 0.100 / 0.098 | 0.200 / 0.196 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_straight | 798 (77.2–82.2 %) | 799 (77.3–82.3 %) | no change detected | 10 | 9 | 0.324 / 0.298 | 0.253 / 0.249 | 0.234 / 0.206 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_flank | 861 (83.8–88.1 %) | 863 (84.0–88.3 %) | no change detected | 5 | 3 | 0.296 / 0.269 | 0.234 / 0.217 | 0.240 / 0.214 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_high | 842 (81.8–86.3 %) | 853 (83.0–87.4 %) | no change detected | 14 | 3 | 0.294 / 0.281 | 0.235 / 0.239 | 0.226 / 0.209 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_low | 899 (87.9–91.6 %) | 846 (82.2–86.7 %) | landing raises the Guard team's hold | 0 | 53 | 0.352 / 0.271 | 0.222 / 0.233 | 0.243 / 0.209 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_sacrifice | 927 (90.9–94.2 %) | 928 (91.0–94.2 %) | no change detected | 2 | 1 | 0.245 / 0.239 | 0.168 / 0.166 | 0.183 / 0.171 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_mirror | strike_converge | 971 (95.9–98.0 %) | 972 (96.0–98.1 %) | no change detected | 1 | 0 | 0.061 / 0.058 | 0.052 / 0.050 | 0.135 / 0.134 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_straight | 716 (68.7–74.3 %) | 716 (68.7–74.3 %) | no change detected | 1 | 1 | 0.117 / 0.110 | 0.057 / 0.056 | 0.064 / 0.044 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_flank | 808 (78.2–83.1 %) | 809 (78.3–83.2 %) | no change detected | 2 | 1 | 0.119 / 0.118 | 0.065 / 0.065 | 0.063 / 0.047 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_high | 732 (70.4–75.9 %) | 734 (70.6–76.0 %) | no change detected | 2 | 0 | 0.124 / 0.113 | 0.067 / 0.067 | 0.064 / 0.047 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_low | 744 (71.6–77.0 %) | 740 (71.2–76.6 %) | no change detected | 3 | 7 | 0.171 / 0.118 | 0.073 / 0.073 | 0.075 / 0.049 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_sacrifice | 863 (84.0–88.3 %) | 863 (84.0–88.3 %) | no change detected | 0 | 0 | 0.127 / 0.121 | 0.066 / 0.065 | 0.066 / 0.047 | 0.000 / 0.000 | 1.600 / 1.600 |
| guard_field | strike_converge | 875 (85.3–89.4 %) | 872 (85.0–89.1 %) | no change detected | 1 | 4 | 0.102 / 0.100 | 0.070 / 0.070 | 0.058 / 0.049 | 0.000 / 0.000 | 1.600 / 1.600 |

