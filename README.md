# AirStack-starling-max2 — Starling Max 2 × AirStack lab repo

Everything for flying a ModalAI **Starling Max 2** live under **CMU AirStack** (branch
`daniel/diffaero_ground_control`) with **OptiTrack + Motive** mocap: our notes, milestone
plan, bug-fix patches, demo recordings, **and a complete known-good snapshot of the AirStack
code itself**.

| File / folder | What it is |
|---|---|
| [MILESTONES.md](MILESTONES.md) | Canonical milestone plan + runbooks + troubleshooting (source of truth) |
| [CLAUDE_NOTES.md](CLAUDE_NOTES.md) | Full session handoff for AI-assisted sessions: history, findings, machine state, gotchas |
| [AirStack/](AirStack/) | **Full AirStack code snapshot** (2026-07-20, bug fixes applied, submodules included) — see its own [README](AirStack/README.md) |
| [patches/](patches/) | Our two bug fixes as patch files (for applying to a fresh CMU clone; already applied in `AirStack/`) |
| [tools/make_milestones_doc.py](tools/make_milestones_doc.py) | Generates the Word (.docx) export of the milestone plan (`pip install python-docx`) |
| [assets/](assets/) · [videos/](videos/) | GIFs (embedded in MILESTONES.md) and source screen recordings of Milestone 1 |

## Whose document is whose

There are two separate places documentation lives, written by two different groups:

**1. Written by us:** `README.md`, `MILESTONES.md`, `CLAUDE_NOTES.md`, `patches/`, `tools/`
— our objective, our milestone structure, our lab's IPs/hardware, our findings and fixes.

**2. Written by CMU — everything inside the [`AirStack/`](AirStack/) folder** (it is a
snapshot of their code; on the lab laptop the live copy is `~/AirStack-diffaero/`). Their key
guides, well worth reading:

- [`AirStack/robot/ros_ws/src/svg_ground_control/experiment.md`](AirStack/robot/ros_ws/src/svg_ground_control/experiment.md)
  — **CMU's maintained command reference** for the SVG ground-control experiments (Parts A–D:
  sim, real-drone bring-up, tasks, first flight). The source of truth for command-level
  detail; written for CMU's rig, so substitute our IPs/names.
- [`AirStack/robot/ros_ws/src/svg_ground_control/README.md`](AirStack/robot/ros_ws/src/svg_ground_control/README.md)
  — CMU's package overview (architecture, scenarios, CBF, safety notes).

When our runbooks and CMU's guide disagree, trust CMU's `experiment.md` for commands and our
documents for lab-specific substitutions and lessons learned.

## The milestones, in brief

The project is split into six milestones. Each one adds and proves **one new piece** of the
flight-day system before the next builds on it — so when something fails, we always know
which piece broke. Simulation proves the software, props-off stages prove the connections,
hand-carry proves the position tracking, and only then do propellers spin.

| # | Milestone | One-line goal | Status |
|---|---|---|---|
| 1 | Sim rehearsal | Fly simulated drones with the exact software and commands used on the real drone | ✅ **Validated by us** (2026-07-20) |
| 2 | Ground-station prep | Laptop networking, Motive/OptiTrack settings, clock sync — no drone needed | 🟡 Networking already in the code; Motive + clock-sync are lab tasks |
| 3 | Drone comms (props off) | Real drone's PX4 talking to the laptop over WiFi | 🔵 Code ready (CMU) — awaiting our validation |
| 4 | Mocap → drone (props off) | OptiTrack position fused into the drone's state estimator, axes verified | 🔵 Code ready (CMU) — plus a manual PX4-settings step (QGC) |
| 5 | Hand-carry preflight | Carry the drone around; the software's belief must track reality | 🔵 Code ready (CMU) — awaiting our validation |
| 6 | First flight | Takeoff, hover, land inside the net under AirStack command | 🔵 Code ready (CMU) — config trim + manual PX4 safety settings, then fly |

