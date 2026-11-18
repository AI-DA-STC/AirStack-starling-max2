"""Test constants and made-up partner values for the Phase 5 method port (tasks M1-M5). The numeric-literal scan (G2) covers
tests/test_nus_*.py, so every number those tests need lives here.

Method markers follow tests/_nus_markers.py: each float is derived from a hash of its key, with six significant digits so that a
leak is easy to find in text. Integer keys get small values that keep tiny CPU runs fast; ranges only keep the method valid.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

from _nus_markers import _unit

# ------------------------------------------------------------------------------------------------ M1: method markers
_FLOAT_RANGES = {
    "win_rate_ema": (0.11, 0.49),
    "initial_log_std": (-0.79, -0.31),
    "log_std_min": (-6.9, -4.1),
    "log_std_max": (1.1, 2.9),
    "output_init_gain": (0.011, 0.049),
    "init_std_scale": (1.01, 1.29),
    "init_truncation": (1.61, 2.39),
    "ppo_clip": (0.11, 0.29),
    "entropy_coef": (0.011, 0.049),
    "critic_loss_coef": (0.31, 0.69),
    "max_grad_norm": (0.31, 0.69),
    "weight_decay": (0.0011, 0.0049),
    "advantage_epsilon": (1.1e-6, 9.9e-6),
    "advantage_clip": (11.1, 29.9),
    "log_ratio_clip": (11.1, 29.9),
    "guard_actor_lr": (1.1e-4, 4.9e-4),
    "guard_critic_lr": (5.1e-4, 9.9e-4),
    "guard_gamma": (0.951, 0.989),
    "guard_gae_lambda": (0.911, 0.949),
    "guard_advantage_weight": (1.01, 1.29),
    "strike_actor_lr": (1.1e-4, 4.9e-4),
    "strike_critic_lr": (5.1e-4, 9.9e-4),
    "strike_gamma": (0.951, 0.989),
    "strike_gae_lambda": (0.911, 0.949),
    "strike_advantage_weight": (1.01, 1.29),
    "shaping_scale": (0.11, 0.29),
    "inside_penalty": (1.11, 1.49),
    "clean_timeout_reward": (0.11, 0.49),
    "first_reach_penalty": (2.11, 2.89),
}
METHOD_INTS = {"generations": 3, "updates_per_generation": 3, "max_learned_opponents": 3, "recent_opponents": 1,
               "episodes_per_opponent": 2, "minimum_rollout_batch": 6, "selection_interval_updates": 2,
               "selection_games_per_opponent": 3, "max_pool_slots": 5, "rank_round_digits": 9, "hidden_dim": 22,
               "hidden_blocks": 2, "ppo_epochs": 2, "ppo_minibatches": 2}
METHOD_OTHER = {"first_team": "guard", "activation": "Mish", "use_layernorm": True, "compute_dtype": "float32",
                "zero_init_output": False}


def marker_method_value(key: str) -> float:
    lo, hi = _FLOAT_RANGES[key]
    for salt in range(100):
        v = float(f"{lo + (hi - lo) * _unit('method/' + key, salt):.6g}")
        if len(f"{abs(v):.6g}".replace(".", "").replace("e-0", "").strip("0")) >= 6:
            return v
    raise RuntimeError(key)


def marker_method(**changes) -> dict:
    values = {k: marker_method_value(k) for k in _FLOAT_RANGES}
    values |= METHOD_INTS | METHOD_OTHER
    values.update(changes)
    return values


def method_marker_strings(values: dict) -> list[str]:
    out = []
    for v in values.values():
        if isinstance(v, float):
            out += [repr(v), f"{v:.6g}", f"{v:.6g}".replace("e-0", "e-")]
    return sorted(set(out))


def write_method_toml(path, values: dict) -> None:
    lines = []
    for k, v in values.items():
        if isinstance(v, bool):
            lines.append(f"{k} = {str(v).lower()}")
        elif isinstance(v, str):
            lines.append(f'{k} = "{v}"')
        else:
            lines.append(f"{k} = {v!r}")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines) + "\n")


STATE_FIELDS = ["p_pos", "done", "step", "area_pos", "prev_p_pos", "agent_spawn_center", "adversary_spawn_center", "breach"]


def fake_run_config(values: dict, **changes) -> dict:
    """A resolved run config.json with the partner's key layout and the marker method values."""
    team = {"guard": "defender", "strike": "attacker"}
    cfg = {
        "train_team": team[values["first_team"]], "include_apf_in_pool": True, "scripted_opponent": "apf",
        "selection_action_mode": "deterministic", "apex": {"enabled": False},
        "jax": {"compute_dtype": values["compute_dtype"]},
        "environment": {"env": {"global_state_fields": list(STATE_FIELDS)}},
        "trainer": {
            "lr_schedule": {"kind": "constant"}, "per_slot_advantage_norm": False, "max_pool_slots": values["max_pool_slots"],
            "ppo_epochs": values["ppo_epochs"], "ppo_num_mini_batch": values["ppo_minibatches"], "ppo_clip": values["ppo_clip"],
            "entropy_coef": values["entropy_coef"], "critic_loss_coef": values["critic_loss_coef"],
            "max_grad_norm": values["max_grad_norm"],
            "policy": {"hidden_dim": values["hidden_dim"], "n_hidden_layers": values["hidden_blocks"],
                       "activation_type": values["activation"], "use_layernorm": values["use_layernorm"],
                       "initial_log_std": values["initial_log_std"], "zero_init_output": values["zero_init_output"]},
            "rewards": {"defender": {"attacker_distance_scale": values["shaping_scale"], "breach_penalty": values["inside_penalty"],
                                     "clean_timeout_reward": values["clean_timeout_reward"],
                                     "first_breach_penalty": values["first_reach_penalty"]}},
        },
        "self_play": {
            "generations": values["generations"], "updates_per_generation": values["updates_per_generation"],
            "max_learned_opponents": values["max_learned_opponents"], "recent_opponents": values["recent_opponents"],
            "episodes_per_opponent": values["episodes_per_opponent"], "minimum_rollout_batch": values["minimum_rollout_batch"],
            "training_win_rate_ema": values["win_rate_ema"], "initial_archive": [],
            "evaluation": {"interval_updates": values["selection_interval_updates"],
                           "episodes_per_opponent": values["selection_games_per_opponent"]},
            "scripted_opponents": {"attacker": None, "defender": None},
        },
    }
    for partner, ours in (("defender", "guard"), ("attacker", "strike")):
        cfg["trainer"][partner] = {"actor_lr": values[f"{ours}_actor_lr"], "critic_lr": values[f"{ours}_critic_lr"],
                                   "task_gamma": values[f"{ours}_gamma"], "task_gae_lambda": values[f"{ours}_gae_lambda"],
                                   "task_advantage_weight": values[f"{ours}_advantage_weight"]}
    for dotted, value in changes.items():
        node = cfg
        *head, last = dotted.split(".")
        for part in head:
            node = node.setdefault(part, {})
        node[last] = value
    return cfg


