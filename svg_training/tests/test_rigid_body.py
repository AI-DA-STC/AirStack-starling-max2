"""S2b Task 2: the pure-PyTorch rigid-body world (test oracle for the cascade and the Isaac adapter)."""
import pathlib
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.models.frames import quat_from_yaw_enu, quat_wxyz_to_rotmat  # noqa: E402
from svg_training.models.physics_params import G_MPS2, load_physics_params  # noqa: E402
from svg_training.models.rigid_body import GYRO_MODES, RigidBodyWorld, TorchRigidBodyWorld  # noqa: E402
from svg_training.models.starling_airframe import RotorModel, body_wrench_flu  # noqa: E402

A = load_physics_params("params/starling_physics_v0.toml").airframe
I_DIAG = torch.tensor(A.inertia_kgm2, dtype=torch.float64)


def _world(n=2, m=3, dt=0.005, dtype=torch.float32):
    w = TorchRigidBodyWorld(n, m, A, dt, "cpu", dtype=dtype)
    pos = torch.zeros(n, m, 3, dtype=dtype)
    pos[..., 2] = 1.0
    w.reset(torch.ones(n, m, dtype=torch.bool), pos, quat_from_yaw_enu(torch.zeros(n, m, dtype=dtype)))
    return w


def test_label_and_protocol():
    w = _world()
    assert isinstance(w, RigidBodyWorld)
    assert w.label == "torch-reference (test oracle)"
    assert (w.num_games, w.drones, w.dt_s) == (2, 3, 0.005)
    p, q, v, om = w.state()
    assert p.shape == (2, 3, 3) and q.shape == (2, 3, 4) and v.shape == (2, 3, 3) and om.shape == (2, 3, 3)


def test_torch_world_free_fall():                         # no wrench, 1 s at 0.005: semi-implicit Euler drop
    w = _world()
    for _ in range(200):
        w.step()
    p, q, v, om = w.state()
    assert torch.allclose(1.0 - p[..., 2], torch.full((2, 3), 9.81 * (1 * 1.005) / 2), atol=1e-4)
    assert torch.allclose(v[..., 2], torch.full((2, 3), -9.81), atol=1e-4)
    assert p[..., :2].abs().max() == 0 and om.abs().max() == 0


def test_integrator_order_is_physx_semi_implicit():
    """Pins the order (PhysX's): velocity first, then position with the NEW velocity; angular velocity first, then
    the quaternion with the NEW rate. After ONE step from rest under constant acceleration a, the position is
    a dt^2: explicit Euler would give 0, the exact solution a dt^2 / 2. Same for the angle under a constant torque.
    """
    dt = 0.005
    w = _world(n=1, m=1, dtype=torch.float64)
    p0 = w.state()[0].clone()
    w.apply_wrench_b(torch.tensor([[[0.0, 0.0, A.mass_kg * (G_MPS2 + 2.0)]]], dtype=torch.float64),
                     torch.tensor([[[1e-3, 0.0, 0.0]]], dtype=torch.float64))                # a = +2 m/s^2 up
    w.step()
    p, q, v, om = w.state()
    alpha = 1e-3 / A.inertia_kgm2[0]
    assert v[0, 0, 2] == pytest.approx(2.0 * dt, rel=1e-12)
    assert (p - p0)[0, 0, 2] == pytest.approx(2.0 * dt * dt, rel=1e-9)                        # not 0, not dt^2 / 2
    assert om[0, 0, 0] == pytest.approx(alpha * dt, rel=1e-12)
    assert 2 * torch.atan2(q[0, 0, 1], q[0, 0, 0]) == pytest.approx(alpha * dt * dt, rel=1e-9)  # roll = alpha dt^2


