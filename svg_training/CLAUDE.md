# CLAUDE.md — svg_training (vectorised training pipeline)

Training pipeline for the **Strike vs Guard** game: thousands of games run at once on one GPU, so
drone teams can learn strategies that then fly through AirStack on Starling 2 Max drones.
It is a sibling of `AirStack/`, `tools/` and `localisation/`, and it edits none of them.

**Status (2026-11-16): S0 and S1 closed; S2 closed (final review done, one fix wave); nothing trained.** S0: run of
record T1 = FAIL on one gate (one tier 2 point lost to an Isaac Sim start-up crash), both decision rules met
([docs/S0_RESULTS.md](docs/S0_RESULTS.md)). S1: filter copy T2 = FAIL (accepted by the owner), simulator fit T3 =
FAIL, tier 1 carries the real-drone command chain with an exploratory PX4 model ([docs/S1_RESULTS.md](docs/S1_RESULTS.md)).
S2: the game (partner rules preset, neutral committed values, varied arenas, Starling layer), scripted opponents,
scoring tool, skrl and Gymnasium adapters and the partner guide; faster filter T8 = PASS, drone-model check T5 = FAIL,
scripted reference T9 = INFO; the stand-in trainer moved to S2b ([docs/S2_RESULTS.md](docs/S2_RESULTS.md),
[docs/PLUG_IN.md](docs/PLUG_IN.md)).

