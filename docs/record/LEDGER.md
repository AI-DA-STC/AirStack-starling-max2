RECORD · SIM + REAL — append-only test ledger. Rows are never rewritten or dropped; detail lives in the linked record files.

# Test ledger

**Every row is simulation unless its third column says REAL.** Table 1 is this software (`yikuan/SVG_ground_control_dev` @ `b21d28c`, since 2026-10-07; nothing in it has touched the real drone). Table 2 is what was observed on the previous software (2026-07-20 → 2026-09-03, branch `archive/airstack-starling-max2`); those are observations to re-earn, never results on this software. Negative results stay (#5, #6, #9, #17). New rows: one line, in this format, drafted by `tools/hover_step_report.py --ledger N --issue NEAR-nnn` for the sim hover test. Results by milestone: [HTX-R1.md](../projects/HTX-R1.md), [HTX-R2.md](../projects/HTX-R2.md), [HTX-R3.md](../projects/HTX-R3.md).

## Table 1 · This software (sim only so far)

| # | Date | SIM/REAL | Result (one sentence) | Evidence | NEAR id(s) |
|---|---|---|---|---|---|
| 1 | 2026-10-19 | SIM | Starling 2 Max model spawns in Isaac Sim: `Starling2MaxConfig` ×3, airframe 10090 ×3, MAVROS connected ×3, no PhysX cooking warnings | launch log (not kept) | NEAR-782 |
| 2 | 2026-10-19 | SIM | Iris regression (env vars unset): hover thrust 0.58, x step ≈0.14 m overshoot, z settle 3.6 s — the bracket the S5 thresholds were set around | echo traces (not kept); thresholds in `tools/README.md` | — |
| 3 | 2026-10-19 | SIM | Starling hover + 1 m steps on the 10-19 asset at 0.6 m/s, wall time: thrust 0.155, x 0.002 m / 2.75 s, z 0.001 m / 0.75 s, takeoff overshoot 0.31 m — superseded by #17–#19 | echo traces (not kept) | NEAR-786 |
| 4 | 2026-10-19 | SIM | CBF crossing, 3 drones antipodal, 10-19 asset, 3 m/s cap: min pairwise distance 1.02 m (2r 1.10), no push-apart, no fence breach — baseline for the re-run, no bag | 45 s of `/svg/commander_status` (not kept) | NEAR-787 |
| 5 | 2026-10-19 | SIM | NEGATIVE: instant disarm after `land` DENIED ×3, drones stayed armed in failsafe hover → `land_settle_s` added, unit tests only (end-to-end closed by #13) | `test/test_landing_settle.py` 4 tests, 144/144 | NEAR-786 (sim landing); real: NEAR-826 |
| 6 | 2026-10-20 | SIM | NEGATIVE: Isaac Stop ▶ Play is not a drone reset — 66,530 `recv_match` tracebacks in 2 min, MAVROS ×3 `connected: false`; only a full relaunch recovers | [sim_notes_2026-10-20.md](sim_notes_2026-10-20.md) #6 | — |
| 7 | 2026-10-20 | SIM | Snapshot bump `cf719f0` → `b21d28c` applied clean (26 files, zero conflicts); 181/181 tests in the robot container | `git diff cf719f0 b21d28c`; test run (not kept) | — |
| 8 | 2026-10-20 | SIM | First landing on the dev commander, `random_goals` ×3: scenario clean; DISARM accepted drone_1, DENIED drone_2/3 → disarm retry added (185/185 tests) | [sim_notes_2026-10-20.md](sim_notes_2026-10-20.md) #8 | NEAR-786 |
| 9 | 2026-10-20 | SIM | NEGATIVE root cause: DENIED disarm = PX4 land-detector gyro gate (`LNDMC_ROT_MAX`), body rocking ~10 Hz on the floor → sim-only `LNDMC_ROT_MAX` 300; hollow 10-19 asset rebuilt (no decimation) | [sim_notes_2026-10-20.md](sim_notes_2026-10-20.md) #9; 3 ulogs (not kept) | NEAR-782 |
| 10 | 2026-10-20 | SIM | 9 Hz pitch limit cycle on the real rate gains (pitch-rate std 164 deg/s) → sim rate gains ×0.5 + gyro filters 80/40 (0.4 deg/s); never port to the drone | [sim_notes_2026-10-20.md](sim_notes_2026-10-20.md) #10 | NEAR-782 |
| 11 | 2026-10-20 | SIM | MAVROS respawn (sim-only, `mavros_px4.launch.xml`) proven with `kill -11` → restarted in ~2 s; the segfault's cause is still unknown | [sim_notes_2026-10-20.md](sim_notes_2026-10-20.md) #11 | — |
| 12 | 2026-10-20 | SIM | Sim speeds raised to the real drone's limits: `cbf_sim.yaml` 2.0 / 4.0 / 6.0, airframe `MPC_XY_VEL_MAX` 20 etc. — config change, no flight | commit `d739a73` | NEAR-787 |
| 13 | 2026-10-21 | SIM | Fresh launch on the rebuilt asset + 10-20 airframe: `random_goals`, 3 drones, 3.5 min at 2.0 m/s, 0 PhysX warnings, DISARM accepted first request ×3 | `videos/random_CBF_sim_edited.mp4`; ulog acks (not kept) | NEAR-782 |
| 14 | 2026-10-21 | SIM | Mocap bridge loopback laptop → container → PX4 message with a fake Motive (no cameras): `/drone_1/fmu/in/vehicle_visual_odometry` at 49.998 Hz | relay + container logs (not kept) | real re-earn: NEAR-816 |
| 15 | 2026-10-22 | SIM | Stereo VO (cuVSLAM) end to end on drone_1's ZED in the flat default world — pipeline works, not an accuracy result (APE RMSE 0.252 m, 480×300) | [sim_cam_run1_record.md](../../localisation/results/sim_cam_run1_record.md) | NEAR-783, NEAR-784 |
| 16 | 2026-10-22 | SIM | Stereo VO in the construction-site world, 3 drones `random_goals`: APE RMSE 0.081 m over 162 m, no jumps (reference = EKF2) | [sim_site_run1_record.md](../../localisation/results/sim_site_run1_record.md) | NEAR-785, NEAR-859 |
| 17 | 2026-10-28 | SIM | Hover + 1 m steps on the rebuilt asset, n = 1 per axis: driver verdict FAIL on 3 gates, re-analysed from the rosbag PASS (x 0.054 m / 1.86 s wall, z 0.001 m / 1.62 s wall, thrust 0.153); drone_1 ulog lost, `Starling2MaxConfig` print not captured | [sim_hover_step_run1_record.md](sim_hover_step_run1_record.md) | NEAR-786 |
| 18 | 2026-10-28 | SIM | Hover + 1 m steps, fixed tooling, 3 per axis, PX4 vehicle time: PASS — x 0.085 m / 2.47 s, z 0.033 m / 2.50 s, thrust 0.153, scale 1.324, landed + DISARMED ×3 | [sim_hover_step_run2_record.md](sim_hover_step_run2_record.md) | NEAR-786 |
| 19 | 2026-10-29 | SIM | Repeat of #18, 9 min later, same commit: PASS — x 0.095 m / 2.47 s, z 0.020 m / 2.42 s, thrust 0.153, scale 1.333, landed + DISARMED ×3 | [sim_hover_step_run3_record.md](sim_hover_step_run3_record.md) | NEAR-786 |

Notes: the Fix 1 detail (the landing path as it is now — `land_settle_s`, `SwarmCommander.landing_done()`, the disarm retry `land_disarm_step()` with `land_disarm_retry_s` 1 s × `land_disarm_retries` 5; sim closed by #13; the real `_ours` configs set `land_settle_s` 0.0 and the retry is inert there because `px4_interface.disarm()` returns true on send; re-observe at NEAR-826 and confirm DISARMED in QGC, iron rule 2) is copied from the old MILESTONES.md "Sim debt" section as the three bullets below this line.

## Table 2 · Observed on the previous software (archived)

Branch `archive/airstack-starling-max2` (`daniel/diffaero_ground_control`), 2026-07-20 → 2026-09-03. The archive's own milestone labels are not carried (they would collide with Linear's M2–M7). Desk and network rows carry no evidence file, only the archived ledger number; the flight rows A17–A21 cite the folder `~/flight_logs/2026-09-01/` (four ulogs, no per-row mapping known). No curve is drawn from these logs.

| A# | Observed | Date | Evidence | Re-earn at |
|---|---|---|---|---|
| A1 | sim: 3 SITL drones takeoff/hover/land, keyboard teleop, geofence latch + recovery (July, old software) | 2026-07-20 | archived ledger #1 | HTX-R1 ancestry — no re-earn |
| A2 | desk prep: host networking, NTP, NatNet ports clear | 2026-07-21 | archived ledger #2 | NEAR-814 |
| A3 | natnet ↔ Motive connected at 50 Hz | 2026-07-22 | archived ledger #3 | NEAR-816 |
| A4 | drone on lab WiFi, survives reboot; ping laptop ↔ drone 7–22 ms | 2026-07-22 | archived ledger #4 | NEAR-814 |
| A5 | PX4 topics on the laptop over WiFi: all 24 `/drone_1/fmu/*` topics live | 2026-07-22 | archived ledger #5 | NEAR-818 |
| A6 | EKF2 params applied via QGC (`EKF2_EV_CTRL=11`, `EKF2_MAG_TYPE=None`, …) | 2026-07-29 | archived ledger #6 | NEAR-822 |
| A7 | onboard VIO off via vision-hub conf, verified by read-back | 2026-08-11 | archived ledger #7 | NEAR-818 |
| A8 | drone WiFi moved to a space-free SSID, DHCP lease obtained | 2026-08-11 | archived ledger #8 | NEAR-814 |
| A9 | drone re-pointed at the laptop IP (`voxl_setup_real_drone.sh`), microdds client `Running, connected` | 2026-08-11 | archived ledger #9 | NEAR-818 |
| A10 | PX4 topics re-verified on the new network; `vehicle_odometry` echoes | 2026-08-11 | archived ledger #10 | NEAR-818 |
| A11 | `vehicle_status` streams ~30 Hz but echo is silent (px4_msgs mismatch) | 2026-08-11 | archived ledger #11 | NEAR-821 |
| A12 | QGC connected (drone → Mocap PC): telemetry + battery showing | 2026-08-11 | archived ledger #12 | NEAR-822 |
| A13 | mocap poses on the laptop via `./mocap.sh` at 50 Hz, tracking the hand-carried drone | 2026-08-28 | archived ledger #13 | NEAR-816 |
| A14 | EKF2 fuses the mocap pose: `fmu/out/vehicle_odometry` matches mocap within ~2 cm | 2026-08-28 | archived ledger #14 | NEAR-822 |
| A15 | RViz tracks the hand-carried drone (GIF in `assets/`) | 2026-08-28 | archived ledger #15 | NEAR-822 |
| A16 | frame hand-check: N → `pos[0]`↑, E → `pos[1]`↑, up → `pos[2]`↓ | 2026-08-28 | archived ledger #16 | NEAR-816 |
| A17 | REAL: first offboard flight — takeoff + hover under the commander, manual landing; RC kill mapped (ch8), takeover exercised | 2026-09-01 | `~/flight_logs/2026-09-01/` | NEAR-825 |
| A18 | REAL: single-goal flight (`goal_single.yaml`), drone flew to the goal and held | 2026-09-03 | `~/flight_logs/2026-09-01/` | NEAR-829 |
| A19 | REAL: multi-goal square (`goal_tracking.yaml`), 2 laps, all corners tracked (videos in `videos/`) | 2026-09-03 | `~/flight_logs/2026-09-01/` | NEAR-829 |
| A20 | REAL: deliberate in-flight geofence breach → freeze-hover (armed); recovery `land` → `reset_fence` → `takeoff` | 2026-09-03 | `~/flight_logs/2026-09-01/` | NEAR-830 |
| A21 | REAL: landing auto-disarm reliable at `land_speed_mps` 0.6; 0.3 bounced and left the drone armed on the ground | 2026-09-03 | `~/flight_logs/2026-09-01/` | NEAR-826 |

- `land_settle_s` (live parameter; `SwarmCommander.landing_done()`): after z ≤
  `land_complete_altitude_m` the drone stays LANDING and keeps commanding the descent for the
  settle time, then DISARM → IDLE; a bounce restarts the timer. Trigger: in sim the instant
  disarm was DENIED and the offboard timeout left all three drones armed in failsafe hover
  (#5). Unit tests `test/test_landing_settle.py`.
- Disarm retry (2026-10-20, `SwarmCommander.land_disarm_step()`): a rejected DISARM is resent
  every `land_disarm_retry_s` (1 s) up to `land_disarm_retries` (5) times while the descent is
  still commanded (#8: settle alone was accepted on 1 of 3). The sim refusals came from
  PX4's land detector seeing the body rock on the floor (#9) → sim airframe
  `LNDMC_ROT_MAX` 300. Closed in sim by #13 (DISARM accepted first time ×3).
- **Real drones:** the `_ours` configs set `land_settle_s: 0.0`, so the landing is the one flown
  2026-09-03; CMU's shipped real configs lack the key and inherit 2.0 → fly the `_ours` files.
  The retry is inert on real: `px4_interface.disarm()` returns true on send, and a normal
  disarm (no force code) is refused by PX4 unless landed — nothing can drop a flying drone.
  Re-observe at M3 (landing sub-test) and confirm DISARMED in QGC (iron rule 2).
