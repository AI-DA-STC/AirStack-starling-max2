"""STE task L1.2: a linear drag force in the physics drone's wrench path, before ``apply_wrench_b``, so both worlds get it.

Form (Pegasus's simple drag, read only): F_b = -diag(d_x, d_y, d_z) (R^T v_w), the body-frame velocity times a diagonal
of coefficients (``models/starling_airframe.linear_drag_force_b``; source cited there). Tests (WORK_BREAKDOWN L1.2): off =
today bit for bit (against the frozen copy ``tests/_physics_drone_today.py``); zero velocity gives zero drag (hover
unchanged); a constant push reaches the analytic terminal speed F / d in the torch world.

CPU, float32, made-up drag coefficients and pushes (the Starling's drag is OPEN, STANDARDS section 5). Observed in the
training simulator (PyTorch reference world), not a flight result.
"""
import dataclasses
import math
import pathlib
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "tests"))
from _physics_drone_today import TodayPhysicsDrone  # noqa: E402
from svg_training.models import physics_drone as physics_drone_module  # noqa: E402
from svg_training.models.frames import quat_from_yaw_enu, quat_mul_wxyz  # noqa: E402
from svg_training.models.physics_drone import PhysicsDrone  # noqa: E402
from svg_training.models.physics_params import G_MPS2, load_physics_drone_params  # noqa: E402
from svg_training.models.rigid_body import TorchRigidBodyWorld  # noqa: E402
from svg_training.models.starling_airframe import linear_drag_force_b  # noqa: E402

P0 = load_physics_drone_params(ROOT / "params/starling_physics_v0.toml")
A = P0.airframe
DRAG = {"drag_x_n_per_mps": 0.25, "drag_y_n_per_mps": 0.4, "drag_z_n_per_mps": 0.1}     # made up, not a Starling value


def world(n, m):
    return TorchRigidBodyWorld(n, m, A, P0.physics_dt_s, "cpu")


def coeff(p=None):
    d = DRAG if p is None else {k: getattr(p, k) for k in DRAG}
    return torch.tensor([d["drag_x_n_per_mps"], d["drag_y_n_per_mps"], d["drag_z_n_per_mps"]])


# ------------------------------------------------------------------------------------- off = today, bit for bit
def test_drag_off_is_today_bit_for_bit():
    from test_estimator_effect import scripted_flight
    n, m = 2, 3
    zeros = dataclasses.replace(P0, **{k: 0.0 for k in DRAG})
    today = TodayPhysicsDrone(world(n, m), P0, "cpu")
    now = PhysicsDrone(world(n, m), zeros, "cpu")
    a = scripted_flight(today, n, m, torch.Generator().manual_seed(9))
    b = scripted_flight(now, n, m, torch.Generator().manual_seed(9))
    for i, (ra, rb) in enumerate(zip(a, b)):
        for j, (x, y) in enumerate(zip(ra, rb)):
            assert torch.equal(x, y), f"call {i}, output {j} differs from today's physics drone"
    assert now.drag_coeff is None                      # off: no drag term is computed at all


# ------------------------------------------------------------------------------------- the force law
def test_zero_velocity_gives_zero_drag_at_any_attitude():
    g = torch.Generator().manual_seed(2)
    q = torch.randn(4, 5, 4, generator=g)
    q = q / q.norm(dim=-1, keepdim=True)
    f = linear_drag_force_b(torch.zeros(4, 5, 3), q, coeff())
    assert torch.equal(f, torch.zeros(4, 5, 3))


def test_drag_is_minus_coefficients_times_body_velocity():
    q = quat_from_yaw_enu(torch.tensor([[math.pi / 2]]))           # nose north: body x = world y, body y = world -x
    f = linear_drag_force_b(torch.tensor([[[1.0, 0.0, 0.5]]]), q, coeff())
    # world (1, 0, 0.5) = body (0, -1, 0.5) -> F_b = (-0.25 * 0, +0.4 * 1, -0.1 * 0.5)
    assert torch.allclose(f, torch.tensor([[[0.0, 0.4, -0.05]]]), atol=1e-7)
    tilt = quat_mul_wxyz(q, torch.tensor([[[math.cos(0.2), math.sin(0.2), 0.0, 0.0]]]))   # rolled 0.4 rad
    v = torch.tensor([[[0.3, -0.7, 0.2]]])
    f = linear_drag_force_b(v, tilt, coeff())
    # power = F . v_b <= 0: drag only ever takes energy out
    from svg_training.models.frames import quat_wxyz_to_rotmat
    v_b = (quat_wxyz_to_rotmat(tilt).transpose(-1, -2) @ v.unsqueeze(-1)).squeeze(-1)
    assert torch.allclose(f, -coeff() * v_b, atol=1e-7) and float((f * v_b).sum()) < 0.0


