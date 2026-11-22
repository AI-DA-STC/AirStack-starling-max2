INTERNAL · reference page of the STE learning track, from the specialist draft `drafts/ARCHITECTURE_draft.md` (20 Nov 2026). **[PLAN.md](PLAN.md) takes precedence** where the two differ; its section 2 lists every change made at integration.
Source of truth for direction: [DISCUSSION_2026-11-19_20.md](DISCUSSION_2026-11-19_20.md) (D1–D9, P1–P8). Rules: `../../STANDARDS.md`.
Status labels follow STANDARDS: **FIXED**, **MEASURED**, **PROPOSED**, **OPEN**. **UNVERIFIED** marks an assumption this draft could not check.
`file:line` references are to the `ste-learning` worktree at `4422772d`.

# STE learning track: architecture

> **Integration notes (PLAN v2, 20 Nov).** (1) Team sizes are OPEN (P9: 1v1, 2v1, 3v3, 5v3 are studied in L0); the roster
> maxima and therefore M come from the sizes ruled at gate G0: M = 6 for a 3v3 track (15 filter pairs), M = 8 for 5v3 (28
> pairs). (2) Tag radius, zone radius and what a tag costs are OPEN until G0 (P1, P12, D2 revisit); `radius_m = 1.6` below
> is the PROPOSED value. (3) The game the track trains is pinned by `GAME_SPEC.md` (task L0.8), not by NUS's hangar files.
> (4) Option B is ruled at the L2 gate.

## 1. Components and data flow

```
 configs/ste_game.toml  configs/ste_train.toml  params/starling_physics_v1.toml
          |                     |                          |
          v                     v                          v
 +---------------- SteEnv (new, ste/env.py): one decision = hold_ticks game ticks ----------------+
 | reset: arenas, starts, ROSTER (random G, S inside fixed M = roster maxima), drop-out schedule|
 |   |                                                                                          |
 |   v                                                                                          |
 | observation  build_obs v0.3 (core/observations.py) on the ESTIMATED state  ---> [N, M, 81]   |
 |   |                                                                                          |
 |   v                                                                                          |
 | policy  (ste/policy_net.py)  Guard net shared by every Guard drone, Strike net likewise;     |
 |         learner's team = training net; other team = league slot (frozen net or scripted)    |
 |   |  action [N, M, 4] in [-1, 1], held for hold_ticks ticks                                  |
 |   v                         per tick (0.05 s):                                               |
 | command chain   team speed cap -> CommandChain (commander copy, models/command_chain.py)     |
 |                 -> safety filter, every pair, share mode B (core/safety_filter.py)           |
 |                 -> trajectory setpoint (p_sp, v_ff, a_ff)                                    |
 |   v                                                                                          |
 | physics drone   EstimatorEffect (new): delayed + noisy state -> Px4Cascade (200 Hz)          |
 |                 -> RotorModel -> wrench + drag (new) -> IsaacWorld / TorchRigidBodyWorld     |
 |   v                                                                                          |
 | rules  walls -> proximity tag 1-for-1 (new) -> tagged pair LANDS (filter obstacle)           |
 |        -> touchdown = out -> scheduled drop-out -> zone test   (all on TRUE state)           |
 |   v                                                                                          |
 | reward  team win/lose (+ optional tag and shaping terms)   info: tags, filter share, upset   |
 +----------------------------------------------------------------------------------------------+
          |  rollout (obs, central state, latents, alive mask, rewards, dones)
          v
 Learner (ste/learner.py, MAPPO generalised) <---- League (ste/league.py): latest / past / scripted
          |  checkpoints runs/<run>/ckpt/, league entries runs/<run>/league/
          v
 Evaluation (ste/evaluate.py + scripts/score.py via ste/strategy.py)  fixed suite, tier 1 / tier 2
          |  passes stages 3 and 4
          v
 Export (ste/export.py): policy.onnx + interface.toml, per team      ===== folder boundary =====
          v
 AirStack game node (SPEC ONLY, section 5): laptop, once per drone every 0.6 s -> teleop topic
          -> CMU commander + flight filter (option B setting) -> PX4 + EKF2 -> drone
```

Order inside one tick keeps the existing rule of `core/game.py:12-15`: move, walls, tags, drop-outs, then zone test. A Strike drone
tagged on the tick it enters the zone does not score.

## 2. Components

