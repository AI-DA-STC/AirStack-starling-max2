# Change-logging coding standard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (one executor per task, a reviewer per task) or superpowers:executing-plans. Each task is self-contained: read only what it names. Steps use `- [ ]` syntax. Authority: [the approved design](../specs/2026-11-02-change-logging-standard-design.md) (owner, 2026-11-02), including "Owner must know" and B1–B11.

**Goal:** Every change that can alter how the software or the simulated drone behaves gets one entry (ID, What, Scope, Why, Could affect, Watch for, Verified by, Revert): one line in `docs/record/CHANGES.md` plus the full entry in the commit body. A missing entry blocks the commit. Live sim changes (PX4 parameters, commander gains) are captured by the tools into the run folder. Every sim-only value in the sim airframe is labelled on its own line and checked against the drone's parameter file.

**Architecture (3 sentences):** A stdlib module `tools/docs_check/changes.py` owns the path map, the CHANGES.md parser, the staged-commit rule (called first by the versioned pre-commit hook, which `core.hooksPath` runs directly) and the git-log audit (a new `change-log` pass of `check_docs.py`). Live changes go through one container-side helper, `tools/lib/px4_param_set.sh`, which writes one `changes.log` line through the one formatter `tools/lib/changes_log.py`; `tools/sim.sh param set` calls it from the host, and the yaw-step sweep calls it from `fly.sh`. Each `sim.sh test` also takes start/end parameter snapshots, dumps PX4's own changed-parameter list from the ulogs, and `report.py` prints all three under "Changes in this run". A bare `sim.sh down` first saves any uncopied ulog.

## Global constraints

