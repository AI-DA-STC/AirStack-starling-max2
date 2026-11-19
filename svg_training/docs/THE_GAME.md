READ · the game, the training pipeline in one picture, and the game as an RL environment.

# The game and the training pipeline

**For** newcomers, NUS researchers included. **STE**: the lab that wrote this repository. The front page is
[svg_training](../README.md); what happened when is in [the map of the pages, history](README.md#history).

This page gives the game first, then the picture, then the parts. Terms are in the [glossary](GLOSSARY.md). The full design, with
reasons, is [DESIGN.md](DESIGN.md). The diagrams are in the deck, [training-pipeline.pptx](pipeline/training-pipeline.pptx).
Use the deck for pictures and this page for where things stand.

## The game

- The **Guard team** holds a circular zone; the **Strike team** tries to reach it (NUS's code calls them `defender`
  and `attacker`: defender (Guard team), attacker (Strike team)). Strike drones are 1.5 times as fast.
- Strike drones try to reach the zone; Guard drones try to keep them out until the time-out. Contact tags are a separate track ([glossary](GLOSSARY.md)). STE's own build steps play in 3-D worlds; the NUS port plays an empty 7.5 m square arena sized to STE's flight room (the hangar).
- A strategy (a *policy*) is trained here. It is meant to fly through AirStack (CMU's flight software) on Starling 2 Max
  drones (ModalAI's small indoor drone) without changes; nothing has flown yet.

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
| 4 | Cross-check | replays the same checkpoint on the heavier Isaac Lab physics drones | gap between the two drone models within a limit |
| 5 | Export | writes the policy file and its `interface.toml` | file loads and reproduces recorded outputs |
| 6 | Simulated flight | flies the policy in the AirStack simulator, PX4 software, up to 3 drones | matches training within a limit |
| 7 | Real flight | the lab's palm-sized Crazyflie drones first, then Starlings | the flight stack's own rules |

A failed gate sends the work back. A failed training gate sends it back to the reward or the opponents. If the
cross-check or the simulated flight disagrees with training, the drone model is wrong and goes back to stage 1.
Detail: [DESIGN §3](DESIGN.md#3-the-pipeline-seven-stages).

## Two drone models

The game is written once in PyTorch: its rules, what each drone sees, the rewards, the safety filter and the shape
of the world. Two drone models plug in underneath it. The *STE drone model (PyTorch)* ("tier 1" in the records) is fast and
simple. The *Isaac Lab physics drones* ("tier 2") are a full physics model in Isaac Lab. Both are the training simulator; the AirStack simulator is a separate one, used in stage 6. The table
compares the two.

| | STE drone model (PyTorch): response model | Isaac Lab physics drones: rigid body |
|---|---|---|
| A drone is | a point that follows its speed command through a copy of the commander's rules, then a delay-and-lag response fitted to one real flight log (exploratory: its check against a real flight, T5, is a FAIL) | a rigid body with four rotors in Isaac Lab, flown by a copy of PX4 1.14's control loops (S2b) |
| Needs Isaac | no; tests run in seconds | yes |
| Speed (S0, laptop) | 5 v 3: 98.3 million drone-steps / s in the open arena; 382,206 with full sensing | 455,300 drone-steps / s at best (3 drones per game, 100 Hz) |
| Used for | bulk training | the cross-check; later flight control and cameras |

A *drone-step* is one tick of game time (1/20 s) for one drone. The speeds were observed in the training
simulator; their scope and limits are in [S0_RESULTS](S0_RESULTS.md). The full comparison is in
[DESIGN §4](DESIGN.md#4-two-tiers-one-game) (the design says "tiers").

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

A strategy plugs into the training simulator through the strategy contract ([plug in your code](PLUG_IN_YOUR_CODE.md)). A
policy trained with NUS's JAX code has a scoring hook since 18 November 2026: `svg_training.nus.strategy:NusPolicy` reads a
converted checkpoint (layout id `nus_area_denial_v1`) and plays one team, scored like any strategy
([plug in a policy trained with NUS's code](PLUG_IN_YOUR_CODE.md#plug-in-a-policy-trained-with-nuss-code)). The exported policy file and `interface.toml` for the AirStack
simulator and for flight still arrive with build step S5
([STANDARDS §3](../STANDARDS.md#3-policy-interface-version-01-proposed)); the converted policy's `interface.toml` is a draft.
The whole NUS port (NUS's code run as the reference, the Copy of NUS 2-D game (PyTorch), the converted policies and
the six tests towards STE drones), with NUS's settings and STE's results: [what we did, day by day](WHAT_WE_DID_DAY_BY_DAY.md).

## The game as an RL environment

| Item | The STE game (build steps, `core/game.py`) | The NUS port's hangar game (Tests 2–6, Phase 5) |
|---|---|---|
| Batching | N games at once on one device, plain PyTorch tensors; `reset()`, `step(actions)`; finished games restart inside the same `step` | the same engine, 3 v 3 only |
| Agents | 1–5 Guard and 1–3 Strike drones per game, drawn per game; one network per drone or one per team | 3 Guard v 3 Strike, fixed |
| Observation, per drone | 71 numbers: itself, 5 Guard slots and 3 Strike slots of 7 numbers each, the zone ([plug in a training method](PLUG_IN_YOUR_CODE.md#plug-a-training-method-in)) | the STE observation, or NUS's 9N + 2 (56 numbers) rebuilt from it by `NusPolicy` |
| Action, per drone | 4 numbers in [−1, 1]: `[vx, vy, vz, yaw_rate]`, scaled by the team's speed, 20 per second | converted NUS-code policies: a 2-D move held for 12 ticks (0.60 s) |
| Reward | +1 / −1 per team at the end (hold / reach), 0 otherwise; optional shaping, off in the committed file | stage 5.2 plans NUS's own reward (inside-share penalty, first-reach penalty, shaping); the STE Guard policy used +1 / −1 at the end only |
| Episode | ends at the first Strike reach or the time-out: 1,200 ticks (60 s) | 2,400 ticks (120 s) |
| Drone model | STE drone model (fast, CPU or GPU) or Isaac Lab physics drones (GPU) | Tests 3–5 STE drone model (Test 2 points), Test 6 Isaac Lab physics drones |
| Libraries | skrl (`SvgSkrlEnv`) and Gymnasium (`SvgTeamVectorEnv`) adapters | the STE port of NUS's training method (PyTorch, in progress); skrl IPPO for the STE Guard policy ([training recipe](TRAIN_A_GUARD.md)) |

## What a benchmark run does

`scripts/run_s0.sh` is the one command that runs S0. How to start it: [GETTING_STARTED](GETTING_STARTED.md). The
table lists its steps in order.

| Step | What happens |
|---|---|
| 1–3 | checks the arguments, that the config is the approved one, and that no Isaac or AirStack container runs |
| 4–5 | makes `runs/<name>/`; writes `preflight.txt` (time, code hash, config hash, GPU state) |
| 6 | runs the tests into `tests.txt` |
| 7 | STE drone model sweep: every case at every number of games, in one process |
| 8 | Isaac Lab sweep: one Isaac Lab process per point |
| 9 | `scripts/make_record.py` writes the record and the ledger row, with PASS or FAIL per gate |

The *record* is the written summary of a run; the *ledger* is the list of all runs. A *hash* is a short
fingerprint of a file: if the file changes, the hash changes. A *container* is a sealed copy of the software that
runs the same way on every machine. Each point warms up for at least 50 steps and 2 s.
Then it times at least 200 steps and 2 s, twice.

## What exists today

Where each build step and the NUS port stand, with their records: [the map of the pages, history](README.md#history).
One training result so far: the STE Guard policy (a pilot, one seed, not gated; [what we found](WHAT_WE_FOUND.md#7-ste-guard-policy-trained-in-test-5-conditions)). Nothing has flown.
