# DRONE_SETUP — provision a NEW Starling from the box

> **Who this is for:** any lab member adding a factory-fresh ModalAI Starling (2 Max) to the
> AirStack + mocap rig. Follow top-to-bottom; every checkbox points at the detailed doc
> section that explains it. Budget **~half a day** (WiFi join and QGC params dominate;
> the kill ground test needs the hangar).
>
> **What you need:** the laptop already set up per README "Setting up AirStack on a NEW
> machine" Steps 1–5 · a charged drone battery · a USB-C cable (adb) · the RC transmitter ·
> reflective markers · access to the Motive PC and the hangar LAN.
>
> **📝 Record as you go:** every value you discover (IP, image version, domain ID, rigid-body
> name) goes into [CONFIG.md](CONFIG.md)'s tables the moment you learn it, and each passed
> check earns a row in the [MILESTONES.md](MILESTONES.md) §3c test ledger. Throughout,
> `drone_N` = this drone's number (drone_1 is taken by Starling 1 / D0012).

*(Unfamiliar term? → [GLOSSARY.md](GLOSSARY.md))*

## 0 · Prerequisites (before touching the drone)

- [ ] Laptop fully set up: README Steps 1–5 done once (clone, host setup, robot image build, setup check, host mocap bridge) — README §"Setting up AirStack on a NEW machine".
- [ ] Battery charged and clicked in; USB-C cable to hand; RC transmitter charged.
- [ ] Know today's lab values before you start: SSID, router admin page, laptop Ethernet IP — CONFIG.md Network + Lab WiFi tables.

## 1 · First contact over USB (adb)

- [ ] Plug in USB-C, power the drone; `adb devices` lists it and `adb shell` lands in the MODAL AI banner — MILESTONES M3-A (screenshot at the top of that section).
- [ ] Record the drone's identity from the banner (model, serial like D00xx, image version, voxl-suite version) → new "Drone identity" row in CONFIG.md §Files & identities.
- [ ] **Factory backup BEFORE any script runs:** on the drone `cp /usr/bin/voxl-px4-start /usr/bin/voxl-px4-start.FACTORY-ORIGINAL` — MILESTONES M3-A step 2.
- [ ] On the laptop: `adb pull /usr/bin/voxl-px4-start ~/AirStack-starling-max2/drone-backups/voxl-px4-start.original-D00xx` and commit it — MILESTONES M3-A step 2 / `drone-backups/` convention.

## 2 · Join the drone to the lab WiFi

