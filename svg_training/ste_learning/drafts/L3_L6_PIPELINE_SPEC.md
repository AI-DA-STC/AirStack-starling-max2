INTERNAL · spec of the L3-L6 pipeline check of the STE learning track (owner R23: cap 20 GPU-h, "pipeline check, not for flight"; R19 both routes; R30 two-level skills; R31 even filter split; R32 landing off): the budget split, the game and gate files, the reading words fixed before any run, the Isaac smoke and the export; reviewed by two reviewers 24 Nov 2026 (no blocking finding) and revised for the lead's answers; NO run launched · gate files: [configs/ste_l3/](../../configs/ste_l3/) · budget: [configs/ste_learning.toml](../../configs/ste_learning.toml) `[budget_l3_l4_l5_l6]` · design notes: [L3_TWO_ROUTES_DESIGN.md](L3_TWO_ROUTES_DESIGN.md), [L3_SLICE2_DESIGN.md](L3_SLICE2_DESIGN.md), [L3_SLICE3_DESIGN.md](L3_SLICE3_DESIGN.md)

# L3-L6 pipeline check: spec (24 Nov 2026)

Written 24 Nov 2026 by the builder (`ste-software-engineer`, Opus 5.5), on branch `l3-pipeline` cut from `development`
at `01909e02`. What it answers: for each route (pure RL "velocity", and the two-level "skills" route of R30), does the
whole pipeline work (train, score, export, reload, every control passing), and how do the two routes compare on the
same budget, read as INFO. It is not a training budget of record, and nothing here is a flight result.

## 1. Budget: 20 GPU-h (owner, R23), the split

Projections come from measured runs on the same recipe, 16,384 games, 550 M game-steps:
- **T46** (laptop RTX 5070 Ti, tier 1, fixed opponent): Guard 0.404 GPU-h, Strike 0.594 GPU-h. The median rate was
  340,000-396,000 game-steps/s. L0.12's pilot used 0.18 GPU-h.
- **T67** (RTX 5090, L1.10, the same budget): run 0 0.031 (PASS at its first read), Guard 0.155, Strike 0.265.
- **T71** (RTX 5090): the Isaac smoke of the scripted cells, 1,000 games × 7 cells, 0.085 GPU-h. On Isaac, 0.080 s per
  batch tick for 7,000 games.
- **T53** (tier 2 training, 302 M game-steps, 1.527 GPU-h for both arms) is not used: every pipeline-check run trains
  on tier 1. Tier 2 enters only through the smoke (section 4).

Two costs are **unmeasured**, and the pilots measure them:
- **The pool:** the opponent team runs K = 5 or 6 scripts per tick instead of one. Assumed at most ×1.5 on time.
- **The skills route:** the trained team's dispatch also runs its K scripts per tick (and logs its choices). Assumed
  at most ×2.25 together with the pool.

