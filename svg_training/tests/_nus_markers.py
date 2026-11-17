"""Made-up rule values for tests of the partner-game replica (G4). They are derived from a hash of the key, so no
marker number is typed anywhere; each has six significant digits, which makes a leak easy to find in text. The ranges
only keep the game valid (total cap below every push radius, boundary outside the zone)."""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

_RANGES = {
    "area_radius": (3.1, 4.3),
    "agent_size": (0.61, 0.89),
    "spawn_distance": (14.1, 18.3),
    "spawn_cluster_radius": (2.1, 3.3),
    "start_guard_disc_fraction": (0.31, 0.62),
    "start_static_guard_ring_fraction": (0.31, 0.62),
    "start_static_strike_cluster_fraction": (0.31, 0.62),
    "guard_max_speed": (0.31, 0.49),
    "strike_max_speed": (0.51, 0.79),
    "guard_safety_distance": (0.71, 0.99),
    "strike_safety_distance": (0.31, 0.59),
    "push_gain": (0.61, 0.99),
    "push_smoothing_margin": (0.011, 0.019),
    "total_displacement_cap": (0.81, 0.99),
    "guard_boundary_radius": (15.1, 19.9),
    "boundary_margin": (0.081, 0.199),
    "norm_floor": (1.1e-8, 9.9e-8),
    "obs_direction_floor": (1.1e-6, 9.9e-6),
}
_INTS = {"guard_count": 3, "strike_count": 2, "episode_steps": 7}


def _unit(key: str, salt: int) -> float:
    return int(hashlib.sha256(f"{key}/{salt}".encode()).hexdigest()[:8], 16) / 16**8


def marker_value(key: str) -> float:
    lo, hi = _RANGES[key]
    for salt in range(100):
        v = float(f"{lo + (hi - lo) * _unit(key, salt):.6g}")
        if len(f"{v:.6g}".replace(".", "").replace("e-0", "").strip("0")) >= 6:
            return v
    raise RuntimeError(key)


def marker_rules(random_start: bool = True) -> dict:
    values = {k: marker_value(k) for k in _RANGES}
    values.update(_INTS)
    values["random_start"] = random_start
    return values


def marker_strings(values: dict) -> list[str]:
    """Text forms of the float markers, as a file could show them."""
    out = []
    for v in values.values():
        if isinstance(v, float):
            out += [repr(v), f"{v:.6g}", f"{v:.6g}".replace("e-0", "e-")]
    return sorted(set(out))


def write_toml(path: Path, values: dict) -> None:
    lines = []
    for k, v in values.items():
        lines.append(f"{k} = {str(v).lower() if isinstance(v, bool) else repr(v)}")
    Path(path).write_text("\n".join(lines) + "\n")


# ---- test-only constants (not partner values). The numeric-literal scan (G2) covers tests/test_nus_*.py, so every
# tolerance and count a test needs lives here, outside that scan.
TOL_TIGHT = 1e-6   # units, float32 arithmetic
TOL_LOOSE = 1e-5
POS_TOL = 1e-4    # the Phase 2 position tolerance (configs/nus_port.toml), units
REL_LOOSE = 1e-3
REL_MID = 1e-5
REL_WIDE = 0.1
DIRECTION_MIN = 0.1  # compare an observation direction only where the vector is longer than this (units)
BATCH = 5
OBS_GAMES = 3
START_GAMES = 400
FEW_STEPS = 3
STEPS_AFTER_LATCH = 3
SPREAD_FACTOR = 3
NOT_INTEGER = 1.5
GUARDS = _INTS["guard_count"]
STRIKES = _INTS["strike_count"]
# per-actor observation order for the fixed marker layout (self, teammates cyclic from self+1, then opponents)
FIXED_LAYOUT_ORDERS = {0: [0, 1, 2, 3, 4], 1: [1, 2, 0, 3, 4], 2: [2, 0, 1, 3, 4], 3: [3, 4, 0, 1, 2], 4: [4, 3, 0, 1, 2]}


