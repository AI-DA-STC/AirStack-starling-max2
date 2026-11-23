# L1.9 scripted screen (INFO): results

Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory). Observed in the training simulator; nothing here is a flight result.

- Gate file `configs/ste_l1/l19_screen_gates.toml`, sha256 `fd79fd861e9f32bddf6ad3ddb317286b20109213e09ee685da8642f82c9ecef1`; commit `4010dededf13`; device cpu; seed 110000; 1000 games per cell, 20 cells per batch; effective 164 s of a 1.5 h cap.

Run notes: **Never suspend the machine during a GPU job** (a suspend counts in full against the cap and is billed as GPU-hours; tooling task L07-SUSPEND). **Finding L011-F1**: the scripted players decide every tick (0.05 s), not at the sheet's 0.6 s decision period; this sweep measures scripted play at 0.05 s; L0.12's trainers must fix their decision period explicitly (T41's recipe used 12 ticks = 0.6 s).

## Controls (read these first)

| Control | Kind | Status | Detail |
|---|---|---|---|
| ctl_tag_fires_1v1 | tag_fires | **PASS** | 1000 games: 1 tags each, all ended at step 1 |
| ctl_reach_fires_1v1 | reach_fires | **PASS** | 1000 reaches in 1000 games |
| ctl_same_seed | same_seed_twice | **PASS** | 20000 games equal |
| ctl_stand_still | stand_still_never_reaches | **PASS** | 0 reaches in 5000 games |
| ctl_still_1v1 | stand_still_zero_tags | **PASS** | 0 tags in 1000 games |
| ctl_still_1v1_1p15 | stand_still_zero_tags | **PASS** | 0 tags in 1000 games |
| ctl_tiny_tag | zero_tags | **PASS** | 0 tags in 5000 games |
| ctl_tag_off | zero_tags | **PASS** | 0 tags in 20000 games |
| tags_one_for_one | global | **PASS** | every played game one for one |
| paired_starts | global | **PASS** | 1 start setting(s), one set of starts each |
| no_nonfinite_actions | global | **PASS** | 0 non-finite actions |

Every control holds.

Unchosen tags (INFO, L0.12b; LEAD CALL 21 Nov 2026 (L0.12b Q4)). Pushed together (the main share): on the tag's tick the safety filter's correction closed the Guard-Strike pair faster than the players' own commands (relative correction along the pair line below -1e-3 m/s), so the tag would not have happened on this tick without the filter. Filter active at the tag (an upper bound): the filter corrected either drone of the pair on the tag's tick (velocity change > 1e-3 m/s), braking included. At the filter edge: the 3-D pair distance was at most the filter distance (1.10 m) plus the gate file's [run] tag_edge_margin_m. Shares are of the tags of the finished first games of each cell.

## Shortlist for L0.12 (rule: gate file [shortlist])

Shortlist: **base_1v1, tag_1p15_1v1**. Without the strike_high, strike_low columns (tier 1 vertical response not fitted (s2b.toml z_up_info)): base_1v1, tag_1p15_1v1 (same).

| Variant | H: best Guard's worst hold | g* | R: best Strike's worst reach | s* | d (games) | eligible | rank |
|---|---|---|---|---|---|---|---|
| base_1v1 | 1.00 | guard_mark_edge | 0.00 | strike_straight | 0.00 (0) | reference, ruled out because Guard-trivial looking: a scripted Guard holds against every scripted Strike | reference |
| tag_1p15_1v1 | 0.84 | guard_mark_edge | 0.16 | strike_straight | 0.16 (157) | reference, ruled out because Guard-trivial looking: a scripted Guard holds against every scripted Strike | reference |
| no proximity tag (INFO; ctl_tag_off) | 0.00 | guard_parked_centre | 1.00 | strike_straight | 0.00 (0) | INFO reference (no proximity tag): never shortlisted; Strike-trivial looking: a scripted Strike reaches against every scripted Guard | INFO, never shortlisted |

## ctl_tag_fires_1v1: control tag_fires (1v1, game `tag_10m`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) | pushed together (share) | filter active at the tag, upper bound (share) | tags at the filter edge (share) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| zero | zero | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | n/a / n/a / n/a | n/a | 1000 of 1000 | 0.00 | 0.05 / 0.05 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |

## ctl_reach_fires_1v1: control reach_fires (1v1, game `zone_2p4_tag_off`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) | pushed together (share) | filter active at the tag, upper bound (share) | tags at the filter edge (share) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| zero | strike_straight | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.61 / 1.84 / 2.41 | 1.61 | 0 of 0 | n/a | 1.40 / 1.40 | 0 of 0 | 0 of 0 | 0 of 0 |

## base_1v1: team size and tag radius, 1v1, tag 1.6 m (the L1.9 runs' reference) (1v1, game `base`)

Not played (with one Strike drone they fly as strike_straight): guard_parked_centre v strike_sacrifice, guard_parked_centre v strike_converge, guard_parked_ring v strike_sacrifice, guard_parked_ring v strike_converge, guard_mark_edge v strike_sacrifice, guard_mark_edge v strike_converge, guard_mirror v strike_sacrifice, guard_mirror v strike_converge, guard_field v strike_sacrifice, guard_field v strike_converge.

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) | pushed together (share) | filter active at the tag, upper bound (share) | tags at the filter edge (share) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| guard_parked_centre | strike_straight | 1000 | 68.3 % (65.4–71.1) | 31.7 % (28.9–34.6) | 0.0 % (0.0–0.4) | 68.3 % (65.4–71.1) | 0.68 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 683 of 683 | 0.00 | 2.90 / 2.90 | 0 of 683 (0.000) | 0 of 683 (0.000) | 0 of 683 (0.000) |
| guard_parked_centre | strike_flank | 1000 | 55.2 % (52.1–58.3) | 44.8 % (41.7–47.9) | 0.0 % (0.0–0.4) | 55.2 % (52.1–58.3) | 0.55 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 552 of 552 | 0.00 | 3.25 / 3.40 | 0 of 552 (0.000) | 0 of 552 (0.000) | 0 of 552 (0.000) |
| guard_parked_centre | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.63 / 1.64 / 1.67 | 1.56 | 0 of 0 | n/a | 3.40 / 3.40 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_parked_centre | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.67 / 1.67 / 1.70 | 1.55 | 0 of 0 | n/a | 3.60 / 3.60 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_parked_ring | strike_straight | 1000 | 42.5 % (39.5–45.6) | 57.5 % (54.4–60.5) | 0.0 % (0.0–0.4) | 42.5 % (39.5–45.6) | 0.42 (1) | 0 | 0 | 1.60 / 1.60 / 1.77 | 1.60 | 425 of 425 | 0.00 | 2.90 / 2.90 | 0 of 425 (0.000) | 0 of 425 (0.000) | 0 of 425 (0.000) |
| guard_parked_ring | strike_flank | 1000 | 50.4 % (47.3–53.5) | 49.6 % (46.5–52.7) | 0.0 % (0.0–0.4) | 50.4 % (47.3–53.5) | 0.50 (1) | 0 | 0 | 1.60 / 1.60 / 1.63 | 1.60 | 504 of 504 | 0.00 | 2.90 / 2.90 | 0 of 504 (0.000) | 0 of 504 (0.000) | 0 of 504 (0.000) |
| guard_parked_ring | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 39.0 % (36.0–42.1) | 61.0 % (57.9–64.0) | 0.0 % (0.0–0.4) | 39.0 % (36.0–42.1) | 0.39 (1) | 0 | 0 | 1.60 / 1.60 / 1.84 | 1.52 | 390 of 390 | 0.00 | 3.40 / 3.40 | 0 of 390 (0.000) | 0 of 390 (0.000) | 0 of 390 (0.000) |
| guard_parked_ring | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 37.1 % (34.2–40.1) | 62.9 % (59.9–65.8) | 0.0 % (0.0–0.4) | 37.1 % (34.2–40.1) | 0.37 (1) | 0 | 0 | 1.60 / 1.60 / 1.87 | 1.48 | 371 of 371 | 0.00 | 3.60 / 3.60 | 0 of 371 (0.000) | 0 of 371 (0.000) | 0 of 371 (0.000) |
| guard_mark_edge | strike_straight | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 1000 of 1000 | 0.00 | 2.10 / 2.60 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_mark_edge | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 1000 of 1000 | 0.00 | 2.20 / 2.60 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_mark_edge | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.52 | 1000 of 1000 | 0.00 | 2.40 / 2.90 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_mark_edge | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.48 | 1000 of 1000 | 0.00 | 2.55 / 3.10 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_mirror | strike_straight | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 1000 of 1000 | 0.00 | 2.10 / 2.60 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_mirror | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 1000 of 1000 | 0.00 | 2.30 / 2.60 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_mirror | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.52 | 1000 of 1000 | 0.00 | 2.40 / 2.90 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_mirror | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.48 | 1000 of 1000 | 0.00 | 2.55 / 3.10 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_field | strike_straight | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 1000 of 1000 | 0.00 | 2.10 / 2.60 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_field | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 1000 of 1000 | 0.00 | 2.20 / 2.60 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_field | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.52 | 1000 of 1000 | 0.00 | 2.40 / 2.90 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_field | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.48 | 1000 of 1000 | 0.00 | 2.55 / 3.10 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |

