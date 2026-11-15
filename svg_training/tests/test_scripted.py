"""Scripted opponents: hand-built observations and one pass through check_strategy each (S2 Task 5)."""
import pathlib
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.game import SCENARIOS, STRIKE_WIN, SvgGame  # noqa: E402
from svg_training.core.game_config import load_game_cfg  # noqa: E402
from svg_training.core.observations import OBS_DIM, ObsView  # noqa: E402
from svg_training.core.strategy import check_strategy  # noqa: E402
from svg_training.opponents.scripted import REGISTRY, make_strategy  # noqa: E402

CFG = load_game_cfg(use_local=False)[0]
V = ObsView()
PG = CFG.pad_guards


def drone(team, pos, vel=(0.0, 0.0), r=1.0):
    o = torch.zeros(OBS_DIM)
    o[0:2] = torch.tensor(pos)
    o[3:5] = torch.tensor(vel)
    o[V.zone_radius], o[V.arena_half], o[V.time_left] = r, 4.0, 30.0
    o[V.team] = -1.0 if team == "guard" else 1.0
    o[V.alive] = 1.0
    return o


def put(o, slot, rel_pos, rel_vel=(0.0, 0.0)):
    s = V.slot(slot)
    o[s.start:s.start + 2] = torch.tensor(rel_pos)
    o[s.start + 3:s.start + 5] = torch.tensor(rel_vel)
    o[s.start + 6] = 1.0


def obs_of(*drones):
    return torch.stack(drones)[None]        # [1, M, OBS_DIM]


def mk(name, team):
    return make_strategy(name, team, CFG, 1, "cpu", 0)


def test_mark_edge_points_at_edge_target():
    g = drone("guard", (0.0, 0.0))
    put(g, PG, (3.0, 0.0))
    a = mk("guard_mark_edge", "guard").act(obs_of(g))
    assert torch.allclose(a[0, 0, :2], torch.tensor([1.0, 0.0]), atol=1e-4)
    g2 = drone("guard", (1.0, 0.0))
    put(g2, PG, (2.0, 0.0))
    assert mk("guard_mark_edge", "guard").act(obs_of(g2))[0, 0, :2].norm() < 0.05


def test_mark_inside_target_is_0_6_r():
    g = drone("guard", (0.6, 0.0))
    put(g, PG, (2.4, 0.0))
    assert mk("guard_mark_inside", "guard").act(obs_of(g))[0, 0, :2].norm() < 0.05
    g = drone("guard", (1.0, 0.0))
    put(g, PG, (2.0, 0.0))
    a = mk("guard_mark_inside", "guard").act(obs_of(g))[0, 0, :2]
    assert a[0] < -0.9


def test_marking_skips_missing_strike():
    # two Guard drones; Strike slot 0 absent, slot 1 present at (0, 3) rel zone
    gs = [drone("guard", (0.0, 0.0)), drone("guard", (0.0, 0.0))]
    for g in gs:
        put(g, PG + 1, (0.0, 3.0))
    a = mk("guard_mark_edge", "guard").act(obs_of(*gs))
    assert torch.allclose(a[0, :, :2], torch.tensor([[0.0, 1.0]] * 2), atol=1e-4)


def test_marking_cycles_over_live_strikes():
    gs = [drone("guard", (0.0, 0.0)) for _ in range(3)]
    for g in gs:
        put(g, PG, (3.0, 0.0))
        put(g, PG + 1, (0.0, 3.0))
    a = mk("guard_mark_edge", "guard").act(obs_of(*gs))[0, :, :2]
    assert torch.allclose(a, torch.tensor([[1.0, 0.0], [0.0, 1.0], [1.0, 0.0]]), atol=1e-4)


def test_field_pushes_off_close_teammate():
    g = drone("guard", (1.0, 0.0))
    put(g, PG, (2.0, 0.0))
    base = mk("guard_field", "guard").act(obs_of(g))[0, 0, :2]
    put(g, 0, (0.0, 0.5))
    a = mk("guard_field", "guard").act(obs_of(g))[0, 0, :2]
    assert a[1] < 0 and base[1].abs() < 1e-6
    put(g, 0, (0.0, 2.0))                       # beyond 1.1 m: no push
    assert torch.allclose(mk("guard_field", "guard").act(obs_of(g))[0, 0, :2], base)


