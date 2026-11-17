# Glossary

Plain definitions of the words this folder uses. Spelling is British. The rules behind them are in
[STANDARDS.md](../STANDARDS.md).

## Terms

Each row gives a word, what it means in everyday terms, and where to read more.

| Term | Meaning | More |
|---|---|---|
| Training simulator | this folder's simulator, tier 1 or tier 2. It is one of three simulators; always say which one you mean | [STANDARDS §2](../STANDARDS.md#2-wording) |
| AirStack simulator | the simulator of the flight software: Isaac Sim + Pegasus + PX4 software in docker (`tools/sim.sh`); up to 3 drones, near real time | [DESIGN §3](DESIGN.md#3-the-pipeline-seven-stages) |
| Tier 1 | the fast, simple drone model: a batched game model in plain PyTorch, no Isaac; a drone is a point that follows a velocity command | [HOW_IT_WORKS](HOW_IT_WORKS.md#two-tiers) |
| Tier 2 | the full physics drone model: Isaac Lab physics; a drone is a rigid body with four rotors | [HOW_IT_WORKS](HOW_IT_WORKS.md#two-tiers) |
| Policy | a trained strategy: it reads what a drone sees and sends a velocity command | [HOW_IT_WORKS](HOW_IT_WORKS.md#where-a-strategy-plugs-in) |
| Game (environment) | one copy of the game; thousands run at once on the GPU. Isaac Lab calls it an environment | config `num_games` |
| Game-step (environment step) | one tick of game time for one game: one policy step, 1/20 s. Records say "environment steps per second" | [S0_RESULTS](S0_RESULTS.md) |
| Drone-step | one tick of game time for one drone; drone-steps = game-steps × drones per game | [S0_RESULTS](S0_RESULTS.md) |
| Case | one named set-up in the benchmark config, for example `t1_5v3_full` | [config](../configs/s0_benchmark.toml) |
| Sweep point | one case at one number of games; T1 had 96 (65 tier 1, 31 tier 2) | [S0_RESULTS](S0_RESULTS.md) |
| Repeat spread | how far two repeats of the same point differ: their difference ÷ their mean. S0's gate allows at most 0.10 | [config](../configs/s0_benchmark.toml) |
| Run of record | the official run whose numbers we keep; it ends in a record and a ledger row, for example T1 | [ledger](../records/LEDGER.md) |
| Gate | a pass/fail check written before a run and never moved afterwards | [STANDARDS §7](../STANDARDS.md#7-evaluation-and-gates) |
| Decision rule | a threshold, PROPOSED in advance, that helps choose the next step; read off the numbers, it never passes or fails a run | [S0_RESULTS](S0_RESULTS.md#decision-rules--training-simulator-only) |
| Record | the written summary of one run, `records/<name>_record.md`, made by `scripts/make_record.py` from the results; never edited | [STANDARDS §8](../STANDARDS.md#8-runs-and-records) |
| Ledger | the list of all runs, `records/LEDGER.md`, one row each: T1, T2, …; separate from the flight ledger (rows #1, #2, …) | [ledger](../records/LEDGER.md) |
| Container | a sealed copy of the software and its libraries (here, NVIDIA's Isaac Lab image plus our tools) that runs the same on every machine | [docker/README](../docker/README.md) |
| Headless | running with no window on screen; faster, and the normal way to train | [TRAINING](TRAINING.md) |
| Container UTC | T1's dates (rows, record, ledger) are UTC from the container; add 8 h for Singapore time | [S0_RESULTS](S0_RESULTS.md#the-fail) |
| sha256, hash | a fingerprint of a file: change one character and it changes completely | [GETTING_STARTED](GETTING_STARTED.md#approved-sha256) |
| Code hash (`code_sha`) | first 12 hex digits of a sha256 over `source/`, `scripts/` and `configs/`; in every result row | [record](../records/2026-11-15_s0_laptop_record.md#code-version) |
| Approved config hash | sha256 of the config the owner approved; `scripts/run_s0.sh` refuses a different one (exit 65) | [GETTING_STARTED](GETTING_STARTED.md#approved-sha256) |
| Seed | the starting number for the random draws; the same seed gives the same run | [STANDARDS §6](../STANDARDS.md#6-training-rules) |
| Held-out | data kept aside and used only to judge a fit or a policy, never to train it. In S1, every other push was held out, chosen before any fit | [DESIGN §7](DESIGN.md#7-environments-and-contact-tags), [S1_RESULTS](S1_RESULTS.md#2-first-fit-to-the-airstack-simulator-t3-fail) |
| Status labels | FIXED, MEASURED, PROPOSED, OPEN: where a value comes from and whether it may change | [STANDARDS](../STANDARDS.md) |
| Plug-in point | `/svg/{name}/teleop_command`: the place where a strategy's velocity command enters the flight software | [STANDARDS §3](../STANDARDS.md#3-policy-interface-version-0-proposed) |
| Guard team | the drone team that holds a circular zone | [STANDARDS §4](../STANDARDS.md#4-game-specification-version-0) |
| Strike team | the drone team that tries to reach the zone; its drones are 1.5 times as fast | [STANDARDS §4](../STANDARDS.md#4-game-specification-version-0) |
| Tag | the scoring event of the game between a Guard drone and a Strike drone; defined in [STANDARDS §4](../STANDARDS.md) | [STANDARDS §4](../STANDARDS.md#4-game-specification-version-0) |
| Safety filter (within each team) | CMU's filter that keeps drones apart; in the game it acts only between drones of one team | [STANDARDS §5](../STANDARDS.md#5-drone-models) |
| Keep-out distance | 1.10 m centre to centre (0.55 m radius): how close the safety filter lets two drones' commanded speeds bring them. The filter does not correct the position the commander sends, so drones can come slightly closer (1.083 m in a tier 1 test) | [STANDARDS §5](../STANDARDS.md#5-drone-models), [S1_RESULTS](S1_RESULTS.md#6-tier-1-with-the-real-chain-t4-information-only) |
| Sweep (safety filter) | one round of small corrections to every drone's speed in the filter copy; more sweeps get closer to CMU's answer but cost time. T2 used 1,000. Not the same as a *sweep point* | [S1_RESULTS](S1_RESULTS.md#1-the-safety-filter-copy-t2-fail-accepted-by-the-owner) |
| Commander | CMU's ground-control program (`swarm_commander.py`); 20 times a second it turns each drone's speed command into an instruction for PX4 | [S1_RESULTS](S1_RESULTS.md#3-why-two-clocks-in-the-simulator) |
| Commander teleop law | the commander's rules for a speed command: cap it, ramp up to it, move a reference point ("where the drone should be") by it, keep that point within 0.5 m of the drone, apply the safety filter. Tier 1 has a copy of the real-drone version (`models/commander.py`) | [S1_RESULTS](S1_RESULTS.md#6-tier-1-with-the-real-chain-t4-information-only) |
| PX4 | the flight software on the drone; version 1.14 on the real drones, 1.16.1 in the AirStack simulator | [STANDARDS §5](../STANDARDS.md#5-drone-models) |
| Trajectory setpoint | the instruction the commander sends a real drone each tick: a position, a speed and an acceleration together. PX4 closes the position loop itself. The AirStack simulator gets a speed only, through MAVROS | [S1_RESULTS](S1_RESULTS.md#4-the-real-drone-takes-a-different-route) |
| Position gain | PX4's `MPC_XY_P`, 0.95 per second on our drones: how much extra speed PX4 adds per metre the drone is away from its position setpoint | [S1_RESULTS](S1_RESULTS.md#5-a-first-fit-from-real-flight-logs-exploratory) |
| Time scale | how many seconds pass on the simulated drone's clock for each second on the wall clock; 1.907 in the S1 simulator session, 1.01 on the real drone | [S1_RESULTS](S1_RESULTS.md#3-why-two-clocks-in-the-simulator) |
| Exploratory | a first look with no gates and no ledger row; its numbers guide the next step but prove nothing | [S1_RESULTS](S1_RESULTS.md) |
| Observed in flight logs | the wording for a model fitted to real flight logs without a run of record; never "validated" | [S1_RESULTS](S1_RESULTS.md) |
| Distance field | a 3D grid holding the distance to the nearest structure; one copy on the GPU serves every game | [DESIGN §4](DESIGN.md#4-two-tiers-one-game) |
| Range ray | a ray from a drone that returns the distance to the first structure it meets | [STANDARDS §3](../STANDARDS.md#3-policy-interface-version-0-proposed) |
| Line of sight | whether one drone can see another past structures; a hidden drone is masked | [DESIGN §7](DESIGN.md#7-environments-and-contact-tags) |
| Stand-in (placeholder) model | the drone model used until a fitted one exists: tier 1 delay + lag, tier 2 ARL Robot 1 | [S0_RESULTS](S0_RESULTS.md#limits) |
| Observed in the training simulator | the only way to describe a result here; no result here is a flight result | [STANDARDS §2](../STANDARDS.md#2-wording) |
| Partner rules preset | the main game of S2, after NUS's rules: opposite teams kept apart by the push-apart rule, teammates pass through each other, one step inside the zone wins for the Strike team, a time-out wins for the Guard team. The committed values are neutral; NUS's own values live only in the git-ignored `configs/local/` | [S2_RESULTS](S2_RESULTS.md#what-was-built), [PLUG_IN](PLUG_IN.md#your-own-game-numbers-stay-local) |
| Pure partner rules (`pure`) | the partner rules with drones as points moving at fixed team speeds, all at one height | [PLUG_IN](PLUG_IN.md#pure-rules-and-the-starling-layer) |
| Push-apart rule | under the pure rules, a move that would bring a drone inside the other team's keep-out distance is cut short | [PLUG_IN](PLUG_IN.md#words-used-here) |
| Starling layer (`starling`) | a switch that makes drones fly like our Starlings: each command goes through a copy of CMU's commander, the safety filter on every pair of drones (both teams) and the drone model `real_exploratory_v0`; the push-apart rule is then off | [S2_RESULTS](S2_RESULTS.md#what-was-built) |
| Size band | arena sizes reported separately: lab 4–6 m, middle 6–10 m, large 10–16 m a side | [S2_RESULTS](S2_RESULTS.md#3-the-scripted-reference-t6-re-run-as-t9) |
| Start miss | a game whose drones could not be placed far enough apart at the start (crowded small arenas: 34.7 % of 5 v 3 lab games in T9); it is played and counted, and flagged | [S2_RESULTS](S2_RESULTS.md#4-how-close-guard-and-strike-drones-came) |
| Hold rate | the share of games in which no Strike drone reached the zone before the time-out, given with its 95 % interval; for a Strike strategy, its win share is 1 − hold rate | [S2_RESULTS](S2_RESULTS.md#3-the-scripted-reference-t6-re-run-as-t9) |
| Strategy contract | the rule a strategy follows to be scored: it plays one team, is called once per step with all its drones' observations in all games, returns all their actions, and is told which games just restarted | [PLUG_IN](PLUG_IN.md#three-layers) |
| Scripted opponent | a hand-written strategy used as an opponent and a yardstick: Guard mark edge, mark inside, field, mirror, random; Strike straight, flank | [S2_RESULTS](S2_RESULTS.md#3-the-scripted-reference-t6-re-run-as-t9) |
| Scoring tool | `scripts/score.py`: plays strategies against each other per size band, team size and rule set, and reports hold rate, closest approach, breaches, filter use and start misses | [PLUG_IN](PLUG_IN.md#what-the-scoring-tool-prints) |
| Adapter | a thin wrapper that lets a training library drive the game: `SvgSkrlEnv` (skrl) and `SvgTeamVectorEnv` (Gymnasium) | [PLUG_IN](PLUG_IN.md#plug-a-training-method-in) |
| Stand-in trainer (pipe test) | a short training run whose only job is to prove the pipe works end to end; never "the policy". Moved from S2 to S2b (owner, 16 November 2026) | [S2_RESULTS](S2_RESULTS.md#5-the-stand-in-trainer-moved-to-s2b) |
| Rule breach (breach) | a game in which some Guard drone and some Strike drone came closer than the keep-out distance; since T9 judged in 3-D | [S2_RESULTS](S2_RESULTS.md#4-how-close-guard-and-strike-drones-came) |
| Closest approach, horizontal and 3-D | the smallest distance between any Guard drone and any Strike drone in a game. Horizontal ignores height; 3-D does not. They differ when drones pass one above the other (T6: 0.004 m horizontally, 0.851 m in 3-D in one probe) | [S2_RESULTS](S2_RESULTS.md#4-how-close-guard-and-strike-drones-came) |
| Early stop, `check_every` | a filter option: every `check_every` sweeps it checks which games still need work and stops when none is left (0 = no early stop). S2 uses 1,000 sweeps with a check every 8 (T8) | [S2_RESULTS](S2_RESULTS.md#1-a-faster-safety-filter-t7-aborted-t8-pass) |
| Interface change, 69 → 71 | on 16 November 2026 each drone's observation gained the zone centre's place in the arena (indices 69–70), so a drone can find the walls | [S2_RESULTS](S2_RESULTS.md#one-change-to-the-interface) |
| S2b | the S2 game on rigid-body Starlings in Isaac Lab, with the stand-in trainer on both versions; approved 16 November 2026 | [S2b plan](plans/2026-11-16-s2b-isaac-lab-environment.md), [S2B_RESULTS](S2B_RESULTS.md) |
| Physics backend (`physics`) | the third way the game can move the drones, added in S2b: each command goes through the same commander copy and safety filter as the Starling layer, then to the physics drone instead of the fitted model | [S2B_RESULTS](S2B_RESULTS.md#what-was-built) |
| Physics drone | a Starling as a rigid body with four rotors, flown by the PX4 cascade with the drone's own gains (yaw-rate gains SIM-ONLY, owner's ruling of 16 November 2026); it runs in Isaac Lab or the PyTorch reference world | [S2B_RESULTS](S2B_RESULTS.md#what-was-built) |
| PX4 cascade | PX4 1.14's chain of control loops, copied line by line: position → speed → acceleration → attitude (tilt) → turn rate → rotor commands, run 200 times a second with the true state (no estimator, no delay) | [S2B_RESULTS](S2B_RESULTS.md#what-was-built) |
| Rotor model | turns the cascade's rotor commands into one force and one torque on the body: each rotor's speed follows its command with the measured motor lag (55 ms up, 85 ms down), thrust grows with speed squared; CAD rotor positions for the body | [S2B_RESULTS](S2B_RESULTS.md#what-was-built) |
| PyTorch reference world (torch reference world, test oracle) | the physics drone's equations in plain PyTorch, with no Isaac; the CPU tests run on it, and T10 checks Isaac Lab against it. A *test oracle* is the answer a test compares with | [S2B_RESULTS](S2B_RESULTS.md#1-do-isaac-lab-and-the-pytorch-reference-world-move-the-drones-the-same-way-t10-fail-accepted) |
| Cell (matchup cell) | one matchup in a scoring run: one Guard strategy against one Strike strategy, at one team size, in one arena size band; T13 has 60 cells of 1,000 games each | [S2B_RESULTS](S2B_RESULTS.md#4-the-scripted-games-on-both-backends-t13-fail) |
| S0's 20,000 line | S0's decision rule: if tier 2 runs at least 20,000 drone-steps a second, it is fast enough to train on directly, not only to cross-check; read off the numbers, it never fails a run | [S0_RESULTS](S0_RESULTS.md#decision-rules--training-simulator-only) |
| Agreement (run) | T10: the same forces and the same cascade in Isaac Lab and the torch reference world, to measure how far apart they end up | [T10 record](../records/2026-11-16_s2b_agreement_record.md) |
| Upset | a physics drone that tips past 60° or whose numbers turn non-finite; counted per game; the S2b gates that count upsets allow none | [S2B_RESULTS](S2B_RESULTS.md#the-gates) |
| Paired games | the same arenas, zones and starts played on two backends (`score.py --batch-per-pair`, same seed), so any difference comes from the drone model, not from chance | [S2B_RESULTS](S2B_RESULTS.md#4-the-scripted-games-on-both-backends-t13-fail) |
| Preflight | `scripts/isaac_preflight.sh`, run before every Isaac start: it stops on a WiFi-only remote-desktop session (exit 10) or a busy GPU (exit 11). Not the flight-stack's `docs/PREFLIGHT.md` safety card | [S2B_RESULTS](S2B_RESULTS.md#what-was-built) |
| Build steps S0–S5 | Measure, Drone model, One against one, Two against one, Five against three, Hand-over. S2 became "the game and the plug-in point" ([S2 design](specs/2026-11-15-s2-game-and-plug-in-design.md)), followed by S2b | [DESIGN §8](DESIGN.md#8-build-order) |
| Versions | which Isaac Lab, Isaac Sim and PX4 run where | [below](#versions) |

## Versions

The table lists which version of each tool runs where.

| What | Version | Used by |
|---|---|---|
| Container image | `nvcr.io/nvidia/isaac-lab:2.3.2` = Isaac Lab 2.3.2 on Isaac Sim 5.1.0; ours is `svg-training:isaaclab-2.3.2` (not yet built on the 5090) | the container ([docker/README](../docker/README.md)); run of record T1 |
| Host install, laptop (RTX 5070 Ti) | `~/IsaacLab`, 2.3.2 plus 25 commits (`f73c331738`), none touching code tier 2 uses | host runs on the laptop, conda `env_isaaclab` |
| Host install, 5090 workstation | `~/IsaacLab` at the tag v2.3.2 exactly (`37ddf62687`), clean; MEASURED 17 Nov 2026 | host runs on the 5090, conda `env_isaaclab` |
| Host Python environment, laptop | conda `env_isaaclab`: Python 3.11, torch 2.7.0+cu128, Isaac Sim 5.1.0, skrl 2.1.0, gymnasium 1.2.1 | host runs on the laptop |
| Host Python environment, 5090 | conda `env_isaaclab`: Python 3.11, torch 2.7.0+cu128, Isaac Sim 5.1.0, skrl 2.1.0, warp-lang 1.14.0; MEASURED 17 Nov 2026, after the [hand fixes](GETTING_STARTED.md#hand-fixes-after-the-setup-script) | host runs on the 5090 |
| Isaac Lab 3.0 | needs Isaac Sim 6.2 and Python 3.12 | later, on the training workstations |
| AirStack simulator | Isaac Sim 5.1.0 + Pegasus + PX4 v1.16.1 | stage 6, simulated flight |
| Real drones | PX4 1.14 | stage 7, real flight |
| Laptop GPU driver | 580.178.04 (RTX 5070 Ti Laptop GPU, 12 GB) | T1 |
| 5090 GPU driver | 580.126.09 (RTX 5090, 32 GB); MEASURED 17 Nov 2026 | host runs on the 5090 |
