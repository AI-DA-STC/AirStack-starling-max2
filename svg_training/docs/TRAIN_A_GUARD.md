READ · TRAINING SIMULATOR ONLY: the step-by-step recipe that produced the STE Guard policy (pilot P1b run 4, record T41).

# Train a Guard: the recipe behind the STE Guard policy

**For** NUS researchers and anyone who wants to repeat the one training result of the NUS port. **STE**: the lab that
wrote this repository. NUS's `defender` is the defender (Guard team) here and NUS's `attacker` the attacker (Strike
team); from here on, Guard and Strike. Every number was observed in a training simulator; nothing here flies a drone.
Terms in *italics* are in the [glossary](GLOSSARY.md).

**What this recipe makes.** The *STE Guard policy* (trained in pilot P1b; a *pilot* is a short training run with no
gate): three Guard drones trained by STE's *stand-in trainer* (`scripts/train_standin.py`, skrl IPPO: independent
PPO, one learner per drone) against *S20*, the Strike policy of generation 20 of NUS self-play seed 2 (trained by STE
using NUS's code, then converted to PyTorch; [glossary, policies](GLOSSARY.md#policies)). It trains in *Test 5
conditions*: the hangar game on the *STE drone model* (a point drone that follows its speed command through a copy of
CMU's commander and the delay and lag of a model fitted to one Starling flight log), with the *safety filter* on every
pair of drones (CMU's collision filter: both drones of a close pair give way, keeping them 1.10 m apart) and drones
free in height (3-D). Run 4's result (a pilot: not gated, not a run of record): holds the zone against S20 in **829 of
1,000** games, against 429 for the *Parked Guard* (an STE baseline that commands zero speed). Evidence: T41,
[record](../records/2026-11-19_nus_phase5_pilot_p1b_run4_record.md); the result in context:
[what we found](WHAT_WE_FOUND.md#7-ste-guard-policy-trained-in-test-5-conditions).

| Badge | Means |
|---|---|
| `none` | the clone and Python only; any laptop, no GPU |
| `GPU` | an NVIDIA GPU (driver 580 or newer, 12 GB or more) |
| `lab only` | files that exist only on the lab's machines |

| Step | What | Needs | Time | Verified from a fresh clone |
|---|---|---|---|---|
| [0](#0-prerequisites) | install, then the PROVISIONAL files | `none` | ~5 min | yes (as level B of [how to run it yourself](RUN_IT_YOURSELF.md#b-a-cpu-laptop-install-run-the-game-score-a-strategy-run-the-tests)) |
| [1](#1-the-one-command) | the one command | — | — | — |
| [2](#2-what-each-setting-means) | what each setting means | — | — | — |
| [3](#3-a-tiny-cpu-check-first) | a tiny CPU check | `none` | 1 min 45 s | no: run on 19 Nov 2026 in a lab worktree of this branch (conda `env_isaaclab`, PROVISIONAL files installed) |
| [4](#4-the-gpu-run) | the GPU run | `GPU` | 2.1 h on an RTX 5090 alone (capped) | no (run 4 ran on the lab's RTX 5090) |
| [5](#5-scoring-against-s20-and-the-parked-guard) | scoring against S20 and the Parked Guard | `GPU` (or a long CPU run) | inside the run; Parked Guard about 0.4 h on a CPU (estimate) | no: the 1,000-game S20 score comes from run 4 on the lab's RTX 5090; the Parked Guard score from Test 5 (T23) |
| [6](#6-videos) | videos | — | seconds, after the run | no: clips seen in the lab-worktree CPU check |

## 0. Prerequisites

Install as in [how to run it yourself](RUN_IT_YOURSELF.md), steps B1 and B2: a Python 3.11 environment with this folder
installed, then `scripts/nus_install_provisional.sh`. B2 installs the *PROVISIONAL* files (the converted S20 and the
STE settings and starts, committed only so the numbers can be repeated) into the git-ignored `configs/local/` and
`runs/nus_port/`; without them the trainer cannot load S20 or the hangar values. Run everything from `svg_training/`,
with `P` the environment's Python and `unset PYTHONPATH` first if the shell sources ROS 2.

## 1. The one command

```bash
PYTHONPATH=source $P scripts/train_standin.py --game nus_hangar --settings pilot_p1b --seed 101 --no-eval-at-start \
    --name <new name> --device cuda
```

Run 4 used this command with `--runs-dir runs/nus_port/phase5/pilots`, the name
`2026-11-19_nus_phase5_pilot_p1b_run4` and `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` in front (the trainer sets
that variable itself in any case). `--game nus_hangar` selects the hangar game of Test 5; `--settings pilot_p1b`
selects the settings table `[pilot_p1b]` in `configs/nus_phase5.toml`; `--no-eval-at-start` skips the evaluation of
the untrained Guards. The trainer refuses an existing run folder: every run needs a new `--name`.

## 2. What each setting means

From `configs/nus_phase5.toml` `[pilot_p1b]` (table sha256 `bc0ea919…`, as in the record). P1b is the first pilot, P1,
with two fixes found by the P1 diagnosis ([P1 record](../records/2026-11-18_nus_phase5_pilot_p1_record.md): 0 holds of
1,000).

| Setting | Value | Meaning |
|---|---|---|
| zero-mean start (`zero_mean_init`) | true | the last layer of every Guard policy's mean head starts at zero, so the untrained Guards stand still; the spread of the actions starts at log std −1.6. P1's untrained Guards had a non-zero mean action and drifted off their start cluster |
| one decision per 12 ticks (`decision_ticks = "deploy"`) | 12 ticks = 0.6 s | the Guards choose a new action every 0.60 s and hold it in between, as the converted NUS-code policies do (the deploy file's hold) |
| γ (`discount_factor`) | 0.99 per decision | the discount per 0.60 s decision, not per 0.05 s tick; with P1's 0.99 per tick the +1 at the 2,400-tick time-out was discounted by about 3e-11 from the start ([P1 record](../records/2026-11-18_nus_phase5_pilot_p1_record.md)) |
| no shaping (`shaping_weight`) | 0.0 | reward only at the end of a game: +1 for a hold, −1 for a Strike reach |
| opponent (`opponent_mix`) | S20 only | the Strike team is always the converted S20 |
| games at once (`num_games`) | 32,768 | training games played in parallel on the GPU, each from a fresh random start |
| update | 32 decisions per update; 5 epochs, 4 mini-batches; learning rate 3e-4; λ 0.95; clip 0.2 | standard PPO settings of skrl's IPPO |
| networks (`hidden`) | two layers of 128 | one policy and one value network per Guard drone |
| yaw (`frozen_log_std_axes`) | frozen | the turn-rate axis keeps its initial spread: the Starling motion ignores it, so its noise is not trained (`configs/s2b.toml`) |
| evaluations (`eval_games_early`, `eval_games`) | 256 half-way, 1,000 at the end | played on the first games of the *paired starts* (the same starts as Tests 1–6) with mean actions |
| cap (`gpu_cap_hours`, `[pilots] total_gpu_hours`) | 3.0 h per run; 6.0 h for all pilots together | a hard wall-clock cap that includes the evaluations (section 4) |

## 3. A tiny CPU check first

`none` · 1 min 45 s · run 19 Nov 2026 in a lab worktree of this branch, not a fresh clone (conda `env_isaaclab`, a
32-thread workstation, `CUDA_VISIBLE_DEVICES=""`, `OMP_NUM_THREADS=4`).
Two updates on 64 games and one evaluation of 200 ticks: a pipe test, never a result.

```bash
PYTHONPATH=source $P scripts/train_standin.py --game nus_hangar --settings pilot_p1b --seed 101 --smoke \
    --no-eval-at-start --timesteps-override 64 --name try_p1b_smoke_short
```

Output seen (the timings vary by machine; `hold S20 0.000` is expected after two updates; the ledger read 0.096 h because a longer check had run before it in the same clone, on a fresh clone it reads 0.000):

```text
note: --device auto: no CUDA GPU visible to PyTorch, running on the cpu (slower; give --device cuda to require a GPU)
estimate: one evaluation about 35 s; cap 10800 s (table 3.0 h, pilots' ledger 0.096 of 6.0 h used)
stand-in (pipe test): motion starling, 64 games, 64 timesteps (49,152 game-steps of 1,000,000,000), cap 180 min wall clock incl. evaluations (hard), run folder …/runs/try_p1b_smoke_short
[eval final, 64 games] timestep 64 game-steps 49,152 | hold S20 0.000 | finished 16/64 | train 76 s eval 21 s
done: 49,152 game-steps (budget reached), train 76 s, eval 21 s -> …/runs/try_p1b_smoke_short
```

Must see: exit 0; `runs/<name>/` with `agent.pt`, `agent_best.pt`, `curve.json`, `interface.toml`,
`train_result.json` (`"status": "FINISHED"`, `"updates_done": 2`, `"smoke": true`) and two clips in `videos/`.
`--smoke` alone (without `--timesteps-override 64 --no-eval-at-start`) runs 8 updates and two evaluations: 5 min 51 s
on the same machine. A timestep here is one decision of every training game (12 ticks).

Every run, a CPU check included, adds one line to the *pilots' ledger* (`runs/nus_port/phase5/pilots/gpu_hours.log`,
git-ignored): the CPU check above used 0.028 h of the 6.0 h that all pilots share in one clone.

## 4. The GPU run

`GPU` · not verified from a fresh clone. Run it alone on the GPU: runs 1 and 2 of P1b shared the GPU and were starved
(ABORTED; evidence T32, T39). Check `nvidia-smi` first.

```bash
PYTHONPATH=source $P scripts/train_standin.py --game nus_hangar --settings pilot_p1b --seed 101 --no-eval-at-start \
    --name <new name> --device cuda
```

| Item | Run 4 (evidence T41) |
|---|---|
| Machine | the lab's RTX 5090, alone on the GPU |
| Time | 2.14 h of wall clock (04:59 to 07:08, 19 Nov 2026), stopped by its cap |
| Cap | 2.17 h: the table's 3.0 h, less what earlier pilots had used of the shared 6.0 h (3.828 h) |
| Training | 46 updates, 1,472 decisions, 579 M game-steps; about 93,600 game-steps/s |
| GPU memory | peak 4.0 GB allocated, 4.6 GB reserved (the run's `train_result.json`, `lab only`) |
| Evaluations | half-way (decision 768, 256 games): 0.758; final (1,000 games): 0.829 |

On a fresh clone the pilots' ledger starts empty, so the same command runs up to the table's full **3.0 h**, longer
than run 4 and with more updates. To stop near run 4's length, add `--stop-at <local time YYYY-MM-DDTHH:MM>` (the run
stops at the first update after that time) or `--stop-file <path>` (it stops once that file exists). Training on a GPU
is not repeatable bit for bit, so a repeat agrees within intervals, not game by game. The trainer sets
`PYTORCH_CUDA_ALLOC_CONF` itself (`[pilots] alloc_conf`). Exit 0 = finished (budget or cap), 1 = crash, 2 = refused,
3 = ABORTED (for example a non-finite value).

## 5. Scoring against S20 and the Parked Guard

**Against S20.** The run scores itself: its final evaluation plays the trained Guards (mean actions) against S20 on
the first 1,000 paired starts and prints `[eval final, 1000 games] … | hold S20 0.829` (run 4). The same numbers, with
the Wilson 95 % interval, closest approach and filter use, are in `runs/<name>/curve.json` (one entry per evaluation)
and `train_result.json`. `agent_best.pt` keeps the networks of the best evaluation.

**Against the Parked Guard.** The comparison uses the Parked Guard's own score on the same 1,000 starts in Test 5:
429 of 1,000 held (GPU; evidence T23, [record](../records/2026-11-18_nus_phase4_rung5_record.md)). To re-score it (not verified from a fresh clone):

```bash
PYTHONPATH=source $P scripts/nus_phase4.py --row 5 --pairs ParkedGuard:S20 --device cuda --out runs/<new folder> --estimate-only
PYTHONPATH=source $P scripts/nus_phase4.py --row 5 --pairs ParkedGuard:S20 --device cuda --out runs/<new folder>
```

`--row 5` is Test 5 (the records number the tests as rows); `--pairs` is meant for tests and short runs, so the
result is a check, not a new record. On the CPU (`--device cpu`) the estimate was 1,322 s (0.37 h) for this one pair.
The safety filter's answer on a GPU depends on the batch size, and in about 40 % of Parked Guard v S20 games it does
not converge in 1,000 sweeps ([filter record](../records/2026-11-18_filter_cuda_graph_record.md)): a re-score agrees
within intervals, not game by game. G19 v S20 on the same starts held 17 of 1,000 (evidence T23).

## 6. Videos

After the GPU work the trainer renders clips of its own evaluation games into `runs/<name>/videos/`: one per
evaluation, two for the final and the best evaluation (STANDARDS §8: every training run saves videos). Run 4's three
clips are published in [videos of the NUS port](media/nus/README.md#pilot-p1b-the-ste-guard-policy-against-s20-ste-drone-model-19-nov-2026).

## 7. What a good result looks like

- **Final evaluation:** 829 of 1,000 held against S20 (0.829, Wilson 95 % [0.804, 0.851]); the bar set before the run
  was a lower bound above 0.460, the Parked Guard's upper bound in Test 5. Half-way: 0.758 on 256 games.
- **In the videos:** the three Guards spread out inside the zone in a triangle that covers it; S20's drones end pressed
  against the arena walls, held off by the safety filter, which likely acts as a wall around each Guard.
- **Other measures** (final evaluation): closest Guard–Strike approach 0.55 m in the horizontal plane (0.87 m in 3-D;
  median 1.50 m); safety filter active in 33 % of ticks; rule-breach share 0.005; mean game end step 2,030 of 2,400.

## 8. What it does not show

- **One seed, one opponent.** Trained and scored only against S20; nothing says how the STE Guard policy does against
  other Strike behaviours (pilot P2, not run) or in self-play.
- **No Isaac Lab check.** It was not scored on the Isaac Lab physics drones (Test 6 conditions).
- The STE drone model uses the exploratory fitted model, which answers more slowly than the real drone.
- The mechanism ("the filter as a wall") is read from the videos and the filter share, not tested by a control.
- A pilot: not gated, not a run of record, and its weights are not in the repository (`lab only`). Observed in the
  training simulator; nothing here authorises a flight.
