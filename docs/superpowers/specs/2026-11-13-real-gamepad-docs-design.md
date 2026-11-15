# Design — the docs catch up with the real gamepad and two-drone flights

Date: 2026-11-13. Status: **approved by the owner on 2026-11-13** ("ok"), with the three recommendations under "For the owner" accepted. The owner also asked for reviewers on the documentation and on the design after the writing.
Process: `quality-change` (recon → four-hat panel, two rounds → this design → builder check → owner).

## Intent

The owner asked: "using the updated video and CBF stuff from my airstack main local folder, could you engage the technical writers to update the github documentation?" and then: "from the galley lead video, u can use videos from CMU as well. maybe have a hero video image in the git. the reference can be found in /home/jeremychia/Documents/GitHub/Strike-Versus-Guard".

The results pages are current: ledger rows 33 to 37, `docs/projects/HTX-R2.md`, `docs/MILESTONES.md`. The how-to pages are not. `tools/real.sh`, the front door used for every real gamepad flight, is mentioned in none of RUNBOOK, TELEOP, CONFIG, PREFLIGHT or TROUBLESHOOTING.

Measured by the newcomer reader on today's pages, starting from the root `README.md`:

| Question | Today | Target |
|---|---|---|
| How do I fly one real drone with the gamepad today? Give me the commands in order. | 4 pages, about 450 lines, 2 clicks, and the answer is the old flow (`tools/real.sh` is never reached) | at most 2 pages, 150 lines, 1 click |
| Which drone is which, and what is `drone_1`'s status? | 4 pages, 3 clicks, and the pages contradict each other ("GROUNDED" on three, "flies with a watcher" on one) | 1 click, about 5 lines, one wording |
| What did the two-drone collision-filter test show: real or sim, the number with its pass line, and where is the video? | 2 clicks, two tests, two numbers, three radii | 1 click, one number with its pass line |

## Goals

1. The README opens with a hero clip of the lab's own work, and its gallery shows the two flights of 2026-11-13.
2. A reader reaches a correct, complete gamepad session in one click from the README.
3. The real gamepad procedure exists in exactly one place.
4. Every page uses the same wording for the older Starling. No page says "grounded" or "fixed".
5. The safety card and the iron rules carry what the flights of 2026-11-12 and 2026-11-13 taught.
6. No how-to page holds a result. Things now seen on the real drone point to their ledger row.

## Non-goals

- Shortening or restructuring `docs/TELEOP.md` (4,778 words against a 2,000-word budget). The owner deferred the big trim on 2026-10-21. The page is corrected in place.
- A README parity check in `tools/docs_check/` (panel P8, 3 to 1). It changes a checker rule, which is a project of its own. Recorded as a follow-up; the per-task reviewer checks the README for typed statuses and stray numbers by hand.
- Any change under `AirStack/`, any real-drone PX4 or VOXL setting, the sim pages, the results pages (except one banner line), new Linear issues.

## Constraints

- Linear is the naming authority (`docs/plans/2026-11-13-project-plan-linear.md`): ids and titles verbatim, no status typed by hand.
- Results live in `docs/record/LEDGER.md` and the project pages. The ledger is append-only.
- `python3 tools/docs_check/check_docs.py` ends with 0 FAIL at every commit. The `IRON_RULES` block in `docs/PREFLIGHT.md` and `CLAUDE.md` must stay byte-identical, and `docs/AI_ASSIST.md` must quote the rule count.
- Commands shown to an operator are full sequences with literal names (`drone_1`, `drone_2`), in the order `tools/real.sh` prints them (pad pane 5 before commander pane 3), and the commander line carries `use_foxglove_studio:=true`.
- Sim and real are never readable as the same thing. Behaviour that was not flown is labelled as not flown.
- Wording: short plain sentences; "motion-capture positioning (mocap)", never "under mocap"; no overclaiming.
- CMU clips carry the line "Video: AirLab, Carnegie Mellon University, CC BY-SA 4.0; re-encoded" wherever they appear.
- Work in the worktree `../AirStack-starling-max2-docsrefresh` on branch `docs/real-gamepad-docs`, fast-forwarded to main; never pushed by the assistant.

