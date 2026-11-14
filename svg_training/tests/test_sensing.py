import torch
from svg_training.worlds.sensing import World, ray_directions, cast_rays, line_of_sight

def _wall(n=2):   # a 0.4 m thick wall across x = 3, per game
    z = torch.zeros
    return World(None, torch.tensor([[[3.0, 0, 1.0]]]).expand(n, 1, 3), torch.tensor([[[0.2, 5.0, 5.0]]]).expand(n, 1, 3),
                 z(n, 0, 3), z(n, 0), z(n, 0))

def test_ray_directions():
    d = ray_directions(34)
    assert d.shape == (34, 3) and torch.allclose(d.norm(dim=-1), torch.ones(34))
    assert torch.allclose(d[-2], torch.tensor([0.0, 0, 1])) and torch.allclose(d[-1], torch.tensor([0.0, 0, -1]))
    assert ray_directions(0).shape == (0, 3)

def test_ray_hits_wall_at_known_range():
    o = torch.tensor([[[0.0, 0, 1.0]]]).expand(2, 1, 3)
    r = cast_rays(_wall(), o, torch.tensor([[1.0, 0, 0], [-1.0, 0, 0]]), max_range_m=10.0)
    assert r.shape == (2, 1, 2)
    assert torch.allclose(r[..., 0], torch.full((2, 1), 2.8), atol=0.02) and torch.allclose(r[..., 1], torch.full((2, 1), 10.0))

def test_ray_from_inside_structure_is_zero_and_finite():
    r = cast_rays(_wall(), torch.tensor([[[3.0, 0, 1.0]]]).expand(2, 1, 3), ray_directions(6))
    assert torch.isfinite(r).all() and (r == 0).all()

def test_line_of_sight_blocked_and_clear():
    p = torch.tensor([[[0.0, 0, 1.0], [6.0, 0, 1.0], [0.0, 2.0, 1.0]]]).expand(2, 3, 3)
    los = line_of_sight(_wall(), p)
    assert los.shape == (2, 3, 3) and los.dtype == torch.bool
    assert not los[0, 0, 1] and not los[0, 1, 0] and los[0, 0, 2] and los[0].diagonal().all()

def test_empty_world_sees_everything():
    z = torch.zeros
    w = World(None, z(1, 0, 3), z(1, 0, 3), z(1, 0, 3), z(1, 0), z(1, 0))
    assert line_of_sight(w, torch.rand(1, 4, 3)).all()
    assert (cast_rays(w, torch.rand(1, 4, 3), ray_directions(8), max_range_m=5.0) == 5.0).all()
