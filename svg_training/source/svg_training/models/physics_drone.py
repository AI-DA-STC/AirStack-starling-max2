"""The physics drone (S2b tier 2): PX4 1.14's cascade -> rotor model -> body wrench -> a rigid-body world.

``PhysicsDrone.step_setpoint`` takes the commander's trajectory setpoint for one 0.05 s game tick (world ENU, as
``models/command_chain.CommandChain`` makes it) and flies it for ``round(0.05 / dt)`` physics steps (10 at the
approved 200 Hz). Per physics step, the closed loop of ``scripts/physics_design_check.py`` ``fly``:

1. read the world state (ENU position and velocity, WXYZ body -> world quaternion, FLU body rates);
2. cross into PX4's frames (``models/frames.py``, the only crossing): ``vec_enu_to_ned`` for position, velocity
   and the three setpoint vectors; ``rot_enu_flu_to_ned_frd`` for the attitude; omega_FRD = (x, -y, -z) of the
   FLU rates; ``yaw_enu_to_ned`` for the yaw setpoint and yaw rate NED = -yaw rate ENU;
3. ``models/px4_cascade.Px4Cascade.step`` -> rotor commands u [N, M, 4];
4. ``models/starling_airframe.RotorModel.step`` (motor lag) -> thrusts -> ``body_wrench_flu`` (plant geometry D4);
5. the wrench through ``torch.nan_to_num`` (D10: one NaN body can break a whole PhysX scene; each drone-step with a
   non-finite wrench is counted in ``nonfinite_count``), then ``world.apply_wrench_b`` and ``world.step``.
   A fresh wrench is applied before every physics step (``world.reset`` zeroes the held one).

Setpoints: the cascade needs finite setpoints (``px4_cascade`` docstring). At the crossing a non-finite setpoint
part is replaced, as PX4 treats NaN, and counted in ``nonfinite_count``: a non-finite feed-forward (v_ff, a_ff,
yaw rate) acts as 0 (PX4's ``addIfNotNanVector3f``); a non-finite position setpoint becomes the drone's position
at the start of the tick, held over the tick's physics steps (a short position hold, not velocity-only control);
a non-finite yaw setpoint becomes the drone's heading at the start of the tick.

Upset (D10): a drone whose tilt passes ``PhysicsParams.upset_tilt_deg`` (60) or whose state or wrench turns
non-finite is ``upset`` until its next reset. ``max_tilt_rad`` is the largest tilt since the reset.

D7: no transport delay and no estimator: the cascade reads the true state; ``setpoint_delay_s`` must be 0.
Shapes: N games x M drones; vectors [N, M, 3]; masks [N, M] bool. Batched; no host reads; the only loop is the
fixed loop over the physics sub-steps of one tick.
"""
from __future__ import annotations

import math

import torch
from torch import Tensor

from .frames import (quat_from_yaw_enu, quat_wxyz_to_rotmat, rot_enu_flu_to_ned_frd, tilt_rad, vec_enu_to_ned,
                     yaw_enu_to_ned)
from .physics_params import PhysicsParams
from .px4_cascade import Px4Cascade
from .rigid_body import RigidBodyWorld
from .starling_airframe import RotorModel, body_wrench_flu

GAME_TICK_S: float = 0.05     # one game tick = core.game_config.TICK_S (models/ does not import core/; a test pins it)


def _finite(x: Tensor) -> Tensor:
    """[N, M] bool: every component of x [N, M, k] is finite."""
    return torch.isfinite(x).all(dim=-1)


def _heading_enu(quat_wxyz: Tensor) -> Tensor:
    """[N, M] heading (rad, ENU, from east) of the body x axis."""
    r = quat_wxyz_to_rotmat(quat_wxyz)
    return torch.atan2(r[..., 1, 0], r[..., 0, 0])


