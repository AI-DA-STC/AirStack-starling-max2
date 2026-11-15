# Linear follow-up — 2026-11-02 (after the sim yaw diagnosis)

Instructions for the Linear agent, in the **nearlab** workspace. They follow `2026-11-02-linear-agent-instructions.md`, which you have already been given. If any step of that file was not applied, apply it first. Use titles exactly as written. Delete nothing. All results below are simulation (Isaac Sim); none flew a real drone.

## Part 1 · Add these comments (statuses unchanged)

**On NEAR-789**, as a correction to the earlier comment:

> Correction, sim, 2026-11-02. The main cause of the swing was a PX4 filter setting, not only the sim's weak turning force. The sim's PX4 v1.16 ran MC_YAW_TQ_CUTOFF at its 2 Hz default; the real drone has MC_YAW_CUTOFF 15 Hz (that the two are the same filter is inferred, not confirmed in PX4's source). At 15 Hz (CHG-0023) the ring is gone, and the sim now uses yaw-rate gains 0.25 / 0.2 (CHG-0024, sim-only). Keyboard flying in the construction site is still to do. Evidence: docs/record/sim_yaw_sweep5_record.md, docs/record/CHANGES.md.

**On "Retune the sim airframe’s yaw-rate gains so the heading settles after a turn":**

> Sim, 2026-11-02. Gains chosen: MC_YAWRATE_P 0.25, MC_YAWRATE_I 0.2, with MC_YAW_TQ_CUTOFF 15 (CHG-0023, CHG-0024). Set live in sim_yaw_sweep5: overshoot 1.3°, settle 0.03 s, 1 crossing, swing-back 12 °/s, drift 0.05 m. The first run with these as booted gains, sim_yaw_run2, was INCOMPLETE: its first pulse was lost before the commander had subscribed, a test-script bug fixed in CHG-0025. Not done until a booted run passes.

**On "Model rotor reaction torque and rotational drag in the sim Starling, then re-run the yaw-step test":**

> Sim, 2026-11-02. Lower priority: the filter fix (CHG-0023) removed most of the ring, so this is no longer needed for NEAR-789. Its purpose now is model realism only.

## Part 2 · Create in milestone "S5d · Sim flies the real command route (px4_interface)"

| Title | Description |
|---|---|
| Compare every PX4 parameter between the sim and the real drone | The airframe check covers only lines written in the airframe, so it missed the yaw filter. Known so far (sim / real): MC_YAWRATE_MAX 200 / 150, MPC_THR_MAX 1.0 / 0.6, MPC_THR_MIN 0.12 / 0.04, LNDMC_TRIG_TIME 1.0 / 0.5, COM_DISARM_LAND 2.0 / 0.5. Decide each one and log it. Backlog, unassigned, no due date. |

## Part 3 · Write the sync record

Write a Markdown file named `2026-11-02-linear-synced.md`, in the same format as `2026-10-30-linear-synced.md`: what was applied from both instruction files, each new issue's NEAR id, title, description, milestone and status, each comment added, the relations, anything not applied, and the totals per project. State only what Linear now holds.
