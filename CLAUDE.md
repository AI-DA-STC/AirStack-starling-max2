# CLAUDE.md — AirStack Starling Max 2 (indoor OptiTrack mocap flight stack)

AirStack ground-control workspace flying a ModalAI Starling Max 2 indoors under OptiTrack mocap (no GPS/VIO for nav).

**Branch (since 2026-10-20):** CMU `yikuan/SVG_ground_control_dev` @ `b21d28c` (their *working* branch; `yikuan/SVG_ground_control` is its squash-release line, last cut `cf719f0` = our 2026-10-07 snapshot), vendored in `AirStack/`. The 10-20 bump brought the 6-gain Foxglove dropdown (goal accel/settle, teleop vmax), `goal_sequence` + `figure_eight` scenarios and the rosbag switch — [MIGRATION.md](docs/MIGRATION.md) §11.
The previous branch (`daniel/diffaero_ground_control`, flown 09-01→03) is frozen on tag
`airstack-starling-max2` / branch `archive/airstack-starling-max2`. The two are **siblings**, not
parent/child. Milestones were RESET; **no real flight validated on this branch; sim validated in
part** ([MILESTONES.md](docs/MILESTONES.md) §3c). Delta and the ordered re-do list:
[MIGRATION.md](docs/MIGRATION.md).

**Read first:** [MILESTONES.md](docs/MILESTONES.md) §3 (status table) / §3c (test ledger + carried-over issues) — current state — then the table below.

| Doc | Use it for |
|---|---|
| [MILESTONES.md](docs/MILESTONES.md) | current state: M0–M7 status, code audit, test ledger (reset), carried-over issues, backlog |
| [MIGRATION.md](docs/MIGRATION.md) | old branch → this branch: removed/added, behaviours to unlearn, re-do list, archived-doc pointers |
| [RUNBOOK.md](docs/RUNBOOK.md) | running a session — sim: `tools/sim_terminals.sh` (four Terminator tabs: Isaac Sim · Interfaces · Commander · Cockpit); real drone: tmux `bringup` panes; the panel instead of RViz |
| [BASESTATION.md](docs/BASESTATION.md) | the Foxglove SVG Basestation panel, `/svg/commander_status` fields, LED strips |
| [TELEOP.md](docs/TELEOP.md) | gamepad teleop, the two fences, controller profiles, CMU `teleop.md` corrections |
| [SCENARIOS.md](docs/SCENARIOS.md) | CBF filter, runtime gains, formations / random goals / RC-intruder squeeze (sim now, real at M7) |
| [CONFIG.md](docs/CONFIG.md) | live values (IPs, params, credentials, branch/commit, flight parameters per config) |
| [MOCAP.md](docs/MOCAP.md) | laptop-side mocap bridge — unchanged by the branch switch |
| [DRONE_SETUP.md](docs/DRONE_SETUP.md) | drone provisioning (new script + watchdog, `target_system`, optional LEDs) |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | symptom → fix index; first move on this branch = `ros2 topic echo /svg/commander_status --once` |
| [PREFLIGHT.md](docs/PREFLIGHT.md) | safety card — mirrors the iron rules below; keep the two in sync |
| [GLOSSARY.md](docs/GLOSSARY.md) | plain-English definitions of every recurring term (commander, panel, CBF, scenarios, tabs/panes…) |
| [AI_ASSIST.md](docs/AI_ASSIST.md) | for humans: how to work with the assistant here (recipes, phrasing, never-do list) — keep its never-do table in step with the iron rules |
| [tools/](tools/) | `sim_terminals.sh` + `sim_tab.sh` (the sim session), `make_milestones_doc.py` (legacy .docx export) |

