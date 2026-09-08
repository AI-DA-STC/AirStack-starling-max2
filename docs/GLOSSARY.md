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
  setpoints (we stream velocity) that PX4 must receive continuously (≥2 Hz; we send 20 Hz) or
  it fails safe. See the primer in [README.md](../README.md) for the full control-loop picture.
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
- **SITL** (Software-In-The-Loop) — real PX4 autopilot firmware flying a simulated aircraft
  instead of real motors/sensors. Used for the sim milestone — same commands as the real drone.
- **adb** (Android Debug Bridge) — the command-line tool used to shell into the Starling's
  onboard Linux computer (which runs a VOXL/Android-derived stack) over USB or network.
- **Geofence** — a software position boundary enforced by the ground-station commander. A
  breach **freezes the drone in a hover at its current position** — it is a hold, not a
  motor cutoff. See the safety chain in [README.md](../README.md)'s primer.
- **CBF (Control Barrier Function)** — a math safety filter sitting between the commanded
  velocity and what actually gets sent to the drone; it clips/adjusts unsafe commands (e.g.
  ones that would breach the geofence) rather than passing them through unmodified.
- **Kill switch** — the one true motor cutoff: an RC transmitter channel (ours: ch8) that
  disarms the motors in hardware, outranking software, PX4 failsafes, and everything else.

**IDLE** — the swarm commander's "parked" state for a drone. `takeoff` only accepts drones
in IDLE; after an RC takeover the commander is stuck non-IDLE until you call `land` once.

**hover_positions** — per-drone x,y,z in the config yaml: the takeoff destination AND the
initial goal, in absolute mocap coordinates. Place the drone at/near its x,y before takeoff.
