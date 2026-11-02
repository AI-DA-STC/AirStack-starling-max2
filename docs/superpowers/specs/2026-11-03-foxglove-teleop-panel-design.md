# Foxglove teleop panel in the cuVSLAM window — design (2026-11-03)

Owner request 2026-11-03, after the Drive-mode keyboard worked: "the teleop window is still separate and it doesn't look nice; fuse it in Foxglove together with the cuVSLAM window", one pilot switching between drones, a chase view beside the first-person view (mockup option A chosen). Status: **draft for owner approval**. Nothing is built before approval.

## 1 · Intent and why

Today the pilot flies from the cuVSLAM Studio's first-person image while a separate Tk window (`tools/sim.sh keys`) must keep keyboard focus. Two windows, two places to look, and a click on the image stops the keys. The owner wants one Studio window: the camera view, a chase view of the drone over the cuVSLAM map, and a thin teleop strip that flies the drone only while it is the clicked panel.

## 2 · Goals

1. A Foxglove panel of ours, **SVG Teleop**, in the cuVSLAM Studio window, that publishes the same `/joy` stream the Tk window does, so `safe_teleop`, the relay and the commander are unchanged.
2. It flies **only while it is the clicked panel**. Click anywhere else, hide the tab, blur the Studio window or close the panel, and zeros go out at once, then the stream stops; the drone holds.
3. The strip shows the same words as the Tk window: Drive mode / Room mode lines from `/teleop_frame/status`, the keys, what is held, the speed in m/s; `F` flips the mode, `Space` stops, `1/2/3` set the speed.
4. One shipped layout: first-person image left, 3D chase view right (camera locked behind and above the selected drone, turning with it), the strip underneath, space left for a later live-map panel.
5. Scalable to several drones with one keyboard: every topic the strip uses is a per-drone template, a drone selector on the strip switches them (zeros to the old drone first). The single-drone session of today keeps working unchanged.
6. The Tk window stays as the fallback (`tools/sim.sh keys`), untouched.
7. Change-log rows for every behaviour change (docs/CODING_STANDARD.md).

## 3 · Non-goals and anti-goals

- **Not the real drone.** Sim only; nothing under `AirStack/` changes. The real session keeps the gamepad through `joy_node`.
- **Not a browser gamepad.** The container's Studio has no `/dev/input`; pads stay on `joy_node`.
- **Not the live cuVSLAM map panel.** That is a later item; the layout leaves a slot for it.
- **Not a multi-drone launch.** Running one `safe_teleop` + relay per drone (`/drone_N/joy`, `…_stick`) is a follow-up project; this one wires the topic convention and the selector so that project needs no panel change (§5.6).
- **Anti-goal:** a strip that looks armed while nothing reaches the drone, or that keeps flying after the pilot's attention left it. Every "not flying" state is visible on the strip and ends with zeros on the wire.
- **Anti-goal:** two sources on one `/joy`. The strip refuses to arm while another publisher is live on its joy topic.

## 4 · Constraints

- Foxglove Studio **2.53.1** inside the `localisation-exploration` container (`scripts/slam_up.sh`, own `--user-data-dir=/exploration/foxglove/studio-data`), connected to our bridge `scripts/foxglove_bridge_isaac.sh` (`foxglove_bridge` on port 8766, `use_sim_time`, a **topic whitelist** that today lists only cuVSLAM, images, `/tf`, `/clock`). Client publishing and services go through that bridge, so its whitelists must admit what the strip uses.
- CMU's Basestation panel (`…/svg_ground_control/foxglove/svg-basestation/`, plain JavaScript, no build step, installed by `foxglove/install.py` into `~/.foxglove-studio/extensions/<publisher>.<name>-<version>`) is the pattern to copy: `extensionContext.registerPanel({ initPanel })`, `panelContext.subscribe / advertise / publish / callService / watch`. Studio loads extensions at start, so the panel must be installed before Studio opens.
- `safe_teleop` reads `/joy` (profile `joy_topic`), `sensor_msgs/Joy`, and holds zero velocity after 0.5 s without it (`joy_timeout_s`). Its axis map and dead zone come from `/safe_teleop/get_parameters` (the Tk window reads `teleop_controller`, `deadzone`, `max_speed_mps`).
- The relay (`tools/teleop/teleop_frame.py`) publishes `/teleop_frame/status` at 5 Hz and takes `stick_frame` through `/teleop_frame/set_parameters`.
- Key semantics are fixed by `tools/teleop/keymap.py` (CMU sign conventions, dead-zone compensation `stick_for`, the words, `header_lines`, `footer_line`, `flip_target`, Space/F rules). The panel must not re-derive them by hand.
- Iron rule 9; never edit `AirStack/`; the owner's wording rules (Drive mode / Room mode, no BODY/WORLD/CMU on screen, no diagrams).

