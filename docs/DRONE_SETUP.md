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
> ⚠️ **Branch note (2026-10-07):** §4 (provisioning script, now with a watchdog, and
> `target_system`), §9 (Basestation replaces RViz) and the new §8b (LED strips, optional)
> changed with the move to `yikuan/SVG_ground_control`; everything else is unchanged.
> All of §4/§9 is ⏳ STE on this branch — [MIGRATION.md](MIGRATION.md) §6.
>
> **"archived MILESTONES M3-A / M4-A"** below = the previous branch's one-time procedures
> (WiFi join, factory backup, QGC params). They were not carried into the reset ladder; read
> them with `git show airstack-starling-max2:docs/MILESTONES.md` (or on GitHub, branch
> `archive/airstack-starling-max2`). The checklists here are self-sufficient without them.
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

- [ ] Plug in USB-C, power the drone; `adb devices` lists it and `adb shell` lands in the MODAL AI banner — archived MILESTONES M3-A (screenshot at the top of that section).
- [ ] Record the drone's identity from the banner (model, serial like D00xx, image version, voxl-suite version) → new "Drone identity" row in CONFIG.md §Files & identities.
- [ ] **Factory backup BEFORE any script runs:** on the drone `cp /usr/bin/voxl-px4-start /usr/bin/voxl-px4-start.FACTORY-ORIGINAL` — archived MILESTONES M3-A step 2.
- [ ] On the laptop: `adb pull /usr/bin/voxl-px4-start ~/AirStack-starling-max2/drone-backups/voxl-px4-start.original-D00xx` and commit it — archived MILESTONES M3-A step 2 / `drone-backups/` convention.

## 2 · Join the drone to the lab WiFi

> **FIRST: which WiFi hardware does this unit have?** `ip -br link | grep -E 'wlan0|mlan0'`
> · **`mlan0`** = newer Starling Max 2, WiFi **integrated on the VOXL board** — follow this
>   section as written, nothing extra to do.
> · **`wlan0`** = older Starling Max 2 with **no integrated chip**, running a USB TP-Link
>   Archer TX20U Nano (RTL8852BU) dongle — read `mlan0` as `wlan0` throughout, and do the
>   extra dongle steps at the end of this section or it will boot on `169.254.x.x`.

