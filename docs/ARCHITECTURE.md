# ARCHITECTURE — how the system works

> **KNOW.** The one-page primer, the flight-lab network, and who wrote which document. Moved
> verbatim from the front-page README on 2026-10-21 so the README can be short. To *run*
> things: [RUNBOOK.md](RUNBOOK.md). Terms: [GLOSSARY.md](GLOSSARY.md).

## How the system works (one-page primer)

**PX4 is the pilot, AirStack is mission control, and the RC kill switch outranks both.**

| | Decides | Where it runs |
|---|---|---|
| **AirStack** (swarm commander) | *where to go* — takeoff, goals, hold, land; and *how fast to get there* (an acceleration-limited profile) | ground laptop |
| **PX4 autopilot** | *how to fly* — position hold, stabilization, motors, EKF2 state estimation, failsafes | on the drone |
| **RC pilot** | emergency veto — kill switch, mode override; or hand-flying through the commander's gamepad path | your hands |

We use a **thin slice** of AirStack: our **`./mocap.sh`** pose bridge (runs on the laptop —
see [MOCAP.md](MOCAP.md)) feeding AirStack's `mocap_bridge` node (mocap → PX4 EKF2), the laptop↔PX4 link
(uXRCE-DDS), and the swarm commander with its two safety layers: the **CBF collision
filter** (Control Barrier Function — a math filter that rewrites the velocity command so
drones keep a safety radius from each other; it is tunable in flight) and the **fence**
(either freeze-everyone `hold_all`, or a `keep_in` wall the drone brakes against).

The planner/perception layers stay dormant here; those belong to AirStack's outdoor missions,
where planning runs on the drone's own computer. The operator watches all of it in the
**Foxglove SVG Basestation** panel, fed by a 5 Hz status snapshot the commander publishes.
*(AirStack's own mocap driver, [`natnet_ros2`](https://github.com/L2S-lab/natnet_ros2), stays
vendored in the snapshot but is unused on our rig — our Motive broadcasts, which it can't
hear; full story in [MOCAP.md](MOCAP.md) §3.)*

<img src="../pictures/Starling_Airstack_architecture.png" alt="Starling Max 2 × AirStack control-flow diagram — Motive PC to mocap bridge to robot container (mocap_bridge, swarm commander, CBF safety filter, MicroXRCEAgent) to PX4 onboard (EKF2, control loops, motors), with the RC kill switch outranking everything" width="850">

*(Diagram drawn for the previous branch; four things moved since — read it with these
corrections: the laptop box is `./mocap.sh` (there is no `bridge` subcommand); between the
CBF and the MicroXRCEAgent sits `px4_interface`, which turns the command into PX4 messages
and carries arm/disarm/offboard; the commander→PX4 arrow is a **trajectory setpoint**
(position + velocity + acceleration), so PX4's chain is position → velocity → attitude → rate;
and the operator view is the Foxglove panel (plus the gamepad through the same CBF), with
QGC kept for arming truth. In sim the right-hand box is Isaac Sim + PX4 SITL over MAVROS.)*

**How the laptop↔drone leg works:** the laptop repackages everything into PX4's native
message format (`px4_msgs`), and the **MicroXRCEAgent** program ships those messages over
WiFi to a tiny **client built into PX4 itself** — so no ROS runs on the drone, and there is
nothing to install on it. The laptop does **no state estimation and no stabilization** — it
is a courier for mocap poses and a source of trajectory setpoints.

**Offboard mode** = PX4 outsources goal-generation to an external computer that must stream
setpoints continuously (≥2 Hz; ours: 20 Hz). Stream stops → PX4 failsafes; it never tumbles.
Onboard modes (Position/Hold/Mission…) = PX4 makes its own goals, fully self-contained.

**What we inject, and why it changed.** PX4's control is a cascade —
`POSITION ~50 Hz → VELOCITY ~50 Hz → ATTITUDE ~250 Hz → RATE ~1000 Hz → motors`, all
onboard. The previous branch streamed a bare **velocity** setpoint, bypassing PX4's position
loop and leaving the laptop to close it over WiFi (~0.7 s lag; the drone overshot goals and
fence walls).

This branch streams a **trajectory setpoint** — a reference position, the
velocity to get there, *and* the acceleration — so PX4's own position loop runs onboard
(~50 Hz, with the attitude loop below it at ~250 Hz) with feedforward, exactly like its Position flight mode. Tracking lag drops to
~0.1 s, a drone with the sticks released is held by PX4 rather than by the laptop, and a
WiFi hiccup leaves it parked on its last reference. Agility stays bounded (responsive, not
acrobatic; aerobatics would need attitude/rate streaming, which WiFi can't support).

**Safety chain, in authority order:**
1. **RC kill switch** — the only true motor cutoff.
2. **PX4 failsafes** — offboard-loss, low battery, RC override; PX4 can always fly itself.
3. **Commander fence + CBF + hold** — software velocity clips and holds, not a cutoff.

"The drone doesn't decide" holds only while everything is healthy — on any failure, deciding
snaps back onboard by design.




## Whose document is whose

There are two separate places documentation lives, written by two different groups:

**1. Written by us:** `README.md` and `CLAUDE.md` at the root, everything in
[`docs/`]() (`RUNBOOK`, `MIGRATION`, `BASESTATION`, `TELEOP`, `SCENARIOS`, `CONFIG`,
`MOCAP`, `PREFLIGHT`, `DRONE_SETUP`, `TROUBLESHOOTING`, `GLOSSARY`, `MILESTONES`), plus
`patches/` and `tools/` — our objective, our milestone structure, our lab's IPs/hardware,
our findings and fixes.

**2. Written by CMU — everything inside the [`AirStack/`](../AirStack/) folder** (a snapshot of
their code; the live working copy is `~/AirStack-starling-max2/AirStack/`). Their key guides,
well worth reading:

- [`AirStack/robot/ros_ws/src/svg_ground_control/experiment.md`](../AirStack/robot/ros_ws/src/svg_ground_control/experiment.md)
  — **CMU's maintained command reference** for the SVG ground-control experiments (Parts A–D:
  sim, real-drone bring-up, tasks, first flight). Written for CMU's three-drone rig, so
  substitute our IPs/names — and see the "corrections" tables in our docs where it disagrees
  with its own code.
- [`AirStack/robot/ros_ws/src/svg_ground_control/README.md`](../AirStack/robot/ros_ws/src/svg_ground_control/README.md)
  — CMU's package overview (architecture, scenarios, CBF, safety notes, and the
  "Update 2026-09-27" section describing this branch's flight bags).
- [`AirStack/robot/ros_ws/src/svg_ground_control/teleop.md`](../AirStack/robot/ros_ws/src/svg_ground_control/teleop.md)
  — CMU's gamepad guide (⚠️ its sign table contradicts the code — [TELEOP.md](TELEOP.md) §9).
- [`AirStack/robot/ros_ws/src/svg_ground_control/foxglove/svg-basestation/README.md`](../AirStack/robot/ros_ws/src/svg_ground_control/foxglove/svg-basestation/README.md)
  — CMU's Basestation panel manual.

When our runbooks and CMU's guide disagree, trust CMU's `experiment.md` for commands and our
documents for lab-specific substitutions and lessons learned — **except** where our
corrections tables show CMU's doc disagreeing with CMU's code; there the code wins.

