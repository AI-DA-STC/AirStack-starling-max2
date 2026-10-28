# tools/ — laptop-side helpers (sim session, docs checker, hover + step acceptance)

> **DO · SIM.** Everything here runs on the laptop or inside the sim containers. Nothing in this folder
> touches the real drone, and nothing measured by these tools is ported to it (CLAUDE.md iron rule 9).

## What is here

| File | What it does |
|---|---|
| `sim_terminals.sh` / `sim_tab.sh` | the four-tab sim session (Isaac Sim · Interfaces · Commander · Cockpit) — [RUNBOOK §A](../docs/RUNBOOK.md) |
| `make_milestones_doc.py` | legacy `.docx` export of MILESTONES.md |
| `docs_check/` | the documentation checker — `tools/docs_check/check_docs.sh` (0 FAIL required before a docs commit) |
| `sim_hover_step_run.sh` | **orchestrator** for the hover + 1 m step acceptance (MILESTONES §4 "Starling model: spawn + hover + steps"), no terminal needed. Phases, in `all` order: `precheck up watch isaac interfaces commander params fly collect down analyse report`; extra: `all`, `status`, `ifgates` (odometry gates only). Env: `STEPS_PER_AXIS` (default 3, alternating +1/−1 m), `ISAAC_KIT_ARGS` (opt-in extra Isaac Kit args, default none) |
| `sim_hover_step_test.sh` | the flight script (ours — moved out of CMU's tree; `wait_s` is a real sleep because `/clock` is not visible in the robot container). Takeoff → hover → `STEPS_PER_AXIS` steps in x, then z → land. Copied into the robot container by the orchestrator |
| `analyze_step.py` | echo-trace analyser — ledger #3's method (`ros2 topic echo` traces). **Info only**, never a gate |
| `hover_step_bag.py` | container-only rosbag → CSV dumper (`drone_1_{odom,cmd,state}.csv`); needs `rosbag2_py`, so it runs inside the robot container |
| `hover_step_analysis.py` | host analysis, pure Python (numpy): commanded-axis detector, goal-referenced settle (±0.1 / 0.05 / 0.02 m), overshoot, band re-entries, velocity tracking, every duration in **wall and vehicle time** |
| `hover_step_timescale.py` | prints PX4 arm/disarm times from a ulog (`pyulog`, runs in the isaac-sim container) — the vehicle-time scale for the report |
| `hover_step_report.py` | writes `docs/record/<run>_record.md`; exit **0 PASS / 2 INCOMPLETE / 1 FAIL**; appends every verdict to `<run>/verdicts.log`; info rows never PASS a gate |
| `hover_step_plot.py` | `step_response.png` (one panel per step, goal line, vehicle-time scale in the axis label) |
| `tests/` | host unit tests for the five hover-step tools (fixtures = ledger #17 artefacts) |

## Prerequisites

- Containers up: `cd AirStack && ./airstack.sh up` (the orchestrator's `up` phase does this).
- **Every container command runs through `bash -ic`** (`docker exec <container> bash -ic '…'`) — the interactive
  profile sets `ROS_DOMAIN_ID=1` and sources the workspace. The profile's noise lines are filtered.
- `pyulog` in the isaac-sim container's system `python3` (`docker exec isaac-sim python3 -c 'import pyulog'`).
- Host `python3` with **numpy + matplotlib** (analysis + plot run on the laptop, no ROS needed).
- `localisation/scripts/sim_resources_watch.sh` (resource + WiFi watch, started by the `watch` phase).
- A free GPU (Isaac Sim headless) and the sim stack only — **no real-drone bridge on the laptop** (iron rule 9:
  sim-only; the real drone is validated by its own ledger rows, never by these tools).

## Run it

```bash
cd ~/AirStack-starling-max2
tools/sim_hover_step_run.sh all sim_hover_step_run2     # the twelve phases; stops at the first FAIL, containers left up
tools/sim_hover_step_run.sh status sim_hover_step_run2  # what is up, last verdict, commit that ran
```

The record lands at `docs/record/sim_hover_step_run2_record.md` (its verdict line is the result). A single phase
can be re-run by name (`… down sim_hover_step_run2`); re-runs are marked in `run.log` / `commands.sh`.

## Where things go

| Where | What |
|---|---|
| `docs/record/<run>/` (tracked, small text) | `run.log`, `commands.sh` (every command used), `run_meta.txt` (commit that ran), `isaac_evidence.txt`, `params_ulog.txt`, `px4_arm_times.txt`, `drone_1_{odom,cmd,state}.csv`, `bag_analysis.json`, `step_response.png`, `verdicts.log`, `caveats.txt`, container logs |
| `~/flight_logs/sim/<run>/` (never the repo) | the rosbag `hover_step_<stamp>/` and the three ulogs `drone_<n>_sysid<s>_<basename>.ulg` (MAV_SYS_ID 2/3/4 = drone_1/2/3) |
| `docs/record/<run>_record.md` | the record written by `hover_step_report.py` |

Bags are written root-owned to `AirStack/robot/ros_ws/bags/` inside the robot container, copied to the heavy
dir, dumped to CSV, and only then removed from the container.

## Time scale

Sim real-time factor: see [ISAAC_REALTIME_NOTE.md](ISAAC_REALTIME_NOTE.md) — the sim ran ≈1.32–1.34× wall clock in #17 (1 Hz MAVROS state limits the resolution); the tools measure the scale per run from drone_1's PX4 ulog.

## Tests

```bash
cd ~/AirStack-starling-max2 && python3 -m unittest discover -s tools/tests -v   # 35 tests, 1 skipped (shellcheck not installed)
```

No pytest, no ROS on the host: the tests add `tools/` to `sys.path` themselves. Fixtures in `tools/tests/fixtures/run1/`
are copies of the ledger #17 artefacts.

## Gotchas

- PX4 ulog temp dirs (`/tmp/tmp*/log/`) vanish when Isaac exits — the orchestrator copies them in `collect` and again
  in `down`, before Isaac is stopped. All three ulogs share a basename: copy per sysid (`drone_<n>_sysid<s>_…`).
- `ros2 topic echo --field` prints `False` / `True` (Python booleans), not `false` / `true`.
- `/clock` is not visible in the robot container — never wait on it there.
- Isaac's exit orphans the PX4 SITL processes (`pkill -9 -x px4`, done by `down`).
- The Isaac launcher's prints (`Starling2MaxConfig`) are lost without `PYTHONUNBUFFERED=1` — the orchestrator sets it;
  a `starling_cfg=0` in `isaac_evidence.txt` makes the run INCOMPLETE, never an indirect PASS.
- Timings: the laptop logs in SGT, the containers in UTC; the report labels every time it prints.
