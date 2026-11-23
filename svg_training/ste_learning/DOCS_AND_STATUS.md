INTERNAL · reference page of the STE learning track, from the specialist draft `archive/DOCS_AND_STATUS_draft.md` (20 Nov 2026). **[PLAN.md](PLAN.md) takes precedence** where the two differ; its section 2 lists every change made at integration.
style rules for STE's own learning track. Input to PLAN.md and the track's STANDARDS.md; kept for the record.

# Documents and status: draft

Sources: [DISCUSSION](DISCUSSION_2026-11-19_20.md) §3–4, `../../CLAUDE.md` (reader-page rules), `../../STANDARDS.md`
§2, §7, §8, `../../docs/README.md` (page labels), `../../docs/linear/README.md`, `../../docs/claude/HANDOFF.md`.

## 1. Documentation plan

### 1.1 Pages and their labels

Labels as in `docs/README.md`: **Read** (newcomers, NUS included), **Reference** (full detail), **Internal** (the lab's
working notes).

| Page | Label | Audience | Holds |
|---|---|---|---|
| `ste_learning/*.md` (DISCUSSION, PLAN, STANDARDS, ARCHITECTURE, CODING_PRACTICES, README) | Internal | lab sessions and agents | the why, the plan, the rules; decisions D1–D9, open proposals P1–P8 |
| `ste_learning/status/STATUS_LATEST.md`, `LOG.md` | Internal | the owner, the lead | the 30-minute status (§2) |
| `ste_learning/drafts/` | Internal | — | first drafts; not maintained |
| `README.md`, new section "STE's own learning track" | Read | NUS and newcomers | 5–8 lines: what the track is, the headline result per finished stage, one GIF, a link to `docs/STE_LEARNING.md` |
| `docs/WHAT_WE_FOUND.md`, one new section per gated result | Read | NUS and newcomers | the result, its caveats, a figure and a GIF, the record linked |
| `docs/STE_LEARNING.md` (new, once the first gated result exists) | Read | NUS and other partners | the track in full: the game rules as trained (tag, filter, drone loss), the learner (shared policy, team critic, league), results per stage, limits, how to repeat |
| `docs/GLOSSARY.md` | Read | everyone | the new terms of §1.4 |
| `records/<date>_<name>_record.md`, `records/LEDGER.md` | Reference | anyone checking a number | one record and one ledger row per gated run |
| `docs/claude/HANDOFF.md` | Internal | the next session | a dated §0 entry per session and per merge |
| `docs/linear/updates/`, `synced/`, `snapshots/` | Internal | the owner, Linear | milestone and issue changes for P-NEAR-31 |

Not written here: the AirStack page "game mode: experimental, not for flight" (decision D4) and its `CHANGES.md` entry.
An AirStack session writes both after the owner approves the change plan. This track supplies the facts the page needs
(policy file, interface file, the tag and filter settings, the equal-output test) in a hand-over note under
`ste_learning/`, and links the page from `docs/STE_LEARNING.md` once it exists.

### 1.2 When each page is updated

