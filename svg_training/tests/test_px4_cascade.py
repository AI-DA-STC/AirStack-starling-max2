"""S2b Task 3: the PX4 1.14 cascade (models/px4_cascade.py) and the design check's closed loop.

Closed-loop tests fly one drone in the PyTorch reference world with the default plant (CAD arms, motor lag on,
dt 0.005 s) through ``scripts/physics_design_check.py``'s ``fly`` (setpoints in ENU, crossing to NED there).
"""
import importlib.util
import math
import pathlib

import pytest
import torch

from svg_training.models.physics_params import load_physics_params
from svg_training.models.px4_cascade import (Px4Cascade, allocate, allocation_matrix, bodyz_to_rotmat, constrain_xy,
                                             limit_tilt)

ROOT = pathlib.Path(__file__).resolve().parents[1]
P = load_physics_params("params/starling_physics_v0.toml")
G = P.gains
H = G.mpc_thr_hover


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DC = _load("physics_design_check")
DEFAULT = DC.load_params()            # configs/s2b.toml [physics]: cad, motor lag on, dt 0.005


def t(*v):
    return torch.tensor(v, dtype=torch.float32)


def _level(n=1, m=1):
    return torch.eye(3).expand(n, m, 3, 3).clone()


def _rest_inputs(n=1, m=1, yaw_ned=0.0):
    z3 = torch.zeros(n, m, 3)
    zy = torch.zeros(n, m)
    c, s = math.cos(yaw_ned), math.sin(yaw_ned)
    r = torch.tensor([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]).expand(n, m, 3, 3).clone()
    return dict(p_sp=z3, v_ff=z3, a_ff=z3, yaw_sp=zy + yaw_ned, yawspeed_ff=zy, pos=z3, vel=z3, r_ned_frd=r,
                omega_frd=z3)


# ------------------------------------------------------------------------------------------ ControlMath ports
def test_constrain_xy_cases():
    assert torch.allclose(constrain_xy(t(1, 0), t(0, 1), math.sqrt(2)), t(1, 1), atol=1e-6)    # fits: sum
    assert torch.allclose(constrain_xy(t(1, 0), t(0, 1), 0.5), t(0.5, 0), atol=1e-6)          # v0 alone too big
    v = constrain_xy(t(0.6, 0), t(0, 3), 1.0)
    assert v.norm() == pytest.approx(1.0) and v[0] == pytest.approx(0.6)


def test_constrain_xy_other_branches_and_batch():
    assert torch.allclose(constrain_xy(t(0, 0), t(0, 3), 1.0), t(0, 1), atol=1e-6)            # v0 zero
    assert torch.allclose(constrain_xy(t(0.4, 0), t(0.4, 0), 0.5), t(0.5, 0), atol=1e-6)      # equal vectors
    batch = constrain_xy(torch.stack((t(1, 0), t(0.6, 0))), torch.stack((t(0, 1), t(0, 3))), 1.0)
    assert torch.allclose(batch[0], t(1, 0), atol=1e-6) and batch[1].norm() == pytest.approx(1.0)


def test_limit_tilt_45():
    az = math.radians(30.0)
    off = math.radians(60.0)
    bz = t(math.sin(off) * math.cos(az), math.sin(off) * math.sin(az), math.cos(off))
    out = limit_tilt(bz, math.radians(45.0))
    assert math.degrees(math.acos(float(out[2]))) == pytest.approx(45.0, abs=1e-4)
    assert math.atan2(float(out[1]), float(out[0])) == pytest.approx(az, abs=1e-6)          # same azimuth
    assert float(out.norm()) == pytest.approx(1.0, abs=1e-6)
    small = t(math.sin(0.1), 0.0, math.cos(0.1))
    assert torch.allclose(limit_tilt(small, math.radians(45.0)), small, atol=1e-6)            # inside: unchanged
    assert torch.allclose(limit_tilt(t(0, 0, 1), math.radians(45.0)), t(0, 0, 1), atol=1e-6)  # parallel corner


