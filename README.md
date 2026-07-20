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
