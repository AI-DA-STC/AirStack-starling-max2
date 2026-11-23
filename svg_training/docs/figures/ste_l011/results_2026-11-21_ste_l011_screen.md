INTERNAL · results page of the L0.11 screening sweep (INFO, no gate): the full table of scored cells behind its record, observed in the training simulator · start at [../../../README.md](../../../README.md); the record: [2026-11-21_ste_l011_screen_record.md](../../../records/2026-11-21_ste_l011_screen_record.md)

# L0.11 Screening sweep (INFO): results

Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory). Observed in the training simulator; nothing here is a flight result.

- Gate file `/home/jeremychia/AirStack-starling-max2-pilot/svg_training/configs/ste_l011/gates.toml`, sha256 `8bfbc2cb8f1d6551fb3060bc750c24f9b2220ebafb19fcd44e9e3baa1c24e5d4`; commit `9b54dff6e05d`; device cuda (NVIDIA GeForce RTX 5070 Ti Laptop GPU); seed 110000; 1000 games per cell, 30 cells per batch; effective 1096 s of a 2.879 h cap.

Run notes: **Never suspend the machine during a GPU job** (a suspend counts in full against the cap and is billed as GPU-hours; tooling task L07-SUSPEND). **Finding L011-F1**: the scripted players decide every tick (0.05 s), not at the sheet's 0.6 s decision period; this sweep measures scripted play at 0.05 s; L0.12's trainers must fix their decision period explicitly (T41's recipe used 12 ticks = 0.6 s).

## Controls (read these first)

| Control | Kind | Status | Detail |
|---|---|---|---|
| ctl_tag_fires_2v1 | tag_fires | **PASS** | 1000 games: 1 tags each, all ended at step 1 |
| ctl_tag_fires_3v3 | tag_fires | **PASS** | 1000 games: 3 tags each, all ended at step 1 |
| ctl_tag_fires_5v3 | tag_fires | **PASS** | 1000 games: 3 tags each, all ended at step 1 |
| ctl_reach_fires_1v1 | reach_fires | **PASS** | 1000 reaches in 1000 games |
| ctl_reach_fires_3v3 | reach_fires | **PASS** | 1000 reaches in 1000 games |
| ctl_same_seed | same_seed_twice | **PASS** | 30000 games equal |
| ctl_stand_still | stand_still_never_reaches | **PASS** | 0 reaches in 5000 games |
| ctl_still_1v1 | stand_still_zero_tags | **PASS** | 0 tags in 1000 games |
| ctl_still_2v1 | stand_still_zero_tags | **PASS** | 0 tags in 1000 games |
| ctl_still_3v3 | stand_still_zero_tags | **PASS** | 0 tags in 1000 games |
| ctl_still_5v3 | stand_still_zero_tags | **PASS** | 0 tags in 1000 games |
| ctl_tiny_tag | zero_tags | **PASS** | 0 tags in 10000 games |
| ctl_tag_off | zero_tags | **PASS** | 0 tags in 30000 games |
| tags_one_for_one | global | **PASS** | every played game one for one |
| paired_starts | global | **PASS** | 6 start setting(s), one set of starts each |
| no_nonfinite_actions | global | **PASS** | 0 non-finite actions |

Every control holds.

## Shortlist for L0.12 (rule: gate file [shortlist])

Shortlist: **base, tag_1p2, tag_1p4**. Without the strike_high, strike_low columns (tier 1 vertical response not fitted (s2b.toml z_up_info)): base, tag_1p2, tag_1p4 (same).

| Variant | H: best Guard's worst hold | g* | R: best Strike's worst reach | s* | d (games) | eligible | rank |
|---|---|---|---|---|---|---|---|
| base | 0.81 | guard_mark_edge | 0.19 | strike_straight | 0.19 (192) | reference, ruled out because Guard-trivial looking: a scripted Guard holds against every scripted Strike | reference |
| tag_1p2 | 0.65 | guard_field | 0.35 | strike_straight | 0.35 (355) | eligible | 1 |
| tag_1p4 | 0.67 | guard_mirror | 0.33 | strike_low | 0.33 (328) | eligible | 2 |
| tag_1p8 | 0.93 | guard_mark_edge | 0.07 | strike_straight | 0.07 (68) | Guard-trivial looking: a scripted Guard holds against every scripted Strike | — |
| zone_2p4 | 0.09 | guard_field | 0.91 | strike_straight | 0.09 (89) | Strike-trivial looking: a scripted Strike reaches against every scripted Guard | — |
| survive_1 | 1.00 | guard_parked_centre | 0.00 | strike_straight | 0.00 (0) | Guard-trivial looking: a scripted Guard holds against every scripted Strike | — |
| arena_7p5 | 0.92 | guard_mark_edge | 0.08 | strike_straight | 0.08 (80) | Guard-trivial looking: a scripted Guard holds against every scripted Strike | — |
| size_1v1 | 1.00 | guard_mark_edge | 0.00 | strike_straight | 0.00 (0) | Guard-trivial looking: a scripted Guard holds against every scripted Strike | report only |
| size_2v1 | 1.00 | guard_mark_edge | 0.00 | strike_straight | 0.00 (0) | Guard-trivial looking: a scripted Guard holds against every scripted Strike | report only |
| size_5v3 | 1.00 | guard_mark_edge | 0.00 | strike_low | 0.00 (2) | Guard-trivial looking: a scripted Guard holds against every scripted Strike | report only |
| no proximity tag (INFO; ctl_tag_off) | 0.00 | guard_parked_centre | 1.00 | strike_high | 0.00 (0) | INFO reference (no proximity tag): never shortlisted; Strike-trivial looking: a scripted Strike reaches against every scripted Guard | INFO, never shortlisted |

## Sensitivity: every Strike drone starts 1 mm higher

INFO, group `sens_strike_dz_1mm` against the base cells of the same pairs (paired starts, only the Strike start height differs). tier 1 vertical response not fitted (s2b.toml z_up_info): a change here is a tier-1 effect (T13: on the physics drone a 1 mm offset flips over/under outcomes).

| Guard | Strike | hold, base (95 %) | hold, offset (95 %) | difference |
|---|---|---|---|---|
| parked (holds starts; = still at 2+ Guards) | strike_straight | 53.4 % (50.3–56.5) | 53.4 % (50.3–56.5) | +0.0 points |
| guard_parked_ring | strike_straight | 52.3 % (49.2–55.4) | 52.3 % (49.2–55.4) | +0.0 points |
| guard_mark_edge | strike_straight | 80.8 % (78.2–83.1) | 80.8 % (78.2–83.1) | +0.0 points |
| guard_mirror | strike_straight | 79.6 % (77.0–82.0) | 79.6 % (77.0–82.0) | +0.0 points |
| guard_field | strike_straight | 71.6 % (68.7–74.3) | 71.6 % (68.7–74.3) | +0.0 points |

## ctl_tag_fires_2v1: control tag_fires (2v1, game `tag_10m`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| zero | zero | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | n/a / n/a / n/a | n/a | 0 of 1000 | 1.00 | 0.05 / 0.05 |

## ctl_tag_fires_3v3: control tag_fires (3v3, game `tag_10m`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| zero | zero | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | n/a / n/a / n/a | n/a | 1000 of 1000 | 0.00 | 0.05 / 0.05 |

## ctl_tag_fires_5v3: control tag_fires (5v3, game `tag_10m`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| zero | zero | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | n/a / n/a / n/a | n/a | 0 of 1000 | 2.00 | 0.05 / 0.05 |

## ctl_reach_fires_1v1: control reach_fires (1v1, game `zone_2p4_tag_off`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| zero | strike_straight | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.60 / 1.82 / 2.40 | 1.60 | 0 of 0 | n/a | 1.40 / 1.40 |

## ctl_reach_fires_3v3: control reach_fires (3v3, game `zone_2p4_tag_off`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| zero | strike_straight | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.59 / 1.61 / 1.70 | 1.59 | 0 of 0 | n/a | 1.40 / 1.40 |

## base: base case, 3v3, tag 1.6 m, zone 1.6 m, survive 0, 6.5 m (3v3, game `base`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| parked (holds starts; = still at 2+ Guards) | strike_straight | 1000 | 53.4 % (50.3–56.5) | 46.6 % (43.5–49.7) | 0.0 % (0.0–0.4) | 53.4 % (50.3–56.5) | 2.53 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 534 of 534 | 0.00 | 2.85 / 2.90 |
| parked (holds starts; = still at 2+ Guards) | strike_flank | 1000 | 45.0 % (41.9–48.1) | 55.0 % (51.9–58.1) | 0.0 % (0.0–0.4) | 45.0 % (41.9–48.1) | 2.44 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 450 of 450 | 0.00 | 3.55 / 3.85 |
| parked (holds starts; = still at 2+ Guards) | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 46.6 % (43.5–49.7) | 53.4 % (50.3–56.5) | 0.0 % (0.0–0.4) | 46.6 % (43.5–49.7) | 2.46 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 466 of 466 | 0.00 | 3.40 / 3.40 |
| parked (holds starts; = still at 2+ Guards) | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 43.0 % (40.0–46.1) | 57.0 % (53.9–60.0) | 0.0 % (0.0–0.4) | 43.0 % (40.0–46.1) | 2.42 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 430 of 430 | 0.00 | 3.60 / 3.60 |
| parked (holds starts; = still at 2+ Guards) | strike_sacrifice | 1000 | 52.5 % (49.4–55.6) | 47.5 % (44.4–50.6) | 0.0 % (0.0–0.4) | 52.5 % (49.4–55.6) | 2.52 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 525 of 525 | 0.00 | 4.45 / 5.20 |
| parked (holds starts; = still at 2+ Guards) | strike_converge | 1000 | 98.6 % (97.7–99.2) | 1.4 % (0.8–2.3) | 0.0 % (0.0–0.4) | 98.6 % (97.7–99.2) | 2.99 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 986 of 986 | 0.00 | 8.10 / 13.21 |
| guard_parked_ring | strike_straight | 1000 | 52.3 % (49.2–55.4) | 47.7 % (44.6–50.8) | 0.0 % (0.0–0.4) | 52.3 % (49.2–55.4) | 2.52 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 523 of 523 | 0.00 | 2.90 / 2.90 |
| guard_parked_ring | strike_flank | 1000 | 47.7 % (44.6–50.8) | 52.3 % (49.2–55.4) | 0.0 % (0.0–0.4) | 47.7 % (44.6–50.8) | 2.46 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 477 of 477 | 0.00 | 3.50 / 3.90 |
| guard_parked_ring | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 45.4 % (42.3–48.5) | 54.6 % (51.5–57.7) | 0.0 % (0.0–0.4) | 45.4 % (42.3–48.5) | 2.44 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 454 of 454 | 0.00 | 3.40 / 3.40 |
| guard_parked_ring | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 42.4 % (39.4–45.5) | 57.6 % (54.5–60.6) | 0.0 % (0.0–0.4) | 42.4 % (39.4–45.5) | 2.41 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 424 of 424 | 0.00 | 3.60 / 3.60 |
| guard_parked_ring | strike_sacrifice | 1000 | 50.3 % (47.2–53.4) | 49.7 % (46.6–52.8) | 0.0 % (0.0–0.4) | 50.3 % (47.2–53.4) | 2.50 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 503 of 503 | 0.00 | 4.30 / 5.10 |
| guard_parked_ring | strike_converge | 1000 | 98.3 % (97.3–98.9) | 1.7 % (1.1–2.7) | 0.0 % (0.0–0.4) | 98.3 % (97.3–98.9) | 2.98 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 983 of 983 | 0.00 | 8.00 / 13.05 |
| guard_mark_edge | strike_straight | 1000 | 80.8 % (78.2–83.1) | 19.2 % (16.9–21.8) | 0.0 % (0.0–0.4) | 80.8 % (78.2–83.1) | 2.81 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 808 of 808 | 0.00 | 2.40 / 2.90 |
| guard_mark_edge | strike_flank | 1000 | 88.7 % (86.6–90.5) | 11.3 % (9.5–13.4) | 0.0 % (0.0–0.4) | 88.7 % (86.6–90.5) | 2.89 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 887 of 887 | 0.00 | 2.90 / 3.55 |
| guard_mark_edge | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 85.0 % (82.7–87.1) | 15.0 % (12.9–17.3) | 0.0 % (0.0–0.4) | 85.0 % (82.7–87.1) | 2.85 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 850 of 850 | 0.00 | 2.85 / 3.40 |
| guard_mark_edge | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 84.4 % (82.0–86.5) | 15.6 % (13.5–18.0) | 0.0 % (0.0–0.4) | 84.4 % (82.0–86.5) | 2.84 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 844 of 844 | 0.00 | 3.05 / 3.60 |
| guard_mark_edge | strike_sacrifice | 1000 | 96.0 % (94.6–97.0) | 4.0 % (3.0–5.4) | 0.0 % (0.0–0.4) | 96.0 % (94.6–97.0) | 2.96 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 960 of 960 | 0.00 | 3.55 / 4.60 |
| guard_mark_edge | strike_converge | 1000 | 97.4 % (96.2–98.2) | 2.6 % (1.8–3.8) | 0.0 % (0.0–0.4) | 97.4 % (96.2–98.2) | 2.97 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 974 of 974 | 0.00 | 5.10 / 10.06 |
| guard_mirror | strike_straight | 1000 | 79.6 % (77.0–82.0) | 20.4 % (18.0–23.0) | 0.0 % (0.0–0.4) | 79.6 % (77.0–82.0) | 2.79 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 796 of 796 | 0.00 | 2.40 / 2.90 |
| guard_mirror | strike_flank | 1000 | 86.4 % (84.1–88.4) | 13.6 % (11.6–15.9) | 0.0 % (0.0–0.4) | 86.4 % (84.1–88.4) | 2.86 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 864 of 864 | 0.00 | 3.00 / 3.55 |
| guard_mirror | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 84.8 % (82.4–86.9) | 15.2 % (13.1–17.6) | 0.0 % (0.0–0.4) | 84.8 % (82.4–86.9) | 2.85 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 848 of 848 | 0.00 | 2.80 / 3.40 |
| guard_mirror | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 84.7 % (82.3–86.8) | 15.3 % (13.2–17.7) | 0.0 % (0.0–0.4) | 84.7 % (82.3–86.8) | 2.84 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 847 of 847 | 0.00 | 3.00 / 3.60 |
| guard_mirror | strike_sacrifice | 1000 | 92.7 % (90.9–94.2) | 7.3 % (5.8–9.1) | 0.0 % (0.0–0.4) | 92.7 % (90.9–94.2) | 2.92 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 927 of 927 | 0.00 | 3.70 / 4.71 |
| guard_mirror | strike_converge | 1000 | 96.8 % (95.5–97.7) | 3.2 % (2.3–4.5) | 0.0 % (0.0–0.4) | 96.8 % (95.5–97.7) | 2.97 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 968 of 968 | 0.00 | 5.78 / 10.86 |
| guard_field | strike_straight | 1000 | 71.6 % (68.7–74.3) | 28.4 % (25.7–31.3) | 0.0 % (0.0–0.4) | 71.6 % (68.7–74.3) | 2.72 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 716 of 716 | 0.00 | 2.00 / 2.90 |
| guard_field | strike_flank | 1000 | 80.8 % (78.2–83.1) | 19.2 % (16.9–21.8) | 0.0 % (0.0–0.4) | 80.8 % (78.2–83.1) | 2.81 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 808 of 808 | 0.00 | 2.40 / 3.35 |
| guard_field | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 73.4 % (70.6–76.0) | 26.6 % (24.0–29.4) | 0.0 % (0.0–0.4) | 73.4 % (70.6–76.0) | 2.73 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 734 of 734 | 0.00 | 2.30 / 3.40 |
| guard_field | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 73.9 % (71.1–76.5) | 26.1 % (23.5–28.9) | 0.0 % (0.0–0.4) | 73.9 % (71.1–76.5) | 2.74 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 739 of 739 | 0.00 | 2.45 / 3.60 |
| guard_field | strike_sacrifice | 1000 | 86.2 % (83.9–88.2) | 13.8 % (11.8–16.1) | 0.0 % (0.0–0.4) | 86.2 % (83.9–88.2) | 2.86 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 862 of 862 | 0.00 | 2.40 / 4.05 |
| guard_field | strike_converge | 1000 | 87.1 % (84.9–89.0) | 12.9 % (11.0–15.1) | 0.0 % (0.0–0.4) | 87.1 % (84.9–89.0) | 2.87 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 871 of 871 | 0.00 | 2.80 / 5.00 |

## ctl_same_seed: control same_seed_twice (3v3, game `base`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| parked (holds starts; = still at 2+ Guards) | strike_straight | 1000 | 53.4 % (50.3–56.5) | 46.6 % (43.5–49.7) | 0.0 % (0.0–0.4) | 53.4 % (50.3–56.5) | 2.53 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 534 of 534 | 0.00 | 2.85 / 2.90 |
| parked (holds starts; = still at 2+ Guards) | strike_flank | 1000 | 45.0 % (41.9–48.1) | 55.0 % (51.9–58.1) | 0.0 % (0.0–0.4) | 45.0 % (41.9–48.1) | 2.44 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 450 of 450 | 0.00 | 3.55 / 3.85 |
| parked (holds starts; = still at 2+ Guards) | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 46.6 % (43.5–49.7) | 53.4 % (50.3–56.5) | 0.0 % (0.0–0.4) | 46.6 % (43.5–49.7) | 2.46 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 466 of 466 | 0.00 | 3.40 / 3.40 |
| parked (holds starts; = still at 2+ Guards) | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 43.0 % (40.0–46.1) | 57.0 % (53.9–60.0) | 0.0 % (0.0–0.4) | 43.0 % (40.0–46.1) | 2.42 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 430 of 430 | 0.00 | 3.60 / 3.60 |
| parked (holds starts; = still at 2+ Guards) | strike_sacrifice | 1000 | 52.5 % (49.4–55.6) | 47.5 % (44.4–50.6) | 0.0 % (0.0–0.4) | 52.5 % (49.4–55.6) | 2.52 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 525 of 525 | 0.00 | 4.45 / 5.20 |
| parked (holds starts; = still at 2+ Guards) | strike_converge | 1000 | 98.6 % (97.7–99.2) | 1.4 % (0.8–2.3) | 0.0 % (0.0–0.4) | 98.6 % (97.7–99.2) | 2.99 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 986 of 986 | 0.00 | 8.10 / 13.21 |
| guard_parked_ring | strike_straight | 1000 | 52.3 % (49.2–55.4) | 47.7 % (44.6–50.8) | 0.0 % (0.0–0.4) | 52.3 % (49.2–55.4) | 2.52 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 523 of 523 | 0.00 | 2.90 / 2.90 |
| guard_parked_ring | strike_flank | 1000 | 47.7 % (44.6–50.8) | 52.3 % (49.2–55.4) | 0.0 % (0.0–0.4) | 47.7 % (44.6–50.8) | 2.46 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 477 of 477 | 0.00 | 3.50 / 3.90 |
| guard_parked_ring | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 45.4 % (42.3–48.5) | 54.6 % (51.5–57.7) | 0.0 % (0.0–0.4) | 45.4 % (42.3–48.5) | 2.44 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 454 of 454 | 0.00 | 3.40 / 3.40 |
| guard_parked_ring | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 42.4 % (39.4–45.5) | 57.6 % (54.5–60.6) | 0.0 % (0.0–0.4) | 42.4 % (39.4–45.5) | 2.41 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 424 of 424 | 0.00 | 3.60 / 3.60 |
| guard_parked_ring | strike_sacrifice | 1000 | 50.3 % (47.2–53.4) | 49.7 % (46.6–52.8) | 0.0 % (0.0–0.4) | 50.3 % (47.2–53.4) | 2.50 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 503 of 503 | 0.00 | 4.30 / 5.10 |
| guard_parked_ring | strike_converge | 1000 | 98.3 % (97.3–98.9) | 1.7 % (1.1–2.7) | 0.0 % (0.0–0.4) | 98.3 % (97.3–98.9) | 2.98 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 983 of 983 | 0.00 | 8.00 / 13.05 |
| guard_mark_edge | strike_straight | 1000 | 80.8 % (78.2–83.1) | 19.2 % (16.9–21.8) | 0.0 % (0.0–0.4) | 80.8 % (78.2–83.1) | 2.81 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 808 of 808 | 0.00 | 2.40 / 2.90 |
| guard_mark_edge | strike_flank | 1000 | 88.7 % (86.6–90.5) | 11.3 % (9.5–13.4) | 0.0 % (0.0–0.4) | 88.7 % (86.6–90.5) | 2.89 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 887 of 887 | 0.00 | 2.90 / 3.55 |
| guard_mark_edge | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 85.0 % (82.7–87.1) | 15.0 % (12.9–17.3) | 0.0 % (0.0–0.4) | 85.0 % (82.7–87.1) | 2.85 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 850 of 850 | 0.00 | 2.85 / 3.40 |
| guard_mark_edge | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 84.4 % (82.0–86.5) | 15.6 % (13.5–18.0) | 0.0 % (0.0–0.4) | 84.4 % (82.0–86.5) | 2.84 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 844 of 844 | 0.00 | 3.05 / 3.60 |
| guard_mark_edge | strike_sacrifice | 1000 | 96.0 % (94.6–97.0) | 4.0 % (3.0–5.4) | 0.0 % (0.0–0.4) | 96.0 % (94.6–97.0) | 2.96 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 960 of 960 | 0.00 | 3.55 / 4.60 |
| guard_mark_edge | strike_converge | 1000 | 97.4 % (96.2–98.2) | 2.6 % (1.8–3.8) | 0.0 % (0.0–0.4) | 97.4 % (96.2–98.2) | 2.97 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 974 of 974 | 0.00 | 5.10 / 10.06 |
| guard_mirror | strike_straight | 1000 | 79.6 % (77.0–82.0) | 20.4 % (18.0–23.0) | 0.0 % (0.0–0.4) | 79.6 % (77.0–82.0) | 2.79 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 796 of 796 | 0.00 | 2.40 / 2.90 |
| guard_mirror | strike_flank | 1000 | 86.4 % (84.1–88.4) | 13.6 % (11.6–15.9) | 0.0 % (0.0–0.4) | 86.4 % (84.1–88.4) | 2.86 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 864 of 864 | 0.00 | 3.00 / 3.55 |
| guard_mirror | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 84.8 % (82.4–86.9) | 15.2 % (13.1–17.6) | 0.0 % (0.0–0.4) | 84.8 % (82.4–86.9) | 2.85 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 848 of 848 | 0.00 | 2.80 / 3.40 |
| guard_mirror | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 84.7 % (82.3–86.8) | 15.3 % (13.2–17.7) | 0.0 % (0.0–0.4) | 84.7 % (82.3–86.8) | 2.84 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 847 of 847 | 0.00 | 3.00 / 3.60 |
| guard_mirror | strike_sacrifice | 1000 | 92.7 % (90.9–94.2) | 7.3 % (5.8–9.1) | 0.0 % (0.0–0.4) | 92.7 % (90.9–94.2) | 2.92 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 927 of 927 | 0.00 | 3.70 / 4.71 |
| guard_mirror | strike_converge | 1000 | 96.8 % (95.5–97.7) | 3.2 % (2.3–4.5) | 0.0 % (0.0–0.4) | 96.8 % (95.5–97.7) | 2.97 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 968 of 968 | 0.00 | 5.78 / 10.86 |
| guard_field | strike_straight | 1000 | 71.6 % (68.7–74.3) | 28.4 % (25.7–31.3) | 0.0 % (0.0–0.4) | 71.6 % (68.7–74.3) | 2.72 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 716 of 716 | 0.00 | 2.00 / 2.90 |
| guard_field | strike_flank | 1000 | 80.8 % (78.2–83.1) | 19.2 % (16.9–21.8) | 0.0 % (0.0–0.4) | 80.8 % (78.2–83.1) | 2.81 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 808 of 808 | 0.00 | 2.40 / 3.35 |
| guard_field | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 73.4 % (70.6–76.0) | 26.6 % (24.0–29.4) | 0.0 % (0.0–0.4) | 73.4 % (70.6–76.0) | 2.73 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 734 of 734 | 0.00 | 2.30 / 3.40 |
| guard_field | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 73.9 % (71.1–76.5) | 26.1 % (23.5–28.9) | 0.0 % (0.0–0.4) | 73.9 % (71.1–76.5) | 2.74 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 739 of 739 | 0.00 | 2.45 / 3.60 |
| guard_field | strike_sacrifice | 1000 | 86.2 % (83.9–88.2) | 13.8 % (11.8–16.1) | 0.0 % (0.0–0.4) | 86.2 % (83.9–88.2) | 2.86 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 862 of 862 | 0.00 | 2.40 / 4.05 |
| guard_field | strike_converge | 1000 | 87.1 % (84.9–89.0) | 12.9 % (11.0–15.1) | 0.0 % (0.0–0.4) | 87.1 % (84.9–89.0) | 2.87 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 871 of 871 | 0.00 | 2.80 / 5.00 |

## ctl_stand_still: control stand_still_never_reaches (3v3, game `base`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| parked (holds starts; = still at 2+ Guards) | zero | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.95 / 1.97 / 2.05 | 1.95 | 0 of 1000 | 3.00 | 120.00 / 120.00 |
| guard_parked_ring | zero | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.93 / 1.94 / 1.97 | 1.93 | 0 of 1000 | 3.00 | 120.00 / 120.00 |
| guard_mark_edge | zero | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 1000 of 1000 | 0.00 | 7.38 / 12.65 |
| guard_mirror | zero | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 1000 of 1000 | 0.00 | 6.95 / 12.10 |
| guard_field | zero | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 1000 of 1000 | 0.00 | 3.65 / 8.60 |

## ctl_still_1v1: control stand_still_zero_tags (1v1, game `base`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| zero | zero | 0 (+1000 unfinished) | n/a | n/a | n/a | n/a | n/a (None) | 0 | 0 | n/a / n/a / n/a | n/a | 0 of 0 | n/a | n/a / n/a |

## ctl_still_2v1: control stand_still_zero_tags (2v1, game `base`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| zero | zero | 0 (+1000 unfinished) | n/a | n/a | n/a | n/a | n/a (None) | 0 | 0 | n/a / n/a / n/a | n/a | 0 of 0 | n/a | n/a / n/a |

## ctl_still_3v3: control stand_still_zero_tags (3v3, game `base`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| zero | zero | 0 (+1000 unfinished) | n/a | n/a | n/a | n/a | n/a (None) | 0 | 0 | n/a / n/a / n/a | n/a | 0 of 0 | n/a | n/a / n/a |

## ctl_still_5v3: control stand_still_zero_tags (5v3, game `base`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| zero | zero | 0 (+1000 unfinished) | n/a | n/a | n/a | n/a | n/a (None) | 0 | 0 | n/a / n/a / n/a | n/a | 0 of 0 | n/a | n/a / n/a |

## ctl_tiny_tag: control zero_tags (3v3, game `tag_0p05`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| parked (holds starts; = still at 2+ Guards) | strike_straight | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.07 / 1.07 / 1.07 | 1.07 | 0 of 0 | n/a | 2.90 / 3.05 |
| parked (holds starts; = still at 2+ Guards) | strike_sacrifice | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.06 / 1.06 / 1.07 | 1.06 | 0 of 0 | n/a | 3.05 / 3.75 |
| guard_parked_ring | strike_straight | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.06 / 1.06 / 1.07 | 1.06 | 0 of 0 | n/a | 2.90 / 3.10 |
| guard_parked_ring | strike_sacrifice | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.04 / 1.06 / 1.07 | 1.04 | 0 of 0 | n/a | 3.10 / 7.46 |
| guard_mark_edge | strike_straight | 1000 | 20.0 % (17.6–22.6) | 80.0 % (77.4–82.4) | 20.0 % (17.6–22.6) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.04 / 1.05 / 1.06 | 1.04 | 0 of 200 | 3.00 | 3.10 / 120.00 |
| guard_mark_edge | strike_sacrifice | 1000 | 44.1 % (41.1–47.2) | 55.9 % (52.8–58.9) | 44.1 % (41.1–47.2) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 0.93 / 0.99 / 1.06 | 0.93 | 0 of 441 | 3.00 | 5.43 / 120.00 |
| guard_mirror | strike_straight | 1000 | 23.5 % (21.0–26.2) | 76.5 % (73.8–79.0) | 23.5 % (21.0–26.2) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.04 / 1.05 / 1.06 | 1.04 | 0 of 235 | 3.00 | 3.10 / 120.00 |
| guard_mirror | strike_sacrifice | 1000 | 24.0 % (21.5–26.7) | 76.0 % (73.3–78.5) | 24.0 % (21.5–26.7) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 0.93 / 1.01 / 1.06 | 0.93 | 0 of 240 | 3.00 | 4.35 / 120.00 |
| guard_field | strike_straight | 1000 | 31.3 % (28.5–34.2) | 68.7 % (65.8–71.5) | 31.3 % (28.5–34.2) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.04 / 1.05 / 1.05 | 1.04 | 0 of 313 | 3.00 | 5.85 / 120.00 |
| guard_field | strike_sacrifice | 1000 | 61.8 % (58.7–64.8) | 38.2 % (35.2–41.3) | 61.8 % (58.7–64.8) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 0.94 / 1.03 / 1.05 | 0.94 | 0 of 618 | 3.00 | 120.00 / 120.00 |

## ctl_tag_off: control zero_tags (3v3, game `tag_off`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| parked (holds starts; = still at 2+ Guards) | strike_straight | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.07 / 1.07 / 1.07 | 1.07 | 0 of 0 | n/a | 2.90 / 3.05 |
| parked (holds starts; = still at 2+ Guards) | strike_flank | 1000 | 33.1 % (30.3–36.1) | 66.9 % (63.9–69.7) | 33.1 % (30.3–36.1) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.03 / 1.04 / 1.08 | 1.03 | 0 of 331 | 3.00 | 7.15 / 120.00 |
| parked (holds starts; = still at 2+ Guards) | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.09 / 1.10 / 1.10 | 0.92 | 0 of 0 | n/a | 3.40 / 3.45 |
| parked (holds starts; = still at 2+ Guards) | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.10 / 1.10 / 1.12 | 0.87 | 0 of 0 | n/a | 3.60 / 3.65 |
| parked (holds starts; = still at 2+ Guards) | strike_sacrifice | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.06 / 1.06 / 1.07 | 1.06 | 0 of 0 | n/a | 3.05 / 3.75 |
| parked (holds starts; = still at 2+ Guards) | strike_converge | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.06 / 1.06 / 1.08 | 1.06 | 0 of 0 | n/a | 9.95 / 15.45 |
| guard_parked_ring | strike_straight | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.06 / 1.06 / 1.07 | 1.06 | 0 of 0 | n/a | 2.90 / 3.10 |
| guard_parked_ring | strike_flank | 1000 | 75.2 % (72.4–77.8) | 24.8 % (22.2–27.6) | 75.2 % (72.4–77.8) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.03 / 1.04 / 1.07 | 1.03 | 0 of 752 | 3.00 | 120.00 / 120.00 |
| guard_parked_ring | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.08 / 1.09 / 1.10 | 0.87 | 0 of 0 | n/a | 3.40 / 3.45 |
| guard_parked_ring | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.09 / 1.09 / 1.10 | 0.83 | 0 of 0 | n/a | 3.60 / 3.65 |
| guard_parked_ring | strike_sacrifice | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.04 / 1.06 / 1.07 | 1.04 | 0 of 0 | n/a | 3.10 / 7.46 |
| guard_parked_ring | strike_converge | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.06 / 1.06 / 1.08 | 1.06 | 0 of 0 | n/a | 10.05 / 15.86 |
| guard_mark_edge | strike_straight | 1000 | 20.0 % (17.6–22.6) | 80.0 % (77.4–82.4) | 20.0 % (17.6–22.6) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.04 / 1.05 / 1.06 | 1.04 | 0 of 200 | 3.00 | 3.10 / 120.00 |
| guard_mark_edge | strike_flank | 1000 | 54.1 % (51.0–57.2) | 45.9 % (42.8–49.0) | 54.1 % (51.0–57.2) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.03 / 1.04 / 1.06 | 1.03 | 0 of 541 | 3.00 | 120.00 / 120.00 |
| guard_mark_edge | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.04 / 1.05 / 1.06 | 0.00 | 0 of 0 | n/a | 3.45 / 4.75 |
| guard_mark_edge | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.03 / 1.04 / 1.06 | 0.00 | 0 of 0 | n/a | 3.65 / 4.50 |
| guard_mark_edge | strike_sacrifice | 1000 | 44.1 % (41.1–47.2) | 55.9 % (52.8–58.9) | 44.1 % (41.1–47.2) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 0.93 / 0.99 / 1.06 | 0.93 | 0 of 441 | 3.00 | 5.43 / 120.00 |
| guard_mark_edge | strike_converge | 1000 | 92.5 % (90.7–94.0) | 7.5 % (6.0–9.3) | 92.5 % (90.7–94.0) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.03 / 1.05 / 1.05 | 1.03 | 0 of 925 | 3.00 | 120.00 / 120.00 |
| guard_mirror | strike_straight | 1000 | 23.5 % (21.0–26.2) | 76.5 % (73.8–79.0) | 23.5 % (21.0–26.2) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.04 / 1.05 / 1.06 | 1.04 | 0 of 235 | 3.00 | 3.10 / 120.00 |
| guard_mirror | strike_flank | 1000 | 44.4 % (41.3–47.5) | 55.6 % (52.5–58.7) | 44.4 % (41.3–47.5) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 0.98 / 1.04 / 1.06 | 0.98 | 0 of 444 | 3.00 | 13.12 / 120.00 |
| guard_mirror | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.03 / 1.04 / 1.06 | 0.00 | 0 of 0 | n/a | 3.50 / 4.70 |
| guard_mirror | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.02 / 1.03 / 1.06 | 0.00 | 0 of 0 | n/a | 3.65 / 4.45 |
| guard_mirror | strike_sacrifice | 1000 | 24.0 % (21.5–26.7) | 76.0 % (73.3–78.5) | 24.0 % (21.5–26.7) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 0.93 / 1.01 / 1.06 | 0.93 | 0 of 240 | 3.00 | 4.35 / 120.00 |
| guard_mirror | strike_converge | 1000 | 92.4 % (90.6–93.9) | 7.6 % (6.1–9.4) | 92.4 % (90.6–93.9) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 0.97 / 1.05 / 1.06 | 0.97 | 0 of 924 | 3.00 | 120.00 / 120.00 |
| guard_field | strike_straight | 1000 | 31.3 % (28.5–34.2) | 68.7 % (65.8–71.5) | 31.3 % (28.5–34.2) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.04 / 1.05 / 1.05 | 1.04 | 0 of 313 | 3.00 | 5.85 / 120.00 |
| guard_field | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.02 / 1.03 / 1.05 | 1.02 | 0 of 1000 | 3.00 | 120.00 / 120.00 |
| guard_field | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.04 / 1.04 / 1.05 | 0.00 | 0 of 0 | n/a | 4.00 / 4.95 |
| guard_field | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.03 / 1.04 / 1.05 | 0.00 | 0 of 0 | n/a | 4.08 / 4.60 |
| guard_field | strike_sacrifice | 1000 | 61.8 % (58.7–64.8) | 38.2 % (35.2–41.3) | 61.8 % (58.7–64.8) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 0.94 / 1.03 / 1.05 | 0.94 | 0 of 618 | 3.00 | 120.00 / 120.00 |
| guard_field | strike_converge | 1000 | 69.7 % (66.8–72.5) | 30.3 % (27.5–33.2) | 69.7 % (66.8–72.5) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.02 / 1.05 / 1.05 | 1.02 | 0 of 697 | 3.00 | 120.00 / 120.00 |

## sens_strike_dz_1mm: sensitivity: Strike start height, every Strike drone starts 1 mm higher (tier 1 vertical response not fitted) (3v3, game `base`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| parked (holds starts; = still at 2+ Guards) | strike_straight | 1000 | 53.4 % (50.3–56.5) | 46.6 % (43.5–49.7) | 0.0 % (0.0–0.4) | 53.4 % (50.3–56.5) | 2.53 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 534 of 534 | 0.00 | 2.85 / 2.90 |
| guard_parked_ring | strike_straight | 1000 | 52.3 % (49.2–55.4) | 47.7 % (44.6–50.8) | 0.0 % (0.0–0.4) | 52.3 % (49.2–55.4) | 2.52 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 523 of 523 | 0.00 | 2.90 / 2.90 |
| guard_mark_edge | strike_straight | 1000 | 80.8 % (78.2–83.1) | 19.2 % (16.9–21.8) | 0.0 % (0.0–0.4) | 80.8 % (78.2–83.1) | 2.81 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 808 of 808 | 0.00 | 2.40 / 2.90 |
| guard_mirror | strike_straight | 1000 | 79.6 % (77.0–82.0) | 20.4 % (18.0–23.0) | 0.0 % (0.0–0.4) | 79.6 % (77.0–82.0) | 2.79 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 796 of 796 | 0.00 | 2.40 / 2.90 |
| guard_field | strike_straight | 1000 | 71.6 % (68.7–74.3) | 28.4 % (25.7–31.3) | 0.0 % (0.0–0.4) | 71.6 % (68.7–74.3) | 2.72 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 716 of 716 | 0.00 | 2.00 / 2.90 |

## size_1v1: team size, 1v1 (1v1, game `base`)

Not played (with one Strike drone they fly as strike_straight): guard_parked_centre v strike_sacrifice, guard_parked_centre v strike_converge, guard_parked_ring v strike_sacrifice, guard_parked_ring v strike_converge, guard_mark_edge v strike_sacrifice, guard_mark_edge v strike_converge, guard_mirror v strike_sacrifice, guard_mirror v strike_converge, guard_field v strike_sacrifice, guard_field v strike_converge.

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| guard_parked_centre | strike_straight | 1000 | 69.3 % (66.4–72.1) | 30.7 % (27.9–33.6) | 0.0 % (0.0–0.4) | 69.3 % (66.4–72.1) | 0.69 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 693 of 693 | 0.00 | 2.90 / 2.90 |
| guard_parked_centre | strike_flank | 1000 | 54.1 % (51.0–57.2) | 45.9 % (42.8–49.0) | 0.0 % (0.0–0.4) | 54.1 % (51.0–57.2) | 0.54 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 541 of 541 | 0.00 | 2.95 / 3.45 |
| guard_parked_centre | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.63 / 1.64 / 1.67 | 1.56 | 0 of 0 | n/a | 3.40 / 3.40 |
| guard_parked_centre | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.67 / 1.67 / 1.70 | 1.55 | 0 of 0 | n/a | 3.60 / 3.60 |
| guard_parked_ring | strike_straight | 1000 | 42.1 % (39.1–45.2) | 57.9 % (54.8–60.9) | 0.0 % (0.0–0.4) | 42.1 % (39.1–45.2) | 0.42 (1) | 0 | 0 | 1.60 / 1.60 / 1.81 | 1.60 | 421 of 421 | 0.00 | 2.90 / 2.90 |
| guard_parked_ring | strike_flank | 1000 | 49.2 % (46.1–52.3) | 50.8 % (47.7–53.9) | 0.0 % (0.0–0.4) | 49.2 % (46.1–52.3) | 0.49 (1) | 0 | 0 | 1.60 / 1.60 / 1.81 | 1.60 | 492 of 492 | 0.00 | 2.90 / 2.90 |
| guard_parked_ring | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 39.7 % (36.7–42.8) | 60.3 % (57.2–63.3) | 0.0 % (0.0–0.4) | 39.7 % (36.7–42.8) | 0.40 (1) | 0 | 0 | 1.60 / 1.60 / 1.88 | 1.52 | 397 of 397 | 0.00 | 3.40 / 3.40 |
| guard_parked_ring | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 38.2 % (35.2–41.3) | 61.8 % (58.7–64.8) | 0.0 % (0.0–0.4) | 38.2 % (35.2–41.3) | 0.38 (1) | 0 | 0 | 1.60 / 1.60 / 1.91 | 1.48 | 382 of 382 | 0.00 | 3.60 / 3.60 |
| guard_mark_edge | strike_straight | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 1000 of 1000 | 0.00 | 2.10 / 2.55 |
| guard_mark_edge | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 1000 of 1000 | 0.00 | 2.20 / 2.60 |
| guard_mark_edge | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.52 | 1000 of 1000 | 0.00 | 2.40 / 2.90 |
| guard_mark_edge | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.48 | 1000 of 1000 | 0.00 | 2.55 / 3.05 |
| guard_mirror | strike_straight | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 1000 of 1000 | 0.00 | 2.10 / 2.55 |
| guard_mirror | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 1000 of 1000 | 0.00 | 2.30 / 2.60 |
| guard_mirror | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.52 | 1000 of 1000 | 0.00 | 2.40 / 2.90 |
| guard_mirror | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.48 | 1000 of 1000 | 0.00 | 2.55 / 3.05 |
| guard_field | strike_straight | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 1000 of 1000 | 0.00 | 2.10 / 2.55 |
| guard_field | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 1000 of 1000 | 0.00 | 2.20 / 2.60 |
| guard_field | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.52 | 1000 of 1000 | 0.00 | 2.40 / 2.90 |
| guard_field | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.48 | 1000 of 1000 | 0.00 | 2.55 / 3.05 |

## size_2v1: team size, 2v1 (2v1, game `base`)

Not played (with one Strike drone they fly as strike_straight): guard_parked_centre v strike_sacrifice, guard_parked_centre v strike_converge, guard_parked_ring v strike_sacrifice, guard_parked_ring v strike_converge, guard_mark_edge v strike_sacrifice, guard_mark_edge v strike_converge, guard_mirror v strike_sacrifice, guard_mirror v strike_converge, guard_field v strike_sacrifice, guard_field v strike_converge.

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| parked (holds starts; = still at 2+ Guards) | strike_straight | 1000 | 87.2 % (85.0–89.1) | 12.8 % (10.9–15.0) | 0.0 % (0.0–0.4) | 87.2 % (85.0–89.1) | 0.87 (1) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 0 of 872 | 1.00 | 2.25 / 2.90 |
| parked (holds starts; = still at 2+ Guards) | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 0 of 1000 | 1.00 | 2.40 / 3.15 |
| parked (holds starts; = still at 2+ Guards) | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 80.8 % (78.2–83.1) | 19.2 % (16.9–21.8) | 0.0 % (0.0–0.4) | 80.8 % (78.2–83.1) | 0.81 (1) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 0 of 808 | 1.00 | 2.80 / 3.40 |
| parked (holds starts; = still at 2+ Guards) | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 78.4 % (75.7–80.8) | 21.6 % (19.2–24.3) | 0.0 % (0.0–0.4) | 78.4 % (75.7–80.8) | 0.78 (1) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 0 of 784 | 1.00 | 3.05 / 3.60 |
| guard_parked_ring | strike_straight | 1000 | 85.4 % (83.1–87.5) | 14.6 % (12.5–16.9) | 0.0 % (0.0–0.4) | 85.4 % (83.1–87.5) | 0.85 (1) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 0 of 854 | 1.00 | 2.15 / 2.90 |
| guard_parked_ring | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 0 of 1000 | 1.00 | 2.30 / 3.15 |
| guard_parked_ring | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 79.7 % (77.1–82.1) | 20.3 % (17.9–22.9) | 0.0 % (0.0–0.4) | 79.7 % (77.1–82.1) | 0.80 (1) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 0 of 797 | 1.00 | 2.70 / 3.40 |
| guard_parked_ring | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 76.8 % (74.1–79.3) | 23.2 % (20.7–25.9) | 0.0 % (0.0–0.4) | 76.8 % (74.1–79.3) | 0.77 (1) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 0 of 768 | 1.00 | 2.95 / 3.60 |
| guard_mark_edge | strike_straight | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 0 of 1000 | 1.00 | 1.55 / 2.10 |
| guard_mark_edge | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 0 of 1000 | 1.00 | 1.65 / 2.15 |
| guard_mark_edge | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.52 | 0 of 1000 | 1.00 | 1.90 / 2.40 |
| guard_mark_edge | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.48 | 0 of 1000 | 1.00 | 2.05 / 2.55 |
| guard_mirror | strike_straight | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 0 of 1000 | 1.00 | 1.55 / 2.05 |
| guard_mirror | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 0 of 1000 | 1.00 | 1.70 / 2.35 |
| guard_mirror | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.52 | 0 of 1000 | 1.00 | 1.90 / 2.40 |
| guard_mirror | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.48 | 0 of 1000 | 1.00 | 2.05 / 2.55 |
| guard_field | strike_straight | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 0 of 1000 | 1.00 | 1.55 / 2.10 |
| guard_field | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 0 of 1000 | 1.00 | 1.65 / 2.15 |
| guard_field | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.52 | 0 of 1000 | 1.00 | 1.90 / 2.40 |
| guard_field | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.48 | 0 of 1000 | 1.00 | 2.05 / 2.55 |

## size_5v3: team size, 5v3 (5v3, game `base`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| parked (holds starts; = still at 2+ Guards) | strike_straight | 1000 | 93.5 % (91.8–94.9) | 6.5 % (5.1–8.2) | 0.0 % (0.0–0.4) | 93.5 % (91.8–94.9) | 2.94 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 0 of 935 | 2.00 | 1.55 / 2.16 |
| parked (holds starts; = still at 2+ Guards) | strike_flank | 1000 | 94.7 % (93.1–95.9) | 5.3 % (4.1–6.9) | 0.0 % (0.0–0.4) | 94.7 % (93.1–95.9) | 2.95 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 0 of 947 | 2.00 | 1.65 / 2.90 |
| parked (holds starts; = still at 2+ Guards) | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 93.5 % (91.8–94.9) | 6.5 % (5.1–8.2) | 0.0 % (0.0–0.4) | 93.5 % (91.8–94.9) | 2.94 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 0 of 935 | 2.00 | 2.10 / 2.75 |
| parked (holds starts; = still at 2+ Guards) | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 93.5 % (91.8–94.9) | 6.5 % (5.1–8.2) | 0.0 % (0.0–0.4) | 93.5 % (91.8–94.9) | 2.94 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.48 | 0 of 935 | 2.00 | 2.40 / 3.05 |
| parked (holds starts; = still at 2+ Guards) | strike_sacrifice | 1000 | 95.5 % (94.0–96.6) | 4.5 % (3.4–6.0) | 0.0 % (0.0–0.4) | 95.5 % (94.0–96.6) | 2.96 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 0 of 955 | 2.00 | 2.40 / 3.51 |
| parked (holds starts; = still at 2+ Guards) | strike_converge | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 0 of 1000 | 2.00 | 9.75 / 15.90 |
| guard_parked_ring | strike_straight | 1000 | 93.5 % (91.8–94.9) | 6.5 % (5.1–8.2) | 0.0 % (0.0–0.4) | 93.5 % (91.8–94.9) | 2.94 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 0 of 935 | 2.00 | 1.55 / 2.16 |
| guard_parked_ring | strike_flank | 1000 | 94.7 % (93.1–95.9) | 5.3 % (4.1–6.9) | 0.0 % (0.0–0.4) | 94.7 % (93.1–95.9) | 2.95 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 0 of 947 | 2.00 | 1.65 / 2.90 |
| guard_parked_ring | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 93.5 % (91.8–94.9) | 6.5 % (5.1–8.2) | 0.0 % (0.0–0.4) | 93.5 % (91.8–94.9) | 2.94 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 0 of 935 | 2.00 | 2.10 / 2.75 |
| guard_parked_ring | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 93.5 % (91.8–94.9) | 6.5 % (5.1–8.2) | 0.0 % (0.0–0.4) | 93.5 % (91.8–94.9) | 2.94 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.48 | 0 of 935 | 2.00 | 2.40 / 3.05 |
| guard_parked_ring | strike_sacrifice | 1000 | 95.5 % (94.0–96.6) | 4.5 % (3.4–6.0) | 0.0 % (0.0–0.4) | 95.5 % (94.0–96.6) | 2.96 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 0 of 955 | 2.00 | 2.40 / 3.51 |
| guard_parked_ring | strike_converge | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 0 of 1000 | 2.00 | 9.75 / 15.90 |
| guard_mark_edge | strike_straight | 1000 | 99.8 % (99.3–99.9) | 0.2 % (0.1–0.7) | 0.0 % (0.0–0.4) | 99.8 % (99.3–99.9) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 0 of 998 | 2.00 | 1.40 / 1.85 |
| guard_mark_edge | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 0 of 1000 | 2.00 | 1.60 / 2.25 |
| guard_mark_edge | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 99.8 % (99.3–99.9) | 0.2 % (0.1–0.7) | 0.0 % (0.0–0.4) | 99.8 % (99.3–99.9) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 0 of 998 | 2.00 | 1.95 / 2.50 |
| guard_mark_edge | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 99.8 % (99.3–99.9) | 0.2 % (0.1–0.7) | 0.0 % (0.0–0.4) | 99.8 % (99.3–99.9) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 0 of 998 | 2.00 | 2.20 / 2.90 |
| guard_mark_edge | strike_sacrifice | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 0 of 1000 | 2.00 | 1.90 / 2.80 |
| guard_mark_edge | strike_converge | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 0 of 1000 | 2.00 | 2.65 / 4.91 |
| guard_mirror | strike_straight | 1000 | 99.9 % (99.4–100.0) | 0.1 % (0.0–0.6) | 0.0 % (0.0–0.4) | 99.9 % (99.4–100.0) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 0 of 999 | 2.00 | 1.40 / 1.85 |
| guard_mirror | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 0 of 1000 | 2.00 | 1.65 / 2.30 |
| guard_mirror | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 99.9 % (99.4–100.0) | 0.1 % (0.0–0.6) | 0.0 % (0.0–0.4) | 99.9 % (99.4–100.0) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 0 of 999 | 2.00 | 1.90 / 2.50 |
| guard_mirror | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 99.8 % (99.3–99.9) | 0.2 % (0.1–0.7) | 0.0 % (0.0–0.4) | 99.8 % (99.3–99.9) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 0 of 998 | 2.00 | 2.20 / 2.90 |
| guard_mirror | strike_sacrifice | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 0 of 1000 | 2.00 | 2.00 / 2.90 |
| guard_mirror | strike_converge | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 0 of 1000 | 2.00 | 2.90 / 5.31 |
| guard_field | strike_straight | 1000 | 99.6 % (99.0–99.8) | 0.4 % (0.2–1.0) | 0.0 % (0.0–0.4) | 99.6 % (99.0–99.8) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 0 of 996 | 2.00 | 1.10 / 1.50 |
| guard_field | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 0 of 1000 | 2.00 | 1.15 / 1.75 |
| guard_field | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 99.6 % (99.0–99.8) | 0.4 % (0.2–1.0) | 0.0 % (0.0–0.4) | 99.6 % (99.0–99.8) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 0 of 996 | 2.00 | 1.50 / 1.85 |
| guard_field | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 99.6 % (99.0–99.8) | 0.4 % (0.2–1.0) | 0.0 % (0.0–0.4) | 99.6 % (99.0–99.8) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 0 of 996 | 2.00 | 1.65 / 2.00 |
| guard_field | strike_sacrifice | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 0 of 1000 | 2.00 | 1.30 / 1.95 |
| guard_field | strike_converge | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 0 of 1000 | 2.00 | 1.50 / 1.95 |

## survive_1: guard survives a tag, probability 1 (3v3, game `survive_1`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| parked (holds starts; = still at 2+ Guards) | strike_straight | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.58 / 1.60 / 1.60 | 1.58 | 0 of 1000 | 3.00 | 2.25 / 2.50 |
| parked (holds starts; = still at 2+ Guards) | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.58 / 1.60 / 1.60 | 1.58 | 0 of 1000 | 3.00 | 2.40 / 2.65 |
| parked (holds starts; = still at 2+ Guards) | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.58 / 1.60 / 1.60 | 1.50 | 0 of 1000 | 3.00 | 2.80 / 3.05 |
| parked (holds starts; = still at 2+ Guards) | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.58 / 1.60 / 1.60 | 1.46 | 0 of 1000 | 3.00 | 3.10 / 3.35 |
| parked (holds starts; = still at 2+ Guards) | strike_sacrifice | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.58 / 1.60 / 1.60 | 1.58 | 0 of 1000 | 3.00 | 3.80 / 4.31 |
| parked (holds starts; = still at 2+ Guards) | strike_converge | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.58 / 1.60 / 1.60 | 1.58 | 0 of 1000 | 3.00 | 8.10 / 13.21 |
| guard_parked_ring | strike_straight | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.58 / 1.60 / 1.60 | 1.58 | 0 of 1000 | 3.00 | 2.20 / 2.45 |
| guard_parked_ring | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.58 / 1.60 / 1.60 | 1.58 | 0 of 1000 | 3.00 | 2.35 / 2.55 |
| guard_parked_ring | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.58 / 1.60 / 1.60 | 1.50 | 0 of 1000 | 3.00 | 2.75 / 3.05 |
| guard_parked_ring | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.59 / 1.60 / 1.60 | 1.47 | 0 of 1000 | 3.00 | 3.05 / 3.35 |
| guard_parked_ring | strike_sacrifice | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.58 / 1.60 / 1.60 | 1.58 | 0 of 1000 | 3.00 | 3.60 / 4.20 |
| guard_parked_ring | strike_converge | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.58 / 1.60 / 1.60 | 1.58 | 0 of 1000 | 3.00 | 8.00 / 13.05 |
| guard_mark_edge | strike_straight | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.58 / 1.60 / 1.61 | 1.58 | 0 of 1000 | 3.00 | 2.00 / 2.35 |
| guard_mark_edge | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.58 / 1.60 / 1.60 | 1.58 | 0 of 1000 | 3.00 | 2.25 / 2.75 |
| guard_mark_edge | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.58 / 1.60 / 1.61 | 1.50 | 0 of 1000 | 3.00 | 2.50 / 2.90 |
| guard_mark_edge | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.58 / 1.60 / 1.61 | 1.46 | 0 of 1000 | 3.00 | 2.70 / 3.20 |
| guard_mark_edge | strike_sacrifice | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.58 / 1.60 / 1.61 | 1.58 | 0 of 1000 | 3.00 | 2.95 / 3.75 |
| guard_mark_edge | strike_converge | 1000 | 99.9 % (99.4–100.0) | 0.1 % (0.0–0.6) | 0.0 % (0.0–0.4) | 99.9 % (99.4–100.0) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 0 of 999 | 3.00 | 4.70 / 9.50 |
| guard_mirror | strike_straight | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.58 / 1.60 / 1.61 | 1.58 | 0 of 1000 | 3.00 | 2.00 / 2.35 |
| guard_mirror | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.58 / 1.60 / 1.60 | 1.58 | 0 of 1000 | 3.00 | 2.25 / 2.85 |
| guard_mirror | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.57 / 1.60 / 1.61 | 1.49 | 0 of 1000 | 3.00 | 2.48 / 2.90 |
| guard_mirror | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.59 / 1.60 / 1.61 | 1.47 | 0 of 1000 | 3.00 | 2.70 / 3.20 |
| guard_mirror | strike_sacrifice | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.58 / 1.60 / 1.61 | 1.58 | 0 of 1000 | 3.00 | 3.15 / 3.90 |
| guard_mirror | strike_converge | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 0 of 1000 | 3.00 | 5.25 / 10.36 |
| guard_field | strike_straight | 1000 | 99.7 % (99.1–99.9) | 0.3 % (0.1–0.9) | 0.0 % (0.0–0.4) | 99.7 % (99.1–99.9) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 0 of 997 | 3.00 | 1.70 / 2.05 |
| guard_field | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 0 of 1000 | 3.00 | 1.75 / 2.25 |
| guard_field | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 98.8 % (97.9–99.3) | 1.2 % (0.7–2.1) | 0.0 % (0.0–0.4) | 98.8 % (97.9–99.3) | 2.99 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 0 of 988 | 3.00 | 2.10 / 2.56 |
| guard_field | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 97.9 % (96.8–98.6) | 2.1 % (1.4–3.2) | 0.0 % (0.0–0.4) | 97.9 % (96.8–98.6) | 2.98 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 0 of 979 | 3.00 | 2.25 / 2.85 |
| guard_field | strike_sacrifice | 1000 | 99.3 % (98.6–99.7) | 0.7 % (0.3–1.4) | 0.0 % (0.0–0.4) | 99.3 % (98.6–99.7) | 2.99 (3) | 0 | 0 | 1.58 / 1.60 / 1.61 | 1.58 | 0 of 993 | 3.00 | 2.10 / 2.85 |
| guard_field | strike_converge | 1000 | 99.2 % (98.4–99.6) | 0.8 % (0.4–1.6) | 0.0 % (0.0–0.4) | 99.2 % (98.4–99.6) | 2.99 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 0 of 992 | 3.00 | 2.60 / 3.95 |

## tag_1p2: tag radius, 1.2 m (3v3, game `tag_1p2`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| parked (holds starts; = still at 2+ Guards) | strike_straight | 1000 | 14.4 % (12.4–16.7) | 85.6 % (83.3–87.6) | 0.0 % (0.0–0.4) | 14.4 % (12.4–16.7) | 1.91 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.20 | 144 of 144 | 0.00 | 2.90 / 3.05 |
| parked (holds starts; = still at 2+ Guards) | strike_flank | 1000 | 33.1 % (30.3–36.1) | 66.9 % (63.9–69.7) | 0.0 % (0.0–0.4) | 33.1 % (30.3–36.1) | 2.30 (3) | 0 | 0 | 1.20 / 1.20 / 1.20 | 1.20 | 331 of 331 | 0.00 | 4.00 / 4.50 |
| parked (holds starts; = still at 2+ Guards) | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 7.1 % (5.7–8.9) | 92.9 % (91.1–94.3) | 0.0 % (0.0–0.4) | 7.1 % (5.7–8.9) | 1.63 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.09 | 71 of 71 | 0.00 | 3.40 / 3.45 |
| parked (holds starts; = still at 2+ Guards) | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 4.3 % (3.2–5.7) | 95.7 % (94.3–96.8) | 0.0 % (0.0–0.4) | 4.3 % (3.2–5.7) | 1.43 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.04 | 43 of 43 | 0.00 | 3.60 / 3.65 |
| parked (holds starts; = still at 2+ Guards) | strike_sacrifice | 1000 | 34.0 % (31.1–37.0) | 66.0 % (63.0–68.9) | 0.0 % (0.0–0.4) | 34.0 % (31.1–37.0) | 2.05 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.20 | 340 of 340 | 0.00 | 5.35 / 5.85 |
| parked (holds starts; = still at 2+ Guards) | strike_converge | 1000 | 73.0 % (70.2–75.7) | 27.0 % (24.3–29.8) | 0.0 % (0.0–0.4) | 73.0 % (70.2–75.7) | 2.26 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.20 | 730 of 730 | 0.00 | 8.90 / 13.91 |
| guard_parked_ring | strike_straight | 1000 | 16.8 % (14.6–19.2) | 83.2 % (80.8–85.4) | 0.0 % (0.0–0.4) | 16.8 % (14.6–19.2) | 1.96 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.20 | 168 of 168 | 0.00 | 2.90 / 3.00 |
| guard_parked_ring | strike_flank | 1000 | 33.1 % (30.3–36.1) | 66.9 % (63.9–69.7) | 0.0 % (0.0–0.4) | 33.1 % (30.3–36.1) | 2.30 (3) | 0 | 0 | 1.20 / 1.20 / 1.20 | 1.20 | 331 of 331 | 0.00 | 4.00 / 4.40 |
| guard_parked_ring | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 8.8 % (7.2–10.7) | 91.2 % (89.3–92.8) | 0.0 % (0.0–0.4) | 8.8 % (7.2–10.7) | 1.73 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.09 | 88 of 88 | 0.00 | 3.40 / 3.45 |
| guard_parked_ring | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 6.1 % (4.8–7.8) | 93.9 % (92.2–95.2) | 0.0 % (0.0–0.4) | 6.1 % (4.8–7.8) | 1.57 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.04 | 61 of 61 | 0.00 | 3.60 / 3.65 |
| guard_parked_ring | strike_sacrifice | 1000 | 36.3 % (33.4–39.3) | 63.7 % (60.7–66.6) | 0.0 % (0.0–0.4) | 36.3 % (33.4–39.3) | 2.17 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.20 | 363 of 363 | 0.00 | 5.25 / 5.85 |
| guard_parked_ring | strike_converge | 1000 | 75.0 % (72.2–77.6) | 25.0 % (22.4–27.8) | 0.0 % (0.0–0.4) | 75.0 % (72.2–77.6) | 2.34 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.20 | 750 of 750 | 0.00 | 8.85 / 13.86 |
| guard_mark_edge | strike_straight | 1000 | 47.4 % (44.3–50.5) | 52.6 % (49.5–55.7) | 0.0 % (0.0–0.4) | 47.4 % (44.3–50.5) | 2.34 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.20 | 474 of 474 | 0.00 | 2.90 / 3.00 |
| guard_mark_edge | strike_flank | 1000 | 65.9 % (62.9–68.8) | 34.1 % (31.2–37.1) | 0.0 % (0.0–0.4) | 65.9 % (62.9–68.8) | 2.50 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.20 | 659 of 659 | 0.00 | 3.80 / 4.20 |
| guard_mark_edge | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 43.9 % (40.9–47.0) | 56.1 % (53.0–59.1) | 0.0 % (0.0–0.4) | 43.9 % (40.9–47.0) | 2.22 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.06 | 439 of 439 | 0.00 | 3.40 / 3.45 |
| guard_mark_edge | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 43.5 % (40.5–46.6) | 56.5 % (53.4–59.5) | 0.0 % (0.0–0.4) | 43.5 % (40.5–46.6) | 2.16 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.00 | 435 of 435 | 0.00 | 3.60 / 3.60 |
| guard_mark_edge | strike_sacrifice | 1000 | 69.5 % (66.6–72.3) | 30.5 % (27.7–33.4) | 0.0 % (0.0–0.4) | 69.5 % (66.6–72.3) | 2.48 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.20 | 695 of 695 | 0.00 | 4.47 / 5.50 |
| guard_mark_edge | strike_converge | 1000 | 81.5 % (79.0–83.8) | 18.5 % (16.2–21.0) | 0.0 % (0.0–0.4) | 81.5 % (79.0–83.8) | 2.71 (3) | 0 | 0 | 1.20 / 1.20 / 1.20 | 1.20 | 815 of 815 | 0.00 | 7.28 / 13.30 |
| guard_mirror | strike_straight | 1000 | 49.4 % (46.3–52.5) | 50.6 % (47.5–53.7) | 0.0 % (0.0–0.4) | 49.4 % (46.3–52.5) | 2.37 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.20 | 494 of 494 | 0.00 | 2.90 / 3.01 |
| guard_mirror | strike_flank | 1000 | 57.9 % (54.8–60.9) | 42.1 % (39.1–45.2) | 0.0 % (0.0–0.4) | 57.9 % (54.8–60.9) | 2.39 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.20 | 579 of 579 | 0.00 | 3.75 / 4.15 |
| guard_mirror | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 44.7 % (41.6–47.8) | 55.3 % (52.2–58.4) | 0.0 % (0.0–0.4) | 44.7 % (41.6–47.8) | 2.24 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.07 | 447 of 447 | 0.00 | 3.40 / 3.45 |
| guard_mirror | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 43.7 % (40.7–46.8) | 56.3 % (53.2–59.3) | 0.0 % (0.0–0.4) | 43.7 % (40.7–46.8) | 2.18 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.00 | 437 of 437 | 0.00 | 3.60 / 3.60 |
| guard_mirror | strike_sacrifice | 1000 | 53.7 % (50.6–56.8) | 46.3 % (43.2–49.4) | 0.0 % (0.0–0.4) | 53.7 % (50.6–56.8) | 2.17 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.20 | 537 of 537 | 0.00 | 4.50 / 5.50 |
| guard_mirror | strike_converge | 1000 | 77.3 % (74.6–79.8) | 22.7 % (20.2–25.4) | 0.0 % (0.0–0.4) | 77.3 % (74.6–79.8) | 2.72 (3) | 0 | 0 | 1.20 / 1.20 / 1.20 | 1.20 | 773 of 773 | 0.00 | 7.33 / 12.80 |
| guard_field | strike_straight | 1000 | 64.5 % (61.5–67.4) | 35.5 % (32.6–38.5) | 0.0 % (0.0–0.4) | 64.5 % (61.5–67.4) | 2.65 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.20 | 645 of 645 | 0.00 | 2.45 / 2.90 |
| guard_field | strike_flank | 1000 | 76.3 % (73.6–78.8) | 23.7 % (21.2–26.4) | 0.0 % (0.0–0.4) | 76.3 % (73.6–78.8) | 2.76 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.20 | 763 of 763 | 0.00 | 3.15 / 3.80 |
| guard_field | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 64.5 % (61.5–67.4) | 35.5 % (32.6–38.5) | 0.0 % (0.0–0.4) | 64.5 % (61.5–67.4) | 2.65 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.09 | 645 of 645 | 0.00 | 2.85 / 3.40 |
| guard_field | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 64.5 % (61.5–67.4) | 35.5 % (32.6–38.5) | 0.0 % (0.0–0.4) | 64.5 % (61.5–67.4) | 2.65 (3) | 0 | 0 | 1.20 / 1.20 / 1.21 | 1.03 | 645 of 645 | 0.00 | 3.00 / 3.60 |
| guard_field | strike_sacrifice | 1000 | 72.5 % (69.7–75.2) | 27.5 % (24.8–30.3) | 0.0 % (0.0–0.4) | 72.5 % (69.7–75.2) | 2.68 (3) | 0 | 0 | 1.20 / 1.20 / 1.20 | 1.20 | 725 of 725 | 0.00 | 3.30 / 4.85 |
| guard_field | strike_converge | 1000 | 76.6 % (73.9–79.1) | 23.4 % (20.9–26.1) | 0.0 % (0.0–0.4) | 76.6 % (73.9–79.1) | 2.77 (3) | 0 | 0 | 1.20 / 1.20 / 1.20 | 1.20 | 766 of 766 | 0.00 | 4.15 / 8.11 |

## tag_1p4: tag radius, 1.4 m (3v3, game `tag_1p4`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| parked (holds starts; = still at 2+ Guards) | strike_straight | 1000 | 34.5 % (31.6–37.5) | 65.5 % (62.5–68.4) | 0.0 % (0.0–0.4) | 34.5 % (31.6–37.5) | 2.32 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.40 | 345 of 345 | 0.00 | 2.90 / 3.00 |
| parked (holds starts; = still at 2+ Guards) | strike_flank | 1000 | 33.1 % (30.3–36.1) | 66.9 % (63.9–69.7) | 0.0 % (0.0–0.4) | 33.1 % (30.3–36.1) | 2.30 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.40 | 331 of 331 | 0.00 | 3.75 / 4.05 |
| parked (holds starts; = still at 2+ Guards) | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 26.5 % (23.9–29.3) | 73.5 % (70.7–76.1) | 0.0 % (0.0–0.4) | 26.5 % (23.9–29.3) | 2.17 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.31 | 265 of 265 | 0.00 | 3.40 / 3.45 |
| parked (holds starts; = still at 2+ Guards) | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 22.4 % (19.9–25.1) | 77.6 % (74.9–80.1) | 0.0 % (0.0–0.4) | 22.4 % (19.9–25.1) | 2.09 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.26 | 224 of 224 | 0.00 | 3.60 / 3.65 |
| parked (holds starts; = still at 2+ Guards) | strike_sacrifice | 1000 | 47.0 % (43.9–50.1) | 53.0 % (49.9–56.1) | 0.0 % (0.0–0.4) | 47.0 % (43.9–50.1) | 2.46 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.40 | 470 of 470 | 0.00 | 4.95 / 5.55 |
| parked (holds starts; = still at 2+ Guards) | strike_converge | 1000 | 98.1 % (97.1–98.8) | 1.9 % (1.2–2.9) | 0.0 % (0.0–0.4) | 98.1 % (97.1–98.8) | 2.98 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.40 | 981 of 981 | 0.00 | 8.55 / 13.61 |
| guard_parked_ring | strike_straight | 1000 | 34.5 % (31.6–37.5) | 65.5 % (62.5–68.4) | 0.0 % (0.0–0.4) | 34.5 % (31.6–37.5) | 2.32 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.40 | 345 of 345 | 0.00 | 2.90 / 3.00 |
| guard_parked_ring | strike_flank | 1000 | 33.1 % (30.3–36.1) | 66.9 % (63.9–69.7) | 0.0 % (0.0–0.4) | 33.1 % (30.3–36.1) | 2.30 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.40 | 331 of 331 | 0.00 | 3.75 / 4.05 |
| guard_parked_ring | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 27.5 % (24.8–30.3) | 72.5 % (69.7–75.2) | 0.0 % (0.0–0.4) | 27.5 % (24.8–30.3) | 2.19 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.31 | 275 of 275 | 0.00 | 3.40 / 3.45 |
| guard_parked_ring | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 23.8 % (21.3–26.5) | 76.2 % (73.5–78.7) | 0.0 % (0.0–0.4) | 23.8 % (21.3–26.5) | 2.12 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.26 | 238 of 238 | 0.00 | 3.60 / 3.65 |
| guard_parked_ring | strike_sacrifice | 1000 | 46.5 % (43.4–49.6) | 53.5 % (50.4–56.6) | 0.0 % (0.0–0.4) | 46.5 % (43.4–49.6) | 2.46 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.40 | 465 of 465 | 0.00 | 4.80 / 5.50 |
| guard_parked_ring | strike_converge | 1000 | 98.1 % (97.1–98.8) | 1.9 % (1.2–2.9) | 0.0 % (0.0–0.4) | 98.1 % (97.1–98.8) | 2.98 (3) | 0 | 0 | 1.40 / 1.40 / 1.40 | 1.40 | 981 of 981 | 0.00 | 8.50 / 13.50 |
| guard_mark_edge | strike_straight | 1000 | 70.1 % (67.2–72.9) | 29.9 % (27.1–32.8) | 0.0 % (0.0–0.4) | 70.1 % (67.2–72.9) | 2.67 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.40 | 701 of 701 | 0.00 | 2.70 / 2.90 |
| guard_mark_edge | strike_flank | 1000 | 80.6 % (78.0–82.9) | 19.4 % (17.1–22.0) | 0.0 % (0.0–0.4) | 80.6 % (78.0–82.9) | 2.79 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.40 | 806 of 806 | 0.00 | 3.35 / 3.85 |
| guard_mark_edge | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 68.5 % (65.6–71.3) | 31.5 % (28.7–34.4) | 0.0 % (0.0–0.4) | 68.5 % (65.6–71.3) | 2.64 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.31 | 685 of 685 | 0.00 | 3.15 / 3.40 |
| guard_mark_edge | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 66.5 % (63.5–69.4) | 33.5 % (30.6–36.5) | 0.0 % (0.0–0.4) | 66.5 % (63.5–69.4) | 2.60 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.26 | 665 of 665 | 0.00 | 3.40 / 3.60 |
| guard_mark_edge | strike_sacrifice | 1000 | 87.6 % (85.4–89.5) | 12.4 % (10.5–14.6) | 0.0 % (0.0–0.4) | 87.6 % (85.4–89.5) | 2.84 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.40 | 876 of 876 | 0.00 | 4.05 / 5.10 |
| guard_mark_edge | strike_converge | 1000 | 91.5 % (89.6–93.1) | 8.5 % (6.9–10.4) | 0.0 % (0.0–0.4) | 91.5 % (89.6–93.1) | 2.89 (3) | 0 | 0 | 1.40 / 1.40 / 1.40 | 1.40 | 915 of 915 | 0.00 | 5.80 / 11.90 |
| guard_mirror | strike_straight | 1000 | 69.5 % (66.6–72.3) | 30.5 % (27.7–33.4) | 0.0 % (0.0–0.4) | 69.5 % (66.6–72.3) | 2.67 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.40 | 695 of 695 | 0.00 | 2.68 / 2.90 |
| guard_mirror | strike_flank | 1000 | 74.1 % (71.3–76.7) | 25.9 % (23.3–28.7) | 0.0 % (0.0–0.4) | 74.1 % (71.3–76.7) | 2.72 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.40 | 741 of 741 | 0.00 | 3.45 / 3.85 |
| guard_mirror | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 67.7 % (64.7–70.5) | 32.3 % (29.5–35.3) | 0.0 % (0.0–0.4) | 67.7 % (64.7–70.5) | 2.63 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.31 | 677 of 677 | 0.00 | 3.15 / 3.40 |
| guard_mirror | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 67.2 % (64.2–70.0) | 32.8 % (30.0–35.8) | 0.0 % (0.0–0.4) | 67.2 % (64.2–70.0) | 2.61 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.26 | 672 of 672 | 0.00 | 3.40 / 3.60 |
| guard_mirror | strike_sacrifice | 1000 | 79.9 % (77.3–82.3) | 20.1 % (17.7–22.7) | 0.0 % (0.0–0.4) | 79.9 % (77.3–82.3) | 2.74 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.40 | 799 of 799 | 0.00 | 4.25 / 5.30 |
| guard_mirror | strike_converge | 1000 | 89.4 % (87.3–91.2) | 10.6 % (8.8–12.7) | 0.0 % (0.0–0.4) | 89.4 % (87.3–91.2) | 2.87 (3) | 0 | 0 | 1.40 / 1.40 / 1.40 | 1.40 | 894 of 894 | 0.00 | 6.50 / 12.15 |
| guard_field | strike_straight | 1000 | 65.0 % (62.0–67.9) | 35.0 % (32.1–38.0) | 0.0 % (0.0–0.4) | 65.0 % (62.0–67.9) | 2.65 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.40 | 650 of 650 | 0.00 | 2.25 / 2.90 |
| guard_field | strike_flank | 1000 | 77.4 % (74.7–79.9) | 22.6 % (20.1–25.3) | 0.0 % (0.0–0.4) | 77.4 % (74.7–79.9) | 2.77 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.40 | 774 of 774 | 0.00 | 2.75 / 3.50 |
| guard_field | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 65.6 % (62.6–68.5) | 34.4 % (31.5–37.4) | 0.0 % (0.0–0.4) | 65.6 % (62.6–68.5) | 2.66 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.31 | 656 of 656 | 0.00 | 2.55 / 3.40 |
| guard_field | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 66.1 % (63.1–69.0) | 33.9 % (31.0–36.9) | 0.0 % (0.0–0.4) | 66.1 % (63.1–69.0) | 2.66 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.26 | 661 of 661 | 0.00 | 2.70 / 3.60 |
| guard_field | strike_sacrifice | 1000 | 79.8 % (77.2–82.2) | 20.2 % (17.8–22.8) | 0.0 % (0.0–0.4) | 79.8 % (77.2–82.2) | 2.79 (3) | 0 | 0 | 1.40 / 1.40 / 1.41 | 1.40 | 798 of 798 | 0.00 | 2.85 / 4.50 |
| guard_field | strike_converge | 1000 | 81.7 % (79.2–84.0) | 18.3 % (16.0–20.8) | 0.0 % (0.0–0.4) | 81.7 % (79.2–84.0) | 2.82 (3) | 0 | 0 | 1.40 / 1.40 / 1.40 | 1.40 | 817 of 817 | 0.00 | 3.30 / 5.75 |

## tag_1p8: tag radius, 1.8 m (3v3, game `tag_1p8`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| parked (holds starts; = still at 2+ Guards) | strike_straight | 1000 | 66.3 % (63.3–69.2) | 33.7 % (30.8–36.7) | 0.0 % (0.0–0.4) | 66.3 % (63.3–69.2) | 2.66 (3) | 0 | 0 | 1.80 / 1.80 / 1.80 | 1.80 | 663 of 663 | 0.00 | 2.50 / 2.90 |
| parked (holds starts; = still at 2+ Guards) | strike_flank | 1000 | 60.1 % (57.0–63.1) | 39.9 % (36.9–43.0) | 0.0 % (0.0–0.4) | 60.1 % (57.0–63.1) | 2.60 (3) | 0 | 0 | 1.80 / 1.80 / 1.80 | 1.80 | 601 of 601 | 0.00 | 3.20 / 3.40 |
| parked (holds starts; = still at 2+ Guards) | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 62.7 % (59.7–65.6) | 37.3 % (34.4–40.3) | 0.0 % (0.0–0.4) | 62.7 % (59.7–65.6) | 2.63 (3) | 0 | 0 | 1.80 / 1.80 / 1.81 | 1.73 | 627 of 627 | 0.00 | 3.05 / 3.40 |
| parked (holds starts; = still at 2+ Guards) | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 60.9 % (57.8–63.9) | 39.1 % (36.1–42.2) | 0.0 % (0.0–0.4) | 60.9 % (57.8–63.9) | 2.61 (3) | 0 | 0 | 1.80 / 1.80 / 1.81 | 1.70 | 609 of 609 | 0.00 | 3.30 / 3.60 |
| parked (holds starts; = still at 2+ Guards) | strike_sacrifice | 1000 | 62.5 % (59.5–65.4) | 37.5 % (34.6–40.5) | 0.0 % (0.0–0.4) | 62.5 % (59.5–65.4) | 2.62 (3) | 0 | 0 | 1.80 / 1.80 / 1.80 | 1.80 | 625 of 625 | 0.00 | 3.80 / 4.70 |
| parked (holds starts; = still at 2+ Guards) | strike_converge | 1000 | 98.5 % (97.5–99.1) | 1.5 % (0.9–2.5) | 0.0 % (0.0–0.4) | 98.5 % (97.5–99.1) | 2.98 (3) | 0 | 0 | 1.80 / 1.80 / 1.80 | 1.80 | 985 of 985 | 0.00 | 7.65 / 13.25 |
| guard_parked_ring | strike_straight | 1000 | 64.9 % (61.9–67.8) | 35.1 % (32.2–38.1) | 0.0 % (0.0–0.4) | 64.9 % (61.9–67.8) | 2.65 (3) | 0 | 0 | 1.80 / 1.80 / 1.80 | 1.80 | 649 of 649 | 0.00 | 2.50 / 2.90 |
| guard_parked_ring | strike_flank | 1000 | 60.3 % (57.2–63.3) | 39.7 % (36.7–42.8) | 0.0 % (0.0–0.4) | 60.3 % (57.2–63.3) | 2.60 (3) | 0 | 0 | 1.80 / 1.80 / 1.80 | 1.80 | 603 of 603 | 0.00 | 3.20 / 3.40 |
| guard_parked_ring | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 61.2 % (58.1–64.2) | 38.8 % (35.8–41.9) | 0.0 % (0.0–0.4) | 61.2 % (58.1–64.2) | 2.61 (3) | 0 | 0 | 1.80 / 1.80 / 1.80 | 1.73 | 612 of 612 | 0.00 | 3.05 / 3.40 |
| guard_parked_ring | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 59.2 % (56.1–62.2) | 40.8 % (37.8–43.9) | 0.0 % (0.0–0.4) | 59.2 % (56.1–62.2) | 2.59 (3) | 0 | 0 | 1.80 / 1.80 / 1.81 | 1.70 | 592 of 592 | 0.00 | 3.35 / 3.60 |
| guard_parked_ring | strike_sacrifice | 1000 | 59.9 % (56.8–62.9) | 40.1 % (37.1–43.2) | 0.0 % (0.0–0.4) | 59.9 % (56.8–62.9) | 2.60 (3) | 0 | 0 | 1.80 / 1.80 / 1.80 | 1.80 | 599 of 599 | 0.00 | 3.75 / 4.65 |
| guard_parked_ring | strike_converge | 1000 | 95.3 % (93.8–96.4) | 4.7 % (3.6–6.2) | 0.0 % (0.0–0.4) | 95.3 % (93.8–96.4) | 2.95 (3) | 0 | 0 | 1.80 / 1.80 / 1.80 | 1.80 | 953 of 953 | 0.00 | 7.65 / 14.50 |
| guard_mark_edge | strike_straight | 1000 | 93.2 % (91.5–94.6) | 6.8 % (5.4–8.5) | 0.0 % (0.0–0.4) | 93.2 % (91.5–94.6) | 2.93 (3) | 0 | 0 | 1.80 / 1.80 / 1.81 | 1.80 | 932 of 932 | 0.00 | 2.10 / 2.85 |
| guard_mark_edge | strike_flank | 1000 | 96.7 % (95.4–97.6) | 3.3 % (2.4–4.6) | 0.0 % (0.0–0.4) | 96.7 % (95.4–97.6) | 2.97 (3) | 0 | 0 | 1.80 / 1.80 / 1.80 | 1.80 | 967 of 967 | 0.00 | 2.45 / 3.15 |
| guard_mark_edge | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 93.7 % (92.0–95.0) | 6.3 % (5.0–8.0) | 0.0 % (0.0–0.4) | 93.7 % (92.0–95.0) | 2.94 (3) | 0 | 0 | 1.80 / 1.80 / 1.81 | 1.73 | 937 of 937 | 0.00 | 2.50 / 3.30 |
| guard_mark_edge | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 95.3 % (93.8–96.4) | 4.7 % (3.6–6.2) | 0.0 % (0.0–0.4) | 95.3 % (93.8–96.4) | 2.95 (3) | 0 | 0 | 1.80 / 1.80 / 1.81 | 1.70 | 953 of 953 | 0.00 | 2.70 / 3.45 |
| guard_mark_edge | strike_sacrifice | 1000 | 99.6 % (99.0–99.8) | 0.4 % (0.2–1.0) | 0.0 % (0.0–0.4) | 99.6 % (99.0–99.8) | 3.00 (3) | 0 | 0 | 1.80 / 1.80 / 1.80 | 1.80 | 996 of 996 | 0.00 | 2.93 / 3.95 |
| guard_mark_edge | strike_converge | 1000 | 98.8 % (97.9–99.3) | 1.2 % (0.7–2.1) | 0.0 % (0.0–0.4) | 98.8 % (97.9–99.3) | 2.99 (3) | 0 | 0 | 1.80 / 1.80 / 1.80 | 1.80 | 988 of 988 | 0.00 | 4.25 / 7.55 |
| guard_mirror | strike_straight | 1000 | 93.2 % (91.5–94.6) | 6.8 % (5.4–8.5) | 0.0 % (0.0–0.4) | 93.2 % (91.5–94.6) | 2.93 (3) | 0 | 0 | 1.80 / 1.80 / 1.81 | 1.80 | 932 of 932 | 0.00 | 2.10 / 2.85 |
| guard_mirror | strike_flank | 1000 | 96.8 % (95.5–97.7) | 3.2 % (2.3–4.5) | 0.0 % (0.0–0.4) | 96.8 % (95.5–97.7) | 2.97 (3) | 0 | 0 | 1.80 / 1.80 / 1.80 | 1.80 | 968 of 968 | 0.00 | 2.50 / 3.16 |
| guard_mirror | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 93.8 % (92.1–95.1) | 6.2 % (4.9–7.9) | 0.0 % (0.0–0.4) | 93.8 % (92.1–95.1) | 2.94 (3) | 0 | 0 | 1.80 / 1.80 / 1.81 | 1.73 | 938 of 938 | 0.00 | 2.50 / 3.30 |
| guard_mirror | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 94.8 % (93.2–96.0) | 5.2 % (4.0–6.8) | 0.0 % (0.0–0.4) | 94.8 % (93.2–96.0) | 2.95 (3) | 0 | 0 | 1.80 / 1.80 / 1.81 | 1.70 | 948 of 948 | 0.00 | 2.70 / 3.45 |
| guard_mirror | strike_sacrifice | 1000 | 98.3 % (97.3–98.9) | 1.7 % (1.1–2.7) | 0.0 % (0.0–0.4) | 98.3 % (97.3–98.9) | 2.98 (3) | 0 | 0 | 1.80 / 1.80 / 1.80 | 1.80 | 983 of 983 | 0.00 | 3.05 / 4.20 |
| guard_mirror | strike_converge | 1000 | 98.7 % (97.8–99.2) | 1.3 % (0.8–2.2) | 0.0 % (0.0–0.4) | 98.7 % (97.8–99.2) | 2.99 (3) | 0 | 0 | 1.80 / 1.80 / 1.80 | 1.80 | 987 of 987 | 0.00 | 4.95 / 9.05 |
| guard_field | strike_straight | 1000 | 87.0 % (84.8–88.9) | 13.0 % (11.1–15.2) | 0.0 % (0.0–0.4) | 87.0 % (84.8–88.9) | 2.87 (3) | 0 | 0 | 1.80 / 1.80 / 1.81 | 1.80 | 870 of 870 | 0.00 | 1.75 / 2.90 |
| guard_field | strike_flank | 1000 | 89.7 % (87.7–91.4) | 10.3 % (8.6–12.3) | 0.0 % (0.0–0.4) | 89.7 % (87.7–91.4) | 2.90 (3) | 0 | 0 | 1.80 / 1.80 / 1.81 | 1.80 | 897 of 897 | 0.00 | 2.00 / 3.15 |
| guard_field | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 84.3 % (81.9–86.4) | 15.7 % (13.6–18.1) | 0.0 % (0.0–0.4) | 84.3 % (81.9–86.4) | 2.84 (3) | 0 | 0 | 1.80 / 1.80 / 1.81 | 1.73 | 843 of 843 | 0.00 | 2.05 / 3.40 |
| guard_field | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 83.1 % (80.7–85.3) | 16.9 % (14.7–19.3) | 0.0 % (0.0–0.4) | 83.1 % (80.7–85.3) | 2.83 (3) | 0 | 0 | 1.80 / 1.80 / 1.81 | 1.70 | 831 of 831 | 0.00 | 2.20 / 3.60 |
| guard_field | strike_sacrifice | 1000 | 94.2 % (92.6–95.5) | 5.8 % (4.5–7.4) | 0.0 % (0.0–0.4) | 94.2 % (92.6–95.5) | 2.94 (3) | 0 | 0 | 1.80 / 1.80 / 1.81 | 1.80 | 942 of 942 | 0.00 | 2.00 / 3.50 |
| guard_field | strike_converge | 1000 | 93.6 % (91.9–95.0) | 6.4 % (5.0–8.1) | 0.0 % (0.0–0.4) | 93.6 % (91.9–95.0) | 2.94 (3) | 0 | 0 | 1.80 / 1.80 / 1.80 | 1.80 | 936 of 936 | 0.00 | 2.28 / 4.30 |

## zone_2p4: zone radius, 2.4 m (PROPOSED); ring 2.75 m kept, run-in 0.35 m (3v3, game `zone_2p4`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| parked (holds starts; = still at 2+ Guards) | strike_straight | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.01 (1) | 0 | 0 | 1.60 / 1.62 / 1.70 | 1.60 | 0 of 0 | n/a | 1.40 / 1.40 |
| parked (holds starts; = still at 2+ Guards) | strike_flank | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.03 (2) | 0 | 0 | 1.60 / 1.61 / 1.68 | 1.60 | 0 of 0 | n/a | 1.65 / 1.70 |
| parked (holds starts; = still at 2+ Guards) | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.67 / 1.69 / 1.77 | 1.59 | 0 of 0 | n/a | 1.80 / 1.80 |
| parked (holds starts; = still at 2+ Guards) | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.70 / 1.72 / 1.80 | 1.59 | 0 of 0 | n/a | 2.00 / 2.00 |
| parked (holds starts; = still at 2+ Guards) | strike_sacrifice | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.01 (1) | 0 | 0 | 1.60 / 1.63 / 1.78 | 1.60 | 0 of 0 | n/a | 1.40 / 1.45 |
| parked (holds starts; = still at 2+ Guards) | strike_converge | 1000 | 0.9 % (0.5–1.7) | 99.1 % (98.3–99.5) | 0.0 % (0.0–0.4) | 0.9 % (0.5–1.7) | 0.03 (3) | 0 | 0 | 1.60 / 1.63 / 1.78 | 1.60 | 9 of 9 | 0.00 | 9.15 / 15.05 |
| guard_parked_ring | strike_straight | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.11 (2) | 0 | 0 | 1.60 / 1.60 / 1.63 | 1.60 | 0 of 0 | n/a | 1.40 / 1.40 |
| guard_parked_ring | strike_flank | 1000 | 0.1 % (0.0–0.6) | 99.9 % (99.4–100.0) | 0.0 % (0.0–0.4) | 0.1 % (0.0–0.6) | 0.32 (3) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 1 of 1 | 0.00 | 1.70 / 1.70 |
| guard_parked_ring | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.67 / 1.67 / 1.70 | 1.59 | 0 of 0 | n/a | 1.80 / 1.80 |
| guard_parked_ring | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.70 / 1.70 / 1.73 | 1.59 | 0 of 0 | n/a | 2.00 / 2.00 |
| guard_parked_ring | strike_sacrifice | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.05 (2) | 0 | 0 | 1.60 / 1.61 / 1.74 | 1.60 | 0 of 0 | n/a | 1.40 / 1.45 |
| guard_parked_ring | strike_converge | 1000 | 10.3 % (8.6–12.3) | 89.7 % (87.7–91.4) | 0.0 % (0.0–0.4) | 10.3 % (8.6–12.3) | 0.36 (3) | 0 | 0 | 1.60 / 1.60 / 1.73 | 1.60 | 103 of 103 | 0.00 | 9.15 / 15.05 |
| guard_mark_edge | strike_straight | 1000 | 3.8 % (2.8–5.2) | 96.2 % (94.8–97.2) | 0.0 % (0.0–0.4) | 3.8 % (2.8–5.2) | 0.77 (3) | 0 | 0 | 1.60 / 1.60 / 1.63 | 1.60 | 38 of 38 | 0.00 | 1.40 / 1.40 |
| guard_mark_edge | strike_flank | 1000 | 10.1 % (8.4–12.1) | 89.9 % (87.9–91.6) | 0.0 % (0.0–0.4) | 10.1 % (8.4–12.1) | 1.04 (3) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 101 of 101 | 0.00 | 1.65 / 1.75 |
| guard_mark_edge | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 4.9 % (3.7–6.4) | 95.1 % (93.6–96.3) | 0.0 % (0.0–0.4) | 4.9 % (3.7–6.4) | 0.81 (3) | 0 | 0 | 1.60 / 1.60 / 1.63 | 1.52 | 49 of 49 | 0.00 | 1.80 / 1.80 |
| guard_mark_edge | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 6.1 % (4.8–7.8) | 93.9 % (92.2–95.2) | 0.0 % (0.0–0.4) | 6.1 % (4.8–7.8) | 0.85 (3) | 0 | 0 | 1.60 / 1.60 / 1.63 | 1.48 | 61 of 61 | 0.00 | 2.00 / 2.00 |
| guard_mark_edge | strike_sacrifice | 1000 | 4.9 % (3.7–6.4) | 95.1 % (93.6–96.3) | 0.0 % (0.0–0.4) | 4.9 % (3.7–6.4) | 0.52 (3) | 0 | 0 | 1.60 / 1.60 / 1.73 | 1.60 | 49 of 49 | 0.00 | 1.43 / 3.00 |
| guard_mark_edge | strike_converge | 1000 | 67.0 % (64.0–69.8) | 33.0 % (30.2–36.0) | 0.0 % (0.0–0.4) | 67.0 % (64.0–69.8) | 2.41 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 670 of 670 | 0.00 | 6.00 / 12.90 |
| guard_mirror | strike_straight | 1000 | 3.8 % (2.8–5.2) | 96.2 % (94.8–97.2) | 0.0 % (0.0–0.4) | 3.8 % (2.8–5.2) | 0.78 (3) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 38 of 38 | 0.00 | 1.40 / 1.40 |
| guard_mirror | strike_flank | 1000 | 7.1 % (5.7–8.9) | 92.9 % (91.1–94.3) | 0.0 % (0.0–0.4) | 7.1 % (5.7–8.9) | 0.97 (3) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 71 of 71 | 0.00 | 1.65 / 1.75 |
| guard_mirror | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 4.9 % (3.7–6.4) | 95.1 % (93.6–96.3) | 0.0 % (0.0–0.4) | 4.9 % (3.7–6.4) | 0.82 (3) | 0 | 0 | 1.60 / 1.60 / 1.63 | 1.52 | 49 of 49 | 0.00 | 1.80 / 1.80 |
| guard_mirror | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 6.1 % (4.8–7.8) | 93.9 % (92.2–95.2) | 0.0 % (0.0–0.4) | 6.1 % (4.8–7.8) | 0.86 (3) | 0 | 0 | 1.60 / 1.60 / 1.63 | 1.48 | 61 of 61 | 0.00 | 2.00 / 2.00 |
| guard_mirror | strike_sacrifice | 1000 | 3.6 % (2.6–4.9) | 96.4 % (95.1–97.4) | 0.0 % (0.0–0.4) | 3.6 % (2.6–4.9) | 0.40 (3) | 0 | 0 | 1.60 / 1.60 / 1.78 | 1.60 | 36 of 36 | 0.00 | 1.40 / 2.85 |
| guard_mirror | strike_converge | 1000 | 55.4 % (52.3–58.5) | 44.6 % (41.5–47.7) | 0.0 % (0.0–0.4) | 55.4 % (52.3–58.5) | 2.33 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 554 of 554 | 0.00 | 6.53 / 12.71 |
| guard_field | strike_straight | 1000 | 8.9 % (7.3–10.8) | 91.1 % (89.2–92.7) | 0.0 % (0.0–0.4) | 8.9 % (7.3–10.8) | 1.71 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 89 of 89 | 0.00 | 1.40 / 1.40 |
| guard_field | strike_flank | 1000 | 28.5 % (25.8–31.4) | 71.5 % (68.6–74.2) | 0.0 % (0.0–0.4) | 28.5 % (25.8–31.4) | 2.20 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 285 of 285 | 0.00 | 1.70 / 1.80 |
| guard_field | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 12.8 % (10.9–15.0) | 87.2 % (85.0–89.1) | 0.0 % (0.0–0.4) | 12.8 % (10.9–15.0) | 1.85 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 128 of 128 | 0.00 | 1.80 / 1.80 |
| guard_field | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 15.8 % (13.7–18.2) | 84.2 % (81.8–86.3) | 0.0 % (0.0–0.4) | 15.8 % (13.7–18.2) | 1.94 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 158 of 158 | 0.00 | 2.00 / 2.00 |
| guard_field | strike_sacrifice | 1000 | 25.6 % (23.0–28.4) | 74.4 % (71.6–77.0) | 0.0 % (0.0–0.4) | 25.6 % (23.0–28.4) | 1.39 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 256 of 256 | 0.00 | 1.45 / 3.00 |
| guard_field | strike_converge | 1000 | 67.9 % (64.9–70.7) | 32.1 % (29.3–35.1) | 0.0 % (0.0–0.4) | 67.9 % (64.9–70.7) | 2.68 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 679 of 679 | 0.00 | 3.75 / 5.90 |

## arena_7p5: arena, 7.5 m with the hangar ring 3.2 m (two changes) (3v3, game `arena_7p5`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| parked (holds starts; = still at 2+ Guards) | strike_straight | 1000 | 52.5 % (49.4–55.6) | 47.5 % (44.4–50.6) | 0.0 % (0.0–0.4) | 52.5 % (49.4–55.6) | 2.52 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 525 of 525 | 0.00 | 3.65 / 3.75 |
| parked (holds starts; = still at 2+ Guards) | strike_flank | 1000 | 37.2 % (34.3–40.2) | 62.8 % (59.8–65.7) | 0.0 % (0.0–0.4) | 37.2 % (34.3–40.2) | 2.34 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 372 of 372 | 0.00 | 4.50 / 4.85 |
| parked (holds starts; = still at 2+ Guards) | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 44.7 % (41.6–47.8) | 55.3 % (52.2–58.4) | 0.0 % (0.0–0.4) | 44.7 % (41.6–47.8) | 2.43 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 447 of 447 | 0.00 | 4.25 / 4.30 |
| parked (holds starts; = still at 2+ Guards) | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 40.9 % (37.9–44.0) | 59.1 % (56.0–62.1) | 0.0 % (0.0–0.4) | 40.9 % (37.9–44.0) | 2.39 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 409 of 409 | 0.00 | 4.45 / 4.50 |
| parked (holds starts; = still at 2+ Guards) | strike_sacrifice | 1000 | 53.0 % (49.9–56.1) | 47.0 % (43.9–50.1) | 0.0 % (0.0–0.4) | 53.0 % (49.9–56.1) | 2.53 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 530 of 530 | 0.00 | 5.35 / 6.00 |
| parked (holds starts; = still at 2+ Guards) | strike_converge | 1000 | 99.5 % (98.8–99.8) | 0.5 % (0.2–1.2) | 0.0 % (0.0–0.4) | 99.5 % (98.8–99.8) | 3.00 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 995 of 995 | 0.00 | 8.70 / 13.96 |
| guard_parked_ring | strike_straight | 1000 | 51.2 % (48.1–54.3) | 48.8 % (45.7–51.9) | 0.0 % (0.0–0.4) | 51.2 % (48.1–54.3) | 2.50 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 512 of 512 | 0.00 | 3.65 / 3.75 |
| guard_parked_ring | strike_flank | 1000 | 39.5 % (36.5–42.6) | 60.5 % (57.4–63.5) | 0.0 % (0.0–0.4) | 39.5 % (36.5–42.6) | 2.36 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 395 of 395 | 0.00 | 4.50 / 4.90 |
| guard_parked_ring | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 43.7 % (40.7–46.8) | 56.3 % (53.2–59.3) | 0.0 % (0.0–0.4) | 43.7 % (40.7–46.8) | 2.42 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 437 of 437 | 0.00 | 4.25 / 4.30 |
| guard_parked_ring | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 39.9 % (36.9–43.0) | 60.1 % (57.0–63.1) | 0.0 % (0.0–0.4) | 39.9 % (36.9–43.0) | 2.38 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 399 of 399 | 0.00 | 4.45 / 4.50 |
| guard_parked_ring | strike_sacrifice | 1000 | 51.2 % (48.1–54.3) | 48.8 % (45.7–51.9) | 0.0 % (0.0–0.4) | 51.2 % (48.1–54.3) | 2.51 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 512 of 512 | 0.00 | 5.30 / 5.95 |
| guard_parked_ring | strike_converge | 1000 | 99.4 % (98.7–99.7) | 0.6 % (0.3–1.3) | 0.0 % (0.0–0.4) | 99.4 % (98.7–99.7) | 2.99 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 994 of 994 | 0.00 | 8.60 / 13.85 |
| guard_mark_edge | strike_straight | 1000 | 92.0 % (90.2–93.5) | 8.0 % (6.5–9.8) | 0.0 % (0.0–0.4) | 92.0 % (90.2–93.5) | 2.92 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 920 of 920 | 0.00 | 3.00 / 3.65 |
| guard_mark_edge | strike_flank | 1000 | 95.6 % (94.1–96.7) | 4.4 % (3.3–5.9) | 0.0 % (0.0–0.4) | 95.6 % (94.1–96.7) | 2.96 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 956 of 956 | 0.00 | 3.60 / 4.35 |
| guard_mark_edge | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 92.3 % (90.5–93.8) | 7.7 % (6.2–9.5) | 0.0 % (0.0–0.4) | 92.3 % (90.5–93.8) | 2.92 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 923 of 923 | 0.00 | 3.50 / 4.20 |
| guard_mark_edge | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 92.4 % (90.6–93.9) | 7.6 % (6.1–9.4) | 0.0 % (0.0–0.4) | 92.4 % (90.6–93.9) | 2.92 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 924 of 924 | 0.00 | 3.75 / 4.40 |
| guard_mark_edge | strike_sacrifice | 1000 | 97.0 % (95.7–97.9) | 3.0 % (2.1–4.3) | 0.0 % (0.0–0.4) | 97.0 % (95.7–97.9) | 2.97 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 970 of 970 | 0.00 | 4.10 / 5.20 |
| guard_mark_edge | strike_converge | 1000 | 96.2 % (94.8–97.2) | 3.8 % (2.8–5.2) | 0.0 % (0.0–0.4) | 96.2 % (94.8–97.2) | 2.96 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 962 of 962 | 0.00 | 5.05 / 9.61 |
| guard_mirror | strike_straight | 1000 | 92.2 % (90.4–93.7) | 7.8 % (6.3–9.6) | 0.0 % (0.0–0.4) | 92.2 % (90.4–93.7) | 2.92 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 922 of 922 | 0.00 | 3.00 / 3.65 |
| guard_mirror | strike_flank | 1000 | 90.4 % (88.4–92.1) | 9.6 % (7.9–11.6) | 0.0 % (0.0–0.4) | 90.4 % (88.4–92.1) | 2.90 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 904 of 904 | 0.00 | 3.75 / 4.40 |
| guard_mirror | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 92.6 % (90.8–94.1) | 7.4 % (5.9–9.2) | 0.0 % (0.0–0.4) | 92.6 % (90.8–94.1) | 2.92 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 926 of 926 | 0.00 | 3.50 / 4.20 |
| guard_mirror | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 92.1 % (90.3–93.6) | 7.9 % (6.4–9.7) | 0.0 % (0.0–0.4) | 92.1 % (90.3–93.6) | 2.91 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 921 of 921 | 0.00 | 3.70 / 4.40 |
| guard_mirror | strike_sacrifice | 1000 | 93.9 % (92.2–95.2) | 6.1 % (4.8–7.8) | 0.0 % (0.0–0.4) | 93.9 % (92.2–95.2) | 2.94 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 939 of 939 | 0.00 | 4.40 / 5.40 |
| guard_mirror | strike_converge | 1000 | 96.4 % (95.1–97.4) | 3.6 % (2.6–4.9) | 0.0 % (0.0–0.4) | 96.4 % (95.1–97.4) | 2.96 (3) | 0 | 0 | 1.60 / 1.60 / 1.60 | 1.60 | 964 of 964 | 0.00 | 5.70 / 11.01 |
| guard_field | strike_straight | 1000 | 79.1 % (76.5–81.5) | 20.9 % (18.5–23.5) | 0.0 % (0.0–0.4) | 79.1 % (76.5–81.5) | 2.79 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 791 of 791 | 0.00 | 2.50 / 3.65 |
| guard_field | strike_flank | 1000 | 84.0 % (81.6–86.1) | 16.0 % (13.9–18.4) | 0.0 % (0.0–0.4) | 84.0 % (81.6–86.1) | 2.84 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 840 of 840 | 0.00 | 3.00 / 4.21 |
| guard_field | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 79.9 % (77.3–82.3) | 20.1 % (17.7–22.7) | 0.0 % (0.0–0.4) | 79.9 % (77.3–82.3) | 2.80 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.52 | 799 of 799 | 0.00 | 2.85 / 4.25 |
| guard_field | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 79.7 % (77.1–82.1) | 20.3 % (17.9–22.9) | 0.0 % (0.0–0.4) | 79.7 % (77.1–82.1) | 2.80 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.48 | 797 of 797 | 0.00 | 3.00 / 4.45 |
| guard_field | strike_sacrifice | 1000 | 86.3 % (84.0–88.3) | 13.7 % (11.7–16.0) | 0.0 % (0.0–0.4) | 86.3 % (84.0–88.3) | 2.86 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 863 of 863 | 0.00 | 2.95 / 4.75 |
| guard_field | strike_converge | 1000 | 87.1 % (84.9–89.0) | 12.9 % (11.0–15.1) | 0.0 % (0.0–0.4) | 87.1 % (84.9–89.0) | 2.87 (3) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 871 of 871 | 0.00 | 3.05 / 5.10 |

## Batches (speed and memory)

| Batch | size | games | ticks | s | game-steps/s | peak reserved (GiB) |
|---|---|---|---|---|---|---|
| ctl_tag_fires_2v1/b00 | 2v1 | 1000 | 100 | 2.4 | 41,526 | 0.03 |
| ctl_tag_fires_3v3/b00 | 3v3 | 1000 | 100 | 1.9 | 51,403 | 0.05 |
| ctl_tag_fires_5v3/b00 | 5v3 | 1000 | 100 | 2.0 | 50,673 | 0.05 |
| ctl_reach_fires_1v1/b00 | 1v1 | 1000 | 100 | 1.7 | 59,907 | 0.05 |
| ctl_reach_fires_3v3/b00 | 3v3 | 1000 | 100 | 2.1 | 48,365 | 0.05 |
| base/b00 | 3v3 | 30000 | 400 | 34.4 | 348,913 | 0.60 |
| ctl_same_seed/b00 | 3v3 | 30000 | 400 | 34.4 | 348,525 | 0.60 |
| ctl_stand_still/b00 | 3v3 | 5000 | 2400 | 96.2 | 124,776 | 0.60 |
| ctl_still_1v1/b00 | 1v1 | 1000 | 200 | 2.5 | 80,054 | 0.60 |
| ctl_still_2v1/b00 | 2v1 | 1000 | 200 | 2.6 | 76,823 | 0.60 |
| ctl_still_3v3/b00 | 3v3 | 1000 | 200 | 2.7 | 73,024 | 0.60 |
| ctl_still_5v3/b00 | 5v3 | 1000 | 200 | 2.7 | 72,916 | 0.60 |
| ctl_tiny_tag/b00 | 3v3 | 10000 | 2400 | 248.6 | 96,529 | 0.61 |
| ctl_tag_off/b00 | 3v3 | 30000 | 2400 | 334.8 | 215,062 | 0.66 |
| sens_strike_dz_1mm/b00 | 3v3 | 5000 | 100 | 3.6 | 140,253 | 0.66 |
| size_1v1/b00 | 1v1 | 20000 | 100 | 2.8 | 711,442 | 0.66 |
| size_2v1/b00 | 2v1 | 20000 | 100 | 3.1 | 653,174 | 0.67 |
| size_5v3/b00 | 5v3 | 30000 | 500 | 71.9 | 208,638 | 0.84 |
| survive_1/b00 | 3v3 | 30000 | 400 | 32.2 | 373,059 | 0.84 |
| tag_1p2/b00 | 3v3 | 30000 | 500 | 47.3 | 317,382 | 0.84 |
| tag_1p4/b00 | 3v3 | 30000 | 400 | 34.7 | 345,858 | 0.84 |
| tag_1p8/b00 | 3v3 | 30000 | 500 | 37.0 | 405,396 | 0.84 |
| zone_2p4/b00 | 3v3 | 30000 | 500 | 39.0 | 384,995 | 0.84 |
| arena_7p5/b00 | 3v3 | 30000 | 400 | 33.7 | 356,112 | 0.84 |

## Clips (videos/)

- videos/guard_parked_ring_v_strike_straight.gif: guard_parked_ring v strike_straight, game 0, outcome hold at 2.8 s (0.05 MB, 4 s to make)
- videos/guard_field_v_strike_converge.gif: guard_field v strike_converge, game 0, outcome hold at 2.7 s (0.05 MB, 5 s to make)
- videos/guard_mark_edge_v_strike_sacrifice.gif: guard_mark_edge v strike_sacrifice, game 0, outcome hold at 2.7 s (0.05 MB, 5 s to make)

Confounds stated before the run: zone_2p4: zone radius 2.4 m: the ring stays 2.75 m (2.75 >= 2.4 + 0.3); the alternative 2.4 + (2.75 - 1.6) = 3.55 m does not fit the 3.0 m keep-in limit. Second change: the run-in from the ring to the zone edge is 0.35 m (0.7 s at 0.5 m/s) instead of 1.15 m (2.3 s); arena_7p5: 7.5 m arena with the hangar ring 3.2 m (the sheet's hangar value): two things change, the arena side (keep-in 3.5 m) and the ring (run-in 1.6 m instead of 1.15 m); height_offset_cell: built as an INFO sensitivity group (LEAD CALL 21 Nov 2026): group sens_strike_dz_1mm, the base game with every Strike drone started 1 mm higher (strike_start_dz_m 0.001) through the sweep's own starts hook (ste/sweep.py SweepGame._draw_starts; the core game draws every start at one height and is not changed), strike_straight against every Guard script, compared with the base cells of the same pairs. T13 lesson: on the physics drone a 1 mm offset flips Strike over/under outcomes; tier 1 holds heights, so a change here is a tier-1 effect. Every other group: no offset, no jitter
