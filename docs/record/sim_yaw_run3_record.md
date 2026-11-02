RECORD · SIM — sim_yaw_run3. Sim-only (iron rule 9): none of these values is ported to the drone; the sim airframe's yaw gains and any gain the sweep sets live are sim-only (iron rule 9).

# sim_yaw_run3 — one-drone yaw-step: heading ring-down after a yaw pulse, PX4 vehicle time (started 2026-11-02T21:52:22+08:00 +08; flight 13:54:06–13:56:55 UTC)

**Verdict: PASS.** Measure how the sim drone's heading settles after a yaw pulse is released (overshoot, ring, settle time, swing-back rate, drift) from the PX4 ulog in vehicle time, so the sim airframe's yaw gains can be retuned; the keyboard sessions of 2026-10-30 showed a ±8–17° ring at ~0.8 Hz. For Linear NEAR-789 (milestone S5). PASS = every gate PASS; INCOMPLETE = no FAIL but ≥ 1 gate UNVERIFIED; FAIL = any gate FAIL; ABORTED = Ctrl-C landing, never a result. Report generated 2026-11-02 at repo `0683b81`.

**Scope:** PX4's own sim state estimate positions the drone (no mocap, no camera); flat default world; one drone; commander teleop input only (safe_teleop and the keyboard not in the loop); time gates read PX4 vehicle time from the ulog.

## Setup

| Item | Value |
|---|---|
| Sim | Isaac Sim, 1 Starling 2 Max (`DRONE_USD=starling2max.usd`, `PX4_VEHICLE_MODEL=pegasus_starling2max`), default flat world |
| Airframe | `10090_pegasus_starling2max` (sim-only airframe gains, see the S5 hover records) |
| Commander | `teleop_single.yaml scenario:=hover`, tuning {"teleop_max_speed_mps": 2.0, "goal_accel_mps2": 3.0, "goal_settle_s": 0.3, "scenario_speed_mps": 0.6} |
| Driver | `tools/sim.sh test yaw_step`, repo commit `0683b81040f0168828da5bffed808fd316c7bffb` (tools/ uncommitted changes: 0) |
| Started | 2026-11-02T21:52:22+08:00 +08 (laptop clock, `run_meta.txt`); flight 13:54:06–13:56:55 UTC (container clock) |
| Video | none recorded |

## Changes in this run

What changed while this run flew (docs/CODING_STANDARD.md §3), from three sources. PX4's own list (the ulog) is the ground truth and wins a conflict.

**Logged by the tools (`changes.log`):**

none logged

**PX4 ulog, parameters changed after boot (vehicle time, t > 2 s; 46 boot-time settings not listed):**

none after boot

**Parameter snapshot, start → end of the flight (MAVROS for PX4, `ros2 param dump /swarm_commander`; catches Foxglove, QGC, `ros2 param set`):**

```
drone_1/COM_FLIGHT_UUID 0 -> 1
drone_1/LND_FLIGHT_T_LO 0 -> 310468950
```

**PX4 at the start vs the airframe file (drone_1):**

all 49 airframe values in force

**Conflicts and unlogged changes:**

- PX4 bookkeeping (not a tuning change): drone_1/COM_FLIGHT_UUID 0 → 1 (snapshot)
- PX4 bookkeeping (not a tuning change): drone_1/LND_FLIGHT_T_LO 0 → 310468950 (snapshot)

## Pass/fail

