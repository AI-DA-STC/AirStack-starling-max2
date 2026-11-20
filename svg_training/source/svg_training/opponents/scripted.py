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


# ------------------------------------------------------------------ STE task L0.10: the study's players
# Added at the end of the module so that the line numbers cited elsewhere (PLAN.md F5, the NUS port plans) still hold.
import math  # noqa: E402  (imported here, not at the top, so that the line numbers cited above still hold)

# Behaviour constants of hand-written players, not tuned on results: PROPOSED, LEAD CALL 21 Nov 2026; listed with the same
# values in ste_learning/GAME_SPEC.md "Scripted player settings" (tests/test_scripted_study.py keeps the two equal).
PARK_RING_M = 0.8        # guard_parked_ring: smallest ring, PLAN section 2 F1; equals configs/ste_game.toml players.guard_park_ring_m
PARK_RING_SPACING_MARGIN_M = 0.05   # guard_parked_ring: neighbours at least the filter distance + this apart (chord rule)
BAND_INSET_M = 0.1       # strike_high / strike_low: aim this far inside the height band edge (the band's walls hold or remove)
STAND_OFF_M = 1.0        # sacrifice / converge: circle and gather this far outside the zone edge (capped at the keep-in box)
RADIAL_RAMP_M = 1.0      # while circling: radial correction towards the stand-off circle reaches full speed this far off
CIRCLE_UNTIL_RAD = 0.5   # converge: circle round the zone while farther than this from the assigned bearing, then steer to it
ENTRY_HALF_ANGLE_DEG = 30.0   # sacrifice: within this of the entry bearing, a Strike flies straight in
ENTRY_HALF_ANGLE_RAD = ENTRY_HALF_ANGLE_DEG * torch.pi / 180
GATHER_ANGLE_RAD = 0.1   # converge: a Strike is in place within this of its bearing; the run-in starts when all are
RUN_IN_COMMIT_M = 0.3    # converge: once a live Strike is this far inside the stand-off circle, the run-in goes on


def _team_slots(obs: Tensor, first: int) -> tuple[Tensor, Tensor]:
    """The team's own drones as seen by each of them: (position rel zone [N, K, K, 2], live [N, K, K] bool), K =
    obs.shape[1], team slots from ``first``; entry [n, i, k] is drone k as drone i sees it (k = i: itself, live if i is)."""
    k = obs.shape[1]
    rp, _, pres = _slots(obs, first, k)
    own_p = obs[..., _V.own_pos][..., :2]
    eye = torch.eye(k, dtype=torch.bool, device=obs.device)
    alive = obs[..., _V.alive] > 0.5                                             # [N, K]
    pos = own_p[:, :, None, :] + rp * (~eye)[None, :, :, None]
    return pos, pres | (eye[None] & alive[:, :, None])


def _wrap(a: Tensor) -> Tensor:
    """Angle(s) to (-pi, pi]."""
    return torch.atan2(a.sin(), a.cos())


def _stand_off_m(obs: Tensor, wall_margin_m: float) -> Tensor:
    """[N, K, 1] stand-off circle radius: zone radius + STAND_OFF_M, capped so the circle stays inside the keep-in box
    (the arena half, from the observation, less the wall margin, less the zone's offset from the arena centre)."""
    r = obs[..., _V.zone_radius, None]
    room = obs[..., _V.arena_half, None] - wall_margin_m - obs[..., _V.zone_centre].abs().amax(-1, keepdim=True)
    return torch.minimum(r + STAND_OFF_M, room)


def _circle(own_p: Tensor, radius_m: Tensor, direction: Tensor) -> Tensor:
    """Move round the zone centre in ``direction`` [N, K] (+1 anticlockwise, -1 clockwise) while easing onto the circle
    ``radius_m`` [N, K, 1]. own_p [N, K, 2] (rel zone) -> xy action [N, K, 2], norm <= 1."""
    rho = own_p.norm(dim=-1, keepdim=True)
    e_r = _unit(own_p)
    e_t = torch.stack((-e_r[..., 1], e_r[..., 0]), dim=-1)
    radial = ((radius_m - rho) / RADIAL_RAMP_M).clamp(-1.0, 1.0)
    a = e_t * direction[..., None] + e_r * radial
    return a / a.norm(dim=-1, keepdim=True).clamp(min=1.0)


