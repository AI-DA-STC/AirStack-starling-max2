"""STE task L0.13 Does tier 2 train at all? The parts of source/svg_training/ste/tier2_train.py, on the CPU with the
PyTorch reference rigid-body world standing in for Isaac Lab: the gate files, the two tiers, the view of a world that
every tier 2 evaluation plays on (equal, game for game, to a world of its own size), the trainer's decision-boundary
restart on the physics drone, the physics agreement check (C-1a) with a known failure, the reserve arithmetic and the
verdict."""
import dataclasses
import math
import re

import numpy as np
import pytest
import torch

from svg_training.core.physics_layer import load_game_physics_params
from svg_training.opponents.scripted import make_strategy
from svg_training.ste import exploit, exploit_train, tier2_train as T

GATES = T.GATES_FILE
SMOKE = T.SMOKE_GATES_FILE


@pytest.fixture(scope="module")
def gates():
    return T.load_gates(GATES)


@pytest.fixture(scope="module")
def ref(gates):
    return exploit.load_reference(T.ROOT / gates.reference["file"])


def edited(tmp_path, old, new, src=GATES):
    text = src.read_text()
    assert old in text, old
    path = tmp_path / "gates.toml"
    path.write_text(text.replace(old, new, 1))
    return path


# ------------------------------------------------------------------------------------------------ the gate files
def test_the_gate_file_fixes_48_updates_in_both_arms_and_the_seed_once(gates):
    assert gates.per_update == 32 * 12 * 16384 == 6_291_456
    assert gates.planned_updates == 48 and gates.planned_game_steps == 301_989_888
    assert gates.run["cap_h_total"] == gates.arms["t1"]["cap_h"] + gates.arms["t2"]["cap_h"]
    assert gates.run["cap_h_total"] <= 6.0                       # the L0.13 task cap (configs/ste_learning.toml)
    assert gates.trainer["num_games"] == 16384 and gates.run["eval_games"] == 1000
    assert gates.run["opponent"] == "strike_straight" and gates.run["parked"] == "guard_parked_centre"
    assert T.pin_problems(gates) == []


def test_the_trainer_is_the_l012_guard_recipe(gates):
    l012 = exploit.load_gates()
    guard = exploit.side_settings(l012, "guard")
    for key, value in gates.trainer.items():
        if key in guard and key not in ("num_games", "game_steps_per_run", "curve_every_updates", "clip_reserve_s",
                                        "final_reserve_factor"):
            assert guard[key] == value, key
    assert exploit.sha256_file(exploit.GATES_FILE) == gates.l012["gates_sha256"]
    assert l012.games["base"].file == gates.run["game_file"] and l012.games["base"].sha256 == gates.run["game_sha256"]


def test_the_smoke_file_differs_only_in_its_smoke_lines():
    def strip(text):
        return [ln for ln in text.splitlines() if "smoke" not in ln.lower() and not ln.startswith("#")]
    full = [ln for ln in GATES.read_text().splitlines() if not ln.startswith("#")]
    smoke = SMOKE.read_text().splitlines()
    marked = [ln for ln in smoke if "# smoke" in ln and not ln.startswith("#")]
    assert len(marked) == 5
    assert strip(SMOKE.read_text()) == [ln for ln in full if not any(
        ln.split("=")[0].strip() == m.split("=")[0].strip() for m in marked)]
    s = T.load_gates(SMOKE)
    assert s.planned_updates == 1 and s.trainer["num_games"] == 16384 and s.run["eval_games"] == 1000


@pytest.mark.parametrize("old, new, why", [
    ('order = ["t1", "t2"]', 'order = ["t2", "t1"]', "arms.order"),
    ('side = "guard"', 'side = "strike"', "run.side"),
    ("eval_games = 1000 ", "eval_games = 6000 ", "exceeds trainer.num_games"),
    ("cap_h_total = 3.25 ", "cap_h_total = 3.0 ", "cap_h_total"),
    ('parked = "guard_parked_centre"', 'parked = "strike_straight"', "scripted guard"),
    ("[videos]", "[videos]\nextra = 1", "unknown key"),
    ('tier_difference = ["starling.backend"]', 'tier_difference = ["drone"]', "tier_difference"),
])
def test_the_gate_file_refuses_a_bad_value(tmp_path, old, new, why):
    with pytest.raises(ValueError, match=re.escape(why)):
        T.load_gates(edited(tmp_path, old, new))


