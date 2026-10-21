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
| hashes | MOVE-phase hook; prints SKIP until `corpus_hashes.txt` / `retired.txt` exist | SKIP |

Output: one `[PASS|FAIL|WARN|SKIP] check: summary` line per check, indented details (max 25, then "… N more"),
then a count summary. `--warn-only` downgrades every FAIL to WARN (exit 0). `--json` prints the same as JSON.
`--selftest` builds a temp corpus with one dead file link and one dead fragment and verifies both are caught.

Exit codes: 0 = no FAIL · 1 = at least one FAIL (or selftest failed).

Registries: `safety_registry.txt` rows are `phrase<TAB>min<TAB>file,file`; `values_registry.txt` rows are
`key<TAB>source<TAB>expected`. Comments start with `#`. Grow the `!` whitelist when a new `⚠️` line is approved.