def write_fake_learner_sources(clone, values: dict) -> Path:
    """The five partner source files the method script parses, with marker constants in the same code shapes."""
    clone = Path(clone)
    jax_dir, runner_dir = clone / "ma_skills" / "jax", clone / "ma_skills" / "runner"
    jax_dir.mkdir(parents=True, exist_ok=True)
    runner_dir.mkdir(parents=True, exist_ok=True)
    (jax_dir / "policy.py").write_text(textwrap.dedent(f"""
        class TeamActor(nn.Module):
            obs_dim: int
            initial_log_std: float = -0.5
            log_std_min: float = {values['log_std_min']!r}
            log_std_max: float = {values['log_std_max']!r}
            def __call__(self, obs):
                init = nn.initializers.orthogonal({values['output_init_gain']!r})
                return jnp.clip(raw, self.log_std_min, self.log_std_max)
        """))
    t = values["init_truncation"]
    (jax_dir / "nn.py").write_text(textwrap.dedent(f"""
        def trunc_normal_in(key, shape, dtype=jnp.float32):
            fan_in = shape[-2]
            std = jnp.asarray({values['init_std_scale']!r} / jnp.sqrt(fan_in), dtype)
            return jax.random.truncated_normal(key, -{t!r}, {t!r}, shape, dtype) * std
        """))
    a, r = values["advantage_clip"], values["log_ratio_clip"]
    (jax_dir / "training.py").write_text(textwrap.dedent(f"""
        def _masked_normalize(value, mask):
            mean = _masked_mean(value, mask)
            normalized = (value - mean) / jnp.sqrt(variance + {values['advantage_epsilon']!r})
            return jnp.where(mask > 0, jnp.clip(normalized, -{a!r}, {a!r}), 0.0)
        def policy_update():
            def actor_loss(params):
                log_ratio = jnp.clip(selected - b_old, -{r!r}, {r!r})
                surrogate = jnp.clip(ratio, 1.0 - config.clip, 1.0 + config.clip)
                return log_ratio
        """))
    (runner_dir / "fixed_opponent_runner.py").write_text(textwrap.dedent(f"""
        class FixedOpponentRunner:
            def _optimizer(self, learning_rate):
                return optax.chain(optax.clip_by_global_norm(1.0), optax.adamw(rate, weight_decay={values['weight_decay']!r}))
        """))
    (runner_dir / "ensemble_self_play_runner.py").write_text(textwrap.dedent(f"""
        class EnsembleSelfPlayRunner:
            def _evaluate(self):
                rank = tuple(round(result[key], {values['rank_round_digits']}) for key in ("a", "b"))
                return rank
        """))
    return clone


