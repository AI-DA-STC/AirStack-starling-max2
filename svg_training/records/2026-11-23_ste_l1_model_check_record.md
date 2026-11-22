Simulator: training simulator, tier 2 (Isaac Lab physics drone and its PyTorch twin) and tier 1. Observed in the training simulator; not a flight result.

# 2026-11-23_ste_l1_model_check record

Written by hand from the two run folders' `results.json` / `results.md` / `isaac_tests.log` (`scripts/l1_model_check.py`
writes no record); the tables are copied from `results.md`.

## Purpose

STE tasks L1.1 (estimator effect in the tier-2 drone), L1.2 (drag) and L1.1b (estimator model shape), main track, INFO
(no gate; WORK_BREAKDOWN: "Done: tests pass; throughput cost measured (≤ 10 %)"). `scripts/l1_model_check.py` runs the
Isaac-marked tests of the changed physics path and measures game-steps per second with the effects off and on (made-up
"on" values, never drone values), in the Isaac Lab world, its PyTorch twin and tier 1.

Two runs:

- **Run A** (22 Nov 2026, L1.1 model: pure whole-state delay plus white noise): `~/AirStack-starling-max2/svg_training/runs/ste_archive/l1model/runs/2026-11-22_ste_l1_model_check`
  (archived from the removed worktree `~/AirStack-starling-max2-l1model`).
- **Run B** (23 Nov 2026, L1.1b model: Gauss–Markov estimate error): `~/AirStack-starling-max2-l11b/svg_training/runs/2026-11-23_ste_l1_model_check`.

## Commit

Neither run folder holds a `code.json`, so the code that ran is not pinned by the run.

- Run A: launched 2026-11-22T22:40:41+08:00 from the worktree `~/AirStack-starling-max2-l1model` before its work was
  committed; the work landed (rebased) as `ff2c912e…` ("L1.1 state delay/noise + L1.2 drag in the tier-2 drone"), and the
  label fix `54706c3b…` followed from this run's one failure. The settings text the run stored equals
  `configs/ste_l1/model_check.toml` at `ff2c912e` and `54706c3b`.
- Run B: launched 2026-11-23T02:50:42+08:00 in the worktree `~/AirStack-starling-max2-l11b`, eight minutes before the
  L1.1b commit `8ca664aa…` (02:59:10). The settings text the run stored equals `configs/ste_l1/model_check.toml` at
  `8ca664aa` (sha256 `f4bfd0a2886ee2ddfe463877b86bc0f8166f187b17ec33ff4bba6cadaf471928`). The code that ran is not shown
  identical to `8ca664aa`.

## Config

- Settings `configs/ste_l1/model_check.toml` (text copied into each `results.json`); the "on" parameter file written into
  each run folder as `params_on.toml` (run A sha256 `01ad566e23fd…`, run B `6b77e02756c6…`): v1 with every effect switched
  on at made-up values, labelled "L1 model check: MADE UP, not a drone value".
  - Run A "on": `state_delay_s` 0.05 (pure delay of the whole state, 10 physics steps), white noise on position,
    attitude, velocity and rate, drag 0.1 N/(m/s) per axis; noise seed 0 (the game seed did not reach the noise yet).
  - Run B "on": `state_error_*` (Gauss–Markov) position 0.02 m / 0.5 s, velocity 0.02 m/s / 0.2 s, attitude 0.005 rad /
    0.5 s; `state_delay_s` 0, `state_delay_att_s` 0 (fixed); white noise position 0.005 m, velocity 0.02 m/s, attitude
    0.005 rad, rate 0.02 rad/s; drag 0.1 N/(m/s) per axis; noise seed 1100 (the game seed).
- Game `configs/ste_l011/base.toml` (`96e0e7f61a49…`), 3v3, 4,096 games; 50 warm-up and 200 timed steps per repeat,
  3 repeats per arm.

Commands (`cmd.txt`; through `scripts/ste_job.py launch --task L1.1 --settings configs/ste_learning.toml --beat-s 60.0`):

```
run A: --name ste_l1_model_check   --gpu-h 0.2  -- python scripts/l1_model_check.py --run-dir runs/2026-11-22_ste_l1_model_check --cap-h 0.2 --headless
run B: --name ste_l1_model_check_b --gpu-h 0.19 -- python scripts/l1_model_check.py --run-dir runs/2026-11-23_ste_l1_model_check --cap-h 0.19 --headless
```

## Model parameter set

Tier 2: the rigid-body Starling `params/starling_physics_v1.toml` (v0's gains and airframe from the drone's file, never
tuned; the L1.1 / L1.1b / L1.2 keys 0 and OPEN until fitted). Tier 1: `params/real_exploratory_v0.toml` (fitted response,
exploratory).

## Machine

jeremychia-Legion-Pro-7-16IAX10H, NVIDIA GeForce RTX 5070 Ti Laptop GPU, torch 2.7.0+cu128, device cuda:0.

| Run | Launched | Exit | GPU-h used (shared ledger, job) |
|---|---|---|---|
| A | 2026-11-22T22:40:41+08:00 | 3 (stopped at its 0.2 cap, 721 s wall) | 0.200 (ste_l1_model_check) |
| B | 2026-11-23T02:50:42+08:00 | 0 (DONE, 457 s wall) | 0.127 (ste_l1_model_check_b) |

## Gates

Verdict: **INFO** (no pass/fail gate). WORK_BREAKDOWN's done-criteria: the tests pass; the throughput cost is measured
(budget ≤ 10 %, INFO).

## Results

**Run A** (copied from `results.md`):

Isaac-marked tests: exit 1: 1 failed, 6 passed, 31 deselected, 1 xfailed in 49.36s.