Architecture pictures: `pictures/Starling_Airstack_architecture.png` (control flow — drawn for
the previous branch, boxes unchanged), `pictures/Flight_lab_architecture.png` (network
topology). Network/router details live in the companion repo
[ground-control-network-setup](https://github.com/AI-DA-STC/ground-control-network-setup).

## Iron rules
1. RC takeover = flip to MANUAL or KILL only — Position/Altitude still obey the commander's setpoints (expected to persist on this branch: the trajectory setpoint is still consumed in POSCTL/ALTCTL; re-test at M3).
2. Confirm **DISARMED in QGC** after every landing — the commander's log is optimistic, and the Basestation's Interface column is an ACK log, not an arming display.
3. Commander stuck non-IDLE after a takeover → call `land` once to reset it.
4. Never run `test/functional_*.py` with the real stack up — they publish fake odometry on live topics (six of them now: `squeeze`, `squeeze_lag`, `fence`, `single_goal`, `multi_goal`, `hybrid`).
5. Software is still BLIND to PX4 arming state (v1.14 px4_msgs mismatch) — fly with QGC visible. **New on this branch:** `px4_interface` logs command ACKs (`ACCEPTED`/`DENIED`); treat them as "PX4 heard me", never as "armed". **No ACK at all = `target_system` ≠ the drone's `MAV_SYS_ID`** — fix before retrying. The ACK message itself is unaudited against v1.14 until MILESTONES §3d is re-run.
6. Lab WiFi SSIDs (`motive`, `StarlingMax2`) are OPEN (no encryption) — never bridge the lab network to the internet.
7. **On this airframe, after `voxl_setup_real_drone.sh`: REBOOT** — `systemctl restart voxl-px4` leaves the SLPI flight core dead ("params missing", sensors never publish).
8. The shipped configs are CMU's bench values, not ours — fly the `_ours` yamls. Traps at b21d28c: `goal_single.yaml` still exempts drone_1 from the CBF, flies 10 m/s and lands at 0.8; `goal_tracking.yaml`/`goal_sequence.yaml` carry `cbf_max_speed_mps 10.0`; CMU's real configs leave `land_settle_s` unset (→ 2.0 s default). The 10-07 traps (drone_2, random_goals) are gone since the 10-20 bump.
9. **Sim-only — never port to the drone:** the sim PX4 airframe `10090_pegasus_starling2max` (rate gains × 0.5, gyro filters 80/40 Hz, `LNDMC_ROT_MAX` 300 — real drone 30 — motor lag off), the sim stack's MAVROS respawn, and `cbf_sim.yaml`'s speeds 2.0 / 4.0 / 6.0 with its landing settle 2.0 s + disarm retry. The drone's parameters come from `starling_1_indoor_params.params` / QGC only; the real `_ours` configs fly `drone_1`, `land_settle_s` 0.0, `land_speed_mps` 0.6, `cbf_max_speed_mps` 1.0 ([CONFIG.md](docs/CONFIG.md)). (Attitude/position gains and the MPC speed limits in the sim airframe *equal* the real drone's — that direction is fine; the other is not.)

**Two clones, one workflow:** `~/AirStack-starling-max2` is the **live** clone (docker-mounted) — **edit and commit HERE**, on `main`. `~/Documents/GitHub/AirStack-starling-max2` is the **mirror** GitHub Desktop pushes from — update it with `git -C ~/Documents/GitHub/AirStack-starling-max2 pull ~/AirStack-starling-max2 main`. **Never push from Claude** — the user pushes via GitHub Desktop. (Every 10-19/10-20 commit was made in the live clone; the older note "commit in the mirror, pull in the live clone" was wrong.) Both clones were put on the new `main` on 2026-10-07; the live clone's old-branch config edits are backed up in `~/AirStack-starling-max2-local-edits-2026-10-07/`.

**Session history:** pre-2026-09 session-by-session narrative used to live in `CLAUDE_NOTES.md`
(retired 2026-09-08 — superseded by the docs above). Recover it with `git log --follow CLAUDE_NOTES.md`.
The old-branch docs in full: `git show airstack-starling-max2:docs/MILESTONES.md` etc.

## WiFi: drone comes up on 169.254.x.x instead of its DHCP address (2026-09-16)

**Applies to OLDER Starling Max 2 units only** — the ones with **no integrated WiFi chip**,
which need a USB **TP-Link Archer TX20U Nano (RTL8852BU)** dongle and come up as **`wlan0`**
(this rig: `m0054`). **NEWER Starling Max 2 units have WiFi integrated on the VOXL board**,
come up as **`mlan0`** driven by `wpa_supplicant@mlan0`, and need **none** of this.
Check which you have before applying anything: `ip -br link | grep -E 'wlan0|mlan0'`.

**Symptom:** boot banner shows `current IP: wlan0: 169.254.38.32`, or no `wlan0` at all.
`169.254.x.x` is dhcpcd's link-local fallback — it means DHCP never ran, because the drone
never associated. It is *not* a DHCP server problem.

