INTERNAL · DRAFT plan for a third route of the STE learning track, the learned-skills route: the hand-written skills and team strategies are copied into one network per team, then trained, then extended with skills no script contains; stage LS1 is planned task by task, stages LS2 to LS4 as gated outlines · the route is adopted (owner, 25 Nov 2026, R35); its budget and order are not ruled; nothing is built or run · the route explained for any reader: [../LEARNED_SKILLS_ROUTE.md](../LEARNED_SKILLS_ROUTE.md) · parent notes: [L3_TWO_ROUTES_DESIGN.md](L3_TWO_ROUTES_DESIGN.md), [../PLAN.md](../PLAN.md)

# Learned-skills route ("the bridge"): execution plan (draft, 25 Nov 2026)

Written 25 Nov 2026 by the lead (a Fable 5.2 session; the advisor tool was not available, so no second opinion yet).
Not reviewed. Before any code: the owner's answers to 9.2 and 9.3 (given 25 Nov 2026, R36 and R37), then a design
review by two reviewers (R22). **Corrections found against the code on 25 Nov 2026 and the changes of R39 to R41 (no cap, the heads trained on the
skill network, self-play before LS3) are in [LS_EXECUTION_WORKFLOW.md](LS_EXECUTION_WORKFLOW.md) (its section 8) and
take precedence over this file where they differ**
(the budget table, the cell count of section 8, the device of the equivalence read, the per-team skill network file,
the noise-floor read, the clips).

