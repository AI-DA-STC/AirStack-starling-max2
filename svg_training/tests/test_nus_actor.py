"""Tests of the converted actor (weight loader and forward pass). A synthetic checkpoint with marker sizes is built in tmp_path from the
partner's file layout; no partner checkpoint or value is used. The gate against the partner's own actor on reference observations
(scripts/nus_export_reference.py) runs only where those files exist."""
import json
import re

import msgpack
import numpy as np
import pytest
import torch

from _nus_markers import (BF16_BAND, LOG_STD, SKEW, UPDATE_MARKER, BATCH, MARKER_ARCH, TOL_LOOSE, TOL_TIGHT, distinctive, load_marker_files, marker_rules, marker_strings,
                          write_synthetic_checkpoint, SEED_B)
from svg_training.nus import deploy as deploy_mod, rules as rules_mod
from svg_training.nus.actor import NusActor

TEAMS = ("guard", "strike")


@pytest.fixture(scope="module")
def files(tmp_path_factory):
    return load_marker_files(tmp_path_factory.mktemp("actor"))


def team_speed(rules, team):
    return rules.guard_max_speed if team == "guard" else rules.strike_max_speed


def numpy_reference(params, obs, speed, eps, floor, activation):
    """Independent float32 restatement of the partner's actor on decoded parameters (mean action, tanh, disk projection)."""
    def dense(x, p):
        return x @ p["Dense_0"]["kernel"] + p["Dense_0"]["bias"]

    def norm(x, p):
        q = p["LayerNorm_0"]
        mean = x.mean(-1, keepdims=True)
        var = ((x - mean) ** 2).mean(-1, keepdims=True)
        return (x - mean) / np.sqrt(var + eps) * q["scale"] + q["bias"]

    x = dense(obs, params["obs_proj"])
    net = params["network"]
    x = dense(x, net["input"])
    k = 0
    while f"block_{k}" in net:
        b = net[f"block_{k}"]
        h = dense(activation(norm(x, b["norm_0"])), b["dense_0"])
        h = dense(activation(norm(h, b["norm_1"])), b["dense_1"])
        x = x + h
        k += 1
    mean = dense(x, net["output"])
    action = np.tanh(mean) * speed
    length = np.linalg.norm(action, axis=-1, keepdims=True)
    return action * np.minimum(1.0, speed / np.maximum(length, floor))


def mish(x):
    return x * np.tanh(np.log1p(np.exp(x)))


def decode(folder, kind):
    def hook(code, data):
        shape, name, buf = msgpack.unpackb(data, raw=True)
        return np.frombuffer(buf, dtype=np.dtype(name.decode())).reshape(shape)
    raw = msgpack.unpackb((folder / ("state.msgpack" if kind == "runner" else "actor.msgpack")).read_bytes(), ext_hook=hook, raw=False)
    return raw["runner"]["policy"]["actor_params"] if kind == "runner" else raw["actor_params"]


def make(tmp_path, files, team="guard", kind="runner", dtype="float32", **changes):
    rules, deploy, _, _ = files
    folder = write_synthetic_checkpoint(tmp_path / f"{team}_{kind}_{dtype}", team, kind=kind, dtype=dtype, **changes)
    return folder, NusActor.load(folder, team=team, rules=rules, deploy=deploy)


def random_obs(actor, rows=BATCH):
    gen = torch.Generator().manual_seed(SEED_B)
    return torch.randn(rows, actor.team_size, actor.obs_dim, generator=gen)


