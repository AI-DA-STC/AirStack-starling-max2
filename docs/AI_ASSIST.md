# Working with an AI assistant on this repo

> **What this is:** how the lab uses Claude Code (or a similar assistant) on this repository
> without it breaking something, and the debugging recipes that have proven to work here.
> **Who should read it:** anyone new who will ask an assistant to look at this code, the sim,
> or a flight problem. Five minutes. Terms in [GLOSSARY.md](GLOSSARY.md).

## 1 · What the assistant already knows, and where it lives

| Where | What it is | Whose |
|---|---|---|
| [`CLAUDE.md`](../CLAUDE.md) (repo root) | The lab's rules for the assistant: the doc map, the 9 iron rules, the two-clone workflow, "never push". Read automatically at the start of every session. | ours |
| [`docs/`](.) | The human docs. The assistant reads them like you do; keep them true and it stays true. | ours |
| [`AirStack/AGENTS.md`](../AirStack/AGENTS.md) + [`AirStack/.agents/skills/`](../AirStack/.agents/skills/) | CMU's own guide and 18 step-by-step "skills" for agents: `debug-module`, `use-airstack-cli`, `test-in-simulation`, `configure-multi-robot`, `write-launch-file`, … Written for AirStack in general, not for our rig. The `svg-release-branches` skill describes CMU's dev→release branch workflow — **not ours** (we commit to `main`). | CMU |
| The assistant's own memory (outside the repo) | Notes it keeps between sessions about this project: what was tried, what failed, which clone is live. It will cite them; they can be stale — the repo wins. | — |

## 2 · Recipes that work here

Each of these cost an afternoon to learn. Ask for them by name.

1. **"Read the status topic first."** One message answers most "what is the swarm doing" questions:
   `ros2 topic echo /svg/commander_status --once` (inside the robot container). States, positions,
   last command results, CBF activity, fence latch.
2. **Run ROS commands through the container, interactively.** From the laptop:
   `docker exec airstack-robot-desktop-1 bash -ic '<command>'`. The `-i` loads the container's
   bashrc, which sources the workspace and sets the ROS domain. Without it the command silently
   talks to the wrong domain and sees nothing.
3. **"Parse the PX4 logs."** For anything "the drone did not do X" in sim, the truth is in PX4's
   own flight logs, not in the commander's output. They sit inside the Isaac container at
   `/tmp/tmp*/log/<date>/<time>.ulg`, one per drone (`MAV_SYS_ID` 2/3/4 = drone_1/2/3), and
   `pyulog` is installed there. Ask for the land-detector flags, command ACKs, body rates,
   setpoints versus flown values. Ledger #9 and #10 were solved this way in minutes.
4. **"Prove it by killing it."** For any watchdog or respawn claim, make the assistant kill the
   process on purpose (in a throwaway namespace, never a flying drone) and show the log line
   where it comes back. Ledger #11.
5. **"Investigate with subagents first and tell me before changing anything."** For a bug with
   several candidate causes, this phrase makes it dispatch read-only readers (PX4 source, the
   commander, the logs) and come back with evidence, not a patch. It then asks for a go.
6. **Live parameters before file edits.** Most commander gains and all PX4 parameters can be
   set live (`ros2 param set /swarm_commander …`, MAVROS `param/set`). Sweep first, write the
   winning value into the YAML or airframe after. Ledger #10 was a five-setting sweep in hover.
7. **"Score the run."** After a camera-world flight, `localisation/scripts/score_run.sh <run> 1` (laptop;
   isaac-sim and exploration containers up) writes APE/RPE and a top-down plot to
   `localisation/results/bags/<run>/`. The pipeline is drawn in [localisation/README.md](../localisation/README.md).
8. **"One change per step."** For a heavy sim change (new world, more cameras), ask for the validation ladder:
   one change, one pass test, stop and report. [VALIDATION.md](../localisation/scenes/construction_site/VALIDATION.md).

## 3 · How to ask so it stays safe

- Say which world you mean: **sim** or **real drone**. Many values exist twice (landing settle,
  rate gains, speed caps) and only the sim copy may be changed freely — iron rule 9.
- Ask for a **plan first** on anything that touches `swarm_commander.py`, the real configs
  (`*_ours.yaml`), `px4_interface`, or the vendored `AirStack/` folder. "Show me the plan, then
  wait" works.
- Expect it to **commit in the live clone** (`~/AirStack-starling-max2`) and pull into the
  mirror; **you push** from GitHub Desktop. If it offers to push, say no.
- When it says a test passed, ask for the command and the output line. When it says a drone
  disarmed, ask for the `armed: false` echo. It will have them.
- Phase-by-phase "what to expect" before a flight or a choreography change is a standing
  request in this lab — ask for it if it is missing.

## 4 · What never to let it do

| Never | Why |
|---|---|
| `git push`, force pushes, rewriting history | the user pushes; the mirror and GitHub must stay in step |
| Port a sim value to the real drone (`starling_1_indoor_params.params`, QGC, or an `_ours` yaml) | sim airframe rate gains ×0.5, gyro filters 80/40, `LNDMC_ROT_MAX` 300, motor lag off, the MAVROS respawn, `cbf_sim.yaml`'s speeds 2.0 / 4.0 / 6.0 and its landing settle 2.0 s + retry are **sim-only — never port to the drone** — iron rule 9 |
| `force_set` on MAVROS parameter writes | it aborted `mavros_node` mid-flight (ledger #11) |
| Press Stop ▶ Play in the Isaac window, or script it | Pegasus leaks the old vehicles; full relaunch needed ([TROUBLESHOOTING](TROUBLESHOOTING.md)) |
| Run `test/functional_*.py` with the real stack up | they publish fake odometry on live topics — iron rule 4 |
| Edit files under `~/AirStack` (the raw CMU clone) | nothing runs from there; the live tree is `~/AirStack-starling-max2/AirStack` |
| Treat a commander log line as proof of a hardware state | iron rules 2 and 5: QGC decides armed/disarmed, ACKs are not arming |
| Start or stop Isaac with nothing watching the laptop's WiFi | Isaac start/stop crashed the WiFi firmware twice (2026-10-22) and dropped the remote desktop. Keep `localisation/scripts/sim_resources_watch.sh` running ([TROUBLESHOOTING](TROUBLESHOOTING.md#simulation-isaac-sim--px4-sitl--mavros)) |
| Call a sim VO score "ground truth" | the reference is PX4's EKF2 on simulated GPS; say "vs EKF2" (the run records do) |

## 5 · Known limits

- It cannot see the Isaac window or Foxglove. Screenshots in the chat work; so does asking it to
  read the status topic or the logs instead.
- It cannot relaunch things in **your** terminal tabs. It will tell you which tab to Ctrl-C and
  what to paste.
- Its memory of earlier sessions can be stale after a branch bump; the repo and `git log` are
  the record. `docs/record/LEDGER.md` and the project page are where it should look first, and where you should check its
  claims.
