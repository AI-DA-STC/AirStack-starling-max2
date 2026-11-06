# Design — the sim keyboard session moves to localisation/README.md

Date: 2026-11-06. Status: **approved by the owner 2026-11-06** ("the rest of the design is ok"), with one addition: the "nothing on this software has flown" sentence is fixed too ("yeah this is confusing man").
Process: `quality-change` (recon → four-hat panel, two rounds → this design → builder check → owner).

## Intent

The owner looked for the teleop documentation and expected it with the localisation page:
"where is the teleop documentation content? i think u can merge it with localization.md right?"
(There is no `localization.md`; the page is `localisation/README.md`.) The owner flies the sim from
the cuVSLAM Foxglove window, which `localisation/scripts/slam_up.sh` starts, so that page is where
the keyboard session belongs. The owner agreed that only the keyboard part moves, and that the
gamepad and real-drone content of `docs/TELEOP.md` stays.

Why it matters, measured by the newcomer reader on today's pages, starting from the root `README.md`:

| Question | Today |
|---|---|
| What do I type to fly drone_1 by keyboard in the construction site? | about 320 lines over 3 pages, after about 40 lines of the wrong (three-drone) cold start |
| Which keys do what, and what is Drive mode? | about 207 lines over 2 pages |
| Has it been flown, and where is the video? | about 220 lines over 2 pages, one dead end |

## Goals

1. A newcomer starts a one-drone keyboard session from `localisation/README.md` alone.
2. Each of these exists in exactly one place: the keyboard cold start, the key table, the "import the layout once" instruction, the evidence list.
3. A real-drone reader of `docs/TELEOP.md` still sees that Drive mode, the relay and `teleop_single_ours.yaml` are sim only.
4. `docs/TELEOP.md` stops holding results. DOCS_STANDARD §1 says procedure pages never hold results; the Evidence block added on 2026-11-06 (commit 2cbce49) broke that rule, and this move repairs it.

5. No page says "nothing on this software has flown" without saying it means the real drone (owner, 2026-11-06).

## Non-goals

- No change to any tool, script, layout, config or to `AirStack/`. Documentation and the docs checker only.
- No rewrite of the gamepad sections of `docs/TELEOP.md` (§1, §2, §3, §4 to §11).
- No change to `docs/record/CHANGES.md`, `docs/record/LEDGER.md`, any record, `docs/plans/*`, or older specs and plans.
- No trimming of the scored three-drone "Run it" steps beyond line 56.
- Not the deferred big docs restructure (MOVE/TRIM phases).

## Constraints

- Linear ids and titles verbatim. Result cells only from records. Sim never reads as real.
- Nothing flies on cuVSLAM. The sim drone flies on PX4's own sim estimate. The text says so.
- On-screen words are `Drive mode` and `Room mode`.
- `tools/docs_check/check_docs.py` ends with 0 FAIL at every commit. Order: content lands, links are retargeted, old text is cut last.
- Commit on `main` in the live clone. Never push. Pull the mirror at the end.
- The heading `### 3b · Keyboard instead of a pad (sim only, ours)` keeps its number and its words, because four rows of the append-only change log cite "TELEOP §3b".

## Decisions

Agreed by all four panellists in round 1: the strip, chase view, grid, layout loading and cold start
move; the "3b" heading stays; one new README section, not woven into "Run it"; two whole cold starts
with a chooser; README line 56 shrinks to a pointer; the layout import is stated once.

| # | Decision | Vote |
|---|---|---|
| P1 | The **key table moves** to the README, beside the cold start. The **Tk-window paragraphs stay** in TELEOP §3b (how to start `tools/sim.sh keys`, focus and let-go rules, one `/joy` source), with a link to the table. They need no cuVSLAM. | 3–1 (flight-test wanted everything moved) |
| P2 | The **evidence list lives in the new README section**, each line tagged simulation. | 3–1 (writer wanted HTX-R1 only) |
| P3 | **One page.** `localisation/README.md`, expected 215 to 265 lines. | 4–0 |
| P4 | The new section sits **after "Run it"**. | 4–0 |
| P5 | Under TELEOP's "3b" heading a **sim-only warning stays**. | 4–0 |
| P6 | A new **`single-home` check at WARN level**. | 3–1 (manager wanted FAIL) |
| P7 | The chooser is a **two-row table** in the first 25 lines of the README. | 4–0 |

Coordinator rulings on the split votes:

- **P2.** The writer's objection is one-place-per-fact. So the README evidence list carries links and verdict words only: the video, `ledger #32` → record with "PASS", the owner-confirmed items, and the Linear ids with a link to HTX-R1. The numbers (0.9°, 0.17 m, gates) stay in `docs/projects/HTX-R1.md` and the record. Cost if wrong: one extra click to read the numbers.
- **P6.** WARN, as voted. A phrase match that fails a commit could block an unrelated safety edit. Cost if wrong: a copy can reappear and only warn.

