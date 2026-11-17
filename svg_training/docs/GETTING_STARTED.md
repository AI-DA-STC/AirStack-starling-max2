# Getting started: set up a machine, then run the tests and a benchmark

This is the one setup guide for every machine: the laptop, the home RTX 5090 workstation, or a new one. It has
three goals, in order. First the machine is set up and the tests pass. Then a trial run prints its plan without
starting anything (a *dry run*). Then the S0 benchmark runs and writes its summary (the *record*). Terms are in the
[glossary](GLOSSARY.md).

There are two ways to run the pipeline. A *container* is a sealed copy of the software that runs the same way on
every machine (the *container route*). The *host route* installs Isaac Lab and a Python environment on the machine
itself. A machine can have both.

## Pick your machine

Every step below has the same order on every machine. Where a step differs by machine, a small table says how.

| Machine | What it is for | Where it stands (18 November 2026) |
|---|---|---|
| Laptop (RTX 5070 Ti, 12 GB) | build, test, record and commit; smoke runs | set up: the container (the S0 run of record T1 ran in it) and the host route |
| Workstation (home RTX 5090, 32 GB) | long runs; NUS's code (5090 only) | host route built with the hand fixes (step 5); conda `nus_jax` for NUS's code ([below](#nus-jax-env-home-rtx-5090-only)); Isaac preflight passes headless when no other GPU job runs (step 7); container image built 17 Nov, its suite not clean (HANDOFF §0) |
| Another new machine | — | a fresh install: follow the 5090 column |

In the step tables below, 5090 cells are MEASURED on 17 November 2026; laptop cells come from this folder's
existing pages and records.

Rebuilding the laptop from scratch: use the same steps. The hand fixes likely apply too (observed on the 5090, not
run on the laptop). Working with a second machine (pushing first, the private bundle, NUS jobs, bringing results
back, remote access): [WORKSTATION_SETUP](WORKSTATION_SETUP.md).

**What the machine needs.**

| Item | Detail |
|---|---|
| NVIDIA GPU and driver | driver 580 or newer. T1 ran on the laptop's RTX 5070 Ti Laptop GPU, driver 580.178.04 |
| GPU memory | at least 12 GB: T1 used up to 7.6 GB device-wide on 12 GB; Isaac Sim states a 16 GB minimum |
| Docker + NVIDIA Container Toolkit | for the container route; the container starts with `--gpus all` |
| Disk | 60 GB free or more (step 2 checks it); NVIDIA's Isaac Lab image alone is about 26 GB |
| Internet, first tier 2 run | Isaac Lab downloads its drone asset the first time |
| A free GPU | no AirStack simulator, flight session or other Isaac process running; check with `nvidia-smi` on the host |

## 1. Get the code

```bash
git clone https://github.com/AI-DA-STC/AirStack-starling-max2.git ~/AirStack-starling-max2   # new machine, once
git -C ~/AirStack-starling-max2 pull           # later, to update (workstation or new machine only)
cd ~/AirStack-starling-max2/svg_training
mkdir -p runs          # run output goes here; it is not in git, so a fresh clone lacks it and one test fails
```

Every command on this page runs from `~/AirStack-starling-max2/svg_training`.

| Laptop | 5090 workstation |
|---|---|
| the live clone: commits land here, so there is nothing to clone | clones from GitHub, so push from the laptop first ([WORKSTATION_SETUP §0](WORKSTATION_SETUP.md#0-before-you-leave-the-laptop-push-first)) |

## 2. Check the machine

```bash
scripts/workstation/check_machine.sh                  # --skip-docker leaves out the Docker check
```

It checks the GPU, the driver (580 or newer), the Ubuntu version, free disk (60 GB or more), Docker with the GPU and
conda. Exit 0 means go; fix every FAIL line first. It changes no settings, but its Docker check downloads the small
`ubuntu` image the first time.

| Laptop | 5090 workstation |
|---|---|
| written there; run only with `--dry-run` | 17 Nov: 0 failed, 2 warnings. The GPU has users (the remote-desktop daemon), and tmux is missing: install it with `sudo apt install tmux`. The Docker check downloaded `ubuntu:latest` (102 MB) |

## 3. Copy the files that are not in git

Everything the pipeline needs lives inside the repository folder, either in git or in a git-ignored folder you
copy by hand. Nothing is read from other project folders (owner, 17 November 2026). The one exception is the
AirStack simulator's own output under `~/flight_logs/sim/`, which `scripts/record_steps.sh` collects from
`tools/sim.sh`.

| What | Where it goes | Needed for |
|---|---|---|
| Three real flight logs of 13 November (`log103.ulg`, `log105.ulg`, `08_47_58.ulg`, 51 MB) | `svg_training/data/flight_logs/2026-11-13/` (git-ignored), same sub-folders as in the bundle | the S2b step tests (`configs/s2b.toml [step_tests] real_log`) and the S1 real-log fit (`scripts/fit_real_px4.py`) |
| Partner's code, checkpoints, reference logs | outside the repository, as the bundle's NOTES say; on the 5090 NUS's code is in `~/ma_skills-self-play/` (5090 only) | NUS jobs only ([TRAINING, NUS jobs](TRAINING.md#nus-jobs)) |
| Construction-site world, `source/` and `build/` (about 280 MB, bought asset) | `localisation/scenes/construction_site/` in the clone, beside its README | the construction-site clips and screenshots only; training, scoring, tests and the other worlds do not use it |

The first two rows come in the private bundle (`~/svg_workstation_bundle/` on the laptop). Copy it by USB, a private
drive or `scp`; it never goes to GitHub. Its NOTES name each folder and give the sha256 of each archive: check them
before unpacking. The construction-site world is not in the bundle: copy it by hand.

| Laptop | 5090 workstation |
|---|---|
| holds the private bundle | none of the three copied yet (17 Nov) |

## 4. The container route (part A)

```bash
docker/build.sh                 # once; downloads NVIDIA's base image (about 26 GB)
```

You should see `built svg-training:isaaclab-2.3.2`. The code is mounted when the container starts, so a code change
needs no rebuild. What the image holds and where it stores things: [docker/README](../docker/README.md).

| Laptop | 5090 workstation |
|---|---|
| built; T1 ran in it | built 17 Nov; its suite there is not clean yet: 704 passed, 29 failed, 13 errors (skrl 1.4.3 in the image, `svg_ground_control` not mounted, bare `python` calls; HANDOFF §0, 17 Nov evening, item 5) |

## 5. The host route (part B)

The host route needs Isaac Lab 2.3.2 in `~/IsaacLab` and the conda environment `env_isaaclab`. The setup script
builds both with the laptop's pinned versions (Python 3.11, PyTorch 2.7.0 for CUDA 12.8, Isaac Sim 5.1.0, Isaac Lab
2.3.2, skrl 2.1.0; the list is `scripts/workstation/env_isaaclab_requirements.txt`).

```bash
scripts/workstation/setup_isaaclab_host.sh --dry-run    # prints every step; read it
scripts/workstation/setup_isaaclab_host.sh              # builds it; stops with exit 4 if env_isaaclab exists
```

Isaac Lab is the tag `v2.3.2` by default. The laptop runs 2.3.2 plus 25 commits (`f73c331738`, none in code the
pipeline uses); add `--isaaclab-ref f73c331738` to match it exactly. Never edit `~/IsaacLab`. The script does not
accept NVIDIA's licence for you (fix 4 below). Today it stops with exit 1 on a fresh install: then do the hand fixes.

| Laptop | 5090 workstation |
|---|---|
| has `~/IsaacLab` (`f73c331738`) and `env_isaaclab`. The script has not run there (dry run only) | 17 Nov, default `v2.3.2`: exit 1. The script's steps 1–4 ran cleanly; its step 5 left out the core `isaaclab` package and changed torch; its step 9 (the tests) failed. The hand fixes finished it |

Versions on both machines: [GLOSSARY, Versions](GLOSSARY.md#versions).

**`msgpack`** (owner approval, 18 November 2026; `pyproject.toml`): the NUS checkpoint loader and its tests need it,
and `tests/_nus_markers.py` imports it, so the suite stops at collection without it. The 5090's `env_isaaclab` has
1.2.4. On a machine that lacks it (check: `~/miniconda3/envs/env_isaaclab/bin/pip show msgpack`):

```bash
~/miniconda3/envs/env_isaaclab/bin/pip install "msgpack>=1.0"
```

The container image does not have it yet (HANDOFF §5).

### Hand fixes after the setup script

A dated workaround (17 November 2026); the script is not yet fixed. `setup_isaaclab_host.sh` does not do these
yet. Run them after it, in one terminal, in this order. Fixes 1–5 apply to any fresh install today. Fix 6 applies
only where the shell sources ROS (the 5090's does); its line is in the first block below, so it runs first.

```bash
cd ~/AirStack-starling-max2/svg_training
P=~/miniconda3/envs/env_isaaclab/bin/python
unset PYTHONPATH    # fix 6: only if your shell sources ROS (the 5090's does)
```

**A. Any fresh install today**

1. **The core `isaaclab` package is missing.** The script's step 5 builds `flatdict==4.0.1` from source with the
   newest setuptools (84.2.1), which no longer has `pkg_resources`. The installer carries on: the other five Isaac Lab
   packages install, `isaaclab` does not.
   ```bash
   $P -m pip install "setuptools<81"
   $P -m pip install --no-build-isolation flatdict==4.0.1
   $P -m pip install --no-build-isolation -e ~/IsaacLab/source/isaaclab
   ```
2. **CUDA 13 libraries left behind.** `isaaclab_rl` needs `torch>=2.7`, so the script's step 5 installs torch 2.15.0
   for CUDA 13 with its libraries. The script's step 6 puts torch back to 2.7.0+cu128 but leaves those libraries.
   Removing them also deletes files that torch's CUDA 12 libraries share (`ImportError: libcudnn.so.9`), so reinstall
   those after. On the 5090 this was done by hand; the lines below rebuild it from pip's own data. Their list commands
   were checked against the 5090 env (the reinstall list matches what was reinstalled by hand); the uninstall has not
   been run as written (PROPOSED). Read the list before you uninstall. An empty list means there is nothing to do.
   ```bash
   G=$($P -m pip list --format=freeze | grep -iE '^(cuda|nvidia)' | grep -viE -- '-cu12==' | cut -d= -f1)
   echo $G    # expect cuda-toolkit, nvidia-*-cu13 and nvidia-* without a suffix; stop if anything else shows
   if [ -n "$G" ]; then
     $P -m pip uninstall -y $G
     $P -m pip install --force-reinstall --no-deps $($P -c "import importlib.metadata as m; print(' '.join(r.split(';')[0].replace(' ', '') for r in m.requires('torch') if r.startswith(('nvidia-', 'triton'))))")
   fi
   ```
3. **Packages without a pin drift from the laptop.** Isaac Lab leaves `warp-lang` unpinned (the 5090 got 1.19.0;
   the laptop has 1.14.0), and `stable_baselines3`, `tensordict` and `starlette` came newer too. Match the laptop:
   ```bash
   $P -m pip install warp-lang==1.14.0 starlette==0.49.1 tensordict==0.12.4 stable_baselines3==2.8.0 pandas==3.0.3
   ```
   The laptop's full list is `scripts/workstation/env_isaaclab_freeze_laptop.txt`; the script's step 8 prints the
   differences.
4. **NVIDIA's licence.** On the 5090 the script ran with `OMNI_KIT_ACCEPT_EULA=YES` (the owner's choice). That lasts
   for one command only. A later process with no terminal, such as pytest's preflight test, then stops with
   `Unable to bootstrap inner kit kernel: EOF when reading a line`. Start Isaac Sim once from a terminal, read the
   licence and accept it yourself. That writes `yes` into the file below. On the 5090 the file was written with the
   owner's approval. Deleting it undoes the acceptance.
   ```bash
   cat ~/miniconda3/envs/env_isaaclab/lib/python3.11/site-packages/isaacsim/kit/EULA_ACCEPTED    # must print yes
   ```
5. **No `runs/` folder in a fresh clone** (it is git-ignored). `tests/test_record_steps.py` then fails with
   `FileNotFoundError` in `test_refuses_existing_run_folder`. The `mkdir -p runs` in step 1 of this page makes it.

**B. Only where the shell sources ROS (the 5090)**

6. **ROS on `PYTHONPATH`.** ROS's Python 3.12 folders leak into `env_isaaclab` (Python 3.11). The tests stop with
   `ModuleNotFoundError: No module named 'lark'` from a ROS pytest plugin; pip prints conflicts for ROS packages, and
   the script's step 8 diff lists them. Clear it in every new terminal before any `env_isaaclab` command (the first
   block of this section already does):
   ```bash
   unset PYTHONPATH
   ```
   To check: `echo $PYTHONPATH`; a path under `/opt/ros/` means your shell sources ROS. From `svg_training/`,
   `PYTHONPATH=source` works too. `scripts/run_s0.sh` sets that itself.

**Check.** Expect torch `2.7.0+cu128`, `True` (the GPU is seen) and warp `1.14.0`.

```bash
$P -c "import torch, isaaclab, warp; print(torch.__version__, torch.cuda.is_available(), warp.config.version)"
```

## 6. First tests

Container route:

```bash
docker/run.sh '$SVG_PY -m pytest -q'
```

Host route:

```bash
unset PYTHONPATH                # only if your shell sources ROS (hand fix 6)
~/miniconda3/envs/env_isaaclab/bin/python -m pytest -q -p no:cacheprovider
```

The tests passed if the last line has no `failed`. Two skipped tests in the container are normal: they only run on
the host.

| Laptop | 5090 workstation |
|---|---|
| both routes in use; every S0 run starts with the tests (`runs/<name>/tests.txt`) | host, 17 Nov: 798 passed, 11 skipped, in 5 min 46 s. Eight skips are Isaac tests that need `SVG_ISAAC_TESTS=1` after preflight; three need private files not yet copied. Container, 17 Nov: 704 passed, 29 failed, 13 errors (step 4 table) |

## 7. The first Isaac check (preflight)

Run this before every Isaac Sim start, and always run Isaac headless (without a window).

```bash
nvidia-smi                      # the GPU is free: no AirStack simulator, flight session or other Isaac process
scripts/isaac_preflight.sh      # exit 0 means go
```

Exit 10: WiFi only, with a remote-desktop program running. Exit 11: another process holds more than 1024 MiB of GPU
memory (owner, 18 November 2026: raised from 500 MiB so the 5090's remote-desktop daemon, 546–589 MiB, does not block;
`scripts/workstation/run_nus_job.sh` uses the same limit). `--approved-headless` turns exit 10 into a warning; the owner
has approved it on both machines (laptop 16 November, 5090 18 November). Never open a window over remote desktop.

| Laptop | 5090 workstation |
|---|---|
| starting Isaac Sim with a window over remote desktop has crashed its WiFi firmware. The owner approved headless launches on it over WiFi (16 Nov, "yes dont worry about wifi"); `--approved-headless` returned 0 before each point of the S2b speed run ([record](../records/2026-11-16_s2b_throughput_record.md)). Plain run: not recorded | 18 Nov: `--approved-headless` exits 0 when no other GPU job runs (a NUS JAX job, about 1.7 GB, still blocks it, as it should). 17 Nov, before the owner's two decisions: exit 10, and exit 11 at the old 500 MiB limit ([WORKSTATION_SETUP §2c](WORKSTATION_SETUP.md#2c-preflight-on-the-5090-decided-18-november)) |

## NUS JAX env (home RTX 5090 only)

NUS's training code is JAX, not PyTorch, and runs in its own conda env, `nus_jax` (Python 3.12), away from
`env_isaaclab`. Only the 5090 has NUS's code (`~/ma_skills-self-play/`, outside every git repository); the laptop
does not need this env to read the results or run the tests (the NUS tests that need NUS's code or the local files
skip there).

```bash
unset PYTHONPATH                # ROS 2 Jazzy is Python 3.12 too: it would load quietly into nus_jax
C=~/ma_skills-self-play/area-denial-continuous-space-self-play
scripts/workstation/setup_nus_jax.sh --dry-run --skip-gpu-check $C
scripts/workstation/setup_nus_jax.sh --skip-gpu-check $C
```

| Laptop | 5090 workstation |
|---|---|
| not built (no NUS code there) | 17 Nov: built (jax 0.10.2, flax 0.12.8, CUDA 13 JAX); NUS's CPU tests 65 passed, 1 failed (a stale NUS test; exit 5). Note: `pip install -e` writes build files into the NUS clone |

Running NUS jobs and our NUS scripts: [TRAINING, NUS jobs](TRAINING.md#nus-jobs).

## Container or host?

| Situation | Use |
|---|---|
| The tests and the S0 benchmark, a run of record | the container: one known image, the same as T1, so the numbers compare |
| The S2b Isaac stand-in seeds | the host: the stand-in trainer needs skrl 2.x and the container has 1.4.3 |
| Quick tests | either; the host skips the container start (on the 5090, the host, until the container suite is clean) |
| The host's Isaac Lab differs from 2.3.2 | the container |

## The S0 benchmark

**Dry run.** It prints every command the benchmark would run and starts nothing.

```bash
docker/run.sh bash scripts/run_s0.sh --dry-run 2026-11-20_s0_trial <approved sha256> | head -40   # container route
```

```bash
bash scripts/run_s0.sh --dry-run 2026-11-20_s0_trial <approved sha256> | head -40                 # host route
```

<a id="approved-sha256"></a>**The approved sha256** (the config T1 ran, [record](../records/2026-11-15_s0_laptop_record.md#config)):
`2d3114864a8f335ce8456e40af9c50c63700d59d821d53b9b0f3e7abac2accf0`.
A sha256 *hash* is a fingerprint of a file: change one character and the hash changes. So the hash proves the
config is the one the owner approved. `sha256sum configs/s0_benchmark.toml` must print exactly this. If it
differs, `run_s0.sh` stops with exit 65, and the config needs the owner's approval. The pass/fail checks set
before a run (the *gates*) are never moved.

The dry run prints the plan for where it runs: host paths on the host, container paths inside `docker/run.sh`.
`head -40` keeps it short, because tier 2 adds one long line per point.

**The benchmark.** Pick a new name, `YYYY-MM-DD_s0_<label>` (lowercase letters, digits, `_`).

```bash
docker/run.sh bash scripts/run_s0.sh 2026-11-20_s0_workstation <approved sha256>   # container route
```

```bash
bash scripts/run_s0.sh 2026-11-20_s0_workstation <approved sha256>                 # host route
```

At the end you should see `record: records/<name>_record.md` and the verdict line. Run it without a window
(*headless*), and do not use the GPU for anything else meanwhile. On the host the script finds Python and Isaac Lab
by itself; tier 2 starts through `conda run -n env_isaaclab`.

| Laptop | 5090 workstation |
|---|---|
| T1 ran in the container | not run yet; a config for 32 GB needs the owner's approval ([WORKSTATION_SETUP §2](WORKSTATION_SETUP.md#2-the-first-evening-in-order)) |

## Reading the output

The table lists the files a run writes and what each holds.

| Where | What it holds |
|---|---|
| `runs/<name>/preflight.txt` | start time, code hash, config hash, GPU state before the run |
| `runs/<name>/tests.txt` | the test step's output |
| `runs/<name>/results.jsonl` | one line per repeat of every point: speeds, memory, status (`ok`, `oom`, `crash`) |
| `runs/<name>/tier1.log`, `tier2.log`, `tier2_logs/` | progress; one log per tier 2 point |
| `runs/<name>/retried_points.txt` | tier 2 points retried after an Isaac start-up crash (only if any) |
| `records/<name>_record.md` | the record: tables, gates with PASS or FAIL, decision rules, limits; never edited |
| `records/LEDGER.md` | the *ledger*: one row per run, T1, T2, … |

`runs/` is not in git; `records/` is. How to read T1: [S0_RESULTS](S0_RESULTS.md).

## How long it takes

T1 took 1 h 47 min on the laptop: preflight at 00:54 Singapore time on 15 November 2026, last row at 02:41.
Tier 1 took most of it. Its slowest points step about once every 2 s (`t1_5v3_prim50_full` at 16,384 games). So
the 200-step timed window lasts up to about 7 minutes per repeat. Tier 2 took about a quarter of an hour.
T1's own files show these times in container UTC (8 h behind).

## When it fails

The table lists each exit code of `run_s0.sh`, what it means and what to do.

| Exit code | Meaning | What to do |
|---|---|---|
| 0 | the record was written, whatever its verdict | read the record |
| 1 | the record could not be written | read the last lines of the output |
| 64 | bad arguments | check the name pattern and the 64-hex hash |
| 65 | config differs from the [approved one](#approved-sha256) | do not edit the config; ask the owner |
| 66 | an Isaac or AirStack container is running | stop it (`docker ps`), then retry |
| 67 | `records/<name>_record.md` already exists | choose a new name; a record is never overwritten |
| 68 | another process uses the GPU (python, kit, isaac or omni) | stop it; `nvidia-smi` on the host |
| 130 | interrupted (Ctrl-C) | an `ABORTED` record is written in `records/` |

- A point that crashes or runs out of memory does not stop the run. It gets a `crash` or `oom` row, and the record
  says why.
- Isaac Sim sometimes crashes while starting: there is no row, and the log stops before the scene is built. Such a
  point is retried once and listed in `retried_points.txt`.
- If you run again with the same name before a record exists, the run picks up where it stopped: finished points
  are skipped.
- In the container, the GPU check sees only the container's own processes. Run `nvidia-smi` on the host first.

Next: training, headless and with the Isaac Sim window → [TRAINING](TRAINING.md) (planned workflow until S2).