# ------------------------------------------------------------------------------------------------ the two tiers
def test_tier_2_is_the_same_game_file_with_the_physics_drone(gates):
    t1, t2 = T.tier_cfg(gates, 1), T.tier_cfg(gates, 2)
    assert T.cfg_differences(t1, t2) == ["starling.backend"]
    assert t2.starling.backend == "physics" and t1.starling.backend != "physics"
    assert t1.rewards.shaping_weight == gates.trainer["shaping_weight"] and t1.tag.mode != "off"


# ------------------------------------------------------------------------------------------------ the view of a world
def _play(gates, ref, world, cells, n, ticks=90):
    cfg = T.tier_cfg(gates, 2)
    return exploit.play_cells(cfg, gates.run["size"], ref, cells, n, "cpu", ref.meta["seed"], ticks, world=world)


def test_a_batch_on_a_view_equals_the_batch_on_a_world_of_its_own_size(gates, ref):
    cfg = T.tier_cfg(gates, 2)
    params = load_game_physics_params(cfg)
    cells, n = [("guard_parked_centre", "strike_straight"), ("guard_mark_edge", "strike_straight")], 6
    own = _play(gates, ref, T.torch_world_factory(len(cells) * n, 6, params, "cpu"), cells, n)
    big = T.torch_world_factory(len(cells) * n + 5, 6, params, "cpu")
    before = big.state()[0][len(cells) * n:].clone()
    on_view = _play(gates, ref, T.view(big, len(cells) * n, params), cells, n)
    for key in ("outcome", "end_step", "tags", "strikes_left", "guards_removed"):
        assert np.array_equal(own[key], on_view[key]), key
    assert np.allclose(own["closest_3d_m"], on_view["closest_3d_m"])
    idle = big.state()[0][len(cells) * n:]
    assert float((idle - before).norm(dim=-1).max()) < 1e-3       # the parked games stayed where they were


def test_a_view_of_the_whole_world_is_the_world_and_a_bad_size_refuses(gates):
    params = load_game_physics_params(T.tier_cfg(gates, 2))
    w = T.torch_world_factory(4, 6, params, "cpu")
    assert T.view(w, 4, params) is w
    with pytest.raises(ValueError):
        T.SliceWorld(w, 5, params.airframe.mass_kg)


# ------------------------------------------------------------------------------------------------ the trainer on tier 2
def test_a_decision_boundary_restart_puts_the_new_starts_in_the_physics_world(gates):
    cfg = T.tier_cfg(gates, 2)
    params = load_game_physics_params(cfg)
    n = 8
    world = T.torch_world_factory(n, 6, params, "cpu")
    game = exploit_train.TrainGame(cfg, n, 3, 3, device="cpu", seed=5, world=world)
    assert game.motion.startswith("physics/")
    env = exploit_train.DecisionEnv(game, 12, "guard", make_strategy("strike_straight", "strike", cfg, n, "cpu", 207))
    env.reset()
    zero = {a: torch.zeros(n, 4) for a in env.possible_agents}
    ended_any = False
    for _ in range(12):                                          # parked Guards v straight Strikes: games end in ~60 ticks
        _obs, _rew, _term, _trunc, info = env.step(zero)
        if bool(info["decision_ended"].any()):
            ended_any = True
            ended = info["decision_ended"]
            game._starling.flush()
            pos = world.state()[0]
            assert torch.allclose(pos[ended], game.pos_m[ended], atol=1e-5)   # the world holds the boundary restart
            assert bool((game.steps[ended] == 0).all())
            break
    assert ended_any


def test_one_update_on_tier_2_moves_the_policy_and_counts_its_game_steps(gates):
    cfg = T.tier_cfg(gates, 2)
    params = load_game_physics_params(cfg)
    n = 4
    game = exploit_train.TrainGame(cfg, n, 3, 3, device="cpu", seed=5, world=T.torch_world_factory(n, 6, params, "cpu"))
    env = exploit_train.DecisionEnv(game, 12, "guard", make_strategy("strike_straight", "strike", cfg, n, "cpu", 207))
    settings = dict(gates.trainer, rollouts=2, learning_epochs=1, mini_batches=1)
    learner = exploit_train.Learner(settings, env, "cpu", 130102, 1)
    before = [p.detach().clone() for p in learner.agent.policies[learner.names[0]].parameters()]
    stats = learner.update()
    after = list(learner.agent.policies[learner.names[0]].parameters())
    assert stats["game_steps"] == 2 * 12 * n and stats["nonfinite_actions"] == 0
    assert any(not torch.equal(a, b) for a, b in zip(before, after))