## tag_1p15_1v1: team size and tag radius, 1v1, tag 1.15 m (bubble touch: filter 1.10 m + 0.05 m; G0 row 8) (1v1, game `tag_1p15_1v1`)

Not played (with one Strike drone they fly as strike_straight): guard_parked_centre v strike_sacrifice, guard_parked_centre v strike_converge, guard_parked_ring v strike_sacrifice, guard_parked_ring v strike_converge, guard_mark_edge v strike_sacrifice, guard_mark_edge v strike_converge, guard_mirror v strike_sacrifice, guard_mirror v strike_converge, guard_field v strike_sacrifice, guard_field v strike_converge.

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) | pushed together (share) | filter active at the tag, upper bound (share) | tags at the filter edge (share) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| guard_parked_centre | strike_straight | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.55 / 1.58 / 1.60 | 1.55 | 0 of 0 | n/a | 2.90 / 2.90 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_parked_centre | strike_flank | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.56 / 1.56 / 1.60 | 1.56 | 0 of 0 | n/a | 3.25 / 3.40 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_parked_centre | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.63 / 1.64 / 1.67 | 1.56 | 0 of 0 | n/a | 3.40 / 3.40 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_parked_centre | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.67 / 1.67 / 1.70 | 1.55 | 0 of 0 | n/a | 3.60 / 3.60 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_parked_ring | strike_straight | 1000 | 23.0 % (20.5–25.7) | 77.0 % (74.3–79.5) | 0.0 % (0.0–0.4) | 23.0 % (20.5–25.7) | 0.23 (1) | 0 | 0 | 1.15 / 1.15 / 1.77 | 1.15 | 230 of 230 | 0.00 | 2.90 / 2.90 | 0 of 230 (0.000) | 230 of 230 (1.000) | 0 of 230 (0.000) |
| guard_parked_ring | strike_flank | 1000 | 47.2 % (44.1–50.3) | 52.8 % (49.7–55.9) | 0.0 % (0.0–0.4) | 47.2 % (44.1–50.3) | 0.47 (1) | 0 | 0 | 1.15 / 1.15 / 1.26 | 1.15 | 472 of 472 | 0.00 | 2.90 / 3.75 | 0 of 472 (0.000) | 472 of 472 (1.000) | 0 of 472 (0.000) |
| guard_parked_ring | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 19.5 % (17.2–22.1) | 80.5 % (77.9–82.8) | 0.0 % (0.0–0.4) | 19.5 % (17.2–22.1) | 0.20 (1) | 0 | 0 | 1.15 / 1.15 / 1.84 | 1.03 | 195 of 195 | 0.00 | 3.40 / 3.40 | 0 of 195 (0.000) | 195 of 195 (1.000) | 0 of 195 (0.000) |
| guard_parked_ring | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 15.8 % (13.7–18.2) | 84.2 % (81.8–86.3) | 0.0 % (0.0–0.4) | 15.8 % (13.7–18.2) | 0.16 (1) | 0 | 0 | 1.15 / 1.15 / 1.87 | 0.98 | 158 of 158 | 0.00 | 3.60 / 3.60 | 0 of 158 (0.000) | 158 of 158 (1.000) | 0 of 158 (0.000) |
| guard_mark_edge | strike_straight | 1000 | 84.3 % (81.9–86.4) | 15.7 % (13.6–18.1) | 0.0 % (0.0–0.4) | 84.3 % (81.9–86.4) | 0.84 (1) | 0 | 0 | 1.15 / 1.15 / 1.17 | 1.15 | 843 of 843 | 0.00 | 2.60 / 2.90 | 0 of 843 (0.000) | 843 of 843 (1.000) | 0 of 843 (0.000) |
| guard_mark_edge | strike_flank | 1000 | 89.6 % (87.6–91.3) | 10.4 % (8.7–12.4) | 0.0 % (0.0–0.4) | 89.6 % (87.6–91.3) | 0.90 (1) | 0 | 0 | 1.15 / 1.15 / 1.16 | 1.15 | 896 of 896 | 0.00 | 2.80 / 3.05 | 0 of 896 (0.000) | 896 of 896 (1.000) | 0 of 896 (0.000) |
| guard_mark_edge | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 88.7 % (86.6–90.5) | 11.3 % (9.5–13.4) | 0.0 % (0.0–0.4) | 88.7 % (86.6–90.5) | 0.89 (1) | 0 | 0 | 1.15 / 1.15 / 1.16 | 1.02 | 887 of 887 | 0.00 | 3.00 / 3.40 | 0 of 887 (0.000) | 887 of 887 (1.000) | 0 of 887 (0.000) |
| guard_mark_edge | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 89.2 % (87.1–91.0) | 10.8 % (9.0–12.9) | 0.0 % (0.0–0.4) | 89.2 % (87.1–91.0) | 0.89 (1) | 0 | 0 | 1.15 / 1.15 / 1.16 | 0.96 | 892 of 892 | 0.00 | 3.20 / 3.60 | 0 of 892 (0.000) | 892 of 892 (1.000) | 0 of 892 (0.000) |
| guard_mirror | strike_straight | 1000 | 84.1 % (81.7–86.2) | 15.9 % (13.8–18.3) | 0.0 % (0.0–0.4) | 84.1 % (81.7–86.2) | 0.84 (1) | 0 | 0 | 1.15 / 1.15 / 1.17 | 1.15 | 841 of 841 | 0.00 | 2.60 / 2.90 | 0 of 841 (0.000) | 841 of 841 (1.000) | 0 of 841 (0.000) |
| guard_mirror | strike_flank | 1000 | 88.2 % (86.1–90.1) | 11.8 % (9.9–13.9) | 0.0 % (0.0–0.4) | 88.2 % (86.1–90.1) | 0.88 (1) | 0 | 0 | 1.15 / 1.15 / 1.16 | 1.15 | 882 of 882 | 0.00 | 2.95 / 3.10 | 0 of 882 (0.000) | 882 of 882 (1.000) | 0 of 882 (0.000) |
| guard_mirror | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 88.7 % (86.6–90.5) | 11.3 % (9.5–13.4) | 0.0 % (0.0–0.4) | 88.7 % (86.6–90.5) | 0.89 (1) | 0 | 0 | 1.15 / 1.15 / 1.16 | 1.02 | 887 of 887 | 0.00 | 3.00 / 3.40 | 0 of 887 (0.000) | 887 of 887 (1.000) | 0 of 887 (0.000) |
| guard_mirror | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 89.2 % (87.1–91.0) | 10.8 % (9.0–12.9) | 0.0 % (0.0–0.4) | 89.2 % (87.1–91.0) | 0.89 (1) | 0 | 0 | 1.15 / 1.15 / 1.16 | 0.96 | 892 of 892 | 0.00 | 3.20 / 3.60 | 0 of 892 (0.000) | 892 of 892 (1.000) | 0 of 892 (0.000) |
| guard_field | strike_straight | 1000 | 84.3 % (81.9–86.4) | 15.7 % (13.6–18.1) | 0.0 % (0.0–0.4) | 84.3 % (81.9–86.4) | 0.84 (1) | 0 | 0 | 1.15 / 1.15 / 1.17 | 1.15 | 843 of 843 | 0.00 | 2.60 / 2.90 | 0 of 843 (0.000) | 843 of 843 (1.000) | 0 of 843 (0.000) |
| guard_field | strike_flank | 1000 | 89.6 % (87.6–91.3) | 10.4 % (8.7–12.4) | 0.0 % (0.0–0.4) | 89.6 % (87.6–91.3) | 0.90 (1) | 0 | 0 | 1.15 / 1.15 / 1.16 | 1.15 | 896 of 896 | 0.00 | 2.80 / 3.05 | 0 of 896 (0.000) | 896 of 896 (1.000) | 0 of 896 (0.000) |
| guard_field | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 88.7 % (86.6–90.5) | 11.3 % (9.5–13.4) | 0.0 % (0.0–0.4) | 88.7 % (86.6–90.5) | 0.89 (1) | 0 | 0 | 1.15 / 1.15 / 1.16 | 1.02 | 887 of 887 | 0.00 | 3.00 / 3.40 | 0 of 887 (0.000) | 887 of 887 (1.000) | 0 of 887 (0.000) |
| guard_field | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 89.2 % (87.1–91.0) | 10.8 % (9.0–12.9) | 0.0 % (0.0–0.4) | 89.2 % (87.1–91.0) | 0.89 (1) | 0 | 0 | 1.15 / 1.15 / 1.16 | 0.96 | 892 of 892 | 0.00 | 3.20 / 3.60 | 0 of 892 (0.000) | 892 of 892 (1.000) | 0 of 892 (0.000) |

