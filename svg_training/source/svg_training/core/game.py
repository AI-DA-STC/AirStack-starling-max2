"""S2 batched game core: partner rules without the pair rule (Task 3 fills ``_apply_pair_rules``).

Everything in ``step`` is a batched tensor operation over all games: no loop over games, no host reads.
Drones are indexed Guard drones first (0..G-1), then Strike drones (G..M-1). The world is planar (D2):
z is held at ``start_height_m``."""
from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor

from .arena import BANDS, GUARD, STRIKE, Arenas, draw_arenas, draw_starts  # noqa: F401  (re-exported)
from .game_config import TICK_S, GameCfg
from .observations import build_obs, build_state
from .rewards import GUARD_WIN, RUNNING, STRIKE_WIN, team_rewards
from .scenarios import SCENARIOS, Scenario, scenario_arenas  # noqa: F401  (re-exported)

PARK_M = 1.0e3     # where a drone that is out is parked (x and y)


@dataclass
class StepOut:
    """Result of one step. obs after auto-reset of the games that ended; reward, outcome, end_step and info
    describe the step just taken. info: band [N], closest_cross_m [N] (inf if no live opposite pair),
    closest_team_m [N] (inf if no live same-team pair), rule_breach [N] bool, filter_corrected [N, M] bool,
    final_alive [N, M] bool (who was in the game at the end of this step, before any reset),
    start_miss [N] bool (True for a game that auto-reset this step whose starts could not meet the spacing /
    keep-out; False elsewhere)."""
    obs: dict[str, Tensor]
    reward: dict[str, Tensor]
    done: Tensor
    outcome: Tensor
    end_step: Tensor
    info: dict[str, Tensor]


