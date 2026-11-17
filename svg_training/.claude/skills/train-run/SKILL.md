---
name: train-run
description: Use when launching a benchmark or a training run. Covers pre-flight checks, gates written first, background launch and monitoring, aborted runs, and the record and ledger row.
---

# Launch and record a run

Do these in order. The S0 benchmark's front door is `scripts/run_s0.sh` (in the container:
`docker/run.sh 'bash scripts/run_s0.sh <name> <approved config sha256>'`); later steps add their own
scripts under `scripts/` (fit, train, evaluate, export). A script that does not exist yet: stop and tell
the owner.

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
**Videos are on for every run** (STANDARDS §8): pass the trainer's video option at launch (Isaac Lab `--video`;
NUS's JAX code `save_eval_gif=True` and its own `hydra.run.dir`), headless, into `runs/<date>_<name>/videos/`.

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
- Videos: at least two evaluation games from the final and the best checkpoint (render them now if the run
  did not); list the paths in the record, or say why there are none.
- One new row in `records/LEDGER.md`, numbered T1, T2, …, append-only. This folder never writes to the
  flight ledger `docs/record/LEDGER.md`.
- Linear: if the run finishes or changes the state of an issue (NEAR-nnn in the newest
  `docs/linear/snapshots/` file), write an instruction file in `docs/linear/updates/` as
  `docs/linear/README.md` says: status and one comment citing "ledger row Tn" and the record; ask for a record
  named `YYYY-MM-DD-linear-sync-record.md`. Owner's rules: no cycles, no due dates, every issue assigned to the
  owner, "Done when" lines are targets; never the partner's confidential numbers. The owner uploads it; save the
  record he brings back in `synced/` and, if a status changed, write a new snapshot.

## 6. Report throughput in the required form
Environment steps per second, together with the number of games, drones per game, tier and GPU
(STANDARDS §8). Write a FAIL as FAIL. Have `train-gatekeeper` read the record before you call the run done.
