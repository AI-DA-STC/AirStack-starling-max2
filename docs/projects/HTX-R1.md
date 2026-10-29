RECORD · SIM ONLY — every result on this page is Isaac Sim; nothing here has flown. Codes, titles and "Done when" are Linear's, verbatim.

# HTX-R1 Swarm Sim Validation (Isaac)

Question (Linear): Does the candidate position source → PX4 → swarm controller and collision-avoidance pipeline work, and how does it fail? · Where: Isaac Sim on the lab laptop · [Linear project](https://linear.app/nearlab/project/htx-r1-swarm-sim-validation-isaac-649103a747b1) · Linear snapshot: 2026-10-26 · Evidence: [LEDGER](../record/LEDGER.md)

### S1 Starling 2 Max sim drones — SIM ONLY (Isaac)
Linear (snapshot 2026-10-26): target 2026-10-21 · 100 % · last ledger row #13 (2026-10-21)
Done when (Linear): not stated in the snapshot — milestone at 100 %

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-782 | Build and fly the Starling 2 Max sim model | spawns ×3 (#1, 2026-10-19); 3 drones random goals, 3 clean landings (#13, 2026-10-21) | [#1, #9, #10, #13](../record/LEDGER.md); `videos/random_CBF_sim_edited.mp4` |

Open: none. Re-run: `tools/sim_terminals.sh` with `DRONE_USD=… PX4_VEHICLE_MODEL=pegasus_starling2max` (RUNBOOK §A).

### S2 Stereo camera on a sim drone — SIM ONLY (Isaac)
Linear (snapshot 2026-10-26): target 2026-10-22 · 100 % · last ledger row #15 (2026-10-22)
Done when (Linear): not stated in the snapshot — milestone at 100 %

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-783 | S2 Add a stereo camera to drone_1 and route its images | pipeline works end to end (sim_cam_run1, 2026-10-22) | [#15](../record/LEDGER.md) → [record](../../localisation/results/sim_cam_run1_record.md) |

### S3 Evaluate cuVSLAM in sim — SIM ONLY (Isaac)
Linear (snapshot 2026-10-26): target 2026-10-22 · 100 % · last ledger row #15 (2026-10-22)
Done when (Linear): not stated in the snapshot — milestone at 100 %

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-784 | S3 Run cuVSLAM on drone_1 and score it | APE RMSE 0.252 m, flat world, 480×300 — pipeline result, not accuracy (2026-10-22) | [#15](../record/LEDGER.md) → [record](../../localisation/results/sim_cam_run1_record.md) |

### S4 Construction-site environment — SIM ONLY (Isaac)
Linear (snapshot 2026-10-26): target 2026-10-23 · 100 % · last ledger row #16 (2026-10-22)
Done when (Linear): not stated in the snapshot — milestone at 100 %

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-785 | S4 Convert the construction site into an Isaac Sim world | world loads (`ENV_USD`, 40 m crop); VO 0.081 m RMSE / 162 m, no jumps (2026-10-22) | [#16](../record/LEDGER.md) → [record](../../localisation/results/sim_site_run1_record.md) |
| NEAR-859 | Fly 3 drones with cuVSLAM in the construction site and score it | 3 drones `random_goals`, 0.081 m RMSE over 162 m (sim_site_run1, 2026-10-22) | [#16](../record/LEDGER.md) → [record](../../localisation/results/sim_site_run1_record.md) |

S3/S4 result (sim only; reference = PX4 EKF2, not ground truth):

| | flat default world (`sim_cam_run2–4`) | construction site (`sim_site_run1`) |
|---|---|---|
| APE RMSE, SE(3)-aligned | 0.88–5.3 m, 2 jumps > 1 m per run (per sim_site_run1 record) | 0.081 m over 162 m, no jumps |

![flat world: VO jumps away from the reference](../../pictures/vo_flat_xy_cam_run3.png) ![construction site: VO stays on the reference](../../pictures/vo_site_xy_site_run1.png)
*Top-down x-y, PX4 (blue) vs cuVSLAM (orange); `localisation/scripts/score_run.sh <run> 1` → `score_vs_ulog.py`; ledger #15, #16. The flat-world picture is `sim_cam_run3` (no record file; #15 is `sim_cam_run1`, same world, same behaviour).*

### S5 Finish basic sim flight checks — SIM ONLY (Isaac)
Linear (snapshot 2026-10-26): 4 % · last ledger row #19 (2026-10-29)

**Done when** (Linear's target, verbatim; a target, not a result): hover and 1 m steps, three-drone collision-avoidance crossing and live gain tuning are tried and recorded; drone_1 is hand-flown in the construction site with cuVSLAM, camera recording and scoring.

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-786 | Re-run hover and 1 m step test on the updated sim drone | PASS ×2 — x 0.095 m / 2.47 s, 2026-10-29 | [#18, #19](../record/LEDGER.md) → [run3 record](../record/sim_hover_step_run3_record.md) |
| NEAR-787 | Re-run three-drone crossing with collision avoidance and record it | — | baseline [#4](../record/LEDGER.md): 1.02 m, old asset, no bag |
| NEAR-788 | Try live gain tuning from the panel in sim | — | — |
| NEAR-789 | Set up one-drone gamepad teleop in the construction site (pad detected, sticks move the drone, release holds) | — | — |
| NEAR-790 | Hand-fly drone_1 with cuVSLAM running, record and score the flight | — | — |
| NEAR-860 | Record the stereo camera images so a flight can be replayed through cuVSLAM | — | — |

NEAR-786 — results (sim only; gates 0.15 m / 3.0 s PX4 vehicle time / 0 re-entries / thrust 0.12–0.20 — [tools/README.md](../../tools/README.md#thresholds); set 2026-10-19 around the Iris reading, not a flight requirement)

| | gate | #3 (19 Oct, old asset, 0.6 m/s, wall time) | #17 (28 Oct, n=1) | #18 (28 Oct, n=3) | #19 (29 Oct, n=3) |
|---|---|---|---|---|---|
| hover thrust | 0.12–0.20 (real 0.165) | 0.155 | 0.153 | 0.153 | 0.153 |
| PX4 s per wall s | — | — | 1.336 (est., overlay scale) | 1.324 | 1.333 |
| x overshoot, m | < 0.15 | 0.002 | 0.054 | 0.085 | 0.095 |
| x settle, s | < 3.0 | 2.75 | 2.49 | 2.47 | 2.47 |
| z overshoot, m | < 0.15 | 0.001 | 0.001 | 0.033 | 0.020 |
| z settle, s | < 3.0 | 0.75 | 2.16 | 2.50 | 2.42 |
| landed, DISARMED ×3 | yes | — | yes | yes | yes |
| verdict | | superseded | driver FAIL ×3, re-analysed PASS; drone_1 ulog lost | PASS | PASS |

![x and z step responses, #17–#19 overlaid, PX4 vehicle time](../record/figures/s5_hover_step_overlay.png)
*`tools/make_figures.sh` → `tools/hover_step_plot.py --overlay sim_hover_step_run1 sim_hover_step_run2 sim_hover_step_run3 --time-scale sim_hover_step_run1=1.336`; ledger #17–#19 ([#17 record](../record/sim_hover_step_run1_record.md), [#18](../record/sim_hover_step_run2_record.md), [#19](../record/sim_hover_step_run3_record.md)).*

Open: nothing hand-flown yet — NEAR-789/790 count only with a video of the hand-flown flight the owner has watched (owner's rule, 2026-10-29); NEAR-787 at 2.0 / 4.0 m/s with a bag (`tools/sim_cbf_crossing_test.sh`, SCENARIOS §5). Re-run: `LEDGER=20 ISSUE=NEAR-786 tools/sim_hover_step_run.sh all <new_run>`.

### S5b · Map the construction site with cuVSLAM — SIM ONLY (Isaac)
Linear (snapshot 2026-10-26): 0 % · no ledger row yet

**Done when** (Linear's target, verbatim; a target, not a result): a map is saved; fresh runs localise from several starts/headings with success rate and time recorded; positions agree with simulator ground truth.

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-791 | Add a mapping mode to the cuVSLAM node | — | — |
| NEAR-792 | Hand-fly a mapping loop and save the map | — | — |
| NEAR-793 | Localise in the saved map from 5+ starting points | — | — |
| NEAR-794 | Compare the localised position with the simulator’s position | — | — |

### S5c · Choose the camera for cuVSLAM — DESK (decision)
Linear (snapshot 2026-10-26): 0 % · no ledger row yet

**Done when** (Linear's target, verbatim; a target, not a result): mono/stereo results are comparable, built-in camera suitability has a reasoned yes/no answer, and the decision is written and shared before ordering.

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-800 | Run cuVSLAM in monocular mode on a replayed flight and score it against stereo | — | — |
| NEAR-801 | List the Starling 2 Max’s built-in cameras and check whether cuVSLAM can use them | — | — |
| NEAR-802 | Decide the camera (built-in mono / built-in stereo / added stereo) and write down why | — | — |

### S6 Sim mocap — SIM ONLY (Isaac)
Linear (snapshot 2026-10-26): 0 % · no ledger row yet

**Done when** (Linear's target, verbatim; a target, not a result): three drones take off, fly random goals and land on sim mocap.

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-803 | Publish the simulator’s true drone positions | — | — |
| NEAR-804 | Send them into PX4 as mocap-style position | — | — |
| NEAR-805 | Sim setting that turns GPS off and uses the real drone’s estimator values | — | — |
| NEAR-806 | Fly three drones on sim mocap: takeoff, random goals, land | — | — |

Related: the laptop-side mocap bridge loopback, [#14](../record/LEDGER.md) (fake Motive, 49.998 Hz into the PX4 message — not sim mocap).

### S7 drone_1 flies on cuVSLAM — SIM ONLY (Isaac)
Linear (snapshot 2026-10-26): 0 % · no ledger row yet

**Done when** (Linear's target, verbatim; a target, not a result): source switching/fallback works; hand-flown hold, out-and-back, spin, open-view and hard-stick tests pass; a scripted flight is scored against true position.

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-795 | Position source switch: sim mocap or cuVSLAM, with automatic fallback | — | — |
| NEAR-796 | Hand-flown handover tests (hold, out-and-back, spin, open view, hard stick) | — | — |
| NEAR-797 | Scripted flight on cuVSLAM, scored against true position | — | — |

### S8 Model the chosen camera and payload — SIM ONLY (Isaac)
Linear (snapshot 2026-10-26): 0 % · no ledger row yet

**Done when** (Linear's target, verbatim; a target, not a result): the camera feeds cuVSLAM; camera+IMU is scored against camera-only; the model with 300–360 g added passes hover, step and crossing checks.

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-798 | Add Jetson and camera weight to the Starling sim model | — | — |
| NEAR-807 | Re-run hover, step and crossing tests on the heavier model | — | — |
| NEAR-808 | Feed drone_1’s IMU into cuVSLAM (camera-only → camera + IMU) and compare the scores | — | — |
| NEAR-809 | Model the chosen camera on drone_1 in sim | — | — |

### S9 Safe failover — SIM ONLY (Isaac)
Linear (snapshot 2026-10-26): 0 % · no ledger row yet

**Done when** (Linear's target, verbatim; a target, not a result): no unsafe movement follows stale/missing positions, and source switching moves the drone less than 30 cm.

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-810 | Controller handles stale or missing positions (tests first) | — | — |
| NEAR-811 | Measure and reduce the jump when the position source switches | — | — |

### S10 Scale test — SIM ONLY (Isaac)
Linear (snapshot 2026-10-26): 0 % · no ledger row yet

**Done when** (Linear's target, verbatim; a target, not a result): 6–10 simulated drones run without cameras; controller load and recording size are measured.

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-812 | Run 6 then 10 headless sim drones | — | — |
| NEAR-813 | Record controller load and recording size | — | — |

## Sim debt (ours; none of it gates a milestone)

| Item | Seen | Candidate fix (none tried) |
|---|---|---|
| Pegasus Stop ▶ Play leaks the stopped vehicles' physics callbacks | [#6](../record/LEDGER.md), 2026-10-20 | guard `PX4MavlinkBackend.update()` with `if not self._is_running: return`, or fix the callback removal by prefix |
| `mavros_node` segfault (exit −11) mid-flight, cause unknown (respawn masks it) | [#8, #11](../record/LEDGER.md) | set a file `core_pattern` on the host before a long sim session (apport eats cores today) |
| Isaac ROS 2 topics invisible to host-network containers (DDS does not cross the isaac docker network) | 2026-10-22 | isaac-sim on the host network, or keep `--network container:isaac-sim` (`localisation/docker/run.sh`) |
| No Isaac ground-truth publisher: every VO score is against EKF2, not the true pose | 2026-10-23 | one OmniGraph node behind an env flag in the launcher |
| Launcher edits in CMU's tree (`10b85b5` camera 640×480, `158204e` `ENV_USD`) | 2026-10-22 | `patches/0004`, `0005` (see `patches/`); re-apply on a fresh clone |
| `robot_interface_node` segfault on Ctrl-C of the interfaces launch (cosmetic) | dmesg, 2026-10-20 | report upstream, do not patch (node shared with the real path) |
