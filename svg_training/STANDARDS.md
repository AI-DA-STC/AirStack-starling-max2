# Standards — svg_training

The rules every change in this folder follows. Precedence: the owner's explicit instruction, then the
repository's iron rules ([../CLAUDE.md](../CLAUDE.md)), then this file, then taste.

Status labels used in the tables below:

| Label | Meaning |
|---|---|
| **FIXED** | set by the programme or by the flight stack; this folder may not change it |
| **MEASURED** | taken from a record in this repository; the source is named |
| **PROPOSED** | this folder's working value, not agreed with the owner or the partners; may change |
| **OPEN** | no value yet; a decision is needed before the stage that uses it |

## 1. Scope

1. This folder holds the training pipeline, stages 1 to 5 ([docs/DESIGN.md](docs/DESIGN.md) §3):
   identify, train, evaluate, cross-check, export.
2. Sessions working on the pipeline write **only** inside `svg_training/`. Reading anywhere is fine.
   One exception, approved by the owner on 14 November 2026: a session may **run** `tools/sim.sh`
   (the AirStack simulator) to record the velocity-step logs for stage 1. Running is approved; editing
   anything under `tools/` is not. What the tool itself writes under `docs/record/` follows the
   repository's own standards. Approved by the owner on 15 November 2026 (final S1 review, item I7):
   `scripts/record_steps.sh` may make its guarded writes outside this folder — the bag folder
   `AirStack/robot/ros_ws/bags/`, `~/flight_logs/sim/_stack/` and the simulator test lock.
3. Stages 6 and 7 (simulated flight in AirStack, real flight) belong to the existing flight stack and
   its documents. This folder hands them two files, a policy and an interface file, and nothing else.
4. Anything that needs an edit outside this folder (a ROS 2 node for the policy, a new AirStack
   config, a link from the repository's docs) is a separate request to the owner. The standing
   exception is the change-log line in `docs/record/CHANGES.md` that the repository's hook demands
   for a `docker/` change.
5. Not in scope: changing drone parameters, AirStack configs, the sim airframe, the mocap bridge, the
   website.

## 2. Wording

The programme's wording rules apply to every document and figure here
(`~/Documents/GitHub/Strike-Versus-Guard/STANDARDS.md` §1–2).

| Avoid | Use |
|---|---|
| attacker, intruder, enemy, hostile | Strike team, the other team |
| defender, defend, protect | Guard team, hold the zone |
| intercept, neutralise, engage, kill | tag, reach, score |
| target | goal, zone |
| swarm | drone team, team of drones |
| counter-UAS, defence, area denial | decentralised multi-drone autonomy |
| under mocap | with motion capture; "camera-only" for flight without it |
| validated, proven (for a simulator result) | observed in the training simulator |

- Paper titles and library names keep their published wording.
- Three simulators exist; name the one you mean every time: **training simulator** (tier 1 or
  tier 2), **AirStack simulator** (Isaac Sim + Pegasus + PX4 software), **real flight**.
- British spelling, short sentences, plain present tense. One number per claim, with its source.
- A figure caption is 2–4 sentences. A results paragraph is 2–3 sentences.
- Partner order: ST Engineering, NUS, UPenn, CMU. HTX is the funder.
- Programme reports marked confidential (the FR&PDR, the monthly reports) are not quoted or copied here. Point to
  them by name.
- **Partner privacy, NUS** (owner, 18 November 2026; replaces the rule of 15–17 November that kept every NUS value
  out of git). NUS agreed that their code details, their game settings and our results on their code may be
  published in this repository, which is public. So documents, records, the ledger, figures, videos and commit
  messages may state NUS's settings and our numbers ([docs/NUS_PORT.md](docs/NUS_PORT.md)). Still kept out:
  **NUS's source code itself** (it stays in NUS's own repository; describe it in words and cite `file:line`, never
  paste a block or vendor a file) and quotes from confidential programme reports. Code keeps reading NUS's values
  from the git-ignored `configs/local/` files (mechanism unchanged), and the record writers keep marking them.
  Tests: `tests/test_partner_privacy.py` (no NUS source file, block or path tracked; no local value hard-coded in
  code or configs). Any other partner's values stay local until that partner agrees.