@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
def test_matches_isaac_spike_checks(dtype):
    """The headless Isaac spike's checks (runs/sdd/s2b/isaac-spike-report.md, 200 Hz): semi-implicit Euler gives
    (n + 1) / n times the exact constant-acceleration distance. Climb 0.5 s at 1.1 x weight: 0.12385 m (PhysX
    observed 0.12385; exact 0.12263). Roll after 0.2 s of a +-1 % roll differential: rate -0.48273 rad/s (PhysX
    -0.48273), angle -2.766 deg x 41 / 40 = -2.835 deg (PhysX observed -2.828 deg; see the Task 2 report)."""
    hover = A.mass_kg * G_MPS2 / 4
    w = _world(n=1, m=1, dtype=dtype)
    w.apply_wrench_b(*body_wrench_flu(torch.full((1, 1, 4), 1.1 * hover, dtype=dtype), A, "cad"))
    for _ in range(100):
        w.step()
    assert w.state()[0][0, 0, 2] - 1.0 == pytest.approx(0.5 * 0.1 * G_MPS2 * 0.005 ** 2 * 100 * 101, abs=2e-6)
    assert w.state()[0][0, 0, 2] - 1.0 == pytest.approx(0.12385, abs=1e-5)

    w = _world(n=1, m=1, dtype=dtype)
    t = torch.tensor([1.01, 0.99, 0.99, 1.01], dtype=dtype).view(1, 1, 4) * hover            # right side (0, 3) up
    w.apply_wrench_b(*body_wrench_flu(t, A, "cad"))
    for _ in range(40):
        w.step()
    _, q, _, om = w.state()
    assert om[0, 0, 0] == pytest.approx(-0.48273, abs=1e-5)
    roll_deg = torch.rad2deg(2 * torch.atan2(q[0, 0, 1], q[0, 0, 0]))
    exact_deg = -0.5 * (0.48273 / 0.2) * 0.2 ** 2 * 180 / torch.pi
    assert roll_deg == pytest.approx(exact_deg * 41 / 40, abs=2e-3)


def test_torch_world_hover_holds():                       # hover wrench 2 s: |dp| < 1e-6, |omega| < 1e-9
    w = _world()
    t = torch.full((2, 3, 4), A.mass_kg * G_MPS2 / 4)
    w.apply_wrench_b(*body_wrench_flu(t, A, "cad"))       # held until the next call
    p0 = w.state()[0].clone()
    for _ in range(400):
        w.step()
    p, q, v, om = w.state()
    assert (p - p0).norm(dim=-1).max() < 1e-6
    assert om.norm(dim=-1).max() < 1e-9


@pytest.mark.parametrize("gyro", GYRO_MODES)
@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
def test_torch_world_spin_conserves_energy(dtype, gyro):  # free tumbling 2 s at dt 1e-4: energy within 1e-3 relative
    w = TorchRigidBodyWorld(2, 3, A, 1e-4, "cpu", dtype=dtype, gyro=gyro)
    p, q, v, _ = w.state()
    om0 = torch.tensor([2.0, -1.0, 1.5], dtype=dtype).expand(2, 3, 3)
    w.write_state(torch.ones(2, 3, dtype=torch.bool), p, q, v, om0)

    inertia = I_DIAG.to(dtype)

    def energy_and_momentum():
        _, q, _, om = w.state()
        e = 0.5 * (inertia * om * om).sum(-1)
        l_world = (quat_wxyz_to_rotmat(q) @ (inertia * om).unsqueeze(-1)).squeeze(-1)
        return e, l_world

    e0, l0 = energy_and_momentum()
    for _ in range(20000):
        w.step()
    e1, l1 = energy_and_momentum()
    assert ((e1 - e0).abs() / e0).max() < 1e-3
    assert ((l1 - l0).norm(dim=-1) / l0.norm(dim=-1)).max() < 1e-3      # world angular momentum kept too
    _, q, _, om = w.state()
    assert not torch.allclose(om, om0, atol=1e-2)                          # it really tumbled (asymmetric inertia)
    assert torch.allclose(q.norm(dim=-1), torch.ones(2, 3, dtype=dtype), atol=1e-6)