class PhysicsDrone:
    """N games x M rigid-body Starlings under PX4 1.14, in ``world`` (``RigidBodyWorld``: Isaac or the torch oracle).

    State after each call (read from the world): ``pos_m``, ``vel_mps`` [N, M, 3] (ENU), ``quat_wxyz`` [N, M, 4];
    ``tilt_rad``, ``max_tilt_rad`` [N, M]; ``upset`` [N, M] bool since the drone's reset; ``nonfinite_count``
    scalar long (non-finite wrenches and setpoint parts replaced, all drones, since construction).
    """

    def __init__(self, world: RigidBodyWorld, p: PhysicsParams, device) -> None:
        if abs(world.dt_s - p.physics_dt_s) > 1e-12:
            raise ValueError(f"the world steps {world.dt_s} s, the physics parameters say {p.physics_dt_s} s")
        sub = GAME_TICK_S / p.physics_dt_s
        if abs(sub - round(sub)) > 1e-9:
            raise ValueError(f"physics_dt_s {p.physics_dt_s} must divide the {GAME_TICK_S} s game tick")
        if p.setpoint_delay_s != 0.0:
            raise ValueError("setpoint_delay_s must be 0.0: no transport delay is built (S2b plan D7)")
        n, m = world.num_games, world.drones
        self.world, self.p = world, p
        self.device = torch.device(device)
        self.sub = round(sub)
        self.rotors = RotorModel(n, m, p.airframe, p.motor_lag, p.physics_dt_s, self.device)
        self.cascade = Px4Cascade(n, m, p.gains, p.physics_dt_s, self.device)
        self._upset_tilt_rad = math.radians(p.upset_tilt_deg)
        self.upset = torch.zeros(n, m, dtype=torch.bool, device=self.device)
        self.max_tilt_rad = torch.zeros(n, m, device=self.device)
        self.nonfinite_count = torch.zeros((), dtype=torch.long, device=self.device)
        self._read()

    # ------------------------------------------------------------------------------------------- helpers
    def _read(self) -> None:
        """Cache the world state; update tilt, the largest tilt and the upset flags."""
        pos, quat, vel, ang = self.world.state()
        self.pos_m, self.quat_wxyz, self.vel_mps, self._ang_vel_b = pos, quat, vel, ang
        self.tilt_rad = tilt_rad(quat)
        ok = _finite(pos) & _finite(quat) & _finite(vel) & _finite(ang)
        self.max_tilt_rad = torch.maximum(self.max_tilt_rad, torch.where(ok, self.tilt_rad,
                                                                         torch.full_like(self.tilt_rad, math.pi)))
        self.upset = self.upset | ~ok | (self.tilt_rad > self._upset_tilt_rad)

    def _count(self, bad: Tensor) -> None:
        self.nonfinite_count = self.nonfinite_count + bad.sum()

    # ------------------------------------------------------------------------------------------- interface
    def reset(self, mask: Tensor, pos_m: Tensor, yaw_rad: Tensor) -> None:
        """Where mask [N, M]: level at ENU heading yaw_rad [N, M], at pos_m [N, M, 3], at rest; rotors at hover
        speed; cascade integrators and filters fresh; upset and largest tilt cleared. One world write."""
        self.world.reset(mask, pos_m, quat_from_yaw_enu(yaw_rad))
        self.rotors.reset(mask)
        self.cascade.reset(mask)
        self.upset = self.upset & ~mask
        self.max_tilt_rad = torch.where(mask, torch.zeros_like(self.max_tilt_rad), self.max_tilt_rad)
        self._read()

    def step_setpoint(self, p_sp_m: Tensor, v_ff_mps: Tensor, a_ff_mps2: Tensor, yaw_sp_rad: Tensor,
                      yaw_rate_rad_s: Tensor) -> None:
        """Fly one game tick: the setpoint (ENU: p_sp_m, v_ff_mps, a_ff_mps2 [N, M, 3]; yaw_sp_rad, yaw_rate_rad_s
        [N, M]) is held over ``round(0.05 / dt)`` physics steps. Non-finite parts are replaced (module docstring)."""
        bad = [~_finite(p_sp_m), ~_finite(v_ff_mps), ~_finite(a_ff_mps2), ~torch.isfinite(yaw_sp_rad),
               ~torch.isfinite(yaw_rate_rad_s)]
        self._count(torch.stack(bad))
        p_sp_m = torch.where(bad[0][..., None], self.pos_m, p_sp_m)
        v_ff_mps = torch.where(bad[1][..., None], torch.zeros_like(v_ff_mps), v_ff_mps)
        a_ff_mps2 = torch.where(bad[2][..., None], torch.zeros_like(a_ff_mps2), a_ff_mps2)
        yaw_sp_rad = torch.where(bad[3], _heading_enu(self.quat_wxyz), yaw_sp_rad)
        yaw_rate_rad_s = torch.where(bad[4], torch.zeros_like(yaw_rate_rad_s), yaw_rate_rad_s)
        # the crossing into PX4's frames, once per tick for the held setpoint
        p_sp, v_ff, a_ff = vec_enu_to_ned(p_sp_m), vec_enu_to_ned(v_ff_mps), vec_enu_to_ned(a_ff_mps2)
        yaw_sp, yaw_ff = yaw_enu_to_ned(yaw_sp_rad), -yaw_rate_rad_s
        a, geometry = self.p.airframe, self.p.rotor_geometry
        for _ in range(self.sub):                     # fixed physics sub-steps of one tick, not a loop over games
            ang = self._ang_vel_b
            r_ned_frd = rot_enu_flu_to_ned_frd(quat_wxyz_to_rotmat(self.quat_wxyz))
            omega_frd = torch.stack((ang[..., 0], -ang[..., 1], -ang[..., 2]), dim=-1)
            u = self.cascade.step(p_sp, v_ff, a_ff, yaw_sp, yaw_ff, vec_enu_to_ned(self.pos_m),
                                  vec_enu_to_ned(self.vel_mps), r_ned_frd, omega_frd)
            force, torque = body_wrench_flu(self.rotors.step(u), a, geometry)
            ok = _finite(force) & _finite(torque)
            self._count(~ok)
            self.upset = self.upset | ~ok
            self.world.apply_wrench_b(torch.nan_to_num(force, nan=0.0, posinf=0.0, neginf=0.0),
                                      torch.nan_to_num(torque, nan=0.0, posinf=0.0, neginf=0.0))
            self.world.step()
            self._read()

    def write_clamped(self, mask: Tensor, pos_m: Tensor, vel_mps: Tensor) -> None:
        """Where mask [N, M]: position pos_m and world velocity vel_mps [N, M, 3] (ENU) from the game's walls and
        height band; attitude and body rates kept. One world write."""
        self.world.write_state(mask, pos_m, self.quat_wxyz, vel_mps, self._ang_vel_b)
        self._read()
