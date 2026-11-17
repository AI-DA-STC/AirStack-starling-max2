# NUS port, Phase 4: the transfer ladder (frozen partner policies, one change at a time)

**Status: PLAN v2 (18 November 2026), after the gatekeeper read of v1 (6 PASS, 7 FAIL; all fixes applied). Nothing
built or run.** Phase 3 passed first (ledger W2). Phase 4 itself is owner-approved as INFO runs (no gates); the one
gated run in it is W3, which finishes Phase 3's deferred arm. The private plan with partner values is on the 5090
(`~/ma_skills-self-play/PORT_PLAN.md` §3 Phase 4 and "Hangar geometry — DECIDED"). This file holds no partner value:
every partner-derived number is named by its local key in `configs/local/nus_rules.toml`,
`configs/local/nus_deploy.toml` or the new `configs/local/nus_hangar.toml` (Task 1). Every new value below is
**PROPOSED** or **OPEN** (STANDARDS status labels).

v2 changes: W3 gates copied verbatim and its archive-arm pass rule written down (D2, D8). PORT_PLAN's rung order kept:
action hold arrives on rung 3 (owner question 3). Control rows 2.1, 3a and 5a, each checked game by game. A pre-set
split of rung 2. More metrics (filter correction size, smoothness, an interval on every rate). Reach time in seconds
only. "At the local value" wording. A text scan of committed pages. A wider marker test. A free GPU for every rung. The
rung 3 layer swap, Run 0's parked Guard and the §6.2 exception stated.

## Goal (PROPOSED)

Find where the partner's strategy stops working as Starling behaviour is added. All results are observed in the
training simulator (tier 1 and tier 2). The partner's converted policies stay frozen. They are scored on the decided
hangar geometry, row by row, ≥ 1,000 games per pair, and each row changes one behaviour. A parked-Guard baseline sits
in every row. Phase 4 trains nothing and, apart from W3, passes or fails nothing. It ends when the owner reads the
ladder and chooses the route for Phase 5.

## Facts this plan rests on (read 18 November 2026)

