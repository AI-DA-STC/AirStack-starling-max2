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
| S1 (drone model and safety filter) | built, run and closed 15 Nov: filter copy T2 **FAIL** (accepted by the owner on the exact counts); simulator fit T3 **FAIL**; real-log fit exploratory; tier 1 with the real chain T4 information only; no S1 gate on the drone model passed yet | [S1 results](docs/S1_RESULTS.md); [S1 plan](docs/plans/2026-11-15-s1-drone-model-and-safety-filter.md) |
| S2 (the game and the plug-in point) | built, reviewed and CLOSED 16 Nov (final review on the whole stage, one fix wave). Faster filter T8 **PASS**; drone-model check T5 **FAIL**; scripted reference T9 information only; stand-in trainer moved to S2b | [S2 results](docs/S2_RESULTS.md); [S2 plan](docs/plans/2026-11-15-s2-game-and-plug-in.md) |
| S2b (the game on Isaac Lab drones) | built and run through Task 8, 16–17 Nov; not closed. Two physics worlds agree T10 **FAIL** (accepted by the owner); step tests T11 **FAIL**; speed T12 information only; scripted games on both backends T13 **FAIL** (Strike drones pass over or under Guards on the physics drone; the owner kept this in the game); stand-in trainer on Isaac Lab T14 **FAIL** (seeds 1–2 fail every gate cell; seed 3 not run, cannot change it); registered Isaac Lab task not yet built | [S2b results](docs/S2B_RESULTS.md); [S2b plan](docs/plans/2026-11-16-s2b-isaac-lab-environment.md) |
| S3–S5 | not started | [DESIGN §8](docs/DESIGN.md#8-build-order) |
| Training | no strategy trained yet; the stand-in trainer (a pipe test) trained 2 seeds on Isaac Lab: the pipe works, the Guards learned almost nothing (T14) | [S2b results §5](docs/S2B_RESULTS.md#5-the-stand-in-trainer) |

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
| set up a training workstation (home RTX 5090 PC) | [WORKSTATION_SETUP](docs/WORKSTATION_SETUP.md) |
| train a policy, without a window (headless) or with the Isaac Sim window | [TRAINING](docs/TRAINING.md) (planned workflow: nothing trains before S2) |
| read the results | [S0_RESULTS](docs/S0_RESULTS.md), [S1_RESULTS](docs/S1_RESULTS.md), [S2_RESULTS](docs/S2_RESULTS.md), [S2B_RESULTS](docs/S2B_RESULTS.md); all records in [records/LEDGER.md](records/LEDGER.md) |
| understand the design | [HOW_IT_WORKS](docs/HOW_IT_WORKS.md), then [DESIGN](docs/DESIGN.md) and [RESEARCH](docs/RESEARCH.md) |
| look up a word or a version | [GLOSSARY](docs/GLOSSARY.md) |
| know the rules | [STANDARDS](STANDARDS.md): interface, game, drone models, gates, records |
| plug in a partner's strategy or training method, and score it | [PLUG_IN](docs/PLUG_IN.md). Export to the drones (policy file and `interface.toml`) arrives with S5 ([STANDARDS §3](STANDARDS.md)) |
| watch a game | top-down replay clips in [docs/media](docs/media/README.md) |
| work on it with Claude | [CLAUDE.md](CLAUDE.md), then [docs/claude/HANDOFF.md](docs/claude/HANDOFF.md) |

## Folder layout

The table lists what each folder holds.

| Folder | What it holds |
|---|---|
| `source/svg_training/` | the package: benchmark timing, tier 1 environment, worlds and sensing, the Isaac Lab adapter; `core/` the game, the safety filter copy, the Starling layer, strategies and scoring; `envs/` also the skrl and Gymnasium adapters; `models/` the drone models (commander copy, PX4 model, placeholder, simulator-route fit) |
| `scripts/` | `run_s0.sh` (the one command that runs S0), the two benchmarks, `make_record.py`; S1's fits (`fit_real_px4.py`, `fit_response.py`), filter check (`filter_parity.py`), figures and the simulator step session (`record_steps.sh`, `virtual_stick.py`); S2's scoring tool (`score.py`), filter speed (`filter_speed.py`), bag check (`bag_check.py`) and replay clips (`make_replay.py`) |
| `configs/` | TOML configs; `s0_benchmark.toml` holds S0's gates, decision rules and sweep; `s1.toml` S1's; `s2_game.toml` the game's neutral values and `s2.toml` S2's gates; `local/` (git-ignored) a partner's own values |
| `params/` | drone-model parameter sets: `real_exploratory_v0.toml` (used by tier 1), `airstack_sim_v0.toml` (simulator only) |
| `tests/` | pytest; most tests need no Isaac |
| `docker/` | the container image, built on NVIDIA's Isaac Lab 2.3.2, and its launchers |
| `data/` | git-ignored copies of the real flight logs the pipeline reads (from the private bundle; see [WORKSTATION_SETUP §1a](docs/WORKSTATION_SETUP.md#1a-files-that-are-not-in-git)) |
| `records/` | one record per run (its written summary) and the training ledger (the list of all runs), in git |
| `runs/`, `docs/` | raw output of each run (not in git); the documents (`docs/notes/` holds investigation notes the results cite) |

Check [STANDARDS §2](STANDARDS.md) before reusing any text on the programme website.
