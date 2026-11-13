# docs_check — documentation guards (plan 2026-10-21 §4, Phase 0b)

Run from anywhere: `tools/docs_check/check_docs.sh [--warn-only] [--json] [--selftest]`
(python3 stdlib only; the .sh just cd's to the repo root). `docs/superpowers/` is excluded from every check.

| Check | What it verifies | Severity |
|---|---|---|
| links | every relative `.md` link (+`#fragment`) in README, CLAUDE.md, AirStack/README.md, docs/**, tools/*.sh resolves; fragments must slugify (GitHub rules) to a heading or `<a id>` | FAIL |
| section-refs | plain-text `§` refs and bare `ledger #N` outside docs/record and MIGRATION (they become links in the MOVE phase) | WARN |
| iron-rules | `<!-- IRON_RULES:BEGIN/END -->` block present in docs/PREFLIGHT.md and CLAUDE.md and byte-identical (diff shown); AI_ASSIST quotes the rule count | FAIL / WARN |
| safety-registry | each phrase in `safety_registry.txt` is byte-identical in its listed files and ≥ min count in the corpus; `?` rows only WARN | FAIL |
| values-registry | (a) each `values_registry.txt` row equals the value in its yaml / PX4 params source; (b) prose "key … number" claims that differ | FAIL / WARN |
| banners | docs/*.md + README.md carry a `DO`/`KNOW`/`RECORD` tag in the first 5 non-empty lines | WARN |
| real-page-hygiene | RUNBOOK/PREFLIGHT never name `cbf_sim`, `swarm_sim`, `teleop_single`, `squeeze_3drone`, bare `teleop_real.yaml` except in the iron-rules block, `⚠️`/`[SIM]` lines or RUNBOOK §A | FAIL |
| warnings-registered | every `⚠️` line contains a registry phrase or a `!`-prefixed free entry | WARN |
| budget | prose words (no fenced code, no `⚠️` lines) vs per-page budgets in `check_docs.py`; TROUBLESHOOTING rows ≤40 words; non-RECORD total | WARN |
| preflight-date | PREFLIGHT first line has `vYYYY-MM-DD`; an uncommitted PREFLIGHT edit must change it | WARN / FAIL |
| headings-stable | headings with dates, `⏳`, `✅`, `(STE` churn anchors | WARN |
| linear-parity | every NEAR-nnn on docs/projects/*.md (and bare ids on MILESTONES, LEDGER, PX4_MSGS_AUDIT) exists in docs/plans/2026-11-12-project-plan-linear.md with the identical title and Linear status (Done, In Progress, Backlog, Canceled); every `### ` milestone heading (text before ` — `) equals the snapshot's, sits on its project's page in the snapshot's order, appears once, and every snapshot milestone has a section; each issue row appears once, under its snapshot milestone; PASS records (docs/record, localisation/results) cited by LEDGER and an issue row; PASS result on a Backlog issue | FAIL / WARN |
| change-lists | an applied Linear change list (`docs/plans/*-linear-change-list.md` with an `**Applied:**` line) maps every `NEW-n` to a NEAR id (no id twice, placeholders only in NEW rows), and each new row's title equals the snapshot's; draft lists are skipped | FAIL |
| images | every relative ![…](…) / <img src> target exists | FAIL |
| page-budgets | docs/MILESTONES.md ≤ 60 lines; docs/projects/*.md ≤ 250 lines and each ### milestone ≤ 40 lines (image + caption lines excluded); every table cell ≤ 120 chars on those pages except the Linear title column | FAIL |
| figure-refs | on MILESTONES and docs/projects/*.md: captions `*Figure N.` numbered 1..n in page order, each with `<a id="fig-N"></a>` just above its image; every `Figure N` in text is the link `[Figure N](#fig-N)` | FAIL |
| purpose-lines | every `###` milestone section on docs/projects/*.md has a `**Purpose:**` line (2–3 sentences a newcomer can follow: the question it answers, why now, what breaks if skipped) | FAIL |
| single-home | each `only` row of `single_home.txt` appears in no live page but its listed files (with a near phrase: only lines that have it on them or up to 3 lines above); each `require` phrase is in its listed files. An `only` phrase missing from its first listed file also warns. Backticks and runs of spaces are ignored. Live pages: README, CLAUDE.md, docs/**, localisation/*.md, localisation/scenes/**, tools/*.md, tools/*/README.md; docs/plans/, docs/superpowers/, docs/record/ are exempt | WARN |
| change-log | (from the commit that adds docs/CODING_STANDARD.md) CHANGES.md lines well-formed, unique; every CHG id carried by exactly one commit (`Change: CHG-nnnn`); no unknown ids; every behaviour commit carries a Change: line or is named by a line; `Verified by:` LEDGER rows exist; entry fields (WARN) | FAIL / WARN / SKIP |
| hashes | MOVE-phase hook; prints SKIP until `corpus_hashes.txt` / `retired.txt` exist | SKIP |

Output: one `[PASS|FAIL|WARN|SKIP] check: summary` line per check, indented details (max 25, then "… N more"),
then a count summary. `--warn-only` downgrades every FAIL to WARN (exit 0). `--json` prints the same as JSON.
`--selftest` builds a temp corpus with one dead file link and one dead fragment and verifies both are caught.

Exit codes: 0 = no FAIL · 1 = at least one FAIL (or selftest failed).

Registries: `safety_registry.txt` rows are `phrase<TAB>min<TAB>file,file`; `values_registry.txt` rows are
`key<TAB>source<TAB>expected`. Comments start with `#`. `single_home.txt` rows are `kind<TAB>phrase<TAB>file,file[<TAB>near phrase]`, kind `only` or `require`. Grow the `!` whitelist when a new `⚠️` line is approved.
