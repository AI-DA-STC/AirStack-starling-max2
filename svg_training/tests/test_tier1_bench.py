import torch
from svg_training.models.placeholder import PlaceholderResponse
from svg_training.envs.tier1_bench import Tier1BenchCfg, Tier1BenchEnv

def test_delay_then_lag():
    m = PlaceholderResponse(1, 1, dt_s=0.05, delay_s=0.15, lag_s=0.55, speed_cap_mps=4.0, device="cpu")
    cmd = torch.tensor([[[1.0, 0, 0]]])
    v = [m.step(cmd)[0, 0, 0].item() for _ in range(40)]
    assert v[0] == v[1] == v[2] == 0.0 and v[3] > 0.0            # 0.15 s = 3 steps of pure delay
    assert abs(v[3 + 11] - 0.632) < 0.05                          # one lag time constant (0.55 s = 11 steps) later
    assert v[-1] < 1.0 and all(b >= a for a, b in zip(v, v[1:]))

def test_speed_cap():
    m = PlaceholderResponse(1, 1, speed_cap_mps=1.0, device="cpu")
    for _ in range(400): v = m.step(torch.tensor([[[30.0, 40.0, 0]]]))
    assert v.norm(dim=-1).max() <= 1.0 + 1e-4

def _env(**kw):
    base = dict(num_games=64, guards=2, strikes=1, world="open", n_obstacles=0, n_rays=0, line_of_sight=False, device="cpu")
    return Tier1BenchEnv(Tier1BenchCfg(**{**base, **kw}))

def test_shapes_and_finite():
    e = _env(world="primitives", n_obstacles=10, n_rays=32, line_of_sight=True)
    o = e.step(torch.zeros(64, 3, 4))
    assert o["pos_m"].shape == (64, 3, 3) and o["ranges_m"].shape == (64, 3, 32) and o["visible"].shape == (64, 3, 3)
    assert all(torch.isfinite(o[k]).all() for k in ("pos_m", "vel_mps", "ranges_m"))

def test_contact_tag_at_half_metre_between_teams_only():
    e = _env(num_games=2)
    e.pos_m[:] = torch.tensor([[0.0, 0, 2], [5.0, 0, 2], [0.49, 0, 2]])     # guard, guard, strike
    assert e.step(torch.zeros(2, 3, 4))["tagged"].tolist() == [[True, False, True]] * 2
    e.pos_m[:] = torch.tensor([[0.0, 0, 2], [0.0, 0.3, 2], [0.51, 0, 2]])   # guards 0.3 m apart; strike 0.51 m and 0.59 m away: no tag
    assert not e.step(torch.zeros(2, 3, 4))["tagged"].any()

def test_no_resets_when_hovering_in_open_world():
    e = _env(num_games=256)
    fr = [e.step(torch.zeros(256, 3, 4))["reset_fraction"].item() for _ in range(20)]
    assert max(fr[1:]) == 0.0

def test_spawns_clear_of_structures():
    e = _env(num_games=256, world="primitives", n_obstacles=50)
    assert (e.world.sdf(e.pos_m) > 0.248).all()

def test_seed_reproducible():
    a, b = _env(seed=3), _env(seed=3)
    act = torch.rand(64, 3, 4)
    assert torch.equal(a.step(act)["pos_m"], b.step(act)["pos_m"])

def test_guard_speed_is_cap_over_1p5_in_norm():
    e = _env(num_games=4, guards=1, strikes=1)
    e.pos_m[:] = torch.tensor([[-10.0, 0, 4], [10.0, 0, 4]])
    for _ in range(200):
        e.pos_m[:] = torch.tensor([[-10.0, 0, 4], [10.0, 0, 4]])     # hold them in place: no contact, no wall
        o = e.step(torch.tensor([1.0, 1.0, 1.0, 0.0]).expand(4, 2, 4))
    speed = o["vel_mps"].norm(dim=-1)
    assert torch.allclose(speed[:, 0], torch.full((4,), 4.0 / 1.5), atol=0.02) and torch.allclose(speed[:, 1], torch.full((4,), 4.0), atol=0.02)