def write_fake_run(folder, values: dict, **changes) -> Path:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "config.json").write_text(json.dumps(fake_run_config(values, **changes), indent=2))
    return folder


UNSUPPORTED_RUNS = {  # dotted override -> the key the refusal names
    "apex.enabled": True,
    "trainer.lr_schedule.kind": "cosine",
    "trainer.per_slot_advantage_norm": True,
    "include_apf_in_pool": False,
    "scripted_opponent": "mirror_rim",
    "selection_action_mode": "sampled",
    "environment.env.global_state_fields": ["p_pos"],
}
NOT_INTEGER = 1.5


# ------------------------------------------------------------------------------------------------ M5: synthetic cross-play numbers
# The frozen [gates.phase5_method_match] numbers, restated so a test can check the loader reads them (configs/nus_port.toml).
FROZEN_GATE = {"generations": 8, "games_per_pairing": 1000, "confidence": 0.95, "b_window": (1, 6), "b_max_worst_win": 0.5,
               "b_max_consecutive": 1, "t_quantile": 2.776, "sd_floor": 0.02, "spread_ratio_max": 4.36}
TOL = 1e-6
# pooled t interval, 3 v 3 (hand computation: means 0.35 and 0.363333, sd 0.05 and 0.0802081, pooled sd 0.0668331, se 0.0545690)
POOLED_CASE = {"ours": [0.30, 0.35, 0.40], "reference": [0.28, 0.37, 0.44],
               "diff": -0.0133333333, "low": -0.1648169286, "high": 0.1381502620, "spread_ratio": 0.6233787262}
# zero spread on both sides: both floored to 0.02, half width = 2.776 x 0.02 x sqrt(2/3)
FLOOR_CASE = {"ours": [0.5, 0.5, 0.5], "reference": [0.5, 0.5, 0.5], "half": 0.0453318902, "spread_ratio": 1.0}
FLOOR_FAIL_CASE = {"ours": [0.1, 0.1, 0.1], "reference": [0.5, 0.5, 0.5]}
WIDE_CASE = {"ours": [0.0, 0.5, 1.0], "reference": [0.48, 0.5, 0.52], "half": 0.8020030071, "spread_ratio": 25.0}
# Welch, six of ours against three reference seeds (scipy t quantile at the Welch-Satterthwaite degrees of freedom)
WELCH_CASE = {"ours": [0.30, 0.35, 0.40, 0.42, 0.31, 0.38], "reference": [0.28, 0.37, 0.44],
              "diff": -0.0033333333, "low": -0.1716913184, "high": 0.1650246517, "df": 2.7637719302, "spread_ratio": 0.6056726659}
