"""EXPLORATORY real-drone response for tier 1: the commander's teleop law, the safety filter per team, then PX4.

``FittedResponse`` is the drop-in for ``PlaceholderResponse`` (same ``step``/``reset``, plus positions): the
command a policy sends, [N, M, 3] world ENU m/s, goes through

Steps 1 and 2 are ``models/command_chain.CommandChain``, the chain shared with the S2b physics backend (moved out of
this class unchanged, S2b Task 4; checked bit for bit by ``tests/test_command_chain.py``).

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

Estimate error (STE L1.7, off by default): ``estimate_error`` = {quantity: (sigma, tau_s)} for "pos" and "vel" gives
the PX4 law tier 2's first-order Gauss-Markov estimate error (``models/estimator_effect.EstimatorEffect``, reused with no
delay and no white noise), stepped once per 0.01 s sub-step and drawn from its stationary distribution at every reset,
seeded with ``estimate_seed``. Only the law's two feedback reads use the estimate (p_sp - p and vel_sp - v); the
integration, ``pos_m`` and ``vel_mps`` stay true. ``commander_reads_estimate``: the commander copy and its safety filter
read the estimated position at the tick start (the same error the law reads then), else the true one. No attitude: the
lag1 model has none. Off (None, or every sigma 0): nothing is built or drawn and every operation is as before.

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
from svg_training.models.command_chain import CommandChain
from svg_training.models.commander import CommanderParams
from svg_training.models.estimator_effect import EstimatorEffect
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
                 filter_kwargs: dict | None = None, hover_seed: bool = False, filter_fn=None,
                 estimate_error: dict[str, tuple[float, float]] | None = None, estimate_seed: int = 0,
                 commander_reads_estimate: bool = False):
        """filter_kwargs, if given, is merged last into the ``filter_velocities`` call (it may override any keyword
        this class passes, e.g. ``iterations``); None leaves the S1 call unchanged. ``filter_fn``: the filter function
        (same signature as ``filter_velocities``); None = this module's ``filter_velocities`` (the default).

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

        self.hover_seed = bool(hover_seed)
        n, m = n_games, n_drones
        self.device, self.dtype = device, dtype
        # the commander copy and the safety filter: the chain shared with the physics backend (S2b Task 4)
        self.chain = CommandChain(n, m, cfg, device, dtype=dtype, safety_filter=safety_filter, pair_mask=pair_mask,
                                  filter_iterations=filter_iterations, filter_kwargs=filter_kwargs,
                                  filter_fn=filter_velocities if filter_fn is None else filter_fn)
        self.vel_mps = torch.zeros(n, m, 3, device=device, dtype=dtype)
        self.pos_m = (torch.zeros(n, m, 3, device=device, dtype=dtype) if pos_m is None
                      else pos_m.to(device=device, dtype=dtype).clone())
        self._buf = torch.zeros(self.hist, n, m, 9, device=device, dtype=dtype)  # delay history, ring buffer
        self._head = 0                                                          # slot the next sample goes to
        self._fresh = torch.ones(n, m, dtype=torch.bool, device=device)        # history not started yet
        # the estimate error (L1.7, module docstring): None = off, nothing built or drawn
        error = dict(estimate_error or {})       # Python numbers (the game file); EstimatorEffect checks them
        bad = sorted(set(error) - {"pos", "vel"})
        if bad:
            raise ValueError(f"tier 1's estimate error has position and velocity only (no attitude state), got {bad}")
        error = {q: v for q, v in error.items() if v[0] != 0.0}
        self.commander_reads_estimate = bool(commander_reads_estimate)
        self.estimator: EstimatorEffect | None = None
        if error:
            self.estimator = EstimatorEffect(n, m, 0, 0.0, 0.0, 0.0, 0.0, device, dtype=dtype, seed=estimate_seed,
                                             error=error, dt_s=model_dt_s)
            self.estimator.reset(torch.ones(n, m, dtype=torch.bool, device=device), self.pos_m, None, self.vel_mps,
                                 None)
            self.estimator.reseed(estimate_seed)   # the first reset after this draws as a reseed's would (replay)

    # ------------------------------------------------------------------------------------- the chain's state
    # Kept as attributes of this class (S1/S2 callers and tests read and write them); they live in ``self.chain``.
    commander = property(lambda self: self.chain.commander)
    safety_filter = property(lambda self: self.chain.safety_filter)
    filter_cfg = property(lambda self: self.chain.filter_cfg)
    filter_iterations = property(lambda self: self.chain.filter_iterations)
    filter_kwargs = property(lambda self: self.chain.filter_kwargs)
    pair_mask = property(lambda self: self.chain.pair_mask)
    setpoint = property(lambda self: self.chain.setpoint)
    _filter_cap_mps = property(lambda self: self.chain._filter_cap_mps)

    @property
    def corrected(self) -> Tensor:
        """[N, M] bool: drones the filter changed in the last step (all False when off)."""
        return self.chain.corrected

    @corrected.setter
    def corrected(self, value: Tensor) -> None:
        self.chain.corrected = value

    @property
    def _filter(self):
        """The filter callback the commander calls (replaceable, as scripts/probe_wall_limit.py does)."""
        return self.chain._filter

    @_filter.setter
    def _filter(self, fn) -> None:
        self.chain._filter = fn

    def set_pair_mask(self, mask: Tensor) -> None:
        """Replace the filter's pair mask: [M, M] (all games) or [N, M, M] bool (per game, e.g. live drones only).
        Same rules as ``filter_velocities``: symmetric, False on the diagonal, block shaped."""
        self.chain.set_pair_mask(mask)

    # ------------------------------------------------------------------------------------- PX4, one 0.01 s step
    def _px4_step(self, x: Tensor, p_est: Tensor | None = None, v_est: Tensor | None = None) -> None:
        """x [N, M, 9] = delayed (p_sp, v_ff, a_ff). The lag1 law of px4_trajectory.simulate, plus z. ``p_est`` /
        ``v_est`` [N, M, 3]: the state the law's feedback reads (L1.7's estimate); None = the true state."""
        q, dt, vz = self.px4, self.model_dt_s, self.vertical
        p_sp, v_ff, a_ff = x[..., 0:3], x[..., 3:6], x[..., 6:9] * q.ff_gain
        p, v = self.pos_m, self.vel_mps
        pe = p if p_est is None else p_est
        ve = v if v_est is None else v_est
        vel_sp = _cap_norm(v_ff[..., :2] + q.kp_xy * (p_sp[..., :2] - pe[..., :2]), q.vel_max_mps)
        dv_xy = _cap_norm(a_ff[..., :2] * dt + self.alpha_xy * (vel_sp - ve[..., :2]), q.acc_max_mps2 * dt)
        vel_sp_z = torch.clamp(v_ff[..., 2] + vz["kp_z"] * (p_sp[..., 2] - pe[..., 2]),
                               min=-vz["vel_max_down_mps"], max=vz["vel_max_up_mps"])
        dv_z = a_ff[..., 2] * dt + self.alpha_z * (vel_sp_z - ve[..., 2])
        if math.isfinite(vz["acc_max_z_mps2"]):
            lim = vz["acc_max_z_mps2"] * dt
            dv_z = torch.clamp(dv_z, min=-lim, max=lim)
        v_new = v + torch.cat([dv_xy, dv_z[..., None]], dim=-1)
        self.pos_m = p + 0.5 * (v + v_new) * dt
        self.vel_mps = v_new

    # ------------------------------------------------------------------------------------- interface
    def step(self, cmd_mps: Tensor, pos_m: Tensor | None = None, landing: Tensor | None = None) -> Tensor:
        """One 0.05 s tick with commands [N, M, 3]; pos_m [N, M, 3], if given, replaces the model's positions first.
        ``landing`` [N, M] bool (STE L2.3; None = none): passed to the command chain (``CommandChain.step``).

        Returns the velocity [N, M, 3] at the end of the tick; ``self.pos_m`` is the position then.
        """
        if pos_m is not None:
            self.pos_m = pos_m.to(device=self.device, dtype=self.dtype)
        est = self.estimator
        land = {} if landing is None else {"landing": landing}       # None: the chain's call as before L2.3
        if est is None:
            p_sp, v_ff, a_ff = self.chain.step(cmd_mps, self.pos_m, **land)
        else:                                   # the estimate now: this instant's error on the (adopted) true state
            p_est, _, v_est, _ = est.replace_latest(self.pos_m, None, self.vel_mps, None)
            p_sp, v_ff, a_ff = self.chain.step(cmd_mps, p_est if self.commander_reads_estimate else self.pos_m, **land)
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
            if est is None:
                self._px4_step((1.0 - f) * a + f * b)
            else:                               # the law reads the estimate; then one sub-step of the error passes
                self._px4_step((1.0 - f) * a + f * b, p_est, v_est)
                p_est, _, v_est, _ = est.push(self.pos_m, None, self.vel_mps, None)
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
        self.chain.reset(mask)
        if self.estimator is not None:          # restarted drones: the error drawn from its stationary distribution
            self.estimator.reset(mask, self.pos_m, None, self.vel_mps, None)

    # ------------------------------------------------------------------------------------- the estimate (L1.7)
    @property
    def est_pos_m(self) -> Tensor:
        """[N, M, 3] the position PX4's law reads now (true + error); the true position when the error is off."""
        if self.estimator is None:
            return self.pos_m
        return self.estimator.replace_latest(self.pos_m, None, self.vel_mps, None)[0]

    @property
    def est_vel_mps(self) -> Tensor:
        """[N, M, 3] the velocity PX4's law reads now; the true velocity when the error is off."""
        if self.estimator is None:
            return self.vel_mps
        return self.estimator.replace_latest(self.pos_m, None, self.vel_mps, None)[2]

    def reseed_estimate(self, seed: int) -> None:
        """Restart the error's streams from ``seed`` (the game seed) and draw every drone's error afresh from the
        stationary distribution; nothing when the error is off."""
        if self.estimator is None:
            return
        self.estimator.reseed(seed)
        all_drones = torch.ones(self.pos_m.shape[:2], dtype=torch.bool, device=self.device)
        self.estimator.reset(all_drones, self.pos_m, None, self.vel_mps, None)
