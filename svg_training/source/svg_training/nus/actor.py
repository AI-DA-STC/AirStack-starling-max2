"""The partner's trained actor, read from its msgpack file and run in PyTorch (no JAX, no Flax in ``source/``).

Accepted checkpoint folders (anything else is refused):

* a runner checkpoint: ``config.json`` and ``state.msgpack`` (fixed-opponent runner, stage ``area_denial_fixed_apf``);
* an archive entry: ``actor.msgpack`` and ``metadata.json`` plus ``config.json`` (in the folder, or given with ``config_path``).

The network is rebuilt from the checkpoint's ``config.json`` (checked against the parameter shapes) and the deploy file: observation
projection, input layer, residual blocks (LayerNorm, activation, dense, twice, plus the block input), output layer. The action is the
deterministic mean: the output goes through tanh, is scaled by the team's speed and projected onto the speed disk. The LayerNorm
epsilon and the disk floor are partner code constants, read from the deploy file.

When the config says ``bfloat16`` the partner's cast points are copied: the observation, every dense layer's input, kernel and bias,
every activation (per operation) and the residual sums are rounded to bfloat16; the LayerNorm statistics and its output formula are
float32, rounded to bfloat16 on the way out; the head (output mean, tanh, projection) is float32.

Error messages name keys and files, never a value.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable

import msgpack
import numpy as np
import torch
import torch.nn.functional as F

from .deploy import NusDeploy
from .replica import FEATURES_PER_ACTOR as FEATURES_PER_DRONE  # three [unit direction, magnitude] blocks per drone
from .rules import NusRules

EXT_NDARRAY, EXT_NPSCALAR = 1, 2 + 1  # the partner library's msgpack extension codes
RUNNER_STAGE = "area_denial_fixed_apf"
RUNNER_SCHEMA = 1
TRAINED_AS = {"guard": "defender", "strike": "attacker"}
DTYPES = {"float32": torch.float32, "bfloat16": torch.bfloat16}
FEATURES_TAIL = 2  # zone radius, reached flag
ACTION_DIM = 2
# partner config name of a physics setting -> the rule key it must equal
PHYSICS_TO_RULE = {
    "area_radius": "area_radius", "defender_max_speed": "guard_max_speed", "attacker_max_speed": "strike_max_speed",
    "defender_safety_distance": "guard_safety_distance", "attacker_safety_distance": "strike_safety_distance",
    "repulsion_k": "push_gain", "repulsion_margin": "push_smoothing_margin", "max_total_displacement": "total_displacement_cap",
    "boundary_margin": "boundary_margin", "max_steps": "episode_steps", "defender_boundary": "guard_boundary_radius",
    "spawn_distance": "spawn_distance",
}


# ------------------------------------------------------------------------------------------------ msgpack (flax layout)
def _ext_hook(code: int, data: bytes) -> Any:
    """The partner library's array encodings: the ndarray and numpy-scalar extensions; both hold (shape, dtype name, bytes)."""
    if code not in (EXT_NDARRAY, EXT_NPSCALAR):
        raise ValueError(f"unsupported msgpack extension type {code}")
    shape, name, buffer = msgpack.unpackb(data, raw=True)
    dtype = name.decode()
    if dtype not in ("float32", "float64", "int32", "int64", "uint32", "bool"):
        raise ValueError(f"unsupported array dtype {dtype!r}")
    array = np.frombuffer(buffer, dtype=np.dtype(dtype)).reshape(shape).copy()
    return array if code == EXT_NDARRAY else array[()]


def read_msgpack(path: Path | str) -> Any:
    """Decode a file written by the partner's serialisation (msgpack with array extensions). Refuses chunked arrays."""
    tree = msgpack.unpackb(Path(path).read_bytes(), ext_hook=_ext_hook, raw=False, strict_map_key=False)

    def check(node: Any) -> None:
        if isinstance(node, dict):
            if "__msgpack_chunked_array__" in node:
                raise ValueError("chunked arrays are not supported")
            for value in node.values():
                check(value)

    check(tree)
    return tree


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------------------------------------------ activations
def _mish_bf16(x: torch.Tensor) -> torch.Tensor:
    """Mish with the rounding of the partner's bfloat16 graph: softplus, tanh and the product each rounded to bfloat16."""
    xf = x.float()
    softplus = F.softplus(xf).to(torch.bfloat16)
    tanh = torch.tanh(softplus.float()).to(torch.bfloat16)
    return (xf * tanh.float()).to(torch.bfloat16)