FOUR_SEEDS = [0.3, 0.4, 0.5, 0.6]

# 5.1-b: failed generations in the window -> lineage passes
WORST_PASS, WORST_FAIL = 0.9, 0.5  # 0.5 itself fails (at most the limit)
B_PATTERNS = [((2, 4), False), ((2, 6), True), ((3, 4), True), ((6, 8), True), ((1, 3), False), ((5,), True), ((), True),
              ((1, 3, 5), False), ((2, 3, 4, 5), False)]
GENERATIONS = tuple(range(1, 9))

GAMES = 100
REF = ("s1", "s2", "s3")
OURS = ("o1", "o2", "o3")
SIX = ("o1", "o2", "o3", "o4", "o5", "o6")
GUARD_STRENGTH = {"s1": 0.30, "s2": 0.40, "s3": 0.50}   # synthetic: reach(L guard, M strike) = (strike[M] + 1 - guard[L]) / 2
STRIKE_STRENGTH = {"s1": 0.50, "s2": 0.70, "s3": 0.90}
APF_HOLD = 0.95    # every Guard entry against the APF Strike team
APF_REACH = 1.0    # every Strike entry against the APF Guard team
APF_OUTSIDE = 0.5  # an APF hold rate far outside the reference envelope


def _entry(lineage, generation):
    from svg_training.nus.crossplay import Entry
    return Entry(lineage, generation, "guard" if generation % 2 else "strike")


def synthetic_crossplay(lineages, guard_strength, strike_strength, games=GAMES, excluded=(), apf_hold=None, apf_reach=None,
                        own_rule="last_mover"):
    """A full matrix over the lineages' entries (generations 1-8). Across lineages the reach rate of a cell depends only on the two
    lineages; inside a lineage the later-trained policy wins every game ("last_mover"), or the earlier one ("first_mover")."""
    import numpy as np
    from svg_training.nus.crossplay import CrossPlay
    guards = [_entry(k, g) for k in lineages for g in GENERATIONS if g % 2]
    strikes = [_entry(k, g) for k in lineages for g in GENERATIONS if not g % 2]
    reached = np.zeros((len(guards), len(strikes)))
    for i, g in enumerate(guards):
        for j, s in enumerate(strikes):
            if g.lineage == s.lineage:
                later_strike = s.generation > g.generation
                rate = float(later_strike if own_rule == "last_mover" else not later_strike)
            else:
                rate = (strike_strength[s.lineage] + 1 - guard_strength[g.lineage]) / 2
            reached[i, j] = round(min(max(rate, 0.0), 1.0) * games)
    apf_hold = apf_hold or {}
    apf_reach = apf_reach or {}
    apf_strike = np.array([round((1 - apf_hold.get(g, APF_HOLD)) * games) for g in guards], float)
    apf_guard = np.array([round(apf_reach.get(s, APF_REACH) * games) for s in strikes], float)
    return CrossPlay(guards, strikes, reached, games, apf_strike, apf_guard, frozenset(excluded))


def copy_strengths(mapping):
    """Our lineages o1-o3 with the strengths of s1-s3 (a copy of the method)."""
    return mapping | {f"o{i}": mapping[f"s{i}"] for i in (1, 2, 3)}


def own_pools(xp, lineages):
    """Each entry's training pool: the other team's entries of its own lineage with a smaller generation (8 generations never exceed a
    pool cap)."""
    pools = {}
    for k in lineages:
        for team, other in (("guard", "strike"), ("strike", "guard")):
            for e in xp.entries(k, team):
                pools[e] = [o for o in xp.entries(k, other) if o.generation < e.generation]
    return pools


