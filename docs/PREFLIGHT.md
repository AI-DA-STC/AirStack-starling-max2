# PRE-FLIGHT & EMERGENCY CARD — v2026-11-14 — print this, laminate it, keep it in the hangar

> **DO · WORLD: REAL DRONE — this card gates every takeoff.** This stack bypasses AirStack's `drone_safety_monitor`: **PX4's failsafes plus the RC kill switch are the entire safety net.** Reprint the card whenever the version above changes.

*(Starling Max 2. AirStack `yikuan/SVG_ground_control_dev` @ `b21d28c`. OptiTrack mocap. Details: RUNBOOK.md §B/§C. First real flights on this software: 2026-11-11 (one drone: hover, goal legs) and 2026-11-12 (two drones, collision filter observed: RUNBOOK.md C9). Gamepad: one flight each on 2026-11-13. One drone alone (ledger #36). One drone hand-flown toward a hovering one (ledger #37). See RUNBOOK.md B9 and B10. Not flown: the pad unplugged in flight, formations, random goals. Hazards: docs/projects/HTX-R2.md "Before the next real flight".)*

## Before EVERY session

- [ ] **No sim on the network:** Isaac container not running (`docker ps | grep isaac` empty), no `mavros_node` and no `svg_teleop` in `ros2 node list` — the sim shares DDS domain 1 and the `/drone_1` topic names with the real drone
- [ ] Net rigged; BOTH fence boxes in the config fit INSIDE it (`fence_min`/`fence_max`, and `teleop_fence_*` inside those); `fence_behavior` known (`hold_all` freezes · `keep_in` brakes)
- [ ] Config is OURS, not CMU's (`swarm_real_ours.yaml` / `goal_single_ours.yaml` / `goal_two_ours.yaml` / the file `tools/real.sh teleop` made): `drone_names` lists exactly the drones on the floor (`drone_1` or `drone_2` alone, both in `goal_two_ours.yaml`), nobody CBF-exempt, `land_speed_mps` 0.6, `cbf_max_speed_mps` ≤ 1.0 for now (**it is the ONLY speed limit** — the drone's PX4 limits allow 20 m/s), `scenario` is `hover`/`goal`, `land_settle_s` **0.0** (the flown landing) until the settle is its own M3 sub-test
- [ ] Drone params come from `starling_1_indoor_params.params` / QGC ONLY — never from the sim airframe (`10090_pegasus_starling2max`: rate gains ×0.5, gyro filters 80/40, `LNDMC_ROT_MAX` 300 are **sim-only — never port to the drone**; the real drone keeps `LNDMC_ROT_MAX` 30)
- [ ] Drone on the floor: mocap z of the rigid body **< 0.15 m** (`land_complete_altitude_m`) — a floor offset above that and the commander never calls a landing done (PX4 still lands and auto-disarms; relaunch the commander)
- [ ] RC transmitter ON, bound, battery OK — thumb finds KILL (ch8) blind (RC: ch5 arm · ch6 mode MANUAL/POSITION/OFFBOARD · ch8 KILL)
- [ ] Mode switch (ch6) at **MANUAL** (low) until told otherwise
- [ ] QGroundControl open, showing every vehicle in the session (both, for two drones). No two-drone takeoff until QGC lists both. QGC is the ONLY trustworthy arming display (the Basestation's Interface column is an ACK log, not an arming display)
- [ ] Mocap bridge running with every drone flown (`MOCAP_BODIES="drone_1 drone_2" ./mocap.sh` for both, `tools/real.sh teleop` prints the line for one — laptop terminal, NOT docker);
      `ros2 topic hz /drone_1/pose` and `ros2 topic hz /drone_2/pose` ≈ 240 Hz each (container)
- [ ] Every drone on the floor: `/drone_1/pose` and `/drone_2/pose` z read ≈ 0.03–0.07 m (if ~1 m: Motive origin problem — STOP)
- [ ] **Each drone ON its own takeoff point**, nose toward +x: compare `/drone_1/pose` and `/drone_2/pose` x,y with the config's `hover_positions` before `takeoff` (takeoff flies a straight line to that absolute point — iron rule 10)
- [ ] EKF2 fusing: `fmu/out/vehicle_odometry` position matches the pose within a few cm
- [ ] **Frame hand-check** (first flight of the day, and after ANY Motive recalibration or ground-plane change): North → pos[0]↑, East → pos[1]↑, lift → pos[2]↓ (NED). Wrong axes = DO NOT FLY
- [ ] Basestation open (`ws://localhost:8765`): banner `EKF EV FUSED`, mission chip `ON GROUND` (never `NO COMMANDER`), one row per drone flown (`drone_1`, `drone_2`), each `IDLE · odom fresh · cmdr`, 3D view tracks the hand-carried drone inside the fence box
- [ ] LED strip (if fitted): steady green before arming — it does NOT show arm state
- [ ] Interface startup line `target_system=N` equals `MAV_SYS_ID` read back in QGC (no ACK on `arm` = mismatch — do not fly)
- [ ] Gamepad session only: Logitech F310 back switch on **X**, MODE light **off**, `tools/real.sh teleop drone_2` ended `PAD CHECK: PASS` (not `STATIC PASS`) — **never press MODE** after that. A `drone_1` session uses `drone_1` in these lines (re-run it after a container restart or pad replug)
- [ ] Gamepad session only: `teleop_max_speed_mps` ≤ 0.5. The drone can overshoot that cap by about a third ([#36](record/LEDGER.md))
- [ ] Gamepad session only: pad pane (pane 5) running, no `REFUSING TO COMMAND` in it, and `ros2 topic hz /svg/drone_2/teleop_command` ≈ 20 Hz before `takeoff`. **No warning appears if it stops**: the drone then holds as if the sticks were centred ([#36](record/LEDGER.md))
- [ ] Gamepad session only: pad pane (pane 5) started BEFORE the commander (pane 3) and **kept open until QGC says DISARMED**
- [ ] Gamepad session only: teleop fence drawn to our net AND inside the geofence (amber box visible in the 3D view) when the config enables it (`teleop_real_ours.yaml` does, `goal_two_ours.yaml` does not); yaw-sign plan agreed OUT LOUD — first yaw input slow, low, thumb on KILL
- [ ] Two drones, one flown by hand: read the stop table in RUNBOOK.md B10 before `takeoff` (letting go when the filter resists, and the CBF radius: hazards 10 and 8 in docs/projects/HTX-R2.md)
- [ ] Kill-switch ground check (after any RC change, and once after the branch switch): props OFF, software takeoff, flip kill — motors cut instantly

## The moment you call `takeoff`

**Props can spin ~1.5 s after Enter.** Hands clear, kill in hand, eyes on QGC. Everyone outside the net from `takeoff` until QGC says DISARMED.

## Emergencies — in this order

| Situation | Action |
|---|---|
| Drone misbehaving / doubt | **1. `hold` service** (or panel **Hold All**) — brakes to a stop point just AHEAD and holds there (STILL ARMED) |
| Need it down | **2. `land` service** (or panel **Safety Stop**, two clicks) — descends at `land_speed_mps` (CONFIG.md) + auto-disarm |
| Software unresponsive / drone ignoring commands / anything scary | **3. KILL SWITCH (ch8)** — instant motor cut. Do not debug a flying drone. Afterwards call `land` once (iron rule 3). `land` brings down every airborne drone, including the one you did not kill |
| Mocap/poses stop while AIRBORNE | `land` NOW (or KILL). Never debug a flying drone |
| Log says `CBF emergency push-apart engaged` | `land` and investigate — the collision filter went infeasible (goals or posts closer than 2 × safety radius). Never exempt two drones from the CBF at once; the random-goal `arena` box is NOT the geofence and nothing checks one against the other |
| Basestation says `NO COMMANDER` while AIRBORNE | the commander process died — PX4 holds the last reference for a moment, then offboard-loss failsafe: **KILL or MANUAL takeover now** |
| Pad disconnects while hand-flying | expected from the code, not flown: the drone holds where it is (stale pad = zero command). `land` from a shell or the panel |

```
ros2 service call /swarm_commander/hold  std_srvs/srv/Trigger
ros2 service call /swarm_commander/land  std_srvs/srv/Trigger
```

## Iron rules (numbered as in CLAUDE.md)

<!-- IRON_RULES:BEGIN -->
<!-- canonical text lives in docs/PREFLIGHT.md; CLAUDE.md carries a byte-identical copy; tools/docs_check/check_docs.sh diffs the two blocks -->
1. **RC takeover = flip ch6 to MANUAL (low), or KILL (ch8) — never Position/Altitude.** The commander's setpoints leak into those modes (its trajectory setpoint is still consumed in POSCTL/ALTCTL; re-observed at the first flight, NEAR-825 — docs/projects/HTX-R2.md).
2. **A landing is not over until QGC says DISARMED** — check before anyone approaches. The commander's log and the panel's Interface column are ACK logs, not arming displays. Landed but still ARMED after ~10 s → flip KILL (harmless on the ground) or arm switch (ch5) down. (The commander's disarm is a normal PX4 disarm — PX4 refuses it unless its land detector says landed, so it cannot drop a flying drone.)
3. **After ANY manual takeover or RC KILL: call `land` once** (drone on the floor) to reset the commander, or `takeoff` will refuse ("not IDLE") (re-observed at NEAR-825). After a KILL the commander keeps sending setpoints until `land` is called (ledger #34).
4. **Never run `test/functional_*.py` with the real stack up** — they publish fake odometry on live topics (`squeeze`, `squeeze_lag`, `fence`, `single_goal`, `multi_goal`, `hybrid`).
5. **Software is BLIND to PX4 arming state** (v1.14 px4_msgs mismatch) — fly with QGC visible. A `PX4 ack: ACCEPTED` means "PX4 heard me", never "armed"; **no ACK at all = `target_system` ≠ the drone's `MAV_SYS_ID`** — do not fly until fixed. The ACK message itself is unaudited against v1.14 until docs/PX4_MSGS_AUDIT.md is re-run (NEAR-821).
6. **Lab WiFi SSIDs (`motive`, `StarlingMax2`) are OPEN** — never bridge the lab network to the internet.
7. **After re-provisioning the drone (`voxl_setup_real_drone.sh`): REBOOT it** — never `systemctl restart voxl-px4` (it leaves the SLPI flight core dead: "params missing", sensors never publish).
8. The shipped configs are CMU's bench values, not ours — fly the `_ours` yamls. Traps at b21d28c: `goal_single.yaml` still exempts drone_1 from the CBF, flies 10 m/s and lands at 0.8; `goal_tracking.yaml`/`goal_sequence.yaml` carry `cbf_max_speed_mps 10.0`; CMU's real configs leave `land_settle_s` unset (→ 2.0 s default). The 10-07 traps (drone_2, random_goals) are gone since the 10-20 bump.
9. **Sim-only — never port to the drone:** the sim PX4 airframe `10090_pegasus_starling2max` (roll and pitch rate gains × 0.5, yaw rate gains 0.25 / 0.2 — real 0.07 / 0.5, `MC_YAW_TQ_CUTOFF` 15, `LNDMC_ROT_MAX` 300 — real 30, motor lag off, MPC speed limits 20 / 6 / 1000 / 10 / 4), the sim stack's MAVROS respawn, and `cbf_sim.yaml`'s speeds 2.0 / 4.0 / 6.0 with its landing settle 2.0 s + disarm retry. The drone's parameters come from `starling_1_indoor_params.params` / QGC only; the real `_ours` configs fly `drone_1`, `land_settle_s` 0.0, `land_speed_mps` 0.6, `cbf_max_speed_mps` 1.0. Lines in the airframe marked `# = real` match the drone's file; copying them from the drone to the sim is fine, the other direction is not.
10. **Takeoff point and watcher.** Each drone stands on its own takeoff point (the config's `hover_positions`), nose toward +x: `takeoff` flies a straight line to that point (ledger #34), and the fence does not act during the climb (docs/projects/HTX-R2.md, hazard 7). A second person watches `drone_1`'s front-right motor every time `drone_1` takes off: it failed or started late in 5 of 7 arms on 2026-11-12, cause unknown (docs/projects/HTX-R2.md, hazard 6).
<!-- IRON_RULES:END -->
- Fence `hold_all` breach = freeze-hover, **still armed** — recover: `land` → `reset_fence`; `keep_in` = brakes at the wall, nothing latches. Neither is a motor cut.
- One person's job during flight is watching QGC + holding the transmitter. Only theirs.