def test_gyro_option_default_is_physx():
    assert GYRO_MODES == ("momentum_preserving", "explicit")
    assert _world().gyro == "momentum_preserving"                         # PhysX 5's own update (see the docstring)
    with pytest.raises(ValueError, match="gyro"):
        TorchRigidBodyWorld(1, 1, A, 0.005, "cpu", gyro="implicit")


RATE_LIMITS_RAD_S = torch.deg2rad(torch.tensor([130.0, 130.0, 150.0], dtype=torch.float64))   # MC_*RATE_MAX


@pytest.mark.parametrize("signs", [(1.0, 1.0, 1.0), (1.0, -1.0, 1.0)])
def test_energy_drift_at_200hz_rate_limits(signs):
    """Documents the drift at the operating step (200 Hz) for both options: free tumbling for 2 s, starting at the
    drone's rate limits. Measured 16 Nov 2026 (float64): explicit +3.0 % / +2.5 % energy and +1.1 % / +0.8 %
    angular momentum; momentum_preserving (PhysX) +0.8 % energy, angular momentum kept to 1e-13. Bounds hold the
    measured values with margin; Task 5 compares both with PhysX tumbles."""
    om0 = (RATE_LIMITS_RAD_S * torch.tensor(signs, dtype=torch.float64)).expand(1, 1, 3)
    i_diag = I_DIAG
    drift = {}
    for gyro in GYRO_MODES:
        w = TorchRigidBodyWorld(1, 1, A, 0.005, "cpu", dtype=torch.float64, gyro=gyro)
        p, q, v, _ = w.state()
        w.write_state(torch.ones(1, 1, dtype=torch.bool), p, q, v, om0)
        e0, l0 = 0.5 * (i_diag * om0 * om0).sum(), (i_diag * om0).norm()
        for _ in range(400):
            w.step()
        om = w.state()[3]
        drift[gyro] = ((0.5 * (i_diag * om * om).sum() - e0) / e0, ((i_diag * om).norm() - l0) / l0)
    e_mp, l_mp = drift["momentum_preserving"]
    e_ex, l_ex = drift["explicit"]
    assert 0.0 < e_mp < 0.01 and abs(l_mp) < 1e-9
    assert 0.02 < e_ex < 0.035 and 0.005 < l_ex < 0.015
    assert e_ex > 2.5 * e_mp


def test_body_force_rotates_with_attitude():
    """Thrust along body z of a drone rolled 90 deg about +x (FLU) points along world -y (ENU)."""
    w = _world(n=1, m=1)
    q = torch.tensor([[[2 ** -0.5, 2 ** -0.5, 0.0, 0.0]]])
    p, _, v, om = w.state()
    w.write_state(torch.ones(1, 1, dtype=torch.bool), p, q, v, om)
    w.apply_wrench_b(torch.tensor([[[0.0, 0.0, 1.0]]]), torch.zeros(1, 1, 3))
    w.step()
    v = w.state()[2]
    assert v[0, 0, 1] == pytest.approx(-0.005 / A.mass_kg, rel=1e-5)
    assert v[0, 0, 2] == pytest.approx(-9.81 * 0.005, rel=1e-5)


def test_body_torque_spins_about_body_axis():
    """Torque about body x on a drone yawed 90 deg: rate grows about body x, the world sees roll about north."""
    w = _world(n=1, m=1)
    p, _, v, om = w.state()
    w.write_state(torch.ones(1, 1, dtype=torch.bool), p, quat_from_yaw_enu(torch.full((1, 1), torch.pi / 2)), v, om)
    w.apply_wrench_b(torch.zeros(1, 1, 3), torch.tensor([[[1e-3, 0.0, 0.0]]]))
    for _ in range(10):
        w.step()
    _, q, _, om = w.state()
    assert om[0, 0, 0] == pytest.approx(10 * 0.005 * 1e-3 / A.inertia_kgm2[0], rel=1e-5)
    assert om[0, 0, 1:].abs().max() < 1e-9
    body_y_world = quat_wxyz_to_rotmat(q)[0, 0, :, 1]                      # body left, initially world -x (west)
    assert body_y_world[2] > 0                                             # positive roll lifts the left side


