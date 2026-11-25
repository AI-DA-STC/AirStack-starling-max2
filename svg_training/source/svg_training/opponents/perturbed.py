"""Changed scripts for the route 3 calibration (stage LS1, job LS1.5; plan ste_learning/drafts/LS1_TASK_PLAN.md, task
LS1-M1-T6). ``scripted.py`` is never edited (its sha256 is pinned in every skill network and skills export), so the
changes live here, and none of them is added to ``scripted.REGISTRY``: the calibration builds them directly.

* ``CommandPerturbation``: a script whose command is changed by noise, a bias, a scale or a turn (``kind``); it records
  the command error against the script it wraps.
* Moved-switch players: ``SacrificeMovedEntry`` (entry half-angle, rad), ``ConvergeMovedGather`` (gather angle, rad),
  ``FlankMoved`` (margin, m) for the Strike team; ``FieldMovedRange`` (field range, m) for the Guard team. Each
  subclasses its script; the first three carry a copy of the script's ``act`` with the module constant replaced by an
  instance value, ``FlankMoved`` sets the class attribute ``MARGIN_M`` on the instance. At the value ``scripted.py``
  holds, each is its script bit for bit.
* ``SwitchRecorder``: flies a moved player and records its command error against the original script on the same
  observation (so the calibration reports a command error for the moved switches too).
* ``SWITCHES``: the near-miss switch keys, each with its team, the code it moves, its moved player and that player's
  keyword (shared by the calibration and the distillation gate file).

The recorded error (``errors()``), the same for the wrapper and the recorder: d = flown command - the original
script's command, on the live drones of each slot's first game only (``play_match`` and ``HeldPlayer`` count only the
first game of each slot), kept per drone slot and channel as tensors on the observation's device and read once per
cell: sum of d^2 ``[M, 4]`` float64, max |d| ``[M, 4]``, the count of rows ``[M]`` int64, and the original command's max
|.| ``[M, 4]`` (a channel is active where it is above zero). Per slot, because a ``Composite`` flies column m of member m.

No host read; shapes N games, M drones of the team, 4 = vx, vy, vz, yaw rate (``[-1, 1]``)."""
from __future__ import annotations

import math

import torch
from torch import Tensor

from ..core.game_config import GameCfg
from . import scripted
from .scripted import (_V, CIRCLE_UNTIL_RAD, RUN_IN_COMMIT_M, SACRIFICE_NO_BEARING_M, _circle, _pack, _slots,
                       _stand_off_m, _team_slots, _unit, _wrap, steer)

KINDS = ("noise", "bias", "scale", "turn")
COMMAND_DIM = 4                  # vx, vy, vz, yaw rate (STANDARDS section 3)
XY = (0, 1)                      # the channels a turn rotates
ALIVE_MIN = 0.5                  # the own-alive flag is 0 or 1 (scripted.py reads it so)


class _Recorder:
    """The command-error accumulators (module docstring), allocated at the first ``act`` on the observation's device."""

    def _init_record(self) -> None:
        self._first: Tensor | None = None       # [N] bool: games still in their slot's first game (None: all)
        self._sum_sq: Tensor | None = None
        self._max_abs: Tensor | None = None
        self._count: Tensor | None = None
        self._ref_max_abs: Tensor | None = None

    def _reset_first(self, games: Tensor) -> None:
        """games [N] bool: the games that end now; their slots' later games are not counted (``HeldPlayer.reset``)."""
        if self._first is None:
            self._first = torch.ones_like(games, dtype=torch.bool)
        else:
            self._first = self._first & ~games

    def _record(self, obs: Tensor, flown: Tensor, original: Tensor) -> None:
        """obs [N, M, OBS_DIM]; flown, original [N, M, 4]: add the live, first-game rows to the accumulators."""
        n, m = obs.shape[:2]
        if self._sum_sq is None:
            self._sum_sq = torch.zeros(m, COMMAND_DIM, dtype=torch.float64, device=obs.device)
            self._max_abs = flown.new_zeros(m, COMMAND_DIM)
            self._ref_max_abs = flown.new_zeros(m, COMMAND_DIM)
            self._count = torch.zeros(m, dtype=torch.long, device=obs.device)
        rows = obs[..., _V.alive] > ALIVE_MIN                                        # [N, M]
        if self._first is not None:
            rows = rows & self._first[:, None]
        w = rows[..., None].to(flown.dtype)
        d = (flown - original) * w
        self._sum_sq = self._sum_sq + (d.double() ** 2).sum(0)
        self._max_abs = torch.maximum(self._max_abs, d.abs().amax(0))
        self._ref_max_abs = torch.maximum(self._ref_max_abs, (original * w).abs().amax(0))
        self._count = self._count + rows.sum(0)

    def errors(self) -> dict | None:
        """The accumulators (tensors, on the device; None before the first ``act``): ``sum_sq`` [M, 4] float64,
        ``max_abs`` [M, 4], ``count`` [M] int64, ``ref_max_abs`` [M, 4]."""
        if self._sum_sq is None:
            return None
        return {"sum_sq": self._sum_sq.clone(), "max_abs": self._max_abs.clone(), "count": self._count.clone(),
                "ref_max_abs": self._ref_max_abs.clone()}