## ctl_same_seed: control same_seed_twice (1v1, game `base`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) | pushed together (share) | filter active at the tag, upper bound (share) | tags at the filter edge (share) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| guard_parked_centre | strike_straight | 1000 | 68.3 % (65.4–71.1) | 31.7 % (28.9–34.6) | 0.0 % (0.0–0.4) | 68.3 % (65.4–71.1) | 0.68 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 683 of 683 | 0.00 | 2.90 / 2.90 | 0 of 683 (0.000) | 0 of 683 (0.000) | 0 of 683 (0.000) |
| guard_parked_centre | strike_flank | 1000 | 55.2 % (52.1–58.3) | 44.8 % (41.7–47.9) | 0.0 % (0.0–0.4) | 55.2 % (52.1–58.3) | 0.55 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 552 of 552 | 0.00 | 3.25 / 3.40 | 0 of 552 (0.000) | 0 of 552 (0.000) | 0 of 552 (0.000) |
| guard_parked_centre | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.63 / 1.64 / 1.67 | 1.56 | 0 of 0 | n/a | 3.40 / 3.40 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_parked_centre | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.67 / 1.67 / 1.70 | 1.55 | 0 of 0 | n/a | 3.60 / 3.60 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_parked_ring | strike_straight | 1000 | 42.5 % (39.5–45.6) | 57.5 % (54.4–60.5) | 0.0 % (0.0–0.4) | 42.5 % (39.5–45.6) | 0.42 (1) | 0 | 0 | 1.60 / 1.60 / 1.77 | 1.60 | 425 of 425 | 0.00 | 2.90 / 2.90 | 0 of 425 (0.000) | 0 of 425 (0.000) | 0 of 425 (0.000) |
| guard_parked_ring | strike_flank | 1000 | 50.4 % (47.3–53.5) | 49.6 % (46.5–52.7) | 0.0 % (0.0–0.4) | 50.4 % (47.3–53.5) | 0.50 (1) | 0 | 0 | 1.60 / 1.60 / 1.63 | 1.60 | 504 of 504 | 0.00 | 2.90 / 2.90 | 0 of 504 (0.000) | 0 of 504 (0.000) | 0 of 504 (0.000) |
| guard_parked_ring | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 39.0 % (36.0–42.1) | 61.0 % (57.9–64.0) | 0.0 % (0.0–0.4) | 39.0 % (36.0–42.1) | 0.39 (1) | 0 | 0 | 1.60 / 1.60 / 1.84 | 1.52 | 390 of 390 | 0.00 | 3.40 / 3.40 | 0 of 390 (0.000) | 0 of 390 (0.000) | 0 of 390 (0.000) |
| guard_parked_ring | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 37.1 % (34.2–40.1) | 62.9 % (59.9–65.8) | 0.0 % (0.0–0.4) | 37.1 % (34.2–40.1) | 0.37 (1) | 0 | 0 | 1.60 / 1.60 / 1.87 | 1.48 | 371 of 371 | 0.00 | 3.60 / 3.60 | 0 of 371 (0.000) | 0 of 371 (0.000) | 0 of 371 (0.000) |
| guard_mark_edge | strike_straight | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 1000 of 1000 | 0.00 | 2.10 / 2.60 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_mark_edge | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 1000 of 1000 | 0.00 | 2.20 / 2.60 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_mark_edge | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.52 | 1000 of 1000 | 0.00 | 2.40 / 2.90 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_mark_edge | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.48 | 1000 of 1000 | 0.00 | 2.55 / 3.10 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_mirror | strike_straight | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 1000 of 1000 | 0.00 | 2.10 / 2.60 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_mirror | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 1000 of 1000 | 0.00 | 2.30 / 2.60 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_mirror | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.52 | 1000 of 1000 | 0.00 | 2.40 / 2.90 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_mirror | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.48 | 1000 of 1000 | 0.00 | 2.55 / 3.10 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_field | strike_straight | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 1000 of 1000 | 0.00 | 2.10 / 2.60 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_field | strike_flank | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.60 | 1000 of 1000 | 0.00 | 2.20 / 2.60 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_field | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.52 | 1000 of 1000 | 0.00 | 2.40 / 2.90 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_field | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.62 | 1.48 | 1000 of 1000 | 0.00 | 2.55 / 3.10 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |

