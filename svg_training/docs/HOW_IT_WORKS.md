# How the training pipeline works

The picture first, then the parts. Terms are in the [glossary](GLOSSARY.md); the full design, with reasons, is
[DESIGN.md](DESIGN.md). Diagrams are in the deck, [training-pipeline.pptx](pipeline/training-pipeline.pptx);
use it for pictures, and this page for status.

## The game

- The **Guard team** holds a circular zone; the **Strike team** tries to reach it. Strike drones are 1.5 times as fast.
- The Guard team's aim is to tag Strike drones ([glossary](GLOSSARY.md)). Games are played in realistic 3D worlds.
- A strategy (policy) is trained here, then flown through AirStack on Starling 2 Max drones without changes.

## The idea in one picture

```
flight logs → 1 Identify → 2 Train → 3 Evaluate → 4 Cross-check → 5 Export │ 6 AirStack simulator → 7 Real flight
              └──────────── this folder, svg_training/ ────────────────────┘ └──── existing flight stack ─────┘
```

## Seven stages

| # | Stage | What it does | Ends on |
|---|---|---|---|
| 1 | Identify | fits a drone model to how a Starling answers a velocity command | model error within a limit set beforehand |
| 2 | Train | plays thousands of games at once on one GPU; the policy learns | training gates |
| 3 | Evaluate | scores a checkpoint against fixed opponents, starts, team sizes and worlds | the fixed evaluation suite |
| 4 | Cross-check | replays the same checkpoint on the heavier tier 2 drone | gap between tiers within a limit |
| 5 | Export | writes the policy file and its `interface.toml` | file loads and reproduces recorded outputs |
| 6 | Simulated flight | flies the policy in the AirStack simulator, PX4 software, up to 3 drones | matches training within a limit |
| 7 | Real flight | Crazyflies first, then Starlings | the flight stack's own rules |

A failed gate sends work back: a training gate to the reward or the opponents; a cross-check or simulated flight
that disagrees with training to the drone model (stage 1). Detail: [DESIGN §3](DESIGN.md#3-the-pipeline-seven-stages).

## Two tiers

One game (rules, observations, rewards, safety filter, world shape) is written once in PyTorch. Two drone
models plug in underneath it.

| | Tier 1: response model | Tier 2: rigid body |
|---|---|---|
| A drone is (planned) | a point that answers a velocity command the way PX4 does: lag, delay, limits | a body with four rotors in Isaac Lab, flown by a PX4-style controller |
| A drone is (S0 today) | a placeholder: 0.15 s delay and 0.55 s lag, not yet fitted | Isaac Lab's ARL Robot 1 airframe; no controller; its state is rewritten each step |
| Needs Isaac | no; tests run in seconds | yes |
| Speed (S0, laptop) | 5 v 3: 98.3 million drone-steps / s in the open arena; 382,206 with full sensing | 455,300 drone-steps / s at best (3 drones per game, 100 Hz) |
| Used for | bulk training | the cross-check; later flight control and cameras |

Speeds were observed in the training simulator; scope and limits in [S0_RESULTS](S0_RESULTS.md).
The full comparison: [DESIGN §4](DESIGN.md#4-two-tiers-one-game).

## Where a strategy plugs in

The trainer copies the interface the flight stack already has, so a trained policy needs no translation.

| Item | Value |
|---|---|
| The policy sends, per drone | `[vx, vy, vz, yaw_rate]` |
| Frame and units | world ENU (x east, y north, z up), m/s and rad/s |
| Rate | 20 commands a second |
| Topic in AirStack | `/svg/{name}/teleop_command` (`TwistStamped`) |
| No fresh command for 0.5 s | the drone holds position |
| Safety filter | keeps drones of the same team apart; not between the two teams |

Status labels and sources for every item: [STANDARDS §3](../STANDARDS.md#3-policy-interface-version-0-proposed).

There is no code hook for a partner's strategy yet: the exported policy file and `interface.toml` arrive with
build step S5 ([STANDARDS §3](../STANDARDS.md#3-policy-interface-version-0-proposed)).

## What a benchmark run does

`scripts/run_s0.sh` is the one front door for S0. How to start it: [GETTING_STARTED](GETTING_STARTED.md).

| Step | What happens |
|---|---|
| 1–3 | checks the arguments, that the config is the approved one, and that no Isaac or AirStack container runs |
| 4–5 | makes `runs/<name>/`; writes `preflight.txt` (time, code hash, config hash, GPU state) |
| 6 | runs the tests into `tests.txt` |
| 7 | tier 1 sweep: every tier 1 case at every number of games, in one process |
| 8 | tier 2 sweep: one Isaac Lab process per point |
| 9 | `scripts/make_record.py` writes the record and the ledger row, with PASS or FAIL per gate |

Each point warms up for at least 50 steps and 2 s, then times at least 200 steps and 2 s, twice.

## What exists today

| Step | Builds | State |
|---|---|---|
| S0 Measure | benchmarks for both tiers, records, ledger, container | done on the laptop: T1 = FAIL on one gate ([results](S0_RESULTS.md)); workstation run to do |
| S1 Drone model | fitted tier 1 model from AirStack simulator logs; safety filter port | building; [plan](plans/2026-11-15-s1-drone-model-and-safety-filter.md) approved 15 Nov |
| S2 One against one | open arena, game rules with tags, scripted opponents, evaluation suite | not started |
| S3 Two against one | random blocks and columns, line of sight, opponent pool | not started |
| S4 Five against three | the construction-site world, team-size randomisation, tier 2 cross-check | not started |
| S5 Hand-over | export and `interface.toml`; a ROS 2 policy node needs the owner's separate approval | not started |

Nothing has been trained yet. Where each step ends: [DESIGN §8](DESIGN.md#8-build-order).
