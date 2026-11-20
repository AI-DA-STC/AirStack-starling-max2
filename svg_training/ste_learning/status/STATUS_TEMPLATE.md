INTERNAL · fill-in template for the 30-minute status of STE's own learning track and the NUS port (the `train-status`
skill fills it; NUS port phases come first in the Phases table). Copy it to `STATUS_LATEST.md`
(overwrite), append the same text to `LOG.md`, paste it in the chat. Delete every `<!-- … -->` comment before posting.

<!--
Rules (owner's format; ste_learning/DISCUSSION_2026-11-19_20.md §4):
- Every number comes from a record, a run log, state.json or a command run for this update. No number, no cell: write "not measured".
- An ETA is computed only from a measured rate (steps done ÷ minutes elapsed); write it as "~HH:MM (est., from <rate>)".
- Tasks are always "ID + plain name". IDs come from ste_learning/PLAN.md; never invent one.
- Simulator column: one of "tier 1 fast engine", "tier 2 Isaac Lab", "AirStack simulator", "real flight", or "none" (code, docs).
- Math library column: "PyTorch", "JAX (NUS)" or "none".
- Status words: DONE, RUNNING, PAUSED, QUEUED, BLOCKED, WAITING (human gate), NOT STARTED, PASS, FAIL, INFO, ABORTED.
  PASS / FAIL / INFO only for a run scored against gates written before it.
- Keep cells short (one line); detail goes in the lines under a table, not in the cell.
-->

**Status, <YYYY-MM-DD HH:MM> (+08:00)** · GPU <util %> / <power W> / <memory used GB of total> · <n> training processes (<n> paused) · <machine: laptop or RTX 5090>
<!-- Event updates add the trigger after the time: "event: run finished", "event: gate verdict", "event: failure", "event: human gate reached". -->

## Phases

| Phase | Status | Math library | Simulator | What |
|---|---|---|---|---|
| <phase ID> <plain name> | DONE | PyTorch | tier 1 fast engine | <one line: what the phase delivers> |
| ▶ <phase ID> <plain name> | RUNNING | PyTorch | tier 2 Isaac Lab | <one line> |
| <phase ID> <plain name> | NOT STARTED | PyTorch | AirStack simulator | <one line> |
| <phase ID> <plain name> | NOT STARTED | none | real flight | <one line> |

<!-- Every phase of PLAN.md, in order; the current phase marked ▶. -->

## Phase <N> <plain name>, task by task

| ID | Plain name | Status | Simulator | Result / ETA |
|---|---|---|---|---|
| <N.1> | <plain name> | DONE | tier 1 fast engine | <verdict, headline number> ([record](../../records/<file>)) |
| <N.2> | <plain name> | RUNNING | tier 2 Isaac Lab | <steps done of total>; ETA ~<HH:MM> (est., from <measured rate>) |
| <N.3> | <plain name> | WAITING | none | human gate: <what the owner must decide> |
| <N.4> | <plain name> | NOT STARTED | tier 2 Isaac Lab | after <N.2> |

<!-- Every task of the current phase, pilots, controls, videos and side tasks included. Repeats are "run 2" in the
     cell, not a new ID. T numbers only inside the Result cell, with the record linked. -->

<one or two lines under the table, only if a cell needs explaining: what changed since the last update>

## Other workstreams

| ID | Plain name | Status |
|---|---|---|
| <DOC-n> | <plain name, e.g. reader page for the track> | RUNNING |
| <VID-n> | <plain name, e.g. Starling side-by-side render> | NOT STARTED |
| <AS-n> | <plain name, e.g. AirStack game-mode change plan (owner approval)> | WAITING |

<!-- Anything active outside the current phase: docs, videos, AirStack change plans, NUS follow-up. -->

**Next.** <the next one to three actions, each "ID + plain name", with what triggers them>

**Waiting on you.** <numbered list of owner decisions, each with its ID (e.g. P1 tag radius) and what it blocks; "nothing" if none>

**Ready to push.** <n> commits on `main`, mirror updated; push from GitHub Desktop. <one line: what they contain>
<!-- Include this line only while the mirror (~/Documents/GitHub/AirStack-starling-max2) is ahead of origin/main.
     If live main and mirror main differ, write instead: "Mirror not updated: the lead pulls it before the owner pushes."
     Drop the line once the owner has pushed. -->
