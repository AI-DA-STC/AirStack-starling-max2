INTERNAL · the lab's rules for its AI coding assistants. Not on the lab team (for example NUS)? You never need this file: start at [README.md](README.md). If you use your own assistant here, these rules (HANDOFF, Linear, the owner's approvals) are the lab's, not yours.

# CLAUDE.md — svg_training (vectorised training pipeline)

Training pipeline for the **Strike vs Guard** game: thousands of games run at once on one GPU, so
drone teams can learn strategies that then fly through AirStack on Starling 2 Max drones.
It is a sibling of `AirStack/`, `tools/` and `localisation/`, and it edits none of them.

**Status (2026-11-20).** S0, S1 and S2 closed; S2b built through Task 8, not closed; NUS port Phases 1–4 done,
Phase 5 in progress (R0 T29, N0 T30 and C0 T33 PASS; 5.1 FAIL T43: route (b) stops; STE Guard policy T41 829/1000); **STE's own learning track: phase L0 approved by the owner (20 Nov, cap 19 GPU-h), in work; status in `ste_learning/status/STATUS_LATEST.md` ([ste_learning/](ste_learning/README.md))**; nothing of ours trained into a strategy; nothing flown.

| Work | Where it stands | Read |
|---|---|---|
| S0 throughput | T1 = FAIL on one gate (an Isaac start-up crash), both decision rules met | [docs/S0_RESULTS.md](docs/S0_RESULTS.md) |
| S1 drone model, filter | filter copy T2 FAIL (accepted), simulator fit T3 FAIL, tier 1 carries the real command chain with an exploratory PX4 model | [docs/S1_RESULTS.md](docs/S1_RESULTS.md) |
| S2 the game, plug-in point | closed 16 Nov: faster filter T8 PASS, drone-model check T5 FAIL, scripted reference T9 INFO | [docs/S2_RESULTS.md](docs/S2_RESULTS.md), [docs/PLUG_IN_YOUR_CODE.md](docs/PLUG_IN_YOUR_CODE.md) |
| S2b game on Isaac Lab drones | T10 FAIL (accepted), T11 FAIL, T12 INFO, T13 FAIL (Strike drones pass over or under Guards; owner kept it, option (a)), stand-in T14 FAIL (seed 3 queued for the 5090); Task 8b not built | [docs/S2B_RESULTS.md](docs/S2B_RESULTS.md) |
| NUS port (17–18 Nov, home RTX 5090) | Phase 1 NUS's code installed (65 of NUS's 66 tests pass; the one failure is a test NUS confirmed is out of date); Phase 2a reference policies trained with NUS's code (self-play 3 seeds × 8 generations, seed 2 to 20); Phase 2 replica T15 PASS; Phase 3 conversion T16 PASS, T17 PASS; Phase 4 ladder rows 1–3 T18–T20 INFO, row 4 first attempt T21 ABORTED, rows 4, 5a, 5, 6 T22–T24 INFO (the filter and 3-D break NUS's push-blocking; Isaac Lab agrees with tier 1); Phase 5 planned by the lead (owner delegated): route (b) plus own-training pilots, not started; Phase 6 public docs passes 1 and 2 done (every clip published) | [docs/WHAT_WE_DID_DAY_BY_DAY.md](docs/WHAT_WE_DID_DAY_BY_DAY.md) |
| Contact-tag track | DRAFT plan, nothing started; may be described publicly (owner, 18 Nov) | [docs/plans/2026-11-17-contact-tag-track.md](docs/plans/2026-11-17-contact-tag-track.md) |

## Read first

