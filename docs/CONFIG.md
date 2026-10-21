# CONFIG — current lab values & what to do when one changes

> **Single source of truth for every value that can drift.** Other docs reference values by
> name; the numbers live HERE. When something changes: update this file, do the "If it
> changes" action, commit.
> Last verified: **2026-10-21** (branch/snapshot, sim airframe, ground-side flight parameters —
> values read from the config yamls and the commander source at `b21d28c`; flight validation
> ⏳ STE) / 2026-09-03 (PX4 flight rows) / 2026-08-28 (mocap rows) / 2026-08-11 (drone/WiFi
> rows) / **2026-09-08** (network rows, GL-MT6000 topology).
>
> **Who reads this:** anyone about to launch, re-provision or tune anything. **Read first:**
> [GLOSSARY.md](GLOSSARY.md) for the words, [MILESTONES.md](MILESTONES.md) §3 for what is
> proven. "The commander" below = the `swarm_commander` node; "the panel" = the Foxglove SVG
> Basestation ([BASESTATION.md](BASESTATION.md)); "the real drone" = our Starling 2 Max.
>
> ⚠️ **Branch switches:** **2026-10-07** the vendored AirStack moved to CMU
> `yikuan/SVG_ground_control` @ `cf719f0`; **2026-10-20** it moved again to CMU's working branch
> `yikuan/SVG_ground_control_dev` @ `b21d28c` (six-gain panel dropdown, `goal_sequence` /
> `figure_eight` scenarios, rosbag switch, live `teleop_max_speed_mps` sync). The ground-side
> section below is read from `b21d28c` — two cf719f0 "traps" are **gone** there
> (`goal_tracking.yaml` ships `goal` again, `goal_single.yaml` targets `drone_1`). Values marked
> **validated** were proven on the previous (`daniel/diffaero`) branch and are our starting
> point; every shipped value that differs is listed so nobody flies a CMU bench number by
> accident. Details: [MIGRATION.md](MIGRATION.md) §7, §11.
>
> ⚠️ **2026-08-27 network change:** the lab moved to the **AI.R STC hangar wired LAN**
> (`192.168.9.x`) for mocap — the 08-11 single-WiFi-network topology below is superseded
> for the mocap path. Mocap now runs through `./mocap.sh` on the laptop ([MOCAP.md](MOCAP.md));
> drone/WiFi rows still describe the 08-11 state and need re-verification on the new network.

*(Unfamiliar term? → [GLOSSARY.md](GLOSSARY.md))*

## Network (router static leases for the key machines — see the leases row; other values still drift)

