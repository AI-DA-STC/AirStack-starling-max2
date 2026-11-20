"""S2 arenas and starting positions, drawn for all games at once (no loop over games, no host reads)."""
from __future__ import annotations

import math
from dataclasses import dataclass

import torch
from torch import Tensor

from .game_config import START_MODES, ArenaCfg, GameCfg

GUARD, STRIKE = "guard", "strike"
BANDS = ("lab", "middle", "large")
N_CANDIDATES = 8


@dataclass
class Arenas:
    """One arena per game. Shapes: side_m, half_m, zone_radius_m, band [N]; zone_centre_m [N, 2].
    ``band`` is a long index into BANDS."""
    side_m: Tensor
    half_m: Tensor
    zone_centre_m: Tensor
    zone_radius_m: Tensor
    band: Tensor

    def merge(self, other: "Arenas", take_other: Tensor) -> "Arenas":
        """Per game: ``other`` where take_other [N] bool, else self."""
        def pick(old: Tensor, new: Tensor) -> Tensor:
            m = take_other.reshape(-1, *([1] * (old.dim() - 1)))
            return torch.where(m, new, old)
        return Arenas(pick(self.side_m, other.side_m), pick(self.half_m, other.half_m),
                      pick(self.zone_centre_m, other.zone_centre_m),
                      pick(self.zone_radius_m, other.zone_radius_m), pick(self.band, other.band))


def band_index_of_side(cfg: ArenaCfg, side_m: float) -> int:
    """Index into BANDS of the first band whose upper edge is at least side_m (the last band otherwise)."""
    for i, name in enumerate(BANDS):
        if side_m <= cfg.bands_m[name][1]:
            return i
    return len(BANDS) - 1


def draw_arenas(cfg: ArenaCfg, n: int, gen: torch.Generator, device, band: int | None = None) -> Arenas:
    """Draw n arenas. Band first (weights), then the side uniform inside the band (D5); zone radius is a
    fraction of the side; the zone keeps ``zone_wall_margin_m`` from every wall. All outputs [N] / [N, 2]."""
    if band is not None and not 0 <= band < len(BANDS):
        raise ValueError(f"band must be 0..{len(BANDS) - 1} or None, got {band!r}")
    if band is None:
        w = cfg.band_weights
        tot = float(sum(w))
        c0, c1 = w[0] / tot, (w[0] + w[1]) / tot
        u = torch.rand(n, generator=gen, device=device)
        b = (u >= c0).long() + (u >= c1).long()
    else:
        b = torch.full((n,), band, dtype=torch.long, device=device)
    (l0, h0), (l1, h1), (l2, h2) = (cfg.bands_m[k] for k in BANDS)
    lo = torch.where(b == 0, l0, torch.where(b == 1, l1, l2))
    hi = torch.where(b == 0, h0, torch.where(b == 1, h1, h2))
    side = lo + (hi - lo) * torch.rand(n, generator=gen, device=device)
    f0, f1 = cfg.zone_radius_frac
    radius = side * (f0 + (f1 - f0) * torch.rand(n, generator=gen, device=device))
    half = side / 2
    reach = (half - radius - cfg.zone_wall_margin_m).clamp(min=0.0)
    centre = (torch.rand(n, 2, generator=gen, device=device) * 2 - 1) * reach[:, None]
    return Arenas(side, half, centre, radius, b)


