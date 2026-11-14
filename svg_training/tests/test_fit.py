"""Task 3 (S1): response model (NumPy reference) and its fit. Runs in seconds, no ROS, no GPU."""
import math
import tomllib

import numpy as np
import pytest

from svg_training.models.fit import (StepData, check_command_source, evaluate, fit, resample_uniform,
                                     segment_steps, split_alternate, step_data, to_vehicle_time)
from svg_training.models.response import ResponseParams, body_to_world, lag_alpha, simulate

TRUE = ResponseParams(delay_s=0.12, tau_xy_s=0.5, tau_z_s=0.4, acc_max_xy_mps2=3.0, acc_max_z_mps2=2.5,
                      speed_cap_mps=2.0, family="lag1")
FITTED = ("delay_s", "tau_xy_s", "tau_z_s", "acc_max_xy_mps2", "acc_max_z_mps2")
# 12 designed steps: (axis, speed). Even indices (train) and odd (held out) both cover x, y, z, both signs, 1 and 2 m/s.
PLAN = [(0, 2.0), (0, -1.0), (1, -2.0), (1, 1.0), (2, 1.0), (2, -2.0),
        (0, -1.0), (0, 2.0), (1, 1.0), (1, -2.0), (2, -2.0), (2, 1.0)]


def _fast(**kw):
    base = dict(delay_s=0.0, tau_xy_s=0.0, tau_z_s=0.0, acc_max_xy_mps2=math.inf, acc_max_z_mps2=math.inf,
                speed_cap_mps=math.inf, family="lag1")
    base.update(kw)
    return ResponseParams(**base)


# ---------------------------------------------------------------- ResponseParams

def test_params_round_trip_and_toml_friendly():
    p = ResponseParams(delay_s=0.1, tau_xy_s=0.5, tau_z_s=0.4, acc_max_xy_mps2=3.0, acc_max_z_mps2=2,
                       speed_cap_mps=2.0, family="lag2", tau2_s=0.05)
    d = p.to_dict()
    assert all(isinstance(v, float) for k, v in d.items() if k != "family") and d["family"] == "lag2"
    toml = "\n".join(f'{k} = "{v}"' if isinstance(v, str) else f"{k} = {v!r}" for k, v in d.items())
    assert ResponseParams.from_dict(tomllib.loads(toml)) == p
    with pytest.raises(AttributeError):
        p.delay_s = 0.2


def test_params_refuse_bad_values():
    with pytest.raises(ValueError):
        _fast(family="lag3")
    with pytest.raises(ValueError):
        _fast(delay_s=-0.01)
    with pytest.raises(ValueError):
        _fast(speed_cap_mps=0.0)
    with pytest.raises(ValueError):
        ResponseParams.from_dict({**_fast().to_dict(), "extra_s": 1.0})


# ---------------------------------------------------------------- simulate

def test_lag_alpha_exact_and_tau_zero():
    assert lag_alpha(0.01, 0.5) == pytest.approx(1 - math.exp(-0.02))
    assert lag_alpha(0.01, 0.0) == 1.0


def test_zero_delay_zero_tau_tracks_command_exactly():
    rng = np.random.default_rng(0)
    cmd = rng.uniform(-1.0, 1.0, (50, 3))
    v = simulate(cmd, 0.05, _fast())
    assert v.shape == (50, 3) and np.all(v[0] == 0.0)
    np.testing.assert_allclose(v[1:], cmd[:-1], atol=1e-15)      # v(t_{k+1}) = cmd held over [t_k, t_{k+1})


def test_zero_tau_tracks_up_to_acceleration_and_speed_limits():
    dt = 0.01
    cmd = np.zeros((300, 3))
    cmd[10:, 0] = 2.0
    cmd[10:, 2] = -1.0
    v = simulate(cmd, dt, _fast(acc_max_xy_mps2=3.0, acc_max_z_mps2=2.0))
    k = np.arange(300)
    np.testing.assert_allclose(v[:, 0], np.clip((k - 10) * 3.0 * dt, 0.0, 2.0), atol=1e-12)
    np.testing.assert_allclose(v[:, 2], -np.clip((k - 10) * 2.0 * dt, 0.0, 1.0), atol=1e-12)
    # speed cap on the 3-D command norm (as the commander and the placeholder do)
    cmd2 = np.tile([3.0, 4.0, 0.0], (5, 1))
    v2 = simulate(cmd2, dt, _fast(speed_cap_mps=2.0))
    np.testing.assert_allclose(v2[-1], [1.2, 1.6, 0.0], atol=1e-12)


