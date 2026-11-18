# Videos of the NUS port

Training simulator only; nothing here is a flight. Published with NUS's agreement (owner, 18 November 2026; STANDARDS
§2). Since 18 November 2026 ~14:10 every clip is public, the Phase 4 ones included: the owner lifted the hold-back on
the hangar size ("just put all clips on the github … no need to keep it private"). The story behind each clip:
[NUS_PORT](../../NUS_PORT.md).

**Five kinds of clip** (271 clip files, 17.5 MB).

| Folder | What | Simulator | Count |
|---|---|---|---|
| `nus_*` (this folder) | **NUS's own 2-D game and NUS's JAX policies**, drawn by NUS's renderer | NUS's 2-D game | 8 files (6 games; 2 also as GIF) |
| [`phase3/`](#phase-3-the-converted-policies-in-the-replica-t16) | NUS's policies converted to PyTorch, in our copy (replica) of NUS's game (T16) | replica | 4 |
| [`w3/`](#t17-the-self-play-pair-through-the-phase-3-gates) | the self-play pair G19 and S20, converted, through the Phase 3 gates (T17) | replica | 4 |
| [`phase4/row_*/`](#phase-4-the-transfer-ladder-top-down) | the transfer ladder, one folder per row: the first Strike win and the first hold among the first 16 games of each pair | replica, tier 1, tier 2 | 246 |
| [`isaac/`](#isaac-lab-camera-clips-row-6) | the converted policies on rigid-body Starlings in Isaac Lab, an oblique camera (row 6) | tier 2 (Isaac Lab) | 6 MP4, 3 GIF previews |

**How to read them.**

- **NUS's clips** (`nus_*`): blue discs D0–D2 are Guard drones (NUS: "defender"), red discs A0–A2 are Strike drones
  (NUS: "attacker"), the green disc is the zone. The title bar shows NUS's environment name and the step (200 per
  game). NUS's game keeps the "reached" flag once a Strike drone has been inside the zone, and the game runs on to
  step 200, so a Strike drone may leave the zone again: the outcome is the first entry, not the last frame. 12.5
  frames/s (2 steps a second; about 6× real time at 0.6 s per step), all 201 frames.
- **Our top-down clips** (`phase3/`, `w3/`, `phase4/`): blue circles are Guard drones, orange triangles Strike drones,
  the green disc the zone (1.6 m radius); marker size only tells the drones of a team apart. The last frame names the
  outcome. Phase 4 clips play at 6× real time (one frame per 8 ticks of 0.05 s, 15 frames/s); `phase3/` and `w3/`
  interpolate between policy steps at 20 frames/s. The title rounds the arena to whole metres: the hangar arena is
  **7.5 m** square (walls at ±3.75 m), shown as "8 m x 8 m". The replica and Phase 4 row 2.1 have no walls (NUS's
  Guard circle instead), so on `phase3/`, `w3/` and Phase 4 rows 1 and 2.1 the drawn square is only the view (8 m or
  17 m across, depending on the clip).
- **Isaac Lab clips** (`isaac/`): real time, 20 frames/s, an oblique camera on Starling models, 2 s still at the end;
  the overlay names the players. Each recorded game repeats its dry run exactly (same positions, end step and
  outcome) and no drone tipped over.
- "Row's Strike reach" is the row's count over all 1,000 paired games of that pair (the records); one clip is one game.
  "Game *n*" is the *n*-th paired start, the same on every row, so a pair's clips can be compared row by row. The
  closest approach in the Phase 4 tables is measured in the horizontal plane; on rows 5 and 6, where drones change
  height, it can be well under the 1.10 m keep-out while the 3-D distance is not (a drone passing over or under).

## NUS's 2-D game

On the hangar geometry (0.40 m per unit, 0.60 s per step; [NUS_PORT §3](../../NUS_PORT.md#3-phase-0-answers-and-the-hangar-geometry)).

| File | Caption | Source (5090 only) | Size |
|---|---|---|---|
| [`nus_fixed_guard_vs_scripted_strike.mp4`](nus_fixed_guard_vs_scripted_strike.mp4) | Fixed-opponent Guard policy (3,000 updates, the run converted as P3G) against NUS's scripted Strike controller. No Strike drone enters the zone in 200 steps (last evaluation: 19 of 20 held). | NUS outputs `hangar/2026-11-17_fixed_apf_3v3_defender/replays/defender_vs_apf_00003000_env0.gif` | 58 kB |
| [`nus_fixed_strike_vs_scripted_guard.mp4`](nus_fixed_strike_vs_scripted_guard.mp4), [`.gif`](nus_fixed_strike_vs_scripted_guard.gif) | Fixed-opponent Strike policy (the run converted as P3S) against NUS's scripted Guard controller. A Strike drone reaches the zone at about step 7 (last evaluation: 20 of 20 reached). | `hangar/2026-11-17_fixed_apf_3v3_attacker/replays/attacker_vs_apf_00003000_env0.gif` | 76 kB, 161 kB |
| [`nus_selfplay_s1_g7_vs_s1_s8.mp4`](nus_selfplay_s1_g7_vs_s1_s8.mp4) | Self-play seed 1: Guard generation 7 against Strike generation 8. The Guard team holds (that pair: 0.005 Strike wins over 200 games). | `_probes/selfplay_eval/videos/s1_guard7_vs_strike8/` | 49 kB |
| [`nus_selfplay_s2_g7_vs_s2_s8.mp4`](nus_selfplay_s2_g7_vs_s2_s8.mp4) | Self-play seed 2: Guard generation 7 against Strike generation 8. A Strike drone reaches the zone at about step 25 (that pair: 1.000 over 200 games), the "last mover wins" pattern of generations 1–12. | `_probes/selfplay_eval/videos/s2_guard7_vs_strike8/` | 73 kB |
| [`nus_selfplay_s2_g19_vs_s2_s20.mp4`](nus_selfplay_s2_g19_vs_s2_s20.mp4), [`.gif`](nus_selfplay_s2_g19_vs_s2_s20.gif) | The reference pair: seed 2 Guard generation 19 (G19) against Strike generation 20 (S20). The Guard team holds for 200 steps (that pair: 0.025 over 200 games). | `_probes/selfplay_eval/videos/s2_guard19_vs_strike20/` | 58 kB, 168 kB |
| [`nus_selfplay_s2_g19_vs_s3_s8.mp4`](nus_selfplay_s2_g19_vs_s3_s8.mp4) | G19 against a policy it never met: seed 3 Strike generation 8. The Guard team holds (that pair: 0.120 over 200 games). | `_probes/selfplay_eval/videos/s2_guard19_vs_s3strike8/` | 62 kB |

## Phase 3: the converted policies in the replica (T16)

The fixed-opponent pair converted to PyTorch (P3G, P3S) against NUS's scripted controllers, ported; replica of NUS's
game on the hangar geometry. Record: [T16](../../../records/2026-11-18_nus_phase3_conversion_record.md).

| File | Guard v Strike | This game | Size |
|---|---|---|---|
| [`guard_game0.mp4`](phase3/guard_game0.mp4) | P3G v NUS's scripted Strike | Guard team holds for 120 s | 268 kB |
| [`guard_game1.mp4`](phase3/guard_game1.mp4) | P3G v NUS's scripted Strike | Guard team holds for 120 s | 267 kB |
| [`strike_game0.mp4`](phase3/strike_game0.mp4) | NUS's scripted Guard v P3S | Strike team reaches the zone at 4.2 s | 31 kB |
| [`strike_game1.mp4`](phase3/strike_game1.mp4) | NUS's scripted Guard v P3S | Strike team reaches the zone at 3.6 s | 29 kB |

## T17: the self-play pair through the Phase 3 gates

G19 and S20 converted, in the replica. Record: [T17](../../../records/2026-11-18_nus_phase4_w3_reference_gates_record.md)
(the "W3" workstation row).

| File | Guard v Strike | This game | Size |
|---|---|---|---|
| [`archive_arm_G19_vs_S20_game0.mp4`](w3/archive_arm_G19_vs_S20_game0.mp4) | G19 v S20 (archive arm) | Guard team holds for 120 s | 257 kB |
| [`archive_arm_G19_vs_S20_game1.mp4`](w3/archive_arm_G19_vs_S20_game1.mp4) | G19 v S20 (archive arm) | Guard team holds for 120 s | 242 kB |
| [`scripted_arm_G19_game0.mp4`](w3/scripted_arm_G19_game0.mp4) | G19 v NUS's scripted Strike | Guard team holds for 120 s | 269 kB |
| [`scripted_arm_S20_game0.mp4`](w3/scripted_arm_S20_game0.mp4) | NUS's scripted Guard v S20 | Strike team reaches the zone at 7.8 s | 39 kB |

## Isaac Lab camera clips (row 6)

Presentation only (no gates, not a measurement): `scripts/nus_isaac_clips.py` with `configs/nus_isaac_clips.toml`
plays the Phase 4 players on the row 6 game (physics drones, safety filter on, free height with the start jitter) from
the first 16 paired starts. Record: [T24](../../../records/2026-11-18_nus_phase4_rung6_record.md).

| File | Guard v Strike | This game | Row 6 Strike reach (of 1,000) | Size |
|---|---|---|---|---|
| [`g19_vs_s20_strike_win_1.mp4`](isaac/g19_vs_s20_strike_win_1.mp4), [`.gif`](isaac/g19_vs_s20_strike_win_1.gif) | G19 v S20 | game 1: Strike team reaches the zone at 24.1 s (no hold among the 16 candidates) | 979 | 150 kB, 762 kB |
| [`g19_vs_s20_strike_win_2.mp4`](isaac/g19_vs_s20_strike_win_2.mp4) | G19 v S20 | game 2: Strike team reaches the zone at 28.7 s | 979 | 172 kB |
| [`parked_vs_s20_hold_1.mp4`](isaac/parked_vs_s20_hold_1.mp4), [`.gif`](isaac/parked_vs_s20_hold_1.gif) | ParkedGuard v S20 | game 2: Guard team holds for 120 s; the Guard drones command zero speed and no Strike drone gets into the zone | 524 | 556 kB, 1,549 kB |
| [`parked_vs_s20_strike_win_1.mp4`](isaac/parked_vs_s20_strike_win_1.mp4), [`.gif`](isaac/parked_vs_s20_strike_win_1.gif) | ParkedGuard v S20 | game 1: Strike team reaches the zone at 8.1 s | 524 | 60 kB, 307 kB |
| [`g19_vs_apf_strike_win_1.mp4`](isaac/g19_vs_apf_strike_win_1.mp4) | G19 v ApfStrike | game 1: Strike team reaches the zone at 4.1 s | 1000 | 46 kB |
| [`g19_vs_apf_strike_win_2.mp4`](isaac/g19_vs_apf_strike_win_2.mp4) | G19 v ApfStrike | game 2: Strike team reaches the zone at 3.2 s | 1000 | 43 kB |

The GIFs are 480 px wide at 4× real time (the 120 s hold: 400 px at 8×), 5 frames/s, 128 colours, for inline display on GitHub.

## Phase 4: the transfer ladder, top-down

One folder per row; each row changes one thing from the row before ([NUS_PORT §8](../../NUS_PORT.md#8-phase-4-the-transfer-ladder)).
Players: G19 and S20 (the self-play pair), P3G and P3S (the Phase 3 pair), ApfGuard and ApfStrike (NUS's scripted
controllers, ported), ParkedGuard (every Guard drone commands zero; Guard 0 starts at the zone centre), `strike_*`
and `guard_*` (our own scripted strategies, from row 2). A pair has no `hold` clip when none of its first 16 games
was held, and no `strike_win` clip when none was reached. Records:
[T18](../../../records/2026-11-18_nus_phase4_rung1_record.md), [T19](../../../records/2026-11-18_nus_phase4_rung2_record.md),
[T20](../../../records/2026-11-18_nus_phase4_rung3_record.md), [T22](../../../records/2026-11-18_nus_phase4_rung4_2_record.md),
[T23](../../../records/2026-11-18_nus_phase4_rung5_record.md), [T24](../../../records/2026-11-18_nus_phase4_rung6_record.md).

#### Row 1: replica of NUS's game on the hangar geometry (T18)

| Clip | Guard v Strike | This game | Row's Strike reach (of 1,000) | Size |
|---|---|---|---|---|
| [`ApfGuard_vs_ApfStrike_strike_win.mp4`](phase4/row_1/ApfGuard_vs_ApfStrike_strike_win.mp4) | ApfGuard v ApfStrike | game 1: Strike team reaches the zone at 15.6 s; closest Guard–Strike in the horizontal plane 1.20 m | 999 | 33 kB |
| [`ApfGuard_vs_P3S_strike_win.mp4`](phase4/row_1/ApfGuard_vs_P3S_strike_win.mp4) | ApfGuard v P3S | game 1: Strike team reaches the zone at 7.8 s; closest Guard–Strike in the horizontal plane 1.20 m | 1000 | 30 kB |
| [`ApfGuard_vs_S20_strike_win.mp4`](phase4/row_1/ApfGuard_vs_S20_strike_win.mp4) | ApfGuard v S20 | game 1: Strike team reaches the zone at 9.0 s; closest Guard–Strike in the horizontal plane 1.20 m | 1000 | 30 kB |
| [`G19_vs_ApfStrike_hold.mp4`](phase4/row_1/G19_vs_ApfStrike_hold.mp4) | G19 v ApfStrike | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.20 m | 175 | 95 kB |
| [`G19_vs_ApfStrike_strike_win.mp4`](phase4/row_1/G19_vs_ApfStrike_strike_win.mp4) | G19 v ApfStrike | game 12: Strike team reaches the zone at 6.0 s; closest Guard–Strike in the horizontal plane 1.20 m | 175 | 26 kB |
| [`G19_vs_P3S_strike_win.mp4`](phase4/row_1/G19_vs_P3S_strike_win.mp4) | G19 v P3S | game 1: Strike team reaches the zone at 28.2 s; closest Guard–Strike in the horizontal plane 1.20 m | 971 | 45 kB |
| [`G19_vs_S20_hold.mp4`](phase4/row_1/G19_vs_S20_hold.mp4) | G19 v S20 | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.20 m | 9 | 89 kB |
| [`P3G_vs_ApfStrike_hold.mp4`](phase4/row_1/P3G_vs_ApfStrike_hold.mp4) | P3G v ApfStrike | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.20 m | 33 | 87 kB |
| [`P3G_vs_ApfStrike_strike_win.mp4`](phase4/row_1/P3G_vs_ApfStrike_strike_win.mp4) | P3G v ApfStrike | game 8: Strike team reaches the zone at 3.6 s; closest Guard–Strike in the horizontal plane 1.20 m | 33 | 25 kB |
| [`P3G_vs_P3S_strike_win.mp4`](phase4/row_1/P3G_vs_P3S_strike_win.mp4) | P3G v P3S | game 1: Strike team reaches the zone at 19.2 s; closest Guard–Strike in the horizontal plane 1.20 m | 993 | 36 kB |
| [`P3G_vs_S20_strike_win.mp4`](phase4/row_1/P3G_vs_S20_strike_win.mp4) | P3G v S20 | game 1: Strike team reaches the zone at 18.6 s; closest Guard–Strike in the horizontal plane 1.20 m | 985 | 32 kB |
| [`ParkedGuard_vs_ApfStrike_strike_win.mp4`](phase4/row_1/ParkedGuard_vs_ApfStrike_strike_win.mp4) | ParkedGuard v ApfStrike | game 1: Strike team reaches the zone at 3.6 s; closest Guard–Strike in the horizontal plane 1.22 m | 1000 | 24 kB |
| [`ParkedGuard_vs_P3S_strike_win.mp4`](phase4/row_1/ParkedGuard_vs_P3S_strike_win.mp4) | ParkedGuard v P3S | game 1: Strike team reaches the zone at 7.8 s; closest Guard–Strike in the horizontal plane 1.20 m | 991 | 26 kB |
| [`ParkedGuard_vs_S20_strike_win.mp4`](phase4/row_1/ParkedGuard_vs_S20_strike_win.mp4) | ParkedGuard v S20 | game 1: Strike team reaches the zone at 4.8 s; closest Guard–Strike in the horizontal plane 1.44 m | 1000 | 23 kB |

#### Row 2.1: our game engine with NUS's push and Guard circle (T19)

| Clip | Guard v Strike | This game | Row's Strike reach (of 1,000) | Size |
|---|---|---|---|---|
| [`ApfGuard_vs_ApfStrike_strike_win.mp4`](phase4/row_2.1/ApfGuard_vs_ApfStrike_strike_win.mp4) | ApfGuard v ApfStrike | game 1: Strike team reaches the zone at 15.1 s; closest Guard–Strike in the horizontal plane 1.20 m | 999 | 32 kB |
| [`ApfGuard_vs_P3S_strike_win.mp4`](phase4/row_2.1/ApfGuard_vs_P3S_strike_win.mp4) | ApfGuard v P3S | game 1: Strike team reaches the zone at 7.2 s; closest Guard–Strike in the horizontal plane 1.20 m | 1000 | 29 kB |
| [`ApfGuard_vs_S20_strike_win.mp4`](phase4/row_2.1/ApfGuard_vs_S20_strike_win.mp4) | ApfGuard v S20 | game 1: Strike team reaches the zone at 8.5 s; closest Guard–Strike in the horizontal plane 1.20 m | 1000 | 30 kB |
| [`G19_vs_ApfStrike_hold.mp4`](phase4/row_2.1/G19_vs_ApfStrike_hold.mp4) | G19 v ApfStrike | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.20 m | 174 | 90 kB |
| [`G19_vs_ApfStrike_strike_win.mp4`](phase4/row_2.1/G19_vs_ApfStrike_strike_win.mp4) | G19 v ApfStrike | game 12: Strike team reaches the zone at 5.5 s; closest Guard–Strike in the horizontal plane 1.20 m | 174 | 25 kB |
| [`G19_vs_P3S_strike_win.mp4`](phase4/row_2.1/G19_vs_P3S_strike_win.mp4) | G19 v P3S | game 1: Strike team reaches the zone at 27.7 s; closest Guard–Strike in the horizontal plane 1.20 m | 970 | 42 kB |
| [`G19_vs_S20_hold.mp4`](phase4/row_2.1/G19_vs_S20_hold.mp4) | G19 v S20 | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.20 m | 9 | 86 kB |
| [`P3G_vs_ApfStrike_hold.mp4`](phase4/row_2.1/P3G_vs_ApfStrike_hold.mp4) | P3G v ApfStrike | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.20 m | 34 | 87 kB |
| [`P3G_vs_ApfStrike_strike_win.mp4`](phase4/row_2.1/P3G_vs_ApfStrike_strike_win.mp4) | P3G v ApfStrike | game 8: Strike team reaches the zone at 3.1 s; closest Guard–Strike in the horizontal plane 1.20 m | 34 | 25 kB |
| [`P3G_vs_P3S_strike_win.mp4`](phase4/row_2.1/P3G_vs_P3S_strike_win.mp4) | P3G v P3S | game 1: Strike team reaches the zone at 18.7 s; closest Guard–Strike in the horizontal plane 1.20 m | 994 | 36 kB |
| [`P3G_vs_S20_strike_win.mp4`](phase4/row_2.1/P3G_vs_S20_strike_win.mp4) | P3G v S20 | game 1: Strike team reaches the zone at 18.1 s; closest Guard–Strike in the horizontal plane 1.20 m | 984 | 31 kB |
| [`ParkedGuard_vs_ApfStrike_strike_win.mp4`](phase4/row_2.1/ParkedGuard_vs_ApfStrike_strike_win.mp4) | ParkedGuard v ApfStrike | game 1: Strike team reaches the zone at 3.1 s; closest Guard–Strike in the horizontal plane 1.22 m | 1000 | 23 kB |
| [`ParkedGuard_vs_P3S_strike_win.mp4`](phase4/row_2.1/ParkedGuard_vs_P3S_strike_win.mp4) | ParkedGuard v P3S | game 1: Strike team reaches the zone at 7.2 s; closest Guard–Strike in the horizontal plane 1.20 m | 991 | 25 kB |
| [`ParkedGuard_vs_S20_strike_win.mp4`](phase4/row_2.1/ParkedGuard_vs_S20_strike_win.mp4) | ParkedGuard v S20 | game 1: Strike team reaches the zone at 4.2 s; closest Guard–Strike in the horizontal plane 1.44 m | 1000 | 24 kB |

#### Row 2.2: square walls instead of the Guard circle (T19)

| Clip | Guard v Strike | This game | Row's Strike reach (of 1,000) | Size |
|---|---|---|---|---|
| [`ApfGuard_vs_ApfStrike_strike_win.mp4`](phase4/row_2.2/ApfGuard_vs_ApfStrike_strike_win.mp4) | ApfGuard v ApfStrike | game 1: Strike team reaches the zone at 15.1 s; closest Guard–Strike in the horizontal plane 1.20 m | 1000 | 32 kB |
| [`ApfGuard_vs_P3S_strike_win.mp4`](phase4/row_2.2/ApfGuard_vs_P3S_strike_win.mp4) | ApfGuard v P3S | game 1: Strike team reaches the zone at 7.2 s; closest Guard–Strike in the horizontal plane 1.20 m | 1000 | 29 kB |
| [`ApfGuard_vs_S20_strike_win.mp4`](phase4/row_2.2/ApfGuard_vs_S20_strike_win.mp4) | ApfGuard v S20 | game 1: Strike team reaches the zone at 8.5 s; closest Guard–Strike in the horizontal plane 1.20 m | 1000 | 30 kB |
| [`G19_vs_ApfStrike_hold.mp4`](phase4/row_2.2/G19_vs_ApfStrike_hold.mp4) | G19 v ApfStrike | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.20 m | 174 | 90 kB |
| [`G19_vs_ApfStrike_strike_win.mp4`](phase4/row_2.2/G19_vs_ApfStrike_strike_win.mp4) | G19 v ApfStrike | game 12: Strike team reaches the zone at 5.5 s; closest Guard–Strike in the horizontal plane 1.20 m | 174 | 26 kB |
| [`G19_vs_P3S_strike_win.mp4`](phase4/row_2.2/G19_vs_P3S_strike_win.mp4) | G19 v P3S | game 1: Strike team reaches the zone at 27.7 s; closest Guard–Strike in the horizontal plane 1.20 m | 970 | 43 kB |
| [`G19_vs_S20_hold.mp4`](phase4/row_2.2/G19_vs_S20_hold.mp4) | G19 v S20 | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.20 m | 7 | 85 kB |
| [`P3G_vs_ApfStrike_hold.mp4`](phase4/row_2.2/P3G_vs_ApfStrike_hold.mp4) | P3G v ApfStrike | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.20 m | 34 | 86 kB |
| [`P3G_vs_ApfStrike_strike_win.mp4`](phase4/row_2.2/P3G_vs_ApfStrike_strike_win.mp4) | P3G v ApfStrike | game 8: Strike team reaches the zone at 3.1 s; closest Guard–Strike in the horizontal plane 1.20 m | 34 | 25 kB |
| [`P3G_vs_P3S_strike_win.mp4`](phase4/row_2.2/P3G_vs_P3S_strike_win.mp4) | P3G v P3S | game 1: Strike team reaches the zone at 18.7 s; closest Guard–Strike in the horizontal plane 1.20 m | 994 | 35 kB |
| [`P3G_vs_S20_hold.mp4`](phase4/row_2.2/P3G_vs_S20_hold.mp4) | P3G v S20 | game 6: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.20 m | 863 | 89 kB |
| [`P3G_vs_S20_strike_win.mp4`](phase4/row_2.2/P3G_vs_S20_strike_win.mp4) | P3G v S20 | game 1: Strike team reaches the zone at 39.7 s; closest Guard–Strike in the horizontal plane 1.20 m | 863 | 40 kB |
| [`ParkedGuard_vs_ApfStrike_strike_win.mp4`](phase4/row_2.2/ParkedGuard_vs_ApfStrike_strike_win.mp4) | ParkedGuard v ApfStrike | game 1: Strike team reaches the zone at 3.1 s; closest Guard–Strike in the horizontal plane 1.22 m | 1000 | 23 kB |
| [`ParkedGuard_vs_P3S_strike_win.mp4`](phase4/row_2.2/ParkedGuard_vs_P3S_strike_win.mp4) | ParkedGuard v P3S | game 1: Strike team reaches the zone at 7.2 s; closest Guard–Strike in the horizontal plane 1.20 m | 991 | 25 kB |
| [`ParkedGuard_vs_S20_strike_win.mp4`](phase4/row_2.2/ParkedGuard_vs_S20_strike_win.mp4) | ParkedGuard v S20 | game 1: Strike team reaches the zone at 4.2 s; closest Guard–Strike in the horizontal plane 1.47 m | 1000 | 24 kB |

#### Row 2: our push-apart instead of NUS's push; each action held for 12 ticks (T19)

| Clip | Guard v Strike | This game | Row's Strike reach (of 1,000) | Size |
|---|---|---|---|---|
| [`ApfGuard_vs_ApfStrike_hold.mp4`](phase4/row_2/ApfGuard_vs_ApfStrike_hold.mp4) | ApfGuard v ApfStrike | game 9: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.00 m | 919 | 70 kB |
| [`ApfGuard_vs_ApfStrike_strike_win.mp4`](phase4/row_2/ApfGuard_vs_ApfStrike_strike_win.mp4) | ApfGuard v ApfStrike | game 1: Strike team reaches the zone at 17.6 s; closest Guard–Strike in the horizontal plane 0.99 m | 919 | 35 kB |
| [`ApfGuard_vs_P3S_strike_win.mp4`](phase4/row_2/ApfGuard_vs_P3S_strike_win.mp4) | ApfGuard v P3S | game 1: Strike team reaches the zone at 8.8 s; closest Guard–Strike in the horizontal plane 1.18 m | 1000 | 31 kB |
| [`ApfGuard_vs_S20_strike_win.mp4`](phase4/row_2/ApfGuard_vs_S20_strike_win.mp4) | ApfGuard v S20 | game 1: Strike team reaches the zone at 10.4 s; closest Guard–Strike in the horizontal plane 1.04 m | 1000 | 32 kB |
| [`G19_vs_ApfStrike_hold.mp4`](phase4/row_2/G19_vs_ApfStrike_hold.mp4) | G19 v ApfStrike | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.19 m | 211 | 86 kB |
| [`G19_vs_ApfStrike_strike_win.mp4`](phase4/row_2/G19_vs_ApfStrike_strike_win.mp4) | G19 v ApfStrike | game 10: Strike team reaches the zone at 3.2 s; closest Guard–Strike in the horizontal plane 1.18 m | 211 | 24 kB |
| [`G19_vs_P3S_strike_win.mp4`](phase4/row_2/G19_vs_P3S_strike_win.mp4) | G19 v P3S | game 1: Strike team reaches the zone at 29.6 s; closest Guard–Strike in the horizontal plane 1.19 m | 980 | 46 kB |
| [`G19_vs_S20_hold.mp4`](phase4/row_2/G19_vs_S20_hold.mp4) | G19 v S20 | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.20 m | 17 | 84 kB |
| [`G19_vs_strike_flank_hold.mp4`](phase4/row_2/G19_vs_strike_flank_hold.mp4) | G19 v strike_flank | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.19 m | 40 | 94 kB |
| [`G19_vs_strike_flank_strike_win.mp4`](phase4/row_2/G19_vs_strike_flank_strike_win.mp4) | G19 v strike_flank | game 8: Strike team reaches the zone at 91.8 s; closest Guard–Strike in the horizontal plane 1.19 m | 40 | 84 kB |
| [`G19_vs_strike_straight_hold.mp4`](phase4/row_2/G19_vs_strike_straight_hold.mp4) | G19 v strike_straight | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.19 m | 209 | 86 kB |
| [`G19_vs_strike_straight_strike_win.mp4`](phase4/row_2/G19_vs_strike_straight_strike_win.mp4) | G19 v strike_straight | game 10: Strike team reaches the zone at 3.2 s; closest Guard–Strike in the horizontal plane 1.18 m | 209 | 24 kB |
| [`guard_mark_edge_vs_ApfStrike_hold.mp4`](phase4/row_2/guard_mark_edge_vs_ApfStrike_hold.mp4) | guard_mark_edge v ApfStrike | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.18 m | 48 | 68 kB |
| [`guard_mark_edge_vs_P3S_hold.mp4`](phase4/row_2/guard_mark_edge_vs_P3S_hold.mp4) | guard_mark_edge v P3S | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.18 m | 25 | 129 kB |
| [`guard_mark_edge_vs_S20_hold.mp4`](phase4/row_2/guard_mark_edge_vs_S20_hold.mp4) | guard_mark_edge v S20 | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.18 m | 0 | 132 kB |
| [`guard_mirror_vs_ApfStrike_hold.mp4`](phase4/row_2/guard_mirror_vs_ApfStrike_hold.mp4) | guard_mirror v ApfStrike | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.18 m | 48 | 69 kB |
| [`guard_mirror_vs_P3S_hold.mp4`](phase4/row_2/guard_mirror_vs_P3S_hold.mp4) | guard_mirror v P3S | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.18 m | 25 | 119 kB |
| [`guard_mirror_vs_S20_hold.mp4`](phase4/row_2/guard_mirror_vs_S20_hold.mp4) | guard_mirror v S20 | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.18 m | 1 | 118 kB |
| [`P3G_vs_ApfStrike_hold.mp4`](phase4/row_2/P3G_vs_ApfStrike_hold.mp4) | P3G v ApfStrike | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.19 m | 96 | 82 kB |
| [`P3G_vs_ApfStrike_strike_win.mp4`](phase4/row_2/P3G_vs_ApfStrike_strike_win.mp4) | P3G v ApfStrike | game 8: Strike team reaches the zone at 3.2 s; closest Guard–Strike in the horizontal plane 1.18 m | 96 | 24 kB |
| [`P3G_vs_P3S_strike_win.mp4`](phase4/row_2/P3G_vs_P3S_strike_win.mp4) | P3G v P3S | game 1: Strike team reaches the zone at 19.5 s; closest Guard–Strike in the horizontal plane 1.19 m | 990 | 35 kB |
| [`P3G_vs_S20_hold.mp4`](phase4/row_2/P3G_vs_S20_hold.mp4) | P3G v S20 | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.38 m | 841 | 84 kB |
| [`P3G_vs_S20_strike_win.mp4`](phase4/row_2/P3G_vs_S20_strike_win.mp4) | P3G v S20 | game 2: Strike team reaches the zone at 14.7 s; closest Guard–Strike in the horizontal plane 1.20 m | 841 | 30 kB |
| [`P3G_vs_strike_flank_hold.mp4`](phase4/row_2/P3G_vs_strike_flank_hold.mp4) | P3G v strike_flank | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.19 m | 193 | 106 kB |
| [`P3G_vs_strike_flank_strike_win.mp4`](phase4/row_2/P3G_vs_strike_flank_strike_win.mp4) | P3G v strike_flank | game 4: Strike team reaches the zone at 13.7 s; closest Guard–Strike in the horizontal plane 1.20 m | 193 | 31 kB |
| [`P3G_vs_strike_straight_hold.mp4`](phase4/row_2/P3G_vs_strike_straight_hold.mp4) | P3G v strike_straight | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.19 m | 96 | 85 kB |
| [`P3G_vs_strike_straight_strike_win.mp4`](phase4/row_2/P3G_vs_strike_straight_strike_win.mp4) | P3G v strike_straight | game 8: Strike team reaches the zone at 3.2 s; closest Guard–Strike in the horizontal plane 1.18 m | 96 | 24 kB |
| [`ParkedGuard_vs_ApfStrike_strike_win.mp4`](phase4/row_2/ParkedGuard_vs_ApfStrike_strike_win.mp4) | ParkedGuard v ApfStrike | game 1: Strike team reaches the zone at 3.2 s; closest Guard–Strike in the horizontal plane 1.20 m | 1000 | 24 kB |
| [`ParkedGuard_vs_P3S_strike_win.mp4`](phase4/row_2/ParkedGuard_vs_P3S_strike_win.mp4) | ParkedGuard v P3S | game 1: Strike team reaches the zone at 7.2 s; closest Guard–Strike in the horizontal plane 1.20 m | 991 | 25 kB |
| [`ParkedGuard_vs_S20_strike_win.mp4`](phase4/row_2/ParkedGuard_vs_S20_strike_win.mp4) | ParkedGuard v S20 | game 1: Strike team reaches the zone at 4.5 s; closest Guard–Strike in the horizontal plane 1.59 m | 1000 | 24 kB |
| [`ParkedGuard_vs_strike_flank_hold.mp4`](phase4/row_2/ParkedGuard_vs_strike_flank_hold.mp4) | ParkedGuard v strike_flank | game 2: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.20 m | 879 | 65 kB |
| [`ParkedGuard_vs_strike_flank_strike_win.mp4`](phase4/row_2/ParkedGuard_vs_strike_flank_strike_win.mp4) | ParkedGuard v strike_flank | game 1: Strike team reaches the zone at 3.9 s; closest Guard–Strike in the horizontal plane 1.20 m | 879 | 23 kB |
| [`ParkedGuard_vs_strike_straight_strike_win.mp4`](phase4/row_2/ParkedGuard_vs_strike_straight_strike_win.mp4) | ParkedGuard v strike_straight | game 1: Strike team reaches the zone at 3.2 s; closest Guard–Strike in the horizontal plane 1.20 m | 1000 | 23 kB |

#### Row 3a: control: an identity drone that flies the held command exactly; must equal row 2 (T20)

| Clip | Guard v Strike | This game | Row's Strike reach (of 1,000) | Size |
|---|---|---|---|---|
| [`ApfGuard_vs_ApfStrike_hold.mp4`](phase4/row_3a/ApfGuard_vs_ApfStrike_hold.mp4) | ApfGuard v ApfStrike | game 9: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.00 m | 919 | 71 kB |
| [`ApfGuard_vs_ApfStrike_strike_win.mp4`](phase4/row_3a/ApfGuard_vs_ApfStrike_strike_win.mp4) | ApfGuard v ApfStrike | game 1: Strike team reaches the zone at 17.6 s; closest Guard–Strike in the horizontal plane 0.99 m | 919 | 35 kB |
| [`ApfGuard_vs_P3S_strike_win.mp4`](phase4/row_3a/ApfGuard_vs_P3S_strike_win.mp4) | ApfGuard v P3S | game 1: Strike team reaches the zone at 8.8 s; closest Guard–Strike in the horizontal plane 1.18 m | 1000 | 31 kB |
| [`ApfGuard_vs_S20_strike_win.mp4`](phase4/row_3a/ApfGuard_vs_S20_strike_win.mp4) | ApfGuard v S20 | game 1: Strike team reaches the zone at 10.4 s; closest Guard–Strike in the horizontal plane 1.04 m | 1000 | 31 kB |
| [`G19_vs_ApfStrike_hold.mp4`](phase4/row_3a/G19_vs_ApfStrike_hold.mp4) | G19 v ApfStrike | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.19 m | 211 | 85 kB |
| [`G19_vs_ApfStrike_strike_win.mp4`](phase4/row_3a/G19_vs_ApfStrike_strike_win.mp4) | G19 v ApfStrike | game 10: Strike team reaches the zone at 3.2 s; closest Guard–Strike in the horizontal plane 1.18 m | 211 | 24 kB |
| [`G19_vs_P3S_strike_win.mp4`](phase4/row_3a/G19_vs_P3S_strike_win.mp4) | G19 v P3S | game 1: Strike team reaches the zone at 29.6 s; closest Guard–Strike in the horizontal plane 1.19 m | 980 | 45 kB |
| [`G19_vs_S20_hold.mp4`](phase4/row_3a/G19_vs_S20_hold.mp4) | G19 v S20 | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.20 m | 17 | 84 kB |
| [`G19_vs_strike_flank_hold.mp4`](phase4/row_3a/G19_vs_strike_flank_hold.mp4) | G19 v strike_flank | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.19 m | 40 | 95 kB |
| [`G19_vs_strike_flank_strike_win.mp4`](phase4/row_3a/G19_vs_strike_flank_strike_win.mp4) | G19 v strike_flank | game 8: Strike team reaches the zone at 91.8 s; closest Guard–Strike in the horizontal plane 1.19 m | 40 | 84 kB |
| [`G19_vs_strike_straight_hold.mp4`](phase4/row_3a/G19_vs_strike_straight_hold.mp4) | G19 v strike_straight | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.19 m | 209 | 86 kB |
| [`G19_vs_strike_straight_strike_win.mp4`](phase4/row_3a/G19_vs_strike_straight_strike_win.mp4) | G19 v strike_straight | game 10: Strike team reaches the zone at 3.2 s; closest Guard–Strike in the horizontal plane 1.18 m | 209 | 24 kB |
| [`guard_mark_edge_vs_ApfStrike_hold.mp4`](phase4/row_3a/guard_mark_edge_vs_ApfStrike_hold.mp4) | guard_mark_edge v ApfStrike | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.18 m | 48 | 69 kB |
| [`guard_mark_edge_vs_P3S_hold.mp4`](phase4/row_3a/guard_mark_edge_vs_P3S_hold.mp4) | guard_mark_edge v P3S | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.18 m | 25 | 128 kB |
| [`guard_mark_edge_vs_S20_hold.mp4`](phase4/row_3a/guard_mark_edge_vs_S20_hold.mp4) | guard_mark_edge v S20 | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.18 m | 0 | 132 kB |
| [`guard_mirror_vs_ApfStrike_hold.mp4`](phase4/row_3a/guard_mirror_vs_ApfStrike_hold.mp4) | guard_mirror v ApfStrike | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.18 m | 48 | 70 kB |
| [`guard_mirror_vs_P3S_hold.mp4`](phase4/row_3a/guard_mirror_vs_P3S_hold.mp4) | guard_mirror v P3S | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.18 m | 25 | 119 kB |
| [`guard_mirror_vs_S20_hold.mp4`](phase4/row_3a/guard_mirror_vs_S20_hold.mp4) | guard_mirror v S20 | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.18 m | 1 | 120 kB |
| [`P3G_vs_ApfStrike_hold.mp4`](phase4/row_3a/P3G_vs_ApfStrike_hold.mp4) | P3G v ApfStrike | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.19 m | 96 | 82 kB |
| [`P3G_vs_ApfStrike_strike_win.mp4`](phase4/row_3a/P3G_vs_ApfStrike_strike_win.mp4) | P3G v ApfStrike | game 8: Strike team reaches the zone at 3.2 s; closest Guard–Strike in the horizontal plane 1.18 m | 96 | 24 kB |
| [`P3G_vs_P3S_strike_win.mp4`](phase4/row_3a/P3G_vs_P3S_strike_win.mp4) | P3G v P3S | game 1: Strike team reaches the zone at 19.5 s; closest Guard–Strike in the horizontal plane 1.19 m | 990 | 35 kB |
| [`P3G_vs_S20_hold.mp4`](phase4/row_3a/P3G_vs_S20_hold.mp4) | P3G v S20 | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.38 m | 841 | 85 kB |
| [`P3G_vs_S20_strike_win.mp4`](phase4/row_3a/P3G_vs_S20_strike_win.mp4) | P3G v S20 | game 2: Strike team reaches the zone at 14.7 s; closest Guard–Strike in the horizontal plane 1.20 m | 841 | 30 kB |
| [`P3G_vs_strike_flank_hold.mp4`](phase4/row_3a/P3G_vs_strike_flank_hold.mp4) | P3G v strike_flank | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.19 m | 193 | 106 kB |
| [`P3G_vs_strike_flank_strike_win.mp4`](phase4/row_3a/P3G_vs_strike_flank_strike_win.mp4) | P3G v strike_flank | game 4: Strike team reaches the zone at 13.7 s; closest Guard–Strike in the horizontal plane 1.20 m | 193 | 32 kB |
| [`P3G_vs_strike_straight_hold.mp4`](phase4/row_3a/P3G_vs_strike_straight_hold.mp4) | P3G v strike_straight | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.19 m | 96 | 85 kB |
| [`P3G_vs_strike_straight_strike_win.mp4`](phase4/row_3a/P3G_vs_strike_straight_strike_win.mp4) | P3G v strike_straight | game 8: Strike team reaches the zone at 3.2 s; closest Guard–Strike in the horizontal plane 1.18 m | 96 | 24 kB |
| [`ParkedGuard_vs_ApfStrike_strike_win.mp4`](phase4/row_3a/ParkedGuard_vs_ApfStrike_strike_win.mp4) | ParkedGuard v ApfStrike | game 1: Strike team reaches the zone at 3.2 s; closest Guard–Strike in the horizontal plane 1.20 m | 1000 | 23 kB |
| [`ParkedGuard_vs_P3S_strike_win.mp4`](phase4/row_3a/ParkedGuard_vs_P3S_strike_win.mp4) | ParkedGuard v P3S | game 1: Strike team reaches the zone at 7.2 s; closest Guard–Strike in the horizontal plane 1.20 m | 991 | 25 kB |
| [`ParkedGuard_vs_S20_strike_win.mp4`](phase4/row_3a/ParkedGuard_vs_S20_strike_win.mp4) | ParkedGuard v S20 | game 1: Strike team reaches the zone at 4.5 s; closest Guard–Strike in the horizontal plane 1.59 m | 1000 | 24 kB |
| [`ParkedGuard_vs_strike_flank_hold.mp4`](phase4/row_3a/ParkedGuard_vs_strike_flank_hold.mp4) | ParkedGuard v strike_flank | game 2: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.20 m | 879 | 65 kB |
| [`ParkedGuard_vs_strike_flank_strike_win.mp4`](phase4/row_3a/ParkedGuard_vs_strike_flank_strike_win.mp4) | ParkedGuard v strike_flank | game 1: Strike team reaches the zone at 3.9 s; closest Guard–Strike in the horizontal plane 1.20 m | 879 | 23 kB |
| [`ParkedGuard_vs_strike_straight_strike_win.mp4`](phase4/row_3a/ParkedGuard_vs_strike_straight_strike_win.mp4) | ParkedGuard v strike_straight | game 1: Strike team reaches the zone at 3.2 s; closest Guard–Strike in the horizontal plane 1.20 m | 1000 | 24 kB |

#### Row 3: the drone response: commander copy, delay and lag of the exploratory fitted model; filter off (T20)

| Clip | Guard v Strike | This game | Row's Strike reach (of 1,000) | Size |
|---|---|---|---|---|
| [`ApfGuard_vs_ApfStrike_hold.mp4`](phase4/row_3/ApfGuard_vs_ApfStrike_hold.mp4) | ApfGuard v ApfStrike | game 11: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.00 m | 894 | 79 kB |
| [`ApfGuard_vs_ApfStrike_strike_win.mp4`](phase4/row_3/ApfGuard_vs_ApfStrike_strike_win.mp4) | ApfGuard v ApfStrike | game 1: Strike team reaches the zone at 13.6 s; closest Guard–Strike in the horizontal plane 0.99 m | 894 | 34 kB |
| [`ApfGuard_vs_P3S_strike_win.mp4`](phase4/row_3/ApfGuard_vs_P3S_strike_win.mp4) | ApfGuard v P3S | game 1: Strike team reaches the zone at 6.4 s; closest Guard–Strike in the horizontal plane 1.18 m | 1000 | 28 kB |
| [`ApfGuard_vs_S20_strike_win.mp4`](phase4/row_3/ApfGuard_vs_S20_strike_win.mp4) | ApfGuard v S20 | game 1: Strike team reaches the zone at 7.9 s; closest Guard–Strike in the horizontal plane 1.18 m | 1000 | 30 kB |
| [`G19_vs_ApfStrike_hold.mp4`](phase4/row_3/G19_vs_ApfStrike_hold.mp4) | G19 v ApfStrike | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.19 m | 408 | 85 kB |
| [`G19_vs_ApfStrike_strike_win.mp4`](phase4/row_3/G19_vs_ApfStrike_strike_win.mp4) | G19 v ApfStrike | game 10: Strike team reaches the zone at 3.7 s; closest Guard–Strike in the horizontal plane 1.18 m | 408 | 24 kB |
| [`G19_vs_P3S_strike_win.mp4`](phase4/row_3/G19_vs_P3S_strike_win.mp4) | G19 v P3S | game 1: Strike team reaches the zone at 11.9 s; closest Guard–Strike in the horizontal plane 1.18 m | 1000 | 31 kB |
| [`G19_vs_S20_hold.mp4`](phase4/row_3/G19_vs_S20_hold.mp4) | G19 v S20 | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.20 m | 43 | 89 kB |
| [`G19_vs_strike_flank_hold.mp4`](phase4/row_3/G19_vs_strike_flank_hold.mp4) | G19 v strike_flank | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.19 m | 54 | 97 kB |
| [`G19_vs_strike_flank_strike_win.mp4`](phase4/row_3/G19_vs_strike_flank_strike_win.mp4) | G19 v strike_flank | game 2: Strike team reaches the zone at 4.9 s; closest Guard–Strike in the horizontal plane 1.20 m | 54 | 25 kB |
| [`G19_vs_strike_straight_hold.mp4`](phase4/row_3/G19_vs_strike_straight_hold.mp4) | G19 v strike_straight | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.19 m | 385 | 85 kB |
| [`G19_vs_strike_straight_strike_win.mp4`](phase4/row_3/G19_vs_strike_straight_strike_win.mp4) | G19 v strike_straight | game 10: Strike team reaches the zone at 3.7 s; closest Guard–Strike in the horizontal plane 1.18 m | 385 | 24 kB |
| [`guard_mark_edge_vs_ApfStrike_hold.mp4`](phase4/row_3/guard_mark_edge_vs_ApfStrike_hold.mp4) | guard_mark_edge v ApfStrike | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.18 m | 38 | 72 kB |
| [`guard_mark_edge_vs_P3S_strike_win.mp4`](phase4/row_3/guard_mark_edge_vs_P3S_strike_win.mp4) | guard_mark_edge v P3S | game 1: Strike team reaches the zone at 22.0 s; closest Guard–Strike in the horizontal plane 1.18 m | 999 | 40 kB |
| [`guard_mark_edge_vs_S20_strike_win.mp4`](phase4/row_3/guard_mark_edge_vs_S20_strike_win.mp4) | guard_mark_edge v S20 | game 1: Strike team reaches the zone at 10.8 s; closest Guard–Strike in the horizontal plane 1.18 m | 1000 | 31 kB |
| [`guard_mirror_vs_ApfStrike_hold.mp4`](phase4/row_3/guard_mirror_vs_ApfStrike_hold.mp4) | guard_mirror v ApfStrike | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.18 m | 39 | 69 kB |
| [`guard_mirror_vs_P3S_hold.mp4`](phase4/row_3/guard_mirror_vs_P3S_hold.mp4) | guard_mirror v P3S | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.18 m | 80 | 120 kB |
| [`guard_mirror_vs_P3S_strike_win.mp4`](phase4/row_3/guard_mirror_vs_P3S_strike_win.mp4) | guard_mirror v P3S | game 15: Strike team reaches the zone at 19.8 s; closest Guard–Strike in the horizontal plane 1.18 m | 80 | 39 kB |
| [`guard_mirror_vs_S20_hold.mp4`](phase4/row_3/guard_mirror_vs_S20_hold.mp4) | guard_mirror v S20 | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.18 m | 69 | 124 kB |
| [`guard_mirror_vs_S20_strike_win.mp4`](phase4/row_3/guard_mirror_vs_S20_strike_win.mp4) | guard_mirror v S20 | game 7: Strike team reaches the zone at 20.2 s; closest Guard–Strike in the horizontal plane 1.18 m | 69 | 39 kB |
| [`P3G_vs_ApfStrike_hold.mp4`](phase4/row_3/P3G_vs_ApfStrike_hold.mp4) | P3G v ApfStrike | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.19 m | 294 | 84 kB |
| [`P3G_vs_ApfStrike_strike_win.mp4`](phase4/row_3/P3G_vs_ApfStrike_strike_win.mp4) | P3G v ApfStrike | game 3: Strike team reaches the zone at 8.2 s; closest Guard–Strike in the horizontal plane 1.18 m | 294 | 27 kB |
| [`P3G_vs_P3S_strike_win.mp4`](phase4/row_3/P3G_vs_P3S_strike_win.mp4) | P3G v P3S | game 1: Strike team reaches the zone at 20.9 s; closest Guard–Strike in the horizontal plane 1.18 m | 1000 | 40 kB |
| [`P3G_vs_S20_hold.mp4`](phase4/row_3/P3G_vs_S20_hold.mp4) | P3G v S20 | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.37 m | 926 | 86 kB |
| [`P3G_vs_S20_strike_win.mp4`](phase4/row_3/P3G_vs_S20_strike_win.mp4) | P3G v S20 | game 2: Strike team reaches the zone at 15.4 s; closest Guard–Strike in the horizontal plane 1.19 m | 926 | 32 kB |
| [`P3G_vs_strike_flank_hold.mp4`](phase4/row_3/P3G_vs_strike_flank_hold.mp4) | P3G v strike_flank | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.19 m | 349 | 105 kB |
| [`P3G_vs_strike_flank_strike_win.mp4`](phase4/row_3/P3G_vs_strike_flank_strike_win.mp4) | P3G v strike_flank | game 2: Strike team reaches the zone at 64.0 s; closest Guard–Strike in the horizontal plane 1.18 m | 349 | 66 kB |
| [`P3G_vs_strike_straight_hold.mp4`](phase4/row_3/P3G_vs_strike_straight_hold.mp4) | P3G v strike_straight | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.19 m | 287 | 84 kB |
| [`P3G_vs_strike_straight_strike_win.mp4`](phase4/row_3/P3G_vs_strike_straight_strike_win.mp4) | P3G v strike_straight | game 3: Strike team reaches the zone at 8.5 s; closest Guard–Strike in the horizontal plane 1.18 m | 287 | 28 kB |
| [`ParkedGuard_vs_ApfStrike_strike_win.mp4`](phase4/row_3/ParkedGuard_vs_ApfStrike_strike_win.mp4) | ParkedGuard v ApfStrike | game 1: Strike team reaches the zone at 3.7 s; closest Guard–Strike in the horizontal plane 1.20 m | 1000 | 23 kB |
| [`ParkedGuard_vs_P3S_strike_win.mp4`](phase4/row_3/ParkedGuard_vs_P3S_strike_win.mp4) | ParkedGuard v P3S | game 1: Strike team reaches the zone at 5.5 s; closest Guard–Strike in the horizontal plane 1.20 m | 997 | 25 kB |
| [`ParkedGuard_vs_S20_strike_win.mp4`](phase4/row_3/ParkedGuard_vs_S20_strike_win.mp4) | ParkedGuard v S20 | game 1: Strike team reaches the zone at 4.8 s; closest Guard–Strike in the horizontal plane 1.58 m | 1000 | 24 kB |
| [`ParkedGuard_vs_strike_flank_hold.mp4`](phase4/row_3/ParkedGuard_vs_strike_flank_hold.mp4) | ParkedGuard v strike_flank | game 2: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.20 m | 876 | 77 kB |
| [`ParkedGuard_vs_strike_flank_strike_win.mp4`](phase4/row_3/ParkedGuard_vs_strike_flank_strike_win.mp4) | ParkedGuard v strike_flank | game 1: Strike team reaches the zone at 4.2 s; closest Guard–Strike in the horizontal plane 1.20 m | 876 | 24 kB |
| [`ParkedGuard_vs_strike_straight_strike_win.mp4`](phase4/row_3/ParkedGuard_vs_strike_straight_strike_win.mp4) | ParkedGuard v strike_straight | game 1: Strike team reaches the zone at 3.7 s; closest Guard–Strike in the horizontal plane 1.20 m | 1000 | 23 kB |

#### Row 4: the all-pairs safety filter instead of the push, as in flight (T22)

| Clip | Guard v Strike | This game | Row's Strike reach (of 1,000) | Size |
|---|---|---|---|---|
| [`ApfGuard_vs_ApfStrike_strike_win.mp4`](phase4/row_4/ApfGuard_vs_ApfStrike_strike_win.mp4) | ApfGuard v ApfStrike | game 1: Strike team reaches the zone at 9.6 s; closest Guard–Strike in the horizontal plane 1.06 m | 1000 | 29 kB |
| [`ApfGuard_vs_P3S_strike_win.mp4`](phase4/row_4/ApfGuard_vs_P3S_strike_win.mp4) | ApfGuard v P3S | game 1: Strike team reaches the zone at 7.5 s; closest Guard–Strike in the horizontal plane 1.04 m | 1000 | 28 kB |
| [`ApfGuard_vs_S20_strike_win.mp4`](phase4/row_4/ApfGuard_vs_S20_strike_win.mp4) | ApfGuard v S20 | game 1: Strike team reaches the zone at 8.6 s; closest Guard–Strike in the horizontal plane 1.06 m | 1000 | 29 kB |
| [`G19_vs_ApfStrike_strike_win.mp4`](phase4/row_4/G19_vs_ApfStrike_strike_win.mp4) | G19 v ApfStrike | game 1: Strike team reaches the zone at 4.4 s; closest Guard–Strike in the horizontal plane 1.06 m | 1000 | 25 kB |
| [`G19_vs_P3S_strike_win.mp4`](phase4/row_4/G19_vs_P3S_strike_win.mp4) | G19 v P3S | game 1: Strike team reaches the zone at 5.9 s; closest Guard–Strike in the horizontal plane 1.02 m | 1000 | 26 kB |
| [`G19_vs_S20_hold.mp4`](phase4/row_4/G19_vs_S20_hold.mp4) | G19 v S20 | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.10 m | 740 | 84 kB |
| [`G19_vs_S20_strike_win.mp4`](phase4/row_4/G19_vs_S20_strike_win.mp4) | G19 v S20 | game 2: Strike team reaches the zone at 23.0 s; closest Guard–Strike in the horizontal plane 1.09 m | 740 | 33 kB |
| [`G19_vs_strike_flank_hold.mp4`](phase4/row_4/G19_vs_strike_flank_hold.mp4) | G19 v strike_flank | game 2: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.06 m | 798 | 99 kB |
| [`G19_vs_strike_flank_strike_win.mp4`](phase4/row_4/G19_vs_strike_flank_strike_win.mp4) | G19 v strike_flank | game 1: Strike team reaches the zone at 8.0 s; closest Guard–Strike in the horizontal plane 1.05 m | 798 | 27 kB |
| [`G19_vs_strike_straight_strike_win.mp4`](phase4/row_4/G19_vs_strike_straight_strike_win.mp4) | G19 v strike_straight | game 1: Strike team reaches the zone at 4.5 s; closest Guard–Strike in the horizontal plane 1.05 m | 1000 | 26 kB |
| [`guard_mark_edge_vs_ApfStrike_strike_win.mp4`](phase4/row_4/guard_mark_edge_vs_ApfStrike_strike_win.mp4) | guard_mark_edge v ApfStrike | game 1: Strike team reaches the zone at 3.7 s; closest Guard–Strike in the horizontal plane 1.06 m | 958 | 25 kB |
| [`guard_mark_edge_vs_P3S_strike_win.mp4`](phase4/row_4/guard_mark_edge_vs_P3S_strike_win.mp4) | guard_mark_edge v P3S | game 1: Strike team reaches the zone at 5.1 s; closest Guard–Strike in the horizontal plane 1.05 m | 1000 | 26 kB |
| [`guard_mark_edge_vs_S20_strike_win.mp4`](phase4/row_4/guard_mark_edge_vs_S20_strike_win.mp4) | guard_mark_edge v S20 | game 1: Strike team reaches the zone at 13.2 s; closest Guard–Strike in the horizontal plane 1.10 m | 994 | 32 kB |
| [`guard_mirror_vs_ApfStrike_hold.mp4`](phase4/row_4/guard_mirror_vs_ApfStrike_hold.mp4) | guard_mirror v ApfStrike | game 2: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.03 m | 960 | 77 kB |
| [`guard_mirror_vs_ApfStrike_strike_win.mp4`](phase4/row_4/guard_mirror_vs_ApfStrike_strike_win.mp4) | guard_mirror v ApfStrike | game 1: Strike team reaches the zone at 3.7 s; closest Guard–Strike in the horizontal plane 1.06 m | 960 | 25 kB |
| [`guard_mirror_vs_P3S_hold.mp4`](phase4/row_4/guard_mirror_vs_P3S_hold.mp4) | guard_mirror v P3S | game 2: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.06 m | 980 | 125 kB |
| [`guard_mirror_vs_P3S_strike_win.mp4`](phase4/row_4/guard_mirror_vs_P3S_strike_win.mp4) | guard_mirror v P3S | game 1: Strike team reaches the zone at 5.1 s; closest Guard–Strike in the horizontal plane 1.04 m | 980 | 26 kB |
| [`guard_mirror_vs_S20_hold.mp4`](phase4/row_4/guard_mirror_vs_S20_hold.mp4) | guard_mirror v S20 | game 2: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.05 m | 856 | 120 kB |
| [`guard_mirror_vs_S20_strike_win.mp4`](phase4/row_4/guard_mirror_vs_S20_strike_win.mp4) | guard_mirror v S20 | game 1: Strike team reaches the zone at 8.6 s; closest Guard–Strike in the horizontal plane 1.08 m | 856 | 29 kB |
| [`P3G_vs_ApfStrike_strike_win.mp4`](phase4/row_4/P3G_vs_ApfStrike_strike_win.mp4) | P3G v ApfStrike | game 1: Strike team reaches the zone at 4.2 s; closest Guard–Strike in the horizontal plane 1.06 m | 1000 | 25 kB |
| [`P3G_vs_P3S_strike_win.mp4`](phase4/row_4/P3G_vs_P3S_strike_win.mp4) | P3G v P3S | game 1: Strike team reaches the zone at 22.9 s; closest Guard–Strike in the horizontal plane 1.04 m | 1000 | 38 kB |
| [`P3G_vs_S20_hold.mp4`](phase4/row_4/P3G_vs_S20_hold.mp4) | P3G v S20 | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.53 m | 908 | 88 kB |
| [`P3G_vs_S20_strike_win.mp4`](phase4/row_4/P3G_vs_S20_strike_win.mp4) | P3G v S20 | game 2: Strike team reaches the zone at 17.4 s; closest Guard–Strike in the horizontal plane 1.08 m | 908 | 31 kB |
| [`P3G_vs_strike_flank_hold.mp4`](phase4/row_4/P3G_vs_strike_flank_hold.mp4) | P3G v strike_flank | game 6: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.01 m | 978 | 111 kB |
| [`P3G_vs_strike_flank_strike_win.mp4`](phase4/row_4/P3G_vs_strike_flank_strike_win.mp4) | P3G v strike_flank | game 1: Strike team reaches the zone at 14.5 s; closest Guard–Strike in the horizontal plane 1.02 m | 978 | 32 kB |
| [`P3G_vs_strike_straight_strike_win.mp4`](phase4/row_4/P3G_vs_strike_straight_strike_win.mp4) | P3G v strike_straight | game 1: Strike team reaches the zone at 4.3 s; closest Guard–Strike in the horizontal plane 1.05 m | 1000 | 25 kB |
| [`ParkedGuard_vs_ApfStrike_strike_win.mp4`](phase4/row_4/ParkedGuard_vs_ApfStrike_strike_win.mp4) | ParkedGuard v ApfStrike | game 1: Strike team reaches the zone at 3.7 s; closest Guard–Strike in the horizontal plane 0.99 m | 1000 | 25 kB |
| [`ParkedGuard_vs_P3S_strike_win.mp4`](phase4/row_4/ParkedGuard_vs_P3S_strike_win.mp4) | ParkedGuard v P3S | game 1: Strike team reaches the zone at 5.4 s; closest Guard–Strike in the horizontal plane 1.04 m | 1000 | 26 kB |
| [`ParkedGuard_vs_S20_hold.mp4`](phase4/row_4/ParkedGuard_vs_S20_hold.mp4) | ParkedGuard v S20 | game 2: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.44 m | 556 | 72 kB |
| [`ParkedGuard_vs_S20_strike_win.mp4`](phase4/row_4/ParkedGuard_vs_S20_strike_win.mp4) | ParkedGuard v S20 | game 1: Strike team reaches the zone at 34.4 s; closest Guard–Strike in the horizontal plane 1.10 m | 556 | 36 kB |
| [`ParkedGuard_vs_strike_flank_hold.mp4`](phase4/row_4/ParkedGuard_vs_strike_flank_hold.mp4) | ParkedGuard v strike_flank | game 7: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.06 m | 945 | 85 kB |
| [`ParkedGuard_vs_strike_flank_strike_win.mp4`](phase4/row_4/ParkedGuard_vs_strike_flank_strike_win.mp4) | ParkedGuard v strike_flank | game 1: Strike team reaches the zone at 5.4 s; closest Guard–Strike in the horizontal plane 1.04 m | 945 | 27 kB |
| [`ParkedGuard_vs_strike_straight_strike_win.mp4`](phase4/row_4/ParkedGuard_vs_strike_straight_strike_win.mp4) | ParkedGuard v strike_straight | game 1: Strike team reaches the zone at 3.7 s; closest Guard–Strike in the horizontal plane 1.02 m | 1000 | 25 kB |

#### Row 5a: control: drones free in height, no start jitter; must equal row 4 (12 core pairs only) (T23)

| Clip | Guard v Strike | This game | Row's Strike reach (of 1,000) | Size |
|---|---|---|---|---|
| [`ApfGuard_vs_ApfStrike_strike_win.mp4`](phase4/row_5a/ApfGuard_vs_ApfStrike_strike_win.mp4) | ApfGuard v ApfStrike | game 1: Strike team reaches the zone at 9.6 s; closest Guard–Strike in the horizontal plane 1.06 m | 1000 | 29 kB |
| [`ApfGuard_vs_P3S_strike_win.mp4`](phase4/row_5a/ApfGuard_vs_P3S_strike_win.mp4) | ApfGuard v P3S | game 1: Strike team reaches the zone at 7.5 s; closest Guard–Strike in the horizontal plane 1.04 m | 1000 | 28 kB |
| [`ApfGuard_vs_S20_strike_win.mp4`](phase4/row_5a/ApfGuard_vs_S20_strike_win.mp4) | ApfGuard v S20 | game 1: Strike team reaches the zone at 8.6 s; closest Guard–Strike in the horizontal plane 1.06 m | 1000 | 28 kB |
| [`G19_vs_ApfStrike_strike_win.mp4`](phase4/row_5a/G19_vs_ApfStrike_strike_win.mp4) | G19 v ApfStrike | game 1: Strike team reaches the zone at 4.4 s; closest Guard–Strike in the horizontal plane 1.06 m | 1000 | 25 kB |
| [`G19_vs_P3S_strike_win.mp4`](phase4/row_5a/G19_vs_P3S_strike_win.mp4) | G19 v P3S | game 1: Strike team reaches the zone at 5.9 s; closest Guard–Strike in the horizontal plane 1.02 m | 1000 | 26 kB |
| [`G19_vs_S20_hold.mp4`](phase4/row_5a/G19_vs_S20_hold.mp4) | G19 v S20 | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.10 m | 740 | 85 kB |
| [`G19_vs_S20_strike_win.mp4`](phase4/row_5a/G19_vs_S20_strike_win.mp4) | G19 v S20 | game 2: Strike team reaches the zone at 23.0 s; closest Guard–Strike in the horizontal plane 1.09 m | 740 | 33 kB |
| [`P3G_vs_ApfStrike_strike_win.mp4`](phase4/row_5a/P3G_vs_ApfStrike_strike_win.mp4) | P3G v ApfStrike | game 1: Strike team reaches the zone at 4.2 s; closest Guard–Strike in the horizontal plane 1.06 m | 1000 | 25 kB |
| [`P3G_vs_P3S_strike_win.mp4`](phase4/row_5a/P3G_vs_P3S_strike_win.mp4) | P3G v P3S | game 1: Strike team reaches the zone at 22.9 s; closest Guard–Strike in the horizontal plane 1.04 m | 1000 | 39 kB |
| [`P3G_vs_S20_hold.mp4`](phase4/row_5a/P3G_vs_S20_hold.mp4) | P3G v S20 | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.53 m | 908 | 88 kB |
| [`P3G_vs_S20_strike_win.mp4`](phase4/row_5a/P3G_vs_S20_strike_win.mp4) | P3G v S20 | game 2: Strike team reaches the zone at 17.4 s; closest Guard–Strike in the horizontal plane 1.08 m | 908 | 31 kB |
| [`ParkedGuard_vs_ApfStrike_strike_win.mp4`](phase4/row_5a/ParkedGuard_vs_ApfStrike_strike_win.mp4) | ParkedGuard v ApfStrike | game 1: Strike team reaches the zone at 3.7 s; closest Guard–Strike in the horizontal plane 0.99 m | 1000 | 25 kB |
| [`ParkedGuard_vs_P3S_strike_win.mp4`](phase4/row_5a/ParkedGuard_vs_P3S_strike_win.mp4) | ParkedGuard v P3S | game 1: Strike team reaches the zone at 5.4 s; closest Guard–Strike in the horizontal plane 1.04 m | 1000 | 26 kB |
| [`ParkedGuard_vs_S20_hold.mp4`](phase4/row_5a/ParkedGuard_vs_S20_hold.mp4) | ParkedGuard v S20 | game 2: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.44 m | 556 | 72 kB |
| [`ParkedGuard_vs_S20_strike_win.mp4`](phase4/row_5a/ParkedGuard_vs_S20_strike_win.mp4) | ParkedGuard v S20 | game 1: Strike team reaches the zone at 34.4 s; closest Guard–Strike in the horizontal plane 1.10 m | 556 | 36 kB |

#### Row 5: drones free in height with a ±1 mm start-height jitter (T23)

| Clip | Guard v Strike | This game | Row's Strike reach (of 1,000) | Size |
|---|---|---|---|---|
| [`ApfGuard_vs_ApfStrike_strike_win.mp4`](phase4/row_5/ApfGuard_vs_ApfStrike_strike_win.mp4) | ApfGuard v ApfStrike | game 1: Strike team reaches the zone at 9.3 s; closest Guard–Strike in the horizontal plane 1.02 m | 1000 | 29 kB |
| [`ApfGuard_vs_P3S_strike_win.mp4`](phase4/row_5/ApfGuard_vs_P3S_strike_win.mp4) | ApfGuard v P3S | game 1: Strike team reaches the zone at 7.5 s; closest Guard–Strike in the horizontal plane 1.04 m | 1000 | 28 kB |
| [`ApfGuard_vs_S20_strike_win.mp4`](phase4/row_5/ApfGuard_vs_S20_strike_win.mp4) | ApfGuard v S20 | game 1: Strike team reaches the zone at 8.6 s; closest Guard–Strike in the horizontal plane 1.06 m | 1000 | 29 kB |
| [`G19_vs_ApfStrike_strike_win.mp4`](phase4/row_5/G19_vs_ApfStrike_strike_win.mp4) | G19 v ApfStrike | game 1: Strike team reaches the zone at 4.4 s; closest Guard–Strike in the horizontal plane 1.05 m | 1000 | 25 kB |
| [`G19_vs_P3S_strike_win.mp4`](phase4/row_5/G19_vs_P3S_strike_win.mp4) | G19 v P3S | game 1: Strike team reaches the zone at 5.9 s; closest Guard–Strike in the horizontal plane 1.02 m | 1000 | 26 kB |
| [`G19_vs_S20_strike_win.mp4`](phase4/row_5/G19_vs_S20_strike_win.mp4) | G19 v S20 | game 1: Strike team reaches the zone at 22.9 s; closest Guard–Strike in the horizontal plane 1.00 m | 983 | 33 kB |
| [`G19_vs_strike_flank_strike_win.mp4`](phase4/row_5/G19_vs_strike_flank_strike_win.mp4) | G19 v strike_flank | game 1: Strike team reaches the zone at 7.9 s; closest Guard–Strike in the horizontal plane 1.05 m | 1000 | 28 kB |
| [`G19_vs_strike_straight_strike_win.mp4`](phase4/row_5/G19_vs_strike_straight_strike_win.mp4) | G19 v strike_straight | game 1: Strike team reaches the zone at 4.5 s; closest Guard–Strike in the horizontal plane 1.05 m | 1000 | 26 kB |
| [`guard_mark_edge_vs_ApfStrike_strike_win.mp4`](phase4/row_5/guard_mark_edge_vs_ApfStrike_strike_win.mp4) | guard_mark_edge v ApfStrike | game 1: Strike team reaches the zone at 3.7 s; closest Guard–Strike in the horizontal plane 1.07 m | 962 | 25 kB |
| [`guard_mark_edge_vs_P3S_strike_win.mp4`](phase4/row_5/guard_mark_edge_vs_P3S_strike_win.mp4) | guard_mark_edge v P3S | game 1: Strike team reaches the zone at 5.1 s; closest Guard–Strike in the horizontal plane 1.05 m | 1000 | 26 kB |
| [`guard_mark_edge_vs_S20_strike_win.mp4`](phase4/row_5/guard_mark_edge_vs_S20_strike_win.mp4) | guard_mark_edge v S20 | game 1: Strike team reaches the zone at 13.0 s; closest Guard–Strike in the horizontal plane 1.07 m | 1000 | 32 kB |
| [`guard_mirror_vs_ApfStrike_hold.mp4`](phase4/row_5/guard_mirror_vs_ApfStrike_hold.mp4) | guard_mirror v ApfStrike | game 2: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 0.46 m | 959 | 77 kB |
| [`guard_mirror_vs_ApfStrike_strike_win.mp4`](phase4/row_5/guard_mirror_vs_ApfStrike_strike_win.mp4) | guard_mirror v ApfStrike | game 1: Strike team reaches the zone at 3.7 s; closest Guard–Strike in the horizontal plane 1.08 m | 959 | 25 kB |
| [`guard_mirror_vs_P3S_strike_win.mp4`](phase4/row_5/guard_mirror_vs_P3S_strike_win.mp4) | guard_mirror v P3S | game 1: Strike team reaches the zone at 5.1 s; closest Guard–Strike in the horizontal plane 1.04 m | 1000 | 26 kB |
| [`guard_mirror_vs_S20_strike_win.mp4`](phase4/row_5/guard_mirror_vs_S20_strike_win.mp4) | guard_mirror v S20 | game 1: Strike team reaches the zone at 8.6 s; closest Guard–Strike in the horizontal plane 1.08 m | 1000 | 29 kB |
| [`P3G_vs_ApfStrike_strike_win.mp4`](phase4/row_5/P3G_vs_ApfStrike_strike_win.mp4) | P3G v ApfStrike | game 1: Strike team reaches the zone at 4.2 s; closest Guard–Strike in the horizontal plane 1.05 m | 1000 | 25 kB |
| [`P3G_vs_P3S_strike_win.mp4`](phase4/row_5/P3G_vs_P3S_strike_win.mp4) | P3G v P3S | game 1: Strike team reaches the zone at 10.4 s; closest Guard–Strike in the horizontal plane 0.91 m | 1000 | 30 kB |
| [`P3G_vs_S20_hold.mp4`](phase4/row_5/P3G_vs_S20_hold.mp4) | P3G v S20 | game 1: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.53 m | 924 | 88 kB |
| [`P3G_vs_S20_strike_win.mp4`](phase4/row_5/P3G_vs_S20_strike_win.mp4) | P3G v S20 | game 2: Strike team reaches the zone at 16.8 s; closest Guard–Strike in the horizontal plane 1.08 m | 924 | 30 kB |
| [`P3G_vs_strike_flank_strike_win.mp4`](phase4/row_5/P3G_vs_strike_flank_strike_win.mp4) | P3G v strike_flank | game 1: Strike team reaches the zone at 11.2 s; closest Guard–Strike in the horizontal plane 0.96 m | 1000 | 30 kB |
| [`P3G_vs_strike_straight_strike_win.mp4`](phase4/row_5/P3G_vs_strike_straight_strike_win.mp4) | P3G v strike_straight | game 1: Strike team reaches the zone at 4.3 s; closest Guard–Strike in the horizontal plane 1.05 m | 1000 | 25 kB |
| [`ParkedGuard_vs_ApfStrike_strike_win.mp4`](phase4/row_5/ParkedGuard_vs_ApfStrike_strike_win.mp4) | ParkedGuard v ApfStrike | game 1: Strike team reaches the zone at 3.7 s; closest Guard–Strike in the horizontal plane 1.05 m | 1000 | 25 kB |
| [`ParkedGuard_vs_P3S_strike_win.mp4`](phase4/row_5/ParkedGuard_vs_P3S_strike_win.mp4) | ParkedGuard v P3S | game 1: Strike team reaches the zone at 4.8 s; closest Guard–Strike in the horizontal plane 1.08 m | 1000 | 25 kB |
| [`ParkedGuard_vs_S20_hold.mp4`](phase4/row_5/ParkedGuard_vs_S20_hold.mp4) | ParkedGuard v S20 | game 2: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.44 m | 571 | 71 kB |
| [`ParkedGuard_vs_S20_strike_win.mp4`](phase4/row_5/ParkedGuard_vs_S20_strike_win.mp4) | ParkedGuard v S20 | game 1: Strike team reaches the zone at 8.3 s; closest Guard–Strike in the horizontal plane 1.51 m | 571 | 26 kB |
| [`ParkedGuard_vs_strike_flank_strike_win.mp4`](phase4/row_5/ParkedGuard_vs_strike_flank_strike_win.mp4) | ParkedGuard v strike_flank | game 1: Strike team reaches the zone at 4.7 s; closest Guard–Strike in the horizontal plane 1.06 m | 1000 | 25 kB |
| [`ParkedGuard_vs_strike_straight_strike_win.mp4`](phase4/row_5/ParkedGuard_vs_strike_straight_strike_win.mp4) | ParkedGuard v strike_straight | game 1: Strike team reaches the zone at 3.7 s; closest Guard–Strike in the horizontal plane 1.04 m | 1000 | 25 kB |

#### Row 6: the physics drone: Isaac Lab rigid-body Starlings, headless (tier 2) (T24)

| Clip | Guard v Strike | This game | Row's Strike reach (of 1,000) | Size |
|---|---|---|---|---|
| [`ApfGuard_vs_ApfStrike_strike_win.mp4`](phase4/row_6/ApfGuard_vs_ApfStrike_strike_win.mp4) | ApfGuard v ApfStrike | game 1: Strike team reaches the zone at 4.8 s; closest Guard–Strike in the horizontal plane 1.05 m | 1000 | 26 kB |
| [`ApfGuard_vs_P3S_strike_win.mp4`](phase4/row_6/ApfGuard_vs_P3S_strike_win.mp4) | ApfGuard v P3S | game 1: Strike team reaches the zone at 7.8 s; closest Guard–Strike in the horizontal plane 1.07 m | 1000 | 28 kB |
| [`ApfGuard_vs_S20_strike_win.mp4`](phase4/row_6/ApfGuard_vs_S20_strike_win.mp4) | ApfGuard v S20 | game 1: Strike team reaches the zone at 7.2 s; closest Guard–Strike in the horizontal plane 1.10 m | 1000 | 28 kB |
| [`G19_vs_ApfStrike_strike_win.mp4`](phase4/row_6/G19_vs_ApfStrike_strike_win.mp4) | G19 v ApfStrike | game 1: Strike team reaches the zone at 4.0 s; closest Guard–Strike in the horizontal plane 1.07 m | 1000 | 25 kB |
| [`G19_vs_P3S_strike_win.mp4`](phase4/row_6/G19_vs_P3S_strike_win.mp4) | G19 v P3S | game 1: Strike team reaches the zone at 7.5 s; closest Guard–Strike in the horizontal plane 1.09 m | 1000 | 27 kB |
| [`G19_vs_S20_strike_win.mp4`](phase4/row_6/G19_vs_S20_strike_win.mp4) | G19 v S20 | game 1: Strike team reaches the zone at 24.5 s; closest Guard–Strike in the horizontal plane 0.97 m | 979 | 33 kB |
| [`G19_vs_strike_flank_strike_win.mp4`](phase4/row_6/G19_vs_strike_flank_strike_win.mp4) | G19 v strike_flank | game 1: Strike team reaches the zone at 7.2 s; closest Guard–Strike in the horizontal plane 1.09 m | 1000 | 27 kB |
| [`G19_vs_strike_straight_strike_win.mp4`](phase4/row_6/G19_vs_strike_straight_strike_win.mp4) | G19 v strike_straight | game 1: Strike team reaches the zone at 4.1 s; closest Guard–Strike in the horizontal plane 1.07 m | 1000 | 26 kB |
| [`guard_mark_edge_vs_ApfStrike_hold.mp4`](phase4/row_6/guard_mark_edge_vs_ApfStrike_hold.mp4) | guard_mark_edge v ApfStrike | game 2: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 0.64 m | 945 | 84 kB |
| [`guard_mark_edge_vs_ApfStrike_strike_win.mp4`](phase4/row_6/guard_mark_edge_vs_ApfStrike_strike_win.mp4) | guard_mark_edge v ApfStrike | game 1: Strike team reaches the zone at 3.2 s; closest Guard–Strike in the horizontal plane 1.10 m | 945 | 25 kB |
| [`guard_mark_edge_vs_P3S_strike_win.mp4`](phase4/row_6/guard_mark_edge_vs_P3S_strike_win.mp4) | guard_mark_edge v P3S | game 1: Strike team reaches the zone at 4.5 s; closest Guard–Strike in the horizontal plane 1.07 m | 1000 | 26 kB |
| [`guard_mark_edge_vs_S20_strike_win.mp4`](phase4/row_6/guard_mark_edge_vs_S20_strike_win.mp4) | guard_mark_edge v S20 | game 1: Strike team reaches the zone at 14.1 s; closest Guard–Strike in the horizontal plane 1.06 m | 1000 | 33 kB |
| [`guard_mirror_vs_ApfStrike_hold.mp4`](phase4/row_6/guard_mirror_vs_ApfStrike_hold.mp4) | guard_mirror v ApfStrike | game 15: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 0.68 m | 961 | 74 kB |
| [`guard_mirror_vs_ApfStrike_strike_win.mp4`](phase4/row_6/guard_mirror_vs_ApfStrike_strike_win.mp4) | guard_mirror v ApfStrike | game 1: Strike team reaches the zone at 3.2 s; closest Guard–Strike in the horizontal plane 1.11 m | 961 | 25 kB |
| [`guard_mirror_vs_P3S_strike_win.mp4`](phase4/row_6/guard_mirror_vs_P3S_strike_win.mp4) | guard_mirror v P3S | game 1: Strike team reaches the zone at 4.3 s; closest Guard–Strike in the horizontal plane 1.09 m | 1000 | 26 kB |
| [`guard_mirror_vs_S20_strike_win.mp4`](phase4/row_6/guard_mirror_vs_S20_strike_win.mp4) | guard_mirror v S20 | game 1: Strike team reaches the zone at 6.9 s; closest Guard–Strike in the horizontal plane 1.11 m | 1000 | 28 kB |
| [`P3G_vs_ApfStrike_strike_win.mp4`](phase4/row_6/P3G_vs_ApfStrike_strike_win.mp4) | P3G v ApfStrike | game 1: Strike team reaches the zone at 4.0 s; closest Guard–Strike in the horizontal plane 1.08 m | 1000 | 25 kB |
| [`P3G_vs_P3S_strike_win.mp4`](phase4/row_6/P3G_vs_P3S_strike_win.mp4) | P3G v P3S | game 1: Strike team reaches the zone at 15.6 s; closest Guard–Strike in the horizontal plane 0.76 m | 1000 | 33 kB |
| [`P3G_vs_S20_strike_win.mp4`](phase4/row_6/P3G_vs_S20_strike_win.mp4) | P3G v S20 | game 1: Strike team reaches the zone at 65.6 s; closest Guard–Strike in the horizontal plane 1.11 m | 928 | 52 kB |
| [`P3G_vs_strike_flank_strike_win.mp4`](phase4/row_6/P3G_vs_strike_flank_strike_win.mp4) | P3G v strike_flank | game 1: Strike team reaches the zone at 10.1 s; closest Guard–Strike in the horizontal plane 1.08 m | 1000 | 29 kB |
| [`P3G_vs_strike_straight_strike_win.mp4`](phase4/row_6/P3G_vs_strike_straight_strike_win.mp4) | P3G v strike_straight | game 1: Strike team reaches the zone at 4.2 s; closest Guard–Strike in the horizontal plane 1.08 m | 1000 | 26 kB |
| [`ParkedGuard_vs_ApfStrike_strike_win.mp4`](phase4/row_6/ParkedGuard_vs_ApfStrike_strike_win.mp4) | ParkedGuard v ApfStrike | game 1: Strike team reaches the zone at 3.2 s; closest Guard–Strike in the horizontal plane 1.06 m | 1000 | 24 kB |
| [`ParkedGuard_vs_P3S_strike_win.mp4`](phase4/row_6/ParkedGuard_vs_P3S_strike_win.mp4) | ParkedGuard v P3S | game 1: Strike team reaches the zone at 5.5 s; closest Guard–Strike in the horizontal plane 1.05 m | 1000 | 26 kB |
| [`ParkedGuard_vs_S20_hold.mp4`](phase4/row_6/ParkedGuard_vs_S20_hold.mp4) | ParkedGuard v S20 | game 2: Guard team holds for 120 s; closest Guard–Strike in the horizontal plane 1.71 m | 524 | 72 kB |
| [`ParkedGuard_vs_S20_strike_win.mp4`](phase4/row_6/ParkedGuard_vs_S20_strike_win.mp4) | ParkedGuard v S20 | game 1: Strike team reaches the zone at 8.2 s; closest Guard–Strike in the horizontal plane 1.44 m | 524 | 26 kB |
| [`ParkedGuard_vs_strike_flank_strike_win.mp4`](phase4/row_6/ParkedGuard_vs_strike_flank_strike_win.mp4) | ParkedGuard v strike_flank | game 1: Strike team reaches the zone at 4.2 s; closest Guard–Strike in the horizontal plane 1.17 m | 1000 | 25 kB |
| [`ParkedGuard_vs_strike_straight_strike_win.mp4`](phase4/row_6/ParkedGuard_vs_strike_straight_strike_win.mp4) | ParkedGuard v strike_straight | game 1: Strike team reaches the zone at 3.2 s; closest Guard–Strike in the horizontal plane 1.02 m | 1000 | 25 kB |

## Size budget and how they were made

263 files added on 18 November 2026 (Phase 6 pass 2): 16.8 MB (260 MP4, 14.2 MB, and 3 GIF, 2.6 MB); with the 8 files of
pass 1 (0.7 MB) the folder holds 271 clip files, 17.5 MB. Sources (git-ignored, 5090 only): `runs/nus_port/phase4/row_*/videos/` (59 MB),
`runs/nus_port/videos/` and `videos/w3/` (8.5 MB), `runs/nus_port/isaac_clips/` (6.8 MB of MP4). Every MP4 keeps
its frame rate and frame count (checked for all 260). GitHub shows GIFs inline on a page and MP4 files only as
downloads, hence the three GIF previews.

Home RTX 5090, 18 November 2026, the `ffmpeg` of `imageio-ffmpeg` in `~/miniconda3/envs/env_isaaclab` (pass 2) and
`~/miniconda3/bin/ffmpeg` (pass 1):

```bash
# pass 2: any run clip -> compact MP4 (H.264, CRF 30, at most 800 px wide, same frame rate, no audio)
ffmpeg -i <run clip.mp4> -c:v libx264 -crf 30 -preset slow -pix_fmt yuv420p -movflags +faststart -vf "scale='min(800,iw)':-2" -an <name>.mp4
# pass 2: Isaac Lab GIF preview (4x real time, 480 px; the 120 s hold: setpts=PTS/8 and scale=400)
ffmpeg -i <isaac clip.mp4> -vf "setpts=PTS/4,fps=5,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle" <name>.gif
# pass 1: NUS GIF -> MP4 (all frames) and a small inline GIF
ffmpeg -i <nus.gif> -movflags +faststart -pix_fmt yuv420p -c:v libx264 -crf 28 -preset slow -vf "scale=640:-2" <name>.mp4
ffmpeg -i <nus.gif> -vf "fps=6.25,scale=360:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=48[p];[b][p]paletteuse=dither=none" <name>.gif
```

Where the run clips come from: `scripts/nus_phase4.py --render <row folder>` (Phase 4, from each row's `clips.npz`),
`scripts/nus_phase4_w3.py` (T17), the Phase 3 video step (T16, `viz/replay.py`), `scripts/nus_isaac_clips.py`
(Isaac Lab). NUS's GIFs come from NUS's `eval.py` with `save_eval_gif=True`; for self-play policies the evaluation
config was edited so the opponent pool holds one archive entry (the self-play runner writes no GIFs itself).

## Isaac Lab camera clips, second set: more pairings and the props world (18 November 2026, evening)

Owner's request (18 Nov): "record more Isaac Lab clips of NUS's policy, including in the props and construction-site
worlds". Presentation only (no gates, not a measurement, no ledger row): `scripts/nus_isaac_clips.py` with the
second-set entries of `configs/nus_isaac_clips.toml`, recorded headless on the home RTX 5090. The game is Phase 4 row 6
(tier 2: Isaac Lab rigid-body Starlings, safety filter on, free height with the start jitter) on the hangar arena,
7.5 m square, unchanged. **Props clips** add the blocks and columns of the S2b props clip (`make_s2b_video.py`'s scene
layer, seed 11, 8 objects). They are a backdrop only: the drones do not see or avoid them and can fly through them.
Every recorded game repeats its dry run exactly (0.0 m position difference, same end and outcome). What these clips show
was observed in the training simulator; nothing here is a flight.

"Game *n*" is the *n*-th paired start of the Phase 4 starts file, as in the row 6 clips. "Row 6" is that pair's count
over all 1,000 row-6 games (record T24). Files are in [`isaac/`](isaac/); the MP4s are real time, the GIF previews 4×
(a 120 s hold: 8×).

| File | World | Guard v Strike | Game, outcome | Row 6 Strike reach | What it shows | Size |
|---|---|---|---|---|---|---|
| [`open_p3g_vs_apf_strike_win_1.mp4`](isaac/open_p3g_vs_apf_strike_win_1.mp4), [`.gif`](isaac/open_p3g_vs_apf_strike_win_1.gif) | hangar arena | P3G v ApfStrike | game 1: Strike team reaches the zone at 4.0 s | 1,000 of 1,000 | NUS's fixed-opponent Guard policy against NUS's scripted Strike controller (ported): a Strike drone gets past the Guards within 4 s | 47 kB, 170 kB |
| [`open_mirror_vs_s20_strike_win_1.mp4`](isaac/open_mirror_vs_s20_strike_win_1.mp4) | hangar arena | guard_mirror v S20 | game 1: Strike team reaches the zone at 6.9 s | 1,000 of 1,000 | NUS's self-play Strike policy S20 against our scripted mirroring Guards | 60 kB |
| [`open_mirror_vs_p3s_strike_win_1.mp4`](isaac/open_mirror_vs_p3s_strike_win_1.mp4) | hangar arena | guard_mirror v P3S | game 1: Strike team reaches the zone at 4.3 s | 1,000 of 1,000 | NUS's fixed-opponent Strike policy against our scripted mirroring Guards | 49 kB |
| [`open_mark_edge_vs_s20_strike_win_1.mp4`](isaac/open_mark_edge_vs_s20_strike_win_1.mp4), [`.gif`](isaac/open_mark_edge_vs_s20_strike_win_1.gif) | hangar arena | guard_mark_edge v S20 | game 1: Strike team reaches the zone at 14.5 s | 1,000 of 1,000 | S20 against our scripted Guards that wait on the zone's edge: it takes the Strike team longer than against the mirroring Guards (row 6 medians: 13.7 s and 8.0 s) | 111 kB, 516 kB |
| [`props_g19_vs_apf_strike_win_1.mp4`](isaac/props_g19_vs_apf_strike_win_1.mp4), [`.gif`](isaac/props_g19_vs_apf_strike_win_1.gif) | props (backdrop only) | G19 v ApfStrike | game 1: Strike team reaches the zone at 4.0 s | 1,000 of 1,000 | the same paired start as the published `g19_vs_apf_strike_win_1` (4.1 s there, with 16 games running at once; row 6: 4.0 s), among blocks and columns that play no part in the game | 52 kB, 164 kB |

**Not recorded yet.** The hold clips: G19 v S20 at game 77 (row 6's first G19 v S20 hold, 21 of 1,000), ParkedGuard
v S20 in the props world (game 2), and P3G v S20 (a Strike win at game 2, the first hold at game 24). They wait until
the GPU is less busy (lead, 18 Nov). The construction-site clips (`site_g19_vs_s20`, `site_parked_vs_s20`) need the
laptop's `localisation/scenes/construction_site/build/` bundle; that bundle is not in git and not on the 5090. On a
machine without it the tool stops with exit 2 before Isaac starts.

**Recording conditions.** The GPU was shared with the Phase 5 jobs (the P1b pilot, NUS's C0 self-play jobs and the
route (b) trainers, at 91–99 % use). Ticks ran 10–30 times slower than for the first set: 3.4–3.7 s per dry-run
tick and about 4 s per rendered frame, against 0.1–0.3 s. The five clips above took 1.21 GPU-hours of the 1.5 h
cap (wall time of each launch, `runs/nus_port/isaac_clips_more/gpu_hours.log`, 5090 only). Re-encoded as the first
set: H.264 CRF 30 at 800 px; GIFs at 4× real time, 480 px, 5 frames/s, 128 colours
(`runs/nus_port/isaac_clips_more/publish.sh`).
