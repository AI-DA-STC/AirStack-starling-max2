"""Pair rules between the two teams: partner push-apart and side-quest contact tags (S2 Task 3).

All batched tensor operations: no loop over games, no host reads. Only fixed pass counts loop.
Teammates never interact here. Distances are planar (x, y) for push-apart and 3-D for contact tags."""
from __future__ import annotations

import torch
from torch import Tensor

_EPS = 1.0e-9


def _unit(rel: Tensor, dist: Tensor) -> Tensor:
    """[..., 2] unit vector rel / dist; (1, 0) where the two points coincide."""
    safe = rel / dist.clamp(min=_EPS)[..., None]
    fallback = torch.zeros_like(rel)
    fallback[..., 0] = 1.0
    return torch.where((dist > _EPS)[..., None], safe, fallback)


def _repair(p: Tensor, pair: Tensor, keep_min_m: float) -> Tensor:
    """One Jacobi repair pass: both drones of every live opposite pair closer than keep_min_m move apart
    equally along their line, so each pair ends exactly keep_min_m apart (if only that pair acts). [N, M, 2]."""
    rel = p[:, :, None, :] - p[:, None, :, :]                     # [N, M, M, 2] i relative to j
    dist = rel.norm(dim=-1)
    viol = pair & (dist < keep_min_m)
    shift = 0.5 * (keep_min_m - dist) * viol
    return p + (shift[..., None] * _unit(rel, dist)).sum(dim=2)


def push_apart(prop_m: Tensor, prev_m: Tensor, is_strike: Tensor, alive: Tensor, keep_guard_m: float,
               keep_strike_m: float, rule: str = "block", passes: int = 3) -> Tensor:
    """Keep opposite teams apart. prop_m, prev_m [N, M, 2] proposed and start-of-step horizontal positions;
    is_strike [M] bool; alive [N, M] bool. Returns corrected proposed positions [N, M, 2].

    block: each live drone is pushed radially out of the disc of its OWN team's distance around every live
    opposite drone's start-of-step position (``passes`` Jacobi passes, pushes summed), then one repair pass moves
    both drones of any opposite pair still closer than min(keep_guard, keep_strike) apart equally.
    shove: only the equal-share repair, ``passes`` times. Drones that are out neither push nor are pushed."""
    if rule not in ("block", "shove"):
        raise ValueError(f"push rule must be 'block' or 'shove', got {rule!r}")
    keep_min = min(keep_guard_m, keep_strike_m)
    keep_own = is_strike.to(prop_m.dtype) * (keep_strike_m - keep_guard_m) + keep_guard_m                # [M]
    cross = is_strike[:, None] != is_strike[None, :]                                  # [M, M]
    pair = alive[:, :, None] & alive[:, None, :] & cross[None]                        # [N, M, M]
    p = prop_m
    if rule == "block":
        for _ in range(passes):
            rel = p[:, :, None, :] - prev_m[:, None, :, :]
            dist = rel.norm(dim=-1)
            inside = pair & (dist < keep_own[None, :, None])
            push = (keep_own[None, :, None] - dist) * inside
            p = p + (push[..., None] * _unit(rel, dist)).sum(dim=2)
        return _repair(p, pair, keep_min)
    for _ in range(passes):
        p = _repair(p, pair, keep_min)
    return p


def contact_tags(pos_m: Tensor, alive: Tensor, guards: int, contact_m: float, guard_survives: Tensor
                 ) -> tuple[Tensor, Tensor]:
    """Contact tags. pos_m [N, M, 3] (Guard drones first, then Strike), alive [N, M], guard_survives [N] bool.
    A live Guard-Strike pair closer than contact_m (3-D centres) tags both; the Strike drone leaves; the Guard
    drone leaves unless guard_survives. Returns (tagged [N, M] bool, alive_after [N, M] bool)."""
    g_pos, s_pos = pos_m[:, :guards], pos_m[:, guards:]
    dist = (g_pos[:, :, None, :] - s_pos[:, None, :, :]).norm(dim=-1)               # [N, G, S]
    hit = alive[:, :guards, None] & alive[:, None, guards:] & (dist < contact_m)
    tagged = torch.cat((hit.any(dim=2), hit.any(dim=1)), dim=1)                      # [N, M]
    leaves = torch.cat((tagged[:, :guards] & ~guard_survives[:, None], tagged[:, guards:]), dim=1)
    return tagged, alive & ~leaves
