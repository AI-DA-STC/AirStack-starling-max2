> 15 November 2026 · author: investigator agent, reviewed by the lead · status: confirmed in code and in the bag; the cause behind T3 = FAIL ([S1 results](../S1_RESULTS.md)); copied unchanged from the working notes for the final review, except one note on a local folder.

# S1 task 4: why the teleop response peaks, sags and reverses

Read-only investigation, 2026-11-15. Session: `~/flight_logs/sim/sim_teleop_frame_run1/teleop_frame_20261102_191344` (AirStack simulator, one drone, five 0.5 m/s pushes held 2.0 wall s each). Code at the live clone's `main`; no commit touched `swarm_commander.py`, `position_hold.py` or `mavros_interface.cpp` since 2026-11-02, so this is the code that flew the session.

## Answer in one paragraph

**Confirmed in code and in the bag.** The commander's own output already sags and reverses; PX4 only smooths it. In the simulator the commander moves its teleop reference point by `stick × 0.05 s` per 20 Hz **wall-clock** tick. PX4 runs in lockstep **vehicle** time, about 1.9 times faster than the wall clock (σ = 1.907 vehicle s per wall s). So a drone flying at the commanded speed outruns the reference point. The P term `kp·(ref − pos)` turns negative and pulls the command down to about `stick/σ` (52 %). On release the drone is about 0.24–0.30 m past the reference point, so the P term flies it back. The whole push moves the drone by `stick × hold time in wall seconds`: 1.00 m commanded, 0.99–1.02 m measured. A replay of the commander's law from the bag reproduces its published setpoint to within 0.019 m/s on every tick of all five pushes.

## Q1. What the commander does with a teleop command

**Config in force: `teleop_single_ours.yaml` at commit 82d9436.** `tools/sim_tests/teleop_frame/test.env:9` says `CONFIG=teleop_single_ours.yaml`. The session started 2026-11-02 19:13:44 UTC (03:13 SGT on 11-03). That is 12 min before commit 9b3d79d (03:25 SGT), which turned both fences off. `params_start_swarm_commander.yaml` beside the bag still shows `teleop_fence_enabled: true`, and `commander_status` agrees. The commander was not running `cbf_sim.yaml`: that file has `teleop_drones: ""` and three drones.

**Values in force** (from `params_start_swarm_commander.yaml`, unchanged at the end of the session): `control_rate_hz` 20 (dt 0.05 s **wall**, `use_sim_time: false`), `teleop_kp` 1.0, `teleop_lead_m` 0.5, `teleop_accel_mps2` 5.0, `teleop_max_speed_mps` 2.0, `teleop_timeout_s` 0.5, `cbf_max_speed_mps` 2.0, `cbf_safety_radius_m` 0.55, teleop fence on, x −3..3, y −1.5..1.5, z 0.3..2.5, `fence_keep_in_gain` 0.7, `fence_brake_accel_mps2` 2.0, `fence_margin_m` 0.

**The path, one 20 Hz tick** (`swarm_commander.py` unless stated):

| Step | Where | What it does |
|---|---|---|
| Subscribe | :894–897, callback :1415–1421 | stores the TwistStamped linear xyz and yaw rate with its arrival time; no deadband |
| Timer | :984–986 | `create_timer(0.05)`: **wall clock** |
| Output kind | :865–873, :887 | `drone_modes: sim` → output `velocity`, TwistStamped on `/drone_1/interface/velocity_command` |
| 1. Reference advance | :2035–2037 → :1951–1968 → `position_hold.py:85–113` | `ref += applied·dt`, where `applied` is the last *stick part* published (patch 0006, :2310–2314); horizontal and vertical leash 0.5 m (`position_hold.py:62–82`); clamped into the teleop fence box (:1966–1968) |
| 2. Stick | :1879–1894 | zero if no message for 0.5 s; capped at 2.0 m/s |
| 3. Ramp | :1896–1910, `position_hold.py:116–147` | slews to the stick at 5 m/s² per wall s (0.25 m/s per tick: 0.5 m/s in 2 ticks); the ramp's acceleration is **dropped** on the velocity output |
| 4. P + feedforward | :1912–1927, `position_hold.py:50–59` | `u = s + kp·(ref − pos)`, speed cap 2.0 |
| 5. CBF | :2135–2147 | one drone, so there are no pair constraints; only the 2.0 m/s cap; never active in the session |
| 6. Keep-in fence | :2207–2210 → :1795–1830, `fence.py:88–133` | per axis, outward speed ≤ `brake_speed(d; a=2, L=1/0.7)`; 0.5 m/s is allowed until 0.78 m from a wall |
| 7. Publish | :2239–2315 (:2299–2306) | TwistStamped (vx, vy, vz, yaw rate); no position and no acceleration |
| Interface | `mavros_interface.cpp:478–497`, `interface.launch.py:87` | `mavros/setpoint_raw/local` PositionTarget, FRAME_LOCAL_NED, velocity only (position, accel and yaw ignored) |

**On release there is no separate hold mode.** The stick ramps to 0 in 2 ticks, and `u = kp·(ref − pos)` holds the reference point, which stops where it is (`position_hold.py:1–12`).

