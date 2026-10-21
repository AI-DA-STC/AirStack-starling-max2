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
