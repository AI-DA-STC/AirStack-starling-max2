"""The rigid-body world behind the physics drone: one protocol, two implementations.

``RigidBodyWorld`` is what ``PhysicsDrone`` (Task 4) talks to. ``IsaacWorld`` (``compat/isaaclab_232.py``, Task 5)
integrates the bodies in PhysX; ``TorchRigidBodyWorld`` (here) integrates the same equations in plain PyTorch, so
every CPU test runs without Isaac Sim and the Isaac world can be checked against it under the same forces.

Frames and units: world ENU, body FLU, quaternions WXYZ body -> world (``models/frames.py``); metres, seconds,
newtons, radians. State per drone: position ``pos_m``, attitude ``quat_wxyz``, world linear velocity
``lin_vel_w`` (ENU, m/s) and body angular velocity ``ang_vel_b`` (FLU, rad/s). Each drone is one rigid body with
the CMU mass and diagonal inertia, centre of mass at the body origin, no collider, no damping (D2).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import torch
from torch import Tensor

from .frames import quat_mul_wxyz, quat_wxyz_to_rotmat
from .physics_params import G_MPS2, AirframeParams

TORCH_WORLD_LABEL: str = "torch-reference (test oracle)"


@runtime_checkable
class RigidBodyWorld(Protocol):
    """N games x M drones of rigid bodies. Every method is batched; none reads a tensor on the host."""

    num_games: int
    drones: int
    dt_s: float
    label: str
    device: torch.device

    def reset(self, mask: Tensor, pos_m: Tensor, quat_wxyz: Tensor) -> None:
        """Where ``mask`` [N, M]: put the drone at ``pos_m`` [N, M, 3] with ``quat_wxyz`` [N, M, 4], at rest."""

    def write_state(self, mask: Tensor, pos_m: Tensor, quat_wxyz: Tensor, lin_vel_mps: Tensor,
                    ang_vel_b_rad_s: Tensor) -> None:
        """Where ``mask`` [N, M]: set the full state (shapes as ``state()``); elsewhere unchanged. One batched write."""

    def apply_wrench_b(self, force_b: Tensor, torque_b: Tensor) -> None:
        """Body-frame (FLU) force [N, M, 3] (N) and torque [N, M, 3] (N m), held until the next call."""

    def step(self) -> None:
        """Advance every body by one physics step of ``dt_s``."""

    def state(self) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        """pos_m [N, M, 3], quat_wxyz [N, M, 4], lin_vel_w [N, M, 3] (ENU), ang_vel_b [N, M, 3] (FLU)."""


class TorchRigidBodyWorld:
    """Plain-PyTorch rigid bodies, semi-implicit Euler in PhysX's order (the test oracle).

    Per step, with the held body wrench (f_b, tau_b), R = body -> world rotation, I = diag inertia:
        v   += (R f_b / m + (0, 0, -g)) dt
        w_b += I^-1 (tau_b - w_b x I w_b) dt
        p   += v dt                                     (new v)
        q   <- normalise(q (x) [cos(|w| dt / 2), sin(|w| dt / 2) w / |w|])      (new w, body frame: right product)

    The order matters: the S2b headless Isaac spike (runs/sdd/s2b/isaac-spike-report.md) found PhysX overshoots
    the exact constant-acceleration distance by (n + 1) / n, as this order does; tests/test_rigid_body.py pins it.

    ``dtype`` (default float32) is an addition to the plan's signature, for float64 oracle tests. State tensors are
    replaced (never changed in place), so tensors returned by ``state()`` stay as they were.
    """

    def __init__(self, num_games: int, drones: int, a: AirframeParams, dt_s: float, device,
                 dtype: torch.dtype = torch.float32) -> None:
        self.num_games = num_games
        self.drones = drones
        self.dt_s = dt_s
        self.label = TORCH_WORLD_LABEL
        self.device = torch.device(device)
        self.dtype = dtype
        self.a = a
        self._inv_mass = 1.0 / a.mass_kg
        n, m = num_games, drones
        kw = dict(device=self.device, dtype=dtype)
        self._inertia = torch.tensor(a.inertia_kgm2, dtype=dtype).to(self.device)        # [3], once
        self._inv_inertia = 1.0 / self._inertia
        self.pos_m = torch.zeros(n, m, 3, **kw)
        self.quat_wxyz = torch.zeros(n, m, 4, **kw)
        self.quat_wxyz[..., 0] = 1.0
        self.lin_vel_w = torch.zeros(n, m, 3, **kw)
        self.ang_vel_b = torch.zeros(n, m, 3, **kw)
        self.force_b = torch.zeros(n, m, 3, **kw)
        self.torque_b = torch.zeros(n, m, 3, **kw)

    def reset(self, mask: Tensor, pos_m: Tensor, quat_wxyz: Tensor) -> None:
        """Where ``mask`` [N, M]: pose from ``pos_m`` [N, M, 3], ``quat_wxyz`` [N, M, 4]; velocities zero.

        The held wrench is left as it is (as Isaac's permanent wrench); the next ``apply_wrench_b`` replaces it.
        """
        self.write_state(mask, pos_m, quat_wxyz, torch.zeros_like(self.lin_vel_w), torch.zeros_like(self.ang_vel_b))

    def write_state(self, mask: Tensor, pos_m: Tensor, quat_wxyz: Tensor, lin_vel_mps: Tensor,
                    ang_vel_b_rad_s: Tensor) -> None:
        """Where ``mask`` [N, M]: the given state (shapes as ``state()``); elsewhere unchanged."""
        k = mask.unsqueeze(-1)
        self.pos_m = torch.where(k, pos_m, self.pos_m)
        self.quat_wxyz = torch.where(k, quat_wxyz, self.quat_wxyz)
        self.lin_vel_w = torch.where(k, lin_vel_mps, self.lin_vel_w)
        self.ang_vel_b = torch.where(k, ang_vel_b_rad_s, self.ang_vel_b)

    def apply_wrench_b(self, force_b: Tensor, torque_b: Tensor) -> None:
        """Body FLU force [N, M, 3] and torque [N, M, 3], copied and held until the next call."""
        self.force_b = force_b.clone()
        self.torque_b = torque_b.clone()

    def step(self) -> None:
        """One semi-implicit Euler step of ``dt_s``."""
        dt = self.dt_s
        r = quat_wxyz_to_rotmat(self.quat_wxyz)                                  # [N, M, 3, 3] body -> world
        acc = (r @ self.force_b.unsqueeze(-1)).squeeze(-1) * self._inv_mass
        acc = torch.cat((acc[..., :2], acc[..., 2:] - G_MPS2), dim=-1)
        self.lin_vel_w = self.lin_vel_w + acc * dt

        w = self.ang_vel_b
        gyro = torch.linalg.cross(w, self._inertia * w)
        self.ang_vel_b = w + self._inv_inertia * (self.torque_b - gyro) * dt

        self.pos_m = self.pos_m + self.lin_vel_w * dt

        w = self.ang_vel_b
        rate = w.norm(dim=-1, keepdim=True)
        half = 0.5 * rate * dt
        # sin(|w| dt / 2) / |w|, and its limit dt / 2 at |w| = 0
        s = torch.where(rate > 1e-12, torch.sin(half) / rate.clamp_min(1e-12), torch.full_like(rate, 0.5 * dt))
        dq = torch.cat((torch.cos(half), s * w), dim=-1)
        q = quat_mul_wxyz(self.quat_wxyz, dq)
        self.quat_wxyz = q / q.norm(dim=-1, keepdim=True)

    def state(self) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        """pos_m [N, M, 3], quat_wxyz [N, M, 4], lin_vel_w [N, M, 3] (ENU), ang_vel_b [N, M, 3] (FLU)."""
        return self.pos_m, self.quat_wxyz, self.lin_vel_w, self.ang_vel_b
