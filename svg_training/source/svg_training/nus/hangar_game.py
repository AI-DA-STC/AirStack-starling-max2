"""The hangar game of the Phase 4 ladder (plan D1, D3, D5, D6): ``SvgGame`` with the arena, the zone and the starts fixed, the rung 3 layers,
and per-tick recording of the extra metrics and the video slots. It touches no shared code: it subclasses ``SvgGame`` and uses the
approved ``_draw_starts`` hook. Everything in the step is a batched tensor operation (no loop over games, no host read). No numeric
literal (G2): every count and tolerance comes from ``configs/nus_phase4.toml`` or from the game configuration.

* Fixed arena: one square arena, the zone at the arena centre (``_draw_arenas``). Starts: the paired starts of the starts file, in metres, at
  the flying height (plus the start-height jitter on ``free_jitter`` rows); with ``parked`` Guard 0 starts at the zone centre (Run 0's parked
  Guard). ``start_miss`` flags a game with any pair inside the safety filter's keep-out at the start: reported, never repaired.
* Rung 3 layer swap: ``SvgGame.__init__`` builds the fitted Starling layer with the safety filter on (``core/game.py``, private
  ``self._starling``) and turns the push-apart off. For rows with ``separation = "block"`` and a drone model this class replaces it with
  :class:`NusPushLayer` (the fitted response, filter off, then ``core.pair_rules.push_apart``) or :class:`NusIdentityLayer` (the drone flies
  the held command exactly), and resets the new layer to the starts. The push moves neither the model's velocity nor the commander's
  reference, so the commander pulls a pushed drone back. Refused with the physics backend.
* Recording (first game of each slot only, like ``play_match``): same-team and any-pair closest approach in 3-D, the safety filter's
  correction size (``_filter`` of the command chain wrapped on the instance, read only), the change of the command per tick, Guard 0's
  largest distance from the zone centre, and the positions of the first slots for videos.
* Clamp share (Phase 5 Task S5, INFO beside gate F-1; opt-in with ``clamp_tol_m``, off by default so Phase 4 is unchanged): the layer's
  ``keep_in`` is wrapped on the instance, read only, and counts per game the live drone-ticks whose pre-clamp position lies outside the
  keep-in box by more than ``clamp_tol_m`` (Euclidean distance to the box), the live drone-ticks, and whether any pre-clamp position was
  not finite. Pre-clamp is the layer's own position before its clamp (``model.pos_m`` fitted, ``drone.pos_m`` physics, ``pos_m``
  identity). The wrapper calls the original and changes no number.
"""
from __future__ import annotations

from dataclasses import replace

import torch
from torch import Tensor

from ..core.arena import Arenas, band_index_of_side
from ..core.game import SvgGame
from ..core.game_config import TICK_S, GameCfg
from ..core.pair_rules import push_apart
from ..core.starling_layer import StarlingLayer, check_commander, resolve_params
from ..models.fitted import FittedResponse, load_params
from .hangar import Geometry, with_wide_arena
from .replica import NusReplica, ReplicaState
from .rules import NusRules

THREE = 2 + 1  # x, y, z


class NusIdentityLayer:
    """An identity drone: it flies the held command exactly (position += command x tick), then the push, then the walls. Row 3a."""
    status = "identity"

    def __init__(self, cfg: GameCfg, num_games: int, guards: int, strikes: int, device):
        if getattr(getattr(cfg, "landing", None), "enabled", False):
            raise ValueError("[landing] enabled is not built for the NUS hangar layers (L2.3); switch it off")
        params = load_params(resolve_params(cfg.starling.params))
        self.stick_cap_mps = check_commander(cfg, params)
        m = guards + strikes
        self.pos_m = torch.zeros(num_games, m, THREE, device=device)
        self._is_strike = torch.arange(m, device=device) >= guards
        self._keep = (cfg.rules.keepout_guard_m, cfg.rules.keepout_strike_m, cfg.rules.push_rule)

    def reset(self, mask: Tensor, pos_m: Tensor, yaw: Tensor | None = None) -> None:
        self.pos_m = torch.where(mask[..., None], pos_m, self.pos_m)

    def step(self, cmd_mps: Tensor, pos_m: Tensor, alive: Tensor, yaw: Tensor | None = None, yaw_rate_rad_s: Tensor | None = None):
        moved = pos_m + cmd_mps * alive[..., None] * TICK_S
        xy = push_apart(moved[..., :2], pos_m[..., :2], self._is_strike, alive, *self._keep)
        self.pos_m = torch.cat((xy, moved[..., 2:]), dim=-1)
        return self.pos_m, cmd_mps * alive[..., None], torch.zeros_like(alive)

    def keep_in(self, lo_m: Tensor, hi_m: Tensor) -> Tensor:
        self.pos_m = torch.maximum(torch.minimum(self.pos_m, hi_m), lo_m)
        return self.pos_m


