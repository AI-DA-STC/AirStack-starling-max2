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
| [tools/make_milestones_doc.py](tools/make_milestones_doc.py) | Word (.docx) export generator — **legacy** (pre-migration paths); [MILESTONES.md](MILESTONES.md) is canonical |
| [assets/](assets/) · [videos/](videos/) | GIFs (embedded in MILESTONES.md) and source screen recordings of Milestone 1 |

## Whose document is whose

There are two separate places documentation lives, written by two different groups:

**1. Written by us:** `README.md`, `MILESTONES.md`, `CLAUDE_NOTES.md`, `patches/`, `tools/`
— our objective, our milestone structure, our lab's IPs/hardware, our findings and fixes.

**2. Written by CMU — everything inside the [`AirStack/`](AirStack/) folder** (it is a
snapshot of their code; the live working copy is `~/AirStack-starling-max2/AirStack/`). Their key
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

## How the system actually works (read once — it makes everything else make sense)

**The one-liner: PX4 is the pilot, AirStack is mission control, and the RC kill switch
outranks both.**

### Who does what

The Starling's onboard **PX4 autopilot** does all the *flying*: keeping the aircraft level,
tracking commanded motion, motor control, state estimation (its EKF2), and failsafes. It has
no opinion about the mission. **AirStack on the ground laptop** does all the *deciding*:
when to take off, where to hover, when to land — but never touches stabilization. Nothing on
the laptop replaces or imitates PX4; AirStack sits **above** it.

In our setup we use only a thin slice of AirStack: the mocap driver (`natnet_ros2`), the
mocap→PX4 bridge (`mocap_bridge`), the uXRCE-DDS transport (`MicroXRCEAgent` +
`px4_interface`), and the **swarm commander** (takeoff/hold/land services, scenario policy,
CBF safety filter, geofence). The famous autonomy layers (planners, perception, mapping)
exist in the code but are never launched here — they are for the *outdoor* form of AirStack,
where the deciding moves onto the drone's own computer.

### The two data streams (both over the lab LAN/WiFi — why host networking matters)

```
POSITION IN:   Motive ─► natnet_ros2 ─► mocap_bridge ─► WiFi ─► PX4's EKF2 (fused ONBOARD —
               the laptop does no state estimation; it is only the courier)

COMMANDS OUT:  scenario/policy ─► CBF safety filter ─► velocity setpoint (20 Hz) ─► WiFi ─► PX4
```

### Offboard mode — the contract that makes this work

PX4 flight modes split by *who generates the goal*:

- **Onboard modes** (Position, Hold, Mission, Land…): PX4 generates its own goals — from RC
  sticks, waypoints, or built-in logic. Fully self-contained.
- **Offboard mode** (what we use): PX4 outsources goal-generation to an external computer,
  which must stream setpoints continuously (≥2 Hz, ours streams at 20 Hz). If the stream
  stops, PX4 declares offboard-loss and falls back to a failsafe — it never just tumbles.

(Naming collision warning: AirStack's `AUTONOMY_ROLE=onboard/offboard` in the compose files
is about *which computer runs autonomy software* — unrelated to PX4's flight modes.)

### Inner and outer control loops — what the laptop takes over, and what it never touches

PX4's control is a cascade of four loops, each one's output feeding the next, each inner one
faster: **position (~50 Hz) → velocity (~50 Hz) → attitude (~250 Hz) → rate (~1000 Hz) →
motors**. Offboard setpoints inject at ONE level: everything *above* the injection point is
bypassed, everything at/below keeps running onboard.

We inject at the **velocity** level: the laptop's policy + CBF replace only PX4's outermost
(position/guidance) loop, while velocity, attitude, and rate loops all keep running onboard
at full speed. That is why WiFi latency and dropouts are survivable — everything that keeps
the aircraft upright never leaves the drone; only the slow "where to next" decision crosses
the network. (It also bounds agility: velocity-level control is responsive, not acrobatic —
truly aggressive flight would need attitude/rate-level streaming, which WiFi cannot support.)

### The safety chain (in order of authority)

1. **RC kill switch** — motor cutoff, outranks everything, the only true stop.
2. **PX4 onboard failsafes** — offboard-loss action, low battery, RC-override to an onboard
   mode. One mode-switch away at all times; PX4 can always fly itself.
3. **Commander geofence + hold** — software freeze-in-place, first line, not a motor cutoff.

The drone "not deciding where to go" is true only while everything is healthy — the moment
anything isn't (link loss, kill switch, mode switch), deciding snaps back onboard by design.

## Milestone 1 at a glance

![Takeoff and land](assets/takeoff_and_land.gif)

*Three SITL drones under the SVG ground controller: `takeoff` → hover scenario → `land`
(RViz view, 2× speed). See [MILESTONES.md](MILESTONES.md) for the geofence-breach clip and
the full runbook.*

## Patches — bug fixes we made to AirStack (backup copies)

While getting AirStack working, we found and fixed **two bugs in CMU's code**. The fixed code
runs on the lab machines (in `~/AirStack-starling-max2/AirStack`) — **nothing in this folder needs to be run
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
a teammate's PC or a re-install. Every step is copy-paste; Step 2 asks one question (just
press Enter).

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

`setup` asks one interactive question — **"API Token:" for the AirLab Nucleus login. Just
press Enter to leave it blank** (that login is for CMU's asset server; we don't use it).
Despite the "Skipping" message, `setup` still generates the two config files Isaac Sim needs
(`omni_pass.env`, `user.config.json`), so nothing further is required.

#### Step 3 — Build the robot Docker image

REQUIRED on this branch: it bakes in MicroXRCEAgent (the real-drone link) and pins the ROS
domain — a plain `up` without this is broken. The other images (isaac-sim, gcs) download
automatically on first `up`.

```bash
./airstack.sh image-build robot-desktop
```

#### Step 4 — Final setup check

```bash
grep -E '^(COMPOSE_PROFILES|AUTOLAUNCH|NUM_ROBOTS)' .env
#   want: COMPOSE_PROFILES="desktop,isaac-sim"  AUTOLAUNCH="false"  NUM_ROBOTS="1"
```

**Setup is now complete.** You never need to repeat Steps 1–4 on this machine (except Step 3's
image rebuild if the Dockerfile ever changes). Starting and using the stack is a separate,
every-session routine — next section.

## Running AirStack (after setup, and at the start of every session)

**A — on your laptop** (safe to paste as one block):

```bash
cd ~/AirStack-starling-max2/AirStack     # your working folder — same path on every machine
./airstack.sh up              # start the containers (robot, isaac-sim, gcs) — takes ~1 min
./airstack.sh status          # all three should say "Up"
./airstack.sh connect robot --command=bash   # opens a shell INSIDE the robot container
```

After `connect`, your prompt changes to `root@...` — you are now inside the container.
(Rule of thumb forever: `root@...` = inside, correct; `yourname@...` = your laptop, wrong
place for any `ros2`/build command.)

**B — inside the container** (paste this only AFTER the prompt shows `root@`; it will not work
if pasted together with block A — the `connect` command swallows anything after it):

```bash
cd ~/AirStack/robot/ros_ws && bws && sws
#   first ever build ~4 min; later sessions it finishes in seconds unless code changed
```

**Why is compiling here and not in setup?** The code can only be compiled *inside* the robot
container (that is where ROS 2 lives — your laptop has none of it). So `bws` necessarily comes
after `up` and `connect`.

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
repo — they are machine-local and gitignored upstream for a reason. They are generated on each
machine by `./airstack.sh setup` (press Enter at the API Token prompt) and must never be
committed.
