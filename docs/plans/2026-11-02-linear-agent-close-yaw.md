# Linear update — 2026-11-02, close the sim yaw retune

Instructions for the Linear agent, in the **nearlab** workspace. Apply every step below. Delete nothing. Use the wording exactly as written. All results below are simulation (Isaac Sim); none flew a real drone.

## Part 1 · NEAR-910 "Retune the sim airframe’s yaw-rate gains so the heading settles after a turn"

Add this comment, then set the status to **Done**:

> Sim, 2026-11-02. Passed with these as booted gains (sim_yaw_run3, ledger #31): overshoot 1.65°, settle 0.03 s, 1 crossing, swing-back 11.8 °/s, drift 0.056 m. Flat world, one drone, scripted pulses. Record: docs/record/sim_yaw_run3_record.md.

Leave **NEAR-789 In Progress**. It still needs the keyboard session in the construction site, with a video the owner has watched. NEAR-910 no longer blocks it.

## Part 2 · NEAR-914 "Read the drone’s MPC speed and acceleration limits in QGC and record which set it flies"

Set the status to **Canceled**, and add this comment:

> Canceled by the owner, 2026-11-02: no QGC read needed. The owner will supply the drone's parameter files later, which answers the same question. Until then starling_1_indoor_params.params (3 / 3 / 3 / 2 / 0.6) is the reference, and PREFLIGHT keeps treating the commander's 1.0 m/s cap as the only speed limit.

## Part 3 · NEAR-912 "Match the sim airframe’s MPC speed and acceleration limits to the real drone’s"

Keep the title and status. Replace the description with:

> Sim-only. Today the sim has MPC_XY_VEL_MAX 20, MPC_ACC_HOR 6, MPC_ACC_HOR_MAX 1000, MPC_Z_VEL_MAX_UP 10, MPC_Z_VEL_MAX_DN 4 (the 2026-08-20 drone backup). Match them to the drone's parameter files, which the owner will supply. Until then the reference is starling_1_indoor_params.params: 3 / 3 / 3 / 2 / 0.6. Also lower cbf_sim.yaml’s 4.0 m/s cap. Re-run hover/step and crossing after (baselines ledger `#17–#22`). Its own change-log entry.

Remove any relation from NEAR-912 to NEAR-914.

## Part 4 · Write the sync record

Write a Markdown file named `2026-11-02-linear-synced-2.md`. State only what Linear now holds:

- the status, title and description of NEAR-789, NEAR-910, NEAR-912 and NEAR-914;
- each comment added here, and the relations on those four issues;
- anything not applied, and why;
- the totals per project for **all three** projects (HTX-R1, HTX-R2 and HTX-R3): total, Backlog, In Progress, Done, Canceled.
