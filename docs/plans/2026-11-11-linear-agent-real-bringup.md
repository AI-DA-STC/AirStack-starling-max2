# Linear update — 2026-11-11, first real-drone session on the new software

Instructions for the Linear agent, in the **nearlab** workspace, project **HTX-R2 Starling Flight Bring-up (M2–M8)**. Apply every step below. Delete nothing. Use the comments exactly as written. Change no title. Check Linear before each step: if a status or comment is already in place, do not repeat it.

Everything below is the **real drone** (Starling 2 Max D0012, motion-capture positioning (mocap), AI.R STC hangar), one drone, on 2026-11-11. Where a line says "owner's report", it is the owner's statement, with no log or video behind it.

Evidence lives in the repo https://github.com/AI-DA-STC/AirStack-starling-max2 and in the laptop folder `~/flight_logs/2026-11-11/` (commander, interface and agent output of the flight).

## Part 1 · Set to Done, each with its comment

**NEAR-814 "Network: laptop on the mocap subnet (192.168.9.x) with the route to the drone subnet; drone gets its WiFi address; both ping each other"**

> Real drone, 2026-11-11. Laptop on the cable at 192.168.9.107, drone on WiFi at 10.40.2.10. Two things had to be fixed first. The laptop needed the route `10.40.2.0/23 via 192.168.9.1`, because its WiFi was on the office network. The laptop firewall blocked the drone's connection on UDP 8888 until a rule allowed 10.40.2.0/23. After that both sides ping each other and the drone link came up. The drone dials the laptop's cable address, not its WiFi address.

**NEAR-815 "Set up the upgraded Motive: calibrate (wand, ground plane, axis convention) and create the Starling rigid body"**

> Real drone, 2026-11-11. Motive 3.5.0.2 (NatNet 4.5) at 192.168.9.100, with a rigid body named drone_1. The owner recalibrated Motive during the session (owner's report). The axis check is recorded on NEAR-822.

**NEAR-818 "Re-run the drone setup script, then reboot the drone (never restart the flight software service)"**

> Real drone, 2026-11-11. `voxl_setup_real_drone.sh drone_1 192.168.9.107 1 8888` ran on the drone, then the drone was rebooted (owner's report). The drone link connected afterwards.

**NEAR-822 "Hand-carry with props off: panel tracks the drone, estimator fuses mocap"**

> Real drone, 2026-11-11. The owner carried the drone by hand with props off and checked the axes and the Foxglove view (owner's report). No numbers were recorded.

**NEAR-823 "Props-off kill switch test"**

> Real drone, 2026-11-11. Done with props off before the flight (owner's report). Earlier in the session the drone refused to arm with a kill-switch message while the switch was off. A drone reboot and a Motive recalibration cleared it (owner's report). The cause was not found.

**NEAR-825 "First flight: takeoff, hover, land"**

> Real drone, 2026-11-11, 16:57:33 to 16:59:54 (+08). First flight on this software. Config `swarm_real_ours.yaml`, scenario hover, one drone, mocap. Takeoff to (−0.5, 0, 0.5) m, "holding takeoff position" after 7 s, about 2 min 20 s in the air, then land. The commander logged touchdown and its disarm. QGroundControl showed DISARMED after landing (owner's report). No video. Two more short hover flights followed at 17:08 and 17:09, each ending in a landing and a logged disarm. Not done in any of them: the RC takeover to MANUAL and the `land` reset that this issue also asks for. The software saw no command acknowledgement from PX4 at any point (see NEAR-821). Logs: `~/flight_logs/2026-11-11/` on the lab laptop.

## Part 2 · Set to In Progress, each with its comment

**NEAR-816 "Mocap stream end to end: laptop receives it at full rate for 10 min with no stalls, it reaches the drone’s PX4, and moving the drone by hand moves the position the same way on every axis"**

> Real drone, 2026-11-11. The laptop receives the stream and forwards it to the drone's PX4 input topic. The hand check of the axes is done (owner's report). Not done: the 10-minute run with no stalls. Open point: Motive streamed at 50 Hz at the start of the session and at 240 Hz later. The flights in September used 50 Hz. The rate for flying is not decided.

**NEAR-817 "Record the new Motive version, IP and streaming settings in the lab docs and pictures"**

> 2026-11-11. Recorded in the repo: Motive PC 192.168.9.100, Motive 3.5.0.2, NatNet 4.5, broadcast (docs/CONFIG.md and mocap/motion_capture.yaml, change CHG-0056). Not done: the streaming rate (see NEAR-816), the firewall and route steps, and the pictures.

## Part 3 · Comment only, status unchanged

**NEAR-819 "Confirm the drone ID matches the controller’s target"**

> 2026-11-11. Not confirmed yet. The interface ran with target_system=1 and the drone armed and flew, which suggests the ids match. `MAV_SYS_ID` has not been read back in QGroundControl.

**NEAR-820 "Confirm only one connection watchdog runs on the drone"**

> 2026-11-11. Not checked. The setup script installed and started `svg-microdds-watchdog` today. Whether the older `voxl-dds-retry` service is also running on this drone was not looked at.

**NEAR-821 "Check the controller’s messages match the drone’s PX4 version"**

> 2026-11-11. Finding: this drone does not publish the command-acknowledgement topic (`fmu/out/vehicle_command_ack` is absent from its topic list). The interface therefore logged no acknowledgement for any arm, takeoff or disarm command, on refused attempts and on the successful flight alike. The rule "no acknowledgement means the drone id is wrong" cannot be used on this drone.

## Part 4 · M4 goal flights

**NEAR-829 "Goal legs on the speed-limited profile".** Set the status to **In Progress**, and add this comment:

> Real drone, 2026-11-11, 17:13:21 to 17:14:29 (+08). First goal flight on this software. Config `goal_single_ours.yaml`: speed 1.0 m/s, acceleration 3.0 m/s², fence `keep_in` ±2 m. After takeoff and Start, three goals were sent from the Foxglove panel at 0.5 m height: x = 1.00, then x = −1.00, then x = 2.00. The drone flew each one (owner's report; the commander logged each goal). No position recording was made, so the shape of the speed profile is not measured yet. That is why this stays In Progress. An earlier goal sent during a hover flight was ignored: the commander takes goals only in the goal scenario, and the panel does not warn about it.

**NEAR-830 "Measure braking at the fence walls".** Leave the status unchanged. Add this comment:

> Real drone, 2026-11-11, 17:14:24 (+08). Observation, not a measurement. The third goal was x = 2.00, which is on the fence wall (fence x max = 2.0 m). Six seconds after it was sent the commander logged "drone_1 outside the fence (x>max), keep_in pushing it back". So at 1.0 m/s the drone went past the wall before it was pushed back. How far it went was not recorded. The owner landed five seconds later.

## Part 5 · Write the sync record

Write a Markdown file named `2026-11-11-linear-synced.md`. State only what Linear now holds:

- the title and status of NEAR-814 to NEAR-825, NEAR-829 and NEAR-830;
- each comment added here, and whether it was added now or already present;
- the progress of milestones R1, M2, M3 and M4;
- anything not applied, and why;
- the totals per project for **all three** projects (HTX-R1, HTX-R2 and HTX-R3): total, Backlog, In Progress, Done, Canceled.
