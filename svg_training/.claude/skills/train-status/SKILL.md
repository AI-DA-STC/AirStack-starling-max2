---
name: train-status
description: Produce the owner's status update for the training work (STE's own learning track and the NUS port) in the fixed three-table format, without being asked. Use at the start of every session (train-start calls it), every 30 minutes while work runs, at once on an event (a job ends, a verdict, a failure, a human gate), and whenever the owner asks "status" or "where are we".
---

# The owner's status update

The owner works on two machines in turn (the home RTX 5090 and the RTX 5070 Ti laptop) and starts new sessions often.
The status must never depend on this session's memory or on the owner asking for it: everything below comes from
committed files and commands run now.

## When
- **Session start:** as the first message, right after `train-start` has read the state. Say which machine.
- **Every 30 minutes while anything runs or is being built:** arm a background timer command of the session
  (`sleep 1800; echo HEARTBEAT`) and re-arm it each time it fires. Stop it when the session ends work.
- **At once on an event:** a job ends (the `scripts/ste_job.py wait` command returns), a gate verdict, a failure, a
  human gate reached, a merge.
- **When asked.**

## Gather (run these; never fill a cell from memory)
```bash
date "+%Y-%m-%d %H:%M"; hostname
nvidia-smi --query-gpu=name,utilization.gpu,power.draw,memory.used,memory.total --format=csv,noheader
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader
cd <svg_training folder of the clone or worktree in use>; unset PYTHONPATH
~/miniconda3/envs/env_isaaclab/bin/python scripts/ste_job.py status      # detached jobs: alive / dead, exit codes
git status -sb; git rev-parse --abbrev-ref HEAD; git log --oneline -5
git rev-list --left-right --count HEAD...@{upstream} 2>/dev/null       # ahead / behind the branch's own upstream
```
On the 5090 also the mirror GitHub Desktop pushes from: `git -C ~/Documents/GitHub/AirStack-starling-max2 status -sb`.
Then read: `ste_learning/status/STATUS_LATEST.md` (the last status), `docs/claude/HANDOFF.md` §0 (top entries),
`ste_learning/PLAN.md` §3–§4 (phase and task IDs and names), and for NUS port rows `docs/claude/HANDOFF.md`
(Phase 5 task IDs) and `docs/NUS_PORT_REPORT.md` "At a glance".

## Write it in exactly this shape
Header line: `**Status, <YYYY-MM-DD HH:MM> (+08:00)** · <machine: RTX 5090 or laptop RTX 5070 Ti> · GPU <util %> / <W> /
<used GB of total> · <n> training processes (<n> paused)`; an event update adds `event: <what>` after the time.

1. **`## Phases`**: `| Phase | Status | Math library | Simulator | What |`, every phase of both projects, current one
   marked ▶. The NUS port first, as its phase groups (Phases 1–4; Phase 5 and its state; Phase 6 docs), then STE's
   L0 to L9. Math library: `PyTorch`, `JAX (NUS)` or `none`. Simulator: `NUS 2-D game (JAX)`, `Copy of NUS 2-D game
   (PyTorch)`, `tier 1 fast engine`, `tier 2 Isaac Lab`, `AirStack simulator`, `real flight`, or `none`.
2. **`## Phase <ID> <plain name>, task by task`**: `| ID | Plain name | Status | Simulator | Result / ETA |`, every task
   of the current phase, pilots, controls and side tasks included. Under it: `GPU-h used in L0 so far: <x> of 19`
   (sum of every machine's ledger; the shared folder `runs/shared/` is per machine, so carry the other machine's
   total from the last status and say which part is from where).
3. **`## Other workstreams`**: `| ID | Plain name | Status |`: docs, videos, reviews, QC, NUS follow-up, AirStack plans.

Then three lines:
- **Next.** One to three actions, each "ID + plain name", with what triggers them.
- **Waiting on you.** Numbered owner decisions with their IDs and what each blocks; "nothing" if none.
- **Ready to push.** Only while the branch in use is ahead of its own upstream: `<n> commits on <branch>, <mirror
  updated / not>; push from GitHub Desktop.` and one line on what they hold. Compare with the branch's upstream, never
  with `main` by habit. Drop the line once pushed.

Rules (the same as `ste_learning/status/STATUS_TEMPLATE.md`): tasks are always "ID + plain name", IDs from PLAN.md or
HANDOFF, never invented; status words DONE, RUNNING, PAUSED, QUEUED, BLOCKED, WAITING, NOT STARTED, PASS, FAIL, INFO,
ABORTED (PASS / FAIL / INFO only against gates written before the run); an ETA only from a measured rate; cells one line,
detail under the table; no number without a source.

## File it
Overwrite `ste_learning/status/STATUS_LATEST.md` (its first line stays the INTERNAL banner) and append the same text
under a `## <date time>` heading to `ste_learning/status/LOG.md` (sub-headings one level down). Commit both with the
session's work on its branch at the end of the session, with `docs/claude/HANDOFF.md` §0 (CLAUDE.md, "How a session
runs"). Then paste the status into the chat.
