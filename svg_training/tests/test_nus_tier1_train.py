"""Phase 5 Task S4 (plan section 9): the stage 5.2 trainer (scripts/nus_tier1_train.py) on the CPU with marker local files and tiny counts:
the method runs on the hangar environment with 3-D actions, the batch shapes of the variants, the probe, the training curves, the videos
kept from the evaluations' own games (deferred), the interface file of every archived entry, the run file (filter path) and its resume
check, the record draft, the GPU-hours log, and the archived entries playing as strategies. No numeric literal (G2)."""
from __future__ import annotations

import importlib.util
import json
import re
import tomllib
from pathlib import Path

import pytest
import torch

import _nus_markers  # noqa: F401
from _nus_markers import ROOT
from _nus_tier1_fixture import TRAIN_EPISODE_STEPS, TRAIN_SEED, TIER1_GAMES, REACH_SEED, tier1_world_fixture, tiny_tier1_config
from svg_training.core.observations import OBS_DIM_V02
from svg_training.nus import outputs, players
from svg_training.nus.mappo import ACTION_DIM, Learner, MappoActor
from svg_training.nus.tier1_env import NusTier1Env, filter_path_name


@pytest.fixture()
def setup(tmp_path, monkeypatch):
    tw = tier1_world_fixture(tmp_path, monkeypatch, episode_steps=TRAIN_EPISODE_STEPS)
    tiny_tier1_config(tmp_path, monkeypatch)
    spec = importlib.util.spec_from_file_location("nus_tier1_train", ROOT / "scripts" / "nus_tier1_train.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "RUNS_ROOT", tmp_path / "runs")
    monkeypatch.setattr(mod, "STAGE_DIR", tmp_path / "runs" / "s52")
    monkeypatch.setattr(players, "TRAINED", {})
    monkeypatch.setattr(outputs, "RUNS_DIR", tmp_path / "runs")
    return tw, mod


def _args(tw, out, *extra):
    return ["--seed", str(TRAIN_SEED), "--smoke", "--method", str(tw.method_path), "--out", str(out), "--log-note", "test", *extra]


def test_tiny_run_end_to_end(setup, tmp_path):
    tw, mod = setup
    out = tmp_path / "runs" / "s52" / "seed"
    assert mod.main(_args(tw, out)) == 0
    run = json.loads((out / "run.json").read_text())
    assert run["not_of_record"] and run["interface_version"] == "0.2" and run["filter_path"].startswith("existing")
    probe = json.loads((out / "probe.json").read_text())
    assert probe["updates_timed"] >= 1 and probe["estimate_hours"] > 0 and probe["not_of_record"]
    state = json.loads((out / "self_play_state.json").read_text())
    assert [e["team"] for e in state["archive"]] == ["guard", "strike"]
    rows = [json.loads(line) for line in (out / "train_log.jsonl").read_text().splitlines()]
    smoke = tomllib.loads((tmp_path / "nus_phase5_tier1.toml").read_text())["smoke"]
    assert len(rows) == smoke["generations"] * smoke["updates_per_generation"]
    for row in rows:
        assert {"strike_reach", "filter_share", "correction_size_mps", "smoothness_decision_mps", "team_min_3d_m", "nonfinite_actions",
                "clamp_share", "entropy", "approx_kl", "clip_frac", "value_loss"} <= set(row)
        assert row["nonfinite_actions"] == 0 and row["nonfinite_metrics"] == [] and row["games"] == smoke["games_per_update"]
        assert 0 <= row["filter_share"] <= 1
    pending = sorted(p.name for p in (out / "videos" / "pending").glob("*.npz"))
    selections = sum(len(json.loads((Path(e["path"]) / "metadata.json").read_text())["evaluations"]) for e in state["archive"])
    assert len([p for p in pending if not p.startswith("archive_")]) == selections
    assert len([p for p in pending if p.startswith("archive_")]) == 2 * len(state["archive"])
    has_commit = re.fullmatch(r"[0-9a-f]{40}", mod._git_head()) is not None
    for e in state["archive"]:
        iface = Path(e["path"]) / "interface.toml"
        assert iface.exists() == has_commit   # needs a git commit to name
        if has_commit:
            data = tomllib.loads(iface.read_text())
            assert data["interface_version"] == "0.2" and data["observation_width"] == OBS_DIM_V02 and data["team"] == e["team"]
    draft = (out / "record_draft.md").read_text()
    assert "NOT OF RECORD" in draft and "EXPLORATORY" in draft and "Safety filter path: existing" in draft and "0.2" in draft
    assert all(name in draft for name in pending)
    import nus_render_pending
    rendered = nus_render_pending.render_pending(out, "gif", "tier 1")       # off the training clock, in its own step
    assert len(rendered) == len(pending) and not list((out / "videos" / "pending").glob("*.npz"))
    log = [json.loads(line) for line in (tmp_path / "runs" / "s52" / "gpu_hours.log").read_text().splitlines()]
    assert [r["what"] for r in log] == ["probe", "train"] and all(r["group"] == "s52" and r["device"] == "cpu" for r in log)
    # the archived entries play as strategies, with the environment's arithmetic: same first command, held for a hold
    entry = next(Path(e["path"]) for e in state["archive"] if e["team"] == "guard")
    assert players.register_trained("ours_g1", entry, tw.method_path) == "guard"
    env = NusTier1Env(tw.world, tw.method)
    s = env.reset(TIER1_GAMES, torch.Generator().manual_seed(REACH_SEED))
    player = players.make_player("ours_g1", "guard", tw.world.cfg, TIER1_GAMES, "cpu")
    player.reset(torch.ones(TIER1_GAMES, dtype=torch.bool))
    obs = s.handle._obs()
    first = player.act(obs["guard"])
    learner = Learner(tw.method, env, "guard", TRAIN_SEED)
    learner.actor.load_state_dict(torch.load(entry / "actor.pt", weights_only=True))
    want, _ = learner.act(env.observe(s)[0], None, deterministic=True)
    assert torch.equal(first[..., :ACTION_DIM + 1], want) and (first[..., -1] == 0).all()
    later = torch.zeros_like(obs["guard"])
    later[..., :] = obs["guard"]
    later[..., 0] += 1
    assert torch.equal(player.act(later), first)               # held until the next decision tick
    with pytest.raises(ValueError):
        players.make_player("ours_g1", "strike", tw.world.cfg, TIER1_GAMES, "cpu")


def test_resume_with_another_filter_path_is_refused(setup, tmp_path):
    tw, mod = setup
    out = tmp_path / "runs" / "s52" / "seed"
    out.mkdir(parents=True)
    run = {"seed": TRAIN_SEED, "variant": "5.1c", "shape": {}, "filter_path": "cuda_graph", "critic_reached_flag": False,
           "interface_version": "0.2", "not_of_record": True, "method_sha256": mod._sha(tw.method_path)}
    (out / "run.json").write_text(json.dumps(run))
    assert mod.main(_args(tw, out, "--probe-updates", "0")) == mod.EXIT_REFUSED


def test_trainer_with_the_cuda_graph_flag_records_its_path(setup, tmp_path):
    tw, mod = setup
    out = tmp_path / "runs" / "s52" / "graph"
    assert mod.main(_args(tw, out, "--probe-updates", "0", "--filter-cuda-graph")) == 0
    assert json.loads((out / "run.json").read_text())["filter_path"].startswith("cuda_graph")
    assert "Safety filter path: cuda_graph" in (out / "record_draft.md").read_text()
    assert mod.main(_args(tw, out, "--probe-updates", "0")) == mod.EXIT_REFUSED      # a resume on the other path is refused


def test_a_run_of_record_names_its_variant_and_waits_for_frozen_gates(setup, tmp_path):
    tw, mod = setup
    out = tmp_path / "runs" / "s52" / "record"
    base = ["--seed", str(TRAIN_SEED), "--method", str(tw.method_path), "--out", str(out), "--probe-updates", "0"]
    with pytest.raises(SystemExit, match="variant"):
        mod.main(base)
    assert mod.main([*base, "--variant", "5.1c"]) == mod.EXIT_REFUSED            # the 5.2 table is PROPOSED
    assert not (out / "run.json").exists()


def test_filter_path_names_and_the_opt_in_flag(setup):
    tw, _ = setup
    cfg = tw.world.cfg
    assert filter_path_name(cfg).startswith("existing") and "early stop" in filter_path_name(cfg)
    graph = cfg.replace(**{"starling.filter_cuda_graph": True})
    assert filter_path_name(graph).startswith("cuda_graph") and "bit for bit" in filter_path_name(graph)
    assert not cfg.starling.filter_cuda_graph          # default off


def test_variant_batch_shapes_come_from_the_gate_table(setup):
    tw, mod = setup
    gates = tomllib.loads((ROOT / "configs" / "nus_port.toml").read_text())["gates"]
    env = NusTier1Env(tw.world, tw.method)
    table = gates["phase5_method_variants"]
    for variant, key in (("5.1b", "s51b"), ("5.1c", "s51c")):
        shape = mod.base.batch_shape(variant, tw.method, env.episode_steps, gates)
        assert shape["games_per_update"] == table["games_per_update"]
        assert shape["updates_per_generation"] == table["updates_per_generation"][key]
        assert list(shape["selection_after"]) == table["selection_evaluations_after_update"][key]


def test_actor_width_follows_the_environment(setup):
    tw, _ = setup
    env = NusTier1Env(tw.world, tw.method)
    learner = Learner(tw.method, env, "strike", TRAIN_SEED)
    assert learner.actor.action_dim == env.action_dim == ACTION_DIM + 1 and learner.actor.trunk.output.out_features == env.action_dim
    assert MappoActor(OBS_DIM_V02, tw.method, env.deploy.layernorm_epsilon).action_dim == ACTION_DIM   # the replica's default unchanged
