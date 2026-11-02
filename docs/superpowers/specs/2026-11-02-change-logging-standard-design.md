# Change-logging coding standard — design (draft for owner approval, 2026-11-02)

**Owner's request (verbatim):** "make sure to log wtv that is changed so we can debug further second order effects if it happens. Put this as a coding standard in this project."
**Process:** quality-change skill. Panel of four (test automation, flight-test engineer, engineering manager, newcomer reader), two rounds; positions and votes in the session scratchpad (`panel4/`).

## Intent

Every change that can alter how the software or the simulated drone behaves is written down once, in one shape, with the symptom that would reveal a side effect. Changes made live during a session are logged by the tools, not from memory. A reader can find what changed, why, what it could affect and how to undo it, in one file plus one commit.

## Why now (the newcomer's measurement, 2026-11-02)

- "What changed in the sim airframe gains, and what could it affect?" took 5 places and about 60 lines. "What could it affect" was not answered anywhere: the airframe says only "Yaw untouched", the choice now suspected of the yaw ring.
- "What did patch 0007 change and what could it break?" took 3 places and about 12 lines. "What could it break" was not answered: the yaw ring 0007 uncovered is not linked to it.
- PX4 logs from the 30 Oct sessions were lost when the containers went down, so the yaw ring cannot be confirmed from PX4's own record.

## Goals

1. One entry per behaviour change, same fields everywhere, findable from one index file.
2. Live changes (PX4 parameters, commander gains from Foxglove or `ros2 param set`) captured automatically into the run folder.
3. A missing entry blocks the commit.
4. Sim-only values in the sim airframe are readable as sim-only on every line.

## Non-goals

- No change to Linear, the LEDGER (still test results only), or MIGRATION's patch table (kept; its rows now point to an entry id).
- No commit-msg hook (a second install step interns would miss).
- No rewriting of existing commits or records.

## Decisions (with the vote)

| # | Decision | Vote |
|---|---|---|
| A1 | New `docs/CODING_STANDARD.md`, TEST_STANDARD style, ≤ 60 lines. A row in CLAUDE.md's docs table and one line in AI_ASSIST.md, each a link (not an iron rule: see B10). | 4–0, placement ruled |
| A2 | An entry is required for: behaviour code, yaml/config, PX4 params (file or live), launch files, sim assets, docker images, test gates. Docs-only and test-only commits need none. | 4–0 |
| A3 | The commit body holds the full entry. | 4–0 |
| A4 | Runtime changes are captured by the tools; the PX4 ulog is copied out before shutdown. | 4–0 |
| A5 | Every entry has **Watch for**: the symptom of a side effect and where it would show (topic, test or ledger row). | 4–0 |
| P1 | `docs/record/CHANGES.md`, append-only, one line per entry. | 3–1 |
| P2 | Enforcement in the existing pre-commit hook: a behaviour path staged without a new CHANGES.md line fails. The docs check also fails a `Verified` that cites a LEDGER row that does not exist. | 3 + 1 (EM: both checks, no commit-msg hook) |
| P3 | Eight fields: **ID, What (old → new), Scope (incl. world and position source), Why, Could affect, Watch for, Verified by, Revert.** | ruling (below) |
| P4 | Backfill 0006, 0007, the 2026-10-20 rate gains and the NEAR-860 node refactor, marked "backfilled", from existing text only. | 4–0 (NEAR-860 3–1) |
| P5 | Per-line marker on every `param set-default` line of the sim airframe, checked by a unit test. | ruling (below) |
| P6 | Both capture paths: `tools/sim.sh param set NAME VAL` (logs time, name, old, new, who) and a start/end parameter snapshot diff in the run folder (catches Foxglove and anything else). `tools/sim.sh down` copies any uncopied PX4 ulogs out before stopping Isaac (see B9). | 4–0, mechanism ruled |

