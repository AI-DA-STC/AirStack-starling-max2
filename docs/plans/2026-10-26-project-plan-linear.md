# Starling swarm: project plan (Linear milestones and issues)

*NEAR Lab · prepared 26 Oct 2026 by Jeremy Chia · mirrors the three projects in Linear*

## How the work is split

Three Linear projects under the HTX swarm work. Each has milestones with target dates; each milestone has issues.
A milestone counts as finished in Linear when all its issues are Done.

| Project | Question it answers | Where it runs |
|---|---|---|
| **1 · Swarm Sim Validation (Isaac)** | Does a candidate flight pipeline (position source → PX4 → swarm controller with collision avoidance) work, and how does it fail? | Isaac Sim on the lab laptop |
| **2 · Starling Flight Bring-up (M2–M7)** | Does the same software fly the real Starling 2 Max safely under mocap, one drone and then several? | Mocap room |
| **3 · Multi-Drone Localisation (VO + UWB)** | Without mocap, which approach keeps every drone's position correct relative to the others? | Literature, sim, then real drones |

The sim project is ahead of the real drone on purpose. In sim a failure points at the idea or the software; on a real
drone it could also be the drone, the network or the mocap. The real-drone milestones repeat what the sim already showed.

### Words used below

| Term | Meaning |
|---|---|
| **Mocap** | OptiTrack motion capture in the lab: cameras that track markers on the drone to millimetres. Indoors, the drone gets its position from mocap, not GPS. |
| **PX4** | The flight controller software on the drone. Its estimator fuses sensors into the drone's position. |
| **Swarm controller / commander** | Our ground software that sends each drone its targets and keeps them apart (collision avoidance, CBF). |
| **cuVSLAM** | NVIDIA's camera-based position tracking. **VO** = from camera images alone; **VIO** = camera plus the drone's IMU. |
| **Sim mocap** | In simulation, the simulator's true drone position fed to PX4 the way mocap is on the real drone. |
| **UWB** | Ultra-wideband radios that measure the distance between drones. |
| **Teleop** | Flying a drone by hand with a gamepad through the swarm controller. |

---

## Project 1 · Swarm Sim Validation (Isaac)

**Summary.** Test a candidate swarm flight pipeline in Isaac Sim (position source → PX4 → swarm controller and collision
avoidance) to find out what works before deciding what goes onto the real Starlings.

**Why.** Sim makes research cheap: no batteries, no crashes, and a failure points at the idea, not the hardware. Mocap
is down until about 9 Nov. The sim must match the indoor drone (no GPS, mocap-style position) for its results to mean
anything. Handing a drone's position to cuVSLAM is the riskiest open question, so it is rehearsed here with a fallback
first. The HTX demo is mid-February and the strategy teams need a multi-drone test bed from December.

**Dates:** 19 Oct → 20 Dec 2026.

### S1 · Starling 2 Max sim drones · 21 Oct · ✅ done
Built the Starling 2 Max model in Isaac Sim from CMU's measured mass, inertia and motor data, using the real drone's
controller gains. Fixed a pitch wobble by softening the sim's rate control. Three drones flew random goals with collision
avoidance and landed cleanly.

| Issue | Status |
|---|---|
| Build and fly the Starling 2 Max sim model | Done |

### S2 · Stereo camera on a sim drone · 22 Oct · ✅ done
Added a simulated ZED stereo camera to drone_1 at 640×480. Found that the camera images can't reach the main robot
container because they sit on a separate network; worked around it with a dedicated container on the simulator's network.

| Issue | Status |
|---|---|
| Add a stereo camera to drone_1 and route its images | Done |

### S3 · Evaluate cuVSLAM in sim · 22 Oct · ✅ done
Ran cuVSLAM on drone_1 and compared it with PX4's own position estimate. The pipeline works end to end. In the empty
default world it jumped 5–10 m whenever the camera saw only sky and a flat grid.

| Issue | Status |
|---|---|
| Run cuVSLAM on drone_1 and score it | Done |

### S4 · Construction-site environment · 23 Oct · ✅ done
Converted the lab's Unreal construction site into an Isaac Sim world, in a full version and a lighter 40 m version.
Tested step by step on the laptop: 3 drones plus a camera ran fine. With structures in view, cuVSLAM stayed within 8 cm
over a 162 m flight, with no jumps.

| Issue | Status |
|---|---|
| Convert the construction site into an Isaac Sim world | Done |
| Fly 3 drones with cuVSLAM in the construction site and score it | Done |

### S5 · Finish basic sim flight checks · 5 Nov · in progress
Re-run the core flight tests on the updated Starling sim model, and get one-drone gamepad flying working in the
construction site. Hand-flying is how S5b builds its map, so this milestone prepares it.