def test_bodyz_to_rotmat_level_yaw():
    yaw = torch.tensor([0.0, math.pi / 2, -2.0])
    r = bodyz_to_rotmat(torch.tensor([[0.0, 0.0, 1.0]]).expand(3, 3), yaw)
    for k in range(3):
        c, s = math.cos(float(yaw[k])), math.sin(float(yaw[k]))
        assert torch.allclose(r[k], torch.tensor([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]), atol=1e-6)
    # thrust tilted forward (body z leaning north-up): nose north (yaw 0) pitches down, x axis points north and down
    lean = bodyz_to_rotmat(t(-0.5, 0.0, 1.0).view(1, 3), torch.zeros(1))
    assert lean[0, 0, 0] > 0 and lean[0, 2, 0] > 0
    assert torch.allclose(lean[0].T @ lean[0], torch.eye(3), atol=1e-6) and torch.det(lean[0]) == pytest.approx(1.0)


# ------------------------------------------------------------------------------------------ allocation
def test_allocation_matrix_values():
    mix = allocation_matrix(G)
    assert mix.shape == (4, 6)
    assert torch.allclose(mix[:, 5], torch.full((4,), -1.0), atol=1e-6)                 # thrust: share of full
    assert torch.allclose(mix[:, 3:5], torch.zeros(4, 2))
    assert torch.allclose(mix[:, 2], t(1, 1, -1, -1), atol=1e-6)                        # yaw: KM sign, max = 1
    # roll and pitch share one scale, the larger (roll: the shorter y arms) -> roll column +-1/sqrt(2)
    assert torch.allclose(mix[:, 0], t(-1, 1, 1, -1) / math.sqrt(2), atol=1e-5)
    ratio = (G.ca_rotor0_py / G.ca_rotor0_px)                                         # pitch / roll = y / x arm
    assert torch.allclose(mix[:, 1], t(1, -1, 1, -1) / math.sqrt(2) * ratio, atol=1e-5)


def test_hover_allocation():
    u = allocate(torch.zeros(1, 1, 3), torch.full((1, 1), 0.165), allocation_matrix(G))
    assert torch.allclose(u, torch.full((1, 1, 4), 0.165), atol=1e-6)


def test_allocation_desaturates_roll_not_thrust_and_yaw_last():
    mix = allocation_matrix(G)
    c = torch.full((1, 1), 0.5)
    u = allocate(torch.tensor([[[1.0, 0.0, 0.0]]]), c, mix)          # roll 1.0 needs +-0.71 around 0.5
    assert (u >= 0).all() and (u <= 1).all()
    assert u.mean() == pytest.approx(0.5, abs=1e-6)                  # airmode off: thrust kept, roll reduced
    assert u[0, 0, 1] > u[0, 0, 0]                                   # still rolls right (left rotors up)
    big_yaw = allocate(torch.tensor([[[0.0, 0.0, 1.0]]]), torch.full((1, 1), 0.165), mix)
    assert (big_yaw >= 0).all() and big_yaw[0, 0, 0] > big_yaw[0, 0, 2]   # KM > 0 rotors 0, 1 up


# ------------------------------------------------------------------------------------------ open-loop cascade
def test_hover_at_rest_outputs_hover_thrust():
    for yaw in (0.0, 1.0):
        c = Px4Cascade(1, 1, G, 0.005, "cpu")
        for _ in range(3):
            u = c.step(**_rest_inputs(yaw_ned=yaw))
            assert torch.allclose(u, torch.full((1, 1, 4), H), atol=1e-6)
            assert c.torque_n.abs().max() < 1e-6 and c.rates_sp.abs().max() < 1e-6
            assert c.collective[0, 0] == pytest.approx(H, abs=1e-6)


