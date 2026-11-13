# CLAUDE.md — AirStack Starling Max 2 (indoor OptiTrack mocap flight stack)

AirStack ground-control workspace flying two ModalAI Starling Max 2 drones indoors (`drone_1` older, `drone_2` newer, see [docs/CONFIG.md](docs/CONFIG.md)) with OptiTrack motion-capture positioning (mocap) (no GPS/VIO for nav).

**Branch (since 2026-10-20):** CMU `yikuan/SVG_ground_control_dev` @ `b21d28c` (their *working* branch; `yikuan/SVG_ground_control` is its squash-release line, last cut `cf719f0` = our 2026-10-07 snapshot), vendored in `AirStack/`. The 10-20 bump brought the 6-gain Foxglove dropdown (goal accel/settle, teleop vmax), `goal_sequence` + `figure_eight` scenarios and the rosbag switch — [MIGRATION.md](docs/MIGRATION.md) §11.
The previous branch (`daniel/diffaero_ground_control`, flown 09-01→03) is frozen on tag
`airstack-starling-max2` / branch `archive/airstack-starling-max2`. The two are **siblings**, not
parent/child. Milestones were RESET; **on the real drone this software has flown one drone (hover, goal legs, fence: ledger #33, 2026-11-11) and two drones together with the collision filter observed (#35, 2026-11-12); gamepad flown with one drone (#36, 2026-11-13; fence top, +x wall and pad unplug still to fly); a hand-flown drone held off by the collision filter of a hovering one (#37, 2026-11-13); formations and random goals unflown; sim results in [record/LEDGER.md](docs/record/LEDGER.md)** (one screen: [MILESTONES.md](docs/MILESTONES.md)). Delta and the ordered re-do list:
[MIGRATION.md](docs/MIGRATION.md).

**Read first:** [MILESTONES.md](docs/MILESTONES.md) (one screen: where each Linear project is, the hazards before the next real flight) → the project page you are working on — then the table below.

| Doc | Use it for |
|---|---|
| [MILESTONES.md](docs/MILESTONES.md) | one screen: where each project is (HTX-R1/R2/R3), before-the-next-real-flight hazards, links to the pages below |
| [projects/](docs/projects/HTX-R1.md) | per Linear project — [HTX-R1](docs/projects/HTX-R1.md) sim validation, [HTX-R2](docs/projects/HTX-R2.md) real-drone bring-up (pilot's hazards box + carried-over table), [HTX-R3](docs/projects/HTX-R3.md) localization research; every milestone and issue by Linear id and verbatim title, results from the records |
| [record/LEDGER.md](docs/record/LEDGER.md) | append-only test ledger: table 1 this software (#1–#37; real rows from #33), table 2 the previous software (A1–A21, archived) |
| [DOCS_STANDARD.md](docs/DOCS_STANDARD.md) | **how docs are organised and changed** — where things live, Linear naming, milestone → issues → results shape, cell rules, budgets, wording, the after-a-test-run recipe, gates; structural changes go through the `quality-change` skill |
| [TEST_STANDARD.md](docs/TEST_STANDARD.md) | **how a milestone test is scripted** — one front door `tools/sim.sh test <name>`, Isaac window on, a live plot window, same numbers gated, Ctrl-C lands + ABORTED, five-file test contract under `tools/sim_tests/` |
| [CODING_STANDARD.md](docs/CODING_STANDARD.md) | **how a behaviour change is logged** — what needs an entry, the eight fields, [record/CHANGES.md](docs/record/CHANGES.md), live changes through the tools, the hook that blocks a missing entry |
| [PX4_MSGS_AUDIT.md](docs/PX4_MSGS_AUDIT.md) | PX4 v1.14 vs px4_msgs audit + re-run method (NEAR-821; iron rule 5) |
| [MIGRATION.md](docs/MIGRATION.md) | old branch → this branch: removed/added, behaviours to unlearn, re-do list, archived-doc pointers |
| [RUNBOOK.md](docs/RUNBOOK.md) | running a session — sim: `tools/sim_terminals.sh` (four Terminator tabs: Isaac Sim · Interfaces · Commander · Cockpit); real drone: tmux `bringup` panes; the panel instead of RViz |
| [BASESTATION.md](docs/BASESTATION.md) | the Foxglove SVG Basestation panel, `/svg/commander_status` fields, LED strips |
| [TELEOP.md](docs/TELEOP.md) | the gamepad mapping (real procedure: [RUNBOOK.md](docs/RUNBOOK.md) B9 one drone, B10 two drones), the sim keyboard window and its sim-only warning (§3b), the two fences, controller profiles, CMU `teleop.md` corrections; the sim keyboard session (keys, Drive mode, strip, cold start, video) is in [localisation/README.md](localisation/README.md#fly-it-with-the-keyboard-one-drone-sim-only) |
| [SCENARIOS.md](docs/SCENARIOS.md) | CBF filter, runtime gains, formations / random goals / RC-intruder squeeze (sim now, real at M7 (HTX-R2, NEAR-840/841)) |
| [CONFIG.md](docs/CONFIG.md) | live values (IPs, params, credentials, branch/commit, flight parameters per config) |
| [MOCAP.md](docs/MOCAP.md) | laptop-side mocap bridge — unchanged by the branch switch |
| [DRONE_SETUP.md](docs/DRONE_SETUP.md) | drone provisioning (new script + watchdog, `target_system`, optional LEDs) |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | symptom → fix index; first move on this branch = `ros2 topic echo /svg/commander_status --once` |
| [PREFLIGHT.md](docs/PREFLIGHT.md) | safety card — mirrors the iron rules below; keep the two in sync |
| [GLOSSARY.md](docs/GLOSSARY.md) | plain-English definitions of every recurring term (commander, panel, CBF, scenarios, tabs/panes…) |
| [AI_ASSIST.md](docs/AI_ASSIST.md) | for humans: how to work with the assistant here (recipes, phrasing, never-do list) — keep its never-do table in step with the iron rules |
| [SETUP.md](docs/SETUP.md) | new-laptop install + first build + the normal-looking error messages (moved from README 2026-10-21) |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | one-page primer, flight-lab network, whose document is whose (moved from README 2026-10-21) |
| [tools/](tools/) | `sim.sh` front door (`setup · doctor · up · down · status · tabs · keys · test <name> … · figures · check`, [tools/README.md](tools/README.md)), `sim_terminals.sh` + `sim_tab.sh`, the hover-step tools |
| [localisation/](localisation/README.md) | camera-world sim runs: construction-site world (`ENV_USD`), stereo VO with cuVSLAM, scoring vs the PX4 ulog, validation ladder — **sim-only exploration, nothing flies on cuVSLAM**; it also holds the one-drone [keyboard session](localisation/README.md#fly-it-with-the-keyboard-one-drone-sim-only). A sibling of `AirStack/` (git subtree, 2026-10-23), never inside CMU's tree |

Architecture pictures: `pictures/Starling_Airstack_architecture.png` (control flow — drawn for
the previous branch; README lists the four corrections: `./mocap.sh`, `px4_interface` box,
trajectory setpoint, Foxglove panel as operator view), `pictures/Flight_lab_architecture.png` (network
topology). Network/router details live in the companion repo
[ground-control-network-setup](https://github.com/AI-DA-STC/ground-control-network-setup).

## Iron rules
<!-- IRON_RULES:BEGIN -->
<!-- canonical text lives in docs/PREFLIGHT.md; CLAUDE.md carries a byte-identical copy; tools/docs_check/check_docs.sh diffs the two blocks -->
1. **RC takeover = flip ch6 to MANUAL (low), or KILL (ch8) — never Position/Altitude.** The commander's setpoints leak into those modes (its trajectory setpoint is still consumed in POSCTL/ALTCTL; re-observed at the first flight, NEAR-825 — docs/projects/HTX-R2.md).
2. **A landing is not over until QGC says DISARMED** — check before anyone approaches. The commander's log and the panel's Interface column are ACK logs, not arming displays. Landed but still ARMED after ~10 s → flip KILL (harmless on the ground) or arm switch (ch5) down. (The commander's disarm is a normal PX4 disarm — PX4 refuses it unless its land detector says landed, so it cannot drop a flying drone.)
3. **After ANY manual takeover or RC KILL: call `land` once** (drone on the floor) to reset the commander, or `takeoff` will refuse ("not IDLE") (re-observed at NEAR-825). After a KILL the commander keeps sending setpoints until `land` is called (ledger #34).
4. **Never run `test/functional_*.py` with the real stack up** — they publish fake odometry on live topics (`squeeze`, `squeeze_lag`, `fence`, `single_goal`, `multi_goal`, `hybrid`).
5. **Software is BLIND to PX4 arming state** (v1.14 px4_msgs mismatch) — fly with QGC visible. A `PX4 ack: ACCEPTED` means "PX4 heard me", never "armed"; **no ACK at all = `target_system` ≠ the drone's `MAV_SYS_ID`** — do not fly until fixed. The ACK message itself is unaudited against v1.14 until docs/PX4_MSGS_AUDIT.md is re-run (NEAR-821).
6. **Lab WiFi SSIDs (`motive`, `StarlingMax2`) are OPEN** — never bridge the lab network to the internet.
7. **After re-provisioning the drone (`voxl_setup_real_drone.sh`): REBOOT it** — never `systemctl restart voxl-px4` (it leaves the SLPI flight core dead: "params missing", sensors never publish).
8. The shipped configs are CMU's bench values, not ours — fly the `_ours` yamls. Traps at b21d28c: `goal_single.yaml` still exempts drone_1 from the CBF, flies 10 m/s and lands at 0.8; `goal_tracking.yaml`/`goal_sequence.yaml` carry `cbf_max_speed_mps 10.0`; CMU's real configs leave `land_settle_s` unset (→ 2.0 s default). The 10-07 traps (drone_2, random_goals) are gone since the 10-20 bump.
9. **Sim-only — never port to the drone:** the sim PX4 airframe `10090_pegasus_starling2max` (roll and pitch rate gains × 0.5, yaw rate gains 0.25 / 0.2 — real 0.07 / 0.5, `MC_YAW_TQ_CUTOFF` 15, `LNDMC_ROT_MAX` 300 — real 30, motor lag off, MPC speed limits 20 / 6 / 1000 / 10 / 4), the sim stack's MAVROS respawn, and `cbf_sim.yaml`'s speeds 2.0 / 4.0 / 6.0 with its landing settle 2.0 s + disarm retry. The drone's parameters come from `starling_1_indoor_params.params` / QGC only; the real `_ours` configs fly `drone_1`, `land_settle_s` 0.0, `land_speed_mps` 0.6, `cbf_max_speed_mps` 1.0. Lines in the airframe marked `# = real` match the drone's file; copying them from the drone to the sim is fine, the other direction is not.
10. **Takeoff point and watcher.** Each drone stands on its own takeoff point (the config's `hover_positions`), nose toward +x: `takeoff` flies a straight line to that point (ledger #34), and the fence does not act during the climb (docs/projects/HTX-R2.md, hazard 7). A second person watches `drone_1`'s front-right motor every time `drone_1` takes off: it failed or started late in 5 of 7 arms on 2026-11-12, cause unknown (docs/projects/HTX-R2.md, hazard 6).
<!-- IRON_RULES:END -->

**Two clones, one workflow:** `~/AirStack-starling-max2` is the **live** clone (docker-mounted) — **commits land HERE**, on `main` (a small edit directly, anything larger by fast-forward from a worktree branch: [More than one Claude session](#more-than-one-claude-session-on-this-repo)). `~/Documents/GitHub/AirStack-starling-max2` is the **mirror** GitHub Desktop pushes from — update it with `git -C ~/Documents/GitHub/AirStack-starling-max2 pull ~/AirStack-starling-max2 main`. **Never push from Claude** — the user pushes via GitHub Desktop. (Every 10-19/10-20 commit was made in the live clone; the older note "commit in the mirror, pull in the live clone" was wrong.) Both clones were put on the new `main` on 2026-10-07; the live clone's old-branch config edits are backed up in `~/AirStack-starling-max2-local-edits-2026-10-07/`.

## More than one Claude session on this repo

Assume another session may be working here at any time.

- Before editing, look: `git status -sb`, `git worktree list`, and `find . -path ./.git -prune -o -type f -mmin -30 -print`. Uncommitted or untracked files you did not create belong to someone else: leave them alone and tell the owner what you saw.
- Stage by explicit path only. Never `git add -A`, `git commit -a`, `git stash`, `git reset --hard`, `git checkout -- <file>` or `git clean`.
- A one-file edit committed within minutes may go straight on `main`. Anything larger goes in its own worktree and branch (`git worktree add ../AirStack-starling-max2-<topic> -b <branch> main`).
- Back to `main`: rebase the branch on `main`, rerun `tools/docs_check/check_docs.sh` and the unit tests (a fast-forward does not run the pre-commit guard), then `git merge --ff-only <branch>` in the live clone. If git refuses, stop and ask.
- Then pull the mirror. The owner pushes.

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
