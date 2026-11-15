# Real gamepad docs — implementation plan

> **For agentic workers:** executed with superpowers:subagent-driven-development. One writer and one reviewer per task. Writers do not commit; the orchestrator commits each task after its review, staging by explicit path.

**Goal:** the how-to pages match what was flown on 2026-11-12 and 2026-11-13, and the README shows it.

**Spec:** [2026-11-13-real-gamepad-docs-design.md](../specs/2026-11-13-real-gamepad-docs-design.md). Read it first. It holds the decisions (D1 to D12), the builder-check answers and the done-when list.

**Worktree:** `/home/jeremychia/AirStack-starling-max2-docsrefresh`, branch `docs/real-gamepad-docs`. Nothing outside it is edited.

## Global constraints

- Never edit `AirStack/`, `tools/` code, `tools/docs_check/`, `docs/record/LEDGER.md` or `docs/plans/`. Never touch running containers, Isaac Sim, Foxglove Studio or a drone.
- `python3 tools/docs_check/check_docs.py` must end `13 PASS · 6 WARN · 0 FAIL · 1 SKIP` after every task.
- Facts come from the repo, never from memory: the ledger rows 33 to 37, `docs/projects/HTX-R2.md` (hazards 5 to 10), `tools/real.sh`, `tools/teleop/real_config.py` (`pane_lines`, `operator_block`, `takeoff_point`), `tools/teleop/pad_core.py`, the config yamls under `AirStack/robot/ros_ws/src/svg_ground_control/config/`.
- A how-to page holds no result number. It points to the ledger row. Behaviour that was not flown says "not flown".
- Commands are full sequences with literal names (`drone_1`, `drone_2`). The commander line carries `use_foxglove_studio:=true`. The pad pane (pane 5) starts before the commander (pane 3) and is never stopped until DISARMED.
- The older Starling, everywhere: "The older Starling (`drone_1`) flies by the owner's decision, with a watcher on its front-right motor at every takeoff." Short form in a cell: "`drone_1` (older Starling): flies by the owner's decision, with a watcher on its front-right motor." Never "grounded", never "fixed".
- Wording: short plain sentences, no semicolon chains, "motion-capture positioning (mocap)", never "under mocap". Linear ids and titles verbatim from `docs/plans/2026-11-13-project-plan-linear.md`.
- Ledger links are written `[#36](record/LEDGER.md)` style, as the pages already do.

## Tasks

### Task 0 — inventory of "⏳ STE", "grounded" and stale gamepad lines (read-only)

Output: a table (file:line, verdict replace/keep/split, ledger row). The orchestrator rules on it. Tasks 2, 3 and 5 use the ruled table.

### Task 1 — the safety card and the iron rules

Files: `docs/PREFLIGHT.md`, `CLAUDE.md` (the `IRON_RULES` block only), `docs/AI_ASSIST.md` (line 12 count, never-do table), `docs/GLOSSARY.md` (line 261 "nine" becomes "ten").

