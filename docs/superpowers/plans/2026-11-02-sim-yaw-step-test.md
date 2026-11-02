# Sim yaw-step test + yaw-gain retune (`tools/sim.sh test yaw_step`, NEAR-789) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (one executor per task, a reviewer per task) or superpowers:executing-plans. Each task is self-contained: read only what it names. Steps use `- [ ]` syntax.

**Goal:** One command (`tools/sim.sh test yaw_step --issue NEAR-789 <run>`) flies one sim drone (flat world, `teleop_single.yaml`), fires N yaw pulses in both directions through the commander's teleop input WITHOUT the keyboard, measures the heading ring-down after every release from the PX4 ulog in **vehicle time** (overshoot, ring frequency, settle to ±2°, peak yaw rate, xy drift), shows heading live in the plot window, and writes a ledger-grade record. The same run can carry a **gain sweep** (MC_YAW_P / MC_YAWRATE_P/I/D set live over MAVROS between pulse groups), so the owner picks the sim-only yaw gains from one record and the chosen values go into the sim airframe file with a comment in the style of the existing rate-gain comment.

**Architecture (3 sentences):** The existing front door, library and record renderer are reused unchanged in shape: `tools/sim.sh test` → `tools/lib/stack.sh` phases → the test's five files under `tools/sim_tests/yaw_step/` → `tools/lib/report.py` + `gates.py`. Two generic extensions carry the test: the stack learns the drone count from `test.env` (`NUM_ROBOTS`, default 3) and passes `FLY_ARGS` to `fly.sh`; the shared metrics library learns heading (odometry quaternion → ENU yaw) so the live window and the bag recompute can show it. Vehicle-time numbers come from a new pure-Python module `tools/live/yaw_core.py` over a CSV that `tools/live/ulog_yaw_dump.py` (pyulog, host-first) writes from drone_1's ulog in the `collect` phase — the same ulog `copy_ulogs` already saves to `~/flight_logs/sim/<run>/` before Isaac stops.

**Tech stack:** bash (host), Python 3 + numpy + matplotlib + pyulog on the host (`python3 -m unittest discover -s tools/tests`, no pytest; pyulog verified importable on this host 2026-11-02), Python 3 + rclpy + rosbag2_py inside `airstack-robot-desktop-1` (every exec via `docker exec … bash -ic`), PX4 SITL v1.16.1 in `isaac-sim`.

## Global constraints (copied rules)

- Repo: `/home/jeremychia/AirStack-starling-max2` (live clone, branch `main`). Read `CLAUDE.md` first (iron rules; rule 9: sim-only settings never go to the real drone). **Never push.** Commits are made in this clone by the executors. The owner's untracked root files (`QGroundControl-x86_64.AppImage`, `starling max2 voxl setup.txt`) and `docs/record/sim_hover_step_run4/` are not ours — leave them alone.
- `AirStack/` is CMU's tree: edits only as owner-approved patches. **Exception already established:** the sim PX4 airframe `AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max` is ours and sim-only (commits 2a70731, d739a73, 7032af4; `docs/MIGRATION.md`, `docs/CONFIG.md` "Sim airframe"); changing its yaw gains is approved by the owner as sim-only. Nothing else under `AirStack/` is touched (TEST_STANDARD rule 12: flight logic lives in `fly.sh`).
- Docs: the owner wants to be ASKED before doc pages are edited. Doc edits are only in the final task, marked "needs owner OK", naming the pages. Executors of Tasks 1–5 touch no file under `docs/` except this plan's sibling `docs/record/<run>/` outputs written by a run, and nothing in `docs/record/LEDGER.md` or project pages.
- Test design: `docs/TEST_STANDARD.md` (one front door `tools/sim.sh test <name>`, five-file contract under `tools/sim_tests/<name>/`, live plot window, record via `tools/lib/report.py`, ledger auto-numbered). Patterns: `tools/sim_tests/crossing/`, `tools/sim_tests/_template/`, `tools/README.md`, `tools/lib/stack.sh`, `tools/live/metrics_core.py`, and the legacy hover/step test (`tools/sim_hover_step_run.sh`, `tools/hover_step_*.py`) for vehicle-time measurement from the ulog.
- Python tests: `python3 -m unittest discover -s tools/tests` (no pytest on the host). TDD: write the failing test first, run it, watch it fail, then implement. No test may start a sim run or reach real docker (`tools/tests/test_sim_sh.py` guard: fake `docker` first on PATH, throwaway HOME).
- `tools/sim.sh check` and the pre-commit hook (`tools/git-hooks/pre-commit`: docs check when `docs/|tools/` staged, unit tests, `sim.sh check`) must pass at every commit. The hover driver (`tools/sim_hover_step_run.sh`) and the crossing test keep working at every commit (defaults stay 3 drones).
- Executors never start Isaac Sim or any docker container that runs the sim. The owner runs the flights ("Owner session" below).
- Sim-only labelling (iron rule 9) in every record line, test.env line and comment this plan writes.

## Deviation from TEST_STANDARD rule 4, stated once

