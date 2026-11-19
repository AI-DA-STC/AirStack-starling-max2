REFERENCE · a map of every page in this folder, with one label each, and a short history of the work.

# Map of the pages

**For** anyone looking for a page. Start at the front page, [../README.md](../README.md). **STE**: the lab that wrote
this repository. Every page carries one of four labels on its first line:

| Label | Means | Needed to… |
|---|---|---|
| **Read** | written for a newcomer, NUS researchers included | understand what was done and run it |
| **Reference** | full detail: rules, designs, results of each build step, every script and flag | check a number or a rule |
| **Lab operations** | how the lab runs its own two machines | nothing, outside the lab |
| **Internal** | the lab's working notes, plans and AI-assistant set-up | nothing; it may be out of date |

## Read

| Page | What it holds |
|---|---|
| [../README.md](../README.md) | the front page: overview and policies, porting NUS's code, the game (NUS 2-D game vs STE drone set-up), testing NUS's policies in the STE drone game (simulation) in PyTorch, why performance drops, training in STE conditions, next steps and the five questions to NUS, run it yourself |
| [WHAT_WE_FOUND.md](WHAT_WE_FOUND.md) | what we found: every result of the NUS port, caveats beside the numbers (was `NUS_RESULTS.md`) |
| [RUN_IT_YOURSELF.md](RUN_IT_YOURSELF.md) | how to run it yourself: six levels, from clips to repeating the six tests (was `TRY_IT.md`) |
| [TRAIN_A_GUARD.md](TRAIN_A_GUARD.md) | training recipe: the step-by-step recipe behind the STE Guard policy (pilot P1b run 4) |
| [THE_GAME.md](THE_GAME.md) | the game, the pipeline in one picture, the game as an RL environment (was `HOW_IT_WORKS.md`) |
| [PLUG_IN_YOUR_CODE.md](PLUG_IN_YOUR_CODE.md) | plug in your code: connect a strategy or a training method, and score it (was `PLUG_IN.md`) |
| [GLOSSARY.md](GLOSSARY.md) | every term: NUS terms and the terms used here, the policies, the six tests, the world around this folder |
| [media/nus/README.md](media/nus/README.md) | videos of the NUS port: all 275 clips, each with a preview that plays in the page, by section |
| [media/README.md](media/README.md) | replay clips and Isaac Lab clips of STE's own scripted games, each with a preview |

## Reference

| Page | What it holds |
|---|---|
| [WHAT_WE_DID_DAY_BY_DAY.md](WHAT_WE_DID_DAY_BY_DAY.md) | what we did, day by day: the NUS port as a dated log, phase by phase (was `NUS_PORT.md`) |
| [TRAINING.md](TRAINING.md) | every training script and flag, NUS jobs included |
| [GETTING_STARTED.md](GETTING_STARTED.md) | the full install with Isaac Lab (container or host), the first tests, the S0 benchmark |
| [../STANDARDS.md](../STANDARDS.md) | the rules: scope, wording, interface, game, drone models, gates, records |
| [DESIGN.md](DESIGN.md), [RESEARCH.md](RESEARCH.md) | the design and the state of the art as of 14 November 2026 |
| [../records/README.md](../records/README.md), [../records/LEDGER.md](../records/LEDGER.md) | how to read a record; every run, one row each |
| [figures/](figures/), [pipeline/](pipeline/) | the figures the pages embed; a slide deck of the pipeline (may lag the pages) |
| [../docker/README.md](../docker/README.md) | the container image |
| [../nus_provisional/README.md](../nus_provisional/README.md) | the PROVISIONAL bundle: STE's converted NUS-port weights, local settings and recordings, for repeating the numbers |

### STE build history

STE's own build steps before the NUS port (names kept; [DESIGN §8](DESIGN.md#8-build-order) has the build order).

| Page | What it holds |
|---|---|
| [S0_RESULTS.md](S0_RESULTS.md) | S0: how fast the two drone models run |
| [S1_RESULTS.md](S1_RESULTS.md) | S1: a drone model and a copy of the safety filter |
| [S2_RESULTS.md](S2_RESULTS.md) | S2: the game, varied arena sizes and the plug-in point |
| [S2B_RESULTS.md](S2B_RESULTS.md) | S2b: the game on rigid-body Starling models in Isaac Lab |

## Lab operations

| Page | What it holds |
|---|---|
| [WORKSTATION_SETUP.md](WORKSTATION_SETUP.md) | the lab's laptop and RTX 5090 workstation: status per machine, the private bundle, moving results, remote access |

## Internal