| Part | World | Games | Off game-steps/s | On game-steps/s | Cost | Budget |
|---|---|---|---|---|---|---|
| tier2_isaac | isaaclab-2.3.2 | 4,096 | 11,935 | 10,615 | 11.1 % | 10 % (INFO) |
| tier2_torch | not run | | | | | |
| tier1 | not run | | | | | |

Stopped: cap. The one failure: `test_estimator_effect.py::test_isaac_world_same_results_as_torch` asserted the world
label starts with "Isaac" and got `isaaclab-2.3.2` (label only; fixed in `54706c3b`); the delay, noise and agreement
checks of that test did not run. Repeats (off / on): 11,072, 10,950, 13,785 / 6,957, 6,807, 18,082 game-steps/s; the
"on" arm had 2 upsets (tilt past 60°), the "off" arm 0; no non-finite values.

**Run B** (copied from `results.md`):

Isaac-marked tests: exit 0: 7 passed, 32 deselected, 1 xfailed in 40.31s.

| Part | World | Games | Off game-steps/s | On game-steps/s | Cost | Budget |
|---|---|---|---|---|---|---|
| tier2_isaac | isaaclab-2.3.2 | 4,096 | 26,763 | 28,192 | -5.3 % | 10 % (INFO) |
| tier2_torch | torch-reference (test oracle) | 4,096 | 34,854 | 37,490 | -7.6 % | 10 % (INFO) |
| tier1 | none (tier 1, fitted response) | 4,096 | 166,816 | not built (L1.7) | — | 10 % (INFO) |

Stopped: no. Repeats, tier2_isaac off / on: 25,783, 26,367, 28,139 / 29,758, 29,436, 25,383; no upsets and no
non-finite values in either arm of either tier-2 world. The xfail is the strict mark on
`test_isaac_world.py::test_isaac_open_loop_matches_torch` (T10's accepted FAIL: PhysX GPU attitude integration, about
1.07–1.15 mm against the 1.0 mm open-loop gate).

## Figures and videos

None (a throughput and test check; no games played to a result).

## Ledger row

Ledger row: | T62 | 2026-11-22T22:40:41+08:00 | training simulator, tier 2 (Isaac Lab physics drone and its PyTorch twin) and tier 1; NVIDIA GeForce RTX 5070 Ti Laptop GPU | 2026-11-23_ste_l1_model_check (2 runs: A 2026-11-22, L1.1 model; B 2026-11-23, L1.1b model) | STE L1.1 / L1.2 / L1.1b model checks: run A stopped at its 0.2 GPU-h cap, Isaac tests 6 passed, 1 failed on the world label only (its delay/noise/agreement checks did not run), speed figure not valid (a CPU suite ran beside it); run B Isaac tests 7 passed, 1 xfailed (T10's accepted gap), tier2_isaac 26,763 off / 28,192 on, tier2_torch 34,854 / 37,490 game-steps/s: no measurable cost (−5 %, −8 %, within noise); tier 1 166,816 off, effects not built (L1.7); 0.327 GPU-h | INFO | records/2026-11-23_ste_l1_model_check_record.md |

## Run notes added by the lead

- **Run A's speed figure is not valid.** While it ran, a full CPU test suite ran in parallel on the same machine; the
  repeats scatter (on arm 6,807 to 18,082) and the 11.1 % "cost" is not a measurement of the effects. Its test result
  stands as written: 6 passed and 1 failed on the world label only, so the delay, noise and Isaac-against-torch agreement
  checks of that test did not run in run A (they passed in run B, on the L1.1b model).
- **Why the model changed between the runs (L1.1 code review).** A pure delay of the whole state is the wrong shape for
  EKF2, whose output predictor hands the controllers current-time states. A CPU check in the review found the z loop
  (MPC_Z_P 5 × MPC_Z_VEL_P_ACC 8) unstable at about 0.117 s of feedback delay: limit cycles of 0.36 m at 0.10 s and
  1.42 m at 0.15 s (attitude delayed as well: tilt 0.92 rad at 0.15 s). Run A's "on" arm used 0.05 s and had 2 upsets.
- **The L1.1b design (built 23 Nov 2026, `8ca664aa`).** The estimate is the true state plus a first-order Gauss–Markov
  error per quantity (position, velocity, attitude as a small body rotation; sigma and tau each, drawn from the
  stationary distribution at each reset); body rates keep white gyro noise. Attitude is never delayed
  (`state_delay_att_s` must be 0); `state_delay_s` is a residual delay of position and velocity, refused above 0.05 s
  (fixed in code, well under the ~0.117 s). The game seed reaches the noise (run B: 1100; run A: 0). A replay restores the
  estimator's state. Every key stays 0 and OPEN in v1 until fitted (L1.3, [record T63](2026-11-23_ste_l13_fit_record.md)).
- **Hover check (CPU, torch world, made-up values; WORK_BREAKDOWN L1.1b).** With position 0.02 m / 0.5 s, velocity
  0.02 m/s / 0.2 s and attitude 0.005 rad / 0.5 s: hover RMS 0.039 m, largest 0.115 m, tilt 0.030 rad, no upset.
  Exploratory values, not drone values; observed in the training simulator.
- **Run B: no measurable cost.** With every effect on, tier 2 runs as fast as with it off (−5 % in Isaac Lab, −8 % in the
  torch twin, both inside the spread of the three repeats), well inside the 10 % budget. Tier 1 has no effects yet (L1.7).
- **Code.** Neither run pins its code; run B's settings equal the committed file and it ran minutes before the commit.
- **Limits.** Throughput at 4,096 games on the laptop GPU only; made-up effect values; observed in the training
  simulator, nothing flown.
- **GPU-hours** (shared ledger): run A 0.200, run B 0.127; total 0.327, charged to L1.1.
