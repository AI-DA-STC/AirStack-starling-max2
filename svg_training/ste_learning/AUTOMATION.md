INTERNAL · reference page of the STE learning track: how the orchestrator launches, watches and ends runs, and where it stops for a person (the state machine, the loop, human gates, budgets and failure handling), from the specialist draft of 20 Nov 2026 · [README.md](README.md); [PLAN.md](PLAN.md) takes precedence where the two differ

From `archive/AUTOMATION_draft.md` (20 Nov 2026); PLAN section 2 lists every change made at integration.

# Automation and orchestration: STE learning track

> **Integration notes (PLAN v2, 20 Nov).** (1) The builder on this track is `ste-software-engineer`; read
> `train-implementer` below as that role. (2) Budgets: phase L0 has one cap of 19 GPU-h (PLAN §4, §9) replacing the
> 3.5 GPU-h step-1 row; L1–L9 budgets are OPEN until gate G0. (3) The heartbeat is a **background timer job** whose
> completion notifies the session (verified by drill); `ScheduleWakeup` below is not relied on. (4) §6 "Needed first" is
> task **L0.7** (shared pause log, status helper, trainer contract, wake-up and resume drills). (5) Gate **G0** (end of
> L0) is the first planned stop.

Work runs unattended through a state machine and stops only at the §3 gates. **A session acts only while alive**:
detached jobs survive it; updates, gates and launches do not. IDs follow `WORK_BREAKDOWN_draft.md`.

## 1. State machine and state file

| State | Meaning → next |
|---|---|
| queued | in the plan, waiting on dependencies or a GPU slot → building (or gate-written if no code) |
| building | `train-implementer`, test-first, in the task's worktree → testing |
| testing | CPU suite + `train-gatekeeper` code read; pass → gate-written, fail → building |
| gate-written | `ste-test-qc-engineer` wrote `gates.toml`, committed before launch → running when §2.2 holds |
| running | detached job alive (pid + start time) → scoring; crash → §5 |
| scoring | QC engineer's verdict (`train-evaluate`), videos rendered → recorded |
| recorded | record, W ledger row, gatekeeper read → documented |
| documented | writer updates HANDOFF, drafts, GIFs → merged (reader pages: blocked-on-human) |
| merged | code and records fast-forwarded into local `development`; the owner pushes |
| paused | owner `gpu_pause.sh` (stat `T`) or own pause → running |
| blocked-on-human | open gate → the state the answer names |
| failed | retries exhausted, ABORTED written → lead re-plans as a new run |

A verdict (PASS/FAIL/INFO/INCONCLUSIVE) is a result, not a failure.

**`ste_learning/status/state.json`** (PROPOSED). Each write: `flock`, temp file, rename. The
technical writer only reads it (its files: `status/STATUS_LATEST.md`, `status/LOG.md`); lead and orchestrator write it.

```json
{ "schema": 1, "updated": "<iso>", "phase": "<current phase>", "boot_id": "<kernel boot_id>",
  "session": { "last_tick": "<iso>", "last_heartbeat": "<iso>", "next_wakeup": "<iso>" },
  "gpu": { "mode": "free|siblings|solo|owner-paused|blocked-sim", "own_pauses": [], "pause_log": "<path>", "disk_free_gb": 256 },
  "budgets": { "<stage>": { "cap_gpu_h": 3.5, "status": "PROPOSED", "log": "<gpu_hours.log>", "used_gpu_h": 0.0 } },
  "tasks": [ { "id": "L0.2", "name": "Step 1a: tier 2 3v3 training speed", "state": "queued", "depends_on": [], "worktree": "<path>",
      "gates": null, "gpu": "solo|sibling|none", "cap_gpu_h": 3.5, "cap_wall_h": 5.0, "attempts": 0,
      "job": { "pid": null, "pid_start": null, "boot_id": null, "cmd_file": null, "run_dir": null, "eta": null },
      "result": { "verdict": null, "record": null, "ledger": null }, "blocked_on": null, "history": [] } ],
  "gates_open": [ { "id": "H-1", "trigger": "H2", "question": "", "options": [], "recommendation": "", "blocks": [], "answer": null } ] }
```