class GuardParkedCentre(_Guard):
    """Guard 0 flies to the zone centre and stops there; every other Guard holds its start position (zero command), so
    no Guard moves once settled (LEAD CALL 21 Nov 2026). Ignores the Strike drones (study task L0.10). On the Starling
    layer the filter may nudge a Guard while Guard 0 settles; after that nothing moves."""

    def act(self, obs: Tensor) -> Tensor:
        first = (torch.arange(obs.shape[1], device=obs.device) == 0)[None, :, None]
        return _pack(steer(-obs[..., _V.own_pos][..., :2]) * first, obs)


class GuardParkedRing(_Guard):
    """Guard i flies to its station on a ring round the zone centre, at bearing 2 pi i / G (G = team size, the stations
    fixed by index: no closing up when a team-mate is lost) and stops there; ignores the Strike drones. Ring radius
    (LEAD CALL 21 Nov 2026) = max(RING_M, chord rule): neighbours at least the filter distance (``rules.keepout_guard_m``)
    + PARK_RING_SPACING_MARGIN_M apart, r >= (d + margin) / (2 sin(pi / G)); 0.8 m up to 3 Guards, 0.98 m for 5."""
    RING_M = PARK_RING_M

    def ring_radius_m(self, guards: int) -> float:
        """Ring radius (m) for a team of ``guards`` Guard drones (Python float, fixed per team size)."""
        if guards < 2:
            return self.RING_M
        need_m = (self.cfg.rules.keepout_guard_m + PARK_RING_SPACING_MARGIN_M) / (2 * math.sin(math.pi / guards))
        return max(self.RING_M, need_m)

    def act(self, obs: Tensor) -> Tensor:
        g = obs.shape[1]
        ang = torch.arange(g, device=obs.device, dtype=obs.dtype) * (2 * torch.pi / g)
        station = self.ring_radius_m(g) * torch.stack((ang.cos(), ang.sin()), dim=-1)[None]          # [1, G, 2]
        return _pack(steer(station - obs[..., _V.own_pos][..., :2]), obs)


class _StrikeHeight(_Strike):
    """Climbs (TOP) or descends to BAND_INSET_M inside the height band edge first, then flies straight at the zone centre
    at that height: the vertical command has priority, so the drone is at its height before it closes in (the 3-D speed
    cap would otherwise trade climb for approach). On the pure path heights are held, so it plays as strike_straight."""
    TOP = True

    def __init__(self, team: str, cfg: GameCfg, num_games: int, device, seed: int = 0):
        super().__init__(team, cfg, num_games, device, seed)
        lo, hi = cfg.arena.height_band_m
        self.target_z_m = hi - BAND_INSET_M if self.TOP else lo + BAND_INSET_M
        self.three_d = cfg.starling.enabled is True       # a Python bool from the config, read once

    def act(self, obs: Tensor) -> Tensor:
        xy = steer(-obs[..., _V.own_pos][..., :2])
        if not self.three_d:
            return _pack(xy, obs)
        vz = ((self.target_z_m - obs[..., 2]) / STEER_RAMP_M).clamp(-1.0, 1.0)            # [N, S]
        xy = xy * (1.0 - vz ** 2).clamp(min=0.0).sqrt()[..., None]
        a = torch.cat((xy, vz[..., None], torch.zeros_like(vz[..., None])), dim=-1)
        return a * obs[..., _V.alive:_V.alive + 1]


class StrikeHigh(_StrikeHeight):
    """Enters at the top of the height band (see _StrikeHeight)."""
    TOP = True


class StrikeLow(_StrikeHeight):
    """Enters at the bottom of the height band (see _StrikeHeight)."""
    TOP = False


