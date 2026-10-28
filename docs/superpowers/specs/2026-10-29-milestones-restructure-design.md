# MILESTONES.md restructure — design (panel decision, 2026-10-29)

**Why.** `docs/MILESTONES.md` is 627 lines. Three sections (§4 procedures 233 lines, §3c ledger 110, §3b audit 86) are 69 % of it; ledger rows #17–#19 are 2,000–2,300 characters each. A newcomer needed ~220 lines across four places to learn whether the hover test passed, and ~290 lines across three places to find the next real-drone step. The file uses its own M0–M7 codes; Linear's names (HTX-R1/R2/R3, S1–S10, R1, M2–M7, L0–L5, NEAR-xxx) appear nowhere. Lines 14 and 396 were already stale against ledger #18/#19.

**Decided by** a four-hat panel (technical writer, flight-test engineer, engineering manager, newcomer reader), two rounds; positions and votes in the session scratchpad `panel/`. Unanimous except P1 (3–1).

## Goals
- An engineer who has never opened the repo answers "where is each project, what passed, what is next" from one screen, then one click.
- Names and codes are Linear's, verbatim (`docs/plans/2026-10-26-project-plan-linear.md` is the naming authority).
- Under each milestone: its issues, then the results of those issues, with the evidence links inline. No separate "evidence" section.
- Results are shown as tables and figures, not prose.
- Sim and real are impossible to confuse: stated in every milestone heading and in every table that can mix them.

