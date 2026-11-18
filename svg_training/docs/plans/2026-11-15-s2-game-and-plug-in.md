INTERNAL · a build plan written for the lab's AI coding assistants; history, not instructions. Results: [../README.md](../README.md).

# S2 Game, Varied Sizes and Plug-in Point Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Strike vs Guard game for thousands of games at once on the GPU (the partner rules preset, with an optional Starling layer), arenas of varied size, a training-library-neutral plug-in point with a scoring tool and scripted opponents, a faster safety filter, a held-out check of the drone model against the 12 November rosbag, and a stand-in trainer that proves the pipe end to end.

**Architecture:** One batched game class (`core/game.py`, PyTorch only) runs N games of G Guard and S Strike drones. Two motion paths: the **pure partner rules** (point drones at fixed per-team speeds, opposite teams kept apart by a push-apart rule, teammates pass through) and the **Starling layer** (the commander copy, the fitted PX4 model and the safety filter on every pair, as on the real drones). A strategy is any object called once per team per step on that team's observations; scripted opponents, the scoring tool and two adapters (skrl multi-agent, Gymnasium vector) are built on that contract only. Partner values live in a git-ignored local file and overlay neutral committed defaults.

**Tech Stack:** Python 3.11, conda `env_isaaclab`: torch 2.7.0+cu128, skrl **2.1.0**, gymnasium **1.2.1** (both checked in the env on 15 November 2026; the brief said skrl 1.4.3 / gymnasium 1.2.3, the env wins), numpy/scipy for offline scripts only, matplotlib for figures. No `pip install`. No Isaac Lab import anywhere in S2.

**Spec:** [../specs/2026-11-15-s2-game-and-plug-in-design.md](../specs/2026-11-15-s2-game-and-plug-in-design.md) (APPROVED 15 November 2026, night) §4, §4a, §4b, §5, §6, §7; [../../STANDARDS.md](../../STANDARDS.md) §3, §4, §6, §7, §8, §9, §11.

**Status:** written 15 November 2026 (night); **approved with its gates by the owner ("just execute the rest", 15 November, late night)**; execution: subagent-driven, the lead commits.

## Facts this plan rests on (read 15 November 2026)

| Fact | Source |
|---|---|
| 325 tests pass on the laptop host (`PYTHONPATH=source`, 214 s) | test run while writing this plan |
| Filter port at 1,000 sweeps on T2's 2,000 scenes: max abs dv 1.6666 m/s, residual 2.08973, emergency agreement 0.999, cross-team corrections 0; on the scenes CMU solved in its first phase, max abs dv 6.18e-05 m/s | [T2 record](../../records/2026-11-15_s1_filter_parity_record.md) |
| Tier 1, 5v3, 4,096 games, laptop GPU: open arena filter off 2,271,956 game-steps/s, filter 1,000 sweeps 10,027, 200 sweeps 48,438; full sensing 38,303 / 7,938 / 21,279 | [T4 record](../../records/2026-11-15_s1_tier1_fitted_filter_record.md) |
| In T4 the filter used the **team** mask; the Starling layer uses **every pair**, so T4's numbers are not the Starling layer's | STANDARDS §4 row "Safety filter in the game" |
| A teammate pair flown head-on with the filter on came to 1.083 m (position-setpoint leak), not 1.10 m | T4 record, "What the filter does not cover" |
| `filter_velocities` accepts a per-game `[N, M, M]` pair mask; an isolated drone is its own group | `core/safety_filter.py` docstring |
| `FittedResponse` takes one static `pair_mask` and `filter_iterations`; its commander and PX4 model need a 0.05 s tick | `models/fitted.py` |
| The commander's stick cap is 0.5 m/s; tier 1 refuses a Strike cap above it | `params/real_exploratory_v0.toml` `[commander]`; `envs/tier1_bench.py` |
| skrl 2.1.0: `MultiAgentEnvWrapper` (abstract `reset/step/state/render/close`, `possible_agents`, `observation_spaces`, `action_spaces`, `state_space`); `IPPO(possible_agents=, models=, memories=, observation_spaces=, state_spaces=, action_spaces=, device=, cfg=IPPO_CFG)`, **one Adam optimiser per agent name** (so one model shared by two names is stepped twice); `SequentialTrainer(env=, agents=, cfg=)`; `RandomMemory(memory_size=, num_envs=, device=)` | `skrl/envs/wrappers/torch/base.py`, `skrl/multi_agents/torch/ippo/ippo.py:68-160`, `skrl/trainers/torch/sequential.py` |
| gymnasium 1.2.1 has `gymnasium.vector.AutoresetMode`; `VectorEnv.reset(*, seed, options)`, `step(actions) -> (obs, rew, term, trunc, info)` | env check |
| Bag `~/flight_logs/2026-11-12/svg_20261112_094546/svg_20261112_094546_0.mcap`: 592 MB, uncompressed chunks, `/drone_N/fmu/in/trajectory_setpoint` 18.8 Hz and `/drone_N/fmu/out/vehicle_local_position` (PX4 local NED, world frame) 51 Hz for drone_2; drone_2 goal legs: 3 y legs of 2.0–2.4 s at 0.5 m/s (17:45) and one 2.8 s leg (18:00); drone_1 only gave way (≤ 0.38 m/s) | [survey §2, §3](../notes/s1_real_logs_survey.md) |
| `real_exploratory_v0` was fitted on 13 November `log103.ulg` (drone_2, gamepad); the bag is a different day and a different command source (goal legs) | `params/real_exploratory_v0.toml` header |
| GPU at writing: 3,648 MiB of 12,227 MiB in use by another process | `nvidia-smi` |

## Global Constraints

