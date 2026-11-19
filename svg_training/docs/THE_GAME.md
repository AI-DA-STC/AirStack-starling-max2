READ · the training pipeline in one picture, and the game as an RL environment.

# How the training pipeline works

New here? Start at the [front page](../README.md); what happened when is in [docs/README.md, History](README.md#history).

This page gives the picture first, then the parts. Terms are in the [glossary](GLOSSARY.md). The full design, with
reasons, is [DESIGN.md](DESIGN.md). The diagrams are in the deck, [training-pipeline.pptx](pipeline/training-pipeline.pptx).
Use the deck for pictures and this page for where things stand.

## The game

- The **Guard team** holds a circular zone; the **Strike team** tries to reach it. Strike drones are 1.5 times as fast.
- Strike drones try to reach the zone; Guard drones try to keep them out until the time-out. Contact tags are a separate track ([glossary](GLOSSARY.md)). Our own build steps play in 3-D worlds; the NUS port plays an empty hangar arena.
- A strategy (a *policy*) is trained here. It is meant to fly through AirStack on Starling 2 Max drones without changes; nothing has flown yet.

## The idea in one picture

The picture shows the seven stages. The first five happen in this folder; the last two use the flight software
that already exists.

```
flight logs → 1 Identify → 2 Train → 3 Evaluate → 4 Cross-check → 5 Export │ 6 AirStack simulator → 7 Real flight
              └──────────── this folder, svg_training/ ────────────────────┘ └──── existing flight stack ─────┘
```

## Seven stages

Each stage ends on a pass/fail check set before the run (a *gate*). The table lists them.

| # | Stage | What it does | Finished when |
|---|---|---|---|
| 1 | Identify | fits a drone model to how a Starling answers a velocity command | model error within a limit set beforehand |
| 2 | Train | plays thousands of games at once on one GPU; the policy learns | training gates |
| 3 | Evaluate | scores a checkpoint against fixed opponents, starts, team sizes and worlds | the fixed evaluation suite |
| 4 | Cross-check | replays the same checkpoint on the heavier tier 2 drone | gap between tiers within a limit |
| 5 | Export | writes the policy file and its `interface.toml` | file loads and reproduces recorded outputs |
| 6 | Simulated flight | flies the policy in the AirStack simulator, PX4 software, up to 3 drones | matches training within a limit |
| 7 | Real flight | the lab's palm-sized Crazyflie drones first, then Starlings | the flight stack's own rules |

A failed gate sends the work back. A failed training gate sends it back to the reward or the opponents. If the
cross-check or the simulated flight disagrees with training, the drone model is wrong and goes back to stage 1.
Detail: [DESIGN §3](DESIGN.md#3-the-pipeline-seven-stages).

## Two tiers

The game is written once in PyTorch: its rules, what each drone sees, the rewards, the safety filter and the shape
of the world. Two drone models plug in underneath it. *Tier 1* is fast and simple. *Tier 2* is a full physics model
in Isaac Lab. Both are the training simulator; the AirStack simulator is a separate one, used in stage 6. The table
compares the two tiers.

| | Tier 1: response model | Tier 2: rigid body |
|---|---|---|
| A drone is | a point that follows its speed command through a copy of the commander's rules, then a delay-and-lag response fitted to one real flight log (exploratory: its check against a real flight, T5, is a FAIL) | a rigid body with four rotors in Isaac Lab, flown by a copy of PX4 1.14's control loops (S2b) |
| Needs Isaac | no; tests run in seconds | yes |
| Speed (S0, laptop) | 5 v 3: 98.3 million drone-steps / s in the open arena; 382,206 with full sensing | 455,300 drone-steps / s at best (3 drones per game, 100 Hz) |
| Used for | bulk training | the cross-check; later flight control and cameras |

A *drone-step* is one tick of game time (1/20 s) for one drone. The speeds were observed in the training
simulator; their scope and limits are in [S0_RESULTS](S0_RESULTS.md). The full comparison is in
[DESIGN §4](DESIGN.md#4-two-tiers-one-game).

## Where a strategy plugs in

The trainer copies the interface the flight software already has, so a trained policy needs no translation. The
place where its commands enter the flight software is the *plug-in point*. The table lists what the policy sends.

| Item | Value |
|---|---|
| The policy sends, per drone | `[vx, vy, vz, yaw_rate]` |
| Frame and units | world ENU (x east, y north, z up), m/s and rad/s |
| Rate | 20 commands a second |
| Topic in AirStack (the plug-in point) | `/svg/{name}/teleop_command` (`TwistStamped`) |
| No fresh command for 0.5 s | the drone holds position |
| Safety filter | CMU's collision filter acts on every pair of drones, both teams, as in flight: both drones of a close pair give way (1.10 m keep-out). The contact-tag track alone filters within a team |

Status labels and sources for every item: [STANDARDS §3](../STANDARDS.md#3-policy-interface-version-01-proposed).

Your strategy plugs into the training simulator through the strategy contract ([PLUG_IN](PLUG_IN_YOUR_CODE.md)). A
trained JAX policy from NUS has a scoring hook since 18 November 2026: `svg_training.nus.strategy:NusPolicy` reads a
converted checkpoint (layout id `nus_area_denial_v1`) and plays one team, scored like any strategy
([PLUG_IN](PLUG_IN_YOUR_CODE.md#plug-in-a-trained-nus-policy)). The exported policy file and `interface.toml` for the AirStack
simulator and for flight still arrive with build step S5
([STANDARDS §3](../STANDARDS.md#3-policy-interface-version-01-proposed)); the NUS policy's `interface.toml` is a draft.
The whole NUS port (NUS's code run as the reference, the copy of NUS's game, the converted policy and the transfer
ladder towards our drones), with NUS's settings and our results: [NUS_PORT](WHAT_WE_DID_DAY_BY_DAY.md).

## The game as an RL environment

| Item | Our game (build steps, `core/game.py`) | The NUS port's hangar game (Phase 4 rows, Phase 5) |
|---|---|---|
| Batching | N games at once on one device, plain PyTorch tensors; `reset()`, `step(actions)`; finished games restart inside the same `step` | the same engine, 3 v 3 only |
| Agents | 1–5 Guard and 1–3 Strike drones per game, drawn per game; one network per drone or one per team | 3 Guard v 3 Strike, fixed |
| Observation, per drone | 71 numbers: itself, 5 Guard slots and 3 Strike slots of 7 numbers each, the zone ([PLUG_IN](PLUG_IN_YOUR_CODE.md#plug-a-training-method-in)) | ours, or NUS's 9N + 2 (56 numbers) rebuilt from it by `NusPolicy` |
| Action, per drone | 4 numbers in [−1, 1]: `[vx, vy, vz, yaw_rate]`, scaled by the team's speed, 20 per second | NUS policies: a 2-D move held for 12 ticks (0.60 s) |
| Reward | +1 / −1 per team at the end (hold / reach), 0 otherwise; optional shaping, off in the committed file | Phase 5.2 plans NUS's own reward (inside-share penalty, first-reach penalty, shaping) |
| Episode | ends at the first Strike reach or the time-out: 1,200 ticks (60 s) | 2,400 ticks (120 s) |
| Drone model | tier 1 (fast, CPU or GPU) or tier 2 (Isaac Lab, GPU) | rows 1–5 tier 1, row 6 tier 2 |
| Libraries | skrl (`SvgSkrlEnv`) and Gymnasium (`SvgTeamVectorEnv`) adapters | NUS's method ported to PyTorch (in progress) |

## What a benchmark run does

`scripts/run_s0.sh` is the one command that runs S0. How to start it: [GETTING_STARTED](GETTING_STARTED.md). The
table lists its steps in order.

| Step | What happens |
|---|---|
| 1–3 | checks the arguments, that the config is the approved one, and that no Isaac or AirStack container runs |
| 4–5 | makes `runs/<name>/`; writes `preflight.txt` (time, code hash, config hash, GPU state) |
| 6 | runs the tests into `tests.txt` |
| 7 | tier 1 sweep: every tier 1 case at every number of games, in one process |
| 8 | tier 2 sweep: one Isaac Lab process per point |
| 9 | `scripts/make_record.py` writes the record and the ledger row, with PASS or FAIL per gate |

The *record* is the written summary of a run; the *ledger* is the list of all runs. A *hash* is a short
fingerprint of a file: if the file changes, the hash changes. A *container* is a sealed copy of the software that
runs the same way on every machine. Each point warms up for at least 50 steps and 2 s.
Then it times at least 200 steps and 2 s, twice.

## What exists today

Where each build step and the NUS port stand, with their records: [docs/README.md, History](README.md#history).
Nothing of ours has been trained into a strategy yet.
