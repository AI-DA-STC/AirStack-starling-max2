# Linear sync record — 2026-11-04 instructions

Workspace: nearlab. Verified after applying the instructions on 2026-11-05 (Asia/Singapore).

## Existing issues: current title, status and description

### <issue id="NEAR-789">NEAR-789</issue>

- Title: Set up one-drone gamepad teleop in the construction site (pad detected, sticks move the drone, release holds)
- Project: <project id="407ebe02-5313-4d58-b43c-424a8fc60e44">HTX-R1 Swarm Sim Validation (Isaac)</project>
- Status: In Progress (unchanged).
- Milestone: <projectmilestone id="da97eba0-285d-402a-94a6-e615c098803e">S5 Finish basic sim flight checks</projectmilestone>
- Description: empty (unchanged).

### <issue id="NEAR-910">NEAR-910</issue>

- Title: Retune the sim airframe’s yaw-rate gains so the heading settles after a turn
- Project: <project id="407ebe02-5313-4d58-b43c-424a8fc60e44">HTX-R1 Swarm Sim Validation (Isaac)</project>
- Status: Done (already held this status).
- Milestone: <projectmilestone id="da97eba0-285d-402a-94a6-e615c098803e">S5 Finish basic sim flight checks</projectmilestone>
- Description (unchanged):

Sim-only (never the real drone). Use `tools/sim.sh test yaw_step`. Done when (target): with the new gains as the airframe’s booted values, the yaw-step test passes: overshoot ≤ 3°, settle to ±2° ≤ 2 s, at most 1 swing back, swing-back ≤ 30 °/s, drift ≤ 0.15 m. The values go in as their own change-log entry, each line marked SIM-ONLY with the real value. Blocks <issue id="162338a8-d485-4ff9-b63e-82a28b90dfde" label="NEAR-789" href="https://linear.app/nearlab/issue/NEAR-789/set-up-one-drone-gamepad-teleop-in-the-construction-site-pad-detected" />.

### <issue id="NEAR-912">NEAR-912</issue>

- Title: Match the sim airframe’s MPC speed and acceleration limits to the real drone’s
- Project: <project id="407ebe02-5313-4d58-b43c-424a8fc60e44">HTX-R1 Swarm Sim Validation (Isaac)</project>
- Status: Backlog (unchanged).
- Milestone: <projectmilestone id="6ece493a-9ae2-4c4c-a51a-7c413a479c3d">S5d · Sim flies the real command route (px4_interface)</projectmilestone>
- Description (replaced now):

Sim-only. Today the sim has MPC_XY_VEL_MAX 20, MPC_ACC_HOR 6, MPC_ACC_HOR_MAX 1000, MPC_Z_VEL_MAX_UP 10, MPC_Z_VEL_MAX_DN 4 (the 2026-08-20 drone backup). Match them to the drone's parameter files, which the owner will supply. Until then the reference is starling_1_indoor_params.params: 3 / 3 / 3 / 2 / 0.6. Also lower cbf_sim.yaml’s 4.0 m/s cap. Re-run hover/step and crossing after (baselines ledger `#17–#22`). Its own change-log entry.

### <issue id="NEAR-914">NEAR-914</issue>

- Title: Read the drone’s MPC speed and acceleration limits in QGC and record which set it flies
- Project: <project id="2b491c29-37ea-4afa-9d78-eddfb6f3e1bd">HTX-R2 Starling Flight Bring-up (M2–M8)</project>
- Status: Canceled (already held this status).
- Milestone: <projectmilestone id="034af75c-fd11-45fc-bca0-24c4478df388">M2 · Drone setup and hand-carry, propellers off</projectmilestone>
- Description (unchanged):

Read MPC_XY_VEL_MAX, MPC_ACC_HOR, MPC_ACC_HOR_MAX, MPC_Z_VEL_MAX_UP, MPC_Z_VEL_MAX_DN. The 2026-08-20 backup says 20 / 6 / 1000 / 10 / 4; starling_1_indoor_params.params says 3 / 3 / 3 / 2 / 0.6. Read only. Settles iron rule 9’s wording and PREFLIGHT’s "20 m/s" line, and whether the commander’s 1.0 m/s cap is the only speed limit.

