# Sim keyboard teleop in BODY frame — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In the sim, the keyboard flies the drone relative to its nose (Drive mode, BODY), `F` flips to Room mode (WORLD), a heading guard zeroes a bad command, and nothing under `AirStack/` changes except one new `_ours` yaml.

**Architecture:** A relay node of ours (`tools/teleop/teleop_frame.py`, pure maths in `tools/teleop/frame.py`) sits between CMU's `safe_teleop` (output diverted to `…/teleop_command_stick` by `teleop_single_ours.yaml`) and the commander's unchanged `…/teleop_command`. The keyboard window (`tools/teleop/key_teleop.py` + `keymap.py`) gains the new words, Space, F and the mode lines; `tools/sim.sh` gains `relay` and starts it from `keys`; a new sim test `teleop_frame` proves "forward follows the nose".

**Tech Stack:** Python 3 (rclpy, Tk) inside the robot container; bash (`tools/sim.sh`, `tools/lib/stack.sh`); `unittest` under `tools/tests/` (pre-commit hook runs `python3 -m unittest discover tools/tests`); the sim-test harness of `docs/TEST_STANDARD.md` (five files, `metrics_core`, `report.py`).

**Spec:** `docs/superpowers/specs/2026-11-03-sim-teleop-body-frame-design.md`

## Global Constraints

- Never edit anything under `AirStack/` except creating `AirStack/robot/ros_ws/src/svg_ground_control/config/teleop_single_ours.yaml` (the recorded `_ours` precedent). `git diff --stat AirStack/` at the end shows only that file. No patch.
- Every behaviour commit (paths matched by `tools/docs_check/changes.py is-behaviour`) carries a `docs/record/CHANGES.md` row and a commit body starting `Change: CHG-nnnn` with the fields What, Scope, Why, Could affect, Watch for, Verified by, Revert (docs/CODING_STANDARD.md). One CHG id per commit; take the next free id from the table each time (CHG-0026 is free at plan time). Never `--amend`, never `--no-verify`.
- Commit in the live clone `~/AirStack-starling-max2` on `main`; stage by name; never stage `QGroundControl-x86_64.AppImage`, `starling max2 voxl setup.txt`, `docs/record/sim_hover_step_run4/`, `.superpowers/`. Never push. After the last task: `git -C ~/Documents/GitHub/AirStack-starling-max2 pull ~/AirStack-starling-max2 main`.
- Never start Isaac, the stack or any container from a task. Sim runs are the owner's.
- Words on screen: `Drive mode` / `Room mode` only; `BODY` / `WORLD` are parameter values and doc brackets. No "CMU config" wording on screen.
- Signs stay CMU's: ↑ = +forward, ← = +left, A = +yaw (counter-clockwise), W = +climb. Keys removed: Shift/Ctrl, Q/E.
- Rotation (BODY → WORLD), ψ = ENU yaw: `vx_w = vx·cos ψ − vy·sin ψ`, `vy_w = vx·sin ψ + vy·cos ψ`; `vz` and yaw rate pass through.
- Guard: stale when the latest heading is older than `heading_stale_s` 0.2; jump when |Δψ| (wrapped to ±π) between consecutive samples > `heading_jump_rad` 0.5; tripped → horizontal zero, vz and yaw rate pass; re-arm only when the input is centred (|v_xy| < 0.05 m/s) AND the heading is fresh and steady again. WORLD never trips.
- Mode flip (`F`): applied only when the input is centred (|v_xy| < 0.05); until then `pending`.
- Status line format (relay → window), `std_msgs/String`, 5 Hz: `frame=<body|world> pending=<body|world|none> heading_deg=<float|nan> heading_age_s=<float|nan> guard=<ok|stale|jump> input=<ok|none>`; heading_deg uses the operator convention of `swarm_commander.yaw_to_heading` (0 = +X, clockwise positive).
- Docs style: short plain sentences; no semicolon chains; each change explained physically. Run `python3 tools/docs_check/check_docs.py` (0 FAIL) and `python3 tools/docs_check/changes.py audit` (PASS) before every commit that touches docs or CHANGES.md.

## Review Focus

1. The relay receives a `TwistStamped` whose quaternion-free odometry has a zero (unfilled) orientation (norm² < 0.5): heading must read NaN and the guard must say `stale`, never a 0° heading → Task 1 `test_unfilled_quaternion_is_no_heading`.
2. `F` pressed twice quickly while a key is held: the pending mode must end up where the operator expects (second press cancels the first), with no flip while keys are down → Task 1 `test_two_f_presses_while_held_cancel`.
3. Odometry at 10–12 Hz (sim lag): the stale guard must not trip on a normal sample gap of 0.1 s → Task 1 `test_normal_sample_gap_does_not_trip`.
4. Someone runs `tools/sim.sh keys` during a real-drone session (no `isaac-sim` container): refusal before any container call → Task 4 `test_keys_and_relay_refuse_without_the_isaac_container`.
5. Old yaml (`teleop_single.yaml`) with the relay running: the window must show grey Room-mode lines and no `F`, never Drive mode → Task 3 `test_header_lines_for_every_status` (`input=none` case) and Task 2 `test_input_silence_is_reported`.

---

### Task 1: Pure frame logic — `tools/teleop/frame.py`

**Files:**
- Create: `tools/teleop/frame.py`
- Test: `tools/tests/test_teleop_frame.py`