E = exists unchanged, X = extend, N = new. Roles: SWE = `ste-software-engineer`, QC = `ste-test-qc-engineer`, ARCH = this role;
advisers: DYN = `train-drone-dynamics`, ISL = `train-isaaclab-engineer`, MARL = `train-marl-researcher`, FIR =
`train-flight-interface-reviewer`.

| Component | E/X/N | Module | Owner (review) | Key interface | TOML keys |
|---|---|---|---|---|---|
| Game core | X | `core/game.py` | SWE (ARCH) | `SvgGame.step(actions) -> StepOut`; adds `status [N, M] int8`: 0 absent, 1 in game, 2 landing, 3 out; `alive = status == 1`; `flying = status in {1, 2}` | `[game] dropout_fraction` (exists, `core/game.py:188`), `[roster] guards_range`, `strikes_range` |
| Roster | N | `core/game.py` `_new_games` | SWE (MARL) | absent slots start with status 0 inside the fixed M of the world | `[roster]` |
| Proximity tag | N | `core/pair_rules.py` `proximity_tags` | SWE (ARCH, QC) | `(pos_m [N,M,3], alive [N,M], guards, radius_m, guard_survives [N]) -> (tagged [N,M], alive_after [N,M], partner [N,M] long)`; nearest pair first, one Guard with one Strike per pass, `min(G, S)` fixed passes inside (built, L0.9) | `[tag] mode = "off"` (default) or `"nearest_pair_1for1"`, `radius_m = 1.6`, `guard_survives_tag_prob = 0.0` (built, L0.9); `land_speed_mps = 0.6` comes with landing (L2.3) |
| Landing | N | `core/game.py` | SWE (FIR) | tagged drones get status 2, commanded `(0, 0, -land_speed)` by the game, stay filter rows; status 3 at `z <= touchdown_z_m`. Status 2 is exempt from the height-band floor: today `keep_in` clamps every drone to the 0.5 m floor (`core/game.py:296-299`) and `walls = "leave"` takes a drone below it out (`:301`), so a landing drone would otherwise hang at 0.5 m as an obstacle | `[tag] touchdown_z_m` (OPEN; 0.1 m PROPOSED) |
| Filter pairs and share | X | `core/safety_filter.py`, `core/safety_filter_graph.py`, `core/starling_layer.py:69` | SWE (FIR) | `filter_velocities(..., pair_share: Tensor [N, P, 2] or None)`; None = today's path. Pairs with a landing drone (status 2) are always 50/50, as flight keeps landing drones ordinary rows | `[filter] pairs = "all"`, `share = "guard_yields"` / `"equal"`, `emergency_share = "equal"`, `landing_share = "equal"` |
| Command chain | X | `models/command_chain.py:67-81` | SWE | passes `pair_share`; positions in = estimated state | none new |
| EKF2 effect | N | `models/estimator_effect.py` | SWE (DYN) | true state + estimate error (L1.1b): a first-order Gauss–Markov error per quantity (position, velocity, attitude as a small body rotation; sigma and tau each), drawn from its stationary distribution at each reset; white gyro noise on body rates; attitude never delayed; at most a small residual delay of position and velocity (≤ 0.05 s, fixed in code); seeded with the game seed | `params/starling_physics_v1.toml` [model] `state_error_*`, `state_noise_*`, `state_delay_s` (all OPEN at 0, L1.3) |
| Drag | N | `models/physics_drone.py:133` | SWE (DYN) | body-frame linear drag added to the wrench before `apply_wrench_b`, so the Isaac world and the torch oracle both get it | `[drag] linear_body = [dx, dy, dz]` (OPEN) |
| Physics layer | X | `core/physics_layer.py:115-137` | SWE (ISL) | `step(cmd, pos, flying, ...)`: restarts only drones with status 0 or 3 (today `~alive` restarts every drone that is out, `physics_layer.py:128-132`) | none new |
| Isaac adapter | E | `compat/isaaclab_232.py:148` `IsaacWorld` | ISL | unchanged; one world of N × M drones, M from the roster maxima (3v3 track: M = 6, 15 pairs) | none |
| Observation v0.3 | X | `core/observations.py:65` | ARCH (FIR) | `build_obs(...)` → `[N, M, 81]` (section 3) | `[game] interface_version = "0.3"` |
| Central state | X | `core/observations.py:103` | SWE (MARL) | entity list `[N, 8, 10]` (padded 5 + 3) + game `[N, 7]` for the team critic | none |
| Policy network | N | `ste/policy_net.py` | SWE (MARL) | `SteActor(obs [B, 81]) -> (mean [B, 4], log_std [B, 4])`; per-slot entity encoder plus masked attention pooling, no positional term | `[network] width`, `heads`, `layers` |
| Team critic | N | `ste/policy_net.py` | SWE (MARL) | `SteCritic(state) -> value [B]`, masked attention over live drones | as above |
| Environment wrapper | N | `ste/env.py` | SWE | `reset(n, gen) -> state`; `step(state, guard_a, strike_a) -> (state, out)`; one decision = `hold_ticks` ticks; same shape as `nus/tier1_env.py:239` | `[decision] hold_ticks = 12` (0.6 s) |
| Learner | N (from `nus/mappo.py`) | `ste/learner.py` | SWE (MARL) | `Rollout` plus `alive [T, N, A]` loss mask; GAE per team | `[learner] ...` (PPO settings) |
| League | N (from `nus/selfplay.py`) | `ste/league.py` | SWE (MARL) | `League.sample_blocks(n_games) -> slot_ids [N]`; frozen nets stacked with `torch.func.stack_module_state` and called with `vmap`; scripted slots never removed (STANDARDS §6.3) | `[league] mix = {latest, past, scripted}`, `snapshot_every`, `pool_max`, `past_weighting` |
| Strategy wrapper | N | `ste/strategy.py` | SWE | `Strategy` protocol (`core/strategy.py:18`) so `scripts/score.py` scores it unchanged | none |
| Evaluation | X | `scripts/score.py`, `core/metrics.py` | QC | fixed suite STANDARDS §7.4 plus the controls in section 6 | `configs/ste_gates_<run>.toml`, written first |
| Export | N | `ste/export.py`, `scripts/ste_export.py` | SWE (FIR) | `policy.onnx` + `interface.toml` per team (section 3); a full golden fixture stays in `tests/` | none |
| Videos | E/X | `viz/`, `compat/isaaclab_232.py:375` | SWE | every run (STANDARDS §8); Starling look (D9) | `[video]` |

