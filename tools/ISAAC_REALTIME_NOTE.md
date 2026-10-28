# Time scale (why PX4 time ≠ wall clock) — sim only

Read-only investigation 2026-10-28 (Task 8 of `docs/superpowers/plans/2026-10-28-hover-step-tools-fix.md`).
Nothing under `AirStack/` was changed; the wrapper's default behaviour is unchanged.

## What sets the sim rate here

1. **Fixed physics step.** `AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/params.py:85-88,92-95`:
   `PX4_PHYSICS_HZ` (env, default 250 → `physics_dt` 4 ms) and `PX4_RENDERING_HZ` (env, default 60).
2. **Unthrottled loop.** `launch_scripts/svg_multi_drone_single_domain.py:335-338`: `while simulation_app.is_running(): world.step(render=True)` — no sleep, no rate limiter.
3. **Lockstep.** `.../backends/px4_mavlink_backend.py:229` `enable_lockstep` defaults `True`; `:629` `_current_utime += int(dt*1e6)` with `dt` = physics dt. PX4 sets its clock from that stamp — `/isaac-sim/PX4-Autopilot/src/modules/simulation/simulator_mavlink/SimulatorMavlink.cpp:492-494` (`abstime_to_ts(&ts, imu.time_usec); px4_clock_settime(...)`) and advances one lockstep per HIL_SENSOR (`:523`).
   ⇒ **PX4 time = physics steps × 4 ms, independent of wall time.** `PX4_SIM_SPEED_FACTOR` is read only by `simulator_sih/sih.cpp:114` (PX4 v1.16.1) — it has no effect on this MAVLink/lockstep path, so there is no knob on the PX4 side.
4. **Kit default is "as fast as possible".** The headless experience `isaacsim.exp.base.python.kit` inherits `isaacsim.exp.base.kit:212` `runLoops.main.rateLimitEnabled = false` (and `:213` `manualModeEnabled = true`, `:214` `player.useFixedTimeStepping = false`).

Result in run #17: Isaac stepped faster than real time → PX4 ran **1.336× wall** (drone_2 ulog arm→disarm 100.87 s vs 75.5 s in the bag). Every wall-clock duration in that record understates vehicle time by that factor.

## How the tooling handles it (default, kept)

`tools/sim_hover_step_run.sh collect` runs `tools/hover_step_timescale.py` on the drone_1 ulog → `px4_arm_times.txt`
(`arm_s= disarm_s= interval_s= source= sysid=`, PX4 boot seconds). `tools/hover_step_analysis.py:109-114` computes
`time_scale = PX4 (arm→disarm) / bag (arm→disarm)` from the bag's MAVROS `armed` transitions and gates settle/overshoot in vehicle time;
`tools/hover_step_report.py:39` accepts `0.5 < scale < 3.0` and prints the row "time scale (PX4 s per wall s)". Missing `px4_arm_times.txt` ⇒ UNVERIFIED ⇒ INCOMPLETE.

## Can `ISAAC_KIT_ARGS` reach Kit? — yes (forwarding confirmed, effect untested)

- The wrapper appends `$ISAAC_KIT_ARGS` to the launcher command line (`tools/sim_hover_step_run.sh:26,30`).
- The launcher has no argparse of its own and builds `SimulationApp({"headless": _headless})` (`svg_multi_drone_single_domain.py:48`).
- `/isaac-sim/exts/isaacsim.simulation_app/isaacsim/simulation_app/simulation_app.py:439-440` does `argparse.ArgumentParser(add_help=False).parse_known_args()` on `sys.argv`, and `:532-533` prints
  `Passing the following args to the base kit application: …` then `args.extend(unknown_args)`. So any `--/path=value` on our line reaches Kit — the existing `--ext-folder …` argument already travels this way.
- If `--/app/runLoops/main/rateLimitEnabled=true` is present when the World is built, Isaac itself sets `rateLimitFrequency` and the timeline target to `rendering_hz` (= `PX4_RENDERING_HZ` 60) — `isaacsim.core.api/.../simulation_context.py:448-450`. An explicit `rateLimitFrequency=60` is therefore redundant but harmless.
- Expected effect: 60 renders per wall-second × (250/60 physics steps per render) × 4 ms ⇒ scale ≈ 1.00 when the machine keeps up; the limiter can only slow Isaac, never speed it. **Not run** (step 2 of the task was skipped on purpose: Isaac must stay down until the Task 10 acceptance run).

## The experiment (run later, as a separate record, not #18)

```bash
cd /home/jeremychia/AirStack-starling-max2
ISAAC_KIT_ARGS='--/app/runLoops/main/rateLimitEnabled=true --/app/runLoops/main/rateLimitFrequency=60' \
  tools/sim_hover_step_run.sh all ratelimit_probe
grep -m1 "Passing the following args" docs/record/ratelimit_probe/isaac.log   # must list the two --/app/runLoops args
cat docs/record/ratelimit_probe/px4_arm_times.txt                             # PX4 arm→disarm interval_s (vehicle s)
python3 -c "import json;j=json.load(open('docs/record/ratelimit_probe/bag_analysis.json'));print(j['time_scale'],j['time_scale_source'])"
```
Read: `time_scale` = `interval_s` from `px4_arm_times.txt` ÷ the bag's MAVROS arm→disarm interval. ≈ 1.00 ⇒ pinned; ≈ 1.3 ⇒ not pinned
(then check `isaac.log` for the "Passing the following args" line — if the args are absent, forwarding broke, not the limiter).
Afterwards `rm -rf docs/record/ratelimit_probe ~/flight_logs/sim/ratelimit_probe` (probe, not a ledger row).

## Recommendation

**Keep measuring per run** (default `ISAAC_KIT_ARGS` empty). The per-run scale is what the gates need and it also catches a slow machine (< 1.0).
Pinning is optional, opt-in via `ISAAC_KIT_ARGS` only, and must never be done by editing CMU files or the `.kit` experiences. Sim-only (CLAUDE.md rule 9).