class NusPushLayer(StarlingLayer):
    """The fitted response with the safety filter off, then the partner push-apart (row 3). Out drones restart at rest every step."""
    status = "exploratory (filter off, push-apart kept)"

    def __init__(self, cfg: GameCfg, num_games: int, guards: int, strikes: int, device):
        if getattr(getattr(cfg, "landing", None), "enabled", False):
            raise ValueError("[landing] enabled is not built for the NUS hangar layers (L2.3); switch it off")
        super().__init__(cfg, num_games, guards, strikes, device)
        params = load_params(resolve_params(cfg.starling.params))
        m = guards + strikes
        self.model = FittedResponse(num_games, m, params, device=device, safety_filter=False, hover_seed=True)
        self._is_strike = torch.arange(m, device=device) >= guards
        self._keep = (cfg.rules.keepout_guard_m, cfg.rules.keepout_strike_m, cfg.rules.push_rule)

    def step(self, cmd_mps: Tensor, pos_m: Tensor, alive: Tensor, yaw: Tensor | None = None, yaw_rate_rad_s: Tensor | None = None):
        self.model.reset(~alive)
        vel = self.model.step(cmd_mps * alive[..., None], pos_m)
        moved = self.model.pos_m
        xy = push_apart(moved[..., :2], pos_m[..., :2], self._is_strike, alive, *self._keep)
        self.model.pos_m = torch.cat((xy, moved[..., 2:]), dim=-1)
        return self.model.pos_m, vel, torch.zeros_like(alive)