**Done when:** hover and 1 m steps are re-run and recorded; the three-drone crossing with collision avoidance is re-run
and recorded; live gain tuning from the panel is tried in sim; drone_1 is hand-flown by gamepad in the construction site
with cuVSLAM running, recorded with its camera images, and scored.

| Issue | Status |
|---|---|
| Re-run hover and 1 m step test on the updated sim drone | Backlog |
| Re-run three-drone crossing with collision avoidance and record it | Backlog |
| Try live gain tuning from the panel in sim | Backlog |
| Set up one-drone gamepad teleop in the construction site (pad detected, sticks move the drone, release holds) | In Progress |
| Record the stereo camera images so a flight can be replayed through cuVSLAM | Backlog |
| Hand-fly drone_1 with cuVSLAM running, record and score the flight | Backlog |

### S5b · Map the construction site with cuVSLAM · 12 Nov
Fly drone_1 around the site by gamepad with cuVSLAM in mapping mode, save the map, and check whether a drone can find its
position in that saved map later. If it can, every drone could share one coordinate frame without UWB.

**Done when:** a map is saved after a hand-flown loop; a fresh run localises in it from several starting points and
headings, with success rate and time recorded; the localised position agrees with the simulator's view of the drone.

| Issue | Status |
|---|---|
| Add a mapping mode to the cuVSLAM node (save the map at the end of a flight) | Backlog |
| Hand-fly a mapping loop around the site and save the map | Backlog |
| Localise in the saved map from 5+ starting points and record success rate and time | Backlog |
| Compare the localised position with the simulator's drone position | Backlog |

### S5c · Choose the camera for cuVSLAM · 12 Nov
Find out which camera cuVSLAM should use on the real Starling before anything is built or ordered around it. The mono
test uses the simulated ZED camera, so it shows whether one camera is enough in principle; whether the Starling's own
camera works is answered separately, first by research.

**Questions.** Does cuVSLAM work well enough with one camera (monocular), or does it need a stereo pair? A single camera
cannot measure distance on its own, so scale and drift are the risk. Can we use the Starling 2 Max's built-in cameras:
which cameras, what lens and resolution, where do they point, does cuVSLAM support that lens, and does the drone's own
visual odometry already use them? If neither works, the fallback is an added stereo camera (RealSense D435i class), at
the cost of weight and a Jetson.

**Done when:** mono vs stereo is compared on the same replayed flight, scored the same way; the built-in camera option is
answered yes or no with the reason; the choice is written down and shared before the hardware order.

| Issue | Status |
|---|---|
| Run cuVSLAM in monocular mode on a replayed flight and score it against stereo | Backlog |
| List the Starling 2 Max's built-in cameras and check whether cuVSLAM can use them | Backlog |
| Decide the camera (built-in mono / built-in stereo / added stereo) and write down why | Backlog |

### S6 · Sim mocap · 19 Nov
Make the sim drones get their position the way the real indoor drones do: the simulator's true position is fed to PX4 as
if it were mocap, with GPS off and the real drone's estimator settings.

**Done when:** three drones take off, fly random goals and land on sim mocap.

| Issue | Status |
|---|---|
| Publish the simulator's true drone positions | Backlog |
| Send them into PX4 as mocap-style position | Backlog |
| Sim setting that turns GPS off and uses the real drone's estimator values | Backlog |
| Fly three drones on sim mocap: takeoff, random goals, land | Backlog |

### S7 · drone_1 flies on cuVSLAM · 26 Nov
Hand drone_1's position over from sim mocap to cuVSLAM, with automatic fallback, and check the drone still holds and
flies where it should.

**Done when:** drone_1 switches to cuVSLAM and back automatically if tracking fails; the hand-flown hold, out-and-back,
spin, open-view and hard-stick tests pass; a scripted flight is scored against the simulator's true position.

| Issue | Status |
|---|---|
| Position source switch: sim mocap or cuVSLAM, with automatic fallback | Backlog |
| Hand-flown handover tests (hold, out-and-back, spin, open view, hard stick) | Backlog |
| Scripted flight on cuVSLAM, scored against true position | Backlog |

### S8 · Model the chosen camera and payload · 3 Dec
Make the sim drone match the real one: the camera chosen in S5c, its IMU feeding cuVSLAM, and the Jetson and camera
weight it will carry.

**Done when:** the chosen camera is modelled on drone_1 and feeds cuVSLAM; cuVSLAM uses camera + IMU, scored against
camera-only; the heavier model (300–360 g added) flies the hover, step and crossing tests.

| Issue | Status |
|---|---|
| Model the chosen camera on drone_1 in sim | Backlog |
| Feed drone_1's IMU into cuVSLAM (camera-only → camera + IMU) and compare the scores | Backlog |
| Add Jetson and camera weight to the Starling sim model | Backlog |
| Re-run hover, step and crossing tests on the heavier model | Backlog |