def test_hover_unchanged_with_drag_on(monkeypatch):
    """From a reset (at rest) the first wrench with drag on is exactly the one without; over a 2 s hold the drone
    flies as without drag to within what the drag of the cascade's settling speeds (under 7 mm/s here) can do."""
    def hover(p):
        w = world(1, 2)
        d = PhysicsDrone(w, p, "cpu")
        start = torch.tensor([[[0.0, 0.0, 1.2], [2.0, 0.0, 1.2]]])
        d.reset(torch.ones(1, 2, dtype=torch.bool), start, torch.zeros(1, 2))
        forces = []
        real = w.apply_wrench_b
        monkeypatch.setattr(w, "apply_wrench_b", lambda f, t: (forces.append(f.clone()), real(f, t)))
        zero = torch.zeros(1, 2, 3)
        for _ in range(40):                                      # 2 s, holding the start point
            d.step_setpoint(start, zero, zero, torch.zeros(1, 2), torch.zeros(1, 2))
        return d, forces
    (off, f_off), (on, f_on) = hover(P0), hover(dataclasses.replace(P0, **DRAG))
    assert torch.equal(f_off[0], f_on[0])                          # zero velocity: zero drag, bit for bit
    assert torch.allclose(off.pos_m, on.pos_m, atol=1e-5) and torch.allclose(off.vel_mps, on.vel_mps, atol=1e-4)


# ------------------------------------------------------------------------------------- terminal speed, torch world
@pytest.mark.parametrize("axis", [0, 1])
def test_constant_push_reaches_the_analytic_terminal_speed(axis):
    """Level body, rotor thrust = weight, a constant body push F along x (or y), the drag of linear_drag_force_b added
    to the wrench each physics step as the physics drone does: m dv/dt = F - d v, so v -> F / d with time constant
    m / d. Semi-implicit Euler has the same fixed point F / d exactly, and v(t) = F/d (1 - (1 - d dt / m)^n)."""
    w = world(1, 1)
    w.reset(torch.ones(1, 1, dtype=torch.bool), torch.tensor([[[0.0, 0.0, 1.0]]]), quat_from_yaw_enu(torch.zeros(1, 1)))
    push_n = 0.2                                                  # made up
    d = coeff()
    lift = torch.tensor([0.0, 0.0, A.mass_kg * G_MPS2])
    push = torch.zeros(3)
    push[axis] = push_n
    terminal = push_n / float(d[axis])
    tau = A.mass_kg / float(d[axis])
    steps = round(8.0 * tau / P0.physics_dt_s)
    v_at_tau = None
    for k in range(1, steps + 1):
        pos, quat, vel, _ = w.state()
        f = lift + push + linear_drag_force_b(vel, quat, d)
        w.apply_wrench_b(f, torch.zeros(1, 1, 3))
        w.step()
        if k == round(tau / P0.physics_dt_s):
            v_at_tau = float(w.state()[2][0, 0, axis])
    v_end = float(w.state()[2][0, 0, axis])
    n_tau = round(tau / P0.physics_dt_s)
    want_tau = terminal * (1.0 - (1.0 - float(d[axis]) * P0.physics_dt_s / A.mass_kg) ** n_tau)
    assert v_at_tau == pytest.approx(want_tau, rel=1e-4)
    assert v_at_tau == pytest.approx(terminal * (1.0 - math.exp(-1.0)), rel=0.01)    # the continuous 63 %
    assert v_end == pytest.approx(terminal, rel=1e-3)                                 # 8 time constants: within 0.03 %
    assert abs(float(w.state()[2][0, 0, 2])) < 1e-5                                   # height held: drag is per axis


# ------------------------------------------------------------------------------------- wiring in the physics drone
def test_physics_drone_applies_rotor_wrench_plus_drag_of_the_true_velocity(monkeypatch):
    """Every wrench the drone hands the world = the rotor wrench + linear_drag_force_b of the TRUE state at that
    physics step, also when the cascade sees a delayed state (L1.1): drag is physics, not estimation."""
    p = dataclasses.replace(P0, **DRAG, state_delay_s=0.02)
    w = world(2, 2)
    d = PhysicsDrone(w, p, "cpu")
    d.reset(torch.ones(2, 2, dtype=torch.bool), torch.rand(2, 2, 3, generator=torch.Generator().manual_seed(4)) + 1.0,
            torch.zeros(2, 2))
    rotor, applied, truth = [], [], []
    real_wrench = physics_drone_module.body_wrench_flu

    def spy_wrench(*a, **k):
        f, t = real_wrench(*a, **k)
        rotor.append(f.clone())
        _, quat, vel, _ = w.state()
        truth.append((vel.clone(), quat.clone()))
        return f, t

    real_apply = w.apply_wrench_b

    def spy_apply(force, torque):
        applied.append(force.clone())
        real_apply(force, torque)

    monkeypatch.setattr(physics_drone_module, "body_wrench_flu", spy_wrench)
    monkeypatch.setattr(w, "apply_wrench_b", spy_apply)
    sp = d.pos_m + torch.tensor([0.5, -0.3, 0.2])
    for _ in range(4):
        d.step_setpoint(sp, torch.zeros(2, 2, 3), torch.zeros(2, 2, 3), torch.zeros(2, 2), torch.zeros(2, 2))
    assert len(applied) == 40
    moving = 0
    for f_rotor, f_applied, (vel, quat) in zip(rotor, applied, truth):
        assert torch.equal(f_applied, f_rotor + linear_drag_force_b(vel, quat, coeff()))
        moving += int(vel.abs().max() > 1e-3)
    assert moving > 10                                                   # the check ran with the drag non-zero