Beside it: `status/RESUME.md` (restart command of every live job, rewritten each tick), `status/decisions.md` (lead's
delegated calls, append-only), `status/gates/H-<n>.md`. **Seed state** = DISCUSSION §3: D4 and P1–P8 open gates; no GPU
task leaves gate-written until its phase is approved (phase L0: approved by the owner on 20 Nov 2026, cap 19 GPU-h).

## 2. The loop

### 2.1 What wakes the lead
1. **Job exit.** Trainers run detached through `scripts/ste_job.py launch` and the lead waits with
   `scripts/ste_job.py wait <name>` as a background command of the session (built in L0.7, §7 below). The waiter's exit
   status is the job's own exit code; it flags ENDED_EARLY and DIED. No `pgrep -f`, no shell `; echo $?` wrappers: both
   failed on 20 Nov (§7).
2. **Heartbeat, 30 min** (ScheduleWakeup, re-armed): a tick, then the **technical writer** gets `state.json` and the
   tick summary and returns the owner's format (DISCUSSION §4: three tables with math library and simulator, Next,
   Waiting on you, "Ready to push"); the lead posts it; writer files per its draft. Finish, failure, new gate: at once.
3. **Fallback**: each job's ETA + 15 min; every 3 h.
4. **Subagent done** (implementer, gatekeeper, writer).

**A tick** = one `ste-orchestrator` run holding `status/tick.lock` (boot_id, time; stale after 10 min), idempotent:
reconcile (boot_id, pid + start time, stat `T`, `exit_code`, log), check the environment, recompute pause-aware
budgets, advance each task at most one state (launch per §2.2), raise gates, write `state.json` and `RESUME.md`,
return an **action list** (spawn, watch pid, wake at T, ask H-n). It cannot schedule wake-ups or spawn agents.

### 2.2 Launching GPU runs safely
All must hold:
- Task gate-written; no open gate blocks it.
- Budget left ≥ the task's cap (the trainer refuses too: `effective_cap_s`, `nus/pilot.py`).
- No AirStack simulator: `sim.sh`'s own test (`docker exec isaac-sim pgrep -f svg_multi_drone_single_domain.py`;
  containers stay up after `down`), no live pid in `~/flight_logs/sim/.sim_test.lock`; the preflight's GPU check decides.
