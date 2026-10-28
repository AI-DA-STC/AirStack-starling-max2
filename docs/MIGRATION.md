# MIGRATION — from `daniel/diffaero_ground_control` to `yikuan/SVG_ground_control` (2026-10-07) → `_dev` @ `b21d28c` (2026-10-20, §11)

> **Who this is for:** anyone who flew this rig on 2026-09-01→03, or who reads the archived
> docs and wonders why they no longer match the tree. It is the bridge between the two
> AirStack snapshots: what changed, what must be re-done, which old statements are now wrong,
> and where the old material lives. **This is NOT a runbook** — read it once, then work from
> [RUNBOOK.md](RUNBOOK.md), [PREFLIGHT.md](PREFLIGHT.md) and the new
> [MILESTONES.md](MILESTONES.md) index. Delete it once HTX-R2 M2–M7 are re-earned.

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
2026-10-07 as commit `91376aa`; **bumped 2026-10-20 to the dev branch `b21d28c` — §11**) **kept** the CBF and built the ground-station side out
instead — gamepad teleop, a geofence braking envelope, trajectory output with acceleration
feedforward, onboard LEDs, the Foxglove SVG Basestation panel. Four commits past the ancestor:

| | |
|---|---|
| `564d43e` | CBF external-velocity reactivity, formation profiles, C5 RC-intruder config |
| `60a90bf` | Onboard LED strips, `px4_interface` `target_system`, 5-over-3 (8-pane) tmux bringup |
| `b9f4107` | gitignore local Micro-XRCE-DDS-Agent clone and `led_ws` reference workspace |
| `cf719f0` | svg_ground_control: teleop, trajectory output, fence envelope, CBF feedforward, foxglove basestation (dev 2026-08-24..09-27) |
| dev `b21d28c` | **+54 commits** on `yikuan/SVG_ground_control_dev` past `cf719f0` (six-gain panel dropdown, rosbag switch, `goal_sequence` / `figure_eight` scenarios, teleop speed sync) — §11 |

**Consequence for us:** September's flights were validated on a branch *without* half of this
and *with* a different commander output. The CBF our docs describe is back (and now reacts to
external velocities); the diffaero machinery our docs never used is gone. Flight validation
restarts — see [MILESTONES.md](MILESTONES.md) "Where each project is".

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

⚠️ **The old test ledger #1–#21 is NOT carried over.** The new [record/LEDGER.md](record/LEDGER.md) table 1 restarts
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
| 8 new `test/` files (`test_trajectory`, `test_fence_and_position_hold`, `test_feedforward`, `test_formations`, `test_teleop_controllers`, `test_led_packet`, `test_live_speed`, `test_runtime_params`) | unit tests — safe to run anywhere, unlike `functional_*.py` (iron rule 4) | [record/LEDGER.md](record/LEDGER.md) |
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
| `hold_all` latched on commanded drones | `hold_all` also latches on an **airborne external (RC-flown) drone** — fresh odometry and z above `land_complete_altitude_m` is enough (`SwarmCommander.enforce_fence`). An RC pilot can now trip the fence for the whole swarm | [SCENARIOS.md](SCENARIOS.md) |
| Commander published a **bare velocity setpoint** | Commander publishes a **trajectory setpoint — position + velocity + acceleration feedforward** — on `/{name}/fmu/trajectory_command`; PX4 closes the position loop onboard. ~0.1 s tracking lag instead of ~0.7 s, and it holds position when velocity is zero. **`px4_interface` REBUILD required** (`bws`) | [SCENARIOS.md](SCENARIOS.md) |
| `hold` pinned the target to the position **at the instant of the call** | `hold` brakes to a **predicted stop point ahead** (`SwarmCommander.stop_point()`, called from `handle_hold`): `v²/(2a) + v/hover_kp` along the current velocity, clamped into the fence. The log says "braking, stops N m ahead". Pinning on the spot overshot ~1.5 m from 6 m/s and flew back | [SCENARIOS.md](SCENARIOS.md) |
| **Keyboard** teleop (click the terminal for focus) | **Gamepad** `safe_teleop` — dead-man latch, pad auto-detection, acceleration ramp. `keyboard_teleop.py` is gone. The container needs the `/dev/input` bind mount | [TELEOP.md](TELEOP.md) |
| **RViz** hand-carry preflight (Fixed Frame `world`) | **Foxglove** + the `svg-basestation` panel 3D view (fence boxes, teleop box amber, per-drone markers). RViz still exists for replay via `scripts/rviz_for_run.py` | [BASESTATION.md](BASESTATION.md) |
| **~7 hand-opened terminals**, one per numbered step | One **8-pane (5-over-3) tmux `bringup` session** inside the container; every pane is already workspace-sourced | [RUNBOOK.md](RUNBOOK.md) §B |
| `target_system` was implicitly 1 | `target_system` is a **parameter** and **must match the drone's `MAV_SYS_ID`**. Mismatch ⇒ PX4 ignores every arm/mode command and sends **no ack at all** | [CONFIG.md](CONFIG.md) |
| Software could see **nothing** about commands | `px4_interface` subscribes `vehicle_command_ack` and logs ACCEPTED (INFO) / DENIED, TEMPORARILY_REJECTED, UNSUPPORTED, FAILED (WARN). ⚠️ **This is still NOT an arming indicator** — it is a per-command verdict. QGC remains the only arming truth | §9 |

