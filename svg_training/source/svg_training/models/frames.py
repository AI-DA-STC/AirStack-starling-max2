"""The one frame crossing of the physics backend, and the one quaternion convention (STANDARDS §6 rule 8).

Frames
------
- The game, the rigid-body worlds and Isaac Lab work in **ENU** (world: x east, y north, z up) with a **FLU** body
  (x forward, y left, z up).
- The PX4 cascade (``models/px4_cascade.py``) is ported line by line from PX4 1.14, so it works in PX4's own frames:
  **NED** world (x north, y east, z down) and an **FRD** body (x forward, y right, z down).
- Nothing else converts between them: every crossing goes through this module.

  ``v_ned = P_ENU_NED @ v_enu`` (P swaps x and y and flips z; it is its own inverse);
  ``v_frd = B_FLU_FRD @ v_flu`` (B flips y and z; its own inverse);
  ``R_ned_frd = P_ENU_NED @ R_enu_flu @ B_FLU_FRD`` (body -> world rotation matrices).
  Yaw: ENU yaw is measured from east, counter-clockwise seen from above; NED yaw from north, clockwise, so
  ``yaw_ned = pi/2 - yaw_enu``.

Quaternions
-----------
Every quaternion in S2b is **WXYZ** (scalar first, Isaac Lab 2.3.2's order) and is named ``quat_wxyz`` (or
``q_wxyz``). It rotates body vectors into the world (body -> world), the same as Isaac Lab's ``root_quat_w``.
Isaac Lab 3.0 flips the order to XYZW: the adapter (``compat/isaaclab_232.py``) converts there and nowhere else.

All functions are batched over any leading dimensions, run on the input's device and dtype, and copy nothing
between host and device (no constant tensors are moved in the step: the fixed permutations are written out).
"""
from __future__ import annotations

import math

import torch
from torch import Tensor

QUAT_CONVENTION: str = "wxyz"     # the one named convention (STANDARDS §6 rule 8)

# Reference matrices (CPU, float32) for documentation and tests; the functions below apply them without a copy.
P_ENU_NED: Tensor = torch.tensor([[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, -1.0]])
B_FLU_FRD: Tensor = torch.diag(torch.tensor([1.0, -1.0, -1.0]))


def quat_wxyz_to_rotmat(q: Tensor) -> Tensor:
    """Unit quaternion [..., 4] (w, x, y, z) -> rotation matrix [..., 3, 3], body -> world."""
    w, x, y, z = q.unbind(-1)
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    rows = (
        torch.stack((1 - 2 * (yy + zz), 2 * (xy - wz), 2 * (xz + wy)), dim=-1),
        torch.stack((2 * (xy + wz), 1 - 2 * (xx + zz), 2 * (yz - wx)), dim=-1),
        torch.stack((2 * (xz - wy), 2 * (yz + wx), 1 - 2 * (xx + yy)), dim=-1),
    )
    return torch.stack(rows, dim=-2)


def rotmat_to_quat_wxyz(r: Tensor) -> Tensor:
    """Rotation matrix [..., 3, 3] -> unit quaternion [..., 4] (w, x, y, z) with w >= 0.

    Branch-free Shepperd method: the four candidate quaternions are built and the best-conditioned one (largest
    of 1 +- trace terms) is picked with ``gather``, so rotations near pi stay accurate and nothing syncs the host.
    """
    m00, m01, m02 = r[..., 0, 0], r[..., 0, 1], r[..., 0, 2]
    m10, m11, m12 = r[..., 1, 0], r[..., 1, 1], r[..., 1, 2]
    m20, m21, m22 = r[..., 2, 0], r[..., 2, 1], r[..., 2, 2]
    four_sq = torch.stack((1 + m00 + m11 + m22, 1 + m00 - m11 - m22,
                           1 - m00 + m11 - m22, 1 - m00 - m11 + m22), dim=-1)      # 4 w^2, 4 x^2, 4 y^2, 4 z^2
    root = four_sq.clamp_min(0.0).sqrt()                                         # 2|w|, 2|x|, 2|y|, 2|z|
    cand = torch.stack((
        torch.stack((four_sq[..., 0], m21 - m12, m02 - m20, m10 - m01), dim=-1),    # each row = 4 * that component
        torch.stack((m21 - m12, four_sq[..., 1], m10 + m01, m02 + m20), dim=-1),    # x (2|x|) quaternion
        torch.stack((m02 - m20, m10 + m01, four_sq[..., 2], m12 + m21), dim=-1),
        torch.stack((m10 - m01, m20 + m02, m21 + m12, four_sq[..., 3]), dim=-1),
    ), dim=-2) / (2.0 * root.clamp_min(1e-12)).unsqueeze(-1)
    best = root.argmax(dim=-1, keepdim=True)                                     # [..., 1]
    q = torch.gather(cand, -2, best.unsqueeze(-1).expand(*best.shape[:-1], 1, 4)).squeeze(-2)
    q = q / q.norm(dim=-1, keepdim=True)
    return torch.where(q[..., :1] < 0, -q, q)


