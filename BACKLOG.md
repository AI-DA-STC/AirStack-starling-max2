# BACKLOG — designed but deliberately NOT implemented

> Three `swarm_commander.py` fixes were fully designed on 2026-09-03 (from flight-log
> forensics of the 09-01→03 sessions) and then **shelved by lab decision** after the
> `land_speed_mps 0.3→0.6` config change proved sufficient. This file preserves the
> designs so a future implementer doesn't re-derive them.
> **Revisit triggers:** any landing that leaves the drone armed on the ground · any move
> to multi-drone ops · wanting yaw control for camera-forward flight.
> All targets are in `AirStack/robot/ros_ws/src/svg_ground_control/` (Python edits need no
> rebuild — symlink-install — just Ctrl-C + relaunch the commander).

## Why these exist (the verified problems)

1. **Premature one-shot disarm** (`swarm_commander.py` ~736-741): on `land`, the commander
   sends ONE non-forced DISARM the instant mocap z ≤ 0.15 m — while still ~15 cm up and
   descending, so PX4 always denies it ("Disarming denied, not landed"). It then flips to
   IDLE and **stops streaming**, and whether the drone ends up disarmed depends on a race:
   PX4 flies the stale descent setpoint for ~1 s (`COM_OF_LOSS_T`); if its land detector
   (0.5 s of sustained low thrust) latches inside that window → auto-disarm ✅; if the gear
   bounces → offboard-loss → POSCTL fallback → hover-ish thrust on the ground → **armed
   forever** ❌. `land_speed 0.6` biases the race heavily toward ✅ but doesn't remove it.
2. **Control-authority leak**: the commander streams setpoints forever, and PX4 v1.14
   consumes `trajectory_setpoint` even in POSCTL/ALTCTL — so RC takeover is only clean
   into MANUAL (or kill). Also, any RC takeover leaves the commander stuck non-IDLE
   (fixed today by the "call `land` once" ritual).
3. **No yaw control**: the commander always publishes `angular.z = 0`; goals' orientation
   is ignored. The drone holds its takeoff heading for the whole flight.

**Hard constraint for all fixes:** the ground software CANNOT read PX4 state on this drone
(`vehicle_status` undecodable — px4_msgs v1.15 vs voxl-px4 v1.14). No `is_armed`, no
`nav_state`. Everything must be open-loop timers + explicit services, never mode-reactive.
Also: `px4_interface`'s `disarm()` service **always returns success** (fire-and-forget, no
ack check) — retries cannot be response-driven.

## Fix 1 — `LANDED_SETTLE` state (deterministic landing disarm)

- New `FlightState.LANDED_SETTLE` between LANDING and IDLE (enum at lines 69-74).
- Touchdown branch (~736-741) rewrite: on z ≤ `land_complete_altitude_m`, do NOT disarm —
  enter LANDED_SETTLE, record `settle_start`.
- While settling: **keep streaming ZERO velocity** (drone pressed on the ground at low
  thrust, still in offboard → land detector reliably latches; PX4's own auto-disarm
  usually fires right here). Publish raw zeros **bypassing the CBF** (a neighbor landing
  nearby must not make a grounded drone thrust); keep the drone in `positions` so others
  still avoid it.
- After `land_settle_duration_s` (default 3.0): send DISARM `disarm_retry_count` (3) times,
  `disarm_retry_period_s` (1.0) apart — open-loop (see constraint). Then IDLE, stop
  streaming, log honestly ("disarm sequence complete", not "disarmed").
