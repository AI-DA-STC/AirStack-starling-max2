"""The Starling's four rotors: a first-order lag on rotor speed, and the body force and torque they make.

Rotor model, once per physics step (S2b plan, Task 2; D5):
    omega_cmd = sqrt(u * f_max / k_f)                    u in [0, 1] = fraction of one rotor's full thrust
    tau = tau_up_s if omega_cmd > omega else tau_down_s  (CMU system identification: 55 ms up, 85 ms down)
    omega += (omega_cmd - omega) (1 - exp(-dt / tau))    motor lag on;  omega = omega_cmd with motor lag off
    F_i = k_f omega_i^2                                  thrust of rotor i, newtons

Body wrench of the four thrusts, worked out in PX4's body frame FRD (as PX4's ActuatorEffectivenessRotors):
    force  = (0, 0, -sum F_i)
    torque = sum r_i x (0, 0, -F_i) + (0, 0, sign(KM_i) (k_m / k_f) F_i),  r_i = (x_i, y_i, 0)
then turned into FLU with B_FLU_FRD (models/frames.py), the frame the worlds take. Rotor order and signs are PX4's
(0 front right, 1 back left, 2 front left, 3 back right; KM > 0 for rotors 0 and 1). ``geometry`` picks the rotor
positions: "cad" (CMU's CAD arms, the plant default, D4) or "params" (the drone's CA_ROTOR* values).
"""
from __future__ import annotations

import functools
import math

import torch
from torch import Tensor

from .physics_params import G_MPS2, ROTOR_GEOMETRIES, AirframeParams


def hover_omega_rad_s(a: AirframeParams) -> float:
    """Rotor speed at which four rotors hold the weight (Python number, rad/s)."""
    return math.sqrt(a.mass_kg * G_MPS2 / 4.0 / a.k_f)


class RotorModel:
    """Rotor speeds of N games x M drones x 4 rotors. Batched; no host reads in ``step`` or ``reset``.

    ``omega_rad_s`` [N, M, 4] starts at hover speed.
    """

    def __init__(self, n: int, m: int, a: AirframeParams, motor_lag: bool, dt_s: float, device) -> None:
        self.a = a
        self.motor_lag = motor_lag
        self.dt_s = dt_s
        self.device = torch.device(device)
        self._omega_cmd_per_u = a.f_max_n() / a.k_f                 # omega_cmd^2 = u * f_max / k_f
        self._alpha_up = 1.0 - math.exp(-dt_s / a.tau_up_s)
        self._alpha_down = 1.0 - math.exp(-dt_s / a.tau_down_s)
        self._omega_hover = hover_omega_rad_s(a)
        self.omega_rad_s: Tensor = torch.full((n, m, 4), self._omega_hover, device=self.device)

    def reset(self, mask: Tensor) -> None:
        """Rotors of the drones where ``mask`` [N, M] (bool) is True go to hover speed; the others keep theirs."""
        self.omega_rad_s = torch.where(mask.unsqueeze(-1), torch.full_like(self.omega_rad_s, self._omega_hover),
                                       self.omega_rad_s)

    def step(self, u: Tensor) -> Tensor:
        """One physics step. ``u`` [N, M, 4] rotor command (clamped to [0, 1]) -> thrust [N, M, 4] in newtons."""
        omega_cmd = torch.sqrt(u.clamp(0.0, 1.0) * self._omega_cmd_per_u)
        if self.motor_lag:
            up = (omega_cmd > self.omega_rad_s).to(omega_cmd.dtype)
            alpha = self._alpha_down + (self._alpha_up - self._alpha_down) * up
            self.omega_rad_s = self.omega_rad_s + (omega_cmd - self.omega_rad_s) * alpha
        else:
            self.omega_rad_s = omega_cmd
        return self.a.k_f * self.omega_rad_s * self.omega_rad_s


@functools.lru_cache(maxsize=32)
def _mixer_flu(a: AirframeParams, geometry: str, device: torch.device, dtype: torch.dtype) -> Tensor:
    """[6, 4]: rotor thrusts -> (force_FLU, torque_FLU). Built once per (airframe, geometry, device, dtype).

    Assumes ONE airframe per run (the cache holds 32 entries). Randomising the airframe per reset (domain
    randomisation) would build a new matrix on the host and copy it to the device inside the step, a host sync:
    that needs a batched per-drone mixer instead, not this cache.
    """
    if geometry not in ROTOR_GEOMETRIES:
        raise ValueError(f"rotor geometry must be one of {ROTOR_GEOMETRIES}, got {geometry!r}")
    xy = a.rotor_xy_cad_m if geometry == "cad" else a.rotor_xy_params_m
    yaw_arm_m = a.k_m / a.k_f
    cols = []
    for (x, y), km in zip(xy, a.rotor_km):
        # FRD per newton: force (0, 0, -1); torque r x (0, 0, -1) = (-y, x, 0), plus the reaction (0, 0, +-k_m/k_f)
        f_frd = (0.0, 0.0, -1.0)
        t_frd = (-y, x, math.copysign(yaw_arm_m, km))
        # FLU = B_FLU_FRD @ FRD = (x, -y, -z)
        cols.append((f_frd[0], -f_frd[1], -f_frd[2], t_frd[0], -t_frd[1], -t_frd[2]))
    return torch.tensor(cols, dtype=dtype).T.contiguous().to(device)


def body_wrench_flu(thrust_n: Tensor, a: AirframeParams, geometry: str) -> tuple[Tensor, Tensor]:
    """Rotor thrusts [N, M, 4] (newtons) -> force_b [N, M, 3] (N) and torque_b [N, M, 3] (N m), both body FLU.

    The mixer matrix is cached per device and dtype, so after the first call this copies nothing to the device
    (one airframe per run; see ``_mixer_flu``).
    Product then sum (not a matmul): a matmul's fused multiply-add leaves a ~1e-9 N m yaw residue when four equal
    thrusts should cancel exactly, and the hover drone of the torch world would then slowly spin.
    """
    w = _mixer_flu(a, geometry, thrust_n.device, thrust_n.dtype)
    wrench = (thrust_n.unsqueeze(-2) * w).sum(-1)                    # [..., 1, 4] * [6, 4] -> [..., 6]
    return wrench[..., :3], wrench[..., 3:]
