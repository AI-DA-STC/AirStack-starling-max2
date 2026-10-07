# MIGRATION — from `daniel/diffaero_ground_control` to `yikuan/SVG_ground_control` (2026-10-07)

> **Who this is for:** anyone who flew this rig on 2026-09-01→03, or who reads the archived
> docs and wonders why they no longer match the tree. It is the bridge between the two
> AirStack snapshots: what changed, what must be re-done, which old statements are now wrong,
> and where the old material lives. **This is NOT a runbook** — read it once, then work from
> [RUNBOOK.md](RUNBOOK.md), [PREFLIGHT.md](PREFLIGHT.md) and the new
> [MILESTONES.md](MILESTONES.md) ladder. Delete it once M0–M7 are signed off at STE.

*(Unfamiliar term? → [GLOSSARY.md](GLOSSARY.md))*

## 1 · Why there is a new branch and how the two relate

They are **siblings, not successors.** Both start from CMU commit `a46f04b` *"goal tracking
verified"* (2026-06-23) and then diverge. Neither contains the other; there is no merge.

```bash
# in ~/AirStack (the CMU clone that holds real git history — the vendored
# AirStack/ folder in THIS repo is a flat snapshot with no .git)
git merge-base cf719f0 f544c74      # -> a46f04b563a5...  "goal tracking verified"
```

**`daniel/diffaero_ground_control`** (our old snapshot, tip `f544c743`, 2026-07-20) went
toward a learned end-to-end policy: diffaero checkpoints, a planar policy, a velocity-command
commander, ToF visualisation — and **removed the CBF from its commander** (`ac1acc4 removed
cbf filter`). Its eleven commits past the ancestor, newest first: `f544c74` hardware impl
changes · `9672a9b` added diffaero checkpoints · `7ac9d4d` added new planar policy support ·
`1b67e36` RIC changes from deployment · `775f475` added real world deployment launch
configurations · `848be9b` added tof visualization · `868b365` implemented vel-cmd diffaero ·
`0963a7a` added implementation docs · `934167c` added face goal state · `a58bdb1` added
position publisher · `ac1acc4` removed cbf filter.

**`yikuan/SVG_ground_control`** (the new snapshot, tip `cf719f0`, vendored here on
2026-10-07 as commit `91376aa`) **kept** the CBF and built the ground-station side out
instead — gamepad teleop, a geofence braking envelope, trajectory output with acceleration
feedforward, onboard LEDs, a Foxglove basestation. Four commits past the ancestor:

| | |
|---|---|
| `564d43e` | CBF external-velocity reactivity, formation profiles, C5 RC-intruder config |
| `60a90bf` | Onboard LED strips, `px4_interface` `target_system`, 5-over-3 (8-pane) tmux bringup |
| `b9f4107` | gitignore local Micro-XRCE-DDS-Agent clone and `led_ws` reference workspace |
| `cf719f0` | svg_ground_control: teleop, trajectory output, fence envelope, CBF feedforward, foxglove basestation (dev 2026-08-24..09-27) |

**Consequence for us:** September's flights were validated on a branch *without* half of this
and *with* a different commander output. The CBF our docs describe is back (and now reacts to
external velocities); the diffaero machinery our docs never used is gone. Flight validation
restarts — see the M0–M7 ladder in [MILESTONES.md](MILESTONES.md) §3.

## 2 · Where the old material lives

Nothing was deleted from history. The pre-2026-10-07 state — old docs, old ledger #1–#21,
old `AirStack/` snapshot — is frozen at two refs in this repo:

| Ref | What it is |
|---|---|
| tag `airstack-starling-max2` | the exact commit that was `main` on 2026-10-06 |
| branch `archive/airstack-starling-max2` | the same commit, as a branch you can check out |

```bash
# anywhere in this repo (host shell)
git show airstack-starling-max2:docs/MILESTONES.md | less     # the old ledger #1-#21
git show airstack-starling-max2:docs/RUNBOOK.md               # the old session procedure
git diff airstack-starling-max2 HEAD -- AirStack/             # the whole snapshot swap
```

On GitHub: pick `archive/airstack-starling-max2` (or the tag) from the branch dropdown, or
append `/tree/airstack-starling-max2/docs` to the repo URL.