class StrikeSacrifice(_Strike):
    """Strike 0 (by index, fixed: never re-elected) flies at the live Guard drone nearest to it, to draw it. The others
    enter opposite the bearing of that drawn Guard drone, the gap it opens (LEAD CALL 21 Nov 2026): while their bearing is
    more than ENTRY_HALF_ANGLE_RAD from that entry bearing, they circle the zone on the stand-off circle the shorter way
    round; within it they fly straight in. With no live Guard drone, or the drawn one exactly at the zone centre (no
    bearing), the entry bearing is opposite Strike 0. When Strike 0 is out, when a Strike drone is alone, or (for Strike
    0) when no Guard drone is live, it flies straight in."""

    def act(self, obs: Tensor) -> Tensor:
        own_p = obs[..., _V.own_pos][..., :2]
        straight = steer(-own_p)
        mates, live = _team_slots(obs, self.cfg.pad_guards)                          # [N, S, S, 2], [N, S, S]
        decoy_p, decoy_live = mates[:, :, 0], live[:, :, 0]                           # Strike 0 as each sees it
        others_live = live.sum(-1) >= 2
        # Strike 0: at the nearest live Guard drone
        gp, _, gpres = _slots(obs, 0, self.cfg.pad_guards)                            # rel own [N, S, G, 2]
        dist = gp.norm(dim=-1).masked_fill(~gpres, float("inf"))
        near = dist.argmin(-1)
        to_guard = torch.gather(gp, 2, near[..., None, None].expand(-1, -1, 1, 2))[:, :, 0]
        any_guard = gpres.any(-1)                                                     # [N, S]
        decoy_a = torch.where(any_guard[..., None], steer(to_guard), straight)
        # the others: the drawn Guard (nearest Strike 0, as each sees it) and the entry bearing opposite it
        guard_p = own_p[:, :, None, :] + gp                                           # rel zone
        to_decoy = (guard_p - decoy_p[:, :, None, :]).norm(dim=-1).masked_fill(~gpres, float("inf"))
        drawn = torch.gather(guard_p, 2, to_decoy.argmin(-1)[..., None, None].expand(-1, -1, 1, 2))[:, :, 0]
        has_bearing = any_guard & (drawn.norm(dim=-1) > 1e-6)
        away = torch.where(has_bearing[..., None], drawn, decoy_p)
        far = torch.atan2(-away[..., 1], -away[..., 0])
        diff = _wrap(far - torch.atan2(own_p[..., 1], own_p[..., 0]))
        direction = torch.where(diff >= 0, 1.0, -1.0)
        go_in = diff.abs() <= ENTRY_HALF_ANGLE_RAD
        around = _circle(own_p, _stand_off_m(obs, self.cfg.arena.wall_margin_m), direction)
        rest_a = torch.where(go_in[..., None], straight, around)
        is_decoy = (torch.arange(obs.shape[1], device=obs.device) == 0)[None, :, None]
        a = torch.where(is_decoy, decoy_a, rest_a)
        a = torch.where((decoy_live & others_live)[..., None], a, straight)
        return _pack(a, obs)


