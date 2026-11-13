# TELEOP — flying `drone_1` by hand: gamepad, or keyboard in sim

> **Who this is for:** anyone in the AI.R / STC lab who wants to hand-fly the Starling with a
> game controller (real drone) or the keyboard (sim only, §3b) instead of publishing waypoints. No robotics background needed.
> **Read first:** [GLOSSARY.md](GLOSSARY.md) for the words, [RUNBOOK.md](RUNBOOK.md) §A (sim) or
> §B (real drone) for the bring-up this sits on top of. "The commander" = the `swarm_commander`
> node; "the panel" = the Foxglove SVG Basestation ([BASESTATION.md](BASESTATION.md)); "the real
> drone" = our Starling 2 Max.
>
> It covers the **new** gamepad teleop (`safe_teleop`) that arrived with the
> `yikuan/SVG_ground_control` snapshot on **2026-10-07** — snapshot now
> `yikuan/SVG_ground_control_dev` @ `b21d28c` (**2026-10-20**), which made the pad's
> `max_speed_mps` **live and kept equal to the commander's `teleop_max_speed_mps` both ways**
> and gave the panel a **Teleop · Sticks** card (§8, [BASESTATION.md](BASESTATION.md) §3.13):
> what the sticks do, what happens when you let go, the two fences that bound you, and bring-up
> in sim (§4). The real-drone procedure is [RUNBOOK.md B9](RUNBOOK.md#b9--fly-one-real-drone-with-the-gamepad) (§5).
>
> It is **NOT** a replacement for [RUNBOOK.md](RUNBOOK.md) — you still need the whole §B
> bring-up (agent, mocap, interfaces, QGC) underneath — and **NOT** CMU's old keyboard teleop,
> which CMU deleted (its `svg_ground_control/README.md` says so in the teleop section).
> Our sim keyboard (§3b) is a new, separate tool.
> It is also **not validated by us**. Seen once on the real drone: `drone_2` hand-flown alone
> ([#36](record/LEDGER.md)) and hand-flown at a hovering `drone_1` ([#37](record/LEDGER.md)).
> Not flown: the +x wall and the top of the teleop fence, the pad unplugged in flight. Treat every
> ⏳ STE mark left as "read this line, then go prove it".
>
> **In sim the drone is flown by keyboard, not by pad.** That path has flown in sim. The keys, cold start, video and test are in [localisation/README.md](../localisation/README.md#fly-it-with-the-keyboard-one-drone-sim-only). The keyboard window is §3b.

*(Unfamiliar term? → [GLOSSARY.md](GLOSSARY.md))*

---

## 1 · What gamepad teleop is, in plain terms

The sticks do **not** drive the motors. They move an invisible point in the room — the
**reference point** — and the drone is held on that point. Push the right stick forward and the
point slides away at up to `max_speed_mps`; the drone chases it. Let go and the point **stops
where it is**, and the drone is flown back onto it if it drifts — so "release = hold" is a real
position hold on all three axes, the same idea as PX4's own Position mode.

| Control | What it does |
|---|---|
| **Right stick** | horizontal velocity of the reference point |
| **Left stick up/down** | vertical velocity (climb / descend) |
| **Left stick left/right** | yaw rate — turns on the spot |
| **Left bumper** | **locks** the left stick: climb and yaw are forced to zero while engaged (the right stick keeps flying) |

Two things that surprise people. **It is room-fixed, not nose-relative** — "forward" on the
right stick means one fixed direction in the hangar (mocap +x, our "East"), whatever way the
nose points; turn the drone 180° and forward is still the *same* wall (CMU `teleop.md`, Controls section; the
command is published as world-frame ENU velocity). And **the sticks do nothing until you call
`start`** — `takeoff` climbs to `hover_positions` and holds there; only
`/swarm_commander/start` hands the drone to the pad, and only for drones listed in the
commander's `teleop_drones`. The sim keyboard with `teleop_single_ours.yaml` is the exception: it flies in Drive mode (BODY) through our relay, §3b.

Chain, end to end:

```
gamepad → joy_node → /joy → safe_teleop → /svg/drone_1/teleop_command
                                           (TwistStamped, world ENU)
                                                  ▼
             swarm_commander (reference point, CBF, fences)
                                                  ▼
                            px4_interface → PX4 → motors
```

On the real drone `joy_node` opens the pad by its name (`Logitech Gamepad F310`, pinned in the config
that `tools/real.sh` prepares), not by a device number: the lab keyboard can appear as a joystick too.
The topic carries the name of the drone flown: `/svg/drone_2/teleop_command` in [#36](record/LEDGER.md).

## 2 · 🚨 Safety first

- **Centred sticks = hold, not idle.** The reference point stops moving and the commander
  keeps holding the drone on it — it does **not** descend or drift. To come down you must call
  `land` (or `hold`, then `land`), or kill.
- **A stale pad is benign — by design.** Unplug it, flat battery, whatever: `safe_teleop`
  publishes zero velocity (`SafeTeleopNode.tick`), and Ctrl-C publishes one
  last zero on the way out (`main()` in `safe_teleop/teleop_node.py`). A **dead teleop node** is benign too: `teleop_timeout_s`
  (0.5 s) makes the commander treat a silent topic as zero, and that staleness path is what
  `./svg_teleop.sh stop` (a `pkill -9`) relies on.
- **None of that brings the drone down.** Benign ≠ safe. The RC **kill switch (ch8)** is
  still the only true motor cutoff — same iron rules as every other flight,
  [PREFLIGHT.md](PREFLIGHT.md). There is also **no per-drone land**: `hold` and `land` are
  swarm-wide Triggers. With two drones in the air, `hold` and `land` act on both.
- **Yaw sign cannot be proven in sim.** The real path negates the yaw rate ENU→NED
  (`PX4Interface::trajectory_callback` in `interface/px4_interface/src/px4_interface.cpp` sends
  `-angular.z` as `yawspeed`); the sim path does not, so a sim
  session proves every axis *except* yaw. Seen once on the real drone ([#36](record/LEDGER.md)):
  the heading followed the stick both ways. One flight is not a pass, and the direction is the
  owner's report. **Make the first yaw input of a session slow and low, thumb on KILL.** If it
  turns the wrong way, land and stop: `tools/real.sh` refuses a config that sets `yaw_sign`, so a
  sign flip is a code change with its change record, not a quick edit.
- **Takeoff is open-loop** fixed-time staging ("request control → arm → ascend") and never
  checks `vehicle_status` — if PX4 refuses to arm, the drone just sits there looking broken.
  The new `vehicle_command_ack` logging in `px4_interface` prints PX4's verdict (ACCEPTED /
  DENIED); **no ack at all** means `target_system` ≠ the drone's `MAV_SYS_ID` — check the
  `real_interfaces` startup line reads `target_system=1` for `drone_1`, `target_system=2` for
  `drone_2` ([RUNBOOK.md](RUNBOOK.md) §B step 5).
- **This stack bypasses `drone_safety_monitor`.** PX4 failsafes plus the RC kill switch are
  the entire net. (Squeeze is M7's problem, but for the record the hand-flown intruder is
  CBF-exempt — the holders dodge, and one cornered against the fence can be hit.)

## 3 · The controller

Two device profiles ship, in one registry (`safe_teleop/controllers.py`), differing **only**
in axis numbers:

| Profile | Device | Right stick | Left stick | Lock button |
|---|---|---|---|---|
| `xbox_usb` | Xbox 360 wired pad (Linux `xpad`) | axes **4 / 3** | 1 / 0 | button **4** |
| `dragonrise_usb` | generic DragonRise / SHANWAN "Android gamepad" (`hid-generic`) | axes **3 / 2** | 1 / 0 | button **6** |

**Which one do we have?** A Logitech F310 on the `xbox_usb` profile, with the switch on its back
on X and the MODE light off. Seen once on the real drone ([#36](record/LEDGER.md), [#37](record/LEDGER.md)).
The pad spec is `F310` in `tools/teleop/pad_core.py`. `tools/real.sh pad` checks the pad, and
`tools/real.sh teleop drone_2` (or `drone_1`) checks it and writes `xbox_usb` into the config it prepares.
Every shipped config pins `dragonrise_usb` (the `safe_teleop` block of `teleop_real.yaml`,
`teleop_single.yaml` and every other shipped yaml) and the config beats the node default
(`resolve_controller` in `safe_teleop/launch_helpers.py`: launch arg > config block > node default),
so a shipped config flown without `tools/real.sh` would read the F310 on the wrong map.

**The wrong-axis-map guard.** On the DragonRise layout axes 4 and 5 are analog triggers that
**rest at full scale**, so flying that pad on the `xbox_usb` map would read an untouched
trigger as a fully pushed forward stick. `safe_teleop` refuses to command any axis resting
past ±0.9, and says so (`SafeTeleopNode.check_axis_map`):

```
[safe_teleop] REFUSING TO COMMAND: forward (axis 4) rests at +1.00. ... probably the
wrong teleop_controller for this pad ... it would command full speed with nothing held.
```

That guard catches a *trigger*, not a merely rearranged stick — so identify an unknown pad
properly. The F310 is known (`tools/real.sh pad` checks it), so `joy_map` is only for a different
pad. In the **container** (`root@…#`), with `joy_node` already running:

```bash
ros2 run svg_ground_control joy_map     # wiggle ONE control at a time, read its number
```

It prints only on change, reports every axis's rest position, flags anything resting past ±0.9
as a trigger, and its numbers go straight into the table above.

### 3b · Keyboard instead of a pad (sim only, ours)

**Sim only.** Drive mode, the relay and `teleop_single_ours.yaml` (it sets `fence_enabled: false` and `teleop_fence_enabled: false`) are for the simulator only and never go on the real drone. Real flying is §5 with `teleop_real_ours.yaml`.

No pad? `tools/sim.sh keys` opens a small window that turns key presses into the same `/joy` stream a pad
sends. `safe_teleop` then flies the drone unchanged, with its hold and speed cap. `teleop_single_ours.yaml` turns both fences off. Start `safe_teleop`
first (§4), then run `keys` in a terminal tab and click the window.

Drive mode needs `teleop_single_ours.yaml`. `keys` starts the relay, a small node between `safe_teleop` and the
commander that turns the stick into room velocities. With a pad, start it with `tools/sim.sh relay` and stop it
with `tools/sim.sh relay stop`. A grey Room-mode header means the relay gets no stick: the old yaml is loaded, or
`safe_teleop` is not running. A red "Keys not reaching the drone" header means the relay is silent: close the
window, then run `tools/sim.sh keys`.

`safe_teleop` commands velocities, so roll slides the drone sideways and pitch moves it forward or back.
Two arrow keys together fly no faster than one. There is no stick lock on the keyboard.

Let go of every key and the drone holds. A key also counts as let go when the window loses focus, when it is
minimised, or after 1 s with no key event (a held key keeps auto-repeating). Closing the window or Ctrl-C
publishes zeros first. If the window dies, `safe_teleop` stops the drone after 0.5 s without `/joy`.

Only one source may publish `/joy`. The window warns while another one does, such as a plugged-in pad.
It reads `safe_teleop`'s controller profile and refuses a mismatch; `teleop_single_ours.yaml` pins
`dragonrise_usb`, the default. Sim only: the keyboard window and this config have not flown the real drone. The real pad is §5.

**Keys, cold start, strip, layout, evidence and video:** [localisation/README.md, Fly it with the keyboard](../localisation/README.md#fly-it-with-the-keyboard-one-drone-sim-only).
They sit beside the cuVSLAM Foxglove window that `slam_up.sh` opens, where the sim keyboard session is flown.

## 4 · Quick start — SIM (M1 rehearsal)

Needs a GPU and Isaac Sim, same as [RUNBOOK.md](RUNBOOK.md) §A. One command, on the
**laptop**, from the scripts directory:

```bash
cd ~/AirStack-starling-max2/AirStack/robot/ros_ws/src/svg_ground_control/scripts
./svg_teleop.sh solo       # 1 sim drone, teleop_single.yaml; --headless skips the viewport
./svg_teleop.sh takeoff && ./svg_teleop.sh start      # sticks do nothing until start
./svg_teleop.sh land       # also: hold | reset-fence | monitor | status | stop
```

⚠️ **The script does not pass `teleop_controller`.** Both its sim and real modes start the node
with **no config file** (the `ros2 run svg_ground_control safe_teleop --ros-args -p drone:=…` lines
in its `bringup` and `bringup_real` functions), so it falls back to `xbox_usb` — *not*
the `dragonrise_usb` the yamls pin — and on a DragonRise pad the §3 guard then fires and the
drone will not move at all. ✅ CMU (their pad), ⏳ STE for ours.

So the **manual two-terminal form is the one to learn** — the same two launches as the real drone's
(pad first, then the commander, same config, [RUNBOOK.md B9](RUNBOOK.md#b9--fly-one-real-drone-with-the-gamepad)), with
`teleop_single_ours.yaml` as the config and no `use_mocap:=true`. Open the sim session with
[RUNBOOK.md](RUNBOOK.md) §A0 (`tools/sim_terminals.sh` opens one Terminator window with the
tabs **Isaac Sim · Interfaces · Commander · Cockpit**, each already inside the right container);
start Isaac with **1** drone in the Isaac Sim tab and `launch_sim_interfaces.sh 1` in the
Interfaces tab. Then, both in the **container** (`root@…#`) — tmux alternative (RUNBOOK §A
"Alternatives to the tabs"): the `bringup` session, pad in pane 5, commander in pane 2:

```bash
CFG=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/teleop_single_ours.yaml
# Cockpit tab — the pad, FIRST (prints the stick reading once a second)
ros2 launch svg_ground_control teleop.launch.py config:=$CFG
# Commander tab — the commander, SAME config
ros2 launch svg_ground_control ground_control.launch.py config:=$CFG
```

`teleop_single_ours.yaml` is a new file, so run `bws && sws` once in the robot container before the first launch.
For the keyboard window use `tools/sim.sh keys` (§3b). A pad in sim needs `tools/sim.sh relay` (§3b). The whole keyboard session, from a cold start, is in [localisation/README.md](../localisation/README.md#cold-start).

(`takeoff` / `start` / `land` then go in any extra container shell — a new Terminator tab,
`Ctrl-Shift-T`, dropped into the robot container the way RUNBOOK §A0 describes.)

M1's teleop gate, all checkable in sim: right stick forward moves it one consistent direction
· left stick up climbs and the height **holds** on release instead of sagging · release the
right stick and it parks instead of coasting · left bumper logs `left stick locked` and the
height stops moving · Ctrl-C publishes a zero. Sim proves all of it — but **not** yaw sign.

## 5 · Quick start — REAL drone (M5)

> **WORLD: REAL DRONE — [PREFLIGHT.md](PREFLIGHT.md) gates every takeoff.** ⚠️ Never fly CMU's `teleop_real.yaml` (its `land_speed_mps` 0.3 left the drone armed on the ground, and its fences are room-sized, §6 and §9).

The real gamepad session has one front door, [`tools/real.sh`](../tools/real.sh)
([tools/README.md](../tools/README.md#real-drone-the-gamepad-check)). It checks the Logitech F310
pad (switch on the back on X, MODE light off) and renders `teleop_real_ours.yaml` for the drone
you name, `drone_1` or `drone_2`. It starts nothing. It prints the pane commands in start order:
the pad pane before the commander, so the sticks are proven on the ground before anything is armed.
The older Starling (`drone_1`) flies by the owner's decision, with a watcher on its front-right
motor at every takeoff.

Seen once on the real drone: `drone_2` hand-flown alone ([#36](record/LEDGER.md)), and `drone_2`
hand-flown at a hovering `drone_1` ([#37](record/LEDGER.md)).
Not flown: the +x wall and the top of the teleop fence, the pad unplugged in flight
([#36](record/LEDGER.md)). Also not flown: other approach directions, height offsets, both drones
moving ([#37](record/LEDGER.md)).

The commander gives no warning when no pad is sending: the drone holds as if the sticks were
centred (hazard 9 in [projects/HTX-R2.md](projects/HTX-R2.md)). Keep the pad pane running until
the drone is DISARMED.

The procedure from a cold start, with the ground check before `takeoff` and a stop table:
[RUNBOOK.md B9](RUNBOOK.md#b9--fly-one-real-drone-with-the-gamepad) for one drone, and
[B10](RUNBOOK.md#b10--two-real-drones-one-flown-by-hand) for two drones with one flown by hand.
The panel's **Teleop · Sticks** card ([BASESTATION.md](BASESTATION.md) §3.13): its states
`STICKS LIVE → drone_2` and `STICKS PARKED — drone_2: press Start` are seen in the panel recordings
of [#36](record/LEDGER.md) and [#37](record/LEDGER.md). The card's other readouts are not checked
on the real drone.

**⏳ STE — `svg_teleop.sh real` is NOT our recipe.** It launches `natnet_ros2`, which binds the
same NatNet ports as our `./mocap.sh` bridge and starves it ([MOCAP.md](MOCAP.md) §5, the
port-1511 squatter). It also carries the §4 `teleop_controller` bug. We have not tried it.

## 6 · The two fences

**The geofence** — `fence_enabled`, `fence_min`, `fence_max`. The outer safety net, watched
for every drone; `fence_behavior` picks what a breach does:

- `hold_all` (the default): any **active** drone outside the box latches the whole swarm —
  everyone freeze-hovers, **still armed**, until `/swarm_commander/reset_fence`. New on this
  branch: it also latches on a merely airborne **external** (RC-flown) drone (`SwarmCommander.enforce_fence`).
- `keep_in` (what both teleop configs use): nobody stops. Outward speed is clipped to a
  braking envelope — cruise until the true braking distance for `fence_brake_accel_mps2`,
  then a firm brake fed forward to PX4, then `fence_keep_in_gain` × distance in the last
  stretch (`wall_speed`, `keep_in_velocity`, `keep_in_acceleration` in `fence.py`). Fly at a wall and you slow to a stop on it.

**The teleop fence** — `teleop_fence_enabled`, `teleop_fence_min/max`
(ours, `teleop_real_ours.yaml`: x and y −1.5 to 1.5 m, z 0.3 to 1.8 m). A **smaller box inside** the geofence
that **only hand-flown drones** see, as the same soft wall whatever `fence_behavior` says,
drawn **amber** in the panel's 3D view (`SwarmCommander._teleop_fence_marker`;
[BASESTATION.md](BASESTATION.md)). It must lie inside the geofence or the commander raises a
`ValueError` at launch and dies (the `box_contains` check in `SwarmCommander.__init__`) — a feature.

Two details that matter on the ground. **Only ACTIVE drones are clipped**
(`SwarmCommander.advance_reference` for the teleop box, `keep_in` for the geofence) — takeoff and
landing cross the fence floor on purpose; without
that carve-out a reference clamped to `teleop_fence_min` z = 0.3 m becomes a position setpoint
PX4's stiff altitude loop holds, and the drone hovers 30 cm up and never touches down. And
**setting `fence_brake_accel_mps2` to 0 in flight** silently reverts the wall to the plain
`gain × distance` barrier — don't.

Our boxes are in `teleop_real_ours.yaml` ([CONFIG.md](CONFIG.md)). The geofence is our net:
x and y −2.0 to 2.0 m, z 0 to 2.0 m. The teleop fence sits inside it, as above. Check both fit
inside the net before every session ([PREFLIGHT.md](PREFLIGHT.md)). CMU's `teleop_real.yaml` keeps
its room-sized boxes (geofence ±4.0 × ±2.0 × 0–3.0 m, teleop fence ±3.0 × ±1.5 × 0.3–2.5 m).
Never fly it (iron rule 8).

## 7 · Hold, leash and ramp

Three numbers shape how the drone feels; all three were added to fix a specific bag.

- **`teleop_lead_m` (0.5 m) — the leash.** How far the reference may run ahead of the drone.
  Without it, a drone held back by the CBF or a fence banks up unbounded error and lunges when
  released. It is applied to the **horizontal and vertical parts separately**
  (`leash` in `position_hold.py`): pulling the reference back along the 3-D vector scaled its z
  with the horizontal lag and walked the altitude reference into every sag — 1.1 m lost on
  pure x-y stick (bag `run_060352`).
- **`hold_lead_m` (0.2 m)** — the same leash while taking off, landing or holding. **Keep it
  small**: PX4's `MPC_Z_P` is 5, and in bag `C1_0920_203148` a reference 1.3 m above a
  drone on the ground shot it to twice hover height.
- **`teleop_accel_mps2` (0.0 = off by default, **5.0** in `teleop_real.yaml` and
  `teleop_single.yaml`) — the ramp.** Stick velocity is ramped at this rate with the
  acceleration fed **forward** to PX4, like `MPC_ACC_HOR_MAX`, so the drone banks with the
  command instead of waiting for its velocity loop (a bare step is followed at only ~4 m/s²).
  The ramp re-attaches to what was last **published**, never to measured velocity — that was
  the old "it keeps going after I let go".

**Coast distance, so you can plan the room.** The ramp applies on release too: from 4 m/s at
5 m/s² the command needs 0.8 s and 1.6 m to reach zero, plus the 0.5 m leash — **≈ 2 m of coast
before it holds.** At our 0.5 m/s start cap it is far shorter. Seen once on the real drone: the
coast after release is measured in [#36](record/LEDGER.md). Not flown: the pad unplugged in flight.
Raise `teleop_accel_mps2` for a sharper stop.

**`~/hold` now brakes to a predicted stop point *ahead*** of where you called it, not back to
the call position (`SwarmCommander.handle_hold` → `stop_point`); the log says how far —
`holding: drone_1 (braking, stops 0.6 m ahead)`. The reference is **re-seeded from measured
position** at `/start` and after any `hold`/`land` (`SwarmCommander.advance_reference`), logging `sticks live,
holding [x, y, z] until moved`, so nothing is chased from before takeoff.

## 8 · Parameters

`safe_teleop` block — read **once at launch, except `max_speed_mps`**, which is live and
synced with the commander (2026-10-20). The old statement "none of it live" is wrong since then:

| Name | Default | Live? | Our value |
|---|---|---|---|
| `drone` | `drone_1` | no | the first of the config's `teleop_drones` (`teleop.launch.py`), or launch arg `drone:=`. `tools/real.sh teleop drone_2` writes `drone_2` there |
| `teleop_controller` | `xbox_usb` | no | **`dragonrise_usb`** in every shipped `safe_teleop` block. Real drone: `xbox_usb` for the F310, written by `tools/real.sh teleop` (§3) |
| `max_speed_mps` | `1.0` | **yes** (since 2026-10-20) | shipped `0.7` (`teleop_real.yaml`) — ours **0.5** for M5 ([CONFIG.md](CONFIG.md)). Kept equal to the commander's `teleop_max_speed_mps` **both ways** (`commander_status_callback` follows the snapshot; `push_max_speed` pushes a local `ros2 param set` to the commander); the panel's Teleop vmax row sets both. `cbf_max_speed_mps` is still a separate cap |
| `sync_max_speed` | `true` | no | default. `false` turns both directions off |
| `commander_status_topic` | `/svg/commander_status` | no | default (= the commander's `status_topic`) |
| `commander_ns` | `/swarm_commander` | no | default (where the commander's `set_parameters` lives) |
| `max_climb_speed_mps` | `0.8` | no | `0.5` (`teleop_real_ours.yaml`) |
| `deadzone` · `joy_timeout_s` · `yaw_rate_rad_s` | `0.15` · `0.5` · `1.0` | no | unset → defaults |
| `joy_topic` · `odometry_topic_template` · `publish_rate_hz` | from the profile (`/joy`) · `/{name}/odometry_conversion/odometry` · `20.0` | no | defaults; odometry is display-only here (the altitude readout) |
| `print_hz` | `0.0` (`teleop.launch.py`: `1.0`) | no | launch arg |
| `forward/left/climb/yaw_axis`, `lock_button`, `*_sign` | from the profile | no | profile (all signs `+1.0`) |

`swarm_commander` block — the live ones take `ros2 param set /swarm_commander <name> <value>`
**in flight**; the rest are refused at runtime with a reason naming what *is* live
(`SwarmCommander.on_parameter_change`):

| Name | Default | Live? | Our value (`teleop_real_ours.yaml`) |
|---|---|---|---|
| `teleop_drones` | `""` | **no** | the config names `drone_1`. `tools/real.sh teleop drone_2` renders it for `drone_2` |
| `teleop_timeout_s` | `0.5` | **no** | `0.5` |
| `teleop_max_speed_mps` | `1.2` | ✅ yes (> 0) | shipped `0.7` — ours **0.5** for M5; clamps with a throttled warn. Reported in the status snapshot's `tuning` block — which is what `safe_teleop` and the panel's Teleop vmax readout follow |
| `teleop_kp` | `1.0` | ✅ yes | `1.0` — sim/velocity output only; a real drone on the trajectory output is held by PX4's `MPC_XY_P` |
| `teleop_lead_m` | `0.5` | ✅ yes | `0.5` |
| `teleop_accel_mps2` | `0.0` (off) | ✅ yes | **`5.0`** |
| `hold_lead_m` | `0.2` | ✅ yes | `0.2` |
| `fence_behavior` | `hold_all` | no | **`keep_in`** |
| `fence_min` / `fence_max` | ±1000 | no | `[-2,-2,0]` / `[2,2,2]` (our net) |
| `fence_brake_accel_mps2` · `fence_keep_in_gain` · `fence_margin_m` | `4.0` · `1.0` · `0.0` | ✅ yes (gain **must stay > 0**) | `4.0` · `2.0` · `0.0` |
| `teleop_fence_enabled` / `_min` / `_max` | `false` / ±1000 | no | `true`, `[-1.5,-1.5,0.3]` / `[1.5,1.5,1.8]` |

yaml editing rules are unchanged — read once at launch, floats only, edit the **source** copy:
[RUNBOOK.md](RUNBOOK.md) §C7.

## 9 · Corrections to CMU's `teleop.md` for OUR rig

CMU's `teleop.md` (471 lines, in `AirStack/robot/ros_ws/src/svg_ground_control/`) is the
source of truth for everything not listed here — and since 2026-10-20 it documents the
`max_speed_mps` ↔ `teleop_max_speed_mps` sync correctly in its Parameters section. These
points are wrong, or wrong for us (code survey 2026-10-07, re-checked 2026-10-21 at `b21d28c`):

| CMU's `teleop.md` says | On our rig / in the code |
|---|---|
| `left_sign = -1.0` for `xbox_usb` (the `left_sign` row of its Parameters table and the Axis signs table) | **Wrong.** `controllers.py` has `left_sign=1.0` for **both** profiles (`XBOX_USB`, `DRAGONRISE_USB`), and its header comment records a bench check on **2026-09-19** that `left_sign = -1.0` moved the drone the **wrong way**. The code wins. Don't "fix" a sideways stick by copying that table. |
| `odometry_timeout_s` is a `safe_teleop` parameter (its Parameters table) | **It does not exist.** `SafeTeleopNode.__init__` declares only `joy_timeout_s`; odometry is display-only there (it supplies the altitude readout). Stale *odometry* is the commander's concern, via `state_timeout_s`. That same table is also split in half by a prose paragraph — the rows after it belong to the table above. |
| The device "today" is `xbox_usb` (the Controls intro and the Parameters table) | Every shipped config pins **`dragonrise_usb`** (`safe_teleop` block of `teleop_real.yaml`, `teleop_single.yaml`, …), and the config beats the node default (`resolve_controller` in `launch_helpers.py`). Our pad is the Logitech F310 on `xbox_usb`, written into the config by `tools/real.sh teleop` — §3. |
| The altitude prose in the Controls table ("release and the drone holds that height") describes `velocity.py`'s target-altitude mode | The node builds its `VelocityMapper` with `direct_vertical=True`, so the left stick **is** the vertical velocity (`VelocityMapper.update` → `_direct`) and there is **no altitude hold inside the node at all**. The hold you feel is entirely the **commander's** reference point. Correct behaviour, wrong mechanism — matters when you debug it. |
| Commander teleop params are "tuned in the commander's block" (the paragraph after its Parameters table) without saying which are live | Only `teleop_max_speed_mps`, `teleop_kp`, `teleop_lead_m`, `teleop_accel_mps2`, `hold_lead_m` and the three fence *dynamics* are live. `teleop_drones`, `teleop_timeout_s`, `fence_behavior` and **both fence boxes** are startup-only and setting them is refused — §8. |
| — (not covered) | `teleop_real.yaml` sets `land_speed_mps: 0.3`. Our lab **validated 0.6** — 0.3 bounces past PX4's land detector and leaves the drone **armed on the ground** ([CONFIG.md](CONFIG.md)). Change it before flying. Its `hover_positions` z is `1.2` where our goal configs use the low-and-safe `0.5`. |
| — (not covered) | `teleop_real.yaml` has **no `led_controller` block** (node defaults → `drone_1`, fine for us), and its `px4_vio_frame` comment says verify with the **B4b hand-check** — that is our [PREFLIGHT.md](PREFLIGHT.md) frame hand-check, not optional. |

## 10 · Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `pad: NO /joy` forever | `joy_node` cannot see the pad. Real drone, on the ground: stop the pad pane (the check refuses while `safe_teleop` runs) and run `tools/real.sh pad`: it names the fault (F310 not found, D mode, another pad carrying the pinned name). Do not look for the pad by device number: the keyboard can be joystick 0. A container made before the `/dev/input` bind mount (§11) cannot see a hot-plugged pad: **recreate** it, `cd ~/AirStack-starling-max2/AirStack && ./airstack.sh down && ./airstack.sh up robot-desktop`. Not in the `input` group? Add yourself and re-login. |
| `REFUSING TO COMMAND: … rests at +1.00`, or one direction dead while the others work | Wrong `teleop_controller` for this pad — a velocity axis pointed at an analog trigger, or at an axis index the pad does not have (`expects axes … but this pad reports only N`). The F310: re-run `tools/real.sh teleop drone_2` (or `drone_1`), which writes `xbox_usb` and names a D-mode or MODE fault. A different, unknown pad: identify it with `joy_map` (§3) and pass the right `teleop_controller:=`. |
| `/joy` arrives but `sequence size exceeds remaining buffer` | `joy_node` is running on a ROS 2 **Humble** host against the **Jazzy container**: they connect but cannot decode each other's messages (CMU's note, our laptop runs Jazzy). Run it in the container. |
| Sticks move the printout but the drone does not move | In order: **1.** `/swarm_commander/start` not called; **2.** the drone flown (`drone_1` or `drone_2`) not in the commander's `teleop_drones`; **3.** commander stuck non-IDLE after an RC takeover → call `land` once on the floor. |
| Commander dies at launch: `teleop fence … must lie inside the geofence` | Working as designed. Widen `fence_min/max` or shrink `teleop_fence_min/max` (§6). |
| Drone stops short of where you are pushing | A wall. `keep_in` geofence or the amber teleop fence is braking you — check the Basestation 3D panel. Not a stick problem. |
| Drone coasts after you let go, or travels forward after `hold` | Both by design (§7): the `teleop_accel_mps2` release ramp plus the leash, and `hold` braking to a predicted stop point ahead (the log prints the distance). Raise `teleop_accel_mps2` live for a sharper stop. |
| Drone hovers ~30 cm up on `land` and never touches down | A reference clamped to the teleop fence floor. Only ACTIVE drones should be clipped; if this happens, the drone is not transitioning to LANDING — `hold`, then `land`, then kill if it persists. |
| Yaw turns the wrong way | Sim cannot prove it. Seen once on the real drone turning with the stick ([#36](record/LEDGER.md), the owner's report). If it turns the wrong way: land and stop. `tools/real.sh` refuses a config that sets `yaw_sign`, so a sign flip is a code change with its change record, not a quick edit (§2). |
| Commander dies: "Logger severity cannot be changed" | **Fixed upstream** on this snapshot (`SwarmCommander.send_robot_command` keeps one severity per call site) — `patches/0002` is no longer needed. If you see it, you are on an older tree. |

Everything else: [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## 11 · Technical appendix

| Piece | Location (under `AirStack/robot/ros_ws/src/svg_ground_control/`) | Role |
|---|---|---|
| `safe_teleop` node | `svg_ground_control/safe_teleop/teleop_node.py` | `/joy` → `/svg/{drone}/teleop_command`; params declared in `SafeTeleopNode.__init__`, axis guard `check_axis_map`, stale-joy zeros `tick`, Ctrl-C zero `main`; speed-cap sync `commander_status_callback` (follow the commander) + `push_max_speed` (push to it). Mapping: `VelocityMapper.update` in `velocity.py`, `direct_vertical=True`. Left-stick lock: `latch.py` (`ButtonToggle`) — a left-bumper **toggle** that zeros climb + yaw, not a held snapshot |
| device registry | `safe_teleop/controllers.py` | `XBOX_USB`, `DRAGONRISE_USB` — driver nodes + axis map + signs. Resolution order (`resolve_controller` in `launch_helpers.py`): launch arg > config block > node default |
| pad diagnostics | `safe_teleop/{view,velocity,joy_view,monitor}.py`, `svg_ground_control/joy_map.py` | console scripts `pad_view`, `velocity_preview`, `joy_topic_view`, `teleop_monitor`, `joy_map` (entry points in `setup.py`); all flag triggers resting past ±0.9. The panel's Teleop · Sticks card is the graphical twin of `teleop_monitor` ([BASESTATION.md](BASESTATION.md) §3.13) |
| launches | `launch/teleop.launch.py`, `launch/ground_control.launch.py` | pad-only: args `config` (default `swarm_sim.yaml`), `drone`, `teleop_controller`, `print_hz` (1.0). Bundled: `use_teleop:=false\|true\|auto`, `teleop_drones:=` |
| reference point + fences | `svg_ground_control/position_hold.py`, `fence.py` | `leash`, `advance_reference`, `ramp_velocity`; `fence.py` is wholly new — `wall_speed`, `keep_in_velocity`, `keep_in_acceleration`, `box_contains` |
| commander glue | `svg_ground_control/swarm_commander.py` | teleop-fence validation = the `box_contains` check in `__init__` · live-param set `on_parameter_change` / `_apply_parameters` · hold `handle_hold` + `stop_point` · hold_all on external `enforce_fence` · reseed + teleop-fence clip `advance_reference` · geofence clip `keep_in` · yaw `publish_command` / `desired_heading` · amber marker `_teleop_fence_marker` |
| yaw ENU→NED | `../../interface/px4_interface/src/px4_interface.cpp` | `PX4Interface::trajectory_callback` sends `-angular.z` as `yawspeed` — why yaw sign is unverifiable in sim; `PX4Interface::on_vehicle_command_ack` logs ACCEPTED / DENIED |
| host bring-up script | `scripts/svg_teleop.sh` (452 lines) | `solo\|squeeze\|hover [--headless]`, `real`, `takeoff\|start\|land\|hold\|reset-fence\|monitor\|status\|stop`, `logs <isaac\|agent\|natnet\|iface\|commander\|teleop\|joy\|rviz>`; tmux inside the containers (`docker exec -it airstack-robot-desktop-1 tmux attach -t commander`), re-exports `ROS_DOMAIN_ID` per session (`detect_domain`) |
| pad into the container | `AirStack/robot/docker/robot-base-docker-compose.yaml` | `/dev/input:/dev/input` bind mount (not `devices:`) so hotplug works |
| legacy node · CMU doc | `svg_ground_control/xbox_teleop.py` · `teleop.md` (471 lines) | `xbox_teleop` is a simpler direct stick→velocity utility, **not** the documented path. Read `teleop.md` with §9 in hand |