**What must stay vectorised (STANDARDS §6.1).** Everything in `SteEnv.step`, the tag matching, landing, estimator, drag, filter,
observation, reward, rollout and league inference is a tensor operation over all games. The allowed fixed loops are: ticks of a
hold, physics sub-steps (`physics_drone.py:127`), filter sweeps, the `min(G, S)` tag-matching passes, PPO epochs and minibatches,
and opponent stacking once per league refresh. No `.cpu()`, `.item()` or NumPy in a step. The filter's `check_every` host sync
stays the one allowed exception.

**Who sees the true state and who sees the estimate (PROPOSED).**

| Consumer | Sees | Why |
|---|---|---|
| PX4 cascade | estimate | EKF2 feeds PX4's controller (D7) |
| Commander copy and filter | estimate | the flight commander reads `/{name}/odometry_conversion/odometry` (`swarm_commander.py:440`); that it carries EKF2's output is **UNVERIFIED** |
| Policy observation | estimate | the game node builds it from the same odometry |
| Tag, zone, walls, rewards | true | in flight the referee could use mocap, close to truth; the choice is **OPEN** (section 6) |

Tier 1 (the fitted backend) gets **no** estimator effect: its fitted delay already lumps estimator, radio and motors
(DISCUSSION §2.6). Adding one there would count the delay twice.

## 3. Interfaces to freeze early