@pytest.mark.parametrize("team", TEAMS)
@pytest.mark.parametrize("kind", ["runner", "archive"])
def test_float32_actor_matches_the_numpy_restatement_for_both_formats_and_teams(tmp_path, files, team, kind):
    rules, deploy, _, _ = files
    folder, actor = make(tmp_path, files, team, kind)
    obs = random_obs(actor)
    want = numpy_reference(decode(folder, kind), obs.numpy(), team_speed(rules, team), deploy.layernorm_epsilon, deploy.disk_floor, mish)
    got = actor.act_units(obs).numpy()
    assert got.shape == (BATCH, actor.team_size, 2)
    np.testing.assert_allclose(got, want, atol=TOL_LOOSE)
    assert actor.meta["format"] == kind and actor.meta["update"] == UPDATE_MARKER and actor.meta["compute_dtype"] == "float32"
    assert len(actor.meta["sha256"]) == len(rules_mod.file_sha256(folder / "config.json"))


def test_bfloat16_config_rounds_at_the_partners_cast_points(tmp_path, files):
    rules, _, _, _ = files
    _, f32 = make(tmp_path, files, dtype="float32")
    _, bf16 = make(tmp_path, files, dtype="bfloat16")
    obs = random_obs(bf16)
    assert bf16.meta["compute_dtype"] == "bfloat16"
    a32, a16 = f32.act_units(obs), bf16.act_units(obs)
    gap = (a32 - a16).abs().max().item()
    assert TOL_LOOSE < gap < BF16_BAND * rules.guard_max_speed
    # the observation is cast on the way in: an input already rounded to bfloat16 gives the same action, in this mode only
    rounded = obs.to(torch.bfloat16).float()
    assert torch.equal(bf16.act_units(rounded), a16)
    assert not torch.equal(f32.act_units(rounded), a32)


@pytest.mark.parametrize("team", TEAMS)
def test_action_is_deterministic_bounded_by_the_team_speed_and_carries_no_graph(tmp_path, files, team):
    rules, _, _, _ = files
    _, actor = make(tmp_path, files, team)
    obs = random_obs(actor) * (BATCH * BATCH)  # large inputs saturate the squash
    a = actor.act_units(obs)
    assert torch.equal(a, actor.act_units(obs)) and not a.requires_grad and a.grad_fn is None
    assert a.norm(dim=-1).max().item() <= team_speed(rules, team) + TOL_TIGHT


def test_rows_are_independent_and_flat_input_works(tmp_path, files):
    _, actor = make(tmp_path, files)
    obs = random_obs(actor)
    both = actor.act_units(obs)
    assert torch.allclose(actor.act_units(obs[1:2]), both[1:2], atol=TOL_LOOSE)
    assert torch.allclose(actor.act_units(obs.reshape(-1, actor.obs_dim)).reshape(both.shape), both, atol=TOL_LOOSE)
    with pytest.raises(ValueError, match="width"):
        actor.act_units(obs[..., 1:])


def test_refuses_other_formats_and_unsupported_checkpoints(tmp_path, files):
    rules, deploy, _, _ = files
    load = lambda folder, team="guard": NusActor.load(folder, team=team, rules=rules, deploy=deploy)
    folder = write_synthetic_checkpoint(tmp_path / "ok", "guard")
    with pytest.raises(ValueError, match="trained as"):
        load(folder, "strike")
    with pytest.raises(FileNotFoundError):
        load(tmp_path / "absent")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="format"):
        load(empty)
    (tmp_path / "ok" / "actor.msgpack").write_bytes(b"x")
    with pytest.raises(ValueError, match="format"):  # both layouts at once is ambiguous
        load(folder)
    no_config = write_synthetic_checkpoint(tmp_path / "noconfig", "guard")
    (no_config / "config.json").unlink()
    with pytest.raises(ValueError, match="config.json"):
        load(no_config)
    for name, changes in (("apex", {"apex": {"enabled": True}}), ("mode", {"selection_action_mode": "sampled"}),
                          ("dtype", {"jax": {"compute_dtype": "float16"}})):
        bad = write_synthetic_checkpoint(tmp_path / name, "guard", **changes)
        with pytest.raises(ValueError):
            load(bad)