**Important context on the statuses:** CMU already built AND flight-tested all of this on their
own Starling 2 Max — our project is **replication and validation**, not development. A code
audit (2026-07-20, details in [MILESTONES.md](MILESTONES.md) §3b) confirmed every mechanism for
M3–M6 exists in the `AirStack/` code: the VOXL comms script, the uXRCE-DDS agent, the OptiTrack
driver and mocap→PX4 bridge, the real-drone interfaces, the geofence, and all flight services.
The only things NOT in code (manual, by design) are: clock sync between machines, the
OptiTrack/Motive settings, and PX4-side parameters set through QGroundControl (EKF2
external-vision settings, RC kill switch, failsafes).

Full plan with commands and exit criteria: [MILESTONES.md](MILESTONES.md).

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

### Reference: using CMU's repo directly (advanced — not the normal install)

The normal install (next section) never needs these patches — the code in `AirStack/` already
contains the fixes. This is only for when you want CMU's **newer** commits than our snapshot:

```bash
# clone CMU's branch + its submodules:
git clone -b daniel/diffaero_ground_control https://github.com/castacks/AirStack.git ~/AirStack-cmu
cd ~/AirStack-cmu
git submodule update --init     # (NOT --recurse-submodules — other branches reference
                                #  private repos and the recursive download fails)

# re-apply our two fixes on top (assumes this repo is cloned at ~/AirStack-starling-max2):
git -C simulation/isaac-sim/extensions/PegasusSimulator apply ~/AirStack-starling-max2/patches/0001-zed-camera-info-init-race.patch \
  && git apply ~/AirStack-starling-max2/patches/0002-swarm-commander-logger-severity-crash.patch \
  && echo "both fixes applied" || echo "PATCH FAILED — a fix may already be merged upstream, check the errors"
```

If a patch fails, CMU may have merged that fix upstream (good — skip it) or changed the
surrounding code (the patch needs regenerating — see below).

### Reference: how a patch file is made

A patch is just saved `git diff` output. To make one: edit the code in any git checkout, then:

```bash
git diff > my-fix.patch          # records exactly which lines of which files changed
```

That is how these two were produced — `git diff` run in the AirStack checkout (fix 2) and
inside the PegasusSimulator submodule folder (fix 1). Anyone can then replay the change onto
another copy of the same code with `git apply my-fix.patch`.

### Setting up AirStack on a NEW machine

You do NOT need any of this on the lab laptop — it is already set up. This is the recipe for
a teammate's PC or a re-install. Steps 1–2 and 4–5 are copy-paste; Step 3 needs files from an
existing machine.

#### Step 1 — Download the code

This repo contains everything, including the fixed AirStack code — one clone is the whole
install:

```bash
git clone https://github.com/AI-DA-STC/AirStack-starling-max2.git ~/AirStack-starling-max2
cd ~/AirStack-starling-max2/AirStack      # ← your WORKING FOLDER — all airstack commands run from here
```

No submodule step, no patch step — the code snapshot is complete and already fixed.

