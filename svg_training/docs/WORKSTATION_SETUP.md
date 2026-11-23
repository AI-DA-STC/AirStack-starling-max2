LAB OPERATIONS · the lab's own two machines (laptop and RTX 5090 workstation). Not needed to read or run anything: start at [../README.md](../README.md).

# Working with the lab's training workstation (RTX 5090, Ubuntu 24.04)

How to move long training runs off the laptop (RTX 5070 Ti). The laptop stays the place to build, test, record and
commit; the workstation runs long jobs. Nothing here touches AirStack, a drone or the lab network.

Setting up either machine is in [GETTING_STARTED](GETTING_STARTED.md) steps 1–7; where each machine stands is §1b below. This page holds what is about a second machine: pushing first, the private bundle, the NUS scripts,
bringing results back, remote access, the 5090's record (§2a) and the preflight decision (§2c, decided 18 November).

Status (18 November 2026): the scripts in `scripts/workstation/` were written on the laptop and checked there with
`bash -n` and `--dry-run`. On the 5090, `check_machine.sh` ran (0 failed, 2 warnings) and `setup_isaaclab_host.sh`
stopped with exit 1; hand fixes finished the host route, and the full test suite passes there (MEASURED).
`setup_nus_jax.sh` built `nus_jax` and `run_nus_job.sh` ran NUS's benchmark and training jobs (17–18 November;
[NUS port report](NUS_PORT_REPORT.md)). Isaac preflight passes headless on the 5090 since the owner's two decisions of 18 November
(§2c). `sync_results.sh`, the S0 benchmark and the S2b stand-in seed 3 have not run on the 5090 yet.

## 0. Before you leave the laptop: push first

The workstation clones from GitHub, so GitHub must have the work. On 17 November 2026 the live clone was 301
commits ahead of GitHub, and the repository carries about 41 MB of video and GIF clips (about 45 MB with figures; the NUS clips of 18 November
add 1.25 MB).