def _mish_f32(x: torch.Tensor) -> torch.Tensor:
    return x * torch.tanh(F.softplus(x))


ACTIVATIONS: dict[str, tuple[Callable, Callable]] = {  # name -> (float32 form, bfloat16 form)
    "Mish": (_mish_f32, _mish_bf16),
    "ReLU": (torch.relu, torch.relu),
    "SiLU": (F.silu, F.silu),
    "Tanh": (torch.tanh, torch.tanh),
    "Identity": (lambda x: x, lambda x: x),
}


class NusActor:
    """Deterministic converted actor of one team. ``act_units`` maps observations to displacement requests in the partner's units."""

    def __init__(self, params: dict[str, Any], config: dict[str, Any], team: str, rules: NusRules, deploy: NusDeploy,
                 device: torch.device | str = "cpu", meta: dict[str, Any] | None = None):
        if team not in TRAINED_AS:
            raise ValueError(f"team must be 'guard' or 'strike', got {team!r}")
        self.team, self.device = team, torch.device(device)
        policy = config["trainer"]["policy"]
        self.compute_dtype = str(config["jax"]["compute_dtype"])
        self.bf16 = self.compute_dtype == "bfloat16"
        self.activation_name = str(policy["activation_type"])
        self.use_norm = bool(policy["use_layernorm"])
        self.blocks = int(policy["n_hidden_layers"])
        self.obs_dim = int(config["obs_dim"])
        self.team_size = rules.guard_count if team == "guard" else rules.strike_count
        self.max_speed = rules.guard_max_speed if team == "guard" else rules.strike_max_speed
        self.eps, self.floor = deploy.layernorm_epsilon, deploy.disk_floor
        self.meta = dict(meta or {}, compute_dtype=self.compute_dtype, team=team)
        self._act = ACTIVATIONS[self.activation_name][1 if self.bf16 else 0]
        self._params = self._convert(params)

    # ------------------------------------------------------------------ weights
    def _tensor(self, array: np.ndarray, transpose: bool = False) -> torch.Tensor:
        return torch.from_numpy(np.ascontiguousarray(array.T if transpose else array)).to(self.device, torch.float32)

    def _dense(self, node: dict[str, Any]) -> tuple[torch.Tensor, torch.Tensor]:
        weight = self._tensor(node["Dense_0"]["kernel"], transpose=True)  # flax (in, out) -> torch (out, in)
        bias = self._tensor(node["Dense_0"]["bias"])
        if self.bf16:
            weight, bias = weight.to(torch.bfloat16), bias.to(torch.bfloat16)
        return weight, bias

    def _norm(self, node: dict[str, Any]) -> tuple[torch.Tensor, torch.Tensor]:
        return self._tensor(node["LayerNorm_0"]["scale"]), self._tensor(node["LayerNorm_0"]["bias"])

    def _convert(self, params: dict[str, Any]) -> dict[str, Any]:
        net = params["network"]
        out: dict[str, Any] = {"obs_proj": self._dense(params["obs_proj"]), "input": self._dense(net["input"]),
                               "output": self._dense(net["output"]), "blocks": []}
        for k in range(self.blocks):
            block = net[f"block_{k}"]
            entry = {"dense_0": self._dense(block["dense_0"]), "dense_1": self._dense(block["dense_1"])}
            if self.use_norm:
                entry |= {"norm_0": self._norm(block["norm_0"]), "norm_1": self._norm(block["norm_1"])}
            out["blocks"].append(entry)
        return out

    # ------------------------------------------------------------------ forward
    def _linear(self, x: torch.Tensor, layer: tuple[torch.Tensor, torch.Tensor]) -> torch.Tensor:
        weight, bias = layer
        return F.linear(x, weight) + bias  # the product and the bias add are separate roundings, as in the partner's graph

    def _layer_norm(self, x: torch.Tensor, layer: tuple[torch.Tensor, torch.Tensor]) -> torch.Tensor:
        scale, bias = layer
        xf = x.float()
        mean = xf.mean(-1, keepdim=True)
        var = (xf - mean).square().mean(-1, keepdim=True)
        y = (xf - mean) * (torch.rsqrt(var + self.eps) * scale) + bias
        return y.to(torch.bfloat16) if self.bf16 else y

    def mean(self, obs: torch.Tensor) -> torch.Tensor:
        """Pre-squash action mean (float32) for observations (..., obs_dim)."""
        if obs.shape[-1] != self.obs_dim:
            raise ValueError(f"observation width does not match the actor's input width (got {obs.shape[-1]})")
        p = self._params
        x = obs.to(self.device, torch.float32)
        if self.bf16:
            x = x.to(torch.bfloat16)
        x = self._linear(self._linear(x, p["obs_proj"]), p["input"])
        for block in p["blocks"]:
            h = self._act(self._layer_norm(x, block["norm_0"])) if self.use_norm else self._act(x)
            h = self._linear(h, block["dense_0"])
            h = self._act(self._layer_norm(h, block["norm_1"])) if self.use_norm else self._act(h)
            h = self._linear(h, block["dense_1"])
            x = x + h
        return self._linear(x, p["output"]).float()

    @torch.no_grad()
    def act_units(self, obs: torch.Tensor) -> torch.Tensor:
        """Observations (..., obs_dim) -> displacement requests (..., 2) in the partner's units per step: the deterministic mean,
        tanh, scaled by the team speed, projected onto the speed disk."""
        action = torch.tanh(self.mean(obs)) * self.max_speed
        length = torch.linalg.norm(action, dim=-1, keepdim=True)
        return action * torch.clamp(self.max_speed / length.clamp_min(self.floor), max=1)

    # ------------------------------------------------------------------ loading
    @classmethod
    def load(cls, folder: Path | str, *, team: str, rules: NusRules, deploy: NusDeploy, device: torch.device | str = "cpu",
             config_path: Path | str | None = None) -> "NusActor":
        """Read a checkpoint folder (see the module docstring) for ``team``. Refuses anything unsupported."""
        folder = Path(folder)
        if not folder.is_dir():
            raise FileNotFoundError(f"checkpoint folder {folder} not found")
        has_runner, has_archive = (folder / "state.msgpack").exists(), (folder / "actor.msgpack").exists()
        if has_runner == has_archive:
            raise ValueError(f"{folder}: unsupported format: expected state.msgpack (runner checkpoint) or actor.msgpack (archive entry), not both or neither")
        config_file = Path(config_path) if config_path is not None else folder / "config.json"
        if not config_file.exists():
            raise ValueError(f"{folder}: the run's config.json is required (give config_path for an archive entry)")
        config = json.loads(config_file.read_text())
        _check_config(config, team, rules)
        weights_file = folder / ("state.msgpack" if has_runner else "actor.msgpack")
        raw = read_msgpack(weights_file)
        if has_runner:
            if raw.get("stage") != RUNNER_STAGE or int(raw.get("schema_version", 0)) != RUNNER_SCHEMA:
                raise ValueError(f"{folder}: unsupported runner checkpoint (stage or schema)")
            params, update = raw["runner"]["policy"]["actor_params"], int(raw["runner"]["global_update"])
        else:
            params, update = raw["actor_params"], int(raw["update"])
        mode = raw.get("action_mode", "deterministic")
        if mode != "deterministic":
            raise ValueError(f"{folder}: only deterministic checkpoints are supported (action_mode)")
        _check_params(params, config, folder)
        meta = {"format": "runner" if has_runner else "archive", "update": update, "sha256": _sha256(weights_file),
                "config_sha256": _sha256(config_file), "path": str(folder)}
        return cls(params, config, team, rules, deploy, device, meta)