## New issues

All six were created in this sync, in <project id="407ebe02-5313-4d58-b43c-424a8fc60e44">HTX-R1 Swarm Sim Validation (Isaac)</project>. Each is unassigned and has no due date, verified after creation.

### Issue A — <issue id="NEAR-920">NEAR-920</issue>

- Title: Sim keyboard teleop flies in Drive mode (BODY), F switches to Room mode, with the forward-follows-the-nose test
- Status: In Progress.
- Milestone: <projectmilestone id="da97eba0-285d-402a-94a6-e615c098803e">S5 Finish basic sim flight checks</projectmilestone>
- Disposition: created now.
- Description:

Sim-only. The real drone and the gamepad path are untouched and stay room-fixed.

Drive mode means the up arrow follows the drone's nose, whichever way it points. CMU's teleop is room-fixed (WORLD), and it stays that way on the real drone.

How it is built: a small relay of ours sits between safe_teleop and the commander. It turns the keyboard's body-frame push into a room-frame command. A heading guard stops it if the heading is not known. The config is `teleop_single_ours.yaml`, which also turns the geofence and the teleop fence off for the construction-site sessions. That config is for the sim only. Start the relay with `tools/sim.sh keys` or `tools/sim.sh relay`.

Keys: Space is STOP. F switches between Drive mode (BODY) and Room mode (WORLD).

Done when (target): the owner watches a video session with `teleop_single_ours.yaml` where the up arrow still follows the nose after a 180° turn, and F flips to Room mode. Plus one PASS of `tools/sim.sh test teleop_frame`, with these gates:

- each push goes within 20° of the nose
- the drone moves at least 0.15 m
- it parks within 0.30 m
- the heading is reached within 10°
- one Room-mode push goes within 20° of +X

### Issue B — <issue id="NEAR-921">NEAR-921</issue>

- Title: Teleop strip inside the cuVSLAM Foxglove window, with a chase view
- Status: In Progress.
- Milestone: <projectmilestone id="da97eba0-285d-402a-94a6-e615c098803e">S5 Finish basic sim flight checks</projectmilestone>
- Disposition: created now.
- Description:

Sim-only. The real drone and the gamepad path are untouched.

A keyboard strip is a panel in the cuVSLAM Foxglove window. It has the same keys and words as the Tk keyboard window. Beside it sit the cuVSLAM image and a chase view that follows the drone's cuVSLAM pose.

How it is built: a panel extension of ours (`tools/teleop/foxglove/svg-teleop/`). `slam_up.sh` installs it and loads the layout `tools/teleop/foxglove/teleop-cuvslam.json` into Studio, so nobody imports it by hand. `slam_up.sh` also starts a grid that grows as the drone flies, because the world size changes between sessions. The strip publishes `/joy` through the Foxglove bridge. It sends keys only while it is clicked. Clicking anything else lets every key go. It shows FLYING only when its own keys come back from the bridge. It refuses to fly while the Tk window is sending. It needs `tools/sim.sh relay` running and `sudo ufw allow from 172.31.0.0/24`.

Done when (target): the owner flies drone_1 from the strip in a video session. Clicking the image stops the drone within a second. Clicking the strip resumes. F flips to Room mode and back. The chase view stays behind the nose and turns with it.

### <issue id="NEAR-922">NEAR-922</issue>

- Title: Launch one safe_teleop and relay per drone for keyboard switching
- Status: Backlog.
- Milestone: none.
- Disposition: created now.
- Description:

Sim-only. Today one `safe_teleop` and one relay serve drone_1. The strip's drone selector already re-targets its topics with `{name}`. Done when (target): each drone has its own `safe_teleop` and relay, and the selector switches the keyboard between them.

### <issue id="NEAR-923">NEAR-923</issue>

- Title: Live cuVSLAM map panel in the teleop layout
- Status: Backlog.
- Milestone: none.
- Disposition: created now.
- Description:

Sim-only. The layout reserves an empty Tab for it. cuVSLAM publishes no landmark points today, so a publisher is part of this issue. Done when (target): the Tab shows a live map next to the chase view.

### <issue id="NEAR-924">NEAR-924</issue>

