INTERNAL · the latest status of STE's own learning track and the NUS port, overwritten at every update; the history is in [LOG.md](LOG.md). Produced by the `train-status` skill.

**Status, 2026-11-20 23:13 (+08:00), event: L0.8 started**   · laptop RTX 5070 Ti · GPU 0 % / 15 W / 1.8 GB of 12 GB · 0 training processes (0 paused)

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
| L0.7 | Process tooling and drills | RUNNING | none | laptop: independent QC next, then fix L07-F1, then the wake-up and resume drills |
| L0.8 | Game spec sheet | RUNNING | none | builder on branch `ste-l0.8` (CPU; lead's call: runs beside the L0.7 review, disjoint files) |
| L0.9 | Tag rule for the study: 1-for-1, nearest pair first | NOT STARTED | tier 1 fast engine | after L0.8; CPU |
| L0.10 | Scripted players for the study | NOT STARTED | tier 1 fast engine | after L0.9; CPU |
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
- **L07-F1** `test_ste_job.py::test_f_d_a_killed_job_reads_dead_the_waiter_says_died_and_the_same_command_resumes`: the waiter prints 0.3 s, the elapsed time was 0.293 s. Candidate cause: the one-decimal rounding against an exact bound (not yet confirmed).
- **TEST-F2** `test_train_standin.py::test_default_path_bit_identical_after_the_nus_hooks`: FIXED (447b317). Measured on the laptop: the hash repeats (75d2a955…), hold rates equal the recorded [0.25, 0.375], and forcing PyTorch's CPU capability down changes the hash; threads (trainer runs one) and local files (not read on this path) ruled out. The fingerprint is now one hash per CPU capability; hold rates are checked on every machine.

## Other workstreams

| ID | Plain name | Status |
|---|---|---|
| SYNC-1 | Branch `development` on both machines; laptop worktree `~/AirStack-starling-max2-dev` | DONE |
| SYNC-2 | Status skill `train-status` and the owner's standing rules in CLAUDE.md | DONE |
| SYNC-3 | Root `CLAUDE.md` and every page: training work lands on `development` | DONE |
| SYNC-4 | STE Guard policy (T41 run folder) in the PROVISIONAL bundle | DONE; installed on the laptop (46 files, agent.pt c91bea51…) |
| L07-F1 | Fix: waiter-duration test bound (rounding) | QUEUED (L0.7 independent QC running, read-only) |
| TEST-F2 | Fix: bit-level training fingerprint is machine-specific | DONE (447b317; trainer test file 43 passed, 1 skipped) |
| TEST-F2b | On the 5090: confirm its CPU capability is AVX512 (the key its 18 Nov hash is now filed under) | WAITING: next 5090 session runs the test (fails or skips loudly if wrong) |

**Next.** (1) L0.7 Process tooling and drills: independent QC (running). (2) L07-F1 and any QC findings, one at a time; L0.8 being built beside it. (3) L0.7 drills on the laptop, then L0.8 Game spec sheet.

**Waiting on you.** Nothing (owner, 20 Nov: "go ahead with ur recommendations then continue").
