# Design — a runbook a person can follow with a drone on the floor

Date: 2026-11-14. Status: **approved by the owner on 2026-11-14** ("Yeah build the whole run book like the sample"; D11 "yes"; D9 "Yes. include all steps from cold run for each commander.py sequence").
Process: `quality-change` (recon → four-hat panel, two rounds → this design → builder check → owner).

## Intent

The owner asked: "can u get some technical writers and analyse how can the runbook.md be improve for readability and follow thru?" and, after the round-1 summary: "yeah go ahead. reduce the amount of unncessary information or like avoid giving "too much information" resulting in a info dump."

`docs/RUNBOOK.md` grew from about 640 to 1024 lines in three days. Measured on the file at `ac197f7`:

| Measure | Today | Target |
|---|---|---|
| Words in the page (prose 6,971 + code blocks 2,500) | 9,739 | about 7,500 (see "What the sample showed") |
| Lines from a session's heading to its first command | B 21, B9 42 | at most 15 |
| "Fly one real drone to two goals, cold start to shutdown" | about 256 lines from six places, no shutdown in section C | one sequence, no jump |
| Lines from line 1 to the first command of a session | 55 (sim), 195, 397, 521, 801 | a chooser in the first 15 lines, one click to any session |
| "Sticks stop answering in B10, what do I do" | the row is 48 lines below the step, no pointer | stop table at most 15 lines above `takeoff` |
| Code blocks that span laptop and container (the page's own "never paste across `connect`" rule) | 3 of 36, each a whole session | 0 |
| Steps that say what to do when the check fails | B9 1 of 15, B10 1 of 17, C9 2 of 19 | every check that has a known action |

## What the sample showed

Section B9 was rewritten to this design before approval: [the sample](2026-11-14-runbook-follow-through-sample-B9.md). Every command and every stop-table row is unchanged.

| Measure | B9 today | Sample |
|---|---|---|
| Lines from the heading to the first command | 42 | 14 |
| Steps that say what must be seen | 9, inside comments | 16, on their own line |
| Steps that say what to do if not | 1 | 13 |
| Code blocks | 2 (one spans laptop and container) | 19, one place each |
| Stop table | 32 lines below `takeoff` | 13 lines above it |
| Words | 1,399 | 1,342 |
| Lines | 144 | 168 |

A sequence does not get shorter: what was history and explanation becomes "Must see" and "If not". The reader gains a first command within one screen and nothing between the steps that is not a step. The page as a whole loses words where it explains instead of instructs: the intro, sections B and C, the sim notes and the tail. The first estimate of 6,000 words was wrong; about 7,500 is the honest figure with two new full sequences added.

## Goals

1. A reader picks a session in the first screen and runs it from its heading to its own shutdown without leaving the section.
2. Every step says where to type, what to paste, what must be seen, and what to do if it is not.
3. A sequence holds only what the person at the laptop needs at that step. Everything else lives on the page that owns it.
4. The real-drone sequences agree with each other on order, wording and expected values.
5. No safety step, stop row or PREFLIGHT pointer is lost or weakened.

## Non-goals

- No change to any command, config, tool or to anything under `AirStack/`.
- No new procedure: only sessions the page already describes. Nothing is re-derived (stop distances, radii, gates).
- `docs/PREFLIGHT.md` is not edited (it is the printed card; an edit means a reprint).
- No split into several files (panel, 4 to 0). B9, B10 and C9 keep their headings, so the 19 inbound links to them do not change. This keeps yesterday's decision D5 (gamepad procedures in RUNBOOK under section B).
- The older `2500`-word prose budget for RUNBOOK in `check_docs.py` stays a warning. Five full sequences cannot fit in it, and the owner's rule is full sequences.

## Constraints

- The owner's standing rules: every session is a full cold-start sequence, never a delta; the commander line carries `use_foxglove_studio:=true`; sim and real cannot be confused; nothing reads as validated on the real drone that was not.
- The iron rules block stays byte-identical in PREFLIGHT.md and CLAUDE.md. Ledger rows are append-only.
- `tools/docs_check/check_docs.sh` ends with 0 FAIL at every commit. Content moves first, links are retargeted next, the old text is cut last.
- Work happens on branch `docs/runbook-follow-through` in the docs worktree. The live clone is not touched until the owner says so. Never pushed.

## Decisions (panel votes in brackets)

**D1 · Step format (P1, 4 to 0).** Each step is a bold line `**N · where · what**`, one small code block, then `Must see:` and, where an action is known, `If not:`. A table was rejected: cells have no copy button and break on `|`. Example, B9 today lines 444 to 447:

````markdown
**13 · Pane 4 · takeoff**
```bash
ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger
```
Must see, pane 3: `holding takeoff position`.

**14 · Pane 4 · start**
```bash
ros2 service call /swarm_commander/start   std_srvs/srv/Trigger
```
Must see, pane 3: `drone_2: sticks live`. If not: stop table, "Sticks do nothing".
````

One code block holds commands for one place only. `takeoff`, `start` and `land` never share a block. No block spans a `connect` line. An `If not:` line cites an existing stop-table or TROUBLESHOOTING row; none is written from memory.

**D2 · The cut rule (P5, 4 to 0 with three amendments).** Inside a sequence a line stays only if it is one of:

1. a command;
2. what the reader must see;
3. what to do if they do not, including a note that stops a working system looking broken (for example the `--qos-reliability best_effort` note at lines 247 to 249);
4. a hazard that applies at that step;
5. the world line at the top of the session (SIM or REAL, and the check that the other world is not running);
6. a "not flown", "not re-derived" or "not set" note that limits a gate or an action (for example lines 922 to 924, 588 to 589 and 615).

Everything else moves to the page that owns it, or is deleted when that page already says it. A step's instruction is at most 160 characters.

**D3 · What leaves the page.** The builder's first task writes the full inventory (passage, destination, "moved" or "already there, line n"). The largest items:

| Passage (lines at `ac197f7`) | Goes to |
|---|---|
| 1 to 19: intro and branch note | chooser table; branch history to MIGRATION.md; the flight list is deleted (LEDGER.md has it) |
| 170 to 190: the four stacked quotes that open section B | one world line; the rest is already in MILESTONES.md, LEDGER.md and ARCHITECTURE.md |
| Section B steps 0 to 8, the explanations between commands | CONFIG.md, ARCHITECTURE.md, DRONE_SETUP.md (several were already moved there on 2026-10-21) |
| 639 to 662 and 701 to 757: section C status text, shipped-config table, C4 to C8 reference | HTX-R2.md, CONFIG.md, SCENARIOS.md, TELEOP.md |
| 472 to 475, 763 to 771, 910 to 912: "what was observed", dates, videos in B9 and C9 | HTX-R2.md, one link each, with the ledger row |
| 576 to 578, 585 to 589: "as flown" history in B10 steps | ledger #37; the hazard lines stay |
| 72 to 73 and 154 to 161: sim variants and the tmux alternative | deleted: lines 981 to 996 (the tail) repeat them and become their single home |
| 74 to 83, 116 to 126: sim explanations | CONFIG.md, SCENARIOS.md, BASESTATION.md. The phrases `sim-only — never port to the drone` and `Stop / Play` stay at their step: `tools/docs_check/safety_registry.txt` requires them in RUNBOOK |

**D4 · Page outline.** Section letters and existing anchors are kept.

```
RUNBOOK                     chooser table: session | SIM or REAL | go to   (first 15 lines)
                            prompt rule and panes (short)
A · Simulation              A0 to A4, then its own shutdown
B · Real drone              panic line · one drone: takeoff, hover, land (full sequence, own shutdown)
  B9                        one drone on the gamepad
  B10                       two drones, one flown by hand
C · Goal flights            one drone to goals (full sequence, own shutdown)
  C9                        two drones with the collision filter
D · Post-flight
Pocket reference            safety and prompt rows only
Sim launch variants         the 5-row table and the tmux paragraph
```

Every real session has the same parts in the same order: world line and panic line · steps to the floor check · go/no-go · stop table · takeoff to land · shutdown.

**D5 · Sections B and C become full sequences (P4, 4 to 0).** Section B's bold steps 0 to 8 become the "one drone: takeoff, hover, land" sequence in the D1 form. Section C becomes "one drone to goals", complete from cold start to shutdown, replacing "same bring-up as B steps 0 to 7". The fusion check, the frame hand-check and the kill-switch ground check stay as steps. Re-provisioning becomes one conditional line at the top of section B ("laptop or its IP changed since the last flight: DRONE_SETUP.md §4, then reboot the drone") DRONE_SETUP.md §4 already holds the push, run and reboot commands; it first receives the three things only RUNBOOK has (the `ssh` line, the ping of the laptop, the two per-drone example lines). The pointers back to "RUNBOOK §B step 0" in DRONE_SETUP.md §4, CONFIG.md and the step-0 lines of B9, B10 and C9 are retargeted in the same commit. Other pages cite "RUNBOOK §B step N" and "§C7" in prose (between 56 and 81 places by two counts, not checked by the link checker; the inventory lists them): each is retargeted in the same commit that renumbers.

**D6 · Stop rules (P3, 2 to 2; ruling).** The stop table sits directly above the `takeoff` step, at most 15 lines from it, and steps carry `If not:` lines that name its rows. Two voted for a table between takeoff and land; the flight-test engineer changed to "above takeoff" because the rules must be read before arming (PREFLIGHT says the same). With D1 the takeoff-to-land steps are short, so the table is still on screen in flight. No row is cut. A table that today points at another section's table ("B9's stop table comes first") carries the rows itself.

**D7 · Go/no-go (P7, 4 to 0).** One line, "Every box on PREFLIGHT.md", plus only the items this session adds (motor watcher, radius read-back, readout at about 2.5 m, recording on). The card is not copied into the page: the copies had already drifted.

**D8 · What to expect (P6, 3 to 1).** A table of at most five rows before takeoff, keeping its "not flown" marks. "What was observed" and the videos move to HTX-R2.md with one link.

**D9 · One opening for every real sequence (P2, 4 to 0).** The shared opening is: world check, container up, QGroundControl, mocap, into the container, drone link, link alive, pose alive, interfaces. The fusion check and the frame hand-check stay steps in sections B and C only; B9, B10 and C9 keep them as PREFLIGHT boxes, as flown. The shared opening steps use the same order, the same words and the same expected values in all five real sequences, in the order B9 and B10 flew (ledger #36, #37: QGroundControl and mocap before the drone link). Where two values exist today, the page says only what is true of both until someone measures: `vehicle_status` prints "a steady rate" (today about 30 Hz in section B, about 2 Hz in C9).

**D10 · Tail of the page (P9, P10).** "Alternatives to the tabs": deleted; lines 981 to 996 repeat it (4 to 0). "Pocket reference": only the safety and prompt rows stay (3 to 1): which shell is which, panic, `target_system`, RC takeover, DISARMED after landing, `land` after a takeover, drone power-off, reboot after re-provisioning. "Sim launch variants": the 5-row table and the tmux paragraph stay, linked from A1; `svg_teleop.sh` moves to TELEOP.md §4 (ruling; four different destinations were proposed). Section C's reference material moves to SCENARIOS.md and CONFIG.md; a parameter hazard stays only on the step that sets that parameter (4 to 0).

**D11 · Keeping it short (P2, P8; needs the owner's yes because it changes `tools/docs_check/`).** New checker rules for RUNBOOK: the chooser starts within 15 lines; no code block mixes laptop commands (`airstack.sh`, `mocap.sh`, the QGroundControl AppImage) with `ros2`; `connect` is the last line of its block; `takeoff`, `start` and `land` never share a block; at most 15 lines from a sequence's stop table to its `takeoff`; the lines marked as the shared opening are identical across the real sequences; no dated sentence inside a sequence. A line budget per sequence was voted 3 to 1 (90, 120 and 150 lines proposed); ruling: 180 lines from heading to shutdown, stop table included (the sample is 168), as a warning, not a failure, so nobody cuts a stop row to pass. The shared opening steps are marked with an HTML comment (`<!-- shared-opening -->` … `<!-- /shared-opening -->`) and compared as text after the drone names are normalised. "Dated" means `20\d\d-\d\d-\d\d` or a ledger number `#\d+` outside the world line and the rule-6 notes. Each rule ships with unit tests. `docs/DOCS_STANDARD.md` gains a short "Procedure pages" section with D1 and D2. If the owner says no to the tool change, the rules are written in DOCS_STANDARD only and held by review.

**D12 · The panel first, the service calls in one box (owner, 2026-11-14, after reading the branch on GitHub).** The owner: "instead of using ros service call, get the user to use the foxglove Ui instead. u can still leave the service calls all tgt in one copy paste box as an alternative for the user to use it if neccesary." Each action step names the panel control first (Takeoff, Start, Hold All, Safety Stop · Land All, Reset Fence, the Goal card, the CBF r field, the Rosbag switch; BASESTATION.md §3), with its Must see from the panel (command log, mission chip) where BASESTATION states it. Each sequence carries ONE box of service calls for use without the panel, placed where the `hold` block is today (directly under the stop table). Ruling on its form: pasting the box must not run anything, because one paste of takeoff, start and land together is the hazard fixed in `ba816ea`. The box therefore defines one shell word per call (`takeoff() { ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger; }` …), and the reader types one word at a time in pane 4. The checker rule "takeoff, start and land never share a block" ignores function-definition lines. Checks (`ros2 topic hz`, `echo`, `param get`) stay as commands: they are not service calls. Topic and parameter alternatives (goals, radius) stay in their step as "or pane 4".

## For the owner (answered 2026-11-14)

Answers: 1 yes. 2 yes, and every sequence that launches the commander carries all its steps from a cold start. 3 the owner believes about 30 Hz but has not measured it ("i think 30hz? idk"): the page keeps "a steady rate" until a reading is logged. 4 not answered: left as written.

1. **D11:** allow the checker rules (a change under `tools/docs_check/`, with tests)? Recommended: yes.
2. **D9, order of the opening steps:** C9 and section B start the drone link before QGroundControl and mocap; B9 and B10 start it after. Use the B9 order everywhere? Recommended: yes (it is the newest, flown on 2026-11-13).
3. **`vehicle_status` rate:** one reading on the rig (`ros2 topic hz /drone_2/fmu/out/vehicle_status`) settles 30 Hz or 2 Hz. Until then the page says "a steady rate".
4. **B10 step 14:** the radius is set with both drones in the air and the read-back has no action if it is not 0.9. Left as written; the owner decides the action.

## Builder check (2026-11-14)

A fresh reader listed what it would still ask. Settled above: the variants table has 5 rows; the tail is the single home of the tmux alternative; the provisioning lines DRONE_SETUP.md lacks; the checker's marker and date pattern; the pocket-reference rows; the order claim about `tools/real.sh` (it prints no such order, removed). Also settled:

- **Word count.** `wc -w` on the whole file (9,739 today). The target is reported on the finished page, not enforced by the checker.
- **A "Must see" line is written only when the page states what appears.** No filler such as "it keeps running".
- **C9's first-flight note** ("the 2026-11-12 flight used 2.0 m; the file and the goals below use 1.0 m") stays as one rule-6 line: it limits what the goals were flown at. The rest of C9's history moves.
- **Blocks that span places.** The builder's script lists them; "3 of 36" is the panel's count.

## Left to the builder

- The wording of each step line, within D1 and D2.
- Which destination page gets each moved passage, when D3 names more than one.
- The order of work: inventory → DOCS_STANDARD → destinations receive moved text → one section of RUNBOOK per commit (A, B, B9, B10, C, C9, tail) → prose references on other pages → checker rules last.

## Done when

- The table under "Intent" meets its targets, measured on the finished file.
- The newcomer reader repeats the three tasks of round 1 (first sim flight; one real drone to two goals; sticks dead in B10) and reports lines read and jumps. Targets: no jump out of the section for any task; the B10 answer within 15 lines of the step.
- The flight-test reviewer confirms, row by row against `ac197f7`, that every stop-table row, every hold point and every PREFLIGHT pointer is still present.
- Every command in the new file appears in the file at `ac197f7` (a script compares the two sets; differences are listed and explained).
- `tools/docs_check/check_docs.sh` ends with 0 FAIL; the unit tests pass.
