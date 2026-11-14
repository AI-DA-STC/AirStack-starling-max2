"""Voxel signed-distance field (the static map) with trilinear sampling, plus a synthetic one."""
import torch
import torch.nn.functional as F
from torch import Tensor

from svg_training.worlds.shapes import sdf_boxes


def _pick_sample_dtype(grid: Tensor) -> torch.dtype:
    """Sampling dtype: always float32 (half-precision sample coordinates give ~4 cm error on a 400-voxel axis,
    and CPU grid_sample lacks some half paths); the stored grid keeps its own dtype."""
    return torch.float32


class DistanceField:
    """grid [X, Y, Z]; ``origin_m`` [3] is the world position of voxel [0, 0, 0]'s centre."""

    def __init__(self, grid: Tensor, origin_m: Tensor, voxel_m: float):
        self.grid = grid
        self.origin_m = origin_m.to(device=grid.device)
        self.voxel_m = float(voxel_m)
        self.sample_dtype = _pick_sample_dtype(grid)
        # [1, 1, Z, Y, X]: grid_sample's coordinates are (x, y, z) = last three dims reversed
        self._vol = grid.to(self.sample_dtype).permute(2, 1, 0)[None, None].contiguous()
        self._span = torch.tensor([max(s - 1, 1) for s in grid.shape], dtype=torch.float32, device=grid.device)

    def sample(self, points_m: Tensor) -> Tensor:
        """Trilinear distance at points_m [..., 3] -> [...] in points_m's dtype; outside = border value."""
        lead = points_m.shape[:-1]
        idx = (points_m.reshape(-1, 3).to(torch.float32) - self.origin_m.to(torch.float32)) / self.voxel_m
        coords = (2.0 * idx / self._span - 1.0).to(self.sample_dtype)
        out = F.grid_sample(self._vol, coords.reshape(1, 1, 1, -1, 3),
                            mode="bilinear", padding_mode="border", align_corners=True)
        return out.reshape(lead).to(points_m.dtype)


def synthetic_field(size_m: tuple[float, float, float] = (80.0, 80.0, 20.0), voxel_m: float = 0.2,
                    n_boxes: int = 60, seed: int = 0, device="cpu", dtype=torch.float16) -> DistanceField:
    """A random-box distance field the size of the construction-site crop.

    Centred on the origin in x and y, floor at z = 0 (boxes stand on it). Built in chunks of
    voxels so the pairwise distance tensors stay near 100 MB while building.
    """
    nx, ny, nz = (round(s / voxel_m) for s in size_m)
    gen = torch.Generator(device="cpu").manual_seed(seed)
    u = torch.rand(n_boxes, 3, generator=gen)
    half = torch.stack((0.5 + 3.5 * u[:, 0], 0.5 + 3.5 * u[:, 1], 0.5 + 4.5 * u[:, 2]), dim=-1)
    size = torch.tensor(size_m)
    centre = (torch.rand(n_boxes, 3, generator=gen) - 0.5) * size
    centre[:, 2] = half[:, 2]
    centre, half = centre.to(device)[None], half.to(device)[None]
    origin = torch.tensor([-size_m[0] / 2 + voxel_m / 2, -size_m[1] / 2 + voxel_m / 2, voxel_m / 2], device=device)

    total = nx * ny * nz
    chunk = max(1, int(8e6 // max(n_boxes, 1)))
    flat = torch.empty(total, dtype=dtype, device=device)
    for start in range(0, total, chunk):  # build-time loop over chunks, not a step-time loop
        ids = torch.arange(start, min(start + chunk, total), device=device)
        ijk = torch.stack((ids // (ny * nz), (ids // nz) % ny, ids % nz), dim=-1).to(torch.float32)
        pts = origin + ijk * voxel_m
        flat[start:start + ids.numel()] = sdf_boxes(pts[None], centre, half)[0].to(dtype)
    return DistanceField(flat.reshape(nx, ny, nz), origin, voxel_m)