- Repo `/home/jeremychia/AirStack-starling-max2`, live clone, branch `main`. Read `CLAUDE.md` first (iron rules; rule 9). **Never push.** Leave the owner's untracked items alone: `.claude/`, `QGroundControl-x86_64.AppImage`, `starling max2 voxl setup.txt`, `docs/record/sim_hover_step_run4/`.
- **Start condition (design B8):** the yaw plan `docs/superpowers/plans/2026-11-02-sim-yaw-step-test.md` has Task 4 committed, with any fix rounds, and its Task 5 not started. Check: `git log --oneline -- tools/sim_tests/yaw_step/fly.sh` shows a commit, and `git status --short tools/ AirStack/` prints nothing. If not, stop and tell the orchestrator.
- **No sim.** Executors never start Isaac, the stack or any container, and no test may reach real docker. Shell tests use `guarded_env()` from `tools/tests/test_sim_sh.py`, plus a fake `docker`/`ros2` first on PATH. Git fixture repos use `clean_env()` (Task 1), which drops every inherited `GIT_*` variable. The hook exports `GIT_DIR`/`GIT_INDEX_FILE`, and without this a fixture would write into the live repo.
- Python tests: `python3 -m unittest discover -s tools/tests` (no pytest on this host). TDD: write the failing test first, run it, watch it fail, then implement.
- `AirStack/` is CMU's tree. The only file this plan touches there is the sim airframe `AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max` (ours, sim-only; per-line markers approved). The real drone's parameters (`starling_1_indoor_params.params`) are read, never written.
- Docs edits: only the pages this plan names (approved in the design's Done-when). Every other docs change goes under "Docs follow-ups" at the end, for the owner to OK.
- **Commits:** only your own paths, via `git add <new files>` then `git commit -F <msgfile> -- <your paths>`. With paths given, git commits only those, and the hook sees only them. Never `--no-verify`. The orchestrator hands out CHG IDs (design B6). From Task 3 on, every commit carries its CHANGES.md line and a commit body that starts with its `Change:` block.
- **Bootstrap:** Task 1 lands and activates the hook (it touches no behaviour path, so it needs no entry). Task 2 is the standard's start commit: it adds `docs/CODING_STANDARD.md` and CHANGES.md and carries the backfilled entries CHG-0001…CHG-B in its body. Tasks 3–7 each carry their own new ID. No commit of this plan touches a behaviour path before both the hook and the start commit exist.
- **IDs:** B = the last backfilled ID (Task 2 computes it; as of 2026-11-02 14:00 it is at least CHG-0008). Task 3 = B+1, Task 4 = B+2, Task 5 = B+3, Task 6 = B+4, Task 7 = B+5. The yaw plan's Task 5 takes the next ID after that.

## Facts verified by reading code (2026-11-02)

| Fact | Where |
|---|---|
| The hook is a copy in `.git/hooks/pre-commit` (identical to `tools/git-hooks/pre-commit`); `core.hooksPath` unset; `install.sh` copies; `sim.sh setup` runs `install.sh`, `doctor` WARNs on a stale copy (`cmp -s`) | `tools/git-hooks/*`, `tools/sim.sh` `cmd_setup` |
| `check_docs.sh` runs `python3 -I`: the script's directory is NOT on `sys.path`, so `check_docs.py` must `sys.path.insert(0, str(HERE))` before importing a sibling | `tools/docs_check/check_docs.sh` |
| The iron-rule block is diffed byte-for-byte (`check_iron_rules`); a PREFLIGHT edit without a new `vYYYY-MM-DD` on line 1 FAILs (`check_preflight_date`); current token `v2026-10-29` | `check_docs.py` |
| The airframe has 48 `param set-default` lines. Against `starling_1_indoor_params.params` (tab-separated `sysid comp NAME value type`, floats such as `3e+01`), 20 equal the drone's value, 24 differ, and 4 (`PWM_MAIN_FUNC1–4`) have no real counterpart. Table in Task 3. | python comparison, 2026-11-02 |
| A trailing `# …` comment on an airframe line is parsed by PX4 SITL: line 33 `MPC_THR_HOVER 0.165   # thrust SETPOINT …` is in force (`docs/record/sim_crossing_run2/params_ulog.txt`: `MPC_THR_HOVER 0.16500000655651093`) | record |
| MAVROS read-back strings: `Double value is: 0.0320…`, `Integer value is: 10090`; param services `/drone_N/interface/mavros/param/{pull,set,get_parameters,set_parameters,…}`; a `get_type_description` service exists (newer ROS 2, so `ros2 param dump` should print YAML to stdout, UNVERIFIED) | `docs/record/sim_crossing_run2/params_mavros.txt`, `sim_crossing_dry1/params_mavros_names.txt` |
| `force_set` on MAVROS parameter writes aborted `mavros_node` mid-flight; never use it | `docs/AI_ASSIST.md` §4 (ledger #11) |
| Commander node: `/swarm_commander` | `swarm_commander.py:332`, `stack.sh` service calls |
| PX4 SITL logs from boot (`SDLOG_MODE 1`); pyulog `changed_parameters` with a message filter holds 46 boot-time entries at 0.9–1.0 s (`CAL_*`, `MAV_*`, `SENS_*`, `SYS_*`, `UXRCE_*`) and nothing else in two sim runs, so only changes after 2.0 s count | `~/flight_logs/sim/sim_crossing_run2/drone_1_sysid2_18_32_18.ulg`, `sim_gains_run1/` |
| `stack.sh down()` already copies ulogs (`copy_ulogs`) into `$HEAVY` unless `$OUT/ulogs_copied.ok` exists; for a bare `sim.sh down`, `OUT=HEAVY=~/flight_logs/sim/_stack` (`stack_env`); test runs name copies `drone_<n>_sysid<s>_<basename>.ulg` | `stack.sh`, `sim.sh stack_env` |
| `metrics_collect` (called by `metrics_stop` on the normal and the abort path) is where files leave `$S=/tmp/svg_test` before `cmd_test` removes it | `sim.sh` |
| `git log --since=2026-11-02` returns nothing at 14:00, because git reads a bare date as that day at the current time. Use `--since='2026-11-02 00:00'`. | run 2026-11-02 |
| Behaviour commits since 2026-11-02 00:00 that predate the standard: `777b0c3`, `a9f38d3`, `923fbad`, `1c45625` (each already carries a "CHANGE LOG" section to draw from), plus whatever the yaw Task 1 fix round and Task 4 add | `git log` |

## Review focus (five failure modes the tests must catch)

1. **A behaviour path staged without a new CHANGES.md line** (the airframe, `tools/sim.sh`, any yaml) is blocked: `Staged.test_airframe_without_a_changes_line_fails`, `HookEndToEnd.test_behaviour_commit_without_entry_is_blocked_then_passes_with_one` (Task 1).
2. **ID reuse across branches.** The same ID twice in the file is blocked by the hook and FAILs the docs check. The same ID carried by two commits FAILs the audit: `Staged.test_reused_id_fails`, `Audit.test_id_carried_by_two_commits_fails`, `Audit.test_duplicate_rows_fail` (Task 1).
3. **A SIM-ONLY marker whose real value is wrong**, or `= real` on a value that differs: `Markers.test_sim_only_with_the_wrong_real_value_fails`, `test_equal_real_passes_and_differing_real_fails`, plus the repo-wide `test_the_repo_airframe_is_fully_marked_and_true` (Task 3).
4. **A `--no-verify` commit** that touches a behaviour path is caught after the fact by the docs check, and a late entry fixes it without rewriting history: `Audit.test_no_verify_behaviour_commit_is_caught_after_the_fact` (Task 1).
5. **The hook is not active on a fresh clone.** `install.sh` sets `core.hooksPath` (`HookEndToEnd.test_install_sets_hooks_path`, Task 1); `sim.sh doctor` FAILs without it (`HookCheck.test_fresh_clone_fails`, Task 4). Commits made meanwhile are still caught by focus 4.

## Dependency graph and parallel groups

**G1:** T1 → **G2:** T2 → **G3:** T3 ∥ T4 (T3 may also overlap T5) → **G4:** T5 (after T4: both edit `tools/sim.sh`) → **G5:** T6 (after T3 and T5) → **G6:** T7.
Parallel executors work in separate git worktrees (superpowers:using-git-worktrees; `core.hooksPath` is relative, so each worktree runs its own versioned hook). The orchestrator lands their commits on `main` one at a time. A CHANGES.md conflict is resolved by keeping both lines: the order of lines is free, and IDs only need to be unique. Without worktrees, run every task serially.

---

### Task 1: The rule and its enforcement: `changes.py`, the hook, the `change-log` docs check (executor: **opus**)

**Files:**
- Create: `tools/docs_check/changes.py`, `tools/tests/test_changes.py`
- Modify: `tools/git-hooks/pre-commit`, `tools/git-hooks/install.sh`, `tools/docs_check/check_docs.py` (+ `check_change_log`), `tools/docs_check/README.md` (one table row), `tools/tests/test_check_docs.py` (one class)

**Interfaces produced (exact names; later tasks and the docs rely on them):**
- Constants: `CHANGES_FILE = "docs/record/CHANGES.md"`, `STANDARD_FILE = "docs/CODING_STANDARD.md"`, `LEDGER_FILE = "docs/record/LEDGER.md"`, `FIELDS = ("Change:", "What:", "Scope:", "Why:", "Could affect:", "Watch for:", "Verified by:", "Revert:")`, `SCOPES = ("sim-only", "real-drone", "sim+real", "tooling")`.
- `ROW_RE = r"^\| (CHG-\d{4}) \| (\d{4}-\d\d-\d\d) \| (sim-only|real-drone|sim\+real|tooling) \| ([^|]+?) \| (this|[0-9a-f]{7,40}(?:, [0-9a-f]{7,40})*) \|\s*$"`. Any line that starts with `| CHG-` and does not match is malformed. The What cell can never hold `|`.
- `CHANGE_RE = r"^Change: (CHG-\d{4})\b"` (multiline, over commit bodies).
- `is_behaviour(path) -> bool`. A path is behaviour if it matches an INCLUDE pattern and no EXCLUDE pattern:
  - INCLUDE: `^AirStack/`, `^patches/`, `^starling_1_indoor_params\.params$`, `^mocap(\.sh$|/)`, `^tools/(sim|sim_tab|sim_terminals|sim_hover_step_run)\.sh$`, `^tools/hover_step_report\.py$`, `^tools/(lib|live|teleop)/`, `^tools/sim_tests/(?!_template/)[^/]+/(fly\.sh|gates\.py|metrics\.py|test\.env)$`, `^localisation/(nodes|scripts|docker|scenes)/`, `\.ya?ml$`, `(^|/)launch/`, `(^|/)Dockerfile`, `(^|/)docker-compose`, `fastdds\.xml$`.
  - EXCLUDE (wins): `\.md$`, `(^|/)docs/`, `(^|/)tests?/`, `\.(png|jpe?g|gif|svg|pdf|mkv|mp4|ulg)$`, `^\.github/`, `^\.claude/`.
- `parse_rows(text) -> (rows, bad)`, where `rows` = list of `Row(id, date, scope, what, commits: tuple[str], lineno, raw)` and `bad` = list of `"malformed line N: …"`.
- `staged_problems(old_text, new_text, staged_paths, standard_present) -> (errors: list[str], new_ids: list[str])`. Pure. If `standard_present` is False it returns `([], [])`.
- `audit(root) -> (fails, warns, skip)`. `skip` is a reason string when `docs/CODING_STANDARD.md` does not exist in the working tree, else `None`. Every git call scrubs `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_COMMON_DIR`, `GIT_OBJECT_DIRECTORY`, `GIT_PREFIX`, and runs `git -C root`.
- `entry_block(body, cid) -> list[str] | None`: the lines from `Change: <cid>` through the first line starting `Revert:`.
- CLI (`python3 tools/docs_check/changes.py …`, run from anywhere inside the repo):
  - `hook`: the staged rule, using the inherited git env (it needs the hook's `GIT_INDEX_FILE`). Exit 1 on any error.
  - `audit`: prints FAIL/WARN lines; exit 1 on any FAIL.
  - `show CHG-nnnn`: prints the CHANGES.md line, a blank line, then the entry block; exit 1 if either is missing.
  - `candidates --since '<date> 00:00'`: oldest first, prints `<sha7> <subject>` for each non-merge commit that touches behaviour paths, has no `Change:` line and is not named in a Commit cell.
  - `is-behaviour <path>…`: prints `<path>: yes|no` for each path.
- Check messages (tests assert these substrings):
  - Hook: `behaviour path(s) staged without a new docs/record/CHANGES.md line: <paths>`; `docs/record/CHANGES.md is append-only`; `duplicate ID CHG-nnnn`; `malformed line`.
  - Hook success: `change log: CHG-nnnn staged — start the commit body with 'Change: CHG-nnnn'`.
  - Audit: `duplicate ID CHG-nnnn`; `CHG-nnnn: no commit carries 'Change: CHG-nnnn'`; `CHG-nnnn: carried by N commits (<shas>) — ID reuse`; `commit <sha7> names unknown CHG-nnnn`; `commit <sha7> touches behaviour paths (<≤3 paths>) without a Change: line`; `CHG-nnnn: Verified by cites LEDGER #n, not in docs/record/LEDGER.md table 1`; `CHG-nnnn: commit cell names <sha>, which is not a commit`.
  - Audit WARN: `CHG-nnnn: entry lacks <field>`.

**Audit rules (R1–R8; the design's B5/B6 made exact):**
- R1. No `docs/CODING_STANDARD.md` → skip (`SKIP`). CHANGES.md missing while the standard exists → FAIL.
- R2. Malformed lines and duplicate IDs → FAIL.
- R3. Every sha in a Commit cell resolves (`git rev-parse --verify --quiet <sha>^{commit}`), else FAIL.
- R4. A commit named in a Commit cell (prefix match on the full sha) is *described by* that row, and its own `Change:` lines are ignored. Over all other commits (`git log HEAD --format=%H%x1f%B%x1e`), map ID → commits carrying `Change: ID`. Each ID present in `HEAD:docs/record/CHANGES.md` needs exactly one carrier: 0 → FAIL "no commit carries", ≥ 2 → FAIL "ID reuse". IDs that exist only in the working tree are exempt: that is the commit being made now.
- R5. A `Change:` ID that no line of the working-tree CHANGES.md lists → FAIL "unknown".
- R6. START = the oldest commit that added `docs/CODING_STANDARD.md` (`git log --diff-filter=A --format=%H -- docs/CODING_STANDARD.md`, last line). Each non-merge commit in `START..HEAD` (START excluded) whose changed files include a behaviour path must carry a `Change:` line, OR be named in a Commit cell, OR have itself added a CHANGES.md line. Otherwise FAIL. If START does not exist yet, R6 is skipped.
- R7. In each carrier's entry block, every `#<n>` on the `Verified by:` line must be a LEDGER table-1 row (`^\|\s*(\d+)\s*\|\s*20\d\d-\d\d-\d\d\s*\|`), else FAIL.
- R8. A carrier block missing a field of `FIELDS`, or listing them out of order → WARN only. The commit cannot be fixed without rewriting history.
- A slipped commit is recovered without a rewrite. Add a new CHANGES.md line whose Commit cell names the slipped sha (late entry), or, for an ID with no carrier, a later commit whose body carries `Change: CHG-nnnn (late)`.

**Hook (`tools/git-hooks/pre-commit`, full new header + order):**
```bash
#!/usr/bin/env bash
# pre-commit guard, run by git directly (core.hooksPath = tools/git-hooks; tools/sim.sh setup sets it).
# Blocks a commit when a behaviour path is staged without a new docs/record/CHANGES.md line (docs/CODING_STANDARD.md),
# when the docs checker reports a FAIL, or the host unit tests fail.
# --no-verify skips it; the docs check's change-log pass still flags a behaviour commit without a Change: line.
set -u
root=$(git rev-parse --show-toplevel)
staged=$(git diff --cached --name-only --no-renames)
[ -z "$staged" ] && exit 0
rc=0
python3 -I "$root/tools/docs_check/changes.py" hook || { echo "pre-commit: change log FAIL — docs/CODING_STANDARD.md"; rc=1; }
# … the existing docs-check block, unchanged …
# unit tests also when the sim airframe or the drone's parameter file is staged (the marker test, Task 3):
if echo "$staged" | grep -qE '^(tools/.*\.(py|sh)$|AirStack/simulation/isaac-sim/px4/airframes/|starling_1_indoor_params\.params$)'; then
# … the existing unit-test and sim.sh-check blocks, unchanged …
```
`hook` reads `git diff --cached --name-only --no-renames` itself (deletions count). The new text is `git show :docs/record/CHANGES.md` (empty if absent) and the old text is `git show HEAD:docs/record/CHANGES.md` (empty if absent). `standard_present` = `docs/CODING_STANDARD.md` is in HEAD or in the index (`git cat-file -e HEAD:…` / `git cat-file -e :…`). If the standard is absent, the hook is a no-op, so landing Task 1 alone blocks nobody.

**`install.sh` (full):**
```bash
#!/usr/bin/env bash
# Activates the versioned pre-commit guard in THIS clone: git runs tools/git-hooks/pre-commit directly (core.hooksPath),
# so there is no copy to go stale. tools/sim.sh setup runs this; tools/sim.sh doctor fails when it has not run.
set -eu
root=$(git rev-parse --show-toplevel); cd "$root"
old="$(git rev-parse --git-common-dir)/hooks/pre-commit"          # computed BEFORE hooksPath is set (git-path would follow it)
git config core.hooksPath tools/git-hooks
if [ -f "$old" ] && head -3 "$old" | grep -q 'pre-commit guard'; then rm -f "$old"; fi   # the pre-2026-11 copy
echo "pre-commit guard active: core.hooksPath = tools/git-hooks ($root)"
```

**`check_docs.py`:** after `HERE = …` add `sys.path.insert(0, str(HERE))` and `import changes as CH`. Then:
```python
def check_change_log():
    """docs/CODING_STANDARD.md: CHANGES.md IDs ↔ commits, behaviour commits carry Change:, Verified cites real LEDGER rows."""
    fails, warns, skip = CH.audit(ROOT)
    if skip:
        return Result("change-log", "SKIP", skip)
    return verdict("change-log", fails, warns, "every CHG id has one commit; behaviour commits since the standard carry Change:",
                   f"{len(fails)} change-log problem(s)")
```
Append `check_change_log` to `main()`'s `checks` list. README row: `| change-log | (from the commit that adds docs/CODING_STANDARD.md) CHANGES.md lines well-formed, unique; every CHG id carried by exactly one commit (`Change: CHG-nnnn`); no unknown ids; every behaviour commit carries a Change: line or is named by a line; `Verified by:` LEDGER rows exist; entry fields (WARN) | FAIL / WARN / SKIP |`.

- [ ] **Step 1: failing tests**: `tools/tests/test_changes.py`:

```python
# tools/tests/test_changes.py — change-logging standard: path map, pre-commit rule, git-log audit (docs/CODING_STANDARD.md)
import os, pathlib, shutil, subprocess, sys, tempfile, unittest
TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS / "docs_check"))
import changes as CH


def clean_env(**extra):
    e = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}     # a hook's GIT_DIR / GIT_INDEX_FILE must not reach the fixtures
    e.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
             GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    e.update(extra)
    return e


def git(root, *args, check=True):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, env=clean_env(), check=check)


HEAD_MD = "RECORD\n\n| ID | Date | Scope | What | Commit |\n|---|---|---|---|---|\n"
LEDGER = "| # | Date | SIM/REAL | Result | Evidence | NEAR |\n|---|---|---|---|---|---|\n| 3 | 2026-10-19 | SIM | r | e | n |\n"
def row(n, commit="this", what="x"): return f"| CHG-{n:04d} | 2026-11-02 | sim-only | {what} | {commit} |\n"
def block(n, verified="unit test", drop=None):
    lines = [f"Change: CHG-{n:04d}", "What: a -> b", "Scope: sim-only", "Why: w", "Could affect: c", "Watch for: s",
             f"Verified by: {verified}", "Revert: git revert"]
    return "\n".join(l for l in lines if not (drop and l.startswith(drop))) + "\n"


def make_repo(tmp, standard=True):
    root = pathlib.Path(tmp); git(root, "init", "-q", "-b", "main")
    (root / "docs/record").mkdir(parents=True); (root / "docs/record/LEDGER.md").write_text(LEDGER)
    paths = ["docs/record/LEDGER.md"]
    if standard:
        (root / "docs/CODING_STANDARD.md").write_text("KNOW\n"); (root / "docs/record/CHANGES.md").write_text(HEAD_MD + row(1))
        paths += ["docs/CODING_STANDARD.md", "docs/record/CHANGES.md"]
    git(root, "add", *paths); git(root, "commit", "-q", "--no-verify", "-m", "start", "-m", block(1) if standard else "x")
    return root


def commit(root, files, msg, body=""):
    for p, text in files.items():
        f = root / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(text)
    git(root, "add", *files); git(root, "commit", "-q", "--no-verify", "-m", msg, *(["-m", body] if body else []))
    return git(root, "rev-parse", "HEAD").stdout.strip()


class PathMap(unittest.TestCase):
    CASES = {"AirStack/robot/ros_ws/src/svg_ground_control/svg_ground_control/swarm_commander.py": True,
             "AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max": True,
             "AirStack/robot/ros_ws/src/svg_ground_control/config/cbf_sim.yaml": True,
             "AirStack/robot/ros_ws/src/svg_ground_control/test/test_sim_teleop_release.py": False,
             "AirStack/docs/index.md": False, "patches/0007-mavros-interface-sim-velocity-room-frame.patch": True,
             "starling_1_indoor_params.params": True, "mocap.sh": True, "mocap/motion_capture.yaml": True,
             "tools/sim.sh": True, "tools/sim_hover_step_run.sh": True, "tools/hover_step_report.py": True,
             "tools/lib/report.py": True, "tools/live/metrics_core.py": True, "tools/teleop/keymap.py": True,
             "tools/sim_tests/crossing/gates.py": True, "tools/sim_tests/crossing/fly.sh": True, "tools/sim_tests/crossing/test.env": True,
             "tools/sim_tests/crossing/plots.json": False, "tools/sim_tests/_template/gates.py": False,
             "tools/tests/test_report.py": False, "tools/docs_check/check_docs.py": False, "tools/git-hooks/pre-commit": False,
             "tools/make_figures.sh": False, "localisation/nodes/cuvslam_stereo_node.py": True, "localisation/docker/Dockerfile": True,
             "localisation/README.md": False, "docs/record/CHANGES.md": False, "README.md": False, "CLAUDE.md": False}

    def test_behaviour_paths(self):
        for p, want in self.CASES.items():
            self.assertEqual(CH.is_behaviour(p), want, p)


class Staged(unittest.TestCase):
    AF = "AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max"

    def test_airframe_without_a_changes_line_fails(self):                          # Review Focus 1
        errs, new = CH.staged_problems(HEAD_MD + row(1), HEAD_MD + row(1), [self.AF], True)
        self.assertTrue(any("without a new docs/record/CHANGES.md line" in e and "10090_pegasus_starling2max" in e for e in errs), errs)
        self.assertEqual(new, [])

    def test_new_line_passes_and_names_the_id(self):
        self.assertEqual(CH.staged_problems(HEAD_MD + row(1), HEAD_MD + row(1) + row(2), ["tools/sim.sh"], True), ([], ["CHG-0002"]))

    def test_edit_of_an_old_line_fails(self):
        errs, _ = CH.staged_problems(HEAD_MD + row(1), HEAD_MD + row(1, what="y") + row(2), ["tools/sim.sh"], True)
        self.assertTrue(any("append-only" in e for e in errs), errs)

    def test_reused_id_fails(self):                                                 # Review Focus 2
        errs, _ = CH.staged_problems(HEAD_MD + row(1), HEAD_MD + row(1) + row(1, what="other"), ["tools/sim.sh"], True)
        self.assertTrue(any("duplicate ID CHG-0001" in e for e in errs), errs)

    def test_malformed_line_fails(self):
        errs, _ = CH.staged_problems(HEAD_MD, HEAD_MD + "| CHG-12 | 2026-11-02 | sim-only | x | this |\n", ["tools/sim.sh"], True)
        self.assertTrue(any("malformed" in e for e in errs), errs)

    def test_docs_and_tests_need_nothing(self):
        self.assertEqual(CH.staged_problems(HEAD_MD + row(1), HEAD_MD + row(1), ["docs/RUNBOOK.md", "tools/tests/test_x.py"], True), ([], []))

    def test_before_the_standard_lands_nothing_is_enforced(self):
        self.assertEqual(CH.staged_problems("", "", ["tools/sim.sh"], False), ([], []))


class HookEndToEnd(unittest.TestCase):                                              # Review Focus 1 + 5, through core.hooksPath
    def _repo(self, tmp):
        root = make_repo(tmp)
        for d in ("tools/git-hooks", "tools/docs_check"): (root / d).mkdir(parents=True)
        for f in ("git-hooks/pre-commit", "git-hooks/install.sh", "docs_check/changes.py"): shutil.copy(TOOLS / f, root / "tools" / f)
        stub = root / "tools/docs_check/check_docs.sh"; stub.write_text("#!/bin/sh\necho '0 PASS · 0 WARN · 0 FAIL · 0 SKIP'\n"); stub.chmod(0o755)
        git(root, "add", "tools"); git(root, "commit", "-q", "--no-verify", "-m", "tools")
        r = subprocess.run(["bash", "tools/git-hooks/install.sh"], cwd=root, capture_output=True, text=True, env=clean_env())
        self.assertEqual(r.returncode, 0, r.stderr)
        return root

    def test_install_sets_hooks_path(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(git(self._repo(d), "config", "--get", "core.hooksPath").stdout.strip(), "tools/git-hooks")

    def test_behaviour_commit_without_entry_is_blocked_then_passes_with_one(self):
        with tempfile.TemporaryDirectory() as d:
            root = self._repo(d)
            (root / "AirStack").mkdir(); (root / "AirStack/x.py").write_text("print(1)\n"); git(root, "add", "AirStack/x.py")
            r = subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=root, capture_output=True, text=True, env=clean_env())
            self.assertNotEqual(r.returncode, 0); self.assertIn("CHANGES.md", r.stdout + r.stderr)
            (root / "docs/record/CHANGES.md").write_text(HEAD_MD + row(1) + row(2)); git(root, "add", "docs/record/CHANGES.md")
            r = subprocess.run(["git", "commit", "-q", "-m", "x", "-m", block(2)], cwd=root, capture_output=True, text=True, env=clean_env())
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class Audit(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory(); self.addCleanup(self._d.cleanup); self.root = make_repo(self._d.name)

    def fails(self): return CH.audit(self.root)[0]

    def test_no_standard_skips(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(CH.audit(make_repo(d, standard=False))[2])

    def test_clean_history_passes(self):
        self.assertEqual(CH.audit(self.root)[:2], ([], []))

    def test_no_verify_behaviour_commit_is_caught_after_the_fact(self):            # Review Focus 4
        sha = commit(self.root, {"tools/sim.sh": "echo\n"}, "sneaky")
        self.assertTrue(any(sha[:7] in f and "without a Change: line" in f for f in self.fails()), self.fails())
        commit(self.root, {"docs/record/CHANGES.md": HEAD_MD + row(1) + row(2, commit=sha[:7], what="late entry")}, "late", block(2))
        self.assertEqual(self.fails(), [])

    def test_id_carried_by_two_commits_fails(self):                                 # Review Focus 2
        commit(self.root, {"docs/record/CHANGES.md": HEAD_MD + row(1) + row(2), "tools/sim.sh": "a\n"}, "a", block(2))
        commit(self.root, {"tools/lib/x.sh": "b\n"}, "b", block(2))
        self.assertTrue(any("CHG-0002" in f and "ID reuse" in f for f in self.fails()), self.fails())

    def test_duplicate_rows_fail(self):
        commit(self.root, {"docs/record/CHANGES.md": HEAD_MD + row(1) + row(2) + row(2, what="other")}, "dup", block(2))
        self.assertTrue(any("duplicate ID CHG-0002" in f for f in self.fails()), self.fails())

    def test_unknown_id_in_a_body_fails(self):
        commit(self.root, {"tools/sim.sh": "a\n"}, "a", block(7))
        self.assertTrue(any("unknown CHG-0007" in f for f in self.fails()), self.fails())

    def test_row_without_a_commit_fails_but_a_row_being_committed_does_not(self):
        commit(self.root, {"docs/record/CHANGES.md": HEAD_MD + row(1) + row(2)}, "row only")
        (self.root / "docs/record/CHANGES.md").write_text(HEAD_MD + row(1) + row(2) + row(3))       # working tree only
        f = self.fails()
        self.assertTrue(any("CHG-0002: no commit carries" in x for x in f), f); self.assertFalse(any("CHG-0003" in x for x in f), f)

    def test_dead_ledger_citation_fails(self):
        commit(self.root, {"docs/record/CHANGES.md": HEAD_MD + row(1) + row(2), "tools/sim.sh": "a\n"}, "a", block(2, verified="run, ledger #99"))
        self.assertTrue(any("LEDGER #99" in f for f in self.fails()), self.fails())
        commit(self.root, {"docs/record/CHANGES.md": HEAD_MD + row(1) + row(2) + row(3), "tools/sim.sh": "b\n"}, "b", block(3, verified="ledger #3"))
        self.assertFalse(any("LEDGER #3, not in" in f for f in self.fails()))

    def test_commit_cell_must_name_a_commit(self):
        commit(self.root, {"docs/record/CHANGES.md": HEAD_MD + row(1) + row(2, commit="deadbee")}, "x", block(2))
        self.assertTrue(any("deadbee" in f and "not a commit" in f for f in self.fails()), self.fails())

    def test_missing_field_is_a_warning(self):
        commit(self.root, {"docs/record/CHANGES.md": HEAD_MD + row(1) + row(2), "tools/sim.sh": "a\n"}, "a", block(2, drop="Watch for:"))
        fails, warns, _ = CH.audit(self.root)
        self.assertEqual(fails, []); self.assertTrue(any("Watch for:" in w for w in warns), warns)

    def test_show_prints_the_row_and_the_entry(self):
        r = subprocess.run([sys.executable, str(TOOLS / "docs_check/changes.py"), "show", "CHG-0001"], cwd=self.root,
                           capture_output=True, text=True, env=clean_env())
        self.assertEqual(r.returncode, 0, r.stderr); self.assertIn("| CHG-0001 |", r.stdout); self.assertIn("Watch for: s", r.stdout)
        self.assertLessEqual(len(r.stdout.splitlines()), 12)

    def test_candidates_lists_uncovered_behaviour_commits(self):
        sha = commit(self.root, {"tools/live/m.py": "x\n"}, "metrics change")
        commit(self.root, {"docs/RUNBOOK.md": "x\n"}, "docs only")
        r = subprocess.run([sys.executable, str(TOOLS / "docs_check/changes.py"), "candidates", "--since", "2000-01-01 00:00"],
                           cwd=self.root, capture_output=True, text=True, env=clean_env())
        self.assertEqual(r.stdout.split(), [sha[:7], "metrics", "change"])


class HookSource(unittest.TestCase):
    def test_change_rule_runs_first_and_the_marker_test_runs_on_airframe_edits(self):
        src = (TOOLS / "git-hooks/pre-commit").read_text()
        self.assertIn('changes.py" hook', src); self.assertLess(src.index('changes.py" hook'), src.index("check_docs.sh"))
        self.assertIn("AirStack/simulation/isaac-sim/px4/airframes/", src); self.assertIn("starling_1_indoor_params", src)
```
In `tools/tests/test_check_docs.py` add:
```python
class ChangeLogCheck(unittest.TestCase):
    def setUp(self):
        self._root = C.ROOT; self.addCleanup(setattr, C, "ROOT", self._root)

    def test_skips_before_the_standard_and_fails_on_a_slipped_commit(self):
        from test_changes import make_repo, commit
        with tempfile.TemporaryDirectory() as d:
            C.ROOT = make_repo(d, standard=False); self.assertEqual(C.check_change_log().status, "SKIP")
        with tempfile.TemporaryDirectory() as d:
            C.ROOT = make_repo(d); self.assertEqual(C.check_change_log().status, "PASS")
            commit(C.ROOT, {"tools/sim.sh": "x\n"}, "slipped"); self.assertEqual(C.check_change_log().status, "FAIL")
```

- [ ] **Step 2: run**: `python3 -m unittest discover -s tools/tests -p 'test_changes.py' 2>&1 | tail -3` → `ModuleNotFoundError: No module named 'changes'` (FAILED, errors=1).
- [ ] **Step 3: implement** `changes.py` (stdlib only: `argparse, collections, os, pathlib, re, subprocess, sys`), the hook, `install.sh`, `check_change_log`, and the README row, all per Interfaces.
- [ ] **Step 4: verify**
  - `python3 -m unittest discover -s tools/tests 2>&1 | tail -3` → `OK`.
  - `tools/docs_check/check_docs.sh | grep change-log` → `[SKIP] change-log: …` (the standard has not landed yet).
  - `python3 tools/docs_check/changes.py candidates --since '2026-11-02 00:00'` lists at least `777b0c3 a9f38d3 923fbad 1c45625` (plus the yaw fix-round/Task 4 commits). Paste the list into your report: Task 2 needs it.
  - `bash tools/git-hooks/install.sh` → `pre-commit guard active: core.hooksPath = tools/git-hooks (…)`.
  - `git config --get core.hooksPath` → `tools/git-hooks`; `.git/hooks/pre-commit` is gone.
- [ ] **Step 5: commit**: no behaviour path is touched, so no entry is needed. The new hook (now active) runs on this commit.
```bash
git add tools/docs_check/changes.py tools/tests/test_changes.py
git commit -F /tmp/claude-…/msg1 -- tools/docs_check/changes.py tools/docs_check/check_docs.py tools/docs_check/README.md tools/git-hooks/pre-commit tools/git-hooks/install.sh tools/tests/test_changes.py tools/tests/test_check_docs.py
```
Message: `tools: change-log rule — pre-commit blocks a behaviour path staged without a new CHANGES.md line; docs check audits CHG ids against git log; hook runs from tools/git-hooks via core.hooksPath` + body: "Design docs/superpowers/specs/2026-11-02-change-logging-standard-design.md (P2, B4–B6). Inactive until docs/CODING_STANDARD.md lands (Task 2). Path map: changes.BEHAVIOUR/NOT_BEHAVIOUR. Tooling only, no behaviour path."

---

### Task 2: The standard, the change record and the backfill (start commit) (executor: **sonnet**)

**Files:**
- Create: `docs/CODING_STANDARD.md`, `docs/record/CHANGES.md`
- Modify: `CLAUDE.md` (docs-table row; rule 9 sentence), `docs/PREFLIGHT.md` (rule 9 sentence; line-1 date), `docs/AI_ASSIST.md` (one line), `docs/MIGRATION.md` (patch table: CHG column)
- Also stage `docs/superpowers/specs/2026-11-02-change-logging-standard-design.md` if `git status` shows it modified (the owner's approval edit).

**Interfaces consumed:** `python3 tools/docs_check/changes.py candidates|show|audit` (Task 1); the CHANGES.md format (`ROW_RE`).

- [ ] **Step 1: the backfill set.** Run `python3 tools/docs_check/changes.py candidates --since '2026-11-02 00:00'`. Each listed commit gets one entry, oldest first, from CHG-0005 up; B = the last of them. As of 2026-11-02 14:00 the list is `777b0c3` (0005), `a9f38d3` (0006), `923fbad` (0007), `1c45625` (0008), plus the yaw Task 1 fix round and Task 4 (+ fix rounds) commits that land before this task. Report B to the orchestrator.
- [ ] **Step 2: failing check.** Write `docs/CODING_STANDARD.md` (below) first, then run `tools/docs_check/check_docs.sh | grep change-log` → `[FAIL] change-log: …` (`docs/record/CHANGES.md` missing while the standard exists, rule R1).
- [ ] **Step 3: write the pages.**

`docs/CODING_STANDARD.md` (verbatim; ≤ 60 lines; check with `wc -l`):
```markdown
KNOW · SIM + REAL — how a change that can alter behaviour is logged. Read before committing code, config, parameters, launch files, sim assets, docker files or test gates. Decided by a four-hat panel on 2026-11-02 ([design](superpowers/specs/2026-11-02-change-logging-standard-design.md)).

# Coding standard: log every behaviour change

Every change that can alter how the software or the simulated drone behaves is written down once, in one shape, with the symptom that would reveal a side effect. Changes made live are logged by the tools, not from memory. One line in [record/CHANGES.md](record/CHANGES.md) and one commit answer what changed, why, what it could affect and how to undo it.

## 1. What needs an entry

| Needs an entry | Needs none |
|---|---|
| behaviour code: `AirStack/`, `tools/sim.sh`, `tools/lib/`, `tools/live/`, `tools/teleop/`, `localisation/nodes/` and `scripts/`, `mocap/` | docs (`*.md`, `docs/`) |
| yaml and other config, launch files, docker files, `patches/` | unit tests (`tools/tests/`, CMU's `test/`) |
| PX4 parameters: the sim airframe, `starling_1_indoor_params.params`, or set live | records and figures written by a run |
| sim assets and worlds; test gates (`gates.py`, `metrics.py`, `fly.sh`, `test.env` of a test) | the `_template` test |

The exact list lives in `tools/docs_check/changes.py`. `python3 tools/docs_check/changes.py is-behaviour <path>` answers for one file.

## 2. The entry

1. Take the next ID: the highest `CHG-nnnn` in CHANGES.md plus one. Parallel work gets its IDs from whoever hands it out.
2. Append one line to CHANGES.md: `| CHG-nnnn | <date> | <scope> | <what, one line> | this |`. Scope is `sim-only`, `real-drone`, `sim+real` or `tooling`. Never edit or delete a line.
3. Start the commit body with the full entry: eight fields, one line each, in this order.

| Field | Holds |
|---|---|
| `Change:` | the ID |
| `What:` | old → new, with the file or parameter names |
| `Scope:` | sim-only, real drone or both; the world and the position source |
| `Why:` | the symptom or the request, with the ledger row or record if there is one |
| `Could affect:` | named neighbours: other tests, other drones, the real-drone path, other parameters |
| `Watch for:` | the symptom of a side effect and where it would show (topic, test, ledger row) |
| `Verified by:` | what checked it at commit time: unit test, harness, offline check, or `pending: <test>` |
| `Revert:` | the exact undo: `git revert`, the old values, any restart needed |

A later LEDGER row cites the CHG ID. The entry never waits for the row. Read any entry with `python3 tools/docs_check/changes.py show CHG-nnnn`.

## 3. Live changes

- To change a PX4 parameter of a sim drone, use `tools/sim.sh param set NAME VALUE [--drone N]`. It reads the old value, sets the new one and reads it back. It writes `time · drone_N/NAME · old → new · who` to `~/flight_logs/sim/changes.log`, and to the run's `changes.log` while a `sim.sh test` runs. A test's own sweep writes through the same helper.
- Every `sim.sh test` record has a "Changes in this run" block. It holds the tools' log, PX4's own list of changed parameters from the ulog, and a start/end parameter snapshot diff. The ulog is what PX4 ran, so it wins a conflict. The snapshot catches Foxglove, QGC and `ros2 param set`.
- `tools/sim.sh down` saves any PX4 ulog not yet copied to `~/flight_logs/sim/uncollected_<date>/` before it stops Isaac. `down --force` skips that, and those logs are lost.
- A value that wins a live sweep goes into the file in its own commit, with its own entry.

## 4. The sim airframe

Every `param set-default` line of `10090_pegasus_starling2max` ends in `# = real`, `# SIM-ONLY (real <value>) CHG-nnnn` or `# SIM-ONLY (no real value) CHG-nnnn`. `tools/tests/test_airframe_markers.py` checks each line against `starling_1_indoor_params.params`.

## 5. What enforces it

| Check | Fails when |
|---|---|
| pre-commit hook (`tools/git-hooks/pre-commit`, active after `tools/sim.sh setup`) | a behaviour path is staged without a new CHANGES.md line; a line is edited or removed; an ID repeats |
| docs check `change-log` (`tools/docs_check/check_docs.sh`) | an ID has no commit or two; a commit names an unknown ID; a behaviour commit since this page carries no `Change:` line (a `--no-verify` commit); `Verified by:` cites a LEDGER row that does not exist |
| `tools/sim.sh doctor` | the hook is not active in this clone |

A commit that slipped through is fixed by a late entry: a new CHANGES.md line whose last cell names the slipped commit, plus a commit whose body carries the entry. History is never rewritten.
```

`docs/record/CHANGES.md` (header verbatim, then the lines; add one line per extra candidate from Step 1 after CHG-0008, in the same shape):
```markdown
RECORD · SIM + REAL — append-only change log ([CODING_STANDARD.md](../CODING_STANDARD.md)). One line per change. The full entry (eight fields) is in the body of the commit that carries `Change: CHG-nnnn`; read it with `python3 tools/docs_check/changes.py show CHG-nnnn`. Never edit or delete a line; correct with a new one.

# Changes

The last cell is `this` (the commit that carries the entry) or the sha(s) of older commits that the entry describes (backfilled, or a late entry for a commit that slipped through).

| ID | Date | Scope | What | Commit |
|---|---|---|---|---|
| CHG-0001 | 2026-10-30 | sim-only | patch 0006: sim teleop, released sticks park the drone (commander velocity output only); backfilled | bdc58d6 |
| CHG-0002 | 2026-10-30 | sim-only | patch 0007: sim MAVROS interface sends room-frame velocities as FRAME_LOCAL_NED (velocity_frame local); backfilled | 02cce03 |
| CHG-0003 | 2026-10-20 | sim-only | sim airframe 10090_pegasus_starling2max baseline: CMU rotor geometry, rate gains x0.5, LNDMC_ROT_MAX 300, MPC limits above the drone's; backfilled | 803385a, 15100b6, 6d40f95, 5bb4e04, 2a70731, 7032af4, d739a73 |
| CHG-0004 | 2026-10-30 | sim-only | NEAR-860: cuvslam_stereo_node.py tracker split into make_tracker()/track_frame() for the offline replay; backfilled | 1790264 |
| CHG-0005 | 2026-11-02 | sim-only | sim stack takes NUM_ROBOTS and FLY_ARGS from test.env (default 3); yaw gains in the ulog header dump; backfilled | 777b0c3 |
| CHG-0006 | 2026-11-02 | tooling | collect dumps drone_1's ulog to px4_drone_1.csv (vehicle-time yaw): ulog_yaw_dump.py, yaw_core.py; backfilled | a9f38d3 |
| CHG-0007 | 2026-11-02 | tooling | live metrics carry heading (quaternion to ENU yaw, unwrapped), yaw rate and xy drift; backfilled | 923fbad |
| CHG-0008 | 2026-11-02 | tooling | heading reads NaN on an unfilled quaternion (norm² < 0.5); backfilled | 1c45625 |
```

`CLAUDE.md` docs table: insert after the `TEST_STANDARD.md` row:
`| [CODING_STANDARD.md](docs/CODING_STANDARD.md) | **how a behaviour change is logged** — what needs an entry, the eight fields, [record/CHANGES.md](docs/record/CHANGES.md), live changes through the tools, the hook that blocks a missing entry |`

`docs/AI_ASSIST.md` §3 "How to ask so it stays safe": append one bullet:
`- Ask for the **CHG id** of any behaviour change it makes and read its "Watch for" line: every such change is logged in [record/CHANGES.md](record/CHANGES.md) ([CODING_STANDARD.md](CODING_STANDARD.md)).`

**Iron rule 9.** The edit is identical in `CLAUDE.md` and `docs/PREFLIGHT.md`; the block must stay byte-identical. Replace exactly
`(The sim airframe's attitude/position gains and MPC speed limits equal the real drone's — that direction is fine; the other is not.)`
with (verbatim, one line):
```
(The sim airframe's attitude/position gains equal the real drone's. Its MPC speed and acceleration limits are HIGHER than the drone's `starling_1_indoor_params.params`: `MPC_XY_VEL_MAX` 20 vs 3 m/s, `MPC_ACC_HOR` 6 vs 3 m/s², `MPC_ACC_HOR_MAX` 1000 vs 3 m/s², `MPC_Z_VEL_MAX_UP` 10 vs 2 m/s, `MPC_Z_VEL_MAX_DN` 4 vs 0.6 m/s — a sim run can fly faster than the drone will, until a later entry in `docs/record/CHANGES.md` matches them.)
```
Use no links inside the block: CLAUDE.md and PREFLIGHT.md sit in different folders. Then bump PREFLIGHT line 1 `v2026-10-29` → `v<today>`. Change nothing else in either block, including the PREFLIGHT bullet "the drone's PX4 limits allow 20 m/s" (see Owner must know).

`docs/MIGRATION.md` patch table (inside `<details>` "Patches — bug fixes…"): header `| Patch file | CHG | Bug it fixes | Symptom without the fix | Status on \`yikuan/SVG_ground_control_dev\` |`, separator with 5 cells. CHG cells: 0001/0002/0003 `—`, 0006 `CHG-0001`, 0007 `CHG-0002`. Under the table add one sentence: `CHG = the entry in [record/CHANGES.md](record/CHANGES.md); patches before 2026-10-30 predate the standard (—).`

- [ ] **Step 4: the commit body**: a short intro paragraph, then one block per backfilled ID. The `Change:` line reads `Change: CHG-nnnn (backfilled from <sha>)`, and every field is on one line. Blocks 0001–0008 (verbatim; write the extra candidates' blocks from each commit's own "CHANGE LOG" section in the same shape, with `#n` on a `Verified by:` line only for rows that exist in LEDGER table 1):

```
Change: CHG-0001 (backfilled from bdc58d6)
What: swarm_commander.py velocity output (sim drones): teleop reference and stick ramp follow the stick part only (teleop_feedforward / teleop_stick_published) instead of the full published command; patches/0006-swarm-commander-sim-teleop-release-swing.patch
Scope: sim-only (Isaac + Pegasus, MAVROS velocity output, any world, PX4 sim state estimate). Real-mode drones (trajectory output) publish commands identical to CMU's.
Why: after one stick push a sim drone kept swinging at 1–2 m/s inside the teleop fence (Isaac 2026-10-30, flat world and construction site).
Could affect: every sim teleop flight (keyboard, gamepad), the yaw-step test (it drives the teleop input), CMU's ramp test (pinned to the trajectory output, sim twin added), the real-drone trajectory route if the output selection were ever wrong.
Watch for: creep or swing after stick release in sim teleop; a released stick that no longer holds position; any real-mode command differing from CMU's (test_sim_teleop_release.py).
Verified by: test/test_sim_teleop_release.py failed before (0.22 and 1.72 m/s after release) and passes after; CMU suite 192/192; pending: hand-flown sim teleop with video.
Revert: git revert bdc58d6 (or reverse-apply patches/0006); restart the commander.

Change: CHG-0002 (backfilled from 02cce03)
What: mavros_interface.cpp velocity frame FRAME_BODY_NED -> new parameter velocity_frame (body = CMU default, local = FRAME_LOCAL_NED), interface.launch.py sets local; patches/0007-mavros-interface-sim-velocity-room-frame.patch
Scope: sim-only (the MAVROS route; real drones never start MAVROS, they use px4_interface over DDS); any world.
Why: a sim drone turned with yaw orbited instead of holding or moving straight: every room-frame command was rotated by its heading.
Could affect: every sim flight that moves while yawed (teleop turns, goals after a yaw, the crossing if headings drift); the yaw-rate sign (ENU 0.3 -> NED -0.3); the yaw ring the yaw-step test chases became visible once the orbit stopped.
Watch for: a forward tap after a 90 deg turn not along room +x (yaw_step patch-0007 INFO row); yaw rate sign reversed; heading ring after a yaw key (NEAR-789).
Verified by: fake FCU behind the real MAVROS: ENU (1, 0, 0.5) yaw_rate 0.3 -> SET_POSITION_TARGET_LOCAL_NED frame 1, (0, 1, -0.5), yaw_rate -0.3; pending: yaw_step tap check.
Revert: git revert 02cce03 (or velocity_frame body in interface.launch.py); rebuild mavros_interface and restart the interfaces.

Change: CHG-0003 (backfilled from 803385a 15100b6 6d40f95 5bb4e04 2a70731 7032af4 d739a73)
What: sim airframe 10090_pegasus_starling2max vs rc.mc_defaults (Iris): CMU sys-ID rotor geometry CA_ROTOR0-3 PX ±0.095, PY ±0.13, KM ±0.0136 (drone 0.085 / 0.0625 / 0.05); the drone's attitude/position gains; MC_ROLLRATE_P/I/D 0.032/0.05/0.00065 and MC_PITCHRATE_P/I/D 0.032/0.048/0.00055 (x0.5 of the drone's); IMU_GYRO_CUTOFF 80, IMU_DGYRO_CUTOFF 40 (= the drone's); LNDMC_ROT_MAX 300 (drone 30); MPC_XY_VEL_MAX 20, MPC_ACC_HOR 6, MPC_ACC_HOR_MAX 1000, MPC_Z_VEL_MAX_UP 10, MPC_Z_VEL_MAX_DN 4 (starling_1_indoor_params.params 3 / 3 / 3 / 2 / 0.6; the 2026-08-20 drone backup ~/RCC_Starling_1 reads 20 / 6 / 1000 / 10 / 4); PWM_MAIN_FUNC1-4 101-104; 7032af4 also rebuilt the Starling USD asset.
Scope: sim-only (Isaac + Pegasus PX4 SITL, every world, sim position source). The drone's parameters come from starling_1_indoor_params.params / QGC only (iron rule 9).
Why: Iris defaults oscillated and ran away (10-19); 9 Hz pitch limit cycle on the drone's rate gains (ledger #10); floor rocking blocked the land detector (#9); the sim clipped at 3 m/s on CMU's 2-6 m/s legs (#12).
Could affect: every sim test (hover/steps #17-#19, crossing #20-#22, teleop, yaw-step); yaw left at the drone's gains while roll/pitch were halved (suspected heading ring, NEAR-789); landing detection; sim speeds above the drone's file (crossing min distance 1.02 m at #4 before d739a73, 0.95-1.00 m at #20-#22 after; not yet separated from the other 10-20 changes).
Watch for: heading ring after a yaw input; roll/pitch rate std > 0.4 deg/s in hover; DISARM denied after landing; speeds above 3 m/s in a test meant to match the drone.
Verified by: ledger #1, #3, #4, #9, #10, #13.
Revert: per line, the real value named in its marker (docs/CODING_STANDARD.md §4); restart Isaac so the airframe reloads. Never by copying values to the drone.

Change: CHG-0004 (backfilled from 1790264)
What: localisation/nodes/cuvslam_stereo_node.py tracker set-up and per-frame tracking extracted into make_tracker()/track_frame() (node behaviour unchanged); new replay_offline.py, replay_bag.sh, compare_replay.py, make_synthetic_stereo_bag.py, replay_selftest.sh; record_sim_bag.sh records left/right image_rect + right camera_info (zstd mcap).
Scope: sim-only (camera-world exploration, cuVSLAM in the exploration container; nothing flies on it).
Why: replay a flight offline through the live node's code (NEAR-860).
Could affect: the live cuVSLAM path of camera-world runs (ledger #15, #16); bag size and disk use of record_sim_bag.sh; anything importing the node.
Watch for: live poses differing from the replay of the same bag; APE on a repeat of #16 drifting from 0.081 m; recording dropping frames.
Verified by: same 39 frames gave identical poses before and after; replay_selftest.sh 500/500 tracked, identical twice, 0.013 m vs truth; tools/tests/test_compare_replay.py.
Revert: git revert 1790264.

Change: CHG-0005 (backfilled from 777b0c3)
What: tools/lib/stack.sh + tools/sim.sh: literal 3 drones -> NUM_ROBOTS (default 3), DRONE_IDS, SYSIDS through Isaac, interfaces, readiness, landing poll and copy_ulogs; fly.sh receives FLY_ARGS from test.env; PARAM_KEYS + MC_YAW_P, MC_YAWRATE_P/I/D/K; report.py helpers take n (default 3); doctor gains a pyulog line.
Scope: sim-only (the sim stack: every sim.sh test and the hover driver, which sources stack.sh).
Why: one-drone tests (teleop_single.yaml, the yaw-step test, NEAR-789) need NUM_ROBOTS=1.
Could affect: the crossing test and the hover driver (commands identical at 3); params_ulog.txt of every run (+5 lines); readers of run_meta.txt.
Watch for: a 3-drone run spawning or polling a different count; armed_post.txt not holding NUM_ROBOTS lines.
Verified by: test_default_is_three_drones, test_num_robots_1_everywhere, test_land_wait_polls_only_the_spawned_drones, OneDroneRows; not run in a live session.
Revert: git revert 777b0c3.

Change: CHG-0006 (backfilled from a9f38d3)
What: sim.sh cmd_test collect gains yaw_dump (host pyulog, isaac-sim fallback): ~/flight_logs/sim/<run>/px4_drone_1.csv + docs/record/<run>/px4_param_changes.txt; new tools/live/ulog_yaw_dump.py and yaw_core.py.
Scope: tooling (every sim.sh test run's collect step; no flight behaviour).
Why: heading gates need PX4 vehicle time (the sim ran 0.36x and 1.32x real time, #17-#19).
Could affect: every sim.sh test (crossing: one more file, about 1 s, a caveat when the drone_1 ulog is missing); the yaw-step gates.
Watch for: "retrying inside isaac-sim" in run.log on a host with pyulog; a new caveat in crossing records; collect slower.
Verified by: test_collect_dumps_the_yaw_csv_with_a_container_fallback, test_yaw_dump_fails_closed_without_a_ulog_or_a_container, test_yaw_core (real sim_crossing_run2 ulog: 15232 rows); not run live.
Revert: delete the yaw_dump "$U1" line in cmd_test, or git revert a9f38d3.

Change: CHG-0007 (backfilled from 923fbad)
What: metrics_core Frame gains yaw, yaw_rate, yaw_unwrapped, start_yaw; Tracker.update_odom takes the quaternion and angular z; new heading helpers; metrics_node and bag_recompute pass orientation; the 1 Hz status line comes from M.status_text.
Scope: tooling (live metrics, bag recompute, figures; no flight behaviour).
Why: the yaw-step test needs heading live and in the bag recompute (NEAR-789).
Could affect: the crossing's live CSV, its bag cross-check and its status line (byte-identical by test).
Watch for: crossing status line or metrics.csv columns changing; live vs bag cross-check failing.
Verified by: test_metrics_core Heading.*, StatusText.test_crossing_status_line_is_unchanged, test_crossing_rows_unchanged_by_orientation; not run in the container.
Revert: git revert 923fbad.

Change: CHG-0008 (backfilled from 1c45625)
What: Tracker.update_odom: a quaternion with norm² < 0.5 (QUAT_MIN_NORM2) is treated as no quaternion (heading NaN).
Scope: tooling.
Why: review fix: an unfilled quaternion must not read as heading 0.
Could affect: the heading series of any test fed an unnormalised orientation.
Watch for: heading_rel_deg all NaN on the first yaw_step run.
Verified by: Heading.test_unfilled_quaternion_gives_nan_heading (failed before the fix).
Revert: git revert 1c45625.
```
- [ ] **Step 5: verify**
  - `wc -l docs/CODING_STANDARD.md` → ≤ 60.
  - `tools/docs_check/check_docs.sh | tail -1` → `… 0 FAIL …`. `iron-rules` PASS; `preflight-date` PASS with the new token; `change-log` PASS. Before the commit R4 exempts the new IDs; after it they are carried.
  - Commit (Step 6), then rerun: `change-log` PASS.
  - `python3 tools/docs_check/changes.py show CHG-0002` → the CHANGES line plus 8 lines.
  - `python3 tools/docs_check/changes.py candidates --since '2026-11-02 00:00'` → empty: every candidate is now named by a line.
- [ ] **Step 6: commit**: subject `docs: change-logging standard — CODING_STANDARD.md, record/CHANGES.md with CHG-0001…CHG-<B> backfilled, iron rule 9's MPC sentence corrected (owner OK 2026-11-02)`; body = the intro paragraph (design link; "no behaviour path in this commit; it is the standard's start commit") + the blocks. Paths: the six pages, CHANGES.md, the spec if modified. `git commit -F <msg> -- <paths>`.
- [ ] **Step 7 (orchestrator, not the executor): newcomer acceptance.** Dispatch `panel-newcomer-reader` with the design's two questions ("What changed in the sim airframe gains, and what could it affect?", "What did patch 0007 change and what could it break?"). Each must be answered from CHANGES.md plus `changes.py show` in ≤ 25 lines, including "could affect" and "watch for". A miss goes back to this task.

---

### Task 3: Airframe markers + the comparison test (executor: **sonnet**; ID CHG-<B+1>)

**Files:**
- Create: `tools/lib/airframe_params.py`, `tools/tests/test_airframe_markers.py`
- Modify: `AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max` (comments and markers only; no value changes), `docs/record/CHANGES.md` (one line)

**Interfaces produced (Task 6 uses them):**
- `AIRFRAME = "AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max"`, `REAL_PARAMS = "starling_1_indoor_params.params"`, `REPO = Path(__file__).resolve().parents[2]`
- `parse_real(text) -> dict[str, float]`: tab-separated, `#` and blank lines skipped, `float(value)`.
- `parse_airframe(text) -> list[Line]`: `Line(no, name, value: float, marker: "real"|"sim"|"sim-noreal"|None, real: float|None, chg: str|None)`. It matches `^\s*param set-default\s+(\S+)\s+(\S+)` and reads the marker at the END of the line: `#\s*= real\s*$` | `# SIM-ONLY \(real (\S+)\) (CHG-\d{4})\s*$` | `# SIM-ONLY \(no real value\) (CHG-\d{4})\s*$`.
- `same(a, b) -> bool`: `abs(a - b) <= 1e-6 * max(abs(a), abs(b))` (so 0 == 0).
- `changes_ids(text) -> set[str]`: `^\| (CHG-\d{4}) \|` lines.
- `check_markers(airframe_text, real: dict, known_ids: set) -> list[str]`. One error per bad line, naming the line number, the name, and both values where relevant:
  - no marker;
  - `= real` on a name the drone lacks, or on a value that differs (`same` is False);
  - `SIM-ONLY (real v)` on a name the drone lacks, or `v` ≠ the drone's value, or the value equals the drone's (then it must be `= real`, B2);
  - `SIM-ONLY (no real value)` on a name the drone has;
  - an unknown CHG id.
- `python3 tools/lib/airframe_params.py --check` (prints errors, exit 1) and `--table` (name, sim value, real value, marker), for a reviewer.

**The 48 markers (from the 2026-11-02 comparison; the test is the arbiter):**
- `# = real` (20): CA_AIRFRAME, CA_ROTOR_COUNT, MPC_THR_HOVER, MC_ROLLRATE_K, MC_PITCHRATE_K, IMU_GYRO_CUTOFF, IMU_DGYRO_CUTOFF, MC_YAWRATE_P, MC_YAWRATE_I, MC_YAWRATE_D, MC_YAWRATE_K, MC_ROLL_P, MC_PITCH_P, MC_YAW_P, MPC_XY_P, MPC_Z_P, MPC_XY_VEL_P_ACC, MPC_Z_VEL_P_ACC, MPC_JERK_AUTO, THR_MDL_FAC.
- `# SIM-ONLY (real <v>) CHG-0003` (24): CA_ROTOR0_PX 0.085, CA_ROTOR0_PY 0.0625, CA_ROTOR0_KM 0.05, CA_ROTOR1_PX -0.085, CA_ROTOR1_PY -0.0625, CA_ROTOR1_KM 0.05, CA_ROTOR2_PX 0.085, CA_ROTOR2_PY -0.0625, CA_ROTOR2_KM -0.05, CA_ROTOR3_PX -0.085, CA_ROTOR3_PY 0.0625, CA_ROTOR3_KM -0.05, MC_ROLLRATE_P 0.064, MC_ROLLRATE_I 0.1, MC_ROLLRATE_D 0.0013, MC_PITCHRATE_P 0.064, MC_PITCHRATE_I 0.096, MC_PITCHRATE_D 0.0011, MPC_XY_VEL_MAX 3, MPC_ACC_HOR 3, MPC_ACC_HOR_MAX 3, MPC_Z_VEL_MAX_UP 2, MPC_Z_VEL_MAX_DN 0.6, LNDMC_ROT_MAX 30.
- `# SIM-ONLY (no real value) CHG-0003` (4): PWM_MAIN_FUNC1-4.
- Comment fixes:
  - Move MPC_THR_HOVER's trailing note onto its own `#` line above it; the line then ends `   # = real`.
  - Replace the outer-loop comment ("Outer-loop limits = the REAL Starling 1's parameter set (~/RCC_Starling_1 backup)…") with: `# Outer-loop limits: the 2026-08-20 drone backup (~/RCC_Starling_1), so the sim can fly CMU's 2-6 m/s legs (2026-10-20). NOT the drone's parameter file (starling_1_indoor_params.params: 3 / 3 / 3 / 2 / 0.6) — SIM-ONLY until a CHANGES entry matches them (owner OK 2026-11-02, after the yaw retune).`
  - Leave every value byte-identical.

- [ ] **Step 1: failing tests**: `tools/tests/test_airframe_markers.py`:
```python
# tools/tests/test_airframe_markers.py — every sim-airframe line is labelled = real / SIM-ONLY and the label is true (CODING_STANDARD §4)
import pathlib, sys, unittest
TOOLS = pathlib.Path(__file__).resolve().parents[1]; REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS / "lib"))
import airframe_params as A

REAL = "# Onboard parameters\n1\t1\tMC_ROLLRATE_P\t0.064\t9\n1\t1\tLNDMC_ROT_MAX\t3e+01\t9\n1\t1\tMC_YAW_P\t2.8\t9\n"
def check(*lines): return A.check_markers("\n".join(lines) + "\n", A.parse_real(REAL), {"CHG-0003"})

class Markers(unittest.TestCase):
    def test_the_repo_airframe_is_fully_marked_and_true(self):
        errs = A.check_markers((REPO / A.AIRFRAME).read_text(), A.parse_real((REPO / A.REAL_PARAMS).read_text()),
                               A.changes_ids((REPO / "docs/record/CHANGES.md").read_text()))
        self.assertEqual(errs, [])
    def test_all_48_lines_carry_a_marker(self):
        lines = A.parse_airframe((REPO / A.AIRFRAME).read_text())
        self.assertEqual(len(lines), 48); self.assertTrue(all(l.marker for l in lines), [l.name for l in lines if not l.marker])
    def test_real_values_parse_as_floats(self):
        self.assertEqual(A.parse_real(REAL)["LNDMC_ROT_MAX"], 30.0)
    def test_unmarked_line_fails(self):
        self.assertTrue(any("MC_YAW_P" in e and "no marker" in e for e in check("param set-default MC_YAW_P 2.8")))
    def test_equal_real_passes_and_differing_real_fails(self):
        self.assertEqual(check("param set-default MC_YAW_P 2.8   # = real"), [])
        self.assertTrue(any("MC_YAW_P" in e and "2.8" in e for e in check("param set-default MC_YAW_P 2.0 # = real")))
    def test_sim_only_with_the_wrong_real_value_fails(self):                        # Review Focus 3
        self.assertEqual(check("param set-default LNDMC_ROT_MAX 300.0 # SIM-ONLY (real 30) CHG-0003"), [])
        e = check("param set-default LNDMC_ROT_MAX 300.0 # SIM-ONLY (real 20) CHG-0003")
        self.assertTrue(any("LNDMC_ROT_MAX" in x and "20" in x and "30" in x for x in e), e)
    def test_sim_only_on_an_equal_value_must_say_real(self):
        self.assertTrue(any("= real" in e for e in check("param set-default MC_YAW_P 2.8 # SIM-ONLY (real 2.8) CHG-0003")))
    def test_no_real_value_only_for_names_the_drone_lacks(self):
        self.assertEqual(check("param set-default PWM_MAIN_FUNC1 101 # SIM-ONLY (no real value) CHG-0003"), [])
        self.assertTrue(check("param set-default MC_YAW_P 9 # SIM-ONLY (no real value) CHG-0003"))
        self.assertTrue(check("param set-default PWM_MAIN_FUNC1 101 # = real"))
    def test_unknown_change_id_fails(self):
        self.assertTrue(any("CHG-0999" in e for e in check("param set-default LNDMC_ROT_MAX 300.0 # SIM-ONLY (real 30) CHG-0999")))
    def test_marker_must_end_the_line(self):
        self.assertTrue(check("param set-default MC_YAW_P 2.8 # = real, as on the drone"))
```
- [ ] **Step 2: run**: `python3 -m unittest discover -s tools/tests -p 'test_airframe_markers.py' 2>&1 | tail -3` → `ModuleNotFoundError: No module named 'airframe_params'`.
- [ ] **Step 3: implement** the module, then edit the airframe.
- [ ] **Step 4: verify**
  - Full suite `OK`.
  - Values unchanged: `git diff -U0 HEAD -- AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max | grep -E '^[-+]param' | cut -c2- | sed -E 's/[[:space:]]*#.*$//' | sort | uniq -u` → prints nothing.
  - `python3 tools/lib/airframe_params.py --check` → exit 0.
- [ ] **Step 5: commit**: append the line `| CHG-<B+1> | <date> | sim-only | sim airframe: every param set-default line marked = real / SIM-ONLY (real value) with its CHG id; outer-loop comment corrected; no value changed | this |`; paths = the four files. Message:
```
sim airframe: every param set-default line marked = real / SIM-ONLY (real <v>) CHG-0003, checked against the drone's file; no value changed

Change: CHG-<B+1>
What: 10090_pegasus_starling2max: 48 param set-default lines gain an end-of-line marker (20 "= real", 24 "SIM-ONLY (real <v>) CHG-0003", 4 "SIM-ONLY (no real value) CHG-0003"); MPC_THR_HOVER's trailing note moved above it; the outer-loop comment now says the MPC limits are the 2026-08-20 drone backup, not starling_1_indoor_params.params (3 / 3 / 3 / 2 / 0.6). No value changed. New tools/lib/airframe_params.py, tools/tests/test_airframe_markers.py; the hook runs the unit tests when the airframe or the drone's file is staged.
Scope: sim-only (Isaac + Pegasus PX4 SITL, every world). The real drone is untouched.
Why: docs/CODING_STANDARD.md §4: sim-only values readable as sim-only on every line, checked against the drone's file (design P5, B1-B3).
Could affect: how PX4 SITL reads the airframe at start (trailing comments; MPC_THR_HOVER's existing one is in force), the yaw_step booted-gains regex, the yaw plan's Task 5 edit (its lines must become SIM-ONLY with their own CHG id).
Watch for: params_ulog.txt of the next run not showing MC_PITCHRATE_P 0.032, LNDMC_ROT_MAX 300, MPC_XY_VEL_MAX 20, MPC_THR_HOVER 0.165; "Unknown model" in isaac.log.
Verified by: tools/tests/test_airframe_markers.py; git diff shows comment-only changes; pending: the next sim run's params_ulog.txt.
Revert: git revert <this commit>.
```

---

### Task 4: `sim.sh down` saves uncopied ulogs; `doctor` checks the hook (executor: **opus**; ID CHG-<B+2>)

**Files:** Modify `tools/sim.sh` (`hook_check`, `cmd_setup`, `already_copied`, `ulog_guard`, the `down)` dispatch, usage text), `tools/tests/test_sim_sh.py` (new classes `UlogGuard`, `HookCheck`), `docs/record/CHANGES.md` (one line).

**Interfaces produced:**
- `hook_check()`, defined after `bad()` and before the `# cmd_setup: idempotent preparation` comment. Prints `ok "pre-commit hook active (core.hooksPath = <v>)"` when `git -C "$REPO" config --get core.hooksPath` is `tools/git-hooks` or `$REPO/tools/git-hooks`. Otherwise `bad "pre-commit hook NOT active in this clone (core.hooksPath='<v>') — run: tools/sim.sh setup   (or: git config core.hooksPath tools/git-hooks)"`.
- `cmd_setup`: replace the existing `.git/hooks` block with: (not DRY) `bash "$REPO/tools/git-hooks/install.sh" >/dev/null || bad "hook install failed"`; then, always, `hook_check`. The `cmp -s` copy check is removed.
- `already_copied <basename> <size>`: 0 if `find "$HOME/flight_logs/sim" -name "*$1" -size "${2}c"` finds a file. Test runs name copies `drone_<n>_sysid<s>_<basename>`; the guard's own copies are named `tmpX_<date>_<basename>`.
- `ulog_guard [--force]`, defined right after `already_copied`, both just above the `# ----…---- setup / doctor / check` comment line:
  - `--force`: `say "down --force: PX4 ulogs NOT copied — any uncollected log is lost when Isaac stops"; return 0` (no docker call).
  - Otherwise: if `docker exec "$I" true` fails → `say "ulog guard: isaac container not running — no ulogs to save"; return 0`.
  - List: `docker exec "$I" bash -c 'for f in /tmp/tmp*/log/*/*.ulg; do [ -f "$f" ] && echo "$f $(stat -c %s "$f")"; done'`.
  - For each file not `already_copied`: `docker cp "$I:$f" "$dst/<tmpdir>_<datedir>_<basename>"`, where `dst=$HOME/flight_logs/sim/uncollected_$(date +%F)`. The copy is good when its size ≥ the listed size.
  - Any failure → `say "ulog guard: copy FAILED for <f> — Isaac NOT stopped. Retry, or: tools/sim.sh down --force (the uncopied logs are lost)"; return 1`.
  - Success → `say "ulog guard: saved N PX4 ulog(s) to <dst> (M already under ~/flight_logs/sim)"`.
- `down)` dispatch: parse args (only `--force`; anything else → `usage_line >&2; echo "error: down takes no arguments except --force (got $a)" >&2; exit 2`), then `HEADLESS=false; stack_env; PHASE=down; ulog_guard ${FORCE:+--force} || exit 1; touch "$OUT/ulogs_copied.ok"; down`. The `.ok` keeps `down()` from copying the same logs again into `_stack`.
- Usage: `down [--force]   stop the sim stack (first saves uncopied PX4 ulogs; --force skips that)`, in `usage()` and in the header comment.

- [ ] **Step 1: failing tests** (append to `tools/tests/test_sim_sh.py`):
```python
class UlogGuard(unittest.TestCase):
    """bare `sim.sh down` saves every PX4 ulog no run folder holds before Isaac stops (design B9)."""
    FAKE = ('#!/bin/sh\necho "$@" >> "$FAKE_LOG"\ncase "$1" in\n'
            '  exec) case "$*" in *"/tmp/tmp*/log/"*) printf "%s\\n" "/tmp/tmpA/log/2026-11-02/10_00_00.ulg 100" "/tmp/tmpB/log/2026-11-02/10_00_00.ulg 200";; esac; exit 0;;\n'
            '  cp) [ -n "$FAIL_CP" ] && exit 1; case "$2" in *tmpA*) n=100;; *) n=200;; esac; head -c $n /dev/zero > "$3"; exit 0;;\n'
            'esac\nexit 0\n')

    def _run(self, tmp, arg="", fail_cp=""):
        src = SIM.read_text()
        fn = src[src.index("already_copied() {"):src.index("# ----------------------------------------------------------------------------------------------- setup / doctor / check")]
        b = os.path.join(tmp, "bin"); os.makedirs(b); open(os.path.join(b, "docker"), "w").write(self.FAKE); os.chmod(os.path.join(b, "docker"), 0o755)
        home = os.path.join(tmp, "home"); prev = os.path.join(home, "flight_logs/sim/run1"); os.makedirs(prev)
        open(os.path.join(prev, "drone_1_sysid2_10_00_00.ulg"), "wb").write(b"\0" * 100)      # tmpA's log: a test run already holds it
        log = os.path.join(tmp, "docker.log")
        env = guarded_env(dict(os.environ, HOME=home, PATH=b + ":" + os.environ["PATH"], FAKE_LOG=log, FAIL_CP=fail_cp))
        r = subprocess.run(["bash", "-c", 'say(){ echo "SAY $*"; }; I=isaac-sim; ' + fn + f"\nulog_guard {arg}; echo rc=$?"],
                           capture_output=True, text=True, timeout=20, env=env)
        return r, home, (open(log).read() if os.path.exists(log) else "")

    def test_copies_only_what_no_run_folder_holds(self):
        with tempfile.TemporaryDirectory() as tmp:
            r, home, calls = self._run(tmp)
            self.assertIn("rc=0", r.stdout, r.stdout + r.stderr)
            saved = list(pathlib.Path(home, "flight_logs/sim").glob("uncollected_*/*.ulg"))
            self.assertEqual([p.name for p in saved], ["tmpB_2026-11-02_10_00_00.ulg"]); self.assertEqual(saved[0].stat().st_size, 200)
            self.assertNotIn("tmpA", "".join(l for l in calls.splitlines() if l.startswith("cp ")))

    def test_a_failed_copy_refuses_and_names_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            r, _, _ = self._run(tmp, fail_cp="1")
            self.assertIn("rc=1", r.stdout); self.assertIn("Isaac NOT stopped", r.stdout); self.assertIn("--force", r.stdout)

    def test_force_copies_nothing_and_says_the_logs_are_lost(self):
        with tempfile.TemporaryDirectory() as tmp:
            r, _, calls = self._run(tmp, arg="--force")
            self.assertIn("rc=0", r.stdout); self.assertIn("lost", r.stdout); self.assertEqual(calls, "")

    def test_bare_down_runs_the_guard_before_down(self):
        src = SIM.read_text(); seg = src[src.index("  down)"):src.index("  status)")]
        self.assertIn("ulog_guard", seg); self.assertLess(seg.index("ulog_guard"), seg.rindex("down"))
        self.assertIn("--force", seg); self.assertIn("ulogs_copied.ok", seg)


class HookCheck(unittest.TestCase):
    """doctor fails on a clone where git would not run the versioned hook (design B4)."""
    def _run(self, configured):
        from test_changes import clean_env, git
        src = SIM.read_text(); fn = src[src.index("hook_check() {"):src.index("# cmd_setup: idempotent preparation")]
        with tempfile.TemporaryDirectory() as d:
            git(d, "init", "-q")
            if configured: git(d, "config", "core.hooksPath", "tools/git-hooks")
            body = 'ok(){ echo "OK $*"; }; bad(){ echo "FAIL $*"; }; ' + fn + f"\nREPO={d}; hook_check"
            return subprocess.run(["bash", "-c", body], capture_output=True, text=True, env=clean_env()).stdout

    def test_fresh_clone_fails(self):                                              # Review Focus 5
        out = self._run(False); self.assertIn("FAIL", out); self.assertIn("tools/sim.sh setup", out)

    def test_configured_clone_is_ok(self):
        self.assertIn("OK", self._run(True))

    def test_setup_installs_then_checks(self):
        src = SIM.read_text(); body = src[src.index("cmd_setup() {"):src.index("cmd_doctor()")]
        self.assertLess(body.index("git-hooks/install.sh"), body.index("hook_check"))
        self.assertNotIn('cmp -s "$REPO/tools/git-hooks/pre-commit"', body)
```
- [ ] **Step 2: run**: `python3 -m unittest discover -s tools/tests -p 'test_sim_sh.py' 2>&1 | tail -3` → the new tests fail with `ValueError: substring not found`.
- [ ] **Step 3: implement** per Interfaces. Keep `test_sim_sh_rejects_bad_flags`' case `(["down", "x"], "takes no arguments")` passing.
- [ ] **Step 4: verify**
  - Full suite `OK`.
  - `bash -n tools/sim.sh`.
  - `tools/sim.sh 2>&1 | grep -- 'down \[--force\]'`.
  - `tools/sim.sh down x; echo $?` → `error: down takes no arguments except --force (got x)`, `2`.
- [ ] **Step 5: commit**: line `| CHG-<B+2> | <date> | sim-only | sim.sh down saves uncopied PX4 ulogs to ~/flight_logs/sim/uncollected_<date>/ before Isaac stops (--force skips); doctor fails without core.hooksPath | this |`. Message:
```
tools: sim.sh down saves every uncopied PX4 ulog before it stops Isaac (--force skips); doctor fails when the pre-commit hook is not active

Change: CHG-<B+2>
What: tools/sim.sh: bare `down` -> ulog_guard first (each /tmp/tmp*/log/*/*.ulg in isaac-sim not already under ~/flight_logs/sim/ is copied to ~/flight_logs/sim/uncollected_<date>/<tmpdir>_<date>_<time>.ulg; a failed copy stops nothing and exits 1; `down --force` skips the copy); setup/doctor: the .git/hooks copy check -> hook_check (core.hooksPath = tools/git-hooks, FAIL otherwise).
Scope: sim-only (the bare tools/sim.sh down and doctor/setup; sim.sh test runs keep their collect step).
Why: PX4 logs of the 2026-10-30 sessions were lost when the containers went down; the hook must be active on every clone (design B4, B9).
Could affect: every bare `sim.sh down` (slower by the copy; refuses when docker cp fails); disk use under ~/flight_logs/sim; doctor's exit code on any clone without the hook (the mirror clone, a fresh laptop).
Watch for: `down` refusing with "copy FAILED"; uncollected_<date>/ growing every session; doctor FAIL where setup was never run.
Verified by: tools/tests/test_sim_sh.py UlogGuard, HookCheck (fake docker, throwaway HOME); pending: owner session check.
Revert: git revert <this commit>.
```

---

### Task 5: The one formatter, the container helper and `sim.sh param set` (executor: **opus**; ID CHG-<B+3>)

**Files:** Create `tools/lib/changes_log.py`, `tools/lib/px4_param_set.sh`, `tools/tests/test_changes_log.py`; modify `tools/sim.sh` (`cmd_param`, dispatch, usage), `tools/tests/test_sim_sh.py` (class `ParamSet`; add `"param"` to `test_no_args_prints_usage_exit_2`'s list), `docs/record/CHANGES.md`.

**Read first:** yaw Task 4's commit message and `tools/sim_tests/yaw_step/fly.sh`. They state what step 0 settled about U1/U2 (ParamSetV2 fields; whether `ros2 param set` reaches PX4). If they settled it, use that mechanism as the helper's primary; otherwise implement the order below.

**Interfaces produced:**
- `changes_log.py` (stdlib only for these; PyYAML and pyulog are imported lazily in Task 6's subcommands):
  - `format_line(target, name, old, new, who, when=None, mismatch=None) -> str` = `f"{when} · {target}/{name} · {old} → {new} · {who}"`, plus `f" · MISMATCH requested {mismatch}"` when `mismatch` is set. `when` defaults to `datetime.now().astimezone().isoformat(timespec="seconds")`.
  - `parse_line(s) -> dict | None` (keys `time target name old new who mismatch`).
  - `same(a, b) -> bool` (numeric, rel 1e-6; strings that are not numbers compare equal only when identical).
  - CLI `line --target T --name N --old O --new V --who W [--mismatch R]` prints the line; `same A B` exits 0 or 1.
- `px4_param_set.sh <drone_n> <NAME> <VALUE> <who> <log>` runs INSIDE the robot container and is copied next to `changes_log.py`. Validation: `drone_n` `^[1-9]$`, NAME `^[A-Z][A-Z0-9_]{0,15}$`, VALUE `^-?[0-9]+(\.[0-9]*)?([eE][-+]?[0-9]+)?$`, who `^[A-Za-z0-9_.@:+-]+$`; bad → exit 2. Steps:
  1. `P=/drone_$n/interface/mavros/param`; `ros2 param get $P NAME` → kind (`Double`/`Integer`) and old value. Nothing returned → exit 3 with `px4_param_set: $P has no NAME (sim stack up? name right?)`.
  2. Integer + non-integer VALUE → exit 2. Double + VALUE without `.`/`e` → append `.0`.
  3. `ros2 param set $P NAME VALUE` (expects `Set parameter successful`). Fallback: `ros2 service call $P/set mavros_msgs/srv/ParamSetV2 "{force_set: false, param_id: NAME, value: {type: 2|3, integer_value|double_value: VALUE}}"` (expects `success=True`). Both fail → exit 3. **Never `force_set: true`** (ledger #11).
  4. `ros2 service call $P/pull mavros_msgs/srv/ParamPull "{force_pull: true}"` (timeout 120, failure ignored), then `ros2 param get` again → new value.
  5. Build the line with `changes_log.py line` (`--mismatch VALUE` when `same VALUE new` fails); append it to `<log>` and print it as the last stdout line. On a mismatch, also print `PARAM MISMATCH: NAME requested VALUE, read back NEW` on stderr and exit 1. Otherwise exit 0.
- `tools/sim.sh param set NAME VALUE [--drone N]` (`cmd_param`):
  - Validate as above. Anything else (`param`, `param get …`, a bad name/value/drone) → usage line + `error: …`, exit 2, before any docker call.
  - `docker exec $R true` fails → `error: param: the robot container is not running`, exit 2.
  - `docker exec $R mkdir -p /tmp/svg_param`; `docker cp tools/lib/px4_param_set.sh tools/lib/changes_log.py $R:/tmp/svg_param/` (two cp calls).
  - Log: `/tmp/svg_test/changes.log` if `$SIM_LOCK` exists and `kill -0 "$(cat "$SIM_LOCK")"` (a `sim.sh test` is running), else `/tmp/svg_param/changes.log`.
  - `docker exec $R bash -ic "bash /tmp/svg_param/px4_param_set.sh $N $NAME $VALUE sim.sh-param-set@${USER:-$(id -un)} $LOG"`. Append its last stdout line matching `grep -E ' · [^ ]+/[A-Z0-9_]+ · .* → '` to `$HOME/flight_logs/sim/changes.log` (mkdir -p), echo the output, and pass the exit code through.
- Usage line: `param set NAME VALUE [--drone N]   one PX4 parameter of a sim drone, live via MAVROS, read back and logged (sim only)`.

- [ ] **Step 1: failing tests**: `tools/tests/test_changes_log.py` (Line + Helper; Task 6 appends to it):
```python
# tools/tests/test_changes_log.py — the one changes.log formatter and the container-side PX4 parameter helper (sim only)
import os, pathlib, subprocess, sys, tempfile, unittest
TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS / "lib"))
import changes_log as CL
HELPER = TOOLS / "lib" / "px4_param_set.sh"
WHEN = "2026-11-03T10:00:00+08:00"

class Line(unittest.TestCase):
    def test_format_and_parse_round_trip(self):
        s = CL.format_line("drone_1", "MC_YAW_P", "2.8", "2.0", "sim.sh-param-set@t", when=WHEN)
        self.assertEqual(s, WHEN + " · drone_1/MC_YAW_P · 2.8 → 2.0 · sim.sh-param-set@t")
        self.assertEqual(CL.parse_line(s)["new"], "2.0"); self.assertIsNone(CL.parse_line("garbage"))
    def test_mismatch_is_on_the_line(self):
        self.assertTrue(CL.format_line("drone_1", "MC_YAW_P", "2.8", "2.8", "w", when=WHEN, mismatch="2.0").endswith(" · MISMATCH requested 2.0"))
    def test_same_is_float32_tolerant(self):
        self.assertTrue(CL.same("0.07", "0.07000000029802322")); self.assertTrue(CL.same("300", "300.0")); self.assertFalse(CL.same("2.8", "2.0"))

FAKE_ROS2 = ('#!/bin/sh\ncase "$1 $2" in\n'
             '  "param get") cat "$STATE";;\n'
             '  "param set") [ -n "$STUCK" ] || echo "$KIND value is: $5" > "$STATE"; echo "Set parameter successful";;\n'
             '  "service call") echo "response: success=True";;\nesac\n')

class Helper(unittest.TestCase):
    def _run(self, kind, old, val, stuck=""):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "ros2"), "w").write(FAKE_ROS2); os.chmod(os.path.join(d, "ros2"), 0o755)
            state = os.path.join(d, "state"); open(state, "w").write(f"{kind} value is: {old}\n"); log = os.path.join(d, "changes.log")
            env = dict(os.environ, PATH=d + ":" + os.environ["PATH"], STATE=state, KIND=kind, STUCK=stuck)
            r = subprocess.run(["bash", str(HELPER), "1", "MC_YAW_P", val, "who-1", log], capture_output=True, text=True, timeout=30, env=env)
            return r, (open(log).read() if os.path.exists(log) else "")
    def test_sets_reads_back_and_logs_one_line(self):
        r, log = self._run("Double", "2.8", "2.0")
        self.assertEqual(r.returncode, 0, r.stderr); self.assertIn(" · drone_1/MC_YAW_P · 2.8 → 2.0 · who-1", log)
        self.assertEqual(r.stdout.strip().splitlines()[-1], log.strip())
    def test_readback_mismatch_exits_1_and_says_so(self):
        r, log = self._run("Double", "2.8", "2.0", stuck="1")
        self.assertEqual(r.returncode, 1); self.assertIn("MISMATCH requested 2.0", log); self.assertIn("PARAM MISMATCH", r.stderr)
    def test_integer_parameter_refuses_a_fraction(self):
        r, log = self._run("Integer", "300", "2.5"); self.assertEqual(r.returncode, 2); self.assertEqual(log, "")
    def test_bad_name_exits_2(self):
        r = subprocess.run(["bash", str(HELPER), "1", "mc_yaw_p", "2.0", "w", os.devnull], capture_output=True, text=True); self.assertEqual(r.returncode, 2)
    def test_never_force_sets(self):                                              # ledger #11: force_set aborted mavros_node
        self.assertNotIn("force_set: true", HELPER.read_text())
```
Append to `tools/tests/test_sim_sh.py`:
```python
class ParamSet(unittest.TestCase):
    LINE = "2026-11-03T10:00:00+08:00 · drone_1/MC_YAW_P · 2.8 → 2.0 · sim.sh-param-set@t"
    def _env(self, tmp, rc=0):
        b = os.path.join(tmp, "bin"); os.makedirs(b, exist_ok=True); fake = os.path.join(b, "docker")
        open(fake, "w").write('#!/bin/sh\necho "$@" >> %s/docker.log\ncase "$*" in *"bash /tmp/svg_param/px4_param_set.sh"*) echo "%s"; exit %d;; esac\nexit 0\n' % (tmp, self.LINE, rc))
        os.chmod(fake, 0o755)
        return dict(os.environ, HOME=tmp, PATH=b + ":" + os.environ["PATH"])
    def test_copies_the_helper_runs_it_in_the_robot_container_and_logs_on_the_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("param", "set", "MC_YAW_P", "2.0", env=self._env(tmp)); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            calls = open(os.path.join(tmp, "docker.log")).read()
            self.assertRegex(calls, r"cp \S+/tools/lib/px4_param_set\.sh airstack-robot-desktop-1:/tmp/svg_param/")
            self.assertRegex(calls, r"cp \S+/tools/lib/changes_log\.py airstack-robot-desktop-1:/tmp/svg_param/")
            self.assertIn("bash /tmp/svg_param/px4_param_set.sh 1 MC_YAW_P 2.0 sim.sh-param-set@", calls)
            self.assertIn("/tmp/svg_param/changes.log", calls)
            self.assertIn(self.LINE, open(os.path.join(tmp, "flight_logs/sim/changes.log")).read())
    def test_during_a_test_run_the_line_lands_in_the_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "flight_logs/sim")); open(os.path.join(tmp, "flight_logs/sim/.sim_test.lock"), "w").write(str(os.getpid()))
            run("param", "set", "MC_YAW_P", "2.0", env=self._env(tmp))
            self.assertIn("/tmp/svg_test/changes.log", open(os.path.join(tmp, "docker.log")).read())
    def test_drone_flag_and_exit_code_pass_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("param", "set", "MC_YAW_P", "2.0", "--drone", "2", env=self._env(tmp, rc=1))
            self.assertEqual(r.returncode, 1); self.assertIn("px4_param_set.sh 2 MC_YAW_P", open(os.path.join(tmp, "docker.log")).read())
    def test_bad_arguments_exit_2_before_docker(self):
        for args in (["param"], ["param", "get", "MC_YAW_P"], ["param", "set", "mc_yaw_p", "2"], ["param", "set", "MC_YAW_P", "abc"],
                     ["param", "set", "MC_YAW_P", "2", "--drone", "0"], ["param", "set", "MC_YAW_P"]):
            with tempfile.TemporaryDirectory() as tmp:
                r = run(*args, env=self._env(tmp)); self.assertEqual(r.returncode, 2, args); self.assertIn("error:", r.stderr, args)
                self.assertFalse(os.path.exists(os.path.join(tmp, "docker.log")), args)
```
- [ ] **Step 2: run**: both files' new tests fail (`ModuleNotFoundError: changes_log`; `param` is not a subcommand → exit 2 with usage).
- [ ] **Step 3: implement** per Interfaces (`chmod +x tools/lib/px4_param_set.sh`).
- [ ] **Step 4: verify**: full suite `OK`; `bash -n tools/lib/px4_param_set.sh tools/sim.sh`; `tools/sim.sh 2>&1 | grep 'param set'`.
- [ ] **Step 5: commit**: line `| CHG-<B+3> | <date> | sim-only | tools/sim.sh param set NAME VALUE: live PX4 parameter of a sim drone via MAVROS, read back, logged by the one formatter (changes_log.py) | this |`. Message:
```
tools: sim.sh param set — one PX4 parameter of a sim drone, live through MAVROS (never force_set), read back, logged as time · drone_N/NAME · old → new · who

Change: CHG-<B+3>
What: new tools/sim.sh param set NAME VALUE [--drone N] (host -> docker cp + docker exec into airstack-robot-desktop-1 -> tools/lib/px4_param_set.sh: ros2 param get, ros2 param set with ParamSetV2 force_set false as fallback, ParamPull force_pull true, read back) and the one changes.log formatter tools/lib/changes_log.py; lines go to ~/flight_logs/sim/changes.log and, while a sim.sh test runs, to /tmp/svg_test/changes.log in the robot container.
Scope: sim-only (the MAVROS param node of a sim drone; real drones never start MAVROS); any world.
Why: docs/CODING_STANDARD.md §3: live changes are logged by the tools, not from memory (design A4, P6, B7).
Could affect: PX4 parameters of a flying sim drone (the purpose); MAVROS load from a full forced param pull mid-flight; a running test's changes.log; the yaw-step sweep once it calls the helper (CHG-<B+5>).
Watch for: mavros_node restarting after a set; a read-back that never matches (exit 1, MISMATCH on the line); a set that the ulog's changed-parameter list does not show.
Verified by: tools/tests/test_changes_log.py Line, Helper (fake ros2: set, mismatch, integer type, bad name), test_sim_sh.py ParamSet (fake docker); pending: owner session param-set read-back.
Revert: git revert <this commit>.
```

---

### Task 6: Run capture — snapshots, the ulog's list, the run's changes.log, "Changes in this run" (executor: **opus**; ID CHG-<B+4>)

**Files:** Modify `tools/lib/changes_log.py` (dump/diff/ulog/block), `tools/lib/stack.sh` (`param_snapshot`, `param_diff`), `tools/sim.sh` (`cmd_test` wiring, `metrics_collect`, `ulog_param_changes`), `tools/lib/report.py` (`render`), `tools/sim.sh` `cmd_setup` (one `warn` line: host PyYAML); tests in `tools/tests/test_changes_log.py`, `test_stack_sh.py`, `test_sim_sh.py`, `test_report.py`; `docs/record/CHANGES.md`.

**Interfaces consumed:** `airframe_params.parse_airframe`, `AIRFRAME`, `REPO`, `same` (Task 3); `changes_log.parse_line`, `same` (Task 5).

**Interfaces produced:**
- `changes_log.py`:
  - `BOOT_S = 2.0`.
  - `read_dump(text) -> dict[str, str]`: drop lines before the first line starting `/`, then `yaml.safe_load`. Under each node: `ros__parameters`, flattened with `.` joins; lists → `json.dumps(list)`; scalars → `str`.
  - `diff_dumps(a, b) -> list[(name, old, new)]`: numeric values compare with `same`; a key in only one side → `"(absent)"`.
  - `ulog_changes(text) -> list[(t_s: float, target, name, value)]`: parses `t_s target NAME value` lines, `#` lines skipped.
  - `changes_block(out: Path, heavy: Path | None, airframe_text: str | None = None) -> list[str]`. Markdown lines, in this order:
    - `## Changes in this run`, then one sentence: what changed while this run flew (docs/CODING_STANDARD.md §3); PX4's own list (the ulog) is the ground truth and wins a conflict.
    - **"Logged by the tools (`changes.log`):"**: a fenced block of `out/changes.log`, or `none logged`.
    - **"PX4 ulog, parameters changed after boot (vehicle time, t > 2 s; <k> boot-time settings not listed):"**: a fenced block of `out/px4_param_changes_all.txt` rows with `t_s > BOOT_S`, or `n/a — px4_param_changes_all.txt missing`.
    - **"Parameter snapshot, start → end of the flight (MAVROS for PX4, `ros2 param dump /swarm_commander`; catches Foxglove, QGC, `ros2 param set`):"**: a fenced block of `out/params_diff.txt` without its `#` lines, `no differences`, or `n/a — params_diff.txt missing`.
    - **"PX4 at the start vs the airframe file (drone_1):"**: `all N airframe values in force`; or one `- NAME: airframe a, in force b` per difference (from `heavy/params_start_drone_1.yaml`); or `n/a — no start snapshot`.
    - **"Conflicts and unlogged changes:"**:
      - `- CONFLICT: changes.log has <target>/<name> → v, the ulog shows w at t s — the ulog wins` (last logged value vs last ulog value, drone targets only);
      - `- CONFLICT: <target>/<name> logged but absent from the ulog list — did PX4 receive it?` (only when the ulog file exists);
      - `- UNLOGGED: <target>/<name> a → b (snapshot; no tool logged it: Foxglove, QGC or ros2 param set?)`;
      - `- UNLOGGED (ulog): <target>/<name> → v at t s`;
      - or `- none`.
  - CLI:
    - `diff <heavy_dir> -o <out>`: for each `params_start_<target>.yaml`, write `<target>/<name> <old> -> <new>` lines to `<out>`; when the matching end file is missing, write `# <target>: no end snapshot`. Exit 4 if PyYAML is missing.
    - `ulog <ulog>... -o <out>`: lazy pyulog, `ULog(f, message_name_filter_list=["vehicle_status"])`; target from the filename (`drone_(\d+)_sysid`); writes `%.3f drone_N NAME value` for every `changed_parameters` entry (boot-time ones included, so the count is honest). Exit 4 if pyulog is missing.
- `stack.sh` `param_snapshot <start|end>`, a new function after `params()`:
  - For each `N in $DRONE_IDS`: `rx "timeout 120 ros2 service call /drone_$N/interface/mavros/param/pull mavros_msgs/srv/ParamPull '{force_pull: false}'"`, then `rx "timeout 60 ros2 param dump /drone_$N/interface/mavros/param" > "$HEAVY/params_<tag>_drone_$N.yaml"`.
  - Count `grep -cE '^ {4}[A-Z][A-Z0-9_]*:'`: ≥ 500 → `say "snapshot <tag> drone_N: <n> PX4 parameters"`, else `say "WARN: snapshot <tag> drone_N has <n> PX4 parameters (< 500) — the diff for drone_N is partial"`.
  - Then `rx "timeout 30 ros2 param dump /swarm_commander" > "$HEAVY/params_<tag>_swarm_commander.yaml"`.
  - Each command gets a `note` first. Snapshots live in `$HEAVY` (about 900 lines each), never in the repo.
- `stack.sh` `param_diff`: `python3 "$REPO/tools/lib/changes_log.py" diff "$HEAVY" -o "$OUT/params_diff.txt" >> "$OUT/run.log" 2>&1 || caveat "params_diff.txt not written (a snapshot missing or host PyYAML absent) — the record's snapshot column is n/a"`.
- `sim.sh cmd_test`:
  - (a) right after the stack phase loop (after `params`): `PHASE=snapshot; param_snapshot start`.
  - (b) copy-in loop: add `"$REPO/tools/lib/px4_param_set.sh" "$REPO/tools/lib/changes_log.py"`.
  - (c) the reset line becomes `docker exec "$R" bash -c ": > $S/metrics_node.log; : > $S/changes.log; rm -f $S/metrics.csv"`.
  - (d) after `json1 /svg/commander_status > "$OUT/status_post.json" …` (step 5): `param_snapshot end; param_diff`.
  - (e) step 7: after `yaw_dump "$U1"` call `ulog_param_changes`, a new function next to `yaw_dump`. It globs `"$HEAVY"/drone_*_sysid*_*.ulg`; none → `caveat "no ulog for px4_param_changes_all.txt — the record's ulog column is n/a"`. Otherwise `nx python3 "$REPO/tools/lib/changes_log.py" ulog <files> -o "$OUT/px4_param_changes_all.txt"`, with a caveat on failure. Add `px4_param_changes_all.txt` to the `phase_begin collect …` list.
  - (f) `metrics_collect`: `docker cp "$R:$S/changes.log" "$OUT/changes.log" 2>/dev/null || true`.
- `report.py render`: `import changes_log as CL` at the top (tools/lib is on `sys.path` both as a script and in the tests). Insert `L += [""] + CL.changes_block(out, heavy) + [""]` after the Setup table and before `## Pass/fail`.
- `cmd_setup`: `python3 -c 'import yaml'` → `ok "host python: PyYAML"`, else `warn "host python lacks PyYAML (pip install pyyaml) — the record's snapshot diff is n/a"`.

- [ ] **Step 1: failing tests**: append to `tools/tests/test_changes_log.py`:
```python
DUMP = "/drone_1/interface/mavros/param:\n  ros__parameters:\n    MC_YAW_P: 2.799999952316284\n    MC_YAWRATE_P: 0.07000000029802322\n    SYS_AUTOSTART: 10090\n"
CMD = ("bash: cannot set terminal process group\n/swarm_commander:\n  ros__parameters:\n    cbf_alpha: 2.5\n    fence_min:\n    - -4.0\n    - -2.0\n"
       "    qos_overrides:\n      /parameter_events:\n        publisher:\n          depth: 1000\n")
AF = "param set-default MC_YAW_P 2.8 # = real\nparam set-default MC_YAWRATE_P 0.07 # = real\n"

class Snapshot(unittest.TestCase):
    def test_dump_flattens_nested_keys_and_lists_after_noise(self):
        d = CL.read_dump(CMD)
        self.assertEqual(d["cbf_alpha"], "2.5"); self.assertEqual(d["fence_min"], "[-4.0, -2.0]"); self.assertIn("qos_overrides./parameter_events.publisher.depth", d)
    def test_diff_is_float32_tolerant(self):
        a = CL.read_dump(DUMP)
        self.assertEqual(CL.diff_dumps(a, CL.read_dump(DUMP.replace("0.07000000029802322", "0.07"))), [])
        self.assertEqual(CL.diff_dumps(a, CL.read_dump(DUMP.replace("2.799999952316284", "2.0"))), [("MC_YAW_P", "2.799999952316284", "2.0")])
    def test_diff_cli_names_a_missing_end(self):
        with tempfile.TemporaryDirectory() as d:
            h = pathlib.Path(d)
            (h / "params_start_drone_1.yaml").write_text(DUMP); (h / "params_end_drone_1.yaml").write_text(DUMP.replace("2.799999952316284", "2.0"))
            (h / "params_start_swarm_commander.yaml").write_text(CMD)
            subprocess.run([sys.executable, str(TOOLS / "lib/changes_log.py"), "diff", d, "-o", str(h / "diff.txt")], check=True)
            t = (h / "diff.txt").read_text()
            self.assertIn("drone_1/MC_YAW_P 2.799999952316284 -> 2.0", t); self.assertIn("# swarm_commander: no end snapshot", t)

class Block(unittest.TestCase):
    def _block(self, files, start=None):
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d, "out"); heavy = pathlib.Path(d, "heavy"); out.mkdir(); heavy.mkdir()
            for k, v in files.items(): (out / k).write_text(v)
            if start: (heavy / "params_start_drone_1.yaml").write_text(start)
            return "\n".join(CL.changes_block(out, heavy, airframe_text=AF))
    LOG = WHEN + " · drone_1/MC_YAW_P · 2.8 → 2.0 · yaw_step-sweep-set-1\n"
    def test_all_sources_agree(self):
        t = self._block({"changes.log": self.LOG, "px4_param_changes_all.txt": "0.950 drone_1 CAL_ACC0_ID 1310988\n35.100 drone_1 MC_YAW_P 2.0\n",
                         "params_diff.txt": "drone_1/MC_YAW_P 2.8 -> 2.0\n"})
        for s in ("## Changes in this run", "yaw_step-sweep-set-1", "35.100 drone_1 MC_YAW_P 2.0", "1 boot-time", "drone_1/MC_YAW_P 2.8 -> 2.0"):
            self.assertIn(s, t)
        self.assertNotIn("CAL_ACC0_ID", t); self.assertIn("Conflicts and unlogged changes:", t); self.assertIn("- none", t)
    def test_conflict_names_the_ulog_as_the_winner(self):
        t = self._block({"changes.log": self.LOG, "px4_param_changes_all.txt": "35.100 drone_1 MC_YAW_P 1.5\n"})
        self.assertIn("CONFLICT", t); self.assertIn("the ulog wins", t)
    def test_unlogged_snapshot_change_is_flagged(self):
        t = self._block({"changes.log": "", "params_diff.txt": "swarm_commander/cbf_alpha 2.5 -> 4.7\n"})
        self.assertIn("UNLOGGED: swarm_commander/cbf_alpha 2.5 → 4.7", t)
    def test_missing_files_say_na_and_never_crash(self):
        t = self._block({}); self.assertIn("none logged", t); self.assertEqual(t.count("n/a"), 3)
    def test_start_vs_airframe(self):
        self.assertIn("MC_YAW_P: airframe 2.8, in force 2.0", self._block({}, start=DUMP.replace("2.799999952316284", "2.0")))
        self.assertIn("all 2 airframe values in force", self._block({}, start=DUMP))
```
`tools/tests/test_stack_sh.py`:
```python
class Snapshots(unittest.TestCase):
    def test_one_dump_per_drone_and_the_commander(self):
        r = run_stub('HEAVY=$(mktemp -d); rx(){ case "$*" in *"param dump /drone_"*) printf "/d:\\n  ros__parameters:\\n"; for i in $(seq 1 600); do echo "    P$i: 1"; done;; '
                     '*"param dump /swarm_commander"*) echo "/swarm_commander:";; esac; }; param_snapshot start; ls "$HEAVY"')
        for n in ("params_start_drone_1.yaml", "params_start_drone_2.yaml", "params_start_drone_3.yaml", "params_start_swarm_commander.yaml"):
            self.assertIn(n, r.stdout, r.stdout + r.stderr)
        self.assertIn("600 PX4 parameters", r.stdout)
    def test_a_short_dump_warns(self):
        r = run_stub('HEAVY=$(mktemp -d); rx(){ case "$*" in *"param dump /drone_"*) printf "/d:\\n  ros__parameters:\\n    P1: 1\\n";; esac; }; param_snapshot end')
        self.assertIn("WARN: snapshot end drone_1 has 1 PX4 parameters", r.stdout)
```
`tools/tests/test_sim_sh.py`:
```python
    def test_run_captures_parameter_changes(self):                     # in class SimSh
        src = SIM.read_text()
        loop = src.index("for PHASE in precheck up watch isaac interfaces commander params"); s = src.index("param_snapshot start")
        self.assertLess(loop, s); self.assertLess(s, src.index("start_live_plot\n"))
        e = src.index("param_snapshot end"); self.assertLess(src.index('> "$OUT/status_post.json"'), e); self.assertLess(e, src.index("PHASE=metrics_stop"))
        self.assertLess(e, src.index("param_diff"))
        self.assertIn(": > $S/changes.log", src); self.assertIn('"$REPO/tools/lib/px4_param_set.sh" "$REPO/tools/lib/changes_log.py"', src)
        self.assertIn("$S/changes.log", src[src.index("metrics_collect() {"):src.index("bag_dump_hook() {")])
        self.assertLess(src.index('yaw_dump "$U1"'), src.index("\n  ulog_param_changes")); self.assertLess(src.index("\n  ulog_param_changes"), src.index("PHASE=down; down"))
```
Also update `test_collect_dumps_the_yaw_csv_with_a_container_fallback`'s `phase_begin collect …` string to include ` px4_param_changes_all.txt`. `tools/tests/test_report.py` (class `Report`):
```python
    def test_changes_block_sits_between_setup_and_pass_fail(self):
        rows, ctx = self.G.build_rows(self.out, self.heavy, self.env)
        md = R.render(self.env, rows, ctx, self.out, self.heavy, "PASS", [], 20, "NEAR-787")
        self.assertLess(md.index("## Setup"), md.index("## Changes in this run")); self.assertLess(md.index("## Changes in this run"), md.index("## Pass/fail"))
```
- [ ] **Step 2: run**: the new tests fail (`AttributeError: … read_dump`, `substring not found`).
- [ ] **Step 3: implement** per Interfaces.
- [ ] **Step 4: verify**
  - Full suite `OK`; `tools/sim.sh check` → OK.
  - `python3 tools/lib/changes_log.py ulog ~/flight_logs/sim/sim_crossing_run2/drone_*_sysid*_*.ulg -o <scratch>/p.txt` → 3 × 46 boot-time lines, all `t_s` < 2.0. This is a real host check, not a sim.
  - Render one record with `python3 tools/lib/report.py tools/sim_tests/crossing <a scratch copy of docs/record/sim_crossing_run2> --heavy ~/flight_logs/sim/sim_crossing_run2 --no-verdict-log --record <scratch>/r.md` and look at its "Changes in this run" block once. Expect `none logged`, the ulog line (0 changes after boot) or n/a, and snapshot n/a. Delete the scratch output.
- [ ] **Step 5: commit**: line `| CHG-<B+4> | <date> | tooling | every sim.sh test: start/end parameter snapshots, PX4 ulog changed-parameter list, the run's changes.log and a "Changes in this run" record block | this |`. Message:
```
tools: every sim test records what changed while it flew — start/end parameter snapshots, PX4's own changed-parameter list, the run's changes.log, and a "Changes in this run" block in the record

Change: CHG-<B+4>
What: stack.sh param_snapshot start|end (MAVROS param pull force_pull false + ros2 param dump per drone, ros2 param dump /swarm_commander -> ~/flight_logs/sim/<run>/params_<tag>_*.yaml) + param_diff -> docs/record/<run>/params_diff.txt; sim.sh cmd_test calls them after the params phase and after landing, copies px4_param_set.sh + changes_log.py into /tmp/svg_test, resets and copies out changes.log, writes px4_param_changes_all.txt from every drone's ulog; report.py prints "Changes in this run" after Setup (tools log, ulog list after 2 s of boot, snapshot diff, start vs airframe, conflicts/unlogged).
Scope: tooling (every sim.sh test run; no flight behaviour, no parameter is written).
Why: docs/CODING_STANDARD.md §3 and design B7: the ulog is the ground truth, the snapshot the safety net, and both are printed with the tools' log.
Could affect: every sim.sh test (crossing, yaw_step): run time (one param pull + dump per drone at each end, UNVERIFIED cost), MAVROS load at the snapshots, record length, collect step; the hover driver does not call the new functions.
Watch for: a snapshot WARN "< 500 PX4 parameters"; UNLOGGED lines in a run nobody touched (a snapshot artefact); the snapshot phases adding minutes; a CONFLICT line.
Verified by: tools/tests/test_changes_log.py Snapshot, Block; test_stack_sh.py Snapshots; test_sim_sh.py test_run_captures_parameter_changes; test_report.py changes block; ulog CLI on the sim_crossing_run2 ulogs (boot-time only); pending: owner session snapshot diff.
Revert: git revert <this commit>.
```

---

### Task 7: The yaw-step sweep writes through the shared helper (executor: **opus**; ID CHG-<B+5>)

**Files:** Modify `tools/sim_tests/yaw_step/fly.sh`, `tools/tests/test_yaw_step_gates.py` (static needles only), `docs/record/CHANGES.md`.

**What fly.sh must call (design B7: the sweep and `sim.sh param set` share one log):** the helper sits next to fly.sh in `$S` (Task 6 copies it in), so `HERE=$(cd "$(dirname "$0")" && pwd)`. For every parameter of gain set k, the sweep calls, from the shell or from the embedded python via `subprocess.run([...], capture_output=True, text=True)`:
```
bash "$HERE/px4_param_set.sh" 1 <NAME> <VALUE> yaw_step-sweep-set-<k> "$HERE/changes.log"
```
- rc 0: print the helper's last stdout line (the changes.log line) to fly.sh's stdout.
- rc ≠ 0: print `PARAM MISMATCH` and the helper's output, stop the sweep, land normally, exit 1 (the yaw plan's existing rule).
- Remove fly.sh's own ParamSetV2 / `ros2 param set` / pull / get code. Keep every stdout line format that `gates.py` parses: read `gates.py` first. If it parses a `[<unix.ns>] param …` line, print that line too.

- [ ] **Step 1: failing test**: in `test_fly_publishes_zeros_on_exit`, replace the needles `"param/set", "param/pull", "force_pull: true"` with `"px4_param_set.sh", "yaw_step-sweep-set-", "changes.log"`, and add `self.assertNotIn("ParamSetV2", src)`. Run `python3 -m unittest discover -s tools/tests -p 'test_yaw_step_gates.py' 2>&1 | tail -3` → FAIL on `px4_param_set.sh`.
- [ ] **Step 2: implement** the switch; `bash -n tools/sim_tests/yaw_step/fly.sh`.
- [ ] **Step 3: verify**: full suite `OK`; `tools/sim.sh check` → `OK yaw_step`.
- [ ] **Step 4: commit**: line `| CHG-<B+5> | <date> | sim-only | yaw_step fly.sh sweep sets PX4 gains through px4_param_set.sh, one changes.log with sim.sh param set | this |`. Message:
```
tools: yaw_step sweep sets the gains through px4_param_set.sh — one changes.log line per set, same helper as sim.sh param set (NEAR-789)

Change: CHG-<B+5>
What: tools/sim_tests/yaw_step/fly.sh: its own ParamSetV2 / ros2 param set + pull + get -> bash $S/px4_param_set.sh 1 NAME VALUE yaw_step-sweep-set-<k> $S/changes.log (stop-on-mismatch unchanged).
Scope: sim-only (one sim drone, yaw_step test, MAVROS param node).
Why: design B7: the sweep and sim.sh param set share one formatter and one log; the record's "Changes in this run" shows every set.
Could affect: the yaw_step sweep groups (which gains PX4 flies per group), the gates' per-set INFO rows, sweep timing (a forced pull per set, as before).
Watch for: a sweep stopping on PARAM MISMATCH; changes.log lines without matching ulog changes (CONFLICT in the record); set-k INFO rows naming gains PX4 did not fly.
Verified by: tools/tests/test_yaw_step_gates.py (static), bash -n, sim.sh check; pending: owner session sweep run.
Revert: git revert <this commit>.
```

---

## Owner session additions (the next live sim session; the yaw plan's owner session)

Run these with the yaw plan's owner session. Each line is the check for one UNVERIFIED item.

```bash
tools/sim.sh doctor                    # "pre-commit hook active (core.hooksPath = tools/git-hooks)" and "host python: PyYAML" OK
tools/sim.sh test yaw_step --issue NEAR-789 sim_yaw_run1     # the first run after this plan
```
1. **Airframe intact (U7).** `docs/record/sim_yaw_run1/params_ulog.txt` shows MC_PITCHRATE_P 0.032, LNDMC_ROT_MAX 300, MPC_XY_VEL_MAX 20, MPC_THR_HOVER 0.165. The record's "PX4 at the start vs the airframe file" reads `all 48 airframe values in force`.
2. **Snapshots (U3, U4).** The terminal shows `snapshot start drone_1: <n> PX4 parameters` with n ≥ 500 and `snapshot end …`; note the seconds both took. With no live change, the record says `none logged`, the ulog list is empty after boot, the snapshot `no differences`, and Conflicts `- none`.
3. **Sweep (U1, U2, U5).** On `sim_yaw_sweep1`, `docs/record/sim_yaw_sweep1/changes.log` has one `drone_1/MC_YAW_P · 2.8 → 2.0 · yaw_step-sweep-set-1` line per set. The ulog list shows the same values at vehicle time > 2 s, the snapshot shows start 2.8 → end = the last set, and Conflicts reads `- none`. `mavros_node` does not restart (`grep -c 'exit code' docs/record/sim_yaw_sweep1/interfaces.log`).
4. **`sim.sh param set` by hand (U1).** With the stack up between runs: `tools/sim.sh param set MC_YAW_P 2.8` prints the line, exits 0 and appends to `~/flight_logs/sim/changes.log`. Set something during a run (e.g. `MC_YAWRATE_D 0.0`): the line must be in that run's `changes.log` and its ulog list. Then a Foxglove gain change during a run must show as `UNLOGGED: swarm_commander/…` in the record.
5. **`down` guard (U6).** After a tabs session (Isaac started by `tools/sim_terminals.sh`), run `tools/sim.sh down`. Expect `ulog guard: saved N PX4 ulog(s) to ~/flight_logs/sim/uncollected_<date>`, then the normal teardown. A second `down` (Isaac already stopped): `isaac container not running` or `saved 0`. `tools/sim.sh down --force` prints the "lost" line.
6. Docs for these runs follow DOCS_STANDARD §7. A LEDGER row of a run that flew a change cites its CHG id. The yaw plan's Task 5 commit carries the next CHG id and turns the five yaw lines into `# SIM-ONLY (real <v>) CHG-<its id>`, which the marker test enforces. Its Task 6 keeps rule 9's new MPC sentence.

## UNVERIFIED (no running container today)

- U1 `ros2 param set /drone_N/interface/mavros/param NAME V` pushes PARAM_SET to PX4 (yaw plan U2). Arbiter: the ulog list (session check 3/4).
- U2 `mavros_msgs/srv/ParamSetV2` field names for the fallback (yaw plan U1).
- U3 `ros2 param dump <node>` prints YAML on stdout in the robot container, with nested keys and block lists as `read_dump` expects, ~900 PX4 keys within 60 s.
- U4 With `force_pull: false`, the MAVROS cache already holds a change made outside MAVROS by the end snapshot.
- U5 `force_pull: true` mid-flight (the helper's read-back, as in the yaw plan) does not disturb MAVROS. Ledger #11 was about `force_set`.
- U6 `/tmp/tmp*/log/*/*.ulg` is still listable when a bare `down` starts after a tabs session. `copy_ulogs` relies on the same glob.
- U7 The trailing markers leave PX4's parse unchanged. Strongly supported (MPC_THR_HOVER's trailing comment is in force) but re-checked in session check 1.

## Owner must know

- **Two "real" sources disagree on the MPC limits.** `starling_1_indoor_params.params` (the QGC export committed 2026-09-04, which rule 9 names as the authority) has `MPC_XY_VEL_MAX` 3, `MPC_ACC_HOR` 3, `MPC_ACC_HOR_MAX` 3, `MPC_Z_VEL_MAX_UP` 2, `MPC_Z_VEL_MAX_DN` 0.6. The 2026-08-20 drone backup `~/RCC_Starling_1/px4/px4_params_all.txt` has 20 / 6 / 1000 / 10 / 4 (and `MPC_XY_CRUISE` 15). `d739a73` copied the backup. Which set the drone flies today depends on whether the file was loaded after 08-20: check in QGC before the next real flight. The new rule-9 sentence and the markers use the file.
- PREFLIGHT's checklist bullet "the drone's PX4 limits allow 20 m/s" matches the backup, not the file. It is conservative and is left unchanged; the owner decides.
- Rule 9 lists "gyro filters 80/40 Hz" as sim-only, but they equal the drone's file (80/40), so the markers say `= real`. Rewording that is not approved; it is left as is.
- Task 2 bumps PREFLIGHT's version token, so the card must be reprinted.
- A candidate second-order effect is already visible in the ledger. The crossing's minimum distance was 1.02 m at #4 (PX4 limits 3 m/s) and 0.95–1.00 m at #20–#22 (after `d739a73`). CHG-0003's "Could affect" names it. The planned MPC-limit match (after the yaw retune) and the crossing re-runs will separate it from the other 10-20 changes.

## Docs follow-ups (ask the owner before editing; not in any task)

- `tools/README.md`: rows for `sim.sh param set`, `down [--force]`, `tools/lib/changes_log.py` / `px4_param_set.sh` / `airframe_params.py`; the `git-hooks/` row ("active via core.hooksPath").
- `CLAUDE.md` tools row: add `param set` to the `sim.sh` subcommand list.
- `docs/RUNBOOK.md` §A: ad-hoc PX4 changes use `tools/sim.sh param set`; `down` saves the ulogs.
- `docs/DOCS_STANDARD.md` §7: a LEDGER row of a run that flew a change cites its CHG id (B11). This is a docs-standard change, so it goes through the `quality-change` skill if the owner wants it.
