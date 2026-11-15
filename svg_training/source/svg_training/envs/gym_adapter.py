"""Single-team Gymnasium vector adapter for the S2 game (S2 Task 9).

One ``SvgGame`` of N games becomes a ``gymnasium.vector.VectorEnv`` with ``num_envs = N``: the trained team is
the "agent" (all its drones at once: observation = their observations side by side, action = their actions side
by side); the other team is played by a fixed ``Strategy`` (the opponent) inside the adapter. Built only on the
game's public interface and the strategy contract; the core imports no training library, this file does.

Conventions: tensors stay on the game's device (as Isaac Lab's vector environments do), they are not NumPy
arrays. Autoreset is SAME_STEP: the game starts a new game where one ended inside ``step``, so the observation
returned on a game's last step is already the new game's. Every end is terminal (reach the zone, the other team
gone, or the time-out, which the observation's time-left shows), so ``truncations`` is always False and nothing
needs the ended game's last observation; ``info`` therefore carries no "final_obs".

Training on the fixed named scenarios is refused (STANDARDS §6 rule 4)."""
from __future__ import annotations

from typing import Any

import gymnasium
import numpy as np
import torch
from gymnasium.vector import AutoresetMode, VectorEnv
from gymnasium.vector.utils import batch_space
from torch import Tensor

from svg_training.core.game import SvgGame
from svg_training.core.observations import OBS_DIM
from svg_training.core.strategy import Strategy


def refuse_scenario(game: SvgGame) -> None:
    """Raise ValueError if the game plays a fixed named scenario (those are for scoring and tests only)."""
    if game.scenario is not None:
        raise ValueError(f"training on the fixed scenario {game.scenario.name!r} is refused (STANDARDS §6 rule 4): "
                         "build the game without scenario= so arenas and starts are random")


class SvgTeamVectorEnv(VectorEnv):
    """``team`` ("guard" or "strike") of ``game`` as a Gymnasium vector env; ``opponent`` plays the other team.

    Shapes (M_team = the team's drone count, N = game.num_games): observation [N, M_team * OBS_DIM] (drone 0's 69
    floats, then drone 1's, ...); action [N, M_team * 4] in [-1, 1] (drone k's vx, vy, vz, yaw rate at
    4k..4k+3); reward [N] = the team's mean drone reward; terminations [N] bool; truncations [N] bool (False).
    info (reset and step): "opponent" = the opponent's name (the opponent mix; a ``SplitStrategy`` names every
    part). info (step): also "outcome" [N] int8 (0 running, 1 Strike team reached the zone, 2 Guard team held),
    "end_step" [N], and the game's own info (StepOut.info: closest approach, rule breach, band, ...)."""

    metadata = {"autoreset_mode": AutoresetMode.SAME_STEP}

    def __init__(self, game: SvgGame, team: str, opponent: Strategy):
        refuse_scenario(game)
        if team not in ("guard", "strike"):
            raise ValueError(f"team must be 'guard' or 'strike', got {team!r}")
        other = "strike" if team == "guard" else "guard"
        if opponent.team != other:
            raise ValueError(f"opponent {opponent.name!r} plays {opponent.team!r}; the {team} team's opponent "
                             f"must play {other!r}")
        self.game, self.team, self.other, self.opponent = game, team, other, opponent
        self.m_team = game.guards if team == "guard" else game.strikes
        self.num_envs = game.num_games
        self.device = game.device
        self.single_observation_space = gymnasium.spaces.Box(-np.inf, np.inf, (self.m_team * OBS_DIM,), np.float32)
        self.single_action_space = gymnasium.spaces.Box(-1.0, 1.0, (self.m_team * 4,), np.float32)
        self.observation_space = batch_space(self.single_observation_space, self.num_envs)
        self.action_space = batch_space(self.single_action_space, self.num_envs)
        self._game_obs: dict[str, Tensor] = {}

    def _flat(self, obs: dict[str, Tensor]) -> Tensor:
        """{team: [N, M_team, OBS_DIM]} -> [N, M_team * OBS_DIM] for the trained team."""
        return obs[self.team].reshape(self.num_envs, -1)

    def reset(self, *, seed: int | None = None, options: dict | None = None) -> tuple[Tensor, dict]:
        """Start every game afresh (reseeding the game's generator if ``seed`` is given; the opponent's own
        random stream is not reseeded). ``options`` is not used. Returns (obs [N, M_team * OBS_DIM], info)."""
        super().reset(seed=seed)
        with torch.no_grad():
            self._game_obs = self.game.reset(seed=seed)
        self.opponent.reset(torch.ones(self.num_envs, dtype=torch.bool, device=self.device))
        return self._flat(self._game_obs), {"opponent": self.opponent.name}

    def step(self, actions: Tensor) -> tuple[Tensor, Tensor, Tensor, Tensor, dict[str, Any]]:
        """actions [N, M_team * 4] (a tensor, or anything ``torch.as_tensor`` takes) -> (obs, reward [N],
        terminations [N], truncations [N], info). See the class docstring."""
        a = torch.as_tensor(actions, dtype=torch.float32, device=self.device).reshape(self.num_envs, self.m_team, 4)
        with torch.no_grad():
            act = {self.team: a.clamp(-1.0, 1.0), self.other: self.opponent.act(self._game_obs[self.other])}
            out = self.game.step(act)
            self.opponent.reset(out.done)
        self._game_obs = out.obs
        reward = out.reward[self.team].mean(dim=1)                        # [N]: every drone gets the team's value
        info = {**out.info, "outcome": out.outcome, "end_step": out.end_step, "opponent": self.opponent.name}
        return self._flat(out.obs), reward, out.done, torch.zeros_like(out.done), info

    def render(self) -> None:
        """No viewer: the game is headless."""
        return None

    def close_extras(self, **kwargs: Any) -> None:
        """Nothing to release."""
        return None
