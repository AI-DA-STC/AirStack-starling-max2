# Design — vectorised training pipeline for Strike vs Guard

Status: **approved by the owner on 14 November 2026** (contact tag, safety filter within each team and realistic
environments added the same day). S0 is built and run: [S0_RESULTS.md](S0_RESULTS.md). The short version:
[HOW_IT_WORKS.md](HOW_IT_WORKS.md). Diagrams: [pipeline/training-pipeline.pptx](pipeline/training-pipeline.pptx).
Evidence: [RESEARCH.md](RESEARCH.md). Rules: [../STANDARDS.md](../STANDARDS.md).

## 1. Intent

The programme tests decentralised multi-drone autonomy with one game: the Guard team holds a circular
zone, the Strike team tries to reach it. Strategies are trained in the partners' own simulators and
checked in the AirStack simulator, which flies at most three Starlings and runs close to real time.

ST Engineering wants its own way to train and stress-test strategies **in parallel**: thousands of
games at once on one GPU, on a drone model that behaves like a Starling under PX4, with the same
safety filter the flight stack uses, in environments shaped like real places. A policy trained here
must plug into AirStack unchanged.

Three rules of the game were set by the owner on 14 November 2026: a tag is **physical contact**; the
safety filter acts **within each team only**; games are played in **realistic 3D environments**.

**Why now.** Three gaps in the programme's public simulation page: skills trained from fixed start
positions fail outside them (about 20 % hold rate at 2 against 1); the AirStack simulator stops at
three drones; nobody trains with the Starling's response and the safety filter in the loop.

## 2. Goals, non-goals, anti-goals

| | |
|---|---|
| **Goals** | (1) Train Guard and Strike team strategies at 20 velocity commands a second. (2) Host a partner's strategy behind the same interface for retraining or stress tests. (3) Later, train flight-control policies (thrust and body rates) on a rigid-body Starling. (4) Leave room for camera-based policies. (5) Every result traceable to a run record with gates set beforehand. |
| **Non-goals** | Replacing the AirStack simulator. Replacing the partners' simulators. Flying anything: stages 6 and 7 belong to the flight stack. Vectorising PX4 or ROS 2. |
| **Anti-goals** | A policy that only works in the trainer. A second source of truth for drone parameters. Any edit outside `svg_training/`. A simulator result written up as a flight result. |

## 3. The pipeline: seven stages

| # | Stage | Takes in | Produces | Gate |
|---|---|---|---|---|
| 1 | **Identify** | real flight logs (since 15 November 2026: the commander's rules are copied and PX4's response is fitted; a fit to AirStack simulator logs describes that simulator only, STANDARDS §5 rule 10) | a named parameter set for the tier 1 response model | step-response error against the log within a stated limit |
| 2 | **Train** | game config, model parameter set, opponent pool | checkpoints, curves | training gates in `gates.toml` |
| 3 | **Evaluate** | a checkpoint | hold rates, safety and smoothness numbers | the fixed suite ([STANDARDS §7](../STANDARDS.md)) |
| 4 | **Cross-check** | the same checkpoint | the same numbers on the tier 2 rigid-body Starling | gap between tiers within a stated limit |
| 5 | **Export** | a checkpoint that passed 3 and 4 | policy file + `interface.toml` | file loads and reproduces recorded outputs |
| 6 | Simulated flight | the two files | a run in the AirStack simulator with PX4 software, up to 3 drones | matches training within a stated limit |
| 7 | Real flight | the same two files | Crazyflies first, then Starlings | the flight stack's own rules |

A failed gate sends work back. Training gate fails → revise curriculum, reward or opponents.
Cross-check or simulated flight disagrees with training → the drone model is wrong; refit it (stage 1).

## 4. Two tiers, one game

The game rules, observations, rewards, safety filter and the world's shape are written once, in
PyTorch, and import nothing from Isaac. Two drone models plug in underneath.

