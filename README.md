# Starling Max 2 × AirStack — Lab Notes

Working notes, milestone plan, runbooks, and local patches for flying a ModalAI **Starling
Max 2** live under **CMU AirStack** (branch `daniel/diffaero_ground_control`) with
**OptiTrack + Motive** mocap.

| File | What it is |
|---|---|
| [MILESTONES.md](MILESTONES.md) | Canonical milestone plan + runbooks + troubleshooting (source of truth) |
| [CLAUDE_NOTES.md](CLAUDE_NOTES.md) | Full session handoff for AI-assisted sessions: history, findings, machine state, gotchas |
| [patches/](patches/) | Local fixes not yet upstream (apply to a fresh AirStack checkout with `git apply`) |
| [tools/make_milestones_doc.py](tools/make_milestones_doc.py) | Generates the Word (.docx) export of the milestone plan (`pip install python-docx`) |
| [assets/](assets/) · [videos/](videos/) | GIFs (embedded in MILESTONES.md) and source screen recordings of Milestone 1 |

## Whose document is whose

**Mine (this repo — lab-specific, maintained by me/Jeremy):**

- `README.md`, `MILESTONES.md`, `CLAUDE_NOTES.md`, `patches/`, `tools/` — our objective, our
  milestone structure, our lab's IPs/hardware, our session findings and fixes.

**CMU's (upstream, live in the AirStack checkout — NOT in this repo):**

- `robot/ros_ws/src/svg_ground_control/experiment.md` — **CMU's maintained command reference**
  for the SVG ground-control experiments (Parts A–D: sim, real-drone bring-up, tasks, first
  flight). The upstream source of truth for command-level detail; written for CMU's rig, so
  substitute our IPs/names.
- `robot/ros_ws/src/svg_ground_control/README.md` — CMU's package overview (architecture,
  scenarios, CBF, safety notes).

Full paths on the lab laptop: `~/AirStack-diffaero/robot/ros_ws/src/svg_ground_control/…`.
When my runbooks and CMU's guide disagree, trust CMU's `experiment.md` for commands and this
repo for lab-specific substitutions and lessons learned.

## Milestone 1 at a glance

![Takeoff and land](assets/takeoff_and_land.gif)

*Three SITL drones under the SVG ground controller: `takeoff` → hover scenario → `land`
(RViz view, 2× speed). See [MILESTONES.md](MILESTONES.md) for the geofence-breach clip and
the full runbook.*

## Patches

| Patch | Applies in | Status upstream |
|---|---|---|
| `0001-zed-camera-info-init-race.patch` | PegasusSimulator **submodule** (`simulation/isaac-sim/extensions/PegasusSimulator`) | CMU branch `fix/camera-init`, PR pending — drop patch once merged |
| `0002-swarm-commander-logger-severity-crash.patch` | AirStack repo root | **Not yet reported** — commander process dies on first failed service report (rclpy per-call-site severity cache) |

Apply:

```bash
cd <airstack-checkout>/simulation/isaac-sim/extensions/PegasusSimulator
git apply /path/to/patches/0001-zed-camera-info-init-race.patch
cd <airstack-checkout>
git apply /path/to/patches/0002-swarm-commander-logger-severity-crash.patch
```

## Security note

`omni_pass.env` (Omniverse credentials) and `user.config.json` are deliberately **not** in this
repo — they are machine-local and gitignored upstream for a reason. Copy them between checkouts
by hand.
