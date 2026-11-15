# Starling swarm: project plan (Linear milestones and issues)

NEAR Lab · Linear snapshot: 26 October 2026 11:53 Asia/Singapore

Linear is the source of truth: this file mirrors the three projects in Linear as of the snapshot above. Only completed milestones carry target dates. Each issue links to its Linear page. The "Done when" lines describe the acceptance test, not progress made.

## Reconciliation notes

- 3 projects, 25 milestones, 78 issues: 6 Done, 1 In Progress, 71 Backlog.
- Project 1 has 33 issues; redundant NEAR-799 removed.
- All three projects have no target date in Linear. Only S1–S4 and L0 have milestone target dates; other milestone targets are unset.

## How the work is split

| Project | Question | Where |
|---|---|---|
| HTX-R1 Swarm Sim Validation (Isaac) | Does the candidate position source → PX4 → swarm controller and collision-avoidance pipeline work, and how does it fail? | Isaac Sim on the lab laptop |
| HTX-R2 Starling Flight Bring-up (M2–M7) | Does the same software fly real Starling 2 Max drones safely under mocap? | Mocap room |
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

**Status:** In Progress. **Start:** 2026-10-19. **Target:** not set. **Inventory:** 12 milestones, 33 issues (5 Done, 1 In Progress, 27 Backlog).

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

**Linear target:** not set. **Progress:** 4%.

Re-run core flight checks on the updated model and prepare gamepad flying for S5b mapping.

