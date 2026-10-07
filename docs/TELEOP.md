# TELEOP — flying `drone_1` by hand with a gamepad

> **Who this is for:** anyone in the AI.R / STC lab who wants to hand-fly the Starling with a
> game controller instead of publishing waypoints. No robotics background needed.
> It covers the **new** gamepad teleop (`safe_teleop`) that arrived with the
> `yikuan/SVG_ground_control` snapshot on **2026-10-07**: what the sticks do, what happens
> when you let go, the two fences that bound you, and bring-up on sim and on the real drone.
> It is **NOT** a replacement for [RUNBOOK.md](RUNBOOK.md) — you still need the whole §B
> bring-up (agent, mocap, interfaces, QGC) underneath — and **NOT** the old keyboard teleop,
> which CMU deleted (`AirStack/robot/ros_ws/src/svg_ground_control/README.md:70`).
> It is also **NOT validated by us**: ⏳ **nothing below has flown at STE.** Treat every
> ⏳ STE mark as "read this line, then go prove it".

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
nose points; turn the drone 180° and forward is still the *same* wall (`teleop.md:60-61`; the
command is published as world-frame ENU velocity). And **the sticks do nothing until you call
`start`** — `takeoff` climbs to `hover_positions` and holds there; only
`/swarm_commander/start` hands the drone to the pad, and only for drones listed in the
commander's `teleop_drones`.

Chain, end to end:

```
gamepad → joy_node → /joy → safe_teleop → /svg/drone_1/teleop_command
                                           (TwistStamped, world ENU)
                                                  ▼
             swarm_commander (reference point, CBF, fences)
                                                  ▼
                            px4_interface → PX4 → motors
```

## 2 · 🚨 Safety first

- **Centred sticks = hold, not idle.** The reference point stops moving and the commander
  keeps holding the drone on it — it does **not** descend or drift. To come down you must call
  `land` (or `hold`, then `land`), or kill.
- **A stale pad is benign — by design.** Unplug it, flat battery, whatever: `safe_teleop`
  publishes zero velocity (`safe_teleop/teleop_node.py:198-201`), and Ctrl-C publishes one
  last zero on the way out (`:298`). A **dead teleop node** is benign too: `teleop_timeout_s`
  (0.5 s) makes the commander treat a silent topic as zero, and that staleness path is what
  `./svg_teleop.sh stop` (a `pkill -9`) relies on.
- **None of that brings the drone down.** Benign ≠ safe. The RC **kill switch (ch8)** is
  still the only true motor cutoff — same iron rules as every other flight,
  [PREFLIGHT.md](PREFLIGHT.md). There is also **no per-drone land**: `hold` and `land` are
  swarm-wide Triggers (academic with one drone, not at M7).
- **Yaw sign cannot be proven in sim.** The real path negates the yaw rate ENU→NED
  (`interface/px4_interface/src/px4_interface.cpp:378-382`); the sim path does not, so a sim
  session proves every axis *except* yaw. ⏳ STE **First real flight: yaw slowly, low, thumb
  on kill.** If it turns the wrong way, flip `yaw_sign` (`teleop_real.yaml:22-24`).
- **Takeoff is open-loop** fixed-time staging ("request control → arm → ascend") and never
  checks `vehicle_status` — if PX4 refuses to arm, the drone just sits there looking broken.
  The new `vehicle_command_ack` logging in `px4_interface` prints PX4's verdict (ACCEPTED /
  DENIED); **no ack at all** means `target_system` ≠ the drone's `MAV_SYS_ID` — check the
  `real_interfaces` startup line reads `target_system=1` ([RUNBOOK.md](RUNBOOK.md) §B step 5).
- **This stack bypasses `drone_safety_monitor`.** PX4 failsafes plus the RC kill switch are
  the entire net. (Squeeze is M7's problem, but for the record the hand-flown intruder is
  CBF-exempt — the holders dodge, and one cornered against the fence can be hit.)

## 3 · The controller

Two device profiles ship, in one registry (`safe_teleop/controllers.py`), differing **only**
in axis numbers:

| Profile | Device | Right stick | Left stick | Lock button |
|---|---|---|---|---|
| `xbox_usb` (`:90`) | Xbox 360 wired pad (Linux `xpad`) | axes **4 / 3** | 1 / 0 | button **4** |
| `dragonrise_usb` (`:127`) | generic DragonRise / SHANWAN "Android gamepad" (`hid-generic`) | axes **3 / 2** | 1 / 0 | button **6** |