# ------------------------------------------------------------------------------------------------ checks
def _check_config(config: dict[str, Any], team: str, rules: NusRules) -> None:
    """Refuse a config the converter does not support or whose game differs from the rules (keys named, values never)."""
    if config.get("train_team") != TRAINED_AS[team]:
        raise ValueError(f"checkpoint was not trained as the {team} team (train_team)")
    if (config.get("apex") or {}).get("enabled"):
        raise ValueError("apex checkpoints (a mixed-in prior action) are not supported (apex.enabled)")
    if str(config.get("selection_action_mode", "deterministic")) != "deterministic":
        raise ValueError("only deterministic checkpoints are supported (selection_action_mode)")
    if str(config["jax"]["compute_dtype"]) not in DTYPES:
        raise ValueError("unsupported compute dtype (jax.compute_dtype)")
    policy = config["trainer"]["policy"]
    if str(policy["activation_type"]) not in ACTIVATIONS:
        raise ValueError("unsupported activation (trainer.policy.activation_type)")
    if policy.get("zero_init_output") is None or int(config["action_dim"]) != ACTION_DIM:
        raise ValueError("unsupported action layout (action_dim)")
    env = config["environment"]
    mismatched = []
    if int(env["num_defenders"]) != rules.guard_count:
        mismatched.append("guard_count")
    if int(env["num_attackers"]) != rules.strike_count:
        mismatched.append("strike_count")
    physics = env["env"].get("physics", {})
    for name, key in PHYSICS_TO_RULE.items():
        if name in physics and not math.isclose(float(physics[name]), float(getattr(rules, key))):
            mismatched.append(key)
    if int(config["obs_dim"]) != FEATURES_PER_DRONE * (rules.guard_count + rules.strike_count) + FEATURES_TAIL:
        mismatched.append("observation width")
    if mismatched:
        raise ValueError(f"checkpoint config disagrees with the local rules and deploy files on: {sorted(set(mismatched))}")


