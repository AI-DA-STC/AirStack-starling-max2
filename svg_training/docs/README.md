REFERENCE · the directory of every page in this folder: what each one is for, grouped by what a reader wants to do, with a short history of the work. Start at [../README.md](../README.md).

# Directory of the pages

**STE** is the lab that wrote this repository; **NUS** is the partner university whose code and trained policies the
first part of the work used. Every page opens with one line that says what it is for and where to go next, led by one
of five labels:

| Label | Means | Read it to… |
|---|---|---|
| **Read** | written for any reader; no drone, ROS or Isaac knowledge assumed | understand what was done and what it showed |
| **Reference** | full detail: rules, designs, results of each build step, every script and flag | check a number, a rule or a command |
| **Lab operations** | how the lab runs its own two machines | nothing, outside the lab |
| **Internal** | the lab's working pages: plans, status, notes and the AI-assistant set-up | follow the work day to day; may lag |
| **Archived** | superseded by a later page; kept unchanged for the record | see what a record cites |

## Start here

Four pages tell the whole story in order:

1. [Overview](OVERVIEW.md): the rules of the two games and the seven main learnings, each with its record. One page.
2. [Front page](../README.md): the story from NUS's code to STE's own game, with the numbers, videos and records behind each step.
3. [NUS port report](NUS_PORT_REPORT.md) and [what was found](WHAT_WE_FOUND.md): the first part of the story in full, phase by phase and finding by finding.
4. [STE learning track](../ste_learning/README.md): what STE is building now, the decisions taken and the plan; [where each task stands today](../ste_learning/status/STATUS_LATEST.md).

## Understand what was found

| Page | What it holds |
|---|---|
| [OVERVIEW.md](OVERVIEW.md) | **Read.** The two games side by side and the seven learnings with their records |
| [../README.md](../README.md) | **Read.** The front page: the policies, the port, the six tests, why performance dropped, STE's own game, the five questions put to NUS, run it yourself |
| [WHAT_WE_FOUND.md](WHAT_WE_FOUND.md) | **Read.** Every result of the NUS port (to 20 November 2026), one section per finding, caveats beside the numbers |
| [NUS_PORT_REPORT.md](NUS_PORT_REPORT.md) | **Reference.** The NUS port as a dated log, phase by phase, with NUS's settings and every command |
| [THE_GAME.md](THE_GAME.md) | **Read.** The training pipeline in one picture: seven stages, two drone models, where a strategy plugs in |
| [GLOSSARY.md](GLOSSARY.md) | **Reference.** Every term: NUS's terms and the terms used here, the policies, the six tests, the world around this folder |
| [media/nus/README.md](media/nus/README.md) | **Read.** Videos of the NUS port: all 275 clips, each with a preview that plays in the page |
| [media/README.md](media/README.md) | **Read.** Replay clips and Isaac Lab clips of STE's own scripted games |
| [figures/](figures/) | the figures the pages embed, drawn by the scripts named in each caption |

## Run it, repeat it or extend it

| Page | What it holds |
|---|---|
| [RUN_IT_YOURSELF.md](RUN_IT_YOURSELF.md) | **Read.** Six levels, from watching clips to repeating the six tests from a fresh clone |
| [GETTING_STARTED.md](GETTING_STARTED.md) | **Reference.** The full install with Isaac Lab (container or host), the first tests, the S0 benchmark |
| [TRAIN_A_GUARD.md](TRAIN_A_GUARD.md) | **Read.** The step-by-step recipe behind the STE Guard policy (pilot P1b, run 4) |
| [PLUG_IN_YOUR_CODE.md](PLUG_IN_YOUR_CODE.md) | **Read.** Connecting a strategy or a training method to the game and scoring it |
| [TRAINING.md](TRAINING.md) | **Reference.** Every training script and flag: STE's trainers, the stand-in trainer, the NUS jobs |
| [../docker/README.md](../docker/README.md) | **Reference.** The container image |
| [../nus_provisional/README.md](../nus_provisional/README.md) | **Reference.** The PROVISIONAL bundle: STE's converted NUS-port weights, local settings and recordings, for repeating the numbers |
| [../ste_provisional/README.md](../ste_provisional/README.md) | **Internal.** The trained players of STE's learning track, carried in git so any clone can re-score them |

## Check a rule or a number