class SvgGame:
    """Batched Strike vs Guard game. See the module docstring and the S2 plan, Task 2."""

    def __init__(self, cfg: GameCfg, num_games: int, guards: int, strikes: int, device: str = "cuda",
                 seed: int = 0, band: int | None = None, scenario: Scenario | None = None):
        if cfg.preset not in ("partner", "contact"):
            raise ValueError(f"preset must be 'partner' or 'contact', got {cfg.preset!r}")
        if cfg.arena.walls not in ("keep_in", "leave"):
            raise ValueError(f"arena.walls must be 'keep_in' or 'leave', got {cfg.arena.walls!r}")
        if cfg.starts.mode not in ("rings", "anywhere"):
            raise ValueError(f"starts.mode must be 'rings' or 'anywhere', got {cfg.starts.mode!r}")
        if cfg.rules.win_steps_in_zone != 1:
            raise ValueError("only win_steps_in_zone = 1 is built (one step inside the zone wins)")
        if guards < 1 or strikes < 1:
            raise ValueError("a game needs at least one Guard and one Strike drone")
        if scenario is not None and len(scenario.start_m) != guards + strikes:
            raise ValueError(f"scenario {scenario.name!r} places {len(scenario.start_m)} drones, "
                             f"game has {guards + strikes}")
        self.cfg, self.num_games, self.num_envs = cfg, num_games, num_games
        self.guards, self.strikes, self.M = guards, strikes, guards + strikes
        self.device, self.scenario, self.band = device, scenario, band
        self.ticks = cfg.game_ticks()
        self.gen = torch.Generator(device=device)
        self.gen.manual_seed(seed)
        n, m, dev = num_games, self.M, device
        speed = [cfg.team_speed_mps(GUARD)] * guards + [cfg.team_speed_mps(STRIKE)] * strikes
        self._speed_mps = torch.tensor(speed, device=dev)[None, :, None]            # [1, M, 1]
        self._is_strike = (torch.arange(m, device=dev) >= guards)[None, :]           # [1, M]
        self._cross = self._is_strike[:, :, None] != self._is_strike[:, None, :]     # [1, M, M]
        self._same = ~self._cross & ~torch.eye(m, dtype=torch.bool, device=dev)[None]
        self._keepout_min = min(cfg.rules.keepout_guard_m, cfg.rules.keepout_strike_m)
        if scenario is not None:
            self._sc_arenas = scenario_arenas(cfg.arena, scenario, n, dev)
            xy = torch.tensor(scenario.start_m, device=dev)
            z = torch.full((m, 1), cfg.arena.start_height_m, device=dev)
            self._sc_pos = torch.cat((xy, z), dim=-1)[None].expand(n, m, 3).contiguous()
        self.pos_m = torch.zeros(n, m, 3, device=dev)
        self.vel_mps = torch.zeros(n, m, 3, device=dev)
        self.yaw = torch.zeros(n, m, device=dev)
        self.alive = torch.ones(n, m, dtype=torch.bool, device=dev)
        self.steps = torch.zeros(n, dtype=torch.long, device=dev)
        self.dropout_step = torch.full((n, m), -1, dtype=torch.long, device=dev)
        self.arenas = self._draw_arenas()
        self.start_miss = torch.zeros(n, dtype=torch.bool, device=dev)
        self._phi = torch.zeros(n, device=dev)
        self.reset()

    # ------------------------------------------------------------------ helpers
    def _draw_arenas(self) -> Arenas:
        if self.scenario is not None:
            return self._sc_arenas
        return draw_arenas(self.cfg.arena, self.num_games, self.gen, self.device, self.band)

    def _potential(self, pos_m: Tensor, alive: Tensor, ar: Arenas) -> Tensor:
        """[N] nearest live Strike drone's distance to the zone edge / arena half; inf if none."""
        d = (pos_m[..., :2] - ar.zone_centre_m[:, None, :]).norm(dim=-1)
        edge = (d - ar.zone_radius_m[:, None]).clamp(min=0.0) / ar.half_m[:, None]
        live = alive & self._is_strike
        return torch.where(live, edge, torch.full_like(edge, float("inf"))).amin(dim=1)

    def _new_games(self, mask: Tensor) -> None:
        """Start a new game wherever mask [N] bool: new arena, starts, drop-out draw (scenario: same layout)."""
        n, m, dev = self.num_games, self.M, self.device
        mk = mask[:, None]
        ar = self._draw_arenas()
        if self.scenario is not None:
            pos, miss = self._sc_pos, torch.zeros(n, dtype=torch.bool, device=dev)
        else:
            pos, miss = draw_starts(self.cfg, ar, self.guards, self.strikes, self.gen, return_miss=True)
        # drop-out: in a fraction of games, one random drone (any team) leaves at one random step
        hit = torch.rand(n, generator=self.gen, device=dev) < self.cfg.dropout_fraction
        who = (torch.rand(n, generator=self.gen, device=dev) * m).floor().long().clamp(max=m - 1)
        when = (torch.rand(n, generator=self.gen, device=dev) * self.ticks).floor().long().clamp(max=self.ticks - 1) + 1
        pick = hit[:, None] & (torch.arange(m, device=dev)[None, :] == who[:, None])
        drop = torch.where(pick, when[:, None].expand(n, m), torch.full((n, m), -1, dtype=torch.long, device=dev))
        self.start_miss = torch.where(mask, miss, torch.zeros_like(miss))
        self.arenas = self.arenas.merge(ar, mask)
        self.pos_m = torch.where(mk[..., None], pos, self.pos_m)
        self.vel_mps = torch.where(mk[..., None], torch.zeros_like(self.vel_mps), self.vel_mps)
        self.yaw = torch.where(mk, torch.zeros_like(self.yaw), self.yaw)
        self.alive = torch.where(mk, torch.ones_like(self.alive), self.alive)
        self.steps = torch.where(mask, torch.zeros_like(self.steps), self.steps)
        self.dropout_step = torch.where(mk, drop, self.dropout_step)
        phi = self._potential(self.pos_m, self.alive, self.arenas)
        self._phi = torch.where(mask, torch.where(torch.isfinite(phi), phi, torch.zeros_like(phi)), self._phi)

    def _time_left_s(self) -> Tensor:
        return (self.ticks - self.steps).to(torch.float32) * TICK_S

    def _obs(self) -> dict[str, Tensor]:
        return build_obs(self.cfg, self.pos_m, self.vel_mps, self.yaw, self.alive, self.arenas,
                         self._time_left_s(), self.guards, self.strikes)

    def _apply_pair_rules(self, pos_prev_m: Tensor, pos_m: Tensor, alive: Tensor) -> tuple[Tensor, Tensor]:
        """Hook for Task 3 (partner push-apart, contact tags, Starling layer). Takes the positions before and
        after the move ([N, M, 3] each) and who is in the game ([N, M]); returns the corrected positions
        [N, M, 3] and filter_corrected [N, M] bool. Here: no pair rule."""
        return pos_m, torch.zeros_like(alive)

    # ------------------------------------------------------------------ public
    def reset(self, seed: int | None = None) -> dict[str, Tensor]:
        """Start every game afresh; reseed the generator if seed is given. Returns the observations."""
        if seed is not None:
            self.gen.manual_seed(seed)
        self._new_games(torch.ones(self.num_games, dtype=torch.bool, device=self.device))
        return self._obs()

    def state(self) -> Tensor:
        """[N, STATE_DIM] central state for critics."""
        return build_state(self.cfg, self.pos_m, self.vel_mps, self.alive, self.arenas, self._time_left_s(),
                           self.guards, self.strikes)

    def schedule_dropout(self, drone: Tensor, at_step: Tensor) -> None:
        """drone [N] long (index, Guard drones first; -1 = none), at_step [N] long (-1 = none): that drone is
        out at the end of step at_step of the current game. Cleared when the game auto-resets."""
        drone, at_step = drone.to(self.device), at_step.to(self.device)
        sel = (torch.arange(self.M, device=self.device)[None, :] == drone[:, None]) & (at_step[:, None] >= 0)
        self.dropout_step = torch.where(sel, at_step[:, None].expand_as(self.dropout_step), self.dropout_step)

    def step(self, actions: dict[str, Tensor]) -> StepOut:
        """actions {"guard": [N, G, 4], "strike": [N, S, 4]} in [-1, 1]: vx, vy, vz (ignored), yaw rate."""
        cfg, g = self.cfg, self.guards
        a = torch.cat((actions[GUARD], actions[STRIKE]), dim=1).clamp(-1.0, 1.0)     # [N, M, 4]
        alive_prev = self.alive
        # per-team norm cap, then move (planar, z held)
        v = a[..., :2]
        v = v / v.norm(dim=-1, keepdim=True).clamp(min=1.0) * self._speed_mps
        v = v * alive_prev[..., None]
        pos_prev = self.pos_m
        xy = pos_prev[..., :2] + v * TICK_S
        pos = torch.cat((xy, torch.full_like(xy[..., :1], cfg.arena.start_height_m)), dim=-1)
        self.yaw = self.yaw + a[..., 3] * cfg.yaw_rate_max_rad_s * TICK_S * alive_prev
        pos, corrected = self._apply_pair_rules(pos_prev, pos, alive_prev)
        # walls
        lim = (self.arenas.half_m - cfg.arena.wall_margin_m)[:, None, None]
        alive = alive_prev
        if cfg.arena.walls == "keep_in":
            xy = torch.maximum(torch.minimum(pos[..., :2], lim), -lim)
            pos = torch.cat((xy, pos[..., 2:]), dim=-1)
        else:
            alive = alive & ~(pos[..., :2].abs() >= lim).any(dim=-1)
        # scheduled drop-outs
        steps_new = self.steps + 1
        alive = alive & ~(self.dropout_step == steps_new[:, None])
        # outcome: reach the zone first, then time-out, then no Strike drone left
        d = (pos[..., :2] - self.arenas.zone_centre_m[:, None, :]).norm(dim=-1)
        strike_win = (alive & self._is_strike & (d <= self.arenas.zone_radius_m[:, None])).any(dim=1)
        guard_win = (steps_new >= self.ticks) | ~(alive & self._is_strike).any(dim=1)
        outcome = torch.where(strike_win, STRIKE_WIN, torch.where(guard_win, GUARD_WIN, RUNNING)).to(torch.int8)
        done = outcome > 0
        # park drones that are out; velocity from the realised move
        pos = torch.where(alive[..., None], pos, torch.full_like(pos, PARK_M))
        both = (alive & alive_prev)[..., None]
        vel = torch.cat(((pos[..., :2] - pos_prev[..., :2]) / TICK_S, torch.zeros_like(pos[..., :1])), dim=-1)
        vel = torch.where(both, vel, torch.zeros_like(vel))
        self.pos_m, self.vel_mps, self.alive, self.steps = pos, vel, alive, steps_new
        # info and rewards (about the game that just played)
        dist = (pos[:, :, None, :2] - pos[:, None, :, :2]).norm(dim=-1)              # [N, M, M]
        live2 = alive[:, :, None] & alive[:, None, :]
        inf = torch.full_like(dist, float("inf"))
        closest_cross = torch.where(live2 & self._cross, dist, inf).amin(dim=(1, 2))
        closest_team = torch.where(live2 & self._same, dist, inf).amin(dim=(1, 2))
        phi_now = self._potential(pos, alive, self.arenas)
        phi_now = torch.where(torch.isfinite(phi_now), phi_now, self._phi)
        reward = team_rewards(cfg.rewards, outcome, self._phi, phi_now, g, self.strikes)
        info = {"band": self.arenas.band, "closest_cross_m": closest_cross, "closest_team_m": closest_team,
                "rule_breach": closest_cross < self._keepout_min - 1e-6, "filter_corrected": corrected,
                "final_alive": alive.clone()}
        end_step = torch.where(done, steps_new, torch.zeros_like(steps_new))
        self._phi = phi_now
        self._new_games(done)
        info["start_miss"] = self.start_miss
        return StepOut(self._obs(), reward, done, outcome, end_step, info)