| File | Use it for |
|---|---|
| [README.md](README.md) | the front page, written for NUS: porting NUS's code, the six tests on STE drones, why performance drops, training in STE conditions, questions for NUS, run it yourself |
| [docs/README.md](docs/README.md) | map of every page with its label (Read, Reference, Lab operations, Internal) and the history |
| [docs/WHAT_WE_FOUND.md](docs/WHAT_WE_FOUND.md), [docs/RUN_IT_YOURSELF.md](docs/RUN_IT_YOURSELF.md), [docs/TRAIN_A_GUARD.md](docs/TRAIN_A_GUARD.md) | the NUS port's results; the verified run-it-yourself commands; the recipe behind the STE Guard policy (T41) |
| [docs/claude/HANDOFF.md](docs/claude/HANDOFF.md) | where the work stands, what was decided, what is waiting on whom |
| [ste_learning/](ste_learning/README.md) | **STE's own learning track** (owner, 20 Nov 2026): README with flowcharts, [PLAN](ste_learning/PLAN.md) (the working plan: phase L0 approved 20 Nov, gate G0, L1–L9 intended), [DISCUSSION](ste_learning/DISCUSSION_2026-11-19_20.md) (why; D1–D9, P1–P13), the track's STANDARDS, ARCHITECTURE, CODING_PRACTICES, AUTOMATION, VALIDATION_QC, and its agents (`ste-*`). Read it before any work on the track; consult the advisor at every key point (owner) |
| [STANDARDS.md](STANDARDS.md) | **the rules**: scope, wording, policy interface, game specification, drone models, gates, records, code, git |
| [docs/DESIGN.md](docs/DESIGN.md) | the design: seven stages, two tiers, four uses, environments and contact tags, build order S0–S5, approaches considered |
| [docs/RESEARCH.md](docs/RESEARCH.md) | state of the art as of 14 November 2026, with sources; the evidence behind the design |
| [docs/S0_RESULTS.md](docs/S0_RESULTS.md), [docs/S1_RESULTS.md](docs/S1_RESULTS.md), [docs/S2_RESULTS.md](docs/S2_RESULTS.md), [docs/S2B_RESULTS.md](docs/S2B_RESULTS.md), [docs/GLOSSARY.md](docs/GLOSSARY.md) | S0's, S1's, S2's and S2b's numbers and limits; terms and the one Versions table |
| [docs/PLUG_IN_YOUR_CODE.md](docs/PLUG_IN_YOUR_CODE.md) | how a partner plugs a strategy or a training method into the game and scores it |
| [docs/WHAT_WE_DID_DAY_BY_DAY.md](docs/WHAT_WE_DID_DAY_BY_DAY.md) | the NUS port: NUS's three branches, phases 0–6, NUS's settings, results and videos; commands in [docs/TRAINING.md](docs/TRAINING.md#nus-jobs) |
| [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) | setting up any machine (laptop or 5090 workstation, side by side), then tests and a benchmark run; `run_s0.sh` exit codes |
| [docs/linear/README.md](docs/linear/README.md) | this project in Linear (P-NEAR-31): how an update goes (`updates/` → owner uploads → `synced/` → `snapshots/`), the latest snapshot, the owner's Linear rules |
| [docs/pipeline/training-pipeline.pptx](docs/pipeline/training-pipeline.pptx) | the diagrams (editable flowchart shapes); rebuilt by `docs/pipeline/build_deck.py` |
| [../CLAUDE.md](../CLAUDE.md) | the repository's own rules (iron rules, two clones, more than one Claude session) — they still apply here |

## Hard rules (short version of STANDARDS.md)

1. **Write only inside `svg_training/`.** The rest of this repository, `~/IsaacLab` and
   `~/Documents/GitHub/Strike-Versus-Guard` are read-only. If the work needs a change outside this
   folder, stop and ask the owner; other Claude sessions work in those places. One approved
   exception: running (not editing) `tools/sim.sh` to record velocity-step logs (STANDARDS §1).
2. **The folder is part of the repository since 14 November 2026** (owner's decision: the pipeline is
   added to AirStack). Commit finished, tested work on `development` with explicit paths ("Two machines, one
   working branch" below; the root `CLAUDE.md` says the same); never push (the owner pushes), never `git add -A`, never `--no-verify`. A change
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
   **NUS privacy (owner, 18 Nov 2026, NUS agreed):** NUS's settings and our results on NUS's code may be stated in
   documents, records and commit messages; NUS's **source code** is never committed (no pasted block, no vendored file);
   code keeps reading NUS's values from `configs/local/`. Confidential programme reports are named, never quoted.
8. **No per-game Python loops** in anything that runs during training (STANDARDS §6).
9. **Videos for every training run** (STANDARDS §8); NUS's self-play runner writes none: render them with NUS's `eval.py`.

## How a session runs

Start Claude **from this folder on `development`** (`cd ~/AirStack-starling-max2-dev/svg_training && claude`; create the
worktree once with `git -C ~/AirStack-starling-max2 worktree add ../AirStack-starling-max2-dev development`) so the
agents and skills below load and the work lands on the shared branch. Then:

| Say or need | Skill |
|---|---|
| start of every session | `train-start` (it ends with `train-status`) |
| a status update: at session start, every 30 min while work runs, at once on an event, or when asked | `train-status` |
| change code, a config or a document in this folder | `train-change` |
| launch a benchmark or a training run | `train-run` |
| score a checkpoint against the gates | `train-evaluate` |
| something is wrong (NaN, reward collapse, slow, unstable) | `train-debug` |
| hand a policy to AirStack | `train-export` |
| **end of every session** (laptop or 5090) | update [docs/claude/HANDOFF.md](docs/claude/HANDOFF.md): a dated §0 summary (what was done, what waits on whom), §4, §5 and the "Last updated" line; commit it with the session's work (on its branch). On the 5090 only, the NUS workspace's copied agents/skills refresh themselves at session start (`~/ma_skills-self-play/sync_claude_setup.sh`, SessionStart hook); run it by hand after merging a branch that changed `.claude/` or `STANDARDS.md`. The laptop has no such copy |

Agents (in `.claude/agents/`, described in [docs/claude/AGENTS_AND_SKILLS.md](docs/claude/AGENTS_AND_SKILLS.md)):
`train-isaaclab-engineer`, `train-drone-dynamics`, `train-marl-researcher`,
`train-flight-interface-reviewer`, `train-gatekeeper` (advisers, read-only) and
`train-implementer` (the only one that writes code). The STE learning track adds `ste-architect`, `ste-software-engineer`
(that track's builder), `ste-test-qc-engineer`, `ste-technical-writer` and `ste-orchestrator`; their source of record is
`ste_learning/agents/` (copies in `.claude/agents/`, keep the two in step).

## Two machines, one working branch (owner, 20 Nov 2026)

The owner works on the home RTX 5090 and the RTX 5070 Ti laptop **in turns**. Both must be able to pick up where the
other stopped, from git alone.

- **`development` is the working branch on both machines** while it exists. Work lands on `development` (small edits
  directly, larger ones by fast-forward from a worktree branch cut from `development`); `main` moves only when the owner
  says so. The root `CLAUDE.md` says the same for training work (owner, 20 Nov 2026). The working folder is the worktree
  `~/AirStack-starling-max2-dev` on `development` on both machines; the docker-mounted live clone stays on `main` for
  flight work. The mirror (`~/Documents/GitHub/AirStack-starling-max2`, where it exists) is kept on `development` and
  updated with `pull --ff-only ~/AirStack-starling-max2 development`.
- **Start of a session:** `git fetch origin` (or the owner pulls in GitHub Desktop), then `git status -sb` must show
  `development` level with `origin/development`. If it is behind, the other machine has pushed: fast-forward first. If
  it has diverged, stop and ask the owner.
- **End of a session (and before the owner switches machine):** commit the work, `docs/claude/HANDOFF.md` §0 and
  `ste_learning/status/` on the branch, merge to `development` (fast-forward only), update this machine's mirror if it
  has one, and give the owner the "Ready to push" line. Nothing that matters may live only in a session, in Claude's
  memory or in `runs/`.
- **What does not travel in git:** Claude's user memory (`~/.claude/`; the owner's standing rules are below so they
  travel), `runs/` (run folders, checkpoints, videos, the shared folder `runs/shared/` with its GPU-hour ledger),
  `configs/local/` (rebuilt with `scripts/nus_install_provisional.sh`), and the 5090-only folders listed below.
  A run folder a later task needs goes into the PROVISIONAL bundle (`nus_provisional/`, installed to the same path under
  `runs/`), as the STE Guard policy (T41) did on 20 Nov; HANDOFF §0 names it.

## The owner's standing rules (portable; they were in one machine's Claude memory)

- **Status updates without being asked**: the `train-status` skill, at session start, every 30 minutes while work runs
  (a background `sleep 1800` timer, re-armed), at once on an event, and when asked. Three tables (phases with math
  library and simulator; the current phase task by task; other workstreams), then Next, Waiting on you, and a bold
  "Ready to push" line while the branch is ahead of its upstream. Tasks always "ID + plain name".
- **A second opinion at every key point** (before a plan or approach, before documentation, before declaring done, when
  stuck): on the owner's personal Max account, the `advisor` tool (Fable 5.2); on the owner's work account, where that
  tool is absent, a read-only advisor agent on the strongest model available, briefed with the full context. The
  independent QC agent (`ste-test-qc-engineer`) checks code; the advisor checks direction and soundness. Say which
  advisor was used.
- **The owner delegates technical calls** (route, proposed gates, observation, budgets inside an approved cap): decide,
  record why, explain in plain words. Still ask before anything outside this folder, anything outward-facing (messages to
  NUS or CMU, publishing, pushing), irreversible steps, and compute beyond what was approved.
- **GPU jobs side by side** when the GPU has room (`--allow-siblings`); short pilots and speed measurements alone. The
  owner pauses jobs with `scripts/gpu_pause.sh` to use the PC: never resume a pause the session did not make.
- **Videos inside every run** (STANDARDS §8); every result shown on a reader page has a GIF that plays on GitHub.
- **Reply before doing** anything that changes the outcome or the plan; propose large document changes first.
- **One fix at a time** when debugging; no parallel fixes.

## Environment (laptop verified 2026-11-14; 5090 set up 2026-11-17, updated 2026-11-18)

| Item | Laptop (RTX 5070 Ti) | Home RTX 5090 workstation |
|---|---|---|
| Role | build, test, record, commit; the live clone `~/AirStack-starling-max2` | long runs; NUS's code (owner, 17 Nov: partner code may live there); work branches in worktrees, merged on the laptop or by the lead |
| GPU, driver | RTX 5070 Ti Laptop GPU, 12 GB, driver 580.178; 24 threads; 30 GB RAM | RTX 5090, 32 GB, driver 580.126.09; 32 threads; 60 GB RAM |
| Isaac Lab on the host | `~/IsaacLab` 2.3.2 + 25 commits (`f73c331738`); **do not edit it** | `~/IsaacLab` tag v2.3.2 (`37ddf62687`) |
| conda `env_isaaclab` | Python 3.11, torch 2.7.0+cu128, Isaac Sim 5.1.0, skrl 2.1.0, rsl_rl 5.0.1. Needs `msgpack` for the NUS tests: `~/miniconda3/envs/env_isaaclab/bin/pip install "msgpack>=1.0"` if missing | same, built with hand fixes ([GETTING_STARTED step 5](docs/GETTING_STARTED.md#5-the-host-route-part-b)); msgpack 1.2.4 |
| conda `nus_jax` (NUS's JAX code) | none | Python 3.12, jax 0.10.2, flax 0.12.8 ([GETTING_STARTED](docs/GETTING_STARTED.md#nus-jax-env-with-your-nus-clone)) |
| Container | `svg-training:isaaclab-2.3.2` (T1 ran in it) | built 17 Nov; its suite is not clean yet (HANDOFF §0) |
| Isaac preflight | `scripts/isaac_preflight.sh --approved-headless` (owner, 16 Nov) | same (owner, 18 Nov, "wifi: yes"); exits 0 when no other GPU job runs |
| GPU limit per foreign process | 1024 MiB in `isaac_preflight.sh` and `run_nus_job.sh` (owner, 18 Nov) | same: the remote-desktop daemon (546–589 MiB) passes; a NUS JAX job (about 1.7 GB) blocks |
| Known trap | a window over remote desktop crashed the WiFi firmware: headless, or Ethernet, or at the machine | the shell sources ROS 2 Jazzy: `unset PYTHONPATH` before any `env_isaaclab` or `nus_jax` command ([hand fix 6](docs/GETTING_STARTED.md#hand-fixes-after-the-setup-script)) |

Other rows: AirStack simulator = Isaac Sim 5.1.0 + Pegasus + PX4 v1.16.1 in docker (`tools/sim.sh`); real drones run PX4
1.14; other training machines (RTX PRO 6000, RTX 6000 Ada) later. Full test suite, either machine, from this folder:
`unset PYTHONPATH; CUDA_VISIBLE_DEVICES="" PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python -m pytest -q -p no:cacheprovider`
(`mkdir -p runs` first on a fresh clone).

### What exists on the 5090 only (a laptop session must not assume it)

| Path | What | On the laptop instead |
|---|---|---|
| `~/ma_skills-self-play/` | NUS's three branches (private, not a git repository), the private port plan, notes `_notes/`, probes `_probes/` (Run 0, self-play matrices, videos), NUS's outputs (`…/outputs/{fixed_apf,hangar}/`: checkpoints, GIFs), its own `CLAUDE.md` and **copies** of this folder's agents and skills (`.claude/`, refreshed by `sync_claude_setup.sh` at session start) | read [docs/WHAT_WE_DID_DAY_BY_DAY.md](docs/WHAT_WE_DID_DAY_BY_DAY.md) and [docs/media/nus](docs/media/nus/README.md); NUS's code comes from NUS |
| `svg_training/configs/local/nus_*.toml` | NUS's rules, the deploy file (scale, hold), the hangar side: the files the NUS code reads | `scripts/nus_install_provisional.sh` installs the lab's copies from the PROVISIONAL bundle [nus_provisional/](nus_provisional/README.md) (owner decision 6, 18 Nov); or rebuild them with the commands in [TRAINING, NUS jobs](docs/TRAINING.md#nus-jobs) (needs NUS's code for the rules file) |
| `svg_training/runs/nus_port/` | recordings, reference data, converted weights, Phase 4 rows (`scores.json`, videos) | weights, starts and recordings: the same installer; rows and videos: the records in `records/` and the figures (runs are not in git) |
| `~/nus_jax_runs/` | logs and exact commands (`*.cmd.txt`) of every NUS job | TRAINING, NUS jobs |
| the NUS-port worktree `~/AirStack-starling-max2-nus-port/` | branch `nus-port-phase2`, where Phase 4 runs (its `configs/local/` and `runs/` hold the data) | the merged `main` |

Claude's user memory (`~/.claude/…`) and these private folders do **not** travel with git: everything a session
needs is in this folder's committed files (HANDOFF first).

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
  Approved again (owner, 18 November 2026): those two rows may carry status and pointers (the NUS port page); nothing
  else outside this folder.
  Approved (owner, 18 November 2026): a one-line banner under the root `README.md`'s H1 pointing at
  `svg_training/README.md` (option A text).
  Approved (owner, 20 November 2026): one more row in the root `README.md` "I want to…" table and one sentence in its
  `svg_training/` row, both pointing at `ste_learning/README.md`; and the status text of this folder's row in the root
  `CLAUDE.md` (stage 5.1, the STE learning track). Approved (owner, 20 November 2026): the root `CLAUDE.md` says that
  training work lands on `development` (the two-clones paragraph and the two lines of "More than one Claude session").
- Ledger rows written on the 5090 are W numbers; the lead renumbers them to the next T numbers at merge
  (records/README.md explains this to readers).
- Reader pages (label Read in docs/README.md): neutral and factual, like a short technical report; no "you"/"your" and no
  conversational headings (owner, 19 Nov 2026). Every label is NUS's own term or defined in one line where it first
  appears on each page ([GLOSSARY](docs/GLOSSARY.md) part 1: "defender (Guard team)", "attacker (Strike team)", the
  policies table, Tests 1–6 = ladder rows 1–6 of the records); link text names the destination in words; T numbers only
  in Evidence columns. NUS's own tests as counts, never a verdict; no owner quotes, clock times, agent roles or "the
  partner"; mechanisms say "likely" until a control test has run; every number links its record.