- **The PROVISIONAL bundle** (owner decision 6, 18 November 2026). The lab's converted NUS weights (G19, S20, P3G, P3S),
  its local settings files and its recordings of NUS's game are committed in [nus_provisional/](nus_provisional/README.md),
  labelled PROVISIONAL (trained by the lab with NUS's code, 8 generations, hangar set-up; kept so anyone can repeat our
  numbers exactly; not final; NUS will retrain), byte-identical, with a sha256 list. That folder, and only that folder,
  may hold NUS's values and checkpoint files: the privacy tests exempt it and nothing else. Code still never reads it
  and never hard-codes a NUS value; `scripts/nus_install_provisional.sh` copies it into the git-ignored `configs/local/`
  and `runs/nus_port/`, which stay git-ignored. The motion-capture camera survey and NUS's source code stay out.
- **NUS's own words** (owner, 18 November 2026): NUS's terms (defender, attacker, area denial) may appear once per page
  in a translation line, for example "your defender = our Guard team, your attacker = our Strike team"; the rest of
  the page uses our words.
- **A tag is physical contact** between a Guard drone and a Strike drone (owner, 14 November 2026).
  Write "tag" or "contact tag". The programme's public pages do not describe contact between drones. The
  contact-tag track ([plan](docs/plans/2026-11-17-contact-tag-track.md), DRAFT) may be described in this
  repository's public documents (owner, 18 November 2026; until then it was kept out of public and
  partner-facing material). The programme website still needs the owner's say-so.
- Plain language (owner, 15 November 2026): everyday words first and the term second, explained at
  first use; short sentences; write for a reader new to training. Every page that claims a result
  shows it with a generated figure or a diagram.

## 3. Policy interface (version 0.1, PROPOSED)

Version history: 0 = the S2 layout of 69 observation numbers; 0.1 (16 November 2026) = 71 numbers, the zone
centre added at the end, no earlier index moved (`INTERFACE_VERSION` in `core/observations.py`).

The interface copies what the flight stack already does, so a policy needs no translation layer.
It becomes FIXED when the velocity contract with NUS and CMU is written (Linear NEAR-874).

| Item | Value | Status | Source |
|---|---|---|---|
| Action, per drone | `[vx, vy, vz, yaw_rate]` | FIXED | programme command chain; `swarm_commander.py` teleop handler |
| Frame and units | world ENU (x east, y north, z up), m/s and rad/s | FIXED | `swarm_commander.py` (`/svg/{name}/teleop_command`, `TwistStamped`) |
| Rate | 20 commands a second | FIXED | `control_rate_hz: 20.0` in every `_ours` config |
| Stale command | no fresh command for 0.5 s → hold position | FIXED | `teleop_timeout_s: 0.5` |
| Policy output range | `[-1, 1]` per axis, scaled by the speed cap of the game config | PROPOSED | — |
| Speed cap, real flights | 1.0 m/s after the safety filter; 0.5 m/s for commands entering as teleop | MEASURED | `goal_two_ours.yaml`, `teleop_real_ours.yaml` |
| Speed cap, AirStack simulator | 4.0 m/s after the safety filter; commands entering as teleop are capped at the 1.2 m/s default, and `cbf_sim.yaml` lists no teleop drones, so no drone listens on the plug-in topic in that config | MEASURED | `cbf_sim.yaml`, `swarm_commander.py` defaults |
| Observation, own drone | position and velocity relative to the zone centre, yaw | PROPOSED | — |
| Observation, others | padded lists of team-mates and of the other team: relative position, relative velocity, present flag; a drone hidden behind a structure is masked, with its last seen position and the time since | PROPOSED | [docs/RESEARCH.md](docs/RESEARCH.md) §10 |
| Observation, surroundings | 32–64 range rays (a horizontal ring, plus up and down); the number is set from the S0 measurements | PROPOSED | RESEARCH §10 |
| What the real drone senses its surroundings with | OPEN: a known map (the accepted first step in published work), or an on-board range sensor | OPEN | owner |
| Observation, game | zone radius, arena half-side, the zone centre's position from the arena centre (so a drone can place the walls), time left, own team. As built in S2: 71 numbers per drone, full view of every drone; layout in `core/observations.py` and [docs/PLUG_IN.md](docs/PLUG_IN.md) | PROPOSED | layout change 16 Nov 2026 (S2 Task 9 review): 69 → 71 numbers, zone centre added at the end; no earlier index moved |
| What a drone may know about others | OPEN: full state of every drone, or only what its team shares, with delay and drop-outs | OPEN | owner + partners |

