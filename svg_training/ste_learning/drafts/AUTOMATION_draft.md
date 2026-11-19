INTERNAL · DRAFT (automation engineer, 20 Nov 2026). The owner's word and `ste_learning/DISCUSSION_2026-11-19_20.md` win over this page.

# Automation and orchestration: STE learning track

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
| merged | code and records fast-forwarded into local `main`; the owner pushes |
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
task leaves gate-written until P3 (step 1, ~3 GPU-h) is approved.

## 2. The loop

### 2.1 What wakes the lead
1. **Job exit.** Trainers run detached: `setsid nohup bash -c '<cmd>; echo $? > <run>/exit_code'`, with `pid`, `cmd.txt`
   and log in the run folder (`restart_51.sh`). A session-attached watcher (`while kill -0 <pid>; do sleep 60; done`,
   Bash background) wakes the lead; a dead session loses only it. Dead pid, no `exit_code` = killed or rebooted.
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
| Step 1, L0.2 + L0.3 (tier-2 speed, zero-shot transfer) | 3.5 GPU-h, solo | PROPOSED (DISCUSSION P3: ~3 GPU-h) |
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
| NaN/Inf (trainer exit 3) | no retry; ABORTED; `train-debug`, sequential |
| Stall (log and CPU time unchanged 30 min, not `T`; PROPOSED per task) | SIGINT, ABORTED, `train-debug` |
| Reboot | resume (§2.3); not an attempt |
| Gate FAIL / INCONCLUSIVE | recorded, never retried; a rerun is a new run with new gates (INCONCLUSIVE: as its plan says) |

**ABORTED** is written at once (what ran, why it stopped, last good step, GPU-hours); the run folder stays.

## 6. Needed first (outside these two files)
1. **One pause log.** `gpu_pause.sh` and `nus/pauses.py` use `<worktree>/runs/nus_port/phase5/pauses.log`, and the
   owner runs the nus-method copy. Proposal: one shared path, STE trainer names in `GPU_PAUSE_PATTERN`. Implementer task.
2. **Trainer contract**: the same command resumes from its checkpoint; SIGINT checkpoints; distinct exit codes for
   done, cap-stop, NaN. A tested `status` helper (lock, atomic write, boot_id, pid start time).
3. The lead's task list with IDs.