def test_write_state_and_reset_are_masked():
    w = _world()
    p, q, v, om = (x.clone() for x in w.state())
    mask = torch.tensor([[True, False, False], [False, False, True]])
    new_p = p + 5.0
    new_v = torch.ones_like(v)
    w.write_state(mask, new_p, q, new_v, torch.full_like(om, 0.3))
    p2, q2, v2, om2 = w.state()
    assert torch.equal(p2[mask], new_p[mask]) and torch.equal(p2[~mask], p[~mask])
    assert torch.equal(v2[mask], new_v[mask]) and torch.equal(v2[~mask], v[~mask])
    assert torch.equal(om2[~mask], om[~mask]) and torch.allclose(om2[mask], torch.full((2, 3), 0.3))
    w.reset(mask, torch.zeros_like(p), quat_from_yaw_enu(torch.full((2, 3), 0.5)))
    p3, q3, v3, om3 = w.state()
    assert p3[mask].abs().max() == 0 and v3[mask].abs().max() == 0 and om3[mask].abs().max() == 0   # at rest
    assert torch.equal(p3[~mask], p[~mask]) and torch.equal(v3[~mask], v[~mask])
    assert torch.allclose(q3[mask], quat_from_yaw_enu(torch.full((2,), 0.5)))


def test_reset_zeroes_held_wrench_of_reset_drones_only():
    w = _world()
    f, t = torch.full((2, 3, 3), 2.0), torch.full((2, 3, 3), 1e-3)
    w.apply_wrench_b(f, t)
    mask = torch.tensor([[True, False, False], [False, False, True]])
    p, q, _, _ = w.state()
    w.reset(mask, p, q)
    assert w.force_b[mask].abs().max() == 0 and w.torque_b[mask].abs().max() == 0
    assert torch.equal(w.force_b[~mask], f[~mask]) and torch.equal(w.torque_b[~mask], t[~mask])
    w.step()                                                               # a reset drone falls freely from rest
    v, om = w.state()[2], w.state()[3]
    assert torch.allclose(v[mask], torch.tensor([0.0, 0.0, -9.81 * 0.005]).expand(2, 3))
    assert om[mask].abs().max() == 0


def test_rotor_model_and_world_hover_together():
    """Hover command through the lagged rotor model holds a level drone for 1 s (the pieces fit)."""
    w = _world()
    rm = RotorModel(2, 3, A, motor_lag=True, dt_s=0.005, device="cpu")
    p0 = w.state()[0].clone()
    u = torch.full((2, 3, 4), A.hover_u())
    for _ in range(200):
        w.apply_wrench_b(*body_wrench_flu(rm.step(u), A, "cad"))
        w.step()
    p, _, _, om = w.state()
    assert (p - p0).norm(dim=-1).max() < 1e-4 and om.abs().max() < 1e-6


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA only")
@pytest.mark.parametrize("gyro", GYRO_MODES)
def test_rotor_and_world_step_run_under_sync_debug_error(gyro):
    """No host sync in the per-physics-step path (rotor model, wrench, world step) on CUDA."""
    w = TorchRigidBodyWorld(64, 3, A, 0.005, "cuda", gyro=gyro)
    rm = RotorModel(64, 3, A, motor_lag=True, dt_s=0.005, device="cuda")
    u = torch.rand(64, 3, 4, device="cuda")
    mask = torch.rand(64, 3, device="cuda") < 0.5
    w.apply_wrench_b(*body_wrench_flu(rm.step(u), A, "cad"))             # warm-up (builds the cached mixer)
    w.step()
    torch.cuda.set_sync_debug_mode("error")
    try:
        for _ in range(10):
            w.apply_wrench_b(*body_wrench_flu(rm.step(u), A, "cad"))
            w.step()
        p, q, v, om = w.state()
        w.write_state(mask, p, q, v, om)
        w.reset(mask, p, q)
        rm.reset(mask)
    finally:
        torch.cuda.set_sync_debug_mode(0)
