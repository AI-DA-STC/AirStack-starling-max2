"""The physics backend of the Starling layer (S2b Task 4): the same command chain, then a rigid-body Starling.

With ``[starling_layer] enabled = true`` and ``backend = "physics"`` each drone's command (already capped to its
team's speed) goes through

1. ``models/command_chain.CommandChain``: the SAME commander copy and safety filter the fitted backend uses
   (``core/starling_layer.py``), built from the same parameter file (``cfg.starling.params``, its ``[commander]``
   and ``[filter]`` tables), with the same stick-cap checks, pair masks and early-stop setting
   (``starling_layer.check_commander``, ``filter_pairs``, ``filter_kwargs``);
2. ``models/physics_drone.PhysicsDrone``: PX4 1.14's cascade with the drone's own gains, the rotor model and a
   rigid-body world (``IsaacWorld`` or ``TorchRigidBodyWorld``), 10 physics steps per tick. Its parameters are
   ``cfg.starling.physics_params`` with the ``[physics]`` table of ``configs/s2b.toml`` over them, then by default
   the SIM-ONLY yaw-rate gains of ``cfg.starling.physics_sim_only_gains`` (owner's ruling, 16 November 2026).

Pairs, out drones and walls follow ``StarlingLayer`` (S2 Task 4): the filter sees the live pairs only; a drone that
is out is restarted at its (parked) position every step, at rest, with a fresh commander and cascade, and is
commanded zero; ``keep_in`` clamps the positions, stops the clamped axes and clamps the commander's reference.

World writes (D9): at most two batched writes per tick. Restarts (new games from ``reset`` and the drones that are
out) are applied together, in one ``world.reset`` at the start of the next ``step``; ``keep_in`` makes the other
(``write_clamped``). So between a ``reset`` and the next ``step`` the world still holds the old poses: read the
drones' state after a step. Nothing here draws from the game's random generator (D15).

Yaw (D8): the cascade's yaw setpoint is the game's integrated yaw, the commanded yaw rate its feed-forward.
Shapes: N games, M drones (Guard drones first). Batched; no host reads (the filter's ``check_every`` early stop is
the one allowed host sync, as in the Starling layer).
"""
from __future__ import annotations

import torch
from torch import Tensor

from svg_training.models.command_chain import CommandChain
from svg_training.models.fitted import load_params
from svg_training.models.physics_drone import PhysicsDrone
from svg_training.models.physics_params import PhysicsParams, apply_sim_only_gains, load_physics_params
from svg_training.models.rigid_body import RigidBodyWorld

from .game_config import GameCfg, load_s2b_gates
from .starling_layer import check_commander, filter_fn, filter_kwargs, filter_pairs, resolve_params


def load_game_physics_params(cfg: GameCfg) -> PhysicsParams:
    """The physics parameters of a game: ``cfg.starling.physics_params`` overridden by configs/s2b.toml [physics],
    then the SIM-ONLY gains of ``cfg.starling.physics_sim_only_gains`` ("" = the drone's own gains). The choice is in
    ``params.source["yaw_rate_gains"]`` (``models.physics_params.yaw_gains_text`` prints it for records)."""
    p = load_physics_params(resolve_params(cfg.starling.physics_params), overrides=load_s2b_gates()["physics"])
    return apply_sim_only_gains(p, cfg.starling.physics_sim_only_gains)


