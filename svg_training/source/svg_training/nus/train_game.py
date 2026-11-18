"""The hangar game for TRAINING (Phase 5 Task P-T2, plan F9): ``NusHangarGame`` with fresh starts for every new game.

``NusHangarGame._draw_starts`` returns the same paired starts at every reset (right for scoring, wrong for training: STANDARDS section 6.4).
Here every new game draws its starts with the replica's own start rule (``NusReplica.reset(random_start=True)``: Guard drones uniform in
radius inside the start disc, Strike drones on the start ring, independent bearings), scaled to metres, at the flying height plus a fresh
start-height jitter on ``free_jitter`` rows, from a ``torch.Generator`` on the game's device seeded with the run seed. The Phase 4 starts
seed is refused, so training never draws the scoring starts. Everything is one batched draw for all games (no loop over games, no host
read); recording (the per-tick extra metrics and video slots of the scoring game) is off unless asked for. No numeric literal (G2).
"""
from __future__ import annotations

import torch
from torch import Tensor

from ..core.arena import Arenas
from ..core.game import SvgGame
from ..core.game_config import GameCfg
from .hangar import Geometry, load_phase4
from .hangar_game import NusHangarGame
from .replica import NusReplica
from .rules import NusRules


def draw_train_starts(replica: NusReplica, n: int, gen: torch.Generator, scale_m_per_unit: float, height_m: float, jitter_m: float) -> Tensor:
    """[n, M, 3] start positions in metres (zone centre at the origin, Guard drones first): the replica's random start rule in partner
    units times ``scale_m_per_unit``, at ``height_m`` plus a uniform jitter in [-jitter_m, jitter_m] per drone and game."""
    units = replica.reset(n, generator=gen, random_start=True).pos
    jitter = (torch.rand(units.shape[:-1], generator=gen, device=units.device, dtype=units.dtype) * 2 - 1) * jitter_m
    return torch.cat((units * scale_m_per_unit, (height_m + jitter)[..., None]), dim=-1)


class NusHangarTrainGame(NusHangarGame):
    """The Phase 4 row's hangar game with fresh starts per game. ``row``: a ``configs/nus_phase4.toml`` row with ``engine = "game"``;
    ``jitter_m``: the start-height jitter (used on ``free_jitter`` rows only); ``record``: keep the scoring game's per-tick extra metrics
    (default off; ``video_slots`` > 0 turns it on)."""

    def __init__(self, cfg: GameCfg, geo: Geometry, row: dict, rules: NusRules, guards: int, strikes: int, num_games: int,
                 device: str = "cpu", seed: int = 0, jitter_m: float = 0.0, parked: bool = False, video_slots: int = 0,
                 record: bool = False):
        if seed == load_phase4()["ladder"]["seed"]:
            raise ValueError("refusing the Phase 4 starts seed for a training game: training never draws the scoring starts")
        m = guards + strikes
        self._replica = NusReplica(rules, device=device)
        self._start_gen = torch.Generator(device=device)
        self._start_gen.manual_seed(int(seed))
        self._jitter_m = float(jitter_m) if row["height"] == "free_jitter" else 0.0
        self._record = bool(record) or video_slots > 0
        placeholder = torch.zeros(num_games, m, 2, device=device)   # the parent's paired starts (x, y), unused here
        super().__init__(cfg, geo, row, placeholder, torch.zeros(num_games, m, device=device), guards, strikes, device=device, seed=seed,
                         parked=parked, video_slots=video_slots, rules=rules)

    def _draw_starts(self, arenas: Arenas) -> tuple[Tensor, Tensor]:
        pos = draw_train_starts(self._replica, self.num_games, self._start_gen, self.geo.scale_m_per_unit, self.geo.height_m, self._jitter_m)
        if self._parked:
            pos[:, 0, :2] = 0
        dist = (pos[:, :, None, :] - pos[:, None, :, :]).norm(dim=-1)
        pair = ~torch.eye(self.M, dtype=torch.bool, device=self.device)[None]
        return pos, ((dist < self._filter_keepout_m) & pair).any(dim=(1, 2))

    def step(self, actions):
        """``SvgGame.step`` (recording off), or the scoring game's step with its extra metrics (recording on)."""
        if self._record:
            return super().step(actions)
        return SvgGame.step(self, actions)