# 5.1-d with a failed conversion: our guard lineage o1 holds 1.0 against s1, 0.5 against s2 and 0 against s3; one s1 Strike entry
# failed conversion. Panels (left out s1, s2, s3) hold 0.25, 3/7 and 5/7; their mean 0.4642857 differs from the pooled 5/11.
PANEL_HOLD = {"s1": 1.0, "s2": 0.5, "s3": 0.0}
PANEL_FAILED = ("s1", 2)
PANEL_MEANS = (0.25, 3 / 7, 5 / 7)
PANEL_VALUE = (0.25 + 3 / 7 + 5 / 7) / 3
POOLED_OVER_ENTRIES = 5 / 11
LAST_MOVER_ALL, LAST_MOVER_NONE = 1.0, 0.0
SHUTOUT_MARGIN = 0.05


# ------------------------------------------------------------------------------------------------ M2: training environment
TRAIN_GAMES = 6
TRAIN_TAG = "train_hangar_3v3"   # runs/nus_port/fixtures/<tag>.npz, recorded with scripts/nus_record_fixtures.py --train-fields
REWARD_TOL = 1e-5                # plan task M2: rewards within 1e-5
STATE_TOL = 1e-4                 # plan task M2: positions (and the central state, which holds them) within 1e-4 units
GAMMA_SHAPING = 0.97


def marker_method_object(**changes):
    from svg_training.nus.method_cfg import METHOD_KEYS, NusMethod
    values = marker_method(**changes)
    return NusMethod(**{k: values[k] for k in METHOD_KEYS})


def marker_env(tmp_path, **changes):
    from _nus_markers import load_marker_files
    from svg_training.nus.replica_train import NusTrainEnv
    rules, deploy, _, _ = load_marker_files(tmp_path / "inputs")
    return NusTrainEnv(rules, deploy, marker_method_object(**changes))


# ------------------------------------------------------------------------------------------------ M3: learner
# GAE by hand: gamma 0.5, lambda 0.5, one game, three steps, done on the last; rewards 1, 0, 2; values 0.5, 1, 1
GAE_CASE = {"gamma": 0.5, "lam": 0.5, "rewards": [1.0, 0.0, 2.0], "values": [0.5, 1.0, 1.0], "dones": [0, 0, 1],
            # deltas: 1 + 0.5 - 0.5 = 1, 0 + 0.5 - 1 = -0.5, 2 - 1 = 1; advantages from the end: 1, -0.5 + 0.25 = -0.25, 1 - 0.0625
            "advantages": [0.9375, -0.25, 1.0], "returns": [1.4375, 0.75, 2.0]}
LATENT_BIG = 30.0          # tanh saturates in float32 here; the Jacobian must stay finite
NORMAL_SAMPLES = 64
UNIT_TOL = 1e-5
CLIP_SCALE = 10.0
PARITY_DTYPES = ("float32", "bfloat16")
# one-update parity (plan task M3): losses within 1e-3 relative and the update within bfloat16 tolerance, PROPOSED 2e-2 relative on
# the update's norm. The policy loss of a first update is -mean(normalised advantage), about 0, so it is compared in absolute terms
# (the advantages have unit scale). The float32 twin proves the logic at a tight tolerance (PROPOSED here: 1e-4 on values, losses and
# gradients, 1e-3 on the update, whose first AdamW step is close to lr x sign(gradient) and so flips for near-zero gradients). The
# clip and AdamW on the partner's own gradients: 1e-4 relative, the float32 resolution of a parameter delta (ulp of a weight near
# 0.05 is 3.7e-9 against steps of the order of the learning rate).
PARITY_TOL = {
    "float32": {"values": 1e-4, "loss_rel": 1e-4, "grad_rel": 1e-4, "delta_rel": 1e-3, "adamw_rel": 1e-4, "gae": 1e-5},
    "bfloat16": {"values": None, "loss_rel": 1e-3, "grad_rel": None, "delta_rel": None, "adamw_rel": 1e-4, "gae": 1e-5},
}
BF16_DELTA_PROPOSED = 2e-2   # plan task M3, PROPOSED; measured 18 Nov 2026: actor 0.049, critic 0.033 (see m3_parity_bfloat16.json)
NOISE_FLOOR_FACTOR = 2       # lead's rule v2, 18 Nov 2026: our bfloat16 update error <= 2 x the partner's bfloat16 floor
NOISE_FLOOR_SEEDS = (1, 2, 3, 4, 5)   # rule v2: K = 5 relative perturbations, seeds 1 to 5
SEEDS = (3, 4, 5, 6)  # torch generator seeds of the unit tests


