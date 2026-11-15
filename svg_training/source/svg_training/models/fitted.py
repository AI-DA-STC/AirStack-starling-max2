"""EXPLORATORY real-drone response for tier 1: the commander's teleop law, the safety filter per team, then PX4.

``FittedResponse`` is the drop-in for ``PlaceholderResponse`` (same ``step``/``reset``, plus positions): the
command a policy sends, [N, M, 3] world ENU m/s, goes through

1. ``models/commander.py``: CMU's real-mode teleop law (stick cap, acceleration ramp, reference point and its
   leash), one 0.05 s tick;
2. optionally ``core/safety_filter.py``, at the point where the commander calls its filter: on the ramped stick,
   before the feed-forward and the setpoint (``swarm_commander.py:2140-2146``; see commander.py step 5), between
   drones of the same team only (``pair_mask``);
3. PX4 1.14's response to the trajectory setpoint, the kept ``lag1`` family of ``models/px4_trajectory.py``
   (horizontal, fitted to real flight logs at <= 0.5 m/s, exploratory), on the fit's own 0.01 s grid: five
   sub-steps per tick, the setpoint held across them. The pure delay shifts the setpoint (position, speed,
   acceleration) by ``delay_s`` with the reference's linear interpolation; a fresh drone's history is its first
   setpoint, as the reference holds x[0] before t_0.
   Feed-forward caveat: the fit saw a "derived" acceleration (slope of the 5 Hz logged speed setpoint); here PX4
   gets the commander's exact 20 Hz ramp acceleration (5 m/s^2 for 0.1 s). The fitted acceleration limit mostly
   absorbs the difference, but outcomes are sensitive to that limit.
   The vertical channel is NOT fitted: the same lag1 shape with the drone's own vertical gains (PROPOSED values in
   the parameter file's ``[px4_vertical]`` table).

The model owns each drone's position (trapezoid integration, as the reference). ``step(cmd, pos_m)`` first adopts
the caller's positions (so a caller that moves or places drones is obeyed), and ``self.pos_m`` holds the positions
after the step. Parameters come from a TOML such as ``params/real_exploratory_v0.toml``.
"""
from __future__ import annotations

import math
import pathlib
import tomllib

import torch
from torch import Tensor

from svg_training.core.safety_filter import filter_velocities
from svg_training.models.commander import CommanderParams, TeleopCommander
from svg_training.models.px4_trajectory import TrajectoryParams
from svg_training.models._filters import lag_alpha


def load_params(path: str | pathlib.Path) -> dict:
    """The parameter TOML as a dict with tables px4, px4_vertical, commander, filter."""
    cfg = tomllib.loads(pathlib.Path(path).read_text())
    missing = {"px4", "px4_vertical", "commander", "filter"} - set(cfg)
    if missing:
        raise ValueError(f"{path}: missing tables {sorted(missing)}")
    need = {"safety_radius_m", "max_speed_mps", "alpha", "tolerance"} - set(cfg["filter"])
    if need:
        raise ValueError(f"{path}: [filter] lacks {sorted(need)}")
    return cfg


def _cap_norm(x: Tensor, limit: float) -> Tensor:
    """px4_trajectory._cap_norm: scale x [..., k] down to norm <= limit (inf = no limit)."""
    if not math.isfinite(limit):
        return x
    norm = x.norm(dim=-1, keepdim=True)
    return x * torch.clamp(limit / norm.clamp(min=1e-12), max=1.0)


