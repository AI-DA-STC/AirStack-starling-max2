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
| Held-out | data kept aside and used only to judge a fit or a policy, never to train it | [DESIGN §7](DESIGN.md#7-environments-and-contact-tags) |
| Status labels | FIXED, MEASURED, PROPOSED, OPEN: where a value comes from and whether it may change | [STANDARDS](../STANDARDS.md) |
| Plug-in point | `/svg/{name}/teleop_command`: the place where a strategy's velocity command enters the flight software | [STANDARDS §3](../STANDARDS.md#3-policy-interface-version-0-proposed) |
| Guard team | the drone team that holds a circular zone | [STANDARDS §4](../STANDARDS.md#4-game-specification-version-0) |
| Strike team | the drone team that tries to reach the zone; its drones are 1.5 times as fast | [STANDARDS §4](../STANDARDS.md#4-game-specification-version-0) |
| Tag | the scoring event of the game between a Guard drone and a Strike drone; defined in [STANDARDS §4](../STANDARDS.md) | [STANDARDS §4](../STANDARDS.md#4-game-specification-version-0) |
| Safety filter (within each team) | CMU's filter that keeps drones apart; in the game it acts only between drones of one team | [STANDARDS §5](../STANDARDS.md#5-drone-models) |
| Keep-out distance | 1.10 m centre to centre (0.55 m radius): how close the safety filter lets two drones come | [STANDARDS §5](../STANDARDS.md#5-drone-models) |
| Distance field | a 3D grid holding the distance to the nearest structure; one copy on the GPU serves every game | [DESIGN §4](DESIGN.md#4-two-tiers-one-game) |
| Range ray | a ray from a drone that returns the distance to the first structure it meets | [STANDARDS §3](../STANDARDS.md#3-policy-interface-version-0-proposed) |
| Line of sight | whether one drone can see another past structures; a hidden drone is masked | [DESIGN §7](DESIGN.md#7-environments-and-contact-tags) |
| Stand-in (placeholder) model | the drone model used until a fitted one exists: tier 1 delay + lag, tier 2 ARL Robot 1 | [S0_RESULTS](S0_RESULTS.md#limits) |
| Observed in the training simulator | the only way to describe a result here; no result here is a flight result | [STANDARDS §2](../STANDARDS.md#2-wording) |
| Build steps S0–S5 | Measure, Drone model, One against one, Two against one, Five against three, Hand-over | [DESIGN §8](DESIGN.md#8-build-order) |
| Versions | which Isaac Lab, Isaac Sim and PX4 run where | [below](#versions) |

## Versions

The table lists which version of each tool runs where.

| What | Version | Used by |
|---|---|---|
| Container image | `nvcr.io/nvidia/isaac-lab:2.3.2` = Isaac Lab 2.3.2 on Isaac Sim 5.1.0; ours is `svg-training:isaaclab-2.3.2` | the container ([docker/README](../docker/README.md)); run of record T1 |
| Host install (this laptop) | `~/IsaacLab`, 2.3.2 plus 25 commits (`f73c331738`), none touching code tier 2 uses | host runs, conda `env_isaaclab` |
| Host Python environment | conda `env_isaaclab`: Python 3.11, torch 2.7.0+cu128, Isaac Sim 5.1.0, skrl 2.1.0 | host runs |
| Isaac Lab 3.0 | needs Isaac Sim 6.2 and Python 3.12 | later, on the training workstations |
| AirStack simulator | Isaac Sim 5.1.0 + Pegasus + PX4 v1.16.1 | stage 6, simulated flight |
| Real drones | PX4 1.14 | stage 7, real flight |
| Laptop GPU driver | 580.178.04 (RTX 5070 Ti Laptop GPU, 12 GB) | T1 |