def quat_mul_wxyz(a: Tensor, b: Tensor) -> Tensor:
    """Hamilton product a (x) b of quaternions [..., 4] (w, x, y, z): rotation b first, then a."""
    aw, ax, ay, az = a.unbind(-1)
    bw, bx, by, bz = b.unbind(-1)
    return torch.stack((aw * bw - ax * bx - ay * by - az * bz,
                        aw * bx + ax * bw + ay * bz - az * by,
                        aw * by - ax * bz + ay * bw + az * bx,
                        aw * bz + ax * by - ay * bx + az * bw), dim=-1)


def rot_enu_flu_to_ned_frd(r_enu_flu: Tensor) -> Tensor:
    """Body -> world rotation [..., 3, 3] from ENU/FLU to NED/FRD: P_ENU_NED @ R @ B_FLU_FRD."""
    pr = torch.stack((r_enu_flu[..., 1, :], r_enu_flu[..., 0, :], -r_enu_flu[..., 2, :]), dim=-2)   # P @ R
    return torch.cat((pr[..., :1], -pr[..., 1:]), dim=-1)                                         # (P @ R) @ B


def vec_enu_to_ned(v: Tensor) -> Tensor:
    """World vector [..., 3] ENU -> NED (x north = ENU y, y east = ENU x, z down = -ENU z)."""
    return torch.stack((v[..., 1], v[..., 0], -v[..., 2]), dim=-1)


def vec_ned_to_enu(v: Tensor) -> Tensor:
    """World vector [..., 3] NED -> ENU (P_ENU_NED is its own inverse)."""
    return torch.stack((v[..., 1], v[..., 0], -v[..., 2]), dim=-1)


def wrap_pi(a_rad: Tensor) -> Tensor:
    """Angle [...] wrapped to (-pi, pi]."""
    return math.pi - torch.remainder(math.pi - a_rad, 2 * math.pi)


def yaw_enu_to_ned(yaw_enu: Tensor) -> Tensor:
    """Heading [...] from ENU (from east, counter-clockwise) to NED (from north, clockwise), wrapped to (-pi, pi]."""
    return wrap_pi(math.pi / 2 - yaw_enu)


def quat_from_yaw_enu(yaw: Tensor) -> Tensor:
    """Level attitude [..., 4] WXYZ with the nose at ENU heading ``yaw`` [...] (radians)."""
    h = 0.5 * yaw
    zero = torch.zeros_like(h)
    return torch.stack((h.cos(), zero, zero, h.sin()), dim=-1)


def tilt_rad(q_wxyz: Tensor) -> Tensor:
    """Angle [...] between the body z axis and the world z axis, in [0, pi], for quaternions [..., 4].

    Uses 2 atan2(|(x, y)|, |(w, z)|): exact for any yaw, accurate near 0 and pi (unlike acos of R[2, 2]).
    """
    w, x, y, z = q_wxyz.unbind(-1)
    return 2.0 * torch.atan2(torch.sqrt(x * x + y * y), torch.sqrt(w * w + z * z))
