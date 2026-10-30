# One-drone sim trial on the real-drone command route — scope (draft for owner review, 2026-10-30)

**Purpose.** Policies (NUS velocity policies, our scenarios, teleop) must be judged in sim on the same chain the real Starling flies, or sim results do not transfer. Today the sim drone takes a different route: commander → velocity → `mavros_interface` → MAVROS → PX4, with the commander holding position itself. That route has two sim-only bugs (the release swing, fixed by patch 0006, and the body-frame turn swing, still open). The real drone takes commander → trajectory (position + velocity + heading) → `px4_interface` → uXRCE-DDS → PX4, and PX4 holds position. This trial checks, with one drone, whether the sim can take the real route and what breaks.

**Owner decision behind it (2026-10-30):** NUS policies output per-drone velocities; CMU's commander filters them with its CBF and flies them to PX4.

## What runs

| Piece | Real drone (today) | Sim trial |
|---|---|---|
| PX4 | VOXL, v1.14 | Isaac SITL, v1.16.1 (message-version gap noted below) |
| DDS client on PX4 | `uxrce_dds_client start -n drone_1` | the SITL startup script already starts it; namespace via `PX4_UXRCE_DDS_NS=drone_1`, agent address via the sim-only parameter `UXRCE_DDS_AG_IP` |
| DDS agent | on the laptop | `MicroXRCEAgent udp4 -p 8888` (already installed in the robot container, `/opt/uxrce/bin`) |
| Interface | `drone_interface.launch.xml drone_name:=drone_1 target_system:=<MAV_SYS_ID>` | the same CMU launch file, unchanged; sim `drone_1` has `MAV_SYS_ID` 2 |
| Commander | `drone_modes: real` → trajectory output, `/drone_1/fmu/trajectory_command`, `/drone_1/fmu/robot_command` | a sim copy of `teleop_single.yaml` with `drone_modes: "real"` (our config, not CMU's file) |
| MAVROS sim interface | not used | **not started** for this drone (it would publish the same odometry topic) |

Expected changes: none in CMU's code. Our side: a sim config copy, a launch recipe in `tools/`, and the two sim-only PX4 settings above (iron rule 9 applies: they never go to the drone).

## Steps and checks

| # | Step | Pass when |
|---|---|---|
| 1 | Isaac, 1 drone, flat world; agent up | agent log shows the client session; `/drone_1/fmu/out/*` topics listed |
| 2 | `drone_interface.launch.xml` for drone_1 | `/drone_1/odometry_conversion/odometry` at ≥ 50 Hz and matches the PX4 log position to 0.05 m |
| 3 | Commander with `drone_modes: real`, takeoff | offboard + arm acknowledged; hover within 0.1 m of 1.2 m for 30 s |
| 4 | `tools/sim.sh keys`: ↑ for 1 s, release; repeat after a 90° turn | parks within 2 m after each release, no orbit or swing (the real route has neither sim bug) |
| 5 | Land | disarmed; MAVROS-free arming state read from PX4's log |
| 6 | Message audit | list which `px4_msgs` topics decode on v1.16 and which are silent or garbled (compare with `docs/PX4_MSGS_AUDIT.md`, which covers v1.14) |
| 7 | Clock | measure Isaac's real-time factor during the flight; record it |

Evidence: PX4 log, commander log, a short bag; one LEDGER row; a record under `docs/record/`.

## What the trial decides

- **Go:** steps 1–5 pass → plan the switch of all sim tests to the real route (three drones, `tools/sim.sh test`, sim mocap S6 also uses this route via `in/vehicle_visual_odometry`).
- **Message gap:** step 6 tells whether v1.16 in sim is acceptable or the sim PX4 must be built at v1.14 to match the drone.
- **Clock:** step 7 tells whether real-time pacing is needed before policy evaluation.

## Not in this trial

Three drones, NUS policies, cameras, sim mocap, tuning. Patch 0007 (body-frame fix for the MAVROS route) is held: it only matters if the MAVROS route is kept.

## Risks

- `px4_msgs` (≈ v1.15) against PX4 v1.16 may leave some topics silent, as v1.14 already does on the drone (iron rule 5).
- The SITL client defaults to an agent on 127.0.0.1 in the Isaac container; the agent runs in the robot container, so the address parameter or a container network setting is needed.
- Time sync between `px4_interface` and a lockstep SITL clock running faster than real time.

Estimate: one session to wire, one to fly and record, if the message gap is small.