| Check | Criterion | Measured | Baseline | Verdict |
|---|---|---|---|---|
| Isaac launch: SYS_AUTOSTART=10090 x1 | SYS_AUTOSTART=10090 x1 | 1 | - | PASS |
| Isaac launch: Ready for takeoff x1 | Ready for takeoff x1 | 1 | - | PASS |
| Isaac launch: no 'Unknown model' | no 'Unknown model' | 0 | - | PASS |
| Isaac launch: no PhysX cooking warnings | no PhysX cooking warnings | 0 | - | PASS |
| Isaac launch: Starling2MaxConfig x1 | Starling2MaxConfig x1 (launcher print) | 2 | - | PASS |
| coverage: rows through the window | largest `t_s` gap over the phase-2 rows ≤ 0.5 s, ≥ 1 landing (`phase` 3) row, metrics node alive at stop | largest phase-2 gap 0.04 s; 9023 phase-2 rows, 248 landing rows | - | PASS |
| set-0 pulses flown and analysable | fly.sh stamped 2N = 6 set-0 pulses; the ulog shows the same (order, sign, onset spacing); each released with ≥ 3 s of NaN-free data after it | 6 stamped, 6 with numbers (sign + spacing match the stamps) | keyboard 2026-10-30: ±8–17° ring ~0.8 Hz, no ulog | PASS |
| heading overshoot ≤ 3.0° | max over set-0 pulses of the heading's overrun past its final value after release (PX4 ulog, unwrapped ENU) | `overshoot_deg`: worst 1.65° (pulse 0/3 (+)); 6 of 6 set-0 pulses with numbers | keyboard 2026-10-30: ±8–17° ring ~0.8 Hz, no ulog | PASS |
| settle to ±2° ≤ 2.0 s (vehicle) | time from release until the heading stays within ±2° of its final value, PX4 vehicle time; not settled in the window = FAIL | `settle_s`: worst 0.03 s (pulse 0/2 (−)); 6 of 6 set-0 pulses with numbers | keyboard 2026-10-30: ±8–17° ring ~0.8 Hz, no ulog | PASS |
| ring crossings ≤ 1 | zero crossings of (heading − final) after it first enters the band, 0.5° hysteresis | `ring_crossings`: worst 1 (pulse 0/1 (+)); 6 of 6 set-0 pulses with numbers | keyboard 2026-10-30: ±8–17° ring ~0.8 Hz, no ulog | PASS |
| swing back ≤ 30 °/s | yaw_core `peak_rate_dps`: fastest body yaw rate AGAINST the turn in [release, +3 s] (PX4 vehicle_angular_velocity); `peak_rate_abs_dps` is info | `peak_rate_dps`: worst 11.8 °/s (pulse 0/3 (+)); 6 of 6 set-0 pulses with numbers | keyboard 2026-10-30: ±8–17° ring ~0.8 Hz, no ulog | PASS |
| xy drift ≤ 0.15 m | max horizontal distance from the onset position over pulse + window (PX4 vehicle_local_position) | `xy_drift_m`: worst 0.056 m (pulse 0/1 (+)); 6 of 6 set-0 pulses with numbers | keyboard 2026-10-30: ±8–17° ring ~0.8 Hz, no ulog | PASS |
| yaw sign | +angular.z (ENU, CCW) raises the ENU heading: ulog `turn_deg` and live `heading_rel_deg` change over the pulse both along the command | ulog `turn_deg` along the command 6/6, live `heading_rel_deg` change 6/6 (pulse 0/1 (+): ulog +110.3°, live +96.1°) | - | PASS |
| booted gains = airframe file | ulog header MC_YAW_P, MC_YAWRATE_P/I/D/K = the `param set-default` lines of 10090_pegasus_starling2max (rel 1e-3), and set 0 flew them | ulog header MC_YAW_P 2.8, MC_YAWRATE_P/I/D/K 0.25/0.2/0/1 = airframe file | - | PASS |
| live vs ulog overshoot | per set-0 pulse, overshoot from live `heading_rel_deg` (yaw_core.measure_pulse on metrics.csv, stamps via t0_unix) within 1.0° of the ulog's | max \|live − ulog\| 0.08° (pulse 0/3 (+): live 1.57°, ulog 1.65°); 6 of 6 compared | - | PASS |
| live parameter changes logged | informational (no sweep in this run) | none — ulog and changes.log list no change | - | info |
| sweep completed | informational (no sweep in this run) | set 0 only; 1 set(s) flown | - | info |
| booted gains restored | informational (no sweep in this run) | nothing to restore | - | info |
| landed, disarmed (commander ACK) | informational (ACK log, not an arming display) | drone_1 | - | info |
| post-flight armed=false x1 (MAVROS state) | armed: false for drone_1 | drone_1 false | - | PASS |
| live vs bag recompute | live metrics.csv agrees with the rosbag recompute (heading_rel_deg within tolerance; flags by count) | heading_rel_deg Δmax 0 (tol 0.5); heading_deg Δmax 0 (tol 0.5); yaw_rate_dps Δmax 0 (tol 2); xy_drift_m Δmax 0 (tol 0.02); fence_breached Σ 0 vs 0; emergency Σ 0 vs 0; unpaired 0.0 %; bag unpaired 0.8 % | - | PASS |
| rosbag copied + readable | bag dir yaw_step_* with metadata.yaml under the heavy folder, and metrics.csv, metrics_bag.csv in the run folder | yaw_step_20261102_135304: 581 MB, metadata.yaml present | - | PASS |
| PX4 ulogs one per sysid 2 | ulog_sysid_map.txt lists sysids 2 (drone_1) | 1 files, sysids ['2'] | - | PASS |
| WiFi firmware alerts | 0 during the run | 0 | - | PASS |
| code that ran | informational (run_meta.txt head vs git HEAD at report time) | ran at 0683b81 | - | info |
| pulse 0/1 (+) | informational (set 0; PX4 ulog, vehicle time) | on 197.1 s, os 1.1°, settle 0.01 s, ring 1, swing 11 °/s (abs 56), drift 0.06 m, plat 56 °/s, scale 2.04 | - | info |
| pulse 0/2 (−) | informational (set 0; PX4 ulog, vehicle time) | on 241.0 s, os 1.5°, settle 0.03 s, ring 1, swing 11 °/s (abs 56), drift 0.04 m, plat 56 °/s, scale 2.09 | - | info |
| pulse 0/3 (+) | informational (set 0; PX4 ulog, vehicle time) | on 285.5 s, os 1.7°, settle 0.02 s, ring 1, swing 12 °/s (abs 56), drift 0.05 m, plat 56 °/s, scale 2.05 | - | info |
| pulse 0/4 (−) | informational (set 0; PX4 ulog, vehicle time) | on 329.3 s, os 1.2°, settle 0.02 s, ring 1, swing 11 °/s (abs 56), drift 0.04 m, plat 56 °/s, scale 2.10 | - | info |
| pulse 0/5 (+) | informational (set 0; PX4 ulog, vehicle time) | on 372.9 s, os 1.0°, settle 0.03 s, ring 1, swing 11 °/s (abs 56), drift 0.05 m, plat 56 °/s, scale 1.74 | - | info |
| pulse 0/6 (−) | informational (set 0; PX4 ulog, vehicle time) | on 412.7 s, os 1.5°, settle 0.03 s, ring 1, swing 11 °/s (abs 56), drift 0.04 m, plat 56 °/s, scale 2.15 | - | info |
| pulse turn (patch-0007) | informational (0.5 rad/s for 3.14 s wall = 90° × the time scale in vehicle time, then the tap) | turn +184° at 29 °/s, not gated; flew booted gains | - | info |
| set 0: booted gains (gated) | informational (gains in force from the ulog's changed_parameters) | MC_YAW_P 2.8, MC_YAWRATE_P/I/D/K 0.25/0.2/0/1 — overshoot max 1.7°, settle max 0.03 s, ring max 1, swing max 12 °/s, drift max 0.06 m; 6 of 6 with numbers | - | info |
| patch-0007 tap | informational: room-frame +x tap after the turn; a direction error ≈ the turn angle = the body-frame orbit (before patch 0007) | direction error 2.0°, heading change -0.0°, displacement 0.98 m (vehicle 473.5–476.7 s) | - | info |
| pulse marker (U3) | informational: which PX4 topic marks onset/release | vehicle_attitude_setpoint.yaw_sp_move_rate (20 Hz; U3: it carries the pulses in offboard) | - | info |
| plateau measured vs commanded (U4) | informational: body yaw rate during set-0 pulses vs the 57.3 °/s commanded | measured 55.9–56.1 °/s, setpoint 57.3 °/s, commanded 57.3 °/s | - | info |
| time scale (vehicle s per wall s) | informational, never a gate | onset spacing median 2.086; per pulse 2.04, 2.09, 2.05, 2.10, 1.74, 2.15 | - | info |
| px4_param_changes.txt | informational: MC_YAW* changes PX4 applied (vehicle time) | none | - | info |
| odometry yaw rate (U5) | informational: odometry twist.angular.z (live `yaw_rate_dps`) is plotted only, never gated | present: max \|`yaw_rate_dps`\| 67.8 °/s, `heading_rel_deg` span 188° | - | info |

Rows marked info are informational and never pass or fail the run.

[Figure 1](#fig-1) plots the heading relative to the test start (live odometry, wall clock) with the ±2° settle band. Worst set-0 pulse after release, PX4 vehicle time: overshoot 1.65° (gate 3.0), settle 0.03 s (gate 2.0 s), 1 ring crossing(s) (gate 1), swing back 11.8 °/s (gate 30), drift 0.056 m (gate 0.15).

<a id="fig-1"></a>
![one-drone yaw-step: heading ring-down after a yaw pulse, PX4 vehicle time](sim_yaw_run3/fig-1.png)

*Figure 1. Heading relative to the test start (`heading_rel_deg`, unwrapped, 40 Hz odometry) against wall-clock time, with the ±2° settle band; shaded bands mark takeoff and land. The gates are measured from the PX4 ulog in vehicle time, not on this axis. Drawn from metrics.csv by `tools/sim.sh figures yaw_step <run>`.*

## Driver verdict history

Every generation of this record (`verdicts.log`, newest last; the last line is this one):

```
2026-11-02T22:08:30+08:00 head=0683b81 verdict=PASS fail=0 unverified=0
```

## Evidence

Flight script stdout (times are UTC, container clock):
```
[13:54:06] pre-takeoff: name:drone_1 state:IDLE position:[-0.017,-0.019,-0.029]
[13:54:07] takeoff: success=True, message='takeoff: drone_1'
[13:54:15] start: success=True, message='scenario "hover" running'
[13:54:15] pulses: gap 20 s (wall), 3 per direction, rate 1.0 rad/s, pulse 1.0 s, sweep 'none'
[13:54:15] swarm_commander subscribed to /svg/drone_1/teleop_command (commander subscribed); 2 s more before the first pulse
[1793627657.570681] pulse 0/1 onset sign=+1 rate=1.000
[1793627658.570789] pulse 0/1 release
[1793627678.570895] pulse 0/2 onset sign=-1 rate=1.000
[1793627679.571005] pulse 0/2 release
[1793627699.571109] pulse 0/3 onset sign=+1 rate=1.000
[1793627700.571213] pulse 0/3 release
[1793627720.571326] pulse 0/4 onset sign=-1 rate=1.000
[1793627721.571439] pulse 0/4 release
[1793627741.571567] pulse 0/5 onset sign=+1 rate=1.000
[1793627742.571689] pulse 0/5 release
[1793627762.571800] pulse 0/6 onset sign=-1 rate=1.000
[1793627763.571909] pulse 0/6 release
[1793627783.572029] turn onset sign=+1 rate=0.500
[1793627786.712149] turn release
[1793627791.712263] tap onset vx=0.500
[1793627793.212360] tap release
[13:56:39] pulse program done (rc 0); zeros published
[13:56:39] land: success=True, message='landing: drone_1'
[13:56:55] landed: name:land name:drone_1 state:IDLE position:[0.805,0.023,-0.031]
```

Metrics node log (tail):
```
[t= 798.0 s] phase=0 heading_rel_deg=nan cbf= emerg=0
[t= 799.0 s] phase=0 heading_rel_deg=nan cbf= emerg=0
[t= 800.0 s] phase=0 heading_rel_deg=nan cbf= emerg=0
[t= 801.0 s] phase=0 heading_rel_deg=nan cbf= emerg=0
[t= 802.0 s] phase=0 heading_rel_deg=nan cbf= emerg=0
[t= 803.0 s] phase=0 heading_rel_deg=nan cbf= emerg=0
[t= 804.0 s] phase=0 heading_rel_deg=nan cbf= emerg=0
[t= 805.0 s] phase=0 heading_rel_deg=nan cbf= emerg=0
[t= 806.0 s] phase=0 heading_rel_deg=nan cbf= emerg=0
[t= 807.0 s] phase=0 heading_rel_deg=nan cbf= emerg=0
[t= 808.0 s] phase=0 heading_rel_deg=nan cbf= emerg=0
[t= 809.0 s] phase=0 heading_rel_deg=nan cbf= emerg=0
```

Landing (commander ACK log) and post-flight MAVROS state:
```
[swarm_commander-2] [0m[INFO] [1793627802.216191934] [swarm_commander]: drone_1: touchdown at z=0.12 m, settling 2.0 s before disarm[0m
[swarm_commander-2] [0m[INFO] [1793627804.316246872] [swarm_commander]: drone_1: landed, disarmed (attempt 1)[0m
armed_post.txt: unreadable
```

Live vs bag recompute:

| Column | Kind | Tolerance | Max diff | Σ live | Σ bag | Paired | Unpaired | OK |
|---|---|---|---|---|---|---|---|---|
| heading_rel_deg | continuous | 0.5 | 0 | 553586 | 553586 | 51343 | 0.0 % | yes |
| heading_deg | continuous | 0.5 | 0 | 6.95002e+06 | 6.95002e+06 | 51343 | 0.0 % | yes |
| yaw_rate_dps | continuous | 2 | 0 | 4794.79 | 4794.79 | 51343 | 0.0 % | yes |
| xy_drift_m | continuous | 0.02 | 0 | 754.04 | 754.04 | 51343 | 0.0 % | yes |
| fence_breached | flag | 0 | 0 | 0 | 0 | 51343 | 0.0 % | yes |
| emergency | flag | 0 | 0 | 0 | 0 | 51343 | 0.0 % | yes |

## Files

- Repo (this folder, `docs/record/sim_yaw_run3/`): `armed_post.txt`, `bag_evidence.txt`, `bag_path.txt`, `bag_status_pre.json`, `changes.log`, `clock_check.txt`, `commander.log`, `commands.sh`, `fig-1.png`, `interfaces.log`, `isaac.log`, `isaac.log.start`, `isaac_evidence.txt`, `landing_evidence.txt`, `live_plot.log`, `metrics.csv`, `metrics_bag.csv`, `metrics_node.log`, `odom_hz.txt`, `params_diff.txt`, `params_mavros.txt`, `params_mavros_names.txt`, `params_ulog.txt`, `px4_arm_times.txt`, `px4_param_changes.txt`, `px4_param_changes_all.txt`, `res_watch.log`, `run.log`, `run_meta.txt`, `status_post.json`, `status_pre.json`, `test_stdout.log`, `topics_of_interest.txt`, `ulog_list.txt`, `ulog_sysid_map.txt`, `ulogs_copied.ok`, `verdicts.log`, `video.txt`.
- Not in the repo (`/home/jeremychia/flight_logs/sim/sim_yaw_run3/`): `drone_1_sysid2_13_52_37.ulg` (135 MB), `params_end_drone_1.yaml` (0 MB), `params_end_swarm_commander.yaml` (0 MB), `params_start_drone_1.yaml` (0 MB), `params_start_swarm_commander.yaml` (0 MB), `px4_drone_1.csv` (3 MB), `yaw_step_20261102_135304` (581 MB).

## Caveats

- The 20 s gap between pulses is wall-clock; in vehicle time it is the gap × the time scale (2.09 here; ~1.3 on the flat world). Every time gate is PX4 vehicle time from the ulog; the figure's axis is wall clock.

## Ledger row draft (docs/record/LEDGER.md table 1, #31, NEAR-789)

| 31 | 2026-11-02 | SIM | yaw step, 1 drone, teleop_single.yaml, 6 pulses ±1 rad/s per set, vehicle time: PASS — overshoot 1.65°, settle 0.03 s, ring 1, swing back 11.8 °/s, drift 0.056 m (set 0: MC_YAW_P 2.8, MC_YAWRATE_P/I/D/K 0.25/0.2/0/1); sweep 0 of 0 set(s) flown; landed + DISARMED yes | [sim_yaw_run3_record.md](sim_yaw_run3_record.md) | NEAR-789 |