class StrikeConverge(_Strike):
    """All live Strike drones arrive together from spread bearings. The lowest-index live Strike drone sets the reference
    bearing; the others keep their order round the zone (anticlockwise from it) and are given the bearings reference +
    2 pi k / S_live, k = their place in that order (so no two cross on the way). Each goes to its bearing on the stand-off
    circle, circling round while more than CIRCLE_UNTIL_RAD away. The run-in starts when every live Strike drone is within
    GATHER_ANGLE_RAD of its bearing (bearings only, so a drone pushed off the circle by a Guard drone does not stall the
    team); each then flies straight in at the speed fraction (own distance to the zone edge) / (the farthest one's), so
    all reach the edge together. Once any live Strike drone is RUN_IN_COMMIT_M inside the stand-off circle the run-in
    goes on, even if a loss changes the bearings wanted (the survivors keep flying in, at the same pace rule). A Strike
    drone that is alone flies straight in. Accepted as built (LEAD CALL 21 Nov 2026)."""

    def stage_radius_m(self, obs: Tensor) -> Tensor:
        """[N, S, 1] the stand-off circle the Strike drones gather on."""
        return _stand_off_m(obs, self.cfg.arena.wall_margin_m)

    def act(self, obs: Tensor) -> Tensor:
        own_p = obs[..., _V.own_pos][..., :2]
        straight = steer(-own_p)
        mates, live = _team_slots(obs, self.cfg.pad_guards)                          # [N, S, S, 2], [N, S, S]
        s = obs.shape[1]
        n_live = live.sum(-1)                                                        # [N, S]
        idx = torch.arange(s, device=obs.device)
        ref = torch.where(live, idx, s).amin(-1).clamp(max=s - 1)                    # lowest live index
        ref_p = torch.gather(mates, 2, ref[..., None, None].expand(-1, -1, 1, 2))[:, :, 0]     # [N, S, 2]
        rp = ref_p[:, :, None, :]
        cross = rp[..., 0] * mates[..., 1] - rp[..., 1] * mates[..., 0]
        dot = (rp * mates).sum(-1)
        offset = torch.atan2(cross, dot)                                             # [N, S, S], 0 for the reference
        offset = torch.where(offset < 0, offset + 2 * torch.pi, offset)
        offset = offset.masked_fill(~live, float("inf"))
        order = offset.argsort(-1)                                                   # live first, in angular order
        rank = order.argsort(-1).to(obs.dtype)                                       # place of each drone in that order
        target = rank * (2 * torch.pi) / n_live.clamp(min=1)[..., None].to(obs.dtype)            # offsets wanted
        err = _wrap(target - offset.masked_fill(~live, 0.0))                          # [N, S, S]
        radius = self.stage_radius_m(obs)                                            # [N, S, 1]
        own = idx[None, :, None] == idx[None, None, :]                               # [1, S, S] the diagonal
        rho = mates.norm(dim=-1)                                                     # [N, S, S]
        committed = (live & (rho < radius - RUN_IN_COMMIT_M)).any(-1)                # [N, S]
        go = ((err.abs() <= GATHER_ANGLE_RAD) | ~live).all(-1) | committed           # [N, S]
        to_edge = (rho - obs[..., _V.zone_radius, None]).clamp(min=0.0) * live         # [N, S, S]
        own_edge = (to_edge * own).sum(-1)
        pace = (own_edge / to_edge.amax(-1).clamp(min=1e-9)).clamp(max=1.0)          # [N, S], 1 for the farthest
        # own move towards the own bearing: circle while far, then steer to the point on the circle
        own_offset = (offset.masked_fill(~live, 0.0) * own).sum(-1)
        own_target = (target * own).sum(-1)
        ref_bearing = torch.atan2(ref_p[..., 1], ref_p[..., 0])
        want = ref_bearing + own_target                                              # [N, S] bearing wanted
        diff = own_target - own_offset                                               # signed, inside [-2 pi, 2 pi]
        direction = torch.where(diff >= 0, 1.0, -1.0)
        point = radius * torch.stack((want.cos(), want.sin()), dim=-1)
        place_a = torch.where((_wrap(diff).abs() > CIRCLE_UNTIL_RAD)[..., None],
                              _circle(own_p, radius, direction), steer(point - own_p))
        a = torch.where(go[..., None], _unit(-own_p) * pace[..., None], place_a)
        a = torch.where((n_live >= 2)[..., None], a, straight)
        return _pack(a, obs)


REGISTRY.update({
    "guard_parked_centre": GuardParkedCentre,
    "guard_parked_ring": GuardParkedRing,
    "strike_high": StrikeHigh,
    "strike_low": StrikeLow,
    "strike_sacrifice": StrikeSacrifice,
    "strike_converge": StrikeConverge,
})
