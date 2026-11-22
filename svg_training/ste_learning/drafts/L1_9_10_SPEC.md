INTERNAL · spec written 23 Nov 2026 by the L1.9/L1.10 implementer, before any of its runs (main track; costed draft rows
L1.9 and L1.10). DRAFT until the lead's two reviews.

# L1.9 and L1.10: the 1v1 read and the tag-draw read (INFO)

**Why.** G0 rows 6–8 and 17: every trained team so far is 3v3 while the demo is 1v1, and 1v1 was never screened at
1.15 m (G0_REPORT, rows 6–8); the tag radius on the real drones is a measured distance with error, so a team trained at
exactly 1.6 m may lean on that exact value (row 17). All tier 1 (fast engine; ruling A12), laptop RTX 5070 Ti, one seed
per run, observed in the training simulator; INFO (no pass/fail gate; the controls are gated).

**The lead's binding calls.** (1) Both tasks TRAIN with the nominal estimate error of L1.7
(`configs/ste_l1/base_err_nominal.toml`, `commander_reads = "true"`; EXPLORATORY values, T63). (2) Each trained team is
scored on its own training game AND on the same game without the error (INFO); for L1.10 (lead's ruling, 23 Nov 2026,
fix round 1) the MAIN read is the fixed 1.6 m game WITH the nominal error (`base_err_nominal.toml`: the task row says
"scored at the fixed tag", and L1.7 makes the error the realistic default), and the tag-draw training game (with error)
and the fixed 1.6 m game without the error (the driver's scoring game) are INFO. (3) Every trained team is scored against
every script of the other team (`scripts/ste_score_matrix.py`; worst cell first). (4) New training seeds.

**How the scoring is split (design, from a measured fact).** The estimate error is drawn per batch slot, so two
identical script cells in one batch do not replay each other with the error on (CPU: end steps differ in 4 of 6 games;
`tests/test_ste_l19_l110.py::test_why_the_driver_scores_without_the_error…`). The best-response driver's known-answer
controls (script cells replay the reference game for game; the untrained team plays as the zero script) need that. So:

- the driver (`scripts/ste_exploit_l012.py`) TRAINS on the with-error game (`train_game`) and SCORES on the no-error game
  (`game`), where every control has its known answer; run 0 also trains on the training game;
- the **with-error read is the main reading**: `scripts/ste_score_matrix.py` with `reference = false` (the player and
  every script of its team against each opponent script, in one batch, on the same starts; plumbing controls only), on
  L1.9's training game (`base_1v1_err.toml`) and, for L1.10, on the fixed 1.6 m game with the error
  (`base_err_nominal.toml`; the tag-draw training game is an INFO game of the same matrix);
- the no-error read is INFO: the driver's verdict, and the score matrix on the no-error game (script cells replayed;
  for L1.10 this is T46's game).

## The runs

| Task | Run | Trains on | Scored by the driver on | Opponent (training) | Seed |
|---|---|---|---|---|---|
| L1.9 | screen (CPU, scoring only) | — | `configs/ste_l011/base.toml` (group base_1v1) and `configs/ste_l1/base_1v1_1p15.toml` (group tag_1p15_1v1), 1v1, 1,000 games per cell, no error | every script v every script | game seed 110000 (CPU draw: a new 1v1 start set) |
| L1.9 | run 0 | `base_1v1_err.toml` (1v1, 1.6 m, error) | base, 1v1, the screen's starts | guard_parked_centre | 130193 |
| L1.9 | Guard | same | same | s* of base_1v1 (screen) | 130192 |
| L1.9 | Strike | same | same | g* of base_1v1 (screen) | 130191 |
| L1.10 | run 0 | `base_err_tagdraw.toml` (3v3, tag drawn per game uniform in [1.5, 1.7] m, error) | base (fixed 1.6 m, no error), T44's 1,000 starts and cells: T46's game | guard_parked_centre | 130203 |
| L1.10 | Guard | same | same | strike_straight (T46's s*) | 130202 |
| L1.10 | Strike | same | same | guard_mark_edge (T46's g*) | 130201 |

Recipe: T46's (L0.12's `[trainer]` as filled: the T41 recipe, the shaped Strike recipe), 0.55 B game-steps per run
(88 updates of 16,384 games). Gate files: `configs/ste_l1/l19_screen_gates.toml`, `l19_gates.toml`, `l110_gates.toml`;
each equals its L0.11 / L0.12 source but for the keys listed in its header (tests check it). The drawn radius is not
an input to the networks. The 1v1 starts are new (T44's 1v1 starts are in no reference file and a CPU generator does not
reproduce a CUDA draw); `l19_gates.toml` holds `FILL_` values until the screen has run (its header lists the steps).

## What each run answers (pre-registered)

- **L1.9 screen, group tag_1p15_1v1 (G0 row 8).** "At 1v1 and tag 1.15 m, the best scripted Guard holds H of 1,000 at
  worst over the Strike scripts (g*), the best scripted Strike reaches R of 1,000 at worst (s*)" — the L0.11 maximin
  rule and words, every cell with its Wilson 95 % interval; "Guard-trivial looking" if H ≥ 0.8 (L0.11's `trivial_at`).
- **L1.9 screen, group base_1v1 (the runs' reference).** Cross-check, INFO: each cell against T44's size_1v1 cell
  (other starts): "agrees with T44" when the Wilson intervals overlap, else "differs from T44 (other start set)".
- **L1.9 Strike.** Can a 1v1 Strike drone trained with the error beat the best 1v1 Guard script (g*)? T44 at 1.6 m: g*
  guard_mark_edge held every game against every Strike script, so the script baseline is near 0 reaches.
- **L1.9 Guard.** Does a 1v1 Guard drone trained with the error hold as well as the best Guard script against s*? If the
  best script already holds ≥ 990 of 1,000 against s*, a gain is impossible by construction: the read is then a
  **ceiling read** ("holds as the script: intervals overlap" or "below the script"), said so in every table; the
  cross-play worst cell is the informative number.
- **L1.10 Guard and Strike.** With the tag drawn in 1.5–1.7 m during training, does the trained team still do what T46's
  fixed-tag team does at the fixed 1.6 m tag? Compared with **T46 at 1.6 m** (Strike 636 of 1,000 v guard_mark_edge;
  Guard 913 v strike_straight; L1.12's cross-play T57 for the Guard team: worst 913).

**Reading words, fixed now (no category, no "validated"; one seed per run, so a Wilson interval covers scoring noise
only, never seed-to-seed spread):**

1. Main (with error, score matrix, per opponent script x, worst cell first; L1.9 on its training game, L1.10 on the
   fixed 1.6 m game with the error): trained team's wins N with Wilson 95 %, the best script of its team against x in
   the same batch M. The best script is picked per cell, after the fact, from several scripts in the same batch, so the
   comparison leans toward "below" (a maximum of several noisy counts is biased up); the words below say it. "**above the best script with the error**" if trained Wilson
   lower bound > the script's upper bound; "**below the best script with the error**" if trained upper < script lower;
   else "**not distinguishable from the best script with the error**". With the error, the cells are paired on starts but
   not on error draws (and, on the tag-draw game, not on radius draws): no paired counts are read.
2. INFO (no error, the driver): its side status as L0.12 defines it (gain / weak / INCONCLUSIVE, learned rule: trained
   lower > untrained upper), with the score matrix on the no-error game (paired counts reported, not pre-registered).
3. INFO, error effect on the trained team: "the error changes the result: N with v M without" only if the trained team's
   two intervals (with, without) do not overlap; otherwise "**no change detected (intervals overlap; the test cannot see
   shifts under about 40–60 games)**". Same starts, different draws (as T64).
4. L1.10 v T46 (no error, fixed 1.6 m, the same 1,000 starts): "**different from T46**: N v M" if the Wilson intervals do
   not overlap, else "**not distinguishable from T46**". Not attributable to the tag draw alone: L1.10 differs from T46 in
   three things (the tag draw, the estimate error in training, the seed). Its with-error read is compared with T46's
   scripts with the error (same batch), never with T46's no-error numbers.
5. Run 0 (both tasks): L0.12's criterion and words (PASS / FAIL / INCONCLUSIVE); a FAIL means no Strike run.

**Limits, stated in every result.** Tier 1 only (L1.9's tier-2 check, row L1.9 "check 2", is not in these files: a later
task); one network per side; EXPLORATORY error values from one hover log; the 1v1 game keeps the 3v3 observation padding
(5 Guard, 3 Strike slots); training at 1v1 and with the tag drawn changes nothing in the game itself; nothing flown.

## Time and GPU-hours

Each run's cap by the driver's time rule (update N starts only if O + B + (N−1)U + ⌊(N−1)/10⌋K ≤ C − R): the evaluation
plays the no-error game as T46's, so B = 100 s and K = 56.5 s (L0.12b's sizing; T46's base Strike reads 53.2 s at
most), and U = 25 s = T46's base Strike update maximum 19.6 s × 1.27, a margin for the error's training cost, which is
**unmeasured on a GPU**; R = 640 s. N = 88 fits at **C = 0.94 h** (not at 0.92). 1v1 timings are unmeasured too (the 3v3
sizing is an upper bound). Run 0's first updates are the check: if its median update exceeds 25 s, stop and re-size
before any run of record.

Expected use = T46's measured use × 1.28, the same error factor the time rule allows per update (25 / 19.6): run 0
0.13 (L0.12b's 0.10), Guard 0.51 (T46 base 0.40), Strike 0.75 (T46 base 0.59). The score matrices (the main reading)
launch last, so the largest launch total is theirs.

| Task | Launch order (each asks) | Expected use | Task cap | Fits? |
|---|---|---|---|---|
| L1.9 | screen (CPU, 0) · run 0 (0.94) · Guard (0.94) · Strike (0.94) · 2 score matrices (0.15 each) | 0 + 0.13 + 0.51 + 0.75 + 2 × 0.05 ≈ 1.50 | 1.6 | yes, tight: largest launch total 1.59; about 0.1 left for the row's tier-2 check (costed 0.05–0.6) |
| L1.10 | run 0 (0.94) · Guard (0.94) · Strike (0.94) · 2 score matrices (0.2 each) | 0.13 + 0.51 + 0.75 + 2 × 0.1 ≈ 1.59 | 1.7 (was 0.9) | yes: largest launch total 1.69 (at 0.9 run 0 alone, asking 0.94, did not fit) |

Caps moved (23 Nov 2026, fix round 1, announced to the owner: L1.10's runs need 1.7 at the time rule): L1.10 0.9 →
1.7 with 0.6 from L1.8 (1.2 → 0.6, used 0.598, T64), 0.1 from L1.6 (0.1 → 0.0) and 0.1 from L1.15 (0.3 → 0.2, used
0.154, T61); the L1 task caps still sum to 9.1 (`configs/ste_learning.toml`). L1.9 keeps 1.6: about 0.005 GPU-h of
margin at its last launch and about 0.1 for its tier-2 check (row L1.9 "check 2", costed 0.05–0.6); if that check needs
more, the 5090 session moves hours to L1.9 first, announced to the owner before it does.
1v1 is likely cheaper than these 3v3 figures (unmeasured).

**Two further unknowns, checked at run 0.** (a) The L1.9 reference is made on the CPU and replayed on CUDA by the
driver within its tolerances (10 holds or reaches, 20 differing games); CPU and CUDA agreed game for game at 3v3 (T44
follow-up), never checked at 1v1: run 0's controls batch is the check, and a CUDA screen (same gate file with device
"cuda", a GPU job) is the fallback. (b) The error's training cost per update (above).

## Launch commands, in order

`python` = `~/miniconda3/envs/env_isaaclab/bin/python`; `<d>` the launch date; `<sha>` each gate file's sha256 at launch.
Check `nvidia-smi` first (STANDARDS: the GPU is shared).

```
# L1.9 — 1. the scripted 1v1 screen (CPU, 0 GPU-h; about 0.1-1.1 h of CPU)
scripts/ste_job.py launch --task L1.9 --name l19_screen --run-dir runs/<d>_ste_l19_screen --min-s 30 --gpu-h 0 \
  --settings configs/ste_learning.toml -- python scripts/ste_sweep_l011.py --gates configs/ste_l1/l19_screen_gates.toml \
  --run-dir runs/<d>_ste_l19_screen --cap-h 1.5
# 2. the reference, then fill l19_gates.toml (its header, FILL steps 1-3) and the two L1.9 score matrices' reference sha
python scripts/ste_l012_reference.py --t44 runs/<d>_ste_l19_screen --out configs/ste_l1/l19_reference.npz \
  --variants base_1v1,tag_1p15_1v1
# 2b. CHECK BEFORE RUN 0 (from the screen's results, no GPU): run 0's bar is the base_1v1 cell guard_parked_centre v
#     strike_straight, minus 0.05. T44 at 1v1: 307 reaches of 1,000 (the parked Guard held 693), so it can be won. If
#     the screen's cell shows 950 or more reaches (a bar of 0.90 or more: run 0 can hardly pass, and a FAIL would block
#     the Strike run for the wrong reason), do NOT launch run 0: run 0's opponent ([run0] opponent) must change first,
#     a gate edit before any run, announced to the owner with the reason, and the file re-hashed.
# 3. run 0 (asks 0.94, expected about 0.13 GPU-h)
scripts/ste_job.py launch --task L1.9 --name l19_run0 --run-dir runs/<d>_ste_l19_run0 --min-s 120 --gpu-h 0.94 \
  --settings configs/ste_learning.toml -- python scripts/ste_exploit_l012.py --run0 --gates configs/ste_l1/l19_gates.toml \
  --expect-gates-sha256 <sha> --run-dir runs/<d>_ste_l19_run0 --cap-h 0.94 \
  --pilot-json ste_provisional/pilots/2026-11-21_ste_l012_pilot/pilot.json
# 4. Guard (asks 0.94, expected about 0.51)
scripts/ste_job.py launch --task L1.9 --name l19_guard --run-dir runs/<d>_ste_l19_guard --min-s 120 --gpu-h 0.94 \
  --settings configs/ste_learning.toml -- python scripts/ste_exploit_l012.py --gates configs/ste_l1/l19_gates.toml \
  --variant base_1v1 --side guard --expect-gates-sha256 <sha> --run-dir runs/<d>_ste_l19_guard --cap-h 0.94 \
  --pilot-json ste_provisional/pilots/2026-11-21_ste_l012_pilot/pilot.json
# 5. Strike, only after run 0 PASS (asks 0.94, expected about 0.75)
scripts/ste_job.py launch --task L1.9 --name l19_strike --run-dir runs/<d>_ste_l19_strike --min-s 120 --gpu-h 0.94 \
  --settings configs/ste_learning.toml -- python scripts/ste_exploit_l012.py --gates configs/ste_l1/l19_gates.toml \
  --variant base_1v1 --side strike --expect-gates-sha256 <sha> --run0-json runs/<d>_ste_l19_run0/learner_control.json \
  --run-dir runs/<d>_ste_l19_strike --cap-h 0.94 --pilot-json ste_provisional/pilots/2026-11-21_ste_l012_pilot/pilot.json
# 6.-7. fill and run the score matrices (each asks 0.15, expected ~0.05)
scripts/ste_job.py launch --task L1.9 --name l19_guard_score --run-dir runs/<d>_ste_l19_guard_score --min-s 60 \
  --gpu-h 0.15 --settings configs/ste_learning.toml -- python scripts/ste_score_matrix.py \
  --settings configs/ste_l1/score_matrix_l19_guard.toml --run-dir runs/<d>_ste_l19_guard_score --cap-h 0.15
#    (the same with score_matrix_l19_strike.toml)

# L1.10 — task cap 1.7 GPU-h (raised 23 Nov 2026)
# 1. run 0, 2. Guard, 3. Strike: the L1.9 lines with --task L1.10, --gates configs/ste_l1/l110_gates.toml,
#    --variant base_tagdraw, run folders runs/<d>_ste_l110_{run0,guard,strike}, --gpu-h 0.94 / --cap-h 0.94
# 4.-5. score matrices: configs/ste_l1/score_matrix_l110_{guard,strike}.toml, --gpu-h 0.2 / --cap-h 0.2
```

Expected GPU-hours: L1.9 about 1.5 (largest launch total 1.59 of 1.6); L1.10 about 1.6 (largest launch total 1.69 of 1.7). Each run
writes its own videos (STANDARDS §8); the screen writes three 1.15 m clips.
