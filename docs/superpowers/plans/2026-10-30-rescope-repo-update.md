# Rescope repo update — implementation plan

> Executor: superpowers:executing-plans (inline), one fresh whole-branch review at the end, then the newcomer acceptance test.

**Goal:** the repo mirrors Linear after the 2026-10-30 rescope: a new snapshot, the three project pages, MILESTONES.md, DOCS_STANDARD §2, and a docs check that reads the new snapshot.

**Spec:** [2026-10-30-rescope-real-route-nus-cameras-design.md](../specs/2026-10-30-rescope-real-route-nus-cameras-design.md). **Naming authority for this plan:** [docs/plans/2026-10-30-linear-sync-record.md](../../plans/2026-10-30-linear-sync-record.md) (what Linear now holds) on top of [docs/plans/2026-10-26-project-plan-linear.md](../../plans/2026-10-26-project-plan-linear.md). Titles are copied from these files, never retyped.

## Global constraints

- Titles, milestone names and statuses verbatim from the sync record / old snapshot, curly ’ kept.
- Project pages ≤ 250 lines, each `###` section ≤ 40 lines, cells ≤ 120 chars (except titles), MILESTONES ≤ 60 lines (`page-budgets`).
- Every `###` section has a `**Purpose:**` line; "Done when" printed as a target; Result cells `—` unless a record exists.
- Wording: "motion-capture positioning (mocap)", no "under mocap", no status pills. Short plain sentences.
- Never edit `AirStack/`. Never push. Commit in the live clone, pull the mirror.
- M8 flies in NEAR Lab's mocap area (owner, 2026-10-30).

## Review focus

1. A page row whose status is `Canceled` (NEAR-802) must pass parity, not fail as "not in plan file".
2. A page heading that keeps the old milestone name (S5c "Choose the camera…", S8 "Model the chosen camera…") must fail the new milestone-name rule.
3. A change list marked "Applied" whose id map still holds a `NEW-n` without a NEAR id must fail.
4. NEAR-809 must appear once, under S5c, never under S8.
5. The `Linear status` cell for NEAR-786/787/788 must say Done (from the new snapshot); a Result of FAIL with status Done (NEAR-787) must not be "fixed" by rewriting the result.

---

### Task 1: New snapshot `docs/plans/2026-10-30-project-plan-linear.md`

Copy the 10-26 file and apply the sync record: header date 30 October 2026; reconciliation notes (28 milestones, 105 issues: 9 Done, 1 In Progress, 94 Backlog, 1 Canceled; progress = Done ÷ issues not Canceled, as Linear computes it); HTX-R2 project name "(M2–M8)" in the split table and heading; milestones in Linear's order (HTX-R1: S1–S5, S5d, S6, S5e, S5b, S5c, S7–S10; HTX-R2: R1, M2–M8); new milestone sections with the sync record's descriptions and issue tables; S5c/S8 renamed with S5c's new description; issue renames, NEAR-809 moved, NEAR-802 Canceled, NEAR-786/787/788 Done; per-project inventory lines and the inventory table.

Check: `python3 -c` that `plan_issues()` (after Task 2 accepts Canceled) returns 105 ids with 9 Done, 1 In Progress, 1 Canceled; every NEAR-866…892 title equals the sync record's.

### Task 2: Docs check reads the new snapshot (TDD in `tools/tests/test_check_docs.py`)

1. Fixture writes the plan to `C.PLAN_FILE`, not a hard-coded path.
2. RED tests: (a) a `Canceled` row matching the snapshot passes; (b) a page `### S5c · Old name — DESK` against a snapshot `### S5c · New name` fails naming the code; (c) a snapshot milestone missing from every page fails; (d) an "Applied" change list with an unmapped `NEW-n` fails; with all mapped and titles equal it passes; a non-applied change list is ignored.
3. GREEN: `PLAN_FILE = "docs/plans/2026-10-30-project-plan-linear.md"`; `plan_issues()` accepts `Canceled`; `plan_milestones(text)` → `{code: full heading}` from `### ` lines under `## Project`; in `check_linear_parity` compare each page `### ` heading (text before ` — `) with the snapshot by code, and each snapshot milestone must appear on a page; new `check_change_lists()` over `docs/plans/*-linear-change-list.md` with a `**Applied:**` line: every `NEW-n` in the id map has a NEAR id, and each NEW row's title equals the snapshot title of its mapped id. Register it in the check list.
4. Full suite: `python3 -m pytest tools/tests -q` green.

### Task 3: HTX-R1 page

Header snapshot 2026-10-30, plan link, a one-line work order, a four-line "Sim vs real" box (what the sim does not match yet: command route until S5d, PX4 1.16 vs 1.14, rate gains ×0.5 and motor lag off, clock 1.3–2×). Sections in Linear's order. S5: statuses Done for 786/787/788 from the snapshot. New S5d and S5e sections (Purpose, Linear line, Done when from the snapshot, issue table). S5c renamed, tag SIM ONLY (Isaac), new Purpose, 10 rows (802 Canceled, 809 moved in). S8 renamed, NEAR-809 row removed. "Sim debt" heading: the clock now gates S5e (NEAR-871). Budget ≤ 250 lines.

### Task 4: HTX-R2 and HTX-R3 pages

HTX-R2: title "(M2–M8)", snapshot date, NEAR-888 row in M2, new M8 section (REAL DRONE, NEAR Lab mocap area, Purpose, Done when, 4 rows). HTX-R3: snapshot date, NEAR-847/855/856 titles, L2 note "built-in cameras depend on HTX-R1 S5c".

### Task 5: MILESTONES.md, DOCS_STANDARD §2, checker README, spec

MILESTONES: snapshot link/date, HTX-R2 name, R1 row next issue unchanged, HTX-R1 row (S5; next NEAR-789 and NEAR-866), "Sim vs real" box (≤ 4 lines), pages list (M2–M8, ledger #1–#23). DOCS_STANDARD §2: snapshot file and codes (S5b–S5e; M2…M8). `tools/docs_check/README.md` names the new rules. Spec: close the M8 open question. `tools/sim.sh check` green.

### Final

Fresh reviewer on the whole range (opus) with this plan's Review focus; one fix pass; newcomer reader acceptance (three questions from the spec's Done-when); mirror pull; handoff + memory.
