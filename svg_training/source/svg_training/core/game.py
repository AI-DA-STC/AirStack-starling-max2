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
the drone out), tags (contact preset, or the study tag of ``[tag]``), scheduled drop-outs, then the zone test. Tie
rule: tags come before the zone test, so a Strike drone tagged on the step it enters the zone does not score.

The study tag (STE task L0.9, ``cfg.tag``; off by default, and off plays today's game bit for bit): one Guard drone
with one Strike drone, nearest pair first, within ``tag.radius_m`` in 3-D (``pair_rules.proximity_tags``); both leave
on that step unless the game drew "Guard survives" (``tag.guard_survives_tag_prob``, drawn per game at its start from
the tag's own generator: the first games and those after ``reset(seed)`` start alike with the tag on or off, later
ones not). Tested on CPU on all three motion paths, partner preset; the contact preset refuses it (own tag)."""
from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor

from svg_training.models.rigid_body import RigidBodyWorld

from .arena import BANDS, GUARD, STRIKE, Arenas, draw_arenas, draw_starts  # noqa: F401  (re-exported)
from .game_config import BACKENDS, START_MODES, TICK_S, GameCfg
from .observations import build_obs, build_state
from .pair_rules import contact_tags, proximity_tags, push_apart
from .physics_layer import PhysicsLayer
from .rewards import GUARD_WIN, RUNNING, STRIKE_WIN, team_rewards
from .scenarios import SCENARIOS, Scenario, scenario_arenas  # noqa: F401  (re-exported)
from .starling_layer import StarlingLayer

PARK_M = 1.0e3     # where a drone that is out is parked (x and y)
_TAG_SEED_MIX = 0x9E3779B97F4A7C15     # odd 64-bit constant: derives the study tag's generator seed from the game seed


def _tag_seed(seed: int) -> int:
    """Seed of the study tag's own generator (CODING_PRACTICES section 5: one generator per purpose), from the game
    seed: (seed + 1) x an odd 64-bit constant, mod 2^63 (not section 5's SeedSequence: no NumPy in the step files)."""
    return ((seed + 1) * _TAG_SEED_MIX) % (1 << 63)


@dataclass
class StepOut:
    """Result of one step. obs after auto-reset of the games that ended; reward, outcome, end_step and info
    describe the step just taken. info: band [N], closest_cross_m [N] (closest live opposite pair, horizontal;
    inf if none), closest_cross_3d_m [N] (the same in 3-D: the safety filter keeps drones apart in 3-D, so a pair
    passing one above the other is close horizontally but not in 3-D), closest_team_m [N] (inf if no live
    same-team pair), rule_breach [N] bool (a live opposite pair closer than min(keepout_guard_m,
    keepout_strike_m) in 3-D; the pure partner rules hold every drone at one height, so there 3-D = horizontal;
    with the Starling layer the push-apart is off, so this reports what the filter alone allowed; these closeness
    and breach figures count live drones only: a landing drone ([landing], L2.3) is not in them), filter_corrected [N, M] bool (Starling layer: live drones the safety
    filter changed this step; all False without it),
    tagged [N, M] bool (contact preset or the study tag: drones tagged this step; a Strike drone tagged on the step it
    enters the zone does not score: tags come before the zone test),
    final_alive [N, M] bool (who was in the game at the end of this step, before any reset),
    start_miss [N] bool (True if the game that played this step started with a miss: its starts could not
    meet the spacing / keep-out; constant over a game, so read it on the done step to count games),
    upset [N] bool (physics backend: a live drone of the game that played this step tipped past 60 deg or turned
    non-finite at any step of that game; all False on the other backends),
    nonfinite_actions [N] long (drones whose action this step held NaN or inf; they were commanded zero).
    ``SvgGame.start_miss`` holds the same flag for the current (new) game. Starts mode zone_disc_ring adds start_team_close (``_start_info``)."""
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
        if cfg.starts.mode not in START_MODES:
            raise ValueError(f"starts.mode must be one of {START_MODES}, got {cfg.starts.mode!r}")
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
        if cfg.preset == "contact" and cfg.tag.mode != "off":
            raise ValueError('preset "contact" has its own tag: use tag.mode = "off" with it (two tag rules at once)')
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
            self._starling = PhysicsLayer(cfg, n, guards, strikes, dev, world, seed=seed)   # estimator noise (L1.1b)
        elif cfg.starling.enabled:
            self._starling = StarlingLayer(cfg, n, guards, strikes, dev, seed=seed)   # estimate error (L1.7)
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
        self.alive, self.landing = torch.ones(n, m, dtype=torch.bool, device=dev), torch.zeros(n, m, dtype=torch.bool, device=dev)
        self.steps = torch.zeros(n, dtype=torch.long, device=dev)
        self.dropout_step = torch.full((n, m), -1, dtype=torch.long, device=dev)
        self.arenas = self._draw_arenas()
        self.start_miss, self.start_team_close = torch.zeros(n, dtype=torch.bool, device=dev), torch.zeros(n, dtype=torch.long, device=dev)
        self._phi = torch.zeros(n, device=dev)
        self._guard_survives = torch.zeros(n, dtype=torch.bool, device=dev)
        self._tag_on = cfg.tag.mode != "off"
        self._tag_gen = torch.Generator(device=device)
        self._seed_tag_streams(seed)          # the survive draw's generator, and the drawn radius's (L1.10), from seed
        self._tag_survives = torch.zeros(n, dtype=torch.bool, device=dev)     # study tag: Guard survives, per game
        self._upset = torch.zeros(n, dtype=torch.bool, device=dev)       # this game had an upset drone (physics)
        self.reset()

    # ------------------------------------------------------------------ helpers
    def _draw_arenas(self) -> Arenas:
        if self.scenario is not None:
            return self._sc_arenas
        return draw_arenas(self.cfg.arena, self.num_games, self.gen, self.device, self.band)

    def _draw_starts(self, arenas: Arenas) -> tuple[Tensor, Tensor]:
        """Starts for a new game in every slot: (starts [N, M, 3], miss [N] bool). The default is the random draw of
        ``core/arena.draw_starts`` from the game's generator; a subclass may replace it (NUS port Phase 4, owner-approved
        hook: ``nus/hangar_game.py``). Not called when a scenario is set."""
        return draw_starts(self.cfg, arenas, self.guards, self.strikes, self.gen, return_miss=True)

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
            pos, miss = self._draw_starts(ar)
        # drop-out: in a fraction of games, one random drone (any team) leaves at one random step
        hit = torch.rand(n, generator=self.gen, device=dev) < self.cfg.dropout_fraction
        who = (torch.rand(n, generator=self.gen, device=dev) * m).floor().long().clamp(max=m - 1)
        when = (torch.rand(n, generator=self.gen, device=dev) * self.ticks).floor().long().clamp(max=self.ticks - 1) + 1
        pick = hit[:, None] & (torch.arange(m, device=dev)[None, :] == who[:, None])
        drop = torch.where(pick, when[:, None].expand(n, m), torch.full((n, m), -1, dtype=torch.long, device=dev))
        self.start_miss, self.start_team_close = self._start_flags(mask, miss, pos)
        self.arenas = self.arenas.merge(ar, mask)
        self.pos_m = torch.where(mk[..., None], pos, self.pos_m)
        self.vel_mps = torch.where(mk[..., None], torch.zeros_like(self.vel_mps), self.vel_mps)
        self.yaw = torch.where(mk, torch.zeros_like(self.yaw), self.yaw)
        self.alive, self.landing = torch.where(mk, torch.ones_like(self.alive), self.alive), self.landing & ~mk   # L2.3
        self.steps = torch.where(mask, torch.zeros_like(self.steps), self.steps)
        self.dropout_step = torch.where(mk, drop, self.dropout_step)
        self._upset = self._upset & ~mask
        if self._starling is not None:       # new games: drones at rest at their starts, fresh commander
            self._starling.reset(mk.expand(n, m), self.pos_m, self.yaw)
        if self.cfg.preset == "contact":      # drawn only here, so the partner preset's random stream is unchanged
            surv = torch.rand(n, generator=self.gen, device=dev) < self.cfg.contact.guard_survives_tag_prob
            self._guard_survives = torch.where(mask, surv, self._guard_survives)
        if self._tag_on:                      # the study tag's own generator: the game's own draws stay as with it off
            surv = torch.rand(n, generator=self._tag_gen, device=dev) < self.cfg.tag.guard_survives_tag_prob
            self._tag_survives, self._tag_radius_m = torch.where(mask, surv, self._tag_survives), self._radii(mask)
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
            self._seed_tag_streams(seed)
        self._new_games(torch.ones(self.num_games, dtype=torch.bool, device=self.device))
        if self._physics or isinstance(self._starling, StarlingLayer):   # new starts held now; error restarts (L1.7)
            self._starling.flush(seed)     # seed: the estimator noise restarts too (its own generators, STE L1.1b)
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
        Tie rule (both tags): tags are applied before the zone test, so a Strike drone tagged on the step it
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
            pos, _, corrected = self._layer_step(v, pos_prev, alive_prev, yaw_rate)    # landing hook (L2.3), end of class
            if self._physics:                     # D10: any live drone upset this game
                self._upset = self._upset | (self._starling.upset & alive_prev).any(dim=1)
            if cfg.arena.walls == "keep_in":      # walls and the height band stop the drone (and its model)
                lo = torch.cat((-lim, -lim, torch.full_like(lim, z_lo)), dim=-1)          # [N, 1, 3]
                hi = torch.cat((lim, lim, torch.full_like(lim, z_hi)), dim=-1)
                pos = self._starling.keep_in(*self._landing_box(lo, hi))     # L2.3: landing drones have no walls
            else:                                 # leaving the arena or the height band takes the drone out
                out = (pos[..., :2].abs() >= lim).any(dim=-1) | (pos[..., 2] < z_lo) | (pos[..., 2] > z_hi)
                alive = alive & ~out
        # tags (contact or study), on the positions the drones end the step at (after the walls), before the zone test
        # (tie rule above). A drone that left through a wall this step can no longer tag or be tagged.
        tagged, alive_walls = torch.zeros_like(alive_prev), alive     # alive_walls: in the game after the walls (L2.3)
        if cfg.preset == "contact":
            tagged, alive = contact_tags(pos, alive, g, cfg.contact.contact_m, self._guard_survives)
        elif self._tag_on:                    # the study tag (L0.9): one for one, nearest pair first
            tagged, alive = self._study_tags(pos, alive, corrected)          # hook at the end of the class
        # scheduled drop-outs
        steps_new = self.steps + 1
        alive = alive & ~(self.dropout_step == steps_new[:, None])
        # outcome: reach the zone first, then time-out, then no Strike drone left
        d = (pos[..., :2] - self.arenas.zone_centre_m[:, None, :]).norm(dim=-1)
        strike_win = (alive & self._is_strike & (d <= self.arenas.zone_radius_m[:, None])).any(dim=1)
        guard_win = (steps_new >= self.ticks) | ~(alive & self._is_strike).any(dim=1)
        outcome = torch.where(strike_win, STRIKE_WIN, torch.where(guard_win, GUARD_WIN, RUNNING)).to(torch.int8)
        done = outcome > 0
        flying, flying_prev = self._land(alive_walls, alive, alive_prev, pos)   # park drones out; velocity from the move
        pos = torch.where(flying[..., None], pos, torch.full_like(pos, PARK_M))
        both = (flying & flying_prev)[..., None]
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
        info.update(self._start_info())                   # the game that just played (start_team_close: zone_disc_ring only)
        info["upset"] = self._upset.clone()
        info["nonfinite_actions"] = bad_action.sum(dim=1)                    # [N] long: drones commanded NaN/inf
        self._landing_info(info)                                              # L2.3: info["landing"] when on
        self._new_games(done)
        return StepOut(self._obs(), reward, done, outcome, end_step, info)

    # ------------------------------------------------------------------ start flags (STE task L0.10)
    # Kept at the end of the class so that the line numbers cited in ste_learning/ (game.py:296-299, :314-315, ...) hold.
    def _start_flags(self, mask: Tensor, miss: Tensor, pos_m: Tensor) -> tuple[Tensor, Tensor]:
        """New games where mask [N] bool: (start_miss [N] bool, start_team_close [N] long). start_team_close counts the
        team-mate pairs (either team) whose starts pos_m [N, M, 3] are closer than the filter distance (horizontal; all
        starts share one height), an INFO count for the study (LEAD CALL 21 Nov 2026: it is not a miss and changes no
        outcome). Computed in starts mode "zone_disc_ring" only; the other modes keep zeros and draw nothing extra."""
        start_miss = torch.where(mask, miss, self.start_miss)
        if self.cfg.starts.mode != "zone_disc_ring" or self.scenario is not None:
            return start_miss, self.start_team_close
        d = (pos_m[:, :, None, :2] - pos_m[:, None, :, :2]).norm(dim=-1)                  # [N, M, M]
        upper = torch.ones(self.M, self.M, dtype=torch.bool, device=self.device).triu(1)
        close = ((d < self._keepout_min) & self._same & upper).sum(dim=(1, 2))
        return start_miss, torch.where(mask, close, self.start_team_close)

    def _start_info(self) -> dict[str, Tensor]:
        """info entries about the starts of the game that played this step: start_miss [N] bool always; start_team_close
        [N] long in starts mode "zone_disc_ring" only (so the other modes' outputs are unchanged)."""
        info = {"start_miss": self.start_miss.clone()}
        if self.cfg.starts.mode == "zone_disc_ring" and self.scenario is None:
            info["start_team_close"] = self.start_team_close.clone()
        return info

    # ------------------------------------------------------------------ study tag hook (STE task L0.12b)
    # Kept at the end of the class so that the cited line numbers above hold.
    def _study_tags(self, pos_m: Tensor, alive: Tensor, corrected: Tensor) -> tuple[Tensor, Tensor]:
        """The study tag of the step (``core/pair_rules.proximity_tags``) on the positions pos_m [N, M, 3] the drones end
        the step at, among the drones alive [N, M] bool. ``corrected`` [N, M] bool: the drones the safety filter changed
        on this step (all False on the pure path). Returns (tagged [N, M] bool, alive_after [N, M] bool). A hook:
        ``ste/sweep.SweepGame`` overrides it to record each tag's partner, pair distance and filter flag; the game's
        own result is the same either way."""
        tagged, alive_after, _ = proximity_tags(pos_m, alive, self.guards, self._study_radius(), self._tag_survives)
        return tagged, alive_after

    # ------------------------------------------------------------------ drawn tag radius (STE task L1.10)
    # ``[tag] radius_m_range`` (optional; absent = the fixed ``radius_m``, today's game bit for bit: nothing is drawn
    # and the matcher gets the same float). With it set, every game draws its radius uniformly in [lo, hi] when it
    # starts (``_new_games``: the first games, auto-resets, ``reset`` and ``TrainGame.restart``), from a generator of its own
    # seeded from the game seed (``_tag_radius_seed``), so the arenas, starts, drop-outs and the survive draw are the
    # same as with the range off; ``reset(seed)`` reseeds it. Kept here so that the cited line numbers above hold.
    def _seed_tag_streams(self, seed: int) -> None:
        """(Re)seed the study tag's own generators from the game seed: the survive draw's and the drawn radius's."""
        self._tag_gen.manual_seed(_tag_seed(seed))
        if self.cfg.tag.radius_m_range is None:
            self._tag_radius_m: Tensor | None = None
            return
        if getattr(self, "_radius_gen", None) is None:
            self._radius_gen = torch.Generator(device=self.device)
            self._tag_radius_m = torch.full((self.num_games,), self.cfg.tag.radius_m, dtype=torch.float32,
                                            device=self.device)      # replaced by the first draw in _new_games
        self._radius_gen.manual_seed(_tag_radius_seed(seed))

    def _radii(self, mask: Tensor) -> Tensor | None:
        """The per-game tag radius after new games start where mask [N] bool: a fresh uniform draw in [lo, hi] for every
        game (one batched draw, the survive draw's pattern), kept where mask; None with the range off (no draw)."""
        rng = self.cfg.tag.radius_m_range
        if rng is None:
            return None
        lo, hi = rng
        u = torch.rand(self.num_games, generator=self._radius_gen, device=self.device)
        return torch.where(mask, lo + (hi - lo) * u, self._tag_radius_m)

    def _study_radius(self) -> float | Tensor:
        """The study tag's radius: ``[tag] radius_m`` (a float) with no range, else each game's drawn radius [N]."""
        return self.cfg.tag.radius_m if self._tag_radius_m is None else self._tag_radius_m

    # ------------------------------------------------------------------ landing drones (STE task L2.3)
    # Kept at the end of the class so that the line numbers cited in ste_learning/ hold; ``step`` reaches them through
    # one-line hooks (``_layer_step``, ``_landing_box``, ``_land``, ``_landing_info``).
    #
    # ``[landing] enabled`` (``game_config.LandingCfg``; off by default, and off plays today's game bit for bit: every
    # hook then returns its inputs unchanged and adds nothing). On: a drone that leaves the game by a tag or a drop-out on
    # a step (alive after the walls, not alive after the tags and drop-outs) is landing at the end of that step, at its
    # position (not parked). ``SvgGame.landing`` [N, M] bool holds it; ``alive`` and ``landing`` are never both True.
    # While landing, its command is (0, 0, -land_speed_mps) whatever its action (its yaw is held: the yaw update reads
    # alive), it is a row of every filter pair, the walls and the height band do not act on it (the flight fence does not
    # act on a LANDING drone), and it neither tags, is tagged, nor counts for the zone or the "no Strike drone left" test
    # (all of them read alive). When its height is at or below ``touchdown_z_m`` (or not finite) after a step it is out:
    # parked, as today. A new game clears it (``_new_games``). The policy sees it as out (``build_obs`` reads alive:
    # present 0, zeros). info["landing"] [N, M] bool (on only): who is landing at the end of the step, before any reset
    # (as final_alive). A drone that leaves through a wall or the height band (walls = "leave") is out at once, as today
    # (PROPOSED).
    def _layer_step(self, v: Tensor, pos_prev: Tensor, alive_prev: Tensor, yaw_rate: Tensor):
        """The Starling layer's step; with landing on, the landing drones' commands are replaced by the descent and the
        layer is told who is landing. Off: the call as before L2.3."""
        if not self.cfg.landing.enabled:
            return self._starling.step(v, pos_prev, alive_prev, self.yaw, yaw_rate)
        land = self.landing[..., None]
        sink = torch.full_like(v[..., 2:], -self.cfg.landing.land_speed_mps)
        descent = torch.cat((torch.zeros_like(v[..., :2]), sink), dim=-1)          # [N, M, 3] world ENU m/s
        return self._starling.step(torch.where(land, descent, v), pos_prev, alive_prev, self.yaw, yaw_rate,
                                   landing=self.landing)

    def _landing_box(self, lo: Tensor, hi: Tensor) -> tuple[Tensor, Tensor]:
        """keep_in's box (lo, hi [N, 1, 3]); with landing on, [N, M, 3] with no limit for the landing drones."""
        if not self.cfg.landing.enabled:
            return lo, hi
        land = self.landing[..., None]
        return torch.where(land, torch.full_like(land, float("-inf"), dtype=lo.dtype), lo), \
            torch.where(land, torch.full_like(land, float("inf"), dtype=hi.dtype), hi)

    def _land(self, alive_walls: Tensor, alive: Tensor, alive_prev: Tensor, pos_m: Tensor) -> tuple[Tensor, Tensor]:
        """Update ``landing`` after the tags and drop-outs of a step: touchdown first, then the drones that left the game
        by a tag or a drop-out. Returns (flying [N, M], flying before the step [N, M]) for the parking and the velocity; off:
        (alive, alive_prev), today's."""
        if not self.cfg.landing.enabled:
            return alive, alive_prev
        before = self.landing
        down = ~(pos_m[..., 2] > self.cfg.landing.touchdown_z_m)        # at or below the touchdown height, or not finite
        self.landing = (before & ~down) | (alive_walls & ~alive)
        return alive | self.landing, alive_prev | before

    def _landing_info(self, info: dict) -> None:
        """info["landing"] [N, M] bool with landing on; nothing when off (today's info keys)."""
        if self.cfg.landing.enabled:
            info["landing"] = self.landing.clone()


def _tag_radius_seed(seed: int) -> int:
    """Seed of the drawn tag radius's own generator (STE L1.10), from the game seed, as ``_tag_seed`` with another odd
    64-bit constant (one generator per purpose, CODING_PRACTICES section 5). Kept at the end of the module so that the
    cited line numbers above hold."""
    return ((seed + 1) * _TAG_RADIUS_SEED_MIX) % (1 << 63)


_TAG_RADIUS_SEED_MIX = 0xD1B54A32D192ED03   # odd 64-bit constant (not _TAG_SEED_MIX): the drawn radius's stream