Rules:

1. Every exported policy ships with an **interface file** (`interface.toml`): interface version,
   observation layout and order, action scaling, rate, frames, the game config, the drone-model
   parameter set, the git commit and the seed. A policy without one is not handed over.
2. The policy runs once per drone on that drone's own observation (decentralised execution). A
   centralised critic may see everything during training only.
3. A change to the layout or scaling raises the interface version and is written in
   [docs/claude/HANDOFF.md](docs/claude/HANDOFF.md).
4. Use 3 (flight control) has a different action, collective thrust and body rates, and gets its own
   interface version when that work starts.

## 4. Game specification (version 0)

Only the first three rows are settled. The rest are working values so that building can start; they
are parameters in one game config, never constants in code.

| Parameter | Value | Status | Source |
|---|---|---|---|
| Teams | the Guard team holds a circular zone; the Strike team tries to reach it | FIXED | programme benchmark |
| Team sizes of interest | 2 Guard against 1 Strike; 5 Guard against 3 Strike | FIXED | programme simulation page |
| Speed ratio | Strike drones 1.5 times as fast as Guard drones | FIXED | NUS partner page |
| Speeds in metres per second | Strike 0.5 m/s, Guard 0.33 m/s: the real stick cap and cap ÷ 1.5; a setting up to the commander's cap | FIXED | owner, 15 November 2026 |
| How the ratio is enforced | by scaling each team's policy output before the safety filter; the filter keeps its single cap for every drone, as in flight, so a Guard drone giving way may briefly exceed its own team's speed | PROPOSED | `cbf_filter.py` takes one cap for all drones |
| Safety filter in the game | side quest (contact tags): acts between drones of the **same team** only. Main game with the Starling layer: as on the real drones, every pair (S2 design §4a) | FIXED | owner, 14 and 15 November 2026 |
| Structures | a drone that touches a structure leaves the game; avoiding structures is learned. The flight stack has no obstacle avoidance, only a box fence | PROPOSED | `fence.py` |
| Trained size range | 1–5 Guard, 1–3 Strike, drawn per game | PROPOSED | — |
| Strike scores | a Strike drone is inside the zone | PROPOSED | S2: `configs/s2_game.toml` `[partner_rules] win_steps_in_zone` (one step) |
| Tag | **side quest only** (owner, 15 November 2026): physical contact between a Guard drone and a Strike drone; there is no tag radius. The main game has no tag: the partner rules preset keeps opposite teams apart ([docs/specs/2026-11-15-s2-game-and-plug-in-design.md](docs/specs/2026-11-15-s2-game-and-plug-in-design.md) §4a) | FIXED | owner, 14 and 15 November 2026 |
| Contact, tier 1 | the two centres closer than **0.50 m**: twice the 0.248 m radius of the smallest sphere that encloses the airframe with its propellers. A property of the airframe, not a game rule; a sphere is slightly generous | MEASURED | vertices of `AirStack/simulation/isaac-sim/assets/robots/starling2max.usd`, read 14 November 2026 |
| Contact, tier 2 | a PhysX contact between the two bodies | PROPOSED | — |
| After a tag, Strike drone | it goes down: it leaves the game | FIXED | owner, 14 November 2026 |
| After a tag, Guard drone | it leaves too by default: setting `guard_survives_tag_prob` = 0 (both leave); training may draw it per game; evaluation reports 0 and 1 separately | FIXED | owner, 15 November 2026 |
| Game length | 60 s (1,200 steps) | PROPOSED | S2: `configs/s2_game.toml` `[partner_rules] game_steps` |
| Arena, lab scale | goals are drawn from a 3 × 3 m box, 0.5–1.8 m high; the boundary that acts on a drone is the 6.5 × 6.5 × 4 m keep-in fence (x, y −3.25…3.25 m, z 0…4 m, centred on the mocap origin; CHG-0072, 16 Nov; was 4 × 4 × 4 m, CHG-0062) | MEASURED | `goal_two_ours.yaml` (`arena_low/high`, `fence_min/max`), read 18 Nov 2026 (owner approved the correction) |
| Environments | games are played in realistic 3D environments, the construction-site world first; an empty arena is only the first build step | FIXED | owner, 14 November 2026 |
| Environment ladder | E0 open arena; E1 random blocks and columns; E2 the construction-site world plus E1 clutter; E3 more worlds, one held out; E4 a scanned real place; E5 a camera-ready copy | PROPOSED | [docs/DESIGN.md](docs/DESIGN.md) §7 |
| Per game | its own placement in the world, start positions and clutter | PROPOSED | RESEARCH §10 |
| The zone's size and place in each world; the playing volume | OPEN | OPEN | owner |
| Zone radius | OPEN in metres; NUS's balanced ratio is in the October 2026 monthly report | OPEN | owner + NUS; S2 draws 10–25 % of the arena side, `configs/s2_game.toml` `[arena] zone_radius_frac` |
| Height | games are scored in the horizontal plane; height is held in a band at first | PROPOSED | S2: `configs/s2_game.toml` `[arena] height_band_m`, `start_height_m`; S2 also reports closest approach in 3-D ([docs/S2_RESULTS.md](docs/S2_RESULTS.md)) |
| Drop-out | a drone is removed at a random time in a set fraction of games | PROPOSED | S2: `configs/s2_game.toml` `[game] dropout_fraction` (0) |
| Start positions | anywhere in the playing volume that is clear of structures and respects the keep-out distance within a team, drawn per game | PROPOSED | [docs/RESEARCH.md](docs/RESEARCH.md) §7; S2 open arena: rings, `configs/s2_game.toml` `[starts]` |

