INTERNAL · the builder's task plan for route 3 stage LS1 and job group LS1.4 (merges M1 to M4), rewritten from workflow v3 and the two design-review reports and checked against the code at `d70b4e01`; DRAFT for the lead and one reviewer, nothing built or run · [README.md](README.md); the source of truth: [LS_EXECUTION_WORKFLOW.md](LS_EXECUTION_WORKFLOW.md) v3, [LS_DESIGN_REVIEW_A.md](LS_DESIGN_REVIEW_A.md), [LS_DESIGN_REVIEW_B.md](LS_DESIGN_REVIEW_B.md)

# LS1 task plan: route 3, merges M1 to M4 (25 Nov 2026)

Written by the architect (Opus 5.5) from workflow v3 (sections 3 to 6 and 9), both review reports, the owner's rulings
R38 to R45 and four read-only scout reports, every load-bearing claim re-checked in the code (section 10 says which).
Where this file and workflow v3 differ on the *what*, the workflow wins; where they differ on the *code*, this file
wins (section 9 lists every such place). [LEARNED_SKILLS_BRIDGE_PLAN.md](LEARNED_SKILLS_BRIDGE_PLAN.md) is used for
proposed sizes only. Paths are relative to `svg_training/`; `ste/` is `source/svg_training/ste/`. Line numbers are those
at `d70b4e01`; re-check with `grep -n` before editing. Task IDs: `LS1-M<merge>-T<n>`. Values that are not the owner's
are labelled PROPOSED with their source; the limits and margins are the owner's (R38) and appear nowhere as numbers a
test types. **Review round 1 applied (25 Nov 2026):** each change names its finding (C1 to C9, B-1 to B-11, F1 to F9,
CA-1 to CA-7); code re-checked as section 10 says.

Each task gives: **Files**; **Consumes** (real names, file:line); **Produces** (signatures, shapes, dtypes, keys);
**Tests first** (name, assertion, fixtures, helpers to write); **Implementation**; **Keep green**; **Commit**.
One commit per task, tests first, on the merge's branch in its own worktree cut from `development`.

## 0. Global constraints

1. **Write only inside `svg_training/`.** `source/svg_training/opponents/scripted.py` is never edited (sha256 today
   `b7ccafde…bad3a`; it is pinned in every skill network and every skills export). Changed scripts live in their own
   file (M1-T6).
2. **Off means identical.** Every new setting defaults to today's behaviour bit for bit. These load and behave as
   today, each pinned by a named test: every committed gate file (the 13 under `configs/` that
   `exploit.load_gates` loads at `d70b4e01`, and the 11 read by other loaders, which no task here touches); the six pipeline-check
   checkpoints and four L6.2 exports (whole-dict meta checks at `ste/exploit_train.py:411, 455`,
   `ste/export.py:263-268, 304-306`); every `pilot.json` and `learner_control.json` (`learner_table`,
   `scripts/ste_exploit_l012.py:236-248`, `ste/exploit.py:961`); `configs/ste_learning.toml`'s existing sections and
   the `ste_job.py status` first lines. The committed evidence copies are the "saved before the change" fixtures:
   `records/evidence/2026-11-25_ste_l3_l6_pipeline/l3_run0_skills_learner_control.json` and
   `records/evidence/2026-11-25_ste_l3_l6_pipeline/exports/skills_{guard,strike}_interface.toml`.
3. **Batched.** No per-game or per-drone Python loop in anything that runs during training, data collection or
   scoring (STANDARDS §6.1). Allowed loops: the tick loop, the K skills (stacked once, as `SkillDispatch.commands`,
   `ste/skills.py:153-155`), cells and arms of a read, epochs and minibatches of a fit, rounds.
4. **Literal scan.** In `ste/` a numeric literal other than 0, 1, −1, 2 only as a module-level UPPER_CASE constant,
   default arguments included (`tests/test_ste_literals.py`); every tuned number comes from a gate file.
5. **Gates before runs (R38).** Limits, margins and control sizes are REQUIRED keys of the gate files with no code
   default. Until the owner sets them they hold a string starting `FILL_` (the `exploit.FILL_MARK` convention,
   `ste/exploit.py:98, 292-295`); a run of record refuses an unfilled file (exit 2). **Tests and limits (one rule, review
   round 1: C5, B-10, F6):** a test that checks a committed file reads its values from that file; a test of the verdict
   arithmetic (`limit_failures`, `verdict`, the LS1.4 rule) **always** writes its own synthetic gate file under
   `tmp_path` from a dict named `STAND_IN` and passes the values in as arguments; it never switches source on whether the
   committed file is filled. `STAND_IN` values are synthetic and are none of the PROPOSED starting points (0.05,
   0.005, 0.03, 0.04, 0.08); `test_stand_in_mirrors_no_limit` (M2-T5, M4-T5) fails if a `STAND_IN` value equals a
   PROPOSED starting point or a filled numeric value of the committed `[limits]`, `[controls]` or `[reading]`.
   **Under `--smoke` with `FILL_` values (F1):** the limit-dependent steps (`limit_failures`, controls C6 and C7, the
   verdict) are not run and are written `NOT_RUN`; a `FILL_` string never reaches an arithmetic comparison, and a smoke
   never writes DISTILLED or NOT DISTILLED (M2-T5, M2-T6). No typed fallback in code or script (R38).
6. **Wording:** Guard team, Strike team, tag, reach the zone; "observed in the training simulator". Never write the
   home directory's user name in a file (write `~/...`); results write repository-relative paths.