def test_mirror_copies_tangential_speed():
    g = drone("guard", (1.2, 0.0))
    put(g, PG, (1.8, 0.0), (0.0, 0.3))          # Strike at (3, 0) moving +y
    a = mk("guard_mirror", "guard").act(obs_of(g))[0, 0, :2]
    assert a[1] > 0.5 and a[0].abs() < 0.1


def test_straight_is_unit_vector_to_centre():
    s = drone("strike", (-3.0, 4.0))
    a = mk("strike_straight", "strike").act(obs_of(s))[0, 0]
    assert torch.allclose(a[:2], torch.tensor([0.6, -0.8]), atol=1e-5) and (a[2:] == 0).all()


def test_flank_goes_round_a_guard_on_the_line():
    s = drone("strike", (-3.0, 0.0))
    put(s, 0, (2.0, 0.0))
    a = mk("strike_flank", "strike").act(obs_of(s))[0, 0, :2]
    assert a[1].abs() > 0.3 and a[0] > 0
    s2 = drone("strike", (-3.0, 0.0))
    put(s2, 0, (2.0, 3.0))                      # far from the line
    assert torch.equal(mk("strike_flank", "strike").act(obs_of(s2)), mk("strike_straight", "strike").act(obs_of(s2)))
    s3 = drone("strike", (-3.0, 0.0))
    put(s3, 0, (-2.0, 0.0))                     # behind: not in the way
    assert torch.equal(mk("strike_flank", "strike").act(obs_of(s3)), mk("strike_straight", "strike").act(obs_of(s3)))
    s4 = drone("strike", (-3.0, 0.0))
    put(s4, 0, (2.0, -0.2))                     # offset to -y: goes round on that side
    assert mk("strike_flank", "strike").act(obs_of(s4))[0, 0, 1] < -0.3


def test_out_drone_gets_zero_action():
    s = torch.zeros(OBS_DIM)
    s[V.team] = 1.0
    assert (mk("strike_straight", "strike").act(obs_of(s)) == 0).all()


def test_wrong_team_refused():
    with pytest.raises(ValueError):
        mk("guard_field", "strike")


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_scripted_read_only_obs(name):
    team = "guard" if name.startswith("guard") else "strike"
    strat = make_strategy(name, team, CFG, 3, "cpu", 1)
    g = SvgGame(CFG, 3, 2, 2, device="cpu", seed=2)
    check_strategy(strat, g, steps=60)
    assert strat.team == team and strat.name


def test_random_is_seeded_and_in_range():
    obs = torch.zeros(4, 2, OBS_DIM)
    a1 = make_strategy("random", "guard", CFG, 4, "cpu", 5).act(obs)
    a2 = make_strategy("random", "guard", CFG, 4, "cpu", 5).act(obs)
    assert torch.equal(a1, a2) and a1.abs().max() <= 1 and a1.abs().sum() > 0


def test_scripted_strike_beats_still_guard_on_open_lab():
    g = SvgGame(CFG, 2, 1, 1, device="cpu", scenario=SCENARIOS["lab4_open"])
    s = mk("strike_straight", "strike")
    obs = g.reset()
    for _ in range(60):
        out = g.step({"guard": torch.zeros(2, 1, 4), "strike": s.act(obs["strike"])})
        obs = out.obs
        if out.done.all():
            break
    assert bool(out.done.all()) and (out.outcome == STRIKE_WIN).all()


def test_make_strategy_module_spec():
    z = make_strategy("svg_training.opponents.scripted:ZeroActions", "guard", CFG, 2, "cpu", 0)
    assert z.act(torch.zeros(2, 3, OBS_DIM)).abs().sum() == 0
    with pytest.raises(KeyError):
        make_strategy("nope", "guard", CFG, 2, "cpu", 0)
