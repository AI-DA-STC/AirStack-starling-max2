"""The players of the Phase 4 ladder, by name (plan D2): the policies bound to their deploy files, the ported scripted controllers as
strategies for our game, the parked Guard, and the replica callables of rows 1 and 2.1. This file holds no partner value.

Names: ``G19`` / ``S20`` (the archive entries of the partner's seed 2 generations 19 and 20, deploy file ``DEPLOY_REF``), ``P3G`` /
``P3S`` (the Phase 3 pair, W2's deploy file), ``ApfGuard`` / ``ApfStrike`` (the partner's scripted controllers), ``ParkedGuard`` (Run 0's
parked Guard); any name of ``opponents.scripted.REGISTRY`` plays in our game only.

``NusPolicy`` reads ``type(self).deploy_path`` (None = the module-level ``DEPLOY_PATH``, resolved at construction), so a binding is a thin
subclass. The ported controllers sample on the policies' schedule: when a game's tick is a multiple of ``hold_ticks`` (and on the first tick
after its reset) they read the positions, then hold the command between samples. ``ParkedGuard`` commands zero for the whole game; the game
puts Guard 0 at the zone centre before the first step (``parks_guard0``).
"""
from __future__ import annotations

import torch
from torch import Tensor

from ..core.game_config import GameCfg
from ..core.observations import ObsView
from . import strategy as strategy_module
from .actor import NusActor
from .apf import NusApf
from .deploy import apply_overrides, load_deploy, weights_folder
from .replica import NusReplica
from .rules import ROOT, load_rules
from .strategy import ACTION_WIDTH, NusPolicy, _check_cfg

DEPLOY_REF = ROOT / "configs" / "local" / "nus_deploy_ref.toml"
_V = ObsView()


class _Bound(NusPolicy):
    """A policy of one team bound to one deploy file. Constructor of ``make_strategy``: (team, cfg, num_games, device, seed)."""
    TEAM = ""

    def __init__(self, team: str, cfg: GameCfg, num_games: int, device, seed: int = 0):
        if team != self.TEAM:
            raise ValueError(f"{type(self).__name__} plays the {self.TEAM} team, not {team!r}")
        super().__init__(team, cfg, num_games, device, seed)
        self.name = type(self).__name__


class RefGuard(_Bound):
    TEAM, deploy_path = "guard", DEPLOY_REF


class RefStrike(_Bound):
    TEAM, deploy_path = "strike", DEPLOY_REF


class P3Guard(_Bound):
    TEAM = "guard"


class P3Strike(_Bound):
    TEAM = "strike"


class _Ported(NusPolicy):
    """A ported scripted controller as a strategy: positions in partner units rebuilt from our observation, sampled on the policies'
    schedule, held between samples. Shares ``NusPolicy.reset`` and ``_positions``."""
    TEAM = ""
    parks_guard0 = False

    def __init__(self, team: str, cfg: GameCfg, num_games: int, device, seed: int = 0):
        if team != self.TEAM:
            raise ValueError(f"{type(self).__name__} plays the {self.TEAM} team, not {team!r}")
        deploy = load_deploy(strategy_module.DEPLOY_PATH)
        rules = apply_overrides(load_rules(strategy_module.RULES_PATH), deploy)
        _check_cfg(cfg, rules, deploy, team)
        self.team, self.cfg, self.num_games, self.device = team, cfg, num_games, torch.device(device)
        self.rules, self.deploy, self.apf = rules, deploy, NusApf(rules, deploy)
        self.guards, self.strikes = rules.guard_count, rules.strike_count
        self.team_size = self.guards if team == "guard" else self.strikes
        self.speed_units = rules.guard_max_speed if team == "guard" else rules.strike_max_speed
        n = num_games
        self.tick = torch.zeros(n, dtype=torch.long, device=self.device)
        self.reached = torch.zeros(n, device=self.device)  # unused by the controllers; NusPolicy.reset clears it
        self.fresh = torch.ones(n, dtype=torch.bool, device=self.device)
        self.held = torch.zeros(n, self.team_size, ACTION_WIDTH, device=self.device)
        self.name = type(self).__name__

    @torch.no_grad()
    def act(self, obs: Tensor) -> Tensor:
        pos = self._positions(obs)
        sample = self.tick % self.deploy.hold_ticks == 0
        units = self.apf.actions(self.team, pos)
        command = torch.cat((units / self.speed_units, torch.zeros_like(units)), dim=-1).clamp(-1, 1)
        new = command * obs[..., _V.alive:_V.alive + 1]
        self.held = torch.where(sample[:, None, None], new, self.held)
        self.fresh = self.fresh & ~sample
        self.tick = self.tick + 1
        return self.held.clone()


class ApfGuard(_Ported):
    TEAM = "guard"


class ApfStrike(_Ported):
    TEAM = "strike"


