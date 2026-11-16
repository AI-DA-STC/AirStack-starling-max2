"""Scripted opponents. Every one reads ONLY the observation tensor (decoded with ObsView), never the game
object. Positions in the observation are relative to the zone centre, so the zone centre is the origin and
a drone's own position is its offset from the zone. Slots hold the other drones relative to the own drone:
Guard drones in slots 0..pad_guards-1, Strike drones from slot pad_guards on."""
from __future__ import annotations

import importlib
from pathlib import Path

import torch
from torch import Tensor

from ..core.game_config import GameCfg
from ..core.observations import SLOT, ObsView

_V = ObsView()
STEER_RAMP_M = 0.25      # steering slows to a stop inside this distance of the target
FIELD_RANGE_M = 1.1      # Guard field: team-mates closer than this push


def _unit(v: Tensor) -> Tensor:
    """v [..., 2] -> unit vector (zero stays zero)."""
    return v / v.norm(dim=-1, keepdim=True).clamp(min=1e-9)


def steer(delta_m: Tensor) -> Tensor:
    """delta_m [..., 2] (target - own) -> action xy [..., 2]: unit(delta) * min(1, |delta| / 0.25 m)."""
    d = delta_m.norm(dim=-1, keepdim=True)
    return delta_m / d.clamp(min=1e-9) * (d / STEER_RAMP_M).clamp(max=1.0)


def _pack(xy: Tensor, obs: Tensor) -> Tensor:
    """xy [N, M, 2] -> actions [N, M, 4] (vz and yaw rate zero); drones that are out get zeros."""
    a = torch.cat((xy, xy.new_zeros(*xy.shape[:2], 2)), dim=-1)
    return a * obs[..., _V.alive:_V.alive + 1]


def _slots(obs: Tensor, first: int, count: int) -> tuple[Tensor, Tensor, Tensor]:
    """Slots first..first+count-1 -> (rel pos xy [N, M, k, 2], rel vel xy [N, M, k, 2], present [N, M, k])."""
    start = _V.SLOTS_FROM + SLOT * first
    s = obs[..., start:start + SLOT * count].reshape(*obs.shape[:2], count, SLOT)
    return s[..., 0:2], s[..., 3:5], s[..., 6] > 0.5


class _Scripted:
    """Common constructor: (team, cfg, num_games, device, seed). Subclasses set TEAM (None = either)."""
    TEAM: str | None = None
    name = "scripted"

    def __init__(self, team: str, cfg: GameCfg, num_games: int, device, seed: int = 0):
        if team not in ("guard", "strike"):
            raise ValueError(f"team must be 'guard' or 'strike', got {team!r}")
        if self.TEAM is not None and team != self.TEAM:
            raise ValueError(f"{type(self).__name__} plays the {self.TEAM} team, not {team!r}")
        self.team, self.cfg, self.num_games, self.device = team, cfg, num_games, device
        self.name = type(self).__name__

    def reset(self, games: Tensor) -> None:
        """Stateless: nothing to clear."""

    def act(self, obs: Tensor) -> Tensor:
        """obs [N, M_team, OBS_DIM] -> [N, M_team, 4]."""
        raise NotImplementedError


class ZeroActions(_Scripted):
    """Stands still."""

    def act(self, obs: Tensor) -> Tensor:
        return obs.new_zeros(*obs.shape[:2], 4)


class RandomActions(_Scripted):
    """Uniform in [-1, 1] on all four channels, from its own seeded generator."""

    def __init__(self, team: str, cfg: GameCfg, num_games: int, device, seed: int = 0):
        super().__init__(team, cfg, num_games, device, seed)
        self.gen = torch.Generator(device=device)
        self.gen.manual_seed(seed)

    def act(self, obs: Tensor) -> Tensor:
        a = torch.rand(*obs.shape[:2], 4, generator=self.gen, device=obs.device) * 2.0 - 1.0
        return a * obs[..., ObsView.alive:ObsView.alive + 1]       # drones that are out get zeros