## ctl_stand_still: control stand_still_never_reaches (1v1, game `base`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) | pushed together (share) | filter active at the tag, upper bound (share) | tags at the filter edge (share) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| guard_parked_centre | zero | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.97 / 2.19 / 2.71 | 1.97 | 0 of 1000 | 1.00 | 120.00 / 120.00 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_parked_ring | zero | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.91 / 1.95 / 2.76 | 1.91 | 0 of 1000 | 1.00 | 120.00 / 120.00 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_mark_edge | zero | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 1000 of 1000 | 0.00 | 3.85 / 5.05 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_mirror | zero | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 1000 of 1000 | 0.00 | 3.85 / 5.05 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |
| guard_field | zero | 1000 | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 1.00 (1) | 0 | 0 | 1.60 / 1.60 / 1.61 | 1.60 | 1000 of 1000 | 0.00 | 3.85 / 5.05 | 0 of 1000 (0.000) | 0 of 1000 (0.000) | 0 of 1000 (0.000) |

## ctl_still_1v1: control stand_still_zero_tags (1v1, game `base`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) | pushed together (share) | filter active at the tag, upper bound (share) | tags at the filter edge (share) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| zero | zero | 0 (+1000 unfinished) | n/a | n/a | n/a | n/a | n/a (None) | 0 | 0 | n/a / n/a / n/a | n/a | 0 of 0 | n/a | n/a / n/a | 0 of 0 | 0 of 0 | 0 of 0 |