> 📖 Full router configuration and reproduction steps live in the companion repo
> [ground-control-network-setup](https://github.com/AI-DA-STC/ground-control-network-setup)
> (local clone: `~/Documents/GitHub/ground-control-network-setup`). Topology picture:
> [`pictures/Flight_lab_architecture.png`](../pictures/Flight_lab_architecture.png) (embedded in README).

| Value | Current | How to check | Used by | If it changes → do this |
|---|---|---|---|---|
| Router hardware | **GL.iNet GL-MT6000, OpenWrt** — LAN gateway `192.168.9.1` (also `10.40.0.1` / `10.40.2.1` on its other bridges); admin page row below | companion repo `docs/02-router-setup.md` | Base of the whole lab network (mocap LAN + drone WiFi) | Reproduction steps live in the companion repo |
| Lab LAN subnet | `192.168.9.0/24` (`br-lan`) — the mocap/ground network: laptop wired `.107`, Mocap PC `.100`-lease-but-answers-`.124`, Crazyflies (SSID `motive`). The Starlings live on the `10.40.2.0/23` segment instead (row below) | `ip -4 -brief addr`; router admin page | NatNet pose stream (Motive → laptop); Crazyflie work | — |
| **Drone segment `STARLING`** | `10.40.2.0/23` (gw `10.40.2.1`, `br-lan3`) — the **Starlings** (SSID `StarlingMax2`) plus the laptop's **WiFi** NIC (static lease `10.40.2.107`) | `ip -4 -brief addr` (the `wlp…` row, laptop side); router admin page for drones | The uXRCE-DDS agent link (drone → laptop, UDP 8888); SSH/`scp` to the drone | The drone must be able to reach the laptop IP baked into it — see the "Laptop IP the drone dials" row. Verify with a ping **from the drone** after any network change |
| Static leases (router-side) | The laptop's wired `.9.107`, the laptop's WiFi `10.40.2.107`, and the Mocap PC's `.9.100` are router **static leases** — should NOT drift (the Starlings' addresses on `10.40.2.x` are not pinned yet — read them per session) | Router admin page → DHCP static leases | Re-provisioning scripts; `mocap/motion_capture.yaml` | ⚠️ The Mocap PC currently answers on `.9.124` via a second NIC instead of its leased `.100` — a known MAC-mismatch issue (the lease is pinned to a NIC that isn't the one on the lab LAN), see companion repo `docs/05-known-issues.md#static-lease-mac-mismatch-mocap-pc`. This is exactly why the Motive PC IP row below says `.124`, not `.100` |
| **Laptop IP the drone dials** | must be reachable **from the drone's segment** (`10.40.2.0/23`): the laptop's **WiFi** NIC `10.40.2.107` is same-subnet; its wired `192.168.9.107` also works because the GL-MT6000 routes between the segments. ⚠️ Whichever you bake in, **prove it with a ping from the drone** before flying. (Historical: `192.168.9.107` when the drone was on the lab LAN; `192.168.0.192` in the 08-11 WiFi era) | `ip -4 -brief addr` on the laptop; `ping <laptop IP>` **on the drone** | Baked into the DRONE's dialer by the setup script | **The critical one.** Re-provision the drone: [RUNBOOK](RUNBOOK.md) §B step 0 (`ssh root@<DRONE_IP>` → `voxl_setup_real_drone.sh <body> <laptop IP> <domain> 8888`). Wrong/unreachable value ⇒ step 3 never gets `session established` |
| Laptop Ethernet IP | `192.168.9.107` (AI.R STC hangar wired LAN — **back in use since 2026-08-27, this is the mocap path**; laptop WiFi is `10.40.2.107` on the drone segment) | `ip -4 -brief addr` (the `enp…` row) | mocap bridge listens here; `clientIP:=` if natnet_ros2 is ever used | Nothing to reconfigure for `./mocap.sh` (it listens on all interfaces); update `clientIP:=` only for natnet_ros2 |
| Motive PC IP | `192.168.9.124` (hangar wired LAN, verified 2026-08-28; was `.9.100` earlier on 08-27 — **the hangar assigns IPs by switch port**, so re-check each session; `192.168.0.190` was the 08-11 WiFi-era value) | `ipconfig` on the Motive PC, or `ping` from laptop | `mocap/motion_capture.yaml` `hostname:`; `serverIP:=` for natnet_ros2 | Update `mocap/motion_capture.yaml` in this repo (and commit); `./mocap.sh check` to confirm packets flow |
| **Starling 1 IP** | **designated lease `10.40.2.10`** on the `10.40.2.0/23` drone segment (SSID `StarlingMax2`, MAC `8C:1F:64:69:DD:32`) — but a reboot on 2026-09-16 came up as **`10.40.2.11`** ([CLAUDE.md](../CLAUDE.md) WiFi writeup), so the lease is not pinned to this MAC yet — ⚠️ **the router config may lag the docs: verify the live IP in LuCI (or `voxl-my-ip` on the drone) before relying on it**, and use the live value for `<DRONE_IP>`. (Historical: `192.168.9.10` static lease while the drone sat on the lab LAN under SSID `motive`.) | Router admin page → DHCP leases; or `adb shell voxl-my-ip`; or the agent's `session established` log line | SSH target for re-provisioning ([RUNBOOK](RUNBOOK.md) §B step 0); ping checks | Record the value here once it is a static lease. If it drifts, `ssh root@<DRONE_IP>` and the pull-logs commands in RUNBOOK §D both need the new value |
| Drone SSH login | user `root` · password `oelinux123` (ModalAI factory default — **verified by login 2026-09-01**; the previously-noted `AI.DA@STEngineering` is REJECTED by Starling 1, that credential belongs to something else) (⚠️ lab-LAN device credential stored here deliberately — keep this repo private) | `ssh root@<DRONE_IP>` | RUNBOOK §B step 0 re-provisioning; pulling `.ulg` flight logs from `/data/px4/log/` | Update here if the image/password ever changes |
| Router admin page | `http://192.168.9.1:8080` (hangar router — shows every device's current IP) | open in a browser on the hangar LAN | The authority for ALL drifting IPs; alternatively contact **Jeremy Chia** | — |

## Lab WiFi

| Value | Current | How to check | If it changes → do this |
|---|---|---|---|
| SSID (Starling joins) | **`StarlingMax2`** → puts the drone on the `10.40.2.0/23` segment. (`motive` is the lab-LAN SSID used by the Crazyflies; the Starling sat there historically. Earlier eras: `Mocap_QCGroundControl` 08-11, `AI.R STC Hangar-5G` before that) | `voxl-wifi getmode` on the drone | SSID **without** spaces → `voxl-wifi station '<SSID>' '<PASSWORD>'` works (proven 2026-08-11). SSID **with** spaces → manual `wpa_passphrase` method, archived MILESTONES M3-A (`git show airstack-starling-max2:docs/MILESTONES.md`) step 1 (`voxl-wifi station` corrupts spaced SSIDs). Check the drone's current SSID with `voxl-wifi getmode` |
| Password | (not stored in this repo) | — | Same as above |
| Drone WiFi interface | `mlan0` (station) / `uap0` (its own hotspot, SSID `Starling_1_demo_mode` on Starling 1 — never connect the laptop to it) | `ip -br link` on the drone | Hardware fact, won't change |
| Band / channel | 5 GHz channel 36 (5.180 GHz), 802.11ax — both SSIDs served by the same radio. 2.4 GHz radio is deliberately **disabled** to keep the band clean for Crazyradio | Router admin page → Wireless | Hardware fact, won't change |
| Security | ⚠️ Both `StarlingMax2` (the Starlings, `10.40.2.x`) and `motive` (lab LAN, Crazyflies) are **OPEN networks — no encryption** | Router admin page → Wireless | ⚠️ **Keep the lab network offline — never bridge it to the internet.** WAN port is deliberately unplugged; adding encryption is the fix if that ever changes (companion repo `docs/05-known-issues.md`) |

## Protocol constants (change only if deliberately reconfigured everywhere)

| Value | Current | Used by |
|---|---|---|
| uXRCE agent port | `8888` | Setup script arg **and** `MicroXRCEAgent udp4 -p 8888` — must match |
| DDS domain | `1` (= drone_1) | Setup script arg; container `.bashrc` pins it; sim uses the same. Each ADDITIONAL drone must get a UNIQUE domain ID and its own subnet IP when provisioned |
| NatNet ports | `1510` (cmd) / `1511` (data) | Motive defaults; per-session check: `ss -ulpn \| grep -E ':(1510\|1511)'` must be clear |
| **`target_system` = `MAV_SYS_ID`** (new 2026-10-07) | ⏳ **read `MAV_SYS_ID` back in QGC before the first arm** — the 2026-09-04 params export says **1**, a 2026-09-18 session note on this airframe says it was set to **2**; whichever it is, `target_systems:=` must match | `px4_interface` stamps it on every command; `real_interfaces.launch.py` derives it from the drone name (`drone_2` → 2) or takes `target_systems:=1,2,…`. **Mismatch ⇒ PX4 silently drops every arm/takeoff/land and sends no ACK.** Each additional drone needs a unique `MAV_SYS_ID` |
| Foxglove bridge port | `8765` (`foxglove_port:=` on the commander launch; `address 0.0.0.0`) | Foxglove Studio connects to `ws://localhost:8765` — robot container is host-networked, so "localhost" on the laptop works ([BASESTATION.md](BASESTATION.md) §2) |
| LED daemon ports | drone → laptop **udp/47901** (heartbeat, 1 Hz) · laptop → drone udp/47900 | `led_controller` binds 47901 (one instance only); open it in `ufw` if strips are used ([BASESTATION.md](BASESTATION.md) §8) |
| Commander status snapshot | `/svg/commander_status`, JSON, `status_rate_hz` **5** | the Basestation's only source of mission truth; `NO COMMANDER` after 2 s silence — keep ≥ 1 Hz |
| **Sim airframe — Starling 2 Max** (2026-10-19, re-tuned 2026-10-20) | PX4 airframe `10090_pegasus_starling2max` + USD `simulation/isaac-sim/assets/robots/starling2max.usd` + Pegasus `Starling2MaxConfig` — a **sim-only file**; every number is in the sub-section "Sim airframe" right below this table, with a "sim-only?" column | Select with `DRONE_USD` + `PX4_VEHICLE_MODEL` ([RUNBOOK.md](RUNBOOK.md) §A T1). Rows marked **sim-only — never port to the drone** must never reach a real parameter set |
| Foxglove panel version | `airlab-cmu.svg-basestation-1.0.0` (`foxglove/svg-basestation/package.json`) | `ls ~/.foxglove-studio/extensions` on the laptop. After any panel edit or snapshot bump: re-run `foxglove/install.py` on the laptop, restart Studio, re-import `svg_basestation.json` |


### Sim airframe (Starling 2 Max, sim-only) — `10090_pegasus_starling2max`

The Isaac Sim model of our drone. Three pieces: the **USD** (geometry + mass), the **Pegasus
vehicle config** (motor model) and the **PX4 airframe file** (parameters PX4 SITL boots with).
Most PX4 values are copied **from** the real Starling 1 so the sim flies like the drone; the
rows marked **sim-only — never port to the drone** are deliberate deviations that make the sim
plant behave, and would be wrong on hardware. Real-side values are quoted so a reader can tell
them apart. Source for the identified numbers: `isaac_sim/Starling 2 Max Sys ID Results - Slite.pdf`
(CMU AirLab); airframe comments carry the reasoning.

| Area | In the sim | On the real drone | Sim-only? | Why |
|---|---|---|---|---|
| Inertials / mesh | mass **0.557 kg** = body 477 g + 4 × 20 g rotor rigid bodies (explicit — without them PhysX added 384 g of collider mass) · I = 0.002943 / 0.001857 / 0.004649 kg·m² · CoM (0.00102, 0.00016, 0.00741) m ≈ 1 mm fwd, 7.4 mm up · body mesh = CMU's 1.2 M-face mesh with parts < 2 mm **culled, nothing decimated** → 564 k faces, 99.9 % of the surface, 8 MB (since 2026-10-20) | the thing being modelled (CMU sys-ID of this airframe) | n/a — a model of the drone | the 10-19 quadric-decimated 50 k-face asset was **hollow** (body plates deleted, ledger #9) |
| Thrust / motors (Pegasus `Starling2MaxConfig`) | k_f 3.964738e-6 N/(rad/s)² · k_m 5.38697e-8 N·m/(rad/s)² · ω_max 1450 rad/s via input scaling 1350 (hover ≈ 0.36 actuator) · **motor lag OFF** (`STARLING_MOTOR_TAU=0.072` re-enables CMU's 72 ms first-order lag) · drag = Pegasus default (not identified) | — | sim-only (a motor model) | the 72 ms lag **tumbles** the attitude loop in sim — experiments only |
| Rotor geometry (`CA_ROTOR*_PX/PY`, `_KM`) | ±0.095 / ±0.13 m (CMU CAD), KM 0.0136 | `CA_ROTOR*` ±0.085 / ±0.0625 | **sim-only — never port to the drone** | user decision 2026-10-19: follow CMU's CAD, not the drone's params |
| PX4 outer loops (attitude + position) | `MC_ROLL_P` / `MC_PITCH_P` 8 · `MC_YAW_P` 2.8 · `MPC_XY_P` 0.95 · `MPC_Z_P` 5 · `MPC_XY_VEL_P_ACC` 1.8 · `MPC_Z_VEL_P_ACC` 8 · `MPC_THR_HOVER` 0.165 (thrust **setpoint**; sim measures 0.155) · `THR_MDL_FAC` 0.9 | **identical** (Starling 1's `starling_1_indoor_params.params`) | no — copied FROM the drone | `rc.mc_defaults` (Iris gains) oscillated and ran away on the first sim flights |
| PX4 inner (rate) loops | **×0.5**: `MC_ROLLRATE_P/I/D` 0.032 / 0.05 / 0.00065 · `MC_PITCHRATE_P/I/D` 0.032 / 0.048 / 0.00055 · `MC_YAWRATE` 0.07 / 0.5 / 0 (unchanged) · `IMU_GYRO_CUTOFF` 80 · `IMU_DGYRO_CUTOFF` 40 | ROLLRATE 0.064 / 0.1 / 0.0013 · PITCHRATE 0.064 / 0.096 / 0.0011 (kept in the airframe comments); the 80 / 40 Hz filters ARE the real ones | **sim-only ×0.5 — never port to the drone** | with the real gains every sim drone carried a **9 Hz pitch limit cycle** (±270 °/s); the sim plant has more loop gain (instant motors, 250 Hz IMU, CMU arms) — ledger #10, 2026-10-20 |
| Land detector | `LNDMC_ROT_MAX` **300** °/s | **30** (`starling_1_indoor_params.params`; PX4 default 20) | **sim-only — never port to the drone** | Isaac floor rocking (~10 Hz) kept PX4's `maybe_landed` gate from passing → every DISARM "denied: not landed" — ledger #9 |
| Speed / accel limits | `MPC_XY_VEL_MAX` 20 · `MPC_ACC_HOR` 6 · `MPC_ACC_HOR_MAX` 1000 · `MPC_JERK_AUTO` 4 · `MPC_Z_VEL_MAX_UP` 10 / `_DN` **4** | **identical** (Starling 1 backup, `~/RCC_Starling_1`) | no — copied from the drone 2026-10-20 | were 3 / 3 / PX4 defaults, which **clipped the sim at 3 m/s**; raised in the same commit that put `cbf_sim.yaml` at 4.0 / 2.0 |
| Selection / source | `DRONE_USD=/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd PX4_VEHICLE_MODEL=pegasus_starling2max` on the Isaac launch ([RUNBOOK.md](RUNBOOK.md) §A T1); the airframe file is bind-mounted into PX4's ROMFS source airframes dir by `simulation/isaac-sim/docker/docker-compose.yaml` | — | the whole file is sim-only | env vars unset ⇒ the Iris regression model |

**Validation so far** ([MILESTONES.md](MILESTONES.md) §3c): ledger #1–#4 passed 2026-10-19 on the
*old* asset / gains / speed limits (#3 steps: x overshoot 0.002 m, settled 2.75 s; z 0.001 m,
0.75 s · #4 antipodal crossing min distance 1.02 m at 0.6 / 1.2 m/s). 2026-10-21 fresh launch on the
current asset = ledger #13: asset complete, no PhysX warnings, 2.0 m/s commanded / ~1.7 flown,
landing DISARM accepted first try ×3. ⏳ **Pending:** re-run #3 (`scenario:=goal`) and the #4
distances at the new 2.0 / 4.0 speeds.

## Mocap / Motive

| Value | Current | If it changes → do this |
|---|---|---|
| Rigid body name | `drone_1` (✅ exists — streaming confirmed 2026-08-27, alongside `cf1`/`cf8`) | Must match everywhere — it names the topics (`/drone_1/pose`, `/drone_1/fmu/*`), `MOCAP_BODIES` for `./mocap.sh`, and the swarm config. Rename → update Motive AND every config's `drone_names` (+ `led_controller.drone_names`); restart the bridge (body list read only at startup) |
| Motive frame rate | `50 Hz` (2026-08-28; briefly 240 Hz on 08-27 after a profile edit — it drifts with profile changes) | Informational — expected rate for `ros2 topic hz /drone_1/pose` |
| Streaming settings | Up Axis = Z · Local Interface = Motive IP · **transmission is effectively BROADCAST** (`BroadcastInsteadOfMulticast="true"` in the Motive profile overrides the GUI's "Multicast" — discovered 2026-08-27) | This is WHY natnet_ros2 gets no data and `./mocap.sh` is the receiver — full story [MOCAP.md](MOCAP.md) §3. Re-check the pane whenever poses look wrong: `pictures/check_motive_ip_address.jpg` |
| Pose receiver | `./mocap.sh` on the laptop ([MOCAP.md](MOCAP.md)) — NOT natnet_ros2 in the container | Diagnose with `./mocap.sh check` (6-second wire test with plain-English verdict) |
| World frame | red = x ("East") · green = y ("North") · z up; origin = floor marker | Photos: `pictures/mocap_axis_1.png`, `pictures/mocap_axis_2.png` — used by the M2 frame hand-check |

## PX4 / EKF2 parameters (set once via QGC — since 2026-09-01 QGC runs on the LAPTOP; it ran on the Mocap PC before that)

Confirmed parameter set — applied in the 2026-07-29 QGC session, recorded here 2026-08-11.

| Value | Current | Why / If it changes → do this |
|---|---|---|
| `EKF2_EV_CTRL` | `11` | Always for mocap flight — horiz pos + vert pos + yaw; 3D-velocity bit OFF |
| `EKF2_GPS_CTRL` | `0` | Always for mocap flight |
| `SYS_HAS_MAG` | `0` | Always for mocap flight |
| `EKF2_HGT_REF` | `3` | Always for mocap flight |
| `EKF2_BARO_CTRL` | `0` | Indoor mocap only |
| `EKF2_MAG_TYPE` | `None` | Indoor mocap only |
| `EKF2_EV_DELAY` | `50 ms` (✅ applied — in the .params export 2026-09-04; was 0.0) | Mocap-over-network latency compensation |

> ⚠️ **Outdoor revert:** re-enable `EKF2_BARO_CTRL` and `EKF2_MAG_TYPE` (and GPS/mag params) before any outdoor/GPS flight.

**📦 The canonical full parameter set lives in this repo: [`starling_1_indoor_params.params`](../starling_1_indoor_params.params)**
(872-param QGC export from Starling 1, PX4 v1.14, 2026-09-04 — includes every row in the tables above and below).
To set up a drone: QGC → Vehicle Setup → Parameters → **Tools ⋮ → Load from file** → this file
→ reboot PX4 → spot-check `EKF2_EV_CTRL=11` and `RC_MAP_KILL_SW=8` by read-back. Procedure: archived MILESTONES M4-A — now [DRONE_SETUP.md](DRONE_SETUP.md) §5.

Flight-log-verified additions (2026-09-01/03 sessions):

| Value | Current | Why / If it changes → do this |
|---|---|---|
| `RC_MAP_KILL_SW` | `8` | Kill switch on ch8 — mapped + verified 2026-09-01. NEVER fly without it |
| `COM_RC_OVERRIDE` | `1` | Stick override for auto modes only — sticks do NOT kick offboard out (takeover = flip to MANUAL, see RUNBOOK §C) |
| `COM_OBL_RC_ACT` | `1` | Offboard-loss → Position mode when RC present |
| `MPC_THR_HOVER` | `0.165` (✅ retuned 2026-09-04 — was factory 0.13; true hover measured 0.165–0.17 from flight logs) | Improves takeoff crispness + landing detection |
| `RC_MAP_ARM_SW` | `5` | Arm/disarm switch on ch5 (from `starling_1_indoor_params.params`) — flip down to force disarm on the ground |

## Ground-side flight parameters (svg_ground_control config yamls)

> Config source: `AirStack/robot/ros_ws/src/svg_ground_control/config/`. A yaml is read **once
> at launch** ([RUNBOOK.md](RUNBOOK.md) §C7); the parameters marked **live** below can also be
> changed in flight with `ros2 param set /swarm_commander <name> <value>` or from the panel's
> runtime-gain dropdown ([BASESTATION.md](BASESTATION.md) §3.4, [SCENARIOS.md](SCENARIOS.md) §3).
> **The shipped files are CMU's bench values** (read at `b21d28c`, 2026-10-21). Files marked
> **ours** are what we fly; "validated" = proven on the previous branch, everything else is the
> deliberate starting point, ⏳ STE. ⚠️ = a CMU value we must not fly as-is.

**Which config for what** (⚠️ no shipped CMU file is flyable as-is — [MIGRATION.md](MIGRATION.md) §7):

| Purpose | File | Notes |
|---|---|---|
| Hover / first real flight (M3) | **`swarm_real_ours.yaml`** (ours, 2026-10-07) | `drone_1` only, hover z 0.5, `land_speed_mps` 0.6, fence `[-2,-2,0]..[2,2,2]`, vmax 1.0, `hold_all`, `land_settle_s` 0.0. Derived from `swarm_real.yaml` (3 real drones, z 1.2, `land_speed_mps` 0.3 ⚠️) |
| Goal flights (M4) | **`goal_single_ours.yaml`** (ours, 2026-10-07) | `drone_1`, `goal`, `keep_in` (brake 4, gain 2), speeds 1.0, `goal_accel` 3.0, `land_speed_mps` 0.6, teleop fence off, nobody exempt. Derived from `goal_single.yaml` (speeds **10.0** ⚠️, `land_speed_mps` 0.8, `drone_1` **exempt** — at `cf719f0` it targeted `drone_2`; fixed upstream at `b21d28c`) |
| Gamepad (M5) | `teleop_real.yaml` (still CMU's) | 1 real drone, `keep_in` + teleop fence, `dragonrise_usb`, `land_speed_mps` 0.3 ⚠️ → derive `teleop_real_ours.yaml` before M5: fences to our net, controller to ours, `land_speed_mps` 0.6 ([TELEOP.md](TELEOP.md)) |
| Sim CBF demo (M1) | **`cbf_sim.yaml`** (ours since 2026-10-19/20) | 3 sim, `antipodal` (override with `scenario:=`), `scenario_speed_mps` **2.0**, `cbf_max_speed_mps` **4.0**, `goal_accel_mps2` **6.0**, `land_speed_mps` 1.0, settle 2.0 s + disarm retry 1.0 s × 5. Real-demo speeds; `ros2 param set` overrides live |
| Other sim files | `swarm_sim.yaml`, `teleop_single.yaml`, `squeeze_3drone.yaml`, `goal_tracking_original.yaml` | as shipped, for M1 sim rehearsals (`goal_tracking_original.yaml` is CMU's pre-mocap 3-drone sim file, new 2026-10-20, reference only) |
| Multi-drone real (M7 only) | `goal_tracking.yaml`, `squeeze_rc_intruder.yaml`, `hybrid_squeeze.yaml`, `goal_sequence.yaml`, `figure_eight_rc_intruder.yaml` | 3 real drones, 10 m/s caps ⚠️. `goal_tracking.yaml` ships **`goal`** again at `b21d28c` (it was `random_goals` at `cf719f0`); `goal_sequence` / `figure_eight` are new 2026-10-20 — sim rehearsal = copy their `sequence_*` / `figure_eight_*` blocks into a `cbf_sim`-style config with `drone_modes: "sim,sim,sim"` |

**Config × parameter matrix** — every file, read from the yamls at `b21d28c` (2026-10-21). A dash
means the key is absent and the commander's default applies (defaults: `fence_behavior hold_all`,
α 2.5, r 0.55, vmax 1.2, `scenario_speed` 0.6, `goal_accel` 3.0 / `goal_settle` 0.3,
`teleop_max_speed` 1.2 / `teleop_accel` 0, `land_speed` 0.3, `land_settle_s` 2.0,
`land_disarm_retry_s` 1.0 × `land_disarm_retries` 5, `takeoff_speed` 0.5, arena
`[-2,-2,0.8]..[2,2,2]`). **Ours** rows in bold.

*A — mission, CBF and speeds* (α / r / vmax = `cbf_alpha` / `cbf_safety_radius_m` / `cbf_max_speed_mps`):

| Config | Drones · modes | `scenario` | α / r / vmax | `scenario_speed` | `goal_accel` / `goal_settle` | `teleop_max_speed` / `teleop_accel` | exempt · teleop · takeoff speed |
|---|---|---|---|---|---|---|---|
| `swarm_real.yaml` | 3 real | `hover` | 2.5 / 0.55 / 1.0 | 0.5 | — / — | 1.0 / — | — · — · 0.5 |
| **`swarm_real_ours.yaml`** | **`drone_1` real** | `hover` | 2.5 / 0.55 / 1.0 | 0.5 | — / — | **0.5** / — | — · — · 0.5 |
| `goal_single.yaml` | `drone_1` real | `goal` | 2.5 / 0.55 / **10.0** ⚠️ | **10.0** ⚠️ | **10.0** ⚠️ / 0.2 | **8.0** ⚠️ / 5.0 | exempt **`drone_1`** ⚠️ (filter off) · — · 0.5 |
| **`goal_single_ours.yaml`** | **`drone_1` real** | `goal` | 2.5 / 0.55 / 1.0 | 1.0 | 3.0 / 0.3 | 0.5 / 5.0 | — · — · 0.5 |
| `goal_tracking.yaml` | 3 real | **`goal`** (was `random_goals` at cf719f0) | 2.5 / 0.55 / **10.0** ⚠️ | **10.0** ⚠️ | **10.0** ⚠️ / 0.2 | **8.0** ⚠️ / 5.0 | — · — · 1.0 |
| `goal_tracking_original.yaml` | 3 (no `drone_modes` → sim) | `goal` | CMU's pre-mocap sim original — reference only | | | | |
| `teleop_real.yaml` | `drone_1` real | `hover` | 2.5 / 0.55 / 0.7 | 0.5 | — / — | 0.7 / 5.0 | — · teleop `drone_1` · 0.5 |
| **`cbf_sim.yaml`** (ours since 10-19) | 3 sim | `antipodal` | 2.5 / 0.55 / **4.0** | **2.0** | **6.0** / — | — / — | — · — · 0.5 |
| `swarm_sim.yaml` | 3 sim | `hover` | 2.5 / 0.55 / 2.0 | 0.6 | — / — | 2.0 / — | — · — · 0.5 |
| `squeeze_3drone.yaml` | 3 sim | `squeeze` | 2.5 / 0.55 / 1.2 | 0.6 | — / — | 1.2 / — | exempt `drone_3` · — · 0.5 |
| `teleop_single.yaml` | `drone_1` sim | `hover` | 2.5 / 0.55 / 2.0 | 0.6 | — / — | 2.0 / 5.0 | — · teleop `drone_1` · 0.5 |
| `hybrid_squeeze.yaml` | real, real, sim | `squeeze` | 2.5 / 0.55 / 1.0 | 0.5 | — / — | — / — | exempt `drone_3` · — · 0.5 |
| `squeeze_rc_intruder.yaml` | 3 real | `squeeze` | 2.5 / 0.55 / **10.0** ⚠️ | **10.0** ⚠️ | **10.0** ⚠️ / 0.2 | 3.0 / 5.0 | exempt + teleop `drone_3` · 1.0 |
| `goal_sequence.yaml` (new 10-20) | 3 real | `goal_sequence` | 2.5 / 0.55 / **10.0** ⚠️ | **6.0** ⚠️ | **10.0** ⚠️ / 0.2 | 3.0 / 5.0 | — · — · 1.0 |
| `figure_eight_rc_intruder.yaml` (new 10-20) | 3 real | `figure_eight` | 2.5 / 0.55 / **10.0** ⚠️ | 2.0 | **10.0** ⚠️ / 0.2 | 3.0 / 5.0 | exempt + teleop `drone_3` · 1.0 |

*B — landing, hover height and fences* (brake, gain = `fence_brake_accel_mps2`, `fence_keep_in_gain`):

| Config | `land_speed` | `land_settle_s` / retry | `land_complete_alt` | `hover_positions` z | `fence_behavior` (brake, gain) | `fence_min..max` | teleop fence |
|---|---|---|---|---|---|---|---|
| `swarm_real.yaml` | 0.3 ⚠️ | — / — | 0.15 | 1.2 | `hold_all` (4, 1) | `[-4,-2,0]..[4,2,3]` | — |
| **`swarm_real_ours.yaml`** | **0.6** ✅ | **0.0** / — | 0.15 | **0.5** at `(-0.5, 0, 0.5)` | `hold_all` (4, 1) | **`[-2,-2,0]..[2,2,2]`** | off |
| `goal_single.yaml` | 0.8 | — / — | **0.1** | 1.0 | `keep_in` (8, 2) | `[-4.5,-5.2,0]..[5.5,4.5,3]` | `[-3.5,-4.2,0.5]..[4.5,3.5,2.5]` |
| **`goal_single_ours.yaml`** | **0.6** ✅ | **0.0** / — | 0.15 | **0.5** at `(-0.5, 0, 0.5)` | `keep_in` (4, 2) | **`[-2,-2,0]..[2,2,2]`** | off |
| `goal_tracking.yaml` | 1.0 | — / — | 0.15 | 1.2 | `keep_in` (8, 2) | `[-4.5,-5.2,0]..[5.5,5,3]` | — |
| `teleop_real.yaml` | 0.3 ⚠️ | — / — | 0.15 | 1.2 | `keep_in` (4, 2) | `[-4,-2,0]..[4,2,3]` | `[-3,-1.5,0.3]..[3,1.5,2.5]` |
| **`cbf_sim.yaml`** | 1.0 | **2.0** / **1.0 s × 5** | 0.15 | 1.2 | — (→ `hold_all`) | `[-3,-6,0]..[5,5,3]` | — |
| `swarm_sim.yaml` | 0.3 | — / — | 0.15 | 1.2 | `hold_all` (4, 1) | `[-4,-2,0]..[4,2,3]` | — |
| `squeeze_3drone.yaml` | 0.3 | — / — | 0.15 | 1.2 | `hold_all` (4, 1) | `[-4,-2,0]..[4,2,3]` | — |
| `teleop_single.yaml` | 0.3 | — / — | 0.15 | 1.2 | `keep_in` (2, 0.7) | `[-4,-2,0]..[4,2,3]` | `[-3,-1.5,0.3]..[3,1.5,2.5]` |
| `hybrid_squeeze.yaml` | 0.3 | — / — | 0.15 | 1.2 | `hold_all` (4, 1) | `[-4,-2,0]..[4,2,3]` | — |
| `squeeze_rc_intruder.yaml` | 1.0 | — / — | 0.15 | 1.2 | `keep_in` (8, 2) | `[-4.5,-5.2,0]..[5.5,5,3]` | `[-3.3,-4.0,1.0]..[4.3,4.2,2.8]` |
| `goal_sequence.yaml` | 1.0 | — / — | 0.15 | 1.2 | `keep_in` (8, 2) | `[-4.5,-5.2,0]..[5.5,5,3]` | `[-3.3,-4.0,0.7]..[4.3,4.2,2.8]` |
| `figure_eight_rc_intruder.yaml` | 1.0 | — / — | 0.15 | 1.2 | `keep_in` (8, 2) | `[-4.5,-5.2,0]..[5.5,5,3]` | `[-3.3,-4.0,0.7]..[4.3,4.2,2.8]` |

All CMU fence/arena boxes are **CMU's room** — redraw to our net before any real flight
([MOCAP.md](MOCAP.md) §6.1). Only the `_ours` files are drawn to ours (and even those ⏳ re-check
against the net on the day).

**What each parameter means** — meaning, whether it is live, and what we fly. "Live" = settable
in flight (`_RUNTIME_ATTRS` + `_SCENARIO_PARAMS` in `SwarmCommander`); everything else is refused
with a reason naming what *is* live (`SwarmCommander.on_parameter_change`), yaml + relaunch.

| Parameter | Meaning | Live? | Ours | Why / If it changes → do this |
|---|---|---|---|---|
| `land_speed_mps` | descent speed while LANDING | no | **`0.6`** (**validated 2026-09-03**, previous branch) for the real drone; 1.0 in `cbf_sim` | 0.3 caused **armed-on-ground landings** (slow touchdown bounces past PX4's land detector). Re-confirm at M3. ⚠️ The comment beside this key in `cbf_sim.yaml` ("PX4 caps descent at `MPC_Z_VEL_MAX_DN` = 1.0 m/s") is **stale since 2026-10-20** — the sim airframe now sets 4.0; the yaml comment is left as-is |
| `land_complete_altitude_m` | height at which the commander calls the descent done and starts the settle | no | 0.15 | lower = later disarm shot (`goal_single` ships 0.1) |
| `land_settle_s` | **ours, 2026-10-19.** How long the drone stays LANDING (descent still commanded) after z ≤ `land_complete_altitude_m` before the DISARM | **yes** | code default 2.0; **`cbf_sim.yaml` 2.0 · real `_ours` configs 0.0** | 0 = CMU's original instant disarm, which PX4 **DENIED** in sim (not landed yet) → offboard timeout → armed failsafe hover. CMU's shipped real configs omit the key → inherit 2.0 → **use the `_ours` files**, which keep the landing exactly as flown 09-03 until the settle is its own M3 sub-test. Raise if QGC still shows "Disarming denied"; PX4's own `COM_DISARM_LAND` may fire first — fine |
| `land_disarm_retry_s` / `land_disarm_retries` | **ours, 2026-10-20.** A DISARM the interface rejects is resent every `land_disarm_retry_s` while the descent is still commanded, up to `land_disarm_retries` times, then IDLE anyway with an ERROR log (`SwarmCommander.land_disarm_step`) | **yes** | 1.0 s / 5 (code defaults, also written in `cbf_sim.yaml`) | Sim 2026-10-20 (ledger #8): settle alone was accepted on 1 of 3 drones; 2026-10-21 (ledger #13): accepted first try ×3. **Inert on the real drone**: `px4_interface`'s `disarm()` returns true on send, so there is never a rejection to retry — the settle + retry is **unflown** on real |
| `hover_positions` | takeoff target AND initial goal — **takeoff flies to the ABSOLUTE point**; place the drone there | no | `(-0.5, 0.0, 0.5)` — z 0.5 low-and-safe (previous-branch value) | CMU ships z 1.2 (`swarm_real`) / 1.0 (`goal_single`). Raise toward 1.0–1.2 if ground effect wobbles |
| `takeoff_speed_mps` | climb speed of the takeoff | **yes** | 0.5 | CMU's 3-drone real files ship 1.0 |
| `fence_enabled` / `fence_min` / `fence_max` | the geofence box, mocap frame, floats only | no (geometry) | **draw to OUR net** before every config is flown (`_ours`: `[-2,-2,0]..[2,2,2]`) | [MOCAP.md](MOCAP.md) §6.1 golden rule |
| `fence_behavior` | what a breach does: `hold_all` = everyone freezes until `reset_fence` (also latched by an airborne RC/external drone); `keep_in` = brake at the wall, nobody freezes — [TELEOP.md](TELEOP.md) §6 | no | `hold_all` for M3, `keep_in` from M4 | — |
| `fence_brake_accel_mps2` | the `keep_in` braking envelope | **yes** | 4.0 to start | keep ≥ `goal_accel_mps2` or the wall caps cruise speed; **0 silently reverts to the old gain × distance barrier**. CMU's `goal_*` / `squeeze_rc` / `goal_sequence` / `figure_eight` ship **8.0** against accel 10 — violates their own rule |
| `fence_keep_in_gain` | near-wall gain; `1/gain` = lag margin | **yes** (must stay > 0) | 1.0 (`_ours` goal config: 2.0) | — |
| `fence_margin_m` | inset from the wall | **yes** | 0.0 | — |
| `teleop_fence_enabled/min/max` | the smaller amber box only hand-flown drones see — [TELEOP.md](TELEOP.md) §6 | no | **draw inside OUR geofence** — launch raises if it isn't | off in both `_ours` files |
| `cbf_alpha` | how early the CBF yields (bigger = later, harder) — [SCENARIOS.md](SCENARIOS.md) §1 | **yes** (> 0) | 2.5 | — |
| `cbf_safety_radius_m` | half the minimum centre-to-centre distance | **yes** (> 0) | 0.55 | the scenario keeps its launch-time value for spacing (SCENARIOS §3) |
| `cbf_max_speed_mps` | the hard cap on anything the commander sends — also the dodge authority | **yes** (> 0) | **1.0** for M3/M4, raise deliberately; **4.0** in `cbf_sim` (sim only) | 10.0 (five CMU real files) is 10 m/s of dodge authority indoors. Panel slider ends at `cbfSpeedMax` = 3 by default — type 4.0 in the number box or raise the setting ([BASESTATION.md](BASESTATION.md) §3.4) |
| `cbf_exempt_drones` / `external_drones` | an exempt drone's command goes out unfiltered and the others absorb 100 % of the dodge; two exempt/external drones get **no** mutual protection | no | `""` | `drone_3` in the squeeze / figure-eight files; **`drone_1` in `goal_single.yaml`** (harmless with one drone — but the filter is then off) |
| `scenario_speed_mps` | goal-law cruise speed; `speed_command` overrides per drone | **yes** | 1.0 real; **2.0** `cbf_sim` | — |
| `goal_accel_mps2` / `goal_settle_s` | the acceleration-limited go-to-goal profile (accel AND braking) + exponential tail; `goal_accel` also caps the CBF feedforward | **yes** (accel > 0, settle ≥ 0) | 3.0 / 0.3 real; **6.0** / 0.3 `cbf_sim` | editable from the panel's gain dropdown since 2026-10-20; reported in the status `tuning` block |
| `teleop_max_speed_mps` ↔ `safe_teleop` `max_speed_mps` | stick full-scale velocity. Since 2026-10-20 **ONE number kept equal both ways** (`sync_max_speed`); the panel's Teleop vmax row sets both. The commander clamps to the smallest of this and `cbf_max_speed_mps` | **yes** (> 0) | **0.5** (M5) | CMU ships 0.7 (`teleop_real`) · 2.0 (sim) · 3.0 (`squeeze_rc`, `goal_sequence`, `figure_eight`) · **8.0** ⚠️ (`goal_*`) |
| `teleop_accel_mps2` | stick ramp, fed forward to PX4 (0 = off) | **yes** | 5.0 for M5 | — |
| `goal_lead_m` / `hold_lead_m` / `teleop_lead_m` | reference-point leashes | **yes** | 2.0 / 0.2 / 0.5 as shipped | **keep `hold_lead_m` small** (0.2) — a 1.3 m lead above a grounded drone doubled its hover height in a CMU bag |
| `sequence_steps`, `sequence_<name>`, `sequence_dwell_s` 2.0, `sequence_arrival_m` 0.3, `sequence_loop` true, `sequence_advance` arrival\|timer, `sequence_period_s` 8.0 | the `goal_sequence` scenario (new 2026-10-20) | no | `goal_sequence.yaml` only | the commander refuses a set outside the arena or with two goals closer than 2r |
| `figure_eight_center/radius_m/center_distance_m/axis_deg/tilt_deg/senses/track_gain/intruder_start/intruder_cbf_exempt` | the `figure_eight` scenario (new 2026-10-20) | no | `figure_eight_rc_intruder.yaml` only | — |
| launch `use_bag_recorder` true, `record_bag` false, `bag_dir`, `bag_prefix` svg, `bag_include_hidden` false | the switchable rosbag recorder (new 2026-10-20) | — | as shipped | [BASESTATION.md](BASESTATION.md) §3.12 |
| `teleop_controller` (`safe_teleop` block) | which gamepad profile | no | ⏳ **identify ours** with `ros2 run svg_ground_control joy_map` → record here | `dragonrise_usb` in every shipped config; config beats the node default (`xbox_usb`); wrong profile + a trigger pad = full stick on an untouched axis (the axis guard refuses) — [TELEOP.md](TELEOP.md) §3. ⚠️ `./svg_teleop.sh` passes no config, so it always runs `xbox_usb` |
| `yaw_sign` (`safe_teleop` block) | flips the yaw stick | no | `1.0` ⏳ verify at M5, slow and low | unverifiable in sim (`px4_interface` negates yaw rate) |
| `real_command_mode` | `trajectory` = position + velocity + acceleration on `/{name}/fmu/trajectory_command`; `velocity` = the old bare-velocity topic | no | `trajectory` | `px4_interface` must be rebuilt for it |
| `use_led` / `led_controller.brightness` | LED strips | no | true (harmless with no strip) / 80 | keep brightness low near the mocap cameras |
| After every landing | — | — | confirm **DISARMED in QGC** | the commander's "landed, disarmed" log is optimistic; the panel's Interface column is an ACK log, not an arming display |

## Drone-side voxl-vision-hub config (`/etc/modalai/voxl-vision-hub.conf` on the drone)

Required values for mocap flight — cross-reference archived MILESTONES M4-A — now [DRONE_SETUP.md](DRONE_SETUP.md) §5.

| Value | Required | Why / If it changes → do this |
|---|---|---|
| `"en_vio"` | `false` | EKF2 must use mocap, not VIO. After editing the file: `systemctl restart voxl-vision-hub` |
| `"offboard_mode"` | `"off"` | vision-hub must not inject offboard commands. Same restart after editing |

## Drone-side voxl-mavlink-server config (`/etc/modalai/voxl-mavlink-server.conf`) — QGC link

The drone PUSHES MAVLink to a fixed GCS IP; QGC itself needs no configuration (it listens on
UDP 14550). ✅ Set 2026-08-11 (drone→Mocap PC ping verified 3–7 ms).

| Value | Current | If it changes → do this |
|---|---|---|
| `"primary_static_gcs_ip"` | the **laptop's** hangar-LAN IP, `192.168.9.107` (QGC moved to the laptop for the 09-01→03 flight sessions and connected — ⚠️ value inferred from that, verify by read-back on the drone; history: `192.168.0.190` = Mocap PC 08-11, factory `192.168.8.10`) | Set to the QGC machine's current IP, then `systemctl restart voxl-mavlink-server`; QGC connects within seconds. Read-back: `ssh root@<DRONE_IP> "grep gcs_ip /etc/modalai/voxl-mavlink-server.conf"` |
| `"primary_static_gcs_ip_port"` | `14550` | QGC's default listen port — leave it |

## Files & identities

| Value | Current |
|---|---|
| Working folder (laptop) | `~/AirStack-starling-max2/AirStack` — on the new `main` since 2026-10-07 18:30 (container recreated, workspace rebuilt clean; old-branch config edits backed up in `~/AirStack-starling-max2-local-edits-2026-10-07/`) |
| **AirStack branch / snapshot** | CMU `yikuan/SVG_ground_control_dev` @ **`b21d28c`** since **2026-10-20** (patch `cf719f0..b21d28c` applied over the 10-07 snapshot; tests 181/181 at the bump, **185 passed** 2026-10-20 with our landing tests; robot container NOT rebuilt — only `bws` + panel `install.py`). Before that `yikuan/SVG_ground_control` @ `cf719f0`, vendored into `AirStack/` on **2026-10-07** (repo commit `91376aa`). Sibling of the previous `daniel/diffaero_ground_control` @ `f544c743` (common ancestor `a46f04b`), frozen at tag `airstack-starling-max2` / branch `archive/airstack-starling-max2`. Patch 0001 applied in-tree; patch 0002 fixed upstream; NatNet SDK NOT vendored (`install_sdk.sh`). **How to check:** `git log -1 -- AirStack` in this repo. **If it changes:** read [MIGRATION.md](MIGRATION.md), do its §6 re-do list, restart the MILESTONES ladder |
| Real-run configs | hover/first flight: **`swarm_real_ours.yaml`** · goals: **`goal_single_ours.yaml`** · gamepad: `teleop_real.yaml` (still CMU's values — derive `teleop_real_ours.yaml` before M5) — all under `<workspace>/src/svg_ground_control/config/`. The shipped 3-drone files are M7 material |
| Gamepad | ⏳ model unknown — identify with `joy_map`, record the `teleop_controller` profile name here |
| uXRCE client keeper on the drone | ⏳ decide: `svg-microdds-watchdog` (installed by the new provisioning script) **or** our `voxl-dds-retry.service` — not both |
| Drone identity | `starling2-max (D0012)` · image 1.8.08 · voxl-suite 1.6.4~beta5 |
| Drone factory backup | `/usr/bin/voxl-px4-start.FACTORY-ORIGINAL` (on drone) + `drone-backups/voxl-px4-start.original-D0012` in this repo (✅ both taken 2026-07-22, before the setup script ran) |

## 60-second fixes for the usual suspects

Moved to [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## When static leases arrive (Wayne/Ryzal)

Update the Network table above, re-run the setup script once with the final laptop IP, and
the per-session IP checks in [RUNBOOK.md](RUNBOOK.md) §B step 1 become a formality.
