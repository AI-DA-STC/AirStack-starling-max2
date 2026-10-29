# tools/ — the sim front door and the live tests

> **DO · SIM.** Everything here runs on the laptop or inside the sim containers. It is sim-only: nothing in this
> folder touches the real drone, and nothing measured here is ported to it (CLAUDE.md iron rule 9).

## Install in three commands

```bash
cd ~/AirStack-starling-max2
AirStack/airstack.sh setup && AirStack/airstack.sh up   # CMU's install + containers (two steps)
tools/sim.sh setup                                      # our checks + an optional Foxglove layout file
```

First run, once the install is done:

```bash
tools/sim.sh test crossing --ledger <next #> --issue NEAR-787 <run>   # <next #> = last row of LEDGER table 1, plus one; <run> = a NEW name
```

`tools/sim.sh doctor` says what is missing. `tools/sim.sh` with no argument prints the usage and does nothing.
The contract behind every test is [TEST_STANDARD.md](../docs/TEST_STANDARD.md).
The old hover + step driver still works and moves under the front door later.

## What is here

| Path | What it does |
|---|---|
| `sim.sh` | the front door: `setup · doctor · up · down · status · tabs · test <name> … · figures · check` |
| `tools/lib/stack.sh` | stack start/stop and cleanup helpers — sourced by `sim.sh` and by the hover driver |
| `tools/lib/report.py` | writes `docs/record/<run>_record.md` and the drafted LEDGER row from a test's `gates.py`; exit 0 PASS / 1 FAIL / 2 INCOMPLETE / 3 ABORTED |
| `tools/lib/contract_check.py` | what `sim.sh check` runs on each test folder |
| `tools/live/metrics_core.py` | the one metrics formulas module: live node, bag recompute and figures all import it |
| `tools/live/` (others) | `metrics_node.py` (publishes `/svg/test/*`, writes `metrics.csv`), `bag_recompute.py`, `make_layout.py`, `plot_metrics.py` (record figure), `live_plot.py` (live plot window) |
| `sim_tests/<name>/` | one test = five files: `test.env`, `fly.sh`, `metrics.py`, `gates.py`, `plots.json` (+ generated `layout.json`) |
| `sim_tests/crossing/` | NEAR-787, the three-drone crossing: the worked example |
| `sim_tests/_template/` | the copy-me folder |
| `sim_terminals.sh` / `sim_tab.sh` | the four-tab sim session (Isaac Sim · Interfaces · Commander · Cockpit) — [RUNBOOK §A](../docs/RUNBOOK.md) |
| `sim_hover_step_run.sh` and the `hover_step_*` / `analyze_step.py` tools | the hover + 1 m step driver, unchanged ([below](#hover--step-legacy-driver)) |
| `docs_check/` | the documentation checker — `tools/docs_check/check_docs.sh` (0 FAIL required before a docs commit) |
| `git-hooks/` | the pre-commit guard: docs check, unit tests, `tools/sim.sh check` |
| `make_figures.sh` | regenerates the committed figures in `docs/record/figures/`; run by hand when a figure should change |
| `tests/` | host unit tests |

## Run a test

```bash
tools/sim.sh test crossing [--headless] [--no-pause] --ledger 20 --issue NEAR-787 sim_crossing_run1
```

`--ledger` is the number of the new LEDGER row, `--issue` its Linear id; both are required, and the run name must be new.

- **Window mode (default)** opens the Isaac window, the in-container Foxglove Studio with the SVG Basestation panel,
  and a live plot window with the test's distance plot. Drag the plot window where OBS can see it, then click back into the terminal.
- **Pause 1**, before the flight: start OBS (the screen recorder), then press Enter.
  **Pause 2**, after landing with the plots still live: type the video's path, repo-relative, e.g. `videos/<file>.mkv` (Enter skips); it goes into the record.
  `--no-pause` skips both.
- **Where the video ends up:** OBS saves where its own settings say (Settings → Output → Recording Path, by default `~/Videos`).
  Move the file into `videos/` under the repo and type that repo-relative path (`videos/<file>.mkv`, not `~/Videos/…`) at Pause 2, so the record links it.
- **`--headless`** (no Isaac window) has no Studio and no pauses; use it when there is no `DISPLAY` or for unattended re-runs.
- **Ctrl-C** lands every drone, waits for disarm, keeps the bag and ulogs, and writes the record as ABORTED.
  It never becomes PASS. If landing fails the driver still writes the ABORTED record, prints DRONES STILL ARMED and leaves the stack up.
- **A late video name:** edit `docs/record/<run>/video.txt`, then re-render with
  `python3 tools/lib/report.py tools/sim_tests/crossing docs/record/<run> --ledger 20 --issue NEAR-787`.
  Run-specific caveats live in `docs/record/<run>/caveats.txt` (one per line) and survive a re-render; edit that file, never the record.
- Then record the result: [DOCS_STANDARD §7](../docs/DOCS_STANDARD.md).
  In Linear: comment the run's `VERDICT:` line, `LEDGER #<n>` and the record's GitHub path (`docs/record/<run>_record.md`) on the NEAR-nnn issue, then tick it if it passed.

## Adding a test

1. `cp -r tools/sim_tests/_template tools/sim_tests/<name>`
2. Fill the five files (the `CHANGE_ME` markers in `test.env` first).
3. `python3 tools/live/make_layout.py tools/sim_tests/<name>` writes `layout.json`; commit it.
4. `tools/sim.sh check` must print `OK <name>`.
5. Run it once in window mode (above).

## Where things go

| Where | What |
|---|---|
| `docs/record/<run>/` (tracked, small text) | `metrics.csv`, `run.log`, `commands.sh`, `video.txt`, `verdicts.log`, `fig-1.png`, container logs; the hover test adds its CSVs and `step_response.png` |
| `docs/record/<run>_record.md` | the record: purpose, scope line, gate table, figure, verdict |
| `~/flight_logs/sim/<run>/` (never the repo) | the rosbag and the three ulogs `drone_<n>_sysid<s>_<basename>.ulg` (sysid = the PX4 `MAV_SYS_ID`; 2/3/4 = drone_1/2/3) |
| `docs/record/figures/` (tracked) | figures the project pages embed; fixed filenames, made only by `tools/make_figures.sh` |

## Hover + step (legacy driver)

`sim_hover_step_run.sh` is the hover + 1 m step acceptance (NEAR-786).
It runs on its own entry point until it migrates under `sim.sh`.

- Phases, in `all` order: `precheck up watch isaac interfaces commander params fly collect down analyse report`; extra: `status`, `ifgates`.
- Env: `STEPS_PER_AXIS` (default 3), `LEDGER`, `ISSUE` (unset = `?`), `ISAAC_GUI=1`, `PAUSE_BEFORE_FLY=1`, `ISAAC_KIT_ARGS`.
- Tools: `sim_hover_step_test.sh` (flight script), `hover_step_bag.py` (container-only bag dump), `hover_step_analysis.py`,
  `hover_step_timescale.py`, `hover_step_report.py` (exit 0 PASS / 2 INCOMPLETE / 1 FAIL), `hover_step_plot.py`,
  `analyze_step.py` (info only, never a gate).

### Prerequisites

- Containers up: `cd AirStack && ./airstack.sh up` (the orchestrator's `up` phase does this).
- **Every container command runs through `bash -ic`** (`docker exec <container> bash -ic '…'`) — the interactive
  profile sets `ROS_DOMAIN_ID=1` and sources the workspace. The profile's noise lines are filtered.
- `pyulog` in the isaac-sim container's system `python3` (`docker exec isaac-sim python3 -c 'import pyulog'`).
- Host `python3` with **numpy + matplotlib** (analysis + plot run on the laptop, no ROS needed).
- `localisation/scripts/sim_resources_watch.sh` (resource + WiFi watch, started by the `watch` phase).
- A free GPU (Isaac Sim headless) and the sim stack only — **no real-drone bridge on the laptop** (iron rule 9:
  sim-only; the real drone is validated by its own ledger rows, never by these tools).

### Run it

```bash
cd ~/AirStack-starling-max2
LEDGER=19 ISSUE=NEAR-786 tools/sim_hover_step_run.sh all sim_hover_step_run3   # legacy hover driver, migrates to the front door later; NEW run name every time; LEDGER = the ledger row this run will get
tools/sim_hover_step_run.sh status sim_hover_step_run3  # what is up, last verdict, commit that ran
```

The record lands at `docs/record/sim_hover_step_run3_record.md` (its verdict line is the result). A single phase
can be re-run by name (`… down sim_hover_step_run3`); re-runs are marked in `run.log` / `commands.sh`.

## Time scale

Sim real-time factor: see [ISAAC_REALTIME_NOTE.md](ISAAC_REALTIME_NOTE.md) — the sim ran ≈1.32–1.34× wall clock in #17 (1 Hz MAVROS state limits the resolution); the tools measure the scale per run from drone_1's PX4 ulog.

## Thresholds

The gates `hover_step_report.py` applies to a sim hover + 1 m step run (S5 / NEAR-786), set 2026-10-19 and unchanged since:

| Gate | Value | Why this value |
|---|---|---|
| hover thrust setpoint (MAVROS `target_attitude`) | 0.12–0.20 | brackets the real drone's `MPC_THR_HOVER` 0.165; Iris reads ≈ 0.58 |
| step overshoot | < 0.15 m | brackets the Iris regression reading of ledger #2 (0.14 m) |
| step settle to ±0.1 m of the goal | < 3.0 s, PX4 vehicle time | brackets the Iris reading (3.6 s); not derived from a flight requirement |
| ringing | 0 band re-entries | a clean first-order approach |
| landing | `landed, disarmed` ×3 (ACK log) and MAVROS `armed: false` ×3 | iron rules 2 and 5: the ACK log is not an arming display |

Sim-only: these characterise the sim loop (TwistStamped → MAVROS → PX4 SITL), never the drone.

Results: [docs/record/LEDGER.md](../docs/record/LEDGER.md), [docs/projects/HTX-R1.md](../docs/projects/HTX-R1.md) S5.

## Tests

```bash
cd ~/AirStack-starling-max2 && python3 -m unittest discover -s tools/tests   # 230 tests, 1 skipped (shellcheck not installed)
```

No pytest, no ROS on the host: the tests add `tools/`, `tools/live` and `tools/lib` to `sys.path` themselves. No test starts a sim run.

## Gotchas

- PX4 ulog temp dirs (`/tmp/tmp*/log/`) vanish when Isaac exits — the orchestrator copies them in `collect` and again
  in `down`, before Isaac is stopped. All three ulogs share a basename: copy per sysid (`drone_<n>_sysid<s>_…`).
- `ros2 topic echo --field` prints `False` / `True` (Python booleans), not `false` / `true`.
- `/clock` is not visible in the robot container — never wait on it there.
- Isaac's exit orphans the PX4 SITL processes (`pkill -9 -x px4`, done by `down`).
- The Isaac launcher's prints (`Starling2MaxConfig`) are lost without `PYTHONUNBUFFERED=1` — the orchestrator sets it;
  a `starling_cfg=0` in `isaac_evidence.txt` makes the run INCOMPLETE, never an indirect PASS.
- Timings: the laptop logs in SGT, the containers in UTC; the report labels every time it prints.
- Plots in Foxglove too (optional): `setup` copies the layout to `/root/svg_test_<name>_layout.json` in the robot container.
  Import it once from Studio's layout menu (Import from file); a signed-in Studio keeps it.
- No `DISPLAY` (ssh, remote session): use `--headless`; window mode needs the laptop's screen.