- New params: `land_settle_duration_s`, `disarm_retry_count`, `disarm_retry_period_s`,
  reserve `land_settle_descent_mps` (default 0.0; small downward push if bench tests show
  zeros don't latch on bouncy gear).
- New `DroneHandle` fields: `settle_start`, `disarm_attempts`, `last_disarm_time`.
- Interactions (audited): fence must NOT freeze a settling drone (it only polices ACTIVE —
  already true); `hold`/`land` must not accept a settling drone (they list ASCEND/ACTIVE —
  already true); `takeoff` refused for ~6 s post-touchdown (acceptable, self-documenting).
- Safety floor: only non-forced disarms — an actually-airborne drone (bad mocap z) is
  simply denied, never dropped. Worst case = today's failure mode, never worse.
- Tests: all `test/functional_*.py` assert DISARM **membership** in commands_received, so
  retries are assertion-safe; first DISARM arrives 3 s later (timeouts have 20 s margin).
- Bench: props off, strapped — land on bench (immediate settle, count 3 disarms on
  `/drone_1/fmu/in/vehicle_command`, motors stop); hold-in-hand land (all 3 denied,
  commander still exits cleanly to IDLE); re-takeoff after.

## Fix 2 — `~/release` Trigger service (clean RC handover)

- Register next to takeoff/start/hold/land/reset_fence (~line 390).
- Handler: `mission_active=False`; for every drone: state=IDLE, clear arming/settle
  bookkeeping, `hold_target = takeoff_target.copy()`; `scenario.reset()` (add a 3-line
  `reset()` to `GoalScenario` restoring stashed initial goals — the only `scenarios.py`
  touch). Single-threaded executor ⇒ publishing stops on the next tick, no flag needed.
- Response/log must warn: *"setpoint stream stopped; PX4 (if in offboard) hits
  offboard-loss in ~1 s and falls back per COM_OBL_RC_ACT (=1 → Position). Be ready on RC."*
- Do NOT touch `fence_breached` (that's `~/reset_fence`'s job); do NOT send any disarm.
- Also fixes: post-RC-takeover stuck-non-IDLE (release resets to IDLE — replaces the
  "call land once" ritual).
- Consider pairing with a `px4_interface.cpp` heartbeat timeout (stop publishing
  `offboard_control_mode` when no setpoint for >0.5 s — also fixes "commander crash leaves
  drone in offboard with stale setpoints"): members + ~6 lines in
  `interface/px4_interface/src/px4_interface.cpp` (~205, ~507), needs `bws`.
- Bench: takeoff on bench → `release` → `topic hz` on the setpoint goes silent within a
  tick → QGC shows offboard-loss → Position → RC responds → `takeoff` accepted again.

## Fix 3 — param-gated yaw control

- Interface side already wired: `px4_interface.cpp:279` maps `twist.angular.z` → PX4
  `yawspeed` (with ENU→NED negation).
- Params: `yaw_control_enabled` (default **False** — zero behavior change until enabled),
  `yaw_kp` (1.0), `yaw_rate_max_rps` (0.5).
- `odometry_callback`: extract yaw from the quaternion → `drone.yaw`.
- `goal_callback`: if the goal's quaternion is valid and non-identity, store
  `desired_yaw` (identity/zero → None — every existing xyz-only publisher stays inert).
- Publish loop: only when enabled AND state==ACTIVE AND desired_yaw set:
  `angular.z = clip(yaw_kp * wrap_pi(desired_yaw - yaw), ±yaw_rate_max_rps)`; all other
  states publish 0 (takeoff/land stay yaw-quiet). CBF is 3-DOF linear — untouched.
- Optional mode: `yaw_follow_velocity` — face direction of travel via `atan2(vy, vx)`.
- Bench: enabled, armed, props off, strapped: 90° yaw goal → `angular.z` clamps at +max
  with correct sign; rotate the drone by hand toward the target → `angular.z` ramps to 0,
  no sign flip. Then disable the param → exactly 0 with a yawed goal.

## Order & effort

Fix 1 → Fix 2 (release must clear Fix 1's new fields) → run the sim functional tests →
Fix 3 as its own revertable commit. Roughly 15 / 25 / 30 lines respectively, one file each
(plus the optional px4_interface heartbeat pair for Fix 2).
