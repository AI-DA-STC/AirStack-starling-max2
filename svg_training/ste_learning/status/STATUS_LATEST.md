INTERNAL · the latest status of STE's own learning track and the NUS port, overwritten at every update by the `train-status` skill · [../README.md](../README.md); the history: [LOG.md](LOG.md)

**Status, 2026-11-25 19:48 (+08:00) (asked: full status)** · RTX 5090 · GPU 3 % / 49 W / 1.8 of 32 GB · 0 training processes (0 paused)

**Main track:** route 3 (the learned-skills route), merge M1: 6 of 7 tasks built and through QC, the last (T7, the calibration read) being built · **Side track:** none

**Plain summary.** Since 14:28: the owner's rulings R42 to R47 (the build's go, no cap confirmed, self-play timing, page redraw, a run 0 per Strike seed, shorter stop rules); the builder's task plan for LS1 and LS1.4 written and checked against the code in two rounds (12 serious findings fixed; round 2's fixes not re-checked); the route page, figures and slides redrawn; merge M1 built task by task, each passing independent QC the first time. The pipeline check's six trained checkpoints, four exports and saved settings load unchanged with M1's code (checked by the lead). Nothing trained, 0 GPU-h on route 3.

## Watch

![The five steps of route 3 in their order: LS1 Distil, head training, LS2 Fine-tune, self-play, LS3 Free codes](../figures/ls_four_stages.png)

The new order of route 3's steps (R41). Nothing is built or run on the GPU yet.

## Phases

| Phase | Status | Math library | Simulator | What |
|---|---|---|---|---|
| NUS port Phases 1–4 | DONE | JAX (NUS), PyTorch | NUS 2-D game (JAX); copy of NUS 2-D game (PyTorch); tier 1; tier 2 Isaac Lab | port, conversion, ladder rows |
| NUS port Phase 5 | PAUSED (5.1 FAIL T43) | PyTorch | tier 1 fast engine | route (b) stopped; STE Guard policy T41 kept |
| NUS port Phase 6 docs | DONE (passes 1, 2) | none | none | public docs |
| L0 Game definition | DONE (G0 ruled 22 Nov) | PyTorch | tier 1; tier 2 Isaac Lab | |
| L1 Drone model | DONE except L1.6 (waits on L1.3 + NEAR-962) | PyTorch | tier 1; tier 2; AirStack simulator (logs) | |
| L2 Game rules in training | DONE | PyTorch | tier 1; tier 2 Isaac Lab | |
| L3 Learner (two routes) | DONE | PyTorch | tier 1; tier 2 Isaac Lab (smoke) | |
| L4–L6 pipeline check | DONE, both routes PIPELINE WORKS (INFO) | PyTorch | tier 1 fast engine; tier 2 Isaac Lab (smoke) | 2.29 of 20 GPU-h |
| ▶ Route 3, LS1 Distil and LS1.4 Head training | BUILDING (merge M1 of four) | PyTorch | tier 1 fast engine | the scripts copied into a skill network per team, then the heads trained on it |
| Route 3, LS2, self-play, LS3 | NOT STARTED (each needs its design note) | PyTorch | tier 1 fast engine | order by R41 |
| L7–L9 | NOT STARTED | — | AirStack simulator; real flight | owner's gate |

## Route 3, merge M1, task by task

From [the task plan](../drafts/LS1_TASK_PLAN.md) section 2; branch `ls1-m1`, worktree `~/AirStack-starling-max2-ls1m1`.

| ID | Plain name | Status | Simulator | Result / ETA |
|---|---|---|---|---|
| — | Design check of M1 against the code (two parts) | DONE | none | no blocker; corrections passed to the builders |
| LS1-M1-T1 | The route's budget section `[budget_ls]` and task IDs | DONE, QC PASS | none | `604b76fd` |
| LS1-M1-T2 | Job status shows the route's hours; hours carried from the other machine | DONE, QC PASS | none | `e3574028` |
| LS1-M1-T3 | The skill network: two paths, save and load with refusals | DONE, QC PASS | tier 1 (CPU tests) | `254079e4` |
| LS1-M1-T4 | The setting that switches skills to the network; net-backed dispatch | DONE, QC PASS | tier 1 (CPU tests) | `bf86d183` |
| — | The pipeline check's real files with M1's code | PASS | CPU | 6 checkpoints load, 4 exports reload, pilot and run 0 settings equal |
| — | `test_dependencies` broken on `development` since `402a66ab` (deck script imports) | FIXED on the branch | none | `c45a7736` |
| LS1-M1-T5 | Game set-ups of the reads, either team | DONE, QC PASS | tier 1 (CPU tests) | `74c64ca6` |
| LS1-M1-T6 | Deliberately changed scripts for the calibration (own file) | DONE, QC PASS | tier 1 (CPU tests) | `c9b78872` |
| LS1-M1-T7 | Paired statistics and the calibration read (job LS1.5) | RUNNING (builder) | tier 1 (CPU) | then its QC |
| — | Full test suite on the M1 branch | QUEUED | CPU | about 40 min, nothing merged while it runs |
| LS1.5 | Calibration read | QUEUED (after the merge) | tier 1 (CPU) | then the owner sets the limits (R38) |

GPU-h on route 3 so far: 0 (`[budget_ls]`, 200 by R43). L3–L6: 2.291 of 20. L1 + L2: 4.447 of 13 (`ste_job.py status`: own rows 0.907, carried 3.540).

## Other workstreams

| ID | Plain name | Status |
|---|---|---|
| — | Route 3 route page, figures and slides redrawn (R45) | DONE, one reviewer, merged |
| — | Route 3 builder's task plan | DONE, two check rounds, merged; round 2's fixes not re-checked |
| — | Learner v2 note | NOT STARTED: after LS1 (R37) |
| NEAR-962 | Planned-pushes flight; the Crazyflie commanded gaps | unchanged from 24 Nov |

**Next.** 1) LS1-M1-T7 and its QC, then the full suite on the M1 branch, then merge M1 into `development`. 2) LS1.5 calibration read (CPU), then the limit options to the owner. 3) Merge M2 (distillation and the copy check) in parallel with the owner's limits.

**Waiting on you.** Nothing now. Next: the LS1 pass limits and the LS1.4 margin (R38, after LS1.5).

**Usage:** GPU 0 on route 3. Agents since 14:28: the task-plan workflow (33 runs, 5.1 M tokens: Opus scouts, writer, fixer; Sonnet checkers and refuters), M1 part 1 (9 runs, 1.1 M tokens), M1 part 2 (6 runs so far). Advisor (Fable 5.2) twice since 14:28 (before M1, after the plan). Checks: docs check and the document test set at each docs merge; no full suite yet (M1's comes before its merge).

**Ready to push.** 13 commits on `development` (`d70b4e01` to `97e85a31`, plus this status): rulings R42 to R47, the route page redraw, the task plan, HANDOFF; mirror updated; push from GitHub Desktop. `main` unchanged.
