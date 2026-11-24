Simulator: AirStack simulator (Isaac Sim 5.1.0 + Pegasus + PX4 v1.16.1 SITL with real EKF2, docker, headless), SIM-ONLY
airframe `10090_pegasus_starling2max`; RTX 5090 workstation. Not the training simulator; not a flight result.

# 2026-11-24_ste_l14_steps record

## Purpose
STE task L1.4 (main track, INFO, no gate; P5 approved): velocity steps through real PX4 and real EKF2 in the AirStack
simulator, so that L1.5 can compare tier 2 against them. Owner ruling R25 (24 Nov 2026): AirStack set up on the RTX
5090 for this task.

## What was set up on the 5090 (R25)
CMU's host setup was already in place (NatNet SDK, the `airstack` shell function, `omni_pass.env`, `user.config.json`;
`airstack.sh setup` found each and skipped it); the robot image rebuilt from cache. New: the three containers
(`./airstack.sh up`), the robot workspace build (`bws`, 59 packages), the git hooks path (`tools/sim.sh setup`, which
sets `core.hooksPath = tools/git-hooks` in the shared git config), and the empty, gitignored bags folder
`AirStack/robot/ros_ws/bags`. `tools/sim.sh doctor`: 21 OK, 2 WARN (no host `pyulog`, no `obs`), 0 FAIL. No AirStack file,
config or drone parameter was edited. The containers are left up and idle.

## Commit and inputs
Script `scripts/record_steps.sh` at `452b260d` on `development`, run with `SVG_STACK_REPO=~/AirStack-starling-max2` (the
docker-mounted live clone, on `main` at `3b8bcf1d`); `configs/s1.toml` sha256 `996714a9…`, `scripts/virtual_stick.py`
sha256 `3b6f9c8c…` (both unchanged since S1). Airframe file sha256 `ec74dd9a…` (the live clone's
`AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max`; its sim-only lines are listed in the repository
iron rule 9). Commander `teleop_single_ours.yaml`, scenario `hover`, `use_mocap:=false`; drone_1 only (the other two
simulated drones stay on the ground).

## Result (INFO)
36 of 36 planned steps reached (x, y and z; 0.5, 1.0 and 2.0 m/s; each + step followed by its − twin; 2.0 s of zero
before each, 3.0 s hold, 20 Hz), landed (`drone_1 IDLE z=-0.05 m`), virtual stick exit 0, simulator brought down and
checked down. Step 6 (−z) was not flown: the floor guard predicted a bottom of 0.52 m, below the 0.80 m floor
(`FLOOR GUARD: step 6 not flown`); `steps_flown.json` marks it skipped. Height at step onset ranged 1.12–14.12 m: the
z steps climbed faster than they descended, likely the airframe's descent speed limit (a hypothesis; L1.5 reads the logs).
Files: the bag (`svg_s1_2026-11-24_ste_l14_steps_r3_20261124_034955`, mcap) and the drone_1 PX4 log
(`drone_1_sysid2_03_49_17.ulg`) in `runs/2026-11-24_ste_l14_steps_r3/` (568 MB, not in git; sha256 in the evidence
folder); a copy of the bag in `~/flight_logs/sim/_stack/`.

## Two stopped runs before it (nothing flown in either)
- Run 1 (11:15): the script's real-drone guard listed every topic matching `/fmu/|/poses|/pose$` and stopped on the
  simulator's own `/drone_N/interface/mavros/local_position/pose`, plus `/drone_N/fmu/in/vehicle_visual_odometry` and
  `/drone_N/pose`. Fix `f7e87089`: only published topics count; the simulator's MAVROS is left out.
- Run 2 (11:24): the stick's own simulator check refused on `/drone_N/fmu/in/vehicle_visual_odometry`, correctly. Root
  cause: `ground_control.launch.py` defaults `use_mocap` to `true` (`:210`), so our commander started a `mocap_bridge`
  that publishes the `/fmu/in/` relay. Fix `452b260d`: the launch passes `use_mocap:=false`, `/fmu/in/` publishers
  count as a real-drone signal again, and a topic list without its "Published topics:" header counts as a signal (fail
  closed; reviewer's hardening).
This was the script's first full run since it was written for S1 (15 Nov, "not yet run"). One independent reviewer read
the first fix (no blocking findings; a real drone's `/fmu/out/*` and a mocap `/drone_N/pose` publisher still stop the
session); the second fix is covered by tests (`tests/test_record_steps.py`, 77 passed). Both stopped runs were brought
down by hand with `tools/sim.sh down` (no `--force`), and their bags were removed from the robot container after
`down` copied them to `~/flight_logs/sim/_stack/`.

## What this does not show
No fit and no comparison yet (that is L1.5); one session, one drone, one airframe; PX4 1.16.1 in the simulator against
1.14 on the drones, the speed-only MAVROS route against the trajectory setpoint, and the simulator's PX4 clock against
the commander's are confounds L1.5 must name (WORK_BREAKDOWN, L1.5). SIM-ONLY values: nothing here goes to a drone
(repository iron rule 9).

## GPU and time
The simulator held the GPU for about 6 minutes (11:48:58–11:54:38); 0 GPU-h charged to the training budget (L1.4 is
simulator time, 0 GPU-h in the WORK_BREAKDOWN budget table). Evidence: `records/evidence/2026-11-24_ste_l14_steps/` (session and stick logs,
plan and flown steps, the stopped runs' logs, sha256 of the run folder's bag and PX4 log).
