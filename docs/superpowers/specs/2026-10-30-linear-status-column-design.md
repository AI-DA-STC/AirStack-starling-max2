# Linear status column on the project pages — design (2026-10-30)

**Why.** The owner found the issue tables misleading: the Result column holds a test verdict ("FAIL ×3 — min 1.00 m"), so a reader cannot tell whether the Linear issue itself is closed. NEAR-787 was re-run and recorded (its goal) yet reads FAIL against the stricter 1.10 m gate.

**Decision (owner, 2026-10-30).** Offered: a "Goal met?" column judged from the records, a plain-words Result cell, a Linear status column, or no change. The owner chose the **Linear status column**. This reverses the 2026-10-29 restructure panel's unanimous rule "no status column; status lives in Linear" ([design](2026-10-29-milestones-restructure-design.md)).

## How

1. Every issue table on `docs/projects/HTX-R1/R2/R3.md` is `| Issue | Title (Linear, verbatim) | Linear status | Result | Evidence |`.
2. The status cell is copied verbatim from the snapshot named in the page header (`docs/plans/2026-10-26-project-plan-linear.md` today). It is never typed by hand: `tools/docs_check/check_docs.py` (`linear-parity`) fails a row with no status cell or one that differs from the snapshot. This keeps the panel's real concern, no second tracker that drifts, because the column can only change with a new snapshot.
3. The Result cell is unchanged: the record's verdict word, headline number and date.
4. Refresh: the owner ticks issues in Linear, a new synced plan file replaces the snapshot, and every status cell is regenerated from it in one commit.

## Known gap

The current snapshot is from 2026-10-26, before NEAR-786/787/788 ran, so it lists them Backlog. The column is only as fresh as the last snapshot; the page header names its date.