Rule 4 says gates read `metrics.csv` (what the owner watched). Here the **time** gates (settle, ring frequency, peak rate) read the PX4 ulog in vehicle time, because the heavy-world sessions ran at 0.36× real time and the flat-world runs at 1.32× (ledger #17–#19): a wall-clock settle time means nothing. The ulog is the standard the hover/step test already set (`tools/hover_step_timescale.py`). The **amplitude** gate (overshoot in degrees, time-scale-free) is read from the ulog AND recomputed from `metrics.csv`; the two must agree within 1.0° per pulse or the overshoot gate is UNVERIFIED (same rule as the crossing's live-vs-bag cross-check). The live window still shows exactly the headline series (`heading_rel_deg`) and the ±2° band. This is the smallest deviation that keeps the five-file contract: no sixth file, no new flag; one generic dumper in `tools/live/` that every test may use.

## Facts verified by reading code (2026-11-02)

| Fact | Where |
|---|---|
| Teleop input topic `/svg/{name}/teleop_command`, type `geometry_msgs/msg/TwistStamped`; `twist.linear` = room-frame (ENU) m/s, `twist.angular.z` = yaw rate rad/s passed raw (no clip) to PX4; stale after `teleop_timeout_s` 0.5 s → yaw_rate 0 | `swarm_commander.py:444` (`teleop_topic_template`), `:894-897` (subscription, role `teleop`), `:1415-1421` (`teleop_callback`), `:2248-2253`, `:2306` (`msg.twist.angular.z = float(yaw_rate)` on the velocity output) |
| Sim route after release: velocity output sends `angular.z = 0`; the trajectory (real) route adopts and holds `teleop_yaw_hold = yaw_of(drone.orientation)` | `swarm_commander.py:2277-2290` |
| Teleop is honoured only when `state == ACTIVE and mission_active` (i.e. after `/swarm_commander/start` is accepted); `start` refuses until every commanded drone is ACTIVE ("not all drones holding yet") | `swarm_commander.py:2097`, `:1566-1591` |
| `teleop_single.yaml`: `drone_names: ["drone_1"]`, `teleop_drones: "drone_1"`, `scenario: "hover"`, `hover_positions: [0,0,1.2]`, `drone_position_offsets: [0,0,0]`, `teleop_max_speed_mps: 2.0`, teleop fence `[-3,-1.5,0.3]..[3,1.5,2.5]`, geofence `[-4,-2,0]..[4,2,3]`; header says "Spawn the sim with NUM_ROBOTS=1 and run launch_sim_interfaces.sh 1" | `AirStack/robot/ros_ws/src/svg_ground_control/config/teleop_single.yaml` |
| MAVROS interface (patch 0007): `FRAME_LOCAL_NED`, `type_mask` ignores P/AF/YAW, `msg.yaw_rate = cmd->twist.angular.z`; MAVROS converts ENU→NED (commit 02cce03 check: ENU yaw_rate 0.3 → NED yaw_rate −0.3) | `mavros_interface.cpp:480-497`; `git show 02cce03` |
| Sim airframe yaw gains = real drone's: `MC_YAWRATE_P 0.07 / I 0.5 / D 0.0 / K 1.0`, `MC_YAW_P 2.8`; rate gains ×0.5 comment block is the style to copy | `AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max:38-60`; `starling_1_indoor_params.params:524-532` |
| Sim plant: `k_m = 5.38697e-8` (yaw torque only from rotor drag), motor lag 0 (`STARLING_MOTOR_TAU`), `MC_YAWRATE_MAX` 200 in the sim ulog header (real 150) | `starling2max.py:14-20`; ulog `sim_crossing_run2/drone_1_sysid2_18_32_18.ulg` initial_parameters |
| PX4 ulog topics logged by this SITL (rates from the same ulog): `vehicle_local_position` ~84 Hz (`x y z heading`), `vehicle_angular_velocity` ~96 Hz (`xyz[2]`), `vehicle_attitude_setpoint` 20 Hz (`yaw_sp_move_rate`, `q_d[0..3]`), `vehicle_rates_setpoint` 50 Hz (`yaw`), `trajectory_setpoint` 5 Hz (`yawspeed`), `vehicle_local_position_setpoint` 10 Hz (`yawspeed`), `vehicle_status` ~2 Hz (`arming_state`); `ULog.changed_parameters` lists live `(timestamp_us, name, value)` | pyulog on the host over that ulog |
| Isaac launcher reads `NUM_ROBOTS` (default 3); drone i spawns at `x = 2(i−1) − (NUM_ROBOTS−1)` → one drone at the origin | `svg_multi_drone_single_domain.py:81,157` |
| MAVROS param services present live: `/drone_1/interface/mavros/param/pull` (`mavros_msgs/srv/ParamPull {force_pull}`), `/drone_1/interface/mavros/param/set`, `/drone_1/interface/mavros/param/set_parameters`, `/drone_1/interface/mavros/param/get_parameters`; `ros2 param get /drone_1/interface/mavros/param MC_PITCHRATE_P` prints `Double value is: 0.0320…` | `docs/record/sim_crossing_dry1/params_mavros_names.txt`, `docs/record/sim_crossing_run2/params_mavros.txt`, `stack.sh params()` |
| Shared library 3-drone hard-codes to generalise: `stack.sh:23` (`NUM_ROBOTS=3` in `ISAAC_CMD`), `:24` (`launch_sim_interfaces.sh 3`), `:131-133`, `:146-147`, `:176` (`["IDLE"] * 3`), `:212` (sysids `2|3|4`), `:266`, `:307`; `isaac()` `NEED=3`; `sim.sh:260` (`for N in 1 2 3` armed_post); `report.py:98` (`parse_armed_post` needs drones 1–3), `:127-137` (`x3`), `:144-147`, `:168` (`sysid 2/3/4`) | grep 2026-11-02 |
| `cmd_test` sources `test.env` AFTER `parse_test_args`, so a `USE_STUDIO=false` line in `test.env` overrides the window-mode default (no Basestation Studio) | `tools/sim.sh` `cmd_test`, lines "source … test.env; ISSUE=$ISSUE_ARG" |
| metrics node: `Frame` has `pos`, `vel` only (no orientation); `on_odom` passes `(p.x,p.y,p.z)`, `(v.x,v.y,v.z)`; `bag_recompute` the same; `status_line` prints `min_d`/`run_min` from the `running_min` series (None → "nan") | `metrics_core.py:55-66`, `metrics_node.py` `on_odom`/`status_line`, `bag_recompute.py` loop |
| `copy_ulogs` saves `~/flight_logs/sim/<run>/drone_1_sysid2_<basename>.ulg` BEFORE Isaac stops; `collect` then calls `ulog_header_params` (PARAM_KEYS) and `px4_arm_times_of` (vehicle-time arm/disarm) | `stack.sh copy_ulogs/ulog_header_params/px4_arm_times_of`, `sim.sh cmd_test` step 7 |
| Keyboard yaw at full stick = `safe_teleop` `yaw_rate_rad_s` default 1.0 rad/s (57 °/s) | `safe_teleop/teleop_node.py:106`, `velocity.py:95` |

**UNVERIFIED (no running container today; the executor of the named task verifies first and records the answer in the task's commit message):**
- U1 `mavros_msgs/srv/ParamSetV2` field names (expected `bool force_set, string param_id, rcl_interfaces/ParameterValue value → bool success, rcl_interfaces/ParameterValue value`) — Task 4 step 0: `docker exec airstack-robot-desktop-1 bash -ic 'ros2 interface show mavros_msgs/srv/ParamSetV2'` (read-only; only when the container is already up — otherwise the fallback path `ros2 param set /drone_1/interface/mavros/param MC_YAW_P 2.0` is coded too and the live read-back decides).
- U2 Whether `ros2 param set /drone_1/interface/mavros/param <P> <v>` pushes PARAM_SET to the FCU (MAVROS 2 param plugin). Read-back after `param/pull {force_pull: true}` is the arbiter; the ulog `changed_parameters` list is the authoritative proof per pulse.
- U3 `vehicle_attitude_setpoint.yaw_sp_move_rate` equals the commanded yawspeed in offboard velocity+yaw_rate mode (expected: the position controller forwards it). Fallback pulse marker: `trajectory_setpoint.yawspeed` (5 Hz, 0.2 s resolution). Task 3's dumper writes both columns; `yaw_core` picks the finer one that shows the pulses.
- U4 Whether `MPC_YAWRAUTO_MAX` (45 °/s) or `MC_YAWRATE_MAX` (200 °/s) limits the 57 °/s offboard yaw rate — the INFO row "plateau rate measured vs commanded" answers it.
- U5 `odometry_conversion` fills `twist.twist.angular.z` (yaw rate) in `/drone_1/odometry_conversion/odometry` — the live `yaw_rate_dps` series is plotted only; gates use the ulog.
- U6 The commander's `hover` scenario with one teleop drone: `start` accepted → `mission_active` true → phase 2 in `phase_from_status` (expected from `teleop_single.yaml` header and `handle_start`); confirmed by the first run's `status_post.json`.

## Review focus (five failure modes the tests must catch)

1. **Heading wrap at ±180°.** A pulse that crosses the ±180° seam must not show a 360° "overshoot": `yaw_core.unwrap_deg` + `test_pulse_across_the_seam_has_small_overshoot` (Task 3); the live series `heading_rel_deg` is unwrapped too (`test_heading_rel_unwraps_across_pi`, Task 2).
2. **Vehicle vs wall time.** The same ring-down stretched 1/0.36 in wall time gives the same settle time in vehicle time: `test_settle_time_is_in_vehicle_time_not_wall` (Task 3) feeds `yaw_core` a CSV whose `t_s` is vehicle time and asserts the result does not change when a separate wall-stamp table is scaled; the per-pulse `time_scale` INFO row is computed, never used in a gate.
3. **A pulse that never released.** Setpoint stays non-zero to the end of the data → yaw_core returns no numbers for it (Task 3, `test_unreleased_pulse_is_unverified`); in the record the "set-0 pulses flown and analysable" row is **FAIL** (the yaw setpoint never returned to 0: a flight-side fault, executor ruling 2026-11-02), every per-pulse gate is UNVERIFIED for it (never PASS, never silently skipped) and the record names it: `test_unreleased_pulse_fails_the_flown_row_and_never_passes_a_gate` (Task 4). On the flight side `fly.sh`'s publisher sends zeros on exit/SIGTERM and the commander's 0.5 s `teleop_timeout_s` zeroes yaw anyway — `test_fly_publishes_zeros_on_exit` (Task 4, static).
4. **Missing ulog.** No `px4_drone_1.csv` (ulog lost with the containers, as on 10-30) → every vehicle-time gate UNVERIFIED → INCOMPLETE, never PASS: `test_missing_px4_csv_is_incomplete` (Task 4). `collect` prints a WARN and `caveats.txt` gets a line.
5. **Sign of yaw.** A +`angular.z` pulse (ENU, counter-clockwise) must raise ENU heading in odometry and lower NED heading in the ulog; a synthetic run with the ulog sign flipped makes the "yaw sign" gate FAIL: `test_yaw_sign_mismatch_fails` (Task 4); `yaw_core.ned_to_enu_deg` has its own unit test (Task 3).

## Proposed gates (owner decides; written in `gates.py` before the run, never moved after)

Per pulse, after release, vehicle time, judged on the pulses flown at the **booted** gains (gain set 0); each gate = worst pulse of set 0.

| Gate | Value | One-sentence physics |
|---|---|---|
| heading overshoot after release | ≤ 3.0° | at 57 °/s a 3° overrun is ~50 ms of continued turning — the lag of a well-damped loop; the owner's 8–17° ring is 3–6× that. |
| settle to ±2° of the held heading | ≤ 2.0 s (vehicle) | the hover-step bar is 3 s for a 1 m translation; a turn in place has no outer position loop to wait for, so 2 s. |
| ring: zero crossings of (heading − held) after the first return | ≤ 1 | one swing back is lag; a second crossing is a limit cycle, the owner's symptom (~0.8 Hz for 10 s). |
| peak yaw rate after release | ≤ 30 °/s | the stop must not bounce back faster than half of what was commanded (57 °/s). |
| xy drift during pulse + settle | ≤ 0.15 m | a turn in place must not move the drone more than the 1 m step is allowed to overshoot (hover-step gate 0.15 m). |
| yaw sign | ENU heading rises on a +angular.z pulse (odometry) and NED heading falls (ulog) | the two frames must disagree by exactly a sign; same sign = a frame bug, not a tuning problem. |
| booted gains = airframe file | `MC_YAW_P`, `MC_YAWRATE_P/I/D/K` in the ulog header equal the `param set-default` lines of `10090_pegasus_starling2max` | the record must prove which gains PX4 actually flew (ledger #17's lost-ulog lesson). |
| live vs ulog overshoot | per pulse within 1.0° (else the overshoot gate is UNVERIFIED) | TEST_STANDARD rule 4: what was watched is what is gated. |
| live vs bag recompute | `heading_rel_deg` Δmax ≤ 0.5°, `xy_drift_m` ≤ 0.02 m, flags by count | the standard's cross-check. |

INFO rows (never pass or fail the run): per-pulse table (onset, release, plateau °/s vs commanded 57, overshoot, settle, ring Hz, peak rate, drift, gains in force, time scale); the same table for every sweep gain set; the patch-0007 flight check (below); landing ACK log; coverage; window/samples; code that ran.

**Patch 0007 flight check — recommendation: YES, scripted, INFO only.** After the pulses: turn +90° (`angular.z = +0.5` for 3.14 s), settle 5 s, tap room-frame forward (`linear.x = +0.5` m/s for 1.5 s), settle 5 s. INFO rows from the ulog's `vehicle_local_position`: `tap direction error` = angle between the xy displacement over the tap window and room +x (ENU +x = PX4 NED +y), and `heading change during tap`. The orbit symptom (body-frame velocity before patch 0007) shows as ~90° direction error. It costs ~15 s of flight, needs no extra file, and answers the owner's "first step of the next session" (commit 02cce03). It is INFO because it is a different fault class and the owner wants to watch it on video; it can become a gate in a later test.

## Dependency graph

**T1 → T4**; **T2 independent** (parallel with T1); **T3 independent** (parallel with T1, T2); **T4 after T1, T2, T3**; **Owner session after T4**; **T5 after the owner session**; **T6 last, needs owner OK**.

---

### Task 1: One-drone stack — `NUM_ROBOTS` and `FLY_ARGS` from `test.env` (executor: **sonnet**)

**Files:**
- Modify: `tools/lib/stack.sh` (lines 23–24 `ISAAC_CMD`/`IF_CMD`; `isaac()` `NEED=3` and the `starling_cfg` check; `interfaces()` loop; `odom_gates()` loop; `commander()` python `["IDLE"] * 3`; `copy_ulogs()` sysid case and the `have` check; `status()` loop; `land_all_and_wait()` loop; `PARAM_KEYS`)
- Modify: `tools/sim.sh` (`cmd_test`: `for N in 1 2 3` armed_post loop, the `wc -l = 3` check, the `fly.sh` exec line, `cmd_setup`/`doctor` pyulog check)
- Modify: `tools/lib/report.py` (`parse_armed_post`, `isaac_rows`, `landing_rows`, `evidence_rows` take an optional drone count)
- Tests: `tools/tests/test_stack_sh.py`, `tools/tests/test_sim_sh.py`, `tools/tests/test_report.py`

**Interfaces:**
- `stack.sh`: new `NUM_ROBOTS=${NUM_ROBOTS:-3}` (set BEFORE sourcing, like `USE_STUDIO`); `DRONE_IDS=$(seq 1 "$NUM_ROBOTS")`; `SYSIDS` = 2..NUM_ROBOTS+1. `ISAAC_CMD` carries `NUM_ROBOTS='"$NUM_ROBOTS"'`; `IF_CMD` ends `launch_sim_interfaces.sh '"$NUM_ROBOTS"`; `isaac()` uses `NEED=$NUM_ROBOTS` and `[ "$n" -ge "$NUM_ROBOTS" ]`; every `for N in 1 2 3` becomes `for N in $DRONE_IDS`; the commander python gets `sys.argv[3]` = NUM_ROBOTS and checks `st == ["IDLE"] * n`; `copy_ulogs` accepts sysids in `SYSIDS` and sets `ulogs_copied.ok` when all of them are present; `PARAM_KEYS` gains `MC_YAW_P MC_YAWRATE_P MC_YAWRATE_I MC_YAWRATE_D MC_YAWRATE_K` (appended; `hover_step_report.py` reads keys by name, extra keys are harmless).
- `sim.sh cmd_test`: after `source test.env` → `NUM_ROBOTS=${NUM_ROBOTS:-3}`, `FLY_ARGS=${FLY_ARGS:-}`, written to `run_meta.txt` (`num_robots=`, `fly_args=`) by `up` (add two lines to the `run_meta.txt` block in `stack.sh up()`); the flight exec becomes `bash $S/fly.sh $DURATION_S $FLY_ARGS` (unquoted expansion on purpose: word-split args); armed_post loops `$DRONE_IDS` and the line-count check compares with `$NUM_ROBOTS`.
- `sim.sh cmd_setup`: a new line `ok "host python: pyulog"` / `warn "host python lacks pyulog (pip install pyulog) — vehicle-time gates fall back to the isaac-sim container"`.
- `report.py`: `parse_armed_post(text, n=3)` accepts exactly `drone_1..n`; `isaac_rows(rows, out, n=3)` criteria say `x{n}`; `landing_rows(rows, out, n=3)`; `evidence_rows(rows, out, heavy, bag_prefix, extra_files=(), n=3)` expects sysids `[str(s) for s in range(2, n+2)]`. Defaults keep every existing caller and record byte-identical. `gates.py` of a test passes `n=int(env.get("NUM_ROBOTS", 3))`.

- [ ] **Step 1: failing tests**

```python
# append to tools/tests/test_stack_sh.py
class OneDrone(unittest.TestCase):
    def test_default_is_three_drones(self):
        r = subprocess.run(["bash", "-c", f"{ENV}; source {LIB}; echo \"$ISAAC_CMD\"; echo \"$IF_CMD\"; echo $DRONE_IDS; echo $SYSIDS"], capture_output=True, text=True)
        self.assertIn("NUM_ROBOTS=3 ", r.stdout); self.assertIn("launch_sim_interfaces.sh 3", r.stdout)
        self.assertIn("1 2 3", r.stdout); self.assertIn("2 3 4", r.stdout)

    def test_num_robots_1_everywhere(self):
        r = subprocess.run(["bash", "-c", f"{ENV} NUM_ROBOTS=1; source {LIB}; echo \"$ISAAC_CMD\"; echo \"$IF_CMD\"; echo \"ids=$DRONE_IDS\"; echo \"sys=$SYSIDS\""], capture_output=True, text=True)
        self.assertIn("NUM_ROBOTS=1 ", r.stdout); self.assertIn("launch_sim_interfaces.sh 1", r.stdout)
        self.assertIn("ids=1\n", r.stdout); self.assertIn("sys=2\n", r.stdout)

    def test_land_wait_polls_only_the_spawned_drones(self):
        pre = ENV + " NUM_ROBOTS=1; source " + str(LIB) + '; OUT=$(mktemp -d); say(){ :; }; note(){ :; }; '
        r = subprocess.run(["bash", "-c", pre + 'rx(){ case "$*" in *mavros/state*) echo "armed: false";; esac; }; land_all_and_wait 10; echo rc=$?; cat "$OUT/armed_post.txt"'], capture_output=True, text=True, timeout=60)
        self.assertIn("rc=0", r.stdout); self.assertEqual(r.stdout.strip().splitlines()[-1], "drone_1 armed: false"); self.assertNotIn("drone_2", r.stdout)

    def test_param_keys_carry_the_yaw_gains(self):
        r = subprocess.run(["bash", "-c", f"{ENV}; source {LIB}; echo \"$PARAM_KEYS\""], capture_output=True, text=True)
        for k in ("MC_YAW_P", "MC_YAWRATE_P", "MC_YAWRATE_I", "MC_YAWRATE_D", "MC_YAWRATE_K"): self.assertIn(k, r.stdout)
```

```python
# append to tools/tests/test_sim_sh.py (class SimSh)
    def test_test_flow_passes_fly_args_and_drone_count(self):
        src = SIM.read_text()
        for n in ('NUM_ROBOTS=${NUM_ROBOTS:-3}', 'FLY_ARGS=${FLY_ARGS:-}', 'fly.sh $DURATION_S $FLY_ARGS', 'for N in $DRONE_IDS', 'pyulog'):
            self.assertIn(n, src, n)
        self.assertNotIn("for N in 1 2 3", src)
        self.assertLess(src.index("source \"$SIM_TESTS_DIR/$NAME/test.env\""), src.index('NUM_ROBOTS=${NUM_ROBOTS:-3}'))   # test.env may set it
```

```python
# append to tools/tests/test_report.py
class OneDroneRows(unittest.TestCase):
    def test_parse_armed_post_n1(self):
        self.assertEqual(R.parse_armed_post("drone_1 armed: false\n", n=1), {"drone_1": False})
        self.assertIsNone(R.parse_armed_post("drone_1 armed: false\n"))            # default still needs three
    def test_evidence_rows_n1_wants_sysid_2_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp); (out / "ulog_sysid_map.txt").write_text("2 /tmp/x.ulg 100\n")
            rows = []; R.evidence_rows(rows, out, out, "yaw", n=1)
            self.assertEqual(next(r.verdict for r in rows if r.check.startswith("PX4 ulogs")), "PASS")
            rows = []; R.evidence_rows(rows, out, out, "yaw")
            self.assertEqual(next(r.verdict for r in rows if r.check.startswith("PX4 ulogs")), "FAIL")
    def test_isaac_rows_n1(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp); (out / "isaac_evidence.txt").write_text("model_line=0 starling_cfg=1 autostart=1 unknown_model=0 cooking=0 ready=1\n")
            rows = []; R.isaac_rows(rows, out, n=1)
            self.assertTrue(all(r.verdict == "PASS" for r in rows), [(r.check, r.verdict) for r in rows])
```

- [ ] **Step 2: run, watch them fail**

`cd /home/jeremychia/AirStack-starling-max2 && python3 -m unittest tools.tests.test_stack_sh tools.tests.test_sim_sh tools.tests.test_report 2>&1 | tail -15` — expect `FAILED (failures=…, errors=…)` naming the new tests only.

- [ ] **Step 3: implement** per Interfaces. Keep `for N in 1 2 3` out of both shell files (the test greps). In `stack.sh up()` add `echo "num_robots=${NUM_ROBOTS}"; echo "fly_args=${FLY_ARGS:-}"` to the `run_meta.txt` block. In `report.py` thread `n` through the four helpers; criteria strings become f-strings (`f"SYS_AUTOSTART=10090 x{n}"`, `f"armed: false for {', '.join(f'drone_{i}' for i in range(1, n+1))}"`, `f"ulog_sysid_map.txt lists sysids {', '.join(str(s) for s in range(2, n+2))}"`).

- [ ] **Step 4: verify** `python3 -m unittest discover -s tools/tests 2>&1 | tail -3` → `OK`; `tools/sim.sh check` → `OK _template`, `OK crossing`; `bash tools/sim_hover_step_run.sh` (no args) → usage, exit 2; `tools/sim.sh` → usage, exit 2.

- [ ] **Step 5: commit**

```bash
cd /home/jeremychia/AirStack-starling-max2 && git add tools/lib/stack.sh tools/sim.sh tools/lib/report.py tools/tests/test_stack_sh.py tools/tests/test_sim_sh.py tools/tests/test_report.py
git commit -m "tools: sim stack takes the drone count and fly.sh args from test.env (NUM_ROBOTS, FLY_ARGS; default 3 unchanged); yaw gains in the ulog header dump" -m "One-drone tests (teleop_single.yaml) need NUM_ROBOTS=1 through Isaac, the interface launcher, the readiness loops, the landing poll and the record's x3 rows. report.py helpers take n (default 3). Sim only."
```

---

### Task 2: Heading in the shared metrics library (executor: **opus**)

**Files:**
- Modify: `tools/live/metrics_core.py` (`Frame`, `Tracker.update_odom`, new helpers), `tools/live/metrics_node.py` (`on_odom`, `status_line`), `tools/live/bag_recompute.py` (replay loop)
- Tests: `tools/tests/test_metrics_core.py`, `tools/tests/test_metrics_node_source.py`

**Interfaces:**
- `metrics_core.Frame` gains `yaw: dict = field(default_factory=dict)` (ENU yaw rad per drone, from the odometry quaternion) and `yaw_rate: dict = field(default_factory=dict)` (odometry `twist.twist.angular.z`, rad/s). `Tracker.update_odom(drone, t, xyz, vxyz, quat=None, ang_z=None)` — `quat = (x, y, z, w)`; `None` leaves the dicts without that drone (every heading series → NaN), so the crossing/synth callers are unchanged.
- New pure helpers: `yaw_from_quat(x, y, z, w) -> float` (atan2(2(wz+xy), 1−2(y²+z²)), the same formula as `swarm_commander.goal_callback`); `unwrap_deg(seq)`; `heading_deg(frame, drone)` = ENU yaw in degrees, NaN when stale/missing; `heading_rel_deg(frame, drone)` = heading minus the heading captured when phase became 2 (`Tracker` stores `_start_yaw` next to `_start`), unwrapped (the Tracker keeps the previous value per drone and adds the ±360 that keeps |Δ| < 180); `yaw_rate_dps(frame, drone)`; `xy_drift(frame, drone)` = horizontal distance from `start_pos` (NaN before phase 2).
- `metrics_node.on_odom`: `o = msg.pose.pose.orientation; w = msg.twist.twist.angular` → `tr.update_odom(drone, t, xyz, vel, (o.x, o.y, o.z, o.w), w.z)`; the same in `bag_recompute`. `status_line`: when the test has no `running_min` series, print the first continuous series' value instead of `min_d=nan run_min=nan` (`[t=  12.0 s] phase=2 heading_rel_deg=57.3 cbf= emerg=0`).

- [ ] **Step 1: failing tests**

```python
# append to tools/tests/test_metrics_core.py
class Heading(unittest.TestCase):
    def test_yaw_from_quat_quarter_turn(self):
        self.assertAlmostEqual(M.yaw_from_quat(0, 0, math.sin(math.pi / 4), math.cos(math.pi / 4)), math.pi / 2, places=9)

    def test_heading_nan_without_quaternion(self):          # crossing callers never pass one
        tr = seen_tracker({d: 2.0 for d in synth.DRONES})
        self.assertTrue(math.isnan(M.heading_deg(tr.frame(2.0), "drone_1")))

    def test_heading_rel_unwraps_across_pi(self):            # Review Focus 1
        tr = synth.make_tracker(); tr.update_status(synth.straight_status(2.0))
        pos, vel = synth.straight_world(2.0)
        for i, yaw in enumerate([170, 175, 179, -179, -175, -170]):   # degrees, crossing the seam
            q = (0.0, 0.0, math.sin(math.radians(yaw) / 2), math.cos(math.radians(yaw) / 2))
            for d in synth.DRONES:
                tr.update_odom(d, 2.0 + 0.1 * i, pos[d] - tr.offsets[d], vel[d], q, 0.3)
            f = tr.frame(2.0 + 0.1 * i)
            if i == 0: tr.row(2.0)   # phase 2 starts: start heading captured
        self.assertAlmostEqual(M.heading_rel_deg(tr.frame(2.5), "drone_1"), 20.0, places=6)
        self.assertAlmostEqual(M.yaw_rate_dps(tr.frame(2.5), "drone_1"), math.degrees(0.3), places=6)

    def test_xy_drift_is_horizontal_distance_from_phase2_start(self):
        tr = seen_tracker({d: 2.0 for d in synth.DRONES}); tr.row(2.0)
        pos, vel = synth.straight_world(2.0)
        tr.update_odom("drone_1", 2.1, pos["drone_1"] - tr.offsets["drone_1"] + np.array([0.3, 0.4, 5.0]), vel["drone_1"])
        self.assertAlmostEqual(M.xy_drift(tr.frame(2.1), "drone_1"), 0.5, places=6)
```

```python
# append to tools/tests/test_metrics_node_source.py (class NodeSource)
    def test_node_and_recompute_pass_orientation_and_yaw_rate(self):
        for f in ("metrics_node.py", "bag_recompute.py"):
            src = (LIVE / f).read_text()
            self.assertIn("pose.pose.orientation", src, f); self.assertIn("twist.twist.angular", src, f)
```

(Check `synth_crossing.make_tracker`/`straight_status`/`straight_world` signatures in `tools/tests/synth_crossing.py` before using them; adapt the helper calls, not the assertions.)

- [ ] **Step 2: run** `python3 -m unittest tools.tests.test_metrics_core tools.tests.test_metrics_node_source 2>&1 | tail -5` → the four new tests fail (`AttributeError: module 'metrics_core' has no attribute 'yaw_from_quat'`, etc.).

- [ ] **Step 3: implement** per Interfaces; `Frame` keeps `rclpy`-free (`test_no_top_level_ros_import_in_core`). `Tracker.frame()` builds `yaw`/`yaw_rate` dicts only for drones that have a quaternion; `_start_yaw` captured on the 1→2 transition next to `_start`; unwrap state per drone (`_unwrap_offset`).

- [ ] **Step 4: verify** full suite `OK`; `tools/sim.sh check` OK (crossing/bag cross-check untouched: `python3 -m unittest tools.tests.test_sim_tests_contract`).

- [ ] **Step 5: commit**

```bash
git add tools/live/metrics_core.py tools/live/metrics_node.py tools/live/bag_recompute.py tools/tests/test_metrics_core.py tools/tests/test_metrics_node_source.py
git commit -m "tools: live metrics carry heading — odometry quaternion -> ENU yaw, unwrapped heading relative to the test start, yaw rate, xy drift (one formula set for node, bag recompute and figures)" -m "Frame.yaw / yaw_rate are empty unless the caller passes a quaternion, so the crossing test is unchanged. Sim only."
```

---

### Task 3: Vehicle-time yaw analysis — `ulog_yaw_dump.py` + `yaw_core.py` + the `collect` hook (executor: **opus**)

**Files:**
- Create: `tools/live/ulog_yaw_dump.py` (pyulog; runs on the host, fallback inside `isaac-sim`), `tools/live/yaw_core.py` (pure numpy), `tools/tests/test_yaw_core.py`, `tools/tests/synth_yaw.py` (synthetic second-order ring-down generator shared with Task 4's tests)
- Modify: `tools/sim.sh` (`cmd_test` step 7 `collect`: after `px4_arm_times_of`, run the dump for the sysid-2 ulog), `tools/tests/test_sim_sh.py` (static check)

**Interfaces:**
- `ulog_yaw_dump.py <ulog> -o <csv> [--params-out <txt>]` writes a CSV with a `# key=value` header (`source=<basename>`, `sysid=`, `MC_YAW_P=`, `MC_YAWRATE_P=`, `_I=`, `_D=`, `_K=` from `initial_parameters`, `arm_s=`/`disarm_s=` reusing `hover_step_timescale.arming_transitions`) and columns `t_s,topic,value_a,value_b` — no: keep it tabular per topic instead. **Decision:** one long-format CSV is awkward for numpy; write **five aligned columns on the `vehicle_local_position` clock** (`t_s` = timestamp/1e6, vehicle seconds since PX4 boot): `t_s,heading_ned_deg,x_ned,y_ned,yaw_rate_dps,ff_dps,yawspeed_sp_dps,yaw_sp_ned_deg`, where `yaw_rate_dps` = `vehicle_angular_velocity.xyz[2]` (deg/s) and `ff_dps` = `vehicle_attitude_setpoint.yaw_sp_move_rate`, `yawspeed_sp_dps` = `trajectory_setpoint.yawspeed`, `yaw_sp_ned_deg` = yaw of `vehicle_attitude_setpoint.q_d`, each **sample-and-hold interpolated** (previous value) onto the ~84 Hz position clock (`np.searchsorted`). Converting degrees once here; NaN before a topic's first sample. `--params-out` writes `changed_parameters` as lines `t_s name value` (vehicle time) filtered to `MC_YAW*`. Exit 0 ok; 2 unreadable ulog; 3 a required topic missing (name it). pyulog imported inside `main()` only (the host test imports the pure helpers `to_deg`, `hold_onto`, `yaw_of_qd`).
- `yaw_core.py` (stdlib + numpy, no pyulog): `read_px4_csv(path) -> (meta, cols, data)` (reuse `metrics_core.read_metrics_csv`'s parser via import); `ned_to_enu_deg(h_ned_deg) = 90 − h_ned_deg`; `unwrap_deg(a)`; `find_pulses(t, ff, min_plateau_dps=20, quiet_s=2.0) -> list[Pulse]` with `Pulse(onset_s, release_s, sign(+1 = ENU CCW = NED negative), plateau_dps, released: bool)` — onset = first sample with |ff| ≥ min_plateau after ≥ quiet_s of |ff| < min_plateau/2; release = the first sample after onset with |ff| < plateau/2 (`released=False` when none before the data ends); falls back to `yawspeed_sp_dps` when `ff_dps` is all-NaN/zero (U3); `measure_pulse(p, t, h_enu_deg, rate_dps, x, y, t_end, band_deg=2.0) -> dict` with keys `overshoot_deg` (max of sign·(h − h_final) after release; h_final = mean over the last 1.0 s of the window), `undershoot_deg`, `settle_s` (release → first sample after the LAST excursion out of ±band; None when still out at `t_end`), `ring_crossings` (sign changes of (h − h_final) after the first return into the band), `ring_hz` ((crossings−1)/(2·Δt) when ≥ 3 crossings else NaN), `peak_rate_dps` (max |rate| in [release, release+3 s]), `plateau_meas_dps` (median |rate| over [onset+0.3 s, release]), `xy_drift_m` (max horizontal distance from the onset position over [onset, t_end]), `window_s`; `t_end` = next onset − 0.5 s or release + 12 s; `gains_in_force(changes, t) -> dict` (last value of each `MC_YAW*` before `t`, else the header's); `group_by_gains(pulses_with_gains) -> list[(gains_tuple, [pulses])]` in order of first appearance; `tap_check(t, x, y, h_enu, t0, t1) -> {direction_err_deg, heading_change_deg}` for the patch-0007 check (displacement vector in ENU: `e = y_ned, n = x_ned`); `analyse(csv_path, changes_path=None, wall_stamps=None) -> dict` tying it together (`pulses: [...]`, `groups: [...]`, `time_scale: [...]` from optional wall onset/release stamps).
- `sim.sh collect`: after `px4_arm_times_of`, when `$U1` is set: `nx python3 "$REPO/tools/live/ulog_yaw_dump.py" "$HEAVY/drone_1_sysid2_$(basename "$U1")" -o "$HEAVY/px4_drone_1.csv" --params-out "$OUT/px4_param_changes.txt"`; on failure (host lacks pyulog) retry inside the isaac container: `docker cp "$REPO/tools/live/ulog_yaw_dump.py" "$I:/tmp/"; docker exec "$I" python3 /tmp/ulog_yaw_dump.py "$U1" -o /tmp/px4_drone_1.csv --params-out /tmp/px4_param_changes.txt; docker cp …`; if both fail → `caveat "no px4_drone_1.csv — vehicle-time gates UNVERIFIED"`. `phase_begin collect` adds `px4_param_changes.txt` to its truncate list. Also copy `tools/hover_step_timescale.py`'s arming helper by import, not by duplication.

- [ ] **Step 1: failing tests** (`tools/tests/synth_yaw.py` first: `ring_down(t, release_s, rate_dps=57.3, zeta=0.2, wn=2*pi*0.8, hold_deg=…)` producing a heading trace that turns at `rate_dps` from onset to release then rings down as a second-order response to the held heading; `px4_csv(path, pulses, hz=84, sign_flip=False, seam=False)` writes a CSV in the dumper's schema; `wall_stamps(pulses, scale)`).

```python
# tools/tests/test_yaw_core.py
import math, pathlib, sys, tempfile, unittest
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent
for p in (HERE, HERE.parent / "live"): sys.path.insert(0, str(p))
import yaw_core as Y
import synth_yaw as S

class Frames(unittest.TestCase):
    def test_ned_to_enu(self):
        self.assertAlmostEqual(Y.ned_to_enu_deg(90.0), 0.0); self.assertAlmostEqual(Y.ned_to_enu_deg(0.0), 90.0)
    def test_unwrap_no_jump_at_seam(self):
        a = Y.unwrap_deg(np.array([170.0, 179.0, -179.0, -170.0])); self.assertTrue(np.all(np.diff(a) > 0)); self.assertAlmostEqual(a[-1], 190.0)

class Pulses(unittest.TestCase):
    def test_finds_both_directions_and_release(self):
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1), dict(onset=40.0, dur=1.0, sign=-1)])
            r = Y.analyse(csv)
        self.assertEqual([p["sign"] for p in r["pulses"]], [1, -1]); self.assertTrue(all(p["released"] for p in r["pulses"]))
        self.assertAlmostEqual(r["pulses"][0]["release_s"] - r["pulses"][0]["onset_s"], 1.0, delta=0.06)   # 20 Hz ff -> 50 ms

    def test_underdamped_ring_is_measured(self):
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1, zeta=0.1, f_hz=0.8)])
            p = Y.analyse(csv)["pulses"][0]
        self.assertGreater(p["overshoot_deg"], 8.0); self.assertGreaterEqual(p["ring_crossings"], 3)
        self.assertAlmostEqual(p["ring_hz"], 0.8, delta=0.15); self.assertGreater(p["settle_s"], 2.0)

    def test_well_damped_pulse_settles_fast(self):
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1, zeta=0.9, f_hz=1.5)])
            p = Y.analyse(csv)["pulses"][0]
        self.assertLess(p["overshoot_deg"], 3.0); self.assertLessEqual(p["ring_crossings"], 1); self.assertLess(p["settle_s"], 2.0)

    def test_pulse_across_the_seam_has_small_overshoot(self):              # Review Focus 1
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1, zeta=0.9, f_hz=1.5)], start_heading_enu_deg=160.0)
            p = Y.analyse(csv)["pulses"][0]
        self.assertLess(p["overshoot_deg"], 3.0)

    def test_settle_time_is_in_vehicle_time_not_wall(self):                 # Review Focus 2
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1, zeta=0.3, f_hz=0.8)])
            a = Y.analyse(csv); b = Y.analyse(csv, wall_stamps=S.wall_stamps(a["pulses"], scale=0.36))
        self.assertEqual(a["pulses"][0]["settle_s"], b["pulses"][0]["settle_s"])
        self.assertAlmostEqual(b["time_scale"][0], 0.36, delta=0.03)

    def test_unreleased_pulse_is_unverified(self):                           # Review Focus 3
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1), dict(onset=40.0, dur=None, sign=-1)])
            r = Y.analyse(csv)
        self.assertFalse(r["pulses"][1]["released"]); self.assertIsNone(r["pulses"][1]["settle_s"])

    def test_sign_follows_enu(self):                                         # Review Focus 5
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1)])
            p = Y.analyse(csv)["pulses"][0]
        self.assertEqual(p["sign"], 1); self.assertGreater(p["turn_deg"], 40.0)    # ENU heading rose
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1)], sign_flip=True)
            p = Y.analyse(csv)["pulses"][0]
        self.assertLess(p["turn_deg"], -40.0)     # a flipped frame shows as a negative turn for a + command

    def test_gains_in_force_and_groups(self):
        changes = [(30.0, "MC_YAW_P", 2.0)]
        hdr = {"MC_YAW_P": 2.8, "MC_YAWRATE_P": 0.07, "MC_YAWRATE_I": 0.5, "MC_YAWRATE_D": 0.0, "MC_YAWRATE_K": 1.0}
        self.assertEqual(Y.gains_in_force(changes, 20.0, hdr)["MC_YAW_P"], 2.8); self.assertEqual(Y.gains_in_force(changes, 40.0, hdr)["MC_YAW_P"], 2.0)

    def test_tap_direction(self):
        t = np.linspace(0, 2, 200); x_ned = np.zeros_like(t); y_ned = 0.5 * t      # +east in ENU = +y NED
        r = Y.tap_check(t, x_ned, y_ned, np.full_like(t, 90.0), 0.0, 2.0)
        self.assertAlmostEqual(r["direction_err_deg"], 0.0, delta=1.0); self.assertAlmostEqual(r["heading_change_deg"], 0.0, delta=0.1)

class Dumper(unittest.TestCase):
    def test_hold_onto_clock_and_yaw_of_qd(self):
        import ulog_yaw_dump as D
        held = D.hold_onto(np.array([0.0, 1.0, 2.0]), np.array([0.5, 1.5]), np.array([10.0, 20.0]))
        self.assertTrue(np.isnan(held[0])); self.assertEqual(list(held[1:]), [10.0, 20.0])
        self.assertAlmostEqual(D.yaw_of_qd(math.cos(math.pi / 4), 0, 0, math.sin(math.pi / 4)), 90.0, places=6)   # PX4 q = (w, x, y, z)
```

```python
# append to tools/tests/test_sim_sh.py (class SimSh)
    def test_collect_dumps_the_yaw_csv_with_a_container_fallback(self):
        src = SIM.read_text()
        for n in ("ulog_yaw_dump.py", "px4_drone_1.csv", "px4_param_changes.txt", "no px4_drone_1.csv"):
            self.assertIn(n, src, n)
        self.assertLess(src.index("px4_arm_times_of"), src.index("ulog_yaw_dump.py"))
```

- [ ] **Step 2: run** `python3 -m unittest tools.tests.test_yaw_core tools.tests.test_sim_sh 2>&1 | tail -5` → `ModuleNotFoundError: yaw_core` then the sim.sh static test fails.

- [ ] **Step 3: implement.** Order: `synth_yaw.py` → `yaw_core.py` → `ulog_yaw_dump.py` → `sim.sh collect` block. In the dumper, PX4 quaternion order is `q[0]=w`; `heading` in `vehicle_local_position` is NED yaw in radians. `yaw_core.find_pulses` works on the ENU-converted sign so `sign=+1` means the commander's `+angular.z` (NED `ff` negative). Run the dumper once on the real file to validate the schema: `python3 tools/live/ulog_yaw_dump.py ~/flight_logs/sim/sim_crossing_run2/drone_1_sysid2_18_32_18.ulg -o /tmp/claude-1000/-home-jeremychia/37cad1a9-5a36-4858-918e-0b06a95a9d2d/scratchpad/px4_probe.csv --params-out /tmp/claude-1000/-home-jeremychia/37cad1a9-5a36-4858-918e-0b06a95a9d2d/scratchpad/px4_probe_params.txt && head -3 /tmp/claude-1000/-home-jeremychia/37cad1a9-5a36-4858-918e-0b06a95a9d2d/scratchpad/px4_probe.csv` (that crossing flight has no yaw pulses; `yaw_core.analyse` on it must return `pulses: []` without crashing — add `test_no_pulses_is_empty_not_error`).

- [ ] **Step 4: verify** full suite OK; `bash -n tools/sim.sh`; `tools/sim.sh check`.

- [ ] **Step 5: commit**

```bash
git add tools/live/ulog_yaw_dump.py tools/live/yaw_core.py tools/tests/test_yaw_core.py tools/tests/synth_yaw.py tools/sim.sh tools/tests/test_sim_sh.py
git commit -m "tools: PX4 yaw analysis in vehicle time — ulog_yaw_dump.py (pyulog, host first, isaac-sim fallback) + yaw_core.py (pulses, overshoot, ring, settle, peak rate, drift, gains in force); collect dumps drone_1's ulog" -m "Gates on heading cannot use wall time: the sim ran 0.36x in the 10-30 sessions and 1.32x in #17-#19. Sim only."
```

---

### Task 4: The `yaw_step` test directory (executor: **opus**)

**Files:**
- Create: `tools/sim_tests/yaw_step/test.env`, `fly.sh`, `metrics.py`, `gates.py`, `plots.json`, generated `layout.json` (`python3 tools/live/make_layout.py tools/sim_tests/yaw_step`)
- Create: `tools/tests/test_yaw_step_gates.py`
- Pre-step 0 (only if `docker ps` shows `airstack-robot-desktop-1` Up; read-only): `docker exec airstack-robot-desktop-1 bash -ic 'ros2 interface show mavros_msgs/srv/ParamSetV2; ros2 interface show mavros_msgs/srv/ParamPull'` → settle U1; otherwise code both paths (service + `ros2 param set`) and let the read-back decide at the owner's run.

**Interfaces:**
- `test.env`:
  ```
  # Sim-only (iron rule 9): one drone, teleop_single.yaml, yaw pulses through the commander's teleop input (no keyboard, no safe_teleop).
  TITLE="one-drone yaw-step: heading ring-down after a yaw pulse, PX4 vehicle time"
  ISSUE=NEAR-789
  MILESTONE=S5
  PURPOSE="Measure how the sim drone's heading settles after a yaw pulse is released (overshoot, ring, settle time, peak rate, drift) from the PX4 ulog in vehicle time, so the sim airframe's yaw gains can be retuned; the keyboard sessions of 2026-10-30 showed a ±8–17° ring at ~0.8 Hz."
  SCOPE="PX4's own sim state estimate positions the drone (no mocap, no camera); flat default world; one drone; commander teleop input only (safe_teleop and the keyboard not in the loop); time gates read PX4 vehicle time from the ulog."
  SIM_ONLY_LINE="none of these values is ported to the drone; the sim airframe's yaw gains are sim-only (iron rule 9)."
  CONFIG=teleop_single.yaml
  SCENARIO=hover
  BAG_PREFIX=yaw_step
  DURATION_S=20            # wall-clock gap between pulses (fly.sh argument 1)
  NUM_ROBOTS=1
  USE_STUDIO=false         # no Basestation Studio: the live plot window is the view (two Studio windows cost sim speed, 10-30)
  # FLY_ARGS: fly.sh <gap_s> [N_PULSES] [RATE_RAD_S] [PULSE_S] [SWEEP]
  #   SWEEP = ';'-separated gain sets applied live over MAVROS before pulse groups 1..k, e.g.
  #   "MC_YAW_P=2.0;MC_YAW_P=1.4,MC_YAWRATE_D=0.002" — group 0 always flies the booted (airframe) gains and is the only gated group.
  FLY_ARGS="3 1.0 1.0"
  BASELINE="keyboard sessions 2026-10-30 (sim_site_hand1/3 cuVSLAM replays): ±8–17° ring at ~0.8 Hz for ≥ 10 s; no ulog"
  ```
- `fly.sh <gap_s> [N_PULSES=3] [RATE=1.0] [PULSE_S=1.0] [SWEEP=""]`, runs inside the robot container: same `svc`/`states` helpers as crossing; `takeoff` → retry `start` (≤ 30 × 3 s) → the pulse schedule as an embedded `python3 - "$@" <<'PY' … PY` rclpy program (one process, 20 Hz, publisher `/svg/drone_1/teleop_command` `geometry_msgs/msg/TwistStamped`, `header.frame_id = "map"`): for each gain set k (0 = none): if k > 0 apply the set (subprocess `ros2 service call /drone_1/interface/mavros/param/set mavros_msgs/srv/ParamSetV2 "{force_set: false, param_id: <P>, value: {type: 3, double_value: <v>}}"` → parse `success=True`; fallback `ros2 param set /drone_1/interface/mavros/param <P> <v>`), then read back: `ros2 service call /drone_1/interface/mavros/param/pull mavros_msgs/srv/ParamPull "{force_pull: true}"` and `ros2 param get /drone_1/interface/mavros/param <P>` → print `[wall] param <P> set <v> readback <v'>` (mismatch → print `PARAM MISMATCH` and stop the sweep: land normally, exit 1); then N_PULSES pulses alternating sign (+RATE for PULSE_S s, zeros for `gap_s`; then −RATE …), printing `[<unix.ns>] pulse k/i onset sign=+1 rate=1.0` and `[<unix.ns>] pulse k/i release` lines (the wall stamps the gates use for the INFO time scale). After the last group: the patch-0007 check (`angular.z=+0.5` for 3.14 s; zeros 5 s; `linear.x=+0.5` for 1.5 s; zeros 5 s) printed as `[..] tap onset` / `[..] tap release`. The program publishes zeros for 1 s on normal exit, on SIGINT/SIGTERM and on any exception (`try/finally`). Then `land` and the `landed:` line as in crossing. Total flight ≈ 60 s + groups × N × 2 × (PULSE_S + gap).
- `metrics.py`: `DRONES = ("drone_1",)`, `TRIGGER = "drone_1"`, `PARAMS = ["teleop_max_speed_mps", "teleop_fence_min", "teleop_fence_max"]`, `REFERENCES = {"ref_band_plus": 2.0, "ref_band_minus": -2.0, "ref_overshoot_gate": 3.0}`, `SERIES = [Series("heading_rel_deg", lambda f: M.heading_rel_deg(f, "drone_1"), 0.5, "deg"), Series("heading_deg", …, 0.5, "deg"), Series("yaw_rate_dps", …, 2.0, "deg/s"), Series("xy_drift_m", …, 0.02, "m"), Series("fence_breached", flag), Series("emergency", flag)]`. No `running_min` series (the node's status line falls back to `heading_rel_deg`, Task 2).
- `plots.json`: plot 1 `heading` (series `heading_rel_deg`, refs `ref_band_plus`, `ref_band_minus`, y_range [−120, 120], unit deg); plot 2 `yaw_rate` (`yaw_rate_dps`, y [−90, 90]); plot 3 `drift` (`xy_drift_m`, y [0, 0.5]); `phase_series: "phase"`.
- `gates.py` (`build_rows(out, heavy, env)`): `n = int(env.get("NUM_ROBOTS", 3))`; `R.isaac_rows(rows, out, n=n)`; coverage row; loads `heavy/px4_drone_1.csv` + `out/px4_param_changes.txt` + wall stamps parsed from `out/test_stdout.log` (regex `^\[(\d+\.\d+)\] pulse (\d+)/(\d+) (onset|release)`), runs `yaw_core.analyse`; gates from the table above over group 0's released pulses; `yaw sign` gate compares each pulse's `turn_deg` sign with its commanded sign AND the live CSV's `heading_rel_deg` change over the pulse (both must be positive for `+angular.z`); `booted gains` gate parses `param set-default (MC_YAW_P|MC_YAWRATE_[PIDK]) ([0-9.eE+-]+)` from `REPO/AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max` and compares with the CSV header's values (rel tol 1e-3); `live vs ulog overshoot` compares per pulse the ulog overshoot with the live CSV's (`yaw_core.measure_pulse` applied to `metrics.csv`'s `heading_rel_deg`/`t_s` with the wall stamps mapped through `t0_unix`), FAIL → overshoot gate verdict set to UNVERIFIED (the crossing's rule); `R.landing_rows(rows, out, n=n)`; `R.evidence_rows(rows, out, heavy, env["BAG_PREFIX"], extra_files=("metrics.csv","metrics_bag.csv" if present), n=n)`; crosscheck rows; INFO rows: per-pulse table (one row per pulse, measured cell ≤ 120 chars), per-gain-set summary (`set k: MC_YAW_P x MC_YAWRATE_P/I/D y — overshoot max a°, settle max b s, ring max c, n pulses`), patch-0007 tap check, plateau measured vs commanded (U4), time scale per pulse (`vehicle s per wall s`), `px4_param_changes.txt` echo. `ctx`: `headline = "worst overshoot after release (set 0)"`, `headline_row = "heading overshoot"`, `reading` 2–3 sentences, `caveats` (gap is wall-clock; vehicle gap = gap × time scale). `ledger_sentence`: `"yaw step, 1 drone, teleop_single.yaml, N pulses ±1.0 rad/s, vehicle time: <verdict> — overshoot a°, settle b s, ring c, peak rate d °/s, drift e m (set 0: MC_YAW_P …, MC_YAWRATE_P/I/D …); sweep k sets; landed + DISARMED <yes/NOT shown>"`. `figure_caption` ≤ 380 chars, says wall clock for the figure's time axis and that the gates are vehicle time.
- `report.py`/`sim.sh` unchanged in this task (Task 1 made them n-aware).

- [ ] **Step 1: failing tests** (`tools/tests/test_yaw_step_gates.py` builds a run folder: `S.px4_csv` into `heavy/px4_drone_1.csv` with header gains equal to the airframe file's current values (parse them in the test the same way), a `metrics.csv` written with `metrics_core.csv_header`/`format_row` from the same synthetic heading (ENU, wall time = vehicle/1.32), `test_stdout.log` with pulse stamp lines, `armed_post.txt` = `drone_1 armed: false`, `isaac_evidence.txt` with `starling_cfg=1 autostart=1 ready=1 unknown_model=0 cooking=0`, `ulog_sysid_map.txt` = `2 /x.ulg 100`, `run_meta.txt`, a `yaw_step_2026_…/metadata.yaml` bag dir, `res_watch.log` empty).

```python
class YawStepGates(unittest.TestCase):
    def test_well_damped_run_passes(self): rows, ctx = G.build_rows(out, heavy, env); self.assertEqual(R.overall_verdict(rows), "PASS", [(r.check, r.verdict, r.measured) for r in rows if r.gate and r.verdict != "PASS"])
    def test_ring_fails_overshoot_settle_and_ring(self): …zeta=0.1 → verdicts FAIL for "heading overshoot", "settle", "ring"
    def test_unreleased_pulse_fails_the_flown_row_and_never_passes_a_gate(self): …dur=None on one pulse → "set-0 pulses" FAIL, every per-pulse gate UNVERIFIED, verdict FAIL   # Review Focus 3
    def test_missing_px4_csv_is_incomplete(self): …no heavy/px4_drone_1.csv → vehicle-time gates "n/a — px4_drone_1.csv missing", INCOMPLETE, never PASS   # Review Focus 4
    def test_yaw_sign_mismatch_fails(self): …sign_flip=True → "yaw sign" FAIL   # Review Focus 5
    def test_only_group_0_is_gated(self): …changes at t=35 (MC_YAW_P=1.0) with a ringing second group → PASS; INFO row "set 1" present
    def test_live_vs_ulog_overshoot_mismatch_makes_overshoot_unverified(self): …metrics.csv heading scaled ×1.5 → overshoot row UNVERIFIED
    def test_booted_gains_gate_reads_the_airframe_file(self): …header MC_YAW_P 9.9 → FAIL; equal → PASS
    def test_fly_publishes_zeros_on_exit(self):   # static
        src = (TOOLS / "sim_tests/yaw_step/fly.sh").read_text()
        for n in ("/svg/drone_1/teleop_command", "TwistStamped", "finally", "SIGTERM", "param/set", "param/pull", "force_pull: true", "pulse", "release", "landed:"): self.assertIn(n, src, n)
        self.assertEqual(subprocess.run(["bash", "-n", str(TOOLS / "sim_tests/yaw_step/fly.sh")]).returncode, 0)
    def test_five_files_and_fresh_layout(self): …contract_check.check(yaw_step) == []
    def test_caption_and_ledger_sentence(self): …≤ 380 chars; sentence names the verdict and "vehicle time"
```

- [ ] **Step 2: run** `python3 -m unittest tools.tests.test_yaw_step_gates 2>&1 | tail -5` → fails (no directory).

- [ ] **Step 3: implement** `cp -r tools/sim_tests/_template tools/sim_tests/yaw_step`, fill the five files per Interfaces, `python3 tools/live/make_layout.py tools/sim_tests/yaw_step`, `tools/sim.sh check` → `OK yaw_step`.

- [ ] **Step 4: verify** full suite OK (`tools/tests/test_sim_tests_contract.py` `test_template_and_crossing_have_the_five_files_and_fresh_layout` still passes; extend it to iterate every directory). `python3 tools/lib/report.py tools/sim_tests/yaw_step <synthetic run dir> --heavy <heavy> --no-verdict-log --ledger 24 --issue NEAR-789` on the test's synthetic folder renders a record with the per-pulse table (inspect it once by eye; delete the scratch output).

- [ ] **Step 5: commit**

```bash
git add tools/sim_tests/yaw_step tools/tests/test_yaw_step_gates.py tools/tests/test_sim_tests_contract.py
git commit -m "tools: yaw_step test — one sim drone, yaw pulses through the commander's teleop input, heading ring-down gated in PX4 vehicle time, live gain sweep over MAVROS, patch-0007 turn-then-tap check as info (NEAR-789)" -m "Gates (owner decides): overshoot <= 3 deg, settle to +-2 deg <= 2 s vehicle, <= 1 ring crossing, peak rate <= 30 deg/s, xy drift <= 0.15 m, yaw sign, booted gains = airframe file, live-vs-ulog overshoot within 1 deg. Sim only."
```

---

### Owner session (the owner runs this; executors never start Isaac)

Cold start, laptop on Ethernet or sitting at it (Isaac start/stop can crash the WiFi firmware), QGC not needed (sim), no real-drone bridge running.

```bash
cd ~/AirStack-starling-max2
git status --short                      # expect only the three known untracked items
tools/sim.sh doctor                     # every line OK/WARN; "host python: pyulog" must be OK (else: pip install pyulog)
tools/sim.sh check                      # OK _template, OK crossing, OK yaw_step
# 1) acceptance of the CURRENT (real-drone) yaw gains on the sim plant — expected to FAIL on overshoot/ring: that is the finding
tools/sim.sh test yaw_step --issue NEAR-789 sim_yaw_run1
```

What you will see, in order: `ledger: #<n> (next free row…)`; phases `precheck` (WiFi warning) → `up` (`./airstack.sh up`, domain-1 check) → `watch` → `isaac` (the Isaac window opens; "Ready for takeoff: 1" after 2–5 min) → `interfaces` (drone_1 MAVROS connected, odometry ok) → `commander` (`SwarmCommander up | scenario=hover`, states `['IDLE']`) → `params` (MAVROS read of the airframe values) → `snapshot` (start PX4 parameter snapshot, `snapshot start drone_1: <n> PX4 parameters`) → `metrics` (`metrics liveness: /svg/test/heading_rel_deg 10 Hz`) → the live plot window (heading_rel_deg with the ±2° band) → **pause 1**: start OBS, press Enter. Flight (~2.5 min at the default `FLY_ARGS="3 1.0 1.0"`): takeoff to 1.2 m, `start` accepted (`sticks live, holding …` in the commander log), six pulses (+,−,+,−,+,−) 20 s apart — the plot shows a ~75° ramp then the ring-down after each release; one line per second in the terminal `[t= 42.0 s] phase=2 heading_rel_deg=…`; then the 90° turn, the forward tap, `land`, `landed:`. **Pause 2**: stop OBS, type `videos/<file>.mkv` or Enter. Then `collect` (ulog copied, `px4_drone_1.csv`, `px4_param_changes.txt`), `down` (stack stopped, containers stay up), the figure, and `VERDICT: <PASS|FAIL|INCOMPLETE> — worst overshoot …`. Open `docs/record/sim_yaw_run1_record.md`: the per-pulse table and the "set 0" summary are the baseline numbers.

Tuning loop (one flight per sweep; each flight re-launches Isaac, ~10 min end to end):

```bash
# 2) edit ONE line in tools/sim_tests/yaw_step/test.env (uncommitted is fine; run_meta records dirty_tools):
#    FLY_ARGS="2 1.0 1.0 MC_YAW_P=2.0;MC_YAW_P=1.4;MC_YAW_P=1.4,MC_YAWRATE_P=0.05;MC_YAW_P=1.4,MC_YAWRATE_P=0.05,MC_YAWRATE_D=0.002"
#    (group 0 = booted gains, then four live sets, 2 pulses each direction -> 20 pulses, ~8 min of flight)
tools/sim.sh test yaw_step --issue NEAR-789 sim_yaw_sweep1
# read docs/record/sim_yaw_sweep1_record.md: the "set k" INFO rows; px4_param_changes.txt proves what PX4 applied (vehicle time)
# 3) narrow the sweep around the best set and repeat once:  sim_yaw_sweep2
# 4) hand the chosen set to the executor of Task 5 (values + the two record paths), restore FLY_ARGS to "3 1.0 1.0"
```

Which mechanism sets the gains (since CHG-0018/0020 every set goes through `tools/lib/px4_param_set.sh`, the same helper as `tools/sim.sh param set`): it first checks that drone_N's MAVROS `fcu_url` is the sim's (`udp://:1454N@172.31.0.200:1458N`, else REFUSED), then tries `ros2 param set /drone_1/interface/mavros/param MC_YAW_P 2.0`, then `ros2 service call … mavros_msgs/srv/ParamSetV2 "{force_set: false, …}"` (never force_set). Read-back, always: `ros2 service call /drone_1/interface/mavros/param/pull mavros_msgs/srv/ParamPull "{force_pull: true}"` then `ros2 param get /drone_1/interface/mavros/param MC_YAW_P` (prints `Double value is: 2.0`); authoritative proof = `docs/record/<run>/px4_param_changes.txt` (from the ulog's `changed_parameters`). The PX4 shell in the isaac container is NOT used (Pegasus starts PX4 without an attached console).

Shutdown: `tools/sim.sh test` already ran `down` (commander, interfaces, Isaac stopped; ulogs and bag in `~/flight_logs/sim/<run>/`). End of day: `cd ~/AirStack-starling-max2/AirStack && ./airstack.sh down`. If a run is interrupted: Ctrl-C lands (ABORTED record); if it prints `DRONES STILL ARMED`: `docker exec airstack-robot-desktop-1 bash -ic 'ros2 service call /swarm_commander/land std_srvs/srv/Trigger'` then `tools/sim.sh down`.

Reading the result: overshoot and ring count are the tuning signal; `plateau measured vs commanded` tells whether PX4 limited the 57 °/s (U4); the `yaw sign` row must be PASS before any number is trusted; `time scale` per pulse ≈ 1.3 on the flat world.

---

### Task 5: Write the chosen yaw gains into the sim airframe (executor: **sonnet**; AFTER the owner session; input = the owner's chosen set + the record paths)

**Files:**
- Modify: `AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max` — the five `param set-default MC_YAW*` lines (find them with `grep -n 'MC_YAW' <file>`; line numbers moved when CHG-0013 added the markers) — the owner-approved sim-only exception
- Modify: `docs/record/CHANGES.md` — append the next CHG row (`python3 tools/docs_check/changes.py audit` names the next free id; CHG-0021 or later)
- Modify: `patches/`? — No: the airframe file is ours (not a CMU patch); no patch file.
- Test: none new; `tools/tests/test_yaw_step_gates.py::test_booted_gains_gate_reads_the_airframe_file` ties `gates.py` to the file, and `tools/tests/test_airframe_markers.py` fails unless every changed line's marker becomes `# SIM-ONLY (real <real value>) CHG-<this id>` (CODING_STANDARD §4).

- [ ] **Step 1:** edit the airframe: replace the values on the five `param set-default MC_YAW*` lines with the chosen ones, change each changed line's marker from `# = real` to `# SIM-ONLY (real <v>) CHG-<this id>` (unchanged lines keep `# = real`), and add, above them, a comment in the style of the rate-gain block (lines 38–48): what was observed (the 10-30 keyboard ring, ledger `#<run1>`), the sweep (`#<sweep>`, sets tried, overshoot/settle/ring per set in one line each), why the sim plant differs (yaw torque only from rotor drag `k_m = 5.38697e-8`, motor lag off), the real values kept in the comment (`MC_YAW_P 2.8 · MC_YAWRATE_P 0.07 / I 0.5 / D 0`), and the line `# SIM-ONLY: never copy these to the real drone's parameter set.`
- [ ] **Step 2:** `python3 -m unittest tools.tests.test_yaw_step_gates tools.tests.test_airframe_markers` → OK; full suite; `tools/sim.sh check` OK; append the CHANGES.md row (scope `sim-only`).
- [ ] **Step 3:** the owner runs the acceptance `tools/sim.sh test yaw_step --issue NEAR-789 sim_yaw_run2` (booted gains = new values; expected PASS). The executor does not run it.
- [ ] **Step 4: commit** (after the acceptance run exists):

```bash
git add AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max docs/record/CHANGES.md
git commit -F - <<'MSG'
sim airframe: yaw gains MC_YAW_P <v> / MC_YAWRATE_P <v> I <v> D <v> — kills the ~0.8 Hz heading ring after a yaw pulse; sim-only

Change: CHG-<this id>
What: 10090_pegasus_starling2max MC_YAW_P 2.8 -> <v>; MC_YAWRATE_P 0.07 -> <v>; MC_YAWRATE_I 0.5 -> <v>; MC_YAWRATE_D 0 -> <v> (markers SIM-ONLY (real ...) CHG-<this id>)
Scope: sim-only (Isaac + Pegasus, PX4 SITL, any world, sim position source). Real drone keeps 2.8 / 0.07 / 0.5 / 0. Never port (iron rule 9).
Why: heading rings ~0.8 Hz after a yaw key (sim_site_hand1/3 replays; yaw-step run sim_yaw_run1); sweep sim_yaw_sweep<k> chose this set. Same class as the 10-20 rate gains x0.5 (CHG-0003).
Could affect: heading hold in every sim test, teleop turns, the crossing tests, landing detection, roll/pitch through motor saturation.
Watch for: heading overshoot > 3 deg or ring after a turn in yaw_step; roll/pitch rate std > 0.4 deg/s in hover; landing not detected.
Verified by: pending: tools/sim.sh test yaw_step --issue NEAR-789 sim_yaw_run2 (booted gains = these values, expected PASS); marker + gate tests.
Revert: git revert <sha>; Isaac restart reloads the airframe.
MSG
```

The record/ledger/project-page entries for `sim_yaw_run1`, `sim_yaw_sweep*`, `sim_yaw_run2` follow DOCS_STANDARD §7 — in Task 6, after the owner's OK.

---

### Task 6: Docs — **needs owner OK** (executor: **sonnet**; list the pages, wait for the owner's yes, then edit; `tools/docs_check/check_docs.sh` → `0 FAIL`)

Pages and the one-line change each:
- `docs/record/LEDGER.md` — paste the drafted rows of `sim_yaw_run1`, `sim_yaw_sweep1/2`, `sim_yaw_run2` (append only).
- `docs/projects/HTX-R1.md` — S5 NEAR-789 block: Result cell from the records; one `**NEAR-789: Set up one-drone gamepad teleop in the construction site (pad detected, sticks move the drone, release holds).**` paragraph naming the yaw finding and the retune (hand-flown parts still count only with a video the owner has watched); optional Figure (heading ring-down overlay, `tools/make_figures.sh` run list).
- `docs/CONFIG.md` "Sim airframe" table — row "PX4 inner (rate) loops": `MC_YAWRATE 0.07 / 0.5 / 0 (unchanged)` → the new values marked **sim-only — never port to the drone**; row "PX4 outer loops": `MC_YAW_P 2.8` → new value, flagged sim-only; the "What in that airframe is real and what is sim-only" table below it gains the yaw line.
- `CLAUDE.md` + `docs/PREFLIGHT.md` iron rule 9 (byte-identical blocks; the docs check diffs them): add "yaw gains" to the sim-only list and strike "attitude … gains equal the real drone's" for yaw.
- `docs/TEST_STANDARD.md` §3 migration order: "3. Later tests (gain tuning …)" → name `yaw_step` as the first gain-tuning test and state the vehicle-time deviation (this plan's "Deviation" paragraph, two sentences).
- `tools/README.md` — table row for `sim_tests/yaw_step/`, `FLY_ARGS`/`NUM_ROBOTS` in "Adding a test", the pyulog prerequisite, a "Thresholds" sub-table for the yaw gates.
- `docs/TELEOP.md` §3b / troubleshooting — one line: "heading rings after a turn in sim → yaw gains, see yaw_step record".
- `docs/MIGRATION.md` — the row list of our patches/edits gains "sim airframe yaw gains (2026-11-xx)".
- `docs/TROUBLESHOOTING.md` — symptom row "sim drone's heading wobbles ±10° after a yaw key".

Commit: `git commit -m "HTX-R1/S5 NEAR-789: ledger #<n>–#<m> — sim yaw-step test, yaw gains retuned sim-only; CONFIG/TEST_STANDARD/README/TELEOP rows"`.
