INTERNAL · DRAFT v2 for the owner's review: how route 3 (the learned-skills route) would be executed: what is added to the pipeline, which jobs run, in what order, on which machine, at what cost, and where the owner is asked · the LS1 budget and its order are ruled (R36, R37); nothing is built or run; v2 is not yet reviewed · the route explained: [../LEARNED_SKILLS_ROUTE.md](../LEARNED_SKILLS_ROUTE.md); the task-level plan: [LEARNED_SKILLS_BRIDGE_PLAN.md](LEARNED_SKILLS_BRIDGE_PLAN.md)

# Route 3 execution workflow (draft v2, 25 Nov 2026)

Written 25 Nov 2026 by the lead (Opus 5.5) for the owner to review before anything is built. **v2, the same day** (the
lead, a Fable 5.2 session, with the advisor tool): the first version was checked against the code, eight corrections
were folded in, and the owner's answers were recorded. Section 6 lists what v2 changed and why. This file is about
route 3 only (the learned-skills route); "v2" is the second version of this file, not a route.

Stage LS1 is given job by job. LS2 to LS4 are listed so the whole path is visible; their jobs are provisional and come
back with their own notes and costs after the gate before them. Next step: the design review of this file and the plan
by two reviewers (R22, and R35's "no code and no run before the design review").

## 0. In one screen

| | LS1 Distil (ruled: build now) | LS2 to LS4 (not asked now) |
|---|---|---|
| Adds to the pipeline | 2 new modules, 4 new scripts, 1 gate file, small changes to the skills switch, the export and the budget table | a skill-level learner, a diversity reward, league entries |
| Changes existing behaviour | no: a new setting whose default keeps today's behaviour bit for bit | the same rule |
| Jobs | 10, or 11 with the optional LS1.4 (3 or 4 on the GPU, the rest on the CPU), section 3 | about 15 to 25, provisional |
| GPU-hours | **1.0 cap, approved (R36)**: 0.8 distillation, 0.1 clips, 0.1 spare; plus **0.5 optional** (job LS1.4, not ruled) | about 15 to 30, estimate only |
| Owner asked | whether LS1.4 runs; the pass limits after the noise-floor read (R38) | at each later stage |
| Wall time | build about 1 to 2 days of agent work; GPU about 1.5 h (estimate) | — |

"Distil" means fitting a network to imitate a behaviour. LS1 does not copy any pipeline code: the game, the trainer,
the scoring and the export of phases L1 to L6 are used as they are. What is copied is the **behaviour** of the eleven
hand-written scripts of `opponents/scripted.py` (Guard: parked at the centre, parked on a ring, mark the edge, mirror,
field; Strike: straight, flank, high, low, sacrifice, converge): a network per team learns to give the same velocity
command as each script for the same view, selected by a skill code.

## 1. What is added to the pipeline

### LS1 (the only stage asked for now)

| File | New or changed | What it does | Off means identical | Tests |
|---|---|---|---|---|
| `source/svg_training/ste/skill_net.py` | new | the skill network (one per team, inputs: what the drone sees, its slot, the skill code; output: a velocity); save and load with refusals (wrong team, wrong skill list or order, wrong team size, scripts edited since the fit); the net-backed dispatch that the two-level heads drive | not used unless the setting says so | `tests/test_ste_ls1_skill_net.py`, `test_ste_ls1_dispatch.py` |
| `source/svg_training/ste/distil.py` | new | data collection from scripted games (every script labels every state), the supervised fit, the relabelling rounds (the network flies, the scripts label), the per-skill error report | not used by any existing driver | `tests/test_ste_ls1_distil.py` |
| `source/svg_training/ste/skills.py` | changed, about 60 lines | `[learner] skill_source = "scripts" \| "net"` and the skill network file **per team** (v2: one file per team, for example `skill_net = { guard = "<file>", strike = "<file>" }`; the first version had one path); the one factory every driver uses (`two_level_dispatch`, 12 calls in 9 files, counted 25 Nov) returns the net-backed dispatch when asked; checkpoints record which skill source they were trained on | default `"scripts"`: today's dispatch, checked bit for bit | `tests/test_ste_ls1_dispatch.py` plus the existing `test_ste_l3_skills.py`, `test_ste_l3_two_level.py` |
| `source/svg_training/ste/export.py`, `scripts/ste_l6_export.py` | changed, about 80 lines | a new export type for the skill network (ONNX, schema `ste-check-skillnet-0`, golden rows, reload check) | existing export types unchanged | `tests/test_ste_ls1_export.py` plus `test_ste_l3_export.py` |
| `scripts/ste_ls1_distil.py` | new | the distillation driver under the run contract (resume, cap, exit codes), launched through `ste_job.py`; 2-D clips with the height panel of network-flown games | — | in `test_ste_ls1_distil.py` |
| `scripts/ste_ls1_equivalence.py` | new | the gate read: controls first, then the copy against the scripts, cell by cell; verdict DISTILLED / NOT DISTILLED / INCONCLUSIVE | — | `tests/test_ste_ls1_equivalence.py` |
| `scripts/ste_ls1_noise_floor.py` | **new in v2** | scripts against scripts, no network: each cell of the gate read is played twice on the same starts, once as written and once with a small bounded error added to the team's commands (PROPOSED sizes 0.01, 0.02, 0.05, 0.1 in command units); reports how many of 1,000 games change per cell. It shows what difference in wins a copy of a given command error can be expected to cause, so the limits are neither impossible nor empty | — | `tests/test_ste_ls1_noise_floor.py` |
| the 3-D clips of an LS1 team | **new in v2** | `scripts/ste_l5_clips3d.py` draws only a finished L5 training run (it needs `results.json`, `agent_final.pt`, `eval_info.npz`; checked 25 Nov), so it cannot draw a skill network flown on a fixed choice. Either a small `scripts/ste_ls1_clips.py` that feeds the same renderer, or one more input type in the clip script: the design review chooses | the existing clip script and its post-run hook behave as today | its own test file |
| `configs/ste_ls1/distil_gates.toml` | new | sizes, rounds, network size, limits, controls, seed; hashed before any run, after the owner has set the limits (R38) | — | its own load test |
| `source/svg_training/ste/config.py`, `configs/ste_learning.toml`, `ste_learning/PLAN.md` §9, `tests/test_ste_config.py` | **changed (v2: four files, not one)** | the task table `TASK_IDS` has no LS1 task and a budget section's name must spell its phases (`ste/config.py:37-48, 181-212`), so today the launcher refuses `--task LS1.1`. LS1 gets its tasks and caps: PROPOSED its own section `[budget_ls1]` with the 1.0 GPU-h of R36 (the lead counts it against the 20 of R23 in the record; the code does not add two sections); the alternative is to widen the L3–L6 section. The design review chooses | every existing task and cap unchanged | `tests/test_ste_config.py` (it ties the file to PLAN.md) |

**Not touched:** the game engine and its rules, the safety filter, the scripts (they are the teachers; their sha256 is
pinned in the skill network file), the opponent pool, the scoring, the run contract, the GPU-hour ledger, the job
launcher, the post-run 3-D clip hook, the two-level learner and its PPO step, every existing gate file, AirStack,
Isaac Lab.

### LS2 to LS4 (for the picture only; each gets its own design note)

| Stage | Expected additions | Depends on |
|---|---|---|
| LS2 Fine-tune | the skill network as a trained policy (a noise level per skill code); a skill-level PPO step at one command per tick with the tie to the scripts as an extra loss; a driver that alternates skill training and head training; gate file | LS1 DISTILLED on both sides; learner v2 (shared actor, team critic) |
| LS3 Free codes | extra skill codes with no script; a diversity reward and the small classifier it needs; heads widened | LS2 passed |
| LS4 League | saved exploits as permanent league entries; scoring against held-out opponents | the league of learner v2 |

## 2. How the work runs

Every task follows the track's usual path (PLAN §6), with the owner's model rule:

```
design review of this file and the plan (two reviewers, R22) -> the lead revises
  -> design check (ste-architect, read-only)
  -> build in its own worktree, tests first (ste-software-engineer, Opus)
  -> QC review of the build (ste-test-qc-engineer, Sonnet)
  -> lead merges to development (fast-forward); full test suite once per code merge, in the background
  -> noise-floor read (CPU) -> the lead advises, THE OWNER SETS THE LIMITS (R38)
  -> gate file written and hashed (lead) BEFORE any run
  -> job launched through scripts/ste_job.py (budget check, heartbeat, exit code, clips)
  -> verdict read: controls first, then the result
  -> record + ledger row + clips; two reviewers (it feeds the owner's route choice)
  -> status update to the owner
```

The Fable 5.2 advisor is asked before the build starts, before the gate is hashed and before LS1 is reported done.
One fix at a time if something fails. The owner runs the build session on Opus 5.5 at high effort as a multi-agent
workflow (R37); reviewers and other checking agents stay on Sonnet 5.5.

**Build order (LS1):** three merges. No merge while the full suite or a run is going.

| Merge | Plan tasks | Content |
|---|---|---|
| M1 | 1, 2 | skill network, save/load, net-backed dispatch, the setting (default off); **v2:** the LS1 tasks in the budget table, the noise-floor script |
| M2 | 3, 4, 5 | distillation, driver, gate file, equivalence read |
| M3 | 6 | export of the skill network; **v2:** the 3-D clip path for an LS1 team |

## 3. The jobs (LS1)

Machine: whichever is in use (owner rule); the RTX 5090 on weekdays. Every GPU job goes through the launcher, for
example:

```
scripts/ste_job.py launch --task LS1.1 --name ls1_distil_guard --run-dir runs/<date>_ste_ls1_distil_guard \
  --min-s <from the smoke> --gpu-h 0.4 --settings configs/ste_learning.toml -- \
  python scripts/ste_ls1_distil.py --gates configs/ste_ls1/distil_gates.toml --side guard \
  --run-dir runs/<date>_ste_ls1_distil_guard --cap-h 0.4 --expect-gates-sha256 <hash>
```

`--min-s` is the shortest time a real finish can take; a finish under it is flagged ENDED_EARLY. It is set from the
timing of the smoke (LS1.0), not guessed (v2: the first version had 300 s).

The jobs in the order they run:

| Job | Plain name | Where | Command (driver, arguments) | Cap GPU-h | Needs | Gives | Owner asked |
|---|---|---|---|---|---|---|---|
| S1 | Full test suite after each code merge (3 times) | CPU, background | `pytest` (full suite, about 40 min each) | 0 | each merge | pass or fail | no |
| LS1.5 | **(v2)** Noise-floor read | CPU | `ste_ls1_noise_floor.py` (scripts only, the gate read's cells, T44's starts, 1,000 games each, four error sizes) | 0 | M1 | per cell and per error size: games changed, difference in wins; the lead's advice on the limits | **the owner sets the limits (R38)** |
| LS1.0 | Smoke of the distillation and the read | CPU | `ste_ls1_distil.py` with 16 games, 2 rounds; `ste_ls1_equivalence.py` on 24 starts | 0 | M2 | the plumbing works end to end; timings for `--min-s` and for the read on the CPU | no |
| — | Gate file written and hashed | — | `configs/ste_ls1/distil_gates.toml` with the owner's limits; QC reads it | 0 | LS1.5, the owner's limits | the hash every later job names | no |
| LS1.1-G | Distil the Guard team's 5 skills | GPU | `ste_ls1_distil.py --side guard` (4,096 games, 4 rounds of 600 ticks, fit after each) | 0.4 | LS1.0, gate hashed | `skill_net_guard.pt`, fit report per skill, 4 clips | no (inside R36) |
| LS1.1-S | Distil the Strike team's 6 skills | GPU, side by side with LS1.1-G | `ste_ls1_distil.py --side strike` | 0.4 | as above | `skill_net_strike.pt`, fit report, clips | no (inside R36) |
| LS1.2-G | Equivalence read, Guard | **CPU (v2)** | `ste_ls1_equivalence.py --side guard`: controls, then 30 fixed-choice cells (5 codes against the 6 Strike scripts) and 120 mixed cells (20 combinations against the 6), 1,000 games each, the copy and the scripts on the same starts | 0 | LS1.1-G | verdict DISTILLED / NOT DISTILLED / INCONCLUSIVE | no |
| LS1.2-S | Equivalence read, Strike | **CPU (v2)** | `ste_ls1_equivalence.py --side strike`: 30 fixed-choice cells (6 codes against the 5 Guard scripts) and 100 mixed cells | 0 | LS1.1-S | verdict | no |
| LS1.3 | Export and reload check of both skill networks | CPU | `ste_l6_export.py` with the skill-network type; reload in a fresh process | 0 | DISTILLED | ONNX files, `interface.toml`, golden rows | no |
| LS1.4 | **Optional.** Skills run 0 again, with the skill network in place of the scripts | GPU | `ste_exploit_l012.py --run0` on a copy of the skills gate file with `skill_source = "net"` | **0.5 (v2)** | DISTILLED (Strike); its reading rule written first | does the two-level learner still train on the copy? INFO, read beside the 644 of 1,000 of the scripted run (same mark 0.554) | **yes, optional, not ruled** |
| LS1.6 | **(v2)** 3-D clips of key games | GPU | 3 to 6 games per side, the copy beside the scripts on the same start, top view and 3-D view | 0.1 | LS1.2, M3 | MP4 and GIF for the record | no (inside R36) |
| R1 | Record, ledger rows, two reviewers | CPU | `records/<date>_ste_ls1_distil_record.md` | 0 | LS1.2 (and LS1.4 if run), LS1.6 | the read for the owner | — |

**Why the equivalence read is on the CPU (v2).** Its positive control is "the script team, through the same scoring
path, differs in 0 games from T44". T44's games are equal game for game only in a CPU replay (`ste/exploit.py:57`), so
on the GPU that control could not be read. The cells are cheap (150 and 130 cells of 1,000 games; the first version
counted 50). If the smoke shows the CPU read is too slow, the result cells (not the controls) move to the GPU on the
0.1 spare, announced first.

**Reading rule of LS1.4, to be written before it runs (v2).** It is one seed against one seed, and the scripted run
read between 461 and 669 of 1,000 on its way to 644. So LS1.4 is INFO: PASS or FAIL against the run's own mark 0.554
as the gate file says, and "not distinguishable from the scripted run" when the two 95 % intervals overlap. The cap is
0.5 because the scripted run used 0.284 GPU-h, and a cap of 0.3 would stop a slightly slower run before its end.

**Totals:** approved 1.0 GPU-h (R36): LS1.1 0.8, LS1.6 0.1, spare 0.1; expected use well under the cap (estimate; the
smoke gives the first timing). With LS1.4: 1.5. Charged to the L3–L6 cap (17.7 of 20 GPU-h left on 25 Nov 2026), not to
the hours planned for the second short check on learner v2.

**Stop rules (written into the gate file):**

- A control fails: INCONCLUSIVE; the cause is found and fixed on the CPU, and the run is repeated once, announced
  with its cost (as R34 allows for bug re-runs).
- NOT DISTILLED: no limit is moved. One announced fix round is allowed (more relabelling rounds or a larger network,
  inside the 1.0 cap); if it still fails, LS1 stops and the record says which skills do not copy and why.
- DISTILLED on one side only: that side may go on; the other side is reported.

## 4. Provisional jobs for LS2 to LS4 (not asked now)

| Stage | Jobs (provisional) | GPU-h (estimate) |
|---|---|---|
| LS2 | pilot per side; tie-weight schedule check; fine-tune per side (alternating skills and heads); `w = 0` control (expected to lose the codes); score against the best fixed mix of scripts and against the LS1 network; code classifier read; record | 5 to 8 |
| LS3 | diversity-only pretraining of the new codes; joint training; same-budget control without new codes; score; clip review to name the new skills | 10 to 20 |
| LS4 | exploit training against frozen teams (saved as league entries); league runs both sides; robustness suite (held-out attackers, drone loss) | open |

## 5. The owner's answers, and what is still asked

| # | Question | State |
|---|---|---|
| 1 | LS1 budget: 1.0 GPU-h from the L3–L6 cap | **ruled yes (R36)** |
| 2 | Optional LS1.4 (0.5 GPU-h, total 1.5): retrain the heads on the skill network to show that the training path works on it | **open.** Lead's recommendation: yes; it is the first evidence that the copy is usable, not only similar |
| 3 | Order: LS1 now or after learner v2 | **ruled: LS1 now, route 3 first (R37).** LS2 onwards stays proposed on learner v2 |
| 4 | Review before build | not a new question: R35 already requires the two-reviewer design review before any code |
| 5 | Who sets the LS1 pass limits | **ruled: the owner, on the lead's advice (R38).** Asked after job LS1.5 |

What runs without asking once the design review is done: the builds, the CPU jobs, the GPU jobs inside the approved
caps, the records. What always comes back: the limits (R38), a failed gate, any hour above the cap, LS1.4, LS2.

## 6. What v2 changed, and why

The first version was read against the code on 25 Nov 2026. "Checked" names what was read.

| # | Correction | Checked |
|---|---|---|
| 1 | The launcher would refuse `--task LS1.1`: the LS1 tasks need the task table, the settings file, PLAN §9 and their test, not the settings file alone | `ste/config.py:37-48, 107-113, 181-212`; `ste/budget.py:232-258` |
| 2 | The 3-D clip script cannot draw an LS1 team; a clip path and 0.1 GPU-h are added (job LS1.6) | `scripts/ste_l5_clips3d.py:94, 134-170`; `ste/post_run.py:70-84` |
| 3 | The equivalence read moves to the CPU: its positive control against T44 can only be read there | `ste/exploit.py:57` |
| 4 | A noise-floor read (job LS1.5) before the limits are set: "every cell within 30 wins of 1,000" over 130 to 150 cells may fail by chance alone | the cell count below; two independent samples of 1,000 games at a rate near one half differ by about 22 wins (one standard deviation) |
| 5 | LS1.4's cap 0.3 → 0.5 | the scripted run 0 used 0.284 GPU-h (pipeline record, T81) |
| 6 | LS1.4 gets a reading rule before it runs, as INFO | the scripted run's reads, 461 to 669 (pipeline record) |
| 7 | `--min-s` comes from the smoke's timing | `scripts/ste_job.py` (`wait`: ENDED_EARLY under `--min-s`) |
| 8 | The skill network file is named per team. And one open point for the design review: heads trained on the scripts (L5.2) would be refused on a skill network by the plan's own load rule (Task 2), so a whole team as "two network files" needs either a recorded allowance to fly script-trained heads on a DISTILLED network, or heads trained on the network; until that is decided LS1.3 exports the skill networks only | plan Task 2 (`skills_meta`); `ste/export.py:302` |

Also corrected: the cell count of the equivalence read (150 for Guard, 130 for Strike, where the plan's section 8
costed 50 per side); the stop rule "one fix round" is kept from the first version.

Confirmed, not changed: the scripts keep no memory between ticks, and each drone's command is computed from its own
row of the observation and its slot in the team (`opponents/scripted.py:58-63, 88-103, 252-262, 320-330, 408-460`;
excerpts read, not every line: a point for the design review); the only script with a random draw is the `random`
player (`scripted.py:78-82`), which is not a skill; `two_level_dispatch` has 12 calls in 9 files, as the plan says.