⚠️ **The old test ledger #1–#21 is NOT carried over.** The new MILESTONES.md ledger restarts
at **#1** — when citing a September result, say "archive ledger #19", never bare "#19". The
*lab facts* those flights produced (EKF2 params, RC mapping, frame hand-check,
`MPC_THR_HOVER 0.165`, network values) do live on in [CONFIG.md](CONFIG.md) and
[DRONE_SETUP.md](DRONE_SETUP.md) — those are not branch-specific.

## 3 · What was REMOVED from the code

All paths relative to `AirStack/robot/ros_ws/src/svg_ground_control/` unless noted.

| Removed | Was |
|---|---|
| `svg_ground_control/diffaero_commander.py`, `diffaero_velocity_commander.py` | the learned-policy commanders |
| `diffaero/` (whole package) | the policy runtime |
| `launch/diffaero_real.launch.py`, `diffaero_single.launch.py`, `diffaero_velocity_single.launch.py` | its launch files |
| `config/diffaero_sim.yaml`, `diffaero_vel_sim.yaml`, `diffaero_vel_real.yaml` | its configs |
| `DIFFAERO.md`, `diffaero_experiment.md` | its docs |
| `scripts/preflight_diffaero_mode_c.sh` | its preflight script |
| `robot/ros_ws/checkpoints/` (repo-level) | the policy weights |
| `svg_ground_control/keyboard_teleop.py` + its `setup.py` console script | keyboard teleop — replaced by the gamepad `safe_teleop` (§5) |
| `config/tof_real_to_sim_bridge.yaml` | ToF bridge config |

✅ **Nothing procedural is lost.** The archived docs never referenced a single diffaero file
by name — only the branch name — so no RUNBOOK step, config row or troubleshooting entry
pointed at anything above. The one real loss is **keyboard teleop**; §5 covers the replacement.

## 4 · What was ADDED

