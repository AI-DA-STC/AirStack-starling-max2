# BASESTATION — the Foxglove panel that replaced RViz

> **Who this is for:** anyone in the AI.R / STC lab who sits at the ground-control
> laptop during a flight, no robotics background needed. This is the **operator's screen**:
> one Foxglove panel ("the panel", CMU's **SVG Basestation**) showing what **the commander**
> (the `swarm_commander` node) thinks, with the buttons that command it. It is **NOT** the
> safety card ([PREFLIGHT.md](PREFLIGHT.md) stays the authority on emergencies), **NOT** the
> session walkthrough ([RUNBOOK.md](RUNBOOK.md) §A sim / §B real drone), **NOT** a Foxglove
> tutorial.
>
> **Read first:** [GLOSSARY.md](GLOSSARY.md), then RUNBOOK §A or §B up to the point where
> Foxglove Studio opens. "The real drone" below = our Starling 2 Max.
>
> ⚠️ **Validation:** the panel arrived with the `yikuan/SVG_ground_control` @ `cf719f0`
> snapshot (**2026-10-07**); **2026-10-20** the snapshot moved to `yikuan/SVG_ground_control_dev`
> @ `b21d28c`, whose panel adds three gains to the dropdown (six in all), a **Rosbag** switch in
> the banner, an **agent picker** in the Goal card and a **Teleop · Sticks** card, and drops the
> Agents roster and the Wiring card (§3.4, §3.6, §3.12, §3.13, §9 appendix). It has been used
> against the **sim** since 2026-10-19 (ledger #1–#13); **nothing has been seen with the real
> drone.** `✅ CMU` = CMU's claim; `⏳ STE` = ours to prove at STE (M0–M3).

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
┌────────────────────────────────────────┬──────────────────────────────┐
│ LINK·EKF·POWER·1 sim 0 real·Tasks      │  3D view /svg/viz/markers    │
│   [Rosbag ◯ NO RECORDER] 0/1 airborne  │  (drone marker, geofence     │
│   14:02:51                             │   box, fence-floor grid,     │
│ [Safety Stop · Land All]  [Hold All]   │   CBF keep-out spheres,      │
│ Takeoff Start Reset · mission chip ·   │   amber teleop fence)        │
│   last-command chip · command log      ├──────────────────────────────┤
│ Runtime gain: [dropdown ▾] slider      │  SVG Battery & Power         │
│   number  Apply ↻  live 2.50 ✓         │  (SoC, sag, RTB budget,      │
│ Formation ▾ Send (hidden w/o topic)    │   Land All)                  │
│ Goal: [drone_1] [drone_2] … x y z spd  │  ┌ Teleop · Sticks ┐ only    │
│ Agent State table · Link Safety        │  │ joy·sticks·bars │ while   │
│ Cellular (hidden on our rig)           │  └─────────────────┘ teleop  │
└────────────────────────────────────────┴──────────────────────────────┘
```

The left half is **this panel** in its `main` view; the right column is a stock Foxglove 3D view
over a **second copy** of the same panel showing only power (`power` view, §5), which grows a
**Teleop · Sticks** card beside the battery card while a gamepad node is publishing (§3.13).
That 3D view is what replaces RViz, including the M2 hand-carry check. Two of CMU's design
rules explain most surprises: **no fabricated numbers** (anything with no live source reads
`--`, and every derived number is tagged with its origin — `cmdr`, `odom`, `dds`, `est`), and
**topics decide what you see** (a section with no publisher is not drawn, so an "empty" panel
usually means something upstream is not running — the **Tasks** chip says what the panel
inferred).

## 2 · Quick start

The robot container installs the panel into its *own* Foxglove directory at start-up (the
`command:` block of [`robot/docker/docker-compose.yaml`](../AirStack/robot/docker/docker-compose.yaml)
runs both Foxglove installers), which does nothing for a Studio on the laptop — so install it on
the **laptop** once (M0), and again after every snapshot bump or panel edit:

```bash
cd ~/AirStack-starling-max2/AirStack
python3 robot/ros_ws/src/svg_ground_control/foxglove/install.py
```

It copies the panel to `~/.foxglove-studio/extensions/airlab-cmu.svg-basestation-1.0.0`.
**Restart Studio afterwards** — extensions load only at start-up. Then, with the stack up
([RUNBOOK.md](RUNBOOK.md) §A3 for sim, §B for the real drone; the commander launch starts the
WebSocket bridge for you):

1. In Studio: **Open connection → Foxglove WebSocket → `ws://localhost:8765`** (the robot
   container is host-networked, so `localhost` is correct).
2. **Layouts → Import from file →** `…/svg_ground_control/foxglove/svg_basestation.json`.
   Re-import after any panel update; the older single-panel layout stacks everything on the
   left and gets cut off. `✅ CMU`

**Healthy** on our rig with the **real** configs (`swarm_real_ours.yaml` / `goal_single_ours.yaml`
— one real drone on the floor, mocap up): banner `LINK HEALTHY` · `EKF EV FUSED` · `0 sim · 1 real`
· `0/1 airborne` · Rosbag chip `IDLE`; mission chip `ON GROUND`; `drone_1` in Agent State as
`IDLE` with x y z matching the mocap pose and tagged `cmdr`, `Odom fresh`; the Goal card's agent
row showing a single `drone_1` button; and the 3D view showing one drone marker, the geofence box
and a grid on the fence floor. `⏳ STE` — not seen yet.

**Healthy in the sim** (`cbf_sim.yaml`, three Isaac drones): mission chip `ON GROUND`, three
`IDLE` rows, three agent buttons. Three cosmetic oddities are **expected**: the banner may read
`0 sim · 3 real` (the sim stack publishes one `/fmu/` topic per drone, which the auto-detection
reads as "real" — set the panel's **Modes** setting to `sim,sim,sim` if it bothers you),
`LINK DEGRADED` (the derived ping is graded against a 20 ms LAN target the sim never meets) and
`EKF NO DATA` (no EKF topics in sim). None of them means anything is wrong.

With no host Studio you can run one *inside* the container, pre-connected with
`ground_control.launch.py use_foxglove_studio:=true` (default `false`).

## 3 · Reading the panel

### 3.1 · Banner chips

**LINK** (worst link state across agents) · **EKF** (worst estimator state across *real*
agents; hidden with no mocap/EKF topics) · **POWER** (worst return-to-base state) ·
`N sim · M real` · **Tasks** (what the panel inferred: goal-tracking, formation, teleop,
mocap/hardware, cellular — `detectedTasks` in `extension.js`) · the **Rosbag** switch and its
chip (§3.12) · a clock reading `k/N airborne · HH:MM:SS`. "Airborne" is just *z > 0.3 m* — not
an arming indicator.

### 3.2 · Safety bar

The red **`Safety Stop · Land All`** needs **two clicks within 4 s** (the first arms it, the
button counts down) and then calls `~/land`. Amber **`Hold All`** freezes every drone in
place via `~/hold`, single click (`onSafetyClick` / `renderSafety`). Both swarm-wide — and a
*convenience*, not a replacement for [PREFLIGHT.md](PREFLIGHT.md): the **kill switch (ch8)** is
still the only true motor cutoff, and `hold`/`land` leave the drone **armed**.

### 3.3 · Swarm Command card

**Takeoff**, **Start** (both behind a confirm dialog) and **Reset Fence** call `~/takeoff`,
`~/start`, `~/reset_fence` as `std_srvs/Trigger` on the commander namespace
(`SwarmCommander.handle_takeoff` / `handle_start` / `handle_reset_fence`). An unanswered call
reports `TIMEOUT` after **6 s** rather than hanging (`callWithTimeout`).

- **Mission chip** — fed **only** by `/svg/commander_status`, never by what the panel just
  sent: `ON GROUND` · `TAKING OFF` · `READY TO START` · `NOT READY` (some commanded drones
  still on the ground, so Start is refused) · `RUNNING` (with the scenario name and time since
  Start) · `HOLDING` · `LANDING` · `FENCE BREACH`, plus **`NO COMMANDER`** after 2 s of silence
  (`missionVerdict`).
- **Last-command chip** — the *commander's* own record of the newest lifecycle call
  (`✓ start 12:01:33` / `✗ start …`, reason on hover). Present even when the reply was lost.
- **Command log** — the last four commands sent from this panel, newest first: `sent, awaiting
  reply` → `reply: accepted / REJECTED / TIMEOUT / FAILED` → `✓ confirmed by commander` or
  `✗ NOT CONFIRMED` (`logCommand`, `verifyCommands`).

**The habit to build:** a lost reply is **not** a lost command — the panel confirms by
watching `command_seq` advance *and* the expected effect appear in the snapshot, so
`TIMEOUT` then `✓ confirmed by commander` means it ran. **The snapshot is the verdict**;
never click Takeoff twice because a reply was slow.

### 3.4 · Runtime gain row (was "CBF gain row")

A **dropdown** picks one of **six** live parameters (since the 2026-10-20 bump; the `param:`
entries of `TUNING_PARAMS` in `extension.js`):

| Dropdown entry | Parameter | Read from the snapshot's | Meaning in one line |
|---|---|---|---|
| CBF α | `cbf_alpha` | `cbf` block | how early the CBF yields — lower = earlier and gentler |
| CBF r | `cbf_safety_radius_m` | `cbf` | each drone's bubble; centres kept > 2r apart |
| CBF vmax | `cbf_max_speed_mps` | `cbf` | cap on every velocity the filter emits (= dodge authority) |
| Teleop vmax | `teleop_max_speed_mps` **and** `safe_teleop`'s `max_speed_mps` | `tuning` | hand-flown drone's speed at full stick; **Apply sets both nodes**, commander first; a `pad ✓/✗/--` readout says whether the pad agrees (§3.13, [TELEOP.md](TELEOP.md) §8) |
| Goal accel | `goal_accel_mps2` | `tuning` | acceleration *and* braking of the go-to-goal profile (no separate deceleration) |
| Goal settle | `goal_settle_s` | `tuning` | exponential tail into the goal; `0` allowed (no tail) |

Slider and number box share one draft per gain; **Apply** sends it via
`<commander>/set_parameters` (`setCbfParam`), **↻** re-reads all six with `get_parameters`
(`refreshCbfParams`). The fixed-width `live` readout is what the commander is actually running,
marked `✓` confirmed / `…` waiting / `✗` rejected-or-not-taken (`renderCbf`, `liveCbf`); a
rejection reason goes to the status line under the row. The commander validates (finite, > 0;
`goal_settle_s` may be 0) and applies on its next control tick ([SCENARIOS.md](SCENARIOS.md) §3).

**Slider ends are panel settings**, not limits: `cbfAlphaMax` 10, `cbfRadiusMax` 2 m,
**`cbfSpeedMax` 3 m/s**, `teleopSpeedMax` 5 m/s, goal accel 15 m/s², goal settle 2 s. So
`cbf_sim.yaml`'s **4.0 m/s** cap sits **past the end of the CBF vmax slider** — type it in the
number box, or raise `CBF max-speed slider max` in the panel settings. The number boxes accept
any positive value.

**Our values** with the real configs (`swarm_real_ours.yaml` / `goal_single_ours.yaml`,
[CONFIG.md](CONFIG.md)): `alpha 2.5` · `r 0.55 m` · `vmax 1.0 m/s` · teleop vmax `0.5` · goal
accel `3.0` · settle `0.3`. In the sim (`cbf_sim.yaml`): vmax **4.0**, accel **6.0** — **sim-only —
never port to the drone**.

Below the row, an activity line: red **`CBF EMERGENCY push-apart engaged`** (solver infeasible —
drones inside each other's safety spheres), amber **`CBF correcting drone_x`**, or a muted "not
correcting anyone". With one drone there is no neighbour to avoid: expect the muted line and
fence keep-in only.

### 3.5 · Formation row

A profile dropdown plus **Send**, publishing the name on `/svg/formation_command`. **Hidden
unless that topic exists** (`renderFormation`). Relevant to M7, not to one drone. The reserved
`next` verb is not exposed — send it from a shell ([SCENARIOS.md](SCENARIOS.md) §6).

### 3.6 · Goal card — with the agent picker (since 2026-10-20)

The card starts with a row of **agent buttons** (`drone_1` `drone_2` …, names only —
`buildAgentPicker`). The highlighted one is the agent the `x y z speed` fields edit and
**Send Goal** targets; the same selection highlights that drone's rows in Agent State / Link
Safety and its power card. Clicking a table row selects too. With our real configs there is
exactly one button, `drone_1`. **Use Current** copies the agent's current world-ENU position
into the fields; **Send Goal** publishes a `geometry_msgs/PoseStamped` (frame `map`) on
`/svg/{name}/goal_command` and, if a speed was typed, a `Float32` on `/svg/{name}/speed_command`
(`sendGoal`). Goals are in **world ENU** = odometry **plus** the commander's
`drone_position_offsets`, adopted straight out of the snapshot (`handleCommanderStatus`). Before
any snapshot the card's note says the frame is **unconfirmed** — believe it, and send no goals in
that state.

⚠️ **The trap:** goals only act while the commander runs the **`goal`** scenario. `cbf_sim.yaml`
ships `antipodal`, and `scenario:=random_goals` / `head_on` / `random_walk` all **silently ignore**
goal, speed and formation commands. For M4 use **`goal_single_ours.yaml`** (`drone_1`, `goal`,
our speeds); the shipped `goal_single.yaml` also runs `goal` on `drone_1` at `b21d28c` (it targeted
`drone_2` at `cf719f0`) but exempts it from the CBF and carries CMU's 10 m/s caps
([CONFIG.md](CONFIG.md)). `goal_tracking.yaml` ships `goal` again at `b21d28c` — at `cf719f0` it
shipped `random_goals`, which is where the old "goals do nothing" warning came from.

### 3.7 · Agents roster and Wiring card — REMOVED on the 2026-10-20 bump

The dev-branch panel has **no separate Agents roster and no Wiring card**: agent selection moved
into the Goal card (§3.6), and the mode decision (`/{name}/fmu/` ⇒ real, `/{name}/interface/`
⇒ sim) is shown on hover of each Agent State row's mode tag instead. To see which topics the
panel is actually watching, open the panel settings (gear): the *Wiring — sim* / *Wiring —
real* topic templates are there. What the `cf719f0` roster and Wiring card looked like is in the
appendix (§9, "the cf719f0 panel").

### 3.8 · Agent State table

Columns **Agent · State · x · y · z · Speed · Cmd stream · CBF · Interface · Odom** (`renderAgentTable`).

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
`/{name}/interface/velocity_command` and `/{name}/fmu/velocity_command` (the
`simCommandTopicTemplate` / `realCommandTopicTemplate` settings; the string `trajectory` appears
nowhere in `extension.js`), but this branch's commander defaults to `real_command_mode:
trajectory`, publishing `MultiDOFJointTrajectory` on `/{name}/fmu/trajectory_command`
(`SwarmCommander.publish_command`), and our `_ours` configs do not override it. So the column CMU
calls "the proof that the commander is driving it" likely sees no traffic for us. `⏳ STE` —
confirm at M3; if so use `State` + `Odom` plus `ros2 topic hz /drone_1/fmu/trajectory_command`
instead, or point the panel's **Velocity command** setting at that topic. (In the sim the column
works — sim drones take `velocity_command`.)

⚠️ **The Interface column is new on this branch and is NOT an arming indicator** — it shows
whether the commander's *request* was ACKed, not what PX4 did with it. Iron rule 5 stands:
the software is blind to PX4 arming state. **QGC remains the only trustworthy arming display.**

### 3.9 · Link Safety

A topology diagram plus a per-agent table: Path, Rate, Ping, **Drop**, Max gap, Mocap age,
EKF, Clock drift, State, **Bridge**. **Drop** carries a source tag (`ddsDropRatePct`,
`streamDropRatePct`, `renderLinkTable`): `dds` is genuinely **measured** (the commander's DDS
reader counts odometry samples lost by sequence number and publishes cumulative totals, which the
panel differences); `report` needs a `comms/link_status` publisher we don't run; `est` is an
arrival-timing guess — shown **muted** and never allowed to grade link health, because arrival
timing cannot tell a late sample from a lost one and the Foxglove bridge itself batches.

The **Bridge** column is an **inferred attribution of silence**, not a measurement — nothing
in the stack reports bridge health, so the panel reasons from which streams stopped
(`evaluateBridge`). A hint about *where* to look (MicroXRCEAgent vs `./mocap.sh` vs the drone),
never a fact. In the sim, `LINK DEGRADED` is normal (§2).

### 3.10 · Cellular · Tailscale VPN

**Hidden on our rig**, and should stay hidden: it needs a cellular or VPN topic to exist, and
we have no 4G/5G and no Tailscale. If it appears, something is publishing that shouldn't be.

### 3.11 · Battery & Power

One card per agent: SoC bar with ticks at the two return-to-base thresholds (`rtbNominalPct`
30, `rtbGatedPct` 20), pack voltage, draw, **sag** against the highest voltage seen this
session, mission time, and a distance-to-pad energy budget that fires `RTB NOW`. Its action
button is **Land All** behind a confirm — there is no per-agent land service. Real-hardware
SoC comes from `/{name}/fmu/out/battery_status`, blank in simulation.

### 3.12 · Rosbag switch (new 2026-10-20)

A toggle at the top right of the banner (right of the Tasks chip, beside the clock) that records
**every topic on the domain** to an mcap bag — the switchable form of `ground_control.launch.py
record_bag:=true`. It talks to the new `bag_recorder` node (`svg_ground_control/bag_recorder.py`),
started by `ground_control.launch.py` (`use_bag_recorder`, default true): on = `std_srvs/SetBool
data: true` on `/bag_recorder/record`, which spawns `ros2 bag record --all-topics --storage mcap`
at `<bag_dir>/<bag_prefix>_<YYYYmmdd_HHMMSS>` (default `bag_dir` = the bind-mounted
`~/AirStack/robot/ros_ws/bags`, so the bag is on the laptop; our compose also mounts
`AirStack/robot/bags` as `/bags`); off = `data: false`, a SIGINT so `metadata.yaml` gets
written (a bag killed hard is unreadable). The node also offers `~/start` and `~/stop` as
`std_srvs/Trigger`.

The switch follows the **recorder's own status** (`/svg/bag_recorder/status`, JSON at 2 Hz —
`renderBag`), not the last click: a bag started from a shell shows as on, and a recorder that dies
(disk full) drops it back to off with its exit code on the row.

| Element | What it shows |
|---|---|
| **Switch** | **Disabled until the recorder is heard from.** Held in the asked position and disabled while the recorder confirms (`STARTING…` / `STOPPING…`); springs back if the recorder refuses (unwritable `bag_dir`) with the reason in the status line; `NOT CONFIRMED` if the status topic never reflects the click |
| **Chip** | `NO RECORDER` (nothing on the status topic for 2.5 s — `bag_recorder` not running) · `IDLE` · red `REC 1:23 · 12.4 MB` (duration and size so far) · amber **`IDLE ✗`** (the last recording died on its own, or a start was refused) |
| **Tooltip** | the bag directory while recording; afterwards the recorder's summary of the last bag (`stopped: … (45 s, 120.3 MB)`) or why it stopped; `bag_dir` when idle |

The switch is banner chrome of the `main` / `full` instance — **hidden in the `power` and
`teleop` views**. Shell equivalent:

```bash
ros2 service call /bag_recorder/record std_srvs/srv/SetBool "{data: true}"    # start
ros2 service call /bag_recorder/record std_srvs/srv/SetBool "{data: false}"   # stop
ros2 topic echo /svg/bag_recorder/status --once
```

`record_bag:=true` on the commander launch records from launch to Ctrl-C, still switchable.
⏳ STE: not yet exercised by us.

### 3.13 · Teleop · Sticks card (new 2026-10-20)

The gamepad as `safe_teleop` sees it — the Foxglove form of `ros2 run svg_ground_control
teleop_monitor` ([TELEOP.md](TELEOP.md) §3, §5). It sits **to the right of the battery card in
the `power` instance** (alone in a `teleop` instance, in the right column of a `full` one, never in
`main`) and exists **only while `safe_teleop` is publishing** on `/svg/{name}/teleop_command` (20 Hz
whenever it runs, zeros included; 2 s of silence hides it again and the battery card widens back —
`renderTeleop`). A run with no hand-flown drone never shows it; `Sections = Show all` forces it on,
reading "Teleop off — safe_teleop is not publishing."

| Element | What it shows |
|---|---|
| **Joy chip** | `/joy 20 Hz` when `sensor_msgs/Joy` is arriving; red `NO /joy` / `STALE` otherwise (joy_node down or pad unplugged — `safe_teleop` publishes zero meanwhile) |
| **safe_teleop chip** | which drone(s) the stick velocity is streaming for, and at what rate |
| **Sticks chip** | whether the sticks reach the drone: green `STICKS LIVE → drone_1` (listed in `teleop_drones`, `ACTIVE`, Start called); amber `STICKS PARKED` with the reason (`press Start`, `not in teleop_drones`, `is ASCEND`); grey `NO COMMANDER` |
| **Sticks table** | four fixed-width rows — `fwd / back`, `left / right` (right stick), `up / down`, `yaw` (left stick). **Raw** = the `/joy` axis value as the driver reports it (−1 … +1); **Mapped** = what `safe_teleop` makes of it after its deadzone (inside `deadzone` reads 0, the rest rescaled so full deflection is still 1.0) and sign flip — the fraction of full stick the drone will fly, × `max_speed_mps`; then a centred bar |
| **Sticks table — hover and colours** | Hover a row for the `/joy` axis index and why it reads 0 (`inside the deadzone`, `LOCKED`, `axis missing` = the pad has fewer axes than the map → wrong `teleop_controller`). Mapped is greyed inside the deadzone, `locked` in amber when the lock is engaged, red when the axis is missing |
| **Lock line** | the lock button's state, whether the left stick is locked (mirrors `safe_teleop`'s edge-triggered latch from presses seen since the panel opened) and which controller profile the map came from |
| **Published** | `vx vy vz yaw` from the last `teleop_command`, each as a bar against `max_speed_mps` / `max_climb_speed_mps` / `yaw_rate_rad_s` (hover the title for topic and scales) |

The axis map, deadzone and speed scaling are read from `safe_teleop`'s own parameters
(`/safe_teleop/get_parameters` — `refreshTeleopParams`; the namespace is the `Teleop node
namespace` setting), so a DragonRise pad is drawn on its own layout. Until that read answers, the
`xbox_usb` defaults are assumed and the lock line says so. The raw joy topic is the `Joystick
(raw)` setting (`/joy`). The card is the quickest way to run TELEOP.md §5's ground check (sticks
move the right bars, zero at rest, unplug → zeros). `⏳ STE`

## 4 · The `/svg/commander_status` snapshot

The **new top-of-funnel diagnostic** on this branch: a `std_msgs/String` carrying JSON,
published at `status_rate_hz` (**5 Hz** default) by `SwarmCommander.build_status`. Almost
everything the panel asserts comes from here, so when the panel looks wrong read the snapshot
directly — in the **container**:

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
**`tuning{teleop_max_speed_mps, goal_accel_mps2, goal_settle_s, scenario_speed_mps}`** (new
2026-10-20 — the source for the dropdown's non-CBF gains, and what `safe_teleop` follows to keep
its `max_speed_mps` equal), plus `command_seq`, `last_command`, `stamp`, `node`, `pid`.

**`pid` has a purpose.** `takeover_twins` (default **true**) makes a second `ground_control`
launch read other commanders' snapshots and **kill the older one** 2 s after start-up —
*unless* it has a drone in a non-`IDLE` state, in which case it refuses and logs an error
(`SwarmCommander.takeover_twins`, `_on_twin_status`). A stray commander from a dead terminal
self-cleans; one with a drone in the air is never killed under you.

## 5 · The `view` setting and the two-instance layout

One panel, four shapes, chosen in its settings (gear → **View**) (`currentView` / `applyView`):

| `view` | Shows | Panel title |
|---|---|---|
| `full` | everything in one panel (the old single-panel form); the Teleop · Sticks card in its right column while teleop runs | SVG Basestation |
| `main` | everything **except** Battery & Power and Teleop · Sticks; cards stack in one full-width column | SVG Basestation |
| `power` | **only** Battery & Power, with its own power chip and clock — plus the Teleop · Sticks card beside the battery while `safe_teleop` publishes | SVG Battery & Power |
| `teleop` (new 2026-10-20) | **only** the Teleop · Sticks card, no banner; reads "Teleop off" while `safe_teleop` is silent (a Foxglove slot cannot remove itself — which is why the shipped layout uses `power` instead) | SVG Teleop |

The shipped `svg_basestation.json` uses **two instances**: `main` filling the left 50 %, a
`power` instance under the 3D view on the right (§1's picture). The Rosbag switch and the link /
task chips are banner chrome of `main` / `full` only. The 3D view's **built-in grid layer is
deliberately off** — a fixed 8 m square on the origin that never matches our fence. The commander
draws a world-aligned grid on the *fence floor* instead (`fence_grid_cell_m`, **0.5 m**), clipped
to the fence, inside `/svg/viz/markers` (`SwarmCommander._fence_grid_marker`). The drone marker is
an **Iris** mesh (`package://robot_descriptions/iris/…base_link_body_body.stl`, served through the
bridge's asset capability) — cosmetic, not our airframe; the Starling model lives only in Isaac Sim.

Studio config and imported layouts survive container recreation via the bind mount
`./Foxglove:/root/.config/Foxglove` (`volumes:` of
[`robot-base-docker-compose.yaml`](../AirStack/robot/docker/robot-base-docker-compose.yaml))
— but that is the **container's** Studio. A laptop Studio keeps layouts in its own Foxglove
profile, so re-import there after a panel update.

## 6 · Corrections to CMU's panel README for OUR rig

CMU's [`svg-basestation/README.md`](../AirStack/robot/ros_ws/src/svg_ground_control/foxglove/svg-basestation/README.md)
is the source of truth for the panel's internals. These points differ for us (code-checked
2026-10-07 at `cf719f0`, re-checked **2026-10-21** at `b21d28c`):

| CMU's README says | On our rig |
|---|---|
| Three drones in the demo | **One** real drone, `drone_1`. Our real configs (`swarm_real_ours.yaml`, `goal_single_ours.yaml`) list `drone_1` only, so the panel shows **one** agent button and **one** Agent State row — `0 sim · 1 real`, `0/1 airborne`. (The `cf719f0` panel's phantom-agent roster is gone — §9 appendix.) The shipped 3-drone files are M7 material |
| Mode is auto-detected from the wire (`/{name}/fmu/` ⇒ real) | True, and it works — but detection needs the drone's `fmu` topics to already be publishing. Before [RUNBOOK.md](RUNBOOK.md) §B's interfaces are up, an agent can read as neither. Set **Modes** to `real` if you want it pinned. In the **sim** the same rule misfires the other way (`0 sim · 3 real`, §2) — cosmetic; `Modes = sim,sim,sim` fixes the banner |
| `Cmd stream` is "~20 Hz while the commander drives it" and "the proof that Start reached the drone" | Only if commands go out as `velocity_command`. This branch defaults real drones to **`trajectory_command`**, which the panel does not subscribe to — expect `--` on the real drone (§3.8). Works in sim. `⏳ STE` |
| Cellular / Tailscale VPN section, 4G/5G path | **Not on our rig** — no cellular, no Tailscale. The section stays hidden, by design |
| The 3D view is "plus a 3D view", an extra | For us it **replaces RViz**, including the M2 hand-carry check. The `svg_drones.rviz` Fixed-Frame-`world` gotcha does not apply; this layout follows `map` |
| Services work on any data source | Disabled on a bag / file source (`servicesAvailable`): buttons grey out, the gain readout says `live -- (no services)`. Normal when reviewing a recording |
| Link health graded against the LAN ping target | In the **sim** that target (20 ms) is never met and no EKF topics exist, so `LINK DEGRADED` / `EKF NO DATA` are the normal sim banner (§2). Only meaningful on the real drone |
| Slider maxima | `cbfSpeedMax` defaults to **3 m/s**; our sim cap is **4.0** — use the number box or raise the setting (§3.4) |

Two notes on `AirStack/CHANGELOG.md`: its claim that the panel "moved from
`gcs/foxglove_extensions/`" is **not true against our previous snapshot** — it was never
there, it arrived with the 2026-10-07 branch. And it understates the gain row: all **six
runtime gains** are editable from the dropdown, not just alpha.

## 7 · Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Panel loads but everything reads `--` / sections missing | No publishers. Confirm the stack with `ros2 topic list` in the container; the banner's **Tasks** chip names what the panel did find. Setting **Sections → Show all** forces them visible but will not invent data |
| Mission chip stuck on `NO COMMANDER` | Nothing on `/svg/commander_status` for 2 s. Commander not up, or `status_rate_hz`/`status_topic` changed. Check with the §4 `echo` |
| Command log: `TIMEOUT` but then `✓ confirmed by commander` | The reply was lost, the command ran. **Do not resend** (§3.3) |
| Command log: `✗ NOT CONFIRMED` | The commander never recorded it. Check the commander's terminal for a rejection reason, and that there is only one commander (§4, `takeover_twins`) |
| `Cmd stream` reads `--` while the drone is clearly flying | Expected if `real_command_mode: trajectory` (§3.8). Verify with `ros2 topic hz /drone_1/fmu/trajectory_command` |
| Agent State x y z tagged `odom`, not `cmdr` | Snapshot is stale — the numbers are the panel's own odometry plus the **last** offsets it saw. Fix the commander/link before trusting positions or sending goals |
| Goal sent, nothing happens, no error | The commander is running a non-`goal` scenario (`cbf_sim.yaml`'s `antipodal`, or `scenario:=random_goals`), which ignores goal commands **silently**. Use `goal_single_ours.yaml` or `scenario:=goal` (§3.6) |
| `Odom` column says `STALE` | The **commander** is not getting fresh odometry, so it is commanding zero velocity. Chase mocap first: `./mocap.sh check` ([MOCAP.md](MOCAP.md) §5) |
| Gain Apply: "asked 0.80 but the commander still reports 2.50" | The set did not take. Read the status line under the row for the commander's reason (≤ 0, non-finite, or not a live parameter); `↻` re-reads |
| Teleop vmax row shows `pad ✗` in amber | `safe_teleop`'s `max_speed_mps` differs from the commander's `teleop_max_speed_mps`. Press **Apply** — it sets both. `pad --` just means `safe_teleop` is not running (normal without a hand-flown drone) |
| Rosbag chip `NO RECORDER`, switch greyed | `bag_recorder` is not running — launched with `use_bag_recorder:=false`, or the node died. `ros2 node list \| grep bag_recorder` in the container |
| Rosbag chip amber `IDLE ✗` | The last recording died on its own (disk full, unwritable `bag_dir`) or a start was refused — hover the chip for the reason |
| Teleop · Sticks card absent although the pad is plugged in | The card needs `safe_teleop` to be **publishing** `/svg/{name}/teleop_command` (20 Hz, zeros included) — start the pad launch ([TELEOP.md](TELEOP.md) §4/§5). `Sections → Show all` forces an empty card. `main` view never shows it: look at the `power` instance |
| Banner `0 sim · 3 real`, `LINK DEGRADED`, `EKF NO DATA` in the sim | Cosmetic (§2). Set **Modes** to `sim,sim,sim` for the first; the other two are the derived-ping grading and missing EKF topics |
| CBF vmax slider will not reach 4.0 | Slider max is the `cbfSpeedMax` setting (3). Type the value in the number box or raise the setting (§3.4) |

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

All paths relative to `AirStack/`. Sizes read 2026-10-21 at `b21d28c`.

| Piece | Location | Role |
|---|---|---|
| Installer | `…/svg_ground_control/foxglove/install.py` | copies any sibling dir with a `package.json` into `~/.foxglove-studio/extensions/<publisher>.<name>-<version>` |
| Layout | `…/foxglove/svg_basestation.json` | 176 lines: two panel instances (`main` + `power`) and the 3D view, with every topic template and threshold |
| The panel | `…/foxglove/svg-basestation/dist/extension.js` | ~3785 lines of plain JavaScript, **no build step** — editable in place, then re-run the installer and restart Studio. Landmarks: `TUNING_PARAMS` (the six gains), `activate` → `rebuildSubscriptions`, `handleCommanderStatus`, `renderMission`, `renderCbf`, `renderBag`, `renderAgentTable`, `renderLinkTable`, `renderTeleop`, `renderPower`, `applyView` |
| Smoke test | `…/svg-basestation/test/smoke.js` | drives the panel under a DOM stub (snapshot, odometry, Start/Hold/Apply incl. the two-node teleop cap, Rosbag) — `node --check dist/extension.js && node test/smoke.js` in a `node:20-alpine` container (CMU README, "Development") |
| CMU's manual | `…/foxglove/svg-basestation/README.md` | ~384 lines; read it for panel internals, with §6's corrections |
| Stale duplicate | `…/foxglove/svg-basestation/dist/nvm.js` | an **older copy** of the panel. Not referenced by `package.json` (`main: ./dist/extension.js`) but copied into every install. Harmless — just don't edit it by mistake |
| Bridge node | `…/svg_ground_control/launch/ground_control.launch.py` | `foxglove_bridge`, port **8765**, address `0.0.0.0`, `respawn=True`, `include_hidden` (`use_foxglove_bridge:=false` to skip) |
| Bag recorder | `…/svg_ground_control/svg_ground_control/bag_recorder.py` + the `bag_recorder()` block of `ground_control.launch.py` | `~/record` (SetBool), `~/start` / `~/stop` (Trigger), status JSON on `/svg/bag_recorder/status` at `status_hz` 2; params `bag_dir`, `bag_prefix`, `storage` mcap, `include_hidden`, `record_on_start` |
| Container install hook | `robot/docker/docker-compose.yaml` (`command:` block) | runs both Foxglove installers at container start (that Studio only) |
| Studio config persistence | `robot/docker/robot-base-docker-compose.yaml` (`volumes:`) | `./Foxglove:/root/.config/Foxglove` |
| Snapshot producer | `…/svg_ground_control/svg_ground_control/swarm_commander.py` | `SwarmCommander.build_status()` → `/svg/commander_status`, 5 Hz (`publish_status`) |
| Twin takeover | same file | `takeover_twins()` / `_on_twin_status()` — kills an idle older commander; refuses if its drone is airborne |
| Teleop speed sync | `…/svg_ground_control/safe_teleop/teleop_node.py` | `commander_status_callback` follows the snapshot's `tuning.teleop_max_speed_mps`; `push_max_speed` pushes a local set to the commander — what makes the panel's `pad ✓` true ([TELEOP.md](TELEOP.md) §8) |
| LED ground node | `…/svg_ground_control/svg_ground_control/led_controller.py` | udp/47901 heartbeat listener, `/svg/led_command`, `SetLedColor`, `/svg/cbf_active` → red |
| LED onboard daemon + provisioning | `…/svg_ground_control/scripts/svg_led_daemon.py`, `scripts/voxl_push_led.sh`, `scripts/voxl_setup_led.sh` | the VOXL-side `svg-led` service (11 RGBW pixels, mutes PX4's ESC LED bits) and the `scp`+`ssh` installer that puts it there |
| Our configs | `…/svg_ground_control/config/swarm_real_ours.yaml`, `goal_single_ours.yaml` | `drone_names` (`drone_1`), `drone_modes`, CBF gains, fence, `led_controller` block — [CONFIG.md](CONFIG.md) |

### Appendix — the `cf719f0` panel (2026-10-07 → 2026-10-20), for the archive

The first panel we vendored had a **CBF gain row** with three gains (α / r / vmax) instead of
the six-entry dropdown, no Rosbag switch, no Teleop · Sticks card, and `view` had three values
(`full` / `main` / `power`). It also had two cards the dev panel removed: an **Agents roster**
listing the configured agents — clicking one selected it, and the Goal and Wiring cards followed
— and a **Wiring** card that spelled out the resolved topics for that agent and how its mode was
decided (publishing under `/{name}/fmu/` ⇒ **real**, `/{name}/interface/` ⇒ **sim**), the first
place to look when a column was unexpectedly blank. With CMU's 3-drone `swarm_real.yaml` and one
real drone, that roster showed `drone_2` / `drone_3` as phantom agents with every cell `--`. Its
`extension.js` was 3220 lines, the layout 167, CMU's README 283. The pre-rewrite version of this
document (describing that panel in full) is in this repo's history: `git log -- docs/BASESTATION.md`.