- Title: Draw the PX4 position in the chase view
- Status: Backlog.
- Milestone: none.
- Disposition: created now.
- Description:

Sim-only. The chase view follows cuVSLAM's estimate, so drift is not visible. PX4 odometry and `cuvslam_odom` are separate frame trees with an alignment nobody has measured. Done when (target): a second marker shows the PX4 position, and the alignment is measured first.

### <issue id="NEAR-925">NEAR-925</issue>

- Title: Find why the cuVSLAM image freezes briefly at takeoff in the teleop layout
- Status: Backlog.
- Milestone: none.
- Disposition: created now.
- Description:

Sim-only. The owner saw the cuVSLAM image in Foxglove freeze for a moment during some takeoffs (2026-11-04). The length was not measured. Seen in the same session: load average 53, and a Foxglove bridge parameter timeout. The cause is not proven. It is not known whether cuVSLAM itself lost images or only the view paused. Next step: log CPU load and the image rate through a takeoff. Done when (target): the cause is named from logged numbers, and either the freeze is fixed or it is shown not to affect cuVSLAM.

## Requested comments now held in Linear

### <issue id="NEAR-910">NEAR-910</issue> — already present; not posted again

<comment id="94d615ee-4b3e-4ce7-a1ac-6b11139f7850">Existing comment</comment>

Sim, 2026-11-02. Passed with these as booted gains (sim_yaw_run3, ledger `#31`): overshoot 1.65°, settle 0.03 s, 1 crossing, swing-back 11.8 °/s, drift 0.056 m. Flat world, one drone, scripted pulses. Record: docs/record/sim_yaw_run3_record.md.

The existing comment formats #31 as inline code; its visible wording matches the requested comment. It was retained once.

### <issue id="NEAR-914">NEAR-914</issue> — added now

<comment id="f6b434c6-5e24-4179-b267-8a217830b8e9">Added comment</comment>

Canceled by the owner, 2026-11-02: no QGC read needed. The owner will supply the drone's parameter files later, which answers the same question. Until then starling_1_indoor_params.params (3 / 3 / 3 / 2 / 0.6) is the reference, and PREFLIGHT keeps treating the commander's 1.0 m/s cap as the only speed limit.

The older cancellation comment remains unchanged; it is not the same wording as this requested update.

### Issue A — <issue id="NEAR-920">NEAR-920</issue> — added now

<comment id="7d2cf295-8370-47b6-b560-a1997b9a43d9">Added comment</comment>

Sim, 2026-11-03. The test half passed: sim_teleop_frame_run1, PASS. Worst direction error 0.9° (gate 20°). Each push moved 1.12–1.20 m (gate at least 0.15 m). The drone stayed within 0.17 m after release (gate 0.30 m). The heading was within 3.5° (gate 10°). Flat world, one drone, PX4's own sim estimate, with the stick topic driven by the test script, so the keyboard was not in this test. Record: docs/record/sim_teleop_frame_run1_record.md. The video session is still to do.

### Issue B — <issue id="NEAR-921">NEAR-921</issue> — added now

<comment id="b06d1504-df85-40b1-b1b0-068dc92f7a32">Added comment</comment>

Sim, 2026-11-04. First keyboard flights from the strip, in the construction site. The owner reports that the drone flies and turns, the chase view sits behind the drone, F flips to Room mode and back, and holding the up arrow while tapping A works. This is the owner's report with no video, so it does not count as a result yet. Still unconfirmed: clicking the image stops the drone, and the auto-growing grid and automatic layout loading have not been seen working in a live session. Change log: docs/record/CHANGES.md, CHG-0040 to CHG-0055.

### <issue id="NEAR-789">NEAR-789</issue> — added now

<comment id="f04b0ae7-768f-4306-9e90-1465e8929bba">Added comment</comment>

Sim, 2026-11-04. Hand-flying is now from the keyboard: the Tk window or the strip in the cuVSLAM Foxglove window, both in Drive mode by default. The yaw retune no longer blocks this (<issue id="8e6ebcad-cb12-4bf5-b6c2-4ab663dd12cf" label="NEAR-910" href="https://linear.app/nearlab/issue/NEAR-910/retune-the-sim-airframes-yaw-rate-gains-so-the-heading-settles-after-a" />). The owner has flown the strip in the construction site, without video. Still needed: a recorded session the owner has watched. The gamepad itself is not part of this work.

