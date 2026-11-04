# Linear update — 2026-11-04, close the sim yaw retune, teleop strip, first keyboard flights

Instructions for the Linear agent, in the **nearlab** workspace. Apply every step below. Delete nothing. Use titles and comments exactly as written, including any curly apostrophe ’. All of this is simulation (Isaac Sim). The real drone is untouched and no real-drone flight is claimed.

This file replaces three earlier instruction files: `2026-11-02-linear-agent-close-yaw.md`, `2026-11-03-linear-agent-teleop-frame.md` and `2026-11-03-linear-agent-foxglove-teleop.md`. Some of them may already have been applied. **Check Linear before each step.** If a step is already in place, do not repeat it. Do not post a comment twice and do not create a second issue with the same title. If an issue already exists under a title below, update it to match this file.

Every new issue is unassigned with no due date. Its status is the one stated here.

Evidence lives in the repo https://github.com/AI-DA-STC/AirStack-starling-max2. The paths below are relative to it.

## Part 1 · HTX-R1: close the sim yaw retune

**NEAR-910 "Retune the sim airframe’s yaw-rate gains so the heading settles after a turn".** Add this comment, then set the status to **Done**:

> Sim, 2026-11-02. Passed with these as booted gains (sim_yaw_run3, ledger #31): overshoot 1.65°, settle 0.03 s, 1 crossing, swing-back 11.8 °/s, drift 0.056 m. Flat world, one drone, scripted pulses. Record: docs/record/sim_yaw_run3_record.md.

**NEAR-912 "Match the sim airframe’s MPC speed and acceleration limits to the real drone’s".** Keep the title and status. Replace the description with:

> Sim-only. Today the sim has MPC_XY_VEL_MAX 20, MPC_ACC_HOR 6, MPC_ACC_HOR_MAX 1000, MPC_Z_VEL_MAX_UP 10, MPC_Z_VEL_MAX_DN 4 (the 2026-08-20 drone backup). Match them to the drone's parameter files, which the owner will supply. Until then the reference is starling_1_indoor_params.params: 3 / 3 / 3 / 2 / 0.6. Also lower cbf_sim.yaml’s 4.0 m/s cap. Re-run hover/step and crossing after (baselines ledger `#17–#22`). Its own change-log entry.

Remove any relation from NEAR-912 to NEAR-914.

## Part 2 · HTX-R2: cancel the QGC read

**NEAR-914 "Read the drone’s MPC speed and acceleration limits in QGC and record which set it flies".** Set the status to **Canceled**, and add this comment:

> Canceled by the owner, 2026-11-02: no QGC read needed. The owner will supply the drone's parameter files later, which answers the same question. Until then starling_1_indoor_params.params (3 / 3 / 3 / 2 / 0.6) is the reference, and PREFLIGHT keeps treating the commander's 1.0 m/s cap as the only speed limit.

## Part 3 · HTX-R1: two teleop issues in milestone "S5 Finish basic sim flight checks"

Both issues are **In Progress**. Both **relate to NEAR-789**.

### Issue A

**Title:** Sim keyboard teleop flies in Drive mode (BODY), F switches to Room mode, with the forward-follows-the-nose test

**Description:**

> Sim-only. The real drone and the gamepad path are untouched and stay room-fixed.
>
> Drive mode means the up arrow follows the drone's nose, whichever way it points. CMU's teleop is room-fixed (WORLD), and it stays that way on the real drone.
>
> How it is built: a small relay of ours sits between safe_teleop and the commander. It turns the keyboard's body-frame push into a room-frame command. A heading guard stops it if the heading is not known. The config is `teleop_single_ours.yaml`, which also turns the geofence and the teleop fence off for the construction-site sessions. That config is for the sim only. Start the relay with `tools/sim.sh keys` or `tools/sim.sh relay`.
>
> Keys: Space is STOP. F switches between Drive mode (BODY) and Room mode (WORLD).
>
> Done when (target): the owner watches a video session with `teleop_single_ours.yaml` where the up arrow still follows the nose after a 180° turn, and F flips to Room mode. Plus one PASS of `tools/sim.sh test teleop_frame`, with these gates:
> - each push goes within 20° of the nose
> - the drone moves at least 0.15 m
> - it parks within 0.30 m
> - the heading is reached within 10°
> - one Room-mode push goes within 20° of +X

Add this comment:

> Sim, 2026-11-03. The test half passed: sim_teleop_frame_run1, PASS. Worst direction error 0.9° (gate 20°). Each push moved 1.12–1.20 m (gate at least 0.15 m). The drone stayed within 0.17 m after release (gate 0.30 m). The heading was within 3.5° (gate 10°). Flat world, one drone, PX4's own sim estimate, with the stick topic driven by the test script, so the keyboard was not in this test. Record: docs/record/sim_teleop_frame_run1_record.md. The video session is still to do.

### Issue B

**Title:** Teleop strip inside the cuVSLAM Foxglove window, with a chase view

**Description:**

> Sim-only. The real drone and the gamepad path are untouched.
>
> A keyboard strip is a panel in the cuVSLAM Foxglove window. It has the same keys and words as the Tk keyboard window. Beside it sit the cuVSLAM image and a chase view that follows the drone's cuVSLAM pose.
>
> How it is built: a panel extension of ours (`tools/teleop/foxglove/svg-teleop/`). `slam_up.sh` installs it and loads the layout `tools/teleop/foxglove/teleop-cuvslam.json` into Studio, so nobody imports it by hand. `slam_up.sh` also starts a grid that grows as the drone flies, because the world size changes between sessions. The strip publishes `/joy` through the Foxglove bridge. It sends keys only while it is clicked. Clicking anything else lets every key go. It shows FLYING only when its own keys come back from the bridge. It refuses to fly while the Tk window is sending. It needs `tools/sim.sh relay` running and `sudo ufw allow from 172.31.0.0/24`.
>
> Done when (target): the owner flies drone_1 from the strip in a video session. Clicking the image stops the drone within a second. Clicking the strip resumes. F flips to Room mode and back. The chase view stays behind the nose and turns with it.

Add this comment:

> Sim, 2026-11-04. First keyboard flights from the strip, in the construction site. The owner reports that the drone flies and turns, the chase view sits behind the drone, F flips to Room mode and back, and holding the up arrow while tapping A works. This is the owner's report with no video, so it does not count as a result yet. Still unconfirmed: clicking the image stops the drone, and the auto-growing grid and automatic layout loading have not been seen working in a live session. Change log: docs/record/CHANGES.md, CHG-0040 to CHG-0055.

## Part 4 · HTX-R1: comment on NEAR-789

**NEAR-789 "Set up one-drone gamepad teleop in the construction site (pad detected, sticks move the drone, release holds)".** Leave it **In Progress**. Add this comment:

> Sim, 2026-11-04. Hand-flying is now from the keyboard: the Tk window or the strip in the cuVSLAM Foxglove window, both in Drive mode by default. The yaw retune no longer blocks this (NEAR-910). The owner has flown the strip in the construction site, without video. Still needed: a recorded session the owner has watched. The gamepad itself is not part of this work.

## Part 5 · HTX-R1: comment on NEAR-874

**NEAR-874 "Write the velocity contract with NUS and CMU (frame, units, limits, rate, timeout)".** Leave the status unchanged. Add this comment:

> The NUS velocity contract stays room-frame (WORLD). The sim keyboard's Drive mode is a relay in tools/teleop only and does not touch that path.

## Part 6 · HTX-R1: new Backlog issues

Create these four in project HTX-R1 Swarm Sim Validation (Isaac), with no milestone and status **Backlog**. Relate each one to Issue B.

**Title:** Launch one safe_teleop and relay per drone for keyboard switching

> Sim-only. Today one `safe_teleop` and one relay serve drone_1. The strip's drone selector already re-targets its topics with `{name}`. Done when (target): each drone has its own `safe_teleop` and relay, and the selector switches the keyboard between them.

**Title:** Live cuVSLAM map panel in the teleop layout

> Sim-only. The layout reserves an empty Tab for it. cuVSLAM publishes no landmark points today, so a publisher is part of this issue. Done when (target): the Tab shows a live map next to the chase view.

**Title:** Draw the PX4 position in the chase view

> Sim-only. The chase view follows cuVSLAM's estimate, so drift is not visible. PX4 odometry and `cuvslam_odom` are separate frame trees with an alignment nobody has measured. Done when (target): a second marker shows the PX4 position, and the alignment is measured first.

**Title:** Find why the cuVSLAM image freezes briefly at takeoff in the teleop layout

> Sim-only. The owner saw the cuVSLAM image in Foxglove freeze for a moment during some takeoffs (2026-11-04). The length was not measured. Seen in the same session: load average 53, and a Foxglove bridge parameter timeout. The cause is not proven. It is not known whether cuVSLAM itself lost images or only the view paused. Next step: log CPU load and the image rate through a takeoff. Done when (target): the cause is named from logged numbers, and either the freeze is fixed or it is shown not to affect cuVSLAM.

Also relate this last issue to NEAR-790.

## Part 7 · Write the sync record

Write a Markdown file named `2026-11-04-linear-synced.md`. State only what Linear now holds:

- the status, title and description of NEAR-789, NEAR-910, NEAR-912 and NEAR-914;
- each new issue's NEAR id, title, milestone and status, and whether it was created now or already existed;
- each comment added here on NEAR-789, NEAR-874, NEAR-910, NEAR-914, Issue A and Issue B, and whether it was added now or already present;
- the relations on all of these issues;
- anything not applied, and why;
- the totals per project for **all three** projects (HTX-R1, HTX-R2 and HTX-R3): total, Backlog, In Progress, Done, Canceled.