def test_refuses_a_checkpoint_whose_game_disagrees_with_the_rules_and_names_keys_only(tmp_path, files):
    rules, deploy, _, _ = files
    values = marker_rules()
    values["push_gain"] = values["push_gain"] * SKEW
    folder = write_synthetic_checkpoint(tmp_path / "skew", "guard", rules_values=values)
    with pytest.raises(ValueError, match="push_gain") as err:
        NusActor.load(folder, team="guard", rules=rules, deploy=deploy)
    text = str(err.value)
    assert not [m for m in distinctive(marker_strings(values)) if m in text]
    other = marker_rules() | {"strike_count": marker_rules()["strike_count"] + 1}
    folder = write_synthetic_checkpoint(tmp_path / "size", "guard", rules_values=other)
    with pytest.raises(ValueError, match="strike_count"):
        NusActor.load(folder, team="guard", rules=rules, deploy=deploy)


def test_refuses_nonfinite_or_mismatched_parameters(tmp_path, files):
    rules, deploy, _, _ = files
    folder = write_synthetic_checkpoint(tmp_path / "widths", "guard")
    cfg = json.loads((folder / "config.json").read_text())
    cfg["trainer"]["policy"]["hidden_dim"] += 2
    (folder / "config.json").write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match="architecture"):
        NusActor.load(folder, team="guard", rules=rules, deploy=deploy)
    folder = write_synthetic_checkpoint(tmp_path / "nan", "guard")
    blob = (folder / "state.msgpack").read_bytes()
    nan = np.float32(np.nan).tobytes()
    inf_blob = re.sub(re.escape(np.float32(LOG_STD).tobytes()), nan, blob, count=1)  # the log_std entry
    (folder / "state.msgpack").write_bytes(inf_blob)
    with pytest.raises(ValueError, match="finite"):
        NusActor.load(folder, team="guard", rules=rules, deploy=deploy)


def test_no_architecture_value_in_error_text(tmp_path, files):
    rules, deploy, _, _ = files
    folder = write_synthetic_checkpoint(tmp_path / "widths", "guard")
    cfg = json.loads((folder / "config.json").read_text())
    cfg["trainer"]["policy"]["hidden_dim"] += 2
    (folder / "config.json").write_text(json.dumps(cfg))
    with pytest.raises(ValueError) as err:
        NusActor.load(folder, team="guard", rules=rules, deploy=deploy)
    assert str(MARKER_ARCH["hidden_dim"]) not in str(err.value) and str(MARKER_ARCH["hidden_dim"] + 2) not in str(err.value)


REFERENCE_DIR = deploy_mod.REFERENCE_DIR
GATE = {"guard": "defender", "strike": "attacker"}


@pytest.mark.parametrize("team", TEAMS)
def test_gate_a_action_parity_with_the_partners_jax_actor(team):
    import tomllib
    npz = REFERENCE_DIR / f"actions_{team}.npz"
    if not (npz.exists() and rules_mod.LOCAL_RULES.exists() and deploy_mod.LOCAL_DEPLOY.exists()):
        pytest.skip("reference file or local files absent (scripts/nus_export_reference.py)")
    gates = tomllib.loads((rules_mod.ROOT / "configs" / "nus_port.toml").read_text())["gates"]["phase3_converted_policy"]
    deploy = deploy_mod.load_deploy()
    rules = deploy_mod.apply_overrides(rules_mod.load_rules(), deploy)
    actor = NusActor.load(deploy_mod.weights_folder(deploy, team), team=team, rules=rules, deploy=deploy)
    data = np.load(npz)
    obs = torch.from_numpy(data["obs"])
    got = actor.act_units(obs)
    err = (got - torch.from_numpy(data["actions"])).abs()
    rows = obs.shape[0] * obs.shape[1]
    print(f"\n[gate a {team}] observations={rows}  max |action error|={err.max().item():.5f}  mean={err.mean().item():.5f}  "
          f"limit={gates['max_action_error_units_per_step']}")
    assert rows >= gates["observations_per_team"]
    assert err.max().item() <= gates["max_action_error_units_per_step"]