**Which one do we have?** ⏳ **Unknown — nobody has written it down.** Every shipped config
pins `dragonrise_usb` (`teleop_real.yaml:140`, `teleop_single.yaml:108`) and the config beats
the node default (`safe_teleop/launch_helpers.py:49-55`), so a real Xbox pad needs
`teleop_controller:=xbox_usb` on the launch line or a yaml edit.
⏳ **STE: record which pad the lab has in [CONFIG.md](CONFIG.md)** and stop guessing.

**The wrong-axis-map guard.** On the DragonRise layout axes 4 and 5 are analog triggers that
**rest at full scale**, so flying that pad on the `xbox_usb` map would read an untouched
trigger as a fully pushed forward stick. `safe_teleop` refuses to command any axis resting
past ±0.9, and says so (`teleop_node.py:146-184`):

```
[safe_teleop] REFUSING TO COMMAND: forward (axis 4) rests at +1.00. ... probably the
wrong teleop_controller for this pad ... it would command full speed with nothing held.
```

That guard catches a *trigger*, not a merely rearranged stick — so identify an unknown pad
properly. In the **container** (`root@…#`), with `joy_node` already running:

```bash
ros2 run svg_ground_control joy_map     # wiggle ONE control at a time, read its number
```

It prints only on change, reports every axis's rest position, flags anything resting past ±0.9
as a trigger, and its numbers go straight into the table above.

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
with **no config file** (`svg_teleop.sh:189`, `:305`), so it falls back to `xbox_usb` — *not*
the `dragonrise_usb` the yamls pin — and on a DragonRise pad the §3 guard then fires and the
drone will not move at all. ✅ CMU (their pad), ⏳ STE for ours.

So the **manual two-pane form is the one to learn** — identical to §5's, with
`teleop_single.yaml` for `teleop_real.yaml` and no `use_mocap:=true`. On top of
[RUNBOOK.md](RUNBOOK.md) §A T1 (Isaac) and T2's `bringup` session with pane 1 running
`launch_sim_interfaces.sh 1`, in the **container** (`root@…#`):

```bash
CFG=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/teleop_single.yaml
# pane 5 — the pad, FIRST (prints the stick reading once a second)
ros2 launch svg_ground_control teleop.launch.py config:=$CFG
# pane 2 — the commander, SAME config
ros2 launch svg_ground_control ground_control.launch.py config:=$CFG
```

M1's teleop gate, all checkable in sim: right stick forward moves it one consistent direction
· left stick up climbs and the height **holds** on release instead of sagging · release the
right stick and it parks instead of coasting · left bumper logs `left stick locked` and the
height stops moving · Ctrl-C publishes a zero. Sim proves all of it — but **not** yaw sign.

## 5 · Quick start — REAL drone (M5)

Do the **whole** [RUNBOOK.md](RUNBOOK.md) §B bring-up first — steps 0–7: agent, QGC,
`./mocap.sh`, `real_interfaces`, Basestation hand-carry preflight. Then swap step 6's config
for `teleop_real.yaml` and add the pad; pad first, deliberately, so the sticks are proven
before anything is armed. Both in the **container** (`root@…#`), in the `bringup` session:

```bash
CFG=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/teleop_real.yaml
# pane 5 — the pad, FIRST
ros2 launch svg_ground_control teleop.launch.py config:=$CFG
# pane 3 — the commander (replaces step 6's launch), SAME config
ros2 launch svg_ground_control ground_control.launch.py config:=$CFG use_mocap:=true
```

Pane 5 prints `pad: fwd … left … climb … yaw … | cmd vx … vy … vz …` once a second — move each
stick and watch the numbers follow. `NO /joy` = the driver cannot see the pad (gotcha below);
`NO odometry` is normal until interfaces and mocap are up — only `vz` waits for the height.

Either launch restarts without the other. One pane instead? Add `use_teleop:=true` to the
commander launch and skip the pad pane (`false|true|auto`) — but you lose the pre-arm pad
check, the whole point of the split. Any config can take a hand-flown drone with
`teleop_drones:=drone_1` on the launch line, whatever its yaml says.

**Ground check, before the first `takeoff`** (stack up, takeoff NOT called):
`ros2 topic echo /svg/drone_1/teleop_command` → right stick moves `vx`/`vy` in the correct
directions and they are zero at rest; left stick up/down moves `vz`, zero at rest; unplug the
pad and every velocity goes to zero; carry the drone and its Basestation mesh follows
([BASESTATION.md](BASESTATION.md)). Then and only then, [PREFLIGHT.md](PREFLIGHT.md),
`takeoff`, `start`.