class _Guard(_Scripted):
    TEAM = "guard"

    def _marked(self, obs: Tensor) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        """Guard i marks live Strike drone (i mod S_live) in slot order. Returns the marked drone's
        (position rel zone [N, G, 2], velocity [N, G, 2], found [N, G] bool), and own position [N, G, 2]."""
        pg = self.cfg.pad_guards
        rp, rv, pres = _slots(obs, pg, self.cfg.pad_strikes)                    # [N, G, 3, 2], .., [N, G, 3]
        own_p, own_v = obs[..., _V.own_pos][..., :2], obs[..., _V.own_vel][..., :2]
        g = obs.shape[1]
        n_live = pres.sum(-1)                                                    # [N, G]
        rank = torch.arange(g, device=obs.device)[None, :] % n_live.clamp(min=1)
        pick = pres & ((pres.cumsum(-1) - 1) == rank[..., None])                 # one-hot over strike slots
        w = pick.to(obs.dtype)[..., None]
        strike_p = own_p + (rp * w).sum(-2)
        strike_v = own_v + (rv * w).sum(-2)
        return strike_p, strike_v, n_live > 0, own_p


class _GuardMark(_Guard):
    FRACTION = 1.0

    def act(self, obs: Tensor) -> Tensor:
        sp, _, found, own_p = self._marked(obs)
        r = obs[..., _V.zone_radius, None]
        target = _unit(sp) * r * self.FRACTION
        return _pack(steer(target - own_p) * found[..., None], obs)


class GuardMarkEdge(_GuardMark):
    """Sits on the zone edge between the centre and the Strike drone it marks."""
    FRACTION = 1.0


class GuardMarkInside(_GuardMark):
    """The same at 0.6 x radius (just inside the zone)."""
    FRACTION = 0.6


class GuardField(_Guard):
    """Pulled to the edge point facing the nearest Strike drone, pushed off team-mates within 1.1 m (1/d^2)."""

    def act(self, obs: Tensor) -> Tensor:
        pg = self.cfg.pad_guards
        own_p = obs[..., _V.own_pos][..., :2]
        r = obs[..., _V.zone_radius, None]
        rp, _, pres = _slots(obs, pg, self.cfg.pad_strikes)
        dist = rp.norm(dim=-1).masked_fill(~pres, float("inf"))                  # [N, G, S]
        near = dist.argmin(-1)                                                   # [N, G]
        found = pres.any(-1)
        rel = torch.gather(rp, 2, near[..., None, None].expand(-1, -1, 1, 2))[:, :, 0]
        edge = _unit(own_p + rel) * r
        pull = steer(edge - own_p) * found[..., None]
        tp, _, tpres = _slots(obs, 0, pg)                                        # team-mates (self absent)
        d = tp.norm(dim=-1).clamp(min=1e-6)
        mag = (1.0 / d ** 2 - 1.0 / FIELD_RANGE_M ** 2) * (tpres & (d < FIELD_RANGE_M))
        push = -(tp / d[..., None] * mag[..., None]).sum(-2)
        a = pull + push
        a = a / a.norm(dim=-1, keepdim=True).clamp(min=1.0)
        return _pack(a, obs)


class GuardMirror(_Guard):
    """Holds a ring at 1.2 x radius towards its marked Strike drone and copies that drone's sideways
    (tangential) speed, scaled by the Guard speed."""
    RING = 1.2

    def act(self, obs: Tensor) -> Tensor:
        sp, sv, found, own_p = self._marked(obs)
        r = obs[..., _V.zone_radius, None]
        e_r = _unit(sp)
        v_t = sv - (sv * e_r).sum(-1, keepdim=True) * e_r
        speed = self.cfg.team_speed_mps("guard")
        a = steer(e_r * r * self.RING - own_p) + v_t / speed
        a = a / a.norm(dim=-1, keepdim=True).clamp(min=1.0)
        return _pack(a * found[..., None], obs)


