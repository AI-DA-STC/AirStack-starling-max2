# Claude handoff: svg_training (vectorised training pipeline)

> **How to use this file.** Read it at the start of a session, after [../../CLAUDE.md](../../CLAUDE.md).
> §4 is the current state, §5 is what is waiting on people. Update both before you stop.
> Last updated: 16 November 2026 (S2 built and every task reviewed; S2 documents written (Task 11): [../S2_RESULTS.md](../S2_RESULTS.md); final review pending; stand-in trainer moved to S2b; S2b plan approved, starts after S2 closes).

## 0. Resume here (for a new session or another Claude account)

Everything needed is in this folder; nothing depends on the previous chat.

**Where it stands.** S0 and S1 are closed. **S2 is built and every task reviewed; its documents are written
(Task 11) and the final review is pending** (gatekeeper on the S2 records, a code review of the whole S2 diff, a
newcomer read of S2_RESULTS and PLUG_IN). Nothing has been trained. S2's results, with figures:
[../S2_RESULTS.md](../S2_RESULTS.md); the partner guide: [../PLUG_IN.md](../PLUG_IN.md). The short version:

| Run | Result | Meaning |
|---|---|---|
| T5, drone model against the 12 Nov bag | FAIL | worst leg 0.120 m/s (gate 0.10; leg 3 is not a push), 63 % time off by 0.690 s (gate 0.10; mostly the held-setpoint method); model not refitted |
| T6, scripted reference | INFO, no gates | pure-rule half stands; Starling closeness spoilt by the wall bug (fixed in 17197a7) |
| T7, faster filter | ABORTED | stopped by hand for the wall fix |
| T8, faster filter | PASS (owner's 4-decimal ruling on `max_abs_dv_mps`) | 1,000 sweeps + `check_every` 8: 121,118 game-steps/s timed window (gate 100,000); whole game 90,121 INFO; staggered restarts NOT measured. Now in `configs/s2_game.toml` |
| T9, scripted reference on the fixed layer | INFO, no gates | the reference for later strategies. Pure half identical to T6. Crowded 5 v 3 near walls still reaches 0.75–0.80 m in 3-D: a LIMIT faithful to CMU's commander (filter wall-blind, fence after the filter), not a bug |

Design §7 done conditions: (1) game-rule tests PASS; (2) scoring tool on fixed scenarios PASS; (3) filter PASS (T8);
(4) stand-in trainer MOVED to S2b by the owner (16 November), not run; (5) partner guide DONE (stand-in example added
in S2b). Interface change 16 November: observation 69 → 71 numbers (zone centre at 69–70; central state 59 → 61).

S1 in one line: T2 filter copy FAIL (accepted by the owner), T3 simulator fit FAIL (two clocks), real-log fit
exploratory, T4 INFO; details in [../S1_RESULTS.md](../S1_RESULTS.md).

Tests (Task 11, 16 November, laptop host, conda `env_isaaclab`, `PYTHONPATH=source`): `531 passed, 2 warnings in 398.78s` (full suite after the Task 11 document edits; the 2 warnings are matplotlib tight-layout notices from `scripts/make_s2_figures.py`). The partner leak test ran but checks nothing on this laptop: the local file has no number distinctive enough to scan (see §5).

1. `cd ~/AirStack-starling-max2/svg_training && claude`, then say: **"Run the train-start skill, read
   docs/claude/HANDOFF.md §0, and tell me what is waiting on me."**
2. **Next, in order.**
   - **S2 final review** (plan Task 11): `train-gatekeeper` on T5–T9 with their `gates.toml` and ledger rows; a code
     review of the whole S2 diff (superpowers:requesting-code-review) against the plan and design; `panel-newcomer-reader`
     on `S2_RESULTS.md` and `PLUG_IN.md`. Fix rounds until no Critical or Important is open; tick STANDARDS §11; the
     lead commits the documents with explicit paths and refreshes the `~/Downloads/` copy.
   - **Owner rulings before S2b runs** (§5 rows A and B): (A) the S2b gate `physics_closest_cross_min_m = 1.0` fails by
     construction (T9: 0.75–0.80 m near walls, 0.025 m in crowded starts); proposed replacement: compare the Isaac
     Lab drones with tier 1 game by game in 3-D, leaving out start-miss games; no S2b run yet. (B) keep the filter
     faithful to CMU (recommended) or make the training copy wall-aware.
   - **S2b** ([../plans/2026-11-16-s2b-isaac-lab-environment.md](../plans/2026-11-16-s2b-isaac-lab-environment.md)),
     approved with the owner's 7 answers (in the plan): the S2 game on rigid-body Starlings in Isaac Lab with PX4's
     cascade and the real gains; compare with tier 1; throughput; stand-in trainer on both backends (unchanged
     `[standin_gates]`); Isaac Lab MP4s; TensorBoard for every training run. Isaac headless only (WiFi-firmware crash risk).
   - **Before any training-time claim:** an INFO speed run with staggered game restarts (T8 did not measure it).
   - **Real flight with planned pushes (owner flies; PENDING; NEAR-962).** It gives the drone model its run of record;
     what to record: [../S1_RESULTS.md](../S1_RESULTS.md#what-the-owner-needs-to-do-next) (proposals only, authorises
     no flight). Then gates BEFORE the fit, the fit, a record, a ledger row and a named parameter file under `params/`.
3. **Owner's decisions so far** (all also in the plans):
   - 15 Nov night: NUS's strategy is the MAIN use; NEAR Lab's own strategies are a research SIDE QUEST; arena sizes
     vary; approach A; main game = **partner rules preset** with the Starling layer scored on top; contact tags only
     in the side quest; NUS's numbers only in the **git-ignored** `configs/local/` (the programme report is
     confidential; this repo may be public); speeds Strike 0.5, Guard 0.33 m/s. Fix the sim commander's wall clock in
     an AirStack session (note `~/Downloads/note-for-airstack-sim-clock-fix.md`); CMU need not be told about the
     position-setpoint gap; emergency push-apart differences accepted; owner labels `08_34_27.ulg`; no sim step session.
   - 15 Nov late night: "just execute the rest" = S2 plan and gates approved (`configs/s2.toml`), build it.
   - 16 Nov: `max_abs_dv_mps` gate compared at its 4 written decimals ("4 decimals. yes."); S2b approved, the S2
     stand-in trainer moves into S2b; replay media wanted (done, `docs/media/`) plus an Isaac Lab MP4 (S2b);
     TensorBoard for every training run (S2b plan); no Linear cycles or dates on pipeline issues; the project's Linear
     snapshot lives in `svg_training/docs/linear/`.
   - **Still to ask NUS (owner; NEAR-970):** metres per unit, seconds per step, which NUS project is the strategy to
     host, its inputs/outputs and software, code access; whether to tell NUS and UPenn about this pipeline.
   - Linear: project P-NEAR-31, S2 issues NEAR-963 game core, NEAR-964 bag check, NEAR-965 faster filter, NEAR-966
     scoring + opponents, NEAR-967 plug-in guide, NEAR-968 stand-in (now S2b), NEAR-969 S2 results page
     ([snapshot](../linear/snapshots/2026-11-16-project-plan-linear.md)); the snapshot's states predate Tasks 6–11.