- [ ] Starlings join **`StarlingMax2`** (no spaces) → on the drone: `voxl-wifi station 'StarlingMax2' '<PASSWORD>'` — CONFIG.md §Lab WiFi. (`motive` is the lab-LAN SSID for the Crazyflies — don't use it here.) Password not stored in the repo, ask Jeremy Chia.
- [ ] ⚠️ If the SSID ever has SPACES do NOT use `voxl-wifi station` (it corrupts the config) — use the manual `wpa_passphrase` method — archived MILESTONES M3-A step 1.
- [ ] Verify association: `iw dev mlan0 link` shows Connected (5 GHz can take >10 s) — archived MILESTONES M3-A step 1.
- [ ] Reboot the drone once and re-check `iw dev mlan0 link` — WiFi must survive reboot (`wpa_supplicant@mlan0` auto-starts) — MILESTONES §3c open issue "WiFi reboot-persistence".
- [ ] If `mlan0` vanishes after reboot (dmesg `Firmware Init Failed`): cold power cycle, battery + USB out 10 s — [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
- [ ] Never connect the laptop to the drone's own hotspot `uap0` (SSID like `Starling_N_demo_mode`) — CONFIG.md §Lab WiFi.

### 2b · Extra steps for OLDER units on the USB dongle (`wlan0`) — skip if you have `mlan0`

Two independent boot races will otherwise leave the drone with no WiFi. Full writeup and
evidence: [CLAUDE.md](../CLAUDE.md).

- [ ] **Stop `option` stealing the dongle.** Append `NoDriverLoading=1` to `/etc/usb_modeswitch.d/0bda:1a2b`. Without it the kernel-builtin `option` serial driver claims the stick and exports it as `/dev/ttyUSB0`, so no `wlan0` ever appears.
- [ ] **Stop `wpa_supplicant` quitting before `wlan0` exists.** Create `/etc/systemd/system/wpa_supplicant.service.d/10-wait-for-wlan0.conf` with `StartLimitIntervalSec=0` under `[Unit]` and `RestartSec=5` under `[Service]`, then `systemctl daemon-reload`. The stock unit burns 5 starts in under a second; the dongle only enumerates at t≈8 s.
- [ ] **Verify by REBOOTING** (this is a boot race — a live test proves nothing): `readlink /sys/bus/usb/devices/1-1.4:1.0/driver` = `rtl8852bu`, `systemctl is-active wpa_supplicant` = `active`, `iw dev wlan0 link` = Connected, and `ip -4 -br addr show wlan0` shows a real lease, **not** `169.254.x.x`.
- [ ] If the drone sits on a different subnet from the GCS, add the GCS-side route (`sudo ip route add <drone_subnet> via 192.168.9.1 dev <gcs_nic>`, persist via `nmcli`). ⚠️ Unicast only — **NatNet mocap is multicast and will not cross the router**, so a drone that must fly under OptiTrack has to sit on `192.168.9.x`.

## 3 · Record the drone's IP

- [ ] Read the DHCP lease: `voxl-my-ip` or `ip -4 addr show mlan0` on the drone; cross-check on the router admin page `http://192.168.9.1:8080` — CONFIG.md Network table.
- [ ] Add a "Starling N IP (hangar network)" row to CONFIG.md's Network table (the hangar assigns IPs by port — note the date) — CONFIG.md header convention.
- [ ] Confirm SSH works: `ssh root@<DRONE_IP>` with password `oelinux123` (ModalAI factory default) — CONFIG.md "Drone SSH login" row.

## 4 · Point PX4 at the laptop (uXRCE-DDS provisioning)

- [ ] Pick this drone's **UNIQUE DDS domain ID** — every additional drone gets its own domain (drone_1 = 1, so drone_2 = 2, …); record it in CONFIG.md §Protocol constants — CONFIG.md "DDS domain" row / archived MILESTONES M3-A step 3 multi-drone rule.
- [ ] **`target_system` = this drone's `MAV_SYS_ID`** (PX4 param, QGC → Parameters; Starling 1: ⏳ **read `MAV_SYS_ID` back in QGC before the first arm** — the 2026-09-04 params export says **1**, a 2026-09-18 session note on this airframe says it was set to **2**; whichever it is, `target_systems:=` must match). For drone_N set `MAV_SYS_ID = N` so QGC tells the fleet apart, and launch its interface with `target_systems:=` matching (defaults to the trailing number of the name: `drone_2` → 2). A mismatch means PX4 **silently drops every arm/takeoff/land command — no error, no ACK** — [MIGRATION.md](MIGRATION.md) §5. Record it in CONFIG.md §Protocol constants.
- [ ] Push the **new** script (rewritten on this branch: `px4-` wrapper, 60 s boot retry loop, `svg-microdds-watchdog` service): `adb push AirStack/robot/ros_ws/src/svg_ground_control/scripts/voxl_setup_real_drone.sh /usr/bin/` then `chmod +x` it on the drone — [RUNBOOK.md](RUNBOOK.md) §B step 0.
- [ ] Run it on the drone: `voxl_setup_real_drone.sh drone_N <LAPTOP_IP> <UNIQUE_DOMAIN> 8888` (laptop IP reachable from the drone segment, CONFIG.md; port must stay 8888). Then **`reboot`** — on these airframes `systemctl restart voxl-px4` (which the script's older form did) leaves the SLPI flight core dead — [CLAUDE.md](../CLAUDE.md) iron rule 7.
- [ ] After the reboot: `systemctl status svg-microdds-watchdog` must be `active`. If the drone also carries our earlier `voxl-dds-retry.service` (Starling 1 does), **keep only one** — both restart the uXRCE client; running both is untested (⏳ STE decision → CONFIG.md).
- [ ] Expect `Running, disconnected` from `px4-microdds_client status` until the laptop agent is up — the watchdog keeps retrying — RUNBOOK §B step 3.
- [ ] Start the agent in the robot container (`MicroXRCEAgent udp4 -p 8888 -v4`) and verify on the drone: `px4-microdds_client status` → **Running, connected**, Agent IP = laptop; and on the laptop the interface startup line `PX4Interface initialized (uXRCE-DDS), target_system=N` — RUNBOOK §B steps 3 + 5.
- [ ] Revert recipe exists if anything goes wrong (restore `.FACTORY-ORIGINAL` + reset the flash-saved domain param) — archived MILESTONES M3-A "Full revert to factory" (`git show airstack-starling-max2:docs/MILESTONES.md`).

## 5 · PX4 parameters (QGC fast path)

- [ ] Connect QGC on the laptop (drone pushes MAVLink to `primary_static_gcs_ip` — set the laptop's IP in `/etc/modalai/voxl-mavlink-server.conf` + `systemctl restart voxl-mavlink-server`) — CONFIG.md §voxl-mavlink-server.
- [ ] Load the full validated set: QGC → Vehicle Setup → Parameters → Tools ⋮ → **Load from file** → [`starling_1_indoor_params.params`](../starling_1_indoor_params.params) — CONFIG.md §PX4 params (procedure was archived MILESTONES M4-A).
- [ ] ⚠️ drone_2+ note: the file is Starling **1**'s export — review per-drone params (calibrations, `MPC_THR_HOVER` trim, RC binding-specific values, **and `MAV_SYS_ID`**, which must be unique per drone) before accepting wholesale.
- [ ] Reboot PX4 (power cycle or QGC reboot) so everything takes effect.
- [ ] **Spot-check by READ-BACK** in the Parameters search box: `EKF2_EV_CTRL=11`, `RC_MAP_KILL_SW=8`, `EKF2_BARO_CTRL=0`, `MAV_SYS_ID=N` — only a read-back counts (archived ledger #7's lesson) — CONFIG.md §PX4 params.
- [ ] Note for later: these are INDOOR mocap params — outdoor/GPS flight needs the revert listed in CONFIG.md §PX4 params warning.

## 6 · Drone-side vision-hub config (NOT in the .params file)

- [ ] Edit `/etc/modalai/voxl-vision-hub.conf` on the drone: `"en_vio": false` and `"offboard_mode": "off"` — CONFIG.md §voxl-vision-hub.
- [ ] **Verify by READ-BACK** (`cat` the file and read the live values) — the 2026-07-29 edit was silently never saved and sat wrong for two weeks; only a read-back counts (archived ledger #7).
- [ ] `systemctl restart voxl-vision-hub` so it takes effect (this one IS safe to restart — it is not `voxl-px4`) — CONFIG.md §voxl-vision-hub.

## 7 · Motive rigid body

- [ ] Attach 4–5 reflective markers in an **asymmetric** pattern (no two spacings alike) — [MOCAP.md](MOCAP.md) §6.3.
- [ ] In Motive create a rigid body named **exactly `drone_N`** (lowercase + underscore — topic names come from it), with the drone's forward axis on global **+X** — [MOCAP.md](MOCAP.md) §6.3 / CONFIG.md §Mocap.
- [ ] Check the Data Streaming pane: Up Axis = Z, streaming enabled, Local Interface = Motive PC IP — [MOCAP.md](MOCAP.md) §6.4 / `pictures/check_motive_ip_address.jpg`.
- [ ] Add the body to `MOCAP_BODIES` for `./mocap.sh` and restart the bridge (body list is read only at startup); verify per [MOCAP.md](MOCAP.md) — CONFIG.md "Rigid body name" row.

## 8 · RC transmitter + kill switch (safety-critical)

- [ ] Bind the transmitter to the drone's receiver (hardware-specific).
- [ ] Calibrate sticks: QGC → Vehicle Setup → Radio.
- [ ] Confirm the safety params (loaded in §5, re-check): `RC_MAP_KILL_SW=8`, `COM_RC_OVERRIDE=1`, `COM_OBL_RC_ACT=1` — CONFIG.md §PX4 params.
- [ ] **Kill ground test — props OFF, drone strapped down:** arm via a software `takeoff`, flip the kill switch, motors must cut instantly. On this branch, also watch the laptop's `px4_interface` log: `arm` must get an `ACCEPTED` ack (no ack = `target_system` mismatch, §4) — MILESTONES M3.
- [ ] Repeat the kill ground test after ANY transmitter/receiver change **and after any AirStack branch change**, forever.
- [ ] Brief every pilot: RC takeover = MANUAL or kill only, never POSCTL/ALTCTL — MILESTONES §3c carried-over issues.

## 8b · LED strip (optional — skip if no strip is fitted)

11 RGBW NeoPixels on the ESC LED output; green = idle, red = the CBF is correcting this
drone; everything else is operator-commanded. Purely cosmetic — nothing in this path can
command the vehicle. Full guide: [BASESTATION.md](BASESTATION.md) §8.

- [ ] Fit the strip to the ESC LED output (hardware note: ⏳ not yet done on Starling 1).
- [ ] From the laptop, package dir: `scripts/voxl_push_led.sh drone_N <DRONE_IP>` (ssh root password in CONFIG.md; `LED_EXTRA_ARGS="--rgb --brightness 60"` for an RGB strip) — installs `svg_led_daemon.py` + a `svg-led` systemd unit.
- [ ] On the drone: `systemctl status svg-led` → `opened … sink` and `PX4 ESC LED bits muted`.
- [ ] ⚠️ **Acknowledge:** the daemon mutes PX4's ESC status LEDs, so **the ESCs no longer show arm state**. QGC is the arming display, as always. Brief the pilots.
- [ ] Laptop firewall: open **udp/47901** (the daemon's heartbeat to the ground) — `sudo ufw allow 47901/udp`.
- [ ] With the commander running (`use_led:=true` is the default): log line `drone_N: LED daemon online at <ip>:47900`; strip green; `ros2 topic pub --once /svg/led_command std_msgs/msg/String "{data: 'drone_N blue'}"` changes it.

## 9 · Acceptance (all pass BEFORE props go on)

- [ ] Agent `session established` and all 24 `/drone_N/fmu/*` topics on the laptop — RUNBOOK §B step 3.
- [ ] `px4_interface` startup line shows `target_system=N` — RUNBOOK §B step 5.
- [ ] Mocap pose: `ros2 topic hz /drone_N/pose` ≈ 50 Hz in the robot container, tracks the hand-carried drone — MOCAP.md.
- [ ] EKF2 fusion in → out: `fmu/in/vehicle_visual_odometry` feeding, `fmu/out/vehicle_odometry` positions match mocap within ~2 cm — RUNBOOK §B step 6.
- [ ] Frame hand-check: carry North/East/up, `pos[0]`↑ / `pos[1]`↑ / `pos[2]`↓ (NED) — a wrong frame flies into a wall — RUNBOOK §B step 6.
- [ ] `ros2 topic echo /svg/commander_status --once` shows `drone_N` with `"odom_fresh": true`, `"state": "IDLE"` — [BASESTATION.md](BASESTATION.md) §4.
- [ ] **Basestation** 3D view tracks the hand-carried drone; Agent State row `IDLE · odom fresh` (`real_interfaces.launch.py drones:=drone_N` running) — MILESTONES M2 / RUNBOOK §B step 7. (RViz, Fixed Frame `world`, still works as a fallback.)
- [ ] Ledger + CONFIG.md rows updated for everything above. **Only now do props go on** — first flight follows MILESTONES M3 + RUNBOOK §B.

## Snags you're most likely to hit (full table: [TROUBLESHOOTING.md](TROUBLESHOOTING.md))

| Symptom during provisioning | Fix |
|---|---|
| `voxl-wifi station` "succeeds" but never connects | Spaced SSID corrupted the config — manual `wpa_passphrase` method, archived MILESTONES M3-A step 1 |
| `mlan0` gone after reboot, dmesg `Firmware Init Failed` | WLAN chip wedged — cold power cycle (battery + USB out 10 s) |
| Older unit (USB dongle): boots on `169.254.x.x` | `wpa_supplicant` hit its systemd start limit before `wlan0` existed — §2b drop-in; recover with `systemctl reset-failed wpa_supplicant && systemctl start wpa_supplicant` |
| Older unit (USB dongle): no `wlan0` at all | `option` driver stole the stick — §2b `NoDriverLoading=1` |
| Setup script prints "PX4 server not running" | PX4 still rebooting (~30 s) — retry `px4-microdds_client status` |
| `px4-microdds_client` stuck `Running, disconnected` | Laptop agent not running yet, or wrong laptop IP/domain — re-run RUNBOOK §B steps 0 + 3 (then **reboot**) |
| After the setup script: QGC "params missing", sensor topics never publish | You ran `systemctl restart voxl-px4` (or the old script did) — the SLPI flight core is wedged. **Reboot the drone.** |
| Arm/takeoff sent, nothing happens, **no** `PX4 ack` line on the laptop | `target_system` ≠ the drone's `MAV_SYS_ID` — §4. (A `DENIED` ack is a different problem: preflight/EKF.) |
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
| `MAV_SYS_ID` / `target_system` (unique!) | |
| uXRCE client keeper (`svg-microdds-watchdog` or `voxl-dds-retry`) | |
| LED strip fitted + `svg-led` active (optional) | |
| Hangar IP (date noted) | |
| Factory backup committed | drone-backups/voxl-px4-start.original-D00xx |
| Params loaded + read-back date | |
| vision-hub read-back date | |
| Kill ground test date + who | |
| Acceptance (§9) all-pass date | |
