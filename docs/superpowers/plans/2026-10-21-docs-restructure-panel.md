# Docs restructuring — panel review and chair's consolidated plan (2026-10-21)

> Status: PROPOSED, awaiting owner approval. Nothing executed. Produced by three independent
> reviews (principal robotics engineer / senior documentation engineer / senior flight-ops
> safety engineer) and a chair that reconciled them. The owner's original plan is in §0.

## 0 · Original plan (owner + assistant, superseded by §1–§6)
Three tiers DO / KNOW / RECORD; DO cap 1,500 words, KNOW 3,000, RECORD uncapped; README → 400-word
front door; new START_HERE.md; RUNBOOK keeps only procedures and every "why" moves to KNOW;
CONFIG keeps flown values; TROUBLESHOOTING rows = symptom · first check · fix · link;
GLOSSARY the only definition; three parallel agents by tier, one commit per tier, cold read.

## 1 · Decisions
| # | Issue | DECISION | Why | Dissent |
|---|---|---|---|---|
| 1 | Ledger fold vs split | Split → `docs/record/LEDGER.md`, row numbers frozen, every "ledger #N" becomes a link in the same commit | A Markdown fold is not an edit boundary; MILESTONES has four edit modes | R1 wanted fold |
| 2 | One RUNBOOK vs SIM/REAL pages | **START_HERE.md = the SIM page** (absorbs RUNBOOK §A verbatim). **RUNBOOK.md = REAL DRONE only** (name kept, §A → stub, §B/§C/§D keep letters). Line-1 WORLD banner on every DO page; "step 0 — which world am I in" on both | World separation is the safety gain; keeping filenames protects 414 inbound links, CLAUDE.md, the printed card, the mirror | R3 wanted new filenames |
| 3 | Word caps | Per-page budgets (§2), prose only (fenced code excluded); `⚠️` lines exempt but must match a registry | All three rejected flat caps; exemption needs a registry to stay honest | — |
| 4 | Iron rules | Canonical text = PREFLIGHT.md between `<!-- IRON_RULES:BEGIN/END -->`; CLAUDE.md carries a byte-identical copy between the same markers; AI_ASSIST keeps a rule-# column; `check_docs.sh` diffs the blocks. Phase 0 merges the two already-diverged texts | The card people hold is the source; the assistant copy is derived | R3 wanted a separate file |
| 5 | "Why stays inline" | Keep ≤1 sentence (≤25 words) as a `⚠️` line wherever omitting it would let a reader "improve" the step unsafely; §3 whitelist mandatory; explanations move to KNOW | Unanimous veto of the blanket rule | — |
| 6 | Scope now vs after M3 | §B/§C/§D move into the REAL shell **verbatim** now; additions only (banner, step 0, gates line, §C8 "never set live", TELEOP §5 blocker). Trim after the M3 flight | Unvalidated content + M3 + camera upgrade imminent = rewriting twice | — |
| 7 | Execution | freeze → scaffold → MOVE sequentially by source (one agent, one commit per source, verbatim) → TRIM in parallel by destination (exclusive ownership) → cold read → mirror pull, owner pushes | Conflicts come from sources, not tiers | — |
| 8 | New files | SETUP.md (DO), ARCHITECTURE.md (KNOW), docs/record/{LEDGER,AUDITS,MILESTONE_RUNS,INCIDENTS,INBOX}.md; docs/reference/* on demand; no IRON_RULES.md | README's setup/primer/network (2,581 w) need homes or "nothing deleted" fails | R3 |
| 9 | GLOSSARY-only vs gloss | ≤1-clause gloss on first use per DO page; full definition only in GLOSSARY | Resolves standalone-vs-single-definition contradiction | — |
| 10 | Tier label | Line 1: `TIER · WORLD`; mixed pages tag sections `[DO]/[KNOW]` and `[SIM]/[REAL]`; headings carry no dates/status | Headings must be stable for fragment links | — |
| 11 | CLAUDE.md WiFi write-up | Symptoms → TROUBLESHOOTING; narrative → record/INCIDENTS.md; systemd fixes → DRONE_SETUP; CLAUDE.md keeps one line + link | Procedure in DO, history in RECORD | — |
| 12 | cbf_sim.yaml name | Docs-only now: checker forbids `cbf_sim`/`sim_*`/non-ours `teleop_real.yaml` on REAL pages outside the rules block or `⚠️` lines. Rename = follow-up | Engineering stays out of the docs plan | — |
| 13 | Shipped-vs-ours traps | Current traps = "Never fly these" table in CONFIG (canonical); MIGRATION records how they changed | They are current safety, not history | — |
| 14 | DRONE_SETUP tier | DO | It is a procedure | — |
| 15 | MILESTONES top | ≤1,200 prose; first 150 words = "Gates before the next real flight" box, mirrored as one registry line in the RUNBOOK header | All three compatible | — |

## 2 · Final file tree (prose budget excl. code; `⚠️` lines exempt)
| File | Tier · World | Purpose | Budget | In ← / Out → |
|---|---|---|---|---|
| README.md | DO | front door: what/who/status/where next | 450 | → showcase, appendix, M1 glance → MIGRATION; setup → SETUP; primer+network → ARCHITECTURE; "Running" → START_HERE |
| CLAUDE.md | KNOW | assistant brief: iron rules (checked copy), doc map, two-clone rule | 1,000 + rules | → WiFi narrative (D11) |
| docs/START_HERE.md (new) | DO · SIM | four-tab sim session, takeoff→land, expected log lines, week-one faults, guest rules, "Real drone = PREFLIGHT + RUNBOOK with the owner present until M3 is dated" | 1,500 | ← RUNBOOK §A0–A4 + Alternatives, README "Running" |
| docs/SETUP.md (new) | DO | new machine, both clones, mirror rule | 1,200 | ← README setup + security note |
| docs/RUNBOOK.md | DO · REAL | §A stub; §B/§C/§D verbatim; step 0; gates line; §C8 "never set live" | 2,500 | ← CONFIG live-param warnings as §C8; → §A; (post-M3) where-things-run, arg/QoS explanations, rebuild history |
| docs/PREFLIGHT.md | DO · REAL | laminated card; canonical iron rules; version+date line 1 | 1,100 | ← §3 PREFLIGHT items |
| docs/DRONE_SETUP.md | DO · REAL | provisioning | 1,800 | ← WiFi systemd fixes if absent |
| docs/TROUBLESHOOTING.md | DO | top-15 block, then index by layer; rows symptom · first check · fix · link | no cap; ≤40 w/row; top-15 ≤600 | ← MILESTONES §5, TELEOP §10, CLAUDE.md WiFi symptoms |
| docs/ARCHITECTURE.md (new) | KNOW | primer + lab network + picture corrections | 1,500 | ← README primer, network; CLAUDE.md picture notes |
| docs/CONFIG.md | KNOW | flown values, sim-airframe table, "Never fly these" | 2,500 | → history → MIGRATION; long tables → reference/ |
| docs/SCENARIOS.md | KNOW (+[DO] run-it) | | 2,500 | → history → MIGRATION |
| docs/TELEOP.md | KNOW (+[DO] §4 SIM, §5 REAL w/ blocker) | | 2,000 | → §10 rows → TROUBLESHOOTING; §11 → reference/ if >400 w |
| docs/BASESTATION.md | KNOW | | 2,500 | ← RUNBOOK where-things-run (post-M3) |
| docs/MOCAP.md | KNOW | | 2,000 | §6.1 trigger copied as `⚠️` to PREFLIGHT |
| docs/GLOSSARY.md | KNOW | full definitions only | 3,000 | — |
| docs/AI_ASSIST.md | KNOW | | 800 | rule-# column |
| docs/MILESTONES.md | RECORD (rewritten state) | gates box, status, Next-up with "gated by", sim debt, backlog | 1,200 | → §3b+§3d → record/AUDITS; §3c → record/LEDGER; §4 → record/MILESTONE_RUNS; §5 → TROUBLESHOOTING |
| docs/MIGRATION.md | RECORD | branch history, trap change history | uncapped | ← README appendix/showcase, CONFIG/SCENARIOS history |
| docs/record/{LEDGER,AUDITS,MILESTONE_RUNS,INCIDENTS,INBOX}.md | RECORD | append-only; INBOX = freeze holding file | uncapped | |
| docs/reference/*.md | RECORD | long tables | uncapped | on demand |
| tools/docs_check/{check_docs.sh, safety_registry.txt, values_registry.txt, corpus_hashes.txt, retired.txt} | — | guards | — | new |
Target non-RECORD total: 30–32k words (from 62k).

## 3 · Safety "stays inline" whitelist (each a registered `⚠️` line)
**RUNBOOK §B (REAL):** B0 no Isaac/MAVROS/svg_teleop nodes — check `ros2 node list` (+PREFLIGHT checkbox) · B4 rigid body must exist in Motive before launch · B4 a 30 cm origin shift moves everything 30 cm · B5 MAV_SYS_ID 1-vs-2 unresolved (+gates box) · B6 takeover_twins warning · B7 do NOT call takeoff during this check · B8 `start` is REQUIRED · B8 DENIED = PX4 refused, no entry = target_system mismatch · B8 props-off kill ground test (+PREFLIGHT) · reboot, never `systemctl restart voxl-px4` (also DRONE_SETUP) · never approach until QGC DISARMED.
**RUNBOOK §C:** C2 each publish REPLACES the goal, publisher exiting does NOT cancel · C2 goals act only under `goal`, keep inside the fence · C4 hold_all latches on an RC-flown drone too (+PREFLIGHT) · C7 edit the SOURCE yaml + readlink verify, teleop fence inside geofence · C8 (new): fence_brake_accel_mps2 0 silently reverts; hold_lead_m keep 0.2; fence_brake ≥ goal_accel.
**PREFLIGHT:** this stack bypasses drone_safety_monitor — PX4 failsafes + RC kill are the entire net · cbf_max_speed_mps is the ONLY speed limit (next to the ≤1.0 check) · after ANY recalibration or ground-plane change re-run the frame hand-check · push-apart engaged → land and investigate · never exempt two drones at once · arena ≠ geofence, nothing checks one against the other · DDS domain 1 — sim uses the same.
**START_HERE (SIM):** Isaac Stop▶Play ≠ reset · sim-only — never port (values list travels WITH the phrase) · Real drone = PREFLIGHT + RUNBOOK with the owner present.
**TELEOP:** centred sticks = hold, not idle, only `land` brings it down · no per-drone land · takeoff is open-loop · ≈2 m coast from 4 m/s · `./svg_teleop.sh real` is NOT our recipe (binds NatNet ports, starves ./mocap.sh) · §5 blocker: teleop_real.yaml = CMU fences, land_speed 0.3 — do not fly until teleop_real_ours.yaml exists.
**CONFIG:** "Never fly these" header · sim-only phrase on the sim-airframe table. **MILESTONES/RUNBOOK header:** the gates line.

## 4 · Phased execution (≈16–18 agent runs)
**F — freeze (owner, 5 min):** new findings only into `docs/record/INBOX.md`; mirror clean; pin SHA.
**0 — scaffold (2 runs, 2 commits; owner approves 0a):** 0a merged iron-rules text in PREFLIGHT markers + identical block in CLAUDE.md + PREFLIGHT line-1 version/date. 0b `tools/docs_check/` — check_docs.sh (dead links/fragments; `§` grep zero outside record/MIGRATION; "ledger #N" must be links; iron-rules blocks identical; AI_ASSIST rule count 9; safety registry byte-identical at each location; values registry vs `_ours` yamls + LNDMC_ROT_MAX 30; line-1 banners; REAL pages free of sim config names; every `⚠️` registered; prose budget; screen-1 rule; hash coverage — MOVE: each hash exactly once or whitelisted, code lines never retired; TRIM: ≤1 or in retired.txt with reason; stubs = heading + "Moved → link"; PREFLIGHT change ⇒ date change; stable headings) + registries + corpus_hashes.txt at the pinned SHA.
**1 — MOVE (≈6 runs / 7 commits, sequential by source, verbatim, each passing all checks):** (1) MILESTONES → record/*, TROUBLESHOOTING, gates box; (2) README → SETUP, ARCHITECTURE, START_HERE, MIGRATION; (3) RUNBOOK → §A to START_HERE, banners, step 0, §C8, stub; (4) CLAUDE.md → INCIDENTS/TROUBLESHOOTING/DRONE_SETUP, doc map; (5) CONFIG → "Never fly these", history → MIGRATION, tables → reference/; (6) TELEOP §10 → TROUBLESHOOTING, §5 blocker; (7) all remaining `§` → fragment links incl. `tools/sim_tab.sh` ×4.
Move-list row: `id · source file + heading slug + first/last line quoted · destination file + heading + position · action {move | move+keep-why | split-row | to-record | retire(reason) | stub} · stub text · inbound refs to rewrite · tier · world · safety-flag`. Granularity: `###` sections; paragraphs in mixed sections; rows for TROUBLESHOOTING.
**2 — TRIM (≈6 runs, parallel, exclusive ownership, one commit each):** A START_HERE+SETUP · B CONFIG+reference · C SCENARIOS+TELEOP · D BASESTATION+MOCAP+ARCHITECTURE · E GLOSSARY+AI_ASSIST+CLAUDE.md · F MILESTONES+MIGRATION+record. RUNBOOK §B/§C/§D and PREFLIGHT NOT trimmed (post-M3, owner). Cuts → retired.txt or record/; command lines never change.
**3 — cold read (2 runs):** pass = (a) sim takeoff→land reconstructed from START_HERE alone diffs clean; (b) 10 "where is X" questions ≤2 hops; (c) 5 safety probes correct from DO pages alone (copy sim gains? Stop▶Play reset? RC takeover in Position? "landed, disarmed" in the log enough? which yaml on the real drone?); (d) undefined jargon ≤3 per DO page; (e) ≤150 words before the first runnable command on START_HERE.
**4 — mirror:** pull into the mirror; owner pushes; reprint PREFLIGHT; drain INBOX; delete stubs after 30 days with zero inbound refs.

## 5 · Out of scope — recommended follow-ups (engineering)
- `teleop_real_ours.yaml` (our fences, land_speed 0.6, max_speed 0.5) — TELEOP §5 blocked until it exists (iron rule 8).
- Separate sim DDS domain (e.g. `SVG_DOMAIN_ID=11`) — removes the shared-topic hazard step 0 only detects.
- Rename `cbf_sim.yaml` → `sim_cbf.yaml` so "ours"/"cbf" never reads as flyable.
- Install check_docs.sh as a local pre-commit hook.
- Printed-card versioning: PREFLIGHT line-1 date checked; reprint step in RUNBOOK §D.
- Resolve MAV_SYS_ID 1-vs-2 and watchdog-vs-voxl-dds-retry before M3 (gates items).

## 6 · Open questions for the owner
1. Approve the Phase-0a merged iron-rules wording first (base = PREFLIGHT's operational text + CLAUDE.md's load-bearing parentheticals). Any rule to word differently?
2. Can you hold all doc edits except `docs/record/INBOX.md` for the move window (two sittings), and is the mirror clean right now?
3. When are the M3 flight and the camera upgrade? That dates the §B/§C trim and the MOCAP §6.1 re-check.
4. TELEOP §5: blocker banner only (docs), or create `teleop_real_ours.yaml` before Phase 1 so §5 is rewritten to it in the same window?