## 5 · Decisions

### 5.1 Our own extension, plain JavaScript, in `tools/teleop/foxglove/svg-teleop/`

`package.json` (publisher `nearlab`, name `svg-teleop`, version 1.0.0, `main: ./dist/extension.js`) and `dist/extension.js`, written by hand like CMU's panel (no bundler). One panel, **SVG Teleop**. Installed by a new `tools/teleop/foxglove/install.sh` that copies the folder into the exploration container's Studio extensions directory before Studio starts; `scripts/slam_up.sh` calls it (and `tools/sim.sh keys`/`relay` are untouched). The builder finds the exact extensions path for a Studio started with `--user-data-dir` (`<user-data-dir>/extensions/` is the expected place; `~/.foxglove-studio/extensions` is the documented default — install to both if needed and say which one Studio used).

### 5.2 One source of truth for keys: `keymap.json` generated from `keymap.py`

`python3 tools/teleop/keymap.py --dump-json > tools/teleop/foxglove/svg-teleop/dist/keymap.json` writes the key table (keysym → stick, sign), `WORDS`, `SCALES`, `DEFAULT_SCALE`, `DEADZONE`, `PROFILES`, the six header sentence pairs and colours, the footer templates. The extension loads it (inlined at install time or fetched relative to `extension.js`, builder's choice) and computes axes with the same `stick_for` formula. A unit test regenerates the JSON and fails if the committed copy differs; a JavaScript smoke test (`node test/smoke.js`, like CMU's) feeds key sets through the panel's mapper and compares with a fixture produced by `keymap.py` for the same sets.

### 5.3 Flying only while clicked

- The panel root has `tabindex=0`; **armed** = the root (or a child) is `document.activeElement` AND the Studio document is visible AND the window has focus. The strip shows a green frame and `FLYING drone_N` when armed, a dashed grey frame and `Click here to fly — drone holds` otherwise.
- `keydown`/`keyup` on the root only; `event.repeat` is ignored (no X11 debounce needed). Keys map through `keymap.json`; `Space` releases everything; `F` asks the relay once per press (`callService` on `/teleop_frame/set_parameters`, target from `flip_target`); `1/2/3` set the scale.
- A 20 Hz timer publishes `sensor_msgs/Joy` on the selected drone's joy topic while armed. On **disarm** (focusout, `visibilitychange` hidden, window `blur`, panel unmount, Studio disconnect): every key is let go, **five zero messages** are sent (one per tick), then the timer stops and the topic is unadvertised. `safe_teleop`'s 0.5 s timeout is the backstop.
- The panel never sends while the bridge reports no connection; it shows `NO BRIDGE` in red.

### 5.4 One source only

Before arming, the panel subscribes to its joy topic for 1 s; if any message arrives, it refuses with `Another source is publishing <topic> (the keyboard window or a pad). Close it first.` and stays disarmed. It re-checks each time it is clicked. The Tk window's own "other publisher" warning covers the opposite case.

### 5.5 What the strip shows (words only, same as the Tk window)

Line 1 bold: the mode line from `header_lines` (`Drive mode — ↑ is always where the nose points`, `Room mode — …`, `Switching to … — let go of the keys first`, `Heading lost — let go of the keys`, `Keys not reaching the drone — start the relay: tools/sim.sh relay`, grey Room lines on `input=none`), coloured as in `keymap.py`, with ` · FLYING drone_N` appended while armed. Line 2: the sentence. Line 3 (monospace): the footer keys plus `holding: ↑, ←` and `50 % = 1.0 m/s` (speed from `/safe_teleop/get_parameters` `max_speed_mps`, re-read every 2 s). Right side: the drone selector. All text from `keymap.json`; the relay-missing line reads `start the relay: tools/sim.sh relay` here because the panel cannot start it.

