# Linear update — 2026-11-03, teleop strip inside the cuVSLAM Foxglove window

Instructions for the Linear agent, in the **nearlab** workspace. Apply every step below. Delete nothing. Use the titles exactly as written. Every new issue is **Backlog**, unassigned, with no due date. All of this is simulation (Isaac Sim). The real drone is untouched. Nothing here has flown with the strip.

Evidence lives in the repo https://github.com/AI-DA-STC/AirStack-starling-max2: `docs/superpowers/specs/2026-11-03-foxglove-teleop-panel-design.md` and `docs/record/CHANGES.md`.

## Part 1 · HTX-R1 Swarm Sim Validation (Isaac)

Create this issue in milestone "S5 Finish basic sim flight checks":

**Title:** Teleop strip inside the cuVSLAM Foxglove window, with a chase view

**Description:**

> Sim-only. The real drone and the gamepad path are untouched.
>
> A keyboard strip is a panel in the cuVSLAM Foxglove window. It has the same keys and words as the Tk keyboard window. Beside it sit the cuVSLAM image and a chase view that follows the drone's cuVSLAM pose.
>
> How it is built: a panel extension of ours (`tools/teleop/foxglove/svg-teleop/`). `slam_up.sh` installs it. The layout is `tools/teleop/foxglove/teleop-cuvslam.json`. The strip publishes `/joy` through the Foxglove bridge. It sends keys only while it is clicked. Clicking anything else lets every key go. It shows FLYING only when its own keys come back from the bridge. It refuses to fly while the Tk window is sending. It needs `tools/sim.sh relay` running and `sudo ufw allow from 172.31.0.0/24`.
>
> Done when (target): the owner flies drone_1 from the strip in a video session. Clicking the image stops the drone within a second. Clicking the strip resumes. F flips to Room mode and back. The chase view stays behind the nose and turns with it. Nothing has flown with the strip yet.

Status: Backlog. Add a relation: the new issue **relates to NEAR-789** (keyboard teleop).

## Part 2 · Backlog issues

Create these three in project HTX-R1 Swarm Sim Validation (Isaac), without a milestone:

**Title:** Launch one safe_teleop and relay per drone for keyboard switching

> Sim-only. Today one `safe_teleop` and one relay serve drone_1. The strip's drone selector already re-targets its topics with `{name}`. Done when (target): each drone has its own `safe_teleop` and relay, and the selector switches the keyboard between them.

**Title:** Live cuVSLAM map panel in the teleop layout

> Sim-only. The layout reserves an empty Tab for it. cuVSLAM publishes no landmark points today, so a publisher is part of this issue. Done when (target): the Tab shows a live map next to the chase view.

**Title:** Draw the PX4 position in the chase view

> Sim-only. The chase view follows cuVSLAM's estimate, so drift is not visible. PX4 odometry and `cuvslam_odom` are separate frame trees with an alignment nobody has measured. Done when (target): a second marker shows the PX4 position, and the alignment is measured first.

Relate each of the three to the new issue in Part 1.

## Part 3 · Write the sync record

Write a Markdown file named `2026-11-03-linear-synced-2.md`. State only what Linear now holds:

- the new issues' NEAR ids, titles, milestone and status;
- the relations;
- anything not applied, and why;
- the totals per project for **all three** projects (HTX-R1, HTX-R2 and HTX-R3): total, Backlog, In Progress, Done, Canceled.
