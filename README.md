# AirStack-starling-max2 — Starling Max 2 × AirStack lab repo

> **Any unfamiliar term** (the commander, the panel, the interfaces, mocap bridge…) → [GLOSSARY.md](docs/GLOSSARY.md), one line each.

One real ModalAI **Starling Max 2**, flown indoors under **OptiTrack** motion capture by CMU's
**AirStack** ground-control stack (a known-good snapshot lives in [`AirStack/`](AirStack/)), with
three-drone swarms rehearsed in **Isaac Sim** before anything flies for real.

**Status:** snapshot `yikuan/SVG_ground_control_dev` @ `b21d28c` · sim validated in part
([MILESTONES.md](docs/MILESTONES.md) §3c) · **no real flight on this branch yet** — the gates
before the next one are the box at the top of MILESTONES.

## I want to…

| | Go to |
|---|---|
| **fly in the simulator** | [RUNBOOK.md §A](docs/RUNBOOK.md) — one command opens four tabs; takeoff → land in ten minutes |
| **fly the real drone** | [PREFLIGHT.md](docs/PREFLIGHT.md) first, always; then [RUNBOOK.md §B](docs/RUNBOOK.md) |
| **set up a new laptop** | [SETUP.md](docs/SETUP.md) |
| **understand how it fits together** | [ARCHITECTURE.md](docs/ARCHITECTURE.md), one page |
| **find a value** (IP, parameter, which config we fly) | [CONFIG.md](docs/CONFIG.md) |
| **fix something** | [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — symptom → fix |
| **see what is proven and what is next** | [MILESTONES.md](docs/MILESTONES.md) |
| **work with the AI assistant on this repo** | [AI_ASSIST.md](docs/AI_ASSIST.md) |

<img src="pictures/Starling_Airstack_architecture.png" alt="Starling Max 2 × AirStack control-flow diagram" width="820">

*(Drawn for the previous branch; four things moved since — the corrections are listed in
[ARCHITECTURE.md](docs/ARCHITECTURE.md).)*

## Two rules before anything else

1. **[PREFLIGHT.md](docs/PREFLIGHT.md) gates every real takeoff.** The commander's log is not an arming display; QGC is.
2. **Sim-only — never port to the drone:** the sim airframe's gains and limits, `cbf_sim.yaml`'s speeds and landing settle. The drone's parameters come from `starling_1_indoor_params.params` only (iron rule 9).

## What is in this repo

## Flight-lab network architecture

<img src="pictures/Flight_lab_architecture.png" alt="Flight lab network topology — isolated OptiTrack camera network to Mocap PC to GL-MT6000 router splitting the lab LAN 192.168.9.0/24 and a secondary drone-WiFi segment 10.40.2.0/23" width="850">

**Current topology (since 2026-08-27, unchanged by the branch switch):** the OptiTrack camera
rig sits on its own **isolated camera network** — the overhead camera rig runs wall-trunking
up the pillar to an unmanaged LiteWave LS105G switch that talks only to the cameras and the
**Mocap PC**; that traffic never touches the lab LAN. The Mocap PC runs Motive and bridges
the cameras to the lab LAN, broadcasting the NatNet pose stream there (≤240 Hz; ours runs
at 50 Hz). A **GL.iNet GL-MT6000 router at `192.168.9.1`** creates and routes between two
subnets: the **lab LAN `192.168.9.0/24`** — where the ground-control laptop is wired in on
LAN port 4 (`192.168.9.107`) and the Mocap PC lives — and the **`10.40.2.0/23` drone
segment** (gateway `10.40.2.1`), where the **Starlings** sit on WiFi SSID **`StarlingMax2`**
alongside the laptop's own WiFi NIC (`10.40.2.107`). Crazyflies stay on the lab LAN
(`192.168.9.x`, SSID `motive`).

> ⚠️ **Check the drone's actual address before every session** — [CONFIG.md](docs/CONFIG.md) is
> the tie-breaker over this picture. The drone *dials the laptop*, so the laptop IP baked
> into it must be reachable from the drone's segment: the laptop's WiFi NIC
> (`10.40.2.107`) is same-subnet, and the router also routes to its wired `192.168.9.107`.
> Confirm with a ping from the drone before flying — a stale or unreachable value means
> [RUNBOOK](docs/RUNBOOK.md) §B step 3 never gets `session established`.

The router serves both drone SSIDs open on 5 GHz **channel 36**. Crazyflies (also
`192.168.9.x`, SSID `motive`) are commanded over a **Crazyradio 2.4 GHz USB dongle** with a
Crazyswarm2 **software kill switch**, independent of WiFi; Starlings are commanded over
WiFi (uXRCE-DDS / MAVLink) with an **RC-remote hardware kill switch** plus QGroundControl
on the laptop. Exact per-device values (IPs, ports, static leases, SSIDs) live in
[CONFIG.md](docs/CONFIG.md)'s network table — treat that as the single source of truth, since
several are DHCP-drifty until static leases land.

**Security note:** both SSIDs are open (no WPA) — keep the lab network offline / air-gapped
from the internet and any untrusted network.

Router configuration and how to reproduce this setup:
[AI-DA-STC/ground-control-network-setup](https://github.com/AI-DA-STC/ground-control-network-setup).

The earlier two-router topology (the `Mocap_QCGroundControl` D-Link setup, 2026-08-11) is
preserved, prose-only, in the [appendix](docs/MIGRATION.md#12--moved-from-readme-showcase-milestones-in-brief-historical-appendix) at the bottom of
this file.

*(Paths written in prose — `pictures/…`, `patches/…` — are relative to the repo root.
Clickable links inside `docs/` use `../` because they resolve from that folder.)*

| File / folder | What it is |
|---|---|
| [SETUP.md](docs/SETUP.md) | **New laptop** — install, both clones, first build; the messages that look like errors but are normal |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | **How it works** — one-page primer, the flight-lab network, whose document is whose |
| [RUNBOOK.md](docs/RUNBOOK.md) | **START HERE each session** — the fast path, commands only, no background: sim (§A, via `tools/sim_terminals.sh`), real drone (§B), goal flights (§C), post-flight (§D) — sim validated in part, real ⏳ STE on this branch |
| [MIGRATION.md](docs/MIGRATION.md) | **Old branch → this branch**: what was removed/added, what to unlearn, the ordered re-do list, where the archived docs live |
| [BASESTATION.md](docs/BASESTATION.md) | **What you are looking at** — the Foxglove SVG Basestation panel, the `/svg/commander_status` snapshot, the LED strips |
| [TELEOP.md](docs/TELEOP.md) | Hand-flying through the commander with a gamepad: position mode, the two fences, the controller profiles, CMU-doc corrections |
| [SCENARIOS.md](docs/SCENARIOS.md) | The CBF filter and the multi-drone scenarios (formations, random-goal stress test, RC-intruder squeeze) — sim procedures now, real flight at M7 |
| [CONFIG.md](docs/CONFIG.md) | **Single source of truth for lab values** (IPs, SSID, ports, names, flight parameters, AirStack branch/commit) + what to do when one changes |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | **Symptom-indexed fixes — start here when something misbehaves** |
| [GLOSSARY.md](docs/GLOSSARY.md) | Plain-English definitions of every recurring term — linked from every doc |
| [AI_ASSIST.md](docs/AI_ASSIST.md) | Using Claude Code on this repo: what it already knows, the debugging recipes that work here, and what never to let it do |
| [MOCAP.md](docs/MOCAP.md) · [mocap.sh](mocap.sh) · [mocap/](mocap/) | **How the drone knows where it is** — the laptop `./mocap.sh` bridge that replaced natnet_ros2 **and** the Motive-PC operator guide (§6). Unchanged by the branch switch |
| [MILESTONES.md](docs/MILESTONES.md) | The plan **and the work log**: M0–M7 status, code audit, test ledger (reset 2026-10-07), carried-over issues, backlog |
| [PREFLIGHT.md](docs/PREFLIGHT.md) | **Print + laminate for the hangar** — pre-flight checklist, emergency ladder (hold → land → KILL), iron rules |
| [DRONE_SETUP.md](docs/DRONE_SETUP.md) | Provision a NEW Starling from the box — one ordered checklist (WiFi → comms script → params file → Motive body → kill test → optional LEDs) |
| [`starling_1_indoor_params.params`](starling_1_indoor_params.params) | Canonical drone parameter set (872-param QGC export, 2026-09-04) — load via QGC, procedure in DRONE_SETUP §5 |
| [CLAUDE.md](CLAUDE.md) | AI-session entry point — read order, iron flight rules, two-clone warning |
| [AirStack/](AirStack/) | **Full AirStack code snapshot** — `yikuan/SVG_ground_control_dev` @ `b21d28c` since 2026-10-20 (was `yikuan/SVG_ground_control` @ `cf719f0`, 2026-10-07); patch 0001 applied, submodules included — see its own [README](AirStack/README.md) |
| [tools/](tools/) | lab helpers: `sim_terminals.sh` (the sim session — one Terminator window, four tabs inside the containers, RUNBOOK §A0) and `sim_tab.sh` (one tab of it); `make_milestones_doc.py` (Word export of the milestones — **legacy**, [MILESTONES.md](docs/MILESTONES.md) is canonical) |
| [patches/](patches/) | Our bug fixes as patch files — 0001 (still needed, applied in `AirStack/`), 0002 (now fixed upstream — kept for the archive branch), 0003 libmotioncapture (`mocap.sh setup` applies it); story in [MIGRATION.md §12](docs/MIGRATION.md#12--moved-from-readme-showcase-milestones-in-brief-historical-appendix) |
| [assets/](assets/) · [videos/](videos/) | GIFs and source recordings: the previous branch's M1 sim demos, hand-carry tracking check and 09-03 goal-tracking flight, plus this branch's `random_CBF_sim_edited.mp4` (2026-10-21, sim) |
| [pictures/](pictures/) | The two architecture diagrams plus bring-up evidence screenshots (previous branch) |
| [drone-backups/](drone-backups/) | Starling 1's factory `voxl-px4-start` (pulled 2026-07-22, before any script ran) |

## Clone, commit, push

```bash
git clone https://github.com/AI-DA-STC/AirStack-starling-max2.git
```

Two clones live on the lab laptop: `~/AirStack-starling-max2` is the **live** one (docker-mounted —
edit and commit there, on `main`); `~/Documents/GitHub/AirStack-starling-max2` is the **mirror** that
GitHub Desktop pushes from (`git -C ~/Documents/GitHub/AirStack-starling-max2 pull ~/AirStack-starling-max2 main`
first). Assistants never push. Details and the first build: [SETUP.md](docs/SETUP.md).
`omni_pass.env` / `user.config.json` are machine-local and must never be committed; the drone's
SSH password is in CONFIG.md on purpose — keep this repo private.