def test_horizontal_acceleration_limit_is_on_the_norm():
    cmd = np.tile([2.0, 2.0, 0.0], (40, 1))
    v = simulate(cmd, 0.01, _fast(acc_max_xy_mps2=3.0))
    np.testing.assert_allclose(np.diff(np.hypot(v[:, 0], v[:, 1]))[:20], 0.03, atol=1e-12)


def test_first_order_lag_is_exact_on_the_grid():
    dt, tau = 0.02, 0.5
    cmd = np.ones((200, 3))
    v = simulate(cmd, dt, _fast(tau_xy_s=tau, tau_z_s=0.3))
    t = np.arange(200) * dt
    np.testing.assert_allclose(v[:, 0], 1 - np.exp(-t / tau), atol=1e-12)
    np.testing.assert_allclose(v[:, 2], 1 - np.exp(-t / 0.3), atol=1e-12)


def test_integer_and_fractional_delay():
    dt = 0.01
    cmd = np.zeros((40, 3))
    cmd[10:, 1] = 1.0
    v_int = simulate(cmd, dt, _fast(delay_s=3 * dt))
    np.testing.assert_allclose(v_int[1:, 1], np.r_[np.zeros(3), cmd[:-4, 1]], atol=1e-12)
    v_frac = simulate(cmd, dt, _fast(delay_s=2.25 * dt))
    # cell 12 is covered 0.25 by the (zero) cell 9 and 0.75 by the (one) cell 10
    assert v_frac[13, 1] == pytest.approx(0.75) and v_frac[12, 1] == 0.0 and v_frac[14, 1] == 1.0


def test_initial_velocity_decays_toward_command():
    v = simulate(np.zeros((100, 3)), 0.01, _fast(tau_xy_s=0.5, tau_z_s=0.5), v0_mps=np.array([1.0, 0.0, 0.0]))
    assert v[0, 0] == 1.0 and v[-1, 0] == pytest.approx(math.exp(-0.99 / 0.5))


def test_lag2_reduces_to_lag1_when_tau2_goes_to_zero():
    rng = np.random.default_rng(1)
    cmd = np.repeat(rng.uniform(-2, 2, (12, 3)), 25, axis=0)
    p1 = ResponseParams(0.13, 0.5, 0.4, 3.0, 2.5, 2.0, "lag1")
    v1 = simulate(cmd, 0.01, p1)
    p2 = ResponseParams(0.13, 0.5, 0.4, 3.0, 2.5, 2.0, "lag2", tau2_s=0.0)
    np.testing.assert_array_equal(simulate(cmd, 0.01, p2), v1)
    p2s = ResponseParams(0.13, 0.5, 0.4, 3.0, 2.5, 2.0, "lag2", tau2_s=1e-6)
    np.testing.assert_allclose(simulate(cmd, 0.01, p2s), v1, atol=1e-9)
    p2b = ResponseParams(0.13, 0.5, 0.4, 3.0, 2.5, 2.0, "lag2", tau2_s=0.1)
    assert np.abs(simulate(cmd, 0.01, p2b) - v1).max() > 0.05     # the second pole does act


def test_body_to_world():
    v = np.array([[1.0, 0.0, 0.5]])
    np.testing.assert_allclose(body_to_world(v, np.array([[1.0, 0, 0, 0]])), v)
    yaw90 = np.array([[math.cos(math.pi / 4), 0, 0, math.sin(math.pi / 4)]])       # w, x, y, z
    np.testing.assert_allclose(body_to_world(v, yaw90), [[0.0, 1.0, 0.5]], atol=1e-12)


# ---------------------------------------------------------------- time, resampling, segmentation

def test_to_vehicle_time():
    t = np.array([100.0, 101.0, 103.0])
    np.testing.assert_allclose(to_vehicle_time(t, 1.33), [133.0, 134.33, 136.99])
    np.testing.assert_allclose(to_vehicle_time(t, 1.33, t0_wall_s=100.0), [0.0, 1.33, 3.99])
    with pytest.raises(ValueError):
        to_vehicle_time(t, 0.0)


def test_resample_cell_averages_command_and_interpolates_velocity():
    t_cmd = np.array([0.0, 0.025, 0.1])
    cmd = np.array([[0.0, 0, 0], [1.0, 0, 0], [1.0, 0, 0]])
    t_od = np.array([0.0, 0.1])
    vel = np.array([[0.0, 0, 0], [0.0, 1.0, 0]])
    t, c, v = resample_uniform(t_cmd, cmd, t_od, vel, dt_s=0.01)
    np.testing.assert_allclose(t, np.arange(10) * 0.01, atol=1e-12)
    np.testing.assert_allclose(c[:4, 0], [0.0, 0.0, 0.5, 1.0])   # the switch at 0.025 s is half of cell 2
    np.testing.assert_allclose(v[:, 1], t * 10.0, atol=1e-12)


