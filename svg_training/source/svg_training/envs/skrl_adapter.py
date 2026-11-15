"""skrl multi-agent adapter for the S2 game (S2 Task 9).

Wraps one ``SvgGame`` as a skrl ``MultiAgentEnvWrapper`` so skrl's multi-agent trainers (IPPO, MAPPO) can drive
it. One skrl agent name per drone of every trained team ("guard_0", ..., then "strike_0", ...); a team that is not
trained is played by a fixed ``Strategy`` (the opponent) inside the adapter. Built only on the game's public
interface and the strategy contract (core/strategy.py); the core imports no training library, this file does.

Conventions (as skrl's own Isaac Lab multi-agent wrapper): tensors stay on the game's device; per agent the
observation is [N, OBS_DIM], the reward, terminated and truncated [N, 1]. Every end of a game is terminal (a
reach of the zone, the other team gone or the time-out, which the observation's time-left shows), so truncated
is always False. The game resets finished games itself (same step): the observation returned on a game's last
step is already the new game's.

Training on the fixed named scenarios is refused (STANDARDS §6 rule 4): a game built with ``scenario=`` raises
``ValueError``."""
from __future__ import annotations

import math
from typing import Any

import gymnasium
import torch
from skrl.envs.wrappers.torch.base import MultiAgentEnvWrapper
from torch import Tensor

from svg_training.core.game import SvgGame
from svg_training.core.observations import OBS_DIM, STATE_DIM
from svg_training.core.strategy import Strategy

from .gym_adapter import refuse_scenario

TEAMS = ("guard", "strike")
_KWARGS_FIELDS = ("learning_rate_scheduler_kwargs", "observation_preprocessor_kwargs", "state_preprocessor_kwargs",
                  "value_preprocessor_kwargs")


def skrl_kwargs_defaults(possible_agents: list[str]) -> dict[str, dict[str, dict]]:
    """Per-agent empty dicts for the four ``*_kwargs`` fields of skrl's multi-agent configs (IPPO_CFG,
    MAPPO_CFG). skrl 2.1.0 rejects its own default (one empty dict: ``MultiAgentCfg.expand`` raises "Specified
    keys (set()) do not match possible agents"), so pass these: ``IPPO_CFG(**skrl_kwargs_defaults(names), ...)``.
    A value you set yourself for one of these fields must also be per agent."""
    return {f: {a: {} for a in possible_agents} for f in _KWARGS_FIELDS}