- **Write only inside `svg_training/`.** Nothing changes AirStack, `tools/`, drone parameters, the sim airframe or the website. Never push. Builder agents make no git writes; **the lead commits** with explicit paths (`git add <path> …`, never `-A`, `-a`, `--no-verify`).
- **Confidentiality.** The partner's game numbers come from a confidential programme report and never appear in any committed file (code, tests, docs, this plan, configs, records, figures, commit messages). The partner rules preset is a set of switches with **neutral committed defaults** (`configs/s2_game.toml`); the partner values live in `configs/local/partner_rules.toml`, git-ignored by `svg_training/.gitignore` (committed), loaded only if present. Tests use made-up numbers. **Every S2 run of record uses the committed neutral values** (`--no-local`); a run with the local file is a local run whose record may give only the file name and its sha256, and is committed only on the owner's say-so.
- **Partner rules mechanism (no numbers):** push-apart between opposite teams, one keep-out distance per team, instead of tags; teammates pass through each other; a Strike drone inside the zone for one step wins, permanently; otherwise the Guard team wins at time-out; per-team speed per step and game length in steps; metres per unit and seconds per step are settings.
- **Starling layer** (switch): `real_exploratory_v0` (labelled exploratory everywhere) + the safety filter on **every pair** (as on the real drones). The scoring tool reports each strategy under "pure partner rules" and "with Starling layer".
- **Side quest** (contact tags, filter within a team only) stays a game mode with hand-worked tests; nothing more is built for it in S2. NEAR Lab's own training is out of scope except the stand-in pipe test.
- **Sizes:** arena side 4–16 m, zone radius 10–25 % of the side, zone centre at least radius + 0.5 m from every wall; bands lab 4–6, middle 6–10, large 10–16 m reported separately. Fixed named scenarios exist only for scoring and tests; the adapters refuse them (STANDARDS §6 rule 4).
- **Defaults where the partner rules are silent (design §4b):** walls stop drones (`keep_in`); Strike drones start on a ring near the walls, Guard drones on a ring around the zone; drop-out fraction 0; Strike 0.5 m/s, Guard 0.33 m/s.
- **Training rules (STANDARDS §6):** batched everywhere; no Python loop over games; no `.cpu()`, `.item()`, `.numpy()`, `.tolist()` or NumPy in the step. One exception, measured and recorded in Task 7: the filter's `check_every` option makes one host sync per check. Fixed sweep counts and sub-step counts are the only loops.
- **Runs:** every run has its gates in `configs/s2.toml` (approved before the first run) copied to `runs/<name>/gates.toml` before it starts, a record from `records/_template_record.md` whose first line names the simulator, a ledger row with the **next free T number at run time** (T5 onwards; expected T5 filter speed, T6 bag check, T7 scripted reference, T8 stand-in, but whichever runs first takes T5). Write "observed in the training simulator" (or "observed in flight logs" for Task 8), never "validated". A FAIL is a FAIL; an interrupted run writes an ABORTED record.
- **GPU runs:** `nvidia-smi` first; no run while the AirStack simulator or a flight session holds the GPU; headless.
- **Writing:** plain words for a newcomer, the term second; every results page shows a figure made by a committed script from the run's own data; captions 2–4 sentences and at most 400 characters; Strike team / Guard team / tag / reach the zone (STANDARDS §2).
- **After every task** the lead updates the S2 progress table in `docs/claude/HANDOFF.md` §0 and refreshes `~/Downloads/claude-handoff-svg-training.md` (owner's rule for running out of usage).
- Python: type hints on public functions, shapes in docstrings, SI units in names (`_m`, `_mps`, `_s`). Tests: `cd svg_training && PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python -m pytest -q`; core tests run on CPU in seconds; GPU-only tests skip without CUDA.

## Review Focus

1. **Partner numbers leaking into the public repo** (a default, a test fixture, a record, a commit message). Test `test_local_values_not_in_tracked_files` and `test_gitignore_covers_local` (Task 1).
2. **A host sync or per-game loop in the step** (the design's third anti-goal), including the auto-reset path. Tests `test_game_modules_have_no_host_calls` (static scan) and `test_step_runs_under_sync_debug_error` (CUDA only) (Task 2), extended to the Starling layer (Task 4).
3. **The Starling layer filtering the wrong pairs or losing the speed ratio**: a team mask would let a Guard and a Strike drone touch; a partner speed above the commander's stick cap would be clipped silently. Tests `test_starling_keeps_opposite_teams_apart`, `test_starling_speed_ratio`, `test_partner_speed_above_stick_cap_raises` (Task 4).
4. **Reset bookkeeping**: an outcome credited to the next game after auto-reset, a win on the last step scored as a time-out, a strategy's memory not cleared. Tests `test_win_on_last_step_is_strike`, `test_outcome_reported_on_done_step_then_new_game`, `test_strategy_reset_mask_equals_done` (Tasks 2, 5).
5. **The core tied to one training library** (the design's first anti-goal). Test `test_core_imports_no_training_library` (Task 5), run again in Task 9 after the adapters exist.

## Decisions this plan makes (for the owner to see before approving)

| # | Decision | Why |
|---|---|---|
| D1 | "One keep-out distance per team" read as: **each team's own drones may not move closer than its own distance** to any drone of the other team (`push_rule = "block"`); a repair pass then separates any opposite pair still closer than the smaller distance. Switch `"shove"` (both pushed equally) is also built. | The design gives the mechanism, not the reading; the owner can check it against the report and flip the switch in the local file. |
| D2 | The pure partner rules are **planar** (height fixed at 1.2 m, `vz` ignored); the Starling layer is 3-D as flown. | The partner game is a 2-D game; scoring is horizontal (STANDARDS §4). |
| D3 | With the Starling layer on, the **push-apart rule is off**: on the real drones only the safety filter (1.10 m, every pair) keeps drones apart. The scoring tool reports the closest opposite approach and a "rule breach" flag when an opposite pair is closer than the partner limit. | Matches what a real Starling can do; the breach count is part of "what flying a real Starling costs". |
| D4 | The game always ticks at 0.05 s (FIXED 20 Hz). Partner per-step speeds and length convert: speed = units per step × metres per unit ÷ seconds per step; ticks = round(steps × seconds per step ÷ 0.05). | The commander and PX4 model need the real tick. |
| D5 | Size draw: band first (equal weights), then side uniform within the band. | A uniform side would give the lab band only 1/6 of training games; the lab is where drones fly. |
| D6 | Filter accuracy gate: T2's four measured values **plus a fifth**: max abs dv ≤ 0.02 m/s on the scenes CMU solved in its first phase (T2: 6.18e-05). | Without it a setting could be 1.6 m/s off on ordinary scenes and still be "no worse than T2's worst scene". |
| D7 | Filter speed target **≥ 100,000 game-steps/s**, 5v3, 4,096 games, the S2 game with the Starling layer, random actions, this laptop. | 10 × T4's 10,027; a 100 M game-step 5v3 run then needs about 17 min of game time, against about 2.8 h at T4's rate. Measured on the S2 game (arenas 4–16 m, ring starts), not on T4's 40 m arena where drones are rarely close. |
| D8 | Stand-in: **skrl IPPO**, 2 Guard v 1 Strike, one network per Guard drone, pure partner rules with the committed neutral values. | IPPO has fewer parts than MAPPO; the full-view observation already holds every drone, so MAPPO's central critic adds little; skrl gives each agent name its own optimiser, so independent networks avoid a shared model being stepped twice. |
| D9 | Observation: 69 floats per drone, every drone's full state (switch `obs_view = "full"`, the only value in S2). | STANDARDS §3 layout without range rays; the open question of what a drone may know stays OPEN behind the switch. |
| D10 | The `check_every` filter option is allowed one host sync per check (it must decide to stop). | No early stop is possible without it; Task 7 measures its cost and the record states it. |

## Task overview and order

| Task | What | Needs | Can run alongside |
|---|---|---|---|
| 1 | Config, gates, local partner file, `.gitignore` | — | — |
| 2 | Game core: arenas, starts, motion, walls, zone, time-out, drop-outs, observations, rewards, scenarios | 1 | 7a, 8 |
| 3 | Pair rules: push-apart (partner) and contact tags (side quest) | 2 | 5, 7a, 8 |
| 4 | Starling layer | 3 | 5, 7a, 8 |
| 5 | Strategy contract and scripted opponents | 2 | 3, 4, 7a, 8 |
| 6 | Match loop, metrics, scoring tool, scripted reference run | 4, 5 | 7b, 8 |
| 7 | Faster safety filter: 7a accuracy (CPU), 7b speed (GPU) + run | 7a: 1; 7b: 4 | see left |
| 8 | Drone-model cross-check on the 12 November bag + run | 1 | 2–7 |
| 9 | Adapters (skrl, Gymnasium) and the partner guide | 6 | 7b, 8 |
| 10 | Stand-in trainer + run | 9 | — |
| 11 | Documents and final review | all | — |

Done conditions of the design §7: 1 → Tasks 2, 3; 2 → Task 6; 3 → Task 7; 4 → Task 10; 5 → Tasks 9, 10.

---

### Task 1: S2 configs, gates and the local partner file (owner approval)

**Files:** Create `configs/s2_game.toml`, `configs/s2.toml`, `configs/partner_rules.example.toml`, `source/svg_training/core/game_config.py`; Modify `.gitignore` (inside `svg_training/`); Test `tests/test_s2_config.py`, `tests/test_partner_privacy.py`.

**Interfaces — Produces:**
```python
TICK_S: float = 0.05
@dataclass(frozen=True) class ArenaCfg:          # [arena]
    bands_m: dict[str, tuple[float, float]]      # {"lab": (4, 6), "middle": (6, 10), "large": (10, 16)}
    band_weights: tuple[float, float, float] = (1.0, 1.0, 1.0)
    zone_radius_frac: tuple[float, float] = (0.10, 0.25)
    zone_wall_margin_m: float = 0.5
    height_band_m: tuple[float, float] = (0.5, 1.8)
    start_height_m: float = 1.2
    walls: str = "keep_in"                       # "keep_in" | "leave"
    wall_margin_m: float = 0.25
@dataclass(frozen=True) class PartnerRulesCfg:   # [partner_rules]; neutral committed defaults
    keepout_guard_m: float = 1.10                # the flight stack's keep-out, NOT a partner value
    keepout_strike_m: float = 1.10
    push_rule: str = "block"                     # "block" | "shove" (D1)
    teammates_pass: bool = True
    win_steps_in_zone: int = 1
    strike_units_per_step: float = 0.025         # = 0.5 m/s with the two lines below (owner, design §4b)
    guard_units_per_step: float = 0.025 / 1.5
    game_steps: int = 1200
    metres_per_unit: float = 1.0
    seconds_per_step: float = 0.05
@dataclass(frozen=True) class ContactRulesCfg:   # [contact_rules], side quest
    contact_m: float = 0.50; guard_survives_tag_prob: float = 0.0
@dataclass(frozen=True) class StarlingLayerCfg:  # [starling_layer]
    enabled: bool = False; params: str = "params/real_exploratory_v0.toml"
    filter_iterations: int = 1000; filter_check_every: int = 0
@dataclass(frozen=True) class StartsCfg:         # [starts]
    mode: str = "rings"                          # "rings" | "anywhere"
    strike_inset_m: float = 0.3; guard_ring_gap_m: float = 0.3; spacing_m: float = 1.2
@dataclass(frozen=True) class RewardsCfg:        # [rewards]
    win: float = 1.0; shaping_weight: float = 0.0
@dataclass(frozen=True) class GameCfg:
    preset: str                                  # "partner" | "contact"
    arena: ArenaCfg; rules: PartnerRulesCfg; contact: ContactRulesCfg
    starling: StarlingLayerCfg; starts: StartsCfg; rewards: RewardsCfg
    dropout_fraction: float = 0.0; obs_view: str = "full"
    pad_guards: int = 5; pad_strikes: int = 3; yaw_rate_max_rad_s: float = 1.0
    def team_speed_mps(self, team: str) -> float  # units/step × m/unit ÷ s/step
    def game_ticks(self) -> int                   # round(game_steps × seconds_per_step / TICK_S)
    def replace(self, **dotted: Any) -> "GameCfg" # e.g. replace(**{"starling.enabled": True})
@dataclass(frozen=True) class Provenance:
    game_file: str; game_sha256: str; local_file: str | None; local_sha256: str | None
LOCAL_ALLOWED: frozenset[str]                     # every "partner_rules.<key>" and "arena.zone_radius_frac"
def load_game_cfg(path: str | Path = CONFIGS / "s2_game.toml", local_dir: Path | None = CONFIGS / "local",
                  use_local: bool = True) -> tuple[GameCfg, Provenance]
def load_s2_gates(path: str | Path = CONFIGS / "s2.toml") -> dict
```

`configs/s2.toml`, PROPOSED values for the owner to approve before any run (never edited after a result exists):

```toml
[filter_speed]                      # Task 7. Candidates fixed before the run; a new one = a new run
iterations = [1000, 500, 300, 200, 100]
check_every = [0, 8, 32]            # 0 = the fixed loop of T2
accuracy_device = "cpu"             # T2's conditions: CPU, float32
speed_case = { guards = 5, strikes = 3, num_games = 4096, actions = "random", repeats = 2 }

[filter_speed_gates]                # on T2's 2,000 scenes (seed 20261115); "no worse than T2"
max_abs_dv_mps = 1.6666             # T2 measured
constraint_residual_max = 2.08973   # T2 measured
emergency_agreement_min = 0.999     # T2 measured
cross_team_corrections = 0          # T2 measured
max_abs_dv_first_phase_mps = 0.02   # D6: scenes CMU solved without its Gauss-Seidel phase (T2: 6.18e-05)
game_steps_per_s_min = 100000       # D7
scenes = 2000
seed = 20261115

[bag_check_gates]                   # Task 8; exploratory: the bag cannot give the 8 legs of S1's fit gates
drone = "drone_2"                   # the airframe the model was fitted on; drone_1 reported, not gated
vel_rms_max_mps = 0.10              # every leg, active span (leg start to leg end + 1 s); S1 [fit_gates] value
t63_err_max_s = 0.10                # worst leg start or stop; S1 [fit_gates] value
min_legs = 3                        # fewer legs found = INFO, no verdict
accel_ff = "derived"                # as the model was fitted

[scoring]                           # Task 6
games_per_band = 1000
sizes = ["2v1", "5v3"]
presets = ["pure", "starling"]

[standin]                           # Task 10 (D8)
algorithm = "IPPO"
guards = 2
strikes = 1
preset = "pure"                     # committed neutral values; --no-local
num_games = 4096
game_steps_per_seed = 50_000_000
wall_clock_cap_min = 45
seeds = [1, 2, 3]
opponent_mix = { strike_straight = 0.5, strike_flank = 0.5 }   # split by game index
shaping_weight = 1.0
rollouts = 32
learning_epochs = 5
mini_batches = 4
learning_rate = 3.0e-4
hidden = [128, 128]

[standin_gates]
eval_games_per_band = 1000          # 3,000 games per condition
eval_seed_offset = 1000             # evaluation seed = training seed + this
behaviours = ["strike_straight", "strike_flank"]
min_hold_rate_gain = 0.20           # trained minus random Guard, absolute, for every seed and behaviour
intervals_disjoint = true           # Wilson 95 %: trained lower bound > random upper bound
seeds_required = 3                  # all three seeds must pass
```

- [ ] **Failing tests** `tests/test_s2_config.py`:
```python
def test_neutral_defaults_load_without_local(tmp_path):
    cfg, prov = load_game_cfg(local_dir=tmp_path / "absent")
    assert prov.local_file is None and cfg.preset == "partner"
    assert cfg.team_speed_mps("strike") == pytest.approx(0.5) and cfg.team_speed_mps("guard") == pytest.approx(0.5 / 1.5)
    assert cfg.game_ticks() == 1200 and not cfg.starling.enabled
def test_local_overlay_applies_allowed_keys(tmp_path):   # made-up numbers only
    (tmp_path / "partner_rules.toml").write_text("[partner_rules]\nkeepout_guard_m = 0.77\nseconds_per_step = 0.1\ngame_steps = 30\n")
    cfg, prov = load_game_cfg(local_dir=tmp_path)
    assert cfg.rules.keepout_guard_m == 0.77 and cfg.game_ticks() == 60 and prov.local_sha256
def test_local_overlay_rejects_other_keys(tmp_path):
    (tmp_path / "partner_rules.toml").write_text("[starling_layer]\nenabled = true\n")
    with pytest.raises(ValueError, match="not allowed"): load_game_cfg(local_dir=tmp_path)
def test_unknown_key_raises(tmp_path): ...               # a typo in s2_game.toml is an error, not ignored
def test_use_local_false_ignores_file(tmp_path): ...
def test_s2_gates_complete():
    g = load_s2_gates()
    assert g["filter_speed_gates"]["game_steps_per_s_min"] == 100000
    assert g["standin_gates"]["seeds_required"] == len(g["standin"]["seeds"]) == 3
    assert set(g) >= {"filter_speed", "filter_speed_gates", "bag_check_gates", "scoring", "standin", "standin_gates"}
```
`tests/test_partner_privacy.py`:
```python
def test_gitignore_covers_local():
    assert "configs/local/" in (ROOT / ".gitignore").read_text().splitlines()
    r = subprocess.run(["git", "check-ignore", "-q", "configs/local/partner_rules.toml"], cwd=ROOT)
    assert r.returncode == 0
def test_local_values_not_in_tracked_files():
    local = ROOT / "configs/local/partner_rules.toml"
    if not local.exists(): pytest.skip("no local partner file on this machine")
    values = _distinctive_values(local.read_text())   # number tokens as written, ≥ 3 significant digits,
                                                       # minus any value equal to a committed default
    tracked = subprocess.run(["git", "ls-files", "-z", "--", "."], cwd=ROOT, capture_output=True,
                             text=True).stdout.split("\0")
    hits = [(f, v) for f in tracked if f for v in values if v in _text(ROOT / f)]
    assert hits == []
```
- [ ] Run: `pytest -q tests/test_s2_config.py tests/test_partner_privacy.py` → fails (module missing).
- [ ] Implement `core/game_config.py` (TOML only, unknown keys raise, dotted `replace`), the three TOML files (`partner_rules.example.toml` has every allowed key with the neutral value and a comment "copy to configs/local/partner_rules.toml and put the partner values there; never commit them"), and add the line `configs/local/` to `svg_training/.gitignore`.
- [ ] Run: tests pass. The lead takes `configs/s2.toml` to the owner; **no run in Tasks 6, 7, 8, 10 starts before approval**.
- [ ] Lead commits: `git add svg_training/configs/s2_game.toml svg_training/configs/s2.toml svg_training/configs/partner_rules.example.toml svg_training/source/svg_training/core/game_config.py svg_training/.gitignore svg_training/tests/test_s2_config.py svg_training/tests/test_partner_privacy.py` then `git commit -m "svg_training S2: game config, gates, git-ignored local partner file"`.

### Task 2: Game core (pure partner rules without the pair rule)

**Files:** Create `source/svg_training/core/arena.py`, `source/svg_training/core/observations.py`, `source/svg_training/core/rewards.py`, `source/svg_training/core/scenarios.py`, `source/svg_training/core/game.py`; Test `tests/test_arena.py`, `tests/test_game_core.py`, `tests/test_observations.py`.

**Interfaces — Consumes:** `GameCfg`, `TICK_S` (Task 1). **Produces:**
```python
GUARD, STRIKE = "guard", "strike"
RUNNING, STRIKE_WIN, GUARD_WIN = 0, 1, 2          # outcome codes (int8)
BANDS = ("lab", "middle", "large")
@dataclass class Arenas:                            # all [N] unless stated
    side_m: Tensor; half_m: Tensor; zone_centre_m: Tensor  # [N, 2]
    zone_radius_m: Tensor; band: Tensor                    # long, index into BANDS
def draw_arenas(cfg: ArenaCfg, n: int, gen: torch.Generator, device, band: int | None = None) -> Arenas
def draw_starts(cfg: GameCfg, ar: Arenas, guards: int, strikes: int, gen: torch.Generator) -> Tensor  # [N, M, 3]
@dataclass(frozen=True) class Scenario:
    name: str; side_m: float; zone_centre_m: tuple[float, float]; zone_radius_m: float
    start_m: tuple[tuple[float, float], ...]       # (x, y) per drone, Guard drones first
SCENARIOS: dict[str, Scenario]                     # "lab4_open", "lab4_block", "large16_open", "large16_block"
OBS_DIM = 69                                       # own 8 + game 5 + (pad_guards + pad_strikes) × 7
STATE_DIM = 59                                     # game 3 + 8 slots × 7
class ObsView:                                     # named slices for readers of an observation (Task 5)
    own_pos, own_vel, sin_cos_yaw, zone_radius, arena_half, time_left, team, alive: slice | int
    def slot(self, k: int) -> slice                # 7 floats: rel pos 3, rel vel 3, present 1
def build_obs(cfg: GameCfg, pos_m, vel_mps, yaw, alive, ar: Arenas, time_left_s, guards, strikes) -> dict[str, Tensor]
def build_state(...) -> Tensor                     # [N, STATE_DIM]
def team_rewards(cfg: RewardsCfg, outcome: Tensor, phi_prev: Tensor, phi_now: Tensor, guards, strikes) -> dict[str, Tensor]
@dataclass class StepOut:
    obs: dict[str, Tensor]                         # {"guard": [N, G, OBS_DIM], "strike": [N, S, OBS_DIM]}, after auto-reset
    reward: dict[str, Tensor]                      # {"guard": [N, G], "strike": [N, S]}
    done: Tensor                                   # [N] bool; every end is terminal (time left is observed)
    outcome: Tensor                                # [N] int8, outcome of the games that ended this step, else 0
    end_step: Tensor                               # [N] long, the step count at which they ended, else 0
    info: dict[str, Tensor]                        # band [N], closest_cross_m [N], closest_team_m [N],
                                                   # rule_breach [N] bool, filter_corrected [N, M] bool
class SvgGame:
    def __init__(self, cfg: GameCfg, num_games: int, guards: int, strikes: int, device: str = "cuda",
                 seed: int = 0, band: int | None = None, scenario: Scenario | None = None)
    num_games: int; num_envs: int; guards: int; strikes: int; device; scenario
    pos_m: Tensor; vel_mps: Tensor; yaw: Tensor; alive: Tensor; steps: Tensor; arenas: Arenas
    def reset(self, seed: int | None = None) -> dict[str, Tensor]
    def step(self, actions: dict[str, Tensor]) -> StepOut   # actions [N, G, 4] and [N, S, 4], in [-1, 1]
    def state(self) -> Tensor
    def schedule_dropout(self, drone: Tensor, at_step: Tensor) -> None  # [N] long each; -1 = none
```

Rules the step applies, in this order (pure partner preset): clamp actions to [-1, 1]; per-team norm cap at `team_speed_mps`; move horizontally (`z` held at `start_height_m`); yaw += yaw rate × `yaw_rate_max_rad_s` × 0.05; pair rule (hook, Task 3); walls (`keep_in`: clamp to `±(half − wall_margin)`, zero the outward speed; `leave`: drone out); scheduled drop-outs (drone out); win check (a live Strike drone with horizontal distance to the zone centre ≤ radius → `STRIKE_WIN`, checked **before** time-out); time-out (`steps == game_ticks` → `GUARD_WIN`); no live Strike drone left → `GUARD_WIN`; rewards; auto-reset of done games (new arena, starts, drop-out draw; with a scenario the same layout); observations. A drone that is out is parked at a far fixed point, excluded from every rule and shown as absent. Shaping potential `phi = min over live Strike of (distance to zone edge) / half_m`; Guard shaping reward `w·(phi_now − phi_prev)`, Strike the negative; terminal ±`win`.

Named scenarios (zone at the centre; Guard drone first, then Strike drone; pure rules, neutral keep-outs 1.10 m):

| Name | Side | Zone radius | Guard start | Strike start | Hand-worked answer with Guard `zero`, Strike `strike_straight` |
|---|---|---|---|---|---|
| `lab4_open` | 4 m | 0.6 m | (1.5, 1.5) | (−1.51, 0) | Strike wins at step 37 |
| `large16_open` | 16 m | 2.4 m | (7.5, 7.5) | (−7.51, 0) | Strike wins at step 205 |
| `lab4_block` | 4 m | 0.6 m | (−0.3, 0) | (−1.70, 0) | Strike blocked at x = −1.40, Guard wins at step 1200 |
| `large16_block` | 16 m | 2.4 m | (−2.0, 0) | (−7.51, 0) | Strike blocked at x = −3.10, Guard wins at step 1200 |

Starts (`rings`): Strike drones on the square inset `strike_inset_m` from the walls, Guard drones evenly on a circle of radius `zone_radius + guard_ring_gap_m` with a random phase, clamped inside the walls; each drone picks the first of 8 candidates that keeps `spacing_m` from its team-mates (the `_spawn` pattern of `envs/tier1_bench.py`, no loop over games). `anywhere`: uniform in the arena, Strike drones outside the zone.

- [ ] **Failing tests** (hand-worked; `S = Scenario(...)` built in the test, both sides):
```python
@pytest.mark.parametrize("side, start_x, zone_r, win_step", [(4.0, -1.51, 0.6, 37), (16.0, -7.51, 2.4, 205)])
def test_strike_scores_hand_worked(side, start_x, zone_r, win_step):
    g = SvgGame(cfg, 4, 1, 1, device="cpu", scenario=Scenario("t", side, (0, 0), zone_r, ((side/2 - 0.5, side/2 - 0.5), (start_x, 0.0))))
    # Guard still in a corner; Strike full speed +x: 0.025 m per step; inside when |x| <= r
    for k in range(1, win_step + 1):
        out = g.step({"guard": zeros(4, 1, 4), "strike": act_x(4, 1, +1.0)})
        assert bool(out.done.any()) == (k == win_step)
    assert (out.outcome == STRIKE_WIN).all() and (out.end_step == win_step).all()
@pytest.mark.parametrize("side", [4.0, 16.0])
def test_time_out_is_guard_win_at_exact_tick(side): ...      # Strike still: done False at 1199, GUARD_WIN at 1200
def test_win_on_last_step_is_strike(): ...                   # game_steps overridden to 37 in lab4 → STRIKE_WIN, not GUARD_WIN
@pytest.mark.parametrize("side", [4.0, 16.0])
def test_dropout_of_last_strike_is_guard_win(side):
    g.schedule_dropout(drone=torch.full((4,), 1), at_step=torch.full((4,), 10))
    # → GUARD_WIN, end_step 10, the Strike drone shown absent in the Guard's observation that step
def test_dropout_of_guard_game_continues(): ...              # Strike still wins at step 37; Guard slot present = 0
def test_outcome_reported_on_done_step_then_new_game():
    # step 37: outcome STRIKE_WIN; returned obs already the new game's: time_left == game_ticks * 0.05, steps == 0
def test_walls_keep_in(): ...                                 # full speed into a wall for 400 steps: |x| <= half - 0.25 + 1e-6
def test_walls_leave(): ...                                   # walls="leave": drone out when it reaches the margin
def test_rewards_terminal_signs(): ...                        # Guard +1 / Strike -1 on GUARD_WIN, reversed on STRIKE_WIN, 0 otherwise (shaping 0)
def test_game_modules_have_no_host_calls():                  # Review Focus 2
    for f in ["arena", "observations", "rewards", "game"]:
        src = (CORE / f"{f}.py").read_text()
        assert not re.search(r"\.(item|cpu|numpy|tolist)\(|import numpy|nonzero\(", src), f
@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA only")
def test_step_runs_under_sync_debug_error():                 # 256 games, 1300 steps (crosses an auto-reset)
    torch.cuda.set_sync_debug_mode("error"); ...; torch.cuda.set_sync_debug_mode(0)
```
`tests/test_arena.py`: 20,000 draws: every side within its band and within 4–16 m; `zone_radius / side` in [0.10, 0.25]; `|centre| + radius + 0.5 <= half + 1e-6` on both axes; `band=0` gives only lab sides; band shares within 0.02 of 1/3; Strike starts outside the zone, every start inside the walls, same-team spacing ≥ 1.2 m in ≥ 99 % of games (the S0 spawn reports misses, it does not loop).
`tests/test_observations.py`: `OBS_DIM == 69`; own slot present = 0; for a Guard in a 2v1 game the Strike's slot is `pad_guards + 0` and holds `strike_pos − own_pos`; padded slots present = 0 and all zeros; `team` is −1 for Guard, +1 for Strike; `build_state(...).shape[-1] == STATE_DIM`.
- [ ] Run → fail. Implement. Run → pass (whole suite still green).
- [ ] Lead commits the eight files listed under **Files**.

### Task 3: Pair rules: push-apart (partner) and contact tags (side quest)

**Files:** Create `source/svg_training/core/pair_rules.py`; Modify `source/svg_training/core/game.py` (call the pair rule; the contact preset); Test `tests/test_pair_rules.py`.

**Interfaces — Produces:**
```python
def push_apart(prop_m: Tensor, prev_m: Tensor, is_strike: Tensor, alive: Tensor, keep_guard_m: float,
               keep_strike_m: float, rule: str = "block", passes: int = 3) -> Tensor
    """prop_m, prev_m [N, M, 2] proposed and start-of-step horizontal positions; is_strike [M] bool; alive [N, M].
    block: each drone is pushed radially out of the disc of its OWN team's distance around every live
    opposite drone's start-of-step position (`passes` Jacobi passes, pushes summed), then one repair pass
    moves both drones of any opposite pair still closer than min(keep_guard, keep_strike) apart equally.
    shove: only the equal-share repair, `passes` times. Teammates never interact. Returns [N, M, 2]."""
def contact_tags(pos_m: Tensor, alive: Tensor, guards: int, contact_m: float, guard_survives: Tensor
                 ) -> tuple[Tensor, Tensor]
    """-> (tagged [N, M] bool, alive_after [N, M]). A live Guard–Strike pair closer than contact_m (3-D centres)
    tags both; the Strike drone leaves; the Guard drone leaves unless guard_survives [N] bool (drawn per game
    at reset with guard_survives_tag_prob)."""
```

- [ ] **Failing tests:**
```python
@pytest.mark.parametrize("side", [4.0, 16.0])
def test_block_strike_stops_at_its_keepout(side):     # test-only distances 1.0 / 1.0
    # Guard still at (0, 0); Strike from (-1.51, 0) at full speed +x for 100 steps; zone far away
    assert final_strike_x == pytest.approx(-1.0, abs=1e-4) and min_distance >= 1.0 - 1e-4
def test_block_both_closing_never_below_smaller_distance(): ...   # head-on 1v1, keep 0.9 / 1.3: min distance >= 0.9 - 1e-4
def test_shove_moves_still_guard(): ...                # rule="shove": after 60 steps the still Guard moved +x by > 0.3 m
def test_teammates_pass_through(): ...                 # two Guard drones head-on: distance < 0.1 at some step
@pytest.mark.parametrize("side", [4.0, 16.0])
def test_contact_tag_hand_worked(side):
    # preset "contact": Guard still at (0.3, 0); Strike from (-0.51, 0) at +x; zone at (1.0, 1.0) r 0.4 (4 m) / same for 16 m
    # distance 0.81 - 0.025 k < 0.50 first at k = 13 → both out (prob 0) → GUARD_WIN, end_step 13
def test_contact_guard_survives_when_prob_one(): ...   # same, guard_survives_tag_prob = 1: Guard alive after the tag
def test_contact_preset_has_no_push_apart(): ...
def test_block_scenario_strike_never_scores(): ...     # SCENARIOS["lab4_block"], 1200 steps: GUARD_WIN at 1200
```
- [ ] Run → fail; implement; run → pass; the static no-host-call test now also scans `pair_rules.py`.
- [ ] Lead commits `core/pair_rules.py`, `core/game.py`, `tests/test_pair_rules.py`, `tests/test_game_core.py` (scan list).

### Task 4: Starling layer

**Files:** Create `source/svg_training/core/starling_layer.py`; Modify `source/svg_training/core/game.py`, `source/svg_training/models/fitted.py` (two additions only); Test `tests/test_starling_layer.py`.

**Interfaces — Consumes:** `FittedResponse` (S1), `filter_velocities`, `team_pair_mask`. **Produces:**
```python
# models/fitted.py additions (existing behaviour unchanged when not used):
FittedResponse.__init__(..., filter_kwargs: dict | None = None)   # merged into the filter_velocities call
def FittedResponse.set_pair_mask(self, mask: Tensor) -> None      # [M, M] or [N, M, M] bool
# core/starling_layer.py
class StarlingLayer:
    def __init__(self, cfg: GameCfg, num_games: int, guards: int, strikes: int, device)
        # raises ValueError("... exceeds the commander's stick cap ...") if team_speed_mps("strike") > stick cap
    def reset(self, mask: Tensor, pos_m: Tensor) -> None          # [N, M] bool, [N, M, 3]
    def step(self, cmd_mps: Tensor, pos_m: Tensor, alive: Tensor) -> tuple[Tensor, Tensor, Tensor]
        # cmd [N, M, 3] (already team-capped) -> (pos_m, vel_mps, corrected [N, M] bool)
        # pair mask = every pair of live drones (preset "partner") or live team-mates only (preset "contact")
```
In `game.py` with `starling.enabled`: commands go through `StarlingLayer.step` (3-D: `vz` used, height band clamped like the walls), the push-apart rule is off (D3), `info["rule_breach"]` flags games where a live opposite pair is closer than `min(keepout_guard_m, keepout_strike_m)`, and `info["filter_corrected"]` is the layer's `corrected`.

- [ ] **Failing tests** (CPU, few games):
```python
def test_starling_keeps_opposite_teams_apart():        # Review Focus 3
    # 1v1 head-on from (-1, 0) and (1, 0), each at its team cap, 10 s
    assert min_horizontal_distance(starling=True, preset="partner") >= 1.0   # 1.083 m dip expected (T4 record)
    assert min_horizontal_distance(starling=True, preset="contact") < 0.5    # team mask: they meet
def test_starling_keeps_teammates_apart(): ...          # two Guard drones head-on: >= 1.0 m; pure preset: < 0.1 m
def test_starling_speed_ratio():
    # full-stick +x for 4 s in a 16 m arena: speed over the last second
    assert strike_speed == pytest.approx(0.5, abs=0.02) and guard_speed == pytest.approx(0.5 / 1.5, abs=0.02)
def test_partner_speed_above_stick_cap_raises(tmp_path):
    # local file (made-up): strike_units_per_step = 0.035 → 0.7 m/s
    with pytest.raises(ValueError, match="stick cap"): SvgGame(cfg_starling, 2, 1, 1, device="cpu")
def test_starling_walls_and_height_band(): ...          # drone driven into a wall and down: inside margin + 0.01, z >= 0.5 - 0.01
def test_rule_breach_flag(): ...                        # keep-outs set to 1.5 (test value): head-on 1v1 → rule_breach True
def test_fitted_filter_kwargs_passthrough(): ...        # filter_kwargs={"iterations": 7} reaches filter_velocities (monkeypatch spy)
def test_dropout_excluded_from_filter(): ...            # a drone out never makes another drone's corrected True
```
Extend `test_step_runs_under_sync_debug_error` to `starling.enabled=True` with `filter_check_every = 0`, and add `starling_layer.py` to the static scan of `test_game_modules_have_no_host_calls`.
- [ ] Run → fail; implement; run → pass; `tests/test_fitted.py` still green (no S1 behaviour changed).
- [ ] Lead commits `core/starling_layer.py`, `core/game.py`, `models/fitted.py`, `tests/test_starling_layer.py`, `tests/test_game_core.py`.

### Task 5: Strategy contract and scripted opponents

**Files:** Create `source/svg_training/core/strategy.py`, `source/svg_training/opponents/__init__.py`, `source/svg_training/opponents/scripted.py`; Test `tests/test_strategy.py`, `tests/test_scripted.py`.

**Interfaces — Consumes:** `ObsView`, `OBS_DIM`, `SvgGame` (Task 2). **Produces:**
```python
class Strategy(Protocol):
    team: str                                         # "guard" | "strike"
    name: str
    def reset(self, games: Tensor) -> None: ...       # [N] bool: these games just started; clear their memory
    def act(self, obs: Tensor) -> Tensor: ...         # [N, M_team, OBS_DIM] -> [N, M_team, 4] in [-1, 1]
class SplitStrategy:                                  # different strategies on fixed slices of the games
    def __init__(self, team: str, parts: list[tuple[Strategy, slice]])
def check_strategy(strategy: Strategy, game: SvgGame, steps: int = 50) -> None
    # raises AssertionError naming the broken rule: shape, range, finite, device, no autograd graph
# opponents/scripted.py — every one reads ONLY the observation (via ObsView), never the game object
class GuardMarkEdge:    # each Guard sits on the zone edge between the centre and the Strike drone it marks
class GuardMarkInside:  # the same at 0.6 × radius (just inside)
class GuardField:       # pulled to the edge point facing the nearest Strike drone, pushed off team-mates within 1.1 m (1/d²)
class GuardMirror:      # holds a ring at 1.2 × radius and copies its marked Strike drone's sideways (tangential) speed
class StrikeStraight:   # straight at the zone centre
class StrikeFlank:      # straight, unless the line passes within keepout + 0.3 m of the nearest Guard drone: then
                        # aims at a waypoint keepout + 0.3 m to the side of that drone, side = away from the zone line
class RandomActions:    # uniform in [-1, 1], own seeded generator
class ZeroActions:
REGISTRY: dict[str, type]   # "guard_mark_edge", "guard_mark_inside", "guard_field", "guard_mirror",
                            # "strike_straight", "strike_flank", "random", "zero"
def make_strategy(spec: str, team: str, cfg: GameCfg, num_games: int, device, seed: int) -> Strategy
    # spec = a REGISTRY name, or "package.module:ClassName" for outside code (same constructor arguments)
```
Marking: Guard `i` marks live Strike drone `i mod S_live` in slot order (tensor ops only; a missing Strike drone is skipped). Steering to a target point: `a = unit(target − own) × min(1, |target − own| / 0.25 m)`.

- [ ] **Failing tests:**
```python
def test_strategy_reset_mask_equals_done():            # Review Focus 4
    rec = RecordingStrategy("guard"); run 80 steps of lab4_open (Strike wins at 37)
    assert torch.equal(rec.resets[37], out_at_37.done) and rec.resets[0].all()
def test_check_strategy_catches_bad_output(): ...       # out-of-range, NaN, wrong shape each raise
def test_core_imports_no_training_library():            # Review Focus 5
    code = "import svg_training.core.game, svg_training.core.strategy, svg_training.opponents, sys; " \
           "assert not {'skrl', 'gymnasium', 'isaaclab'} & set(sys.modules)"
    assert subprocess.run([sys.executable, "-c", code], env=ENV).returncode == 0
def test_mark_edge_points_at_edge_target(): ...         # Strike at (+3, 0) rel zone, r 1, Guard at origin: a ≈ (+1, 0); at (1, 0): |a| < 0.05
def test_mark_inside_target_is_0_6_r(): ...
def test_marking_skips_missing_strike(): ...            # Strike slot 0 absent: every Guard marks Strike slot 1
def test_field_pushes_off_close_teammate(): ...         # team-mate 0.5 m to +y: a_y < 0
def test_mirror_copies_tangential_speed(): ...          # Strike moving +y tangentially, Guard on its ring: a_y > 0.5, radial |a| < 0.1
def test_straight_is_unit_vector_to_centre(): ...
def test_flank_goes_round_a_guard_on_the_line(): ...    # Guard on the line: |a_y| > 0.3 and a_x > 0; no Guard near: equals straight
def test_scripted_read_only_obs(): ...                  # act() is called with an obs tensor only and check_strategy passes for every REGISTRY entry
def test_make_strategy_module_spec(): ...               # "svg_training.opponents.scripted:ZeroActions" loads
```
- [ ] Run → fail; implement; run → pass.
- [ ] Lead commits the five files under **Files**.

### Task 6: Match loop, metrics, scoring tool and the scripted reference run

**Files:** Create `source/svg_training/core/play.py`, `source/svg_training/core/metrics.py`, `scripts/score.py`, `scripts/make_s2_figures.py` (one script, one function per figure, extended by Tasks 7, 8, 10); Test `tests/test_play.py`, `tests/test_score.py`; run record `records/<date>_s2_scripted_reference_record.md`; Modify `records/LEDGER.md`.

**Interfaces — Produces:**
```python
@dataclass class MatchResult:                        # one entry per game slot, its FIRST finished game
    outcome: Tensor; end_step: Tensor; band: Tensor  # [N] int8 / long / long
    closest_cross_m: Tensor; rule_breach: Tensor; filter_corrected_rate: Tensor   # [N]
def play_match(game: SvgGame, guard: Strategy, strike: Strategy, max_steps: int | None = None) -> MatchResult
    # resets both strategies on game.reset(), calls reset(done) then act(obs) once per team per step;
    # stops when every slot has finished once (one host check per 100 steps, outside the game step)
def hold_rate(outcome: Tensor) -> float
def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]
def summarise(res: MatchResult, by: tuple[str, ...] = ("band",)) -> list[dict]
    # rows: hold_rate, ci_low, ci_high, games, mean_end_step, closest_cross_m (min), rule_breach_rate, filter_rate
```
`scripts/score.py --guard <spec> --strike <spec> [--sizes 2v1,5v3] [--presets pure,starling] [--games-per-band 1000] [--bands lab,middle,large] [--scenario <name>] [--seed 0] [--no-local] [--device cuda] --out runs/<name>/` → `scores.json`, `scores.md` (one table per preset × size, a row per band, rates with intervals), and a line naming the game config file, its sha256 and whether a local file was used (name and sha256 only). Each band is its own batch (`band=` in `SvgGame`).

- [ ] **Failing tests:**
```python
def test_wilson_interval_known_values():
    assert wilson_interval(0, 1000) == pytest.approx((0.0, 0.00383), abs=1e-4)
    assert wilson_interval(500, 1000) == pytest.approx((0.4691, 0.5309), abs=1e-4)
@pytest.mark.parametrize("scenario, hold, end", [("lab4_open", 0.0, 37), ("large16_open", 0.0, 205),
                                                  ("lab4_block", 1.0, 1200), ("large16_block", 1.0, 1200)])
def test_score_fixed_scenarios_hand_worked(scenario, hold, end, tmp_path):   # design §7 condition 2
    run score.py --guard zero --strike strike_straight --scenario {scenario} --presets pure --no-local --device cpu
    rows = json.load(...); assert rows[0]["hold_rate"] == hold and rows[0]["mean_end_step"] == end
def test_play_counts_first_game_per_slot(): ...          # games that finish twice are counted once
def test_score_reports_local_file_by_sha_only(tmp_path): ...   # made-up local file: scores.md has its sha256, none of its values
def test_scenario_size_matches_band_reporting(): ...      # band=2 games all have side in [10, 16]
```
- [ ] Run → fail; implement; run → pass.
- [ ] **Run (INFO, no gates; `gates.toml` = `gates = []`):** after `nvidia-smi`, `score.py` for Guard {mark_edge, mark_inside, field, mirror, random} × Strike {straight, flank}, sizes 2v1 and 5v3, presets pure and starling, 1,000 games per band, seed 0, `--no-local`, into `runs/<date>_s2_scripted_reference/`. With the filter still at 1,000 sweeps the Starling half may take a few hours (at most 72 M game-steps at about 10,000 per second or less); run it in the background; it uses whatever `[starling_layer]` setting `configs/s2_game.toml` holds at launch, written in the record. Figure `docs/figures/s2_scripted_reference.png`: hold rate with intervals per band, one panel per preset × size. Record + ledger row (next free T).
- [ ] Lead commits code, tests, figure script, figure, record and `records/LEDGER.md`.

### Task 7: Faster safety filter

**Files:** Modify `source/svg_training/core/safety_filter.py` (one option), `scripts/filter_parity.py` (`run_port(..., **filter_kw)` only; defaults unchanged); Create `scripts/filter_speed.py`; Test `tests/test_safety_filter.py` (new tests), `tests/test_filter_speed.py`; run record `records/<date>_s2_filter_speed_record.md`; Modify `records/LEDGER.md`, and after a PASS `configs/s2_game.toml` `[starling_layer]`.

**Interfaces — Produces:**
```python
def filter_velocities(nominal_mps, pos_m, pair_mask, safety_radius_m, max_speed_mps, alpha=2.5, iterations=1000,
                      tolerance=2e-3, fixed=None, check_every: int = 0) -> FilterResult
    # check_every = k > 0: games where no pair is active skip the sweeps (their answer is the speed clamp);
    # every k sweeps the still-unconverged games are gathered into a smaller working batch, and the loop ends
    # when none is left or `iterations` is reached. Converged groups are frozen already, so the answer equals
    # the fixed loop's up to float rounding. One host sync per check (D10).
```
`scripts/filter_speed.py --gates configs/s2.toml --name <date>_s2_filter_speed [--phase accuracy|speed|both]`:
1. **Accuracy (7a, CPU, needs Task 1 only):** T2's scenes (`filter_parity.make_scenes(2000, 20261115)`), CMU's filter once (`run_original`), the port at each `iterations` candidate with `check_every = 0` and with the largest `check_every`; the five accuracy gates per candidate with `filter_parity.evaluate` and `cross_team_check`; `max_abs_dv_first_phase_mps` = `evaluate(...)["max_dv_subset_no_gs"]`.
2. **Speed (7b, GPU, needs Task 4):** `SvgGame` 5v3, 4,096 games, Starling layer on, random actions (seeded, drawn on the GPU in the timed loop), every (iterations, check_every) pair; game-steps/s from `bench/timing.py` with S0's warm-up and 2 repeats; also the share of time in the filter and the host syncs per step.
3. **Selection rule (fixed now):** the fastest candidate whose `iterations` passes all five accuracy gates and whose speed is ≥ 100,000 game-steps/s → **PASS**; it becomes `[starling_layer] filter_iterations / filter_check_every` in `configs/s2_game.toml` (the lead edits it after the record; noted in the record). Otherwise **FAIL**: the record lists the fastest accurate candidate and the fastest candidate, the 1,000-sweep setting stays, and the owner rules. S2 is not blocked.
4. Record (first line: "Simulator: training simulator, tier 1 (safety-filter port vs CMU cbf_filter.py on T2's scenes; S2 game with the Starling layer for speed)"), ledger row, figure `docs/figures/s2_filter_speed.png` (game-steps/s against sweeps, one line per `check_every`, accuracy PASS/FAIL marked, the 100,000 line drawn).

- [ ] **Failing tests:**
```python
def test_check_every_matches_fixed_loop():
    scenes = make_scenes(200, 7); nom, pos, mask, cap = _batch(scenes)
    a = filter_velocities(nom, pos, mask, 0.55, cap, iterations=300)
    b = filter_velocities(nom, pos, mask, 0.55, cap, iterations=300, check_every=8)
    assert (a.velocities - b.velocities).abs().max() <= 1e-5
    assert torch.equal(a.emergency, b.emergency) and torch.equal(a.corrected, b.corrected)
def test_check_every_zero_is_bit_identical(): ...         # check_every=0 equals the call without the argument, torch.equal
def test_inactive_games_return_clamped_nominal(): ...     # drones 10 m apart: velocities == nominal clamped to the cap
def test_check_every_with_per_game_mask(): ...            # [N, M, M] mask (drop-outs) gives the same answer as the fixed loop
def test_filter_speed_selection_rule(): ...               # fake measurement table → picks the fastest passing; none passing → "FAIL"
def test_filter_parity_defaults_unchanged(): ...          # run_port without filter_kw == before (T2 path untouched)
```
- [ ] Run → fail; implement; run → pass. Phase 7a may run as soon as Task 1 is approved; phase 7b after Task 4.
- [ ] Lead commits code, tests, figure script change, figure, record, ledger, and (after a PASS) `configs/s2_game.toml`.

### Task 8: Drone-model cross-check on the 12 November bag (exploratory, no refit)

**Files:** Create `source/svg_training/logs/__init__.py`, `source/svg_training/logs/mcap_reader.py`, `source/svg_training/logs/cdr.py`, `scripts/bag_check.py`; Test `tests/_mcap_writer.py` (test helper: writes a tiny uncompressed MCAP), `tests/test_mcap_reader.py`, `tests/test_bag_check.py`; run record `records/<date>_s2_bag_check_record.md`; Modify `records/LEDGER.md`.

**Interfaces — Produces:**
```python
@dataclass(frozen=True) class McapMessage:
    topic: str; log_time_ns: int; publish_time_ns: int; data: bytes
def list_topics(path: str | Path) -> dict[str, tuple[str, str]]          # topic -> (schema name, ros2msg text)
def iter_messages(path: str | Path, topics: set[str]) -> Iterator[McapMessage]
    # magic b"\x89MCAP0\r\n"; records = opcode u8 + length u64 LE; Schema 0x03, Channel 0x04, Message 0x05,
    # Chunk 0x06 (records inside parsed the same way); every other opcode skipped by length; a Chunk with a
    # compression other than "" raises ValueError. Read with mmap, read-only. Pure Python, no new package.
def compile_ros2msg(text: str) -> "CdrLayout"                             # flat primitives and fixed arrays only;
                                                                          # anything else raises NotImplementedError
def decode(layout: "CdrLayout", data: bytes, fields: tuple[str, ...]) -> dict[str, float | tuple[float, ...]]
    # 4-byte encapsulation header (little-endian CDR); each primitive aligned to its size from the header's end
```
`scripts/bag_check.py --bag <dir> --params params/real_exploratory_v0.toml --gates configs/s2.toml --name <date>_s2_bag_check`:
reads `/drone_{1,2}/fmu/in/trajectory_setpoint` (position, velocity, acceleration) and `/drone_{1,2}/fmu/out/vehicle_local_position` (x, y, vx, vy) with the layouts compiled **from the bag's own schemas**; NED → ENU as `scripts/fit_real_px4.py`; time base = bag log time (stated: the measured velocity crosses WiFi, so its apparent delay includes one network leg); legs with `px4_trajectory.find_legs` on the setpoint speed; windows 1.0 s before to 2.5 s after, cut at the midpoint to neighbours (as the S1 fit); setpoint held onto the 0.01 s grid; feed-forward `derived`; model = `px4_trajectory.simulate_windows` with the `[px4]` table **as written** (no fit call anywhere in the script); per leg: RMS over the active span, t63 error at start and stop; baselines (setpoint speed, and the same delayed 0.15 s); information only: the extra shift in [−0.10, 0.30] s that minimises RMS. Gates on `drone_2`; `drone_1` reported. Fewer than `min_legs` legs → INFO. Writes `runs/<name>/results.json`, figure `docs/figures/s2_bag_check.png` (measured, model and setpoint speed per leg), record (first line: "Observed in flight logs: real drone, 12 November 2026 rosbag; the training simulator's drone model checked, not refitted"), ledger row.

- [ ] **Failing tests:**
```python
def test_reader_round_trip(tmp_path):                    # helper writes 2 schemas, 2 channels, 50 messages in 2 chunks
    msgs = list(iter_messages(p, {"/a"})); assert [m.log_time_ns for m in msgs] == expected_times
def test_reader_refuses_compressed_chunk(tmp_path): ...  # compression "zstd" → ValueError
def test_cdr_alignment(): ...                            # uint64, bool, float32[3], uint8, float32: values back exactly (float32)
def test_cdr_unsupported_type_raises(): ...              # "string name" → NotImplementedError
def test_bag_check_reproduces_model_exactly(tmp_path):
    # synthetic bag: 3 setpoint legs at 19 Hz; "measured" velocity at 51 Hz = simulate() with the v0 parameters
    assert max(leg["rms_mps"] for leg in res["drone_2"]["legs"]) < 1e-3
def test_bag_check_finds_extra_delay(tmp_path): ...      # measured delayed 0.20 s more: best extra shift 0.20 ± 0.02 s
def test_bag_check_never_fits(): ...                     # the script's source has no "fit(" call and writes nothing under params/
def test_bag_check_too_few_legs_is_info(tmp_path): ...   # one leg → result "INFO"
```
- [ ] Run → fail; implement; run → pass.
- [ ] **Run:** `scripts/bag_check.py` on `~/flight_logs/2026-11-12/svg_20261112_094546` (CPU; the bag is read, never moved or changed). Record, ledger row, figure. The record says what the result can and cannot change: a PASS or FAIL here does not touch `params/`; the model of record still waits on the planned-push flight.
- [ ] Lead commits code, tests, figure script change, figure, record, ledger.

### Task 9: Adapters and the partner guide

**Files:** Create `source/svg_training/envs/skrl_adapter.py`, `source/svg_training/envs/gym_adapter.py`, `docs/PLUG_IN.md`, `scripts/make_s2_plug_in_flowchart.py`, `docs/figures/s2_plug_in_flow.png`; Test `tests/test_adapters.py`.

**Interfaces — Consumes:** `SvgGame`, `StepOut`, `Strategy`, `OBS_DIM`, `STATE_DIM`. **Produces:**
```python
class SvgSkrlEnv(skrl.envs.wrappers.torch.base.MultiAgentEnvWrapper):
    def __init__(self, game: SvgGame, train_teams: tuple[str, ...] = ("guard",),
                 opponents: dict[str, Strategy] | None = None)   # a team not trained must have an opponent
    possible_agents: list[str]          # "guard_0", …, then "strike_0", … (trained teams only)
    observation_spaces: dict[str, gymnasium.spaces.Box]   # (OBS_DIM,)
    action_spaces: dict[str, gymnasium.spaces.Box]        # (4,), low -1, high 1
    state_space: gymnasium.spaces.Box                      # (STATE_DIM,)
    def reset(self) -> tuple[dict[str, Tensor], dict]
    def step(self, actions: dict[str, Tensor]) -> tuple[dict, dict, dict, dict, dict]
        # obs [N, OBS_DIM]; reward, terminated, truncated [N, 1] per agent; truncated all False (every end is terminal)
    def state(self)                     # same return type as skrl's own Isaac Lab multi-agent wrapper (check in the env)
    def render(self, *args, **kwargs) -> None; def close(self) -> None
class SvgTeamVectorEnv(gymnasium.vector.VectorEnv):
    metadata = {"autoreset_mode": gymnasium.vector.AutoresetMode.SAME_STEP}
    def __init__(self, game: SvgGame, team: str, opponent: Strategy)
    # num_envs = game.num_games; single_observation_space Box((M_team * OBS_DIM,)); single_action_space Box(-1, 1, (M_team * 4,))
    def reset(self, *, seed: int | None = None, options: dict | None = None) -> tuple[Tensor, dict]
    def step(self, actions: Tensor) -> tuple[Tensor, Tensor, Tensor, Tensor, dict]
        # reward [N] = the team's mean drone reward; terminations [N]; truncations [N] False; info["outcome"] [N]
        # tensors stay on the game's device (as Isaac Lab's vector envs do); documented in PLUG_IN.md
```
Both adapters raise `ValueError` when the game has a `scenario` (STANDARDS §6 rule 4) and record the opponent mix in `info`.

`docs/PLUG_IN.md` (one page, plain words): the three layers (game, strategy contract, adapters) with the generated flowchart; "plug a strategy in" (a 15-line `Strategy` class, `check_strategy`, `score.py --guard my_pkg.my_mod:MyGuard`); "plug a training method in" (skrl and Gymnasium, ten lines each); what the observation holds (the 69-float table from `ObsView`); the partner-values rule (local file, never commit); what the scoring tool prints. Task 10 adds the worked example with the stand-in.

- [ ] **Failing tests:**
```python
def test_skrl_env_shapes_and_spaces(): ...           # 16 games 2v1 CPU: obs [16, 69] per agent, reward [16, 1], terminated bool
def test_skrl_ippo_runs_64_timesteps():
    # tiny IPPO (one 16-unit network per Guard name), RandomMemory(memory_size=16), SequentialTrainer(timesteps=64, headless=True)
    # → no exception, every loss finite
def test_gym_vector_env_api():
    env = SvgTeamVectorEnv(game, "guard", make_strategy("strike_straight", ...))
    obs, _ = env.reset(seed=3); obs2, _ = env.reset(seed=3); assert torch.equal(obs, obs2)
    assert env.single_action_space.shape == (8,) and obs.shape == (16, 2 * OBS_DIM)
def test_gym_autoreset_same_step(): ...              # lab-sized game, Strike straight, Guard zero: on the done step the obs is the new game's
def test_adapters_refuse_scenarios(): ...
def test_core_imports_no_training_library(): ...     # re-run from Task 5, now that the adapters import skrl and gymnasium
```
- [ ] Run → fail; implement; run → pass. `panel-newcomer-reader` reads `PLUG_IN.md` once; fix where it got lost.
- [ ] Lead commits the files under **Files**.

### Task 10: Stand-in trainer (pipe test)

**Files:** Create `scripts/train_standin.py`, `source/svg_training/opponents/learned.py`; Test `tests/test_train_standin.py`; Modify `docs/PLUG_IN.md` (worked example), `scripts/make_s2_figures.py`; run record `records/<date>_s2_standin_record.md`; Modify `records/LEDGER.md`.

**Interfaces — Produces:**
```python
class SkrlPolicyStrategy:                       # a saved stand-in, behind the strategy contract
    def __init__(self, run_dir: str | Path, num_games: int, device, deterministic: bool = True)
        # reads interface.toml; refuses a team size other than the one trained (one network per Guard slot)
    team = "guard"; name: str
    def reset(self, games: Tensor) -> None; def act(self, obs: Tensor) -> Tensor
# opponents/__init__.py: make_strategy(spec, ...) also accepts a run folder holding interface.toml -> SkrlPolicyStrategy
```
`scripts/train_standin.py --config configs/s2.toml --seed <s> --name <date>_s2_standin_seed<s> [--timesteps-override <n>] [--device cuda]`: `SvgGame` with the `[standin]` settings (`--no-local` always), Strike = `SplitStrategy` (games [0, N/2) `strike_straight`, [N/2, N) `strike_flank`), `SvgSkrlEnv(train_teams=("guard",))`, skrl IPPO (one Gaussian policy and one value network per Guard name, `hidden` ELU layers, `RunningStandardScaler` on observations and values, the `[standin]` PPO settings), `SequentialTrainer(timesteps = game_steps_per_seed // num_games, headless=True)`, wall-clock cap → stop and keep the last checkpoint (written in the record, not an ABORT). Every 20 updates: hold rate of the current policy on 256 evaluation games (the one metrics module), logged for the learning-curve figure. Saves `runs/<name>/agent.pt` and `interface.toml` (STANDARDS §3 rule 1: interface version 0, obs layout `ObsView` table, action scaling per team, tick 0.05 s, game config file + sha256, preset "pure", parameter set "none (pure rules)", git commit, seed, `pipe_test = true`).

Evaluation (gates `[standin_gates]`, copied to `runs/<date>_s2_standin/gates.toml` before the first seed starts): for each seed and each behaviour in `behaviours`, `score.py` with `--guard <run_dir>` (loaded as `SkrlPolicyStrategy`) and with `--guard random`, 2v1, preset pure, 1,000 games per band, evaluation seed = seed + 1000. **PASS** when, for all 3 seeds and both behaviours, trained hold rate − random hold rate ≥ 0.20 and the trained interval's lower bound > the random interval's upper bound. The Starling layer and `guard_mark_edge` are scored too, as information. Figures: learning curves (hold rate against game-steps, one line per seed) and final bars (trained, random, `guard_mark_edge`, per behaviour, with intervals).

- [ ] **Failing tests:**
```python
def test_standin_smoke(tmp_path):                 # CPU, 32 games, --timesteps-override 200
    run train_standin.py; assert (run_dir / "agent.pt").exists()
    meta = tomllib.loads((run_dir / "interface.toml").read_text())
    assert meta["pipe_test"] is True and meta["interface_version"] == 0 and meta["preset"] == "pure"
    check_strategy(SkrlPolicyStrategy(run_dir, 32, "cpu"), SvgGame(cfg, 32, 2, 1, device="cpu"))
def test_learned_refuses_other_team_size(tmp_path): ...
def test_make_strategy_loads_run_folder(tmp_path): ... # make_strategy(str(run_dir), "guard", ...) is a SkrlPolicyStrategy
def test_standin_ignores_local_file(tmp_path): ...    # a made-up local file present: interface.toml records local_file = none
def test_standin_gate_rule(): ...                     # fake score tables: one seed short of 0.20 → FAIL; overlapping intervals → FAIL
```
- [ ] Run → fail; implement; run → pass.
- [ ] **Run:** `nvidia-smi` (no simulator, headless); seeds 1, 2, 3 one after another in the background; evaluation; record (first line: "Simulator: training simulator, tier 1, pure partner rules (committed neutral values); stand-in pipe test, not a strategy of record"), one ledger row for the three seeds, figures. Wording everywhere: "stand-in" and "pipe test"; never "the policy", never NUS's result.
- [ ] Add the worked example to `docs/PLUG_IN.md` (load the stand-in as a `Strategy`, score it, retrain it with the same command).
- [ ] Lead commits code, tests, guide, figures, record, ledger.

### Task 11: Documents and final review

**Files:** Create `docs/S2_RESULTS.md`; Modify `docs/claude/HANDOFF.md`, `README.md`, `CLAUDE.md` (status lines), `docs/WHAT_WE_DID.md` (new chapter "S2: the game and the plug-in point"), `docs/GLOSSARY.md`, `docs/DESIGN.md` §8 (the S2 row, as the design asks), `STANDARDS.md` §4 (rows S2 settles point to `configs/s2_game.toml`; status labels change only with the owner's word).

- [ ] `docs/S2_RESULTS.md` for a newcomer: what was built (the plug-in flowchart), then one short section per run (filter speed, bag check, scripted reference, stand-in), each with its generated figure, a caption of at most 400 characters and a 2–3 sentence reading; the done-conditions table of design §7 with PASS / FAIL / INFO and the record link; what S2 does not do (below); what waits on the owner (filter ruling if Task 7 failed, D1 against the report, NUS's units).
- [ ] GLOSSARY: partner rules preset, Starling layer, push-apart, size band, strategy contract, scripted opponent, stand-in (pipe test), hold rate, rule breach, `check_every`.
- [ ] Docs check: no partner number anywhere (`test_local_values_not_in_tracked_files` passes with the local file present), wording per STANDARDS §2, every number traced to a record, simulator named.
- [ ] Final review: `train-gatekeeper` reads each S2 record with its `gates.toml` and ledger row; a code review of the whole S2 diff (superpowers:requesting-code-review) against this plan and the design; `panel-newcomer-reader` reads `S2_RESULTS.md` and `PLUG_IN.md`. Fix rounds until no Critical or Important finding is open. Full test suite output quoted in HANDOFF; STANDARDS §11 checklist ticked.
- [ ] Lead commits the documents with explicit paths; HANDOFF copy refreshed in `~/Downloads/`.

## What S2 does not do

- No NUS training method, no self-play league, no side-quest training (contact tags exist as a tested game mode only).
- No varied team sizes inside one game batch (each `SvgGame` has fixed G and S; the observation is padded to 5 + 3 so one network can later serve every size); the STANDARDS §4 size range 1–5 / 1–3 per game waits.
- The design §4b "count time in the zone" Strike-win switch is not built (the partner rule is one step in the zone).
- No limited view of other drones (`obs_view` has one value, `full`); no range rays, obstacles or worlds (S3–S4); no tier 2 game; no export to AirStack (S5).
- No refit of the drone model: the bag check only checks `real_exploratory_v0`; the model of record waits on the planned-push flight.