class PhysicsLayer:
    """Command chain + physics drone for N games of M drones; the ``StarlingLayer`` contract (module docstring).

    ``status`` is "physics"; ``stick_cap_mps`` the commander's stick cap; ``chain`` (CommandChain) and ``drone``
    (PhysicsDrone) are public for logging and tests; ``params`` the PhysicsParams in use.

    Restart contract (D9): ``reset`` only records the restart; the next ``step`` applies it, together with the
    restarts of the drones that are out, in one world write. Until then the world, ``drone`` and the chain still
    hold the old state. A reader that needs the restarted drones before the next step (a renderer, a test that
    writes the world, ``SvgGame.reset``) calls ``flush()``: it applies the pending restarts now (one world write)
    and does nothing, not even a write, when ``reset`` was not called since the last step or flush.
    """

    status = "physics"

    def __init__(self, cfg: GameCfg, num_games: int, guards: int, strikes: int, device, world: RigidBodyWorld,
                 seed: int = 0):                         # seed: the game seed, for the estimator noise (STE L1.1b)
        m = guards + strikes
        if (world.num_games, world.drones) != (num_games, m):
            raise ValueError(f"the world holds {world.num_games} games x {world.drones} drones; the game needs "
                             f"{num_games} x {m}")
        params = load_params(resolve_params(cfg.starling.params))
        self.stick_cap_mps = check_commander(cfg, params)
        pairs = filter_pairs(cfg, guards, strikes, device)
        self._pairs = pairs[None]                                              # [1, M, M]
        self.chain = CommandChain(num_games, m, params, device, safety_filter=True, pair_mask=pairs,
                                  filter_iterations=cfg.starling.filter_iterations, filter_kwargs=filter_kwargs(cfg),
                                  filter_fn=filter_fn(cfg))
        self.params = load_game_physics_params(cfg)
        self.world = world
        self.drone = PhysicsDrone(world, self.params, device, noise_seed=seed)
        n = num_games
        self._pending = torch.zeros(n, m, dtype=torch.bool, device=device)    # restarts waiting for the next step
        self._pending_pos = torch.zeros(n, m, 3, device=device)
        self._pending_yaw = torch.zeros(n, m, device=device)
        self._alive = torch.ones(n, m, dtype=torch.bool, device=device)        # who was in the game this step
        self._has_pending = False        # Python flag: reset() called since the last step / flush (no host read)

    @property
    def upset(self) -> Tensor:
        """[N, M] bool: drones upset (tilt past 60 deg or non-finite) since their last restart."""
        return self.drone.upset

    def reset(self, mask: Tensor, pos_m: Tensor, yaw: Tensor | None = None) -> None:
        """Restart the drones where mask [N, M] bool is True: level at yaw [N, M] (default 0, nose east), at rest at
        pos_m [N, M, 3], fresh commander and cascade. Applied at the start of the next ``step`` (module docstring)."""
        yaw = torch.zeros_like(self._pending_yaw) if yaw is None else yaw
        self._pending = self._pending | mask
        self._pending_pos = torch.where(mask[..., None], pos_m.to(self._pending_pos.dtype), self._pending_pos)
        self._pending_yaw = torch.where(mask, yaw.to(self._pending_yaw.dtype), self._pending_yaw)
        self._has_pending = True

    def flush(self, seed: int | None = None) -> None:
        """Apply the pending restarts now (class docstring): one world write; nothing at all when none is pending.
        ``seed`` (``SvgGame.reset(seed)``): the estimator noise restarts from it first (STE L1.1b)."""
        self.drone.reseed_noise(seed)                  # None: nothing
        if not self._has_pending:
            return
        pend = self._pending
        self.drone.reset(pend, self._pending_pos, self._pending_yaw)
        self.chain.reset(pend)
        self._pending = torch.zeros_like(self._pending)
        self._has_pending = False

    def step(self, cmd_mps: Tensor, pos_m: Tensor, alive: Tensor, yaw: Tensor | None = None,
             yaw_rate_rad_s: Tensor | None = None) -> tuple[Tensor, Tensor, Tensor]:
        """One 0.05 s tick. cmd_mps [N, M, 3] world ENU m/s (already capped to each team's speed); pos_m [N, M, 3]
        the game's positions (used to place the drones that are out; the commander reads the world's positions);
        alive [N, M] bool; yaw (rad, ENU) and yaw_rate_rad_s [N, M] (default 0).

        Returns (pos_m [N, M, 3], vel_mps [N, M, 3], corrected [N, M] bool: live drones the filter changed)."""
        zero = torch.zeros_like(alive, dtype=self._pending_yaw.dtype)
        yaw = zero if yaw is None else yaw
        yaw_rate_rad_s = zero if yaw_rate_rad_s is None else yaw_rate_rad_s
        self._alive = alive
        self.chain.set_pair_mask(self._pairs & alive[:, :, None] & alive[:, None, :])
        # restarts: pending new games, and the drones that are out (at their parked positions); one world write
        restart = self._pending | ~alive
        pend = self._pending
        self.drone.reset(restart, torch.where(pend[..., None], self._pending_pos, pos_m),
                         torch.where(pend, self._pending_yaw, yaw))
        self.chain.reset(restart)
        self._pending = torch.zeros_like(self._pending)
        self._has_pending = False
        p_sp, v_ff, a_ff = self.chain.step(cmd_mps * alive[..., None], self.drone.pos_m)
        self.drone.step_setpoint(p_sp, v_ff, a_ff, yaw, yaw_rate_rad_s * alive)
        return self.drone.pos_m, self.drone.vel_mps, self.chain.corrected & alive

    def keep_in(self, lo_m: Tensor, hi_m: Tensor) -> Tensor:
        """Walls and height band, as ``StarlingLayer.keep_in``: clamp the positions to [lo_m, hi_m] (each
        broadcastable to [N, M, 3]), stop the drone's speed on every clamped axis (one ``write_clamped``; attitude
        and body rates kept: Isaac sees a small teleport), and clamp the commander's reference and its outward
        published speed and ramp (``CommandChain.keep_in``). Returns the clamped positions [N, M, 3].

        Drones that were out this step are not written: they stay at their parked position in the world (the game
        parks them again), instead of being pulled into an arena corner. A drone whose position is not finite is not
        written either (NaN != NaN would mark it clamped and write a NaN pose); it is already flagged upset."""
        p, v = self.drone.pos_m, self.drone.vel_mps
        q = torch.maximum(torch.minimum(p, hi_m), lo_m)
        hit = q != p
        out_hi, out_lo = p > hi_m, p < lo_m
        write = hit.any(dim=-1) & self._alive & torch.isfinite(p).all(dim=-1)
        self.drone.write_clamped(write, q, torch.where(hit, torch.zeros_like(v), v))
        self.chain.keep_in(lo_m, hi_m, out_hi, out_lo)
        return q