Two **independent boot races** caused this. Both are fixed and reboot-verified.

### Cause 1 — the `option` serial driver steals the dongle (no `wlan0` at all)
`usb_modeswitch` flips the stick from `0bda:1a2b` (fake CD-ROM) to `35bc:0108` (WLAN), then
— assuming every mode-switching device is an LTE modem — writes the new ID into
`/sys/bus/usb-serial/drivers/option1/new_id`. `option` is **built into the kernel** (registers
at t=1.9s, before `rtl8852bu` at t=2.6s), so it claims the interface and exports the WiFi
adapter as `/dev/ttyUSB0`. The stick then re-enumerated 5x per boot in a switch/revert loop.

**Fix:** `NoDriverLoading=1` in `/etc/usb_modeswitch.d/0bda:1a2b`.

**Diagnose:** `readlink /sys/bus/usb/devices/1-1.4:1.0/driver` → must say `rtl8852bu`, not `option`.
`lsmod | grep 8852` showing refcount `0` = module loaded but owns nothing.
Live recovery without reboot (`option1` has `new_id` but **no** `remove_id`, so the poisoned
ID can't be cleared until reboot):
```
echo -n 1-1.4:1.0 > /sys/bus/usb/drivers/option/unbind
echo -n 1-1.4:1.0 > /sys/bus/usb/drivers/rtl8852bu/bind
```

### Cause 2 — `wpa_supplicant` gives up before `wlan0` exists (this is the 169.254 one)
Stock `/lib/systemd/system/wpa_supplicant.service` has `Restart=always` but **no `RestartSec`**,
so it defaults to 100 ms. Against systemd's default `StartLimitBurst=5` /
`StartLimitIntervalSec=10s` it burns all 5 starts **inside one second**, logging
`Could not read interface wlan0 flags: No such device`, then
`Start request repeated too quickly` — and gives up **permanently**. But the USB dongle only
enumerates at **t=8.1s** and `wlan0` exists at **t=9.2s**. The stock unit assumes built-in WiFi
present at t=0, which is true for `mlan0` and false for any USB stick.

**Fix:** drop-in `/etc/systemd/system/wpa_supplicant.service.d/10-wait-for-wlan0.conf`
```
[Unit]
StartLimitIntervalSec=0
After=sys-subsystem-net-devices-wlan0.device
[Service]
RestartSec=5
```

**Recovery if it ever fails again:** `systemctl reset-failed wpa_supplicant` **then**
`systemctl start wpa_supplicant`. A plain `systemctl restart` will NOT work once the start
limit is hit — `reset-failed` is mandatory.

### Verified state after reboot
`rtl8852bu` bound · 1 USB enumeration (was 5) · 1 supplicant retry · associated to
`StarlingMax2` on 5180 MHz · DHCP lease **10.40.2.11/23** via 10.40.2.1 · 0% loss both ways.

### Laptop side — drone "can't ping the GCS" is asymmetric routing, NOT a firewall
Drone `10.40.2.11` pinging the GCS `192.168.9.107` failed while the router was fine (drone
pings `192.168.9.1` at 0% loss). Proof the packets *did* arrive, no root needed: `/proc/net/snmp`
Icmp `InEchos` **and** `OutEchoReps` both rose by 5 during 5 pings. The laptop was replying —
the replies just left via the wrong NIC, because it has two default routes and the WiFi one
(metric 600) beats ethernet (metric 20100). `rp_filter` was `2` (loose), so it dropped nothing.

**Fix (on the LAPTOP, not in `adb shell` — `enp129s0` doesn't exist on the drone):**
```
sudo ip route add 10.40.2.0/23 via 192.168.9.1 dev enp129s0          # runtime only
sudo nmcli connection modify "AI.DA.STC" +ipv4.routes "10.40.2.0/23 192.168.9.1"   # persist
sudo nmcli connection up "AI.DA.STC"
```

> **Mocap caveat:** that route carries **unicast only**. NatNet is **multicast** and will not
> cross the router into `10.40.2.x`. To fly this drone under OptiTrack it must sit on
> `192.168.9.x`, not on a route into the AP's subnet. See the network repo's subnet rule.