**⚠️ The pad-in-container gotcha.** `joy_node` runs inside the container, and `privileged`
populates `/dev` only at container start — a pad plugged in later would stay invisible
forever. The compose file therefore bind-mounts the *directory*
(`AirStack/robot/docker/robot-base-docker-compose.yaml:51`, `/dev/input:/dev/input`), which
tracks hotplug. A container created **before** that line existed needs **recreating**:

```bash
ls /dev/input/js0                                        # laptop: the pad is there
docker exec airstack-robot-desktop-1 ls /dev/input/js0   # container: must also be there
cd ~/AirStack-starling-max2/AirStack && ./airstack.sh down && ./airstack.sh up robot-desktop
docker exec airstack-robot-desktop-1 bash -lc "ros2 run joy joy_enumerate_devices"
```

(CMU writes this as `AUTOLAUNCH=false airstack up`; we use `./airstack.sh`, and any container
made before the branch switch needs recreating anyway — [MIGRATION.md](MIGRATION.md) §6.) The
last command lists the pad by name once the container can see it; an SDL
`Failed loading udev_device_get_action` on the way is harmless. If the device exists but is
unreadable, add yourself to the `input` group and log out and back in.

**Do NOT run `joy_node` on the laptop.** Run it in the container (the launch does). CMU's
note is about a Humble host against the Jazzy container (they connect at the DDS level and
then cannot deserialize each other's messages — `sequence size exceeds remaining buffer`
forever). Our laptop is 24.04 / Jazzy, so that failure does not apply here, but keeping the
pad driver in the container is still the only path these docs describe.

**⏳ STE — `./svg_teleop.sh real` is NOT our recipe.** It *launches `natnet_ros2`* and
hard-fails if that package is not built (`svg_teleop.sh:254-259`). On our rig `natnet_ros2`
receives nothing (our Motive broadcasts — [MOCAP.md](MOCAP.md) §3) **and** it binds the same
NatNet ports as our bridge, which is the documented way to starve `./mocap.sh` (MOCAP.md §5,
the port-1511 squatter). Its `/drone_1/pose` gate would *pass* if `./mocap.sh` is already
running, but **we have not tried this** — and it carries the §4 `teleop_controller` bug too.

## 6 · The two fences

**The geofence** — `fence_enabled`, `fence_min`, `fence_max`. The outer safety net, watched
for every drone; `fence_behavior` picks what a breach does:

- `hold_all` (the default): any **active** drone outside the box latches the whole swarm —
  everyone freeze-hovers, **still armed**, until `/swarm_commander/reset_fence`. New on this
  branch: it also latches on a merely airborne **external** (RC-flown) drone (`:1493-1507`).
- `keep_in` (what both teleop configs use): nobody stops. Outward speed is clipped to a
  braking envelope — cruise until the true braking distance for `fence_brake_accel_mps2`,
  then a firm brake fed forward to PX4, then `fence_keep_in_gain` × distance in the last
  stretch (`fence.py:88`, `:111`, `:136`). Fly at a wall and you slow to a stop on it.

**The teleop fence** — `teleop_fence_enabled`, `teleop_fence_min/max`
(`teleop_real.yaml:107-109`: ±3.0 / ±1.5 / 0.3–2.5 m). A **smaller box inside** the geofence
that **only hand-flown drones** see, as the same soft wall whatever `fence_behavior` says,
drawn **amber** in the Basestation's 3D panel (`swarm_commander.py:2205-2207`;
[BASESTATION.md](BASESTATION.md)). It must lie inside the geofence or the commander raises a
`ValueError` at launch and dies (`:607-618`) — a feature.

Two details that matter on the ground. **Only ACTIVE drones are clipped**
(`:1949-1953`, `:1709-1712`) — takeoff and landing cross the fence floor on purpose; without
that carve-out a reference clamped to `teleop_fence_min` z = 0.3 m becomes a position setpoint
PX4's stiff altitude loop holds, and the drone hovers 30 cm up and never touches down. And
**setting `fence_brake_accel_mps2` to 0 in flight** silently reverts the wall to the plain
`gain × distance` barrier — don't.

⏳ STE: `teleop_real.yaml`'s geofence (±4.0 × ±2.0 × 0–3.0 m) is **CMU's volume, not ours** —
every shipped config's boxes are drawn to their arena ([RUNBOOK.md](RUNBOOK.md) §C). Redraw
**both** boxes to our net before the first teleop flight, and record them in CONFIG.md.

