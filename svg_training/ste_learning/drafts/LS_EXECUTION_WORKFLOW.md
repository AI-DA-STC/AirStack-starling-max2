INTERNAL · DRAFT v3 for the owner's review: how route 3 (the learned-skills route) is executed towards a policy that is useful on the drones: what is added to the pipeline, which jobs run, in what order, on which machine, at what cost, and where the owner is asked · rulings R35 to R45 recorded; design review done (two reviewers, 25 Nov 2026) and folded in; **the owner gave the word for the build on 25 Nov 2026 (R42)**; nothing is built or run yet · the route explained: [../LEARNED_SKILLS_ROUTE.md](../LEARNED_SKILLS_ROUTE.md) (its stage order is older than R41); the task-level plan of LS1: [LEARNED_SKILLS_BRIDGE_PLAN.md](LEARNED_SKILLS_BRIDGE_PLAN.md)

# Route 3 execution workflow (draft v3, reviewed, 25 Nov 2026)

Version 1: the lead (Opus 5.5), 25 Nov 2026. Version 2, the same day (the lead, a Fable 5.2 session, with the advisor
tool): checked against the code, eight corrections. **Version 3, the same day:** the owner's rulings R39 to R41 change
the aim and the order (no GPU-hour cap, the heads trained again on the skill network on both sides, self-play brought
forward, the aim a policy that is useful on the drones); then the **design review** by two independent reviewers
(A: learning soundness and gates; B: build, pipeline, budget, export; Sonnet 5.5, read-only; the lead checked their
file references against the code) was folded in. Section 9 lists the review's findings, section 10 what each version
changed. This file is about route 3 only; "v3" is the third version of this file, not a route.

Stage LS1 and the head training (LS1.4) are given job by job. LS2, self-play and LS3 are outlines with their open
questions; each comes back with its own design note before code. Where this file and the plan differ, this file wins.

## 0. In one screen

| | Now, job by job | Later, outlines |
|---|---|---|
| Stages | **LS1 Distil** (the scripts copied into one skill network per team) → **LS1.4 Head training** (the heads trained again on the skill network, both sides) | **LS2 Fine-tune** (the skills trained by the game reward) → **Self-play** (the stage called LS4 League on the route page, brought forward by R41) → **LS3 Free codes** (skills no script has; last, an extension) |
| Adds to the pipeline | 3 new modules, 6 new scripts, 3 gate files, changes to the skills switch, the training driver's controls, the export and its reload check, the budget table and the status line | a pool entry for saved teams (self-play), a skill-level learner (LS2), a diversity reward (LS3) |
| Changes existing behaviour | no: a new setting whose default keeps today's behaviour bit for bit; existing checkpoints and exports load as before | the same rule |
| GPU-hours | no cap (R39). Asked per job: LS1 0.9, LS1.4 4.0 (two seeds per arm, clips included); expected use about 2.8 (estimate) | each note brings its hours |
| Build | four merges, about 2 to 4 days of agent work (estimate; the review added four pieces) | self-play and LS2 are new builds, 3 to 5 days each (estimate) |
| Owner asked | the limits and margins after the calibration read (R38) | each stage's design note; the held-out scripts |

"Distil" means fitting a network to imitate a behaviour. LS1 does not copy any pipeline code: the game, the trainer,
the scoring and the export of phases L1 to L6 are used as they are. What is copied is the **behaviour** of the eleven
hand-written scripts of `opponents/scripted.py` (Guard: parked at the centre, parked on a ring, mark the edge, mirror,
field; Strike: straight, flank, high, low, sacrifice, converge): a network per team learns to give the same velocity
command as each script for the same view, selected by a skill code.

## 1. The owner's rulings on route 3

