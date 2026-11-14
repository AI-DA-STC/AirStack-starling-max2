# RUNBOOK — start the pipeline fast

| Session | SIM or REAL | Go to |
|---|---|---|
| Fly in simulation with the four-tab window | SIM | [A](#a--fly-in-simulation--sim-validated-in-part-on-this-branch-recordledgermd) |
| Fly the simulation with the keyboard, one drone | SIM | [Keyboard teleop](../localisation/README.md#fly-it-with-the-keyboard-one-drone-sim-only) |
| One real drone, takeoff and land from the commander | REAL | [B](#b--real-drone-session-mocap-room) |
| One real drone on the gamepad | REAL | [B9](#b9--fly-one-real-drone-with-the-gamepad) |
| Two real drones, one flown by hand | REAL | [B10](#b10--two-real-drones-one-flown-by-hand) |
| One real drone flying to commanded goals | REAL | [C](#c--goal-flights-fly-to-commanded-waypoints) |
| Two real drones with the collision filter | REAL | [C9](#c9--two-real-drones-with-the-collision-filter-cbf) |
| Pull and review the PX4 logs after a flight | REAL | [D](#d--post-flight--pull--review-the-px4-logs) |

For anyone whose machine is already set up. Every code block says where it runs. Unfamiliar term? See [GLOSSARY.md](GLOSSARY.md).

**Prompt rule:** `jeremychia@…$` = laptop · `root@…#` = inside the robot container (the docker
container that holds the ROS 2 workspace) · `starling2-max…$` = on the drone (adb/ssh) ·
`root@…:/exploration#` = the exploration container (camera-world runs — [localisation/README.md](../localisation/README.md)).

**Never paste across a `connect` line.** It opens a new shell and swallows what follows.

The `bringup` tmux session has 8 panes: pane 0 top-left, 1–4 across the top, 5–7 along the bottom. Each is a container shell with the workspace sourced. Sections B and C say "pane N". Section A says "<name> tab".

tmux moves: `Ctrl-b` then an arrow key switches panes. `Ctrl-b d` detaches. The session survives closing the terminal (`connect` again to return).

---

## A · Fly in SIMULATION — sim validated in part on this branch ([record/LEDGER.md](record/LEDGER.md))

> **WORLD: SIMULATION — nothing in this section touches the drone.** Step 0, before anything else: the drone's battery is OUT and `./mocap.sh` is NOT running on the laptop (the sim shares DDS domain 1 and the `/drone_1` topic names with the real drone). ⚠️ Sim-only — never port to the drone: the sim airframe values and `cbf_sim.yaml` speeds/landing settle (iron rule 9).

### A0 — open the session (one command)

**1 · Laptop · the four tabs**
```bash
~/AirStack-starling-max2/tools/sim_terminals.sh
```
Must see: ONE Terminator window, four tabs (Isaac Sim, Interfaces, Commander, Cockpit), each already inside its container. Keep the window open.

### A1 — Isaac Sim tab: spawn the sim drones

**2 · Isaac Sim · spawn the drones.** Starling 2 Max model, Isaac window on. Paste as one block.
```bash
DRONE_USD=/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd PX4_VEHICLE_MODEL=pegasus_starling2max NUM_ROBOTS=3 SVG_DOMAIN_ID=1 PLAY_SIM_ON_START=true ISAAC_SIM_HEADLESS=false PYTHONPATH="$ISAAC_SIM_PYTHONPATH" /isaac-sim/python.sh /isaac-sim/AirStack/simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py --ext-folder ~/.local/share/ov/data/documents/Kit/shared/exts
```
Must see: `Ready for takeoff!` ×3. Leave running. Other launch lines: [§ Sim launch variants](#sim-launch-variants).

> ⚠️ **Never press Stop / Play in the Isaac window** to reset the drones. The new PX4s never connect and the whole stack has to be restarted ([TROUBLESHOOTING.md](TROUBLESHOOTING.md), "Pressed Stop ▶ Play").
> The only reset is Ctrl-C + relaunch of this script, then the Interfaces and Commander tabs.
> To bring landed drones back to their pads without a restart: `hold` → formation `home` → `land`. This works **only** under `scenario:=goal`.

### A2 — Interfaces tab: one MAVROS per drone

**3 · Interfaces · MAVROS.** Only after `Ready for takeoff!` ×3.
```bash
./src/svg_ground_control/scripts/launch_sim_interfaces.sh 3
```
Leave running.

### A3 — Commander tab: the commander + the panel

**4 · Commander · the commander**
```bash
ros2 launch svg_ground_control ground_control.launch.py config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/cbf_sim.yaml scenario:=random_goals use_foxglove_studio:=true
```
Must see: Foxglove Studio opens, already connected. Leave running.

### A4 — Cockpit tab: fly

One call at a time, or the panel's buttons (they call the same services).

**5 · Cockpit · takeoff.** Arms and climbs.
```bash
ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger
```
Must see: `holding takeoff position` ×3 (about 30 s). Only then `start`.

**6 · Cockpit · start**
```bash
ros2 service call /swarm_commander/start   std_srvs/srv/Trigger
```
Drones frozen with the `FENCE BREACH` chip (`hold_all` configs): `land`, then `ros2 service call /swarm_commander/reset_fence std_srvs/srv/Trigger` (or the panel's **Reset Fence**), then `takeoff` + `start` again. `keep_in` configs never latch: the drone brakes at the wall.
A MAVROS node died and came back after 2 s (the respawn is sim-only — never port to the drone): PX4 has dropped to its offboard-loss failsafe. In this tab: `ros2 topic echo /drone_N/interface/mavros/state --once`. If `mode` ≠ `OFFBOARD`: `ros2 service call /drone_N/interface/mavros/set_mode mavros_msgs/srv/SetMode "{custom_mode: AUTO.LAND}"`, then the commander's `land`.

**7 · Cockpit · hold.** Freezes the drones in a hover. Also the PANIC button.
```bash
ros2 service call /swarm_commander/hold    std_srvs/srv/Trigger
```

**8 · Cockpit · land.** Land from the hover — never mid-leg.
```bash
ros2 service call /swarm_commander/land    std_srvs/srv/Trigger
```
Must see, Commander tab, per drone: `touchdown at z=… settling 2.0 s before disarm`, then `landed, disarmed (attempt 1)`.
If not: PX4 refused the disarm. Up to 5 retries follow, 1 s apart, then ERROR `disarm not accepted after 5 tries` → the MAVROS recovery in step 6, and [TROUBLESHOOTING.md](TROUBLESHOOTING.md), "Landing ends with the drone still armed".

**9 · Cockpit · disarmed**
```bash
ros2 topic echo /drone_1/interface/mavros/state --once
```
Must see: `armed: false`. If not: [TROUBLESHOOTING.md](TROUBLESHOOTING.md), "Landing ends with the drone still armed".

**Shutdown.** Ctrl-C each tab's launch.

**10 · Laptop · stack down**
```bash
cd ~/AirStack-starling-max2/AirStack && ./airstack.sh down
```

---

## B · REAL DRONE session (mocap room)

Flown here: one drone ([#33](record/LEDGER.md)), two drones ([#35](record/LEDGER.md)).

> **WORLD: REAL DRONE — [PREFLIGHT.md](PREFLIGHT.md) gates every takeoff.** Gates before the next real flight: [MILESTONES.md](MILESTONES.md) "Before the next real flight" (MAV_SYS_ID 1 vs 2, one watchdog only, [PX4_MSGS_AUDIT.md](PX4_MSGS_AUDIT.md) ACK audit, NEAR-826 landing test); props-off kill test: [PREFLIGHT.md](PREFLIGHT.md) / [DRONE_SETUP.md](DRONE_SETUP.md) §8 (NEAR-823); mocap chain after the camera upgrade: [projects/HTX-R2.md](projects/HTX-R2.md) R1.
>
> **Step 0 — which world am I in:** Isaac container NOT running (`docker ps | grep isaac` → empty), no `mavros_node` and no `svg_teleop` in `ros2 node list`, and the `px4_interface … target_system=N` startup line present. ⚠️ Never start Isaac Sim during a real session: the sim publishes on the real drone's topic names.

> **Where things run:** laptop `jeremychia@…$` = steps 0 (ssh), 1, 2 (`up`), 3b, 4, 7 (host Studio) ·
> container pane `root@…#` = steps 3, 5, 6, 8 + verify commands · drone `starling2-max…$` = provisioning, shutdown.
> `ros2: command not found` ⇒ host shell; `./mocap.sh` complaining about ROS ⇒ container — swap.
> Full table: [ARCHITECTURE.md](ARCHITECTURE.md#where-things-run-real-drone-session).

> **Maturity:** flown on this branch with one drone ([#33](record/LEDGER.md), 2026-11-11); the
> two-drone session flown on 2026-11-12 is [C9](#c9--two-real-drones-with-the-collision-filter-cbf) ([#35](record/LEDGER.md)). The mocap chain
> (steps 1, 3b, 4) is unchanged from the previous branch. Steps 0, 5, 6, 7 are changed —
> read them, don't skim. One-time drone work (new provisioning script, watchdog decision):
> NEAR-818–823 ([projects/HTX-R2.md](projects/HTX-R2.md)). No Isaac Sim needed — do NOT start it.
> The gamepad sessions are [B9](#b9--fly-one-real-drone-with-the-gamepad) (one drone, [#36](record/LEDGER.md))
> and [B10](#b10--two-real-drones-one-flown-by-hand) (two drones, [#37](record/LEDGER.md)), each a full sequence.

**0 — Re-provision the drone(s)** — needed once per drone every time the GC laptop (or its
IP) changes, **and once after switching to this branch** (why: [DRONE_SETUP.md](DRONE_SETUP.md#4--point-px4-at-the-laptop-uxrce-dds-provisioning) §4). The drone
*dials the laptop*, so a stale IP means step 3 never gets a session. Laptop:
```bash
ssh root@<DRONE_IP>            # the drone you are provisioning — IPs and password in CONFIG.md
```
Then, on the drone. `<LAPTOP_IP>` = **the laptop's `wlp…` address on the drone segment
(`10.40.2.107`)** — same subnet as the drone. Get today's value from step 1's
`ip -4 -brief addr`; confirm the drone can `ping` it before you fly:
```bash
voxl_setup_real_drone.sh <BODY_NAME> <LAPTOP_IP> <DOMAIN_ID> <AGENT_PORT>
# newer Starling (D0012, 10.40.2.10):       voxl_setup_real_drone.sh drone_2 <LAPTOP_IP> 1 8888
# older Starling (WiFi dongle, 10.40.2.11):  voxl_setup_real_drone.sh drone_1 <LAPTOP_IP> 1 8888
reboot                         # ⚠️ ALWAYS reboot — never `systemctl restart voxl-px4` on this airframe (it kills the flight core)
```
Arguments (`<BODY_NAME>` / `<DOMAIN_ID>` / `<AGENT_PORT>` — the port must match step 3's agent)
and the `adb push` of the new script: [DRONE_SETUP.md](DRONE_SETUP.md#4--point-px4-at-the-laptop-uxrce-dds-provisioning) §4.
Names per drone: the table under "The two Starlings" in [CONFIG.md](CONFIG.md). A wrong name here is not caught until the interfaces step (step 5).
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
Leave running. Verify (pane 4): `ros2 topic hz /drone_1/pose` (Motive's rate — 240 Hz since
2026-11-11). Poses missing → `./mocap.sh check` (laptop) names the culprit.

**5 — Per-drone interfaces** (turns `/fmu` traffic into the odometry the commander needs —
without this the Basestation shows no odometry and takeoff is refused). Pane 2:
```bash
ros2 launch svg_ground_control real_interfaces.launch.py drones:=drone_1   # more drones: drones:=drone_1,drone_2 target_systems:=1,2
```
**New on this branch:** the startup line must read
`[drone_1.fmu.px4_interface]: PX4Interface initialized (uXRCE-DDS), target_system=N`. That
number must equal the drone's `MAV_SYS_ID` (per drone: the table under "The two Starlings" in [CONFIG.md](CONFIG.md), read 2026-11-12: `drone_1` → 1, `drone_2` → 2; `target_systems:=` must match) or PX4 silently drops every
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

**8 — Fly** (flown here: [#33](record/LEDGER.md), [#35](record/LEDGER.md) — NEAR-825 ([projects/HTX-R2.md](projects/HTX-R2.md))). ⚠️ Do not call `takeoff` until every
box on [PREFLIGHT.md](PREFLIGHT.md) is checked and a briefed safety pilot holds the
transmitter. Pane 4 (the "cockpit") — one call at a time — **or the Basestation buttons**
(Takeoff and Start ask for confirmation; Safety Stop needs two clicks within 4 s):

Takeoff:
```bash
ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger   # arm + climb + hold
```
Then start (REQUIRED before goals or teleop respond):
```bash
ros2 service call /swarm_commander/start   std_srvs/srv/Trigger   # scenario live
```
Land:
```bash
ros2 service call /swarm_commander/land    std_srvs/srv/Trigger   # descend + disarm
```
**PANIC call — hold:**
```bash
ros2 service call /swarm_commander/hold    std_srvs/srv/Trigger   # PANIC: brake to a stop point ahead, hold there
```
In hover, confirm the setpoint stream from a pane: `ros2 topic hz /drone_1/fmu/trajectory_command` ≈ 20 Hz (the panel's `Cmd stream` column watches velocity topics only and reads `--` on a real drone — [BASESTATION.md](BASESTATION.md) §6).
`start` begins the scenario and is **REQUIRED** before goals or teleop respond. Hover about 20 s before `land`; at touchdown on this software the Interface column shows `disarm ✗` and QGC one red "Disarming denied" until the landing test (NEAR-826) is re-observed — expected, not a fault.
Watch the panel's command log: `sent → accepted → ✓ confirmed`, and the Interface column:
`request offboard ✓ · arm ✓`. **`DENIED`** = PX4 refused (preflight) · **no entry at all** =
`target_system` mismatch — fix before retrying. Goal/waypoint flights → **§C**. Gamepad →
[B9](#b9--fly-one-real-drone-with-the-gamepad) (one drone) or [B10](#b10--two-real-drones-one-flown-by-hand) (two drones).
⚠️ Kill-switch ground check (after any RC change, and once after the branch switch): props OFF,
software takeoff, flip kill — motors cut instantly ([PREFLIGHT.md](PREFLIGHT.md),
[DRONE_SETUP.md](DRONE_SETUP.md) §8). Every flight: fence fits the net, thumb on kill,
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

### B9 — Fly one real drone with the gamepad

One Starling, hand-flown with a Logitech F310 pad, motion-capture positioning (mocap). The front door is
[`tools/real.sh`](../tools/README.md#real-drone-the-gamepad-check): it checks the pad and makes the config. It starts nothing.
No Isaac Sim. Every box on [PREFLIGHT.md](PREFLIGHT.md) gates the takeoff.

**Which drone is which** (source: the table under "The two Starlings" in [CONFIG.md](CONFIG.md)):

| Name | Drone | IP | `MAV_SYS_ID` |
|---|---|---|---|
| `drone_1` | older Starling, WiFi dongle | `10.40.2.11` | 1 |
| `drone_2` | newer Starling, D0012 | `10.40.2.10` | 2 |

The older Starling (`drone_1`) flies by the owner's decision, with a watcher on its front-right motor at every
takeoff ([projects/HTX-R2.md](projects/HTX-R2.md#before-the-next-real-flight), hazard 6). This section flies
`drone_2`, as on 2026-11-13. To fly `drone_1` instead, run `tools/real.sh teleop drone_1` in step 3, paste the
lines it prints (they say `drone_1` and `target_systems:=1`), ping `10.40.2.11`, and read `drone_1` for `drone_2` in every check.

**The pad.** Logitech F310, plugged into the laptop. Switch on the back of the pad on **X**, MODE light **off**.
Never press MODE after the pad check. `tools/real.sh pad` checks the pad alone. `tools/real.sh teleop drone_2`
runs the same check (five stick moves), then makes `/tmp/svg_real/teleop_real_drone_2.yaml` in the robot
container. Re-run it after any container restart or pad replug. It refuses while the pad pane runs.

**Cold start.** Prompts: laptop `jeremychia@…$`, container pane `root@…#`. The container's tmux session has
numbered panes. `Ctrl-b` then an arrow key moves between them.

| Pane | What runs there |
|---|---|
| 1 | the drone link (agent). Left running |
| 2 | the interfaces. Left running |
| 3 | the commander. Left running |
| 4 | the cockpit: every `echo`, `hz` and service call |
| 5 | the pad. Left running until DISARMED |

Until DISARMED, press Ctrl-C in pane 4 only.

**0 ·** Drone powered and booted. If the laptop or its IP changed since the last session, re-provision it first
([section B, step 0](#b--real-drone-session-mocap-room)). Then REBOOT it, never `systemctl restart voxl-px4` (iron rule 7).
Each drone keeps its own name and ID: `drone_1` → `MAV_SYS_ID` 1, `drone_2` → `MAV_SYS_ID` 2. The script does not set `MAV_SYS_ID`.

```bash
# 1 · Laptop — no sim (must print nothing), mocap ports clear, the drone answers
docker ps | grep isaac
ss -ulpn | grep -E ':(1510|1511)' || echo "ports clear"
ping -c2 10.40.2.10        # drone_2 (IPs drift: CONFIG.md table)

# 2 · Laptop — robot container up (the pad check runs inside it)
cd ~/AirStack-starling-max2/AirStack
./airstack.sh up robot-desktop

# 3 · Laptop, a terminal — pad check, then the config. Move each stick when asked. It must end
#     "PAD CHECK: PASS — do not press MODE from now on", then print the takeoff point and the pane lines.
cd ~/AirStack-starling-max2 && tools/real.sh teleop drone_2

# 4 · Laptop, two new terminals — QGroundControl (keep it visible), then mocap
#     (rigid body drone_2 must exist in Motive before this starts: MOCAP.md)
~/QGroundControl-x86_64.AppImage
cd ~/AirStack-starling-max2 && MOCAP_BODIES="drone_2" ./mocap.sh

# 5 · Laptop — into the container
cd ~/AirStack-starling-max2/AirStack && ./airstack.sh connect robot   # → tmux "bringup", prompt root@…#

# 6 · Pane 1 — the drone link; wait for "session established", leave running
MicroXRCEAgent udp4 -p 8888 -v4

# 7 · Pane 4 — link and pose alive: a steady rate each (pose about 240 Hz). Ctrl-C after each reading
ros2 topic hz /drone_2/fmu/out/vehicle_status
ros2 topic hz /drone_2/pose

# 8 · Pane 2 — interfaces; the startup line must say target_system=2
ros2 launch svg_ground_control real_interfaces.launch.py drones:=drone_2 target_systems:=2

# 9 · Pane 5 — the pad, BEFORE the commander. A "pad:" line once a second: move each stick, the numbers
#     must follow. No "REFUSING TO COMMAND". Leave it running until QGroundControl says DISARMED.
ros2 launch svg_ground_control teleop.launch.py config:=/tmp/svg_real/teleop_real_drone_2.yaml

# 10 · Pane 3 — the commander, with the config step 3 made
ros2 launch svg_ground_control ground_control.launch.py config:=/tmp/svg_real/teleop_real_drone_2.yaml use_mocap:=true use_foxglove_studio:=true

# 11 · Pane 4 — odometry flowing, drone_2 "state": "IDLE" and "odom_fresh": true, then the
#      pad-alive check: about 20 Hz. Ctrl-C each hz after the reading
ros2 topic hz /drone_2/odometry_conversion/odometry
ros2 topic echo /svg/commander_status --once
ros2 topic hz /svg/drone_2/teleop_command

# 12 · Every box on PREFLIGHT.md. drone_2 stands ON the takeoff point step 3 printed
#      (x -0.5, y 0.0 in teleop_real_ours.yaml), nose toward +x. Safety pilot on the transmitter, thumb on KILL.
#      Everyone stays outside the net from takeoff until QGroundControl says DISARMED.

# 13 · Pane 4 — takeoff. Wait for "holding takeoff position" in pane 3, then start.
#      After start, wait for "drone_2: sticks live" in pane 3 before touching the sticks
ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger
#      WAIT for "holding takeoff position" in pane 3. Only then:
ros2 service call /swarm_commander/start   std_srvs/srv/Trigger

# 14 · Fly with the sticks (below). Sticks do nothing: see the stop table below. Then land.
#      QGroundControl must show DISARMED before anyone walks in.
#      Still ARMED after about 10 s → KILL or arm switch down (iron rule 2)
ros2 service call /swarm_commander/land std_srvs/srv/Trigger
```

**The sticks** (the Basestation's Teleop · Sticks card shows them live: [BASESTATION.md](BASESTATION.md) §3.13):

| Control | What it does |
|---|---|
| Right stick | moves the drone in ROOM axes, not relative to its nose: up = +x, left = +y |
| Left stick | up and down = climb and descend · left and right = turn |
| LB | press once to lock climb and turn, press again to unlock. The right stick still works. Pane 5 shows `LOCKED` |
| Sticks released | the drone holds where it is |

The sticks do nothing until `start`. The speed cap is 0.5 m/s (`teleop_max_speed_mps` and `max_speed_mps` in
`teleop_real_ours.yaml`). It caps the command, not the drone ([#36](record/LEDGER.md)). First turn: slow and low, thumb on KILL.

**What to expect**
- `takeoff` arms and flies a STRAIGHT LINE from where the drone stands to the takeoff point step 3 printed (z 0.5).
  Standing on the point, that is a climb. The fence does not act during the climb or the landing.
- Then it hovers on the point. The Sticks card reads `STICKS PARKED` (press Start).
- `start`: pane 3 prints `drone_2: sticks live, holding [...] until moved`. The card reads `STICKS LIVE → drone_2`.
  (Seen in the panel recordings: `STICKS LIVE` in `videos/xbox_teleop_ui.mp4`, ledger [#36](record/LEDGER.md), and `STICKS PARKED` in
  `videos/cbf_teleop_two_drones_ui.mp4`, ledger [#37](record/LEDGER.md).)
- In flight the teleop fence (x and y −1.5 to 1.5 m, z 0.3 to 1.8 m) is meant to brake the drone at its walls.
  The −y wall was seen in one flight ([#36](record/LEDGER.md)). The +x wall and the top are not flown.

**Stop table.** The [PREFLIGHT.md](PREFLIGHT.md) emergency table comes first.

| What you see | Do this | Record |
|---|---|---|
| Doubt, or the drone drifts with the sticks released | `hold` (pane 4 or the panel's Hold All), then `land`. After `hold` the sticks stay dead until `start` | not flown (`hold`: NEAR-832) |
| You need it down | `land` (pane 4, or the panel's Safety Stop, two clicks) | iron rule 2 |
| A motor of `drone_1` does not spin with the others at takeoff (`drone_1` variant) | KILL, then `land` once | hazard 6, [#34](record/LEDGER.md) |
| Sticks do nothing after `start` | pane 4: `ros2 topic hz /svg/drone_2/teleop_command`. Silent = the pad pane stopped, and no warning appears: `land`. Card says `press Start`: call `start` | [#36](record/LEDGER.md) |
| Pad unplugged in flight | do not replug it in flight. `land`. The code holds the drone where it is (a stale pad = zero command) | not flown |
| Near the top or the +x wall of the teleop fence | let go of the sticks. Still moving: `hold`, then `land` | not flown |
| Anything scary | KILL (ch8), then `land` once with the drone on the floor | iron rule 3 |
| Landed, but QGroundControl still says ARMED | after about 10 s: KILL or arm switch (ch5) down. Nobody walks in | iron rule 2 |

**Shutdown.** Only after QGroundControl says DISARMED: Ctrl-C panes 3, 5, 2, 1 and the mocap terminal, then on the laptop:
```bash
cd ~/AirStack-starling-max2/AirStack && ./airstack.sh down
adb shell shutdown now      # drone power-off, USB-C connected; wait about 10 s, then unplug USB and the battery
```

What was seen: ledger [#36](record/LEDGER.md).

### B10 — Two real drones, one flown by hand

Both Starlings. `drone_1` hovers on its takeoff point. `drone_2` is hand-flown at it with the Logitech F310, and the collision
filter (CBF) keeps them apart. Config `goal_two_ours.yaml` with `teleop_drones:=drone_2`. Which drone is which, the pad and the
sticks: [B9](#b9--fly-one-real-drone-with-the-gamepad). The older Starling (`drone_1`) flies by the owner's decision, with a
watcher on its front-right motor at every takeoff ([projects/HTX-R2.md](projects/HTX-R2.md#before-the-next-real-flight), hazard 6).

**Before you start**
- Two people at takeoff (iron rule 10): the pilot, and a second person watching `drone_1`'s front-right motor.
  Everyone stays outside the net until QGroundControl shows both drones DISARMED.
- Takeoff points (`hover_positions` in `goal_two_ours.yaml`): `drone_1` x 1.0, y −0.2 · `drone_2` x −1.5, y −0.1 ·
  both z 1.0. 2.5 m apart. Each drone stands ON its own point, nose toward +x. Takeoff flies a straight line to it.
- One KILL switch per drone and one person per transmitter. Confirm on the ground which transmitter is which drone.
- No teleop fence in this config. Only the geofence (x and y −2 to 2 m, z 0 to 4 m) brakes `drone_2`.
- Pane 4 is the cockpit (every `echo`, `hz`, `param` and service call). Pane 5 is the pad. Pane 6 is the
  separation readout. Until DISARMED, Ctrl-C in pane 4 only.

**0 ·** Both drones powered and booted. If the laptop or its IP changed since the last session, re-provision each drone
first ([section B, step 0](#b--real-drone-session-mocap-room)). Then REBOOT it, never `systemctl restart voxl-px4` (iron
rule 7). Each drone keeps its own name and ID: `drone_1` → `MAV_SYS_ID` 1, `drone_2` → `MAV_SYS_ID` 2. The script does not set `MAV_SYS_ID`.

```bash
# 1 · Laptop — no sim (must print nothing), mocap ports clear, both drones answer
docker ps | grep isaac
ss -ulpn | grep -E ':(1510|1511)' || echo "ports clear"
ping -c2 10.40.2.10        # drone_2 (IPs drift: CONFIG.md table)
ping -c2 10.40.2.11        # drone_1

# 2 · Laptop — robot container up
cd ~/AirStack-starling-max2/AirStack
./airstack.sh up robot-desktop

# 3 · Laptop, a terminal — pad check and the pad config for drone_2. It must end "PAD CHECK: PASS — do not press
#     MODE from now on". Use only its pane 5 line: its takeoff point and its other lines are for one drone, NOT used here.
#     Do NOT launch pane 3 from that output: its commander line is for one drone.
cd ~/AirStack-starling-max2 && tools/real.sh teleop drone_2

# 4 · Laptop, two new terminals — QGroundControl (both drones, keep it visible), then mocap for both
#     bodies (rigid bodies drone_1 and drone_2 must exist in Motive: MOCAP.md)
#     No takeoff until QGroundControl lists both drones (PREFLIGHT.md)
~/QGroundControl-x86_64.AppImage
cd ~/AirStack-starling-max2 && MOCAP_BODIES="drone_1 drone_2" ./mocap.sh

# 5 · Laptop — into the container
cd ~/AirStack-starling-max2/AirStack && ./airstack.sh connect robot   # → tmux "bringup", prompt root@…#

# 6 · Pane 1 — the drone link; wait for "session established", leave running
MicroXRCEAgent udp4 -p 8888 -v4

# 7 · Pane 4 — both links and both poses: a steady rate each (poses about 240 Hz). Ctrl-C after each
ros2 topic hz /drone_1/fmu/out/vehicle_status
ros2 topic hz /drone_2/fmu/out/vehicle_status
ros2 topic hz /drone_1/pose
ros2 topic hz /drone_2/pose

# 8 · Pane 2 — interfaces; startup lines must say target_system=1 (drone_1) and =2 (drone_2)
ros2 launch svg_ground_control real_interfaces.launch.py drones:=drone_1,drone_2 target_systems:=1,2

# 9 · Pane 5 — the pad for drone_2, BEFORE the commander. Leave it running until QGroundControl
#     shows BOTH drones DISARMED.
ros2 launch svg_ground_control teleop.launch.py config:=/tmp/svg_real/teleop_real_drone_2.yaml

# 10 · Pane 3 — the commander: two-drone config, drone_2 flown by hand
ros2 launch svg_ground_control ground_control.launch.py \
  config:=/root/AirStack/robot/ros_ws/src/svg_ground_control/config/goal_two_ours.yaml \
  teleop_drones:=drone_2 use_mocap:=true use_foxglove_studio:=true

# 11 · Pane 4 — both drones "IDLE" and "odom_fresh": true, each "position" on its own takeoff point
#      (wrong side → carry the drones over, check again). Then the pad-alive check: about 20 Hz. Ctrl-C after
ros2 topic echo /svg/commander_status --once
ros2 topic hz /svg/drone_2/teleop_command

# 12 · Pane 6 — the separation readout: paste the python3 block under "Separation readout" below, unchanged.
#      It must print about 2.5 m (both drones on their points). Leave it running until both are DISARMED.

# 13 · Every box on PREFLIGHT.md. Watcher on drone_1's front-right motor, from outside the net.
#      Pane 4 — takeoff; wait for "holding takeoff position" twice in pane 3
ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger

# 14 · CBF radius 0.90, as flown in ledger #37, with both drones holding on their own points (or the
#      panel's CBF r field → Apply). The read-back must say 0.9 before you go on. Skipping this step
#      leaves the file's 0.55, which has not been flown with the pad. A commander restart puts it back to 0.55.
ros2 param set /swarm_commander cbf_safety_radius_m 0.90
ros2 param get /swarm_commander cbf_safety_radius_m      # read back: 0.9

# 15 · Start: the sticks go live for drone_2
ros2 service call /swarm_commander/start std_srvs/srv/Trigger

# 16 · Fly drone_2 slowly toward drone_1 along x, at the takeoff height. Watch the readout in pane 6.
#      Approach along x at the same height only. Other directions and height offsets are not flown
#      (ledger #37). There is no teleop fence in this config: the only vertical limit is the geofence.
#      Let go once the filter resists. No stop distance is set for the pilot. The pass line fixed before
#      the 2026-11-13 flight is in ledger #37. The owner sets a stop distance before the next flight.
#      Land both. QGroundControl must show BOTH DISARMED before anyone walks in. Still ARMED
#      after about 10 s → KILL or arm switch down (iron rule 2)
ros2 service call /swarm_commander/land std_srvs/srv/Trigger
```

**Separation readout** (step 12, pane 6; needs the interfaces of step 8; run on the live stack
on 2026-11-12). Prints the centre-to-centre distance from odometry, five times a second:
```bash
python3 -c "
import rclpy,numpy as np
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from nav_msgs.msg import Odometry
rclpy.init();n=Node('sep');p={}
for d in('drone_1','drone_2'):
  n.create_subscription(Odometry,'/%s/odometry_conversion/odometry'%d,lambda m,d=d:p.__setitem__(d,np.array([m.pose.pose.position.x,m.pose.pose.position.y,m.pose.pose.position.z])),qos_profile_sensor_data)
n.create_timer(0.2,lambda:len(p)==2 and print('sep %.2f m'%np.linalg.norm(p['drone_1']-p['drone_2']),flush=True))
rclpy.spin(n)"
```
The block has no stale-data check. If the number stops changing while a drone moves, the readout is dead: let go of the sticks and `land`.

**What to expect.** Each drone flies a straight line to its takeoff point and hovers. The fence does not act during the climb or
the landing. `start` makes the sticks live for `drone_2` only. Near `drone_1` the filter slows `drone_2`, and `drone_1` gives way.
Pane 6 shows the distance between the drones throughout.

**Stop table.** The [PREFLIGHT.md](PREFLIGHT.md) emergency table and B9's stop table come first. `hold` on a hand-flown drone
is not flown (NEAR-832). `land` brings down EVERY airborne drone, including one that was not killed.

| What you see | Do this | Record |
|---|---|---|
| A motor of `drone_1` does not spin with the others at takeoff | KILL `drone_1` (its transmitter), then `land` once | hazard 6, [#34](record/LEDGER.md) |
| No stop distance is set | watch the pane 6 readout, let go once the filter resists, `land` if in doubt | the owner sets one before the next flight |
| The filter resists and `drone_1` is pushed toward its +x wall | let go of the stick | hazard 10, [#37](record/LEDGER.md) |
| `CBF emergency push-apart` in pane 3 | `land` | hazard 8 |
| You want a larger CBF radius while the drones are closer than twice the new radius | do not raise it. Fly `drone_2` back to its point first | hazard 8 |
| Sticks do nothing after `start` | pane 4: `ros2 topic hz /svg/drone_2/teleop_command`. Silent: `land` | [#36](record/LEDGER.md) |
| Anything scary | KILL (each pilot their own drone), then `land` once. Killing one leaves the other flying. `land` brings down EVERY airborne drone, including the one that was not killed | iron rule 3 |

**Shutdown.** Only after QGroundControl shows both drones DISARMED: Ctrl-C panes 6, 3, 5, 2, 1 and the mocap terminal, then laptop:
```bash
cd ~/AirStack-starling-max2/AirStack && ./airstack.sh down
adb shell shutdown now      # one USB-C cable at a time: one drone plugged in; wait about 10 s, unplug USB and its battery, then the other
```

What was seen: ledger [#37](record/LEDGER.md).

---

## C · GOAL FLIGHTS (fly to commanded waypoints)

Flown here ([#33](record/LEDGER.md), [#35](record/LEDGER.md)). Seen on the real drone: goal legs and the hold at the +x `keep_in` wall with one drone (NEAR-829, NEAR-830,
[#33](record/LEDGER.md)), goals with two drones and the collision filter (C9, [#35](record/LEDGER.md)). The CBF radius was changed
live from the panel ([#37](record/LEDGER.md), NEAR-831). No other live gain change is recorded. Not flown: where a hold stops the
drone (NEAR-832). Not measured: the speed profile and the distance past the wall ([#33](record/LEDGER.md)).
Issues: [projects/HTX-R2.md](projects/HTX-R2.md).

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
or from pane 4. Before takeoff, place the drone on the floor ON the config's
`hover_positions` x,y — takeoff flies to that ABSOLUTE point (iron rule 10).
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

> ⚠️ `fence_brake_accel_mps2` **0** silently reverts the keep_in wall to the old gain×distance barrier · keep `hold_lead_m` at **0.2** (a 1.3 m lead above a drone on the ground doubled its hover height, bag C1_0920_203148) · keep `fence_brake_accel_mps2` **≥ `goal_accel_mps2`** or the wall caps cruise speed · `cbf_max_speed_mps` is the ONLY speed limit on the real drone (its PX4 allows 20 m/s). Details: [CONFIG.md](CONFIG.md).

### C9 — Two real drones with the collision filter (CBF)

> The older Starling (`drone_1`) flies by the owner's decision, with a watcher on its front-right
> motor at every takeoff ([projects/HTX-R2.md](projects/HTX-R2.md#before-the-next-real-flight), hazard 6).

One drone hovers while the other is flown toward it, to see the collision filter (CBF) keep
them apart. This is the sequence run on 2026-11-12 ([#35](record/LEDGER.md)): config
`goal_two_ours.yaml`, 0.5 m/s, CBF radius 0.80 (keep-out 1.60 m centre to centre). Times are SGT.
On 2026-11-12 the takeoff height was 2.0 m. The file now says 1.0 m (CHG-0067), and the goals below use 1.0 m.

**What was observed** (no gate was set beforehand): [hangar camera](../videos/cbf_drone_real_1080p.mp4) ·
[panel](../videos/cbf_check_ui.mp4) — the 18:00 flight: `drone_2` stopped short of the hovering
`drone_1`, which gave way ([#35](record/LEDGER.md)). The drones are small on the hangar camera
once they hover; the panel shows the filter best.

**Before you start**
- Every box on [PREFLIGHT.md](PREFLIGHT.md); the hazards in [MILESTONES.md](MILESTONES.md#before-the-next-real-flight).
- Which drone is which (IP, `MAV_SYS_ID`): the table under "The two Starlings" in [CONFIG.md](CONFIG.md).
- **Hazard:** takeoff flies a straight line to each drone's takeoff point, so a drone standing
  on the wrong side is flown across the room at floor level ([#34](record/LEDGER.md)). Stand
  each drone on its own point, nose toward +x: `drone_1` (+1.0, −0.2), `drone_2` (−1.5, −0.1),
  2.5 m apart. Step 10 checks it.
- **Hazard:** raising the radius while the drones are closer than twice the new radius fires
  `CBF emergency push-apart` (seen on the floor on 2026-11-12, drones 1.1 m apart). The config
  ships 0.55 and a commander restart resets it to 0.55. Set it only with both drones on their
  points, after step 10 passes.
- **Hazard:** a motor that does not start sends the drone along the floor (7.5 m at up to
  4.5 m/s, [#34](record/LEDGER.md)). Everyone stays outside the net from takeoff until
  QGroundControl shows both drones Disarmed; a motor that does not spin up at arming means KILL.
- One KILL switch per drone and one person per transmitter. Which transmitter is bound to which
  drone is not written down yet: confirm it on the ground. Killing one drone leaves the other flying.

**Where things run:** drones = step 0 · laptop = steps 1, 2, 5 · container panes = the rest
(pane 1 agent, pane 2 interfaces, pane 3 commander, pane 4 cockpit, pane 6 separation
readout, as in B10). **Order on the floor:** positions (10), then
radius (11), then recording (12), then readout (13), then takeoff (14).

**0 ·** Both drones powered and booted. If the laptop or its IP changed since the last session, re-provision each drone
first ([section B, step 0](#b--real-drone-session-mocap-room)). Then REBOOT it, never `systemctl restart voxl-px4` (iron
rule 7). Each drone keeps its own name and ID: `drone_1` → `MAV_SYS_ID` 1, `drone_2` → `MAV_SYS_ID` 2. The script does not set `MAV_SYS_ID`.

```bash
# 1 · Laptop — no sim (must print nothing), mocap ports clear, both drones answer
docker ps | grep isaac
ss -ulpn | grep -E ':(1510|1511)' || echo "ports clear"
ping -c2 10.40.2.10        # drone_2 (IPs drift: CONFIG.md table)
ping -c2 10.40.2.11        # drone_1

# 2 · Laptop — robot container
cd ~/AirStack-starling-max2/AirStack
./airstack.sh up robot-desktop
./airstack.sh connect robot          # → tmux "bringup", prompt root@…#

# 3 · Pane 1 — the drone link; wait for "session established", leave running
MicroXRCEAgent udp4 -p 8888 -v4

# 4 · Pane 4 — both links alive: each must print a steady rate (the 2026-11-12 session notes
#     say about 2 Hz; section B's older note says ~30 Hz). Ctrl-C after each reading
ros2 topic hz /drone_1/fmu/out/vehicle_status
ros2 topic hz /drone_2/fmu/out/vehicle_status

# 5 · Laptop, two new terminals — QGroundControl (connect both drones, keep it visible),
#     then mocap for both bodies (rigid bodies drone_1 and drone_2 must exist in Motive: MOCAP.md)
#     No takeoff until QGroundControl lists both drones (PREFLIGHT.md)
~/QGroundControl-x86_64.AppImage
cd ~/AirStack-starling-max2 && MOCAP_BODIES="drone_1 drone_2" ./mocap.sh

# 6 · Pane 4 — both poses at 240 Hz
ros2 topic hz /drone_1/pose
ros2 topic hz /drone_2/pose

# 7 · Pane 2 — interfaces; startup lines must say target_system=1 (drone_1) and =2 (drone_2)
ros2 launch svg_ground_control real_interfaces.launch.py drones:=drone_1,drone_2 target_systems:=1,2

# 8 · Pane 3 — commander with the two-drone config
ros2 launch svg_ground_control ground_control.launch.py \
  config:=/root/AirStack/robot/ros_ws/src/svg_ground_control/config/goal_two_ours.yaml \
  use_mocap:=true use_foxglove_studio:=true

# 9 · Pane 4 — both drones "state": "IDLE" and "odom_fresh": true; fence keep_in,
#     min [-2,-2,0] max [2,2,4]; cbf safety_radius_m 0.55
ros2 topic echo /svg/commander_status --once

# 10 · Positions: the panel's Agent State x, y per drone (or "position" in step 9's output)
#      must match that drone's takeoff point: drone_1 (+1.0, -0.2), drone_2 (-1.5, -0.1).
#      Wrong side → carry the drones over and check again. No takeoff until both match.

# 11 · Radius 0.80, only after step 10 passes (a drone moved since → redo step 10 first).
#      As flown, in the panel: Swarm Command box, CBF r field → 0.80 → Apply; the panel then
#      shows "CBF r 0.80 · Live 0.80 m". Pane 4 equivalent:
ros2 param set /swarm_commander cbf_safety_radius_m 0.80
ros2 param get /swarm_commander cbf_safety_radius_m      # read back: 0.8

# 12 · Recording on: the panel's Rosbag switch, or pane 4; status must say "recording": true
#      (where the bag lands: BASESTATION.md, "Rosbag switch")
ros2 service call /bag_recorder/record std_srvs/srv/SetBool "{data: true}"
ros2 topic echo /svg/bag_recorder/status --once

# 13 · Pane 6 — start the separation readout (block below). It must print about 2.5 m before
#      takeoff. The stop rules below depend on it.

# 14 · Pane 4 (or the panel's Takeoff / Start buttons). Wait for "holding takeoff position"
#      twice in pane 3, then start
ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger
#      WAIT for "holding takeoff position" twice in pane 3. Only then:
ros2 service call /swarm_commander/start   std_srvs/srv/Trigger

# 15 · Goals for drone_2; the brief waited about 10 s between them. Goals 1 and 2 lie inside
#      the keep-out (1.5 m and 1.3 m from drone_1's point): drone_2 is not meant to reach them.
#      As flown: the panel's Goal box, drone_2 selected, x y z → Send Goal (frame note must
#      read "commander"). Pane 4 equivalents:
ros2 topic pub --once /svg/drone_2/goal_command geometry_msgs/msg/PoseStamped \
  "{header: {frame_id: map}, pose: {position: {x: -0.5, y: -0.2, z: 1.0}}}"   # goal 1
ros2 topic pub --once /svg/drone_2/goal_command geometry_msgs/msg/PoseStamped \
  "{header: {frame_id: map}, pose: {position: {x: -0.3, y: -0.2, z: 1.0}}}"   # goal 2
ros2 topic pub --once /svg/drone_2/goal_command geometry_msgs/msg/PoseStamped \
  "{header: {frame_id: map}, pose: {position: {x: -1.5, y: -0.1, z: 1.0}}}"   # home

# 16 · Land both. QGroundControl must show BOTH Disarmed before anyone walks in. Still armed
#      after about 10 s → KILL or arm switch down (iron rule 2)
ros2 service call /swarm_commander/land std_srvs/srv/Trigger

# 17 · Recording off (or the Rosbag switch)
ros2 service call /bag_recorder/record std_srvs/srv/SetBool "{data: false}"

# 18 · Shutdown: Ctrl-C panes 6, 3, 2, 1 and the mocap terminal, then on the laptop
cd ~/AirStack-starling-max2/AirStack && ./airstack.sh down
```
Then power each drone down: "Drone shutdown" in [section B](#b--real-drone-session-mocap-room), one USB-C cable at a time.

**Panic, in this order:** hold → land → KILL (each pilot kills their own drone). The emergency
table on [PREFLIGHT.md](PREFLIGHT.md) is the one to follow. After any kill or RC takeover call
`land` once: the commander keeps sending setpoints (iron rule 3, [#34](record/LEDGER.md)).
`land` brings down EVERY airborne drone, including one that was not killed.
RC takeover is MANUAL or KILL, never Position or Altitude (iron rule 1).
```bash
ros2 service call /swarm_commander/hold std_srvs/srv/Trigger
```

**Separation readout** (step 13, pane 6; needs the interfaces of step 7; run on the live stack
on 2026-11-12). Prints the centre-to-centre distance from odometry, five times a second:
```bash
python3 -c "
import rclpy,numpy as np
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from nav_msgs.msg import Odometry
rclpy.init();n=Node('sep');p={}
for d in('drone_1','drone_2'):
  n.create_subscription(Odometry,'/%s/odometry_conversion/odometry'%d,lambda m,d=d:p.__setitem__(d,np.array([m.pose.pose.position.x,m.pose.pose.position.y,m.pose.pose.position.z])),qos_profile_sensor_data)
n.create_timer(0.2,lambda:len(p)==2 and print('sep %.2f m'%np.linalg.norm(p['drone_1']-p['drone_2']),flush=True))
rclpy.spin(n)"
```

**What to expect.** Settings: radius 0.80 (keep-out 1.60 m), takeoff height 1.0 m. What was seen on 2026-11-12, with the
earlier 2.0 m takeoff height: [#35](record/LEDGER.md). The 18:00 flight ended with one more goal, on `drone_1`'s own takeoff
point; that goal is not part of this sequence.

| Phase | Expect |
|---|---|
| Takeoff | each drone flies a straight line to its own takeoff point at 1.0 m and holds. That is a plain climb only if the drone stands on its point (hazard 7). Readout about 2.5 m |
| Goal 1 (x −0.5) | `drone_2` flies toward `drone_1` and stops short of its goal, near the 1.60 m keep-out; the panel shows both keep-out spheres blue and "CBF correcting drone_1, drone_2" |
| Goal 2 (x −0.3) | `drone_2` barely moves although its goal is 0.2 m deeper; `drone_1` gives way along +x |
| Home | `drone_2` flies back to x −1.5; the readout rises |
| Land | both descend; QGroundControl must show both Disarmed |

**Stop rules.** The actions on the [PREFLIGHT.md](PREFLIGHT.md) emergency table come first. The
2026-11-12 brief added the triggers below. These limits are for C9 only (goal-driven, set for radius 0.85).
They are not for B10 or for any other radius. They were not re-derived for 0.80.

| Trigger briefed on 2026-11-12 | Action |
|---|---|
| Either drone climbs or sinks more than 0.3 m | send `drone_2` home (step 15, last goal) |
| Readout under 1.2 m | hold |
| Readout under 0.7 m | both KILL switches, then `land` once. `land` brings down every airborne drone |
| `CBF emergency push-apart` in pane 3 | `land` and investigate (the PREFLIGHT.md emergency table) |

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
| `docker` / `airstack.sh` / `adb` / `ip addr` / `./mocap.sh` / `./svg_teleop.sh` / `tools/real.sh` | laptop only (`jeremychia@`) |
| Real gamepad session | [B9](#b9--fly-one-real-drone-with-the-gamepad) (one drone) · [B10](#b10--two-real-drones-one-flown-by-hand) (two drones, one by hand) — `tools/real.sh teleop drone_2` first, pad pane 5 before commander pane 3, pane 5 open until DISARMED |
| Sim session (tabs) | `~/AirStack-starling-max2/tools/sim_terminals.sh` (laptop) → one Terminator window: Isaac Sim · Interfaces · Commander · Cockpit tabs, each inside its container with its commands printed — §A |
| tmux `bringup` (real drone; sim alternative) | `./airstack.sh connect robot` attaches · `Ctrl-b ←→↑↓` moves · `Ctrl-b d` detaches · session survives closing the terminal |
| `/fmu/*` topics | `echo` always needs `--qos-reliability best_effort`; `hz` takes no QoS flag in this ros2 |
| One-message health check | `ros2 topic echo /svg/commander_status --once` — state, odometry freshness, fence, last command |
| Long-running (leave open) | Isaac spawn (Isaac Sim tab) · mocap bridge (laptop) · QGC (laptop) · agent · interfaces · gamepad pad (pane 5) · commander — **one tab or pane each** |
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