# ------------------------------------------------------------------------------------------------ M4: self-play
SELECTION_TABLE = "nus_select_opponents.json"   # tests/data/, recorded once with scripts/nus_record_selection_table.py
# games per update = slots x max(per opponent, ceil(minimum / slots)), by hand: (slots, per opponent, minimum, games)
BATCH_CASES = [(1, 6, 100, 100), (2, 6, 100, 100), (3, 6, 100, 102), (5, 6, 100, 100), (7, 6, 100, 105), (9, 6, 100, 108),
               (16, 6, 100, 112), (1, 2, 6, 6), (4, 2, 6, 8)]   # made-up sizes, not the partner's
STAGE_SEED_CASES = [(1001, 1, 1001), (1001, 8, 1008), (101, 3, 103)]
SELFPLAY_STOP_AFTER = 4   # updates before an interruption in the resume test (inside generation 2 of the marker schedule)

# ------------------------------------------------------------------------------------------------ M5: scoring on the replica
SCORE_GAMES = 8
SCORE_CHUNK = 3          # pairings per batch: smaller than the pairing count, so chunking is exercised
STARTS_SEED = 20261120   # [gates.phase5_reference_rebuild] starts_seed
RUN_SEED, OTHER_RUN_SEED = 1001, 2001   # lineage seeds of the self-play tests (spaced like plan P5-12)


# ------------------------------------------------------------------------------------------------ M6: R0 reference rebuild
R0_GAMES = 4             # --games-override of the tests (not of record)
R0_CHUNK = 5
R0_ROWS = 10000          # [gates.phase3_converted_policy] observations_per_team (frozen), so the tests meet the real row rule
R0_SPOIL = 2             # a spoiled entry's reference actions are moved by this many times the gate's limit


def write_fake_reference(tmp_path, runs, generations, spoil=()):
    """NUS's output layout (``<outputs>/<run>/archive/<gggg>_<defender|attacker>``) with synthetic archive entries, and reference
    actions for each: the converted actor's own actions on replica observations (so gate (a) passes), moved for the entries in
    ``spoil`` ((run, generation) pairs). Returns (outputs dir, actions dir, rules path, deploy path)."""
    import math
    import numpy as np
    import torch
    from _nus_markers import load_marker_files, write_synthetic_checkpoint
    from svg_training.nus.actor import NusActor
    from svg_training.nus.replica import NusReplica
    rules, deploy, rules_path, deploy_path = load_marker_files(tmp_path / "inputs")
    sim = NusReplica(rules)
    outputs, actions = tmp_path / "outputs", tmp_path / "runs" / "ref" / "actions"
    states = math.ceil(R0_ROWS / min(rules.guard_count, rules.strike_count))
    state = sim.reset(states, generator=torch.Generator().manual_seed(len(runs)))
    state = sim.step(state, torch.randn(states, sim.num_actors, 2, generator=torch.Generator().manual_seed(len(runs) + 1)))
    obs = sim.observe(state)
    for r, run in enumerate(runs):
        for g in generations:
            team, partner = ("guard", "defender") if g % 2 else ("strike", "attacker")
            folder = write_synthetic_checkpoint(outputs / run / "archive" / f"{g:04d}_{partner}", team, kind="archive", seed=r * 16 + g)
            actor = NusActor.load(folder, team=team, rules=rules, deploy=deploy)
            own = obs[:, : rules.guard_count] if team == "guard" else obs[:, rules.guard_count:]
            acts = actor.act_units(own)
            if (run, g) in spoil:
                acts = acts + R0_SPOIL * 0.02
            out = actions / run / folder.name
            out.mkdir(parents=True, exist_ok=True)
            np.savez(out / f"actions_{team}.npz", obs=own.numpy().astype(np.float32), actions=acts.numpy().astype(np.float32))
    return outputs, actions, rules_path, deploy_path