## 7 · Hold, leash and ramp

Three numbers shape how the drone feels; all three were added to fix a specific bag.

- **`teleop_lead_m` (0.5 m) — the leash.** How far the reference may run ahead of the drone.
  Without it, a drone held back by the CBF or a fence banks up unbounded error and lunges when
  released. It is applied to the **horizontal and vertical parts separately**
  (`position_hold.py:62-80`): pulling the reference back along the 3-D vector scaled its z
  with the horizontal lag and walked the altitude reference into every sag — 1.1 m lost on
  pure x-y stick (bag `run_060352`).
- **`hold_lead_m` (0.2 m)** — the same leash while taking off, landing or holding. **Keep it
  small**: PX4's `MPC_Z_P` is 5, and in bag `C1_0920_203148` a reference 1.3 m above a
  grounded drone shot it to twice hover height.
- **`teleop_accel_mps2` (0.0 = off by default, **5.0** in `teleop_real.yaml:80` and
  `teleop_single.yaml:64`) — the ramp.** Stick velocity is ramped at this rate with the
  acceleration fed **forward** to PX4, like `MPC_ACC_HOR_MAX`, so the drone banks with the
  command instead of waiting for its velocity loop (a bare step is followed at only ~4 m/s²).
  The ramp re-attaches to what was last **published**, never to measured velocity — that was
  the old "it keeps going after I let go".

**Coast distance, so you can plan the room.** The ramp applies on release too: from 4 m/s at
5 m/s² the command needs 0.8 s and 1.6 m to reach zero, plus the 0.5 m leash — **≈ 2 m of coast
before it holds.** At our 0.5 m/s start cap it is far shorter; ⏳ STE **measure it** (M5's exit
criterion). Raise `teleop_accel_mps2` for a sharper stop.

**`~/hold` now brakes to a predicted stop point *ahead*** of where you called it, not back to
the call position (`swarm_commander.py:1409-1425`); the log says how far —
`holding: drone_1 (braking, stops 0.6 m ahead)`. The reference is **re-seeded from measured
position** at `/start` and after any `hold`/`land` (`:1697-1724`), logging `sticks live,
holding [x, y, z] until moved`, so nothing is chased from before takeoff.

## 8 · Parameters

`safe_teleop` block — read **once at launch**, none of it live:

| Name | Default | Live? | Our value |
|---|---|---|---|
| `teleop_controller` | `xbox_usb` | no | **`dragonrise_usb`** — `teleop_real.yaml:140` ⏳ verify §3 |
| `max_speed_mps` | `1.0` | no | shipped `0.7` (`teleop_real.yaml:141`) — ours **0.5** for M5 ([CONFIG.md](CONFIG.md)) |
| `max_climb_speed_mps` | `0.8` | no | `0.5` (`:142`) |
| `deadzone` · `joy_timeout_s` · `yaw_rate_rad_s` | `0.15` · `0.5` · `1.0` | no | unset → defaults |
| `print_hz` | `0.0` (`teleop.launch.py`: `1.0`) | no | launch arg |
| `forward/left/climb/yaw_axis`, `lock_button`, `*_sign` | from the profile | no | profile (all signs `+1.0`) |

`swarm_commander` block — the live ones take `ros2 param set /swarm_commander <name> <value>`
**in flight**; the rest are refused at runtime with a reason (`swarm_commander.py:920-1033`):

| Name | Default | Live? | Our value (`teleop_real.yaml`) |
|---|---|---|---|
| `teleop_drones` | `""` | **no** | `drone_1` (`:30`) |
| `teleop_timeout_s` | `0.5` | **no** | `0.5` (`:54`) |
| `teleop_max_speed_mps` | `1.2` | ✅ yes | shipped `0.7` (`:70`) — ours **0.5** for M5; clamps with a throttled warn |
| `teleop_kp` | `1.0` | ✅ yes | `1.0` (`:75`) — sim/velocity output only; a real drone on the trajectory output is held by PX4's `MPC_XY_P` |
| `teleop_lead_m` | `0.5` | ✅ yes | `0.5` (`:76`) |
| `teleop_accel_mps2` | `0.0` (off) | ✅ yes | **`5.0`** (`:80`) |
| `hold_lead_m` | `0.2` | ✅ yes | `0.2` (`:60`) |
| `fence_behavior` | `hold_all` | no | **`keep_in`** (`:92`) |
| `fence_min` / `fence_max` | ±1000 | no | `[-4,-2,0]` / `[4,2,3]` (`:101-102`) ⏳ shrink |
| `fence_brake_accel_mps2` · `fence_keep_in_gain` · `fence_margin_m` | `4.0` · `1.0` · `0.0` | ✅ yes (gain **must stay > 0**) | `4.0` · `2.0` · `0.0` (`:98-100`) |
| `teleop_fence_enabled` / `_min` / `_max` | `false` / ±1000 | no | `true`, `[-3,-1.5,0.3]` / `[3,1.5,2.5]` (`:107-109`) ⏳ shrink |

