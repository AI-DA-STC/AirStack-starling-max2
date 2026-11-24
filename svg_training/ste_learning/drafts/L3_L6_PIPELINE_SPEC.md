INTERNAL · spec of the L3-L6 pipeline check of the STE learning track (owner R23: cap 20 GPU-h, "pipeline check, not for flight"; R19 both routes; R30 two-level skills; R31 even filter split; R32 landing off): the budget split, the game and gate files, the reading words fixed before any run, the Isaac smoke and the export; DRAFT for the lead and two reviewers (R22), NO run launched · gate files: [configs/ste_l3/](../../configs/ste_l3/) · budget: [configs/ste_learning.toml](../../configs/ste_learning.toml) `[budget_l3_l4_l5_l6]` · design notes: [L3_TWO_ROUTES_DESIGN.md](L3_TWO_ROUTES_DESIGN.md), [L3_SLICE2_DESIGN.md](L3_SLICE2_DESIGN.md), [L3_SLICE3_DESIGN.md](L3_SLICE3_DESIGN.md)

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
| L3.5 | skills run 0 v the parked Guard (PASS: reach ≥ 900 of 1,000 at the **final** checkpoint; the full budget) | 1 × 1.5 | 0.9 / 0.35 | 1.5 |
| L4.1 | held-command arm (`scripts/ste_l3_held_arm.py`, every script held 12 ticks v closed loop, both teams) | CPU | 0 | 0.0 |
| L4.2 | scoring suite on known players (the pooled row, best single choice and choice share on scripted teams) | CPU | 0 | 0.0 |
| L5.1 | velocity route, pool + mask, Guard then Strike | 2 × 1.0 | 0.6 + 0.9 / 0.23 + 0.40 | 1.8 |
| L5.2 | skills route, pool + mask, Guard then Strike | 2 × 1.5 | 0.9 + 1.34 / 0.35 + 0.60 | 2.6 |
| L5.3 | velocity route, **pool only** (the attribution control), Guard side | 1 × 1.0 | 0.6 / 0.23 | 1.0 |
| L5.4 | skills route, pool only, Guard side (with its own skills pilot, question 1) | 0.6 + 1.5 | 0.4 + 0.9 / 0.15 + 0.35 | 2.1 |
| L6.1 | per-route reads and the route comparison (section 3) | CPU | 0 | 0.0 |
| L6.2 | export and reload check, both routes (section 5) | CPU (a GPU reload at most) | < 0.05 | 0.1 |
| | **total of the caps** | | **≈ 8.4 / ≈ 3.5** | **11.4** |

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
- **The fill step** (each file's header): each route's pilot fills `[trainer] side_overrides.strike` (the pre-registered
  Strike recipe rule over the probes against g*; the probes are not on the pool) and confirms `game_steps_per_run`. The
  same number goes in all four files.

## 3. Reading words (fixed before any run; R22: two reviewers; INFO; "pipeline check, not for flight")

**Per route, one of three words:**
- **PIPELINE WORKS:** all of the following hold.
  - The pilot completes and its controls PASS.
  - Run 0 reads PASS (velocity: L0.12's rule; skills: ≥ 900 of 1,000 at the final checkpoint).
  - Both sides train to the step budget, with every control PASS (before, curve, final, INFO; non-finite 0).
  - The final phase writes the score cells against every script of the other team, the pooled row, the best single
    fixed choice and (skills) the choice share by decision index.
  - The export reloads in a fresh process with its golden rows equal (section 5).
- **PIPELINE WORKS, RUN 0 FAILED:** everything works up to run 0, which reads FAIL (or INCONCLUSIVE). The Strike side
  is not launched; the Guard side reads as above. Meaning: the learner did not learn the easy task at this budget.
- **PIPELINE DOES NOT WORK at <stage>:** a control fails (exit 6), a run crashes or exits 5, or the export does not
  reload with its golden rows. The stage and the first failing control are named.

**The route comparison (INFO only).** Per side, on T44's 1,000 starts:
- **The worst cell is the headline:** the trained team's lowest rate over the opponent scripts, with its Wilson 95 %
  interval. Each route's worst cell against the other's reads **above / below** when the intervals are disjoint, else
  **not distinguishable**.
- **The pooled row:** the mean of the K cell rates. The difference between the routes is paired by start (same starts),
  with a 95 % interval from the per-start standard error. **Above / below** when it excludes 0, else **not
  distinguishable**. Flagged when trivial cells (rate 0 or 1) pull the mean.
- **Each route against its best single fixed choice over the pool** (the best script played every tick closed loop, on
  the same starts): the same paired words.
- **Attribution (Guard side):** pool + mask against pool only, per route, the same paired words. It says what the mask
  changes on this one seed.
- **Choice share by decision index** (skills): described, not worded. The late bins hold only long games
  (survivor-biased).

**What it cannot show** (each read says so):
- one seed per route and side (no seed spread);
- the 1.6 m tag only;
- tier 1 training only (tier 2 only through the scripted smoke);
- no flight;
- the estimate error off;
- scripted opponents only (no self-play or league);
- today's per-slot MLP and observation v0.1 (not the attention encoder or v0.3);
- a policy without memory or opponent identity (it can adapt only to what it observes);
- the skills route's closed-loop advantage (measured separately by L4.1);
- a 550 M budget, not a budget of record.

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

(The form of L2.6's smoke, `ste_learning/drafts/L2_6_SPEC.md`; the driver's own flags are fixed when it is built.)

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
one network per slot, so it needs its own schemas (question 3), both written by `ste/export.py`. That module is not
built yet: ARCHITECTURE's export row, status N.
- **Velocity route** (`policy_schema = "ste-check-velocity-0"`, PROPOSED):
  - per slot `policy_<team>_<slot>.onnx`, input `obs [B, 71] float32`, output `action_mean [B, 4]` (deterministic,
    the Tanh inside), the observation scaler folded in;
  - `interface.toml`: STANDARDS §3 rule 1's fields, `team`, `hold_ticks = 12`, `tag_radius_m`, `filter_share`, the
    ONNX sha256s, and 8 `[[golden]]` rows per slot (71 inputs, 4 outputs).
- **Skills route** (`policy_schema = "ste-check-skills-0"`, PROPOSED):
  - per slot `policy_<team>_<slot>.onnx`, input `obs [B, 71]`, output `logits [B, T+1+K_d]`;
  - `interface.toml` additionally carries:
    - the ordered player list, `team_strategies`, `drone_skills` and `free_index = 0` (`skills.skills_meta`);
    - the leader rule;
    - the hold rule (the choice held 12 ticks, the chosen skill closed loop every tick);
    - the sha256 of `opponents/scripted.py` and its constants;
    - the team size;
    - 8 `[[golden]]` rows per slot: the logits, both heads' argmax, the flown skill and the final command on recorded
      observations.
- **The reload check:** in a fresh Python process, load the ONNX files with onnxruntime (UNVERIFIED in the AirStack
  container, ARCHITECTURE §3) and the interface. Refuse on a sha256 or schema mismatch. The golden rows must be equal
  (bit for bit on the CPU, the velocity commands; for the skills route the logits within 1e-6 and the choices, flown
  skill and command exactly, with the scripts loaded from the pinned `scripted.py`).
- **Flight side:** flying the skills route needs a 20 Hz port of the scripts into the game node. That is L7, an
  AirStack change the owner gates; nothing here touches AirStack.

## Open questions for the lead

1. **The skills pool-only control's pilot:** the run-of-record check compares the whole `[learner]` table, `mask_absent`
   included, so the pool-only skills file needs its own pilot (0.6 GPU-h, in L5.4's cap). A one-line change could leave
   `mask_absent` out of that comparison (the mask does not change the rates), saving 0.6. Keep strict (proposed), or
   change it?
2. **Estimate error:** T44's base game has it off, so the known answers and T44's cells hold (proposed). L1.10's main
   read used the nominal error (L1.7). Off for the pipeline check?
3. **Build items before the runs:** the Isaac smoke driver (section 4); `ste/export.py` with the two pipeline-check
   schemas (section 5); a small reader for the route comparison (section 3, L6.1). Schema names as proposed?
4. **Tier-2 cross-check of the finals** (PLAN row L6, "tier 1, tier 2"): the tier-2 scoring drivers do not take the
   skills route yet. Proposed: the pipeline check's tier-2 part is the smoke only, and a tier-2 re-score of the four
   finals comes from the unallocated hours after the drivers are wired. Agree?
5. **Machine:** the asks are the laptop's worst case; the RTX 5090 is expected to use about 40 % of them. Run on the
   5090 on weekdays as usual?