## 5. Drone models

There are two, and they must agree (stage 4 checks that they do).

**Tier 1, response model.** Everything between the policy's velocity command and the drone's next
measured state, as one batched PyTorch model: the ground controller's command shaping, PX4's
position and velocity loops, attitude lag, delay, limits.

**Tier 2, rigid body.** The Starling as a rigid body with four rotors in Isaac Lab, flown by a batched port of PX4's
control cascade. Since S2b (the *physics drone*, [S2B_RESULTS](docs/S2B_RESULTS.md)) each drone is one PhysX rigid
body pushed by our own rotor model (`models/starling_airframe.py`: measured motor lag, one force and torque per
drone), not `isaaclab_contrib` `Multirotor` + `Thruster`, which needs thruster joints the Starling model lacks (S2b
plan D2).

| Quantity | Value | Status | Source |
|---|---|---|---|
| Mass | 0.557 kg | MEASURED | `docs/CONFIG.md`; CMU system identification (`isaac_sim/Starling 2 Max Sys ID Results - Slite.pdf`) |
| Inertia (roll, pitch, yaw) | 0.002943, 0.001857, 0.004649 kg·m² | MEASURED | `docs/CONFIG.md` (axis order to be confirmed against the PDF) |
| Thrust coefficient | 3.964738e-6 N/(rad/s)² | MEASURED | same PDF |
| Moment coefficient | 5.38697e-8 N·m/(rad/s)² | MEASURED | same PDF |
| Motor time constant | 55 ms rising, 85 ms falling (72 ms average) | MEASURED | same PDF |
| Maximum rotor speed | 1,450 rad/s | MEASURED | `docs/CONFIG.md` |
| Rotor positions | sim CAD ±0.095 / ±0.13 m; drone parameters ±0.085 / ±0.0625 m. Tier 2's body uses CAD; PX4's motor mixing uses the drone's parameters, as on the drone | FIXED for tier 2 (owner's answer 2, 16 November 2026); which layout the real drone has is not measured | `docs/CONFIG.md` records both; S2b plan D4: CAD and inertia come from the same system identification |
| Drag | not identified | OPEN | — |
| PX4 velocity loop gains, horizontal | P 1.8, I 0.4, D 0.2 | MEASURED | `starling_1_indoor_params.params` (`MPC_XY_VEL_*_ACC`) |
| PX4 position gains | horizontal 0.95, vertical 5; vertical velocity P 8 | MEASURED | same file |
| PX4 limits on the drone | 3 m/s horizontal, 2 m/s up, 0.6 m/s down, tilt 45° | MEASURED | same file; `docs/CONFIG.md` states 20 m/s. The 13 November flight logs show 3.0 m/s on both drones, tilt 30° on drone_1 and 45° on drone_2 ([exploratory record §1](records/2026-11-15_s1_real_px4_exploratory.md#1-the-path-a-teleop-command-takes-on-the-real-drone)) |
| Command route, real drone | not a bare velocity: the commander sends a trajectory setpoint (position + speed + acceleration) through `px4_interface` TRAJECTORY mode; PX4 1.14 flies `speed = sent speed + 0.95 × (position setpoint − position)`; clocks agree (ratio 1.01) | MEASURED | [exploratory record §1, §4](records/2026-11-15_s1_real_px4_exploratory.md#1-the-path-a-teleop-command-takes-on-the-real-drone): `MPC_XY_P` 0.95 read from the ulogs; a least-squares fit to the log gives 0.98 |
| Response of the real drone to that setpoint | close to the setpoint's speed delayed by about 0.1–0.15 s, at up to 0.5 m/s: held-out RMS 0.058 m/s for the fitted model and for a plain 0.15 s delay (0.095 with no delay); misses the overshoot (up to 1.31×) and the slow drift after release (−0.14×) | MEASURED, exploratory (no gates, one flight) | [exploratory record §4](records/2026-11-15_s1_real_px4_exploratory.md#4-results); `params/real_exploratory_v0.toml` |
| Command route, AirStack simulator | speed only, through MAVROS (`setpoint_raw/local`) to PX4 1.16.1; the commander moves its reference point on the wall clock while PX4 runs 1.907 times faster (1.73–1.97 within the session), so a held push sags to about half speed and swings back on release | MEASURED | [T3 record](records/2026-11-15_s1_fit_v0_record.md#time-scale--measured); [cause notes](docs/notes/s1_two_clocks_cause.md) (replay within 0.019 m/s) |
| Response to a bare velocity command | 0.15 s delay plus 0.55 s lag; the real drone does not take this route today (row above) | MEASURED | `svg_ground_control/trajectory.py` header: one CMU log, drone_2 at 5 m/s, 20 September 2026; not measured on our drones or at lab speeds |
| Response with acceleration feed-forward | about 0.1 s lag | MEASURED | same header; `docs/ARCHITECTURE.md` |
| Safety filter in flight today | keep-out radius 0.55 m (1.10 m centre to centre), alpha 2.5, 20 Hz, **every pair of drones**; the flight stack has no notion of teams | FIXED | `cbf_filter.py`, `swarm_commander.py`, `_ours` configs |

Rules:

1. **Identify at the plug-in point.** The response model is fitted to velocity steps injected where
   the policy will plug in, so it includes the ground controller's shaping (reference point, leash,
   acceleration ramp), not PX4 alone. The real drone and the AirStack simulator use different
   command routes today (NEAR-866); fit each and keep both parameter sets.
2. **Tier 2's control gains come from the drone's parameter file**, never from the sim airframe,
   whose rate gains are halved on purpose (iron rule 9). One exception, the owner's ruling of 16 November 2026:
   the physics drone uses the AirStack simulator's SIM-ONLY yaw-rate gains `MC_YAWRATE_P/I/D` 0.25 / 0.2 / 0
   (`params/sim_only_yaw_v0.toml`, precedent CHG-0024), because with the drone's own the modelled yaw does not
   settle. They are never a drone value, and every record names the yaw gains it used. A tier 1 parameter set fitted to AirStack
   simulator logs is a different thing: it describes that simulator and is used to predict stage 6.
3. **Two tier 1 parameter sets**: `airstack_sim` (fitted to the AirStack simulator) and `real`
   (fitted to the drone). Training uses `real` with small random variation around it (rule 10);
   `airstack_sim` predicts stage 6; evaluation reports each separately (PROPOSED).
4. Every model parameter set is a named, versioned file with its source log. A policy records which
   set it trained on.
5. Randomise around the fitted values, do not replace fitting with wide randomisation
   ([docs/RESEARCH.md](docs/RESEARCH.md) §4). Ranges are part of the parameter set.
6. Delay is modelled explicitly in both tiers.
7. The safety filter in training is a port of `cbf_filter.py` and is tested against the original on
   recorded inputs: same inputs, same outputs, within a stated tolerance. In the game it runs once
   per team, on that team's drones only. The flight stack cannot do that today: its filter keeps
   every pair apart, so a policy that tags by contact cannot fly until CMU's filter takes a pair
   mask. That change is outside this folder.
8. **PX4 versions differ**: the drone runs PX4 1.14, the AirStack simulator 1.16.1. Both tiers copy
   the drone's version of the control law. Between the two versions the position step is unchanged and
   the velocity loop differs (new notch and low-pass filters, restructured anti-windup) (MEASURED,
   [S1 plan, facts](docs/plans/2026-11-15-s1-drone-model-and-safety-filter.md#facts-this-plan-rests-on-s1-research-15-november-2026)).
   The routes differ more than the versions (MEASURED, S1): the drone gets a trajectory setpoint
   through `px4_interface`, the simulator a speed only through MAVROS, with its PX4 clock about 1.9
   times the commander's ([exploratory record §6](records/2026-11-15_s1_real_px4_exploratory.md#6-real-drone-and-airstack-simulator-side-by-side)).
9. **Unit trap**: Isaac Lab's `ThrusterCfg.thrust_const_range` is in N/(revolutions per second)²; the
   identified thrust coefficient is in N/(rad/s)². Convert, and test the hover thrust. (S2b's own rotor model uses
   N/(rad/s)² throughout, so the trap does not arise there; it applies to any use of `Thruster`.)
10. **The drone model for training is fitted from real flight logs; simulator fits describe the
    simulator only** (owner, 15 November 2026; FIXED). The AirStack simulator feeds PX4 by a different
    route and clock (rule 8), so its fit would teach a policy the wrong drone. The `real` set gets its
    run of record from planned pushes at a real flight
    ([S1_RESULTS](docs/S1_RESULTS.md#what-the-owner-needs-to-do-next)).

**World models.** Both tiers take the world from the same source file, so they cannot drift apart.

| Quantity | Value | Status | Source |
|---|---|---|---|
| Construction-site world | 546 × 575 × 137 m, 5,622 meshes, 5.79 million triangles, Z up, metres; collision shapes already applied; a 40 m crop exists | MEASURED | `localisation/scenes/construction_site/build/` (`construction_site_full.usdc`, `construction_site_r40.usdc`), read 14 November 2026 |
| Its origin and licence | the lab's export of an Unreal Engine asset pack; no licence file found | OPEN | `localisation/scenes/construction_site/README.md` |
| Tier 1 world | one signed distance field on the GPU, baked once from the merged, simplified mesh and shared by every game; random blocks and columns are added per game as analytic shapes | PROPOSED | RESEARCH §9 |
| Tier 2 world | one static triangle mesh outside the per-game folders; drones carry simple colliders | PROPOSED | RESEARCH §9 |
| Distance-field resolution | 0.2 m to start, 0.1 m if gaps matter | PROPOSED | RESEARCH §9 |

11. World files are read, never changed. Anything baked from a licensed asset (meshes, distance
    fields) goes under `runs/` or a git-ignored folder, never into git.
12. Appearance is dropped: the training copy of a world is collision shape only.

## 6. Training rules

1. **Batched everywhere.** Observations, rewards, resets, the safety filter and the drone model are
   tensor operations over all games. No Python loop over games, no `.cpu()`, no NumPy in the step.
2. **The safety filter is in the loop** during training and evaluation, the same as in flight. Store
   the policy's unfiltered command in the learning buffer; log how often and how much the filter
   changes it.
3. **Opponents come from a pool**: the latest version, earlier saved versions, and scripted
   opponents. A run states its mix. Scripted opponents are never removed from the pool.
4. **Starts and layouts are random from the first run.** No fixed start positions or single fixed
   layout anywhere except in a named evaluation scenario. One world is held out and never trained on.
5. **Seeds**: every run fixes and records its seeds. A gate applies to the one checkpoint that was
   evaluated; a claim that a method is better needs at least 3 seeds.
6. **Headless**, and never while the AirStack simulator or a flight session uses the GPU.
7. **Version-specific Isaac Lab calls live in one adapter module.** The game, the safety filter and
   the tier 1 model import nothing from Isaac Lab or Isaac Sim, so they run and are tested without
   launching either.
8. Isaac Lab 3.0 flips quaternion order (WXYZ to XYZW). Quaternions cross the adapter in one named
   convention only.

## 7. Evaluation and gates

1. Each stage of a run has a `gates.toml` written **before** the run starts. It is never edited after
   the first result exists; a new gate is a new run. The builder proposes the limits in the step's
   plan; the owner approves them before the first run (PROPOSED).
2. The numbers gated are the numbers plotted: one metrics module serves training curves,
   evaluation and records.
3. An evaluation plays at least 1,000 games per condition and reports a rate with its 95 % interval.
4. The fixed evaluation suite (grows, never shrinks):

| Group | What it measures |
|---|---|
| Scripted opponents | hold rate against textbook Strike behaviours (straight run, split, feint, change of plan) and textbook Guard assignments |
| Starts | hold rate from held-out start regions |
| Team sizes | every size in the trained range, plus one outside it |
| Drop-out | hold rate when one drone leaves mid-game |
| Earlier versions | win rate against every saved version (cross-play table) |
| Safety | within a team: closest approach, filter intervention rate and size; touches on structures; fence breaches (gate: 0) |
| Contact tags | tag rate against scripted Strike behaviours that dodge; closing speed at contact |
| Environments | every number above on held-out layouts and on the held-out world; with and without line of sight to the other team |
| Smoothness | change in command between steps |
| Cross-check (stage 4) | gap in hold rate between tier 1 and tier 2; step-response error between them |

5. Reference point for use 1: two Guard drones against one Strike drone held the zone in about 20 %
   of games in the partners' first test (programme simulation page). The conditions of that test
   (arena, zone, speeds, starts) are not reproduced here, so it is a reference, never a gate.
   Beating a number in the training simulator says nothing yet about real drones.
6. A FAIL is recorded as a FAIL. An aborted run writes an ABORTED record.
7. Limits that have no value yet. Each is written into the plan of the build step that first uses
   it, before that step's first run:

| Limit | Status | Set in the plan for |
|---|---|---|
| Stage 1: error between the fitted model and the logged velocity step: held-out velocity RMS ≤ 0.10 m/s, t63 error ≤ 0.10 s, fitted delay 0–0.40 s, at least 8 held-out steps | FIXED (owner, 15 November 2026) | S1: [`configs/s1.toml`](configs/s1.toml) `[fit_gates]` |
| Safety filter port: tolerance against `cbf_filter.py`: speed difference ≤ 0.02 m/s, constraint residual ≤ 2e-3, emergency agreement ≥ 0.99, Guard–Strike corrections 0, over 2,000 scenes | FIXED (owner, 15 November 2026) | S1: [`configs/s1.toml`](configs/s1.toml) `[filter_gates]` |
| Stage 4: allowed gap in hold rate and in step response between tier 1 and tier 2 | OPEN | S4 |
| Stage 6: allowed gap between the training simulator and the AirStack simulator | OPEN | S5 |

## 8. Runs and records

| Path | Holds | In git |
|---|---|---|
| `runs/<date>_<name>/` | checkpoints, logs, videos | no |
| `records/<date>_<name>_record.md` | purpose, commit, config, model parameter set, seeds, machine, games at once, steps per second, gates with PASS or FAIL | yes |
| `records/LEDGER.md` | one row per run, append-only, numbered T1, T2, … | yes |

- The training ledger is separate from the flight ledger (`docs/record/LEDGER.md`); this folder never
  writes there.
- A record names its simulator in the first line.
- Throughput is always reported as environment steps per second together with the number of games,
  the number of drones per game, the tier and the GPU.
- **Every training run saves videos** (owner, 17 November 2026). At least two evaluation games per
  checkpoint the run keeps (its final and its best), and one game at each scheduled evaluation where
  the trainer supports it; headless, into `runs/<date>_<name>/videos/`. A partner's own trainer uses its
  own recorder (for NUS's JAX code: `save_eval_gif=True` on the fixed-opponent runner; NUS's self-play runner
  writes no GIFs, so render them afterwards with `ma_skills/scripts/eval.py`). Its raw videos stay with the
  partner's outputs, outside this repository; a small chosen set may be converted and committed under
  `docs/media/` (owner, 18 November 2026, NUS agreed; [docs/media/nus/](docs/media/nus/README.md)). For the NUS
  port the owner widened this the same day (~14:10): every clip of the port, re-encoded small, may be committed. The record lists
  the video paths. A run that ends without videos says so in its record and why.
- Ledger rows written on a workstation are numbered T15, T16, … (WORKSTATION_SETUP §4); the lead renumbers them to
  the next T numbers when the branch merges to `main`.
- `runs/` stays out of git. One exception (owner decision 6, 18 November 2026): the NUS-port files a ladder row and the
  NUS parity tests need (converted weights, local settings, starts, recordings) are committed once, PROVISIONAL, in
  [nus_provisional/](nus_provisional/README.md) and installed into `runs/nus_port/` and `configs/local/` by
  `scripts/nus_install_provisional.sh` (§2).

## 9. Code

Layout. Built in S0: `source/svg_training/` with `bench/`, `compat/`, `envs/`, `models/`, `worlds/`; `configs/`, `scripts/`,
`tests/`, `records/`, `runs/`, `docker/`. Still planned: `core/`, `opponents/` and the scripts after the benchmark. Target:

```
svg_training/
  source/svg_training/
    core/        game rules, observations, rewards, safety filter port, fence  (PyTorch only)
    worlds/      distance field, analytic shapes, range rays, line of sight   (PyTorch only)
    models/      tier 1 response model; tier 2 Starling asset and control cascade
    envs/        tier 1 vector environment; tier 2 DirectMARLEnv wrapper
    opponents/   pool, scripted opponents
    compat/      the one Isaac Lab version adapter (2.3.2 now, 3.0 later)
  configs/       Python or TOML, never YAML
  scripts/       benchmark, fit_model, bake_world, train, evaluate, export
  tests/         pytest; core tests need no simulator
  records/  runs/
```

1. Test first. `core/` and the tier 1 model are covered by tests that run in seconds without Isaac.
2. No YAML, `docker-compose*` or `launch/` paths. The one `Dockerfile` lives in `docker/`; a change
   to it needs a line in the repository's `docs/record/CHANGES.md` and the eight-field commit body
   (`docs/CODING_STANDARD.md`).
3. Isaac Lab is never copied into the repository and never edited. The repository's way to get it is
   the image built by `docker/build.sh` on NVIDIA's official Isaac Lab image; a host install
   (`~/IsaacLab` with conda `env_isaaclab` on the laptop) works the same. `scripts/run_s0.sh` reads
   `SVG_PY`, `SVG_ISAACLAB` and `SVG_IN_CONTAINER`, so one script serves both.
4. Nothing is copied out of `AirStack/` except by a script that records the source path and commit.
   `isaac_sim/starlingmax2.usd` is read, never changed.
5. Python: type hints on public functions, shapes in docstrings (`(N, M, 3)`), SI units in names
   (`_m`, `_mps`, `_s`).

## 10. Git and other sessions

1. Before writing: `git status -sb`, `git worktree list`, and look for files changed in the last 30
   minutes. Files you did not create belong to someone else.
2. The folder is tracked since 14 November 2026. Commits: explicit paths, the live clone
   (`~/AirStack-starling-max2`), `main` or a worktree branch per the root `CLAUDE.md`, no push.
3. `.claude/` is ignored by this clone's `.git/info/exclude`; this folder's agents and skills are
   committed all the same, so a new file there needs `git add -f <path>`.
4. Never `git add -A`, `git commit -a`, `git stash`, `git reset --hard`, `git clean`, `--no-verify`.

## 11. Definition of done

A change is done when all of these hold:

- [ ] It is inside `svg_training/`, and `git status` shows nothing else touched.
- [ ] No flight or simulator code changed (owner, 15 November 2026): `git -C .. status --short -- AirStack tools patches mocap mocap.sh starling_1_indoor_params.params localisation` prints nothing, and no commit of this work touches those paths.
- [ ] A page that claims a result or a passing test shows it with a figure generated by a committed script from the run's own data (owner, 15 November 2026), with a numbered caption.
- [ ] Tests pass, and the output is quoted in the hand-over.
- [ ] Any number in a document traces to a record, a source file or a cited paper.
- [ ] New values carry a status label (FIXED, MEASURED, PROPOSED, OPEN).
- [ ] Wording follows §2; the simulator is named.
- [ ] A run has its gates file dated before the run, a record and a ledger row.
- [ ] [docs/claude/HANDOFF.md](docs/claude/HANDOFF.md) says what changed and what is still open.