Linear converted the issue identifier in this comment to an issue mention; the visible wording is unchanged.

### <issue id="NEAR-874">NEAR-874</issue> — added now

<comment id="b4825860-3575-4ee1-86f4-157eb97077d6">Added comment</comment>

The NUS velocity contract stays room-frame (WORLD). The sim keyboard's Drive mode is a relay in tools/teleop only and does not touch that path.

Its status remains Backlog and its description remains: Written once, shared with NUS, used by S5e and M8.

## Current issue relations

These are all structured relations returned for the issues covered by the instructions after the sync. Every listed relation is `related`, not blocking. Inbound/outbound records which side stores the relation; related relations are mutual.

| Issue | Outbound related issues | Inbound related issues |
| --- | --- | --- |
| <issue id="NEAR-789">NEAR-789</issue> | <issue id="NEAR-910">NEAR-910</issue> | <issue id="NEAR-913">NEAR-913</issue>, <issue id="NEAR-920">NEAR-920</issue>, <issue id="NEAR-921">NEAR-921</issue> |
| <issue id="NEAR-874">NEAR-874</issue> | None | None |
| <issue id="NEAR-910">NEAR-910</issue> | None | <issue id="NEAR-789">NEAR-789</issue> |
| <issue id="NEAR-912">NEAR-912</issue> | None | None |
| <issue id="NEAR-914">NEAR-914</issue> | None | None |
| <issue id="NEAR-920">NEAR-920</issue> | <issue id="NEAR-789">NEAR-789</issue> | None |
| <issue id="NEAR-921">NEAR-921</issue> | <issue id="NEAR-789">NEAR-789</issue> | <issue id="NEAR-922">NEAR-922</issue>, <issue id="NEAR-923">NEAR-923</issue>, <issue id="NEAR-924">NEAR-924</issue>, <issue id="NEAR-925">NEAR-925</issue> |
| <issue id="NEAR-922">NEAR-922</issue> | <issue id="NEAR-921">NEAR-921</issue> | None |
| <issue id="NEAR-923">NEAR-923</issue> | <issue id="NEAR-921">NEAR-921</issue> | None |
| <issue id="NEAR-924">NEAR-924</issue> | <issue id="NEAR-921">NEAR-921</issue> | None |
| <issue id="NEAR-925">NEAR-925</issue> | <issue id="NEAR-921">NEAR-921</issue>, <issue id="NEAR-790">NEAR-790</issue> | None |
| <issue id="NEAR-790">NEAR-790</issue> | None | <issue id="NEAR-925">NEAR-925</issue> |

No relation between <issue id="NEAR-912">NEAR-912</issue> and <issue id="NEAR-914">NEAR-914</issue> existed before the sync, and none exists after it. No removal was needed. The old “Blocks” sentence in <issue id="NEAR-910">NEAR-910</issue>'s description was preserved as instructed; it is not a structured blocking relation.

## Not applied and why

No requested change remains unapplied. Already-satisfied steps were not repeated: the Done and Canceled statuses, the existing booted-gains PASS comment, the unchanged statuses, and the absence of the relation requested for removal. No issue or comment was deleted. Five requested comments were added, one was already present, and six issues were created.

## Project totals after sync

All project issues, including archived non-trashed issues. Counts grouped by exact status name. No additional status categories were returned.

| Project | Total | Backlog | In Progress | Done | Canceled |
| --- | ---: | ---: | ---: | ---: | ---: |
| <project id="407ebe02-5313-4d58-b43c-424a8fc60e44">HTX-R1 Swarm Sim Validation (Isaac)</project> | 66 | 53 | 3 | 9 | 1 |
| <project id="2b491c29-37ea-4afa-9d78-eddfb6f3e1bd">HTX-R2 Starling Flight Bring-up (M2–M8)</project> | 35 | 34 | 0 | 0 | 1 |
| <project id="70bca613-da01-4b0b-9985-5368d80782c4">HTX-R3 Multi-Drone Localisation (VO + UWB)</project> | 17 | 16 | 0 | 1 | 0 |
