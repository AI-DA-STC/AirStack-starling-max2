Simulator: training simulator tier 2 (Isaac Lab, PhysX, GPU) with SIM-ONLY AirStack-simulator airframe values, beside the AirStack simulator's logs (Isaac Sim 5.1.0 + Pegasus + PX4 v1.16.1 SITL, real EKF2, from the L1.4 session); NVIDIA GeForce RTX 5090. Observed in the training simulator; not a flight result.

# 2026-11-24_ste_l15_compare record

## Purpose

STE task L1.5 (main track, INFO, no gate): with the airframe and plant the AirStack simulator flies, does tier 2's drone
(PX4 1.14 cascade port, rigid body, no estimator) answer the same velocity setpoints as the simulator's PX4 1.16.1 with
its real EKF2, and does adding L1.1's residual delay (0.05 s) or L1.1b's estimate error bring it closer? Reading rules
were fixed before the run in `ste_learning/drafts/L1_5_SPEC.md` (with addenda 1 and 2). Owner ruling R21 (24 Nov 2026,
DISCUSSION section 16): tier 2 may fly the AirStack simulator's SIM-ONLY values for this comparison only.

## Commit and inputs

- Code: commit `d01bf39e` on `development` (`scripts/compare_sim_steps.py`); extract and replay both record commit
  `d01bf39eaac8` ([replay_meta.json](evidence/2026-11-24_ste_l15_compare/replay_meta.json)).
- SIM-ONLY parameters: `params/airstack_sim_physics_v0.toml`, sha256
  `e0fe320b39b1639b52f5c0fa7b9d18853eecbc269488ef9cec090679b875fef2` (the file's `[sim_only]` table makes the trainer's loader
  refuse it; only the comparison script reads it). Error values: `params/starling_physics_v1_nominal.toml` (T63, EXPLORATORY).
- AirStack steps: the L1.4 run `runs/2026-11-24_ste_l14_steps_r3` ([T68](2026-11-24_ste_l14_steps_record.md)); 35 of its 36
  steps (step 6 not flown). Extraction: [extract.json](evidence/2026-11-24_ste_l15_compare/extract.json).
- Command: [cmd.txt](evidence/2026-11-24_ste_l15_compare/cmd.txt); replay: 4 replicas, 140 games x 2 drone slots, 245 ticks, one Isaac Lab world, seed 0,
  wall 38.8 s ([replay_meta.json](evidence/2026-11-24_ste_l15_compare/replay_meta.json)).

## What was compared

- **Setpoint PX4 received:** the velocity setpoint on `/drone_1/interface/mavros/setpoint_raw/local` (20 Hz wall), replayed
  into tier 2 at each 0.05 s tick, against PX4's own estimated velocity (ULog `vehicle_local_position`).
- **Clock alignment per step:** the simulator's PX4 clock ran 2.38 to 2.57 times the wall clock per step (median 2.54). Each
  step was aligned by fitting the bag's setpoint to the setpoint PX4 logged. Worst alignment residual 0.076 m/s, worst onset
  spread 0.075 s ([results.md](evidence/2026-11-24_ste_l15_compare/results.md), Health). The fit also removes any commander-to-PX4 link delay.
- **Speed-only route checked in PX4's log:** 35 of 35 steps sent velocity only; none of the 2,103 trajectory setpoints PX4
  logged inside the step windows carried a finite position ([extract.json](evidence/2026-11-24_ste_l15_compare/extract.json), `px4_position_setpoint`). Tier 2
  emulates the route with its two position gains at 0.