| | Tier 1 planned: response model | Tier 1 in S0 today | Tier 2 planned: rigid body | Tier 2 in S0 today |
|---|---|---|---|---|
| What a drone is | a point that follows a velocity command as the flight stack does: shaping, PX4 loops, lag, delay, limits | a point behind a placeholder 0.15 s delay and 0.55 s lag | a rigid body with four rotors in Isaac Lab, flown by a batched port of PX4's cascade | Isaac Lab's ARL Robot 1 airframe; no flight controller; state rewritten every policy step |
| Built from | real flight logs (stage 1; S1 today: the real command chain, PX4's response observed in flight logs, exploratory) | nothing fitted (S0) | CMU system identification + the drone's PX4 parameter file | Isaac Lab's asset |
| Used for | bulk training of uses 1 and 2 | throughput only | the cross-check (stage 4), use 3, later use 4 | throughput only |
| The world is | one distance field on the GPU, shared by every game, plus random blocks and columns per game | open arena, 10 or 50 shapes per game, or a stand-in field the size of the construction-site crop | one static collision mesh in Isaac Lab, shared by every game | a ground plane only |
| A contact tag is | the two centres closer than 0.50 m | the same | a PhysX contact between the two bodies | not modelled |
| Needs Isaac | no | no | yes (Isaac Lab 2.3.2 `Multirotor` + `Thruster`) | yes |
| Speed | high | see [S0_RESULTS](S0_RESULTS.md) | lower | see [S0_RESULTS](S0_RESULTS.md) |

Why two: published work flew velocity-level policies trained on a fitted point-mass model through PX4
(RESEARCH §4–5), and strategy learning gains nothing from rotor physics. But a point-mass model
cannot show what happens near tilt and thrust limits, so a heavier model checks it before the
AirStack simulator does. Tier 2 carries its own PX4-style cascade: Isaac Lab has no PX4-like one (§9).

## 5. Four uses

| # | Use | Tier | Policy sends | When |
|---|---|---|---|---|
| 1 | Team strategy for Guard and Strike | 1, checked on 2 | velocity + yaw rate | now, S0–S5 |
| 2 | Partner strategies (NUS, UPenn) retrained or stress-tested | 1 | the same interface | after S5; needs the written velocity contract |
| 3 | Flight control replacing PX4's loops | 2 | collective thrust + body rates | decided by S2: earlier if velocity commands prove too slow for contact tags (§7); no deployment route today (PX4's on-board neural modules need PX4 1.17+, the Starling runs 1.14) |
| 4 | Camera-based behaviour | 2 + depth by ray-casting | velocity + yaw rate | future, low priority |

The order of the four uses is Claude's reading of the owner's answer of 14 November 2026 (he marked
only cameras as future work); confirm it before planning beyond S5.

## 6. Training recipe for use 1 (starting point; the builder may change it with evidence)

| Topic | Starting choice | Why |
|---|---|---|
| Algorithm | PPO with a shared policy per team and a critic per team that sees the whole game (MAPPO); independent PPO as the baseline | standard for team games; a critic per team avoids cancelling advantages in a two-team game (RESEARCH §7) |
| Library | skrl (installed with Isaac Lab; has IPPO and MAPPO) | already in the environment; no self-play support, so the pool is ours |
| Policy input | padded lists of team-mates and the other team with present flags, through a permutation-invariant encoder, plus a small recurrent layer; a drone hidden behind a structure is masked, and the policy keeps its last seen position and the time since; 32–64 range rays for the surroundings | one network for any team size; copes with a missing drone; in clutter, how the surroundings are encoded decided success in published work (RESEARCH §10) |
| Opponent pool | per game: about 40 % latest version, 35 % earlier versions weighted towards those that still win, 25 % scripted | no single self-play scheme wins on every measure; scripted opponents stop the pool going in circles |
| Starts and worlds | starts random over the whole world from the first run, plus an archive of starts won 50–90 % of the time; each game also draws a placement in the world and its own random blocks and columns | the published fix for start-position overfitting; plain training failed in hard obstacle layouts without such a curriculum (RESEARCH §7, §10) |
| Team sizes and drop-outs | drawn per game; one drone removed mid-game in a fraction of games | generalisation falls off outside the trained range |
| Reward | win or lose per team, a reward at a contact tag, a small shaping term that fades out, a smoothness term added in a second phase, a small penalty proportional to the safety filter's correction | sparse rewards transferred better; smoothness added too early gave policies that do nothing (RESEARCH §4, §6, §7) |
| Safety filter | within each team, in the loop from the first runs; if exploration stalls, switch it on part-way | both schedules are published; measure which works |
| Structures | a drone that touches a structure leaves the game; avoiding structures is learned, because the flight stack has no obstacle avoidance, only a box fence | a distance-field safety filter for structures is published work and a later option (RESEARCH §10) |

If 5 against 3 stalls on a flat policy, move to learned skills with a learned assignment on top.

## 7. Environments and contact tags

**Does a realistic environment affect training? Yes** (RESEARCH §9–10).

