RECORD · REAL DRONE — nothing on this software has flown. Every result cell on this page is `—` until a LEDGER row with REAL exists; the archived tables are observations on the previous software, not results. Codes, titles and "Done when" are Linear's, verbatim.

# HTX-R2 Starling Flight Bring-up (M2–M7)

Question: Does the same software fly real Starling 2 Max drones safely with motion-capture positioning (mocap)? · Where: mocap room · [Linear project](https://linear.app/nearlab/project/htx-r2-starling-flight-bring-up-m2-m7-269b3d72d5ce) · Linear snapshot: 2026-10-26 · Evidence: [LEDGER](../record/LEDGER.md) · Every flight follows [PREFLIGHT.md](../PREFLIGHT.md).

## Before the next real flight

Hazards the pilot assumes until the named issue re-earns them (iron rules in [PREFLIGHT.md](../PREFLIGHT.md)):

1. Software is blind to PX4 arming; the command-ACK message is unaudited against PX4 v1.14 — [PX4_MSGS_AUDIT.md](../PX4_MSGS_AUDIT.md), re-run at NEAR-821. Fly with QGC visible.
2. fly `_ours` configs (shipped real ones carry 0.3); `land_speed_mps` must stay 0.6 — 0.3 left the drone armed on the ground ([A21](../record/LEDGER.md#table-2--observed-on-the-previous-software-archived)); the landing is re-earned at NEAR-826.
3. Drone ID must equal the controller target (`MAV_SYS_ID` = `target_system`; no ACK at all = mismatch) — NEAR-819; exactly one uXRCE watchdog on the drone — NEAR-820.
4. After `voxl_setup_real_drone.sh`: reboot, never `systemctl restart voxl-px4` — NEAR-818.
5. RC takeover is MANUAL or KILL only: setpoints leak into POSCTL/ALTCTL (confirmed in the code 2026-10-29, accepted; iron rule 1), and the commander stays non-IDLE after a takeover (`land` once; iron rule 3). No issue of their own; re-observed at NEAR-825 ([PX4_MSGS_AUDIT.md](../PX4_MSGS_AUDIT.md)).

## Carried over from the previous software — verdicts the pilot assumes until re-observed

| Hazard (observed on the previous software) | What changed on this software | Re-earned by |
|---|---|---|
| Control-authority leak: RC takeover only clean into MANUAL (setpoints leak into POSCTL/ALTCTL) | Confirmed in current code 2026-10-29 and ACCEPTED by the owner: takeover is MANUAL or KILL; see note below | NEAR-825 (re-observed; no issue of its own) |
| Commander touchdown disarm is a premature one-shot (one red QGC message per landing) | `px4_interface` logs the DENIED ack; `land_settle_s` + disarm retry exist (sim-closed, #13) | NEAR-826 |
| Commander stuck non-IDLE after any RC takeover (`land` once to reset) | `takeover_twins` + reference re-seed on `hold`/`land` are new; stuck-state logic unchanged | NEAR-825 (no issue of its own) |
| `test/functional_*.py` publish fake odometry on real topics | six scripts now (`squeeze`, `squeeze_lag`, `fence`, `single_goal`, `multi_goal`, `hybrid`) — same hazard | iron rule 4 — every session (no Linear issue) |
| PX4 v1.14 vs px4_msgs mismatch (`vehicle_status` echo silent; software blind to arming) | `VehicleCommandAck` newly subscribed; `TrajectorySetpoint`/`OffboardControlMode` acceleration newly populated | NEAR-821 ([audit](../PX4_MSGS_AUDIT.md)) |
| `land_speed_mps` 0.6 (0.3 left the drone armed on the ground) | shipped configs carry 0.3 / 0.8 / 1.0; our `_ours` configs carry 0.6 — fly those, change deliberately | NEAR-826 |
| WiFi reboot-persistence, drone IP drift, NatNet on WiFi | unchanged | NEAR-814, NEAR-816 |

Leak detail: `px4_interface` publishes the trajectory setpoint ungated, and PX4 v1.14's position controller takes the latest sample in POSCTL/ALTCTL. Takeover is MANUAL or KILL; the panel's stop is the software-side stop. Iron rule 1 stands.

### R1 · New mocap and network pipeline — REAL DRONE, mocap hardware, no flight
Linear (snapshot 2026-10-26): 0 % · no ledger row on this software
Done when (Linear, verbatim): Motive calibration, ground plane, axes and rigid body are configured; full-rate streaming lasts 10 minutes without stalls; laptop/drone communicate both ways; PX4 receives correct-axis mocap; settings are documented.

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-814 | Network: laptop on the mocap subnet (192.168.9.x) with the route to the drone subnet; drone gets its WiFi address; both ping each other | — | — |
| NEAR-815 | Set up the upgraded Motive: calibrate (wand, ground plane, axis convention) and create the Starling rigid body | — | — |
| NEAR-816 | Mocap stream end to end: laptop receives it at full rate for 10 min with no stalls, it reaches the drone’s PX4, and moving the drone by hand moves the position the same way on every axis | — | laptop-side loopback with a fake Motive: [#14](../record/LEDGER.md) (sim, not the real stream) |
| NEAR-817 | Record the new Motive version, IP and streaming settings in the lab docs and pictures | — | — |

Observed on the previous software (archived branch `archive/airstack-starling-max2`, 2026-07-20 → 09-03) — observations, not results on this software ([LEDGER table 2](../record/LEDGER.md#table-2--observed-on-the-previous-software-archived)):

| A# | Observed | Re-earned by |
|---|---|---|
| A2 | desk prep: host networking, NTP, NatNet ports clear (2026-07-21) | NEAR-814 |
| A3 | natnet ↔ Motive connected at 50 Hz (2026-07-22) | NEAR-816 |
| A4 | drone on lab WiFi, survives reboot (2026-07-22) | NEAR-814 |
| A8 | drone WiFi moved to a space-free SSID (2026-08-11) | NEAR-814 |
| A13 | mocap poses on the laptop via `./mocap.sh` at 50 Hz (2026-08-28) | NEAR-816 |
| A16 | frame hand-check, axes correct (2026-08-28) | NEAR-816 |

Decisive check: `./mocap.sh check` → `./mocap.sh` → `ros2 topic hz /drone_1/pose` (50 Hz) → panel EKF `EV FUSED` before any arming ([MOCAP.md](../MOCAP.md)). The laptop must sit on 192.168.9.x: NatNet is multicast and never crosses the router.

### M2 · Drone setup and hand-carry, propellers off — REAL DRONE, props off
Linear (snapshot 2026-10-26): 0 % · no ledger row on this software
Done when (Linear, verbatim): drone ID matches controller target, only one watchdog runs, estimator fuses mocap, the panel tracks the hand-carried drone correctly, and kill switch is checked props-off.

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-818 | Re-run the drone setup script, then reboot the drone (never restart the flight software service) | — | — |
| NEAR-819 | Confirm the drone ID matches the controller’s target | — | — |
| NEAR-820 | Confirm only one connection watchdog runs on the drone | — | — |
| NEAR-821 | Check the controller’s messages match the drone’s PX4 version | — | [PX4_MSGS_AUDIT.md](../PX4_MSGS_AUDIT.md) (2026-08-11 audit; re-run method) |
| NEAR-822 | Hand-carry with props off: panel tracks the drone, estimator fuses mocap | — | — |
| NEAR-823 | Props-off kill switch test | — | — |

NEAR-818 — gate: `voxl_setup_real_drone.sh drone_1 <LAPTOP_IP> 1 8888` then `reboot` (never `systemctl restart voxl-px4`: it leaves the SLPI flight core dead) — [DRONE_SETUP.md](../DRONE_SETUP.md) §4.
NEAR-819 — gate: read `MAV_SYS_ID` back in QGC before the first arm (the 2026-09-04 export says 1, a 2026-09-18 note says 2); the `px4_interface` startup line must read `target_system=N` with the same N (`target_systems:=2` if the read-back says 2); no ACK at all = mismatch.
NEAR-820 — gate: `systemctl status svg-microdds-watchdog` and `systemctl status voxl-dds-retry` — keep ONE, record which in [CONFIG.md](../CONFIG.md); both together is untested.

Observed on the previous software (archived branch `archive/airstack-starling-max2`, 2026-07-22 → 08-28) — observations, not results on this software ([LEDGER table 2](../record/LEDGER.md#table-2--observed-on-the-previous-software-archived)):

| A# | Observed | Re-earned by |
|---|---|---|
| A5 | PX4 topics on the laptop over WiFi, 24 `/drone_1/fmu/*` topics (2026-07-22) | NEAR-818 |
| A6 | EKF2 params applied via QGC (2026-07-29) | NEAR-822 |
| A7 | onboard VIO off, verified by read-back (2026-08-11) | NEAR-818 |
| A9 | drone re-pointed at the laptop IP, microdds client connected (2026-08-11) | NEAR-818 |
| A10 | PX4 topics re-verified on the new network (2026-08-11) | NEAR-818 |
| A11 | `vehicle_status` ~30 Hz but echo silent (2026-08-11) | NEAR-821 |
| A12 | QGC connected drone → Mocap PC (2026-08-11) | NEAR-822 |
| A14 | EKF2 fuses the mocap pose within ~2 cm (2026-08-28) | NEAR-822 |
| A15 | RViz tracks the hand-carried drone (2026-08-28) | NEAR-822 |

### M3 · First flight on the new software — REAL DRONE
Linear (snapshot 2026-10-26): 0 % · no ledger row on this software
Done when (Linear, verbatim): every command is acknowledged; landing settles and disarms; dummy-payload hover yields hover throttle and flight time.

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-824 | Preflight card dry run with the new software | — | — |
| NEAR-825 | First flight: takeoff, hover, land | — | — |
| NEAR-826 | Landing test: settle on the ground, then disarm | — | — |
| NEAR-827 | Weigh the flight-ready drone and fit a dummy payload mass | — | — |
| NEAR-828 | Dummy-payload hover: hover throttle and flight time to 20 % battery | — | — |

NEAR-825 — also re-observes: RC takeover to MANUAL mid-hover, land by hand, `land` once to reset the commander (iron rules 1, 3); every command ACK seen in the Interface column; a `DENIED` = PX4 refused, no entry = `target_system` mismatch.
NEAR-826 — sub-test (from the retired M3 procedure): fly `land_settle_s` 0.0 (what `swarm_real_ours.yaml` ships) until two landings end DISARMED in QGC; then set 2.0 live (`ros2 param set /swarm_commander land_settle_s 2.0`), land twice more, expect `touchdown … settling 2.0 s` then `landed, disarmed (attempt 1)` and QGC DISARMED within ~3 s, no re-climb; only then put 2.0 in the real config. The disarm retry cannot engage on real (`px4_interface.disarm()` returns true on send) — the `px4_interface` ACK log is the only evidence.

Observed on the previous software (archived branch `archive/airstack-starling-max2`, 2026-09-01 → 03) — observations, not results on this software ([LEDGER table 2](../record/LEDGER.md#table-2--observed-on-the-previous-software-archived)):

| A# | Observed | Re-earned by |
|---|---|---|
| A17 | first offboard flight: takeoff + hover under the commander, manual landing (2026-09-01) | NEAR-825 |
| A21 | landing auto-disarm at `land_speed_mps` 0.6; 0.3 left the drone armed (2026-09-03) | NEAR-826 |

Decisive check in hover: `ros2 topic hz /drone_1/fmu/trajectory_command` ≈ 20 Hz ([RUNBOOK.md](../RUNBOOK.md) §B step 8).

### M4 · Goal flights with the braking fence — REAL DRONE
Linear (snapshot 2026-10-26): 0 % · no ledger row on this software
Done when (Linear, verbatim): goal legs use the smooth speed-limited profile; wall braking distance is measured; gains change live; hold stops the drone where expected.

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-829 | Goal legs on the speed-limited profile | — | — |
| NEAR-830 | Measure braking at the fence walls | — | — |
| NEAR-831 | Change gains live from the panel in flight | — | — |
| NEAR-832 | Check where a hold stops the drone | — | — |

Observed on the previous software (archived branch `archive/airstack-starling-max2`, 2026-09-03; freeze-fence, not the braking fence) — observations, not results on this software ([LEDGER table 2](../record/LEDGER.md#table-2--observed-on-the-previous-software-archived)):

| A# | Observed | Re-earned by |
|---|---|---|
| A18 | single-goal flight, drone flew to the goal and held | NEAR-829 |
| A19 | multi-goal square, 2 laps, all corners tracked | NEAR-829 |
| A20 | deliberate fence breach → freeze-hover, recovery clean | NEAR-830 |

Decisive check: wall test — goal 0.5 m past the `keep_in` wall at low speed: cruise, brake, stop, `fence_breached` stays `false` ([RUNBOOK.md](../RUNBOOK.md) §C). Config `goal_single_ours.yaml`.

### M5 · Gamepad flying on the real drone — REAL DRONE
Linear (snapshot 2026-10-26): 0 % · no ledger row on this software
Done when (Linear, verbatim): yaw direction is correct (not proved by sim), the gamepad fence holds, stick release holds position, and coast distance is measured.

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-833 | Check the yaw stick turns the drone the right way, slowly and low | — | — |
| NEAR-834 | Gamepad fence test | — | — |
| NEAR-835 | Release-to-hold test and coast distance | — | — |

Decisive check: yaw stick 10 % for one second, low, thumb on KILL; wrong way → land, flip `yaw_sign`, relaunch ([TELEOP.md](../TELEOP.md) §2, §5). Config `teleop_real_ours.yaml`.

### M6 · LED strips — REAL DRONE, cosmetic
Linear (snapshot 2026-10-26): 0 % · no ledger row on this software · starts when the strip arrives
Done when (Linear, verbatim): LED service runs on the drone; green by default, red when collision avoidance acts; motor LEDs muted.

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-836 | Fit the LED strip and start the LED service on the drone | — | — |
| NEAR-837 | Check green / red behaviour in flight | — | — |

Decisive check: `scripts/voxl_push_led.sh drone_1 <DRONE_IP>` then on the drone `systemctl status svg-led` → `opened … sink`, `PX4 ESC LED bits muted` ([BASESTATION.md](../BASESTATION.md) §8). The ESC LEDs then no longer show arm state — QGC is the arming display.

### M7 · Multi-drone — REAL DRONE, needs the new Starlings
Linear (snapshot 2026-10-26): 0 % · no ledger row on this software
Done when (Linear, verbatim): formations, random goals with collision avoidance and intruder-squeeze tests fly.

| Issue | Title (Linear, verbatim) | Result | Evidence |
|---|---|---|---|
| NEAR-838 | Check the hardware order went out (Starlings, 2 stereo cameras, LED strip, 2.4 GHz radio) | — | — |
| NEAR-839 | Set up each new Starling (one at a time, setup guide) | — | — |
| NEAR-840 | Two drones: formation and random goals with collision avoidance | — | — |
| NEAR-841 | Three drones: intruder-squeeze test | — | — |

Each airframe: unique `MAV_SYS_ID` / `target_system`, DDS domain and Motive body ([DRONE_SETUP.md](../DRONE_SETUP.md)); procedures and safety briefs in [SCENARIOS.md](../SCENARIOS.md) §6–8 (sim-validated in HTX-R1 only).
