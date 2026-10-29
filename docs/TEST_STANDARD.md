KNOW · SIM + REAL — how a script that runs a milestone test is written, so the owner can watch it live, record it, and still get a ledger-grade record. Adopted 2026-10-29 by a four-hat panel ([design](superpowers/specs/2026-10-29-live-test-driver-design.md)); first implementation = the NEAR-787 crossing driver.

# Test-script standard

A test is one command, watched live, recorded, and gated by the same numbers the owner watched.

## 1. Rules

1. **One front door.** Every test runs as `tools/sim.sh test <name> [--headless] [--no-pause] --ledger N --issue NEAR-nnn <run>`. No test has its own entry point. `tools/sim.sh` with no arguments prints usage and does nothing.
2. **Window on by default.** The Isaac Sim window opens unless `--headless` is given. Headless is for unattended re-runs only.
3. **Live in one Foxglove.** A metrics node of ours (`tools/live/metrics_node.py`) publishes every quantity the test gates on as a numeric topic under `/svg/test/` at about 10 Hz, computed from the 40 Hz odometry, never from the 5 Hz status string. Reference lines (a radius, a cap) are published as constant topics. Foxglove's plot panels graph them next to the SVG Basestation panels, in the same Studio, from one layout the driver prints the path of.
4. **What you watched is what is gated.** The metrics node writes `metrics.csv` from the values it publishes; `gates.py` reads that file. The report recomputes the headline number from the rosbag and the two must agree (minimum distance within 0.02 m, other columns by max difference); otherwise the gate is UNVERIFIED and the run cannot PASS.
5. **One shared metrics module.** Live node, offline recompute and figures import the same `tools/live/metrics_core.py`. No formula exists twice.
6. **A test is five files** in `tools/sim_tests/<name>/`: `test.env` (title, purpose, sim-only line, config), `fly.sh` (drives the commander: services and goal topics), `metrics.py` (the series list, pure functions over odometry and status), `gates.py` (returns gate rows: name, criterion, measured, verdict), `plots.json` (what to plot, which reference lines). `layout.json` is generated from `plots.json` and CMU's read-only base layout by `tools/live/make_layout.py`, committed, and checked for staleness by `tools/sim.sh check`.
7. **Pauses for the human.** In window mode the driver waits for Enter before the flight (start OBS) and again after landing with the plots still live. `--no-pause` skips both.
8. **Ctrl-C is a landing.** The driver traps it, lands every drone, waits for disarm, keeps the bag and ulogs, and writes the record as ABORTED. ABORTED never becomes PASS. If landing fails it prints DRONES STILL ARMED and does not tear the stack down.
9. **Terminal tells the story.** One line per second during the flight (phase, the headline metric, CBF state), then a verdict banner. A `/svg/test/phase` topic marks takeoff, test, land for the plots.
10. **The record is complete or it is not a result.** Every run writes `docs/record/<run>_record.md` (purpose, scope line, pass/fail table, figure, verdict history), `docs/record/<run>/` (metrics.csv, logs), and `~/flight_logs/sim/<run>/` (bag + ulogs). The record names the OBS file. Missing evidence = INCOMPLETE. The drafted LEDGER row carries the issue id.
11. **Gates are written before the run** in `gates.py`, with the justification and the last baseline, and are never moved to fit a result. A failed gate is the finding.
12. **Nothing under `AirStack/`.** Our code lives in `tools/`; flight logic needed from CMU's scripts is copied into `fly.sh` unchanged in behaviour.
13. **Contract in pre-commit.** `tools/sim.sh check` verifies every test directory has the five files, `gates.py` imports `metrics_core`, `layout.json` matches `plots.json`, and the unit tests for `metrics_core` pass.

## 1b. Where things run

Laptop: `tools/sim.sh` and everything under `tools/`. Robot container: CMU's commander, MAVROS, the Foxglove bridge and the in-container Studio, plus our metrics node and flight script copied in for the run. Isaac container: the sim and PX4. One install: `AirStack/airstack.sh setup` (CMU's) then `tools/sim.sh setup`; `tools/sim.sh doctor` says what is missing. The Foxglove you watch is the in-container Studio (`use_foxglove_studio:=true`), with the test layout installed by setup.

## 2. Adding a test

Five commands, then record the result:

```bash
cp -r tools/sim_tests/_template tools/sim_tests/<name>
# edit the five files: test.env, fly.sh, metrics.py, gates.py, plots.json
python3 tools/live/make_layout.py tools/sim_tests/<name>
tools/sim.sh check
tools/sim.sh test <name> --ledger N --issue NEAR-nnn <run>
```

Follow [DOCS_STANDARD.md](DOCS_STANDARD.md) §7 to record it. The project page's results block for the issue opens with the scope line (position source, world, what is not in the loop).

## 3. Migration order

1. NEAR-787 three-drone crossing: first test on this standard (proves the library).
2. Hover + 1 m steps (`tools/sim_hover_step_run.sh`): folded in second, its report becoming a `gates.py`; the three existing records stay valid.
3. Later tests (gain tuning, teleop in the site, cuVSLAM scoring) are added as directories, not drivers.
