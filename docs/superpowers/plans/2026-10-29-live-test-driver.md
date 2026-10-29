# Live test driver (`tools/sim.sh`, NEAR-787 crossing first) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One command (`tools/sim.sh test crossing --ledger N --issue NEAR-787 <run>`) runs the three-drone crossing with the Isaac window open, plots the gated numbers live in the in-container Foxglove Studio next to the SVG Basestation panels, prints a per-second line and a verdict, and writes a ledger-grade record whose gates read the same `metrics.csv` the owner watched, cross-checked against the rosbag.

**Architecture:** The 12-phase hover-step driver's shared phases are extracted into `tools/lib/stack.sh` (the hover driver sources it, unchanged behaviour). A new front door `tools/sim.sh` sources the same library, copies our rclpy metrics node plus the test's five files into the robot container, runs the flight, and hands the artefacts to a generic renderer `tools/lib/report.py` that calls the test's `gates.py`. All formulas live once in `tools/live/metrics_core.py` (pure Python; a `Tracker` class drives both the live node and the bag recompute). `tools/live/make_layout.py` turns `plots.json` + CMU's read-only base layout into a committed `layout.json`.

**Tech Stack:** bash (host), Python 3 + numpy + matplotlib on the host (`python3 -m unittest`, no pytest, no rclpy), Python 3 + rclpy + rosbag2_py + numpy inside `airstack-robot-desktop-1` (every exec via `docker exec … bash -ic`), pyulog in `isaac-sim`, Foxglove Studio desktop inside the robot container, docker.

**Spec:** `docs/superpowers/specs/2026-10-29-live-test-driver-design.md` (read all of it, including "Builder-check answers" and "Architecture") and the standard it implements, `docs/TEST_STANDARD.md` (its 13 rules are requirements). Record shape rules: `docs/DOCS_STANDARD.md` §4 and §7.

## Global Constraints