class SvgSkrlEnv(MultiAgentEnvWrapper):
    """skrl multi-agent view of ``game``: one agent name per drone of the trained teams.

    game: an ``SvgGame`` without a scenario. train_teams: the teams skrl controls ("guard", "strike" or both).
    opponents: {team: Strategy} for every team not trained (its ``team`` must match). info of reset and step
    carries "opponents" ({team: strategy name}: the opponent mix); step's info also carries the game's own info
    (StepOut.info) plus "outcome" [N] and "end_step" [N]."""

    def __init__(self, game: SvgGame, train_teams: tuple[str, ...] = ("guard",),
                 opponents: dict[str, Strategy] | None = None):
        refuse_scenario(game)
        train_teams = tuple(train_teams)
        opponents = dict(opponents or {})
        if not train_teams or any(t not in TEAMS for t in train_teams) or len(set(train_teams)) != len(train_teams):
            raise ValueError(f"train_teams must be distinct names from {TEAMS}, got {train_teams!r}")
        for team in TEAMS:
            if team in train_teams:
                if team in opponents:
                    raise ValueError(f"team {team!r} is trained; it cannot also have an opponent strategy")
            elif team not in opponents:
                raise ValueError(f"team {team!r} is not trained, so it needs an opponent strategy")
            elif opponents[team].team != team:
                raise ValueError(f"opponent {opponents[team].name!r} plays {opponents[team].team!r}, not {team!r}")
        super().__init__(game)
        self.game = game
        self.train_teams = tuple(t for t in TEAMS if t in train_teams)       # always Guard first
        self.opponents = opponents
        count = {"guard": game.guards, "strike": game.strikes}
        self._names = {t: [f"{t}_{i}" for i in range(count[t])] for t in self.train_teams}
        self._possible_agents = [a for t in self.train_teams for a in self._names[t]]
        obs_box = gymnasium.spaces.Box(-math.inf, math.inf, (OBS_DIM,), "float32")
        act_box = gymnasium.spaces.Box(-1.0, 1.0, (4,), "float32")
        self._state_box = gymnasium.spaces.Box(-math.inf, math.inf, (STATE_DIM,), "float32")
        self._obs_spaces = {a: obs_box for a in self._possible_agents}
        self._act_spaces = {a: act_box for a in self._possible_agents}
        self._obs: dict[str, Tensor] = {}

    # ---------------------------------------------------------------- names and spaces (skrl reads these)
    @property
    def possible_agents(self) -> list[str]:
        """Agent names: "guard_0", ..., then "strike_0", ... (trained teams only)."""
        return list(self._possible_agents)

    @property
    def agents(self) -> list[str]:
        """Every drone keeps its name for the whole run (a drone that is out gets a zero observation)."""
        return list(self._possible_agents)

    @property
    def num_agents(self) -> int:
        return len(self._possible_agents)

    @property
    def max_num_agents(self) -> int:
        return len(self._possible_agents)

    @property
    def observation_spaces(self) -> dict[str, gymnasium.spaces.Box]:
        """{agent: Box((OBS_DIM,))}."""
        return dict(self._obs_spaces)

    @property
    def action_spaces(self) -> dict[str, gymnasium.spaces.Box]:
        """{agent: Box(-1, 1, (4,))}: vx, vy, vz, yaw rate, scaled by the team's speed cap in the game."""
        return dict(self._act_spaces)

    @property
    def state_spaces(self) -> dict[str, gymnasium.spaces.Box]:
        """{agent: Box((STATE_DIM,))}: the one central state, the same for every agent (critics only)."""
        return {a: self._state_box for a in self._possible_agents}

    @property
    def central_state_space(self) -> gymnasium.spaces.Box:
        """Box((STATE_DIM,)). skrl's own spelling is ``state_space(agent)`` (a method), kept from the base."""
        return self._state_box

    # ---------------------------------------------------------------- helpers
    def _split(self, obs: dict[str, Tensor]) -> dict[str, Tensor]:
        """{"guard": [N, G, OBS_DIM], "strike": [N, S, OBS_DIM]} -> {agent: [N, OBS_DIM]} for trained teams."""
        return {name: obs[t][:, i] for t in self.train_teams for i, name in enumerate(self._names[t])}

    def _info(self) -> dict[str, Any]:
        return {"opponents": {t: s.name for t, s in self.opponents.items()}}

    # ---------------------------------------------------------------- skrl interface
    def reset(self) -> tuple[dict[str, Tensor], dict[str, Any]]:
        """Start every game afresh. Returns ({agent: [N, OBS_DIM]}, info)."""
        with torch.no_grad():
            self._game_obs = self.game.reset()
        everything = torch.ones(self.game.num_games, dtype=torch.bool, device=self.game.device)
        for strat in self.opponents.values():
            strat.reset(everything)
        self._obs = self._split(self._game_obs)
        return self._obs, self._info()

    def step(self, actions: dict[str, Tensor]) -> tuple[dict[str, Tensor], dict[str, Tensor], dict[str, Tensor],
                                                        dict[str, Tensor], dict[str, Any]]:
        """actions {agent: [N, 4]} -> (obs {agent: [N, OBS_DIM]}, reward {agent: [N, 1]},
        terminated {agent: [N, 1] bool}, truncated {agent: [N, 1] bool, all False}, info)."""
        dev = self.game.device
        with torch.no_grad():
            act = {}
            for t in self.train_teams:
                act[t] = torch.stack([actions[a].to(dev, torch.float32).reshape(-1, 4) for a in self._names[t]],
                                     dim=1).clamp(-1.0, 1.0)                    # [N, M_team, 4]
            for t, strat in self.opponents.items():
                act[t] = strat.act(self._game_obs[t])
            out = self.game.step(act)
            for strat in self.opponents.values():
                strat.reset(out.done)
        self._game_obs = out.obs
        self._obs = self._split(out.obs)
        done = out.done[:, None]                                                  # [N, 1]
        never = torch.zeros_like(done)
        reward = {name: out.reward[t][:, i:i + 1] for t in self.train_teams for i, name in enumerate(self._names[t])}
        terminated = {a: done for a in self._possible_agents}
        truncated = {a: never for a in self._possible_agents}
        info = {**out.info, "outcome": out.outcome, "end_step": out.end_step, **self._info()}
        return self._obs, reward, terminated, truncated, info

    def state(self) -> dict[str, Tensor]:
        """{agent: [N, STATE_DIM]}: the central state, the same tensor for every agent (as skrl's Isaac Lab
        multi-agent wrapper returns it)."""
        s = self.game.state()
        return {a: s for a in self._possible_agents}

    def render(self, *args, **kwargs) -> None:
        """No viewer: the game is headless."""
        return None

    def close(self) -> None:
        """Nothing to release."""
        return None