- `scripts/isaac_preflight.sh --approved-headless` exits 0 (`--allow-siblings` for sibling tasks only).
- No open **owner** pause (he is using the PC: wait).
- Disk free ≥ 50 GB.
- Command: `unset PYTHONPATH`, `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, videos on, own run folder.

**Solo vs side by side.** Short pilots and speed measurements (L0.2) run alone (starved runs say nothing). Multi-seed
training shares (memory fraction set; ≥ 8 GB free; ≤ 3 GPU processes, PROPOSED). A solo task next to siblings: wait,
or pause only our own siblings the P1b way (pause by pattern, record in `gpu.own_pauses`, resume in an EXIT trap).
The lead tags such a pause as its own: `GPU_PAUSE_BY=lead GPU_PAUSE_PATTERN='<the siblings' pattern>'
scripts/gpu_pause.sh pause`, and the same two variables for the resume. A tagged pause does not block the solo
launch; an owner pause (a bare `gpu_pause.sh pause`) still does. A resume continues every job its pattern finds and
closes every open pause in the log, so a resume or stop with `GPU_PAUSE_BY=lead` is refused (exit 2, nothing done)
while an owner pause is open (`scripts/ste_job.py owner-pauses` lists them): the owner made it, the owner ends it, and
our siblings wait. The guard is enforced by the script; a bare resume (the owner's) is unchanged. The guard runs
`scripts/ste_job.py`, which needs Python 3.11 or newer: on a machine whose `python3` is older, the lead also sets
`GPU_PAUSE_PYTHON=~/miniconda3/envs/env_isaaclab/bin/python` (otherwise the lead's resume and stop are always refused).

**Pauses.** Stat `T` = paused, not stalled. Never resume a pause we did not make. Simulator appears mid-run: pause
our jobs (recorded), raise H4, resume when it is gone (PROPOSED).

**Unattended chains.** No session, no ticks. For a night or an expected reboot the lead may leave a detached chain
script (`chain2.sh` pattern; `status/chain.log`, registered in `state.json`) holding only gate-written, in-budget
launches; preflight before each step; stop at the first verdict, crash or refusal.

### 2.3 Resume after a reboot or a dead session
New session: `train-start` → `state.json` + `RESUME.md` → one tick in resume mode.
- **New boot_id.** `running` → `paused`. If the pause log ends in a `pause` older than the boot, append
  `{"event":"resume","by":"restart after reboot"}` (otherwise caps never fire). Preflight, then relaunch from
  `cmd.txt`: idempotent (refuses while the pid lives, continues from the checkpoint, appends the log; the interrupted
  segment keeps its GPU-hours line). Jobs without checkpoints (evaluations, Isaac clips) rerun against the same cap.
- **Dead session, same boot.** Adopt live jobs (pid + start time), re-arm watchers; the first report states the gap
  (`now − last_heartbeat`).

### 2.4 Agents at once
One lead; one orchestrator tick (lock); one technical writer per heartbeat; one `train-implementer` per worktree, with
**debugging strictly sequential** (one fix verified before the next, owner memory); read-only advisers in parallel,
briefed with files, not conclusions; GPU jobs side by side under §2.2 (owner memory).

## 3. Human gates

**Stop and ask the owner:**
- **H1 Direction**: a FAIL or INCONCLUSIVE whose plan changes the route (e.g. L0.2 shows tier 2 too slow for D3; L0.6),
  or any result reopening D1–D9.
- **H2 Soundness**, the idea as framed does not hold: a parked Guard team holds ≥ the trained Guard or above its
  control limit under the tag radius (P1 risk); tier-2 transfer collapses beyond the planned gap; self-play still
  cycles or forgets with the pool; the hold depends on Strike drones running our filter (P8); a policy exploits a
  simulator artefact (passing over/under, fence, PhysX bounce); drone loss breaks the shared policy.
- **H3 Rules**: a FIXED `STANDARDS.md` row; rulings P1, P2, P7; gate limits of a run that decides direction (§7.1).
- **H4 Outside `svg_training`**: AirStack change plans; `tools/sim.sh` logs (P5: owner window, empty GPU); the
  simulator found mid-run.
- **H5 Outward**: messages to NUS/CMU (P6), publishing, pushes, large or reader-page doc changes before `main`.
- **H6 Budget**: a stage cap or the track total would be passed; a run needs > 24 h wall clock; disk < 50 GB.
- **H7 NUS** changes direction in a way touching D1 or D8.
- **H8 Stuck**: two ABORTED on one task; `train-debug` not converging in two fix rounds; unknown GPU process > 2 h.
- **H9 Safety**: a finding that matters for real flights; report at once.

**The lead decides alone and records** (`status/decisions.md`, HANDOFF §0; owner delegation, 18 Nov):
hyperparameters, seeds, learner details inside D6, rewards, curriculum, pilots, scheduling, retries, gate limits of
pilots and INFO runs (gatekeeper read), stopping a starved run, bug fixes, commits, local fast-forwards, W→T numbers.

**How a gate is asked**: `status/gates/H-<n>.md` and a block under "Waiting on you" with one plain question; context
in ≤ 5 lines with record links; options A/B(/C), each with its consequence, cost (GPU-h, days) and what it unblocks;
the recommendation and why; what keeps running. No default changes the outcome: an unanswered gate holds only its
branch; everything independent continues; the blocked branch gets CPU-only preparation, no GPU. Heartbeats repeat it.

## 4. Budgets and safety rails

| Item | Value | Status |
|---|---|---|
| Phase L0, all tasks | at most 19 GPU-h; the task caps of [PLAN](PLAN.md) §4 sum to 17.3 (L0.11 0.5, L0.12 13, L0.2 0.4, L0.13 1.6, L0.3 1.3, L0.4 0.2, L0.5 0.3; changed 21 Nov 2026 for L0.12c, 18.5 before); the speed and training probes run alone on the GPU | phase cap FIXED (owner approved L0, 20 Nov 2026); task split PROPOSED by the lead (PLAN §4) |
| Pilots per stage, together | 6 GPU-h | PROPOSED (precedent `configs/nus_phase5.toml [pilots]`) |
| Training stage of record | set in its plan before the first run (5.1 had 36 GPU-h; 5.2 72 GPU-h OPEN) | OPEN |
| Wall clock per job | cap × 1.5, pauses excluded; SIGINT at cap + 30 min | PROPOSED (P1b overrun rule) |
| Starvation guard | progress check at launch + 45 min | PROPOSED (P1b) |
| Disk | 256 GB free on `/` (86 % used, 20 Nov); no launch below 50 GB; keep last, best, archived checkpoints | MEASURED / PROPOSED |
| GPU sharing | ≤ 3 processes, ≥ 8 GB free | PROPOSED (`isaac_preflight.sh`) |

GPU-hours are pause-aware: `nus/pauses.py` `logged_gpu_hours`, one `gpu_hours.log` per stage.

**Never**: push, `git add -A`, `--no-verify`, stash; write outside `svg_training/`; break a §2.2 rule; kill a process
not ours, or SIGKILL ours (SIGINT checkpoints); launch windowed; edit gates after a result; delete a run folder;
message outsiders; change a FIXED row; commit NUS source; use the GPU before P3 is approved.

## 5. Failure handling

| Failure | Rule |
|---|---|
| Preflight refused, owner pause | not a failure; re-check each tick; foreign process > 2 h → H8 |
| Crash, OOM | one retry from the checkpoint (OOM: lower memory fraction); second → ABORTED |
| NaN/Inf (STE track trainers: exit 5; `train_standin.py`: exit 3) | no retry; ABORTED; `train-debug`, sequential |
| A control failed (exit 6, CONTROL_FAILED; `scripts/ste_sweep_l011.py`, `scripts/ste_exploit_l012.py`) | terminal: never retried, not a refusal; the lead reads `controls.json` and `results.md`; ABORTED; a rerun is a new run folder (and a new gate version if the gate was wrong) |
| Stall (log and CPU time unchanged 30 min, not `T`; PROPOSED per task) | SIGINT, ABORTED, `train-debug` |
| Reboot | resume (§2.3); not an attempt |
| Gate FAIL / INCONCLUSIVE | recorded, never retried; a rerun is a new run with new gates (INCONCLUSIVE: as its plan says) |

**ABORTED** is written at once (what ran, why it stopped, last good step, GPU-hours); the run folder stays.

## 6. Needed first (outside these two files)
Items 1 and 2 were built in L0.7 (20 Nov 2026); see §7. Kept for the record:
1. **One pause log.** `gpu_pause.sh` and `nus/pauses.py` use `<worktree>/runs/nus_port/phase5/pauses.log`, and the
   owner runs the nus-method copy. Proposal: one shared path, STE trainer names in `GPU_PAUSE_PATTERN`. Implementer task.
2. **Trainer contract**: the same command resumes from its checkpoint; SIGINT checkpoints; distinct exit codes for
   done, cap-stop, NaN. A tested `status` helper (lock, atomic write, boot_id, pid start time).
3. The lead's task list with IDs.

## 7. The tooling as built (task L0.7, 20 Nov 2026)

Code: `source/svg_training/ste/` (`shared.py`, `pauses.py`, `state.py`, `atomic.py`, `run_contract.py`, `budget.py`,
`jobs.py`, `post_run.py`), `scripts/ste_job.py`, `scripts/ste_dummy_job.py`, `scripts/gpu_pause.sh`. Tests: `tests/test_ste_*.py`,
`tests/test_gpu_pause.py`. Linux only. Standard library only.

| Piece | What it does |
|---|---|
| Shared folder | `SVG_SHARED_DIR`, else `<main clone>/svg_training/runs/shared/` (git-ignored, one per machine): `state.json`, `pauses.log`, `gpu_hours.log` |
| One pause log | `gpu_pause.sh` writes each event to the legacy log and to the shared one; the reader merges every worktree's legacy log too, so a pause made with an old copy still counts; `scripts/ste_*.py` jobs are paused, the launcher and waiter are not |
| State file | `state.json` under a lock, written atomically; a job is alive only if its pid exists with the recorded start time in the current boot |
| Trainer contract | the same command resumes from its last checkpoint; SIGINT or SIGTERM saves and exits; a non-finite value never overwrites the last good checkpoint; the cap counts effective time (time a pause stopped this job excluded) |
| GPU-hour ledger | used GPU-hours per task and per phase from `gpu_hours.log` (CUDA intervals less the time a pause stopped that job); `launch` refuses a job over the task or phase cap of `configs/ste_learning.toml`; a relaunch of the same job in the same run folder is not charged again for hours it already logged, but a new run folder under an old job name is a new run and gets no credit |
| Launcher and waiter | `scripts/ste_job.py launch / wait / status`; `launch` refuses while an owner pause is open (a pause tagged `GPU_PAUSE_BY=lead` is the session's own and does not block); `bash <run>/cmd.txt` relaunches with the first launch's `PYTHONPATH`, `CUDA_VISIBLE_DEVICES`, `PYTORCH_CUDA_ALLOC_CONF`, `SVG_SHARED_DIR` and `SVG_PAUSE_LEGACY_LOGS`, each set to the same value or unset as it was; a relaunch with another shared folder than the run folder recorded is refused |
| Post-run 3-D clips (L5) | `launch --post-clips3d` (put it on every L5 training launch line): when the command exits 0 and its run folder holds a complete `results.json` and `agent_final.pt`, the wrapper launches `scripts/ste_l5_clips3d.py --run-dir <run>` as its own job `clips3d_<job>` (run folder `<run>/videos3d`, the run's task cap, `--gpu-h 0.1`, `--min-s 30`; ledger rows like any GPU job). It never waits and never changes the run's exit code: an open owner pause, a busy GPU (preflight) or the cap leave `pending` in `<run>/videos3d/HOOK_STATUS` with the retry line `scripts/ste_job.py post-clips3d --run-dir <run>`; `status` shows `clips3d=<state>`. Code: `ste/post_run.py`; tests: `tests/test_ste_post_clips3d.py` |

**Exit codes** (`ste/run_contract.py`): 0 done; 2 refused to start; 3 stopped at its cap; 4 interrupted (SIGINT or
SIGTERM); 5 non-finite value; 6 a control with a known answer failed (CONTROL_FAILED: terminal, never retried; a
relaunch on the same run folder ends with 6 again; LEAD CALL 21 Nov 2026, L0.11). The waiter adds: 20 ENDED_EARLY (the job returned 0 before its expected minimum
duration); 21 DIED (no exit code recorded: killed, or a previous boot); 22 no such job; 23 the tool itself failed.
127: the command could not start; 128 + n: killed by signal n.

**The three failures of 20 Nov this replaces**, each reproduced by a test and shown caught: a watcher written with
`pgrep -f` matched its own shell and never fired; `pytest … ; echo "exit $?"` reported 0 for a run with 463 errors; and
that run ended after 3 minutes instead of 19 with nothing flagging it.

**Drills: run them on each machine before its first detached GPU job.** From the `svg_training` folder of the clone
the work is in, `unset PYTHONPATH` first. They use the machine's real shared folder.
**Task ID:** phase L0 is closed (G0, 22 Nov 2026), so `--task L0.7` below is now refused (exit 2, the closed-phase
check). Run the drills under the current phase's machine-check task instead (on the RTX 5090, 23 Nov 2026: `--task L1.0`,
`--gpu-h 0`), with the names and run folders changed to match; the expected lines are otherwise the same.

Wake-up drill (about 2 minutes):
```
PY=~/miniconda3/envs/env_isaaclab/bin/python; mkdir -p runs
$PY scripts/ste_job.py launch --task L0.7 --name l07_wakeup --run-dir runs/ste_l07/wakeup --min-s 100 --gpu-h 0 -- \
    $PY scripts/ste_dummy_job.py --run-dir runs/ste_l07/wakeup --steps 120 --step-s 1 --cap-s 600 --checkpoint-every 10