**Interfaces:**
- Produces:
  - `rotate_body_to_world(vx: float, vy: float, yaw: float) -> tuple[float, float]`
  - `yaw_from_quat(x: float, y: float, z: float, w: float) -> float` (ENU yaw, `math.nan` when x²+y²+z²+w² < 0.5)
  - `heading_deg_from_yaw(yaw: float) -> float` (0 = +X, clockwise positive, `[0, 360)`, nan passes through)
  - `wrap_pi(a: float) -> float`
  - Constants: `MODES = ("body", "world")`, `CENTRED_MPS = 0.05`, `STALE_S = 0.2`, `JUMP_RAD = 0.5`, `INPUT_SILENT_S = 1.0`
  - `class FrameState(mode="body", stale_s=STALE_S, jump_rad=JUMP_RAD, input_silent_s=INPUT_SILENT_S)` with
    - `update_heading(yaw: float, t: float) -> None` (t = monotonic seconds; a nan yaw counts as no sample)
    - `request_mode(mode: str) -> None` (unknown mode → `ValueError`; requesting the current mode cancels a pending flip)
    - `command(vx: float, vy: float, vz: float, yaw_rate: float, t: float) -> tuple[float, float, float, float]` (world-frame output; records input time)
    - `status(t: float) -> dict` with keys `frame, pending, heading_deg, heading_age_s, guard, input` (values as in Global Constraints)
    - `status_line(t: float) -> str` (the exact `key=value` line)
  - All of this is pure Python with `math` only (no numpy, no ROS, no Tk).

- [ ] **Step 1: Write the failing tests**

```python
# tools/tests/test_teleop_frame.py
import math, pathlib, sys, unittest
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "teleop"))
import frame as F

class Rotation(unittest.TestCase):
    def test_four_headings(self):
        for yaw, want in ((0.0, (1.0, 0.0)), (math.pi/2, (0.0, 1.0)), (math.pi, (-1.0, 0.0)), (-math.pi/2, (0.0, -1.0))):
            vx, vy = F.rotate_body_to_world(1.0, 0.0, yaw)
            self.assertAlmostEqual(vx, want[0], 6, yaw); self.assertAlmostEqual(vy, want[1], 6, yaw)
    def test_left_key_at_heading_180_slides_to_room_right(self):
        vx, vy = F.rotate_body_to_world(0.0, 1.0, math.pi)
        self.assertAlmostEqual(vx, 0.0, 6); self.assertAlmostEqual(vy, -1.0, 6)
    def test_unfilled_quaternion_is_no_heading(self):
        self.assertTrue(math.isnan(F.yaw_from_quat(0, 0, 0, 0)))
        self.assertAlmostEqual(F.yaw_from_quat(0, 0, math.sin(0.25), math.cos(0.25)), 0.5, 6)
    def test_heading_deg_is_operator_convention(self):
        self.assertAlmostEqual(F.heading_deg_from_yaw(0.0), 0.0, 6)
        self.assertAlmostEqual(F.heading_deg_from_yaw(math.pi/2), 270.0, 6)   # nose on +Y (ENU) = 270 clockwise from +X
        self.assertTrue(math.isnan(F.heading_deg_from_yaw(math.nan)))

class Modes(unittest.TestCase):
    def fresh(self, mode="body"):
        s = F.FrameState(mode=mode); s.update_heading(math.pi, 10.0); return s
    def test_body_rotates_world_passes_through(self):
        s = self.fresh()
        vx, vy, vz, yr = s.command(1.0, 0.0, 0.3, 0.7, 10.05)
        self.assertAlmostEqual(vx, -1.0, 6); self.assertAlmostEqual(vy, 0.0, 6); self.assertEqual((vz, yr), (0.3, 0.7))
        w = self.fresh("world"); self.assertEqual(w.command(1.0, 0.0, 0.3, 0.7, 10.05), (1.0, 0.0, 0.3, 0.7))
    def test_flip_waits_until_centred(self):
        s = self.fresh(); s.command(1.0, 0.0, 0, 0, 10.05); s.request_mode("world")
        self.assertEqual(s.status(10.06)["pending"], "world")
        vx, _, _, _ = s.command(1.0, 0.0, 0, 0, 10.1); self.assertAlmostEqual(vx, -1.0, 6)      # still body
        s.command(0.0, 0.0, 0, 0, 10.15)                                                         # centred: flip applies
        self.assertEqual(s.status(10.16)["frame"], "world"); self.assertEqual(s.status(10.16)["pending"], "none")
        self.assertEqual(s.command(1.0, 0.0, 0, 0, 10.2)[0], 1.0)
    def test_two_f_presses_while_held_cancel(self):
        s = self.fresh(); s.command(1.0, 0, 0, 0, 10.05); s.request_mode("world"); s.request_mode("body")
        self.assertEqual(s.status(10.06)["pending"], "none"); s.command(0, 0, 0, 0, 10.1)
        self.assertEqual(s.status(10.11)["frame"], "body")
    def test_unknown_mode_rejected(self):
        with self.assertRaises(ValueError): F.FrameState().request_mode("nose")

class Guard(unittest.TestCase):
    def test_stale_heading_zeroes_horizontal_keeps_vz_and_yaw(self):
        s = F.FrameState(); s.update_heading(0.0, 10.0)
        self.assertEqual(s.command(1.0, 0.5, 0.3, 0.7, 10.5), (0.0, 0.0, 0.3, 0.7)); self.assertEqual(s.status(10.5)["guard"], "stale")
    def test_normal_sample_gap_does_not_trip(self):
        s = F.FrameState(); s.update_heading(0.0, 10.0); s.update_heading(0.03, 10.1)
        self.assertEqual(s.command(1.0, 0.0, 0, 0, 10.15)[0], 1.0 * math.cos(0.03)); self.assertEqual(s.status(10.15)["guard"], "ok")
    def test_jump_trips_and_rearms_only_when_centred_and_steady(self):
        s = F.FrameState(); s.update_heading(0.0, 10.0); s.update_heading(3.1, 10.05)
        self.assertEqual(s.command(1.0, 0, 0, 0, 10.06)[:2], (0.0, 0.0)); self.assertEqual(s.status(10.06)["guard"], "jump")
        s.update_heading(3.1, 10.1); s.update_heading(3.1, 10.15)
        self.assertEqual(s.command(1.0, 0, 0, 0, 10.16)[:2], (0.0, 0.0))                  # steady but not centred: still tripped
        s.command(0.0, 0.0, 0, 0, 10.2); s.update_heading(3.1, 10.25); s.command(0.0, 0.0, 0, 0, 10.26)
        self.assertEqual(s.status(10.27)["guard"], "ok"); self.assertNotEqual(s.command(1.0, 0, 0, 0, 10.3)[0], 0.0)
    def test_wraparound_is_not_a_jump(self):
        s = F.FrameState(); s.update_heading(math.pi - 0.01, 10.0); s.update_heading(-math.pi + 0.01, 10.05)
        self.assertEqual(s.status(10.06)["guard"], "ok")
    def test_world_mode_never_trips(self):
        s = F.FrameState(mode="world"); s.update_heading(0.0, 10.0); s.update_heading(3.1, 10.05)
        self.assertEqual(s.command(1.0, 0, 0, 0, 12.0), (1.0, 0.0, 0.0, 0.0)); self.assertEqual(s.status(12.0)["guard"], "ok")

class Status(unittest.TestCase):
    def test_status_line_format_and_input_silence(self):
        s = F.FrameState(); s.update_heading(0.0, 10.0); s.command(0, 0, 0, 0, 10.0)
        self.assertEqual(s.status_line(10.1), "frame=body pending=none heading_deg=0.0 heading_age_s=0.10 guard=ok input=ok")
        self.assertEqual(s.status(11.5)["input"], "none")
        n = F.FrameState(); self.assertEqual(n.status(0.0)["input"], "none"); self.assertTrue(math.isnan(n.status(0.0)["heading_deg"]))
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest tools.tests.test_teleop_frame -v`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'frame'`

- [ ] **Step 3: Implement `tools/teleop/frame.py`**

Module docstring: what it is (sim-only relay maths, iron rule 9), the rotation formula, the guard rule, the status line. `FrameState` keeps `mode`, `pending` (None or a mode), `yaw`, `yaw_t`, `prev_yaw`, `tripped` (None | "stale" | "jump"), `last_input_t`, `last_input_centred: bool`. `command()` order: record input time and centredness → apply a pending flip if centred → in body mode evaluate stale/jump (jump is latched in `update_heading` when |wrap_pi(yaw − prev_yaw)| > jump_rad; it stays latched until centred and fresh and the last two samples steady) → rotate or zero. `status()` reads guard without side effects. `status_line()` formats `heading_deg` with `%.1f` (nan → `nan`) and `heading_age_s` with `%.2f`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest tools.tests.test_teleop_frame -v`
Expected: all PASS

