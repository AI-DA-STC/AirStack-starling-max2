"""The partner's training-method values (NUS port Phase 5, task M1): read from one git-ignored local file, never written in committed
text (G1).

Template: ``configs/nus_method.template.toml`` (every value the string "LOCAL"). Real file: ``configs/local/nus_method.toml``, written by
``scripts/nus_make_local_method.py`` from a reference run's resolved ``config.json`` and from constants that sit in the partner's code
(parsed, never imported or copied). The loader refuses a missing file, a missing, unknown or "LOCAL" key and a wrong type.

What the file holds (plan section 4.1, items 1-14): the self-play schedule and pool sizes, the selection evaluation, the learner's network
shape, the PPO and optimiser settings per team, the reward constants, and the code constants of the partner's learner (log-std bounds, the
initialisation scales, the advantage and log-ratio clips, the weight decay, the rank rounding). Comments say what each key is, never its
value. The geometry of the game comes from the rules and deploy files (``rules.py``, ``deploy.py``), not from here.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from .rules import PLACEHOLDER, ROOT

LOCAL_METHOD = ROOT / "configs" / "local" / "nus_method.toml"
METHOD_TEMPLATE = ROOT / "configs" / "nus_method.template.toml"
TEAMS = ("guard", "strike")
ACTIVATIONS = ("Mish", "ReLU", "SiLU", "Tanh", "Identity")
COMPUTE_DTYPES = ("float32", "bfloat16")


@dataclass(frozen=True)
class NusMethod:
    """Field names are the TOML keys; comments say what each one is, not its value."""

    # schedule and pool (partner runner: ensemble self-play)
    first_team: str  # the team trained in odd generations ("guard" or "strike")
    generations: int  # generations per lineage
    updates_per_generation: int  # PPO updates per generation
    max_learned_opponents: int  # largest learned pool; above it the pool is the latest plus a random draw of older entries
    recent_opponents: int  # latest entries always kept when the pool is drawn
    episodes_per_opponent: int  # games per pool slot per update (at least)
    minimum_rollout_batch: int  # games per update (at least)
    win_rate_ema: float  # weight of the newest update in the per-slot win-rate average
    selection_interval_updates: int  # updates between selection evaluations (and one at the end)
    selection_games_per_opponent: int  # games per pool slot in a selection evaluation
    max_pool_slots: int  # width of the critic's slot one-hot (learned slots plus the scripted one, padded)
    rank_round_digits: int  # decimal digits the selection rank is rounded to
    # learner network (actor and critic share the trunk shape)
    hidden_dim: int  # width of the residual trunk (the projection is half of it)
    hidden_blocks: int  # residual blocks
    activation: str  # activation name
    use_layernorm: bool  # pre-norm residual blocks
    compute_dtype: str  # trunk compute dtype ("float32" or "bfloat16"); the actor head is float32
    initial_log_std: float  # initial state-independent log standard deviation per action axis
    zero_init_output: bool  # actor output layer initialised to zero (else orthogonal with the gain below)
    log_std_min: float  # lower clip of the log standard deviation
    log_std_max: float  # upper clip of the log standard deviation
    output_init_gain: float  # orthogonal gain of the actor's output layer
    init_std_scale: float  # fan-in truncated-normal initialisation: standard deviation x sqrt(fan in)
    init_truncation: float  # truncation of that normal, in standard deviations
    # PPO and optimiser
    ppo_epochs: int  # passes over one rollout
    ppo_minibatches: int  # minibatches per pass
    ppo_clip: float  # ratio clip
    entropy_coef: float  # weight of the squashed-policy entropy
    critic_loss_coef: float  # weight of the squared value error
    max_grad_norm: float  # global-norm gradient clip (actor and critic separately)
    weight_decay: float  # decoupled weight decay of both optimisers
    advantage_epsilon: float  # added to the advantage variance when normalising
    advantage_clip: float  # normalised advantages are clipped to plus or minus this
    log_ratio_clip: float  # the log probability ratio is clipped to plus or minus this
    guard_actor_lr: float  # learning rates, discount, GAE lambda and advantage weight when the Guard team trains
    guard_critic_lr: float
    guard_gamma: float
    guard_gae_lambda: float
    guard_advantage_weight: float
    strike_actor_lr: float  # the same when the Strike team trains
    strike_critic_lr: float
    strike_gamma: float
    strike_gae_lambda: float
    strike_advantage_weight: float
    # reward (Guard team; the Strike team gets the exact negative)
    shaping_scale: float  # potential shaping on the summed Strike distance to the zone
    inside_penalty: float  # per step, times the share of Strike drones inside the zone
    clean_timeout_reward: float  # on the last step of a game the Strike team never reached
    first_reach_penalty: float  # on the step of the game's first reach


METHOD_KEYS: tuple[str, ...] = tuple(f.name for f in fields(NusMethod))
_TYPES = {f.name: f.type for f in fields(NusMethod)}
STRING_KEYS = tuple(k for k, t in _TYPES.items() if t in ("str", str))
_CHOICES = {"first_team": TEAMS, "activation": ACTIVATIONS, "compute_dtype": COMPUTE_DTYPES}


def _coerce(key: str, value: Any, path: Path) -> Any:
    kind = _TYPES[key]
    if kind in ("str", str):
        if not isinstance(value, str) or value == PLACEHOLDER or value not in _CHOICES[key]:
            raise ValueError(f"{path}: key '{key}' must be one of {_CHOICES[key]} (still {PLACEHOLDER}?)")
        return value
    if isinstance(value, str):
        raise ValueError(f"{path}: key '{key}' is a string (still {PLACEHOLDER}?); fill it with scripts/nus_make_local_method.py")
    if kind in ("bool", bool):
        if not isinstance(value, bool):
            raise ValueError(f"{path}: key '{key}' must be true or false")
        return value
    if isinstance(value, bool):
        raise ValueError(f"{path}: key '{key}' must be a number")
    if kind in ("int", int):
        if not isinstance(value, int):
            raise ValueError(f"{path}: key '{key}' must be an integer")
        return int(value)
    if not isinstance(value, (int, float)):
        raise ValueError(f"{path}: key '{key}' must be a number")
    return float(value)


def _check(method: NusMethod, path: Path) -> None:
    """Consistency rules the runner itself enforces (keys named, values never)."""
    positive = ("generations", "updates_per_generation", "max_learned_opponents", "episodes_per_opponent", "minimum_rollout_batch",
                "selection_interval_updates", "selection_games_per_opponent", "hidden_dim", "ppo_epochs", "ppo_minibatches")
    bad = [k for k in positive if getattr(method, k) < 1]
    if bad:
        raise ValueError(f"{path}: keys must be positive: {bad}")
    if not 0 <= method.recent_opponents <= method.max_learned_opponents:
        raise ValueError(f"{path}: 'recent_opponents' must lie between 0 and 'max_learned_opponents'")
    if method.max_pool_slots < method.max_learned_opponents + 1:
        raise ValueError(f"{path}: 'max_pool_slots' must hold the learned opponents plus the scripted slot")
    if not 0 < method.win_rate_ema <= 1:
        raise ValueError(f"{path}: 'win_rate_ema' must lie in (0, 1]")
    if method.hidden_dim % 2:
        raise ValueError(f"{path}: 'hidden_dim' must be even (the projection is half of it)")
    if not method.log_std_min < method.log_std_max:
        raise ValueError(f"{path}: 'log_std_min' must be below 'log_std_max'")


def load_method(path: Path | str = LOCAL_METHOD) -> NusMethod:
    """Read the local method file. Refuses a missing file, missing, unknown or placeholder keys and a wrong type."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found: run scripts/nus_make_local_method.py (it is git-ignored), or install the lab's "
                                "PROVISIONAL files: scripts/nus_install_provisional.sh")
    raw = tomllib.loads(path.read_text())
    missing = [k for k in METHOD_KEYS if k not in raw]
    if missing:
        raise ValueError(f"{path}: missing keys {missing}")
    unknown = [k for k in raw if k not in METHOD_KEYS]
    if unknown:
        raise ValueError(f"{path}: unknown keys {unknown}")
    method = NusMethod(**{k: _coerce(k, raw[k], path) for k in METHOD_KEYS})
    _check(method, path)
    return method


def numeric_values(method: NusMethod) -> list[float]:
    """Every numeric value of the file (used to refuse them in a record)."""
    return [float(getattr(method, f.name)) for f in fields(NusMethod)
            if _TYPES[f.name] not in ("str", str, "bool", bool)]


def team_value(method: NusMethod, team: str, name: str) -> float:
    """``<team>_<name>`` of the learner's team (``actor_lr``, ``critic_lr``, ``gamma``, ``gae_lambda``, ``advantage_weight``)."""
    if team not in TEAMS:
        raise ValueError(f"team must be one of {TEAMS}, got {team!r}")
    return float(getattr(method, f"{team}_{name}"))


def team_of_generation(method: NusMethod, generation: int) -> str:
    """Odd generations train ``first_team``, even ones the other team (partner runner, ``_team``)."""
    if generation < 1:
        raise ValueError("generations count from 1")
    other = TEAMS[1] if method.first_team == TEAMS[0] else TEAMS[0]
    return method.first_team if generation % 2 else other
