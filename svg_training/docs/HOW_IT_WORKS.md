# How the training pipeline works

New here? The story of what has been done so far, in order, is in [WHAT_WE_DID](WHAT_WE_DID.md).

This page gives the picture first, then the parts. Terms are in the [glossary](GLOSSARY.md). The full design, with
reasons, is [DESIGN.md](DESIGN.md). The diagrams are in the deck, [training-pipeline.pptx](pipeline/training-pipeline.pptx).
Use the deck for pictures and this page for where things stand.

## The game

- The **Guard team** holds a circular zone; the **Strike team** tries to reach it. Strike drones are 1.5 times as fast.
- The Guard team's aim is to tag Strike drones ([glossary](GLOSSARY.md)). Games are played in realistic 3D worlds.
- A strategy (a *policy*) is trained here. It then flies through AirStack on Starling 2 Max drones without changes.

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
| 7 | Real flight | Crazyflies first, then Starlings | the flight stack's own rules |

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
| A drone is (planned) | a point that answers a velocity command the way PX4 does: lag, delay, limits | a body with four rotors in Isaac Lab, flown by a PX4-style controller |
| A drone is (S0 today) | a placeholder: 0.15 s delay and 0.55 s lag, not yet fitted | Isaac Lab's ARL Robot 1 airframe; no controller; its state is rewritten each step |
| A drone is (S1 today) | the real drone's command chain: a copy of the commander's rules, then PX4's response taken from real flight logs (exploratory, no run of record yet); the AirStack simulator's fit describes that simulator only | unchanged |
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
| Safety filter | keeps drones of the same team apart; it does not act between the two teams |

Status labels and sources for every item: [STANDARDS §3](../STANDARDS.md#3-policy-interface-version-01-proposed).

A partner's strategy plugs into the training simulator through the strategy contract ([PLUG_IN](PLUG_IN.md)). A
partner's trained JAX policy has a scoring hook since 18 November 2026: `svg_training.nus.strategy:NusPolicy` reads a
converted checkpoint (layout id `nus_area_denial_v1`) and plays one team, scored like any strategy
([PLUG_IN](PLUG_IN.md#plug-in-a-trained-nus-policy)). The exported policy file and `interface.toml` for the AirStack
simulator and for flight still arrive with build step S5
([STANDARDS §3](../STANDARDS.md#3-policy-interface-version-01-proposed)); the NUS policy's `interface.toml` is a draft.
The whole NUS port (NUS's code run as the reference, the copy of NUS's game, the converted policy and the transfer
ladder towards our drones), with NUS's settings and our results: [NUS_PORT](NUS_PORT.md).

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

The table shows each build step and where it stands.

| Step | What it builds | Where it stands |
|---|---|---|
| S0 Measure | benchmarks for both tiers, records, ledger, container | done on the laptop: T1 = FAIL on one gate ([results](S0_RESULTS.md)); workstation run to do |
| S1 Drone model | tier 1 carries the real drone's command chain, with PX4's response from real flight logs; safety filter copy | built and run, no drone-model gate passed yet: T2 and T3 FAIL, real-log fit exploratory, T4 information only ([results](S1_RESULTS.md)); next, a real flight with planned pushes (owner) |
| S2 The game and the plug-in point | open arena, game rules, scripted opponents, scoring tool, partner guide | closed 16 November: T8 PASS, T5 FAIL, T9 information only ([results](S2_RESULTS.md)) |
| S2b The game on Isaac Lab drones | rigid-body Starlings with a PX4 1.14 cascade; stand-in trainer | built through Task 8, not closed: T10–T14 ([results](S2B_RESULTS.md)) |
| NUS port (beside the build steps) | NUS's code as the reference, a copy of NUS's game, NUS's policy converted, the transfer ladder | T15–T17 PASS, ladder rows 1–6 scored (T18–T24 INFO): the safety filter and 3-D undo NUS's push-based blocking; Phase 5 planned ([NUS_PORT](NUS_PORT.md)) |
| S3 Two against one | random blocks and columns, line of sight, opponent pool | not started |
| S4 Five against three | the construction-site world, team-size randomisation, tier 2 cross-check | not started |
| S5 Hand-over | export and `interface.toml`; a ROS 2 policy node needs the owner's separate approval | not started |

Nothing of ours has been trained into a strategy yet: the stand-in trainer is a pipe test (T14), and the NUS policies were trained with NUS's own code. Where each step ends: [DESIGN §8](DESIGN.md#8-build-order).
