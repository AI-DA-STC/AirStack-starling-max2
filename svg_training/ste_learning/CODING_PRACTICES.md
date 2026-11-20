INTERNAL · reference page of the STE learning track, from the specialist draft `drafts/CODING_PRACTICES_draft.md` (20 Nov 2026). **[PLAN.md](PLAN.md) takes precedence** where the two differ; its section 2 lists every change made at integration.
[STANDARDS.md](STANDARDS.md) and does not replace it: where the two differ, STANDARDS wins until the owner rules.
Source of truth for direction: [DISCUSSION_2026-11-19_20.md](DISCUSSION_2026-11-19_20.md) (D1–D9, P1–P8).

# Coding practices: STE learning track

## 1. Where work happens

- Write only inside `svg_training/` (CLAUDE.md rule 1). Never edit `AirStack/`, `tools/`, `~/IsaacLab`, the drone
  parameter files, or NUS's code. The AirStack game node and the flight copy of the filter are another session's work
  after the owner approves a change plan (D4, §2.14).
- One short-lived worktree per task group, cut from `main` (root CLAUDE.md):
  `git worktree add ../AirStack-starling-max2-ste-<topic> -b ste-<topic> main`. Before writing: `git status -sb`,
  `git worktree list`, files changed in the last 30 minutes; files you did not create belong to someone else.
- Back to `development` (the shared working branch): rebase on `development`, run the full suite, `git merge --ff-only` in the live clone. The lead merges; if git
  refuses, stop and ask. The owner pushes; Claude never pushes.

## 2. Test first, on the CPU

1. Write the failing test, run it, watch it fail, then write the smallest change that passes (`train-change` step 3).
2. Every new module under `core/`, `models/` and the learner runs its tests **without Isaac Sim**. Isaac-only tests carry
   `@pytest.mark.isaac` and are skipped unless `SVG_ISAAC_TESTS=1` (`tests/conftest.py`).
3. **The PyTorch reference world is the oracle for tier 2.** `models/rigid_body.TorchRigidBodyWorld` integrates the same
   equations as `IsaacWorld`. Anything added to the physics drone (state delay, noise, drag) is computed in our code
   *before* `apply_wrench_b` or *after* `_read`, so the same test runs on both worlds; the Isaac agreement test
   (`configs/s2b.toml [agreement_gates]`) is rerun once per change of that path.
4. **Off means identical.** Every new behaviour sits behind a setting whose default reproduces today's output **bit for
   bit** on CPU; that test is written first (the pattern of `tests/test_command_chain.py`). This covers filter option
   B, the tag preset, delay, noise and drag.
5. Hand-checkable cases as fixtures: for the filter, the desk-run cases of DISCUSSION §2.9 (Strike at 0.5 m/s into a
   still Guard; Guard pushing back at 0.33 m/s; closest approach 1.100 m) become named tests with stated tolerances.
6. Commands (this worktree, either machine):
   ```bash
   unset PYTHONPATH
   CUDA_VISIBLE_DEVICES="" PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python -m pytest -q -p no:cacheprovider tests/test_<area>.py
   ```
   During the loop, run the touched test files; before hand-over or merge, the full suite (1,383 tests collected on 20 Nov 2026 after L0.7; 1,243 on
   20 Nov 2026 after L0.1; about 19 minutes on the home RTX 5090 with the GPU hidden), quoting the last line. A skip is not a pass.

## 3. Vectorisation (STANDARDS §6.1)

- Everything in a training or evaluation step is a tensor operation over all games: no Python loop over games or
  drones, no `.cpu()`, `.item()`, `.tolist()` or NumPy in the step. Allowed loops: fixed counts (physics sub-steps,
  filter sweeps, PPO epochs, time steps of a rollout, members of a pool when stacking them once).
- One host sync is allowed per step only where it already exists (the filter's `check_every` early stop) and is
  recorded in the run.
- Variable team size and drone loss are **masks**, never ragged lists: tensors stay `[N, M_pad, ...]` with
  `alive`/`present` `[N, M_pad]` bool. Masked rows are zeroed and excluded from losses, attention and the filter.

## 4. Configuration, no magic numbers

- Values that could change a result live in TOML (`configs/ste_*.toml`, `params/*.toml`), loaded into frozen
  dataclasses that **raise on unknown keys** (as `core/game_config.py`). Never YAML.
- Each value carries its status label (FIXED, MEASURED, PROPOSED, OPEN) and source in a comment. The tag radius 1.6 m
  and filter option B are PROPOSED (P1, P2): they ship as settings, default off, until the owner rules; they contradict
  two FIXED rows of STANDARDS §4 and must not be presented as settled.
- Code holds no tuned numbers; named physical or structural constants (`G_MPS2`, `SLOT`) are fine. G2 (only 0, 1, −1, 2
  as literals, `tests/test_nus_rules_privacy.py`) binds `nus/` only; the track's package has its own literal-scan test, `tests/test_ste_literals.py` (L0.1; rule set by
  the lead, 20 Nov 2026): in `source/svg_training/ste/`, a numeric literal other than 0, 1, −1, 2 is allowed only on the
  right-hand side of a module-level assignment to an UPPER_CASE name; anywhere else the test fails with file and line.
  As built (L0.1): the sign is an operator, as in G2, so −2 passes and −0.5 fails; 0.0, 1.0 and 2.0 pass; a leading
  underscore counts as UPPER_CASE (`_SLOT = 7`) and so does an annotated assignment; any expression on the right-hand
  side fails (`RATE = 0.3 * 2`); a numeric dataclass default fails, so the package's dataclasses carry no defaults and
  every number comes from TOML.
