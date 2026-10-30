# Rescope HTX-R1/R2/R3 for the real command route, NUS velocity policies and two camera setups — design (approved and applied, 2026-10-30)

**Change list (what the owner applies in Linear):** [docs/plans/2026-10-30-linear-change-list.md](../../plans/2026-10-30-linear-change-list.md).
**Process:** quality-change skill. A panel of four (engineering manager, flight-test engineer, test automation, newcomer reader) wrote positions and voted in two rounds. A builder check followed; its 20 questions are answered in the last section.

## Terms

- **NUS:** the university team writing the swarm decision policies. **CMU:** the AirLab team whose commander (`swarm_commander`) we vendor.
- **Real command route:** commander → trajectory → `px4_interface` → uXRCE-DDS (PX4's ROS 2 link) → PX4. The real drone flies it. The sim today flies commander → velocity → MAVROS → PX4 instead.
- **The two MAVROS-route bugs:** the release swing (fixed by patch 0006) and the turn orbit (a turned drone circles, because MAVROS labels the velocity as body frame).
- **Vehicle time:** PX4's own clock. Isaac runs 1.3–2× faster than the wall clock, so gates are timed in vehicle time. **Real-time factor:** sim seconds per wall second.
- **Setup A / B:** short table labels for the two camera setups below.
- **Iron rule 9:** sim-only settings never go to the real drone (CLAUDE.md).

## Intent

The owner wants to test NUS policies in sim before flying them on the real drones. NUS policies output one velocity per drone. CMU's commander filters those velocities with its CBF (collision avoidance) and flies them to PX4. A sim result only carries over if the sim drone uses the real drone's command route. The sim must also carry the Starling 2 Max's own sensors, so camera-based work (cuVSLAM, OpenVINS) can be re-run on them.

## Owner decisions (2026-10-30, fixed)

- **D1.** NUS evaluation is a new milestone in HTX-R1 (sim) and in HTX-R2 (real drones), not a new project.
- **D2.** Keep both camera setups. **ZED-style added camera (A):** the stereo camera plus Jetson payload planned so far. **Starling built-in sensors (B):** the drone's own cameras, ToF, thermal camera and IMUs. Both are modelled in sim and carried through the experiments.
- **D3.** In sim, run both cuVSLAM and OpenVINS (what the drone runs), and compare them.
- **D4.** Model all of the Starling 2 Max's sensors as accurately as possible.
- **D5.** NUS policies output per-drone velocities, filtered by CMU's CBF.

## Goals

1. The sim drone flies the real command route, with MAVROS not started.
2. NUS policies are evaluated in sim on that route, then on the real drones with the same scenarios and gate numbers.
3. Both camera setups exist in sim, and each VIO is scored on each setup in one table.
4. Every new sim record says which route and which camera setup it used. A record that cannot prove both is INCOMPLETE.
5. A reader can always tell a sim result from a real one.

## Non-goals

- No change to the real drone's PX4 or VOXL configuration (iron rule 9).
- No sim PX4 built at v1.14. The v1.16 vs v1.14 gap is a recorded difference, unless the message check (NEW-5) finds a topic the commander needs that does not decode.
- No separate "sim fidelity" milestone. The clock, PX4 version and rate-loop differences are issues inside S5d.
- Done issues are not touched. NEAR-789 (keyboard teleop) stays. Old ledger rows are not rewritten.
- Patch 0007 (the turn-orbit fix for the MAVROS route) stays held. It is moot once the sim takes the real route.

## Decisions (with the panel vote)

| # | Question | Decision | Vote |
|---|---|---|---|
| P1 | Where the real-route work goes | Its own milestone, **S5d**, before S6. The route and the position source (S6) are two changes and must fail separately. | 4–0 |
| P2 | Where the NUS sim milestone sits | **S5e**, after S6 and before S5b, S5c and S7. NUS on real drones reads mocap positions, so nothing waits on cuVSLAM. | 4–0 |
| P3 | Codes | **S5d · …**, **S5e · …** (like S5b/S5c) and **M8 · …** (like M2–M7). No clash with S9. | 3–1 (test automation preferred S5r/S5n) |
| P4 | Camera naming | Plain words in titles. A and B only as short table labels. | 4–0 |
| P5 | Where the VIO comparison lives | S5c renamed "Compare the two camera setups for cuVSLAM and OpenVINS". Method: one `vio_site` test run per setup and per VIO. NEAR-802 Canceled with a note. | unanimous in substance |
| P6 | Sim vs real | A four-line "Sim vs real" box on HTX-R1 and MILESTONES.md. The LEDGER already has a SIM/REAL column; new run names keep starting `sim_` or `real_`. New ledger sentences name the camera setup (NEW-2). | 4–0 |
| P7 | Test-driver axes as Linear issues | Split 2–2. **Ruling:** one outcome issue in S5d, "Sim records name and prove their command route and camera setup" (NEW-2). Flag names are left to the plan. | 2–2, coordinator ruling |

**Ruling on order.** S5e sits after S6, so codes no longer sort in work order (S5b and S5c already did not). The milestones are dragged into work order in Linear, and HTX-R1 gets one line under its title: S5 → S5d → S6 → S5e → S5b → S5c → S7 → S8 → S9 → S10. Cost if wrong: a reader may still sort by code.

## The new and changed milestones

Full rows and the old titles are in the change list. Done-when sentences are targets. Each new milestone's Linear description is its Purpose and Done-when sentence below.

**S5d · Sim flies the real command route (px4_interface).**
*Purpose:* the sim drone takes the same command path as the real drone, so sim results carry over.
*Done when (target):* one sim drone takes off, hovers and lands through `px4_interface` with MAVROS not started. The hover and 1 m step test passes on gates no looser than [ledger #17–#19](../../record/LEDGER.md), in vehicle time. The release and 90° turn test shows neither MAVROS-route bug. The crossing is re-run against ledger #22. Every sim record names its route and camera setup and prints the remaining sim-vs-real differences.
Issues NEW-1 to NEW-8. NEW-1 is the draft trial ([2026-10-30-sim-real-route-trial-design.md](2026-10-30-sim-real-route-trial-design.md)).

**S5e · Evaluate NUS velocity policies in sim.**
*Purpose:* check a NUS policy in sim, on the real command route, before it flies on a real drone.
*Done when (target):* the velocity contract (frame, units, limits, rate, timeout) is written once and shared with NUS. The plug-in point and its teleop behaviour (leash, fence, hold on timeout) are decided. One, two and three policy drones fly in sim with collision avoidance on and off, each with one command and a record. The separation gate is agreed. Results say "observed in sim", never "validated".
*Gated by:* S5d, S6 (sim mocap, so positions come the way they do on the real drones), and the clock: sim time for every gate, or a real-time factor near 1 that is recorded (NEW-6). NEW-13 is blocked by the owner's NEAR-787 gate decision (a Linear relation).

**S5c · Compare the two camera setups for cuVSLAM and OpenVINS** (renamed from "Choose the camera for cuVSLAM").
*Done when (target):* every Starling built-in sensor is modelled at its real mount, resolution and rate. OpenVINS runs in sim. The flat-world and site VIO tests are re-run on the built-in sensors, with their images recorded for replay. One table scores cuVSLAM and OpenVINS on both setups.
One issue per sensor: tracking_front and tracking_down (AR0144), hires_front and hires_down (IMX412), ToF, thermal (approximate, since Isaac has no thermal sensor), and the IMUs. NEAR-809 moves here from S8. The ZED-style results (ledger #15, #16) stay as setup A and are not re-run. Mounts and rates come from the m0054 backup until NEW-23 delivers each flown drone's files; records say which source they used.

**S8 Model the ZED-style added camera and Jetson payload** (renamed). Same work, named for setup A. NEAR-798 is renamed to match. NEAR-807 and NEAR-808 keep their titles. Setup B's IMU is NEW-19.

**M8 · Evaluate NUS velocity policies on the real drones** (HTX-R2, new).
*Done when (target):* one, two, then three Starlings fly the S5e scenarios with the same gate numbers, speed capped below the sim-tested speed, fence on. The real results are compared with the sim results. Ticks only from REAL records.
*Gated by:* M4 (fence braking measured), M7 (multi-drone) and S5e. The project is renamed "(M2–M8)".

**HTX-R2 M2** gains NEW-23: copy each Starling's camera calibration and mount files, read only.

**HTX-R3 L2 and L4:** NEAR-847, NEAR-855 and NEAR-856 are renamed to cover both setups and both VIOs. L2's setup-B cameras depend on S5c; this is stated in L2's description.

NEAR-860 (S5) is not renamed: it stays the ZED-style recording. Setup B's recording is part of NEW-21.

## Delivery

1. The owner approves this design and the change list.
2. The owner applies the change list in Linear (milestone order, descriptions, the NEAR-787 relation, the project rename included).
3. A new snapshot `docs/plans/<date>-project-plan-linear.md` is written from Linear in the same format as the 10-26 file. Claude writes it from the owner's Linear view or export, as before, and fills the NEW-n → NEAR id map in the change list.
4. A plan (writing-plans skill) updates the repo in one pass, from that snapshot:
   - HTX-R1/R2/R3 milestone sections and issue tables; the HTX-R1 order line and "Sim vs real" box; MILESTONES.md; DOCS_STANDARD §2 (snapshot file name, milestone codes).
   - HTX-R1 stays within its 250-line budget (now 198, about +45 expected). If it does not fit, the plan proposes the cut to the owner.
   - The "Sim debt" heading changes: the clock item now gates S5e.
   - `tools/docs_check/check_docs.py`: `PLAN_FILE` points at the new snapshot. `plan_issues()` accepts `Canceled`. A new rule checks milestone names on the pages against the snapshot. A new rule checks every row of a change list marked "Applied" against the snapshot (same title, same milestone), and fails on a leftover `NEW-n`.

Nothing on the project pages changes before the new snapshot exists.

## Left to the builder (the plan)

- Flag names and how `tools/sim.sh` selects route and camera (`--route`, `--camera A|B`, `--opt vio=` are the panel's working names).
- Where the velocity contract file lives (one file under `docs/`, linked from S5e and M8).
- How the milestone-name rule matches page headings to snapshot names.

## Done when

- The owner has approved this design and the change list.
- Linear matches the change list and a fresh snapshot is in `docs/plans/`.
- The repo pages match the snapshot and `tools/sim.sh check` passes, including the new rules.
- Newcomer test passes: from MILESTONES.md plus one click, a new reader answers "does the sim fly the real command route yet?", "where are the NUS sim results?" and "which camera setup did ledger #15 use?" in ≤ 15 lines read each.

## Builder-check answers (2026-10-30)

| # | Question | Answer |
|---|---|---|
| 1 | Who writes the snapshot; the checker's fixed file | Delivery 3 and 4 |
| 2 | Canceled fails parity | `plan_issues()` accepts Canceled; the snapshot lists it; total stays 105 |
| 3 | Vague checker rules | Delivery 4: only change lists marked "Applied"; count-line rule dropped (the snapshot inventory is the count) |
| 4 | Milestone names unchecked | In scope, Delivery 4 |
| 5 | NEAR-860 / NEAR-847 order | NEAR-860 not renamed; L2 states its S5c dependency |
| 6 | S6 gates S5e? | Yes, added |
| 7 | LEDGER already has SIM/REAL | P6 revised: no new column; new sentences name the setup; newcomer question uses #15 |
| 8 | Linear text | Change list "Applying it" paragraph; gates go in milestone descriptions; NEAR-787 as a relation |
| 9 | "·" in names | S5d · , S5e · , M8 · ; S8 keeps no dot, as in the snapshot |
| 10 | NEAR-808 "was" title cut | NEAR-808 now KEEP, full title |
| 11 | Apostrophes | Curly ’ everywhere in titles |
| 12 | "real route" in sim titles | Titles say "px4_interface route" |
| 13 | HTX-R2 "(M2–M7)" | Project renamed "(M2–M8)"; its "simulation outside scope" stays true (M8 flies real drones); DOCS_STANDARD §2 in Delivery 4 |
| 14 | CMU vs mocap room | Open, for the owner (below); titles no longer say CMU |
| 15 | NEAR-808 vs S8 | KEEP for setup A; setup B's IMU is NEW-19 |
| 16 | HTX-R1 budget | Delivery 4 |
| 17 | "Sim debt" heading | Delivery 4 |
| 18 | Newcomer terms | Terms section added; ledger rows linked |
| 19 | Counts by state | Change list count line gives per-project totals; all new issues Backlog, one Canceled |
| 20 | "under mocap" | No title breaks it |

**Resolved (owner, 2026-10-30):** M8 flies in NEAR Lab's mocap area, like M2–M7. **Status:** approved and applied in Linear 2026-10-30, the HTX-R1 milestone order dragged by the owner the same day ([sync record](../../plans/2026-10-30-linear-sync-record.md)); repo updated by [the plan](../plans/2026-10-30-rescope-repo-update.md).
