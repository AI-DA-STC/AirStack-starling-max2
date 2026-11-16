"""S2 batched game core: partner rules (push-apart) and the contact-tag side quest.

Everything in ``step`` is a batched tensor operation over all games: no loop over games, no host reads.
Drones are indexed Guard drones first (0..G-1), then Strike drones (G..M-1). The pure partner rules are planar
(D2): z is held at ``start_height_m``. With ``[starling_layer] enabled`` (core/starling_layer.py, Task 4) drones
move in 3-D through the commander copy, the safety filter and the fitted PX4 model (exploratory); the push-apart
rule is then off (D3) and a breach of the keep-out is reported in ``info["rule_breach"]``. With ``[starling_layer]
backend = "physics"`` (S2b, core/physics_layer.py) the same commander copy and filter fly rigid-body Starlings under
PX4 1.14's cascade in a world given as ``SvgGame(..., world=...)``; ``motion`` names the path ("pure", "starling"
or "physics/<world label>") and ``info["upset"]`` flags games where a live drone was upset (D10).

Order inside one step: move (pure rule + push-apart, or the Starling layer), walls (keep_in clamps, leave takes
the drone out), contact tags (contact preset), scheduled drop-outs, then the zone test. Tie rule: tags come before
the zone test, so a Strike drone tagged on the step it enters the zone does not score."""
from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor

from svg_training.models.rigid_body import RigidBodyWorld

from .arena import BANDS, GUARD, STRIKE, Arenas, draw_arenas, draw_starts  # noqa: F401  (re-exported)
from .game_config import BACKENDS, TICK_S, GameCfg
from .observations import build_obs, build_state
from .pair_rules import contact_tags, push_apart
from .physics_layer import PhysicsLayer
from .rewards import GUARD_WIN, RUNNING, STRIKE_WIN, team_rewards
from .scenarios import SCENARIOS, Scenario, scenario_arenas  # noqa: F401  (re-exported)
from .starling_layer import StarlingLayer

PARK_M = 1.0e3     # where a drone that is out is parked (x and y)


@dataclass
class StepOut:
    """Result of one step. obs after auto-reset of the games that ended; reward, outcome, end_step and info
    describe the step just taken. info: band [N], closest_cross_m [N] (closest live opposite pair, horizontal;
    inf if none), closest_cross_3d_m [N] (the same in 3-D: the safety filter keeps drones apart in 3-D, so a pair
    passing one above the other is close horizontally but not in 3-D), closest_team_m [N] (inf if no live
    same-team pair), rule_breach [N] bool (a live opposite pair closer than min(keepout_guard_m,
    keepout_strike_m) in 3-D; the pure partner rules hold every drone at one height, so there 3-D = horizontal;
    with the Starling layer the push-apart is off, so this reports what the filter alone allowed), filter_corrected [N, M] bool (Starling layer: live drones the safety
    filter changed this step; all False without it),
    tagged [N, M] bool (contact preset: drones tagged this step; a Strike drone tagged on the step it enters the
    zone does not score: tags come before the zone test),
    final_alive [N, M] bool (who was in the game at the end of this step, before any reset),
    start_miss [N] bool (True if the game that played this step started with a miss: its starts could not
    meet the spacing / keep-out; constant over a game, so read it on the done step to count games),
    upset [N] bool (physics backend: a live drone of the game that played this step tipped past 60 deg or turned
    non-finite at any step of that game; all False on the other backends),
    nonfinite_actions [N] long (drones whose action this step held NaN or inf; they were commanded zero).
    ``SvgGame.start_miss`` holds the same flag for the current (new) game."""
    obs: dict[str, Tensor]
    reward: dict[str, Tensor]
    done: Tensor
    outcome: Tensor
    end_step: Tensor
    info: dict[str, Tensor]


