INTERNAL · a build plan written for the lab's AI coding assistants; history, not instructions. Results: [../README.md](../README.md).

# S1 Drone Model and Safety Filter Implementation Plan

## Changes during execution (15 November 2026)

The plan below is kept as approved. Three things changed while it was carried out, all on the owner's word the
same day:

- **Why.** The fit to the AirStack simulator (Task 4, T3) failed because the simulator runs two clocks: the
  commander moves its reference point on the wall clock while PX4 runs about 1.9 times faster
  ([cause notes](../notes/s1_two_clocks_cause.md)). A survey of the real flight logs then showed that the real
  drone gets a different command, a trajectory setpoint through `px4_interface`, not a bare speed through MAVROS
  ([survey](../notes/s1_real_logs_survey.md)). So a simulator fit describes the simulator, not the drone. The owner
  ruled that the training model comes from real flight logs (STANDARDS §5 rule 10).
- **Task 6 was replaced.** Fit v1 on simulator steps is not done. Its place is taken by a real flight with planned
  pushes, flown by the owner, which will give the drone model its run of record
  ([S1 results, next steps](../S1_RESULTS.md#what-the-owner-needs-to-do-next)). Task 5's simulator session (scripts
  ready, not run) is optional now.
- **Task 8 was revised to the real chain.** Instead of `FittedResponse(params: ResponseParams)` tested against
  `models.response.simulate`, tier 1 got a batched copy of the commander's real-drone rules (`models/commander.py`,
  tested against CMU's `position_hold.py`), a PX4 trajectory-mode model fitted to real flight logs
  (`models/fitted.py`, `params/real_exploratory_v0.toml`, exploratory), and the team filter where the commander
  calls it. The revised brief is a local working note; what was built and measured is in the
  [T4 record](../../records/2026-11-15_s1_tier1_fitted_filter_record.md) and the
  [exploratory record](../../records/2026-11-15_s1_real_px4_exploratory.md).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the stand-in drone response with one fitted to how a velocity command actually moves a Starling in the AirStack simulator, and port CMU's safety filter to batched PyTorch (within each team only), each proven by gates set before the runs.

**Architecture:** Bags are read inside CMU's robot image (it has `rosbag2_py`), turned into CSV under `runs/`, and fitted on the host with NumPy/SciPy. One NumPy model function is the reference; the PyTorch tier 1 model must reproduce it exactly. The safety filter is a fixed-iteration batched port of `cbf_filter.py`, tested against the original imported read-only from `AirStack/`.

**Tech Stack:** Python 3.11 (`env_isaaclab`: torch 2.7, numpy, scipy, pandas), CMU robot image `airstack:v0.18.0_robot-x86-64_dev` for bag reading, `tools/sim.sh` for the AirStack simulator (run, never edited).

**Spec:** [../DESIGN.md](../DESIGN.md) §3 (stage 1), §4, §8 row S1; [../../STANDARDS.md](../../STANDARDS.md) §3, §5 (rules 1–9), §7.

**Status:** written 15 November 2026; **approved by the owner on 15 November 2026 with the gates of Task 1 as proposed**; execution: subagent-driven.

## Facts this plan rests on (S1 research, 15 November 2026)

| Fact | Source |
|---|---|
| Policy commands enter at `/svg/drone_1/teleop_command` (`TwistStamped`, world ENU, 20 Hz); the commander ramps them (`teleop_accel_mps2` 5.0), adds `teleop_kp·(ref − pos)` on a reference point leashed at 0.5 m, caps speed, then sends a bare velocity setpoint to PX4 through MAVROS in the simulator | `swarm_commander.py:1415-1421, 1879-1976`; `position_hold.py:50-147` |
| One-drone simulator config with teleop on: `teleop_single_ours.yaml` (`teleop_drones: drone_1`, `teleop_max_speed_mps 2.0`, fences off) | `AirStack/robot/ros_ws/src/svg_ground_control/config/` |
| One existing plug-in-point session: `~/flight_logs/sim/sim_teleop_frame_run1/` (mcap bag 139 MB, ulog; 0.5 m/s pushes for 2 s in four directions) | ledger #32 |
| The AirStack simulator runs about 1.33 times faster than wall clock (PX4 lockstep); bag stamps are wall time; vehicle time = wall × scale from the ulog | `tools/ISAAC_REALTIME_NOTE.md`; `tools/hover_step_timescale.py` |
| The commander runs at 20 Hz wall, i.e. about 15 Hz of vehicle time in the simulator; on the real drone 20 Hz is vehicle time | consequence of the line above |
| `cbf_filter.py` imports only numpy and its package `__init__` is empty: importable without ROS | research check, numpy 1.26.4 |
| PX4 1.14.3 and 1.16.1 differ in the velocity loop (new velocity notch and low-pass filters, restructured anti-windup); position P step unchanged | `~/PX4-Autopilot`, `git show v1.14.3:` vs `v1.16.1:` |
| No bag reader on the host (`mcap`, `rosbags` absent); no `pip install` allowed | env check |
| `tools/sim.sh up` always spawns 3 drones and writes only under `~/flight_logs/sim/_stack/`; `sim.sh test` would need a new folder under `tools/` (not allowed) | `tools/sim.sh:91-94, 621` |

## Global Constraints

- Write only inside `svg_training/`. `tools/`, `AirStack/`, `docs/` of the repository are read-only. Running `tools/sim.sh` is approved (owner, 14 November 2026); editing it is not.
- Writes outside `svg_training/` that the simulator itself makes are allowed and must be listed in each run's record: `~/flight_logs/sim/_stack/`, `~/flight_logs/sim/uncollected_<date>/`, `AirStack/robot/ros_ws/bags/<prefix>_*` (git-ignored; the session script copies the bag out and deletes it).
- No `pip install`; no YAML; configs and parameter sets are TOML.
- Never start the AirStack simulator while a benchmark or another simulator holds the GPU; never start it during a real-drone session (`tools/sim.sh up` refuses those itself).
- Fitted parameter sets are named files: `params/airstack_sim_v<k>.toml` (source bag, ulog time scale, fit date, code hash, model family, every parameter with its unit). Parameters fitted to the simulator never go to the drone (iron rule 9).
- Every fit and every parity test is a run with a gates table written before it, a record and a ledger row (T2, T3, …), like S0.
- Units in names; shapes in docstrings; tier 1 code stays batched and Isaac-free.
- Wording: "observed in the training simulator / AirStack simulator"; Guard team, Strike team.

## Review Focus

1. **Wall time versus vehicle time.** A fit on wall-time stamps is 33 % off. Every fit converts to vehicle time first and the record states the scale used. Test in Task 3.
2. **Commander shaping in the response.** The fitted model goes from the plug-in command to the measured velocity, so it must include the ramp and the reference P term; a fit to PX4's own setpoint would skip them. Test in Task 3 (fit input is `teleop_command`, not `setpoint_raw`).
3. **Over-fitting a model family.** Parameters are fitted on half of the steps and judged on the other half. Test in Task 3.
4. **A batched filter that silently differs from CMU's.** The port is compared with the original on thousands of scenes, including infeasible ones that trigger CMU's emergency push-apart. Test in Task 7.
5. **The filter acting across teams.** A Guard–Strike pair must never be constrained, by construction and by test. Test in Task 7.

---

### Task 1: S1 config and gates (owner approval)

**Files:** Create `configs/s1.toml`; Test `tests/test_s1_config.py`.

**Produces:** tables `[fit_gates]`, `[filter_gates]`, `[steps]`, `[filter_bench]`.

PROPOSED values, for the owner to approve or change before any run:

```toml
[fit_gates]                       # judged on held-out steps only, vehicle time
vel_rms_max_mps = 0.10            # RMS of measured minus model velocity over each held-out step window
t63_err_max_s = 0.10              # |time to 63 % of the step|, model vs measured, worst held-out step
delay_range_s = [0.0, 0.40]       # fitted pure delay must be physically plausible
min_held_out_steps = 8

[filter_gates]
max_abs_dv_mps = 0.02             # port vs cbf_filter.py, scenes where the original converged without emergency
constraint_residual_max = 2.0e-3  # every pair constraint of the port, same tolerance as the original
emergency_agreement_min = 0.99    # fraction of scenes where both agree on "emergency push-apart used"
cross_team_corrections = 0        # Guard–Strike pairs: exactly zero correction
scenes = 2000                     # random scenes, 2–8 drones, 1 or 2 teams, near-collision heavy

[steps]                           # designed step session in the AirStack simulator (Task 5)
speeds_mps = [0.5, 1.0, 2.0]
axes = ["x", "y", "z"]
hold_s = 3.0                      # wall time per step
signs = [1, -1]
repeats = 2

[filter_bench]                    # throughput with the filter on (informational)
cases = ["t1_5v3_open", "t1_5v3_full"]
num_games = [1024, 4096, 16384]
```

- [ ] Write `tests/test_s1_config.py`: the file parses with `tomllib`; every key above exists with the stated type; `len(speeds)×len(axes)×len(signs)×repeats ≥ 2·min_held_out_steps`.
- [ ] Run it (fails), write the file, run it (passes). The lead takes the values to the owner; nothing in Tasks 4, 6, 7, 8 runs before approval.

### Task 2: Bag to CSV, inside CMU's robot image

**Files:** Create `scripts/bag_to_csv.py`, `scripts/extract_bag.sh`; Test `tests/test_bag_to_csv.py`.

**Produces:**
- `scripts/extract_bag.sh <bag_dir> <out_dir>`: `docker run --rm` of `airlab-docker.andrew.cmu.edu/airstack/airstack:v0.18.0_robot-x86-64_dev` with the bag mounted read-only and `out_dir` mounted read-write, runs `bag_to_csv.py`, hands files back to the caller (same `find -user root … chown` as `docker/run.sh`).
- `bag_to_csv.py`: writes `teleop_command.csv` (`t_wall_s,vx,vy,vz,yaw_rate`), `velocity_command.csv` (same columns), `odometry.csv` (`t_wall_s,x,y,z,vx,vy,vz,qw,qx,qy,qz`), `commander_status.csv` if present. Pure row-conversion functions `twist_row(msg, t)`, `odom_row(msg, t)` are separate from the rosbag2 reading, so they are tested on the host with fake message objects.

- [ ] Tests (host, no ROS): fake objects with `.twist.linear.x` etc. produce the exact rows; the script refuses an output folder that is not empty.
- [ ] Integration check (not a pytest test): run `extract_bag.sh` on `~/flight_logs/sim/sim_teleop_frame_run1/teleop_frame_20261102_191344` into `runs/s1_extract_check/`; expect about 1,182 teleop rows and about 12,745 odometry rows (the counts in the bag's `metadata.yaml`).

### Task 3: Response model and fitting (NumPy reference)

**Files:** Create `source/svg_training/models/response.py` (NumPy reference simulator), `source/svg_training/models/fit.py`; Test `tests/test_fit.py`.

**Produces:**
- `simulate(cmd: ndarray[T,3], dt_s: float, p: ResponseParams) -> ndarray[T,3]`: the model family. `ResponseParams` (dataclass): `delay_s`, `tau_xy_s`, `tau_z_s`, `acc_max_xy_mps2`, `acc_max_z_mps2`, `speed_cap_mps`, `family` (`"lag1"` = delay + first-order lag + acceleration limit; `"lag2"` adds a second pole `tau2_s`). Delay is fractional (linear interpolation between samples) so it can be fitted continuously.
- `to_vehicle_time(t_wall_s, scale) -> ndarray`; `segment_steps(cmd, t, min_jump_mps=0.2) -> list[(start, end)]`.
- `fit(cmd, vel, t_vehicle, family, train_idx) -> (ResponseParams, report)` with `scipy.optimize.least_squares` on the velocity error of the training steps; `evaluate(p, segments, held_out_idx) -> {"vel_rms_mps", "t63_err_s", per-step table}`.
- Train/held-out split: alternate steps (even indices train, odd held out), fixed and recorded.

- [ ] Tests: data simulated with known parameters (delay 0.12 s, τ 0.5 s, acc 3 m/s², noise σ 0.01) is recovered within 5 %; a wall-time input with scale 1.33 gives a delay 1.33 × too small unless `to_vehicle_time` is applied (Review Focus 1); `fit` refuses `setpoint_raw` input by column name check (it must be the teleop command, Review Focus 2); held-out metrics use only held-out steps (Review Focus 3); `lag2` reduces to `lag1` when `tau2_s → 0`.

### Task 4: Fit v0 on the existing session (no new simulator run)

**Files:** Create `scripts/fit_response.py`, `params/airstack_sim_v0.toml`, `records/<date>_s1_fit_v0_record.md`; Modify `records/LEDGER.md`.

- CLI: `fit_response.py --csv-dir runs/s1_extract_check --ulog <ulog> --family lag1 --name <date>_s1_fit_v0 --gates configs/s1.toml` reads the time scale from the ulog arm→disarm span against the bag span (port the 10 lines of `tools/hover_step_timescale.py` logic; record the source path), fits both families, keeps the one with the lower held-out RMS, writes the parameter file, a record (first line names the AirStack simulator and the session; gates PASS/FAIL; a plot of measured vs model for every held-out step under `runs/`) and a ledger row.
- [ ] Run it. The session has only 0.5 m/s pushes in four directions, so expect too few held-out steps for `min_held_out_steps`: v0 is then a FAIL recorded as such, and its parameters are still the first fitted set (better than the placeholder). The record says so.

### Task 5: Designed step session in the AirStack simulator

**Files:** Create `scripts/record_steps.sh`, `scripts/virtual_stick.py`; Test `tests/test_record_steps.py`.

**Produces:**
- `virtual_stick.py` (runs inside the robot container; pattern of `tools/sim_tests/teleop_frame/fly.sh:82-333`, re-written, not copied): calls `/swarm_commander/takeoff`, waits for "holding takeoff position" on `/svg/commander_status`, calls `start`, then publishes on `/svg/drone_1/teleop_command` at 20 Hz: for each step in `[steps]`, zero for 2 s, the step for `hold_s`, zero; publishes zeros on exit; calls `land`.
- `record_steps.sh [--dry-run] <name>`: refuses if a simulator, benchmark or real-drone bridge is up (as `tools/sim.sh up` does, plus a GPU-busy check); `tools/sim.sh up --headless`; in the robot container starts the commander with `teleop_single_ours.yaml scenario:=hover record_bag:=true bag_prefix:=svg_s1_<name>` (only `drone_1` is commanded; the other two spawned drones stay on the ground); `docker cp` + runs `virtual_stick.py`; waits for "landed"; copies the bag and the ulog into `runs/<name>/`; deletes the bag from `AirStack/robot/ros_ws/bags/`; `tools/sim.sh down`. A trap lands the drone and brings the simulator down on Ctrl-C. Writes `runs/<name>/outside_writes.txt` listing everything written outside `svg_training/`.
- [ ] Tests: `--dry-run` prints every command and creates nothing; the step list printed by `virtual_stick.py --print-plan` matches `[steps]` (36 steps with the proposed values); refusal when the GPU-busy check reports a Kit or python process.
- [ ] One real session (about 15 minutes; Isaac starts in the AirStack docker; the owner has accepted the WiFi risk): `bash scripts/record_steps.sh <date>_s1_steps`.

### Task 6: Fit v1 on the designed steps

- [ ] `extract_bag.sh` on the new bag; `fit_response.py … --name <date>_s1_fit_v1` → `params/airstack_sim_v1.toml`, record T(n), ledger row. Gate: `[fit_gates]`. If it fails, `lag2` and a per-axis delay are the next families to try, each a new run.

### Task 7: Batched safety filter with team mask

**Files:** Create `source/svg_training/core/safety_filter.py`; Test `tests/test_safety_filter.py`, `scripts/filter_parity.py`.

**Produces:** `filter_velocities(nominal_mps: Tensor[N,M,3], pos_m: Tensor[N,M,3], pair_mask: Tensor[M,M] bool, safety_radius_m: float, max_speed_mps: float | Tensor[N,M,1], alpha: float = 2.5, iterations: int = 60) -> FilterResult(velocities [N,M,3], corrected [N,M] bool, residual [N], emergency [N] bool)`. Same barrier and constraint as `cbf_filter.py` (`h = |Δp|² − (2r)²`, `2Δp·Δv + αh ≥ 0`, speed cap), solved by a fixed number of parallel Dykstra sweeps (no per-scene loop); pairs outside `pair_mask` are dropped; the emergency push-apart is applied per scene when the residual after the sweeps exceeds `5 × 2e-3` (same rule as the original).
- `team_pair_mask(guards: int, strikes: int) -> Tensor[M,M]`: True only within a team.
- `scripts/filter_parity.py --gates configs/s1.toml --name <date>_s1_filter_parity`: generates `scenes` random scenes (seeded), runs CMU's `filter_velocities` (imported from `../AirStack/robot/ros_ws/src/svg_ground_control/` by `sys.path`, read-only; the record states its git blob hash) one scene at a time and the port batched, applies `[filter_gates]`, writes a record and a ledger row.
- [ ] Tests: no conflict → nominal unchanged; two drones head-on inside the keep-out → port and original agree within `max_abs_dv_mps`; a Guard–Strike pair on collision course → zero correction (Review Focus 5); speed cap respected; `iterations` is the only loop.
- [ ] Run `filter_parity.py` (CPU, a few minutes).

### Task 8: Tier 1 with the fitted model and the filter

**Files:** Create `source/svg_training/models/fitted.py`; Modify `source/svg_training/envs/tier1_bench.py` (new optional config fields only), `scripts/benchmark_tier1.py`; Test `tests/test_fitted.py`.

**Produces:** `FittedResponse(n_games, n_drones, params: ResponseParams, dt_s, device)` with the same `step`/`reset` interface as `PlaceholderResponse`; `Tier1BenchCfg.response = "placeholder" | <path to params toml>` and `Tier1BenchCfg.safety_filter: bool = False` (filter applied within each team, between the action scaling and the response model).
- [ ] Tests: `FittedResponse` matches `models.response.simulate` on the same command sequence within 1e-5 m/s (one model, two implementations); the placeholder path is unchanged; with `safety_filter=True` two same-team drones never come closer than the keep-out in a scripted head-on run.
- [ ] Throughput with the filter (informational, no gate): `benchmark_tier1.py` on `[filter_bench]` cases, results and a short record.

### Task 9: Hand-over

- [ ] `docs/claude/HANDOFF.md` §0 and §4 updated; STANDARDS §5 rows "Response to a bare velocity command" and "PX4 versions differ" updated with MEASURED values and record links; `train-gatekeeper` reads each S1 record.

## What S1 does not do

- No fit to the real drone (needs logged velocity steps on the Starling; a later run, and the `real` parameter set).
- No rigid-body cross-check (S4) and no game, reward or policy (S2).
