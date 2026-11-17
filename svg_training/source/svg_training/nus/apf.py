"""The partner's scripted controllers (APF), batched, in the partner's units. Every constant comes from the local rules and
deploy files; this file holds no partner value.

* **Strike controller**: attraction to the zone centre (unit direction times a gain) plus repulsion from every Guard that is
  closer than the Guards' push radius (the radius is twice the body radius plus the Guard safety distance), capped at the
  Strike team's speed.
* **Guard controller**: run straight at the nearest Strike drone, capped at the Guard team's speed.

Lengths below the floor count as zero. Shapes: positions ``(N, M, 2)`` for N games and M = guard_count + strike_count drones,
Guard drones first; actions ``(N, team size, 2)``. Everything is a batched tensor operation.
"""
from __future__ import annotations

import torch

from .deploy import NusDeploy
from .rules import NusRules


class NusApf:
    """The partner's two scripted controllers on batched positions."""

    def __init__(self, rules: NusRules, deploy: NusDeploy):
        self.rules, self.deploy = rules, deploy
        self.guard_count, self.strike_count = rules.guard_count, rules.strike_count
        self.repulsion_radius = 2 * rules.agent_size + rules.guard_safety_distance

    def _cap(self, vectors: torch.Tensor, limit: float) -> torch.Tensor:
        norms = torch.linalg.norm(vectors, dim=-1, keepdim=True)
        return vectors * torch.clamp(limit / norms.clamp_min(self.deploy.apf_floor), max=1)

    def strike_actions(self, pos: torch.Tensor) -> torch.Tensor:
        """pos (N, M, 2) -> requested displacement (N, strike_count, 2) of the Strike team."""
        floor = self.deploy.apf_floor
        guards, strikes = pos[:, : self.guard_count], pos[:, self.guard_count:]
        to_zone = -strikes
        zone_distance = torch.linalg.norm(to_zone, dim=-1, keepdim=True)
        attraction = self.deploy.apf_attraction_gain * torch.where(
            zone_distance > floor, to_zone / zone_distance.clamp_min(floor), torch.zeros_like(to_zone))
        away = strikes[:, :, None, :] - guards[:, None, :, :]  # (N, strike, guard, 2)
        distance = torch.linalg.norm(away, dim=-1, keepdim=True)
        direction = torch.where(distance > floor, away / distance.clamp_min(floor), torch.zeros_like(away))
        safe = distance.clamp_min(floor)
        strength = (1 / safe - 1 / self.repulsion_radius).clamp_min(0) / safe.square()
        repulsion = self.deploy.apf_repulsion_gain * (direction * strength).sum(dim=2)
        return self._cap(attraction + repulsion, self.rules.strike_max_speed)

    def guard_actions(self, pos: torch.Tensor) -> torch.Tensor:
        """pos (N, M, 2) -> requested displacement (N, guard_count, 2) of the Guard team."""
        guards, strikes = pos[:, : self.guard_count], pos[:, self.guard_count:]
        offsets = strikes[:, None, :, :] - guards[:, :, None, :]  # (N, guard, strike, 2)
        nearest = torch.linalg.norm(offsets, dim=-1).argmin(dim=-1)
        desired = torch.gather(offsets, 2, nearest[:, :, None, None].expand(-1, -1, 1, 2))[:, :, 0]
        return self._cap(desired, self.rules.guard_max_speed)

    def actions(self, team: str, pos: torch.Tensor) -> torch.Tensor:
        if team == "strike":
            return self.strike_actions(pos)
        if team == "guard":
            return self.guard_actions(pos)
        raise ValueError(f"team must be 'guard' or 'strike', got {team!r}")
