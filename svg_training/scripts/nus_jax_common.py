"""Shared helpers for the scripts that run in the partner's JAX environment (``nus_jax``, CPU): load a checkpoint's actor with the
partner's own network class, and its deterministic actions in the checkpoint's own compute dtype. Reads the partner's clone,
never edits it. Holds no partner value.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("JAX_PLATFORMS", "cpu")
os.environ.setdefault("WANDB_MODE", "disabled")

TEAM_TRAINED = {"guard": "defender", "strike": "attacker"}
SPEED_KEY = {"guard": "defender_max_speed", "strike": "attacker_max_speed"}


def add_partner_paths(clone: Path) -> None:
    sys.path.insert(0, str(clone))
    sys.path.insert(0, str(clone / "third_party" / "skill_learning_mpe" / "src"))


def load_actor(clone: Path, checkpoint: Path, team: str, dtype_name: str | None = None) -> dict[str, Any]:
    """The partner's TeamActor with the checkpoint's parameters. ``dtype_name`` overrides the config's compute dtype."""
    add_partner_paths(clone)
    import jax
    import jax.numpy as jnp
    from flax import serialization
    from ma_skills.jax.policy import TeamActor

    config = json.loads((checkpoint / "config.json").read_text())
    if config["train_team"] != TEAM_TRAINED[team]:
        raise SystemExit(f"checkpoint was not trained as the {team} team")
    policy = config["trainer"]["policy"]
    dtype = getattr(jnp, dtype_name or config["jax"]["compute_dtype"])
    speed = float(config["environment"]["env"]["physics"][SPEED_KEY[team]])
    actor = TeamActor(config["obs_dim"], config["action_dim"], max_speed=speed, hidden_dim=policy["hidden_dim"],
                      num_blocks=policy["n_hidden_layers"], activation_name=policy["activation_type"], use_norm=policy["use_layernorm"],
                      dtype=dtype)
    if (checkpoint / "state.msgpack").exists():  # a runner checkpoint
        raw = serialization.msgpack_restore((checkpoint / "state.msgpack").read_bytes())["runner"]["policy"]["actor_params"]
    else:  # an archive entry (self-play archive): actor.msgpack holds the actor parameters at the top level
        raw = serialization.msgpack_restore((checkpoint / "actor.msgpack").read_bytes())["actor_params"]
    template = actor.init(jax.random.key(0), jnp.zeros((1, 1, config["obs_dim"]), jnp.float32))["params"]
    params = serialization.from_state_dict(template, raw)
    return {"actor": actor, "params": params, "speed": speed, "config": config}


def deterministic_actions(bundle: dict[str, Any], obs):
    """(..., obs_dim) -> (..., 2) float32 deterministic actions (the partner's ``actor_actions`` with deterministic=True)."""
    import jax
    from ma_skills.jax.policy import actor_actions

    action, _, _ = actor_actions(bundle["actor"], bundle["params"], obs, jax.random.key(0), max_speed=bundle["speed"], deterministic=True)
    return action


def make_adapter(config: dict[str, Any]):
    from ma_skills.jax.mpe import JAXMPEAdapter

    env = config["environment"]["env"]
    return JAXMPEAdapter(env_id=env["env_id"], global_state_fields=env["global_state_fields"], max_episode_steps=env["max_episode_steps"],
                         env_kwargs=env.get("physics", {}))


def write_frame(stream, array) -> None:
    """One array on a binary stream (numpy's own format inside a length-prefixed frame, so a pipe works)."""
    import io
    import struct

    import numpy as np

    buffer = io.BytesIO()
    np.save(buffer, np.ascontiguousarray(array), allow_pickle=False)
    payload = buffer.getvalue()
    stream.write(struct.pack("<Q", len(payload)) + payload)
    stream.flush()


def _read_exactly(stream, count: int):
    chunks = []
    while count:
        chunk = stream.read(count)
        if not chunk:
            return None
        chunks.append(chunk)
        count -= len(chunk)
    return b"".join(chunks)


def read_frame(stream):
    """The next array from a binary stream, or None at the end of the stream."""
    import io
    import struct

    import numpy as np

    header = _read_exactly(stream, struct.calcsize("<Q"))
    if header is None:
        return None
    payload = _read_exactly(stream, struct.unpack("<Q", header)[0])
    if payload is None:
        raise EOFError("the stream ended inside a frame")
    return np.load(io.BytesIO(payload), allow_pickle=False)