# ------------------------------------------------------------------------------------------------ C-1a
def test_the_physics_agreement_passes_on_the_reference_world_and_on_a_view(gates):
    small = dataclasses.replace(gates, controls=dict(gates.controls, agree_ticks=6))
    cfg = T.tier_cfg(gates, 2)
    params = load_game_physics_params(cfg)
    same = T.physics_agreement(small, cfg, T.torch_world_factory(4, 6, params, "cpu"), "cpu")
    assert same["pass"] and same["max_gap_m"] == 0.0 and same["ticks"] == 6 and same["games"] == 4
    big = T.torch_world_factory(7, 6, params, "cpu")
    on_view = T.physics_agreement(small, cfg, T.view(big, 4, params), "cpu")
    assert on_view["pass"] and on_view["max_gap_m"] < 1e-5 and on_view["world"].endswith("[:4]")


def test_the_physics_agreement_fails_on_a_heavier_drone(gates):
    small = dataclasses.replace(gates, controls=dict(gates.controls, agree_ticks=20))
    cfg = T.tier_cfg(gates, 2)
    params = load_game_physics_params(cfg)
    heavy = dataclasses.replace(params.airframe, mass_kg=params.airframe.mass_kg * 1.5)
    from svg_training.models.rigid_body import TorchRigidBodyWorld
    out = T.physics_agreement(small, cfg, TorchRigidBodyWorld(4, 6, heavy, params.physics_dt_s, "cpu"), "cpu")
    assert not out["pass"] and out["max_gap_m"] > gates.controls["agree_max_m"]


# ------------------------------------------------------------------------------------------------ time
def test_the_reserve_and_the_room_before_an_update(gates):
    assert T.final_reserve_s(gates, "t2", 10.0) == 1500.0                    # the floor
    assert T.final_reserve_s(gates, "t2", 600.0) == 2.0 * (2 * 600.0 + 300.0)
    assert T.room_needed_s(gates, 1500.0, None, None, True) == 1500.0
    assert T.room_needed_s(gates, 1500.0, 100.0, 60.0, False) == 1500.0 + 1.5 * 100.0
    assert T.room_needed_s(gates, 1500.0, 100.0, 60.0, True) == 1500.0 + 1.5 * 160.0
    assert [u for u in range(1, 49) if T.curve_due(gates, u)] == [6, 12, 18, 24, 30, 36, 42, 48]


# ------------------------------------------------------------------------------------------------ the verdict
def test_the_bar_is_the_trained_lower_bound_above_the_parked_upper_bound():
    assert T.trains_bar((600, 1000), (534, 1000))["cleared"]          # 0.569 > 0.565
    assert not T.trains_bar((590, 1000), (534, 1000))["cleared"]
    assert not T.trains_bar((0, 0), (534, 1000))["cleared"]


def test_the_verdict_words():
    p = T.tier2_verdict((800, 1000), (534, 1000), True, 301_989_888, True)
    assert p["verdict"] == T.PASS_WORD and p["reading"] is None
    f = T.tier2_verdict((540, 1000), (534, 1000), True, 301_989_888, False)
    assert f["verdict"] == T.FAIL_WORD and "does not single out tier 2" in f["reading"]
    f2 = T.tier2_verdict((540, 1000), (534, 1000), True, 301_989_888, True)
    assert f2["verdict"] == T.FAIL_WORD and "tier 1 trained at" in f2["reading"]
    s = T.tier2_verdict((800, 1000), (534, 1000), False, 200_000_000, True)
    assert s["verdict"] == T.TOO_SLOW and s["bar_at_steps_reached"] and "200,000,000" in s["reading"]


def test_a_snapshot_keeps_what_a_team_needs(gates):
    cfg = T.tier_cfg(gates, 1)
    game = exploit_train.TrainGame(cfg, 2, 3, 3, device="cpu", seed=1)
    env = exploit_train.DecisionEnv(game, 12, "guard", make_strategy("strike_straight", "strike", cfg, 2, "cpu", 3))
    learner = exploit_train.Learner(dict(gates.trainer, rollouts=2, learning_epochs=1, mini_batches=1), env, "cpu", 1)
    snap = T.snapshot(learner.modules())
    assert all(set(m) == set(T.SNAPSHOT_KEYS) for m in snap.values())
    team = exploit_train.team_from_modules("guard", snap, list(gates.trainer["hidden"]), "cpu")
    obs = game.reset()["guard"]
    assert torch.equal(team.act(obs), learner.team().act(obs))


