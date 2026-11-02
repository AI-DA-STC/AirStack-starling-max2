# Linear update — 2026-11-02 (sim yaw tuning, sim-model fidelity, MPC limits)

Instructions for the Linear agent. Apply every step below in the **nearlab** workspace. Use the titles exactly as written, including the curly apostrophe ’. Do not delete anything. Every new issue is **Backlog**, unassigned, with no due date. Reply at the end with each new issue’s NEAR id and title.

Evidence lives in the repo https://github.com/AI-DA-STC/AirStack-starling-max2: `docs/record/sim_notes_2026-11-02.md` (findings), `docs/record/sim_yaw_run1_record.md`, `sim_yaw_sweep1_record.md`, `sim_yaw_sweep2_record.md`, and `docs/record/CHANGES.md` (change log).

All runs below are simulation (Isaac Sim). None of them flew a real drone.

---

## Part 1 · HTX-R1 Swarm Sim Validation (Isaac)

### 1.1 Comment on NEAR-789

Add this comment to **NEAR-789** (status unchanged, In Progress):

> Sim, 2026-11-02. The swing after a yaw key is PX4’s yaw-rate loop ringing on the simulated drone (about 1 Hz, decays over 10+ s), measured with the new scripted yaw-step test: overshoot up to 14°, ~12 s to settle (ledger rows for sim_yaw_run1 / sweep1 / sweep2). Lower gains made it worse; the sim needs more damping. Cause: the sim model turns weakly (rotor-drag yaw torque 0.0136 N·m/N vs PX4’s 0.05; no rotor-inertia torque; no rotational drag). Tracked in the new issue "Retune the sim airframe’s yaw-rate gains so the heading settles after a turn". Patch 0007 passed in flight (no orbit after a turn). Findings: docs/record/sim_notes_2026-11-02.md.

### 1.2 Create in milestone "S5 Finish basic sim flight checks"

| Title | Description |
|---|---|
| Retune the sim airframe’s yaw-rate gains so the heading settles after a turn | Sim-only (never the real drone). Use `tools/sim.sh test yaw_step`. Done when (target): with the new gains as the airframe’s booted values, the yaw-step test passes: overshoot ≤ 3°, settle to ±2° ≤ 2 s, at most 1 swing back, swing-back ≤ 30 °/s, drift ≤ 0.15 m. The values go in as their own change-log entry, each line marked SIM-ONLY with the real value. Blocks NEAR-789. |

Add a relation: the new issue **blocks NEAR-789**.

### 1.3 Create in milestone "S5d · Sim flies the real command route (px4_interface)"

| Title | Description |
|---|---|
| Check heading hold (MC_YAW_P) on the px4_interface route with the yaw-step test | On the MAVROS route PX4 only gets "yaw rate 0", so MC_YAW_P has no effect (sim notes 2026-11-02). The px4_interface route sends an absolute heading, so heading hold matters there. Run the yaw-step test on that route and compare. |
| Match the sim airframe’s MPC speed and acceleration limits to the real drone’s | Sim-only. Today the sim has MPC_XY_VEL_MAX 20, MPC_ACC_HOR 6, MPC_ACC_HOR_MAX 1000, MPC_Z_VEL_MAX_UP 10, MPC_Z_VEL_MAX_DN 4 (the 2026-08-20 drone backup); the indoor params file has 3 / 3 / 3 / 2 / 0.6. Waits for the QGC check in HTX-R2 M2. Also lower cbf_sim.yaml’s 4.0 m/s cap. Re-run hover/step and crossing after (baselines ledger #17–#22). Its own change-log entry. |
| Model rotor reaction torque and rotational drag in the sim Starling, then re-run the yaw-step test | Optional alternative to the gain retune: make the sim body turn like a real one. Pegasus models yaw torque only as rotor drag (k_m·ω²), with no torque from motors speeding up or slowing down and no drag on rotation. A model change, its own change-log entry. Decide after the retune. |

---

## Part 2 · HTX-R2 Starling Flight Bring-up (M2–M8)

### 2.1 Create in milestone "M2 · Drone setup and hand-carry, propellers off"

| Title | Description |
|---|---|
| Read the drone’s MPC speed and acceleration limits in QGC and record which set it flies | Read MPC_XY_VEL_MAX, MPC_ACC_HOR, MPC_ACC_HOR_MAX, MPC_Z_VEL_MAX_UP, MPC_Z_VEL_MAX_DN. The 2026-08-20 backup says 20 / 6 / 1000 / 10 / 4; starling_1_indoor_params.params says 3 / 3 / 3 / 2 / 0.6. Read only. Settles iron rule 9’s wording and PREFLIGHT’s "20 m/s" line, and whether the commander’s 1.0 m/s cap is the only speed limit. |

### 2.2 Create in milestone "M5 · Gamepad flying on the real drone"

| Title | Description |
|---|---|
| Yaw-step check on the real Starling: overshoot and settle after a yaw pulse, compared with the sim | Low and slow, after NEAR-833. Measures whether the real drone also rings after a turn. Tells whether CA_ROTOR_KM 0.05 (PX4’s default) or CMU’s measured 0.0136 matches the real Starling, and whether the sim-only yaw retune hides a real-drone tuning issue. |

---

## Part 3 · Check when done

- 6 new issues: 1 in S5, 3 in S5d, 1 in M2, 1 in M5. All Backlog.
- NEAR-789 has the new comment and is blocked by the new S5 issue.
- Reply with each new issue’s NEAR id and title, so the repo can be updated to match.