class ParkedGuard:
    """Run 0's parked Guard: every Guard commands zero at every step; the game starts Guard 0 at the zone centre (``parks_guard0``)."""
    team, name, parks_guard0 = "guard", "ParkedGuard", True

    def __init__(self, team: str, cfg: GameCfg, num_games: int, device, seed: int = 0):
        if team != "guard":
            raise ValueError("ParkedGuard plays the guard team")
        self.cfg, self.num_games, self.device = cfg, num_games, torch.device(device)
        self.size = load_rules(strategy_module.RULES_PATH).guard_count

    def reset(self, games: Tensor) -> None:
        """Stateless."""

    def act(self, obs: Tensor) -> Tensor:
        return torch.zeros(obs.shape[0], obs.shape[1], ACTION_WIDTH, device=obs.device)


class JumpPlayer:
    """Jump motion (rows 2.1, 2.2): the wrapped player acts on a game's sample ticks only (its own ``tick`` counts them), zero between."""

    def __init__(self, inner, hold_ticks: int):
        self.inner, self.hold_ticks = inner, hold_ticks
        self.team, self.name, self.parks_guard0 = inner.team, inner.name, parks_guard0(inner)

    def reset(self, games: Tensor) -> None:
        self.inner.reset(games)

    def act(self, obs: Tensor) -> Tensor:
        action = self.inner.act(obs)
        if not hasattr(self.inner, "tick"):   # ParkedGuard commands zero every tick
            return action
        sample = ((self.inner.tick - 1) % self.hold_ticks == 0)[:, None, None]  # the inner player has counted this tick already
        return torch.where(sample, action, torch.zeros_like(action))


STRATEGIES: dict[str, type] = {"G19": RefGuard, "S20": RefStrike, "P3G": P3Guard, "P3S": P3Strike, "ApfGuard": ApfGuard,
                               "ApfStrike": ApfStrike, "ParkedGuard": ParkedGuard}
TEAM_OF = {"G19": "guard", "S20": "strike", "P3G": "guard", "P3S": "strike", "ApfGuard": "guard", "ApfStrike": "strike",
           "ParkedGuard": "guard"}
POLICIES = ("G19", "S20", "P3G", "P3S")  # the converted partner policies


def deploy_path_of(name: str):
    """The deploy file a player reads (the module-level one for the Phase 3 pair and the controllers)."""
    cls = STRATEGIES.get(name)
    return (getattr(cls, "deploy_path", None) if cls is not None else None) or strategy_module.DEPLOY_PATH


def make_player(name: str, team: str, cfg: GameCfg, num_games: int, device, seed: int = 0, jump_hold_ticks: int = 0):
    """A strategy of our game by name: the ladder's own names first, then ``opponents.scripted`` (``strike_straight`` ...). With
    ``jump_hold_ticks`` the player acts on sample ticks only (jump motion; our own scripted players are refused)."""
    if name in STRATEGIES:
        if TEAM_OF[name] != team:
            raise ValueError(f"{name} plays the {TEAM_OF[name]} team, not {team!r}")
        player = STRATEGIES[name](team, cfg, num_games, device, seed)
        return JumpPlayer(player, jump_hold_ticks) if jump_hold_ticks else player
    if jump_hold_ticks:
        raise ValueError(f"{name!r} reads our observation every tick and has no sample ticks: it cannot play in jump motion")
    from ..opponents.scripted import make_strategy
    return make_strategy(name, team, cfg, num_games, device, seed)


def parks_guard0(player) -> bool:
    return bool(getattr(player, "parks_guard0", False))


class ReplicaPlayer:
    """A player of the replica (rows 1 and 2.1): ``__call__(team_observation [N, T, obs], positions [N, M, 2] in units) -> displacement
    requests [N, T, 2] in units per step``. ``parks_guard0`` is read by the starts."""

    def __init__(self, name: str, device: torch.device | str = "cpu"):
        if name not in STRATEGIES:
            raise ValueError(f"{name!r} cannot play in the replica (it reads our observation); known: {sorted(STRATEGIES)}")
        self.name, self.team, self.parks_guard0 = name, TEAM_OF[name], name == "ParkedGuard"
        deploy_file = deploy_path_of(name)
        deploy = load_deploy(deploy_file)
        rules = apply_overrides(load_rules(strategy_module.RULES_PATH), deploy)
        self.rules, self.deploy = rules, deploy
        self.actor = None
        if name in POLICIES:
            self.actor = NusActor.load(weights_folder(deploy, self.team), team=self.team, rules=rules, deploy=deploy, device=device)
        self.apf = NusApf(rules, deploy)

    @torch.no_grad()
    def __call__(self, obs: Tensor, pos: Tensor) -> Tensor:
        if self.actor is not None:
            return self.actor.act_units(obs)
        if self.parks_guard0:
            return torch.zeros(obs.shape[0], obs.shape[1], 2, device=obs.device)
        return self.apf.actions(self.team, pos)


def replica_for(name: str, device="cpu") -> NusReplica:
    """The replica of a player's deploy file (W2's and the reference deploy file differ only in the weights folders)."""
    deploy = load_deploy(deploy_path_of(name))
    return NusReplica(apply_overrides(load_rules(strategy_module.RULES_PATH), deploy), device=device)
