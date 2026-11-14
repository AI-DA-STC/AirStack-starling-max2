"""The world (static field plus per-game shapes), range rays and drone-to-drone line of sight."""
from dataclasses import dataclass

import torch
from torch import Tensor

from svg_training.worlds.field import DistanceField
from svg_training.worlds.shapes import sdf_boxes, sdf_cylinders

_HIT_M = 0.01  # a sphere-tracing ray closer than this to a surface has hit it


@dataclass
class World:
    """field: shared static map or None; box_* [N, B, 3]; cyl_base_m [N, C, 3], cyl_radius_m / cyl_height_m [N, C]."""
    field: DistanceField | None
    box_centre_m: Tensor
    box_half_m: Tensor
    cyl_base_m: Tensor
    cyl_radius_m: Tensor
    cyl_height_m: Tensor

    def sdf(self, points_m: Tensor) -> Tensor:
        """Signed distance to the nearest structure: points_m [N, P, 3] -> [N, P] (+inf if there is none)."""
        d = sdf_boxes(points_m, self.box_centre_m.to(points_m), self.box_half_m.to(points_m))
        d = torch.minimum(d, sdf_cylinders(points_m, self.cyl_base_m.to(points_m),
                                           self.cyl_radius_m.to(points_m), self.cyl_height_m.to(points_m)))
        if self.field is not None:
            d = torch.minimum(d, self.field.sample(points_m))
        return d


def ray_directions(n_rays: int, device="cpu", dtype=torch.float32) -> Tensor:
    """[R, 3] unit vectors: n_rays - 2 on a horizontal ring, then straight up, then straight down."""
    n_ring = max(n_rays - 2, 0)
    ang = 2.0 * torch.pi * torch.arange(n_ring, device=device, dtype=dtype) / max(n_ring, 1)
    ring = torch.stack((ang.cos(), ang.sin(), torch.zeros_like(ang)), dim=-1)
    updown = torch.tensor([[0.0, 0.0, 1.0], [0.0, 0.0, -1.0]], device=device, dtype=dtype)
    return torch.cat((ring, updown), dim=0)[:n_rays]


def _march(world: World, start_m: Tensor, dir_unit: Tensor, length_m: Tensor, n_steps: int):
    """Sphere-trace start_m [N, K, 3] along dir_unit [N, K, 3] up to length_m [N, K].

    Returns (travelled [N, K], hit [N, K] bool). A ray that gets within _HIT_M of a surface stops.

    Known limit (S0): the step count is fixed. A path that runs close beside a surface advances by
    that small clearance each step and may not reach its end in n_steps. The result is then
    conservative: cast_rays reports a range shorter than the true one, line_of_sight reports
    "blocked". Sensing cost is linear in n_steps. The step rule and count are to be set against a
    dense-sampling reference before obstacles are trained on (build step S3).
    """
    t = torch.zeros_like(length_m)
    hit = torch.zeros_like(length_m, dtype=torch.bool)
    for _ in range(n_steps):
        s = world.sdf(start_m + t[..., None] * dir_unit)
        hit = hit | (s < _HIT_M)
        step = torch.minimum(s.clamp(min=0.0), length_m - t)
        t = t + torch.where(hit, torch.zeros_like(step), step)
    hit = hit | (world.sdf(start_m + t[..., None] * dir_unit) < _HIT_M)
    return t, hit


def cast_rays(world: World, origin_m: Tensor, dirs: Tensor, max_range_m: float = 10.0,
              n_steps: int = 24) -> Tensor:
    """Range along each ray: origin_m [N, M, 3], dirs [R, 3] unit -> [N, M, R], capped at max_range_m.

    0 where the origin is inside a structure.
    """
    n, m, _ = origin_m.shape
    r = dirs.shape[0]
    o = origin_m[:, :, None, :].expand(n, m, r, 3).reshape(n, m * r, 3)
    d = dirs.to(origin_m)[None, None].expand(n, m, r, 3).reshape(n, m * r, 3)
    length = torch.full((n, m * r), float(max_range_m), dtype=origin_m.dtype, device=origin_m.device)
    t, _ = _march(world, o, d, length, n_steps)
    return t.reshape(n, m, r)


def line_of_sight(world: World, pos_m: Tensor, n_steps: int = 24) -> Tensor:
    """True where the segment between two drones is clear: pos_m [N, M, 3] -> [N, M, M] bool.

    Symmetric; the diagonal is True. Only the upper triangle is marched, then mirrored.
    """
    n, m, _ = pos_m.shape
    out = torch.eye(m, dtype=torch.bool, device=pos_m.device)[None].expand(n, m, m).clone()
    if m < 2:
        return out
    i, j = torch.triu_indices(m, m, 1, device=pos_m.device)
    a, b = pos_m[:, i], pos_m[:, j]
    seg = b - a
    length = seg.norm(dim=-1)
    t, hit = _march(world, a, seg / length.clamp(min=1e-9)[..., None], length, n_steps)
    clear = ~hit & (length - t <= 1e-4)
    out[:, i, j] = clear
    out[:, j, i] = clear
    return out