## Decisions (with the panel's vote)

**D1 · Hero (unanimous).** The README leads with the lab's own captioned showcase of 2026-11-13, as a GIF that plays inline: 12 to 15 s, about 800 px wide, at most 4 MB (P2, 3 to 1; the flight-test engineer wanted 3 MB). It is cut from `videos/cbf_teleop_two_drones_showcase.mp4`, must include one approach where the filter engages, and ends on the result card. File: `assets/cbf_teleop_two_drones_hero.gif`. The image links to the full mp4. It sits under the title and the one-paragraph introduction, above "I want to…".

**D2 · One number on the README (P1, unanimous after two changed their minds).** The hero caption carries the only result number on the page, with its pass line, as the link text to ledger row 37: "closest 1.76 m, pass mark 1.40 m". Gallery rows carry no result numbers. The existing 2026-11-12 row loses its hand-typed numbers and links to ledger row 35.

**D3 · Gallery in two groups (unanimous).** "Flown here" and "The same software at CMU". "Flown here" gains two rows, newest first: the hand-flown two-drone flight (GIF cut from `videos/cbf_teleop_two_drones_real_labeled_1080p.mp4`) and the first gamepad flight (GIF cut from `videos/xbox_teleop_real_1080p.mp4`). The two 2026-09 rows (previous software) retire to `pictures/README.md` as observed on the previous software (P6, 3 to 1). Each group is capped at six rows. The CMU group holds two clips that preview the next demos: random goals and figure-eight, converted from `/home/jeremychia/Documents/GitHub/Strike-Versus-Guard/public/media/random-goals.mp4` and `figure-eight-head-on.mp4`, each with the credit line.

**D4 · Which drone is which (P9, unanimous).** One line in the "I want to…" row for flying the real drone: the older Starling is `drone_1`, the newer is `drone_2`, with the hazard-6 wording for the older one and a link to `docs/CONFIG.md`. The README's first paragraph says two Starlings, not one. A new "I want to…" row points to the gamepad session.

**D5 · Home of the gamepad procedure (unanimous on the home; P3, 3 to 1 for placing it under §B).** Two new sections in `docs/RUNBOOK.md` under §B, after step 8. Ruling on the names: the panel voted "B7" and "B8", but §B already numbers its steps 0 to 8, so the sections are **"B9 — Fly one real drone with the gamepad"** and **"B10 — Two real drones, one flown by hand"**. `docs/TELEOP.md` §5 becomes a short corrected paragraph and a link to B9, with no commands.

B9 holds, in this order: (1) which drone is which and the watcher rule for `drone_1`; (2) the pad: Logitech F310, back switch on X, MODE light off, `tools/real.sh pad`; (3) the cold start with literal names, `tools/real.sh teleop drone_2` before the panes; (4) the pad pane stays up for the whole flight, the pad-alive check, the Sticks card; (5) fly: `takeoff` flies a straight line to the takeoff point, `start`, then the sticks (right stick in room axes, LB locks climb and turn); (6) a stop table, each row with its ledger row or the label "not flown"; (7) the full shutdown; (8) one pointer line to ledger row 36. B10 is the two-drone variant (`goal_two_ours.yaml` with `teleop_drones:=drone_2`), with its own stop table and a pointer to ledger row 37. Addition 5 (let go once the filter resists) is a stop-table row in B10.

**D6 · C9's opening (unanimous).** "Not flyable as written today ... GROUNDED" is replaced by the hazard-6 wording. The §B and §C headings lose "⏳ STE on this branch" where a ledger row now exists, and point to it.

