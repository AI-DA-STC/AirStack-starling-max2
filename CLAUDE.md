# CLAUDE.md — AirStack Starling Max 2 (indoor OptiTrack mocap flight stack)

AirStack ground-control workspace flying a ModalAI Starling Max 2 indoors under OptiTrack mocap (no GPS/VIO for nav).

**Read first:** [MILESTONES.md](docs/MILESTONES.md) §3 (status table) / §3c (test ledger) — current state — then the table below.

| Doc | Use it for |
|---|---|
| [MILESTONES.md](docs/MILESTONES.md) | current state: status table, test ledger, open issues |
| [RUNBOOK.md](docs/RUNBOOK.md) | running a session |
| [CONFIG.md](docs/CONFIG.md) | live values (IPs, params, credentials) |
| [MOCAP.md](docs/MOCAP.md) | laptop-side mocap bridge |
| [DRONE_SETUP.md](docs/DRONE_SETUP.md) | drone provisioning |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | symptom → fix index |
| [MILESTONES.md](docs/MILESTONES.md) §8 | deferred designs (shelved commander fixes) |
| [PREFLIGHT.md](docs/PREFLIGHT.md) | safety card |

Architecture pictures: `pictures/Starling_Airstack_architecture.png` (control flow),
`pictures/Flight_lab_architecture.png` (network topology). Network/router details live in
the companion repo [ground-control-network-setup](https://github.com/AI-DA-STC/ground-control-network-setup).

## Iron rules
1. RC takeover = flip to MANUAL or KILL only — Position/Altitude still obey the commander's setpoints.
2. Confirm **DISARMED in QGC** after every landing — the commander's log is optimistic.
3. Commander stuck non-IDLE after a takeover → call `land` once to reset it.
4. Never run `test/functional_*.py` with the real stack up — they publish fake odometry on live topics.
5. Software is BLIND to PX4 arming state (v1.14 px4_msgs mismatch) — fly with QGC visible.
6. Lab WiFi SSIDs (`motive`, `StarlingMax2`) are OPEN (no encryption) — never bridge the lab network to the internet.

**Two clones:** `~/AirStack-starling-max2` (live, docker-mounted) vs `~/Documents/GitHub/AirStack-starling-max2` (git mirror) — workflow currently INVERTED, check `git log` in both before editing. **Never push** — the user pushes via GitHub Desktop.

**Session history:** pre-2026-09 session-by-session narrative used to live in `CLAUDE_NOTES.md`
(retired 2026-09-08 — superseded by the docs above). Recover it with `git log --follow CLAUDE_NOTES.md`.

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
