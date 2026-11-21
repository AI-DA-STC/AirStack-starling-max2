INTERNAL · the game spec sheet of the STE learning track (task L0.8, 20 Nov 2026; QC fix round 1, 21 Nov 2026; task L0.10, 21 Nov 2026: the lab start ring and the scripted players). It lists the values of the game the track trains; it decides nothing. The game does not read it: the `tag.*` rows are the defaults of the game's own `[tag]` switch (`core/game_config.py` `TagCfg`, task L0.9), kept equal by the same test, and so are the `starts.*` rows (the game's `[starts]` mode `zone_disc_ring`, task L0.10) and `players.guard_park_ring_m` (the scripted player `guard_parked_ring`). The same values, with the same labels, are in [configs/ste_game.toml](../configs/ste_game.toml); `tests/test_ste_game_spec.py` fails if a setting, a value or a label differs between the two (the source texts are not compared).

# Game spec sheet

The Guard team holds a circular zone; the Strike team tries to reach it. Each row is one value of that game. **Status**
uses the four labels of [../STANDARDS.md](../STANDARDS.md): FIXED (set by the programme or by the flight stack; this folder may not change it), MEASURED (from a
record), PROPOSED (a working value, not ruled), OPEN (no settled value; the value shown is today's, for reference only).
D, P and F numbers are rows of the [discussion record](DISCUSSION_2026-11-19_20.md) and [PLAN](PLAN.md) §2. A *tick* is
0.05 s, one command of the flight software. The last column gives today's value in the two games the numbers come from.

Terms: the *hangar game* is NUS's game in metres as the lab ran it (`nus/hangar.py`); *T41* is the training run of the
STE Guard policy, in *Phase 4 row 5* of that game (safety filter on every pair, height free; `configs/nus_phase4.toml`).
The *Starling layer* is the S2 game's switch that flies drones through the copy of the flight software's commands and
filter; with it off, a *push rule* keeps opposite teams apart instead. The *keep-in limit* is how far from the arena
centre a drone may go along x or y: half the side less the wall margin.

| Item | Setting | Value | Status | Source | Today: hangar game · S2 game |
|---|---|---|---|---|---|
| Zone shape | `zone.shape` | `"circle"` | FIXED | parent STANDARDS §4 "Teams" (programme benchmark) | circle · circle |
| Where the zone counts | `zone.scored_in` | `"horizontal_plane"` | PROPOSED | parent STANDARDS §4 "Height"; `core/game.py:314-315` tests the horizontal distance only, so the zone is a vertical cylinder | same · same |
| Zone radius (m) | `zone.radius_m` | `1.6` | OPEN | P12, OPEN at gate G0 (DISCUSSION §3; the parent row "Zone radius" is OPEN); today's value: PLAN §4 L0.11 base case; hangar: `nus_rules.toml` `area_radius` × `nus_deploy.toml` `metres_per_unit` | 1.6 · 10–25 % of the arena side |
| Zone centre | `zone.centre` | `"arena_centre"` | PROPOSED | hangar: `nus/hangar_game.py` `_draw_arenas`; PLAN is silent; kept, LEAD CALL (20 Nov 2026) | arena centre · drawn per game |
| Strike wins after (ticks inside) | `zone.win_ticks_inside` | `1` | PROPOSED | parent STANDARDS §4 "Strike scores"; `s2_game.toml` and `nus_hangar_game.toml` `[partner_rules] win_steps_in_zone` | 1 · 1 |
| Height band (m) | `height.band_m` | `[0.5, 1.8]` | PROPOSED | parent STANDARDS §4 "Height"; `s2_game.toml` and `nus_hangar_game.toml` `[arena] height_band_m`; the lab's goal box, `goal_two_ours.yaml` `arena_low/high` (MEASURED) | same · same |
| Height | `height.mode` | `"free"` | PROPOSED | the game of the STE Guard policy (T41), Phase 4 row 5 (DISCUSSION §2.4, §2.6); `nus_phase4.toml` row 5 `height` | free in the band · held at the start height (Starling layer off, as committed) |
| Start height (m) | `height.start_m` | `1.2` | PROPOSED | `nus_deploy.toml` `flying_height_m` (row 5 adds a 1 mm jitter); `s2_game.toml` `start_height_m` | 1.2 · 1.2 |
| Arena side (m) | `arena.side_m` | `6.5` | PROPOSED | F8; PLAN §4 L0.11 base case: the lab fence, 6.5 × 6.5 × 4 m (parent STANDARDS §4, MEASURED) | 7.5 (`configs/local/nus_hangar.toml`) · 4–16 in three bands |
| Wall margin (m) | `arena.wall_margin_m` | `0.25` | PROPOSED | `s2_game.toml` and `nus_hangar_game.toml` `[arena] wall_margin_m`; drones are held this far inside each wall | 0.25 · 0.25 |
| Walls | `arena.walls` | `"keep_in"` | PROPOSED | `s2_game.toml` and `nus_hangar_game.toml` `[arena] walls`; `core/game.py:296-299` holds a drone at the wall; the lab fence keeps drones in too (`goal_two_ours.yaml` `fence_behavior`) | keep in · keep in |
| Environment | `arena.environment` | `"open_arena"` | OPEN | P10, OPEN at gate G0; the parent FIXED rule "Environments" asks for realistic 3-D worlds, construction site first; today's value is E0 of the parent's "Environment ladder", the first build step only, not claimed as meeting the rule | open · open |
| Guard start disc (m) | `starts.guard_disc_m` | `0.8` | PROPOSED | hangar: `nus_rules.toml` `start_guard_disc_fraction` × `area_radius` × `nus_deploy.toml` `metres_per_unit`; Guards uniform in radius inside this disc round the zone centre (`nus/replica.py` `reset`) | 0.8 · rings |
| Strike start ring (m) | `starts.strike_ring_m` | `2.75` | PROPOSED | LEAD CALL 21 Nov 2026, L08-F1 (task L0.10), ruled at G0 with the arena (F8): the hangar ring (`nus_deploy.toml` `spawn_distance` × `metres_per_unit`, random bearings) scaled by the arena half-side, 3.2 × 3.25 / 3.75 = 2.77, rounded down to 2.75. It fits the keep-in limit (3.0 m) on every bearing with 0.25 m to spare, stays 1.15 m outside the zone edge and 1.95 m from the Guard disc (more than the tag radius: no tag at the first step). Game: `[starts] mode = "zone_disc_ring"` | 3.2 · 0.3 m inside the walls |
| Team-mates' start spacing margin (m) | `starts.team_spacing_margin_m` | `0.05` | PROPOSED | LEAD CALL 21 Nov 2026 (L0.10 QC finding I1: with team-mates closer than the filter distance, the filter spread them into tag range with nobody moving). Mode `zone_disc_ring`: team-mates start at least the filter distance + 0.05 m apart. **Guard start radius rule:** two or more Guards evenly spaced on one circle per game (random rotation), radius uniform from the chord radius, 1.15 / (2 sin(π / Guards)) (0.66 m for 3, 0.98 m for 5), up to the Guard disc where it fits, else the chord radius; one Guard anywhere in the disc. Strikes on the ring at random gaps, none closer than 1.15 m. Information for later learners: in this mode the slot order is the bearing order (Guards evenly anticlockwise from Guard 0, Strikes anticlockwise from Strike 0) | — · — |
| Game length (s) | `timing.game_s` | `120.0` | PROPOSED | hangar: `nus_rules.toml` `episode_steps` × `nus_deploy.toml` `seconds_per_step` (2,400 ticks); PLAN is silent; kept, LEAD CALL (20 Nov 2026); S2: `s2_game.toml` `game_steps` × `seconds_per_step` | 120 · 60 |
| Decision every (s) | `timing.decision_s` | `0.6` | PROPOSED | `nus_deploy.toml` `seconds_per_step` (a command held 12 ticks); T41; DISCUSSION §2.10 | 0.6 · 0.05 |
| Strike speed (m/s) | `speeds.strike_mps` | `0.5` | FIXED | owner, 15 Nov 2026; parent STANDARDS §4 | 0.5 · 0.5 |
| Strike ÷ Guard speed | `speeds.strike_to_guard_ratio` | `1.5` | FIXED | parent STANDARDS §4 "Speed ratio": the Guard team flies 0.33 m/s | 1.5 · 1.5 |
| Programme team sizes (Guard v Strike) | `teams.of_interest` | `["2v1", "5v3"]` | FIXED | parent STANDARDS §4 "Team sizes of interest" | — · 2v1, 5v3 scored |
| Team sizes to train | `teams.target_sizes` | `["1v1", "2v1", "3v3", "5v3"]` | OPEN | P9: the candidates, all four studied in L0 | 3v3 · 1–5 v 1–3 |
| Base case of the study | `teams.base_case` | `"3v3"` | PROPOSED | PLAN §4 L0.11 base case; hangar: `nus_rules.toml` `guard_count`, `strike_count` | 3v3 · — |
| Main game has a tag | `tag_rule.main_game_has_tag` | `false` | FIXED | owner, 14–15 Nov 2026; parent STANDARDS §4 "Tag"; P1 would overturn it | no · no (contact tag 0.50 m is a side quest) |
| Proposed tag radius (m, 3-D centres) | `tag_rule.radius_m` | `1.6` | PROPOSED | P1; DISCUSSION §2.9: the filter distance + 0.5 m. Beside it, OPEN at G0 (no ruling): the owner's realistic-tag target 1.15 m, the filter distance + 0.05 m (L0.12b, DISCUSSION §11; G0_DECISION row 1d) | none · none |
| Proposed tag pairing | `tag_rule.pairing` | `"nearest_pair_1for1"` | PROPOSED | PLAN §4 L0.9, F5: one Guard tags at most one Strike, nearest pair first | — · one Guard tags all in range |
| Guard survives a tag (probability) | `tag_rule.guard_survives_tag_prob` | `0.0` | PROPOSED | D2 (owner, provisional); stays PROPOSED, both ends (0 and 1) swept in L0.11, ruled at G0 under P12 (LEAD CALL, 20 Nov 2026); the parent row is FIXED for the contact tag | — · 0.0 |
| Study tag switch in the game | `tag.mode` | `"off"` | FIXED | parent STANDARDS §4 "Tag" (as `tag_rule.main_game_has_tag`); a game file's `[tag]` table (L0.9); off = today's game bit for bit; `"nearest_pair_1for1"` switches the study tag on, for study runs only until P1 is ruled | off · off |
| Study tag radius (m, 3-D centres) | `tag.radius_m` | `1.6` | PROPOSED | P1; equals `tag_rule.radius_m`; a pair strictly closer tags | — · — |
| Study tag: Guard survives (probability) | `tag.guard_survives_tag_prob` | `0.0` | PROPOSED | D2 (owner, provisional), P12; equals `tag_rule.guard_survives_tag_prob`; drawn per game at its start, from the tag's own random stream | — · — |
| Filter pairs | `filter.pairs` | `"every_pair"` | FIXED | owner, 14–15 Nov 2026; parent STANDARDS §4 "Safety filter in the game" and §5 "Safety filter in flight today" | every pair · none as committed (`[starling_layer] enabled = false`: a push rule keeps opposite teams 1.10 m apart); every pair with the Starling layer on |
| Filter share | `filter.share` | `"equal"` | MEASURED | read from `AirStack/robot/ros_ws/src/svg_ground_control/svg_ground_control/cbf_filter.py:150-152, 339-341` (each pair's correction split evenly between the two drones) and DISCUSSION §2.9 desk run; option B is P2 | equal · equal with the Starling layer on |
| Filter distance (m, centre to centre) | `filter.keepout_m` | `1.10` | FIXED | parent STANDARDS §5: `cbf_safety_radius_m` 0.55 m in the `_ours` configs (`params/real_exploratory_v0.toml` `safety_radius_m`) | 1.10 · 1.10 (push rule `[partner_rules] keepout_*_m` as committed; filter with the Starling layer on) |
| Parked-ring Guard: smallest ring radius (m) | `players.guard_park_ring_m` | `0.8` | PROPOSED | PLAN §2 F1 (lead's geometry script, 20 Nov 2026): three Guards parked on a 0.8 m ring cover the whole zone (worst gap 1.53 m); task L0.10. LEAD CALL 21 Nov 2026: the ring grows when neighbours would be closer than the filter distance + 0.05 m (5 Guards: 0.98 m) | — · — |

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
| P1 | Tag radius 1.6 m; it overturns the parent FIXED row "the main game has no tag". Built behind a setting, off by default: `[tag] mode` (L0.9) | gate G0 |
| P12, D2 | Zone radius (OPEN here) against tag radius (both 1.6 m today, F2), and what a tag costs (0 and 1 both reported in L0.11) | gate G0 |
| P9 | Team sizes to train: 1v1, 2v1, 3v3, 5v3 | gate G0 |
| P10 | Environments (OPEN here): open arena first, or the construction-site world sooner | gate G0 |
| P2 | Filter option B (only the Guard swerves in a Guard–Strike pair) | the L2 gate |
| L08-F1 | Closed by LEAD CALL 21 Nov 2026 (task L0.10). The finding: the hangar's Strike start ring (3.2 m) lies outside the 6.5 m arena's keep-in limit (3.0 m) on about 45 % of bearings. The ring is now 2.75 m (PROPOSED, row `starts.strike_ring_m`) | value ruled at G0 with the arena (F8) |
| — | Game length and zone centre: PLAN is silent. LEAD CALL (20 Nov 2026): 120 s and the zone fixed at the arena centre stay PROPOSED, with the S2 game's 60 s and drawn centre shown beside them | ruled by the lead |
| — | A fixed 6.5 m base-case game file (arena fixed, zone at the centre, starts `zone_disc_ring`). Done (task L0.11, 21 Nov 2026): [configs/ste_l011/base.toml](../configs/ste_l011/base.toml) fixes the arena through the band, zone-radius and zone-margin settings, with the study tag on; its variants and the sweep's gate file are beside it, and `tests/test_ste_l011.py` checks the built game against this sheet. Not applied there: `timing.decision_s` (finding L011-F1: the scripted players decide every 0.05 s tick) | closed by L0.11 (LEAD CALL 21 Nov 2026) |
| — | Starts mode `zone_disc_ring`: a miss is a Guard–Strike pair inside the keep-out or a Strike drone inside the zone; team-mate pairs closer than the filter distance are a separate INFO count, `info["start_team_close"]` (no change to outcomes). L0.11 reports both. LEAD CALL 21 Nov 2026 | settled by the lead |

## Scripted players

Hand-written players for the L0.11 screening sweep and the L0.12 controls (`source/svg_training/opponents/scripted.py`,
task L0.10). Each reads only its team's observations. "Pure path" means the Starling layer is off: drones stay at the
start height there.

| Player | What it does |
|---|---|
| `guard_parked_centre` | A lone Guard flies to the zone centre and stops there. With two or more Guards, every Guard holds its start position: their start circle is already centred on the zone (LEAD CALL 21 Nov 2026; a Guard flying into the middle made the filter push its team-mates into the Strikes' tag range at 5v3). It ignores the Strike drones. |
| `guard_parked_ring` | The Guards park on a ring round the zone centre, points a whole turn / team size apart, and stop there. The ring is 0.8 m (`players.guard_park_ring_m`), larger when neighbours would be closer than the filter distance + 0.05 m (5 Guards: 0.98 m). The lowest-index Guard keeps its bearing; the others take the next points in the order they stand round the zone, so none crosses the ring (LEAD CALL 21 Nov 2026). After a loss the others hold their points. |
| `guard_mark_edge` | Each Guard picks one live Strike and sits on the zone edge between it and the centre. |
| `guard_mirror` | Each Guard holds a ring at 1.2 × the zone radius towards its Strike and copies its sideways speed. |
| `guard_field` | Each Guard is pulled to the zone edge facing the nearest Strike and pushed off team-mates closer than 1.1 m. |
| `strike_straight` | Flies straight at the zone centre at one height. |
| `strike_flank` | Flies straight, unless a Guard is in the way; then it goes round that Guard on its far side. |
| `strike_high` | Climbs to 0.1 m below the top of the height band, then flies straight in at that height. Plays as `strike_straight` on the pure path. |
| `strike_low` | The same at 0.1 m above the bottom of the band. |
| `strike_sacrifice` | Strike 0 flies at the Guard nearest to it, to draw it. The others enter opposite that Guard's bearing, the gap it opens (if that Guard is within 0.05 m of the centre, it has no clear bearing and they enter opposite Strike 0 instead): they circle at a stand-off distance until within 30° of that bearing, then fly straight in. When Strike 0 is out, or only one Strike is left, they fly straight in. |
| `strike_converge` | The Strikes spread out round the zone at a stand-off distance, at bearings a whole turn / team size apart, starting from the bearing of the lowest-index live Strike. When all are at their bearings, they fly straight in, the nearer ones slower, so that all reach the zone edge together (within 0.3 s in the test). Once they are well on the way in, a loss does not stop them. Accepted as built (LEAD CALL 21 Nov 2026). |

## Scripted player settings

The behaviour constants of the scripted players (`opponents/scripted.py`; `tests/test_scripted_study.py` keeps this
table and the constants equal). Hand picks for the screening sweep, not tuned on results.

| Setting | Constant | Value | Unit | Status | Source |
|---|---|---|---|---|---|
| Parked ring: smallest radius | `PARK_RING_M` | `0.8` | m | PROPOSED | LEAD CALL 21 Nov 2026 (PLAN §2 F1); same as `players.guard_park_ring_m` |
| Parked ring: neighbours at least the filter distance + this apart | `PARK_RING_SPACING_MARGIN_M` | `0.05` | m | PROPOSED | LEAD CALL 21 Nov 2026 |
| High / low Strike: aim this far inside the height band edge | `BAND_INSET_M` | `0.1` | m | PROPOSED | LEAD CALL 21 Nov 2026 |
| Sacrifice / converge: stand-off circle, outside the zone edge | `STAND_OFF_M` | `1.0` | m | PROPOSED | LEAD CALL 21 Nov 2026; capped inside the keep-in box |
| Sacrifice: fly straight in within this of the entry bearing | `ENTRY_HALF_ANGLE_DEG` | `30.0` | deg | PROPOSED | LEAD CALL 21 Nov 2026 |
| Sacrifice: a drawn Guard this close to the centre gives no entry bearing | `SACRIFICE_NO_BEARING_M` | `0.05` | m | PROPOSED | LEAD CALL 21 Nov 2026 (QC M4) |
| Converge: in place within this of the own bearing | `GATHER_ANGLE_RAD` | `0.1` | rad | PROPOSED | LEAD CALL 21 Nov 2026 |
| Circling: radial correction reaches full speed this far off the circle | `RADIAL_RAMP_M` | `1.0` | m | PROPOSED | LEAD CALL 21 Nov 2026 |
| Converge: circle round while farther than this from the own bearing | `CIRCLE_UNTIL_RAD` | `0.5` | rad | PROPOSED | LEAD CALL 21 Nov 2026 |
| Converge: run-in goes on once a Strike is this far inside the stand-off circle | `RUN_IN_COMMIT_M` | `0.3` | m | PROPOSED | LEAD CALL 21 Nov 2026 |
