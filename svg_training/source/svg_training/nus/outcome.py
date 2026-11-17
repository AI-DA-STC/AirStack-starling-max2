"""Outcome parity of the converted policy with the partner's own (gate b): batched games in the replica, the Wilson interval, the pass rule.

Both arms (the partner's JAX policy through its action worker, and our converted policy) play their team against the ported scripted
controller of the other team, from the same starts, with deterministic actions. The score is the rate of games in which the Strike team
reaches the zone (the replica's reached flag at the end of the episode). The gate passes when the converted policy's rate lies inside the
Wilson interval of the JAX arm's rate, at the confidence the gate text names. No partner value is held here.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from fractions import Fraction
from statistics import NormalDist
from typing import Callable

import torch

from .apf import NusApf
from .replica import NusReplica, ReplicaState

PERCENT = int("100")  # unit conversion of a percentage, not a game value
_CONFIDENCE = re.compile(r"within_(?P<pct>[1-9][0-9]?)pct_interval")


def parse_confidence(rule: str) -> float:
    """The confidence level in the gate's text (``..._within_95pct_interval_of_jax``) as a fraction; refuses another form."""
    found = _CONFIDENCE.search(rule)
    if found is None:
        raise ValueError("the outcome-parity gate text must name a percentage interval ('within_<pct>pct_interval')")
    return float(Fraction(int(found["pct"]), PERCENT))


def wilson_interval(successes: int, games: int, confidence: float) -> tuple[float, float]:
    """Wilson score interval of a rate (two-sided, at ``confidence``)."""
    z = NormalDist().inv_cdf(1 - (1 - confidence) / 2)
    rate = successes / games
    denominator = 1 + z * z / games
    centre = (rate + z * z / (2 * games)) / denominator
    half = z * math.sqrt(rate * (1 - rate) / games + z * z / (2 * games) ** 2) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def verdict(jax_reached: int, converted_reached: int, games: int, confidence: float) -> dict:
    """Both rates with their intervals and the pass rule: the converted rate inside the JAX arm's interval."""
    jax_interval = wilson_interval(jax_reached, games, confidence)
    converted_interval = wilson_interval(converted_reached, games, confidence)
    rate = converted_reached / games
    return {"games": games, "confidence": confidence,
            "jax_reached": jax_reached, "jax_rate": jax_reached / games, "jax_interval": list(jax_interval),
            "converted_reached": converted_reached, "converted_rate": rate, "converted_interval": list(converted_interval),
            "converted_within_jax_interval": bool(jax_interval[0] <= rate <= jax_interval[1]),
            "jax_within_converted_interval": bool(converted_interval[0] <= jax_reached / games <= converted_interval[1])}


@dataclass
class ArmResult:
    """``reached`` [N] bool: the Strike team reached the zone at some step; ``first_reach_step`` [N] long: the step it first did
    (1-based, -1 if never); ``final_pos`` [N, M, 2]."""
    reached: torch.Tensor
    first_reach_step: torch.Tensor
    final_pos: torch.Tensor


@torch.no_grad()
def play_arm(sim: NusReplica, apf: NusApf, team: str, starts: torch.Tensor,
             policy: Callable[[torch.Tensor], torch.Tensor]) -> ArmResult:
    """``team`` plays by ``policy`` (team observations [N, T, obs] -> displacement requests [N, T, 2] in units per step) against the
    scripted controller of the other team, from ``starts`` [N, M, 2] (the previous positions equal the starts), for the episode length."""
    if team not in ("guard", "strike"):
        raise ValueError(f"team must be 'guard' or 'strike', got {team!r}")
    guards = sim.guard_count
    other = "strike" if team == "guard" else "guard"
    games = starts.shape[0]
    state = ReplicaState(pos=starts.clone(), prev_pos=starts.clone(), reached=torch.zeros(games, dtype=sim.dtype, device=sim.device),
                         step=torch.zeros(games, dtype=torch.long, device=sim.device))
    first = torch.full((games,), -1, dtype=torch.long, device=sim.device)
    for step in range(sim.rules.episode_steps):
        observation = sim.observe(state)
        mine = policy(observation[:, :guards] if team == "guard" else observation[:, guards:])
        theirs = apf.actions(other, state.pos)
        actions = torch.cat((mine, theirs) if team == "guard" else (theirs, mine), dim=1)
        state = sim.step(state, actions)
        first = torch.where((first < 0) & (state.reached > 0), torch.full_like(first, step + 1), first)
    return ArmResult(reached=state.reached > 0, first_reach_step=first, final_pos=state.pos)


@torch.no_grad()
def play_pair(sim: NusReplica, guard_policy: Callable[[torch.Tensor], torch.Tensor], strike_policy: Callable[[torch.Tensor], torch.Tensor],
              starts: torch.Tensor) -> ArmResult:
    """Both teams play by their policies (team observations [N, T, obs] -> displacement requests [N, T, 2] in units per step) from ``starts``
    [N, M, 2], for the episode length (the archive arm of Phase 4's W3). Same bookkeeping as :func:`play_arm`."""
    guards = sim.guard_count
    games = starts.shape[0]
    state = ReplicaState(pos=starts.clone(), prev_pos=starts.clone(), reached=torch.zeros(games, dtype=sim.dtype, device=sim.device),
                         step=torch.zeros(games, dtype=torch.long, device=sim.device))
    first = torch.full((games,), -1, dtype=torch.long, device=sim.device)
    for step in range(sim.rules.episode_steps):
        observation = sim.observe(state)
        actions = torch.cat((guard_policy(observation[:, :guards]), strike_policy(observation[:, guards:])), dim=1)
        state = sim.step(state, actions)
        first = torch.where((first < 0) & (state.reached > 0), torch.full_like(first, step + 1), first)
    return ArmResult(reached=state.reached > 0, first_reach_step=first, final_pos=state.pos)
