# BASESTATION — the Foxglove panel that replaced RViz

> **Who this is for:** anyone in the AI.R / STC lab who sits at the ground-control
> laptop during a flight, no robotics background needed. This is the **operator's screen**:
> one Foxglove panel showing what the swarm commander thinks, with the buttons that command
> it. It is **NOT** the safety card ([PREFLIGHT.md](PREFLIGHT.md) stays the authority on
> emergencies), **NOT** the session walkthrough ([RUNBOOK.md](RUNBOOK.md) §B), **NOT** a
> Foxglove tutorial.
> ⚠️ **Nothing here has been validated by us yet.** The repo switched its vendored AirStack
> snapshot to CMU branch `yikuan/SVG_ground_control` @ `cf719f0` on **2026-10-07** and the
> panel came with it. `✅ CMU` = CMU's claim; `⏳ STE` = ours to prove at STE (M0-M3).

---

*(Unfamiliar term? → [GLOSSARY.md](GLOSSARY.md))*

## 1 · What the Basestation is, in plain terms

Until this branch the operator watched **RViz**: a 3D box with a drone marker. It told you
*where* the drone was and nothing else — whether the commander heard your `takeoff`, whether
odometry was fresh, whether the CBF was fighting the drone, all of that lived in scrolling
terminal logs. The **SVG Basestation** is a panel inside **Foxglove Studio** (a free desktop
app, roughly "RViz with a browser's UI") that replaces that view. Think of a car's
**instrument cluster**: every light, gauge and switch you need while moving, on one surface.

```
┌──────────────────────────────────────┬─────────────────────────────┐
│ LINK·EKF·POWER·0 sim 3 real·Tasks·   │  3D view /svg/viz/markers   │
│   0/3 airborne 14:02:51              │  (drone marker, geofence    │
│ [Safety Stop · Land All] [Hold All]  │   box, fence-floor grid,    │
│ Takeoff Start Reset · mission chip · │   CBF keep-out spheres)     │
│   last-command chip · command log    ├─────────────────────────────┤
│ CBF gains · Formation · Goal card    │  SVG Battery & Power        │
│ Agents roster │ Wiring · Agent State │  (SoC, sag, RTB budget,     │
│ Link Safety · Cellular               │   Land All)                 │
└──────────────────────────────────────┴─────────────────────────────┘
```

The left half is **this panel**; the right column is a stock Foxglove 3D view over a **second
copy** of the same panel showing only power (§5). That 3D view is what replaces RViz, including
the M2 hand-carry check. Two of CMU's design rules explain most surprises: **no fabricated
numbers** (anything with no live source reads `--`, and every derived number is tagged with its
origin — `cmdr`, `odom`, `dds`, `est`), and **topics decide what you see** (a section with no
publisher is not drawn, so an "empty" panel usually means something upstream is not running —
the **Tasks** chip says what the panel inferred).

## 2 · Quick start

The robot container installs the panel into its *own* Foxglove directory at start-up
([`docker-compose.yaml:34-35`](../AirStack/robot/docker/docker-compose.yaml)), which does
nothing for a Studio on the laptop — so install it on the **laptop** once (M0):

```bash
cd ~/AirStack-starling-max2/AirStack
python3 robot/ros_ws/src/svg_ground_control/foxglove/install.py
```

It copies the panel to `~/.foxglove-studio/extensions/airlab-cmu.svg-basestation-1.0.0`.
**Restart Studio afterwards** — extensions load only at start-up. Then, with the stack up
([RUNBOOK.md](RUNBOOK.md) §B; the launch starts the WebSocket server for you):

1. In Studio: **Open connection → Foxglove WebSocket → `ws://localhost:8765`** (the robot
   container is host-networked, so `localhost` is correct).
2. **Layouts → Import from file →** `…/svg_ground_control/foxglove/svg_basestation.json`.
   Re-import after any panel update; the older single-panel layout stacks everything on the
   left and gets cut off. `✅ CMU`

**Healthy** on our rig — one real drone on the floor, mocap up — is: banner
`LINK HEALTHY` · `EKF EV FUSED` · `0 sim · 3 real` · `0/3 airborne`; mission chip
`ON GROUND`; `drone_1` in Agent State as `IDLE` with x y z matching the mocap pose and tagged
`cmdr`, `Odom fresh`; `drone_2`/`drone_3` all `--` (**expected**, §6); and the 3D view showing
one drone marker, the geofence box and a grid on the fence floor. `⏳ STE` — not seen yet.

