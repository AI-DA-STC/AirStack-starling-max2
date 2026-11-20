INTERNAL · the latest status of STE's own learning track and the NUS port, overwritten at every update; the history is in [LOG.md](LOG.md). Produced by the `train-status` skill.

**Status, 2026-11-21 02:33 (+08:00), event: L0.10 built; lead's rulings round running**                           · laptop RTX 5070 Ti · GPU 72 % / 22 W / 1.7 GB of 12 GB · 0 training processes (0 paused)

## Phases

| Phase | Status | Math library | Simulator | What |
|---|---|---|---|---|
| NUS port Phases 1–4 | DONE | JAX (NUS), PyTorch | NUS 2-D game (JAX), Copy of NUS 2-D game (PyTorch), tier 2 Isaac Lab | NUS's code installed, game and policies copied to PyTorch, six tests towards STE drones |
| NUS port Phase 5 | PAUSED (lead call D8) | PyTorch | Copy of NUS 2-D game (PyTorch), tier 1 fast engine | 5.1 Method match FAIL (T43); STE Guard policy 829 of 1,000 (T41) |
| NUS port Phase 6 | DONE | none | none | public documents with videos |
| ▶ L0 Game definition and feasibility | RUNNING (approved 20 Nov, cap 19 GPU-h) | PyTorch | tier 1 fast engine, tier 2 Isaac Lab | which game, worth learning, can tier 2 train, is the Crazyflie route sound |
| L1–L8 | NOT STARTED | PyTorch | as ruled at gate G0 | drone model, rules, learner, evaluation, league, export, AirStack side, real flight |
| L9 Documentation | RUNNING | none | none | status, records, results page |

## Phase L0 Game definition and feasibility, task by task

| ID | Plain name | Status | Simulator | Result / ETA |
|---|---|---|---|---|
| L0.1 | Track set-up: config and test skeleton | DONE | none | settings file, loader, tests; independent QC closed all findings |
| L0.7 | Process tooling and drills | RUNNING (laptop part DONE) | none | merged into `development`; laptop: full suite 1,420 passed / 0 failed, wake-up drill and resume drill both as expected (below); DONE when the 5090 has run the same (L07-5090) |
| L0.8 | Game spec sheet | DONE | none | merged into `development`; QC passed; full suite on `development` 1,461 passed / 0 failed (41 min) |
| L0.9 | Tag rule for the study: 1-for-1, nearest pair first | RUNNING | tier 1 fast engine | merged into `development` (QC passed); full suite re-running; DONE when it passes (the 5090 records its own tag-off positions, L09-5090) |
| L0.10 | Scripted players for the study | RUNNING | tier 1 fast engine | built (6 new players + start ring 2.75 m, checked on 8,192 games: inside the arena, ≥ 1.95 m from Guards, no tag at the first step); lead's rulings on 10 open points being applied; then QC |
| L0.11 | Screening sweep (INFO) | NOT STARTED | tier 1 fast engine | cap 3 GPU-h |
| L0.12 | Best-response test: is the game worth learning? | NOT STARTED | tier 1 fast engine | cap 6 GPU-h |
| L0.2 | Tier 2 speed in contested play | NOT STARTED | tier 2 Isaac Lab | 5090; cap 1.5 GPU-h |
| L0.13 | Does tier 2 train at all? | NOT STARTED | tier 2 Isaac Lab | 5090, after L0.2; cap 6 GPU-h |
| L0.3 | STE Guard policy in tier 2 without retraining | NOT STARTED | tier 2 Isaac Lab | T41 policy in the bundle (installed on the laptop too); cap 1.5 GPU-h |
| L0.4 | Side-by-side Starling render | NOT STARTED | tier 2 Isaac Lab | cap 0.2 GPU-h |
| L0.5 | Starling video look fix | NOT STARTED | tier 2 Isaac Lab | after L0.4; cap 0.3 GPU-h |
| L0.14 | Crazyflie route check | NOT STARTED | tier 1 fast engine (CPU) | T41 policy installed on the laptop; cap 0 GPU-h |
| L0.6 | Gate G0 | NOT STARTED | none | after every task above; the owner decides |

