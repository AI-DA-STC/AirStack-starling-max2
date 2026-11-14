---
name: train-start
description: Run at the start of every session on the svg_training pipeline, before any edit, question or investigation. Loads the rules and state, checks the working copy and the GPU, and sets how the session is run.
---

# Start a session on the training pipeline

Do these in order. Do not skip because the task looks small.

## 1. Read the rules and the state
1. `CLAUDE.md` of the folder (hard rules, environment, git facts).
2. `STANDARDS.md`: §1 scope, §2 wording, §7 gates, §8 records, §10 git, §11 definition of done. Read
   §3 to §6 and §9 as well if the task touches the interface, the game, the drone models or code.
3. `docs/claude/HANDOFF.md` §4 (current state) and §5 (open items). Something you are about to "fix"
   may already be a recorded decision or a question waiting on the owner.

## 2. Check the working copy
```bash
git -C ~/AirStack-starling-max2 status -sb
git -C ~/AirStack-starling-max2 worktree list
find ~/AirStack-starling-max2/svg_training -type f -mmin -30
pwd    # must be ~/AirStack-starling-max2/svg_training so the agents and skills load
```
Files you did not create belong to another session: leave them alone and tell the owner what you saw.
The folder is tracked since 14 November 2026 (STANDARDS §10); `runs/` is git-ignored.

## 3. Check the GPU
```bash
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv
docker ps --format '{{.Names}}'     # a running AirStack simulator shares this GPU
```
If the AirStack simulator or a flight session is up, no GPU job starts (CLAUDE.md rule 6).

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
