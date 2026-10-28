# RUNBOOK — start the pipeline fast

> **What this is:** the copy-paste command sequence for one session — simulation (§A), the
> real drone (§B), goal flights (§C), post-flight logs (§D).
> **Who should read it:** anyone whose machine is already set up (README → "Setting up AirStack
> on a NEW machine") and who just wants to **run** things. No background, no debugging — that
> lives in the project pages ([MILESTONES.md](MILESTONES.md) is the index) and
> [TROUBLESHOOTING.md](TROUBLESHOOTING.md) (symptom → fix).
> Every code block says where it runs. **Never paste across a `connect` line** — it opens a
> new shell and swallows what follows.
>
> ⚠️ **Branch note (2026-10-21):** this runbook describes CMU's `yikuan/SVG_ground_control_dev`
> @ `b21d28c` (vendored 2026-10-20 — [MIGRATION.md](MIGRATION.md) §11; the release line
> `yikuan/SVG_ground_control` @ `cf719f0` was our 2026-10-07 snapshot). **Sim (§A) is validated
> in part** — ledger in [record/LEDGER.md](record/LEDGER.md). **No real flight on this branch
> yet:** §B/§C were last flown on the *previous* branch (2026-09-01→03) and stay **⏳ STE until
> re-validated**. What changed for a pilot: [MIGRATION.md](MIGRATION.md) §5.

*(Unfamiliar term? → [GLOSSARY.md](GLOSSARY.md))*

**Prompt rule:** `jeremychia@…$` = laptop · `root@…#` = inside the robot container (the docker
container that holds the ROS 2 workspace) · `starling2-max…$` = on the drone (adb/ssh) ·
`root@…:/exploration#` = the exploration container (camera-world runs — [localisation/README.md](../localisation/README.md)).

**Two ways into the containers.** Pick one per session:

| Way | Laptop command | What opens | Use it for |
|---|---|---|---|
| **Sim session (tabs)** | `~/AirStack-starling-max2/tools/sim_terminals.sh` | ONE Terminator window, four tabs — **Isaac Sim · Interfaces · Commander · Cockpit** — each already inside its container, each printing its own commands | the sim (§A) |
| **tmux `bringup` session** | `cd ~/AirStack-starling-max2/AirStack && ./airstack.sh connect robot` | the container's tmux session: **8 panes** — pane 0 top-left, 1–4 across the top, 5–7 along the bottom — every one a container shell with the workspace sourced | the real drone (§B/§C); §A without Terminator |

tmux moves: `Ctrl-b` then an arrow key switches panes; `Ctrl-b d` detaches; the session
survives closing the terminal (`connect` again to return). One long-running thing per
tab or pane. §B/§C say "pane N"; §A says "<name> tab".

---

## A · Fly in SIMULATION — sim validated in part on this branch ([record/LEDGER.md](record/LEDGER.md))

> **WORLD: SIMULATION — nothing on this page touches the drone.** Step 0, before anything else: the drone's battery is OUT and `./mocap.sh` is NOT running on the laptop (the sim shares DDS domain 1 and the `/drone_1` topic names with the real drone). ⚠️ Sim-only — never port to the drone: the sim airframe values and `cbf_sim.yaml` speeds/landing settle (iron rule 9).

GPU required. Four long-running things, one per tab — Isaac spawn · interfaces (MAVROS) ·
commander · cockpit; the panel is the operator view (why: [ARCHITECTURE.md](ARCHITECTURE.md#sim-session-anatomy)).

**What success looks like:** [videos/random_CBF_sim_edited.mp4](../videos/random_CBF_sim_edited.mp4)
— three Starling 2 Max models flying `random_goals` under the CBF in Isaac Sim, 2026-10-21 ·
camera world: [localisation/README.md](../localisation/README.md)
(`cbf_sim.yaml`: 2.0 m/s cruise, cap 4.0, r 0.55, α 2.5; a 47 s excerpt of a 3.5 min run).

### A0 — open the session (one command)

Laptop:
```bash
~/AirStack-starling-max2/tools/sim_terminals.sh
```
Opens ONE Terminator window, four tabs, each already inside its container (brings the
containers up first if needed). Work left to right: **A1 = Isaac Sim tab, A2 = Interfaces
tab, A3 = Commander tab, A4 = Cockpit tab.** Keep the window open (why:
[ARCHITECTURE.md](ARCHITECTURE.md#sim-session-anatomy)).

> **No-terminal variant for the hover + 1 m step acceptance only:** `tools/sim_hover_step_run.sh all` runs A1–A4 for that one test from the laptop and writes `docs/record/<run>_record.md` — see [tools/README.md](../tools/README.md). Everything else in §A is done in the tabs.

### A1 — Isaac Sim tab: spawn the sim drones

Paste as one block (Starling 2 Max model, Isaac window on):
```bash
DRONE_USD=/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd PX4_VEHICLE_MODEL=pegasus_starling2max NUM_ROBOTS=3 SVG_DOMAIN_ID=1 PLAY_SIM_ON_START=true ISAAC_SIM_HEADLESS=false PYTHONPATH="$ISAAC_SIM_PYTHONPATH" /isaac-sim/python.sh /isaac-sim/AirStack/simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py --ext-folder ~/.local/share/ov/data/documents/Kit/shared/exts
```
Wait for `Ready for takeoff!` ×3. Leave running.

Variants: no Isaac window → `ISAAC_SIM_HEADLESS=true` · CMU's Iris quad → drop `DRONE_USD=…`
and `PX4_VEHICLE_MODEL=…` · ZED camera / construction-site world / 72 ms motor lag → [§ Sim launch variants](#sim-launch-variants).

`DRONE_USD` + `PX4_VEHICLE_MODEL` select CMU's sys-ID Starling model and our bind-mounted PX4
airframe; what in it is real and what is sim-only: [CONFIG.md](CONFIG.md#sim-airframe-starling-2-max-sim-only--10090_pegasus_starling2max) "Sim airframe".

⚠️ Everything marked **sim-only — never port to the drone** stays in the sim (iron rule 9) — so
do `cbf_sim.yaml`'s speeds 2.0 / 4.0 / 6.0 and its landing settle 2.0 s + disarm retry (the real
`_ours` configs fly `drone_1`, `land_settle_s` 0.0, `land_speed_mps` 0.6, `cbf_max_speed_mps` 1.0).
The drone's parameters come from `starling_1_indoor_params.params` via QGC.

Validation: [record/LEDGER.md](record/LEDGER.md) (state + acceptance tools: [CONFIG.md](CONFIG.md#sim-airframe-starling-2-max-sim-only--10090_pegasus_starling2max) "Sim airframe").

> ⚠️ **Never press Stop / Play in the Isaac window** to reset the drones (observed 2026-10-20):
> Pegasus kills and relaunches PX4 but leaks the old vehicles' physics callbacks, the new PX4s
> never connect, and the whole stack has to be restarted — [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
> The only reset is Ctrl-C + relaunch of this script, then the Interfaces and Commander tabs.
> To bring landed drones back to their pads without a restart: `hold` → formation `home` →
> `land` — this works **only** under `scenario:=goal`.

### A2 — Interfaces tab: one MAVROS per drone

After `Ready for takeoff!` ×3:
```bash
./src/svg_ground_control/scripts/launch_sim_interfaces.sh 3
```
Leave running (you are already in `~/AirStack/robot/ros_ws`, workspace sourced — why:
[ARCHITECTURE.md](ARCHITECTURE.md#workspace-build-and-sourcing)).

- **Rebuild** (`bws && sws`) only after NEW entry points or files (e.g. a snapshot bump);
  `.py`/`.yaml` edits need none (why: [ARCHITECTURE.md](ARCHITECTURE.md#workspace-build-and-sourcing)).
- **MAVROS respawn (sim-only — never port to the drone):** a MAVROS node that dies comes back after 2 s, but PX4 has
  meanwhile dropped to its offboard-loss failsafe. Recovery, in the Cockpit tab:
  `ros2 topic echo /drone_N/interface/mavros/state --once`; if `mode` ≠ `OFFBOARD`:
  `ros2 service call /drone_N/interface/mavros/set_mode mavros_msgs/srv/SetMode "{custom_mode: AUTO.LAND}"`,
  then the commander's `land`.

### A3 — Commander tab: the commander + the panel

```bash
ros2 launch svg_ground_control ground_control.launch.py config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/cbf_sim.yaml scenario:=random_goals use_foxglove_studio:=true
```
Leave running.

- `scenario:=` overrides the yaml's own `antipodal`. Choices: `hover`, `goal`, `random_walk`,
  `random_goals`, `head_on`, `antipodal`, `squeeze`, `goal_sequence`, `figure_eight` —
  catalogue in [SCENARIOS.md](SCENARIOS.md) §4.
- `use_foxglove_studio:=true` = Studio inside the container, already connected. First time
  only: import the layout — paths, the laptop-Studio alternative and what "healthy" looks
  like: [BASESTATION.md](BASESTATION.md#2--quick-start) §2.
- The launch also starts the `bag_recorder` node (since 2026-10-20); add `record_bag:=true`
  to record the whole run, or use the panel's Rosbag switch mid-run
  ([BASESTATION.md](BASESTATION.md) §3.12).
- **Speeds:** `cbf_sim.yaml` flies 2.0 m/s cruise with a 4.0 m/s CBF cap and 6.0 m/s² goal
  accel — **sim-only — never port to the drone**; the real `_ours` configs stay at 1.0 m/s.

### A4 — Cockpit tab: fly

One call at a time — or the panel's buttons, which call the same services:
```bash
ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger   # arm + climb; wait for "holding takeoff position" ×3 (~30 s)
ros2 service call /swarm_commander/start   std_srvs/srv/Trigger   # scenario live
ros2 service call /swarm_commander/hold    std_srvs/srv/Trigger   # freeze in a hover (also the PANIC button)
ros2 service call /swarm_commander/land    std_srvs/srv/Trigger   # land from the hover — never mid-leg
ros2 topic echo /drone_1/interface/mavros/state --once           # expect armed: false
```
Expected landing log in the Commander tab, per drone: `touchdown at z=… settling 2.0 s
before disarm` then `landed, disarmed (attempt 1)`. If PX4 refuses, up to 5 retries 1 s
apart, then ERROR `disarm not accepted after 5 tries` → see the MAVROS note in A2 and
[TROUBLESHOOTING.md](TROUBLESHOOTING.md). (The 2.0 s settle and the retry are **sim-only — never
port to the drone**; the real `_ours` configs set `land_settle_s` 0.0.)

**Live parameters** (no relaunch): `ros2 param set /swarm_commander scenario_speed_mps 1.0`
— the live list is in [SCENARIOS.md](SCENARIOS.md) §3 and §C8 below.

**Fence latched** (`FENCE BREACH` chip, drones frozen — `hold_all` configs)? → `land`, then
`ros2 service call /swarm_commander/reset_fence std_srvs/srv/Trigger` (or the panel's **Reset
Fence**), then `takeoff` + `start` again. `keep_in` configs never latch — the drone brakes at
the wall instead.

### Alternatives to the tabs

tmux instead of Terminator — same commands. Laptop:
```bash
cd ~/AirStack-starling-max2/AirStack && ./airstack.sh up && ./airstack.sh connect isaac-sim --command=bash
```
→ run A1 there. New laptop terminal: `cd ~/AirStack-starling-max2/AirStack && ./airstack.sh connect robot`
→ tmux `bringup`: pane 1 = A2 (after `cd ~/AirStack/robot/ros_ws`), pane 2 = A3, pane 3 = A4.
`Ctrl-b d` detaches; `connect robot` again re-attaches. One-command teleop session, RViz
fallback and the throw-away shell: [§ Sim launch variants](#sim-launch-variants).

*Optional fifth terminal* (laptop, not a tab — Ctrl-Shift-T is fine): `localisation/scripts/slam_up.sh` after
`Ready for takeoff!` ×3 starts the SLAM side of a camera-world run ([localisation/README.md](../localisation/README.md)).

---

## B · REAL DRONE session (mocap room) — ⏳ STE on this branch

> **WORLD: REAL DRONE — [PREFLIGHT.md](PREFLIGHT.md) gates every takeoff.** Gates before the next real flight: [MILESTONES.md](MILESTONES.md) "Before the next real flight" (MAV_SYS_ID 1 vs 2, one watchdog only, [PX4_MSGS_AUDIT.md](PX4_MSGS_AUDIT.md) ACK audit, NEAR-826 landing test); props-off kill test: [PREFLIGHT.md](PREFLIGHT.md) / [DRONE_SETUP.md](DRONE_SETUP.md) §8 (NEAR-823); mocap chain after the camera upgrade: [projects/HTX-R2.md](projects/HTX-R2.md) R1.
>
> **Step 0 — which world am I in:** Isaac container NOT running (`docker ps | grep isaac` → empty), no `mavros_node` and no `svg_teleop` in `ros2 node list`, and the `px4_interface … target_system=N` startup line present. ⚠️ Never start Isaac Sim during a real session: the sim publishes on the real drone's topic names.

> **Where things run:** laptop `jeremychia@…$` = steps 0 (ssh), 1, 2 (`up`), 3b, 4, 7 (host Studio) ·
> container pane `root@…#` = steps 3, 5, 6, 8 + verify commands · drone `starling2-max…$` = provisioning, shutdown.
> `ros2: command not found` ⇒ host shell; `./mocap.sh` complaining about ROS ⇒ container — swap.
> Full table: [ARCHITECTURE.md](ARCHITECTURE.md#where-things-run-real-drone-session).

> **Maturity (2026-10-07):** nothing in §B has run on this branch yet. The mocap chain
> (steps 1, 3b, 4) is unchanged from the previous branch. Steps 0, 5, 6, 7 are changed —
> read them, don't skim. One-time drone work (new provisioning script, watchdog decision):
> NEAR-818–823 ([projects/HTX-R2.md](projects/HTX-R2.md)). No Isaac Sim needed — do NOT start it.

**0 — Re-provision the drone(s)** — needed once per drone every time the GC laptop (or its
IP) changes, **and once after switching to this branch** (why: [DRONE_SETUP.md](DRONE_SETUP.md#4--point-px4-at-the-laptop-uxrce-dds-provisioning) §4). The drone
*dials the laptop*, so a stale IP means step 3 never gets a session. Laptop:
```bash
ssh root@<DRONE_IP>            # Starling 1 — IP + password in CONFIG.md
```
Then, on the drone. `<LAPTOP_IP>` = **the laptop's `wlp…` address on the drone segment
(`10.40.2.107`)** — same subnet as the drone. Get today's value from step 1's
`ip -4 -brief addr`; confirm the drone can `ping` it before you fly:
```bash
voxl_setup_real_drone.sh <BODY_NAME> <LAPTOP_IP> <DOMAIN_ID> <AGENT_PORT>
# Starling 1:  voxl_setup_real_drone.sh drone_1 <LAPTOP_IP> 1 8888
reboot                         # ⚠️ ALWAYS reboot — never `systemctl restart voxl-px4` on this airframe (it kills the flight core)
```
Arguments (`<BODY_NAME>` / `<DOMAIN_ID>` / `<AGENT_PORT>` — the port must match step 3's agent)
and the `adb push` of the new script: [DRONE_SETUP.md](DRONE_SETUP.md#4--point-px4-at-the-laptop-uxrce-dds-provisioning) §4.
Skip this step if nothing changed since the last session **on this branch**. Unsure?
Proceed to step 3 — `session established` means step 0 wasn't needed.
⚠️ **First time on this drone?** [DRONE_SETUP.md](DRONE_SETUP.md).

**1 — Check today's IPs** (everything is DHCP; addresses drift). Laptop:
```bash
ip -4 -brief addr              # every interface + its IPv4, one line each
ping -c2 <MOTIVE_IP>           # Motive PC answers (hangar wired LAN) — current value: CONFIG.md network table
ss -ulpn | grep -E ':(1510|1511)' || echo "ports clear"
```
Ports NOT clear → `./mocap.sh stop` (laptop) then re-check; full table:
[TROUBLESHOOTING.md](TROUBLESHOOTING.md).
Compare against **[CONFIG.md](CONFIG.md)** (source of truth for every IP/SSID/name). `enp…`
(`192.168.9.x`) = mocap path · `wlp…` (`10.40.2.x`) = drone segment. Finding the drone's IP,
its SSID, WiFi missing after reboot: [TROUBLESHOOTING.md](TROUBLESHOOTING.md#drone-side--network) rows.

**2 — Stack up (robot container only).** Laptop:
```bash
cd ~/AirStack-starling-max2/AirStack
./airstack.sh up robot-desktop
./airstack.sh connect robot          # → tmux "bringup", 8 panes, prompt root@…#
```
Pane 0, only after NEW entry points or files (e.g. right after a snapshot bump):
`cd ~/AirStack/robot/ros_ws && bws && sws` (why, and why `.py`/`.yaml` edits need no rebuild:
[ARCHITECTURE.md](ARCHITECTURE.md#workspace-build-and-sourcing)). Every container step below names a pane.
⚠️ If this container was created **before** the branch switch, recreate it once
(`./airstack.sh down` first) — the new `/dev/input` and `./Foxglove` mounts only exist on a
fresh container ([MIGRATION.md](MIGRATION.md) §6).

**3 — Agent** (the drone link). Pane 1:
```bash
MicroXRCEAgent udp4 -p 8888 -v4
```
Wait for `session established`. Leave running. Verify in pane 4:
```bash
ros2 topic hz /drone_1/fmu/out/vehicle_status              # want ~30 Hz
ros2 topic echo /drone_1/fmu/out/vehicle_odometry --qos-reliability best_effort --once
```
⚠️ Every `/fmu/*` **echo** needs `--qos-reliability best_effort` or it looks dead — but this
container's `ros2 topic hz` does NOT accept that flag (run hz bare). `vehicle_status` echo
prints nothing even though hz shows 30 Hz — use `vehicle_odometry` for the echo check (why:
[CONFIG.md](CONFIG.md#protocol-constants-change-only-if-deliberately-reconfigured-everywhere) "Protocol constants").

**3b — QGroundControl** (battery, arming status, params, kill switch). **Laptop** terminal
(NOT a container shell), its own window — leave running:
```bash
~/QGroundControl-x86_64.AppImage
```
No vehicle appears? The drone pushes MAVLink to the GCS IP configured on it
(`voxl-mavlink-server.conf`, see CONFIG.md) — it must point at this laptop.

**4 — Mocap bridge** (why `./mocap.sh` and not the stock driver: [MOCAP.md](MOCAP.md),
[ARCHITECTURE.md](ARCHITECTURE.md#mocap-receiver-note)). *Prereq: the
`drone_1` rigid body exists in Motive BEFORE launching — the body list is read only at
startup.* **Laptop** terminal (NOT a container shell):
```bash
cd ~/AirStack-starling-max2 && ./mocap.sh      # this repo's root
```
Leave running. Verify (pane 4): `ros2 topic hz /drone_1/pose` (Motive's rate — 50 Hz as of
2026-08-28). Poses missing → `./mocap.sh check` (laptop) names the culprit.

**5 — Per-drone interfaces** (turns `/fmu` traffic into the odometry the commander needs —
without this the Basestation shows no odometry and takeoff is refused). Pane 2:
```bash
ros2 launch svg_ground_control real_interfaces.launch.py drones:=drone_1   # more drones: drones:=drone_1,drone_2 target_systems:=1,2
```
**New on this branch:** the startup line must read
`[drone_1.fmu.px4_interface]: PX4Interface initialized (uXRCE-DDS), target_system=N`. That
number must equal the drone's `MAV_SYS_ID` (⏳ **read `MAV_SYS_ID` back in QGC before the first arm** — the 2026-09-04 params export says **1**, a 2026-09-18 session note on this airframe says it was set to **2**; whichever it is, `target_systems:=` must match) or PX4 silently drops every
arm/takeoff/land command — no error anywhere, just no ACK ([MIGRATION.md](MIGRATION.md) §5).
Leave running. Verify (pane 4):
```bash
ros2 topic hz /drone_1/odometry_conversion/odometry   # silent here = takeoff will be refused later
```

**6 — Commander launch.** Use **our** config `swarm_real_ours.yaml`, never the shipped
`swarm_real.yaml` (which config and why, what the launch starts, one-time prereqs:
[CONFIG.md](CONFIG.md#ground-side-flight-parameters-svg_ground_control-config-yamls) "Which config for what"). Pane 3:
```bash
ros2 launch svg_ground_control ground_control.launch.py \
  config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/swarm_real_ours.yaml \
  use_mocap:=true use_foxglove_studio:=true
```
`use_foxglove_studio:=true` opens Foxglove Studio inside the container already pointed at the
bridge; leave it off if you run Studio on the laptop (step 7).
On launch expect: a WARN that `drone_position_offsets` are all zero (**correct for mocap**),
`LED daemon` warnings if no strip is fitted (harmless, or add `use_led:=false`), and
`foxglove_bridge` listening on 8765. If a previous commander is still alive the new one
**takes it over** (`takeover_twins`) unless the old one has a drone airborne. Leave running.

**Verify fusion** (pane 4). ⚠️ Copy-paste these — arrow-key-editing `in/` into `out/`
keeps producing a nonexistent `/fmu/inout/…` topic:
```bash
ros2 topic hz   /drone_1/fmu/in/vehicle_visual_odometry     # ~mocap rate = mocap_bridge alive
ros2 topic echo /drone_1/fmu/out/vehicle_odometry --once --qos-reliability best_effort --qos-durability volatile
ros2 topic echo /svg/commander_status --once                 # NEW: state, odom_fresh, fence, last command — in one message
```
The `in/…` message shows velocities as `.nan` — **by design**. **Success = `out/…`
position matches `in/…` to within a few cm** (EKF2 is fusing) and the status JSON shows
`drone_1` with `"odom_fresh": true`, `"state": "IDLE"`. Then the **frame hand-check**
(before the day's first flight): carry North → `position[0]`↑, East → `[1]`↑, up → `[2]`↓.

**7 — Basestation preflight (no arming) — replaces the RViz check.** Open Foxglove Studio:
either **laptop** Studio → `ws://localhost:8765`, or add `use_foxglove_studio:=true` to the
step 6 launch (opens Studio inside the container). Import the layout the first time
([BASESTATION.md](BASESTATION.md) §2). Healthy = banner `EKF EV FUSED`, mission chip
`ON GROUND`, Agent State row for `drone_1` reads `IDLE · odom fresh · x y z tagged cmdr`,
and the drone mesh in the 3D view **follows the hand-carried drone**. Step 5 must be
running or the row says `odom none`. Do NOT call takeoff during this check. Phantom rows,
RViz fallback: [BASESTATION.md](BASESTATION.md#7--troubleshooting) §7.

**8 — Fly** (⏳ STE on this branch — NEAR-825 ([projects/HTX-R2.md](projects/HTX-R2.md))). ⚠️ Do not call `takeoff` until every
box on [PREFLIGHT.md](PREFLIGHT.md) is checked and a briefed safety pilot holds the
transmitter. Pane 4 (the "cockpit") — one call at a time — **or the Basestation buttons**
(Takeoff and Start ask for confirmation; Safety Stop needs two clicks within 4 s):
```bash
ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger   # arm + climb + hold
ros2 service call /swarm_commander/start   std_srvs/srv/Trigger   # scenario live
ros2 service call /swarm_commander/hold    std_srvs/srv/Trigger   # PANIC: brake to a stop point ahead, hold there
ros2 service call /swarm_commander/land    std_srvs/srv/Trigger   # descend + disarm
```
In hover, confirm the setpoint stream from a pane: `ros2 topic hz /drone_1/fmu/trajectory_command` ≈ 20 Hz (the panel's `Cmd stream` column watches velocity topics only and reads `--` on a real drone — [BASESTATION.md](BASESTATION.md) §6).
`start` begins the scenario and is **REQUIRED** before goals or teleop respond. Hover about 20 s before `land`; at touchdown on this software the Interface column shows `disarm ✗` and QGC one red "Disarming denied" until the landing test (NEAR-826) is re-observed — expected, not a fault.
Watch the panel's command log: `sent → accepted → ✓ confirmed`, and the Interface column:
`request offboard ✓ · arm ✓`. **`DENIED`** = PX4 refused (preflight) · **no entry at all** =
`target_system` mismatch — fix before retrying. Goal/waypoint flights → **§C**. Gamepad →
[TELEOP.md](TELEOP.md) §5.
⚠️ Safety status: RC kill switch mapped + tested on the previous branch (2026-09-01) —
**repeat the props-off kill ground test** before the first flight on this branch
([DRONE_SETUP.md](DRONE_SETUP.md) §8). Every flight: fence fits the net, thumb on kill,
QGC visible.

**Shutdown** (either session type). Ctrl+C each tab's or pane's launch (in tmux, `Ctrl-b d`
to leave it), then laptop:
```bash
cd ~/AirStack-starling-max2/AirStack && ./airstack.sh down
```

**Drone shutdown** (real-drone sessions — power down cleanly, don't just yank the battery).
Laptop, USB-C connected:
```bash
adb shell shutdown now
```
Wait ~10 s, then unplug USB and disconnect the battery. (Already in the drone's own shell —
`starling2-max` prompt? Just `shutdown now` there. NOT in a laptop or container shell.)

---

## C · GOAL FLIGHTS (fly to commanded waypoints) — ⏳ STE on this branch (NEAR-829–832, [projects/HTX-R2.md](projects/HTX-R2.md))

> **🚨 EMERGENCY** — `ros2 service call /swarm_commander/hold  std_srvs/srv/Trigger`
> · `ros2 service call /swarm_commander/land  std_srvs/srv/Trigger`
> · panel: **Hold All** / **Safety Stop · Land All** (two clicks)
> · **KILL = ch8 on the RC — instant motor cut**
> · **takeover = flip ch6 to MANUAL, never Position/Altitude**

Same session bring-up as §B steps 0–7 — **only step 6's config changes**. ⚠️ The shipped
goal configs are **not usable as-is on our rig** ([MIGRATION.md](MIGRATION.md) §7):

| Config | Shipped as | What to do |
|---|---|---|
| `swarm_real.yaml` | 3 real drones, hover scenario, `hold_all` fence, z 1.2 m | use **`swarm_real_ours.yaml`** (`drone_1`, z 0.5, `land_speed_mps` 0.6, ±2 m fence) — the §B hover config |
| `goal_single.yaml` | `drone_1`, `goal` scenario, **`drone_1` CBF-exempt** (filter off), `keep_in` fence `[-4.5,-5.2,0]..[5.5,4.5,3.0]`, teleop fence on, `cbf_max_speed_mps` **10.0**, `land_speed_mps` 0.8 (targeted `drone_2` at `cf719f0`; `drone_1` since the 10-20 bump) | use **`goal_single_ours.yaml`** (`drone_1`, ±2 m fence, speeds 1.0, `goal_accel` 3.0, `keep_in` brake 4 / gain 2, `land_speed_mps` 0.6) — the §C config |
| `goal_tracking.yaml` | 3 real drones, `goal` scenario (`random_goals` at `cf719f0`; `goal` again since the 10-20 bump), `keep_in`, 10 m/s | not for one drone — M7 material ([SCENARIOS.md](SCENARIOS.md) §6–7) |

Both `*_ours.yaml` files live beside CMU's under
`AirStack/robot/ros_ws/src/svg_ground_control/config/` (rules in C7); any change to them
goes into [CONFIG.md](CONFIG.md).

**C1 — Launch.** Pane 3 (replaces step 6's launch command):
```bash
ros2 launch svg_ground_control ground_control.launch.py \
  config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/goal_single_ours.yaml \
  use_mocap:=true use_foxglove_studio:=true
```

**C2 — Fly.** Takeoff (climbs to `hover_positions` — BOTH the takeoff target AND the initial
goal), then `start`, then publish waypoints — from the Basestation's **Goal card** (select
`drone_1`, type x y z, Send Goal; its frame note must read `commander`, not "unconfirmed")
or from pane 4. Before takeoff, place the drone on the floor at/near the config's
`hover_positions` x,y — takeoff flies to that ABSOLUTE point.
```bash
ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger
ros2 service call /swarm_commander/start   std_srvs/srv/Trigger
ros2 topic pub --once /svg/drone_1/goal_command geometry_msgs/msg/PoseStamped \
  "{header: {frame_id: map}, pose: {position: {x: 0.5, y: 0.0, z: 1.0}}}"
ros2 topic pub --once /svg/drone_1/speed_command std_msgs/msg/Float32 "{data: 0.8}"
```
- Coordinates are **ABSOLUTE** in the mocap/world frame (same numbers as `/drone_1/pose`).
- Each publish **REPLACES** the goal — no queue. The publisher exiting does NOT cancel it.
- **New:** the drone flies an acceleration-limited profile (`goal_accel_mps2`) and PX4
  holds the position onboard — expect a crisper stop than the old branch, and a
  `speed_cap_note` in the commander log if the requested speed cannot be reached.
- **New:** `/svg/drone_1/goal_xyzt` (`Float64MultiArray [x,y,z,theta_deg]`) also sets the
  heading; otherwise the nose stays on +X.
- Keep goals inside the fence. Goals only act under the `goal` scenario.

**C3 — Square / multi-goal loop.** Pane 4, after C2's takeoff + start:
```bash
G() { ros2 topic pub --once /svg/drone_1/goal_command geometry_msgs/msg/PoseStamped "{header: {frame_id: map}, pose: {position: {x: $1, y: $2, z: $3}}}"; }
for lap in 1 2; do for c in "-0.5 -0.5" "0.5 -0.5" "0.5 0.5" "-0.5 0.5"; do G $c 1.0; sleep 5; done; done
ros2 service call /swarm_commander/land std_srvs/srv/Trigger
```
What success looked like on the previous branch: [drone POV](../videos/Starling_goal_tracking_drone.mp4)
· [RViz POV](../videos/Starling_goal_tracking_RVIZ.mp4) (2026-09-03).

**C4 — Fence: two behaviours now** ([TELEOP.md](TELEOP.md) §6). `fence_behavior` in the
config decides:
- **`hold_all`** (default, `swarm_real.yaml`): breach ⇒ **ALL drones freeze-hover in place
  — still ARMED, not a motor cut.** Recover: `land` → `/swarm_commander/reset_fence` →
  `takeoff` → `start`. ⚠️ Now also latches when an **RC-flown** drone is airborne outside
  the box.
- **`keep_in`** (`goal_single`, `goal_tracking`): nobody freezes — the drone **brakes
  before the wall** (`fence_brake_accel_mps2`) and is pushed back inside if already out;
  `fence_breached` stays false; `reset_fence` is never needed. Only ACTIVE drones are
  clipped (landing may cross the floor). **M4 wall test:** goal 0.5 m past the wall at low
  speed, measure the overshoot.

**C5 — Landing / disarm.** `land` descends at `land_speed_mps`. On touchdown the commander
waits `land_settle_s`, then sends DISARM; if PX4 refuses it retries up to
`land_disarm_retries` times, `land_disarm_retry_s` apart (log: `touchdown at z=… settling …`
→ `landed, disarmed (attempt N)`). PX4's own land detector + auto-disarm remain the backstop.
- Our `_ours` configs set **`land_settle_s: 0.0`** — the landing exactly as flown
  2026-09-03 (immediate disarm). CMU's shipped real configs do **not** set it and inherit
  the code default **2.0 s** — one more reason to fly `_ours`. Re-check the settle at M3.
- On the real drone the interface answers `success` on *send*, not on PX4's ACK, so the
  retry only ever fires in sim and the log says `landed, disarmed` whether or not PX4
  obeyed. ⚠️ ALWAYS confirm **DISARMED** in QGC before approaching.
- Our validated `land_speed_mps` is **0.6** (0.3 left the drone armed on the ground); the
  shipped configs carry **0.3** (`swarm_real`, `teleop_real`), 0.8 (`goal_single`) or 1.0
  (`goal_tracking`, `goal_sequence`) — set 0.6 in every config you fly.

**C6 — RC takeover rules** (previous-branch forensics; re-test at M3). While the commander
runs, its setpoints leak into POSCTL/ALTCTL — takeover is ONLY clean flipping straight to
**MANUAL**, or the **kill switch**. After ANY RC takeover the commander is stuck non-IDLE →
call `land` once (drone on floor) to reset before the next takeoff.

**C7 — Config editing rules.** yaml is read once at launch: edit → Ctrl-C the commander →
relaunch (no rebuild). Edit the **SOURCE** yaml under
`AirStack/robot/ros_ws/src/svg_ground_control/config/` — the workspace is symlink-installed.
Verify once: `readlink $(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/<file>.yaml`
should point at the source; no symlink → `bws`. Every number in a list must be a float
(`0.0` not `0`). The teleop fence must lie **inside** the geofence or the launch raises.
⚠️ Never run `test/functional_*.py` while the real stack is up — they publish FAKE odometry
onto the real topics (flyaway risk).

**C8 — Live gains (new).** Some parameters change in flight without a relaunch — from the
Basestation's CBF row (dropdown α / r / vmax, slider, Apply, `live ✓`) or pane 4:
```bash
ros2 param set /swarm_commander cbf_alpha 4.0            # how early the CBF yields
ros2 param set /swarm_commander scenario_speed_mps 1.0   # cruise speed of the goal law
ros2 param set /swarm_commander fence_brake_accel_mps2 6.0
```
Live list: CBF gains, fence dynamics, goal law, teleop gains ([SCENARIOS.md](SCENARIOS.md) §3).
Anything else is refused with a reason. Gains must stay > 0. The scenario keeps the safety
radius it was launched with for its own spacing; only the filter follows a live change.

---

### C8 — parameters you must NEVER set live (they look harmless and are not)

> ⚠️ `fence_brake_accel_mps2` **0** silently reverts the keep_in wall to the old gain×distance barrier · keep `hold_lead_m` at **0.2** (a 1.3 m lead above a grounded drone doubled its hover height, bag C1_0920_203148) · keep `fence_brake_accel_mps2` **≥ `goal_accel_mps2`** or the wall caps cruise speed · `cbf_max_speed_mps` is the ONLY speed limit on the real drone (its PX4 allows 20 m/s). Details: [CONFIG.md](CONFIG.md).

## D · POST-FLIGHT — pull & review the PX4 logs

Every arming writes a `.ulg` on the drone. **Laptop** terminal (password: CONFIG.md):
```bash
ssh root@<DRONE_IP> "ls -lt /data/px4/log/ | head -3"        # newest session dir
mkdir -p ~/flight_logs/$(date +%F)
scp root@<DRONE_IP>:/data/px4/log/sessNNN/logNNN.ulg ~/flight_logs/$(date +%F)/
```
⚠️ The drone's clock is often unsynced — **match logs by SIZE, not date**. Sessions
increment per boot; log numbers per arming.

Review: drag the `.ulg` onto **logs.px4.io** (Flight Review). Look at: EKF vision-fusion
health, actuator outputs, and the mode/arming timeline (every takeover and disarm is
recorded). **New tool:** `python3 AirStack/robot/ros_ws/src/svg_ground_control/scripts/ulog_param_diff.py a.ulg b.ulg MPC_ EKF2_`
(needs `pip install pyulog`) prints only the PX4 parameters that differ between two logs —
the first thing to run when "this flight behaved differently".

## Pocket reference

| Thing | Rule |
|---|---|
| `ros2` / `bws` / `rviz2` | container only (`root@`) — a sim-session tab or a `bringup` pane |
| `docker` / `airstack.sh` / `adb` / `ip addr` / `./mocap.sh` / `./svg_teleop.sh` | laptop only (`jeremychia@`) |
| Sim session (tabs) | `~/AirStack-starling-max2/tools/sim_terminals.sh` (laptop) → one Terminator window: Isaac Sim · Interfaces · Commander · Cockpit tabs, each inside its container with its commands printed — §A |
| tmux `bringup` (real drone; sim alternative) | `./airstack.sh connect robot` attaches · `Ctrl-b ←→↑↓` moves · `Ctrl-b d` detaches · session survives closing the terminal |
| `/fmu/*` topics | `echo` always needs `--qos-reliability best_effort`; `hz` takes no QoS flag in this ros2 |
| One-message health check | `ros2 topic echo /svg/commander_status --once` — state, odometry freshness, fence, last command |
| Long-running (leave open) | Isaac spawn (Isaac Sim tab) · mocap bridge (laptop) · QGC (laptop) · agent · interfaces · commander — **one tab or pane each** |
| Panic, in order | `hold` → `land` → **RC kill switch** — exact syntax: [PREFLIGHT.md](PREFLIGHT.md); the panel's Hold All / Safety Stop call the same services |
| Troubleshooting | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |
| Goal topics | `/svg/drone_1/goal_command` (PoseStamped, `map` frame, ABSOLUTE) · `/svg/drone_1/speed_command` (Float32) · `/svg/drone_1/goal_xyzt` (x,y,z,θ°) — after `start`, `goal` scenario only |
| Live params | `ros2 param set /swarm_commander <name> <value>` — CBF gains, fence dynamics, goal law, teleop; others refused |
| [SIM] **sim-only — never port to the drone** (iron rule 9) | sim airframe rate gains ×0.5, gyro filters 80/40, `LNDMC_ROT_MAX` 300 (real 30), motor lag off, MAVROS respawn, `cbf_sim.yaml` speeds 2.0 / 4.0 / 6.0 + landing settle 2.0 s / retry. Real `_ours` configs: `drone_1`, `land_settle_s` 0.0, `land_speed_mps` 0.6, `cbf_max_speed_mps` 1.0 |
| `target_system` | must equal the drone's `MAV_SYS_ID` — check the `px4_interface` startup line; no ACK = mismatch |
| RC takeover | straight to **MANUAL** or **kill switch** ONLY (POSCTL/ALTCTL leak commander setpoints) |
| After landing | confirm **DISARMED** in QGC before approaching — the panel's Interface column is an ACK log, not an arming display |
| After RC takeover | call `land` once (drone on floor) to reset the commander |
| Container messages to ignore | `Workspace not built yet` (pre-bws) · `groups: … 992` · `unknown-robot` · `LED daemon` warnings with no strip fitted · prompt garbage `[:refused refused reached]` |
| Drone hotspot (`uap0`, SSID `Starling_1_demo_mode` on Starling 1) | never connect the laptop to it |
| Drone power-off | `adb shell shutdown now` (laptop) → wait ~10 s → unplug USB, then battery |
| Drone after re-provisioning | **reboot**, never `systemctl restart voxl-px4` |

### Sim launch variants

*(Moved verbatim from §A1 and §A "Alternatives to the tabs" on 2026-10-21. "The line above" =
the §A1 Isaac spawn line.)*

| Variant | Change to the line above |
|---|---|
| No Isaac window (lighter) | `ISAAC_SIM_HEADLESS=true` |
| CMU's Iris quad instead of the Starling | drop `DRONE_USD=…` and `PX4_VEHICLE_MODEL=…` |
| ZED stereo camera on drone_1 (needed for the camera world / stereo VO runs; costs GPU) | add `ENABLE_CAMERA=true CAMERA_DRONES=drone_1` in front; size `CAMERA_WIDTH=640 CAMERA_HEIGHT=480` (default since 2026-10-22). The images are visible only from a container on the Isaac network — [TROUBLESHOOTING](TROUBLESHOOTING.md#simulation-isaac-sim--px4-sitl--mavros) |
| Construction-site world (textured — stereo VO needs it) | add `ENV_USD=…/construction_site_full.usdc` (`_r40.usdc` = lighter 40 m crop) plus the ZED row's env in front; the stage takes ~90 s longer. Isaac start/stop has crashed the laptop's WiFi firmware ([TROUBLESHOOTING](TROUBLESHOOTING.md#simulation-isaac-sim--px4-sitl--mavros)) — run `localisation/scripts/sim_resources_watch.sh`. Full path, install, SLAM side, scoring: [localisation/README.md](../localisation/README.md) |
| CMU's measured 72 ms motor lag (experiments only — it tumbles the attitude loop) | add `STARLING_MOTOR_TAU=0.072` in front |

**tmux instead of Terminator.** Same commands, different windows. Laptop:
```bash
cd ~/AirStack-starling-max2/AirStack && ./airstack.sh up && ./airstack.sh connect isaac-sim --command=bash
```
→ run A1 there. New laptop terminal: `cd ~/AirStack-starling-max2/AirStack && ./airstack.sh connect robot`
→ tmux `bringup`: pane 1 = A2 (after `cd ~/AirStack/robot/ros_ws`), pane 2 = A3, pane 3 = A4.
The old `./airstack.sh connect robot --command=bash` still gives a throw-away container shell
outside tmux.

**One-command teleop session** (laptop, from the package's `scripts/` folder — brings up
Isaac, interfaces, commander, an RViz window and a gamepad in tmux sessions of its own — ⏳ STE;
it passes no `teleop_controller`, so it always assumes an Xbox pad; the panel still connects
to its commander):
```bash
cd ~/AirStack-starling-max2/AirStack/robot/ros_ws/src/svg_ground_control/scripts
./svg_teleop.sh solo        # 1 sim drone + gamepad   (squeeze = 3 drones, hover = 3 drones)
./svg_teleop.sh takeoff && ./svg_teleop.sh start      # later: land | hold | reset-fence | stop
```
Details and the gamepad: [TELEOP.md](TELEOP.md) §4. RViz still works as a fallback view
(`rviz2 -d $(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/svg_drones.rviz`).
