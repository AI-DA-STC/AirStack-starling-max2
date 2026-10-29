# Live test driver — design (panel decision, 2026-10-29)

**Why.** The owner: "for future tests I want the scripts to not run in headless, with the visualiser live and the graphs plotted live for my view, all in the same Foxglove. Start from NEAR-787. Mark this down in a standard for coding scripts that run milestones and tests." Today's only driver (`tools/sim_hover_step_run.sh`) runs headless by default, analyses offline from the bag, and plots afterwards; the crossing test exists only as CMU's 45 s script that samples the 5 Hz status string (two drones closing at 8 m/s move 1.6 m between samples, so a 1.10 m gate cannot be measured from it).

**Decided by** a four-hat panel (test-automation, ROS/Foxglove visualisation, flight-test, student reader; agents saved under `~/.claude/agents/panel-*`), two rounds, positions and votes in the session scratchpad `panel2/`. The rules are in [docs/TEST_STANDARD.md](../../TEST_STANDARD.md); this document records the decisions and the first implementation.

## Goals
- One command runs a test with the Isaac window open; the owner watches the flight and the metrics live in the same Foxglove Studio that shows the SVG Basestation panel, records with OBS, and gets a ledger-grade record from the same run.
- The numbers on screen are the numbers gated.
- Adding a test is five files in one directory; no new driver.
- NEAR-787 (three-drone crossing with collision avoidance) is the first test on this standard.

## Non-goals / anti-goals
- No edits under `AirStack/` (no DDS allowlist, no launch-file changes; the robot container's own Foxglove bridge already sees every topic).
- The hover-step driver is not rewritten now; it migrates after the crossing test proves the library (vote 4–0).
- No Foxglove user scripts for metrics (tied to one Studio's layout, cannot write the CSV).
- Gates are never moved to fit a result; a failed gate is the finding.

## Decisions (with votes)
1. **Metrics node (4–0).** `tools/live/metrics_node.py` (ROS 2, Python, docker-cp'd into the robot container like the flight script) subscribes to `/drone_N/odometry_conversion/odometry` (40 Hz) and `/svg/commander_status`, computes the test's series via `tools/live/metrics_core.py`, publishes one `std_msgs/Float64` per series under `/svg/test/<series>` at 10 Hz plus constant reference topics (`/svg/test/ref_2r`, `/svg/test/ref_speed_cap`) and `/svg/test/phase` (0 idle, 1 takeoff, 2 test, 3 land), and appends every published sample to `metrics.csv`.
2. **Authority (4–0).** `gates.py` reads `metrics.csv` (what the owner watched). The report recomputes the headline series from the bag with the same `metrics_core`; minimum distance must agree within 0.02 m and every other column by max difference (tolerance stated per column in `metrics.py`); a mismatch makes the gate UNVERIFIED and the run cannot PASS. The bag and ulogs stay the backup evidence.
3. **Layout (3–1).** `tools/live/make_layout.py` generates `tools/sim_tests/<name>/layout.json` from CMU's read-only `svg_basestation.json` (its three panels kept) plus the Plot panels described in `plots.json`. The generated file is committed; `tools/sim.sh check` fails when it is stale against `plots.json` or the base. The driver prints the layout path; the user imports it once in Studio (in-container or laptop; both connect to `ws://localhost:8765`).
4. **Per-test contract (4–0).** `tools/sim_tests/<name>/`: `test.env`, `fly.sh`, `metrics.py`, `gates.py`, `plots.json` (+ generated `layout.json`). `tools/sim_tests/_template/` is the starting copy. The unittest directory `tools/tests/` is untouched.
5. **Front door (4–0).** `tools/sim.sh up|down|status|tabs|test <name> [--headless] [--no-pause] --ledger N --issue NEAR-nnn <run>|figures|check`. Shared phases in `tools/lib/stack.sh` (precheck, up, watch, isaac, interfaces, commander, params, collect, down), generic `tools/lib/report.py` that renders any test's gate rows into the record shape DOCS_STANDARD requires. Flags, not environment variables; no-argument invocation prints usage.
6. **Pauses (4–0).** Window mode waits for Enter before the flight and after landing (plots still live); `--no-pause` skips both; headless never pauses.
7. **Abort (4–0).** Ctrl-C trap: `land`, wait for `armed: false` ×3 (bounded), collect bag + ulogs, write the record with verdict ABORTED (exit 3). Landing failure: print DRONES STILL ARMED, keep the stack up.
8. **NEAR-787 gates.** min pairwise distance ≥ 1.10 m (2r, binary — **ruling** on the 2–2 tie: no MARGINAL band, because a band lets a run look half-passed; the record prints ledger #4's 1.02 m as an info row and states the margin to the gate); zero emergency samples; zero fence breaches; CBF active on ≥ 1 drone at least once; each drone reaches its far goal (within 0.3 m) before `land`; peak speed ≤ 4.2 m/s (cap 4.0 + 5 %, 3–1, catches a mis-loaded config); all three `landed, disarmed` and MAVROS `armed: false` ×3; live/offline agreement (decision 2).
9. **NEAR-787 live view.** Plot 1: the three pairwise distances with the 1.10 m line and the 0.55 m radius line. Plot 2: speed per drone with the 4.0 m/s line. Plot 3: CBF-active per drone (0/1) and emergency. Plot 4: fence margin. Phase topic shades takeoff / crossing / land. Terminal: one line per second (phase, min distance, CBF state), then the verdict banner.
10. **NEAR-787 record.** bag, 3 ulogs, `metrics.csv`, `fig-1` distances over time (generated by `tools/sim.sh figures` from `metrics_core`), the pass/fail table, the OBS file name line, the drafted LEDGER row with `NEAR-787`, the scope line (PX4's own sim estimate, flat world, camera/cuVSLAM not in the loop), and the comparison to ledger #4.
11. **Contract check in pre-commit (4–0).** `tools/sim.sh check` = five files present, `gates.py` imports `metrics_core`, `layout.json` fresh, `metrics_core` unit tests pass. The existing hook calls it.

## Constraints carried from the repo
Sim-only labelling (iron rule 9); DOCS_STANDARD for every page the run writes; never push; the owner's two untracked root files are not ours; `cbf_sim.yaml` speeds are sim-only.

## Left to the builder
Exact Float64 topic names per series (documented in `plots.json`); the Plot panel JSON fields; the phase-marker rendering; how `stack.sh` reuses the hover-step driver's proven phase code (copy, then the hover driver migrates in a later plan); the CSV schema (`t_s` first, one column per series, same names as topics); the far-goal threshold source (the scenario's antipodal offsets in `cbf_sim.yaml`).

## Done when
`tools/sim.sh test crossing --ledger 20 --issue NEAR-787 sim_crossing_run1` runs with the Isaac window open, the four plots move in Studio during the flight, the terminal prints the per-second line and a verdict, the record and LEDGER row draft exist with every gate row filled from `metrics.csv`, the bag cross-check row is PASS, Ctrl-C mid-flight produces an ABORTED record with all three drones disarmed, `tools/sim.sh check` passes in pre-commit, docs check 0 FAIL, unit tests green, and the HTX-R1 NEAR-787 row shows the result with the figure and the video file name.
