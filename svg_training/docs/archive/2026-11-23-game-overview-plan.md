ARCHIVED 2026-11-23 · superseded by [../OVERVIEW.md](../OVERVIEW.md), the page it planned; kept for the record. Start at [../README.md](../README.md).

# Game overview page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One reader page, `svg_training/docs/OVERVIEW.md`, that gives the lab lead the rules of both games and seven
learnings, plus dated notes on the out-of-date pages and one "start here" path.

**Architecture:** Markdown only, inside `svg_training/`. Content is copied from records and GAME_SPEC (never invented);
existing pages get banners, not rewrites.

**Tech Stack:** GitHub-flavoured Markdown; Python 3 one-liners for the link and number checks.

**Spec:** [2026-11-23-game-overview-design.md](2026-11-23-game-overview-design.md) (approved by the owner 23 Nov 2026,
page name `docs/OVERVIEW.md`, build today).

## Global Constraints

- Write only inside `svg_training/`; commit by explicit path on `development`; never push; never `git add -A`.
- Reader-page rules (svg_training/CLAUDE.md "Git facts that bite", last bullet): neutral and factual; no "you"/"your";
  no owner quotes, clock times, agent roles or "the partner"; every label defined where it first appears; T numbers
  only in an Evidence column, each linking its record; mechanisms say "likely" until a control test has run.
- Every result says "observed in the training simulator" (T63: flight-log analysis); never "validated"; nothing flown.
- STE game values: only those labelled FIXED in `ste_learning/GAME_SPEC.md`; PROPOSED ones → "see GAME_SPEC".
- No status words on OVERVIEW ("in progress", "next", "blocked", "done"); open work = one line pointing to
  `ste_learning/status/STATUS_LATEST.md` and Linear.
- Captions 2–4 sentences, ≤ 400 characters, naming the generating script.
- No new figure; no change to any checker; record bodies, LEDGER and DISCUSSION untouched.

## Review Focus

1. A number on OVERVIEW that differs from its record (most likely failure) — reviewer checks every number against the cited record.
2. A link that does not resolve (renamed pages, anchors) — link check in every task.
3. A PROPOSED value shown as a rule — reviewer checks each STE cell against GAME_SPEC's label.
4. Wording that reads as flight-ready or as a verdict on NUS — reviewer checks against the reader-page rules.
5. A banner that rewrites history in a dated log — banners are added above existing text, nothing deleted.

**Link check** (run from `svg_training/` after each task; expected output `broken: 0`):
```bash
python3 - <<'EOF'
import re,os,glob
bad=0
for f in ["docs/OVERVIEW.md","README.md","docs/README.md","docs/THE_GAME.md","docs/WHAT_WE_FOUND.md","docs/NUS_PORT_REPORT.md","ste_learning/README.md"]:
    if not os.path.exists(f): continue
    for m in re.finditer(r'\]\(([^)#\s]+)(#[^)\s]*)?\)', open(f).read()):
        t=m.group(1)
        if t.startswith("http"): continue
        if not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(f),t))): bad+=1; print(f,t)
print("broken:",bad)
EOF
```

---

### Task 1: The overview page

**Files:** Create `svg_training/docs/OVERVIEW.md`.

**Interfaces:** Produces the path `docs/OVERVIEW.md` that Tasks 2 and 3 link to.

- [ ] **Step 1:** Read the spec's "The page" section and "Builder check, answers"; read README §3, GAME_SPEC lines 1–60,
  and the records named in the spec for each learning.
- [ ] **Step 2:** Write the page: line 1 label `READ · TRAINING SIMULATOR ONLY: the two games' rules and the seven main
  learnings so far, each with its record.`; then H1 `# Overview: the game and what the work has shown`; then the six
  parts in the spec's order (answer + box; two-games table + 1.15 m caveat line; Figures 1–2; seven learnings as a table
  `Learning | Number | Evidence`; what has not been done + one open-work line; where to read more). ≤ 80 lines.
- [ ] **Step 3:** Run the link check. Expected `broken: 0`.
- [ ] **Step 4:** Commit: `git add svg_training/docs/OVERVIEW.md && git commit -m "svg_training docs: OVERVIEW.md, the two games' rules and seven learnings (design 2026-11-23)"`.

### Task 2: Dated notes on out-of-date pages; THE_GAME tag sentence

**Files:** Modify `svg_training/README.md` (start of §6 and of §7), `svg_training/docs/NUS_PORT_REPORT.md` (start of §12),
`svg_training/docs/WHAT_WE_FOUND.md` (under the H1), `svg_training/docs/THE_GAME.md` (the "Contact tags are a separate
track" sentence in "The game").

**Interfaces:** Consumes `docs/OVERVIEW.md` (relative links: `docs/OVERVIEW.md` from README, `OVERVIEW.md` from docs/).

- [ ] **Step 1:** Add above existing text, one blockquote each: `> **Superseded on 22 November 2026.** The NUS route was
  paused on 20 November and STE trains its own strategies in a game with a tag (rules fixed at gate G0, 22 November).
  The rules and the main learnings: [overview](<path>/OVERVIEW.md).` Delete nothing.
- [ ] **Step 2:** In THE_GAME, replace the sentence "Contact tags are a separate track ([glossary](GLOSSARY.md))." with:
  "STE's own game (rules fixed at gate G0, 22 November 2026) adds a tag: a Guard drone that comes within the tag
  distance of a Strike drone takes it out and is out too ([overview](OVERVIEW.md))." Nothing else changes.
- [ ] **Step 3:** Link check, `broken: 0`.
- [ ] **Step 4:** Commit the four files by path: `svg_training docs: dated notes on pages superseded by gate G0; THE_GAME tag sentence`.

### Task 3: One "start here" path

**Files:** Modify `svg_training/README.md` (directly under the **For** paragraph at the top), `svg_training/docs/README.md`
(first row of the page map), `svg_training/ste_learning/README.md` (line 1 label: "the page to read first" → "the lab's
working folder for the STE learning track").

- [ ] **Step 1:** README: add one line `**The rules and the main learnings on one page:** [overview](docs/OVERVIEW.md).`
- [ ] **Step 2:** docs/README.md: add `| [OVERVIEW.md](OVERVIEW.md) | the two games' rules and the seven main learnings, each with its record |` as the first row of the Read table.
- [ ] **Step 3:** ste_learning/README.md line 1 as above; nothing else.
- [ ] **Step 4:** Link check, `broken: 0`; commit the three files by path: `svg_training docs: one start-here path to OVERVIEW.md`.

### After the tasks
Final review on the most capable model (numbers v records, reader-page rules, spec coverage), one fix wave, scoped
re-review; newcomer acceptance (the three questions from `README.md`, each ≤ 60 lines and ≤ 1 click); HANDOFF §0 line;
mirror pull; "Ready to push" line to the owner.