4. Rules while building: write only inside `svg_training/`; commit finished, tested steps with explicit
   paths, never push (builder agents make no git writes; the lead commits); no `pip install`; Python is
   `~/miniconda3/envs/env_isaaclab/bin/python`; tests with `python -m pytest -q` from this folder.
   Owner rules of 15 November: every results page shows generated figures or a flowchart; plain language for
   a reader new to the topic; no change to flight or simulator code (STANDARDS §11).
5. Model use the owner prefers: the lead plans and reviews, cheaper models build. He expects usage
   limits to run out quickly, so **update the tables below after every task**, before starting the next.
6. A copy of this file is kept at `~/Downloads/claude-handoff-svg-training.md`; refresh it with
   `cp docs/claude/HANDOFF.md ~/Downloads/claude-handoff-svg-training.md` after each update.

**S2 progress** (plan: [../plans/2026-11-15-s2-game-and-plug-in.md](../plans/2026-11-15-s2-game-and-plug-in.md); build ledger `runs/sdd/s2/progress.md`, git-ignored, with every ruling and finding)

| Task | What | State |
|---|---|---|
| 1 | Configs, gates, git-ignored local partner file, leak test | done (`fc1a2bd`) |
| 2 | Game core: arenas, starts, motion, walls, zone, time-out, drop-outs, observations | done (`96894cc`..`fc19712`); 5 v 3 lab start miss ~1/3 = geometry, flagged and counted |
| 3 | Pair rules: push-apart (partner) and contact tags (side quest) | done (`3a174d1`) |
| 4 | Starling layer | done (`12ffaf7`..`04a5223`); exploratory-model limits: head-on 1.050 m, t63 0.6–0.9 s, ~9 s slow mode |
| 5 | Strategy contract and scripted opponents | done (`bf49b31`..`771f206`) |
| 6 | Match loop, metrics, scoring tool, scripted reference T6 (INFO) | done (`91746a6`..`27deb4f`); wall bug found in review, 3-D closest approach added |
| 7 | Faster filter: 7a accuracy (`df8a591`), 7b speed: T7 ABORTED, T8 PASS, wall fix | done (`17197a7`..`673536f`); `check_every` 8 in the game config (`f6702ca`) |
| 8 | Drone-model check on the 12 Nov bag, T5 FAIL | done (`f6f0a39`..`59e8ec4`) |
| — | Scripted reference re-run on the fixed layer, T9 (INFO) | done (`0467628`, `002a65b`); crowded-5 v 3 wall limit diagnosed |
| 9 | skrl and Gymnasium adapters, partner guide `docs/PLUG_IN.md`; observation 69 → 71 | done (`c9faff3`..`911b3ae`) |
| 10 | Stand-in trainer | MOVED to S2b (owner, 16 November) |
| — | Replay clips (`docs/media/`) | done (`bcae60b`); the Starling clip predates the wall fix |
| 11 | Documents (S2_RESULTS, WHAT_WE_DID §7, GLOSSARY, README, CLAUDE.md, DESIGN §8 note, STANDARDS §4 sources, this file) | written, final review pending |