| What changes | Consequence for the design |
|---|---|
| Drones lose sight of each other behind structures | masking by line of sight, last-seen memory, a recurrent layer; the critic still sees everything during training |
| Training cost rises sharply: over 2 billion samples in a published game with a few columns | S0 measures throughput with obstacles; the compute budget follows from it |
| One site is not enough: policies overfit a layout | every game draws its own placement and clutter; one world is held out for evaluation |
| Shape matters, appearance does not, for a policy without cameras | the world is stripped to its collision shape; textures and lighting are dropped |
| Sensing, not physics, becomes the bottleneck (10–40 times slower in published simulators) | range rays and line-of-sight tests are part of the S0 benchmark |

**Environment ladder.** Each rung is added only when the one before it trains.

| Rung | World | First used |
|---|---|---|
| E0 | open arena | S2 |
| E1 | random blocks and columns | S3 |
| E2 | the lab's construction-site world (546 × 575 m, 5.8 million triangles; a 40 m crop exists), baked once into a distance field, plus E1 clutter | S4 |
| E3 | more worlds: NVIDIA's warehouse, hospital and office scenes, generated interiors, block-city models; one held out | after S5 |
| E4 | a scanned real place (photogrammetry or LiDAR to mesh) | later, with the site owner's permission |
| E5 | a camera-ready copy (Gaussian splats for appearance, the scan mesh for collision) | with use 4 |

**Contact tags and the control level.** Two published comparisons found that a drone commanded by
velocity touches an agile drone far less often than one commanded by thrust and body rates (17.7 %
against 88.4 %, and 0.51 against 0.95; RESEARCH §10). Neither used PX4 at 20 commands a second, so
the size of the effect here is unknown. S2 measures it. If the tag rate against scripted Strike
drones misses its gate, the strategy stays at velocity level and a final-approach skill at thrust and
body-rate level is trained on tier 2, which brings use 3 forward.

## 8. Build order

Each step ends on a number. S0–S5 deliver use 1.

> **Status note, 15 November 2026.** S1 changed during the work. The AirStack simulator feeds PX4 by a different
> route and clock from the real drone, so the owner ruled that the training model comes from real flight logs and
> simulator fits describe the simulator only (STANDARDS §5 rule 10). The S1 row below is the original plan; what
> was built and measured is in [S1_RESULTS](S1_RESULTS.md), and the changes are listed at the top of the
> [S1 plan](plans/2026-11-15-s1-drone-model-and-safety-filter.md).
>
> **Status note, 16 November 2026.** S2 changed before it started. NUS's strategy became the main use, so S2 builds
> the game, varied arena sizes, a plug-in point and a scoring tool instead of training one against one. The approved
> [S2 design](specs/2026-11-15-s2-game-and-plug-in-design.md) replaces the S2 row below; what was built and measured
> is in [S2_RESULTS](S2_RESULTS.md). The owner then added S2b, the S2 game on Isaac Lab drones
> ([S2b plan](plans/2026-11-16-s2b-isaac-lab-environment.md)), which pulls part of S4's cross-check forward and
> runs the stand-in trainer moved out of S2.

| Step | Builds | Ends when |
|---|---|---|
| **S0 Measure** | the project skeleton; minimal tier 1 and tier 2 environments with random actions; tier 1 with 0, 10 and 50 obstacles, range rays, line of sight and a stand-in distance field | steps per second against number of games recorded for both tiers on the laptop (done: T1, [S0_RESULTS](S0_RESULTS.md)) and a training workstation (to do), with a compute budget for S2–S4 |
| **S1 Drone model** | velocity-step logs at the plug-in point (none exist yet; recorded by running `tools/sim.sh`, approved by the owner on 14 November 2026); stage 1 fitting script; tier 1 model; the safety filter port | fitted model reproduces a velocity step from the AirStack simulator within a limit set beforehand; filter port matches `cbf_filter.py` on recorded inputs |
| **S2 One against one** | open arena (E0); game rules with contact tags, scripted opponents, evaluation suite, records | unit tests pass without Isaac; a trained Guard policy tags the scripted Strike behaviours at a rate set beforehand; that rate decides the control level (§7) |
| **S3 Two against one** | random blocks and columns (E1); line-of-sight masking; opponent pool, start archive | hold rate from random starts and layouts against the scripted Strike behaviours at a rate set beforehand, with the interval reported; the 20 % figure is a reference only, its game conditions differ |
| **S4 Five against three** | the construction-site world (E2): bake its distance field, random clutter; team-size and drop-out randomisation; tier 2 cross-check in the same world | suite passes on tier 1, on held-out layouts too; gap to tier 2 within its limit |
| **S5 Hand-over** | export and `interface.toml` | the owner approves a ROS 2 policy node in the AirStack tree (outside this folder); the policy flies in the AirStack simulator |

