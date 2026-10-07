# Glossary

**Who this is for:** anyone new to the project (or new to drones/mocap/ROS) who hits an
unfamiliar term in [README.md](../README.md), [RUNBOOK.md](RUNBOOK.md), [MOCAP.md](MOCAP.md), or
any other doc here. Plain-English, lab-specific — not a general robotics reference. Linked
from every doc; add a term here rather than re-explaining it inline elsewhere.

- **Mocap (motion capture)** — using cameras to track an object's position/orientation in
  real time. Here it replaces GPS, which doesn't work indoors.
- **Rigid body** — a named, tracked object in Motive (e.g. the drone) made of reflective
  markers whose fixed arrangement lets Motive report one position + orientation for it.
- **NatNet** — OptiTrack's network protocol for streaming mocap poses out of Motive. Our
  Motive **broadcasts** it rather than multicasting (see below) — see [MOCAP.md](MOCAP.md) §3.
- **Multicast vs broadcast** — two ways to send one stream to many receivers. Multicast is
  addressed to a special "join this group" address (what OptiTrack's own NatNet SDK expects);
  broadcast is addressed to everyone on the subnet whether they asked or not (what our Motive
  actually does). The mismatch is why we run our own bridge instead of the stock SDK.
- **Motive** — OptiTrack's mocap server software, running on the Windows PC wired to the
  ceiling cameras. Calibrates the cameras, defines rigid bodies, and streams NatNet.
- **EKF2** — PX4's onboard state estimator (Extended Kalman Filter). Fuses sensor inputs
  (here: mocap pose, standing in for GPS/vision) into the drone's belief about its own
  position, velocity, and orientation.
- **External vision** — the EKF2 input class that mocap poses arrive as; PX4 treats our
  bridge exactly like a vision system reporting position, not like GPS.
- **Offboard mode** — a PX4 flight mode where an external computer (our laptop) streams
  setpoints that PX4 must receive continuously (≥2 Hz; we send 20 Hz) or it fails safe. On
  this branch the setpoint is a *trajectory setpoint* (below), not a bare velocity. See the
  primer in [README.md](../README.md) for the full control-loop picture.
- **Trajectory setpoint** — the message the commander now sends to a real drone instead of a
  bare velocity: one PX4 `TrajectorySetpoint` carrying a reference **position**, the
  **velocity** to get there and the **acceleration**, so PX4 closes the position loop onboard
  (~0.1 s lag instead of ~0.7 s) and a drone with released sticks is held by PX4, not by the
  laptop. Topic `/{name}/fmu/trajectory_command`; needs a rebuilt `px4_interface`.
- **Acceleration feedforward** — telling PX4 not just where to go and how fast but how hard
  to accelerate or brake *right now*, so it reacts in the same control tick instead of
  waiting for its velocity loop to notice the error. Used by the goal profile, the stick
  ramp, the keep-in wall and CBF corrections.
- **Reference point / leash** — the commander's "where I told you to be", integrated from
  the velocity it actually published. The **leash** (`goal_lead_m`, `teleop_lead_m`,
  `hold_lead_m`) stops that reference running away from a drone that is being held back,
  horizontally and vertically separately. [TELEOP.md](TELEOP.md) §7.
- **MANUAL mode** — the RC pilot flies with raw stick input; no autopilot assistance. The
  only mode to flip into for a manual takeover — never Position or Altitude (see below).
- **POSITION mode** — PX4 holds/moves to a position using its own state estimate and sticks
  as position/velocity commands; an onboard, self-contained mode (not offboard).
- **ALTITUDE mode** — like Position mode but only altitude is held automatically; horizontal
  movement is manual, unassisted by position hold.
- **NED vs ENU** — two 3D axis conventions. PX4/MAVLink internally use **N**orth-**E**ast-
  **D**own; ROS conventionally uses **E**ast-**N**orth-**U**p. Bridges and drivers must
  convert between them, or axes end up flipped/rotated.
- **DDS** — the pub/sub messaging layer under ROS 2 (and under PX4's uXRCE-DDS link). Nodes
  discover each other automatically over the network rather than connecting point-to-point.
- **DDS domain (domain ID)** — an isolation number: only DDS participants on the same domain
  ID see each other, so multiple independent ROS 2/PX4 systems can share one network without
  crosstalk. Ours is **1**; each additional drone in the lab must get its own unique ID (see
  [CONFIG.md](CONFIG.md)).
- **uXRCE-DDS / MicroXRCEAgent** — PX4's lightweight DDS bridge for small/embedded devices.
  The **client** is built into PX4 firmware on the drone; the **MicroXRCEAgent** program runs
  on the laptop and translates between that client and full ROS 2 DDS.
- **QoS best-effort vs reliable** — a DDS delivery guarantee setting. Reliable retransmits
  lost messages; best-effort doesn't bother, favoring low latency (right for a live pose/
  setpoint stream, wrong when you need every message). PX4's `/fmu/*` topics publish
  best-effort, so tools like `ros2 topic echo`/`hz` need `--qos-reliability best_effort`
  explicitly or they see nothing.
- **Isaac Sim** — NVIDIA's GPU simulator that AirStack spawns SITL drones in. Needed for
  every multi-drone rehearsal; never started for a real-drone session.
- **SITL** (Software-In-The-Loop) — real PX4 autopilot firmware flying a simulated aircraft
  instead of real motors/sensors. Used for the sim milestone — same commands as the real drone.
- **adb** (Android Debug Bridge) — the command-line tool used to shell into the Starling's
  onboard Linux computer (which runs a VOXL/Android-derived stack) over USB or network.
- **Geofence** — a software position box (`fence_min/max`) enforced by the ground-station
  commander, with two behaviours chosen by `fence_behavior`. It is a velocity clip or a hold,
  never a motor cutoff. See the safety chain in [README.md](../README.md)'s primer and
  [TELEOP.md](TELEOP.md) §6.
- **`hold_all`** — geofence behaviour: any policed drone outside the box latches the fence
  and **every** drone freezes in a hover until `~/reset_fence`. The only behaviour on the
  previous branch. Now also triggered by an airborne RC-flown drone.
- **`keep_in`** — the other geofence behaviour: nobody freezes; each commanded drone's
  outward speed is capped by a **braking envelope** so it stops *at* the wall (cruise until
  the true braking distance for `fence_brake_accel_mps2`, then brake, with the deceleration
  fed forward to PX4). A drone already outside is pushed back in.
- **Teleop fence** — a second, smaller box (`teleop_fence_min/max`) that only the hand-flown
  drone sees; must sit inside the geofence or the commander refuses to launch. Amber in the
  Basestation 3D view.
- **CBF (Control Barrier Function)** — a math safety filter sitting between the commanded
  velocity and what is sent, which rewrites the commands of all drones together so every pair
  keeps `2 × cbf_safety_radius_m` apart. `cbf_alpha` sets how early it starts yielding;
  `cbf_max_speed_mps` caps everything it outputs; all three are tunable in flight. A drone
  that is **CBF-exempt** or **external** (RC-flown) is a *fixed row*: modelled as going where
  it will actually go, never corrected, and the others absorb the whole dodge. Two fixed rows
  get **no** protection from each other. [SCENARIOS.md](SCENARIOS.md) §1–2.
- **Fixed row** — a drone the CBF may not adjust because its velocity is what it will
  actually fly: an RC-flown (external) or CBF-exempt drone. The others absorb 100 % of the
  dodge instead of half. Two fixed rows have **no** mutual protection.
- **Arena (`arena_low` / `arena_high`)** — the box a scenario samples its goals and initial
  layout inside. It is NOT the geofence and nothing checks one against the other — set it by
  hand to fit the net.
- **Emergency push-apart** — the CBF's fallback when the solver cannot satisfy every pair:
  every movable drone is pushed straight away from its nearest neighbour. Red note on the
  Basestation, all LEDs red — land and investigate.
- **External drone** — a drone the commander tracks (as a CBF obstacle and a fence trigger)
  but never commands; the role for an RC-flown intruder. May not also be CBF-exempt.
- **Formation profile** — a named set of per-drone goals in the config (`formation_<name>`);
  publishing the name on `/svg/formation_command` retargets the whole swarm at once; `next`
  cycles through them. Only honoured by the `goal` scenario.
- **Random goals (`random_goals`)** — a scenario that gives every drone a fresh random goal
  inside the `arena` box each time it arrives, so drones keep crossing paths — the CBF stress
  test. It ignores goal/speed/formation commands. [SCENARIOS.md](SCENARIOS.md) §7.
- **Squeeze** — the three-drone scenario: two holders keep station while an intruder (scripted
  or hand-flown, CBF-exempt) pushes between them and the holders must yield.
- **Kill switch** — the one true motor cutoff: an RC transmitter channel (ours: ch8) that
  disarms the motors in hardware, outranking software, PX4 failsafes, and everything else.
- **Foxglove / SVG Basestation** — Foxglove Studio is the ROS visualisation app (desktop or
  browser); the **SVG Basestation** is CMU's custom panel for it: mission chip, command
  buttons, live CBF gains, per-drone state table, link health, battery — plus a 3D view with
  the fence boxes. Together they replace RViz as the operator view. [BASESTATION.md](BASESTATION.md).
- **Foxglove bridge** — the ROS 2 node (`foxglove_bridge`, port 8765) that serves every topic
  and service on the domain to Foxglove Studio over a WebSocket, so Studio never has to speak
  DDS. Started by the commander launch; Studio connects to `ws://localhost:8765`.
- **Swarm commander** — the ground-side node (`swarm_commander`) that owns every drone's
  flight state, publishes their setpoints, enforces the fence and the CBF, and exposes the
  `takeoff`/`start`/`hold`/`land`/`reset_fence` services. Everything the operator commands
  goes through it.
- **Scenario** — the behaviour the commander runs after `start`: `hover`, `goal`,
  `antipodal`, `head_on`, `squeeze`, `random_goals`. Set in the config yaml or with
  `scenario:=` on the launch. A scenario that does not read goal commands ignores them
  **silently**. [SCENARIOS.md](SCENARIOS.md) §4.
- **ROS 2 service / parameter** — a *service* is a request/reply call to a node
  (`takeoff`, `land` — each gets an accept/reject answer, which can itself be lost on a bad
  link); a *parameter* is a named runtime value on a node (`cbf_alpha`), settable live with
  `ros2 param set` or, for the CBF gains, from the Basestation's slider.
- **Status snapshot (`/svg/commander_status`)** — a JSON message the commander publishes at
  5 Hz with every drone's state, position, odometry freshness and last command outcome, the
  fence and CBF settings, and the last lifecycle command. The Basestation's only source of
  mission truth, and the first thing to `ros2 topic echo` when something is odd.
- **tmux `bringup` session** — the one container tmux session `./airstack.sh connect robot`
  attaches to: 8 panes, pane 0 top-left for the main launch, 1–7 pre-sourced shells. It
  survives closing the terminal and replaces the old "one terminal per step".
- **`safe_teleop`** — the gamepad teleop node that replaced `keyboard_teleop`: controller
  profiles (`xbox_usb`, `dragonrise_usb`), a wrong-axis-map guard, a left-stick lock, stale-pad
  → zero command. It moves the commander's reference point; the hold is the commander's.
  [TELEOP.md](TELEOP.md).
- **`/joy` / `joy_node`** — `joy_node` is the stock ROS 2 driver that turns a USB gamepad
  into `/joy` messages (axes + buttons, nothing drone-specific). It runs **inside the robot
  container**, never on the laptop (a Humble host and the Jazzy container cannot read each
  other's messages).
- **Controller profile** — one entry in `safe_teleop/controllers.py` naming the driver node,
  axis numbers, signs and lock button for one kind of pad (`xbox_usb`, `dragonrise_usb`);
  `teleop_controller` selects it. Wrong profile = the axis guard refuses to command.
- **Analog trigger / deadzone** — on many generic pads the shoulder triggers appear as *axes*
  that read **+1.0 untouched**; pointing a velocity axis at one would command full speed with
  nothing held, so `safe_teleop` refuses any mapped axis resting past ±0.9. The **deadzone**
  (0.15) is the slop around centre treated as zero, rescaled so full deflection still reaches 1.0.
- **Coast distance** — how far a hand-flown drone keeps travelling after the sticks are
  released: the command ramps down at `teleop_accel_mps2` and the reference may lead by
  `teleop_lead_m` (≈ 2 m from 4 m/s at 5 m/s²; far less at our 0.5 m/s cap — M5 measures it).
- **Position mode (teleop)** — the sticks command a velocity of the *reference point*, and the
  drone is flown to it; release the sticks and it holds. Not nose-relative — axes are fixed to
  the room (ENU).
- **`target_system` / `MAV_SYS_ID`** — the MAVLink system id a command is addressed to
  (`target_system`, a `px4_interface` parameter) versus the id the drone actually has
  (`MAV_SYS_ID`, a PX4 parameter). They must match or PX4 silently ignores every command and
  sends no ack. Unique per drone.
- **Command ACK (`VehicleCommandAck`)** — PX4's per-command verdict (ACCEPTED / DENIED /
  TEMPORARILY_REJECTED / …), now logged by `px4_interface` and shown in the Basestation's
  Interface column. A verdict on one command, **not** a state report — it is not an arming
  indicator. No ack at all = `target_system` mismatch.
- **LED strip / `svg-led`** — 11 RGBW NeoPixels on the ESC LED output, driven by a daemon on
  the VOXL over plain UDP: green by default, red while the CBF corrects that drone, any colour
  on command. Mutes PX4's own ESC status LEDs, so they no longer show arm state.
  [BASESTATION.md](BASESTATION.md) §8.
- **ESC / NeoPixel / RGBW** — the ESCs are the motor driver boards; on this airframe they
  also drive the LED strip output. NeoPixels are individually addressable LEDs on one data
  wire; RGBW adds a white element. Ours: 11 pixels on the ESC LED output.
- **SoC / sag / RTB** — battery terms on the Basestation's power card: **SoC** (state of
  charge) is the remaining percentage; **sag** is how far pack voltage drops under load
  against the session's peak (big sag on a fresh pack = tired battery); **RTB** (return to
  base) is the reserve needed to fly home and land — `RTB NOW` when SoC reaches it.
