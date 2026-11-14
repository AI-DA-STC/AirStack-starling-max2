import torch
from svg_training.worlds.field import DistanceField, synthetic_field

def _ramp():
    g = torch.arange(4.0)[:, None, None].expand(4, 3, 2).contiguous()   # value = x index
    return DistanceField(g, origin_m=torch.zeros(3), voxel_m=0.5)

def test_sample_at_voxel_centres_and_between():
    f = _ramp()
    pts = torch.tensor([[0.0, 0, 0], [0.5, 0.5, 0.5], [0.25, 0, 0], [1.5, 1.0, 0.5]])
    assert torch.allclose(f.sample(pts), torch.tensor([0.0, 1.0, 0.5, 3.0]), atol=1e-5)

def test_outside_returns_border_value_and_is_finite():
    f = _ramp()
    out = f.sample(torch.tensor([[-10.0, 0, 0], [99.0, 0, 0]]))
    assert torch.allclose(out, torch.tensor([0.0, 3.0])) and torch.isfinite(out).all()

def test_any_leading_shape():
    assert _ramp().sample(torch.zeros(5, 8, 32, 3)).shape == (5, 8, 32)

def test_synthetic_field_size():
    f = synthetic_field(size_m=(8.0, 8.0, 4.0), voxel_m=0.2, n_boxes=5)
    assert tuple(f.grid.shape) == (40, 40, 20) and f.grid.dtype == torch.float16
    assert (f.grid < 0).any() and (f.grid > 0).any()
