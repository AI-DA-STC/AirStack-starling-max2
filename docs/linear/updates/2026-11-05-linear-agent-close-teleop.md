# Linear update — 2026-11-05, close the keyboard teleop issues

Instructions for the Linear agent, in the **nearlab** workspace. Apply every step below. Delete nothing. Use titles and comments exactly as written. All of this is simulation (Isaac Sim). The real drone is untouched and no real-drone flight is claimed.

Evidence lives in the repo https://github.com/AI-DA-STC/AirStack-starling-max2. The paths below are relative to it.

## Part 1 · NEAR-789: it is keyboard teleop

Change the title of NEAR-789 from:

"Set up one-drone gamepad teleop in the construction site (pad detected, sticks move the drone, release holds)"

to:

**Set up one-drone keyboard teleop in the construction site (keys move the drone, release holds)**

Add this comment, then set the status to **Done**:

> Closed by the owner, 2026-11-05. This issue was always keyboard teleop, so the title now says keyboard. The gamepad is not part of it. The owner flew drone_1 from the keyboard in the construction site (sim) and accepts this without a video. The work is in NEAR-920 and NEAR-921. The recorded and scored hand flight stays open as NEAR-790.

## Part 2 · NEAR-920: Drive mode

Add this comment, then set the status to **Done**:

> Closed by the owner, 2026-11-05. Test: VERDICT PASS, LEDGER #32, docs/record/sim_teleop_frame_run1_record.md. The owner flew Drive mode in the construction site (sim) and accepts it without the video session named in the Done-when target.

## Part 3 · NEAR-921: teleop strip

Add this comment, then set the status to **Done**:

> Closed by the owner, 2026-11-05. The owner confirms that the strip flies drone_1 in the construction site (sim), that clicking the image stops the drone, and that the auto-growing grid and the automatic layout loading work. The owner accepts this without the video session named in the Done-when target. This replaces the "still unconfirmed" list in the 2026-11-04 comment.

## Part 4 · NEAR-860: record what exists

**NEAR-860 "Record the stereo camera images so a flight can be replayed through cuVSLAM".** Set the status to **In Progress**, and add this comment:

> Sim, 2026-11-05. Recording and offline replay are built (commit 1790264, `localisation/scripts/replay_bag.sh`, self-test `localisation/scripts/replay_selftest.sh`). Three flights from 2026-10-30 were replayed with 0 frames lost. Replay against the live path, RMSE: 0.19 m (sim_site_hand1), 0.29 m (sim_site_hand2), 60 m (sim_site_hand3). The 60 m is not explained and no record has been written, so this stays open.

## Part 5 · Milestone "S5 Finish basic sim flight checks"

In the milestone's description, change "prepare gamepad flying for S5b mapping" to "prepare keyboard flying for S5b mapping". If that wording is not in Linear, change nothing and say so in the sync record. Leave its "Done when" text as it is. Do not change the milestone HTX-R2 "M5 · Gamepad flying on the real drone" or any of its issues.

## Part 6 · Write the sync record

Write a Markdown file named `2026-11-05-linear-synced.md`. State only what Linear now holds:

- the title and status of NEAR-789, NEAR-790, NEAR-860, NEAR-920 and NEAR-921;
- each comment added here;
- the S5 milestone description and progress;
- anything not applied, and why;
- the totals per project for **all three** projects (HTX-R1, HTX-R2 and HTX-R3): total, Backlog, In Progress, Done, Canceled.
