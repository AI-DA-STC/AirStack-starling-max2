"""STE L1.3: scripts/fit_estimate_error.py recovers known estimate-error statistics (sigma, tau) from synthetic data.

No real flight log is read: every test makes its own data. Gauss-Markov series use the exact discretisation of
models/estimator_effect.py (x = a x + sigma sqrt(1 - a^2) w, a = exp(-dt / tau)); one test draws the errors with
EstimatorEffect itself (the training model), one runs the whole script on a hand-built ULog file.
"""
import importlib.util
import json
import math
import pathlib
import struct

import numpy as np
import pytest
import torch

from svg_training.models.estimator_effect import EstimatorEffect

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fit_estimate_error.py"


def _load():
    spec = importlib.util.spec_from_file_location("fit_estimate_error", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fe = _load()


def gm(n, dt, sigma, tau, rng, k=1):
    """k independent stationary first-order Gauss-Markov series of n samples, shape (n, k)."""
    a = math.exp(-dt / tau)
    x = np.empty((n, k))
    x[0] = rng.standard_normal(k) * sigma
    w = rng.standard_normal((n, k)) * sigma * math.sqrt(1 - a * a)
    for i in range(1, n):
        x[i] = a * x[i - 1] + w[i]
    return x


# ------------------------------------------------------------------------------------------- statistics
@pytest.mark.parametrize("sigma,tau", [(0.02, 0.5), (0.005, 2.0)])
def test_fit_recovers_sigma_and_tau_of_a_pure_gauss_markov_series(sigma, tau):
    dt = 0.1
    x = gm(60000, dt, sigma, tau, np.random.default_rng(1))[:, 0]
    r = fe.fit_gm([x], dt)
    assert r["tau_resolved"]
    assert r["sigma_gm"] == pytest.approx(sigma, rel=0.05)
    assert r["tau_s"] == pytest.approx(tau, rel=0.10)
    assert r["tau_efold_s"] == pytest.approx(tau, rel=0.10)          # no white part: all three agree
    assert r["tau_ar1_s"] == pytest.approx(tau, rel=0.10)
    assert r["sigma_white"] is None or r["sigma_white"] < 0.25 * sigma   # None: the free intercept came out above 1
    assert r["n"] == 60000
    assert r["n_eff"] == pytest.approx(60000 * dt / (2 * tau), rel=0.15)


def test_white_floor_is_separated_and_does_not_bias_tau():
    dt, sigma, tau, white = 0.1, 0.02, 0.6, 0.012
    rng = np.random.default_rng(2)
    x = gm(80000, dt, sigma, tau, rng)[:, 0] + rng.standard_normal(80000) * white
    r = fe.fit_gm([x], dt)
    assert r["tau_s"] == pytest.approx(tau, rel=0.12)
    assert r["sigma_gm"] == pytest.approx(sigma, rel=0.06)
    assert r["sigma_white"] == pytest.approx(white, rel=0.2)
    assert r["std"] == pytest.approx(math.hypot(sigma, white), rel=0.05)
    assert r["tau_ar1_s"] < 0.85 * tau                     # the naive AR(1) is biased low by the white part (why A is fitted)


def test_a_smoother_than_first_order_error_gets_a_through_origin_tau_and_no_white_part():
    """Two first-order filters in a row (autocorrelation (1 + t/T) exp(-t/T), smooth at 0): the free fit's intercept
    lands above 1, so A is held at 1 and tau refitted through the origin; it then sits near the 1/e time (added after
    the first look at the real logs, whose position and velocity errors have this shape)."""
    dt, T = 0.1, 0.4
    rng = np.random.default_rng(8)
    a = math.exp(-dt / T)
    w = rng.standard_normal(200000)
    x1 = np.empty_like(w)
    x2 = np.empty_like(w)
    x1[0] = x2[0] = 0.0
    for i in range(1, w.size):
        x1[i] = a * x1[i - 1] + w[i]
        x2[i] = a * x2[i - 1] + x1[i]
    r = fe.fit_gm([x2[1000:]], dt)
    assert r["A_fit"] > 1.0 and r["A"] == 1.0
    assert r["sigma_white"] is None and r["sigma_gm"] == pytest.approx(r["std"])
    assert r["tau_s"] == pytest.approx(r["tau_efold_s"], rel=0.15)
    assert r["tau_efold_s"] == pytest.approx(2.146 * T, rel=0.08)          # (1 + x) e^-x = 1/e at x = 2.146


def test_tau_shorter_than_the_sample_interval_is_reported_unresolved():
    dt = 0.1
    x = gm(20000, dt, 0.01, 0.02, np.random.default_rng(3))[:, 0]      # tau = dt / 5: rho(1) = 0.007
    r = fe.fit_gm([x], dt)
    assert not r["tau_resolved"]
    assert r["tau_s"] is None and r["sigma_gm"] is None
    assert r["std"] == pytest.approx(0.01, rel=0.05)


def test_segments_are_pooled_without_crossing_gaps():
    dt, sigma, tau = 0.1, 0.02, 0.5
    rng = np.random.default_rng(4)
    segs = [gm(400, dt, sigma, tau, rng)[:, 0] for _ in range(100)]    # 100 segments of 40 s
    r = fe.fit_gm(segs, dt)
    assert r["n"] == 40000 and r["n_segments"] == 100
    assert r["sigma_gm"] == pytest.approx(sigma, rel=0.06)
    assert r["tau_s"] == pytest.approx(tau, rel=0.12)
    # a segment too short for one lag adds samples to the spread but no lag pairs
    r2 = fe.fit_gm(segs + [np.array([5.0])], dt)
    assert r2["n"] == 40001


def test_segments_of_splits_at_gaps_and_drops_short_runs():
    t = np.r_[np.arange(0, 10, 0.1), np.arange(20, 21, 0.1), np.arange(30, 40, 0.1)]
    mask = np.ones_like(t, bool)
    mask[50] = False                                                    # a hole in the first run
    segs = fe.segments_of(t, mask, min_len_s=3.0, max_gap_s=0.25)
    spans = [(round(t[a], 1), round(t[b - 1], 1)) for a, b in segs]
    assert spans == [(0.0, 4.9), (5.1, 9.9), (30.0, 39.9)]              # 20-21 s is too short


def test_resample_on_a_uniform_grid_inside_each_segment():
    t = np.array([0.0, 0.09, 0.21, 0.30, 0.41, 0.5])
    x = 2.0 * t
    g, y = fe.resample(t, x, 0.1)
    np.testing.assert_allclose(g, [0.0, 0.1, 0.2, 0.3, 0.4, 0.5], atol=1e-12)
    np.testing.assert_allclose(y, 2.0 * g, atol=1e-12)


# ------------------------------------------------------------------------------------------- geometry
def _quat_axis_angle(axis, angle):
    axis = np.asarray(axis, float) / np.linalg.norm(axis)
    return np.r_[math.cos(angle / 2), math.sin(angle / 2) * axis]


def test_small_angle_is_the_body_rotation_from_reference_to_estimate_sign_free():
    q_ref = _quat_axis_angle([0.3, -0.2, 1.0], 1.9)[None]
    rot = np.array([0.004, -0.003, 0.006])
    dq = np.r_[1.0, rot / 2]
    dq /= np.linalg.norm(dq)
    q_est = fe.quat_mul(q_ref, dq[None])                                # as models/estimator_effect.py: q (x) dq
    np.testing.assert_allclose(fe.small_angle(q_ref, q_est)[0], rot, atol=2e-6)
    np.testing.assert_allclose(fe.small_angle(-q_ref, q_est)[0], rot, atol=2e-6)   # q and -q: same rotation


def test_quaternion_interpolation_handles_sign_flips():
    t = np.array([0.0, 1.0])
    q = np.stack([_quat_axis_angle([0, 0, 1], 0.2), -_quat_axis_angle([0, 0, 1], 0.4)])
    qi = fe.interp_quat(t, q, np.array([0.5]))
    ang = fe.small_angle(_quat_axis_angle([0, 0, 1], 0.3)[None], qi)[0]
    np.testing.assert_allclose(ang, 0.0, atol=1e-3)


def test_local_slope_recovers_velocity_with_jittered_stamps():
    rng = np.random.default_rng(5)
    t = np.cumsum(0.03 + rng.uniform(-0.005, 0.005, 400))
    x = 0.4 * t + 0.3 * t ** 2
    v = fe.local_slope(t, x, half=3)
    ok = ~np.isnan(v)
    assert ok.sum() == 400 - 6
    np.testing.assert_allclose(v[ok], 0.4 + 0.6 * t[ok], atol=2e-3)     # exact for a quadratic, up to the jitter


def test_noise_floor_recovers_white_noise_on_a_smooth_track():
    rng = np.random.default_rng(6)
    t = np.arange(0, 60, 0.03)
    x = 0.05 * np.sin(1.3 * t) + rng.standard_normal(t.size) * 0.0007
    assert fe.noise_floor(t, x, np.ones_like(t, bool), half=3) == pytest.approx(0.0007, rel=0.08)


def test_best_lag_recovers_a_known_delay():
    t = np.arange(0, 60, 0.03)
    s = lambda tt: 0.03 * np.sin(2 * np.pi * 0.7 * tt) + 0.02 * np.sin(2 * np.pi * 1.9 * tt + 1)   # noqa: E731
    t_est = np.arange(1, 59, 0.05)
    lag, curve = fe.best_lag(t_est, s(t_est), t, s(t - 0.023), np.arange(-0.1, 0.2001, 0.001))
    assert lag == pytest.approx(0.023, abs=0.0015)


# ------------------------------------------------------------------------------------------- training model
def test_recovers_what_the_training_estimator_draws():
    """EstimatorEffect (the model the trainer flies) draws position and attitude errors with known (sigma, tau) at
    the 100 Hz physics step; sampled at the log's 10 Hz and 20 Hz, the fit gives them back."""
    n, dt = 48, 0.01
    err = {"pos": (0.02, 0.5), "att": (0.005, 0.4), "vel": (0.03, 0.3)}
    eff = EstimatorEffect(n, 1, 0, 0.0, 0.0, 0.0, 0.0, "cpu", torch.float64, seed=7, error=err, dt_s=dt)
    z3 = torch.zeros(n, 1, 3, dtype=torch.float64)
    q = torch.zeros(n, 1, 4, dtype=torch.float64)
    q[..., 0] = 1.0
    mask = torch.ones(n, 1, dtype=torch.bool)
    pos, quat, vel = [], [], []
    p, qq, v, _ = eff.reset(mask, z3, q, z3, z3)
    for _ in range(6000):                                               # 60 s per drone
        p, qq, v, _ = eff.push(z3, q, z3, z3)
        pos.append(p[:, 0].numpy().copy()); quat.append(qq[:, 0].numpy().copy()); vel.append(v[:, 0].numpy().copy())
    pos, quat, vel = np.stack(pos, 1), np.stack(quat, 1), np.stack(vel, 1)              # [n, T, 3 or 4]
    for name, series, every, (s, tau) in (("pos", pos, 10, err["pos"]), ("vel", vel, 10, err["vel"])):
        r = fe.fit_axes([series[i, ::every, k] for i in range(n) for k in range(3)], every * dt)
        assert r["sigma_gm"] == pytest.approx(s, rel=0.08), name
        assert r["tau_s"] == pytest.approx(tau, rel=0.15), name
    ident = np.tile([1.0, 0, 0, 0], (quat.shape[1], 1))
    rot = np.stack([fe.small_angle(ident, quat[i]) for i in range(n)])                # [n, T, 3] body rotation
    r = fe.fit_axes([rot[i, ::5, k] for i in range(n) for k in range(3)], 5 * dt)
    assert r["sigma_gm"] == pytest.approx(err["att"][0], rel=0.08)
    assert r["tau_s"] == pytest.approx(err["att"][1], rel=0.15)


# ------------------------------------------------------------------------------------------- whole script on a ULog
def _msg(kind: bytes, payload: bytes) -> bytes:
    return struct.pack("<HB", len(payload), kind[0]) + payload


def _param(name, value):
    key = (b"float " if isinstance(value, float) else b"int32_t ") + name.encode()
    val = struct.pack("<f", value) if isinstance(value, float) else struct.pack("<i", value)
    return _msg(b"P", bytes([len(key)]) + key + val)


def _qmul(a, b):
    return fe.quat_mul(a[None], b[None])[0]


def write_synthetic_ulog(path, *, dur=300.0, seed=11, pos=(0.01, 0.6), vel=(0.02, 0.4), att=(0.004, 0.5),
                         latency=0.02, mocap_noise=0.0005):
    """A hovering drone (NED (1, 2, -1) m) that rocks in roll and pitch. EKF2 output = truth + Gauss-Markov error
    (sigma per NED axis or one for all; position and velocity at 10 Hz, attitude at 20 Hz, all with jittered sample times); the mocap at 33 Hz, stamped on
    arrival `latency` s after capture, with white noise. Landed for the first 2 s."""
    rng = np.random.default_rng(seed)
    roll = lambda t: 0.03 * np.sin(2 * np.pi * 0.7 * t) + 0.01 * np.sin(2 * np.pi * 2.3 * t)    # noqa: E731
    pitch = lambda t: 0.02 * np.sin(2 * np.pi * 0.45 * t + 1) + 0.01 * np.sin(2 * np.pi * 1.7 * t)  # noqa: E731

    def q_true(t):
        qr = np.stack([np.cos(roll(t) / 2), np.sin(roll(t) / 2), 0 * t, 0 * t], -1)
        qp = np.stack([np.cos(pitch(t) / 2), 0 * t, np.sin(pitch(t) / 2), 0 * t], -1)
        yaw = 0.8
        qy = np.array([math.cos(yaw / 2), 0, 0, math.sin(yaw / 2)])
        return fe.quat_mul(fe.quat_mul(np.tile(qy, (t.size, 1)), qr), qp)

    p0 = np.array([1.0, 2.0, -1.0])
    t_lp = np.arange(0.0, dur, 0.1) + rng.uniform(-0.01, 0.01, int(round(dur / 0.1)))
    t_at = np.arange(0.0, dur, 0.05) + rng.uniform(-0.005, 0.005, int(round(dur / 0.05)))
    t_cap = np.arange(0.0, dur, 0.03)
    t_arr = t_cap + latency + rng.uniform(0, 0.004, t_cap.size)
    e_pos = gm(t_lp.size, 0.1, 1.0, pos[1], rng, 3) * np.broadcast_to(pos[0], (3,))     # sigma per NED axis allowed
    e_vel = gm(t_lp.size, 0.1, 1.0, vel[1], rng, 3) * np.broadcast_to(vel[0], (3,))
    e_att = gm(t_at.size, 0.05, att[0], att[1], rng, 3)
    q_est = np.stack([_qmul(q, np.r_[1.0, r / 2] / np.linalg.norm(np.r_[1.0, r / 2]))
                      for q, r in zip(q_true(t_at), e_att)])
    p_meas = p0 + rng.standard_normal((t_cap.size, 3)) * mocap_noise
    q_meas = q_true(t_cap)

    fmts = {"vehicle_visual_odometry": "uint64_t timestamp;uint64_t timestamp_sample;float[3] position;float[4] q;",
            "vehicle_local_position": "uint64_t timestamp;uint64_t timestamp_sample;float x;float y;float z;"
                                      "float vx;float vy;float vz;",
            "vehicle_attitude": "uint64_t timestamp;uint64_t timestamp_sample;float[4] q;",
            "vehicle_land_detected": "uint64_t timestamp;bool landed;uint8_t[7] _padding0;"}
    body = b"ULog\x01\x12\x35\x01" + struct.pack("<Q", 0)
    for name, f in fmts.items():
        body += _msg(b"F", f"{name}:{f}".encode())
    body += _param("EKF2_EV_DELAY", 50.0) + _param("EKF2_EV_CTRL", 11) + _param("EKF2_HGT_REF", 3)
    for mid, name in enumerate(fmts):
        body += _msg(b"A", struct.pack("<BH", 0, mid) + name.encode())
    us = lambda t: int(round((t + 1.0) * 1e6))                                                  # noqa: E731
    events = []
    for i, t in enumerate(t_arr):
        events.append((t, struct.pack("<H", 0) + struct.pack("<QQ3f4f", us(t), us(t), *p_meas[i], *q_meas[i])))
    for i, t in enumerate(t_lp):
        p = p0 + e_pos[i]
        events.append((t, struct.pack("<H", 1) + struct.pack("<QQ6f", us(t), us(t), *p, *e_vel[i])))
    for i, t in enumerate(t_at):
        events.append((t, struct.pack("<H", 2) + struct.pack("<QQ4f", us(t), us(t), *q_est[i])))
    for t in np.arange(0.0, dur, 0.25):
        events.append((t, struct.pack("<H", 3) + struct.pack("<Q?", us(t), bool(t < 2.0))))
    for _, payload in sorted(events, key=lambda e: e[0]):
        body += _msg(b"D", payload)
    pathlib.Path(path).write_bytes(body)


def test_whole_script_on_a_synthetic_ulog(tmp_path):
    log = tmp_path / "synthetic.ulg"
    write_synthetic_ulog(log)
    out = tmp_path / "out"
    assert fe.main(["--logs", str(log), "--main", str(log), "--out-dir", str(out), "--no-figures"]) == 0
    res = json.loads((out / "results.json").read_text())
    r = res["logs"][0]
    assert r["topics"]["measurement"] == "vehicle_visual_odometry"
    assert r["ekf2"]["EKF2_EV_DELAY"] == 50.0 and r["ekf2"]["ev_fuses"] == ["horizontal position", "vertical position",
                                                                             "yaw"]
    assert len(r["sha256"]) == 64
    hov = r["hover"]
    assert hov["pos"]["pooled"]["sigma_gm"] == pytest.approx(0.01, rel=0.12)
    assert hov["pos"]["pooled"]["tau_s"] == pytest.approx(0.6, rel=0.25)
    assert hov["att"]["pooled"]["sigma_gm"] == pytest.approx(0.004, rel=0.12)
    assert hov["att"]["pooled"]["tau_s"] == pytest.approx(0.5, rel=0.25)
    assert hov["vel"]["pooled"]["sigma_gm"] == pytest.approx(0.02, rel=0.15)
    prop_json = res["proposal"]
    assert prop_json["pos"]["tau_s"] == pytest.approx(hov["pos"]["pooled"]["tau_efold_s"], rel=0.06)   # the 1/e rule
    assert prop_json["pos"]["tau_origin_s"] == pytest.approx(hov["pos"]["pooled"]["tau_origin_s"], rel=0.06)
    assert "second_order" in hov["pos"]["pooled"]
    # the mocap's own noise and its age at the arrival stamp
    assert r["mocap"]["pos_noise_m"] == pytest.approx(0.0005, rel=0.2)
    assert r["latency"]["tilt_lag_s"] == pytest.approx(0.022, abs=0.004)
    assert r["latency"]["stamp_minus_write_ms"] is not None
    # the proposal: EXPLORATORY, its source named, v1's keys only
    prop = (out / "proposed_starling_physics_v1.toml").read_text()
    assert "EXPLORATORY" in prop and "PROPOSED" in prop and log.name in prop
    for key in ("state_error_pos_m", "state_error_pos_tau_s", "state_error_att_rad", "state_error_att_tau_s"):
        assert f"\n{key} = " in prop
    assert (out / "results.md").exists()


def test_ulog_path_maps_ned_axes_to_enu_with_a_sigma_per_axis(tmp_path):
    """Different sigma per NED axis: ENU x = NED y (east), ENU y = NED x (north), ENU z = up. Velocity tau checked too."""
    log = tmp_path / "axes.ulg"
    write_synthetic_ulog(log, dur=400.0, seed=12, pos=((0.004, 0.012, 0.024), 0.6), vel=((0.03, 0.01, 0.02), 0.4))
    out = tmp_path / "out"
    assert fe.main(["--logs", str(log), "--out-dir", str(out), "--no-figures"]) == 0
    hov = json.loads((out / "results.json").read_text())["logs"][0]["hover"]
    for q, want in (("pos", {"x": 0.012, "y": 0.004, "z": 0.024}), ("vel", {"x": 0.01, "y": 0.03, "z": 0.02})):
        for ax, s in want.items():
            assert hov[q]["axes"][ax]["std"] == pytest.approx(s, rel=0.15), (q, ax)
    assert hov["vel"]["pooled"]["tau_efold_s"] == pytest.approx(0.4, rel=0.2)
    assert hov["vel"]["pooled"]["tau_origin_s"] == pytest.approx(0.4, rel=0.2)


def _second_order_series(zeta, wn, n_series, dur, dt_sim, every, rng):
    """x'' + 2 zeta wn x' + wn^2 x = white noise, semi-implicit Euler at dt_sim, kept every `every` steps."""
    x = np.zeros(n_series)
    v = np.zeros(n_series)
    steps = int(dur / dt_sim)
    out = []
    for i in range(steps):
        v += (-2 * zeta * wn * v - wn * wn * x) * dt_sim + rng.standard_normal(n_series) * math.sqrt(dt_sim)
        x += v * dt_sim
        if i % every == 0:
            out.append(x.copy())
    return np.array(out).T[:, 200:]                       # drop the start-up transient (20 s at 0.1 s)


def test_second_order_fit_recovers_damping_and_natural_frequency_of_an_oscillating_error():
    zeta, wn = 0.3, 1.0
    rng = np.random.default_rng(9)
    series = _second_order_series(zeta, wn, 60, 800.0, 0.005, 20, rng)        # 0.1 s samples
    r = fe.fit_axes(list(series), 0.1)
    so = r["second_order"]
    assert so["zeta"] == pytest.approx(zeta, rel=0.15)
    assert so["wn_rad_s"] == pytest.approx(wn, rel=0.08)
    assert so["sse_ratio_first_over_second"] > 3                     # the swing-back is far from first order
    assert r["rho_min"] < -0.2
    # and a first-order truth gives a heavily damped (no swing-back) second-order fit
    g = fe.fit_axes(list(gm(20000, 0.1, 1.0, 0.5, np.random.default_rng(10), 4).T), 0.1)
    assert g["second_order"]["sse_ratio_first_over_second"] < 2