def draw_starts(cfg: GameCfg, ar: Arenas, guards: int, strikes: int, gen: torch.Generator,
                return_miss: bool = False) -> Tensor | tuple[Tensor, Tensor]:
    """Starting positions [N, M, 3], M = guards + strikes, Guard drones first, z = start_height_m.

    ``rings``: Strike drones on the square inset ``strike_inset_m`` from the walls; Guard drones evenly on a
    circle of radius zone_radius + guard_ring_gap_m round the zone (one random phase per game), clamped inside
    the walls. ``anywhere``: uniform in the arena, Strike drones outside the zone. Each drone takes the first
    of 8 candidates that keeps ``spacing_m`` from its placed team-mates (and, for Strike, stays outside the
    zone) and the larger keep-out from every placed opposite-team drone (Guard drones are placed first, so
    only Strike drones check it). The Guard ring radius is at least spacing / (2 sin(pi / G)) so that team-mates
    can be spacing apart. If no candidate fits (arena too small), candidate 0 is used (a Strike drone inside the
    zone is pushed out along the radius): that game is a miss. With ``return_miss`` returns (starts, miss [N] bool).
    ``zone_disc_ring``: see ``_zone_disc_ring_starts``."""
    mode = cfg.starts.mode
    if mode not in START_MODES:
        raise ValueError(f"starts.mode must be one of {START_MODES}, got {mode!r}")
    if mode == "zone_disc_ring":
        starts, miss = _zone_disc_ring_starts(cfg, ar, guards, strikes, gen)
        return (starts, miss) if return_miss else starts
    st = cfg.starts
    n, m, k = ar.half_m.shape[0], guards + strikes, N_CANDIDATES
    dev = ar.half_m.device
    half = ar.half_m[:, None]                                    # [N, 1]
    lim = (half - cfg.arena.wall_margin_m)[:, :, None]           # [N, 1, 1]
    centre = ar.zone_centre_m[:, None, :]                        # [N, 1, 2]
    phase0 = torch.rand(n, 1, generator=gen, device=dev) * (2 * math.pi)
    placed = torch.zeros(n, m, 2, device=dev)
    miss = torch.zeros(n, dtype=torch.bool, device=dev)
    keepout = max(cfg.rules.keepout_guard_m, cfg.rules.keepout_strike_m)
    ring_min = st.spacing_m / (2 * math.sin(math.pi / guards)) if guards > 1 else 0.0
    for i in range(m):                                           # fixed small drone count
        is_strike = i >= guards
        if mode == "anywhere":
            cand = (torch.rand(n, k, 2, generator=gen, device=dev) * 2 - 1) * lim
        elif is_strike:
            h = (half - st.strike_inset_m)                       # [N, 1]
            t = torch.rand(n, k, generator=gen, device=dev) * 4
            side = t.floor().clamp(max=3.0)
            u = (t - side) * 2 - 1
            x = torch.where(side == 0, -h, torch.where(side == 1, h, u * h))
            y = torch.where(side == 2, -h, torch.where(side == 3, h, u * h))
            cand = torch.stack((x, y), dim=-1)
        else:
            step = 2 * math.pi / guards
            jit = (torch.rand(n, k, generator=gen, device=dev) - 0.5) * step
            jit = torch.cat((torch.zeros(n, 1, device=dev), jit[:, 1:]), dim=1)   # candidate 0 = exact ring
            ang = phase0 + step * i + jit
            rr = (ar.zone_radius_m + st.guard_ring_gap_m).clamp(min=ring_min)[:, None]
            cand = centre + rr[:, :, None] * torch.stack((ang.cos(), ang.sin()), dim=-1)
        cand = torch.maximum(torch.minimum(cand, lim), -lim)
        valid = torch.ones(n, k, dtype=torch.bool, device=dev)
        for j in range(m):                                       # placed team-mates only
            if j < i and (j >= guards) == is_strike:
                valid = valid & ((cand - placed[:, j:j + 1]).norm(dim=-1) >= st.spacing_m)
        if is_strike:
            valid = valid & ((cand - centre).norm(dim=-1) > ar.zone_radius_m[:, None])
            for j in range(guards):                              # opposite team: keep-out distance
                valid = valid & ((cand - placed[:, j:j + 1]).norm(dim=-1) >= keepout)
        has = valid.any(dim=-1)
        idx = valid.to(torch.uint8).argmax(dim=-1)               # first valid, else 0
        pick = cand.gather(1, idx[:, None, None].expand(n, 1, 2))[:, 0]
        if is_strike:                                            # a fallback must not start inside the zone
            off = pick - ar.zone_centre_m
            dist = off.norm(dim=-1, keepdim=True)
            unit = torch.where(dist > 1e-6, off / dist.clamp(min=1e-6), torch.cat((torch.ones_like(dist), torch.zeros_like(dist)), dim=-1))
            out = ar.zone_centre_m + unit * (ar.zone_radius_m[:, None] + 0.05)
            out = torch.maximum(torch.minimum(out, lim[:, 0]), -lim[:, 0])
            pick = torch.where((dist[:, 0] <= ar.zone_radius_m)[:, None], out, pick)
        placed[:, i] = pick
        miss = miss | ~has
    z = torch.full((n, m, 1), cfg.arena.start_height_m, device=dev)
    starts = torch.cat((placed, z), dim=-1)
    return (starts, miss) if return_miss else starts


def _zone_disc_ring_starts(cfg: GameCfg, ar: Arenas, guards: int, strikes: int, gen: torch.Generator
                           ) -> tuple[Tensor, Tensor]:
    """Mode ``zone_disc_ring`` (STE task L0.10; the hangar game's starts, sheet rows ``starts.guard_disc_m`` and
    ``starts.strike_ring_m``): starts [N, M, 3], miss [N] bool. Guard drones uniform in radius in [0, guard_disc_m] round
    the zone centre, Strike drones at strike_ring_m from it; every bearing uniform in [0, 2 pi), drawn per drone. Draw
    order: Guard radii [N, G], Guard bearings [N, G], Strike bearings [N, S]. No spacing is drawn for between team-mates
    (as in the hangar game: team-mates may start closer than the filter distance). Positions are clamped into the keep-in
    box (a no-op when the ring fits, as the lab ring does); z = start_height_m. A game is a miss if an opposite pair starts
    closer than the larger keep-out (never when ring - disc exceeds it) or a Strike drone starts inside the zone."""
    st = cfg.starts
    n, dev = ar.half_m.shape[0], ar.half_m.device
    lim = (ar.half_m - cfg.arena.wall_margin_m)[:, None, None]                      # [N, 1, 1]
    centre = ar.zone_centre_m[:, None, :]                                           # [N, 1, 2]
    g_rho = torch.rand(n, guards, generator=gen, device=dev) * st.guard_disc_m
    g_ang = torch.rand(n, guards, generator=gen, device=dev) * (2 * math.pi)
    s_ang = torch.rand(n, strikes, generator=gen, device=dev) * (2 * math.pi)
    rho = torch.cat((g_rho, torch.full((n, strikes), st.strike_ring_m, device=dev)), dim=1)     # [N, M]
    ang = torch.cat((g_ang, s_ang), dim=1)
    xy = centre + rho[..., None] * torch.stack((ang.cos(), ang.sin()), dim=-1)
    xy = torch.maximum(torch.minimum(xy, lim), -lim)
    keepout = max(cfg.rules.keepout_guard_m, cfg.rules.keepout_strike_m)
    cross = (xy[:, :guards, None, :] - xy[:, None, guards:, :]).norm(dim=-1)       # [N, G, S]
    inside = (xy[:, guards:] - centre).norm(dim=-1) <= ar.zone_radius_m[:, None]   # [N, S]
    miss = (cross < keepout).any(dim=(1, 2)) | inside.any(dim=1)
    z = torch.full((n, guards + strikes, 1), cfg.arena.start_height_m, device=dev)
    return torch.cat((xy, z), dim=-1), miss