### S9 · Safe failover · 13 Dec
Make sure the swarm controller stays safe when a drone's position goes stale, drops out or switches source mid-flight.

**Done when:** stale and dropped positions are handled without unsafe moves; switching position source mid-flight moves
the drone less than 30 cm.

| Issue | Status |
|---|---|
| Controller handles stale or missing positions (tests first) | Backlog |
| Measure and reduce the jump when the position source switches | Backlog |

### S10 · Scale test · 20 Dec
Check the stack copes with a bigger swarm.

**Done when:** 6–10 sim drones run together without cameras; controller load and recording size are measured.

| Issue | Status |
|---|---|
| Run 6 then 10 headless sim drones | Backlog |
| Record controller load and recording size | Backlog |

---

## Project 2 · Starling Flight Bring-up (M2–M7)

**Summary.** Fly the real Starling 2 Max on the new ground-control software under mocap, one safety-checked step at a
time: hand-carry, first flight, goal flights, gamepad, then several drones.

**Why.** The lab switched to CMU's newer ground-control software on 7 Oct, so the flights proven in September have to be
re-earned on it. Each step only starts when the previous one passes, and every flight follows the preflight card. Mocap
returns around 9 Nov after the camera upgrade.

**Dates:** 9 Nov 2026 → 31 Jan 2027. M0–M1 (bring-up and sim rehearsal) are covered by Project 1.

### R0 · Earlier flights on the previous software · 3 Sep · ✅ done
First takeoff and landing under software control with position from mocap only (1 Sep), then autonomous waypoint
flights with a fence and automatic landing (3 Sep). Kept here as history: the move to the new software on 7 Oct
restarted the ladder.

| Issue | Status |
|---|---|
| First software takeoff and landing on mocap | Done |
| Autonomous waypoint flight | Done |

### M2 · Drone setup and hand-carry, propellers off · 15 Nov
Set the drone up for the new software and carry it by hand, propellers off, to check that position flows end to end
before anything spins.

**Done when:** mocap matches Motive after the camera upgrade; the drone's ID matches the controller's target; only one
connection watchdog runs; the drone's estimator fuses mocap; the hand-carried drone moves correctly in the panel's 3D
view; the kill switch is checked with props off.

| Issue | Status |
|---|---|
| Mocap back: check the laptop receiver against Motive after the camera upgrade | Backlog |
| Re-run the drone setup script, then reboot the drone (never restart the flight software service) | Backlog |
| Confirm the drone ID matches the controller's target | Backlog |
| Confirm only one connection watchdog runs on the drone | Backlog |
| Check the controller's messages match the drone's PX4 version | Backlog |
| Hand-carry with props off: panel tracks the drone, estimator fuses mocap | Backlog |
| Props-off kill switch test | Backlog |

### M3 · First flight on the new software · 22 Nov
Takeoff, hover and land under software control, inside the fence, with the safety rules re-verified.

**Done when:** takeoff → hover → land works with the fence holding; every command is acknowledged; the landing settles
and disarms cleanly; a hover with the dummy payload gives hover throttle and flight time.

| Issue | Status |
|---|---|
| Preflight card dry run with the new software | Backlog |
| First flight: takeoff, hover, land | Backlog |
| Landing test: settle on the ground, then disarm | Backlog |
| Weigh the flight-ready drone and fit a dummy payload mass | Backlog |
| Dummy-payload hover: hover throttle and flight time to 20 % battery | Backlog |

### M4 · Goal flights with the braking fence · 29 Nov
Fly commanded goals on the smooth, speed-limited profile and check the fence brakes the drone before the walls.

**Done when:** goal legs fly on the limited profile; wall braking distance is measured; gains are changed live from the
panel; a hold stops the drone where expected.

| Issue | Status |
|---|---|
| Goal legs on the speed-limited profile | Backlog |
| Measure braking at the fence walls | Backlog |
| Change gains live from the panel in flight | Backlog |
| Check where a hold stops the drone | Backlog |

### M5 · Gamepad flying on the real drone · 6 Dec
Fly the real drone by gamepad through the controller.

**Done when:** the yaw direction is correct (the sim cannot prove it); the gamepad fence holds; releasing the sticks
holds position; coast distance after release is measured.

| Issue | Status |
|---|---|
| Check the yaw stick turns the drone the right way, slowly and low | Backlog |
| Gamepad fence test | Backlog |
| Release-to-hold test and coast distance | Backlog |

### M6 · LED strips (optional hardware) · when the strip arrives (target Dec)
Show each drone's state on an LED strip.

