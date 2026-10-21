# RUNBOOK — start the pipeline fast

> **What this is:** the copy-paste command sequence for one session — simulation (§A), the
> real drone (§B), goal flights (§C), post-flight logs (§D).
> **Who should read it:** anyone whose machine is already set up (README → "Setting up AirStack
> on a NEW machine") and who just wants to **run** things. No background, no debugging — that
> lives in [MILESTONES.md](MILESTONES.md) (plan + work log) and
> [TROUBLESHOOTING.md](TROUBLESHOOTING.md) (symptom → fix).
> Every code block says where it runs. **Never paste across a `connect` line** — it opens a
> new shell and swallows what follows.
>
> ⚠️ **Branch note (2026-10-21):** this runbook describes CMU's `yikuan/SVG_ground_control_dev`
> @ `b21d28c` (vendored 2026-10-20 — [MIGRATION.md](MIGRATION.md) §11; the release line
> `yikuan/SVG_ground_control` @ `cf719f0` was our 2026-10-07 snapshot). **Sim (§A) is validated
> in part** — ledger in [MILESTONES.md](MILESTONES.md) §3c. **No real flight on this branch
> yet:** §B/§C were last flown on the *previous* branch (2026-09-01→03) and stay **⏳ STE until
> re-validated**. What changed for a pilot: [MIGRATION.md](MIGRATION.md) §5.

*(Unfamiliar term? → [GLOSSARY.md](GLOSSARY.md))*

**Prompt rule:** `jeremychia@…$` = laptop · `root@…#` = inside the robot container (the docker
container that holds the ROS 2 workspace) · `starling2-max…$` = on the drone (adb/ssh).

**Two ways into the containers.** Pick one per session:

| Way | Laptop command | What opens | Use it for |
|---|---|---|---|
| **Sim session (tabs)** | `~/AirStack-starling-max2/tools/sim_terminals.sh` | ONE Terminator window, four tabs — **Isaac Sim · Interfaces · Commander · Cockpit** — each already inside its container, each printing its own commands | the sim (§A) |
| **tmux `bringup` session** | `cd ~/AirStack-starling-max2/AirStack && ./airstack.sh connect robot` | the container's tmux session: **8 panes** — pane 0 top-left, 1–4 across the top, 5–7 along the bottom — every one a container shell with the workspace sourced | the real drone (§B/§C); §A without Terminator |

tmux moves: `Ctrl-b` then an arrow key switches panes; `Ctrl-b d` detaches; the session
survives closing the terminal (`connect` again to return). One long-running thing per
tab or pane. §B/§C say "pane N"; §A says "<name> tab".

---

## A · Fly in SIMULATION — sim validated in part on this branch (MILESTONES §3c)

GPU required (Isaac Sim is NVIDIA's GPU simulator). Four long-running things, one per tab:
the Isaac Sim spawn, the **interfaces** (one MAVROS node per drone — MAVROS turns PX4's
MAVLink into ROS topics), the **commander** (the ROS node that flies the swarm) and a
**cockpit** shell for the service calls. The **panel** (the Foxglove SVG Basestation) is the
operator view.

**What success looks like:** [videos/random_CBF_sim_edited.mp4](../videos/random_CBF_sim_edited.mp4)
— three Starling 2 Max models flying `random_goals` under the CBF in Isaac Sim, 2026-10-21
(`cbf_sim.yaml`: 2.0 m/s cruise, cap 4.0, r 0.55, α 2.5; a 47 s excerpt of a 3.5 min run).

### A0 — open the session (one command)

Laptop:
```bash
~/AirStack-starling-max2/tools/sim_terminals.sh
```
It brings the containers up (`./airstack.sh up`) if they are not running, then opens ONE
Terminator window with the four tabs. Each tab is already inside the right container and
prints its commands at the top (that is `tools/sim_tab.sh <role>`). Work the tabs left to
right: **A1 = Isaac Sim tab, A2 = Interfaces tab, A3 = Commander tab, A4 = Cockpit tab.**
Whatever you start lives in its tab — keep the window open. (A tab stays open even if its
shell exits, because `sim_tab.sh` ends in `exec bash`.)

### A1 — Isaac Sim tab: spawn the sim drones

Paste as one block (Starling 2 Max model, Isaac window on):
```bash
DRONE_USD=/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd PX4_VEHICLE_MODEL=pegasus_starling2max NUM_ROBOTS=3 SVG_DOMAIN_ID=1 PLAY_SIM_ON_START=true ISAAC_SIM_HEADLESS=false PYTHONPATH="$ISAAC_SIM_PYTHONPATH" /isaac-sim/python.sh /isaac-sim/AirStack/simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py --ext-folder ~/.local/share/ov/data/documents/Kit/shared/exts
```
Wait for `Ready for takeoff!` ×3. Leave running.

| Variant | Change to the line above |
|---|---|
| No Isaac window (lighter) | `ISAAC_SIM_HEADLESS=true` |
| CMU's Iris quad instead of the Starling | drop `DRONE_USD=…` and `PX4_VEHICLE_MODEL=…` |
| ZED camera on one drone (costly — skip unless needed) | add `ENABLE_CAMERA=true CAMERA_DRONES=drone_3` in front |
| CMU's measured 72 ms motor lag (experiments only — it tumbles the attitude loop) | add `STARLING_MOTOR_TAU=0.072` in front |

**What the two Starling variables select** (added 2026-10-19): CMU's sys-ID dynamics
(0.557 kg, k_f 3.96e-6, motor lag off — `Starling2MaxConfig` in the launch log) and our
bind-mounted PX4 airframe `10090_pegasus_starling2max`. Values and sources:
[CONFIG.md](CONFIG.md) "Sim airframe". What in that airframe is real and what is sim-only:

| Sim airframe value | Status |
|---|---|
| Attitude + position gains | = the real Starling 1's PX4 params |
| MPC speed/accel limits (`MPC_XY_VEL_MAX` 20, `MPC_ACC_HOR` 6, `MPC_ACC_HOR_MAX` 1000, `MPC_Z_VEL_MAX_UP/DN` 10/4) | = the real drone's |
| Rate gains × 0.5 + gyro filters `IMU_GYRO_CUTOFF` 80 / `IMU_DGYRO_CUTOFF` 40 | **sim-only** — the real gains give a 9 Hz pitch limit cycle in sim (ledger #10) |
| `LNDMC_ROT_MAX` 300 | **sim-only** — the real drone has 30 (`starling_1_indoor_params.params`) |
| Motor lag off · MAVROS respawn | **sim-only** |

⚠️ **Never port a sim-only value to the drone** (iron rule 9). The drone's parameters come
from `starling_1_indoor_params.params` via QGC.

**Validation state.** Ledger #1–#4 passed 2026-10-19 on the OLD asset, gains and speeds.
A fresh launch on 2026-10-21 (ledger #13) passed: asset complete, no PhysX warnings,
2.0 m/s commanded / ~1.7 flown, all three landed and disarm accepted first try. **Still
pending:** re-run of the 1 m step test (#3) with `scenario:=goal`, and the CBF crossing
distances (#4) at the new speeds. Acceptance tools live in `simulation/isaac-sim/tools/`
(`docker cp` them into the robot container, run with `bash -ic`).

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
You are already in `~/AirStack/robot/ros_ws`; the container's bashrc sourced the workspace
and set `ROS_DOMAIN_ID=1`. Leave running.

- **Rebuild** (`bws && sws` — build the workspace, then source it) is needed only after NEW
  entry points or files, e.g. right after a snapshot bump. Edits to existing `.py`/`.yaml`
  need no rebuild (symlink install).
- **MAVROS respawn (sim only):** a MAVROS node that dies comes back after 2 s, but PX4 has
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
- `use_foxglove_studio:=true` opens Foxglove Studio **inside the container, already
  connected** to `ws://localhost:8765`. First time only, import the layout ([BASESTATION.md](BASESTATION.md) §2):
  container path
  `/root/AirStack/robot/ros_ws/src/svg_ground_control/foxglove/svg_basestation.json`
  (laptop path `~/AirStack-starling-max2/AirStack/robot/ros_ws/src/svg_ground_control/foxglove/svg_basestation.json`).
  Running Studio on the laptop instead: drop the flag, connect to `ws://localhost:8765`,
  import from the laptop path. What "healthy" looks like: [BASESTATION.md](BASESTATION.md) §2.
- The launch also starts the `bag_recorder` node (since 2026-10-20); add `record_bag:=true`
  to record the whole run, or use the panel's Rosbag switch mid-run
  ([BASESTATION.md](BASESTATION.md) §3.12).
- **Speeds:** `cbf_sim.yaml` flies 2.0 m/s cruise with a 4.0 m/s CBF cap. The real-drone
  configs stay ≤ 1.0 m/s — never copy sim speeds into them.

### A4 — Cockpit tab: fly

One call at a time — or the panel's buttons, which call the same services:
```bash
ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger   # arm + climb; wait for "holding takeoff position" ×3 (~30 s)
ros2 service call /swarm_commander/start   std_srvs/srv/Trigger   # scenario live
ros2 service call /swarm_commander/hold    std_srvs/srv/Trigger   # freeze in a hover (also the PANIC button)
ros2 service call /swarm_commander/land    std_srvs/srv/Trigger   # from the hover — never mid-leg
ros2 topic echo /drone_1/interface/mavros/state --once           # expect armed: false
```
Expected landing log in the Commander tab, per drone: `touchdown at z=… settling 2.0 s
before disarm` then `landed, disarmed (attempt 1)`. If PX4 refuses, up to 5 retries 1 s
apart, then ERROR `disarm not accepted after 5 tries` → see the MAVROS note in A2 and
[TROUBLESHOOTING.md](TROUBLESHOOTING.md).

**Live parameters** (no relaunch): `ros2 param set /swarm_commander scenario_speed_mps 1.0`
— the live list is in [SCENARIOS.md](SCENARIOS.md) §3 and §C8 below.

**Fence latched** (`FENCE BREACH` chip, drones frozen — `hold_all` configs)? → `land`, then
`ros2 service call /swarm_commander/reset_fence std_srvs/srv/Trigger` (or the panel's **Reset
Fence**), then `takeoff` + `start` again. `keep_in` configs never latch — the drone brakes at
the wall instead.

### Alternatives to the tabs

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
Pane 0, only after NEW entry points or files (e.g. right after a snapshot bump):
`cd ~/AirStack/robot/ros_ws && bws && sws` — `bws` builds the workspace, `sws` sources it;
the other panes auto-source when it finishes. Edits to existing `.py`/`.yaml` need no
rebuild (symlink install). Every container step below names a pane. Need a shell outside
tmux? `./airstack.sh connect robot --command=bash` still works.
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

**6 — Commander + mocap bridge + Foxglove bridge (+ Studio).** *One-time prereqs (all done
on the previous branch, unchanged): EKF2 params via QGC, vision-hub conf (`en_vio` false /
`offboard_mode` off).* Use **our** config `swarm_real_ours.yaml` (added 2026-10-07: `drone_1`
only, hover z 0.5, `land_speed_mps` 0.6, the validated ±2 m fence, `hold_all`) — the shipped
`swarm_real.yaml` lists three real drones at 1.2 m with `land_speed_mps: 0.3`. Values:
[CONFIG.md](CONFIG.md). Pane 3:
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
| `swarm_real.yaml` | 3 real drones, hover scenario, `hold_all` fence, z 1.2 m | use **`swarm_real_ours.yaml`** (`drone_1`, z 0.5, `land_speed_mps` 0.6, ±2 m fence) — the §B hover config |
| `goal_single.yaml` | **`drone_2`**, `goal` scenario, `keep_in` fence `[-4.5,-5.2,0]..[5.5,4.5,3.0]`, teleop fence on, `cbf_max_speed_mps` **10.0** | use **`goal_single_ours.yaml`** (`drone_1`, ±2 m fence, speeds 1.0, `goal_accel` 3.0, `keep_in` brake 4 / gain 2, `land_speed_mps` 0.6) — the §C config |
| `goal_tracking.yaml` | 3 real drones, **`random_goals`** scenario (ignores goal commands!), 10 m/s | not for one drone — M7 material ([SCENARIOS.md](SCENARIOS.md) §7) |

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
| Sim-only values | sim airframe rate gains ×0.5, gyro filters 80/40, `LNDMC_ROT_MAX` 300, motor lag off, MAVROS respawn — **never port to the drone** (iron rule 9) |
| `target_system` | must equal the drone's `MAV_SYS_ID` — check the `px4_interface` startup line; no ACK = mismatch |
| RC takeover | straight to **MANUAL** or **kill switch** ONLY (POSCTL/ALTCTL leak commander setpoints) |
| After landing | confirm **DISARMED** in QGC before approaching — the panel's Interface column is an ACK log, not an arming display |
| After RC takeover | call `land` once (drone on floor) to reset the commander |
| Container messages to ignore | `Workspace not built yet` (pre-bws) · `groups: … 992` · `unknown-robot` · `LED daemon` warnings with no strip fitted · prompt garbage `[:refused refused reached]` |
| Drone hotspot (`uap0`, SSID `Starling_1_demo_mode` on Starling 1) | never connect the laptop to it |
| Drone power-off | `adb shell shutdown now` (laptop) → wait ~10 s → unplug USB, then battery |
| Drone after re-provisioning | **reboot**, never `systemctl restart voxl-px4` |
