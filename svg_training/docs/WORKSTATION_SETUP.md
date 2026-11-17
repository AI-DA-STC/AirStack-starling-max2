# Setting up a training workstation (home PC: RTX 5090, Ubuntu 24.04)

How to move long training runs off the laptop. The laptop stays the place to build, test, record and commit; the
workstation runs long jobs. Nothing here touches AirStack, a drone or the lab network.

Status: PROPOSED (owner, 17 November 2026). The scripts in `scripts/workstation/` were written on the laptop and
checked there only with `bash -n` and `--dry-run`. **None has run on the 5090 yet.**

## 0. Before you leave the laptop: push first

The workstation clones from GitHub, so GitHub must have the work. On 17 November 2026 the live clone was 301
commits ahead of GitHub, and the repository carries about 41 MB of video and GIF clips.

1. Bring the mirror up to date: `git -C ~/Documents/GitHub/AirStack-starling-max2 pull ~/AirStack-starling-max2 main`.
2. Push `main` from GitHub Desktop. Claude never pushes.
3. Copy the private bundle (`~/svg_workstation_bundle/`) to the workstation by USB, a private drive or `scp`.
   It holds the partner's code and checkpoints and the flight log. It never goes to GitHub.
4. Copy the construction-site world too (section 1a): it is not in git and not in the bundle.

## 1a. Files that are not in git

Everything the pipeline needs lives inside the repository folder, either in git or in a git-ignored folder you
copy by hand. Nothing is read from other project folders.

| What | Where it goes on the workstation | Needed for |
|---|---|---|
| Construction-site world, `source/` and `build/` (about 280 MB, bought asset) | `localisation/scenes/construction_site/` in the clone, beside its README | the construction-site clips and screenshots only; training, scoring, tests and the other worlds do not use it |
| Partner's code, checkpoints, reference logs | outside the repository, as the bundle's NOTES say | NUS jobs only |
| Flight log `log103.ulg` (13 November, drone_2) | `~/flight_logs/2026-11-13/ulog_drone_2/` (path in `configs/s2b.toml`, `real_log`) | the S2b step tests (T11) only |

The flight log is the one file still read from outside the repository folder; moving it inside needs a config
change (`real_log`) and the owner's approval.

## 1. The scripts

All five print their steps; `--help` explains each, and `--dry-run` prints what would run without running it.

| Script | When | What it does |
|---|---|---|
| `check_machine.sh` | first, on the workstation | read-only checks: GPU, driver (580 or newer), Ubuntu version, free disk (60 GB or more), Docker with the GPU, conda |
| `setup_isaaclab_host.sh` | once, for Isaac runs on the host | conda `env_isaaclab` as on the laptop: Python 3.11, PyTorch 2.7.0 for CUDA 12.8, Isaac Sim 5.1.0, Isaac Lab 2.3.2 in `~/IsaacLab`, skrl 2.1.0; versions in `env_isaaclab_requirements.txt` |
| `setup_nus_jax.sh <folder>` | once, for NUS jobs | a separate conda env `nus_jax` (Python 3.12) for NUS's code, then their CPU tests |
| `run_nus_job.sh` | each NUS job | starts the job in the background with a log; cloud logging off; JAX takes at most 60 % of GPU memory by default (PROPOSED; the laptop used 30 % beside other runs) |
| `sync_results.sh <pc> <run>` | on the laptop, after a run | copies `runs/<run>/` back, plus the workstation's record and ledger for you to copy by hand |

Run them from the pipeline folder: `cd ~/AirStack-starling-max2/svg_training`, then `scripts/workstation/<name>`.

**Container or host?** Use the container ([GETTING_STARTED](GETTING_STARTED.md) part A) for the tests and the S0
benchmark: it is the same image as the laptop's run of record T1, so the numbers compare. Use the host env for the
S2b Isaac stand-in seeds and the step tests: the stand-in trainer needs skrl 2.x and the container has 1.4.3, and
the step tests read a flight log outside this folder.

On the host, Isaac Lab is 2.3.2 by default. The laptop runs 2.3.2 plus 25 commits (`f73c331738`, none in code the
pipeline uses); add `--isaaclab-ref f73c331738` to match it exactly.

## 2. The first evening, in order

1. **Check the machine.** `scripts/workstation/check_machine.sh`. Exit 0 means go; fix every FAIL line first.
2. **Get the pipeline.**
   `git clone https://github.com/AI-DA-STC/AirStack-starling-max2.git ~/AirStack-starling-max2`
3. **Unpack the private bundle** to the same places as on the laptop. Its NOTES name each folder and give the
   sha256 of each archive; check them before unpacking.
4. **Container route.** `docker/build.sh`, then `docker/run.sh '$SVG_PY -m pytest -q'`
   ([GETTING_STARTED](GETTING_STARTED.md) A1–A2).
5. **Host route.** `scripts/workstation/setup_isaaclab_host.sh --dry-run`, read it, then run it without
   `--dry-run`. The first Isaac Sim start asks you to accept NVIDIA's licence.
6. **S0 speed benchmark** (Linear NEAR-959; [GETTING_STARTED](GETTING_STARTED.md) A3–A4). It runs only on a config
   the owner approved (its sha256). More games to fill the 5090's 32 GB is a new config, so it needs his approval
   first (STANDARDS §7).
7. **The remaining S2b Isaac stand-in seeds**: the ones the laptop did not finish. The list and the exact command
   are in [HANDOFF](claude/HANDOFF.md) and `scripts/train_standin.py --help`. Run `scripts/isaac_preflight.sh` first,
   and always headless.
8. **NUS jobs.** `scripts/workstation/setup_nus_jax.sh <NUS folder>`, then `run_nus_job.sh` with the settings in
   the bundle's NOTES. Run them inside `tmux`.

## 3. NUS's code stays private

NUS's code, checkpoints and settings come only from the private bundle. They are never committed to this repository
or pushed to GitHub. That is why `run_nus_job.sh` takes every NUS setting as an argument, and why a test fails if
NUS-specific words appear in these scripts or this page. Their logs go to `~/nus_jax_runs/`, outside the repository.

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
  comes from the laptop's WiFi crashes. Put the PC on Ethernet.

## 6. Rules that still apply

- Headless for every run; check `nvidia-smi` before each one (CLAUDE.md rule 6).
- A training result is not a flight result: write "observed in the training simulator" (CLAUDE.md rule 4).
- Nothing trained here flies until it has passed its gates and the export stage (STANDARDS §3).
