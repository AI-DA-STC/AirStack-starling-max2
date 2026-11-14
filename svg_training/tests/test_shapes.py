import torch
from svg_training.worlds.shapes import sdf_boxes, sdf_cylinders

def test_box_distances():
    c = torch.zeros(1, 1, 3); h = torch.tensor([[[1.0, 1.0, 1.0]]])
    p = torch.tensor([[[3.0, 0, 0], [0, 0, 0], [1.0, 0, 0], [2.0, 2.0, 0]]])
    d = sdf_boxes(p, c, h)
    assert torch.allclose(d, torch.tensor([[2.0, -1.0, 0.0, 2 ** 0.5]]), atol=1e-6)

def test_cylinder_distances():
    base = torch.zeros(1, 1, 3); r = torch.tensor([[0.5]]); hgt = torch.tensor([[2.0]])
    p = torch.tensor([[[1.5, 0, 1.0], [0, 0, 1.0], [0, 0, 3.0]]])
    assert torch.allclose(sdf_cylinders(p, base, r, hgt), torch.tensor([[1.0, -0.5, 1.0]]), atol=1e-6)

def test_no_shapes_is_free_space_and_batched():
    p = torch.rand(7, 5, 3)
    assert torch.isinf(sdf_boxes(p, torch.zeros(7, 0, 3), torch.zeros(7, 0, 3))).all()
    assert sdf_boxes(p, torch.zeros(7, 4, 3), torch.ones(7, 4, 3)).shape == (7, 5)