**S2b (2026-11-17): built and run through Task 8, not closed; no strategy trained.** The S2 game on rigid-body
Starlings in Isaac Lab (the physics drone: PX4 1.14 cascade with the drone's gains, SIM-ONLY yaw-rate gains by the
owner's ruling). Two physics worlds agree T10 = FAIL (accepted by the owner), step tests T11 = FAIL, speed T12 = INFO,
scripted games on both backends T13 = FAIL: on the physics drone Strike drones pass over or under Guards, and the
owner kept this in the game (option (a), 17 November). The stand-in trainer is running on Isaac Lab; the registered
Isaac Lab task (Task 8b) is not yet built ([docs/S2B_RESULTS.md](docs/S2B_RESULTS.md)).

## Read first

| File | Use it for |
|---|---|
| [docs/claude/HANDOFF.md](docs/claude/HANDOFF.md) | where the work stands, what was decided, what is waiting on whom |
| [STANDARDS.md](STANDARDS.md) | **the rules**: scope, wording, policy interface, game specification, drone models, gates, records, code, git |
| [docs/DESIGN.md](docs/DESIGN.md) | the design: seven stages, two tiers, four uses, environments and contact tags, build order S0–S5, approaches considered |
| [docs/RESEARCH.md](docs/RESEARCH.md) | state of the art as of 14 November 2026, with sources; the evidence behind the design |
| [docs/S0_RESULTS.md](docs/S0_RESULTS.md), [docs/S1_RESULTS.md](docs/S1_RESULTS.md), [docs/S2_RESULTS.md](docs/S2_RESULTS.md), [docs/S2B_RESULTS.md](docs/S2B_RESULTS.md), [docs/GLOSSARY.md](docs/GLOSSARY.md) | S0's, S1's, S2's and S2b's numbers and limits; terms and the one Versions table |
| [docs/PLUG_IN.md](docs/PLUG_IN.md) | how a partner plugs a strategy or a training method into the game and scores it |
| [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) | the human path from a clone to tests and a benchmark run; `run_s0.sh` exit codes |
| [docs/linear/README.md](docs/linear/README.md) | this project in Linear (P-NEAR-31): how an update goes (`updates/` → owner uploads → `synced/` → `snapshots/`), the latest snapshot, the owner's Linear rules |
| [docs/pipeline/training-pipeline.pptx](docs/pipeline/training-pipeline.pptx) | the diagrams (editable flowchart shapes); rebuilt by `docs/pipeline/build_deck.py` |
| [../CLAUDE.md](../CLAUDE.md) | the repository's own rules (iron rules, two clones, more than one Claude session) — they still apply here |

## Hard rules (short version of STANDARDS.md)

1. **Write only inside `svg_training/`.** The rest of this repository, `~/IsaacLab` and
   `~/Documents/GitHub/Strike-Versus-Guard` are read-only. If the work needs a change outside this
   folder, stop and ask the owner; other Claude sessions work in those places. One approved
   exception: running (not editing) `tools/sim.sh` to record velocity-step logs (STANDARDS §1).
2. **The folder is part of the repository since 14 November 2026** (owner's decision: the pipeline is
   added to AirStack). Commit finished, tested work in the live clone with explicit paths, as the root
   `CLAUDE.md` says; never push (the owner pushes), never `git add -A`, never `--no-verify`. A change
   under `docker/` or any YAML needs a line in `docs/record/CHANGES.md` (root `docs/CODING_STANDARD.md`).
3. **Numbers flow from the drone to the trainer, never back.** Nothing here changes a drone
   parameter, an AirStack config or the sim airframe (repository iron rule 9).
4. **A training result is not a flight result.** Write "observed in the training simulator", never
   "validated". Nothing produced here authorises a real flight; real flights follow
   `docs/PREFLIGHT.md` and `docs/RUNBOOK.md`.
5. **Gates are written before a run and never moved** (STANDARDS §7).
6. **The GPU is shared with the AirStack simulator.** Check `nvidia-smi` first; do not start a
   training run while a simulator or flight session is up. Always run headless.
7. **Programme wording**: Strike team, Guard team, tag, reach the zone, drone team (STANDARDS §2).
8. **No per-game Python loops** in anything that runs during training (STANDARDS §6).

## How a session runs

Start Claude **from this folder** (`cd ~/AirStack-starling-max2/svg_training && claude`) so the
agents and skills below load. Then:

| Say or need | Skill |
|---|---|
| start of every session | `train-start` |
| change code, a config or a document in this folder | `train-change` |
| launch a benchmark or a training run | `train-run` |
| score a checkpoint against the gates | `train-evaluate` |
| something is wrong (NaN, reward collapse, slow, unstable) | `train-debug` |
| hand a policy to AirStack | `train-export` |

Agents (in `.claude/agents/`, described in [docs/claude/AGENTS_AND_SKILLS.md](docs/claude/AGENTS_AND_SKILLS.md)):
`train-isaaclab-engineer`, `train-drone-dynamics`, `train-marl-researcher`,
`train-flight-interface-reviewer`, `train-gatekeeper` (advisers, read-only) and
`train-implementer` (the only one that writes code).

## Environment (verified 2026-11-14 on this laptop)

| Item | Value |
|---|---|
| This laptop | RTX 5070 Ti Laptop GPU, 12 GB, driver 580.178; 24 threads; 30 GB RAM — development and smoke tests |
| Training machines | RTX 5090, RTX PRO 6000 or RTX 6000 Ada workstations, later (none inspected yet) |
| Isaac Lab, in the container (the repository's way) | image `svg-training:isaaclab-2.3.2`, built by `docker/build.sh` on NVIDIA's `nvcr.io/nvidia/isaac-lab:2.3.2`; see [docker/README.md](docker/README.md) |
| Isaac Lab, on this laptop's host | `~/IsaacLab`, version 2.3.2 plus 25 commits (`f73c331738`; none touch code tier 2 uses), clean; **do not edit it** |
| Python environment | conda `env_isaaclab`: Python 3.11, torch 2.7.0+cu128, Isaac Sim 5.1.0 (pip), skrl 2.1.0, rsl_rl 5.0.1 |
| AirStack simulator | Isaac Sim 5.1.0 + Pegasus + PX4 v1.16.1 in docker (`tools/sim.sh`); real drones run PX4 1.14 |
| Known trap | starting Isaac Sim with a window over remote desktop has crashed this laptop's WiFi firmware: run headless, or be on Ethernet or at the machine |

## Git facts that bite

- `.git/info/exclude` ignores `.claude/` at any depth. This folder's agents and skills are committed
  all the same (owner, 14 November 2026): a new or renamed file under `svg_training/.claude/` needs
  `git add -f <that path>`. Do not change the exclude rule.
- The repository hook treats any committed `*.yaml`/`*.yml`, `Dockerfile`, `docker-compose*` or
  `launch/` path as a behaviour change that needs a `docs/record/CHANGES.md` entry. Configs here are
  Python or TOML; `docker/` is the one place with such a file.
- Do not link to this folder from `docs/`, `README.md` or the root `CLAUDE.md` without the owner's
  say-so: that brings it under the docs checker. Approved once (owner, 15 November 2026): one row in the root
  `README.md` "I want to…" table points at `svg_training/README.md` and `docs/S1_RESULTS.md`; the checker
  still does not scan inside this folder (links resolved, no new warnings). Also approved (owner, 16 November 2026): one row in the root `CLAUDE.md` doc table points at this folder's CLAUDE.md.