| Interface | Proposal | Status |
|---|---|---|
| Observation | **v0.3 = v0.2 (73) + 8 landing flags appended at indices 73–80 = 81 numbers**; no index moves (the history rule of `core/observations.py:10-21`). **Not a pure append**: today a slot with present 0 is all zeros (`core/observations.py:77`); v0.3 fills a landing drone's slot (present 0, landing 1), so v0.3 is built from state, not derived from a v0.2 vector. In a game with no landing drone, indices 0–72 equal v0.2. Guard drone i sits in slot i, Strike drone j in slot `pad_guards + j` (pads 5 + 3, `_check_pads` at `:50-54`). The policy reshapes slots to `[8, 7]` entities, adds `landing` and an `is_teammate` bit derived from slot index and own team, and pools with masked attention. Team-size independence comes from the present flags and the order-free encoder; the 5 + 3 pads cap the size range, which matches STANDARDS §4's trained range | PROPOSED |
| Present flag semantics | present = 1 only for drones in the game (status 1); a landing drone has present 0 and landing 1, with relative position and velocity filled in; absent and out drones are all zero | PROPOSED |
| Action | `[vx, vy, vz, yaw_rate]` in [-1, 1]; velocity part capped at length 1 then times the team speed (`core/game.py:291`); world ENU; yaw rate may be held at 0 in training | FIXED (action, frame, rate: STANDARDS §3); scaling PROPOSED |
| Decision period | 12 ticks = 0.6 s, the action held between decisions (P1b, `nus/pilot.py:226`) | PROPOSED |
| Policy file | Two files per team, as STANDARDS §1.3 allows. `policy.onnx`: input `obs [B, 81] float32`, output `action_mean [B, 4]`, deterministic. `interface.toml`: STANDARDS §3 rule 1's fields plus `team`, `hold_ticks`, `tag_radius_m`, `filter_share`, the estimator and drag parameter set with sha256, `policy_schema = "ste-policy-1"`, the ONNX file's sha256 and 8 `[[golden]]` rows (81 inputs, 4 outputs) for the reload check. The `train-export` skill prescribes no format | PROPOSED; ONNX chosen because a torch install in the AirStack ground container is **UNVERIFIED** |
| Tag event | not produced yet (L0.9 keeps the pairs, `partner`, inside the step); intended: per game, a list of `(guard_index, strike_index, tick, distance_m)`; 3-D centre distance `< radius_m`; nearest pair first; both drones land unless `guard_survives_tag_prob` draws otherwise (0 = both, D2) | radius P1 OPEN; matching PROPOSED |
| Filter mode setting | `[filter] share`: `"equal"` (today) or `"guard_yields"` (option B: in a Guard–Strike pair the Guard takes the whole correction; Guard–Guard and Strike–Strike pairs 50/50); `emergency_share = "equal"` (the push-apart moves both drones) | P2 OPEN |

**Versioning.** The interface version rises with any layout or scaling change and is recorded in HANDOFF (STANDARDS §3 rule 3).
v0.3 is opt-in, like v0.2 (`obs_v02`, `core/observations.py:92`), so every v0.1 and v0.2 consumer (stand-in, NUS players, pilots)
stays unchanged. `policy_schema` versions the export separately from the observation. The filter and tag settings have no
version: their names and defaults are the contract, and the default (`"equal"`, no tag) reproduces today bit for bit.

**Option B mathematics.** Today a violated pair (violation c) moves drone i by `+c g / (2|g|²)` and drone j by the negative
(`core/safety_filter.py:190-200`). With shares `σ_i + σ_j = 1`: `Δv_i = σ_i c g / |g|²`, `Δv_j = -σ_j c g / |g|²`; `(½, ½)` is today,
`(1, 0)` is the flight `fixed` per pair (`cbf_filter.py:341`). A share-0 drone does not count that pair in its averaging weight;
pruning follows `cbf_filter.py:207-214`. Both training paths refuse `fixed` today (`safety_filter.py:121`,
`safety_filter_graph.py:213`), and the flight `fixed` is per drone (it would also hold a Strike drone in its Strike–Strike pairs),
so both copies need a per-pair share.

## 4. Reuse plan (NUS-port code becomes STE's own trainer)