1. Bring the mirror up to date: `git -C ~/Documents/GitHub/AirStack-starling-max2 pull ~/AirStack-starling-max2 main`.
2. Push `main` from GitHub Desktop. Claude never pushes.
3. Copy the private bundle (`~/svg_workstation_bundle/`: NUS's code and checkpoints, the flight logs) and the
   construction-site world to the workstation: how and where, [GETTING_STARTED step 3](GETTING_STARTED.md#3-copy-the-files-that-are-not-in-git).

## 1. The scripts

All five print their steps; `--help` explains each, and `--dry-run` prints what would run without running it. Run
them from the pipeline folder: `cd ~/AirStack-starling-max2/svg_training`, then `scripts/workstation/<name>`.

| Script | When | What it does | On the 5090, 17 Nov 2026 |
|---|---|---|---|
| `check_machine.sh` | first, on any new machine | checks the machine: [GETTING_STARTED step 2](GETTING_STARTED.md#2-check-the-machine) | ran (step 2) |
| `setup_isaaclab_host.sh` | once, for the host route | builds `env_isaaclab` and `~/IsaacLab`: [GETTING_STARTED step 5](GETTING_STARTED.md#5-the-host-route-part-b) | ran: exit 1, then hand fixes (step 5) |
| `setup_nus_jax.sh <folder>` | once, for NUS jobs | a separate conda env `nus_jax` (Python 3.12) for NUS's code, then their CPU tests | ran: env built, NUS's tests 65 passed, 1 failed (exit 5; a stale NUS test) |
| `run_nus_job.sh` | each NUS job | starts the job in the background with a log; cloud logging off; JAX takes at most 60 % of GPU memory by default (PROPOSED; the laptop used 30 % beside other runs); refuses when another process holds more than 1024 MiB | ran: benchmark, fixed-opponent and self-play jobs ([TRAINING, NUS jobs](TRAINING.md#nus-jobs)) |
| `sync_results.sh <pc> <run>` | on the laptop, after a run | copies `runs/<run>/` back, plus the workstation's record and ledger for you to copy by hand | not run yet |

## 1b. Where each machine stands, step by step

Moved from GETTING_STARTED on 18 November 2026; the cells are as they were measured.

### The machines

GETTING_STARTED's steps have the same order on every machine; the tables below say where each of the lab's machines stands at each step.

| Machine | What it is for | Where it stands (18 November 2026) |
|---|---|---|
| Laptop (RTX 5070 Ti, 12 GB) | build, test, record and commit; smoke runs | set up: the container (the S0 run of record T1 ran in it) and the host route |
| Workstation (home RTX 5090, 32 GB) | long runs; NUS's code (5090 only) | host route built with the hand fixes (step 5); conda `nus_jax` for NUS's code ([GETTING_STARTED](GETTING_STARTED.md#nus-jax-env-with-your-nus-clone)); Isaac preflight passes headless when no other GPU job runs (step 7); container image built 17 Nov, its suite not clean (HANDOFF §0) |
| Another new machine | — | a fresh install: follow the 5090 column |

In the tables below, 5090 cells are MEASURED on 17 November 2026; laptop cells come from this folder's
existing pages and records.

Rebuilding the laptop from scratch: use the same steps. The hand fixes likely apply too (observed on the 5090, not
run on the laptop). The rest of this page covers working with a second machine.

#### GETTING_STARTED step: 1. Get the code

| Laptop | 5090 workstation |
|---|---|
| the live clone: commits land here, so there is nothing to clone | clones from GitHub, so push from the laptop first ([WORKSTATION_SETUP §0](#0-before-you-leave-the-laptop-push-first)) |

#### GETTING_STARTED step: 2. Check the machine

| Laptop | 5090 workstation |
|---|---|
| written there; run only with `--dry-run` | 17 Nov: 0 failed, 2 warnings. The GPU has users (the remote-desktop daemon), and tmux is missing: install it with `sudo apt install tmux`. The Docker check downloaded `ubuntu:latest` (102 MB) |

#### GETTING_STARTED step: 3. Copy the files that are not in git

| Laptop | 5090 workstation |
|---|---|
| holds the private bundle | none of the three copied yet (17 Nov) |

#### GETTING_STARTED step: 4. The container route (part A)

| Laptop | 5090 workstation |
|---|---|
| built; T1 ran in it | built 17 Nov; its suite there is not clean yet: 704 passed, 29 failed, 13 errors (skrl 1.4.3 in the image, `svg_ground_control` not mounted, bare `python` calls; HANDOFF §0, 17 Nov evening, item 5) |

#### GETTING_STARTED step: 5. The host route (part B)

| Laptop | 5090 workstation |
|---|---|
| has `~/IsaacLab` (`f73c331738`) and `env_isaaclab`. The script has not run there (dry run only) | 17 Nov, default `v2.3.2`: exit 1. The script's steps 1–4 ran cleanly; its step 5 left out the core `isaaclab` package and changed torch; its step 9 (the tests) failed. The hand fixes finished it |

#### GETTING_STARTED step: 6. First tests

| Laptop | 5090 workstation |
|---|---|
| both routes in use; every S0 run starts with the tests (`runs/<name>/tests.txt`) | host, 17 Nov: 798 passed, 11 skipped, in 5 min 46 s. Eight skips are Isaac tests that need `SVG_ISAAC_TESTS=1` after preflight; three need private files not yet copied. Container, 17 Nov: 704 passed, 29 failed, 13 errors (step 4 table) |

#### GETTING_STARTED step: 7. The first Isaac check (preflight)

| Laptop | 5090 workstation |
|---|---|
| starting Isaac Sim with a window over remote desktop has crashed its WiFi firmware. The owner approved headless launches on it over WiFi (16 Nov); `--approved-headless` returned 0 before each point of the S2b speed run ([record](../records/2026-11-16_s2b_throughput_record.md)). Plain run: not recorded | 18 Nov: `--approved-headless` exits 0 when no other GPU job runs (a NUS JAX job, about 1.7 GB, still blocks it, as it should). 17 Nov, before the owner's two decisions: exit 10, and exit 11 at the old 500 MiB limit ([WORKSTATION_SETUP §2c](#2c-preflight-on-the-5090-decided-18-november)) |

#### GETTING_STARTED step: NUS JAX env

| Laptop | 5090 workstation |
|---|---|
| not built (no NUS code there) | 17 Nov: built (jax 0.10.2, flax 0.12.8, CUDA 13 JAX); NUS's CPU tests: 65 of 66 pass; the one failure checks an older Guard distance, which NUS confirmed is out of date (exit 5). Note: `pip install -e` writes build files into the NUS clone |

#### GETTING_STARTED step: The S0 benchmark

| Laptop | 5090 workstation |
|---|---|
| T1 ran in the container | not run yet; a config for 32 GB needs the owner's approval ([WORKSTATION_SETUP §2](#2-the-first-evening-in-order)) |

## 2. The first evening, in order

1. **Push first** (§0) and copy the private bundle.
2. **Set up the machine:** [GETTING_STARTED](GETTING_STARTED.md) steps 1–7, the 5090 column.
3. **S0 speed benchmark** (Linear NEAR-959): [GETTING_STARTED, the S0 benchmark](GETTING_STARTED.md#the-s0-benchmark).
   It runs only on a config the owner approved (its sha256). More games to fill the 5090's 32 GB is a new config, so
   it needs his approval first (STANDARDS §7). Not run on the 5090 yet.
4. **The remaining S2b Isaac stand-in seeds**: the ones the laptop did not finish. The list and the exact command
   are in [HANDOFF](claude/HANDOFF.md) and `scripts/train_standin.py --help`. They start with
   `scripts/isaac_preflight.sh --approved-headless` (§2c). Always headless.
5. **NUS jobs.** `scripts/workstation/setup_nus_jax.sh <NUS folder>`, then `run_nus_job.sh` with the settings in
   the bundle's NOTES and in [TRAINING, NUS jobs](TRAINING.md#nus-jobs). Run them inside `tmux`. Done on the 5090,
   17–18 November ([NUS port report](NUS_PORT_REPORT.md)).

## 2a. What ran on the 5090

Everything in this section was MEASURED on the 5090 on 17 November 2026, by a Claude session with the owner. The
results of the setup steps (machine check, setup script, tests, preflight) are in the 5090 column of
[GETTING_STARTED](GETTING_STARTED.md) steps 2–7. The laptop's values are in [CLAUDE.md](../CLAUDE.md) (Environment)
and [GLOSSARY, Versions](GLOSSARY.md#versions).

| The machine | Value |
|---|---|
| GPU | NVIDIA GeForce RTX 5090, 32 GB; driver and software versions in [GLOSSARY](GLOSSARY.md#versions) |
| CPU threads, memory | 32 threads, 60 GB |
| OS, Docker, free disk in `$HOME` | Ubuntu 24.04.4 LTS; Docker 29.6.1, containers see the GPU; 330 GB |
| Network | WiFi only; no Ethernet connected |
| Remote-desktop programs running | gnome-remote-desktop-daemon, AnyDesk, TeamViewer, RustDesk |
| GPU memory in use at idle | 546 MiB, held by gnome-remote-desktop-daemon |
| tmux | not installed |
| Shell | `~/.bashrc` sources ROS 2 Jazzy, so `PYTHONPATH` holds ROS's Python folders ([GETTING_STARTED, hand fix 6](GETTING_STARTED.md#hand-fixes-after-the-setup-script)) |

**A headless Isaac smoke run** (not a run of record): `scripts/spike_isaac_starling.py`, headless, 64 games. Status
ok, 512 drones, 0 NaN, about 254,000 drone-steps/s at 200 Hz, 3.8 GB of GPU memory, Isaac launch 3.3 s. Observed in
the training simulator. It ran without preflight passing (§2c), so it is not a procedure.

**Not run on the 5090 yet** (18 November): `run_s0.sh`; `train_standin.py`; `score.py`; the step tests;
`fit_real_px4.py`; `sync_results.sh`; any launch with the Isaac Sim window; TensorBoard. The container image was built
on 17 November; its test suite is not clean yet (HANDOFF §0). The private bundle, the flight logs and the
construction-site world are not copied yet. Ran since 17 November: `setup_nus_jax.sh`, `run_nus_job.sh`, the NUS port
Phases 1–4 ([NUS port report](NUS_PORT_REPORT.md)), Isaac Lab headless after preflight (the Phase 4 row 6 warm-up estimate, 18 November).

## 2c. Preflight on the 5090 (decided 18 November)

`scripts/isaac_preflight.sh` checks the machine before an Isaac launch. On the 5090 (MEASURED, 17 November 2026),
before the decisions below:

| Command | Exit | Cause |
|---|---|---|
| `scripts/isaac_preflight.sh` | 10 | WiFi only, with remote-desktop programs running (§2a) |
| `scripts/isaac_preflight.sh --approved-headless` | 11 | the GPU counted as in use: gnome-remote-desktop-daemon held 546 MiB, over the old 500 MiB limit |

The owner's decisions (18 November 2026):

- **GPU limit 1024 MiB per foreign process**, in `isaac_preflight.sh` and in `run_nus_job.sh` alike, so the
  remote-desktop daemon (546–589 MiB measured) no longer blocks. A NUS JAX job (about 1.7 GB) still blocks, as it should.
- **Headless over WiFi is approved on the 5090 too**, as on the laptop (16 November). Use
  `scripts/isaac_preflight.sh --approved-headless`; it exits 0 on the 5090 when no other GPU job runs. A window over
  remote desktop stays forbidden on both machines.

## 3. NUS's code stays in NUS's repository; its settings and our results may be published

NUS's code lives outside this repository (on the workstation, in a folder outside every git repository). It is never
committed or pushed (`tests/test_partner_privacy.py` fails on a tracked copy). NUS agreed (18 November 2026) that their
settings and our results may be published, and our converted G19, S20, P3G and P3S, the local settings files and the
recordings are committed as PROVISIONAL in [nus_provisional/](../nus_provisional/README.md) ([STANDARDS §2](../STANDARDS.md#2-wording)).
The scripts stay generic: `run_nus_job.sh` takes every NUS setting as an argument, and a test fails if NUS-specific
words or values appear in the scripts. Logs go to `~/nus_jax_runs/`, NUS's outputs to NUS's own `outputs/` folder,
both outside the repository.

## 4. Getting results back to the laptop

Every run folder under `runs/<name>/` holds the policy, TensorBoard logs, scores and settings. On the laptop:

```bash
scripts/workstation/sync_results.sh --dry-run <workstation> <name>    # see the commands
scripts/workstation/sync_results.sh <workstation> <name>              # copy
```

Runs of record are still recorded and committed on the laptop. `run_s0.sh` writes a record and a ledger row on the
machine that ran it, so `sync_results.sh` brings the workstation's record and ledger into
`runs/<name>/_from_workstation/`. Move the record into `records/`, and copy its ledger row by hand with the laptop
ledger's next T number (the two ledgers number separately). Then commit on the laptop.

## 5. Working on it from the lab (Tailscale + Ubuntu remote desktop)

- Join the PC and the laptop to the same Tailscale network; use the PC's Tailscale name as `<workstation>`.
- Ubuntu 24.04: Settings → System → Remote Desktop. "Remote Login" works with nobody logged in at the PC.
- Start long runs inside `tmux`, so a dropped connection does not stop them; `tmux attach` to look again.
- TensorBoard: `tensorboard --logdir runs/` on the PC, or `ssh -L 6006:localhost:6006 <workstation>` and open
  `http://localhost:6006` on the laptop.
- `isaac_preflight.sh` refuses (exit 10) when no Ethernet is connected and a remote-desktop program runs. That rule
  comes from the laptop's WiFi crashes. With `--approved-headless` (approved on both machines) it warns instead: §2c.

## 6. Rules that still apply

- Headless for every run; check `nvidia-smi` before each one (CLAUDE.md rule 6).
- A training result is not a flight result: write "observed in the training simulator" (CLAUDE.md rule 4).
- Nothing trained here flies until it has passed its gates and the export stage (STANDARDS §3).
