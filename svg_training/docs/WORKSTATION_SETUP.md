# Setting up a training workstation (home PC: RTX 5090, Ubuntu 24.04)

A checklist for moving long training runs off the laptop. The laptop stays the place to build, test and watch
results; the workstation runs long jobs. Nothing here touches AirStack, a drone or the lab network.

Status: PROPOSED (owner, 17 November 2026). Nothing has been installed or run on this PC yet; every value below
marked OPEN is to be checked on the machine.

## 1. Check the machine

| Check | Command | Expect |
|---|---|---|
| GPU and driver | `nvidia-smi` | RTX 5090 listed; driver 580 or newer (the laptop runs 580.178; Isaac Sim 5.1 and JAX with CUDA 13 need a recent driver). OPEN |
| OS | `lsb_release -d` | Ubuntu 24.04. OPEN |
| Disk | `df -h ~` | at least 60 GB free: about 26 GB for NVIDIA's Isaac Lab image, the rest for run folders. OPEN |
| Docker + GPU in containers | `docker run --rm --gpus all ubuntu nvidia-smi` | the same GPU table as above. If it fails, install Docker and the NVIDIA Container Toolkit |

## 2. Get the pipeline

```bash
git clone https://github.com/AI-DA-STC/AirStack-starling-max2.git ~/AirStack-starling-max2
cd ~/AirStack-starling-max2/svg_training
```

Then build and test exactly as on the laptop: [GETTING_STARTED](GETTING_STARTED.md) A1 (`docker/build.sh`) and
A2 (`docker/run.sh '$SVG_PY -m pytest -q'`). Use the container, not a host install: the same image means results
compare with the laptop's.

The Starling model file and the flight logs are not in the container (see the S2b plan, D13). Runs that need them
(Isaac step tests, the drone-model checks) stay on the laptop until they are copied over.

## 3. First run: measure speed (Linear NEAR-959)

The S0 benchmark is the speed test for a new machine: [GETTING_STARTED](GETTING_STARTED.md) A3–A4. Its config
hash must be one the owner approved; a new game count for 32 GB is a new config and needs his approval first
(STANDARDS §7). The result is a run of record with its own ledger row.

## 4. NUS's own training code (optional)

NUS's code is a partner's code: copy it by USB, a private drive or `scp`, never through GitHub or this repository.
Give it its own conda environment, separate from Isaac Lab, and always switch off their W&B logging
(`use_wandb=False`). The laptop's reference runs and their report live outside the repository
(`~/nus_jax_reference/`).

## 5. Getting results back to the laptop

Each run folder under `svg_training/runs/<name>/` holds everything: the policy, TensorBoard logs, scores and
settings. Copy the whole folder back, then score or watch it on the laptop with the usual scripts.

```bash
rsync -av <workstation>:AirStack-starling-max2/svg_training/runs/<name>/ ~/AirStack-starling-max2/svg_training/runs/<name>/
```

`<workstation>` is the PC's address on your network or over Tailscale. Records and ledger rows are written and
committed on the laptop, in the live clone, as always (root CLAUDE.md).

## 6. Working on it from the lab (owner's choice: Tailscale + Ubuntu remote desktop)

- Join the PC and the laptop to the same Tailscale network; use the PC's Tailscale name as `<workstation>` above.
- Ubuntu 24.04: Settings → System → Remote Desktop. "Remote Login" works with nobody logged in at the PC.
- Start long runs inside `tmux` (over SSH or a terminal in the remote desktop), so a dropped connection does not stop
  the run; `tmux attach` to check on it.
- Watch training live in TensorBoard on the PC (`tensorboard --logdir runs/`) through the remote desktop, or forward
  the port: `ssh -L 6006:localhost:6006 <workstation>`, then `http://localhost:6006` on the laptop.

## 7. Rules that still apply

- Headless for runs of record; check `nvidia-smi` before every run (CLAUDE.md rule 6).
- A training result is not a flight result: "observed in the training simulator" (CLAUDE.md rule 4).
- Nothing trained here flies until it has passed its gates and the export stage (STANDARDS §3).
