KNOW · SIM + REAL — one screen: where each Linear project is, what passed, what is next. Codes, titles and "Done when" are Linear's, verbatim.

# Milestones — where each project is

Three Linear projects ([plan snapshot 2026-10-26](plans/2026-10-26-project-plan-linear.md); status and order live in [Linear](https://linear.app/nearlab)). **Every result is simulation unless the row says REAL DRONE.** Nothing on this software (`yikuan/SVG_ground_control_dev` @ `b21d28c`) has flown; the September 2026 flights were the previous software, archived in [LEDGER table 2](record/LEDGER.md#table-2--observed-on-the-previous-software-archived). Evidence: one row per test in [record/LEDGER.md](record/LEDGER.md); results tables and figures sit under each milestone on the project pages.

## Before the next real flight

Hazards the pilot assumes until the named issue re-earns them (detail: [HTX-R2.md](projects/HTX-R2.md)):

1. Software is blind to PX4 arming; the command-ACK message is unaudited against PX4 v1.14 — [PX4_MSGS_AUDIT.md](PX4_MSGS_AUDIT.md), re-run at NEAR-821.
2. fly `_ours` configs (shipped real ones carry 0.3); `land_speed_mps` must stay 0.6 — 0.3 left the drone armed on the ground ([A21](record/LEDGER.md)); landing re-earned at NEAR-826.
3. Drone ID must equal the controller target (`MAV_SYS_ID` = `target_system`; no ACK = mismatch) — NEAR-819; one uXRCE watchdog only — NEAR-820.
4. After `voxl_setup_real_drone.sh`: reboot, never `systemctl restart voxl-px4` — NEAR-818.
5. RC-takeover leak into POSCTL/ALTCTL confirmed in the current code 2026-10-29 and accepted: takeover = MANUAL or KILL ([HTX-R2.md](projects/HTX-R2.md)); `land` once after any takeover; re-observed at NEAR-825.

## Where each project is

| Project (Linear) | Sim / real | Milestone in progress (snapshot 2026-10-26) | Last result | Next issue | Blocked by |
|---|---|---|---|---|---|
| [HTX-R1 Swarm Sim Validation (Isaac)](projects/HTX-R1.md) | SIM ONLY (Isaac) | S5 Finish basic sim flight checks | [#21](record/LEDGER.md) FAIL crossing, min 0.95 m vs 1.10 m, 2026-10-30 → [record](record/sim_crossing_run1_record.md) | NEAR-788 (787 gate decision open) | — |
| [HTX-R2 Starling Flight Bring-up (M2–M7)](projects/HTX-R2.md) | REAL DRONE | R1 · New mocap and network pipeline (not started) | none on this software; previous software [A21](record/LEDGER.md), 2026-09-03 | NEAR-814 | mocap system back ~2026-11-09; the five hazards above |
| [HTX-R3 Multi-Drone Localisation (VO + UWB)](projects/HTX-R3.md) | SIM + desk; L4 hand-carried | L1 · Team review pack | [#16](record/LEDGER.md) stereo VO 0.081 m RMSE over 162 m, 2026-10-22 | NEAR-843 | — |

## Pages

- [projects/HTX-R1.md](projects/HTX-R1.md) — sim validation S1–S10: results tables, the S5 step-response figure, sim debt
- [projects/HTX-R2.md](projects/HTX-R2.md) — real-drone bring-up R1, M2–M7: the pilot's hazards box, carried-over table, archived observations to re-earn
- [projects/HTX-R3.md](projects/HTX-R3.md) — localization research L0–L5
- [record/LEDGER.md](record/LEDGER.md) — append-only evidence: table 1 this software (#1–#19, all sim), table 2 previous software (A1–A21)
- [PX4_MSGS_AUDIT.md](PX4_MSGS_AUDIT.md) — PX4 v1.14 vs px4_msgs audit and its re-run method (NEAR-821)
- Procedures: [RUNBOOK.md](RUNBOOK.md) · [PREFLIGHT.md](PREFLIGHT.md) · [DRONE_SETUP.md](DRONE_SETUP.md) · [SCENARIOS.md](SCENARIOS.md) · sim hover-test thresholds: [tools/README.md](../tools/README.md#thresholds)
- Per test: one LEDGER row + one Result cell on the project page (both from the record), one Linear comment with the ledger number and record link; then the owner ticks the issue in Linear.

