"""The Phase 2 replica as a training environment for stage 5.1 (NUS port Phase 5, task M2), in the partner's units, observation layout
``nus_area_denial_v1``.

What it adds to :class:`svg_training.nus.replica.NusReplica` (plan section 4.1, items 10 and 11; described from the partner's
``ma_skills/jax/mpe.py`` ``JAXMPEAdapter.critic_state`` and ``collect_fixed_matchups``, and ``ma_skills/jax/rewards.py``):

* **Starts** drawn fresh for every game by the replica's start rule, and the two spawn centres the partner's state carries: the Guard
  team's is the zone centre; the Strike team's is the mean of the Strike start positions (random starts) or the fixed cluster centre
  on the +x axis (fixed layout).
* **Central state** for the critic, in the partner's field order: positions (Guards first, x and y), the per-drone done flags, the step
  count, the zone position, the previous positions, the Guard spawn centre, the Strike spawn centre, the reached flag; 5M + 8 numbers
  for M drones, then a one-hot of the opponent slot, padded to the method's slot count.
* **Reward** of the Guard team per step: potential shaping (scale x (gamma x summed Strike distance to the zone after the step - the
  same before)), minus the inside penalty times the share of Strike drones inside the zone, plus the clean time-out reward on the last
  step of a game the Strike team never reached, minus the first-reach penalty on the step of the game's first reach. The Strike team
  gets the exact negative (zero-sum). The game always runs to the time limit; the reached flag is sticky.
* **Scripted block**: the partner's APF controller of either team (``nus/apf.py``).

Shapes: N games, G Guard and S Strike drones (M = G + S), Guards first. Everything is a batched tensor operation: no loop over games,
no ``.cpu()``, no NumPy. This file holds no partner value (G2): every number comes from the rules, deploy and method files.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch

from .apf import NusApf
from .deploy import NusDeploy
from .method_cfg import NusMethod
from .replica import NusReplica, ReplicaState
from .rules import NusRules

# the partner's critic-state fields in the order the port builds them (checked against the run config by nus_make_local_method.py)
CENTRAL_FIELDS = ("p_pos", "done", "step", "area_pos", "prev_p_pos", "agent_spawn_center", "adversary_spawn_center", "breach")
SPACE = 2  # the game is in the plane


@dataclass
class TrainState:
    """``game``: the replica state; ``guard_spawn``, ``strike_spawn``: (N, 2) spawn centres fixed at reset."""

    game: ReplicaState
    guard_spawn: torch.Tensor
    strike_spawn: torch.Tensor


@dataclass
class StepOut:
    """Per game (N,): the Guard team's reward (the Strike team's is its negative), Strike drones inside the zone after the step, whether
    the step was the game's first reach, whether it was the last step of the game, and the sticky reached flag after the step."""

    guard_reward: torch.Tensor
    inside_count: torch.Tensor
    first_reach: torch.Tensor
    time_limit: torch.Tensor
    reached: torch.Tensor


def guard_reward(prev_pos: torch.Tensor, pos: torch.Tensor, inside_count: torch.Tensor, time_limit: torch.Tensor,
                 reached_after: torch.Tensor, first_reach: torch.Tensor, *, guard_count: int, method: NusMethod,
                 shaping_gamma: float) -> torch.Tensor:
    """The Guard team's reward of one step, (N,). ``prev_pos``, ``pos``: (N, M, 2) before and after the step (zone at the origin);
    ``inside_count``: (N,) Strike drones inside after the step; ``time_limit``, ``reached_after``, ``first_reach``: (N,) bool."""
    strikes_before, strikes_after = prev_pos[:, guard_count:], pos[:, guard_count:]
    before = torch.linalg.norm(strikes_before, dim=-1).sum(dim=-1)
    after = torch.linalg.norm(strikes_after, dim=-1).sum(dim=-1)
    shaping = method.shaping_scale * (shaping_gamma * after - before)
    strike_count = pos.shape[1] - guard_count
    clean = (time_limit & ~reached_after).to(pos.dtype)
    outcome = method.clean_timeout_reward * clean - method.inside_penalty * (inside_count.to(pos.dtype) / strike_count)
    return shaping + outcome - method.first_reach_penalty * first_reach.to(pos.dtype)


