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

## Patches — bug fixes we made to AirStack (backup copies)

While getting AirStack working, we found and fixed **two bugs in CMU's code**. The fixed code
runs on the lab laptop (in `~/AirStack-diffaero`) — **nothing in this folder needs to be run
for the lab laptop; it is already fixed there.**

The `patches/` folder holds a **backup copy of each fix** as a small text file (a git
"patch" — a file that records exactly which lines of which file were changed, so git can
re-apply the same change to another copy of the code). We keep them because anyone who
downloads AirStack fresh from CMU's GitHub **gets the bugs again** — CMU has not merged the
fixes yet. With these files, a new setup re-applies both fixes in seconds instead of
re-debugging them.

| Patch file | Bug it fixes | Symptom without the fix |
|---|---|---|
| `0001-zed-camera-info-init-race.patch` | Camera startup race in the Isaac Sim Pegasus extension | The drone's right stereo camera randomly never publishes → navigation flies "blind" and becomes erratic (took us days to diagnose) |
| `0002-swarm-commander-logger-severity-crash.patch` | Logging crash in the SVG ground controller | The ground-controller process **dies mid-flight** the first time any drone command fails |

### When would anyone use these? (not on the lab laptop)

**Only when setting up AirStack on a NEW machine** (a teammate's PC, a re-install, a fresh
`git clone`). After cloning AirStack's `daniel/diffaero_ground_control` branch (and its
submodules), run this — **edit only the two paths on the first two lines**, the rest is
copy-paste:

```bash
# EDIT THESE TWO LINES to match your machine:
NOTES=~/Documents/GitHub/starling-airstack-notes   # where you cloned THIS repo
cd ~/AirStack-diffaero                             # your fresh AirStack clone

# then run as-is:
git -C simulation/isaac-sim/extensions/PegasusSimulator apply "$NOTES/patches/0001-zed-camera-info-init-race.patch"
git apply "$NOTES/patches/0002-swarm-commander-logger-severity-crash.patch"
echo "both fixes applied"
```

(Fix 1 targets the PegasusSimulator sub-folder because it is its own git repo — a
"submodule" — so the patch must be applied from inside it; the `git -C` flag does that.)
Both patch files are verified to apply cleanly against the branch as of 2026-07-20.

**These files become unnecessary** once CMU merges the fixes into their repo — fix 1 is
already on their `fix/camera-init` branch awaiting review; fix 2 we still need to report to
them. When both are merged upstream, delete this folder.

## Security note

`omni_pass.env` (Omniverse credentials) and `user.config.json` are deliberately **not** in this
repo — they are machine-local and gitignored upstream for a reason. Copy them between checkouts
by hand.
