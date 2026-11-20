INTERNAL · the latest status of STE's own learning track, overwritten at every update; the history is in [LOG.md](LOG.md).

**Status, 2026-11-20 12:25 (+08:00), event: human gate passed (the owner approved phase L0)** · GPU 11 % / 57 W / 2.4 GB of 32 GB · 0 training processes (0 paused) · RTX 5090

## Phases

| Phase | Status | Math library | Simulator | What |
|---|---|---|---|---|
| ▶ L0 Game definition and feasibility | RUNNING (approved by the owner 20 Nov 2026, cap 19 GPU-h) | PyTorch | tier 1 fast engine, tier 2 Isaac Lab | which game the track trains; is it worth learning; can tier 2 train, and at what cost |
| L1 Drone model | NOT STARTED | PyTorch | tier 2 Isaac Lab; AirStack simulator logs | estimator effect, drag, fit to flight logs |
| L2 Game rules in the training copy | NOT STARTED | PyTorch | tier 1 fast engine, then tier 2 Isaac Lab | the rules chosen at gate G0, landing, drone loss, filter option B |
| L3 Learner | NOT STARTED | PyTorch | tier 1 fast engine, tier 2 Isaac Lab | observation version 0.3, shared policy, team critic, PPO |
| L4 Evaluation suite and gates | NOT STARTED | PyTorch | tier 1 fast engine, tier 2 Isaac Lab | test suite, gates file, calibration on known players |
| L5 League self-play | NOT STARTED | PyTorch | as ruled at gate G0 | pilots, then the runs of record with 3 seeds |
| L6 QC and export | NOT STARTED | PyTorch | tier 1 fast engine, tier 2 Isaac Lab | scoring, cross-checks, the policy file |
| L7 AirStack side | NOT STARTED | none | AirStack simulator | specifications here; built and played by an AirStack session |
| L8 Real flight | NOT STARTED | none | real flight | a real 1v1 game |
| L9 Documentation | RUNNING | none | none | status, records, results page |

L1 to L9 are the intended path; their tasks and budgets are set again at gate G0.

## Phase L0 Game definition and feasibility, task by task

| ID | Plain name | Status | Simulator | Result / ETA |
|---|---|---|---|---|
| L0.1 | Track set-up: config and test skeleton | NOT STARTED | none | next; cap 0 GPU-h |
| L0.7 | Process tooling and drills | NOT STARTED | none | after L0.1; cap 0 GPU-h |
| L0.8 | Game spec sheet | NOT STARTED | none | after L0.7; cap 0 GPU-h |
| L0.9 | Tag rule for the study: 1-for-1, nearest pair first | NOT STARTED | tier 1 fast engine | after L0.8; cap 0 GPU-h |
| L0.10 | Scripted players for the study | NOT STARTED | tier 1 fast engine | after L0.9; cap 0 GPU-h |
| L0.11 | Screening sweep (INFO) | NOT STARTED | tier 1 fast engine | after L0.10; cap 3 GPU-h |
| L0.12 | Best-response test: is the game worth learning? | NOT STARTED | tier 1 fast engine | after L0.11; cap 6 GPU-h |
| L0.2 | Tier 2 speed in contested play | NOT STARTED | tier 2 Isaac Lab | after L0.7; cap 1.5 GPU-h |
| L0.13 | Does tier 2 train at all? | NOT STARTED | tier 2 Isaac Lab | after L0.2; cap 6 GPU-h |
| L0.3 | STE Guard policy in tier 2 without retraining | NOT STARTED | tier 2 Isaac Lab | after L0.2; cap 1.5 GPU-h |
| L0.4 | Side-by-side Starling render | NOT STARTED | tier 2 Isaac Lab | cap 0.2 GPU-h |
| L0.5 | Starling video look fix | NOT STARTED | tier 2 Isaac Lab | after L0.4; cap 0.3 GPU-h |
| L0.6 | Gate G0 | NOT STARTED | none | after every task above; the owner decides |

GPU-h used in L0 so far: 0 of 19.

## Other workstreams

| ID | Plain name | Status |
|---|---|---|
| DOC-1 | Links to the track from the repository's front page and the training front page | DONE |
| DOC-2 | Track pages and figures say "L0 approved" | DONE |

**Next.** L0.1 Track set-up: config and test skeleton (starts now, CPU only); then L0.7 Process tooling and drills and L0.8 Game spec sheet.

**Waiting on you.** Nothing until gate G0.
