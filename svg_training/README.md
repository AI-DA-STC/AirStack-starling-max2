# svg_training — training pipeline for the Strike vs Guard game

Trains drone-team strategies for the Guard team and the Strike team by playing thousands of games at once on one
GPU, so that a trained policy can fly through AirStack on Starling 2 Max drones. A top-level folder of this
repository, like `localisation/`; it changes nothing in CMU's `AirStack/` tree.

## Status

| Build step | State | Evidence |
|---|---|---|
| S0 (throughput benchmark) | run of record T1: **FAIL** on one [gate](docs/GLOSSARY.md) (1 of 96 points lost to an Isaac start-up crash) | every number verified; both speed [decision rules](docs/GLOSSARY.md) met → [S0 results](docs/S0_RESULTS.md) |
| S1 Drone model and safety filter | approved 15 Nov; building | [S1 plan](docs/plans/2026-11-15-s1-drone-model-and-safety-filter.md) |
| S2–S5 | not started | [DESIGN §8](docs/DESIGN.md#8-build-order) |
| Training | nothing trained yet | — |

Every number in this folder was observed in the training simulator; none is a flight result.

## What this is

A game is written once in PyTorch and played by thousands of copies at once on the GPU. A fast drone model
(tier 1) carries bulk training; a rigid-body drone in Isaac Lab (tier 2) checks it. A trained policy sends the same
velocity commands the flight stack already takes. Read [HOW_IT_WORKS](docs/HOW_IT_WORKS.md) first; diagrams are in
the [deck](docs/pipeline/training-pipeline.pptx).

## I want to…

| I want to… | Go to |
|---|---|
| run the tests | [GETTING_STARTED](docs/GETTING_STARTED.md) A2: `docker/run.sh '$SVG_PY -m pytest -q'` |
| build the container | [GETTING_STARTED](docs/GETTING_STARTED.md) A1 |
| run the benchmark | [GETTING_STARTED](docs/GETTING_STARTED.md) A3–A4 (container) or B (host) |
| read the results | [S0_RESULTS](docs/S0_RESULTS.md); all records in [records/LEDGER.md](records/LEDGER.md) |
| understand the design | [HOW_IT_WORKS](docs/HOW_IT_WORKS.md), then [DESIGN](docs/DESIGN.md) and [RESEARCH](docs/RESEARCH.md) |
| look up a word or a version | [GLOSSARY](docs/GLOSSARY.md) |
| know the rules | [STANDARDS](STANDARDS.md): interface, game, drone models, gates, records |
| plug in a partner's strategy | no code hook yet: the policy file and `interface.toml` arrive with S5 ([STANDARDS §3](STANDARDS.md)) |
| work on it with Claude | [CLAUDE.md](CLAUDE.md), then [docs/claude/HANDOFF.md](docs/claude/HANDOFF.md) |

## Folder layout

| Folder | Holds |
|---|---|
| `source/svg_training/` | the package: benchmark timing, tier 1 environment, worlds and sensing, the Isaac Lab adapter |
| `scripts/` | `run_s0.sh` (the S0 front door), the two benchmarks, `make_record.py` |
| `configs/` | TOML configs; `s0_benchmark.toml` holds S0's gates, decision rules and sweep |
| `tests/` | pytest; most tests need no Isaac |
| `docker/` | the image on NVIDIA's Isaac Lab 2.3.2 and its launchers |
| `records/` | one record per run and the training ledger (in git) |
| `runs/`, `docs/` | raw output of each run (not in git); the documents |

Check [STANDARDS §2](STANDARDS.md) before reusing any text on the programme website.