**S1 progress** (plan: [../plans/2026-11-15-s1-drone-model-and-safety-filter.md](../plans/2026-11-15-s1-drone-model-and-safety-filter.md); build ledger `runs/sdd/s1/progress.md`)

| Task | What | State |
|---|---|---|
| 1 | Config and approved gates (`configs/s1.toml`) | done (`92d30ac`) |
| 2 | Bag to CSV inside CMU's robot image | done (`cf239d0`) |
| 3 | Response model and fitting (NumPy reference) | done (`c4f77d0`) |
| 4 | Fit v0 on the existing teleop session | DONE, reviewed: run of record **T3 = FAIL** on 3 of 4 gates (`records/2026-11-15_s1_fit_v0_record.md`, figures in `docs/figures/s1_t3_*`). Main finding: on every 0.5 m/s push the sim drone peaks at ~85 % of the command, sags to 50–65 % while the command is still held, then drifts backwards ~25 % after release; no lag model can do that. CAUSE FOUND ([../notes/s1_two_clocks_cause.md](../notes/s1_two_clocks_cause.md), replay matches to 0.019 m/s): in the SIM the commander advances its teleop reference on the wall clock while PX4 runs 1.9× faster, so the drone outruns it (sim-only; real drone σ = 1). Recommendation for Task 6: copy the commander's teleop law in code with the time scale σ as a parameter, and fit only PX4's lag (setpoint → velocity; a first-order fit gives held-out RMS 0.036–0.047 m/s). Owner to confirm; running the commander on sim time inside AirStack is his call. Sim time scale this session 1.907 (ulog) |
| 5 | Designed step session in the AirStack simulator (Isaac starts once) | SCRIPTS DONE and committed after 5 fix rounds and a safety re-review (`runs/sdd/s1/task-5-rereview.md`: safe with the owner present, no open Critical/Important). 270 tests pass; dry run creates nothing. **Real session NOT RUN, held for the owner.** Conditions: launch detached (`setsid nohup bash scripts/record_steps.sh <name> > runs/<name>.out 2>&1 &`, about 7–11 min), and the owner confirms no real drone, mocap bridge or second ground station is on DDS domain 1. Expected (worked out with the old time scale 1.33; the measured one is 1.73–1.97, so more descents may be skipped or cut): 35 of 36 steps fly (one 2.0 m/s descent skipped by the floor guard), peak about 16.5 m in the sim. Since the final review the stick itself refuses (exit 67) unless the commander reports every drone in mode `sim` and no `/fmu/` topic is on the domain. Any other commander seen → exit 67, no `land`, no `down` |
| 6 | Fit v1 on the designed steps | REPLACED: the drone model's run of record comes from planned pushes at the next REAL flight (list in `records/2026-11-15_s1_real_px4_exploratory.md`); the sim step session is optional |
| 7 | Batched safety filter with team mask, parity run | built; run of record **T2 = FAIL** on 2 of 4 gates (`records/2026-11-15_s1_filter_parity_record.md`). DONE: reviewed (task review + re-review clean after one fix: a NaN in one team leaked into the other team; T2 numbers unchanged bit for bit); 28 tests pass; figures in the record. **Owner, 15 Nov: "if 1998/2000 checks passed its ok"** = T2 stays FAIL in the ledger, gates unchanged, and S1 goes on with this filter. The owner accepted T2 on 15 November ('if 1998/2000 checks passed its ok'); that figure is the emergency-agreement count. Re-confirmation on the counts above was asked the same day; **the owner confirmed (15 November, night: "yes ok")**. Background (corrected after the gatekeeper check, `runs/sdd/s1/gatekeeper-s1.md`): of the 1,779 scenes where CMU did not push apart, 13 are over the 0.02 m/s limit (3 over 0.1 m/s; the worst 2, 1.67 and 1.04 m/s, are where our copy pushed apart) and 109 over the 2e-3 residual limit (CMU's own filter is over it in 94); the speed failures are scenes where CMU needs its slow one-pair-at-a-time phase, and CMU's own answer stops up to 0.10 m/s short of the exact one. Options: re-define the two gates against the exact answer, add that slow phase (a pair loop), or accept FAIL. Also: 1,000 sweeps cost 582 ms per step for 4,096 games, about 7,000 game-steps/s (Task 7 estimate; T4 later measured 10,027 open / 7,938 full sensing), far too slow to train; Task 8 must measure a lower sweep count |
| 8 | Tier 1 with the fitted model and the filter | DONE, reviewed clean after 1 fix round. Real-drone chain in tier 1 (commander copy + exploratory PX4 response + team filter at the commander's CBF point; per-team speed cap, Guard = Strike ÷ 1.5). Run T4 = INFO (`records/2026-11-15_s1_tier1_fitted_filter_record.md`): 4,096 games, open/full sensing: filter off 2.27 M / 38.3 k game-steps/s; 1,000 sweeps 10.0 k / 7.9 k; 200 sweeps 48.4 k / 21.3 k. Finding (HYPOTHESIS for the real drone, owner told): the commander's CBF filters only the teleop velocity, the position setpoint up to 0.2 m ahead is not filtered, so teammates flown head-on reach 1.083 m (keep-out 1.10 m) in the copy |
| 9 | Hand-over | DONE: [../S1_RESULTS.md](../S1_RESULTS.md) written (10 figures, route flowchart, run table, the owner's next steps); STANDARDS §5 rows and rules 3 and 8, new rule 10 (training model from real flight logs); WHAT_WE_DID §6–7, GLOSSARY, README, CLAUDE.md status; report `runs/sdd/s1/task-9-report.md` (local); tests `316 passed` at hand-over, `325 passed` after the final-review fixes. Gatekeeper reading of the S1 records done; its must-fixes applied |

**Owner, 15 Nov afternoon ("ok i will follow all ur reccomendations"):** (1) Task 6 = copy the commander's teleop law in code (time scale σ as a parameter, 1 for the real drone) + fit only PX4's lag; fit it from the sim first (label "simulator drone"), then from REAL flight logs, which is what training should use, plus small randomisation. The real-log fit is a NEW step outside the approved plan; first a read-only survey of ~/flight_logs/2026-11-1x ([../notes/s1_real_logs_survey.md](../notes/s1_real_logs_survey.md)). (2) Owner says no drone is up. The sim step session is still held: at 15:xx the laptop was on WiFi only (Ethernet down, 10.10.100.x, remote desktop active), which is the Isaac-start WiFi-crash setup; launch once on Ethernet or with the owner at the machine. SURVEY RESULT ([../notes/s1_real_logs_survey.md](../notes/s1_real_logs_survey.md)): the real drone gets position + velocity setpoints (px4_interface TRAJECTORY mode, CMU comment ~0.1 s lag), the sim gets velocity only through MAVROS (~0.7 s): a sim-fitted model would make training think the drone is sluggish. Real ulogs: setpoint 5 Hz, position 10 Hz, ≤0.5 m/s, no stick topic. Exploratory real fit on log103 (#36) DONE and committed (`records/2026-11-15_s1_real_px4_exploratory.md`, no gates, reviewed clean after one fix round): commander → px4_interface TRAJECTORY mode → PX4 1.14 `v_ff + 0.95·(p_sp − p)`; real σ = 1.01. After choosing the family on training legs only, held-out RMS 0.058 m/s, the SAME as the baseline 'drone flies the setpoint speed ~0.15 s later' (no delay: 0.095). So at ≤0.5 m/s the real drone ≈ setpoint delayed ~0.1–0.15 s; the model misses the overshoot (held-out peaks up to 1.31×) and the slow drift after release (−0.14×). Also found: MPC_XY_VEL_MAX is 3.0 m/s on both drones (docs/CONFIG.md said 20; fixed on the owner's request in AirStack commit 680cd1f); tilt limit 30° drone_1, 45° drone_2. Recommendation: sim step session deprioritised (it measures the wrong chain); the run of record for the drone model should come from designed steps at the next real flight with full-rate logging. (3) The commander's wall-clock bug is SIM-ONLY (the real drone runs in real time); fixing AirStack is the owner's call, not done here.

**S0 progress** (plan: [../plans/2026-11-14-s0-measure-throughput.md](../plans/2026-11-14-s0-measure-throughput.md))

| Task | What | State | Evidence |
|---|---|---|---|
| 1 | Skeleton, gates, record scaffolding | done | 3 tests pass; reviewed. Approved config sha256: [../GETTING_STARTED.md](../GETTING_STARTED.md#approved-sha256) (approved 15 November; replaced `959dc710…` of 14 November) |
| 2 | Analytic shapes | done | reviewed; maths checked independently. Known limit parked for S3: the 24-step ray march is conservative beside surfaces (`runs/sdd/progress.md`) |
| 3 | Distance field | done | reviewed; maths checked independently. Known limit parked for S3: the 24-step ray march is conservative beside surfaces (`runs/sdd/progress.md`) |
| 4 | World, range rays, line of sight | done | reviewed; maths checked independently. Known limit parked for S3: the 24-step ray march is conservative beside surfaces (`runs/sdd/progress.md`) |
| 5 | Placeholder response model, tier 1 benchmark environment | done | reviewed twice; 23 tests pass for Tasks 1–5. Review caught and fixed: Guard drones could reach Strike speed on diagonals (now capped at speed ÷ 1.5 in norm, with a test) |
| 6 | Timing harness, tier 1 benchmark script | done | reviewed (timing logic verified: no hidden sync, clock bounded by synchronises); one fix round (re-runs skip finished points instead of duplicating rows). Whole suite: 64 tests pass |
| 7 | Tier 2 benchmark (Isaac Lab) | done; FIRST RUN 15 Nov | smoke point in the container: 64 games × 2 drones, ~1,800–2,300 game-steps/s, 0 NaN, 2.5 % resets per step, repeats within 1 %. Found and fixed: `simulation_app.close()` spun forever after the rows were written; the script now always leaves with `os._exit` (commit `08107eb`) |
| 8 | Record and ledger from results and gates | done | 30 tests pass; reviewed with an attack list, two fix rounds. Reviews closed three ways the record could have shown a false PASS (NaN rate, missing NaN count, negative or duplicated rows). `make_record.py` needs `--seeds` |
| 9 | Run S0 on the laptop, record, gatekeeper | done: T1 = FAIL on one gate | `records/2026-11-15_s0_laptop_record.md`, ledger T1 (commit `1b50419`). Only `sweep_complete` failed: tier 2 point `t2_k1` at 64 games lost to an Isaac Sim start-up segfault (Kit telemetry thread, before project code). Gatekeeper: every number recomputes exactly from `results.jsonl`; record faults to fix in code for the next run: commit shown as `unknown` (no `.git` in the container) and stale "untracked" text; no status labels (MEASURED / PROPOSED) in the record; ledger date in container UTC. Owner decides: accept T1 and go to S1, or re-run S0 after the fixes |
| — | Owner's decision on T1 (15 Nov) | "go with ur recommendations" | T1 stands as FAIL as written; its numbers are used. Next, in order: (1) record fixes + automatic retry of an Isaac start-up crash (building); (2) the S1 plan for the owner's approval (research running); (3) documentation written with the technical-writer agent. The next S0 (on the workstation) should come out PASS |
| — | Owner, 15 Nov ("yup ok") | S1 plan approved with its gates; root README links the folder | S1 runs subagent-driven from `docs/plans/2026-11-15-s1-drone-model-and-safety-filter.md`; a training guide (headless and with the Isaac Sim window) is being written for when training exists (S2) |
| — | Owner, 15 Nov, before signing off for the night | "show it by showing generated graphs … (flowchart etc) to visualize the data" | Standing rule: every results or evidence page shows at least one figure generated by a committed script from the run's own data (and a flowchart where a process is explained). Apply to S0_RESULTS now and to every S1 record. He checks tomorrow |
| — | Owner, 15 Nov, same evening | "ensure that none of the real drone code or sim code in airstack is affected"; "provide explanation in non AI-ish terms … assume reader is new to this" | Verified by git: no commit of this work touches `AirStack/`, `tools/`, `patches/`, `mocap/`, `localisation/` or the drone parameters; now a definition-of-done check (STANDARDS §11). Plain-language rule added to STANDARDS §2; a plain-language pass and a new page `docs/WHAT_WE_DID.md` are being written. Applies to chat replies too |

Build bookkeeping (rulings, briefs, reports, snapshots) is in `runs/sdd/`; its ledger is `runs/sdd/progress.md`. `runs/` is git-ignored: these exist on this laptop only, so committed pages must not cite them (notes they need are copied to `docs/notes/`).
S0 was built before the folder was tracked: each task was reviewed from a file diff against a snapshot (`bash runs/sdd/tools.sh`).
Tasks 2–4 are built and reviewed together. No Isaac Sim launch before the lead checks `docker ps` and
that the owner is at the machine or on Ethernet.

What the final review found that matters to the owner: (1) a cold laptop GPU made two repeats differ by 22 % at the smallest sweep point, so warm-up becomes at least 50 steps AND 2 s (gates and config untouched); (2) one distance routine in the tier 1 stand-in dominated open-arena timing (being replaced, with a before/after measurement); (3) rows carry a hash of the code (`code_sha`), added while the folder was untracked; (4) `gnome-remote-desktop-daemon` holds 611 MiB of GPU compute memory on this laptop, a sign a remote-desktop session may be active.

**S0 results:** [../S0_RESULTS.md](../S0_RESULTS.md) (run of record T1; record
[../../records/2026-11-15_s0_laptop_record.md](../../records/2026-11-15_s0_laptop_record.md)). The tier 1 table of
14 November and its repeat-gate question are superseded: the owner approved the new config (timed window at least
200 steps and at least 2 s) on 15 November, and T1 passed the repeat gate.

**Packaging (14 November 2026, third round).** The folder is COMMITTED: `2daf942` on `main` (change-log
CHG-0068), mirror updated (one commit ahead of GitHub; the owner pushes after checking the repository is
private). It is a top-level component of the repository. `docker/build.sh` builds `svg-training:isaaclab-2.3.2` on NVIDIA's `nvcr.io/nvidia/isaac-lab:2.3.2`
(26 GB download, once) and adds pytest plus two launchers, `svg-python` and `svg-isaaclab`, that keep exit codes
(Isaac Sim's own `python.sh` turns every failure into exit 1). Tests: T1's test count is in
[../S0_RESULTS.md](../S0_RESULTS.md#the-fail). `scripts/run_s0.sh` works in both places
(`SVG_PY`, `SVG_ISAACLAB`, `SVG_IN_CONTAINER`). The partial run `runs/2026-11-14_s0_laptop/` (code hash
`e9a7b4407e58`) was not finished; T1 ran from the start as `2026-11-15_s0_laptop` (code hash `13bebe8bb138`).

State values: not started · building · built, in review · done (tests quoted) · blocked (why).

## 1. Summary

Jeremy (Robotics AI Engineer, NEAR Lab, ST Engineering) wants training for the Strike vs Guard game to
run in parallel on a GPU. On 14 November 2026 a first session read the flight stack and the programme
website, ran web research on drone training in Isaac Lab, proposed a pipeline, and the owner chose an
approach. This folder now holds the rules, the design, the research digest, the diagrams, and the
agents and skills for the work. Since then S0, S1 and S2 have been built and run (T1–T9, §0); **nothing has been trained.**

## 2. Read these first

| File | Why |
|---|---|
| [../../CLAUDE.md](../../CLAUDE.md) | hard rules, environment, how a session runs |
| [../../STANDARDS.md](../../STANDARDS.md) | interface, game specification, drone models, gates, records |
| [../DESIGN.md](../DESIGN.md) | seven stages, two tiers, four uses, build order |
| [../RESEARCH.md](../RESEARCH.md) | evidence with sources |
| [AGENTS_AND_SKILLS.md](AGENTS_AND_SKILLS.md) | which agent or skill to use for what |
| `~/Downloads/claude-handoff-vectorised-drone-training.md` | the earlier chat that started this (11 November 2026) |

## 3. Non-negotiables

1. Write only inside `svg_training/`. Ask the owner before anything outside it.
2. Never push. Commit finished, tested work with explicit paths (CLAUDE.md rule 2).
3. Drone numbers flow from the drone to the trainer, never back.
4. A simulator result is "observed in the training simulator", not "validated".
5. Gates before runs; never moved.
6. Programme wording: Strike team, Guard team, tag, reach the zone, drone team.

## 4. Current state

**How to talk to the owner.** Start from the high-level picture, then go deeper step by step. Use
standard professional terms. Prefer simple diagrams and tables, readable at page width. He is new to
this simulation and training stack. He dislikes walls of text. He asked to be consulted before
anything uncertain is executed, and told about anything that could affect other sessions' work.

**Decided by the owner, 14 November 2026.**

| Decision | Choice |
|---|---|
| What the pipeline is for | team strategy; hosting partner strategies; low-level flight control; camera-based behaviour ("future work, not a priority at the moment") |
| Build approach | C: two tiers sharing one game ([DESIGN §4](../DESIGN.md)) |
| Isaac Lab version | 2.3.2 now; 3.0 later on the RTX 5090 machine |
| Folder | `svg_training` in the live clone `~/AirStack-starling-max2` (he first wrote "IssacLab") |
| Packaging (third round, same day) | "the point is to add a training pipeline to airstack": the folder is committed as a top-level component of the repository, like `localisation/`, with a `docker/` image carrying Isaac Lab (option A); its agents and skills are committed too ("yes commit agents") |
| Models | Fable orchestrates; if it runs out, Opus at high effort |
| Fourth round (15 November) | repository may be public ("its just a training pipeline doesnt need to be private"); new S0 config approved (timed window at least 200 steps and at least 2 s); Isaac Lab launch approved ("ok do it"; he is remote with the laptop behind him); after a tag both drones leave by default |
| Design | approved ("yup looks good"), with the four answers below |
| Tag | physical contact between a Guard drone and a Strike drone; no tag radius. His words: "the end goal is to have physical interdiction between strike team and guard team drones" |
| Safety filter | only between drones of the same team |
| Environments | "different real-ish environments", the construction-site world as the example; he asked for research on more realistic ones and whether it affects training |
| Velocity-step logs | this pipeline may run `tools/sim.sh` |
| Training hardware | "eventually" an RTX 5090, RTX PRO 6000 or RTX 6000 Ada |

The priority order among the four uses (strategy, partners, flight control, cameras) is Claude's
reading of his answer, not his words; confirm it if it matters.

**The earlier handoff's three open questions, answered.**

| Question | Answer |
|---|---|
| What is being trained? | the four uses above |
| Which Isaac Sim and Isaac Lab? | Isaac Sim 5.1.0, Isaac Lab 2.3.2 + 25 commits → the 2.x cloning API (`clone_environments`, `GridCloner`) |
| Which AirStack simulation profile, how many drones? | Isaac Sim + Pegasus + PX4 v1.16.1, three drones by default, PX4 time about 1.3 times wall-clock |

**Session 1 (14 November 2026): what was done.**
- Read `~/AirStack-starling-max2` and the website repository; six agents (two repository readers, one
  local Isaac Lab inspector, three web researchers).
- Checked that a new top-level folder cannot break another session's commit: the pre-commit hook reads
  staged paths only and the docs checker does not scan it.
- Built the diagram deck (10 slides) and, after the owner's choices, wrote `CLAUDE.md`,
  `STANDARDS.md`, `docs/DESIGN.md`, `docs/RESEARCH.md`, this file, six agents and six skills.
- Nothing outside this folder was edited. Nothing was committed.

**Session 1, second round (same day): what the owner's answers changed.**
- Contact tags and a per-team safety filter are now FIXED in STANDARDS §4. Contact distance in tier 1
  is 0.50 m, measured from the drone's USD.
- Three more research tasks: the construction-site world on disk, sources of realistic environments,
  and how clutter and contact change training. Results are in RESEARCH §9–10 and DESIGN §7.
- A realistic environment does affect training: drones lose sight of each other, cost rises, one
  layout is not enough, and sensing becomes the speed limit. DESIGN §7 has the environment ladder.
- Published comparisons found velocity-commanded drones touch an agile drone far less often than
  thrust-and-body-rate ones. S2 measures this here; the fallback is a final-approach skill on tier 2.
- Build steps keep their names S0–S5 but now carry environments: S2 open arena, S3 random blocks and
  columns, S4 the construction-site world with the tier 2 cross-check.

**Calls Claude made in that round, for the owner to correct:** a drone that touches a structure
leaves the game and avoiding structures is learned (the flight stack has no obstacle avoidance);
the policy senses its surroundings through range rays; files baked from the construction-site asset
stay out of git; real flights of a contact policy should start with a virtual contact distance.

**Facts found that the design rests on** (sources in STANDARDS §3–5 and RESEARCH):
- A strategy sends velocity + yaw rate in the world frame, 20 times a second, into the ground
  controller; today's plug-in point is `/svg/{name}/teleop_command`.
- The safety filter is one centralised node, about 550 lines of Python, keep-out 1.10 m.
- Isaac Lab 2.3.2 offers a multirotor at motor-thrust level, multi-agent environments and skrl's
  IPPO and MAPPO; it has no velocity controller and no self-play. Both are ours to build.
- Isaac Lab 3.0 (20 October 2026) adds batched velocity controllers and a velocity-command
  navigation task, needs Isaac Sim 6.2 and a newer GPU driver.
- No published throughput existed for quadrotor teams in Isaac Lab; S0 has since measured ours ([../S0_RESULTS.md](../S0_RESULTS.md)).
- The repository holds no Strike vs Guard game code.

## 5. Open items

| Item | Who | Needed before |
|---|---|---|
| **A. S2b gate `physics_closest_cross_min_m = 1.0`** fails by construction (T9: the same command chain reaches 0.75–0.80 m near walls, 0.025 m in crowded starts). Proposed: compare Isaac Lab drones with tier 1 game by game in 3-D, excluding start-miss games | owner (proposal pending) | the first S2b run |
| **B. Training filter faithful to CMU (recommended), or wall-aware** (a departure from the real commander) | owner | S2b scoring runs |
| D1 reading of "one keep-out per team" (`push_rule = "block"`) against NUS's report; `shove` is the other switch | owner | a partner-rules result |
| Real-drone hazards, **HYPOTHESES, not flown, not fixed**: (1) CMU's commander runs the CBF (`swarm_commander.py` ~2140) before the keep-in fence (~2210), so a drone held at the fence may let another inside 1.10 m (T9 diagnosis, training copy); (2) the position setpoint is not filtered, teammates head-on 1.083 m in tier 1 (T4) | owner (tell CMU? test?) | the next multi-drone real flight near a fence |
| INFO speed run with staggered game restarts (T8 timed all games starting together) | Claude | any training-time claim |
| The partner leak test (`test_local_values_not_in_tracked_files`) is vacuous here: the local file has no number with 3+ significant digits outside the committed defaults (placeholders), so it scans nothing; widen the test or fill the real values | lead | the real partner values arrive |
| `docs/media/5v3_starling` clip and its README "known limit" line predate the wall fix (`bcae60b` < `17197a7`); regenerate or relabel | Claude | showing the clip outside the lab |
| A pair mask in CMU's safety filter, so that a contact tag can fly at all; and a flight safety case for deliberate contact | owner + CMU (outside this folder) | any flight of a contact policy |
| The zone's size and place in each world beyond S2 (S2 draws arena and zone sizes at random; partner zone ratio in the local file) | owner | S3 |
| Licence of the construction-site asset (an Unreal Engine asset pack exported by the lab; no licence file found) | owner | before anything made from it leaves the lab |
| What the real drone senses its surroundings with: a known map, or an on-board range sensor | owner | S3 |
| Control level for contact tags: stay at velocity, or add a final-approach skill at thrust and body rates | owner | side quest (S2 trained nothing with tags) |
| The real flight with planned pushes (NEAR-962; list: [../S1_RESULTS.md](../S1_RESULTS.md#what-the-owner-needs-to-do-next)); T5 shows the exploratory model rises too slowly | owner | the `real` parameter set's run of record |
| Metres per partner unit and seconds per step, NUS's strategy code and its inputs/outputs (NEAR-970); hangar flying space in metres | owner + NUS | a partner-rules result quoted in metres; scoring NUS's strategy |
| What a drone may observe about others (full state, or shared with delay and loss); S2 gives the full state behind the `obs_view` switch | owner + partners | S3 |
| How a drop-out is simulated | owner + partners | S4 |
| Written velocity contract with NUS and CMU (Linear NEAR-874, NEAR-875) | owner + NUS + CMU | use 2, S5 |
| Tell UPenn and NUS about this pipeline; UPenn already has an Isaac Lab environment | owner | early |
| Access to a training workstation (RTX 5090, RTX PRO 6000 or RTX 6000 Ada); its driver and Isaac versions (NEAR-959) | owner | S0 on that machine |
| Build and try the image on the training workstation (`docker/build.sh`, then `docker/run.sh`) | owner + Claude | S0 on that machine |
| A ROS 2 policy node inside the AirStack tree | owner (separate approval) | S5 |
| Rotor positions for tier 2: sim CAD or the drone's parameters | owner | S4 |
| Driver 595 with AirStack's Isaac Sim 5.1 | untested | any move to Isaac Lab 3.0 on a machine that also runs AirStack |

**Not verified** (carry these as doubts, not facts): every published throughput estimate for Isaac Lab (S0 measured
ours: [../S0_RESULTS.md](../S0_RESULTS.md)); the
Isaac Lab 3.0 release details beyond what RESEARCH cites; the links in RESEARCH (collected by web
research agents; open one before quoting it outside the lab); the axis order of the inertia values;
the real drone's response above 0.5 m/s (S1 saw only up to 0.5 m/s, exploratory); the vertical response
(not fitted); whether the drone's PX4 build matches tag v1.14.0, which S1 read.

**Independent checks run in session 1.** A builder check of the design and a review by the agent that
wrote the agents and skills found five wrong statements (simulator speed cap, arena box, delay
figure, Isaac Lab velocity controller, one speed cap in the filter); all five are corrected in
STANDARDS and DESIGN. Their open questions are in the table above.

## 6. How to continue

1. Run the `train-start` skill.
2. The design is approved. A change to it goes through the owner first.
3. S0 and S1 are closed; S2 is built and reviewed, final review pending (§0, [../S2_RESULTS.md](../S2_RESULTS.md)). Next is
   S2's final review, then S2b from its approved plan: build with `train-implementer`, test first, and have
   `train-gatekeeper` read each record.
4. One step at a time, S0 to S5. Each ends on a record and a ledger row.
5. For a design question, brief the adviser agents in parallel with the files, not your conclusion;
   reconcile; show the owner; then build.
6. Model split the owner prefers: the lead plans, orchestrates and reviews; other models execute.

## 7. Source material

| Source | Where |
|---|---|
| Flight stack, configs, records | this repository, read-only from here |
| Starling system identification | `isaac_sim/Starling 2 Max Sys ID Results - Slite.pdf` |
| Drone PX4 parameters | `starling_1_indoor_params.params` |
| Safety filter | `AirStack/robot/ros_ws/src/svg_ground_control/svg_ground_control/cbf_filter.py` |
| Ground controller | same package, `swarm_commander.py`, `trajectory.py`, `fence.py` |
| Programme, game, wording rules | `~/Documents/GitHub/Strike-Versus-Guard` (`content/programme/`, `STANDARDS.md`) |
| Programme reports | `~/Documents/GitHub/Strike-Versus-Guard-sources` — **confidential**: point to them, do not copy from them |
| Isaac Lab | `~/IsaacLab` (2.3.2), conda `env_isaaclab` |
| Linear plan snapshot | this project (P-NEAR-31): [svg_training/docs/linear/snapshots/2026-11-16-project-plan-linear.md](../linear/snapshots/2026-11-16-project-plan-linear.md) (folder layout: [../linear/README.md](../linear/README.md)); the flight-stack projects: `docs/linear/snapshots/2026-11-13-project-plan-linear.md` in this repository |
