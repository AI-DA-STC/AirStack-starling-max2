"""S2 team rewards: terminal win/loss plus an optional shaping term on the Strike team's distance to the zone."""
from __future__ import annotations

import torch
from torch import Tensor

from .game_config import RewardsCfg

RUNNING, STRIKE_WIN, GUARD_WIN = 0, 1, 2


def team_rewards(cfg: RewardsCfg, outcome: Tensor, phi_prev: Tensor, phi_now: Tensor,
                 guards: int, strikes: int) -> dict[str, Tensor]:
    """outcome [N] int8 (of the games that ended this step, else 0); phi_prev, phi_now [N] (potential:
    nearest live Strike drone's distance to the zone edge over the arena half-side). Returns
    {"guard": [N, G], "strike": [N, S]}: Guard = win * (+1 on GUARD_WIN, -1 on STRIKE_WIN)
    + shaping_weight * (phi_now - phi_prev); the Strike reward is its negative. Every drone of a team gets
    the team's value."""
    terminal = cfg.win * ((outcome == GUARD_WIN).float() - (outcome == STRIKE_WIN).float())
    r = terminal + cfg.shaping_weight * (phi_now - phi_prev)
    return {"guard": r[:, None].expand(-1, guards).contiguous(),
            "strike": (-r)[:, None].expand(-1, strikes).contiguous()}
