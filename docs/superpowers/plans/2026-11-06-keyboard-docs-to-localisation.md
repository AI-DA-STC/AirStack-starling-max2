# Keyboard docs to localisation/README.md: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The one-drone sim keyboard session (keys, cold start, layout, strip, evidence) lives once, in `localisation/README.md`. `docs/TELEOP.md` §3b keeps a sim-only warning, the Tk-window rules and a pointer. A WARN-level `single-home` check keeps it that way. Seven "nothing has flown" lines say "on the real drone".

**Architecture:** Docs move in the order the spec fixes: new content lands in the README (Task 1), the checker that watches the homes arrives (Task 2), inbound links are retargeted (Task 3), TELEOP's old text is cut last (Task 4). The "has flown" wording (Task 5) is independent. Task 6 verifies the spec's Done-when list and pulls the mirror. The check comes before the cut on purpose: it reports the TELEOP copies as WARN after Task 2 and PASS after Task 4, which proves the cut.

**Tech Stack:** Markdown (GitHub rendering), Python 3 stdlib (`tools/docs_check/check_docs.py`), `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-06-keyboard-docs-to-localisation-design.md` (approved by the owner 2026-11-06). Read it, including "Builder check" and "Real or sim", before any task.

## Global Constraints

- Work in the live clone `/home/jeremychia/AirStack-starling-max2`, on `main`. No worktree, no branch (owner's standing ruling). Never push.
- After the last task: `git -C ~/Documents/GitHub/AirStack-starling-max2 pull ~/AirStack-starling-max2 main`.
- Never edit `AirStack/`, `docs/record/LEDGER.md`, any record, `docs/plans/*`, older specs or plans. `docs/record/CHANGES.md` is append-only, and this plan appends nothing to it (see below).
- Never stage `QGroundControl-x86_64.AppImage`, `"starling max2 voxl setup.txt"`, `docs/record/sim_hover_step_run4/` or `.superpowers/`. Stage named paths only (`git add <path> …`), never `git add -A` or `git add .`.
- Never `--amend`, never `--no-verify`. If the pre-commit hook blocks, fix the cause and make a new commit.
- Change log: every file this plan touches answers `no` to `python3 tools/docs_check/changes.py is-behaviour <path>`. That covers `tools/docs_check/check_docs.py`, `tools/docs_check/single_home.txt`, `tools/tests/test_check_docs.py`, `tools/docs_check/README.md`, `tools/README.md`, `localisation/README.md`, `docs/TELEOP.md`, `README.md` and `CLAUDE.md`, all checked on 2026-11-06. So no CHANGES.md row and no eight-field body. CHG-0056 stays free. If any answer differs at commit time, stop and report it.
- `python3 tools/docs_check/check_docs.py` must end with `0 FAIL` at every commit. The pre-commit hook (`tools/git-hooks/pre-commit`, active through `core.hooksPath`) runs it when docs or tools are staged. It runs `python3 -m unittest discover -s tools/tests` and `tools/sim.sh check` when `tools/` is staged.
- Moved blocks are copied byte for byte from `docs/TELEOP.md` at commit `2cbce49` (identical to HEAD `5b19d3b` for that file). Every sentence changed to fit its new page is listed in the implementer's report. The known changes are listed in each task.
- Wording rules for new text: short plain sentences. On-screen words are `Drive mode` and `Room mode`. Write "motion-capture positioning (mocap)", never "under mocap". Sim must never read as real. No ⚠️ glyph and no `[SIM]` token in new text. The sim-only warning opens with plain bold "Sim only." and contains the fixed words `never go on the real drone`.
- Linear ids and titles are copied verbatim from `docs/plans/2026-11-05-project-plan-linear.md`.
- FAIL-level page budgets: `docs/projects/HTX-R1.md` ≤ 250 lines and is at exactly 250, so every edit there is in-line (net zero lines). Each `###` section ≤ 40 lines, cells ≤ 120 characters. `docs/MILESTONES.md` ≤ 60 lines, cells ≤ 120 characters.
- A paragraph on the line right after a table row, with no blank line between, is absorbed into the table. Always leave a blank line after a table.
- `docs/PREFLIGHT.md`: any edit must change the `vYYYY-MM-DD` token on its first line (`check_preflight_date` FAILs an uncommitted PREFLIGHT edit whose token equals HEAD's). This plan bumps `v2026-11-02` → `v2026-11-06` in the same commit as the line-5 edit.
- The `single-home` check is WARN only, never FAIL, and never matches inside `docs/plans/`, `docs/superpowers/`, `docs/record/` or `.claude/`.
- Anchors this plan relies on (GitHub slugs; `check_docs.slugify` gives the same):
  `localisation/README.md#fly-it-with-the-keyboard-one-drone-sim-only`, `#evidence`, `#keys`, `#cold-start`, `#the-layout-first-time-only`, `#the-strip`, `#run-it`;
  `docs/TELEOP.md#3b--keyboard-instead-of-a-pad-sim-only-ours`;
  `docs/projects/HTX-R1.md#s5-finish-basic-sim-flight-checks--sim-only-isaac`.

## Controller rulings on the plan (2026-11-06)

- **Chooser above the picture.** The spec's page order had the picture first. Counting from the page top (builder check 4), that order cannot meet "flown and the video ≤ 15 lines". Ruling: banner, chooser, picture. Cost if wrong: the picture sits about 8 lines lower.
- **README length 270 lines**, against the spec's expected 215 to 265. Ruling: stays one page (panel 4–0). No gate covers it.
- **Three edits beyond the spec's link list** (root README "I want to…" row, CLAUDE.md localisation row, the split link in tools/README's `teleop/` row). Ruling: kept. Each one removes a pointer that would otherwise send a keyboard reader to the wrong page.
- **One moved bullet reworded** ("After this change …"), listed as change 8 in Task 1.

## Review Focus

1. A real-drone reader opens `docs/TELEOP.md` §3b and never the README. The first line under the "3b" heading must tell them that Drive mode, the relay and `teleop_single_ours.yaml` (both fences off) are sim only and never go on the real drone. Pinned by Task 4 Step 3 (the line right after the heading) and by the `require` row tested in Task 2 (`test_require_missing_warns_and_a_wrapped_phrase_passes`).
2. A moved evidence line reads as a hardware result once it has left its "(simulation)" header. Every Evidence bullet carries "(simulation)", and the section opens by saying it runs in the simulator only. Pinned by Task 1 Step 7 (`grep -c '(simulation)'` = 4).
3. A paragraph lands directly under a table row and is swallowed by the table (chooser, Where it runs, Keys, Prerequisites, Folder map). Pinned by the `awk` step in Tasks 1, 3 and 4.
4. A link still says "TELEOP §3b" but means moved content (keys, strip, cold start, video). Pinned by Task 3 Step 4, which lists every `§3b` left on the live pages and why each one is about the Tk window.
5. A "nothing has flown" sentence wraps, so a line-by-line grep shows it without its qualifier (`docs/SCENARIOS.md:19–20` already does this). Done-when 5 must read the next line too. Pinned by Task 5 Step 3 and Task 6 Step 6, which use `git grep -A1`.

---

### Task 1: localisation/README.md gains the chooser and the keyboard section

**Files:**
- Modify: `localisation/README.md` (lines 5–7 chooser, row after 18, line 56, new section after 94, line 132, row after 140, line 151)
- Read only: `docs/TELEOP.md` at `2cbce49` (source of the copied blocks)

**Interfaces:**
- Consumes: nothing.
- Produces: the anchors listed in Global Constraints for `localisation/README.md`. Tasks 3 and 4 link to them. The README is the home file of all three `only` rows in Task 2's registry.

- [ ] **Step 1: Confirm the source is unchanged since the design**

Run: `cd ~/AirStack-starling-max2 && git diff --quiet 2cbce49 HEAD -- docs/TELEOP.md localisation/README.md; echo $?`
Expected: `0`

- [ ] **Step 2: Insert the chooser between the banner and the picture**

Insert these lines after the banner's last line (`> here touches the real drone.`) and its blank line, so the `<img src="../pictures/drones_in_construction_site.jpg" …>` line follows the chooser's trailing blank line. Title, banner, picture and caption are unchanged.

```markdown
## Which run do you want?

| Goal | Drones | Config | Go to |
|---|---|---|---|
| Scored camera run: fly, record and score cuVSLAM | 3 | `cbf_sim.yaml`, `random_goals` | [Run it](#run-it) |
| Fly it yourself by keyboard | 1 | `teleop_single_ours.yaml` | [Fly it with the keyboard](#fly-it-with-the-keyboard-one-drone-sim-only): [evidence](#evidence) · [keys](#keys) · [cold start](#cold-start) |

```

The chooser sits above the picture, not below it. This deviates from the spec's order and is required by Done-when 4 (see Task 6 Step 5).

- [ ] **Step 3: Add the keyboard row to "Where it runs"**

After the row `| Interfaces · Commander · Cockpit tabs | robot container | unchanged — [RUNBOOK §A2–A4](../docs/RUNBOOK.md) |`, add as the table's last row:

```markdown
| Cockpit tab · `jeremychia@…$` | robot container · laptop terminal | keyboard session only: `teleop.launch.py` in the Cockpit tab; `tools/sim.sh relay` in a laptop terminal (it starts the relay inside the robot container) |
```

- [ ] **Step 4: Cut "Run it" step 6's paragraph (old line 56) to the expected output, the plain import and one link**

Replace the whole line that starts with ``Expect `tracker ready` `` with:

```markdown
Expect `tracker ready`, a status line at ≥ 10 Hz, and SLAM Studio on `ws://172.31.0.200:8766`. First time only: Layouts → Import from file → `/exploration/foxglove/cuvslam_slam_view.json`. To fly drone_1 yourself by keyboard instead, see [Fly it with the keyboard](#fly-it-with-the-keyboard-one-drone-sim-only).
```

- [ ] **Step 5: Insert the new section after "Run it"**

Insert this block after the line `New to a change (a different world, more cameras)? Test one change at a time: [VALIDATION.md](scenes/construction_site/VALIDATION.md).` and its blank line, so that `## What you should see` follows the block's trailing blank line. Copied blocks come from `docs/TELEOP.md` @ `2cbce49`: key table 136–144, Drive/Room paragraph 146–149, layout 168–175, strip bullets 183–192, Grid 194, cold start 196–239.

~~~~markdown
## Fly it with the keyboard (one drone, sim only)

You fly drone_1 by hand in the construction site, from the keyboard strip in the cuVSLAM Foxglove window. This runs in the simulator only: the drone flies on PX4's own sim estimate, and nothing flies on cuVSLAM.

Jump to: [Evidence](#evidence) · [Keys](#keys) · [Cold start](#cold-start) · [The layout](#the-layout-first-time-only) · [The strip](#the-strip)

### Evidence

- Video (simulation): [sim_keyboard_teleop_2026-11-04.mp4](../videos/sim_keyboard_teleop_2026-11-04.mp4), 79 s, recorded 2026-11-04. The strip flies drone_1 in Drive mode, beside the cuVSLAM image and the chase view.
- Test (simulation): [ledger #32](../docs/record/LEDGER.md) → [record](../docs/record/sim_teleop_frame_run1_record.md), PASS, 2026-11-03. The test script drove the stick, not the keyboard. The numbers are in [HTX-R1, S5](../docs/projects/HTX-R1.md#s5-finish-basic-sim-flight-checks--sim-only-isaac).
- Owner-confirmed (simulation), not on video or in a record, on 2026-11-05: clicking the image stops the drone, and the grid and the layout load by themselves.
- Linear (simulation): NEAR-789, NEAR-920 and NEAR-921, Done ([HTX-R1](../docs/projects/HTX-R1.md), S5). Still open there: a recorded and scored hand flight (NEAR-790), and the follow-ups NEAR-922 to NEAR-925.

### Keys

| Key | On screen | Pad equivalent |
|---|---|---|
| ↑ / ↓ | pitch: forward / back | right stick |
| ← / → | roll: slide left / right | right stick |
| W / S | climb / descend | left stick |
| A / D | turn (yaw) left / right | left stick |
| Space | STOP (every key let go, zeros published) | — |
| F | drive mode ⇄ room mode | — |
| 1 / 2 / 3 | 25 / 50 / 100 % = x.x m/s (from `safe_teleop`'s live `max_speed_mps`) | — |

Drive mode (BODY) is the default: ↑ goes where the nose points, like driving a car. Room mode (WORLD) is the
pad's behaviour: ↑ is always the far wall, like moving a chess piece. `F` only asks the relay to switch.
The switch waits until every key is up, so a push in flight is never reversed. The window header shows the
mode in words and turns red when the heading is lost.

The keyboard window instead of the strip (`tools/sim.sh keys`), with its focus and let-go rules, is in [TELEOP.md §3b](../docs/TELEOP.md#3b--keyboard-instead-of-a-pad-sim-only-ours).

### Cold start

Steps 0, 1, 6, 7 and 10 go in a terminal on the laptop. Steps 2 to 5 go in the tabs of the Terminator window that step 1 opens. Lines marked "first time only" are needed once per laptop.

```bash
# 0 · Laptop terminal, first time only — let the cuVSLAM container reach the drone side
sudo ufw allow from 172.31.0.0/24

# 1 · Laptop terminal — containers, then one Terminator window with four tabs
cd ~/AirStack-starling-max2/AirStack && ./airstack.sh up
cd ~/AirStack-starling-max2 && tools/sim_terminals.sh

# 2 · Isaac Sim tab — wait for "Ready for takeoff!"
ENV_USD=/isaac-sim/.local/share/ov/data/scenes/construction_site/construction_site_full.usdc ENABLE_CAMERA=true CAMERA_DRONES=drone_1 DRONE_USD=/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd PX4_VEHICLE_MODEL=pegasus_starling2max NUM_ROBOTS=1 SVG_DOMAIN_ID=1 PLAY_SIM_ON_START=true ISAAC_SIM_HEADLESS=false PYTHONPATH="$ISAAC_SIM_PYTHONPATH" /isaac-sim/python.sh /isaac-sim/AirStack/simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py --ext-folder ~/.local/share/ov/data/documents/Kit/shared/exts

# 3 · Interfaces tab
./src/svg_ground_control/scripts/launch_sim_interfaces.sh 1

# 4 · Cockpit tab (first time only, before the launch: bws && sws)
CFG=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/teleop_single_ours.yaml
ros2 launch svg_ground_control teleop.launch.py config:=$CFG

# 5 · Commander tab
CFG=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/teleop_single_ours.yaml
ros2 launch svg_ground_control ground_control.launch.py config:=$CFG use_foxglove_studio:=true

# 6 · New laptop terminal — the relay (the command starts it inside the robot container)
cd ~/AirStack-starling-max2 && tools/sim.sh relay

# 7 · New laptop terminal — cuVSLAM, its Foxglove window, the strip, the grid, the layout
cd ~/AirStack-starling-max2/localisation && scripts/slam_up.sh
#     First time only: import the layout, see The layout below
#     No Foxglove? `tools/sim.sh keys` (laptop) opens the keyboard window instead; it starts the relay itself.

# 8 · Take off — Basestation panel, or a robot-container shell (new laptop terminal: tools/sim_tab.sh cockpit)
ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger   # wait for "holding takeoff position" (~30 s)
ros2 service call /swarm_commander/start std_srvs/srv/Trigger

# 9 · Click the strip and fly. Land — panel "Land All", or
ros2 service call /swarm_commander/land std_srvs/srv/Trigger

# 10 · Shut down — Ctrl-C the Commander, Cockpit and Interfaces tabs first
cd ~/AirStack-starling-max2/localisation && scripts/slam_down.sh
cd ~/AirStack-starling-max2 && tools/sim.sh down
cd AirStack && ./airstack.sh down
```

### The layout (first time only)

`localisation/scripts/slam_up.sh` installs the SVG Teleop panel into the SLAM Studio. On a new machine, import the layout once:
Layouts → Import from file → `/teleop-foxglove/teleop-cuvslam.json` (the file is `tools/teleop/foxglove/teleop-cuvslam.json`).
After that, `slam_up.sh` loads the shipped layout by itself each time it starts Studio. Studio then always opens on `teleop-cuvslam` when it exists.
Your edits stay until the shipped file changes. Your saved chase view survives that change too.
The old copy is saved to `localisation/results/layout_backups/` first. `slam_up.sh` pushes nothing to your Foxglove account. Import and Save do push.
Do not import the layout again, because that makes a second `teleop-cuvslam`. Delete any extra one.
Revert in Studio shows the old cloud copy. To get the shipped layout back, run `rm localisation/results/teleop_layout.marker` and restart Studio with `slam_down.sh` then `slam_up.sh`.
It shows the cuVSLAM image and a chase view of the drone, with the strip below. The strip has the same keys and words as the keyboard window.

### The strip

- `tools/sim.sh relay` must be running. The strip cannot start it.
- Click the strip to fly. Click anything else and the drone holds.
- `FLYING drone_1` proves your keys came back from the bridge. A grey dashed frame with keys pressed means not proven, and keys may still be going out.
- If you hold ↑ and tap A, ↑ stops about 1 s after A is released, because the keyboard stops repeating the older key. Let go of ↑ and press it again.
- Keys stuck by a lost connection stop after 1 s.
- Once the strip has been used, the Tk window warns about another publisher on `/joy`. The strip itself refuses to fly while the Tk window is sending.
- The Tk window is the fallback if the strip misbehaves.
- The chase view sits behind the drone and turns with it. Tune its distance and angle in the 3D panel's settings.
- Prerequisite: `sudo ufw allow from 172.31.0.0/24`. `tools/sim.sh doctor` checks it.
- The first `slam_up.sh` after the strip was added needs `slam_down.sh` before it, so the container gets the panel mount. `slam_up.sh` says so if it is missing.

**Grid.** The grid in the cuVSLAM window grows by itself, so the drone never flies off it. `slam_up.sh` starts it. The squares start at 1 m and widen as the grid grows. It stops growing at 1600 m. The grid arrives with the shipped layout, which `slam_up.sh` loads when it starts Studio. To reset a grid grown by a bad cuVSLAM jump, stop it with `pkill -f auto_grid.py` in the exploration container and run `scripts/slam_up.sh` again. In the Basestation window turn on topic `/svg/viz/grid` once in the 3D panel's settings.

~~~~

Changed sentences to report (everything else in the copied ranges is byte-identical):
1. TELEOP 177 `**Evidence (simulation, drone_1 in the construction site).**` became the `### Evidence` heading. Each bullet now carries "(simulation)" (spec P2).
2. TELEOP 179: the numbers sentence ("Forward pushes at four headings went within 0.9° … (gate 0.30 m).") is dropped and "The numbers are in HTX-R1, S5" is added (P2 ruling: the numbers stay in HTX-R1). The link paths gain `../docs/`.
3. TELEOP 180: "Not on video or in a record, confirmed by the owner on 2026-11-05:" became "Owner-confirmed (simulation), not on video or in a record, on 2026-11-05:".
4. TELEOP 181: "Linear:" became "Linear (simulation):". The link `projects/HTX-R1.md` became `../docs/projects/HTX-R1.md`.
5. TELEOP 168: the lead `**In Foxglove.** ` is dropped, because the heading replaces it.
6. TELEOP 196: the lead `**Cold start: a keyboard session in the construction site (sim only).** ` is dropped, because the heading replaces it.
7. TELEOP 225: the step-7 comment became `#     First time only: import the layout, see The layout below` (builder check 1).
8. TELEOP 192: "After this change the first `slam_up.sh` needs" became "The first `slam_up.sh` after the strip was added needs", because "this change" points at nothing on the new page (controller ruling).

New text (not moved): the opening sentence pair, the "Jump to" line, and the Keys pointer to TELEOP §3b.

- [ ] **Step 6: The smaller edits further down**

a. "The flight on video": after the line `[contact sheet](../pictures/randompos_construction_sheet.jpg). The 64 s recording stays outside git.` add a blank line, then:

```markdown
The keyboard flight (one drone, simulation) is on video under [Evidence](#evidence).
```

b. "Prerequisites": after the row that starts `| cuVSLAM wheel, SDK source |`, add:

```markdown
| Firewall rule for the keyboard session: `sudo ufw allow from 172.31.0.0/24` (lets the cuVSLAM container reach the drone side) | you, once per laptop ([Cold start](#cold-start) step 0); `tools/sim.sh doctor` checks it |
```

c. "Folder map": replace the whole `| (auto grid) | …` row with:

```markdown
| (auto grid) | `slam_up.sh` also starts `auto_grid.py`, a ground grid that grows with the drone ([The strip](#the-strip)) |
```

- [ ] **Step 7: Verify the copies, anchors, tags, tables and counts**

Run:
```bash
cd ~/AirStack-starling-max2
python3 - <<'PY'
import subprocess
t = subprocess.run(["git","show","2cbce49:docs/TELEOP.md"],capture_output=True,text=True).stdout.splitlines()
r = open("localisation/README.md").read()
for a,b in [(136,144),(146,149),(169,175),(183,191),(194,194),(198,224),(226,239)]:
    print(a, b, "OK" if "\n".join(t[a-1:b]) in r else "MISSING")
PY
diff <(git show 2cbce49:docs/TELEOP.md | sed -n '198,239p') <(awk '/^### Cold start/{f=1} f&&/^```bash$/{p=1} p{print} p&&/^```$/{exit}' localisation/README.md)
python3 -c "import sys; sys.path.insert(0,'tools/docs_check'); import check_docs as C; C.print_result(C.check_links([C.ROOT/'localisation/README.md']))"
grep -c '(simulation)' localisation/README.md
awk 'prev ~ /^\|/ && $0 !~ /^\|/ && $0 != "" {print FILENAME": "FNR": "$0} {prev=$0}' localisation/README.md
wc -l < localisation/README.md
```
Expected: seven lines ending `OK`. Then the diff prints exactly one change, `28c28`, `<` the old `Import from file → /teleop-foxglove/teleop-cuvslam.json` comment, `>` `#     First time only: import the layout, see The layout below`. Then `[PASS] links: all 26 relative .md links in 1 files resolve`, `4`, no awk output, and `270`.

- [ ] **Step 8: Docs check**

Run: `python3 tools/docs_check/check_docs.py | tail -1`
Expected: `12 PASS · 6 WARN · 0 FAIL · 1 SKIP`

- [ ] **Step 9: Commit**

```bash
git add localisation/README.md
git commit -m "docs: localisation README gains the run chooser and the one-drone keyboard section" -m "Copied from TELEOP §3b @ 2cbce49 (keys, cold start, layout, strip, grid, evidence without numbers). TELEOP still holds its copy; the cut comes after the links move. Design: docs/superpowers/specs/2026-11-06-keyboard-docs-to-localisation-design.md."
```
Expected: the hook prints the docs-check summary with `0 FAIL` and the commit is created.

---

### Task 2: the `single-home` check (WARN), test-first

**Files:**
- Create: `tools/docs_check/single_home.txt`
- Modify: `tools/docs_check/check_docs.py` (new section before `# ---… selftest / main`; one entry in `main()`'s `checks` list)
- Modify: `tools/docs_check/README.md` (one table row, one sentence under "Registries")
- Modify: `docs/DOCS_STANDARD.md` §9 (one gate row)
- Test: `tools/tests/test_check_docs.py` (new class `SingleHome`; add `json, subprocess` to the import line)

**Interfaces:**
- Consumes: `C.ROOT`, `C.HERE`, `registry(fname)`, `corpus()`, `rel(p)`, `read(p)`, `verdict(...)`, `Result` from `check_docs.py`.
- Produces:
  - `SINGLE_HOME_EXEMPT = ("docs/plans/", "docs/superpowers/", "docs/record/", ".claude/")`
  - `SINGLE_HOME_GLOBS = ("localisation/*.md", "localisation/scenes/**/*.md", "tools/*.md", "tools/*/README.md")`
  - `NEAR_LINES = 3`
  - `flat_line(s: str) -> str`: backticks removed, runs of whitespace collapsed to one space, stripped.
  - `single_home_files() -> list[Path]`: `corpus()` plus the globs under `ROOT`, de-duplicated, files only, no path under an exempt prefix. Do not glob `localisation/**`: `localisation/foxglove/studio-data/` holds root-owned directories that cannot be read.
  - `check_single_home(rows=None) -> Result` named `"single-home"`. `rows=None` reads `registry("single_home.txt")`. Status is only ever PASS or WARN.

- [ ] **Step 1: Write the failing tests**

Change the line `import pathlib, sys, tempfile, textwrap, unittest` (line 2) of `tools/tests/test_check_docs.py` to `import json, pathlib, subprocess, sys, tempfile, textwrap, unittest` and append:

```python
class SingleHome(unittest.TestCase):                                  # design 2026-11-06: one home per moved fact, WARN only
    ONLY = ("", ["only", "Import from file → /x/layout.json", "localisation/README.md"])
    NEAR = ("", ["only", "teleop.launch.py config:=$CFG", "localisation/README.md,docs/TELEOP.md", "teleop_single_ours.yaml"])
    REQ = ("", ["require", "never go on the real drone", "docs/TELEOP.md"])

    def setUp(self):
        self._root, self._here = C.ROOT, C.HERE
        self.addCleanup(setattr, C, "ROOT", self._root); self.addCleanup(setattr, C, "HERE", self._here)

    def tree(self, d, pages):
        root = pathlib.Path(d)
        pages = {"README.md": "# r\n", "CLAUDE.md": "# c\n", "localisation/README.md": "# l\n", "docs/TELEOP.md": "# t\n", **pages}
        for name, text in pages.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True); (root / name).write_text(text)
        C.ROOT = root
        return root

    def test_copy_outside_its_home_warns_with_file_and_line(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {"localisation/README.md": "Layouts → Import from file → `/x/layout.json`\n",
                          "docs/RUNBOOK.md": "# r\nLayouts → Import from file → `/x/layout.json`\n"})
            r = C.check_single_home([self.ONLY])
            self.assertEqual(r.status, "WARN"); self.assertTrue(any(x.startswith("docs/RUNBOOK.md:2:") for x in r.details), r.details)

    def test_phrase_only_in_its_home_passes(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {"localisation/README.md": "Layouts → Import from file → `/x/layout.json`\n"})
            self.assertEqual(C.check_single_home([self.ONLY]).status, "PASS")

    def test_copies_in_tools_and_localisation_pages_are_found(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {"tools/README.md": "Import from file → /x/layout.json\n",
                          "localisation/scenes/construction_site/README.md": "Import from file → /x/layout.json\n"})
            r = C.check_single_home([self.ONLY])
            self.assertTrue(any(x.startswith("tools/README.md:1:") for x in r.details), r.details)
            self.assertTrue(any(x.startswith("localisation/scenes/construction_site/README.md:1:") for x in r.details), r.details)

    def test_dated_history_is_exempt(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {n: "Import from file → /x/layout.json\n" for n in
                          ("docs/plans/p.md", "docs/superpowers/specs/s.md", "docs/record/r_record.md", ".claude/worktrees/a/docs/TELEOP.md")})
            self.assertEqual(C.check_single_home([self.ONLY]).status, "PASS")

    def test_backticks_and_spacing_are_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {"docs/GLOSSARY.md": "Import  from file →\t`/x/layout.json`\n"})
            self.assertEqual(C.check_single_home([self.ONLY]).status, "WARN")

    def test_near_phrase_on_the_line_or_three_above_warns_inside_a_fence(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {"docs/RUNBOOK.md": "```bash\nCFG=/c/teleop_single_ours.yaml\n# a\n# b\nros2 launch p teleop.launch.py config:=$CFG\n```\n"})
            r = C.check_single_home([self.NEAR])
            self.assertEqual(r.status, "WARN"); self.assertTrue(any(x.startswith("docs/RUNBOOK.md:5:") for x in r.details), r.details)

    def test_near_phrase_four_lines_above_or_below_passes(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {"docs/RUNBOOK.md": "CFG=/c/teleop_single_ours.yaml\n# a\n# b\n# c\nros2 launch p teleop.launch.py config:=$CFG\n",
                          "docs/SCENARIOS.md": "CFG=/c/teleop_real_ours.yaml\nros2 launch p teleop.launch.py config:=$CFG\nin sim use teleop_single_ours.yaml\n"})
            self.assertEqual(C.check_single_home([self.NEAR]).status, "PASS")

    def test_require_missing_warns_and_a_wrapped_phrase_passes(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {})
            r = C.check_single_home([self.REQ])
            self.assertEqual(r.status, "WARN"); self.assertTrue(any("docs/TELEOP.md" in x and "never go on the real drone" in x for x in r.details), r.details)
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {"docs/TELEOP.md": "**Sim only.** These never go on the\nreal drone.\n"})
            self.assertEqual(C.check_single_home([self.REQ]).status, "PASS")

    def test_listed_home_that_does_not_exist_warns(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {})
            r = C.check_single_home([("", ["only", "x y", "localisation/GONE.md"])])
            self.assertEqual(r.status, "WARN"); self.assertTrue(any("localisation/GONE.md" in x and "does not exist" in x for x in r.details), r.details)

    def test_bad_rows_and_a_missing_registry_warn_never_fail(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {})
            r = C.check_single_home([("", ["maybe", "x", "a.md"]), ("", ["only", "x"])])
            self.assertEqual(r.status, "WARN"); self.assertEqual(sum("malformed" in x for x in r.details), 2, r.details)
            C.HERE = pathlib.Path(d)                                    # no single_home.txt here
            r = C.check_single_home()
            self.assertEqual(r.status, "WARN"); self.assertIn("single_home.txt", r.summary)

    def test_shipped_registry_has_the_designs_rows(self):
        rows = C.registry("single_home.txt")
        self.assertEqual([(f[0].strip(), f[1].strip()) for _, f in rows],
                         [("only", "Import from file → /teleop-foxglove/teleop-cuvslam.json"), ("only", "teleop.launch.py config:=$CFG"),
                          ("only", "sim_keyboard_teleop_2026-11-04.mp4"), ("require", "never go on the real drone")])
        self.assertEqual(rows[1][1][3].strip(), "teleop_single_ours.yaml")
        for _, f in rows:
            for fn in f[2].split(","):
                self.assertTrue((self._root / fn.strip()).is_file(), fn)

    def test_registered_in_the_checker_run(self):
        out = subprocess.run([sys.executable, "-I", str(pathlib.Path(C.__file__)), "--json"], capture_output=True, text=True, cwd=self._root).stdout
        self.assertIn("single-home", [r["check"] for r in json.loads(out)["results"]])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/AirStack-starling-max2 && python3 -m unittest discover -s tools/tests -p 'test_check_docs.py' -k SingleHome 2>&1 | tail -3`
Expected: `FAILED (failures=…, errors=…)` covering all 12 tests: `AttributeError: module 'check_docs' has no attribute 'check_single_home'`, a `TypeError` on the missing registry, and the `assertIn` failure on the checker run.

- [ ] **Step 3: Create `tools/docs_check/single_home.txt`**

The fields are separated by real TAB characters. Write the file with `printf` or Python, not an editor that turns tabs into spaces. `→` is U+2192. Header comments start with `#`.

```text
# single_home.txt — facts that live in one place (design docs/superpowers/specs/2026-11-06-keyboard-docs-to-localisation-design.md).
# Format (tab-separated): <kind><TAB><phrase><TAB><file,file>[<TAB><near phrase>]
#   only    — the phrase may appear only in the listed files. With a near phrase, a line counts only when the near
#             phrase is on it or on one of the 3 lines above it.
#   require — the phrase must appear in each listed file.
# Matching ignores backticks and runs of whitespace. Every row is WARN, never FAIL.
# Not scanned (dated history): docs/plans/, docs/superpowers/, docs/record/, .claude/.
only<TAB>Import from file → /teleop-foxglove/teleop-cuvslam.json<TAB>localisation/README.md
only<TAB>teleop.launch.py config:=$CFG<TAB>localisation/README.md,docs/TELEOP.md<TAB>teleop_single_ours.yaml
only<TAB>sim_keyboard_teleop_2026-11-04.mp4<TAB>localisation/README.md,docs/projects/HTX-R1.md
require<TAB>never go on the real drone<TAB>docs/TELEOP.md
```

Run: `grep -v '^#' tools/docs_check/single_home.txt | awk -F'\t' '{print NF}'`
Expected: `3`, `4`, `3`, `3`

- [ ] **Step 4: Implement the check in `check_docs.py`**

Add a section `# ----… 21. single home` with the constants and the three functions from the Interfaces block. Rules for `check_single_home(rows=None) -> Result`:
- `rows is None` → `registry("single_home.txt")`. If that is `None`, return `Result("single-home", "WARN", "tools/docs_check/single_home.txt missing")`.
- Strip every field. A row is well formed when kind ∈ {`only`, `require`}, there are ≥ 3 fields and the phrase is non-empty. Otherwise add the warning `malformed registry row: {fields}` and skip the row.
- Every listed file that does not exist (both kinds) → `{fn}: listed file does not exist ('{phrase}')`.
- `require`: `flat_line(phrase)` must be in `flat_line(whole file text)`, so a phrase wrapped over two lines still counts. Otherwise → `{fn}: required phrase '{phrase}' missing`.
- `only`: for every file in `single_home_files()` whose `rel()` is not a listed home, read line by line (fenced lines included). Line *i* (1-based) is a hit when `flat_line(phrase)` is in `flat_line(line)` and, if a near phrase is given, `flat_line(near)` is in one of lines `max(1, i-NEAR_LINES)…i`. Each hit → `{rel}:{i}: '{phrase}' outside its home ({', '.join(homes)})`. A file that `read()` returns `None` for is skipped.
- Return `verdict("single-home", [], warns, f"{n} phrase(s) in their single homes", warn_msg=f"{len(warns)} single-home warning(s)")`, with `n` = the number of well-formed rows. Nothing goes in the FAIL list.

Register it in `main()`: put `check_single_home` in `checks` right after `check_purpose_lines`, before `check_change_log`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s tools/tests -p 'test_check_docs.py' -k SingleHome 2>&1 | tail -3`
Expected: `Ran 12 tests` … `OK`

- [ ] **Step 6: Run the checker on the real tree**

Run: `python3 tools/docs_check/check_docs.py | grep -A4 '^\[[A-Z]*\] single-home'; python3 tools/docs_check/check_docs.py | tail -1`
Expected (TELEOP still holds its copy, so these warnings prove the check works):
```
[WARN] single-home: 4 single-home warning(s)
    docs/TELEOP.md:169: 'Import from file → /teleop-foxglove/teleop-cuvslam.json' outside its home (localisation/README.md)
    docs/TELEOP.md:225: 'Import from file → /teleop-foxglove/teleop-cuvslam.json' outside its home (localisation/README.md)
    docs/TELEOP.md:178: 'sim_keyboard_teleop_2026-11-04.mp4' outside its home (localisation/README.md, docs/projects/HTX-R1.md)
    docs/TELEOP.md: required phrase 'never go on the real drone' missing
```
and `12 PASS · 7 WARN · 0 FAIL · 1 SKIP`.

- [ ] **Step 7: Document the check**

a. `tools/docs_check/README.md`: add this row to the check table after `purpose-lines`:
```markdown
| single-home | each `only` row of `single_home.txt` appears in no live page but its listed files (with a near phrase: only lines that have it on them or up to 3 lines above); each `require` phrase is in its listed files. Backticks and runs of spaces are ignored. Live pages: README, CLAUDE.md, docs/**, localisation/*.md, localisation/scenes/**, tools/*.md, tools/*/README.md; docs/plans/, docs/superpowers/, docs/record/ are exempt | WARN |
```
Append to the "Registries:" paragraph: `` `single_home.txt` rows are `kind<TAB>phrase<TAB>file,file[<TAB>near phrase]`, kind `only` or `require`. ``

b. `docs/DOCS_STANDARD.md` §9, add after the `host unit tests` row:
```markdown
| one home per moved fact (WARN) | `tools/docs_check/check_docs.sh`, check `single-home` | no WARN: each phrase in `tools/docs_check/single_home.txt` sits only in its listed files, and every `require` phrase is present |
```
Neither text may quote a registry phrase. Quoting one would make the page a copy.

- [ ] **Step 8: Full suite and docs check**

Run: `python3 -m unittest discover -s tools/tests 2>&1 | grep -E '^(Ran|OK|FAILED)'; python3 tools/docs_check/check_docs.py | tail -1`
Expected: `Ran 840 tests …`, `OK (skipped=1)`, then `12 PASS · 7 WARN · 0 FAIL · 1 SKIP`

- [ ] **Step 9: Commit**

```bash
git add tools/docs_check/single_home.txt tools/docs_check/check_docs.py tools/tests/test_check_docs.py tools/docs_check/README.md docs/DOCS_STANDARD.md
git commit -m "docs_check: single-home check (WARN) and its registry" -m "Each moved keyboard fact has one home: the layout import and the video only in localisation/README.md (video also HTX-R1), the keyboard launch with teleop_single_ours.yaml in the README and TELEOP §4, and the TELEOP §3b warning must exist. Dated history is exempt. Warns on TELEOP's old copy until the cut. Design: docs/superpowers/specs/2026-11-06-keyboard-docs-to-localisation-design.md."
```
Expected: the hook prints the docs-check summary (`0 FAIL`) and `tools/tests OK`, and the commit is created.

---

### Task 3: retarget the inbound links

**Files:**
- Modify: `docs/RUNBOOK.md:165`, `docs/GLOSSARY.md:194`, `docs/CONFIG.md:205`, `docs/projects/HTX-R1.md:95`, `tools/README.md:39-40`, `CLAUDE.md:25,37`, `README.md:23,57,65`, `docs/TELEOP.md:25,276`

**Interfaces:**
- Consumes: Task 1's anchors.
- Produces: no live page sends a reader to TELEOP §3b for keys, cold start, strip, layout or video.

- [ ] **Step 1: In-line replacements (old → new, each old text occurs once)**

1. `docs/RUNBOOK.md`: `the cold start, the keys and the video are in [TELEOP.md](TELEOP.md) §3b.` → `the cold start, the keys and the video are in [localisation/README.md](../localisation/README.md#fly-it-with-the-keyboard-one-drone-sim-only).`
2. `docs/GLOSSARY.md` (Drive mode entry): `Sim only ([TELEOP.md](TELEOP.md) §3b).` → `Sim only ([keys](../localisation/README.md#keys)).`
3. `docs/CONFIG.md`: `(Drive/Room mode, [TELEOP.md](TELEOP.md) §3b)` → `(Drive/Room mode, [keyboard session](../localisation/README.md#fly-it-with-the-keyboard-one-drone-sim-only))`
4. `docs/projects/HTX-R1.md` (NEAR-921 paragraph, in-line, net zero lines): `([TELEOP.md](../TELEOP.md) §3b)` → `([keyboard session](../../localisation/README.md#fly-it-with-the-keyboard-one-drone-sim-only))`
5. `tools/README.md` `teleop/` row: `` `relay stop` always works — [TELEOP.md §3b](../docs/TELEOP.md) | `` → `` `relay stop` always works — the window: [TELEOP.md §3b](../docs/TELEOP.md#3b--keyboard-instead-of-a-pad-sim-only-ours); the session: [localisation/README.md](../localisation/README.md#fly-it-with-the-keyboard-one-drone-sim-only) | ``
6. `tools/README.md` `teleop/foxglove/` row: `Sim only — [TELEOP.md §3b](../docs/TELEOP.md) |` → `Sim only — [localisation/README.md](../localisation/README.md#fly-it-with-the-keyboard-one-drone-sim-only) |`
7. `CLAUDE.md` TELEOP row: replace the cell ``gamepad teleop (real drone) and sim keyboard teleop (Drive mode, Foxglove strip, cold start, video), the two fences, controller profiles, CMU `teleop.md` corrections`` with `` gamepad teleop (real drone), the sim keyboard window and its sim-only warning (§3b), the two fences, controller profiles, CMU `teleop.md` corrections; the sim keyboard session (keys, Drive mode, strip, cold start, video) is in [localisation/README.md](localisation/README.md#fly-it-with-the-keyboard-one-drone-sim-only) ``
8. `CLAUDE.md` localisation row: `— **sim-only exploration, nothing flies**.` → `— **sim-only exploration, nothing flies on cuVSLAM**; it also holds the one-drone [keyboard session](localisation/README.md#fly-it-with-the-keyboard-one-drone-sim-only).`
9. `README.md` "I want to…" row: `| **fly in the construction site with the camera** (sim stereo VO) | [localisation/README.md](localisation/README.md) |` → `| **fly in the construction site** (sim): the scored camera run, or drone_1 yourself by keyboard | [localisation/README.md](localisation/README.md), its first table picks the run |`
10. `README.md` doc table: `| Gamepad flying through the commander, and keyboard flying in sim |` → `| Gamepad flying through the commander; the sim keyboard session is in [localisation/README.md](localisation/README.md#fly-it-with-the-keyboard-one-drone-sim-only) |`
11. `README.md` doc table: `| Camera-world sim runs: construction-site world, stereo VO (cuVSLAM), scoring. A sibling` → `| Camera-world sim runs: construction-site world, stereo VO (cuVSLAM), scoring, and the one-drone [keyboard session](localisation/README.md#fly-it-with-the-keyboard-one-drone-sim-only). A sibling`
12. `docs/TELEOP.md` intro (line 25): `That path has flown in sim: keys, cold start, video and test are in §3b.` → `That path has flown in sim. The keys, cold start, video and test are in [localisation/README.md](../localisation/README.md#fly-it-with-the-keyboard-one-drone-sim-only). The keyboard window is §3b.`
13. `docs/TELEOP.md` §4 (line 276): ``For the keyboard window use `tools/sim.sh keys`. A pad in sim needs `tools/sim.sh relay` (§3b).`` → ``For the keyboard window use `tools/sim.sh keys` (§3b). A pad in sim needs `tools/sim.sh relay` (§3b). The whole keyboard session, from a cold start, is in [localisation/README.md](../localisation/README.md#cold-start).``

Links that stay on TELEOP: `docs/TELEOP.md:4`, `:21` and `:52` (the keyboard window and the relay live in §3b), and `docs/MIGRATION.md:135` (history).

- [ ] **Step 2: Budgets and tables**

Run: `wc -l < docs/projects/HTX-R1.md; awk 'prev ~ /^\|/ && $0 !~ /^\|/ && $0 != "" {print FILENAME": "FNR": "$0} {prev=$0}' README.md CLAUDE.md docs/CONFIG.md tools/README.md`
Expected: `250` and no awk output.

- [ ] **Step 3: Links resolve (corpus and the two pages the checker skips)**

Run: `python3 tools/docs_check/check_docs.py | grep -E '^\[(PASS|FAIL)\] (links|page-budgets|real-page-hygiene)'; python3 -c "import sys; sys.path.insert(0,'tools/docs_check'); import check_docs as C; C.print_result(C.check_links([C.ROOT/'localisation/README.md', C.ROOT/'tools/README.md']))"`
Expected: `[PASS] links: …`, `[PASS] real-page-hygiene: …`, `[PASS] page-budgets: …`, then `[PASS] links: all 37 relative .md links in 2 files resolve` (26 in the README, 11 in tools/README.md).

- [ ] **Step 4: Every `§3b` left on a live page is about the Tk window**

Run: `git grep -n '§3b' -- '*.md' ':!AirStack' ':!docs/plans' ':!docs/superpowers' ':!docs/record' ':!.claude' | cut -c1-120`
Expected: only `CLAUDE.md:25` (the window), `docs/TELEOP.md:4`, `:21`, `:25` ("The keyboard window is §3b"), `:52`, `:276`, `localisation/README.md` (the Keys pointer) and `tools/README.md:39` (the window). No hit in RUNBOOK, GLOSSARY, CONFIG, HTX-R1 or `tools/README.md:40`.

- [ ] **Step 5: Commit**

```bash
git add docs/RUNBOOK.md docs/GLOSSARY.md docs/CONFIG.md docs/projects/HTX-R1.md tools/README.md CLAUDE.md README.md docs/TELEOP.md
git commit -m "docs: keyboard-session links point at localisation/README.md" -m "RUNBOOK, GLOSSARY (Drive mode), CONFIG (teleop_single_ours row), HTX-R1 NEAR-921, tools/README teleop rows, CLAUDE.md and README doc rows, TELEOP intro and §4. Links about the Tk window keep pointing at TELEOP §3b."
```
Expected: hook `0 FAIL`, `tools/tests OK`, commit created.

---

### Task 4: cut TELEOP §3b to the warning, the Tk-window rules and the pointer

**Files:**
- Modify: `docs/TELEOP.md:130-239` (the heading line through the cold start's closing fence)

**Interfaces:**
- Consumes: Task 1's section, Task 2's check, Task 3's links.
- Produces: the `require` phrase in `docs/TELEOP.md`. `single-home` turns PASS.

- [ ] **Step 1: Replace lines 130–239**

Replace everything from `### 3b · Keyboard instead of a pad (sim only, ours)` down to and including the closing fence of the cold start. That fence is the line ```` ``` ```` right before the blank line that precedes `## 4 · Quick start — SIM (M1 rehearsal)`. Replace it with this block. The heading is unchanged. The four Tk-window paragraphs are TELEOP 132–134, 151–155, 157–158, 160–162 and 164–166, byte-identical.

```markdown
### 3b · Keyboard instead of a pad (sim only, ours)

**Sim only.** Drive mode, the relay and `teleop_single_ours.yaml` (it sets `fence_enabled: false` and `teleop_fence_enabled: false`) are for the simulator only and never go on the real drone. Real flying is §5 with `teleop_real_ours.yaml`.

No pad? `tools/sim.sh keys` opens a small window that turns key presses into the same `/joy` stream a pad
sends. `safe_teleop` then flies the drone unchanged, with its fences, hold and speed cap. Start `safe_teleop`
first (§4), then run `keys` in a terminal tab and click the window.

Drive mode needs `teleop_single_ours.yaml`. `keys` starts the relay, a small node between `safe_teleop` and the
commander that turns the stick into room velocities. With a pad, start it with `tools/sim.sh relay` and stop it
with `tools/sim.sh relay stop`. A grey Room-mode header means the relay gets no stick: the old yaml is loaded, or
`safe_teleop` is not running. A red "Keys not reaching the drone" header means the relay is silent: close the
window, then run `tools/sim.sh keys`.

`safe_teleop` commands velocities, so roll slides the drone sideways and pitch moves it forward or back.
Two arrow keys together fly no faster than one. There is no stick lock on the keyboard.

Let go of every key and the drone holds. A key also counts as let go when the window loses focus, when it is
minimised, or after 1 s with no key event (a held key keeps auto-repeating). Closing the window or Ctrl-C
publishes zeros first. If the window dies, `safe_teleop` stops the drone after 0.5 s without `/joy`.

Only one source may publish `/joy`. The window warns while another one does, such as a plugged-in pad.
It reads `safe_teleop`'s controller profile and refuses a mismatch; `teleop_single_ours.yaml` pins
`dragonrise_usb`, the default. Sim only: it has not flown the real drone.

**Keys, cold start, strip, layout, evidence and video:** [localisation/README.md, Fly it with the keyboard](../localisation/README.md#fly-it-with-the-keyboard-one-drone-sim-only).
They sit beside the cuVSLAM Foxglove window that `slam_up.sh` opens, where the sim keyboard session is flown.
```

Removed from TELEOP (now in the README): the key table (136–144), the Drive/Room paragraph (146–149), "In Foxglove" (168–175), Evidence (177–181), the strip bullets (183–192), Grid (194) and the cold start (196–239).

- [ ] **Step 2: Verify the kept paragraphs are byte-identical**

Run:
```bash
python3 - <<'PY'
import subprocess
t = subprocess.run(["git","show","2cbce49:docs/TELEOP.md"],capture_output=True,text=True).stdout.splitlines()
r = open("docs/TELEOP.md").read()
for a,b in [(132,134),(151,155),(157,158),(160,162),(164,166)]:
    print(a, b, "OK" if "\n".join(t[a-1:b]) in r else "MISSING")
PY
wc -l < docs/TELEOP.md
```
Expected: five lines ending `OK`, then `422`.

- [ ] **Step 3: Done-when 2 and Review Focus 1**

Run:
```bash
grep -c '^| Key | On screen' docs/TELEOP.md; grep -c 'Cold start: a keyboard session' docs/TELEOP.md; grep -c '^\*\*Evidence' docs/TELEOP.md
grep -A2 '^### 3b · Keyboard instead of a pad (sim only, ours)$' docs/TELEOP.md | sed -n 3p | cut -c1-60
awk 'prev ~ /^\|/ && $0 !~ /^\|/ && $0 != "" {print FILENAME": "FNR": "$0} {prev=$0}' docs/TELEOP.md
```
Expected: `0`, `0`, `0`, then the line ``**Sim only.** Drive mode, the relay and `teleop_single_ours.`` (the warning is the first text under the heading), and no awk output.

- [ ] **Step 4: Docs check, with single-home now PASS**

Run: `python3 tools/docs_check/check_docs.py | grep -E '^\[[A-Z]+\] (single-home|links|warnings-registered)'; python3 tools/docs_check/check_docs.py | tail -1`
Expected: `[PASS] links: …`, `[WARN] warnings-registered: 28/30 ⚠️ lines not in safety_registry.txt` (unchanged), `[PASS] single-home: 4 phrase(s) in their single homes`, then `13 PASS · 6 WARN · 0 FAIL · 1 SKIP`.

- [ ] **Step 5: Commit**

```bash
git add docs/TELEOP.md
git commit -m "docs: TELEOP §3b keeps the sim-only warning and the keyboard-window rules; the session moved to localisation/README.md" -m "Removed from TELEOP: key table, Drive/Room paragraph, In Foxglove, Evidence, strip bullets, Grid, cold start (all in localisation/README.md since the previous commits). The 3b heading keeps its words: CHANGES.md cites TELEOP §3b. TELEOP no longer holds results (DOCS_STANDARD §1)."
```
Expected: hook `0 FAIL`, commit created.

---

### Task 5: "nothing has flown" names the real drone on seven pages

**Files:**
- Modify: `README.md:9`, `CLAUDE.md:8`, `docs/MILESTONES.md:5`, `docs/projects/HTX-R2.md:1`, `docs/projects/HTX-R1.md:1`, `docs/TELEOP.md:22`, `docs/PREFLIGHT.md:1,5`

**Interfaces:**
- Consumes: nothing from earlier tasks (independent).
- Produces: PREFLIGHT token `v2026-11-06`.

- [ ] **Step 1: In-line replacements (old → new)**

1. `README.md:9`: `**nothing on this software has flown**` → `**nothing on this software has flown on the real drone**`
2. `CLAUDE.md:8`: `**nothing on this software has flown; sim results in` → `**nothing on this software has flown on the real drone; sim results in`
3. `docs/MILESTONES.md:5`: `` (`yikuan/SVG_ground_control_dev` @ `b21d28c`) has flown; `` → `` (`yikuan/SVG_ground_control_dev` @ `b21d28c`) has flown on the real drone; ``
4. `docs/projects/HTX-R2.md:1`: `RECORD · REAL DRONE — nothing on this software has flown.` → `RECORD · REAL DRONE — nothing on this software has flown on the real drone.`
5. `docs/projects/HTX-R1.md:1`: `nothing here has flown.` → `nothing here flew a real drone.`
6. `docs/TELEOP.md:22`: `⏳ **nothing below has flown at STE.**` → `⏳ **nothing below has flown on the real drone at STE.**`
7. `docs/PREFLIGHT.md:5`: `· nothing on this software has flown; hazards:` → `· nothing on this software has flown on the real drone; hazards:`
8. `docs/PREFLIGHT.md:1`: `— v2026-11-02 —` → `— v2026-11-06 —` (same commit as item 7; the laminated card needs a reprint, see the report).

`docs/SCENARIOS.md` already says "on the real drone" and is not touched. Add no softening words.

- [ ] **Step 2: Budgets and the PREFLIGHT token**

Run: `wc -l < docs/projects/HTX-R1.md; wc -l < docs/MILESTONES.md; python3 tools/docs_check/check_docs.py | grep -E '^\[[A-Z]+\] (preflight-date|iron-rules|page-budgets|real-page-hygiene)'`
Expected: `250`, `36`, `[PASS] iron-rules: …`, `[PASS] real-page-hygiene: …`, `[PASS] preflight-date: token v2026-11-06`, `[PASS] page-budgets: …`

- [ ] **Step 3: Goal 5 / Done-when 5**

Run: `git grep -n -A1 'has flown' -- '*.md' ':!AirStack' ':!docs/plans' ':!docs/superpowers' ':!docs/record' ':!.claude' | cut -c1-200`
Expected hits: `CLAUDE.md:8`, `README.md:9`, `docs/MILESTONES.md:5`, `docs/PREFLIGHT.md:5`, `docs/TELEOP.md:22` and `docs/projects/HTX-R2.md:1`, each with "on the real drone" on the hit line; `docs/SCENARIOS.md:19`, with "on the real drone." on the `-20-` line; and `docs/TELEOP.md:25` ("has flown in sim"). No other hit. Read each one: it must still read as a warning about the real drone and must not imply a sim result is real.

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md docs/MILESTONES.md docs/projects/HTX-R2.md docs/projects/HTX-R1.md docs/TELEOP.md docs/PREFLIGHT.md
git commit -m "docs: \"nothing has flown\" says the real drone on seven pages (PREFLIGHT v2026-11-06)" -m "The keyboard has flown in sim, so the bare sentence read as a contradiction (owner, 2026-11-06). Hazard meaning unchanged. PREFLIGHT card version bumped: reprint the laminated card."
```
Expected: hook `0 FAIL`, commit created.

---

### Task 6: final verification against the spec's Done-when, then the mirror

**Files:** none modified.

- [ ] **Step 1: Done-when 1, the docs check**

Run: `python3 tools/docs_check/check_docs.py | grep -E '^\[[A-Z]+\] single-home'; python3 tools/docs_check/check_docs.py | tail -1`
Expected: `[PASS] single-home: 4 phrase(s) in their single homes` and `13 PASS · 6 WARN · 0 FAIL · 1 SKIP`

- [ ] **Step 2: Full unit tests**

Run: `python3 -m unittest discover -s tools/tests 2>&1 | grep -E '^(Ran|OK|FAILED)'`
Expected: `Ran 840 tests …` and `OK (skipped=1)`

- [ ] **Step 3: Done-when 2**

Run Task 4 Step 3's commands again.
Expected: the same output (`0`, `0`, `0`, the warning line, no awk output).

- [ ] **Step 4: Done-when 3, every retargeted link resolves**

Run Task 3 Step 3's commands again.
Expected: both `links` results PASS.

- [ ] **Step 5: Done-when 4, newcomer line counts**

Run:
```bash
f=localisation/README.md
top=$(grep -n '^| Fly it yourself by keyboard' $f | cut -d: -f1)
sec=$(grep -n '^## Fly it with the keyboard' $f | cut -d: -f1)
es=$(grep -n '^### Evidence' $f | cut -d: -f1); ee=$(grep -n '^- Video (simulation)' $f | cut -d: -f1)
ks=$(grep -n '^### Keys' $f | cut -d: -f1);     ke=$(grep -n 'turns red when the heading is lost' $f | cut -d: -f1)
cs=$(grep -n '^### Cold start' $f | cut -d: -f1); ce=$(awk -v s=$cs 'NR>s && /^```$/ {print NR; exit}' $f)
echo "from the page top via the chooser: cold start $((top+ce-cs+1)) · keys $((top+ke-ks+1)) · flown+video $((top+ee-es+1))"
echo "from the section anchor:           cold start $(( (es-sec) + ce-cs+1 )) · keys $((ke-sec+1)) · flown+video $((ee-sec+1))"
```
Expected: `cold start 58 · keys 28 · flown+video 15`, then `cold start 52 · keys 29 · flown+video 9`. Gates: ≤ 70, ≤ 30, ≤ 15. Before (spec table): about 320, 207 and 220 lines over 2–3 pages.

The controller then dispatches the saved agent `panel-newcomer-reader` (read-only). The prompt has the three BEFORE questions, the start at the root `README.md`, and the counting rule in spec builder check 4. The agent reports lines read and clicks for each question. Record its numbers next to the mechanical ones in the final report. A miss sends the opening text back for shortening (builder check 4), never the cold-start block.

- [ ] **Step 6: Done-when 5**

Run Task 5 Step 3's command again.
Expected: the same hit list.

- [ ] **Step 7: Done-when 6, the cold start matches 2cbce49**

Run: `diff <(git show 2cbce49:docs/TELEOP.md | sed -n '198,239p') <(awk '/^### Cold start/{f=1} f&&/^```bash$/{p=1} p{print} p&&/^```$/{exit}' localisation/README.md)`
Expected: exactly one hunk `28c28`, which is the step-7 layout comment.

- [ ] **Step 8: Working tree and history**

Run: `git status --short; git log --oneline -6`
Expected: only the four untracked items that were there before (`.superpowers/`, `QGroundControl-x86_64.AppImage`, `docs/record/sim_hover_step_run4/`, `"starling max2 voxl setup.txt"`), and the five commits of Tasks 1–5 above `5b19d3b` (plus the plan's own commit if the controller made one).

- [ ] **Step 9: Pull the mirror**

Run: `git -C ~/Documents/GitHub/AirStack-starling-max2 pull ~/AirStack-starling-max2 main`
Expected: `Fast-forward` and the files of Tasks 1–5 listed. Do not push. The owner pushes from GitHub Desktop.
