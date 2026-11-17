# Working with a training workstation (home PC: RTX 5090, Ubuntu 24.04)

How to move long training runs off the laptop (RTX 5070 Ti). The laptop stays the place to build, test, record and
commit; the workstation runs long jobs. Nothing here touches AirStack, a drone or the lab network.

Setting up either machine is in [GETTING_STARTED](GETTING_STARTED.md) steps 1–7, with a laptop and a 5090 column
at each step. This page holds what is about a second machine: pushing first, the private bundle, the NUS scripts,
bringing results back, remote access, the 5090's record (§2a) and the OPEN preflight decision (§2c).

Status (17 November 2026): the scripts in `scripts/workstation/` were written on the laptop and checked there with
`bash -n` and `--dry-run`. On the 5090, `check_machine.sh` ran (0 failed, 2 warnings) and `setup_isaaclab_host.sh`
stopped with exit 1; hand fixes finished the host route, and the full test suite passes there (MEASURED). Isaac
preflight refuses on the 5090: an OPEN owner decision (§2c). The container, the NUS scripts, `sync_results.sh` and every
training or benchmark run have not run on the 5090 yet.

## 0. Before you leave the laptop: push first

The workstation clones from GitHub, so GitHub must have the work. On 17 November 2026 the live clone was 301
commits ahead of GitHub, and the repository carries about 41 MB of video and GIF clips.

1. Bring the mirror up to date: `git -C ~/Documents/GitHub/AirStack-starling-max2 pull ~/AirStack-starling-max2 main`.
2. Push `main` from GitHub Desktop. Claude never pushes.
3. Copy the private bundle (`~/svg_workstation_bundle/`: the partner's code and checkpoints, the flight logs) and the
   construction-site world to the workstation: how and where, [GETTING_STARTED step 3](GETTING_STARTED.md#3-copy-the-files-that-are-not-in-git).

## 1. The scripts

All five print their steps; `--help` explains each, and `--dry-run` prints what would run without running it. Run
them from the pipeline folder: `cd ~/AirStack-starling-max2/svg_training`, then `scripts/workstation/<name>`.

| Script | When | What it does | On the 5090, 17 Nov 2026 |
|---|---|---|---|
| `check_machine.sh` | first, on any new machine | checks the machine: [GETTING_STARTED step 2](GETTING_STARTED.md#2-check-the-machine) | ran (step 2) |
| `setup_isaaclab_host.sh` | once, for the host route | builds `env_isaaclab` and `~/IsaacLab`: [GETTING_STARTED step 5](GETTING_STARTED.md#5-the-host-route-part-b) | ran: exit 1, then hand fixes (step 5) |
| `setup_nus_jax.sh <folder>` | once, for NUS jobs | a separate conda env `nus_jax` (Python 3.12) for NUS's code, then their CPU tests | not run yet |
| `run_nus_job.sh` | each NUS job | starts the job in the background with a log; cloud logging off; JAX takes at most 60 % of GPU memory by default (PROPOSED; the laptop used 30 % beside other runs) | not run yet |
| `sync_results.sh <pc> <run>` | on the laptop, after a run | copies `runs/<run>/` back, plus the workstation's record and ledger for you to copy by hand | not run yet |

## 2. The first evening, in order

1. **Push first** (§0) and copy the private bundle.
2. **Set up the machine:** [GETTING_STARTED](GETTING_STARTED.md) steps 1–7, the 5090 column.
3. **S0 speed benchmark** (Linear NEAR-959): [GETTING_STARTED, the S0 benchmark](GETTING_STARTED.md#the-s0-benchmark).
   It runs only on a config the owner approved (its sha256). More games to fill the 5090's 32 GB is a new config, so
   it needs his approval first (STANDARDS §7). Not run on the 5090 yet.
4. **The remaining S2b Isaac stand-in seeds**: the ones the laptop did not finish. The list and the exact command
   are in [HANDOFF](claude/HANDOFF.md) and `scripts/train_standin.py --help`. They start with preflight, which
   refuses on the 5090 today (§2c). Always headless.
5. **NUS jobs.** `scripts/workstation/setup_nus_jax.sh <NUS folder>`, then `run_nus_job.sh` with the settings in
   the bundle's NOTES. Run them inside `tmux`. Not run on the 5090 yet.

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

**Not run on the 5090 yet:** the container (`docker/build.sh`, `docker/run.sh`); `run_s0.sh`; `train_standin.py`;
`score.py`; the step tests; `fit_real_px4.py`; `setup_nus_jax.sh`, `run_nus_job.sh`, `sync_results.sh`; any launch
with the Isaac Sim window; TensorBoard. The private bundle, the flight logs and the construction-site world are not
copied yet.

## 2c. Preflight on the 5090 (OPEN: owner decision)

`scripts/isaac_preflight.sh` checks the machine before an Isaac launch. On the 5090 (MEASURED, 17 November 2026):

| Command | Exit | Cause |
|---|---|---|
| `scripts/isaac_preflight.sh` | 10 | WiFi only, with remote-desktop programs running (§2a) |
| `scripts/isaac_preflight.sh --approved-headless` | 11 | WiFi becomes a warning, but the GPU counts as in use: gnome-remote-desktop-daemon holds 546 MiB, over the 500 MiB limit. It is not a simulator or a flight session |

The owner's approval the script cites (16 November, "yes dont worry about wifi") was given for the laptop. Whether
it covers the 5090 is the owner's call. As the PC stands, the seed commands in [HANDOFF §5a](claude/HANDOFF.md)
stop at exit 11, because they start with preflight.

Options for the owner (OPEN):

- Put the PC on Ethernet and end the remote-desktop session before a run.
- Change the preflight rule or its 500 MiB limit. That is a script change, made on the laptop.

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
  comes from the laptop's WiFi crashes. On the 5090 it refuses even with `--approved-headless`: see §2c (OPEN).

## 6. Rules that still apply

- Headless for every run; check `nvidia-smi` before each one (CLAUDE.md rule 6).
- A training result is not a flight result: write "observed in the training simulator" (CLAUDE.md rule 4).
- Nothing trained here flies until it has passed its gates and the export stage (STANDARDS §3).