| NUS-port code | Reused | Changed for STE |
|---|---|---|
| `nus/mappo.py` (PPO, GAE, AdamW, global-norm clip, entropy of the squashed policy, NaN abort) | the update maths (`:215-420`), copied into `ste/learner.py` | MLP `Trunk` → attention actor and critic; `ACTION_DIM` 2/3 → 4; `Rollout` (`:249`) gains an alive mask so dead and absent drones add no loss; no `NusMethod`, `deploy.*`, `configs/local` or partner reward; reads `configs/ste_train.toml` |
| `nus/selfplay.py` (archive, best-snapshot selection, resumable state, SIGINT stop, deadline) | checkpoint, resume and stop logic (`:140-299`) | alternating fresh learner per generation → **league**: both teams train in the same run, each against blocks of latest / past / scripted opponents (DESIGN §6: about 40 / 35 / 25 %); past entries weighted towards those that still win; `OpponentPool` (`:61`) stacks MLP trees only → stack any `nn.Module` with `torch.func` |
| `nus/tier1_env.py` (decision hold, critic state, per-game counters, recording for videos) | the env shape (`reset`, `observe`, `central_state`, `step`, `begin_recording`) | the hangar game → `SvgGame` with `[roster]`, `[tag]`, `[filter]`, `[estimator]`; `hold_ticks` from STE's own key, not NUS's deploy file (`:158`); APF slot → `opponents/scripted.py` registry plus frozen G19/S20 as fixed slots |
| `nus/pilot.py` `DecisionHoldEnv`, `HeldStrategy`, `zero_mean_head` | kept as they are (P1b's two fixes) | none |
| `scripts/train_standin.py` `WorldSlice` (`:247`), interface writer (`:822-880`) | evaluating on a slice of the training Isaac world; the interface.toml writer | new fields (section 3) |
| `nus/crossplay.py` | cross-play matrix and intervals | used for the league's cross-play table (STANDARDS §7.4) |

The NUS files stay untouched. Their parity tests pin them to NUS's recipe, and D8 pauses that route. Variable team size uses an initial
roster mask inside a fixed M taken from the `[roster]` maxima (3v3 track: M = 6; a fixed 8 would cost 28 filter pairs instead of 15 and make the P3 number unrepresentative), with the observation pads kept at 5 + 3: `SvgGame` and `IsaacWorld` are fixed-size (`physics_layer.py:67-70`), so environments per team size
are the wrong route. Tier 1 runs the same `SteEnv` with `backend = "fitted"` for quick experiments (D3).

## 5. Flight-side contract (spec for an AirStack session, owner-gated, D4)

**A. Filter change** (`cbf_filter.py`, `swarm_commander.py`).
1. `filter_velocities(..., pair_share=None)`, where `pair_share` has shape `(P, 2)`. None keeps today's code path untouched.
2. New commander parameters `cbf_share_mode` (`''` default, or `'guard_yields'`), `cbf_guard_drones` and `cbf_strike_drones`. The
   team list belongs to the commander, because the filter runs there (`swarm_commander.py:2141-2147`).
3. Emergency push-apart stays 50/50. Climb-out and landing drones stay ordinary 50/50 rows, as today ("only ACTIVE drones are
   eligible"). `cbf_exempt_drones` keeps its meaning.
4. **Equal-output test**, setting off: outputs must be **bit-identical**, not merely close, to main before the change. It covers
   recorded or scripted inputs of every existing scenario and config: figure-8 (`figure_eight_two_ours`,
   `figure_eight_rc_intruder`), random goals (`random_goals_two_ours`), goal configs (`goal_single*`, `goal_two_ours`,
   `goal_swap_two_ours`, `goal_tracking*`, `goal_sequence`), squeeze (`squeeze_3drone`, `squeeze_rc_intruder`, `hybrid_squeeze`),
   teleop (`teleop_*`), swarm (`swarm_real*`, `swarm_sim`) and `cbf_sim`. The existing `test/test_cbf.py` and `test/test_exempt.py`
   must pass unchanged.
5. **Parity with the training copy**, setting on. `svg_training` ships golden vectors from its filter copy, and the flight copy must
   meet the FIXED filter gates (`configs/s1.toml [filter_gates]`: speed difference ≤ 0.02 m/s, residual ≤ 2e-3, emergency
   agreement ≥ 0.99). No flight original of option B exists, so the training copy is the reference.

**B. Game node** (new, additive, launched only by new `*_game` configs).
1. Load `policy.onnx` and `interface.toml`. Refuse to start if the `[[golden]]` outputs differ, or if
   `interface_version`, `hold_ticks`, the team speeds or `filter_share` disagree with the commander's parameters.
2. Subscribe to every drone's odometry (the commander's topic). Build v0.3 observations with a port of `build_obs`, kept in parity
   by a golden test against `svg_training` outputs on recorded states.
3. Every 0.6 s, run the team policy once per drone (batched). Publish `TwistStamped` world ENU on `/svg/{name}/teleop_command`.
   **Republish the held command at 20 Hz**: `teleop_timeout_s` is 0.5 s, shorter than the 0.6 s decision, so without it the
   commander falls back to hold.
4. Enter through teleop, because the training commander copy is the teleop law. The `*_game` config must list the game drones as
   teleop drones; `cbf_sim.yaml` lists none (STANDARDS §3).
5. Referee: tag at 3-D centre distance < radius, 1-for-1, nearest pair first. Then land the pair. `~/land` lands every commanded
   drone (`swarm_commander.py:1612-1626`), which is enough for 1v1, where the first tag ends the game. 3v3 in the AirStack simulator
   needs a per-drone land service (a commander change). A Strike reach or the time-out logs and lands all.
6. Log every decision, observation, action, tag and filter correction to a bag for the stage-6 comparison.

**C. Off by default and separation.** No existing launch file, scenario or `_ours` config changes. There is one "game mode:
experimental, not for flight" doc page and a `CHANGES.md` entry. A normal-scenario AirStack-simulator flight is required before the
next real flight. Real drones use game mode only after PREFLIGHT is updated and the owner approves.

## 6. Risks, owner decisions, unverified assumptions

| Risk | Limit or check |
|---|---|
| Tier 2 3v3 with a learner may be too slow (tier 1 is about 2.7× faster at 5v3, DISCUSSION §2.6; 3v3 with a learner on the 5090 is not measured) | P3 measures it first; tier 1 for sweeps; graph filter (`filter_cuda_graph`, T8 PASS) |
| A 1.6 m radius favours a parked Guard (DISCUSSION §2.9) | evaluation control: `players.ParkedGuard` (`nus/players.py:108`) and the T41 Guard as fixed rows; gate the trained Guard above the parked one |
| Option B lets the Strike team use the Guards as walls without paying; the "filter as a wall" effect flips sides | report the filter share per team; P8 decides whether Strike drones are assumed to run a filter |
| Landing drones are slow obstacles that the policy cannot see as present | landing flag in v0.3; landing-collision count in the safety group |
| The physics layer restarts every drone that is out each tick; landing needs `flying`, not `alive` | unit test: a landing drone keeps its height trajectory and stays in the pair mask until touchdown |
| Estimator delay is applied in the commander and filter too: filter closest-approach may change | re-run the filter-breach metric (`info["rule_breach"]`, `core/game.py:340`) with the estimator on and off |
| Isaac Lab drones have no colliders (`docs/S2B_RESULTS.md:39`): tags and crashes are rules, not physics | accepted; stated in every record |
| The AirStack-simulator rung differs for reasons that are not the policy: speed-only MAVROS route, PX4 clock about 1.9× the commander's, SIM-ONLY rate gains (STANDARDS §5 command-route rows, rule 8) | compare against a tier 1 run on the `airstack_sim` parameter set (STANDARDS §5 rule 3), not only against training; the stage-6 gap limit is OPEN |
| Landing drones hang at the height-band floor | status 2 exempt from the floor clamp; unit test that a tagged drone reaches `touchdown_z_m` |

**Decisions that need the owner.**

| Item | What this architecture needs |
|---|---|
| P1 tag radius 1.6 m | `[tag] radius_m`. **RULED 22 Nov 2026** ([DISCUSSION §14](DISCUSSION_2026-11-19_20.md#14-gate-g0-rulings-owner-22-nov-2026)): the main game has a 1-for-1 tag, 1.6 m to build the pipeline, 1.15 m main training after L2; STANDARDS §4 "Tag" is changed. Still to change with it: "Safety filter in the game", §5 rule 7 ("once per team"), AGENTS_AND_SKILLS "Rejected: a tag radius", and the `train-marl-researcher` body ("there is no tag radius") |
| P2 option B | `[filter] share`; flight change A |
| P3 | throughput step before any long run |
| P7 drop-out part of the game | `[game] dropout_fraction > 0` and the roster in evaluation |
| P8 | whether a Strike-runs-no-filter variant is trained (filter pairs Guard-only) |
| Referee truth (new, OPEN) | whether the flight referee uses mocap or EKF2 odometry; training uses truth |
| `touchdown_z_m`, drag values (new, OPEN) | Pegasus's `LinearDrag([0.50, 0.30, 0.0])` (`starling2max.py:41`) equals the Iris default (`iris.py:30`): not a Starling measurement; STANDARDS §5 says drag is "not identified". Training values come from logs (§5 rule 10) |

**Assumptions not verified.**
- That `/{name}/odometry_conversion/odometry` is EKF2's estimate, and its latency.
- That onnxruntime, or torch, can be installed in the AirStack ground container. The VOXL 2 running the network is also unverified
  (DISCUSSION §2.10).
- That attention pooling over 8 entities trains at 3v3 in the GPU-hour budget, which is not measured.
- That the `share` generalisation keeps the T2 parity bit for bit at `"equal"`. It must be a test before the change, against tensors
  saved first.