- [ ] Current SSID is `motive` (no spaces) → on the drone: `voxl-wifi station 'motive' '<PASSWORD>'` — CONFIG.md §Lab WiFi; password not stored in the repo, ask Jeremy Chia.
- [ ] ⚠️ If the SSID ever has SPACES do NOT use `voxl-wifi station` (it corrupts the config) — use the manual `wpa_passphrase` method — MILESTONES M3-A step 1.
- [ ] Verify association: `iw dev mlan0 link` shows Connected (5 GHz can take >10 s) — MILESTONES M3-A step 1.
- [ ] Reboot the drone once and re-check `iw dev mlan0 link` — WiFi must survive reboot (`wpa_supplicant@mlan0` auto-starts) — MILESTONES §3c open issue "WiFi reboot-persistence".
- [ ] If `mlan0` vanishes after reboot (dmesg `Firmware Init Failed`): cold power cycle, battery + USB out 10 s — [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
- [ ] Never connect the laptop to the drone's own hotspot `uap0` (SSID like `Starling_N_demo_mode`) — CONFIG.md §Lab WiFi.

## 3 · Record the drone's IP

- [ ] Read the DHCP lease: `voxl-my-ip` or `ip -4 addr show mlan0` on the drone; cross-check on the router admin page `http://192.168.9.1:8080` — CONFIG.md Network table.
- [ ] Add a "Starling N IP (hangar network)" row to CONFIG.md's Network table (the hangar assigns IPs by port — note the date) — CONFIG.md header convention.
- [ ] Confirm SSH works: `ssh root@<DRONE_IP>` with password `oelinux123` (ModalAI factory default) — CONFIG.md "Drone SSH login" row.

## 4 · Point PX4 at the laptop (uXRCE-DDS provisioning)

- [ ] Pick this drone's **UNIQUE DDS domain ID** — every additional drone gets its own domain (drone_1 = 1, so drone_2 = 2, …); record it in CONFIG.md §Protocol constants — CONFIG.md "DDS domain" row / MILESTONES M3-A step 3 multi-drone rule.
- [ ] Push the script: `adb push AirStack/robot/ros_ws/src/svg_ground_control/scripts/voxl_setup_real_drone.sh /usr/bin/` then `chmod +x` it on the drone — MILESTONES M3-A step 3.
- [ ] Run it on the drone: `voxl_setup_real_drone.sh drone_N <LAPTOP_IP> <UNIQUE_DOMAIN> 8888` (laptop Ethernet IP from CONFIG.md; port must stay 8888) — RUNBOOK §B step 0 / MILESTONES M3-A step 3.
- [ ] Expect two red herrings: "PX4 server not running" during the ~30 s PX4 reboot (just retry), and `Running, disconnected` until the laptop agent is up — MILESTONES M3-A step 3 screenshot notes.
- [ ] Start the agent in the robot container (`MicroXRCEAgent udp4 -p 8888 -v4`) and verify on the drone: `px4-microdds_client status` → **Running, connected**, Agent IP = laptop — MILESTONES M3-B / RUNBOOK §B step 3.
- [ ] Revert recipe exists if anything goes wrong (restore `.FACTORY-ORIGINAL` + reset the flash-saved domain param) — MILESTONES M3-A "Full revert to factory".

## 5 · PX4 parameters (QGC fast path)

- [ ] Connect QGC on the laptop (drone pushes MAVLink to `primary_static_gcs_ip` — set the laptop's IP in `/etc/modalai/voxl-mavlink-server.conf` + `systemctl restart voxl-mavlink-server`) — CONFIG.md §voxl-mavlink-server.
- [ ] Load the full validated set: QGC → Vehicle Setup → Parameters → Tools ⋮ → **Load from file** → [`starling_1_indoor_params.params`](starling_1_indoor_params.params) — MILESTONES M4-A fast path / CONFIG.md §PX4 params.
- [ ] ⚠️ drone_2+ note: the file is Starling **1**'s export — review per-drone params (calibrations, `MPC_THR_HOVER` trim, RC binding-specific values) before accepting wholesale — MILESTONES M4-A.
- [ ] Reboot PX4 (power cycle or QGC reboot) so everything takes effect — MILESTONES M4-A fast path.
- [ ] **Spot-check by READ-BACK** in the Parameters search box: `EKF2_EV_CTRL=11`, `RC_MAP_KILL_SW=8`, `EKF2_BARO_CTRL=0` — only a read-back counts (ledger #7's lesson) — MILESTONES M4-A / CONFIG.md §PX4 params.
- [ ] Note for later: these are INDOOR mocap params — outdoor/GPS flight needs the revert listed in CONFIG.md §PX4 params warning.

## 6 · Drone-side vision-hub config (NOT in the .params file)

- [ ] Edit `/etc/modalai/voxl-vision-hub.conf` on the drone: `"en_vio": false` and `"offboard_mode": "off"` — MILESTONES M4-A step 2.
- [ ] **Verify by READ-BACK** (`cat` the file and read the live values) — the 2026-07-29 edit was silently never saved and sat wrong for two weeks; only a read-back counts — MILESTONES ledger #7.
- [ ] `systemctl restart voxl-vision-hub` so it takes effect — MILESTONES M4-A step 2 / CONFIG.md §voxl-vision-hub.

## 7 · Motive rigid body

- [ ] Attach 4–5 reflective markers in an **asymmetric** pattern (no two spacings alike) — [MOTIVE.md](MOTIVE.md) §3 (detail: MILESTONES M2 step 1).
- [ ] In Motive create a rigid body named **exactly `drone_N`** (lowercase + underscore — topic names come from it), with the drone's forward axis on global **+X** — [MOTIVE.md](MOTIVE.md) §3 / CONFIG.md §Mocap.
- [ ] Check the Data Streaming pane: Up Axis = Z, streaming enabled, Local Interface = Motive PC IP — [MOTIVE.md](MOTIVE.md) §4 / `pictures/check_motive_ip_address.jpg`.
- [ ] Add the body to `MOCAP_BODIES` for `./mocap.sh` and restart the bridge (body list is read only at startup); verify per [MOCAP.md](MOCAP.md) — CONFIG.md "Rigid body name" row.

## 8 · RC transmitter + kill switch (safety-critical)

- [ ] Bind the transmitter to the drone's receiver (hardware-specific) — MILESTONES M6-A step 1.
- [ ] Calibrate sticks: QGC → Vehicle Setup → Radio — MILESTONES M6-A step 2.
- [ ] Confirm the safety params (loaded in §5, re-check): `RC_MAP_KILL_SW=8`, `COM_RC_OVERRIDE=1`, `COM_OBL_RC_ACT=1` — MILESTONES M6-A step 3 / CONFIG.md §PX4 params.
- [ ] **Kill ground test — props OFF, drone strapped down:** arm via a software `takeoff`, flip the kill switch, motors must cut instantly — MILESTONES M6-A step 4.
- [ ] Repeat the kill ground test after ANY transmitter/receiver change, forever — MILESTONES M6-A step 5.
- [ ] Brief every pilot: RC takeover = MANUAL or kill only, never POSCTL/ALTCTL — MILESTONES §3c open issues.

## 9 · Acceptance (all pass BEFORE props go on)

- [ ] Agent `session established` and all 24 `/drone_N/fmu/*` topics on the laptop — MILESTONES M3-B exit / RUNBOOK §B step 3.
- [ ] Mocap pose: `ros2 topic hz /drone_N/pose` ≈ 50 Hz in the robot container, tracks the hand-carried drone — MOCAP.md / MILESTONES ledger #13.
- [ ] EKF2 fusion in → out: `fmu/in/vehicle_visual_odometry` feeding, `fmu/out/vehicle_odometry` positions match mocap within ~2 cm — MILESTONES M4-B step 3.
- [ ] Frame hand-check: carry North/East/up, `pos[0]`↑ / `pos[1]`↑ / `pos[2]`↓ (NED) — a wrong frame flies into a wall — MILESTONES M4-B step 4.
- [ ] RViz (Fixed Frame `world`, `real_interfaces.launch.py drones:=drone_N`) tracks the hand-carried drone — MILESTONES M5.
- [ ] Ledger + CONFIG.md rows updated for everything above. **Only now do props go on** — first flight follows MILESTONES M6 + RUNBOOK §B.

## Snags you're most likely to hit (full table: [TROUBLESHOOTING.md](TROUBLESHOOTING.md))

| Symptom during provisioning | Fix |
|---|---|
| `voxl-wifi station` "succeeds" but never connects | Spaced SSID corrupted the config — manual `wpa_passphrase` method, MILESTONES M3-A step 1 |
| `mlan0` gone after reboot, dmesg `Firmware Init Failed` | WLAN chip wedged — cold power cycle (battery + USB out 10 s) |
| Setup script prints "PX4 server not running" | PX4 still rebooting (~30 s) — retry `px4-microdds_client status` |
| `px4-microdds_client` stuck `Running, disconnected` | Laptop agent not running yet, or wrong laptop IP/domain — re-run RUNBOOK §B steps 0 + 3 |
| `/fmu/*` topics look dead | Add `--qos-reliability best_effort` to echo/hz |
| PX4 won't arm ("fuse failure") | No fused position source — mocap feed or EKF2 params missing (§§5–7 above) |
| `/drone_N/pose` missing / 0 Hz | `./mocap.sh check` names the culprit (Motive not streaming / wrong network / port 1511 squatter) — MOCAP.md §5 |
| Ctrl+C dead inside `adb shell` | VOXL adbd doesn't forward signals — kill from a second shell |

## Completion record (fill in and commit with this drone's CONFIG.md rows)

| Field | Value |
|---|---|
| Drone name / serial | drone_N · D00xx |
| Image / voxl-suite | |
| DDS domain ID (unique!) | |
| Hangar IP (date noted) | |
| Factory backup committed | drone-backups/voxl-px4-start.original-D00xx |
| Params loaded + read-back date | |
| vision-hub read-back date | |
| Kill ground test date + who | |
| Acceptance (§9) all-pass date | |