## ctl_still_1v1_1p15: control stand_still_zero_tags (1v1, game `tag_1p15_1v1`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) | pushed together (share) | filter active at the tag, upper bound (share) | tags at the filter edge (share) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| zero | zero | 0 (+1000 unfinished) | n/a | n/a | n/a | n/a | n/a (None) | 0 | 0 | n/a / n/a / n/a | n/a | 0 of 0 | n/a | n/a / n/a | 0 of 0 | 0 of 0 | 0 of 0 |

## ctl_tiny_tag: control zero_tags (1v1, game `tag_0p05`)

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) | pushed together (share) | filter active at the tag, upper bound (share) | tags at the filter edge (share) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| guard_parked_centre | strike_straight | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.55 / 1.58 / 1.60 | 1.55 | 0 of 0 | n/a | 2.90 / 2.90 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_parked_ring | strike_straight | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.05 / 1.06 / 1.77 | 1.05 | 0 of 0 | n/a | 2.90 / 3.25 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_mark_edge | strike_straight | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.04 / 1.04 / 1.06 | 1.04 | 0 of 0 | n/a | 4.30 / 7.05 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_mirror | strike_straight | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.04 / 1.04 / 1.05 | 1.04 | 0 of 0 | n/a | 4.30 / 7.25 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_field | strike_straight | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.04 / 1.04 / 1.06 | 1.04 | 0 of 0 | n/a | 4.30 / 7.05 | 0 of 0 | 0 of 0 | 0 of 0 |