- [ ] **Step 5: Run the full suite and commit**

Run: `python3 -m unittest discover tools/tests 2>&1 | tail -3`
Expected: `OK` (count ≥ 630 + the new tests)

```bash
git add tools/teleop/frame.py tools/tests/test_teleop_frame.py
git commit -m "HTX-R1/S5 NEAR-789: frame.py — BODY/WORLD rotation, pending flip, heading guard (pure logic)" -m "Change: CHG-00NN
What: new tools/teleop/frame.py (rotate_body_to_world, yaw_from_quat, FrameState with pending flip, stale/jump guard, status line) + tools/tests/test_teleop_frame.py.
Scope: sim-only (tools/teleop). Not wired to ROS yet; nothing flies differently until Task 2.
Why: owner decision 2026-11-03 — sim keyboard flies relative to the nose; spec docs/superpowers/specs/2026-11-03-sim-teleop-body-frame-design.md.
Could affect: nothing at runtime yet.
Watch for: n/a until the relay node (next CHG) uses it.
Verified by: test_teleop_frame (all failed first), full suite.
Revert: git revert <sha>."
```

Add the CHANGES.md row (`| CHG-00NN | 2026-11-03 | sim-only | tools/teleop/frame.py: BODY/WORLD rotation, pending flip, heading guard — pure logic for the relay | this |`) in the same commit; `python3 tools/docs_check/changes.py audit` → PASS.

---

### Task 2: Relay node — `tools/teleop/teleop_frame.py`

**Files:**
- Create: `tools/teleop/teleop_frame.py`
- Test: `tools/tests/test_teleop_frame_node.py`