class CommandPerturbation(_Recorder):
    """``act = clamp(f(inner.act(obs)), -1, 1) * alive`` with f by ``kind`` on the chosen ``channels``:

    * ``noise``: adds i.i.d. uniform noise in [-size, size] per tick, drone and channel, drawn as [N, M, 4] every tick
      from the wrapper's own ``torch.Generator`` (seeded ``seed``, created on the observation's device at the first
      ``act``, never reseeded); one object per cell, so a cell's noise does not depend on the other cells of a batch;
    * ``bias``: adds the constant ``+size`` on every live drone and tick (zero on out drones through the alive multiply;
      the one kind that moves a zero command, ``guard_parked_centre`` in 3v3);
    * ``scale``: multiplies by ``size`` (1 = identity);
    * ``turn``: rotates xy anticlockwise by ``size`` degrees (channels must be (0, 1)).

    Identity at noise 0, bias 0, scale 1, turn 0. ``team``, ``name`` (default "<inner name>~<kind>=<size>") and
    ``reset`` (forwarded) as a strategy; ``errors()`` against the inner command (module docstring)."""

    def __init__(self, inner, kind: str, size: float, seed: int, channels: tuple[int, ...], name: str | None = None):
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
        size = float(size)
        if not math.isfinite(size):
            raise ValueError(f"size must be finite, got {size!r}")
        if kind == "noise" and size < 0:
            raise ValueError(f"a noise size is a half-width, at least 0, got {size!r}")
        channels = tuple(int(c) for c in channels)
        if not channels or len(set(channels)) != len(channels) or not all(0 <= c < COMMAND_DIM for c in channels):
            raise ValueError(f"channels must be distinct indices in 0..{COMMAND_DIM - 1}, got {channels!r}")
        if kind == "turn" and channels != XY:
            raise ValueError(f"a turn rotates xy: channels must be {XY}, got {channels!r}")
        self.inner, self.kind, self.size, self.seed, self.channels = inner, kind, size, int(seed), channels
        self.team = inner.team
        self.name = name if name is not None else f"{inner.name}~{kind}={size:g}"
        mask = torch.zeros(COMMAND_DIM, dtype=torch.bool)
        mask[list(channels)] = True
        self._mask_cpu = mask
        self._mask: Tensor | None = None
        self._gen: torch.Generator | None = None
        if kind == "turn":
            rad = math.radians(size)
            self._cos, self._sin = math.cos(rad), math.sin(rad)
        self._init_record()

    def reset(self, games: Tensor) -> None:
        self.inner.reset(games)
        self._reset_first(games)

    def _change(self, a: Tensor) -> Tensor:
        if self._mask is None or self._mask.device != a.device:
            self._mask = self._mask_cpu.to(a.device)
        if self.kind == "noise":
            if self._gen is None:
                self._gen = torch.Generator(device=a.device)
                self._gen.manual_seed(self.seed)
            u = torch.rand(a.shape, generator=self._gen, device=a.device, dtype=a.dtype)
            return a + (u * 2 - 1) * self.size * self._mask
        if self.kind == "bias":
            return a + self.size * self._mask
        if self.kind == "scale":
            return torch.where(self._mask, a * self.size, a)
        x, y = a[..., 0], a[..., 1]
        xy = torch.stack((x * self._cos - y * self._sin, x * self._sin + y * self._cos), dim=-1)
        return torch.cat((xy, a[..., 2:]), dim=-1)

    def act(self, obs: Tensor) -> Tensor:
        """obs [N, M, OBS_DIM] -> [N, M, 4]."""
        original = self.inner.act(obs)
        flown = self._change(original).clamp(-1, 1) * obs[..., _V.alive:_V.alive + 1]
        self._record(obs, flown, original)
        return flown


class SwitchRecorder(_Recorder):
    """Flies ``moved`` (a moved-switch player) and records its command error against ``original`` (the unmoved script)
    on the same observation every tick (``errors()``, module docstring). Both must play the same team."""

    def __init__(self, moved, original, name: str | None = None):
        if moved.team != original.team:
            raise ValueError(f"the moved player plays {moved.team!r}, the original {original.team!r}")
        self.moved, self.original, self.team = moved, original, moved.team
        self.name = name if name is not None else moved.name
        self._init_record()

    def reset(self, games: Tensor) -> None:
        self.moved.reset(games)
        self.original.reset(games)
        self._reset_first(games)

    def act(self, obs: Tensor) -> Tensor:
        """obs [N, M, OBS_DIM] -> [N, M, 4] (the moved player's command)."""
        flown = self.moved.act(obs)
        self._record(obs, flown, self.original.act(obs))
        return flown


