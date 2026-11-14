---
name: train-run
description: Use when launching a benchmark or a training run. Covers pre-flight checks, gates written first, background launch and monitoring, aborted runs, and the record and ledger row.
---

# Launch and record a run

Do these in order. The run scripts do not exist until build step S0; from then they live in
`scripts/` (benchmark, fit_model, train, evaluate, export) and this skill points at them. Until then,
stop at step 1 and tell the owner.

## 1. Pre-flight
```bash
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv
docker ps --format '{{.Names}}'
```
| Check | Required |
|---|---|
| GPU free | memory used is near zero; no one else's job |
| AirStack simulator | not running; no flight session up |
| `gates.toml` | written and dated before the run, in the run's folder or its plan |
| Seeds | fixed and written down; 3 or more for a method claim |
| Parameter set | the named drone-model set (STANDARDS §5 rule 4) |
| Opponent pool mix | stated (STANDARDS §6.3) |
| Mode | headless, always |

If any row fails, stop and say which.

## 2. Launch in the background
```bash
cd ~/AirStack-starling-max2/svg_training
~/IsaacLab/isaaclab.sh -p scripts/<script>.py --headless <args>   # planned; from build step S0
```
Use the Bash tool's background option so the session stays free. Logs and checkpoints go to
`runs/<date>_<name>/` (not in git).

## 3. Monitor
- Throughput in environment steps per second; a sudden drop means a loop or a sync crept in.
- GPU memory: `nvidia-smi --query-gpu=memory.used,memory.total --format=csv -l 30`.
- NaN or infinite values in observations, rewards and losses; stop at the first one and use `train-debug`.

## 4. Abort or failure
On Ctrl-C, a crash or a NaN, write an ABORTED record at once: what was running, why it stopped, the
last good step. Do not delete the run folder. Do not edit `gates.toml`.

## 5. After the run: record and ledger
- `records/<date>_<name>_record.md`: simulator named in the first line, purpose, commit, config, model
  parameter set, seeds, machine, games at once, steps per second, gates with PASS or FAIL.
- One new row in `records/LEDGER.md`, numbered T1, T2, …, append-only. This folder never writes to the
  flight ledger `docs/record/LEDGER.md`.

## 6. Report throughput in the required form
Environment steps per second, together with the number of games, drones per game, tier and GPU
(STANDARDS §8). Write a FAIL as FAIL. Have `train-gatekeeper` read the record before you call the run done.