- Work and commit in the live clone `/home/jeremychia/AirStack-starling-max2` on `main`. **Never push.** Never edit under `AirStack/` (CMU's tree; flight logic is copied into `fly.sh`). The owner's two untracked root files (`QGroundControl-x86_64.AppImage`, `starling max2 voxl setup.txt`) are not ours; the untracked `docs/record/sim_hover_step_run4/` is the owner's run folder — leave all three alone.
- The existing hover-step driver keeps working at every commit: its 70 tests stay green and `tools/sim_hover_step_run.sh` with no args prints usage (exit 2).
- Docs check `tools/docs_check/check_docs.sh` prints `0 FAIL` at the end of every task that touches docs (`docs/`, `README.md`, `CLAUDE.md`, `tools/`).
- New unit tests live under `tools/tests/` and run with `python3 -m unittest discover -s tools/tests` (tests add `tools/` and `tools/live` and `tools/lib` to `sys.path` themselves). No test may start a real sim run; a no-argument `tools/sim.sh` prints usage and does nothing.
- Anything that needs `rclpy`/`rosbag2_py`/`pyulog` runs inside a container (docker exec/cp like today) and is never imported by host tests; host tests cover the pure parts (`metrics_core`, `make_layout`, `report`, `contract_check`, `plot_metrics`, `gates.py`).
- Sim-only labelling (CLAUDE.md iron rule 9) in every record, README line and ledger row this plan writes. DOCS_STANDARD for every page touched (scope line, caption ≤ 400 chars, numbered anchored figures, cell ≤ 120 chars, S5 section ≤ 40 lines, Result cell filled only from a record).
- Spec values (verbatim): odometry 40 Hz; publish 10 Hz; CSV at 40 Hz; min pairwise distance gate ≥ 1.10 m (2r, binary, no MARGINAL band; ledger #4's 1.02 m as an info row); emergency samples 0 at 5 Hz; fence-breach samples 0 at 5 Hz; CBF active on ≥ 1 drone at least once (`/svg/cbf_active`, 20 Hz); peak speed ≤ 4.2 m/s (cap 4.0 + 5 %); `landed, disarmed` ×3 and MAVROS `armed: false` ×3; live/offline agreement: minimum distance within 0.02 m, other columns per-column tolerance; mismatch → UNVERIFIED, run cannot PASS; offset sanity 0.05 m; abort bound 30 s, exit 3; window 45 s; phase 0 idle / 1 takeoff / 2 test / 3 land; reference topics `/svg/test/ref_2r`, `/svg/test/ref_speed_cap` (+ `ref_r` for the 0.55 m line); runs land in `docs/record/<run>/`, `docs/record/<run>_record.md`, `~/flight_logs/sim/<run>/`.
- Commit subjects follow the repo's `tools: …` / `docs: …` style; test-result commits follow DOCS_STANDARD §7.6 (`HTX-R1/S5 NEAR-787: …`).

## Rulings on spec gaps (decided here so every task agrees)

1. **Far-goal threshold.** `AntipodalScenario._ARRIVAL_RADIUS_M = 0.4` (`scenarios.py:364`): the commander declares arrival and re-targets at 0.4 m, so the spec's 0.3 m is unreachable by construction. Gate: each drone's closest approach to its antipode during phase 2 ≤ **0.40 m** (the commander's own arrival radius); the measured cell prints the closest approach, and the record states 0.3 m was the spec's draft value. Every drone has an antipode: takeoff targets are the Fibonacci-sphere points (radius 0.45·min(arena size) = 0.9 m around the arena centre (0, 0, 1.5)); nobody starts at the centre; antipode = 2·centre − position at the moment phase becomes 2. No "n/a" row.
2. **Phase source.** The metrics node derives the phase from `/svg/commander_status` (`drones[].state`, `mission_active`), not from `fly.sh`: all `IDLE` → 0; any `ARMING`/`ASCEND` while `mission_active` is false → 1; `mission_active` true → 2; any `LANDING` → 3; all `IDLE` again → 0.
3. **40 Hz trigger.** One CSV row per odometry message of the trigger drone (`TRIGGER = "drone_1"` in `metrics.py`), using the latest pose of the others; `t_s` = that message's `header.stamp` − `t0` (first trigger stamp the node saw, recorded as `t0_unix` in the CSV header). The bag recompute replays every message in bag order and emits a row on the same trigger with the same `t0`.
4. **Positions in the CSV.** The CSV has no raw positions, so the far-goal gate reads series `goal_dist_drone_N` (distance to the antipode, NaN before phase 2).
5. **Flag columns in the cross-check.** A 0/1 column's max difference is vacuous; `kind="flag"` series are compared by sample count: |Σ live − Σ bag| ≤ max(2, 1 % of paired rows).
6. **Running minimum** is over every row since node start (what the owner watched); the gate reads the same column.
7. **Stale odometry.** A drone whose last odometry is older than 0.5 s makes every series that uses it NaN for that row; a gate column with NaN in more than 1 % of phase-2 rows is UNVERIFIED.
8. **Layout store.** Found 2026-10-29 in the running robot container: `/root/.config/Foxglove/studio-datastores/layouts-local/` (empty) next to `layouts-remote-*/lay_*` files whose envelope is `{"id","name","permission":"CREATOR_WRITE","baseline":{"data":<layout>,"savedAt":<iso>}}`. Host side it is the bind mount `AirStack/robot/docker/Foxglove/` (gitignored `*`, root-owned): writing there through `docker cp` edits nothing tracked under `AirStack/`. `setup` writes `lay_svgtest_<name>` in that envelope and says that Studio shows it after a restart; if the directory is absent it prints the import path.
9. **Studio with the commander** only for `sim.sh test` in window mode (`USE_STUDIO=true` → `use_foxglove_studio:=true` on the commander launch); the hover driver never sets it.
10. **Flags.** `--ledger N` and `--issue NEAR-nnn` are required for `test` (rule 1 shows them without brackets).
11. **Per-second line** is printed by the metrics node to its log; the driver streams it with `tail -f` during the flight.
12. **Record figure** `docs/record/<run>/fig-1.png` is made by `tools/sim.sh figures` (plot 1 of `plots.json`); the project-page figure is a fixed-name copy made by `tools/make_figures.sh` (DOCS_STANDARD §7.4), `docs/record/figures/s5_crossing_distances.png`, numbered Figure 3 on HTX-R1.
13. **Abort exercise.** The Ctrl-C acceptance run (`sim_crossing_abort1`) is a driver test, not a flight result: its record is verified, then removed from `docs/record/` and `~/flight_logs/sim/`.
14. **Video name.** In window mode the post-landing pause asks for the OBS file name and writes `video.txt`; headless writes `video.txt` = `none (headless run)`.

## Review Focus

Inputs the spec implies but no spec sentence tests; each is pinned by a test in the named task.

1. **One drone's odometry stops mid-flight** (MAVROS respawn): the distance to it must become NaN, never a frozen value that looks safe — Task 3 `test_stale_drone_gives_nan_distance`; Task 7 `test_nan_fraction_makes_gate_unverified`.
2. **`aborted.txt` present with every gate PASS**: the verdict is ABORTED, exit 3 — Task 6 `test_aborted_marker_forces_aborted_verdict`.
3. **`--ledger x` or `--issue NEAR787`**: usage error, exit 2, no docker call — Task 2 `test_sim_sh_rejects_bad_flags`.
4. **`plots.json` names a series `metrics.py` does not define**: `make_layout` fails naming the plot and the series — Task 5 `test_make_layout_rejects_unknown_series`.
5. **Bag with fewer odometry rows than the live CSV** (DDS loss while recording): unpaired live rows are counted; > 5 % unpaired → UNVERIFIED, never a silent PASS — Task 3 `test_crosscheck_unpaired_rows_flagged`.

Dependency graph: **T1 → T2**; **T3 independent** (start in parallel with T1); **T4, T5, T6 after T3** (parallel); **T7 after T3, T5, T6**; **T8 after T2, T4, T7**; **T9 after T5, T7, T8**; **T10 after T9**; **T11 last**.

---

### Task 1: `tools/lib/stack.sh` extracted from the hover driver

**Files:**
- Create: `tools/lib/stack.sh`
- Modify: `tools/sim_hover_step_run.sh` (lines 20–37 variables, 39–75 helpers, 77–239 phases `precheck`…`params`, 253–271 `copy_ulogs`, 294–334 `down`, 371–380 `status`)
- Modify: `tools/tests/test_scripts_syntax.py` (needles now searched in driver + library)
- Test: `tools/tests/test_stack_sh.py`

**Interfaces:**
- Produces `tools/lib/stack.sh`, sourced after the caller sets `RUN OUT HEAVY S SCENARIO BAG_PREFIX CONFIG HEADLESS` (and optionally `USE_STUDIO` default `false`, `ISAAC_KIT_ARGS`, `ISAAC_LOG_HINT`). Sourcing with any required variable unset prints `stack.sh: <VAR> unset` to stderr and returns 2; sourcing runs nothing else. It defines `REPO` (= `tools/lib/../..`), `TOOLS`, `R=airstack-robot-desktop-1`, `I=isaac-sim`, `NOISE`, `BAGS`, `ISAAC_CMD`, `IF_CMD`, `CMD_CMD` (built as today from `$CONFIG scenario:=$SCENARIO record_bag:=true bag_prefix:=$BAG_PREFIX` plus ` use_foxglove_studio:=true` only when `USE_STUDIO=true`), `PARAM_KEYS`; helpers `say note nx fail caveat rx ix alive wait_for json1 count_log mavros_connected phase_begin isaac_evidence`; phases `precheck up watch isaac interfaces ifgates odom_gates commander params copy_ulogs down status`; new helpers `ulog_header_params <ulog>` (writes `$OUT/params_ulog.txt`, the loop now in `collect`), `px4_arm_times_of <ulog> <sid> <who>` (writes `$OUT/px4_arm_times.txt`, the block now in `collect`), `land_all_and_wait <bound_s>` (calls `/swarm_commander/land`, polls MAVROS `armed` for drones 1–3 every 3 s, returns 0 when all `false`, 1 at the bound), `arm_abort_trap` (installs `trap abort_trap INT`), `abort_trap` (say `ABORT: Ctrl-C — landing`; `land_all_and_wait 30`; run `$ABORT_HOOK` if declared; write `aborted=<date -Is>` to `$OUT/aborted.txt`; on success `copy_ulogs; down; run $REPORT_HOOK if declared; exit 3`; on failure print `DRONES STILL ARMED — stack left up; land by hand: docker exec $R bash -ic 'ros2 service call /swarm_commander/land std_srvs/srv/Trigger', then tools/sim.sh down`, `exit 3`).
- `commander` checks `SwarmCommander up | scenario=$SCENARIO` in the log and `j["scenario"] == "$SCENARIO"` in `status_pre.json`. `down` globs `$BAGS/${BAG_PREFIX}_*`, greps `stopped: .*${BAG_PREFIX}_`, and after copying the bag calls `bag_dump_hook <bag_dir>` when that function is declared (hook returns non-zero → bag left in the container, as today); removes the bag only when the hook succeeded or no hook exists.
- `precheck` adds a WARN line (not a fail) `WARN: Isaac start/stop can crash the WiFi firmware (iwlwifi) — use Ethernet or sit at the laptop` and, when `HEADLESS=false` and `DISPLAY` is empty, fails with `no DISPLAY for the Isaac window — use --headless`.
- The hover driver keeps `PHASE`/`RUN` parsing, sets `S=/tmp/hover_step SCENARIO=goal BAG_PREFIX=hover_step CONFIG=cbf_sim.yaml HEADLESS` (from `ISAAC_GUI`), sources the library, defines `bag_dump_hook` (the `hover_step_bag.py` dump + three CSV copies, caveats as today), and keeps `fly collect analyse report`, the `ALL` loop and the usage text.

- [ ] **Step 1: Record the base commit and write the failing tests**

Run: `git -C /home/jeremychia/AirStack-starling-max2 rev-parse HEAD > /tmp/claude-1000/-home-jeremychia/37cad1a9-5a36-4858-918e-0b06a95a9d2d/scratchpad/base_commit`

```python
# tools/tests/test_stack_sh.py
import pathlib, subprocess, unittest
TOOLS = pathlib.Path(__file__).resolve().parents[1]
LIB = TOOLS / "lib" / "stack.sh"
ENV = "RUN=x OUT=/tmp/o HEAVY=/tmp/h S=/tmp/s SCENARIO=goal BAG_PREFIX=hover_step CONFIG=cbf_sim.yaml HEADLESS=true"

class StackSh(unittest.TestCase):
    def test_parses(self):
        self.assertEqual(subprocess.run(["bash", "-n", str(LIB)]).returncode, 0)

    def test_source_without_vars_returns_2(self):
        r = subprocess.run(["bash", "-c", f"source {LIB}"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2); self.assertIn("unset", r.stderr)

    def test_source_defines_phases_and_runs_nothing(self):
        r = subprocess.run(["bash", "-c", f"{ENV}; source {LIB}; declare -F | sed 's/declare -f //'"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr); self.assertEqual(r.stderr, "")
        for fn in ("precheck", "up", "watch", "isaac", "interfaces", "ifgates", "odom_gates", "commander", "params", "copy_ulogs",
                   "down", "status", "ulog_header_params", "px4_arm_times_of", "land_all_and_wait", "arm_abort_trap", "abort_trap"):
            self.assertIn(fn, r.stdout.split(), fn)

    def test_studio_arg_only_when_asked(self):
        for use, want in (("false", False), ("true", True)):
            r = subprocess.run(["bash", "-c", f"{ENV} USE_STUDIO={use}; source {LIB}; echo \"$CMD_CMD\""], capture_output=True, text=True)
            self.assertEqual("use_foxglove_studio:=true" in r.stdout, want, r.stdout)
            self.assertIn("scenario:=goal record_bag:=true bag_prefix:=hover_step", r.stdout)
```

And in `tools/tests/test_scripts_syntax.py::test_wrapper_parses_and_usage` change `src = p.read_text()` to `src = p.read_text() + (TOOLS / "lib" / "stack.sh").read_text()` (the needle list is unchanged; `sed -i` and `isaac-sim/tools` must be absent from both), and add `str(TOOLS / "lib" / "stack.sh")` to the shellcheck list.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/jeremychia/AirStack-starling-max2 && python3 -m unittest tools.tests.test_stack_sh -v`
Expected: 4 failures/errors (`stack.sh` missing).

- [ ] **Step 3: Create `tools/lib/stack.sh` by moving the blocks named in Files, parameterised as the Interfaces block says; rewrite `tools/sim_hover_step_run.sh` to set its variables, source the library, define `bag_dump_hook`, and call `ulog_header_params`/`px4_arm_times_of` from `collect`**

Move, do not retype: `sed -n` the line ranges out of the driver into the library, then edit only the `goal`/`hover_step` literals, the bag-dump block (into the hook) and the two `collect` blocks (into the helpers). Keep `set -o pipefail` in both files; no `set -e`.

- [ ] **Step 4: Verify the moved function bodies differ only where parameterised**

Run:
```bash
cd /home/jeremychia/AirStack-starling-max2 && BASE=$(cat /tmp/claude-1000/-home-jeremychia/37cad1a9-5a36-4858-918e-0b06a95a9d2d/scratchpad/base_commit)
git show "$BASE":tools/sim_hover_step_run.sh | sed -n '/^# -* helpers/,/^fly() {/p' | sed '$d' > /tmp/claude-1000/-home-jeremychia/37cad1a9-5a36-4858-918e-0b06a95a9d2d/scratchpad/old_fns.sh
F="precheck up watch isaac interfaces ifgates odom_gates commander params copy_ulogs down status"
diff <(bash -c "RUN=x OUT=/tmp/o HEAVY=/tmp/h S=/tmp/s REPO=/r TOOLS=/r/tools; source /tmp/claude-1000/-home-jeremychia/37cad1a9-5a36-4858-918e-0b06a95a9d2d/scratchpad/old_fns.sh; declare -f $F") \
     <(bash -c "RUN=x OUT=/tmp/o HEAVY=/tmp/h S=/tmp/s SCENARIO=goal BAG_PREFIX=hover_step CONFIG=cbf_sim.yaml HEADLESS=true; source tools/lib/stack.sh; declare -f $F")
```
Expected: the only differing lines contain `$SCENARIO`, `$BAG_PREFIX`, `bag_dump_hook`, or the two new `precheck` lines (WiFi WARN, DISPLAY check). Anything else is a regression — fix it.

- [ ] **Step 5: Run every test and the usage check**

Run: `cd /home/jeremychia/AirStack-starling-max2 && python3 -m unittest discover -s tools/tests 2>&1 | tail -3 && tools/sim_hover_step_run.sh; echo rc=$?`
Expected: `Ran 74 tests … OK (skipped=1)`; usage text and `rc=2`.

- [ ] **Step 6: Commit**

```bash
git add tools/lib/stack.sh tools/sim_hover_step_run.sh tools/tests/test_stack_sh.py tools/tests/test_scripts_syntax.py
git commit -m "tools: extract the shared sim phases into tools/lib/stack.sh (precheck…down, status, ulog helpers, land_all_and_wait + abort trap); the hover driver sources it, behaviour unchanged"
```

---

### Task 2: `tools/sim.sh` front door

**Files:**
- Create: `tools/sim.sh`
- Test: `tools/tests/test_sim_sh.py`

**Interfaces:**
- Consumes `tools/lib/stack.sh` (Task 1).
- Produces `tools/sim.sh <subcommand> …` with subcommands `setup doctor up down status tabs test figures check`. No arguments, `-h`, or an unknown subcommand → usage on stdout, exit 2, nothing run. Flag parsing (function `parse_test_args`): `test <name> [--headless] [--no-pause] --ledger N --issue NEAR-nnn <run>`; `--ledger` must be an integer, `--issue` must match `^NEAR-[0-9]+$`, `<name>` must be a directory `tools/sim_tests/<name>` other than `_template`, `<run>` must match `^[A-Za-z0-9_]+$`; any violation → the usage line plus `error: <what>` on stderr, exit 2, before any docker call. Sets `HEADLESS=true|false` (default `false`), `PAUSE=1|0` (default 1; headless forces 0), `USE_STUDIO` = not headless.
- `up [--headless]` = `precheck up watch isaac interfaces` with `RUN=_stack OUT=$HOME/flight_logs/sim/_stack HEAVY=$OUT S=/tmp/svg_test SCENARIO=- BAG_PREFIX=svg CONFIG=cbf_sim.yaml`; `down` = `down`; `status` = `status`; `tabs` = `exec tools/sim_terminals.sh`. `test`, `figures`, `setup`, `doctor`, `check` dispatch to functions `cmd_test cmd_figures cmd_setup cmd_doctor cmd_check` that Tasks 8 and 9 fill; until then each prints `not implemented yet` and exits 2.

- [ ] **Step 1: Write the failing test**

```python
# tools/tests/test_sim_sh.py
import pathlib, subprocess, unittest
SIM = pathlib.Path(__file__).resolve().parents[1] / "sim.sh"

def run(*args):
    return subprocess.run(["bash", str(SIM), *args], capture_output=True, text=True, timeout=20)

class SimSh(unittest.TestCase):
    def test_parses(self):
        self.assertEqual(subprocess.run(["bash", "-n", str(SIM)]).returncode, 0)

    def test_no_args_prints_usage_exit_2(self):
        r = run(); self.assertEqual(r.returncode, 2); self.assertIn("usage:", r.stdout)
        for sub in ("setup", "doctor", "up", "down", "status", "tabs", "test", "figures", "check"): self.assertIn(sub, r.stdout)

    def test_unknown_subcommand_exit_2(self):
        self.assertEqual(run("fly").returncode, 2)

    def test_sim_sh_rejects_bad_flags(self):                      # Review Focus 3
        for args in (["test", "crossing", "--ledger", "x", "--issue", "NEAR-787", "r1"],
                     ["test", "crossing", "--ledger", "20", "--issue", "NEAR787", "r1"],
                     ["test", "crossing", "--ledger", "20", "r1"],
                     ["test", "_template", "--ledger", "20", "--issue", "NEAR-787", "r1"],
                     ["test", "no_such_test", "--ledger", "20", "--issue", "NEAR-787", "r1"],
                     ["test", "crossing", "--ledger", "20", "--issue", "NEAR-787", "bad run"]):
            r = run(*args); self.assertEqual(r.returncode, 2, args); self.assertIn("error:", r.stderr, args)
            self.assertNotIn("docker", (r.stdout + r.stderr).lower(), args)   # failed before any container call; the usage text never says "docker"
            self.assertNotRegex(r.stdout, r"^\[\d\d:\d\d:\d\d")                # no `say` line: no phase ran
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /home/jeremychia/AirStack-starling-max2 && python3 -m unittest tools.tests.test_sim_sh -v`
Expected: FAIL (`sim.sh` missing).

- [ ] **Step 3: Write `tools/sim.sh`** with `usage()`, `parse_test_args()`, the `case` dispatch and the stub `cmd_*` functions; `up/down/status` set the `_stack` variables then `source "$(dirname "${BASH_SOURCE[0]}")/lib/stack.sh"` and call the phase. Header comment: what each subcommand does, sim-only line, "flags, not environment variables".

- [ ] **Step 4: Run the tests**

Run: `cd /home/jeremychia/AirStack-starling-max2 && python3 -m unittest discover -s tools/tests 2>&1 | tail -3`
Expected: `OK (skipped=1)`, 78 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/sim.sh tools/tests/test_sim_sh.py
git commit -m "tools: sim.sh front door (setup doctor up down status tabs test figures check), flag parsing, usage on no args; up/down/status via lib/stack.sh"
```

---

### Task 3: `tools/live/metrics_core.py` — the one place every formula lives

**Files:**
- Create: `tools/live/metrics_core.py`, `tools/live/__init__.py` (empty)
- Create: `tools/tests/synth_crossing.py` (test helper: synthetic frames)
- Test: `tools/tests/test_metrics_core.py`

**Interfaces (produces; every later task uses these names):**
```python
STALE_S = 0.5
class MetricsCsvError(ValueError): ...
@dataclass(frozen=True)
class Series: name: str; fn: Callable[["Frame"], float]; tol: float; unit: str = ""; kind: str = "continuous"; running_min: bool = False   # kind: "continuous" | "flag"
@dataclass
class Frame: t_s: float; pos: dict[str, np.ndarray]; vel: dict[str, np.ndarray]; stale: frozenset[str]; cbf_active: frozenset[str]; emergency: bool; fence_breached: bool; phase: int; start_pos: dict[str, np.ndarray]; params: dict
@dataclass
class CrossRow: name: str; tol: float; kind: str; max_abs_diff: float; sum_live: float; sum_bag: float; paired: int; unpaired_frac: float; ok: bool

def world_position(xyz, offset) -> np.ndarray
def pair_key(a: str, b: str) -> str                      # "d_12" for drone_1/drone_2 (sorted by name)
def pair_distance(frame, a, b) -> float                  # nan if a or b stale
def pairwise_distances(pos, stale=frozenset()) -> dict[str, float]
def min_pair_distance(frame) -> float
def speed_of(frame, drone) -> float                      # norm of odometry twist.linear (same as the commander's speed_mps)
def fence_margin(frame) -> float                         # min over non-stale drones and axes of distance to the nearest fence face (params fence_min/fence_max)
def goal_distance(frame, drone) -> float                 # |pos - antipode(start_pos)|, nan before phase 2
def antipode(p_start, center) -> np.ndarray              # 2*center - p_start
def arena_center(params) -> np.ndarray                   # (arena_low + arena_high) / 2
def phase_from_status(states: list[str], mission_active: bool, prev: int) -> int
def parse_param_array(text) -> list[float]               # "Double array value is: array('d', [-2.0, 0.0])" or "[-2.0, 0.0]"
def parse_param_scalar(text) -> float                    # "Double value is: 0.55"
def offsets_by_drone(flat: list[float], drones) -> dict[str, np.ndarray]
def offset_sanity(status_pos: dict, odom_pos: dict, offsets: dict, tol=0.05) -> list[str]   # one error string per drone off by > tol; [] = ok
class Tracker:
    def __init__(self, drones, offsets: dict, params: dict, series: list[Series], stale_s=STALE_S)
    def update_odom(self, drone, t, xyz, vxyz)
    def update_cbf(self, names_csv: str)
    def update_status(self, status: dict)             # reads drones[].state, mission_active, cbf.emergency, fence_breached
    def frame(self, t) -> Frame                        # phase via phase_from_status; start_pos captured on the 1→2 transition
    def row(self, t) -> dict[str, float]               # evaluate(series) + "<name>_running" running minima + "phase"
def evaluate(frame, series) -> dict[str, float]
def csv_columns(series) -> list[str]                      # ["t_s", "phase", *names, *running names]
def csv_header(series, meta: dict) -> str                 # "# key=value" lines (sorted keys; arrays as comma-joined) then the column line
def format_row(t_s, phase, values, columns) -> str
def read_metrics_csv(path) -> tuple[dict, list[str], np.ndarray]   # meta, columns, rows; MetricsCsvError if no column line, no "offsets" meta, or ragged rows
def meta_offsets(meta, drones) -> dict[str, np.ndarray]
def crosscheck(live_cols, live, bag_cols, bag, series, t_tol=0.05) -> list[CrossRow]   # nearest-timestamp pairing of live rows to bag rows; continuous: ok = max_abs_diff <= tol; flag: ok = |sum_live - sum_bag| <= max(2, 0.01 * paired); unpaired_frac > 0.05 → ok False for every row
def nan_fraction(rows, cols, name, phase=2) -> float
```
`synth_crossing.py` exports the crossing contract (`DRONES`, `TRIGGER = "drone_1"`, `PARAMS`, `REFERENCES`, `SERIES` — the lists Task 7 fixes for `crossing/metrics.py`, so the file also serves as a stand-in `metrics.py` in Task 4's smoke test) and provides `make_tracker(series=SERIES)`, `frame_at(t) -> Frame` (the synthetic world at time t, phase 2 from t = 1 s), `frames(n=400, dt=0.025, closest_m=1.25, emergency_at=None, peak_speed=2.0, cbf=True, far_goal_miss_m=None) -> (columns, rows)` that drives a `Tracker` with three drones on straight lines through the centre (offsets −2/0/2 on x, closest approach `closest_m` at t = 5 s, CBF names on drone_1 and drone_3 for t in [4, 6] when `cbf`, one emergency sample at `emergency_at` when given, each drone ending within 0.2 m of its antipode unless `far_goal_miss_m` says otherwise), and `write_csv(path, columns, rows, meta)` (`meta` defaults to the crossing params: offsets `-2,0,0,0,0,0,2,0,0`, arena −3..3 / 0.5..2.5, fence `[-3,-6,0]..[5,5,3]`, r 0.55, cap 4.0, refs, `t0_unix`).

- [ ] **Step 1: Write the failing tests**

```python
# tools/tests/test_metrics_core.py  (sys.path gets tools/live)
class Geometry(unittest.TestCase):
    def test_world_position_adds_offset(self):
        np.testing.assert_allclose(M.world_position([1, 2, 3], [-2, 0, 0]), [-1, 2, 3])
    def test_pairwise_distances_three_drones(self):
        pos = {"drone_1": np.array([0., 0, 1]), "drone_2": np.array([3., 4, 1]), "drone_3": np.array([0., 0, 2])}
        d = M.pairwise_distances(pos); self.assertEqual(set(d), {"d_12", "d_13", "d_23"}); self.assertAlmostEqual(d["d_12"], 5.0); self.assertAlmostEqual(d["d_13"], 1.0)
    def test_stale_drone_gives_nan_distance(self):                       # Review Focus 1
        f = synth.frame_at(5.0); f.stale = frozenset({"drone_3"})
        self.assertTrue(math.isnan(M.pair_distance(f, "drone_1", "drone_3"))); self.assertFalse(math.isnan(M.pair_distance(f, "drone_1", "drone_2")))
    def test_fence_margin_is_distance_to_nearest_face(self):
        f = synth.frame_at(0.0); f.pos = {"drone_1": np.array([4.5, 0, 1.0])}; f.params = {"fence_min": [-3, -6, 0], "fence_max": [5, 5, 3]}
        self.assertAlmostEqual(M.fence_margin(f), 0.5)
    def test_antipode_and_goal_distance(self):
        np.testing.assert_allclose(M.antipode(np.array([0.9, 0, 1.5]), np.array([0, 0, 1.5])), [-0.9, 0, 1.5])
        self.assertTrue(math.isnan(M.goal_distance(synth.frame_at(0.5), "drone_1")))   # before phase 2
class Phase(unittest.TestCase):
    def test_phase_transitions(self):
        self.assertEqual(M.phase_from_status(["IDLE"] * 3, False, 0), 0)
        self.assertEqual(M.phase_from_status(["ARMING", "IDLE", "IDLE"], False, 0), 1)
        self.assertEqual(M.phase_from_status(["ACTIVE"] * 3, True, 1), 2)
        self.assertEqual(M.phase_from_status(["LANDING", "ACTIVE", "ACTIVE"], False, 2), 3)
        self.assertEqual(M.phase_from_status(["IDLE"] * 3, False, 3), 0)
class Params(unittest.TestCase):
    def test_parse_param_array_ros2_format(self):
        self.assertEqual(M.parse_param_array("Double array value is: array('d', [-2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0, 0.0, 0.0])"), [-2.0, 0, 0, 0, 0, 0, 2.0, 0, 0])
    def test_offset_sanity_detects_wrong_offset(self):
        ok = M.offset_sanity({"drone_1": [-1.0, 0, 0.1]}, {"drone_1": [1.0, 0, 0.1]}, {"drone_1": np.array([-2.0, 0, 0])}); self.assertEqual(ok, [])
        bad = M.offset_sanity({"drone_1": [1.0, 0, 0.1]}, {"drone_1": [1.0, 0, 0.1]}, {"drone_1": np.array([-2.0, 0, 0])}); self.assertEqual(len(bad), 1); self.assertIn("drone_1", bad[0])
class TrackerAndCsv(unittest.TestCase):
    def test_running_min_and_min_distance_on_synthetic_run(self):
        cols, rows = synth.frames(); i = cols.index("min_pair_distance_running")
        self.assertAlmostEqual(rows[-1, i], 1.25, places=2); self.assertTrue(np.all(np.diff(rows[:, i]) <= 1e-9))
    def test_csv_roundtrip_keeps_meta_and_columns(self):
        cols, rows = synth.frames()
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "metrics.csv"; synth.write_csv(p, cols, rows, {"offsets": "-2,0,0,0,0,0,2,0,0", "t0_unix": "1.5"})
            meta, cols2, rows2 = M.read_metrics_csv(p); self.assertEqual(cols2, cols); self.assertEqual(meta["offsets"], "-2,0,0,0,0,0,2,0,0"); np.testing.assert_allclose(rows2, rows, atol=1e-4)
    def test_read_metrics_csv_without_offsets_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "m.csv"; p.write_text("t_s,phase,d_12\n0,0,1\n")
            with self.assertRaises(M.MetricsCsvError): M.read_metrics_csv(p)
class CrossCheck(unittest.TestCase):
    def test_identical_runs_agree(self):
        cols, rows = synth.frames(); cr = M.crosscheck(cols, rows, cols, rows.copy(), synth.SERIES)
        self.assertTrue(all(r.ok for r in cr)); self.assertEqual({r.name for r in cr}, {s.name for s in synth.SERIES} | {"min_pair_distance_running"})
    def test_min_distance_off_by_3cm_fails(self):
        cols, rows = synth.frames(); bag = rows.copy(); bag[:, cols.index("min_pair_distance")] -= 0.03
        bad = [r for r in M.crosscheck(cols, rows, cols, bag, synth.SERIES) if not r.ok]; self.assertIn("min_pair_distance", [r.name for r in bad])
    def test_flag_column_one_sample_skew_is_ok(self):
        cols, rows = synth.frames(); bag = rows.copy(); j = cols.index("cbf_drone_1"); k = int(np.argmax(bag[:, j])); bag[k, j] = 0; bag[k - 1, j] = 1
        self.assertTrue(next(r for r in M.crosscheck(cols, rows, cols, bag, synth.SERIES) if r.name == "cbf_drone_1").ok)
    def test_crosscheck_unpaired_rows_flagged(self):                     # Review Focus 5
        cols, rows = synth.frames(); bag = rows[::2]                        # bag lost every other row → half the live rows unpaired
        cr = M.crosscheck(cols, rows, cols, bag, synth.SERIES); self.assertTrue(all(r.unpaired_frac > 0.05 for r in cr)); self.assertFalse(any(r.ok for r in cr))
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd /home/jeremychia/AirStack-starling-max2 && python3 -m unittest tools.tests.test_metrics_core -v`
Expected: ImportError (`metrics_core`).

- [ ] **Step 3: Implement `tools/live/metrics_core.py` and `tools/tests/synth_crossing.py`** with the signatures above. Module docstring: the definitions (world frame, t_s, phase rule, stale rule, cross-check rule, sim-only). `synth_crossing.SERIES` is the crossing series list of Task 7 duplicated minimally here (d_12, d_13, d_23, min_pair_distance running, speed_drone_1..3, cbf_drone_1..3 flags, emergency flag, fence_breached flag, fence_margin, goal_dist_drone_1..3) so the synthetic fixtures match the real test; Task 7 imports `tools/sim_tests/crossing/metrics.py` in a test that asserts the two lists agree by name/kind/tol.

- [ ] **Step 4: Run the tests**

Run: `cd /home/jeremychia/AirStack-starling-max2 && python3 -m unittest discover -s tools/tests 2>&1 | tail -3`
Expected: `OK (skipped=1)`.

- [ ] **Step 5: Commit**

```bash
git add tools/live/__init__.py tools/live/metrics_core.py tools/tests/synth_crossing.py tools/tests/test_metrics_core.py
git commit -m "tools(live): metrics_core — pairwise distances from odometry + offsets, running min, speeds, fence margin, antipode goal distance, phase from commander_status, CSV schema, nearest-timestamp cross-check; Tracker drives live and offline alike"
```

---

### Task 4: `tools/live/metrics_node.py` (rclpy, container) and `tools/live/bag_recompute.py` (rosbag2_py, container)

**Files:**
- Create: `tools/live/metrics_node.py`, `tools/live/bag_recompute.py`
- Test: `tools/tests/test_metrics_node_source.py` (host: syntax + static checks only)

**Interfaces:**
- Consumes `metrics_core` (Task 3) and a test directory holding `metrics.py` that defines `SERIES: list[Series]`, `PARAMS: list[str]` (commander parameter names to read once), `REFERENCES: dict[str, Callable[[dict], float]]`, `TRIGGER: str`, `DRONES: tuple[str, ...]`.
- Produces `metrics_node.py --test-dir DIR --csv PATH [--publish-hz 10] [--commander /swarm_commander] [--status-topic /svg/commander_status] [--cbf-topic /svg/cbf_active] [--odom-template /{name}/odometry_conversion/odometry]`. Start-up: `ros2 param get <commander> <p>` for every `PARAMS` entry (via `subprocess`, parsed with `parse_param_array`/`parse_param_scalar`); wait ≤ 30 s for one status message and one odometry per drone; `offset_sanity` on them; on any failure print `metrics_node: REFUSED — <reason>` and exit 4. Then write the CSV header (`csv_header(SERIES, meta)` with meta = every param, `refs=<name>:<value>;…`, `t0_unix`, `trigger`, `drones`, `started=<iso>`), print `metrics_node: ready offsets=<…>`, and run: one CSV row per trigger odometry message (`Tracker.row`), a 10 Hz timer publishing `std_msgs/Float64` on `/svg/test/<name>` for every column but `t_s`/`phase`, `std_msgs/Float64` on `/svg/test/<ref>`, `std_msgs/Int32` on `/svg/test/phase`, and a 1 Hz line `[t=  12.0 s] phase=2 min_d=1.432 run_min=1.213 cbf=drone_1,drone_3 emerg=0` on stdout (`min_d`/`run_min` are the first `running_min` series and its running column). SIGINT/SIGTERM → flush, close, exit 0.
- Produces `bag_recompute.py <bag_dir> --test-dir DIR --meta-from LIVE_CSV -o OUT_CSV`: reads offsets/params/`t0_unix` from the live CSV header (never re-fetched), opens the mcap bag with `rosbag2_py` (as `tools/hover_step_bag.py` does), replays odometry ×drones, the cbf topic and the status topic in bag order through a `Tracker`, emits a row per trigger odometry `header.stamp`, writes the same schema with the same meta plus `source=bag:<dir>`, prints one JSON line `{"rows": n, "odom_msgs": {...}, "status_msgs": n, "cbf_msgs": n}`; exit 1 with a message if the bag holds no trigger odometry.

- [ ] **Step 1: Write the failing host test**

```python
# tools/tests/test_metrics_node_source.py
import ast, pathlib, py_compile, unittest
LIVE = pathlib.Path(__file__).resolve().parents[1] / "live"
class NodeSource(unittest.TestCase):
    def test_compiles(self):
        for f in ("metrics_node.py", "bag_recompute.py"): py_compile.compile(str(LIVE / f), doraise=True)
    def test_node_uses_metrics_core_and_the_spec_topics(self):
        src = (LIVE / "metrics_node.py").read_text()
        for needle in ("import metrics_core", "/svg/test/", "Float64", "Int32", "offset_sanity", "REFUSED", "metrics_node: ready", "--publish-hz", "header.stamp"):
            self.assertIn(needle, src, needle)
    def test_recompute_never_refetches_params(self):
        src = (LIVE / "bag_recompute.py").read_text()
        self.assertIn("--meta-from", src); self.assertNotIn("ros2 param", src); self.assertIn("rosbag2_py", src)
    def test_no_top_level_ros_import_in_core(self):
        tree = ast.parse((LIVE / "metrics_core.py").read_text())
        names = {n.names[0].name.split(".")[0] for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)) for _ in [0]} | {n.module.split(".")[0] for n in tree.body if isinstance(n, ast.ImportFrom) and n.module}
        self.assertFalse(names & {"rclpy", "rosbag2_py", "std_msgs", "nav_msgs"}, names)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /home/jeremychia/AirStack-starling-max2 && python3 -m unittest tools.tests.test_metrics_node_source -v`
Expected: FAIL (files missing).

- [ ] **Step 3: Implement both scripts** per the Interfaces block. The node imports `metrics_core` and the test's `metrics.py` with `importlib.util.spec_from_file_location` from `--test-dir` (the driver copies both into `/tmp/svg_test/`). Odometry subscriptions use `rclpy.qos.qos_profile_sensor_data`; the status and cbf topics default QoS. Docstrings: what runs where, exit codes, the CSV schema, sim-only line.

- [ ] **Step 4: Container smoke test (the containers are up: `docker ps` shows `isaac-sim` and `airstack-robot-desktop-1`)**

Run:
```bash
cd /home/jeremychia/AirStack-starling-max2 && R=airstack-robot-desktop-1
docker exec $R mkdir -p /tmp/svg_test && docker cp tools/live/metrics_core.py $R:/tmp/svg_test/ && docker cp tools/live/metrics_node.py $R:/tmp/svg_test/ && docker cp tools/live/bag_recompute.py $R:/tmp/svg_test/
docker cp tools/tests/synth_crossing.py $R:/tmp/svg_test/metrics.py        # stand-in metrics.py until Task 7 (it exports SERIES/PARAMS/REFERENCES/TRIGGER/DRONES)
docker exec $R bash -ic 'cd /tmp/svg_test && timeout 60 python3 metrics_node.py --test-dir /tmp/svg_test --csv /tmp/svg_test/m.csv; echo rc=$?' 2>&1 | grep -v -E 'cannot set terminal|no job control|Sourcing|groups: cannot'
docker exec $R bash -ic 'python3 /tmp/svg_test/bag_recompute.py /nonexistent --test-dir /tmp/svg_test --meta-from /nonexistent -o /tmp/x.csv; echo rc=$?' 2>&1 | tail -2
```
Expected: with no commander running the node prints `metrics_node: REFUSED — …/swarm_commander…` and `rc=4` within 30 s (not a traceback); the recompute prints a one-line error and `rc=1`. If the containers are not up, record `containers down — smoke test skipped` in the commit message and rely on Step 1's checks; Task 11 exercises the node for real.

- [ ] **Step 5: Run the host tests, commit**

Run: `cd /home/jeremychia/AirStack-starling-max2 && python3 -m unittest discover -s tools/tests 2>&1 | tail -3`
```bash
git add tools/live/metrics_node.py tools/live/bag_recompute.py tools/tests/test_metrics_node_source.py tools/tests/synth_crossing.py
git commit -m "tools(live): metrics_node (rclpy, in the robot container: offsets read once + sanity check, 40 Hz CSV, 10 Hz /svg/test/* + refs + phase, per-second line) and bag_recompute (rosbag2_py, same Tracker, recorded offsets)"
```

---

### Task 5: `tools/live/make_layout.py` + `plots.json` schema + staleness check

**Files:**
- Create: `tools/live/make_layout.py`
- Test: `tools/tests/test_make_layout.py`

**Interfaces:**
- Consumes the base layout `AirStack/robot/ros_ws/src/svg_ground_control/foxglove/svg_basestation.json` (read-only; keys `configById`, `globalVariables`, `userNodes`, `playbackConfig`, `layout`) and a test dir with `plots.json` + `metrics.py`.
- `plots.json` schema: `{"plots": [{"id": "<slug>", "title": "<text>", "series": ["<series or running name>", …], "refs": ["<reference name>", …], "y_range": [lo, hi] | null}, …], "phase_series": "phase", "panel_width_pct": 50}`.
- Produces:
```python
class LayoutError(ValueError): ...
BASE_LAYOUT = REPO / "AirStack/robot/ros_ws/src/svg_ground_control/foxglove/svg_basestation.json"
def load_series_names(test_dir) -> set[str]            # SERIES names ∪ "<name>_running" for running_min ∪ REFERENCES keys ∪ {"phase"}
def plot_panel(plot: dict) -> dict                      # Foxglove Plot config: paths [{"value": "/svg/test/<name>.data", "enabled": True, "timestampMethod": "receiveTime", "label": <name>} …], "xAxisVal": "timestamp", "showLegend": True, "legendDisplay": "floating", "showPlotValuesInLegend": True, "isSynced": True, "followingViewWidth": 60, "showXAxisLabels": True, "showYAxisLabels": True, "minYValue"/"maxYValue" from y_range
def phase_panel(name) -> dict                           # StateTransitions config: paths [{"value": "/svg/test/<name>.data", "timestampMethod": "receiveTime"}], "isSynced": True
def column_tree(ids: list[str]) -> dict | str           # balanced binary column tree with equal splitPercentage
def render(base: dict, plots: dict, known: set[str]) -> dict   # configById = base's + "Plot!svgtest_<id>" + "StateTransitions!svgtest_phase"; layout = {"direction": "row", "first": base["layout"], "second": column_tree([phase, *plots]), "splitPercentage": 100 - panel_width_pct}; other base keys copied; LayoutError("plot '<id>': unknown series '<name>'") on an unknown name, LayoutError on duplicate ids
def dumps(layout: dict) -> str                          # json.dumps(indent=2, sort_keys=True) + "\n"  (deterministic)
def studio_envelope(layout: dict, name: str) -> dict    # {"id": "lay_svgtest_<name>", "name": "svg_test_<name>", "permission": "CREATOR_WRITE", "baseline": {"data": layout, "savedAt": <iso>}}
def main(argv) -> int                                   # make_layout.py <test_dir> [--check] [--base PATH] [--studio-envelope]; writes <test_dir>/layout.json; --check: 0 fresh, 1 stale (prints "stale: run python3 tools/live/make_layout.py <test_dir>"), 2 error; --studio-envelope prints the envelope JSON to stdout
```

- [ ] **Step 1: Write the failing tests** (`make_test_dir(d)` writes a temp test dir with a `metrics.py` that defines, inline, `SERIES` = `d_12 d_13 d_23` + `min_pair_distance` (running_min) and `REFERENCES` with `ref_2r`/`ref_r` — it may import only `metrics_core`, since `make_layout` puts `tools/live` alone on `sys.path` — and a `plots.json` with plots `distances` (the four series + two refs, y 0–4) and `fence` (one series); `BASE` = the real base layout, `PLOTS` = that `plots.json`, `KNOWN` = `L.load_series_names(dir)`)

```python
class MakeLayout(unittest.TestCase):
    def test_render_keeps_base_panels_and_adds_plots(self):
        out = L.render(BASE, PLOTS, KNOWN)
        for k in ("svg-basestation.SVG Basestation!sbmain", "svg-basestation.SVG Basestation!sbpower", "3D!sbview"): self.assertIn(k, out["configById"])
        self.assertIn("Plot!svgtest_distances", out["configById"]); self.assertIn("StateTransitions!svgtest_phase", out["configById"])
        self.assertEqual(out["layout"]["first"], BASE["layout"]); self.assertEqual(out["layout"]["splitPercentage"], 50)
        paths = [p["value"] for p in out["configById"]["Plot!svgtest_distances"]["paths"]]
        self.assertEqual(paths, ["/svg/test/d_12.data", "/svg/test/d_13.data", "/svg/test/d_23.data", "/svg/test/min_pair_distance_running.data", "/svg/test/ref_2r.data", "/svg/test/ref_r.data"])
    def test_make_layout_rejects_unknown_series(self):                  # Review Focus 4
        bad = json.loads(json.dumps(PLOTS)); bad["plots"][0]["series"].append("d_99")
        with self.assertRaisesRegex(L.LayoutError, "distances.*d_99"): L.render(BASE, bad, KNOWN)
    def test_dumps_is_deterministic_and_check_detects_staleness(self):
        with tempfile.TemporaryDirectory() as d:
            td = make_test_dir(d); self.assertEqual(L.main([td]), 0); self.assertEqual(L.main([td, "--check"]), 0)
            p = pathlib.Path(td) / "plots.json"; j = json.loads(p.read_text()); j["plots"][0]["title"] = "changed"; p.write_text(json.dumps(j))
            self.assertEqual(L.main([td, "--check"]), 1)
    def test_envelope_shape(self):
        env = L.studio_envelope({"layout": {}}, "crossing"); self.assertEqual(env["id"], "lay_svgtest_crossing"); self.assertEqual(env["permission"], "CREATOR_WRITE"); self.assertIn("savedAt", env["baseline"])
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m unittest tools.tests.test_make_layout -v` → ImportError.

- [ ] **Step 3: Implement `tools/live/make_layout.py`** per the Interfaces block (stdlib json only; imports the test's `metrics.py` by path with `tools/live` on `sys.path`).

- [ ] **Step 4: Run the tests** — `python3 -m unittest discover -s tools/tests 2>&1 | tail -3` → `OK`.

- [ ] **Step 5: Commit**

```bash
git add tools/live/make_layout.py tools/tests/test_make_layout.py
git commit -m "tools(live): make_layout — plots.json + CMU's read-only svg_basestation.json → committed layout.json (Plot panels on /svg/test/*, StateTransitions on phase), deterministic, --check for staleness, Studio envelope"
```

---

### Task 6: `tools/lib/report.py` generic record renderer + `tools/live/plot_metrics.py` figure

**Files:**
- Create: `tools/lib/report.py`, `tools/lib/__init__.py` (empty), `tools/live/plot_metrics.py`
- Test: `tools/tests/test_report.py`, `tools/tests/test_plot_metrics.py`

**Interfaces:**
- Consumes `metrics_core.read_metrics_csv`, the hover fixtures `tools/tests/fixtures/run1/` (`isaac_evidence.txt`, `armed_post.txt`, `ulog_sysid_map.txt`, `res_watch.log`, `landing_evidence.txt`) for the generic rows, and a test dir's `test.env` + `gates.py`.
- `test.env` keys (shell `KEY=value` / `KEY="value"`, also parsed by `parse_env`): `TITLE PURPOSE SCOPE SIM_ONLY_LINE ISSUE MILESTONE CONFIG SCENARIO BAG_PREFIX DURATION_S BASELINE`.
- `gates.py` contract (what `report.py` calls): `build_rows(out: Path, heavy: Path, env: dict) -> tuple[list[Row], dict]` (ctx keys used by the renderer: `headline` str for the banner, `crosscheck` list[CrossRow] or None, `node_log_tail` str, `test_stdout` str, `caveats` list[str], `tuning` dict), `ledger_sentence(rows, ctx, verdict) -> str`, `figure_caption(ctx) -> str` (2–4 sentences, ≤ 380 chars, without the leading `Figure 1.`).
- Produces (`tools/lib/report.py`):
```python
@dataclass
class Row: check: str; criterion: str; measured: str; baseline: str; verdict: str; gate: bool
def row(rows, check, crit, meas, base, ok, gate=True) -> Row          # ok True/False/None → PASS/FAIL/UNVERIFIED; gate=False → "info"
def overall_verdict(rows, aborted=False) -> str                         # "ABORTED" if aborted else FAIL > INCOMPLETE > PASS
def parse_env(path) -> dict
def parse_kv(text) -> dict
def parse_armed_post(text) -> dict | None                                # moved from hover_step_report (same semantics; hover keeps its own copy)
def read(out, name) -> str
def isaac_rows(rows, out)                                                # the five "Isaac launch:" rows exactly as hover_step_report.build_rows writes them
def landing_rows(rows, out)                                              # info "landing: 'landed, disarmed' x3 (commander ACK log…)" + gate "post-flight armed=false x3 (MAVROS state)"
def evidence_rows(rows, out, heavy, bag_prefix, extra_files=())          # gate "rosbag copied + readable" (dir <bag_prefix>_* with metadata.yaml and every extra_files present in out), gate "PX4 ulogs one per sysid 2/3/4", gate "WiFi firmware alerts" (0), info "code that ran", info "driver verdict history"
def crosscheck_rows(rows, cr: list[CrossRow] | None, headline: str)      # one gate row "live vs bag recompute": PASS when every CrossRow ok, FAIL when a row is not ok, UNVERIFIED when cr is None; measured lists "<name> Δmax <v> (tol <t>)" for continuous and "<name> Σ <a> vs <b>" for flags, plus "unpaired <pct> %"
def append_verdict(out, verdict, rows, head_short) -> str                # same line format as hover: "<iso> head=<h> verdict=<v> fail=<n> unverified=<n>"
def ledger_row(num, today, sentence, run, issue) -> str                  # "| <num|?> | <today> | SIM | <sentence> | [<run>_record.md](<run>_record.md) | <issue|?> |"
def render(env, rows, ctx, out, heavy, verdict, history, ledger, issue) -> str
def load_gates(test_dir) -> module
def main(argv) -> int        # report.py <test_dir> <run_dir> [--heavy D] [--record P] [--ledger N] [--issue NEAR-nnn] [--no-verdict-log]; exit 0 PASS / 2 INCOMPLETE / 1 FAIL / 3 ABORTED (aborted = <run_dir>/aborted.txt exists); prints "<VERDICT>: <record path>" then one line per non-PASS gate
```
- Record shape written by `render`, in this order (DOCS_STANDARD §4): line 1 `RECORD · SIM — <run>. Sim-only (iron rule 9): <SIM_ONLY_LINE>`; `# <run> — <TITLE> (started <run_meta started tz>; flight <test_stdout first–last time> UTC)`; `**Verdict: <V>.** <PURPOSE> For Linear <ISSUE> (milestone <MILESTONE>). PASS = every gate PASS; INCOMPLETE = no FAIL but ≥ 1 gate UNVERIFIED; FAIL = any gate FAIL; ABORTED = Ctrl-C landing, never a result. Report generated <date> at repo \`<head>\`.`; `**Scope:** <SCOPE>`; `## Setup` table (Sim, Airframe, Commander = `<CONFIG> scenario:=<SCENARIO>` + tuning, Driver = `tools/sim.sh test <name>` + commit + dirty count, Started, Video = `video.txt` content or `none recorded`); `## Pass/fail` table `| Check | Criterion | Measured | Baseline | Verdict |` (FAIL/UNVERIFIED bold) + the "Rows marked info…" line; when `<run_dir>/fig-1.png` exists: `<a id="fig-1"></a>`, `![<TITLE>](<run>/fig-1.png)`, `*Figure 1. <figure_caption>*`; `## Driver verdict history` (code block); `## Evidence` (test stdout, metrics node log tail, landing + armed, cross-check table); `## Files` (repo folder list; heavy dir list with MB); `## Caveats`; `## Ledger row draft (docs/record/LEDGER.md table 1, #<n>, <issue>)` + the row.
- Produces (`tools/live/plot_metrics.py`): `plot(columns, rows, meta, plot_spec: dict, out_png, title)` and `main(argv)`: `plot_metrics.py <metrics.csv> --plots plots.json [--plot <id>, default the first] -o fig-1.png`; draws the plot's series against `t_s`, horizontal dashed lines for its refs at the values in `meta["refs"]`, shaded spans for phase 1 and 3 (phase column), legend, axis labels `t [s, wall]` and `<title>`; matplotlib `Agg`.

- [ ] **Step 1: Write the failing tests** (a temp test dir `fake/` with `test.env`, a minimal `gates.py` that returns rows through `report.isaac_rows/landing_rows/evidence_rows`, `metrics.py` from synth; the run dir seeded from `fixtures/run1` + a synthetic `metrics.csv`)

```python
class Report(unittest.TestCase):
    def test_clean_run_renders_pass_record_in_docs_standard_shape(self):
        rows, ctx = G.build_rows(out, heavy, env); self.assertEqual(R.overall_verdict(rows), "PASS")
        md = R.render(env, rows, ctx, out, heavy, "PASS", [], 20, "NEAR-787")
        head = md.splitlines()
        self.assertTrue(head[0].startswith("RECORD · SIM — ")); self.assertIn("Sim-only", head[0])
        self.assertIn("**Verdict: PASS.**", md); self.assertIn("**Scope:**", md); self.assertIn("| Check | Criterion | Measured | Baseline | Verdict |", md)
        self.assertIn("| 20 | ", md.splitlines()[-2]); self.assertIn("NEAR-787", md.splitlines()[-2])
    def test_figure_block_only_when_png_exists_and_caption_within_400(self):
        rows, ctx = G.build_rows(out, heavy, env)
        self.assertNotIn('<a id="fig-1"></a>', R.render(env, rows, ctx, out, heavy, "PASS", [], 20, "NEAR-787"))
        (out / "fig-1.png").write_bytes(b"x"); md = R.render(env, rows, ctx, out, heavy, "PASS", [], 20, "NEAR-787")
        i = md.index('<a id="fig-1"></a>'); self.assertTrue(md[i:].splitlines()[1].startswith("!["))
        cap = next(l for l in md.splitlines() if l.startswith("*Figure 1.")); self.assertLessEqual(len(cap), 400); self.assertTrue(cap.endswith("*"))
    def test_aborted_marker_forces_aborted_verdict(self):                # Review Focus 2
        (out / "aborted.txt").write_text("aborted=2026-10-29T12:00:00+08:00\n")
        rc = R.main([str(test_dir), str(out), "--heavy", str(heavy), "--no-verdict-log"]); self.assertEqual(rc, 3)
        self.assertIn("**Verdict: ABORTED.**", (out.parent / f"{out.name}_record.md").read_text())
    def test_missing_armed_post_is_unverified_and_incomplete(self):
        (out / "armed_post.txt").unlink(); rows, _ = G.build_rows(out, heavy, env); self.assertEqual(R.overall_verdict(rows), "INCOMPLETE")
    def test_crosscheck_rows_verdicts(self):
        rows = []; R.crosscheck_rows(rows, None, "min_pair_distance"); self.assertEqual(rows[0].verdict, "UNVERIFIED")
        rows = []; R.crosscheck_rows(rows, [M.CrossRow("min_pair_distance", 0.02, "continuous", 0.03, 0, 0, 100, 0.0, False)], "min_pair_distance"); self.assertEqual(rows[0].verdict, "FAIL")
    def test_cli_exit_codes_and_bad_issue(self):
        with self.assertRaises(SystemExit): R.main([str(test_dir), str(out), "--issue", "NEAR787"])
class PlotMetrics(unittest.TestCase):
    def test_renders_png_with_refs_and_phase(self):
        P.main([str(csv), "--plots", str(plots_json), "-o", str(png)]); self.assertGreater(png.stat().st_size, 15_000)
```

- [ ] **Step 2: Run to verify they fail** — `python3 -m unittest tools.tests.test_report tools.tests.test_plot_metrics -v` → ImportError.

- [ ] **Step 3: Implement `tools/lib/report.py` and `tools/live/plot_metrics.py`** per the Interfaces block. Copy the five Isaac rows, the landing/armed rows, the bag/ulog/WiFi/code/history rows and `append_verdict` from `tools/hover_step_report.py` (same wording, parameterised bag prefix); do not change the hover report.

- [ ] **Step 4: Run the tests** — `python3 -m unittest discover -s tools/tests 2>&1 | tail -3` → `OK`.

- [ ] **Step 5: Commit**

```bash
git add tools/lib/__init__.py tools/lib/report.py tools/live/plot_metrics.py tools/tests/test_report.py tools/tests/test_plot_metrics.py
git commit -m "tools(lib): report.py — generic DOCS_STANDARD record renderer (gate rows from a test's gates.py, Isaac/landing/bag/ulog evidence rows, cross-check row, verdict history, LEDGER draft with --ledger/--issue, scope line, anchored Figure 1, ABORTED exit 3); plot_metrics.py figure from metrics.csv"
```

---

### Task 7: `tools/sim_tests/_template/` and `tools/sim_tests/crossing/`

**Files:**
- Create: `tools/sim_tests/_template/{test.env,fly.sh,metrics.py,gates.py,plots.json,layout.json,README.md}`
- Create: `tools/sim_tests/crossing/{test.env,fly.sh,metrics.py,gates.py,plots.json,layout.json}`
- Test: `tools/tests/test_sim_tests_contract.py`

**Interfaces:**
- Consumes `metrics_core` (Task 3), `report` (Task 6), `make_layout` (Task 5).
- `crossing/metrics.py`: `DRONES = ("drone_1","drone_2","drone_3")`, `TRIGGER = "drone_1"`, `PARAMS = ["drone_position_offsets","arena_low","arena_high","fence_min","fence_max","cbf_safety_radius_m","cbf_max_speed_mps"]`, `REFERENCES = {"ref_2r": lambda p: 2*p["cbf_safety_radius_m"], "ref_r": lambda p: p["cbf_safety_radius_m"], "ref_speed_cap": lambda p: p["cbf_max_speed_mps"]}`, `SERIES` = `d_12 d_13 d_23` (tol 0.02 m), `min_pair_distance` (0.02 m, running_min), `speed_drone_1..3` (0.10 m/s), `cbf_drone_1..3` (flag), `emergency` (flag), `fence_breached` (flag), `fence_margin` (0.02 m), `goal_dist_drone_1..3` (0.05 m). Same list by name/kind/tol as `synth_crossing.SERIES`.
- `crossing/fly.sh [DURATION_S]` (default 45): CMU's `sim_cbf_crossing_test.sh` flow with `wait_s(){ sleep "$1"; }` (no `/clock` in the robot container), `svc` as CMU's, prints `[HH:MM:SS] pre-takeoff: <state x y z per drone>`, `takeoff: …`, the `start` retry loop (30 × 3 s), `start: …`, `window: <DURATION> s`, `land: …`, `wait_s 15`, `landed: <states>`; no analysis (the metrics node measures). Header comment names the CMU source and the two differences.
- `crossing/gates.py`: `build_rows(out, heavy, env)` reads `out/metrics.csv` via `read_metrics_csv` (missing/unreadable → every metric gate UNVERIFIED with the reason, never a crash) and `out/metrics_bag.csv` (missing → cross-check UNVERIFIED), and writes, in this order: `isaac_rows`; gate `min pairwise distance ≥ 1.10 m (2r)` measured `<min> m (margin <±x.xx> m to the gate; pair <d_ij> at t=<s> s)` baseline `#4: 1.02 m (0.08 m inside, 10-19 asset, 3 m/s cap, no bag)`; info `vs ledger #4` (`<min − 1.02> m`); gate `emergency samples` criterion `0 (5 Hz status string)`; gate `fence-breach samples` `0 (5 Hz status string)`; gate `CBF active on ≥ 1 drone at least once` (`/svg/cbf_active`, 20 Hz; measured = drones seen + seconds active); gate `far goal reached per drone` criterion `closest approach ≤ 0.40 m (commander arrival radius; spec draft said 0.3 m)` measured per drone; gate `peak speed ≤ 4.2 m/s` (cap 4.0 + 5 %); `landing_rows`; `crosscheck_rows` (the live CSV vs `metrics_bag.csv` through `metrics_core.crosscheck`); `evidence_rows(…, bag_prefix=env["BAG_PREFIX"], extra_files=("metrics.csv","metrics_bag.csv"))`; info `metrics node offsets (read once at start)` from the CSV meta; info `window / samples` (phase-2 duration, rows, Hz). Gate columns with `nan_fraction > 0.01` in phase 2 → that gate UNVERIFIED with `stale odometry in <pct> % of rows`. `ledger_sentence` = `CBF crossing, 3 drones antipodal, cbf_sim.yaml 2.0 / 4.0 m/s, live metrics: <V> — min pairwise distance <x.xx> m (2r 1.10), emergency <n>, fence breach <n>, peak <v> m/s, CBF on <drones>, landed + DISARMED ×3, bag cross-check <PASS|FAIL|UNVERIFIED>` (+ `; UNVERIFIED: …`/`; FAIL: …` like hover). `figure_caption` names the three pairs, the running minimum, the 1.10 m and 0.55 m lines, the shaded takeoff/land phases, `tools/sim.sh figures crossing <run>` and `metrics.csv`.
- `crossing/test.env`: `TITLE="three-drone CBF crossing, antipodal, live metrics"`, `ISSUE=NEAR-787`, `MILESTONE=S5`, `PURPOSE="Re-run of the three-drone crossing with collision avoidance on the rebuilt asset at cbf_sim.yaml's 2.0 / 4.0 m/s, gated on live 40 Hz odometry (ledger #4 sampled the 5 Hz status string)."`, `SCOPE="PX4's own sim state estimate positions the drones (no mocap, no camera); flat default world; camera and cuVSLAM not in the loop; speeds are cbf_sim.yaml's sim-only values."`, `SIM_ONLY_LINE="none of these values is ported to the drone; cbf_sim.yaml speeds are sim-only (iron rule 9)."`, `CONFIG=cbf_sim.yaml`, `SCENARIO=antipodal`, `BAG_PREFIX=crossing`, `DURATION_S=45`, `BASELINE="ledger #4 (2026-10-19): 1.02 m"`.
- `crossing/plots.json`: plots `distances` (d_12 d_13 d_23 min_pair_distance_running; refs ref_2r ref_r; y 0–4), `speeds` (speed_drone_1..3; ref_speed_cap; y 0–5), `cbf` (cbf_drone_1..3 emergency; y −0.1–1.1), `fence` (fence_margin; y 0–3); `phase_series: "phase"`, `panel_width_pct: 50`. `layout.json` generated.
- `_template/`: the same five files reduced to `d_12` + `min_pair_distance` + two drones' speeds, every value a placeholder the newcomer must change marked `CHANGE_ME` in `test.env` (TITLE, ISSUE, PURPOSE, SCOPE), one plot; `README.md` (10 lines: copy, fill, `tools/sim.sh check`, run once in window mode, record per DOCS_STANDARD §7).

- [ ] **Step 1: Write the failing tests**

```python
def make_run(tmp, **frames_kw):
    """Run dir = fixtures/run1 evidence files (isaac_evidence, res_watch.log, ulog_sysid_map) + armed_post false x3 + landing_evidence with
    3x 'landed, disarmed (attempt 1)' + run_meta + the synthetic csv written as BOTH metrics.csv and metrics_bag.csv; heavy dir with crossing_<stamp>/metadata.yaml.
    Returns (out, heavy, env) with env = report.parse_env(CROSSING / 'test.env')."""

def nan_out_rows(csv_path, columns, frac):
    """Rewrite the csv with every k-th phase-2 row's named columns set to nan so that `frac` of the phase-2 rows are nan."""

def verdict_of(rows, prefix):
    return next(r.verdict for r in rows if r.check.startswith(prefix))

# every test body below runs inside `with tempfile.TemporaryDirectory() as d:`
class Crossing(unittest.TestCase):
    def test_series_match_synth(self):
        self.assertEqual([(s.name, s.kind, s.tol, s.running_min) for s in CM.SERIES], [(s.name, s.kind, s.tol, s.running_min) for s in synth.SERIES])
    def test_clean_synthetic_run_passes(self):
        out, heavy, env = make_run(d); rows, ctx = G.build_rows(out, heavy, env)
        self.assertEqual(R.overall_verdict(rows), "PASS", [(r.check, r.measured) for r in rows if r.gate and r.verdict != "PASS"])
        self.assertIn("1.25", next(r.measured for r in rows if r.check.startswith("min pairwise distance")))
        self.assertEqual(next(r.verdict for r in rows if r.check.startswith("vs ledger #4")), "info")
    def test_distance_below_2r_fails(self):
        out, heavy, env = make_run(d, closest_m=1.05); rows, _ = G.build_rows(out, heavy, env); self.assertEqual(verdict_of(rows, "min pairwise distance"), "FAIL")
    def test_one_emergency_sample_fails(self):
        out, heavy, env = make_run(d, emergency_at=5.0); rows, _ = G.build_rows(out, heavy, env); self.assertEqual(verdict_of(rows, "emergency samples"), "FAIL")
    def test_speed_4_3_fails_and_4_1_passes(self):
        for peak, want in ((4.3, "FAIL"), (4.1, "PASS")):
            out, heavy, env = make_run(d, peak_speed=peak); rows, _ = G.build_rows(out, heavy, env); self.assertEqual(verdict_of(rows, "peak speed"), want, peak)
    def test_far_goal_0_45_fails(self):
        out, heavy, env = make_run(d, far_goal_miss_m=0.45); rows, _ = G.build_rows(out, heavy, env); self.assertEqual(verdict_of(rows, "far goal reached"), "FAIL")
    def test_no_cbf_activity_fails(self):
        out, heavy, env = make_run(d, cbf=False); rows, _ = G.build_rows(out, heavy, env); self.assertEqual(verdict_of(rows, "CBF active on"), "FAIL")
    def test_nan_fraction_makes_gate_unverified(self):     # Review Focus 1: NaN written into 5 % of the phase-2 rows of d_13 and min_pair_distance in metrics.csv
        out, heavy, env = make_run(d); nan_out_rows(out / "metrics.csv", ("d_13", "min_pair_distance"), frac=0.05)
        rows, _ = G.build_rows(out, heavy, env); self.assertEqual(verdict_of(rows, "min pairwise distance"), "UNVERIFIED"); self.assertEqual(R.overall_verdict(rows), "INCOMPLETE")
    def test_missing_csv_is_incomplete(self):
        out, heavy, env = make_run(d); (out / "metrics.csv").unlink(); rows, _ = G.build_rows(out, heavy, env)
        self.assertEqual(R.overall_verdict(rows), "INCOMPLETE"); self.assertIn("metrics.csv", next(r.measured for r in rows if r.check.startswith("min pairwise distance")))
    def test_missing_bag_csv_makes_crosscheck_unverified(self):
        out, heavy, env = make_run(d); (out / "metrics_bag.csv").unlink(); rows, _ = G.build_rows(out, heavy, env); self.assertEqual(verdict_of(rows, "live vs bag recompute"), "UNVERIFIED")
    def test_ledger_sentence_and_caption(self):
        out, heavy, env = make_run(d); rows, ctx = G.build_rows(out, heavy, env)
        self.assertLessEqual(len("*Figure 1. " + G.figure_caption(ctx) + "*"), 400); self.assertIn("NEAR", R.ledger_row(20, "2026-10-29", G.ledger_sentence(rows, ctx, "PASS"), "r", "NEAR-787"))
class FlySh(unittest.TestCase):
    def test_fly_parses_sleeps_and_keeps_cmu_flow(self):
        src = (CROSSING / "fly.sh").read_text(); self.assertEqual(subprocess.run(["bash", "-n", str(CROSSING / "fly.sh")]).returncode, 0)
        for n in ('wait_s(){ sleep "$1"; }', "svc takeoff", "svc start", "svc land", "DURATION", "landed:"): self.assertIn(n, src)
        self.assertNotIn("ros2 topic echo /clock", src); self.assertNotIn("python3", src)      # no analysis in the flight script
class Template(unittest.TestCase):
    def test_template_and_crossing_have_the_five_files_and_fresh_layout(self):
        for d in (TEMPLATE, CROSSING):
            for f in ("test.env", "fly.sh", "metrics.py", "gates.py", "plots.json", "layout.json"): self.assertTrue((d / f).exists(), d / f)
            self.assertEqual(L.main([str(d), "--check"]), 0, d)
            self.assertIn("metrics_core", (d / "gates.py").read_text())
```

- [ ] **Step 2: Run to verify they fail** — `python3 -m unittest tools.tests.test_sim_tests_contract -v` → errors (files missing).

- [ ] **Step 3: Write the two directories** per the Interfaces block; generate both `layout.json` with `python3 tools/live/make_layout.py tools/sim_tests/crossing` and `… _template`. `fly.sh` executable.

- [ ] **Step 4: Run the tests** — `python3 -m unittest discover -s tools/tests 2>&1 | tail -3` → `OK`.

- [ ] **Step 5: Commit**

```bash
git add tools/sim_tests
git commit -m "tools(sim_tests): the five-file contract — _template/ and crossing/ (NEAR-787: fly.sh from CMU's crossing flow, series list, gates ≥ 1.10 m / 0 emergency / 0 breach / CBF seen / far goal 0.40 m / peak ≤ 4.2 m/s / disarmed x3 / bag cross-check, plots.json → layout.json)"
```

---

### Task 8: `tools/sim.sh test` and `figures` wiring

**Files:**
- Modify: `tools/sim.sh` (`cmd_test`, `cmd_figures`)
- Test: `tools/tests/test_sim_sh.py` (static checks on the flow)

**Interfaces:**
- Consumes `stack.sh` (Task 1), `metrics_node.py`/`bag_recompute.py` (Task 4), `report.py`/`plot_metrics.py` (Task 6), the test dirs (Task 7).
- `cmd_test` flow (`S=/tmp/svg_test`, `OUT=$REPO/docs/record/$RUN`, `HEAVY=$HOME/flight_logs/sim/$RUN`, `SCENARIO/BAG_PREFIX/CONFIG/DURATION_S` from `test.env`, `ALL_MODE=1`): 1 `precheck up watch isaac interfaces commander params` (`STACK_UP=1` from `isaac`); 2 `arm_abort_trap` with `ABORT_HOOK=metrics_stop` and `REPORT_HOOK=render_report`; 3 copy-in: `docker exec $R mkdir -p $S` then `docker cp` of `tools/live/metrics_core.py`, `metrics_node.py`, `bag_recompute.py`, `tools/sim_tests/<name>/metrics.py`, `fly.sh` into `$R:$S/`; 4 `metrics_start`: `docker exec -d $R bash -ic "cd $S && python3 metrics_node.py --test-dir $S --csv $S/metrics.csv > $S/metrics_node.log 2>&1"`, `NEED=1 wait_for 60 2 "metrics node ready" count_log $R 'metrics_node: ready' $S/metrics_node.log || fail "metrics node refused: $(docker exec $R tail -3 $S/metrics_node.log)"`, liveness `rx "timeout 10 ros2 topic hz /svg/test/<first running series> -w 20" | grep 'average rate'` ≥ 5 Hz else `fail`; 5 `say "layout: tools/sim_tests/<name>/layout.json (import once in Studio if not installed by setup)"`; pause when `PAUSE=1`: `say "Stack up, drones on their pads, plots live. Start OBS now, then press Enter to fly."; read -r _ < /dev/tty`; 6 fly: `docker exec -d $R bash -ic "$S/fly.sh $DURATION_S > $S/test_stdout.log 2>&1"`; `docker exec $R tail -n0 -f $S/metrics_node.log & TAIL=$!`; poll `alive $R fly.sh` every 2 s up to `DURATION_S + 240` s; `kill $TAIL`; `docker cp $R:$S/test_stdout.log $OUT/`; `grep -q 'landed:' $OUT/test_stdout.log || say "WARN: fly.sh did not print landed:"`; 7 post-flight as hover `fly` (sleep 20; `armed_post.txt`; `landing_evidence.txt`; `status_post.json`); 8 `metrics_stop`: `docker exec $R pkill -INT -f metrics_node.py`, wait ≤ 10 s, `docker cp $R:$S/metrics.csv $OUT/` and `metrics_node.log`, append `offsets=<meta offsets>` to `$OUT/run_meta.txt`; 9 pause when `PAUSE=1`: `say "Landed. Plots still live. OBS file name (Enter to skip):"; read -r v < /dev/tty; echo "${v:-none recorded}" > $OUT/video.txt`; headless: `echo "none (headless run)" > $OUT/video.txt`; 10 `copy_ulogs`; `ulog_header_params`/`px4_arm_times_of` on the sysid-2 ulog (as hover `collect`); 11 `bag_dump_hook` = `docker exec $R bash -ic "python3 $S/bag_recompute.py <bag> --test-dir $S --meta-from $S/metrics.csv -o $S/metrics_bag.csv"` + `docker cp` to `$OUT/metrics_bag.csv` (failure → caveat, bag left); `down`; `docker exec $R rm -rf $S`; 12 `cmd_figures "$NAME" "$RUN"`; 13 `render_report`: `python3 tools/lib/report.py tools/sim_tests/<name> $OUT --heavy $HEAVY --ledger $LEDGER --issue $ISSUE | tee -a $OUT/run.log`; banner from the first stdout line: `========  VERDICT: <V> — <headline>  ========` (headline = the `min pairwise distance` row's measured cell, read from the record); exit with the report's rc (0/2/1/3).
- `cmd_figures <name> <run>`: `python3 tools/live/plot_metrics.py docs/record/<run>/metrics.csv --plots tools/sim_tests/<name>/plots.json -o docs/record/<run>/fig-1.png`.

- [ ] **Step 1: Extend the failing test**

```python
    def test_test_flow_wires_the_pieces(self):
        src = SIM.read_text()
        for n in ("source", "lib/stack.sh", "arm_abort_trap", "ABORT_HOOK=metrics_stop", "metrics_node.py", "bag_recompute.py", "metrics_node: ready", "ros2 topic hz /svg/test/",
                  "tail -n0 -f", "fly.sh", "armed_post.txt", "video.txt", "copy_ulogs", "bag_dump_hook", "report.py", "plot_metrics.py", "VERDICT:", "read -r"):
            self.assertIn(n, src, n)
        self.assertNotIn("sed -i", src); self.assertNotIn("AirStack/simulation/isaac-sim/tools", src)
        self.assertLess(src.index("commander"), src.index("arm_abort_trap"))        # trap armed only from the commander phase on
        self.assertLess(src.index('cmd_figures "$NAME" "$RUN"'), src.rindex("render_report"))   # figure exists before the record is rendered
    def test_figures_needs_two_args(self):
        self.assertEqual(run("figures", "crossing").returncode, 2)
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m unittest tools.tests.test_sim_sh -v` → FAIL on the stubs.

- [ ] **Step 3: Implement `cmd_test` and `cmd_figures`** in `tools/sim.sh` as the Interfaces block orders; `fail` inherits stack.sh's ALL_MODE/STACK_UP tear-down.

- [ ] **Step 4: Run the tests and the hover usage check**

Run: `cd /home/jeremychia/AirStack-starling-max2 && python3 -m unittest discover -s tools/tests 2>&1 | tail -3 && tools/sim.sh; echo rc=$?; tools/sim_hover_step_run.sh >/dev/null; echo rc=$?`
Expected: `OK`; both `rc=2`.

- [ ] **Step 5: Commit**

```bash
git add tools/sim.sh tools/tests/test_sim_sh.py
git commit -m "tools: sim.sh test — phases, copy-in, metrics node lifecycle (ready + liveness, stop after land), Enter pauses, Ctrl-C trap armed from the commander phase, per-second line, bag recompute cross-check, figures, record + verdict banner"
```

---

### Task 9: `setup` / `doctor` / `check`, pre-commit guard, layout install

**Files:**
- Create: `tools/lib/contract_check.py`
- Modify: `tools/sim.sh` (`cmd_setup`, `cmd_doctor`, `cmd_check`, `install_layout`), `tools/git-hooks/pre-commit`
- Test: `tools/tests/test_contract_check.py`, `tools/tests/test_sim_sh.py` (one more test)

**Interfaces:**
- `contract_check.py [--tests-root tools/sim_tests]` → exit 0 / 1; for every directory under the root (including `_template`): the five files + `layout.json` present; `gates.py` contains `metrics_core`; `python3 -m py_compile` of `metrics.py` and `gates.py`; `bash -n fly.sh`; `test.env` parses and carries `TITLE ISSUE SCOPE SIM_ONLY_LINE CONFIG SCENARIO BAG_PREFIX`; `make_layout.main([dir, "--check"]) == 0`. Prints one `OK <dir>` or `FAIL <dir>: <reason>` line per directory; `check(dir) -> list[str]` returns the problems for one directory.
- `tools/sim.sh check` = `python3 tools/lib/contract_check.py && python3 -m unittest discover -s tools/tests -p 'test_metrics_core*.py'`; exit non-zero on either.
- `tools/sim.sh setup` (idempotent; `doctor` = the same with `DRY=1`, changes nothing): checks `docker` on PATH; containers `isaac-sim`, `airstack-robot-desktop-1`, `airstack-gcs-1` exist (`docker ps -a`), else prints `run: cd AirStack && ./airstack.sh setup && ./airstack.sh up`; host `python3 -c 'import numpy, matplotlib'`; `ffmpeg`/`obs` on PATH (informational); in the robot container `command -v foxglove-studio` and `ls ~/.foxglove-studio/extensions | grep -i svg` (informational WARN); installs the hook (`bash tools/git-hooks/install.sh`); regenerates every `tools/sim_tests/*/layout.json` (`make_layout.py <dir>`); `install_layout <name>` for every test dir except `_template`; runs `tools/sim.sh check` and the full unit tests; prints a summary `setup: <n> OK, <m> WARN, <k> FAIL` and exits 1 on any FAIL.
- `install_layout <name>`: `STORE=/root/.config/Foxglove/studio-datastores/layouts-local`; if `docker exec $R test -d $STORE`: `python3 tools/live/make_layout.py tools/sim_tests/<name> --studio-envelope > <tmp>`; `docker cp <tmp> $R:$STORE/lay_svgtest_<name>`; say `layout installed: $STORE/lay_svgtest_<name> — appears in Studio's Layouts menu after Studio restarts`; else say `no Studio layout store in the container — import tools/sim_tests/<name>/layout.json once via Layouts → Import`. `doctor` reports whether the file is present.
- Pre-commit: after the existing two blocks add: when staged paths match `^tools/`, run `"$root/tools/sim.sh" check >/dev/null 2>&1 || { echo "pre-commit: tools/sim.sh check FAIL — run it"; rc=1; }`.

- [ ] **Step 1: Write the failing tests**

```python
class ContractCheck(unittest.TestCase):
    def test_repo_test_dirs_pass(self):
        self.assertEqual(C.main([]), 0)
    def test_missing_gates_file_fails_with_name(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(CROSSING, pathlib.Path(d) / "x"); (pathlib.Path(d) / "x" / "gates.py").unlink()
            probs = C.check(pathlib.Path(d) / "x"); self.assertTrue(any("gates.py" in p for p in probs))
    def test_stale_layout_fails(self):
        with tempfile.TemporaryDirectory() as d:
            td = pathlib.Path(d) / "x"; shutil.copytree(CROSSING, td); p = td / "plots.json"; j = json.loads(p.read_text()); j["plots"][0]["title"] = "changed"; p.write_text(json.dumps(j))
            self.assertTrue(any("stale" in m for m in C.check(td)))
# test_sim_sh.py
    def test_check_passes_on_the_repo(self):
        r = subprocess.run(["bash", str(SIM), "check"], capture_output=True, text=True, timeout=120); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
    def test_precommit_calls_check(self):
        self.assertIn("sim.sh\" check", (SIM.parent / "git-hooks" / "pre-commit").read_text())
```

- [ ] **Step 2: Run to verify they fail** — `python3 -m unittest tools.tests.test_contract_check tools.tests.test_sim_sh -v` → errors.

- [ ] **Step 3: Implement `contract_check.py`, the three `cmd_*` functions, `install_layout`, and the hook block.**

- [ ] **Step 4: Verify**

Run: `cd /home/jeremychia/AirStack-starling-max2 && python3 -m unittest discover -s tools/tests 2>&1 | tail -3 && tools/sim.sh check && tools/sim.sh doctor; echo rc=$?`
Expected: `OK`; `check` exits 0; `doctor` lists every check with OK/WARN/FAIL, names the layout store path, exits 0 (WARNs allowed). Then `bash tools/git-hooks/install.sh` and `tools/sim.sh setup` once (expected: `layout installed: …lay_svgtest_crossing …` or the import line).

- [ ] **Step 5: Commit**

```bash
git add tools/lib/contract_check.py tools/sim.sh tools/git-hooks/pre-commit tools/tests/test_contract_check.py tools/tests/test_sim_sh.py
git commit -m "tools: sim.sh setup/doctor/check — contract check (five files, gates imports metrics_core, layout fresh, metrics_core tests) in pre-commit; layouts generated and installed into the in-container Studio store (layouts-local) or an import path printed"
```

---

### Task 10: Docs around the front door

**Files:**
- Rewrite: `tools/README.md` (keep the `## Thresholds` heading — HTX-R1 links `tools/README.md#thresholds`)
- Modify: `docs/TEST_STANDARD.md` §2; `docs/projects/HTX-R1.md` lines 67 and 94; `docs/DOCS_STANDARD.md` §7 step 1; `docs/record/LEDGER.md` line 5 (the "drafted by" sentence); `docs/SCENARIOS.md` lines 222–227 (the re-run pointer); `CLAUDE.md` line 35 (tools row)
- Test: `tools/tests/test_scripts_syntax.py` (one link test)

**Interfaces:** none produced; every command named in these pages must exist by now.

- [ ] **Step 1: Write the failing test**

```python
    def test_readme_opens_with_the_three_command_install_and_names_every_front_door_file(self):
        src = (TOOLS / "README.md").read_text()
        self.assertLess(src.index("Install in three commands"), 600)
        for n in ("AirStack/airstack.sh setup", "tools/sim.sh setup", "tools/sim.sh test crossing --ledger", "## Thresholds", "tools/sim_tests/_template", "tools/lib/stack.sh", "tools/lib/report.py", "tools/live/metrics_core.py", "sim-only"):
            self.assertIn(n, src, n)
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m unittest tools.tests.test_scripts_syntax -v` → FAIL.

- [ ] **Step 3: Edit the pages**
  - `tools/README.md`: banner line (`DO · SIM`), then `## Install in three commands` (`cd AirStack && ./airstack.sh setup && ./airstack.sh up` → `tools/sim.sh setup` → `tools/sim.sh test crossing --ledger <next #> --issue NEAR-787 <run>`), `## What is here` table (front door, `lib/`, `live/`, `sim_tests/` with the five files, the hover tools unchanged, `docs_check/`, `git-hooks/`, `make_figures.sh`, `tests/`), `## Run a test` (flags; what the pauses ask; Ctrl-C = landing + ABORTED; the layout path; `tools/lib/report.py` re-render for a late video name), `## Adding a test` (copy `_template`, five files, `tools/sim.sh check`), `## Where things go`, `## Hover + step (legacy driver)` keeping today's "Run it" and `## Thresholds` verbatim, `## Tests` (count from `python3 -m unittest discover -s tools/tests`), `## Gotchas` (today's plus: layouts-local path and Studio restart; `--headless` when there is no DISPLAY).
  - `TEST_STANDARD.md` §2: add the five-command example block (`cp -r tools/sim_tests/_template tools/sim_tests/<name>` → edit the five files → `python3 tools/live/make_layout.py tools/sim_tests/<name>` → `tools/sim.sh check` → `tools/sim.sh test <name> --ledger N --issue NEAR-nnn <run>`).
  - `HTX-R1.md` line 94: `NEAR-787 at 2.0 / 4.0 m/s with a bag: \`tools/sim.sh test crossing --ledger 20 --issue NEAR-787 <run>\` ([TEST_STANDARD](../TEST_STANDARD.md))`; the Re-run sentence keeps the hover command and adds the crossing one. Line 67 Result stays `—` (no record yet), Evidence unchanged.
  - `DOCS_STANDARD.md` §7 step 1: `tools/sim.sh test <name> --ledger <next #> --issue NEAR-nnn <new_run_name>` (hover test until migrated: the existing `LEDGER=… tools/sim_hover_step_run.sh all …`).
  - `LEDGER.md` line 5: `drafted by tools/lib/report.py --ledger N --issue NEAR-nnn (every tools/sim.sh test) or tools/hover_step_report.py (the hover test)`.
  - `SCENARIOS.md` §5 "Status" sentence: replace the `AirStack/simulation/isaac-sim/tools/sim_cbf_crossing_test.sh` pointer with `tools/sim.sh test crossing … ([TEST_STANDARD](TEST_STANDARD.md))`.
  - `CLAUDE.md` tools row: `\`sim.sh\` front door (\`setup · doctor · up · down · status · tabs · test <name> … · figures · check\`, [tools/README.md](tools/README.md)), \`sim_terminals.sh\` + \`sim_tab.sh\`, the hover-step tools, \`make_milestones_doc.py\``.

- [ ] **Step 4: Verify**

Run: `cd /home/jeremychia/AirStack-starling-max2 && python3 -m unittest discover -s tools/tests 2>&1 | tail -3 && tools/docs_check/check_docs.sh | tail -1`
Expected: `OK`; `… 0 FAIL …`.

- [ ] **Step 5: Commit**

```bash
git add tools/README.md docs/TEST_STANDARD.md docs/projects/HTX-R1.md docs/DOCS_STANDARD.md docs/record/LEDGER.md docs/SCENARIOS.md CLAUDE.md tools/tests/test_scripts_syntax.py
git commit -m "docs: tools/README around the front door (install in three commands, adding a test), TEST_STANDARD §2 example, HTX-R1 S5 crossing command, DOCS_STANDARD §7 recipe, LEDGER drafting tool, SCENARIOS §5 pointer, CLAUDE tools row"
```

---

### Task 11: Acceptance — headless dry run, Ctrl-C path, record into the docs

**Files:**
- Create (by the run): `docs/record/sim_crossing_dry1/`, `docs/record/sim_crossing_dry1_record.md`, `~/flight_logs/sim/sim_crossing_dry1/`
- Modify: `docs/record/LEDGER.md` (append row #20 only if the verdict is PASS or FAIL), `docs/projects/HTX-R1.md` (NEAR-787 Result/Evidence from the record; results block with scope line; Figure 3), `tools/make_figures.sh` (crossing figure line), `docs/record/figures/s5_crossing_distances.png`

**Interfaces:** consumes everything above. The containers are up on this laptop (`docker ps`: `isaac-sim`, `airstack-robot-desktop-1`); Isaac headless ran today.

- [ ] **Step 1: Dry run, headless, no pauses**

Run: `cd /home/jeremychia/AirStack-starling-max2 && tools/sim.sh test crossing --headless --no-pause --ledger 20 --issue NEAR-787 sim_crossing_dry1 2>&1 | tee /tmp/claude-1000/-home-jeremychia/37cad1a9-5a36-4858-918e-0b06a95a9d2d/scratchpad/dry1.log; echo rc=${PIPESTATUS[0]}`
Expected: `metrics node ready`, ~45 per-second lines, `VERDICT: <PASS|FAIL>` banner, rc 0 or 1 (an INCOMPLETE = rc 2 is a tooling defect: read the UNVERIFIED rows, fix the task that owns them, re-run as `sim_crossing_dry2`). Then `tools/docs_check/check_docs.sh | tail -1` → `0 FAIL` (the record's links and image resolve), `ls docs/record/sim_crossing_dry1/` shows `metrics.csv metrics_bag.csv fig-1.png armed_post.txt video.txt run_meta.txt verdicts.log`, and the record's `live vs bag recompute` row is PASS.

- [ ] **Step 2: Ctrl-C path**

Run (a background job started from a non-interactive bash inherits SIGINT ignored, so the trap would never fire; drive it from Python, which restores default signal dispositions in the child):
```bash
cd /home/jeremychia/AirStack-starling-max2 && python3 - <<'PY'
import signal, subprocess, time
log = open("/tmp/claude-1000/-home-jeremychia/37cad1a9-5a36-4858-918e-0b06a95a9d2d/scratchpad/abort1.log", "w")
p = subprocess.Popen(["tools/sim.sh", "test", "crossing", "--headless", "--no-pause", "--ledger", "21", "--issue", "NEAR-787", "sim_crossing_abort1"],
                     stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
while True:
    r = subprocess.run(["docker", "exec", "airstack-robot-desktop-1", "cat", "/tmp/svg_test/test_stdout.log"], capture_output=True, text=True)
    if "start: success=True" in r.stdout: break
    if p.poll() is not None: raise SystemExit(f"driver exited early rc={p.returncode}")
    time.sleep(2)
time.sleep(10); p.send_signal(signal.SIGINT); print("rc", p.wait())
PY
tail -5 /tmp/claude-1000/-home-jeremychia/37cad1a9-5a36-4858-918e-0b06a95a9d2d/scratchpad/abort1.log; cat docs/record/sim_crossing_abort1/armed_post.txt
```
Expected: `ABORT: Ctrl-C — landing`, three `armed: false` lines, `rc=3`, `docs/record/sim_crossing_abort1_record.md` with `**Verdict: ABORTED.**`, bag + ulogs in `~/flight_logs/sim/sim_crossing_abort1/`. Then remove the driver-test artefacts (ruling 13): `rm -rf docs/record/sim_crossing_abort1 docs/record/sim_crossing_abort1_record.md ~/flight_logs/sim/sim_crossing_abort1` and confirm `git status --short` shows nothing from it.

- [ ] **Step 3: Record into the docs (DOCS_STANDARD §7)**
  - Paste the record's drafted row as LEDGER #20 (only if the verdict is PASS or FAIL; an INCOMPLETE record is fixed and re-run first).
  - `tools/make_figures.sh`: add `python3 tools/live/plot_metrics.py docs/record/sim_crossing_dry1/metrics.csv --plots tools/sim_tests/crossing/plots.json -o docs/record/figures/s5_crossing_distances.png`; run it.
  - `HTX-R1.md` S5: NEAR-787 Result cell `<verdict> — min <x.xx> m, 2026-10-29`, Evidence `[#20](../record/LEDGER.md) → [dry1 record](../record/sim_crossing_dry1_record.md)`; after the NEAR-786 figure add: a one-line `NEAR-787 — results (sim only; …)` with the scope sentence first (position source, world, camera/cuVSLAM not in the loop), one reading sentence pointing at `[Figure 3](#fig-3)`, `<a id="fig-3"></a>`, the image, `*Figure 3. …*` (≤ 400 chars, names `tools/make_figures.sh` and `[#20]`); keep the S5 section ≤ 40 counted lines (shorten the "Open:" line if needed; detail belongs in the record).
  - `tools/tests/test_scripts_syntax.py::test_make_figures_names_the_runs_and_the_fixed_output`: add the two new needles (`sim_crossing_dry1`, `s5_crossing_distances.png`).

- [ ] **Step 4: Verify**

Run: `cd /home/jeremychia/AirStack-starling-max2 && tools/docs_check/check_docs.sh | tail -1 && python3 -m unittest discover -s tools/tests 2>&1 | tail -3 && tools/sim.sh check && tools/sim_hover_step_run.sh >/dev/null; echo rc=$?`
Expected: `0 FAIL`; `OK`; check 0; `rc=2`.

- [ ] **Step 5: Commit (pre-commit guard runs docs check, unit tests and `sim.sh check`)**

```bash
git add docs/record/sim_crossing_dry1 docs/record/sim_crossing_dry1_record.md docs/record/LEDGER.md docs/projects/HTX-R1.md docs/record/figures/s5_crossing_distances.png tools/make_figures.sh tools/tests/test_scripts_syntax.py
git commit -m "HTX-R1/S5 NEAR-787: headless dry run of the crossing on the live driver (ledger #20) — record, Figure 3, Ctrl-C path exercised (ABORTED record, disarmed x3)"
```

- [ ] **Step 6: Hand the owner the final step (not for the implementer)**

Print for the owner, verbatim: `tools/sim.sh test crossing --ledger 21 --issue NEAR-787 sim_crossing_run1` — Isaac window on, OBS running from the first Enter, the in-container Studio layout `svg_test_crossing` selected (import `tools/sim_tests/crossing/layout.json` once if it is not in the Layouts menu), the OBS file name typed at the second pause; then LEDGER #21, HTX-R1 Result/Evidence from that record, the video name in the record, and `git -C ~/Documents/GitHub/AirStack-starling-max2 pull ~/AirStack-starling-max2 main` before pushing from GitHub Desktop.

---

## Self-review notes

- Spec coverage: decisions 1–11 → T4/T3 (1), T3/T7/T8 (2), T5/T9 (3), T7 (4), T2/T1/T6 (5), T8 (6), T1/T8 (7), T7 (8), T7 plots.json + T5 (9), T6/T7/T8/T11 (10), T9 (11). Builder-check answers 1–10 → T4 (1, 2, 3, 5), T7 (4), T1/T8 (6), T5/T9 (7), T1 (8), T3/T5 tests location (9), T9 install + T1 precheck WARN (10). Architecture install steps 1–4 → T9. "Done when" → T11 plus the owner's step. TEST_STANDARD rules 1–13 → T2 (1), T2/T8 (2), T4/T5 (3), T7/T8 (4), T3 (5), T7 (6), T8 (7), T1/T8 (8), T4/T8 (9), T6/T8 (10), T7 (11), every task (12), T9 (13).
- Names used across tasks: `Series Frame Tracker CrossRow read_metrics_csv crosscheck nan_fraction` (T3) ← T4, T6, T7; `Row row overall_verdict isaac_rows landing_rows evidence_rows crosscheck_rows` (T6) ← T7; `build_rows ledger_sentence figure_caption` (T7 contract, declared in T6) ← T6 CLI, T8; `make_layout.main --check / --studio-envelope` (T5) ← T7 test, T9; `bag_dump_hook ABORT_HOOK REPORT_HOOK arm_abort_trap land_all_and_wait ulog_header_params px4_arm_times_of USE_STUDIO` (T1) ← T8.