## 6 · Re-do list before the first session

Ordered. Everything here was done once on the old snapshot and is void or must be
re-checked. ⏳ = decide at STE. ✅ = done, with the date and the [LEDGER](record/LEDGER.md) row.
**Post-bump (10-20) and sim re-dos are NOT here** → §11 and the next issue in Linear.

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
- [x] **Full workspace rebuild** — ✅ 2026-10-20 (full `bws`, then `bws --packages-select
      svg_ground_control` after the bump; pytest 185/185 — ledger #7/#8). Not optional on a
      fresh machine: `px4_interface` is C++ and gained a `trajectory_msgs` dependency;
      `airstack_msgs` gained `SetLedColor.srv`.
      ```bash
      # in the robot container
      bws        # full colcon build, then `sws`
      ```
- [ ] **Recreate the robot-desktop container** — compose gained two mounts
      (`robot-base-docker-compose.yaml:42,51`; `:41` pre-exists): `./Foxglove` → `/root/.config/Foxglove`
      and `/dev/input` → `/dev/input`. A `restart` does **not** add mounts; you need a
      `down`/`up`. (Reminder from TROUBLESHOOTING: container `apt install`s vanish on
      `down`/`up` — re-do any by hand.)
- [x] **Install the Foxglove panel on the host** — ✅ 2026-10-20 (`install.py` re-run after
      the bump, Studio restarted, six-gain dropdown visible — ledger #7). The compose `command`
      runs `svg_ground_control/foxglove/install.py` non-fatally at container start; after any
      bump re-run it by hand and import `svg_basestation.json` as the layout.
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
      `goal_single.yaml` targeted **`drone_2`** at `cf719f0` (at `b21d28c`: `drone_1` again — but
      still CBF-exempt, 10 m/s, `land_speed_mps` 0.8); `swarm_real.yaml` hover z is
      **1.2** not our validated 0.5; `land_speed_mps` differs from our validated **0.6**
      everywhere. Full list in §7; what we fly instead: the `_ours` files ([CONFIG.md](CONFIG.md)).
- [ ] **Verify `target_system` == the drone's `MAV_SYS_ID`** before the first arm attempt —
      ⏳ **read `MAV_SYS_ID` back in QGC before the first arm** — the 2026-09-04 params export says **1**, a 2026-09-18 session note on this airframe says it was set to **2**; whichever it is, `target_systems:=` must match. A silent no-ack is the symptom of getting this wrong.

## 7 · Config value diff table

`AirStack/robot/ros_ws/src/svg_ground_control/config/`. ⚠️ = our September validation no
longer applies to the shipped value.

*Shipped values as read at `cf719f0` (2026-10-07) — kept as history. At `b21d28c` (2026-10-20):
`goal_single` → `drone_1`, `goal_tracking` → `goal` ([CONFIG.md](CONFIG.md)); the other rows are unchanged.*

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
| | `scenario` | `"goal"` | `"random_goals"` | ⚠️ autonomous random targeting, not hand-sent goals — at `b21d28c`: back to `"goal"` (CONFIG.md) |
| | `scenario_speed_mps` | `0.6` | `10.0` | 🚨 ⚠️ |
| | `cbf_max_speed_mps` | `1.2` | `10.0` | 🚨 ⚠️ |
| | `fence_min`/`max` | `[-2,-2,0]` / `[2,2,2]` | `[-4.5,-5.2,0]` / `[5.5,5.0,3.0]` | 🚨 ⚠️ bigger than our net |
| | `fence_behavior` | *(latch)* | `"keep_in"`, brake `8.0`, gain `2.0` | ⚠️ new behaviour, unflown here |
| | `land_speed_mps` | `0.6` ✅ validated 2026-09-03 | `1.0` | ⚠️ |
| | `takeoff_speed_mps` | *(absent)* | `1.0` | new key |
| `goal_single.yaml` | `drone_names` | `["drone_1"]` | `["drone_2"]` | ⚠️ wrong drone for us — at `b21d28c`: `["drone_1"]` again, still CBF-exempt (CONFIG.md) |
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

This table is **CMU-old vs CMU-shipped only.** The values we actually fly (`swarm_real_ours.yaml`,
`goal_single_ours.yaml`, our `cbf_sim.yaml`) are in [CONFIG.md](CONFIG.md) "Ground-side flight
parameters".

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
| "RViz tracking the hand-carried drone (Fixed Frame `world`)" (archive `PREFLIGHT.md:17`) | The panel's (Foxglove SVG Basestation) 3D view. |
| "Geofence breach = freeze-hover, still armed" (archive `PREFLIGHT.md:45-46`) | True for `hold_all` only; say which behaviour the loaded config uses. |
| GLOSSARY **Offboard mode** "(we stream velocity)" (archive `:25-27`) | We stream a trajectory setpoint. |
| GLOSSARY **Geofence** "breach freezes the drone in a hover" + **CBF** "clips … velocity" (archive `:55-60`) | Both need the two-behaviour wording; add `hold_all` / `keep_in` / teleop fence as terms. |
| CONFIG `` `fence` in goal_single.yaml `` = tight ±0.7 m (archive `:102`) | Ships `[-4.5,-5.2,0]..[5.5,4.5,3.0]` with `keep_in`. |
| CONFIG `land_speed_mps` **`0.6`** "in goal_single/goal_tracking (validated)" (archive `:100`) | Ships 0.8 / 1.0 / 0.3. Keep the 0.6 finding as the lab's validated value and re-flag the files as needing a trim. |
| CONFIG "`swarm_real.yaml` still 3-drone; trim OPTIONAL" (archive `:129`) | Still 3-drone, and at `cf719f0` `goal_single.yaml` pointed at **`drone_2`** — the trim is no longer optional for single-drone ops (at `b21d28c`: `goal_single` → `drone_1`, `goal_tracking` → `goal` — CONFIG.md; we fly the `_ours` files regardless). |
| TROUBLESHOOTING RViz rows (archive `:18-19`) | Foxglove equivalents needed. |
| TROUBLESHOOTING "click the teleop terminal for **keyboard focus**" (archive `:45`) | Gamepad now — the equivalent failure is an undetected pad / the dead-man latch not held. |
| TROUBLESHOOTING "phantom `drone_2`/`drone_3` WARNs harmless" (archive `:46`) | Still true for `swarm_real.yaml`, but a `drone_2`-targeted `goal_single.yaml` (as at `cf719f0`) is a real misconfiguration, not a phantom (at `b21d28c`: `goal_single` → `drone_1` — CONFIG.md). |
| TROUBLESHOOTING geofence row (archive `:44`) | Same `hold_all`-only caveat. |
| [PX4_MSGS_AUDIT.md](PX4_MSGS_AUDIT.md) px4_msgs audit | ⚠️ **Re-audit needed.** The conclusion rests on *which* `TrajectorySetpoint`/`OffboardControlMode` fields are exercised. Acceleration feedforward now populates `acceleration[]` and `yaw`/`yawspeed`, and `VehicleCommandAck` is a newly-subscribed message. The old per-message verdicts do not cover that set. |
| archived MILESTONES §8 (now [record/LEDGER.md](record/LEDGER.md) note under table 1) shelved fixes | Line numbers are stale. **Fix 1** (`LANDED_SETTLE`): **implemented 2026-10-19/10-20** as `land_settle_s` + the disarm retry → [record/LEDGER.md](record/LEDGER.md) note under table 1 (real `_ours` configs keep 0.0). **Fix 2** (`~/release`): still absent — the design stands. **Fix 3** (yaw): largely **subsumed** — the trajectory output carries an absolute yaw (details: [projects/HTX-R2.md](projects/HTX-R2.md) "Carried over"). The old "CBF is 3-DOF linear" claim predates `564d43e` |

## 9 · Iron rules — what changed

CLAUDE.md now has **9** iron rules (7 = reboot, never `systemctl restart voxl-px4`, after provisioning; 8 = the shipped configs are not ours; 9, added 2026-10-20 = sim-only values never go to the drone) and PREFLIGHT.md numbers its bullets to match. Rules **1, 2, 3, 4, 6** keep their wording but are all **unvalidated on this branch** pending
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

## 11 · 2026-10-20 — snapshot bumped to `yikuan/SVG_ground_control_dev` @ `b21d28c`

**Why.** CMU keeps two branches (their `.agents/skills/svg-release-branches` skill, now in the
snapshot): daily work on **`yikuan/SVG_ground_control_dev`**, releases cut to
`yikuan/SVG_ground_control` as ONE squash commit per verified batch, never merged. Our 10-07
snapshot `cf719f0` was the 2026-09-27 release. The Foxglove gain dropdown with goal accel /
settle / teleop vmax that the lab saw at the CMU demo exists only on dev (merged from
`cindy/svg_foxglove` on 09-28) and depends on commander + teleop changes there, so the panel
could not be ported alone. User decision 2026-10-20: take dev.

**How.** `git diff --binary cf719f0 b21d28c` (54 commits; 26 files, +3,699/−278, all inside
`robot/ros_ws/src/svg_ground_control/` except `AGENTS.md` and the new skill) applied with
`git apply --directory=AirStack` onto the 10-07 snapshot. Clean apply, no conflicts: dev does
not touch `simulation/` (our whole Starling sim model) and its commander hunks do not overlap
our `land_settle_s` fix. No container rebuild (the three new deps `rcl_interfaces`, `ros2bag`,
`rosbag2_storage_mcap` were already in the image); `bws --packages-select svg_ground_control`
for the new `bag_recorder` entry point and config symlinks; panel re-installed with
`python3 …/foxglove/install.py` (normally runs at container start) and Studio restarted.
Tests 181/181. Reversible: one commit, `git revert`.

**What changed (dev `README.md` "Since the 2026-09-27 release" + our diff):**

| Area | Delta | Our doc |
|---|---|---|
| Foxglove panel | gain dropdown → 6 params (+ `teleop_max_speed_mps` with pad mirror, `goal_accel_mps2`, `goal_settle_s`); **Rosbag switch**; Goal card gets an **agent picker**, the Agents roster and Wiring card are gone; Teleop · Sticks card beside the battery card while `safe_teleop` runs; `view` gains `teleop`; cards stack in one column | [BASESTATION.md](BASESTATION.md) §3.4, §3.7, §3.12, §5 |
| Commander | status snapshot gains a `tuning` block (`teleop_max_speed_mps`, `goal_accel_mps2`, `goal_settle_s`, `scenario_speed_mps`); `goal_settle_s` may be 0 (`NON_NEGATIVE_PARAMS`); `sequence_*` params + `/svg/sequence_command`; pushes/accepts the teleop speed sync | [CONFIG.md](CONFIG.md) |
| Scenarios | `GoalSequenceScenario` (scripted crossing goal sets), `FigureEightScenario` (collision-negligent pair + intruder), both with `path` markers | [SCENARIOS.md](SCENARIOS.md) §4 |
| Teleop | `safe_teleop` `max_speed_mps` is live and kept equal to the commander's `teleop_max_speed_mps` both ways (`sync_max_speed`, `commander_status_topic`, `commander_ns`) | [TELEOP.md](TELEOP.md) |
| Launch | `use_bag_recorder` (true), `record_bag`, `bag_dir`, `bag_prefix`, `bag_include_hidden`; `bag_recorder` node always started | [RUNBOOK.md](RUNBOOK.md) §A |
| Configs | new `goal_sequence.yaml`, `figure_eight_rc_intruder.yaml`; one-line touches to `goal_single`, `goal_tracking`, `squeeze_rc_intruder`, `swarm_sim`, `teleop_real`, `teleop_single` (not our `_ours` files) | [CONFIG.md](CONFIG.md) |
| Docs | `experiment.md` C2–C7 (C3 goal sequence, C7 figure-eight; squeeze moved to C4–C6), "Recording rosbags"; panel README; `teleop.md` | — |
| Tests | +37 (`test_safe_teleop_sync.py`, sequence/figure-eight rollouts, runtime params) | — |

**Unchanged by the bump:** everything under `simulation/` (Starling model, airframe, tools),
`px4_interface`, `mocap_bridge`, the LED daemon, the fence and CBF maths, our `_ours.yaml`
configs, `cbf_sim.yaml` (dev did not touch it), `land_settle_s`.

**Re-do after the bump.** Our own sim changes made right after the bump also invalidate the
10-19 sim results, so the re-runs are forced twice over:

- asset rebuilt, cull < 2 mm instead of decimation (`7032af4`, ledger #9);
- sim airframe: rate gains ×0.5 + gyro filters 80/40 (`2a70731`, ledger #10),
  `LNDMC_ROT_MAX` 300 (`7032af4`), MPC speed/accel limits = the real drone's (`d739a73`,
  ledger #12);
- `cbf_sim.yaml` speeds 2.0 / 4.0 / 6.0 (`d739a73`);
- MAVROS respawn in the sim interfaces launch (`6191d8c`, ledger #11).

Status 2026-10-21: the **fresh-launch and landing-end-to-end checks are closed** by ledger #13
(new asset loaded, PhysX clean, three clean landings with DISARM accepted first time). Still
⏳: the sim re-runs and first-use checks — the ordered list lives **only** in
the next issue in Linear (snapshot: [MILESTONES.md](MILESTONES.md) "Where each project is"; this page keeps no copy).
Everything real-drone stays ⏳ STE as before.

## 12 · Moved from README: showcase, milestones in brief, historical appendix

> Moved verbatim from the front-page README on 2026-10-21 (the README is now a 400-word front
> door). Everything below describes the PREVIOUS branch's results and history.

## ✈️ Showcase — autonomous waypoint flight, validated 2026-09-03 (previous branch)

The drone below is flying itself. No pilot is touching sticks: ceiling cameras track it,
the ground laptop fuses that into PX4's state estimator, and the swarm commander flies it
through operator-published waypoints — takeoff, goal tracking, geofence, landing, and
auto-disarm all under software control (RC kill switch armed in hand throughout).

| Drone's-eye view (12× speed) | What the software saw — RViz, previous branch (4× speed) |
|---|---|
| <img src="../assets/starling_goal_tracking_drone_8x.gif" alt="Starling Max 2 flying commanded waypoints in the hangar" width="420"> | <img src="../assets/starling_goal_tracking_rviz_4x.gif" alt="RViz view of the same goal-tracking flight" width="420"> |
| [full video](../videos/Starling_goal_tracking_drone.mp4) | [full video](../videos/Starling_goal_tracking_RVIZ.mp4) |

*(Recorded on the previous branch. The operator view is now the Foxglove Basestation —
[BASESTATION.md](BASESTATION.md); RViz remains available as a fallback.)*

**What's been achieved so far** (details: [record/LEDGER.md](record/LEDGER.md)):

- **2026-09-01 — first offboard flight** (previous branch): takeoff + hover fully under
  AirStack command, position from OptiTrack mocap (no GPS, no VIO), RC kill switch verified
  in flight.
- **2026-09-03 — waypoint flights** (previous branch): runtime goals published over ROS 2
  (single goal + a multi-goal square, 2 laps), **in-flight geofence** validated, reliable
  landing auto-disarm.
- **2026-10-07 — moved to `yikuan/SVG_ground_control`** (bumped to `_dev @ b21d28c`
  2026-10-20): the mocap chain, drone provisioning and network setup carry over unchanged;
  the flight software is re-validated from the start ([MILESTONES.md](MILESTONES.md) "Where each project is").
- **2026-10-21 — random goals under the CBF, in sim (Starling 2 Max model):**
  [videos/random_CBF_sim_edited.mp4](../videos/random_CBF_sim_edited.mp4) — three simulated
  Starlings cross paths at 2.0 m/s and the CBF alone keeps them apart (`cbf_sim.yaml`: cap
  4.0 m/s, r 0.55 m, α 2.5; a 47 s excerpt of a 3.5 min run). **Sim only — real re-check
  pending** (M3+).
- The full toolchain is in this repo: mocap bridge ([MOCAP.md](MOCAP.md)), session
  runbook ([RUNBOOK.md](RUNBOOK.md) §B/§C), drone parameter set
  ([`starling_1_indoor_params.params`](../starling_1_indoor_params.params)), and every lesson
  learned along the way.

> **New here? Read in this order:**
>
> - **Newcomer** → the one-page primer (next section) → run the sim ([RUNBOOK.md](RUNBOOK.md) §A)
>   → [BASESTATION.md](BASESTATION.md) (what you are looking at) → [MOCAP.md](MOCAP.md)
>   → [PREFLIGHT.md](PREFLIGHT.md) → shadow a real session ([RUNBOOK.md](RUNBOOK.md) §B)
>   with a trained person.
> - **Flew the old branch** → [MIGRATION.md](MIGRATION.md) first.
> - **Flying today** → [RUNBOOK.md](RUNBOOK.md)
> - **Hand-flying with the gamepad** → [TELEOP.md](TELEOP.md)
> - **CBF, formations, squeeze, random goals** → [SCENARIOS.md](SCENARIOS.md)
> - **Setting up a new drone** → [DRONE_SETUP.md](DRONE_SETUP.md)
> - **At the Motive PC** → [MOCAP.md](MOCAP.md) §6
> - **Something's broken** → [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
> - **Starting an AI-assisted session** → [CLAUDE.md](../CLAUDE.md)
> - **Any unfamiliar term** → [GLOSSARY.md](GLOSSARY.md)


## The milestones, in brief

The ladder restarts at **M0** on this branch. Each milestone adds and proves **one new
piece** before the next builds on it — so when something fails, we always know which piece
broke. Simulation proves the software, props-off stages prove the connections, hand-carry
proves the position tracking, and only then do propellers spin.

| # | Milestone | One-line goal | Status |
|---|---|---|---|
| 0 | Bring-up on the new branch | Build, containers, Foxglove panel — three sim drones visible in the Basestation | ⏳ STE |
| 1 | Sim rehearsal | CBF crossing, braking fence, gamepad, formations, random goals in Isaac Sim; pytest green | ⏳ partly — Starling model, CBF crossing, random goals + landing pass in sim; re-runs pending — the one to-do list is the next issue in Linear (snapshot: [MILESTONES.md](MILESTONES.md) "Where each project is") |
| 2 | Drone provisioning + hand-carry | New provisioning script + watchdog; `target_system`; Basestation tracks the carried drone; EKF2 fusing | ⏳ STE |
| 3 | First flight | Takeoff, hover, land under the trajectory output; command ACKs seen; iron rules re-verified | ⏳ STE |
| 4 | Goal flights + braking fence | Acceleration-limited goal legs; keep-in wall braking measured; live gains | ⏳ STE |
| 5 | Gamepad teleop, real | Yaw sign verified; teleop fence; release-to-hold | ⏳ STE |
| 6 | LED strips (optional) | Green default, red on CBF; ESC arm LEDs muted — acknowledged | ⏳ STE |
| 7 | Multi-drone | Formations, random-goal CBF test, RC-intruder squeeze | ⏳ blocked — one Starling |

Live status: Linear; snapshot in [MILESTONES.md](MILESTONES.md). The previous branch's ladder (M1–M5 validated 2026-07-20→08-28, M6 flown
2026-09-01→03 without final sign-off) is on the archive tag.

**Important context on the statuses:** CMU built AND flight-tested all of this on their own
three Starlings — our project is **replication and validation**, not development. A code
audit (2026-10-07, the appendix below) confirmed every mechanism for
M0–M7 exists in the `AirStack/` code. The things NOT in code (manual, by design) are: clock
sync between machines, the OptiTrack/Motive settings, PX4-side parameters set through
QGroundControl, and which physical gamepad the lab owns.

## Milestone 1 at a glance (previous branch, 2026-07-20)

![Takeoff and land](../assets/takeoff_and_land.gif)

*Three simulated PX4 drones (SITL — real autopilot firmware, simulated aircraft) under the
commander: `takeoff` → hover scenario → `land` (RViz view, 2× speed). The same
rehearsal on this branch is M1, watched in the Basestation instead.*


## Appendix — historical reference

Superseded or reference-only material, kept for the record. Nothing here is needed for a
normal session.

<details>
<summary><strong>Historical network topology (pre-2026-08-27)</strong> — the two-router <code>Mocap_QCGroundControl</code> setup</summary>

*(The diagram that used to illustrate this section has been retired. The current network
diagram lives in the [Flight-lab network architecture](ARCHITECTURE.md#flight-lab-network-architecture)
section above.)*

Rough pipeline, mocap to motors: the **8 OptiTrack cameras** feed (via the OptiTrack mocap
router) the **Motive workstation** — the mocap server, capable of up to 240 Hz (ours streams
at 50 Hz). Motive pushes the **NatNet pose stream over wired LAN** through the hangar's
unmanaged Ethernet switch to the **D-Link router**, which broadcasts the 5 GHz Wi-Fi SSID
**`Mocap_QCGroundControl`**. The **ground-control workstation** (the AirStack / Crazyswarm2
laptop) and the **drone** both live on that router's network — so laptop ↔ Starling Max 2 is
two-way discovery on the same subnet (uXRCE-DDS agent link, QGC MAVLink). Crazyflies are the
exception: they are commanded over a **Crazyradio USB dongle** rather than Wi-Fi, with a
software E-stop via Crazyswarm2; a **hardware E-stop remote** (safety pilot) covers drones
that support it. Two footnotes from the diagram worth remembering: the main office router and
the D-Link router are **different subnets**, and IPs are assigned **by router port, not by
machine**.

This was the lab topology as of 2026-08-11; since **2026-08-27** the lab uses the AI.R STC
hangar wired LAN instead (see the network-architecture section above, and
[CONFIG.md](CONFIG.md) for current values).

More detail on the D-Link router itself (configuration, ports, access):
[AI-DA-STC/Mocap_QC_Ground_Control_Router_Information](https://github.com/AI-DA-STC/Mocap_QC_Ground_Control_Router_Information).

</details>

<details>
<summary><strong>Patches — bug fixes we made to AirStack (backup copies)</strong> — what lives in <code>patches/</code> and when you'd need it</summary>

While getting AirStack working on the previous branch, we found and fixed **two bugs in
CMU's code**. On this branch one is still needed and one has been fixed upstream:

| Patch file | Bug it fixes | Symptom without the fix | Status on `yikuan/SVG_ground_control_dev` |
|---|---|---|---|
| `0001-zed-camera-info-init-race.patch` | Camera startup race in the Isaac Sim Pegasus extension | The drone's right stereo camera randomly never publishes → navigation flies "blind" and becomes erratic | **Still needed** — upstream lacks it; **applied in `AirStack/`** (2026-10-07). Only matters for `ENABLE_CAMERA=true` runs |
| `0002-swarm-commander-logger-severity-crash.patch` | Logging crash in the commander (`swarm_commander`) | The commander process **dies mid-flight** the first time any drone command fails | **Fixed upstream** (same fix: the `report` done-callback of the service-call helper in `swarm_commander.py` now logs `info` and `error` on separate call sites). Do NOT apply; kept for the archive branch |
| `0003-libmotioncapture-natnet-4.2-modeldef-segfault.patch` | NatNet 4.2 modeldef segfault in libmotioncapture | the laptop mocap bridge crashes on connect | Unchanged — `./mocap.sh setup` applies it |

The `patches/` folder holds a **backup copy of each fix** as a small text file (a git
"patch"). Anyone who downloads AirStack fresh from CMU's GitHub **gets bug 1 again**.

**Reference: using CMU's repo directly (advanced — not the normal install).**
Only for when you want CMU's **newer** commits than our snapshot:

```bash
# clone CMU's branch + its submodules:
git clone -b yikuan/SVG_ground_control_dev https://github.com/castacks/AirStack.git ~/AirStack-cmu
cd ~/AirStack-cmu
git submodule update --init     # (NOT --recurse-submodules — other branches reference
                                #  private repos and the recursive download fails)

# re-apply our remaining fix on top (assumes this repo is cloned at ~/AirStack-starling-max2):
git -C simulation/isaac-sim/extensions/PegasusSimulator apply ~/AirStack-starling-max2/patches/0001-zed-camera-info-init-race.patch \
  && echo "fix applied" || echo "PATCH FAILED — CMU may have merged it, or changed the surrounding code"
# the NatNet SDK binary download, as in Step 1:
robot/ros_ws/src/perception/natnet_ros2/install_sdk.sh
```

**Reference: how a patch file is made.**

```bash
git diff > my-fix.patch    # save your edits as a patch (run in the repo you edited)
git apply my-fix.patch     # replay them onto another copy of the same code
```

Fix 1 was made inside the PegasusSimulator submodule folder.

**Lifecycle:** delete `0001` once CMU merges it (it is on their `fix/camera-init` branch
awaiting review); `0002` is retired on this branch.

</details>


## Appendix — code-readiness audit of the `cf719f0` snapshot (moved from the old MILESTONES.md)

> **2026-10-20:** the audit below was done on `cf719f0`. The bump to `b21d28c` changed
> `swarm_commander.py` (+180: `tuning` status block, `sequence_*`, teleop-speed sync),
> `scenarios.py` (+356: `GoalSequenceScenario`, `FigureEightScenario`), `teleop_node.py`
> (+198: `sync_max_speed`), the launch file (bag recorder args) and the panel. Findings below
> are unchanged unless marked; the new code is **unaudited** (⏳ STE) — §11.
> Line numbers in this table are those of `cf719f0`; in `swarm_commander.py` they are stale
> after the bump — find the named function instead.
>
> **Our own code edits since the audit** (not CMU's, all listed in `AirStack/README.md`
> "Ours vs CMU"): `swarm_commander.py` `landing_done()` (settle, 10-19) and
> `land_disarm_step()` (disarm retry, 10-20) + `test/test_landing_settle.py`;
> `interface_bringup/launch/mavros_px4.launch.xml` (mavros respawn, sim-only, 10-20); the
> sim airframe's 10-20 parameters (rate gains ×0.5, `LNDMC_ROT_MAX` 300, MPC limits = real).

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
| **Starling 2 Max sim model** (ours, 2026-10-19, updated 10-20) | sim-only — the parts are listed right below this table |
| **MAVROS respawn** (ours, 2026-10-20, sim-only) | `robot/ros_ws/src/interface/interface_bringup/launch/mavros_px4.launch.xml` — `mavros_node` declared with `respawn="true"`, `respawn_delay="2.0"`; real drones use `px4_interface` and never load this file |

Parts of the Starling 2 Max sim model (all under `AirStack/simulation/isaac-sim/` or the
vendored Pegasus extension; values in [CONFIG.md](CONFIG.md) "Sim airframe", which is
authoritative):

- asset `assets/robots/starling2max.usd` — CMU's sys-ID masses/inertia; body mesh culled of
  parts < 2 mm, no decimation (10-20 rebuild, [LEDGER](record/LEDGER.md) #9);
- Pegasus `logic/vehicles/multirotors/starling2max.py` + `registry.py` — the vehicle config,
  picked by USD file name in `OgnPegasusMultirotorNodeBase.create_multirotor`;
- Pegasus `logic/thrusters/lagged_quadratic_thrust_curve.py` — motor-lag capability, default
  0 (off);
- PX4 airframe `px4/airframes/10090_pegasus_starling2max`, bind-mounted into PX4's ROMFS
  source dir by `docker/docker-compose.yaml` — the real drone's attitude/position gains; rate
  gains ×0.5 + gyro filters 80/40 (sim-only, [LEDGER](record/LEDGER.md) #10); `LNDMC_ROT_MAX` 300 (sim-only,
  [LEDGER](record/LEDGER.md) #9); MPC speed/accel limits = the real drone's ([LEDGER](record/LEDGER.md) #12);
- `launch_scripts/launch_env.py` + `svg_multi_drone_single_domain.py` — `DRONE_USD`,
  `PX4_VEHICLE_MODEL` env vars;
- unit tests in Pegasus `tests/unit/` + `tools/test_launch_env.py`; test scripts
  `tools/sim_hover_step_test.sh`, `tools/sim_cbf_crossing_test.sh`.

**Genuinely NOT in code (manual, by design):** machine clock sync; PX4 EKF2 external-vision
parameters (the `.params` file via QGC); PX4 failsafes and the RC kill switch (QGC);
Motive-side configuration; which physical gamepad the lab owns (identify with `joy_map`,
record in [CONFIG.md](CONFIG.md)).

**Known defects on arrival** (found in the 2026-10-07 code survey — none block M0–M3, all
must be remembered; details in the corrections tables of the linked docs):

| Defect | Effect | Where documented |
|---|---|---|
| `goal_tracking.yaml` ships `scenario: random_goals` (at `cf719f0`) | goal / speed / formation commands were **silently ignored**; CMU's C2 recipe did nothing — resolved upstream at b21d28c (goal / drone_1); remaining: 10 m/s, exempt drone_1 | [SCENARIOS.md](SCENARIOS.md) §9 |
| `goal_single.yaml` targets `drone_2`, not `drone_1` (at `cf719f0`) | commander waited for a drone we don't have — resolved upstream at b21d28c (goal / drone_1); remaining: 10 m/s, exempt drone_1 | [MIGRATION.md](MIGRATION.md) §6 |
| CMU `teleop.md` sign table says `left_sign = -1.0` | code has `+1.0` and records that `-1.0` flew the wrong way on the bench — **trust the code** | [TELEOP.md](TELEOP.md) §9 |
| Two CBF-exempt / external drones get **no** mutual protection | pairs with no movable drone are pruned from the solve | [SCENARIOS.md](SCENARIOS.md) §2 |
| `random_goals` samples goals with no separation | CMU bag: 100 of 221 legs had a drone within 1.5 m of a goal; one arrival took 68 s | [SCENARIOS.md](SCENARIOS.md) §7 |
| Patch 0001 (ZED camera-info race) absent upstream | re-applied in our snapshot; re-apply on any fresh CMU clone | `AirStack/README.md` |
| Stale `foxglove/svg-basestation/dist/nvm.js` | copied into every panel install; unused, harmless | [BASESTATION.md](BASESTATION.md) §9 |

### Upstream candidates (found 2026-10-07, not ours to fix)

- `random_goals` samples goals with no separation from other drones (deadlock on a goal);
- `goal_single.yaml` / `goal_tracking.yaml` shipped values (drone_2, `random_goals`, 10 m/s)
  that contradict CMU's own `experiment.md` recipes — resolved upstream at b21d28c (goal / drone_1); remaining: 10 m/s, exempt drone_1;
- `svg_teleop.sh real` gates on `natnet_ros2` — our rig uses `./mocap.sh` (the gate on
  `/drone_1/pose` may still pass; untested);
- `svg-microdds-watchdog` duplicates our `voxl-dds-retry.service`.
