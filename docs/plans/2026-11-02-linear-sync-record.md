# Linear sync — 2026-11-02

Workspace: nearlab. Instructions: `2026-11-02-linear-agent-instructions.md` and `2026-11-02-linear-agent-followup.md`. Reported runs concern Isaac Sim; no real-drone flight is asserted by this sync. This record states the verified Linear contents, not independent validation of flight results.

## Applied

- The first instruction file’s six issues, original NEAR-789 comment and blocking relation already existed; reused without duplication.
- Created NEAR-916 and added three follow-up comments.
- Preserved existing statuses, including In Progress on NEAR-789 and NEAR-910.
- Corrected NEAR-912’s ledger reference to literal `#17–#22`, avoiding unrelated pull-request mentions.
- Deleted nothing. NEAR-913 priority remains No priority.

## Issues

All seven issues are unassigned and have no due date.

### [NEAR-910](https://linear.app/nearlab/issue/NEAR-910) — Retune the sim airframe’s yaw-rate gains so the heading settles after a turn

Project: HTX-R1 Swarm Sim Validation (Isaac)  
Milestone: S5 Finish basic sim flight checks  
Status: In Progress

Sim-only (never the real drone). Use `tools/sim.sh test yaw_step`. Done when (target): with the new gains as the airframe’s booted values, the yaw-step test passes: overshoot ≤ 3°, settle to ±2° ≤ 2 s, at most 1 swing back, swing-back ≤ 30 °/s, drift ≤ 0.15 m. The values go in as their own change-log entry, each line marked SIM-ONLY with the real value. Blocks [NEAR-789](https://linear.app/nearlab/issue/NEAR-789).

### [NEAR-911](https://linear.app/nearlab/issue/NEAR-911) — Check heading hold (MC_YAW_P) on the px4_interface route with the yaw-step test

Project: HTX-R1 Swarm Sim Validation (Isaac)  
Milestone: S5d · Sim flies the real command route (px4_interface)  
Status: Backlog

On the MAVROS route PX4 only gets "yaw rate 0", so MC_YAW_P has no effect (sim notes 2026-11-02). The px4_interface route sends an absolute heading, so heading hold matters there. Run the yaw-step test on that route and compare.

### [NEAR-912](https://linear.app/nearlab/issue/NEAR-912) — Match the sim airframe’s MPC speed and acceleration limits to the real drone’s

Project: HTX-R1 Swarm Sim Validation (Isaac)  
Milestone: S5d · Sim flies the real command route (px4_interface)  
Status: Backlog

Sim-only. Today the sim has MPC_XY_VEL_MAX 20, MPC_ACC_HOR 6, MPC_ACC_HOR_MAX 1000, MPC_Z_VEL_MAX_UP 10, MPC_Z_VEL_MAX_DN 4 (the 2026-08-20 drone backup); the indoor params file has 3 / 3 / 3 / 2 / 0.6. Waits for the QGC check in HTX-R2 M2. Also lower cbf_sim.yaml’s 4.0 m/s cap. Re-run hover/step and crossing after (baselines ledger `#17–#22`). Its own change-log entry.

### [NEAR-913](https://linear.app/nearlab/issue/NEAR-913) — Model rotor reaction torque and rotational drag in the sim Starling, then re-run the yaw-step test

Project: HTX-R1 Swarm Sim Validation (Isaac)  
Milestone: S5d · Sim flies the real command route (px4_interface)  
Status: Backlog  
Priority: No priority

Optional alternative to the gain retune: make the sim body turn like a real one. Pegasus models yaw torque only as rotor drag (k_m·ω²), with no torque from motors speeding up or slowing down and no drag on rotation. A model change, its own change-log entry. Decide after the retune.

### [NEAR-914](https://linear.app/nearlab/issue/NEAR-914) — Read the drone’s MPC speed and acceleration limits in QGC and record which set it flies

Project: HTX-R2 Starling Flight Bring-up (M2–M8)  
Milestone: M2 · Drone setup and hand-carry, propellers off  
Status: Backlog

Read MPC_XY_VEL_MAX, MPC_ACC_HOR, MPC_ACC_HOR_MAX, MPC_Z_VEL_MAX_UP, MPC_Z_VEL_MAX_DN. The 2026-08-20 backup says 20 / 6 / 1000 / 10 / 4; starling_1_indoor_params.params says 3 / 3 / 3 / 2 / 0.6. Read only. Settles iron rule 9’s wording and PREFLIGHT’s "20 m/s" line, and whether the commander’s 1.0 m/s cap is the only speed limit.

### [NEAR-915](https://linear.app/nearlab/issue/NEAR-915) — Yaw-step check on the real Starling: overshoot and settle after a yaw pulse, compared with the sim

Project: HTX-R2 Starling Flight Bring-up (M2–M8)  
Milestone: M5 · Gamepad flying on the real drone  
Status: Backlog

Low and slow, after [NEAR-833](https://linear.app/nearlab/issue/NEAR-833). Measures whether the real drone also rings after a turn. Tells whether CA_ROTOR_KM 0.05 (PX4’s default) or CMU’s measured 0.0136 matches the real Starling, and whether the sim-only yaw retune hides a real-drone tuning issue.

### [NEAR-916](https://linear.app/nearlab/issue/NEAR-916) — Compare every PX4 parameter between the sim and the real drone

Project: HTX-R1 Swarm Sim Validation (Isaac)  
Milestone: S5d · Sim flies the real command route (px4_interface)  
Status: Backlog

The airframe check covers only lines written in the airframe, so it missed the yaw filter. Known so far (sim / real): MC_YAWRATE_MAX 200 / 150, MPC_THR_MAX 1.0 / 0.6, MPC_THR_MIN 0.12 / 0.04, LNDMC_TRIG_TIME 1.0 / 0.5, COM_DISARM_LAND 2.0 / 0.5. Decide each one and log it. Backlog, unassigned, no due date.

## Stored comments

### NEAR-789 — [original diagnosis, already present](https://linear.app/nearlab/issue/NEAR-789/set-up-one-drone-gamepad-teleop-in-the-construction-site-pad-detected#comment-9577add0)

Sim, 2026-11-02. The swing after a yaw key is PX4’s yaw-rate loop ringing on the simulated drone (about 1 Hz, decays over 10+ s), measured with the new scripted yaw-step test: overshoot up to 14°, ~12 s to settle (ledger rows for sim_yaw_run1 / sweep1 / sweep2). Lower gains made it worse; the sim needs more damping. Cause: the sim model turns weakly (rotor-drag yaw torque 0.0136 N·m/N vs PX4’s 0.05; no rotor-inertia torque; no rotational drag). Tracked in [NEAR-910](https://linear.app/nearlab/issue/NEAR-910). Patch 0007 passed in flight (no orbit after a turn). Findings: docs/record/sim_notes_2026-11-02.md.

The stored comment references NEAR-910 by an issue mention rather than quoting its full title. Its flight wording is reproduced as stored; the instruction files specify these were simulation runs.

### NEAR-789 — [correction added](https://linear.app/nearlab/issue/NEAR-789/set-up-one-drone-gamepad-teleop-in-the-construction-site-pad-detected#comment-f8945a20)

Correction, sim, 2026-11-02. The main cause of the swing was a PX4 filter setting, not only the sim's weak turning force. The sim's PX4 v1.16 ran MC_YAW_TQ_CUTOFF at its 2 Hz default; the real drone has MC_YAW_CUTOFF 15 Hz (that the two are the same filter is inferred, not confirmed in PX4's source). At 15 Hz (CHG-0023) the ring is gone, and the sim now uses yaw-rate gains 0.25 / 0.2 (CHG-0024, sim-only). Keyboard flying in the construction site is still to do. Evidence: docs/record/sim_yaw_sweep5_record.md, docs/record/CHANGES.md.

### NEAR-910 — [gains and incomplete booted test added](https://linear.app/nearlab/issue/NEAR-910/retune-the-sim-airframes-yaw-rate-gains-so-the-heading-settles-after-a#comment-14159819)

Sim, 2026-11-02. Gains chosen: MC_YAWRATE_P 0.25, MC_YAWRATE_I 0.2, with MC_YAW_TQ_CUTOFF 15 (CHG-0023, CHG-0024). Set live in sim_yaw_sweep5: overshoot 1.3°, settle 0.03 s, 1 crossing, swing-back 12 °/s, drift 0.05 m. The first run with these as booted gains, sim_yaw_run2, was INCOMPLETE: its first pulse was lost before the commander had subscribed, a test-script bug fixed in CHG-0025. Not done until a booted run passes.

### NEAR-913 — [model-realism purpose added](https://linear.app/nearlab/issue/NEAR-913/model-rotor-reaction-torque-and-rotational-drag-in-the-sim-starling#comment-add94d43)

Sim, 2026-11-02. Lower priority: the filter fix (CHG-0023) removed most of the ring, so this is no longer needed for [NEAR-789](https://linear.app/nearlab/issue/NEAR-789). Its purpose now is model realism only.

## Relations verified

- [NEAR-910](https://linear.app/nearlab/issue/NEAR-910) blocks [NEAR-789](https://linear.app/nearlab/issue/NEAR-789).
- [NEAR-913](https://linear.app/nearlab/issue/NEAR-913) is related to [NEAR-789](https://linear.app/nearlab/issue/NEAR-789). This related relation appeared automatically when posting the follow-up comment.
- [NEAR-915](https://linear.app/nearlab/issue/NEAR-915) is related to [NEAR-833](https://linear.app/nearlab/issue/NEAR-833).
- No blocking relation was removed.

## Exceptions and present-state caveats

- Six original issues already existed; only NEAR-916 was newly created in this run.
- The original diagnosis comment already existed and was not reposted. Its stored wording links NEAR-910 instead of quoting its full title.
- NEAR-910 was already In Progress; the follow-up’s “statuses unchanged” instruction preserved it. The six other scoped issues are Backlog. Thus the current state is not seven Backlog issues.
- All seven scoped issues are unassigned with no due date.
- The ledger row reference in NEAR-912 uses inline code solely to prevent conversion to unrelated pull-request mentions.
- “Lower priority” was posted as comment text only; NEAR-913’s structured priority was not changed.
- No source-code work or flight execution was performed. The booted yaw-step pass remains unconfirmed in the stored follow-up comment.
- No document named `2026-10-30-linear-synced.md` was found through the workspace Document search; this record therefore does not claim exact formatting parity with that file.

## Project totals

Counts include archived non-trashed issues, retrieved after updates.

| Project | Total | Backlog | In Progress | Done | Canceled |
|---|---:|---:|---:|---:|---:|
| HTX-R1 Swarm Sim Validation (Isaac), P-NEAR-28 | 60 | 49 | 2 | 8 | 1 |
| HTX-R2 Starling Flight Bring-up (M2–M8), P-NEAR-29 | 35 | 35 | 0 | 0 | 0 |

Scoped issues: HTX-R1 five (one In Progress, four Backlog); HTX-R2 two (both Backlog).
