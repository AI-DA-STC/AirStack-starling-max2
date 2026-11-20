INTERNAL · the game spec sheet of the STE learning track (task L0.8, 20 Nov 2026). It lists the values of the game the track trains; it decides nothing. The same values, with the same labels, are in [configs/ste_game.toml](../configs/ste_game.toml); `tests/test_ste_game_spec.py` fails if the two differ.

# Game spec sheet

The Guard team holds a circular zone; the Strike team tries to reach it. Each row is one value of that game. **Status**
uses the four labels of [../STANDARDS.md](../STANDARDS.md): FIXED (set by the programme or by the flight stack; this folder may not change it), MEASURED (from a
record), PROPOSED (a working value, not ruled), OPEN (no settled value; the value shown is today's, for reference only).
D, P and F numbers are rows of the [discussion record](DISCUSSION_2026-11-19_20.md) and [PLAN](PLAN.md) §2. A *tick* is
0.05 s, one command of the flight software. The last column gives today's value in the two games the numbers come from.

| Item | Setting | Value | Status | Source | Today: hangar game · S2 game |
|---|---|---|---|---|---|
| Zone shape | `zone.shape` | `"circle"` | FIXED | parent STANDARDS §4 "Teams" (programme benchmark) | circle · circle |
| Where the zone counts | `zone.scored_in` | `"horizontal_plane"` | PROPOSED | parent STANDARDS §4 "Height"; `core/game.py:289-290` tests the horizontal distance only, so the zone is a vertical cylinder | same · same |
| Zone radius (m) | `zone.radius_m` | `1.6` | PROPOSED | P12; PLAN §4 L0.11 base case; hangar: `nus_rules.toml` `area_radius` × `nus_deploy.toml` `metres_per_unit`; the parent row is OPEN | 1.6 · 10–25 % of the arena side |
| Zone centre | `zone.centre` | `"arena_centre"` | PROPOSED | hangar: `nus/hangar_game.py` `_draw_arenas`; PLAN is silent; kept, LEAD CALL (20 Nov 2026) | arena centre · drawn per game |
| Strike wins after (ticks inside) | `zone.win_ticks_inside` | `1` | PROPOSED | parent STANDARDS §4 "Strike scores"; `s2_game.toml` and `nus_hangar_game.toml` `[partner_rules] win_steps_in_zone` | 1 · 1 |
| Height band (m) | `height.band_m` | `[0.5, 1.8]` | PROPOSED | parent STANDARDS §4 "Height"; `s2_game.toml` and `nus_hangar_game.toml` `[arena] height_band_m`; the lab's goal box, `goal_two_ours.yaml` `arena_low/high` (MEASURED) | same · same |
| Height | `height.mode` | `"free"` | PROPOSED | the game of the STE Guard policy (T41), Phase 4 row 5 (DISCUSSION §2.4, §2.6); `nus_phase4.toml` row 5 `height` | free in the band · held at the start height (Starling layer off, as committed) |
| Start height (m) | `height.start_m` | `1.2` | PROPOSED | `nus_deploy.toml` `flying_height_m` (row 5 adds a 1 mm jitter); `s2_game.toml` `start_height_m` | 1.2 · 1.2 |
| Arena side (m) | `arena.side_m` | `6.5` | PROPOSED | F8; PLAN §4 L0.11 base case: the lab fence, 6.5 × 6.5 × 4 m (parent STANDARDS §4, MEASURED) | 7.5 (`configs/local/nus_hangar.toml`) · 4–16 in three bands |
| Wall margin (m) | `arena.wall_margin_m` | `0.25` | PROPOSED | `s2_game.toml` and `nus_hangar_game.toml` `[arena] wall_margin_m`; drones are held this far inside each wall | 0.25 · 0.25 |
| Walls | `arena.walls` | `"keep_in"` | PROPOSED | parent STANDARDS §4 "Structures"; `s2_game.toml` and `nus_hangar_game.toml` `[arena] walls` | keep in · keep in |
| Environment | `arena.environment` | `"open_arena"` | PROPOSED | P10; the parent FIXED rule asks for realistic 3-D worlds, construction site first | open · open |
| Guard start disc (m) | `starts.guard_disc_m` | `0.8` | PROPOSED | hangar: `nus_rules.toml` `start_guard_disc_fraction` × `area_radius` × `nus_deploy.toml` `metres_per_unit`; Guards uniform in radius inside this disc round the zone centre (`nus/replica.py` `reset`) | 0.8 · rings |
| Strike start ring (m) | `starts.strike_ring_m` | `3.2` | OPEN | hangar: `nus_deploy.toml` `spawn_distance` × `metres_per_unit`, random bearings; **does not fit the 6.5 m arena** (keep-in limit 3.25 − 0.25 = 3.0 m) | 3.2 · 0.3 m inside the walls |
| Game length (s) | `timing.game_s` | `120.0` | PROPOSED | hangar: `nus_rules.toml` `episode_steps` × `nus_deploy.toml` `seconds_per_step` (2,400 ticks); PLAN is silent; kept, LEAD CALL (20 Nov 2026); S2: `s2_game.toml` `game_steps` × `seconds_per_step` | 120 · 60 |
| Decision every (s) | `timing.decision_s` | `0.6` | PROPOSED | `nus_deploy.toml` `seconds_per_step` (a command held 12 ticks); T41; DISCUSSION §2.10 | 0.6 · 0.05 |
| Strike speed (m/s) | `speeds.strike_mps` | `0.5` | FIXED | owner, 15 Nov 2026; parent STANDARDS §4 | 0.5 · 0.5 |
| Strike ÷ Guard speed | `speeds.strike_to_guard_ratio` | `1.5` | FIXED | parent STANDARDS §4 "Speed ratio": the Guard team flies 0.33 m/s | 1.5 · 1.5 |
| Programme team sizes (Guard v Strike) | `teams.of_interest` | `["2v1", "5v3"]` | FIXED | parent STANDARDS §4 "Team sizes of interest" | — · 2v1, 5v3 scored |
| Team sizes to train | `teams.target_sizes` | `["1v1", "2v1", "3v3", "5v3"]` | OPEN | P9: the candidates, all four studied in L0 | 3v3 · 1–5 v 1–3 |
| Base case of the study | `teams.base_case` | `"3v3"` | PROPOSED | PLAN §4 L0.11 base case; hangar: `nus_rules.toml` `guard_count`, `strike_count` | 3v3 · — |
| Main game has a tag | `tag_rule.main_game_has_tag` | `false` | FIXED | owner, 14–15 Nov 2026; parent STANDARDS §4 "Tag"; P1 would overturn it | no · no (contact tag 0.50 m is a side quest) |
| Proposed tag radius (m, 3-D centres) | `tag_rule.radius_m` | `1.6` | PROPOSED | P1; DISCUSSION §2.9: the filter distance + 0.5 m | none · none |
| Proposed tag pairing | `tag_rule.pairing` | `"nearest_pair_1for1"` | PROPOSED | PLAN §4 L0.9, F5: one Guard tags at most one Strike, nearest pair first | — · one Guard tags all in range |
| Guard survives a tag (probability) | `tag_rule.guard_survives_tag_prob` | `0.0` | PROPOSED | D2 (owner, provisional); stays PROPOSED, both ends (0 and 1) swept in L0.11, ruled at G0 under P12 (LEAD CALL, 20 Nov 2026); the parent row is FIXED for the contact tag | — · 0.0 |
| Filter pairs | `filter.pairs` | `"every_pair"` | FIXED | owner, 14–15 Nov 2026; parent STANDARDS §4 "Safety filter in the game" and §5 "Safety filter in flight today" | every pair · none as committed (`[starling_layer] enabled = false`: a push rule keeps opposite teams 1.10 m apart); every pair with the Starling layer on |
| Filter share | `filter.share` | `"equal"` | MEASURED | read from `AirStack/robot/ros_ws/src/svg_ground_control/svg_ground_control/cbf_filter.py:150-152, 339-341` (each pair's correction split evenly between the two drones) and DISCUSSION §2.9 desk run; option B is P2 | equal · equal with the Starling layer on |
| Filter distance (m, centre to centre) | `filter.keepout_m` | `1.10` | FIXED | parent STANDARDS §5: `cbf_safety_radius_m` 0.55 m in the `_ours` configs (`params/real_exploratory_v0.toml` `safety_radius_m`) | 1.10 · 1.10 (push rule `[partner_rules] keepout_*_m` as committed; filter with the Starling layer on) |

## Which source the track uses, and why

- **The hangar game first.** The track starts from the game the STE Guard policy was trained in (T41: NUS's hangar
  rules, Phase 4 row 5, safety filter on every pair, height free; DISCUSSION §2.4), because that game is known to train.
  NUS agreed that its settings may be published (owner decision 6, 18 Nov 2026).
- **PLAN overrides it where it says so.** The L0.11 base case puts the game in the 6.5 m lab arena, not the hangar's
  7.5 m (F8). Both sizes are swept in L0.11.
- **The S2 game** supplies the shared values (height band, walls, start height) and is shown for comparison.

## Open items

| # | What is open | Ruled at |
|---|---|---|
| P1 | Tag radius 1.6 m; it overturns the parent FIXED row "the main game has no tag". Built behind a setting, off by default (L0.9) | gate G0 |
| P12, D2 | Zone radius against tag radius (both 1.6 m today, F2), and what a tag costs (0 and 1 both reported in L0.11) | gate G0 |
| P9 | Team sizes to train: 1v1, 2v1, 3v3, 5v3 | gate G0 |
| P10 | Environments: open arena first, or the construction-site world sooner | gate G0 |
| P2 | Filter option B (only the Guard swerves in a Guard–Strike pair) | the L2 gate |
| F8 | New finding for L0.10 and L0.11: the Strike start ring (3.2 m) does not fit the 6.5 m arena (keep-in limit 3.0 m). A start ring that fits the 6.5 m arena must be chosen before L0.11's base case | the lead, before L0.11 |
| — | Game length and zone centre: PLAN is silent. LEAD CALL (20 Nov 2026): 120 s and the zone fixed at the arena centre stay PROPOSED, with the S2 game's 60 s and drawn centre shown beside them | ruled by the lead |