## ctl_tag_off: control zero_tags (1v1, game `tag_off`)

Not played (with one Strike drone they fly as strike_straight): guard_parked_centre v strike_sacrifice, guard_parked_centre v strike_converge, guard_parked_ring v strike_sacrifice, guard_parked_ring v strike_converge, guard_mark_edge v strike_sacrifice, guard_mark_edge v strike_converge, guard_mirror v strike_sacrifice, guard_mirror v strike_converge, guard_field v strike_sacrifice, guard_field v strike_converge.

| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game (max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | length median / p90 (s) | pushed together (share) | filter active at the tag, upper bound (share) | tags at the filter edge (share) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| guard_parked_centre | strike_straight | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.55 / 1.58 / 1.60 | 1.55 | 0 of 0 | n/a | 2.90 / 2.90 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_parked_centre | strike_flank | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.56 / 1.56 / 1.60 | 1.56 | 0 of 0 | n/a | 3.25 / 3.40 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_parked_centre | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.63 / 1.64 / 1.67 | 1.56 | 0 of 0 | n/a | 3.40 / 3.40 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_parked_centre | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.67 / 1.67 / 1.70 | 1.55 | 0 of 0 | n/a | 3.60 / 3.60 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_parked_ring | strike_straight | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.05 / 1.06 / 1.77 | 1.05 | 0 of 0 | n/a | 2.90 / 3.25 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_parked_ring | strike_flank | 1000 | 31.2 % (28.4–34.1) | 68.8 % (65.9–71.6) | 31.2 % (28.4–34.1) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.01 / 1.05 / 1.26 | 1.01 | 0 of 312 | 1.00 | 3.80 / 120.00 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_parked_ring | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.07 / 1.08 / 1.84 | 0.87 | 0 of 0 | n/a | 3.40 / 3.50 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_parked_ring | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.08 / 1.08 / 1.87 | 0.82 | 0 of 0 | n/a | 3.60 / 3.65 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_mark_edge | strike_straight | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.04 / 1.04 / 1.06 | 1.04 | 0 of 0 | n/a | 4.30 / 7.05 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_mark_edge | strike_flank | 1000 | 84.2 % (81.8–86.3) | 15.8 % (13.7–18.2) | 84.2 % (81.8–86.3) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 0.99 / 1.00 / 1.04 | 0.99 | 0 of 842 | 1.00 | 120.00 / 120.00 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_mark_edge | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.07 / 1.07 / 1.08 | 0.05 | 0 of 0 | n/a | 4.10 / 4.40 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_mark_edge | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.07 / 1.07 / 1.08 | 0.02 | 0 of 0 | n/a | 4.15 / 4.35 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_mirror | strike_straight | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.04 / 1.04 / 1.05 | 1.04 | 0 of 0 | n/a | 4.30 / 7.25 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_mirror | strike_flank | 1000 | 75.8 % (73.0–78.4) | 24.2 % (21.6–27.0) | 75.8 % (73.0–78.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.03 / 1.03 / 1.04 | 1.03 | 0 of 758 | 1.00 | 120.00 / 120.00 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_mirror | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.07 / 1.07 / 1.08 | 0.01 | 0 of 0 | n/a | 4.10 / 4.40 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_mirror | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.07 / 1.07 / 1.08 | 0.00 | 0 of 0 | n/a | 4.15 / 4.35 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_field | strike_straight | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.04 / 1.04 / 1.06 | 1.04 | 0 of 0 | n/a | 4.30 / 7.05 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_field | strike_flank | 1000 | 84.2 % (81.8–86.3) | 15.8 % (13.7–18.2) | 84.2 % (81.8–86.3) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 0.99 / 1.00 / 1.04 | 0.99 | 0 of 842 | 1.00 | 120.00 / 120.00 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_field | strike_high (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.07 / 1.07 / 1.08 | 0.05 | 0 of 0 | n/a | 4.10 / 4.40 | 0 of 0 | 0 of 0 | 0 of 0 |
| guard_field | strike_low (tier 1 vertical response not fitted (s2b.toml z_up_info)) | 1000 | 0.0 % (0.0–0.4) | 100.0 % (99.6–100.0) | 0.0 % (0.0–0.4) | 0.0 % (0.0–0.4) | 0.00 (0) | 0 | 0 | 1.07 / 1.07 / 1.08 | 0.02 | 0 of 0 | n/a | 4.15 / 4.35 | 0 of 0 | 0 of 0 | 0 of 0 |

## Batches (speed and memory)

| Batch | size | games | ticks | s | game-steps/s | peak reserved (GiB) |
|---|---|---|---|---|---|---|
| ctl_tag_fires_1v1/b00 | 1v1 | 1000 | 100 | 0.5 | 215,096 | n/a |
| ctl_reach_fires_1v1/b00 | 1v1 | 1000 | 100 | 0.4 | 224,891 | n/a |
| base_1v1/b00 | 1v1 | 20000 | 100 | 3.5 | 564,166 | n/a |
| tag_1p15_1v1/b00 | 1v1 | 20000 | 100 | 3.7 | 534,066 | n/a |
| ctl_same_seed/b00 | 1v1 | 20000 | 100 | 3.5 | 573,908 | n/a |
| ctl_stand_still/b00 | 1v1 | 5000 | 2400 | 33.8 | 354,614 | n/a |
| ctl_still_1v1/b00 | 1v1 | 1000 | 200 | 0.9 | 223,371 | n/a |
| ctl_still_1v1_1p15/b00 | 1v1 | 1000 | 200 | 0.9 | 218,769 | n/a |
| ctl_tiny_tag/b00 | 1v1 | 5000 | 200 | 3.9 | 257,997 | n/a |
| ctl_tag_off/b00 | 1v1 | 20000 | 2400 | 108.3 | 443,013 | n/a |

## Clips (videos/)

- videos/guard_mark_edge_v_strike_straight.gif: guard_mark_edge v strike_straight, game 0, outcome hold at 2.0 s (0.03 MB, 1 s to make)
- videos/guard_field_v_strike_flank.gif: guard_field v strike_flank, game 0, outcome hold at 2.1 s (0.04 MB, 1 s to make)
- videos/guard_mirror_v_strike_low.gif: guard_mirror v strike_low, game 0, outcome hold at 2.5 s (0.05 MB, 1 s to make)

Confounds stated before the run: zone_2p4: not screened here; the zone 2.4 m game file is used only by the reach_fires control (tag off); arena_7p5: not screened here; height_offset_cell: not screened here (no strike_start_dz_m group)
