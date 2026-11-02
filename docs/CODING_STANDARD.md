KNOW · SIM + REAL — how a change that can alter behaviour is logged. Read before committing code, config, parameters, launch files, sim assets, docker files or test gates. Decided by a four-hat panel on 2026-11-02 ([design](superpowers/specs/2026-11-02-change-logging-standard-design.md)).

# Coding standard: log every behaviour change
Every change that can alter how the software or the simulated drone behaves is written down once, in one shape, with the symptom that would reveal a side effect. Changes made live are logged by the tools, not from memory. One line in [record/CHANGES.md](record/CHANGES.md) and one commit answer what changed, why, what it could affect and how to undo it.

## 1. What needs an entry
| Needs an entry | Needs none |
|---|---|
| `AirStack/`, `patches/`, `mocap/`, `tools/sim.sh`, `tools/lib/`, `tools/live/`, `tools/teleop/`, `localisation/` (`nodes`, `scripts`, `docker`, `scenes`) | docs (`*.md`, `docs/`) |
| `tools/sim_tab.sh`, `sim_terminals.sh`, `sim_hover_step_run.sh`, `sim_hover_step_test.sh`, `analyze_step.py`, `hover_step_` `analysis`, `report`, `bag`, `timescale` (not `plot`) | unit tests (`tools/tests/`, CMU's `test/`) |
| yaml and other config, launch files, `Dockerfile`, `docker-compose*`, `fastdds.xml` | records and figures written by a run |
| PX4 parameters (the sim airframe, `starling_1_indoor_params.params`, or set live), sim assets and worlds, test gates (`gates.py`, `metrics.py`, `fly.sh`, `test.env`) | the `_template` test |

The exact list lives in `tools/docs_check/changes.py`. `python3 tools/docs_check/changes.py is-behaviour <path>` answers for one file.

## 2. The entry
1. Take the next ID: the highest `CHG-nnnn` in CHANGES.md plus one. Parallel work gets its IDs from whoever hands it out.
2. Append one line to CHANGES.md: `| CHG-nnnn | <date> | <scope> | <what, one line> | this |`. Scope is `sim-only`, `real-drone`, `sim+real` or `tooling`. Never edit or delete a line.
3. Start the commit body with the full entry: eight fields, one line each, in this order.
| Field | Holds |
|---|---|
| `Change:` | the ID |
| `What:` | old → new, with the file or parameter names |
| `Scope:` | sim-only, real drone or both; the world and the position source |
| `Why:` | the symptom or the request, with the ledger row or record if there is one |
| `Could affect:` | named neighbours: other tests, other drones, the real-drone path, other parameters |
| `Watch for:` | the symptom of a side effect and where it would show (topic, test, ledger row) |
| `Verified by:` | what checked it at commit time: unit test, harness, offline check, or `pending: <test>` |
| `Revert:` | the exact undo: `git revert`, the old values, any restart needed |

A later LEDGER row cites the CHG ID. The entry never waits for the row. Read any entry with `python3 tools/docs_check/changes.py show CHG-nnnn`.

## 3. Live changes
| Rule | Status |
|---|---|
| Set a sim PX4 parameter with `tools/sim.sh param set NAME VALUE [--drone N]`. It reads the old value, sets, reads back and logs one line to `~/flight_logs/sim/changes.log` (and to the run's `changes.log` during a test): `<time> · drone_N/NAME · <old> → <new> · <who> · readback <v>`, plus ` · MISMATCH` when the read-back differs, ` · UNVERIFIED <why>` when nothing confirmed it, ` · REFUSED <why>` when the target is not the sim's PX4. The yaw-step sweep sets through the same helper. | live: `param set` CHG-0016, guard CHG-0018; yaw sweep CHG-0020 |
| Every `sim.sh test` record has a "Changes in this run" block: the tools' log, PX4's own list from the ulog, a start/end snapshot diff (PX4 via MAVROS, re-read from PX4 after landing; the commander's parameters). The ulog wins a conflict. The snapshot catches Foxglove, QGC and `ros2 param set`. A missing source reads "unknown (why)", a change no tool logged "UNLOGGED CHANGE"; either adds one record caveat (the verdict is unchanged). | live: CHG-0017, CHG-0019 |
| `tools/sim.sh down` saves any PX4 ulog not yet copied to `~/flight_logs/sim/uncollected_<date>/`. `down --force` skips that and those logs are lost. | live: CHG-0014 |
| A value that wins a live sweep goes into the file in its own commit, with its own entry. | rule |
## 4. The sim airframe
Every `param set-default` line of `10090_pegasus_starling2max` ends in `# = real`, `# SIM-ONLY (real <value>) CHG-nnnn` or `# SIM-ONLY (no real value) CHG-nnnn`. `tools/tests/test_airframe_markers.py` checks each line against `starling_1_indoor_params.params` (live: CHG-0013).
## 5. What enforces it
| Check | Fails when |
|---|---|
| pre-commit hook (`tools/git-hooks/pre-commit`, active after `tools/sim.sh setup`) | a behaviour path is staged without a new CHANGES.md line |
| | a line is edited, removed or malformed |
| | an ID repeats |
| docs check `change-log` (`tools/docs_check/check_docs.sh`) | an ID has no commit, or two |
| | a commit names an unknown ID |
| | a commit cell names something that is not a commit |
| | a behaviour commit since this page has no `Change:` line (a `--no-verify` commit) |
| | `Verified by:` cites a LEDGER row that does not exist |
| | this page is renamed or deleted |
| `tools/sim.sh doctor` | the hook is not active in this clone |

## When the hook blocks you
The message `behaviour path(s) staged without a new … line` means CHANGES.md has no new line in this commit. Append the line, stage it and start the commit body with `Change: CHG-nnnn`. Make a new commit, never `--amend` or `--no-verify`.

## Correcting an entry
History is never rewritten. A wrong entry gets a new line whose What starts `correction of CHG-nnnn:`. The commit body carries `Corrects CHG-nnnn — What: …` for each corrected field. `changes.py show CHG-nnnn` prints every later correction. A commit that slipped through is fixed by a late entry: a new line whose last cell names the slipped commit, plus a commit whose body carries the entry.
