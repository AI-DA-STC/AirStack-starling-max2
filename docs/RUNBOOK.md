# RUNBOOK — start the pipeline fast

> **Who this is for:** anyone whose machine is already set up (README → "Setting up AirStack
> on a NEW machine") and who just wants to **run** things. No background, no debugging — that
> lives in [MILESTONES.md](MILESTONES.md) (plan + work log) and
> [TROUBLESHOOTING.md](TROUBLESHOOTING.md) (symptom → fix).
> Every code block says where it runs. **Never paste across a `connect` line** — it opens a
> new shell and swallows what follows.
>
> ⚠️ **Branch note (2026-10-07):** this runbook describes `yikuan/SVG_ground_control`. The
> flows below were validated on the *previous* branch (2026-07-20 sim, 2026-09-01→03 real);
> on this branch every section is **⏳ STE until re-validated** — ledger in
> [MILESTONES.md](MILESTONES.md) §3c. What changed: [MIGRATION.md](MIGRATION.md) §5.

*(Unfamiliar term? → [GLOSSARY.md](GLOSSARY.md))*

**Prompt rule:** `jeremychia@…$` = laptop · `root@…#` = inside the robot container ·
`starling2-max…$` = on the drone (adb/ssh).

**Pane rule (new on this branch):** `./airstack.sh connect robot` drops you into a tmux
session called `bringup` with **8 panes** — pane 0 top-left, 1–4 across the top, 5–7 along the
bottom — every one already a container shell with the workspace sourced. One long-running
thing per pane; the whole session survives you closing the terminal (`connect` again to
return). Move between panes with `Ctrl-b` then an arrow key; `Ctrl-b d` detaches. Steps below
say "pane N" where the old runbook said "new container shell".

---

## A · Fly in SIMULATION (⏳ STE on this branch — was ✅ 2026-07-20)

GPU required (Isaac Sim). One laptop terminal for Isaac, one tmux session for everything else,
Foxglove Studio for the view.

**T1 — stack + sim drones.** Laptop:
```bash
cd ~/AirStack-starling-max2/AirStack
./airstack.sh up
./airstack.sh connect isaac-sim --command=bash
```
Inside (one command, safe to paste whole):
```bash
NUM_ROBOTS=3 SVG_DOMAIN_ID=1 PLAY_SIM_ON_START=true ISAAC_SIM_HEADLESS=true \
PYTHONPATH="$ISAAC_SIM_PYTHONPATH" \
/isaac-sim/python.sh /isaac-sim/AirStack/simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py \
  --ext-folder ~/.local/share/ov/data/documents/Kit/shared/exts
```
Wait for `Ready for takeoff!` ×3. Leave running. (Optional: `ENABLE_CAMERA=true
CAMERA_DRONES=drone_3` in front spawns a ZED camera on one drone — costly, skip unless needed.)

**T2 — the `bringup` session.** New laptop terminal:
```bash
cd ~/AirStack-starling-max2/AirStack && ./airstack.sh connect robot
```
You are in tmux, pane 0. Build once (pane 0):
```bash
cd ~/AirStack/robot/ros_ws && bws && sws     # bws only if code changed; panes 1–7 auto-source when it finishes
```
Pane 1 — interfaces (leave running):
```bash
./src/svg_ground_control/scripts/launch_sim_interfaces.sh 3
```
Pane 2 — commander (leave running). Pick the config for what you want to see
([SCENARIOS.md](SCENARIOS.md) §4 has the catalogue):
```bash
ros2 launch svg_ground_control ground_control.launch.py                                   # default: hover, all-auto, foxglove_bridge on
# CBF crossing demo:
ros2 launch svg_ground_control ground_control.launch.py \
  config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/cbf_sim.yaml
```

**T3 — Foxglove Studio (replaces RViz).** Either open Studio **inside the container** by
adding `use_foxglove_studio:=true` to the commander launch above, or run Studio on the laptop
and connect it to `ws://localhost:8765`. Import the layout once
(`robot/ros_ws/src/svg_ground_control/foxglove/svg_basestation.json`). Setup and what
"healthy" looks like: [BASESTATION.md](BASESTATION.md) §2.

**T4 — cockpit.** Pane 3, one call at a time — or the Basestation's buttons, which call the
same services:
```bash
ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger   # arm + climb + hold
ros2 service call /swarm_commander/start   std_srvs/srv/Trigger   # scenario live
ros2 service call /swarm_commander/hold    std_srvs/srv/Trigger   # PANIC freeze
ros2 service call /swarm_commander/land    std_srvs/srv/Trigger   # descend + disarm
```
Fence latched (`FENCE BREACH` chip, drones frozen — `hold_all` configs)? → `land`, then
`/swarm_commander/reset_fence` (or the panel's **Reset Fence**), then takeoff + start again.
`keep_in` configs never latch — the drone brakes at the wall instead.

**One-command alternative** (host, from the package's `scripts/` folder — brings up Isaac,
interfaces, commander, an RViz window and a gamepad in tmux sessions of its own — ⏳ STE, and
note it passes no `teleop_controller`, so it always assumes an Xbox pad; the Basestation still
connects to its commander):
```bash
cd ~/AirStack-starling-max2/AirStack/robot/ros_ws/src/svg_ground_control/scripts
./svg_teleop.sh solo        # 1 sim drone + gamepad   (squeeze = 3 drones, hover = 3 drones)
./svg_teleop.sh takeoff && ./svg_teleop.sh start      # later: land | hold | reset-fence | stop
```
Details and the gamepad: [TELEOP.md](TELEOP.md) §4.

<details>
<summary>Legacy — one container terminal per step (superseded 2026-10-07 by the tmux session — kept for the record)</summary>

Each step opened its own laptop terminal with
`cd ~/AirStack-starling-max2/AirStack && ./airstack.sh connect robot --command=bash`
(prompt `root@…#`), then: T2 `bws && sws` + `launch_sim_interfaces.sh 3`; T3
`ros2 launch svg_ground_control ground_control.launch.py`; T4
`rviz2 -d $(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/svg_drones.rviz`
(RViz still works — the `svg_drones.rviz` config is still shipped — but the Basestation is
the operator view now); T5 the four service calls. The `--command=bash` form still works for
a throw-away shell outside tmux.

</details>

---

## B · REAL DRONE session (mocap room) — ⏳ STE on this branch

> **Where things run.** Three KINDS of shell exist; each step names its kind:
>
> | Kind | Prompt looks like | How you get one | Runs |
> |---|---|---|---|
> | **Laptop (host)** — outside docker | `jeremychia@…$` | just open a terminal | step 0 ssh entry · step 1 IP checks · step 2 `airstack.sh up` · **step 3b QGC** · **step 4 mocap bridge** · **step 7 Foxglove Studio (if on the host)** — these do NOT run in docker |
> | **Container pane** — inside docker | `root@…#` | step 2's `connect` → tmux `bringup`, panes 0–7 | step 3 agent · step 5 interfaces · step 6 commander · step 8 cockpit · verify commands |
> | **Drone (ssh/adb)** | `starling2-max…$` | `ssh root@<DRONE_IP>` (step 0) or `adb shell` | one-time provisioning · clean shutdown |
>
> A full session = 3–4 laptop terminals + one tmux session. If a `ros2` command says
> "command not found" you're in a host shell; if `./mocap.sh` complains about ROS you're in
> the container — swap kinds.

> **Maturity (2026-10-07):** nothing in §B has run on this branch yet. The mocap chain
> (steps 1, 3b, 4) is unchanged from the previous branch. Steps 0, 5, 6, 7 are changed —
> read them, don't skim. One-time drone work (new provisioning script, watchdog decision):
> MILESTONES M2-A. No Isaac Sim needed — do NOT start it.

**0 — Re-provision the drone(s)** — needed once per drone every time the GC laptop (or its
IP) changes, **and once after switching to this branch** (the script is rewritten:
`px4-` wrapper, boot retry loop, and a new `svg-microdds-watchdog` service). The drone
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
`<BODY_NAME>` = the Motive rigid-body name (`drone_1`), `<DOMAIN_ID>` = the drone's DDS
domain (`1` for drone_1 — unique per drone), `<AGENT_PORT>` = `8888` (must match step 3's
agent). Push the *new* script first if the drone still has the old one
(`adb push AirStack/robot/ros_ws/src/svg_ground_control/scripts/voxl_setup_real_drone.sh /usr/bin/`).
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
Compare against **[CONFIG.md](CONFIG.md)** (the single source of truth for every IP/SSID/name
— including *what to do* when one has drifted). Quick version: `enp…` (Ethernet, lab LAN
`192.168.9.x`) is the mocap path — step 4 listens on it automatically. `wlp…` (`10.40.2.x`)
is the drone segment. **The drone's IP** (for step 0's `ssh` and §D): router admin page
(`http://192.168.9.1:8080`), or `adb shell voxl-my-ip`, or the agent's `session established`
line. The drone auto-joins SSID `StarlingMax2` at boot. (WiFi missing after reboot + dmesg
`Firmware Init Failed` → cold power cycle: battery + USB out 10 s.)

**2 — Stack up (robot container only).** Laptop:
```bash
cd ~/AirStack-starling-max2/AirStack
./airstack.sh up robot-desktop
./airstack.sh connect robot          # → tmux "bringup", 8 panes, prompt root@…#
```
Pane 0, once: `cd ~/AirStack/robot/ros_ws && bws && sws` (seconds unless code changed; the
other panes auto-source when it finishes). Every container step below names a pane. Need
a shell outside tmux? `./airstack.sh connect robot --command=bash` still works.
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
prints nothing even though hz shows 30 Hz — px4_msgs mismatch, MILESTONES §3d; use
`vehicle_odometry` for the echo check. (Before the agent starts, the drone-side
`px4-microdds_client status` shows `Running, disconnected` — normal; the new watchdog keeps
retrying.)

**3b — QGroundControl** (battery, arming status, params, kill switch). **Laptop** terminal
(NOT a container shell), its own window — leave running:
```bash
~/QGroundControl-x86_64.AppImage
```
No vehicle appears? The drone pushes MAVLink to the GCS IP configured on it
(`voxl-mavlink-server.conf`, see CONFIG.md) — it must point at this laptop.

**4 — Mocap bridge** (unchanged by the branch switch — our Motive broadcasts and the stock
driver can't hear it; story + troubleshooting in [MOCAP.md](MOCAP.md)). *Prereq: the
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

**6 — Commander + mocap bridge + Foxglove bridge.** *One-time prereqs (all done on the
previous branch, unchanged): EKF2 params via QGC, vision-hub conf (`en_vio` false /
`offboard_mode` off).* Use a config **trimmed to `drone_1`** — the shipped
`swarm_real.yaml` lists three real drones, moved its hover height to 1.2 m and still
carries `land_speed_mps: 0.3` (the value that left the drone armed on the ground); our
validated single-drone values (z 0.5 m, `land_speed_mps` 0.6) are in [CONFIG.md](CONFIG.md)
and the trim is on the [MIGRATION.md](MIGRATION.md) §6 list. Pane 3:
```bash
ros2 launch svg_ground_control ground_control.launch.py \
  config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/swarm_real.yaml use_mocap:=true
```
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
running or the row says `odom none`. Phantom `drone_2`/`drone_3` rows with no data are
normal if the config is still 3-drone. Do NOT call takeoff during this check.
*(RViz still works — `rviz2 -d …/svg_drones.rviz`, Fixed Frame → `world` — as a fallback.)*

**8 — Fly** (⏳ STE on this branch — MILESTONES M3). ⚠️ Do not call `takeoff` until every
box on [PREFLIGHT.md](PREFLIGHT.md) is checked and a briefed safety pilot holds the
transmitter. Pane 4 (the "cockpit") — one call at a time — **or the Basestation buttons**
(Takeoff and Start ask for confirmation; Safety Stop needs two clicks within 4 s):
```bash
ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger   # arm + climb + hold
ros2 service call /swarm_commander/start   std_srvs/srv/Trigger   # scenario live
ros2 service call /swarm_commander/hold    std_srvs/srv/Trigger   # PANIC: brake to a stop point ahead, hold there
ros2 service call /swarm_commander/land    std_srvs/srv/Trigger   # descend + disarm
```
`start` begins the scenario and is **REQUIRED** before goals or teleop respond.
Watch the panel's command log: `sent → accepted → ✓ confirmed`, and the Interface column:
`request offboard ✓ · arm ✓`. **`DENIED`** = PX4 refused (preflight) · **no entry at all** =
`target_system` mismatch — fix before retrying. Goal/waypoint flights → **§C**. Gamepad →
[TELEOP.md](TELEOP.md) §5.
⚠️ Safety status: RC kill switch mapped + tested on the previous branch (2026-09-01) —
**repeat the props-off kill ground test** before the first flight on this branch
([DRONE_SETUP.md](DRONE_SETUP.md) §8). Every flight: fence fits the net, thumb on kill,
QGC visible.

**Shutdown** (either session type). Ctrl+C each pane's launch, `Ctrl-b d` to leave tmux,
then laptop:
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

## C · GOAL FLIGHTS (fly to commanded waypoints) — ⏳ STE on this branch (MILESTONES M4)

> **🚨 EMERGENCY** — `ros2 service call /swarm_commander/hold  std_srvs/srv/Trigger`
> · `ros2 service call /swarm_commander/land  std_srvs/srv/Trigger`
> · panel: **Hold All** / **Safety Stop · Land All** (two clicks)
> · **KILL = ch8 on the RC — instant motor cut**
> · **takeover = flip ch6 to MANUAL, never Position/Altitude**

Same session bring-up as §B steps 0–7 — **only step 6's config changes**. ⚠️ The shipped
goal configs are **not usable as-is on our rig** ([MIGRATION.md](MIGRATION.md) §7):

| Config | Shipped as | What to do |
|---|---|---|
| `swarm_real.yaml` | 3 real drones, hover scenario, `hold_all` fence, z 1.2 m | trim to `drone_1`, z 0.5 — the §B hover config |
| `goal_single.yaml` | **`drone_2`**, `goal` scenario, `keep_in` fence `[-4.5,-5.2,0]..[5.5,4.5,3.0]`, teleop fence on, `cbf_max_speed_mps` **10.0** | copy → `goal_single_ours.yaml`: `drone_1`, fence + teleop fence drawn to **our net**, speeds down to 1.0, `land_speed_mps` 0.6 — the §C config |
| `goal_tracking.yaml` | 3 real drones, **`random_goals`** scenario (ignores goal commands!), 10 m/s | not for one drone — M7 material ([SCENARIOS.md](SCENARIOS.md) §7) |

Edit the SOURCE yaml under `AirStack/robot/ros_ws/src/svg_ground_control/config/`
(rules in C7) and record the values in [CONFIG.md](CONFIG.md).

**C1 — Launch.** Pane 3 (replaces step 6's launch command):
```bash
ros2 launch svg_ground_control ground_control.launch.py \
  config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/goal_single_ours.yaml use_mocap:=true
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

**C5 — Landing / disarm.** `land` descends at `land_speed_mps`; on touchdown **PX4's own
land detector + auto-disarm** finish the job (the commander's disarm is the cosmetic early
one — now visible as `disarm ✗` in the panel's Interface column). Our validated
`land_speed_mps` is **0.6** (0.3 left the drone armed on the ground); the shipped configs
carry **0.3** (`swarm_real`, `teleop_real`), 0.8 (`goal_single`) or 1.0 (`goal_tracking`)
— set 0.6 in every config you fly. ⚠️ ALWAYS confirm **DISARMED** in QGC before approaching.

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
| `ros2` / `bws` / `rviz2` | container only (`root@`) — normally a `bringup` pane |
| `docker` / `airstack.sh` / `adb` / `ip addr` / `./mocap.sh` / `./svg_teleop.sh` | laptop only (`jeremychia@`) |
| tmux | `./airstack.sh connect robot` attaches · `Ctrl-b ←→↑↓` moves · `Ctrl-b d` detaches · session survives closing the terminal |
| `/fmu/*` topics | `echo` always needs `--qos-reliability best_effort`; `hz` takes no QoS flag in this ros2 |
| One-message health check | `ros2 topic echo /svg/commander_status --once` — state, odometry freshness, fence, last command |
| Long-running (leave open) | Isaac spawn (laptop terminal) · mocap bridge (laptop) · QGC (laptop) · agent · interfaces · commander — **one pane each** |
| Panic, in order | `hold` → `land` → **RC kill switch** — exact syntax: [PREFLIGHT.md](PREFLIGHT.md); the panel's Hold All / Safety Stop call the same services |
| Troubleshooting | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |
| Goal topics | `/svg/drone_1/goal_command` (PoseStamped, `map` frame, ABSOLUTE) · `/svg/drone_1/speed_command` (Float32) · `/svg/drone_1/goal_xyzt` (x,y,z,θ°) — after `start`, `goal` scenario only |
| Live params | `ros2 param set /swarm_commander <name> <value>` — CBF gains, fence dynamics, goal law, teleop; others refused |
| `target_system` | must equal the drone's `MAV_SYS_ID` — check the `px4_interface` startup line; no ACK = mismatch |
| RC takeover | straight to **MANUAL** or **kill switch** ONLY (POSCTL/ALTCTL leak commander setpoints) |
| After landing | confirm **DISARMED** in QGC before approaching — the panel's Interface column is an ACK log, not an arming display |
| After RC takeover | call `land` once (drone on floor) to reset the commander |
| Container messages to ignore | `Workspace not built yet` (pre-bws) · `groups: … 992` · `unknown-robot` · `LED daemon` warnings with no strip fitted · prompt garbage `[:refused refused reached]` |
| Drone hotspot (`uap0`, SSID `Starling_1_demo_mode` on Starling 1) | never connect the laptop to it |
| Drone power-off | `adb shell shutdown now` (laptop) → wait ~10 s → unplug USB, then battery |
| Drone after re-provisioning | **reboot**, never `systemctl restart voxl-px4` |
