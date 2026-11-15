# Runbook follow-through — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. One implementer and one reviewer per task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/RUNBOOK.md` rebuilt so a person picks a session in the first screen and runs it from its heading to its own shutdown in the step form of the approved B9 sample, with nothing lost.

**Architecture:** inventory first (scratch, out of the repo); then the standard, then the destination pages receive what leaves RUNBOOK; RUNBOOK sections are drafted in parallel into scratch files and assembled one section per commit in page order; prose references retargeted; checker rules (D11) last, test-first.

**Tech stack:** Markdown; `tools/docs_check/check_docs.py` (python3 stdlib); `unittest` in `tools/tests/`; three scratch scripts (python3 stdlib).

**Spec:** [design](../specs/2026-11-14-runbook-follow-through-design.md) (decisions D1 to D11, non-goals, constraints, "Done when") and the approved [B9 sample](../specs/2026-11-14-runbook-follow-through-sample-B9.md) ("build the whole run book like the sample"). Read both before any task. This plan cites decisions by number and does not restate them.

**Worktree:** `/home/jeremychia/AirStack-starling-max2-docs`, branch `docs/runbook-follow-through`. Never open `/home/jeremychia/AirStack-starling-max2` (the live clone). Never push.

## Global constraints

- `OLD` = `docs/RUNBOOK.md` at `ac197f7` (1008 lines). All line numbers below are OLD's: `git show ac197f7:docs/RUNBOOK.md | cat -n`. The working file adds `ba816ea` (six safety-wording fixes, no command changed); everything `ba816ea` added is kept. (The design's "1024 lines, 9,739 words" are the working file's numbers; its line numbers are OLD's.)
- `SCR` = `/tmp/claude-1000/-home-jeremychia/9eaa2356-e0ee-42ff-a000-1884f1956710/scratchpad/runbook-build`. Scripts, inventory, drafts and reports live there, never in the repo.
- Never edit: `docs/PREFLIGHT.md`, `docs/record/**` (LEDGER rows are append-only; nothing is appended here), `docs/plans/**`, `docs/superpowers/specs/**`, `AirStack/**`, the `IRON_RULES` block in `CLAUDE.md`. No change to any command, config or tool (non-goals). The `RUNBOOK` entry of `BUDGETS` in `check_docs.py` stays 2500 (non-goal).
- The working tree holds an uncommitted edit to the design spec that belongs to the orchestrator. Stage by explicit path only (CLAUDE.md "More than one Claude session"): never `git add -A`, `git commit -a`, `git stash`, `git reset --hard`, `git checkout -- <file>`, `git clean`. Never `--no-verify`.
- After every commit: `tools/docs_check/check_docs.sh | tail -1` prints `… 0 FAIL …` (baseline today: `13 PASS · 6 WARN · 0 FAIL · 1 SKIP`). The pre-commit hook runs it, and also `python3 -m unittest discover -s tools/tests` when `tools/` is staged (baseline `Ran 986 tests`, `OK (skipped=1)`).
- Facts, commands, anchors and paths are copied from the repo, never from memory.
- Commit subjects: `docs: <what>` for pages, `docs_check: <what>` for the checker (this repo's style).

## Shared definitions (used by the scripts, the drafts and the checker)

- **Heading:** a line starting `#` **outside** a ``` / ~~~ fence (bash comments inside fences are not headings).
- **Segments of RUNBOOK:** `A` = `## A ·` to `## B ·`; `B` = `## B ·` to `### B9 —`; `B9` = `### B9 —` to `### B10 —`; `B10` = `### B10 —` to `## C ·`; `C` = `## C ·` to `### C9 —`; `C9` = `### C9 —` to `## D ·`; `Pocket` = `## Pocket reference` to `### Sim launch variants`; `Variants` = `### Sim launch variants` to end of file. **Real sequences** = B, B9, B10, C, C9. No new heading may be added inside a sequence.
- **Headings kept byte-identical** (anchors): line 1 title; the `## A` heading (line 39) and `### A0`…`### A4` (51, 64, 92, 109, 128); `## B · REAL DRONE session (mocap room)`; `### B9 — Fly one real drone with the gamepad`; `### B10 — Two real drones, one flown by hand`; `## C · GOAL FLIGHTS (fly to commanded waypoints)`; `### C9 — Two real drones with the collision filter (CBF)`; `## D · POST-FLIGHT — pull & review the PX4 logs`; `## Pocket reference`; `### Sim launch variants`. Linked from other files today: `#b9--fly-one-real-drone-with-the-gamepad`, `#b10--two-real-drones-one-flown-by-hand`, `#c9--two-real-drones-with-the-collision-filter-cbf` (19 links); in-page: `#sim-launch-variants`, `#b--real-drone-session-mocap-room`. **Headings removed:** `### Alternatives to the tabs` (D10), `### C8 — parameters you must NEVER set live (they look harmless and are not)` (D10). Neither is linked from anywhere; Task 1 confirms.
- **Command line:** a non-blank line inside a fence whose stripped form does not start with `#`, with a trailing comment (regex `\s+#\s.*$`) removed, then stripped. Inline command: a backtick span in prose starting with `ros2 `, `./`, `cd `, `ssh `, `scp `, `adb `, `docker `, `tools/`, `python3 `, `ping `, `ss `, `rviz2 `, `readlink `, `bws`, `voxl_`, `~/`.
- **Laptop line:** contains `airstack.sh`, `mocap.sh` or `QGroundControl-x86_64.AppImage`. **Container line:** starts with `ros2 `.
- **Shared opening (D9):** in each real sequence, the lines between every `<!-- shared-opening -->` and the next `<!-- /shared-opening -->`, concatenated in order (several regions per sequence are allowed). **Normalisation**, applied in this order: drop fence lines and blank lines; `drone_\d+` → `drone_N`; `10\.40\.2\.\d+` → `IP`; ` target_systems:=[\d,]+` → removed; `target_system=\d+` → `target_system=N`; `MOCAP_BODIES="[^"]*" ` → removed; leading `**\d+ ·` → `**N ·`; repeatedly `drone_N(, | and |,| )drone_N` → `drone_N`; drop a line identical to the line before it. All five real sequences must give the same list.
- **Chooser:** a markdown table whose header line is exactly the line below, starting at line 15 or earlier:

  ```
  | Session | SIM or REAL | Go to |
  ```
- **Stop table:** the markdown table that directly follows a line starting `**Stop table.**`. Gap = (line of the first `/swarm_commander/takeoff` after it) − (line of its last row); at most 15 (D6).

## Order and parallelism

| Task | What | Runs | Commits |
|---|---|---|---|
| 1 | inventory + `cmdset.py`, `rows.py`, `splice.py` | first; parallel with 2 and 3 | none |
| 2 | canonical shared opening + `opening_check.py` | parallel with 1 and 3 | none |
| 3 | DOCS_STANDARD "Procedure pages" | parallel with 1 and 2 | 1st commit |
| 4 | destinations I: DRONE_SETUP, CONFIG, ARCHITECTURE | after 1; drafting parallel with 5 | after 3 |
| 5 | destinations II: HTX-R2, HTX-R1, MIGRATION, SCENARIOS, TELEOP, BASESTATION, MOCAP, TROUBLESHOOTING | after 1 | after 4 |
| 6–12 | drafts: intro+tail, A, B, B9, B10, C, C9 | after 1 and 2; parallel with each other (Task 11 waits for Task 8's reviewed draft) | none |
| 13a–13h | assembly, one section per commit: intro, A, B, B9, B10, C, C9, tail | strictly in this order, after 4 and 5 are committed and the section's draft is reviewed | one each |
| 14 | prose-reference sweep on other pages | after 13h | one |
| 15 | checker rules (D11), test-first | last | one |
| 16 | acceptance ("Done when") | after 15 | none |

---

### Task 1: inventory and the comparison scripts (read-only on the repo)

**Files:** create `SCR/old.md` (`git show ac197f7:docs/RUNBOOK.md > SCR/old.md`), `SCR/cmdset.py`, `SCR/rows.py`, `SCR/splice.py`, `SCR/inventory.md`.
**Read:** the design D2, D3, D5, D10; the sample's removal ledger `/tmp/claude-1000/-home-jeremychia/9eaa2356-e0ee-42ff-a000-1884f1956710/scratchpad/runbook-panel/sample-B9-ledger.md` (the kind of inventory wanted; its line numbers are the working file's, convert to OLD's); `OLD`; the working file.

- [ ] **`cmdset.py OLD NEW [--old-range A:B] [--new-only] [--spanning] [--measure]`.** Prints `ONLY IN OLD (n):` (OLD command lines found in neither NEW's command lines nor NEW's inline commands) and `ONLY IN NEW (n):` (NEW command lines found in neither OLD's command lines nor OLD's inline commands), each with its line number. `--old-range` limits OLD to those lines (drafts are checked against their section's range). `--new-only` prints only the second list. `--spanning` prints every NEW block that holds a laptop line and a container line, or where a line containing `airstack.sh connect` is not the block's last command line, then `spanning blocks: n`. `--measure` prints, per heading of NEW: lines from the heading to its first fence, segment lines, code blocks, `Must see` and `If not` lines.
- [ ] **`rows.py OLD NEW`.** One `PASS`/`FAIL` line per check, FAIL lists what is missing; on load it asserts each cited OLD line starts with `|`. Row matches are byte-identical after stripping outer whitespace, inside the named NEW segment:
  - R1 OLD 481–488 (B9 stop rows) in B9. R2 OLD 619–625 (B10 stop rows) in B10. R3 OLD 481, 482, 485, 488 in B10 (D6: B10 carries B9's rows that B10 lacks; 483, 484, 487 have B10 counterparts, 486 is the teleop fence, absent in B10's config, OLD 511). R4 OLD 916–920 (C9 What to expect) and 928–931 (C9 stop rows) in C9. R5 OLD 954, 955, 962, 967, 968, 969, 970, 973, 974 (D10 pocket rows) in Pocket. R6 OLD 983–987 (variants rows) in Variants.
  - R7 phrases (case-insensitive) per segment: `still armed after about 10 s` in B9, B10, C9; `Only then` in B9, C9; `No takeoff until QGroundControl lists both drones (PREFLIGHT.md)` in B10, C9; `Kill-switch ground check (after any RC change, and once after the branch switch): props OFF` in B and C; `PANIC call — hold` in B; `iron rule 10` in C; `Stop / Play`, `never port to the drone`, `land from the hover` in A.
- [ ] **`splice.py FILE START END DRAFT`.** START and END are exact full lines, or `__BOF__` / `__EOF__`. Asserts each occurs exactly once outside fences, replaces lines [START, END) with DRAFT's content, writes FILE, prints old and new line counts.
- [ ] **Baseline runs** (paste outputs into `inventory.md`): `python3 SCR/cmdset.py SCR/old.md docs/RUNBOOK.md` → both lists empty. `python3 SCR/rows.py SCR/old.md docs/RUNBOOK.md` → all PASS except R3 and R7 `Kill-switch…` in C (they pass only after assembly). `--spanning` on `SCR/old.md` → the count (the panel said 3 of 36).
- [ ] **Inventory part 1 — every passage that leaves RUNBOOK.** One row per sentence, bullet, row or block of OLD that does not survive in place: OLD lines · first words · verdict `moved to <page> §x` / `already there: <page> line n` / `deleted: repeats RUNBOOK line n` · decision (D2 rule or D3 row). Destinations follow D3 and D10; where D3 names several pages, pick the one whose DOCS_STANDARD §1 role fits. Include the commands that leave (`ssh root@<DRONE_IP>`, `voxl_setup_real_drone.sh …`, the `svg_teleop.sh` block and `rviz2 -d …`, C8's `ros2 param set` lines, any other): this is the explained "ONLY IN OLD" list for Task 16. Give every row an id (P1, P2, …).
- [ ] **Inventory part 2 — references into RUNBOOK from other files.** Run `grep -rnE "RUNBOOK" README.md CLAUDE.md docs localisation tools AirStack/README.md --include=*.md --include=*.sh --include=*.py`, drop `docs/RUNBOOK.md`, `docs/superpowers/`, `docs/plans/`, `docs/record/`; then `grep -rnE "\bsteps? [0-9]+[a-z]?\b|§ ?[ABCD][0-9]?\b|\b[ABCD][0-9]{1,2}\b"` on the same files. Read each hit with its neighbouring lines and keep those that mean RUNBOOK. Verdict per hit: `valid` (a section letter, A0–A4, B9, B10, C9, D: they stay) / `breaks` (§B step N, C1–C8, "Alternatives to the tabs", "Drone shutdown in section B", a removed pocket row, an A-section note that moves) with the section it points into / `history` (labels like "Moved from RUNBOOK §B step 1 (2026-10-21)", MIGRATION's "archive `RUNBOOK.md:…`" rows: left unchanged). Report the count (the design expects 56 to 81).
- [ ] **Inventory part 3 — anchors.** `grep -rnoE "RUNBOOK\.md#[A-Za-z0-9_-]+"` over the same files plus every `(#…)` in RUNBOOK. Confirm the list under "Headings kept" is complete and that no file links the two removed headings.
- [ ] **Inventory part 4 — conflicts to report, not fix.** At least: DRONE_SETUP.md line 76 says each drone gets a UNIQUE DDS domain, OLD lines 202–203 provision both drones with domain `1`.

**Rules:** D3, D10; non-goals. **Verify:** a reviewer re-runs the three scripts on the baseline and spot-checks ten inventory rows against the named page and line. **Commit:** none.

### Task 2: the canonical shared opening

**Files:** create `SCR/opening.md`, `SCR/opening_check.py`.
**Read:** sample lines 10–74; D9; "Shared opening" under Shared definitions.

- [ ] Write `opening.md`: the sample's lines 10–11 and steps 1, 2, 4–10 for `drone_2`, wrapped in shared-opening markers (step 3, the pad check, sits between two marker regions). Change only words that cannot hold for two drones, to forms true for one and for two: "the drone answers" → "every drone answers"; "Ctrl-C after the reading" → "Ctrl-C after each reading"; step 5's rigid-body sentence names the bodies as a list; step 10's Must see becomes one line per drone (`Must see: the startup line of `drone_2` says `target_system=2`.`). `vehicle_status`: "a steady rate" (D9, owner answer 3).
- [ ] Below it, the substitutions, each copied from OLD (no new command): `drone_1` alone (B, C) — `ping -c2 10.40.2.11`, `cd ~/AirStack-starling-max2 && ./mocap.sh`, `ros2 topic hz /drone_1/fmu/out/vehicle_status`, `ros2 topic hz /drone_1/pose`, `ros2 launch svg_ground_control real_interfaces.launch.py drones:=drone_1`. Two drones (B10, C9) — both `ping` lines, `MOCAP_BODIES="drone_1 drone_2" ./mocap.sh`, one `hz` block per drone, `drones:=drone_1,drone_2 target_systems:=1,2`, one Must-see line per drone. Two-drone sequences close the marker before `ba816ea`'s `No takeoff until QGroundControl lists both drones (PREFLIGHT.md)` line and reopen after it.
- [ ] `opening_check.py [--ref SCR/opening.md] FILE…`: extracts each sequence's shared opening (a draft file counts as one sequence), normalises it, compares every sequence with the reference (or with the first), prints `OPENING IDENTICAL (n sequences)` or, per sequence, the first differing normalised line pair. A sequence without markers is listed as `no markers` and not compared.
- [ ] **Verify:** expand the substitutions by hand into three throwaway files (`drone_1`, `drone_2`, two drones) and run `python3 SCR/opening_check.py --ref SCR/opening.md` on them → `OPENING IDENTICAL (3 sequences)`. Change "a steady rate" to "about 30 Hz" in one → that line reported.

**Rules:** D9; no new command, number or expected value. **Commit:** none.

### Task 3: DOCS_STANDARD gains "Procedure pages"

**Files:** modify `docs/DOCS_STANDARD.md`: insert `## 6b. Procedure pages` after §6 (keeps §7–§9 numbers).

- [ ] At most 25 lines: the D1 step format with the two-step example from D1; the D2 cut rule (the six kinds of line, 160-character step instruction); one block per place, `takeoff`/`start`/`land` never share a block, no block continues past a `connect` line; `If not:` cites an existing stop-table or TROUBLESHOOTING row; the stop table, introduced by `**Stop table.**`, directly above `takeoff` (D6); go/no-go as D7; "What to expect" at most five rows (D8); the shared-opening markers (D9). End with one line: the checker rules are added by this project's last task.
- [ ] **Verify:** `tools/docs_check/check_docs.sh | tail -1` → `0 FAIL`.
- [ ] **Commit:** `git add docs/DOCS_STANDARD.md && git commit -m "docs: DOCS_STANDARD gains a Procedure pages section"`.

### Task 4: destinations I — DRONE_SETUP, CONFIG, ARCHITECTURE

**Files:** `docs/DRONE_SETUP.md` (§4, lines 74–92), `docs/CONFIG.md`, `docs/ARCHITECTURE.md`. **Read:** inventory part 1 rows whose destination is one of these pages.

- [ ] DRONE_SETUP §4 receives what only RUNBOOK has (D5): the `ssh root@<DRONE_IP>` line (OLD 195), the laptop-IP and ping sentence (OLD 197–199), the two per-drone lines (OLD 202–203) copied verbatim, and "The script does not set `MAV_SYS_ID`." (OLD 393). Do not touch the domain conflict; report it.
- [ ] CONFIG and ARCHITECTURE receive every other `moved to` row for them (for example C7's config-editing rules OLD 732–739 and the never-set-live quote OLD 756 to CONFIG, unless the inventory says already there). Text moves verbatim or shortened; no number, command or claim changes. Pointers to RUNBOOK steps on these pages are NOT retargeted here (13c does that, D5).
- [ ] **Verify:** checker `0 FAIL`; every moved row's text is found on its page (`grep -nF`); `git diff --stat` shows only these three files.
- [ ] **Commit:** `docs: drone setup and config pages receive the runbook's provisioning and config notes`.

### Task 5: destinations II — the history and reference pages

**Files:** `docs/projects/HTX-R2.md`, `docs/projects/HTX-R1.md`, `docs/MIGRATION.md`, `docs/SCENARIOS.md`, `docs/TELEOP.md` (§4 `## 4 · Quick start — SIM (M1 rehearsal)`), `docs/BASESTATION.md`, and any other page the inventory names (MOCAP, TROUBLESHOOTING).

- [ ] Apply every `moved to` row for these pages: "what was observed", dates and videos of B9, B10, C9 to HTX-R2 inside the matching `**NEAR-nnn: <title>.**` block (D8; DOCS_STANDARD §4); the branch note to MIGRATION (D3 row 1); C4, C8 reference to SCENARIOS/TELEOP (D3); the `svg_teleop.sh` block (OLD 998–1006) and the RViz fallback line to TELEOP §4 (D10).
- [ ] Project pages fail the build otherwise: each `###` milestone at most 40 lines, the page at most 250, cells at most 120 characters (`page-budgets`), every NEAR id in `docs/plans/2026-11-13-project-plan-linear.md` (`linear-parity`), figures per `figure-refs`. Today M5 is 21 lines, M7 29: if a moved passage does not fit, link the LEDGER row instead and say so in the report.
- [ ] Moved text must render: visible prose, not an HTML comment, not a code comment.
- [ ] **Verify:** checker `0 FAIL`; `grep -nF` finds each moved passage; `git diff --stat` only the named pages.
- [ ] **Commit:** `docs: history, results and reference pages receive what leaves the runbook`.

### Tasks 6–12: draft one RUNBOOK section each (parallel, scratch only)

Each drafting task writes `SCR/draft-<id>.md` (exactly the text that replaces the section's segment, heading line included; end it the way OLD's range ends, including a closing `---` where OLD has one) and `SCR/report-<id>.md`.

**Read for every draft:** the design; the sample (the model); `SCR/opening.md`; `SCR/inventory.md` (the rows for this section); the OLD range below and the same segment of the working file (for `ba816ea`'s lines); DOCS_STANDARD §6; PREFLIGHT.md; the TROUBLESHOOTING rows you cite.

**Hard rules (every draft):**
1. Every command copied character for character from OLD or the working file, trailing comments dropped as in the sample. No new command, number, expected value or action.
2. No stop-table row cut, and none reworded so that its action changes (D6). Rows the plan names are copied byte-identical.
3. `Must see:` only where the page states what appears (builder check). `If not:` only from an existing stop-table row, TROUBLESHOOTING row or sentence of RUNBOOK or PREFLIGHT; cite its source line in the report.
4. Hazards stay at their step; "not flown", "not re-derived", "not set" notes stay (D2 rule 6).
5. The commander line carries `use_foxglove_studio:=true`.
6. The sequence runs from a cold start to its own shutdown with all its steps (owner, D9 answer). No "same as section X".
7. Shared-opening steps are `SCR/opening.md`'s text, changing only drone names, IPs and counts as its substitution list says, inside the markers. `vehicle_status` reads "a steady rate".
8. Parts in D4's order: world line and panic line · steps to the floor check · go/no-go (D7) · What to expect, at most five rows, if the section has one, keeping its "not flown" marks, and one link to the HTX-R2 block that holds what was observed (D8) · `**Stop table.**` (header `| What you see | Do this | Record |` unless the section's table has another), then the `hold` block where the section has one · takeoff to land · shutdown.
9. D1 form; `takeoff`, `start`, `land` and `hold` each in their own block; no block spans laptop and container or continues past `connect`. Step instruction at most 160 characters.
10. Wording per DOCS_STANDARD §6 ("motion-capture positioning (mocap)", nothing reads as validated on the real drone that was not). Outside §A never name `cbf_sim`, `swarm_sim`, `teleop_single`, `squeeze_3drone` or bare `teleop_real.yaml` (`real-page-hygiene` FAIL).
11. Aim for at most 180 lines heading to shutdown and at most 15 lines heading to first command; never cut a stop row or a hazard to meet either.

**Steps (every draft):**
- [ ] Write the draft.
- [ ] `python3 SCR/cmdset.py SCR/old.md SCR/draft-<id>.md --old-range <range> --new-only` → `ONLY IN NEW (0)`. Without `--new-only`: every "ONLY IN OLD" line has an inventory row.
- [ ] Real sequences: `python3 SCR/opening_check.py --ref SCR/opening.md SCR/draft-<id>.md` → `OPENING IDENTICAL`. `python3 SCR/cmdset.py SCR/old.md SCR/draft-<id>.md --spanning` → `spanning blocks: 0`.
- [ ] Report: source of each `Must see` and `If not`; each removed passage with its inventory id; the `--measure` counts and the stop-table gap; anything unsure.

**Reviewer (every draft):** the hard rules one by one; every stop row against OLD; every hazard and hold point ("wait for …", "only then", "no takeoff until") of the OLD range present at its step; no sim content in a real section and none real in §A.

| Task | Draft | OLD range | Section notes |
|---|---|---|---|
| 6 | `intro`, `tail` | 1–37; 933–1008 | Intro: title; the chooser (Shared definitions), one row each for A, B, B9, B10, C, C9, D (go-to = link to the kept heading; slugs from `python3 -c "import sys;sys.path.insert(0,'tools/docs_check');import check_docs as C;print(C.slugify(input()))"`) plus one row for the keyboard sim session (OLD 166's link); the prompt rule (22–24), the never-paste-across-`connect` rule (10–11), panes and tmux moves (31, 33–35), short. Tail: D's commands and its ⚠️ clock line unchanged; Pocket = the nine rows of R5, byte-identical; Variants = heading, one line saying the rows change the A1 spawn line, rows 983–987, the tmux paragraph 989–996. 998–1008 left per Task 5. |
| 7 | `A` | 39–167 | Keep the world line 41 (it carries `Sim-only — never port to the drone`) and the A0–A4 headings. Split A4's block (132–136): `takeoff`, `start`, `hold`, `land`, the `mavros/state` echo, one block each; `land from the hover — never mid-leg` stays at the land step. The Stop / Play warning (85–90) stays at A1. MAVROS respawn recovery (103–107) and "Fence latched" (147–150) become `If not:` lines where they apply. A1 links `#sim-launch-variants` once; 72–73 and 152–161 go (D3, D10: the tail is their single home). Own shutdown: Ctrl-C each tab, then `cd ~/AirStack-starling-max2/AirStack && ./airstack.sh down` (344). |
| 8 | `B` | 170–353 | One drone, `drone_1`, `swarm_real_ours.yaml`. World and panic lines from 174–176, 327, 645–649, 727–730. Re-provision conditional line (D5) as in `opening.md`. Shared opening for `drone_1`. Outside the markers: after the world check, a step with `ip -4 -brief addr` and `ping -c2 <MOTIVE_IP>` (215–216, Must see 221–222); after "link alive", the `vehicle_odometry` echo with the best_effort note (245, 247–250, D2 rule 3). Then: commander (288–290 verbatim; Must see and launch notes 292–297); odometry flowing (281) where B9 has it; fusion check (299–308, the arrow-key warning stays); frame hand-check (309); Basestation check (311–318, no takeoff during it); go/no-go with the kill-switch ground check in `ba816ea`'s words. Stop table rows: OLD 482, 487, 488 byte-identical, plus rows written from 333–334 (`DENIED`; no entry = `target_system` mismatch), 649 with 729–730 (RC takeover, then `land` once), 147–150 (fence latched: `swarm_real_ours.yaml` is `hold_all`). Then `**PANIC call — hold:**` and its block (`ba816ea`). Takeoff (Must see 332–333), start, hover check `ros2 topic hz /drone_1/fmu/trajectory_command` ≈ 20 Hz (330), "Hover about 20 s" (331), land (Must see: QGroundControl DISARMED; the `disarm ✗` / "Disarming denied" note of 331 until NEAR-826 is re-observed), shutdown as the sample's step 21 with Ctrl-C panes 3, 2, 1 and the mocap terminal. |
| 9 | `B9` | 355–496 | The approved sample, with `opening.md`'s text in the shared steps and the markers added. Nothing else changes. |
| 10 | `B10` | 498–633 | Both drones, `goal_two_ours.yaml`, `teleop_drones:=drone_2`. Panic line from 614–615 and 625. Shared opening, two-drone form; step 3 (pad check) keeps 530–532's "only its pane 5 line / do NOT launch pane 3" warning. Pad pane (557), commander (560–562 verbatim), status and positions (564–566), pad alive (567), separation readout in its step (597–607, Must see about 2.5 m, `If not` = 608). Go/no-go adds 506–511 (two people and the watcher, iron rule 10; takeoff points; one KILL per drone; geofence only). What to expect from 610–612. Stop table: R2 rows, then R3 rows, byte-identical; keep 614–615's two sentences. Takeoff (twice "holding takeoff position"), radius step 14 as written (576–580, owner answer 4), start, fly with 585–589's notes, land with `ba816ea`'s still-ARMED line, shutdown 627–631. |
| 11 | `C` | 637–756 | Waits for Task 8's reviewed draft: copy draft-B's steps up to and including the Basestation check unchanged except the commander step, which launches `goal_single_ours.yaml` (666–668). World line + panic line from 645–649. Go/no-go adds `ba816ea`'s "ON the config's `hover_positions` x,y … (iron rule 10)". Stop table as draft-B's without the fence-latched row (`goal_single_ours.yaml` is `keep_in`, 707). Takeoff, start, goal (679–680), speed (681), the goal hazards 683–684 and 690, square loop (694–695), land in its own step (696), shutdown as B. Everything else in 637–756 per the inventory. |
| 12 | `C9` | 758–931 | World line: 760–761, 763, and the first-flight line 766 (builder check). Panic line from 886–890. Shared opening, two-drone form (B9 order, D9). Commander (832–834), status (836–838), positions (840–842, hazard 776–779 here), radius (844–848, hazard 780–783 here), recording on (852–853), readout (895–907 block in its step). Go/no-go adds 787–788. What to expect: the R4 rows. `**Stop table.**` replaces "Stop rules"; the R4 rows byte-identical; the note 922–924 stays; the header may drop its date only if the date stays in that note. `**PANIC call — hold:**` with the `hold` block (892). Takeoff with the motor hazard 784–786 and `ba816ea`'s WAIT line, start, goals 1, 2, home (867–872, notes 863–866), land, recording off (879), shutdown 881–882 plus each drone powered down one USB-C cable at a time (630, 884). |

### Tasks 13a–13h: assemble one section per commit (strictly ordered)

**Procedure (each):**
- [ ] `python3 SCR/splice.py docs/RUNBOOK.md "<START>" "<END>" SCR/draft-<id>.md`.
- [ ] Retarget, in the same commit (D5), every inventory part-2 `breaks` reference that points into this section, to `[RUNBOOK.md](RUNBOOK.md#<anchor>) §X step N (<step name>)` with the new number. `history` rows stay.
- [ ] Verify: `tools/docs_check/check_docs.sh | tail -1` → `0 FAIL`; `python3 SCR/cmdset.py SCR/old.md docs/RUNBOOK.md` → `ONLY IN NEW (0)`, and every "ONLY IN OLD" line belongs to a section assembled so far and has an inventory row; `python3 SCR/rows.py SCR/old.md docs/RUNBOOK.md` → PASS for every check whose segment is assembled; `python3 SCR/opening_check.py docs/RUNBOOK.md` → identical across the assembled real sequences; `python3 SCR/cmdset.py SCR/old.md docs/RUNBOOK.md --spanning` → no block from an assembled section; `git diff --stat` shows only RUNBOOK and the retargeted pages.
- [ ] Commit, staging RUNBOOK and each retargeted page by path.

| Task | START | END | Draft | Also in this commit | Subject |
|---|---|---|---|---|---|
| 13a | `__BOF__` | the `## A ·` heading | intro | — | `docs: runbook opens with a session chooser` |
| 13b | `## A ·` heading | `## B · REAL DRONE session (mocap room)` | A | refs into §A | `docs: runbook section A in step form` |
| 13c | `## B · REAL DRONE session (mocap room)` | `### B9 — Fly one real drone with the gamepad` | B | D5: step-0 pointers in DRONE_SETUP §4 (lines 78, 85–90, 158), CONFIG (64), TROUBLESHOOTING (185), and the old step-0 lines of B9, B10, C9 (OLD 391–392, 515–516, 795–796) now point to `[DRONE_SETUP.md](DRONE_SETUP.md#4--point-px4-at-the-laptop-uxrce-dds-provisioning) §4`; refs into §B | `docs: runbook section B as one full sequence` |
| 13d | `### B9 — …` | `### B10 — …` | B9 | refs into B9 | `docs: runbook section B9 in step form` |
| 13e | `### B10 — …` | `## C · GOAL FLIGHTS (fly to commanded waypoints)` | B10 | refs into B10 | `docs: runbook section B10 in step form` |
| 13f | `## C · GOAL FLIGHTS (fly to commanded waypoints)` | `### C9 — …` | C | refs to C1–C8 (for example "§C7" now points to CONFIG.md's config-editing rules) | `docs: runbook section C as one full sequence` |
| 13g | `### C9 — …` | `## D · POST-FLIGHT — pull & review the PX4 logs` | C9 | refs into C9 | `docs: runbook section C9 in step form` |
| 13h | `## D · …` | `__EOF__` | tail | refs to removed pocket rows | `docs: runbook tail keeps the safety rows and the sim variants` |

(`…` = the full heading line as listed under "Headings kept".) After 13h: `rows.py` all PASS, `opening_check.py` → `OPENING IDENTICAL (5 sequences)`, `--spanning` → `spanning blocks: 0`.

### Task 14: prose-reference sweep

- [ ] Re-run inventory part 2's two greps on the finished tree. Every hit is `valid` against the new page, or `history`. Fix any left: a step number that no longer exists, a C1–C8 or "Alternatives to the tabs" mention, a pointer to text that moved. PREFLIGHT.md is not edited: confirm its RUNBOOK mentions (lines 5 and 31: §B/§C, B9, B10, C9, "the stop table in RUNBOOK.md B10") still hold.
- [ ] **Verify:** checker `0 FAIL`; list each remaining hit with its verdict in the report.
- [ ] **Commit:** `docs: pages point at the runbook's new steps` (skip if nothing changed).

### Task 15: checker rules for procedure pages (D11), test-first

**Files:** modify `tools/docs_check/check_docs.py` (new section `# ----- 22. runbook procedure` before `selftest`; register `check_runbook_procedure` in `main()`'s list after `check_single_home`), `tools/tests/test_check_docs.py` (new class `RunbookProcedure`), `tools/docs_check/README.md` (one row after `single-home`), `docs/DOCS_STANDARD.md` (§6b's last line names the check).

**Interfaces:** `check_runbook_procedure(text: str | None = None) -> Result` named `"runbook-procedure"`; reads `ROOT / "docs/RUNBOOK.md"` when `text` is None; a missing file is a WARN. Helpers `segments(lines) -> dict[str, tuple[int, int]]` (Shared definitions, fence-aware), `opening_lines(lines, seg) -> list[str]`, `normalise_opening(lines) -> list[str]` (the normalisation above, verbatim).

| Rule | Severity |
|---|---|
| the chooser header (Shared definitions) at line ≤ 15 | FAIL |
| no fenced block holds a laptop line and a container line | FAIL |
| a line containing `airstack.sh connect` is its block's last command line | FAIL |
| no block holds two different calls among `/swarm_commander/takeoff`, `start`, `land` | FAIL |
| each real sequence has a `**Stop table.**` table, gap ≤ 15 | FAIL |
| each real sequence has paired markers; the normalised openings are identical (details: sequence and first differing line) | FAIL |
| inside a real sequence, `20\d\d-\d\d-\d\d` or `#\d+` outside the opening blockquote, table rows and lines containing `not flown`, `not re-derived` or `not set` | WARN |
| a sequence (`## A` whole, and each real one) longer than 180 lines | WARN |

- [ ] **Write the failing tests** (each builds a small page string and calls `C.check_runbook_procedure(text)`): `test_chooser_on_line_15_passes_on_16_fails`; `test_block_mixing_mocap_sh_and_ros2_fails` (also `airstack.sh` and the AppImage); `test_connect_not_last_fails_last_passes`; `test_takeoff_and_start_in_one_block_fails`; `test_stop_table_gap_16_fails_15_passes`; `test_real_sequence_without_stop_table_fails_section_A_needs_none`; `test_openings_differing_only_in_names_ips_and_counts_pass` (`drone_1` + `10.40.2.11` + bare `./mocap.sh` + `drones:=drone_1` against `drone_2` + `MOCAP_BODIES="drone_2"` + `target_systems:=2`, and a two-drone form with duplicated per-drone lines); `test_opening_word_change_fails_with_the_line` ("a steady rate" vs "about 30 Hz"); `test_unpaired_or_missing_markers_fail`; `test_date_or_ledger_number_in_a_step_warns_not_in_world_line_table_row_or_not_flown_line`; `test_sequence_of_181_lines_warns_not_fails`; `test_registered_in_the_checker_run` (as `SingleHome`'s); `test_shipped_runbook_has_no_fail` (runs on the real file).
- [ ] Run `python3 -m unittest discover -s tools/tests -p test_check_docs.py -k RunbookProcedure -v` from the repo root → fails (no such function).
- [ ] Implement; rerun → OK; then `python3 -m unittest discover -s tools/tests` → `OK (skipped=1)` with `Ran 999 tests` (986 + 13).
- [ ] If the finished RUNBOOK fails a FAIL rule, that rule ships as WARN, and the findings go to the report for the owner. No rule is loosened to make the page pass.
- [ ] README row: `| runbook-procedure | docs/RUNBOOK.md (design 2026-11-14 D11): chooser in the first 15 lines; no block mixes laptop commands with ros2; connect ends its block; takeoff, start and land in separate blocks; each real sequence has a stop table ≤ 15 lines above takeoff and the same shared opening (normalised); dated text in a sequence and sequences over 180 lines warn | FAIL / WARN |`.
- [ ] **Verify:** `tools/docs_check/check_docs.sh` → `[PASS] runbook-procedure` or `[WARN]` with only listed dated lines or long sequences, and `0 FAIL`.
- [ ] **Commit:** `git add tools/docs_check/check_docs.py tools/tests/test_check_docs.py tools/docs_check/README.md docs/DOCS_STANDARD.md && git commit -m "docs_check: runbook procedure rules (D11) with tests"`.

### Task 16: acceptance ("Done when")

- [ ] Measures on the finished file, against the design's Intent table: `wc -w docs/RUNBOOK.md` (target about 7,500, reported, not enforced); `cmdset.py --measure` (heading to first command ≤ 15 per session; chooser by line 15); `--spanning` → 0; one-drone-to-goals = section C alone, no jump; the B10 stop table ≤ 15 lines above `takeoff`; every check with a known action has `If not:`.
- [ ] `cmdset.py SCR/old.md docs/RUNBOOK.md` → `ONLY IN NEW (0)`; each "ONLY IN OLD" line explained by an inventory row.
- [ ] Flight-test reviewer (agent `panel-flight-test-engineer`), row by row against `ac197f7`: every stop-table row, every hold point, every PREFLIGHT pointer, every hazard and rule-6 note still present at its step.
- [ ] Newcomer reader (agent `panel-newcomer-reader`) repeats round 1's three tasks on the finished page and reports lines read and jumps: (1) a first sim flight; (2) one real drone to two goals, cold start to shutdown; (3) sticks stop answering in B10, what to do. Targets: no jump out of the section for any task; the B10 answer within 15 lines of the step.
- [ ] `tools/docs_check/check_docs.sh` → `0 FAIL`; `python3 -m unittest discover -s tools/tests` → `OK`.

## Review focus (final whole-branch review)

1. **A dropped safety line:** a hazard, a "not flown / not re-derived / not set" note, a PREFLIGHT pointer or a `ba816ea` line missing or moved away from its step. Diff each real sequence against its OLD range with `rows.py` and by eye.
2. **A stop row changed or lost:** any row not byte-identical to OLD, or a row whose action changed; B10 missing B9's rows; section B or C without a stop table, or a row written there from memory instead of the cited OLD lines.
3. **A command altered:** `cmdset.py` NEW-only not empty, or a reformatted multi-line command (the three-line commander launches, the separation readout).
4. **An anchor broken or a prose reference stale:** the 19 inbound links and the chooser are caught by `links`; the prose "§B step N", "§C7", "Alternatives to the tabs", "Drone shutdown in section B" are not.
5. **Text moved to a page that does not render it, or does not fit:** an HTML or code comment, `docs/superpowers/`, a project-page section over 40 lines, a NEAR id missing from the plan file.
6. **Sim and real mixed:** a sim config name outside §A, sim-only values in a real step, or a real-drone step in §A; the shared opening drifting between sequences (`opening_check.py`).
