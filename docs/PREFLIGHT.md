# PRE-FLIGHT & EMERGENCY CARD — print this, laminate it, keep it in the hangar

*(Starling Max 2 · AirStack `yikuan/SVG_ground_control` · OptiTrack mocap — details: RUNBOOK.md §B/§C · ⏳ STE since 2026-10-07)*

## Before EVERY session

- [ ] Net rigged; BOTH fence boxes in the config fit INSIDE it (`fence_min`/`fence_max`, and `teleop_fence_*` inside those); `fence_behavior` known (`hold_all` freezes · `keep_in` brakes)
- [ ] Config is OURS, not CMU's: `drone_1` (not `drone_2`), `land_speed_mps` 0.6, `cbf_max_speed_mps` ≤ 1.0 for now, `scenario` is `hover`/`goal` (not `random_goals`)
- [ ] RC transmitter ON, bound, battery OK — thumb finds KILL (ch8) blind (RC: ch5 arm · ch6 mode MANUAL/POSITION/OFFBOARD · ch8 KILL)
- [ ] Mode switch (ch6) at **MANUAL** (low) until told otherwise
- [ ] QGroundControl open, showing the vehicle — the ONLY trustworthy arming display (the Basestation's Interface column is an ACK log, not an arming display)
- [ ] Mocap bridge running (`./mocap.sh` — laptop terminal, NOT docker);
      `ros2 topic hz /drone_1/pose` ≈ 50 Hz (container)
- [ ] Drone on floor: `/drone_1/pose` z reads ≈ 0.03–0.07 m (if ~1 m: Motive origin problem — STOP)
- [ ] Drone placed at/near the config's `hover_positions` x,y (takeoff flies to that absolute point)
- [ ] EKF2 fusing: `fmu/out/vehicle_odometry` position matches the pose within a few cm
- [ ] **Frame hand-check** (first flight of the day): North → pos[0]↑, East → pos[1]↑, lift → pos[2]↓ (NED). Wrong axes = DO NOT FLY
- [ ] Basestation open (`ws://localhost:8765`): banner `EKF EV FUSED`, mission chip `ON GROUND` (never `NO COMMANDER`), `drone_1` row `IDLE · odom fresh · cmdr`, 3D view tracks the hand-carried drone inside the fence box
- [ ] LED strip (if fitted): steady green before arming — it does NOT show arm state
- [ ] Interface startup line `target_system=N` equals `MAV_SYS_ID` read back in QGC (no ACK on `arm` = mismatch — do not fly)
- [ ] Gamepad session only: pad plugged in BEFORE the commander, identified (`joy_map`), `teleop_controller` matches it, no `REFUSING TO COMMAND` in the teleop log, `teleop_max_speed_mps` ≤ 0.5
- [ ] Gamepad session only: teleop fence drawn to our net AND inside the geofence (amber box visible in the 3D view); yaw-sign plan agreed OUT LOUD — first yaw input slow, low, thumb on KILL
- [ ] Kill-switch ground check (after any RC change, and once after the branch switch): props OFF, software takeoff, flip kill — motors cut instantly

## The moment you call `takeoff`

**Props can spin ~1.5 s after Enter.** Hands clear, kill in hand, eyes on QGC.

## Emergencies — in this order

| Situation | Action |
|---|---|
| Drone misbehaving / doubt | **1. `hold` service** (or panel **Hold All**) — brakes to a stop point just AHEAD and holds there (STILL ARMED) |
| Need it down | **2. `land` service** (or panel **Safety Stop**, two clicks) — descends at `land_speed_mps` (CONFIG.md) + auto-disarm |
| Software unresponsive / drone ignoring commands / anything scary | **3. KILL SWITCH (ch8)** — instant motor cut. Do not debug a flying drone |
| Mocap/poses stop while AIRBORNE | `land` NOW (or KILL). Never debug a flying drone |
| Basestation says `NO COMMANDER` while AIRBORNE | the commander process died — PX4 holds the last reference for a moment, then offboard-loss failsafe: **KILL or MANUAL takeover now** |
| Pad disconnects while hand-flying | drone holds position by itself (stale pad = zero command) — `land` from a shell or the panel |

```
ros2 service call /swarm_commander/hold  std_srvs/srv/Trigger
ros2 service call /swarm_commander/land  std_srvs/srv/Trigger
```

## Iron rules (numbered as in CLAUDE.md)

1. **RC takeover = flip ch6 to MANUAL (low), or KILL** — never expect Position/Altitude to obey while the commander runs (its setpoints leak into those modes)
2. A landing is not over until **QGC says DISARMED**. Check before anyone approaches. Landed but still ARMED after ~10 s → flip KILL (harmless on the ground) or arm switch (ch5) down.
3. After ANY manual takeover: call `land` once (drone on floor) to reset the commander, or `takeoff` will refuse ("not IDLE").
4. Never run `test/functional_*.py` with the real stack up — fake odometry on live topics.
5. Software still cannot see arming. A `PX4 ack: ACCEPTED` means "PX4 heard me", never "armed"; **no ack at all** = `target_system` wrong — do not fly until fixed.
6. Lab WiFi is OPEN — never bridge the lab network to the internet.
7. After re-provisioning the drone: **reboot it**, never `systemctl restart voxl-px4`.
8. The shipped configs are CMU's, not ours — `drone_1`, `land_speed_mps` 0.6, fences to our net, speeds down, before any flight.
- Fence `hold_all` breach = freeze-hover, **still armed** — recover: `land` → `reset_fence`; `keep_in` = brakes at the wall, nothing latches. Neither is a motor cut.
- One person's job during flight is watching QGC + holding the transmitter. Only theirs.
