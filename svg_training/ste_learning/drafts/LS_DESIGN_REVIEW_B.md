INTERNAL · the report of design reviewer B (build, pipeline, budget and export) on the route 3 execution workflow v3 and the learned-skills plan, 25 Nov 2026, as the reviewer wrote it (Sonnet 5.5, read-only, given the files and not the lead's conclusions); the lead checked its file references against the code and folded the findings into the workflow, whose section 9 is the summary · [LS_EXECUTION_WORKFLOW.md](LS_EXECUTION_WORKFLOW.md)

# Route 3 design review, reviewer B: build, pipeline, budget and export (25 Nov 2026)

A builder reads this file for the detail behind each finding (file and line, the exact change). Figures the reviewer marks as its own estimates are estimates. The workflow reviewed was the first v3 (commit `28184629`); the workflow has since been revised for these findings.

DESIGN REVIEW B (build, pipeline, budget, export) of LS_EXECUTION_WORKFLOW v3 and LEARNED_SKILLS_BRIDGE_PLAN. READ-ONLY. I created nothing in the repo. Scratch files are only under the session scratchpad, plus one CPU timing snippet and one ONNX export snippet held in memory.

All paths are relative to ~/AirStack-starling-max2-dev/svg_training. "Read" means I read the lines. "Grep only" is stated where that applies.

## FINDINGS, most serious first

**1. BLOCKER: the untrained-twin control fails under any net gate file, so every LS1.4 training job ends with exit 6 before it trains.**
- Claim: LS1.4 is "the same recipe ... with the skill network flying in place of the scripts". The driver `scripts/ste_exploit_l012.py` is not in the workflow's change list, and "Not touched" names only the learner and PPO step.
- Code:
  - `evaluate_controls` (`scripts/ste_exploit_l012.py:380-388`), phases "before" and "pilot": the untrained exploiter's cell is compared with the script cell of the first drone skill. It uses `replay_ok`, which on the CPU needs every game equal.
  - On CUDA (`exploit.py:803-807`) `replay_ok` needs holds and reaches within `replay_count_tol_cuda_games` (10) of the twin, and at most `replay_differ_tol_cuda_games` (20) games with a different outcome. Both limits are in `configs/ste_l3/skills_gates.toml`.
  - `run0_controls` (`ste_exploit_l012.py:921-933`) has the same check, and `run_run0` adds the script cell `(opp, strike_straight)` at 1000-1002.
  - A distilled net flies its own commands, not the script's. The 20-game limit is about the size of the equivalence gate (30 wins), and job LS1.5 is the read that measures this number.
  - A failure ends the run as exit 6: run 0 through `end_on` (1008, `ending` at 1008), a run of record through `end_on_controls` (`:468-473`, run at `:469`). `stop_on_fail = true` in `skills_gates.toml`. Exit 6 is terminal and never retried (`ste_job.py` docstring).
  - The pilot only records the FAIL in `pilot.json`; the pilot itself continues (no `ending` call in `pilot()`).
- Fix:
  - Under `skill_source = "net"`, replace the script twin with a net-backed twin: a fixed-choice `SkillTeam(ConstHeads(free, first drone skill))` on the same `NetTwoLevelDispatch`. Equality is then exact on the CPU.
  - Pass it in through `play_cells(players=...)`, which accepts `players` (`exploit.py:700`, wrapped in `HeldPlayer` at 691).
  - The edits are in `evaluate_controls`, `run0_controls`, the three `play_cells` call sites (`pilot` `timed_batch` 1171-1176, `run_run0` `play` ~1032-1035, `run_exploit` `play` ~455-458), plus tests.
  - Put this into M1 or M3 (it is in neither) and list the driver in the workflow's change table.
  - The same twin logic exists in `scripts/ste_l4_suite.py:62-72` and `ste_l3_run0_ceiling.py:123-128`. The L4.2 suite would also fail under a net gate (`EXACT_TOL=1e-12`, twin from `drone_skills[side][0]`). That is not planned for LS1, so keep it out of LS1.4.

**2. MAJOR (BLOCKER if built as the plan words it): `skills_meta` gains a key and every existing checkpoint and export reload breaks.**
- Claim (plan Task 2): "for a script-backed dispatch the dictionary is unchanged apart from `skill_source: scripts`; checkpoints saved before this change load as scripts".
- Code:
  - Equality is whole-dict: `exploit_train.py:411` (resume, `load_state`) and `:455` (`skill_team_from_modules`). Used by `make_videos` (`ste_exploit_l012.py:803`), `ste_l5_clips3d.py:341`, `ste_l6_export.py:51`, `ste_tier2_l013.py:383` and `ste_l3_isaac_smoke.py:386`.
  - `export.py:304-306` (`_skills_reload`) and `:275-279` (`reload_check`) compare against a literal dict of the six old keys.
  - The skills JSON is also written into every ONNX file (`export.py:131-132`).
  - No normalisation path exists for old files. Adding the key unconditionally refuses all six pipeline-check `agent_final.pt` files and all four L6.2 exports.
- Fix:
  - `skills_meta` returns today's dict unchanged for scripts. It adds `skill_source` and `skill_net_sha256` only for a net dispatch.
  - A net-saved checkpoint is then refused by a scripts dispatch, and an old checkpoint by a net dispatch.
  - Add a test that pins the literal key set for scripts and one that loads a literal old dict.
  - Test files that would catch a break: `tests/test_ste_l3_export.py`, `test_ste_l6_export.py`, `test_ste_l3_two_level_learner.py:380`. Line 380 compares meta against itself, so it would not catch an added key.

**3. MAJOR: `learner_table` must carry the skill source, or an old script pilot is accepted silently for a net gate file.**
- Code:
  - `skills_pilot_problem` (`ste_exploit_l012.py:236-249`) compares only `learner_block(gates)["learner"]` (`learner_table`, `skills.py:315-324`). It does not compare the gate hash. `recipe_problem` compares only `side_overrides.strike`.
  - Run 0 is pinned by hash: `run0_problem` (`exploit.py:933-939`) refuses unless `run0.gates_sha256 == gates.sha256`. It also needs the same `[learner]` table (`exploit.py:961`), status PASS (964), and `cap_h` equal to the run's cap (975-976).
  - A real pilot checked: `runs/2026-11-25_ste_l3_pilot_skills/pilot.json` records `learner` and `strike_recipe` (T41, `{}`) and `gates_sha256 6c83762d689a`.
- Consequences:
  - `learner_table` gains `skill_source` and per-side net sha only when the source is net, so scripts files stay byte-identical. Then the net gate file needs its own pilot. Without this the script pilot's rates and recipe are accepted.
  - Every new gate file needs its own run 0.
  - The heads gate file is hashed twice: the FILL step (header of `skills_gates.toml`) rewrites `side_overrides.strike` and `game_steps_per_run` from the pilot, so the hash changes after the pilot. The pilot rule (`exploit.py:309-` `strike_recipe`, probes against g*) may pick the shaped Strike recipe on the net while route 2 got "T41 recipe". Then the two arms differ in recipe and the comparison is confounded. Say so in the reading rule.
  - `game_steps_per_run = 550M` "same budget as route 2" cannot be promised; the pilot decides. My estimate of the net's cost per tick on the GPU is negligible against a ~18 ms tick (16384 games at ~890k game-steps/s), but that is arithmetic, not a GPU measurement.

**4. MAJOR: LS1.4-R (a second seed of route 2) is under-budgeted and needs a new gate file.**
- Claim: LS1.4 job table, "LS1.4-R, 0.4 each, Needs: —".
- Code:
  - You cannot add a variant to `configs/ste_l3/skills_gates.toml`. Its hash is pinned in six run folders, and `tests/test_ste_l3_pipeline_gates.py` checks the four files as one template.
  - A second route-2 seed therefore needs a new gate file. By finding 3 that file needs its own run 0, which is a Strike job (about +0.28 to 0.4 GPU-h, not in the 2.9 asked).
  - The old L3.3 pilot is accepted for it, because the `[learner]` table is equal.

**5. MAJOR: the existing reload check refuses a route-3 heads export, and the L6 reader cannot read route 3.**
- Code:
  - `_skills_reload` (`export.py:302`) builds a script `TwoLevelDispatch` directly and compares commands with the golden rows. In `export_policy` the golden commands come from `_dispatch`, which would be net-backed. The check would raise "skills golden rows ... commands differ".
  - `reload_check` picks one route from one `policy_schema` (`export.py:259-261`). There is no place for a second graph.
  - `ste_l6_read.py:54-61` hard-codes `ROUTES`, `TASKS` and `SCHEMAS`. `read_export` (`:277-286`) expects one folder per side with the schema and `gates_sha256`. Route 3 cannot be read.
  - The workflow lists no script that reads LS1.4 (two seeds against two seeds with the spread rule). That deliverable is missing.
- Fix for the export:
  - Add a `[skill_net]` section and file to `interface.toml`.
  - Branch the reload on it: run the skill-net ONNX with onnxruntime and the reference evaluator on golden `(obs, slot, z)` rows. The scripted sha stays as provenance only.
  - A slot-to-code check is needed, since the flown index equals z.
  - Keep `SCHEMAS` entries for old files.
- Fix for the reader: add `scripts/ste_ls1_read.py`, with the reading rule and per-cell numbers, to the file table.
- ONNX check: a net with the normaliser in the graph, `F.one_hot(slot, 5)` and `F.one_hot(z, 6)` from int64 inputs, opset 17, dynamic batch, exports and loads. The check ran onnxruntime and `onnx.reference.ReferenceEvaluator`, max difference 1.3e-07 and 1.2e-07. So "obs [B,71], slot [B] int64, z [B] int64 -> command [B,4]" is exportable. This was a test net of my own, not the plan's `SkillNet`.

**6. MAJOR: the budget section name and mechanics (Q1). The minimal change list is in the Q1 answer below.** The two points that change the plan:
- "No cap" (R39) is not reached by writing 200.0. Per-task caps still bind a launch, and the section's task caps must be exact keys. Every new job group needs a `TASK_IDS` code edit, a toml edit and a test edit in a merge.
- `ste_job.py status` and `carry` act on `budget_in_work()` only. In the real file that is `budget_l1_l2`, as my scratch run printed. So R39's "every status shows the route's hours so far" is not met without a change to `budget.budget_summary` (`budget.py:223-229`) and `ste_job.py:174`.

**7. MAJOR: the task cap of LS1.4 must cover the post-run clips.**
- Code: `post_run.py:23-25` asks 0.1 GPU-h per clips job, against the run's own task. The hook is on by default for `ste_exploit_l012.py` runs of record (`post_run.drives_training`, lines 83-95).
- Consequences:
  - The six runs of record add 0.6 GPU-h, so a cap of exactly 2.9 would leave the last clips "pending".
  - The pipeline record's actual extras were +0.016 to +0.043 per run.
  - Propose a cap of at least 3.5.

**8. MAJOR: M1 cannot stand alone.**
- The noise-floor script (LS1.5, in M1) plays "the gate read's cells". Those cells (choices, mixed combinations, `Composite`, `fixed_team`) are only in Task 5 (M2).
- The existing code is Strike-only: `SIDE = "strike"` (`ste_l3_run0_ceiling.py:69`), `Composite` (232-245, `self.team = SIDE`), `choices()` (99-115, `strikes(gates)`), `fixed_team` (123-128) and `ConstHeads`. The "mixed cells" pattern is not reusable for Guard as it stands.
- Fix: factor a team-parametrised cell module into M1, or move the noise-floor to M2.
- Plan Task 4's test "limits equal the table of section 4" contradicts R38 (the owner sets the limits after LS1.5).
- Note also: the existing tests prove `fixed-choice == T44 cell` on the CPU (`tests/test_ste_l3_two_level.py:311-338`). The Composite hold-1 oracle (`oracle_check`, ceiling:248-288) covers mixed cells for Strike only.

**9. MAJOR: the equivalence read's CPU claim is correct for the positive control only.**
- `exploit.py:57` EXACT and `replay_ok` (803-804): bit-exact equality with T44 is a CPU rule. On CUDA only count tolerances apply.
- The net-versus-script cells compare two arms. They can run on the same device, CPU or GPU, and need no T44. The workflow's fallback (result cells to the GPU) is sound.
- `Reference.cells` is keyed `(variant, guard, strike)` for script against script only (`exploit.py:398-415`). T44 therefore backs only the 30 single-code cells per side. The mixed cells (120 Guard, 100 Strike) have no T44 reference. They need a scripted `Composite`-style arm played on the same starts, at `hold_ticks=1` (`oracle_check` does the same, ceiling:284-285; `HeldPlayer` with hold 12 would freeze a non-choice player's command, `exploit.py:545-559`).
- Timing estimate (computed, not measured on this job):
  - Existing CPU measures: the L4.1 held-arm folder ran 543 s for 60 hold-1 cells plus 60 arm cells, alongside L4.2 started in the same second. That is about 4.5 s per 1,000-game cell-play. The L3.5 ceiling ran 66 cells in 133 s, about 2 s each.
  - Measured now on 16 threads, 3x256 MLP (82 inputs, 4 outputs): 2.1 to 2.3 ms per tick per cell of 3,000 rows. At 2,400 ticks that is about 5 s per cell-play.
  - 280 net cells at about 5 s MLP plus 2 to 4.5 s game = roughly 2,000 to 2,700 s. The scripted arm for 220 mixed cells is about 440 to 1,000 s. The 60-cell replay control is 120 to 270 s.
  - Total: roughly 50 to 75 minutes on an idle machine, about double if a GPU job, the test suite or another session is also using the CPU. The estimate carries a wide error bar.
- `NetTwoLevelDispatch.act` must run under `torch.no_grad()` or with `requires_grad_(False)`. `SkillTeam.command` (`exploit.py:629-631`) is not under `no_grad`, and `play_match` has no `no_grad` (`core/play.py:58-88`). Training calls `env.step` inside `no_grad` (`exploit_train.py:309`). Scripts have no parameters, so today nothing builds a graph.

**10. MINOR: second seeds (Q3) and export.**
- A second seed is a second `[variants]` entry with its own `train_seed` pair and `reference_variant = "base"` (`exploit.py:100-108`, `271-274`, used by `evaluate_controls`, `preflight`, `eval_cells`).
- It must also pass: `verdict.order` lists every variant once (`exploit.py:222`), seeds distinct from `run0`, `curve`, `clip` and `pool` seeds (216-218, 243-245), and the maximin g*/s* check.
- With `[run0] per_variant` unset, one run 0 serves both Strike seeds, provided it uses the same cap.
- `follow_up_seeds` is a required `[verdict]` key (`exploit.py:80`) and nothing in `source/` or `scripts/` reads it (grep).
- `export.py` hard-codes `"base"`: `_dispatch` (98), `golden_observations` (86), `_interface` (seed line and game entry). A second-seed export would record the wrong seed in `interface.toml`, or fail with a missing `"base"`. The `ste_l6_export.py:49` call uses `"base"` too.

**11. MINOR: plan interface details.**
- Plan Task 2 test uses `gates.learner_table`, which does not exist. `ExploitGates` has a `learner` field (a `LearnerSpec`), and `learner_table(spec)` is a function in `skills.py:315`. Helpers used in the plan's tests (`META_STRIKE`, `GOOD`, `IDX`, `live_obs`, `TWO_LEVEL_TABLE`, `relabel_one_script`, `collect_again`) are not defined anywhere.
- `learner_spec` ends with `LearnerSpec(spec.action, ..., mask)` (`skills.py:105`). It rebuilds the object from named fields, so new fields `skill_source` and `skill_net` would be dropped unless passed there too.
- `TWO_LEVEL_KEYS` (`skills.py:47`) is a required list (`:189`) and is also what the velocity route refuses (`:92`). Put the new keys only in the allowed set (`:80`) and refuse them explicitly outside two-level.
- The plan has a single `skill_net: str`. The workflow's per-team table wins, so the plan is stale there.
- The factory signature (`skills.py:299`) has no team size and no hash input. Carry both through `LearnerSpec` and check team size at the first `act` (the plan already does this through `obs.shape[1]`).
- Net file paths are resolved from ROOT. `ste_l5_clips3d.py` and `ste_l6_export.py` read `gates.toml` from the run folder, and a path under `runs/` would not exist in another worktree. Pin the net sha256 in the gate file and keep the file somewhere stable.
- Plan Task 4 lists `budget.check_launch` as consumed. Drivers do not call it; the launcher does (`jobs.py:210`). The driver reads only `cap_gpu_h` (`ste_exploit_l012.py:1307`).
- `RunGuard(run_dir, cap_s, dump, load)` and `atomic.write_text/temporary_path/commit` exist as the plan assumes. `atomic` has no bytes writer, but `temporary_path` plus `commit` suffice for `torch.save`.

**12. MINOR: weak comparison for Strike.** The record shows route 2's Strike run read "INCONCLUSIVE: the exploiter did not learn" (176 against untrained 192). "Level with route 2" is nearly vacuous on Strike. State what a Strike read can show.

## Q1: minimal correct change list for `ste_job.py launch --task LS1.1`
- Verified in a scratch copy with `TASK_IDS["LS1"]` patched in memory: the loader accepts the section, `budget_of("LS1.1")` is it, `check_launch("LS1.1", 0.4)` returns Usage (cap 0.8, phase cap 200.0), `track.phase` stays "L1" and `budget_in_work()` stays `budget_l1_l2`.
- Code, `source/svg_training/ste/config.py:37-48`: add `"LS1": ("LS1.0", "LS1.1", "LS1.2", "LS1.3", "LS1.4", "LS1.5", "LS1.6")` and update the comment. Nothing else in `config.py`, `budget.py` or `jobs.py` needs a change (`phase_of` is a whole-ID lookup, `config.py:127`).
- `configs/ste_learning.toml`:
  - Section `[budget_ls1]` with `phases = ["LS1"]`, `closed = false`, `phase_cap_gpu_h = 200.0`, and `[budget_ls1.task_cap_gpu_h]` with all seven quoted keys as floats (`"LS1.0" = 0.0`).
  - Place it after `budget_l3_l4_l5_l6` so `later_budgets[0]` and `[1]` keep their indices.
  - Section name must be exactly `budget_ls1`. `[budget_ls_1]` is refused with "the section's name must spell its phases ['LS1']: expected [budget_ls1]" (`config.py:220-222`).
  - A missing key, even a CPU task such as `LS1.3`, is refused: "missing task ID(s) in [budget_ls1.task_cap_gpu_h]" (`config.py:193`, `_exact`).
  - Every value line needs a status label and source (`FIXED|MEASURED|PROPOSED|OPEN` followed by `(` or `:`, `tests/test_ste_config.py:476-512`). The 200.0 is PROPOSED until the owner confirms R39.
  - Task caps must add up to no more than the phase cap, in decimal. Suggested: LS1.1 0.8 and LS1.6 0.1 inside R36's 1.0, plus LS1.4 at least 3.5 (finding 7). Do not write the text `phase = "L1"` in a new comment: `test_ste_config.py:360,380` replace that exact string and `GOOD.count` must stay 1.
- `tests/test_ste_config.py`:
  - Line 90: the expected section set gains `"budget_ls1"`.
  - Line 107: `cfg.budgets() == (cfg.budget, later, cfg.later_budgets[1])` fails with a fourth section; add `cfg.later_budgets[2]`.
  - Add a test like the L3-L6 test at lines 588-600, plus constants.
  - `test_task_ids_and_caps_are_those_of_plan_section_4`, `test_the_l1_and_l2_cap_is_the_one_in_plan_section_9` and the `phase_of` checks are unaffected.
- `ste_learning/PLAN.md` §9: add a row. The only pinned row is `| **L1 + L2** | **<number> GPU-h**` (`test_ste_config.py:248-254`). The L3-L6 row is not test-pinned, so this is documentation only.
- Things that do not get in the way: `closed = false` is not an obstacle, and `track.phase = "L1"` plus `budget_in_work()` do not matter because `check_launch` uses `cfg.budget_of(task)` (`budget.py:252`). Nothing sums across sections or assumes exactly three (`budgets()`, `budget_of` and `_exact` are generic).
- `ste_job.py status` and `carry` ignore route 3 (finding 6).
- Naming choice: with phase key "LS1" a later LS2 task forces `phases = ["LS1", "LS2"]` and a section rename to `budget_ls1_ls2`. The ledger groups are task IDs, so a rename is safe. If R39 means "all stages", consider one phase key "LS" (section `budget_ls`) holding IDs like "LS1.4"; `phase_of` only looks the ID up.

## Q2: call sites of `two_level_dispatch`
Count verified: 12 calls in 9 files, plus one direct `TwoLevelDispatch(...)` at `ste/export.py:302`. Two further items the workflow does not name: the definition `skills.py:299`, and a direct slice-1 `SkillDispatch(...)` at `exploit_train.py:170` (choice team/drone; `learner_spec` should refuse `skill_source = "net"` there). The spec (`gates.learner`) reaches the factory at all 12, and the team is always an argument.

| # | Site | Under `skill_source = "net"` |
|---|---|---|
| 1 | `export.py:98` (`_dispatch`) | works: golden commands come from the net. The reload at :302 does not (finding 5) |
| 2 | `exploit_train.py:168` (`decision_env`) | the training env gets the net dispatch; `DecisionEnv._skill_commands` calls `act` (`:158`) inside `no_grad` |
| 3 | `ste_exploit_l012.py:802` (`make_videos`) | device "cpu"; net loaded on CPU; the reload through `skill_team_from_modules` works only with the meta rule of finding 2 |
| 4 | `ste_exploit_l012.py:1183` (pilot `untrained`) | works, but the twin control fails (finding 1) |
| 5 | `ste_tier2_l013.py:382` (`team_from`) | works; num_games 1, any device; not used in LS1 |
| 6 | `ste_l4_suite.py:70` | works, but the suite's script-twin check would FAIL (not an LS1 job) |
| 7 | `ste_l3_run0_ceiling.py:126` (`fixed_team`) | would build a net team; its mark (604) and oracle check are the script ceiling, so the mark is not re-derived under net; Strike-only (`SIDE`) |
| 8 | `ste_l6_export.py:49` (`team_outputs`) | works for logits only |
| 9 | `ste_l5_clips3d.py:338` (`build_team`) | works; see Q5 |
| 10-12 | `ste_l3_isaac_smoke.py:273, 385, 403` | work on any device; they use `env.skills._team_map` and `_drone_map` (373), which the subclass keeps; not an LS1 job |

- Silent use of scripts: none passes the factory without the spec. The only direct construction that ignores the spec is `export.py:302`, which does not fail silently: the reload check raises.
- `scripts/ste_score_matrix.py:215`, `ste_tier2_score_l18.py:189,312`, `ste_cross_tag_l012d.py:205` and `ste_vid1_capture.py:96` call `require_velocity_learner` and refuse any skills gate file. So the scoring matrix is not available for route 3.
- Nothing in these sites reads `dispatch.players` or `names` except `HeldPlayer._log_choice` (`exploit.py:592`, `dispatch.k`), which the subclass inherits as long as its constructor still builds the K scripts. Keeping the parent's constructor is wasteful, but it keeps `k` and `names` valid.

## Q3: what else the driver assumes
- Besides findings 1 and 3: `learner_control.json` is written by `run_run0` with `**learner_block(gates)` at the end. `trained_against`, the "best script" comparisons (`results_of`: the trained team against the best scripted team of the same side), and `results.json` / `eval_info.npz` stay valid because they concern the opponents and the script baselines, not the learner's own dispatch.
- Nothing in `results.json` records the net's identity unless `learner_table` does. Add it.
- The run 0 mark 0.554 (`skills_gates.toml`) is the script team's ceiling (604 less 50, `records/...pipeline_record.md`). Reusing it for the net is a pre-registered choice. Label it so.
- Pilot: one pilot covers both sides (it loops `exploit.SIDES`).
- Run 0: one under the net gate file covers both Strike seeds if both seeds are variants of that file and its cap equals the runs' cap. Each new gate file, and a route-2 second-seed file, needs its own run 0 (finding 4).
- Pins: pilot by `[learner]` table plus recipe; run 0 by gate hash, table, PASS and cap; seed by `variants.<name>.train_seed.{strike,guard}`.
- The workflow's job order is consistent with this, apart from the omissions above.

## Q5: clips
- (a) Confirmed. `load_run` (`ste_l5_clips3d.py:108-137`) needs `results.json` complete, `agent_final.pt`, `eval_info.npz`, `gates.toml` and `gates.sha256` in a run folder, and refuses a run 0 (`run.json` run0). A skill network on a fixed choice has no such folder.
- (b) Confirmed in the code paths read. The hook is on by default for `ste_exploit_l012.py` runs of record (`post_run.drives_training`). `build_team` (`:322-342`) goes through `two_level_dispatch`, so a net gate file builds the net-backed team.
  - Risk: `capture` requires the replay of the INFO batch to equal the record game for game. Net GEMM results can differ with batch shape, so a clip pick could fail the equality check (exit 1 "MISMATCH"). Not verified. Unlike scripts, which are element-wise, the heads already use GEMM in today's runs and replay fine.
- Smallest change for LS1.6, "the copy beside the scripts on the same start": a small new script that calls `viz/replay3d.capture_trained` twice on the same cell list and game indices, once with the net `SkillTeam` and once with the script cell by name (a fixed-choice cell needs no `players`), then feeds the existing render stage. For mixed combinations, add a `players` pass-through to `capture_trained` (`replay3d.py:198-211` calls `_team_split` without `players`).
- The equivalence read must save per-game arrays (like `eval_info.npz`) so the games can be picked. The plan's `results.json` has only per-cell counts.

## Q7 extras
- File names: no clashes. `skill_net.py`, `distil.py`, `scripts/ste_ls1_*`, `configs/ste_ls1/` and `tests/test_ste_ls1_*` do not exist (the existing `scripts/make_ste_learned_skills_deck.py` is unrelated).
- "Off means identical" would be proven by: `tests/test_ste_l3_skills.py` (spec load, pinned gate files load as before), `test_ste_l3_two_level.py:311-338` (bit-for-bit replay), `test_ste_l3_pipeline_gates.py` (four committed gate files), `test_ste_l3_export.py` and `test_ste_l6_export.py` (reloads), `test_ste_l3_run0.py`, `test_ste_l3_pool.py` and `test_ste_l3_driver.py` (via `learner_table`). Add a literal-key test for `skills_meta` and `learner_table`; the self-comparing tests do not catch an added key.
- A new load test for `heads_gates.toml` must name `[variants]` and `[verdict] order` among the keys that differ from `skills_gates.toml`, as well as `[learner]`, `[run] task` and `[run0]`.

## CHECKED AND CORRECT
- The 12 calls in 9 files plus the direct construction at `export.py:302` (list above).
- Cell counts: Guard 5x6 fixed + 20x6 mixed = 150, Strike 6x5 + 20x5 = 130. Mixed combinations exist in numbers: Guard has 3 drone skills over 3 drones (27 combinations, 20 drawn), Strike 4 over 3 (64).
- `exploit.py:57`: EXACT is "equal game for game in a CPU replay of T44".
- `ste_l5_clips3d.py` cannot draw an LS1 skill network without a training run folder.
- The scripts are stateless and per-slot (cited by the workflow; I read `skills.py:129-162` and `ste_l3_run0_ceiling.py:232-245`, not `scripted.py`).
- `exploit_train.py:455` is the skills-meta refusal the plan names. `RunGuard`, `atomic` and `_mlp` (`opponents/learned.py:36`) exist.
- ONNX opset 17 export of a normaliser plus one-hot net (test net).
- The launcher ledger group is the task ID, so a section rename does not lose hours.
- GPU rate: `skills_gates` pilots at ~890k game-steps/s (Strike) and the net adds an estimated few percent (computed).

## NOT CHECKED (grep line only or not read)
`scripted.py` bodies, `pool.py`, `scoring.py` bodies (grep only for names), `ste_learning/PLAN.md` §6, `ARCHITECTURE.md`, `L3_L6_PIPELINE_SPEC.md`, `ste_l6_read.py` bodies (only its constants and the `read_export` head), `ste_l5_clips3d.py` lines 180-299 and 380-779, the rest of `post_run.py`, `replay3d.py` beyond `capture_trained`, `ste_l3_held_arm.py` beyond the cell builders, the GPU rate of a net-backed run (no GPU job started), whether a distilled net can pass the CUDA tolerance of the twin control (that is exactly what job LS1.5 would show), and the full test suite (I did not run tests; the `test_ste_config.py` line numbers above come from reading, and the loader behaviour from the scratch run).