### 5.6 Per-drone topics and the selector

Panel settings (Foxglove panel settings sidebar): `drones` (list, default `["drone_1"]`), `joyTopicTemplate` (default `/joy`, i.e. today's single-drone session; the multi-drone convention is `/{name}/joy`), `statusTopicTemplate` (`/teleop_frame/status`; convention `/{name}/teleop_frame/status`), `teleopNsTemplate` (`/safe_teleop`; convention `/{name}/safe_teleop`), `relayNsTemplate` (`/teleop_frame`; convention `/{name}/teleop_frame`). The selector lists `drones`; choosing another drone disarms (zeros to the old topic), re-targets every template with `{name}`, then waits for a click to arm again. With one drone the selector is greyed. The follow-up project that launches one `safe_teleop` + relay per drone only has to set these templates in the layout.

### 5.7 The layout: `tools/teleop/foxglove/teleop-cuvslam.json`

Three panels: **Image** on `/drone_1/cuvslam/debug_image` (left), **3D** (right) with `followTf: drone_1/cuvslam_odom`, follow mode with orientation, perspective camera behind and above the drone (the builder tunes `distance`, `phi`, `thetaOffset` so the view sits behind the nose and turns with it; the existing `cuvslam_slam_view.json` shows the field names), showing the odometry trail, the cuVSLAM landmarks and every drone's `cuvslam_odom` frame; **SVG Teleop** across the bottom. A collapsed fourth slot (empty Tab) is reserved for the map panel. Imported once in Studio (Layouts → Import from file, documented in TELEOP.md §3b and localisation/README.md) like the existing SLAM layout.

### 5.8 Bridge whitelists (our script, `localisation/scripts/foxglove_bridge_isaac.sh`)

Add to `topic_whitelist`: `^/joy$`, `^/drone_[0-9]+/joy$`, `^(/drone_[0-9]+)?/teleop_frame/status$`. Add `service_whitelist`: `^(/drone_[0-9]+)?/teleop_frame/set_parameters$`, `^(/drone_[0-9]+)?/safe_teleop/get_parameters$`. Keep `client_topic_whitelist` at its default (`.*`) or set it to the joy patterns, builder's choice. The commander's own bridge in the robot container is untouched.

### 5.9 Records and docs

- CHANGES rows: the extension + installer + `keymap.py --dump-json` (sim-only tooling); the bridge whitelist; the layout file; `slam_up.sh` installing the panel.
- `docs/TELEOP.md` §3b: a short "In Foxglove" paragraph (the strip, click to fly, selector, layout import); `localisation/README.md`: the new layout and installer; `tools/README.md`: `teleop/foxglove/`.
- Linear: one new S5 issue "Teleop strip inside the cuVSLAM Foxglove window, with a chase view" (next sync file); the multi-drone launch as a separate Backlog issue.

## 6 · Left to the builder

- The extension's internal structure (one file like CMU's or a few), how `keymap.json` is loaded, the smoke-test harness (CMU's `test/smoke.js` is the model).
- The exact Studio extensions directory for a `--user-data-dir` instance, and how `install.sh` is idempotent.
- Chase-camera numbers in the layout; marker sizes.
- How the panel detects bridge disconnect (`panelContext.watch("topics")` going empty, or the Studio connection state).

## 7 · Done when

- Owner session in the construction site, video watched: flies drone_1 from the strip in the cuVSLAM window with the chase view beside the image; clicking the image stops the drone within a second; clicking the strip resumes; `F` flips to Room mode and back; the Tk window still works as a fallback and the strip refuses to arm while it is open.
- `node tools/teleop/foxglove/svg-teleop/test/smoke.js` and the `keymap.json` contract test pass in the pre-commit suite; `python3 tools/docs_check/check_docs.py` 0 FAIL; `changes.py audit` PASS; `git diff --stat AirStack/` empty.
