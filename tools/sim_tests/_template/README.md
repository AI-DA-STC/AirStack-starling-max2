# Test template (sim only)

1. Copy this folder to `tools/sim_tests/<name>/` (no leading underscore).
2. Fill `test.env`: every `CHANGE_ME` (TITLE, ISSUE, PURPOSE, SCOPE) and the milestone.
3. Replace the flow in `fly.sh`, the series in `metrics.py`, the gates in `gates.py`, the plots in `plots.json`.
4. `python3 tools/live/make_layout.py tools/sim_tests/<name>` writes `layout.json`; commit it.
5. `tools/sim.sh check` must print no failure for the new folder.
6. Run it once in window mode: `tools/sim.sh test <name> --ledger N --issue NEAR-nnn`.
7. Record the result per DOCS_STANDARD section 7 (record, ledger row, project page).
Contract: [docs/TEST_STANDARD.md](../../../docs/TEST_STANDARD.md). The crossing test next door is the worked example.