**Ruling P1 + P3 (the engineering manager's objection).** A CHANGES.md line cannot hold its own commit's sha: the sha does not exist until after the commit. So each entry gets an **ID** (`CHG-0001`, …). The CHANGES.md line carries ID, date, scope and a one-line what; the commit body starts with `Change: CHG-nnnn` and holds the full entry. The docs check maps every ID to a commit with `git log --grep` and fails an ID that has no commit (except the newest, staged one). This is why the field list is eight, not seven. Cost if wrong: one extra field per entry.

**Ruling P5 (2–2).** The marker is per line, but it can neither rot nor duplicate a number by hand: every `param set-default` line in the sim airframe ends in either `# = real` (same as the drone) or `# SIM-ONLY (real <value>) CHG-nnnn`. A unit test reads `starling_1_indoor_params.params` and fails if a `= real` line differs from the drone's value, a SIM-ONLY line's `real` value differs from it, or a line has no marker. That meets the flight-test engineer's readability point and test automation's "only if a test checks it". Cost if wrong: a one-time edit of about 30 lines.

## The entry (worked example: the yaw retune the yaw-step plan will make)

CHANGES.md line:
```
| CHG-nnnn | 2026-11-0x | sim-only | sim airframe yaw gains MC_YAWRATE_P/I, MC_YAW_P retuned to stop the yaw ring | <sha via git log --grep> |
```
Commit body:
```
Change: CHG-nnnn
What: MC_YAWRATE_P 0.07 -> <a>; MC_YAWRATE_I 0.5 -> <b>; MC_YAW_P 2.8 -> <c> (10090_pegasus_starling2max)
Scope: sim-only (Isaac + Pegasus, PX4 SITL, any world, sim position source). Real drone keeps 0.07 / 0.5 / 2.8. Never port (rule 9).
Why: heading rings ±8-17° at ~0.8 Hz after a yaw key (sim_site_hand1/3 replays); roll/pitch were retuned 10-20 (CHG-0003, backfilled), yaw was not.
Could affect: heading hold in every sim test, teleop turns, the crossing tests, landing detection (LNDMC_ROT_MAX), roll/pitch through motor saturation.
Watch for: heading overshoot > 3° or ring after a turn in the yaw-step test; roll/pitch rate std > 0.4 deg/s in hover; landing not detected.
Verified by: yaw-step test run <run> (ulog in its run folder shows <a>, <b>, <c> in force); the LEDGER row for that run cites CHG-nnnn.
Revert: set the three lines back to 0.07 / 0.5 / 2.8 (git revert <sha>); restart Isaac so the airframe reloads.
```

## Owner must know (found by the builder check, 2026-11-02)

The sim airframe's MPC speed and acceleration limits are **not** the real drone's, although commit `d739a73` and CLAUDE.md iron rule 9 say they are. Sim: MPC_XY_VEL_MAX 20, MPC_ACC_HOR 6, MPC_ACC_HOR_MAX 1000, MPC_Z_VEL_MAX_UP 10, MPC_Z_VEL_MAX_DN 4. Real (`starling_1_indoor_params.params`): 3, 3, 3, 2, 0.6. The real drone is unaffected (the file is sim-only). But sim runs can fly faster than the real drone ever will, and rule 9's sentence is wrong. The marker work (B1) will label these lines SIM-ONLY with the real values; correcting rule 9's text (CLAUDE.md + PREFLIGHT, a safety page) needs the owner's OK and is listed in Done-when.

## Builder-check answers

| # | Question | Answer |
|---|---|---|
| B1 | Lines with no real counterpart, geometry, MPC limits | Three markers: `# = real`, `# SIM-ONLY (real <v>) CHG-nnnn`, `# SIM-ONLY (no real value) CHG-nnnn` (e.g. PWM_MAIN_FUNC*). CMU's sim geometry (CA_ROTOR*) and the MPC limits are SIM-ONLY with their real values. |
| B2 | Parsing the real file | Tab-separated (`sysid comp NAME value type`); compare as floats (relative tolerance 1e-6), so `3e+01` = 30. A line whose value equals the real one is `= real`, whatever its comment says. |
| B3 | Which IDs the airframe lines carry | Backfill: CHG-0001 patch 0006, CHG-0002 patch 0007, **CHG-0003 the sim airframe baseline as it stands** (10-19 geometry, 10-20 rate gains ×0.5 + gyro filters + LNDMC_ROT_MAX 300, d739a73 MPC limits), CHG-0004 the NEAR-860 node refactor. Every SIM-ONLY line cites CHG-0003 until a later entry changes it. |
| B4 | Hook install on a fresh clone | `tools/sim.sh setup` sets `git config core.hooksPath tools/git-hooks` (the versioned hook runs directly, no copy to drift); `tools/sim.sh doctor` fails if it is unset. |
| B5 | What checks the commit body | The docs check walks `git log` from the commit that adds the standard: every CHANGES.md ID (except backfilled ones, which name their old commits) has exactly one commit with `Change: CHG-nnnn`, and every commit touching a behaviour path has a `Change:` line. This also catches `--no-verify` commits after the fact. |
| B6 | ID races | The hook fails a staged CHANGES.md that reuses an ID; the docs check fails duplicates. Parallel executors get their IDs from the orchestrator. |
| B7 | Live params vs the yaw-step plan | One formatter in `tools/lib/` writes `changes.log` lines (`time · name · old → new · who`). `sim.sh param set` (host, via `docker exec`) and the yaw-step sweep inside `fly.sh` both use it. The PX4 ulog's changed-parameters list is the ground truth of what PX4 ran; on a conflict it wins. The snapshot diff is the safety net. The record prints all three under "Changes in this run". |
| B8 | Order with the yaw-step plan | The standard lands before Task 5. Yaw-step commits made before it (Tasks 1–4) get entries at landing. Task 5's commit then carries the next ID. |
| B9 | `down` guard mechanism | `sim.sh down` copies any PX4 ulog not yet copied into `~/flight_logs/sim/uncollected_<date>/` before stopping Isaac, and stops only when the copy succeeds (`--force` skips it and prints that the logs are lost). No refusal loop, and no run folder needed. |
| B10 | Iron-rule placement and budgets | Not an iron rule: the iron-rule block is mirrored byte-for-byte on the pilot's PREFLIGHT card, which is about flying safely, not committing. A row in CLAUDE.md's docs table and one line in AI_ASSIST.md instead, within their word budgets. |
| B11 | Newcomer clarity | "Verified by" = what verified it at commit time (unit test, harness, offline check, or `pending: <test>`); the later LEDGER row cites the CHG ID, never the reverse. "Could affect" = named neighbours: other tests, other drones, the real-drone path, other parameters. MIGRATION's patch table gains a CHG column, so a patch number and its CHG ID sit side by side. |

## Left to the builder (the plan)

- The exact path map in the pre-commit hook (starting point: `AirStack/**` code, `**/*.yaml`, `**/launch/**`, `AirStack/simulation/**/airframes/**`, `patches/**`, `tools/sim.sh`, `tools/lib/**`, `tools/live/**`, `tools/teleop/**`, `tools/sim_tests/*/gates.py`, `localisation/nodes/**`, `localisation/scripts/**`, docker files).
- The parameter-snapshot mechanism (PX4 `param show` diff vs MAVROS param pull; commander `ros2 param dump`), and how the record prints "Changes in this run".
- Where `sim.sh param set` sits relative to the yaw-step test's own live sweep (the sweep must call it, so both share one log).

## Done when

- `docs/CODING_STANDARD.md` exists; CLAUDE.md's docs table and AI_ASSIST.md point to it.
- With the owner's OK: iron rule 9's sentence on MPC limits corrected in CLAUDE.md and PREFLIGHT.md.
- `docs/record/CHANGES.md` holds the four backfilled entries (CHG-0001…0004) and one entry for each behaviour commit since 2026-11-02.
- The pre-commit hook blocks a staged behaviour path without a new CHANGES.md line (unit test). The docs check fails an unknown ID or a dead LEDGER citation (unit tests). The airframe-marker test passes.
- `tools/sim.sh param set`, the snapshot diff and the `down` guard exist with tests; the next sim record shows "Changes in this run".
- Newcomer test: both 2026-11-02 questions answered from CHANGES.md plus one commit, in ≤ 25 lines each, including "could affect" and "watch for".