**The body-frame bug (:1412) does not touch this path.** `drone.velocity` reaches teleop only through `advance_reference`'s `v_meas` on a seed or leash pull. That value is overwritten by `publish_command` (:2313) before the next tick. The leash never pulled anyway: |ref − pos| ≤ 0.30 m. `drone.velocity` also feeds `keep_in_acceleration` (:1809), but the velocity output drops that acceleration. The brief's "yaw ≈ 0" is not true for this session: the Drive-mode pushes ran at headings +0.5°, −87°, −177°, +94° and +177°. The fit already rotates the odometry to world.

## Q2. Does the law predict the shape? Yes

Use vehicle time τ, σ = vehicle s per wall s, stick s, and e = ref − pos. The reference moves at s per wall second, which is s/σ per vehicle second. PX4 treats u as m per vehicle second:

```
de/dτ = s/σ − v,      u = s + kp·e,      v ≈ PX4 lag of u
```

**Steady state while held** (v = u, de/dτ = 0):

```
u_ss = v_ss = s/σ             = 0.5/1.907 = 0.262 m/s  → 52 % of the command
e_ss = (s/σ − s)/kp = −s(1 − 1/σ)/kp  = −0.238 m       (drone 0.24 m AHEAD of its reference)
```

**Release** (s → 0): `u = kp·e`. The setpoint jumps to about −0.24 m/s (−48 %) and gets more negative while the drone coasts forward: e reaches −0.26 to −0.30 m, so u reaches −0.52 to −0.60 of the command. e then decays with `de/dτ = −kp·e` behind the PX4 lag. With kp = 1 and a PX4 lag τ_p ≈ 0.8 s, the loop `τ_p·ë + ė + kp·e = 0` has ωn = 1.12 rad/s and ζ = 0.56. It is underdamped, which gives the early peak and the slow return. **Peak:** at first the drone lags its reference, so e > 0 and u reaches 1.16–1.23 × the command at about 0.3–0.5 wall s. e crosses zero at about 0.75 wall s (1.4 vehicle s), which is the velocity peak, and the sag follows. At σ = 1 the law gives e_ss = 0 and v → s: **no sag**.

**Measured, per push** (fractions of the command; t in vehicle s):

| Push | Axis, heading | Commander u: peak / last held / min after | Velocity: peak (t) / at release / min after | e min (m) | Moved (m) vs stick·T_wall |
|---|---|---|---|---|---|
| 0 | +x, +0.5° | 1.18 / 0.54 / −0.60 | 0.81 (1.51) / 0.50 / −0.29 | −0.30 | 1.020 vs 1.000 |
| 1 | −y, −87° | 1.23 / 0.52 / −0.53 | 0.86 (1.52) / 0.59 / −0.24 | −0.26 | 1.004 vs 0.999 |
| 2 | −x, −177° | 1.21 / 0.68 / −0.54 | 0.84 (1.58) / 0.63 / −0.25 | −0.27 | 1.007 vs 0.998 |
| 3 | +y, +94° | 1.16 / 0.70 / −0.52 | 0.82 (1.73) / 0.64 / −0.25 | −0.26 | 0.991 vs 0.998 |
| 4 | +x, +177° | 1.21 / 0.70 / −0.54 | 0.86 (1.70) / 0.65 / −0.25 | −0.27 | 1.013 vs 1.000 |

"Last held" is 0.52–0.70, against a steady state of 0.52. The 3.8 vehicle-s hold is too short for the underdamped loop to settle. The time scale is also not constant: σ measured over each push from position over integrated velocity is 1.74–2.06, which puts s/σ at 0.49–0.58.

**Replay check** (`replay.py` in the scratchpad below). The commander law above (steps 1–6) was run from the bag's `teleop_command` and odometry positions. Its output matched `/drone_1/interface/velocity_command` with a median per-tick error of 0.000 m/s and a maximum of 0.012–0.019 m/s on all five pushes. The teleop fence clipped 5 ticks near y = −1.2 in push 1 only (0.07 m/s at most). Without the fence, push 1's maximum error is 0.071 m/s.

**Other suspects, ruled out as the cause.** The PX4 velocity loop (`MPC_XY_VEL_P/I/D_ACC` 1.8 / 0.4 / 0.2) cannot make a sag or a reversal by itself: it only smooths the setpoint. `MPC_ACC_HOR` 6, `MPC_XY_VEL_MAX` 20 and `MPC_TILTMAX_AIR` 45 never bind at 0.5 m/s. The CBF with one drone is a 2 m/s cap only. The keep-in fence acts briefly in push 1 only. The sim airframe (iron rule 9) affects only how fast PX4 follows u, not its shape.

## Q3. What PX4 receives, and is it in the bag? Yes

Velocity only. The commander publishes TwistStamped `/drone_1/interface/velocity_command` (world ENU) at 20 Hz. MAVROS sends it to PX4 as `/drone_1/interface/mavros/setpoint_raw/local` (FRAME_LOCAL_NED, type mask ignores position, accel and yaw). The bag `metadata.yaml` lists:

- `/drone_1/interface/velocity_command`: 1339 messages. `bag_to_csv.py` already extracts it as `velocity_command.csv` (in `runs/s1_extract_check/`, a local working folder that git ignores; re-create it with `scripts/extract_bag.sh`).
- `/drone_1/interface/mavros/setpoint_raw/local`: 1339 messages (same stream after MAVROS).
- `/drone_1/interface/mavros/setpoint_raw/target_local`: 4246 messages (PX4's echo of what it is tracking).
- The ulog has `trajectory_setpoint` (logged at 5 Hz) and `vehicle_local_position` (100 Hz), both in vehicle time.

Other topics of interest: `/drone_1/odometry_conversion/odometry` (12745, body-frame twist) and `/drone_1/interface/mavros/local_position/velocity_local` (12741, world-frame twist).

**So the pipeline can copy the commander exactly and fit only PX4.** First fits of PX4's own response (commander setpoint → world velocity), main axis, vehicle time, train = pushes 0, 2, 4, held out = 1, 3. Windows run from −0.5 to +6.0 wall s around each push start: longer than the s1 record's, so these RMS values are not directly comparable with its 0.123.

| Model of PX4 (u → v) | Source of u | Train RMS (m/s) | Held-out RMS (m/s) | Parameters |
|---|---|---|---|---|
| lag1 | bag `velocity_command` | 0.045 | 0.045, 0.044 | τ 0.875 s, delay 0 |
| lag1 + acceleration cap | bag `velocity_command` | 0.038 | 0.036, 0.041 | τ 0.05 s, a_max 0.35 m/s² |
| lag1 | ulog `trajectory_setpoint` | 0.036 | 0.047, 0.047 | τ 0.775 s |
| lag1 + acceleration cap | ulog `trajectory_setpoint` | 0.031 | 0.039, 0.040 | τ 0.05 s, a_max 0.40 m/s² |
| PX4 PID with gains as set + attitude lag | bag | 0.084 (all) | — | does not fit |
| **Black box (today's approach), stick → v, lag1, same windows** | `teleop_command` | 0.087 | 0.081, 0.081 | τ 0.40 s |

**Closed loop** (commander copy plus lag1, driven only by `teleop_command`, σ = 1.907): held-out RMS 0.036 and 0.042. Its shape gives peak 0.88 (measured 0.81–0.86), release 0.54–0.55 (measured 0.50–0.65) and minimum after release **−0.41 (measured −0.24 to −0.29)**. The acceleration-cap variant does better on RMS (0.032, 0.038) but worse on shape: peak 1.01, minimum −0.49. The sag is reproduced; the reversal depth is not yet. The measured drone rises slowly after a step but follows a slowly changing setpoint closely, which neither form captures. The PX4 model structure needs one more round of work, judged on the shape numbers and not on RMS alone.

## Q4. Recommendation: (b), with σ as an explicit parameter

| Option | What it is | Cost | Verdict |
|---|---|---|---|
| (a) black-box lag, teleop → velocity | today's fit | none to build; cannot pass, because the shape comes from a closed loop with an integrator in wall time (held-out 0.12 on the record's windows, 0.081 here); it would also train the policy on a simulator artefact | drop |
| **(b) commander copy + fitted PX4 lag** | port steps 1–6 (ramp, reference with leash and fence clamp, P + feedforward, caps, keep-in fence) at 20 Hz zero-order hold, reference advanced in wall time = vehicle dt/σ | about 60–80 lines plus a vectorised version (per drone: ref 3, stick-published 3, tick phase); a regression test that replays this bag to ≤ 0.02 m/s (done once here); pin the copy to the git blobs of `swarm_commander.py` and `position_hold.py`, as the record pins its ported tools; one more PX4-structure iteration (above) | **do this** |
| (c) remove the cause | run the commander on sim time (`use_sim_time`, or dt from `/clock`), then re-record | a change to flight code (CHG entry, sim re-validation, CMU-owned file); does not tell the pipeline what the real drone does | owner's call, separate from S1 |

**Why (b), and how to use σ.** With σ = 1.907 the model reproduces the AirStack simulator; with σ = 1 it is what the same law does in real time (no sag, e_ss = 0). To match AirStack, randomise σ over 1.7–2.1, the range measured in this session. The real drone does not use this path: `real_command_mode: trajectory` (:869–871) sends the reference as a position setpoint with the stick as feedforward, and PX4 holds the reference itself. A response model meant to carry over to the real drone needs the trajectory-output law plus a real-drone fit, and no data for that exists in this session. Fit PX4 open loop on (`velocity_command` or ulog `trajectory_setpoint`) → velocity. Then judge the closed-loop model on peak, release and post-release minimum per held-out push, not on RMS only.

**Scripts (temporary, not in the repo):** `/tmp/claude-1000/-home-jeremychia/2b67e152-f4d0-40c1-8b77-4ead5185a30b/scratchpad/` holds `seg.py` (per-push tables), `replay.py` (commander replay against the bag), `px4fit.py`, `ulogfit.py`, `e2e.py` and `e2efit.py` (open-loop and closed-loop PX4 fits).