class FittedResponse:
    """Commander + (filter) + PX4 response for N games of M drones: cmd_mps [N, M, 3] -> velocity [N, M, 3].

    Attributes after a step: ``vel_mps``, ``pos_m`` [N, M, 3]; ``setpoint`` = (p_sp, v_ff, a_ff), each [N, M, 3],
    the commander's output this tick; ``corrected`` [N, M] bool, drones the filter changed (all False when off).
    """

    def __init__(self, n_games: int, n_drones: int, params: str | pathlib.Path | dict, dt_s: float | None = None,
                 device="cuda", dtype: torch.dtype = torch.float32, safety_filter: bool = False,
                 pair_mask: Tensor | None = None, filter_iterations: int = 1000, pos_m: Tensor | None = None,
                 filter_kwargs: dict | None = None, hover_seed: bool = False):
        """filter_kwargs, if given, is merged last into the ``filter_velocities`` call (it may override any keyword
        this class passes, e.g. ``iterations``); None leaves the S1 call unchanged.

        hover_seed: on ``reset`` fill a drone's delay history with a hover setpoint (its position, zero speed, zero
        acceleration), so PX4 sees "hold here" for the first ``delay_s`` and the first tick's feed-forward arrives
        delayed like every later one. Off (the S1 default, bit-identical): the history is filled with the first
        setpoint, so the first tick's 5 m/s^2 ramp acceleration acts with no delay for about 0.2 s."""
        cfg = params if isinstance(params, dict) else load_params(params)
        px4 = dict(cfg["px4"])
        model_dt_s = float(px4.pop("model_dt_s"))
        self.px4 = TrajectoryParams.from_dict(px4)
        if self.px4.family != "lag1":
            raise ValueError(f"only the lag1 family is implemented in torch, got {self.px4.family!r}")
        self.vertical = {k: float(v) for k, v in cfg["px4_vertical"].items()}
        self.commander_params = CommanderParams.from_dict(cfg["commander"])
        tick_s = self.commander_params.tick_s
        if dt_s is not None and abs(dt_s - tick_s) > 1e-12:
            raise ValueError(f"dt_s {dt_s} must equal the commander tick {tick_s}")
        self.dt_s = tick_s
        self.sub = round(tick_s / model_dt_s)
        if self.sub < 1 or abs(self.sub * model_dt_s - tick_s) > 1e-9:
            raise ValueError(f"the tick {tick_s} s must be a whole number of model steps {model_dt_s} s")
        self.model_dt_s = model_dt_s
        d = self.px4.delay_s / model_dt_s
        self.delay_n = int(math.floor(d))
        self.delay_f = d - self.delay_n
        self.hist = self.delay_n + 2
        self.alpha_xy = lag_alpha(model_dt_s, self.px4.tau_s)
        self.alpha_z = lag_alpha(model_dt_s, self.vertical["tau_z_s"])

        self.safety_filter = bool(safety_filter)
        self.filter_cfg = dict(cfg["filter"])
        self.filter_iterations = int(filter_iterations)
        self.filter_kwargs = dict(filter_kwargs) if filter_kwargs else {}
        self.hover_seed = bool(hover_seed)
        if self.safety_filter:
            if pair_mask is None:
                raise ValueError("safety_filter=True needs a pair_mask (core.safety_filter.team_pair_mask)")
            self.pair_mask = pair_mask.to(device)
        else:
            self.pair_mask = None

        n, m = n_games, n_drones
        self.device, self.dtype = device, dtype
        self.commander = TeleopCommander(n, m, self.commander_params, device=device, dtype=dtype)
        self.vel_mps = torch.zeros(n, m, 3, device=device, dtype=dtype)
        self.pos_m = (torch.zeros(n, m, 3, device=device, dtype=dtype) if pos_m is None
                      else pos_m.to(device=device, dtype=dtype).clone())
        self._buf = torch.zeros(self.hist, n, m, 9, device=device, dtype=dtype)  # delay history, ring buffer
        self._head = 0                                                          # slot the next sample goes to
        self._fresh = torch.ones(n, m, dtype=torch.bool, device=device)        # history not started yet
        zeros = torch.zeros(n, m, 3, device=device, dtype=dtype)
        self.setpoint = (zeros, zeros.clone(), zeros.clone())
        # the filter's speed cap as a device tensor, made once: a Python number would be copied to the GPU on
        # every call (a host sync); same value, so results are unchanged
        self._filter_cap_mps = torch.tensor(float(self.filter_cfg["max_speed_mps"]), device=device, dtype=dtype)
        self.corrected = torch.zeros(n, m, dtype=torch.bool, device=device)

    # ------------------------------------------------------------------------------------- the filter
    def _filter(self, nominal: Tensor, pos_m: Tensor) -> tuple[Tensor, Tensor]:
        f = self.filter_cfg
        kw = {"alpha": f["alpha"], "iterations": self.filter_iterations, "tolerance": f["tolerance"],
              **self.filter_kwargs}
        res = filter_velocities(nominal, pos_m, self.pair_mask, f["safety_radius_m"], self._filter_cap_mps, **kw)
        self.corrected = res.corrected
        return res.velocities, res.corrected

    def set_pair_mask(self, mask: Tensor) -> None:
        """Replace the filter's pair mask: [M, M] (all games) or [N, M, M] bool (per game, e.g. live drones only).
        Same rules as ``filter_velocities``: symmetric, False on the diagonal, block shaped."""
        self.pair_mask = mask.to(self.device)

    # ------------------------------------------------------------------------------------- PX4, one 0.01 s step
    def _px4_step(self, x: Tensor) -> None:
        """x [N, M, 9] = delayed (p_sp, v_ff, a_ff). The lag1 law of px4_trajectory.simulate, plus z."""
        q, dt, vz = self.px4, self.model_dt_s, self.vertical
        p_sp, v_ff, a_ff = x[..., 0:3], x[..., 3:6], x[..., 6:9] * q.ff_gain
        p, v = self.pos_m, self.vel_mps
        vel_sp = _cap_norm(v_ff[..., :2] + q.kp_xy * (p_sp[..., :2] - p[..., :2]), q.vel_max_mps)
        dv_xy = _cap_norm(a_ff[..., :2] * dt + self.alpha_xy * (vel_sp - v[..., :2]), q.acc_max_mps2 * dt)
        vel_sp_z = torch.clamp(v_ff[..., 2] + vz["kp_z"] * (p_sp[..., 2] - p[..., 2]),
                               min=-vz["vel_max_down_mps"], max=vz["vel_max_up_mps"])
        dv_z = a_ff[..., 2] * dt + self.alpha_z * (vel_sp_z - v[..., 2])
        if math.isfinite(vz["acc_max_z_mps2"]):
            lim = vz["acc_max_z_mps2"] * dt
            dv_z = torch.clamp(dv_z, min=-lim, max=lim)
        v_new = v + torch.cat([dv_xy, dv_z[..., None]], dim=-1)
        self.pos_m = p + 0.5 * (v + v_new) * dt
        self.vel_mps = v_new

    # ------------------------------------------------------------------------------------- interface
    def step(self, cmd_mps: Tensor, pos_m: Tensor | None = None) -> Tensor:
        """One 0.05 s tick with commands [N, M, 3]; pos_m [N, M, 3], if given, replaces the model's positions first.

        Returns the velocity [N, M, 3] at the end of the tick; ``self.pos_m`` is the position then.
        """
        if pos_m is not None:
            self.pos_m = pos_m.to(device=self.device, dtype=self.dtype)
        safety = self._filter if self.safety_filter else None
        if not self.safety_filter:
            self.corrected = torch.zeros_like(self.corrected)
        p_sp, v_ff, a_ff = self.commander.step(cmd_mps.to(self.dtype), self.pos_m, safety=safety)
        self.setpoint = (p_sp, v_ff, a_ff)
        x = torch.cat([p_sp, v_ff, a_ff], dim=-1)
        # a fresh drone's history is its first setpoint (the reference holds x[0] before t_0)
        self._buf = torch.where(self._fresh[None, ..., None], x[None], self._buf)
        self._fresh = torch.zeros_like(self._fresh)
        n, f, h = self.delay_n, self.delay_f, self.hist
        for _ in range(self.sub):      # fixed sub-steps of one tick (5), not a loop over games
            self._buf[self._head] = x
            a = self._buf[(self._head - n) % h]          # x[k - n]
            b = self._buf[(self._head - n - 1) % h]      # x[k - n - 1]
            self._head = (self._head + 1) % h
            self._px4_step((1.0 - f) * a + f * b)
        return self.vel_mps

    def reset(self, mask: Tensor, pos_m: Tensor | None = None) -> None:
        """Restart the drones where mask [N, M] bool is True: at rest, fresh commander and delay history;
        at pos_m [N, M, 3] where given (else where they are)."""
        sel = mask[..., None]
        self.vel_mps = torch.where(sel, torch.zeros_like(self.vel_mps), self.vel_mps)
        if pos_m is not None:
            self.pos_m = torch.where(sel, pos_m.to(device=self.device, dtype=self.dtype), self.pos_m)
        if self.hover_seed:      # history = hover at the (new) position; the drone is no longer fresh
            hover = torch.cat([self.pos_m, torch.zeros_like(self.pos_m), torch.zeros_like(self.pos_m)], dim=-1)
            self._buf = torch.where(mask[None, ..., None], hover[None], self._buf)
            self._fresh = self._fresh & ~mask
        else:
            self._fresh = self._fresh | mask
        self.commander.reset(mask)
