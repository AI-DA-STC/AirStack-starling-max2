REFERENCE · every term these pages use: NUS's terms and the terms used here, the policies and the six tests, the world around this folder, and the pipeline's own terms.

# Glossary

Plain definitions, British spelling. The rules behind them are in [STANDARDS.md](../STANDARDS.md). Part 1 maps NUS's
terms to the terms used on these pages and defines the policies and the six tests; part 2 explains the drones and
software around this folder; part 3 is this folder's own vocabulary. **STE**: the lab that wrote this repository.

## 1. NUS terms and the terms used here

The programme's wording rules rename some of NUS's terms ([STANDARDS §2](../STANDARDS.md#2-wording)). Each reader page
gives NUS's term once, then the term used here.

| NUS term or setting | Term used here | Notes |
|---|---|---|
| area denial (the NUS game) | the Strike vs Guard game (SvG) | `svg_training` = Strike vs Guard training |
| `defender` | defender (Guard team), then Guard team, Guard drone | holds the zone |
| `attacker` | attacker (Strike team), then Strike team, Strike drone | tries to reach the zone; 1.5 times as fast as a Guard drone |
| the "reached" flag (sticky) | a Strike reach (a Strike win) | the NUS game runs on to step 200 after the first reach; STE scoring ends the game at the first reach. The win or loss is the same either way |
| time-out with no reach | a hold (a Guard win) | |
| the NUS reward: per-step inside-share penalty, −2 on the first reach, potential shaping, zero-sum | STE scoring counts the outcome only (reach or hold) | stage 5.2 training keeps the NUS reward, in metres ([plan](plans/2026-11-18-nus-phase5-retraining.md)) |
| 1 unit | 0.40 m on the hangar set-up | STE's choice, so the zone (4 units = 1.6 m radius) sits outside the flight software's 1.10 m keep-out |
| 1 step | 0.60 s = 12 *ticks* of 0.05 s | each action is held for the 12 ticks |
| `spawn_distance`, `defender_boundary` | 8.0 units each on the hangar set-up | the NUS defaults are 20 |
| the NUS soft push between teams | the *push-apart* rule (`block`) in Tests 2–3; the *safety filter* from Test 4 | the NUS push herds; the push-apart only cuts a move short; the filter makes both drones give way |
| `scripted_opponent: apf` (artificial potential field) | APF defender, APF attacker; in STE code `ApfGuard`, `ApfStrike` | NUS's scripted controllers, ported to PyTorch by STE; gains read from the NUS code |
| archive, generation, lineage | the same | an archived policy of one team; one generation of alternating training; a lineage is the chain of archived Guard and Strike policies of one self-play seed |
| `area-denial-continuous-space-self-play` | the NUS code (commit `2d2b904`) | the one NUS branch used |
| observation, 9N + 2 (56 numbers for 3 v 3) | rebuilt from the 71-number STE observation by `NusPolicy` | interface layout `nus_area_denial_v1` |
| `train_self_play` | the NUS training method: alternating best-response multi-agent PPO with the archive pool | the STE port of NUS's training method (PyTorch) copies it, without APEX |

### Policies

Every policy named on these pages. NUS shared its code, not trained checkpoints, so STE trained G19, S20, P3G and P3S
itself with the NUS code (Phase 2a) and converted them to PyTorch (Phase 3).

| Label | NUS run folder → entry | Trained by | Code / simulator / library |
|---|---|---|---|
| G19 | `2026-11-17_selfplay_3v3_seed2` → `archive/0019_defender` | STE, using NUS's code (self-play seed 2, continued to 20 generations) | NUS self-play runner (`train_self_play`) / NUS 2-D game / JAX |
| S20 | same run → `archive/0020_attacker` | STE, using NUS's code | same |
| P3G | `2026-11-17_fixed_apf_3v3_defender` | STE, using NUS's code (against the APF attacker) | NUS fixed-opponent runner / NUS 2-D game / JAX |
| P3S | `2026-11-17_fixed_apf_3v3_attacker` | STE, using NUS's code (against the APF defender) | same |
| APF defender, APF attacker (`ApfGuard`, `ApfStrike`) | NUS's scripted opponent (config `scripted_opponent: apf`) | written by NUS, no training | ported to PyTorch by STE |
| Parked Guard (`ParkedGuard`) | — | STE baseline, no training | every Guard drone commands zero speed from its start point; one Guard drone starts at the zone centre |
| STE Guard policy | `pilot_p1b` run 4 | STE (pilot P1b: one seed, not gated) | skrl IPPO / STE drone model, Test 5 conditions / PyTorch ([training recipe](TRAIN_A_GUARD.md)) |
| STE scripted Guards and Strikes | — | hand-written by STE, no training | Guard `guard_mirror`, `guard_mark_edge`, `guard_mark_inside`, `guard_field`; Strike `strike_straight`, `strike_flank`; PyTorch |

"G19" = Guard of generation 19, "S20" = Strike of generation 20; IPPO = independent PPO, one learner per drone (skrl's multi-agent trainer); "P3G" and "P3S" = the Guard and Strike converted in
Phase 3. The run folders are in NUS's `outputs/hangar/` on the lab's workstation (not in git); the converted
weights are in the repository marked PROVISIONAL ([nus_provisional/](../nus_provisional/README.md)).

### The six tests

Phase 4 scored the converted policies, frozen, in six tests; each test brings the game one step closer to the STE
drones. The records call a test a "ladder row" (record file names say "rung"): **Test N = ladder row N in the records**,
and the sub-tests keep the records' numbers.

| Test | Name used on these pages | What it is |
|---|---|---|
| 1 | Copy of NUS 2-D game, in PyTorch | STE's batched PyTorch copy of the NUS game (`nus/replica.py`; "replica" in the records), on the hangar set-up |
| 2.1 | sub-test of Test 2 | the STE game engine with NUS's soft push and NUS's Guard circle |
| 2.2 | sub-test of Test 2 | as 2.1, with square walls (the 7.5 m arena) in place of the Guard circle |
| 2 | STE game engine (PyTorch), NUS rules, action held for each 0.6 s step | NUS's speeds, zone and scoring in the STE engine, with the square walls of 2.2; **two changes from 2.2**: the push-apart in place of NUS's soft push, and each action held for 12 ticks (0.60 s) |
| 3a | control for Test 3 | a drone that flies the held command exactly; must equal Test 2 |
| 3 | STE drone model (PyTorch): + Starling delay and lag | each command goes through a copy of CMU's commander and the delay and lag of the exploratory drone model |
| 4 | STE drone model: + safety filter on every drone pair | the safety filter in place of the push-apart, as in flight; **two effects**: no pushing, and team-mates kept 1.10 m apart |
| 5a | control for Test 5 | drones free in height, no start jitter; must equal Test 4 |
| 5 | STE drone model: + free height (3-D) | drones free in height, start heights jittered by ±1 mm |
| 6 | Isaac Lab physics drones (Isaac Sim 5.1) | rigid-body Starling models in Isaac Lab, flown by a copy of PX4's control loops ("tier 2" in the records) |

"Test 5 conditions" = the hangar game of Test 5, the game the STE Guard policy was trained in.

## 2. The world around this folder

None of this is needed to run anything in this folder. It explains words on the pages.

| Term | Meaning | More |
|---|---|---|
| Starling 2 Max (Starling) | ModalAI's small indoor quadrotor drone. The lab has two | root [README](../../README.md) |
| PX4 | the open-source flight software on the drone: version 1.14 on the real drones, 1.16.1 in the AirStack simulator | [STANDARDS §5](../STANDARDS.md#5-drone-models) |
| AirStack | CMU's ground-control software that flies the drones; a snapshot lives in the repository's `AirStack/` folder | root [README](../../README.md) |
| Commander | AirStack's program (`swarm_commander.py`) that, 20 times a second, turns each drone's speed command into an instruction for PX4 | [S1_RESULTS](S1_RESULTS.md#3-why-two-clocks-in-the-simulator) |
| Safety filter (CBF) | CMU's collision filter in the commander (a control barrier function). In flight it acts on **every pair of drones**: when two drones come close, it changes both speed commands so they give way, keeping them 1.10 m apart. Main game and NUS port (Tests 4–6): every pair, as in flight. Contact-tag track only: within a team ([STANDARDS §4](../STANDARDS.md#4-game-specification-version-0)) | root [GLOSSARY](../../docs/GLOSSARY.md) |
| Keep-out distance | 1.10 m centre to centre (0.55 m radius): how close the safety filter lets two drones' commanded speeds bring them. The filter does not correct the position the commander sends, so drones can come slightly closer (1.083 m in a test on the STE drone model) | [S1_RESULTS](S1_RESULTS.md#6-tier-1-with-the-real-chain-t4-information-only) |
| Keep-in fence | a box the commander keeps every drone inside; today ±3.25 m around the motion-capture origin | [hangar geometry](WHAT_WE_DID_DAY_BY_DAY.md#3-phase-0-answers-and-the-hangar-geometry) |
| Motion capture (mocap) | cameras around the room track markers on each drone and send its position to the drone, in place of GPS | root [GLOSSARY](../../docs/GLOSSARY.md) |
| The hangar | the lab's indoor flight room with motion capture. Its usable flying box is about 7.6 m × 7.9 m, 0.5–5.0 m high; the arena for the NUS game is a 7.5 m square inside it | [hangar geometry](WHAT_WE_DID_DAY_BY_DAY.md#3-phase-0-answers-and-the-hangar-geometry) |
| Isaac Sim | NVIDIA's GPU robot simulator | root [GLOSSARY](../../docs/GLOSSARY.md) |
| Isaac Lab | NVIDIA's robot-learning framework on top of Isaac Sim; runs thousands of simulated robots on one GPU. The Isaac Lab physics drones (Test 6) use it | [the game](THE_GAME.md#two-drone-models) |
| ROS 2 | the robot messaging software the flight side uses. This folder needs none of it; if the shell loads it, run `unset PYTHONPATH` first | root [GLOSSARY](../../docs/GLOSSARY.md) |
| AirStack simulator | the flight software's own simulator: Isaac Sim + Pegasus (a drone plug-in) + PX4 software; up to 3 drones, near real time. Separate from the training simulator | [DESIGN §3](DESIGN.md#3-the-pipeline-seven-stages) |
| Crazyflie | a palm-sized research drone; the lab also flies these | root [README](../../README.md) |
| ENU frame | x east, y north, z up: the frame of every speed command | [STANDARDS §3](../STANDARDS.md#3-policy-interface-version-01-proposed) |
| Plug-in point | `/svg/{name}/teleop_command`: where a strategy's speed command enters the flight software | [STANDARDS §3](../STANDARDS.md#3-policy-interface-version-01-proposed) |
| Trajectory setpoint | the instruction the commander sends a real drone each tick: a position, a speed and an acceleration together; PX4 closes the position loop itself | [S1_RESULTS](S1_RESULTS.md#4-the-real-drone-takes-a-different-route) |
| Position gain | PX4's `MPC_XY_P`, 0.95 per second on the STE drones: extra speed per metre away from the setpoint | [S1_RESULTS](S1_RESULTS.md#5-a-first-fit-from-real-flight-logs-exploratory) |
| FR&PDR, monthly reports | confidential programme reports; named here, never quoted | [STANDARDS §2](../STANDARDS.md#2-wording) |
| The owner, the lead, the gatekeeper | roles in the lab's records and internal pages: the owner is the lab member who owns this repository and approves gates and decisions; the lead is the main AI coding-assistant session that plans the work; the gatekeeper is an AI reviewer that checks gates and records | [docs/README](README.md#history) |

## 3. Words in this folder

### Simulators, drones and games

| Term | Meaning | More |
|---|---|---|
| Training simulator | this folder's simulator: the STE drone model or the Isaac Lab physics drones. One of three simulators (with the AirStack simulator and real flight); always say which | [STANDARDS §2](../STANDARDS.md#2-wording) |
| STE drone model (PyTorch); "tier 1" in the records | the fast drone model: a batched game in plain PyTorch, no Isaac; a drone is a point that follows a speed command through a copy of the commander and a fitted response (the exploratory drone model) | [the game](THE_GAME.md#two-drone-models) |
| Isaac Lab physics drones; "tier 2" in the records | the physics drone model: rigid-body Starling models in Isaac Lab, flown by a copy of PX4's control loops | [the game](THE_GAME.md#two-drone-models) |
| Copy of NUS 2-D game (PyTorch); "replica" in the records | STE's batched PyTorch copy of the NUS 2-D game, used for Phases 2–3, Test 1 and stage 5.1 | [what we found, the copy](WHAT_WE_FOUND.md#1-copy-of-nus-2-d-game-pytorch-matches-nus-2-d-game-jax) |
| Exploratory drone model (`real_exploratory_v0`) | the STE drone model's response, fitted to one real flight log with no gate; it answers more slowly than the real drone (its check against a real flight, T5, is a FAIL) | [S2_RESULTS](S2_RESULTS.md) |
| Starling layer (`starling`) | a switch that makes drones fly like the STE Starlings: each command goes through the commander copy, the safety filter on every pair of drones (both teams) and the exploratory drone model; the push-apart rule is then off | [S2_RESULTS](S2_RESULTS.md#what-was-built) |
| Pure partner rules (`pure`) | drones as points at fixed team speeds, all at one height, with the push-apart rule | [plug in your code](PLUG_IN_YOUR_CODE.md#pure-rules-and-the-starling-layer) |
| Push-apart rule (`block`) | under the pure rules, a move that would bring a drone inside the other team's keep-out distance is cut short | [plug in your code](PLUG_IN_YOUR_CODE.md#words-used-here) |
| Physics backend (`physics`), physics drone | the third way the game moves drones: the same commander copy and filter, then a rigid body with four rotors flown by the PX4 cascade | [S2B_RESULTS](S2B_RESULTS.md#what-was-built) |
| PX4 cascade | PX4 1.14's chain of control loops, copied line by line: position → speed → acceleration → tilt → turn rate → rotor commands, 200 times a second | [S2B_RESULTS](S2B_RESULTS.md#what-was-built) |
| Rotor model | turns rotor commands into one force and one torque; each rotor follows its command with the measured motor lag (55 ms up, 85 ms down) | [S2B_RESULTS](S2B_RESULTS.md#what-was-built) |
| PyTorch reference world (test oracle) | the physics drone's equations in plain PyTorch, no Isaac; the CPU tests run on it | [S2B_RESULTS](S2B_RESULTS.md#what-was-built) |
| Game (environment) | one copy of the game; thousands run at once on the GPU. Isaac Lab calls it an environment | config `num_games` |
| Tick, game-step | one tick of game time for one game, 1/20 s. Records say "environment steps per second" | [S0_RESULTS](S0_RESULTS.md) |
| Drone-step | one tick for one drone; drone-steps = game-steps × drones per game | [S0_RESULTS](S0_RESULTS.md) |
| Policy | a trained strategy: it reads what a drone sees and sends a speed command | [the game](THE_GAME.md#where-a-strategy-plugs-in) |
| Strategy contract | the rule a strategy follows to be scored: it plays one team, is called once per step with all its drones' observations in all games, returns all their actions, and is told which games restarted | [plug in your code](PLUG_IN_YOUR_CODE.md#three-layers) |
| STE scripted Guards and Strikes (scripted opponent) | a hand-written STE strategy used as an opponent and yardstick: Guard `guard_mark_edge`, `guard_mark_inside`, `guard_field`, `guard_mirror`; Strike `strike_straight`, `strike_flank`; either `random`, `zero` | [S2_RESULTS](S2_RESULTS.md#3-the-scripted-reference-t6-re-run-as-t9) |
| Parked Guard (`ParkedGuard`) | the STE baseline Guard team, no training: one drone starts at the zone centre, every drone commands zero speed | [what we found, a Guard team that stands still](WHAT_WE_FOUND.md#5-a-guard-team-that-stands-still) |
| Guard team, Strike team | the team that holds a circular zone; the team that tries to reach it (1.5 times as fast) | [STANDARDS §4](../STANDARDS.md#4-game-specification-version-0) |
| Tag (contact tag) | physical contact between a Guard drone and a Strike drone. Only in the separate contact-tag track; the main game and the NUS port have no tag | [STANDARDS §2](../STANDARDS.md#2-wording) |
| Size band | arena sizes reported separately: lab 4–6 m, middle 6–10 m, large 10–16 m a side | [S2_RESULTS](S2_RESULTS.md#3-the-scripted-reference-t6-re-run-as-t9) |
| Scoring tool | `scripts/score.py`: plays strategies against each other per size band, team size and rule set, and reports hold rate, closest approach, breaches, filter use and start misses | [plug in your code](PLUG_IN_YOUR_CODE.md#what-the-scoring-tool-prints) |
| Adapter | a thin wrapper that lets a training library drive the game: `SvgSkrlEnv` (skrl) and `SvgTeamVectorEnv` (Gymnasium) | [plug in your code](PLUG_IN_YOUR_CODE.md#plug-a-training-method-in) |
| Stand-in trainer (pipe test) | `scripts/train_standin.py` (skrl IPPO). On the S2 game a short run only proves the pipe works end to end and is never "the policy". The same trainer with the `pilot_p1b` settings on the hangar game produced the STE Guard policy, a pilot output (one seed, not gated; [training recipe](TRAIN_A_GUARD.md)) | [S2B_RESULTS](S2B_RESULTS.md#5-the-stand-in-trainer) |
| Sweep (safety filter) | one round of small corrections to every drone's speed in the filter copy; more sweeps get closer to CMU's answer but cost time. Not the same as a *sweep point* | [S1_RESULTS](S1_RESULTS.md#1-the-safety-filter-copy-t2-fail-accepted-by-the-owner) |
| Early stop, `check_every` | a filter option: every `check_every` sweeps it checks which games still need work and stops when none is left (0 = no early stop). The game uses 1,000 sweeps with a check every 8. On a GPU its answer depends on the batch size ([record](../records/2026-11-18_filter_cuda_graph_record.md)) | [S2_RESULTS](S2_RESULTS.md#1-a-faster-safety-filter-t7-aborted-t8-pass) |
| Commander teleop law | the commander's rules for a speed command: cap it, ramp up to it, move a reference point by it, keep that point within 0.5 m of the drone, apply the safety filter. The STE drone model has a copy of the real-drone version (`models/commander.py`) | [S1_RESULTS](S1_RESULTS.md#6-tier-1-with-the-real-chain-t4-information-only) |
| Stand-in (placeholder) model | the drone model used before a fitted one existed: delay + lag on the STE drone model, ARL Robot 1 on Isaac Lab | [S0_RESULTS](S0_RESULTS.md#limits) |
| Partner rules preset | the main game of S2, after NUS's rules: opposite teams kept apart by the push-apart rule, team-mates pass through each other, one step inside the zone wins for the Strike team, a time-out wins for the Guard team. Committed values are neutral; the code reads NUS's values from the git-ignored `configs/local/` | [S2_RESULTS](S2_RESULTS.md#what-was-built) |
| Container UTC | T1's dates are UTC from the container; add 8 h for Singapore time | [S0_RESULTS](S0_RESULTS.md#the-fail) |
| Distance field, range ray, line of sight | a 3-D grid of distances to the nearest structure; a ray that returns the distance to the first structure; whether one drone can see another | [DESIGN §4](DESIGN.md#4-two-tiers-one-game) |

### The NUS port

| Term | Meaning | More |
|---|---|---|
| NUS port | running team strategies trained with NUS's code, and then NUS's training method, in this pipeline | [what we did, day by day](WHAT_WE_DID_DAY_BY_DAY.md) |
| NUS 2-D game | NUS's own game, in JAX: point drones in a plane that jump each step by up to the team's cap, a soft push between the teams, a Guard circle and no walls; G19, S20, P3G and P3S were trained in it | [front page, the game](../README.md#3-the-game-nus-2-d-game-vs-ste-drone-set-up) |
| Hangar set-up | STE's scale for NUS's game: 0.40 m per unit, 0.60 s per step, spawn distance and Guard circle 8 units (3.2 m), a 7.5 m square arena, every drone at 1.2 m | [hangar geometry](WHAT_WE_DID_DAY_BY_DAY.md#3-phase-0-answers-and-the-hangar-geometry) |
| STE drone set-up | the game as STE's drones would play it (Test 5 conditions; Test 6 on the Isaac Lab physics drones): the STE drone model, the safety filter on every pair, free height, the 7.5 m hangar box with walls, one action per 0.60 s | [front page, the game](../README.md#3-the-game-nus-2-d-game-vs-ste-drone-set-up) |
| Phase | one stage of the NUS port, 0 to 6: questions, the NUS code installed (1), policies trained with the NUS code (2a), the Copy of NUS 2-D game (2), the conversion (3), the six tests (4), training in STE conditions (5), these documents (6) | [what we did, day by day](WHAT_WE_DID_DAY_BY_DAY.md#at-a-glance) |
| Test 1–6, sub-tests 2.1, 2.2, 3a, 5a | Phase 4: the frozen converted policies scored in six tests, each bringing the game closer to the STE drones (part 1). The records say "transfer ladder", "ladder row" or "rung": **Test N = ladder row N in the records** | [the six tests](#the-six-tests) |
| STE game engine (PyTorch) | the batched game of `core/game.py`, used from Test 2 on; its rules, walls and push are set per test | [the game](THE_GAME.md#the-game-as-an-rl-environment) |
| Core pairs | the 12 pairs of every test: G19, P3G, APF defender, Parked Guard against S20, P3S, APF attacker | [what we found, the six tests](WHAT_WE_FOUND.md#3-six-tests-towards-ste-drones) |
| Paired starts | one file of 1,000 start positions (seed 20261119), the same in every test, so two tests can be compared game by game | [how to run it yourself, level D](RUN_IT_YOURSELF.md#d-repeat-the-six-tests) |
| Run 0 | the check of the hangar set-up before any training, with the NUS environment and scripted players | [hangar geometry](WHAT_WE_DID_DAY_BY_DAY.md#3-phase-0-answers-and-the-hangar-geometry) |
| STE port of NUS's training method (PyTorch) | STE's PyTorch copy of `train_self_play`; "route (b)" and "5.1" in the records. 5.1 = this copy in 2-D on the Copy of NUS 2-D game, 3 seeds; 5.2 = the same on the STE drone model (planned) | [what we found, training method](WHAT_WE_FOUND.md#6-ste-port-of-nus-training-method-stage-51-fail) |
| R0, C0, N0 | the checks of the test for that port: R0 the three NUS-code hangar lineages (trained by STE with NUS's code) rebuilt as the reference; C0 the NUS code with new seeds (must pass the test); N0 untrained actors (must fail it) | [what we found, training method](WHAT_WE_FOUND.md#6-ste-port-of-nus-training-method-stage-51-fail) |
| Pilot (P0, P1, P1b, P2) | a short training run with no gate, to look before planning; INFO only. Pilot P1b run 4 produced the STE Guard policy | [what we found, STE Guard policy](WHAT_WE_FOUND.md#7-ste-guard-policy-trained-in-test-5-conditions) |
| Start miss | a game whose drones start closer than the spacing rule wants. In the NUS starts every game has a pair inside the 1.10 m keep-out (1,000 of 1,000); in STE's own small arenas it flags crowded starts | [what we found, the six tests](WHAT_WE_FOUND.md#3-six-tests-towards-ste-drones) |
| Contact (records column) | games in which any two drones, team-mates included, come closer than 0.50 m. Not a crash count: the packed NUS Guard start already has such a pair in 853 of 1,000 games | [what we found, the six tests](WHAT_WE_FOUND.md#3-six-tests-towards-ste-drones) |
| Rule breach | a game in which some Guard drone and some Strike drone came closer than the keep-out distance; judged in 3-D | [S2_RESULTS](S2_RESULTS.md#4-how-close-guard-and-strike-drones-came) |
| Closest approach, horizontal and 3-D | the smallest Guard–Strike distance in a game. Horizontal ignores height; they differ when drones pass one above the other | [S2_RESULTS](S2_RESULTS.md#4-how-close-guard-and-strike-drones-came) |
| Hold rate | the share of games the Guard team held, with its 95 % interval; a Strike strategy's win share is 1 − hold rate | [S2_RESULTS](S2_RESULTS.md#3-the-scripted-reference-t6-re-run-as-t9) |
| "at the local value" | in records only: a number equal to a value from a git-ignored local settings file was masked. NUS's settings may now be stated, so reader pages print the number | [records/README](../records/README.md) |
| PROVISIONAL (weights, settings files) | the converted G19, S20, P3G and P3S and the STE local settings files, committed only so the numbers here can be repeated: trained by STE with the NUS code, 8 generations, hangar set-up. NUS will retrain | [how to run it yourself, level D](RUN_IT_YOURSELF.md#d-repeat-the-six-tests) |

### Results, records and gates

| Term | Meaning | More |
|---|---|---|
| Gate | a pass mark written before a run and never moved afterwards | [STANDARDS §7](../STANDARDS.md#7-evaluation-and-gates) |
| PASS, FAIL | a run met, or missed, its gates. They grade STE code and STE copies, never the NUS code. A FAIL stays a FAIL | [records/README](../records/README.md) |
| "FAIL (accepted)" | the gate was missed, the lab owner judged the cause harmless, and the work went on; the FAIL stays in the ledger | [records/README](../records/README.md) |
| INFO | a run with no gates: a measurement, not a pass or a fail | [records/README](../records/README.md) |
| ABORTED | a run stopped before it finished; its partial numbers prove nothing | [records/README](../records/README.md) |
| Exploratory | a first look with no gates and no ledger row; it guides the next step but proves nothing | [S1_RESULTS](S1_RESULTS.md) |
| Decision rule | a threshold set in advance that helps choose the next step; it never passes or fails a run | [S0_RESULTS](S0_RESULTS.md#decision-rules--training-simulator-only) |
| Wilson interval (Wilson 95 %) | the 95 % confidence interval of a rate from k successes in n games; unlike "rate ± 2 standard errors" it stays inside 0–1 near 0 and 1. At 1,000 games it is at most about ±0.03 wide | [STANDARDS §7](../STANDARDS.md#7-evaluation-and-gates) |
| Run of record | the official run whose numbers are kept; it ends in a record and a ledger row | [ledger](../records/LEDGER.md) |
| Record | the written summary of one run, `records/<name>_record.md`, made by the tooling; never edited | [records/README](../records/README.md) |
| Ledger, T rows | `records/LEDGER.md`, one row per run: T1, T2, … T*n* is the *n*-th run of this folder. Separate from the flight ledger | [ledger](../records/LEDGER.md) |
| W rows | ledger rows written on the lab's second workstation before its branch joins `main`; each gets the next T number at the merge | [records/README](../records/README.md) |
| Status labels | FIXED, MEASURED, PROPOSED, OPEN: where a value comes from and whether it may change | [STANDARDS](../STANDARDS.md) |
| Observed in the training simulator | the only way to describe a result here; never "validated". No result here is a flight result | [STANDARDS §2](../STANDARDS.md#2-wording) |
| Held-out | data kept aside to judge a fit or a policy, never to train it | [S1_RESULTS](S1_RESULTS.md#2-first-fit-to-the-airstack-simulator-t3-fail) |
| Paired games | the same arenas, zones and starts played twice (two drone models, or two tests), so any difference comes from what changed | [S2B_RESULTS](S2B_RESULTS.md#4-the-scripted-games-on-both-backends-t13-fail) |
| Cell (matchup cell) | one Guard strategy against one Strike strategy, at one team size, in one size band | [S2B_RESULTS](S2B_RESULTS.md#4-the-scripted-games-on-both-backends-t13-fail) |
| Upset | a physics drone that tips past 60° or whose numbers turn non-finite; counted per game | [S2B_RESULTS](S2B_RESULTS.md#the-gates) |
| Seed | the starting number for the random draws; the same seed gives the same run on the same machine | [STANDARDS §6](../STANDARDS.md#6-training-rules) |
| sha256, hash; code hash (`code_sha`) | a fingerprint of a file; the first 12 hex digits of a sha256 over `source/`, `scripts/` and `configs/`, in every result row | [GETTING_STARTED](GETTING_STARTED.md#approved-sha256) |
| Approved config hash | sha256 of the config the owner approved; `scripts/run_s0.sh` refuses a different one (exit 65) | [GETTING_STARTED](GETTING_STARTED.md#approved-sha256) |
| Case, sweep point, repeat spread | the benchmark's named set-ups, one set-up at one game count, and how far two repeats differ (S0 allows 0.10) | [S0_RESULTS](S0_RESULTS.md) |
| S0's 20,000 line | S0's decision rule: the Isaac Lab drones at 20,000 drone-steps a second or more is fast enough to train on directly | [S0_RESULTS](S0_RESULTS.md#decision-rules--training-simulator-only) |
| Agreement (run) | T10: the same forces and cascade in Isaac Lab and the PyTorch reference world, to measure how far apart they end up | [T10 record](../records/2026-11-16_s2b_agreement_record.md) |
| Build steps S0–S5, S2b | this folder's own build order: Measure, Drone model, the game and the plug-in point (S2), the game on Isaac Lab drones (S2b), Two against one, Five against three, Hand-over. Not the AirStack milestones S1–S10 of the root pages | [DESIGN §8](DESIGN.md#8-build-order) |
| Container, headless | a sealed copy of the software that runs the same on every machine; running with no window on screen | [docker/README](../docker/README.md) |
| Preflight | `scripts/isaac_preflight.sh`, run before every Isaac start; it stops on a WiFi-only remote desktop (exit 10) or a busy GPU (exit 11). Not the flight stack's `docs/PREFLIGHT.md` | [GETTING_STARTED](GETTING_STARTED.md#7-the-first-isaac-check-preflight) |
| Interface change, 69 → 71 | on 16 November 2026 each drone's observation gained the zone centre's place in the arena (indices 69–70) | [S2_RESULTS](S2_RESULTS.md#one-change-to-the-interface) |
| Time scale | seconds on the simulated drone's clock per wall-clock second; 1.907 in the S1 simulator session, 1.01 on the real drone | [S1_RESULTS](S1_RESULTS.md#3-why-two-clocks-in-the-simulator) |
| Observed in flight logs | the wording for a model fitted to real flight logs without a run of record; never "validated" | [S1_RESULTS](S1_RESULTS.md) |

## Versions

| What | Version | Used by |
|---|---|---|
| Container image | `nvcr.io/nvidia/isaac-lab:2.3.2` = Isaac Lab 2.3.2 on Isaac Sim 5.1.0; ours is `svg-training:isaaclab-2.3.2` (its test suite is not clean yet) | the container ([docker/README](../docker/README.md)); run of record T1 |
| Host Python environment (lab machines) | conda `env_isaaclab`: Python 3.11, torch 2.7.0+cu128, Isaac Sim 5.1.0, Isaac Lab 2.3.2, skrl 2.1.0, gymnasium 1.2.1 | host runs; MEASURED 17 Nov 2026 |
| CPU environment (RUN_IT_YOURSELF B) | Python 3.11, torch 2.7.0+cpu, skrl 2.1.0, gymnasium 1.2.1, numpy < 2, scipy, msgpack, pyyaml, matplotlib, imageio, opencv | levels A–D of [how to run it yourself](RUN_IT_YOURSELF.md) |
| Isaac Lab 3.0 | needs Isaac Sim 6.2 and Python 3.12 | later |
| AirStack simulator | Isaac Sim 5.1.0 + Pegasus + PX4 v1.16.1 | stage 6, simulated flight |
| Real drones | PX4 1.14 | stage 7, real flight |
| NUS JAX environment (lab workstation) | conda `nus_jax`: Python 3.12, jax 0.10.2, flax 0.12.8, CUDA 13 JAX; the NUS code at `2d2b904` | training and evaluation with the NUS code; the JAX reference arms of Phase 3 |
| `msgpack` | 1.2.4 in `env_isaaclab`, 1.1.2 in the container image | reading NUS checkpoint files (`nus/actor.py`) and the NUS tests |
| NUS policy interface layout | `nus_area_denial_v1`: the NUS 9N+2 observation rebuilt from the 71 STE numbers, a 2-D action held for 12 ticks, vertical speed and yaw rate zero | `svg_training.nus.strategy:NusPolicy` |
