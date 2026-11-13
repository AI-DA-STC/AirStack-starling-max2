KNOW · SIM + REAL — one screen: where each Linear project is, what passed, what is next. Codes, titles and "Done when" are Linear's, verbatim.

# Milestones — where each project is

Three Linear projects ([plan snapshot 2026-11-12](plans/2026-11-12-project-plan-linear.md); status and order live in [Linear](https://linear.app/nearlab)). **Every result is simulation unless the row says REAL DRONE.** This software (`yikuan/SVG_ground_control_dev` @ `b21d28c`) first flew the real drone on 2026-11-11: one Starling, hover, goal legs and the fence ([#33](record/LEDGER.md)). On 2026-11-12 two Starlings flew together and the collision filter was observed ([#35](record/LEDGER.md)). On 2026-11-13 one drone flew on the gamepad ([#36](record/LEDGER.md)), then was hand-flown at a hovering one ([#37](record/LEDGER.md)). Formations and random goals are unflown. The September 2026 flights were the previous software, archived in [LEDGER table 2](record/LEDGER.md#table-2--observed-on-the-previous-software-archived). Evidence: one row per test in [record/LEDGER.md](record/LEDGER.md); results tables and figures sit under each milestone on the project pages.

## Before the next real flight

Hazards the pilot assumes until the named issue re-earns them (detail: [HTX-R2.md](projects/HTX-R2.md)):

1. Software is blind to PX4 arming; the command-ACK message is unaudited against PX4 v1.14 — [PX4_MSGS_AUDIT.md](PX4_MSGS_AUDIT.md), re-run at NEAR-821.
2. fly `_ours` configs (shipped real ones carry 0.3); `land_speed_mps` must stay 0.6 — 0.3 left the drone armed on the ground ([A21](record/LEDGER.md)); landing re-earned at NEAR-826.
3. Drone ID must equal the controller target (`MAV_SYS_ID` = `target_system`; no ACK = mismatch) — NEAR-819; one uXRCE watchdog only — NEAR-820.
4. After `voxl_setup_real_drone.sh`: reboot, never `systemctl restart voxl-px4` — NEAR-818.
5. RC-takeover leak into POSCTL/ALTCTL confirmed in the current code 2026-10-29 and accepted: takeover = MANUAL or KILL ([HTX-R2.md](projects/HTX-R2.md)); `land` once after any takeover or RC kill (the commander keeps sending setpoints); re-observed at NEAR-825.
6. Older Starling (`drone_1`) flies by the owner's decision, a watcher on its front-right motor at every takeoff. That motor failed or started late in 5 of 7 arms on 2026-11-12, cause unknown ([#34](record/LEDGER.md)). It started on time in the three flights checked on 2026-11-13.
7. Takeoff flies a straight line to the takeoff point: stand each drone on its own point. The fence does not act during climb or landing.
8. Never raise the CBF radius with drones inside the new keep-out (instant emergency push-apart).
9. No warning when no pad sends commands: check `ros2 topic hz /svg/drone_2/teleop_command` ≈ 20 Hz before takeoff; keep the pad pane running until after landing ([#36](record/LEDGER.md)).
10. With the stick held, the collision filter pushes a hovering drone toward the wall behind it (0.29 m left): let go once it resists ([#37](record/LEDGER.md)).

## Where each project is

| Project (Linear) | Sim / real | Milestone in progress (snapshot 2026-11-12) | Last result | Next issue | Blocked by |
|---|---|---|---|---|---|
| [HTX-R1 Swarm Sim Validation (Isaac)](projects/HTX-R1.md) | SIM ONLY (Isaac) | S5 Finish basic sim flight checks | [#32](record/LEDGER.md) Drive mode, 0.9° off the nose, 2026-11-03 → [record](record/sim_teleop_frame_run1_record.md) | NEAR-790; then NEAR-866 (S5d, the real command route) | — |
| [HTX-R2 Starling Flight Bring-up (M2–M8)](projects/HTX-R2.md) | REAL DRONE | M4 · Goal flights with the braking fence (R1, M2, M3 also open) | [#37](record/LEDGER.md) drone hand-flown at a hovering one: closest 1.76 m, 2026-11-13 | NEAR-816; then NEAR-826 | the ten hazards above |
| [HTX-R3 Multi-Drone Localisation (VO + UWB)](projects/HTX-R3.md) | SIM + desk; L4 hand-carried | L1 · Team review pack | [#16](record/LEDGER.md) stereo VO 0.081 m RMSE over 162 m, 2026-10-22 | NEAR-843 | — |

**Sim vs real:** until HTX-R1 S5d, sim drones take a different command route (MAVROS) from the real drone, run PX4 1.16 (real 1.14) with sim-only rate gains, and Isaac's clock runs 1.3–2× wall time; full list on [HTX-R1](projects/HTX-R1.md). NUS policies run in sim at S5e, then on real drones in NEAR Lab's mocap area at HTX-R2 M8. Camera setups: A = ZED-style added camera (every camera result so far, e.g. #15, #16); B = Starling built-in sensors (HTX-R1 S5c).

## Pages

- [projects/HTX-R1.md](projects/HTX-R1.md) — sim validation S1–S10 with S5b–S5e (in work order): results tables, the S5 figures, sim vs real, sim debt
- [projects/HTX-R2.md](projects/HTX-R2.md) — real-drone bring-up R1, M2–M8: the pilot's hazards box, carried-over table, archived observations to re-earn
- [projects/HTX-R3.md](projects/HTX-R3.md) — localization research L0–L5
- [record/LEDGER.md](record/LEDGER.md) — append-only evidence: table 1 this software (#1–#37; real rows from #33), table 2 previous software (A1–A21)
- [PX4_MSGS_AUDIT.md](PX4_MSGS_AUDIT.md) — PX4 v1.14 vs px4_msgs audit and its re-run method (NEAR-821)
- Procedures: [RUNBOOK.md](RUNBOOK.md) · [PREFLIGHT.md](PREFLIGHT.md) · [DRONE_SETUP.md](DRONE_SETUP.md) · [SCENARIOS.md](SCENARIOS.md) · sim hover-test thresholds: [tools/README.md](../tools/README.md#thresholds)
- Per test: one LEDGER row + one Result cell on the project page (both from the record), one Linear comment with the ledger number and record link; then the owner ticks the issue in Linear.