def test_attitude_and_rate_signs():
    c = Px4Cascade(1, 1, G, 0.005, "cpu")
    x = _rest_inputs()
    x["a_ff"] = torch.tensor([[[1.0, 0.0, 0.0]]])        # accelerate north (= nose, yaw 0): pitch down first
    c.step(**x)
    assert c.rates_sp[0, 0, 1] < 0 and c.torque_n[0, 0, 1] < 0          # nose-down rate and torque (FRD y)
    assert c.u[0, 0, 0] < c.u[0, 0, 1]                                   # front rotors drop
    c = Px4Cascade(1, 1, G, 0.005, "cpu")
    x = _rest_inputs()
    x["a_ff"] = torch.tensor([[[0.0, 1.0, 0.0]]])        # accelerate east (= right): roll right
    c.step(**x)
    assert c.rates_sp[0, 0, 0] > 0 and c.u[0, 0, 1] > c.u[0, 0, 0]       # left rotors (1, 2) up
    c = Px4Cascade(1, 1, G, 0.005, "cpu")
    x = _rest_inputs()
    x["yaw_sp"] = torch.full((1, 1), 0.1)                # yaw right
    c.step(**x)
    expected = 2 * math.sin(0.1 * G.mc_yaw_weight / 2) * G.mc_yaw_p / G.mc_yaw_weight   # v1.14 yaw compensation
    assert c.rates_sp[0, 0, 2] == pytest.approx(expected, rel=1e-4)


def test_rate_limits_deg_to_rad():
    c = Px4Cascade(1, 1, G, 0.005, "cpu")
    x = _rest_inputs()
    x["a_ff"] = torch.tensor([[[0.0, 30.0, 0.0]]])
    x["yaw_sp"] = torch.full((1, 1), 2.0)
    c.step(**x)
    assert c.rates_sp[0, 0, 0] == pytest.approx(math.radians(G.mc_rollrate_max), rel=1e-6)
    assert c.rates_sp[0, 0, 2] == pytest.approx(math.radians(G.mc_yawrate_max), rel=1e-6)


def test_cascade_reset_clears_integrators():
    c = Px4Cascade(2, 2, G, 0.005, "cpu")
    x = _rest_inputs(2, 2)
    x["p_sp"] = torch.full((2, 2, 3), 0.3)
    x["vel"] = torch.full((2, 2, 3), 0.1)
    x["omega_frd"] = torch.full((2, 2, 3), 0.2)
    for k in range(20):
        x["vel"] = x["vel"] + 0.01
        x["omega_frd"] = x["omega_frd"] + 0.05
        c.step(**x)
    assert c.vel_int.abs().min() > 0 and c.rate_int.abs().min() > 0
    assert c.vel_dot.abs().min() > 0 and c.ang_acc.abs().min() > 0
    before = (c.vel_int.clone(), c.rate_int.clone(), c.vel_dot.clone(), c.ang_acc.clone())
    mask = torch.tensor([[True, False], [False, False]])
    c.reset(mask)
    for now, old in zip((c.vel_int, c.rate_int, c.vel_dot, c.ang_acc), before):
        assert (now[0, 0] == 0).all()
        assert torch.equal(now[~mask], old[~mask])
    # derivative filters at rest: the next step after a reset sees no derivative kick for the reset drone
    x["vel"] = x["vel"] + 1.0
    x["omega_frd"] = x["omega_frd"] + 1.0
    c.step(**x)
    assert (c.vel_dot[0, 0] == 0).all() and (c.ang_acc[0, 0] == 0).all()
    assert (c.vel_dot[1, 1].abs() > 1.0).all()


# ------------------------------------------------------------------------------------------ closed loop
def test_x_command_moves_east_nose_down():                # Review Focus 1; torch world, 1 drone, default plant
    pos0 = torch.tensor([[[0.0, 0.0, 1.0]]])
    out = DC.fly(DEFAULT, 3.0, DC.ramp_x(pos0, 0.5), pos0=pos0)
    p = out["pos_m"][:, 0, 0]
    assert p[-1, 0] > 1.0
    assert p[:, 1].abs().max() < 0.02
    assert (p[:, 2] - 1.0).abs().max() < 0.05
    vx = out["vel_mps"][:, 0, 0, 0]
    accel = (out["t_s"] < 0.3) & (out["t_s"] > 0.02)
    assert (out["pitch_frd_deg"][accel, 0, 0] < 0).all()
    assert vx[accel].diff().min() > 0                                      # really accelerating there
    assert abs(float(out["yaw_enu_deg"][-1, 0, 0])) < 1.0


def test_hover_stable_default_plant():                    # the D5 check as a test (design check rule (a))
    h = DC.hover_metrics(DEFAULT)
    assert h["finite"]
    assert h["tilt_spread_deg"] <= 1.0
    assert h["drift_m"] <= 0.05