| Path | What it holds |
|---|---|
| [../CLAUDE.md](../CLAUDE.md), `../.claude/` | the AI coding assistants' rules, agents and skills ([.claude/README](../.claude/README.md)) |
| [claude/](claude/) | the assistants' hand-over notes |
| [../ste_learning/](../ste_learning/README.md) | STE's own learning track: what is being built (with flowcharts), the plan and its first phase, the discussion record, the track's rules and agents. Nothing built or run yet |
| [linear/](linear/) | copies of the lab's project-tracker items |
| [plans/](plans/), [specs/](specs/) | build plans and designs written for the assistants; history, not instructions |
| [notes/](notes/) | investigation notes that records cite |

Retired or renamed: `WHAT_WE_DID.md` (its story is the history below), `NUS_PHASE4_RESULTS.md` (now
[what we found](WHAT_WE_FOUND.md)), and, on 19 November 2026, `NUS_RESULTS.md`, `NUS_PORT.md`, `TRY_IT.md`, `PLUG_IN.md`
and `HOW_IT_WORKS.md` (new names above). Their one-line pointer pages were deleted on 19 November 2026 and every link
now names the new page; the old texts are in git history.

## History

**Who.** The lab's owner (the member who owns this repository) set the goals and approved every gate and decision.
Much of the code, the runs and these pages were done by AI coding assistants under that approval; the records and
internal pages call the planning session "the lead" and its reviewer "the gatekeeper". Every number links to the record
of the run that produced it.

| Dates (2026) | What happened | Where it stands | Evidence |
|---|---|---|---|
| 14 Nov | the idea, a research review and the design: seven stages, two drone models ("tiers"), build steps S0–S5 | design approved | [DESIGN](DESIGN.md), [RESEARCH](RESEARCH.md) |
| 14–15 Nov | S0: how fast both drone models run | T1 FAIL on one gate (1 of 96 points lost to an Isaac start-up crash); both speed decision rules met | [S0_RESULTS](S0_RESULTS.md) |
| 15 Nov | S1: a drone model and a copy of the safety filter | filter copy T2 FAIL (accepted); simulator fit T3 FAIL; real-log fit exploratory; T4 INFO; no drone-model gate passed yet | [S1_RESULTS](S1_RESULTS.md) |
| 15–16 Nov | S2: the game, varied arena sizes and the plug-in point | closed: faster filter T8 PASS; drone-model check T5 FAIL; scripted reference T9 INFO | [S2_RESULTS](S2_RESULTS.md) |
| 16–17 Nov | S2b: the game on rigid-body Starlings in Isaac Lab | not closed: T10 FAIL (accepted), T11 FAIL, T12 INFO, T13 FAIL (Strike drones pass over or under Guards), stand-in trainer T14 FAIL | [S2B_RESULTS](S2B_RESULTS.md) |
| 17–18 Nov | NUS port, Phases 0–4: NUS's code installed, policies trained by STE with it, the Copy of NUS 2-D game, the conversion, the six tests | T15–T17 PASS; Tests 1–6 T18–T20, T22–T24 INFO; T21 ABORTED | [what we did, day by day](WHAT_WE_DID_DAY_BY_DAY.md), [what we found](WHAT_WE_FOUND.md) |
| 18–19 Nov | NUS port, Phase 5: the STE port of NUS's training method (PyTorch); pilots of STE's stand-in trainer; a faster safety-filter path | in progress: R0 T29 PASS, N0 T30 PASS, C0 T33 PASS; stage 5.1 running; pilots T25–T28, T32, T39, T40 INFO or ABORTED; pilot P1b run 4 T41 INFO: the STE Guard policy holds S20 in 829 of 1,000; filter path T31 INFO | [what we did, day by day, Phase 5](WHAT_WE_DID_DAY_BY_DAY.md#12-phase-5-training-in-ste-conditions-in-progress), [training recipe](TRAIN_A_GUARD.md) |
| 18 Nov | these pages rewritten for the NUS team | — | this page |
| 19 Nov | naming pass: pages renamed, Tests 1–6 and the policies named and defined, the training recipe added | — | this page |
| 19 Nov | videos and the game: a playing preview for every clip, front-page section on NUS's 2-D game against the STE drone set-up, the old-name pointer pages deleted | — | [videos of the NUS port](media/nus/README.md), [front page, the game](../README.md#3-the-game-nus-2-d-game-vs-ste-drone-set-up) |
| not started | S3 two against one, S4 five against three, S5 hand-over to the drones | — | [DESIGN §8](DESIGN.md#8-build-order) |

One training result so far, a pilot: the STE Guard policy (one seed, not gated). Nothing in this folder has flown.