**Done when:** hover and 1 m steps, three-drone collision-avoidance crossing and live gain tuning are tried and recorded; drone_1 is hand-flown in the construction site with cuVSLAM, camera recording and scoring.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-786](https://linear.app/nearlab/issue/NEAR-786) | Re-run hover and 1 m step test on the updated sim drone | Backlog |
| [NEAR-787](https://linear.app/nearlab/issue/NEAR-787) | Re-run three-drone crossing with collision avoidance and record it | Backlog |
| [NEAR-788](https://linear.app/nearlab/issue/NEAR-788) | Try live gain tuning from the panel in sim | Backlog |
| [NEAR-789](https://linear.app/nearlab/issue/NEAR-789) | Set up one-drone gamepad teleop in the construction site (pad detected, sticks move the drone, release holds) | In Progress |
| [NEAR-790](https://linear.app/nearlab/issue/NEAR-790) | Hand-fly drone_1 with cuVSLAM running, record and score the flight | Backlog |
| [NEAR-860](https://linear.app/nearlab/issue/NEAR-860) | Record the stereo camera images so a flight can be replayed through cuVSLAM | Backlog |

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

### S5c · Choose the camera for cuVSLAM

**Linear target:** not set. **Progress:** 0%.

Determine the real Starling camera before hardware decisions. Compare mono and stereo; investigate built-in camera lenses, resolution, direction, compatibility and existing VO use. Added stereo (RealSense D435i class) is a fallback with weight and Jetson costs. Monocular scale and drift are risks.

**Done when:** mono/stereo results are comparable, built-in camera suitability has a reasoned yes/no answer, and the decision is written and shared before ordering.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-800](https://linear.app/nearlab/issue/NEAR-800) | Run cuVSLAM in monocular mode on a replayed flight and score it against stereo | Backlog |
| [NEAR-801](https://linear.app/nearlab/issue/NEAR-801) | List the Starling 2 Max’s built-in cameras and check whether cuVSLAM can use them | Backlog |
| [NEAR-802](https://linear.app/nearlab/issue/NEAR-802) | Decide the camera (built-in mono / built-in stereo / added stereo) and write down why | Backlog |

### S6 Sim mocap

**Linear target:** not set. **Progress:** 0%.

Make the sim drones get their position the way the real indoor drones do: the simulator's true position is fed to PX4 as if it were mocap, with GPS off and the real drone's estimator settings. Done when: three drones take off, fly random goals and land on sim mocap.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-803](https://linear.app/nearlab/issue/NEAR-803) | Publish the simulator’s true drone positions | Backlog |
| [NEAR-804](https://linear.app/nearlab/issue/NEAR-804) | Send them into PX4 as mocap-style position | Backlog |
| [NEAR-805](https://linear.app/nearlab/issue/NEAR-805) | Sim setting that turns GPS off and uses the real drone’s estimator values | Backlog |
| [NEAR-806](https://linear.app/nearlab/issue/NEAR-806) | Fly three drones on sim mocap: takeoff, random goals, land | Backlog |

### S7 drone_1 flies on cuVSLAM

**Linear target:** not set. **Progress:** 0%.

Hand over position from sim mocap to cuVSLAM with automatic fallback. **Done when:** source switching/fallback works; hand-flown hold, out-and-back, spin, open-view and hard-stick tests pass; a scripted flight is scored against true position.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-795](https://linear.app/nearlab/issue/NEAR-795) | Position source switch: sim mocap or cuVSLAM, with automatic fallback | Backlog |
| [NEAR-796](https://linear.app/nearlab/issue/NEAR-796) | Hand-flown handover tests (hold, out-and-back, spin, open view, hard stick) | Backlog |
| [NEAR-797](https://linear.app/nearlab/issue/NEAR-797) | Scripted flight on cuVSLAM, scored against true position | Backlog |

### S8 Model the chosen camera and payload

**Linear target:** not set. **Progress:** 0%.

Model the chosen camera, its IMU input and Jetson/camera weight. **Done when:** the camera feeds cuVSLAM; camera+IMU is scored against camera-only; the model with 300–360 g added passes hover, step and crossing checks.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-798](https://linear.app/nearlab/issue/NEAR-798) | Add Jetson and camera weight to the Starling sim model | Backlog |
| [NEAR-807](https://linear.app/nearlab/issue/NEAR-807) | Re-run hover, step and crossing tests on the heavier model | Backlog |
| [NEAR-808](https://linear.app/nearlab/issue/NEAR-808) | Feed drone_1’s IMU into cuVSLAM (camera-only → camera + IMU) and compare the scores | Backlog |
| [NEAR-809](https://linear.app/nearlab/issue/NEAR-809) | Model the chosen camera on drone_1 in sim | Backlog |

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

---

## Project 2 · HTX-R2 Starling Flight Bring-up (M2–M7)

[Linear project](https://linear.app/nearlab/project/htx-r2-starling-flight-bring-up-m2-m7-269b3d72d5ce)

**Status:** Backlog. **Start:** 2026-11-09. **Target:** not set. **Inventory:** 7 milestones, 28 issues, all Backlog.

Fly real Starling 2 Max drones on the new ground-control software under mocap, one safety-checked step at a time. The software changed on 7 Oct, so September's flight capabilities must be re-earned. Each step begins only after the previous one passes; every flight follows the preflight card. Mocap is expected back around 9 Nov. Simulation and flight without mocap are outside this project's scope.

### R1 · New mocap and network pipeline

**Linear target:** not set. **Progress:** 0%.

Bring upgraded OptiTrack online and rebuild the camera-to-drone network path. The laptop needs the mocap PC's 192.168.9.x subnet because multicast does not cross the router; the drone uses a separate routed subnet.

**Done when:** Motive calibration, ground plane, axes and rigid body are configured; full-rate streaming lasts 10 minutes without stalls; laptop/drone communicate both ways; PX4 receives correct-axis mocap; settings are documented.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-814](https://linear.app/nearlab/issue/NEAR-814) | Network: laptop on the mocap subnet (192.168.9.x) with the route to the drone subnet; drone gets its WiFi address; both ping each other | Backlog |
| [NEAR-815](https://linear.app/nearlab/issue/NEAR-815) | Set up the upgraded Motive: calibrate (wand, ground plane, axis convention) and create the Starling rigid body | Backlog |
| [NEAR-816](https://linear.app/nearlab/issue/NEAR-816) | Mocap stream end to end: laptop receives it at full rate for 10 min with no stalls, it reaches the drone’s PX4, and moving the drone by hand moves the position the same way on every axis | Backlog |
| [NEAR-817](https://linear.app/nearlab/issue/NEAR-817) | Record the new Motive version, IP and streaming settings in the lab docs and pictures | Backlog |

### M2 · Drone setup and hand-carry, propellers off

**Linear target:** not set. **Progress:** 0%.

Set up the drone and check end-to-end position with propellers off. **Done when:** drone ID matches controller target, only one watchdog runs, estimator fuses mocap, the panel tracks the hand-carried drone correctly, and kill switch is checked props-off.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-818](https://linear.app/nearlab/issue/NEAR-818) | Re-run the drone setup script, then reboot the drone (never restart the flight software service) | Backlog |
| [NEAR-819](https://linear.app/nearlab/issue/NEAR-819) | Confirm the drone ID matches the controller’s target | Backlog |
| [NEAR-820](https://linear.app/nearlab/issue/NEAR-820) | Confirm only one connection watchdog runs on the drone | Backlog |
| [NEAR-821](https://linear.app/nearlab/issue/NEAR-821) | Check the controller’s messages match the drone’s PX4 version | Backlog |
| [NEAR-822](https://linear.app/nearlab/issue/NEAR-822) | Hand-carry with props off: panel tracks the drone, estimator fuses mocap | Backlog |
| [NEAR-823](https://linear.app/nearlab/issue/NEAR-823) | Props-off kill switch test | Backlog |

### M3 · First flight on the new software

**Linear target:** not set. **Progress:** 0%.

Take off, hover and land under software control inside the fence. **Done when:** every command is acknowledged; landing settles and disarms; dummy-payload hover yields hover throttle and flight time.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-824](https://linear.app/nearlab/issue/NEAR-824) | Preflight card dry run with the new software | Backlog |
| [NEAR-825](https://linear.app/nearlab/issue/NEAR-825) | First flight: takeoff, hover, land | Backlog |
| [NEAR-826](https://linear.app/nearlab/issue/NEAR-826) | Landing test: settle on the ground, then disarm | Backlog |
| [NEAR-827](https://linear.app/nearlab/issue/NEAR-827) | Weigh the flight-ready drone and fit a dummy payload mass | Backlog |
| [NEAR-828](https://linear.app/nearlab/issue/NEAR-828) | Dummy-payload hover: hover throttle and flight time to 20 % battery | Backlog |

NEAR-824 description: walk through the preflight card on the ground, props off, QGC visible; fix steps that no longer match.

### M4 · Goal flights with the braking fence

**Linear target:** not set. **Progress:** 0%.

**Done when:** goal legs use the smooth speed-limited profile; wall braking distance is measured; gains change live; hold stops the drone where expected.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-829](https://linear.app/nearlab/issue/NEAR-829) | Goal legs on the speed-limited profile | Backlog |
| [NEAR-830](https://linear.app/nearlab/issue/NEAR-830) | Measure braking at the fence walls | Backlog |
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

### M6 · LED strips

**Linear target:** not set. **Progress:** 0%.

Optional hardware; starts when the strip arrives. **Done when:** LED service runs on the drone; green by default, red when collision avoidance acts; motor LEDs muted.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-836](https://linear.app/nearlab/issue/NEAR-836) | Fit the LED strip and start the LED service on the drone | Backlog |
| [NEAR-837](https://linear.app/nearlab/issue/NEAR-837) | Check green / red behaviour in flight | Backlog |

### M7 · Multi-drone

**Linear target:** not set. **Progress:** 0%.

Fly two, then three real drones under mocap. **Done when:** formations, random goals with collision avoidance and intruder-squeeze tests fly. The plan states this depends on the new Starlings arriving; issue status remains Backlog.

| Issue | Exact Linear title | Status |
|---|---|---|
| [NEAR-838](https://linear.app/nearlab/issue/NEAR-838) | Check the hardware order went out (Starlings, 2 stereo cameras, LED strip, 2.4 GHz radio) | Backlog |
| [NEAR-839](https://linear.app/nearlab/issue/NEAR-839) | Set up each new Starling (one at a time, setup guide) | Backlog |
| [NEAR-840](https://linear.app/nearlab/issue/NEAR-840) | Two drones: formation and random goals with collision avoidance | Backlog |
| [NEAR-841](https://linear.app/nearlab/issue/NEAR-841) | Three drones: intruder-squeeze test | Backlog |

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
| [NEAR-847](https://linear.app/nearlab/issue/NEAR-847) | Cameras on all three sim drones, added one at a time with a GPU check | Backlog |
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
| [NEAR-855](https://linear.app/nearlab/issue/NEAR-855) | Hand-carry the chosen camera under mocap with cuVSLAM on the laptop | Backlog |
| [NEAR-856](https://linear.app/nearlab/issue/NEAR-856) | Score cuVSLAM against Motive | Backlog |

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
| HTX-R1 | 12 | 33 | 5 | 1 | 27 |
| HTX-R2 | 7 | 28 | 0 | 0 | 28 |
| HTX-R3 | 6 | 17 | 1 | 0 | 16 |
| Total | 25 | 78 | 6 | 1 | 71 |