class NusHangarGame(SvgGame):
    """See the module docstring. ``starts_units`` [N, M, 2]: the paired starts in partner units (zone centre at the origin), Guard drones
    first; ``jitter_m`` [N, M] or None; ``row``: the six keys of the ladder row; ``video_slots``: how many slots keep their positions."""

    def __init__(self, cfg: GameCfg, geo: Geometry, row: dict, starts_units: Tensor, jitter_m: Tensor | None, guards: int, strikes: int,
                 device: str = "cpu", seed: int = 0, parked: bool = False, video_slots: int = 0, world=None, rules: NusRules | None = None,
                 clamp_tol_m: float | None = None):
        if row["drone"] == "physics" and row["separation"] == "block":
            raise ValueError("the push layer is not built for the physics drone")
        n = starts_units.shape[0]
        self._jump = row["motion"] == "jump"
        self._partner_push = None
        if row["separation"] == "partner_push":   # rows 2.1 and 2.2: the partner's soft push, in the replica's own arithmetic (plan 4b)
            if rules is None:
                raise ValueError("a partner_push row needs the rules")
            kept = rules if row["boundary"] == "guard_circle" else replace(rules, guard_boundary_radius=float("inf"))  # 2.2: no Guard circle
            self._partner_push = NusReplica(kept, device=device)
            if row["boundary"] == "guard_circle":
                geo = with_wide_arena(geo)
        self.geo, self.row, self._parked, self._video_slots = geo, row, bool(parked), min(int(video_slots), starts_units.shape[0])
        z = torch.full((n, guards + strikes, 1), geo.height_m, device=device)
        if row["height"] == "free_jitter":
            if jitter_m is None:
                raise ValueError("a free_jitter row needs the jitter of the starts file")
            z = z + jitter_m.to(device)[..., None]
        self._starts_m = torch.cat((starts_units.to(device) * geo.scale_m_per_unit, z), dim=-1)
        if self._parked:     # Run 0: Guard 0 (and, with it, its previous position) at the zone centre
            self._starts_m[:, 0, :2] = 0
        params = load_params(resolve_params(cfg.starling.params))
        self._filter_keepout_m = 2 * float(params["filter"]["safety_radius_m"])
        self._last_pos: Tensor | None = None
        self._corr_size: Tensor | None = None
        self._clamp_tol_m = None if clamp_tol_m is None else float(clamp_tol_m)
        super().__init__(cfg, n, guards, strikes, device=device, seed=seed, world=world)
        self._base_speed_mps = self._speed_mps.clone()
        if cfg.starling.enabled and row["separation"] == "block":
            layer_cls = NusIdentityLayer if row["drone"] == "identity" else NusPushLayer
            self._starling = layer_cls(cfg, n, guards, strikes, device)
            self.motion = "starling"
            self._starling.reset(torch.ones(n, self.M, dtype=torch.bool, device=device), self.pos_m, self.yaw)
        self._wrap_filter()
        self._wrap_keep_in()
        self.reset()

    # ------------------------------------------------------------------ fixed arena and starts
    def _draw_arenas(self) -> Arenas:
        n, dev, geo = self.num_games, self.device, self.geo
        full = lambda v: torch.full((n,), v, device=dev)  # noqa: E731
        return Arenas(full(geo.side_m), full(geo.side_m / 2), torch.zeros(n, 2, device=dev), full(geo.zone_radius_m),
                      torch.full((n,), band_index_of_side(self.cfg.arena, geo.side_m), dtype=torch.long, device=dev))

    def _draw_starts(self, arenas: Arenas) -> tuple[Tensor, Tensor]:
        pos = self._starts_m.clone()
        dist = (pos[:, :, None, :] - pos[:, None, :, :]).norm(dim=-1)
        pair = ~torch.eye(self.M, dtype=torch.bool, device=self.device)[None]
        return pos, ((dist < self._filter_keepout_m) & pair).any(dim=(1, 2))

    # ------------------------------------------------------------------ the partner's push (rows 2.1, 2.2) and jump motion
    def _apply_pair_rules(self, pos_prev_m: Tensor, pos_m: Tensor, alive: Tensor):
        """Row 2.1 / 2.2: the proposed displacement goes through the replica's push (and Guard circle) in partner units, then the replica's
        cap; everything else is ``SvgGame``'s. Other rows: ``SvgGame``'s rule."""
        sim = self._partner_push
        if sim is None:
            return super()._apply_pair_rules(pos_prev_m, pos_m, alive)
        scale = self.geo.scale_m_per_unit
        prev = pos_prev_m[..., :2] / scale
        intended = (pos_m[..., :2] - pos_prev_m[..., :2]) / scale
        state = ReplicaState(pos=prev, prev_pos=prev, reached=torch.zeros(prev.shape[0], device=prev.device),
                             step=torch.zeros(prev.shape[0], dtype=torch.long, device=prev.device))
        moved = sim._cap(intended + sim.corrections(state, intended), sim.rules.total_displacement_cap)
        if self._jump:    # the partner's push acts once per partner step: only on the sample tick, not on the ticks between
            moved = torch.where(self.jump_sample[:, None, None], moved, intended)
        return torch.cat(((prev + moved) * scale, pos_m[..., 2:]), dim=-1), torch.zeros_like(alive)

    @property
    def jump_sample(self) -> Tensor:
        """[N] bool: this tick is a sample tick of the game (jump motion: the displacement of a whole partner step is flown in one tick)."""
        return self.steps % self.geo.hold_ticks == 0

    # ------------------------------------------------------------------ recording
    def _chain(self):
        layer = self._starling
        return None if layer is None else getattr(layer, "chain", None) or getattr(getattr(layer, "model", None), "chain", None)

    def _wrap_filter(self) -> None:
        chain = self._chain()
        if chain is None or not chain.safety_filter:
            return
        original = chain._filter

        def recording(nominal: Tensor, pos_m: Tensor):
            velocities, corrected = original(nominal, pos_m)
            self._corr_size = (velocities - nominal).norm(dim=-1)
            return velocities, corrected
        chain._filter = recording

    def _wrap_keep_in(self) -> None:
        layer = self._starling
        if layer is None or self._clamp_tol_m is None:
            return
        original, tol = layer.keep_in, self._clamp_tol_m

        def counting(lo_m: Tensor, hi_m: Tensor) -> Tensor:
            pre = _layer_positions(layer)                                      # [N, M, 3] before the clamp
            excess = (pre - torch.maximum(torch.minimum(pre, hi_m), lo_m)).norm(dim=-1)
            live, active = self.alive, ~self._first_done                       # self.alive is still the step's alive_prev here
            acc = self._safety
            acc["clamp_ticks"] += active * ((excess > tol) & live).sum(dim=1)
            acc["live_ticks"] += active * live.sum(dim=1)
            acc["nonfinite_state"] |= active & ~torch.isfinite(pre).all(dim=-1).all(dim=-1)
            return original(lo_m, hi_m)
        layer.keep_in = counting

    def safety(self) -> dict[str, Tensor]:
        """Per game, device tensors (no host read): clamp_ticks, live_ticks [N] (clamp share = their ratio) and nonfinite_state [N]
        bool, since the last reset (scoring game: the first game of each slot). Empty without ``clamp_tol_m``."""
        return dict(self._safety)

    def _new_games(self, mask: Tensor) -> None:
        self._last_pos = self.pos_m      # the positions the games that ended this step finished at (the old tensor is kept)
        super()._new_games(mask)

    def reset(self, seed: int | None = None):
        obs = super().reset(seed)
        n, m, dev, big = self.num_games, self.M, self.device, float("inf")
        self._first_done = torch.zeros(n, dtype=torch.bool, device=dev)
        self._ticks_seen = 0
        self._prev_cmd = torch.zeros(n, m, THREE, device=dev)
        self._acc = {name: torch.zeros(n, device=dev) for name in ("corr_sum", "corr_n", "smooth_sum", "smooth_n", "drift")}
        self._acc["team_min"] = torch.full((n,), big, device=dev)
        self._acc["any_min"] = torch.full((n,), big, device=dev)
        self._safety = {} if self._clamp_tol_m is None else {
            "clamp_ticks": torch.zeros(n, dtype=torch.long, device=dev), "live_ticks": torch.zeros(n, dtype=torch.long, device=dev),
            "nonfinite_state": torch.zeros(n, dtype=torch.bool, device=dev)}
        self._video = torch.zeros(self.ticks + 1, self._video_slots, m, THREE, device=dev) if self._video_slots else None
        if self._video is not None:
            self._video[0] = self.pos_m[:self._video_slots]
        return obs

    def step(self, actions):
        a = torch.cat((actions["guard"], actions["strike"]), dim=1)
        a = torch.where(torch.isfinite(a).all(dim=-1, keepdim=True), a, torch.zeros_like(a)).clamp(-1.0, 1.0)
        alive_prev = self.alive.clone()
        self._corr_size = None
        if self._jump:   # jump motion: on a sample tick the team speed cap is scaled by hold_ticks for that tick only
            self._speed_mps = self._base_speed_mps * torch.where(self.jump_sample, float(self.geo.hold_ticks), 1.0)[:, None, None]
        out = super().step(actions)
        active = ~self._first_done
        v = a[..., :THREE]
        v = v / v.norm(dim=-1, keepdim=True).clamp(min=1.0) * self._speed_mps
        change = (v - self._prev_cmd).norm(dim=-1) * alive_prev
        have_prev = self._ticks_seen > 0
        if have_prev:
            self._acc["smooth_sum"] += active * change.sum(dim=1)
            self._acc["smooth_n"] += active * alive_prev.sum(dim=1)
        self._prev_cmd = v
        pos, alive = self._last_pos, out.info["final_alive"]
        live2 = alive[:, :, None] & alive[:, None, :]
        dist3 = (pos[:, :, None, :] - pos[:, None, :, :]).norm(dim=-1)
        inf = torch.full_like(dist3, float("inf"))
        self._acc["team_min"] = torch.where(active, torch.minimum(self._acc["team_min"], torch.where(live2 & self._same, dist3, inf).amin(dim=(1, 2))),
                                            self._acc["team_min"])
        offdiag = ~torch.eye(self.M, dtype=torch.bool, device=self.device)[None]
        self._acc["any_min"] = torch.where(active, torch.minimum(self._acc["any_min"], torch.where(live2 & offdiag, dist3, inf).amin(dim=(1, 2))),
                                           self._acc["any_min"])
        drift = (pos[:, 0, :2] - self.arenas.zone_centre_m).norm(dim=-1)
        self._acc["drift"] = torch.where(active, torch.maximum(self._acc["drift"], drift), self._acc["drift"])
        if self._corr_size is not None:
            hit = out.info["filter_corrected"] & alive
            self._acc["corr_sum"] += active * (self._corr_size * hit).sum(dim=1)
            self._acc["corr_n"] += active * hit.sum(dim=1)
        self._ticks_seen += 1
        if self._video is not None and self._ticks_seen < self._video.shape[0]:
            self._video[self._ticks_seen] = pos[:self._video_slots]
        self._first_done = self._first_done | out.done
        return out

    def extras(self) -> dict[str, Tensor]:
        """Per-slot extras of the first games, on the host (one read, after the match): team_min_3d_m, any_min_3d_m, corr_mean_mps and
        corr_count (per game: mean size over its corrected drone-steps, and how many), smooth_tick_mps (per game mean over live drone-ticks of
        the change of the command), guard0_drift_m, and ``video`` [T + 1, slots, M, 3] when slots are kept."""
        acc = {k: v.detach().cpu() for k, v in self._acc.items()}
        out = {"team_min_3d_m": acc["team_min"], "any_min_3d_m": acc["any_min"], "guard0_drift_m": acc["drift"],
               "corr_mean_mps": acc["corr_sum"] / acc["corr_n"].clamp(min=1), "corr_count": acc["corr_n"],
               "smooth_tick_mps": acc["smooth_sum"] / acc["smooth_n"].clamp(min=1)}
        if self._video is not None:
            out["video"] = self._video.detach().cpu()
        out.update({k: v.detach().cpu() for k, v in self._safety.items()})
        return out


def _layer_positions(layer) -> Tensor:
    """The layer's own drone positions [N, M, 3] (before ``keep_in`` clamps them): physics ``drone``, fitted ``model``, identity."""
    for name in ("drone", "model"):
        inner = getattr(layer, name, None)
        if inner is not None:
            return inner.pos_m
    return layer.pos_m