def test_segment_steps():
    t = np.arange(1000) * 0.01
    cmd = np.zeros((1000, 3))
    cmd[100:300, 0] = 1.0          # step 1, released at 300
    cmd[200:300, 0] = 1.1          # a small change inside the hold is not a step
    cmd[350:500, 2] = -0.5         # step 2, starts 0.5 s after the release: ends at the next start
    cmd[600:700, 1] = 0.1          # below min_jump: not a step
    cmd[800:900, 1] = -2.0         # step 3, released at 900, tail 1.0 s runs past the end
    assert segment_steps(cmd, t, min_jump_mps=0.2, tail_s=1.0) == [(100, 350), (350, 600), (800, 1000)]


def test_split_alternate():
    assert split_alternate(5) == ([0, 2, 4], [1, 3])


# ---------------------------------------------------------------- synthetic AirStack-like session

def _session(p, scale=1.0, noise_mps=0.01, seed=0, plan=PLAN):
    """Truth in vehicle time on a 1 ms grid; commands stamped at 20 Hz wall, odometry at 50 Hz wall.

    Returns wall-time stamps: (t_cmd_wall, cmd, t_odom_wall, vel_noisy).
    """
    rest_wall, hold_wall = 2.0, 3.0
    n_cmd = int(round((len(plan) * (rest_wall + hold_wall) + rest_wall) * 20))
    t_cmd_wall = np.arange(n_cmd) / 20.0
    cmd = np.zeros((n_cmd, 3))
    for i, (axis, speed) in enumerate(plan):
        t0 = rest_wall + i * (rest_wall + hold_wall)
        cmd[(t_cmd_wall >= t0) & (t_cmd_wall < t0 + hold_wall), axis] = speed
    t_cmd_veh = t_cmd_wall * scale
    dt_f = 0.001
    t_f = np.arange(int(t_cmd_veh[-1] / dt_f)) * dt_f
    idx = np.searchsorted(t_cmd_veh, t_f + 1e-12, side="right") - 1
    v_f = simulate(cmd[idx], dt_f, p)
    t_od_wall = np.arange(0.0, t_cmd_wall[-1] - 0.05, 1 / 50.0)
    vel = np.stack([np.interp(t_od_wall * scale, t_f, v_f[:, a]) for a in range(3)], axis=1)
    vel += np.random.default_rng(seed).normal(0.0, noise_mps, vel.shape)
    return t_cmd_wall, cmd, t_od_wall, vel


def _data(p, scale=1.0, use_vehicle_time=True, **kw):
    t_cmd, cmd, t_od, vel = _session(p, scale=scale, **kw)
    if use_vehicle_time:
        t_cmd, t_od = to_vehicle_time(t_cmd, scale), to_vehicle_time(t_od, scale)
    t, c, v = resample_uniform(t_cmd, cmd, t_od, vel, dt_s=0.01)
    return t, c, v


def test_session_segments_into_the_twelve_designed_steps():
    t, c, v = _data(TRUE)
    assert len(segment_steps(c, t)) == len(PLAN)


def test_recovers_known_parameters_within_5_percent():
    t, c, v = _data(TRUE, scale=1.33)
    train, held = split_alternate(len(segment_steps(c, t)))
    p, report = fit(c, v, t, "lag1", train, source="teleop_command")
    for name in FITTED:
        assert getattr(p, name) == pytest.approx(getattr(TRUE, name), rel=0.05), name
    assert p.speed_cap_mps == 2.0 and p.family == "lag1"
    assert report["optimizer"]["success"] and report["train_idx"] == train
    assert [row["index"] for row in report["train_steps"]] == train
    ev = evaluate(p, step_data(c, v, t, source="teleop_command"), held)
    assert ev["vel_rms_mps"] < 0.03 and ev["t63_err_s"] < 0.03


def test_wall_time_input_gives_a_delay_scale_times_too_small():
    """Review Focus 1: the fit must run in vehicle time; bag stamps are wall time."""
    scale = 1.33
    t_w, c_w, v_w = _data(TRUE, scale=scale, use_vehicle_time=False)
    train = split_alternate(len(segment_steps(c_w, t_w)))[0]
    p_wall, _ = fit(c_w, v_w, t_w, "lag1", train, source="teleop_command")
    assert p_wall.delay_s == pytest.approx(TRUE.delay_s / scale, rel=0.05)
    assert p_wall.tau_xy_s == pytest.approx(TRUE.tau_xy_s / scale, rel=0.05)
    assert abs(p_wall.delay_s - TRUE.delay_s) > 0.05 * TRUE.delay_s
    t_v, c_v, v_v = _data(TRUE, scale=scale, use_vehicle_time=True)
    p_veh, _ = fit(c_v, v_v, t_v, "lag1", train, source="teleop_command")
    assert p_veh.delay_s == pytest.approx(TRUE.delay_s, rel=0.05)


