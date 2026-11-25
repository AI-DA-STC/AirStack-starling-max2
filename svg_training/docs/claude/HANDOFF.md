INTERNAL · the lab's AI-assistant hand-over notes: where the work stands, what was decided and what waits on whom, newest entry first (§0); not needed to read or run anything · start at [../../README.md](../../README.md); the pages for readers: [directory](../README.md)

# Claude handoff: svg_training (vectorised training pipeline)

> **How to use this file.** Read it at the start of a session, after [../../CLAUDE.md](../../CLAUDE.md).
> §4 is the current state, §5 is what is waiting on people. Update both before you stop.
> Last updated: 25 November 2026 ~14:45, on the home RTX 5090 (afternoon: route 3 build has the owner's word, R42–R45; before: ~14:00 rulings R36–R41, execution workflow v3, its design review done and folded in; before: ~12:10 morning: clean-up, automatic 3-D clip hook, learner v2 first; before: night: L3–L6 pipeline check done, both routes PIPELINE WORKS; before: 24 Nov ~18:20 late day: rulings R29–R33, L2.6 and the figure-eight check, L3 slice 2 merged; before: ~13:30 day: rulings R24–R28, AirStack set up, L1.4, L1.5, L2.5 done, L3 note v2; before: ~07:30 night run: L1 reads, L2.1/L2.3/L2.4; before: 23 Nov ~13:30 documentation clean-up), worktree `~/AirStack-starling-max2-dev` on branch `development`.

## 0. Resume here (for a new session or another Claude account)

Everything needed is in this folder; nothing depends on the previous chat. Claude's user memory (`~/.claude/…`) and
the private NUS workspace (`~/ma_skills-self-play/`, 5090 only) do **not** travel with git: if this file and a memory
note disagree, this file wins.

### 25 November 2026 ~14:45 — RTX 5090 AFTERNOON: ROUTE 3 BUILD HAS THE OWNER'S WORD (R42–R45) (read this first)

- **Owner, ~14:40: "1. go 2. confirm 3. yes 4. yes"** (DISCUSSION §16, R42–R45): the build of route 3's LS1 and LS1.4
  starts; the lead's reading of R39 is confirmed (no cap; jobs state their hours; a job above 5 GPU-h announced; M1
  writes 200 GPU-h for the route, 4.0 for LS1.4); self-play: pool entry early, pilot after LS1.4, the full stage
  before LS2 only if the pilot shows room; the route page, figures and slides are redrawn for R39–R41. The owner
  pushed `development` at `f6d90924`.
- **In work (started ~14:45):** (1) the task plan rewritten from the workflow v3 and the two review reports (an Opus
  agent, worktree `~/AirStack-starling-max2-ls1plan`, branch `ls1-taskplan`), then one Sonnet reviewer, then merge M1
  (worktree and branch named in the task plan); (2) the route page, figures and slides redrawn (a Sonnet writer,
  worktree `~/AirStack-starling-max2-lsroute`, branch `ls-route-page`). Both fast-forward into `development` after
  their checks. **The plan's old Tasks 1–7 (LEARNED_SKILLS_BRIDGE_PLAN.md) are not to be built as written.**
- **Still the owner's:** the LS1 limits and the LS1.4 margin (R38), after the calibration read LS1.5; the held-out
  scripts, with the self-play note. Nothing on the GPU before the gate file is hashed.
- **Main track:** route 3, stage LS1, build · **Side track:** the route page redraw (R45).

### 25 November 2026 ~14:00 — RTX 5090 AFTERNOON: ROUTE 3 (LEARNED-SKILLS ROUTE), RULINGS R36–R41, WORKFLOW v3, DESIGN REVIEW (read this first)

- **Owner's rulings (DISCUSSION §16):** R36 LS1 1.0 GPU-h; R37 "build LS1 now, lets try route 3 first" (the build
  session on Opus 5.5, high effort, a multi-agent workflow); R38 the owner sets the LS1 pass limits on the lead's
  advice, after a noise-floor read; **R39 no GPU-hour cap on route 3, the aim is a useful policy** (the lead's reading
  of its scope is PROPOSED and not confirmed: until it is, GPU launches stay inside R36's 1.0); **R40 the heads are
  trained again on the skill network, both sides** (job group LS1.4, two seeds per arm); **R41 self-play brought
  forward** (LS1 → LS1.4 → LS2 → self-play → LS3) and the go for the design review.
- **Workflow v3** ([LS_EXECUTION_WORKFLOW.md](../../ste_learning/drafts/LS_EXECUTION_WORKFLOW.md)): LS1 and LS1.4 job
  by job; LS2, self-play and LS3 as outlines; section 2 sets route 3 against PLAN §1 (what a useful policy still
  needs: a pool that can hold saved teams, a held-out set, the shared actor for drone loss, tier 2). What a builder
  must not miss (section 8): the launcher refuses `--task LS1.x` until `ste/config.py` `TASK_IDS`,
  `configs/ste_learning.toml`, PLAN §9 and `tests/test_ste_config.py` carry the LS1 tasks; `scripts/ste_l5_clips3d.py`
  cannot draw an LS1 team; the equivalence read runs on the CPU; the noise-floor read comes before the limits; the
  skill network file is per team. Where the workflow and the plan (LEARNED_SKILLS_BRIDGE_PLAN.md) differ, the
  workflow wins. Corrected from what the owner was told: a saved team cannot be a training opponent with today's code
  (`ste/pool.py` takes script names only), so self-play is a new build.
- **Design review DONE (~14:30, two Sonnet reviewers, read-only; the lead checked their file references):** one
  blocker and fourteen further findings, all folded into v3 (its section 9). The blocker: the training driver's control
  "untrained team equals its first skill" compares with the script, so under a skill network every head-training job
  would end with exit 6 (`scripts/ste_exploit_l012.py:380-388, 921-933`); the driver is now in the change table (M4).
  Also: `skills_meta` and `learner_table` must stay byte for byte for scripts; the reload check needs a branch for a
  route 3 team; the gate read is paired (games changed, not only net wins) with near-miss controls; the LS1.4 rule is
  "no drop beyond a margin", Strike read on run 0; `opponents/scripted.py` is frozen from the first distillation on.
- **Order of work:** **the owner's word for the build** → M1 → the calibration read (LS1.5) → the owner sets the limits
  and margins → gate hashed → M2, M3 → LS1 runs → M4 → LS1.4 runs. No code and no run before that word.
- **Nothing built, nothing run, 0 GPU-h.** Documents only; the short document check ran, not the full suite.
- **Not changed, waiting on the owner's yes:** the reader page LEARNED_SKILLS_ROUTE.md, its figures and the slides
  still show the order LS1, LS2, LS3, LS4 (its "Where it stands" table was brought up to R36–R38 in `a133ba25`).
- **Main track:** route 3, stage LS1, design review done, waiting on the owner's word for the build · **Side track:** none. The learner v2 note follows (R37).
- **Waiting on the owner:** the confirmation of the reading of R39; then the word for the build; later the LS1
  limits (R38) and the held-out set. Unchanged: NEAR-962, the Crazyflie commanded gaps.

### 25 November 2026 ~12:10 — RTX 5090 MORNING: CLEAN-UP, AUTOMATIC 3-D CLIP HOOK, OWNER CHOSE LEARNER v2 FIRST

- **Owner's answers to the pipeline-check read:** upgrade the learner before choosing a route ("yes"); the 3-D clip hook
  next. Next work: the learner v2 note (observation v0.3, attention encoder, shared actor, team critic, league after NUS's
  archive self-play) brought to the owner before code; then a second short check on v2 from the 17.7 GPU-h left of the
  20 (announced with its cost first). NEAR-962 is a gamepad data flight for the drone-model fit, needs no policy; L7 has
  nothing to decide now (D4 open).
- **Automatic 3-D clip hook merged** (branch `clips3d-hook`, `ste/post_run.py`): `ste_job.py launch` of the training
  driver as a run of record (not `--pilot`, `--run0`, `verdict`) starts `scripts/ste_l5_clips3d.py` as its own recorded
  job on exit 0 + complete run; opt out `--no-post-clips3d`; state in `<run>/videos3d/HOOK_STATUS` and `status`
  (`clips3d=launched|pending|skipped|done|failed|missing`); retry `ste_job.py post-clips3d --run-dir <run>`. QC one
  reviewer (ACCEPT WITH FIXES, all fixed). Not yet run on the GPU with a real run. Wait for `clips3d_<job>` before a
  solo job (its preflight would exit 11).
- **Clean-up (owner):** 45 worktrees and 52 local branches removed; GitHub branches `docs-5090-setup`,
  `nus-port-phase2`, `docs/runbook-follow-through` deleted by the owner. All unique run data (1,849 files, ~3.2 GB,
  incl. T79's ceiling and the NUS Phase 4/5 runs) copied by checksum into this worktree's `runs/` at the same paths
  (one clash under `runs/_from_worktrees/`). Only `~/AirStack-starling-max2` (`main`) and `-dev` (`development`) remain.

### 25 November 2026 ~05:00 — RTX 5090 NIGHT: L3–L6 PIPELINE CHECK RUN END TO END, BOTH ROUTES PIPELINE WORKS (read this first)

- **Owner's go (night of 24–25 Nov): "go 1 to 4"** (the L3–L6 pipeline check; the three flaky tests; the L2.6 tier-2
  clips; status + this entry) **and the 3-D clips of every L5 run; R34** (bug re-runs from the unallocated hours, cap
  2 GPU-h, announced; a real result never re-run) recorded in DISCUSSION §16.
- **The pipeline check** ([record](../../records/2026-11-25_ste_l3_l6_pipeline_record.md), T73–T89, INFO, two reviewers):
  both routes **PIPELINE WORKS** (`runs/2026-11-25_ste_l61_read_r`). 2.291 of 20 GPU-h. Skills run 0 mark re-set by the
  pre-registered rule from the CPU ceiling (604 → 0.554; oracle check PASS); skills run 0 PASS 644/1000. The skills Strike
  run's own driver word is INCONCLUSIVE (176 v best script 192 v guard_mark_edge; all controls PASS; a real result, not
  re-run). Guard: velocity above skills on the pooled row (0.963 v 0.895). Strike: pooled rows level.
- **Built and merged tonight:** `scripts/ste_l3_run0_ceiling.py --oracle-check`; `scripts/ste_l5_clips3d.py` (3-D clips of a
  finished L5 run, launched by hand that night (automatic since ~12:00); 68 clips over six runs in `runs/2026-11-25_ste_l5_*/videos3d/`); the reader accepts a pilot that ran
  before the fill step (`026fc00c`); the suite-flake fix (SIGINT ignored in background-launched suites). Each had one
  reviewer.
- **L2.6 tier-2 clips** rendered on the fixed path: both tiers agree game for game; T71's record updated.
- **R34 use:** 0 GPU-h. Launch errors of ours (CPU only): four CPU jobs launched one folder level too high (re-launched,
  byte-identical); the full suite's first run tripped on a merge made while it ran (`test_timing` read HEAD twice).
- **Rules learned:** launch L4.1/L4.2/L6.2 with `--run-dir` equal to the script's `--out` (the reader reads `exit_code`
  beside the output); never merge into `development` while the full suite or a run is going.
