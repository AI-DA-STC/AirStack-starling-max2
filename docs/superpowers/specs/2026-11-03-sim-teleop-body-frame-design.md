# Sim keyboard teleop in BODY frame — design (2026-11-03)

Owner decision 2026-11-03, after a three-agent panel (positions kept in the session scratchpad `panel6/`): the sim keyboard flies relative to the drone's nose, switchable to room frame with one key; the real drone is untouched. Status: **draft for owner approval** (UI wording settled with the owner 2026-11-03). Nothing is built before approval.

## 1 · Intent and why

CMU's teleop is **room-fixed**: the stick's "forward" is mocap +X, whatever way the nose points ([TELEOP.md §1](../../TELEOP.md)). That suits a pilot who watches the drone from outside. In the sim the owner watches a view that follows the drone, and after a 180° turn every key felt reversed (NEAR-789 session, 2026-11-03). The owner wants the controls of a helicopter in a flight simulator or GTA V: forward is where the nose points.

On screen the two frames are called **Drive mode** and **Room mode** (owner, 2026-11-03, after mockups: no diagram, no jargon, one analogy each). In code, parameters and docs they carry PX4's names, which are also MAVROS's: **BODY** (relative to the nose, `FRAME_BODY_NED`) and **WORLD** (relative to the room, `FRAME_LOCAL_NED`). Drive mode = BODY and is the default.

## 2 · Goals

1. In the sim, with the keyboard, ↑ moves the drone the way its nose points, ← slides it to the nose's left, and this stays true after any turn.
2. One key (`F`) flips between Drive mode (BODY) and Room mode (WORLD) while flying; the window says which is live in plain words.
3. A heading fault can never send the drone the wrong way at speed: a stale or jumping heading zeroes the horizontal command until the operator centres the keys.
4. Nothing in CMU's tree changes, and the real-drone session cannot run any of this.
5. Every behaviour change has a `docs/record/CHANGES.md` row and a commit body `Change: CHG-nnnn` (docs/CODING_STANDARD.md).

## 3 · Non-goals and anti-goals

- **Not the real drone.** `teleop_real_ours.yaml`, the real launch and the gamepad path stay exactly as shipped. Flying the real drone in BODY frame is a later decision with its own test (HTX-R2 M5).
- **Not a patch to `AirStack/`.** No change to `safe_teleop`, `swarm_commander`, `teleop.launch.py` or the Basestation panel. (The panel considered a `stick_frame` parameter in `safe_teleop` as patch 0008; the owner chose sim-only code instead.)
- **Not attitude control.** `safe_teleop` commands velocities. "Roll" on screen means a sideways slide, never a bank angle.
- **Not the Foxglove teleop panel.** That is the next project; this design must not make it harder (see §5.1: the relay is its own process, so a panel can replace the Tk window later).
- **Anti-goal:** a green "STICKS LIVE" in the Basestation while the commander receives nothing. The topic layout in §5.2 is chosen so that cannot happen.

## 4 · Constraints