class SvgGame:
    """Batched Strike vs Guard game. See the module docstring and the S2 plan, Task 2."""

    def __init__(self, cfg: GameCfg, num_games: int, guards: int, strikes: int, device: str = "cuda",
                 seed: int = 0, band: int | None = None, scenario: Scenario | None = None,
                 world: RigidBodyWorld | None = None):
        if cfg.preset not in ("partner", "contact"):
            raise ValueError(f"preset must be 'partner' or 'contact', got {cfg.preset!r}")
        if cfg.arena.walls not in ("keep_in", "leave"):
            raise ValueError(f"arena.walls must be 'keep_in' or 'leave', got {cfg.arena.walls!r}")
        if cfg.starts.mode not in ("rings", "anywhere"):
            raise ValueError(f"starts.mode must be 'rings' or 'anywhere', got {cfg.starts.mode!r}")
        if cfg.rules.win_steps_in_zone != 1:
            raise ValueError("only win_steps_in_zone = 1 is built (one step inside the zone wins)")
        if cfg.rules.push_rule not in ("block", "shove"):
            raise ValueError(f"rules.push_rule must be 'block' or 'shove', got {cfg.rules.push_rule!r}")
        # Only these two are built so far. The message names the key, never the value (it may come from the
        # partner's local file).
        if cfg.rules.teammates_pass is not True:
            raise ValueError("only partner_rules.teammates_pass = true is built (team-mates pass through each other)")
        if cfg.obs_view != "full":
            raise ValueError("only game.obs_view = \"full\" is built (every drone sees every drone's full state)")
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
        # Starling layer (raises if a team's speed is above the commander's stick cap); None = pure partner rules.
        # Backend "fitted": S2's fitted PX4 model; "physics": the rigid-body drone in ``world`` (S2b).
        backend = cfg.starling.backend
        if backend not in BACKENDS:
            raise ValueError(f"starling_layer.backend must be one of {BACKENDS}, got {backend!r}")
        physics = cfg.starling.enabled and backend == "physics"
        if backend == "physics" and not cfg.starling.enabled:
            raise ValueError('starling_layer.backend = "physics" needs starling_layer.enabled = true')
        if physics and world is None:
            raise ValueError("the physics backend needs a world: IsaacWorld or TorchRigidBodyWorld")
        if world is not None and not physics:
            raise ValueError('a world is used only by the physics backend (starling_layer.backend = "physics")')
        self._starling: StarlingLayer | PhysicsLayer | None = None
        if physics:
            self._starling = PhysicsLayer(cfg, n, guards, strikes, dev, world)
        elif cfg.starling.enabled:
            self._starling = StarlingLayer(cfg, n, guards, strikes, dev)
        self.motion = f"physics/{world.label}" if physics else ("starling" if cfg.starling.enabled else "pure")
        self._physics = physics
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
        self._guard_survives = torch.zeros(n, dtype=torch.bool, device=dev)
        self._upset = torch.zeros(n, dtype=torch.bool, device=dev)       # this game had an upset drone (physics)
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
        self.start_miss = torch.where(mask, miss, self.start_miss)
        self.arenas = self.arenas.merge(ar, mask)
        self.pos_m = torch.where(mk[..., None], pos, self.pos_m)
        self.vel_mps = torch.where(mk[..., None], torch.zeros_like(self.vel_mps), self.vel_mps)
        self.yaw = torch.where(mk, torch.zeros_like(self.yaw), self.yaw)
        self.alive = torch.where(mk, torch.ones_like(self.alive), self.alive)
        self.steps = torch.where(mask, torch.zeros_like(self.steps), self.steps)
        self.dropout_step = torch.where(mk, drop, self.dropout_step)
        self._upset = self._upset & ~mask
        if self._starling is not None:       # new games: drones at rest at their starts, fresh commander
            self._starling.reset(mk.expand(n, m), self.pos_m, self.yaw)
        if self.cfg.preset == "contact":      # drawn only here, so the partner preset's random stream is unchanged
            surv = torch.rand(n, generator=self.gen, device=dev) < self.cfg.contact.guard_survives_tag_prob
            self._guard_survives = torch.where(mask, surv, self._guard_survives)
        phi = self._potential(self.pos_m, self.alive, self.arenas)
        self._phi = torch.where(mask, torch.where(torch.isfinite(phi), phi, torch.zeros_like(phi)), self._phi)

    def _time_left_s(self) -> Tensor:
        return (self.ticks - self.steps).to(torch.float32) * TICK_S

    def _obs(self) -> dict[str, Tensor]:
        return build_obs(self.cfg, self.pos_m, self.vel_mps, self.yaw, self.alive, self.arenas,
                         self._time_left_s(), self.guards, self.strikes)

    def _apply_pair_rules(self, pos_prev_m: Tensor, pos_m: Tensor, alive: Tensor) -> tuple[Tensor, Tensor]:
        """Partner preset: push-apart between opposite teams (rule from cfg.rules.push_rule), skipping drones that
        are out. Contact preset: no push-apart (tags are applied in step). Takes positions before and after the
        move ([N, M, 3]) and who is in the game ([N, M]); returns corrected positions [N, M, 3] and
        filter_corrected [N, M] bool (all False: this is the pure path; the Starling layer reports its own)."""
        no_filter = torch.zeros_like(alive)
        if self.cfg.preset != "partner":
            return pos_m, no_filter
        r = self.cfg.rules
        xy = push_apart(pos_m[..., :2], pos_prev_m[..., :2], self._is_strike[0], alive, r.keepout_guard_m,
                        r.keepout_strike_m, r.push_rule)
        return torch.cat((xy, pos_m[..., 2:]), dim=-1), no_filter

    # ------------------------------------------------------------------ public
    def reset(self, seed: int | None = None) -> dict[str, Tensor]:
        """Start every game afresh; reseed the generator if seed is given. Returns the observations."""
        if seed is not None:
            self.gen.manual_seed(seed)
        self._new_games(torch.ones(self.num_games, dtype=torch.bool, device=self.device))
        if self._physics:          # the world holds the new starts at once (a reader may look before the first step)
            self._starling.flush()
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
        """actions {"guard": [N, G, 4], "strike": [N, S, 4]} in [-1, 1]: vx, vy, vz, yaw rate. Pure partner rules:
        vz ignored (planar). Starling layer: (vx, vy, vz) norm-capped at the team speed, then the layer.
        Tie rule (contact preset): tags are applied before the zone test, so a Strike drone tagged on the step it
        enters the zone does not score."""
        cfg, g = self.cfg, self.guards
        a = torch.cat((actions[GUARD], actions[STRIKE]), dim=1)                       # [N, M, 4]
        # a drone whose action holds NaN or +/-inf is commanded zero and counted per game in info["nonfinite_actions"],
        # so a diverged strategy can never win silently (S2b Task 9, lead's ruling). Before: clamp let NaN through and
        # turned +/-inf into a full-scale command.
        bad_action = ~torch.isfinite(a).all(dim=-1)                                      # [N, M]
        a = torch.where(bad_action[..., None], torch.zeros_like(a), a).clamp(-1.0, 1.0)
        alive_prev = self.alive
        pos_prev = self.pos_m
        self.yaw = self.yaw + a[..., 3] * cfg.yaw_rate_max_rad_s * TICK_S * alive_prev
        lim = (self.arenas.half_m - cfg.arena.wall_margin_m)[:, None, None]            # [N, 1, 1]
        z_lo, z_hi = cfg.arena.height_band_m
        alive = alive_prev
        if self._starling is None:
            # pure partner rules: per-team norm cap, planar move (z held), push-apart
            v = a[..., :2]
            v = v / v.norm(dim=-1, keepdim=True).clamp(min=1.0) * self._speed_mps
            v = v * alive_prev[..., None]
            xy = pos_prev[..., :2] + v * TICK_S
            pos = torch.cat((xy, torch.full_like(xy[..., :1], cfg.arena.start_height_m)), dim=-1)
            pos, corrected = self._apply_pair_rules(pos_prev, pos, alive_prev)
            if cfg.arena.walls == "keep_in":
                xy = torch.maximum(torch.minimum(pos[..., :2], lim), -lim)
                pos = torch.cat((xy, pos[..., 2:]), dim=-1)
            else:
                alive = alive & ~(pos[..., :2].abs() >= lim).any(dim=-1)
        else:
            # Starling layer: 3-D command capped at the team speed (<= the stick cap, checked at construction),
            # commander + safety filter + PX4; no push-apart (D3)
            v = a[..., :3]
            v = v / v.norm(dim=-1, keepdim=True).clamp(min=1.0) * self._speed_mps
            yaw_rate = a[..., 3] * cfg.yaw_rate_max_rad_s * alive_prev
            pos, _, corrected = self._starling.step(v, pos_prev, alive_prev, self.yaw, yaw_rate)
            if self._physics:                     # D10: any live drone upset this game
                self._upset = self._upset | (self._starling.upset & alive_prev).any(dim=1)
            if cfg.arena.walls == "keep_in":      # walls and the height band stop the drone (and its model)
                lo = torch.cat((-lim, -lim, torch.full_like(lim, z_lo)), dim=-1)          # [N, 1, 3]
                hi = torch.cat((lim, lim, torch.full_like(lim, z_hi)), dim=-1)
                pos = self._starling.keep_in(lo, hi)
            else:                                 # leaving the arena or the height band takes the drone out
                out = (pos[..., :2].abs() >= lim).any(dim=-1) | (pos[..., 2] < z_lo) | (pos[..., 2] > z_hi)
                alive = alive & ~out
        # contact tags, on the positions the drones end the step at (after the walls), and before the zone test
        # (tie rule above). A drone that left through a wall this step can no longer tag or be tagged.
        tagged = torch.zeros_like(alive_prev)
        if cfg.preset == "contact":
            tagged, alive = contact_tags(pos, alive, g, cfg.contact.contact_m, self._guard_survives)
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
        vel = (pos - pos_prev) / TICK_S
        if self._starling is None:                          # planar path (D2): no vertical speed
            vel = torch.cat((vel[..., :2], torch.zeros_like(vel[..., 2:])), dim=-1)
        vel = torch.where(both, vel, torch.zeros_like(vel))
        self.pos_m, self.vel_mps, self.alive, self.steps = pos, vel, alive, steps_new
        # info and rewards (about the game that just played)
        dist = (pos[:, :, None, :2] - pos[:, None, :, :2]).norm(dim=-1)              # [N, M, M]
        live2 = alive[:, :, None] & alive[:, None, :]
        inf = torch.full_like(dist, float("inf"))
        closest_cross = torch.where(live2 & self._cross, dist, inf).amin(dim=(1, 2))
        closest_team = torch.where(live2 & self._same, dist, inf).amin(dim=(1, 2))
        dist3 = (pos[:, :, None, :] - pos[:, None, :, :]).norm(dim=-1)                 # [N, M, M], 3-D
        closest_cross_3d = torch.where(live2 & self._cross, dist3, inf).amin(dim=(1, 2))
        phi_now = self._potential(pos, alive, self.arenas)
        phi_now = torch.where(torch.isfinite(phi_now), phi_now, self._phi)
        reward = team_rewards(cfg.rewards, outcome, self._phi, phi_now, g, self.strikes)
        info = {"band": self.arenas.band, "closest_cross_m": closest_cross, "closest_cross_3d_m": closest_cross_3d,
                "closest_team_m": closest_team,
                "rule_breach": closest_cross_3d < self._keepout_min - 1e-6, "filter_corrected": corrected,
                "final_alive": alive.clone(), "tagged": tagged}
        end_step = torch.where(done, steps_new, torch.zeros_like(steps_new))
        self._phi = phi_now
        info["start_miss"] = self.start_miss.clone()      # the game that just played
        info["upset"] = self._upset.clone()
        info["nonfinite_actions"] = bad_action.sum(dim=1)                    # [N] long: drones commanded NaN/inf
        self._new_games(done)
        return StepOut(self._obs(), reward, done, outcome, end_step, info)
