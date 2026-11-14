"""Signed distance to analytic shapes, batched over games (no Python loops).

Shapes: ``N`` games, ``P`` query points, ``B`` boxes, ``C`` cylinders per game.
Negative inside, positive outside, ``+inf`` when a game has no shape of that kind.
"""
import torch
from torch import Tensor


def _empty(points_m: Tensor) -> Tensor:
    return torch.full(points_m.shape[:2], float("inf"), dtype=points_m.dtype, device=points_m.device)


def sdf_boxes(points_m: Tensor, centre_m: Tensor, half_m: Tensor) -> Tensor:
    """Signed distance to the nearest axis-aligned box.

    points_m [N, P, 3], centre_m [N, B, 3], half_m [N, B, 3] -> [N, P]; +inf when B == 0.
    """
    if centre_m.shape[1] == 0:
        return _empty(points_m)
    q = (points_m[:, :, None, :] - centre_m[:, None, :, :]).abs() - half_m[:, None, :, :]  # [N, P, B, 3]
    outside = q.clamp(min=0.0).norm(dim=-1)
    inside = q.amax(dim=-1).clamp(max=0.0)
    return (outside + inside).amin(dim=2)


def sdf_cylinders(points_m: Tensor, base_m: Tensor, radius_m: Tensor, height_m: Tensor) -> Tensor:
    """Signed distance to the nearest vertical (z-axis) capped cylinder standing on ``base_m``.

    points_m [N, P, 3], base_m [N, C, 3] (centre of the bottom disc), radius_m [N, C],
    height_m [N, C] -> [N, P]; +inf when C == 0.
    """
    if base_m.shape[1] == 0:
        return _empty(points_m)
    rel = points_m[:, :, None, :] - base_m[:, None, :, :]  # [N, P, C, 3]
    half_h = 0.5 * height_m[:, None, :]
    dr = rel[..., :2].norm(dim=-1) - radius_m[:, None, :]
    dz = (rel[..., 2] - half_h).abs() - half_h
    outside = torch.stack((dr, dz), dim=-1).clamp(min=0.0).norm(dim=-1)
    inside = torch.maximum(dr, dz).clamp(max=0.0)
    return (outside + inside).amin(dim=2)
