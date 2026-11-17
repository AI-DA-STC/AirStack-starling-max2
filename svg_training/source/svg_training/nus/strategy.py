"""The partner's trained policy as a strategy for our game: ``svg_training.nus.strategy:NusPolicy`` through
``make_strategy("module:Class")`` (constructor ``(team, cfg, num_games, device, seed)``).

What it does each simulator tick, for all games at once (no loop over games, no host read):

* It reads only the observation (``opponents/scripted.py``): every drone's position relative to the zone centre, in metres, turned
  into the partner's units with the deploy file's metres per unit.
* Every ``hold_ticks`` ticks of a game (and on the first tick after the game's reset) it samples: it rebuilds the partner's
  observation from the positions now, the positions at the previous sample (its own memory; at a reset they are the current ones) and
  the reached flag (its own memory: set once any Strike drone is inside the zone at a sample, cleared at a reset), asks the converted
  actor for a displacement request in units per step and converts it to the normalised command: units per step divided by the team's
  speed in units per step. Between samples it holds the last command.
* Vertical speed and yaw rate are zero. A drone that is out gets a zero command.

The partner's observation is built with :class:`svg_training.nus.replica.NusReplica`'s own ``observe``, so the two cannot drift apart.
The class refuses (naming keys, never values) a game configuration whose scale, step length or team speeds differ from the deploy and
rules files, because the command would then not be the partner's action. It plays fixed team sizes; a drone removed from the game is
not modelled (its slot is absent in our observation).

Local files: ``RULES_PATH`` and ``DEPLOY_PATH`` (git-ignored); the converted weights come from the folder the deploy file names for the team.
"""
from __future__ import annotations

import math

import torch
from torch import Tensor

from ..core.game_config import GameCfg
from ..core.observations import SLOT, ObsView
from .actor import NusActor
from .deploy import LOCAL_DEPLOY, apply_overrides, load_deploy, weights_folder
from .replica import NusReplica, ReplicaState
from .rules import LOCAL_RULES, load_rules

RULES_PATH = LOCAL_RULES
DEPLOY_PATH = LOCAL_DEPLOY
_V = ObsView()
TEAMS = ("guard", "strike")
ACTION_WIDTH = 2 * 2  # vx, vy, vz, yaw rate


def _check_cfg(cfg: GameCfg, rules, deploy, team: str) -> None:
    """Refuse a game whose scale, step length or team speeds are not the ones the policy was trained with."""
    wrong = []
    if not math.isclose(cfg.rules.metres_per_unit, deploy.metres_per_unit):
        wrong.append("rules.metres_per_unit")
    if not math.isclose(cfg.rules.seconds_per_step, deploy.seconds_per_step):
        wrong.append("rules.seconds_per_step")
    if not math.isclose(cfg.rules.strike_units_per_step, rules.strike_max_speed):
        wrong.append("rules.strike_units_per_step")
    if not math.isclose(cfg.rules.guard_units_per_step, rules.guard_max_speed):
        wrong.append("rules.guard_units_per_step")
    if cfg.dropout_fraction != 0:
        wrong.append("dropout_fraction")
    if cfg.obs_view != "full":
        wrong.append("obs_view")
    if wrong:
        raise ValueError(f"the game configuration does not match the partner policy's deploy and rules files on: {wrong}")