# ------------------------------------------------------------------------------------------------ M7: trainer
TRAIN_GENERATIONS = 2
PROBE_UPDATES = 2
TINY_VARIANTS = """
[gates.phase5_method_match]
generations = 8
[gates.phase5_method_variants]
games_per_update = 10
updates_per_generation = { s51b = 4, s51c = 3 }
selection_evaluations_after_update = { s51b = [2, 4], s51c = [3] }
"""
TINY_CAP = 1e-9          # GPU-hours: any estimate is above it
HOUR = 3600.0
LOG_ROWS = [  # (group, device, start s, end s): two overlapping CUDA jobs (one hour of union), a CPU job and another group
    ("s51", "cuda:0", 0.0, 2700.0), ("s51", "cuda", 900.0, 3600.0), ("s51", "cpu", 0.0, 36000.0), ("variants", "cuda", 0.0, 7200.0)]
LOG_S51_HOURS = 1.0


# ------------------------------------------------------------------------------------------------ pauses (owner, 18 Nov 2026)
# events (event, time s): paused 100-160 and 300-(open)
PAUSE_EVENTS = [("pause", 100.0), ("pause", 120.0), ("resume", 160.0), ("resume", 170.0), ("pause", 300.0)]
PAUSE_NOW = 400.0
PAUSED_SPANS = [(100.0, 160.0), (300.0, 400.0)]
EFFECTIVE_CASE = (50.0, 350.0, 300.0 - 60.0 - 50.0)        # start, end, wall clock less the two pauses inside
# gpu_hours rows: two overlapping CUDA jobs 0-3600 s and 1800-5400 s (union 5400 s), one CPU row; a pause 3600-4500 s inside
GPU_ROWS = [("s51", "cuda", 0.0, 3600.0), ("s51", "cuda:0", 1800.0, 5400.0), ("s51", "cpu", 0.0, 36000.0)]
GPU_PAUSES = [("pause", 3600.0), ("resume", 4500.0)]
GPU_HOURS_AFTER_PAUSES = 1.25


# ------------------------------------------------------------------------------------------------ M8: scoring the arms
SYNTHETIC_HIDDEN = 46     # the synthetic NUS checkpoints' width (tests/_nus_markers.py MARKER_ARCH): our arm must match it to share
                          # one stacked forward with the reference
C0_RUN = "2026-11-18_c0_selfplay_3v3_seed{seed}"


def write_fake_ours(phase5_dir, stage, seeds, env, method, generations):
    """Our archive layout (nus/selfplay.py) for each seed: untrained actors as archived entries, a state file and a status file."""
    import json
    import torch
    from svg_training.nus.mappo import MappoActor
    for seed in seeds:
        folder = phase5_dir / stage / f"seed{seed}"
        archive = []
        for g in range(1, generations + 1):
            team = "guard" if g % 2 else "strike"
            entry = folder / "archive" / f"{g:04d}_{team}"
            entry.mkdir(parents=True, exist_ok=True)
            actor = MappoActor(env.obs_dim, method, env.deploy.layernorm_epsilon, torch.Generator().manual_seed(seed + g))
            torch.save(actor.state_dict(), entry / "actor.pt")
            archive.append({"generation": g, "team": team, "path": str(entry), "best_update": 1})
        (folder / "self_play_state.json").write_text(json.dumps({"schema": 1, "seed": seed, "archive": archive, "active": None}))
        (folder / "status.json").write_text(json.dumps({"status": "complete", "nonfinite_abort": False}))