**Done when:** the LED service runs on the drone; green by default, red when collision avoidance acts; the motor LEDs
are muted.

| Issue | Status |
|---|---|
| Fit the LED strip and start the LED service on the drone | Backlog |
| Check green / red behaviour in flight | Backlog |

### M7 · Multi-drone · 31 Jan
Fly two, then three real drones together under mocap.

**Done when:** formations, random goals with collision avoidance, and the intruder-squeeze test fly with real drones.
Blocked until the new Starlings arrive.

| Issue | Status |
|---|---|
| Check the hardware order went out (Starlings, 2 stereo cameras, LED strip, 2.4 GHz radio) | Backlog |
| Set up each new Starling (one at a time, setup guide) | Backlog |
| Two drones: formation and random goals with collision avoidance | Backlog |
| Three drones: intruder-squeeze test | Backlog |

---

## Project 3 · Multi-Drone Localisation (VO + UWB)

**Summary.** Find out which approach keeps every drone's position correct relative to the other drones without mocap, and
what each approach costs, before the hardware design is fixed.

**Why.** Mocap only exists in the lab. For the HTX venue each drone must know where it is on its own, and the swarm must
agree on one shared frame. Three families are compared: (A) collaborative SLAM, where drones share map pieces; (B) each
drone localises in one pre-built shared map (tested in Project 1, S5b); (C) each drone runs its own visual odometry and
UWB distances between drones keep the frames lined up. Heading is the known weak point of C.

**Dates:** 22 Oct 2026 → March 2027.

### L0 · Literature review · 22 Oct · ✅ done
Reviewed 13 methods (Omni-swarm, D²SLAM, Swarm-SLAM, Kimera-Multi, COVINS and others) for evidence of use on real drones.
Verdicts: collaborative SLAM is not ready for us now; a shared map is worth a one-day trial; own VO + UWB alignment is the
recommended baseline, but heading needs an extra source such as a second UWB tag per drone.

| Issue | Status |
|---|---|
| Literature review with validation evidence | Done |

### L1 · Team review pack · 3 Nov
Bring the evidence so far to the team review.

**Done when:** the review has the literature table, the flat-world vs construction-site cuVSLAM result, the effort log,
and a recommendation with open questions.

| Issue | Status |
|---|---|
| Results table: what was tested, what it showed | Backlog |
| Recommendation and open questions | Backlog |
| Update the effort log | Backlog |
| Slides for the review | Backlog |

### L2 · Three-drone dataset and UWB emulator · 13 Dec
Record the flights every approach will be compared on, and simulate the UWB distances between drones.

**Done when:** cameras run on all three sim drones; hover, formation, crossing and a 10–15 min figure-8 are recorded with
true positions; the UWB emulator produces distances with realistic noise, bias and blocked-line errors from the papers.

| Issue | Status |
|---|---|
| Cameras on all three sim drones, added one at a time with a GPU check | Backlog |
| Record hover, formation, crossing and long figure-8 with true positions | Backlog |
| UWB distance emulator between drones (noise, bias, blocked-line errors) | Backlog |
| Drift injector to test many drones without many cameras | Backlog |
| Run one public multi-drone dataset (MILUV) for a real-data result | Backlog |

### L3 · Own VO + UWB alignment · 3 Jan
Build the aligner that keeps every drone's frame lined up using UWB distances, and measure it.

**Done when:** relative position error per drone pair over time, heading error and time to converge are measured; one vs
two UWB tags per drone is compared.

| Issue | Status |
|---|---|
| Aligner: continuous frame alignment from positions and UWB distances | Backlog |
| Measure pair error, heading error and convergence time | Backlog |
| Compare one vs two UWB tags per drone | Backlog |

### L4 · First real-hardware number · 27 Feb
Carry the chosen camera by hand under mocap with cuVSLAM running, and compare against Motive.

**Done when:** cuVSLAM's path is scored against mocap for a hand-carried camera.

| Issue | Status |
|---|---|
| Hand-carry the chosen camera under mocap with cuVSLAM on the laptop | Backlog |
| Score cuVSLAM against Motive | Backlog |

### L5 · Scale to 10 sim drones · March
Check the alignment still holds with a bigger swarm.

**Done when:** UWB alignment runs on 10 sim drones; error and radio bandwidth are measured.

| Issue | Status |
|---|---|
| Run the aligner on 10 sim drones | Backlog |
| Measure error and UWB/WiFi bandwidth | Backlog |

---

*Totals: Project 1 has 12 milestones and 33 issues; Project 2 has 7 milestones and 27 issues; Project 3 has 6 milestones
and 17 issues. Results so far live in the repo under `localisation/results/`; the real-drone procedures in
`docs/RUNBOOK.md` and `docs/PREFLIGHT.md`.*
