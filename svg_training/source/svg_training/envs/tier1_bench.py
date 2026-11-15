"""Tier 1 benchmark environment: batched point-mass drones, a response model, sensing, contact tags.

No game rules and no rewards yet; its speed is what S0 measures. N = games, M = drones per game
(Guard drones first, then Strike drones), R = rays.

Response model (``Tier1BenchCfg.response``): "placeholder" (S0's delay + lag, the default, unchanged bit for bit)
or the path of a parameter TOML such as ``params/real_exploratory_v0.toml`` for ``models/fitted.FittedResponse``
(the commander's real-mode teleop law, then PX4's fitted response; exploratory). ``safety_filter=True`` puts
``core/safety_filter.py`` inside the commander, between drones of the same team only, with
``filter_iterations`` sweeps; it needs the fitted response.
Speeds on the fitted path: each team's command is scaled and its NORM capped before the commander, Strike drones at
``strike_speed_mps`` and Guard drones at ``strike_speed_mps / 1.5`` (STANDARDS §4); ``speed_cap_mps`` is the
placeholder path's cap only. ``strike_speed_mps`` may not exceed the commander's own stick cap (0.5 m/s in the real
config), or the ratio would be lost there.
"""
from dataclasses import dataclass

import torch
from torch import Tensor

from svg_training.core.safety_filter import team_pair_mask
from svg_training.models.fitted import FittedResponse
from svg_training.models.placeholder import PlaceholderResponse
from svg_training.worlds.field import synthetic_field
from svg_training.worlds.sensing import World, cast_rays, line_of_sight, ray_directions

_N_CANDIDATES = 8
_CLEAR_M = 1.0  # spawn clearance from structures and from other drones


@dataclass
class Tier1BenchCfg:
    num_games: int
    guards: int
    strikes: int
    world: str  # "open" | "primitives" | "field"
    n_obstacles: int
    n_rays: int
    line_of_sight: bool
    dt_s: float = 0.05
    contact_m: float = 0.50
    body_radius_m: float = 0.248
    arena_half_m: tuple = (20.0, 20.0)
    height_m: tuple = (0.5, 8.0)
    seed: int = 0
    device: str = "cuda"
    speed_cap_mps: float = 4.0  # Strike drones; Guard drones get speed_cap_mps / 1.5 (STANDARDS §4)
    response: str = "placeholder"  # "placeholder" | path of a parameter TOML (FittedResponse)
    safety_filter: bool = False  # the safety filter, per team, inside the commander (fitted response only)
    filter_iterations: int = 1000  # filter sweeps per tick (core/safety_filter.py default: the parity record's)
    strike_speed_mps: float = 0.5  # fitted path: Strike norm cap; Guard = this / 1.5; <= the commander's stick cap


