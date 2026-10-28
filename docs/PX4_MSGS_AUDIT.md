KNOW · REAL DRONE — PX4 v1.14 (the drone) vs the vendored `px4_msgs` (effectively release/1.15): which messages are wire-compatible, which are not, and how to re-run the check. Moved whole from the old MILESTONES.md on 2026-10-29. Re-earned at NEAR-821 ([HTX-R2.md](projects/HTX-R2.md)).

# PX4 v1.14 vs px4_msgs — compatibility audit (needs re-run)

## Status on this software

> ⚠️ **Carried over from the previous branch, 2026-08-11 — its conclusion is NOT yet valid
> here.** The vendored `px4_msgs` is the same (`src/local/controls/px4_msgs`, upstream main @
> `9e35651`, effectively release/1.15) and the drone is still v1.14, but the new branch
> **changes which messages and fields are exercised**:
>
> | Message | Old branch | This branch | Risk to re-check |
> |---|---|---|---|
> | `TrajectorySetpoint` | position NaN, velocity set | position + velocity + **acceleration** set (`px4_interface.cpp:364`, `:379`, `:386`; `:356-363` is the NaN init) | wire-identical 1.14↔1.15 per the old audit — acceleration field position must be re-confirmed |
> | `OffboardControlMode` | position/velocity flags | `position`, `velocity`, **`acceleration`** all true for TRAJECTORY (`:626-633`) | the old audit covered "the first 6 flags" — acceleration is among them, confirm |
> | `VehicleCommandAck` | not subscribed | **subscribed and logged** (`:208-213`, `:680-706`) | **new** — never audited; if its 1.14 layout differs the ACCEPTED/DENIED log is garbage and must be ignored |
> | `VehicleCommand` | sent | sent, with `target_system` (`:661`) | the old audit found trailing-metadata corruption only; `target_system` sits before `source_component`, so it should decode — confirm |
> | `VehicleStatus` | subscribed, undecodable, unused | same | same |
>
> Until NEAR-821 is done, treat the command-ACK log as **advisory only** and keep
> iron rule 5 exactly as written.

## The 2026-08-11 audit, for the record

**The old audit's conclusion, for the record** (verbatim reasoning at
`git show airstack-starling-max2:docs/MILESTONES.md`, §3d): `VehicleOdometry`,
`TrajectorySetpoint`, `BatteryStatus` wire-identical; `VehicleStatus`, `VehicleCommand`,
`VehicleLocalPosition`, `VehicleControlMode` dangerous; CMU flew v1.14 with this exact
`px4_msgs`; the exercised path was wire-compatible and the commander never read `is_armed`.
The last clause is still true on this branch (`grep is_armed` over `svg_ground_control`
returns nothing) — what is new is the ACK subscription.

**Symptom that triggered this:** `vehicle_status` streams at ~30 Hz per `ros2 topic hz`, but
`ros2 topic echo` prints nothing — suspected px4_msgs definition mismatch between the drone's
PX4 v1.14 and the workspace's message definitions.

**FULL AUDIT 2026-08-11 (two-agent verification):** the vendored px4_msgs
(`src/local/controls/px4_msgs`) is a byte-exact snapshot of upstream px4_msgs **main @
`9e35651` (2024-06-26) — effectively release/1.15** for all flight-critical messages (pkg
version 2.0.1; diffed against every upstream commit since 2023). The rest of the workspace
agrees: **sim containers build PX4 v1.16.1 SITL** (`Dockerfile.isaac-ros:3`, ms-airsim
`Dockerfile:13`), agent v2.4.3 is version-agnostic, and the ONLY v1.14 artifacts are
drone-side (factory `microdds_client` name; the setup script auto-detects both names).

**Per-message audit vs release/1.14:** `VehicleOdometry`, `TrajectorySetpoint`,
`BatteryStatus` **wire-identical** (mocap feed + setpoints safe — which MASKS the problem);
`OffboardControlMode` benign for position/velocity offboard; `VehicleStatus`,
`VehicleCommand` (arm/mode commands — `source_component` u8→u16 shifts everything after it),
`VehicleLocalPosition`, `VehicleControlMode` **DANGEROUS** (mid-message inserts/reorder →
silent garbage both directions).

**REVISED after CMU input (same day):** CMU confirms THEY also flew a v1.14 drone — with
this exact px4_msgs (git history in `~/AirStack-cmu`: px4_msgs added 2026-03-09 in the
Jazzy-upgrade commit, untouched since, i.e. before their flight tests).

**Code audit explains why it works:** the SVG workflow's exercised path is wire-compatible —
`px4_interface` subscribes ONLY to `VehicleStatus` + `VehicleOdometry`; odometry +
`TrajectorySetpoint` are byte-identical to 1.14; `OffboardControlMode`'s first 6 flags (all
we use) are identical; `VehicleCommand`'s corruption is confined to trailing metadata after
`source_component` (command/params/targets decode correctly on the drone) — and crucially the
commander's ARMING sequence is **time-staged fire-and-forget** (offboard @1.0s, arm @1.5s,
ascend @2.5s — `swarm_commander.py:77-80`) and **nothing in svg_ground_control reads
`is_armed`**, so the undecodable `VehicleStatus` is never consumed.
`VehicleLocalPosition`/`VehicleControlMode` aren't subscribed at all.

**Conclusion: flying on v1.14 is evidenced-OK for THIS workflow (CMU did it).** Residual
risks to respect at the first flight (NEAR-825): the software is BLIND to arming/nav state (QGC + RC kill are the only
arming visibility — both already mandated), and any future use of the onboard
`takeoff_landing_planner` path (which DOES gate on `is_armed`) would break. Optional clean-up
remains upgrading the drone to the voxl-px4 1.15 line. Worth asking CMU their exact voxl-px4
build to fully close this.

**Matters for:** first flight (NEAR-825) caution, not a blocker — fly with QGC visible + thumb on RC kill (already
required); don't trust any software arming indication.

## Re-run method
1. Drone side: `adb shell` → `px4-listener vehicle_status` and `cat /etc/modalai/voxl-px4.conf` → record the exact voxl-px4 build (PX4 v1.14.x).
2. Workspace side: `git -C AirStack log -1 --format=%H -- robot/ros_ws/src/local/controls/px4_msgs` and `cat AirStack/robot/ros_ws/src/local/controls/px4_msgs/package.xml | grep version`.
3. For each of `VehicleCommandAck`, `TrajectorySetpoint`, `OffboardControlMode`, `VehicleCommand`, `VehicleOdometry`, `VehicleStatus`: diff the vendored `msg/<Name>.msg` against PX4 `release/1.14` `msg/<Name>.msg` (`git -C <px4 checkout> show release/1.14:msg/<Name>.msg`) field by field; a field inserted, removed, reordered or retyped before any field we read or write = NOT compatible.
4. Live check with props off, drone strapped down, QGC visible: `arm` from the panel; the `px4_interface` log must print `PX4 ack: ACCEPTED` with `command 400` and the DENIED path must print `DENIED` on a refused command (e.g. arm with `COM_ARM_WO_GPS` unmet). A garbled or absent decode = treat the ACK log as advisory (iron rule 5 stays as written).
5. Record: one LEDGER row (REAL), the per-message verdict table updated here with the date, and the NEAR-821 Result cell on HTX-R2.md.
