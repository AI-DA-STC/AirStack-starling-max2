"""Standalone batched PyTorch replica of the partner's 2-D area-denial game, in the partner's units.

Rules (all constants come from :class:`svg_training.nus.rules.NusRules`; this file holds no partner value):

* each drone asks for a displacement, capped per team (disc cap, vector scaled down);
* one pass of soft cross-team push at the tentative positions: the push on drone i from an opponent j has a magnitude
  gain * smooth * softplus((push radius of j's team - distance) / smooth), where the push radius of a team is twice the
  body radius plus that team's safety distance, directed from j to i (from the current positions if the tentative ones
  coincide); same-team overlap is allowed;
* the Guard team only gets a soft circular boundary pushed inward, evaluated at the tentative position;
* the executed displacement (choice plus corrections) is capped; positions update; the previous positions are kept;
* the reached flag latches when any Strike drone ends a step inside the zone; the episode has a fixed length.

State shapes: positions ``(N, M, 2)`` for N games and M = guard_count + strike_count drones, Guard drones first.
Everything is a batched tensor operation: no loop over games, no ``.cpu()``, no NumPy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import torch

from .rules import NusRules

PHI_WIDTH = 2 + 1  # unit direction (x, y) and magnitude
FEATURES_PER_ACTOR = PHI_WIDTH * PHI_WIDTH  # three phi blocks per actor


@dataclass
class ReplicaState:
    """Batched state. ``pos``, ``prev_pos``: (N, M, 2); ``reached``: (N,) float 0/1; ``step``: (N,) int64."""

    pos: torch.Tensor
    prev_pos: torch.Tensor
    reached: torch.Tensor
    step: torch.Tensor


def _unit_with_floor(vectors: torch.Tensor, floor: float) -> tuple[torch.Tensor, torch.Tensor]:
    """Return (unit direction or zero below the floor, magnitude); shapes (..., 2) and (..., 1)."""
    magnitude = torch.linalg.norm(vectors, dim=-1, keepdim=True)
    direction = torch.where(magnitude > floor, vectors / magnitude.clamp_min(floor), torch.zeros_like(vectors))
    return direction, magnitude


class NusReplica:
    """The partner's game as batched tensor operations. Units are the partner's (length units, steps)."""

    def __init__(self, rules: NusRules, device: torch.device | str = "cpu", dtype: torch.dtype = torch.float32):
        self.rules = rules
        self.device = torch.device(device)
        self.dtype = dtype
        self.guard_count = rules.guard_count
        self.strike_count = rules.strike_count
        self.num_actors = self.guard_count + self.strike_count
        count = self.num_actors
        is_guard = torch.arange(count, device=self.device) < self.guard_count
        self.is_guard = is_guard
        self.speed_limit = torch.where(
            is_guard, torch.tensor(rules.guard_max_speed, dtype=dtype, device=self.device),
            torch.tensor(rules.strike_max_speed, dtype=dtype, device=self.device),
        )[:, None]
        safety = torch.where(
            is_guard, torch.tensor(rules.guard_safety_distance, dtype=dtype, device=self.device),
            torch.tensor(rules.strike_safety_distance, dtype=dtype, device=self.device),
        )
        # push radius around drone j (column index), used when an opponent i is pushed away from j
        self.push_radius = 2 * rules.agent_size + safety
        self.cross_team = is_guard[:, None] != is_guard[None, :]
        self.obs_order = self._obs_order()
        self.obs_dim = FEATURES_PER_ACTOR * count + 2

    def _obs_order(self) -> torch.Tensor:
        """(M, M) index table: self, teammates cyclically from self+1, then opponents in index order."""
        rows = []
        for actor in range(self.num_actors):
            guard = actor < self.guard_count
            team_start = 0 if guard else self.guard_count
            team_size = self.guard_count if guard else self.strike_count
            opponent_start = self.guard_count if guard else 0
            opponent_size = self.strike_count if guard else self.guard_count
            offset = actor - team_start
            mates = [team_start + (offset + 1 + k) % team_size for k in range(team_size - 1)]
            rows.append([actor, *mates, *range(opponent_start, opponent_start + opponent_size)])
        return torch.tensor(rows, dtype=torch.long, device=self.device)

    # ------------------------------------------------------------------ starts
    def reset(self, n_games: int, generator: torch.Generator | None = None, random_start: bool | None = None) -> ReplicaState:
        """Fresh games. Random start: Guards uniform in radius inside a disc around the zone centre, Strikes on the ring at
        the start distance with independent bearings. Fixed layout: Guards on a ring, Strikes on a small ring around a
        point on the +x axis. ``random_start`` overrides the rules' start mode."""
        r = self.rules
        use_random = r.random_start if random_start is None else random_start
        kw = {"device": self.device, "dtype": self.dtype}
        if use_random:
            guard_radius = torch.rand(n_games, self.guard_count, 1, generator=generator, **kw) * (r.start_guard_disc_fraction * r.area_radius)
            guard_angle = torch.rand(n_games, self.guard_count, 1, generator=generator, **kw) * (2 * math.pi)
            guards = guard_radius * torch.cat((guard_angle.cos(), guard_angle.sin()), dim=-1)
            strike_angle = torch.rand(n_games, self.strike_count, 1, generator=generator, **kw) * (2 * math.pi)
            strikes = r.spawn_distance * torch.cat((strike_angle.cos(), strike_angle.sin()), dim=-1)
        else:
            guard_angle = (2 * math.pi) * torch.arange(self.guard_count, **kw)[:, None] / self.guard_count
            strike_angle = (2 * math.pi) * torch.arange(self.strike_count, **kw)[:, None] / self.strike_count
            guards = (r.start_static_guard_ring_fraction * r.area_radius) * torch.cat((guard_angle.cos(), guard_angle.sin()), dim=-1)
            centre = torch.tensor((r.spawn_distance, 0), **kw)
            strikes = centre + (r.start_static_strike_cluster_fraction * r.spawn_cluster_radius) * torch.cat(
                (strike_angle.cos(), strike_angle.sin()), dim=-1)
            guards = guards.expand(n_games, -1, -1)
            strikes = strikes.expand(n_games, -1, -1)
        pos = torch.cat((guards, strikes), dim=1).contiguous()
        return ReplicaState(
            pos=pos, prev_pos=pos.clone(),
            reached=torch.zeros(n_games, **kw), step=torch.zeros(n_games, dtype=torch.long, device=self.device),
        )

    # ------------------------------------------------------------------ rules
    def _cap(self, vectors: torch.Tensor, limit: torch.Tensor | float) -> torch.Tensor:
        norms = torch.linalg.norm(vectors, dim=-1, keepdim=True)
        scale = torch.clamp(limit / norms.clamp_min(self.rules.norm_floor), max=1)
        return vectors * scale

    def intended(self, actions: torch.Tensor) -> torch.Tensor:
        """(N, M, 2) requested displacement capped by each team's speed limit."""
        return self._cap(actions.to(self.dtype), self.speed_limit)

    def corrections(self, state: ReplicaState, intended: torch.Tensor) -> torch.Tensor:
        """(N, M, 2) simultaneous cross-team push and Guard boundary push at the tentative positions."""
        r = self.rules
        floor = r.norm_floor
        tentative = state.pos + intended
        offset = tentative[:, :, None, :] - tentative[:, None, :, :]  # (N, i, j, 2): from j to i
        distance = torch.linalg.norm(offset, dim=-1, keepdim=True)
        fallback = state.pos[:, :, None, :] - state.pos[:, None, :, :]
        fallback_distance = torch.linalg.norm(fallback, dim=-1, keepdim=True)
        fallback_dir = torch.where(fallback_distance > floor, fallback / fallback_distance.clamp_min(floor), torch.zeros_like(fallback))
        direction = torch.where(distance > floor, offset / distance.clamp_min(floor), fallback_dir)
        margin = r.push_smoothing_margin
        zeros = torch.zeros_like(distance)
        penetration = margin * torch.logaddexp((self.push_radius[None, None, :, None] - distance) / margin, zeros)
        pair = (r.push_gain * penetration * direction * self.cross_team[None, :, :, None]).sum(dim=2)

        radial_dir, radial = _unit_with_floor(tentative, floor)
        trigger = r.guard_boundary_radius - r.boundary_margin
        boundary_pen = margin * torch.logaddexp((radial - trigger) / margin, torch.zeros_like(radial))
        boundary = r.push_gain * boundary_pen * (-radial_dir)
        boundary = torch.where(self.is_guard[None, :, None], boundary, torch.zeros_like(boundary))
        return pair + boundary

    def executed(self, state: ReplicaState, actions: torch.Tensor) -> torch.Tensor:
        """(N, M, 2) displacement actually applied."""
        intended = self.intended(actions)
        return self._cap(intended + self.corrections(state, intended), self.rules.total_displacement_cap)

    def inside_zone(self, pos: torch.Tensor) -> torch.Tensor:
        return torch.linalg.norm(pos, dim=-1) <= self.rules.area_radius

    def step(self, state: ReplicaState, actions: torch.Tensor) -> ReplicaState:
        """One step for all games. ``actions`` (N, M, 2). Does not reset; ``done`` says when the episode is over."""
        displacement = self.executed(state, actions)
        new_pos = state.pos + displacement
        strike_inside = self.inside_zone(new_pos[:, self.guard_count:]).any(dim=1)
        return ReplicaState(
            pos=new_pos, prev_pos=state.pos,
            reached=torch.maximum(state.reached, strike_inside.to(self.dtype)), step=state.step + 1,
        )

    def done(self, state: ReplicaState) -> torch.Tensor:
        """(N,) True once the fixed episode length is reached."""
        return state.step >= self.rules.episode_steps

    # ------------------------------------------------------------ observation
    def observe(self, state: ReplicaState) -> torch.Tensor:
        """(N, M, 9M + 2): per drone, its own then teammates' (cyclic from self+1) then opponents' features, each
        [unit direction, magnitude] of (position, previous position, last displacement) relative to the zone centre
        (the last one relative to the previous position), then the zone radius and the reached flag."""
        floor = self.rules.obs_direction_floor

        def phi(vectors: torch.Tensor) -> torch.Tensor:
            direction, magnitude = _unit_with_floor(vectors, floor)
            return torch.cat((direction, magnitude), dim=-1)

        features = torch.cat((phi(state.pos), phi(state.prev_pos), phi(state.pos - state.prev_pos)), dim=-1)  # (N, M, 9)
        gathered = features[:, self.obs_order]  # (N, M, M, 9)
        flat = gathered.reshape(features.shape[0], self.num_actors, -1)
        tail = torch.stack((torch.full_like(state.reached, self.rules.area_radius), state.reached), dim=-1)
        return torch.cat((flat, tail[:, None, :].expand(-1, self.num_actors, -1)), dim=-1)