Recorded in [DISCUSSION §16](../DISCUSSION_2026-11-19_20.md#16-rulings-for-l1-to-l6-owner-24-nov-2026) with the
owner's words.

| # | Ruling | What it means here |
|---|---|---|
| R35 | the learned-skills route is adopted as the third route | no code and no run before the two-reviewer design review (done 25 Nov, section 9) |
| R36 | LS1 may use 1.0 GPU-h from the L3–L6 cap | superseded by R39 (confirmed, R43) |
| R37 | LS1 is built now, route 3 first | the learner v2 note follows; the build session runs on Opus 5.5, high effort, as a multi-agent workflow |
| R38 | the owner sets the LS1 pass limits, on the lead's advice | asked after the calibration read (job LS1.5), before the gate file is hashed; the margin of LS1.4 is asked at the same time |
| R39 | no GPU-hour cap on route 3; the aim is a useful policy | **the lead's reading, confirmed by the owner (R43):** all stages of route 3; hours no longer charged to the 20 of R23; every job still states its hours before launch; every status shows the route's hours so far; a single job above 5 GPU-h is announced before launch. In the code a number is still needed: the route's budget section carries 200 GPU-h, and each job group keeps a task cap (a cap per task is how the launcher stops a job that hangs) |
| R40 | the heads are trained again on the skill network, on both sides | job group LS1.4; a team of route 3 is a set of heads and a skill network trained together |
| R41 | self-play is brought forward | order LS1 → LS1.4 → LS2 → self-play → LS3. After the review, and agreed by the owner (R44): the pool entry for saved teams is built early and a self-play pilot runs right after LS1.4; the full stage starts before LS2 only if the pilot's three measurements show room (section 7) |
| R42 | the word for the build | merges M1 to M4, then the jobs of sections 5 and 6; the first step is the task plan rewritten from this file and the two review reports |
| R43 | the lead's reading of R39 is confirmed | merge M1 writes 200 GPU-h for the route and 4.0 for LS1.4 |
| R44 | self-play: the pool entry early, a pilot after LS1.4, the full stage before LS2 only if the pilot shows room | section 7 |
| R45 | the route page, its figures and the slides are redrawn for R39 to R41 | a writer's task beside the build |

## 2. What "useful on the drones" asks, and what route 3 gives

The track's goal is [PLAN §1](../PLAN.md). Route 3 is one part of it. Checked against the code on 25 Nov 2026:

| PLAN §1 asks | Route 3 as planned here | What is missing, and where it comes from |
|---|---|---|
| plays the game under rules that can fly | yes: the same game and safety filter as routes 1 and 2 (tier 1) | — |
| robust to attackers it did not train against (self-play with a pool) | the self-play stage | **a new build:** the opponent pool takes script names only (`ste/pool.py:84-113`); a saved team cannot be a training opponent today. The loaders and the player objects exist (`exploit_train.py:427-473`, `exploit.SkillTeam`), the pool entry and the drivers' wiring do not |
| a held-out test | not possible today: every Strike script is in the training pool; the one unused Guard script, `guard_mark_inside`, is mark the edge with one number changed (`scripted.py:105-122`) | **new held-out scripts, two per side, written before self-play is designed** (section 7) |
| keeps the team plan when a drone is lost (one shared policy per drone) | partly: the skill network is one network shared by a team's drones and is fitted on states with a drone absent; the heads are one network per drone slot; team size 3v3 only | the shared actor and training at drawn team sizes (learner v2); the absent-drone mask exists |
| trained with the Isaac Lab Starling (tier 2) | no: route 3 trains on tier 1; tier 2 has replayed fixed choices only (L3.1) | a tier-2 score of the trained team, then tier-2 training: its own task |
| the robustness suite (held-out attackers, drone loss, filter mismatch) | the scoring matrix exists but its scripts refuse a skills gate file (`scripts/ste_score_matrix.py:215`) | a scorer for route 3 teams (merge M4), then the suite: its own task, after self-play |
| export and reload | yes: heads and skill network per team, with a new branch in the reload check | — |
| AirStack simulator, real flight | owner-gated (L7, L8); a team of route 3 needs no port of the scripts into the flight software | unchanged |

**The size of the work.** LS1 and LS1.4 are changes to a pipeline that exists, but not only small ones: the review
found that the training driver's controls, the export's reload check and the reader need changes too (section 9).
Self-play and LS2 are new builds. Every figure is the lead's estimate, with nothing measured behind it.

## 3. What is added to the pipeline (LS1 and LS1.4)

| File | New or changed | What it does | Off means identical | Tests |
|---|---|---|---|---|
| `source/svg_training/ste/skill_net.py` | new | the skill network (one per team; inputs: what the drone sees, its slot, the skill code; output: a velocity). Inputs no script reads are set to zero (yaw, time left, team flag); the input scale is clamped where an input never varies; the output is a clipped linear layer, not tanh (two scripts command exactly ±1); the forward pass runs without gradients when it flies. Save and load with refusals: wrong team, wrong skill list or order, wrong team size, scripts edited since the fit, **and a different game file** (the scripts read the keep-out distances, the wall margin, the height band and the team speed from the game file). The net-backed dispatch that the two-level heads drive | not used unless the setting says so | `tests/test_ste_ls1_skill_net.py`, `test_ste_ls1_dispatch.py` (a drone that is out gets a zero command on both paths, all codes and one code) |
| `source/svg_training/ste/cells.py` (name PROPOSED) | new | the cells of the equivalence read for either team: one code on every drone, and the mixed combinations with a scripted arm that flies the same combination. Today's helpers are Strike-only (`scripts/ste_l3_run0_ceiling.py:69, 99-128, 232-245`) | the ceiling script keeps its own helpers | `tests/test_ste_ls1_cells.py` |
| `source/svg_training/ste/distil.py` | new | data collection, the supervised fit, the relabelling rounds, the report. **Data mix (review):** at least half the games fly one code for the whole game (each of the team's codes, as the gate's fixed-choice cells do), the rest fixed per-drone mixes and the random redraw; rows with a team-mate absent are oversampled (PROPOSED 20 % or more); rows are kept in proportion to the network's error, with a floor near the scripts' switch points. **Report:** error per skill and per active channel, the largest output on channels a skill never uses, by number of live drones and by how long the code was held, and the tick-to-tick change of the command beside the scripts' | not used by any existing driver | `tests/test_ste_ls1_distil.py` |
| `source/svg_training/ste/skills.py` | changed | `[learner] skill_source = "scripts" \| "net"` and the skill network file per team with its sha256 in the gate file (the file kept at a path that exists in every worktree); the factory `two_level_dispatch` (12 calls in 9 files, verified) returns the net-backed dispatch when asked. `skills_meta` and `learner_table` **stay byte for byte as today for scripts** and gain the skill source and the network's sha256 only for a network: existing checkpoints, exports and pilots keep loading, and a pilot or a set of heads made on one skill source is refused on the other. The single-head modes of slice 1 refuse `"net"` | default `"scripts"`: today's dispatch, checked bit for bit; a test pins the literal keys of today's dictionaries and loads a dictionary saved before the change | `tests/test_ste_ls1_dispatch.py` plus the existing `test_ste_l3_skills.py`, `test_ste_l3_two_level.py`, `test_ste_l3_pipeline_gates.py`, `test_ste_l3_driver.py` |
| `scripts/ste_exploit_l012.py` (the training driver) | **changed (review, blocker)** | under `skill_source = "net"` the control "the untrained team equals its first skill" compares against a twin that flies the same code **on the skill network**, not the script. As written today it compares against the script (`:380-388`, `:921-933`) and allows at most 20 games of 1,000 to differ on the GPU (`skills_gates.toml:86-87`): a copy differs by more, the control fails, and every head-training job would end with exit 6 before training | the scripts route's controls unchanged | `tests/test_ste_ls1_driver.py` plus `test_ste_l3_driver.py`, `test_ste_l3_run0.py` |
| `source/svg_training/ste/export.py`, `scripts/ste_l6_export.py` | changed | the skill network as an ONNX graph (inputs `obs [B, 71]`, `slot [B]`, `z [B]`; output `command [B, 4]`; the input scale inside the graph; a test graph of this shape exported and reloaded on 25 Nov). A team's folder holds its heads and its skill network, with a `[skill_net]` section in `interface.toml`. **The reload check gets a branch** for it: today it rebuilds the scripts and compares commands (`export.py:302-306`), which refuses a route 3 team. The variant is no longer fixed to "base" (`export.py:86, 98, 161`), so a second seed exports with its own seed | existing export types and the four exports of the pipeline check reload as before | `tests/test_ste_ls1_export.py` plus `test_ste_l3_export.py`, `test_ste_l6_export.py` |
| `scripts/ste_ls1_distil.py` | new | the distillation driver under the run contract (resume, cap, exit codes), launched through `ste_job.py`; 2-D clips with the height panel of network-flown games | — | in `test_ste_ls1_distil.py` |
| `scripts/ste_ls1_equivalence.py` | new | the gate read (section 5): controls first, then the copy against the scripts on the same starts; per game arrays saved, so that games can be picked for clips; verdict DISTILLED / NOT DISTILLED / INCONCLUSIVE | — | `tests/test_ste_ls1_equivalence.py` |
| `scripts/ste_ls1_calibration.py` (v2's noise-floor read) | new | scripts against changed scripts, no network, on the gate read's cells: random error on the commands (0.01 to 0.1), and systematic changes (commands scaled by 0.95, turned by 3 degrees, a switch angle moved; the changed scripts are subclasses in their own file, the teacher file is not edited). It shows which sizes of error the gate lets through and which it stops | — | `tests/test_ste_ls1_calibration.py` |
| `scripts/ste_ls1_clips.py` | new | 3-D clips of the copy beside the scripts on the same start: the existing capture (`viz/replay3d.capture_trained`) called once per arm, then the existing renderer. `scripts/ste_l5_clips3d.py` draws only a finished training run and stays as it is; the runs of LS1.4 are ordinary training runs and the post-run hook draws them | the clip script and its hook behave as today | `tests/test_ste_ls1_clips.py` |
| `scripts/ste_ls1_read.py` | **new (review)** | the read of LS1.4: route 3 against route 2, seed by seed and cell by cell, by the rule of section 6; the scores of route 3 teams against players that were in no pool. The L6 reader knows two routes only (`scripts/ste_l6_read.py:54-61`) and the score-matrix scripts refuse a skills gate file | — | `tests/test_ste_ls1_read.py` |
| `configs/ste_ls1/distil_gates.toml` | new | sizes, rounds, network size, the limits the owner sets (R38), controls, seed, the game file's sha256; hashed before any run | — | its own load test (the limits are read from the file, not typed into the test) |
| `configs/ste_ls1/heads_gates.toml` | new | the gate file of LS1.4's route 3 arm: the skills gate file of the pipeline check with `skill_source = "net"`, the two skill network files, two seeds as two variants, the reading rule. Route 2's recipe and game-steps are pinned in it (section 6) | — | a test that it differs from `configs/ste_l3/skills_gates.toml` in the named keys only |
| `configs/ste_ls1/skills_seed2_gates.toml` | **new (review)** | route 2's second seed. A variant cannot be added to `configs/ste_l3/skills_gates.toml`: its sha256 is pinned in six run folders and in `tests/test_ste_l3_pipeline_gates.py`. A new gate file needs its own run 0 (`ste/exploit.py:933-939`) | — | as above |
| `source/svg_training/ste/config.py`, `configs/ste_learning.toml`, `ste/budget.py`, `scripts/ste_job.py`, `ste_learning/PLAN.md` §9, `tests/test_ste_config.py` | changed | the route's tasks and hours (the exact list is in section 9, B6). `TASK_IDS` gains the LS1 tasks; a section `[budget_ls1]` after the L3–L6 one, every task with a cap entry, CPU tasks at 0.0. The owner confirmed the reading of R39 (R43): merge M1 writes 200 for the section, 0.8 for LS1.1, 0.1 for LS1.6 and 4.0 for LS1.4. `ste_job.py status` prints only the section "in work" (`ste/budget.py:223-229`): it also prints route 3's hours, as R39's reading promises | every existing task, cap and status line unchanged | `tests/test_ste_config.py` (its section set at line 90 and the tuple at line 107 name three sections today) |

**Not touched:** the game engine and its rules, the safety filter, the scripts (they are the teachers; **the file
`opponents/scripted.py` is frozen from the first distillation on**: its sha256 is pinned in every skill network, so
any edit, a bug fix included, means distilling again), the opponent pool, the scoring, the run contract, the GPU-hour
ledger, the two-level learner and its PPO step, the post-run 3-D clip hook, every existing gate file, AirStack, Isaac
Lab.

## 4. How the work runs

```
design review of this file and the plan (two reviewers, R22): DONE 25 Nov 2026, folded in
  -> the owner reads the rulings and this file, and gives the word for the build
  -> the task plan rewritten from this file and the two review reports (the plan's Tasks 1 to 7 are older than the
     review and must not be built as written); one reviewer reads it
  -> design check (ste-architect, read-only)
  -> build in its own worktree, tests first (ste-software-engineer, Opus)
  -> QC review of the build (ste-test-qc-engineer, Sonnet)
  -> lead merges to development (fast-forward); full test suite once per code merge, in the background
  -> calibration read (CPU) -> the lead advises, THE OWNER SETS THE LIMITS AND MARGINS (R38)
  -> gate file written and hashed (lead) BEFORE any run
  -> job launched through scripts/ste_job.py (budget check, heartbeat, exit code, clips)
  -> verdict read: controls first, then the result
  -> record + ledger row + clips; two reviewers
  -> status update to the owner
```

The Fable 5.2 advisor is asked before the build starts, before each gate is hashed and before a stage is reported
done. One fix at a time if something fails. Reviewers and other checking agents stay on Sonnet 5.5.

**Build order:** four merges. No merge while the full suite or a run is going.

| Merge | Content | Lets run |
|---|---|---|
| M1 | skill network, save/load, net-backed dispatch, the setting (default off), the meta rules; the LS1 tasks in the budget table and the status line; the cell module; the calibration script | the calibration read (LS1.5) |
| M2 | distillation, its driver, the distillation gate file, the equivalence read | LS1.0, LS1.1, LS1.2 |
| M3 | export of the skill network and the reload branch; the LS1 clip script | LS1.3, LS1.6 |
| M4 | the training driver's control under a network; the two gate files of LS1.4; the LS1.4 reader and the scorer against players of no pool | LS1.4 |

## 5. The jobs of LS1 Distil

Machine: whichever is in use (owner rule); the RTX 5090 on weekdays. Every GPU job goes through the launcher, for
example:

```
scripts/ste_job.py launch --task LS1.1 --name ls1_distil_guard --run-dir runs/<date>_ste_ls1_distil_guard \
  --min-s <from the smoke> --gpu-h 0.4 --settings configs/ste_learning.toml -- \
  python scripts/ste_ls1_distil.py --gates configs/ste_ls1/distil_gates.toml --side guard \
  --run-dir runs/<date>_ste_ls1_distil_guard --cap-h 0.4 --expect-gates-sha256 <hash>
```

`--min-s` is the shortest time a real finish can take; a finish under it is flagged ENDED_EARLY. It is set from the
timing of the smoke (LS1.0). "Asked" is the hours a job states at launch; a job is stopped at its own ask.

| Job | Plain name | Where | What runs | Asked GPU-h | Needs | Gives | Owner asked |
|---|---|---|---|---|---|---|---|
| S1 | Full test suite after each code merge (4 times) | CPU, background | `pytest` (full suite, about 40 min each) | 0 | each merge | pass or fail | no |
| LS1.5 | Calibration read | CPU | `ste_ls1_calibration.py`: scripts against changed scripts on the gate read's cells, T44's starts, 1,000 games each | 0 | M1 | which error sizes the gate lets through and which it stops; the lead's advice | **the owner sets the limits and margins (R38)** |
| LS1.0 | Smoke of the distillation and the read | CPU | `ste_ls1_distil.py` with 16 games, 2 rounds; `ste_ls1_equivalence.py` on 24 starts | 0 | M2 | the plumbing works; timings for `--min-s`, for the read on the CPU and the network's game-steps per second | no |
| — | Gate file written and hashed | — | `configs/ste_ls1/distil_gates.toml` with the owner's limits; QC reads it | 0 | LS1.5, the limits | the hash every later job names | no |
| LS1.1-G | Distil the Guard team's 5 skills | GPU | `ste_ls1_distil.py --side guard` (4,096 games, 4 rounds of 600 ticks, fit after each) | 0.4 | LS1.0, gate hashed | `skill_net_guard.pt`, the fit report, 4 clips | no |
| LS1.1-S | Distil the Strike team's 6 skills | GPU, side by side with LS1.1-G | `ste_ls1_distil.py --side strike` | 0.4 | as above | `skill_net_strike.pt`, the fit report, clips | no |
| LS1.2-G | Equivalence read, Guard | CPU | `ste_ls1_equivalence.py --side guard`: controls, then 30 fixed-choice cells (5 codes against the 6 Strike scripts) and 120 mixed cells (20 combinations against the 6), 1,000 games each | 0 | LS1.1-G | DISTILLED / NOT DISTILLED / INCONCLUSIVE | no |
| LS1.2-S | Equivalence read, Strike | CPU | `ste_ls1_equivalence.py --side strike`: 30 fixed-choice cells (6 codes against the 5 Guard scripts) and 100 mixed cells; `guard_mark_inside`, which the network never saw, as an extra opponent (INFO) | 0 | LS1.1-S | verdict | no |
| LS1.3 | Export and reload check of both skill networks | CPU | `ste_l6_export.py` with the skill-network type; reload in a fresh process | 0 | DISTILLED | ONNX files, `interface.toml`, golden rows | no |
| LS1.6 | 3-D clips of key games | GPU | `ste_ls1_clips.py`: 3 to 6 games per side, the copy beside the scripts on the same start | 0.1 | LS1.2, M3 | MP4 and GIF for the record | no |
| R1 | Record, ledger rows, two reviewers | CPU | `records/<date>_ste_ls1_distil_record.md` | 0 | LS1.2, LS1.6 | the read for the owner | — |

**The gate read, as revised by the review.** The copy and the scripts play the same 1,000 starts per cell, so the
read is paired: per cell it reports the games the copy lost that the scripts won (b), the games it won that the
scripts lost (c), and the games that changed (b + c). Two copies of one policy change few games (in the pipeline
check's GPU replay, 0 of 1,000 in 11 of 17 cells and 2 to 5 in the mixed cells), so a limit such as "within 30 wins"
is a size of effect the owner accepts, not an allowance for chance. What the gate reads:

| Read | What | Limit |
|---|---|---|
| Command error | per skill and per active channel, on states the network itself reached; the largest output on channels the skill never uses; for the skill whose command is exactly zero (parked at the centre in 3v3) the largest output | the owner's (PROPOSED starting points: 0.05 per active channel; 0.005 for the zero-command skill) |
| Games changed | b + c per cell | the owner's, from the calibration read |
| Net difference | b − c per cell with its interval, corrected for the number of cells; the pooled row (the mean of the cell rates: "within 15 wins" is 0.015 there) | the owner's margin, as a size of effect (PROPOSED starting point 0.03 per cell) |
| Time to the end | the difference in the tick each game ended, per cell (more sensitive than win or loss) | reported; a limit if the calibration read supports one |
| Flight paths | the distance between the copy's and the scripts' paths from the same start after 1, 3 and 10 s | reported |

The 30 fixed-choice cells per side have T44 as their reference. The mixed cells have none: their scripted arm is
played on the same starts by the cell module.

**Controls, read before any result.** Positive 1: the script team through the same scoring path differs in 0 games
from T44 (CPU; T44's games are equal game for game only there, `ste/exploit.py:57`). Positive 2 (review): a stand-in
network that returns the scripts' own commands through the new slot and code path differs in 0 games: it proves the
new path, which positive 1 does not touch. Negative, gross: an unfitted network and a network with its codes permuted
must miss (the permutation is first shown to miss with the scripts themselves, and "at least N cells miss" is fixed
from that). Negative, near miss (review): scripts changed by a systematic error just above the owner's limits must
FAIL, and scripts with a random error just below them must PASS (PROPOSED sizes: a 0.05 bias, a 3-degree turn and a
moved switch to FAIL; random error 0.02 to PASS; the sizes are set with the limits, from the calibration read, so
that the two cannot contradict each other). Without the near-miss controls the gate is only known to stop a
network that learned nothing.

**CPU time of the read (estimate from measurements):** about 50 to 75 minutes for both sides on an idle machine,
about double beside a GPU job or the test suite (measured 25 Nov: 2.1 to 2.3 ms per tick for a 3 x 256 network on
3,000 rows; the existing CPU reads took 2 to 4.5 s per 1,000-game cell). If it is too slow, the result cells (not
the controls) move to the GPU, announced first.

**Stop rules of LS1 (written into the gate file):**

- A control fails: INCONCLUSIVE; the cause is found and fixed on the CPU, and the run is repeated once, announced
  with its cost (as R34 allows for bug re-runs).
- NOT DISTILLED: no limit is moved. One announced fix round is allowed: the data mix, more relabelling rounds, a
  larger network or added inputs (the drone's and its team-mates' bearing and distance from the zone, which several
  scripts compute; left out of the first fit). If it still fails, LS1 stops and the record says which skills do not
  copy and why.
- DISTILLED on one side only: that side may go on; the other side is reported.

## 6. The jobs of LS1.4 Head training on the skill network (R40), after DISTILLED on both sides

The recipe, game-steps and opponent pool of the skills route's runs of the pipeline check (L3.3, L3.5, L5.2), with the
skill network flying in place of the scripts. Measured GPU-hours of those runs
([pipeline record](../../records/2026-11-25_ste_l3_l6_pipeline_record.md)): pilot 0.055, run 0 0.284, Guard 0.277,
Strike 0.284, 3-D clips 0.016 to 0.043 per run.

| Job | Plain name | Where | Asked GPU-h | Needs | Gives |
|---|---|---|---|---|---|
| — | Both gate files and the reading rule written and hashed | — | 0 | LS1 DISTILLED, M4, the owner's margin | `heads_gates.toml`, `skills_seed2_gates.toml` |
| LS1.4-P | Skills pilot on the skill network (covers both sides) | GPU | 0.1 | gate hashed | rates and controls. It is read as a check: if its rule would choose another Strike recipe or another number of game-steps than route 2's, nothing is launched and it comes back |
| LS1.4-0 | Run 0 on the skill network: Strike against the parked Guard | GPU | 0.4 | LS1.4-P | PASS or FAIL against its mark. Route 2's mark 0.554 is the scripts' best fixed choice (604 of 1,000) less 0.05; for the network the same rule is applied to the network's own best fixed choice, read on the CPU before the gate is hashed (a FAIL of run 0 cannot be overridden and would stop both Strike seeds). One run 0 serves both Strike seeds |
| LS1.4-G1, -G2 | Head training on the network, Guard, two seeds | GPU, side by side | 0.4 each | LS1.4-P | two Guard teams of route 3, scored against every Strike script; clips by the post-run hook (0.1 asked each) |
| LS1.4-S1, -S2 | Head training on the network, Strike, two seeds | GPU, side by side | 0.4 each | LS1.4-0 | two Strike teams of route 3, scored against every Guard script; clips |
| LS1.4-R0 | Run 0 of route 2's second-seed gate file | GPU | 0.4 | — | needed before its Strike run (review) |
| LS1.4-RG, -RS | A second seed of route 2 (the scripted arm), Guard and Strike | GPU | 0.4 each | LS1.4-R0 | two seeds on both arms; clips |
| LS1.4-X | Export and reload of the route 3 teams (heads and skill network per team) | CPU | 0 | the runs, M3 | export folders |
| LS1.4-H | Scores against players of no pool (INFO) | CPU or GPU | 0 | the runs, M4 | each route 3 team against the trained teams of route 1 (the velocity Guard and Strike teams of L5.1) |
| R2 | The read (`ste_ls1_read.py`), record, ledger rows, two reviewers | CPU | 0 | all of the above | the read for the owner |

Asked in total: 4.0 GPU-h (eight training jobs at 0.4, the pilot 0.1, six clip jobs at 0.1, 0.1 spare); expected
about 2.5 (estimate from the measured runs). The task cap of LS1.4 in the settings file is 4.0.

**What LS1.4 can and cannot show.** The skill network imitates the scripts, so heads trained on it are expected to
score about as route 2's. That is the success of this step: it shows that the copy can carry training. A new
strategy is not expected before LS2. Three limits on the reading, from the pipeline record:

- **The Strike run of record of route 2 did not learn** (176 of 1,000 against guard_mark_edge, the untrained team
  192; its driver word is INCONCLUSIVE). Matching it shows nothing. The Strike read is therefore **run 0** (route 2:
  644 of 1,000 against the parked Guard, the untrained team 466), with the runs of record beside it as INFO.
- **The Guard run of record is weak evidence too:** 813 against 808 for the best single script.
- **The trained heads use about three of the eleven codes** (Strike: flank and low; Guard: mark the edge). LS1.4 says
  nothing about the other codes; the equivalence read (LS1.2) is their only check.

**Reading rule, written before the runs (PROPOSED; the owner sets the margin with the LS1 limits).** A seed's score is
the mean of its last three reads (a single read can land on a dip: run 0 read 461 once between 633 and 620). Both arms
use the same training seeds and the same pool draws, and are scored on the same starts and compared start by start. With a margin Δ fixed beforehand
(PROPOSED 0.04 on the pooled row, 0.08 per cell): **"no drop beyond Δ"** when the mean of route 3's seeds is at least
route 2's mean less Δ and each route 3 seed is at least route 2's lower seed less Δ; **"below"** when route 3's mean
is under route 2's by more than 2Δ; otherwise INCONCLUSIVE, and a third seed per arm is announced (0.4 GPU-h each).
Two seeds never support the word "level". The share of each code chosen is compared with route 2's as INFO.

## 7. The later stages (outlines; each gets its own design note before code)

Order by R41: LS2 → self-play → LS3.

| Stage | What it adds | Open questions for its note |
|---|---|---|
| **Self-play, part 1: the pool entry and a pilot** (right after LS1.4) | a pool entry that loads a saved team (heads and skill network, frozen), so a team can train against trained teams as well as the scripts. The entry does not depend on LS2 and stays valid after it. A pilot on the heads of LS1.4 gives three measurements | built while LS1 runs (other files); its design note first |
| **LS2 Fine-tune** | the skill network trained by the game reward at one command per tick, with a tie that keeps each code near its script, weakened step by step; skills and heads trained in turns | the exploration noise of the skill network at 20 Hz against the tie (the learner's usual noise is about four times the copy's error limit); the tie's schedule; the control without a tie (expected to lose the codes); today's per-slot heads or the shared actor of learner v2 |
| **Self-play, part 2: the stage** | teams trained in turns against past and present teams; saved exploits (a Strike team trained against a frozen Guard team, and the reverse) kept as permanent pool entries | how turns are taken and when a team joins the pool; how a cycle (A beats B beats C beats A) is detected; the cost per turn |
| **LS3 Free codes** | skill codes with no script, rewarded for being distinct and useful | whether it is needed at all once self-play has run |
| **Robustness suite** | held-out opponents, drone loss, filter mismatch (PLAN §1) | the shared actor and drawn team sizes; tier 2 |

**When the self-play stage starts (review).** Heads that only choose among fixed, imitated skills have little room:
route 2's teams sit close to their best single script and choose almost one code per side. So the stage starts before
LS2 only if the pilot shows room; otherwise LS2 runs first. The three measurements, with their marks fixed in the
pilot's note: (1) how varied the LS1.4 teams' choices are per opponent (PROPOSED mark: above 1 bit in several cells);
(2) how much a fresh exploiter gains against a frozen LS1.4 team over the best script (PROPOSED mark: more than the
margin Δ of section 6); (3) the gap to the best fixed mix of scripts on the same starts.

**The held-out set (review).** A script taken out of a training pool is not held out when the opposing trained teams
can still fly it as one of their own skills. So: **two new scripts per side, written before self-play is designed, in
their own file outside `opponents/scripted.py`** (the strategy factory loads `package.module:ClassName`,
`scripted.py:217-228`; editing the teacher file would invalidate every skill network). They are written by an agent
that has not seen the trained teams, and are never used in training. Beside them: the trained teams of route 1
(unseen players, though trained in the same game); at the end, a new exploiter trained against the frozen final
team, the strongest test.

## 8. What the owner is asked

| # | Question | State |
|---|---|---|
| 1 | The word for the build (merges M1 to M4, then the jobs of sections 5 and 6) | **given (R42), 25 Nov 2026** |
| 2 | The lead's reading of R39 (row R39 of section 1) | **confirmed (R43)** |
| 3 | The LS1 limits and the LS1.4 margin | the owner sets them after job LS1.5 (R38); the lead brings the calibration read, options and a recommendation |
| 4 | Self-play: the pool entry built early and a pilot after LS1.4; the full stage before LS2 only if the pilot's three measurements show room | **yes (R44)** |
| 5 | Two new held-out scripts per side, written before self-play is designed | proposed; asked with the self-play note |
| 6 | The route page [LEARNED_SKILLS_ROUTE.md](../LEARNED_SKILLS_ROUTE.md), its figures and the slides redrawn for R39 to R41 | **yes (R45)**; in work |

What runs without asking once the build has the owner's word: the builds, the CPU jobs, the GPU jobs as listed here,
the records. What always comes back: the limits and margins (R38), a
failed gate, a pilot that disagrees with route 2's recipe, a single job above 5 GPU-h (announced), every later
stage's design note.

## 9. The design review (25 Nov 2026)

Two independent reviewers, read-only, given the files and not the lead's conclusions. A read every line of
`opponents/scripted.py`; B traced every call site and ran two small CPU checks (the budget loader with an LS1 section
in a scratch copy; an ONNX export of a test network). The lead checked their file references by grep before folding
them in. Neither reviewer ran a test suite or a GPU job. **The full reports, with the file and line of every change a
builder needs: [LS_DESIGN_REVIEW_A.md](LS_DESIGN_REVIEW_A.md), [LS_DESIGN_REVIEW_B.md](LS_DESIGN_REVIEW_B.md).** The
table below is the summary.

| # | Finding | Severity | What changed here |
|---|---|---|---|
| B1 | The driver's control "untrained team equals its first skill" compares with the script and fails under a network: every head-training job would end with exit 6 (`scripts/ste_exploit_l012.py:380-388, 921-933`; `skills_gates.toml:85-87`) | blocker | the driver is in the change table; merge M4 |
| B2 | Adding a key to `skills_meta` for scripts refuses all six checkpoints and four exports of the pipeline check (whole-dictionary equality: `exploit_train.py:411, 455`; `export.py:304-306`) | major | the dictionary is unchanged for scripts; keys added for a network only |
| B3 | A pilot made on scripts would be accepted for a network gate file (`ste_exploit_l012.py:236-249` compares the `[learner]` table only); the gate file is filled from the pilot, which may choose another Strike recipe | major | `learner_table` carries the skill source for a network; route 2's recipe pinned; a disagreeing pilot comes back |
| B4 | Route 2's second seed needs a new gate file and its own run 0 | major | `skills_seed2_gates.toml`, job LS1.4-R0 |
| B5 | The reload check refuses a route 3 team; the L6 reader and the score-matrix scripts cannot read route 3; no script read LS1.4 | major | the reload branch, `ste_ls1_read.py`, merge M4 |
| B6 | Budget: `TASK_IDS["LS1"]`; `[budget_ls1]` placed after the L3–L6 section with every task capped (a missing key is refused, `config.py:193`); the name must spell the phases (`config.py:220-222`); `tests/test_ste_config.py:90, 107`; each value line labelled; PLAN §9 a documentation row. Verified in a scratch copy: with these, `check_launch("LS1.1", 0.4)` is accepted while the section "in work" stays `budget_l1_l2`. A task cap still binds each launch, and `status` shows only the section in work | major | section 3's last row; R39's row in section 1 |
| B7 | The post-run clips ask 0.1 GPU-h per run against the run's task (`ste/post_run.py:71`) | major | LS1.4 asks 4.0 |
| B8 | Merge M1 could not stand alone (the calibration read needs the cells of a later task); the mixed-cell helpers are Strike-only | major | the cell module, in M1 |
| B9 | T44 backs only the 30 fixed-choice cells per side; the mixed cells need a scripted arm on the same starts; the CPU read is about 50 to 75 minutes; the network must fly without gradients | major | section 5 |
| B10, B11 | The export fixes the variant to "base"; plan details that do not match the code (the plan's tests name helpers that do not exist; `learner_spec` drops new fields unless they are passed on, `skills.py:105`; the limits typed into a test contradict R38) | minor | section 3; the plan's tests are rewritten by the builder against the real signatures |
| A1 | The data would hardly contain whole games on one team strategy, which is what the gate plays; relabelling does not repair that | major | the data mix, sampling and report of `distil.py`; the fix round may change the data |
| A2 | The read is paired, so the chance figure of v2 (22 wins) was the wrong ruler; random error on commands averages out while a network's error is systematic; the net difference hides errors that cancel | major | the gate read of section 5; job LS1.5 is a calibration with systematic changes |
| A3 | The LS1.4 rule of the first v3 could not be defended with two seeds, and the Strike cell it compared did not learn | major | the reading rule and the Strike read of section 6 |
| A4 | The controls could not show that the gate sees a near miss, and the positive control did not touch the new code path | major | controls of section 5 |
| A5 | Confirmed: all eleven skills keep no memory and use only the drone's own row and its slot; the slot input is needed (after a loss two drones can have the same observation). Not in the plan: the scripts read constants of the game file; three inputs no script reads; inputs that never vary; one skill's command is exactly zero; error averaged over channels a skill never uses | major | `skill_net.py` and the command-error read |
| A6 | Switch points blur under a squared-error fit; two scripts command exactly ±1, which tanh cannot reach; the scripts' branches for a lost team-mate are rare in the data | minor to major | clipped linear output; oversampling; error by number of live drones |
| A7 | `guard_mark_inside` is a weak held-out; a script withheld from a pool is not held out; adding scripts to the teacher file breaks the pin | major | the held-out set of section 7; the teacher file frozen |
| A8 | Self-play on fixed skills has little room; the pool entry does not depend on LS2 | decision | section 7, question 4 of section 8 |
| A9 | Same starts and pool draws on both arms; the command's tick-to-tick change; the absent-drone test on the one-code path; the network's speed measured in the smoke | minor | sections 3, 5 and 6 |

Not checked by either reviewer: the GPU speed of a network-backed run; whether the post-run clips of a network team
replay game for game (the clip script requires it); the full test suite.

## 10. What each version changed

**v3 (R39 to R41, then the review).** The aim is a useful policy. No cap: jobs state their hours. LS1.4 is the full
head training on both sides with two seeds per arm. Self-play before LS3. Corrected from what the lead told the owner
on 25 Nov: a saved team cannot be a training opponent with today's code, so self-play is a new build; and LS1 with
LS1.4 is four merges, not "minor edits" throughout.

**v2 (checked against the code).** The LS1 tasks in the budget table; a clip path for an LS1 team; the equivalence
read on the CPU (its control against T44 is exact only there, `ste/exploit.py:57`); a read before the limits are set
(its reasoning corrected by A2); the cell count of the read (150 for Guard, 130 for Strike; the plan costed 50 per
side); `--min-s` from the smoke; the skill network file per team; heads trained on scripts refused on a network
(settled by R40). Confirmed then and again by reviewer A: the scripts keep no memory; `two_level_dispatch` has 12
calls in 9 files.
