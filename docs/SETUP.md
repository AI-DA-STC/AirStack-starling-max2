# SETUP — a new laptop, from zero to a running stack

> **DO.** One-time install on a new machine, then what every session starts with. Moved
> verbatim from the front-page README on 2026-10-21. Session commands themselves:
> [RUNBOOK.md](RUNBOOK.md) (sim §A, real drone §B).

## Setting up AirStack on a NEW machine

> ⚠️ **Two clones exist on the LAB laptop:** `~/AirStack-starling-max2` is the
> **live/flying copy** — it is what docker mounts, and it is the copy every document in this
> repo assumes; `~/Documents/GitHub/AirStack-starling-max2` is the git mirror used for
> pushing. On a fresh machine there is no split — clone to `~/AirStack-starling-max2` and
> that one folder plays both roles.
>
> **Already set up for the previous branch?** Skip to [MIGRATION.md](MIGRATION.md) §6 —
> the ordered re-do list (rebuild, recreate the container, install the panel, re-provision
> the drone). Steps 1–5 below are unchanged.

You do NOT need any of this on the lab laptop — it is already set up. This is the recipe for
a teammate's PC or a re-install. Every step is copy-paste; Step 2 asks one question (just
press Enter).

#### Step 1 — Download the code

**Requirements, up front:** **Ubuntu 24.04** (hard requirement — the host mocap bridge in
Step 5 needs ROS 2 Jazzy); an **NVIDIA GPU with a recent driver — only for simulation**
(Isaac Sim needs it; real-drone work (§B) needs no GPU and no Isaac Sim); and free disk in
the **tens of GB** (docker images and Isaac Sim assets dominate).

This repo contains everything, including the fixed AirStack code — one clone is the whole
install:

```bash
git clone https://github.com/AI-DA-STC/AirStack-starling-max2.git ~/AirStack-starling-max2
cd ~/AirStack-starling-max2/AirStack      # ← your WORKING FOLDER — all airstack commands run from here
```

