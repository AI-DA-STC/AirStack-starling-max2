# Linear sync record — 2026-11-05

Workspace: NEAR Lab (`nearlab`). Verified against Linear after the updates. The recorded work concerns simulation (Isaac Sim); no real-drone flight is claimed.

## Issue titles and statuses

| Issue | Title | Status |
| --- | --- | --- |
| <issue id="NEAR-789" /> | Set up one-drone keyboard teleop in the construction site (keys move the drone, release holds) | Done |
| <issue id="NEAR-790" /> | Hand-fly drone_1 with cuVSLAM running, record and score the flight | Backlog |
| <issue id="NEAR-860" /> | Record the stereo camera images so a flight can be replayed through cuVSLAM | In Progress |
| <issue id="NEAR-920" /> | Sim keyboard teleop flies in Drive mode (BODY), F switches to Room mode, with the forward-follows-the-nose test | Done |
| <issue id="NEAR-921" /> | Teleop strip inside the cuVSLAM Foxglove window, with a chase view | Done |

## Comments added

### <issue id="NEAR-789" />

<comment id="db269917-3a1d-4b8c-acef-1275f69dc4a4">Added comment</comment>

> Closed by the owner, 2026-11-05. This issue was always keyboard teleop, so the title now says keyboard. The gamepad is not part of it. The owner flew drone_1 from the keyboard in the construction site (sim) and accepts this without a video. The work is in <issue id="b3da3200-b88b-4662-8e15-a46a74031a93" label="NEAR-920" href="https://linear.app/nearlab/issue/NEAR-920/sim-keyboard-teleop-flies-in-drive-mode-body-f-switches-to-room-mode" /> and <issue id="98401008-8bd6-4669-8804-9ff15f2b218e" label="NEAR-921" href="https://linear.app/nearlab/issue/NEAR-921/teleop-strip-inside-the-cuvslam-foxglove-window-with-a-chase-view" />. The recorded and scored hand flight stays open as <issue id="5817d4a0-7297-4a39-b7c1-75054c11a93d" label="NEAR-790" href="https://linear.app/nearlab/issue/NEAR-790/hand-fly-drone-1-with-cuvslam-running-record-and-score-the-flight" />.

### <issue id="NEAR-920" />

<comment id="f69c66a1-5a03-4023-a645-8b2d28065e0f">Added comment</comment>

> Closed by the owner, 2026-11-05. Test: VERDICT PASS, LEDGER `#32`, docs/record/sim_teleop_frame_run1_record.md. The owner flew Drive mode in the construction site (sim) and accepts it without the video session named in the Done-when target.

### <issue id="NEAR-921" />

<comment id="c6e072f5-2541-4eb4-b5f4-dca0818dd066">Added comment</comment>

> Closed by the owner, 2026-11-05. The owner confirms that the strip flies drone_1 in the construction site (sim), that clicking the image stops the drone, and that the auto-growing grid and the automatic layout loading work. The owner accepts this without the video session named in the Done-when target. This replaces the "still unconfirmed" list in the 2026-11-04 comment.

### <issue id="NEAR-860" />

<comment id="63cb0460-69da-47c2-9067-6a5033b58b56">Added comment</comment>

> Sim, 2026-11-05. Recording and offline replay are built (commit 1790264, `localisation/scripts/replay_bag.sh`, self-test `localisation/scripts/replay_selftest.sh`). Three flights from 2026-10-30 were replayed with 0 frames lost. Replay against the live path, RMSE: 0.19 m (sim_site_hand1), 0.29 m (sim_site_hand2), 60 m (sim_site_hand3). The 60 m is not explained and no record has been written, so this stays open.

## S5 milestone

<projectmilestone id="da97eba0-285d-402a-94a6-e615c098803e" /> in <project id="407ebe02-5313-4d58-b43c-424a8fc60e44" />.

Progress: **81%**.

Description, unchanged:

Re-run the core flight tests on the updated Starling sim model, and get one-drone gamepad flying working in the construction site. Hand-flying is how S5b will build its map, so this milestone prepares it.

**Done when:**

- Hover and 1 m steps are re-run and recorded.
- The three-drone crossing with collision avoidance is re-run and recorded.
- Live gain tuning from the panel is tried in sim.
- drone_1 is hand-flown by gamepad in the construction site with cuVSLAM running, and the flight is scored.

## Unapplied items and preservation

- The S5 replacement was not applied: the exact phrase "prepare gamepad flying for S5b mapping" is absent from the milestone description. As instructed, no alternative wording was changed; its entire description, including "Done when", remains unchanged.
- The wording of the four comments was added as requested. In the <issue id="NEAR-920" /> comment, `#32` is formatted as inline code because plain or escaped `#32` was automatically converted into an unrelated pull-request link. The ledger reference now remains literal `#32`.
- <issue id="NEAR-790" /> was read for this record and not changed.
- <project id="2b491c29-37ea-4afa-9d78-eddfb6f3e1bd" /> milestone "M5 · Gamepad flying on the real drone" and all its issues were not changed. No changes were made to that project or to <project id="70bca613-da01-4b0b-9985-5368d80782c4" />.
- No issues, comments, milestones, or projects were deleted. Existing comments were preserved. Each of the four new comments was added once; existing comments were checked first.

## All-project issue totals

Fresh counts after the updates, including archived non-trashed issues and all sub-issues. Counts are grouped by exact status name. No other statuses were returned.

| Project | Total | Backlog | In Progress | Done | Canceled |
| --- | ---: | ---: | ---: | ---: | ---: |
| <project id="407ebe02-5313-4d58-b43c-424a8fc60e44">HTX-R1</project> | 66 | 52 | 1 | 12 | 1 |
| <project id="2b491c29-37ea-4afa-9d78-eddfb6f3e1bd">HTX-R2</project> | 35 | 34 | 0 | 0 | 1 |
| <project id="70bca613-da01-4b0b-9985-5368d80782c4">HTX-R3</project> | 17 | 16 | 0 | 1 | 0 |