- Iron rules (CLAUDE.md): rule 9, never edit `AirStack/` except as a recorded patch; `_ours` configs are the recorded way to add a run config (CONFIG.md "Ground-side flight configs", `swarm_real_ours.yaml`, `goal_single_ours.yaml`, `teleop_real_ours.yaml` precedent).
- `safe_teleop` keeps publishing world-frame ENU `TwistStamped` at 20 Hz on the topic its `teleop_topic_template` parameter names; the commander reads its own `teleop_topic_template` (default `/svg/{name}/teleop_command`) and holds the drone when that stream is stale for `teleop_timeout_s` 0.5 s. Both templates are per-node parameters loaded from the run yaml.
- The Basestation's Teleop card shows while `/svg/{name}/teleop_command` is fresh and reads `/joy` for the stick picture (`extension.js` `renderTeleop`, `teleopTopicTemplate`).
- Heading source: `/drone_1/odometry_conversion/odometry` (the commander's `state_topic_template`), ENU yaw from the quaternion. Its sim rate is not recorded; the builder measures it and the record states it (goal: ≥ 20 Hz).
- `/joy` axes are clipped at ±1 and dead-zone compensated, so the rotation cannot be done in the keyboard window's `/joy` output (a rotated diagonal would clip).
- Sim time runs 1.3–2× wall clock; all timeouts are in ROS time inside the container.

## 5 · Decisions

### 5.1 A relay node of our own: `tools/teleop/teleop_frame.py`

A small ROS 2 node, **our file, sim only**, run inside the robot container. It:

- subscribes to `safe_teleop`'s output on `/svg/{name}/teleop_command_stick` (world-frame stick velocity as CMU computes it, see §5.2) and to the drone's odometry;
- publishes on `/svg/{name}/teleop_command` (the topic the commander and the Basestation card already read) at the input rate;
- in **BODY** mode rotates the horizontal velocity by the measured ENU yaw ψ: `vx_w = vx cos ψ − vy sin ψ`, `vy_w = vx sin ψ + vy cos ψ`; `vz` and the yaw rate pass through unchanged;
- in **WORLD** mode passes the message through unchanged;
- has a parameter `stick_frame` (`body` | `world`, default `body` because it is only ever launched in sim), settable live; the keyboard's `F` key sets it through the standard parameter service;
- publishes a status string on `/teleop_frame/status` at 5 Hz: frame, heading in degrees (0 = +X, clockwise positive, the operator convention of `yaw_to_heading`), heading age, guard state;
- is a separate process from the keyboard window, so the coming Foxglove panel can replace the window and keep the relay.

The pure maths and the guard live in `tools/teleop/frame.py` (no ROS, no Tk), unit-tested; `teleop_frame.py` is the ROS wiring.

### 5.2 Topic layout: divert `safe_teleop`, not the commander

A new run config **`teleop_single_ours.yaml`** (copy of `teleop_single.yaml`) whose `safe_teleop` block sets `teleop_topic_template: "/svg/{name}/teleop_command_stick"`. The commander block is unchanged, so the commander still reads `/svg/{name}/teleop_command`, which the relay now feeds.

Why this direction: if the relay is not running, the commander and the Basestation see nothing on `/svg/{name}/teleop_command`, the card hides ("safe_teleop not publishing") and the drone holds. The alternative (pointing the commander at a relay topic) would leave the card green with the commander deaf. Recorded as an `_ours` config in CONFIG.md, like the three existing ones.

`teleop_single.yaml` (CMU's) stays and still works with no relay: WORLD frame, exactly as today.

### 5.3 Heading guard

In BODY mode the horizontal command is zeroed (vz and yaw rate still pass) when:

- the latest odometry is older than **0.2 s**, or
- the yaw moved by more than **0.5 rad** between two consecutive odometry samples (a real turn at the 1.0 rad/s stick limit moves about 0.03 rad per sample at 20 Hz; a rigid-body flip is π).

The relay logs `HEADING JUMP` or `HEADING STALE` once per episode, the status string says `guard: tripped`, and the window turns its header red. The guard **re-arms only when the stick is centred** (|v| < 0.05 m/s on the input) and the heading is fresh and steady again, so a drone never lurches off when the fault clears mid-push. WORLD mode never trips the guard.

### 5.4 Key map (`tools/teleop/keymap.py`)

| Key | On screen |
|---|---|
| ↑ / ↓ | pitch: forward / back |
| ← / → | roll: slide left / right |
| W / S | climb / descend |
| A / D | turn (yaw) left / right |
| Space | STOP (every key let go, zeros published) |
| F | drive mode ⇄ room mode |
| 1 / 2 / 3 | 25 / 50 / 100 % = x.x m/s (computed from `safe_teleop`'s live `max_speed_mps`) |

The Shift/Ctrl and Q/E aliases are removed (Ctrl and Shift are Foxglove shortcuts in the panel that follows; one key per action keeps the two UIs identical). Signs are unchanged: ↑ = +forward, ← = +left, A = +yaw (counter-clockwise), W = +climb; these are CMU's `controllers.py` conventions and `test_keymap.py` keeps checking them against that file.

Window header, **words only, no picture** (owner chose this over two mockup rounds), read from `/teleop_frame/status`. Two lines:

- Drive mode: bold green **`Drive mode — ↑ is always where the nose points`**, then `Like driving a car: turn with A / D, then ↑ goes that way.`
- Room mode: bold blue **`Room mode — ↑ is always the far wall`**, then `Like moving a chess piece: ↑ is the far wall no matter where the nose points.`
- `F` pressed while a key is held: bold amber **`Switching to room mode — let go of the keys first`** (or "drive mode"), then `Your ↑ still works the old way until every key is up.`
- Heading lost (guard tripped): bold red **`Heading lost — let go of the keys`**, then `The drone holds until the heading is back and every key is up.`
- Relay missing: bold red **`Keys not reaching the drone — run tools/sim.sh keys again`** when the status topic is silent for 2 s.
- Launched with the old yaml (no diversion, §5.8 1): the Room-mode lines in grey, and the footer omits `F`.

The footer line lists the keys: `A / D turn · W / S up / down · Space STOP · F → room mode` (or `→ drive mode`). The existing status line (held keys, percent) stays and gains the m/s figure. "BODY"/"WORLD" appear only in brackets in TELEOP.md, never on screen.

### 5.5 Front door

`tools/sim.sh keys` starts the relay in the container, then the window; when the window ends, the relay is stopped too (same `trap`). It refuses, as today, when a window is already running, and also when a second relay is. The Cockpit tab command and the session docs use `teleop_single_ours.yaml`:

```bash
CFG=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/teleop_single_ours.yaml
ros2 launch svg_ground_control teleop.launch.py config:=$CFG          # Cockpit tab
ros2 launch svg_ground_control ground_control.launch.py config:=$CFG use_foxglove_studio:=true   # Commander tab
```

### 5.6 Test: "forward follows the nose" (`tools/sim.sh test teleop_frame`)

A scripted sim test in `tools/sim_tests/teleop_frame/`, same harness as `yaw_step`. It drives the relay's **input** topic (`…/teleop_command_stick`, the same message `safe_teleop` would send) with the relay running in BODY mode:

1. Hover at `hover_positions`. For each heading 0°, 90°, 180°, 270°: yaw to it with the yaw rate, settle 2 s, push forward at 25 % of `teleop_max_speed_mps` for 2 s, release, wait 3 s.
2. Gates per pulse: the horizontal move is **within 20° of the nose heading** measured from odometry; the move is **≥ 0.15 m**; after release the drone **parks within 0.30 m** of its release point within 3 s. Numbers are vehicle time.
3. One WORLD-mode pulse at heading 180° as a control: the move must be within 20° of +X (room), proving the toggle.
4. The record names the live `stick_frame`, the odometry rate and the airframe/CHG ids; a missing value is INCOMPLETE, never PASS. Ctrl-C is ABORTED.

The keyboard itself is covered by `tools/tests/test_keymap.py` (new words, Space, F, aliases gone, m/s text) and a new `tools/tests/test_teleop_frame.py` (rotation at the four headings, pass-through in WORLD, both guard trips, re-arm only when centred). Both run in the pre-commit hook.

### 5.7 Records and docs

- `CHANGES.md`: **CHG-0026** relay + `teleop_single_ours.yaml` (scope: sim teleop; could affect: Basestation card now shows the relay's output, NEAR-789/790 hand-flown sessions before this date were WORLD frame; watch for: guard trips in the log, heading convention sign). **CHG-0027** key map (Space, F, aliases removed, words). Each in its own commit with `Change:` body.
- `docs/TELEOP.md` §3b rewritten with the table above and a short "BODY vs WORLD" paragraph; §1 gets one sentence saying the sim keyboard differs from CMU's room-fixed rule and why.
- `docs/CONFIG.md`: a `teleop_single_ours.yaml` row. `tools/README.md`: `keys` starts the relay. `tools/sim_tab.sh` Cockpit text and RUNBOOK/sim command lists: the `_ours` config.
- Linear (next sync file): a new S5 issue "Sim keyboard teleop flies BODY frame, with F to switch to WORLD, and the forward-follows-the-nose test", blocked-by none; a note on NEAR-874 that the NUS velocity contract stays WORLD frame and is unaffected.
- Ledger row for the first `teleop_frame` run.

### 5.8 Builder-check answers (my calls, 2026-11-03)

A fresh reviewer read this document as the builder would. Five questions came back; the answers below are the designer's calls, not the owner's, and the owner can change any of them.

1. **Relay with a silent input.** With CMU's `teleop_single.yaml` or `swarm_sim.yaml` (no diversion), `safe_teleop` feeds the commander directly and the relay hears nothing. The relay reports `input: none` in its status when `…_stick` has been silent for 1 s, and the window shows the grey Room-mode lines with no `F` in the footer (§5.4). It never claims Drive mode without input. The relay's drone name follows `safe_teleop`'s `drone` parameter, which `keys` already reads.
2. **`F` while a key is held.** The flip is **held until every key is let go**, like the guard's re-arm; the window shows the amber "Switching to … — let go of the keys first" lines meanwhile (§5.4). A flip never reverses a push in flight.
3. **Gamepad in sim, and the test.** The relay gets its own front door, `tools/sim.sh relay [body|world]` (start it, or report it running), which is also the hook the Foxglove panel will use. `keys` starts the relay if none runs and stops only what it started. The Cockpit tab text names `relay` for pad users. `tools/sim.sh test teleop_frame` starts and stops the relay through the same command in its `fly.sh`.
4. **Keeping it out of the real session.** Convention is not enough for a safety goal. `tools/sim.sh keys` and `tools/sim.sh relay` refuse to start unless the `isaac-sim` container is running (the real session never has it), with a one-line reason. The relay itself has no real-drone knowledge; the container check is the guard, and it is unit-tested like the other `sim.sh` refusals.
5. **Odometry rate below 20 Hz.** The guard thresholds are relay parameters (`heading_stale_s` 0.2, `heading_jump_rad` 0.5) whose defaults assume about 20 Hz. The test records the measured rate; below 10 Hz the run is INCOMPLETE and the builder reports before any threshold is changed. Nothing is re-derived silently.

## 6 · Left to the builder

- Tk + rclpy co-operation in `key_teleop.py` (it already runs a 20 Hz tick); how the window subscribes to the status string and calls the parameter service for `F` without blocking the loop.
- How `cmd_keys` and `cmd_relay` share one container process and clean up on every exit path.
- The exact status string format and its parsing, the heading-rate measurement, the test harness files copied from `yaw_step/` (`fly.sh`, `gates.py`, `layout.json`, `record.py`).
- Whether the relay stamps the output with its own clock or copies the input stamp (copy, unless the commander's staleness check argues otherwise).

## 7 · Done when

- Sim session with `teleop_single_ours.yaml`: after a 180° turn, ↑ still moves the drone the way the nose points; `F` flips to Room mode and ↑ moves it towards +X; the window's mode lines match throughout. Owner-watched video, as every hand-flown result.
- `tools/sim.sh test teleop_frame` PASS once, ledger row written.
- `python3 -m unittest discover tools/tests` green, docs check 0 FAIL, `changes.py audit` PASS, `teleop_real_ours.yaml` and everything under `AirStack/` unchanged (`git diff --stat AirStack/` shows only the new `_ours` yaml).