@pytest.mark.parametrize("label", ["setpoint_raw", "velocity_command", "velocity_command.csv",
                                   "/drone_1/interface/mavros/setpoint_raw/local",
                                   "/drone_1/interface/velocity_command", "odometry", ""])
def test_fit_refuses_non_teleop_input(label):
    """Review Focus 2: the plug-in point is the teleop command, before the commander's shaping."""
    t, c, v = _data(TRUE, plan=PLAN[:2])
    with pytest.raises(ValueError, match="teleop_command"):
        fit(c, v, t, "lag1", [0], source=label)
    with pytest.raises(ValueError, match="teleop_command"):
        step_data(c, v, t, source=label)


@pytest.mark.parametrize("label", ["teleop_command", "teleop_command.csv", "/svg/drone_1/teleop_command",
                                   "runs/x/teleop_command.csv"])
def test_teleop_labels_accepted(label):
    assert check_command_source(label) == "teleop_command"


def test_fit_refuses_non_uniform_grid():
    t, c, v = _data(TRUE, plan=PLAN[:2])
    t = t.copy()
    t[5] += 0.003
    with pytest.raises(ValueError, match="uniform"):
        fit(c, v, t, "lag1", [0], source="teleop_command")


def test_held_out_metrics_use_only_held_out_steps():
    """Review Focus 3: corrupting the training windows changes nothing; corrupting a held-out one does."""
    t, c, v = _data(TRUE)
    d = step_data(c, v, t, source="teleop_command")
    train, held = split_alternate(len(d.windows))
    base = evaluate(TRUE, d, held)
    assert [row["index"] for row in base["steps"]] == held
    v_bad = v.copy()
    for i in train:
        s, e = d.windows[i]
        v_bad[s:e] += 5.0
    same = evaluate(TRUE, StepData(d.t_s, d.cmd_mps, v_bad, d.windows), held)
    assert same["vel_rms_mps"] == base["vel_rms_mps"] and same["t63_err_s"] == base["t63_err_s"]
    s, e = d.windows[held[2]]
    v_bad[s:e] += 0.5
    worse = evaluate(TRUE, StepData(d.t_s, d.cmd_mps, v_bad, d.windows), held)
    assert worse["vel_rms_mps"] > base["vel_rms_mps"] + 0.4
    with pytest.raises(ValueError):
        evaluate(TRUE, d, [])


def test_evaluate_t63_matches_theory_without_noise():
    p = _fast(delay_s=0.1, tau_xy_s=0.5, tau_z_s=0.5, speed_cap_mps=2.0)
    t, c, v = _data(p, noise_mps=0.0, plan=[(0, 1.0), (1, -1.0)])
    d = step_data(c, v, t, source="teleop_command")
    ev = evaluate(p, d, [0, 1])
    for row in ev["steps"]:
        assert row["t63_meas_s"] == pytest.approx(0.1 + 0.5, abs=0.01)
        assert row["t63_err_s"] < 1e-3
    assert ev["steps"][1]["axis"] == "y" and ev["steps"][1]["step_mps"] == pytest.approx(-1.0, abs=1e-12)


def test_lag2_fit_recovers_its_second_pole():
    """lag2 on lag2 data: tau2 within 10 %; delay and tau2 trade off a little, so their sum within 5 %."""
    true2 = ResponseParams(0.12, 0.5, 0.4, 3.0, 2.5, 2.0, "lag2", tau2_s=0.1)
    t, c, v = _data(true2, scale=1.33)
    p, report = fit(c, v, t, "lag2", split_alternate(len(PLAN))[0], source="teleop_command")
    assert p.family == "lag2" and report["free_params"][-1] == "tau2_s"
    assert p.tau2_s == pytest.approx(0.1, rel=0.10)
    assert p.delay_s + p.tau2_s == pytest.approx(0.22, rel=0.05)
    for name in FITTED[1:]:
        assert getattr(p, name) == pytest.approx(getattr(true2, name), rel=0.05), name


def test_default_starts_begin_with_binding_acceleration_limits():
    """A limit that never binds has zero gradient: every default start must sit below the 3 m/s^2 test value."""
    from svg_training.models.fit import LAG1_STARTS
    assert any(s[3] < 3.0 and s[4] < 2.5 for s in LAG1_STARTS)