No submodule step, no patch step — the code snapshot is complete and already fixed. One
binary download is still needed (CMU's `.gitignore` excludes it): the OptiTrack NatNet SDK,
which the workspace build requires even though our mocap bridge doesn't use it:

```bash
cd ~/AirStack-starling-max2/AirStack/robot/ros_ws/src/perception/natnet_ros2 && ./install_sdk.sh
```

> **Reference — where this code originally came from:** CMU's working branch
> [`yikuan/SVG_ground_control_dev`](https://github.com/castacks/AirStack/tree/yikuan/SVG_ground_control_dev)
> of castacks/AirStack, snapshot at `b21d28c` (2026-10-20); its squash-release line is
> [`yikuan/SVG_ground_control`](https://github.com/castacks/AirStack/tree/yikuan/SVG_ground_control),
> whose `cf719f0` was our 2026-10-07 snapshot. It is a **sibling** of the previous branch,
> not its successor — [MIGRATION.md](MIGRATION.md) §1. You only need CMU's repo if you
> want their *newer* commits — see the [patches appendix](MIGRATION.md#12--moved-from-readme-showcase-milestones-in-brief-historical-appendix)
> for how to re-apply our fix on top.

Note: after you start using the stack, build artifacts and generated config files will appear
as untracked/ignored noise in GitHub Desktop — that is expected.

#### Step 2 — One-time host setup

Skip any part already installed on the machine. (A `git hooks … No such file or directory`
message here is harmless — the code folder is not its own git repo.)

```bash
./airstack.sh setup      # puts the "airstack" command on your PATH — open a NEW terminal after
airstack install         # installs Docker Engine + NVIDIA Container Toolkit (asks for sudo)
docker info              # verify Docker runs (start it with: sudo systemctl start docker)
```

`setup` asks one interactive question — **"API Token:" for the AirLab Nucleus login. Just
press Enter to leave it blank.** Despite the "Skipping" message, `setup` still generates the
two config files Isaac Sim needs (`omni_pass.env`, `user.config.json`).

#### Step 3 — Build the robot Docker image

REQUIRED: it bakes in MicroXRCEAgent (the real-drone link), Foxglove Studio and the
`foxglove_bridge`, and pins the ROS domain — a plain `up` without this is broken. The other
images (isaac-sim, gcs) download automatically on first `up`. (The Dockerfile is identical
to the previous branch's — a machine that built it before does not need to rebuild.)

```bash
./airstack.sh image-build robot-desktop
```

#### Step 4 — Final setup check

```bash
grep -E '^(COMPOSE_PROFILES|AUTOLAUNCH|NUM_ROBOTS)' .env
#   want: COMPOSE_PROFILES="desktop,isaac-sim"  AUTOLAUNCH="false"  NUM_ROBOTS="1"
```

#### Step 5 — one-time mocap bridge + ground-station tools (needs internet — do BEFORE your first hangar session)

The mocap bridge runs **on the laptop itself, not in the container** — the container's ROS
does not count. So the host needs its own ROS 2 Jazzy, which is why Step 1 requires
Ubuntu 24.04.

First, configure the ROS 2 apt repository (the standard recipe from
[docs.ros.org](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html) for
Ubuntu 24.04):

```bash
# a) enable the ROS 2 apt repository:
sudo apt install software-properties-common
sudo add-apt-repository universe
sudo apt update && sudo apt install curl -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt update
```

```bash
# b) host ROS 2 Jazzy + build deps + ADB + AppImage runtime — one line:
sudo apt install ros-jazzy-desktop python3-colcon-common-extensions build-essential cmake git libpcl-dev libeigen3-dev libfmt-dev ros-jazzy-eigen3-cmake-module android-tools-adb libfuse2

# c) build the mocap bridge (clones + patches + builds ~/mocap_ws, ~5 min):
cd ~/AirStack-starling-max2 && ./mocap.sh setup
```

**QGroundControl:** download the AppImage from <https://qgroundcontrol.com>, save it as
`~/QGroundControl-x86_64.AppImage`, then:

```bash
chmod +x ~/QGroundControl-x86_64.AppImage
sudo usermod -aG dialout $USER    # serial-port access (log out/in to take effect)
sudo apt remove modemmanager      # it grabs the serial ports QGC needs
```

#### Step 6 — the operator view (new on this branch)

The **Foxglove SVG Basestation** panel is installed into the robot container automatically
at every `up`. To run Foxglove Studio **on the laptop** instead (nicer on a laptop screen),
install Studio from <https://foxglove.dev/download>, then install the panel into it once and
restart Studio:

```bash
cd ~/AirStack-starling-max2/AirStack && python3 robot/ros_ws/src/svg_ground_control/foxglove/install.py
```

Connect it to `ws://localhost:8765` whenever the commander is running, and import the layout
file once. Full guide: [BASESTATION.md](BASESTATION.md) §2. (Alternative with nothing
to install: `use_foxglove_studio:=true` on the commander launch opens Studio inside the
container.)

**Setup is now complete.** Starting and using the stack is a separate, every-session routine
— next section.


## Running AirStack (after setup, and at the start of every session)

> **Fast path each session: [RUNBOOK.md](RUNBOOK.md)** — commands only, sim (§A), real
> drone (§B), goal flights (§C), post-flight (§D). Follow it verbatim; the notes below cover
> what the commands themselves don't say.

**Two ways into the containers.** For the **sim**, `~/AirStack-starling-max2/tools/sim_terminals.sh`
(laptop) brings the containers up and opens one Terminator window with four tabs — **Isaac
Sim · Interfaces · Commander · Cockpit** — each already inside its container with that tab's
commands printed ([RUNBOOK.md](RUNBOOK.md) §A0). For the **real drone** (and as the sim
alternative), `./airstack.sh connect robot` attaches to a tmux session called `bringup` that
the container creates at `up`: 8 panes, every one a container shell (`root@…#`) with the
workspace sourced; `Ctrl-b` + arrow moves between panes, `Ctrl-b d` detaches, the session
survives closing the terminal. Put each long-running launch in its own tab or pane. The old
per-step `connect robot --command=bash` still works for a throw-away shell.

**Optional camera world (sim stereo VO).** The construction-site files and the exploration docker image are
**not in git** and exist only on the lab laptop. Install and prerequisites: [localisation/README.md](../localisation/README.md).

**What `bws` / `sws` are, and when you need them:** inside the container, `bws` builds the
workspace and `sws` sources the result into that shell. The first ever build takes ~4 min.
After that you rebuild **only after NEW entry points or files** (e.g. right after a snapshot
bump) — edits to existing `.py`/`.yaml` files take effect on the next launch with no rebuild,
because the install is symlinked. The code can only be compiled *inside* the robot container
(that is where ROS 2 Jazzy for the workspace lives — the host's ROS 2 Jazzy from Step 5 is
for the mocap bridge only). In tmux, run `bws` in pane 0; the other panes wait for it and
source automatically. After the first `bws`, `tmux attach -t bringup` — expect pane 0 = launch, panes 1–7 = shells titled "shell".

**Messages that look like errors but are NORMAL:**

- `Workspace not built yet. Please make sure to build first with 'bws'` — printed by every new
  container shell until the **first successful `bws`** has completed.
- `ROBOT_NAME: unknown-robot` in `./airstack.sh status` — harmless. The SVG stack names its
  drones from config files. What matters is `ROS_DOMAIN_ID: 1` next to it.
- `groups: cannot find name for group ID 992` on every `connect` — harmless (host GPU
  `render` group with no name inside the container).
- `Foxglove extension install failed (non-fatal)` at `up` — the panel installer could not
  write `~/.foxglove-studio/extensions` inside the container; Studio on the laptop is
  unaffected. Re-run the installer by hand if you use in-container Studio.
- `led_controller`: `no heartbeat from drone_1` — no LED strip fitted (M6). Harmless, or
  launch with `use_led:=false`.


## Security note

`omni_pass.env` (Omniverse credentials) and `user.config.json` are deliberately **not** in this
repo — they are machine-local and gitignored upstream for a reason. They are generated on each
machine by `./airstack.sh setup` and must never be committed. The drone's SSH password is
recorded in [CONFIG.md](CONFIG.md) deliberately — keep this repo private.