- **Owed (small, no ruling needed):** (the automatic post-run 3-D clip hook: done ~12:00, entry above); the stale "0.90" in the error string of
  `scripts/ste_exploit_l012.py` (~line 188; shown only when a skills gate file has no mark; left so the driver's code
  stamp did not change mid-route); `scripts/ste_job.py status` prints only `budget_l1_l2`, not `[budget_l3_l4_l5_l6]`
  (tonight's L3–L6 hours were summed from `runs/shared/gpu_hours.log`). The ceiling of record and its oracle check
  (T79) now live in the dev worktree's `runs/`: the run0mark worktree was folded in and removed on 25 Nov (owner).
- **Main track:** L3–L6 pipeline check done · **Side track:** the automatic 3-D clip hook (done ~12:00, entry above).
- **Waiting on the owner:** the read of the pipeline check (which route(s) next, budget; L7 is the owner's gate); the
  planned-pushes flight NEAR-962; the Crazyflie commanded gaps. Nothing is running.

### 24 November 2026 ~18:20 — RTX 5090 DAY, LATE: RULINGS R29–R33, L3 SLICE 2 MERGED, FLIGHT LOGS READ (read this first)

- **Rulings (owner, ~15:35 and ~16:25):** R29 1v1 training skipped; R30 "Team strategy, with individual drone skills which
  can adapt to the opponent's strategy" (two-level choice: a team head and a drone head); R31 P2 option B deferred (even
  split stays the default); R32 landing off in the L3–L6 pipeline check; R33 no flight with the filter off: the
  planned-pushes flight flies one drone alone with the filter on. Text: end of
  [DISCUSSION](../../ste_learning/DISCUSSION_2026-11-19_20.md).
- **L2.6 done (T71 INFO, 0.145 GPU-h, two reviewers):** [record](../../records/2026-11-24_ste_l26_tier12_record.md). Tier 1
  agrees with tier 2 for scripted play at 1.6 m and at 1.15 m without option B (40 of 42 cell readings); option B at
  1.15 m lowers mark_edge v straight on both tiers.
- **Side task CLIP-T2 done:** the tier-2 clip script drew its starts on CUDA; fixed (`record_games` `starts=`); the L0.13
  clip caption is corrected; run numbers are unaffected.
- **Flight logs (owner, 24 Nov):** [survey](../notes/2026-11-24_flight_logs_survey.md): the figure-eight flight is a
  held-out check only; the planned-pushes flight NEAR-962 is still needed. Figure-eight check (T72 INFO, two reviewers,
  [record](../../records/2026-11-24_fig8_heldout_record.md)): at 2–3 m/s tier 1's exploratory model flies about half to
  two thirds of the real speed, likely its fitted acceleration limit (1.72 m/s²) against about 2.6 m/s² measured; game
  speeds are inside the fit range, nothing re-scored; NEAR-962 should add fast pushes and turns reaching 2–4 m/s².
  Crazyflie [summary](../notes/2026-11-24_crazyflie_reports_summary.md) (one reviewer): lag about 0.56 s with the PID
  controller v 0.08–0.10 s with Mellinger (a co-occurrence); commanded gaps below the show's own 0.80 m separation
  minimum in 73 of 78 close events.
- **L3:** slice 1 merged earlier; slice 2 merged ([design](../../ste_learning/drafts/L3_SLICE2_DESIGN.md)): two-level
  learner `TwoLevelIPPO`, per-head ratios, entropy and KL, p(free) = 0.5 start, checkpoint skill lists, driver wired,
  skills pilot wired, held-command arm script; QC once per step. Next: step 4b (run 0 for the skills route: skills Strike
  v guard_parked_centre, PASS at 900 or more of 1,000; lead's call) on branch `l3-run0`, then slice 3 (absent-drone mask,
  opponent pool, tier 2 wiring), then the pipeline-check pilots.
- **Tests and budget:** full suite on `fa549048`: 2,672 passed, 1 failed (a literals rule), fixed in `9a982c69` and
  re-run. budget_l1_l2 (phases L1 + L2): used 4.439 of 13.0 GPU-h (own rows 0.899, carried 3.540)
  (`scripts/ste_job.py status`).
- **Main track:** L2 done; L3 slice 2 merged, run 0 for the skills route next · **Side track:** none open.
- **Waiting on the owner:** the planned-pushes flight NEAR-962 (one drone alone, filter on, single-axis pushes from rest
  at 0.25–1.0 m/s plus a few fast pushes and turns; record `/svg/drone_N/teleop_command`; note the config, the PX4 build
  and `MPC_XY_VEL_MAX`); a look at the Crazyflie show's commanded gaps below its own 0.80 m minimum before the next
  Crazyflie flight. No other decision is open.

### 24 November 2026 ~13:30 — RTX 5090 DAY: OWNER RULINGS R24–R28, AIRSTACK SET UP ON THE 5090, L1.4, L1.5 AND L2.5 DONE, L3 NOTE v2 (read this first)

- **Rulings (owner, ~11:00):** R24 1v1: "what do u recommed" (a question: R20 hold stands; lead recommends skipping 1v1
  training, the scripted 1v1 stays the demo as ruled at G0; or a free CPU screen of flyable variants); R25 set AirStack
  up on the 5090; R26 L3 two-route design and skill list approved; R27 PLAN.md updated (two routes, L3–L6 pipeline check
  20 GPU-h); R28 touchdown 0.15 m fixed. DISCUSSION §16; commit `c1f268a6`.
- **Host changes on the RTX 5090 (R25), outside git:** containers `isaac-sim`, `airstack-robot-desktop-1`,
  `airstack-gcs-1` created (`./airstack.sh up`, left up and idle, no GPU held); robot workspace built in the container
  (`bws`, 59 packages); `tools/sim.sh setup` set `core.hooksPath = tools/git-hooks` in the shared git config (the
  repository's pre-commit hook now runs on every worktree's commits: never bypass it); empty gitignored folder
  `AirStack/robot/ros_ws/bags`. Already there from earlier: NatNet SDK, the `airstack` shell function, `omni_pass.env`,
  `user.config.json`, the robot image. `tools/sim.sh doctor`: 21 OK, 2 WARN (no `pyulog`, no `obs`), 0 FAIL. No AirStack
  file, config or drone parameter edited.
- **L1.4 done (T68 INFO):** 36 of 36 velocity steps in the AirStack simulator ([record](../../records/2026-11-24_ste_l14_steps_record.md); corrected: heights come from the simulator's PX4 clock, about 2.5x, not a descent limit), logs in
  `runs/2026-11-24_ste_l14_steps_r3/` (568 MB, not in git; L1.5 needs it: copy it to the laptop if L1.5 moves there).
  `scripts/record_steps.sh` had never run; two fixes (`f7e87089`, `452b260d`, each reviewed once): our commander now
  launches with `use_mocap:=false`; the guard reads published topics only, leaves out the simulator's MAVROS, and fails
  closed on an unreadable topic list (also after the flight: a missing robot container then exits 67 without `down`;
  bring it down by hand). Run it from this worktree with `SVG_STACK_REPO=~/AirStack-starling-max2` (the containers mount
  the live clone).
- **L1.5 done (T69 INFO, 0.012 GPU-h, two reviewers):** [record](../../records/2026-11-24_ste_l15_compare_record.md). Tier 2
  with the AirStack simulator's SIM-ONLY airframe is within the simulator's per-step spread in 187 of 189 readings; the
  0.05 s delay and the estimate error are not resolvable here (~0.1 s resolution). The L1.6 decision still needs L1.3 and
  NEAR-962.
- **L2.5 done (T70 INFO, 0 GPU-h, 46 min CPU, two reviewers, all 12 controls):** [record](../../records/2026-11-24_ste_l25_screen_record.md).
  Parked-Guard risk not seen with scripted Strikes (still Guard 432 v mark_edge ~805, worst cell); the tag raises the
  parked hold in 23 of 24 cells. Option B is not testable at 1.6 m with scripted play: with the tag off it changes 11,429
  of 12,000 games and removes most parked-Guard blocking (331 to 171, 752 to 86); it is 5.3x slower on the CPU in long
  games. Landing changes 2 of 30 cells, both against strike_low; vertical not fitted.
- **L3 note v2** after two design reviewers and the advisor (`b651a05f`, `ste_learning/drafts/L3_TWO_ROUTES_DESIGN.md`):
  no previous-choice slot, per-slot networks, closed-loop skills under a 0.6 s choice plus a held-command arm, both
  routes train against the same opponent pool, masking list, export needs, first slice.
- **Tests and budget:** full suite 2,458 passed on `3103d4d0`; a second run on `d01bf39e` in progress. Budget
  budget_l1_l2: 4.271 of 13.0 GPU-h (`scripts/ste_job.py status`).
- **Next (no ruling needed):** L3 first slice build (tier 1: skill dispatch + categorical head + tests); L2.6 spec (tier 1
  v tier 2 under the new rules).
- **Waiting on the owner (one-word answers):** 1. 1v1: skip (lead) / screen variants. 2. L3 choice per team (lead) / per
  drone. 3. P2 option B: not ready to rule (L2.5 could not measure it at 1.6 m; its convergence gate in the PLAN L2 row
  has no record yet; the drones fly the even split today and option B in flight needs the CMU proposal P6; the L2.1 wall
  shortfall 0.39 m v 0.97 m is not shown by L2.5); lead proposes keeping the even split as the default and offering a
  1.15 m CPU screen (0 GPU-h) when the 1.15 m main training nears. 4. P7 landing: lead proposes landing off in the L3–L6
  pipeline check (needs observation v0.3 so live drones can see a landing drone; v0.3 comes to the owner with the main
  training); drawn sizes and drop-outs not screened and not asked now.

### 24 November 2026 ~07:30 — RTX 5090 NIGHT: L1 READS DONE, L2.1/L2.3/L2.4 BUILT (read this first)
Owner rulings of 24 Nov (DISCUSSION §16, R19–R23): build both routes (pure RL, mixed) and compare; L1.9 screen first,
training after the owner's word; L1.5 yes; process scaled (two reviewers only where a decision or reader page depends on
it); L3–L6 = pipeline check, cap 20 GPU-h. Models by role in CLAUDE.md (Opus 5.5 main, Fable 5.2 advisor at forks,
Sonnet agents for checking). Done (records reviewed by a numbers and a completeness reviewer, fixes applied; full suites on the CPU; after the merges, on the GPU: the touched tests 230 passed, the L1.10 Guard score matrix
replayed on merged development with every cell identical (19 controls PASS, 0.016 GPU-h), and the Isaac-marked tests
7 passed + 1 expected failure, as T62):
T65 L1.7 speed (estimate error ≈1–3.5 % cost); T66 L1.9 1v1 screen (1v1 Guard-lopsided: moving Guard scripts hold 100 %
at 1.6 m, 84–90 % at 1.15 m; training held, R20); T67 L1.10 tag drawn 1.5–1.7 m (run 0 PASS; Guard above the scripts v
4 of 6, Strike v 2 of 5; no error effect; not distinguishable from T46; players in ste_provisional). Built, QC-reviewed,
full suite at each merge, all off by default: L2.3 landing (`[landing]`; floor shortfall 0.95–1.05 m), L2.1 option B
(`[filter] share`; wall shortfall 0.39 m tier 1), L2.4 drone loss and drawn sizes (`[team_size]`; study file only;
the learner must mask absent slots before any drawn training). L3 two-routes design note drafted (no code). **Blocked:**
L1.4/L1.5: AirStack has never been set up on the 5090 (no built ros_ws, no containers; `airstack.sh setup` is outside
the approved exception): owner to choose 5090 setup or the laptop. Ledger budget_l1_l2 4.260 of 13.0. Nothing runs on
the GPU now. Next: owner decisions (STATUS "Waiting on you"), then L2.5/L2.6 INFO runs and the L3 build. Worktrees
-l2, -l21, -l24 are merged branches (can be removed); -l2 had a symlink trap (runs/nus_port linked from another
worktree makes the NUS phase-4 tests refuse to write: do not link runs/ across worktrees).

### 23 November 2026 ~13:30 — DOCUMENTATION CLEAN-UP: STORY PAGES FOR ANY READER, EVERY PAGE LABELLED, SUPERSEDED PAGES ARCHIVED (read this first)
Owner (23 Nov): "use that story line and further polish up the readability, content and flow. dont have to indicate nus
or lab lead just make it generic for any reader" and "clean up the other mds. every md must be directed somewhere and
the reader must know what each md is for. outdated mds or contents can be archived." Then: "i only asking u to polish
up documentation": the queued L1 GPU work was **not** started (an agent had begun preparing L1.7; stopped before any
launch, 0 GPU-h, nothing committed). Documentation only; no code changed.
Done on branch `docs-cleanup` (worktree `~/AirStack-starling-max2-docs`), in four batches by three agents and the lead:
(1) story pages: `README.md` generic opener and five-row "Where to go" table, §6.3 as a three-column table, the five
NUS questions dated with Q4 marked as predating STE's game; `docs/OVERVIEW.md` intro in two paragraphs and a Terms
table; `ste_learning/README.md` is the reader half only, its process sections moved verbatim to
`ste_learning/HOW_THE_WORK_RUNS.md` and the L0 step-by-step and review sections to `ste_learning/L0_HISTORY.md`.
(2) every page's first line: label (READ, REFERENCE, LAB OPERATIONS, INTERNAL, ARCHIVED) · what it is for · where to go
next (48 pages; THE_GAME trimmed to the pipeline, rules live in OVERVIEW; NUS port pages dated to 20 Nov; G0_DECISION no
longer DRAFT; TRAINING "what trains today" box current; NUS_PORT_REPORT §12 heading now "(paused 20 November 2026)",
its anchor followed in three pages). (3) `docs/README.md` rewritten as a directory grouped by reader goal with the
history to 23 Nov. (4) archived with indexes: seven finished build plans and the S2 design → `docs/archive/`, the six
specialist drafts → `ste_learning/archive/`, the overview page's design and plan → `docs/archive/`; `docs/specs/` and
`docs/superpowers/` are gone; `ste_learning/drafts/README.md` indexes the live specs; every citation follows (records
and two pinned TOML comments were left as they were, see commit 18d0899a's message). Decision 3 items: STANDARDS §2 tag
rule opens with the two tags; root `CLAUDE.md` `svg_training` row at gate G0 (approved exception). New rules in
`CLAUDE.md`: pages written for any reader; documentation-only merges with file moves run only the touched test file.
Checks: link reachability 171 pages, 0 orphans, 0 broken inside `svg_training`; docs check 13 PASS · 0 FAIL; short
document check (privacy, bundle and tie tests plus every test file naming a changed page): 228 passed, 4 skipped. Reviews:
the newcomer walk from the root README ran (PASS on the root README, overview and front page with fixes; the learning-track
page and the status link failed as a newcomer destination; its ten fixes applied, commit a3d9bc13). **The numbers review
and the flow/contradiction review did not run: both reviewer agents stopped on the account's 5-hour usage limit (resets
14:10 +08:00) and the owner reported 3 % of the weekly allowance left. They are owed: run them first when usage allows,
before any further change to these pages.** Each agent's own checks ran (heads: 48 first lines, 0 form problems; archive:
every changed link resolves, anchors included).
Not done: the two pinned TOML comment paths (`configs/s1.toml:2`, `configs/nus_phase4.toml:1`) still name the old plan
paths because their sha256 is recorded; `docs/linear/updates/…isaac-lab-pipeline.md:12` is a posted copy and keeps its
old path. Training: nothing running; L1.7 speed re-measure, L1.9 and L1.10 still queued, start only on the owner's word.

### 23 November 2026 ~12:40 — READING FLOW FROM THE ROOT README; MAIN BROUGHT UP TO DEVELOPMENT (read this first)
Owner (23 Nov): update the root README, `svg_training/README.md` and `ste_learning/README.md` so readers starting at the
root README find their way. Path: root README (banner and two "I want to…" rows) → `docs/OVERVIEW.md` (rules and
results) → `svg_training/README.md` ("Where to go" table; the whole story) and `ste_learning/README.md` (plan,
decisions, link to the status page). The learning-track page now says real flight is Crazyflies first, then the
Starling 1v1 (R12), and marks the L0 sections as history; PLAN rows L1 and L8 follow it. Two on-path stale lines fixed
(THE_GAME arena, WHAT_WE_FOUND tag; separate commit). Reviews: facts (no wrong statement), newcomer from the root
README (FLOW PASS: four questions, one click each). **Owner chose option B: `main` was fast-forwarded to `development`
on 23 Nov ~12:40** (GitHub shows `main` by default; it stood at 20 Nov). `main` and `development` are the same commit
until the next training commit; training work still lands on `development`.

### 23 November 2026 ~11:50 — README BROUGHT UP TO DATE WITH GATE G0; NEW RULE ON DOCS-ONLY MERGES (read this first)
Owner (23 Nov): "bring those sections up to date". `README.md` at a glance, §1, §3, §6 (new 6.3) and §7 now tell the story
through gate G0 and point at `docs/OVERVIEW.md` for the numbers; the story figure's last box and footer are redrawn; the
GLOSSARY "Tag" row gives both meanings (separate commits, droppable). Reviews: numbers (no wrong statement), rules and
contradictions (fixed), a scoped re-check and a newcomer re-read (all three questions pass). Not changed, owner to
decide: the five questions to NUS in §7 (Q4 "no drop-outs" no longer fits STE's game), `THE_GAME.md` "3-D worlds" and
`WHAT_WE_FOUND.md` "a tag is a separate track", STANDARDS §2's first line "A tag is physical contact". **New rule (owner,
23 Nov): documentation-only merges skip the full suite** and run the short document check (CLAUDE.md, standing rules).

### 23 November 2026 ~11:20 — OVERVIEW PAGE DONE ON THE RTX 5090 (read this first)
`docs/OVERVIEW.md` built (plan Task 1), 80 lines; link check `broken: 0`. Reviews: Task 1 by two reviewers (numbers v
records: no wrong number; reader rules and spec coverage), Tasks 2–3 by one (READY), a final review on the strongest
model (no wrong number; one fix wave applied), a scoped re-review of that wave, and the newcomer acceptance test
(ALL PASS: each of the three questions answered on OVERVIEW, one click from README, 8–24 lines). Departures from the
design, each from a review: the 1.15 m caveat uses the flight-log record's figures (about 1 cm hover sigma, 2.5 cm
moving spread), not the design's "3–10 cm", which came from a different measurement; T61's closest tag (1.106 m) is
left out because it comes from the 0.30 s delay stress test; a Terms paragraph defines the labels; working values are
marked. **Owner's call, not done:** `docs/GLOSSARY.md` "Tag" row still says tags exist only in a separate track, and
README's body (at-a-glance, §3 "both sides play the same game", §6–7 lines) still predates G0; the design left README
bodies for a later change with the owner's OK. Next on the 5090: the 07:15 entry (carry 0.73, L1.7 speed, L1.9 → L1.10).