def _expected_shapes(config: dict[str, Any]) -> dict[str, tuple[int, ...]]:
    policy = config["trainer"]["policy"]
    hidden, half, obs = int(policy["hidden_dim"]), int(policy["hidden_dim"]) // 2, int(config["obs_dim"])
    shapes = {"obs_proj/Dense_0/kernel": (obs, half), "obs_proj/Dense_0/bias": (half,),
              "network/input/Dense_0/kernel": (half, hidden), "network/input/Dense_0/bias": (hidden,),
              "network/output/Dense_0/kernel": (hidden, ACTION_DIM), "network/output/Dense_0/bias": (ACTION_DIM,),
              "log_std": (ACTION_DIM,)}
    for k in range(int(policy["n_hidden_layers"])):
        base = f"network/block_{k}"
        for layer in ("dense_0", "dense_1"):
            shapes[f"{base}/{layer}/Dense_0/kernel"] = (hidden, hidden)
            shapes[f"{base}/{layer}/Dense_0/bias"] = (hidden,)
        if policy["use_layernorm"]:
            for layer in ("norm_0", "norm_1"):
                shapes[f"{base}/{layer}/LayerNorm_0/scale"] = (hidden,)
                shapes[f"{base}/{layer}/LayerNorm_0/bias"] = (hidden,)
    return shapes


def _flatten(tree: Any, prefix: str = "") -> dict[str, np.ndarray]:
    if isinstance(tree, dict):
        out: dict[str, np.ndarray] = {}
        for key, value in tree.items():
            out |= _flatten(value, f"{prefix}/{key}" if prefix else str(key))
        return out
    return {prefix: np.asarray(tree)}


def _check_params(params: Any, config: dict[str, Any], folder: Path) -> None:
    flat = _flatten(params)
    want = _expected_shapes(config)
    if {k: v.shape for k, v in flat.items()} != want:
        raise ValueError(f"{folder}: the parameters do not match the config's actor architecture")
    if not all(np.isfinite(v).all() for v in flat.values()):
        raise ValueError(f"{folder}: the parameters are not all finite")
