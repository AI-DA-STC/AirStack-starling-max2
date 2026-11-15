# Linear update — 2026-11-16, new project "Isaac Lab Pipeline for NUS Strategy Training"

Instructions for the Linear agent, in the **nearlab** workspace (team NEAR Lab). Apply every step below. Delete
nothing. Use the titles, descriptions and comments exactly as written. Change no existing title. Check Linear
before each step: if a project, milestone, issue, relation or comment is already in place, do not repeat it.
Every new issue is unassigned with no due date. Set a milestone target date only where this file gives one.

Evidence is in the repo https://github.com/AI-DA-STC/AirStack-starling-max2, folder `svg_training/`
(`records/LEDGER.md` rows T1–T4, `docs/S0_RESULTS.md`, `docs/S1_RESULTS.md`,
`docs/specs/2026-11-15-s2-game-and-plug-in-design.md`, `docs/plans/2026-11-15-s2-game-and-plug-in.md`).
Write "ledger row T2", never "#T2".

## Part 1 · Create the project

**Name:** Isaac Lab Pipeline for NUS Strategy Training

**Description:**

> A GPU training and test pipeline for the Strike vs Guard game, built in `svg_training/` of the
> AirStack-starling-max2 repo. Thousands of games run at once on one GPU, with the Starling's measured response
> and CMU's collision filter in the loop. Main use: host NUS's strategy, score it under NUS's own game rules and
> again with real Starling limits, and hand it to AirStack. Side use: NEAR Lab trains its own Guard and Strike
> strategies as research. Results are observed in the training simulator; none of them authorises a flight.

## Part 2 · Create seven milestones, in this order

| Milestone | Description | Target date |
|---|---|---|
| **S0 · Measure training speed** | How many games per second the training simulator runs, on the laptop and later on a workstation. | 2026-11-15 |
| **S1 · Drone model and collision filter** | The Starling's response to velocity commands, and a copy of CMU's collision filter, inside the training simulator. | 2026-11-15 |
| **S2 · Game and plug-in point** | The game under NUS's rules, arenas of varied size, a plug-in point any strategy fits, a scoring tool, a faster collision filter, a stand-in trainer that proves the pipe. | none |
| **S3 · NUS strategy scored** | NUS's strategy plugged in and scored two ways: under NUS's rules, and with the Starling's limits and collision filter. | none |
| **S4 · Realistic worlds and physics cross-check** | Obstacles and the construction-site world; the same games checked on full drone physics in Isaac Lab. | none |
| **S5 · Hand-over to AirStack** | Export a strategy with its interface file and fly it in the AirStack simulator. | none |
| **Side quest · NEAR Lab strategies** | Research: NEAR Lab trains its own Guard and Strike strategies on the same pipeline. | none |

## Part 3 · Move one existing issue into the project

**NEAR-955 "Isaac Lab: train in parallel with the Starling model and measure steps per second"** → project
Isaac Lab Pipeline for NUS Strategy Training, milestone **S0 · Measure training speed**, status **Done**, with this
comment:

> 2026-11-16. Done for the laptop (RTX 5070 Ti), ledger row T1, 2026-11-15. Fast simulator, 5 Guard and 3 Strike
> drones with full sensing: about 48,000 games-steps per second. Isaac Lab full drone physics: up to 455,000 drone
> steps per second. These are simulator speeds with random actions, not training speeds. Not done: the training
> workstation (new issue in S0). Results: `svg_training/docs/S0_RESULTS.md`.

## Part 4 · Create issues

Each issue below: project **Isaac Lab Pipeline for NUS Strategy Training**, the milestone in its heading, the
status given. Put the description in the issue body. "Done when" lines are targets, not results.

### S0 · Measure training speed

**"Measure training speed on the training workstation"** — Backlog

> Run the S0 benchmark on the lab's training workstation (RTX 5090, RTX PRO 6000 or RTX 6000 Ada) with the repo's
> docker image. Needs access to the machine. Done when (target): a ledger row with games per second for both
> simulators on that machine.

### S1 · Drone model and collision filter

**"Copy CMU's collision filter into the training simulator"** — Done, with comment:

> 2026-11-15. Built and checked against CMU's filter on 2,000 recorded scenes, ledger row T2: FAIL on 2 of 4
> checks, accepted by the owner on the exact counts (13 and 109 scenes outside the limits; emergency decisions
> agree in 1,998 of 2,000). Results: `svg_training/docs/S1_RESULTS.md`.

**"Starling response model from the 13 Nov flight logs (exploratory)"** — Done, with comment:

> 2026-11-15. Fitted on the 13 Nov gamepad flight of drone_2 (ledger row 36): at up to 0.5 m/s the drone follows
> its command about 0.1–0.15 s late. Exploratory, no gates. The AirStack simulator was also fitted (ledger row T3,
> FAIL): its commander runs on the wall clock while the simulated PX4 runs about 1.9 times faster, so it is not used
> for training.

