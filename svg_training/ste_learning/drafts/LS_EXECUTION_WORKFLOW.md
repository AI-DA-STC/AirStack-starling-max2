INTERNAL · DRAFT for the owner's review: how route 3 (the learned-skills route) would be executed: what is added to the pipeline, which jobs run, in what order, on which machine, at what cost, and where the owner is asked · nothing here is approved, built or run · the route explained: [../LEARNED_SKILLS_ROUTE.md](../LEARNED_SKILLS_ROUTE.md); the task-level plan: [LEARNED_SKILLS_BRIDGE_PLAN.md](LEARNED_SKILLS_BRIDGE_PLAN.md)

# Route 3 execution workflow (draft, 25 Nov 2026)

Written 25 Nov 2026 by the lead (Opus 5.5) for the owner to review before anything is built. Stage LS1 is given job by
job with exact commands. LS2 to LS4 are listed so the whole path is visible; their jobs are provisional and come back
with their own notes and costs after the gate before them.

## 0. In one screen

| | LS1 Distil (asked now) | LS2 to LS4 (not asked now) |
|---|---|---|
| Adds to the pipeline | 2 new modules, 2 new drivers, 1 gate file, small changes to the skills switch and the export | a skill-level learner, a diversity reward, league entries |
| Changes existing behaviour | no: a new setting whose default keeps today's behaviour bit for bit | the same rule |
| Jobs | 8 (4 GPU, 4 CPU), section 3 | about 15 to 25, provisional |
| GPU-hours | **1.0 cap** (about 0.7 expected), plus **0.3 optional** (job LS1.4) | about 15 to 30, estimate only |
| Owner asked | the budget, the order against learner v2, whether LS1.4 runs | at each later stage |
| Wall time | build about 1 to 2 days of agent work; GPU about 1.5 h | — |

## 1. What is added to the pipeline

### LS1 (the only stage asked for now)

| File | New or changed | What it does | Off means identical | Tests |
|---|---|---|---|---|
| `source/svg_training/ste/skill_net.py` | new | the skill network (one per team, inputs: what the drone sees, its slot, the skill code; output: a velocity); save and load with refusals (wrong team, wrong skill list or order, wrong team size, scripts edited since the fit); the net-backed dispatch that the two-level heads drive | not used unless the setting says so | `tests/test_ste_ls1_skill_net.py`, `test_ste_ls1_dispatch.py` |
| `source/svg_training/ste/distil.py` | new | data collection from scripted games (every script labels every state), the supervised fit, the relabelling rounds (the network flies, the scripts label), the per-skill error report | not used by any existing driver | `tests/test_ste_ls1_distil.py` |
| `source/svg_training/ste/skills.py` | changed, about 60 lines | `[learner] skill_source = "scripts" \| "net"` and `skill_net = "<file>"`; the one factory every driver uses (`two_level_dispatch`) returns the net-backed dispatch when asked; checkpoints record which skill source they were trained on | default `"scripts"`: today's dispatch, checked bit for bit | `tests/test_ste_ls1_dispatch.py` plus the existing `test_ste_l3_skills.py`, `test_ste_l3_two_level.py` |
| `source/svg_training/ste/export.py`, `scripts/ste_l6_export.py` | changed, about 80 lines | a new export type for the skill network (ONNX, schema `ste-check-skillnet-0`, golden rows, reload check) | existing export types unchanged | `tests/test_ste_ls1_export.py` plus `test_ste_l3_export.py` |
| `scripts/ste_ls1_distil.py` | new | the distillation driver under the run contract (resume, cap, exit codes), launched through `ste_job.py` | — | in `test_ste_ls1_distil.py` |
| `scripts/ste_ls1_equivalence.py` | new | the gate read: controls first, then the copy against the scripts, cell by cell; verdict DISTILLED / NOT DISTILLED / INCONCLUSIVE | — | `tests/test_ste_ls1_equivalence.py` |
| `configs/ste_ls1/distil_gates.toml` | new | sizes, rounds, network size, limits, controls, seed; hashed before any run | — | its own load test |
| `configs/ste_learning.toml` | changed | the LS1 task caps (LS1.1 to LS1.4) inside the L3–L6 cap, only after the owner's answer | — | `tests/test_ste_config.py` |

**Not touched:** the game engine and its rules, the safety filter, the opponent pool, the scoring, the run contract,
the GPU-hour ledger, the job launcher, the 3-D clip hook, the two-level learner and its PPO step, every existing gate
file, AirStack, Isaac Lab.

### LS2 to LS4 (for the picture only; each gets its own design note)

| Stage | Expected additions | Depends on |
|---|---|---|
| LS2 Fine-tune | the skill network as a trained policy (a noise level per skill code); a skill-level PPO step at one command per tick with the tie to the scripts as an extra loss; a driver that alternates skill training and head training; gate file | LS1 DISTILLED on both sides; learner v2 (shared actor, team critic) |
| LS3 Free codes | extra skill codes with no script; a diversity reward and the small classifier it needs; heads widened | LS2 passed |
| LS4 League | saved exploits as permanent league entries; scoring against held-out opponents | the league of learner v2 |

## 2. How the work runs

Every task follows the track's usual path (PLAN §6), with the owner's model rule:

```
design check (ste-architect, read-only)
  -> build in its own worktree, tests first (ste-software-engineer, Opus)
  -> QC review of the build (ste-test-qc-engineer, Sonnet)
  -> lead merges to development (fast-forward); full test suite once per code merge, in the background
  -> gate file written and hashed (lead; QC drafts the limits) BEFORE any run
  -> job launched through scripts/ste_job.py (budget check, heartbeat, exit code, clips)
  -> verdict read: controls first, then the result
  -> record + ledger row + clips; two reviewers (it feeds the owner's route choice)
  -> status update to the owner
```

The Fable 5.2 advisor is asked before the build starts, before the gate is hashed and before LS1 is reported done.
One fix at a time if something fails.

**Build order (LS1):** three merges.

| Merge | Plan tasks | Content |
|---|---|---|
| M1 | 1, 2 | skill network, save/load, net-backed dispatch, the setting (default off) |
| M2 | 3, 4, 5 | distillation, driver, gate file, equivalence read |
| M3 | 6 | export of the skill network |

## 3. The jobs (LS1)

Machine: whichever is in use (owner rule); the RTX 5090 on weekdays. Every GPU job goes through the launcher, for
example:

```
scripts/ste_job.py launch --task LS1.1 --name ls1_distil_guard --run-dir runs/<date>_ste_ls1_distil_guard \
  --min-s 300 --gpu-h 0.4 --settings configs/ste_learning.toml -- \
  python scripts/ste_ls1_distil.py --gates configs/ste_ls1/distil_gates.toml --side guard \
  --run-dir runs/<date>_ste_ls1_distil_guard --cap-h 0.4 --expect-gates-sha256 <hash>
```

| Job | Plain name | Where | Command (driver, arguments) | Cap GPU-h | Needs | Gives | Owner asked |
|---|---|---|---|---|---|---|---|
| S1 | Full test suite after each code merge (3 times) | CPU, background | `pytest` (full suite, about 40 min each) | 0 | each merge | pass or fail | no |
| LS1.0 | Smoke of the distillation and the read | CPU | `ste_ls1_distil.py` with 16 games, 2 rounds; `ste_ls1_equivalence.py` on 24 starts | 0 | M2 | the plumbing works end to end | no |
| LS1.1-G | Distil the Guard team's 5 skills | GPU | `ste_ls1_distil.py --side guard` (4,096 games, 4 rounds of 600 ticks, fit after each) | 0.4 | LS1.0, gate hashed | `skill_net_guard.pt`, fit report per skill, 4 clips | **budget** |
| LS1.1-S | Distil the Strike team's 6 skills | GPU, side by side with LS1.1-G | `ste_ls1_distil.py --side strike` | 0.4 | as above | `skill_net_strike.pt`, fit report, clips | **budget** |
| LS1.2-G | Equivalence read, Guard | GPU (scoring only) | `ste_ls1_equivalence.py --side guard` (controls, then 5 fixed-choice cells and 20 mixed cells against every Strike script, 1,000 games each) | 0.1 | LS1.1-G | verdict DISTILLED / NOT DISTILLED / INCONCLUSIVE | no |
| LS1.2-S | Equivalence read, Strike | GPU (scoring only) | `ste_ls1_equivalence.py --side strike` | 0.1 | LS1.1-S | verdict | no |
| LS1.3 | Export and reload check of both skill networks | CPU | `ste_l6_export.py` with the skill-network type; reload in a fresh process | 0 | DISTILLED | ONNX files, `interface.toml`, golden rows | no |
| LS1.4 | **Optional.** Skills run 0 again, with the skill network in place of the scripts | GPU | `ste_exploit_l012.py --run0` on a copy of the skills gate file with `skill_source = "net"` | 0.3 | DISTILLED (Strike) | does the two-level learner still train on the copy? Compared with the 644 of 1,000 of the scripted run (same mark 0.554) | **yes, optional** |
| R1 | Record, ledger rows, clips, two reviewers | CPU | `records/<date>_ste_ls1_distil_record.md`; 3-D clips of network-flown games beside the same starts flown by scripts | 0 | LS1.2 (and LS1.4 if run) | the read for the owner | — |

**Totals:** LS1.1 to LS1.3: cap 1.0 GPU-h, expected about 0.7. With LS1.4: cap 1.3. Charged to the L3–L6 cap
(17.7 of 20 GPU-h left on 25 Nov 2026), not to the hours planned for the second short check on learner v2.

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

## 5. What the owner is asked now

1. **LS1 budget:** 1.0 GPU-h from the L3–L6 cap. Yes / no / other.
2. **Optional LS1.4** (0.3 GPU-h): retrain the heads on the skill network to show the training path works on it.
   Lead's recommendation: yes; it is the first evidence that the copy is usable, not only similar.
3. **Order:** LS1 now, beside the learner v2 note (LS1 needs no v2 part); LS2 onwards on learner v2.
   Lead's recommendation: yes.
4. **Review before build:** the plan and this workflow get the two-reviewer design review first (R22). Yes / skip.

What runs without asking once these are answered: the builds, the CPU jobs, the GPU jobs inside the approved caps,
the records. What always comes back: a failed gate, any hour above the cap, LS2.