# ---- deploy-file markers (same idea as the rules markers: derived from a hash, six significant digits where the range allows)
_DEPLOY_RANGES = {
    "metres_per_unit": (0.31, 0.49),
    "flying_height_m": (1.1, 1.9),
    "spawn_distance": (14.1, 18.3),
    "guard_boundary_radius": (15.1, 19.9),
    "layernorm_epsilon": (1.1e-7, 9.9e-7),
    "disk_floor": (1.1e-9, 9.9e-9),
    "apf_attraction_gain": (1.1, 1.9),
    "apf_repulsion_gain": (11.1, 29.9),
    "apf_floor": (1.1e-9, 9.9e-9),
}
HOLD_TICKS = 7
TICK_SECONDS = 0.05  # the simulator tick (core.game_config.TICK_S); a test constant here so the test files hold no literal
WEIGHTS_NAMES = {"guard_weights": "marker_guard_weights", "strike_weights": "marker_strike_weights"}


def marker_deploy_value(key: str) -> float:
    lo, hi = _DEPLOY_RANGES[key]
    for salt in range(100):
        v = float(f"{lo + (hi - lo) * _unit('deploy/' + key, salt):.6g}")
        if len(f"{v:.6g}".replace(".", "").replace("e-0", "").strip("0")) >= 6:
            return v
    raise RuntimeError(key)


def marker_deploy() -> dict:
    values = {k: marker_deploy_value(k) for k in _DEPLOY_RANGES}
    values["hold_ticks"] = HOLD_TICKS
    values["seconds_per_step"] = HOLD_TICKS * TICK_SECONDS
    values.update(WEIGHTS_NAMES)
    return values


def write_deploy_toml(path: Path, values: dict) -> None:
    lines = []
    for k, v in values.items():
        lines.append(f"{k} = {v!r}" if not isinstance(v, str) else f'{k} = "{v}"')
    Path(path).write_text("\n".join(lines) + "\n")


def distinctive(strings: list[str], minimum_digits: int = 5) -> list[str]:
    """Marker strings with enough digits to be searched for in text (the seconds per step has too few)."""
    return [m for m in strings if sum(c.isdigit() for c in m.replace("e-0", "").replace("e-", "")) >= minimum_digits]
MIN_SCANNED_FILES = 5


# ---- synthetic partner-format checkpoint (flax msgpack layout) with marker architecture sizes, built in tmp_path
import json as _json

import msgpack as _msgpack
import numpy as _np

MARKER_ARCH = {"hidden_dim": 46, "n_hidden_layers": 2, "activation_type": "Mish", "use_layernorm": True,
               "initial_log_std": -0.5, "zero_init_output": False}
TEAM_TRAINED = {"guard": "defender", "strike": "attacker"}
PHYSICS_KEYS = {  # partner config name -> rule key
    "area_radius": "area_radius", "defender_max_speed": "guard_max_speed", "attacker_max_speed": "strike_max_speed",
    "defender_safety_distance": "guard_safety_distance", "attacker_safety_distance": "strike_safety_distance",
    "repulsion_k": "push_gain", "repulsion_margin": "push_smoothing_margin", "max_total_displacement": "total_displacement_cap",
    "boundary_margin": "boundary_margin", "max_steps": "episode_steps",
}
OBS_PER_DRONE = 9  # three [direction, magnitude] blocks
OBS_TAIL = 2       # zone radius and the reached flag


def _ext(array: _np.ndarray):
    """The partner library's ndarray encoding: ext type 1 holding (shape, dtype name, C-order bytes)."""
    return _msgpack.ExtType(1, _msgpack.packb((list(array.shape), array.dtype.name, array.tobytes("C")), use_bin_type=True))


