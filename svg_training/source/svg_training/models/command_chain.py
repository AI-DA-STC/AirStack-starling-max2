"""The shared command chain: CMU's commander copy, with the safety filter at the point the commander calls it.

Both drone models of the Starling layer use this one class, so they cannot drift apart (S2b plan, Review Focus 3):

* backend "fitted" (S1/S2): ``models/fitted.FittedResponse`` -> the fitted PX4 response;
* backend "physics" (S2b): ``core/physics_layer.PhysicsLayer`` -> ``models/physics_drone.PhysicsDrone`` (the PX4
  1.14 cascade on a rigid body).

One 0.05 s tick: ``step(cmd_mps, pos_m)`` runs ``models/commander.TeleopCommander`` (stick cap, ramp, reference
point and leash) with ``core/safety_filter.filter_velocities`` on the ramped stick (``swarm_commander.py``
:2140-2146; commander.py step 5), and returns the trajectory setpoint (p_sp, v_ff, a_ff), world ENU. The code was
moved out of ``FittedResponse`` unchanged: ``tests/test_command_chain.py`` checks the fitted path bit for bit
against tensors saved before the move.

Shapes: N games, M drones; vectors [N, M, 3], masks [N, M] bool. Batched; no loop over games, no host reads in
``step`` / ``reset`` / ``keep_in`` (the filter's own ``check_every`` early stop is its one allowed host sync).
"""
from __future__ import annotations

from typing import Callable

import torch
from torch import Tensor

from svg_training.core.safety_filter import filter_velocities, filter_velocities_shared
from svg_training.models.commander import CommanderParams, TeleopCommander