class NusPolicy:
    """The partner's converted actor playing one team. Batched torch only; per-game memory; deterministic."""
    name = "NusPolicy"
    deploy_path = None  # a subclass binds another deploy file (nus/players.py); None = the module-level DEPLOY_PATH, read at construction

    def __init__(self, team: str, cfg: GameCfg, num_games: int, device, seed: int = 0):
        if team not in TEAMS:
            raise ValueError(f"team must be 'guard' or 'strike', got {team!r}")
        deploy = load_deploy(type(self).deploy_path or DEPLOY_PATH)
        rules = apply_overrides(load_rules(RULES_PATH), deploy)
        _check_cfg(cfg, rules, deploy, team)
        self.team, self.cfg, self.num_games, self.device = team, cfg, num_games, torch.device(device)
        self.rules, self.deploy = rules, deploy
        self.actor = NusActor.load(weights_folder(deploy, team), team=team, rules=rules, deploy=deploy, device=self.device)
        self.replica = NusReplica(rules, device=self.device)
        self.guards, self.strikes = rules.guard_count, rules.strike_count
        self.team_size = self.actor.team_size
        self.rows = slice(0, self.guards) if team == "guard" else slice(self.guards, self.guards + self.strikes)
        self.speed_units = self.actor.max_speed
        n, m = num_games, self.guards + self.strikes
        self.memory_pos = torch.zeros(n, m, 2, device=self.device)  # positions at the previous sample, units
        self.reached = torch.zeros(n, device=self.device)
        self.tick = torch.zeros(n, dtype=torch.long, device=self.device)
        self.fresh = torch.ones(n, dtype=torch.bool, device=self.device)  # no sample since the game started
        self.held = torch.zeros(n, self.team_size, ACTION_WIDTH, device=self.device)
        self.partner_obs = torch.zeros(n, self.team_size, self.actor.obs_dim, device=self.device)

    def reset(self, games: Tensor) -> None:
        """games [N] bool: these games just started; clear their memory."""
        keep = ~games
        self.tick = torch.where(games, torch.zeros_like(self.tick), self.tick)
        self.fresh = self.fresh | games
        self.reached = self.reached * keep
        self.held = self.held * keep[:, None, None]

    def _positions(self, obs: Tensor) -> Tensor:
        """Every drone's position relative to the zone centre in units, (N, M, 2), from this team's observations (own positions for the
        team, the first member's slots for the other team)."""
        own = obs[..., _V.own_pos][..., :2]  # (N, T, 2) metres
        pad_guards = self.cfg.pad_guards
        slots = obs[:, 0, _V.SLOTS_FROM:_V.SLOTS_FROM + SLOT * (pad_guards + self.cfg.pad_strikes)].reshape(obs.shape[0], -1, SLOT)
        relative = slots[..., :2]  # (N, pads, 2) relative to the first member
        if self.team == "guard":
            others = relative[:, pad_guards:pad_guards + self.strikes]
            team_pos, other_pos = own, own[:, :1] + others
            full = torch.cat((team_pos, other_pos), dim=1)
        else:
            others = relative[:, :self.guards]
            full = torch.cat((own[:, :1] + others, own), dim=1)
        return full / self.deploy.metres_per_unit

    @torch.no_grad()
    def act(self, obs: Tensor) -> Tensor:
        """obs [N, M_team, OBS_DIM] -> actions [N, M_team, 4] in [-1, 1] (vx, vy, vz, yaw rate)."""
        if obs.shape[1] != self.team_size:
            raise ValueError("the observation's team size is not the one the policy was trained with")
        pos = self._positions(obs)
        zone_units = obs[:, 0, _V.zone_radius] / self.deploy.metres_per_unit
        sample = (self.tick % self.deploy.hold_ticks == 0)
        previous = torch.where(self.fresh[:, None, None], pos, self.memory_pos)
        strike_inside = (torch.linalg.norm(pos[:, self.guards:], dim=-1) <= zone_units[:, None]).any(dim=1)
        # the reached flag is set at a sample, and not at a game's first sample (the partner's game sets it from the first step on)
        reached = torch.where(sample & ~self.fresh, torch.maximum(self.reached, strike_inside.to(self.reached.dtype)), self.reached)
        state = ReplicaState(pos=pos, prev_pos=previous, reached=reached, step=torch.zeros_like(self.tick))
        partner_obs = self.replica.observe(state)[:, self.rows]
        units = self.actor.act_units(partner_obs)
        command = torch.cat((units / self.speed_units, torch.zeros_like(units)), dim=-1).clamp(-1, 1)
        alive = obs[..., _V.alive:_V.alive + 1]
        new = (command * alive) * 1.0
        sampled = sample[:, None, None]
        self.held = torch.where(sampled, new, self.held)
        self.partner_obs = torch.where(sampled, partner_obs, self.partner_obs)
        self.memory_pos = torch.where(sample[:, None, None], pos, self.memory_pos)
        self.reached = reached
        self.fresh = self.fresh & ~sample
        self.tick = self.tick + 1
        return self.held.clone()
