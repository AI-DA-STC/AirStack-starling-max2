"""PLACEHOLDER drone response to a bare velocity command (STANDARDS §5 values, not a fit).

A whole-step delay followed by a first-order lag. The fitted model replaces this class in S1.
"""
import math

import torch
from torch import Tensor


class PlaceholderResponse:
    """Velocity response for N games of M drones: cmd_mps [N, M, 3] -> velocity [N, M, 3]."""

    def __init__(self, n_games: int, n_drones: int, dt_s: float = 0.05, delay_s: float = 0.15,
                 lag_s: float = 0.55, speed_cap_mps=4.0, device="cuda"):
        self.dt_s = dt_s
        self.delay_steps = round(delay_s / dt_s)
        self.alpha = 1.0 - math.exp(-dt_s / lag_s)
        # float, or a tensor broadcastable to [N, M, 1] (a per-drone cap on the command norm)
        self.speed_cap_mps = speed_cap_mps.to(device) if isinstance(speed_cap_mps, Tensor) else speed_cap_mps
        self.vel_mps = torch.zeros(n_games, n_drones, 3, device=device)
        # ring buffer of the last `delay_steps` commands, oldest at slot self._head
        self._buf = torch.zeros(self.delay_steps, n_games, n_drones, 3, device=device)
        self._head = 0

    def step(self, cmd_mps: Tensor) -> Tensor:
        """Advance one step with commands [N, M, 3]; returns the velocity [N, M, 3]."""
        norm = cmd_mps.norm(dim=-1, keepdim=True)
        cmd = cmd_mps * (self.speed_cap_mps / norm.clamp(min=1e-9)).clamp(max=1.0)
        if self.delay_steps > 0:
            delayed = self._buf[self._head].clone()
            self._buf[self._head] = cmd
            self._head = (self._head + 1) % self.delay_steps
        else:
            delayed = cmd
        self.vel_mps = self.vel_mps + self.alpha * (delayed - self.vel_mps)
        return self.vel_mps

    def reset(self, mask: Tensor) -> None:
        """Zero the velocity and the pending commands of the drones where mask [N, M] bool is True."""
        keep = (~mask)[..., None].to(self.vel_mps.dtype)
        self.vel_mps = self.vel_mps * keep
        self._buf = self._buf * keep[None]
