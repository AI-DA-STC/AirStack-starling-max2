REFERENCE · a map of every page in this folder, with one label each, and a short history of the work.

# Map of the pages

**For** anyone looking for a page. Start at the front page, [../README.md](../README.md). Every page carries one of
four labels on its first line:

| Label | Means | You need it to… |
|---|---|---|
| **Read** | written for a newcomer, the NUS team included | understand what we did and try it |
| **Reference** | full detail: rules, designs, results of each build step, every script and flag | check a number or a rule |
| **Lab operations** | how the lab runs its own two machines | nothing, unless you work in the lab |
| **Internal** | the lab's working notes, plans and AI-assistant set-up | nothing; it may be out of date |

## Read

| Page | What it holds |
|---|---|
| [../README.md](../README.md) | the front door: what this is, what we did with NUS's code, questions for NUS, try-it levels |
| [WHAT_WE_FOUND.md](WHAT_WE_FOUND.md) | the NUS port's results, one table per question, caveats beside the numbers |
| [RUN_IT_YOURSELF.md](RUN_IT_YOURSELF.md) | five levels of trying it yourself, from clips to repeating a ladder row |
| [THE_GAME.md](THE_GAME.md) | the pipeline in one picture; the game as an RL environment |
| [PLUG_IN_YOUR_CODE.md](PLUG_IN_YOUR_CODE.md) | plug in your own strategy or training method, and score it |
| [GLOSSARY.md](GLOSSARY.md) | every word: your words and ours, the world around this folder, our terms |
| [media/nus/README.md](media/nus/README.md) | every clip of the NUS port, one line each |
| [media/README.md](media/README.md) | replay clips and Isaac Lab clips of our own scripted games |

## Reference

| Page | What it holds |
|---|---|
| [WHAT_WE_DID_DAY_BY_DAY.md](WHAT_WE_DID_DAY_BY_DAY.md) | the NUS port as a dated log, phase by phase |
| [TRAINING.md](TRAINING.md) | every training script and flag, NUS jobs included |
| [GETTING_STARTED.md](GETTING_STARTED.md) | the full install with Isaac Lab (container or host), the first tests, the S0 benchmark |
| [../STANDARDS.md](../STANDARDS.md) | the rules: scope, wording, interface, game, drone models, gates, records |
| [DESIGN.md](DESIGN.md), [RESEARCH.md](RESEARCH.md) | the design and the state of the art as of 14 November 2026 |
| [S0_RESULTS.md](S0_RESULTS.md), [S1_RESULTS.md](S1_RESULTS.md), [S2_RESULTS.md](S2_RESULTS.md), [S2B_RESULTS.md](S2B_RESULTS.md) | results of our own build steps |
| [../records/README.md](../records/README.md), [../records/LEDGER.md](../records/LEDGER.md) | how to read a record; every run, one row each |
| [figures/](figures/), [pipeline/](pipeline/) | the figures the pages embed; a slide deck of the pipeline (may lag the pages) |
| [../docker/README.md](../docker/README.md) | the container image |
| [../nus_provisional/README.md](../nus_provisional/README.md) | the PROVISIONAL bundle: our converted NUS-port weights, local settings and recordings, for repeating our numbers |

## Lab operations

| Page | What it holds |
|---|---|
| [WORKSTATION_SETUP.md](WORKSTATION_SETUP.md) | the lab's laptop and RTX 5090 workstation: status per machine, the private bundle, moving results, remote access |

## Internal

| Path | What it holds |
|---|---|
| [../CLAUDE.md](../CLAUDE.md), `../.claude/` | the AI coding assistants' rules, agents and skills ([.claude/README](../.claude/README.md)) |
| [claude/](claude/) | the assistants' hand-over notes |
| [linear/](linear/) | copies of the lab's project-tracker items |
| [plans/](plans/), [specs/](specs/) | build plans and designs written for the assistants; history, not instructions |
| [notes/](notes/) | investigation notes that records cite |

Retired: `WHAT_WE_DID.md` (its story is the history below) and `NUS_PHASE4_RESULTS.md` (now [NUS_RESULTS](WHAT_WE_FOUND.md)).
Each keeps a one-line pointer so old links still land.

## History

**Who.** The lab's owner (the member who owns this repository) set the goals and approved every gate and decision.
Much of the code, the runs and these pages were done by AI coding assistants under that approval; the records and
internal pages call the planning session "the lead" and its reviewer "the gatekeeper". Every number links to the record
of the run that produced it.

| Dates (2026) | What happened | Where it stands | Evidence |
|---|---|---|---|
| 14 Nov | the idea, a research review and the design: seven stages, two tiers, build steps S0–S5 | design approved | [DESIGN](DESIGN.md), [RESEARCH](RESEARCH.md) |
| 14–15 Nov | S0: how fast both tiers run | T1 FAIL on one gate (1 of 96 points lost to an Isaac start-up crash); both speed decision rules met | [S0_RESULTS](S0_RESULTS.md) |
| 15 Nov | S1: a drone model and a copy of the safety filter | filter copy T2 FAIL (accepted); simulator fit T3 FAIL; real-log fit exploratory; T4 INFO; no drone-model gate passed yet | [S1_RESULTS](S1_RESULTS.md) |
| 15–16 Nov | S2: the game, varied arena sizes and the plug-in point | closed: faster filter T8 PASS; drone-model check T5 FAIL; scripted reference T9 INFO | [S2_RESULTS](S2_RESULTS.md) |
| 16–17 Nov | S2b: the game on rigid-body Starlings in Isaac Lab | not closed: T10 FAIL (accepted), T11 FAIL, T12 INFO, T13 FAIL (Strike drones pass over or under Guards), stand-in trainer T14 FAIL | [S2B_RESULTS](S2B_RESULTS.md) |
| 17–18 Nov | NUS port, Phases 0–4: NUS's code installed, policies trained with it, the replica, the conversion, the transfer ladder | T15–T17 PASS; ladder rows T18–T20, T22–T24 INFO; T21 ABORTED | [NUS_PORT](WHAT_WE_DID_DAY_BY_DAY.md), [NUS_RESULTS](WHAT_WE_FOUND.md) |
| 18 Nov | NUS port, Phase 5: NUS's training method in PyTorch; pilots of our own learner; a faster safety-filter path | in progress: R0 T29 PASS, N0 T30 PASS, C0 T33 PASS; 5.1 running; pilots T25–T28, T32 INFO or ABORTED; filter path T31 INFO | [NUS_PORT §12](WHAT_WE_DID_DAY_BY_DAY.md#12-phase-5-your-training-method-in-pytorch-in-progress) |
| 18 Nov | these pages rewritten for the NUS team | — | this page |
| not started | S3 two against one, S4 five against three, S5 hand-over to the drones | — | [DESIGN §8](DESIGN.md#8-build-order) |

Nothing of ours has been trained into a strategy yet, and nothing in this folder has flown.