> **DO NOT BUILD FROM THE TASKS BELOW AS WRITTEN (25 Nov 2026).** They are older than the design review. Built as
> written, Task 2 breaks the load of every existing checkpoint and export (it adds a key to the scripts' dictionary),
> Task 1 uses a tanh output, Task 4 types the limits into a test (the owner sets them, R38), and nothing here covers
> the training driver's control, the cell module, the calibration read, the reload branch or the LS1.4 reader. The
> source for a build is [LS_EXECUTION_WORKFLOW.md](LS_EXECUTION_WORKFLOW.md) v3 with the two review reports
> ([A](LS_DESIGN_REVIEW_A.md), [B](LS_DESIGN_REVIEW_B.md)); the first step after the owner's word is a task plan
> rewritten from them, read by one reviewer. This file is kept for the design (sections 1 to 4) and the history.
>
> **For the builder (`ste-software-engineer`, in its own worktree cut from `development`):** stage LS1 below is
> task by task, tests first, steps as checkboxes. It follows [PLAN §6](../PLAN.md) (design check, develop, gate
> written, test run, validate, QC, document, merge) and [STANDARDS §3](../STANDARDS.md). Independent QC by
> `ste-test-qc-engineer`. LS2 to LS4 get their own task plans when the gate before them has been read.

**Goal.** Drone teams that learn their own individual skills and their own team strategy, reached in four gated
stages that each start from the behaviour of the stage before, so no stage starts from random flight.

**Architecture.** Today's skills route keeps its two choice heads (`ste/two_level.py`, R30) and replaces what they
choose among: the K scripts of a team become one network `π(command | observation, drone slot, skill code z)`.
LS1 fits that network to the scripts (supervised, with on-policy relabelling). LS2 trains it with the game reward
while a penalty keeps each code near its script. LS3 adds codes with no script. LS4 lets the team level give out
codes freely, in league self-play.

**Tech stack.** PyTorch, the STE game engine (tier 1), skrl 2.1.0 (unchanged), ONNX opset 17 for export.

**Spec.** This file (sections 1 to 4 are the design, 5 to 8 the plan). It builds on
[L3_TWO_ROUTES_DESIGN.md](L3_TWO_ROUTES_DESIGN.md) v2 and `L3_SLICE2_DESIGN.md` (R30).

## Global constraints

- Write only inside `svg_training/`. Commits on a topic branch, explicit paths, ff-only into `development`; never push.
- **Off means identical** (STANDARDS §3.1): every new setting defaults to today's behaviour bit for bit; the equality
  test is written first. `[learner] skill_source` defaults to `"scripts"`.
- Gates are written and hashed before a run and never edited after. Positive controls PASS and negative controls FAIL
  before a result is read.
- No per-game Python loops in anything that runs during training or data collection.
- Observation stays v0.1 (`OBS_DIM = 71`, `core/observations.py:19`); the drone slot and the skill code are network
  inputs built beside the observation, not new observation fields.
- Skill lists unchanged (R26, list A): Guard `guard_parked_centre, guard_mark_edge, guard_mirror, guard_parked_ring,
  guard_field`; Strike `strike_straight, strike_flank, strike_high, strike_low, strike_sacrifice, strike_converge`,
  in the `[players]` order of `configs/ste_l3/skills_gates.toml`.
- Team size 3v3 only in LS1 (the trained size, G0 ruling R6–8).
- Every training run saves videos (parent STANDARDS §8). Results are "observed in the training simulator".
- Test command, from `svg_training/`:
  `unset PYTHONPATH; CUDA_VISIBLE_DEVICES="" PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python -m pytest -q -p no:cacheprovider <file>`

## Review focus

Inputs the design implies that are most likely to bite, each pinned by a test in the task that owns the code:

1. **A team size other than 3.** The scripts branch on team size (`obs.shape[1]`: `scripted.py` parked ring, converge,
   sacrifice); the network has only seen 3v3. Expected: a net-backed dispatch refuses any other size (Task 2).
2. **A drone that is out.** Its observation is all zeros except the team value (`core/observations.py:87-88`).
   Expected: its command is exactly zero, as `_pack` gives for the scripts (Task 1).
3. **A checkpoint whose skill list or order differs from the gate file's.** Expected: refused at load, naming both
   lists (Task 2).
4. **`opponents/scripted.py` edited after the network was fitted.** The teacher changed; the copy is stale. Expected:
   refused at load on a sha256 mismatch unless the gate file names the new hash (Task 2).
5. **Switch points inside a script** (sacrifice "circle or fly in", converge's run-in). A mean error hides a large
   error at the switch. Expected: the fit report carries the per-skill 99th-percentile error, and the gate reads the
   games, not only the error (Tasks 3 and 5).

---

## 1. What the code allows today (checked 25 Nov 2026)

| Fact | Where | Consequence |
|---|---|---|
| Every script is a stateless function of the team's observation tensor `[N, M, 71] -> [N, M, 4]`; `reset` does nothing | `opponents/scripted.py:45-63` | a network can copy a script; no hidden memory to reproduce |
| A script learns which drone it is from the tensor axis, never from the 71 numbers (`torch.arange(obs.shape[1])`) | `scripted.py:97, 318, 390, 419` | one shared network needs the **drone slot as an extra input**; the observation alone cannot tell Strike 0 (the decoy) from Strike 1 |
| The dispatch runs all K scripts every tick and gathers the chosen one | `ste/skills.py:153-161` (`SkillDispatch.commands`, `.act`) | replacing `commands` replaces the scripts everywhere: training (`DecisionEnv`), scoring (`HeldPlayer`, `SkillTeam`), tier 2 |
| Every driver builds its dispatch through one factory, `skills.two_level_dispatch` (12 call sites: the trainer, the L3 and L4 scoring scripts, the clips, the tier-2 smoke, the export) | `grep two_level_dispatch source scripts`, 25 Nov 2026 | one change in the factory reaches all of them; the one direct construction is the export's reload check (`ste/export.py:302`, Task 6) |
| The choice is held 12 ticks (0.6 s); the chosen skill's command is recomputed every tick | `exploit_train.py:93-155` | the skill network runs at 20 Hz, the heads at 1.67 Hz: two rates |
| The replay tests ask for games equal bit for bit | `tests/test_ste_l3_two_level.py:311-338`, `exploit.EXACT` | a network cannot pass them; LS1 needs an equivalence gate with a stated tolerance |
| The opponent pool holds scripts only; there is no league of past checkpoints yet | `ste/pool.py:89` | self-play (LS4) waits for the league of the learner v2 note |
| Flying the skills route needs the scripts ported into the game node at 20 Hz, an AirStack change (L7) | L3 design note v2, "Export (B3)" | a distilled team is two ONNX graphs and no script port: a simpler hand-over |

## 2. The four stages

| Stage | What is learned | What stays hand-written | Starts from | Gate, in one line |
|---|---|---|---|---|
| **LS1 Distil** | a copy of every script, as codes of one network per team | the scripts (as teachers) | the scripts | the copy plays like the scripts, cell by cell |
| **LS2 Fine-tune** | the heads' choices and the skills themselves | a penalty that ties each code to its script, weakened step by step | LS1's network and today's heads | above the best fixed mix of scripts, each code still told apart |
| **LS3 Free codes** | skills no script contains | nothing for the new codes | LS2 | the new codes are chosen and raise the worst cell |
| **LS4 Team strategy in a league** | which codes the team gives to which drone, against past and present opponents | nothing | LS3 and the learner v2 league | holds against saved exploits and held-out scripts |

Stopping after any stage leaves a usable result: LS1 alone gives a skills team that exports without a script port.

## 3. Design of the skill network (LS1)

- **One network per team**, shared by its drones: `SkillNet(obs [B, 71], slot [B], z [B]) -> command [B, 4]` in
  [-1, 1]. `slot` is the drone's index in its own team (one-hot over the team's pad: 5 for Guard, 3 for Strike);
  `z` is the skill code (one-hot over the team's K players, in `[players]` order). Team strategies and drone skills
  are both codes: each is a per-drone function of the observation, and coordination comes from every drone flying
  the same code while seeing its team-mates.
- **Body**: MLP, ELU, hidden `[256, 256, 256]` (PROPOSED; larger than the heads' `[128, 128]` because of the
  scripts' switch points), tanh output. Input normalisation is stored in the network as buffers, fitted on the
  data, so the export needs no separate scaler. The architecture is a parameter of the fit: when learner v2
  changes the encoder, LS1 is run again on it in minutes.
- **Data**: games on tier 1 against the opponent pool (every script of the other team). The team flies a random
  two-level choice, redrawn every 12 ticks (team head uniform over free and the team strategies; drone heads
  uniform). At every tick every script is asked for its command, so one state gives K labels. Rows of drones that
  are out are dropped.
- **On-policy relabelling (DAgger)**: round 0 flies the scripts' commands. In later rounds a share of the games
  flies the network's own commands; the states they reach are labelled by the scripts and added. Without this the
  copy is only right on states the scripts visit. PROPOSED: 4 rounds, the script-flown share 1, 0.5, 0.25, 0.
- **Loss**: mean squared error over the 4 command channels, all K codes, live drones.
- **Plug-in**: a `TwoLevelDispatch` whose `commands(obs)` comes from the network. Setting
  `[learner] skill_source = "net"`, `skill_net = "<path>"`; default `"scripts"`.

## 4. The LS1 gate (equivalence, written before the run)

Bit-for-bit equality is replaced by three reads, all on T44's starts (`configs/ste_l012/t44_reference.npz`), base
variant, 3v3. Limits are PROPOSED by the lead and fixed in `configs/ste_ls1/distil_gates.toml` before any run.

| Read | Measured | Limit (PROPOSED) |
|---|---|---|
| Command error | per skill, RMSE between network and script commands on held-out states from a network-flown round; the 99th percentile reported beside it | RMSE <= 0.05 for every skill (command units, range -1 to 1) |
| Fixed-choice cells | the team flying one code on every drone (Guard 5 codes, Strike 6) against each script of the other team, first 1,000 starts: wins of the network team against wins of the script team, same starts | every cell within 30 wins of 1,000; the pooled row within 15 |
| Mixed cells | 20 seeded "free" combinations (a different drone skill per drone) against each opponent script, against the same combination flown by scripts (the `Composite` player of `scripts/ste_l3_run0_ceiling.py:232`) | as above |

Controls: **positive**, the script-backed dispatch through the same scoring path differs in 0 games from T44;
**negative 1**, an unfitted network must miss the cell limit; **negative 2**, the fitted network with its codes
permuted must miss it (the code decides the behaviour). Verdict words: DISTILLED, NOT DISTILLED, INCONCLUSIVE
(a control failed). One seed; labelled a pipeline check, not for flight.

## 5. File structure (LS1)

| File | Responsibility |
|---|---|
| Create `source/svg_training/ste/skill_net.py` | the network, its save and load with the refusals, the net-backed dispatch |
| Create `source/svg_training/ste/distil.py` | data collection, the fit, the DAgger loop, the fit report |
| Modify `source/svg_training/ste/skills.py` | `[learner] skill_source`, `skill_net` in `learner_spec` and `LearnerSpec`; `two_level_dispatch` returns the net-backed dispatch when asked |
| Create `configs/ste_ls1/distil_gates.toml` | game file reference, data sizes, rounds, limits, controls, `[run] task` |
| Create `scripts/ste_ls1_distil.py` | driver under the run contract (`ste/run_contract.RunGuard`), launched with `scripts/ste_job.py` |
| Create `scripts/ste_ls1_equivalence.py` | the three reads of section 4, controls first, `results.json` and the verdict |
| Modify `source/svg_training/ste/export.py`, `scripts/ste_l6_export.py` | export and reload check of a net-backed skills team |
| Create `tests/test_ste_ls1_skill_net.py`, `test_ste_ls1_dispatch.py`, `test_ste_ls1_distil.py`, `test_ste_ls1_equivalence.py`, `test_ste_ls1_export.py` | one test file per task |
| Modify `configs/ste_learning.toml` | the LS1 task caps, only after the owner's answer to 9.2 |

## 6. Stage LS1, task by task

### Task 1: The skill network

**Files:** create `source/svg_training/ste/skill_net.py`, `tests/test_ste_ls1_skill_net.py`.

**Interfaces.**
- Consumes: `core.observations.OBS_DIM`, `ObsView.alive`.
- Produces:
  - `class SkillNet(torch.nn.Module)`: `__init__(self, obs_dim: int, slots: int, k: int, hidden: list[int])`;
    `forward(self, obs: Tensor, slot: Tensor, z: Tensor) -> Tensor` with obs `[B, obs_dim]`, slot and z `[B]` long,
    result `[B, 4]` in [-1, 1]; buffers `in_mean`, `in_std` `[obs_dim]` (identity until `set_normaliser`);
    `set_normaliser(self, mean: Tensor, std: Tensor) -> None`.
  - `all_codes(net: SkillNet, obs: Tensor) -> Tensor`: obs `[N, M, D]` -> `[N, M, K, 4]`; slot = the drone's
    index on axis 1; multiplied by the alive flag, so a drone that is out gets zeros.

- [ ] **Step 1: write the failing tests**

```python
def test_shapes_and_range():
    net = SkillNet(71, slots=3, k=6, hidden=[16])
    out = net(torch.randn(10, 71), torch.zeros(10, dtype=torch.long), torch.arange(10) % 6)
    assert out.shape == (10, 4) and out.abs().max() <= 1.0

def test_all_codes_shape_and_dead_drone_is_zero():
    net = SkillNet(71, slots=3, k=6, hidden=[16])
    obs = torch.randn(4, 3, 71); obs[..., ObsView.alive] = 1.0
    obs[0, 1] = 0.0                                   # drone 1 of game 0 is out
    out = all_codes(net, obs)
    assert out.shape == (4, 3, 6, 4)
    assert torch.equal(out[0, 1], torch.zeros(6, 4))

def test_slot_and_code_change_the_output():
    net = SkillNet(71, slots=3, k=6, hidden=[16]); o = torch.randn(1, 71)
    a = net(o, torch.tensor([0]), torch.tensor([0]))
    assert not torch.equal(a, net(o, torch.tensor([1]), torch.tensor([0])))
    assert not torch.equal(a, net(o, torch.tensor([0]), torch.tensor([1])))

def test_normaliser_is_identity_by_default_and_applied_when_set():
    net = SkillNet(71, 3, 6, [16]); o = torch.randn(5, 71); s = torch.zeros(5, dtype=torch.long)
    before = net(o, s, s)
    net.set_normaliser(torch.ones(71), torch.full((71,), 2.0))
    assert torch.allclose(net((o * 2.0) + 1.0, s, s), before, atol=1e-6)
```

- [ ] **Step 2: run them; expected: FAIL, `skill_net` not found**
- [ ] **Step 3: implement `SkillNet` and `all_codes`** (MLP with ELU as `opponents/learned._mlp`, tanh output; the
  input is `[(obs - in_mean) / in_std, one_hot(slot), one_hot(z)]`)
- [ ] **Step 4: run them; expected: 4 passed**
- [ ] **Step 5: commit** (`svg_training: LS1 skill network`)

### Task 2: Save, load and the net-backed dispatch

**Files:** modify `source/svg_training/ste/skill_net.py`, `source/svg_training/ste/skills.py`; create
`tests/test_ste_ls1_dispatch.py`.

**Interfaces.**
- Consumes: Task 1; `skills.TwoLevelDispatch`, `skills.learner_spec`, `skills.LearnerSpec`, `skills.two_level_dispatch`.
- Produces:
  - `save_skill_net(path, net: SkillNet, meta: dict) -> None`; `load_skill_net(path, device, *, players: list[str],
    team: str, team_size: int, scripted_sha256: str | None = None) -> SkillNet`. `meta` keys: `team`, `players`
    (ordered), `team_size`, `obs_interface` ("0.1"), `hidden`, `scripted_sha256`. `load_skill_net` raises
    `ValueError` naming both values when team, players (names or order) or team size differ, and when the sha256
    of `opponents/scripted.py` differs from the stored one unless `scripted_sha256` names the current file's.
  - `class NetTwoLevelDispatch(TwoLevelDispatch)`: same constructor plus `net: SkillNet`; `commands(obs)` returns
    `all_codes(net, obs)`; `script_commands(obs)` returns the scripts' (the parent's `commands`), kept for LS2's
    penalty; `act(obs, choice)` runs the network once on the chosen code only (`[N, M]` rows, not all K), equal
    to the gather over `commands`; raises `ValueError` when `obs.shape[1]` is not the stored team size.
  - `skills.skills_meta(dispatch)` gains `skill_source` and, for a net-backed dispatch, the sha256 of the skill
    network file, so a heads checkpoint trained on one skill source is refused on another
    (`exploit_train.py:455`). For a script-backed dispatch the dictionary is unchanged apart from
    `"skill_source": "scripts"`; checkpoints saved before this change load as `"scripts"`.
  - `LearnerSpec.skill_source: str = "scripts"`, `LearnerSpec.skill_net: str | None = None`; `learner_spec`
    accepts the two keys for `choice = "two_level"` only, refuses `skill_source = "net"` without `skill_net`.
  - `two_level_dispatch(...)` returns a `NetTwoLevelDispatch` when `spec.skill_source == "net"`.

- [ ] **Step 1: write the failing tests**

```python
def test_default_spec_is_scripts_and_dispatch_unchanged(gates):       # off means identical
    spec = skills.learner_spec(dict(gates.learner_table))
    assert spec.skill_source == "scripts" and spec.skill_net is None
    d = skills.two_level_dispatch(spec, gates.players, "strike", cfg, 4, "cpu", 0)
    assert type(d) is skills.TwoLevelDispatch

def test_net_source_needs_a_path():
    with pytest.raises(ValueError, match="skill_net"):
        skills.learner_spec({**TWO_LEVEL_TABLE, "skill_source": "net"})

def test_round_trip_and_refusals(tmp_path):
    net = SkillNet(71, 3, 6, [16]); meta = META_STRIKE                # players in [players] order, team_size 3
    save_skill_net(tmp_path / "s.pt", net, meta)
    again = load_skill_net(tmp_path / "s.pt", "cpu", players=meta["players"], team="strike", team_size=3)
    assert torch.equal(again(O, S, Z), net(O, S, Z))
    for bad in (dict(players=meta["players"][::-1]), dict(team="guard"), dict(team_size=5)):
        with pytest.raises(ValueError):
            load_skill_net(tmp_path / "s.pt", "cpu", **{**GOOD, **bad})

def test_stale_teacher_is_refused(tmp_path):
    save_skill_net(tmp_path / "s.pt", SkillNet(71, 3, 6, [16]), {**META_STRIKE, "scripted_sha256": "0" * 64})
    with pytest.raises(ValueError, match="scripted.py"):
        load_skill_net(tmp_path / "s.pt", "cpu", **GOOD)

def test_net_dispatch_gathers_the_chosen_code_and_refuses_other_sizes():
    d = NetTwoLevelDispatch(..., net=net)                             # 3 Strike drones
    obs = live_obs(n=4, m=3); choice = torch.tensor([[0, 1, 2]] * 4)
    assert torch.equal(d.act(obs, choice), torch.gather(all_codes(net, obs), 2, IDX(choice))[:, :, 0])
    with pytest.raises(ValueError, match="team size"):
        d.commands(live_obs(n=4, m=2))
```

- [ ] **Step 2: run them; expected: FAIL**
- [ ] **Step 3: implement** (the file is written through `ste/atomic.py`; the sha256 is of the file's bytes)
- [ ] **Step 4: run them and `tests/test_ste_l3_skills.py`, `test_ste_l3_two_level.py`; expected: all pass**
- [ ] **Step 5: commit** (`svg_training: LS1 net-backed dispatch behind [learner] skill_source`)

### Task 3: Data collection, fit and DAgger

**Files:** create `source/svg_training/ste/distil.py`, `tests/test_ste_ls1_distil.py`.

**Interfaces.**
- Consumes: Tasks 1–2; `exploit_train.TrainGame`, `pool.OpponentPool`, `skills.TwoLevelDispatch`.
- Produces:
  - `collect(game, team: str, dispatch: TwoLevelDispatch, opponent, net: SkillNet | None, script_share: float,
    ticks: int, hold: int, seed: int) -> dict` with `obs [T, D]`, `slot [T]` long, `label [T, K, 4]`, live rows
    only. Per game, for the whole call, the team flies the scripts' commands with probability `script_share`,
    else the network's; the two-level choice is redrawn uniformly every `hold` ticks. `net=None` needs
    `script_share == 1.0`.
  - `fit(net, data: dict, epochs: int, lr: float, batch: int, seed: int) -> dict` (sets the normaliser from
    `data["obs"]`, then minimises the mean squared error over all K codes); returns `{"rmse": [K], "p99": [K]}`.
  - `evaluate(net, data) -> dict` (the same report, no training).
  - `dagger(game, team, dispatch, opponent, net, rounds: list[float], ticks, hold, keep_rows: int, fit_kw: dict,
    seed) -> dict` (round r collects with `script_share = rounds[r]`, keeps at most `keep_rows` rows per round by
    seeded subsampling, fits on all rounds so far; returns the per-round reports).

- [ ] **Step 1: write the failing tests** (CPU, 16 games, hidden `[64, 64]`)

```python
def test_labels_are_every_scripts_command_on_that_state(strike_setup):
    data = distil.collect(game, "strike", disp, pool, None, 1.0, ticks=24, hold=12, seed=0)
    assert data["label"].shape[1:] == (6, 4) and data["obs"].shape[1] == 71
    k = 3; rows = slice(0, 50)
    assert torch.allclose(data["label"][rows, k], relabel_one_script(disp, data, k)[rows])   # helper replays script k

def test_no_rows_from_drones_that_are_out(strike_setup):
    data = distil.collect(game, "strike", disp, pool, None, 1.0, ticks=120, hold=12, seed=0)
    assert (data["obs"][:, ObsView.alive] > 0.5).all()

def test_fit_lowers_the_error_and_reports_per_skill(strike_setup):
    data = distil.collect(game, "strike", disp, pool, None, 1.0, ticks=120, hold=12, seed=0)
    net = SkillNet(71, 3, 6, [64, 64]); before = distil.evaluate(net, data)["rmse"]
    rep = distil.fit(net, data, epochs=30, lr=1e-3, batch=1024, seed=0)
    assert len(rep["rmse"]) == 6 and len(rep["p99"]) == 6
    assert (torch.tensor(rep["rmse"]) < 0.5 * torch.tensor(before)).all()

def test_net_flown_games_visit_other_states_and_are_script_labelled(strike_setup):
    a = distil.collect(game, "strike", disp, pool, net, 1.0, ticks=60, hold=12, seed=1)
    b = distil.collect(game, "strike", disp, pool, net, 0.0, ticks=60, hold=12, seed=1)
    assert not torch.equal(a["obs"][:100], b["obs"][:100])
    assert torch.allclose(b["label"][:50, 0], relabel_one_script(disp, b, 0)[:50])

def test_same_seed_same_data(strike_setup):
    assert torch.equal(collect_again(seed=7)["obs"], collect_again(seed=7)["obs"])
```

- [ ] **Step 2: run them; expected: FAIL**
- [ ] **Step 3: implement** (tensor operations over all games; the tick loop is the one allowed fixed loop)
- [ ] **Step 4: run them; expected: 5 passed**
- [ ] **Step 5: commit** (`svg_training: LS1 distillation data, fit and DAgger`)

### Task 4: The gate file and the distillation driver

**Files:** create `configs/ste_ls1/distil_gates.toml`, `scripts/ste_ls1_distil.py`; extend
`tests/test_ste_ls1_distil.py`; modify `configs/ste_learning.toml` (after 9.2).

**Interfaces.**
- Consumes: Task 3; `run_contract.RunGuard`, `budget.check_launch`, the game and `[players]` of
  `configs/ste_l3/skills_gates.toml` (referenced by path and sha256, not copied).
- Produces: `scripts/ste_ls1_distil.py --gates <file> --side guard|strike --run-dir <dir> --cap-h <h>
  --expect-gates-sha256 <hash>`; in the run folder `skill_net_<side>.pt`, `fit_report.json` (per round, per
  skill: rmse, p99), `progress.json`, videos of 4 network-flown games. Exit codes as the run contract (0 done,
  2 refused, 3 cap, 4 interrupted, 5 non-finite). The same command resumes at the last finished round.

**Gate file values (all PROPOSED until hashed):** `games = 4096`; `ticks_per_round = 600`; `hold = 12`;
`rounds = [1.0, 0.5, 0.25, 0.0]`; `keep_rows = 2_000_000`; `hidden = [256, 256, 256]`; `epochs = 40`;
`lr = 1e-3`; `batch = 8192`; `seed = 150001`; `[limits] rmse_max = 0.05`, `cell_wins_max_diff = 30`,
`pooled_wins_max_diff = 15`, `games_per_cell = 1000`, `mixed_combinations = 20`; `[run] task = "LS1.1"`.

- [ ] **Step 1: write the failing tests**: the gate file loads and its limits equal the table of section 4; the
  driver refuses a gate file whose sha256 differs from `--expect-gates-sha256` (exit 2); a 2-round CPU smoke
  (16 games, 24 ticks) writes the three files and exits 0; the same command run again exits 0 without refitting
  (resume); a run stopped after round 0 resumes at round 1.
- [ ] **Step 2: run them; expected: FAIL**
- [ ] **Step 3: implement the gate file and the driver**
- [ ] **Step 4: run them; expected: pass**
- [ ] **Step 5: commit** (`svg_training: LS1 gate file and distillation driver`)

### Task 5: The equivalence read

**Files:** create `scripts/ste_ls1_equivalence.py`, `tests/test_ste_ls1_equivalence.py`.

**Interfaces.**
- Consumes: Tasks 2 and 4; `exploit.play_cells(..., players=...)`, `exploit.load_reference`, `exploit.agreement`,
  `scoring.win_count`, `scoring.pooled_row`; the `Composite` player pattern of `scripts/ste_l3_run0_ceiling.py:232`.
- Produces: `--gates --side --skill-net <file> --run-dir`; `controls.json`, `results.json` (per cell: script wins,
  network wins, difference; the pooled row; the command-error table), `results.md`, and one verdict word on the
  last line of stdout: `DISTILLED`, `NOT DISTILLED` or `INCONCLUSIVE`.
  `verdict(controls: dict, cells: list[dict], pooled: dict, errors: dict, limits: dict) -> str` is importable.

- [ ] **Step 1: write the failing tests**

```python
def test_verdict_reads_controls_first():
    assert verdict(BAD_POSITIVE, GOOD_CELLS, GOOD_POOLED, GOOD_ERR, LIMITS) == "INCONCLUSIVE"
    assert verdict(NEGATIVE_PASSED, GOOD_CELLS, GOOD_POOLED, GOOD_ERR, LIMITS) == "INCONCLUSIVE"

def test_verdict_limits():
    assert verdict(GOOD_CONTROLS, GOOD_CELLS, GOOD_POOLED, GOOD_ERR, LIMITS) == "DISTILLED"
    one_off = [*GOOD_CELLS[:-1], {**GOOD_CELLS[-1], "diff": 31}]
    assert verdict(GOOD_CONTROLS, one_off, GOOD_POOLED, GOOD_ERR, LIMITS) == "NOT DISTILLED"
    assert verdict(GOOD_CONTROLS, GOOD_CELLS, {"diff": 16}, GOOD_ERR, LIMITS) == "NOT DISTILLED"
    assert verdict(GOOD_CONTROLS, GOOD_CELLS, GOOD_POOLED, {"rmse": [0.06] * 6}, LIMITS) == "NOT DISTILLED"

def test_script_backed_team_differs_in_zero_games(gates, ref):        # the positive control, 24 starts
    assert positive_control(gates, ref, "strike", n=24)["differ"] == 0

def test_unfitted_and_permuted_networks_miss_the_limit(gates, ref, fitted_small_net):
    assert negative_control(unfitted, n=200)["max_diff"] > scaled_limit(200)
    assert negative_control(permute_codes(fitted_small_net), n=200)["max_diff"] > scaled_limit(200)
```

- [ ] **Step 2: run them; expected: FAIL**
- [ ] **Step 3: implement** (cells and mixed combinations drawn from the gate file's seed; controls run and are
  written before any result cell is played)
- [ ] **Step 4: run them; expected: pass**
- [ ] **Step 5: commit** (`svg_training: LS1 equivalence read with controls`)

### Task 6: Export and reload of a net-backed team

**Files:** modify `source/svg_training/ste/export.py`, `scripts/ste_l6_export.py`; create
`tests/test_ste_ls1_export.py`.

**Interfaces.**
- Consumes: Task 2; `export.export_policy`, `export.reload_check`, `export.GOLDEN_ATOL`.
- Produces: `export_skill_net(net_file, gates, side, out_dir, obs) -> dict` writing `skills_<side>.onnx`
  (inputs `obs [B, 71]`, `slot [B]` int64, `z [B]` int64; output `command [B, 4]`; opset 17; the normaliser is
  inside the graph), golden rows (obs, slot, z, command) and an `interface.toml` entry with schema
  `ste-check-skillnet-0`, the ordered skill list, team size 3, the hold rule (choice every 12 ticks, command
  every tick), the sha256 of each file, and the status "pipeline check, not for flight". `reload_check` covers
  the new file in a fresh process.

- [ ] **Step 1: write the failing tests**: the exported graph matches the torch network on 64 golden rows within
  `GOLDEN_ATOL`; `reload_check` passes on the folder and fails when one byte of the ONNX file is changed; the
  interface entry names the 6 (Strike) or 5 (Guard) skills in `[players]` order.
- [ ] **Step 2: run them; expected: FAIL**
- [ ] **Step 3: implement**
- [ ] **Step 4: run them and `tests/test_ste_l3_export.py`; expected: pass**
- [ ] **Step 5: commit** (`svg_training: LS1 export of the skill network`)

### Task 7: The runs and the record

- [ ] The lead writes and hashes `configs/ste_ls1/distil_gates.toml`; `ste-test-qc-engineer` reviews the limits.
- [ ] Launch per side with `scripts/ste_job.py launch --task LS1.1 ...` (Guard, then Strike), then
  `ste_ls1_equivalence.py` per side (task LS1.2), then the export (LS1.3, CPU).
- [ ] Record `records/2026-..._ste_ls1_distil_record.md`, ledger rows, clips of network-flown games beside the
  same starts flown by scripts; two reviewers (it is a result that feeds the owner's route choice).
- [ ] Read for the owner: per side DISTILLED or not; which skills copy worst and why (the switch points are the
  expected place); what LS2 would start from.

## 7. Stages LS2 to LS4 (outlines; each gets its own design note and task plan)

### LS2 Fine-tune the skills

- **Two time scales, solved by taking turns.** With the heads frozen, the game plus the heads is an ordinary
  environment for the skill network at one command per tick (the code z is part of its input): today's PPO applies
  with `hold = 1`. With the skill network frozen, today's `DecisionEnv` and `TwoLevelIPPO` train the heads unchanged
  on a `NetTwoLevelDispatch`. Phases alternate (PROPOSED: skills, then heads, repeated).
- **The tie to the scripts**: an added loss `w · ||π(obs, slot, z) − script_z(obs)||²` (`script_commands` of Task 2),
  `w` lowered on a schedule written in the gate file. Without it the codes collapse into one behaviour and the
  heads have nothing to choose.
- **Gate (to be written):** the worst cell and the pooled row above the best fixed mix of scripts
  (`scripts/ste_l3_run0_ceiling.py`) and above today's skills-route result on the same starts; each code still
  recognisable (a classifier names the code from a 12-tick track, accuracy above a limit); controls: the LS1
  network unchanged (the step-0 row), and a run with `w = 0` (expected to lose the codes).
- **Depends on:** LS1 DISTILLED on both sides. Recommended on learner v2 (shared actor, team critic), so nothing is
  built twice; the v2 note gains one section for the skill network's inputs (slot, code).
- **Open design questions for its note:** exploration noise of the skill network at 20 Hz; whether the Guard and
  Strike teams take turns or train in the same run; team sizes beyond 3v3 (the slot input covers the index; the
  team size itself is not an input yet).

### LS3 Free codes

- M extra codes with no script and no tie (PROPOSED M = 4). Reward = game reward + a diversity reward that pays
  when the code can be told from where the drone went (DIAYN or METRA style; METRA suits movement skills). Order:
  diversity only, then both. The heads widen to K + M.
- **Gate (to be written):** the new codes are chosen (the choice log already exists, `scoring.choice_share`); the
  worst cell rises over LS2 on the same budget; controls: LS2 continued for the same steps without new codes.
  The new skills are named afterwards from clips.
- **Risk:** the codes stay unused or differ without being useful. This is the research question of the route.

### LS4 Team strategy in a league

- The named team strategies stop being special: the team level gives each drone a code every 0.6 s; a team
  strategy is a pattern of codes. Opponents come from the learner v2 league (latest, past, scripts), with one
  addition: **saved exploits**, a Strike team trained against a frozen Guard team (and the reverse), kept as
  permanent league entries like the scripts.
- **Gate (to be written):** the robustness suite of PLAN §1 (held-out attackers, drone loss), plus every saved
  exploit; patterns of codes clustered and shown as clips.
- **Depends on:** the league (learner v2), LS3 or LS2.

## 8. Budget (every hour an estimate until LS1 has run)

| Stage | Estimate (GPU-h) | Basis | Status |
|---|---|---|---|
| LS1.1 distillation, both sides | 0.6 | 4 rounds × 4,096 games × 600 ticks per side at tier 1's measured rate, plus the fits | PROPOSED cap 0.8 |
| LS1.2 equivalence, both sides | 0.1 | 50 cells × 1,000 games per side, scoring only | PROPOSED cap 0.2 |
| LS1.3 export | 0 | CPU | — |
| LS2 | 5 to 8 | L5.2 asked 2.6 for both sides of the skills route; tick-level training and two alternating learners | OPEN, estimated again after LS1 |
| LS3 | 10 to 20 | discovery methods are sample-hungry; no measurement of ours | OPEN |
| LS4 | OPEN | depends on the league's cost in learner v2 | OPEN |

LS1's 1.0 GPU-h would come from the unallocated hours of `[budget_l3_l4_l5_l6]` (17.7 of 20 left on 25 Nov 2026),
if the owner agrees (9.2). It does not take the hours planned for the second short check on learner v2.

## 9. For the owner (nothing is built before these are answered)

1. **Adopt the learned-skills route as a third route**, beside pure RL and today's skills route, with the name above?
   **RULED 25 Nov 2026 (R35): adopted.** The ruling covers the route only: no GPU hour and no later stage.
2. **LS1 budget:** 1.0 GPU-h, charged to the L3–L6 cap as tasks LS1.1 to LS1.3?
   **RULED 25 Nov 2026 (R36): yes.**
3. **Order against learner v2:** recommended: LS1 now, beside the v2 note (it needs only the scripts and a
   supervised fit); LS2 onwards on learner v2. **RULED 25 Nov 2026 (R37): LS1 now, route 3 first.**
4. **The LS1 limits** (section 4) are the lead's proposal; the lead fixes them in the gate file unless the owner
   wants to rule on them. **RULED 25 Nov 2026 (R38): the owner sets them, on the lead's advice, after a
   noise-floor read.**
5. **LS2 to LS4** are not asked for now; each comes back with its own note and cost after the gate before it.

## 10. What comes out, and how it is used

- Per team, an export folder: the heads (logits, run every 0.6 s) and the skill network (command, run every tick),
  ONNX with golden rows and `interface.toml`. The Guard team's and the Strike team's folders are separate and
  either can be used without the other.
- A policy reads only the observation (positions and velocities of the drones, the zone, the clock). It does not
  know what flies the other team. Any Strike player can be put against an exported Guard team: a script of
  `opponents/scripted.py`, outside code named as `package.module:ClassName` (`make_strategy`,
  [PLUG_IN_YOUR_CODE](../../docs/PLUG_IN_YOUR_CODE.md)), a trained Strike team, or in flight a hand-flown drone.
  In the training simulator such a match is 1,000 games in seconds; that is the held-out attacker test of the
  robustness suite.
- Flight is L7 and L8, owner-gated, unchanged by this plan: nothing here has flown.