**D7 · Safety card and iron rules (P4, unanimous).** Iron rule 3 is amended to cover an RC kill: after a manual takeover or an RC kill, call `land` once. One new iron rule 10: stand each drone on its own takeoff point, nose toward +x, and a second person watches `drone_1`'s front-right motor at every takeoff. The pad items are card checklist lines, not iron rules: back switch on X and MODE light off with `tools/real.sh teleop` ending in PASS; the pad-alive check before takeoff; the pad pane open until DISARMED. The card may grow to about 80 lines. `docs/AI_ASSIST.md` follows (rule count and never-do table).

**D8 · Card corrections found by the flight-test engineer (P10, unanimous).** Fix now: the line saying a disconnected pad holds position becomes "expected from the code, not flown"; the lines that name only `drone_1` name the drone being flown; the `joy_map` flow is replaced by `tools/real.sh`; the header line stops saying the gamepad is unflown. Ask the owner: the 0.5 m/s cap against the 0.56 and 0.66 m/s seen on the fence runs (see "For the owner").

**D9 · The mark for "seen on the real drone" (P5, 3 to 1).** A "⏳ STE" mark for something now seen is replaced by the short form "Seen once on the real drone ([#36])" (or the row that applies). Ruling on the minority view: wherever a page lists behaviours, a "Not flown:" line sits beside the mark, so no page reads as a pass. The caveats (direction by the owner's report, no video) stay in the ledger row.

**D10 · Troubleshooting (P7, 3 to 1).** Seven new rows, each 40 words or fewer: sticks ignored after Start; "arming denied"; the second drone missing in QGroundControl; the keyboard read as a joystick; `ros2 topic echo` says the topic is not published; a drone tips at lift-off; the CBF radius back at 0.55 after a restart. "Both drones fly at each other at takeoff" is not a symptom row: iron rule 10 prevents it.

**D11 · One-line pages.** `docs/CONFIG.md` (the `drone_1` row, the gamepad config and profile rows, the two-drone config's fence and takeoff height), `docs/SCENARIOS.md` line 8, `docs/BASESTATION.md` §3.13, `docs/MIGRATION.md` row 5, `docs/GLOSSARY.md` (lock button, keep-out, pass line, pad check), `pictures/README.md`, the banner line of `docs/projects/HTX-R2.md`.

**D12 · Order of work (P12, unanimous).** The card and iron rules first, then the two runbook sections, the teleop page, troubleshooting, the one-line pages, the media, and the README last, because it only points at the others.

## Left to the builder

- The exact seconds cut for the hero and the gallery GIFs, and the encoder settings, inside the size caps.
- The wording of every sentence, inside the constraints above.
- Whether B9 repeats §B steps 1 to 5 in full or states them once as its own numbered cold start (the owner's rule is a full sequence, so the section must be runnable from a cold start without jumping back).
- The row order inside the stop tables.

## Builder check (a fresh reader's questions, answered)

1. **Which file is the safety card?** `docs/PREFLIGHT.md`, the whole file (66 lines today, about 80 after). The pad checklist lines go there, outside the `IRON_RULES` block. `docs/BASESTATION.md` only points to it.
2. **What else changes when rule 10 is added?** Rule 10 is appended, so "iron rule 9" keeps its number and its 40 or so mentions stay. Two counts change: `docs/GLOSSARY.md` line 261 ("nine" becomes "ten") and `docs/AI_ASSIST.md` line 12 ("the 9 iron rules" becomes "the 10 iron rules"), plus the AI_ASSIST never-do table. `tools/docs_check/safety_registry.txt` is not edited. No new ⚠️ line is added unless it carries an already registered phrase, so the check still ends 13 PASS · 6 WARN · 0 FAIL · 1 SKIP.
3. **Rules against the hazard list.** `docs/projects/HTX-R2.md` keeps its hazards as written. The rules are short orders and may be worded differently, but must not contradict hazards 5, 6 and 7. Rule 10 links to the hazard list instead of quoting it. Hazard 9 (no warning when no pad is sending) reaches the card as a new line: the pad-alive check before takeoff.
4. **The hazard-6 wording.** The sentence, used as is: "The older Starling (`drone_1`) flies by the owner's decision, with a watcher on its front-right motor at every takeoff." In a table cell the short form is allowed: "`drone_1` (older Starling): flies by the owner's decision, with a watcher on its front-right motor." This is a standing decision, not a Linear status, so it may appear on the README, with a link to the hazard list.
5. **The hero cut and the size cap.** The size cap wins. Tools: `ffmpeg` with `palettegen` and `paletteuse` only (nothing is installed). If the file is over 4 MB, drop to 10 frames per second, then to 640 px wide. The cut is picked from a one-frame-per-second contact sheet of the showcase: the first captioned approach where the distance readout stops falling, then the closing card. The owner sees the candidate before it is committed.
6. **Which "⏳ STE" marks change?** Targeted, not global. The first task of the plan writes an inventory: every "⏳ STE" in RUNBOOK (4), TELEOP (7), CONFIG (2), SCENARIOS (7), BASESTATION (7), MIGRATION (8), DRONE_SETUP (2) and GLOSSARY (1), each marked "replace, ledger row n" or "keep". A mark is replaced only when a ledger row from 33 to 37 records that exact behaviour on the real drone. The orchestrator rules on the inventory before any page is written.
7. **How far is `docs/TELEOP.md` corrected?** Every statement that contradicts B9 or ledger rows 36 and 37: §5, the header lines 14 and 22, and lines 205, 343 and 386. The sim drive-mode text stays as it is (it is sim only and true). Nothing is moved or trimmed.
8. **The "grounded" check.** After the work, `grep -rliw grounded README.md docs/*.md docs/projects/*.md` returns nothing. Only `docs/record/LEDGER.md` (row 34, append-only) keeps the word.

## For the owner

1. **The 0.5 m/s gamepad cap.** The card caps `teleop_max_speed_mps` at 0.5. On the fence runs the drone reached 0.56 and 0.66 m/s (ledger row 36). The cap limits the command and the drone overshoots it. Keep the cap and say on the card that the drone may exceed it by about a third, or lower the cap?
2. **The iron rules.** D7 changes rule 3 and adds rule 10. These are your rules. Confirm, or say which items should stay checklist lines only.
3. **The CMU clips.** Two clips, random goals and figure-eight, with the credit line. Confirm, or name others.
4. **Reprint.** The card changes, so the printed copy in the hangar needs replacing after this lands.

## Done when

- The three questions in the Intent table meet their targets, measured by a fresh newcomer reader starting from `README.md`.
- `grep -rliw grounded README.md docs/*.md docs/projects/*.md` returns nothing (`-w`, so "backgrounded" in MIGRATION.md does not count). Only the ledger (row 34) keeps the word.
- `tools/real.sh` is linked from `README.md`, the runbook's §B and `docs/TELEOP.md` §5.
- The docs check ends with 0 FAIL, and the iron rules are identical in `CLAUDE.md` and `docs/PREFLIGHT.md`.
- The README shows one result number, in the hero caption, linked to ledger row 37.

## As built (2026-11-13, after the final reviews)

**The owner's answers.** "ok" to the design with the three recommendations: (1) the 0.5 m/s cap stays, and the card says the drone can overshoot it by about a third; (2) rule 3 is amended and rule 10 is added, as worded in D7; (3) the two CMU clips are random goals and figure-eight. He also asked for reviewers on the documentation and on the design. Three ran on the whole branch: documentation, safety (flight-test engineer), design (technical writer, on the rendered README).

**Key to the panel's ballot (P1 to P12).** P1 numbers in README captions. P2 hero size cap. P3 where the two runbook sections sit. P4 iron rules. P5 the label that replaces "⏳ STE". P6 which gallery rows retire. P7 troubleshooting rows. P8 a README parity check. P9 which drone is which on the README. P10 card lines found wrong. P11 the three acceptance questions. P12 writing order. Panellists: technical writer, flight-test engineer, engineering manager, newcomer reader.

**Built differently from the decisions above, and why.**

| Decision | As built | Why |
|---|---|---|
| D1 hero | 14 s (6 to 17 s, then 42 to 45 s of the showcase), 800 px, 12 frames per second, 3.3 MB | Inside the caps. `ffmpeg` with `palettegen` and `paletteuse` |
| D3 gallery, two groups | Three groups: "Flown here" (real drones only), "Rehearsed in Isaac Sim", "Flown at CMU with the same software (not our flights)" | The design reviewer found sim rows under the heading "Flown here" |
| D3 gallery rows | Four September GIFs left the README (two rows of two). Two panel GIFs were added for ledger rows 36 and 37. Gallery images are 380 px | The new rows had an empty right cell. Two 400 px cells do not fit GitHub's column |
| D3 CMU credit | One credit line under the CMU table, for both clips | The reviewer found the same long sentence twice |
| D6 headings | The §B and §C headings are neutral. What has flown is on the first line under each | A status in a heading goes stale and changes its anchor |
| D7 card | 70 lines. One pointer line to B10's stop table was added, although the panel had voted the "let go" item off the card. The takeoff box says everyone stays outside the net. The KILL row says `land` brings down every airborne drone | Both safety reviewers asked for them. The iron rules themselves are as the owner approved |
| D7 card version | `v2026-11-14` | The checker refuses a second edit under one date. The card is reprinted on 2026-11-14 at the earliest |
| D10 troubleshooting | Seven rows asked for, six added and one merged. "Arming denied" extends the existing DENIED row: no cause was recorded in the repo, and the safety reviewer asked for "`land` once before touching the switch". The QGroundControl row uses what CONFIG.md records | The plan's rule: a cause not in the repo is not invented |
| D5 B10 | Carries C9's separation readout block in full | The safety reviewer: it is the pilot's only distance instrument |
| D11 | `docs/projects/HTX-R2.md`: only the banner sentence gained "two Starlings since 2026-11-12". `docs/DRONE_SETUP.md` and `CLAUDE.md` (two lines outside the iron rules) were also corrected | The whole-branch reviewer found the wrong drone named in the re-provisioning step |
| C9 (not in the design) | Brought in line with `goal_two_ours.yaml` (takeoff and goal height 1.0 m), its `push-apart` answer made the card's (`land`), its result numbers replaced by a pointer to ledger row 35 | Found by the safety and documentation reviewers. C9 is where B10 sends the reader |

**Acceptance, measured by a fresh newcomer reader from `README.md` on 2026-11-13.**

| Question | Result | Measured |
|---|---|---|
| Fly one real drone with the gamepad, commands in order | Right answer. Misses the target on pages and lines | 3 pages, 2 clicks, about 225 lines. The commands are 1 click and one section (B9). The third page is the safety card, which the README sends every pilot to first, by design |
| Which drone is which, and `drone_1`'s status | Pass | README only, 0 clicks, 1 line. No page disagreed |
| The hand-flown two-drone test: real or sim, number and pass line, video | Pass | README only, 0 clicks, 2 lines |

After the test B9 gained a pane table, the wait for "sticks live" and a pointer to the stop table. B9 is 143 lines against the plan's 140.

**Not done, for the owner.** See the hand-over message of 2026-11-13: the iron-rule wording the safety reviewer would add, the stop distance for B10, the stale comments at the top of the two `_ours` yamls, the readout's missing stale-data check.

## Follow-ups (not in this work)

- Extend the docs check to the README: Linear titles identical, no typed status, no result number outside a ledger link.
- The deferred trim of `docs/TELEOP.md`.