The absent-drone mask adds a loop of 32 decisions per update, which is negligible. Each run is asked with its
**laptop worst case** (the run's `--cap-h`, recomputed by the pilot through the driver's time rule before any run). A
task cap covers its first run's expected use plus its last run's ask, as the launcher sees it (L1.10's rule).

| Task | What | Runs and asks (GPU-h) | Expected use: laptop / RTX 5090 | Cap |
|---|---|---|---|---|
| L3.1 | Isaac smoke of the tier-2 skills fixed-choice replay (section 4) | 1 × 0.3 | 0.1 / 0.1 (T71 0.085) | 0.3 |
| L3.2 | velocity pilot (rates at 8 k / 16 k / 32 k games, the 4 Strike probes, timing) | 1 × 0.4 | 0.27 / 0.1 | 0.4 |
| L3.3 | skills pilot (the same, two-level learner) | 1 × 0.6 | 0.4 / 0.15 | 0.6 |
| L3.4 | velocity run 0 v the parked Guard (L0.12's rule: reach ≥ strike_straight's − 0.05, first passing read) | 1 × 1.0 | ≤ 0.6 / ≤ 0.25 (T67: 0.031) | 1.0 |
| L3.5 | skills run 0 v the parked Guard (PASS: reach ≥ the mark at the **final** checkpoint; the full budget; mark re-set 25 Nov 2026, §2, was 900 of 1,000; the CPU ceiling run of the mark goes in this task's folder, 0 GPU-h) | 1 × 1.5 | 0.9 / 0.35 | 1.5 |
| L4.1 | held-command arm (`scripts/ste_l3_held_arm.py`, every script held 12 ticks v closed loop, both teams) | CPU | 0 | 0.0 |
| L4.2 | scoring suite on known players (the pooled row, best single choice and choice share on scripted teams) | CPU | 0 | 0.0 |
| L5.1 | velocity route, pool + mask, Guard then Strike | 2 × 1.0 | 0.6 + 0.9 / 0.23 + 0.40 | 1.8 |
| L5.2 | skills route, pool + mask, Guard then Strike | 2 × 1.5 | 0.9 + 1.34 / 0.35 + 0.60 | 2.6 |
| L5.3 | velocity route, **pool only** (the attribution control), Guard side | 1 × 1.0 | 0.6 / 0.23 | 1.0 |
| L5.4 | skills route, pool only, Guard side (with its own skills pilot, question 1) | 0.6 + 1.5 | 0.4 + 0.9 / 0.15 + 0.35 | 2.1 |
| L6.1 | per-route reads and the route comparison (section 3) | CPU | 0 | 0.0 |
| L6.2 | export and reload check, both routes (section 5) | CPU (a GPU reload at most) | < 0.05 | 0.1 |
| | **total of the caps** | | **≈ 8.4 / ≈ 3.5** | **11.4** |

**Launch condition for L5.2's Strike run (B1):** the skills pilot must confirm the ×2.25 factor: its measured
game-steps per second, with the dispatch and the pool, at least 1/2.25 of the velocity pilot's at the same size. If it
is slower, the lead re-plans the asks and caps (announced) before the launch.

The remaining 8.6 GPU-h are **unallocated**. They are for re-runs after a failed control, and for an added read (for
example a second seed or the tier-2 cross-check of question 4). Each use is announced with its question, trigger and
hours (owner's side-track rule). Order: L3.2 and L3.3 (pilots) and L3.1 (smoke) first, then the fill step, then run 0
per route (L3.4, L3.5), then L5.1-L5.4, then L6. L4.1 and L4.2 run on the CPU at any time. The pool-only controls run
the Guard side only: a Guard run needs no run 0 (the Guard recipe is T41's), so attribution costs one run per route.

## 2. The game and the gate files

- **Game:** G0's main game, T44's `configs/ste_l011/base.toml` (3v3, the 1-for-1 nearest-pair tag at 1.6 m, zone 1.6 m),
  T44's 1,000 starts and reference cells.
  - **Landing off** (R32): there is no `[landing]` table, so `LandingCfg.enabled` is False.
  - **The even filter split** (R31): `FilterCfg.share = "equal"`.
  - The estimate error is off, as T44's base (question 2).
- **Gate files**, one template (`tests/test_ste_l3_pipeline_gates.py` checks the four differ only in `[run] task`,
  `[learner]` and the skills run 0 mark):
  - `configs/ste_l3/velocity_gates.toml` (task L5.1);
  - `skills_gates.toml` (L5.2);
  - `velocity_poolonly_gates.toml` (L5.3);
  - `skills_poolonly_gates.toml` (L5.4).
- **Recipe:** T46's (T41 recipe, IPPO, per-slot MLP [128, 128], 12-tick decisions), 16,384 games, **550 M game-steps
  per run on both routes** (the same budget, R19), confirmed by each pilot.
- **Seeds and pool draws:** the same seeds in all four files (training 140201 Strike / 140202 Guard, run 0 140203,
  curve 140900, clips 140950), and the same pool (`[pool] enabled, seed 140001`). Every script of the other team except
  `random`, one per game by `pool_draw(seed, slot, k)`, so both routes see the same opponent for the same (slot, game
  number). Run 0 keeps its parked Guard.
- **Learner:**
  - Velocity: `[learner] action = "velocity", mask_absent`.
  - Skills: `choice = "two_level"` with list A, `strike_straight` first (run 0's known answer), entropy 0.01 per head,
    and the comment that a `kl_threshold`, if ever set, is for the sum of the two per-head KLs.
  - The mask is on in the main files and off in the pool-only controls.
- **Skills run 0 mark:** `[run0] skills_reach_min = 0.90` (it loads only with `eval_games = 1000`).
  **Addendum, 25 Nov 2026 (DRAFT, before the ceiling run): 0.90 is wrong and is re-set.** It came from the 1v1 screen
  (T66). In the 3v3 base game on T44's starts the parked-centre Guard holds against every Strike script (T70: straight
  534, flank 450, high 466, low 430, sacrifice 525, converge 986 of 1,000), so no constant choice reaches 900.
  - The new mark is `skills_reach_min = (k_best − 0.05 × 1,000) / 1,000`, where k_best is the most reaches of any
    constant choice of the two-level Strike team (2 team strategies + 4^3 free combinations, each held for the whole
    game).
  - k_best comes from `scripts/ste_l3_run0_ceiling.py` (CPU of record, 1,000 games, controls: the one-script choices
    replay T44, the choice log, plumbing).
  - The mark must lie above the untrained team's Wilson upper bound (free + strike_straight, 466 of 1,000: 0.497),
    else the lead re-plans run 0 and no skills run 0 is launched.
  - The number: `____` (the lead fills it after the full run, in both skills gate files, before any skills run 0).
  - Full text: [L3_SLICE2_DESIGN.md](L3_SLICE2_DESIGN.md), "Addendum, 25 Nov 2026".
- **The fill step** (each file's header): the fill rule of section 2b.

## 2b. What differs between the routes (fairness), and the fill rule

The two routes share the game, the opponents (the same pool draws), the starts, the seeds, the step budget, the
network size, the PPO settings and the scoring. They still differ in these ways, by design or by construction, and
each read names them:
- **Action:** a velocity command held 12 ticks against a two-level skill choice held 12 ticks, the chosen skills
  running closed loop every tick inside each hold. This reaction-speed advantage belongs to the skills route; L4.1
  measures it for the scripts.
- **Entropy:** 0.0 for the velocity route (T41's recipe; its Gaussian log-std is learned and frozen on yaw) against
  0.01 per head for the skills route (two categorical heads).
- **The start:** the velocity route starts at a zero mean (standing still); the skills route starts at p(free) = 0.5,
  playing free + its first drone skill (strike_straight / guard_parked_centre) at argmax.
- **The Strike recipe:** `side_overrides.strike` is filled per route from that route's own pilot, so it may differ
  between the routes.

**The fill rule** (pre-registered; the lead applies it after both pilots and before any run 0):
1. **`side_overrides.strike` of each route** is the value its own pilot's pre-registered rule picks
   (`exploit.strike_recipe` over the probes against g*). The same value goes into that route's pool-only file.
2. **`game_steps_per_run`** is one number for all four files: the smallest of 550,000,000 and each pilot's projected
   game-steps that fit its run ask (pilot.json `projection`), rounded down to whole updates. One update is
   32 × 12 × 16,384 = 6,291,456 game-steps; at 550 M that is 88 updates, 553,648,128 game-steps. If the two pilots
   disagree, the smaller number holds for both routes (the same budget, R19). If it falls below 60 updates
   (377,487,360), the lead re-plans before any run (the budget would no longer be T46's) and announces it.

## 3. Reading words (fixed before any run; R22: two reviewers; INFO; "pipeline check, not for flight")

Every word reads **"these two trained policies"** (one seed each), never "the route". The intervals cover the sampling
of the 1,000 starts only, not the spread over seeds.

**Per route, the required tasks and the word.** PIPELINE WORKS needs all of these:
- the route's pilot (L3.2 or L3.3), its controls PASS;
- run 0 (L3.4 or L3.5);
- both main runs (L5.1 or L5.2), every control PASS, trained to the step budget;
- the final scoring of each main run;
- the export and reload check of each main run's policy (L6.2).

The pool-only controls (L5.3, L5.4 and L5.4's pilot), the held-command arm (L4.1) and the scoring-suite check (L4.2)
are not part of a route's word; they are separate reads, below. The words:
- **PIPELINE WORKS:** every required task as above. The final phase writes the cells against every script of the
  other team, the pooled row, the best single fixed choice and (skills) the choice share. The export reloads in a
  fresh process with its golden rows matching (section 5).
- **PIPELINE WORKS, RUN 0 FAILED:** run 0 reads FAIL at the full budget. The trainer did not learn the Strike task
  against the parked Guard (the word "easy" dropped 25 Nov 2026: in 3v3 no constant choice is near 1,000, §2) at this
  budget. The Strike run is not launched; the Guard run, its scoring and its export and reload must hold as
  above.
- **PIPELINE WORKS, RUN 0 INCONCLUSIVE:** run 0 stopped at its cap reserve before the budget. This is not a failure to
  learn: the run did not get its time.
  - Velocity route: the lead may record a decision (`--accept-learner-control`, L0.12's rule) and launch the Strike run.
  - Skills route: the Strike run is never launched (PASS only), and the lead re-plans run 0.
  - The Guard side reads as above.
- **PIPELINE DOES NOT WORK at <stage>:** a control fails (exit 6), a run crashes or exits 5, or an export does not
  reload with its golden rows. The stage and the first failing control are named.

**The separate reads:**
- **Not given:** a separate read (attribution, held arm) that no folder was named for reads **not given**, a fact,
  not a result. The cells against `strike_high` and `strike_low` carry the label "vertical response not fitted in
  tier 1" wherever they are shown.
- **Attribution (L5.3, L5.4):** pool + mask against pool only, Guard side. Read with the paired words below. A
  pool-only run (or L5.4's pilot) that fails or crashes reads **ATTRIBUTION NOT READ at <stage>**; the route's word does
  not change.
- **Held-command arm (L4.1):** per script and opponent, the held against the closed-loop wins, INFO. A failed control
  (hold 1 ≠ the reference) reads **HELD ARM NOT READ**.
- **Scoring-suite check (L4.2):** on scripted teams with known answers (the pooled row equals the mean of the script
  cells on the reference; the best single choice equals the reference's best; the choice share of a fixed choice is
  one skill). **Required before the route comparison is written.** A failure reads **COMPARISON NOT READ** until fixed.
  Driver: `scripts/ste_l4_suite.py --out <dir>` (through `ste_job.py`, task L4.2, CPU, T44's 1,000 starts) writes
  `suite_check.json`, which the reader (`scripts/ste_l6_read.py`) reads.

**The route comparison (INFO), per side, on T44's 1,000 starts.** K = 6 opponent scripts for the trained Guard team
(the Strike scripts), K = 5 for the trained Strike team (the Guard scripts).
- **The headline is the worst cell:** the trained team's lowest rate over the opponent cells, with its Wilson 95 %
  interval.
  - The interval of a minimum over K cells is optimistic (the minimum is biased low and its interval is not adjusted
    for the K).
  - The cells against `strike_high` and `strike_low` are labelled "vertical response not fitted in tier 1"
    (z_up_info). The headline is the worst cell **among the other cells**, and the z_up_info cells are shown beside it.
  - Each policy's worst cell against the other's: **above / below** if the Wilson intervals are disjoint, else **not
    distinguishable**.
- **Paired same-cell differences:** the two worst cells may be against different opponents. So, for every opponent
  cell, the difference between the two policies is taken paired by start (the same starts), with a 95 % interval from
  the per-start standard error. **Above / below** if it excludes 0, else **not distinguishable**. Reported for every
  cell, the headline cell first.
- **The pooled row:** the mean of the K cell rates. Its difference is paired by start with the per-start standard
  error, read with the same words. Flagged when trivial cells (rate 0 or 1) pull the mean.
- **Each policy against the best single fixed choice over the pool** (the best script played every tick closed loop,
  on the same starts): paired, the same words.
- **Choice shares (skills, R30):**
  - per opponent cell, the share of each flown skill or strategy over all decisions;
  - by decision index (0, 1, 2, 3-5, 6-11, 12+), the late bins survivor-biased.
  - Described, not worded. A share that changes with the opponent on the same starts is the only sign of adaptation
    this check can give.

**What it cannot show** (each read says so):
- one seed per route and side (no seed spread; the intervals are over the starts only);
- the 1.6 m tag only;
- tier 1 training only (tier 2 only through the scripted smoke);
- no flight;
- the estimate error off;
- scripted opponents only (no self-play or league);
- **no held-out opponent:** every scored script was in the training pool, so adaptation to an unseen opponent is not
  tested;
- today's per-slot MLP and observation v0.1 (not the attention encoder or v0.3);
- a policy without memory or opponent identity (it can adapt only to what it observes);
- the skills route's closed-loop advantage (measured for the scripts by L4.1);
- a 550 M budget, not a budget of record.

A second seed or any other read paid from the unallocated hours is labelled **an added read**. It never replaces a
pre-registered one.

## 4. The Isaac smoke of the tier-2 skills replay (task L3.1)

**To build first:** `scripts/ste_l3_isaac_smoke.py`, a short driver, plus its CPU test on the reference world. It is
not built yet. It plays slice 3's step-3(b) replay on an Isaac world:
- each team strategy and each uniform drone skill, as a fixed two-level team, against the same scripts on tier 2;
- three mixed "free" combinations against the composite player;
- both teams, T44's first 1,000 starts.

Launch, after `nvidia-smi` and `scripts/isaac_preflight.sh --approved-headless` both exit 0, alone on the GPU, at the
lead's go (as T71):

```
cd ~/AirStack-starling-max2-dev/svg_training && unset PYTHONPATH
~/miniconda3/envs/env_isaaclab/bin/python scripts/ste_job.py launch --task L3.1 --name l3_isaac_smoke \
  --run-dir runs/<d>_ste_l3_isaac_smoke --min-s 60 --gpu-h 0.3 --settings configs/ste_learning.toml -- \
  ~/miniconda3/envs/env_isaaclab/bin/python scripts/ste_l3_isaac_smoke.py --gates configs/ste_l3/skills_gates.toml \
  --run-dir runs/<d>_ste_l3_isaac_smoke --cap-h 0.3 --headless --games 1000
```

(The form of L2.6's smoke, `ste_learning/drafts/L2_6_SPEC.md`, run from the machine's development worktree
`~/AirStack-starling-max2-dev`, its `svg_training/` folder; the driver's flags as built, section 4's script.)

It must check (QC's list), each a control that ends the smoke on failure:
1. **CUDA replay tolerance:** each fixed-choice cell against its script cell on Isaac. Outcome counts within
   `replay_count_tol_cuda_games` (10), differing games at most `replay_differ_tol_cuda_games` (20); the rule of
   `exploit.replay_ok` on CUDA.
2. **Device placement:** every dispatch, pool and learner tensor on CUDA; no host read inside a tick (the step's
   batched rule).
3. **Snapshot reload across devices:** a two-level learner's `saved()` from CUDA reloads on the CPU through
   `skill_team_from_modules` (and back). Logits within 1e-5 and greedy choices equal on recorded tier-2 observations.
4. **Clips:** two tier-2 clips of a fixed two-level team on the CPU clip starts (as CLIP-T2) that play on GitHub.
5. **Non-finite and stale:** non-finite actions and wrenches 0, and `physics_nonfinite` 0. Upsets are recorded. In a
   `DecisionEnv` loop on Isaac the stale-tick share is reported (0 in `play_cells`).
6. **Throughput:** game-steps per second of the two-level dispatch on Isaac, against one script, recorded for the
   budget projection.

No tier-2 skills run of record starts before this smoke passes (slice 3 design §3).

## 5. Export and reload (task L6.2)

`ste-policy-1` (ARCHITECTURE §3) is defined for observation v0.3 (81 inputs). The pipeline check runs v0.1 (71) with
one network per slot, so it uses its own schemas (lead, 24 Nov 2026), both written by `ste/export.py`:
- **Velocity route** (`policy_schema = "ste-check-velocity-0"`):
  - per slot `policy_<team>_<slot>.onnx`, input `obs [B, 71] float32` (raw observation; the observation scaler is
    folded into the graph), output `action_mean [B, 4]` (deterministic, the Tanh inside);
  - `interface.toml`: STANDARDS §3 rule 1's fields, `team`, `hold_ticks = 12`, `tag_radius_m`, `filter_share`, the
    ONNX sha256s, and 8 `[[golden]]` rows per slot (71 inputs, 4 outputs).
- **Skills route** (`policy_schema = "ste-check-skills-0"`):
  - per slot `policy_<team>_<slot>.onnx`, input `obs [B, 71]`, output `logits [B, T+1+K_d]`;
  - `interface.toml` additionally carries:
    - the skill lists and `free_index = 0` (`skills.skills_meta`);
    - the leader rule;
    - the hold rule (the choice held 12 ticks, the chosen skill closed loop every tick);
    - the sha256 of `opponents/scripted.py`;
    - the team size;
    - 8 `[[golden]]` rows per slot: the logits, both heads' argmax, the flown skill and the final command on recorded
      observations.
- **Status, required:** `status = "pipeline check, not for flight"` in `interface.toml` and in every ONNX file's
  metadata (`metadata_props`). The reload refuses a file without it or with another value.
- **The reload check** runs in a fresh Python process with **onnxruntime 1.20.1 (CPU) as the primary runtime** (owner
  approved, 24 Nov 2026; the `export` extra in `pyproject.toml`) and `onnx.reference.ReferenceEvaluator` (numpy) as an
  independent second check on the same files. Whether onnxruntime or torch can run in the AirStack ground container is
  UNVERIFIED (ARCHITECTURE §3, line 214); this check does not settle it.
  - It refuses a sha256, schema or status mismatch.
  - The golden rows: outputs within 1e-6 (absolute; the ONNX evaluator and torch round differently, so not bit for
    bit), the argmax of each head, the leader's choice, the flown skill and the skill names and lists exactly. For the
    skills route the final commands come from the pinned `scripted.py`, within 1e-6.
- **The export command:** `scripts/ste_l6_export.py --run-dir <run> --out <dir>` (through `ste_job.py`, task L6.2,
  CPU) loads `agent_final.pt` through the route's loader and records `source_checkpoint_sha256` and the run's
  `gates_sha256` in `interface.toml`; the reader refuses an export whose checkpoint sha256 is not the run's.
- **Flight side:** flying the skills route needs a 20 Hz port of the scripts into the game node. That is L7, an
  AirStack change the owner gates; nothing here touches AirStack.

## Lead's answers (24 Nov 2026, after two reviewers, no blocking finding)

1. Strict `[learner]` matching kept: L5.4 has its own pilot.
2. Estimate error off.
3. Build the Isaac smoke driver, `ste/export.py` and the comparison reader. Schema names `ste-check-velocity-0` and
   `ste-check-skills-0` accepted.
4. The smoke is the pipeline check's tier-2 part.
5. The RTX 5090 on weekdays.
