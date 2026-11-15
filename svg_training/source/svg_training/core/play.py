"""S2 match loop: two strategies play N games at once; every game slot's FIRST finished game is kept (Task 6).

Inside the loop everything is a batched tensor operation (no loop over games, no host reads); the only host read
is one check every ``CHECK_EVERY_STEPS`` steps, outside the game step, to stop once every slot has finished
its first game. Shapes: N games, M drones (Guard drones first)."""
from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor

from .game import SvgGame
from .rewards import RUNNING
from .strategy import Strategy

CHECK_EVERY_STEPS = 100


@dataclass
class MatchResult:
    """One entry per game slot: its FIRST finished game (a slot that never finished has outcome 0 = running and
    is left out of every summary). outcome [N] int8 (1 Strike win, 2 Guard win), end_step [N] long (the step it
    ended on), band [N] long (index into BANDS), closest_cross_m [N] (closest horizontal approach of any live
    opposite pair over the game's steps, m; inf if none), rule_breach [N] bool (some step had an opposite pair
    closer than the keep-out), filter_corrected_rate [N] (share of live drone-steps the safety filter changed),
    start_miss [N] bool (the game's starts could not meet the spacing / keep-out). steps_played: steps the loop
    ran (all N games step every time, so N x steps_played game-steps were simulated)."""
    outcome: Tensor
    end_step: Tensor
    band: Tensor
    closest_cross_m: Tensor
    rule_breach: Tensor
    filter_corrected_rate: Tensor
    start_miss: Tensor
    steps_played: int = 0

    def slice(self, sl: slice) -> "MatchResult":
        """The games in sl (e.g. one strategy pair's share of a packed batch)."""
        return MatchResult(self.outcome[sl], self.end_step[sl], self.band[sl], self.closest_cross_m[sl],
                           self.rule_breach[sl], self.filter_corrected_rate[sl], self.start_miss[sl],
                           self.steps_played)


def play_match(game: SvgGame, guard: Strategy, strike: Strategy, max_steps: int | None = None) -> MatchResult:
    """Reset the game and both strategies, then step until every slot has finished its first game (checked on
    the host once every CHECK_EVERY_STEPS steps) or max_steps steps (default: the game length in ticks, by which
    every first game has ended). Each step: act(obs) once per team, game.step, then reset(done) on both
    strategies. Later games in a slot (after auto-reset) are played but not counted."""
    if guard.team != "guard" or strike.team != "strike":
        raise ValueError(f"guard plays {guard.team!r}, strike plays {strike.team!r}: need 'guard' and 'strike'")
    n, dev = game.num_games, game.device
    max_steps = game.ticks if max_steps is None else int(max_steps)
    obs = game.reset()
    start = torch.ones(n, dtype=torch.bool, device=dev)
    guard.reset(start)
    strike.reset(start)
    finished = torch.zeros(n, dtype=torch.bool, device=dev)
    outcome = torch.full((n,), RUNNING, dtype=torch.int8, device=dev)
    end_step = torch.zeros(n, dtype=torch.long, device=dev)
    band = game.arenas.band.clone()
    start_miss = game.start_miss.clone()
    closest = torch.full((n,), float("inf"), device=dev)
    breach = torch.zeros(n, dtype=torch.bool, device=dev)
    corrected = torch.zeros(n, device=dev)
    live = torch.zeros(n, device=dev)
    steps = 0
    for steps in range(1, max_steps + 1):
        out = game.step({"guard": guard.act(obs["guard"]), "strike": strike.act(obs["strike"])})
        active = ~finished                                    # the slot's first game played this step
        info = out.info
        closest = torch.where(active, torch.minimum(closest, info["closest_cross_m"]), closest)
        breach = breach | (active & info["rule_breach"])
        alive = info["final_alive"]
        corrected = corrected + active * (info["filter_corrected"] & alive).sum(dim=1)
        live = live + active * alive.sum(dim=1)
        first_end = active & out.done
        outcome = torch.where(first_end, out.outcome, outcome)
        end_step = torch.where(first_end, out.end_step, end_step)
        band = torch.where(first_end, info["band"], band)
        start_miss = torch.where(first_end, info["start_miss"], start_miss)
        finished = finished | out.done
        guard.reset(out.done)
        strike.reset(out.done)
        obs = out.obs
        if steps % CHECK_EVERY_STEPS == 0 and bool(finished.all()):     # one host read, outside the game step
            break
    return MatchResult(outcome, end_step, band, closest, breach, corrected / live.clamp(min=1.0), start_miss,
                       steps)
