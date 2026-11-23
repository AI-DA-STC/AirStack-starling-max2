---
name: train-start
description: Run at the start of every session on the svg_training pipeline, before any edit, question or investigation. Loads the rules and state, checks the working copy and the GPU, and sets how the session is run.
---

# Start a session on the training pipeline

Do these in order. Do not skip because the task looks small.

## 0. Bring the branch up to date
The owner works on two machines in turns (CLAUDE.md, "Two machines, one working branch"). Before anything else:
`git fetch origin`, then `git status -sb` on `development` (or the work branch). Behind: fast-forward. Diverged:
stop and ask the owner. Never start work on a stale branch.

## 1. Read the rules and the state
1. `CLAUDE.md` of the folder (hard rules, environment, git facts).
2. `STANDARDS.md`: §1 scope, §2 wording, §7 gates, §8 records, §10 git, §11 definition of done. Read
   §3 to §6 and §9 as well if the task touches the interface, the game, the drone models or code.
3. `docs/claude/HANDOFF.md` §4 (current state) and §5 (open items). Something you are about to "fix"
   may already be a recorded decision or a question waiting on the owner.
4. `docs/linear/README.md` and the newest file in `docs/linear/snapshots/`: which Linear issues (NEAR-nnn) are In
   Progress, so the work and the Linear status stay in step.
5. For NUS work: `docs/NUS_PORT_REPORT.md` (phases, settings, results) and `docs/TRAINING.md` "NUS jobs" (commands).

Know which machine you are on (`hostname`; `nvidia-smi` shows RTX 5070 Ti on the laptop, RTX 5090 on the workstation).
**5090 only, never assume them on the laptop:** `~/ma_skills-self-play/` (NUS's code, the private plan and notes, NUS's
outputs, copies of these agents and skills), `~/nus_jax_runs/`, conda `nus_jax`, and Phase 4/5 run outputs under
`runs/nus_port/`. `configs/local/nus_*.toml` and the NUS weights, starts and recordings come on any machine from
`scripts/nus_install_provisional.sh` (the committed PROVISIONAL bundle). On the laptop, NUS's results are in `docs/NUS_PORT_REPORT.md` and `records/`. Claude's user memory (`~/.claude/`)
does not travel with git: the committed files are the state.

## 2. Check the working copy
```bash
git status -sb                                  # in the worktree on development (~/AirStack-starling-max2-dev)
git -C ~/AirStack-starling-max2 worktree list
find . -type f -mmin -30 -not -path './runs/*'
pwd    # must be the svg_training folder of the clone or worktree you work in, so the agents and skills load
echo $PYTHONPATH    # a path under /opt/ros (the 5090) means: unset PYTHONPATH before any env_isaaclab or nus_jax command
```
Files you did not create belong to another session: leave them alone and tell the owner what you saw.
The folder is tracked since 14 November 2026 (STANDARDS §10); `runs/` is git-ignored.

## 3. Check the GPU
```bash
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv
docker ps --format '{{.Names}}'     # a running AirStack simulator shares this GPU
```
If the AirStack simulator or a flight session is up, no GPU job starts (CLAUDE.md rule 6). Another process holding
more than 1024 MiB (a NUS JAX job, another run) also blocks Isaac (`scripts/isaac_preflight.sh`) and NUS jobs
(`run_nus_job.sh`); the 5090's remote-desktop daemon (546–589 MiB) does not.

## 4. Say what you intend before doing it
One short message: what you understood, which files change, what stays untouched, how you will
verify. If an open item in HANDOFF §5 blocks the task, say so and ask the owner. Then start.

## 5. Pick the skill for the task
| Task | Skill |
|---|---|
| Edit code, a config or a document in this folder | `train-change` |
| Launch a benchmark or a training run | `train-run` |
| Score a checkpoint against the gates | `train-evaluate` |
| Something is wrong: NaN, flat reward, slow, unstable | `train-debug` |
| Hand a policy to AirStack | `train-export` |
| A design question | brief the advisers in parallel (see `docs/claude/AGENTS_AND_SKILLS.md`) |
| A status update | `train-status` |

## 6. Post the status
End the start-up with the `train-status` skill: the owner's three-table status, posted without being asked, and the
30-minute timer armed if anything runs or is being built.