| Added | What it is | Doc |
|---|---|---|
| `svg_ground_control/fence.py`, `trajectory.py`, `position_hold.py` | geofence maths (`hold_all` latch + `keep_in` braking envelope), the go-to-goal brake/leash profile, and reference-point hold with a stick ramp | [SCENARIOS.md](SCENARIOS.md) |
| `svg_ground_control/safe_teleop/` (9 modules), `joy_map.py`, `print_joystick.py`, `xbox_teleop.py` | gamepad teleop: pad detection, latch, monitor, TUI view | [TELEOP.md](TELEOP.md) |
| `launch/teleop.launch.py`, `scripts/svg_teleop.sh`, `teleop.md` (CMU's) | teleop bringup | [TELEOP.md](TELEOP.md) |
| `svg_ground_control/led_controller.py`, `scripts/svg_led_daemon.py`, `voxl_push_led.sh`, `voxl_setup_led.sh`, `airstack_msgs/srv/SetLedColor.srv` | onboard LED strips (green idle / red while the CBF corrects), UDP heartbeat on **47901**; the new `.srv` **forces an `airstack_msgs` rebuild** | [BASESTATION.md](BASESTATION.md) §8 |
| `foxglove/` — `svg-basestation` panel, `svg_basestation.json` layout, `install.py` | the 3D view + command panel that replaces RViz | [BASESTATION.md](BASESTATION.md) |
| `config/teleop_real.yaml`, `teleop_single.yaml`, `squeeze_rc_intruder.yaml`, `cbf_sim.yaml` | new run configs (teleop, C5 RC-intruder, CBF sim) | [SCENARIOS.md](SCENARIOS.md) |
| `scripts/rviz_for_run.py`, `ulog_param_diff.py` | post-flight replay + `.ulg` param diffing | [RUNBOOK.md](RUNBOOK.md) §D |
| 8 new `test/` files (`test_trajectory`, `test_fence_and_position_hold`, `test_feedforward`, `test_formations`, `test_teleop_controllers`, `test_led_packet`, `test_live_speed`, `test_runtime_params`) | unit tests — safe to run anywhere, unlike `functional_*.py` (iron rule 4) | [MILESTONES.md](MILESTONES.md) |
| `robot/docker/Foxglove/` | host mount dir for `/root/.config/Foxglove` (layouts survive container recreation) | [BASESTATION.md](BASESTATION.md) |

Changed, not added — the four that matter:

- **`interface/px4_interface/src/px4_interface.cpp`** — new `trajectory_command` subscriber
  (`:225-234`) + handler (`:333-392`) publishing a full PX4 `TrajectorySetpoint` (position +
  velocity + acceleration) under a new `ControlMode::TRAJECTORY`; a `target_system` parameter
  (`:161-163`, stamped at `:661`); `vehicle_command_ack` logging (`:680-706`). New
  `trajectory_msgs` dep — **C++, so `bws`.**
- **`scripts/voxl_setup_real_drone.sh`** — `px4-` wrapper prefix (`:129-141`), a 60 s
  backgrounded retry loop for the DDS client (`:137-146`), portable awk field matching
  (`:157-183`), and a new `svg-microdds-watchdog` systemd unit (`:193-240`).
- **`common/.tmux.conf`** (`:16-55`) — the `bringup` session auto-splits into a 5-over-3
  pane grid, pane 0.0 the autonomy launch, panes 1–7 idle shells that `sws_after_build`.
- **`svg_ground_control/mocap_bridge.py`** — only an `rclpy.ok()` shutdown guard. The mocap
  path itself is unchanged, so [MOCAP.md](MOCAP.md) still holds end to end.

## 5 · Behaviour changes an old-branch pilot must unlearn

| On the old branch | On this branch | Doc |
|---|---|---|
| Geofence breach ⇒ **freeze-hover for everyone**, always | Two behaviours chosen per config by `fence_behavior`: `"hold_all"` (the old latch) or `"keep_in"` — **nobody stops**, each commanded drone is held inside by a braking velocity envelope. `goal_single.yaml` and `goal_tracking.yaml` now ship `keep_in`; `swarm_real.yaml` ships `hold_all` | [SCENARIOS.md](SCENARIOS.md) |
| One fence | Plus a **separate, smaller teleop fence** (`teleop_fence_min/max`) that only polices the hand-flown drone and must sit INSIDE the geofence or the commander refuses to start | [TELEOP.md](TELEOP.md) |
| `hold_all` latched on commanded drones | `hold_all` also latches on an **airborne external (RC-flown) drone** — fresh odometry and z above `land_complete_altitude_m` is enough (`swarm_commander.py:1493-1507`). An RC pilot can now trip the fence for the whole swarm | [SCENARIOS.md](SCENARIOS.md) |
| Commander published a **bare velocity setpoint** | Commander publishes a **trajectory setpoint — position + velocity + acceleration feedforward** — on `/{name}/fmu/trajectory_command`; PX4 closes the position loop onboard. ~0.1 s tracking lag instead of ~0.7 s, and it holds position when velocity is zero. **`px4_interface` REBUILD required** (`bws`) | [SCENARIOS.md](SCENARIOS.md) |
| `hold` pinned the target to the position **at the instant of the call** | `hold` brakes to a **predicted stop point ahead** (`stop_point()`, `swarm_commander.py:1673-1694`): `v²/(2a) + v/hover_kp` along the current velocity, clamped into the fence. The log says "braking, stops N m ahead". Pinning on the spot overshot ~1.5 m from 6 m/s and flew back | [SCENARIOS.md](SCENARIOS.md) |
| **Keyboard** teleop (click the terminal for focus) | **Gamepad** `safe_teleop` — dead-man latch, pad auto-detection, acceleration ramp. `keyboard_teleop.py` is gone. The container needs the `/dev/input` bind mount | [TELEOP.md](TELEOP.md) |
| **RViz** hand-carry preflight (Fixed Frame `world`) | **Foxglove** + the `svg-basestation` panel 3D view (fence boxes, teleop box amber, per-drone markers). RViz still exists for replay via `scripts/rviz_for_run.py` | [BASESTATION.md](BASESTATION.md) |
| **~7 hand-opened terminals**, one per numbered step | One **8-pane (5-over-3) tmux `bringup` session** inside the container; every pane is already workspace-sourced | [RUNBOOK.md](RUNBOOK.md) §B |
| `target_system` was implicitly 1 | `target_system` is a **parameter** and **must match the drone's `MAV_SYS_ID`**. Mismatch ⇒ PX4 ignores every arm/mode command and sends **no ack at all** | [CONFIG.md](CONFIG.md) |
| Software could see **nothing** about commands | `px4_interface` subscribes `vehicle_command_ack` and logs ACCEPTED (INFO) / DENIED, TEMPORARILY_REJECTED, UNSUPPORTED, FAILED (WARN). ⚠️ **This is still NOT an arming indicator** — it is a per-command verdict. QGC remains the only arming truth | §9 |

## 6 · Re-do list before the first session

Ordered. Everything here was done once on the old snapshot and is void or must be
re-checked. ⏳ = decide at STE.

- [ ] **NatNet SDK** — `natnet_ros2` is in the tree and the workspace **build** needs its SDK
      headers. Our `./mocap.sh` bridge still does **not** use it ([MOCAP.md](MOCAP.md) §3 is
      unchanged), but `bws` fails without it.
      ```bash
      # in the robot container, before the first build
      /root/AirStack/robot/ros_ws/src/perception/natnet_ros2/install_sdk.sh
      ```
- [ ] **Patch 0001** (ZED camera-info init race) — ✅ **already applied** by commit `91376aa`;
      upstream still lacks the fix, so do not "clean" it out. **Patch 0002**
      (swarm_commander logger-severity crash) is **fixed upstream** here — do not re-apply.
      `patches/0003` is unrelated (libmotioncapture).
- [ ] **Robot image** — `robot/docker/Dockerfile.robot` is **byte-identical** to the old
      snapshot (that path's `git diff` against the tag is empty). **No image rebuild needed.**
- [ ] **Full workspace rebuild** — not optional. `px4_interface` is C++ and gained a
      `trajectory_msgs` dependency; `airstack_msgs` gained `SetLedColor.srv`.
      ```bash
      # in the robot container
      bws        # full colcon build, then `sws`
      ```
- [ ] **Recreate the robot-desktop container** — compose gained two mounts
      (`robot-base-docker-compose.yaml:42,51`; `:41` pre-exists): `./Foxglove` → `/root/.config/Foxglove`
      and `/dev/input` → `/dev/input`. A `restart` does **not** add mounts; you need a
      `down`/`up`. (Reminder from TROUBLESHOOTING: container `apt install`s vanish on
      `down`/`up` — re-do any by hand.)
- [ ] **Install the Foxglove panel on the host** — the compose `command` runs
      `svg_ground_control/foxglove/install.py` non-fatally at container start; verify it
      actually landed and import `svg_basestation.json` as the layout.
- [ ] **Re-run `voxl_setup_real_drone.sh` on the drone** — the script changed substantially
      (px4- wrapper, retry loop, watchdog). 🚨 **The script ends with
      `systemctl restart voxl-px4` (`:250`), which on THIS drone (`m0054` / D0012) leaves the
      SLPI flight core dead** — every sensor topic "never published", QGC reports missing
      params. **ALWAYS reboot the drone after provisioning**, never trust the script's own
      verification block.
- [ ] 🚨 ⏳ **Two watchdogs now overlap.** The new script installs `svg-microdds-watchdog`
      (polls `px4-microdds_client status` every 1 s, restarts it with the configured
      `-h/-p/-n`). The lab installed its own `voxl-dds-retry.service` on this drone for the
      same failure. **They must not both run** — two restarters can race and resurrect the
      client against the wrong agent IP. Pick one at STE and disable the other:
      ```bash
      # on the DRONE (ssh root@<DRONE_IP> or adb shell)
      systemctl status svg-microdds-watchdog voxl-dds-retry
      systemctl disable --now <the one you drop>
      ```
- [ ] **Open udp/47901 in ufw** — only if LED strips are used; the VOXL daemons heartbeat to
      the ground PC on that port.
      `sudo ufw allow 47901/udp` on the LAPTOP (host) — see [BASESTATION.md](BASESTATION.md) §8.
- [ ] **Trim the configs** — the shipped values are CMU's STE arena, not ours. At minimum:
      `goal_single.yaml` targets **`drone_2`** (we fly `drone_1`); `swarm_real.yaml` hover z is
      **1.2** not our validated 0.5; `land_speed_mps` differs from our validated **0.6**
      everywhere. Full list in §7.
- [ ] **Verify `target_system` == the drone's `MAV_SYS_ID`** before the first arm attempt —
      ⏳ **read `MAV_SYS_ID` back in QGC before the first arm** — the 2026-09-04 params export says **1**, a 2026-09-18 session note on this airframe says it was set to **2**; whichever it is, `target_systems:=` must match. A silent no-ack is the symptom of getting this wrong.

## 7 · Config value diff table

`AirStack/robot/ros_ws/src/svg_ground_control/config/`. ⚠️ = our September validation no
longer applies to the shipped value.

| File | Key | Old (validated) | New (shipped) | |
|---|---|---|---|---|
| `swarm_real.yaml` | `teleop_drones` / `cbf_exempt_drones` | `"drone_3"` | `""` | drone_3 is now CBF-policed |
| | `hover_positions` z (drone_1 slot) | `0.5` | `1.2` | ⚠️ our low-and-safe height is gone |
| | `fence_behavior` | *(absent — latch implied)* | `"hold_all"` explicit | same behaviour, now stated |
| | `land_speed_mps` | `0.3` (never flown) | `0.3` | ⚠️ 0.3 caused armed-on-ground landings (archive ledger #21) |
| | `led_controller:` block | — | added (brightness 80, port 47901) | new node |
| `swarm_sim.yaml` | `cbf_max_speed_mps` | `1.2` | `2.0` | sim only |
| | `teleop_max_speed_mps` | `1.2` | `2.0` | sim only |
| `goal_tracking.yaml` | `drone_names` | `["drone_1"]` | 3 drones, `"real,real,real"` | ⚠️ needs a trim for single-drone ops |
| | `scenario` | `"goal"` | `"random_goals"` | ⚠️ autonomous random targeting, not hand-sent goals |
| | `scenario_speed_mps` | `0.6` | `10.0` | 🚨 ⚠️ |
| | `cbf_max_speed_mps` | `1.2` | `10.0` | 🚨 ⚠️ |
| | `fence_min`/`max` | `[-2,-2,0]` / `[2,2,2]` | `[-4.5,-5.2,0]` / `[5.5,5.0,3.0]` | 🚨 ⚠️ bigger than our net |
| | `fence_behavior` | *(latch)* | `"keep_in"`, brake `8.0`, gain `2.0` | ⚠️ new behaviour, unflown here |
| | `land_speed_mps` | `0.6` ✅ validated 2026-09-03 | `1.0` | ⚠️ |
| | `takeoff_speed_mps` | *(absent)* | `1.0` | new key |
| `goal_single.yaml` | `drone_names` | `["drone_1"]` | `["drone_2"]` | ⚠️ wrong drone for us |
| | `scenario_speed_mps` | `0.6` | `10.0` | 🚨 ⚠️ |
| | `cbf_max_speed_mps` | `1.2` | `10.0` | 🚨 ⚠️ |
| | `fence_min`/`max` | `±0.7` XY, z `0..2.8` | `[-4.5,-5.2,0]` / `[5.5,4.5,3.0]` | 🚨 ⚠️ |
| | `teleop_fence_enabled` | *(did not exist)* | `true`, `[-3.5,-4.2,0.5]..[4.5,3.5,2.5]` | new inner fence |
| | `land_speed_mps` | `0.6` ✅ validated | `0.8` | ⚠️ |
| | `land_complete_altitude_m` | `0.15` | `0.1` | ⚠️ touchdown detection point moved down |
| `hybrid_squeeze.yaml` | `mocap_bridge` | `via_interface` keys only | `px4_vio_mode: direct`, `px4_vio_frame: enu_to_ned`, `vio_quality: 100` | now matches the other configs |
| **all** | `fence_brake_accel_mps2` | — | `4.0` (`swarm_real`) / `8.0` (goal configs) | new |
| | `fence_keep_in_gain` | — | `1.0` / `2.0` | new |
| | `fence_margin_m` | — | `0.0` | new |
| | `hold_lead_m` | — | `0.2` | new |
| | `takeoff_speed_mps` | — | `0.5`–`1.0` | new |

🚨 **Speed caps of `10.0 m/s` and a ~10 m fence are CMU's STE arena.** Our net is nothing
like that. Trim both before the first powered flight at any site.

## 8 · Old-doc statements that are now wrong

Locations are in the **archived** docs (`git show airstack-starling-max2:<path>`).

| Old doc said (where) | Now |
|---|---|
| "CBF safety filter … clips unsafe **velocity** commands" (archive `README.md:54-59`) | The commander outputs a trajectory setpoint; the CBF clips a velocity that is then sent with position and acceleration alongside it. Rewrite the thin-slice paragraph. |
| 4-loop ladder: "laptop **velocity setpoint** 20 Hz … POSITION loop **bypassed** … we inject **velocity**" (archive `README.md:79-85`) | Wrong at every step: we inject at the **position** level and PX4's POSITION loop is **in use** again, with our velocity and acceleration as feedforward. The whole ladder needs redrawing. |
| Showcase GIF captions "What the software sees — **RViz**" (archive `README.md:15-18`) | The live view is Foxglove. The September GIFs are genuine archive footage — keep them, re-caption as archive. |
| `RUNBOOK` §A T4 "**RViz**" terminal (archive `:49-52`) and §B step 7 "RViz preflight", Fixed Frame `world` fix (archive `:226-241`) | Replaced by the Foxglove hand-carry check — [BASESTATION.md](BASESTATION.md). |
| "One terminal per numbered step … a full session = **~7 terminals**" (archive `RUNBOOK.md:68-78`) | One container + the 8-pane (5-over-3) tmux `bringup` session. The three terminal KINDS table is still correct and worth keeping. |
| C4 "Breach ⇒ **ALL drones freeze-hover**" (archive `RUNBOOK.md:323-326`) | Only under `fence_behavior: "hold_all"`. The goal configs ship `keep_in`, where nothing freezes. |
| Pocket-reference row `` `ros2` / `bws` / `rviz2` `` (archive `RUNBOOK.md:372`) | `rviz2` is no longer part of a session. |
| C7 (archive `RUNBOOK.md:339-347`) | ✅ **still valid** — listed here only so nobody re-checks it. |
| Fence checklist line naming `fence_min`/`fence_max` only (archive `PREFLIGHT.md:7`) | Must now also cover `fence_behavior`, `teleop_fence_min`/`max`, and "teleop fence inside the geofence". |
| "RViz tracking the hand-carried drone (Fixed Frame `world`)" (archive `PREFLIGHT.md:17`) | Foxglove basestation 3D view. |
| "Geofence breach = freeze-hover, still armed" (archive `PREFLIGHT.md:45-46`) | True for `hold_all` only; say which behaviour the loaded config uses. |
| GLOSSARY **Offboard mode** "(we stream velocity)" (archive `:25-27`) | We stream a trajectory setpoint. |
| GLOSSARY **Geofence** "breach freezes the drone in a hover" + **CBF** "clips … velocity" (archive `:55-60`) | Both need the two-behaviour wording; add `hold_all` / `keep_in` / teleop fence as terms. |
| CONFIG `` `fence` in goal_single.yaml `` = tight ±0.7 m (archive `:102`) | Ships `[-4.5,-5.2,0]..[5.5,4.5,3.0]` with `keep_in`. |
| CONFIG `land_speed_mps` **`0.6`** "in goal_single/goal_tracking (validated)" (archive `:100`) | Ships 0.8 / 1.0 / 0.3. Keep the 0.6 finding as the lab's validated value and re-flag the files as needing a trim. |
| CONFIG "`swarm_real.yaml` still 3-drone; trim OPTIONAL" (archive `:129`) | Still 3-drone, but `goal_single.yaml` now points at **`drone_2`** — the trim is no longer optional for single-drone ops. |
| TROUBLESHOOTING RViz rows (archive `:18-19`) | Foxglove equivalents needed. |
| TROUBLESHOOTING "click the teleop terminal for **keyboard focus**" (archive `:45`) | Gamepad now — the equivalent failure is an undetected pad / the dead-man latch not held. |
| TROUBLESHOOTING "phantom `drone_2`/`drone_3` WARNs harmless" (archive `:46`) | Still true for `swarm_real.yaml`, but a `drone_2`-targeted `goal_single.yaml` is a real misconfiguration, not a phantom. |
| TROUBLESHOOTING geofence row (archive `:44`) | Same `hold_all`-only caveat. |
| MILESTONES §3d px4_msgs audit | ⚠️ **Re-audit needed.** The conclusion rests on *which* `TrajectorySetpoint`/`OffboardControlMode` fields are exercised. Acceleration feedforward now populates `acceleration[]` and `yaw`/`yawspeed`, and `VehicleCommandAck` is a newly-subscribed message. The old per-message verdicts do not cover that set. |
| archived MILESTONES §8 (now [MILESTONES.md](MILESTONES.md) §6) shelved fixes | Line numbers are stale. **Fix 1** (`LANDED_SETTLE`): re-check — the touchdown branch moved and `land_complete_altitude_m` is now 0.1 in one config. **Fix 2** (`~/release`): still absent — the design stands. **Fix 3** (yaw): largely **subsumed** — the trajectory output carries absolute yaw (`px4_interface.cpp:371-387`), with an all-zero quaternion meaning "no yaw setpoint → yaw-rate control". The §8 claim "CBF is 3-DOF linear" also predates `564d43e`'s external-velocity reactivity. |

## 9 · Iron rules — what changed

CLAUDE.md now has **8** iron rules (7 = reboot, never `systemctl restart voxl-px4`, after provisioning; 8 = the shipped configs are not ours) and PREFLIGHT.md numbers its bullets to match. Rules **1, 2, 3, 4, 6** keep their wording but are all **unvalidated on this branch** pending
the STE re-test — especially rule 1: the control-authority leak is a property of what PX4
consumes, and we now send a different setpoint type.

**Rule 5 is now PARTLY FALSE.** `px4_interface` subscribes `vehicle_command_ack` and logs
PX4's verdict per command: ACCEPTED at INFO, DENIED / TEMPORARILY_REJECTED / UNSUPPORTED /
FAILED / IN_PROGRESS at WARN (`px4_interface.cpp:680-706`). Two things to read from it, one not:

- A **DENIED** arm is a *PX4 preflight refusal* — real, actionable information we never had.
- **No ack at all** is the signature of `target_system` ≠ `MAV_SYS_ID`: PX4 never saw the
  command (`px4_interface.cpp:682-683`).
- An **ACCEPTED** arm is **not** an arming indicator. `VehicleStatus` is still undecodable on
  this v1.14 drone, nothing in the commander reads `is_armed`, and the arming sequence is
  still time-staged fire-and-forget. **QGC remains the only arming truth.**

Amended rule 5, for [CLAUDE.md](../CLAUDE.md) and [PREFLIGHT.md](PREFLIGHT.md):

> **5.** Read `px4_interface`'s `PX4 ack:` lines to see whether PX4 **accepted** a command
> (and treat *no* ack as `target_system` ≠ `MAV_SYS_ID`) — but an accepted arm is still not
> an armed drone: fly with QGC visible, it is the only arming truth.

## 10 · CMU-side doc bugs found during the survey

CMU's own docs on this branch have errors we hit while surveying it. Each is corrected in
detail in the doc that owns the topic; this table is only an index.

| CMU doc | Topic | Corrections table |
|---|---|---|
| `svg_ground_control/teleop.md` | gamepad layout, launch args, dead-man latch | [TELEOP.md](TELEOP.md) §9 |
| `svg_ground_control/experiment.md` (Parts B/C) | scenarios, fence behaviours, run configs | [SCENARIOS.md](SCENARIOS.md) §9 |
| `svg_ground_control/foxglove/svg-basestation/README.md` | panel install + layout import | [BASESTATION.md](BASESTATION.md) §6 |
| `experiment.md` Part B4 (mocap) | unchanged from the old branch — our corrections still stand | [MOCAP.md](MOCAP.md) §4 |