With no host Studio you can run one *inside* the container, pre-connected with
`ground_control.launch.py use_foxglove_studio:=true` (default `false`).

## 3 · Reading the panel

### 3.1 · Banner chips

**LINK** (worst link state across agents) · **EKF** (worst estimator state across *real*
agents; hidden with no mocap/EKF topics) · **POWER** (worst return-to-base state) ·
`N sim · M real` · **Tasks** (what the panel inferred) · a clock reading `k/N airborne ·
HH:MM:SS` ([`extension.js:1516-1525`](../AirStack/robot/ros_ws/src/svg_ground_control/foxglove/svg-basestation/dist/extension.js), `:2935-2966`).
"Airborne" is just *z > 0.3 m* — not an arming indicator.

### 3.2 · Safety bar

The red **`Safety Stop · Land All`** needs **two clicks within 4 s** (the first arms it, the
button counts down) and then calls `~/land`. Amber **`Hold All`** freezes every drone in
place via `~/hold`, single click (`:2097-2123`). Both swarm-wide — and a *convenience*, not a
replacement for [PREFLIGHT.md](PREFLIGHT.md): the **kill switch (ch8)** is still the only
true motor cutoff, and `hold`/`land` leave the drone **armed**.

### 3.3 · Swarm Command card

**Takeoff**, **Start** (both behind a confirm dialog) and **Reset Fence** call `~/takeoff`,
`~/start`, `~/reset_fence` as `std_srvs/Trigger` on the commander namespace
([`swarm_commander.py:813-817`](../AirStack/robot/ros_ws/src/svg_ground_control/svg_ground_control/swarm_commander.py)).
An unanswered call reports `TIMEOUT` after **6 s** rather than hanging.

- **Mission chip** — fed **only** by `/svg/commander_status`, never by what the panel just
  sent: `ON GROUND` · `TAKING OFF` · `READY TO START` · `NOT READY` (some commanded drones
  still on the ground, so Start is refused) · `RUNNING` · `HOLDING` · `LANDING` ·
  `FENCE BREACH`, plus **`NO COMMANDER`** after 2 s of silence (`:2297-2341`).
- **Last-command chip** — the *commander's* own record of the newest lifecycle call
  (`✓ start 12:01:33` / `✗ start …`, reason on hover). Present even when the reply was lost.
- **Command log** — the last four commands sent from this panel, newest first: `sent, awaiting
  reply` → `reply: accepted / REJECTED / TIMEOUT / FAILED` → `✓ confirmed by commander` or
  `✗ NOT CONFIRMED` (`:1970-2009`).

**The habit to build:** a lost reply is **not** a lost command — the panel confirms by
watching `command_seq` advance *and* the expected effect appear in the snapshot, so
`TIMEOUT` then `✓ confirmed by commander` means it ran. **The snapshot is the verdict**;
never click Takeoff twice because a reply was slow.

### 3.4 · CBF gain row

