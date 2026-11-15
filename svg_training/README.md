# svg_training: training pipeline for the Strike vs Guard game

This folder trains strategies for drone teams in the Strike vs Guard game. It plays thousands of games at once on
one graphics card (GPU). The aim is a trained strategy (a *policy*) that flies through AirStack on Starling 2 Max
drones. The folder sits at the top of this repository, like `localisation/`. It changes nothing in CMU's
`AirStack/` tree.

## Status

The table shows each build step and where its evidence is. A *gate* is a pass/fail check set before a run; the
official run whose numbers we keep is the *run of record* (both in the [glossary](docs/GLOSSARY.md)).

| Build step | Where it stands | Evidence |
|---|---|---|
| S0 (throughput benchmark) | run of record T1: **FAIL** on one [gate](docs/GLOSSARY.md) (1 of 96 points lost to an Isaac start-up crash) | every number verified; both speed [decision rules](docs/GLOSSARY.md) met → [S0 results](docs/S0_RESULTS.md) |
| S1 (drone model and safety filter) | built and run 15 Nov: filter copy T2 **FAIL** (accepted by the owner; re-confirmation on the exact counts asked); simulator fit T3 **FAIL**; real-log fit exploratory; tier 1 with the real chain T4 information only; no S1 gate on the drone model passed yet | [S1 results](docs/S1_RESULTS.md); [S1 plan](docs/plans/2026-11-15-s1-drone-model-and-safety-filter.md) |
| S2–S5 | not started | [DESIGN §8](docs/DESIGN.md#8-build-order) |
| Training | nothing trained yet | none |

Every number in this folder was observed in the training simulator. None is a flight result.
The story so far, in plain words and in order: [WHAT_WE_DID](docs/WHAT_WE_DID.md).

## What this is

A game is written once in PyTorch, and thousands of copies of it play at once on the GPU. Two simulators run it.
A fast, simple drone model (*tier 1*) does most of the training. A full physics drone in Isaac Lab (*tier 2*)
checks it. A trained policy sends the same speed commands the flight software already takes. Read
[HOW_IT_WORKS](docs/HOW_IT_WORKS.md) first. The diagrams are in the [deck](docs/pipeline/training-pipeline.pptx).

## I want to…

Each row points to the page that answers the question.

| I want to… | Go to |
|---|---|
| know what has been done so far, in plain words | [WHAT_WE_DID](docs/WHAT_WE_DID.md) |
| run the tests | [GETTING_STARTED](docs/GETTING_STARTED.md) A2: `docker/run.sh '$SVG_PY -m pytest -q'` |
| build the container | [GETTING_STARTED](docs/GETTING_STARTED.md) A1 |
| run the benchmark | [GETTING_STARTED](docs/GETTING_STARTED.md) A3–A4 (container) or B (host) |
| train a policy, without a window (headless) or with the Isaac Sim window | [TRAINING](docs/TRAINING.md) (planned workflow: nothing trains before S2) |
| read the results | [S0_RESULTS](docs/S0_RESULTS.md), [S1_RESULTS](docs/S1_RESULTS.md); all records in [records/LEDGER.md](records/LEDGER.md) |
| understand the design | [HOW_IT_WORKS](docs/HOW_IT_WORKS.md), then [DESIGN](docs/DESIGN.md) and [RESEARCH](docs/RESEARCH.md) |
| look up a word or a version | [GLOSSARY](docs/GLOSSARY.md) |
| know the rules | [STANDARDS](STANDARDS.md): interface, game, drone models, gates, records |
| plug in a partner's strategy | there is no code hook yet. The policy file and `interface.toml` arrive with S5 ([STANDARDS §3](STANDARDS.md)) |
| work on it with Claude | [CLAUDE.md](CLAUDE.md), then [docs/claude/HANDOFF.md](docs/claude/HANDOFF.md) |

## Folder layout

The table lists what each folder holds.

| Folder | What it holds |
|---|---|
| `source/svg_training/` | the package: benchmark timing, tier 1 environment, worlds and sensing, the Isaac Lab adapter |
| `scripts/` | `run_s0.sh` (the one command that runs S0), the two benchmarks, `make_record.py` |
| `configs/` | TOML configs; `s0_benchmark.toml` holds S0's gates, decision rules and sweep |
| `tests/` | pytest; most tests need no Isaac |
| `docker/` | the container image, built on NVIDIA's Isaac Lab 2.3.2, and its launchers |
| `records/` | one record per run (its written summary) and the training ledger (the list of all runs), in git |
| `runs/`, `docs/` | raw output of each run (not in git); the documents |

Check [STANDARDS §2](STANDARDS.md) before reusing any text on the programme website.
