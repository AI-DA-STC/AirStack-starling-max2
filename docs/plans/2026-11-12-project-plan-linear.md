# Starling swarm: project plan (Linear milestones and issues)

NEAR Lab · Linear snapshot: 12 November 2026, after the first real two-drone session ([instructions](2026-11-12-linear-agent-two-drone.md), [Linear agent's sync record](2026-11-12-linear-sync-record.md)); built from the 11 November snapshot plus that record

Linear is the source of truth: this file mirrors the three projects in Linear as of the snapshot above. Only completed milestones carry target dates. Each issue links to its Linear page. The "Done when" lines describe the acceptance test, not progress made.

## Reconciliation notes

- 3 projects, 28 milestones, 119 issues: 21 Done, 5 In Progress, 91 Backlog, 2 Canceled.
- 2026-11-12 sync (HTX-R2, real drones): NEAR-840 Done, closed for collision avoidance by the owner. One new issue, NEAR-951 (M7, Backlog), holds the part of NEAR-840 that has not flown. Comments on NEAR-819, 826, 831, 839. No title changed. Milestone progress is Linear's displayed figure: M7 20 %; M2 57 %, M3 20 %, M4 13 % unchanged. Eight findings are listed in the sync record as proposed, not created. HTX-R1 and HTX-R3 are unchanged.
- 2026-11-11 sync (HTX-R2, real drone): Done NEAR-814, 815, 818, 819, 822, 823, 825; In Progress NEAR-816, 817, 829, 830; comments on NEAR-820, 821, 826. No title changed. Milestone progress is Linear's displayed figure: R1 63 %, M2 57 %, M3 20 %, M4 13 %. HTX-R1 and HTX-R3 are unchanged.
- 2026-11-05 sync: NEAR-789 retitled (it was always keyboard teleop, not gamepad) and Done; NEAR-920 and NEAR-921 Done, closed by the owner without a video; NEAR-860 In Progress. Linear reports S5 at 81 %.
- 2026-11-06 sync: S5's description and Done when now say keyboard instead of gamepad (owner, 2026-11-05). No status or count changed.
- 2026-11-04 sync: NEAR-910 Done and NEAR-914 Canceled (both already held in Linear), NEAR-912 description replaced. Six new HTX-R1 issues: NEAR-920 and 921 (S5) and NEAR-922…925 (no milestone, listed after Project 1). The sync record counts all three projects: HTX-R1 66, HTX-R2 35, HTX-R3 17.
- 2026-11-02 sync: seven issues. NEAR-910 (In Progress) is in S5. NEAR-911, 912, 913 and 916 (Backlog) are in S5d. NEAR-914 (Backlog) is in M2 and NEAR-915 (Backlog) is in M5. Nothing else changed. The sync record gives counts for HTX-R1 (60) and HTX-R2 (35) only. HTX-R3 is not in it, so its 17 issues are carried over from the 30 October snapshot.
- 2026-10-30 rescope: new milestones S5d, S5e (HTX-R1) and M8 (HTX-R2); S5c and S8 renamed; 27 new issues NEAR-866…892; NEAR-809 moved S8 → S5c; NEAR-802 Canceled; NEAR-786/787/788 Done; HTX-R2 renamed (M2–M8).
- Progress for S5 and the new milestones is computed, not read from Linear: Done counts 1 and In Progress ¼ (the 26 October figures imply this: S5 was 4 % with one of six In Progress), over the issues not Canceled. On 2 November this gave S5 50 %. From 5 November S5's 81 % is Linear's own figure (7 Done of 9, one In Progress), which matches the same rule; S5d stays 0 %. The rest are unchanged from 26 October.
- Milestones are listed in Linear's order. The owner dragged HTX-R1 into the work order on 30 October, after the sync record (which still reads PENDING); codes therefore do not sort (S5d before S6, S5e after S6).
- Project 1 has 66 issues (55 on 30 October, five on 2 November, six on 4 November); redundant NEAR-799 removed (26 October).

## How the work is split

| Project | Question | Where |
|---|---|---|
| HTX-R1 Swarm Sim Validation (Isaac) | Does the candidate position source → PX4 → swarm controller and collision-avoidance pipeline work, and how does it fail? | Isaac Sim on the lab laptop |
| HTX-R2 Starling Flight Bring-up (M2–M8) | Does the same software fly real Starling 2 Max drones safely under mocap? | Mocap room |
| HTX-R3 Multi-Drone Localisation (VO + UWB) | Without mocap, which approach keeps drones positioned correctly relative to one another? | Literature, simulation, then real drones |

Simulation precedes real flight to distinguish software/algorithm failures from hardware, network and mocap problems. Real-drone milestones repeat capabilities rehearsed in simulation.

### Terms

- Mocap: OptiTrack motion capture; indoor position source rather than GPS.
- PX4: drone flight-controller software, including its position estimator.
- Swarm controller / commander: ground software sending targets and applying collision avoidance (CBF).
- cuVSLAM: NVIDIA camera-based tracking. VO uses camera images; VIO combines camera and IMU.
- Sim mocap: simulator ground-truth position supplied to PX4 as mocap-style input.
- UWB: ultra-wideband radios measuring inter-drone distances.
- Teleop: gamepad flying through the swarm controller.

---

## Project 1 · HTX-R1 Swarm Sim Validation (Isaac)

[Linear project](https://linear.app/nearlab/project/htx-r1-swarm-sim-validation-isaac-649103a747b1)

**Status:** In Progress. **Start:** 2026-10-19. **Target:** not set. **Inventory:** 14 milestones, 66 issues (12 Done, 1 In Progress, 52 Backlog, 1 Canceled).

Test a candidate swarm flight pipeline in Isaac Sim: position source → PX4 → commander and CBF. Find out what works before deciding what goes onto the real Starlings. Simulation makes failures cheaper to investigate and must match indoor flight with GPS off. Mocap is expected back around 9 Nov; the HTX demo is mid-February and strategy teams need a multi-drone test bed from December. Real flight belongs to Project 2; shared-frame research belongs to Project 3.

### S1 Starling 2 Max sim drones

**Linear target:** 2026-10-21. **Progress:** 100%.

Built the model from CMU's measured mass, inertia and motor data using real-drone controller gains. Fixed a 9 Hz pitch wobble by halving sim rate gains. Three drones flew random goals under CBF and landed cleanly.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-782](https://linear.app/nearlab/issue/NEAR-782) | Build and fly the Starling 2 Max sim model | Done |

### S2 Stereo camera on a sim drone

**Linear target:** 2026-10-22. **Progress:** 100%.

Added a simulated ZED stereo camera to drone_1 at 640×480. Camera topics could not reach the robot container across networks; a container on Isaac's network provided the workaround.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-783](https://linear.app/nearlab/issue/NEAR-783) | S2 Add a stereo camera to drone_1 and route its images | Done |

### S3 Evaluate cuVSLAM in sim

**Linear target:** 2026-10-22. **Progress:** 100%.

Ran cuVSLAM on drone_1 and scored it against PX4's estimate. The pipeline worked end to end, but the empty default world produced 5–10 m jumps when only sky and a grid floor were visible.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-784](https://linear.app/nearlab/issue/NEAR-784) | S3 Run cuVSLAM on drone_1 and score it | Done |

### S4 Construction-site environment

**Linear target:** 2026-10-23. **Progress:** 100%.

Converted the lab's UE4 construction site into an Isaac world, loaded with `ENV_USD`, with a full version and 40 m crop. Three drones plus a camera used 4.3 GB GPU memory. cuVSLAM recorded 0.08 m error over 162 m, with no jumps.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-785](https://linear.app/nearlab/issue/NEAR-785) | S4 Convert the construction site into an Isaac Sim world | Done |
| [NEAR-859](https://linear.app/nearlab/issue/NEAR-859) | Fly 3 drones with cuVSLAM in the construction site and score it | Done |

### S5 Finish basic sim flight checks

**Linear target:** not set. **Progress:** 81%.

Re-run the core flight tests on the updated Starling sim model, and get one-drone keyboard flying working in the construction site. Hand-flying is how S5b will build its map, so this milestone prepares it.

**Done when:** hover and 1 m steps are re-run and recorded; the three-drone crossing with collision avoidance is re-run and recorded; live gain tuning from the panel is tried in sim; drone_1 is hand-flown by keyboard in the construction site with cuVSLAM running, and the flight is scored.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-786](https://linear.app/nearlab/issue/NEAR-786) | Re-run hover and 1 m step test on the updated sim drone | Done |
| [NEAR-787](https://linear.app/nearlab/issue/NEAR-787) | Re-run three-drone crossing with collision avoidance and record it | Done |
| [NEAR-788](https://linear.app/nearlab/issue/NEAR-788) | Try live gain tuning from the panel in sim | Done |
| [NEAR-789](https://linear.app/nearlab/issue/NEAR-789) | Set up one-drone keyboard teleop in the construction site (keys move the drone, release holds) | Done |
| [NEAR-790](https://linear.app/nearlab/issue/NEAR-790) | Hand-fly drone_1 with cuVSLAM running, record and score the flight | Backlog |
| [NEAR-860](https://linear.app/nearlab/issue/NEAR-860) | Record the stereo camera images so a flight can be replayed through cuVSLAM | In Progress |
| [NEAR-910](https://linear.app/nearlab/issue/NEAR-910) | Retune the sim airframe’s yaw-rate gains so the heading settles after a turn | Done |
| [NEAR-920](https://linear.app/nearlab/issue/NEAR-920) | Sim keyboard teleop flies in Drive mode (BODY), F switches to Room mode, with the forward-follows-the-nose test | Done |
| [NEAR-921](https://linear.app/nearlab/issue/NEAR-921) | Teleop strip inside the cuVSLAM Foxglove window, with a chase view | Done |

### S5d · Sim flies the real command route (px4_interface)

**Linear target:** not set. **Progress:** 0%.

The sim drone takes the same command path as the real drone (commander → trajectory → px4_interface → uXRCE-DDS → PX4), so sim results carry over.

**Done when:** one sim drone takes off, hovers and lands through px4_interface with MAVROS not started; the hover and 1 m step test passes on gates no looser than ledger #17–#19, in vehicle time; the release and 90° turn test shows neither MAVROS-route bug; the crossing is re-run against ledger #22; every sim record names its route and camera setup and prints the remaining sim-vs-real differences.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-866](https://linear.app/nearlab/issue/NEAR-866) | One sim drone flies takeoff, hover and land through px4_interface with MAVROS not started | Backlog |
| [NEAR-867](https://linear.app/nearlab/issue/NEAR-867) | Sim records name and prove their command route and camera setup | Backlog |
| [NEAR-868](https://linear.app/nearlab/issue/NEAR-868) | Re-run the hover and 1 m step test on the px4_interface route and compare with the MAVROS-route results | Backlog |
| [NEAR-869](https://linear.app/nearlab/issue/NEAR-869) | Release-to-hold and 90° turn test on the px4_interface route | Backlog |
| [NEAR-870](https://linear.app/nearlab/issue/NEAR-870) | Check which PX4 messages decode on the sim’s PX4 v1.16 | Backlog |
| [NEAR-871](https://linear.app/nearlab/issue/NEAR-871) | Record Isaac’s real-time factor on every run and add a real-time pacing switch | Backlog |
| [NEAR-872](https://linear.app/nearlab/issue/NEAR-872) | Re-run the three-drone crossing on the px4_interface route | Backlog |
| [NEAR-873](https://linear.app/nearlab/issue/NEAR-873) | Print the remaining sim-vs-real differences on every sim record | Backlog |
| [NEAR-911](https://linear.app/nearlab/issue/NEAR-911) | Check heading hold (MC_YAW_P) on the px4_interface route with the yaw-step test | Backlog |
| [NEAR-912](https://linear.app/nearlab/issue/NEAR-912) | Match the sim airframe’s MPC speed and acceleration limits to the real drone’s | Backlog |
| [NEAR-913](https://linear.app/nearlab/issue/NEAR-913) | Model rotor reaction torque and rotational drag in the sim Starling, then re-run the yaw-step test | Backlog |
| [NEAR-916](https://linear.app/nearlab/issue/NEAR-916) | Compare every PX4 parameter between the sim and the real drone | Backlog |

### S6 Sim mocap

**Linear target:** not set. **Progress:** 0%.

Make the sim drones get their position the way the real indoor drones do: the simulator's true position is fed to PX4 as if it were mocap, with GPS off and the real drone's estimator settings. Done when: three drones take off, fly random goals and land on sim mocap.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-803](https://linear.app/nearlab/issue/NEAR-803) | Publish the simulator’s true drone positions | Backlog |
| [NEAR-804](https://linear.app/nearlab/issue/NEAR-804) | Send them into PX4 as mocap-style position | Backlog |
| [NEAR-805](https://linear.app/nearlab/issue/NEAR-805) | Sim setting that turns GPS off and uses the real drone’s estimator values | Backlog |
| [NEAR-806](https://linear.app/nearlab/issue/NEAR-806) | Fly three drones on sim mocap: takeoff, random goals, land | Backlog |

### S5e · Evaluate NUS velocity policies in sim

**Linear target:** not set. **Progress:** 0%.

Check a NUS policy in sim, on the real command route, before it flies on a real drone. NUS policies output one velocity per drone; CMU’s commander filters them with its CBF. Gated by: S5d, S6, and the real-time factor issue.

**Done when:** the velocity contract is written once and shared with NUS; the plug-in point and its teleop behaviour are decided; one, two and three policy drones fly in sim with collision avoidance on and off, each with one command and a record; the separation gate is agreed. Results say "observed in sim", never "validated".

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-874](https://linear.app/nearlab/issue/NEAR-874) | Write the velocity contract with NUS and CMU (frame, units, limits, rate, timeout) | Backlog |
| [NEAR-875](https://linear.app/nearlab/issue/NEAR-875) | Decide how a policy drone plugs into the commander (leash, teleop fence, hold on timeout) | Backlog |
| [NEAR-876](https://linear.app/nearlab/issue/NEAR-876) | Run a NUS policy in sim with one command and a record (gates written first) | Backlog |
| [NEAR-877](https://linear.app/nearlab/issue/NEAR-877) | Fly one, two, then three policy drones in sim with collision avoidance on and off | Backlog |
| [NEAR-878](https://linear.app/nearlab/issue/NEAR-878) | Agree the separation gate for policy runs | Backlog |

### S5b · Map the construction site with cuVSLAM

**Linear target:** not set. **Progress:** 0%.

Hand-fly a mapping loop, save the map and test whether a fresh drone run can localise in it. A shared map could give every drone one coordinate frame without UWB.

**Done when:** a map is saved; fresh runs localise from several starts/headings with success rate and time recorded; positions agree with simulator ground truth.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-791](https://linear.app/nearlab/issue/NEAR-791) | Add a mapping mode to the cuVSLAM node | Backlog |
| [NEAR-792](https://linear.app/nearlab/issue/NEAR-792) | Hand-fly a mapping loop and save the map | Backlog |
| [NEAR-793](https://linear.app/nearlab/issue/NEAR-793) | Localise in the saved map from 5+ starting points | Backlog |
| [NEAR-794](https://linear.app/nearlab/issue/NEAR-794) | Compare the localised position with the simulator’s position | Backlog |

### S5c · Compare the two camera setups for cuVSLAM and OpenVINS

**Linear target:** not set. **Progress:** 0%.

Two camera setups are kept: the ZED-style added camera (stereo + Jetson payload) and the Starling built-in sensors.

**Done when:** every Starling built-in sensor is modelled at its real mount, resolution and rate; OpenVINS runs in sim; the flat-world and site VIO tests are re-run on the built-in sensors; one table scores cuVSLAM and OpenVINS on both setups.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-800](https://linear.app/nearlab/issue/NEAR-800) | Run cuVSLAM in monocular mode on a replayed flight and score it against stereo | Backlog |
| [NEAR-801](https://linear.app/nearlab/issue/NEAR-801) | List the Starling 2 Max’s sensors and check which modes cuVSLAM and OpenVINS support on them | Backlog |
| [NEAR-802](https://linear.app/nearlab/issue/NEAR-802) | Decide the camera (built-in mono / built-in stereo / added stereo) and write down why | Canceled |
| [NEAR-809](https://linear.app/nearlab/issue/NEAR-809) | Model the Starling built-in tracking_front camera (AR0144) in sim | Backlog |
| [NEAR-879](https://linear.app/nearlab/issue/NEAR-879) | Model the Starling built-in tracking_down camera (AR0144) in sim | Backlog |
| [NEAR-880](https://linear.app/nearlab/issue/NEAR-880) | Model the Starling built-in hires_front camera (IMX412) in sim | Backlog |
| [NEAR-881](https://linear.app/nearlab/issue/NEAR-881) | Model the Starling built-in hires_down camera (IMX412) in sim | Backlog |
| [NEAR-882](https://linear.app/nearlab/issue/NEAR-882) | Model the Starling built-in ToF depth sensor in sim | Backlog |
| [NEAR-883](https://linear.app/nearlab/issue/NEAR-883) | Model the Starling built-in thermal camera (Lepton) in sim | Backlog |
| [NEAR-884](https://linear.app/nearlab/issue/NEAR-884) | Model the Starling built-in IMUs (imu_apps, imu_px4) at their real mounts and rates | Backlog |
| [NEAR-885](https://linear.app/nearlab/issue/NEAR-885) | Run OpenVINS in sim on the Starling built-in sensors | Backlog |
| [NEAR-886](https://linear.app/nearlab/issue/NEAR-886) | Re-run the flat-world and construction-site VIO tests on the Starling built-in sensors | Backlog |
| [NEAR-887](https://linear.app/nearlab/issue/NEAR-887) | Score cuVSLAM and OpenVINS on both camera setups in one table | Backlog |

### S7 drone_1 flies on cuVSLAM

**Linear target:** not set. **Progress:** 0%.

Hand over position from sim mocap to cuVSLAM with automatic fallback. **Done when:** source switching/fallback works; hand-flown hold, out-and-back, spin, open-view and hard-stick tests pass; a scripted flight is scored against true position.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-795](https://linear.app/nearlab/issue/NEAR-795) | Position source switch: sim mocap or cuVSLAM, with automatic fallback | Backlog |
| [NEAR-796](https://linear.app/nearlab/issue/NEAR-796) | Hand-flown handover tests (hold, out-and-back, spin, open view, hard stick) | Backlog |
| [NEAR-797](https://linear.app/nearlab/issue/NEAR-797) | Scripted flight on cuVSLAM, scored against true position | Backlog |

### S8 Model the ZED-style added camera and Jetson payload

**Linear target:** not set. **Progress:** 0%.

Model the chosen camera, its IMU input and Jetson/camera weight. **Done when:** the camera feeds cuVSLAM; camera+IMU is scored against camera-only; the model with 300–360 g added passes hover, step and crossing checks.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-798](https://linear.app/nearlab/issue/NEAR-798) | Add the Jetson and ZED-style camera weight to the Starling sim model | Backlog |
| [NEAR-807](https://linear.app/nearlab/issue/NEAR-807) | Re-run hover, step and crossing tests on the heavier model | Backlog |
| [NEAR-808](https://linear.app/nearlab/issue/NEAR-808) | Feed drone_1’s IMU into cuVSLAM (camera-only → camera + IMU) and compare the scores | Backlog |

### S9 Safe failover

**Linear target:** not set. **Progress:** 0%.

Keep the controller safe through stale, missing or switched position. **Done when:** no unsafe movement follows stale/missing positions, and source switching moves the drone less than 30 cm.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-810](https://linear.app/nearlab/issue/NEAR-810) | Controller handles stale or missing positions (tests first) | Backlog |
| [NEAR-811](https://linear.app/nearlab/issue/NEAR-811) | Measure and reduce the jump when the position source switches | Backlog |

### S10 Scale test

**Linear target:** not set. **Progress:** 0%.

**Done when:** 6–10 simulated drones run without cameras; controller load and recording size are measured.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-812](https://linear.app/nearlab/issue/NEAR-812) | Run 6 then 10 headless sim drones | Backlog |
| [NEAR-813](https://linear.app/nearlab/issue/NEAR-813) | Record controller load and recording size | Backlog |

## HTX-R1 issues without a milestone

In project HTX-R1, with no milestone in Linear (created 2026-11-04).

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-922](https://linear.app/nearlab/issue/NEAR-922) | Launch one safe_teleop and relay per drone for keyboard switching | Backlog |
| [NEAR-923](https://linear.app/nearlab/issue/NEAR-923) | Live cuVSLAM map panel in the teleop layout | Backlog |
| [NEAR-924](https://linear.app/nearlab/issue/NEAR-924) | Draw the PX4 position in the chase view | Backlog |
| [NEAR-925](https://linear.app/nearlab/issue/NEAR-925) | Find why the cuVSLAM image freezes briefly at takeoff in the teleop layout | Backlog |

---

## Project 2 · HTX-R2 Starling Flight Bring-up (M2–M8)

[Linear project](https://linear.app/nearlab/project/htx-r2-starling-flight-bring-up-m2-m7-269b3d72d5ce)

**Status:** Backlog. **Start:** 2026-11-09. **Target:** not set. **Inventory:** 8 milestones, 36 issues (8 Done, 4 In Progress, 23 Backlog, 1 Canceled).

Fly real Starling 2 Max drones on the new ground-control software under mocap, one safety-checked step at a time. The software changed on 7 Oct, so September's flight capabilities must be re-earned. Each step begins only after the previous one passes; every flight follows the preflight card. Mocap is expected back around 9 Nov. Simulation and flight without mocap are outside this project's scope.

### R1 · New mocap and network pipeline

**Linear target:** not set. **Progress:** 63%.

Bring upgraded OptiTrack online and rebuild the camera-to-drone network path. The laptop needs the mocap PC's 192.168.9.x subnet because multicast does not cross the router; the drone uses a separate routed subnet.

**Done when:** Motive calibration, ground plane, axes and rigid body are configured; full-rate streaming lasts 10 minutes without stalls; laptop/drone communicate both ways; PX4 receives correct-axis mocap; settings are documented.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-814](https://linear.app/nearlab/issue/NEAR-814) | Network: laptop on the mocap subnet (192.168.9.x) with the route to the drone subnet; drone gets its WiFi address; both ping each other | Done |
| [NEAR-815](https://linear.app/nearlab/issue/NEAR-815) | Set up the upgraded Motive: calibrate (wand, ground plane, axis convention) and create the Starling rigid body | Done |
| [NEAR-816](https://linear.app/nearlab/issue/NEAR-816) | Mocap stream end to end: laptop receives it at full rate for 10 min with no stalls, it reaches the drone’s PX4, and moving the drone by hand moves the position the same way on every axis | In Progress |
| [NEAR-817](https://linear.app/nearlab/issue/NEAR-817) | Record the new Motive version, IP and streaming settings in the lab docs and pictures | In Progress |

### M2 · Drone setup and hand-carry, propellers off

**Linear target:** not set. **Progress:** 57%.

Set up the drone and check end-to-end position with propellers off. **Done when:** drone ID matches controller target, only one watchdog runs, estimator fuses mocap, the panel tracks the hand-carried drone correctly, and kill switch is checked props-off.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-818](https://linear.app/nearlab/issue/NEAR-818) | Re-run the drone setup script, then reboot the drone (never restart the flight software service) | Done |
| [NEAR-819](https://linear.app/nearlab/issue/NEAR-819) | Confirm the drone ID matches the controller’s target | Done |
| [NEAR-820](https://linear.app/nearlab/issue/NEAR-820) | Confirm only one connection watchdog runs on the drone | Backlog |
| [NEAR-821](https://linear.app/nearlab/issue/NEAR-821) | Check the controller’s messages match the drone’s PX4 version | Backlog |
| [NEAR-822](https://linear.app/nearlab/issue/NEAR-822) | Hand-carry with props off: panel tracks the drone, estimator fuses mocap | Done |
| [NEAR-823](https://linear.app/nearlab/issue/NEAR-823) | Props-off kill switch test | Done |
| [NEAR-888](https://linear.app/nearlab/issue/NEAR-888) | Copy each Starling’s camera calibration and mount files (read only) | Backlog |
| [NEAR-914](https://linear.app/nearlab/issue/NEAR-914) | Read the drone’s MPC speed and acceleration limits in QGC and record which set it flies | Canceled |

### M3 · First flight on the new software

**Linear target:** not set. **Progress:** 20%.

Take off, hover and land under software control inside the fence. **Done when:** every command is acknowledged; landing settles and disarms; dummy-payload hover yields hover throttle and flight time.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-824](https://linear.app/nearlab/issue/NEAR-824) | Preflight card dry run with the new software | Backlog |
| [NEAR-825](https://linear.app/nearlab/issue/NEAR-825) | First flight: takeoff, hover, land | Done |
| [NEAR-826](https://linear.app/nearlab/issue/NEAR-826) | Landing test: settle on the ground, then disarm | Backlog |
| [NEAR-827](https://linear.app/nearlab/issue/NEAR-827) | Weigh the flight-ready drone and fit a dummy payload mass | Backlog |
| [NEAR-828](https://linear.app/nearlab/issue/NEAR-828) | Dummy-payload hover: hover throttle and flight time to 20 % battery | Backlog |

NEAR-824 description: walk through the preflight card on the ground, props off, QGC visible; fix steps that no longer match.

### M4 · Goal flights with the braking fence

**Linear target:** not set. **Progress:** 13%.

**Done when:** goal legs use the smooth speed-limited profile; wall braking distance is measured; gains change live; hold stops the drone where expected.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-829](https://linear.app/nearlab/issue/NEAR-829) | Goal legs on the speed-limited profile | In Progress |
| [NEAR-830](https://linear.app/nearlab/issue/NEAR-830) | Measure braking at the fence walls | In Progress |
| [NEAR-831](https://linear.app/nearlab/issue/NEAR-831) | Change gains live from the panel in flight | Backlog |
| [NEAR-832](https://linear.app/nearlab/issue/NEAR-832) | Check where a hold stops the drone | Backlog |

### M5 · Gamepad flying on the real drone

**Linear target:** not set. **Progress:** 0%.

**Done when:** yaw direction is correct (not proved by sim), the gamepad fence holds, stick release holds position, and coast distance is measured.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-833](https://linear.app/nearlab/issue/NEAR-833) | Check the yaw stick turns the drone the right way, slowly and low | Backlog |
| [NEAR-834](https://linear.app/nearlab/issue/NEAR-834) | Gamepad fence test | Backlog |
| [NEAR-835](https://linear.app/nearlab/issue/NEAR-835) | Release-to-hold test and coast distance | Backlog |
| [NEAR-915](https://linear.app/nearlab/issue/NEAR-915) | Yaw-step check on the real Starling: overshoot and settle after a yaw pulse, compared with the sim | Backlog |

### M6 · LED strips

**Linear target:** not set. **Progress:** 0%.

Optional hardware; starts when the strip arrives. **Done when:** LED service runs on the drone; green by default, red when collision avoidance acts; motor LEDs muted.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-836](https://linear.app/nearlab/issue/NEAR-836) | Fit the LED strip and start the LED service on the drone | Backlog |
| [NEAR-837](https://linear.app/nearlab/issue/NEAR-837) | Check green / red behaviour in flight | Backlog |

### M7 · Multi-drone

**Linear target:** not set. **Progress:** 20%.

Fly two, then three real drones under mocap. **Done when:** formations, random goals with collision avoidance and intruder-squeeze tests fly. The plan states this depends on the new Starlings arriving; issue status remains Backlog.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-838](https://linear.app/nearlab/issue/NEAR-838) | Check the hardware order went out (Starlings, 2 stereo cameras, LED strip, 2.4 GHz radio) | Backlog |
| [NEAR-839](https://linear.app/nearlab/issue/NEAR-839) | Set up each new Starling (one at a time, setup guide) | Backlog |
| [NEAR-840](https://linear.app/nearlab/issue/NEAR-840) | Two drones: formation and random goals with collision avoidance | Done |
| [NEAR-841](https://linear.app/nearlab/issue/NEAR-841) | Three drones: intruder-squeeze test | Backlog |
| [NEAR-951](https://linear.app/nearlab/issue/NEAR-951) | Two drones: formation and random goals | Backlog |

### M8 · Evaluate NUS velocity policies on the real drones

**Linear target:** not set. **Progress:** 0%.

Fly the S5e sim scenarios on real Starlings with the same gate numbers. Gated by: M4 (fence braking measured), M7 (multi-drone) and HTX-R1 S5e.

**Done when:** one, two, then three Starlings fly the S5e scenarios, speed capped below the sim-tested speed, fence on; the real results are compared with the sim results. Ticks only from real-flight records.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-889](https://linear.app/nearlab/issue/NEAR-889) | One Starling flies a NUS policy, speed capped below the sim-tested speed, fence on | Backlog |
| [NEAR-890](https://linear.app/nearlab/issue/NEAR-890) | Two Starlings fly the S5e scenario with collision avoidance | Backlog |
| [NEAR-891](https://linear.app/nearlab/issue/NEAR-891) | Three Starlings fly the S5e scenarios with the same gates as in sim | Backlog |
| [NEAR-892](https://linear.app/nearlab/issue/NEAR-892) | Compare the real-drone results with the sim results | Backlog |

---

## Project 3 · HTX-R3 Multi-Drone Localisation (VO + UWB)

[Linear project](https://linear.app/nearlab/project/htx-r3-multi-drone-localisation-vo-uwb-b4a877b2fd7c)

**Status:** Backlog. **Start:** 2026-10-22. **Target:** not set. **Inventory:** 6 milestones, 17 issues (1 Done, 16 Backlog).

Find which approach keeps drones positioned correctly relative to one another without mocap, and its costs, before hardware design is fixed. Compare collaborative SLAM, individual localisation in a shared pre-built map (Project 1 S5b), and individual VO aligned by inter-drone UWB distances. Heading is the known weak point of the third approach.

### L0 · Literature review

**Linear target:** 2026-10-22. **Progress:** 100%.

Reviewed 13 methods including Omni-swarm, D²SLAM, Swarm-SLAM, Kimera-Multi and COVINS for real-drone evidence. Collaborative SLAM is not ready for this effort; shared maps merit a one-day trial; own VO + UWB alignment is the recommended baseline, with an extra heading source such as two UWB tags per drone.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-842](https://linear.app/nearlab/issue/NEAR-842) | Literature review with validation evidence | Done |

### L1 · Team review pack

**Linear target:** not set. **Progress:** 0%.

**Done when:** the review includes the literature table, flat-world versus construction-site cuVSLAM result, effort log, recommendation and open questions.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-843](https://linear.app/nearlab/issue/NEAR-843) | Results table: what was tested, what it showed | Backlog |
| [NEAR-844](https://linear.app/nearlab/issue/NEAR-844) | Recommendation and open questions | Backlog |
| [NEAR-845](https://linear.app/nearlab/issue/NEAR-845) | Update the effort log | Backlog |
| [NEAR-846](https://linear.app/nearlab/issue/NEAR-846) | Slides for the review | Backlog |

### L2 · Three-drone dataset and UWB emulator

**Linear target:** not set. **Progress:** 0%.

Record comparison flights and emulate inter-drone UWB distances. **Done when:** cameras run on all three drones; hover, formation, crossing and a 10–15 min figure-8 are recorded with true positions; the emulator includes realistic noise, bias and blocked-line errors from the papers.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-847](https://linear.app/nearlab/issue/NEAR-847) | Cameras of both setups on all three sim drones, added one at a time with a GPU check | Backlog |
| [NEAR-848](https://linear.app/nearlab/issue/NEAR-848) | Record hover, formation, crossing and long figure-8 with true positions | Backlog |
| [NEAR-849](https://linear.app/nearlab/issue/NEAR-849) | UWB distance emulator between drones (noise, bias, blocked-line errors) | Backlog |
| [NEAR-850](https://linear.app/nearlab/issue/NEAR-850) | Drift injector to test many drones without many cameras | Backlog |
| [NEAR-851](https://linear.app/nearlab/issue/NEAR-851) | Run one public multi-drone dataset (MILUV) for a real-data result | Backlog |

### L3 · Own visual odometry + UWB alignment

**Linear target:** not set. **Progress:** 0%.

Build and measure continuous UWB frame alignment. **Done when:** pairwise relative-position error over time, heading error and convergence time are measured; one versus two UWB tags per drone are compared.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-852](https://linear.app/nearlab/issue/NEAR-852) | Aligner: continuous frame alignment from positions and UWB distances | Backlog |
| [NEAR-853](https://linear.app/nearlab/issue/NEAR-853) | Measure pair error, heading error and convergence time | Backlog |
| [NEAR-854](https://linear.app/nearlab/issue/NEAR-854) | Compare one vs two UWB tags per drone | Backlog |

### L4 · First real-hardware number

**Linear target:** not set. **Progress:** 0%.

Hand-carry the selected camera under mocap with cuVSLAM. **Done when:** its trajectory is scored against Motive/mocap.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-855](https://linear.app/nearlab/issue/NEAR-855) | Hand-carry each camera setup with motion-capture positioning (mocap) and run cuVSLAM and OpenVINS on the laptop | Backlog |
| [NEAR-856](https://linear.app/nearlab/issue/NEAR-856) | Score cuVSLAM and OpenVINS against Motive | Backlog |

### L5 · Scale to 10 sim drones

**Linear target:** not set. **Progress:** 0%.

**Done when:** alignment runs on 10 simulated drones; error and UWB/WiFi bandwidth are measured.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-857](https://linear.app/nearlab/issue/NEAR-857) | Run the aligner on 10 sim drones | Backlog |
| [NEAR-858](https://linear.app/nearlab/issue/NEAR-858) | Measure error and UWB/WiFi bandwidth | Backlog |

---

## Where things live in the repo

Sim results and run records: `localisation/results/`. How to run the camera-world sim: `localisation/README.md`. Real-drone procedures: `docs/RUNBOOK.md` and `docs/PREFLIGHT.md`. Milestone ladder and test history: `docs/MILESTONES.md`.

## Inventory check

| Project | Milestones | Issues | Done | In Progress | Backlog |
|---|---:|---:|---:|---:|---:|
| HTX-R1 | 14 | 66 | 12 | 1 | 52 |
| HTX-R2 | 8 | 36 | 8 | 4 | 23 |
| HTX-R3 | 6 | 17 | 1 | 0 | 16 |
| Total | 28 | 119 | 21 | 5 | 91 |

Canceled: 2 (NEAR-802, HTX-R1; NEAR-914, HTX-R2), counted in Issues, not in the status columns.
