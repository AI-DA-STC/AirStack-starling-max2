# Foxglove teleop strip — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fly the sim drone from a teleop strip inside the cuVSLAM Foxglove window, beside a first-person view and a chase view, only while the strip is the clicked panel.

**Architecture:** A plain-JavaScript Foxglove extension of ours (`tools/teleop/foxglove/svg-teleop`) publishes the same `/joy` stream as the Tk window, so `safe_teleop`, the relay and the commander do not change. The cuVSLAM bridge alone gets Fast DDS initial peers, so one WebSocket carries the camera topics and the drone-side topics. Key tables and on-screen words are generated from `tools/teleop/keymap.py`, and fixtures generated from the same file prove the JavaScript agrees.

**Tech Stack:** Foxglove Studio 2.53.1 extension API (plain JS, no bundler, CMU's `svg-basestation` is the pattern), `foxglove_bridge` 3.2.6 on ROS 2 Jazzy, Fast DDS XML, bash, Python `unittest` (`python3 -m unittest discover tools/tests`, run by the pre-commit hook), Node 24 for `node test/smoke.js`.

**Spec:** `docs/superpowers/specs/2026-11-03-foxglove-teleop-panel-design.md`

## Global Constraints

- Nothing under `AirStack/` changes. `git diff --stat a6e5e87 HEAD -- AirStack/` stays empty. Sim only. The real session keeps the gamepad through `joy_node`.
- Every behaviour commit carries a `docs/record/CHANGES.md` row and a commit body starting `Change: CHG-nnnn` with What, Scope, Why, Could affect, Watch for, Verified by, Revert. One id per commit, next free id at commit time (CHG-0040 is free now). Never `--amend`, never `--no-verify`.
- Commit on `main` in `~/AirStack-starling-max2`, stage by name. Never stage `QGroundControl-x86_64.AppImage`, `starling max2 voxl setup.txt`, `docs/record/sim_hover_step_run4/`, `.superpowers/`. Never push. Before each commit: `python3 tools/docs_check/check_docs.py` 0 FAIL and `python3 tools/docs_check/changes.py audit` PASS.
- Implementers never start the stack, Isaac, Studio or `tools/sim.sh test|up|keys|relay`. Throwaway `docker run --rm --network none localisation-exploration:cu12 …` checks are allowed. Live checks belong to the owner.
- On screen: `Drive mode` / `Room mode` only. No BODY, WORLD or CMU in any visible string. No diagrams on the strip.
- **Flies only while clicked.** `armed` is an explicit boolean set only by `pointerdown` on the panel root. Refocusing the Studio window never re-arms it.
- **Disarm triggers:** `focusout` leaving the root, window `blur`, `visibilitychange` to hidden, drone change, panel cleanup. Disarm lets every key go and sends five zero `sensor_msgs/msg/Joy` messages synchronously, then the 20 Hz timer stops.
- Topic layout per spec §5.6, templates with `{name}`: `joyTopicTemplate` `/joy`, `statusTopicTemplate` `/teleop_frame/status`, `teleopNsTemplate` `/safe_teleop`, `relayNsTemplate` `/teleop_frame`; `drones` default `["drone_1"]`.
- Dead link: `/teleop_frame/status` silent for 2 s, or a publish or service failure, shows the red line. The strip shows `FLYING drone_N` only when armed, the status is fresh, and `frame` is valid with `input=ok`.
- Red relay line on the strip: `Keys not reaching the drone — start the relay: tools/sim.sh relay`. All other lines are verbatim from `keymap.py`.
- Peer profile on the bridge only: `FASTRTPS_DEFAULT_PROFILES_FILE=/exploration/docker/fastdds_bridge.xml`, set inside `foxglove_bridge_isaac.sh`. The cuVSLAM node, the recorder and Isaac keep `fastdds.xml`. Peers: `172.31.0.1`, ports 7660 to 7718, even numbers.
- Docs: short plain sentences, no semicolon chains.

**Plan rulings against the spec (read these):**
- Spec §5.2 lets the builder choose how the table loads. Studio loads one file, so the tables are a generated block inside `dist/extension.js`, between `// KEYMAP:BEGIN` and `// KEYMAP:END`.
- Spec §5.3 unadvertises on every disarm. This plan advertises when a drone is selected and unadvertises on drone change or cleanup, because a new publisher on each click waits for DDS discovery and would lose the first key presses. The spec's zero-message rule is unchanged.
- Spec §5.7's second PX4 marker is **not built here**. PX4 odometry and `cuvslam_odom` are separate TF trees with an unknown alignment, so a marker needs a transform nobody has measured. It goes to the Linear file as a follow-up.

## Review Focus

1. Key pressed, panel clicked away, key released elsewhere so `keyup` is lost: after clicking back the drone must not move → Task 4 `lost keyup does not stick after re-click`.
2. Alt-Tab away and back with the strip still focused: stays disarmed until clicked → Task 4 `refocusing the window does not re-arm`.
3. `publish` throws while armed (bridge gone): no uncaught error, timer survives, red line shows → Task 4 `publish failure shows the red line and keeps the panel alive`.
4. Relay stopped, strip clicked: must not read `FLYING` → Task 4 `no FLYING while the relay is silent`.
5. Tab key while armed moves focus out of the panel → Task 4 `focus leaving the root disarms and sends five zeros`.

---

### Task 1: Bridge reaches both networks

**Files:**
- Create: `localisation/docker/fastdds_bridge.xml`
- Modify: `localisation/scripts/foxglove_bridge_isaac.sh`, `localisation/scripts/slam_up.sh` (warn line), `tools/sim.sh` (`cmd_setup`/doctor section, ~L516-600)
- Test: `tools/tests/test_foxglove_bridge.py`, `tools/tests/test_sim_sh.py`

**Interfaces:**
- Produces: bridge on 8766 whose whitelists admit `/joy`, `/teleop_frame/status`, `/teleop_frame/set_parameters`, `/safe_teleop/get_parameters`, plus the `/drone_N/…` forms. Doctor line: `firewall: container → host OK` or `firewall: container → host BLOCKED — run: sudo ufw allow from 172.31.0.0/24`.

- [ ] **Step 1: Write the failing tests**

```python
# tools/tests/test_foxglove_bridge.py
class Profile(unittest.TestCase):
    def test_bridge_profile_lists_thirty_host_peers(self):
        ports = peers(ROOT / "localisation/docker/fastdds_bridge.xml")   # ElementTree: every initialPeersList locator
        self.assertEqual(ports, [("172.31.0.1", p) for p in range(7660, 7720, 2)])
    def test_bridge_profile_is_udp_without_builtin_transports(self): ...  # useBuiltinTransports false, UDPv4
    def test_plain_profile_has_no_peers(self):                            # the node, recorder and Isaac stay unpeered
        self.assertEqual(peers(ROOT / "localisation/docker/fastdds.xml"), [])
class Script(unittest.TestCase):
    def test_script_exports_the_bridge_profile_before_exec(self): ...     # export line precedes `exec ros2 run`
    def test_topic_whitelist_admits_both_worlds(self):
        rx = whitelist("topic_whitelist")                                 # parse the JSON list from the script
        for t in ("/joy", "/drone_2/joy", "/teleop_frame/status", "/drone_2/teleop_frame/status",
                  "/drone_1/cuvslam/debug_image", "/tf", "/clock"):
            self.assertTrue(any(re.search(r, t) for r in rx), t)
        self.assertFalse(any(re.search(r, "/svg/commander_status") for r in rx))
    def test_service_whitelist_admits_exactly_the_two_services(self): ...  # both name forms in, /swarm_commander/land out
```

In `test_sim_sh.py`: `test_doctor_reports_the_firewall_probe` with a fake docker for three cases: probe delivered (OK line), not delivered (BLOCKED line with the exact `sudo ufw` text), `isaac-sim` not running (`firewall: not checked (isaac-sim not running)`). Doctor stays read-only and its exit code does not change for the not-checked case.

- [ ] **Step 2: Run to verify they fail** — `python3 -m unittest tools.tests.test_foxglove_bridge -v` → FileNotFoundError on the new XML.

- [ ] **Step 3: Implement.** XML = `fastdds.xml` plus the `initialPeersList`. Script: `export FASTRTPS_DEFAULT_PROFILES_FILE=/exploration/docker/fastdds_bridge.xml`, topic whitelist as spec §5.8a, `-p service_whitelist:='[…]'`, `-p client_topic_whitelist:='["^(/drone_[0-9]+)?/joy$"]'`. Doctor probe: host binds a UDP socket on an ephemeral port, `docker exec isaac-sim python3 -c` sends one datagram to `172.31.0.1:<port>`, 3 s timeout. `slam_up.sh`: same probe through a helper, one warning line, never a refusal.

- [ ] **Step 4: Verify parameter names on the real binary**

Run: `docker run --rm --network none --entrypoint bash localisation-exploration:cu12 -c 'source /opt/ros/jazzy/setup.bash; timeout 8 ros2 run foxglove_bridge foxglove_bridge --ros-args -p port:=8799 & sleep 4; ros2 param list /foxglove_bridge'`
Expected: `service_whitelist` and `client_topic_whitelist` listed. If a name differs, use the real one and note it in the report.

- [ ] **Step 5: Run tests, full suite, commit** — subject `HTX-R1/S5 NEAR-789: cuVSLAM bridge reaches the drone side (initial peers, whitelists), doctor checks the firewall`. Could affect: the bridge also sees host-side `/tf` if anything publishes it there, and `results/foxglove_bridge.log`. Watch for: a duplicated or jumping `/tf` in the 3D panel, higher bridge CPU. Verified by: tests + spike numbers from spec §5.8; pending the owner's session.

---

### Task 2: Generated tables and fixtures from `keymap.py`

**Files:**
- Modify: `tools/teleop/keymap.py` (`export_tables() -> dict`, `--dump-json` under `if __name__ == "__main__"`)
- Create: `tools/teleop/foxglove/gen_keymap.py`, `tools/teleop/foxglove/svg-teleop/package.json`, `tools/teleop/foxglove/svg-teleop/dist/extension.js` (skeleton with the marked block), `tools/teleop/foxglove/svg-teleop/test/fixtures.json`
- Test: `tools/tests/test_svg_teleop_tables.py`

**Interfaces:**
- Produces: `export_tables()` keys `keys`, `words`, `scales`, `default_scale`, `deadzone`, `profiles`, `lines` (the header sentence pairs and colours), `footer`, `stop_shown_s`. `python3 tools/teleop/foxglove/gen_keymap.py` rewrites the block and `fixtures.json`; `--check` exits 1 when either differs. Fixtures: `axes` cases (held key sets + scale + profile + deadzone → `KeyState.axes`), `status` cases (status line + seen → `header_lines`, `footer_line`, `flip_target`). Cover all six header states, both profiles, diagonals, opposite keys, Space, nan headings, garbled lines.
- `package.json`: publisher `nearlab`, name `svg-teleop`, displayName `SVG Teleop`, version `1.0.0`, main `./dist/extension.js`.

- [ ] **Step 1: Write the failing tests**

```python
class Tables(unittest.TestCase):
    def test_generated_files_match_keymap_py(self):
        r = subprocess.run([sys.executable, str(GEN), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
    def test_removed_aliases_stay_removed(self):
        self.assertFalse({"q", "e", "shift_l", "shift_r", "control_l", "control_r"} & set(K.export_tables()["keys"]))
    def test_a_changed_word_fails_the_check(self): ...   # temp copy with one edited word in the block → --check rc 1
    def test_fixtures_cover_all_six_header_states(self): ...  # the six bold lines all appear in fixtures["status"]
    def test_no_jargon_in_visible_strings(self):
        for s in visible_strings(K.export_tables()):
            for w in ("BODY", "WORLD", "CMU"): self.assertNotIn(w, s)
```

- [ ] **Step 2: Run to verify they fail** — `python3 -m unittest tools.tests.test_svg_teleop_tables -v` → missing GEN.

- [ ] **Step 3: Implement** `export_tables`, the generator and the skeleton (exports `activate`, registers panel `SVG Teleop`, renders nothing yet; copy CMU's tail for how `activate` is exported).

- [ ] **Step 4: Run tests, full suite, commit** — subject `HTX-R1/S5 NEAR-789: keymap.py exports its tables; generated block and fixtures for the Foxglove strip`. Could affect: nothing at runtime. Watch for: `--check` failing after a keymap edit, which is the point.

---

### Task 3: Strip logic in JavaScript

**Files:**
- Modify: `tools/teleop/foxglove/svg-teleop/dist/extension.js`
- Create: `tools/teleop/foxglove/svg-teleop/test/core.test.js`
- Test: `tools/tests/test_svg_teleop_panel.py`

**Interfaces:**
- Consumes: the generated `TABLES` block and `fixtures.json` (Task 2).
- Produces, on `module.exports.__core`: `class KeyState(profile, deadzone)` with `press(key)`, `release(key)`, `allUp()`, `setScale(k)`, `axes()`, `buttons()`, `held()`, `statusText(nowS, maxSpeed)`; `stickFor(frac, width)`; `parseStatus(line)`; `headerLines(status, seen)`; `footerLine(status)`; `flipTarget(status)`; `fillTemplate(tpl, name)`. Key names are `KeyboardEvent.key` lower-cased and mapped: `arrowup`→`up`, `arrowdown`→`down`, `arrowleft`→`left`, `arrowright`→`right`, ` `→`space`. Browser `keyup` is reliable, so no X11 debounce and no silence timer.

- [ ] **Step 1: Write the failing tests** — `core.test.js` walks every fixture and asserts equal results (axes within 1e-9, strings exact), then prints `core ok N cases`. Python wrapper:

```python
@unittest.skipUnless(shutil.which("node"), "node not installed")
class Panel(unittest.TestCase):
    def test_extension_parses(self):  self.assertEqual(run("node", "--check", "dist/extension.js").returncode, 0)
    def test_core_matches_keymap_py(self):
        r = run("node", "test/core.test.js"); self.assertEqual(r.returncode, 0, r.stdout + r.stderr); self.assertIn("core ok", r.stdout)
```

- [ ] **Step 2: Run to verify they fail** — `python3 -m unittest tools.tests.test_svg_teleop_panel -v` → `__core` undefined.

- [ ] **Step 3: Implement** the functions by porting `keymap.py`. The relay-missing bold line is overridden with the strip's own text after `headerLines` returns, in Task 4, not here, so fixtures stay equal to Python.

- [ ] **Step 4: Run tests, full suite, commit** — subject `HTX-R1/S5 NEAR-789: Foxglove strip logic, proved equal to keymap.py by fixtures`. Could affect: nothing at runtime yet.

---

### Task 4: The panel

**Files:**
- Modify: `tools/teleop/foxglove/svg-teleop/dist/extension.js`
- Create: `tools/teleop/foxglove/svg-teleop/test/smoke.js` (DOM stub + fake `panelContext`, modelled on CMU's `svg-basestation/test/smoke.js`, with a fake clock)
- Modify: `tools/tests/test_svg_teleop_panel.py` (runs `smoke.js`, expects `smoke ok`)

**Interfaces:**
- Consumes: `__core` (Task 3), `panelContext.subscribe/unsubscribeAll/advertise/unadvertise/publish/callService/watch/saveState/onRender`, `initialState`.
- Produces: panel `SVG Teleop` with config keys from Global Constraints. Timer 20 Hz. `/safe_teleop/get_parameters` every 2 s (`teleop_controller`, `deadzone`, `max_speed_mps`). F → `set_parameters` with `stick_frame` from `flipTarget`, once per press (`event.repeat` ignored), 2 s timeout then dropped. Handled keys call `preventDefault` and `stopPropagation`.

- [ ] **Step 1: Write the failing smoke cases** (each named exactly, each asserting on the fake context's publish log and the rendered text):

```text
not armed at start: no /joy published, text "Click here to fly — drone holds"
pointerdown arms: publishes at 20 Hz with zero axes, then "FLYING drone_1"
↑ held: forward axis equals fixture value for scale 0.5
focus leaving the root disarms and sends five zeros
window blur disarms and sends five zeros; hidden document does the same
refocusing the window does not re-arm
lost keyup does not stick after re-click
panel cleanup sends five zeros and unadvertises
space lets every key go and shows STOP; a later flight key clears STOP
F while held asks once with event.repeat ignored; target comes from flipTarget
no FLYING while the relay is silent (status older than 2 s: red strip line)
no FLYING with input=none (grey lines, no F in the footer)
publish failure shows the red line and keeps the panel alive
another source on the topic refuses to arm and names the topic; re-click re-checks
own trailing zeros do not trip the check (listen starts 0.5 s after the last disarm)
selector: choosing drone_2 disarms with zeros on the old topic, re-targets all templates, unadvertises the old topic
one drone: selector greyed
no BODY, WORLD or CMU anywhere in the rendered text across all states
```

- [ ] **Step 2: Run to verify they fail** — `node test/smoke.js` from the extension folder → first case fails.

- [ ] **Step 3: Implement.** Look: green frame when flying, dashed grey when not, line 1 bold in the colour from the tables, line 2 the sentence, line 3 monospace footer + `holding: …` + speed, selector on the right. `watch("currentFrame")` and `watch("topics")`, as CMU's panel does. Arming sequence: `pointerdown` → focus root → if listening needed, show `Checking for another source…` for 1 s with a subscription on the joy topic → armed or refused. Copy the `typeof panelContext.callService === "function"` guard. Panel settings use `updatePanelSettingsEditor` if CMU's panel uses it, otherwise the saved config only, and say which in the report.

- [ ] **Step 4: Run tests, full suite, commit** — subject `HTX-R1/S5 NEAR-789: SVG Teleop panel — flies only while clicked, zeros on every way out, drone selector`. Could affect: nothing until installed. Watch for: Studio shortcuts catching Space or arrows despite `stopPropagation`, a panel that never reads FLYING (focus events differ from the stub). Verified by: smoke cases; pending the owner's session.

---

### Task 5: Install, layout, docs, Linear

**Files:**
- Create: `tools/teleop/foxglove/install.sh`, `tools/teleop/foxglove/teleop-cuvslam.json`, `docs/plans/2026-11-03-linear-agent-foxglove-teleop.md`
- Modify: `localisation/scripts/slam_up.sh`, `localisation/docker/up.sh` (mount `tools/teleop/foxglove` read-only at `/teleop-foxglove`), `docs/TELEOP.md` §3b, `localisation/README.md`, `tools/README.md`, `docs/record/CHANGES.md`
- Test: `tools/tests/test_svg_teleop_install.py`

**Interfaces:**
- Consumes: `svg-teleop/` (Tasks 2 to 4).
- Produces: `install.sh <dest-dir>` copies the extension to `<dest>/nearlab.svg-teleop-1.0.0`, idempotent, default dest `~/.foxglove-studio/extensions` (the path found in the Studio 2.53.1 bundle). `slam_up.sh` runs it in the exploration container **before** it starts Studio, every time, because that container's home is lost on `docker rm`.

- [ ] **Step 1: Write the failing tests**

```python
class Install(unittest.TestCase):
    def test_install_copies_and_is_idempotent(self): ...       # run twice into a temp dir, package.json + dist/extension.js present
    def test_slam_up_installs_before_studio(self):
        src = (ROOT / "localisation/scripts/slam_up.sh").read_text()
        self.assertLess(src.index("install.sh"), src.index("foxglove-studio --no-sandbox"))
    def test_exploration_container_mounts_the_panel_read_only(self): ...  # up.sh has the :ro mount
class Layout(unittest.TestCase):
    def setUp(self): self.d = json.load(open(LAYOUT))
    def test_three_panels_in_the_chosen_arrangement(self): ...  # Image + 3D side by side, SVG Teleop below (a row inside a column)
    def test_image_shows_the_cuvslam_debug_image(self): ...     # /drone_1/cuvslam/debug_image
    def test_chase_follows_the_moving_body_with_its_heading(self):
        c = self.d["configById"][three_d_id(self.d)]
        self.assertEqual(c["followTf"], "drone_1/cuvslam_base"); self.assertEqual(c["followMode"], "follow-pose")
        self.assertTrue(c["cameraState"]["perspective"])
```

- [ ] **Step 2: Run to verify they fail** — `python3 -m unittest tools.tests.test_svg_teleop_install -v`.

- [ ] **Step 3: Implement.** Layout built from `localisation/foxglove/cuvslam_slam_view.json`. Strip about 22 % of the height. Chase camera: `distance` 4, `phi` 65, `thetaOffset` chosen so the camera sits behind the nose; the owner tunes it live. A reserved empty Tab for the later map panel. Docs: TELEOP §3b gets a short "In Foxglove" paragraph (import the layout once, click the strip to fly, click away and the drone holds, `tools/sim.sh relay` must run, Tk window is the fallback, the `ufw` prerequisite). Linear file (nearlab, same style as `docs/plans/2026-11-03-linear-agent-teleop-frame.md`): one new S5 issue `Teleop strip inside the cuVSLAM Foxglove window, with a chase view`, Backlog issues `Launch one safe_teleop and relay per drone for keyboard switching`, `Live cuVSLAM map panel in the teleop layout`, `Draw the PX4 position in the chase view`; sync record `2026-11-03-linear-synced-2.md`.

- [ ] **Step 4: Run tests, full suite, docs check, `git diff --stat a6e5e87 HEAD -- AirStack/` empty, commit** — subject `HTX-R1/S5 NEAR-789: install the strip with slam_up, teleop-cuvslam layout, docs and Linear file`. Could affect: `slam_up.sh` start-up, and a first `up.sh` after this needs `slam_down.sh` so the new mount exists. Watch for: panel missing from Studio's list (wrong extensions path), the chase view static or facing the wrong way.
