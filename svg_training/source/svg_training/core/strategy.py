"""The strategy contract: how any controller (scripted, learned, a partner's) plugs into the game.

A strategy plays one team. It is called once per step with that team's observations in ALL games at once,
may keep memory per game, and is told which games just started (``reset``). This module imports no
training library: adapters (skrl and others) wrap their policies into this shape from the outside."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import torch
from torch import Tensor

from .game import SvgGame
from .observations import OBS_DIM


@runtime_checkable
class Strategy(Protocol):
    """Plays one team (``team`` = "guard" or "strike")."""
    team: str
    name: str

    def reset(self, games: Tensor) -> None:
        """games [N] bool: these games just started; clear their memory. Called with all True before the
        first step, then with ``StepOut.done`` after every step."""

    def act(self, obs: Tensor) -> Tensor:
        """obs [N, M_team, OBS_DIM] -> actions [N, M_team, 4] in [-1, 1] (vx, vy, vz, yaw rate)."""


class SplitStrategy:
    """Different strategies on fixed slices of the games (e.g. half the games face one opponent)."""

    def __init__(self, team: str, parts: list[tuple[Strategy, slice]]):
        if not parts:
            raise ValueError("SplitStrategy needs at least one part")
        for strat, _ in parts:
            if strat.team != team:
                raise ValueError(f"part {strat.name!r} plays {strat.team!r}, split is for {team!r}")
        self.team = team
        self.parts = parts
        self.name = "split(" + ",".join(s.name for s, _ in parts) + ")"

    def reset(self, games: Tensor) -> None:
        """games [N] bool."""
        for strat, sl in self.parts:
            strat.reset(games[sl])

    def act(self, obs: Tensor) -> Tensor:
        """obs [N, M_team, OBS_DIM] -> [N, M_team, 4]. Games outside every slice get zeros."""
        out = obs.new_zeros(*obs.shape[:2], 4)
        for strat, sl in self.parts:
            out[sl] = strat.act(obs[sl])
        return out


def _check_actions(strategy: Strategy, a: Tensor, shape: tuple[int, int, int], device: torch.device,
                   step: int) -> None:
    who = f"strategy {strategy.name!r} step {step}"
    assert isinstance(a, Tensor), f"{who}: shape rule: act must return a Tensor, got {type(a).__name__}"
    assert tuple(a.shape) == shape, f"{who}: shape rule: expected {shape}, got {tuple(a.shape)}"
    assert a.is_floating_point(), f"{who}: dtype rule: actions must be floating point, got {a.dtype}"
    assert a.device == device, f"{who}: device rule: actions on {a.device}, game on {device}"
    assert not a.requires_grad and a.grad_fn is None, f"{who}: autograd rule: actions carry a graph (detach)"
    assert bool(torch.isfinite(a).all()), f"{who}: finite rule: actions contain NaN or inf"
    assert bool((a.abs() <= 1.0).all()), f"{who}: range rule: actions outside [-1, 1]"


def check_strategy(strategy: Strategy, game: SvgGame, steps: int = 50) -> None:
    """Play ``steps`` steps of ``game`` (the other team stands still) and raise AssertionError naming the
    rule a strategy breaks: shape, dtype, device, no autograd graph, finite, range. Resets the game first."""
    team = strategy.team
    assert team in ("guard", "strike"), f"strategy {strategy.name!r}: team rule: team is {team!r}"
    other = "strike" if team == "guard" else "guard"
    count = {"guard": game.guards, "strike": game.strikes}
    obs = game.reset()
    strategy.reset(torch.ones(game.num_games, dtype=torch.bool, device=game.device))
    still = torch.zeros(game.num_games, count[other], 4, device=game.device)
    for k in range(steps):
        o = obs[team]
        assert o.shape[-1] == OBS_DIM, f"observation width {o.shape[-1]} != OBS_DIM {OBS_DIM}"
        a = strategy.act(o)
        _check_actions(strategy, a, (game.num_games, count[team], 4), o.device, k)
        out = game.step({team: a, other: still})
        obs = out.obs
        strategy.reset(out.done)