A dropdown picks one of `cbf_alpha` / `cbf_safety_radius_m` / `cbf_max_speed_mps`
(`:188-206`); slider and number box share one draft per gain; **Apply** sends it via
`<commander>/set_parameters`, **↻** re-reads all three with `get_parameters`. The fixed-width
`live` readout is what the commander is actually running, marked `✓` confirmed / `…` waiting /
`✗` rejected-or-not-taken (`:2380-2462`). Our values: `alpha 2.5`, `r 0.55 m`, `vmax 1.0 m/s`
(`swarm_real.yaml`, [CONFIG.md](CONFIG.md)). Below it, an activity line: red **`CBF EMERGENCY
push-apart engaged`** (solver infeasible — drones inside each other's safety spheres), amber
**`CBF correcting drone_x`**, or a muted "not correcting anyone". With one drone there is no
neighbour to avoid: expect the muted line and fence keep-in only.

### 3.5 · Formation row

A profile dropdown plus **Send**, publishing the name on `/svg/formation_command`. **Hidden
unless that topic exists** (`:1389`, `:2927`). Relevant to M7, not to one drone.

### 3.6 · Goal card

`x y z speed` for the **selected** agent, **Use Current**, and **Send Goal**, which publishes
a `geometry_msgs/PoseStamped` (frame `map`) on `/svg/{name}/goal_command` and, if a speed was
typed, a `Float32` on `/svg/{name}/speed_command` (`:2169-2208`). Goals are in **world ENU** =
odometry **plus** the commander's `drone_position_offsets`, adopted straight out of the
snapshot (`:1346-1358`). Before any snapshot the card's note says the frame is
**unconfirmed** — believe it, and send no goals in that state.

⚠️ **The trap:** goals only act while the commander runs the **`goal`** scenario.
`goal_tracking.yaml` ships `scenario: random_goals`, which **silently ignores** goal, speed and
formation commands. For M4 pass `scenario:=goal`, or use `goal_single.yaml` — which ships
`drone_names: ["drone_2"]` and must be retargeted to `drone_1` first.

### 3.7 · Agents roster and Wiring card

The roster lists the configured agents; **clicking one selects it**, and the Goal and
Wiring cards follow. The **Wiring** card spells out the resolved topics for that agent and
how its mode was decided: publishing under `/{name}/fmu/` ⇒ **real**, `/{name}/interface/`
⇒ **sim**. Read it first whenever a column is unexpectedly blank — it says which topic the
panel is actually watching.

### 3.8 · Agent State table

Columns **Agent · State · x · y · z · Speed · Cmd stream · CBF · Interface · Odom** (`:2464-2597`).

| Column | Read it as |
|---|---|
| **State** | `IDLE` / `ARMING` / `ASCEND` / `ACTIVE` / `LANDING`, from the commander. Hover for role, CBF exemption, hold target |
| **x y z** | tagged `cmdr` (the commander's own world-ENU number — what the CBF filters on and goals fly in) or `odom` (this panel's fallback while the snapshot is stale) |
| **Speed** | ground-truth speed from the same source |
| **Cmd stream** | measured rate on the drone's velocity-command topic — see below |
| **CBF** | `correcting` / `exempt` / `clear` |
| **Interface** | result of the last `robot_command` (offboard / arm / disarm): ✓ accepted, … pending, ✗ rejected |
| **Odom** | `fresh` / `STALE` / `none` as the **commander** sees it (stale ⇒ it commands zero velocity) |

⚠️ **Cmd stream will probably read `--` on our rig.** The panel subscribes *only* to
`/{name}/interface/velocity_command` and `/{name}/fmu/velocity_command` (`:1318-1319`; the
string `trajectory` appears nowhere in `extension.js`), but this branch's commander defaults to
`real_command_mode: trajectory`, publishing `MultiDOFJointTrajectory` on
`/{name}/fmu/trajectory_command` (`swarm_commander.py:415-417`, `:720-745`), and our
`swarm_real.yaml` never overrides it. So the column CMU calls "the proof that the commander is
driving it" likely sees no traffic for us. `⏳ STE` — confirm at M3; if so use `State` + `Odom`
plus `ros2 topic hz /drone_1/fmu/trajectory_command` instead, or point the panel's **Velocity
command** setting at that topic.

⚠️ **The Interface column is new on this branch and is NOT an arming indicator** — it shows
whether the commander's *request* was ACKed, not what PX4 did with it. Iron rule 5 stands:
the software is blind to PX4 arming state. **QGC remains the only trustworthy arming display.**

### 3.9 · Link Safety

A topology diagram plus a per-agent table: Path, Rate, Ping, **Drop**, Max gap, Mocap age,
EKF, Clock drift, State, **Bridge**. **Drop** carries a source tag (`:736-754`, `:2672-2689`):
`dds` is genuinely **measured** (the commander's DDS reader counts odometry samples lost by
sequence number and publishes cumulative totals, which the panel differences); `report` needs
a `comms/link_status` publisher we don't run; `est` is an arrival-timing guess — shown
**muted** and never allowed to grade link health, because arrival timing cannot tell a late
sample from a lost one and the Foxglove bridge itself batches.

The **Bridge** column is an **inferred attribution of silence**, not a measurement — nothing
in the stack reports bridge health, so the panel reasons from which streams stopped
(`:633-664`, `:2730-2734`). A hint about *where* to look (MicroXRCEAgent vs `./mocap.sh` vs
the drone), never a fact.

### 3.10 · Cellular · Tailscale VPN

**Hidden on our rig**, and should stay hidden: it needs a cellular or VPN topic to exist, and
we have no 4G/5G and no Tailscale. If it appears, something is publishing that shouldn't be.

### 3.11 · Battery & Power

One card per agent: SoC bar with ticks at the two return-to-base thresholds (`rtbNominalPct`
30, `rtbGatedPct` 20), pack voltage, draw, **sag** against the highest voltage seen this
session, mission time, and a distance-to-pad energy budget that fires `RTB NOW`. Its action
button is **Land All** behind a confirm — there is no per-agent land service. Real-hardware
SoC comes from `/{name}/fmu/out/battery_status`, blank in simulation.

## 4 · The `/svg/commander_status` snapshot

The **new top-of-funnel diagnostic** on this branch: a `std_msgs/String` carrying JSON,
published at `status_rate_hz` (**5 Hz** default) by `swarm_commander.build_status`
(`swarm_commander.py:1037-1118`). Almost everything the panel asserts comes from here, so when
the panel looks wrong read the snapshot directly — in the **container**:

```bash
ros2 topic echo /svg/commander_status --once | python3 -c \
  "import sys,json,yaml;print(json.dumps(json.loads(yaml.safe_load(sys.stdin)['data']),indent=2))"
```

(`echo` prints the JSON as one escaped line; the pipe makes it readable. `ros2 topic hz
/svg/commander_status` should read ≈ 5 Hz.) Per drone, in `drones[]`:

| Field | Means |
|---|---|
| `role` `mode` `commanded` | `auto`/`teleop`/`external` · `sim`/`real` · whether the commander drives it at all |
| `cbf_exempt` `cbf_active` | left uncorrected by the filter · being corrected right now |
| `state` `speed_mps` `hold_target` | the Agent State chip (`IDLE`/`ARMING`/`ASCEND`/`ACTIVE`/`LANDING`); speed; where it is freezing (only while ASCEND/ACTIVE) |
| `position_offset` `position` | the offset, and world ENU = odometry + offset (the frame goals fly in) |
| `odom_fresh` `odom_age_s` | the `Odom` column. Not fresh ⇒ commander outputs zero velocity |
| `odom_rx_total` `odom_lost_total` `odom_loss_counter` | DDS loss counters behind the `dds` Drop tag. `odom_loss_counter: "unsupported"` means this RMW has no `message_lost` event, so there is no measured drop |
| `robot_command` | `{label, result, message, stamp}` — the `Interface` column |

Globally: `scenario`, `mission_active`, `mission_ever_started`, `mission_started_at`,
`fence_enabled`, `fence_breached`, `fence{behavior,min,max,keep_in_gain,brake_accel_mps2,margin_m}`,
`teleop_fence{…}`, `cbf{alpha,safety_radius_m,max_speed_mps,external_velocity_gain,active,emergency}`,
plus `command_seq`, `last_command`, `stamp`, `node`, `pid`.

**`pid` has a purpose.** `takeover_twins` (default **true**) makes a second `ground_control`
launch read other commanders' snapshots and **kill the older one** 2 s after start-up —
*unless* it has a drone in a non-`IDLE` state, in which case it refuses and logs an error
(`swarm_commander.py:1188-1225`). A stray commander from a dead terminal self-cleans; one
with a drone in the air is never killed under you.

## 5 · The `view` setting and the two-instance layout

One panel, three shapes, chosen in its settings (gear → **View**) (`:1849-1864`, `:3070-3077`):

| `view` | Shows | Panel title |
|---|---|---|
| `full` | everything in one panel (the old single-panel form) | SVG Basestation |
| `main` | everything **except** Battery & Power | SVG Basestation |
| `power` | **only** Battery & Power, with its own power chip and clock | SVG Battery & Power |

The shipped `svg_basestation.json` uses **two instances**: `main` filling the left 50 %, a
`power` instance under the 3D view on the right (§1's picture). The 3D view's **built-in grid
layer is deliberately off** — a fixed 8 m square on the origin that never matches our fence.
The commander draws a world-aligned grid on the *fence floor* instead (`fence_grid_cell_m`,
**0.5 m**), clipped to the fence, inside `/svg/viz/markers`. The drone marker is an **Iris**
mesh (`package://robot_descriptions/iris/…base_link_body_body.stl`, served through the bridge's
asset capability) — cosmetic, not our airframe.

Studio config and imported layouts survive container recreation via the bind mount
`./Foxglove:/root/.config/Foxglove` ([`robot-base-docker-compose.yaml:42`](../AirStack/robot/docker/robot-base-docker-compose.yaml))
— but that is the **container's** Studio. A laptop Studio keeps layouts in its own Foxglove
profile, so re-import there after a panel update.

## 6 · Corrections to CMU's panel README for OUR rig

CMU's [`svg-basestation/README.md`](../AirStack/robot/ros_ws/src/svg_ground_control/foxglove/svg-basestation/README.md)
is the source of truth for the panel's internals. These points differ for us (code-checked
2026-10-07):

| CMU's README says | On our rig |
|---|---|
| Three drones in the demo | **One** real drone, `drone_1`. But `swarm_real.yaml` still lists `drone_1,2,3`, so the roster and Agent State table show **two phantom agents with every cell `--`**. Expected until the config is trimmed to `drone_1` — which is **required before M3** ([MIGRATION.md](MIGRATION.md) §6), not optional as on the old branch |
| Mode is auto-detected from the wire (`/{name}/fmu/` ⇒ real) | True, and it works — but detection needs the drone's `fmu` topics to already be publishing. Before [RUNBOOK.md](RUNBOOK.md) §B's interfaces are up, an agent can read as neither. Set **Modes** to `real,real,real` if you want it pinned |
| `Cmd stream` is "~20 Hz while the commander drives it" and "the proof that Start reached the drone" | Only if commands go out as `velocity_command`. This branch defaults real drones to **`trajectory_command`**, which the panel does not subscribe to — expect `--` (§3.8). `⏳ STE` |
| Cellular / Tailscale VPN section, 4G/5G path | **Not on our rig** — no cellular, no Tailscale. The section stays hidden, by design |
| The 3D view is "plus a 3D view", an extra | For us it **replaces RViz**, including the M2 hand-carry check. The `svg_drones.rviz` Fixed-Frame-`world` gotcha does not apply; this layout follows `map` |
| Services work on any data source | Disabled on a bag / file source (`:1899-1901`): buttons grey out, the CBF readout says `live -- (no services)`. Normal when reviewing a recording |

Two notes on `AirStack/CHANGELOG.md`: its claim that the panel "moved from
`gcs/foxglove_extensions/`" is **not true against our previous snapshot** — it was never
there, it arrived with this branch. And it understates
the slider: all **three** CBF gains are editable, not just alpha.

## 7 · Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Panel loads but everything reads `--` / sections missing | No publishers. Confirm the stack with `ros2 topic list` in the container; the banner's **Tasks** chip names what the panel did find. Setting **Sections → Show all** forces them visible but will not invent data |
| Mission chip stuck on `NO COMMANDER` | Nothing on `/svg/commander_status` for 2 s. Commander not up, or `status_rate_hz`/`status_topic` changed. Check with the §4 `echo` |
| Command log: `TIMEOUT` but then `✓ confirmed by commander` | The reply was lost, the command ran. **Do not resend** (§3.3) |
| Command log: `✗ NOT CONFIRMED` | The commander never recorded it. Check the commander's terminal for a rejection reason, and that there is only one commander (§4, `takeover_twins`) |
| `Cmd stream` reads `--` while the drone is clearly flying | Expected if `real_command_mode: trajectory` (§3.8). Verify with `ros2 topic hz /drone_1/fmu/trajectory_command` |
| Agent State x y z tagged `odom`, not `cmdr` | Snapshot is stale — the numbers are the panel's own odometry plus the **last** offsets it saw. Fix the commander/link before trusting positions or sending goals |
| Goal sent, nothing happens, no error | The commander is running `random_goals` (or another non-`goal` scenario), which ignores goal commands **silently**. Use `goal_single.yaml` or `scenario:=goal` (§3.6) |
| `Odom` column says `STALE` | The **commander** is not getting fresh odometry, so it is commanding zero velocity. Chase mocap first: `./mocap.sh check` ([MOCAP.md](MOCAP.md) §5) |
| CBF Apply: "asked 0.80 but the commander still reports 2.50" | The set did not take. Read the status line under the row for the commander's reason; `↻` re-reads |

## 8 · LED strips

The Basestation's **physical counterpart**: 11 RGBW NeoPixels on the drone's ESC LED output,
so someone standing by the net can read the drone's safety state without looking at a screen
(M6, optional hardware).

**Green = normal**, shown from daemon start, before any ground link exists. **Red = the CBF
is correcting this drone** — from `/svg/cbf_active`, held ≥ `cbf_hold_s` (0.5 s) so one tick
is still visible, and **ignored if the signal is >1 s stale**, so a dead commander cannot pin
the strip red. After **10 s with no ground datagrams** the daemon reverts to green on its own.

Operator recolouring, from the **container** (or `airstack_msgs/srv/SetLedColor`):

```bash
ros2 topic pub --once /svg/led_command std_msgs/msg/String "{data: 'drone_1 blue'}"
ros2 topic pub --once /svg/led_command std_msgs/msg/String "{data: 'all green blink'}"
```

How it talks: the onboard daemon sends a 1 Hz JSON heartbeat to the ground node on
**udp/47901**, which is how the ground side **learns the drone's IP** — nothing is hardcoded,
so open udp/47901 in the laptop's `ufw` or the strips never get a colour. `led_controller` runs
by default (`use_led:=true`) and binds that port **without** `SO_REUSEADDR` on purpose: a second
instance exits rather than two fighting over the strips. Brightness **80/255** — keep it low,
the mocap cameras watch infrared.

⚠️ **The ESC arm-state LEDs are MUTED.** PX4's `voxl_esc` driver normally paints the same strip
with its own arm-state colours (disarmed red, armed blue/green), which fought our green at the
20 Hz passthrough. The daemon freezes those bits (`px4-qshell voxl_esc -l 0 led`), so **the LEDs
no longer tell you whether the drone is armed**. Iron rule 2 is unchanged: arming is read in QGC.

Provisioning belongs with the drone-side work — [DRONE_SETUP.md](DRONE_SETUP.md); the short
form, from the **laptop** (in `…/src/svg_ground_control`):

```bash
scripts/voxl_push_led.sh drone_1 <drone_ip>
```

Then on the **drone**: `systemctl status svg-led` — the strip should sit steady green, with
`PX4 ESC LED bits muted` in its log. `⏳ STE`

## 9 · Technical appendix

All paths relative to `AirStack/`.

| Piece | Location | Role |
|---|---|---|
| Installer | `…/svg_ground_control/foxglove/install.py` | copies any sibling dir with a `package.json` into `~/.foxglove-studio/extensions/<publisher>.<name>-<version>` |
| Layout | `…/foxglove/svg_basestation.json` | 167 lines: two panel instances (`main` + `power`) and the 3D view, with every topic template and threshold |
| The panel | `…/foxglove/svg-basestation/dist/extension.js` | 3220 lines of plain JavaScript, **no build step** — editable in place, then re-run the installer and restart Studio |
| CMU's manual | `…/foxglove/svg-basestation/README.md` | 283 lines; read it for panel internals, with §6's corrections |
| Stale duplicate | `…/foxglove/svg-basestation/dist/nvm.js` | 2120 lines, an **older copy** of the panel. Not referenced by `package.json` (`main: ./dist/extension.js`) but copied into every install. Harmless — just don't edit it by mistake |
| Bridge node | `…/svg_ground_control/launch/ground_control.launch.py:105-127` | `foxglove_bridge`, port **8765**, address `0.0.0.0`, `respawn=True`, `include_hidden` |
| Container install hook | `robot/docker/docker-compose.yaml:34-35` | runs both Foxglove installers at container start (that Studio only) |
| Studio config persistence | `robot/docker/robot-base-docker-compose.yaml:42` | `./Foxglove:/root/.config/Foxglove` |
| Snapshot producer | `…/svg_ground_control/swarm_commander.py:1037-1118` | `build_status()` → `/svg/commander_status`, 5 Hz |
| Twin takeover | `…/swarm_commander.py:1188-1225` | kills an idle older commander; refuses if its drone is airborne |
| LED ground node | `…/svg_ground_control/svg_ground_control/led_controller.py` | udp/47901 heartbeat listener, `/svg/led_command`, `SetLedColor`, `/svg/cbf_active` → red |
| LED onboard daemon + provisioning | `…/svg_ground_control/scripts/svg_led_daemon.py`, `scripts/voxl_push_led.sh`, `scripts/voxl_setup_led.sh` | the VOXL-side `svg-led` service (11 RGBW pixels, mutes PX4's ESC LED bits) and the `scp`+`ssh` installer that puts it there |
| Our config | `…/svg_ground_control/config/swarm_real.yaml` | `drone_names`, `drone_modes`, CBF gains, fence, `led_controller` block |