### 23 November 2026 ~10:15 — OVERVIEW PAGE FOR THE LAB LEAD: HALF BUILT (SUPERSEDED by the ~11:20 entry above)
**What and why.** The owner's lab lead wants the game rules and the main learnings (NUS port + STE track) on one page.
Run through the `quality-change` process: panel of four (technical writer, flight-test engineer, engineering manager,
newcomer reader; positions + vote), builder check, **design APPROVED by the owner 23 Nov**
(`docs/archive/2026-11-23-game-overview-design.md`, page name `docs/OVERVIEW.md`), plan
`docs/archive/2026-11-23-game-overview-plan.md` (three tasks). Owner asked to stop the laptop build and finish on
the 5090.
**Done (committed with this entry, not yet reviewed):** plan Tasks 2 and 3: dated "Superseded on 22 November 2026"
notes on README §6 and §7, `docs/NUS_PORT_REPORT.md` §12 and `docs/WHAT_WE_FOUND.md`; the THE_GAME tag sentence; one
line under README's **For** paragraph; first row of the `docs/README.md` Read table; `ste_learning/README.md` line 1
no longer says "the page to read first". **These seven links point at `docs/OVERVIEW.md`, which does not exist yet:
they are broken until Task 1 lands.**
**To do on the 5090, in order:** (1) Task 1: write `docs/OVERVIEW.md` per the plan and the spec's "The page" and
"Builder check, answers" (every number checked against its record; evidence = the records named there); (2) plan's
link check → `broken: 0`; (3) one reviewer per task (numbers v records; reader-page rules in `CLAUDE.md` "Git facts
that bite", last bullet; FIXED-only STE values), fixes; (4) final review on the strongest model, one fix wave; (5)
newcomer acceptance: from `README.md`, the three questions (rules now; why STE left NUS's policies; what STE's own
training showed) each ≤ 60 lines and ≤ 1 click; (6) commit by path, "Ready to push". The 07:15 entry below still holds
for the training work (carry 0.73, L1.7 speed re-measure, L1.9 → L1.10).

### 23 November 2026 ~07:15 — LAPTOP NIGHT 2 DONE; RTX 5090 PICKS UP (read this first)
**Merged to development tonight (each built, two code reviews, full suite at merge):** L1.1b (Gauss–Markov estimate
error in tier 2), L1.3 first fit (T63, EXPLORATORY: hover position ~1 cm/1.2 s, velocity ~2 cm/s/1.3 s, attitude ≤0.15°;
mocap age 6–9 ms), Isaac checks (T62: 7/7 pass, no measurable cost), L1.7 (estimate error in tier 1, off by default,
commander_reads switch), L1.8 (T64: T46 players on tier 2 — simulator shifts −33..+47 per cell; with the measured error
no change detected; 2× error moves Strike v parked Guards 351→399), L1.9/L1.10 tooling (spec
ste_learning/drafts/L1_9_10_SPEC.md; caps L1.9 1.6, L1.10 1.7 — moved from L1.8/L1.6/L1.15 unused, announced).
**On the 5090, in order:** (1) pull `development`; `scripts/ste_job.py carry --gpu-h 0.73 --note "laptop 2026-11-23"`
(laptop L1 hours 3.533 minus the 2.808 already carried = 0.725, rounded up); (2) L1.7 speed re-measure on an idle GPU (laptop numbers were
under load); (3) L1.9 then L1.10 exactly as the spec's launch order (step 1 CPU screen; step 2b: if the 1v1 parked
Guard v straight cell shows ≥ 950 reaches, change run 0's opponent first); L1.9's cap leaves ~0.1 GPU-h for its tier-2
check — announce any move first; (4) L1.4/L1.5 need an AirStack-simulator session with the owner. Follow-ups listed
in WORK_BREAKDOWN: L1.1c (second-order error), L1.7 review lows, z-sign ULog test, a duplicate-carry guard (5090
suggestion). T45's per_game.npz must be copied to runs/2026-11-21_ste_l014/response/ for the L0.3 tests on a fresh
machine (ste_provisional/README.md now says so).
Laptop run folders archived in ~/AirStack-starling-max2/svg_training/runs/ste_archive/{l11b,l13,l17,l18,l19}/ (laptop only).

### 22–23 November 2026 night — L1 FIRST NIGHT, HAND-OVER TO THE RTX 5090 (SUPERSEDED by the 23 Nov ~07:15 entry above; kept for history)
**Start on the 5090:** pull `development`; `mkdir -p runs`. **The carry of the laptop's 2.81 GPU-h was DONE on the 5090
on 23 Nov ~02:00 (ledger 2.81 of 13): do not run it again** (the tool has no duplicate guard; see the 23 Nov entry below).
Then in order: (1) **L1.0** 5090 checks (TEST-F2b, L09-5090, drills, 5090 suite); (2) **L1.1b** (WORK_BREAKDOWN: model
the estimate's error, not a transport delay; never delay attitude; pass the game seed to the noise; tests first, two
code reviews); (3) **Isaac check re-run** of L1.1/L1.2: `scripts/ste_job.py launch --task L1.1 --name ste_l1_model_check
--run-dir runs/<date>_ste_l1_model_check --min-s 120 --gpu-h <h> -- <python> scripts/l1_model_check.py --run-dir <same>
--cap-h <h> --headless` (the laptop run stopped at the 0.2 cap: 6 isaac tests passed, 1 failed on the world label — fixed
by the commit "isaac test accepts the IsaacWorld label", not re-run, so the delay/noise/agreement checks have not run on Isaac; Isaac cost 11.1 %;
torch-twin and tier-1 speed parts not run; L1.1 cap 0.2 is used: move hours with a "why" message to the owner first);
(4) L1.3/L1.4 when the AirStack simulator is free (P5 approved, laptop or 5090).
**Done tonight (all reviewed by two agents):** side track T57–T61 (records + ledger + figures docs/figures/ste_l1_side,
clips docs/media/ste_l1_side); DISCUSSION §15 = the agreed reading and plan (two panellists); main track L1.1/L1.2 built
(models/estimator_effect.py, drag in starling_airframe/physics_drone, params/starling_physics_v1.toml all OPEN at 0).
Trained players for the 5090 in `ste_provisional/players/` (T46, T52, T54, T55, L1.11, L1.13 arms A/B). Laptop run
folders archived in `~/AirStack-starling-max2/svg_training/runs/ste_archive/l1side/` (laptop only).
**Side-track rule (owner, 22 Nov):** additions allowed, each announced with why + GPU-h + where the hours come from; every
status opens "Main track · Side track". Next side-track step if any: a second seed of the clamped 1.15 m read / arm A
(≈0.5 GPU-h), announced first. **L1 caps:** L1.1 0.2 (used), L1.6 0.1, L1.9 1.6, L1.10 0.9, L1.11 1.2, L1.13 2.1, L1.14
0.3, L1.15 0.3; sum 9.1 + L2 3.9 = 13.

### 23 November 2026 ~02:45 — RTX 5090: L1.0 MACHINE CHECKS DONE (speed part deferred)
Branch `ste-l1-0` (merged into `development`); record [records/2026-11-23_ste_l10_5090_checks_record.md](../../records/2026-11-23_ste_l10_5090_checks_record.md), two reviewers (numbers, completeness).
**The carry of the laptop's 2.81 GPU-h is DONE on the 5090 (ledger 2.81 of 13): do not run it again.** TEST-F2b
passed (AVX512 key confirmed); L09-5090 closed: AVX512 record added to `tests/data/game_tag_off_golden.json` from
`5ebac526` (the L0.9 commit's parent; `dec9d276` is not in the shared history), current game equal to it natively; closed
L0 refuses launches (exit 2); wake-up and resume drills as expected under `--task L1.0`; 5090 full suite 2,213 passed,
54 skipped, 0 failed; GPU-only tests with the GPU visible 203 passed. Deferred with the speed re-measure (laptop lead):
A8's "three tier 2 seeds fit 32 GB" and the 16,384-game physics check. For the laptop lead: T45's per-game file must be
copied to `runs/2026-11-21_ste_l014/response/` for the L0.3 tests (the bundle README says nothing needs installing); the
owner should pause from the `development` worktree's `gpu_pause.sh` (the main clone's copy is older).

### 22 November 2026 ~16:40 — GATE G0 RULED; PHASE L1 OPEN (read this first)
The owner ruled every G0 row (DISCUSSION §14; G0_DECISION banner): main game has a 1-for-1 tag (P1, overturns the FIXED
no-tag rows); option (d): 1.6 m to build the pipeline and for the first demo (scripted 1v1), a 1.15 m side track in L1–L2,
1.15 m main training after L2; A12: fast engine for quick experiments and checks, main training in Isaac Lab; L1 + L2 cap
13 GPU-h; 120 s game; P5 approved (laptop or 5090); E0 → E1 → E2; train 3v3 (+1v1), score 2v1 and 5v3 too; new row 18
(training-settings sweep, cost in the L3 plan). Code: `configs/ste_learning.toml` has `[budget_l1_l2]` (cap 13.0, L1 caps
sum 8.1), L0 `closed = true` (launches refused); **one ledger per machine: at each switch run
`scripts/ste_job.py carry --gpu-h <the other machine's L1+L2 hours since its last carry> --note "<machine> <date>"`**.
L1+L2 hours used so far: 0 (laptop). Trained players for L1 are in git: `ste_provisional/` (T46 base Guard/Strike, T54,
T55, T52 ABORTED, T45 per_game.npz). Next: the L1 side-track spec (L1.11 Strike v guard_field at 1.6 m; L1.12 T46 Guard v
every Strike script; L1.13 two arms at 1.15 m: 30 s training clock / discount 0.997, T52 comparator), its driver build,
then the runs; L1.0 (5090 checks) first on the 5090. Machine-switch rule: a slow task is handed over, never cut short.
NUS-facing pages still saying "no tag" (GLOSSARY, RESEARCH, THE_GAME, DESIGN, docs/README, contact-tag plan, README):
ask the owner before editing.

### 22 November 2026 ~14:00 — G0 REPORT WRITTEN (owner asked for a proper report before G0)
`ste_learning/G0_REPORT.md`: the G0 decision explained for a project lead (summary, primer, the tag decision first, one
decision table with cost and "if wrong", evidence, limits, appendices; new game diagram by `scripts/make_g0_report_figures.py`).
Two reviewers (numbers/sources; newcomer reader), three rounds. It updates recommendation 1 (option (d): drone-model work
now, demo tag chosen after the game-rules phase; budget 12 GPU-h under (d), 11 under (a)/(b), 15 under (c)).
G0_DECISION.md is NOT yet changed: rewrite its recommendation 1 and budget after the owner rules.

### 22 November 2026 ~12:50 — WORKTREE CLEAN-UP (owner approved)
The 16 finished task worktrees (`~/AirStack-starling-max2-{g0,l02,l04,l07fix,l08,l09,l10,l11,l12,l12b,l12c,l12d,l13,l14,pilot,vid1b}`)
are removed (`git worktree remove`; every commit is in `development`; the `ste-*` branches stay). Their run folders and
`configs/local` were moved first, unchanged, to `~/AirStack-starling-max2/svg_training/runs/ste_archive/<name>/` (git-ignored;
map in its README.md). Records and LOG.md still quote the old paths: read them through that map (example: T46's players
are in `ste_archive/l12/runs/`, hashes unchanged). Two reviewers checked before removal. Left alone (not training work):
`~/AirStack-starling-max2-docs` and six `.claude/worktrees/agent-*` folders from 2 Nov flight-stack sessions (four hold
commits not on `main`). From now on: remove a task's worktree after it merges, moving its runs into `ste_archive` first.

### LAPTOP SESSION, 22 November 2026 ~06:30 — STATE AFTER L0.12c AND L0.12d (read this first)

**Done tonight (training simulator, tier 1, laptop; one seed per run; nothing flown):**
- **L0.12c longer 1.15 m runs** (owner-approved, records T54/T55, 4.71 GPU-h): Guard 3× 572 v script 645 (466 at 1×);
  Strike 5× 134 v 355 (trades two for two, then the last Strike waits out the clock). Both learned, both below scripts.
- **L0.12d cross-tag check** (owner said go, record T56, 0.12 GPU-h, controls C1–C4 game-for-game PASS): T46's 1.6 m
  Guard team at 1.15 m holds 195 (1.15 m-trained 572): the Guard strategy does not carry over. T46's 1.6 m Strike team
  reaches 636 / 931 against mark_edge (1.6 / 1.15 m) but 85 / 121 against field: the opponent moves its score far more
  than the tag (one seed). The earlier "Strike learns at 1.6 m, not at 1.15 m" reading is not supported.
- **No cause** of the 1.15 m shortfall is established (DISCUSSION §12 table; §13). Measured lead: at 1.2/1.15 m Strike
  training games finish ~13–15× less often.
- **Owner rule (22 Nov):** two or more independent reviewers on every finding and write-up, plus a two-agent
  results-and-plan discussion after each result (svg_training/CLAUDE.md). Tonight: 10+ reviews; they withdrew the lead's
  chat explanation of "why" and two overclaims.
- G0 page updated (new recommendation 1: tag 1.6 m for L1 set-up; train at the tag that will be played; opponent pool
  and cross-play scoring before anything is shown; first demo = scripted 1v1 at 1.6 m). Costed L1–L9 draft (D3: ~87
  GPU-h) updated. L0 GPU-h: 13.77 of 19.

**Waiting on the owner:** G0 walk-through (Sunday); two proposals (not run): (a) Strike team trained against
guard_field at 1.6 m (~0.6 GPU-h), (b) T46 Guard team scored against every Strike script at 1.6 m (minutes).
**Not done yet:** 3-D clips of the L0.12c/L0.12d key games; status page and morning digest (this session, next).
Worktrees: `-l12c` (merged), `-l12d` (branch `ste-l012d`, merged at session end). Row 17 stays first on the next
5090 session.

### LAPTOP SESSION, 21–22 November 2026 — L0.12c LONGER 1.15 m RUNS (read this first)

**Owner approved (21 Nov ~23:00):** Guard 3×, Strike 5× L0.12's 550 M game-steps at tag 1.15 m, same recipe, "about 6.5
GPU-h" (DISCUSSION §11). Gate files `configs/ste_l012c/guard_gates.toml` (sha256 `b52dcc23…0d4c81`) and
`configs/ste_l012c/strike_gates.toml` (sha256 `362b9126…0dfee9`), QC'd twice, locked at the first launch. Task caps
changed (L0.12 6 → 13; finished tasks lowered; sum 17.3 of 19). Expected use ~5.2 GPU-h; caps are ceilings (7.5 total):
owner (22 Nov ~00:10): if Strike runs slow, let it finish (up to the caps). Order, one job at a time, alone on the GPU (no renders, no
full suite while they run); from `~/AirStack-starling-max2-l12c/svg_training` (branch `ste-l012c`), with
`JOB="env -u CUDA_VISIBLE_DEVICES -u SVG_SHARED_DIR -u SVG_PAUSE_LEGACY_LOGS PYTHONPATH=source PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True $PY scripts/ste_job.py"`,
`P=runs/2026-11-21_ste_l012_pilot/pilot.json` (copied from the l12b worktree), `GG`/`GS` = the full hashes above:

```
$JOB launch --task L0.12 --name l012c_tag_1p15_guard --run-dir runs/2026-11-22_ste_l012c_tag_1p15_guard --min-s 900 --gpu-h 2.7 -- $PY scripts/ste_exploit_l012.py --gates configs/ste_l012c/guard_gates.toml --variant tag_1p15 --side guard --run-dir runs/2026-11-22_ste_l012c_tag_1p15_guard --cap-h 2.7 --expect-gates-sha256 $GG --pilot-json $P
$JOB launch --task L0.12 --name l012c_run0 --run-dir runs/2026-11-22_ste_l012c_run0 --min-s 120 --gpu-h 4.8 -- $PY scripts/ste_exploit_l012.py --run0 --gates configs/ste_l012c/strike_gates.toml --run-dir runs/2026-11-22_ste_l012c_run0 --cap-h 4.8 --pilot-json $P --expect-gates-sha256 $GS
# only if run 0's learner_control.json reads PASS:
$JOB launch --task L0.12 --name l012c_tag_1p15_strike --run-dir runs/2026-11-22_ste_l012c_tag_1p15_strike --min-s 1200 --gpu-h 4.8 -- $PY scripts/ste_exploit_l012.py --gates configs/ste_l012c/strike_gates.toml --variant tag_1p15 --side strike --run-dir runs/2026-11-22_ste_l012c_tag_1p15_strike --cap-h 4.8 --expect-gates-sha256 $GS --pilot-json $P --run0-json runs/2026-11-22_ste_l012c_run0/learner_control.json
```

After the runs: `scripts/ste_exploit_l012.py verdict` once per gate file (each reports one side), the category formed
in the record with `ste/exploit.variant_verdict` on the two side results (gate header "Reads"); records, ledger rows,
clips (2-D + 3-D key games), G0 page row 1d/2 and the tag-rule section. Row 17 (L0.7's 5090 part) stays first on the
next 5090 session: it checks that machine, not memory (owner asked; answered 21 Nov).

### LAPTOP SESSION, 21 November 2026 — STATE AT ~21:10 (read this first)

**Phase L0's measurements are all done and merged into `development`; the gate G0 page is ready for the owner:**
[`../../ste_learning/G0_DECISION.md`](../../ste_learning/G0_DECISION.md). Status and pictures:
[`../../ste_learning/status/STATUS_LATEST.md`](../../ste_learning/status/STATUS_LATEST.md). Records T44–T53
(`records/LEDGER.md`): T44 L0.11 screen, T45 L0.14 Crazyflie route, T46/T47 L0.12 best response (T47 ABORTED),
T48 L0.2 tier-2 speed, T49 L0.3 T41 on Isaac Lab (856 v 831), T50–T52 L0.12b bubble tag 1.15 m (T52 ABORTED),
T53 L0.13 Isaac Lab trains (PASS, 832 v 836). GPU-hours used in L0: **8.93 of 19** (ledger `runs/shared/gpu_hours.log`).

- **Owner decisions of 21 Nov:** in `ste_learning/DISCUSSION_2026-11-19_20.md` §11 (ring marker; no 1.2 m Strike re-run;
  bubble-tag test approved; proximity tag in the real game, physical intercept shown in simulation as a G0 proposal;
  tag circles and round zone in 3-D clips).
- **Waiting on the owner:** (1) longer 1.15 m runs (Guard + Strike, 3× budget, ~3.5–4 GPU-h; lead recommends yes;
  the closer-tag Guards were still climbing at the budget end, DISCUSSION §11); (2) the G0 walk-through and rulings.
- **Lead owes:** a costed L1–L9 plan for the walk-through.
- **Key reading (G0 page, numbers-checked; SUPERSEDED 22 Nov by L0.12d, see the entry above):** only tag 1.6 m has both trained sides clearly beating the scripts; the 1.4 m
  Guard gain may be the 0.05 s v 0.6 s decision-period difference (scripts held 0.6 s: 738 v trained 747).
- **On the 5090 next time:** L0.7's 5090 part (full suite, TEST-F2b, L09-5090, the two drills; `scripts/ste_job.py
  owner-pauses` first). The tier-2 physics check passed at 16,384 games with a thin margin (0.0166 v 0.02 m): a larger
  world on the 5090 may fail it. L0.3's tests need T45's per-game file (`runs/2026-11-21_ste_l014/response/per_game.npz`,
  sha 3959d594…), not yet in the PROVISIONAL bundle (lead's to-do before the switch).
- **Lessons recorded:** size a run's cap from timings on the same rule set (T47, T52 ABORTED by the time rule); tests
  that read the live progress file must not assume a task's state (two broke today).
- **Topic worktrees (merged; safe to remove later):** `-l02`, `-l04`, `-l12`, `-l12b`, `-l13`, `-vid1b`, `-g0`. Their
  `runs/` folders hold the run data the records cite (not in git).

### LAPTOP SESSION, 20 November 2026 ~22:00 onwards (RTX 5070 Ti)

Worktree `~/AirStack-starling-max2-dev` on `development` made per the note below; `scripts/nus_install_provisional.sh`
run (46 files, T41 included). Full CPU suite: 1,333 passed, 2 failed, 48 skipped (24 min); both failures are
machine-dependent tests, queued as L07-F1 (waiter-duration bound vs one-decimal rounding) and TEST-F2 (bit-level
training fingerprint recorded on the 5090 differs on the laptop's CPU), see `ste_learning/status/STATUS_LATEST.md`.
Owner (20 Nov): "go ahead with ur recommendations then continue building": L0.7 QC + fixes one at a time, drills, then
L0.8 onward on the laptop (CPU).

**21 Nov ~01:30 (laptop):** L0.7 fixes (QC C1, I1–I5, plus C1b/C1c: session-tagged pauses) merged into `development`;
laptop full suite 1,420 passed, wake-up and resume drills as expected (STATUS_LATEST). L0.8 Game spec sheet merged
(owner said Yes to NUS values in it, parent STANDARDS §2). **On the 5090 next time:** `git pull` development, run
`scripts/ste_job.py owner-pauses` (an old untagged pause would now block launches), the full suite (TEST-F2b: the 5090's
CPU capability key; L09-5090: record the tag-off golden positions once L0.9 lands), then the two drills (AUTOMATION §7;
set `GPU_PAUSE_PYTHON` if `python3` is older than 3.11). L0.9 Tag rule is on branch `ste-l0.9` under QC.

### MOVING BETWEEN MACHINES, 20 November 2026 ~21:45 — read this first on the laptop (and on every switch)

The owner works on the home RTX 5090 and the RTX 5070 Ti laptop in turns and moved to the laptop on 20 Nov evening.
The rules are in [`../../CLAUDE.md`](../../CLAUDE.md), sections "Two machines, one working branch" and "The owner's
standing rules": **`development` is the working branch on both machines; `main` moves only on the owner's word.** The
root `CLAUDE.md` says the same for training work (owner, 20 Nov 2026). On the 5090 the working folder is the same
worktree `~/AirStack-starling-max2-dev` (created 20 Nov, tracking `origin/development`); the mirror is on `development`.

**On the laptop, the first time** (the laptop's clone already has `main`; this leaves it and any local change alone):
```bash
cd ~/AirStack-starling-max2 && git status -sb          # note any uncommitted change; nothing below touches it
git fetch origin                                        # needs the owner's GitHub login (GitHub Desktop can fetch too)
git worktree add ../AirStack-starling-max2-dev development   # a separate folder on branch development
cd ../AirStack-starling-max2-dev/svg_training && claude      # start Claude HERE so the skills and agents load
```
Do not `git pull` `development` into the laptop's `main`. The laptop's docker-mounted live clone stays on `main` for
flight work; training work happens in the `-dev` worktree. Then: `mkdir -p runs`, `unset PYTHONPATH` if ROS is sourced,
`scripts/nus_install_provisional.sh` (fills `configs/local/` and `runs/nus_port/` for the NUS tests), and the full CPU
suite (CLAUDE.md, Environment). The session runs `train-start`, which ends with the status (`train-status`).

**What is on `development` (20 Nov ~22:20):** everything on `main` up to `11d9d4f2` (L0 approved, L0.1, L0.14 added to
the plan, the fleet record), then L0.7 (process tooling, built; independent QC and drills pending), the track pages
updated to the tooling as built ([AUTOMATION](../../ste_learning/AUTOMATION.md) §7: commands, exit codes, drills), the
`train-status` skill, the two-machine rules and the owner's standing rules in CLAUDE.md, the rule "training work lands
on `development`" in the root `CLAUDE.md` and every page that named `main` as the target, the STE Guard policy's run
folder in `nus_provisional/`, and this note.

**Next on the laptop (CPU only; no GPU job on the laptop until the drills below have passed there):**
1. L0.7 independent QC (`ste-test-qc-engineer`, read-only, on the code of commits `c035cbed`..`be5c6ee9`), then the wake-up
   and resume drills of AUTOMATION §7 on the laptop. Record the result in the status; L0.7 is DONE only then.
2. L0.8 Game spec sheet, L0.9 Tag rule for the study, L0.10 Scripted players (PLAN §4): all CPU.
3. (Superseded 21 Nov by the owner: no task is 5090-only; the laptop runs L0.2 and L0.13 at what fits in 12 GB.) Formerly: L0.2 and L0.13 are specified for the 5090 (tier 2 speed and training at up to 8,192 games; the
   laptop GPU has 12 GB). The STE Guard policy's run folder, which L0.3 and L0.14 part 1 need, is in the PROVISIONAL
   bundle since 20 Nov (owner): `scripts/nus_install_provisional.sh` puts it at
   `runs/nus_port/phase5/pilots/2026-11-19_nus_phase5_pilot_p1b_run4/` on any machine (`agent.pt` is the T41 checkpoint).

**GPU-hours used in phase L0: 0 of 19** on both machines. Each machine keeps its own ledger (`runs/shared/`, not in git):
before any GPU job, take the other machine's total from the last status and add it by hand.

**Advisor:** on the owner's personal Max account the `advisor` tool (Fable 5.2); on the work account an advisor agent
(CLAUDE.md, standing rules). Claude's memory on the 5090 holds nothing that is not in the committed files.

### STE LEARNING TRACK: PHASE L0 APPROVED, 20 November 2026 — read this first for anything after the NUS port

The owner set a new direction on 19–20 Nov: **STE trains its own Guard and Strike policies, in parallel with NUS**
(the NUS route is paused, lead call D8). Everything is in [`ste_learning/`](../../ste_learning/README.md): the README (what is
being built, the plan, phase L0 step by step, four flowcharts), `PLAN.md` (version 2, after an independent soundness
review), `DISCUSSION_2026-11-19_20.md` (every question, decision D1–D9 and open item P1–P13), the track's STANDARDS,
reference pages and five agents (`ste-*`, copied into `.claude/agents/`).

- **State:** **phase L0 (game definition and feasibility, cap 19 GPU-h) APPROVED by the owner, 20 Nov 2026** (L0 only:
  no later phase, no PROPOSED value); task status in `ste_learning/status/STATUS_LATEST.md`. L0 ends at gate G0, where the owner rules on the tag and zone, what a tag costs, team sizes, where to
  train, environments, the demo and the L1–L9 budget.
- **Links (owner, 20 Nov 2026):** the root `README.md` ("I want to…" row and one sentence in its `svg_training/` row) and
  the training `README.md` §7 now point at `ste_learning/README.md`. The root `CLAUDE.md` row for this folder was updated
  with the owner's yes (20 Nov).
- **Status files:** `ste_learning/status/STATUS_LATEST.md` (overwritten) and `LOG.md` (append-only), first written 20 Nov.
- **Heartbeat:** the owner did not answer the heartbeat question; the standing rule holds (full status every 30 min).
- **L0.1 DONE (20 Nov ~14:00):** `configs/ste_learning.toml` (`[track]`, `[budget]`: the 19 GPU-h phase cap FIXED, the task
  caps PROPOSED), `source/svg_training/ste/config.py` (frozen, fails closed), `tests/test_ste_config.py` (38 tests; several
  parse PLAN.md §4's table, budget sentence and header, so an edit there must keep the file in step), `tests/test_ste_literals.py`
  (no hard-coded number in `ste/` outside a module-level UPPER_CASE constant; rule in ste_learning/CODING_PRACTICES §4). The two marker tests that
  failed when pytest's temp folder number was 46, 48 or 23 are fixed (`mask_paths` in `tests/_nus_markers.py`). Next: L0.7.
- **Fleet question (owner, 20 Nov), OPEN:** real flight on Starlings, Crazyflies (`~/CrazySwarm2-with-Mocap_Strike-and-Guard`,
  another repository, read-only for this folder) or a mix. Recommendation given: Crazyflies first at Starling metres, Starling
  1v1 as planned, mix deferred; proposed a zero-GPU task "Crazyflie route check" in L0 and a fleet question at G0. Offline check
  in the Crazyflie planner (1.10 m keep-out, 0.6 s lag): 1v1 and 2v1 clean in a 6.5 m arena, 3v3 and 5v3 show solver
  emergencies in 5 of 100 matches there and none in the larger room. Owner's facts (20 Nov): both fleets share one room and
  one OptiTrack rig at different Motive rates; the 6 Nov Crazyflie flight logs are not on the 5090. Full record: DISCUSSION
  §2.16, open item P13. **Owner's ruling (20 Nov): task L0.14 Crazyflie route check added to L0 (0 GPU-h), fleet question
  added to gate G0**; the fleets themselves stay OPEN. Also approved the same day: the status text of this folder's row in
  the root `CLAUDE.md`, and a paragraph in README §2 on why NUS's JAX code was converted to PyTorch.
- **L0.7 BUILT, on `development` (20 Nov ~16:30; QC and drills pending, see the note above):** process tooling
  for every later GPU run, CPU only. `ste/shared.py` (one live-state folder `runs/shared/` in the main clone, or
  `SVG_SHARED_DIR`), `ste/pauses.py` + `scripts/gpu_pause.sh` (one pause log; old copies in other worktrees still counted),
  `ste/state.py` (`state.json`: lock, atomic write; a job is alive only if pid + start time + boot id match),
  `ste/run_contract.py` + `scripts/ste_dummy_job.py` (exit codes 0 done, 2 refused, 3 cap, 4 interrupted, 5 non-finite;
  resume after SIGINT or SIGKILL), `ste/budget.py` (GPU-hour ledger, launch refused over a cap), `ste/jobs.py` +
  `scripts/ste_job.py` (`launch` / `wait` / `status`; `wait` returns the job's own exit code, flags ENDED_EARLY 20 and
  DIED 21; no `pgrep -f` in the track's code). Builder's full CPU suite: 1326 passed, 57 skipped, pytest exit 0.
  **Still to do:** (1) independent QC (`ste-test-qc-engineer`, read-only); (2) the wake-up and resume drills of
  [AUTOMATION](../../ste_learning/AUTOMATION.md) §7 on each machine. The pages were updated to the tooling as built
  (AUTOMATION §2.1, §5, §6, §7; CODING_PRACTICES §2, §8; PLAN §8). Known limits are in AUTOMATION §7. Then L0.8.
- **Advisor:** by account (CLAUDE.md, the owner's standing rules).
- **Why L0 exists:** the review found that the proposed rules (1.6 m proximity tag, 1-for-1) may let head-count decide
  the game, that the zone radius equals the tag radius, that the programme's sizes are 2v1 and 5v3 (not 3v3), and that
  tier 2 has never trained anything (PLAN §2, F1–F10).
- **5.1 scored: FAIL** (T43), route (b) stopped; the NUS route is paused (lead call D8). G19 v P3S in NUS's JAX game and
  the same-start videos are done (T42).
- **Owner's standing asks:** the advisor is consulted at every key point; status every 30 min in the owner's format;
  quality first.
- **Private notes (5090 only):** `~/ma_skills-self-play/_notes/DISCUSSION_2026-11-19_20_FULL_PRIVATE.md`.

### LAPTOP TAKEOVER, 19 November 2026 ~11:30 — read this first if the 5090 is out of reach (for the laptop session)

The owner is moving to the office and may lose remote access to the home RTX 5090. Everything below is what a laptop
session needs; Claude's user memory on the 5090 does **not** travel, so the owner's working preferences are written
here too.

**What is on `main` (pushed by the owner):** every Phase 5 result so far, the code fixes and the PROVISIONAL bundle
(`nus_provisional/`, install with `scripts/nus_install_provisional.sh`), the docs restructure and naming pass (front
page story, What we found, Run it yourself, Train a Guard, video gallery) and this note. The stage 5.2 code (S1–S5,
CPU-tested, not yet run on a GPU) is on `main` too (full CPU suite 1,114 passed, 0 failed, 19 Nov ~11:25), once the owner
has pushed it. On the laptop: `git pull`, then `svg_training/README.md` and this file.

**What exists only on the 5090 (not reachable from the laptop):**

| Item | Where | State at ~11:30 |
|---|---|---|
| 5.1 Method match (STE port of NUS's training method), 3 seeds | worktree `~/AirStack-starling-max2-nus-method` (branch `nus-phase5-method`), `runs/nus_port/phase5/s51/` | DONE 19 Nov 21:06, scored 22:10: **FAIL** (T43; b and c fail on seed 3001 only, d passes). Plan: route (b) stops; 5.2 not started; owner's call |
| Docs pass 3 (videos viewable in every page: a GIF per clip, folded video list, GIFs beside every result, a "Watch the clips" line appended to records; new front-page section 3 "The game: NUS 2-D game vs STE drone set-up"; root README training rows; old pointer pages deleted with links updated; a list of other possibly stale pages for the owner) | worktree `~/AirStack-starling-max2-naming` (branch `docs-naming`) | a writer agent was working; NOT on main. If lost, redo from the brief in the owner's 19 Nov ~11:00 messages (summarised in this bullet) |
| Private files: NUS's code, `~/ma_skills-self-play/` (port plan, notes, docs-panel proposal and drafts, resume notes), `configs/local/` with the lab's NUS values, `runs/` | 5090 | the laptop can install the PROVISIONAL bundle instead of `configs/local/`; NUS's code only from NUS |

**Pilot results so far (on main):** 5.P1b "STE Guard policy" holds the zone against S20 in **829 of 1,000** games in
Test 5 conditions (T41; parked Guard 429). R0, N0, C0 PASS (T29, T30, T33): the 5.1 test is calibrated.

**Waiting on the owner:**
1. Route decision (5.1 FAILED, T43; the plan stops route (b)): promote the STE Guard policy route (more seeds, more
   Strike behaviours, self-play, Isaac Lab check, then an AirStack hand-over plan with CMU) and shelve 5.1b/5.1c/5.2
   unless NUS asks? (lead's recommendation: yes).
2. Review of docs pass 3 (branch `docs-naming`) before it goes to main; decide on the stale-page list it produces.
3. Send NUS the cover note (questions on the front page, section "Next steps and open questions").

**The owner's working preferences (from Claude memory on the 5090; follow them on the laptop):**
- Status updates every ~30 min and on events, always three tables: Phases (Phase | Status | Math library |
  Simulator | What), the current phase task by task (ID | Plain name | Status | Simulator | Result / ETA), and any
  other workstream (ID | Plain name | Status); then Next and Waiting on you. While `main` has unpushed commits, add a
  bold "Ready to push" line; drop it after the owner pushes.
- Task IDs, always "ID + plain name": 5.0 Plan · 5.R0 Reference rebuild · 5.C0 Fairness check: NUS vs NUS · 5.N0
  Fairness check: untrained · 5.1 Method match · 5.1b/5.1c Cheaper method variants · 5.2 Train on our drones · 5.3
  Isaac Lab check · 5.P0 Pilot: speed test · 5.P1 Pilot: Guard learner, first try · 5.P1b Pilot: Guard learner, fixed ·
  5.P2 Pilot: Guard vs mixed Strikes · 5.P3 Pilot: self-play. Side work: DOC, VID, FLT.
- The owner delegates technical training calls to the lead (decide, record why, report); still ask for AirStack or
  flight changes, external messages, pushes and anything published. Propose before large doc changes; the owner
  reviews before `main`.
- Run GPU jobs side by side when the GPU has room (`scripts/isaac_preflight.sh --approved-headless
  --allow-siblings`), but give short pilots the GPU alone (a starved run says nothing); the owner pauses jobs to use
  the PC with `scripts/gpu_pause.sh` (nus-method worktree's copy; pause-aware caps).
- Videos are recorded inside every run (never a separate re-record), and every result shown in a doc gets a GIF that
  plays on GitHub (MP4 links do not play inline).
- Public docs: neutral report tone (NUS by name, not "you"); every label is NUS's own term or defined where first
  used; NUS's policies were trained **by STE with NUS's code** (NUS gave no checkpoints).
- Never push, never `git add -A`; the owner pushes from GitHub Desktop.
### Videos, the game section and pointer pages deleted, 19 November 2026 ~12:00 — branch `docs-naming` (for the lead and the owner)

Owner-approved (19 Nov ~11:00) follow-up on the same branch; numbers and evidence unchanged.

- **GIF previews**: 261 new GIFs beside the MP4s of `docs/media/nus/` (15.9 MB; 380 px, 5–6 frames/s, 48–64 colours,
  at most 14.2 s with the last frame held; 19 re-made at 5 frames/s and 48 colours, 4 of them at 320 px;
  `isaac/g19_vs_s20_strike_win_2.gif` 224 kB is the one over 150 kB). `docs/media/nus/README.md` regenerated: every clip as a 240 px preview linking its MP4, captions
  "Guard vs Strike · played in … · outcome", one `<details>` block per section with stable anchors (`#nus-2-d-game`,
  `#copy-of-nus-2-d-game`, `#tests-1-6`, `#test-1` … `#test-6` incl. `#test-2-1`, `#test-2-2`, `#test-3a`, `#test-5a`,
  `#isaac-lab-clips`, `#ste-guard-policy`, `#how-they-were-made`). `docs/media/README.md` the same for S2/S2b.
- **Reader pages**: previews beside every result with a clip (WHAT_WE_FOUND §2, §3; day by day §4–§8, §12;
  TRAIN_A_GUARD §5–§6; RUN_IT_YOURSELF A, D2, E, F).
- **Records**: 11 records gained one final line "Watch the clips: …" (additive only; the owner's one exception).
- **Front page**: new §3 "The game: NUS 2-D game vs STE drone set-up" (table + one preview per column; the term lines
  moved there from the tests section); sections renumbered 1–8 (Watch it unnumbered). GLOSSARY: NUS 2-D game, hangar
  set-up, STE drone set-up.
- **Root**: README "I want to…" svg_training rows replaced with the owner's text; root CLAUDE.md row link now
  `NUS_PORT_REPORT.md` (link target only).
- **Deleted** (`git rm`): HOW_IT_WORKS, NUS_PORT, NUS_RESULTS, TRY_IT, PLUG_IN, NUS_PHASE4_RESULTS, WHAT_WE_DID. Plain-text
  old names stay in dated history (plans, this file's log, Linear comment copies, two records' "NUS_PORT §3" and
  "NUS_PORT Figure 1"). The deletions landed in the commit titled for the root CLAUDE.md fix (a staging slip; content
  correct).
- Checks: every relative link, image (Markdown and HTML) and anchor in `svg_training/**/*.md`, README.md and
  CLAUDE.md resolves (scripted, 1,723 links); every `<details>` block well-formed and every MP4 shown with its own
  preview (scripted); `tools/docs_check/check_docs.sh` 0 FAIL (13 PASS, 7 WARN, 1 SKIP); full CPU suite 1,077 passed,
  47 skipped, 0 failed (10 min 14 s, `env_isaaclab`). GitHub rendering itself was not viewed (no browser here).

### Naming and story pass, 19 November 2026 ~11:00 — branch `docs-naming` (for the lead and the owner)

Owner-approved (19 Nov) pass on the public docs; facts, numbers and evidence links unchanged; records not re-worded.

- **Renames** (`git mv`, one-line pointer page left at each old name so records, plans, Linear copies and the root
  README/CLAUDE.md keep working): `NUS_RESULTS` → `WHAT_WE_FOUND`, `NUS_PORT` → `NUS_PORT_REPORT`, `TRY_IT` →
  `RUN_IT_YOURSELF`, `PLUG_IN` → `PLUG_IN_YOUR_CODE` (`tests/test_adapters.py` follows), `HOW_IT_WORKS` → `THE_GAME`.
  New `docs/TRAIN_A_GUARD.md`: the pilot P1b run 4 recipe (T41) with a CPU check run on 19 Nov (1 min 45 s, exit 0).
- **Story**: front page in seven sections (overview + policies table; porting NUS's code; testing NUS's policies on STE
  drones; why performance drops; training in STE conditions; next steps and the five questions; run it yourself),
  gallery after section 5.
- **Names**: "STE" defined once per page; "defender (Guard team)", "attacker (Strike team)" at first mention; Tests 1–6
  (sub-tests 2.1, 2.2, 3a, 5a) replace ladder rows on reader pages, "Test N = ladder row N in the records" in GLOSSARY
  and WHAT_WE_FOUND; Copy of NUS 2-D game (PyTorch), STE game engine, STE drone model, Isaac Lab physics drones, STE
  port of NUS's training method (PyTorch), STE Guard policy; G19/S20/P3G/P3S said to be trained by STE using NUS's
  code. Tone neutral (no "you"/"your"): CLAUDE.md's reader-page rule and STANDARDS §2's "the partner" row updated to match.
- Checks: every relative link and anchor in `svg_training/**/*.md` resolves (scripted); `tools/docs_check/check_docs.sh`
  0 FAIL (13 PASS, 7 WARN, 1 SKIP); full CPU suite 1,077 passed, 47 skipped, 0 failed (10 min 22 s, `env_isaaclab`).

### Plain-laptop route and the PROVISIONAL bundle, 19 November 2026 ~00:30 — branch `nus-release` (for the lead and the docs writer)

Owner decisions of 18 Nov ~23:15 (docs panel `~/ma_skills-self-play/_notes/docs_panel/PROPOSAL.md`, 5090 only). Done, test
first, one commit each, on `nus-release` (not pushed):

- **C1–C3** `score.py` and `train_standin.py`: `--device auto` (default; CUDA if PyTorch sees one, else the CPU with a note);
  `train_standin.py --smoke` (the pipe test in seconds, `train_result.json` `smoke: true`). Module `svg_training/devices.py`.
- **C4** `pyproject.toml` lists the real dependencies (torch, numpy<2, scipy, msgpack, matplotlib, imageio, imageio-ffmpeg,
  opencv-python-headless, pyyaml, skrl 2.x, gymnasium, tensorboard; extra `test` = pytest) and installs with
  `pip install -e .[test]`; `tests/test_dependencies.py` fails on any unlisted import (Isaac, ROS 2, NUS's JAX named apart).
- **C5** `test_run_s0.py` passes off the lab machines (SVG_PY stub); the unstubbed host-default test skips there.
- **C6** the numpy-2 line in `test_fit_response.py`'s fixture. **C7** `make_nus_phase4_figures.py` refuses (exit 2) when
  a row is missing. **C8** the missing-`nus_deploy.toml` error says "before nus_convert_checkpoint.py". **C9**
  `setup_nus_jax.sh --cpu`.
- **Decision 6**: `nus_provisional/` (44 MB, 38 files, sha256 list) holds the lab's local settings files, the converted
  weights G19, S20, P3G, P3S, the Phase 4 starts, T16's reference data and the recordings of NUS's game, byte-identical,
  labelled PROVISIONAL (NUS will retrain). `scripts/nus_install_provisional.sh` copies it into the git-ignored
  `configs/local/` and `runs/nus_port/`. Privacy tests exempt that folder only; STANDARDS §2 and §8 say so (dated).
  STANDARDS §2 also allows NUS's own terms once per page in a translation line.
- Fresh-clone check found one more: a plain venv from `pyproject.toml` gets torch 2.15.0+cpu and skrl 2.1.2, and the
  default-path bit-level fingerprint test (recorded with torch 2.7.0, skrl 2.1.0) failed; with torch 2.7.0 + skrl 2.1.0
  in a CPU venv it passes, so the test now skips on other versions and names both. Pin or float the versions in
  `pyproject.toml`: the lead's call (floating today).
- Verified: this worktree with the bundle installed, env_isaaclab, CPU only: 1074 passed, 47 skipped, 0 failed (11 min);
  10 NUS tests that skipped before now run and pass. A fresh clone of `nus-release` (`1fd05474`), plain CPU venv with
  only `pip install -e .[test]`, bundle installed, empty HOME, `OMP_NUM_THREADS=4`: 1069 passed, 52 skipped, 0 failed
  in 10 min 21 s, `git status` clean (commands: `~/ma_skills-self-play/_notes/docs_drafts/VERIFIED_CPU_COMMANDS.md`,
  5090 only). Same clone, CPU: `nus_phase4.py --w2-replay` equals T16 exactly (46 and 1,000 of 1,000); ladder row 1 in
  full (97 s) equals the lab's GPU row in 7 of 12 pairs and differs by 1–3 of 1,000 games in 5 (each inside the record's
  Wilson interval; identical with torch 2.7.0, so not the torch version; CPU v GPU or the earlier settings file of rows
  1–3, not separated).

### Phase 4 complete and Phase 6 pass 2, 18 November 2026 ~15:15 — NUS port (for the owner, the lead and the laptop session)

Observed in the training simulator only; nothing flown. **Phase 4 is complete.** Rows 4, 5a, 5 and 6 ran in one background
chain, 05:52 to 13:54 (T22 row 4, T23 rows 5a and 5, T24 row 6; all INFO, exit 0; records
`records/2026-11-18_nus_phase4_rung{4_2,5,6}_record.md`). What they show:

| Row | Change | G19 v S20 Strike reach (of 1,000) | Reading (likely causes, not tested) |
|---|---|---|---|
| 3 | drone response, filter off | 43 | (before) |
| 4 | the all-pairs safety filter | 740 | both drones give way, so push-based blocking fails; both trained Guards concede every game to NUS's scripted Strike; the parked Guard team now holds 444 |
| 5a | free height, no jitter (control) | 740 | equals row 4 in all 12 × 1,000 games |
| 5 | free height, ±1 mm start jitter | 983 | Strike drones pass over or under (as S2b T13): G19 v S20 horizontal closest approach median 1.09 → 0.93 m, 3-D stays 1.09 m |
| 6 | Isaac Lab physics drone | 979 | agrees with tier 1; parked v S20 571 → 524 (247 games differ); 0 upsets |

A parked (zero-speed) Guard team holds 429–476 of 1,000 against S20 on rows 4–6, more than either trained Guard: the
filter works as a wall. The records' "Contact" column (853 of 1,000 on rows 4–6, whatever the Strike policy) counts
any pair under 0.50 m, team-mates included: NUS's start layout already gives 853 such starts (checked on `starts.npz`);
it is not evidence of a flight hazard (Guard–Strike 3-D closest approach: medians 1.05–1.14 m; one scripted-v-scripted game at 0.48 m; NUS-policy pairs ≥ 0.57 m). Isaac Lab camera clips: six, by `scripts/nus_isaac_clips.py` (commit `e595bfd3`).

**Phase 6 pass 2 (this session; docs only, no code or test edited).** Owner, 18 Nov ~14:10: "just put all clips on the
github … no need to keep it private": the hangar size is public (supersedes Phase 4 answer 6 and pass 1's hold-back).
- Filled every pass-2 placeholder: NUS_PORT (at a glance, §3 arena 7.5 m and the usable flying box, §8 table
  rows 4–6 and "What rows 4–6 show" with the Contact explanation, Figure 2 caption, §9 videos with key clips, §10 flight
  meaning, §11, §12 renamed "Next steps: the Phase 5 plan"), NUS_PHASE4_RESULTS, PLUG_IN, HOW_IT_WORKS, README,
  CLAUDE.md, root `CLAUDE.md` svg_training row, `docs/media/README.md` (a pointer).
- **All clips published:** 263 new files, 16.8 MB, in `docs/media/nus/{phase3,w3,phase4/row_*,isaac}/` (260 MP4
  re-encoded H.264 CRF 30, at most 800 px, same frame rate and frame count, checked; 3 Isaac Lab GIF previews).
  Index, one line per clip with game, outcome and size: [../media/nus/README.md](../media/nus/README.md). The
  top-down titles round the 7.5 m arena to "8 m x 8 m" (`viz/replay.py:148`, `:.0f`); the README says so.
- **Phase 5 plan** (owner delegated to the lead ~12:20; own-training pilots ~12:30): route (b) with a 2-D method match
  first, 3-D with the filter, hangar geometry, interface v0.1 plus height, gates before runs, a message to NUS, and
  own-training pilots not of record. Described as the plan in NUS_PORT §12; nothing started.

- STANDARDS §8 video bullet: one dated sentence added for the owner's ~14:10 decision (all NUS-port clips, re-encoded
  small, may be committed; it said "a small chosen set").

**Waiting on the lead:** review and commit (`git add` the four new media folders by path; 263 files); the Phase 5 plan
document and the NUS message (D-P5-5, D-P5-6); the stale comments, the private CLAUDE.md rule and the stale STANDARDS
fence row listed in §5.

### Phase 6 pass 1, 18 November 2026 ~06:45 — public NUS docs (for the owner, the lead and the laptop session)

Observed in the training simulator only; nothing flown. Done in the integration worktree `~/AirStack-starling-max2-integrate`
(branch `main-5090` = GitHub `main` + `docs-5090-setup` + `nus-port-phase2`), uncommitted; the lead reviews, commits, renumbers
W rows and merges. **Owner's decisions applied (18 November 2026):** NUS agreed that their code details, game settings and our
results on their code may be published (STANDARDS §2 rewritten, dated; NUS's source code and confidential report quotes stay
out); the contact-tag track may be described publicly (STANDARDS §2); root `README.md` and root `CLAUDE.md` svg_training rows
updated (status and pointers only).

- **New:** [../NUS_PORT_REPORT.md](../NUS_PORT_REPORT.md) (NUS's three branches, Phases 0–6 with library and simulator, Run 0, hangar
  geometry, self-play matrices and settling, T15–T17, Phase 4 rows 1–3, what it means for flight, Phase 5 options, the
  contact-tag track); Figure 1 `docs/figures/nus_selfplay_matrix.png` by the new `scripts/make_nus_selfplay_figures.py`
  (reads the 5090's matrix file); 13 clips in `docs/media/nus/` (1.25 MB, captions in its README).
- **Pass-2 placeholders** in NUS_PORT, NUS_PHASE4_RESULTS, media/nus README and PLUG_IN: all filled in pass 2 (above).
- **Setup and run docs:** GETTING_STARTED (NUS JAX env section, `msgpack` step, preflight 1024 MiB and both machines'
  approval), TRAINING (new "NUS jobs": `setup_nus_jax.sh`, `run_nus_job.sh` with unique `hydra.run.dir` and
  `save_eval_gif=True`, self-play videos with `eval.py`, the Phase 2–4 scripts in order), WORKSTATION_SETUP (§2c decided,
  §3 rewritten), PLUG_IN, HOW_IT_WORKS, GLOSSARY (terms; Versions: `nus_jax`, `msgpack`, layout `nus_area_denial_v1`).
- **Privacy tests rewritten, not dropped:** `tests/test_partner_privacy.py` now (1) fails on tracked NUS source (path
  rule always; file and long-line block scan when a NUS clone is present, `SVG_NUS_CLONE` or the 5090 default) and (2)
  scans code, configs and scripts only for local values (documents may state them). `tests/test_workstation_scripts.py`:
  the word and value scans cover the scripts only, not the page. `tests/test_nus_phase4.py`: the committed-text check
  (D8) is retired with a dated comment. G1–G4 (the `configs/local/` mechanism) unchanged.
- **Claude files:** CLAUDE.md (status table, machine-by-machine Environment, "5090 only" table), all six skills and six
  agents, AGENTS_AND_SKILLS, this file. `FROM_5090_2026-11-17.md` retired into §4 and §5 below (removed from the working tree).

**Waiting on the lead:** review; `git add -f` for the `.claude/` files; stage the removal of `docs/claude/FROM_5090_2026-11-17.md`
(deleted from the working tree; its content is in §4 and §5); renumber the W rows to the next T numbers (T15 onward on
today's ledger) in LEDGER and the records that cite them; merge. On the laptop after the pull: install `msgpack` if missing
(GETTING_STARTED step 5) and run `tests/test_partner_privacy.py` and `tests/test_workstation_scripts.py`, whose value scans
need the laptop's private reference files (they skip on the 5090). **Waiting on the owner:** confirm publishing the hangar's
hangar arena side (answered ~14:10: publish, see pass 2 above); choose Phase 5's route after Phase 4 (delegated to the lead ~12:20); push `main`.
**Gap:** Phase 1, Phase 2a, Run 0 and the self-play evaluation have no record or ledger row (their numbers are INFO, from the
5090's private notes); write records for them if they should count.

### Phase 4 summary, 18 November 2026 ~05:30 — NUS port, transfer ladder (for the lead, the owner and the laptop session)

Observed in the training simulator; nothing flown; no partner or hangar value here. Built and ran the plan `docs/archive/2026-11-18-nus-phase4-transfer-ladder.md` v2 with
the owner's seven answers (hold in rung 2, no row 3h). **T17 PASS** (archive pair G19/S20 through the frozen Phase 3 gates, both arms). Ledger **T17 PASS, T18 to T20 INFO,
T21 ABORTED**; records `records/2026-11-18_nus_phase4_*_record.md`; summary page `docs/NUS_PHASE4_RESULTS.md`. Rungs 1 to 3 scored (rows 1, 2.1, 2.2, 2, 3a, 3; the split of
rung 2 fired). **Rungs 4, 5, 6 NOT run:** each is estimated at 4 to 5 h (limit 2 h); rung 4 was started and stopped, rows 5a, 5 and 6 never started; the lead or owner chooses
(background run with `--accept-long`, core block only, or a filter-setting change). **Reading rule 2 fired on row 2.1** (float32 noise floor; diagnosed in the rung 2 record): the
implementer continued; the lead confirms or rewords the rule. Core change: one hook, `SvgGame._draw_starts` (owner-approved), its test is `tests/test_game_draw_starts.py`.
**Files** (all uncommitted, the lead commits; the core hook, its test and this HANDOFF line as one separate commit): `source/svg_training/core/game.py`, `tests/test_game_draw_starts.py`;
new `source/svg_training/nus/{hangar,hangar_game,players,ladder}.py`, `configs/{nus_hangar.template,nus_hangar_game,nus_phase4}.toml`, `scripts/{nus_phase4,nus_phase4_w3,make_nus_phase4_figures}.py`,
`tests/{test_nus_phase4.py,_nus_phase4_fixture.py}`; changed `nus/{outputs,outcome,strategy}.py`, `scripts/{nus_jax_common,nus_export_reference,nus_make_local_deploy}.py`,
`tests/{test_nus_phase3_privacy,test_nus_rules_privacy}.py`, `docs/PLUG_IN_YOUR_CODE.md`, `records/LEDGER.md`; new records and `docs/figures/nus_phase4_ladder.png`.
**Waiting on the lead:** commit; `train-gatekeeper` read of the records; laptop privacy scans before merge (the partner value scans skip on the 5090; every diff and commit message by eye for short partner numbers). **How the privacy check was done:** `check_payload` on every committed text and an in-memory scan of every new or changed non-ignored file for the protected set in decimal and integer forms catch EQUALITY (and relative 1e-6 near-equality) with local values only, not ratios or common divisors; two ratio leaks were found by reading and removed (the per-sample smoothness column, which differs from the per-tick one by the hold length; reach times of replica and jump rows, which are multiples of the step length, now whole seconds) and run times are kept out of the records (throughput x run time shows the game length).

### Phase 3 summary, 18 November 2026 — NUS port, converted policy (for the owner and the laptop session)

Observed in the training simulator (2-D replica); nothing flown; no partner value here (they stay in `configs/local/` and `runs/`).
Built Tasks 1–9 of `docs/archive/2026-11-18-nus-phase3-converted-policy.md`: privacy guard rails widened (literal scan over `tests/test_nus_*.py`;
`write_record` refuses any rules, deploy or architecture number), `nus/deploy.py` (git-ignored `configs/local/nus_deploy.toml`, template committed), both
scripted controllers ported (`nus/apf.py`), msgpack weight loader and bfloat16-faithful actor (`nus/actor.py`), reference export, wrapper
`svg_training.nus.strategy:NusPolicy`, outcome machinery and JAX action worker, interface draft. Gates on the first hangar checkpoints: (a) action error
0.0074 (Guard) / 0.0105 (Strike), limit 0.02; (b) converted Strike reach rate inside the JAX arm's Wilson 95 % interval for both teams (Guard 46 v 48 of 1,000;
Strike 1,000 v 1,000); wrapper test passes. Ledger `T16` (PASS); record `records/2026-11-18_nus_phase3_conversion_record.md` (see the note below if it is missing).
Videos: `runs/nus_port/videos/`. **Interface layout id `nus_area_denial_v1` (STANDARDS §3 rule 3 entry):** observation = partner layout rebuilt from our
71-number observation (own, team-mates cyclic, opponents; position / previous sample / last displacement blocks; zone radius; reached flag), action = deterministic mean, held for the hold length, vertical and yaw zero, prior weight 0; keys in `configs/nus_interface.template.toml`.
`msgpack` added to `pyproject.toml` (new `[project]` table); container image and its `CHANGES.md` line not done.
**Waiting on the lead:** commit; laptop privacy scans before merge; owner reads T16 before Phase 4.

### Evening summary, 17 November 2026 — home RTX 5090 session (for the owner and the laptop session)

All observed in the training simulator or on the desktop; nothing flown. Partner numbers are NOT in this file: they
live only on the 5090 in `~/ma_skills-self-play/` (private port plan, notes `_notes/`) and in the
git-ignored `configs/local/` and `runs/`.

**Done:**
- 5090 host env `env_isaaclab` built (setup script exits 1 on a fresh install; hand fixes in
  [../GETTING_STARTED.md](../GETTING_STARTED.md) step 5, on branch `docs-5090-setup` with its note
  `docs/claude/FROM_5090_2026-11-17.md`). Full suite there: 798 passed, 11 skipped.
- NUS code (three branches) cloned on the 5090 only; owner: NUS's code may live on the workstation,
  so TRAINING.md's "must not leave the laptop" needs updating. NUS confirms the continuous-space branch is the one.
- **Two tracks (owner, 17 Nov):** (1) area denial = the NUS port, contact-free, filter on every pair (matches the
  programme design review's Scenarios A/B); (2) contact tag = a separate one-on-one track,
  [../plans/2026-11-17-contact-tag-track.md](../plans/2026-11-17-contact-tag-track.md) (DRAFT, nothing started).
- NUS answers: their units are scaled to the arena (scale is ours; owner adopted a PROPOSED scale fitted to the
  8 m hangar, value in `configs/local/`); a policy works only on the config it was trained on (train NUS policies on
  the deployment geometry); fixed team size for the whole game (no drone dropping out).
- Phase 1: conda `nus_jax` built; NUS's own tests 65 passed, 1 failed (their stale test vs their config; NUS
  confirmed harmless). Phase 2a: NUS benchmark and two short 3 v 3 fixed-opponent runs (one per team), both teams
  win every evaluation game against NUS's scripted opponents; not runs of record; videos saved with NUS's outputs.
- **Phase 2 part A (this branch, `nus-port-phase2`):** privacy checks G1–G4 (`configs/nus_rules.template.toml`,
  `source/svg_training/nus/rules.py`, `outputs.py`, `tests/test_nus_rules_privacy.py`; marker test), a batched
  PyTorch replica of NUS's 2-D game (`source/svg_training/nus/replica.py`), fixture recorder
  (`scripts/nus_record_fixtures.py`), tests (`tests/test_nus_replica.py`). Per-step parity with NUS's code on 3 v 3,
  5 v 3 and fixed starts: max position error < 1e-5 units, flags and steps identical, every rule exercised. Full
  suite 820 passed, 11 skipped. Development check only: no record or ledger row.
- **New standard:** every training run saves videos (STANDARDS §8; `train-run` skill).
- Claude setup copied to `~/ma_skills-self-play/.claude/` (agents, skills, superpowers) with its own `CLAUDE.md`;
  kept current by the process in §6.

**Later the same night (to ~23:55):** hangar geometry decided from three reviews and a CPU balance probe (values
private on the 5090); Phase 2 gate of record **T15 PASS** (`records/2026-11-17_nus_phase2_parity_record.md`, gates in
`configs/nus_port.toml`); NUS self-play go/no-go on the hangar geometry running detached (3 seeds × 8 generations,
done ≈ 02:00); Phase 3 plan v2 committed (owner approved `msgpack` and layout id `nus_area_denial_v1`), its build
may be unfinished and uncommitted in this worktree. **Resume note (private, on the 5090):**
`~/ma_skills-self-play/_notes/RESUME_2026-11-17_night.md`.

**Waiting on the owner:**
1. ~~Zone radius and arena~~ decided (lead, from three reviews; owner asked agents to decide).
2. Phase 1: 65 of NUS's 66 tests pass (the failure is a test NUS confirmed is out of date); approve the PROPOSED gate numbers in the private port plan.
3. Go for a full NUS self-play run on the 5090 (a few hours) on the chosen hangar geometry.
4. ~~5090 Isaac preflight~~ owner chose (18 Nov) to raise the GPU limit: `isaac_preflight.sh` now allows up to 1024 MiB per foreign process (the 5090's remote-desktop daemon holds 546-589 MiB; a NUS JAX job, ~1.7 GB, still blocks). The WiFi rule (exit 10) is unchanged; the owner extended his 16 Nov headless-on-WiFi approval to the 5090 (18 Nov, "wifi: yes"), so headless launches here use `--approved-headless`. `run_nus_job.sh` uses the same 1024 MiB limit (owner, 18 Nov), so NUS jobs no longer need `--allow-shared-gpu`. Branch `docs-5090-setup` still says "500 MiB" in WORKSTATION_SETUP §2c and GETTING_STARTED step 7: update when merging.
5. **Container route is incomplete (found 17 Nov on the 5090, first container suite run since T1):** image
   `svg-training:isaaclab-2.3.2` built; `docker/run.sh '$SVG_PY -m pytest -q'` gives 704 passed, 29 failed, 13 errors
   (host: 820 passed). Causes: skrl 1.4.3 in the image (stand-in trainer tests need 2.x; 27 + 2 adapter tests);
   `svg_ground_control` not importable because only `svg_training/` is mounted (`docker/run.sh:32`; 7 filter tests);
   bare `python` subprocesses without torch/toml (3). Not 5090-specific. Fix on the laptop: (a) skip host-only tests
   in the container, or (b) skrl 2.x in the image + AirStack read-only mount (docker change: CHANGES.md entry).
   GETTING_STARTED's "two skipped tests in the container are normal" is out of date.
6. Merge `docs-5090-setup` and `nus-port-phase2` on the laptop; run `test_partner_privacy.py` there (its value scan
   skips on the 5090) and read the diff for short partner numbers.

### Morning summary, 17 November 2026 (for the owner)

**Done overnight (all observed in the training simulator; nothing flown):** S2b Tasks 1–9 built and reviewed, Task 10
results page [../S2B_RESULTS.md](../S2B_RESULTS.md) (linked from the root README). Ledger: T13 scripted games on both
backends **FAIL** (Strike drones pass over/under Guards on the physics drone; your option (a)); T14 stand-in on Isaac
drones **FAIL** (seeds 1–2 hold 0 % v straight Strike, 7–13 % v flank; seed 3 queued for the 5090, §5a). 5090 port kit
(`scripts/workstation/`, [../WORKSTATION_SETUP.md](../WORKSTATION_SETUP.md)) and the private bundle `~/svg_workstation_bundle/`. Five live screenshots of the Isaac Sim window (four worlds + the stand-in
trainer running) in [../media/README.md](../media/README.md); new opt-in `--windowed` launch option (headless stays default; WiFi survived).

**Waiting on you, most important first:**

1. **Push `main`** from GitHub Desktop before you port (the 5090 clones from GitHub; ~310 commits ahead, ~45 MB of clips and figures).
2. **The stand-in does not learn on the physics drone.** Pick the next step: (a) a tier-1 control run to find the cause, (b) a different learner or a curriculum, (c) Guards with a height-covering reward. Lead suggests (a) first, on the 5090.
3. **Confirm `[standin_v2]`** (initial log std −1.6, frozen noise on reward-free axes, 100 M game-steps per seed): taken as approved from "Issac drone runs, if possible"; you have not confirmed the table itself.
4. **T13 hold-rate gate**: FAIL by design after option (a). Re-scope that gate for later stages, or keep it as a standing record of the 2-D/3-D gap?
5. **Undiagnosed**: in 4 random-Guard cells the physics drones come 0.12–0.23 m closer than tier 1; stand-in and scripted Guards reach ~0.95 m in 3-D (under the 1.10 m keep-out). Diagnose next session?
6. **NUS**: their JAX reference results are in `~/nus_jax_reference/` (Guard best 0.999, Strike 1.000 against scripted opponents; full self-play needs the 5090). The agent's REPORT.md write was refused — say "save it" if you want it written. Slack draft in the chat.
7. **5090 settings (PROPOSED)**: JAX memory fraction 0.60; a larger S0 config for 32 GB needs your approval (STANDARDS §7).
8. **Deferred by the lead**: Task 8b (registered Isaac Lab task) and the S2b final review (gatekeeper, drone dynamics, Isaac Lab engineer) — next session. (The two small trainer fixes M7/M8 are done, 0d10ffb.)

**Where it stands.** S0 and S1 are closed. **S2 is CLOSED (16 November): every task reviewed, the final
whole-stage review done (no Critical), its single fix wave applied and re-reviewed** (review notes: `runs/sdd/s2/`). Nothing has been trained. S2's results, with figures:
[../S2_RESULTS.md](../S2_RESULTS.md); the partner guide: [../PLUG_IN_YOUR_CODE.md](../PLUG_IN_YOUR_CODE.md). The short version:

| Run | Result | Meaning |
|---|---|---|
| T5, drone model against the 12 Nov bag | FAIL | worst leg 0.120 m/s (gate 0.10; leg 3 is not a push), 63 % time off by 0.690 s (gate 0.10; mostly the held-setpoint method); model not refitted |
| T6, scripted reference | INFO, no gates | pure-rule half stands; Starling closeness spoilt by the wall bug (fixed in 17197a7) |
| T7, faster filter | ABORTED | stopped by hand for the wall fix |
| T8, faster filter | PASS (owner's 4-decimal ruling on `max_abs_dv_mps`) | 1,000 sweeps + `check_every` 8: 121,118 game-steps/s timed window (gate 100,000); whole game 90,121 INFO; staggered restarts NOT measured. Now in `configs/s2_game.toml` |
| T9, scripted reference on the fixed layer | INFO, no gates | the reference for later strategies. Pure half identical to T6. Crowded 5 v 3 near walls still reaches 0.75–0.80 m in 3-D: a LIMIT faithful to CMU's commander (filter wall-blind, fence after the filter), not a bug |

Design §7 done conditions: (1) game-rule tests PASS; (2) scoring tool on fixed scenarios PASS; (3) filter PASS (T8);
(4) stand-in trainer MOVED to S2b by the owner (16 November), not run; (5) partner guide DONE in part (the guide
exists and runs; the design's worked example uses the stand-in, so it comes in S2b, lead's ruling). Interface change 16 November: observation 69 → 71 numbers (zone centre at 69–70; central state 59 → 61); policy interface version 0 → 0.1 (`INTERFACE_VERSION`).

S1 in one line: T2 filter copy FAIL (accepted by the owner), T3 simulator fit FAIL (two clocks), real-log fit
exploratory, T4 INFO; details in [../S1_RESULTS.md](../S1_RESULTS.md).

Tests (Task 11, 16 November, laptop host, conda `env_isaaclab`, `PYTHONPATH=source`): `531 passed, 2 warnings in 398.78s` (full suite after the Task 11 document edits; the 2 warnings are matplotlib tight-layout notices from `scripts/make_s2_figures.py`). The partner leak test ran but checks nothing on this laptop: the local file has no number distinctive enough to scan (see §5).

1. `cd ~/AirStack-starling-max2/svg_training && claude`, then say: **"Run the train-start skill, read
   docs/claude/HANDOFF.md §0, and tell me what is waiting on me."**
2. **Next, in order.**
   - **S2 final review: DONE** (16 November): Opus (Fable was out of quota), no Critical; fix wave 4d0d409 (setting guard, honest leak test, committed wall probe `scripts/probe_wall_limit.py`, interface version 0.1, caveats, clip on the fixed walls); A/B wording c218cbb.
   - **Owner ruled, 16 November** (S2b plan, a7e4c2f): (A) the S2b games gate is now `closest_cross_3d_gap_max_m = 0.10`
     (Isaac Lab drones' 3-D closest approach at most 0.10 m below tier 1's on paired games without a start miss),
     replacing `physics_closest_cross_min_m = 1.0`, which failed by construction; (B) the training filter stays faithful
     to CMU's.
   - **S2b STARTED 16 Nov ~06:45** (build ledger `runs/sdd/s2b/progress.md`, briefs beside it): Tasks 1–2 DONE (20021af, 2d000bf, 7873811), Task 3 PX4 cascade done (a669df8, eea2d2e: + ModalAI 15 Hz yaw filter, + PX4 allocator saturation feedback), Task 4 physics backend done (f4ff5fb, 1a94f87), Task 5 done (Isaac Lab adapter; ledger T10 FAIL, accepted). **Night 16 Nov:** Task 9 stand-in trainer committed (dfc2211) + fix round 1 (7eb8241: Tanh-bounded policy; non-finite actions counted, refused by score.py, abort exit 3), re-review 5/5 ✅, five small findings queued as fix round 2; GPU pilot (pure, seed 1, not of record) running. Task 6 Isaac Lab video committed ad6a9ef (7 scripted clips + 3 stills in `docs/media/s2b_*`, 41 MB; four clips cut at 40 s with no result), task review running. **Night 16→17 Nov, later:** Task 6 complete (fix round 9832c51: two sidecars now say working tree unknown). Task 7 complete (413c713, 4eb6e55): ledger **T11 step tests FAIL** (real-log t63 worst 0.377 s, Isaac drone 0.05–0.13 s quicker than the real drone; tier 1 far slower than both — REAL tier-1 behaviour: fitted 1.72 m/s² acceleration cap eats the commander's 0.1 s feed-forward pulse, t63 ~0.9 s; owner's call), **T12 throughput INFO** (4,096 games: 2v1 162,510, 5v3 262,190 drone-steps/s; all > 20,000). Task 9 diagnosis (nine pilots, none of record, `runs/sdd/s2b/task-9-report.md`): cause of no learning = initial exploration noise (std 1.0 on a ±1 action box); init log std −1.6 + frozen noise on reward-free axes learns, but seed 1 ends 0.22 and seed 2 0.13 v straight → stand-in gate likely FAIL. Proposed `[standin_v2]` (100 M/seed) waits for the OWNER: (a) approve and run, accept a likely FAIL as the pipe-test result (lead recommends); (b) new learner/curriculum; (c) gate change. Diag-only flags 9471b61, 9964ac7. **Task 8 DONE (c4d722d, 17 Nov ~05:25): ledger T13 FAIL** — 36 of 60 cells over the 0.10 hold gap, every one with Guards holding less on the physics drone (worst 95.1 % → 0.3 %): Strike drones pass over or under Guards (43–64 % of physics games, 0 of 48,000 tier-1 games); tier 1 itself drops 97.5 % → 0 % held when the Strike starts 1 mm higher, so tier 1's scripted holds rest on exact equal heights. 4 random-Guard cells over the 0.10 m closest-approach gap (physics 0.12–0.23 m closer at the minimum; undiagnosed). 0 upsets, 0 NaN. Owner kept vertical passing (option a). Review: 2 Important fixed in round 1 (600464d: fail-closed upset/NaN gates; 1 mm diagnosis committed as `scripts/diag_vertical_pass.py` + `docs/notes/2026-11-17_s2b_vertical_pass_note.md`), re-review ✅ — Task 8 COMPLETE. **Task 10:** `docs/S2B_RESULTS.md` committed ee2a59f + newcomer fix round dee4cb8; root README links it (8d32cf0); stand-in section waits for the Isaac seeds. Isaac stand-in seed 3 goes to the 5090 (lead's ruling 05:52). **17 Nov ~01:30 (owner):** NUS MARMOT Lab's JAX training code shared (`~/ma_skills-area-denial-continuous-space-self-play`, partner-confidential, never committed); owner chose to run it unchanged tonight as the reference (`~/nus_jax_reference/`, conda env `nus_jax`, W&B off); later our PyTorch copy of their method must match it on 2-D rules before training on Starling/Isaac drones. Home RTX 5090 PC (Ubuntu 24.04) = future training workstation: checklist [../WORKSTATION_SETUP.md](../WORKSTATION_SETUP.md). **Port kit (17 Nov, owner porting next day):** `scripts/workstation/` (check_machine, setup_isaaclab_host with pinned `env_isaaclab_requirements.txt`, setup_nus_jax, run_nus_job, sync_results; all `--dry-run`, UNTESTED ON THE 5090), `tests/test_workstation_scripts.py` (29 pass), page rewritten; PRIVATE bundle `~/svg_workstation_bundle/` (99 MB, outside git: NUS code, tonight's two NUS checkpoints, reference logs, log103 flight log, NOTES.md with commands + sha256). Open for the 5090 evening: the remaining S2b Isaac stand-in seeds and their exact command go here once the laptop's overnight seeds finish (WORKSTATION_SETUP §2 step 4 points here); memory fraction 0.60 and an S0 config for 32 GB are PROPOSED, owner approves. Still to do: Task 10 docs (`docs/S2B_RESULTS.md`, being written 17 Nov from 05:30; then the root README row gets its link), Task 8b registered Isaac task DEFERRED to the next session / 5090 (lead's ruling), windowed screenshots last, S2b final review. OWNER DECIDED (16 Nov, before sleeping): accept T10's FAIL; use SIM-ONLY yaw-rate gains 0.25/0.2/0 (AirStack sim precedent CHG-0024; translation identical); construction-site world bought by the owner from CGTrader — rendered clips may be committed (never the asset files). Running S2b Tasks 6–10 overnight; Isaac spike done (bcad43e). Isaac launches: HEADLESS only, approved on the WiFi laptop by the owner (16 Nov, "yes dont worry about wifi"); windowed launches allowed too ("u can allow window launches"); default stays headless for runs of record. An early headless Isaac spike runs alongside Task 2.
   - **S2b** ([../archive/2026-11-16-s2b-isaac-lab-environment.md](../archive/2026-11-16-s2b-isaac-lab-environment.md)),
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

**S2 progress** (plan: [../archive/2026-11-15-s2-game-and-plug-in.md](../archive/2026-11-15-s2-game-and-plug-in.md); build ledger `runs/sdd/s2/progress.md`, git-ignored, with every ruling and finding)

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
| 9 | skrl and Gymnasium adapters, partner guide `docs/PLUG_IN_YOUR_CODE.md`; observation 69 → 71 | done (`c9faff3`..`911b3ae`) |
| 10 | Stand-in trainer | MOVED to S2b (owner, 16 November) |
| — | Replay clips (`docs/media/`) | done (`bcae60b`); the Starling clip predates the wall fix |
| 11 | Documents (S2_RESULTS, WHAT_WE_DID §7, GLOSSARY, README, CLAUDE.md, DESIGN §8 note, STANDARDS §4 sources, this file) | DONE (aedb076; final review fix wave 4d0d409, c218cbb) |

**S1 progress** (plan: [../archive/2026-11-15-s1-drone-model-and-safety-filter.md](../archive/2026-11-15-s1-drone-model-and-safety-filter.md); build ledger `runs/sdd/s1/progress.md`)

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

**S0 progress** (plan: [../archive/2026-11-14-s0-measure-throughput.md](../archive/2026-11-14-s0-measure-throughput.md))

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
| — | Owner's decision on T1 (15 Nov) | (the owner followed the recommendations) | T1 stands as FAIL as written; its numbers are used. Next, in order: (1) record fixes + automatic retry of an Isaac start-up crash (building); (2) the S1 plan for the owner's approval (research running); (3) documentation written with the technical-writer agent. The next S0 (on the workstation) should come out PASS |
| — | Owner, 15 Nov ("yup ok") | S1 plan approved with its gates; root README links the folder | S1 runs subagent-driven from `docs/archive/2026-11-15-s1-drone-model-and-safety-filter.md`; a training guide (headless and with the Isaac Sim window) is being written for when training exists (S2) |
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
agents and skills for the work. Since then S0, S1 and S2 have been built and run (T1–T9), S2b built and run (T10–T14), and NUS's strategy ported (T15–T21, [NUS_PORT_REPORT](../NUS_PORT_REPORT.md)); **no strategy of ours has been trained** (NUS's policies were trained with NUS's code).

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

**25 November 2026 ~14:00:** STE track: L0–L3 done, the L3–L6 pipeline check done (both routes PIPELINE WORKS, T73–T89); route 3 (the learned-skills route) adopted (R35), no GPU-hour cap and the aim a useful policy (R39), the heads trained on the skill network (R40), self-play before LS3 (R41): the workflow v3 has had its design review (folded in); the build waits on the owner's word; nothing built or run. The newest §0 entry is the current state; the table below is older.

**State on 18 November 2026** (details in §0 and the results pages):

| Item | State |
|---|---|
| S2b | built through Task 8, not closed; T14 seed 3 queued for the 5090 (§5a); Task 8b and the S2b final review deferred |
| NUS port | Phases 1–4 done: T15, T16, T17 PASS; Phase 4 rows 1–3 (T18–T20) and 4, 5a, 5, 6 (T22–T24) INFO, the first row 4 attempt T21 ABORTED. The safety filter and 3-D undo NUS's push-based blocking (G19 v S20 43 → 740 → 983 of 1,000; Isaac Lab 979); a parked Guard team holds about half against S20. Phase 5 planned by the lead (route (b) and own-training pilots), not started; Phase 6 passes 1 and 2 done, every clip published ([NUS_PORT_REPORT](../NUS_PORT_REPORT.md)). The lab's NUS files are committed PROVISIONAL in `nus_provisional/` (decision 6, 19 Nov; installer `scripts/nus_install_provisional.sh`) |
| 5090 host env | `env_isaaclab` built with hand fixes (GETTING_STARTED step 5; the follow-ups in §5); NVIDIA's licence accepted (owner's choice) through the `EULA_ACCEPTED` file; `nus_jax` built; container image built, its suite not clean (§0, 17 Nov evening, item 5) |
| Preflight | 1024 MiB per foreign process in `isaac_preflight.sh` and `run_nus_job.sh`; `--approved-headless` approved on both machines (laptop 16 Nov, 5090 18 Nov) |

**Decided by the owner, 17–18 November 2026.**

| Decision | Choice |
|---|---|
| NUS's code on the workstation | allowed (owner, 17 Nov) |
| Two tracks | (1) area denial = the NUS port, contact-free, filter on every pair; (2) contact tag = a separate one-on-one track, DRAFT plan (17 Nov) |
| NUS port values | the hangar geometry decided by the lead from three reviews (owner asked agents to decide, 17 Nov); every PROPOSED gate approved before its run; Phase 1 FAIL accepted |
| Publication | NUS agreed: code details, settings and our results may be published; NUS's source code may not (18 Nov; STANDARDS §2) |
| Contact-tag track | may be described in public documents (18 Nov; STANDARDS §2) |
| GPU limit, WiFi | 1024 MiB per foreign process; headless over WiFi approved on the 5090 (18 Nov) |
| Phase 4 | all seven plan answers accepted (18 Nov ~05:00); core hook `SvgGame._draw_starts` approved |
| Root edits | root `README.md` and root `CLAUDE.md` svg_training rows (status and pointers only, 18 Nov) |
| Phase 5 (~12:20) | delegated to the lead (owner, 18 Nov): route (b), our PyTorch copy of NUS's method with a 2-D method match first; 3-D with the filter; hangar geometry kept; gates before any run ([NUS_PORT_REPORT §12](../NUS_PORT_REPORT.md#12-next-steps-the-phase-5-plan)) |
| Own training (~12:30) | "explore to see if we can train ourselves": time-boxed pilots, not of record, training our own Guard policy on tier 1 with the filter and 3-D |
| Clips and hangar size (~14:10) | "just put all clips on the github … no need to keep it private": every NUS-port clip published; the 7.5 m arena and the usable flying box may be stated (the motion-capture camera survey is still not needed in the docs) |

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

**25 November 2026:** the owner's confirmation of the lead's reading of R39 (no cap: scope and the announce rule); the word for the route 3 build after the design review; the LS1 pass limits, set by the owner after the noise-floor read (R38); the held-out set; the learner v2 note (after LS1, R37); L7 is the owner's gate; NEAR-962; the Crazyflie commanded gaps. Older items below.

### 5-phase5-2. Branch `nus-phase5-2` (19 Nov 2026): what stage 5.2 still needs

- `train-gatekeeper` read of the S1–S5 code and of `[gates.phase5_tier1_training]` (PROPOSED), then the freeze. Items to read: the
  opt-in v0.2 interface; the critic's missing reached flag (`critic_reached_flag`); the reward choices (sticky flag per tick, inside share
  at the decision's end, horizontal distances); `configs/nus_phase5_tier1.toml` (training cap 72 GPU-h OPEN, the INFO pairing lists,
  clamp tolerance 0.01 m); whether training may use the CUDA-graph filter (the evaluation always uses row 5's path, which C-1 needs).
- 5.1 PASS, then 5.1b and 5.1c (variants run only after it); 5.2 uses the cheapest variant that PASSES. At P0's rates only 5.1c with the
  three seeds side by side fits 72 GPU-h (about 35 h, plan §8); three seeds in **one process** is not built; separate processes need
  `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` plus `--memory-fraction`, tested on the GPU first.
- Copy the Phase 4 `row_5/` and `row_6/` `scores.json` and `per_game.npz` (sha256 pinned in the gate table) into this worktree's
  `runs/nus_port/phase4/`; the evaluation refuses without them.
- The plan's S6–S9 and D1 (runs, evaluation, 5.3, docs) are not started.

### 5-naming. Branch `docs-naming` (19 Nov 2026): what is still open

- Merge to `main` (the lead) and the owner's read of the front page. The figure `docs/figures/nus_phase4_ladder.png` still
  says "row" on its axis (its caption maps row N = Test N); redrawing it needs all ten Phase 4 `scores.json` (5090 only).
- TRAIN_A_GUARD's GPU run and the Parked Guard re-score are not verified from a fresh clone.

### 5-release. Branch `nus-release` (19 Nov 2026): what is still open

- The docs restructure for NUS is applied on this branch (19 Nov): front door `README.md`, `docs/WHAT_WE_FOUND.md`,
  `docs/RUN_IT_YOURSELF.md` (the verified fresh-clone commands), `docs/README.md` (page map, labels, history), `records/README.md`,
  four after-the-fact INFO records (T35–T38; T34 unused: the P1b rerun takes the next free number when it ends), the agents and skills no longer call
  `configs/local/` and `runs/nus_port/` 5090-only. Not done: the S1/S2/S2b owner to-do sections stay on their pages
  (other pages link their anchors).
- Not in the bundle: `runs/nus_port/w3/reference/` (only `--cuda-parity` needs it), the 223 MB Phase 5 one-update exports
  (3 `test_nus_mappo` tests keep skipping), `configs/local/partner_rules.toml` (exists nowhere; 2 privacy scans skip).

### 5a. On the home RTX 5090: S2b stand-in seed 3 (ledger T14 is FAIL already; seed 3 completes the record)

**17 Nov 2026:** the 5090's host env is built (with hand fixes): setup in [../GETTING_STARTED.md](../GETTING_STARTED.md) (5090 column), record in [../WORKSTATION_SETUP.md](../WORKSTATION_SETUP.md) §2a. **18 Nov:** preflight decided (§2c: 1024 MiB, headless on WiFi approved); `--approved-headless` exits 0 when no other GPU job runs; the Phase 4 chain finished at 13:54 and the Isaac Lab clips at 14:33 (18 Nov), so the GPU is free unless a Phase 5 job has started.

Seeds 1–2 ran on the laptop (17 Nov, record `records/2026-11-17_s2b_standin_isaac_record.md`); both FAIL every gate
cell, so T14 is FAIL and seed 3 cannot change it, but it completes the record. From `svg_training/`, with
`export PYTHONPATH=source`, `P=~/miniconda3/envs/env_isaaclab/bin/python`, after `scripts/isaac_preflight.sh --approved-headless`,
inside `tmux`:

```bash
$P scripts/train_standin.py --headless --config configs/s2.toml --settings standin_v2 --seed 3 --name 2026-11-17_s2b_standin_isaac_seed3 --motion physics --eval-every-updates 80 > runs/2026-11-17_s2b_standin_isaac_seed3.log 2>&1
$P scripts/score.py --guard runs/2026-11-17_s2b_standin_isaac_seed3,random --strike strike_straight,strike_flank --sizes 2v1 --presets physics --batch-per-pair --games-per-band 1000 --seed 1003 --no-local --headless --out runs/2026-11-17_s2b_standin_isaac_seed3_score
$P scripts/score.py --guard guard_mark_edge --strike strike_straight,strike_flank --sizes 2v1 --presets physics --batch-per-pair --games-per-band 1000 --seed 1003 --no-local --headless --out runs/2026-11-17_s2b_standin_isaac_seed3_score_mark_edge
```

Bring the three folders back with `scripts/workstation/sync_results.sh` (one folder per call), then on the laptop
(where seeds 1–2 live; `runs/` is not in git) run:

```bash
G=runs/2026-11-17_s2b_standin_isaac
$P scripts/train_standin.py verdict --gates $G/gates.toml \
   --scores runs/2026-11-17_s2b_standin_isaac_seed1_score,runs/2026-11-17_s2b_standin_isaac_seed2_score,runs/2026-11-17_s2b_standin_isaac_seed3_score \
   --out $G/verdict_seeds_1_2_3
$P scripts/make_s2b_figures.py standin docs/figures/s2b_standin_isaac_curves.png runs/2026-11-17_s2b_standin_isaac_seed{1,2,3}
$P scripts/make_s2b_figures.py standin_bars docs/figures/s2b_standin_isaac_bars.png $G/verdict_seeds_1_2_3 \
   runs/2026-11-17_s2b_standin_isaac_seed{1,2,3}_score runs/2026-11-17_s2b_standin_isaac_seed{1,2,3}_score_mark_edge
```

Then amend the T14 record (it must name the
5090 and the commit seed 3 ran on). About 70 min training on a free laptop GPU; expect less on the 5090.

| Item | Who | Needed before |
|---|---|---|
| D1 reading of "one keep-out per team" (`push_rule = "block"`) against NUS's report; `shove` is the other switch | owner | a partner-rules result |
| Real-drone hazards, **HYPOTHESES, not flown, not fixed**: (1) CMU's commander runs the CBF (`swarm_commander.py` ~2140) before the keep-in fence (~2210), so a drone held at the fence may let another inside 1.10 m (T9 diagnosis, training copy); (2) the position setpoint is not filtered, teammates head-on 1.083 m in tier 1 (T4) | owner (tell CMU? test?) | the next multi-drone real flight near a fence |
| INFO speed run with staggered game restarts (T8 timed all games starting together) | Claude | any training-time claim |
| Phase 5, route (b) (decided by the lead, owner delegated, 18 Nov ~12:20): write the plan with its gates (method match in 2-D first, 3 seeds), have the gatekeeper read it, then build ([NUS_PORT_REPORT §12](../NUS_PORT_REPORT.md#12-next-steps-the-phase-5-plan)) | lead | before any Phase 5 run |
| Phase 5 own-training pilots (owner ~12:30): tier 1, hangar geometry, filter and 3-D, the stand-in trainer; Guard first against S20 and our scripted Strike, then self-play; not of record; videos on | lead | when the GPU is free of Phase 5 work |
| Message to NUS with the Phase 4 findings (the filter and 3-D break push-blocking), asking whether NUS retrains on their side in parallel | lead drafts, owner sends | soon |
| A flight-side height lock that removes over/under passing (an AirStack change, CHG entry) | owner + CMU | before a 3-D policy flies |
| Records and ledger rows for Phase 1, Phase 2a (benchmark, fixed-opponent runs), Run 0 and the self-play evaluation (today INFO from the 5090's private notes) | lead + owner | if they should count as runs |
| STANDARDS §4 row "Arena, lab scale" still says the keep-in fence is 4 × 4 × 4 m; `goal_two_ours.yaml:74-75` is ±3.25 m × 4 m (CHG-0072, owner 16 Nov). A flight-stack value: STANDARDS changes go through the owner | lead → owner | the next STANDARDS edit |
| Stale "kept local" wording after the owner's ~14:10 decision (the hangar size is public): `scripts/nus_isaac_clips.py:18` docstring and `configs/nus_hangar.template.toml` lines 1–3 (comments only; the `configs/local/` mechanism stays); `~/ma_skills-self-play/CLAUDE.md` rule 1 (5090 only: still lists the hangar size as never committed); the Phase 4 plan's answer 6 (historical, leave it or add a dated note). Not edited in pass 2 (a docs-only pass) | lead | the next code edit |
| `~/ma_skills-self-play/CLAUDE.md` rules 1 and 3 (5090 only) still say NUS values and videos never enter the repository: update them to STANDARDS §2 (18 Nov) | lead, on the 5090 | the next NUS session |
| Code and config comments still state the old rule ("never type/copy a partner value into a tracked file"): `configs/nus_{rules,deploy,hangar,interface}.template.toml` line 3; `scripts/nus_make_local_rules.py:63`, `scripts/nus_make_local_deploy.py:51` (the header they write into the local files); `scripts/nus_make_videos.py:10` (videos stay under `runs/`); `source/svg_training/nus/hangar.py:100`. True for code and configs (the mechanism), no longer for documents (STANDARDS §2, 18 Nov). Not edited in Phase 6 pass 1 because the Phase 4 chain runs this code | lead | the next code edit, after Phase 4 |
| Build the hand fixes into `setup_isaaclab_host.sh` (`flatdict` needs setuptools < 81; `isaaclab_rl` upgrades torch to CUDA 13 and leaves its libraries; unpinned drift), from the 5090's note of 17 Nov | owner decides | the next fresh install |
| Pin `warp-lang==1.14.0`, `tensordict==0.12.4`, `stable_baselines3==2.8.0`, `starlette==0.49.1`, `pandas==3.0.3` in `scripts/workstation/env_isaaclab_requirements.txt` | owner decides | the next fresh install |
| `tests/test_record_steps.py::test_refuses_existing_run_folder` needs `runs/` to exist (fresh clone: `FileNotFoundError`; docs say `mkdir -p runs`) | lead | — |
| The setup script could clear a ROS `PYTHONPATH` itself (`env -u PYTHONPATH`); its header still says `UNTESTED ON THE 5090` (the test `test_syntax_header_and_executable` requires that phrase: change both together) | lead | — |
| `msgpack` in the container image (and its `docs/record/CHANGES.md` line) | lead | the next image build |
| `docs/media/5v3_starling` clip and its README "known limit" line predate the wall fix (`bcae60b` < `17197a7`); regenerate or relabel | Claude | showing the clip outside the lab |
| A pair mask in CMU's safety filter, so that a contact tag can fly at all; and a flight safety case for deliberate contact | owner + CMU (outside this folder) | any flight of a contact policy |
| The zone's size and place in each world beyond S2 (S2 draws arena and zone sizes at random; partner zone ratio in the local file) | owner | S3 |
| What the real drone senses its surroundings with: a known map, or an on-board range sensor | owner | S3 |
| Control level for contact tags: stay at velocity, or add a final-approach skill at thrust and body rates | owner | side quest (S2 trained nothing with tags) |
| The real flight with planned pushes (NEAR-962; list: [../S1_RESULTS.md](../S1_RESULTS.md#what-the-owner-needs-to-do-next)); T5 shows the exploratory model rises too slowly | owner | the `real` parameter set's run of record |
| Metres per partner unit and seconds per step (NEAR-970): decided for the hangar, 0.40 m per unit and 0.60 s per step (NUS: the units are scaled to the arena; [NUS_PORT_REPORT §3](../NUS_PORT_REPORT.md#3-phase-0-answers-and-the-hangar-geometry)) | closed (lead, 17 Nov) | — |
| What a drone may observe about others (full state, or shared with delay and loss); S2 gives the full state behind the `obs_view` switch | owner + partners | S3 |
| How a drop-out is simulated | owner + partners | S4 |
| Written velocity contract with NUS and CMU (Linear NEAR-874, NEAR-875) | owner + NUS + CMU | use 2, S5 |
| Tell UPenn about this pipeline (NUS knows: Phases 0–4 ran on its code with its answers); UPenn already has an Isaac Lab environment | owner | early |
| Access to a training workstation (RTX 5090, RTX PRO 6000 or RTX 6000 Ada); its driver and Isaac versions (NEAR-959) | owner | S0 on that machine |
| Build and try the image on the training workstation (`docker/build.sh`, then `docker/run.sh`) | owner + Claude | S0 on that machine |
| A ROS 2 policy node inside the AirStack tree | owner (separate approval) | S5 |
| Rotor positions for tier 2: sim CAD or the drone's parameters | owner | S4 |
| Driver 595 with AirStack's Isaac Sim 5.1 | untested | any move to Isaac Lab 3.0 on a machine that also runs AirStack |

**Closed 16 November 2026:** licence of the construction-site asset. The owner bought it from CGTrader. Rendered
clips made from it may be committed; the asset files themselves never are.

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

**Keeping this file current (owner, 17 November 2026):** every session ends by updating §0 (a dated summary for the
owner and the next session, on whichever machine), §4, §5 and "Last updated", committed with the work on its branch;
the other machine merges it. NUS's settings and results may be written here since 18 November 2026 (STANDARDS §2);
NUS's source code and quotes from confidential programme reports may not. The NUS workspace on the 5090
(`~/ma_skills-self-play/`, private, 5090 only) keeps copies of this folder's agents, skills and STANDARDS, refreshed at
each session start by `sync_claude_setup.sh`; the laptop has none and needs none.

1. Run the `train-start` skill.
2. The design is approved. A change to it goes through the owner first.
3. S0, S1 and S2 are closed; S2b is built and waits on the owner's choices (§0 morning summary 17 Nov); the NUS port
   has finished Phase 4 and Phase 6 pass 2; next is the Phase 5 plan (route (b)) and the own-training pilots (§0, §5,
   [../NUS_PORT_REPORT.md](../NUS_PORT_REPORT.md#12-next-steps-the-phase-5-plan)).
   Build with `train-implementer`, test first, and have `train-gatekeeper` read each record.
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
| NUS's code (three branches), the private port plan, notes `_notes/`, probes `_probes/` (Run 0, self-play matrices, videos), NUS's outputs | `~/ma_skills-self-play/` — **5090 only**; on the laptop read [../NUS_PORT_REPORT.md](../NUS_PORT_REPORT.md) |
| NUS job logs and exact commands | `~/nus_jax_runs/*.log`, `*.cmd.txt` — **5090 only** |
| NUS local values, converted weights, Phase 4 rows | `configs/local/nus_*.toml`, `runs/nus_port/` in `~/AirStack-starling-max2-nus-port/svg_training/` — **5090 only** (git-ignored) |
| Linear plan snapshot | this project (P-NEAR-31): [svg_training/docs/linear/snapshots/2026-11-16-project-plan-linear.md](../linear/snapshots/2026-11-16-project-plan-linear.md) (folder layout: [../linear/README.md](../linear/README.md)); the flight-stack projects: `docs/linear/snapshots/2026-11-13-project-plan-linear.md` in this repository |