def test_tilt_limited_45():
    pos0 = torch.tensor([[[0.0, 0.0, 1.0]]])
    z = torch.zeros(1, 1, 3)
    zy = torch.zeros(1, 1)
    a = torch.tensor([[[20.0, 0.0, 0.0]]])
    out = DC.fly(DEFAULT, 1.5, lambda s: (pos0, z, a, zy, zy), pos0=pos0)
    peak = float(out["tilt_deg"].max())
    assert 40.0 < peak <= 45.5


def test_vertical_step_and_thrust_cap():
    pos0 = torch.tensor([[[0.0, 0.0, 1.0]]])
    zy = torch.zeros(1, 1)

    def up(s):
        p = pos0.clone()
        p[..., 2] += 2.0 * s
        return p, torch.tensor([[[0.0, 0.0, 2.0]]]), torch.zeros(1, 1, 3), zy, zy   # ENU up = NED v_ff z -2
    out = DC.fly(DEFAULT, 2.0, up, pos0=pos0)
    assert float(out["u"].max()) <= G.mpc_thr_max + 1e-6
    assert float(out["vel_mps"][-1, 0, 0, 2]) > 1.5
    # a step this gentle never reaches the cap (peak u about 0.43); an upward a_ff of 30 m/s^2 does, and is held to it
    hard = DC.fly(DEFAULT, 0.5, lambda s: (pos0, torch.zeros(1, 1, 3), torch.tensor([[[0.0, 0.0, 30.0]]]), zy, zy),
                  pos0=pos0)
    assert float(hard["u"].max()) <= G.mpc_thr_max + 1e-6
    assert float(hard["u"].max()) == pytest.approx(G.mpc_thr_max, abs=1e-4)
    assert float(hard["collective"].max()) == pytest.approx(G.mpc_thr_max, abs=1e-6)


def test_cascade_dt_convergence():                         # design check rule (b)
    a = DC.step_run(DEFAULT)
    b = DC.step_run(DC.load_params(dt_s=0.001))
    assert DC.speed_rms_diff(a, b) <= 0.02


def test_rate_loop_tracks_roll_rate_step():
    r = DC.rate_metrics(DEFAULT)
    assert 0.0 < r["t63_s"] < 0.15


def test_batched_drones_independent():
    n, m = 3, 2
    pos0 = torch.zeros(n, m, 3)
    pos0[..., 2] = 1.0
    spd = torch.tensor([0.0, 0.5, -0.3]).view(n, 1, 1)
    zy = torch.zeros(n, m)

    def sp(s):
        p = pos0.clone()
        p[..., 0] += spd[..., 0] * s
        v = torch.zeros(n, m, 3)
        v[..., 0] = spd[..., 0]
        return p, v, torch.zeros(n, m, 3), zy, zy
    out = DC.fly(DEFAULT, 1.0, sp, n=n, m=m, pos0=pos0)
    one = DC.fly(DEFAULT, 1.0, DC.ramp_x(pos0[1:2, :1], 0.5), pos0=pos0[1:2, :1])
    assert torch.allclose(out["pos_m"][:, 1, 0], one["pos_m"][:, 0, 0], atol=1e-5)
    assert out["pos_m"][-1, 0, :, 0].abs().max() < 1e-3
    assert (out["pos_m"][-1, 2, :, 0] < -0.05).all()


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA only")
def test_cascade_step_runs_under_sync_debug_error():
    n, m = 64, 3
    c = Px4Cascade(n, m, G, 0.005, "cuda")
    x = {k: v.to("cuda") for k, v in _rest_inputs(n, m).items()}
    x["p_sp"] = torch.rand(n, m, 3, device="cuda")
    x["omega_frd"] = torch.rand(n, m, 3, device="cuda")
    mask = torch.rand(n, m, device="cuda") < 0.5
    c.step(**x)                                                      # warm-up
    torch.cuda.set_sync_debug_mode("error")
    try:
        for _ in range(5):
            u = c.step(**x)
            c.rate_step(c.rates_sp, x["omega_frd"], c.collective)
        c.reset(mask)
    finally:
        torch.cuda.set_sync_debug_mode(0)
    assert u.shape == (n, m, 4) and torch.isfinite(u).all()