class _Strike(_Scripted):
    TEAM = "strike"


class StrikeStraight(_Strike):
    """Straight at the zone centre."""

    def act(self, obs: Tensor) -> Tensor:
        return _pack(steer(-obs[..., _V.own_pos][..., :2]), obs)


class StrikeFlank(_Strike):
    """Straight, unless the line to the zone passes within keepout + 0.3 m of the nearest Guard drone ahead:
    then aims at a waypoint keepout + 0.3 m to the side of that drone, on the FAR side of the Guard drone
    from the zone line (the side it is offset to; the left of the heading if it is exactly on the line).
    Only Guard drones ahead on the line and within the clearance count, so a nearer Guard drone off to the
    side or behind never hides a blocking one."""
    MARGIN_M = 0.3

    def act(self, obs: Tensor) -> Tensor:
        own_p = obs[..., _V.own_pos][..., :2]
        to_zone = -own_p
        dist_zone = to_zone.norm(dim=-1, keepdim=True)
        heading = _unit(to_zone)
        side_dir = torch.stack((-heading[..., 1], heading[..., 0]), dim=-1)      # left of heading
        rp, _, pres = _slots(obs, 0, self.cfg.pad_guards)                        # [N, M, G, 2]
        clear_m = self.cfg.rules.keepout_strike_m + self.MARGIN_M
        along = (rp * heading[..., None, :]).sum(-1)                             # [N, M, G]
        off_all = (rp * side_dir[..., None, :]).sum(-1)
        in_way = pres & (along > 0) & (along < dist_zone) & (off_all.abs() < clear_m)
        dist = rp.norm(dim=-1).masked_fill(~in_way, float("inf"))
        near = dist.argmin(-1)                                                   # nearest Guard IN THE WAY
        blocked = in_way.any(-1, keepdim=True)
        g = torch.gather(rp, 2, near[..., None, None].expand(-1, -1, 1, 2))[:, :, 0]     # rel to own
        off = (g * side_dir).sum(-1, keepdim=True)
        sign = torch.where(off >= 0, 1.0, -1.0)
        waypoint = g + side_dir * sign * clear_m
        delta = torch.where(blocked, waypoint, to_zone)
        return _pack(steer(delta), obs)


REGISTRY: dict[str, type] = {
    "guard_mark_edge": GuardMarkEdge,
    "guard_mark_inside": GuardMarkInside,
    "guard_field": GuardField,
    "guard_mirror": GuardMirror,
    "strike_straight": StrikeStraight,
    "strike_flank": StrikeFlank,
    "random": RandomActions,
    "zero": ZeroActions,
}


def make_strategy(spec: str, team: str, cfg: GameCfg, num_games: int, device, seed: int):
    """spec = a REGISTRY name, "package.module:ClassName" (outside code; same constructor arguments:
    team, cfg, num_games, device, seed), or a stand-in run folder holding interface.toml (S2b Task 9: loaded as
    ``opponents.learned.SkrlPolicyStrategy``, deterministic; Guard team only). skrl is imported only for a run folder."""
    if Path(spec).is_dir() and (Path(spec) / "interface.toml").is_file():
        from .learned import SkrlPolicyStrategy        # lazy: the scripted opponents import no training library
        if team != "guard":
            raise ValueError(f"run folder {spec!r} holds a Guard stand-in; it cannot play the {team!r} team")
        return SkrlPolicyStrategy(spec, num_games, device, deterministic=True, seed=seed)
    if ":" in spec:
        mod, _, cls = spec.partition(":")
        klass = getattr(importlib.import_module(mod), cls)
    elif spec in REGISTRY:
        klass = REGISTRY[spec]
    else:
        raise KeyError(f"unknown strategy {spec!r}; known: {sorted(REGISTRY)} or 'package.module:ClassName'")
    return klass(team, cfg, num_games, device, seed)