7. **Git:** explicit paths; never `git add -A`, `commit -a`, `stash`, `reset`, `checkout` of another branch, `clean`,
   `push`. **Tests (B-2), always with this command and environment, from `svg_training/`:**
   `mkdir -p runs; unset PYTHONPATH; CUDA_VISIBLE_DEVICES="" PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python -m pytest -q -p no:cacheprovider <files>`
   (`svg_training/CLAUDE.md`, Environment: CUDA hidden and the ROS `PYTHONPATH` unset, which the CPU-only equality
   tests and constraint 8's batch-shape numerics assume). The builder runs each task's new test files and its "Keep
   green" list with it; the lead runs the full suite once per merge with the same command and no file list, in the
   background, and nothing is merged while it runs (workflow §4). No GPU job during the build.
8. **CPU numerics (scout measurement, 16 threads, not re-run by the architect):** a 3 x 256 ELU MLP gives results that
   depend on the batch size (rows run in a batch of 1 or 7 differ from the same rows in a batch of 18,000 by about
   1e-7; 3,000, 6,000, 12,000 and a permuted batch were equal). Every "game for game" comparison of two net-flown
   arms therefore plays both at the same batch shape; one-code and all-codes outputs are compared with `allclose`,
   not `equal`.

## 1. Shared contracts (the names every merge uses)

Later merges cite these; a builder never re-derives them.

**C1. Phase key and budget section.** `TASK_IDS["LS1"] = ("LS1.0", …, "LS1.6")` and `[budget_ls1]`, as workflow v3
section 3 names them. Open point OP-1 offers `"LS"` / `[budget_ls]`. **M1-T1 does not start until the lead has
settled OP-1** (B-9); if (b) is picked, every `"LS1"` key, `budget_ls1` string, `later_budgets[2]` section name and
test name in M1-T1, M1-T2, M4-T4 and section 6 becomes `"LS"` / `budget_ls` before the builder starts (the task IDs
stay `LS1.x`).

**C2. The skill network** (`ste/skill_net.py`, M1-T3). `SkillNet(team: str, skills: list[str], team_size: int,
slot_width: int, hidden: list[int], zeroed_inputs: list[int])`; attributes `team`, `skills` (tuple), `k`
(= `len(skills)`), `team_size`, `slot_width`, `hidden`, `zeroed_inputs`; buffers `in_mean [71]`, `in_std [71]`,
`keep [71]` (float32). `forward(obs [B, 71] f32, slot [B] i64, z [B] i64, clip: bool = True) -> [B, 4] f32`:
`x = (obs - in_mean) / in_std * keep`; `h = cat(x, one_hot(slot, slot_width), one_hot(z, k))` (float);
Linear+ELU per hidden size, `Linear(-> 4)`; `clamp(-1, 1)` when `clip`; **times `obs[:, 12:13]`**. The alive rule is
inside `forward`, the same rule as `_pack` (`opponents/scripted.py:32-35`, multiply by the flag), so it is in the
ONNX graph too and every path (one code, all codes, export, reload) gets it once. Any stand-in flown in its place
(M1-T5 `ScriptOracle`, M2-T5 `PermutedNet`) has the same signature, attributes and alive rule.

**C3. The skill-network file.** `torch.save` payload of plain types and tensors (loads with `weights_only=True`):
`format = "ste-ls1-skill-net-1"`, `team`, `skills` (ordered = the gate file's `[players]` list of the team),
`team_size`, `guards`, `strikes` (the game's team sizes, for golden observations), `slot_width`, `obs_dim = 71`,
`interface_version = "0.1"`, `hidden`, `zeroed_inputs`, `std_floor`, `scripted_sha256`, `game_file`
(repository-relative), `game_sha256`, `game_constants` (C2's `game_constants(cfg)`), `provenance` (dict: M2 writes
`distil_gates_file`, `distil_gates_sha256`, `rounds`, `seed`, `git_commit`), `state_dict`.

**C4. The gate-file syntax** (`ste/skills.py`, M1-T4):

```toml
[learner]
skill_source = "net"                       # default "scripts" when absent
[learner.skill_net]
strike = { file = "ste_provisional/skill_nets/<folder>/skill_net_strike.pt", sha256 = "<64 hex or FILL_...>" }
guard  = { file = "ste_provisional/skill_nets/<folder>/skill_net_guard.pt",  sha256 = "<64 hex or FILL_...>" }
```

Both sides required (OP-35). A relative file resolves from the `svg_training/` root, an absolute one as is (tests
under `tmp_path`). A `FILL_` sha loads (template, M4) and is refused when a dispatch is built.

**C5. Where a net is checked.** `two_level_dispatch` checks file sha256, format, team, skills (names and order),
scripts sha256 and the game constants against the `cfg` it is given; team size at the first `act`/`commands`. The
game-file sha256 is checked by `skill_net.net_problems(...)` in each driver's preflight (M2-T6, M3-T4, M4-T2, M4-T3)
against the game file the run plays. OP-2 has the alternative.

**C6. The cells** (`ste/cells.py`, M1-T5). Code index z = index in the team's `[players]` list. Fixed-choice cell k
= every drone flies code k (team strategy t: heads `(t, 0)`; drone skill d: heads `(FREE, d)`). Mixed cells: explicit
per-side combinations from `configs/ste_ls1/cells.toml` (20 per side, free combinations with at least two distinct
drone skills). Every read plays `hold_ticks = 1` (a held Composite or changed script would freeze its command,
`ste/exploit.py:571-578`; a constant-heads `SkillTeam` is the same at any hold). Seed = `int(ref.meta["seed"])`
(110000) on T44's starts. Cell player names carry a prefix (`net:`, `scr:`, `orc:`, `unf:`, `perm:`, `cal:`) so they
never shadow a script name (`ste/exploit.py:691-692`), and each recording or stateful player is one object per cell.

**C7. The paired statistics** (`ste/cells.py`, M1-T7, used by the calibration and the gate alike, so the owner's
limits are set on the gate's own ruler): per cell `b` (games the arm lost that the reference won), `c` (the
reverse), `flips = b + c`, `n`, `diff = (c - b) / n` with an interval, `sign_test_p`; the pooled difference (mean of
per-start means over cells, `ste/scoring.py:316-348` style); end-step differences. b, c and n are always stored, so
the interval method (OP-11) can be changed after the calibration without replaying a game.

**C8. Seeds (PROPOSED, a fresh block; used today: 110000 to 140950; a grep of `configs/` and `ste_provisional/` finds none in
140210-140299 or 15xxxx).**
Calibration noise 150101+; distillation `[data] seed` 150001, `pool_seed` 150002, `[fit] seed` 150003, `[report]
seed` 150004, `[clips] seed` 150005; LS1.4 140211/140212 (second training seed pair, both arms), 140213 (the second seed's run 0,
both arms: route 2's `skills_seed2` run 0 and, only under OP-29 B, route 3's `base_s2` run 0, so the arms stay paired). New `configs/ste_*/*.toml` are scanned by
`tests/test_ste_l19_l110.py:186-198` and `tests/test_ste_l1side.py:369-380`.

**C9. Net files of record** live under `ste_provisional/skill_nets/<date>_ls1_<side>/` (committed, about 0.6 MB per
3 x 256 net; `runs/` is git-ignored, `.gitignore:1`), added to `ste_provisional/SHA256SUMS` (OP-7).

**PROPOSED sizes** (not the owner's; each lives in a gate file):

| Value | PROPOSED | Source |
|---|---|---|
| hidden | [256, 256, 256] | bridge plan :107, :336 |
| rounds, script-flown share | 4 rounds, [1.0, 0.5, 0.25, 0.0] | bridge plan :117 |
| games, ticks per round | 4,096 games, 600 ticks | workflow §5 row LS1.1-G |
| keep_rows, epochs, lr, batch | 2,000,000; 40; 1e-3; 8,192 | bridge plan :336 |
| data mix | uniform (one code all game) ≥ 0.5, rest fixed mixes and random redraw | workflow §3 `distil.py` row; review A F1 |
| rows with a mate absent | ≥ 0.20 of kept rows | workflow §3; review A F6 (measured natural share 0.22 Guard, 0.27 Strike, scout probe) |
| switch-jump threshold | 0.2 (max channel, one tick) | scout probe: 1.9 % Guard, 3.6 % Strike rows above it |
| zeroed inputs | 6, 7, 10, 11 | workflow §3 (yaw sin/cos, time left, team flag); OP-5 |
| mixed combinations | 20 per side | workflow §5 |
| read games per cell | 1,000 | workflow §5 |
| smoke | 16 games, 2 rounds; read on 24 starts | workflow §5 row LS1.0 |
| calibration | noise 0.01, 0.02, 0.05, 0.1; bias 0.01, 0.02, 0.05 on xy, and 0.0025, 0.005, 0.01 on the zero-command skill's cells; scale 0.95; turn 3°; sacrifice entry 30° → 40°; converge gather 0.1 → 0.2 rad | workflow §3 calibration row, §5 near miss (0.05 bias); review A F2, F5 |
| limit starting points (the owner sets them) | 0.05 per active channel; 0.005 zero-command skill; 0.03 per cell | workflow §5 |
| LS1.4 margins (the owner sets them) | Δ 0.04 pooled, 0.08 per cell | workflow §6; review A F3 |

## 2. Merge M1: the skill network, the setting, the budget, the cells, the calibration

Lets run: the calibration read LS1.5. Stands alone on today's `development`.

### LS1-M1-T1 The route's budget section and task IDs

- **Files:** `ste/config.py`; `configs/ste_learning.toml`; `tests/test_ste_config.py`; `tests/test_ste_budget.py`;
  `ste_learning/PLAN.md` §9.
- **Consumes:** `TASK_IDS` (`ste/config.py:37-48`); `_budget` (`:181-201`, task caps must be exactly the phase's IDs,
  through `_table` at `:193`, which calls `_exact` (`:172`); decimal sum ≤ phase cap); `_later_phases` (`:204-223`, section name must spell the phases,
  `:220-222`); `SteLearningCfg.budget_of` (`:107-113`), `budget_in_work` (`:103-105`); `phase_of` (`:127-132`);
  `budget.check_launch` (`ste/budget.py:232-271`, uses `cfg.budget_of(task)` at `:252`).
- **Produces:** `TASK_IDS["LS1"] = ("LS1.0", "LS1.1", "LS1.2", "LS1.3", "LS1.4", "LS1.5", "LS1.6")` after `"L6"`; the
  `[budget_ls1]` section of section 6 appended after `[budget_l3_l4_l5_l6]` (so `later_budgets[0]` and `[1]` keep their
  indices; the new one is `later_budgets[2]`); a PLAN §9 row `| **Route 3 (learned skills)** | **200 GPU-h** |
  **FIXED: owner, R39 as read by the lead, confirmed R43, 25 Nov 2026** …|` after the L3–L6 row.
- **Tests first** (`tests/test_ste_config.py`): constants `LS1_CAP_GPU_H = 200.0` and `LS1_TASK_CAP_GPU_H` (this
  file types its caps on purpose, `:25`); `:90` section set gains `"budget_ls1"`; `:107` tuple gains
  `cfg.later_budgets[2]`; **`:514-515` value-line count gains `+ 3 + len(LS1_TASK_CAP_GPU_H)`**;
  `test_the_route_3_budget`: `later_budgets[2] == BudgetCfg(section="budget_ls1", phases=("LS1",), closed=False,
  phase_cap_gpu_h=200.0, task_cap_gpu_h=tuple(LS1_TASK_CAP_GPU_H.items()))`, `TASK_IDS["LS1"] ==
  tuple(LS1_TASK_CAP_GPU_H)`, `task_caps_total_gpu_h() == 4.9` (the number that moves, with `LS1_TASK_CAP_GPU_H`,
  when the owner moves a cap, section 6), `budget_of("LS1.4") is later_budgets[2]`,
  `phase_of("LS1.4") == "LS1"`, `budget_in_work().section == "budget_l1_l2"`; `test_plan_names_the_route_3_cap`:
  PLAN §9 matches `^\| \*\*Route 3[^|]*\*\* \| \*\*(\d+(?:\.\d+)?) GPU-h\*\*` and equals 200.0 (pattern of
  `:248-254`). `tests/test_ste_budget.py::test_the_committed_route_3_caps` (autouse `made_up_machine`, helper `ran`,
  `:23, :41`): `check_launch("LS1.1", 0.8) == Usage(0.8, 0.0, 200.0, 0.0)`; `check_launch("LS1.5", 0.1)` raises
  `BudgetError` matching `task LS1\.5.*cap 0\.0 GPU-h.*budget_ls1\.task_cap_gpu_h`; a row `ran("LS1.1", …)` leaves
  the L1+L2 section's `budget_gpu_h` unchanged.
- **Implementation:** the TASK_IDS comment names route 3 and R43. Every value line labelled (`test_ste_config.py:504`).
  The labels name their source: 200 and 4.0 the owner's R43 row (`DISCUSSION_2026-11-19_20.md:758`, workflow v3 §1
  R43 row); 0.8 and 0.1 workflow v3 §3 (`LS_EXECUTION_WORKFLOW.md:89`), which says R43 writes them while the two R43
  rows do not. All four are labelled FIXED (owner, R43), 0.8 and 0.1 "as workflow v3 §3 records it" (F5; workflow v3
  is the source of truth on the what); OP-40 says when the lead would revert them.
  New comments must not repeat strings the test swaps (`changed()` asserts `GOOD.count(old) == 1`, `:60`):
  `phase = "L1"`, `closed = true`, `phases = ["L1", "L2"]`, `phase_cap_gpu_h = 13.0`, `= 19.0`, `"L1.9" = 1.6`,
  `"L0.11" = 0.5`, `"L1.13" =`, `"L0.6" =`, `"L0.4" = 0.2`, `[budget]\n`. Task IDs quoted (unquoted `LS1.0` is a
  table). Nothing in `budget.py` or `jobs.py` changes for launching (scout scratch run: `check_launch("LS1.4", 4.0)`
  accepted, `budget_in_work()` unchanged).
- **Keep green:** `test_ste_config.py`, `test_ste_budget.py`, `test_ste_job.py`, `test_ste_l3_pipeline_gates.py`,
  `test_ste_l012c.py`, `test_ste_tier2_score_l18.py`.
- **Commit:** `svg_training ste config: route 3 budget section and LS1 task IDs (R43)`.

### LS1-M1-T2 `ste_job.py status` shows the route's hours

- **Files:** `ste/budget.py`; `scripts/ste_job.py` (`:174`, docstring `:45-51`); `tests/test_ste_budget.py`;
  `tests/test_ste_job.py`.
- **Consumes:** `budget_summary` (`ste/budget.py:223-229`, pinned string at `tests/test_ste_budget.py:230`);
  `own_gpu_h` (`:173`), `carried_gpu_h` (`:183`); `ste_job.run` status `:174`, carry `:164-173`.
- **Produces:** `section_summary(budget: BudgetCfg) -> str` (today's text format, any section);
  `budget_summaries(settings=SETTINGS_FILE) -> list[str]`: the section in work first, then every section not closed,
  in file order (OP-3). `budget_summary` returns exactly today's string. Status prints one `budget <line>` per entry,
  after today's lines: **existing lines unchanged, lines added** (B-8; under OP-3's recommendation one added line is the
  open `budget_l3_l4_l5_l6` section's, besides the route's). Only if OP-4 is yes: `carry --section <name>` (default the section in work).
- **Tests first:** `budget_summaries(SETTINGS_FILE)[0] == budget_summary(SETTINGS_FILE)`; the list contains
  `"budget_ls1 (phase LS1): used 0.000 of 200.0 GPU-h (own rows 0.000, carried 0.000)"` under `made_up_machine`; a
  settings file without the section gives no route line; `tests/test_ste_job.py`: that string is in `bench.status()`
  (`:69-72`) and `status().splitlines()[0]` is unchanged (`:627`).
- **Implementation:** `section_summary` is the body of `budget_summary` (`ste/budget.py:223-229`) for a given section; `budget_summary`
  calls it on `budget_in_work()`; `budget_summaries` walks `cfg.budgets()` skipping closed sections; `ste_job.py:174`
  prints one line per entry; docstring `:45-51` updated.
- **Keep green:** `test_ste_job.py` (regex/`in` asserts at `:345, :361, :473, :495, :518, :597, :603, :627, :741`),
  `test_ste_budget.py`.
- **Commit:** `svg_training ste budget: status shows every open budget section (R39 as read, R43)`.

### LS1-M1-T3 `ste/skill_net.py`: the network, its two paths, save and load

- **Files:** new `ste/skill_net.py`, `tests/test_ste_ls1_skill_net.py`, test helper `tests/_ste_ls1.py`.
- **Consumes:** `core/observations.py` (`OBS_DIM = 71` `:19`, `INTERFACE_VERSION = "0.1"` `:16`, `ObsView` alive 12,
  slots from 13, 7 wide; an out drone's row is zero but its team flag, `:85-89`); `core/game_config.GameCfg`
  (`pad_guards`, `pad_strikes` `:323-324`, `.rules.keepout_strike_m`, `.rules.keepout_guard_m`,
  `.arena.wall_margin_m`, `.arena.height_band_m`, `.starling.enabled`, `.team_speed_mps(team)` `:400-405`); what the
  scripts read (`scripted.py:158, 190, 319, 358-360, 413, 434`); `ste/atomic.temporary_path` (`:14`), `commit` (`:29`;
  no bytes writer: `torch.save` to the temporary path, then commit); `ste/shared.PACKAGE_DIR` (`:31`; root =
  `PACKAGE_DIR.parents[2]`, as `ste/sweep.py:54`). Not reused: `opponents/learned._mlp` (`:36`, fixed input width,
  imports skrl).
- **Produces:** C2 and C3, plus `COMMAND_DIM = 4`, `FORMAT = "ste-ls1-skill-net-1"`;
  `SkillNet.set_normaliser(mean: Tensor[71], std: Tensor[71], floor: float) -> None` (stores `std.clamp(min=floor)`);
  `one_code(net, obs: [N, M, 71], z: [N, M] long) -> [N, M, 4]` (rows `obs.reshape(N*M, 71)`, slot
  `arange(M).repeat(N)`; `torch.no_grad()`; `ValueError` "team size" when `M != net.team_size`);
  `all_codes(net, obs) -> [N, M, K, 4]` (row `(n*M + m)*K + k`; no_grad; same check); `game_constants(cfg) -> dict`
  (`pad_guards`, `pad_strikes`, `keepout_strike_m`, `keepout_guard_m`, `wall_margin_m`, `height_band_m` list,
  `starling_enabled`, `guard_speed_mps`, `strike_speed_mps`); `scripted_sha256() -> str`;
  `save_skill_net(path, net, meta: dict) -> str` (refuses missing or extra meta keys; atomic; returns the sha256 of
  the written bytes); `read_skill_net_meta(path) -> dict` (no refusals; for the export, M3);
  `load_skill_net(path, *, team, skills, cfg, device, team_size=None, file_sha256=None, game_sha256=None) ->
  tuple[SkillNet, dict]` (`team_size=None` skips that check, which the dispatch then makes at the first call; net in `eval()`, `requires_grad_(False)`; `ValueError` naming field and both values, in
  this order: file sha, format, team, skills, team size, scripts sha, game sha, game constants, obs width/interface);
  `net_problems(path, *, sha256, team, skills, team_size, cfg, game_file=None, game_sha256=None) -> list[str]` (the
  same checks as strings, plus a missing file and a `FILL_` sha; for preflights).
- **Tests first** (`tests/test_ste_ls1_skill_net.py`; fixtures: `exploit.load_gates("configs/ste_l3/skills_gates.toml")`,
  `cfg = exploit.variant_cfg(gates, "base")`, autouse `default_torch_threads` from `tests/_torch_threads.py`):
  1. `test_output_is_clipped_linear`: last layer scaled x100: `forward` in [-1, 1] with some entry exactly ±1;
     `clip=False` exceeds 1.
  2. `test_zeroed_inputs_do_not_change_the_command`: random values at the zeroed indices, `torch.equal` outputs.
  3. `test_normaliser_clamps_a_constant_input`: std with zeros → `in_std.min() == floor`, outputs finite.
  4. `test_a_drone_that_is_out_gets_zero_on_every_path`: rows with alive 0 are exactly 0 in `forward`, `one_code`,
     `all_codes`, for a net with non-zero biases.
  5. `test_one_code_is_the_gathered_all_codes`: shapes; `allclose(one_code, gather(all_codes), rtol=0, atol=TOL)`
     with `TOL = 1e-6` a named test constant (constraint 8).
  6. `test_slot_and_code_change_the_command`.
  7. `test_flying_builds_no_graph`: outputs of `one_code`/`all_codes` have `requires_grad False` with parameters
     requiring grad.
  8. `test_round_trip_and_refusals`: returned sha == `hashlib.sha256(path.read_bytes())`; `torch.load(path,
     weights_only=True)` works; reloaded net `torch.equal`; one `pytest.raises(ValueError, match=...)` per refusal (a
     changed config by `dataclasses.replace(cfg, rules=dataclasses.replace(cfg.rules, keepout_strike_m=...))`); no
     `*.tmp.*` file left; `net_problems` returns one string per fault and `[]` for a good file.
  9. `test_game_constants_are_read_from_the_config`.
  Helpers to write in `tests/_ste_ls1.py`: `team_obs(gates, side, n=64, ticks=40, seed=5)` (the recipe of the private
  `_team_obs`, `tests/test_ste_l3_two_level.py:180-189`); `tiny_net(side, hidden=(16,))`; `save_tiny_net(tmp_path,
  side, cfg)`.
- **Implementation:** input zeroing multiplies after normalising, so stale buffers cannot leak a zeroed input. Slot
  width = the team's pad (`pad_guards` 5 / `pad_strikes` 3; OP-6); team size stored separately. No import from
  `skills`, `exploit` or `export` (import direction: `exploit` imports `skills`, `export` imports `exploit`). Tolerance,
  floor and sizes are arguments (literal scan).
- **Keep green:** `test_ste_literals.py`, `test_dependencies.py`.
- **Commit:** `svg_training ste: the skill network module (route 3 LS1, no caller yet)`.

### LS1-M1-T4 The `skill_source` setting, the net-backed dispatch, the meta rules (`ste/skills.py`)

- **Files:** `ste/skills.py`; `ste/tier2_train.py` (one refusal, OP-8); new `tests/test_ste_ls1_dispatch.py`.
- **Consumes:** `LearnerSpec` (`ste/skills.py:56-70`, frozen); `learner_spec` (`:73-105`: allowed keys `:80`, velocity
  refusals `:89-94`, slice-1 refusals `:98-103`, **positional rebuild `:105` drops new fields**); `TWO_LEVEL_KEYS`
  (`:47`, required at `:189`; do not add to it); `_two_level_spec` (`:187-209`); `TwoLevelDispatch` (`:240-296`);
  `two_level_dispatch` (`:299-303`, 12 calls in 9 files); `skills_meta` (`:306-312`); `learner_table` (`:315-324`);
  `exploit.load_gates` → `learner_spec` (`ste/exploit.py:226-227`); second loader `ste/tier2_train.py:142-144`.
- **Produces:** `LearnerSpec` fields appended after `mask_absent`: `skill_source: str = "scripts"`,
  `skill_net: dict | None = None` (`{side: {"file": str, "sha256": str}}`); constants `SKILL_SOURCES = ("scripts",
  "net")`, `SCRIPTS_SOURCE`, `NET_SOURCE`, `FILL_PREFIX = "FILL_"`. `learner_spec` accepts the C4 keys for
  `choice = "two_level"` only and passes both fields at `:105`. `class NetTwoLevelDispatch(TwoLevelDispatch)`:
  `__init__(team, players, team_strategies, drone_skills, cfg, num_games, device, seed, net, net_sha256: str | None)`
  (calls `super().__init__`, so `names`, `k`, `widths`, `greedy`, `resolve` and the scripts stay; refuses
  `net.team != team` or `tuple(net.skills) != tuple(self.names)`); attributes `skill_source = "net"`, `net`,
  `skill_net_sha256`; `commands(obs) = skill_net.all_codes(self.net, obs)`; `act(obs, choice) =
  skill_net.one_code(self.net, obs, choice.long())`. `two_level_dispatch`: unchanged signature; for `"net"` it resolves
  the side's file (C4), refuses a `FILL_` sha ("not filled yet"), checks the file bytes' sha256, calls
  `load_skill_net(..., team=team, skills=team_skills(players, team), cfg=cfg, device=device)` (team size checked at
  the first call, C5) and returns a `NetTwoLevelDispatch`; for `"scripts"` it returns exactly today's
  `TwoLevelDispatch`. `skills_meta`: today's six keys for scripts; a net adds `"skill_source": "net"`,
  `"skill_net_sha256": sha`. `learner_table`: today's dict for scripts; a net adds `"skill_source": "net"`,
  `"skill_net_sha256": {"guard": …, "strike": …}`. `tier2_train.py:142-144` refuses `skill_source = "net"` ("not
  wired").
- **Tests first** (`tests/test_ste_ls1_dispatch.py`):
  1. `test_scripts_route_is_byte_for_byte_as_before`: `learner_table(load_gates(skills_gates).learner)` equals the
     evidence `l3_run0_skills_learner_control.json["learner"]`, and so do the `json.dumps` bytes; `set(skills_meta(d))`
     equals the literal six keys; the meta equals one built from the evidence exports' `[skills]` plus team and
     `"two_level"`; an explicit `skill_source = "scripts"` gives an equal spec and table and `type(d) is
     skills.TwoLevelDispatch`.
  2. `test_new_keys_are_refused_where_they_do_not_belong`: velocity with either key; choice team or drone with
     `"net"`; an unknown source; `"net"` without `skill_net`; `skill_net` with `"scripts"`; one side missing or extra;
     an entry key other than file/sha256; a sha neither 64 hex nor `FILL_…`.
  3. `test_learner_spec_keeps_the_new_fields`: through `exploit.load_gates` of a `tmp_path` copy of `skills_gates.toml`
     with the keys inserted after `mask_absent = true`.
  4. `test_net_dispatch_from_the_factory` (tiny net saved under `tmp_path`, absolute path): type, `act == one_code`,
     `commands == all_codes`, out drones zero on both, `act` with M = 2 raises "team size"; a wrong sha, a Guard net
     under the strike key, a changed `cfg`, a `FILL_` sha each refused.
  5. `test_meta_and_table_differ_only_for_a_net`: `skills_meta(net) == {**scripts_meta, "skill_source": "net",
     "skill_net_sha256": sha}`, likewise `learner_table`; `exploit_train.skill_team_from_modules`
     (`ste/exploit_train.py:448-473`, check `:455`) refuses a scripts-saved checkpoint with the net dispatch and the
     reverse (CA-7: the scripts-saved dict is `test_ste_l3_export.tiny_learner("skills", side).saved()`,
     `tests/test_ste_l3_export.py:29`, `ste/exploit_train.py:381`; the net-saved one is the same learner built on the
     tiny net dispatch, helper to write `tests/_ste_ls1.tiny_net_learner_saved(gates, side, net_path)`).
  6. `test_fill_prefix_is_the_gate_files_mark`: `skills.FILL_PREFIX == exploit.FILL_MARK`.
  7. `test_tier2_loader_refuses_a_net`.
- **Implementation:** `skills.py` imports `skill_net` at the top (C2 imports nothing from `skills`). The factory gets
  no team size: `NetTwoLevelDispatch` checks `obs.shape[1] == net.team_size` inside `one_code`/`all_codes`.
  **Half-wired between merges, and why that is safe (B-8):** from M1, `learner_spec` accepts `skill_source = "net"`,
  so `exploit.load_gates` loads it; only `tier2_train` and the slice-1 modes refuse it. The other `two_level_dispatch`
  callers (`scripts/ste_l3_isaac_smoke.py:273, 385, 403`, `ste_l4_suite.py:70`, `ste_l5_clips3d.py:338`,
  `ste_l6_export.py:49`, `ste_exploit_l012.py:802, 1183`) would take the net path without a check of their own until
  M3 and M4 add theirs. Nothing committed sets `"net"` before M4-T4 (only `tmp_path` test files do), and the M4
  preflights (M4-T2, M4-T3) are the first runtime checks. M4-T1 later requires `[reading]` in a net gate file (review round 1,
  finding C4); test 3 here and every helper that writes a net gate file then gain a `[reading]` block filled
  from `STAND_IN` (M4-T1 edits them).
- **Keep green:** `test_ste_l3_skills.py`, `test_ste_l3_two_level.py`, `test_ste_l3_two_level_learner.py`,
  `test_ste_l3_mask_learners.py` (`:85` compares with `LearnerSpec("skills", "team")`), `test_ste_l3_refuse.py`,
  `test_ste_l3_masking.py`, `test_ste_l3_pipeline_gates.py`, `test_ste_l3_driver.py`, `test_ste_l3_run0.py`,
  `test_ste_l3_pool.py`, `test_ste_l3_export.py`, `test_ste_l6_export.py`, `test_ste_l3_tier2.py`,
  `test_ste_l4_suite.py`, `test_ste_l5_clips3d.py`, `test_ste_l3_run0_ceiling.py`, `test_ste_literals.py`;
  for `tier2_train.py` (B-7) `test_ste_tier2_score_l18.py`, `test_ste_l013.py`, `test_ste_l013_driver.py`,
  `test_ste_l26.py`; for `skills.py` also `test_ste_l3_velocity_golden.py` (the velocity learner unchanged). Rule:
  every test file that names a changed file (`grep -l "tier2_train\|skills" tests/*.py`).
- **Commit:** `svg_training ste skills: skill_source setting and net-backed dispatch (default scripts, unchanged)`.

### LS1-M1-T5 `ste/cells.py`: the cells of the reads, either team

- **Files:** new `ste/cells.py`, `tests/test_ste_ls1_cells.py`. `scripts/ste_l3_run0_ceiling.py` is not changed.
- **Consumes:** `ste_l3_run0_ceiling.py`: `ConstHeads` (`:80-92`), `choices` (`:99-114`, order: team strategies
  `(t, 0)` first, then `itertools.product` over drone skills, slot 0 slowest), `fixed_team` (`:123-128`), `Composite`
  (`:232-245`, Strike only through `SIDE` `:69`); `exploit.SkillTeam` (`ste/exploit.py:601-635`), `play_cells`
  (`:699-739`), `_team_split` (`:678-696`), `slice_cell` (`:760`), `agreement` (`:766-772`), `replay_ok`
  (`:789-807`), `load_reference` (`:431`), `Reference.cell` (`:414`); `sweep.parse_size` (`ste/sweep.py:171`);
  `skills.FREE`, `team_skills`.
- **Produces:** `@dataclass(frozen=True) CellSpec(side: str, players: tuple[str, ...], team_strategies: tuple,
  drone_skills: tuple, drones: int)`; `cell_spec(gates, side) -> CellSpec` (from an `ExploitGates`; M2's distil gates
  build it from the skills gate file it pins); `other(side)`; `cell_of(side, mine, opp) -> (guard, strike)`;
  `fixed_choices(spec) -> list[dict]` (one per code in `players` order, keys `name`, `kind`, `heads`, `flies`,
  `script`); `all_choices(spec)` (the ceiling's order, either team); `mixed_pool(spec) -> list[tuple[str, ...]]` (free
  combinations with ≥ 2 distinct skills: Guard 24, Strike 60); `mixed_choices(spec, combos)`;
  `draw_mixed(spec, count, seed)` (a proposal tool whose output is written into `configs/ste_ls1/cells.toml`);
  `ConstHeads` (copy); `fixed_team(spec, choice, dispatch, name) -> exploit.SkillTeam` (constant heads per slot,
  identity scalers, **any** dispatch: scripts, net, stand-in); `Composite(side, members, cfg, n, device="cpu",
  seed=0, name=None)` (drone m flies column m of member m; a member is a script name or a player object);
  `ScriptOracle(cfg, side, skills, team_size, n_rows_hint=None)` (a C2 stand-in: `forward(obs [B,71], slot, z)` puts
  each row at index `slot` of a zero `[B, M, 71]` tensor, runs the K scripts once each, gathers `[b, slot_b, z_b]`;
  attributes `team`, `skills`, `k`, `team_size`); name-prefix constants of C6.
- **Tests first** (`tests/test_ste_ls1_cells.py`; ceiling imported through `_ste_tools.SCRIPTS` as
  `tests/test_ste_l3_run0_ceiling.py:19-22`): `all_choices(cell_spec(gates, "strike"))` equals `ceiling.choices(gates)`
  field for field; `fixed_choices` has K entries, each `flies == [code] * 3`; `mixed_pool` sizes 24 and 60, disjoint
  from the fixed choices; `draw_mixed` deterministic, `count` distinct; play (CPU, 24 games, `hold_ticks=1`): for each
  side every fixed choice through `fixed_team(..., two_level_dispatch(...))` equals its T44 cell (`replay_ok`, CPU, every
  game); `Composite` of the same name equals the script; 4 mixed combos: `fixed_team` equals `Composite` game for
  game; `NetTwoLevelDispatch(net=ScriptOracle(...))` through `fixed_team` equals the scripts' cells per game for every
  fixed choice and the 4 mixed combos, both teams (**positive control 2 in miniature**, review A F4.1); `Composite`
  with a member of the other team raises `ValueError`; `test_the_scripts_are_row_wise` (review A F5, the oracle's
  premise): `ScriptOracle.forward` on every live and out row of `team_obs` equals the scripts' team commands
  `torch.equal`, every code, both teams (scout: exact for all 11 scripts on 64 games x 40 ticks).
- **Implementation:** loops over cells and arms only. `ScriptOracle` is exact because the scripts are row-wise
  (`test_the_scripts_are_row_wise`). It lives in `ste/` (not the tests) because M2's control C2 and M3's clip test fly it.
- **Keep green:** `test_ste_l3_run0_ceiling.py`, `test_ste_l3_two_level.py` (`:342-365`), `test_ste_l3_held_arm.py`,
  `test_ste_literals.py`.
- **Commit:** `svg_training ste: cell module for the route 3 reads, both teams`.

### LS1-M1-T6 Changed scripts for the calibration (their own file)

- **Files:** new `source/svg_training/opponents/perturbed.py` (outside the literal scan, OP-9);
  `tests/test_ste_ls1_perturbed.py`.
- **Consumes:** `scripted.py` helpers `_unit` (`:21`), `steer` (`:26`), `_pack` (`:32`), `_slots` (`:38`),
  `_team_slots` (`:255`), `_wrap` (`:267`), `_stand_off_m` (`:272`), `_circle` (`:280`); `StrikeSacrifice.act`
  (`:390-418`, global `ENTRY_HALF_ANGLE_RAD` read at `:412`), `StrikeConverge.act` (`:436-475`, `GATHER_ANGLE_RAD`
  `:459`, `CIRCLE_UNTIL_RAD` `:471`), `GuardField.act` (`:128-145`, `FIELD_RANGE_M` `:18`), `StrikeFlank.MARGIN_M`
  (`:181`); `make_strategy` (`:217-233`).
- **Produces:** `CommandPerturbation(inner, kind: "noise" | "bias" | "scale" | "turn", size: float, seed: int, channels:
  tuple[int, ...])`: `act = clamp(f(inner.act(obs)), -1, 1) * alive`; noise i.i.d. uniform in [-size, size] per tick
  and channel from its own `torch.Generator` seeded `seed`; **bias adds the constant `+size` to each chosen channel
  on every live drone and every tick (zero on out drones through the alive multiply; review round 1, C1: the one kind
  that moves the zero-command skill, `guard_parked_centre` in 3v3, `scripted.py:297-299`, whose command a scale or a
  turn leaves at 0)**; scale multiplies the channels; turn rotates xy by `size` degrees; it accumulates, as tensors, the command error against the inner command over live drones (per-channel sum
  of squares, max |Δ|, count). Moved-switch players `SacrificeMovedEntry(entry_half_angle_rad)`,
  `ConvergeMovedGather(gather_angle_rad)`, `FieldMovedRange(range_m)` (copies of `act` that read an instance value)
  and `FlankMoved(margin_m)` (a subclass attribute).
- **Tests first:** at today's values each moved player and each wrapper at size 0 / scale 1 / turn 0 is `torch.equal`
  to its script on `team_obs`, both teams, out rows included; scale gives exactly `0.95 × script` on the chosen
  channels; bias gives exactly `clamp(script + size)` on the chosen channels of live drones, the other channels and
  out drones unchanged, and moves `guard_parked_centre`'s zero command to `size` on a 3-Guard `team_obs` (a scale or a
  turn leaves it 0, asserted beside it); turn keeps the norm and turns by 3° (`allclose`); noise is within [-s, s] before the clamp, zero on out
  drones, equal for equal seeds, different for another, independent of how a cell is chunked; the moved sacrifice
  differs from the script only on rows whose bearing lies between the two half-angles.
- **Implementation:** each moved player subclasses its script and copies its `act` with the module global replaced by an instance value
  (OP-9); the wrapper exposes `team`, `name`, `reset` (forwarded) and `act`; none is added to `REGISTRY`
  (`scripted.py:205-214`): the calibration builds them directly (`make_strategy` has a fixed constructor, `:217-233`).
  The noise generator lives on the obs device; the error accumulators are tensors read once per cell.
- **Keep green:** `test_ste_literals.py` (not scanned here), every `opponents` importer.
- **Commit:** `svg_training opponents: changed scripts for the LS1 calibration (scripted.py untouched)`.

### LS1-M1-T7 The paired statistics and the calibration read (job LS1.5)

- **Files:** `ste/cells.py` (statistics, C7); new `scripts/ste_ls1_calibration.py`; new
  `configs/ste_ls1/cells.toml`, `configs/ste_ls1/calibration.toml`; new `tests/test_ste_ls1_calibration.py`.
- **Consumes:** M1-T5, M1-T6; `ste_l3_held_arm.input_problems(gates)` (`scripts/ste_l3_held_arm.py:73-89`);
  `ste_sweep_l011.write_json` (`:138`), `SIMULATOR` (`:72`); `scoring.paired_wins` (`ste/scoring.py:86-98`; raises on
  an unfinished game), `plumbing_controls` (`:47-61`), `ending` (`:64-67`), `save_batch`/`load_batch` (`:163-176`),
  `pooled_row` (`:316-348`); `compare.paired_difference` (`ste/compare.py:62-74`), `per_start_mean` (`:77-79`);
  `transfer.sign_test_p` (`ste/transfer.py:254`); `metrics.wilson_interval(k, n, z)` (`core/metrics.py:30-39`);
  `exploit.PER_GAME` (`ste/exploit.py:54`, `end_step` stored), `counts` (`:442`), `replay_ok`.
- **Produces (statistics, in `ste/cells.py`):** `paired_cell(arm_pg, ref_pg, side, z: float) -> {"b", "c", "flips",
  "n", "diff", "ci": [lo, hi], "sign_test_p", "method"}` (interval PROPOSED Newcombe paired hybrid score, OP-11;
  φ = 0 on degenerate cells, said in `method`); `adjusted_z(alpha, m) -> float` (Bonferroni);
  `pooled_difference(arm_wins: dict, ref_wins: dict, z) -> {"diff", "se", "ci", "cells"}`; `end_time(arm_pg, ref_pg)
  -> {"differ_games", "mean_ticks", "median_ticks", "mean_abs_ticks", "p90_abs_ticks"}`. Empty strata are `None`,
  never NaN.
- **Produces (configs):** `cells.toml`: `[mixed] guard = [[…], …]`, `strike = [[…], …]` (20 explicit combinations per
  side, drawn once by `draw_mixed` with a named seed, written as data so no RNG stream is relied on);
  `[info_opponents] strike = ["guard_mark_inside"]`, `guard = []`; `[read] games_per_cell = 1000` (**the one place
  the cell size is written**, B-6: the calibration and the equivalence read both take it from here through their
  `cells_sha256` pin, so the owner's limits are set on the gate's own n; alpha is not needed to match, because b, c
  and n are stored and an interval at any alpha is recomputed without a replay).
  `calibration.toml`: `[noise] sizes`, `channels`, `active_only_arm`, `seed`; `[bias] sizes`, `channels`,
  `zero_skill_sizes` (C1: the xy ladder on every cell, and a finer ladder played only on the fixed cells of the
  zero-command skill, so the owner can set `cmd_zero_skill_max_abs` from the read); `[scale] size`, `channels`; `[turn]
  degrees`; `[switch] sacrifice_entry_rad`, `converge_gather_rad`, `field_range_m`, `flank_margin_m` (each a ladder);
  `[run] chunk_cells`, `device = "cpu"` (no game count of its own: `cells.toml [read] games_per_cell`; `--games` is a
  test-only override and writes `of_record: false`); `[source] skills_gates`, `skills_gates_sha256`, `cells`,
  `cells_sha256`, `scripted_sha256`. All PROPOSED (section 1 table); the lead hashes it before LS1.5.
- **Produces (script):** `ste_ls1_calibration.py --calibration <toml> --side guard|strike --out <folder>
  --expect-sha256 <hash> [--games N] [--chunk K]`; launched as `ste_job.py launch --task LS1.5 --gpu-h 0`. Exit 0 done,
  2 refused (finished folder, pin off, bad arguments), 5 non-finite, 6 control failed. Writes `controls.json` (first),
  `batch_*.npz` per chunk, `results.json` (`complete` last), `results.md`. Controls: (a) each unperturbed fixed-cell
  arm equals T44 on the CPU, every game; (b) the identity arm (size 0) has `b = c = 0` against the reference arm;
  (c) plumbing (paired starts, no non-finite). Per arm (each noise size, each bias size, each zero-skill bias size on
  its cells, scale, turn, each moved switch, the active-only noise arm): command error on the states the arm reached (RMSE and max per active channel, max on the
  others); per cell b, c, flips, diff with interval, sign-test p, end-step statistics; across cells median and max of
  flips, max |b − c|, pooled difference over all, fixed-only and mixed-only cells; the count of cells with p < 0.05.
  No pass or fail column: the owner sets the limits from this read (R38). Moved-switch arms play only the cells where
  their code flies (team strategies: their fixed cells; flank: its fixed cells and the mixed cells that contain it).
- **Tests first:** `test_paired_cell_counts_match_paired_wins` (synthetic arrays, both sides);
  `test_interval_contains_the_difference_and_narrows_with_n`; `test_a_worked_paired_example` (B-5; n = 1,000 with
  both won 500, b = 30, c = 20, both lost 450, z = 1.959964: `diff == -0.010`, `flips == 50`, `sign_test_p` =
  0.20264 (exact two-sided binomial, method-independent), Newcombe paired hybrid score without continuity correction
  (Wilson intervals of the two win shares, φ = 0.89994) `ci` = [−0.02381, 0.00383], all within 1e-5; architect-computed
  with the formula written in the test's docstring, QC re-derives them by hand before the test is committed; the `ci`
  numbers hold for Newcombe only: if OP-11 picks another method, that method is added beside it with its own worked
  numbers, before the gate is hashed); `test_adjusted_z` (m = 1 → 1.959964 within 1e-6,
  grows with m); `test_pooled_difference_is_the_mean_of_cell_differences`; `test_no_nan_in_results`
  (`json.dumps(allow_nan=False)`); a tiny run (8 games, one opponent, two arms, `tmp_path`) writes the documented keys,
  controls PASS, the identity arm has b = c = 0, `complete` last; a finished folder exits 2; a forced control failure
  (monkeypatch, as `tests/test_ste_l3_run0_ceiling.py:195`) writes `controls.json` only and exits 6; chunking does not
  change a game; `cells.toml` combinations are 20 distinct members of `mixed_pool` per side.
- **Implementation:** `input_problems` first (exit 2); per side and chunk of cells one `play_cells` call per arm with `players` (C6
  prefixes), hold 1, seed `ref.meta["seed"]`, `ticks_cap` = the pinned skills gate file's `gates.run["ticks_cap"]` (2,400
  today; read, not typed, CA-3); the reference arm is T44 for fixed cells, the played
  `Composite` for mixed cells; `RunGuard` with the JSON default (done chunks only, as
  `scripts/ste_score_matrix.py:622-632`); `save_batch` per chunk; resume skips saved chunks.
- **Keep green:** `test_ste_l19_l110.py`, `test_ste_l1side.py` (seed scans), `test_drone_loss.py` (`:148`, no
  `[team_size]` or dropout in new configs), `test_ste_job.py` (scripts scan `:318`), `test_ste_literals.py`.
- **Cost (estimate from review B's 2 to 4.5 s per 1,000-game cell-play, unmeasured here):** about 150 Guard and
  130 + 26 Strike cells x (reference + about 9 full arms, the three bias sizes included) plus switch arms and the
  zero-skill bias arms on their cells: roughly 50 to 115 min per side on an idle CPU, double beside other work.
- **Commit:** `svg_training: paired statistics and the LS1 calibration read (job LS1.5)`.

## 3. Merge M2: distillation, its driver, its gate file, the equivalence read

Lets run: LS1.0 (smoke), LS1.1 (distil, GPU), LS1.2 (equivalence read, CPU). Needs M1 merged.

### LS1-M2-T1 The distillation gate file and its loader

- **Files:** new `configs/ste_ls1/distil_gates.toml`; new `ste/distil.py` (the loader first);
  `tests/test_ste_ls1_distil_gates.py`.
- **Consumes:** `exploit._exact` pattern (`ste/exploit.py:138-146`, unknown and missing keys refused),
  `FILL_MARK` (`:98`), `sha256_file` (`:356`), `load_gates` (`:149-231`, bytes hashed as read `:153-154, :229`);
  `configs/ste_l3/skills_gates.toml` (`[games] base`, `[reference]` T44, `[pool] seed 140001`, `[players]`,
  `[learner]`, `decision_ticks 12`); M1's `cells.toml` and `cell_spec`.
- **Produces:** `load_distil_gates(path) -> DistilGates` (frozen: `path`, `sha256`, one dict per section);
  `unfilled_limits(g) -> list[str]`; module tuples `LIMIT_KEYS`, `CONTROL_SIZE_KEYS`. Every key REQUIRED, no
  default:
  - `[run]` `task`, `device`; `[source]` `skills_gates`, `skills_gates_sha256`, `cells`, `cells_sha256`,
    `scripted_sha256`, `game_file`, `game_sha256`;
  - `[data]` `games`, `ticks_per_round`, `hold`, `uniform_share`, `mix_share`, `random_share`, `absent_min_share`,
    `keep_rows`, `switch_jump`, `switch_window_ticks`, `switch_floor`, `seed`, `pool_seed`; `[dagger]`
    `script_share` (list, first entry 1.0); `[net]` `hidden`, `zeroed_inputs`, `std_floor`; `[fit]` `epochs`, `lr`,
    `batch`, `seed`; `[report]` `games`, `ticks`, `seed`, `hold_bins_ticks`; `[clips]` `games`, `keep`, `codes`,
    `seed`, `max_ticks`, `speed`, `fps`, `dpi`; `[smoke]` `games`, `rounds`, `ticks`, `read_games` (OP-15);
  - `[read]` `alpha`, `path_times_s` (1, 3, 10), `chunk_cells`, `device`, `control_games`, `near_miss_cells` (no
    `games_per_cell`: the read takes `cells.toml [read] games_per_cell` through `cells_sha256`, B-6; nor `ticks_cap`,
    `cap_check_every_ticks` or the seed: the read takes `gates.run["ticks_cap"]`, `gates.run["cap_check_every_ticks"]`
    and `ref.meta["seed"]` from the skills gate file it pins, CA-3);
  - `[limits]` (owner, R38; `FILL_…` until set): `cmd_rmse_max`, `cmd_unused_max_abs`, `cmd_zero_skill_max_abs`,
    `flips_max_games`, `cell_margin`, `pooled_margin`, `end_time_gated` (bool), `end_time_max_ticks` (OP-18);
  - `[controls]` `permutation = {guard = [...], strike = [...]}` (an explicit derangement of code indices),
    `permuted_min_miss_cells`, `unfitted_min_miss_cells` (owner, OP-21), `near_miss = {bias, rotate_deg, switch,
    noise}` (owner, set with the limits; `bias` is played as `CommandPerturbation(kind="bias")` on xy, `rotate_deg` as
    `kind="turn"`, `switch` as the moved-switch players at that size, `noise` as `kind="noise"`, M2-T5 `arms()`);
  - `[stop]` the stop rules of workflow §5 as text (control fails, NOT DISTILLED, one side only), with two notes the
    code imposes: added inputs need a new build (section 7, A F1) and a one-side-only continuation needs a gate-file
    variant (section 7, C7).
- **Tests first:** `test_the_committed_file_loads_and_its_pins_hold` (file sha == sha of bytes; `skills_gates_sha256`,
  `cells_sha256`, `scripted_sha256` and `game_sha256` equal the files' now; `game_sha256 ==
  load_gates(skills_gates).games["base"].sha256`); `test_every_key_is_required` (for each key of each section a
  `tmp_path` copy without it raises `ValueError` naming it; an unknown key raises); `test_limits_are_numbers_or_fill`
  (each `[limits]` value is a `FILL_` string or a finite number > 0, bool refused except `end_time_gated`;
  `unfilled_limits` lists exactly the `FILL_` ones of `[limits]` and of the owner's `[controls]` keys,
  `permuted_min_miss_cells`, `unfitted_min_miss_cells` and `near_miss`); `test_the_mix_rules` (`uniform_share >= 0.5`; the three shares
  sum to 1 by `math.isclose`; `script_share[0] == 1.0`; `hold == skills_gates.trainer["decision_ticks"]`);
  `test_the_seeds_are_new` (every seed ≠ 110000, ≠ 140001 and not among the other `configs/ste_*/*.toml` seeds, regex
  of `_seeds`, `tests/test_ste_l1side.py:366-368`, which `tests/test_ste_l19_l110.py` imports);
  `test_the_permutation_is_a_derangement`; `test_one_ruler` (B-6: neither `distil_gates.toml` nor `calibration.toml`
  holds a game count per cell; both pin the same `cells_sha256`).
- **Implementation:** `tomllib` on the file's bytes, sha256 of the same bytes (`ste/exploit.py:153-154, 229`); a per-section exact-key
  check in the `_exact` style (copied, the helper is private); numbers reject bool; shares by `math.isclose`;
  `DistilGates` builds `cells.CellSpec` from the pinned skills gate file.
- **Keep green:** `test_ste_l19_l110.py`, `test_ste_l1side.py`, `test_drone_loss.py` (no `[game]` section with
  `dropout_fraction`), `test_ste_literals.py`, `test_ste_l3_pipeline_gates.py`.
- **Commit:** `svg_training: LS1 distillation gate file (limits FILL until the owner sets them, R38) and its loader`.

### LS1-M2-T2 Collection: the code schedule, labels, flags and the weighted keep (`ste/distil.py`)

- **Files:** `ste/distil.py`; new `tests/test_ste_ls1_distil.py`.
- **Consumes:** `core/game.SvgGame(cfg, num_games, guards, strikes, device, seed)` (`core/game.py:80`; `reset`
  `:235`; `step` `:257` restarts ended games and returns the post-restart obs, `_new_games` defined `:179`, called `:349`);
  `exploit.variant_cfg(gates, "base")` (`ste/exploit.py:365-368`); `skills.two_level_dispatch`, `commands`,
  `widths`, `resolve_two_level` (`ste/skills.py:272-292`, leader = lowest-index live drone), `team_skills`, `FREE`,
  `ALIVE_FLAG_MIN`; `pool.OpponentPool(team, names, cfg, num_games, device, seed)` (`ste/pool.py:84-140`, `act`
  `:123-127`; **`redraw(games)` `:117-121` must run on `out.done`**, `reset` keeps the draw), `pool_members`
  (`:75-80`); M1's `NetTwoLevelDispatch`, `SkillNet`.
- **Produces:** `CodeSchedule(spec: CellSpec, dispatch, shares, combos: Tensor[C, M], hold, script_share, device,
  seed)`: per-game `[N]` and per-drone `[N, M]` tensors with its own `torch.Generator(seed + round)`;
  `new_games(mask [N] bool)` draws a mode (uniform / mix / random), a code (uniform), a combination row (mix) and
  `net_flown ~ Bernoulli(1 - script_share)`; `flown(obs, tick) -> [N, M] long` (uniform: code k on every drone; mix:
  the combination; random: at `tick % hold == 0` a (team index, drone index) per drone resolved by
  `resolve_two_level` on that tick's obs, the resolved flown held to the next decision).
  `collect(cfg, spec, players, side, net: SkillNet | None, script_share, games, ticks, hold, seed, pool_seed, device,
  should_stop=None) -> Rows`; `Rows` on the CPU: `obs [R, 71] f32`, `slot [R] i64`, `label [R, K, 4] f32` (every
  script's command on that state), `flown [R] i64`, `n_live [R] i8`, `held [R] i16` (ticks the flown code has been
  held), `mode [R] i8`, `net_flown [R] bool`, `near_switch [R] bool`, `round [R] i8`; live own-team rows only.
  Script-flown games fly `gather(label, flown)`, net-flown games `one_code(net, obs, flown)`, combined with
  `torch.where`. `net=None` with `script_share != 1.0` raises `ValueError`. `keep(rows, err: Tensor | None, keep_rows,
  absent_min_share, switch_floor, gen) -> Tensor[keep_rows] i64`: weighted sampling without replacement
  (Efraimidis–Spirakis keys `u ** (1 / w)` and `topk`; not `torch.multinomial`, limited to 2**24 categories), `w =
  err / mean(err)` raised to at least `switch_floor` on `near_switch` rows (round 0: `w = 1`, `switch_floor` on
  `near_switch`), stratified so rows with a mate absent are at least `max(absent_min_share, natural share) *
  keep_rows`.
- **Tests first** (CPU; 16 games, 24 to 120 ticks; `skills_gates.toml` `[players]`/`[learner]`):
  `test_labels_are_every_scripts_command_on_that_state` (helper to write `isolated(obs_rows, slot, M) -> [R, M, 71]`;
  `label[r, k]` equals script k's `act` on the isolated tensor at `[:, slot]`, `torch.equal`);
  `test_only_live_drones_give_rows` (`obs[:, 12] > 0.5` all, `0 <= slot < 3`);
  `test_uniform_and_mix_games_fly_one_code_per_drone_all_game`;
  `test_random_games_change_choice_only_on_hold_boundaries_from_each_games_start` (from `held` and `mode`);
  `test_same_seed_same_rows` (`torch.equal`; another round seed differs); `test_net_none_needs_script_share_1`;
  `test_near_switch_flag_follows_label_jumps` (helper `jumps(labels_t, labels_prev, same_game)`; never on a game's first
  tick or across a restart); `test_keep_is_exact_meets_the_absent_quota_and_is_uniform_without_weights` (stratum share
  ±1 row); `test_the_opponent_is_redrawn_after_each_game`.
- **Implementation:** label on the obs **before** `step`; reset the schedule, `held` and the switch countdown for
  `out.done` games after it. `near_switch` = any code's max-channel |label_t − label_{t−1}| > `switch_jump`, same game,
  live both ticks, held `switch_window_ticks` by a per-`[N, M]` countdown. Move live rows to the CPU in chunks of
  ticks (one host copy per chunk). Labels always come from the scripts, also in net-flown games. No scheduled drop-outs
  (OP-22). Memory (estimate): Strike, 4,096 games x 600 ticks x about 2.5 live drones ≈ 6.1 M rows x about 101 floats ≈
  2.5 GB on the CPU per round before keep.
- **Keep green:** `test_ste_literals.py` (channel indices, eps and 0.5 come from constants), `test_ste_l3_pool.py`,
  `test_ste_l3_pool_draw.py`, `test_ste_l3_skills.py`, `test_ste_l3_two_level.py`, `test_dependencies.py`,
  `test_ste_job.py::test_no_process_is_ever_found_by_name`.
- **Commit:** `svg_training ste distil: data collection with the review's data mix and weighted keep`.

### The files M2 writes: keys, types, readers (B-5; the tests of M2-T3, M2-T6, M3-T6 and M4 assert these names)

JSON floats are finite or `null` (an empty stratum); `[4]` is a list over the command channels (vx, vy, vz, yaw rate).

| File | Key | Type, shape | Read by |
|---|---|---|---|
| `fit_report.json` (M2-T3, M2-T4) | `rounds` | list of `{"round": int, "rows": int, "kept": int, "shares_by_mode": {"uniform", "mix", "random": float}, "absent_share": float, "near_switch_share": float, "prev_net_rmse": float \| null, "loss": [float per epoch], "seconds": float}` | the lead (diagnostics, OP-16), the record |
| | `final` | the `report()` dict: `per_skill` `{skill: {"rmse": [4] float, "p99_abs": [4] float, "active": [4] bool, "rows": int}}`; `unused_max_abs` `{skill: float \| null}`; `zero_skill` `{"name": str, "max_abs": float} \| null`; `rmse_by_n_live` `{"1", "2", "3": float \| null}`; `rmse_by_hold_bin` `{"<lo>-<hi>": float \| null}` over `hold_bins_ticks`; `delta_cmd` `{"net": float, "scripts": float}`; `game_steps_per_s` float | as above |
| | `gates_sha256`, `net_sha256` (str), `of_record` (bool), `complete` (true, last) | | the lead (a net goes to LS1.2 only from a complete, of-record report) |
| `results.json` (M2-T6) | `controls` | `{name: {"status": "PASS" \| "FAIL" \| "NOT_RUN", "detail": str}}` (equal to `controls.json`) | `verdict()`, the lead |
| | `cells` | list of `{"batch": str, "arm": str, "side": str, "kind": "fixed" \| "mixed" \| "info", "codes": [M] str, "opponent": str, "n": int, "b": int, "c": int, "flips": int, "diff": float, "ci": [2] float, "sign_test_p": float, "method": str, "end_time": end_time dict (M1-T7) \| null, "path_distance": {"1", "3", "10": path_distance entry \| null}, "games": {"file": "games/<batch>.npz", "start": int, "stop": int}}` | `limit_failures`, M3-T6 (picks), the record |
| | `pooled` | `{"all", "fixed", "mixed": pooled_difference dict (M1-T7)}` | `limit_failures` (`all`) |
| | `errors` | the command-error table of R1's fixed cells, and the `errors` argument of `limit_failures`: `{"skills": {skill: {"rmse": [4] float \| null, "max_abs": [4] float \| null, "active": [4] bool, "rows": int, "rmse_by_n_live": {"1", "2", "3": float \| null}}}, "zero_skill": str \| null}` (`active` from the scripts' labels on the same rows, as M2-T3) | `limit_failures` |
| | `failures` | list of str, or the string `"NOT_RUN"` (smoke with `FILL_`) | the lead |
| | `verdict`, `reasons`, `of_record`, `gates_sha256`, `net_sha256`, `skill_net_file`, `complete` | str (`"DISTILLED"`, `"NOT DISTILLED"`, `"INCONCLUSIVE"`, or `"NOT_RUN"` for a smoke), list of str, bool, str, str, repository-relative str, true (last) | M3-T6, M4-T3 (F7), the lead |
| `layout.json` (M2-T6) | `batches` | list, in play order, of `{"name": str, "arm": str, "side": str, "device": str, "seed": int, "ticks_cap": int, "hold_ticks": int, "n": int, "gates_sha256": str, "net_sha256": str \| null, "seconds": float \| null (null until played), "cells": [{"index": int, "arm": str, "codes": [M] str, "opponent": str, "player": str}]}` | M3-T6 (rebuilds each batch; its CPU estimate) |
| `games/<batch>.npz` (M2-T6) | `save_batch` arrays | `exploit.PER_GAME` keys, `[G]` with G = cells x n, as `scoring.save_batch` writes them | M3-T6 (replay check) |
| | `pos_at`, `alive_at` | f32 `[G, M, T, 3]`, bool `[G, M, T]`, T = `len(path_times_s)` | `path_distance`, M3-T6 |
| | `pair_class` | int8 `[G]`: 0 same, 1 `b`, 2 `c` (constants `PAIR_SAME`, `PAIR_B`, `PAIR_C` of the script); arm batches only | M3-T6 (picks) |

`limit_failures(cells, pooled, errors, limits)` takes `results["cells"]` (the net arm's fixed and mixed cells),
`results["pooled"]["all"]`, `results["errors"]` and the `[limits]` dict. One string per miss, naming the key: an active
channel's `rmse` above `cmd_rmse_max`; an inactive channel's `max_abs` above `cmd_unused_max_abs`; the zero-command
skill's largest `max_abs` above `cmd_zero_skill_max_abs`; a cell's `flips` above `flips_max_games` or its `ci` not
inside ±`cell_margin`; the pooled `ci` not inside ±`pooled_margin`; with `end_time_gated`, a cell's
`end_time.mean_abs_ticks` above `end_time_max_ticks`.

### LS1-M2-T3 The fit, the relabelling rounds, the report (`ste/distil.py`)

- **Files:** `ste/distil.py`; `tests/test_ste_ls1_distil.py`.
- **Consumes:** M2-T2; M1's `SkillNet`, `set_normaliser`, `all_codes`.
- **Produces:** `fit(net, rows: Rows, epochs, lr, batch, seed, device, should_stop=None, check=None) -> dict`
  (normaliser from `rows.obs` mean and std with the gate's floor; Adam; each minibatch expands rows x K codes; loss =
  mean squared error over K codes x 4 channels on `forward(..., clip=False)` (a clamp gives zero gradient on
  overshoot); seeded shuffle; `{"loss": [per epoch]}`; `check(loss=float)` each epoch). `dagger(...)` per round r:
  collect with `script_share[r]`, weight by the round r−1 net's per-row error (RMS over K codes x 4 channels, OP-17),
  keep `keep_rows`, re-initialise the net from `[fit] seed` and fit on all rounds so far (OP-17); per-round summary
  (rows, kept, shares by mode, absent and near-switch shares, previous net's error on the new rows, loss, seconds).
  `report(net, cfg, spec, players, side, games, ticks, seed, hold_bins_ticks, device) -> dict` on a **fresh,
  unweighted** collection (script share 0): per skill and channel RMSE and p99 |err| with `active` (any label on that
  channel ≠ 0.0); `unused_max_abs`; `zero_skill` (a skill whose labels are all exactly 0, with its max |output|;
  `guard_parked_centre` in 3v3, `scripted.py:297-299`); RMSE on active channels by `n_live` 1/2/3; flown-code RMSE
  by hold bin; mean |Δcommand| tick to tick for the net beside the scripts (same game, live both ticks, accumulated
  online); net game-steps per second (review A F9.6). Empty strata `None`.
- **Tests first:** `test_fit_lowers_the_error_of_every_skill` (hidden [64, 64]; each skill's RMSE < 0.5 x before);
  `test_report_has_every_read_and_none_for_empty_strata` (exactly the `final` keys of the table above;
  `json.dumps(allow_nan=False)`; Guard `zero_skill ==
  "guard_parked_centre"`; Strike: `strike_high`/`strike_low` have channel 2 active, the other skills channels 0 and 1
  only); `test_scripts_tick_to_tick_change_matches_a_direct_recomputation`;
  `test_net_flown_games_reach_other_states_and_stay_script_labelled`; `test_round_zero_needs_no_net_and_later_rounds_do`.
- **Implementation:** the fit runs on `[run] device`, the aggregate moved there once; the normaliser recomputed from the aggregate each
  round; report rows unweighted (kept rows are error-weighted); `None` for empty strata because `RunGuard.save` runs
  `check_finite` on the state (`ste/run_contract.py:207-219`).
- **Keep green:** `test_ste_literals.py`.
- **Commit:** `svg_training ste distil: fit, relabelling rounds and the fit report`.

### LS1-M2-T4 `scripts/ste_ls1_distil.py`: the driver under the run contract (jobs LS1.0, LS1.1)

- **Files:** new `scripts/ste_ls1_distil.py`; `tests/test_ste_ls1_distil.py` (driver part).
- **Consumes:** `run_contract` (exit codes `ste/run_contract.py:58-63`, `EXIT_FOR_STOP` `:69`, `RunGuard(run_dir,
  cap_s, dump, load)` `:121`, `stop_reason` `:188`, `check_finite` `:196`, `save` `:207`, `load_latest` `:243`,
  `RunBusyError`, `NonFiniteError`); `atomic`; `ste_exploit_l012.py` patterns (`RunGuard(..., dump=torch.save,
  load=lambda p: torch.load(p, weights_only=False))` `:285-286`; job.json `gpu_h` against `--cap-h` and device
  `:168-182`; gate sha in the run folder `:164-167, :290-292`); `ste_sweep_l011.pin_code(args)` (`:117-135`, needs
  `args.run_dir`, `args.allow_code_change`), `write_json` (`:138`); `viz/replay.record_games` (`:110-199`),
  `cpu_starts` (`:100`), `render_replay(..., height_panel=True)` (`:357`); `exploit.HeldPlayer`, M1 `cells.fixed_team`,
  `skill_net.save_skill_net`. `post_run.drives_training` (`ste/post_run.py:97`) stays False for this driver.
- **Produces:** `ste_ls1_distil.py --gates <toml> --side guard|strike --run-dir <dir> --cap-h <h>
  [--expect-gates-sha256 <hex>] [--smoke] [--no-clips] [--allow-code-change]`, and one hidden test flag to write
  (CA-2): `--stop-after-step <k>` (`argparse.SUPPRESS`, the precedent for a SUPPRESSed test flag is
  `ste_sweep_l011.py:90`, an unrelated flag): after checkpoint step k is saved the driver calls
  `os.kill(os.getpid(), signal.SIGTERM)`, so the real `RunGuard` handler (`ste/run_contract.py:171`) sets the stop and
  `stop_reason()` returns `"interrupted"` (`:188`) at the next check: exit 4 by the contract, no test-only exit path.
  Run folder: `gates.toml`,
  `gates.sha256`, `code.json`, `data/round_<r>.pt` (kept rows, atomic, sha256 in the checkpoint), `checkpoint.latest`,
  `progress.json`, `skill_net_<side>.pt` (C3; `provenance` holds the distil gates file and sha, rounds, seed, commit),
  `fit_report.json` (per round + final report, `complete: true` last, `of_record` false under `--smoke`),
  `results.md`, `videos/*.gif` (2-D, height panel: each `[clips] codes` code flown by the net beside the same start
  flown by the scripts). Checkpoint step `2r + phase` (0 collected, 1 fitted). Refusals (exit 2): schema error; `FILL_`
  limits outside `--smoke`; expected sha; any pin (skills gates, cells, scripted, game); data seed 110000; job.json and
  device mismatch; CUDA asked and absent; `RunBusyError`; a data file whose sha differs on resume. A done folder exits 0
  at once. Stops: collection checks `stop_reason()` in the tick loop, the fit between epochs; the partial round is
  redone (seeded by seed and round). Control `ctl_labels_are_the_scripts` (the isolation check of M2-T2 on a seeded
  sample of each round's kept rows; failure → `controls.json`, exit 6).
- **Tests first** (CPU, `[smoke]` sizes): `test_a_gate_file_off_its_expected_sha256_is_refused` (exit 2, nothing else
  written); `test_a_changed_teacher_pin_is_refused`; `test_a_cpu_smoke_writes_the_net_report_progress_and_exits_0`
  (the net loads with `load_skill_net` and its meta names the gate sha); `test_a_done_folder_exits_0_without_refitting`
  (mtime and sha of the net unchanged); `test_a_run_stopped_after_round_0_resumes_at_round_1` (hidden
  `--stop-after-step 1`, above; first launch exit 4; `data/round_0.pt`
  not rewritten); `test_a_nan_loss_exits_5_and_keeps_the_last_checkpoint`; `test_clips_are_written_with_the_height_panel`;
  `test_a_cpu_job_with_a_cuda_gate_device_is_refused`; `test_gpu_h_must_equal_cap_h`.
- **Implementation:** `main`: parse, then load and pins (exit 2), `pin_code`, `RunGuard`, resume; per round collect, write
  `data/round_<r>.pt` (`atomic.temporary_path` + `torch.save` + `commit`), checkpoint, fit, checkpoint; then the final
  report, `save_skill_net`, clips (CPU), `fit_report.json` last. State loads with `weights_only=False`.
- **Keep green:** `test_ste_run_contract.py`, `test_ste_job.py` (`:318` scans `scripts/ste_*`), `test_tier2_args.py`
  (no top-level isaac import), `test_dependencies.py`.
- **Commit:** `svg_training: the LS1 distillation driver (jobs LS1.0, LS1.1)`.

### LS1-M2-T5 The read's players and its verdict functions (`scripts/ste_ls1_equivalence.py`, importable part)

- **Files:** new `scripts/ste_ls1_equivalence.py`; new `tests/test_ste_ls1_equivalence.py` (imports the script as
  `tests/test_ste_l3_run0_ceiling.py` does, `tests/_ste_tools.py:14`).
- **Consumes:** M1 C7 statistics, `cells` (fixed, mixed, `fixed_team`, `Composite`, `ScriptOracle`),
  `NetTwoLevelDispatch(net=...)`, `perturbed`; `exploit.play_cells` (`ste/exploit.py:699-739`; one `hold_ticks` per
  call; `players` at `:701`, wrapped `HeldPlayer` at `:692`; returns host arrays, `start_sha256`, `choice_log`),
  `HeldPlayer` (`:543-598`; `reset` `:562-569`), `SkillTeam` (`command` `:629-631` runs without `no_grad`; the net path
  is under `no_grad` in M1); `core.game_config.TICK_S = 0.05` (`core/game_config.py:14`).
- **Produces:** `RecordingSkillTeam(exploit.SkillTeam)` (overrides `command` to record, for slots' first games only,
  own positions `obs[..., 0:3]` and alive at ticks `round(t / TICK_S)` for t in `path_times_s`, and, with a
  `labeller` dispatch, the flown code's command error against the scripts' label: per-channel sums of squares, max
  |out|, by `n_live`, batched); `RecordingPlayer` (the same position record for `Composite` and changed-script arms;
  no `holds_choice`); `PermutedNet(net, perm)` (`forward(obs, slot, z) = net(obs, slot, perm[z])`, C2 attributes);
  `unfitted_net(spec, gates, seed)` (fresh `SkillNet` with the gate's sizes); `arms(side, kind, ...) -> dict[name,
  player]` (one object per cell, C6 prefixes; the near-miss kinds map as M2-T1 says: `near_miss.bias` to
  `CommandPerturbation(kind="bias", channels=xy)`, `rotate_deg` to `kind="turn"`, `switch` to the moved-switch players,
  `noise` to `kind="noise"`); `path_distance(pos_a, pos_b, alive_a, alive_b) -> {mark: {"games",
  "median_m", "p90_m", "max_m"} | None}`; `limit_failures(cells, pooled, errors, limits) -> list[str]` (arguments and rule:
  the M2 file table above; it raises `ValueError` if any limit it reads is a `FILL_` string, so a `FILL_` never reaches
  a comparison); `verdict(controls, failures, unfilled: list[str]) -> "DISTILLED" | "NOT DISTILLED" | "INCONCLUSIVE" |
  "NOT_RUN"` (`unfilled` = `distil.unfilled_limits(g)`, non-empty only under `--smoke` since a run of record refuses an
  unfilled file: `"NOT_RUN"` when non-empty, F1; else INCONCLUSIVE if any control is not PASS; else NOT DISTILLED on
  any failure).
- **Tests first** (CPU, 24 starts): `test_the_recorder_keeps_first_games_only` (positions at tick 0 equal
  `play_cells`' `start_pos_m`); `test_the_oracle_net_flies_the_scripts_through_the_new_path` (fixed cells and two mixed
  combinations per side, `agreement(...)["differ"] == 0`); `test_the_net_arm_command_carries_no_graph` (unfitted,
  permuted, oracle); `test_the_permuted_scripts_miss_from_t44_alone` (permuted cell (k, opp) = T44 cell (perm[k],
  opp)); `test_one_player_object_per_cell`; `test_path_distance_excludes_ended_games_and_absent_drones`;
  `test_verdict_reads_controls_first`; `test_each_limit_just_crossed_gives_not_distilled` (constraint 5: cases built
  as limit x (1 ± ε) from `STAND_IN`, always, through a synthetic gate file under `tmp_path`; never from the committed
  file); `test_a_fill_limit_never_reaches_a_comparison` (`limit_failures` with one `FILL_` value raises; `verdict(...,
  unfilled=[...])` is `"NOT_RUN"`, never DISTILLED or NOT DISTILLED; the C3 to C5 miss counts and the C6/C7 judgments
  raise likewise on a `FILL_` control size or limit); `test_stand_in_mirrors_no_limit`
  (constraint 5); `test_each_near_miss_kind_maps_to_its_player` (bias, turn, switch, noise).
- **Implementation:** these live in the script (not literal-scanned; OP-12); `RecordingSkillTeam.reset` marks a slot's later games as
  `HeldPlayer._first` does (`ste/exploit.py:566-569`); one name per cell because `_team_split` reuses
  `players[name]` for every cell naming it (`:691-692`).
- **Keep green:** `test_dependencies.py`, `test_ste_job.py`.
- **Commit:** `svg_training: the LS1 equivalence read's players and verdict rule`.

### LS1-M2-T6 `scripts/ste_ls1_equivalence.py`: the read (job LS1.2), controls first

- **Files:** `scripts/ste_ls1_equivalence.py`; `tests/test_ste_ls1_equivalence.py`.
- **Consumes:** M2-T5; `RunGuard` with the JSON default (done batches only, as `scripts/ste_score_matrix.py:622-632`);
  the stop closure and `sweep.SweepStopped` (`ste/sweep.py:104`, raised `:438-440`; cap checked every
  `gates.run["cap_check_every_ticks"]` of the pinned skills gate file, CA-3); failed-control folder refusal and
  done-folder handling (`ste_score_matrix.py:606-616`: `controls_file` and `scoring.ending` `:606-612`, done folder
  `:613-616`);
  `replay_ok` per fixed cell (as `ste_l3_run0_ceiling.py:169-183`; `scoring.check_script_cells` cannot take prefixed
  names); `skill_net.net_problems`.
- **Produces:** `ste_ls1_equivalence.py --gates <distil_gates.toml> --side guard|strike --skill-net <file> --run-dir
  <dir> --cap-h <h> [--expect-gates-sha256] [--smoke] [--allow-code-change]` and a hidden test flag to write (CA-2)
  `--stop-after-batch <name>` (`argparse.SUPPRESS`; after that batch is saved it sends itself SIGTERM, as M2-T4's flag,
  so the stop is the contract's own and the exit is 4); CPU job (job.json `gpu_h` must be 0).
  Batches in order, each saved as played to `games/<batch>.npz` (`save_batch` arrays plus `pos_at [G, M, T, 3] f32`,
  `alive_at [G, M, T] bool`) and listed in `layout.json` (**for M3's clips:** per batch the cell list in order with
  arm, side, codes and opponent, `n`, `device`, `seed`, `ticks_cap`, `hold_ticks`, gate and net sha256):
  C1 `ctl_scripts_equal_t44` (fixed cells through `fixed_team` + scripts dispatch; `replay_ok` on the CPU; doubles as
  the scripted arm); C1m (scripted mixed arm, `Composite` via `RecordingPlayer`; plumbing); C2
  `ctl_oracle_net_equals_scripts` (`ScriptOracle`, differ 0 per game against C1/C1m); C3 `ctl_permuted_scripts_miss`
  (from T44, ≥ `permuted_min_miss_cells`); C4 `ctl_unfitted_net_misses`; C5 `ctl_permuted_net_misses`; C6
  `ctl_near_miss_systematic_fails` (one per kind, `limit_failures` non-empty); C7 `ctl_near_miss_random_passes`
  (`limit_failures` empty); then R1 (the net arm on fixed and mixed cells, with the command-error accumulators) and R2
  (INFO: Strike side against `guard_mark_inside`, both arms, not gated). `results.json`, `layout.json` and the
  `games/*.npz` arrays: exactly the keys of the M2 file table (per cell b, c, flips, diff, ci, sign p, end time, path
  distance per mark, the per-game b/c class as `pair_class` in the batch file; pooled difference; the command-error
  table from R1's fixed cells, OP-16); `complete: true` last; `results.md`; last stdout line the verdict word.
  **Under `--smoke` with `FILL_` values (F1):** C6, C7, `limit_failures` and the verdict are not run, and C3 to C5
  are played but not judged (their "at least N cells miss" needs the owner's `[controls]` counts and the `[limits]`
  that define a miss): C3 to C7 are written `NOT_RUN` in `controls.json`, `failures` and `verdict` are `"NOT_RUN"`,
  `of_record` false, and the last line is `NOT_RUN`; C1, C1m, C2 (judged as usual, they need no limit), R1, R2 and the
  per-game classes are played as in a run of record. Exit 0 for DISTILLED, NOT DISTILLED or a smoke's NOT_RUN; 6 a
  control failed (INCONCLUSIVE written, OP-19); 5 non-finite; 3/4 stopped; 2 refused (pins; `net_problems` non-empty;
  net meta's `distil_gates_sha256` not this file's; `FILL_` outside `--smoke`; `gpu_h > 0`).
- **Tests first:** `test_controls_are_written_before_any_result_batch` (hidden `--stop-after-batch`);
  `test_a_smoke_on_24_starts_ends_with_not_run_and_per_game_arrays` (net from the M2-T4 smoke, committed-style
  `FILL_` limits: last line `NOT_RUN`, C3 to C7 `NOT_RUN`, C1, C1m, C2 PASS, no DISTILLED or NOT DISTILLED anywhere, `results.json` has every
  key of the table); `test_a_smoke_with_stand_in_limits_ends_with_a_verdict_word` (a `tmp_path` gate file filled from
  `STAND_IN`);
  `test_a_failed_control_exits_6_and_again_6_on_the_same_folder` (oracle monkeypatched to change one command);
  `test_resume_skips_done_batches` (mtimes unchanged); `test_a_net_from_another_gate_file_or_side_is_refused`;
  `test_layout_names_every_batch_and_cell`.
- **Implementation:** batches in the order C1, C1m, C2, C3 (no play), C4, C5, C6, C7, R1, R2; every call hold 1, seed
  `ref.meta["seed"]` (110000 today) and `ticks_cap` `gates.run["ticks_cap"]` (2,400 today) of the pinned skills gate
  file, read, never typed (CA-3; `paired_wins` raises on an unfinished game); `controls.json` settled before R1; `layout.json`
  appended before each batch is played.
- **Cost (estimate, review B's measures; controls C4 to C7 not in the workflow's 50 to 75 min):** C1 30 + C1m 120/100
  + C2 + C4 30 + C5 30 + C6/C7 on `near_miss_cells` + R1 150/130 cell-plays of 1,000 games per side (OP-20).
- **Keep green:** `test_ste_job.py`, `test_dependencies.py`, `test_tier2_args.py`.
- **Commit:** `svg_training: the LS1 equivalence read (job LS1.2), controls before results`.

## 4. Merge M3: export of the skill network, the reload branch, the LS1 clips

Lets run: LS1.3 (export, CPU) and LS1.6 (3-D clips, GPU). Needs M1 and M2 merged.

### LS1-M3-T1 The export's variant is no longer fixed to "base"

- **Files:** `ste/export.py`; `scripts/ste_l6_export.py`; new `tests/test_ste_ls1_export.py`.
- **Consumes:** `export.golden_observations` (`ste/export.py:81-94`, "base" `:86`), `_dispatch` (`:97-99`, `:98`),
  `export_policy` (`:102-157`), `_interface` (`:160`, "base" `:161-162` and the seed line); `ste_l6_export.team_outputs`
  (`scripts/ste_l6_export.py:45-53`, `:49`), `main` (`:56-102`, reads `results.json`); `exploit.variant_cfg`
  (`ste/exploit.py:365-368`; an unknown name falls back to a `[games]` key, `:367`).
- **Produces:** a trailing keyword `variant: str = "base"` on `golden_observations`, `_dispatch`, `export_policy`,
  `_interface`, `team_outputs`; `ValueError("variant … not in the gate file")` before `variant_cfg`; inside
  `_interface` the variant's game and `train_seed[side]`; `interface.toml` gains `variant = "<name>"` only for a
  variant other than "base" (OP-24); `ste_l6_export` passes `results.json["variant"]` (default "base"), exit 2 for a
  variant not in the run's gate copy.
- **Tests first:** `test_export_without_variant_equals_variant_base_bit_for_bit` (`import test_ste_l3_export as tx`,
  as `tests/test_ste_l6_read.py:402`; ONNX bytes and interface text equal); `test_a_second_variant_exports_with_its_own_seed_and_game`
  (`configs/ste_l012/smoke_gates.toml` + `test_ste_l3_pool.POOL + TWO_LEVEL` in `tmp_path`, pattern of
  `test_ste_l3_pool.py:362-365`; variant `tag_1p2`: seed 120201, game sha and tag radius of that variant; helper to
  write `tiny_learner_from(gates, side, variant)`); `test_an_unknown_variant_is_refused`;
  `test_the_export_command_takes_the_runs_variant`.
- **Implementation:** thread the keyword; every existing caller is positional (`tests/test_ste_l3_export.py:55-56, 199-200`,
  `tests/test_ste_l6_read.py:406-407`, `scripts/ste_l6_export.py:85, 91`), so the default keeps them; golden
  opponents stay fixed (`ste/export.py:90-91`).
- **Keep green:** `test_ste_l3_export.py`, `test_ste_l6_export.py`, `test_ste_l6_read.py`. After the merge the lead
  re-runs `export.reload_check` on the four L6.2 export folders (in `runs/`, not in git; a recorded check).
- **Commit:** `svg_training ste export: the variant is an argument (a second seed exports with its own seed)`.

### LS1-M3-T2 The skill network as an ONNX graph, its stand-alone folder and reload

- **Files:** `ste/export.py`; `tests/test_ste_ls1_export.py`.
- **Consumes:** `export.STATUS` (`:36`), `SCHEMAS` (`:37`), `GOLDEN_ATOL/RTOL` (`:38-39`), `OPSET = 17` (`:40`),
  `within` (`:47-55`), `sha256_file` (`:62`), the export pattern (`:129-141`: BytesIO, dynamic axes, metadata, checker),
  `_obs_layout` (`:214`), `reload_check` (`:238-289`, schema lookup `:248-250`, heads loop `:252-277`,
  `slots = len(files)` `:188`); M1 C2/C3 and `read_skill_net_meta`.
- **Produces:** **the schema mechanism (B-1, CA-1; one for M3-T2 and M3-T3):** `SCHEMAS` keeps its two entries
  unchanged; new constants `SKILL_NET_SCHEMA = "ste-check-skillnet-0"` (stand-alone folder) and, in M3-T3,
  `SKILLS_NET_SCHEMA = "ste-check-skills-net-0"` (route 3 team folder) (OP-23); `ROUTE_OF_SCHEMA: dict[str, tuple[str,
  str | None]]` = each `SCHEMAS` value to `(route, None)`, plus `SKILL_NET_SCHEMA: ("skill_net", None)` and (M3-T3)
  `SKILLS_NET_SCHEMA: ("skills", "net")`. `reload_check` replaces the reverse lookup at `:248` by `route, source =
  ROUTE_OF_SCHEMA.get(schema, (None, None))`; the unknown-schema message lists `sorted(ROUTE_OF_SCHEMA)`. `skill_net_onnx(net, side, skills) ->
  onnx.ModelProto` (inputs `obs` f32 `[B, 71]`, `slot` i64 `[B]`, `z` i64 `[B]`; output `command` `[B, 4]`; dynamic
  B; opset 17; metadata status, schema, team, skills JSON, slot_width, k; `onnx.checker`);
  `skill_net_golden(net, obs [G, M, 71]) -> list[dict]` (`{"game", "obs" [M, 71], "commands" [M, K, 4]}`, one batched
  forward; out drones' rows are zero by C2); `export_skill_net(net, meta, side, out_dir, obs, source=None) -> Path`
  (writes `skill_net_<side>.onnx` and `interface.toml` with top-level schema, status, interface version, obs layout,
  team, tick, game file and sha, `scripted_sha256` (provenance), commit, tolerance, `source_*`, a `[skill_net]`
  section: `file`, `sha256`, `net_file`, `net_sha256`, `skills`, `slot_width`, `k`, `team_size`, `zeroed_inputs`,
  `alive_rule = "inside the graph: command times obs[12]"`, `code_rule = "z = index in skills; a two-level team's
  flown index is z"`, `input_check = "the consumer refuses slot outside [0, slot_width) and z outside [0, k)"`, and
  `[[skill_net_golden]]` rows; the net file is **not** in `[[files]]`); `_skill_net_check(folder, meta) -> dict`
  (sha; metadata; skills equal `[skill_net].skills`; rows range-checked before any runtime; onnxruntime and
  `ReferenceEvaluator` within `within` of the stored commands; `{"skill_net_max_abs_diff", "skill_net_golden_rows"}`);
  `reload_check` returns the stand-alone result right after the schema lookup when `route == "skill_net"` (a
  stand-alone folder has no `[[files]]`).
- **Tests first:** `test_the_skill_net_graph_takes_obs_slot_z_and_computes_the_network` (ops include OneHot; onnxruntime
  on G x M x K rows within `within` of `net(...)`); `test_the_input_scale_and_alive_rule_are_in_the_graph` (changing the
  scale buffers changes the ONNX output; an out row gives 0); `test_a_skill_net_folder_reloads_in_a_fresh_process`
  (`tx.reload_in_a_fresh_process`, `tests/test_ste_l3_export.py:42-47`); `test_the_skill_net_reload_refuses_damage`
  (parametrised: bytes changed → "sha256"; status removed → "status"; skills reversed → "skills"; a command bumped 1e-3
  → "golden", `tx.tamper`/`tx._bump` `:140-154`); `test_codes_out_of_range_are_refused_before_the_runtime` (z = k, z =
  −1). Helper to write: `tiny_skill_net(tmp_path, side)` (reuse `tests/_ste_ls1.save_tiny_net`).
- **Implementation:** `torch.onnx.export(net.eval(), (zeros(1, 71), zeros(1, int64), zeros(1, int64)), ...)` in the pattern of
  `ste/export.py:129-141`; files written with `onnx.save` and `Path.write_text` (`:141, :156`); the stand-alone
  branch of `reload_check` returns right after `:248-250`. No new dependency.
- **Gotchas (scout runs, torch 2.7.0, onnx 1.23.2, onnxruntime 1.20.1, test nets only):** onnxruntime's OneHot runs
  z = k and z = −1 without error (hence the range check); onnxruntime refuses int32 slot/z (golden arrays int64);
  differences 2.4e-7 / 1.2e-7 small net, about 5e-7 for a random 3 x 256 net against a tolerance near 1.8e-6. A
  trained net is not measured; the tolerance is not loosened without the lead.
- **Keep green:** `test_ste_l3_export.py` (its unknown-schema message lists one more value here, two after M3-T3; no
  test asserts that message, grep `unknown policy_schema` in `tests/`).
- **Commit:** `svg_training ste export: the skill network as an ONNX graph with golden rows and a reload check`.

### LS1-M3-T3 A route 3 team's folder: heads and skill network, and its reload branch

- **Files:** `ste/export.py`; `tests/test_ste_ls1_export.py`.
- **Consumes:** `export_policy` (route `:111`, dispatch `:120`, skills JSON `:122` written into every heads file
  `:136-138`, golden choices and commands `:150-155`); `_interface` `[skills]` (`:198-206`); `reload_check` heads loop
  (`:252-277`; **the literal six-key `mine` at `:261-268` is where a net team is refused first**); `_skills_reload`
  (`:292-319`; scripts sha `:294-296`, game sha `:297-299`, scripts dispatch `:302-303`, six-key compare `:304-306`);
  M1 `skills_meta` net keys, `NetTwoLevelDispatch.net`.
- **Produces:** `SKILLS_NET_SCHEMA` and its `ROUTE_OF_SCHEMA` entry `("skills", "net")` (M3-T2's mechanism; top-level
  schema of a route 3 team folder, OP-23). Writing: `schema_of(route: str, net: bool) -> str` (`SKILLS_NET_SCHEMA`
  when `route == "skills"` and `net`, else `SCHEMAS[route]`) replaces `SCHEMAS[route]` at `ste/export.py:133` (ONNX
  metadata) and `:173` (`interface.toml`); inside `export_policy` `route` stays `"skills"`. Reading: for a route 3 folder
  `reload_check` derives `route = "skills"`, `source = "net"`, so the per-file skill-list check at `:261` (`route ==
  "skills"`) and the golden branch at `:287` run for it **unchanged as text**; `mine` gains `skill_source` and
  `skill_net_sha256` when `source == "net"`; `:287` calls `_skills_net_reload` when `source == "net"`, else
  `_skills_reload`. The returned dict has `"route": "skills"` for both, and only a net folder's has `"skill_source":
  "net"` (a scripts folder's dict keeps today's keys). `scripts/ste_l6_read.py` keeps its own two-entry table (`:61`,
  check `:284`), so it refuses a route 3 folder, as OP-23 intends. A net team (detected by `skills_meta(d).get("skill_source") ==
  "net"`) also gets `skill_net_<side>.onnx`, `[skill_net]`, `[[skill_net_golden]]`, and in `[skills]`
  `skill_source = "net"` and `skill_net_sha256`; `reload_check`'s `mine` gains the two keys only when
  `meta["skills"]` has `skill_source`; `_skills_net_reload(folder, meta, obs, logits) -> dict`:
  `_skill_net_check`; `[skill_net].skills == [skills].players` (same order); `team_size == meta["slots"] ==` golden
  M; the game sha as `:297-299`; scripts sha reported as `scripted_sha256_now_equal` (provenance, not a refusal,
  review B5); a scripts `TwoLevelDispatch` built only for `greedy`/`resolve` (heads and flown equal the golden ones
  exactly); commands = the skill-net ONNX on `(obs.reshape(G*M, 71), tile(arange(M), G), flown.reshape(-1))`, int64,
  range-checked, within `within` of the golden command on both runtimes. Returns `{choices_equal, skill_lists_equal,
  commands_max_abs_diff, skill_net_max_abs_diff, scripted_sha256_now_equal}`.
- **Tests first:** `test_a_route3_team_folder_holds_heads_and_its_skill_net` (three heads files, one skill-net file,
  schema, `skills_meta(d)` in every heads file); `test_the_route3_reload_passes_in_a_fresh_process`;
  `test_the_route3_reload_flies_the_onnx_net_not_the_scripts` (monkeypatch `skills.SkillDispatch.commands` to raise);
  `test_a_scripts_team_export_is_unchanged_by_the_net_branch` (no `skill_source`, no `[skill_net]`, the ONNX skills JSON
  keys are the literal six, no `skill_net_*` reload keys, `policy_schema` `ste-check-skills-0`, the returned dict's keys
  as today); `test_the_route3_reload_refuses_tampering` (command, flown, reversed skills, `team_size = 2`; a golden
  command bumped fails on the net branch's "golden" message, not only on the heads);
  `test_a_route3_heads_file_with_tampered_skills_json_is_refused_by_the_heads_loop` (B-1: message "skill lists in
  interface.toml", before `_skills_net_reload` runs); `test_the_route3_reload_returns_route_skills_and_source_net`
  (`out["route"] == "skills"`, `out["skill_source"] == "net"`, `policy_schema` `ste-check-skills-net-0` in
  `interface.toml` and in every heads file's metadata); `test_a_drone_that_is_out_has_a_zero_command` (golden after 30 ticks, or a
  hand-made row). Helpers to write: `net_gates_file(tmp_path, side, net_paths)` (skills gate text with C4 keys);
  `tiny_net_learner(gates, side)`.
- **Implementation:** the net branch sits in `export_policy` after the dispatch (`:120`); the schema string is chosen by
  `schema_of`, apart from `route`, so the about 12 `route == "skills"` tests (writer and reader) are untouched;
  `reload_check` calls `_skills_net_reload` at `:287` when `source == "net"`.
- **Keep green:** `test_ste_l3_export.py` (incl. the large-logits test `:190`), `test_ste_l6_export.py`,
  `test_ste_l6_read.py`; the four L6.2 exports reload (lead, recorded).
- **Commit:** `svg_training ste export: route 3 team folders and their reload branch (scripts route unchanged)`.

### LS1-M3-T4 `ste_l6_export.py --skill-net`: the stand-alone export (job LS1.3)

- **Files:** `scripts/ste_l6_export.py`; `ste/export.py` (one helper); `tests/test_ste_ls1_export.py`.
- **Consumes:** `ste_l6_export.py` (`--run-dir required=True` `:58`; run-file checks `:67-69`; `refuse` `:40-42`;
  exit codes `:35`; controls pattern `:95-100`); `golden_observations` (`:81-94`); `ste_l6_read.reload_in_a_fresh_process`
  (`scripts/ste_l6_read.py:254-270`); M1 `read_skill_net_meta`, `load_skill_net`, `net_problems`.
- **Produces:** `export.golden_observations_cfg(cfg, guards, strikes, side, games, seed) -> Tensor[games, M, 71]`
  (`golden_observations` delegates to it); CLI `--skill-net <file> --side guard|strike --out <folder> [--games 8]`,
  mutually exclusive with `--run-dir` (one required). Game file and sizes from the net's meta (OP-26); the game file's
  sha must equal the meta's (exit 2). `controls.json`: `ctl_net_equals_export` (the torch net against the golden rows),
  `ctl_reload_fresh_process` (OP-25). Exit 0, 2, 6.
- **Tests first:** `test_golden_observations_cfg_equals_golden_observations` (`torch.equal`);
  `test_the_skill_net_export_command_writes_a_reloading_folder` (`main([...]) == 0`, both controls PASS);
  `test_the_skill_net_export_refuses_exit_2` (finished `--out`; meta game sha off; both modes given; `--skill-net`
  without `--side`); the existing `test_refusals_exit_2` (`tests/test_ste_l6_export.py:57-72`) unchanged.
- **Implementation:** a mutually exclusive argparse group replaces `required=True` at `:58` (a `--run-dir`-only call parses as today); the
  skill-net branch returns before the run-file checks `:67-69`.
- **Keep green:** `test_ste_l6_export.py`, `test_ste_l6_read.py`.
- **Commit:** `svg_training: stand-alone skill network export (job LS1.3)`.

### LS1-M3-T5 `replay3d.capture_trained` passes `players` through

- **Files:** `source/svg_training/viz/replay3d.py`; one new test in `tests/test_ste_replay3d_trained.py` (no edit to
  the existing tests).
- **Consumes:** `capture_trained(cfg, size, ref, cells, n, device, seed, ticks_cap, learner, hold_ticks, keep)`
  (`viz/replay3d.py:198-211`, `_team_split` calls `:208-209` without `players`); `exploit._team_split`
  (`ste/exploit.py:678-696`).
- **Produces:** a trailing `players: dict | None = None`, passed to both `_team_split` calls; `learner` may be None
  when no cell names the exploiter.
- **Tests first:** `test_capture_with_players_equals_play_cells_with_players` (CPU, `exploit.load_gates()`, N = 2,
  160 ticks as `tests/test_ste_replay3d_trained.py:14-31`; cells `[(guard_mark_edge, "scr:strike_flank"),
  (guard_mark_edge, strike_flank)]`, hold 1; per-game outcome, end_step, tags, strikes_left, start_pos_m,
  closest_3d_m equal `play_cells(..., players=same)` and the two cells are equal).
- **Implementation:** the keyword on the signature (`viz/replay3d.py:198`) and on both `_team_split` calls (`:208-209`).
- **Keep green:** `test_ste_replay3d_trained.py`, `test_ste_vid1_capture_trained.py`, `test_ste_l5_clips3d.py`,
  `test_ste_post_clips3d.py`, `test_ste_replay3d.py` (positional callers `scripts/ste_l5_clips3d.py:376-377`,
  `scripts/ste_vid1_capture.py:144-145`).
- **Commit:** `svg_training viz: capture_trained takes named players`.

### LS1-M3-T6 `scripts/ste_ls1_clips.py`: the copy beside the scripts (job LS1.6)

- **Files:** new `scripts/ste_ls1_clips.py`, `tests/test_ste_ls1_clips.py`. `scripts/ste_l5_clips3d.py` and
  `ste/post_run.py` unchanged.
- **Consumes:** `ste_l5_clips3d` as a module (`import ste_l5_clips3d as l5`): `render_stage` (`:418-431`, Isaac
  preflight and `--render-child`), `gif_ticks` (`:454`), `_raw_frames` (`:470`), `_overlaid` (`:480`), `stream_mp4`
  (`:495`), `fit_gif` (`:525`), `GIF_FRAME_CAPS` and cost constants (`:100-110`), `git_commit` (`:632`);
  **not** `encode_clips` (`:542-619`: it burns in a training run's caption and needs run meta keys);
  `viz/replay3d`: `capture_trained` (+ M3-T5), `check_against_record` (`:214-234`; the default `EXACT_KEYS` reads
  `start_pos_m`, which T44 lacks), `save_trajectory`, `caption` (`:351-355`, at most 400 characters);
  `scripts/make_ste_3d.render` (`:158-300`; one arena per launch `:176-179`; folders named by stem `:271`); M2's
  `layout.json`, `games/*.npz` (with `pair_class`) and `results.json` `cells` (M2 file table); M1 `cells` builders.
- **Produces:** `ste_ls1_clips.py --equivalence <folder> [--equivalence <folder>] --out <folder> [--settings]
  [--picks-per-side N] [--plan-only]`; a `RULE` constant fixed in code before rendering (OP-27); per pick both arms
  replayed on the read's device with the read's whole batch (`layout.json`; batch-mates matter, `ste/sweep.py:12-13`),
  **one replay per batch for all the picks in it** (B-11: `capture_trained`'s `keep` takes every picked game of the
  batch, so a batch is never replayed twice; at most 2 x picks batch replays, fewer when picks share a batch)
  through `capture_trained(..., players=...)` built by the same builders, each checked against the read's own
  per-game arrays (tol 0 on the CPU) — a mismatch exits 1 and that game is not drawn; trajectories
  `<out>/trajectories/<side>_<pick>_<cell>_game<i>_<copy|scripts>.npz` (meta: kind, side, arm, cell, codes, opponent,
  game index, outcome, tags, device, commit, gates and net sha); one render launch for both sides via
  `l5.render_stage`; its own `encode_ls1(out, work, settings)` from l5's helpers; `clips_ls1.json` (`complete` last,
  `atomic.write_text`); `--plan-only` prints the GPU-h ask, the number of batch replays and their CPU estimate (the sum
  of the read's own `seconds` of those batches in `layout.json`; about 12 picks x 2 arms x `chunk_cells` cell-plays at
  2 to 4.5 s each for the scripted arm, the net arm at the read's measured rate) and writes nothing. Two clips per pick, shown side by side
  on the record page.
- **Tests first** (CPU; `test_make_ste_3d.FakeIsaac`, `small_settings` as `tests/test_ste_l5_clips3d.py:30-37`; helper
  to write `tiny_equivalence_read(tmp, side, net)` using M2's script at N = 2):
  `test_both_arms_are_replayed_on_the_same_start_and_drawn` (with `ScriptOracle` as the net the two trajectories are
  equal frame for frame); `test_a_replay_that_differs_from_the_read_is_not_drawn` (one end_step tampered → exit 1);
  `test_picks_of_one_batch_share_one_replay` (B-11; a counter on `capture_trained`);
  `test_the_pick_rule` (hand-made `pair_class` arrays; written only after the lead confirms OP-27's rule, which is a
  start condition of this task, B-5); `test_plan_only_writes_nothing_and_refusals_exit_2`.
- **Implementation:** picks from M2's per-game `pair_class` (the batch file named by each cell's `games` entry); each replay rebuilds its whole batch from `layout.json`;
  `l5.render_stage` called as a module attribute so tests monkeypatch it (`tests/test_ste_l5_clips3d.py:40-51`); a
  CUDA-recorded read on a CPU-only machine is refused as `scripts/ste_l5_clips3d.py:358-360`.
- **Keep green:** `test_ste_l5_clips3d.py`, `test_ste_post_clips3d.py`, `test_ste_replay3d_trained.py`,
  `test_make_ste_3d.py`.
- **Commit:** `svg_training: LS1 clips of the copy beside the scripts (job LS1.6)`.

## 5. Merge M4: head training on the skill network (LS1.4)

Lets run: LS1.4 (pilot, run 0, Guard and Strike runs of both arms, export, unseen scores, the read). Needs M1 to M3.
**Start condition (B-3): the lead confirms OP-29 before M4-T1.** This section is written for option B (recommended):
M4-T1b is built, and both LS1.4 gate files carry `[run0] per_variant` and the run 0 seeds as M4-T4 says. If A is
chosen instead, M4-T1b is deleted, `heads_gates.toml` keeps `[run0] per_variant` absent and no `run0_seed`, and the
two keys leave M4-T4's named-keys test; nothing else in M4 changes.

### LS1-M4-T1 The gate loader takes the reading rule and lists the new fills

- **Files:** `ste/exploit.py`; new `tests/test_ste_ls1_gates_loader.py`.
- **Consumes:** `_SECTIONS` (`ste/exploit.py:68-85`), `_SECTION_OPTIONAL` (`:93-94`), `_exact` (`:138-146`),
  `load_gates` (`:149-231`; unknown sections `:155-157`; `[run0] skills_reach_min` typed `:207-213`; `verdict.order`
  `:223-224`), `ExploitGates` (`:116-135`, defaulted `learner`, `pool`), `unfilled` (`:292-295`, `[reference]` only);
  `preflight` refuses unfilled files (`scripts/ste_exploit_l012.py:138-140`); M1's `FILL_` sha rule (C4).
- **Produces:** a section `[reading]` (PROPOSED name; `ExploitGates.reading`, a new field defaulted to None),
  **required when `[learner] skill_source = "net"` and refused otherwise** (C4, F8: a net gate file without it does not
  load, so the reader never sees `reading = None`; every committed file, none of which is net, loads as today); every
  key REQUIRED: `margin_pooled`, `margin_cell` (each a float in (0, 1) or `FILL_…`),
  `last_reads` (int ≥ 1), `strike_read` (`"run0"`). `unfilled()` also lists `[reading] <key>`, `[run0]
  skills_reach_min` and `[learner.skill_net] <side>.sha256` when they hold `FILL_`; the loader accepts a `FILL_`
  `skills_reach_min` (and still checks it when filled).
- **Tests first:** `test_every_committed_gate_file_loads_as_before` (parametrised over the 13 files of `configs/ste_l*/`
  that `load_gates` loads at `d70b4e01`, listed explicitly, `configs/ste_ls1/` excluded: `.reading is None` and
  `unfilled()` as today, `[]` for all but `configs/ste_l1/l19_gates.toml`, whose five `[reference]` fills stay listed); `test_reading_keys_are_required_without_defaults`;
  `test_a_net_gate_file_needs_reading_and_a_scripts_one_refuses_it` (both directions, `ValueError` naming
  `[reading]`); `test_a_fill_placeholder_loads_and_is_listed`
  (preflight refuses with "not filled yet", via `driver.preflight(driver.parse([...]), gates)` as
  `tests/test_ste_l3_driver.py:254-258`); `test_reading_values_come_from_the_file` (equal to
  `tomllib.loads(text)["reading"]`).
- **Implementation:** `"reading"` joins the allow-list at `ste/exploit.py:155`; `_reading_table(data.get("reading"),
  learner)` beside `_pool_table` (`:234-247`), after `learner_spec` (`:226-227`) so it knows the source; `unfilled`
  extended with the same message format and only these named keys (it is also L0.12b's screen rule). The test helpers
  that write a net gate file (`tests/_ste_ls1.py`, M1-T4 test 3, M3-T3 `net_gates_file`) gain a `[reading]`
  block filled from `STAND_IN` in this task.
- **Keep green (B-7; rule: every test file that names a changed file, `grep -l "load_gates\|exploit" tests/*.py`):**
  `test_ste_l3_pipeline_gates.py`, `test_ste_l3_run0.py`, `test_ste_l1side.py`, `test_ste_l012.py`,
  `test_ste_l3_skills.py`, `test_ste_l012_driver.py`, `test_ste_l012b.py`, `test_ste_l012c.py`, `test_ste_l19_l110.py`,
  `test_ste_l3_driver.py`, and the M1 to M3 net tests (`test_ste_ls1_dispatch.py`, `test_ste_ls1_export.py`).
- **Commit:** `svg_training ste exploit: the LS1.4 reading section and fill markers in the gate loader`.

### LS1-M4-T1b A run 0 seed per variant (OP-29 option B; deleted if the lead picks A)

- **Files:** `ste/exploit.py`, `scripts/ste_exploit_l012.py`, `tests/test_ste_ls1_gates_loader.py`.
- **Consumes:** `_VARIANT_OPTIONAL` (`ste/exploit.py:108`), `_check_variant_options` (`:250-268`), seed checks
  (`:216-218, :243-246`); driver per-variant preflight (`:194-200`), `build_learner(..., int(r0["train_seed"]), …)`
  (`:976`), `learner_control.json` `train_seed` (`:1124`).
- **Produces:** optional `variants.<v>.run0_seed` read only under `[run0] per_variant = true` (refused otherwise);
  absent → today's `r0["train_seed"]`. `load_gates`' seed-distinctness check (`:216-218`) extends to every `run0_seed`
  (CA-4): distinct from each variant's `train_seed` values, `[run0] train_seed`, the other variants' `run0_seed`,
  `curve_seed`, `clip_seed` and `[pool] seed` (`:243-246`); `ref.meta["seed"]` (110000) is checked in the driver's
  preflight, which already loads the reference.
- **Tests first:** `test_per_variant_run0_trains_its_own_seed` (`learner_control.json` `train_seed` equals the
  variant's `run0_seed`); a file without the key records `[run0] train_seed`; `test_a_run0_seed_that_repeats_a_seed_is_refused`
  (parametrised over each seed it must differ from); `test_run0_seed_without_per_variant_is_refused`.
- **Implementation:** `_VARIANT_OPTIONAL` gains `run0_seed`; `run_run0` reads `variants[v].get("run0_seed", r0["train_seed"])` at `:976`
  and records it at `:1124`.
- **Keep green:** `test_ste_l1side.py`, `test_ste_l3_run0.py`, `test_ste_l3_driver.py`.
- **Commit:** `svg_training ste: a run 0 seed per variant (opt-in)`.

### LS1-M4-T2 The training driver's untrained-team control under a network

- **Files:** `scripts/ste_exploit_l012.py`; new `tests/test_ste_ls1_driver.py`.
- **Consumes:** `evaluate_controls` (`scripts/ste_exploit_l012.py:367-401`, twin branch `:379-388`); `run0_controls`
  (`:912-944`, twin `:924-930`); `run_exploit` (`:421-596`: `play` `:467-469`, before batch `:486`, final `:570`, INFO
  `:571-573`, `end_on_controls` `:471-480`); `run_run0` (`:952-1143`: twin cell appended `:966-968`, `play`
  `:1002-1004`, `end_on` `:1006-1012`, controls `:1014-1029`); `pilot` (`:1147-1296`: `timed_batch` `:1170-1178`,
  `untrained` `:1180-1186`); `preflight` (`:133-233`); `main` catches only around `load_gates` (`:263-267`);
  `exploit.eval_cells` (`ste/exploit.py:472-477`; `script_cells` `:480-482` passes every non-exploiter cell to
  `ref.cell` at driver `:374`, so the twin must never come from `eval_cells`), `run0_cells` (`:887-891`), `play_cells`
  (`players`), `replay_ok` (`:789-807`); M1 `cells.ConstHeads`, `cells.fixed_team`, `skills.two_level_dispatch`,
  `skill_net.net_problems`.
- **Produces:** `NET_TWIN = "net twin:"` (never a registry name, the exploiter or zero); `net_twin(gates, side,
  opponent, cfg, n, device, seed) -> tuple[list[tuple], dict[str, SkillTeam]]` returning `([], {})` unless
  `gates.learner.skills and gates.learner.skill_source == "net"`; the twin is `cells.fixed_team(spec, choice(FREE,
  first drone skill), two_level_dispatch(gates.learner, gates.players, side, cfg, n, device, seed), name)`, a
  `SkillTeam` (holds its choice; a plain net player would have its command frozen by `HeldPlayer`, `ste/exploit.py:574-578`).
  `run_exploit`: `cells = eval_cells(...) + twin_cells` (appended last), `players=twin_players` in the before and final
  batches. `evaluate_controls` under net: the twin is the `NET_TWIN` cell and the detail names it; the scripts branch
  `:379-388` byte for byte. `run_run0` under net: the twin cell replaces the append at `:966-968`; `play` gains
  `players` for the controls batch; `run0_controls` uses the twin; `state["script"]` stays the scripted cell. `pilot`:
  `timed_batch` gains `players`; step 1 and the timing batches play `eval_cells + twin`. `preflight` calls
  `net_problems` for both sides against the variants' game files, so a missing or edited net exits 2 before the run
  folder is touched (today a loader `ValueError` from `build_learner` escapes `main` as exit 1).
  **The pilot as a check (C8, F9; workflow §6 LS1.4-P):** `net_pilot_problem(gates, pilot_data, side, cap_h) -> str |
  None`, called by `preflight` for every run of record and run 0 under `skill_source = "net"` only (None otherwise, so
  the scripts and velocity routes are untouched): (1) the pilot's `strike_recipe.side_overrides_strike` must equal the
  gate's pinned `[trainer] side_overrides.strike`, for Guard runs too (`exploit.recipe_problem` already covers Strike
  runs and run 0, `ste/exploit.py:924-930`); (2) the game-steps the pilot's measured rate gives this side at
  `trainer.num_games` and this launch's `--cap-h` (the arithmetic of `project`, `scripts/ste_exploit_l012.py:1314-1332`,
  for the one cap `cap_h` rather than `PROJECTION_CAPS_H`) must reach the pinned `game_steps_per_run`. A miss returns
  "the pilot's rule would choose another Strike recipe / fewer game-steps than route 2's pinned … : nothing is
  launched, the lead reads the pilot (workflow §6 LS1.4-P)" and `main` exits 2 (`refuse`, `:268-270`).
- **Tests first:** helper to write `net_gate_file(folder, *, twin_code=0)` (SMOKE text `configs/ste_l012/smoke_gates.toml`
  + the TWO_LEVEL table of `tests/test_ste_l3_driver.py:24-40` + C4 keys pointing at tiny untrained nets saved with
  `save_skill_net`; drops variants `tag_1p2`, `tag_1p4`, sets `verdict.order = ["base"]` and the pilot's timing batches
  to base; a `[reading]` filled from `STAND_IN`, so `unfilled()` is empty and preflight passes, since M4-T1 requires
  the section in a net file and lists a `FILL_` in it); helper to write `distilled_read(folder, side, net_sha256)` (a
  fake LS1.2 `results.json`: complete, of record, DISTILLED, that net's sha; M4-T3 and M4-T7 use it); `test_net_untrained_team_equals_its_net_twin_and_every_control_passes` (Guard and Strike on the CPU, the
  `run()`/`run0_json()`/`skills_pilot()` patterns of `tests/test_ste_l3_driver.py:60-80`; every control PASS; the
  detail names the twin; `eval_before.npz` cell 0 equals the last cell in outcome, end_step, tags);
  `test_the_check_is_not_vacuous` (cell 0 differs from the scripts' first-skill cell in > 0 games; the helper picks a
  seed where it does); `test_a_twin_of_another_code_fails_exit_6`; `test_net_run0_controls_pass_with_the_net_twin`
  (`tiny_run0` pattern `tests/test_ste_l3_run0.py:172-192`); `test_net_pilot_records_the_net_learner`;
  `test_scripts_route_cells_and_players_unchanged` (`net_twin` returns `([], {})` for skills, velocity and SMOKE gate
  files); `test_preflight_refuses_a_missing_or_edited_net_exit_2`;
  `test_a_pilot_with_another_recipe_or_too_few_game_steps_is_refused_exit_2` (hand-made `pilot.json` beside the net
  gate file: a Strike recipe other than the pinned one, Guard and Strike; a rate whose projection at `--cap-h` falls
  one game-step short of `game_steps_per_run`; message "nothing is launched"); `net_pilot_problem` is None for the
  committed `skills_gates.toml` with route 2's L3.3 `pilot.json` shape.
- **Implementation:** plug-ins: `run_exploit` cells `:432`, `play` `:467-469` gains `players`, batches `:486` and `:570`;
  `evaluate_controls` a net branch before `:379`; `run_run0` `:966-968`, `play` `:1002-1004`, controls batch
  `:1017`; `run0_controls` `:924-930`; `pilot` `timed_batch` `:1170-1178`, step 1 `:1189-1197`, timing batches
  `:1199-1209`; `preflight` a net check after `:186-193`.
- **Keep green:** `test_ste_l3_driver.py` (`:141-152`), `test_ste_l3_run0.py` (`:113-128` passes a 4-cell list),
  `test_ste_l012_driver.py`, `test_ste_l3_pool.py`, `test_ste_l1side.py`, `test_ste_l013_driver.py`,
  `test_ste_l3_mask_learners.py`. The larger `eval_before/final.npz` (the appended twin cell) are read outside the
  driver by `ste_vid1_capture.py`, `ste_score_matrix.py`, `ste_tier2_score_l18.py` (`PLAYER_FILES` `:60`) and
  `ste_cross_tag_l012d.py` (`:252`), and all four refuse a skills gate file (`:96`, `:215`, `:189`, `:205`, CA-6);
  `ste_l5_clips3d.py` lists it in `RUN_FILES` (`:94-95`, existence only) and replays the INFO batch, which has no twin.
- **Commit:** `svg_training: the driver's untrained-team control flies a net twin under a skill network (review B1)`.

### LS1-M4-T3 The run 0 mark for the network (`scripts/ste_l3_run0_ceiling.py`)

- **Files:** `scripts/ste_l3_run0_ceiling.py`; new `tests/test_ste_ls1_run0_ceiling_net.py`.
- **Consumes:** `choices` (`:99-114`, 66 for 3v3), `fixed_team` (`:123-128`, already through the factory),
  `controls_of` (`:169-199`), `mark_rule` (`:202-215`), `of_record` (`:218-221`), `Composite` (`:232-245`),
  `oracle_check` (`:248-307`, refuses a changed gate sha `:267-269`); `gates.run0["margin"]`; M1 `skill_net.one_code`.
- **Produces:** under `skill_source == "net"`: `ctl_one_script_choices_are_reference` (`:169-183`) becomes status
  `INFO` with the T44 numbers kept (equivalence is LS1.2's gate); `--oracle-check` uses `NetComposite(net, codes,
  side)` (drone m flies code `skills.index(flies[m])` through `one_code` on the whole team tensor, no heads, no
  dispatch, hold 1; same batch shape as the dispatch path, constraint 8); `results.json` carries `learner_table` with
  the net. `play`, `choices` and `mark_rule` unchanged. Branch only inside `controls_of` and `oracle_check`, plus
  one refusal (F7): the demoted control is covered by LS1.2's C1 and C2 (DISTILLED on both sides is a prerequisite), so
  under net the ceiling, in both its modes (the mark and `--oracle-check`), takes `--equivalence <folder>` once per
  side and exits 2 unless each `results.json` is
  `complete`, `of_record`, `verdict == "DISTILLED"`, and its `net_sha256` equals that side's `[learner.skill_net]`
  sha256 (the net file itself cannot carry the verdict: its sha is pinned before LS1.2 runs). The mark rule is
  unchanged.
- **Tests first:** `test_net_ceiling_runs_and_sets_a_mark_from_the_nets_own_best` (temporary net gate file from M4-T2's
  helper, `--equivalence` folders from M4-T2's `distilled_read` for both sides in this and the oracle test, 2 to 4 games, `--chunk`; exit 0; the T44 control INFO; the choice-log control PASS; `mark.k_best ==
  max(choice k)`); `test_net_oracle_check_passes_and_a_differing_oracle_fails_exit_6`;
  `test_the_net_ceiling_needs_a_distilled_read_of_each_net_exit_2` (no `--equivalence`; a read that is NOT DISTILLED,
  INCONCLUSIVE, a smoke's NOT_RUN, not complete, or of another net sha); the scripts ceiling tests
  (`tests/test_ste_l3_run0_ceiling.py`) unchanged, including exit 6 on a scripts T44 FAIL.
- **Implementation:** run the ceiling and its oracle check on a draft copy of `heads_gates.toml`
  (the oracle refuses once the sha changes), then write the mark and hash once. The mark must lie above the untrained
  net team's Wilson upper bound, not route 2's 466. Cost estimate (review B timings): 66 choices x 1,000 games on the
  CPU, about 8 to 11 min.
- **Keep green:** `test_ste_l3_run0_ceiling.py`.
- **Commit:** `svg_training: the run 0 ceiling on a skill network (its own mark; T44 check INFO)`.

### LS1-M4-T4 The two gate files of LS1.4

- **Files:** new `configs/ste_ls1/heads_gates.toml`, `configs/ste_ls1/skills_seed2_gates.toml`; new
  `tests/test_ste_ls1_heads_gates.py`.
- **Consumes:** `configs/ste_l3/skills_gates.toml` (template: `side_overrides = { strike = {}, guard = {} }`,
  `game_steps_per_run = 550_000_000` `:58`, `final_reserve_s = 600` `:80`, base seeds 140201/140202, `run0.train_seed`
  140203, `skills_reach_min` 0.554, pool 140001, curve 140900, clip 140950); load checks (`verdict.order`
  `ste/exploit.py:223-224`, run 0 seed distinct `:216-218`, pool seed `:243-246`, `ref_variant` `:271-274`,
  `check_two_level` `ste/skills.py:212-237`); preflight maximin g*/s* (`ste_exploit_l012.py:153-161`);
  `skills_pilot_problem` (`:236-248`, learner table only), `recipe_problem` (`ste/exploit.py:924-930`), `run0_problem`
  (`:933-939`, gate sha), `pilot_problem` (`:942-979`: learner `:961-963`, PASS only `:964-966`, cap equality
  `:974-975`).
- **Produces:** `skills_seed2_gates.toml` (complete at M4): `skills_gates.toml` with `[run] task = "LS1.4"`, variant
  base seeds 140211/140212 (C8), `[run0] train_seed` 140213, the same `[learner]` (so the L3.3 pilot's table is
  accepted; its own run 0 because the gate sha differs); one variant only, so `[run0] per_variant` stays absent there
  and its run 0 pairs with route 3's `base_s2` run 0 by seed (140213 both). `heads_gates.toml` (template, `FILL_` until LS1.1, LS1.5 and
  M4-T3): `[run] task = "LS1.4"`; `[learner] skill_source = "net"` and C4 entries (sha `FILL_`); `[variants] base`
  (140201/140202, paired with route 2 seed 1) and `base_s2` (`game = "base"`, same g*/s*, 140211/140212, paired with
  route 2 seed 2, `reference_variant = "base"`, no extra opponents); `[verdict] order = ["base", "base_s2"]`;
  `[run0]` variant base, `train_seed` 140203 (base's run 0, paired with route 2 seed 1's), **`per_variant = true`**
  (OP-29 B; M4-T1b), and **`variants.base_s2.run0_seed = 140213`** (base has none, so it trains `[run0] train_seed`),
  `skills_reach_min` `FILL_` (from M4-T3); `[reading]` `FILL_` (owner, R38), with a TOML comment, hashed with the
  file, that records the departure from workflow §6 (C3: the last three reads of a run of record are `curve.json`
  reads, not paired per start, W3; the Guard score is OP-30's); route 2's recipe pinned as filled
  (`side_overrides.strike = {}`, 550 M), so the pilot is a check, not a fill (M4-T2 `net_pilot_problem`).
- **Tests first:** `test_heads_differs_from_skills_gates_in_the_named_keys_only` (style of
  `tests/test_ste_l3_pipeline_gates.py:33-50`: pop `[run] task`, the two learner keys, variant `base_s2` (with its
  `run0_seed`), `[verdict] order`, `[run0] skills_reach_min`, `[run0] per_variant`, `[reading]`; the rest equal, including `side_overrides.strike == {}`,
  `game_steps_per_run`, `[pool]`, `[controls]`, `[pilot]`); `test_seed2_differs_in_task_and_seeds_only`;
  `test_seeds_pair_across_arms`; `test_both_load_and_name_only_the_fills` (`unfilled(heads)` within the named fill
  keys; `unfilled(seed2) == []`); `test_the_task_is_in_the_route_budget` (`budget_of("LS1.4").section == "budget_ls1"`);
  `test_route2_pilot_table_equals_seed2_table` (and the heads table differs);
  `test_heads_has_reading_with_every_key` (F8: the four keys present, values `FILL_` until the owner sets them);
  `test_each_run0_seed_pairs_across_arms` (heads base run 0 = route 2 seed 1's 140203; heads `base_s2` run 0 =
  `skills_seed2`'s 140213). The pilot check itself (C8, F9) is tested in M4-T2.
- **Implementation:** copy `skills_gates.toml`'s text and change only the named keys, each with a labelled comment; route 2's L3.3
  pilot (`runs/2026-11-25_ste_l3_pilot_skills/pilot.json`) is then accepted by `skills_seed2` (learner table equal)
  and refused by `heads_gates` (the table carries the net).
- **Keep green:** `test_ste_l3_pipeline_gates.py` (reads `configs/ste_l3/*` only), the seed scans.
- **Commit:** `svg_training: LS1.4 gate files (route 3 heads template with fills; route 2 second seed)`.

### LS1-M4-T5 `scripts/ste_ls1_read.py`: the read of LS1.4

- **Files:** new `scripts/ste_ls1_read.py`, `tests/test_ste_ls1_read.py`, fake-folder helpers.
- **Consumes:** `scripts/ste_l6_read.py` (scout-read: `Refused` `:81`, `stopped` `:119-141`, `check_pilot_sha`
  `:167-179`, `read_pilot` `:182-195`, `read_run0` `:198-206`, `read_main` `:213-251` incl. the short-of-budget refusal
  `:228-229`, `same_starts` `:393-399`; ROUTES/TASKS/SCHEMAS `:54-61` unchanged); `compare.wins_by_cell`,
  `paired_difference`, `per_start_mean`, `overall_share` (`ste/compare.py:25-93`); `scoring.pooled_row`, `rate`;
  saved files: `results.json` (`train_seed`, `recipe`, `game_steps`, `budget_reached`, `learner`, `gates_sha256`,
  `pooled`, `info`, `best_single_choice`), `eval_info.npz`, `curve.json` (`curve_point`,
  `scripts/ste_exploit_l012.py:606-621`: 256 games on the curve starts against g*/s*), `learner_control.json`
  (`reads`, `status`, `train_seed`, `cap_h`, `learner`).
- **Produces:** `ste_ls1_read.py --manifest <toml> --out <folder>` → `read.json`, `read.md`; exit 0 or 2. The
  manifest names per arm (route2, route3) and seed (s1, s2) the pilot, run 0, Guard and Strike folders. Rule (margins
  from `gates.reading`, never typed): per seed a score; "no drop beyond Δ" when mean(route 3) ≥ mean(route 2) − Δ and
  every route 3 seed ≥ min(route 2) − Δ; "below" when mean(route 3) < mean(route 2) − 2Δ; otherwise INCONCLUSIVE and a
  third seed per arm is named. **Which Δ applies where (C3):** Strike: the run 0 cell (one run 0 per seed and arm
  under OP-29 B), score = the mean of its last `last_reads` reads, Δ = `margin_cell` (OP-34); Guard: the pooled row of
  the final INFO batch, paired per start (OP-30 (a)), Δ = `margin_pooled`; the Guard per-cell differences against
  `margin_cell` are written per cell as INFO, not gated (two seeds carry no per-cell verdict; OP-30). `read.json`
  carries per seed and arm, beside each score, `min_last_reads` (the lowest of the last `last_reads` reads: run 0 reads
  for Strike, `curve.json` reads for Guard as INFO; review A F3). The departure from workflow §6 (the last reads not
  paired per start, W3) is written in `read.md` and in the gate file's `[reading]` comment (M4-T4). INFO: paired per-start pooled differences seed by seed;
  choice shares per opponent both arms; route 2's runs of record. Refusals: train seeds, run 0 seeds, pool seed,
  recipe, game sha or starts not paired; a route 3 `learner` without the net or with another sha; route 2 seed 2's
  pilot checked against the file it ran under plus learner-table equality. The word "level" never appears. A route 3
  run's `best_single_choice` is the scripts' (`ste_exploit_l012.py:707-708`): labelled so.
- **Tests first** (helpers adapted from `make_main`/`make_pilot`/`make_run0`/`wins_rows`,
  `tests/test_ste_l6_read.py:82-131`, with `train_seed`, `learner`, `recipe`, `curve.json`, run 0 `reads`; synthetic Δ,
  edge arithmetic with `fractions.Fraction` on the n = 1,000 count grid): mean exactly at mean2 − Δ → no drop, one
  count lower → not; one seed below min2 − Δ → INCONCLUSIVE; one count past 2Δ → below, exactly 2Δ → INCONCLUSIVE;
  "level" absent; the Strike score ignores an earlier dip; any pairing mismatch exits 2; a monkeypatched margin moves
  the verdict; the paired difference uses `same_starts`; `min_last_reads` is the minimum and is reported for every seed
  and arm; a Guard per-cell miss never changes the verdict; `test_a_gate_file_without_reading_or_with_a_fill_margin_exits_2`
  (F8: a net gate file without `[reading]` is refused by the loader, a `FILL_` margin by the reader, both exit 2);
  `test_stand_in_mirrors_no_limit` (constraint 5; the synthetic Δ come from `STAND_IN` through a `tmp_path` gate
  file).
- **Implementation:** import `ste_l6_read` as the driver imports `ste_sweep_l011` (`sys.path`); `read_main` needs each folder launched
  through `ste_job.py` (an `exit_code` file; route 2's folders have one, scout-checked).
- **Keep green:** `test_ste_l6_read.py`.
- **Commit:** `svg_training: the LS1.4 read (route 3 against route 2, seed by seed)`.

### LS1-M4-T6 Scores against players of no pool (INFO)

- **Files:** new `scripts/ste_ls1_unseen.py` (OP-31), `tests/test_ste_ls1_unseen.py`.
- **Consumes:** `exploit.play_cells(..., learner=route_team, hold_ticks=12, players={"route1:<side>": velocity_team})`;
  `exploit_train.team_from_modules` (`ste/exploit_train.py:427-445`), `skill_team_from_modules` (`:448-473`); the route
  1 runs (L5.1 velocity Guard and Strike, `configs/ste_l3/velocity_gates.toml`, `mask_absent` true); `scoring.plumbing_controls`.
- **Produces:** per route team (2 arms x 2 seeds x 2 sides) one cell against the other side's route 1 team on T44's
  first 1,000 starts; `results.json` (counts, Wilson intervals, pooled rows, per-game npz, `complete` last), INFO.
- **Tests first:** `test_route_team_v_velocity_team_plays_both_held_12` (SMOKE-sized, tiny fake checkpoints);
  `test_a_velocity_checkpoint_from_a_skills_folder_is_refused`; `test_score_matrix_still_refuses_skills_gate_files`
  (`scripts/ste_score_matrix.py:215`).
- **Implementation:** the velocity team through `team_from_modules` with `hidden` from `configs/ste_l3/velocity_gates.toml`, the route
  team through `skill_team_from_modules` with the heads gate file's dispatch; both in one `play_cells` call held 12
  (one hold per call); CPU of record.
- **Keep green:** `test_ste_score_matrix.py`, `test_ste_l6_read.py`.
- **Commit:** `svg_training: route 3 teams scored against route 1's trained teams (INFO)`.

### LS1-M4-T7 A route 3 run's post-run clips and run export (B-4, C6; after M4-T2)

- **Files:** new `tests/test_ste_ls1_post_run.py`. No code change is expected (the paths below already go through the
  factory); if a test shows one is needed, it is a separate task, announced.
- **Consumes:** `make_videos` (`scripts/ste_exploit_l012.py:791-806`, net dispatch through the factory at `:802`);
  `ste_l5_clips3d.build_team` (`scripts/ste_l5_clips3d.py:323-342`, factory `:338`), `capture` (`:346-400`: the INFO
  batch replayed on the run's device at the record's cells x n, tol 0 on the CPU), `EXIT_MISMATCH` (`:91`, `:721`);
  `viz/replay3d.check_against_record` (`:214`); `ste/post_run.py` (`drives_training` `:97`, `CLIPS3D_GPU_H` `:71`);
  `ste_l6_export.main(["--run-dir", …])` (M3-T1 variant, M3-T3 net branch); `FakeIsaac`, `small_settings`,
  `fake_render` (`tests/test_ste_l5_clips3d.py:31-51`); the driver-run fixture pattern `pooled_runs`
  (`tests/test_ste_l3_pool.py:347`) with M4-T2's `net_gate_file`.
- **Produces:** tests, and one rule written into the LS1.4 job table (section 6): for a route 3 run a replay that
  differs from the record leaves that game undrawn and the clips job `failed` (exit 1), while the training job's own
  exit code (written before the hook runs) stands; the run's record says "3-D clips pending: replay differed" for those
  games; the 2-D clips that `make_videos` draws inside the driver exist for every run (the hook runs after the exit
  code is written and cannot change it, `ste/jobs.py:34`). Risk named: on the GPU the replay
  matches only if the net's kernels give equal results at equal batch shape, as route 2's heads already must (the INFO
  batch carries no twin cell, so its shape is the record's).
- **Tests first** (CPU, a tiny net run of the driver on `net_gate_file`): `test_make_videos_draws_a_net_team_clip`;
  `test_build_team_builds_the_net_team_and_its_replay_equals_the_record` (`capture` on the run's INFO batch,
  `check_against_record` equal at tol 0); `test_a_net_replay_that_differs_is_not_drawn_and_exits_1` (one `end_step`
  of `eval_info.npz` tampered); `test_the_export_of_a_route3_run_folder_exits_0_and_reloads`.
- **Keep green:** `test_ste_l5_clips3d.py`, `test_ste_post_clips3d.py`, `test_ste_l6_export.py`, `test_ste_l3_pool.py`.
- **Commit:** `svg_training: tests of a route 3 run's post-run clips and run export`.

## 6. The budget change list (R43)

All in merge M1 (M1-T1, M1-T2). The section is appended after `[budget_l3_l4_l5_l6]`:

```toml
[budget_ls1]
phases = ["LS1"]          # FIXED (owner, R39 and R43, 25 Nov 2026): route 3's GPU-hours, all stages, outside R23's 20
closed = false            # FIXED (owner, R42, 25 Nov 2026): the word for the build
phase_cap_gpu_h = 200.0   # FIXED (owner, R43, 25 Nov 2026): the number the launcher needs for route 3 (PLAN.md section 9)

[budget_ls1.task_cap_gpu_h]
"LS1.0" = 0.0             # PROPOSED (workflow v3 section 5; CPU): smoke of the distillation and the read
"LS1.1" = 0.8             # FIXED (owner, R43, as workflow v3 section 3 records it; two distillations at 0.4): distil both teams
"LS1.2" = 0.0             # PROPOSED (workflow v3 section 5; CPU): equivalence read, both teams
"LS1.3" = 0.0             # PROPOSED (workflow v3 section 5; CPU): export and reload of both skill networks
"LS1.4" = 4.0             # FIXED (owner, R43, 25 Nov 2026): head training on the skill network, both arms, clips included
"LS1.5" = 0.0             # PROPOSED (workflow v3 section 5; CPU): calibration read
"LS1.6" = 0.1             # FIXED (owner, R43, as workflow v3 section 3 records it): 3-D clips of the copy beside the scripts
```

Task caps add to 4.9 ≤ 200.0. Workflow v3 section 3 attributes 0.8 and 0.1 to R43; the owner's R43 row
(`ste_learning/DISCUSSION_2026-11-19_20.md:758`) names 200 and 4.0 only. The plan follows the workflow (the source of
truth on the what) and labels them FIXED with that source named; the difference is kept as W6 and OP-40. Other changes: `ste/config.py:37-48` `TASK_IDS["LS1"]`; `tests/test_ste_config.py`
`:90`, `:107`, `:514-515` and the new test; `tests/test_ste_budget.py` new test; `ste/budget.py` `section_summary`,
`budget_summaries`; `scripts/ste_job.py:174` status lines (and `carry --section` if OP-4); PLAN §9 row. Nothing in
`ste/budget.check_launch` or `ste/jobs.py` changes. Every LS1.4 job still states its ask at launch; an ask above
5 GPU-h is announced first (R39 as read).

**What the caps allow, and the owner step beyond them (F4).** `check_launch` refuses a launch when the task's used
hours plus the new ask exceed the task cap (`ste/budget.py:262-270`; hours a job already used are credited, so a
restart is not counted twice). The caps are the owner's (R38, R43); the lead never moves one.

- **LS1.1 (0.8 = two fits at 0.4).** The one announced fix round of workflow §5 can launch only if the two first fits
  used less than they asked by at least the re-fit's ask; otherwise it needs an owner-announced cap change in
  `configs/ste_learning.toml`, and `LS1_TASK_CAP_GPU_H` and `task_caps_total_gpu_h() == 4.9` (M1-T1's test) move with
  it in the same commit.
- **LS1.6 (0.1).** Kept at 0.1 by cutting the number of picks until `--plan-only` gives an ask ≤ 0.1 (OP-27), never by
  moving the cap.
- **LS1.4 (4.0).** The jobs and their asks (workflow §6; OP-28's asks beside; route 3's second run 0 under OP-29 B):

| Job | Count | Ask each, workflow §6 | Ask each, OP-28 | Note |
|---|---|---|---|---|
| LS1.4-P pilot (route 3) | 1 | 0.1 | 0.1 | the check of M4-T2 (`net_pilot_problem`) |
| LS1.4-0 run 0 (route 3) | 2 under B (1 under A) | 0.4 | 0.6 | at the cap of its Strike runs (`ste/exploit.py:974-975`) |
| LS1.4-G1, -G2, -S1, -S2 (route 3) | 4 | 0.4 | 0.6 | post-run clips: a replay that differs leaves its game undrawn, the run stands (M4-T7); risk: GPU results at equal batch shape |
| LS1.4-R0 run 0 (route 2 seed 2) | 1 | 0.4 | 0.6 | |
| LS1.4-RG, -RS (route 2 seed 2) | 2 | 0.4 | 0.6 | post-run clips as today |
| post-run clips jobs | 6 | 0.1 | 0.1 | charged to LS1.4 (`ste/post_run.py:71`) |
| **Sum of asks** | | **4.3 under B (3.9 under A)** | **6.1 under B (5.5 under A)** | expected use about 2.5 to 2.8 (workflow §1, §6; estimate) |

  The sum of asks is not what binds; each launch's used + ask is. The lead tracks used + the next ask before every
  LS1.4 launch and asks the owner before any launch whose ask would take the task over 4.0 (no launch is made to be
  refused).

## 7. Review findings and where each is built

| Finding | Task(s) | Not built here (and why) |
|---|---|---|
| A F1 data coverage | M2-T1 `[data]` shares; M2-T2 schedule (uniform ≥ 0.5, fixed mixes, random), weighted keep, switch floor; M2-T3 error by hold bin and `n_live` | engineered polar/zone inputs (each drone's and its team-mates' bearing and distance from the zone): **not in LS1** (C2). The input is fixed at obs 71 + slot + code (C2), and `zeroed_inputs` is the only knob; added inputs need a new build (`SkillNet.forward`, the normaliser, the C3 file, the ONNX graph `[B, 71]` of M3-T2, the reload and the golden rows), so the fix round of workflow §5 can change the data mix, the rounds and the network size from the gate file, but not the inputs; `[stop]` says so (M2-T1); OP-14 |
| A F2 paired read, systematic error | M1-T6 changed scripts (noise, bias, scale, turn, moved switches); M1-T7 calibration and C7 (b, c, flips, interval, sign test, end step); M2-T6 flips limit, end time, path distance at 1/3/10 s | final distance to the zone: OP-14 |
| A F3 LS1.4 rule, Strike cell | M4-T1 `[reading]`; M4-T4 seeds paired, recipe pinned; M4-T5 rule, run 0 as the Strike read | how many run 0s per arm: OP-29; Guard score: OP-30 |
| A F4 controls | M1-T5 oracle in miniature; M2-T6 C1 to C7 (C6 includes the 0.05-bias near miss, `kind="bias"`); M2-T1 `[controls]`; M1-T7 bias ladder | — |
| A F5 what the net cannot see | M1-T3 game constants in meta and refused, zeroed inputs, std floor, slot one-hot; M2-T3 per-channel and zero-skill reads; M2-T1 limits; M1-T7 zero-skill bias arms (the calibration behind `cmd_zero_skill_max_abs`) | which further inputs to zero: OP-5 |
| A F6 switches, ±1, losses | M1-T3 clipped linear; M2-T2 near-switch floor and absent quota; M2-T3 by `n_live` | a gate cell that starts with a drone removed: OP-14 |
| A F7 held-out set | M1-T6 (teacher file untouched); M2-T6 R2 (`guard_mark_inside` INFO) | new held-out scripts: self-play's note (workflow §7) |
| A F8 self-play timing | — | self-play pilot: its own note (R44) |
| A F9 same starts, chatter, mask, speed | M4-T4/M4-T5 pairing; M2-T3 tick-to-tick change and game-steps/s; M1-T3 test 4 and M1-T4 test 4 (both paths); M2-T2 absent rows | LS2 exploration noise: LS2's note |
| B1 twin control | M4-T2; M4-T3 | `ste_l4_suite.py:62-72` under a net: not an LS1 job |
| B2 `skills_meta` | M1-T4 | — |
| B3 `learner_table`, pilot | M1-T4; M4-T4 recipe pinned | — |
| B4 route 2 second seed | M4-T4 `skills_seed2_gates.toml` | job LS1.4-R0 (run) |
| B5 reload and reader | M3-T2, M3-T3; M4-T5 | — |
| B6 budget | M1-T1, M1-T2, section 6 | — |
| B7 post-run clips in the cap | section 6 (4.0 includes them; the LS1.4 job table); M4-T7 (the hook under a net) | the per-job ask: OP-28 |
| B8 M1 standing alone | M1-T5, M1-T7 | — |
| B9 CPU read, mixed cells, no_grad | M1-T3 (no_grad), M1-T5 (hold 1, `Composite`), M2-T6 (scripted arm played) | — |
| B10 second seeds, export variant | M3-T1; M4-T4 | — |
| B11 plan details | M1-T4 (rebuild at `:105`, keys outside `TWO_LEVEL_KEYS`, per-team table, team size at first call, stable path C9); every test here names real helpers | — |
| B12 Strike comparison | M4-T5 (run 0 primary, runs of record INFO) | — |
| B Q1 budget list | M1-T1 (plus `tests/test_ste_config.py:514-515`, missed by B) | — |
| B Q2 call sites | M1-T4 (signature unchanged at all 12; slice 1 refuses `"net"`; `tier2_train.py:142` OP-8) | — |
| B Q3 driver assumptions | M4-T2, M4-T4 | — |
| B Q4, B Q6 | report B has no section for them (A answers Q6 in F8) | — |
| B Q5 clips | M3-T5, M3-T6; M2-T6 per-game arrays and `layout.json` | — |
| B Q7 names, off-means-identical tests | M1-T4 literal-key tests; M4-T4 named-keys test | — |
| Workflow §5 stop rule 3 (one side only) | — | **not in LS1** (C7): `[learner.skill_net]` needs both sides (OP-35) and a `FILL_` sha is refused when a dispatch is built, so a Guard-only or Strike-only continuation needs a gate-file variant (one side's heads only, the other side's entry optional), decided by the lead after LS1.2 |

**Lead steps outside the build tasks (C9).** Done by the lead, each recorded, none by the builder:

1. After LS1.2 reads DISTILLED: copy the two nets to `ste_provisional/skill_nets/<date>_ls1_<side>/` (C9), add them to
   `ste_provisional/SHA256SUMS`, fill their sha256 into `configs/ste_ls1/heads_gates.toml` `[learner.skill_net]`, run
   the net ceiling (M4-T3) and fill `skills_reach_min`, then hash the file.
2. The pointers: the README row of the two review reports ("the builder's task plan (to be written)") and workflow v3
   line 1 (it names the bridge plan as the task-level plan) are pointed at this file.
3. R45's writer's task (the route page, its figures and the slides redrawn for R39 to R41; workflow §8 item 6) runs
   beside the build; no task here touches it.
4. `[verdict] follow_up_seeds` (required by `ste/exploit.py:80`, read by nothing in `source/` or `scripts/`, review B
   finding 10) is copied unchanged into both LS1.4 gate files.

## 8. Open points the builder must NOT decide (for the lead; recommendation last)

**Before M1**
- **OP-1 Phase key.** (a) `"LS1"` / `[budget_ls1]` as workflow v3 (a later stage needs `phases = ["LS1", "LS2"]` and
  a rename to `budget_ls1_ls2` with test edits); (b) `"LS"` / `[budget_ls]` for every stage (R43: 200 for all stages;
  scout scratch run: loads, `check_launch("LS1.4", 4.0)` accepted). *Recommend (b)*; the plan is written in (a).
  **Settled before M1-T1 starts** (B-9); the substitution list is in C1.
- **OP-2 Where the game-file sha is refused.** (a) In `exploit.load_gates` when the source is net (reads the `.pt`;
  breaks the `FILL_` template); (b) a factory argument at 12 call sites; (c) constants in the factory, file sha in
  each driver's preflight via `net_problems`. *Recommend (c)* (as planned, C5).
- **OP-3 Status lines.** Route 3 only, or every section not closed. *Recommend every open section, in-work first.*
- **OP-4 `carry --section`.** *Recommend yes* (two machines share the 200 GPU-h); else route 3 hours from the other
  machine cannot be carried (`scripts/ste_job.py:165`).
- **OP-5 Zeroed inputs.** Workflow's four (6, 7, 10, 11) or every input no script reads (scout: also own vz 5, every
  slot's relative z and vz; per team more). *Recommend the four*, as a `[net]` key so a fix round can change it.
- **OP-6 Slot one-hot width.** The team's pad (5/3) or the team size. *Recommend the pad*; team size pinned apart.
- **OP-7 Net file location.** `ste_provisional/skill_nets/…` with `SHA256SUMS`, or another committed folder.
  *Recommend `ste_provisional`.*
- **OP-8 `tier2_train.py` and `"net"`.** *Recommend refuse* ("not wired").
- **OP-9 Changed scripts.** (a) Copies of `act` reading an instance value, under `opponents/`; (b) swap the module
  global around `super().act()` (mutates what the teacher arm reads in the same batch). *Recommend (a).*
- **OP-10 Perturbed channels.** *Recommend* noise on all 4 channels as the main ladder plus one active-only arm; bias
  on xy (a constant drift, the near miss of workflow §5), and on the zero-command skill's cells xy as its finer ladder;
  scale on xyz; turn on xy (vz and yaw rate act on the game, `core/game.py:271, 290-292`).
- **OP-11 Interval and correction.** Newcombe paired hybrid / Wald with continuity / exact conditional; Bonferroni /
  Holm / max-|z|; fixed and mixed cells one family or two. *Recommend* Newcombe, Bonferroni over all gated cells of a
  side, the pooled row at plain alpha; decidable after LS1.5 since b, c, n are stored. M1-T7 builds Newcombe with a
  worked example (B-5); another method, if chosen, is added with its own worked numbers before the gate is hashed.
- **OP-12 Where the statistics live.** `ste/cells.py` (planned; no new module) or a fourth module `ste/paired.py`
  (workflow's table names three). *Recommend `cells.py`.*
- **OP-13 Limits before R38.** `FILL_` strings refused outside `--smoke` (planned); a separate smoke gate file; keys
  left out (breaks "required"). *Recommend `FILL_`*; under `--smoke` the limit-dependent steps are written `NOT_RUN` (constraint 5, F1).
- **OP-40 The labels of LS1.1 = 0.8 and LS1.6 = 0.1** (F5). Workflow v3 §3 (`LS_EXECUTION_WORKFLOW.md:89`) says R43
  writes them; the R43 rows (`DISCUSSION_2026-11-19_20.md:758`, workflow §1) name 200 and 4.0 only. The values are
  the same either way. The plan labels them FIXED (owner, R43, as workflow v3 §3 records it). *Recommend* the lead
  checks with the owner once; if the owner says R43 named only 200 and 4.0, the two labels become PROPOSED before M1-T1
  (the labels are in its committed lines).

**Before M2**
- **OP-14 Review A items workflow v3 did not adopt.** Engineered inputs (A F1), final distance to the zone (A F2), a gate
  cell starting with a drone removed (A F6). *Recommend:* inputs not in LS1 (they need a new build, section 7 row
  A F1; the fix round cannot add them from the gate file); distance as INFO in the read if cheap; the removed-drone
  cell needs the owner (it changes the read's cells).
- **OP-15 The LS1.0 smoke.** `[smoke]` table and `--smoke` (planned, labelled not of record); size flags; a second file.
  *Recommend the table.*
- **OP-16 The command error the gate reads.** The read's own net arm on the fixed cells (states the net reached on the
  gate's starts) for the verdict, the fit report as diagnostics (planned); or the fit report alone. *Recommend as planned.*
- **OP-17 Keep and refit.** Row error RMS over codes and channels or max over codes; switch proxy = label jump
  (planned) or the scripts' own triggers; refit from scratch each round (planned) or warm start; sampling only
  (planned) or also 1/p loss weights. *Recommend as planned.*
- **OP-18 End-time limit.** A required `end_time_gated` bool plus a number (`FILL_`), or INFO only. *Recommend the bool
  plus the number.*
- **OP-19 Exit when a control fails.** 6 (terminal; repeat needs a new folder) or 0 with INCONCLUSIVE. *Recommend 6.*
- **OP-20 Cells and n of controls C4 to C7.** All gated cells (about 4 x 150 cell-plays more per side), fixed only, or
  fixed plus a few mixed. *Recommend fixed plus a few mixed at 1,000 games, cost stated.*
- **OP-21 N of "at least N cells miss".** An owner key with the limits, the read checking the permuted scripts reach
  it; or derived in the read from T44. *Recommend the owner key.*
- **OP-22 Rows with a mate absent.** Quota on kept rows (planned; natural share 22–27 % already) or dropped; scheduled
  drop-outs (`core/game.py:250`). *Recommend the quota, no scheduled drop-outs.*

**Before M3**
- **OP-23 Schemas.** A new `ste-check-skills-net-0` (team folder) and `ste-check-skillnet-0` (stand-alone), or the old
  `ste-check-skills-0` plus `[skill_net]` (an old consumer could fly the scripts instead of the net). *Recommend new.*
- **OP-24 `variant` line in `interface.toml`.** Only when not "base" (base exports stay text-identical but for the
  commit). *Recommend that.*
- **OP-25 Fresh-process reload of LS1.3.** A control inside the export command (planned), M4's reader, or a test only.
  *Recommend the control* (LS1.3 has no reader before M4).
- **OP-26 Stand-alone export sizes.** From the net's meta (planned, C3 `guards`/`strikes`) or a `--gates` file.
  *Recommend the meta* (one input, already pinned by the net's sha).
- **OP-27 LS1.6 pick rule and ask.** PROPOSED rule per side: the fixed cell with the most flips (its lowest b game and
  lowest c game), the mixed cell with the most flips (lowest changed game), filled to 3 with an agreeing game; both
  arms each. L5's cost constants (`scripts/ste_l5_clips3d.py:105-110`) give an ask near 0.18 to 0.24 GPU-h for 12
  trajectories (scout and architect arithmetic, unmeasured) against the 0.1 cap. *Recommend* `--plan-only` first; if
  above 0.1, fewer picks per side until the ask is ≤ 0.1; the cap is the owner's and is not moved (F4). **Confirmed
  before M3-T6 starts** (its `test_the_pick_rule` pins the rule, B-5).

**Before M4**
- **OP-28 LS1.4 asks.** 0.4 per training job (workflow §6) cannot reach 550 M game-steps (section 9, W1). *Recommend*
  asks of at least 0.6 per job, every run 0 at the same cap as its Strike runs (`ste/exploit.py:974-975`); the sum of
  asks is then 6.1 GPU-h under OP-29 B (5.5 under A; section 6's LS1.4 table, 16 jobs under B) against the 4.0 cap row, but
  `check_launch` counts used hours (`ste/budget.py:262-270`) and the expected use is about 2.5 to 2.8; the lead asks
  the owner before any launch whose ask would take used + ask over 4.0 (F4).
- **OP-29 Run 0 seeds.** One `train_seed` per gate file (`scripts/ste_exploit_l012.py:976`): (A) one run 0 per arm, the
  Strike read n = 1 per arm; (B) M4-T1b, a run 0 per seed variant (+0.3 to 0.4 GPU-h); (C) one heads gate file per
  seed. *Recommend B* (owner's call: cost). **Confirmed before M4 starts** (B-3): M4 is written in B; choosing A
  deletes M4-T1b and two keys from M4-T4 (section 5's start condition).
- **OP-30 The Guard score.** (a) Final INFO batch, pooled and per cell, paired per start, with the last-three curve
  mean as INFO; (b) the last-three `curve.json` mean (256 games, curve starts, one opponent, not paired); (c) a new
  driver option saving checkpoints or INFO batches at the last three reads (route 2 seed 1 re-run). *Recommend (a)*,
  Δ = `margin_pooled` on the pooled row, the per-cell differences against `margin_cell` as INFO, `min_last_reads`
  reported (M4-T5, C3).
- **OP-31 The unseen scorer.** Its own script (planned; the reader stays play-free, as `ste_l6_read` is) or a reader
  subcommand (workflow §3 names only `ste_ls1_read.py`). *Recommend its own script.*
- **OP-32 `heads_gates.toml` before its fills.** A `FILL_` template at M4 (planned) or the file only at the
  hashing step. *Recommend the template.*
- **OP-33 The `[reading]` name and keys** (`margin_pooled`, `margin_cell`, `last_reads`, `strike_read`), or the rule
  kept in the reader with only the margins in the gate file. *Recommend the section* (the rule is pre-registered with
  the file's hash).
- **OP-34 Δ of the Strike run 0 read** (one cell, counts only). *Recommend `margin_cell`.*
- **OP-35 Both sides required in `[learner.skill_net]`.** *Recommend both* (LS1.4 starts after DISTILLED on both).
  Consequence (C7): workflow §5's "DISTILLED on one side only: that side may go on" is not possible in LS1 without a
  gate-file variant (section 7); the lead decides one if it arises.

**Choices this plan made that differ from a scout or from workflow v3's file table (the lead confirms or reverses)**
- **OP-36 The alive rule inside `SkillNet.forward` and the ONNX graph** (C2). The M3 scout recommended it outside the
  graph (dispatch and reload multiply; unmasked golden rows). Inside means one rule on every path and stand-in, golden
  rows of out drones are exactly 0, and a consumer cannot forget it; outside keeps the graph a pure function of the
  inputs. *Recommend inside.* No ONNX export with the alive multiply has been run yet (section 10).
- **OP-37 Two config files not in workflow §3's table:** `configs/ste_ls1/cells.toml` (the explicit mixed combinations,
  shared by the calibration and the read, pinned by both) and `configs/ste_ls1/calibration.toml` (the perturbation
  ladders, hashed before LS1.5). Alternative: both inside `distil_gates.toml` (but that file is hashed only after
  LS1.5, so the calibration would run on an unhashed file). *Recommend the two files.*
- **OP-38 LS1.6 "beside":** two clips per pick shown side by side on the record page (planned; no new compositing) or
  one composited frame (new code in the renderer). *Recommend two clips.*
- **OP-39 The statistics and the near-miss players land in M1** (C7, M1-T6) although workflow §4 lists the
  equivalence read in M2, so the calibration and the gate share one ruler. *Recommend as planned.*

## 9. Where workflow v3 or a review report is wrong or impossible against the code

- **W1 (workflow §6 asks, LS1.4).** 0.4 GPU-h per training job cannot reach the pinned 550 M game-steps: training
  stops when cap − effective < the reserve (`scripts/ste_exploit_l012.py:511`, run 0 `:1068`; reserve ≥ `final_reserve_s
  = 600`, `configs/ste_l3/skills_gates.toml:80`, `ste/exploit.py:860-864`); 0.4 h = 1,440 s leaves about 840 s of
  effective time, route 2 trained 952.6 s and 957.6 s (L5.2 Guard and Strike `results.json`, both at `--cap-h 1.5`,
  `budget_reached` true; route 2's run 0 at cap 1.5). The run would end short of budget (run 0 INCONCLUSIVE at the cap
  reserve, `:955`; a run of record refused short by the reader, `scripts/ste_l6_read.py:228-229`, scout-read). OP-28.
- **W2 (workflow §6 "One run 0 serves both Strike seeds" with "the Strike read is run 0").** One run 0 seed per gate
  file (`scripts/ste_exploit_l012.py:976`), so the Strike read has one route 3 read per arm and the two-seed rule of
  §6 cannot apply to it. OP-29.
- **W3 (workflow §6 "a seed's score is the mean of its last three reads … compared start by start").** Runs of record
  save only `curve.json` reads (256 games on the curve starts against one opponent, `scripts/ste_exploit_l012.py:606-621`)
  and one final INFO batch; the last three reads are not paired per start. OP-30.
- **W4 (workflow §5 LS1.6 0.1 GPU-h).** L5's cost constants (`scripts/ste_l5_clips3d.py:105-110`) put 12 trajectories
  above it (estimate). OP-27.
- **W5 (workflow §3 budget row; review B6/Q1).** `tests/test_ste_config.py:514-515` (the value-line count) also
  breaks; both reviews and the workflow name only `:90` and `:107`.
- **W6 (workflow §3 budget row).** It records 0.8 and 0.1 as the owner's (R43); the owner's R43 row
  (`DISCUSSION_2026-11-19_20.md:758`) names 200 and 4.0 only. The plan follows the workflow (FIXED, source named; F5).
- **W7 (review B5, workflow §3 export row "`export.py:302-306`").** A net team's export is refused first at
  `ste/export.py:261-268` (the skills JSON in every heads file against the literal six-key dict), before
  `_skills_reload`; B cites `:275-279`.
- **W8 (review B2).** The skills JSON is written into each ONNX file at `ste/export.py:136-138` (B: `:131-132`).
- **W9 (review B1, B9 line numbers).** `play_cells`' `players` `ste/exploit.py:701` (B: 700); the wrap `:692` (B:
  691); `HeldPlayer`'s command hold `:571-578` (B: 545-559); `run_run0` twin append `scripts/ste_exploit_l012.py:966-968`
  (B: 1000-1002); `run_run0.play` `:1002-1004` (B: ~1032-1035); `end_on` `:1006-1012` (B: 1008); run 0 twin branch
  `:924-930` (workflow: 921-933); `post_run.drives_training` `ste/post_run.py:97` (B: 83-95).
- **W10 (review A F2, F3).** `PER_GAME` is at `ste/exploit.py:54` (A: 46-48); `scoring.pooled_row` `ste/scoring.py:316-348`
  (A: 316-341; scout-read).
- **W11 (review B1 "equality is then exact on the CPU"; B Q5).** True only at equal batch shapes: CPU MLP results move
  by about 1e-7 with the batch size (constraint 8, scout measurement). Twin and exploiter are both called on `[n, M]`
  per cell, so the twin control holds; any oracle or replay must keep the shape.
- **W12 (workflow §5 CPU time 50 to 75 min).** Excludes controls C4 to C7 and the Strike INFO cells (estimate).
- **W13 (workflow §3 export row, review B5).** onnxruntime's OneHot accepts out-of-range codes without error (scout
  run): the reload must range-check inputs (M3-T2), which neither names.
- **Pointers, not code:** workflow line 1 still names the bridge plan as "the task-level plan of LS1", and the README
  row of the two review reports says "the builder's task plan (to be written)"; this file now is that plan (not edited
  here; a lead step, section 7).

## 10. Verified in the code, and not checked

**Re-read by the architect at `d70b4e01`:** `ste/skills.py:40-162, 240-324`; `ste/config.py:35-50`;
`ste/budget.py:160-271`; `scripts/ste_job.py:160-179`; `tests/test_ste_config.py:86-108, 498-515`;
`configs/ste_learning.toml:70-98`; `ste/exploit.py:543-635, 686-702, 860-865`; `ste/export.py:259-311` and the
`"base"`, metadata and `slots` lines (`:86, :98, :122, :136-138, :161-162, :188`); `scripts/ste_l6_export.py:49, 58`;
`opponents/scripted.py:28-40` and its sha256; `scripts/ste_exploit_l012.py:227-228, 376-392, 506-513, 606-621,
918-935, 962-980, 1000-1012, 1032-1070` and its function heads; `ste/post_run.py:71, 97`;
`scripts/ste_l5_clips3d.py:100-112`; `ste/tier2_train.py:138-146`; `scripts/ste_l3_run0_ceiling.py:66-130, 228-246`;
`tests/test_ste_l19_l110.py:185-208`; `tests/test_ste_l1side.py:365-380`; `tests/test_ste_l3_two_level.py:176-192`;
`ste_learning/DISCUSSION_2026-11-19_20.md:754-762`; seeds in `configs/` and `ste_provisional/` (none in 140210-140299 or 15xxxx, full grep); a CPU run of
`exploit.load_gates` over every `configs/**/*gates*.toml` (13 load, 11 belong to other loaders, `l19_gates.toml` lists five
`[reference]` fills); the evidence files of constraint 2; `ste_provisional/`, `.gitignore:1`; route 2's L5.2 and L3.5 run folders (`results.json`,
`job.json`, `learner_control.json`).

**Re-read for review round 1 (same commit):** `ste/export.py:37, 133, 173, 240-292` (route derived by reverse lookup
at `:248`, tested at `:261` and `:287`) and every consumer of `SCHEMAS` and of the returned `route`
(`scripts/ste_l6_read.py:61, 284`; `tests/test_ste_l3_run0.py:207`, `tests/test_ste_l5_clips3d.py:76`; no test asserts
the unknown-schema message); `ste/budget.py:255-271`; `ste/config.py:160-200`; `ste/run_contract.py:165-195`;
`ste/post_run.py:60-100`; `ste/jobs.py:34`; `ste/exploit.py:69-70, 80, 108, 200-220, 920-980`;
`scripts/ste_exploit_l012.py:84-96, 190-250, 258-270, 791-810, 970-980, 1120-1126, 1280-1332`;
`scripts/ste_l5_clips3d.py:91, 318-400, 721`; `scripts/ste_score_matrix.py:600-618` (636 lines);
`ste/compare.py` (93 lines); `scripts/ste_sweep_l011.py:85-91`; `tests/test_ste_l1side.py:366-368`;
`core/game.py:179, 240, 349`; `opponents/scripted.py:290-300`; `configs/ste_l3/skills_gates.toml` (seeds, `[run0]`,
`follow_up_seeds`); `configs/ste_learning.toml` (closed flags); `scripts/ste_tier2_score_l18.py:60, 189`,
`scripts/ste_cross_tag_l012d.py:205, 252`; `tests/test_ste_l3_export.py:29`, `ste/exploit_train.py:381`; workflow v3
§5 (`:175-198`) and §6 (`:200-240`). M1-T7's worked interval numbers: architect-computed (Newcombe 1998 hybrid score,
no continuity correction), not yet re-derived by a reviewer.

**Read by the scouts only (file:line as they reported, two scouts agreeing where both read it):** the rest of
`ste/exploit.py`, `ste/exploit_train.py`, `ste/export.py`, `scripts/ste_exploit_l012.py`, `ste/scoring.py`,
`ste/compare.py`, `ste/transfer.py`, `ste/pool.py`, `ste/run_contract.py`, `core/game.py`, `core/observations.py`,
`core/game_config.py`, `viz/replay.py`, `viz/replay3d.py`, `scripts/ste_l6_read.py`, `scripts/ste_l5_clips3d.py`
beyond `:100-112`, `scripts/make_ste_3d.py`, the test files named under "Keep green"; their CPU runs (scripts row-wise
for all 11, unread inputs, CPU batch-shape dependence, the budget section in a scratch copy, T44 cells and seed,
ONNX export of test networks, `reload_check` on the four L6.2 exports, the natural share of absent-mate rows and
label jumps).

**Not checked by anyone:** an ONNX export of a network with the alive multiply inside (C2; the scout's and reviewer
B's test graphs had none); the GPU speed and memory of collection, fit and a net-backed training run; a trained net's
ONNX tolerance margin; whether a tiny random net differs from the script cell in 8 smoke games (M4-T2 test 3); the CPU
time of the calibration, the read, the net ceiling and the LS1.6 replays (estimates only); a second derivation of
M1-T7's worked example; whether a net team's post-run clips replay game for game (M4-T7 tests it on the CPU; the GPU is
not checked); how side-by-side launches see each other's hours in the ledger; the full
test suite (no test file was run for this plan).