# ------------------------------------------------------------------------------------------------ fix round (QC F1, T2)
def test_a_batch_reports_its_drone_model_its_upsets_and_its_non_finite_wrenches(gates, ref):
    cfg2 = T.tier_cfg(gates, 2)
    params = load_game_physics_params(cfg2)
    cells, n = [("guard_parked_centre", "strike_straight")], 4
    on2 = _play(gates, ref, T.torch_world_factory(n, 6, params, "cpu"), cells, n)
    assert on2["motion"].startswith("physics/") and on2["physics_nonfinite"] == 0
    assert on2["upset"].shape == (n,) and on2["upset"].dtype == bool
    on1 = exploit.play_cells(T.tier_cfg(gates, 1), gates.run["size"], ref, cells, n, "cpu", ref.meta["seed"], 90)
    assert on1["motion"] == "starling" and on1["physics_nonfinite"] == 0 and not on1["upset"].any()
    assert T.batch_tier(on2) == 2 and T.batch_tier(on1) == 1


def test_the_either_tier_reading_needs_the_tier_1_control_at_its_full_budget():     # QC D3
    f = T.tier2_verdict((540, 1000), (534, 1000), True, 301_989_888, False, t1_budget_reached=False)
    assert f["verdict"] == T.FAIL_WORD and "does not single out" not in f["reading"]
    assert "stopped before its budget" in f["reading"]


def test_a_clip_recording_stops_on_request(gates):                                  # QC D4
    from svg_training.viz.replay import RecordingStopped, record_games
    cfg = T.tier_cfg(gates, 1)
    with pytest.raises(RecordingStopped):
        record_games(cfg, 3, 3, "guard_parked_centre", "strike_straight", num_games=2, seed=1, band=0, max_steps=20,
                     should_stop=lambda: True)


def test_the_projection_for_the_run_of_record(gates):                               # QC C1
    # QC's inequality for t2: pre + 48.5 U + 8.5 C <= 2.5 h - 1,500 s = 7,500 s
    p = T.projection(gates, "t2", pre_s=300.0, update_s=94.0, curve_s=60.0, batch_s=30.0)
    assert p["reads"] == 8 and p["updates"] == 48
    assert p["need_s"] == 300.0 + 48.5 * 94.0 + 8.5 * 60.0 and p["available_s"] == 7500.0
    assert math.isclose(p["margin_s"], 7500.0 - p["need_s"])
    u_max = (7500.0 - 300.0 - 8.5 * 60.0) / 48.5
    assert math.isclose(p["break_even_game_steps_per_s"], gates.per_update / u_max)
    assert 45_000 < p["break_even_game_steps_per_s"] < 50_000


def test_a_view_parks_its_idle_games_and_never_writes_them(gates):                   # M14, M30
    params = load_game_physics_params(T.tier_cfg(gates, 2))
    w = T.torch_world_factory(6, 6, params, "cpu")
    pos, quat, lin, ang = (t.clone() for t in w.state())
    every = torch.ones(6, 6, dtype=torch.bool)
    tilted = torch.tensor([0.9, 0.3, 0.2, 0.2]) / torch.tensor([0.9, 0.3, 0.2, 0.2]).norm()
    w.write_state(every, pos, tilted.expand(6, 6, 4).contiguous(), torch.ones_like(lin), torch.ones_like(ang))
    v = T.SliceWorld(w, 4, params.airframe.mass_kg)
    _p, q, l, a = w.state()
    assert torch.allclose(q[4:], torch.tensor(T.QUAT_ONE).expand(2, 6, 4)) and float(l[4:].abs().max()) == 0.0
    assert float(a[4:].abs().max()) == 0.0                                  # parked: level, at rest
    w.write_state(every & (torch.arange(6)[:, None] >= 4), w.state()[0], w.state()[1], torch.full_like(lin, 0.5),
                  torch.zeros_like(ang))                                    # the idle games move (as a test probe)
    v.reset(torch.ones(4, 6, dtype=torch.bool), torch.zeros(4, 6, 3), torch.tensor(T.QUAT_ONE).expand(4, 6, 4))
    assert torch.allclose(w.state()[2][4:], torch.full((2, 6, 3), 0.5))   # a view's write never reaches them
