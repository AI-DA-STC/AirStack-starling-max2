# Linear change list — rescope for the real command route, NUS velocity policies and the two camera setups (APPLIED in Linear 2026-10-30)

Design: [2026-10-30-rescope-real-route-nus-cameras-design.md](../superpowers/specs/2026-10-30-rescope-real-route-nus-cameras-design.md). **Applied:** 2026-10-30 by the Linear agent; its record is [2026-10-30-linear-sync-record.md](2026-10-30-linear-sync-record.md) (all 27 titles match; HTX-R1 milestone order dragged by the owner the same day). The owner applies these rows in Linear, re-exports the plan, and the repo pages follow the new snapshot in one commit. Nothing on the project pages changes before that. `NEW-n` ids are placeholders until Linear assigns NEAR numbers.

Camera setups in titles: **ZED-style added camera** (the stereo camera + Jetson payload planned so far; short label **A** in tables) and **Starling built-in sensors** (the Starling 2 Max's own cameras, ToF, thermal camera and IMUs; short label **B**).

## HTX-R1 Swarm Sim Validation (Isaac)

| op | id | milestone | exact title | state | note |
|---|---|---|---|---|---|
| NEW-M | — | S5d · Sim flies the real command route (px4_interface) | (milestone) | — | after S5, before S6; description = the design's Purpose + Done-when |
| NEW | NEW-1 | S5d | One sim drone flies takeoff, hover and land through px4_interface with MAVROS not started | Backlog | the trial: docs/superpowers/specs/2026-10-30-sim-real-route-trial-design.md |
| NEW | NEW-2 | S5d | Sim records name and prove their command route and camera setup | Backlog | a record whose route or camera cannot be read back is INCOMPLETE |
| NEW | NEW-3 | S5d | Re-run the hover and 1 m step test on the px4_interface route and compare with the MAVROS-route results | Backlog | baseline ledger #17–#19; gates no looser, vehicle time |
| NEW | NEW-4 | S5d | Release-to-hold and 90° turn test on the px4_interface route | Backlog | the two MAVROS-route sim bugs must be absent |
| NEW | NEW-5 | S5d | Check which PX4 messages decode on the sim’s PX4 v1.16 | Backlog | compare docs/PX4_MSGS_AUDIT.md (v1.14) |
| NEW | NEW-6 | S5d | Record Isaac’s real-time factor on every run and add a real-time pacing switch | Backlog | gates S5e |
| NEW | NEW-7 | S5d | Re-run the three-drone crossing on the px4_interface route | Backlog | baseline ledger #22 |
| NEW | NEW-8 | S5d | Print the remaining sim-vs-real differences on every sim record | Backlog | PX4 1.16 vs 1.14, rate gains ×0.5, motor lag off, hover thrust 0.153 vs 0.165 |
| NEW-M | — | S5e · Evaluate NUS velocity policies in sim | (milestone) | — | after S6; gated by S5d, S6 and NEW-6 (in the description) |
| NEW | NEW-9 | S5e | Write the velocity contract with NUS and CMU (frame, units, limits, rate, timeout) | Backlog | shared once, used by S5e and M8 |
| NEW | NEW-10 | S5e | Decide how a policy drone plugs into the commander (leash, teleop fence, hold on timeout) | Backlog | today's entry point is the teleop velocity topic |
| NEW | NEW-11 | S5e | Run a NUS policy in sim with one command and a record (gates written first) | Backlog | `tools/sim.sh test` |
| NEW | NEW-12 | S5e | Fly one, two, then three policy drones in sim with collision avoidance on and off | Backlog | "observed in sim", never "validated" |
| NEW | NEW-13 | S5e | Agree the separation gate for policy runs | Backlog | Linear relation: blocked by NEAR-787 (the owner’s gate decision) |
| RENAME-M | — | S5c · Compare the two camera setups for cuVSLAM and OpenVINS | (milestone) | — | was "S5c · Choose the camera for cuVSLAM" (D2 keeps both setups) |
| KEEP | NEAR-800 | S5c | Run cuVSLAM in monocular mode on a replayed flight and score it against stereo | Backlog | mono = Starling tracking_front |
| RENAME | NEAR-801 | S5c | List the Starling 2 Max’s sensors and check which modes cuVSLAM and OpenVINS support on them | Backlog | was "List the Starling 2 Max’s built-in cameras and check whether cuVSLAM can use them" |
| CLOSE | NEAR-802 | S5c | Decide the camera (built-in mono / built-in stereo / added stereo) and write down why | Canceled | note: "Superseded 2026-10-30 — owner keeps both camera setups (D2); the comparison is NEW-22." |
| MOVE+RENAME | NEAR-809 | S5c | Model the Starling built-in tracking_front camera (AR0144) in sim | Backlog | from S8; was "Model the chosen camera on drone_1 in sim" |
| NEW | NEW-14 | S5c | Model the Starling built-in tracking_down camera (AR0144) in sim | Backlog | the drone's VIO uses front + down (`vio_cams.conf`) |
| NEW | NEW-15 | S5c | Model the Starling built-in hires_front camera (IMX412) in sim | Backlog | 1024×768 stream; 4056×3040 optional |
| NEW | NEW-16 | S5c | Model the Starling built-in hires_down camera (IMX412) in sim | Backlog | |
| NEW | NEW-17 | S5c | Model the Starling built-in ToF depth sensor in sim | Backlog | pmd-tof-liow2, 10 fps |
| NEW | NEW-18 | S5c | Model the Starling built-in thermal camera (Lepton) in sim | Backlog | approximate; Isaac has no native thermal |
| NEW | NEW-19 | S5c | Model the Starling built-in IMUs (imu_apps, imu_px4) at their real mounts and rates | Backlog | needed by OpenVINS |
| NEW | NEW-20 | S5c | Run OpenVINS in sim on the Starling built-in sensors | Backlog | what the drone runs (voxl-open-vins-server) |
| NEW | NEW-21 | S5c | Re-run the flat-world and construction-site VIO tests on the Starling built-in sensors | Backlog | the ZED-style results #15/#16 stay as setup A; this issue also records the built-in camera images for replay |
| NEW | NEW-22 | S5c | Score cuVSLAM and OpenVINS on both camera setups in one table | Backlog | one test, run per setup and per VIO |
| RENAME-M | — | S8 Model the ZED-style added camera and Jetson payload | (milestone) | — | was "S8 Model the chosen camera and payload" |
| RENAME | NEAR-798 | S8 | Add the Jetson and ZED-style camera weight to the Starling sim model | Backlog | was "Add Jetson and camera weight to the Starling sim model" |
| KEEP | NEAR-807 | S8 | Re-run hover, step and crossing tests on the heavier model | Backlog | |
| KEEP | NEAR-808 | S8 | Feed drone_1’s IMU into cuVSLAM (camera-only → camera + IMU) and compare the scores | Backlog | setup A; setup B’s IMU is NEW-19, scored in NEW-22 |

Unchanged in HTX-R1: S1–S5 (NEAR-860 stays the ZED-style recording), S5b, S6, S7, S9, S10.

**Milestone order in Linear (drag to this order):** S1, S2, S3, S4, S5, S5d, S6, S5e, S5b, S5c, S7, S8, S9, S10.

## HTX-R2 Starling Flight Bring-up (M2–M7) → also hosts M8

| op | id | milestone | exact title | state | note |
|---|---|---|---|---|---|
| RENAME-P | — | (project) | HTX-R2 Starling Flight Bring-up (M2–M8) | — | was "HTX-R2 Starling Flight Bring-up (M2–M7)" |
| NEW | NEW-23 | M2 | Copy each Starling’s camera calibration and mount files (read only) | Backlog | `/data/modalai/opencv_*_intrinsics.yml`, `extrinsics.conf`, `voxl-camera-server.conf`; feeds S5c |
| NEW-M | — | M8 · Evaluate NUS velocity policies on the real drones | (milestone) | — | after M7; gated by M4, M7 and S5e (in the description) |
| NEW | NEW-24 | M8 | One Starling flies a NUS policy, speed capped below the sim-tested speed, fence on | Backlog | RC takeover = MANUAL or KILL (iron rule 1) |
| NEW | NEW-25 | M8 | Two Starlings fly the S5e scenario with collision avoidance | Backlog | |
| NEW | NEW-26 | M8 | Three Starlings fly the S5e scenarios with the same gates as in sim | Backlog | |
| NEW | NEW-27 | M8 | Compare the real-drone results with the sim results | Backlog | ticks only from REAL records |

Unchanged in HTX-R2: R1, M2–M7 issues (NEAR-838's order still includes the stereo cameras, D2).

## HTX-R3 Multi-Drone Localisation (VO + UWB)

| op | id | milestone | exact title | state | note |
|---|---|---|---|---|---|
| RENAME | NEAR-847 | L2 | Cameras of both setups on all three sim drones, added one at a time with a GPU check | Backlog | was "Cameras on all three sim drones, added one at a time with a GPU check" |
| RENAME | NEAR-855 | L4 | Hand-carry each camera setup with motion-capture positioning (mocap) and run cuVSLAM and OpenVINS on the laptop | Backlog | was "Hand-carry the chosen camera under mocap with cuVSLAM on the laptop" |
| RENAME | NEAR-856 | L4 | Score cuVSLAM and OpenVINS against Motive | Backlog | was "Score cuVSLAM against Motive" |

## Counts after the change

Milestones 25 → 28 (S5d, S5e, M8 new; S5c, S8 renamed). Issues 78 → 105: HTX-R1 55, HTX-R2 33, HTX-R3 17 (27 new, NEAR-809 moved, NEAR-802 Canceled with a note, none deleted). Every new issue is Backlog.

**Applying it in Linear.** New milestone descriptions: the Purpose and Done-when sentences from the design. New issue descriptions: the note cell. Apostrophes are the curly ’ Linear already uses. When done, the owner exports the snapshot and Claude fills the NEW-n → NEAR id map below from it.

| placeholder | NEAR id |
|---|---|
| NEW-1 | NEAR-866 |
| NEW-2 | NEAR-867 |
| NEW-3 | NEAR-868 |
| NEW-4 | NEAR-869 |
| NEW-5 | NEAR-870 |
| NEW-6 | NEAR-871 |
| NEW-7 | NEAR-872 |
| NEW-8 | NEAR-873 |
| NEW-9 | NEAR-874 |
| NEW-10 | NEAR-875 |
| NEW-11 | NEAR-876 |
| NEW-12 | NEAR-877 |
| NEW-13 | NEAR-878 |
| NEW-14 | NEAR-879 |
| NEW-15 | NEAR-880 |
| NEW-16 | NEAR-881 |
| NEW-17 | NEAR-882 |
| NEW-18 | NEAR-883 |
| NEW-19 | NEAR-884 |
| NEW-20 | NEAR-885 |
| NEW-21 | NEAR-886 |
| NEW-22 | NEAR-887 |
| NEW-23 | NEAR-888 |
| NEW-24 | NEAR-889 |
| NEW-25 | NEAR-890 |
| NEW-26 | NEAR-891 |
| NEW-27 | NEAR-892 |