```
Then, as a background command of the session (its completion is the wake-up):
`$PY scripts/ste_job.py wait l07_wakeup; echo "waiter exit $?"`. Expected about 120 s after the launch:
`L0.7 l07_wakeup DONE exit=0 duration=120.1s effective=120.1s`, then `waiter exit 0`.

Resume drill:
1. Launch: the same line as above with `l07_resume` and `runs/ste_l07/resume` (and `--min-s 60`).
2. About 40 s later, in a separate command: `$PY scripts/ste_job.py status`; then kill the whole job (the power-cut
   stand-in) with `kill -KILL -- -<pid>`, where `<pid>` is the `pid` in `runs/ste_l07/resume/job.json`; then `status`
   again. Expected: `alive`, then `dead`.
3. `$PY scripts/ste_job.py wait l07_resume; echo "waiter exit $?"`. Expected: `DIED exit=none`, `waiter exit 21`.
4. Relaunch with `bash runs/ste_l07/resume/cmd.txt` (it restores the first launch's environment and shared folder; the same line typed again works only from the same shell): it prints `launch=2`. Wait again. Expected:
   `DONE exit=0 … run_effective≈120s`, `waiter exit 0`, a log line `resumed from step 30 of 120` (or 40), and
   `{"steps": 120, "total": 7260.0}` in `runs/ste_l07/resume/result.json`.

Do not pause during a drill while a real GPU job runs: `gpu_pause.sh pause` pauses every job it finds.

**Known limits (L0.7 as built).** `launch` refuses (exit 2) while an owner pause is open, even one that stopped no
job; only the owner ends it, with `gpu_pause.sh resume`. Only a pause the lead tagged `GPU_PAUSE_BY=lead` (§2.2) does
not block; an untagged line counts as the owner's. A pause takes time off a job only if the pause line lists the
job's command pid. A pause that stopped only a process the command started (a trainer behind `bash -c`) is not matched:
that job is charged the paused time, the safe side. `--gpu-h` at launch and the trainer's own cap are not linked: the caller keeps them equal. The effective time
carried in a checkpoint undercounts by up to one checkpoint interval per SIGKILL; the ledger loses at most one minute.
A failed write of the wrapper (a full disk, any error) does not end it: it is retried at the next beat, and `wait`
and `status` show `faults=<n>` (details in `job.json` and `job.log`). After a backward step of the wall clock the
wrapper logs nothing until the clock catches up, so the GPU time of the step itself is not counted.
A resumed trainer is judged against `--min-s` on its whole run, the effective time it saved with its checkpoints
(`progress.json`, shown as `run_effective`), so a correct finish after a relaunch reads DONE; a command that saves no
checkpoint is still judged on its last launch alone. The `tasks` block of `state.json` is
validated but not yet written; `RESUME.md`, the wall-clock limit, the starvation guard and the disk check are not built.
**The shared folder is per machine**: the GPU-hours used on the 5090 and on the laptop are counted separately, so the
phase total is kept by hand in the status (`status/STATUS_LATEST.md`, "GPU-h used in L0") until the ledgers are merged.