GPU-h used in L0 so far: 0 of 19 (RTX 5090: 0, from the 22:20 status; laptop: 0, no job launched).

Laptop full CPU suite (20 Nov, `development` at 5c5d465, after `scripts/nus_install_provisional.sh`): **1,333 passed, 2 failed, 48 skipped** in 24 min. Both failures repeat when run alone:
- **L07-F1** `test_ste_job.py::test_f_d_a_killed_job…resumes`: CONFIRMED by QC: the tool does not over-report (it measures from the same start; ~0.255 s raw, printed rounded to 0.3); the test compares the rounded text with the exact elapsed time. Fix: allow half a display step.
- **TEST-F2** `test_train_standin.py::test_default_path_bit_identical_after_the_nus_hooks`: FIXED (447b317). Measured on the laptop: the hash repeats (75d2a955…), hold rates equal the recorded [0.25, 0.375], and forcing PyTorch's CPU capability down changes the hash; threads (trainer runs one) and local files (not read on this path) ruled out. The fingerprint is now one hash per CPU capability; hold rates are checked on every machine.

## Usage (laptop session, 20 Nov 22:00 to now)

| What | Agent tokens | Wall time | Note |
|---|---|---|---|
| L0.7 fixes: builder, 7 fixes one at a time | ~400 k | ~51 min | the largest: each fix re-reads the tooling and its tests |
| L0.8 Game spec sheet: builder, build + 2 fix rounds | ~320 k | ~50 min | includes its own 25-min full suite |
| L0.7 independent QC + re-check | ~246 k | ~18 min | reproduced C1 and I1 in a scratch folder |
| L0.8 independent QC + re-check | ~209 k | ~12 min | mutation tests on the sheet |
| L0.9 Tag rule: builder (build + fix round) | ~358 k | ~66 min | the first 50 min slowed by sharing the CPU with the L0.7 suite |
| L0.9 independent QC + re-check | ~239 k | ~31 min | ran its own reference matcher, mutants and old-vs-new games |
| L0.10 Scripted players: builder | running | running | |
| Full CPU test suite | none | ~25 min alone; the L0.7 merge run took 61 min (shared the CPU with L0.9's tests) | rule from now: one heavy test run at a time |
| GPU | 0 GPU-h | | nothing has used the GPU |

Sub-agents total about 1.2 M tokens so far; the lead's own context is not measured by the tools here.

Laptop drills (21 Nov, fix branch, shared folder `~/AirStack-starling-max2/svg_training/runs/shared/`, no owner pause open):
- Wake-up: `L0.7 l07_wakeup DONE exit=0 duration=120.4s effective=120.4s`, `waiter exit 0` (the background waiter's end was the wake-up).
- Resume: `alive` → simulated power cut (`kill -KILL` of the process group at step 30) → `dead`; waiter `DIED exit=none duration=31.2s`, `waiter exit 21`; relaunch with `bash cmd.txt` from a shell with a wrong `PYTHONPATH` and `SVG_SHARED_DIR` → `launch=2`, `resumed from step 30 of 120`, `DONE exit=0 duration=90.4s effective=90.4s run_effective=120.3s`, `waiter exit 0`, `{"steps": 120, "total": 7260.0}`; the wrong shared folder was never created.

## Other workstreams

| ID | Plain name | Status |
|---|---|---|
| SYNC-1 | Branch `development` on both machines; laptop worktree `~/AirStack-starling-max2-dev` | DONE |
| SYNC-2 | Status skill `train-status` and the owner's standing rules in CLAUDE.md | DONE |
| SYNC-3 | Root `CLAUDE.md` and every page: training work lands on `development` | DONE |
| SYNC-4 | STE Guard policy (T41 run folder) in the PROVISIONAL bundle | DONE; installed on the laptop (46 files, agent.pt c91bea51…) |
| L07-F1 | Fix: waiter-duration test bound (rounding) (QC I5) | DONE (a4100d0; 30 of 30 runs pass; L0.7 test files 217 passed) |
| L07-C1 | Fix: an open pause takes time off every job, and launch does not check for one: a job launched during a pause runs on the GPU with 0 GPU-h counted and its cap never fires | DONE (79effa0 on branch ste-l0.7-fix; red 48 failed, then L0.7 + NUS pause tests 251 passed). Pauses still always logged; launch refuses while one is open; a pause counts only against the jobs it stopped |
| L07-I1 | Fix: a new run reusing an old job name inherits that job's GPU-hours as credit (task cap can be exceeded) | DONE (05dd547; credit keyed by job name + run folder; red 24 failed, then 256 passed) |
| L07-I2 | Fix: `cmd.txt` relaunch loses the environment (PYTHONPATH, CUDA alloc setting, shared-folder path) | DONE (d0661f4; cmd.txt replays the first launch's environment; a different shared folder is refused; resume drill uses bash cmd.txt; red 3 failed, then 259 passed) |
| L07-I3 | Fix: the launcher's wrapper can die (clock step back, full disk) while the job runs on: GPU time stops being logged | DONE (1ca8a70; every wrapper write survives an error, records a fault and retries; red 8 failed, then 267 passed) |
| L07-I4 | Fix: a job resumed after a reboot is flagged ENDED_EARLY (exit 20) though it finished correctly | DONE (70fc1a3; judged on the trainer's saved progress across launches; red: drill pattern read 20; then 280 passed) |
| L08-F1 | Finding: the hangar's Strike start ring (3.2 m from the zone centre) does not fit the 6.5 m lab arena (drones kept within 3.0 m); a ring for 6.5 m is needed before L0.11's base case | CLOSED (lead's call): Strike start ring 2.75 m for the 6.5 m arena, PROPOSED, ruled at G0 |
| L07-C1b | Fix: our own "pause the siblings, run solo" step (AUTOMATION §2.2) is now refused too; lead's design: pauses the session makes are tagged and do not block launch, your pauses still do | DONE (ef38534; `GPU_PAUSE_BY=lead` tags the session's pauses; a bare `gpu_pause.sh pause` is still yours and still blocks; red 13 failed, then 298 passed) |
| L07-C1c | Fix: a session-tagged resume must refuse while any of your pauses is open (a resume today continues every job and closes your pauses too) | DONE (efa9ec1; a bare resume/stop is unchanged; red 4 failed, then 304 passed) |
| GIT-1 | Fix: my 17 Nov `.gitignore` line `data/` also hid new files in `tests/data/` | DONE (d3572dc: anchored to `/data/`) |
| L09-5090 | On the 5090: record the tag-off golden's positions for its CPU type (AVX512); check the outcome fingerprints there | WAITING: next 5090 session |
| L08-M | L0.8 minors left: 3 hangar values unchecked on a clone without the NUS bundle; 3 values whose wrong value still passes; loader refuses some honest wording; tests tied to exact lines and the AirStack fence file | PARKED |
| L07-DISK | Follow-up: the planned disk-space check (a disk full through 10 retries at a job's end reads DIED) | PARKED (stated limit) |
| L07-N | Re-check minors N1–N4: a session pause also lands in the old per-worktree log the NUS reader uses; full disk can hold the wrapper 10 min after the end; AUTOMATION §4 still states the old GPU-hour rule; on the 5090 run `scripts/ste_job.py owner-pauses` before the drills | PARKED (N4 goes into the 5090 note) |
| L07-M | QC's 10 minor findings (+3 from the C1 build: pid-only matching, test pause pattern shared across sessions, pid reuse) (runs/ste_l07/qc_report.md) | PARKED until the six fixes land |
| L07-5090 | L0.7 on the 5090: full CPU suite and the two drills there (L0.7 is DONE only after both machines) | WAITING: next 5090 session |
| TEST-F2 | Fix: bit-level training fingerprint is machine-specific | DONE (447b317; trainer test file 43 passed, 1 skipped) |
| TEST-F2b | On the 5090: confirm its CPU capability is AVX512 (the key its 18 Nov hash is now filed under) | WAITING: next 5090 session runs the test (fails or skips loudly if wrong) |

**Next.** (1) L0.7 fixes L07-F1, C1, I1–I4, one at a time, each tested first and committed alone; scoped QC re-check. (2) Full CPU suite, then the wake-up and resume drills on the laptop. (3) L0.8 Game spec sheet (being built), then L0.9 Tag rule.

**Waiting on you.** Nothing.