- **SLPI flight core** — the DSP coprocessor on the VOXL2 that runs PX4's sensor drivers.
  `systemctl restart voxl-px4` can leave it dead on this drone (QGC "params missing", sensor
  topics never publish) — hence "always reboot after provisioning".
- **uXRCE watchdog (`svg-microdds-watchdog`)** — a systemd service the new provisioning script
  installs on the drone to restart the PX4 DDS client if it dies mid-session. Overlaps our
  earlier `voxl-dds-retry.service`; keep one.
- **STE** — the lab's flight site, where every stage of this branch is validated. "⏳ STE"
  in a doc = exists in code, not yet observed by us.
- **diffaero** — the learned end-to-end flight policy on the archived branch
  (`daniel/diffaero_ground_control`). Never used by this lab; absent on the new branch.
- **Sibling branches** — two git branches that fork from the same commit and go different
  ways, neither containing the other's work. Our previous and current AirStack branches are
  siblings (common ancestor `a46f04b`), which is why the docs forked rather than updated.
  [MIGRATION.md](MIGRATION.md) §1.

- **IDLE / ARMING / ASCEND / ACTIVE / LANDING** — the swarm commander's per-drone flight
  states (shown as chips in the Basestation). `takeoff` only accepts drones in IDLE; after an
  RC takeover the commander is stuck non-IDLE until you call `land` once. Only ACTIVE drones
  are fence-clipped or CBF-exempt-able.
- **hover_positions** — per-drone x,y,z in the config yaml: the takeoff destination AND the
  initial goal, in absolute mocap coordinates. Place the drone at/near its x,y before takeoff.
  (Ignored by `random_goals`, which picks its own layout.)