| Page | What it holds |
|---|---|
| [../STANDARDS.md](../STANDARDS.md) | **Reference.** The rules every change follows: scope, wording, the policy interface, the game, drone models, gates, records |
| [../records/README.md](../records/README.md), [../records/LEDGER.md](../records/LEDGER.md) | **Reference.** How to read a record; every run, one row each (the T numbers the pages cite) |
| [DESIGN.md](DESIGN.md), [RESEARCH.md](RESEARCH.md) | **Reference.** The design as approved on 14 November 2026 with dated notes, and the state of the art behind it |
| [S0_RESULTS.md](S0_RESULTS.md), [S1_RESULTS.md](S1_RESULTS.md), [S2_RESULTS.md](S2_RESULTS.md), [S2B_RESULTS.md](S2B_RESULTS.md) | **Reference.** STE's build steps before the NUS port: speed of the two drone models; a drone model and the safety filter; the game and the plug-in point; the game on Isaac Lab drones ([DESIGN §8](DESIGN.md#8-build-order) has the order) |
| [pipeline/](pipeline/) | a slide deck of the pipeline (may lag the pages) |

## Follow STE's own training

The learning track has its own folder, [../ste_learning/](../ste_learning/README.md); its README lists every file there.
The pages most often needed:

| Page | What it holds |
|---|---|
| [../ste_learning/README.md](../ste_learning/README.md) | **Read.** What is being built, the decisions taken, the plan, phase L0 done |
| [../ste_learning/status/STATUS_LATEST.md](../ste_learning/status/STATUS_LATEST.md) | **Internal.** Where each task stands today; history in [LOG.md](../ste_learning/status/LOG.md) |
| [../ste_learning/GAME_SPEC.md](../ste_learning/GAME_SPEC.md) | **Internal.** Every value of STE's game with its label and source |
| [../ste_learning/G0_REPORT.md](../ste_learning/G0_REPORT.md), [../ste_learning/G0_DECISION.md](../ste_learning/G0_DECISION.md) | **Internal.** What phase L0 found and what the owner ruled at gate G0 (22 November 2026) |
| [../ste_learning/PLAN.md](../ste_learning/PLAN.md) | **Internal.** The master plan: phases L0 to L9 with their tasks and gates |
| [../ste_learning/DISCUSSION_2026-11-19_20.md](../ste_learning/DISCUSSION_2026-11-19_20.md) | **Internal.** The record of the discussion that set the direction (decisions D1 to D9, questions P1 to P13, the G0 rulings in §14) |
| [../ste_learning/HOW_THE_WORK_RUNS.md](../ste_learning/HOW_THE_WORK_RUNS.md), [../ste_learning/L0_HISTORY.md](../ste_learning/L0_HISTORY.md) | **Internal.** How a task moves through the team and the gates; phase L0 step by step |

## Lab operations and internal pages

| Path | What it holds |
|---|---|
| [WORKSTATION_SETUP.md](WORKSTATION_SETUP.md) | **Lab operations.** The lab's laptop and RTX 5090 workstation: moving long runs between them |
| [../CLAUDE.md](../CLAUDE.md), `../.claude/` | **Internal.** The AI coding assistants' rules, agents and skills ([.claude/README](../.claude/README.md)) |
| [claude/](claude/HANDOFF.md) | **Internal.** The assistants' hand-over notes ([HANDOFF](claude/HANDOFF.md): where the work stands, what waits on whom) and their [agents and skills](claude/AGENTS_AND_SKILLS.md) |
| [linear/](linear/README.md) | **Internal.** Copies of the lab's project-tracker items |
| [plans/](plans/) | **Internal.** The two live build plans: [Phase 5 retraining](plans/2026-11-18-nus-phase5-retraining.md) (tests, configs and records read it) and the [contact-tag side quest](plans/2026-11-17-contact-tag-track.md) |
| [notes/](notes/) | **Internal.** Investigation notes that records cite, kept as written |
| [archive/](archive/README.md) | **Archived.** Superseded build plans and designs, with an index saying what superseded each. The learning track's superseded drafts: [../ste_learning/archive/](../ste_learning/archive/README.md) |