## 9. Approaches considered

| | A: full physics only | B: response model only | **C: two tiers, one game (chosen)** |
|---|---|---|---|
| Idea | every drone a rigid body with rotors in Isaac Lab | point-mass model in plain PyTorch, no Isaac | game written once; B for bulk training, A for the cross-check |
| For | closest to the airframe; cameras available | fastest, simplest; this kind of model has flown through PX4 | speed of B with the check of A; game code testable without Isaac; tier 2 also serves uses 3 and 4 |
| Against | slowest; Isaac Lab has no PX4-like velocity controller (none in 2.3.2, proportional-only in 3.0); rotor physics adds nothing to strategy | no check near limits; no path to uses 3 and 4 | two drone models to keep in step |

The owner chose C on 14 November 2026, with Isaac Lab 2.3.2 now and 3.0 later, and the folder name
`svg_training`.

## 10. Constraints

- Isaac Lab 2.3.2 now, 3.0 later on the training workstations, behind the adapter module
  ([versions](GLOSSARY.md#versions)); no GPU driver change on the flight laptop.
- Training moves to an RTX 5090, RTX PRO 6000 or RTX 6000 Ada workstation (owner, 14 November 2026);
  the laptop is for development and smoke tests.
- 12 GB of GPU memory on the laptop, below Isaac Sim's stated 16 GB minimum: enough for headless
  physics and ray-casting, not for camera training. The GPU is shared with the AirStack simulator.
- The construction-site world has no licence file: it is read, never changed, and nothing baked from it enters git.
- Packaging (owner, 14 November 2026): a top-level component of the repository with its own `docker/`
  image carrying Isaac Lab; CMU's `AirStack/` tree is not touched.
- The repository's hook, its docs checker and other Claude sessions ([STANDARDS §9–10](../STANDARDS.md)).

## 11. Risks

| Risk | What limits it |
|---|---|
| A tag is physical contact. Velocity commands at 20 Hz with 0.15 s delay and about half a second of lag may be too slow to touch a drone that is trying not to be touched | S2 measures the tag rate; the fallback is a final-approach skill at thrust and body-rate level (§7) |
| Tier 1 without the fitted delay and lag makes contact look easier than it is | the response model comes first (S1), before any game is trained |
| With no filter between the teams, two drones can meet at a high closing speed | closing speed at contact is logged and gated in evaluation; published real flights use a virtual contact distance instead of impact |
| A policy that tags by contact cannot fly on today's flight stack, whose safety filter keeps every pair of drones apart | training is unaffected; flying it needs a pair mask in CMU's filter and a flight safety case, both outside this folder |
| Contact is an event, not physics, in tier 1: what happens to the two drones afterwards is not modelled | the drones leave the game at contact; tier 2 shows the physical contact |
| The response model is fitted to one route; the real drone and the AirStack simulator use different command routes (NEAR-866) | train on the real route (STANDARDS §5 rule 10, 15 November 2026); a simulator fit is kept only to describe the simulator; cross-check on tier 2 |
| Self-play goes in circles or overfits to its own pool | scripted opponents, cross-play table, a fixed-budget best-response test |
| The drone runs PX4 1.14 and the AirStack simulator PX4 1.16.1; a model fitted to one may not match the other | copy the drone's control law; compare the two versions' position controller before S1; fit both routes |
| Overlap with UPenn's Isaac Lab environment and NUS's simulators | this pipeline's niche is Starling response + safety filter + AirStack hand-over; tell the partners early |
| The lab arena (3 × 3 m) is small against a 1.10 m keep-out: few drones fit | arena size is a parameter; decide the scales with the owner |
| Thousands of games placed in one copy of a world may overflow the physics engine's pair capacity in tier 2 (NVIDIA's own warning) | several copies of the world, each hosting a share of the games; measured in S4 |
| Policies learn one site by heart | random placement and clutter per game; a held-out world |
| The policy needs to sense its surroundings, and the real drone's sensor for that is not chosen | a known map is the accepted first step in published work; the sensor question is open (HANDOFF) |

## 12. Left to the builder

Network sizes and hyperparameters; the exact form of the tier 1 model (start with PX4's velocity
controller and a fitted lag, add terms only when the fit demands them); file formats inside `runs/`;
which scripted opponents come first; whether skrl's trainer is kept or replaced for the opponent pool;
the distance field's resolution and the number of range rays, from the S0 numbers.
