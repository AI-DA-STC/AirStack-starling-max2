# AirStack + Starling Max 2 — Milestones: plan, work log, setup & troubleshooting

> Canonical (markdown) version — **our lab's own document** (see "Whose document is whose" in
> the README; CMU's upstream guide is `experiment.md` inside the AirStack checkout).
> Per-session commands only? → [RUNBOOK.md](RUNBOOK.md).
> Last updated: 2026-10-07.
> Branch: `yikuan/SVG_ground_control` @ `cf719f0` · Working folder: `~/AirStack-starling-max2/AirStack`
>
> ⚠️ **This ladder was RESET on 2026-10-07** when the repo moved to the new AirStack branch.
> The previous ladder (M1–M6, ledger #1–#21, flights of 2026-09-01→03 on
> `daniel/diffaero_ground_control`) is preserved on tag `airstack-starling-max2` / branch
> `archive/airstack-starling-max2` and is **not** carried over: the new branch changes the
> fence model, the setpoint type, the operator view and the teleop path, so every stage is
> re-validated at STE. What changed and why → [MIGRATION.md](MIGRATION.md).

*(Unfamiliar term? → [GLOSSARY.md](GLOSSARY.md))*

## Table of contents

- [1. Objective](#1-objective)
- [2. Why milestones](#2-why-milestones)
- [3. Status](#3-status)
- [3b. Code-readiness audit (2026-10-07)](#3b-code-readiness-audit-2026-10-07)
- [3c. Test ledger — what's proven, what's next](#3c-test-ledger--whats-proven-whats-next)
- [3d. PX4 v1.14 vs px4_msgs — compatibility audit (needs re-run)](#3d-px4-v114-vs-px4_msgs--compatibility-audit-needs-re-run)
- [4. Milestones M0–M7 (procedures + validation records)](#4-milestones-m0m7-procedures--validation-records)
  - [M0 — Bring-up on the new branch](#m0--bring-up-on-the-new-branch)
  - [M1 — Sim rehearsal](#m1--sim-rehearsal)
  - [M2 — Drone provisioning + hand-carry (props off)](#m2--drone-provisioning--hand-carry-props-off)
  - [M3 — First flight on the new branch](#m3--first-flight-on-the-new-branch)
  - [M4 — Goal flights with the braking fence](#m4--goal-flights-with-the-braking-fence)
  - [M5 — Gamepad teleop, real drone](#m5--gamepad-teleop-real-drone)
  - [M6 — LED strips (optional hardware)](#m6--led-strips-optional-hardware)
  - [M7 — Multi-drone (blocked on a second Starling)](#m7--multi-drone-blocked-on-a-second-starling)
- [5. Troubleshooting quick table](#5-troubleshooting-quick-table)
- [6. Backlog — carried over, re-evaluate on this branch](#6-backlog--carried-over-re-evaluate-on-this-branch)

## 1. Objective

Replicate CMU AirLab's ground-controller workflow on our hardware: fly a ModalAI **Starling
Max 2** live, commanded by **AirStack** on a ground laptop, using **OptiTrack + Motive** mocap
as the indoor position source — now on the `yikuan/SVG_ground_control` branch, which adds
what the previous branch lacked:

- a **CBF collision filter** that is actually wired in (fixed rows for RC-flown or exempt
  drones, runtime-tunable gains) — [SCENARIOS.md](SCENARIOS.md) §1;
- a **keep-in fence** that brakes at the wall instead of freezing the swarm, plus a smaller
  **teleop fence** for hand-flying — [TELEOP.md](TELEOP.md) §6;
- a **trajectory setpoint** (position + velocity + acceleration) to PX4 instead of a bare
  velocity, so PX4 closes the position loop onboard — [MIGRATION.md](MIGRATION.md) §5;
- **gamepad teleop** in position mode (release the sticks and it holds) — [TELEOP.md](TELEOP.md);
- the **Foxglove SVG Basestation** panel as the operator console, fed by a JSON status
  snapshot on `/svg/commander_status` — [BASESTATION.md](BASESTATION.md);
- **LED strips** that show CBF activity in the room — [BASESTATION.md](BASESTATION.md) §8;
- formation profiles, a random-goal CBF stress test and an RC-intruder "squeeze" —
  [SCENARIOS.md](SCENARIOS.md) §6–8.

Scope: the lab has **one** Starling (`drone_1`, D0012). Everything multi-drone is proven in
**simulation** (M1) and parked for real flight until a second airframe exists (M7).
The mocap chain (`./mocap.sh` → `mocap_bridge` → EKF2) is **unchanged** by the branch
switch and stays exactly as [MOCAP.md](MOCAP.md) describes.

## 2. Why milestones

Flight day is a long chain: Motive → `./mocap.sh` → mocap_bridge → XRCE agent → WiFi → PX4
EKF2 → px4_interface → commander → motors. Each milestone adds **one** new link and proves it
before the next stacks on, so failures always localize to the link just added.
Sim proves the software and the operator (SITL runs real PX4 firmware); props-off stages prove
the links; hand-carry proves the stack's beliefs; only then does anything spin. Exit criteria
are observed facts, and each milestone is a re-entry point.

The ladder starts at **M0** this time because the branch switch itself is a link that can
break (rebuilds, re-provisioning, a new operator view) — see [MIGRATION.md](MIGRATION.md) §6.

## 3. Status

| Milestone | Goal | Code exists? | Validated by us? |
|---|---|---|---|
| M0 Bring-up on the new branch | Build + containers + Foxglove panel up; three sim drones visible in the Basestation | ✅ CMU | ⏳ STE |
| M1 Sim rehearsal | CBF crossing, keep-in braking, gamepad teleop, formations, random goals — all in Isaac Sim; pytest suite green | ✅ CMU (bags cited in their README) | ⏳ STE |
| M2 Drone provisioning + hand-carry (props off) | New provisioning script + uXRCE watchdog; `target_system` = `MAV_SYS_ID`; hand-carry tracked in the Basestation 3D view; EKF2 fusing | ✅ CMU | ⏳ STE |
| M3 First flight on the new branch | Takeoff → hover → land under the **trajectory** output, `hold_all` fence; command ACKs seen; iron rules re-verified | ✅ CMU | ⏳ STE |
| M4 Goal flights with the braking fence | Goal legs on the acceleration-limited profile; `keep_in` wall braking measured; gains changed live from the panel; `hold` stop-point behaviour | ✅ CMU (bags `run_045417`, `log_141`) | ⏳ STE |
| M5 Gamepad teleop, real drone | Yaw sign verified; teleop fence; release-to-hold; coast distance measured | ✅ CMU | ⏳ STE |
| M6 LED strips (optional hardware) | Daemon on the VOXL; green default, red on CBF; ESC arm LEDs muted — acknowledged | ✅ CMU | ⏳ STE (needs the strip fitted) |
| M7 Multi-drone | Formations, random-goal CBF test, RC-intruder squeeze with real airframes | ✅ CMU (3 real drones) | ⏳ **blocked — one Starling** |

CMU flight-tested M2–M7 on their own three Starlings (their `README.md` "Update 2026-09-27"
cites the flight bags) — our work is **validation and replication on our rig**, not
development. "✅ CMU" means the mechanism exists and CMU reports flying it; nothing in this
table is trusted until the "Validated by us?" cell carries a date.

## 3b. Code-readiness audit (2026-10-07)

Verified by direct inspection of the `AirStack/` snapshot (paths relative to
`AirStack/robot/ros_ws/src/svg_ground_control/` unless stated). Everything below EXISTS:

| Capability | Where in the code |
|---|---|
| Host networking for robot container | `robot/docker/docker-compose.yaml:50` — `network_mode: host` (unchanged) |
| Foxglove installers run at container start | `robot/docker/docker-compose.yaml:34-35` (general panels + SVG panel, non-fatal) |
| Studio config persistence + gamepad visibility | `robot/docker/robot-base-docker-compose.yaml:42` (`./Foxglove` mount), `:51` (`/dev/input` bind mount) |
| 8-pane (5-over-3) tmux `bringup` session | `common/.tmux.conf:16-55`; `robot/docker/.bashrc:33-46` (`sws_after_build`) |
| VOXL2 comms provisioner (rewritten) | `scripts/voxl_setup_real_drone.sh:129-146` (`px4-` wrapper + 60 s retry), `:193-240` (`svg-microdds-watchdog` unit) |
| uXRCE-DDS agent in the robot image | `robot/docker/Dockerfile.robot` — **unchanged** vs the previous snapshot (no image rebuild needed for the agent) |
| Real-drone flight interface, `target_system` | `robot/ros_ws/src/interface/px4_interface/src/px4_interface.cpp:161-163` (param), `:661` (stamped on every VehicleCommand), `:680-706` (`vehicle_command_ack` logging) |
| Trajectory setpoint input (position + velocity + acceleration) | `px4_interface.cpp:225-234` (subscriber), `:333-392` (handler, ENU→NED, NaN = not commanded), `:371-387` (absolute yaw vs yaw-rate) |
| Per-drone `target_systems:=` launch arg | `launch/real_interfaces.launch.py:54-57` (`_default_target_system`: the trailing number of the drone name) |
| Mocap → PX4 external vision | `svg_ground_control/mocap_bridge.py` — **unchanged** except a shutdown guard (`:211-215`) |
| Commander: trajectory output for real drones | `svg_ground_control/swarm_commander.py:415-418` (`real_command_mode: trajectory`), `:1982-2052` (`publish_command`), `:189-220` (`command_feedforward`) |
| Commander: status snapshot | `swarm_commander.py:1037-1118` (`/svg/commander_status`, 5 Hz), `:491` (`takeover_twins`) |
| Commander: runtime parameters | `swarm_commander.py:920-1033` (CBF gains, fence dynamics, goal law, teleop; others refused with a reason) |
| CBF filter with fixed rows | `svg_ground_control/cbf_filter.py:140` (`fixed`), `:198-216` (pruning), `:512-549` (emergency push-apart); wiring `swarm_commander.py:1810-1889`; `/svg/cbf_active` `:1909-1917` |
| Keep-in fence braking envelope + teleop fence | `svg_ground_control/fence.py:88` (`wall_speed`), `:111`, `:136`; `swarm_commander.py:1455-1581`, `:1952-1953`; teleop fence must sit inside the geofence `:607-618` |
| Position-hold leash, stick ramp, predicted stop point | `svg_ground_control/position_hold.py:62` (`leash`), `:116` (`ramp_velocity`); `swarm_commander.py:1695-1722`, `:1673-1693` (`stop_point`) |
| Go-to-goal profile | `svg_ground_control/trajectory.py:53` (`brake_speed`), `:92` (`ReferenceTracker`); `scenarios.py:123-156` |
| Gamepad teleop | `svg_ground_control/safe_teleop/teleop_node.py:42-75` (params), `:146-184` (wrong-axis-map guard); `controllers.py:90`, `:127` (profiles); `launch/teleop.launch.py`; `scripts/svg_teleop.sh` |
| Formation profiles | `swarm_commander.py:775-810`, `:1312-1338`; `config/goal_tracking.yaml:99-113`, `config/cbf_sim.yaml:101-113` |
| Random-goal scenario | `svg_ground_control/scenarios.py:238-274` (`RandomGoalsScenario`), `:172` (initial layout) |
| LED strips | `svg_ground_control/led_controller.py:100`; `scripts/svg_led_daemon.py`; `scripts/voxl_push_led.sh`; `common/ros_packages/msgs/airstack_msgs/srv/SetLedColor.srv` |
| Foxglove SVG Basestation panel + layout | `foxglove/svg-basestation/dist/extension.js` (3220 lines); `foxglove/svg_basestation.json`; `foxglove/install.py`; bridge in `launch/ground_control.launch.py:105-127` |
| Fence-clipped ground grid in the 3D view | `swarm_commander.py:2240-2292` (`fence_grid_cell_m` 0.5 m) |
| Flight services | `swarm_commander.py:813-817` (`~/takeoff ~/start ~/hold ~/land ~/reset_fence`) |
| Procedures documented by CMU | `experiment.md` Part A (sim), B (real-drone bring-up, B1 includes LEDs), C (tasks: C0 interfaces + `target_system`, C1 single goal, …), `teleop.md`, `foxglove/svg-basestation/README.md` |

**Genuinely NOT in code (manual, by design):** machine clock sync; PX4 EKF2 external-vision
parameters (the `.params` file via QGC); PX4 failsafes and the RC kill switch (QGC);
Motive-side configuration; which physical gamepad the lab owns (identify with `joy_map`,
record in [CONFIG.md](CONFIG.md)).

**Known defects on arrival** (found in the 2026-10-07 code survey — none block M0–M3, all
must be remembered; details in the corrections tables of the linked docs):

| Defect | Effect | Where documented |
|---|---|---|
| `goal_tracking.yaml` ships `scenario: random_goals` | goal / speed / formation commands are **silently ignored**; CMU's C2 recipe does nothing | [SCENARIOS.md](SCENARIOS.md) §9 |
| `goal_single.yaml` targets `drone_2`, not `drone_1` | commander waits for a drone we don't have — trim before use | [MIGRATION.md](MIGRATION.md) §6 |
| CMU `teleop.md` sign table says `left_sign = -1.0` | code has `+1.0` and records that `-1.0` flew the wrong way on the bench — **trust the code** | [TELEOP.md](TELEOP.md) §9 |
| Two CBF-exempt / external drones get **no** mutual protection | pairs with no movable drone are pruned from the solve | [SCENARIOS.md](SCENARIOS.md) §2 |
| `random_goals` samples goals with no separation | CMU bag: 100 of 221 legs had a drone within 1.5 m of a goal; one arrival took 68 s | [SCENARIOS.md](SCENARIOS.md) §7 |
| Patch 0001 (ZED camera-info race) absent upstream | re-applied in our snapshot; re-apply on any fresh CMU clone | `AirStack/README.md` |
| Stale `foxglove/svg-basestation/dist/nvm.js` | copied into every panel install; unused, harmless | [BASESTATION.md](BASESTATION.md) §9 |

## 3c. Test ledger — what's proven, what's next

> Updated after every lab/bench session. One row per discrete test: what was checked, how,
> the observed result, and the date it last passed. Numbering restarts at **#1** for this
> branch; the previous ledger (#1–#21) is on tag `airstack-starling-max2`. "Next up" is
> ordered — do the top row first.

### ✅ Tests passed

| # | Test | How (command / evidence) | Result | Date |
|---|---|---|---|---|
| — | *(nothing on this branch yet — first row lands at M0)* | | | |

### ⚠️ Carried-over issues — re-test before trusting (none copied as verdicts)

Each of these was a confirmed behaviour on the previous branch. The new branch changes the
code around every one of them, so each is **⏳ until re-observed**.

| Issue (old-branch verdict) | What changed that may affect it | Re-test at |
|---|---|---|
| **Control-authority leak: RC takeover only clean into MANUAL** (setpoints leak into POSCTL/ALTCTL) | Output is now a trajectory setpoint with position + acceleration; PX4 v1.14 still consumes `trajectory_setpoint` in POSCTL/ALTCTL, so the leak is *expected to persist* | M3 — brief the pilot exactly as before until proven otherwise |
| Commander touchdown disarm is a premature one-shot (one red QGC message per landing) | `px4_interface` now logs the DENIED ack explicitly; the commander's `robot_command` field in the snapshot shows it | M3 |
| Commander stuck non-IDLE after any RC takeover (`land` once to reset) | `takeover_twins` and the reference re-seed on `hold`/`land` are new; stuck-state logic itself unchanged | M3 |
| `test/functional_*.py` publish fake odometry on real topics | Six functional scripts now (`squeeze`, `squeeze_lag`, `fence`, `single_goal`, `multi_goal`, `hybrid`) — same hazard | standing rule, every session |
| PX4 v1.14 vs px4_msgs mismatch (`vehicle_status` echo silent; software blind to arming) | `VehicleCommandAck` is newly subscribed and `TrajectorySetpoint.acceleration` + `OffboardControlMode.acceleration` are newly populated → **§3d must be re-run** | M2 (before props) |
| `land_speed_mps` 0.6 validated (0.3 left the drone armed on the ground) | shipped configs carry **0.3** (`swarm_real`, `teleop_real` — the very value that failed) / 0.8 (`goal_single`) / 1.0 (`goal_tracking`), and `goal_single` moves `land_complete_altitude_m` to 0.1 | M3 — set our 0.6 in every config we fly, change deliberately |
| WiFi reboot-persistence, drone IP drift, NatNet on WiFi | unchanged by the branch | M2 (same checks as before) |

### ⏭ Next up (in order)

| # | Task | Where | Gated by |
|---|---|---|---|
| 1 | **M0:** `install_sdk.sh`, full `bws`, recreate `robot-desktop`, install the Foxglove panel, open the layout — three sim drones visible | laptop + container | — |
| 2 | **M1:** `cbf_sim.yaml` antipodal crossing with CBF chips/LED-red visible; pytest suite green (record the count) | container | 1 |
| 3 | **M1:** `./svg_teleop.sh solo` — gamepad identified with `joy_map`, axis guard behaviour recorded, release-to-hold in sim | laptop + container | 1 |
| 4 | **M1:** formations via `cbf_sim.yaml scenario:=goal`; `random_goals` in sim | container | 2 |
| 5 | **M2:** re-run `voxl_setup_real_drone.sh` → **reboot** the drone (never `systemctl restart voxl-px4` on this airframe); confirm `svg-microdds-watchdog` vs our `voxl-dds-retry.service` — keep ONE | drone | — |
| 6 | **M2:** agent session + `target_system=1` in the `px4_interface` startup line + hand-carry in the Basestation 3D view + EKF2 fusion + frame hand-check | container | 5 |
| 7 | **§3d re-audit** of `VehicleCommandAck`, `TrajectorySetpoint`, `OffboardControlMode` against the drone's v1.14 | laptop | 6 |
| 8 | **M3:** first flight — `swarm_real.yaml` trimmed to `drone_1`, `hold_all`, QGC visible, kill in hand | STE | 7 + [PREFLIGHT.md](PREFLIGHT.md) |
| 9 | **M4** → **M5** → **M6** in order | STE | 8 |

## 3d. PX4 v1.14 vs px4_msgs — compatibility audit (needs re-run)

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
> Until row 7 of "Next up" is done, treat the command-ACK log as **advisory only** and keep
> iron rule 5 exactly as written.

**The old audit's conclusion, for the record** (verbatim reasoning at
`git show airstack-starling-max2:docs/MILESTONES.md`, §3d): `VehicleOdometry`,
`TrajectorySetpoint`, `BatteryStatus` wire-identical; `VehicleStatus`, `VehicleCommand`,
`VehicleLocalPosition`, `VehicleControlMode` dangerous; CMU flew v1.14 with this exact
`px4_msgs`; the exercised path was wire-compatible and the commander never read `is_armed`.
The last clause is still true on this branch (`grep is_armed` over `svg_ground_control`
returns nothing) — what is new is the ACK subscription.

## 4. Milestones M0–M7 (procedures + validation records)

Each milestone: **Goal · Prereqs · Procedure (pointer + the decisive commands) · Exit
criterion · Validation record.** Procedures that are the same every session live in
[RUNBOOK.md](RUNBOOK.md); one-time setup is marked **-A**, every-session checks **-B**, the
repo's standard split.

### M0 — Bring-up on the new branch

**Goal:** the new snapshot builds and runs on the lab laptop with the new operator view, with
no drone involved.

**Prereqs:** the machine was set up for the previous branch (README "Setting up AirStack on
a NEW machine"); otherwise do that first — Steps 1–5 are unchanged.

**Procedure** — the ordered re-do list is [MIGRATION.md](MIGRATION.md) §6. The decisive
steps, laptop then container:

```bash
# laptop — NatNet SDK is a binary download CMU's .gitignore excludes (workspace build needs it)
cd ~/AirStack-starling-max2/AirStack/robot/ros_ws/src/perception/natnet_ros2 && ./install_sdk.sh
# laptop — recreate the robot container so the new /dev/input and ./Foxglove mounts exist
cd ~/AirStack-starling-max2/AirStack && ./airstack.sh down && ./airstack.sh up robot-desktop
# laptop — install the SVG Basestation panel into the host's Foxglove Studio, then RESTART Studio
python3 robot/ros_ws/src/svg_ground_control/foxglove/install.py
```
```bash
# container — full rebuild (px4_interface gained trajectory_msgs; airstack_msgs gained SetLedColor.srv)
cd ~/AirStack/robot/ros_ws && bws && sws
tmux attach -t bringup        # expect pane 0 = launch, panes 1–7 = shells titled "shell"
```
Then [RUNBOOK.md](RUNBOOK.md) §A (sim) up to the commander, and
[BASESTATION.md](BASESTATION.md) §2 to connect Studio to `ws://localhost:8765` and import
the layout.

**Exit criterion:** the Basestation shows three sim agents with `odom fresh`, the mission
chip reads `ON GROUND` (not `NO COMMANDER`), and `ros2 topic echo /svg/commander_status --once`
prints JSON with `"drones"` populated. Ledger row.

**Validation record:** ⏳ STE.

### M1 — Sim rehearsal

**Goal:** every new behaviour exercised in Isaac Sim with the exact commands used on the
real drone, so the operator learns the Basestation, the gamepad and the fence modes with
nothing at stake.

**Prereqs:** M0. GPU (Isaac Sim).

**Procedure** — [RUNBOOK.md](RUNBOOK.md) §A, then one sub-test per row, each its own ledger
line:

| Sub-test | Config / command | Watch for | Doc |
|---|---|---|---|
| CBF crossing | `cbf_sim.yaml` (antipodal, 3 drones) → `takeoff` → `start` | CBF chip `correcting drone_x` on the panel; drones pass at ≥ 2 × 0.55 m | [SCENARIOS.md](SCENARIOS.md) §5 |
| Keep-in braking | `goal_single.yaml` **trimmed to drone_1 / sim**, goal placed past the wall | drone cruises, brakes before the wall, no freeze | [SCENARIOS.md](SCENARIOS.md) §4, [TELEOP.md](TELEOP.md) §6 |
| `hold_all` latch | `swarm_sim.yaml`, drive a drone out by goal | ALL freeze, `FENCE BREACH` chip, `Reset Fence` button recovers | [BASESTATION.md](BASESTATION.md) §3 |
| Gamepad teleop | `./svg_teleop.sh solo` (host) — identify the pad with `joy_map` first | axis-guard message on a trigger-type pad; release = hold; LB locks the left stick | [TELEOP.md](TELEOP.md) §3–4 |
| Formations | `cbf_sim.yaml scenario:=goal` → `/svg/formation_command` `triangle`, `next` | all three retarget at once; `home` returns | [SCENARIOS.md](SCENARIOS.md) §6 |
| Random goals | `cbf_sim.yaml scenario:=random_goals` | continuous crossings; note any deadlock near a goal | [SCENARIOS.md](SCENARIOS.md) §7 |
| Live gains | panel slider `CBF α` 2.5 → 4.0 → `live ✓`; then from a shell `ros2 param set /swarm_commander cbf_alpha 0` must be **refused** (gains must stay > 0) | `live` readout follows the slider; the refusal names the reason | [BASESTATION.md](BASESTATION.md) §3 |
| Unit tests | container, package dir: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q -p no:cacheprovider test/` | **0 failed** (CMU's README says ~140 tests; 126 `def test_` plus parametrisation — record what you see) | [SCENARIOS.md](SCENARIOS.md) §11 |

**Exit criterion:** every row above has a ledger line with a date, and the operator can
bring the sim up and down from the tmux session without the manual terminal list.

**Validation record:** ⏳ STE.

### M2 — Drone provisioning + hand-carry (props off)

**Goal:** the real drone talks to the new branch's interface, re-provisioned with the new
script, and the Basestation tracks it by hand — nothing armed.

**Prereqs:** M0. Drone on `StarlingMax2` WiFi, laptop IP known ([CONFIG.md](CONFIG.md)).

**M2-A (one-time per drone).** On the drone, then **reboot** — on this airframe
`systemctl restart voxl-px4` (which the script's older form did) leaves the SLPI flight core
dead; a reboot is the only safe way to pick up the new startup block:

```bash
# drone (ssh root@<DRONE_IP>) — same arguments as before; the script now installs a watchdog
voxl_setup_real_drone.sh drone_1 <LAPTOP_IP> 1 8888
systemctl status svg-microdds-watchdog    # new on this branch — must be active
systemctl status voxl-dds-retry           # OUR earlier fix for the same problem — decide which ONE stays
reboot
```
⚠️ The two services both restart the uXRCE client; running both is untested. Decision
recorded in [CONFIG.md](CONFIG.md) once made.

**M2-B (every session).** [RUNBOOK.md](RUNBOOK.md) §B steps 1–7. The new checks:

- `px4_interface` startup line reads `target_system=N` where N = this drone's `MAV_SYS_ID`
  (⏳ **read `MAV_SYS_ID` back in QGC before the first arm** — the 2026-09-04 params export says **1**, a 2026-09-18 session note on this airframe says it was set to **2**; whichever it is, `target_systems:=` must match). `real_interfaces.launch.py drones:=drone_1` derives 1 from the name; pass
  `target_systems:=2` if the read-back says 2.
- Hand-carry: the Basestation 3D view's drone mesh follows the drone; the Agent State row
  shows `odom fresh`, x/y/z tagged `cmdr`. RViz is no longer the check.
- EKF2 fusion and the frame hand-check exactly as before ([RUNBOOK.md](RUNBOOK.md) §B step 6).
- `ros2 topic echo /svg/commander_status --once` → `drone_1` `state: IDLE`, `odom_fresh: true`.

**Exit criterion:** fusion within a few cm, frame hand-check correct, Basestation tracking,
watchdog decision made, §3d re-audit done (Next-up row 7).

**Validation record:** ⏳ STE.

### M3 — First flight on the new branch

**Goal:** takeoff → hover → land under the **trajectory** output with the `hold_all` fence,
RC kill in hand, and every iron rule re-observed.

**Prereqs:** M2 exit. [PREFLIGHT.md](PREFLIGHT.md) every box. `swarm_real.yaml` **trimmed to
`drone_1`** (the shipped file lists three drones and its hover z moved from our 0.5 m to
1.2 m — start at our validated 0.5 m). `land_speed_mps` left at our validated `0.6`.

**Procedure** — [RUNBOOK.md](RUNBOOK.md) §B step 8 with the Basestation open:

1. `takeoff` from the panel (confirm modal) — watch the command log go `sent → accepted →
   ✓ confirmed`, the Interface column show `request offboard ✓ / arm ✓`, and QGC show ARMED.
   A `DENIED` in the Interface column = PX4 refused (preflight); **no ack at all** =
   `target_system` mismatch — land/kill and fix before retrying.
2. Hover 20 s. Confirm the setpoint stream from a pane: `ros2 topic hz /drone_1/fmu/trajectory_command`
   ≈ 20 Hz. (The panel's Agent State `Cmd stream` column watches `velocity_command` topics only,
   so on a real drone it reads `--` — a panel limitation, not the drone: [BASESTATION.md](BASESTATION.md) §6.)
3. `land` from the panel. Confirm **DISARMED in QGC**. Expect the usual one red
   "Disarming denied" (now also visible as `disarm ✗` in the Interface column).
4. Second cycle: RC takeover to **MANUAL** mid-hover, land by hand, then `land` service once
   to reset the commander, then a clean software cycle.

**Exit criterion:** one clean untethered takeoff → hover → land with auto-disarm, plus one
takeover cycle, both in the ledger; the carried-over issues table updated with observed
verdicts.

**Validation record:** ⏳ STE.

### M4 — Goal flights with the braking fence

**Goal:** waypoints flown on the acceleration-limited profile; the `keep_in` wall braking
seen and measured; gains changed in flight.

**Prereqs:** M3 exit. A config derived from `goal_single.yaml` with `drone_2` → `drone_1`,
fence and teleop fence re-drawn to **our** net, `cbf_max_speed_mps` and
`scenario_speed_mps` reduced from the shipped `10.0` to something the room can hold
(start 1.0). Record the values in [CONFIG.md](CONFIG.md).

**Procedure** — [RUNBOOK.md](RUNBOOK.md) §C:

1. Single goal via the panel's Goal card (frame note must read `commander`, not
   "unconfirmed").
2. Square loop (§C3) — compare overshoot at the corners with the old branch's recordings.
3. **Wall test:** goal 0.5 m *past* the `keep_in` wall at low speed. Expect: cruise, brake,
   stop at the wall, no freeze, `fence_breached` stays `false`. Measure the overshoot.
4. `hold` at cruise: expect the drone to continue **forward** to a predicted stop point, not
   return to the call position.
5. Live gain: `CBF r` 0.55 → 0.8 on the slider during hover; `live ✓`; keep-out sphere in
   the 3D view grows.

**Exit criterion:** overshoot numbers at the wall and at goals in the ledger; `hold`
behaviour recorded; the config committed with its values in CONFIG.

**Validation record:** ⏳ STE.

### M5 — Gamepad teleop, real drone

**Goal:** hand-fly `drone_1` in position mode inside the teleop fence.

**Prereqs:** M4 exit. M1 gamepad row done (pad identified, `teleop_controller` recorded in
[CONFIG.md](CONFIG.md)). `teleop_real.yaml` fences re-drawn to our net; `teleop_max_speed_mps`
start 0.5.

**Procedure** — [TELEOP.md](TELEOP.md) §5, two terminals (pad first, then commander):

1. Takeoff, `start`, sticks centred — drone holds.
2. **Yaw sign check first**: yaw stick 10 % for one second, low altitude, thumb on kill.
   Wrong way → land, flip `yaw_sign` in the config, relaunch ([TELEOP.md](TELEOP.md) §2).
3. Short pushes on each axis; release — must hold within the leash (`teleop_lead_m` 0.5 m).
4. Fly toward the amber teleop-fence wall slowly — must brake and stop.
5. Pull the pad's USB during hover — command goes stale, drone holds (`joy_timeout_s`).

**Exit criterion:** yaw sign recorded, release-to-hold and coast distance measured, fence
stop observed, pad-disconnect behaviour observed; each a ledger row.

**Validation record:** ⏳ STE.

### M6 — LED strips (optional hardware)

**Goal:** the drone shows CBF activity in the room. Purely cosmetic — nothing in the LED
path can command the vehicle.

**Prereqs:** an 11-pixel RGBW strip on the ESC LED output (hardware not yet fitted ⏳).
udp/47901 open in the laptop's firewall.

**M6-A (one-time):** [BASESTATION.md](BASESTATION.md) §8 — `scripts/voxl_push_led.sh drone_1
<DRONE_IP>` from the laptop; on the drone `systemctl status svg-led` → `opened … sink`,
`PX4 ESC LED bits muted`.

**M6-B (every session):** commander launch logs `drone_1: LED daemon online`; strip green;
`ros2 topic pub --once /svg/led_command std_msgs/msg/String "{data: 'drone_1 blue'}"` works.

**Exit criterion:** green at rest, red during an M4 wall test or a sim CBF correction,
back to green within a second. ⚠️ **Acknowledged in the ledger:** the ESCs' own status LEDs
no longer show arm state — QGC is the arming display, as always.

**Validation record:** ⏳ STE.

### M7 — Multi-drone (blocked on a second Starling)

**Goal:** formations, the random-goal CBF test and the RC-intruder squeeze with real
airframes — the branch's headline features.

**Prereqs:** a second (and third) Starling, each with a unique `MAV_SYS_ID` / `target_system`,
DDS domain and Motive body ([DRONE_SETUP.md](DRONE_SETUP.md)); a second pilot for the squeeze;
M1–M5 done. All three procedures are **sim-validated in M1** and written out in
[SCENARIOS.md](SCENARIOS.md) §6–8 with their safety briefs.

**Exit criterion:** not defined until hardware exists.

**Validation record:** ⏳ blocked — one Starling (2026-10-07).

## 5. Troubleshooting quick table

Moved to [TROUBLESHOOTING.md](TROUBLESHOOTING.md) (unified symptom index). New on this
branch: the first move for anything odd is `ros2 topic echo /svg/commander_status --once`
— it names the state, the last command outcome, odometry freshness and fence status in one
message ([BASESTATION.md](BASESTATION.md) §4).

## 6. Backlog — carried over, re-evaluate on this branch

The previous branch's §8 held three **designed-but-not-implemented** fixes. Each was written
against the old `swarm_commander.py` line numbers and the old velocity-only output; none can
be applied as written. Status on this branch:

| Old backlog item | What it fixed | On this branch |
|---|---|---|
| Fix 1 — `LANDED_SETTLE` state (settle on the ground before the one-shot disarm) | premature "Disarming denied" | **Still absent** — the disarm is still a timed one-shot; the ack is now logged. Re-evaluate after M3 if landings ever stay armed again |
| Fix 2 — `~/release` service (stop streaming setpoints so POSCTL takeover is clean) | control-authority leak | **Still absent** — no release service (`swarm_commander.py:813-817` lists five). Leak expected to persist; MANUAL-or-KILL rule stands |
| Fix 3 — param-gated yaw passthrough | yaw stayed at takeoff heading | **Subsumed** — the trajectory output carries an absolute yaw for scenario drones and yaw-rate for teleop (`swarm_commander.py:2008-2028`); the old "CBF is 3-DOF linear" premise is unchanged (yaw bypasses the CBF) |

New candidates found 2026-10-07 (not ours to fix — report upstream):

- `random_goals` samples goals with no separation from other drones (deadlock on a goal);
- `goal_single.yaml` / `goal_tracking.yaml` ship values (drone_2, `random_goals`, 10 m/s)
  that contradict CMU's own `experiment.md` recipes;
- `svg_teleop.sh real` gates on `natnet_ros2` — our rig uses `./mocap.sh` (the gate on
  `/drone_1/pose` may still pass; untested);
- `svg-microdds-watchdog` duplicates our `voxl-dds-retry.service`.