Pages renamed on 19 November 2026 (old names in git history): `NUS_RESULTS.md` is now [WHAT_WE_FOUND.md](WHAT_WE_FOUND.md),
`NUS_PORT.md` is [NUS_PORT_REPORT.md](NUS_PORT_REPORT.md), `TRY_IT.md` is [RUN_IT_YOURSELF.md](RUN_IT_YOURSELF.md),
`PLUG_IN.md` is [PLUG_IN_YOUR_CODE.md](PLUG_IN_YOUR_CODE.md) and `HOW_IT_WORKS.md` is [THE_GAME.md](THE_GAME.md).

## History

**Who.** The lab's owner (the member who owns this repository) set the goals and approved every gate and decision.
Much of the code, the runs and these pages were done by AI coding assistants under that approval; the records and
internal pages call the planning session "the lead" and its reviewer "the gatekeeper". Every number links to the record
of the run that produced it. T numbers are rows of the [run ledger](../records/LEDGER.md).

| Dates (2026) | What happened | Where it stands | Evidence |
|---|---|---|---|
| 14 Nov | the idea, a research review and the design: seven stages, two drone models ("tiers"), build steps S0–S5 | design approved | [DESIGN](DESIGN.md), [RESEARCH](RESEARCH.md) |
| 14–15 Nov | S0: how fast both drone models run | T1 FAIL on one gate (1 of 96 points lost to an Isaac start-up crash); both speed decision rules met | [S0_RESULTS](S0_RESULTS.md) |
| 15 Nov | S1: a drone model and a copy of the safety filter | filter copy T2 FAIL (accepted); simulator fit T3 FAIL; real-log fit exploratory; T4 INFO; no drone-model gate passed yet | [S1_RESULTS](S1_RESULTS.md) |
| 15–16 Nov | S2: the game, varied arena sizes and the plug-in point | closed: faster filter T8 PASS; drone-model check T5 FAIL; scripted reference T9 INFO | [S2_RESULTS](S2_RESULTS.md) |
| 16–17 Nov | S2b: the game on rigid-body Starlings in Isaac Lab | not closed: T10 FAIL (accepted), T11 FAIL, T12 INFO, T13 FAIL (Strike drones pass over or under Guards), stand-in trainer T14 FAIL | [S2B_RESULTS](S2B_RESULTS.md) |
| 17–18 Nov | NUS port, Phases 0–4: NUS's code installed, policies trained by STE with it, the copy of NUS's 2-D game, the conversion, the six tests | T15–T17 PASS; Tests 1–6 T18–T20, T22–T24 INFO; T21 ABORTED | [NUS port report](NUS_PORT_REPORT.md), [what was found](WHAT_WE_FOUND.md) |
| 18–20 Nov | NUS port, Phase 5: STE's PyTorch copy of NUS's training method; pilots of STE's stand-in trainer; a faster safety-filter path | R0 T29, N0 T30, C0 T33 PASS; stage 5.1 FAIL T43 (narrow miss) and the route paused on 20 Nov; pilot P1b run 4 T41 INFO: the STE Guard policy holds S20 in 829 of 1,000 | [NUS port report, Phase 5](NUS_PORT_REPORT.md#12-phase-5-training-in-ste-conditions-paused-20-november-2026), [training recipe](TRAIN_A_GUARD.md) |
| 18–19 Nov | these pages written for any reader: naming pass, Tests 1–6 and the policies defined, a playing preview for every clip | — | this page, [videos of the NUS port](media/nus/README.md) |
| 20–22 Nov | STE's own learning track, phase L0: the game with a tag built and tested on the fast engine and Isaac Lab, hand-written tactics, first trained teams at 1.6 m and 1.15 m | phase L0 done (13.77 of 19 GPU-h); gate G0 ruled 22 Nov: the main game has a 1-for-1 tag, 1.6 m first, 1.15 m later | [overview](OVERVIEW.md), [G0 report](../ste_learning/G0_REPORT.md), [L0 history](../ste_learning/L0_HISTORY.md) |
| 23 Nov | phase L1 (the drone model) in work; overview page added; pages reorganised for any reader, superseded pages archived | L1 and L2 approved together, cap 13 GPU-h | [status](../ste_learning/status/STATUS_LATEST.md), this page |
| not started | S3 two against one, S4 five against three, S5 hand-over to the drones; phases L3 to L9 open at their own gates | — | [DESIGN §8](DESIGN.md#8-build-order), [PLAN](../ste_learning/PLAN.md) |

Nothing in this folder has flown.