# ------------------------------------------------------------------------------------------------ moved switches
class FieldMovedRange(scripted.GuardField):
    """``guard_field`` with the push range ``range_m`` (scripted.FIELD_RANGE_M today) as an instance value; ``act`` is a
    copy of ``GuardField.act`` (scripted.py) with that one constant replaced."""

    def __init__(self, team: str, cfg: GameCfg, num_games: int, device, seed: int = 0, *, range_m: float):
        super().__init__(team, cfg, num_games, device, seed)
        self.range_m = float(range_m)

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
        mag = (1.0 / d ** 2 - 1.0 / self.range_m ** 2) * (tpres & (d < self.range_m))
        push = -(tp / d[..., None] * mag[..., None]).sum(-2)
        a = pull + push
        a = a / a.norm(dim=-1, keepdim=True).clamp(min=1.0)
        return _pack(a, obs)


class FlankMoved(scripted.StrikeFlank):
    """``strike_flank`` with the clearance margin ``margin_m`` (scripted.StrikeFlank.MARGIN_M today): ``MARGIN_M`` set on
    the instance, which ``StrikeFlank.act`` reads (the class attribute is untouched)."""

    def __init__(self, team: str, cfg: GameCfg, num_games: int, device, seed: int = 0, *, margin_m: float):
        super().__init__(team, cfg, num_games, device, seed)
        self.MARGIN_M = float(margin_m)


class SacrificeMovedEntry(scripted.StrikeSacrifice):
    """``strike_sacrifice`` with the entry half-angle ``entry_half_angle_rad`` (scripted.ENTRY_HALF_ANGLE_RAD today) as an
    instance value; ``act`` is a copy of ``StrikeSacrifice.act`` (scripted.py) with that one constant replaced."""

    def __init__(self, team: str, cfg: GameCfg, num_games: int, device, seed: int = 0, *, entry_half_angle_rad: float):
        super().__init__(team, cfg, num_games, device, seed)
        self.entry_half_angle_rad = float(entry_half_angle_rad)

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
        has_bearing = any_guard & (drawn.norm(dim=-1) > SACRIFICE_NO_BEARING_M)
        away = torch.where(has_bearing[..., None], drawn, decoy_p)
        far = torch.atan2(-away[..., 1], -away[..., 0])
        diff = _wrap(far - torch.atan2(own_p[..., 1], own_p[..., 0]))
        direction = torch.where(diff >= 0, 1.0, -1.0)
        go_in = diff.abs() <= self.entry_half_angle_rad
        around = _circle(own_p, _stand_off_m(obs, self.cfg.arena.wall_margin_m), direction)
        rest_a = torch.where(go_in[..., None], straight, around)
        is_decoy = (torch.arange(obs.shape[1], device=obs.device) == 0)[None, :, None]
        a = torch.where(is_decoy, decoy_a, rest_a)
        a = torch.where((decoy_live & others_live)[..., None], a, straight)
        return _pack(a, obs)


class ConvergeMovedGather(scripted.StrikeConverge):
    """``strike_converge`` with the gather angle ``gather_angle_rad`` (scripted.GATHER_ANGLE_RAD today) as an instance
    value; ``act`` is a copy of ``StrikeConverge.act`` (scripted.py) with that one constant replaced."""

    def __init__(self, team: str, cfg: GameCfg, num_games: int, device, seed: int = 0, *, gather_angle_rad: float):
        super().__init__(team, cfg, num_games, device, seed)
        self.gather_angle_rad = float(gather_angle_rad)

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
        go = ((err.abs() <= self.gather_angle_rad) | ~live).all(-1) | committed      # [N, S]
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


# the moved switches, one per near-miss switch key (R2 OA-3): key -> (team, the code it moves, the moved player, the
# player's keyword for the value, in that player's unit). Read by the calibration (LS1.5) and the equivalence read's
# gate file (configs/ste_ls1/distil_gates.toml [controls] near_miss.switch; task LS1-M2-T1 moved it here from
# scripts/ste_ls1_calibration.py, unchanged).
SWITCHES = {
    "sacrifice_entry_rad": ("strike", "strike_sacrifice", SacrificeMovedEntry, "entry_half_angle_rad"),
    "converge_gather_rad": ("strike", "strike_converge", ConvergeMovedGather, "gather_angle_rad"),
    "flank_margin_m": ("strike", "strike_flank", FlankMoved, "margin_m"),
    "field_range_m": ("guard", "guard_field", FieldMovedRange, "range_m"),
}
