INTERNAL · spec of task L1.5 (tier 2 against the AirStack simulator, the simulator's own airframe), written before its run of record; DRAFT, unreviewed · [README.md](README.md); the task: [WORK_BREAKDOWN](../WORK_BREAKDOWN.md) row L1.5

Written 24 Nov 2026 by the L1.5 builder (branch `l15-build`), before the Isaac Lab run. Main track. Owner ruling R21
(24 Nov 2026, [DISCUSSION §16](../DISCUSSION_2026-11-19_20.md#16-rulings-for-l1-to-l6-owner-24-nov-2026)): tier 2 may
fly the AirStack simulator's SIM-ONLY airframe values for this comparison only.

# L1.5: tier 2 against the AirStack simulator (INFO)

**Verdict kind: INFO.** No pass/fail gate; the health checks below are reported, not gated. Observed in the training
simulator (tier 2, Isaac Lab) against the AirStack simulator; not a flight result. Nothing here is a training set, a
drone value or an AirStack change (repository iron rule 9).

## 1. Question

With the airframe and plant the AirStack simulator flies, does tier 2's drone (PX4 1.14 cascade port, rigid body, no
estimator) answer the same velocity setpoints as the simulator's PX4 1.16.1 with its real EKF2, and does adding L1.1's
residual delay or L1.1b's estimate error bring it closer? This narrows the estimator's effect as far as this simulator
and this comparison's time resolution (about 0.1 s, section 5) allow; it does not isolate it: PX4 1.16.1 against the
1.14 port and the plant details of section 3 remain.

## 2. Inputs (pinned)

| Item | Value |
|---|---|
| AirStack steps | L1.4 session `runs/2026-11-24_ste_l14_steps_r3` (record [2026-11-24_ste_l14_steps_record](../../records/2026-11-24_ste_l14_steps_record.md), T68): bag sha256 `6e2546ca20a2…`, drone_1 PX4 log sha256 `07de377b2819…`, `steps.json` `12a0e5c69339…`, `steps_flown.json` `d491a4c93868…` |
| SIM-ONLY parameters | `params/airstack_sim_physics_v0.toml`, sha256 `e0fe320b39b1…`: every `[gains]` value equals the session's PX4 parameter dump (test); 37 `[gains]` lines cite the airframe file `10090_pegasus_starling2max` (sha256 `ec74dd9a…`, the file L1.4 flew) by line (test); plant from Pegasus `starling2max.py` (motor lag off, linear drag 0.5 / 0.3 / 0 N per m/s, body axes). The file carries a `[sim_only]` table, so the trainer's loader refuses it; only `scripts/compare_sim_steps.py` reads it; no config, source or other script file names it (test); the loaded parameters carry `source["sim_only"]` |
| Error values | `params/starling_physics_v1_nominal.toml` (T63's nominal proposal, EXPLORATORY) |
| Code | `scripts/compare_sim_steps.py`, tests `tests/test_compare_sim_steps.py` (fixture `tests/data/l15_steps_fixture.npz`, 201 kB, steps 1, 17, 18 cut from the session) |

## 3. What is compared, and the confounds

PX4's own input against PX4's own estimate, on PX4's clock: the velocity setpoint PX4 received
(`/drone_1/interface/mavros/setpoint_raw/local`, 20 Hz wall) and the velocity PX4 estimated (ULog
`vehicle_local_position`, 100 Hz PX4 time). Tier 2 replays that setpoint.

| Confound (WORK_BREAKDOWN L1.5) | Handled how |
|---|---|
| The simulator's PX4 clock against the commander's wall clock | **Measured and aligned per step** (onset uncertainty up to 0.075 s): the map PX4 time = a + s (wall - onset) is fitted by matching the bag's held setpoint to the setpoint PX4 logged (`vehicle_local_position_setpoint`, 10 Hz); tier 2 gets PX4's input on PX4's clock. The fit matches setpoint to setpoint only, so a lag between PX4's setpoint and its response is not absorbed (a synthetic test injects 0.3 s and gets 0.3 s back). Two consequences: (a) the fit also removes any commander -> PX4 link delay (MAVROS, the bridge), so if part of L1.1's 0.05 s stands for link delay this comparison cannot see that part; (b) an onset error enters AirStack's `delay_s` (and `lag_s`, `t63_s`) one for one, up to ±0.075 s per step, averaged over the 3-4 steps of a cell. The clock's size is still reported: s per step, and the settled setpoint PX4 got over the teleop command, per speed |
| The speed-only MAVROS route against the trajectory setpoint | **Measured, and emulated in tier 2**: all 35 steps sent velocity and yaw rate only (type mask 1479), and on PX4's side none of the 2,103 trajectory setpoints PX4 logged inside the 35 step windows carried a position (all NaN; finite positions appear only before arming; a test checks every step). PX4 therefore flew velocity only. Tier 2 emulates the route with its two position gains (`MPC_XY_P`, `MPC_Z_P`) at 0 in the script (the TOML keeps the as-flown 0.95 / 5). Why: tier 2's `PhysicsDrone` holds a position setpoint over each tick, which pulls back about K_p v dt / 2 (about 0.19 m/s at a 1.5 m/s climb; pinned by a test). The real drone's trajectory-setpoint route is **not** part of this comparison |
| PX4 1.16.1 (simulator) against the 1.14 cascade port (tier 2) | **Named**, not removable |
| Where the estimate comes from | **Named**: the simulator's EKF2 fuses simulated GPS (`EKF2_GPS_CTRL` 7, `EKF2_HGT_REF` 1, `EKF2_EV_CTRL` 0); the drone fuses mocap. The error arm's values (T63) are the real drone_2's EKF2 against mocap, not this EKF2's error |
| Plant details tier 2 does not model | **Named**: `THR_MDL_FAC` 0.9 (tier 2 linear), the hover-thrust estimator, Pegasus's input scaling 1350 rad/s per unit against omega_max 1450, the USD's inertia (binary, not read: v1's CMU sys-ID values used, NOT VERIFIED), each simulator's PhysX scene settings |

## 4. The run

Tier 2 input: the AirStack setpoint at each tick's midpoint, held over the 0.05 s tick (a change reaches tier 2
within ±0.025 s); start state = the AirStack drone's estimated position, velocity and heading 2 s before the onset,
level, fresh integrators; window from 2 s before the onset to 2.5 s after the hold ends (PX4 time; the hold is
3 s wall, about 7.5 s PX4). One batch for all arms: 35 steps x 4 replicas = 140 games x 2 drone slots (slot 0 flies
the step; slot 1 holds still 15 m off in x and y, the two-slot layout of the other tier-2 scripts), one Isaac Lab world,
the arms flown one after the other on it.

**The trace scored for tier 2 is its estimate** (`PhysicsDrone.est_vel_mps`, what its cascade saw), because the
AirStack trace is PX4's EKF2 estimate; tier 2's true velocity is kept beside it (INFO). In `off` the two are equal; in
`delay` the estimate is the truth 0.05 s earlier; in `error` the truth plus the correlated error (pinned by a test).
With the position gains at 0, `state_error_pos_*` acts on nothing: the error arm tests the velocity and attitude
errors only.

| Arm | Change from the SIM-ONLY file (all arms: position gains 0) |
|---|---|
| `off` | none |
| `delay` | `state_delay_s` 0.05 s (L1.1's residual delay at its FIXED limit; the 0.1482 s tier-1 delay is refused by design) |
| `error` | the six `state_error_*` of `starling_physics_v1_nominal.toml` (sigma 0.0099 m / 1.2 s, 0.022 m/s / 1.3 s, 0.0027 rad / 2.0 s) |

## 5. Metrics, floors and reading words (fixed before the run)

Per step, the speed along the command (signs pooled), onset-aligned, on the 0.05 s grid; levels shared by every trace
of the step and taken from the input (the delivered setpoint peaks, then sags, so it is not a step): level0 = the
input's mean over the last 1 s before the onset, level_peak = the input's extreme in the first 2.5 s.

| Metric | Definition | Floor |
|---|---|---|
| `delay_s` | the trace's 10 % crossing of level0 -> level_peak minus the input's | 0.1 s |
| `rise_s` | 10 % -> 90 % of level0 -> level_peak; n/a if 90 % is never reached in the hold (every x and y step: the response peaks about 25-35 % under the input's peak) | 0.1 s |
| `rise_own_s` | 10 % -> 90 % of the trace's own extreme in the hold (**added after the first CPU dry run**, because `rise_s` is n/a in all six x and y cells) | 0.1 s |
| `t63_s` | 63 % of level0 -> level_peak, from the onset | 0.1 s |
| `overshoot_pct` | (the trace's extreme in the hold - level_peak) / (level_peak - level0) x 100; negative = under the input's peak | 5 points |
| `ss_error_mps` | mean(trace - input) over the hold's last 1 s; positive = faster than sent | 0.02 m/s |
| `lag_s` | the shift of the input in [-0.10, 0.60] s that minimises the RMS to the trace from 0.5 s before the onset to the hold's end | 0.1 s |

**Time resolution and the time floor (0.1 s).** The honest time resolution of this comparison is about 0.1 s: the
clock alignment's onset uncertainty (worst 0.075 s; it enters AirStack's times one for one) plus tier 2's ±0.025 s
input quantisation, and the dry run's replica ranges reach 0.10 s on `delay_s`. A 0.05 s floor (one tick) would sit
below that resolution, so the time floor is 0.1 s (the lead's preference, adopted). Consequence, stated before the
run: **the 0.05 s delay arm is below the time resolution, so on the time metrics "within" cannot tell it from `off`
and "no change (within the floor)" is the expected outcome for it there.**

**Overshoot and steady-state floors (5 points, 0.02 m/s)** were sized from the CPU dry run on the real AirStack data,
that is, set after seeing data: they are of the order of the error arm's replica-to-replica range there (overshoot
median 1.9, largest 8.6 points; steady-state error median 0.018, largest 0.047 m/s). The lead accepted the floors
(technical call).

Four steps per cell (three for z 0.5 m/s) make a narrow AirStack spread; the floor is what keeps "within" from
meaning "identical".

**Cells**: axis x speed (9 cells; 4 steps each, z 0.5 m/s 3 steps: step 6 was not flown). AirStack spread of a cell =
the min to max of its steps' values. Tier 2's cell value = the mean over the cell's steps of the replica mean.

**Reading words** per arm, cell and metric: **within** (inside the AirStack spread widened by the floor on both sides),
**outside (above)**, **outside (below)**, **not reached** (tier 2 never reaches a level AirStack reaches),
**outside (AirStack not reached)** (the reverse); both never reaching it reads **within**.

**Each arm against `off`**, per metric: the mean over cells of |tier 2 cell value - AirStack cell median|; the arm is
**closer** if that is smaller than `off`'s by more than the floor, **further** if larger by more than the floor, else
**no change (within the floor)**.

**Trace RMS (the one read that could see the delay arm).** Per step, the RMS of tier 2 - AirStack along the command
over the step's window (tier 2's estimate; its true state beside it, INFO); mean and worst step per arm. Reading,
paired over the 35 steps: an arm is **closer** / **further** than `off` only if the mean of RMS(arm) - RMS(off) is
beyond 0.005 m/s AND at least 24 of the 35 steps share its sign; otherwise **no change**. The 0.005 m/s was set after
the dry run (delay +0.0018 m/s, error +0.0055 m/s); for the error arm the word is descriptive only, because adding a
random error to the scored estimate raises its RMS against any other trace by itself, whatever the error's size.

**"Most cells"** = at least 7 of the 9 cells, per metric (`results.json` `within_most_cells`).

**Health (reported, not gated)**: upsets and non-finite counts per arm (expected 0); largest tilt; per step the
alignment residual (worst 0.076 m/s) and onset spread (worst 0.075 s); each arm's largest replica-to-replica spread
(in `off` and `delay` a determinism check of PhysX on the GPU; 0 on the CPU). All in `results.json` `health`.

**How the result will be read** (no gate): if `off` is within in most cells (at least 7 of 9) on every metric but
`rise_s`, tier 2 with the simulator's
airframe reproduces the simulator's PX4 + EKF2 at these floors, and the simulator cannot resolve an estimator effect
of the size L1.1 / L1.1b model; the comparison then says nothing about the real drone's EKF2 (mocap-fed, a different
route, PX4 1.14). An arm that is **closer** on a metric is evidence (one session, one airframe) that the simulator's
EKF2 adds that effect; **further** is evidence against that arm's size in the simulator.

## 6. What the extraction found on the real bag (CPU, 24 Nov 2026)

- 35 steps parsed (36 planned; step 6, -z 0.5 m/s, skipped by the floor guard, as `steps_flown.json` says).
- Every step's setpoint was speed-only (type mask 1479).
- The simulator's PX4 clock ran **2.38 to 2.57 times** the wall clock per step (median 2.54; flight-span method 2.51),
  not the 1.9 of the S1 session on the laptop. It drifts within the session: a single affine map is off by up to 3.4 s
  of PX4 time, hence the per-step fit (alignment residual 0.004-0.076 m/s, onset spread 0-0.075 s).
- The settled setpoint PX4 got over the teleop command: 0.37-0.44 at 0.5 m/s (about 1 / clock scale), 0.50 at
  1 m/s and 0.75 at 2 m/s (the setpoint settles at teleop - 0.5 m/s: likely the commander's reference pull reaching a
  limit while the drone outruns its wall-clock reference point; not checked against the commander's source).
- The z steps are symmetric (climb and descent both settle at the setpoint, e.g. 1.5 m/s at 2 m/s teleop): the
  14 m heights are a 3 s wall hold x about 2.5 clock x 1.5 m/s (about 11 m) on top of 2.6 m, not a descent limit as
  the L1.4 record guessed; the 1.12 -> 2.63 m shift early on is step 5 (+z) without its skipped twin.
- The simulator's drag is visible: at a 1.5 m/s setpoint x settles about 0.15-0.18 m/s slow, y 0.06-0.09, z none,
  the order of Pegasus's 0.5 / 0.3 / 0 drag on a drone facing +x.

## 7. CPU dry run (torch world, 4 replicas; NOT of record)

Run to check the pipeline end to end before the GPU run (`runs/2026-11-24_ste_l15_cpu_dry` in the builder's worktree,
about 15 s on the CPU). PyTorch reference world, not PhysX. Seen with the final rules (after both addenda): `off`
within in 9 of 9 cells on every metric but `overshoot_pct` (8 of 9: z 0.5 m/s, tier 2 does not overshoot, AirStack
+3 to +7 %); `delay` within in 9 of 9 on every metric (z 0.5 m/s overshoot +2.5 %); `error` as `off`; both arms "no
change (within the floor)" against `off` on every metric (as expected for the delay arm, section 5). Trace RMS against
AirStack (tier 2's estimate): 0.022 m/s mean (off), 0.024 (delay), 0.027 (error); paired against `off`: delay +0.0018
m/s, same sign in 23 of 35 steps, **no change**; error +0.0055 m/s, 34 of 35, **further** (descriptive only).
Health: no upsets, no non-finite values, largest tilt 12.9 deg; replica spread 0 in `off` and `delay`, at most 0.10 m/s
in `error`.

**Addendum (24 Nov 2026, after the first dry run, before any GPU run; advisor's review):** (1) `rise_own_s` and the trace
RMS line were added (section 5). (2) The first dry run scored tier 2's TRUE velocity against AirStack's EKF2 estimate;
the scored trace is now tier 2's estimate (section 4), which changed the delay arm's z readings (its `lag_s`, `t63_s`
and `delay_s` on z had read "outside (below)": an artefact of comparing truth with an estimate). (3) Two drone slots
per game instead of one, as every other tier-2 script (a one-drone Isaac world has never been built here). (4) The
health block gained the replica spreads and the alignment. Nothing else in sections 4 and 5 changed.

**Addendum 2 (24 Nov 2026, after one independent review for the lead, before any GPU run):** time floors raised from
0.05 s to 0.1 s (the honest resolution; the delay arm is below it); the trace RMS reading and "most cells" (7 of 9)
fixed with numbers; the overshoot and steady-state floors stated as set after seeing data; the speed-only route
checked in PX4's own log (no position setpoint in any step window); the clock row now says measured and aligned, with
what the fit removes (link delay) and how an onset error enters; a synthetic test that a response lag survives the
alignment; the name-scan test covers `scripts/`; the loaded parameters carry a SIM-ONLY tag.

## 8. GPU, cost and launch

Projection: Isaac Lab start and world about 2 min, three arms of 140 games x about 250 ticks about 1 min; **about
0.05 GPU-h, cap 0.3 GPU-h** (task L1.5's cap in `configs/ste_learning.toml`). Alone on the GPU or side by side
(small: 140 games x 2 drones). The lead launches it; nothing here ran on the GPU. **The Isaac branch of the script
(`--world isaac`, `_isaac_main`, the Isaac world factory) has not been executed: the first launch is its smoke.** It
follows `scripts/physics_step_tests.py`'s pattern (Isaac started headless before torch, `make_physics_sim`,
`IsaacWorld(sim, n, 2, ...)`, `physics_play`, `os._exit`).

```
cd ~/AirStack-starling-max2-dev/svg_training     # after l15-build is merged
unset PYTHONPATH
PY=~/miniconda3/envs/env_isaaclab/bin/python
R=runs/<date>_ste_l15_compare
$PY scripts/compare_sim_steps.py extract --l14-run runs/2026-11-24_ste_l14_steps_r3 --run-dir $R    # CPU, ~10 s
nvidia-smi && scripts/isaac_preflight.sh --approved-headless
$PY scripts/ste_job.py launch --task L1.5 --name l15_compare --run-dir $R --min-s 30 --gpu-h 0.1 -- \
    $PY scripts/compare_sim_steps.py replay --run-dir $R --world isaac --replicas 4 --headless
```

Writes into the run folder: `extract.json`, `tier2.npz`, `replay_meta.json`, `results.json`, `results.md`,
`l15_steps.png` (one panel per cell). Then the record and the ledger row (lead).

## 9. What this does not show

One session, one drone, one airframe, one simulator machine; the simulator's EKF2 is GPS-fed; the speed-only route
only; PX4 1.16.1 against a 1.14 port. Nothing about the real drone's estimator or the trajectory-setpoint route. The
SIM-ONLY values never become a training set (R21).
