# PRE-FLIGHT & EMERGENCY CARD — print this, laminate it, keep it in the hangar

*(Starling Max 2 · AirStack ground control · OptiTrack mocap — details: RUNBOOK.md §B/§C)*

## Before EVERY session

- [ ] Net rigged; fence values in the config fit INSIDE it (`fence_min`/`fence_max`)
- [ ] RC transmitter ON, bound, battery OK — **thumb finds the KILL switch (ch8) blind**
- [ ] Mode switch (ch6) at **MANUAL** (low) until told otherwise
- [ ] QGroundControl open on the laptop and showing the vehicle — QGC is the ONLY
      trustworthy arming display; the ground software cannot see arming state
- [ ] Mocap bridge running (`./mocap.sh` — laptop terminal, NOT docker);
      `ros2 topic hz /drone_1/pose` ≈ 50 Hz (container)
- [ ] Drone on floor: `/drone_1/pose` z reads ≈ 0.03–0.07 m (if ~1 m: Motive origin problem — STOP)
- [ ] EKF2 fusing: `fmu/out/vehicle_odometry` position matches the pose within a few cm
- [ ] **Frame hand-check** (first flight of the day): carry North → pos[0]↑, East → pos[1]↑,
      lift → pos[2]↓ (NED). Wrong axes = DO NOT FLY
- [ ] RViz tracking the hand-carried drone (Fixed Frame `world`)
- [ ] Kill-switch ground check (after any transmitter/receiver change): props OFF,
      software takeoff, flip kill — motors cut instantly

## The moment you call `takeoff`

**Props can spin ~1.5 s after Enter.** Hands clear, kill in hand, eyes on QGC.

## Emergencies — in this order

| Situation | Action |
|---|---|
| Drone misbehaving / doubt | **1. `hold` service** — freezes in place (STILL ARMED) |
| Need it down | **2. `land` service** — 0.6 m/s descent + auto-disarm |
| Software unresponsive / drone ignoring commands / anything scary | **3. KILL SWITCH (ch8)** — instant motor cut. Do not debug a flying drone |

```
ros2 service call /swarm_commander/hold  std_srvs/srv/Trigger
ros2 service call /swarm_commander/land  std_srvs/srv/Trigger
```

## Iron rules

- **RC takeover = flip ch6 to MANUAL (low), or KILL. Never expect Position/Altitude mode
  to obey you while the commander runs** — its setpoints leak into those modes.
- A landing is not over until **QGC says DISARMED**. Check before anyone approaches.
- After ANY manual takeover: call `land` once (drone on floor) to reset the commander,
  or `takeoff` will refuse ("not IDLE").
- Geofence breach = freeze-hover, **still armed** — recover: `land` → `reset_fence`;
  it is NOT a motor cut.
- One person's job during flight is watching QGC + holding the transmitter. Only theirs.
