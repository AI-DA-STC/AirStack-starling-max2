"""S2b Task 2: the one frame crossing, ENU/FLU (game, worlds, Isaac) <-> NED/FRD (PX4 cascade); quaternions WXYZ."""
import math
import pathlib
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.models.frames import (  # noqa: E402
    B_FLU_FRD, P_ENU_NED, QUAT_CONVENTION, quat_from_yaw_enu, quat_mul_wxyz, quat_wxyz_to_rotmat,
    rot_enu_flu_to_ned_frd, rotmat_to_quat_wxyz, tilt_rad, vec_enu_to_ned, vec_ned_to_enu, yaw_enu_to_ned)


def test_frames_known_rotations():                        # Review Focus 1 (the plan's test, verbatim)
    assert yaw_enu_to_ned(torch.tensor(0.0)) == pytest.approx(math.pi / 2)        # nose east
    r = rot_enu_flu_to_ned_frd(quat_wxyz_to_rotmat(quat_from_yaw_enu(torch.tensor(0.0))))
    assert torch.allclose(r @ torch.tensor([1.0, 0, 0]), torch.tensor([0.0, 1, 0]), atol=1e-6)   # body x -> NED east
    assert torch.allclose(r @ torch.tensor([0.0, 0, 1]), torch.tensor([0.0, 0, 1]), atol=1e-6)   # body down -> NED down
    q = torch.randn(100, 4); q = q / q.norm(dim=-1, keepdim=True)
    assert torch.allclose(rotmat_to_quat_wxyz(quat_wxyz_to_rotmat(q)).abs(), q.abs(), atol=1e-5)


def test_convention_is_named_wxyz():
    assert QUAT_CONVENTION == "wxyz"
    q = quat_from_yaw_enu(torch.tensor(0.3))
    assert q[0] == pytest.approx(math.cos(0.15)) and q[3] == pytest.approx(math.sin(0.15))   # w first


def test_constants_are_their_own_inverse():
    eye = torch.eye(3)
    assert torch.equal(P_ENU_NED @ P_ENU_NED, eye) and torch.equal(B_FLU_FRD @ B_FLU_FRD, eye)
    assert torch.equal(P_ENU_NED, torch.tensor([[0.0, 1, 0], [1, 0, 0], [0, 0, -1]]))
    assert torch.equal(B_FLU_FRD, torch.diag(torch.tensor([1.0, -1, -1])))


def test_vec_crossing_matches_matrix_and_round_trips():
    v = torch.randn(5, 3, 3)
    assert torch.allclose(vec_enu_to_ned(v), v @ P_ENU_NED.T)
    assert torch.equal(vec_ned_to_enu(vec_enu_to_ned(v)), v)
    assert torch.equal(vec_enu_to_ned(torch.tensor([1.0, 2.0, 3.0])), torch.tensor([2.0, 1.0, -3.0]))  # east -> NED y


def test_rot_crossing_is_p_r_b_and_a_rotation():
    q = torch.randn(7, 2, 4); q = q / q.norm(dim=-1, keepdim=True)
    r = quat_wxyz_to_rotmat(q)
    r_ned = rot_enu_flu_to_ned_frd(r)
    assert torch.allclose(r_ned, P_ENU_NED @ r @ B_FLU_FRD, atol=1e-6)
    assert torch.allclose(r_ned @ r_ned.transpose(-1, -2), torch.eye(3).expand(7, 2, 3, 3), atol=1e-5)
    assert torch.allclose(torch.linalg.det(r_ned), torch.ones(7, 2), atol=1e-5)          # proper rotation, no mirror
    # a body vector carried to the world either way agrees: (FRD -> NED) = P (FLU -> ENU) B
    v_frd = torch.randn(7, 2, 3)
    via_enu = vec_enu_to_ned((r @ (B_FLU_FRD @ v_frd.unsqueeze(-1))).squeeze(-1))
    assert torch.allclose((r_ned @ v_frd.unsqueeze(-1)).squeeze(-1), via_enu, atol=1e-5)


def test_yaw_crossing_wraps():
    yaw = torch.tensor([0.0, math.pi / 2, math.pi, -math.pi / 2, -math.pi, 3 * math.pi])
    out = yaw_enu_to_ned(yaw)
    # nose east, north, west, south, west, west; NED yaw: north 0, east pi/2, south pi (never -pi), west -pi/2
    expected = torch.tensor([math.pi / 2, 0.0, -math.pi / 2, math.pi, -math.pi / 2, -math.pi / 2])
    assert torch.allclose(out, expected, atol=1e-5)
    assert bool((out > -math.pi).all()) and bool((out <= math.pi).all())


def test_yaw_quat_points_nose_along_yaw():
    yaw = torch.tensor([0.0, 0.7, -2.0])
    r = quat_wxyz_to_rotmat(quat_from_yaw_enu(yaw))
    nose = r[..., :, 0]
    assert torch.allclose(nose, torch.stack((yaw.cos(), yaw.sin(), torch.zeros(3)), dim=-1), atol=1e-6)
    # in NED the nose's heading is the NED yaw
    nose_ned = vec_enu_to_ned(nose)
    assert torch.allclose(torch.atan2(nose_ned[:, 1], nose_ned[:, 0]), yaw_enu_to_ned(yaw), atol=1e-6)


def test_quat_mul_composes_rotations():
    a = torch.randn(9, 4); a = a / a.norm(dim=-1, keepdim=True)
    b = torch.randn(9, 4); b = b / b.norm(dim=-1, keepdim=True)
    assert torch.allclose(quat_wxyz_to_rotmat(quat_mul_wxyz(a, b)), quat_wxyz_to_rotmat(a) @ quat_wxyz_to_rotmat(b),
                          atol=1e-5)


def test_rotmat_to_quat_w_nonnegative_and_near_pi():
    # rotations by (almost) pi, where the trace-based formula is ill-conditioned
    axes = torch.randn(50, 3); axes = axes / axes.norm(dim=-1, keepdim=True)
    ang = torch.full((50, 1), math.pi - 1e-4)
    q = torch.cat(((ang / 2).cos(), (ang / 2).sin() * axes), dim=-1)
    out = rotmat_to_quat_wxyz(quat_wxyz_to_rotmat(q))
    assert bool((out[:, 0] >= 0).all())
    assert torch.allclose(out.norm(dim=-1), torch.ones(50), atol=1e-6)
    assert torch.allclose(quat_wxyz_to_rotmat(out), quat_wxyz_to_rotmat(q), atol=1e-5)


def test_tilt():
    assert tilt_rad(quat_from_yaw_enu(torch.tensor(1.2))) == pytest.approx(0.0, abs=1e-6)
    for ang in (0.1, 0.8, 1.2, 2.5):
        for axis in ([1.0, 0, 0], [0.0, 1, 0], [0.6, 0.8, 0]):
            ax = torch.tensor(axis)
            q = torch.cat((torch.tensor([math.cos(ang / 2)]), math.sin(ang / 2) * ax))
            q = quat_mul_wxyz(quat_from_yaw_enu(torch.tensor(0.9)), q)             # yaw does not change tilt
            assert tilt_rad(q) == pytest.approx(ang, abs=1e-5)
    q = torch.randn(30, 4); q = q / q.norm(dim=-1, keepdim=True)
    r22 = quat_wxyz_to_rotmat(q)[:, 2, 2]
    assert torch.allclose(tilt_rad(q), torch.acos(r22.clamp(-1, 1)), atol=1e-3)