### `localisation/README.md` after the move

1. Title, `DO · SIM` banner, picture. Unchanged.
2. **"Which run do you want?"**, a two-row table inside the first 25 lines. Columns: goal · drones · config · go to.
   - Scored camera run · 3 · `cbf_sim.yaml`, `random_goals` · "Run it"
   - Fly it yourself by keyboard · 1 · `teleop_single_ours.yaml` · "Fly it with the keyboard"
3. "Where it runs". One row added for the Cockpit tab (`teleop.launch.py`) and the relay (`tools/sim.sh relay`, laptop).
4. "Run it" (the scored three-drone run). Unchanged except line 56, cut to the expected output, the plain SLAM layout import, and one link to the keyboard section.
5. **`## Fly it with the keyboard (one drone, sim only)`**, new:
   - Two opening sentences: what it is; flown in the simulator only, on PX4's own sim estimate, nothing flies on cuVSLAM.
   - `### Evidence`: the list ruled in P2.
   - `### Keys`: the key table, then the Drive mode / Room mode paragraph.
   - `### Cold start`: the ten-step fenced block, moved whole from TELEOP.
   - `### The layout (first time only)`: import once, what `slam_up.sh` then does by itself, backups, "do not import again", how to get the shipped layout back.
   - `### The strip`: the strip bullets and the Grid paragraph.
6. "What you should see", "How a run is scored", "Why the construction site". Unchanged.
7. "The flight on video". One line added pointing to the keyboard video in the section above.
8. "Prerequisites". The `ufw` rule added (the cold start keeps its own step 0, so the list stays whole).
9. "Folder map". Line 151 shortened to one clause with a link.

### `docs/TELEOP.md` after the move

- Title and intro keep their mention of the sim keyboard; the pointer goes to the README section.
- `### 3b · Keyboard instead of a pad (sim only, ours)` keeps, in this order:
  1. the sim-only warning: Drive mode, the relay and `teleop_single_ours.yaml` (it sets `fence_enabled: false` and `teleop_fence_enabled: false`) are for the simulator only and never go on the real drone; real flying is §5 with `teleop_real_ours.yaml`;
  2. the Tk-window paragraphs (P1);
  3. a two-line pointer: keys, cold start, strip, layout, evidence and video are in `localisation/README.md`.
- Removed from TELEOP: the key table, the Drive/Room paragraph, "In Foxglove", Evidence, the strip bullets, Grid, the cold start.
- §4's sentence about `tools/sim.sh keys` and the relay points to the README section.

### Links

Retargeted to the README section: `docs/RUNBOOK.md` (the keyboard pointer), `docs/GLOSSARY.md`
(the Drive mode entry), `docs/CONFIG.md` (the `teleop_single_ours.yaml` row),
`docs/projects/HTX-R1.md` (NEAR-921 paragraph), `tools/README.md` (the two `teleop/` rows),
`CLAUDE.md` and the root `README.md` doc-table rows. A link that is about the Tk window keeps
pointing at TELEOP §3b. The change log, older specs and plans are not touched.

### The `single-home` check

A new registry `tools/docs_check/single_home.txt`, same pipe-separated style as `values_registry.txt`:
a phrase and the files allowed to contain it. A match in any other live docs page is a WARN that
names the file and line. First rows:

| Phrase | Allowed in |
|---|---|
| `Import from file → `/teleop-foxglove/teleop-cuvslam.json`` | `localisation/README.md` |
| `teleop.launch.py config:=$CFG` together with `teleop_single_ours.yaml` | `localisation/README.md`, `docs/TELEOP.md` (§4) |
| `sim_keyboard_teleop_2026-11-04.mp4` | `localisation/README.md`, `docs/projects/HTX-R1.md` |
| `never go on the real drone` (the 3b warning) | must be present in `docs/TELEOP.md` (a missing warning is the WARN) |

Dated history is exempt: `docs/plans/`, `docs/superpowers/`, `docs/record/`. The check gets unit
tests beside the existing checker tests, and one line in `tools/docs_check/README.md` and
DOCS_STANDARD's gate list.

### Real or sim: "nothing on this software has flown" (added by the owner, 2026-11-06)

The sentence means the real drone, but does not say so, and the same pages now say the keyboard has
flown in sim. Every live page that carries it names the real drone:

| Page | Today | After |
|---|---|---|
| `README.md` line 9 | "nothing on this software has flown" | "nothing on this software has flown on the real drone" |
| `CLAUDE.md` line 8 | "nothing on this software has flown; sim results in …" | "nothing on this software has flown on the real drone; sim results in …" |
| `docs/MILESTONES.md` line 5 | "Nothing on this software (…) has flown" | "… has flown on the real drone" |
| `docs/projects/HTX-R2.md` line 1 | "nothing on this software has flown" | "nothing on this software has flown on the real drone" |
| `docs/projects/HTX-R1.md` line 1 | "nothing here has flown" | "nothing here flew a real drone" |
| `docs/TELEOP.md` intro | "nothing below has flown at STE" | "nothing below has flown on the real drone at STE" |
| `docs/PREFLIGHT.md` line 5 | "nothing on this software has flown" | "nothing on this software has flown on the real drone" |

`docs/SCENARIOS.md` already says "on the real drone" and is unchanged. No softening words are added:
the hazard meaning stays exactly as strong. Coordinator's call: `docs/PREFLIGHT.md` is included, so
its version token on line 1 is bumped to the edit date and the laminated card needs a reprint (one
was already pending since v2026-11-02). Dated history (`docs/plans/`, `docs/superpowers/`,
`docs/record/`) is not touched. The flight-test reviewer reads each of the seven lines.

## Builder check (answers to a fresh reader's questions)

All six were settled without the owner. Items marked "coordinator's call" are choices, not owner decisions.

1. **The layout import appears twice if the cold start is moved whole.** Coordinator's call: the instruction is written once, under `### The layout (first time only)`. The comment in cold-start step 7 becomes "First time only: import the layout, see The layout below". Done-when 5 compares the commands of the ten steps, not their comments. README line 56 keeps the plain SLAM layout (`cuvslam_slam_view.json`), which is a different file and not in the registry.
2. **The 3b warning's exact phrase.** Coordinator's call: the warning contains the fixed words "never go on the real drone". The registry has two kinds of row: `only` (the phrase may appear in the listed files and nowhere else) and `require` (the phrase must appear in the listed file). Both kinds are WARN.
3. **The ⚠️ registry.** Coordinator's call: the new text uses no ⚠️ glyph and no `[SIM]` token, so `safety_registry.txt` gets no new row and the `warnings-registered` count does not change. The warning is plain bold text opening with "Sim only." Evidence lines say "simulation" in words.
4. **What the 70 / 30 / 15 lines count.** Lines the reader reads on `localisation/README.md`, from the top of that page, following the chooser's jump link. Lines skipped by a jump do not count. Fenced blocks and blank lines inside what is read do count. The cold-start block is not trimmed to meet the number; if the count misses, the opening text is shortened instead.
5. **Source of the evidence list.** Already answered by the repo: `docs/projects/HTX-R1.md` holds the numbers (the NEAR-920 row and paragraph, ledger #32). HTX-R1 gets a link retarget only. The README list is TELEOP's Evidence block at commit 2cbce49 without its numbers.
6. **A line gate on the README.** Already answered by the repo: the FAIL-level page budgets cover `docs/MILESTONES.md` and `docs/projects/*.md` only. The README has a WARN-level word budget and no line gate.

## Left to the builder

- Exact wording of moved text where a sentence must change to make sense on its new page. Moved blocks are otherwise copied, not rewritten; every difference is listed for the reviewer.
- The anchor slug of the new heading and the form of each retargeted link.
- The number and order of commits, given the content → links → cut order.
- Whether the phrase rows of the registry match on a normalised line or a regular expression.

## Done when

1. `check_docs.py`: 0 FAIL at every commit; the `single-home` check reports no WARN on the final tree.
2. `docs/TELEOP.md` contains no key table, no cold start, no Evidence block; "3b" still resolves and carries the sim-only warning.
3. Every retargeted link resolves.
4. Newcomer acceptance, a fresh reader starting from the root `README.md`, same three questions as the BEFORE table: cold start ≤ 70 lines on one page after the root README; keys and Drive mode ≤ 30 lines on the same page; flown-or-not and the video ≤ 15 lines on the same page. Before and after line counts are reported.
5. Goal 5: `grep -rn "has flown"` over the live pages finds no sentence that leaves real or sim unsaid.
6. The moved cold start has the same ten steps and the same commands as the one in TELEOP at commit 2cbce49. Only the step 7 layout comment differs (builder check 1).

## Review focus

- A real-drone reader of TELEOP.md who never opens the README: do they still learn that Drive mode and the fences-off config are sim only?
- Any moved sentence that now reads as a result on hardware.
- A paragraph absorbed into a table after the move (no blank line after a table row).
- Links that still say "TELEOP §3b" but mean moved content.
- The seven "nothing has flown" lines: each must still read as a warning about the real drone, and none may imply a sim result is a real one.
