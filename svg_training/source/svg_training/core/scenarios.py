"""Named fixed scenarios for scoring and tests (never for training: the adapters refuse them)."""
from __future__ import annotations

from dataclasses import dataclass

import torch

from .arena import Arenas, band_index_of_side
from .game_config import ArenaCfg


@dataclass(frozen=True)
class Scenario:
    name: str
    side_m: float
    zone_centre_m: tuple[float, float]
    zone_radius_m: float
    start_m: tuple[tuple[float, float], ...]   # (x, y) per drone, Guard drones first


def scenario_arenas(cfg: ArenaCfg, sc: Scenario, n: int, device) -> Arenas:
    """n identical arenas for a scenario. Shapes as Arenas."""
    side = torch.full((n,), sc.side_m, device=device)
    return Arenas(side, side / 2, torch.tensor(sc.zone_centre_m, device=device).expand(n, 2).contiguous(),
                  torch.full((n,), sc.zone_radius_m, device=device),
                  torch.full((n,), band_index_of_side(cfg, sc.side_m), dtype=torch.long, device=device))


SCENARIOS: dict[str, Scenario] = {
    "lab4_open": Scenario("lab4_open", 4.0, (0.0, 0.0), 0.6, ((1.5, 1.5), (-1.51, 0.0))),
    "lab4_block": Scenario("lab4_block", 4.0, (0.0, 0.0), 0.6, ((-0.3, 0.0), (-1.70, 0.0))),
    "large16_open": Scenario("large16_open", 16.0, (0.0, 0.0), 2.4, ((7.5, 7.5), (-7.51, 0.0))),
    "large16_block": Scenario("large16_block", 16.0, (0.0, 0.0), 2.4, ((-2.0, 0.0), (-7.51, 0.0))),
}
