"""Response model at the plug-in point (NumPy reference): teleop velocity command -> measured velocity.

The model is a black box from the command a policy sends (`/svg/<drone>/teleop_command`, world ENU, m/s)
to the drone's measured velocity (odometry, world ENU, m/s). It stands for everything in between: the
ground controller's shaping (ramp at `teleop_accel_mps2`, P term on the leashed reference point, speed
cap), the MAVROS link and PX4's position/velocity/attitude loops. It does not re-implement the commander.

Time grid and indexing (read this before porting)
-------------------------------------------------
`cmd[k]` is the command held over the cell [t_k, t_k + dt) (zero-order hold; `fit.resample_uniform`
cell-averages a command that switches inside a cell). `simulate` returns `v[k]`, the velocity AT t_k:
`v[0] = v0_mps` and `v[k+1] = step(v[k], cmd up to k)`. A batched `step(cmd_k)` that returns the state
after the step therefore reproduces `simulate(cmd)[1:]` (Task 8's comparison).

One step, k -> k+1 (fixed order, every operation over the 3 axes):
  1. speed cap on the command norm:   c[k] = cmd[k] * min(1, speed_cap / max(|cmd[k]|, 1e-9))
  2. fractional delay, D = delay_s / dt, n = floor(D), f = D - n:
                                       u[k] = (1 - f) * c[k - n] + f * c[k - n - 1]     (c[j < 0] = 0)
     For a zero-order-hold signal this is exactly the average of c over the shifted cell
     [t_k - delay, t_k + dt - delay).
  3. first-order lag, exact for a held input:  dv = alpha * (u[k] - x[k]),  alpha = 1 - exp(-dt / tau)
     (tau_xy_s for x and y, tau_z_s for z; alpha = 1 when tau = 0)
  4. acceleration limit:  horizontal (dv_x, dv_y) scaled down to norm <= acc_max_xy * dt (tilt limit);
                          dv_z clipped to [-acc_max_z * dt, +acc_max_z * dt]
  5. x[k+1] = x[k] + dv
  6. family "lag1": v[k+1] = x[k+1]
     family "lag2": v[k+1] = v[k] + alpha2 * (x[k+1] - v[k]),  alpha2 = 1 - exp(-dt / tau2_s)
                    (alpha2 = 1 when tau2_s = 0, so lag2 equals lag1 exactly)
Initial state: x[0] = v[0] = v0_mps (zeros by default); commands before t_0 are zero (drone at rest).

Odometry frame (checked 15 November 2026, read-only)
----------------------------------------------------
The measured velocity comes from `/<drone>/odometry_conversion/odometry`, which is MAVROS
`local_position/odom` (`interface_bringup/launch/interface.launch.py:43-45`) relabelled by
`odometry_conversion` in OVERWRITE mode (`interface.launch.py:123`; `robot_interface/src/
odometry_conversion.cpp:128-130` rewrites only `frame_id`/`child_frame_id`, the twist is untouched).
MAVROS publishes that twist in the BODY frame (`child_frame_id` base_link, FLU), not in world ENU.
Rotate it with `body_to_world(v_body, q)` (q = odometry orientation, w x y z) before fitting. At yaw 0 and
level flight the two frames coincide, which is why the commander, which reads the twist as world
(`swarm_commander.py:1406-1412`), works in the hover tests.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields

import numpy as np

FAMILIES = ("lag1", "lag2")


@dataclass(frozen=True)
class ResponseParams:
    """Parameters of the response model; all SI, all plain floats (TOML-friendly)."""

    delay_s: float
    tau_xy_s: float
    tau_z_s: float
    acc_max_xy_mps2: float
    acc_max_z_mps2: float
    speed_cap_mps: float
    family: str = "lag1"
    tau2_s: float = 0.0

    def __post_init__(self):
        if self.family not in FAMILIES:
            raise ValueError(f"family must be one of {FAMILIES}, got {self.family!r}")
        for f in fields(self):
            if f.name == "family":
                continue
            value = float(getattr(self, f.name))
            object.__setattr__(self, f.name, value)
            if math.isnan(value) or value < 0.0:
                raise ValueError(f"{f.name} must be >= 0, got {value}")
        for name in ("acc_max_xy_mps2", "acc_max_z_mps2", "speed_cap_mps"):
            if getattr(self, name) <= 0.0:
                raise ValueError(f"{name} must be > 0 (use inf for no limit)")
        if self.family == "lag1" and self.tau2_s != 0.0:
            raise ValueError("tau2_s is a lag2 parameter; lag1 needs tau2_s = 0")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ResponseParams":
        names = {f.name for f in fields(cls)}
        unknown = set(d) - names
        if unknown:
            raise ValueError(f"unknown ResponseParams keys: {sorted(unknown)}")
        return cls(**d)


def lag_alpha(dt_s: float, tau_s: float) -> float:
    """Exact zero-order-hold gain of a first-order lag over one step: 1 - exp(-dt/tau); 1 when tau = 0."""
    if tau_s <= 0.0:
        return 1.0
    return -math.expm1(-dt_s / tau_s)


def cap_speed(cmd_mps: np.ndarray, speed_cap_mps: float) -> np.ndarray:
    """Scale each command (..., 3) down to norm <= speed_cap_mps (as the commander and the placeholder)."""
    cmd = np.asarray(cmd_mps, dtype=float)
    norm = np.linalg.norm(cmd, axis=-1, keepdims=True)
    return cmd * np.minimum(1.0, speed_cap_mps / np.maximum(norm, 1e-9))


def delay_command(cmd_mps: np.ndarray, dt_s: float, delay_s: float) -> np.ndarray:
    """Fractional delay (T, 3) -> (T, 3) by linear interpolation; commands before t_0 are zero."""
    cmd = np.asarray(cmd_mps, dtype=float)
    d = delay_s / dt_s
    n = int(math.floor(d))
    f = d - n
    padded = np.concatenate([np.zeros((n + 1, 3)), cmd], axis=0)    # padded[j + n + 1] = cmd[j]
    t = cmd.shape[0]
    a = padded[1:t + 1]          # cmd[k - n]
    b = padded[0:t]              # cmd[k - n - 1]
    return (1.0 - f) * a + f * b


def simulate(cmd: np.ndarray, dt_s: float, p: ResponseParams, v0_mps: np.ndarray | None = None) -> np.ndarray:
    """Velocity (T, 3) at t_k = k*dt for the command (T, 3) held over [t_k, t_k + dt). See the module doc."""
    cmd = np.asarray(cmd, dtype=float)
    if cmd.ndim != 2 or cmd.shape[1] != 3:
        raise ValueError(f"cmd must be (T, 3), got {cmd.shape}")
    if not dt_s > 0.0:
        raise ValueError("dt_s must be > 0")
    u = delay_command(cap_speed(cmd, p.speed_cap_mps), dt_s, p.delay_s).tolist()
    a_xy = lag_alpha(dt_s, p.tau_xy_s)
    a_z = lag_alpha(dt_s, p.tau_z_s)
    a_2 = lag_alpha(dt_s, p.tau2_s) if p.family == "lag2" else 1.0
    lim_xy = p.acc_max_xy_mps2 * dt_s
    lim_z = p.acc_max_z_mps2 * dt_s
    v0 = np.zeros(3) if v0_mps is None else np.asarray(v0_mps, dtype=float).reshape(3)
    x0, x1, x2 = (float(c) for c in v0)          # first stage
    w0, w1, w2 = x0, x1, x2                      # output (second stage for lag2)
    out = [None] * cmd.shape[0]
    out[0] = (w0, w1, w2)
    for k in range(cmd.shape[0] - 1):
        u0, u1, u2 = u[k]
        d0 = a_xy * (u0 - x0)
        d1 = a_xy * (u1 - x1)
        d2 = a_z * (u2 - x2)
        s = min(1.0, lim_xy / max(math.hypot(d0, d1), 1e-12))
        d0 *= s
        d1 *= s
        d2 = min(max(d2, -lim_z), lim_z)
        x0 += d0
        x1 += d1
        x2 += d2
        if a_2 == 1.0:
            w0, w1, w2 = x0, x1, x2
        else:
            w0 += a_2 * (x0 - w0)
            w1 += a_2 * (x1 - w1)
            w2 += a_2 * (x2 - w2)
        out[k + 1] = (w0, w1, w2)
    return np.array(out, dtype=float).reshape(cmd.shape[0], 3)


def body_to_world(v_body: np.ndarray, q_wxyz: np.ndarray) -> np.ndarray:
    """Rotate body-frame vectors (T, 3) into the world frame with unit quaternions (T, 4) in w, x, y, z order."""
    v = np.asarray(v_body, dtype=float)
    q = np.asarray(q_wxyz, dtype=float)
    q = q / np.linalg.norm(q, axis=-1, keepdims=True)
    w, xyz = q[..., :1], q[..., 1:]
    t = 2.0 * np.cross(xyz, v)
    return v + w * t + np.cross(xyz, t)
