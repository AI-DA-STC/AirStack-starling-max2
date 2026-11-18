"""Phase 5 task M4: alternating best-response self-play (nus/selection.py, nus/selfplay.py), on the CPU with marker files and tiny counts:
the opponent selection against a table recorded once from the partner's own function (tests/data, indices only), the batch-size formula,
stage seeds, the stacked opponent pool, team alternation and the archive, best-snapshot selection, the per-slot win-rate average, resume
from the alternating checkpoints (same archive as an uninterrupted run) and the non-finite abort."""
import json

import pytest
import torch

from _nus_markers import ROOT
from _nus_phase5_method_fixture import (BATCH_CASES, OTHER_RUN_SEED, RUN_SEED, SEEDS, SELECTION_TABLE, SELFPLAY_STOP_AFTER, STAGE_SEED_CASES, TRAIN_GAMES,
                                        marker_env)
from svg_training.nus import mappo as M
from svg_training.nus.selection import rollout_batch_size, select_opponents, stage_seed
from svg_training.nus.selfplay import OpponentPool, SelfPlay

TEAM = {"defender": "guard", "attacker": "strike"}


def _archive(last):
    return [{"generation": g, "team": "guard" if g % 2 else "strike"} for g in range(1, last + 1)]


def test_selection_matches_the_partners_table():
    table = json.loads((ROOT / "tests" / "data" / SELECTION_TABLE).read_text())["cases"]
    assert any(c["generation"] - 1 > c["maximum"] * 2 for c in table)          # the drawing branch is exercised
    for c in table:
        team = "guard" if c["generation"] % 2 else "strike"
        chosen = select_opponents(_archive(c["generation"] - 1), team=team, generation=c["generation"], seed=c["seed"],
                                  maximum=c["maximum"], recent=c["recent"])
        assert [e["generation"] for e in chosen] == c["selected_generations"], c


def test_batch_size_and_stage_seed():
    for slots, per, minimum, games in BATCH_CASES:
        assert rollout_batch_size(slots, per, minimum) == games
    for seed, generation, expected in STAGE_SEED_CASES:
        assert stage_seed(seed, generation) == expected


def test_opponent_pool_blocks_match_single_actors(tmp_path):
    env = marker_env(tmp_path)
    actors = [M.MappoActor(env.obs_dim, env.method, env.deploy.layernorm_epsilon, torch.Generator().manual_seed(s)) for s in SEEDS[:2]]
    pool = OpponentPool(env, "strike", actors)
    block = TRAIN_GAMES
    state = env.reset(pool.slots * block, torch.Generator().manual_seed(SEEDS[2]))
    acts = pool.actions(state, block)
    _, strike_obs = env.observe(state)
    for i, actor in enumerate(actors):
        with torch.no_grad():
            mean, _ = actor(strike_obs[i * block:(i + 1) * block])
        expected = M.squash(mean, env.team_speed("strike"), env.deploy.disk_floor)
        torch.testing.assert_close(acts[i * block:(i + 1) * block], expected)
    torch.testing.assert_close(acts[len(actors) * block:], env.apf_actions(state, "strike")[len(actors) * block:])


def _run(tmp_path, name, max_updates=None, env=None):
    env = env or marker_env(tmp_path)
    sp = SelfPlay(env.method, env, seed=RUN_SEED, run_dir=tmp_path / name)
    return sp, sp.run(max_updates=max_updates)


def test_generations_alternate_and_archive(tmp_path):
    sp, archive = _run(tmp_path, "run")
    m = sp.method
    assert [e["team"] for e in archive] == ["guard", "strike", "guard"][: m.generations]
    for e in archive:
        meta = json.loads((tmp_path / "run" / "archive" / f"{e['generation']:04d}_{e['team']}" / "metadata.json").read_text())
        earlier_other = [g["generation"] for g in archive if g["generation"] < e["generation"] and g["team"] != e["team"]]
        assert meta["opponent_generations"] == earlier_other
        assert len(meta["training_win_rate_ema"]) == len(earlier_other) + 1             # one per slot, APF last
        ranks = [tuple(ev["rank"]) for ev in meta["evaluations"]]
        assert tuple(meta["best_rank"]) == max(ranks) and meta["best_update"] in [ev["update"] for ev in meta["evaluations"]]
        assert [ev["update"] for ev in meta["evaluations"]] == sorted(sp.selection_after)
        actor = sp.load_actor(e)
        assert isinstance(actor, M.MappoActor)
    assert all(p.is_relative_to(tmp_path) for p in tmp_path.rglob("*"))


def test_resume_gives_the_same_archive(tmp_path):
    env = marker_env(tmp_path)
    _, whole = _run(tmp_path, "whole", env=env)
    sp, partial = _run(tmp_path, "parts", max_updates=SELFPLAY_STOP_AFTER, env=env)
    assert len(partial) < len(whole)
    resumed = SelfPlay(env.method, env, seed=RUN_SEED, run_dir=tmp_path / "parts").run()
    assert [e["best_update"] for e in resumed] == [e["best_update"] for e in whole]
    for a, b in zip(whole, resumed):
        wa = torch.load(f"{a['path']}/actor.pt", weights_only=True)
        wb = torch.load(f"{b['path']}/actor.pt", weights_only=True)
        assert all(torch.equal(wa[k], wb[k]) for k in wa)
    with pytest.raises(ValueError, match="another run"):
        SelfPlay(env.method, env, seed=OTHER_RUN_SEED, run_dir=tmp_path / "parts")


def test_non_finite_aborts_and_keeps_the_checkpoint(tmp_path, monkeypatch):
    env = marker_env(tmp_path)

    def bad_update(self, rollout, generator=None, **kw):
        raise M.NonFiniteError("non-finite training metrics: ['policy_loss']")

    monkeypatch.setattr(M.Learner, "update", bad_update)
    sp = SelfPlay(env.method, env, seed=RUN_SEED, run_dir=tmp_path / "nan")
    with pytest.raises(M.NonFiniteError):
        sp.run()
    state = json.loads((tmp_path / "nan" / "self_play_state.json").read_text())
    assert state["archive"] == [] and state["active"]["checkpoint"] and state["active"]["update"] == 0