class Tier1BenchEnv:
    """Batched tier 1 environment. ``step(action [N, M, 4])`` returns a dict with:

    pos_m [N, M, 3] (before respawn), vel_mps [N, M, 3], ranges_m [N, M, R], visible [N, M, M] bool,
    tagged [N, M] bool, touched [N, M] bool, reset_fraction (scalar), bad_spawns (scalar, cumulative
    over the env's life and including the initial placement).
    """

    def __init__(self, cfg: Tier1BenchCfg):
        self.cfg = cfg
        self.N, self.G, self.S = cfg.num_games, cfg.guards, cfg.strikes
        self.M = cfg.guards + cfg.strikes
        dev = cfg.device
        self.gen = torch.Generator(device=dev).manual_seed(cfg.seed)
        cap = cfg.speed_cap_mps
        self._cap_mps = torch.tensor([cap / 1.5] * self.G + [cap] * self.S, device=dev)[None, :, None]  # [1, M, 1]
        self._fitted = cfg.response != "placeholder"
        if not self._fitted:
            if cfg.safety_filter:
                raise ValueError("safety_filter needs the fitted response: set response to a parameter TOML path")
            self.response = PlaceholderResponse(self.N, self.M, dt_s=cfg.dt_s, speed_cap_mps=self._cap_mps, device=dev)
        else:
            self.response = FittedResponse(self.N, self.M, cfg.response, dt_s=cfg.dt_s, device=dev,
                                           safety_filter=cfg.safety_filter,
                                           pair_mask=team_pair_mask(self.G, self.S, device=dev),
                                           filter_iterations=cfg.filter_iterations)
            stick_cap = self.response.commander_params.teleop_max_speed_mps
            if cfg.strike_speed_mps > stick_cap:
                raise ValueError(f"strike_speed_mps {cfg.strike_speed_mps} exceeds the commander's stick cap "
                                 f"{stick_cap} m/s: the Strike/Guard speed ratio would be lost")
            s_cap = cfg.strike_speed_mps
            self._team_cap_mps = torch.tensor([s_cap / 1.5] * self.G + [s_cap] * self.S, device=dev)[None, :, None]
        self._self_inf = torch.diag(torch.full((self.M,), float("inf"), device=dev))[None, :, None, :]  # [1, M, 1, M]
        self._lo_m = torch.tensor([-cfg.arena_half_m[0], -cfg.arena_half_m[1], cfg.height_m[0]], device=dev)
        self._hi_m = torch.tensor([cfg.arena_half_m[0], cfg.arena_half_m[1], cfg.height_m[1]], device=dev)
        self._dirs = ray_directions(cfg.n_rays, device=dev) if cfg.n_rays > 0 else None
        self.world = self._build_world()
        self.bad_spawns = torch.zeros((), dtype=torch.long, device=dev)  # cumulative, including initial placement
        self.pos_m = torch.full((self.N, self.M, 3), 1e6, device=dev)  # sentinel: not yet placed
        self.vel_mps = torch.zeros(self.N, self.M, 3, device=dev)
        for m in range(self.M):  # one drone index at a time (small fixed count), all games at once
            mask = torch.zeros(self.N, self.M, dtype=torch.bool, device=dev)
            mask[:, m] = True
            self._spawn(mask)
        if self._fitted:
            self.response.reset(torch.ones(self.N, self.M, dtype=torch.bool, device=dev), self.pos_m)

    def _uniform(self, *shape) -> Tensor:
        return torch.rand(*shape, generator=self.gen, device=self.cfg.device)

    def _build_world(self) -> World:
        cfg, dev, n = self.cfg, self.cfg.device, self.N
        n_obs = 0 if cfg.world == "open" else cfg.n_obstacles
        nb, nc = n_obs - n_obs // 2, n_obs // 2
        ax, ay = cfg.arena_half_m
        bhalf = torch.stack((0.5 + 2.5 * self._uniform(n, nb), 0.5 + 2.5 * self._uniform(n, nb),
                             0.5 + 2.5 * self._uniform(n, nb)), dim=-1)
        bxy = (self._uniform(n, nb, 2) * 2 - 1) * torch.tensor([ax, ay], device=dev)
        bcen = torch.cat((bxy, bhalf[..., 2:]), dim=-1)  # boxes stand on the floor z = 0
        crad = 0.2 + 0.8 * self._uniform(n, nc)
        chgt = 2.0 + 6.0 * self._uniform(n, nc)
        cxy = (self._uniform(n, nc, 2) * 2 - 1) * torch.tensor([ax, ay], device=dev)
        cbase = torch.cat((cxy, torch.zeros(n, nc, 1, device=dev)), dim=-1)
        field = synthetic_field(device=dev) if cfg.world == "field" else None
        return World(field, bcen, bhalf, cbase, crad, chgt)

    def _spawn(self, mask: Tensor) -> None:
        """Place the drones where mask [N, M] is True: first of 8 uniform candidates that is clear."""
        n, m, k = self.N, self.M, _N_CANDIDATES
        cand = self._lo_m + self._uniform(n, m, k, 3) * (self._hi_m - self._lo_m)  # [N, M, K, 3]
        clear = self.world.sdf(cand.reshape(n, m * k, 3)).reshape(n, m, k) > _CLEAR_M
        # broadcast difference ([N, M*K, M, 3] temporary), not torch.cdist: its exact-distance kernel is slow
        d = (cand.reshape(n, m * k, 1, 3) - self.pos_m[:, None]).norm(dim=-1).reshape(n, m, k, m)  # [N, M, K, M]
        d = d + self._self_inf  # ignore itself
        valid = clear & (d.amin(dim=-1) > _CLEAR_M)
        has = valid.any(dim=-1)
        idx = torch.where(has, valid.to(torch.uint8).argmax(dim=-1), torch.full_like(has, k - 1, dtype=torch.long))
        chosen = cand.gather(2, idx[:, :, None, None].expand(n, m, 1, 3))[:, :, 0]
        self.pos_m = torch.where(mask[..., None], chosen, self.pos_m)
        self.bad_spawns = self.bad_spawns + (mask & ~has).sum()

    def step(self, action: Tensor) -> dict:
        """action [N, M, 4] (vx, vy, vz in [-1, 1] of the speed cap; yaw rate ignored in S0)."""
        cfg = self.cfg
        if self._fitted:  # the model integrates the position itself, from the env's current one
            cap = self._team_cap_mps  # [1, M, 1]: per-team norm cap before the commander (STANDARDS §4)
            cmd = action[..., :3].clamp(-1.0, 1.0) * cap
            cmd = cmd * (cap / cmd.norm(dim=-1, keepdim=True).clamp(min=1e-9)).clamp(max=1.0)
            self.vel_mps = self.response.step(cmd, self.pos_m)
            self.pos_m = self.response.pos_m
        else:
            cmd = action[..., :3].clamp(-1.0, 1.0) * self._cap_mps
            self.vel_mps = self.response.step(cmd)
            self.pos_m = self.pos_m + self.vel_mps * cfg.dt_s
        pos = self.pos_m

        g, s = pos[:, :self.G], pos[:, self.G:]
        close = (g[:, :, None, :] - s[:, None, :, :]).norm(dim=-1) < cfg.contact_m  # [N, G, S]
        tagged = torch.cat((close.any(dim=2), close.any(dim=1)), dim=1)
        outside = ((pos < self._lo_m) | (pos > self._hi_m)).any(dim=-1)
        touched = (self.world.sdf(pos) < cfg.body_radius_m) | outside

        if self._dirs is not None:
            ranges = cast_rays(self.world, pos, self._dirs)
        else:
            ranges = pos.new_zeros(self.N, self.M, 0)
        if cfg.line_of_sight:
            visible = line_of_sight(self.world, pos)
        else:
            visible = torch.ones(self.N, self.M, self.M, dtype=torch.bool, device=pos.device)

        out = {"pos_m": pos.clone(), "vel_mps": self.vel_mps.clone(), "ranges_m": ranges, "visible": visible,
               "tagged": tagged, "touched": touched}
        respawn = tagged | touched
        self._spawn(respawn)
        if self._fitted:
            self.response.reset(respawn, self.pos_m)
        else:
            self.response.reset(respawn)
        self.vel_mps = self.response.vel_mps
        out["reset_fraction"] = respawn.float().mean()
        out["bad_spawns"] = self.bad_spawns
        return out
