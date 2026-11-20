INTERNAL · the latest status of STE's own learning track and the NUS port, overwritten at every update; the history is in [LOG.md](LOG.md). Produced by the `train-status` skill.

**Status, 2026-11-20 22:20 (+08:00), event: owner's rulings on the working branch and the checkpoint** · RTX 5090 · GPU 0 % / 79 W / 1.3 GB of 32 GB · 0 training processes (0 paused)

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
| L0.7 | Process tooling and drills | RUNNING | none | built (`scripts/ste_job.py`, AUTOMATION §7); builder's CPU suite 1326 passed, 57 skipped; independent QC and the drills still to do |
| L0.8 | Game spec sheet | NOT STARTED | none | next after L0.7; CPU |
| L0.9 | Tag rule for the study: 1-for-1, nearest pair first | NOT STARTED | tier 1 fast engine | after L0.8; CPU |
| L0.10 | Scripted players for the study | NOT STARTED | tier 1 fast engine | after L0.9; CPU |
| L0.11 | Screening sweep (INFO) | NOT STARTED | tier 1 fast engine | cap 3 GPU-h |
| L0.12 | Best-response test: is the game worth learning? | NOT STARTED | tier 1 fast engine | cap 6 GPU-h |
| L0.2 | Tier 2 speed in contested play | NOT STARTED | tier 2 Isaac Lab | 5090; cap 1.5 GPU-h |
| L0.13 | Does tier 2 train at all? | NOT STARTED | tier 2 Isaac Lab | 5090, after L0.2; cap 6 GPU-h |
| L0.3 | STE Guard policy in tier 2 without retraining | NOT STARTED | tier 2 Isaac Lab | T41 policy now in the bundle; cap 1.5 GPU-h |
| L0.4 | Side-by-side Starling render | NOT STARTED | tier 2 Isaac Lab | cap 0.2 GPU-h |
| L0.5 | Starling video look fix | NOT STARTED | tier 2 Isaac Lab | after L0.4; cap 0.3 GPU-h |
| L0.14 | Crazyflie route check | NOT STARTED | tier 1 fast engine (CPU) | T41 policy now in the bundle; cap 0 GPU-h |
| L0.6 | Gate G0 | NOT STARTED | none | after every task above; the owner decides |

GPU-h used in L0 so far: 0 of 19 (RTX 5090: 0; laptop: 0).

## Other workstreams

| ID | Plain name | Status |
|---|---|---|
| SYNC-1 | Branch `development` for working on both machines; machine-switch note in HANDOFF §0 | DONE (to push) |
| SYNC-2 | Status skill `train-status` and the owner's standing rules in CLAUDE.md, so new sessions on either machine post this without being asked | DONE (to push) |
| SYNC-3 | Root `CLAUDE.md` and every page: training work lands on `development` | DONE (owner, 20 Nov; to push) |
| SYNC-4 | STE Guard policy (T41 run folder) in the PROVISIONAL bundle | DONE (owner, 20 Nov; to push) |

**Next.** On the laptop: L0.7 independent QC and the two drills, then L0.8 Game spec sheet (CPU).

**Waiting on you.** Push branch `development` from GitHub Desktop, then on the laptop follow HANDOFF §0 "MOVING BETWEEN
MACHINES". Nothing else.
