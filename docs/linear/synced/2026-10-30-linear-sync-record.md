# Linear sync record — 2026-10-30

Applied in the **nearlab** workspace. Titles and technical descriptions below are preserved. No issues were deleted. Every new issue is **Backlog**, unassigned, with no due date. Creation and metadata changes are complete; this does not mean the underlying work is complete.

**Remaining action:** HTX-R1 manual milestone ordering is **PENDING**; see §2.5. HTX-R2 M8 is correctly placed after M7.

Evidence lives in the repo https://github.com/AI-DA-STC/AirStack-starling-max2 (`docs/record/LEDGER.md` and the record files it links).

---

## Part 1 · Status updates from the latest sim runs — applied

All runs below are simulation (Isaac Sim). None of them flew a real drone. The following statuses and comments were applied.

| Issue | Recorded status | Comment added |
|---|---|---|
| NEAR-786 Re-run hover and 1 m step test on the updated sim drone | **Done** | Sim, PASS twice (ledger #18 and #19, 2026-10-28/29). Worst step: x 0.095 m overshoot, 2.47 s settle. Records: docs/record/sim_hover_step_run2_record.md, sim_hover_step_run3_record.md. |
| NEAR-787 Re-run three-drone crossing with collision avoidance and record it | **Done** | Sim, re-run three times and recorded (ledger #20–#22). Collision avoidance worked: closest pair 0.95–1.00 m, no contact. All three miss the 1.10 m gate (the CBF’s own keep-out); CMU’s tests accept 0.825 m. The gate decision moves to the new issue "Agree the separation gate for policy runs". Record: docs/record/sim_crossing_run2_record.md, video videos/cbf_test.mp4. |
| NEAR-788 Try live gain tuning from the panel in sim | **Done** | Sim, works: 5 of 5 gain changes from the Foxglove panel applied on the next control tick (ledger #23, 2026-10-30). Lesson: change the radius in small steps; a jump from 0.75 to 1.2 m pushed a drone past the fence. Record: docs/record/sim_gains_run1_record.md. |
| NEAR-789 Set up one-drone gamepad teleop in the construction site (pad detected, sticks move the drone, release holds) | remains **In Progress** | Keyboard teleop added (`tools/sim.sh keys`, acts as a gamepad). Release swing fixed (patch 0006). Turning still makes the sim drone circle: a sim-only MAVROS frame bug, which goes away when the sim moves to the px4_interface route (new milestone S5d). |

Milestones S1, S2, S3, S4 (HTX-R1) and L0 (HTX-R3) were already complete and were left unchanged. S5 stays open: NEAR-789, NEAR-790 and NEAR-860 are not finished.

---

## Part 2 · Project HTX-R1 Swarm Sim Validation (Isaac)

### 2.1 Milestone created: "S5d · Sim flies the real command route (px4_interface)"

Description:
> The sim drone takes the same command path as the real drone (commander → trajectory → px4_interface → uXRCE-DDS → PX4), so sim results carry over. Done when (target): one sim drone takes off, hovers and lands through px4_interface with MAVROS not started; the hover and 1 m step test passes on gates no looser than ledger #17–#19, in vehicle time; the release and 90° turn test shows neither MAVROS-route bug; the crossing is re-run against ledger #22; every sim record names its route and camera setup and prints the remaining sim-vs-real differences.

Issues created in it (Backlog, unassigned, no due date):

| ID | Title | Description |
|---|---|---|
| NEAR-866 | One sim drone flies takeoff, hover and land through px4_interface with MAVROS not started | The one-drone trial. Scope: docs/superpowers/specs/2026-10-30-sim-real-route-trial-design.md. |
| NEAR-867 | Sim records name and prove their command route and camera setup | A record whose route or camera setup cannot be read back from the run is INCOMPLETE. |
| NEAR-868 | Re-run the hover and 1 m step test on the px4_interface route and compare with the MAVROS-route results | Baseline: ledger #17–#19. Gates no looser, timed in vehicle time. |
| NEAR-869 | Release-to-hold and 90° turn test on the px4_interface route | The two MAVROS-route sim bugs (release swing, turn orbit) must be absent. |
| NEAR-870 | Check which PX4 messages decode on the sim’s PX4 v1.16 | Compare with docs/PX4_MSGS_AUDIT.md, which covers the drone’s v1.14. |
| NEAR-871 | Record Isaac’s real-time factor on every run and add a real-time pacing switch | Isaac runs 1.3–2× faster than the wall clock. This issue gates S5e. |
| NEAR-872 | Re-run the three-drone crossing on the px4_interface route | Baseline: ledger #22. |
| NEAR-873 | Print the remaining sim-vs-real differences on every sim record | PX4 1.16 vs 1.14, rate gains ×0.5, motor lag off, hover thrust 0.153 vs 0.165. |

### 2.2 Milestone created: "S5e · Evaluate NUS velocity policies in sim"

Description:
> Check a NUS policy in sim, on the real command route, before it flies on a real drone. NUS policies output one velocity per drone; CMU’s commander filters them with its CBF. Gated by: S5d, S6, and the real-time factor issue. Done when (target): the velocity contract is written once and shared with NUS; the plug-in point and its teleop behaviour are decided; one, two and three policy drones fly in sim with collision avoidance on and off, each with one command and a record; the separation gate is agreed. Results say "observed in sim", never "validated".

Issues created in it (Backlog, unassigned, no due date):

| ID | Title | Description |
|---|---|---|
| NEAR-874 | Write the velocity contract with NUS and CMU (frame, units, limits, rate, timeout) | Written once, shared with NUS, used by S5e and M8. |
| NEAR-875 | Decide how a policy drone plugs into the commander (leash, teleop fence, hold on timeout) | Today’s entry point is the per-drone teleop velocity topic, which carries teleop behaviour. |
| NEAR-876 | Run a NUS policy in sim with one command and a record (gates written first) | Through `tools/sim.sh test`. |
| NEAR-877 | Fly one, two, then three policy drones in sim with collision avoidance on and off | Results say "observed in sim", never "validated". |
| NEAR-878 | Agree the separation gate for policy runs | Relation added: **blocked by NEAR-787**. Options: keep 1.10 m and tune the CBF, gate at 0.825 m (CMU’s test value), or accept. |

### 2.3 Milestone renamed from "S5c · Choose the camera for cuVSLAM"

Applied name: **S5c · Compare the two camera setups for cuVSLAM and OpenVINS**

Applied description:
> Two camera setups are kept: the ZED-style added camera (stereo + Jetson payload) and the Starling built-in sensors. Done when (target): every Starling built-in sensor is modelled at its real mount, resolution and rate; OpenVINS runs in sim; the flat-world and site VIO tests are re-run on the built-in sensors; one table scores cuVSLAM and OpenVINS on both setups.

Applied issue changes:

- **NEAR-800:** kept as is.
- **NEAR-801:** renamed to "List the Starling 2 Max’s sensors and check which modes cuVSLAM and OpenVINS support on them".
- **NEAR-802:** status set to **Canceled**. Comment added: "Superseded 2026-10-30: the owner keeps both camera setups. The comparison is the new issue ‘Score cuVSLAM and OpenVINS on both camera setups in one table’."
- **NEAR-809:** moved from milestone S8 to S5c and renamed to "Model the Starling built-in tracking_front camera (AR0144) in sim".

Issues created in S5c (Backlog, unassigned, no due date):

| ID | Title | Description |
|---|---|---|
| NEAR-879 | Model the Starling built-in tracking_down camera (AR0144) in sim | The drone’s VIO uses tracking_front + tracking_down (vio_cams.conf). |
| NEAR-880 | Model the Starling built-in hires_front camera (IMX412) in sim | 1024×768 stream at 30 fps; 4056×3040 optional. |
| NEAR-881 | Model the Starling built-in hires_down camera (IMX412) in sim | |
| NEAR-882 | Model the Starling built-in ToF depth sensor in sim | pmd-tof-liow2, 10 fps. |
| NEAR-883 | Model the Starling built-in thermal camera (Lepton) in sim | Approximate: Isaac Sim has no native thermal sensor. |
| NEAR-884 | Model the Starling built-in IMUs (imu_apps, imu_px4) at their real mounts and rates | Needed by OpenVINS. |
| NEAR-885 | Run OpenVINS in sim on the Starling built-in sensors | What the drone runs (voxl-open-vins-server). |
| NEAR-886 | Re-run the flat-world and construction-site VIO tests on the Starling built-in sensors | Also records the built-in camera images for replay. The ZED-style results (ledger #15, #16) stay as they are. |
| NEAR-887 | Score cuVSLAM and OpenVINS on both camera setups in one table | One test, run once per setup and per VIO. |

### 2.4 Milestone renamed from "S8 Model the chosen camera and payload"

Applied name: **S8 Model the ZED-style added camera and Jetson payload**

- **NEAR-798:** renamed to "Add the Jetson and ZED-style camera weight to the Starling sim model".
- **NEAR-807, NEAR-808:** kept as they are.

### 2.5 Milestone order — PENDING manual action

HTX-R1 milestones still require manual ordering into this sequence:
S1, S2, S3, S4, S5, **S5d**, S6, **S5e**, S5b, S5c, S7, S8, S9, S10.

---

## Part 3 · Project HTX-R2 Starling Flight Bring-up (M2–M8)

### 3.1 Project renamed

Applied name: **HTX-R2 Starling Flight Bring-up (M2–M8)**

Previous name: HTX-R2 Starling Flight Bring-up (M2–M7).

### 3.2 Issue added to milestone "M2 · Drone setup and hand-carry, propellers off"

Created as Backlog, unassigned, with no due date.

| ID | Title | Description |
|---|---|---|
| NEAR-888 | Copy each Starling’s camera calibration and mount files (read only) | /data/modalai/opencv_*_intrinsics.yml, /etc/modalai/extrinsics.conf, voxl-camera-server.conf. Read only; change nothing on the drone. Feeds S5c in HTX-R1. |

### 3.3 Milestone created: "M8 · Evaluate NUS velocity policies on the real drones"

Placed after M7. Description:
> Fly the S5e sim scenarios on real Starlings with the same gate numbers. Gated by: M4 (fence braking measured), M7 (multi-drone) and HTX-R1 S5e. Done when (target): one, two, then three Starlings fly the S5e scenarios, speed capped below the sim-tested speed, fence on; the real results are compared with the sim results. Ticks only from real-flight records.

Issues created in it (Backlog, unassigned, no due date):

| ID | Title | Description |
|---|---|---|
| NEAR-889 | One Starling flies a NUS policy, speed capped below the sim-tested speed, fence on | RC takeover = MANUAL or KILL, never Position/Altitude. |
| NEAR-890 | Two Starlings fly the S5e scenario with collision avoidance | |
| NEAR-891 | Three Starlings fly the S5e scenarios with the same gates as in sim | |
| NEAR-892 | Compare the real-drone results with the sim results | Ticks only from real-flight records. |

---

## Part 4 · Project HTX-R3 Multi-Drone Localisation (VO + UWB)

Three issue renames applied:

- **NEAR-847** → "Cameras of both setups on all three sim drones, added one at a time with a GPU check". Description appended: "The Starling built-in cameras depend on HTX-R1 S5c."
- **NEAR-855** → "Hand-carry each camera setup with motion-capture positioning (mocap) and run cuVSLAM and OpenVINS on the laptop"
- **NEAR-856** → "Score cuVSLAM and OpenVINS against Motive"

---

## Part 5 · Verification completed

- HTX-R1: **55 issues, 14 milestones**.
- HTX-R2: **33 issues, 8 milestones**.
- HTX-R3: **17 issues, 6 milestones**.
- Total: **105 issues, 28 milestones**.
- **27 new issues**, NEAR-866–NEAR-892, listed with titles in the tables above; all Backlog, unassigned, with no due date.
- NEAR-809 moved from S8 to S5c; NEAR-802 Canceled; none deleted.
- NEAR-786, NEAR-787 and NEAR-788 are Done; NEAR-789 remains In Progress.
- Requested renames, descriptions, comments and move applied. New milestones S5d, S5e and M8 created; S5c and S8 renamed; HTX-R2 project renamed to M2–M8.
- HTX-R2 M8 is after M7. **HTX-R1 manual milestone ordering remains PENDING**, using the sequence in §2.5.
