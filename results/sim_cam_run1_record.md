# Run record — sim_cam_run1 (2026-10-22): cuVSLAM stereo VO on the simulated Starling, end to end

**Status: pipeline works end to end in sim.** Not an accuracy claim (see caveats).

## Setup
- Isaac Sim 5.1 headless, 3 Starling 2 Max (validated model, sim airframe), `ENABLE_CAMERA=true CAMERA_DRONES=drone_1`:
  ZED-X subgraph, 480×300 rgb8 stereo at ~31 Hz sim time, pinhole fx=fy=184, baseline 0.120 m (from right `P[0,3]`).
- cuVSLAM 17.0.1 (cu12 wheel) in `localisation-exploration:cu12` (CMU robot image + CUDA 12.6 libs + gtsam), run with
  `--network container:isaac-sim` (see "DDS finding"). Node: `nodes/cuvslam_stereo_node.py`, stereo mode, visual only (no IMU), rectified.
- Flight: `cbf_sim.yaml scenario:=random_goals` (2.0 m/s cruise / 4.0 cap), takeoff → 180 s random goals → hold → land. All 3 drones `landed, disarmed (attempt 1)`.
- Reference: drone_1 PX4 ulog `vehicle_local_position` (EKF2 on simulated GPS) — **a reference, NOT ground truth**.

## Numbers (drone_1, 141.3 m path, 5,517 associated pairs, clock offset −0.452 s found by search)
| Metric | Value |
|---|---|
| Tracker | 7,112 frames tracked, **0 lost**, 20–24 Hz out (31 Hz in), track() p50 ≈ 4 ms |
| APE translation, SE(3)-aligned | **RMSE 0.252 m**, mean 0.233, max 0.674 m → 0.18 % of path |
| APE rotation, aligned | RMSE 2.12°, max 8.23° |
| RPE per 1 m | RMSE 0.060 m, mean 0.043 m |
| APE unaligned | 0.803 m (includes camera→body lever arm + initial yaw) |

## Caveats (why this is a pipeline result, not a VIO result)
1. Reference is PX4 EKF2 on simulated GPS (its own error is unknown here); the Isaac ground-truth publisher is still to be built.
2. The 0.12 m forward / 0.02 m down camera lever arm is not compensated in the node; it inflates APE/RPE whenever the drone yaws.
3. Sim textures/lighting are ideal and there is no motion blur, rolling shutter or exposure change → sim accuracy is an upper bound.
4. 480×300 with fx=184 is a very wide, low-res camera; the real D435i will be 848×480 IR.
5. Clock offset between PX4 boot time and Isaac sim time was estimated by search, not measured.

## DDS finding (important for every future sim sensor node)
The Isaac ROS 2 bridge publishes on the `airstack_airstack_network` docker network (172.31.0.200). Host-network containers (the
CMU robot container) never discover it: `ros2 topic list` shows no `/clock` or camera topics there, static peers did not help.
MAVROS works because it is MAVLink/UDP, not DDS. Workaround used: run the node with `--network container:isaac-sim`.
Consequence: nodes that need BOTH Isaac topics and MAVROS topics need a fix (Isaac on host network, a relay, or discovery server).

## Files
`results/bags/sim_cam_run1/` — `sim_cam_run1_0.mcap` (cuvslam odometry+status, /clock, camera_info), `drone_1_sysid2.ulg`,
`cuvslam_drone_1.tum`, `cuvslam_drone_1_vs_ulog.json`, `cuvslam_drone_1_diag.png`. Node log: `results/cuvslam_node.log`.