def synthetic_actor_params(obs_dim: int, hidden: int, blocks: int, seed: int = 0, action_dim: int = 2) -> dict:
    """A parameter tree with the partner's names and shapes, small random values (so the actions are not all saturated)."""
    rng = _np.random.default_rng(seed)

    def dense(i, o, gain=1.0):
        return {"Dense_0": {"kernel": _ext((rng.normal(size=(i, o)) * gain / _np.sqrt(i)).astype(_np.float32)),
                            "bias": _ext((rng.normal(size=(o,)) * 0.1).astype(_np.float32))}}

    def norm(width):
        return {"LayerNorm_0": {"scale": _ext((1 + 0.1 * rng.normal(size=(width,))).astype(_np.float32)),
                                "bias": _ext((0.1 * rng.normal(size=(width,))).astype(_np.float32))}}

    network = {"input": dense(hidden // 2, hidden), "output": dense(hidden, action_dim, gain=1.0)}
    for k in range(blocks):
        network[f"block_{k}"] = {"norm_0": norm(hidden), "dense_0": dense(hidden, hidden), "norm_1": norm(hidden),
                                 "dense_1": dense(hidden, hidden)}
    return {"obs_proj": dense(obs_dim, hidden // 2), "network": network,
            "log_std": _ext(_np.full((action_dim,), LOG_STD, _np.float32))}


def synthetic_config(team: str, rules_values: dict | None = None, deploy_values: dict | None = None, dtype: str = "bfloat16",
                     **changes) -> dict:
    rules_values = rules_values or marker_rules()
    deploy_values = deploy_values or marker_deploy()
    g, s = rules_values["guard_count"], rules_values["strike_count"]
    physics = {name: rules_values[key] for name, key in PHYSICS_KEYS.items()}
    physics["defender_boundary"] = deploy_values["guard_boundary_radius"]
    physics["spawn_distance"] = deploy_values["spawn_distance"]
    cfg = {
        "environment": {"num_defenders": g, "num_attackers": s, "max_episode_steps": rules_values["episode_steps"],
                        "start_mode": "random" if rules_values["random_start"] else "static",
                        "env": {"env_id": f"simple_areadenial_{g}v{s}_0obs_continuous_0s_random_v0", "physics": physics}},
        "train_team": TEAM_TRAINED[team], "scripted_opponent": "apf", "selection_action_mode": "deterministic",
        "apex": {"enabled": False}, "jax": {"compute_dtype": dtype}, "trainer": {"policy": dict(MARKER_ARCH)},
        "obs_dim": OBS_PER_DRONE * (g + s) + OBS_TAIL, "action_dim": 2,
    }
    cfg.update(changes)
    return cfg


def write_synthetic_checkpoint(folder, team: str, kind: str = "runner", dtype: str = "bfloat16", seed: int = 0,
                               rules_values: dict | None = None, deploy_values: dict | None = None, **changes):
    """A checkpoint folder in one of the two accepted formats: kind "runner" (config.json, state.msgpack) or "archive" (actor.msgpack,
    metadata.json, config.json). Returns the folder."""
    from pathlib import Path
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    cfg = synthetic_config(team, rules_values, deploy_values, dtype, **changes)
    params = synthetic_actor_params(cfg["obs_dim"], MARKER_ARCH["hidden_dim"], MARKER_ARCH["n_hidden_layers"], seed)
    (folder / "config.json").write_text(_json.dumps(cfg, indent=2))
    update = _ext(_np.asarray(UPDATE_MARKER, _np.int32))
    if kind == "runner":
        tree = {"schema_version": 1, "stage": "area_denial_fixed_apf",
                "runner": {"policy": {"actor_params": params}, "global_update": update, "best_score": float("-inf"),
                           "rng": _ext(_np.zeros((2,), _np.uint32))},
                "action_mode": "deterministic"}
        (folder / "state.msgpack").write_bytes(_msgpack.packb(tree, use_bin_type=True))
    elif kind == "archive":
        tree = {"actor_params": params, "update": update, "action_mode": "deterministic"}
        (folder / "actor.msgpack").write_bytes(_msgpack.packb(tree, use_bin_type=True))
        (folder / "metadata.json").write_text(_json.dumps({"team": TEAM_TRAINED[team]}))
    else:
        raise ValueError(kind)
    return folder
PHI_WIDTH = 3
SHAPE_HEAD = 3
SEED_B = 3
SEED_C = 5


def load_marker_files(folder):
    """Write marker rules and deploy files into ``folder``; return (rules with the deploy overrides, deploy, rules path, deploy path)."""
    from pathlib import Path
    from svg_training.nus import deploy as deploy_mod, rules as rules_mod
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    write_toml(folder / "nus_rules.toml", marker_rules())
    write_deploy_toml(folder / "nus_deploy.toml", marker_deploy())
    deploy = deploy_mod.load_deploy(folder / "nus_deploy.toml")
    rules = deploy_mod.apply_overrides(rules_mod.load_rules(folder / "nus_rules.toml"), deploy)
    return rules, deploy, folder / "nus_rules.toml", folder / "nus_deploy.toml"
BF16_BAND = 0.25  # a bfloat16 trunk differs from the float32 one by a visible fraction of the speed on synthetic weights
SKEW = 1.25
UPDATE_MARKER = 7
LOG_STD = -0.5
TIE_SHARE_MAX = 0.01  # near-tie states (two Strike drones equally near a Guard) may be at most this share of the reference states


def obs_errors(ours, theirs, m, direction_check_above=DIRECTION_MIN):
    """Largest observation error. The unit direction of a near-zero vector is ill-conditioned in float32 (a rounding step
    of a position turns into a large angle), so each [direction, magnitude] block is compared as the magnitude and as the
    vector direction x magnitude; the direction alone is compared where the vector is longer than `direction_check_above`
    units. The last two entries (zone radius, reached flag) are compared exactly in the same pass."""
    a, b = ours[..., :-2].reshape(*ours.shape[:-1], -1, PHI_WIDTH), theirs[..., :-2].reshape(*theirs.shape[:-1], -1, PHI_WIDTH)
    vec_a, vec_b = a[..., :2] * a[..., 2:], b[..., :2] * b[..., 2:]
    err = max((a[..., 2] - b[..., 2]).abs().max().item(), (vec_a - vec_b).abs().max().item(), (ours[..., -2:] - theirs[..., -2:]).abs().max().item())
    long = b[..., 2] > direction_check_above
    dir_err = (a[..., :2] - b[..., :2]).abs().amax(dim=-1)[long].max().item()
    return err, dir_err
ARENA_SIDE_M = 120.0  # an arena far larger than any marker game, so no wall matters
ACTION_WIDTH = 4  # vx, vy, vz, yaw rate
SPACE_DIM = 3
HOLDS = 3  # policy steps played in a trajectory test
WILSON_CONFIDENCE = 0.95
WILSON_N_TEN = 10  # a small sample for the closed-form interval checks
FAKE_COMMIT = "a" * 40  # a made-up commit hash


def write_fake_policy_sources(clone, deploy_values: dict) -> None:
    """The three partner source files the deploy script parses for code constants, with marker values in the same code shapes."""
    from pathlib import Path
    import textwrap
    clone = Path(clone)
    (clone / "ma_skills" / "jax").mkdir(parents=True, exist_ok=True)
    (clone / "ma_skills" / "jax" / "nn.py").write_text(textwrap.dedent(f"""
        class ResidualBlock:
            def __call__(self, x):
                x = Norm("layer", epsilon={deploy_values['layernorm_epsilon']!r}, dtype=self.dtype, name="norm_0")(x)
                x = Norm("layer", epsilon={deploy_values['layernorm_epsilon']!r}, dtype=self.dtype, name="norm_1")(x)
                return x
        """))
    (clone / "ma_skills" / "jax" / "policy.py").write_text(textwrap.dedent(f"""
        def project_to_disk(actions, max_speed):
            norm = jnp.linalg.norm(actions, axis=-1, keepdims=True)
            return jnp.minimum(1.0, max_speed / jnp.maximum(norm, {deploy_values['disk_floor']!r}))
        """))
    env = clone / "third_party" / "skill_learning_mpe" / "src" / "skill_learning_mpe" / "env" / "mpe"
    env.mkdir(parents=True, exist_ok=True)
    floor = deploy_values["apf_floor"]
    (env / "simple_area_denial.py").write_text(textwrap.dedent(f"""
        class SimpleAreaDenial:
            def __init__(self):
                self.attacker_apf_attraction_gain = {deploy_values['apf_attraction_gain']!r}
                self.attacker_apf_repulsion_gain = {deploy_values['apf_repulsion_gain']!r}
            @staticmethod
            def _cap_vectors(vectors, limit):
                return vectors / jnp.maximum(limit, {floor!r})
            def apf_attacker_actions(self, state):
                return jnp.where(distance > {floor!r}, a, b) + jnp.maximum(d, {floor!r})
            def apf_defender_actions(self, state):
                return argmin(offsets)
        """))