## Non-goals / anti-goals
- No new branch; everything stays on `main`. No change to Linear from the repo. No edits inside `AirStack/` (CMU's tree).
- The repo does not become a second status tracker: status, order and target dates live in Linear. The repo holds codes, exact titles, "Done when", and evidence.
- Nothing may read as validated on the real drone that was not (iron rule 9). No curve is drawn from the September 2026 logs (previous software): a curve reads as validated whatever its caption says.
- Failure: a restructure that loses a negative result (#5, #6, #9, #17's driver FAIL) or a carried-over hazard.

## Constraints
- HTX-facing wording: never "under mocap" in repo prose (write "with motion-capture positioning"); no "not committed"; no status pills; no "autopilot"; American "localization" in new prose. Linear issue titles are copied verbatim even where they break this (NEAR-816/822/855 say "mocap"); the owner is asked to reword Linear's HTX-R2 project text and NEAR-855.
- `tools/docs_check/check_docs.sh` must end with 0 FAIL. Every link that today points at `MILESTONES.md §…` (CLAUDE.md iron rule 5, PREFLIGHT, RUNBOOK, CONFIG, records, `tools/hover_step_report.py` thresholds text) is retargeted.
- Append-only ledger: rows are never rewritten, only shortened to one line with the detail in a record file.

## The files (decisions)

### `docs/MILESTONES.md` — top page, ≤ 60 lines, one screen
1. Three lines: what the page is; "every result is simulation unless the row says real drone"; nothing on this software has flown; September flights = previous software, archived (link to LEDGER table 2); Linear link + snapshot date.
2. `## Before the next real flight` — 3–5 lines, one per hazard, each naming the NEAR issue that re-earns it: software blind to arming / ACK unaudited (NEAR-821), `land_speed_mps` 0.3 leaves the drone armed (NEAR-826), drone ID = controller target (NEAR-819), one watchdog only (NEAR-820), reboot never restart after setup (NEAR-818), and two hazards with no Linear issue of their own, re-observed at the first flight (NEAR-825): control-authority leak into POSCTL/ALTCTL, commander stuck non-IDLE after a takeover. Ids are copied from the plan file, never typed from memory.
3. `## Where each project is` — table: Project | Sim/Real | Milestone in progress | Last result (number + date, linked to the record) | Next issue (NEAR id) | Blocked by. Three rows.
4. `## Pages` — `projects/HTX-R1.md`, `projects/HTX-R2.md`, `projects/HTX-R3.md`, `record/LEDGER.md`, `PX4_MSGS_AUDIT.md`.

### `docs/projects/HTX-R1.md`, `HTX-R2.md`, `HTX-R3.md` — ≤ 250 lines each
Header: Linear project name verbatim, one-line question (from the plan's "How the work is split" table), `Linear snapshot: 2026-10-26` line. HTX-R2.md repeats the "Before the next real flight" box at its top (the pilot's page), then the full carried-over table (today §3c "Carried-over issues", every row keyed to its NEAR id, column "re-test at" → "re-earned by", rows cleared only by a ledger row that re-observes them).

One `###` per Linear milestone, in Linear order, ≤ 40 lines excluding figures:
```
### S5 Finish basic sim flight checks — SIM ONLY (Isaac)
Linear: Backlog · 4 % (snapshot 2026-10-26) · last ledger row #19 (2026-10-29)
Done when (Linear, verbatim): …

| Issue | Title (Linear, verbatim) | Result | Evidence |
| NEAR-786 | Re-run hover and 1 m step test on the updated sim drone | PASS ×2, 2026-10-28/29 | #18, #19 → run3 record |
| NEAR-787 | Re-run three-drone crossing with collision avoidance and record it | — | baseline #4: 1.02 m, old asset, no bag |
| … one row per Linear issue, all of them, in Linear order … |

NEAR-786 — results (sim only; gates 0.15 m / 3.0 s PX4 vehicle time / 0 re-entries / thrust 0.12–0.20; thresholds set 2026-10-19, bracket the Iris reading, not a flight requirement)
| | gate | #3 (19 Oct, old asset, 0.6 m/s, wall time) | #17 (28 Oct, n=1) | #18 (28 Oct, n=3) | #19 (29 Oct, n=3) |
| hover thrust | 0.12–0.20 (real 0.165) | 0.155 | 0.153 | 0.153 | 0.153 |
| PX4 s per wall s | — | — | ≈1.33 | 1.324 | 1.333 |
| x overshoot, m | < 0.15 | 0.002 | 0.054 | 0.085 | 0.095 |
| x settle, s | < 3.0 | 2.75 | 2.49 | 2.47 | 2.47 |
| z overshoot, m | < 0.15 | 0.001 | 0.001 | 0.033 | 0.020 |
| z settle, s | < 3.0 | 0.75 | 2.16 | 2.50 | 2.42 |
| landed, DISARMED ×3 | yes | — | yes | yes | yes |
| verdict | | superseded | driver FAIL ×3, re-analysed PASS; drone_1 ulog lost | PASS | PASS |
![x and z step responses, #17–#19 overlaid](../record/figures/s5_hover_step_overlay.png)
*`tools/hover_step_plot.py --overlay sim_hover_step_run1 sim_hover_step_run2 sim_hover_step_run3`; ledger #17–#19.*
Open: NEAR-787 at 2.0 / 4.0 m/s with a bag. Re-run: `LEDGER=20 tools/sim_hover_step_run.sh all <new_run>`.
```
Rules: the Result cell holds only a record's verdict word, the headline number and the date, and is filled only when a record file exists (otherwise "—"); it is evidence-derived, never copied from Linear, so it cannot drift. No status column. Negative and superseded results stay in the results table. Every table cell ≤ 120 characters except the verbatim Linear title column. One figure and one results table per issue that has data; issues without data get one line. Every figure caption names the generating command and the ledger rows. One "Open" line and one re-run command per milestone.

HTX-R2 milestones carry a second small table under M2/M3/M4 only where the archive has rows: "Observed on the previous software (archived branch `archive/airstack-starling-max2`, 2026-07-20 → 09-03), re-earned at NEAR-xxx" — words allowed: observed, archived; words banned: PASS, validated, done, ticks, dates in a "validated by us" column.

### `docs/record/LEDGER.md` — append-only evidence (P1: 3–1 for `docs/record/`)
Table 1, rows #1–#19 migrated one line each: `# | date | SIM/REAL | one-sentence result | evidence link (record / log) | NEAR id(s)`. The long notes of #6–#11 move to `docs/record/sim_notes_2026-10-20.md`; the §6 "Fix 1" detail becomes a LEDGER note. Table 2, rows A1–A21 from the archived branch's ledger: `A# | observed | date | evidence (ulog path under ~/flight_logs/2026-09-01/) | re-earn at NEAR-xxx`; the archive's own M-labels (old "M6" = first flight) are stripped so they cannot collide with Linear's M2–M7. 20 of 21 rows map to HTX-R2 (R1: A2,A3,A4,A8,A13,A16 · M2: A5,A6,A7,A9,A10,A11,A12,A14,A15 · M3: A17,A21 · M4: A18,A19,A20); A1 is July sim, HTX-R1 ancestry.
The run tooling's ledger-row draft (`tools/hover_step_report.py ledger_row`) switches to this one-line format and carries the NEAR id.

### `docs/PX4_MSGS_AUDIT.md` (P3: 3–1)
§3d moved whole, with its re-run method; linked from the NEAR-821 row in HTX-R2.md, from CLAUDE.md iron rule 5 and from PREFLIGHT.md.

### What moves where (today's sections)
| Today | Decision |
|---|---|
| §1 objective | 3 lines on the top page |
| §2 why milestones, §5 troubleshooting table, §3c "Next up" | delete (Linear owns order; TROUBLESHOOTING.md owns symptoms) |
| §3 status table | the "Where each project is" table |
| §3b code audit (2026-10-07) | appendix of MIGRATION.md |
| §3c ledger | `record/LEDGER.md` table 1 |
| §3c carried-over issues | HTX-R2.md top, keyed to NEAR ids; 3–5 line gates box on the top page |
| §3d PX4 audit | `PX4_MSGS_AUDIT.md` |
| §4 M0–M7 procedures | deleted from MILESTONES only after each step is found in RUNBOOK / DRONE_SETUP / PREFLIGHT / SCENARIOS, or moved: M3 landing sub-test → NEAR-826 "Done when" sub-line; M2 gates (one watchdog, `target_system`) → NEAR-818/819; M1 thresholds → `tools/README.md` (and the thresholds sentence in `tools/hover_step_report.py`). One decisive command per milestone stays on the project page |
| §6 backlog | Fix 1 → LEDGER note; Fix 2/3 are carried-over rows already; sim debt → 6-row table at the end of HTX-R1.md; upstream candidates → MIGRATION.md |

### Figures now
- `docs/record/figures/s5_hover_step_overlay.png`: x and z step responses of #17/#18/#19 overlaid (goal line, ±0.1 m band, 3 s gate, vehicle time), new `--overlay` mode in `tools/hover_step_plot.py` reading the three `drone_1_odom.csv` / `drone_1_cmd.csv`. Follow the dataviz skill (one hue per run, fixed order, legend + direct labels, dark-safe).
- S3/S4 (HTX-R1): reuse `pictures/vo_flat_xy_cam_run3.png` and `pictures/vo_site_xy_site_run1.png` side by side, with the 0.08 m RMSE / 162 m table from `localisation/results/sim_site_run1_record.md`.
- Nothing for #4, #10, #13 until re-run with a bag (table rows only). No September curve.

### Checks (`tools/docs_check/`, new pass `linear-parity` + budgets)
- Every `NEAR-nnn` on a project page exists in the plan file with the identical title; a title mismatch is FAIL.
- Every record whose verdict is PASS is cited by a LEDGER row and by an issue row; otherwise WARN naming the record.
- Budgets: top page ≤ 60 lines, project page ≤ 250, milestone ≤ 40 (figures excluded), cell ≤ 120 chars except the title column; FAIL when exceeded.
- Every image referenced exists (FAIL).

### Keeping it in step with Linear
One direction, Linear → repo: codes, titles and "Done when" copied verbatim with a `Linear snapshot: <date>` line; status is read in Linear, not here. Per test: one LEDGER row + one issue-row Result cell here (both from the record), one comment in Linear with the ledger number and record link, then the owner ticks the issue. `linear-parity` WARNs when a PASS record exists for an issue still Backlog in the snapshot (today: NEAR-786).

## Builder-check answers (2026-10-29, fresh reader of this document)
1. Hazard → issue ids corrected above from the plan file (NEAR-818 reboot, 819 drone ID, 820 watchdog, 821 PX4 messages, 826 landing). The RC-takeover leak and the stuck-non-IDLE check have no Linear issue; they are re-observed at NEAR-825 and the owner is asked whether to add two issues under M3.
2. "Record" for a Result cell = any of: a `docs/record/*_record.md` (quote its verdict word), a `localisation/results/*_record.md` (quote its headline number), or a LEDGER row when no record file exists (quote the row's one-sentence result, cite `#n`). The cell always carries the date and the source (`#n` or the record link). The parity check looks in both record folders.
3. Archive table 2: desk and network rows (A1–A16) carry no evidence file, just the archived ledger reference; flight rows A17–A21 cite the folder `~/flight_logs/2026-09-01/` (four ulogs, no per-row mapping known). Never invent a file-per-row mapping.
4. Overlay: per-run time scale from each run's `px4_arm_times.txt`; run1 has none (drone_1 ulog lost), so `--overlay` accepts `--time-scale sim_hover_step_run1=1.336` and the legend marks it "(est.)". All three traces plotted in vehicle time.
5. Status lines and the "milestone in progress" column are snapshot-dated copies, allowed; `linear-parity` checks them only against the snapshot named in the page header, never against live Linear.
6. `hover_step_report.py` gains `--issue NEAR-nnn` (wrapper env `ISSUE`), default none → the ledger-row draft carries `?` like `--ledger`. The overlay is NOT regenerated by the report phase; `tools/make_figures.sh` holds the explicit run list and is run by hand when a figure should change, so a run4 never alters the S5 figure silently.

## Left to the builder
Exact wording of status lines; column order inside the budget; figure styling within the dataviz rules; the order of rows in the CLAUDE.md doc table (add `projects/`, `record/LEDGER.md`, `PX4_MSGS_AUDIT.md`); whether `docs/record/figures/` or per-run folders hold the overlay (decision: `figures/`, fixed filename, regenerated by the report phase); how `check_docs.sh` reports budgets (same PASS/WARN/FAIL lines as today).

## Done when
`docs/MILESTONES.md` ≤ 60 lines; three project pages exist with every Linear milestone and every Linear issue present by id and verbatim title; LEDGER tables 1 and 2 complete; §3d page linked from iron rule 5; the S5 overlay figure renders; `check_docs.sh` 0 FAIL including the new pass; the newcomer's three questions (hover passed + numbers; next real-drone step + preconditions; sim vs real) each answered within one screen of the top page plus one click.