- **Arms:** `off` (no delay, no error); `delay` (`state_delay_s` 0.05 s); `error` (the six `state_error_*` values of T63's nominal file).
  The trace scored for tier 2 is its estimate (what its cascade saw).
- **Metrics:** delay_s, rise_s, rise_own_s, t63_s, overshoot_pct, ss_error_mps, lag_s, in 9 cells (axis x speed), with the
  floors of the spec (0.1 s time, 5 points overshoot, 0.02 m/s steady state). "Within" = inside the AirStack spread widened
  by the floor.

## Result (INFO)

Verdict: INFO. Ledger row: T69.

Cells where tier 2's value is within the AirStack spread (of 9), from [results.json](evidence/2026-11-24_ste_l15_compare/results.json) `within_most_cells`
and [results.md](evidence/2026-11-24_ste_l15_compare/results.md):

| Metric | off | delay | error |
|---|---|---|---|
| delay_s | 9 of 9 | 9 of 9 | 9 of 9 |
| rise_s | 9 of 9 | 9 of 9 | 9 of 9 |
| rise_own_s | 9 of 9 | 9 of 9 | 9 of 9 |
| t63_s | 9 of 9 | 9 of 9 | 9 of 9 |
| overshoot_pct | 8 of 9 | 9 of 9 | 8 of 9 |
| ss_error_mps | 9 of 9 | 9 of 9 | 9 of 9 |
| lag_s | 9 of 9 | 9 of 9 | 9 of 9 |

All 21 arm-metric pairs are within in most cells (at least 7 of 9). The rise_s of the six x and y cells is n/a for AirStack
and tier 2 alike (90 % is never reached in the hold) and reads within.

**The one cell outside:** z 0.5 m/s, overshoot. AirStack +3.3 to +6.6 % (the raw spread of its three steps; widened by the
5-point floor the band is -1.7 to +11.6 %, which is why -5.1 and -5.0 read outside and +2.5 within); tier 2 `off` -5.1 % (outside, below); `delay` +2.5 %
(within); `error` -5.0 % (outside, below). This is an observation of one cell (three AirStack steps); it is not a finding
about the delay.

**Each arm against `off` (per metric):** `delay` and `error` both read "no change (within the floor)" on all seven metrics,
which here means **not resolvable**: the time metrics' resolution is about 0.1 s, twice the 0.05 s delay arm.

**Trace RMS (tier 2 estimate minus AirStack, along the command, paired over 35 steps; pre-registered rule: closer or further
only if the mean of RMS(arm) - RMS(off) is beyond 0.005 m/s AND at least 24 of 35 steps share its sign):**

| Arm | Mean RMS (m/s) | Worst step (m/s) | Mean difference to off (m/s) | Steps with same sign | Word |
|---|---|---|---|---|---|
| off | 0.022 | 0.084 | n/a | n/a | n/a |
| delay | 0.024 | 0.091 | +0.0018 | 23 of 35 | no change (not resolvable here) |
| error | 0.027 | 0.086 | +0.0051 | 35 of 35 | further (descriptive only) |

The rule's word for `error` is descriptive only: adding a random error to the scored estimate raises its RMS against any
other trace by itself, whatever the error's size. The `error` difference (0.0051) is just above the 0.005 line.

**Health (reported, not gated):** upsets 0 and non-finite 0 in all three arms; largest tilt 12.5 (off), 12.9 (delay), 12.6
(error) degrees; replica spread 0.0 m/s in `off` and `delay`, 0.108 m/s in `error`. `off` and `delay` have no random draw,
so their 4 replicas are identical (one measurement, not four); only `error` draws its error per replica.

**Observations from the extraction (spec section 6; not readings):** the setpoint PX4 received settled at 0.37–0.44 of a
0.5 m/s teleop command, 0.50 m/s at 1 m/s and 0.75 m/s at 2 m/s (the commander's sag, cause not checked), which likely
explains the -20 to -37 % overshoot figures in x and y (AirStack and tier 2 alike) and the n/a rise_s there; climb and descent are symmetric; at a
1.5 m/s setpoint the simulator's drone settles 0.15–0.18 m/s slow in x, 0.06–0.09 in y and not at all in z (drag). The
simulator's PX4 clock (2.38–2.57 times the wall clock, median 2.54) supersedes WORK_BREAKDOWN's "about 1.9" and the L1.4
record's first reading; it is aligned per step, not removed. With the position gains at 0, the `error` arm's
position-error terms act on nothing: that arm tests the velocity and attitude errors only.

## Plain reading

1. With the AirStack simulator's airframe values, tier 2's step responses fell inside the simulator's per-step spread,
   widened by the floors, in 187 of 189 arm-metric-cell readings (3 arms x 7 metrics x 9 cells). Within is not identical,
   and the overshoot, steady-state and RMS floors were sized after a dry run on this same data.
2. The 0.05 s delay and the T63 error are not resolvable here: the time metrics resolve about 0.1 s, and the trace RMS did
   not separate the delay from off.
3. The one cell outside is the overshoot at z 0.5 m/s; whether it has a cause worth chasing is not shown.

## What it means for L1.6

L1.6's batched estimator is "only if needed". This comparison cannot see a 0.05 s delay (its resolution is about 0.1 s:
the onset uncertainty up to 0.075 s plus tier 2's +-0.025 s input quantisation), so it neither shows the need for the
estimator nor rules it out. In the spec's words, `off` within in most cells means the simulator cannot resolve an
estimator effect of the size L1.1 and L1.1b model. The simulator's EKF2 fuses simulated GPS, so this says nothing about the
real drone's mocap-fed estimator. L1.6's decision also waits on L1.3 and the NEAR-962 flight (WORK_BREAKDOWN, L1.6).

## Confounds (spec section 3)

- PX4 1.16.1 (simulator) against the 1.14 cascade port (tier 2): named, not removable.
- Route: speed-only MAVROS; the real drone's trajectory-setpoint route is not part of this comparison.
- Clock: measured and aligned per step; the fit removes any link delay, and an onset error enters AirStack's time metrics one for one (up to 0.075 s per step).
- Estimate source: the simulator's EKF2 fuses simulated GPS; the drone fuses mocap. The error arm's values are the real drone_2's EKF2 against mocap (T63), not this EKF2's error.
- Plant details tier 2 does not model: `THR_MDL_FAC` 0.9, the hover-thrust estimator, Pegasus's input scaling (1350 against 1450 rad/s), the USD's inertia (v1's CMU values used, not verified), each simulator's PhysX settings.
- The overshoot and steady-state floors were sized after seeing the CPU dry run on this data; the trace RMS threshold of 0.005 m/s likewise.

## What this does not show

One session, one drone, one airframe, one simulator machine. Nothing about the real drone's estimator, its mocap-fed EKF2
or the trajectory-setpoint route. Within the floors is not identical: with 3 to 4 steps per cell the floors, not the
spread, set the width. The SIM-ONLY values are not a training set, a drone value or an AirStack change (R21).

## GPU-hours

0.012 GPU-h (job window 42.5 s, `runs/shared/gpu_hours.log` line 50, group L1.5; task cap 0.3; launched with `--gpu-h 0.1`).
Exit code 0; run folder `runs/2026-11-24_ste_l15_compare/` (job.json, job.log; not in git).

## Evidence

`records/evidence/2026-11-24_ste_l15_compare/`: [results.md](evidence/2026-11-24_ste_l15_compare/results.md), [results.json](evidence/2026-11-24_ste_l15_compare/results.json),
[extract.json](evidence/2026-11-24_ste_l15_compare/extract.json), [replay_meta.json](evidence/2026-11-24_ste_l15_compare/replay_meta.json), [l15_steps.png](evidence/2026-11-24_ste_l15_compare/l15_steps.png), [cmd.txt](evidence/2026-11-24_ste_l15_compare/cmd.txt).
No videos: a replay of recorded setpoints plays no games.
