# Hover + step test tooling fix (after the four-expert review of ledger #17) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `tools/sim_hover_step_run.sh all` run the sim hover + 1 m step test end to end with zero manual intervention and write a record whose every gate is decided by committed, host-tested code — in PX4 vehicle time, on the commanded axis, failing closed on missing evidence.

**Architecture:** The rosbag work is split into a thin container-only reader (`tools/hover_step_bag.py`, dumps three CSVs) and a pure-Python analysis module (`tools/hover_step_analysis.py`, runs and is unit-tested on the host with the ledger #17 CSVs as fixtures). A tiny pyulog script in the Isaac container prints PX4 arm/disarm times; the analysis divides the PX4 interval by the bag's MAVROS-state interval to get the wall→vehicle time scale and emits every duration in both clocks. The report (`tools/hover_step_report.py`) becomes a library with a `build_rows()` entry point so its fail-closed behaviour is unit-tested against corrupted fixtures; it gates on vehicle-time, goal-referenced metrics and prints `info` for non-gates. The wrapper copies OUR test script + analyser from `tools/` (CMU's `AirStack/` tree is never touched), checks readiness per MAVROS namespace, copies ulogs before Isaac stops (in `collect` and again in `down`), guards the bag copy, and records every command, the commit that ran, and every report verdict.

**Tech Stack:** bash (host), Python 3.13 + numpy 1.26 + matplotlib 3.10 (host; `python3 -m unittest`), Python 3.12 + rosbag2_py + numpy (robot container `airstack-robot-desktop-1`, every exec via `bash -ic`), pyulog in `isaac-sim` system python3, docker.

**Spec:** `/tmp/claude-1000/-home-jeremychia/37cad1a9-5a36-4858-918e-0b06a95a9d2d/scratchpad/s5/EXPERT_REVIEW_sim_hover_step_run1.md` (sections 3 and 5). Map of review items → tasks at the end of this document.

## Global Constraints

- Work and commit in the **live clone** `/home/jeremychia/AirStack-starling-max2` on `main`. `git add <files>; git commit -m …`. **Never push.** No committed file > 1 MB.
- New or changed code only under `tools/` and `tools/tests/`. `AirStack/` (CMU's vendored tree) is **read-only** in this plan: `AirStack/simulation/isaac-sim/tools/sim_hover_step_test.sh` and `analyze_step.py` are COPIED into `tools/` and left untouched where they are.
- Host has **no pytest and no rosbag2_py**: host tests run with `cd /home/jeremychia/AirStack-starling-max2 && python3 -m unittest discover -s tools/tests -v`. Tests add `tools/` to `sys.path` themselves (`sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))`).
- Every container command is `docker exec <container> bash -ic '…'` (ROS_DOMAIN_ID=1 and the workspace are set by the interactive profile). Filter the profile noise lines `bash: cannot set terminal`, `bash: no job control`, `Sourcing`, `groups: cannot find name` from captured output.
- Fixtures live in `tools/tests/fixtures/run1/` and are copies of `docs/record/sim_hover_step_run1/` files (largest: `drone_1_odom.csv` 258 706 B — under the 300 KB trim threshold, keep whole).
- Thresholds (verbatim from MILESTONES §4 "Starling model: spawn + hover + steps"): hover thrust setpoint **0.12–0.20**; steps **settle < 3 s** (±0.1 m), **overshoot < 0.15 m**, **no ringing** (= 0 band re-entries at ±0.1 m). The `≤ 1 re-entry` loosening in the current report is removed.
- Event detector constants: `ONSET = 0.10 m/s`, `DONE = 0.02 m/s`, `QUIET_S = 0.8`, `MIN_RAMP_S = 0.3`, window `8.0 s` (or the next onset ≥ 2 s later), tail = last `0.5 s` of the window, `TAKEOFF_PHASE_S = 15.0` after arming.
- Sysid map (fixed): `MAV_SYS_ID` 2/3/4 = drone_1/2/3. Bag CSV times are seconds since the bag's first odometry message (wall clock).
- Sim-only (CLAUDE.md iron rule 9): nothing measured here is ported to the drone; every record/ledger text written by this plan carries "sim".
- Timezones: the laptop logs in SGT (`date +%T %Z`), the containers in UTC. Every time the report prints is labelled.
- Linear/ledger: the re-run is ledger **#18**; #17 keeps its row plus a one-line note (Task 9).

## Review Focus

Inputs the spec implies that could bite first; each is pinned by a test in the named task.

1. **A gentle velocity ramp (0.5 m/s², samples sitting in 0.05–0.10 m/s for 100 ms)** must yield exactly one event with onset at the first sample ≥ 0.10 m/s — never zero events. Task 3 `test_detect_gentle_ramp_single_event`.
2. **A horizontal command on x while the drone's largest motion is on y** must be flagged `axis_mismatch: true` and the report must print FAIL for that step, not measure y and call it x. Task 3 `test_measure_flags_axis_mismatch`, Task 5 `test_axis_mismatch_fails_step_row`.
3. **`isaac_evidence.txt` with `starling_cfg=0` (buffered stdout) or missing** must be UNVERIFIED and the run INCOMPLETE — never PASS "indirectly". Task 5 `test_starling_cfg_zero_is_unverified`.
4. **`armed_post.txt` holding profile garbage (`groups: …`) or only two readable values** must be UNVERIFIED. Task 5 `test_armed_post_garbage_is_unverified`, `test_armed_post_two_values_is_unverified`.
5. **`px4_arm_times.txt` missing** (drone_1 ulog lost again) must leave the time-scale gate UNVERIFIED and the verdict INCOMPLETE while the analysis still runs with scale 1.0 and says so. Task 3 `test_analyse_without_px4_times_assumes_scale_1`, Task 5 `test_missing_px4_times_is_unverified`.

Dependency graph: **T1, T2, T4 independent (parallel)** → **T3 after T2** → **T5 and T6 after T3 (parallel; T5 also after T4)** → **T7 after T1–T6** → **T8 and T9 after T7 (parallel)** → **T10 last**.

---

### Task 1: Our flight script + echo analyser move into `tools/`

**Files:**
- Create: `tools/sim_hover_step_test.sh` (copy of `AirStack/simulation/isaac-sim/tools/sim_hover_step_test.sh`, then edited)
- Create: `tools/analyze_step.py` (byte-identical copy of `AirStack/simulation/isaac-sim/tools/analyze_step.py`)
- Test: `tools/tests/test_scripts_syntax.py`
- Leave untouched: both originals under `AirStack/simulation/isaac-sim/tools/`

**Interfaces:**
- Produces: `tools/sim_hover_step_test.sh <drone>` with env `STEPS_PER_AXIS` (default `3`): takeoff → `start` → 10 hover-thrust samples → for k = 1..N on x: goal = current ± 1.0 m (sign `+` for odd k, `−` for even k), trace `/tmp/step_x_<k>.txt` (8 s) → same on z (`/tmp/step_z_<k>.txt`) → land. Also `/tmp/ascent.txt`. Prints `[HH:MM:SS] step x<k>: goal (…)` lines, `--- hover thrust samples … ---` header followed by ONE line of floats, `land: success=True`, `landed: IDLE …`.
- Produces: `tools/analyze_step.py <trace> <axis> <delta> [hz]` (unchanged CLI).

- [ ] **Step 1: Write the failing syntax/usage test**

```python
# tools/tests/test_scripts_syntax.py
import pathlib, subprocess, unittest
TOOLS = pathlib.Path(__file__).resolve().parents[1]

class ScriptSyntax(unittest.TestCase):
    def test_test_script_parses_and_sleeps(self):
        p = TOOLS / "sim_hover_step_test.sh"
        self.assertTrue(p.exists(), p)
        self.assertEqual(subprocess.run(["bash", "-n", str(p)]).returncode, 0)
        src = p.read_text()
        self.assertIn('wait_s(){ sleep "$1"; }', src)
        self.assertNotIn("ros2 topic echo /clock", src)
        self.assertIn("STEPS_PER_AXIS", src)

    def test_analyze_step_is_identical_copy(self):
        ours = (TOOLS / "analyze_step.py").read_bytes()
        theirs = (TOOLS.parent / "AirStack/simulation/isaac-sim/tools/analyze_step.py").read_bytes()
        self.assertEqual(ours, theirs)
```

- [ ] **Step 2: Run it**

Run: `cd /home/jeremychia/AirStack-starling-max2 && python3 -m unittest tools.tests.test_scripts_syntax -v`
Expected: FAIL — `AssertionError: False is not true : …/tools/sim_hover_step_test.sh` (file missing). (`tools/tests/__init__.py` may be needed for the dotted name: create it empty; `discover -s tools/tests` works without it.)

- [ ] **Step 3: Copy both files and edit the test script**

```bash
cd /home/jeremychia/AirStack-starling-max2
cp AirStack/simulation/isaac-sim/tools/analyze_step.py tools/analyze_step.py
cp AirStack/simulation/isaac-sim/tools/sim_hover_step_test.sh tools/sim_hover_step_test.sh
chmod +x tools/sim_hover_step_test.sh tools/analyze_step.py
```

Edits in `tools/sim_hover_step_test.sh` (header comment: say it is OURS, lives in `tools/`, is `docker cp`'d by `tools/sim_hover_step_run.sh`; the 2026-10-28 review found `/clock` is not visible in the robot container so `wait_s` is a real sleep):
- line 17 → `wait_s(){ sleep "$1"; }`
- after `D=${1:-drone_1}` add `N=${STEPS_PER_AXIS:-3}`
- replace lines 36–45 (the single x step and single z step) with two loops; the x loop:

```bash
for k in $(seq 1 "$N"); do
  sgn=$([ $((k % 2)) -eq 1 ] && echo 1.0 || echo -1.0)
  read st x y z <<< "$(pos)"
  gx=$(python3 -c "print(round($x+($sgn),3))")
  echo "[$(date +%T)] step x$k: goal ($gx, $y, $z) delta $sgn"
  ros2 topic pub --once /svg/$D/goal_command geometry_msgs/msg/PoseStamped "{header: {frame_id: map}, pose: {position: {x: $gx, y: $y, z: $z}}}" >/dev/null 2>&1 &
  timeout 8 ros2 topic echo /$D/odometry_conversion/odometry --field pose.pose.position 2>/dev/null > /tmp/step_x_$k.txt
done
```
  and the same for z (`gz`, `/tmp/step_z_$k.txt`, `step z$k`). Final `traces:` line lists `/tmp/ascent.txt /tmp/step_x_*.txt /tmp/step_z_*.txt`.

- [ ] **Step 4: Run the test**

Run: `cd /home/jeremychia/AirStack-starling-max2 && python3 -m unittest tools.tests.test_scripts_syntax -v`
Expected: `Ran 2 tests … OK`

- [ ] **Step 5: Verify the originals are untouched and commit**

Run: `git -C /home/jeremychia/AirStack-starling-max2 status --short AirStack/` → Expected: no output.
```bash
cd /home/jeremychia/AirStack-starling-max2
git add tools/sim_hover_step_test.sh tools/analyze_step.py tools/tests/test_scripts_syntax.py tools/tests/__init__.py
git commit -m "tools: hover-step flight script + echo analyser moved out of the CMU tree; wait_s is a real sleep; STEPS_PER_AXIS alternating ±1 m (default 3)"
```

---

### Task 2: Thin container-only bag reader + fixtures

**Files:**
- Rewrite: `tools/hover_step_bag.py` (reader only; all analysis removed)
- Create: `tools/tests/fixtures/run1/` — `drone_1_odom.csv`, `drone_1_cmd.csv`, `drone_1_state.csv` (from the real #17 bag via the new reader) plus copies of `docs/record/sim_hover_step_run1/{isaac_evidence.txt,test_stdout.log,armed_post.txt,params_ulog.txt,landing_evidence.txt,ulog_sysid_map.txt,odom_hz.txt,status_pre.json,caveats.txt,analyze.txt,bag_analysis.json}` and `res_watch.log` trimmed to its first 60 lines (`head -60`)
- Create: `tools/tests/fixtures/run1/px4_arm_times.txt` with the content printed in Task 4 step 5 (`arm_s=293.840613 disarm_s=394.710525 interval_s=100.869912 source=drone_2_sysid3_07_39_26.ulg sysid=3` — drone_2's ulog; drone_1's was lost in #17, the fixture documents that in a `# ` comment line)

**Interfaces:**
- Produces: `python3 /tmp/hover_step_bag.py <bag_dir> <drone> <csv_prefix>` (inside `airstack-robot-desktop-1`) → writes `<csv_prefix>_odom.csv` (`t_s,x,y,z`), `<csv_prefix>_cmd.csv` (`t_s,vx,vy,vz`, from `/<drone>/interface/mavros/setpoint_raw/local` `.velocity`), `<csv_prefix>_state.csv` (`t_s,armed,mode`; armed as `0`/`1`), all `t_s` = seconds since the first odometry message; prints one JSON line `{"bag": …, "drone": …, "odom_msgs": int, "cmd_msgs": int, "state_msgs": int, "t0_unix": float, "csv": [three paths]}`. Exit 1 with a message on stderr if the bag has no odometry for the drone.

- [ ] **Step 1: Write the reader** (`tools/hover_step_bag.py`, ~45 lines): keep lines 18–39 of the current file (open, type map, three topic names, collection loop), drop everything after; write the three CSVs with 3-decimal `t_s`, 4-decimal values; `mode` string unquoted (it never contains a comma).

- [ ] **Step 2: Verify in the container against the #17 bag (this also produces the fixtures)**

```bash
cd /home/jeremychia/AirStack-starling-max2 && mkdir -p tools/tests/fixtures/run1
docker cp ~/flight_logs/sim/sim_hover_step_run1/hover_step_20261028_074116 airstack-robot-desktop-1:/tmp/fixture_bag
docker cp tools/hover_step_bag.py airstack-robot-desktop-1:/tmp/
docker exec airstack-robot-desktop-1 bash -ic 'python3 /tmp/hover_step_bag.py /tmp/fixture_bag drone_1 /tmp/drone_1' 2>&1 | grep '^{'
for f in odom cmd state; do docker cp airstack-robot-desktop-1:/tmp/drone_1_$f.csv tools/tests/fixtures/run1/; done
docker exec airstack-robot-desktop-1 rm -rf /tmp/fixture_bag /tmp/drone_1_odom.csv /tmp/drone_1_cmd.csv /tmp/drone_1_state.csv
python3 - <<'EOF'
import csv
s=[(float(t),int(a)) for t,a,m in csv.reader(open("tools/tests/fixtures/run1/drone_1_state.csv")) if t!="t_s"]
tr=[round(s[i][0],2) for i in range(1,len(s)) if s[i][1]!=s[i-1][1]]
print("transitions", tr)
EOF
cmp tools/tests/fixtures/run1/drone_1_odom.csv docs/record/sim_hover_step_run1/drone_1_odom.csv && echo odom-identical
```
Expected: JSON line with `"odom_msgs": 8858`, `"cmd_msgs": 1555`, `state_msgs` > 0; `transitions [98.23, 174.55]`; `odom-identical`.

- [ ] **Step 3: Copy the remaining fixtures**

```bash
cd /home/jeremychia/AirStack-starling-max2/docs/record/sim_hover_step_run1
cp isaac_evidence.txt test_stdout.log armed_post.txt params_ulog.txt landing_evidence.txt ulog_sysid_map.txt odom_hz.txt status_pre.json caveats.txt analyze.txt bag_analysis.json ../../../tools/tests/fixtures/run1/
head -60 res_watch.log > ../../../tools/tests/fixtures/run1/res_watch.log
printf '# PX4 arm/disarm from drone_2 (sysid 3) ulog of ledger #17 — drone_1 ulog was lost; same session, same lockstep clock\narm_s=293.840613 disarm_s=394.710525 interval_s=100.869912 source=drone_2_sysid3_07_39_26.ulg sysid=3\n' > ../../../tools/tests/fixtures/run1/px4_arm_times.txt
du -sh ../../../tools/tests/fixtures/run1
```
Expected: total well under 1 MB (about 420 KB).

- [ ] **Step 4: Commit**

```bash
cd /home/jeremychia/AirStack-starling-max2
git add tools/hover_step_bag.py tools/tests/fixtures/run1
git commit -m "tools: hover_step_bag.py is now a thin CSV dumper (odom/cmd/state); ledger #17 artefacts saved as host test fixtures"
```

---

### Task 3: Pure-Python analysis module (`tools/hover_step_analysis.py`)

**Files:**
- Create: `tools/hover_step_analysis.py`
- Test: `tools/tests/test_hover_step_analysis.py`

**Interfaces:**
- Consumes: the three CSVs from Task 2; `px4_arm_times.txt` (`key=value` tokens on one line, `#` comment lines ignored).
- Produces (all in `tools/hover_step_analysis.py`):
  - `load_xyz_csv(path) -> list[tuple[float, float, float, float]]`
  - `load_state_csv(path) -> list[tuple[float, bool, str]]`
  - `load_px4_arm_times(path) -> dict | None` (keys `arm_s`, `disarm_s`, `interval_s`, `source`, `sysid`; `None` if the file is missing or lacks `arm_s`/`disarm_s`)
  - `arming_events(state) -> tuple[list[float], list[float], bool | None]` (arm times, disarm times, armed at end)
  - `compute_time_scale(px4_arm_s, px4_disarm_s, bag_arm_s, bag_disarm_s) -> float` = `(px4_disarm − px4_arm) / (bag_disarm − bag_arm)`; raises `ValueError` if either interval ≤ 1.0 s
  - `detect_events(cmd, onset=0.10, done=0.02, quiet_s=0.8, min_ramp_s=0.3) -> list[dict]` with keys `axis` (1/2/3), `onset`, `ramp_end`, `peak_v`; sorted by onset
  - `name_events(events, t_arm, odom, takeoff_phase_s=15.0, step_delta_m=1.0) -> list[dict]` adds `name` and `commanded_delta_m` (`±step_delta_m` for steps, `None` otherwise)
  - `settle_after_last_excursion(seg, ref, band) -> tuple[float | None, int, bool]` → (time of the FIRST in-band sample after the last excursion, re-entries into the band after the first entry, saturated)
  - `velocity_tracking(odom_win, cmd, axis, time_scale) -> dict` with `lag_s` (wall), `gain`, `residual_rms_mps`
  - `measure_event(event, odom, cmd, end, time_scale=1.0, band=0.1) -> dict` (schema below)
  - `summarise_steps(events) -> dict`
  - `analyse(odom, cmd, state, step_delta_m=1.0, px4_arm_times=None, drone="drone_1") -> dict`
  - `main(argv) -> int`: `--odom F --cmd F --state F [--px4-arm-times F] [--step-delta 1.0] [--drone drone_1] -o OUT.json`
- Output schema (`analyse`):
  ```
  {"drone", "odom_msgs", "cmd_msgs", "duration_s", "odom_rate_hz",
   "armed_at_s": [...], "disarmed_at_s": [...], "armed_at_end",
   "time_scale", "time_scale_source": "px4_arm_times.txt (sysid N)" | "assumed 1.0 (no px4_arm_times)",
   "px4_arm_interval_s", "bag_arm_interval_s",
   "events": [{"name", "axis" ("x"/"y"/"z", = commanded axis), "moved_most_axis", "axis_mismatch",
               "onset_s_from_bag_start", "onset_s_after_arming", "commanded_peak_speed_mps", "commanded_delta_m",
               "commander_ramp_s", "start_m", "final_m", "peak_m", "moved_m", "samples", "window_s",
               "tail": {"overshoot_m", "settle_s", "band_reentries", "saturated"},
               "goal": null | {"goal_m", "overshoot_m", "steady_state_error_m",
                               "settle_0p1_s", "settle_0p05_s", "settle_0p02_s",
                               "reentries_0p1", "reentries_0p05", "reentries_0p02", "saturated_0p1"},
               "velocity_tracking": {"lag_s", "gain", "residual_rms_mps"},
               "vehicle_time": {"settle_s", "commander_ramp_s", "settle_0p1_s", "settle_0p05_s", "settle_0p02_s", "lag_s"}}],
   "steps": {"x": {"n", "names", "settle_0p1_max_veh_s", "settle_0p1_median_veh_s", "overshoot_max_m",
                   "steady_state_error_max_m", "reentries_0p1_max", "any_axis_mismatch", "any_saturated"}, "z": {...}}}
  ```
  `overshoot_max_m` = max over the axis's steps of `max(tail.overshoot_m, goal.overshoot_m)`. `vehicle_time` values = wall value × `time_scale` (`None` stays `None`).

Algorithms the signatures do not determine:
- **Detector:** a sample is *loud* iff `|v| ≥ onset`. Walk each axis; an onset is a loud sample with `t − last_loud ≥ quiet_s` while no event is open (`last_loud` starts at −∞). The event's `ramp_end` is the first sample with `t − onset ≥ min_ramp_s` **and** `|v| < done`; `peak_v` = max-|·| sample in `[onset, ramp_end]`; after the event `last_loud = ramp_end`. Every loud sample that is not an onset only updates `last_loud`; samples in `[done, onset)` touch nothing (this is the quiet-timer fix). Onset time = the loud sample itself (not the one before).
- **Naming:** events with `0 ≤ onset − t_arm < takeoff_phase_s`: the z-up one → `takeoff`, the others `takeoff_lateral_<axis>`. Later: z with `peak_v < 0` and mean odom z over the last 0.5 s of its window (same window rule as the measurement below) `< 0.3 m` → `landing`; z otherwise → `step_z_<k>`; x/y → `step_<axis>_<k>` (k counts per axis from 1); `commanded_delta_m = +step_delta_m if peak_v > 0 else −step_delta_m` for steps only.
- **Measurement window:** `[onset, min(next onset ≥ 2 s later, onset + 8.0)]`; need ≥ 20 odometry samples else the event is dropped with `"skipped": "fewer than 20 samples"` kept in a top-level `"skipped_events"` list. `moved_most_axis` = axis with the largest `|last − first|` in the window; `axis_mismatch = moved_most_axis != axis`. `start_m` = first odom value on the axis in the window; `final_m` = mean of the tail; sign = sign of `commanded_delta_m` if set else of `final − start`; `peak_m` = max (sign +) or min (sign −). Tail metrics reference `final_m`; goal metrics reference `goal_m = start_m + commanded_delta_m`.
- **Settle:** indices `out` where `|v − ref| > band`; none → `(0.0, 0, False)`; last excursion at the final sample → `(window_s, reentries, True)`; else settle = `seg[last_out + 1].t`. Re-entries = number of False→True transitions of the in-band mask minus one if the first sample was out of band.
- **Velocity tracking:** `vm = moving_average(np.gradient(p, t_wall), 5) / time_scale` (the ÷ time_scale is essential: on the #17 data differentiating in wall time inflates the gain by exactly the time scale); `vc(t) = np.interp(t, t_cmd, v_cmd_axis)`; lag = argmin over `np.arange(-0.5, 1.0001, 0.025)` of RMS(`vm(t) − vc(t − lag)`); `gain = max|vm| / max|vc(t)|` (guard 1e-6); `residual_rms_mps` = RMS at the best lag.

- [ ] **Step 1: Write the failing tests**

```python
# tools/tests/test_hover_step_analysis.py
import json, math, pathlib, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import hover_step_analysis as A
FX = pathlib.Path(__file__).resolve().parent / "fixtures" / "run1"

def load():
    return (A.load_xyz_csv(FX / "drone_1_odom.csv"), A.load_xyz_csv(FX / "drone_1_cmd.csv"),
            A.load_state_csv(FX / "drone_1_state.csv"))

class Detector(unittest.TestCase):
    def test_detect_gentle_ramp_single_event(self):          # Review Focus 1
        cmd = [(i / 20, 0.0, 0.0, 0.0) for i in range(40)]  # 2 s quiet
        cmd += [(2 + i / 20, min(0.5 * i / 20, 0.6), 0.0, 0.0) for i in range(80)]   # 0.5 m/s² ramp to 0.6 m/s
        cmd += [(6 + i / 20, 0.0, 0.0, 0.0) for i in range(40)]
        ev = A.detect_events(cmd)
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["axis"], 1)
        self.assertAlmostEqual(ev[0]["onset"], 2.2, places=6)   # first sample with v >= 0.10
        self.assertAlmostEqual(ev[0]["ramp_end"], 6.0, places=6)

    def test_fixture_events_axes_and_onsets(self):
        _, cmd, _ = load()
        ev = A.detect_events(cmd)
        self.assertEqual([e["axis"] for e in ev], [1, 2, 3, 1, 3, 3])
        self.assertAlmostEqual(ev[3]["onset"], 149.54, places=2)
        self.assertAlmostEqual(ev[4]["onset"], 158.59, places=2)
        self.assertAlmostEqual(ev[5]["onset"], 170.64, places=2)
        self.assertAlmostEqual(ev[3]["peak_v"], 0.917, places=2)

class Naming(unittest.TestCase):
    def test_fixture_names(self):
        odom, cmd, state = load()
        arm, _, _ = A.arming_events(state)
        names = [e["name"] for e in A.name_events(A.detect_events(cmd), arm[0], odom)]
        self.assertEqual(names, ["takeoff_lateral_x", "takeoff_lateral_y", "takeoff", "step_x_1", "step_z_1", "landing"])

    def test_three_alternating_z_steps_then_landing(self):
        # synthetic: arm at 0, takeoff z-up at 1 s, then z +1/−1/+1 at 30/40/50 s, landing (z-down to the floor) at 60 s
        def pulse(t0, ax, sgn):
            return [(t0 + i / 20, *(sgn * 0.9 if a == ax else 0.0 for a in (1, 2, 3))) for i in range(30)]
        quiet = lambda t0, n: [(t0 + i / 20, 0.0, 0.0, 0.0) for i in range(n)]
        cmd = quiet(0, 20) + pulse(1, 3, +1) + quiet(2.5, 550) + pulse(30, 3, +1) + quiet(31.5, 170) \
              + pulse(40, 3, -1) + quiet(41.5, 170) + pulse(50, 3, +1) + quiet(51.5, 170) + pulse(60, 3, -1) + quiet(61.5, 100)
        z = lambda t: 1.2 if t < 30 else (2.2 if t < 40 else (1.2 if t < 50 else (2.2 if t < 60 else 0.05)))
        odom = [(t, 0.0, 0.0, 0.0 if t < 1.5 else z(t)) for t in (i / 40 for i in range(70 * 40))]
        names = [e["name"] for e in A.name_events(A.detect_events(cmd), 0.0, odom)]
        self.assertEqual(names, ["takeoff", "step_z_1", "step_z_2", "step_z_3", "landing"])

class Measurement(unittest.TestCase):
    def test_step_x_metrics_on_fixture(self):
        odom, cmd, state = load()
        res = A.analyse(odom, cmd, state, px4_arm_times=A.load_px4_arm_times(FX / "px4_arm_times.txt"))
        sx = next(e for e in res["events"] if e["name"] == "step_x_1")
        self.assertEqual(sx["axis"], "x"); self.assertFalse(sx["axis_mismatch"])
        self.assertAlmostEqual(sx["start_m"], 2.006, delta=0.002)
        self.assertAlmostEqual(sx["final_m"], 3.003, delta=0.002)
        self.assertAlmostEqual(sx["tail"]["overshoot_m"], 0.054, delta=0.003)
        self.assertAlmostEqual(sx["tail"]["settle_s"], 1.84, delta=0.03)      # first in-band sample after the last excursion
        self.assertEqual(sx["tail"]["band_reentries"], 0)
        self.assertAlmostEqual(sx["goal"]["goal_m"], 3.006, delta=0.002)
        self.assertAlmostEqual(sx["goal"]["overshoot_m"], 0.052, delta=0.003)
        self.assertAlmostEqual(sx["goal"]["steady_state_error_m"], -0.002, delta=0.003)
        self.assertAlmostEqual(sx["goal"]["settle_0p05_s"], 3.29, delta=0.05)
        self.assertEqual(sx["goal"]["reentries_0p05"], 1)
        self.assertAlmostEqual(sx["commander_ramp_s"], 2.10, delta=0.03)
        self.assertAlmostEqual(sx["vehicle_time"]["settle_s"], 1.84 * res["time_scale"], delta=0.05)

    def test_time_scale_from_fixture(self):
        odom, cmd, state = load()
        res = A.analyse(odom, cmd, state, px4_arm_times=A.load_px4_arm_times(FX / "px4_arm_times.txt"))
        self.assertAlmostEqual(res["bag_arm_interval_s"], 76.32, delta=0.02)
        self.assertAlmostEqual(res["px4_arm_interval_s"], 100.87, delta=0.01)
        self.assertAlmostEqual(res["time_scale"], 1.3217, delta=0.002)
        self.assertIn("sysid 3", res["time_scale_source"])

    def test_velocity_tracking_gain_is_in_vehicle_time(self):
        odom, cmd, state = load()
        res = A.analyse(odom, cmd, state, px4_arm_times=A.load_px4_arm_times(FX / "px4_arm_times.txt"))
        sz = next(e for e in res["events"] if e["name"] == "step_z_1")
        self.assertAlmostEqual(sz["velocity_tracking"]["gain"], 1.01, delta=0.05)   # 1.336 if the ÷ time_scale is missing
        self.assertTrue(0.0 <= sz["velocity_tracking"]["lag_s"] <= 0.6)
        self.assertLess(sz["velocity_tracking"]["residual_rms_mps"], 0.15)

    def test_analyse_without_px4_times_assumes_scale_1(self):   # Review Focus 5
        odom, cmd, state = load()
        res = A.analyse(odom, cmd, state, px4_arm_times=None)
        self.assertEqual(res["time_scale"], 1.0)
        self.assertTrue(res["time_scale_source"].startswith("assumed 1.0"))
        sx = next(e for e in res["events"] if e["name"] == "step_x_1")
        self.assertEqual(sx["vehicle_time"]["settle_s"], sx["tail"]["settle_s"])

    def test_measure_flags_axis_mismatch(self):                  # Review Focus 2
        odom, cmd, state = load()
        swapped = [(t, y, x, z) for t, x, y, z in odom]          # the drone "moved" on y while x was commanded
        res = A.analyse(swapped, cmd, state)
        sx = next(e for e in res["events"] if e["name"] == "step_x_1")
        self.assertTrue(sx["axis_mismatch"]); self.assertEqual(sx["moved_most_axis"], "y")
        self.assertTrue(res["steps"]["x"]["any_axis_mismatch"])

    def test_settle_first_in_band_sample(self):
        seg = [(0.0, 0.0), (0.1, 0.5), (0.2, 0.95), (0.3, 1.12), (0.4, 1.05), (0.5, 1.0), (0.6, 1.0)]
        settle, reent, sat = A.settle_after_last_excursion(seg, 1.0, 0.1)
        self.assertAlmostEqual(settle, 0.4); self.assertEqual(reent, 1); self.assertFalse(sat)

    def test_steps_summary_gates_on_max(self):
        odom, cmd, state = load()
        res = A.analyse(odom, cmd, state, px4_arm_times=A.load_px4_arm_times(FX / "px4_arm_times.txt"))
        self.assertEqual(res["steps"]["x"]["n"], 1); self.assertEqual(res["steps"]["z"]["n"], 1)
        self.assertAlmostEqual(res["steps"]["x"]["settle_0p1_max_veh_s"], 1.84 * 1.3217, delta=0.06)
        self.assertEqual(res["steps"]["z"]["reentries_0p1_max"], 0)

class Cli(unittest.TestCase):
    def test_main_writes_json(self):
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / "bag_analysis.json"
            rc = A.main(["--odom", str(FX / "drone_1_odom.csv"), "--cmd", str(FX / "drone_1_cmd.csv"),
                         "--state", str(FX / "drone_1_state.csv"), "--px4-arm-times", str(FX / "px4_arm_times.txt"), "-o", str(out)])
            self.assertEqual(rc, 0)
            j = json.loads(out.read_text())
            self.assertEqual(j["odom_msgs"], 8858); self.assertIn("steps", j)
```

- [ ] **Step 2: Run them**

Run: `cd /home/jeremychia/AirStack-starling-max2 && python3 -m unittest tools.tests.test_hover_step_analysis -v`
Expected: FAIL/ERROR with `ModuleNotFoundError: No module named 'hover_step_analysis'`.

- [ ] **Step 3: Implement `tools/hover_step_analysis.py`** with the signatures and algorithms above (numpy allowed; no ROS imports). Module docstring states the definitions (onset, settle, tail vs goal, time scale, velocity tracking in vehicle time) in six lines so the record can cite it.

- [ ] **Step 4: Run the tests**

Run: `cd /home/jeremychia/AirStack-starling-max2 && python3 -m unittest tools.tests.test_hover_step_analysis -v`
Expected: `Ran 12 tests … OK`. If a fixture number misses by more than its delta, print the computed value, confirm by hand against the prototype values quoted in the test (they were computed from these exact CSVs on 2026-10-28), and fix the code — not the assertion.

- [ ] **Step 5: Commit**

```bash
cd /home/jeremychia/AirStack-starling-max2
git add tools/hover_step_analysis.py tools/tests/test_hover_step_analysis.py
git commit -m "tools: hover_step_analysis.py — pure-python step analysis (commanded axis, quiet-timer fix, first-in-band settle, goal-referenced metrics, velocity tracking, wall + vehicle time) with fixture tests"
```

---

### Task 4: PX4 arm/disarm times from the ulog (`tools/hover_step_timescale.py`)

**Files:**
- Create: `tools/hover_step_timescale.py`
- Test: `tools/tests/test_hover_step_timescale.py`

**Interfaces:**
- Produces: `arming_transitions(timestamps_us, arming_state) -> tuple[float | None, float | None]` — first `1→2` and first subsequent `2→1` transition, in seconds (`timestamp / 1e6`, PX4 boot time); `format_line(arm_s, disarm_s, source, sysid) -> str` → `arm_s=<.6f> disarm_s=<.6f> interval_s=<.6f> source=<basename> sysid=<n>`; `main(argv) -> int`: `hover_step_timescale.py <ulog>` reads `vehicle_status` with pyulog (`message_name_filter_list=['vehicle_status']`), prints the line, exit 3 if no arm/disarm pair.
- Consumed by: Task 3 `load_px4_arm_times` (same tokens), Task 7 `collect`.

- [ ] **Step 1: Write the failing test**

```python
# tools/tests/test_hover_step_timescale.py
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import hover_step_timescale as T

class Transitions(unittest.TestCase):
    def test_first_arm_then_disarm(self):
        ts = [i * 1_000_000 for i in range(10)]
        st = [1, 1, 2, 2, 2, 1, 1, 2, 1, 1]
        self.assertEqual(T.arming_transitions(ts, st), (2.0, 5.0))
    def test_never_armed(self):
        self.assertEqual(T.arming_transitions([0, 1_000_000], [1, 1]), (None, None))
    def test_format_line(self):
        self.assertEqual(T.format_line(293.840613, 394.710525, "/tmp/x/07_39_26.ulg", 3),
                         "arm_s=293.840613 disarm_s=394.710525 interval_s=100.869912 source=07_39_26.ulg sysid=3")
```

- [ ] **Step 2: Run it** — `cd /home/jeremychia/AirStack-starling-max2 && python3 -m unittest tools.tests.test_hover_step_timescale -v` → Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement** — pyulog imported inside `main()` only (host has none). `main` also reads `MAV_SYS_ID` from `ULog(...).initial_parameters`.

- [ ] **Step 4: Run** — same command → Expected: `Ran 3 tests … OK`.

- [ ] **Step 5: Verify in the Isaac container on the saved drone_2 ulog**

```bash
docker cp ~/flight_logs/sim/sim_hover_step_run1/drone_2_sysid3_07_39_26.ulg isaac-sim:/tmp/ts_probe.ulg
docker cp /home/jeremychia/AirStack-starling-max2/tools/hover_step_timescale.py isaac-sim:/tmp/
docker exec isaac-sim python3 /tmp/hover_step_timescale.py /tmp/ts_probe.ulg; echo rc=$?
docker exec isaac-sim rm -f /tmp/ts_probe.ulg /tmp/hover_step_timescale.py
```
Expected: `arm_s=293.840613 disarm_s=394.710525 interval_s=100.869912 source=ts_probe.ulg sysid=3` and `rc=0`.

- [ ] **Step 6: Commit**

```bash
cd /home/jeremychia/AirStack-starling-max2
git add tools/hover_step_timescale.py tools/tests/test_hover_step_timescale.py
git commit -m "tools: hover_step_timescale.py prints PX4 arm/disarm times from a ulog (vehicle-time scale for the step report)"
```

---

### Task 5: Report rewrite — fail-closed rows, vehicle-time gates, verdict history

**Files:**
- Rewrite: `tools/hover_step_report.py`
- Test: `tools/tests/test_hover_step_report.py`

**Interfaces:**
- Consumes: `bag_analysis.json` (Task 3 schema), `px4_arm_times.txt`, `run_meta.txt` (Task 7: `key=value` lines `head`, `head_short`, `dirty_tools`, `started`, `tz`, `run`), `clock_check.txt` (`clock_rc=0|1`), `armed_post.txt` (lines `drone_N armed: true|false`), `verdicts.log`, and the existing text artefacts.
- Produces:
  - `Row = dataclasses.dataclass(check: str, criterion: str, measured: str, baseline: str, verdict: str, gate: bool)`
  - `row(rows, check, crit, meas, base, ok, gate=True)`: gate → `PASS`/`FAIL`/`UNVERIFIED` (ok True/False/None); `gate=False` → verdict `info` always
  - `parse_thrust_line(test_stdout: str) -> list[float] | None` — the line AFTER `--- hover thrust samples`; accept only if it holds ≥ 5 floats all in `[0, 1]`; else `None` (no ulog fallback)
  - `parse_armed_post(text: str) -> dict[str, bool] | None` — needs exactly `drone_1`, `drone_2`, `drone_3` each with `armed: true|false`; else `None`
  - `build_rows(out: pathlib.Path, heavy: pathlib.Path | None) -> tuple[list[Row], dict]` (rows, context dict for the markdown)
  - `overall_verdict(rows) -> str` — `FAIL` if any gate FAIL, else `INCOMPLETE` if any gate UNVERIFIED, else `PASS`
  - `append_verdict(out, verdict, rows, head_short) -> str` — appends `"<ISO local time with tz> head=<short> verdict=<V> fail=<n> unverified=<n>"` to `out/verdicts.log`, returns the line
  - `render_md(out, rows, ctx, verdict, history: list[str]) -> str`
  - `main(argv) -> int`: `hover_step_report.py <run_dir> [--heavy DIR] [--record PATH] [--no-verdict-log]`; exit 0 PASS, 2 INCOMPLETE, 1 FAIL
- Row set (G = gate, I = info):
  - Isaac launch: `autostart ≥ 3` G, `ready == 3` G, `unknown_model == 0` G, `cooking == 0` G, **`starling_cfg ≥ 3` G (0 or missing → UNVERIFIED with measured "0 — launcher print not captured")**
  - PX4 params from `params_ulog.txt` ONLY (6 keys as today) G; measured `n/a` → UNVERIFIED
  - `takeoff accepted`, `start accepted`, `land accepted + landed: IDLE` G
  - `hover thrust setpoint (MAVROS target_attitude)` G: median of `parse_thrust_line`; `None` → UNVERIFIED
  - `time scale (PX4 s per wall s)` G: PASS if `time_scale_source` starts with `px4_arm_times.txt` and `0.5 < scale < 3.0`; UNVERIFIED if assumed
  - per axis `ax` in `("x", "z")` from `steps[ax]` — the check strings are exactly `f"{ax} step: overshoot max"` (< 0.15 m; measured shows tail and goal values) G; `f"{ax} step: settle ±0.1 m vs goal (max of {n})"` (< 3.0 s vehicle; FAIL also when `any_saturated`) G; `f"{ax} step: ringing"` (`reentries_0p1_max == 0`) G; `f"{ax} step: commanded axis moved most"` (`not any_axis_mismatch`) G; `f"{ax} step: settle ±0.05 / ±0.02 m vs goal (median)"` I; `f"{ax} step: steady-state error max"` I; `f"{ax} step: velocity tracking"` (lag, gain, residual per step) I; `f"{ax} step: settle vs tail (old method)"` I; `f"{ax} step: vs #3 (echo method)"` I (from `analyze.txt`, as now). Every duration's measured string starts `f"{veh:.2f} s [{wall:.2f} s wall]"` (vehicle first, wall in brackets), then any suffix.
  - `takeoff climb`, `landing descent` I
  - `landing: 'landed, disarmed' x3 (commander ACK log, not an arming display)` I
  - `post-flight armed=false x3 (MAVROS state)` G via `parse_armed_post`; `None` → UNVERIFIED
  - `WiFi firmware alerts` G; `rosbag copied + readable` G: bag dir with `metadata.yaml` under heavy AND `odom_msgs > 0` → PASS; no `hover_step_*` dir under heavy → UNVERIFIED; dir present but no `metadata.yaml` or `odom_msgs == 0` → FAIL; `PX4 ulogs one per sysid 2/3/4` G: `ulog_sysid_map.txt` missing/empty → UNVERIFIED, present but sysids ≠ `["2","3","4"]` → FAIL
  - `/clock visible in the robot container` I (from `clock_check.txt`); `code that ran` I (`run_meta.txt` head vs `git rev-parse --short HEAD` at report time: "ran at X, report at Y" when they differ; `dirty_tools > 0` appended as "(tools/ had uncommitted changes)"); `driver verdict history` I (every `verdicts.log` line, newest last, before this run's own line is appended)
- Markdown: header line `RECORD · SIM — <run>`; title with `started` from `run_meta.txt` labelled with its `tz` and the flight span from `test_stdout.log` labelled `UTC (container clock)`; verdict; Setup table (Driver row cites `tools/sim_hover_step_run.sh` + `tools/sim_hover_step_test.sh` + `tools/analyze_step.py`, commit from `run_meta.txt`); Pass/fail table; the line `Rows marked info are informational and never pass or fail the run.`; a **Thresholds** line: `0.15 m / 3.0 s / 0 re-entries / thrust 0.12–0.20 come from MILESTONES §4 (set 2026-10-19 in docs/superpowers/plans/2026-10-19-starling2max-sim.md, bracketed by the Iris reading of ledger #2 — 0.14 m / 3.6 s — not derived from a flight requirement). Gated values are PX4 vehicle time; wall-clock values in brackets.`; figure if present; Evidence; Files; Caveats (from `caveats.txt` + the fixed lines: sim path is TwistStamped→MAVROS not the real drone's trajectory path; n = STEPS_PER_AXIS per axis, one launch; commander braking law shapes the ±0.1 m settle); Ledger row draft for **#18** (template in Task 10).

- [ ] **Step 1: Write the failing tests**

```python
# tools/tests/test_hover_step_report.py
import json, pathlib, shutil, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import hover_step_report as R
import hover_step_analysis as A
FX = pathlib.Path(__file__).resolve().parent / "fixtures" / "run1"

def make_run(tmp, **overrides):
    """Fixture run dir: real #17 artefacts + a fresh bag_analysis.json from the Task 3 module + run_meta + clock + armed."""
    out = pathlib.Path(tmp) / "sim_hover_step_runX"; out.mkdir()
    for f in FX.iterdir():
        if f.name != "bag_analysis.json": shutil.copy(f, out / f.name)
    odom, cmd, state = (A.load_xyz_csv(out / "drone_1_odom.csv"), A.load_xyz_csv(out / "drone_1_cmd.csv"), A.load_state_csv(out / "drone_1_state.csv"))
    (out / "bag_analysis.json").write_text(json.dumps(A.analyse(odom, cmd, state, px4_arm_times=A.load_px4_arm_times(out / "px4_arm_times.txt"))))
    (out / "run_meta.txt").write_text("head=0123456789abcdef\nhead_short=0123456\ndirty_tools=0\nstarted=2026-10-28T15:39:01+08:00\ntz=+08\nrun=sim_hover_step_runX\n")
    (out / "clock_check.txt").write_text("clock_rc=1\n")
    (out / "armed_post.txt").write_text("drone_1 armed: false\ndrone_2 armed: false\ndrone_3 armed: false\n")
    (out / "isaac_evidence.txt").write_text("model_line=3 starling_cfg=3 autostart=3 unknown_model=0 cooking=0 ready=3\n")
    heavy = pathlib.Path(tmp) / "heavy"; (heavy / "hover_step_20261028_074116").mkdir(parents=True)
    (heavy / "hover_step_20261028_074116" / "metadata.yaml").write_text("rosbag2_bagfile_information: {}\n")
    for k, v in overrides.items():
        if v is None: (out / k).unlink(missing_ok=True)
        else: (out / k).write_text(v)
    return out, heavy

def verdict_of(rows, prefix):
    return next(r.verdict for r in rows if r.check.startswith(prefix))

class Rows(unittest.TestCase):
    def test_clean_fixture_is_pass(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d)
            rows, ctx = R.build_rows(out, heavy)
            self.assertEqual(R.overall_verdict(rows), "PASS", [(r.check, r.verdict, r.measured) for r in rows if r.verdict not in ("PASS", "info")])
            self.assertTrue(all(r.verdict == "info" for r in rows if not r.gate))
            self.assertNotIn("PASS", [r.verdict for r in rows if not r.gate])

    def test_vehicle_time_is_gated_with_wall_in_brackets(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d)
            rows, _ = R.build_rows(out, heavy)
            r = next(r for r in rows if r.check.startswith("x step") and "settle ±0.1" in r.check)
            self.assertRegex(r.measured, r"^2\.4\d s \[1\.8\d s wall\]")

    def test_starling_cfg_zero_is_unverified(self):            # Review Focus 3
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d, **{"isaac_evidence.txt": "model_line=0 starling_cfg=0 autostart=3 unknown_model=0 cooking=0 ready=3\n"})
            rows, _ = R.build_rows(out, heavy)
            self.assertEqual(verdict_of(rows, "Isaac launch: Starling2MaxConfig"), "UNVERIFIED")
            self.assertEqual(R.overall_verdict(rows), "INCOMPLETE")

    def test_armed_post_garbage_is_unverified(self):           # Review Focus 4
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d, **{"armed_post.txt": "drone_1 armed: groups: cannot find name for group ID 992\n" * 3})
            rows, _ = R.build_rows(out, heavy)
            self.assertEqual(verdict_of(rows, "post-flight armed=false x3"), "UNVERIFIED")

    def test_armed_post_two_values_is_unverified(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d, **{"armed_post.txt": "drone_1 armed: false\ndrone_2 armed: false\n"})
            rows, _ = R.build_rows(out, heavy)
            self.assertEqual(verdict_of(rows, "post-flight armed=false x3"), "UNVERIFIED")

    def test_armed_true_fails(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d, **{"armed_post.txt": "drone_1 armed: true\ndrone_2 armed: false\ndrone_3 armed: false\n"})
            rows, _ = R.build_rows(out, heavy)
            self.assertEqual(verdict_of(rows, "post-flight armed=false x3"), "FAIL")

    def test_thrust_parser_fail_closed(self):
        self.assertIsNone(R.parse_thrust_line("--- hover thrust samples ---\nulog thrust_setpoint median(mid-third) 0.001\n"))
        self.assertIsNone(R.parse_thrust_line("--- hover thrust samples ---\n0.15 0.15 0.15\n"))
        self.assertEqual(len(R.parse_thrust_line((FX / "test_stdout.log").read_text())), 10)
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d, **{"test_stdout.log": (FX / "test_stdout.log").read_text().replace("--- hover thrust samples", "--- nothing")})
            rows, _ = R.build_rows(out, heavy)
            self.assertEqual(verdict_of(rows, "hover thrust setpoint"), "UNVERIFIED")

    def test_missing_px4_times_is_unverified(self):           # Review Focus 5
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d)
            odom, cmd, state = (A.load_xyz_csv(out / "drone_1_odom.csv"), A.load_xyz_csv(out / "drone_1_cmd.csv"), A.load_state_csv(out / "drone_1_state.csv"))
            (out / "bag_analysis.json").write_text(json.dumps(A.analyse(odom, cmd, state, px4_arm_times=None)))
            rows, _ = R.build_rows(out, heavy)
            self.assertEqual(verdict_of(rows, "time scale"), "UNVERIFIED")
            self.assertEqual(R.overall_verdict(rows), "INCOMPLETE")

    def test_axis_mismatch_fails_step_row(self):               # Review Focus 2
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d)
            j = json.loads((out / "bag_analysis.json").read_text()); j["steps"]["x"]["any_axis_mismatch"] = True
            (out / "bag_analysis.json").write_text(json.dumps(j))
            rows, _ = R.build_rows(out, heavy)
            self.assertEqual(verdict_of(rows, "x step: commanded axis moved most"), "FAIL")

    def test_ringing_gate_is_zero_reentries(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d)
            j = json.loads((out / "bag_analysis.json").read_text()); j["steps"]["z"]["reentries_0p1_max"] = 1
            (out / "bag_analysis.json").write_text(json.dumps(j))
            rows, _ = R.build_rows(out, heavy)
            self.assertEqual(verdict_of(rows, "z step: ringing"), "FAIL")

    def test_missing_bag_and_ulogs_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d, **{"ulog_sysid_map.txt": "3 /tmp/a.ulg 1\n4 /tmp/b.ulg 1\n"})
            rows, _ = R.build_rows(out, pathlib.Path(d) / "nowhere")
            self.assertEqual(verdict_of(rows, "rosbag"), "UNVERIFIED")
            self.assertEqual(verdict_of(rows, "PX4 ulogs"), "FAIL")

class VerdictLog(unittest.TestCase):
    def test_history_row_and_append(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d, **{"verdicts.log": "2026-10-28T15:45:58+08:00 head=76cd405 verdict=FAIL fail=3 unverified=0\n"})
            rec = pathlib.Path(d) / "rec.md"
            rc = R.main([str(out), "--heavy", str(heavy), "--record", str(rec)])
            self.assertEqual(rc, 0)
            lines = (out / "verdicts.log").read_text().splitlines()
            self.assertEqual(len(lines), 2); self.assertIn("verdict=PASS", lines[1])
            md = rec.read_text()
            self.assertIn("verdict=FAIL fail=3", md)            # the earlier generation is visible in the record
            self.assertIn("UTC (container clock)", md); self.assertIn("+08", md)
            self.assertIn("MILESTONES §4", md)

    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d, **{"isaac_evidence.txt": "starling_cfg=0 autostart=3 unknown_model=0 cooking=0 ready=3\n"})
            self.assertEqual(R.main([str(out), "--heavy", str(heavy), "--record", str(pathlib.Path(d) / "r.md"), "--no-verdict-log"]), 2)
```

- [ ] **Step 2: Run** — `cd /home/jeremychia/AirStack-starling-max2 && python3 -m unittest tools.tests.test_hover_step_report -v` → Expected: ERROR `AttributeError: module 'hover_step_report' has no attribute 'build_rows'` (the current file also executes on import with no argv — the rewrite must put everything under functions and `if __name__ == "__main__": sys.exit(main(sys.argv[1:]))`).

- [ ] **Step 3: Rewrite `tools/hover_step_report.py`** per the Interfaces block. Keep `EXPECT_PARAMS`, `BASE` (#3 numbers, info rows only), the markdown skeleton and the Evidence/Files sections from the current file; drop `trace_stats`, the MAVROS params fallback, the ulog thrust fallback, the bag-only disarm fallback and `gate=bool(sc)`.

- [ ] **Step 4: Run** — same command → Expected: `Ran 13 tests … OK`. Then the whole suite: `python3 -m unittest discover -s tools/tests -v` → all OK.

- [ ] **Step 5: Commit**

```bash
cd /home/jeremychia/AirStack-starling-max2
git add tools/hover_step_report.py tools/tests/test_hover_step_report.py
git commit -m "tools: hover_step_report.py fails closed — info vs gate rows, UNVERIFIED→INCOMPLETE, vehicle-time goal-referenced gates (max over steps), 0-re-entry ringing, strict thrust/armed parsers, verdicts.log history, thresholds provenance, timezone labels"
```

---

### Task 6: Plot follows the new analysis schema

**Files:**
- Modify: `tools/hover_step_plot.py`
- Test: `tools/tests/test_hover_step_plot.py`

**Interfaces:**
- Consumes: `bag_analysis.json` (Task 3), `drone_1_odom.csv`, `drone_1_cmd.csv`.
- Produces: `tools/hover_step_plot.py <run_dir>` → `<run_dir>/step_response.png`; `panel_order(events: list[dict]) -> list[tuple[str, str]]` = `takeoff`, then every `step_x_*`, every `step_z_*` (sorted by k), then `landing` — one column each, so N = 3 gives 8 columns.

- [ ] **Step 1: Write the failing test**

```python
# tools/tests/test_hover_step_plot.py
import json, pathlib, shutil, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import hover_step_plot as P
import hover_step_analysis as A
FX = pathlib.Path(__file__).resolve().parent / "fixtures" / "run1"

class Plot(unittest.TestCase):
    def test_panel_order_handles_n_steps(self):
        ev = [{"name": n} for n in ["takeoff_lateral_x", "takeoff", "step_x_1", "step_x_2", "step_z_1", "landing"]]
        self.assertEqual([n for n, _ in P.panel_order(ev)], ["takeoff", "step_x_1", "step_x_2", "step_z_1", "landing"])

    def test_renders_png_from_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d)
            for f in ("drone_1_odom.csv", "drone_1_cmd.csv", "drone_1_state.csv", "px4_arm_times.txt"): shutil.copy(FX / f, out / f)
            odom, cmd, state = A.load_xyz_csv(out / "drone_1_odom.csv"), A.load_xyz_csv(out / "drone_1_cmd.csv"), A.load_state_csv(out / "drone_1_state.csv")
            (out / "bag_analysis.json").write_text(json.dumps(A.analyse(odom, cmd, state, px4_arm_times=A.load_px4_arm_times(out / "px4_arm_times.txt"))))
            P.main([str(out)])
            self.assertGreater((out / "step_response.png").stat().st_size, 20_000)
```

- [ ] **Step 2: Run** — `python3 -m unittest tools.tests.test_hover_step_plot -v` → Expected: `AttributeError: … no attribute 'panel_order'`.

- [ ] **Step 3: Modify the plot**: wrap in `main(argv)`; add `panel_order`; read `onset_s_from_bag_start`, `final_m`, `tail["settle_s"]`, `tail["overshoot_m"]`, `goal["goal_m"]` (dotted line when present), `goal["reentries_0p1"]`, `commander_ramp_s`; x-axis label `time since onset (wall s; vehicle time = wall × <time_scale:.3f>)`; title subtitle names the time scale source; column count = `len(panel_order)`, figure width `3.4 × columns`.

- [ ] **Step 4: Run** → `Ran 2 tests … OK`. Open the PNG once (`xdg-open` or the Read tool) and check the x-step panel shows the goal line at 3.006 and settle 1.84 s.

- [ ] **Step 5: Commit**

```bash
cd /home/jeremychia/AirStack-starling-max2
git add tools/hover_step_plot.py tools/tests/test_hover_step_plot.py
git commit -m "tools: hover_step_plot.py reads the new analysis schema (N steps per axis, goal line, vehicle-time scale in the axis label)"
```

---

### Task 7: Wrapper rewrite (`tools/sim_hover_step_run.sh`)

**Files:**
- Rewrite: `tools/sim_hover_step_run.sh`
- Test: `tools/tests/test_scripts_syntax.py` (add two tests) + manual `status`/usage checks

**Interfaces:**
- Consumes: `tools/sim_hover_step_test.sh`, `tools/analyze_step.py` (T1), `tools/hover_step_bag.py` (T2), `tools/hover_step_analysis.py` (T3), `tools/hover_step_timescale.py` (T4), `tools/hover_step_report.py` (T5), `tools/hover_step_plot.py` (T6), `localisation/scripts/sim_resources_watch.sh`.
- Produces: phases `precheck up watch isaac interfaces commander params fly collect down analyse report | all | status`; `all` = all of them in that order, stops at the first `fail`, containers left up. Files in `$OUT=docs/record/<run>/`: `run.log`, `commands.sh`, `run_meta.txt`, `isaac_evidence.txt`, `clock_check.txt`, `odom_hz.txt`, `topics_of_interest.txt`, `status_pre.json`, `status_post.json`, `bag_status_pre.json`, `params_mavros*.txt`, `params_ulog.txt`, `test_stdout.log`, `armed_post.txt`, `landing_evidence.txt`, `analyze.txt`, `ascent.txt`, `step_x_<k>.txt`, `step_z_<k>.txt`, `ulog_list.txt`, `ulog_sysid_map.txt`, `ulogs_copied.ok`, `px4_arm_times.txt`, `bag_path.txt`, `bag_evidence.txt`, `drone_1_{odom,cmd,state}.csv`, `bag_analysis.json`, `step_response.png`, `verdicts.log`, `caveats.txt`, `res_watch.log`, `isaac.log`, `interfaces.log`, `commander.log`. Heavy: `~/flight_logs/sim/<run>/` ← bag dir + `drone_<n>_sysid<s>_<basename>.ulg` ×3.

Design (key lines the implementer writes exactly):
- Header: `set -o pipefail` (no `-e`: every failure is an explicit `|| fail`). Constants: `TOOLS=$REPO/tools`, `STEPS_PER_AXIS=${STEPS_PER_AXIS:-3}`, `ISAAC_KIT_ARGS=${ISAAC_KIT_ARGS:-}` appended to `ISAAC_CMD` (see Task 8), `NOISE='^(bash: cannot set terminal|bash: no job control|Sourcing|groups: cannot find name)'`.
- `say()` → `echo "[$(date '+%T %Z')] $*" | tee -a "$OUT/run.log"`. `note()` appends to `commands.sh`. `rx()`/`ix()` filter `$NOISE`.
- `phase_begin <phase> [files…]`: if `run.log` already contains `== phase <phase> ==` → `say "== phase <phase> (re-run) =="` and `echo "# == phase <phase> (re-run) ==" >> commands.sh`, else without "(re-run)"; then `: > "$OUT/<file>"` for each listed file (per-phase outputs are truncated, `run.log`/`commands.sh`/`verdicts.log`/`caveats.txt` never).
- `up`: `phase_begin up run_meta.txt`; after the containers are up write `run_meta.txt`: `head=$(git -C "$REPO" rev-parse HEAD)`, `head_short=$(git -C "$REPO" rev-parse --short HEAD)`, `dirty_tools=$(git -C "$REPO" status --porcelain -- tools | wc -l)`, `started=$(date -Is)`, `tz=$(date +%Z)`, `run=$RUN`, `steps_per_axis=$STEPS_PER_AXIS`; `note` every command.
- `isaac`: as now (`PYTHONUNBUFFERED=1` is already in `ISAAC_CMD`); after Ready ×3: `grep -c Starling2MaxConfig` < 3 → `say "WARN: Starling2MaxConfig printed $n times (report will mark it UNVERIFIED)"` (not a fail).
- `interfaces`: `phase_begin interfaces odom_hz.txt topics_of_interest.txt clock_check.txt`; launch; readiness per namespace:
  ```bash
  mavros_connected() { rx "timeout 10 ros2 topic echo --once /drone_$1/interface/mavros/state" | grep -q '^connected: true'; }
  for N in 1 2 3; do el=0; until mavros_connected "$N"; do sleep 3; el=$((el+13)); [ "$el" -ge 120 ] && fail "drone_$N MAVROS never reported connected: true"; done; say "drone_$N MAVROS connected (after ~${el}s)"; done
  ```
  then the odometry wait per drone (the old `ifgates` body, same 90 s budget, each attempt logged with `say`), `odom_hz.txt`, `topics_of_interest.txt`, and `rx 'ros2 topic info /clock >/dev/null 2>&1; echo clock_rc=$?' | grep clock_rc > "$OUT/clock_check.txt"` (rc 0 = `/clock` exists, rc 1 = unknown topic — verified 2026-10-28). Segfault count → `say "WARN: …"` only. `ifgates` stays callable as a phase alias but is NOT needed by `all`.
- `fly`: `phase_begin fly test_stdout.log armed_post.txt landing_evidence.txt status_post.json`; `docker cp "$TOOLS/sim_hover_step_test.sh" "$R:/tmp/"; docker cp "$TOOLS/analyze_step.py" "$R:/tmp/"` (no sed, no `/clock` probe); run `timeout 720 docker exec "$R" bash -ic "STEPS_PER_AXIS=$STEPS_PER_AXIS /tmp/sim_hover_step_test.sh drone_1"`; armed check:
  ```bash
  for N in 1 2 3; do rx "timeout 10 ros2 topic echo --once /drone_$N/interface/mavros/state" | grep -oE '^armed: (true|false)' | sed "s/^/drone_$N /"; done > "$OUT/armed_post.txt"
  ```
  (`--field armed` prints Python-style `False` — that is why the old `^(true|false)$` grep captured nothing; the full message prints `armed: false`.)
- `copy_ulogs()` (shared): list `/tmp/tmp*/log/*/*.ulg` newer than `isaac.log.start`, sysid via pyulog, `docker cp "$I:$f" "$HEAVY/drone_$((sid-1))_sysid${sid}_$(basename "$f")"` each; when all three sysids 2 3 4 are present in `$HEAVY` → `touch "$OUT/ulogs_copied.ok"`; else `say "WARN: ulogs copied: <list>"`.
- `collect`: `phase_begin collect analyze.txt ulog_list.txt ulog_sysid_map.txt params_ulog.txt px4_arm_times.txt`; echo-trace analysis for `ascent` and every `/tmp/step_{x,z}_<k>.txt` (k = 1..STEPS_PER_AXIS; `analyze_step.py` delta = `+1.0` for odd k, `−1.0` for even k; trace files `docker cp`'d to `$OUT`); `copy_ulogs`; params from the sysid-2 ulog as now (drop the meaningless `ulog thrust_setpoint` line); `docker cp "$TOOLS/hover_step_timescale.py" "$I:/tmp/"` and `docker exec "$I" python3 /tmp/hover_step_timescale.py "$U1" > "$OUT/px4_arm_times.txt"` (`U1` = sysid-2 ulog path inside the container; `|| say "WARN: no PX4 arm times"`).
- `down`: `phase_begin down bag_evidence.txt bag_path.txt`; stop the commander → wait → `bag_evidence.txt`; bag copy guard:
  ```bash
  b=$(docker exec "$R" bash -c 'ls -d /root/AirStack/robot/ros_ws/bags/hover_step_* 2>/dev/null | tail -1')
  [ -n "$b" ] || fail "no hover_step bag in the robot container"
  echo "$b" > "$OUT/bag_path.txt"
  if docker cp "$R:$b" "$HEAVY/" && [ -f "$HEAVY/$(basename "$b")/metadata.yaml" ]; then
    say "bag copied to $HEAVY/$(basename "$b")"
    docker cp "$TOOLS/hover_step_bag.py" "$R:/tmp/"
    rx "python3 /tmp/hover_step_bag.py $b drone_1 /tmp/drone_1" | grep '^{' | tee -a "$OUT/run.log" || fail "bag reader failed"
    for f in odom cmd state; do docker cp "$R:/tmp/drone_1_$f.csv" "$OUT/drone_1_$f.csv" || fail "csv copy $f"; done
    docker exec "$R" rm -rf "$b"
  else say "WARN: bag copy failed — bag LEFT in the container at $b"; echo "bag copy failed; bag left at $b" >> "$OUT/caveats.txt"; fi
  ```
  stop the interfaces; `[ -f "$OUT/ulogs_copied.ok" ] || copy_ulogs` (BEFORE Isaac stops); stop Isaac; orphan px4 kill; isaac.log + evidence; watch stop; log-size guard as now. `note` every docker command.
- `analyse` (host): `phase_begin analyse bag_analysis.json`; `python3 "$TOOLS/hover_step_analysis.py" --odom "$OUT/drone_1_odom.csv" --cmd "$OUT/drone_1_cmd.csv" --state "$OUT/drone_1_state.csv" --px4-arm-times "$OUT/px4_arm_times.txt" --step-delta 1.0 --drone drone_1 -o "$OUT/bag_analysis.json" || fail "analysis"`; `python3 "$TOOLS/hover_step_plot.py" "$OUT" || say "WARN: plot failed"`; both `note`d; print the `steps` block with a python one-liner into run.log.
- `report`: `note "python3 $TOOLS/hover_step_report.py $OUT --heavy $HEAVY"`; run it, `tee -a run.log`; the report's exit code is the phase's (0/2 both let `all` finish; 1 = `fail "report: FAIL"` after printing).
- `status`: containers; `ready` count; per-drone `mavros_connected` → `drone_N connected: yes/no`; commander up count; `/svg/bag_recorder/status` first 200 chars; watch alive; `[ -f "$OUT/verdicts.log" ] && tail -1 "$OUT/verdicts.log" || echo "no verdicts yet"`; `grep head_short "$OUT/run_meta.txt" 2>/dev/null || echo "no run_meta (up not run)"`.
- `all`: `for p in precheck up watch isaac interfaces commander params fly collect down analyse report`.
- Usage line lists every phase including `analyse`, `status`, `ifgates`; unknown phase → exit 2.

- [ ] **Step 1: Add the failing tests to `tools/tests/test_scripts_syntax.py`**

```python
    def test_wrapper_parses_and_usage(self):
        p = TOOLS / "sim_hover_step_run.sh"
        self.assertEqual(subprocess.run(["bash", "-n", str(p)]).returncode, 0)
        r = subprocess.run(["bash", str(p), "no_such_phase"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        for ph in ("analyse", "status", "report", "collect", "down"): self.assertIn(ph, r.stdout + r.stderr)
        src = p.read_text()
        self.assertNotIn("sed -i", src)                       # no in-container patching
        self.assertNotIn("isaac-sim/tools", src)              # copies come from tools/
        self.assertIn("set -o pipefail", src); self.assertNotIn("set -eo pipefail", src)
        for needle in ("ulogs_copied.ok", "run_meta.txt", "clock_check.txt", "hover_step_timescale.py", "hover_step_analysis.py", "connected: true", "^armed: (true|false)"):
            self.assertIn(needle, src, needle)

    def test_shellcheck_if_present(self):
        import shutil
        if not shutil.which("shellcheck"): self.skipTest("shellcheck not installed")
        r = subprocess.run(["shellcheck", "-S", "warning", str(TOOLS / "sim_hover_step_run.sh"), str(TOOLS / "sim_hover_step_test.sh")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)
```

- [ ] **Step 2: Run** — `python3 -m unittest tools.tests.test_scripts_syntax -v` → Expected: `test_wrapper_parses_and_usage` FAILS on `analyse` missing from usage.

- [ ] **Step 3: Rewrite the wrapper** per the design above (keep the working parts of `precheck`, `watch`, `commander`, `params` verbatim apart from `phase_begin`/`note`).

- [ ] **Step 4: Run the tests and the live dry checks** (containers are up, nothing else running)

```bash
cd /home/jeremychia/AirStack-starling-max2 && python3 -m unittest discover -s tools/tests -v
tools/sim_hover_step_run.sh status plan_dryrun
tools/sim_hover_step_run.sh precheck plan_dryrun
grep -c "== phase precheck" docs/record/plan_dryrun/run.log; tools/sim_hover_step_run.sh precheck plan_dryrun >/dev/null; grep -c "(re-run)" docs/record/plan_dryrun/run.log
rm -rf docs/record/plan_dryrun ~/flight_logs/sim/plan_dryrun
```
Expected: all tests OK; `status` prints the two containers `Up`, `ready: 0`, `drone_1 connected: no` ×3, `watch not running`, `no verdicts yet`; `precheck` ends with the GPU line; the two greps print `1` then `1` (second run marked re-run).

- [ ] **Step 5: Commit**

```bash
cd /home/jeremychia/AirStack-starling-max2
git add tools/sim_hover_step_run.sh tools/tests/test_scripts_syntax.py
git commit -m "tools: sim_hover_step_run.sh — per-namespace MAVROS readiness, odometry wait inside interfaces, guarded bag copy, ulogs copied before Isaac stops (collect + down), PX4 arm times, host analyse phase, run_meta/commands/verdict provenance, phase re-run markers, no sed patch, status shows what is up"
```

---

### Task 8: Try to pin Isaac to real time (read-only investigation + opt-in hook)

**Files:**
- Create: `tools/README.md` section "Time scale (why PX4 time ≠ wall clock)" — the note (Task 9 writes the rest of the README; if Task 9 runs first, append the section)
- Modify: nothing under `AirStack/`

**Interfaces:**
- Consumes: `ISAAC_KIT_ARGS` hook from Task 7 (`ISAAC_CMD` gets `$ISAAC_KIT_ARGS` appended after `--ext-folder …`).
- Produces: a written note with the three facts below filled in; default behaviour of the wrapper unchanged (hook empty).

- [ ] **Step 1: Read the stepping configuration (record the exact lines in the note)**

Run:
```bash
cd /home/jeremychia/AirStack-starling-max2/AirStack/simulation/isaac-sim
sed -n 84,96p extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/params.py
sed -n 326,345p launch_scripts/svg_multi_drone_single_domain.py
grep -n "enable_lockstep" extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/logic/backends/px4_mavlink_backend.py | head -3
docker exec isaac-sim grep -n "sys.argv\|extra_args\|unknown" /isaac-sim/exts/isaacsim.simulation_app/isaacsim/simulation_app/simulation_app.py | head
```
Expected (already seen 2026-10-28): `PX4_PHYSICS_HZ` 250 / `PX4_RENDERING_HZ` 60 from env with defaults; the run loop is `while simulation_app.is_running(): world.step(render=True)` with no sleep or rate limiter; `enable_lockstep` defaults `True` (PX4 advances one 4 ms step per physics step, so PX4 time = physics steps × 4 ms regardless of wall time). The fourth command tells whether `SimulationApp` forwards unknown `--/…` argv to Kit — write down what it prints.

- [ ] **Step 2: One-shot experiment with the wrapper's hook (only if step 1 shows argv forwarding; skip otherwise and say so in the note)**

```bash
cd /home/jeremychia/AirStack-starling-max2
ISAAC_KIT_ARGS='--/app/runLoops/main/rateLimitEnabled=true --/app/runLoops/main/rateLimitFrequency=60' tools/sim_hover_step_run.sh up ratelimit_probe
ISAAC_KIT_ARGS='--/app/runLoops/main/rateLimitEnabled=true --/app/runLoops/main/rateLimitFrequency=60' tools/sim_hover_step_run.sh isaac ratelimit_probe
sleep 60
docker exec isaac-sim bash -c 'grep -m1 -n "rateLimit" /tmp/hover_step/isaac.log; for f in /tmp/tmp*/log/*/*.ulg; do ls -l "$f"; done'
tools/sim_hover_step_run.sh down ratelimit_probe
rm -rf docs/record/ratelimit_probe ~/flight_logs/sim/ratelimit_probe
```
Measure: ulog growth over 60 s wall with `pyulog` `vehicle_status` last timestamp (≈ 60 s → pinned; ≈ 80 s → not pinned). Record the number.

- [ ] **Step 3: Write the note** into `tools/README.md` under `## Time scale (why PX4 time ≠ wall clock)`: lockstep + unthrottled `world.step` loop ⇒ PX4 ran 1.336× wall in #17; the analysis measures the scale per run from the drone_1 ulog arm/disarm vs the bag's MAVROS state and gates in vehicle time; the `ISAAC_KIT_ARGS` experiment result (pinned / not pinned / not forwarded) and the recommendation (keep measuring; pinning is optional and must never be done by editing CMU files). No commit of anything under `AirStack/`.

- [ ] **Step 4: Commit**

```bash
cd /home/jeremychia/AirStack-starling-max2
git add tools/README.md
git commit -m "tools/README: time-scale note — lockstep + unthrottled loop, per-run measurement, ISAAC_KIT_ARGS rate-limit experiment result"
```

---

### Task 9: Docs — tools/README.md, RUNBOOK pointer, MILESTONES #17 note + Next-up, CONFIG.md, §4 row, #17 record caveat

**Files:**
- Create: `tools/README.md` (full page; Task 8's section is one of its headings)
- Modify: `docs/RUNBOOK.md` (insert after the A0 block, before `### A1 — Isaac Sim tab`), `docs/MILESTONES.md` (ledger row #17 line 218, Next-up row 1 line 281, §4 row line 387), `docs/CONFIG.md:116-124`, `docs/record/sim_hover_step_run1_record.md` (Caveats list)
- Test: `tools/docs_check/check_docs.sh` exit 0

- [ ] **Step 1: `tools/README.md`** — sections, in order: **What is here** (table: `sim_terminals.sh`/`sim_tab.sh` — the four-tab sim session; `make_milestones_doc.py` — legacy docx; `docs_check/` — doc checker; then the five hover-step tools: `sim_hover_step_run.sh` orchestrator with the phase list, `sim_hover_step_test.sh` flight script (ours; `STEPS_PER_AXIS`), `analyze_step.py` echo-trace analyser (ledger #3's method, info only), `hover_step_bag.py` container CSV dumper, `hover_step_analysis.py` host analysis, `hover_step_timescale.py` PX4 arm times, `hover_step_report.py` record writer, `hover_step_plot.py` figure); **Prerequisites** (containers up via `AirStack/airstack.sh up`; every container command runs through `bash -ic`; `pyulog` in the Isaac container's system python3; host `python3` with numpy + matplotlib; `localisation/scripts/sim_resources_watch.sh`; GPU; no real-drone bridge on the laptop — iron rule 9 line); **Run it** (`tools/sim_hover_step_run.sh all [run_name]`, then `status`, then where the record lands); **Where things go** (`docs/record/<run>/` small text, `~/flight_logs/sim/<run>/` bag + three ulogs `drone_<n>_sysid<s>_<basename>.ulg`, record at `docs/record/<run>_record.md`); **Time scale** (Task 8's section); **Tests** (`python3 -m unittest discover -s tools/tests -v`; fixtures = ledger #17 artefacts); **Gotchas** (ulog temp dirs vanish when Isaac exits; all three ulogs share a basename; `ros2 topic echo --field` prints `False`/`True`; `/clock` not visible in the robot container; Isaac's exit orphans PX4 SITL processes).

- [ ] **Step 2: RUNBOOK §A pointer** — insert after the A0 paragraph (before `### A1 — Isaac Sim tab: spawn the sim drones`):

```
> **No-terminal variant for the hover + 1 m step acceptance only:** `tools/sim_hover_step_run.sh all` runs A1–A4 for that one test from the laptop and writes `docs/record/<run>_record.md` — see [tools/README.md](../tools/README.md). Everything else in §A is done in the tabs.
```

- [ ] **Step 3: MILESTONES edits (exact text)**

(a) Row **#17** (line 218): replace `**PASS** on every M1 gate.` with `**PASS** on the hover + step row of M1 (sim path, n = 1).` and append to the Result cell, before its closing `|`: ` *Four-expert review 2026-10-28: every timing above is wall clock while PX4 ran 1.336× faster (vehicle time: x settle 2.49 s, z 2.16 s — still < 3 s); the driver's own verdict was FAIL ×3 (Starling2MaxConfig 0, z settle 3.05 s by the echo method, armed check unreadable) and the PASS came from a manual bag re-analysis; `all` aborted at `interfaces` and the later phases were hand-run (manual recovery); drone_1's ulog was lost. Tooling fixed per [superpowers/plans/2026-10-28-hover-step-tools-fix.md](superpowers/plans/2026-10-28-hover-step-tools-fix.md); clean re-run = #18.*`

(b) Next-up row 1 (line 281) becomes:
```
| 1 | **M1 re-run of #17 as ledger #18 ⏳:** `tools/sim_hover_step_run.sh all` end to end with zero manual steps on the fixed tooling (vehicle-time gates, 3 steps per axis, drone_1 ulog kept, record at the commit that ran) — plan [superpowers/plans/2026-10-28-hover-step-tools-fix.md](superpowers/plans/2026-10-28-hover-step-tools-fix.md) | container | — |
```

(c) §4 row (line 387) "How" cell: replace ``; `docker cp` `simulation/isaac-sim/tools/{sim_hover_step_test.sh,analyze_step.py}` into the robot container, run with `bash -ic` `` with ``; `tools/sim_hover_step_run.sh all` (copies OUR `tools/sim_hover_step_test.sh` + `tools/analyze_step.py` into the robot container; gates in PX4 vehicle time from the rosbag) ``.

- [ ] **Step 4: CONFIG.md "Validation so far" (lines 116–124) — replace the whole paragraph with:**

```
**Validation so far** ([MILESTONES.md](MILESTONES.md) §3c): ledger #1–#4 passed 2026-10-19 on the
*old* asset / gains / speed limits (#3 steps: x overshoot 0.002 m, settled 2.75 s; z 0.001 m,
0.75 s · #4 antipodal crossing min distance 1.02 m at 0.6 / 1.2 m/s). 2026-10-21 fresh launch on the
current asset = ledger #13: asset complete, no PhysX warnings, 2.0 m/s commanded / ~1.7 flown,
landing DISARM accepted first try ×3. 2026-10-28 hover + 1 m steps on the current asset / **sim-only**
gains / speed limits = ledger #17 ([record](record/sim_hover_step_run1_record.md)): hover thrust setpoint
0.153, x step overshoot 0.054 m, z 0.001 m, no ringing, disarm first try ×3 — passed the hover + step row
of M1 with wall-clock timings (x 1.86 s / z 1.62 s; PX4 ran 1.336× wall, so 2.49 s / 2.16 s in vehicle
time) and manual recovery of the driver; the clean re-run with vehicle-time gates is ledger #18 ⏳ (Next up
row 1). ⏳ The CBF-crossing re-run (#4) is still pending — the ordered list lives only in
[MILESTONES.md](MILESTONES.md) §3c "Next up".
```

- [ ] **Step 5: #17 record caveat** — append two bullets to the Caveats list in `docs/record/sim_hover_step_run1_record.md`:
```
- Four-expert review 2026-10-28: the driver's own verdict at 15:45:58 was FAIL on three gates (`Starling2MaxConfig x3: 0`, `z step settle 3.05 s` by the echo method, `post-flight armed` unreadable); the PASS above comes from the rosbag re-analysis done afterwards. `all` aborted at `interfaces`; `commander` → `report` were run by hand; the bag and ulogs were recovered manually; drone_1's ulog was lost; this record was generated at `76cd405`, a commit made after the flight.
- Every timing in this record is wall clock. PX4 ran 1.336× faster (lockstep; drone_2 ulog arm→disarm 100.87 s vs 75.5 s wall): x settle 1.86 s → 2.49 s, z 1.62 s → 2.16 s in vehicle time (both still < 3 s). The re-run (#18) gates in vehicle time.
```

- [ ] **Step 6: Check and commit**

Run: `cd /home/jeremychia/AirStack-starling-max2 && tools/docs_check/check_docs.sh` → Expected: exit 0, `0 FAIL`.
```bash
git add tools/README.md docs/RUNBOOK.md docs/MILESTONES.md docs/CONFIG.md docs/record/sim_hover_step_run1_record.md
git commit -m "docs: tools/README (hover-step tool set, prerequisites, time-scale caveat); RUNBOOK §A pointer; MILESTONES #17 review note + Next-up row 1 = re-run as #18; CONFIG validation text; #17 record caveats"
```

---

### Task 10: The acceptance run — `all` from a cold start, ledger #18, record (session owner runs it)

**Files:**
- Produced: `docs/record/sim_hover_step_run2/` (small artefacts), `docs/record/sim_hover_step_run2_record.md`, `~/flight_logs/sim/sim_hover_step_run2/` (bag + three ulogs, never committed)
- Modify: `docs/MILESTONES.md` (ledger row #18 appended after #17; Next-up row 1 struck through; §3 M1 cell and §4 row updated; "Validation record" line), `docs/CONFIG.md` (the "#18 ⏳" clause → "#18 passed (record)")

**Interfaces:**
- Consumes: everything from Tasks 1–9 at one commit; `git -C ~/AirStack-starling-max2 status --porcelain tools/` must be empty before `up` (the record cites `run_meta.txt`'s `head` and flags `dirty_tools`).

Acceptance criterion: `tools/sim_hover_step_run.sh all sim_hover_step_run2` runs from containers-up to the record with **zero manual intervention**; every row of the record is `PASS`, `UNVERIFIED` or `info` (no `FAIL`) and the overall verdict is `PASS` or `INCOMPLETE`; the record's Files section lists the bag and `drone_1_sysid2_*.ulg`, `drone_2_sysid3_*.ulg`, `drone_3_sysid4_*.ulg`. If any phase `fail`s or any row is FAIL, that is a finding: fix the tool under `tools/` (with a test), commit, and re-run `all` with a new run name — do not hand-run phases and call it #18.

- [ ] **Step 1: Cold-start command sequence (laptop; drone battery OUT, no `./mocap.sh`, laptop on Ethernet or sitting at it — Isaac start has crashed the WiFi firmware before)**

```bash
cd ~/AirStack-starling-max2 && git status --porcelain tools/ docs/ && git log -1 --oneline     # Expected: no porcelain lines
python3 -m unittest discover -s tools/tests                                                      # Expected: OK
cd ~/AirStack-starling-max2/AirStack && ./airstack.sh up && cd ..                                  # containers (idempotent)
tools/sim_hover_step_run.sh status sim_hover_step_run2                                            # Expected: both Up, ready 0, connected no x3
tools/sim_hover_step_run.sh all sim_hover_step_run2 2>&1 | tee ~/flight_logs/sim_hover_step_run2_console.log
```
`all` = precheck → up (writes `run_meta.txt`) → watch (`sim_resources_watch.sh`) → isaac (Ready ×3) → interfaces (MAVROS `connected: true` ×3, odometry ×3, `/clock` check) → commander (`scenario=goal`, `record_bag:=true`) → params → fly (takeoff → start → 10 thrust samples → x ±1 m ×3 → z ±1 m ×3 → land; about 5 min) → collect (echo traces, three ulogs per sysid, PX4 params, `px4_arm_times.txt`) → down (commander stops → bag closes → guarded copy → CSVs → interfaces stop → ulog re-copy if needed → Isaac stops) → analyse (host) → report. Expected console tail: `PASS: …/docs/record/sim_hover_step_run2_record.md` (or `INCOMPLETE:` with the UNVERIFIED rows listed) and `== phase report ==` in `run.log` with no `FAIL (` line anywhere.

- [ ] **Step 2: Verify the artefacts the record cites**

```bash
cd ~/AirStack-starling-max2
grep -E "FAIL|UNVERIFIED" docs/record/sim_hover_step_run2_record.md || echo "no FAIL/UNVERIFIED rows"
ls -l ~/flight_logs/sim/sim_hover_step_run2/                       # Expected: hover_step_<stamp>/ + drone_1_sysid2_*.ulg drone_2_sysid3_*.ulg drone_3_sysid4_*.ulg
cat docs/record/sim_hover_step_run2/px4_arm_times.txt              # Expected: sysid=2
cat docs/record/sim_hover_step_run2/verdicts.log                   # Expected: exactly one line
grep -c "(re-run)" docs/record/sim_hover_step_run2/run.log         # Expected: 0
diff <(grep head= docs/record/sim_hover_step_run2/run_meta.txt | cut -d= -f2) <(git rev-parse HEAD) && echo "record at the commit that ran"
find docs/record/sim_hover_step_run2 -size +1000k                   # Expected: nothing
```

- [ ] **Step 3: Shutdown**

```bash
cd ~/AirStack-starling-max2/AirStack && ./airstack.sh down          # optional — `all` already stopped Isaac/interfaces/commander and left the containers up
```

- [ ] **Step 4: Ledger row #18 (MILESTONES §3c, after row 17) — placeholders `⟨…⟩` are measured numbers from the record only**

```
| 18 | **M1 re-run of #17 with the fixed tooling: Starling hover + 1 m steps, 3 per axis (±1 m alternating), gated in PX4 vehicle time** — `tools/sim_hover_step_run.sh all sim_hover_step_run2`, zero manual steps, `cbf_sim.yaml scenario:=goal`, `record_bag:=true` | Isaac launch log; PX4 ulog header (pyulog); MAVROS `target_attitude` thrust samples; rosbag → `tools/hover_step_analysis.py` (commanded axis, goal-referenced, time scale from drone_1's ulog arm/disarm vs MAVROS state); `tools/hover_step_report.py` fail-closed; record [docs/record/sim_hover_step_run2_record.md](record/sim_hover_step_run2_record.md), artefacts `docs/record/sim_hover_step_run2/`, bag + 3 ulogs (sysid 2/3/4 = drone_1/2/3) in `~/flight_logs/sim/sim_hover_step_run2/` | `Starling2MaxConfig` ×⟨n⟩, `SYS_AUTOSTART` 10090 ×3, `Ready for takeoff` ×3; ulog `MC_PITCHRATE_P` 0.032 / `LNDMC_ROT_MAX` 300 / `MPC_XY_VEL_MAX` 20 / `MPC_THR_HOVER` 0.165; hover thrust setpoint **⟨median⟩** (#17: 0.153, real 0.165); time scale **⟨scale⟩** PX4 s per wall s; odometry ⟨hz⟩ Hz; x steps (3): overshoot max ⟨m⟩ m, settle ±0.1 m vs goal max **⟨s⟩ s** vehicle [⟨s⟩ s wall], median ⟨s⟩ s, ±0.05 m median ⟨s⟩ s, steady-state error max ⟨m⟩ m, velocity lag ⟨s⟩ s / gain ⟨g⟩ / residual ⟨mps⟩ m/s; z steps (3): ⟨m⟩ m / **⟨s⟩ s** [⟨s⟩ wall] / ±0.05 ⟨s⟩ s / lag ⟨s⟩ s gain ⟨g⟩; 0 band re-entries on every step; takeoff climb ⟨m⟩ m / ⟨s⟩ s; `landed, disarmed (attempt 1)` ×3 (ACK log) and MAVROS `armed: false` ×3; ⟨n⟩ WiFi alerts; driver verdict history: one generation, `⟨verdict⟩`. **⟨PASS / INCOMPLETE⟩** on the hover + step row of M1 (sim path, n = 3 per axis, one launch). Thresholds 0.15 m / 3 s / 0 re-entries are MILESTONES §4's (bracketed by the Iris #2 reading, not derived). Sim-only (iron rule 9) | ⟨YYYY-MM-DD⟩ |
```
Also: strike Next-up row 1 (`~~…~~ ✅ done ⟨date⟩ → ledger #18`); §3 M1 cell `#17 (…passed)` → `#17/#18 (hover + steps, fixed tooling, vehicle time)`; §4 row: add `✅ ⟨date⟩ re-run #18 ([record](record/sim_hover_step_run2_record.md))`; "Validation record" line → `ledger #1–#13, #17–#18`; CONFIG.md `#18 ⏳ (Next up row 1)` → `#18 passed ⟨date⟩ ([record](record/sim_hover_step_run2_record.md))`. If the verdict is INCOMPLETE, write INCOMPLETE and name the UNVERIFIED rows in the ledger cell instead of PASS.

- [ ] **Step 5: Check and commit**

```bash
cd ~/AirStack-starling-max2 && tools/docs_check/check_docs.sh      # Expected: 0 FAIL
git add docs/record/sim_hover_step_run2 docs/record/sim_hover_step_run2_record.md docs/MILESTONES.md docs/CONFIG.md
git commit -m "S5 / NEAR-786: ledger #18 — hover + 1 m steps re-run end to end with the fixed tooling, vehicle-time gates, 3 steps per axis; record + artefacts"
```
Then tell the user the verdict, the vehicle-time numbers, and that the mirror clone needs `git -C ~/Documents/GitHub/AirStack-starling-max2 pull ~/AirStack-starling-max2 main` before they push.

---

## Spec coverage (review §3/§5 → task)

| Review item | Task |
|---|---|
| C1 undisclosed re-adjudication → verdict history + record/ledger wording | T5 (`verdicts.log` row), T9 (#17 note, record caveats), T10 |
| C2 wall vs PX4 time | T3 (`time_scale`, `vehicle_time`), T4, T5 (gated in vehicle time), T8 (pin attempt) |
| C3 committed scripts ≠ what ran; commands.sh gaps; `all` aborted; bag copy; ulog names | T7 (`run_meta.txt`, `note` everywhere, readiness, guarded copy, per-sysid ulogs in collect + down), T10 |
| C4/C5/M5/M8/M9 real-drone items | out of scope for tooling; carried in the review's "Next tests" list, not in this plan |
| M1 PASS for missing evidence / info rows | T5 |
| M2 commander-dominated settle → goal-referenced + velocity tracking | T3, T5 |
| M3 n = 1, loosened ringing, threshold provenance | T1 (3 steps/axis), T3 (`summarise_steps` max/median), T5 (0 re-entries, provenance line) |
| M4 #3 comparison invalid | T5 (`vs #3` rows are `info`) |
| M6 bag detector bugs (axis, quiet timer, offsets, no tests) | T3 |
| M7 wrapper readiness / rm / thrust parser / ulog loss | T7, T5 |
| M10 echo method | T5 (info only) |
| MINOR `/clock` rc, sed | T7 (`ros2 topic info` rc, no sed) |
| MINOR armed_post garbage | T7 (full-message grep), T5 (strict parser) |
| MINOR timezones / `today` / `head` | T7 (`run_meta.txt`), T5 |
| MINOR "CMU's test tool" authorship | T1 (moved to `tools/`), T9 |
| MINOR idempotency (append-only files) | T7 (`phase_begin` truncation + re-run markers) |
| MINOR `ifgates` missing from usage / needed by hand | T7 |
| MINOR record omits lost drone_1 ulog | T9 (#17 caveat), T5 (ulog gate) |
| MINOR hover thrust 10 samples | unchanged (10 samples kept; parser now strict) — documented in tools/README Gotchas |
| MINOR takeoff 3-D move, vz 10–15 % high | info rows only; noted in README |
| §5 docs corrections | T9 |
| §5 tooling fixes list | T3, T5, T7 |