| # | Fact | Source |
|---|---|---|
| F1 | The game draws a random arena side per band, a random zone radius as a fraction of the side, and a random zone centre. `starts.mode` is `rings` or `anywhere`; neither is the partner's start. The local partner file may set only `partner_rules.*` and `arena.zone_radius_frac` | `core/arena.py`, `core/game_config.py` `LOCAL_ALLOWED` |
| F2 | `SvgGame._draw_arenas` is already a method. Starts are drawn inline in `_new_games` | `core/game.py` |
| F3 | `SvgGame.__init__` sets the private `self._starling` (`core/game.py:115-119`): `StarlingLayer` or `PhysicsLayer`, both built with the safety filter on. Turning on the Starling layer also turns the push-apart off. `FittedResponse` itself takes `safety_filter=False` | `core/game.py`, `core/starling_layer.py`, `core/physics_layer.py`, `models/fitted.py:73` |
| F4 | `NusPolicy` holds each action for `hold_ticks` in any `SvgGame` | `nus/strategy.py` `act` |
| F5 | On tier 1, drones that start at one height and are never commanded up or down stay at that height. The filter's escape can only be sideways. On the physics drone, heights differ by millimetres and the escape can turn vertical. A 1 mm higher Strike start took one tier 1 cell from 97.5 % held to 0 % | [S2B_RESULTS §4](../S2B_RESULTS.md), `scripts/diag_vertical_pass.py` |
| F6 | `NusPolicy` reads one weights folder per team from the module-level `DEPLOY_PATH` (W2's deploy file, sha256 in W2) | `nus/strategy.py`, `nus/deploy.py` |
| F7 | `nus/apf.py` works on replica positions in partner units; it is not a strategy for `SvgGame` | `nus/apf.py` |
| F8 | `core.metrics.summarise` gives the hold rate with Wilson 95 %, the mean end step, closest approaches, breach share, filter share and start miss. It gives no reach time, same-team approach, correction size or smoothness. `MatchResult` can be built by hand | `core/metrics.py`, `core/play.py` |
| F9 | The filter runs in `CommandChain._filter(nominal, pos)`. The chain keeps only `corrected` (bool), not the size of the change | `models/command_chain.py` |
| F10 | `score.py` cannot take the hangar geometry. Its Isaac path starts Isaac Sim before torch and reuses one `IsaacWorld` for every pair (`_isaac_world_factory`) | `scripts/score.py` |
| F11 | `IsaacWorld` drone bodies have no collision shape (`collision_props=None`); games are `spacing_m` apart | `compat/isaaclab_232.py` `IsaacWorld.__init__` |
| F12 | `write_record` refuses raw local values, not derived ones (metres = units × scale, ticks = steps × hold) | `nus/outputs.py` |
| F13 | The s2 g19 Guard and s2 g20 Strike archive entries have not been through Phase 3's gates. Gate (b) names "scripted APF and the archive partner"; the archive arm was deferred | `configs/nus_port.toml`, Phase 3 plan Task 7, W2 record |
| F14 | Run 0's parked Guard (private, `~/ma_skills-self-play/_probes/run0/run0.py:17-22`): before the first step, Guard 0's position and its previous position are set to the zone centre; then every Guard is commanded zero displacement at every step | private probe, described in words |
| F15 | The 5090's headless Isaac launch on WiFi is approved (owner, 18 November, commit `6472b548`). Port plan item D9(b) is therefore closed | `scripts/isaac_preflight.sh`, HANDOFF |

## Decisions

### D1. The hangar geometry as a game config

Partner-derived values never sit in a tracked file. They are computed in memory from the local files, the way
`NusPolicy` already works.

1. **Committed `configs/nus_hangar_game.toml`**: generic settings only. These are `preset = "partner"`,
   `walls = "keep_in"`, the committed `wall_margin_m` and `height_band_m`, `dropout_fraction = 0`, `obs_view = "full"`,
   `push_rule = "block"`, and the Starling parameter files, sweeps and `check_every` as in `s2_game.toml`. Keys that
   `nus/hangar.py` sets are left at the neutral defaults. A comment lists them.
2. **New local file `configs/local/nus_hangar.toml`** (git-ignored), with template `configs/nus_hangar.template.toml`
   (all `"LOCAL"`). Key `arena_side_m`: the owner's arena side, chosen to fit the partner's start ring at the owner's
   scale, so kept local. It is a separate file, so W2's deploy file and its sha256 stay unchanged.
3. **`nus/hangar.py:hangar_cfg(base, rules, deploy, hangar, row) -> GameCfg`**, a pure function with no numeric
   literal (G2):

   | Game key | From (local key names only) |
   |---|---|
   | `rules.metres_per_unit`, `rules.seconds_per_step` | deploy `metres_per_unit`, `seconds_per_step` |
   | `rules.strike_units_per_step`, `rules.guard_units_per_step` | rules `strike_max_speed`, `guard_max_speed` |
   | `rules.game_steps` | rules `episode_steps` |
   | `rules.keepout_strike_m` | (2 × `agent_size` + `guard_safety_distance`) × scale: the disc round a **Guard** that keeps **Strike** drones out. The crossing is deliberate (port plan F3); a test pins it |
   | `rules.keepout_guard_m` | (2 × `agent_size` + `strike_safety_distance`) × scale |
   | fixed arena side, zone radius, zone centre | hangar `arena_side_m`; `area_radius` × scale; the arena centre |
   | start ring, Guard start disc | deploy `spawn_distance` × scale; `start_guard_disc_fraction` × `area_radius` × scale |
   | `arena.start_height_m` | deploy `flying_height_m` |
   | `arena.height_band_m` | `pinned` = the flying height at both ends; `free` = the committed band (D3) |

4. **Core change: one hook only** (PROPOSED; another session may edit `core/`, so it is one small separate commit with
   a HANDOFF line). In `SvgGame._new_games` the inline `draw_starts(...)` call becomes a method,
   `self._draw_starts(arenas) -> (starts [N, M, 3], miss [N])`. The default body is the same call, and a test shows
   the random stream is bit-identical.
5. **`nus/hangar_game.py:NusHangarGame(SvgGame)`**, after the precedent of `viz/replay._RecordingGame`:
   - `_draw_arenas` returns the fixed arena;
   - `_draw_starts` returns the paired starts (D4); `miss` flags any pair inside the filter's keep-out at the start,
     reported, never repaired;
   - the jump mode (rung 2) and the layer swap (rung 3) of D3;
   - per-tick recording of the extra metrics and video slots (D5, D6).

   `score.py` cannot build this game (F10), so a dedicated runner does (Task 7).
6. **Fixed team size 3v3**, `dropout_fraction = 0`: the partner's network has its team size built in.

### D2. Policies, opponents and the W3 precondition

| Name | What | Weights from |
|---|---|---|
| `G19` | s2 g19 Guard: archive entry 19 of self-play seed 2, hangar geometry | `configs/local/nus_deploy_ref.toml` (new). Same keys and values as W2's deploy file except `guard_weights` and `strike_weights`; a test checks this |
| `S20` | s2 g20 Strike: archive entry 20 of the same run | same file |
| `P3G`, `P3S` | the Phase 3 pair as converted and gated in W2 | `configs/local/nus_deploy.toml` (W2's, unchanged) |

`NusPolicy` reads `type(self).deploy_path`, which defaults to today's `DEPLOY_PATH`. Thin subclasses in
`nus/players.py` (`RefGuard`, `RefStrike`, `P3Guard`, `P3Strike`) bind the two files. Every row records the sha256 of
the deploy file it used.

**W3, before any rung (gated, F13).** G19 and S20 are converted and scored against the frozen
`[gates.phase3_converted_policy]`:
- **Gates file.** Before the run, `runs/nus_port/w3/gates.toml` gets a verbatim copy of that section, the sha256 of
  `configs/nus_port.toml` and the line "unchanged since W2". It is not `gates = []`.
- **Gate (a).** Action parity on ≥ 10,000 reference observations per team, as in W2.
- **Gate (b), two arms, both named by the frozen text.**
  - *Scripted arm*, as W2: G19 against the ported scripted Strike controller, and S20 against the ported scripted
    Guard controller. Each converted arm's Strike reach rate must lie inside its JAX arm's Wilson 95 % interval, on the
    same 1,000 shared starts.
  - *Archive arm*: G19 against S20, both teams converted, and both teams JAX through two action workers (one per
    team). **Pass rule, written before the run:** the converted pair's Strike reach rate lies inside the Wilson 95 %
    interval of the JAX pair's rate, on the same 1,000 shared starts, all actions deterministic. The record also gives
    the count of games that differ.
- **Videos.** Two replica games per arm from the converted policies → `runs/nus_port/videos/w3/`.
- A FAIL stops Phase 4 for the owner.

**Pairs per row** (PROPOSED). Every Guard spec plays every Strike spec in its block, 1,000 games each.

| Block | Guard team | Strike team | Rows |
|---|---|---|---|
| Core (4 × 3 pairs) | `G19`, `P3G`, `ApfGuard`, `ParkedGuard` | `S20`, `P3S`, `ApfStrike` | all |
| Our scripted Strike (3 × 2) | `G19`, `P3G`, `ParkedGuard` | `strike_straight`, `strike_flank` | all except 1 and 2.1 (they read our observation, which the replica lacks) |
| Our scripted Guard (2 × 3) | `guard_mirror`, `guard_mark_edge` | `S20`, `P3S`, `ApfStrike` | as above |

- `ApfGuard`, `ApfStrike`: the ported controllers as strategies. They rebuild positions in partner units from our
  observation with `NusPolicy`'s helper and sample on the same schedule as the policies. `ApfGuard` against
  `ApfStrike` is the policy-free control.
- **`ParkedGuard`**, as Run 0 (F14): Guard 0's start (and previous position) is the zone centre; the other five starts
  are unchanged. All three Guards command zero for the whole game. Its rows also report how far Guard 0 drifts from
  the centre (largest distance per game, min / p50 / max). From rung 4 the filter may push it, because the other
  Guards start close by.
- On rows 1 and 2.1 every player is a replica callable under the same name (`nus/players.py` registry).
- **Exact check against W2** (reading rule 3). Row 1 also replays W2's 1,000 shared starts, on the CPU, for `P3G`
  against `ApfStrike` and `ApfGuard` against `P3S`. Outcomes must equal W2's converted arm game by game. On the
  ladder's own starts these two pairs are INFO: an unpaired interval check misses about one time in six.

### D3. The rows: one behaviour each

The ladder keeps PORT_PLAN's six steps as rungs 1–6, in order. Action hold therefore belongs to rung 3 ("+ action hold
and Starling layer"); moving it is owner question 3. Lettered rows split a rung so that each row changes one
behaviour. The committed `configs/nus_phase4.toml` `[[row]]` table declares every row by six keys (no partner value):
`engine` (`replica`/`game`), `boundary` (`guard_circle`/`walls`), `separation` (`partner_push`/`block`/`filter`),
`motion` (`jump`/`hold`), `drone` (`points`/`identity`/`fitted`/`physics`) and `height` (`pinned`/`free`/`free_jitter`).

| Row | The one change | Key changed | Runs | Behaviour check |
|---|---|---|---|---|
| 1 | baseline: our replica of the partner's game (W1 parity) | — | always | W2 replay (D2) |
| 2.1 | our game engine with the partner's own rules: the soft push and the Guard circle, from the replica's `corrections` converted to metres; walls moved out of reach; jump motion | `engine` | if split (below) | equals row 1 game by game; positions within 1e-4 units at every partner step |
| 2.2 | square walls instead of the Guard circle | `boundary` | if split | — |
| **2** | `block` push-apart instead of the partner's soft push. Rung 2 = PORT_PLAN step 2: our `partner_rules` (pure), jump motion | `separation` | always | — |
| 3h | action hold: the displacement flown at constant speed over the partner step instead of in one tick | `motion` | always | — |
| 3a | the rung 3 layer with an identity drone (no commander, delay or lag): the drone flies the held command exactly | `drone` | always | equals 3h game by game |
| **3** | the drone response: commander copy (ramp, leash), delay, lag (`real_exploratory_v0`); filter still off, push kept | `drone` | always | — |
| **4** | the all-pairs safety filter instead of the push (as in flight) | `separation` | always | — |
| 5a | free height, no jitter | `height` | always | equals rung 4 game by game (F5) |
| **5** | 3-D at one height: a 1 mm start jitter breaks the symmetry | `height` | always | — |
| **6** | the physics drone (tier 2, Isaac Lab) | `drone` | always | — |

Notes:

- **Jump motion (rungs 1–2).** In `NusHangarGame` on a game's sample tick (`steps % hold_ticks == 0`), the team speed
  cap is scaled by `hold_ticks` for that tick only, and players emit their action on sample ticks only, zero
  between. The drone therefore covers the partner's displacement in one tick, the push acts on that jump as the
  partner's one-pass push acts on its tentative positions, and the per-tick zone test sees the same positions as a
  per-step test. This uses the private `_speed_mps` (per-game tensor), and a test pins it.
- **Split of rung 2, pre-set.** If any core pair's rung 2 Strike reach rate lies outside rung 1's Wilson 95 %
  interval, rows 2.1 and 2.2 run before rung 3, in that order. Otherwise they stay declared but skipped. The partner
  push in metres (row 2.1) is built only then (Task 4b).
- **Rung 3 layer swap** (`nus/hangar_game.py`, no core edit). `NusHangarGame.__init__` calls `super().__init__` with the
  fitted Starling layer on. That sets `self._starling` (`core/game.py:115-119`). It then replaces `self._starling` with
  `NusPushLayer`, a `StarlingLayer` subclass whose `FittedResponse` has `safety_filter=False` (row 3a: an identity
  response). After each model step it applies `core.pair_rules.push_apart` to the horizontal positions and writes
  them back into the model. Then it resets again, so the new layer holds the starts. The push moves neither the
  velocity nor the commander's reference, so the commander pulls a pushed drone back; the record says so.
  - Tests: after construction, `game._starling` is a `NusPushLayer` with its filter off, and one step equals a
    hand-built layer.
  - The runner refuses this layer with `physics`.
- **STANDARDS §6.2 exception, stated.** Rows 1 to 3 run without the safety filter, although §6.2 puts the filter in the
  loop for training and evaluation. They are INFO measurements of a frozen partner policy: nothing is trained, gated
  or exported from them. Port plan Phase 4, as approved, defines the ladder that way. Rungs 4–6 restore the filter.
  Every record of rows 1–3 says "safety filter off (STANDARDS §6.2 exception, Phase 4 ladder)".
- **`pinned`** = `arena.height_band_m` at the flying height at both ends. Row 1 is 2-D and the pure rules hold z, so
  rows 1–3h are pinned by construction.
- **Jitter**, uniform ±1 mm per drone and game (PROPOSED; the size of the S2b 1 mm test, a stand-in for the physics
  drone's millimetre differences). It is drawn once and stored in the starts file.
- **Rung 6** keeps rung 5's settings and changes `drone` only (`starling.backend = "physics"`). Passing over or under
  stays in the game (owner, option (a), 17 November).
- The exploratory drone model (T5 = FAIL) answers more slowly than the real drone (PLUG_IN), so rows 3–5 overstate
  the lag cost; every record says so.
- **Checks.** A config test checks that consecutive declared rows differ in exactly one key: a lint. The evidence is
  behavioural: each control row's equality is a unit test on a small CPU batch (Task 4) and a reading rule in the run
  (D5).

### D4. Paired starts (PROPOSED)

One starts file, drawn once with the replica's own start rule (`NusReplica.reset`, random starts, hangar overrides, seed
`[ladder] seed`; the value is PROPOSED in Task 3 and fixed before the first run). It is written only under
`runs/nus_port/phase4/` (`require_under_runs`) with its sha256, and holds the starts in units, the jitter and Guard 0's
parked variant. Every row and every pair plays slot k from the same start. Each record counts the games whose outcome
flipped against the row before. One seed: Phase 4 makes no method claim (STANDARDS §6.5).

### D5. Metrics per row (STANDARDS §7)

One row per pair. Shared fields come from `core.metrics.summarise`; row 1 and row 2.1 build a `MatchResult` by hand
(ticks = partner steps × `hold_ticks`, metres = units × scale). The extras live in `nus/ladder.py`, which is the one
module for every Phase 4 number. The figure script imports it and computes nothing itself.

| Metric | Definition |
|---|---|
| Strike reach rate | 1 − hold rate, Wilson 95 %, 1,000 games |
| Reach time | median over Strike-win games of the first reach, **in seconds only** |
| Closest approach, Guard–Strike | min / p5 / p50 over games, horizontal and 3-D |
| Closest approach, same team | the same, 3-D (recorded by `NusHangarGame`; rows 1 and 2.1 from positions) |
| Filter correction share | share of live drone-steps the filter changed, Wilson 95 % |
| Filter correction size | per corrected drone-step, \|filtered − nominal\| speed (m/s): mean and p95. `NusHangarGame` wraps the chain's `_filter` on the instance (F9), read-only, so no shared code changes |
| Smoothness | change in the command the game receives, per drone per tick and per policy sample (m/s): mean and p95 |
| Rule breach | share of games with an opposite pair inside the smaller partner push radius (`cfg.rules`, 3-D), Wilson 95 % |
| Filter breach | share of games with any pair inside the filter's keep-out (from the Starling parameter file; the flight stack's, STANDARDS §5), Wilson 95 % |
| Contact | share of games with any pair closer than the tier 1 contact distance in 3-D (STANDARDS §4; a crash in flight), Wilson 95 %; the distance is named, not quoted |
| Start miss, upsets | shares with Wilson 95 % (upsets on rung 6 only); non-finite actions or wrench values: the runner refuses to score |
| Parked-Guard baseline | `ParkedGuard` Strike reach rate per Strike player, beside the policy rows; Guard 0's drift |
| Paired change | games whose outcome differs from the row before, same pair and slot |
| Throughput | game-steps/s and drone-steps/s, with games, drones per game, tier and GPU (§8) |

**Pre-set reading rules** (PROPOSED; not gates):
1. If `ParkedGuard` holds ≥ 90 % against `ApfStrike` on any row (Run 0's trigger), the geometry closes the zone on its
   own. Stop and ask the owner; the pre-set adjustment is a larger zone.
2. A control row (2.1, 3a, 5a) that differs from its partner row in any game: stop and `train-debug`.
3. Row 1's replay of W2's starts differs in any game: stop.
4. Any upset, non-finite wrench or contact on rung 6: record it, then `train-debug` before the summary.

### D6. Videos (owner rule, STANDARDS §8)

`NusHangarGame` keeps the per-tick positions of the first 16 slots (PROPOSED) of every pair until their first game
ends: one batched device copy per tick, one host read at the end. The runner renders two games per pair with
`viz/replay.render_replay` from a hand-built `Recording`: the first Strike win and the first hold among those slots.
Rows 1 and 2.1 interpolate per tick, as `scripts/nus_make_videos.py` does. Rung 6 renders the physics drones'
positions top-down, not a camera view. Output goes only to `runs/nus_port/phase4/<row>/videos/` (partner geometry);
records list the paths. Isaac camera clips stay OPEN (they would need `make_s2b_video.py` to take an in-memory
config and write under `runs/`).

### D7. The Isaac Lab rung, and the GPU

- **How `NusPolicy` drives tier 2.** Unchanged. It reads our observation. `NusHangarGame(cfg with backend "physics",
  world=IsaacWorld)` feeds it, as `score.py --presets physics` feeds scripted strategies. The commander copy, the
  filter on every pair, PX4 1.14's cascade with the drone's gains, the SIM-ONLY yaw-rate gains (named in the record),
  the rotor model and the PhysX bodies come from S2b unchanged. The policy's yaw rate and vertical speed are 0; PX4
  holds height.
- **Process.** `scripts/nus_phase4.py --row 6 --headless` keeps `score.py`'s order:
  1. stdlib-only imports at the top, and refusals before launch (cuda, headless, one size);
  2. `_isaac_app.start_headless`, and only then torch;
  3. one `IsaacWorld` of 1,000 games × 6 drones (`score._isaac_world_factory`, imported), reused for every pair with a
     fresh `NusHangarGame`.

  The world is the plain floor (E0). The walls are game clamps (`keep_in`). Drone bodies have no collision shape and
  the games are spaced apart (F11), so contact is measured by distance, as on tier 1. The run exits through
  `os._exit` after flushing.
- **Policy device.** The actors run on cuda on every row. Phase 3's parity was on the CPU, so Task 6 re-measures gate
  (a)'s error with the actor on cuda (INFO, same limit). If it misses, stop for the owner: the policy cannot fall back
  to the CPU inside the step (STANDARDS §6.1).
- **A free GPU for every row** (`train-run`). Before each row, `nvidia-smi` must show no other compute process beyond
  the preflight's 1024 MiB allowance: no NUS JAX job alongside, no AirStack simulator, no flight session, no other run.
  Rung 6 also needs `scripts/isaac_preflight.sh --approved-headless` with exit 0. The 5090's headless-on-WiFi approval
  is the owner's, of 18 November (commit `6472b548`); port plan item D9(b) is closed (F15). Exit 11 means wait.
- **Time.** Not estimated here (the game length is local). The runner prints an estimate from a 50-tick warm-up
  (PROPOSED). Records quote measured rates only.
- **Isaac Lab 3.0 later.** Nothing new is version-specific; only positions cross the new code, no quaternion.

### D8. Records, ledger and committed text

- **W3**: gated, PASS or FAIL. Its gates file is described in D2. **W4–W9**: rungs 1–6, one record per rung, INFO,
  each written as `records/<date>_nus_phase4_rung<k>_record.md`. A rung's record includes its lettered rows. A stopped
  rung writes an ABORTED record. W numbers are the workstation's; the laptop assigns T numbers at merge.
- **Gates files for W4–W9.** Each INFO run writes `gates.toml` with `gates = []`, plus the reading rules (D5) as text,
  before it starts.
- **Record contents.** Each record names the simulator on its first line and gives the §8 fields: commit, configs, the
  sha256 of every local file (rules, both deploy files, hangar, starts), checkpoint sha256s, parameter files, seeds,
  machine, games, throughput and video paths.
- **Numbers that equal a protected value.** The record payload holds measurements, counts and names only, through
  `write_record`. The protected set is the raw local values plus the derived values (Task 1), checked by six-digit
  rounding and by near-equality (relative 1e-6).
  - A rate is written as the text `k/n` beside its interval.
  - A colliding number reads "at the local value", and the full value stays in the git-ignored `scores.json`.
  - Metrics that are pinned to a local value by construction are always written that way, even when rounding hides
    the equality. `nus/ladder.py` lists them: closest approach held at a push radius, a reach time or end step at the
    game length.
- **Committed text check.** A test runs `check_payload` over the text of every Phase 4 `.md` record, the W3–W9 ledger
  rows, the summary page and HANDOFF. It skips without local files, and the laptop's scans cover the rest.
- **Summary page** `docs/NUS_PHASE4_RESULTS.md`, written after rung 6. It shows the ladder figure (Strike reach rate
  with intervals per row for the core pairs, parked baseline marked; numbered caption; no geometry drawn), made by the
  committed `scripts/make_nus_phase4_figures.py` from `nus/ladder.py`'s outputs. It gives a 2–3-sentence reading per
  rung.

## Tasks, in build order (test first; `train-change`; implementer writes, lead reviews)

0. **Gatekeeper re-read of v2.**
1. **Privacy first.**
   - **New local files.** Template and loader for `nus_hangar.toml` (refuses missing, unknown, `"LOCAL"` and
     wrong-type keys; a test that the file is git-ignored). `nus_make_local_deploy.py` gets `--weights-guard`,
     `--weights-strike` and `--out`; `--out` outside `configs/local/` is refused. A test checks that every other key
     equals W2's file.
   - **Literal scan.** Widen the G2 scan to `nus/hangar.py`, `nus/hangar_game.py`, `nus/players.py`, `nus/ladder.py`,
     `scripts/nus_phase4*.py` and `scripts/make_nus_phase4_figures.py`.
   - **Protected values.** Add the hangar file and the derived values to `protected_numbers`: every length key × scale,
     speeds in m/s, ticks and seconds = steps × hold, keep-outs, ring, disc and zone in metres.
   - **Record writer.** The `k/n`, "at the local value" and near-equality rules (D8), with a marker test.
   - **Committed text check** (D8).
   - **G4 marker test of the whole chain.** Marker local files → `hangar_cfg` → `play_replica` (rows 1, 2.1) and
     `NusHangarGame` rows 2–5 on the CPU, plus rung 6 with `TorchRigidBodyWorld` → starts file, runner outputs, videos,
     record, summary text, figure and the deploy-ref script. It fails on any marker outside `runs/` and `configs/local/`.
     Marker values must give a valid geometry.
2. **Core hook** `SvgGame._draw_starts`. Tests first: with a fixed seed, starts, arenas and a short game are
   bit-identical before and after; the full suite is unchanged. Separate commit, with a HANDOFF line for the other
   session.
3. **Configs.** `configs/nus_hangar_game.toml`, `configs/nus_phase4.toml` (`[ladder]`: games, seed, video slots,
   jitter, pair blocks, split trigger; `[[row]]`: the six keys) and `hangar_cfg`. Tests:
   - the crossed keep-out mapping;
   - every D1 key is set from a marker file;
   - the config passes `NusPolicy._check_cfg` and the stick-cap check;
   - the ring lies inside the walls;
   - the row lint (one key per row).
4. **`NusHangarGame`.** Fixed arena, paired starts and the parked variant, start miss, jump mode, `NusPushLayer`
   (fitted and identity), metric recording (same-team approach, correction size, smoothness, Guard 0 drift),
   video slots. Tests:
   - its starts equal the starts file;
   - jump mode moves a drone by the full step in one tick;
   - the layer swap (D3);
   - push-apart after a step with the filter off;
   - the physics refusal;
   - control equalities on a small CPU batch: 3a = 3h, 5a = 4.
   **4b** (only if the split is triggered): the partner push and Guard circle in metres for row 2.1, with the test
   2.1 = 1.
5. **Players.** `ApfGuard`, `ApfStrike`, `ParkedGuard`, the four bindings with `deploy_path`, the replica registry, and
   a jump-or-hold sampling flag. Tests:
   - the `check_strategy` contract;
   - the `SvgGame` controllers equal `NusApf` at every sample within 1e-4 units;
   - each binding loads its folder;
   - each name means the same player on rows 1 and 2.
6. **Replica engine and checks.** `nus/ladder.py:play_replica(sim, guard_player, strike_player, starts) -> MatchResult`,
   plus the metrics of D5. Tests:
   - on the same starts, the P3-against-APF path equals `play_arm` exactly;
   - closest approaches are checked by hand.
   Script modes: the cuda actor parity check (D7) and the W2 replay (D2).
7. **Runner** `scripts/nus_phase4.py --row <id> [--headless] --out runs/nus_port/phase4/<row>/`. It:
   - refuses an existing `scores.json`, and writes `gates.toml` first;
   - plays every pair, one batch per pair on the paired starts;
   - refuses non-finite values;
   - writes `scores.json`, `scores.md`, `per_game.npz` (under `runs/` only) and the record draft;
   - applies the reading rules and the split trigger.
   CPU tests on every row with tiny counts; rung 6 with `TorchRigidBodyWorld`.
8. **Videos.** The slot picker and the `Recording` builder. A test writes two files per pair under `tmp_path/runs/`.
9. **W3 run.** Convert archive entries 19 and 20; export the reference (`nus_jax`, CPU); add a second JAX action
   worker; write the gates file and the archive-arm pass rule before the run; run gates (a) and (b), both arms; make
   the videos (D2); write the record and ledger row. A FAIL stops the phase.
10. **Runs W4–W9**, rungs 1 to 6 in order, one row at a time, on a free GPU (`train-run`; rung 6 after preflight exit 0).
    Each rung gets a record, a ledger row, videos and the reading rules. The lead reads each record before the next
    rung.
11. **Summary and docs.** The figure script and `docs/NUS_PHASE4_RESULTS.md`, then a `train-gatekeeper` read of the
    records. HANDOFF §0/§4/§5. PLUG_IN "Plug in a trained NUS policy" (the ladder runner). The private notes and
    PORT_PLAN updated outside git. **Before merge:** the laptop privacy scans, and every diff and commit message read
    by eye for short partner numbers (G5/G6).

## Not in Phase 4

Training of any kind: no partner retraining with hold and delay (Phase 5 a), no port of the partner's method (5 b), no
fine-tuning (5 c). Also not in this phase:
- choosing Phase 5's route;
- other team sizes and our band arenas;
- changing the zone radius;
- the contact-tag track;
- Isaac camera clips;
- `score.py` changes;
- the AirStack simulator, any flight, a ROS 2 node, the final `interface.toml`, any change to CMU's filter or an
  AirStack config.

Nothing here authorises a flight.

## Stop point

After W9 and the summary page, the owner reads the ladder before choosing Phase 5's route (a, b or c, port plan §3). A
reading rule, a W3 FAIL or a failed cuda parity check stops the phase earlier, with a record.

## Open questions for the owner (with the plan's recommendation)

1. **Core hook** `_draw_starts` (one method extraction in `core/game.py`). Recommended: approve it as a separate
   commit on this branch, announced in HANDOFF.
2. **W3 before the ladder**, both arms of the frozen gate (b). Recommended: yes.
3. **Move action hold to rung 2?** Recommended: yes. A Starling can never fly the partner's one-tick jumps. Rung 2 would
   then hold, jump mode and row 3h would go, and 3a would be checked against rung 2. Until you approve, the plan keeps
   PORT_PLAN's order.
4. **Rung 2 push rule** `block` or `shove`. Recommended: `block` (each team keeps its own radius, as in the partner's
   rule). Split rows 2.1–2.2 run only on the trigger.
5. **±1 mm jitter on rung 5.** Recommended: yes; without it, 3-D changes nothing on tier 1.
6. **Arena side kept local.** Recommended: yes.
7. **Videos**: top-down, two games per pair. Recommended: yes now; Isaac camera clips later, if wanted.

## Owner answers (18 November 2026, ~05:00: "Accept all 7")

1. Core hook `SvgGame._draw_starts` in `core/game.py`: **approved** (minimal, own commit, test that the default random
   stream is unchanged).
2. **W3 first**: the reference policies (seed 2 generation 19 Guard, generation 20 Strike) through the frozen Phase 3
   gates before the ladder.
3. **Action hold moves into rung 2**: the partner policy acts once per partner step and its command is held for the
   step's ticks from rung 2 on, so rung 2 compares rules at the same timing. The separate hold row (3h) is dropped;
   the rest of the order is unchanged (each row still changes one key; control rows still checked game by game).
4. Rung 2 pair rule: **`block`**.
5. Rung 5: **±1 mm start-height jitter** (so 3-D has an effect in tier 1).
6. Arena side **stays in the local (git-ignored) file**.
7. **Top-down videos**, two games per matchup, every row.
