> 15 November 2026 · author: investigator agent, reviewed by the lead · status: read-only survey, copied unchanged from the working notes; §6 lists proposals for the owner and authorises no flight (real flights follow [docs/PREFLIGHT.md](../../../docs/PREFLIGHT.md) and [docs/RUNBOOK.md](../../../docs/RUNBOOK.md)).

# Real flight logs survey: can we fit setpoint -> velocity on the real Starling?

Read-only survey, 2026-11-15, of `~/flight_logs/2026-11-11`, `2026-11-12`, `2026-11-13`. Nothing was changed there. The scan scripts are in the session scratchpad, not in the repo. Ledger rows are from `docs/record/LEDGER.md` (#33 to #37).

## 1. Short answer

There is enough real data to start a first fit of the PX4 part (setpoint to velocity), but only at low speed. Every horizontal setpoint in the real logs is at most 0.5 m/s, and the stick was capped at 0.5 m/s (`teleop_max_speed_mps`, commander log of 11-13). The one exception is an unlabelled log with 0.87 m/s (section 4). The simulator runs at 2, 4 and 6 m/s. There is no designed step data and no stick command was recorded anywhere. Best files are in section 5. What to record next is in section 6.

## 2. Bag: `2026-11-12/svg_20261112_094546` (the only rosbag)

- Format: mcap, uncompressed, 592 MB, 829.8 s, 2,048,485 messages. Started 2026-11-12 09:45:46 UTC (17:45:46 +08).
- Covers the two-drone goal and CBF flights of the evening (ledger #35: 17:45:24 goal flight, 17:47:42 flip of the older drone, 18:00:16 flight). Only one `/svg/drone_2/goal_command` burst (3 messages, 20 s after bag start) is in it.
- No `/svg/*/teleop_command` topic exists in the bag. No stick data is in it. It was recorded before the gamepad flights (#36, #37).
- No mcap or rosbags reader is installed. Counts come from `metadata.yaml`. Rates and frames come from a small mcap parser I wrote in the scratchpad (uncompressed chunks), run read-only.

| Need | Topic | Msgs | Rate |
|---|---|---|---|
| Setpoint to PX4 (drone_2) | `/drone_2/fmu/in/trajectory_setpoint` (px4_msgs/TrajectorySetpoint) | 15,470 | 18.8 Hz |
| Setpoint to PX4 (drone_1) | `/drone_1/fmu/in/trajectory_setpoint` | 15,468 | 18.8 Hz |
| Commander output before px4_interface | `/drone_N/fmu/trajectory_command` (MultiDOFJointTrajectory) | 15,471 / 15,468 | 18.8 Hz |
| Offboard heartbeat | `/drone_N/fmu/in/offboard_control_mode` | 23,767 / 23,763 | n/a |
| Measured state, PX4 | `/drone_2/fmu/out/vehicle_odometry` (51 Hz), `vehicle_local_position` (51 Hz); drone_1 `vehicle_odometry` 104,082, `vehicle_local_position` 104,252 | see left | 51 Hz (drone_2) |
| Measured state, converted | `/drone_N/interface/odometry`, `/drone_N/odometry_conversion/odometry` (nav_msgs/Odometry) | 42,379 (drone_2); 102,586 and 102,569 (drone_1) | 51 Hz (drone_2) |
| Mocap | `/drone_N/pose` (PoseStamped), `/drone_N/fmu/in/vehicle_visual_odometry` | 93,217 (drone_2 pose), 82,720 (drone_1 pose) | 112 Hz (drone_2) |
| Attitude | `/drone_N/fmu/out/vehicle_attitude` | 78,882 (drone_2), 109,824 (drone_1) | 95 Hz (drone_2) |
| Commander status | `/svg/commander_status` (String) | 4,147 | 5 Hz |
| CBF | `/svg/cbf_active` (String) | 16,590 | 20 Hz |
| Armed | `/drone_N/fmu/is_armed`, `has_control` | 16,590 each | 20 Hz |
| IMU, battery, GPS, point cloud, tf | `sensor_combined`, `battery_status`, `vehicle_gps_position`, `/pointCloud` (199,073), `/tf` (250,044) | | not needed |

No `/poses` topic: mocap is the per-drone `/drone_N/pose` plus `vehicle_visual_odometry`.

Frames (read from the first message of each odometry topic): `frame_id = map`. `child_frame_id = base_link` on `/drone_N/interface/odometry`; `drone_N/base_link` on `/drone_N/odometry_conversion/odometry`. So pose is world, and the twist follows the ROS convention of being in the child (body) frame. Memory note: in the simulator the odometry twist was body frame and the commander used it as world. For the real path this is unchecked, so a derivative check against position is needed before using it. `vehicle_odometry` (PX4 raw) also has a `velocity_frame` field; I did not decode it. I did not check whether the 51 Hz rate is a real PX4 rate or the logging rate.

Flights in the bag: the setpoint and `is_armed` topics run for the whole 830 s. The armed spans were not extracted (needs a full decode). The three goal-flight ulogs below give the real spans.

## 3. Ulogs

All are PX4 1.14. What every flight ulog has: `trajectory_setpoint` at 5.0 Hz, `vehicle_local_position` at 10 Hz, `vehicle_local_position_setpoint` at 10 Hz, `vehicle_attitude` at 20 Hz, `vehicle_visual_odometry` (the mocap fed to PX4) at 33 Hz, `vehicle_status` at 2 Hz. Not logged: `vehicle_odometry`. Setpoint rate is 5 Hz here, against about 19 Hz sent in the bag, so the ulog setpoint is decimated and a 20 Hz leash or reference ripple is aliased.

Facts that hold for all of them:
- `trajectory_setpoint` has position AND velocity both set (no NaN), plus acceleration and jerk fields. So PX4 runs its position loop with velocity feedforward, not a pure velocity loop. The fit is "position+velocity setpoint to velocity", and the kp-on-reference term is inside what PX4 sees.
- `yawspeed` is NaN (97% to 100%). `yaw` is set.
- `vehicle_local_position` vx, vy, vz are in PX4's local NED frame (world, not body). `heading` is logged, so a body-frame twist can be rebuilt. The local frame is rotated by the mocap heading at start (heading 1.4 to 1.8 rad), so setpoint and velocity share one frame and no rotation is needed to compare them.
- Setpoint and local position share the PX4 clock, so a fit inside one ulog needs no time base. A time base is only needed to line a ulog up with the bag or the mocap.
- "Armed time" below is log start to disarm, from `vehicle_status`. The logs start at arming.
- Clocks: 11-12 newer drone (drone_2) is right (UTC). 11-12 older drone (drone_1) says 2026-08-19: laptop_epoch = drone_epoch + 7343415 s (morning) or + 7346234 s (evening). 11-13 drone clocks also wrong, file times say Aug 19/20; use the README's pairing.

### 2026-11-11 (ledger #33)
No ulog, no bag. Only `launch.log` and three tmux pane dumps. Nothing to fit.

### 2026-11-12 morning (ledger #34, negative: failed two-drone attempts)
| File | Drone, time | Armed | Notes |
|---|---|---|---|
| `ulog/drone_2_newer_10.40.2.10/log103.ulg` | drone_2, flight 1, ends 08:43:11 UTC (16:43 +08) | 23 s | 106 setpoints |
| `.../log104.ulg` | drone_2, flight 2, ends 08:48:57 UTC | 5 s | short |
| `ulog/drone_1_older_10.40.2.11/08_52_34.ulg` | drone_1, flight 1 | 21 s | |
| `.../08_58_40.ulg` | drone_1, flight 2, front-right motor never started, ran 7.5 m along the floor (ledger #34) | 6 s | bad data, hardware fault |
Also 3 short armed spans and many tiny logs (`log100` to `log102`, `08_49_*`, `08_58_*`, `09_00_*`). Not useful.

### 2026-11-12 evening (ledger #35, first clean two-drone flights and CBF)
| File | Drone, time | Armed | Notes |
|---|---|---|---|
| `ulog/evening_newer/sess128/log104.ulg` | drone_2, 17:45:24 | 85 s | goal flight toward the hovering drone; max setpoint 0.5 m/s, 3 y-axis legs of 2.0 to 2.4 s |
| `ulog/evening_older/09_08_14.ulg` | drone_1, same flight | 85 s | gave way up to 0.38 m; setpoint speed max 0.21 m/s |
| `evening_newer/sess128/log105.ulg`, `evening_older/09_10_28.ulg` | 17:47:42, the flip | 5 s each | not usable |
| `ulog/evening_newer/sess129/log100.ulg` | drone_2, 18:00:16 | 53 s | one 2.8 s leg at 0.5 m/s |
| `ulog/evening_older/09_23_05.ulg` | drone_1, 18:00:16 | 56 s | max 0.25 m/s |
Three RC arm tests (`09_21_05`, `09_21_10`, `09_21_31`) are not flights.

### 2026-11-13 (ledger #36 and #37)
| File | Drone, time | Armed | Notes |
|---|---|---|---|
| `ulog_drone_2/log103.ulg` (copy: `two_drone_teleop/drone_2/log103.ulg`) | drone_2 (newer), 16:40:36 to 16:43:13, ledger #36, gamepad flight | 156 s (README: 149 s airborne) | the richest file, see section 4 |
| `ulog_drone_2/log101.ulg` | drone_2, 16:34:59 flight | 36 s | one x leg 2.6 s at 0.23, one y leg 3.0 s at 0.35 |
| `two_drone_teleop/drone_2/log105.ulg` | drone_2, 17:40:21, ledger #37, hand-flown at the hovering drone | 65 s | y legs only, max 0.39 m/s |
| `two_drone_teleop/drone_1_candidates/08_47_58.ulg` | drone_1 (older), same flight, hovering, pushed by CBF | 68 s | response to the CBF, not to a stick |
| `two_drone_teleop/drone_2/log104.ulg`, `drone_1_candidates/08_42_53.ulg` | 17:35:16 flight | 21 s and 26 s | hover and takeoff only (no horizontal setpoint) |
| `ulog_drone_1_this_boot/08_34_27.ulg` | drone_1, unlabelled, 62 s | 62 s | NOT in any README or ledger row. Largest horizontal setpoint of all real data (0.87 m/s on x); x legs 6.4, 1.4, 2.6, 2.0, 3.4 s. Ask the owner what it was before using it. |
The other 62 ulogs in `ulog_drone_1_this_boot/` and `ulog_drone_1/` are short or arm tests (only 13 are over 2 MB). I scanned three of them. `two_drone_teleop/sep_flightB.csv` has 10 Hz separation and both positions for the 17:40:21 flight (time since arming).

## 4. How much pushing is there

No bag has a stick topic, so I counted from the ulog `trajectory_setpoint` velocity (5 Hz). Rule used: a run where one axis's setpoint velocity stays above 0.1 m/s for about 1 s or more. It includes everything the commander sent, not only the stick (leash, fence braking, CBF edits, takeoff ramps). Axes are PX4 local NED (x = north, y = east, z = down, so takeoff shows on z).

| File | x legs | y legs | z legs | Max setpoint (m/s) |
|---|---|---|---|---|
| 11-13 `log103` (gamepad, #36) | 7 (0.8 to 4.0 s long) | 3 (1.0, 1.0, 1.6 s) | 5 | 0.5 x, 0.5 y, 0.6 z |
| 11-13 `log105` (drone_2 hand-flown, #37) | 0 | 6 (0.8 to 5.4 s) | 2 | 0.39 y |
| 11-13 `08_47_58` (hovering drone, pushed by CBF) | 0 | 3 (2.2 to 2.8 s) | 2 | 0.36 y |
| 11-13 `log101` | 1 | 1 | 2 | 0.35 |
| 11-12 `sess128/log104` (goal flight) | 0 | 3 (2.0 to 2.4 s) | 2 | 0.5 y |
| 11-12 `sess129/log100`, `09_08_14`, `09_23_05` | 0 | 1 each | 2 | 0.5, 0.21, 0.25 |
| 11-13 `this_boot/08_34_27` (unlabelled) | 5 | 1 | 1 | 0.87 x |

So the pushing is 10 horizontal legs in `log103`, 6 in `log105`, a few more in the goal flights. Most legs are 1 to 3 s long and a good share sit at the 0.5 m/s cap, so the data show saturation as much as response. Speeds the sim uses (2 to 6 m/s) are never reached. Stick-command counts proper (the number of segments the stick was held non-zero for 1 s on one axis) cannot be given: the `teleop_command` was not recorded in any log, and there is no bag for the 11-13 flights.

## 5. Verdict and best files

Enough for a first low-speed fit of "setpoint to velocity", with these limits:
- Speed range only up to about 0.5 m/s, with one 0.87 m/s log. The sim's response (and the 9 Hz pitch limit cycle found earlier) lives at higher speeds. A fit from this data will not cover them.
- Setpoint is logged at 5 Hz in the ulog, against about 19 Hz sent. Fine for a first-order lag fit of the PX4 loop with its known sampling; poor for the 20 Hz reference ripple.
- The same fit needs the commander's input (stick) to explain the setpoint. That is missing, so only "setpoint to velocity" (the PX4 part) can be fitted, not "stick to velocity".

Best files, in order:
1. `2026-11-13/ulog_drone_2/log103.ulg`: gamepad flight, 156 s, 15 horizontal legs, all topics at the rates above, no time base needed.
2. `2026-11-13/two_drone_teleop/drone_2/log105.ulg` and `drone_1_candidates/08_47_58.ulg`: the second a different drone (the older one) pushed by the CBF; useful to see if the two airframes respond alike.
3. `2026-11-12/svg_20261112_094546/` (the bag): the only source with the setpoint at its full 18.8 Hz and with a measured velocity in `map` frame at 51 Hz. But the goal flights are autonomous, speed 0.5 m/s, with no stick. Needs an mcap reader.
4. `2026-11-13/ulog_drone_1_this_boot/08_34_27.ulg`: only if the owner can say what it was; it has the highest speed.
5. Do not use: the 5 to 6 s logs, the flip logs (`09_10_28`, `log105` of sess128), the 11-12 morning drone_1 flight 2 (motor never started).

Missing, in order of importance:
- The stick command (`/svg/*/teleop_command`) and the commander's own pre-limit velocity: not in any real log.
- Setpoint above 0.5 m/s.
- Designed steps with a clean stop in between. The existing legs are ad hoc, and some end at the fence (`fence keep-in` lines in the commander log).
- A time base between ulog and mocap/bag for the older drone (clock says August 2026; offset recorded only in the README by hand).
- Real odometry twist frame (body or world) is unverified; the ulog `vehicle_local_position` is world NED and can be used instead.
- No mcap reader and no pyulog in this environment. Reading the bag needs `mcap` or `rosbags` installed, or the small parser I used.

## 6. What to record at the next real flight

1. Record a rosbag for every flight (not done on 11-13). Include: `/svg/*/teleop_command` (or the gamepad topic), `/drone_N/fmu/in/trajectory_setpoint`, `/drone_N/fmu/trajectory_command`, `/drone_N/fmu/out/vehicle_odometry`, `/drone_N/fmu/out/vehicle_local_position`, `/drone_N/interface/odometry`, `/drone_N/pose` (mocap), `/drone_N/fmu/out/vehicle_attitude`, `/svg/commander_status`, `/svg/cbf_active`. Skip `/pointCloud` and `/tf` (they are 80 % of the bag).
2. Raise the PX4 ulog `trajectory_setpoint` rate to the sent rate (SDLOG profile or `logger` rate for that topic) and log `vehicle_odometry`, so the ulog alone is enough.
3. Designed steps, one axis at a time, from hover at 1 to 1.5 m height, well inside the fence, away from the wall: x, then y, each at 0.25, 0.5, 0.75, 1.0 m/s (go up in steps as safety allows, since only 0.5 m/s has been flown), both directions. Each step: hold the stick for about 3 s (long enough to reach steady state), then release and hold still for about 3 s. Repeat each size 3 times. Also one z step and one yaw step. About 3 to 4 minutes per speed, so about 15 minutes of data over two batteries.
4. Turn the CBF off for the fit flight (single drone), and lift `teleop_max_speed_mps` above 0.5 before the higher steps.
5. One flight with the mocap yaw known and written in the note, one flight per drone (the two Starlings differ), and note the drone clock offset in the README at the time.
6. Add a leash-only run (reference changing at 20 Hz, stick at zero) if the aim is to fit the sim's `u = s + kp(ref - pos)` law; the real data have no clean case of it.