yaml editing rules are unchanged — read once at launch, floats only, edit the **source** copy:
[RUNBOOK.md](RUNBOOK.md) §C7.

## 9 · Corrections to CMU's `teleop.md` for OUR rig

CMU's `teleop.md` (463 lines, in `AirStack/robot/ros_ws/src/svg_ground_control/`) is the
source of truth for everything not listed here. These lines are wrong, or wrong for us
(code survey 2026-10-07):

| CMU's `teleop.md` says | On our rig / in the code |
|---|---|
| `left_sign = -1.0` for `xbox_usb` (`:320`, `:399`, the Axis signs table `:409`) | **Wrong.** `controllers.py` has `left_sign=1.0` for **both** profiles (`:112`, `:142`), and the comment at `:38-40` records a bench check on **2026-09-19** that `left_sign = -1.0` moved the drone the **wrong way**. The code wins. Don't "fix" a sideways stick by copying that table. |
| `odometry_timeout_s` is a `safe_teleop` parameter (`:394`) | **It does not exist.** The node declares only `joy_timeout_s` (`teleop_node.py:61`); odometry is display-only there (it supplies the altitude readout). Stale *odometry* is the commander's concern, via `state_timeout_s`. That same table is also split in half by a prose paragraph — the four rows after it belong to the table above. |
| The device "today" is `xbox_usb` (`:16-17`, `:382`) | Every shipped config pins **`dragonrise_usb`** (`teleop_real.yaml:140`, `teleop_single.yaml:108`), and the config beats the node default (`launch_helpers.py:49-55`). Which pad **we** own is ⏳ unrecorded — §3. |
| The altitude prose (`:25`, "release and the drone holds that height") describes `velocity.py`'s target-altitude mode | The node runs `direct_vertical=True` (`teleop_node.py:81`), so the left stick **is** the vertical velocity (`velocity.py:138-153`) and there is **no altitude hold inside the node at all**. The hold you feel is entirely the **commander's** reference point. Correct behaviour, wrong mechanism — matters when you debug it. |
| Commander teleop params are "tuned in the commander's block" (`:390-393`) without saying which are live | Only `teleop_max_speed_mps`, `teleop_kp`, `teleop_lead_m`, `teleop_accel_mps2`, `hold_lead_m` and the three fence *dynamics* are live. `teleop_drones`, `teleop_timeout_s`, `fence_behavior` and **both fence boxes** are startup-only and setting them is refused — §8. |
| — (not covered) | `teleop_real.yaml:58` sets `land_speed_mps: 0.3`. Our lab **validated 0.6** — 0.3 bounces past PX4's land detector and leaves the drone **armed on the ground** ([CONFIG.md](CONFIG.md)). Change it before flying. Its `hover_positions` z is `1.2` where our goal configs use the low-and-safe `0.5`. It has **no `led_controller` block** (node defaults → `drone_1`, fine for us), and its `px4_vio_frame` comment says verify with the **B4b hand-check** — that is our [PREFLIGHT.md](PREFLIGHT.md) frame hand-check, not optional. |