| Trigger | Updated | By |
|---|---|---|
| Before a gated run | gates file (dated before the run); the status shows the task as QUEUED | test and QC engineer; writer for status |
| Run ends (any verdict, ABORTED included) | record, ledger row (W numbers on the 5090, renumbered to T at merge), video paths in the record | tooling and test and QC engineer |
| Gate verdict | status (event update); `ste_learning/PLAN.md` task row | writer |
| Stage result (a stage's gates all scored) | `WHAT_WE_FOUND.md` section, `STE_LEARNING.md` section, `README.md` lines, figure by a committed script, GIF | writer, after the lead asks; owner reviews before `main` |
| Merge to `development` | HANDOFF §0, §4, §5 and "Last updated"; `docs/README.md` map row for any new page; glossary terms; the "Ready to push" line appears | writer drafts, lead commits |
| Milestone change | Linear update file in `docs/linear/updates/`, owner uploads, record in `synced/`, new snapshot if titles or statuses changed | writer drafts, owner uploads |
| Owner decision (a P row decided) | DISCUSSION §3 row (append-only), affected STANDARDS rows; GLOSSARY if a term changes | lead; writer for wording |

Large document changes (a new reader page, a restructure) are proposed to the owner first as an outline and reach
`main` only after the owner has read the branch.

### 1.3 Records, videos and figures per gated run

Every gated run has:

1. a gates file written before the run (STANDARDS §7);
2. a record as in STANDARDS §8, simulator named in its first line;
3. one ledger row, append-only;
4. videos recorded inside the run (final and best checkpoint, at least two games each, plus one per scheduled
   evaluation where the trainer supports it), Starling as it looks in the AirStack simulator (decision D9);
5. for every result later shown on a reader page: a figure drawn by a committed script from the run's own data, with a
   numbered caption, and a GIF that plays on GitHub beside it (MP4 links do not play inline).

No videos: the record says why.

### 1.4 Glossary terms to add

Each is one line in `docs/GLOSSARY.md` §3. Terms tied to an open proposal are marked "proposed" until the owner rules;
P1 was ruled at G0 (owner, 22 Nov 2026: the main game has a 1-for-1 tag): STANDARDS §2 and §4 are changed; the reader
page's row "Tag (contact tag)" in `docs/GLOSSARY.md` waits for the owner's yes (reader pages).

| Term | One-line definition | Status |
|---|---|---|
| Tag radius | the 3-D distance between a Guard drone's and a Strike drone's centres below which both are out and land: 1.6 m (the filter's 1.10 m plus 0.5 m) while the pipeline is built, 1.15 m main training after L2 | ruled (P1, G0, 22 Nov 2026) |
| Option B filter | a safety-filter variant: for a Guard–Strike pair only the Guard drone swerves; team-mate pairs keep the even split | proposed (P2) |
| Shared policy | one trained network copied onto every drone of a team; each drone feeds it its own view and gets its own command | decided (D6) |
| Team critic | the part of training that scores the whole team's situation; used only during training, never flown | decided (D6) |
| League (opponent pool) | the set of opponents a team trains against: earlier saved versions of the other team plus scripted opponents, never emptied | decided (D6) |
| Drone loss | a drone leaves the game mid-play (tagged, or a drop-out); the policy must keep playing with the drones left. Same mechanism as the existing "drop-out" row | decided (D6); flight rule open (P7) |
| Tier 1 | add "tier 1 fast engine" as a name of the existing row "STE drone model (PyTorch)" | wording |
| Tier 2 | add "tier 2 Isaac Lab" as a name of the existing row "Isaac Lab physics drones" | wording |
| Human gate | a point in the plan where work stops until the owner decides | wording |

## 2. The 30-minute status

### 2.1 Who, when, where

- **Who.** The `ste-technical-writer` agent, invoked by the lead session. The lead does not rewrite it.
- **When.** Every ~30 minutes while work runs, and at once on four events: a run finished, a gate verdict, a failure
  (crash, NaN, abort, out of memory), a human gate reached. An event update names its trigger in the header line.
- **Where.** `ste_learning/status/STATUS_LATEST.md` (overwritten) and `ste_learning/status/LOG.md` (append-only, one
  dated heading per update). Template: `ste_learning/status/STATUS_TEMPLATE.md`.
- **Shown.** The lead pastes the text in the chat unchanged.
- **Not committed per update** (proposal): a commit every 30 minutes would keep "Ready to push" up for good. The status
  files go in with the session's end-of-session commit.

### 2.2 Inputs

| Input | Read with | Gives |
|---|---|---|
| Process state `ste_learning/status/state.json` | Read | phase, tasks with status, run folders, open decisions |
| Run logs `runs/<date>_<name>/` | `tail` | steps done and total, elapsed time, last metrics |
| Records `records/*_record.md`, `records/LEDGER.md` | Read | verdicts and headline numbers |
| GPU | `nvidia-smi`, `scripts/gpu_pause.sh status` | use, power, memory; jobs running and paused |
| Push state | `git rev-parse main` in the live clone and the mirror; `git status -sb` in the mirror | "Ready to push" line |
| Open decisions | DISCUSSION §3 (OPEN rows), state.json | "Waiting on you" |

Push state is read only; the writer never fetches or pulls. The live clone's own "ahead" count is stale (it showed
"ahead 89" on 20 November while the mirror and GitHub were level), so: live `main` ≠ mirror `main` → "Mirror not
updated"; equal and mirror ahead of its `origin/main` → bold "Ready to push"; ahead 0 → no line.

### 2.3 Format

Exactly the owner's format (DISCUSSION §4), as laid out in `STATUS_TEMPLATE.md`: header line, three tables (phases;
current phase task by task; other workstreams), then **Next**, **Waiting on you**, and **Ready to push** while it applies.

### 2.4 Rules

- No invented numbers. Each number comes from a record, a log, state.json or a command run for this update.
- An ETA only from a measured rate (remaining steps ÷ steps per minute measured in this run), marked "est.". No rate, no
  ETA.
- A missing or stale state file is reported, not filled in by guesswork.
- PASS, FAIL and INFO only for a run scored against gates written before it.
- Paused jobs (`gpu_pause.sh`) show as PAUSED; their ETA excludes paused time.
- Every task "ID + plain name", IDs only from PLAN.md.

## 3. Style rules for this track's documents

All of STANDARDS §2 applies. In addition:

1. **ID + plain name** for every phase and task, everywhere; repeats are "run N" in details only; T numbers only in
   Evidence or Result cells.
2. **Every label defined** in one line where it first appears on each page, or linked to the glossary. No made-up label
   without a definition (tag radius, option B, league are defined before use).
3. **Reader pages** (label Read): neutral report tone; no "you"/"your"; no conversational headings; no owner quotes,
   clock times or agent roles; mechanisms "likely" until a control test has run; "observed in the training simulator",
   never "validated".
4. **Numbers link records.** Every number on a reader page links the record of the run that produced it; open
   proposals say "proposed" beside the value.
5. **Name the simulator** every time: tier 1 fast engine, tier 2 Isaac Lab, AirStack simulator, real flight.
6. **Pictures.** Every shown result has a script-drawn figure and a GIF that plays on GitHub, from videos recorded
   inside the run.
7. **Tables with room.** Short cells, one idea per cell; detail under the table.

## 4. Open questions for the lead

1. `ste_learning/PLAN.md` does not exist yet: phase and task IDs in the status come from it. Until it does, the status
   cannot be filled.
2. `status/state.json`: who writes it (the orchestrator?), its fields, and how often. The writer only reads it.
3. Commit policy for `STATUS_LATEST.md` and `LOG.md` (§2.1 proposes end of session only).
4. `docs/STE_LEARNING.md`: first written after the first gated stage result, or as an outline now? (Needs the owner's
   yes as a new reader page.)
5. Glossary rows for P1 and P2: add now marked "proposed", or wait for the owner's ruling?
6. The agent file loads only from `.claude/agents/` (`git add -f`); the lead copies it.
