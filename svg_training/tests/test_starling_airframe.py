"""S2b Task 2: the rotor model (first-order lag on rotor speed) and the body wrench of four rotors (FRD -> FLU)."""
import dataclasses
import math
import pathlib
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.models.physics_params import G_MPS2, load_physics_params  # noqa: E402
from svg_training.models.starling_airframe import RotorModel, body_wrench_flu, hover_omega_rad_s  # noqa: E402

A = load_physics_params("params/starling_physics_v0.toml").airframe
DT = 0.005


def test_hover_wrench():
    t = torch.full((1, 1, 4), 1.3660425)
    f, tau = body_wrench_flu(t, A, "cad")
    assert f[0, 0, 2] == pytest.approx(5.46417, abs=1e-4) and tau.abs().max() < 1e-7
    assert f[0, 0, :2].abs().max() == 0.0


@pytest.mark.parametrize("geometry", ["cad", "params"])
def test_rotor_torque_signs(geometry):                    # Review Focus 1
    hover = torch.full((1, 1, 4), A.mass_kg * G_MPS2 / 4)

    def extra(*rotors):
        t = hover.clone()
        t[0, 0, list(rotors)] += 0.1
        return body_wrench_flu(t, A, geometry)[1][0, 0]

    roll = extra(0, 3)            # right side (y_FRD > 0) pushes harder: roll left -> torque x < 0 (FRD and FLU)
    assert roll[0] < -1e-3 and roll[1].abs() < 1e-6 and roll[2].abs() < 1e-6
    yaw = extra(0, 1)             # KM > 0 rotors: reaction yaw right seen from above -> FRD z > 0 -> FLU z < 0
    assert yaw[2] < -1e-4 and yaw[0].abs() < 1e-6 and yaw[1].abs() < 1e-6
    pitch = extra(0, 2)           # front rotors: nose up -> FRD y > 0 -> FLU y < 0
    assert pitch[1] < -1e-3 and pitch[0].abs() < 1e-6


def test_wrench_magnitudes_match_layout():
    """Exact numbers: arm x 0.2 N for roll / pitch, k_m/k_f x 0.2 N for yaw; force is the thrust sum."""
    t = torch.zeros(2, 3, 4, dtype=torch.float64)
    t[..., 0] = 0.2
    for geometry, xy in (("cad", A.rotor_xy_cad_m), ("params", A.rotor_xy_params_m)):
        f, tau = body_wrench_flu(t, A, geometry)
        x0, y0 = xy[0]
        assert f.dtype == torch.float64 and f.shape == (2, 3, 3) and tau.shape == (2, 3, 3)
        assert torch.allclose(f[..., 2], torch.full((2, 3), 0.2, dtype=torch.float64))
        # FRD torque of rotor 0 = (-y F, x F, +k_m/k_f F); FLU = (x, -y, -z)
        exp = torch.tensor([-y0 * 0.2, -x0 * 0.2, -(A.k_m / A.k_f) * 0.2], dtype=torch.float64)
        assert torch.allclose(tau, exp.expand(2, 3, 3), atol=1e-15)
    assert A.k_m / A.k_f == pytest.approx(0.0135872, rel=1e-5)          # the plan's Facts row


def test_unknown_geometry_raises():
    with pytest.raises(ValueError, match="geometry"):
        body_wrench_flu(torch.zeros(1, 1, 4), A, "wide")


def test_hover_speed():
    assert hover_omega_rad_s(A) == pytest.approx(586.98, abs=0.01)
    rm = RotorModel(2, 3, A, motor_lag=True, dt_s=DT, device="cpu")
    assert rm.omega_rad_s.shape == (2, 3, 4)
    assert torch.allclose(rm.omega_rad_s, torch.full((2, 3, 4), hover_omega_rad_s(A)))
    thrust = rm.step(torch.full((2, 3, 4), A.hover_u()))                # hover command holds hover speed
    assert torch.allclose(thrust.sum(-1), torch.full((2, 3), A.mass_kg * G_MPS2), rtol=1e-5)
    assert torch.allclose(rm.omega_rad_s, torch.full((2, 3, 4), hover_omega_rad_s(A)), rtol=1e-6)


def test_rotor_lag_63pct():                               # from hover speed, u stepped to 1: 63.2 % of the gap after 55 ms
    rm = RotorModel(1, 1, A, motor_lag=True, dt_s=DT, device="cpu")
    w0, w_end = hover_omega_rad_s(A), A.omega_max_rad_s
    frac = []
    for _ in range(40):
        rm.step(torch.ones(1, 1, 4))
        frac.append((rm.omega_rad_s[0, 0, 0] - w0) / (w_end - w0))
    k = next(i + 1 for i, f in enumerate(frac) if f >= 1 - math.exp(-1) - 1e-6)
    assert abs(k * DT - A.tau_up_s) <= DT + 1e-9
    assert torch.allclose(rm.omega_rad_s, rm.omega_rad_s[..., :1].expand(1, 1, 4))   # all four rotors alike


def test_rotor_lag_down_uses_tau_down():
    rm = RotorModel(1, 1, A, motor_lag=True, dt_s=DT, device="cpu")
    w0 = hover_omega_rad_s(A)
    n = round(A.tau_down_s / DT)
    for _ in range(n):
        rm.step(torch.zeros(1, 1, 4))
    assert rm.omega_rad_s[0, 0, 0] / w0 == pytest.approx(math.exp(-n * DT / A.tau_down_s), rel=1e-5)


def test_rotor_lag_off_is_instant():
    rm = RotorModel(2, 1, A, motor_lag=False, dt_s=DT, device="cpu")
    u = torch.tensor([0.0, 0.25, 0.7, 1.0]).expand(2, 1, 4)
    thrust = rm.step(u)
    assert torch.allclose(rm.omega_rad_s, A.omega_max_rad_s * u.sqrt())
    assert torch.allclose(thrust, u * A.f_max_n(), rtol=1e-5)


def test_rotor_command_clamped_and_reset_masked():
    rm = RotorModel(2, 2, A, motor_lag=False, dt_s=DT, device="cpu")
    thrust = rm.step(torch.tensor([-0.5, 1.5, 0.5, 0.5]).expand(2, 2, 4))
    assert thrust[..., 0].abs().max() == 0 and torch.allclose(thrust[..., 1], torch.full((2, 2), A.f_max_n()))
    mask = torch.tensor([[True, False], [False, False]])
    rm.reset(mask)
    assert torch.allclose(rm.omega_rad_s[0, 0], torch.full((4,), hover_omega_rad_s(A)))
    assert rm.omega_rad_s[0, 1, 1] == pytest.approx(A.omega_max_rad_s)   # untouched where mask is False


def test_lag_switch_is_from_params():
    p = load_physics_params("params/starling_physics_v0.toml")
    assert p.motor_lag is True and p.rotor_geometry == "cad"             # D4, D5 defaults
    a2 = dataclasses.replace(A, tau_up_s=0.01)
    rm = RotorModel(1, 1, a2, motor_lag=True, dt_s=DT, device="cpu")
    rm.step(torch.ones(1, 1, 4))
    assert (rm.omega_rad_s[0, 0, 0] - hover_omega_rad_s(A)) / (A.omega_max_rad_s - hover_omega_rad_s(A)) == \
        pytest.approx(1 - math.exp(-DT / 0.01), rel=1e-5)