class NusTrainEnv:
    """The replica with fresh starts, the central state, the reward and the scripted block. Units are the partner's."""

    def __init__(self, rules: NusRules, deploy: NusDeploy, method: NusMethod, device: torch.device | str = "cpu",
                 dtype: torch.dtype = torch.float32):
        self.rules, self.deploy, self.method = rules, deploy, method
        self.replica = NusReplica(rules, device, dtype)
        self.apf = NusApf(rules, deploy)
        self.device, self.dtype = self.replica.device, dtype
        self.guard_count, self.strike_count = rules.guard_count, rules.strike_count
        self.num_actors = self.replica.num_actors
        self.obs_dim = self.replica.obs_dim
        self.base_state_dim = (2 * 2 + 1) * self.num_actors + 2 * 2 * 2   # 5M + 8
        self.slots = method.max_pool_slots
        self.state_dim = self.base_state_dim + self.slots
        self.episode_steps = rules.episode_steps

    def team_size(self, team: str) -> int:
        return self.guard_count if team == "guard" else self.strike_count

    def team_speed(self, team: str) -> float:
        return self.rules.guard_max_speed if team == "guard" else self.rules.strike_max_speed

    # ------------------------------------------------------------------ starts
    def reset(self, n_games: int, generator: torch.Generator | None = None, random_start: bool | None = None) -> TrainState:
        """Fresh games from the replica's start rule (a ``torch.Generator`` makes them reproducible)."""
        use_random = self.rules.random_start if random_start is None else random_start
        game = self.replica.reset(n_games, generator=generator, random_start=use_random)
        guard_spawn = torch.zeros(n_games, SPACE, device=self.device, dtype=self.dtype)
        if use_random:
            strike_spawn = game.pos[:, self.guard_count:].mean(dim=1)
        else:
            strike_spawn = torch.zeros_like(guard_spawn)
            strike_spawn[:, 0] = self.rules.spawn_distance
        return TrainState(game=game, guard_spawn=guard_spawn, strike_spawn=strike_spawn)

    @staticmethod
    def from_positions(pos: torch.Tensor, prev_pos: torch.Tensor, reached: torch.Tensor, step: torch.Tensor,
                       strike_spawn: torch.Tensor) -> TrainState:
        """A state from recorded values (parity tests)."""
        return TrainState(ReplicaState(pos, prev_pos, reached, step), torch.zeros_like(strike_spawn), strike_spawn)

    # ------------------------------------------------------------------ views
    def observe(self, state: TrainState) -> tuple[torch.Tensor, torch.Tensor]:
        """(Guard observations (N, G, D), Strike observations (N, S, D)), D = 9M + 2."""
        obs = self.replica.observe(state.game)
        return obs[:, : self.guard_count], obs[:, self.guard_count:]

    def central_state(self, state: TrainState, slot_ids: torch.Tensor) -> torch.Tensor:
        """(N, 5M + 8 + slots): the partner's central state fields, then the one-hot of each game's opponent slot (N,)."""
        g = state.game
        n = g.pos.shape[0]
        done = (g.step >= self.episode_steps).to(self.dtype)[:, None].expand(n, self.num_actors)
        zone = torch.zeros(n, SPACE, device=self.device, dtype=self.dtype)
        one_hot = torch.nn.functional.one_hot(slot_ids.long(), self.slots).to(self.dtype)
        return torch.cat((g.pos.reshape(n, -1), done, g.step.to(self.dtype)[:, None], zone, g.prev_pos.reshape(n, -1),
                          state.guard_spawn, state.strike_spawn, g.reached[:, None], one_hot), dim=-1)

    # ------------------------------------------------------------------ step
    def step(self, state: TrainState, guard_actions: torch.Tensor, strike_actions: torch.Tensor,
             shaping_gamma: float) -> tuple[TrainState, StepOut]:
        """One joint step. ``guard_actions`` (N, G, 2), ``strike_actions`` (N, S, 2): requested displacements in units per step.
        ``shaping_gamma``: the learner team's discount (the partner shapes with the training team's gamma)."""
        g = state.game
        nxt = self.replica.step(g, torch.cat((guard_actions, strike_actions), dim=1))
        inside = self.replica.inside_zone(nxt.pos[:, self.guard_count:]).sum(dim=1)
        first = (nxt.reached > 0) & ~(g.reached > 0)
        time_limit = nxt.step >= self.episode_steps
        reward = guard_reward(g.pos, nxt.pos, inside, time_limit, nxt.reached > 0, first, guard_count=self.guard_count,
                              method=self.method, shaping_gamma=shaping_gamma)
        out = StepOut(guard_reward=reward, inside_count=inside, first_reach=first, time_limit=time_limit, reached=nxt.reached > 0)
        return TrainState(nxt, state.guard_spawn, state.strike_spawn), out

    def apf_actions(self, state: TrainState, team: str) -> torch.Tensor:
        """The partner's scripted controller of ``team``: (N, team size, 2)."""
        return self.apf.actions(team, state.game.pos)