class CommandChain:
    """Commander + (safety filter) for N games of M drones. ``params`` is the parameter TOML as a dict
    (``models/fitted.load_params``); its ``[commander]`` and ``[filter]`` tables are used.

    Attributes: ``commander`` (TeleopCommander), ``commander_params``; after a step ``setpoint`` = (p_sp, v_ff,
    a_ff), each [N, M, 3], and ``corrected`` [N, M] bool (drones the filter changed; all False when off).

    ``filter_kwargs``, if given, is merged last into the ``filter_velocities`` call (it may override any keyword
    this class passes, e.g. ``iterations``). ``filter_fn`` (an addition to the plan's signature) is the filter
    function, default ``core.safety_filter.filter_velocities``; ``FittedResponse`` passes the name it imported, so
    a test that replaces ``models.fitted.filter_velocities`` still reaches the call.
    """

    def __init__(self, n: int, m: int, params: dict, device, dtype: torch.dtype = torch.float32,
                 safety_filter: bool = False, pair_mask: Tensor | None = None, filter_iterations: int = 1000,
                 filter_kwargs: dict | None = None, filter_fn: Callable | None = None):
        self.commander_params = CommanderParams.from_dict(params["commander"])
        self.safety_filter = bool(safety_filter)
        self.filter_cfg = dict(params["filter"])
        self.filter_iterations = int(filter_iterations)
        self.filter_kwargs = dict(filter_kwargs) if filter_kwargs else {}
        self._filter_fn = filter_velocities if filter_fn is None else filter_fn
        if self.safety_filter:
            if pair_mask is None:
                raise ValueError("safety_filter=True needs a pair_mask (core.safety_filter.team_pair_mask)")
            self.pair_mask = pair_mask.to(device)
        else:
            self.pair_mask = None
        self.device, self.dtype = device, dtype
        self.commander = TeleopCommander(n, m, self.commander_params, device=device, dtype=dtype)
        zeros = torch.zeros(n, m, 3, device=device, dtype=dtype)
        self.setpoint = (zeros, zeros.clone(), zeros.clone())
        # the filter's speed cap as a device tensor, made once: a Python number would be copied to the GPU on
        # every call (a host sync); same value, so results are unchanged
        self._filter_cap_mps = torch.tensor(float(self.filter_cfg["max_speed_mps"]), device=device, dtype=dtype)
        self.corrected = torch.zeros(n, m, dtype=torch.bool, device=device)
        # the filter's correction this tick (safe - nominal velocity, [N, M, 3] m/s; zeros when off): read by
        # ste/sweep.SweepGame for L0.12b's "pushed together" tag measurement; it changes no result
        self.correction = torch.zeros(n, m, 3, device=device, dtype=dtype)
        # STE L2.1: the per-pair share of the filter's correction ([N, P, 2] or [P, 2]; None = the even split, today's
        # call bit for bit), set per step by the Starling layer (``set_pair_share``); ``fallback`` [N] bool, the games
        # that took the even split by option B's emergency rule this tick (all False when the share is None)
        self.pair_share: Tensor | None = None
        self.fallback = torch.zeros(n, dtype=torch.bool, device=device)

    # ------------------------------------------------------------------------------------- the filter
    def _filter(self, nominal: Tensor, pos_m: Tensor) -> tuple[Tensor, Tensor]:
        f = self.filter_cfg
        kw = {"alpha": f["alpha"], "iterations": self.filter_iterations, "tolerance": f["tolerance"],
              **self.filter_kwargs}
        if self.pair_share is None:
            res = self._filter_fn(nominal, pos_m, self.pair_mask, f["safety_radius_m"], self._filter_cap_mps, **kw)
        else:                    # option B with its emergency rule (core/safety_filter.filter_velocities_shared)
            res = filter_velocities_shared(nominal, pos_m, self.pair_mask, f["safety_radius_m"], self._filter_cap_mps,
                                           self.pair_share, filter_fn=self._filter_fn, **kw)
            self.fallback = res.fallback
        self.corrected = res.corrected
        self.correction = res.velocities - nominal
        return res.velocities, res.corrected

    def set_pair_mask(self, mask: Tensor) -> None:
        """Replace the filter's pair mask: [M, M] (all games) or [N, M, M] bool (per game, e.g. live drones only).
        Same rules as ``filter_velocities``: symmetric, False on the diagonal, block shaped."""
        self.pair_mask = mask.to(self.device)

    def set_pair_share(self, share: Tensor | None) -> None:
        """Replace the filter's per-pair share (STE L2.1): [P, 2] or [N, P, 2] float (``triu_indices`` pair order; e.g.
        ``core.safety_filter.guard_yields_share``), or None for the even split (today's call, bit for bit)."""
        self.pair_share = None if share is None else share.to(device=self.device, dtype=self.dtype)

    # ------------------------------------------------------------------------------------- interface
    def step(self, cmd_mps: Tensor, pos_m: Tensor, landing: Tensor | None = None) -> tuple[Tensor, Tensor, Tensor]:
        """One 0.05 s tick: commands [N, M, 3] and measured positions [N, M, 3], world ENU. ``landing`` [N, M] bool
        (STE L2.3; None = none, today's path): those drones' commands are the LANDING nominal
        (``TeleopCommander.step``).

        Returns the trajectory setpoint (p_sp_m, v_ff_mps, a_ff_mps2), each [N, M, 3] ENU; also kept in
        ``setpoint``. ``corrected`` is updated (all False when the filter is off)."""
        safety = self._filter if self.safety_filter else None
        if not self.safety_filter:
            self.corrected = torch.zeros_like(self.corrected)
            self.correction = torch.zeros_like(self.correction)
        if landing is None:
            p_sp, v_ff, a_ff = self.commander.step(cmd_mps.to(self.dtype), pos_m, safety=safety)
        else:
            p_sp, v_ff, a_ff = self.commander.step(cmd_mps.to(self.dtype), pos_m, safety=safety, landing=landing)
        self.setpoint = (p_sp, v_ff, a_ff)
        return p_sp, v_ff, a_ff

    def reset(self, mask: Tensor) -> None:
        """Fresh commander (reference re-seeded at the next step, ramp restarted) where mask [N, M] bool."""
        self.commander.reset(mask)

    def keep_in(self, lo_m: Tensor, hi_m: Tensor, out_hi: Tensor, out_lo: Tensor) -> None:
        """The commander's side of the walls and height band (S2 Task 7b): clamp the reference point into
        [lo_m, hi_m] (broadcastable to [N, M, 3]) and zero the outward part of the published speed and of the ramp on
        every axis the wall clamped (``out_hi`` / ``out_lo`` [N, M, 3] bool: the drone was beyond hi / lo), as the
        real commander's keep_in fence publishes the clipped speed at the wall (``swarm_commander.py`` :2208-2219,
        :2307-2308). See ``core/starling_layer.StarlingLayer.keep_in``."""
        c = self.commander
        c.ref = torch.maximum(torch.minimum(c.ref, hi_m), lo_m)
        c.published = torch.where((out_hi & (c.published > 0)) | (out_lo & (c.published < 0)),
                                  torch.zeros_like(c.published), c.published)
        c.profile = torch.where((out_hi & (c.profile > 0)) | (out_lo & (c.profile < 0)),
                                torch.zeros_like(c.profile), c.profile)