**"Fit the drone model from a planned-pushes real flight"** — Backlog

> At the next real flight, one drone, gamepad, recording on: full stick for 3–4 s, release, rest 3 s; forward,
> back, left, right; 3 times each; at speed limits 0.25, 0.5, 0.75 and 1.0 m/s; both drones if possible. The flight
> follows PREFLIGHT and RUNBOOK B9. Done when (target): a drone-model fit with gates written before it, a ledger row
> and a named parameter file.

### S2 · Game and plug-in point

**"Game core: thousands of games at once, varied arena and zone sizes"** — In Progress

> One batched game for all games at once. Every game draws its own arena (4–16 m side) and zone size; results are
> reported for lab, middle and large arenas. NUS's rules are the main game; a contact-tag mode stays for the side
> quest. Done when (target): the game-rule tests pass, including hand-worked games at the smallest and largest
> arenas.

**"Check the drone model against the 12 Nov rosbag"** — In Progress

> The 12 Nov two-drone flight (ledger row 35) was recorded at full rate. Compare the exploratory drone model with
> it on the goal legs, without refitting. Done when (target): a ledger row with the error per leg against limits
> written before the run.

**"Faster collision filter, checked against CMU's"** — In Progress

> The filter copy is about 10 times too slow to train with. Try cheaper settings and keep the fastest one that is no
> worse than ledger row T2 on T2's checks. Done when (target): a ledger row; at least 100,000 game-steps per second
> for 5 Guard and 3 Strike drones on the laptop, or a recorded FAIL for the owner to rule on.

**"Scoring tool and scripted opponents"** — In Progress

> A tool that scores any strategy against scripted Guard and Strike opponents, per arena size and team size, under
> NUS's rules and again with the Starling layer. Done when (target): it gives the hand-worked answer on fixed
> scenarios, and a scripted reference run is recorded.

**"Plug-in point for a partner's strategy, with a written guide"** — Backlog

> Connections to common training libraries (skrl, Gymnasium) and a one-page guide for NUS on how to plug a strategy
> or a training method in. Done when (target): the guide's worked example runs.

**"Stand-in trainer: prove the training pipe end to end"** — Backlog

> A simple trainer (not NUS's method) trains a Guard team on this pipeline to show the whole path works. It is a
> pipe test, never the strategy. Done when (target): over 3 seeds the trained Guard team holds the zone clearly
> more often than random actions, by a margin written before the run.

**"S2 results page"** — Backlog

> One page with each S2 result, its figure and what it does not show. Done when (target): the page is in the repo
> and every S2 ledger row links to its record.

### S3 · NUS strategy scored

**"Get NUS's strategy and its rule details"** — Backlog. Relate it to **NEAR-874**.

> Ask NUS for: the strategy's code or checkpoints, which of their projects it is, its inputs and outputs, the
> software it runs on, how many metres one game unit is, and how long one game step is. Done when (target): the
> answers are written down and the code is on the laptop.

**"Score NUS's strategy: NUS's rules against Starling limits"** — Backlog

> Plug NUS's strategy in and score it under NUS's rules as written, then with the Starling's response and CMU's
> collision filter on every pair. The difference shows what flying real Starlings costs that strategy. Done when
> (target): a ledger row with both scores per arena size.

### S4 · Realistic worlds and physics cross-check

**"Games among obstacles and in the construction-site world"** — Backlog

> Random blocks and columns first, then the construction-site world. Done when (target): the scoring tool runs in
> both.

**"Cross-check the fast simulator against full drone physics in Isaac Lab"** — Backlog

> Play the same games on full Starling physics in Isaac Lab and compare. Done when (target): a ledger row with the
> difference against a limit written before the run.

### S5 · Hand-over to AirStack

**"Export a strategy and fly it in the AirStack simulator"** — Backlog. Relate it to **NEAR-875**.

> Export a strategy with its interface file (inputs, outputs, rate, frames, settings), run it as a ROS 2 node
> (needs the owner's approval to add it to AirStack) and fly it in the AirStack simulator. Done when (target): the
> strategy flies a game in the AirStack simulator.

### Side quest · NEAR Lab strategies

**"Train NEAR Lab's own Guard and Strike strategies (research)"** — Backlog

> Research use of the same pipeline: NEAR Lab trains Guard and Strike strategies of its own. Done when (target): a
> trained Guard team beats the scripted Strike behaviours at a rate written before the run.

## Part 5 · Write the sync record

Write a Markdown file named `2026-11-16-linear-synced-isaac-lab-pipeline.md`. State only what Linear now holds:

- the project's name and its seven milestones with target dates and progress;
- NEAR-955's project, milestone, status and comment;
- the NEAR id, title, milestone and status of every new issue, and each relation added;
- anything not applied, and why;
- the totals for the new project and for HTX-R1, HTX-R2 and HTX-R3: total, Backlog, In Progress, Done, Canceled.
