# Claude handoff: svg_training (vectorised training pipeline)

> **How to use this file.** Read it at the start of a session, after [../../CLAUDE.md](../../CLAUDE.md).
> §4 is the current state, §5 is what is waiting on people. Update both before you stop.
> Last updated: 15 November 2026, night (S1 CLOSED: owner confirmed T2 on the exact counts and approved I7; docs/CONFIG.md speed limits fixed on his request, AirStack commit 680cd1f; root README.md "I want to…" table now has a row pointing here (owner's request); no drone-model gate passed; next = S2 plan for approval, real flight with planned pushes whenever the owner flies).

## 0. Resume here (for a new session or another Claude account)

Everything needed is in this folder; nothing depends on the previous chat.

**Where it stands.** S0 and S1 are closed (S1 closed 15 November, night, on the owner's answers). Nothing has been trained. Both gated S1 runs (T2, T3) are
FAIL, and no S1 gate on the drone model has passed yet: that waits on the real flight below. S1's results, with figures, are in
[../S1_RESULTS.md](../S1_RESULTS.md); the short version:

| Run | Result | Meaning |
|---|---|---|
| T2, filter copy | FAIL, accepted by the owner on the exact counts (15 November) | of the 1,779 scenes where CMU did not push apart, 13 are over the 0.02 m/s limit (3 over 0.1; worst 1.67 and 1.04 m/s, where our copy pushed apart) and 109 over the 2e-3 residual limit (CMU's own filter: 94); emergency agreement 1,998 of 2,000 |
| T3, AirStack simulator fit | FAIL | the sim's sag and swing-back come from the commander's wall clock against a PX4 running 1.907 times faster |
| real-log fit (no ledger row) | exploratory, no gates | real drone ≈ its trajectory setpoint delayed about 0.1–0.15 s at up to 0.5 m/s; the model is "observed in flight logs", never "validated" |
| T4, tier 1 with the real chain | INFO, no gates | filter at 1,000 sweeps: 10,027 / 7,938 game-steps/s at 4,096 games (open / full sensing), too slow to train. Lead's arithmetic from T4, not measured training: 2 billion drone-steps with full sensing take about 9 h at 4,096 games, about 5 h at 16,384 games (14,042 game-steps/s) |

Tests after the final-review fixes (15 November, late evening, laptop host, conda `env_isaaclab`, `PYTHONPATH=source`): `325 passed in 198.08s` (318 at the review plus 7 for the stick's simulator check).

1. `cd ~/AirStack-starling-max2/svg_training && claude`, then say: **"Run the train-start skill, read
   docs/claude/HANDOFF.md §0, and tell me what is waiting on me."**
2. **Next, in order.**
   - **Real flight with planned pushes (owner flies; PENDING).** It gives the drone model its run of record.
     What to record is listed in [../S1_RESULTS.md](../S1_RESULTS.md#what-the-owner-needs-to-do-next)
     (from the exploratory record §8 and [the survey §6](../notes/s1_real_logs_survey.md#6-what-to-record-at-the-next-real-flight)). That list is proposals only and authorises no flight. Afterwards: gates written
     BEFORE the fit, the fit, a record, a ledger row and a named parameter file under `params/`.
   - **Owner, 15 November, night: NUS's strategy is the MAIN use** (their code is not here yet; how it is trained is unknown); NEAR Lab training its own Guard/Strike strategies is a research SIDE QUEST. Arena sizes vary per game, as a test. Approach A chosen: game + random sizes + library-neutral plug-in + scoring tool + faster filter + stand-in trainer (pipe test only). Draft design: [../specs/2026-11-15-s2-game-and-plug-in-design.md](../specs/2026-11-15-s2-game-and-plug-in-design.md) (builder check done; **APPROVED by the owner 15 November, night**). Owner shared NUS's October 2026 update and then the programme's October monthly report (`~/Downloads/MR-Strike vs Guard-1.0-OCT29.docx`, RCC-MR-001, the one with the game rules in its Figure 2.1.1; both outside the repo). It is partner material with unpublished results: **do not copy its contents into this public repo** until the owner says what may go in. Its game differs from ours in one big way (see the owner's answer, pending), so the S2 plan waits on that answer.
   - **S2 needs a plan and the owner's approval before any code.** Nothing of S2 is written. The plan must
     settle a faster safety filter (fewer sweeps, an early stop, CUDA graphs; each measured against T2's
     checks), and uses the open items in §5 (zone size, arena, what a drone may observe about others).
   - **Final S1 review** done (15 November): no Critical; I1–I6 fixed (`runs/sdd/s1/final-fix-report.md`, local);
     I7 approved by the owner (15 November; STANDARDS §1). The gatekeeper's must-fixes were applied before it.
3. **Owner's answers, 15 November (night)** (A1–A4, C9–C14 of the decision list):
   - A1 main game = the **partner rules preset** (NUS's area-denial rules: opposite teams kept apart, teammates
     pass through, one step inside the zone wins), with the Starling layer scored on top (S2 design §4a);
   - A2 contact tags **only in the side quest**; A3 NUS's numbers only in a **git-ignored local file** (the
     programme report is confidential; this repo is public); A4 speeds Strike 0.5, Guard 0.33 m/s;
   - C9 fix the sim commander's wall clock **in an AirStack session** (note: `~/Downloads/note-for-airstack-sim-clock-fix.md`);
     C10 CMU need not be told about the position-setpoint gap; C11 the "20 m/s" comment fixed (AirStack 53945f6,
     CHG-0069); C12 emergency push-apart differences accepted; C13 owner will label `08_34_27.ulg`;
     C14 the simulator step session is not wanted.
   - **Still to ask NUS (owner):** metres per unit, seconds per step, which NUS project is the strategy to host,
     its inputs/outputs and software, code access; whether to tell NUS and UPenn about this pipeline.
   - **Owner, 16 November: after S2, stage S2b = the S2 game as an Isaac Lab environment** (rigid-body Starlings, PX4-like velocity controller with the real gains, compared with the PyTorch tier on step tests and the scripted reference games; pulls part of S4 forward). S2 Task 10 (stand-in trainer) MOVED into S2b, run on both backends with the unchanged S2 gates; S2 closes with Tasks 6, 7b, 9, 11. Plan being drafted: `docs/plans/2026-11-16-s2b-isaac-lab-environment.md`. Isaac runs headless only (WiFi-firmware crash risk). Owner wants showable media: a top-down replay GIF/MP4 of the PyTorch game (building now, docs/media/) and an Isaac Lab MP4 (task in S2b).
   - **Owner, 15 November late night: "just execute the rest"** (no drone available) = write the S2 plan and build it (subagent-driven, review per task, final review). Plan APPROVED with its gates and committed (e51ba6a): `docs/plans/2026-11-15-s2-game-and-plug-in.md`, 11 tasks. Build ledger: `runs/sdd/s2/progress.md` (git-ignored; task briefs and reports beside it). Task 1 DONE (fc1a2bd, review clean; local partner file created, git-ignored, scale placeholders). Task 2 (game core) DONE (96894cc..fc19712, review clean). Task 3 (pair rules) DONE (3a174d1, review clean). Task 5 (strategy contract + scripted opponents) DONE (bf49b31..771f206, review clean). Task 4 (Starling layer) DONE (12ffaf7..04a5223, review clean; head-on 1.050 m and t63 0.6–0.9 s are exploratory-model limits). Task 6 (match loop + scoring + scripted reference run, ledger T6 INFO) built (91746a6), in review — open: under the Starling layer Guard–Strike pairs reached 0.66–0.77 m (keep-out 1.10 m), cause FOUND: a bug at the walls (the wall clamp was not fed back to the commander copy, so the filter thought a walled drone was retreating; pairs held at 0.77 m). Fix being applied (mirrors the real commander's fence); open space loses only ~0.05 m (model limit). Scripted reference to be re-run after the fix as a new ledger row. Replay GIF/MP4s DONE in docs/media (bcae60b): 4 clips, 1280x960 MP4 + 800x600 GIF. Task 7a (filter early stop + accuracy) DONE (df8a591): no candidate passes because the plan wrote the speed-error gate as 1.6666 (T2 rounded down from 1.6666038) — OWNER RULED 16 Nov: compare that gate at its 4 written decimals (T2's 1.6666038 passes); s2.toml not edited; the 7b record states the raw value and the ruling. 7b DONE: T7 ABORTED (stopped for the wall fix), T8 PASS (1000 sweeps + check every 8, ~121k game-steps/s timed window, ~90k whole game), committed 17197a7, gatekeeper: PASS stands, wall fix confirmed (Task 7 complete, 673536f). Game config uses k=8 (f6702ca). Scripted reference re-run DONE = ledger T9 (0467628, INFO): pure half identical to T6; the 0.77 m wall floor is gone; crowded 5 v 3 still reaches 0.75–0.80 m in 3-D (being diagnosed; affects the S2b gate 'closest approach ≥ 1.0 m'). Task 9 (skrl + Gymnasium adapters, docs/PLUG_IN.md) committed c9faff3, in review; fix round: **interface change** — each drone's observation 69 → 71 numbers (zone centre relative to the arena centre at indices 69–70; central state 59 → 61), so drones can place the walls; guide fixed after a newcomer read-through. Flight-stack HYPOTHESIS for the owner: real commander runs the CBF before the keep-in fence, so a drone held against the fence lets another drone inside 1.10 m (0.86 m in the copy); not flown. To do before any training-time claim: INFO speed run with staggered game restarts. S2b plan APPROVED (all 7 owner answers in the plan). Task 8 (bag check) ran: ledger T5 = FAIL (worst leg 0.120 m/s vs 0.10; 63 % time error 0.69 s vs 0.10, caused by the held-setpoint method the plan prescribed; leg 3 is a stream dropout); record wording fixed (2d44caa), in re-review; Task 8 (bag check vs drone model) building in parallel. Linear: instruction file for the owner's Linear agent, `docs/linear/updates/2026-11-16-linear-agent-isaac-lab-pipeline.md` (72af464; copy in ~/Downloads): new project 'Isaac Lab Pipeline for NUS Strategy Training', milestones S0–S5 + side quest, NEAR-955 moved and closed, 4 S2 issues In Progress. The 4 In Progress issues are assigned to the owner, current cycle (2139410). **Owner, 16 Nov: the project's Linear snapshot lives in `svg_training/docs/linear/`, not in the root `docs/plans/`.** Synced 16 Nov: Linear project P-NEAR-31, issues NEAR-959..975 (+ NEAR-955 moved); record and snapshot in `docs/linear/` ([snapshots/2026-11-16-project-plan-linear.md](../linear/snapshots/2026-11-16-project-plan-linear.md)). S2 issues: NEAR-963 game core, NEAR-964 bag check (T5), NEAR-965 faster filter, NEAR-966 scoring + opponents (In Progress); NEAR-967 plug-in guide, NEAR-968 stand-in, NEAR-969 S2 results (Backlog). Use these ids in S2 docs. The 4 In Progress issues landed in Cycle 37, which had ended; owner: no cycles and no dates on these issues — done (second sync record in `docs/linear/`, snapshot updated). Real rosbags: only `~/flight_logs/2026-11-12/svg_20261112_094546` (goal flights, no stick) — used in S2 as a held-out check of the drone model, never to refit it.
4. Rules while building: write only inside `svg_training/`; commit finished, tested steps with explicit
   paths, never push (builder agents make no git writes; the lead commits); no `pip install`; Python is
   `~/miniconda3/envs/env_isaaclab/bin/python`; tests with `python -m pytest -q` from this folder.
   Owner rules of 15 November: every results page shows generated figures or a flowchart; plain language for
   a reader new to the topic; no change to flight or simulator code (STANDARDS §11).
5. Model use the owner prefers: the lead plans and reviews, cheaper models build. He expects usage
   limits to run out quickly, so **update the tables below after every task**, before starting the next.
6. A copy of this file is kept at `~/Downloads/claude-handoff-svg-training.md`; refresh it with
   `cp docs/claude/HANDOFF.md ~/Downloads/claude-handoff-svg-training.md` after each update.

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
agents and skills for the work. Since then S0 and S1 have been built and run (T1–T4, §0); **nothing has been trained.**

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
| A pair mask in CMU's safety filter, so that a contact tag can fly at all; and a flight safety case for deliberate contact | owner + CMU (outside this folder) | any flight of a contact policy |
| The zone's size and place in each world beyond S2 (S2 draws arena and zone sizes at random; partner zone ratio in the local file) | owner | S3 |
| Licence of the construction-site asset (an Unreal Engine asset pack exported by the lab; no licence file found) | owner | before anything made from it leaves the lab |
| What the real drone senses its surroundings with: a known map, or an on-board range sensor | owner | S3 |
| Control level for contact tags: stay at velocity, or add a final-approach skill at thrust and body rates | owner, on the S2 numbers | after S2 |
| The real flight with planned pushes (list: [../S1_RESULTS.md](../S1_RESULTS.md#what-the-owner-needs-to-do-next)) | owner | the `real` parameter set's run of record |
| Metres per partner unit and seconds per step (NUS); hangar flying space in metres | owner + NUS | a partner-rules result quoted in metres |
| What a drone may observe about others (full state, or shared with delay and loss) | owner + partners | S2 |
| How a drop-out is simulated | owner + partners | S4 |
| Written velocity contract with NUS and CMU (Linear NEAR-874, NEAR-875) | owner + NUS + CMU | use 2, S5 |
| Tell UPenn and NUS about this pipeline; UPenn already has an Isaac Lab environment | owner | early |
| Access to a training workstation (RTX 5090, RTX PRO 6000 or RTX 6000 Ada); its driver and Isaac versions | owner | S0 on that machine |
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
3. S0 and S1's build tasks are done (§0, [../S1_RESULTS.md](../S1_RESULTS.md)); no S1 gate on the drone model has passed yet. Next is the S2 plan, for the owner's
   approval; then build it with `train-implementer`, test first, and have `train-gatekeeper` read the record.
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