## 10 · Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `pad: NO /joy` forever | `joy_node` cannot see the device. `ls /dev/input/js0` on the laptop, then the same inside the container — if it is missing there, **recreate** the container (§5). Not in the `input` group? Add yourself and re-login. |
| `REFUSING TO COMMAND: … rests at +1.00`, or one direction dead while the others work | Wrong `teleop_controller` for this pad — a velocity axis pointed at an analog trigger, or at an axis index the pad does not have (`expects axes … but this pad reports only N`). Identify the pad with `joy_map` (§3) and pass the right `teleop_controller:=`. |
| `/joy` arrives but `sequence size exceeds remaining buffer` | `joy_node` is running on the **Humble laptop** against the **Jazzy container**. Run it in the container. |
| Sticks move the printout but the drone does not move | In order: **1.** `/swarm_commander/start` not called; **2.** `drone_1` not in the commander's `teleop_drones`; **3.** commander stuck non-IDLE after an RC takeover → call `land` once on the floor. |
| Commander dies at launch: `teleop fence … must lie inside the geofence` | Working as designed. Widen `fence_min/max` or shrink `teleop_fence_min/max` (§6). |
| Drone stops short of where you are pushing | A wall. `keep_in` geofence or the amber teleop fence is braking you — check the Basestation 3D panel. Not a stick problem. |
| Drone coasts after you let go, or travels forward after `hold` | Both by design (§7): the `teleop_accel_mps2` release ramp plus the leash, and `hold` braking to a predicted stop point ahead (the log prints the distance). Raise `teleop_accel_mps2` live for a sharper stop. |
| Drone hovers ~30 cm up on `land` and never touches down | A reference clamped to the teleop fence floor. Only ACTIVE drones should be clipped; if this happens, the drone is not transitioning to LANDING — `hold`, then `land`, then kill if it persists. |
| Yaw turns the wrong way | Expected risk — sim cannot prove it. Land, flip `yaw_sign` in the config's `safe_teleop` block, relaunch. |
| Commander dies: "Logger severity cannot be changed" | **Fixed upstream** on this snapshot (`swarm_commander.py:1612-1614`) — `patches/0002` is no longer needed. If you see it, you are on an older tree. |

Everything else: [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## 11 · Technical appendix

| Piece | Location (under `AirStack/robot/ros_ws/src/svg_ground_control/`) | Role |
|---|---|---|
| `safe_teleop` node | `svg_ground_control/safe_teleop/teleop_node.py` | `/joy` → `/svg/{drone}/teleop_command`; params `:42-75`, axis guard `:146-184`, stale-joy zeros `:198-201`, Ctrl-C zero `:298`. Mapping: `velocity.py:124-156`, `direct_vertical=True`. Left-stick lock: `latch.py` — a left-bumper **toggle** that zeros climb + yaw, not a held snapshot |
| device registry | `safe_teleop/controllers.py` | `XBOX_USB` `:90`, `DRAGONRISE_USB` `:127` — driver nodes + axis map + signs. Resolution order (`launch_helpers.py:49-55`): launch arg > config block > node default |
| pad diagnostics | `safe_teleop/{view,velocity,joy_view,monitor}.py`, `svg_ground_control/joy_map.py` | console scripts `pad_view`, `velocity_preview`, `joy_topic_view`, `teleop_monitor`, `joy_map` (`setup.py:35-40`); all flag triggers resting past ±0.9 |
| launches | `launch/teleop.launch.py`, `launch/ground_control.launch.py` | pad-only: args `config` (default `swarm_sim.yaml`), `drone`, `teleop_controller`, `print_hz` (1.0). Bundled: `use_teleop:=false\|true\|auto`, `teleop_drones:=` |
| reference point + fences | `svg_ground_control/position_hold.py`, `fence.py` | `leash` `:62-80`, `advance_reference` `:85`; `fence.py` is wholly new — `wall_speed` `:88`, `keep_in_velocity` `:111`, `keep_in_acceleration` `:136` |
| commander glue | `svg_ground_control/swarm_commander.py` | teleop-fence validation `:607-618`, live-param set `:915-960`, hold `:1409-1425`, hold_all on external `:1493-1507`, reseed `:1697-1724`, fence clip `:1949-1953`, yaw `:2008-2028`, amber marker `:2205-2207` |
| yaw ENU→NED | `../../interface/px4_interface/src/px4_interface.cpp:378-382` | negates the yaw rate — why yaw sign is unverifiable in sim; `vehicle_command_ack` logging `:680-706` |
| host bring-up script | `scripts/svg_teleop.sh` (452 lines) | `solo\|squeeze\|hover [--headless]`, `real`, `takeoff\|start\|land\|hold\|reset-fence\|monitor\|status\|stop`, `logs <isaac\|agent\|natnet\|iface\|commander\|teleop\|joy\|rviz>`; tmux inside the containers (`docker exec -it airstack-robot-desktop-1 tmux attach -t commander`), re-exports `ROS_DOMAIN_ID` per session `:45-57` |
| pad into the container | `AirStack/robot/docker/robot-base-docker-compose.yaml:51` | `/dev/input:/dev/input` bind mount (not `devices:`) so hotplug works |
| legacy node · CMU doc | `svg_ground_control/xbox_teleop.py` · `teleop.md` (463 lines) | `xbox_teleop` is a simpler direct stick→velocity utility, **not** the documented path. Read `teleop.md` with §9 in hand |