> **Reference — where this code originally came from:** CMU's branch
> [`daniel/diffaero_ground_control`](https://github.com/castacks/AirStack/tree/daniel/diffaero_ground_control)
> of castacks/AirStack (the only branch with the ground-controller + mocap pipeline; snapshot
> taken 2026-07-20 at commit `f544c743`). You only need CMU's repo if you want their *newer*
> commits — in that case see the [Patches](#patches--bug-fixes-we-made-to-airstack-backup-copies)
> section for how to re-apply our fixes on top.

Note: after you start using the stack, build artifacts and generated config files will appear
as untracked/ignored noise in GitHub Desktop — that is expected.

#### Step 2 — One-time host setup

Requires Ubuntu 22.04+ and an NVIDIA GPU with a recent driver (Isaac Sim needs it). Skip any
part already installed on the machine. (A `git hooks … No such file or directory` message
here is harmless — the code folder is not its own git repo.)

```bash
./airstack.sh setup      # puts the "airstack" command on your PATH — open a NEW terminal after
airstack install         # installs Docker Engine + NVIDIA Container Toolkit (asks for sudo)
docker info              # verify Docker runs (start it with: sudo systemctl start docker)
```

#### Step 3 — Copy two config files git does not carry

Credentials / machine config — CMU keeps them out of git on purpose. Get them from an existing
lab machine, or create them from the `*_TEMPLATE` files sitting next to them:

- `simulation/isaac-sim/docker/omni_pass.env`
- `simulation/isaac-sim/docker/user.config.json`

#### Step 4 — Build the robot Docker image

REQUIRED on this branch: it bakes in MicroXRCEAgent (the real-drone link) and pins the ROS
domain — a plain `up` without this is broken. The other images (isaac-sim, gcs) download
automatically on first `up`; isaac-sim additionally needs the credentials from Step 3.

```bash
./airstack.sh image-build robot-desktop
```

#### Step 5 — Final setup check

```bash
grep -E '^(COMPOSE_PROFILES|AUTOLAUNCH|NUM_ROBOTS)' .env
#   want: COMPOSE_PROFILES="desktop,isaac-sim"  AUTOLAUNCH="false"  NUM_ROBOTS="1"
```

**Setup is now complete.** You never need to repeat Steps 1–5 on this machine (except Step 4's
image rebuild if the Dockerfile ever changes). Starting and using the stack is a separate,
every-session routine — next section.

## Running AirStack (after setup, and at the start of every session)

```bash
cd ~/AirStack-starling-max2/AirStack     # your working folder (original lab laptop: ~/AirStack-diffaero)
./airstack.sh up              # start the containers (robot, isaac-sim, gcs) — takes ~1 min
./airstack.sh status          # all three should say "Up"

# open a shell INSIDE the robot container — this is where ALL ros2/build commands run
# (rule of thumb: prompt "root@..." = inside, correct; "yourname@..." = your laptop, wrong)
./airstack.sh connect robot --command=bash

# inside the container, compile the workspace:
cd ~/AirStack/robot/ros_ws && bws && sws
#   first ever build ~4 min; later sessions it finishes in seconds unless code changed
```

**Why is compiling here and not in setup?** The code can only be compiled *inside* the robot
container (that is where ROS 2 lives — your laptop has none of it). So `bws` necessarily comes
after `up` and `connect`. Do not paste this whole block at once: `connect` opens an interactive
shell and swallows the lines after it — **type the `bws` line yourself at the `root@` prompt.**

**Two messages that look like errors but are NORMAL on a fresh machine:**

- `Workspace not built yet. Please make sure to build first with 'bws'` — printed by every new
  container shell until the **first successful `bws`** has completed. It is the shell telling
  you to do the very next command, not a build failure. If you keep seeing it across sessions,
  it means `bws` has still never actually run to completion.
- `ROBOT_NAME: unknown-robot` in `./airstack.sh status` — harmless on this branch. The SVG
  ground-control stack names its drones `drone_1/2/3` from config files and never uses
  ROBOT_NAME. What matters is `ROS_DOMAIN_ID: 1` next to it, which should read 1.

**At this point the stack is running and compiled — but nothing is flying yet.** What you do
next depends on your goal:

- **Fly in simulation** (recommended first) → follow the **Milestone 1 runbook** in
  [MILESTONES.md](MILESTONES.md) §5, which continues from exactly this point: spawn the drones
  in Isaac Sim → start the per-drone interfaces → launch the ground controller → open RViz →
  call the takeoff/start/land services.
- **Real-drone work** (props off, drone on the bench) → Milestones 3+ in
  [MILESTONES.md](MILESTONES.md) §6, backed by CMU's guide
  ([`AirStack/robot/ros_ws/src/svg_ground_control/experiment.md`](AirStack/robot/ros_ws/src/svg_ground_control/experiment.md), Part B).
- **Done for the day** → `./airstack.sh down` (from the same folder) stops everything.

**These files become unnecessary** once CMU merges the fixes into their repo — fix 1 is
already on their `fix/camera-init` branch awaiting review; fix 2 we still need to report to
them. When both are merged upstream, delete this folder.

## Security note

`omni_pass.env` (Omniverse credentials) and `user.config.json` are deliberately **not** in this
repo — they are machine-local and gitignored upstream for a reason. Copy them between checkouts
by hand.