**Interfaces:**
- Consumes: `frame.FrameState`, `frame.yaw_from_quat`, `frame.MODES` (Task 1).
- Produces: node name `teleop_frame`; parameters `drone` (str, default `drone_1`), `stick_frame` (str, `body`), `heading_stale_s` (0.2), `heading_jump_rad` (0.5), `input_topic_template` (`/svg/{name}/teleop_command_stick`), `output_topic_template` (`/svg/{name}/teleop_command`), `odometry_topic_template` (`/{name}/odometry_conversion/odometry`), `status_topic` (`/teleop_frame/status`), `status_rate_hz` (5.0). Pure helper `topics_for(drone: str, params: dict) -> dict(input, output, odometry)`. `stick_frame` settable live through the standard parameter service (the window's `F` uses `/teleop_frame/set_parameters`); a value outside `MODES` is rejected by the parameter callback. CLI: `python3 teleop_frame.py [--drone drone_1] [--stick-frame body|world]` (CLI values seed the parameters). Output message: copy the input header stamp and frame_id, rotated linear, angular.z unchanged.

- [ ] **Step 1: Write the failing tests** — source-level and stub-rclpy, the pattern of `tools/tests/test_keymap.py::WindowSource` (read the file) and the yaw_step stub (`tools/tests/test_yaw_step_fly.py` if present, else build a minimal `sys.modules` stub for `rclpy`, `rclpy.node`, `rclpy.signals`, `geometry_msgs.msg`, `nav_msgs.msg`, `std_msgs.msg`, `rcl_interfaces.msg`):

```python
class Source(unittest.TestCase):          # tools/tests/test_teleop_frame_node.py
    def test_parameters_and_topics_named_as_in_the_spec(self): ...   # all nine parameter names + defaults appear in the source
    def test_status_published_at_5_hz_and_input_silence_is_reported(self): ...   # "status_rate_hz" timer; INPUT_SILENT_S or input_silent_s used
    def test_stick_frame_rejects_unknown_values(self): ...           # parameter callback returns SetParametersResult(successful=False) for "nose"
    def test_rclpy_signal_handlers_are_ours(self): ...               # SignalHandlerOptions.NO, zeros published on exit (same rule as key_teleop)
    def test_topics_for(self):
        t = TF.topics_for("drone_2", {"input_topic_template": "/svg/{name}/teleop_command_stick", "output_topic_template": "/svg/{name}/teleop_command", "odometry_topic_template": "/{name}/odometry_conversion/odometry"})
        self.assertEqual(t, {"input": "/svg/drone_2/teleop_command_stick", "output": "/svg/drone_2/teleop_command", "odometry": "/drone_2/odometry_conversion/odometry"})
class Relay(unittest.TestCase):           # with the stub: build the node, feed one odometry (yaw π) and one input (1,0,0.3,0.7), assert the published output is (-1,0,0.3,0.7) and the status line says frame=body guard=ok input=ok
    def test_body_output_is_rotated(self): ...
    def test_input_silence_is_reported(self): ...                    # no input for > 1 s (monotonic patched) → status input=none
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m unittest tools.tests.test_teleop_frame_node -v`
Expected: ERROR `No module named 'teleop_frame'`

- [ ] **Step 3: Implement `tools/teleop/teleop_frame.py`**

Thin wiring: `main(argv=None) -> int`; `rclpy.init(signal_handler_options=SignalHandlerOptions.NO)`; own SIGINT/SIGTERM flag; one `FrameState`; odometry callback → `update_heading(yaw_from_quat(...), monotonic)`; input callback → `command(...)` → publish; 5 Hz timer → publish `status_line`; `add_on_set_parameters_callback` for `stick_frame` (validates, calls `request_mode`), `heading_stale_s`, `heading_jump_rad`; on exit publish one zero `TwistStamped` on the output (the commander's 0.5 s timeout does the rest). Log once per episode: `teleop_frame: HEADING STALE`, `HEADING JUMP`, `input silent`, `mode -> world (pending until centred)`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest tools.tests.test_teleop_frame_node -v`
Expected: all PASS

- [ ] **Step 5: Full suite, CHANGES row, commit**

Run: `python3 -m unittest discover tools/tests 2>&1 | tail -3` → `OK`; `python3 tools/docs_check/changes.py audit` → PASS.

```bash
git add tools/teleop/teleop_frame.py tools/tests/test_teleop_frame_node.py docs/record/CHANGES.md
git commit -m "HTX-R1/S5 NEAR-789: teleop_frame relay node — safe_teleop stick → BODY/WORLD → commander" -m "Change: CHG-00NN
What: new tools/teleop/teleop_frame.py: subscribes /svg/{drone}/teleop_command_stick + odometry, publishes /svg/{drone}/teleop_command rotated by the heading (stick_frame body|world, live-settable), /teleop_frame/status at 5 Hz.
Scope: sim-only. Only runs when started (tools/sim.sh relay/keys, next CHG); with CMU's yaml it has no input and changes nothing.
Why: spec §5.1–5.3.
Could affect: the Basestation Teleop card now shows the relay's output when the _ours yaml is used; NEAR-789/790 sessions before 2026-11-03 flew WORLD frame.
Watch for: 'HEADING JUMP'/'HEADING STALE' in the relay log; a 0.5 s hold after the relay exits (commander timeout); heading sign (clockwise-positive on screen).
Verified by: test_teleop_frame_node (stub rclpy; failed first), full suite. pending: tools/sim.sh test teleop_frame (Task 6).
Revert: git revert <sha>."
```

---

### Task 3: Keyboard window — words, Space, F, mode lines

**Files:**
- Modify: `tools/teleop/keymap.py` (docstring, `KEYS`, `WORDS`, `KeyState.press/status`, new `HELP` text lives in key_teleop)
- Modify: `tools/teleop/key_teleop.py` (`HELP`, `read_safe_teleop` adds `max_speed_mps`, header labels, status subscription, `F` → parameter set)
- Test: `tools/tests/test_keymap.py` (modify existing cases; add new)

**Interfaces:**
- Consumes: the status line format (Global Constraints) parsed by `keymap.parse_status(line: str) -> dict`.
- Produces in `keymap.py`: `KEYS` without `shift_l/shift_r/control_l/control_r/q/e`; `"space"` handled in `press()` as `all_up()` + a `stop_at` timestamp so `status()` shows `STOP` for 1 s; `"f"` sets `self.flip_requested = True` (the window consumes it and calls the parameter service; `KeyState` never changes the frame itself); `WORDS` values: `"pitch: forward"`, `"pitch: back"`, `"roll: slide left"`, `"roll: slide right"`, `"turn (yaw) left"`, `"turn (yaw) right"`, `"climb"`, `"descend"`; `KeyState.status(t, max_speed_mps=None)` appends ` = x.x m/s` when the speed is known; `parse_status(line)`; `header_lines(status: dict | None, relay_seen: bool) -> tuple[str, str, str]` returning (bold line, sentence, colour hex) for the six cases of spec §5.4: drive, room, pending, heading lost, relay missing, old yaml (`input=none` → grey room lines, footer without F).
- Produces in `key_teleop.py`: `HELP` footer `A / D turn · W / S up / down · Space STOP · F → room mode` (or `→ drive mode`, or no F when `input=none`), rebuilt each tick; `read_safe_teleop` also returns `max_speed_mps`; a `std_msgs/String` subscription on `/teleop_frame/status` (last line + receive time); `F` → async `SetParameters` on `/teleop_frame/set_parameters` with `stick_frame` = the other mode (never blocks the tick; result logged); window title unchanged.

- [ ] **Step 1: Update and add the failing tests in `tools/tests/test_keymap.py`**

Change `test_mode2_layout_follows_the_stick_conventions` to drop the Shift/Ctrl/Q/E cases and add `test_aliases_are_gone` (pressing `Shift_L`, `Control_L`, `q`, `e` leaves every axis 0). Replace `test_alias_and_main_key_together_never_exceed_full_stick` with `test_two_keys_of_one_stick_never_exceed_full_stick` using `Up`+`Up` repeat. Add:

```python
    def test_space_releases_everything_and_reads_stop(self):
        s = K.KeyState("dragonrise_usb"); s.press("Up", 1.0); s.press("a", 1.0); s.press("space", 1.2)
        self.assertEqual(set(s.axes(1.25)), {0.0}); self.assertIn("STOP", s.status(1.25))
    def test_f_is_a_flip_request_not_a_stick(self):
        s = K.KeyState("dragonrise_usb"); s.press("f", 1.0)
        self.assertTrue(s.flip_requested); self.assertEqual(set(s.axes(1.05)), {0.0})
    def test_status_line_uses_the_new_words_and_speed(self):
        s = K.KeyState("dragonrise_usb", scale=0.5); s.press("Up", 1.0); s.press("Left", 1.0)
        self.assertEqual(s.status(1.05, max_speed_mps=2.0), "pitch: forward, roll: slide left  ·  50 % of top speed = 1.0 m/s")
    def test_parse_status(self):
        d = K.parse_status("frame=body pending=none heading_deg=123.0 heading_age_s=0.05 guard=ok input=ok")
        self.assertEqual(d["frame"], "body"); self.assertEqual(d["heading_deg"], 123.0); self.assertEqual(d["guard"], "ok")
    def test_header_lines_for_every_status(self):
        drive = K.header_lines(K.parse_status("frame=body pending=none heading_deg=1 heading_age_s=0.1 guard=ok input=ok"), True)
        self.assertEqual(drive[0], "Drive mode — ↑ is always where the nose points"); self.assertTrue(drive[1].startswith("Like driving a car"))
        room = K.header_lines(K.parse_status("frame=world pending=none heading_deg=1 heading_age_s=0.1 guard=ok input=ok"), True)
        self.assertEqual(room[0], "Room mode — ↑ is always the far wall")
        pend = K.header_lines(K.parse_status("frame=body pending=world heading_deg=1 heading_age_s=0.1 guard=ok input=ok"), True)
        self.assertEqual(pend[0], "Switching to room mode — let go of the keys first")
        lost = K.header_lines(K.parse_status("frame=body pending=none heading_deg=nan heading_age_s=nan guard=stale input=ok"), True)
        self.assertEqual(lost[0], "Heading lost — let go of the keys")
        self.assertEqual(K.header_lines(None, False)[0], "Keys not reaching the drone — run tools/sim.sh keys again")
        old = K.header_lines(K.parse_status("frame=body pending=none heading_deg=1 heading_age_s=0.1 guard=ok input=none"), True)
        self.assertEqual(old[0], "Room mode — ↑ is always the far wall"); self.assertEqual(old[2], K.GREY)
        for lines in (drive, room, pend, lost, old):
            self.assertNotIn("BODY", lines[0] + lines[1]); self.assertNotIn("WORLD", lines[0] + lines[1]); self.assertNotIn("CMU", lines[0] + lines[1])
```

In `WindowSource`/`WindowReviewFixes` add: `test_help_footer_has_space_and_f_and_no_aliases` (source has `Space STOP`, `F → room mode`, and no `Shift`, `Ctrl`, `Q / E`), `test_reads_max_speed_and_status_topic` (source has `max_speed_mps` in `req.names`, `/teleop_frame/status`, `/teleop_frame/set_parameters`), `test_f_never_blocks_the_tick` (source calls `call_async` for the flip, never `spin_until_future_complete` inside `tick`).

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m unittest tools.tests.test_keymap -v`
Expected: the new tests FAIL (`AttributeError: flip_requested`, `parse_status` missing, footer assertions); the altered layout test fails on the alias keys still mapping.

- [ ] **Step 3: Implement in `keymap.py` and `key_teleop.py`** (signatures in Interfaces; `GREY = "#6b7280"`, `GREEN = "#0a7a3c"`, `BLUE = "#1d4ed8"`, `AMBER = "#b45309"`, `RED = "#B00020"`; the six sentence pairs copied verbatim from spec §5.4). In `key_teleop.py` the header is two `tk.Label`s above the existing status label; `tick()` sets them from `header_lines(...)` each cycle and consumes `state.flip_requested`.

- [ ] **Step 4: Run to verify they pass**

Run: `python3 -m unittest tools.tests.test_keymap -v`
Expected: all PASS

- [ ] **Step 5: Docs touched by the key change, full suite, CHANGES row, commit**

Update `docs/TELEOP.md` §3b table to the spec §5.4 table (keys, "On screen" column), drop the alias row, add one short "Drive mode / Room mode" paragraph (3–4 sentences, physical explanation, `BODY`/`WORLD` in brackets once), and one sentence in §1 after "It is room-fixed, not nose-relative": "The sim keyboard is the exception: it flies in Drive mode (BODY) through our relay, §3b." Run `python3 tools/docs_check/check_docs.py` → 0 FAIL.

```bash
git add tools/teleop/keymap.py tools/teleop/key_teleop.py tools/tests/test_keymap.py docs/TELEOP.md docs/record/CHANGES.md
git commit -m "HTX-R1/S5 NEAR-789: keyboard window — Drive/Room mode lines, Space STOP, F flip, new words, aliases removed" -m "Change: CHG-00NN
What: keymap.py KEYS/WORDS/status/parse_status/header_lines; key_teleop.py HELP footer, max_speed read, /teleop_frame/status subscription, F → set_parameters stick_frame; TELEOP.md §3b.
Scope: sim-only keyboard window.
Why: spec §5.4 (owner-chosen wording 2026-11-03).
Could affect: anyone used to Shift/Ctrl/Q/E (now dead keys); the status line text that the 2026-10-30 records quote.
Watch for: a window showing 'Keys not reaching the drone' while the relay runs (status topic name mismatch); the m/s figure when safe_teleop's max_speed_mps changes live.
Verified by: test_keymap (new cases failed first), full suite.
Revert: git revert <sha>."
```

---

### Task 4: `tools/sim.sh relay`, `keys` starts it, Isaac-container guard

**Files:**
- Modify: `tools/sim.sh` (`cmd_keys`, new `cmd_relay`, usage text, dispatcher)
- Modify: `tools/README.md` (`sim.sh` row + `teleop/` row)
- Test: `tools/tests/test_sim_sh.py` (class `Keys`, new class `Relay`)

**Interfaces:**
- Produces: `tools/sim.sh relay [body|world] [--drone N]` → copies `tools/teleop/frame.py` and `tools/teleop/teleop_frame.py` to `$R:/tmp/svg_keys/`, starts `python3 /tmp/svg_keys/teleop_frame.py --drone drone_N --stick-frame <mode>` detached (`docker exec -d`, log `/tmp/svg_keys/teleop_frame.log`), prints `relay: running (pid …)` or, if one already runs, `relay: already running` (exit 0). `tools/sim.sh relay stop` stops it. `keys` calls `cmd_relay` first (default `body`), remembers whether it started one, and stops only what it started in its `trap`. Both refuse with exit 2 and `error: … needs the sim (isaac-sim container not running) — this is sim-only` **before any other container call** when `docker ps --format '{{.Names}}' | grep -qx isaac-sim` fails. `sim.sh test` also copies `frame.py` and `teleop_frame.py` into `$S` (the loop at "copy-in").

- [ ] **Step 1: Write the failing tests** in `tools/tests/test_sim_sh.py`, following the existing `Keys` class (fake `docker` script on PATH that records calls; `SIM_KEYS_NO_TTY_OK=1`):

```python
class Relay(unittest.TestCase):
    def test_usage_lists_relay(self): self.assertIn("relay", run().stdout)
    def test_relay_copies_both_files_and_starts_the_node(self): ...   # fake docker answers `ps` with "isaac-sim"; calls contain cp of frame.py and teleop_frame.py, and "teleop_frame.py --drone drone_1 --stick-frame body"
    def test_relay_world_and_drone_2(self): ...                       # "--drone drone_2 --stick-frame world"
    def test_relay_rejects_bad_mode(self): ...                        # "nose" → rc 2, no docker call
    def test_keys_starts_the_relay_first_and_stops_only_its_own(self): ...   # order: relay cp/start before key_teleop; cleanup line has both pkill when it started the relay
    def test_keys_and_relay_refuse_without_the_isaac_container(self): ...   # fake docker `ps` prints nothing → rc 2, message contains "sim-only", and no `cp`/`exec -d` recorded
class TestFlow(...):  # extend test_test_flow_wires_the_pieces: "tools/teleop/frame.py" and "tools/teleop/teleop_frame.py" in the copy-in list
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m unittest tools.tests.test_sim_sh -k Relay -k Keys -v`
Expected: FAIL (`relay` unknown → usage printed, rc 2; keys has no guard)

- [ ] **Step 3: Implement in `tools/sim.sh`** — `sim_only_guard()` helper used by `cmd_keys` and `cmd_relay`; `cmd_relay` with the argument check pattern of `cmd_keys` (regex, `usage_line`); dispatcher `relay) cmd_relay "$@"; exit $? ;;`; copy-in list extended. Update `tools/README.md` rows and the `keys` echo line (`arrows move, W/S up/down, A/D turn, Space STOP, F drive/room mode, 1/2/3 = speed`).

- [ ] **Step 4: Run to verify they pass**

Run: `python3 -m unittest tools.tests.test_sim_sh -v 2>&1 | tail -3`
Expected: `OK`

- [ ] **Step 5: Full suite, docs check, CHANGES row, commit**

```bash
git add tools/sim.sh tools/README.md tools/tests/test_sim_sh.py docs/record/CHANGES.md
git commit -m "HTX-R1/S5 NEAR-789: sim.sh relay + keys starts it; keys/relay refuse without the isaac-sim container" -m "Change: CHG-00NN
What: cmd_relay (start/stop the teleop_frame node in the robot container), cmd_keys starts it first and stops only what it started, sim_only_guard (isaac-sim container must be up), test copy-in gains frame.py + teleop_frame.py.
Scope: sim-only tooling. The real session never has the isaac-sim container, so keys/relay refuse there.
Why: spec §5.5 and §5.8 items 3–4.
Could affect: a keys window started while Isaac is down (now refused); two relays (second start reports 'already running').
Watch for: 'relay: already running' from an orphan after a crash (tools/sim.sh relay stop); the guard message in a real-drone session.
Verified by: test_sim_sh Relay/Keys (failed first), full suite.
Revert: git revert <sha>."
```

---

### Task 5: `teleop_single_ours.yaml`, Cockpit text, config docs

**Files:**
- Create: `AirStack/robot/ros_ws/src/svg_ground_control/config/teleop_single_ours.yaml`
- Modify: `tools/sim_tab.sh` (cockpit block), `docs/CONFIG.md` ("Which config for what" table), `docs/RUNBOOK.md` and `docs/TELEOP.md` (every `teleop_single.yaml` command line used for the keyboard session → `_ours`), `docs/record/CHANGES.md`
- Test: `tools/tests/test_configs.py` (new, small)

**Interfaces:**
- Produces: the yaml = `teleop_single.yaml` byte-for-byte except (a) a header comment (ours, 2026-11-03, why, which topic is diverted) and (b) in the `safe_teleop:` block the line `teleop_topic_template: "/svg/{name}/teleop_command_stick"   # ours: the teleop_frame relay feeds the commander's /svg/{name}/teleop_command`. The commander block is untouched (it keeps the default template).

- [ ] **Step 1: Write the failing test**

```python
# tools/tests/test_configs.py
class TeleopOurs(unittest.TestCase):
    def test_ours_diverts_safe_teleop_only(self):
        base = yaml_load(CFG / "teleop_single.yaml"); ours = yaml_load(CFG / "teleop_single_ours.yaml")
        self.assertEqual(ours["swarm_commander"], base["swarm_commander"])
        self.assertEqual(ours["safe_teleop"]["ros__parameters"]["teleop_topic_template"], "/svg/{name}/teleop_command_stick")
        b = dict(base["safe_teleop"]["ros__parameters"]); o = dict(ours["safe_teleop"]["ros__parameters"]); o.pop("teleop_topic_template", None); b.pop("teleop_topic_template", None)
        self.assertEqual(o, b)
    def test_cockpit_and_docs_name_the_ours_yaml_for_the_keyboard_session(self):
        for f in ("tools/sim_tab.sh", "docs/TELEOP.md"):
            self.assertIn("teleop_single_ours.yaml", (ROOT / f).read_text(), f)
```

(Use `yaml` if importable, else a minimal parse: the test may skip with a clear message when PyYAML is absent — check `python3 -c "import yaml"` first; it is available on the laptop.)

- [ ] **Step 2: Run to verify it fails** — `python3 -m unittest tools.tests.test_configs -v` → FileNotFoundError.

- [ ] **Step 3: Create the yaml; update `tools/sim_tab.sh` cockpit block** (add the two `CFG=…teleop_single_ours.yaml` launch lines for Cockpit and Commander with `use_foxglove_studio:=true`, plus `tools/sim.sh keys` on the laptop and `tools/sim.sh relay` for pad users); `docs/CONFIG.md` row: `| Keyboard teleop in sim (S5) | **`teleop_single_ours.yaml`** (ours, 2026-11-03) | as `teleop_single.yaml`; safe_teleop publishes on `…/teleop_command_stick`, the `teleop_frame` relay feeds the commander (Drive/Room mode, TELEOP.md §3b) |`; TELEOP.md §3b/§4 and RUNBOOK sim-session lines that name `teleop_single.yaml` for keyboard flying → `_ours` (leave gamepad-only and yaw_step mentions as they are). Note in TELEOP.md that the package needs no rebuild for a `.yaml` edit but a NEW file needs `bws && sws` once (RUNBOOK rule, `setup.py` globs `config/*.yaml`) — put that sentence next to the launch lines.

- [ ] **Step 4: Run to verify it passes** — `python3 -m unittest tools.tests.test_configs -v` → OK; `python3 tools/docs_check/check_docs.py` → 0 FAIL.

- [ ] **Step 5: Commit**

```bash
git add AirStack/robot/ros_ws/src/svg_ground_control/config/teleop_single_ours.yaml tools/sim_tab.sh tools/tests/test_configs.py docs/CONFIG.md docs/TELEOP.md docs/RUNBOOK.md docs/record/CHANGES.md
git commit -m "HTX-R1/S5 NEAR-789: teleop_single_ours.yaml diverts safe_teleop to the relay; cockpit + docs name it" -m "Change: CHG-00NN
What: new _ours yaml (safe_teleop teleop_topic_template → /svg/{name}/teleop_command_stick, commander untouched); sim_tab.sh cockpit lines; CONFIG/TELEOP/RUNBOOK name it for the keyboard session.
Scope: sim-only config (the real session uses teleop_real_ours.yaml, untouched). The only file added under AirStack/.
Why: spec §5.2 — if the relay is down the commander hears nothing and holds, and the Basestation card hides instead of lying.
Could affect: a session launched with _ours but no relay (drone holds, card hidden); the first launch needs bws && sws once (new file).
Watch for: 'STICKS PARKED'/hidden Teleop card with the relay running = template mismatch between yaml and relay.
Verified by: test_configs (failed first), docs check 0 FAIL, full suite.
Revert: git revert <sha>."
```

---

### Task 6: Sim test `teleop_frame` — "forward follows the nose"

**Files:**
- Create: `tools/sim_tests/teleop_frame/{test.env, fly.sh, metrics.py, gates.py, plots.json, layout.json}` (copy `_template/`, model `yaw_step/`)
- Modify: `tools/sim.sh` only if `cmd_test` needs nothing new (it already copies `frame.py`/`teleop_frame.py` after Task 4)
- Test: `tools/tests/test_teleop_frame_gates.py`

**Interfaces:**
- Consumes: relay CLI (Task 2), `metrics_core.heading_deg`, `M.Frame.pos`, `report.row/isaac_rows/landing_rows/evidence_rows/coverage_row`, the `yaw_step/fly.sh` rclpy publisher pattern (executor + stamps on stdout).
- Produces: `test.env`: `TITLE="one-drone teleop frame: a forward push follows the nose (Drive mode) and +X (Room mode)"`, `ISSUE=NEAR-789`, `MILESTONE=S5`, `CONFIG=teleop_single_ours.yaml`, `SCENARIO=hover`, `BAG_PREFIX=teleop_frame`, `NUM_ROBOTS=1`, `USE_STUDIO=false`, `DURATION_S=4` (settle after each yaw), `FLY_ARGS="0.25 2.0"` (push fraction, push seconds), `FLY_TIMEOUT_S=600`, `BASELINE="none (first run sets it)"`, SCOPE/PURPOSE/SIM_ONLY_LINE per the template. `fly.sh`: starts the relay (`python3 $HERE/teleop_frame.py --drone drone_1 --stick-frame body &`, waits for `/teleop_frame/status`), takeoff → start → for heading in 0 90 180 270: yaw at 1.0 rad/s to the target (closed loop on odometry, ±3°), settle `DURATION_S`, publish on `/svg/drone_1/teleop_command_stick` `vx = frac·teleop_max_speed_mps` for `push_s`, release, wait 3 s, printing `[<unix s>] push <deg> onset|release heading=<deg>`; then `ros2 param set /teleop_frame stick_frame world`, one push at heading 180 printed as `[…] push world onset|release heading=180`; land; stop the relay in `trap` on every exit; zeros for 1 s on exit. `gates.py` rows per push from `metrics.csv` (positions, heading): `move direction within 20° of the nose` (angle between the xy displacement onset→release and the nose heading at onset), `moved ≥ 0.15 m`, `parked within 0.30 m of the release point at release+3 s`; the world push: `within 20° of +X`; plus `stick_frame live value present` (from `test_stdout.log` line `relay: stick_frame=body`), `odometry rate ≥ 10 Hz` (`odom_hz.txt`; below → INCOMPLETE). `metrics.py` series: `heading_deg`, `x_m`, `y_m` (position of drone_1, tolerance 0.02), `xy_drift_m`, `speed_drone_1`, flags. `plots.json`: heading, xy position, speed.

- [ ] **Step 1: Write the failing gate tests** — `tools/tests/test_teleop_frame_gates.py`: build a synthetic `metrics.csv` + `test_stdout.log` in a temp dir (a push at heading 90 that moves 0.25 m along +Y → PASS rows; one that moves along +X → direction FAIL; missing `stick_frame` line → INCOMPLETE; `odom_hz.txt` 8 Hz → INCOMPLETE). Also the existing contract: `tools/sim.sh check` must pass for the new folder (run it in the test via the existing pattern in `test_sim_sh.py` if there is one; else call `python3 tools/live/make_layout.py tools/sim_tests/teleop_frame` and assert `layout.json` is committed and matches).

- [ ] **Step 2: Run to verify they fail** — `python3 -m unittest tools.tests.test_teleop_frame_gates -v` → ImportError / FileNotFoundError.

- [ ] **Step 3: Write the five files + `layout.json`** (`python3 tools/live/make_layout.py tools/sim_tests/teleop_frame`), `fly.sh --check` validates `FLY_ARGS` (fraction in (0, 1], seconds > 0).

- [ ] **Step 4: Verify** — `python3 -m unittest tools.tests.test_teleop_frame_gates -v` → OK; `tools/sim.sh check` → no failure for `teleop_frame`; `bash tools/sim_tests/teleop_frame/fly.sh --check 4 0.25 2.0` → `arguments ok`.

- [ ] **Step 5: Full suite, CHANGES row, commit**

```bash
git add tools/sim_tests/teleop_frame tools/tests/test_teleop_frame_gates.py docs/record/CHANGES.md
git commit -m "HTX-R1/S5 NEAR-789: teleop_frame sim test — a forward push follows the nose at 0/90/180/270, one Room-mode control push" -m "Change: CHG-00NN
What: new tools/sim_tests/teleop_frame (five files + layout): fly.sh starts the relay, yaws to four headings, pushes forward on the relay's input, one world-mode push; gates on direction (≤ 20°), distance (≥ 0.15 m), parking (≤ 0.30 m), live stick_frame, odometry rate.
Scope: sim-only test. No airframe, gain or config change.
Why: spec §5.6; done-when needs one PASS.
Could affect: nothing outside the test.
Watch for: direction error near 20° at 270° (heading wrap); odometry below 10 Hz (INCOMPLETE by design).
Verified by: test_teleop_frame_gates (failed first), sim.sh check, fly.sh --check, full suite. pending: first live run by the owner.
Revert: git revert <sha>."
```

---

### Task 7: Finish — handoff, mirror, Linear note

**Files:**
- Modify: `docs/plans/2026-11-03-linear-agent-teleop-frame.md` (create), `~/claude-handoff.md`
- No code.

- [ ] **Step 1:** `python3 -m unittest discover tools/tests 2>&1 | tail -3` → OK; `python3 tools/docs_check/check_docs.py` → 0 FAIL; `python3 tools/docs_check/changes.py audit` → PASS; `git diff --stat $(git log --format=%H -1 --before="2026-11-03 00:00" main) -- AirStack/` shows only `teleop_single_ours.yaml`.
- [ ] **Step 2:** Write `docs/plans/2026-11-03-linear-agent-teleop-frame.md` (nearlab workspace; create in S5: title `Sim keyboard teleop flies in Drive mode (BODY), F switches to Room mode, with the forward-follows-the-nose test`, Backlog, description from spec §1 + §5.6 gates; comment on NEAR-874: "The NUS velocity contract stays room-frame (WORLD). The sim keyboard's Drive mode is a relay in tools/teleop only and does not touch that path."). Commit (docs only).
- [ ] **Step 3:** `git -C ~/Documents/GitHub/AirStack-starling-max2 pull ~/AirStack-starling-max2 main`; update `~/claude-handoff.md` (Recent changes bullets, Open items: first `teleop_frame` run + hand-flown session with video pending).