- A drone-model parameter set is a new versioned file (for example `params/starling_physics_v1.toml`); `v0` is never
  edited. Parameters flow from the drone to the trainer, never back (iron rule 9). Training uses sets fitted to real
  logs (STANDARDS §5 rule 10); a set fitted to the AirStack simulator describes that simulator only.
- A run records the config path, its sha256 and the values used.

## 5. Determinism and seeds

- Every random draw takes an explicit `torch.Generator`, one per purpose (game starts, actions, drone loss,
  noise, matchmaking), derived from the run seed and a stream number (the `stage_generator` pattern in `nus/mappo.py`).
  No global `torch.manual_seed` reliance; nothing in the physics layer draws from the game's generator (S2b D15).
- On CPU, same seed ⇒ same tensors bit for bit (tested). On CUDA, state a tolerance; never claim bit-identity.
- Seeds are fixed and recorded; a claim that one method beats another needs at least 3 seeds (STANDARDS §6.5).

## 6. Shapes, units, frames

- Shapes in every public docstring: `N` games, `M` drones per game (Guard drones first, `0..G-1`, then Strike drones),
  `P` pairs, `T` steps, `D` observation width, `E` entity slots. Vectors `[N, M, 3]`, masks `[N, M]` bool.
- SI units in names: `_m`, `_mps`, `_mps2`, `_s`, `_rad`, `_n`. Policy output is unitless in `[-1, 1]` and scaled by the
  team speed before the filter (STANDARDS §4).
- Frames: world ENU, body FLU, quaternions WXYZ body → world everywhere outside the cascade; PX4 NED/FRD only inside
  `models/px4_cascade.py`, crossed only in `models/frames.py`. Isaac-version calls only in `compat/`.
- Interface changes (layout, scaling, entity lists for the attention encoder) raise the interface version and need the
  owner (STANDARDS §3 rule 3).

## 7. Logging and metrics

- One metrics module serves curves, evaluation and records (STANDARDS §7.2): the numbers gated are the numbers plotted.
- Per update, one JSON line in `runs/<date>_<name>/train_log.jsonl`; TensorBoard as in `configs/s2b.toml
  [tensorboard]`; GPU-hours appended to the stage's log.
- Always log: game-steps/s with games, drones per game, tier and GPU; filter intervention rate and size (STANDARDS
  §6.2); tags, reaches, drone losses; non-finite counts; pool mix.
- Videos in every run (STANDARDS §8).

## 8. Error handling

- Fail closed and early: a config error, a missing or unfrozen gates file, or a busy GPU (`isaac_preflight.sh` exit 11)
  refuses to start, with a message, before Isaac launches.
- A non-finite metric aborts the update with a checkpoint kept (`NonFiniteError` pattern); non-finite physics values are
  replaced and **counted**, never silently hidden.
- Exit codes (`ste/run_contract.py`, L0.7): 0 done, 2 refused, 3 cap (ABORTED), 4 interrupted (STOPPED), 5 non-finite.
  The older `train_standin.py` uses 3 for a NaN abort; this track uses 5. Launch, wait and status go through
  `scripts/ste_job.py` ([AUTOMATION](AUTOMATION.md) §7); never find a process by name (`pgrep`, `pkill`: a test fails).
- No bare `except`.

## 9. Performance budgets (PROPOSED)

| Item | Budget |
|---|---|
| A single unit test | ≤ 5 s on CPU; a new test file ≤ 30 s |
| A new step feature (tag, option B, delay, noise, drag) | ≤ 10 % throughput loss at 4,096 games against the same build with it off, measured, not estimated |
| Off-setting overhead | none measurable (same code path) |
| Host syncs per step | none new |
| Learner forward per decision, deployment | well under 1 ms per drone on the laptop CPU (DISCUSSION §2.10; to be measured at export) |

## 10. Review checklist (before hand-over)

- [ ] Paths inside `svg_training/`; `git status` shows only my files; no YAML/launch/Docker path.
- [ ] Failing test written first; targeted tests and the full suite pass, output quoted.
- [ ] Off-setting bit-identity test present for every new behaviour.
- [ ] No loop over games, no host read in the step; masks for absent drones.
- [ ] No magic numbers; new values labelled with source; new param sets versioned.
- [ ] Shapes, units, frames in docstrings and names.
- [ ] Seeds explicit; CPU determinism test.
- [ ] Wording per STANDARDS §2 (Strike team, Guard team, tag, reach; "observed in the training simulator").
- [ ] No NUS source code copied; NUS values only from `configs/local/`. New learner code lives outside `nus/`.
- [ ] HANDOFF and the track's status updated.

## 11. Commits

The lead commits, on the task's branch, staging by explicit path. Subject: `svg_training <area>: <what>`,
plain words; body wrapped at about 90 columns saying why and what was checked, with test counts; T or W numbers when a
record exists. End with:

the `Co-Authored-By:` trailer the session gives for its model (it changes with the model; never copy an old one).

A new file under `.claude/` needs `git add -f <path>`.

## 12. Never

- Edit outside `svg_training/` (AirStack, tools, IsaacLab, drone parameters, the sim airframe).
- `git push`, `git add -A`, `git commit -a`, `git stash`, `git reset --hard`, `git checkout -- <file>`, `git clean`,
  `--no-verify`.
- Commit or paste NUS's source code; hard-code a NUS value.
- Move or edit a `gates.toml` after the first result; call a training result "validated".
- Start a GPU job while the AirStack simulator or a flight session is up, or without headless mode.
- Run `tools/sim.sh` for anything but the approved velocity-step logs.