- Rule 3 becomes: `3. **After ANY manual takeover or RC KILL: call `land` once** (drone on the floor) to reset the commander, or `takeoff` will refuse ("not IDLE") (re-observed at NEAR-825). After a KILL the commander keeps sending setpoints until `land` is called (ledger #34).`
- Rule 10 is appended: `10. **Two people at takeoff.** Each drone stands on its own takeoff point (the config's `hover_positions`), nose toward +x: `takeoff` flies a straight line to that point and the fence does not act during the climb (ledger #34). A second person watches `drone_1`'s front-right motor at every takeoff: it failed or started late in 5 of 7 arms on 2026-11-12, cause unknown (docs/projects/HTX-R2.md, hazard 6).`
- The block in `CLAUDE.md` is made byte-identical to the block in `docs/PREFLIGHT.md`.
- Card version line becomes `v2026-11-13b`.
- Header line 5: the gamepad has flown (one drone, and one hand-flown beside a hovering one, 2026-11-13: RUNBOOK.md B9 and B10). Formations and random goals stay unflown.
- Checklist lines 11, 18, 19, 23: name every drone in the session's config, not only `drone_1` (two-drone configs: `goal_two_ours.yaml`).
- Line 20 is strengthened to match rule 10: each drone ON its own takeoff point, nose toward +x. Compare `/poses` with `hover_positions` before `takeoff`.
- Lines 26 and 27 (`joy_map` flow) are replaced by three lines: (a) pad back switch on X, MODE light off, `tools/real.sh teleop drone_2` ended PASS, never press MODE; (b) pad pane running, `ros2 topic hz /svg/drone_2/teleop_command` about 20 Hz, no warning appears if it stops; (c) keep the pad pane open until DISARMED. Keep the teleop-fence and yaw-plan content of line 27. Keep `teleop_max_speed_mps` ≤ 0.5 and add: the drone can overshoot the cap by about a third (ledger #36).
- Emergencies line 44 (pad disconnects): "expected from the code, not flown" plus `land`.
- Whole card at most 80 lines.

Check: docs check green; `diff` of the two `IRON_RULES` blocks is empty; `grep -n "joy_map" docs/PREFLIGHT.md` is empty.

### Task 2 — runbook: B9, B10, C9 opening, headings

File: `docs/RUNBOOK.md`.

- New `### B9 — Fly one real drone with the gamepad` and `### B10 — Two real drones, one flown by hand`, after step 8 of §B and before `## C`. Content and order: spec D5. B9 at most 140 lines and runnable from a cold start without jumping to another section. B10 at most 110 lines, also a full sequence, config `goal_two_ours.yaml` with `teleop_drones:=drone_2`.
- Each has a stop table (what you see, do this, record). The record column holds a ledger link, a hazard number or "not flown". No result numbers.
- Each ends with the full shutdown and one pointer line to its ledger row (36 for B9, 37 for B10).
- B9 opens with which drone is which (older Starling = `drone_1`, 10.40.2.11, MAV_SYS_ID 1; newer = `drone_2`, 10.40.2.10, MAV_SYS_ID 2) and the older-Starling sentence.
- C9's opening ("Not flyable as written today ... GROUNDED") is replaced by the older-Starling sentence. Any other "grounded" on the page goes the same way.
- §B and §C headings and step 8: "⏳ STE" handled per the ruled inventory (spec D6, D9).
- Add B9 and B10 to the page's own contents list or pocket reference if it has one.

Check: docs check green; `grep -ci grounded docs/RUNBOOK.md` is 0; `grep -c "tools/real.sh" docs/RUNBOOK.md` is at least 3; the command lines in B9 match what `python3 tools/teleop/real_config.py` prints for `drone_2` (read `pane_lines`).

### Task 3 — teleop page

File: `docs/TELEOP.md`. §5 becomes a short corrected paragraph and a link to RUNBOOK B9, with no commands. Lines 14, 22, 205, 343, 386 and anything else that contradicts B9 or ledger rows 36 and 37 are corrected in place (ruled inventory). Nothing is moved or trimmed beyond §5. Sim text stays.

Check: docs check green; `grep -n "js0\|joy_map" docs/TELEOP.md` shows no line that presents the old flow as the way to fly the real drone.

### Task 4 — troubleshooting

File: `docs/TROUBLESHOOTING.md`. Seven rows, 40 words or fewer each, in the sections where they belong (spec D10): sticks ignored after Start; "arming denied"; second drone missing in QGroundControl; keyboard read as a joystick; `ros2 topic echo` says the topic is not published; a drone tips at lift-off; CBF radius back at 0.55 after a restart. Causes and fixes come from ledger rows 34 to 37, HTX-R2 hazards and `tools/teleop/`. A row whose cause is not recorded in the repo is reported back, not invented.

### Task 5 — the one-line pages

Files: `docs/CONFIG.md`, `docs/SCENARIOS.md`, `docs/BASESTATION.md`, `docs/MIGRATION.md`, `docs/GLOSSARY.md`, `docs/DRONE_SETUP.md` (only if the inventory says so), `docs/projects/HTX-R2.md` (banner line only). Spec D11 plus the ruled inventory. Glossary gains: lock button, keep-out, pass line, pad check (one line each).

Check: docs check green; `grep -rli grounded README.md docs/*.md docs/projects/*.md` is empty after tasks 2, 3 and 5.

### Task 6 — media (orchestrator)

`assets/cbf_teleop_two_drones_hero.gif` (14 s, 800 px, at most 4 MB), `assets/cbf_teleop_two_drones_real.gif`, `assets/xbox_teleop_real.gif`, `assets/cmu_random_goals.gif`, `assets/cmu_figure_eight.gif` (gallery GIFs 400 px wide, at most 3 MB each). `pictures/README.md` gains the new files, the CMU credit line and the two retired 2026-09 rows.

### Task 7 — README (last)

File: `README.md`. Spec D1 to D4. First paragraph says two Starlings. Hero under the introduction, above "I want to…", with a caption of at most 400 characters that carries the only result number on the page as link text to ledger row 37. The status line shrinks to pointers (no typed results). "I want to…" gains a row for the gamepad session (link to RUNBOOK B9) and the which-drone line. Gallery in two groups, at most six rows each, no result numbers in rows; CMU rows carry the credit line. `tools/real.sh` is linked.

Check: docs check green; the page still fits the "one screen to the table" intent (hero plus at most 12 lines above "I want to…").

## Review

- Per task: one reviewer with `~/.claude/skills/quality-change/references/review-checklists.md`, the spec and the diff. Every fact is traced to its source. Fix rounds until clean.
- Final (owner's request, 2026-11-13): three reviewers on the whole branch. (1) Documentation: every changed page against the spec, the ledger and the code. (2) Safety: the card, the iron rules, B9, B10 and the stop tables, by the flight-test engineer. (3) Design: the README as rendered (hero, captions, gallery, first screen), and the design note against what was built.
- Acceptance: a fresh newcomer answers the three questions in the spec's Intent table from `README.md`, measured in pages, lines and clicks.

## Review focus

1. A command in B9 or B10 that differs from what `tools/real.sh` prints or from what was flown.
2. A sentence that reads as a pass where only one flight was seen, or that presents unflown behaviour (pad unplug, fence top, +x wall) as seen.
3. The two `IRON_RULES` blocks drifting apart, or a count left at "nine".
4. A result number typed on a how-to page or in a README gallery row.
5. A link to an anchor that does not exist on GitHub (`#b9--fly-one-real-drone-with-the-gamepad`, `#b10--two-real-drones-one-flown-by-hand`).
