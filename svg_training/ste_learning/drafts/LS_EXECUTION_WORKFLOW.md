INTERNAL · DRAFT v3 for the owner's review: how route 3 (the learned-skills route) is executed towards a policy that is useful on the drones: what is added to the pipeline, which jobs run, in what order, on which machine, at what cost, and where the owner is asked · rulings R35 to R41 recorded; nothing is built or run; v3 is in its two-reviewer design review · the route explained: [../LEARNED_SKILLS_ROUTE.md](../LEARNED_SKILLS_ROUTE.md) (its stage order is older than R41); the task-level plan of LS1: [LEARNED_SKILLS_BRIDGE_PLAN.md](LEARNED_SKILLS_BRIDGE_PLAN.md)

# Route 3 execution workflow (draft v3, 25 Nov 2026)

Version 1: the lead (Opus 5.5), 25 Nov 2026. Version 2, the same day (the lead, a Fable 5.2 session, with the advisor
tool): checked against the code, eight corrections. **Version 3, the same day:** the owner's rulings R39 to R41 change
the aim and the order: no GPU-hour cap, the heads trained again on the skill network on both sides, self-play brought
forward, the aim a policy that is useful on the drones. Section 8 lists what each version changed. This file is about
route 3 only; "v3" is the third version of this file, not a route.

Stage LS1 and the head training (LS1.4) are given job by job. LS2, self-play and LS3 are outlines with their open
questions; each comes back with its own design note before code. Where this file and the plan differ, this file wins.

## 0. In one screen

| | Now, job by job | Later, outlines |
|---|---|---|
| Stages | **LS1 Distil** (the scripts copied into one skill network per team) → **LS1.4 Head training** (the heads trained again on the skill network, both sides) | **LS2 Fine-tune** (the skills trained by the game reward) → **Self-play** (the stage called LS4 League on the route page, brought forward by R41) → **LS3 Free codes** (skills no script has; last, an extension) |
| Adds to the pipeline | 2 new modules, 4 new scripts, 2 gate files, small changes to the skills switch, the export and the budget table | a pool entry for saved teams (self-play), a skill-level learner (LS2), a diversity reward (LS3) |
| Changes existing behaviour | no: a new setting whose default keeps today's behaviour bit for bit | the same rule |
| GPU-hours | no cap (R39). Asked per job: LS1 0.9, LS1.4 2.9 (two seeds per arm); expected use about 2.3 (estimate) | not estimated again here; each note brings its hours |
| Owner asked | the pass limits after the noise-floor read (R38); the confirmation of the lead's reading of R39 | each stage's design note; the held-out set |

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
| R35 | the learned-skills route is adopted as the third route | no code and no run before the two-reviewer design review |
| R36 | LS1 may use 1.0 GPU-h from the L3–L6 cap | superseded in its charging by R39; until the lead's reading of R39 is confirmed, GPU launches stay inside this 1.0 |
| R37 | LS1 is built now, route 3 first | the learner v2 note follows; the build session runs on Opus 5.5, high effort, as a multi-agent workflow |
| R38 | the owner sets the LS1 pass limits, on the lead's advice | asked after the noise-floor read (job LS1.5), before the gate file is hashed |
| R39 | no GPU-hour cap on route 3; the aim is a useful policy | **lead's reading, PROPOSED until the owner confirms:** all stages of route 3; hours no longer charged to the 20 of R23; every job still states its hours before launch; every status shows the route's hours so far; a single job above 5 GPU-h is announced before launch; the launcher needs a number, so the route's budget section carries 200 GPU-h with this ruling beside it |
| R40 | the heads are trained again on the skill network, on both sides | job group LS1.4, in place of the small optional job of v2; a team of route 3 is a set of heads and a skill network trained together |
| R41 | self-play is brought forward | order LS1 → LS1.4 → LS2 → self-play → LS3; whether self-play can start on the heads of LS1.4, before LS2, is a question of the design review |

## 2. What "useful on the drones" asks, and what route 3 gives

The track's goal is [PLAN §1](../PLAN.md). Route 3 is one part of it. Checked against the code on 25 Nov 2026:

| PLAN §1 asks | Route 3 as planned here | What is missing, and where it comes from |
|---|---|---|
| plays the game under rules that can fly | yes: the same game and safety filter as routes 1 and 2 (tier 1) | — |
| robust to attackers it did not train against (self-play with a pool) | the self-play stage | **a new build:** the opponent pool takes script names only (`ste/pool.py:84-113`, `make_strategy` from the scripts' registry); a saved team cannot be a training opponent today. The loaders and the player objects exist (`exploit_train.py:427-473`, `exploit.SkillTeam`), the pool entry and the drivers' wiring do not |
| a held-out test | not possible today for the Strike side: every Strike script is in the training pool. One Guard script, `guard_mark_inside`, is in the registry and in no pool (`scripted.py:206-211, 479-484`) | **the held-out set must be fixed before self-play is designed** (section 6) |
| keeps the team plan when a drone is lost (one shared policy per drone) | partly: the skill network is one network shared by a team's drones; the heads are one network per drone slot, and LS1 is 3v3 only | the shared actor and training at drawn team sizes (learner v2); the absent-drone mask exists |
| trained with the Isaac Lab Starling (tier 2) | no: route 3 trains on tier 1; tier 2 has replayed fixed choices only (L3.1) | a tier-2 score of the trained team, then tier-2 training: its own task |
| the robustness suite (held-out attackers, drone loss, filter mismatch) | the scoring matrix exists; the suite as a whole does not | its own task, after self-play |
| export and reload | yes: heads and skill network per team | — |
| AirStack simulator, real flight | owner-gated (L7, L8); a team of route 3 needs no port of the scripts into the flight software | unchanged |

**What this means for the size of the work.** LS1 and LS1.4 are small changes to a pipeline that exists: about 1 to 2
days of agent work (estimate). Self-play and LS2 are **new builds**, not small edits: a pool that can hold saved teams
and the runs that take turns (estimate 3 to 5 days of agent work with its note and reviews), and a learner that trains
the skill network at every tick with a tie to the scripts (estimate 3 to 5 days). Both estimates are the lead's, with
nothing measured behind them.

## 3. What is added to the pipeline

### LS1 and LS1.4

| File | New or changed | What it does | Off means identical | Tests |
|---|---|---|---|---|
| `source/svg_training/ste/skill_net.py` | new | the skill network (one per team, inputs: what the drone sees, its slot, the skill code; output: a velocity); save and load with refusals (wrong team, wrong skill list or order, wrong team size, scripts edited since the fit); the net-backed dispatch that the two-level heads drive | not used unless the setting says so | `tests/test_ste_ls1_skill_net.py`, `test_ste_ls1_dispatch.py` |
| `source/svg_training/ste/distil.py` | new | data collection from scripted games (every script labels every state), the supervised fit, the relabelling rounds (the network flies, the scripts label), the per-skill error report | not used by any existing driver | `tests/test_ste_ls1_distil.py` |
| `source/svg_training/ste/skills.py` | changed, about 60 lines | `[learner] skill_source = "scripts" \| "net"` and the skill network file per team (for example `skill_net = { guard = "<file>", strike = "<file>" }`); the one factory every driver uses (`two_level_dispatch`, 12 calls in 9 files, counted 25 Nov) returns the net-backed dispatch when asked; checkpoints record which skill source they were trained on, and a set of heads is refused on another skill source | default `"scripts"`: today's dispatch, checked bit for bit | `tests/test_ste_ls1_dispatch.py` plus the existing `test_ste_l3_skills.py`, `test_ste_l3_two_level.py` |
| `source/svg_training/ste/export.py`, `scripts/ste_l6_export.py` | changed, about 80 lines | a new export type for the skill network (ONNX, schema `ste-check-skillnet-0`, golden rows, reload check); a team's folder holds its heads and its skill network | existing export types unchanged | `tests/test_ste_ls1_export.py` plus `test_ste_l3_export.py` |
| `scripts/ste_ls1_distil.py` | new | the distillation driver under the run contract (resume, cap, exit codes), launched through `ste_job.py`; 2-D clips with the height panel of network-flown games | — | in `test_ste_ls1_distil.py` |
| `scripts/ste_ls1_equivalence.py` | new | the gate read: controls first, then the copy against the scripts, cell by cell; verdict DISTILLED / NOT DISTILLED / INCONCLUSIVE | — | `tests/test_ste_ls1_equivalence.py` |
| `scripts/ste_ls1_noise_floor.py` | new | scripts against scripts, no network: each cell of the gate read is played twice on the same starts, once as written and once with a small bounded error added to the team's commands (PROPOSED sizes 0.01, 0.02, 0.05, 0.1 in command units); reports how many of 1,000 games change per cell | — | `tests/test_ste_ls1_noise_floor.py` |
| the 3-D clips of an LS1 team | new | `scripts/ste_l5_clips3d.py` draws only a finished training run (`results.json`, `agent_final.pt`, `eval_info.npz`), so it cannot draw a skill network flown on a fixed choice. Either a small `scripts/ste_ls1_clips.py` that feeds the same renderer, or one more input type in the clip script: the design review chooses. The runs of LS1.4 are ordinary training runs: the automatic post-run hook draws them | the existing clip script and its hook behave as today | its own test file |
| `configs/ste_ls1/distil_gates.toml` | new | sizes, rounds, network size, limits, controls, seed; hashed before any run, after the owner has set the limits (R38) | — | its own load test |
| `configs/ste_ls1/heads_gates.toml` | **new in v3** | the gate file of LS1.4: the skills gate file of the pipeline check (`configs/ste_l3/skills_gates.toml`) with `skill_source = "net"`, the two skill network files, the seeds, and the reading rule against route 2 | — | its own load test, and a test that it differs from the skills gate file in the named keys only |
| `source/svg_training/ste/config.py`, `configs/ste_learning.toml`, `ste_learning/PLAN.md` §9, `tests/test_ste_config.py` | changed | the task table `TASK_IDS` has no LS1 task and a budget section's name must spell its phases (`ste/config.py:37-48, 181-212`), so today the launcher refuses `--task LS1.1`. PROPOSED: one budget section for route 3 holding the LS1 tasks, with the number of R39; the design review checks the mechanics | every existing task and cap unchanged | `tests/test_ste_config.py` (it ties the file to PLAN.md) |

**Not touched:** the game engine and its rules, the safety filter, the scripts (they are the teachers; their sha256 is
pinned in the skill network file), the scoring, the run contract, the GPU-hour ledger, the job launcher, the post-run
3-D clip hook, the two-level learner and its PPO step, every existing gate file, AirStack, Isaac Lab. The opponent
pool is not touched in LS1 and LS1.4; self-play changes it.

## 4. How the work runs

```
design review of this file and the plan (two reviewers, R22) -> the lead revises this file
  -> the owner reads the rulings and this file, and gives the word for the build
  -> design check (ste-architect, read-only)
  -> build in its own worktree, tests first (ste-software-engineer, Opus)
  -> QC review of the build (ste-test-qc-engineer, Sonnet)
  -> lead merges to development (fast-forward); full test suite once per code merge, in the background
  -> noise-floor read (CPU) -> the lead advises, THE OWNER SETS THE LIMITS (R38)
  -> gate file written and hashed (lead) BEFORE any run
  -> job launched through scripts/ste_job.py (budget check, heartbeat, exit code, clips)
  -> verdict read: controls first, then the result
  -> record + ledger row + clips; two reviewers
  -> status update to the owner
```

The Fable 5.2 advisor is asked before the build starts, before each gate is hashed and before a stage is reported
done. One fix at a time if something fails. Reviewers and other checking agents stay on Sonnet 5.5.

**Build order:** three merges. No merge while the full suite or a run is going.

| Merge | Plan tasks | Content |
|---|---|---|
| M1 | 1, 2 | skill network, save/load, net-backed dispatch, the setting (default off); the LS1 tasks in the budget table; the noise-floor script |
| M2 | 3, 4, 5 | distillation, driver, gate file, equivalence read |
| M3 | 6 | export of the skill network and of a route 3 team; the 3-D clip path for an LS1 team; the LS1.4 gate file |

## 5. The jobs

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

### LS1 Distil, in the order the jobs run

| Job | Plain name | Where | Command (driver, arguments) | Asked GPU-h | Needs | Gives | Owner asked |
|---|---|---|---|---|---|---|---|
| S1 | Full test suite after each code merge (3 times) | CPU, background | `pytest` (full suite, about 40 min each) | 0 | each merge | pass or fail | no |
| LS1.5 | Noise-floor read | CPU | `ste_ls1_noise_floor.py` (scripts only, the gate read's cells, T44's starts, 1,000 games each, four error sizes) | 0 | M1 | per cell and per error size: games changed, difference in wins; the lead's advice on the limits | **the owner sets the limits (R38)** |
| LS1.0 | Smoke of the distillation and the read | CPU | `ste_ls1_distil.py` with 16 games, 2 rounds; `ste_ls1_equivalence.py` on 24 starts | 0 | M2 | the plumbing works end to end; timings for `--min-s` and for the read on the CPU | no |
| — | Gate file written and hashed | — | `configs/ste_ls1/distil_gates.toml` with the owner's limits; QC reads it | 0 | LS1.5, the owner's limits | the hash every later job names | no |
| LS1.1-G | Distil the Guard team's 5 skills | GPU | `ste_ls1_distil.py --side guard` (4,096 games, 4 rounds of 600 ticks, fit after each) | 0.4 | LS1.0, gate hashed | `skill_net_guard.pt`, fit report per skill, 4 clips | no |
| LS1.1-S | Distil the Strike team's 6 skills | GPU, side by side with LS1.1-G | `ste_ls1_distil.py --side strike` | 0.4 | as above | `skill_net_strike.pt`, fit report, clips | no |
| LS1.2-G | Equivalence read, Guard | CPU | `ste_ls1_equivalence.py --side guard`: controls, then 30 fixed-choice cells (5 codes against the 6 Strike scripts) and 120 mixed cells (20 combinations against the 6), 1,000 games each, the copy and the scripts on the same starts | 0 | LS1.1-G | verdict DISTILLED / NOT DISTILLED / INCONCLUSIVE | no |
| LS1.2-S | Equivalence read, Strike | CPU | `ste_ls1_equivalence.py --side strike`: 30 fixed-choice cells (6 codes against the 5 Guard scripts) and 100 mixed cells | 0 | LS1.1-S | verdict | no |
| LS1.3 | Export and reload check of both skill networks | CPU | `ste_l6_export.py` with the skill-network type; reload in a fresh process | 0 | DISTILLED | ONNX files, `interface.toml`, golden rows | no |
| LS1.6 | 3-D clips of key games | GPU | 3 to 6 games per side, the copy beside the scripts on the same start, top view and 3-D view | 0.1 | LS1.2, M3 | MP4 and GIF for the record | no |
| R1 | Record, ledger rows, two reviewers | CPU | `records/<date>_ste_ls1_distil_record.md` | 0 | LS1.2, LS1.6 | the read for the owner | — |

**Why the equivalence read is on the CPU.** Its positive control is "the script team, through the same scoring path,
differs in 0 games from T44". T44's games are equal game for game only in a CPU replay (`ste/exploit.py:57`). If the
smoke shows the CPU read is too slow, the result cells (not the controls) move to the GPU, announced first.

**Stop rules of LS1 (written into the gate file):**

- A control fails: INCONCLUSIVE; the cause is found and fixed on the CPU, and the run is repeated once, announced
  with its cost (as R34 allows for bug re-runs).
- NOT DISTILLED: no limit is moved. One announced fix round is allowed (more relabelling rounds or a larger network);
  if it still fails, LS1 stops and the record says which skills do not copy and why.
- DISTILLED on one side only: that side may go on; the other side is reported.

### LS1.4 Head training on the skill network (R40), after DISTILLED on both sides

The same recipe, game-steps and opponent pool as the skills route's runs of the pipeline check (L3.3, L3.5, L5.2), with
the skill network flying in place of the scripts. Measured GPU-hours of those runs are in the
[pipeline record](../../records/2026-11-25_ste_l3_l6_pipeline_record.md): pilot 0.055, run 0 0.284, Guard 0.277,
Strike 0.284.

| Job | Plain name | Where | Asked GPU-h | Needs | Gives |
|---|---|---|---|---|---|
| — | Gate file and reading rule written and hashed | — | 0 | LS1 DISTILLED, M3 | `configs/ste_ls1/heads_gates.toml` |
| LS1.4-P | Skills pilot on the skill network | GPU | 0.1 | gate hashed | rates and controls, as L3.3 |
| LS1.4-0 | Run 0: Strike against the parked Guard (the learner's positive control) | GPU | 0.4 | LS1.4-P | PASS or FAIL against the mark 0.554; needed before a Strike run |
| LS1.4-G1, -G2 | Head training, Guard, two seeds | GPU, side by side | 0.4 each | LS1.4-P | two Guard teams of route 3, scored against every Strike script; 3-D clips by the post-run hook |
| LS1.4-S1, -S2 | Head training, Strike, two seeds | GPU, side by side | 0.4 each | LS1.4-0 | two Strike teams of route 3, scored against every Guard script; clips |
| LS1.4-R | A second seed of route 2 (the scripted arm), Guard and Strike | GPU | 0.4 each | — | the comparison has two seeds on both arms |
| LS1.4-X | Export and reload of the route 3 teams (heads and skill network per team) | CPU | 0 | the runs | export folders |
| R2 | Record, ledger rows, two reviewers | CPU | 0 | all of the above | the read for the owner |

Asked in total: 2.9 GPU-h; expected about 2.0 (estimate from the measured runs: one pilot, one run 0 and six runs
of about 0.28 each).

**What LS1.4 can and cannot show.** The skill network imitates the scripts, so heads trained on it are expected to
score about as route 2's (in the cell of the gate file's named opponent: Guard 813 of 1,000 against strike_straight,
Strike 176 of 1,000 against guard_mark_edge; observed in the training simulator, one seed). "About the same" is the success of this step: it shows that the copy can carry training. A new
strategy is not expected before LS2. One seed against one seed cannot show "about the same": the scripted run itself
read between 461 and 669 of 1,000 on its way to 644. Hence two seeds per arm, and a reading rule written before the
runs (PROPOSED: per cell and on the pooled row, route 3 "level with route 2" when its two seeds lie inside or above
the spread of route 2's two seeds widened by the 95 % interval of one read; INFO, not a gate of record). The design
review checks this rule.

**Held-out read in LS1.4 (INFO).** Each route 3 team is also scored against players that were in no training pool:
the trained teams of route 1 (the velocity Guard and Strike teams of L5.1, T77 and T80) and, for the Strike teams,
`guard_mark_inside`.

## 6. The later stages (outlines; each gets its own design note before code)

Order by R41: LS2 → self-play → LS3.

| Stage | What it adds | Open questions for its note |
|---|---|---|
| **LS2 Fine-tune** | the skill network trained by the game reward at one command per tick, with a tie that keeps each code near its script, weakened step by step; skills and heads trained in turns | the exploration noise of the skill network at 20 Hz; the tie's schedule; the control without a tie (expected to lose the codes); whether it is built on today's per-slot heads or on the shared actor of learner v2 |
| **Self-play** (LS4 League on the route page) | a pool entry that loads a saved team, so a team trains against past and present trained teams as well as the scripts; saved exploits (a Strike team trained against a frozen Guard team, and the reverse) kept as permanent pool entries | whether it can start on the heads of LS1.4 before LS2 (the design review's first question); how turns are taken and when a team is added to the pool; how a cycle (A beats B beats C beats A) is detected; the cost per turn |
| **LS3 Free codes** | skill codes with no script, rewarded for being distinct and useful | whether it is needed at all once self-play has run; the diversity reward |
| **Robustness suite** | held-out opponents, drone loss, filter mismatch (PLAN §1) | the shared actor and drawn team sizes; tier 2 |

**The held-out set, PROPOSED, to be fixed before self-play is designed:** (a) the trained teams of route 1 (they share
no skill with route 3); (b) `guard_mark_inside`; (c) one Strike script and one Guard script taken out of the
self-play training pools (which ones: the design review; LS1.4 keeps the full pools, so that it compares with route
2); (d) at the end, a new exploiter trained against the frozen final team: the strongest test, and the last one.

## 7. What the owner is asked

| # | Question | State |
|---|---|---|
| 1 | The lead's reading of R39 (row R39 of section 1): all stages; the 5 GPU-h announce rule; the 200 in the settings file | **open.** Until confirmed, GPU launches stay inside R36's 1.0 GPU-h (the distillation and its clips) |
| 2 | The LS1 pass limits | the owner sets them after job LS1.5 (R38) |
| 3 | The word for the build | after the design review's findings and this file have been read |
| 4 | The held-out set (section 6) | proposed; asked with the self-play note |
| 5 | The route page [LEARNED_SKILLS_ROUTE.md](../LEARNED_SKILLS_ROUTE.md), its figures and the slides still show the order LS1, LS2, LS3, LS4 and "LS1 budget about 1 GPU-hour" | redraw them for R39 to R41: yes or no. Its "Where it stands" table was already brought up to R36 to R38 on 25 Nov (`a133ba25`) |

What runs without asking once the build has the owner's word: the builds, the CPU jobs, the GPU jobs as listed here,
the records. What always comes back: the limits (R38), a failed gate, a single job above 5 GPU-h (announced), every
later stage's design note.

## 8. What each version changed

**v3 (R39 to R41).** The aim is a useful policy (section 2 says what that asks beyond route 3). No cap: jobs state
their hours, section 1 row R39. LS1.4 is the full head training on both sides with two seeds per arm, in place of v2's
optional run 0. Self-play before LS3. The held-out set is named as a decision. Corrected from what the lead told the
owner on 25 Nov: a saved team cannot be a training opponent with today's code (the pool and the drivers take script
names only), so self-play is a new build.

**v2 (checked against the code).** "Checked" names what was read.

| # | Correction | Checked |
|---|---|---|
| 1 | The launcher would refuse `--task LS1.1`: the LS1 tasks need the task table, the settings file, PLAN §9 and their test | `ste/config.py:37-48, 107-113, 181-212`; `ste/budget.py:232-258` |
| 2 | The 3-D clip script cannot draw an LS1 team; a clip path is added (job LS1.6) | `scripts/ste_l5_clips3d.py:94, 134-170`; `ste/post_run.py:70-84` |
| 3 | The equivalence read moves to the CPU: its positive control against T44 can only be read there | `ste/exploit.py:57` |
| 4 | A noise-floor read (job LS1.5) before the limits are set: "every cell within 30 wins of 1,000" over 130 to 150 cells may fail by chance alone | two independent samples of 1,000 games at a rate near one half differ by about 22 wins (one standard deviation) |
| 5 | The cell count of the equivalence read: 150 for Guard, 130 for Strike (the plan's section 8 costed 50 per side) | plan section 4; `configs/ste_l3/skills_gates.toml:45-46` |
| 6 | `--min-s` comes from the smoke's timing | `scripts/ste_job.py` (`wait`: ENDED_EARLY under `--min-s`) |
| 7 | The skill network file is named per team | plan section 3 |
| 8 | Heads trained on the scripts are refused on a skill network by the plan's own load rule; settled in v3 by R40 (the heads are trained on the skill network) | plan Task 2 (`skills_meta`); `ste/export.py:302` |

Confirmed, not changed: the scripts keep no memory between ticks, and each drone's command is computed from its own
row of the observation and its slot in the team (`opponents/scripted.py:58-63, 88-103, 252-262, 320-330, 408-460`;
excerpts read, not every line: a point for the design review); the only script with a random draw is the `random`
player (`scripted.py:78-82`), which is not a skill; `two_level_dispatch` has 12 calls in 9 files, as the plan says.
