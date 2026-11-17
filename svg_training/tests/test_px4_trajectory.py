"""PX4 trajectory-setpoint model (real-drone path): position + velocity setpoint -> drone velocity.

Synthetic data only, no ROS, no GPU, no flight logs. Known parameters are recovered by the fit within tolerance;
the held-out split is fixed before fitting and the held-out data cannot change the fit. The small ULog reader of
scripts/fit_real_px4.py is tested on a hand-built file (parameters, array fields, trailing padding cut off).
"""
import importlib.util
import math
import pathlib
import struct

import numpy as np
import pytest

from svg_training.models import px4_trajectory as m

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fit_real_px4.py"
DT = 0.01


def _load_script():
    spec = importlib.util.spec_from_file_location("fit_real_px4", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _const(n, value):
    return np.tile(np.asarray(value, dtype=float), (n, 1))


def _commander_leg(v_target, t_on=1.0, t_hold=2.5, t_total=6.0, ramp_mps2=5.0, p_start=(0.0, 0.0)):
    """What the commander sends for one stick push: v_ff ramps at ramp_mps2 to v_target, holds, ramps back to 0;
    p_sp = integral of v_ff (the reference point); a_ff = d v_ff / dt. Arrays (N, 2) on the DT grid."""
    n = int(round(t_total / DT))
    t = np.arange(n) * DT
    v = np.zeros((n, 2))
    target = np.asarray(v_target, dtype=float)
    cur = np.zeros(2)
    for k in range(n):
        goal = target if t_on <= t[k] < t_on + t_hold else np.zeros(2)
        dv = goal - cur
        norm = np.linalg.norm(dv)
        step = ramp_mps2 * DT
        cur = goal.copy() if norm <= step else cur + dv * (step / norm)
        v[k] = cur
    a = np.gradient(v, DT, axis=0)
    p = np.asarray(p_start, dtype=float) + np.concatenate([np.zeros((1, 2)), np.cumsum(v[:-1] * DT, axis=0)])
    return t, p, v, a


def _windows(true, legs, noise=0.01, seed=0, every=10):
    """Simulate `true` on each commander leg; measure the velocity every `every` steps (10 Hz) with noise."""
    rng = np.random.default_rng(seed)
    out = []
    for i, target in enumerate(legs):
        t, p_sp, v_ff, a_ff = _commander_leg(target)
        v, _p = m.simulate(p_sp, v_ff, a_ff, DT, true, p0=p_sp[0], v0=np.zeros(2))
        idx = np.arange(0, len(t), every)
        out.append(m.Window(t_s=t, p_sp=p_sp, v_ff=v_ff, a_ff=a_ff, p0=p_sp[0].copy(), v0=np.zeros(2),
                            meas_idx=idx, v_meas=v[idx] + rng.normal(0.0, noise, (len(idx), 2)),
                            label=f"leg {i}"))
    return out


LEGS = [(0.5, 0.0), (0.0, -0.5), (-1.0, 0.0), (0.0, 1.0), (0.7, 0.7), (-0.5, 0.3), (1.0, 0.0), (0.0, -1.0)]


# ------------------------------------------------------------------------------------------------- parameters
def test_params_validate_and_roundtrip():
    p = m.TrajectoryParams(family="lag1", kp_xy=0.95, tau_s=0.4, delay_s=0.1, acc_max_mps2=3.0)
    assert m.TrajectoryParams.from_dict(p.to_dict()) == p
    with pytest.raises(ValueError):
        m.TrajectoryParams(family="lag3", kp_xy=0.95, tau_s=0.4, delay_s=0.1, acc_max_mps2=3.0)
    with pytest.raises(ValueError):
        m.TrajectoryParams(family="lag1", kp_xy=0.95, tau_s=-0.1, delay_s=0.1, acc_max_mps2=3.0)
    with pytest.raises(ValueError):
        m.TrajectoryParams(family="lag1", kp_xy=0.95, tau_s=0.4, delay_s=0.1, acc_max_mps2=0.0)
    with pytest.raises(ValueError):
        m.TrajectoryParams.from_dict({**p.to_dict(), "bogus": 1.0})


# ------------------------------------------------------------------------------------------------- the law
def test_split_alternate_is_fixed_by_count_only():
    assert m.split_alternate(5) == ((0, 2, 4), (1, 3))
    assert m.split_alternate(1) == ((0,), ())


def test_consistent_setpoint_is_tracked_without_error():
    """p_sp moving at v_ff (what the commander sends): the drone ends at v_ff with the position error near 0."""
    n = 800
    v_ff = _const(n, (0.5, -0.3))
    p_sp = np.cumsum(np.concatenate([np.zeros((1, 2)), v_ff[:-1] * DT]), axis=0)
    for fam in m.FAMILIES:
        p = m.TrajectoryParams(family=fam, kp_xy=0.95, tau_s=0.2, delay_s=0.0, acc_max_mps2=math.inf)
        v, pos = m.simulate(p_sp, v_ff, np.zeros((n, 2)), DT, p, p0=np.zeros(2), v0=np.zeros(2))
        np.testing.assert_allclose(v[-1], v_ff[-1], atol=0.01)
        assert np.linalg.norm(pos[-1] - p_sp[-1]) < 0.05


def test_lag1_time_constant_is_tau():
    """Kp = 0, no feed-forward: a velocity step is a first-order lag; 63 % is reached at tau."""
    n = 400
    v_ff = np.zeros((n, 2))
    v_ff[10:, 0] = 1.0
    p = m.TrajectoryParams(family="lag1", kp_xy=0.0, tau_s=0.5, delay_s=0.0, acc_max_mps2=math.inf)
    v, _ = m.simulate(np.zeros((n, 2)), v_ff, np.zeros((n, 2)), DT, p, p0=np.zeros(2), v0=np.zeros(2))
    t = np.arange(n) * DT
    assert m.time_to_63pct(t, v[:, 0], 0.0, 1.0, t[10]) == pytest.approx(0.5, abs=0.02)


def test_position_error_gives_kp_velocity():
    """Fast loop, v_ff = 0, setpoint 1 m away: the commanded speed is Kp * error, so the error decays at Kp."""
    n = 300
    p_sp = _const(n, (1.0, 0.0))
    p = m.TrajectoryParams(family="lag1", kp_xy=0.95, tau_s=0.01, delay_s=0.0, acc_max_mps2=math.inf)
    v, pos = m.simulate(p_sp, np.zeros((n, 2)), np.zeros((n, 2)), DT, p, p0=np.zeros(2), v0=np.zeros(2))
    k = 100   # t = 1 s
    assert v[k, 0] == pytest.approx(0.95 * (1.0 - pos[k, 0]), rel=0.03)
    assert 1.0 - pos[k, 0] == pytest.approx(math.exp(-0.95), rel=0.05)


def test_delay_shifts_the_response():
    n = 400
    v_ff = np.zeros((n, 2))
    v_ff[50:, 1] = 0.5
    base = dict(family="lag1", kp_xy=0.0, tau_s=0.3, acc_max_mps2=math.inf)
    v0, _ = m.simulate(np.zeros((n, 2)), v_ff, np.zeros((n, 2)), DT, m.TrajectoryParams(delay_s=0.0, **base),
                       p0=np.zeros(2), v0=np.zeros(2))
    v1, _ = m.simulate(np.zeros((n, 2)), v_ff, np.zeros((n, 2)), DT, m.TrajectoryParams(delay_s=0.15, **base),
                       p0=np.zeros(2), v0=np.zeros(2))
    np.testing.assert_allclose(v1[15:], v0[:-15], atol=1e-9)


def test_acceleration_limit_and_speed_cap():
    """The PID's integrator overshoots the cap after a saturated climb and then settles (PX4 does the same)."""
    n = 1500
    v_ff = np.zeros((n, 2))
    v_ff[10:] = (4.0, 3.0)                       # 5 m/s, above the 3 m/s cap
    for fam in m.FAMILIES:
        p = m.TrajectoryParams(family=fam, kp_xy=0.0, tau_s=0.05, delay_s=0.0, acc_max_mps2=2.0)
        v, _ = m.simulate(np.zeros((n, 2)), v_ff, np.zeros((n, 2)), DT, p, p0=np.zeros(2), v0=np.zeros(2))
        acc = np.linalg.norm(np.diff(v, axis=0), axis=1) / DT
        assert acc.max() <= 2.0 + 1e-6
        assert np.linalg.norm(v[-1]) == pytest.approx(3.0, abs=0.02)
        assert np.linalg.norm(v, axis=1).max() < 3.3


def test_feedforward_speeds_up_the_response():
    t, p_sp, v_ff, a_ff = _commander_leg((0.5, 0.0))
    kw = dict(family="pid", kp_xy=0.95, tau_s=0.1, delay_s=0.0, acc_max_mps2=math.inf)
    v_ff1, _ = m.simulate(p_sp, v_ff, a_ff, DT, m.TrajectoryParams(ff_gain=1.0, **kw), p0=p_sp[0], v0=np.zeros(2))
    v_ff0, _ = m.simulate(p_sp, v_ff, a_ff, DT, m.TrajectoryParams(ff_gain=0.0, **kw), p0=p_sp[0], v0=np.zeros(2))
    on = int(round(1.0 / DT))
    t63_1 = m.time_to_63pct(t, v_ff1[:, 0], 0.0, 0.5, t[on])
    t63_0 = m.time_to_63pct(t, v_ff0[:, 0], 0.0, 0.5, t[on])
    assert t63_1 < t63_0


def test_batch_simulation_matches_single():
    legs = [_commander_leg(v) for v in [(0.5, 0.0), (0.0, -0.4)]]
    p = m.TrajectoryParams(family="pid", kp_xy=0.95, tau_s=0.12, delay_s=0.07, acc_max_mps2=2.5)
    singles = [m.simulate(ps, vf, af, DT, p, p0=ps[0], v0=np.zeros(2))[0] for _t, ps, vf, af in legs]
    stack = lambda i: np.stack([leg[i] for leg in legs])                          # noqa: E731
    batch, _ = m.simulate(stack(1), stack(2), stack(3), DT, p, p0=stack(1)[:, 0], v0=np.zeros((2, 2)))
    for b, s in zip(batch, singles):
        np.testing.assert_allclose(b, s, atol=1e-12)


def test_simulate_windows_batch_equals_one_by_one():
    true = m.TrajectoryParams(family="pid", kp_xy=0.95, tau_s=0.12, delay_s=0.05, acc_max_mps2=2.0)
    windows = _windows(true, LEGS[:3])
    windows[1] = m.Window(**{**windows[1].__dict__, **{k: getattr(windows[1], k)[:350]
                                                       for k in ("t_s", "p_sp", "v_ff", "a_ff")},
                             "meas_idx": windows[1].meas_idx[:35], "v_meas": windows[1].v_meas[:35]})
    for w, v in zip(windows, m.simulate_windows(true, windows)):
        np.testing.assert_allclose(v, m.simulate_window(true, w), atol=1e-12)


# ------------------------------------------------------------------------------------------------- legs
def test_find_legs_merges_short_gaps_and_drops_blips():
    t = np.arange(0, 30, 0.2)
    v = np.zeros((len(t), 2))
    v[(t >= 2) & (t < 4)] = (0.5, 0.0)            # leg 1
    v[(t >= 4.4) & (t < 5)] = (0.5, 0.0)          # 0.4 s gap -> merged into leg 1
    v[(t >= 10) & (t < 10.2)] = (0.0, 0.3)        # blip -> dropped
    v[(t >= 15) & (t < 18)] = (0.0, -0.4)         # leg 2
    legs = m.find_legs(t, v, on_mps=0.1, min_len_s=0.6, merge_gap_s=1.0)
    assert [(round(a, 1), round(b, 1)) for a, b in legs] == [(2.0, 4.8), (15.0, 17.8)]


# ------------------------------------------------------------------------------------------------- the fit
def test_fit_recovers_lag1_parameters():
    true = m.TrajectoryParams(family="lag1", kp_xy=0.95, tau_s=0.35, delay_s=0.12, acc_max_mps2=1.5)
    windows = _windows(true, LEGS)
    train, held = m.split_alternate(len(windows))
    start = m.TrajectoryParams(family="lag1", kp_xy=0.95, tau_s=0.8, delay_s=0.0, acc_max_mps2=6.0)
    got, info = m.fit([windows[i] for i in train], start, free=("tau_s", "delay_s", "acc_max_mps2"))
    assert got.kp_xy == 0.95                                        # fixed, never fitted
    assert got.tau_s == pytest.approx(0.35, rel=0.10)
    assert got.delay_s == pytest.approx(0.12, abs=0.03)
    assert got.acc_max_mps2 == pytest.approx(1.5, rel=0.15)
    assert m.velocity_rms(got, [windows[i] for i in held]) < 0.02   # noise is 0.01 m/s per axis
    assert info["train_rms_mps"] < 0.02


def test_fit_recovers_pid_attitude_lag_and_delay():
    true = m.TrajectoryParams(family="pid", kp_xy=0.95, tau_s=0.15, delay_s=0.08, acc_max_mps2=math.inf,
                              vel_p=1.8, vel_i=0.4, vel_d=0.2)
    windows = _windows(true, LEGS, noise=0.005)
    train, _held = m.split_alternate(len(windows))
    start = m.TrajectoryParams(family="pid", kp_xy=0.95, tau_s=0.5, delay_s=0.0, acc_max_mps2=math.inf,
                               vel_p=1.8, vel_i=0.4, vel_d=0.2)
    got, _info = m.fit([windows[i] for i in train], start, free=("tau_s", "delay_s"))
    assert (got.vel_p, got.vel_i, got.vel_d) == (1.8, 0.4, 0.2)
    assert got.tau_s == pytest.approx(0.15, abs=0.04)
    assert got.delay_s == pytest.approx(0.08, abs=0.03)


def test_held_out_windows_cannot_change_the_fit():
    true = m.TrajectoryParams(family="lag1", kp_xy=0.95, tau_s=0.4, delay_s=0.1, acc_max_mps2=3.0)
    windows = _windows(true, LEGS[:4])
    train, held = m.split_alternate(len(windows))
    start = m.TrajectoryParams(family="lag1", kp_xy=0.95, tau_s=0.8, delay_s=0.0, acc_max_mps2=6.0)
    a, _ = m.fit([windows[i] for i in train], start, free=("tau_s", "delay_s"))
    for i in held:                                                  # wreck the held-out measurements
        windows[i] = m.Window(**{**windows[i].__dict__, "v_meas": windows[i].v_meas * 0 + 9.0})
    b, _ = m.fit([windows[i] for i in train], start, free=("tau_s", "delay_s"))
    assert a == b


def test_fit_refuses_unknown_free_parameter():
    true = m.TrajectoryParams(family="lag1", kp_xy=0.95, tau_s=0.4, delay_s=0.1, acc_max_mps2=3.0)
    with pytest.raises(ValueError):
        m.fit(_windows(true, LEGS[:2]), true, free=("kp_xy",))      # Kp is read from the log, never fitted


# ------------------------------------------------------------------------------------------------- ULog reader
def _msg(kind: bytes, payload: bytes) -> bytes:
    return struct.pack("<HB", len(payload), kind[0]) + payload


def _param(name: str, value) -> bytes:
    key = (f"float {name}" if isinstance(value, float) else f"int32_t {name}").encode()
    val = struct.pack("<f", value) if isinstance(value, float) else struct.pack("<i", value)
    return _msg(b"P", bytes([len(key)]) + key + val)


def test_ulog_reader_parameters_arrays_and_cut_padding(tmp_path):
    fmt = b"trajectory_setpoint:uint64_t timestamp;float[3] position;float[3] velocity;uint8_t[4] _padding0;"
    body = b"ULog\x01\x12\x35\x01" + struct.pack("<Q", 0)
    body += _msg(b"F", fmt)
    body += _param("MPC_XY_P", 0.95) + _param("MAV_SYS_ID", 2)
    body += _msg(b"A", struct.pack("<BH", 0, 7) + b"trajectory_setpoint")
    for k in range(3):
        payload = struct.pack("<Q3f3f", 1000 * k, k, 2.0 * k, -k, 0.5, 0.25, 0.0)   # padding cut off (as logged)
        body += _msg(b"D", struct.pack("<H", 7) + payload)
    body += _param("MPC_XY_P", 1.10)                                 # changed in flight
    path = tmp_path / "t.ulg"
    path.write_bytes(body)
    data, params, changes = _load_script().read_ulog_full(path, ["trajectory_setpoint"])
    ts = data["trajectory_setpoint"]
    np.testing.assert_allclose(ts["timestamp"], [0, 1000, 2000])
    np.testing.assert_allclose(ts["position[1]"], [0.0, 2.0, 4.0])
    np.testing.assert_allclose(ts["velocity[1]"], [0.25] * 3)
    assert params["MPC_XY_P"] == pytest.approx(1.10)
    assert params["MAV_SYS_ID"] == 2
    assert changes == [("MPC_XY_P", pytest.approx(0.95), pytest.approx(1.10))]


# ------------------------------------------------------------------------------------------------- fix round 1 (I4)
def _flight(t_sp_offset=0.037, t_lp_offset=0.013):
    """A synthetic flight dict as load_flight returns it. Setpoint at 5 Hz, measurement at 10 Hz, on different
    phases. v_ff (east) is a trapezoid whose corners sit on 5 Hz samples, so joining the samples is exact."""
    t_sp = t_sp_offset + 0.2 * np.arange(101)                       # 0.037 .. 20.037
    corners_t = t_sp_offset + np.array([0.0, 5.0, 5.4, 8.0, 8.4, 20.0])
    corners_v = np.array([0.0, 0.0, 0.4, 0.4, 0.0, 0.0])
    vx = lambda t: np.interp(t, corners_t, corners_v)                # noqa: E731
    ps = lambda t: np.stack([1.0 + 0.1 * t, -0.5 + 0.05 * t], axis=-1)   # noqa: E731
    t_lp = t_lp_offset + 0.1 * np.arange(201)
    v = np.stack([np.sin(t_lp), np.cos(t_lp)], axis=-1)
    f = {"t_sp": t_sp, "p_sp": ps(t_sp), "v_ff": np.stack([vx(t_sp), 0 * t_sp], axis=-1),
         "a_ff_logged": np.zeros((len(t_sp), 2)), "t_lp": t_lp, "p": np.stack([t_lp, -t_lp], axis=-1), "v": v,
         "a": np.zeros((len(t_lp), 2)), "height_m": np.ones(len(t_lp))}
    return f, vx, ps


def test_join_5hz_setpoint_to_10hz_measurement_with_known_offsets():
    """The grid starts on a measurement sample; every measured value is the logged one at its own time (not shifted
    by the 5 Hz / 10 Hz phase offsets); the setpoint on the grid is the exact join of its 5 Hz samples; the
    rebuilt acceleration is the slope of that join (0.4 m/s over 0.4 s = 1.0 m/s^2)."""
    S = _load_script()
    f, vx, ps = _flight()
    windows, meta = S.make_windows(f, "derived")
    assert len(windows) == 1
    w = windows[0]
    assert np.min(np.abs(f["t_lp"] - w.t_s[0])) < 1e-9                  # grid on a measurement time
    t_meas = w.t_s[w.meas_idx]
    j = np.array([np.argmin(np.abs(f["t_lp"] - t)) for t in t_meas])
    assert np.max(np.abs(f["t_lp"][j] - t_meas)) < 0.5 * S.DT_S + 1e-9
    np.testing.assert_allclose(w.v_meas, f["v"][j], atol=1e-12)        # value at its own time
    np.testing.assert_allclose(w.v_meas[:, 0], np.sin(t_meas), atol=0.006)
    np.testing.assert_allclose(w.v_ff[:, 0], vx(w.t_s), atol=1e-9)
    np.testing.assert_allclose(w.p_sp, ps(w.t_s), atol=1e-9)
    ramp = (w.t_s > f["t_sp"][0] + 5.0 + 0.02) & (w.t_s < f["t_sp"][0] + 5.4 - 0.02)
    hold = (w.t_s > f["t_sp"][0] + 5.4 + 0.02) & (w.t_s < f["t_sp"][0] + 8.0 - 0.02)
    np.testing.assert_allclose(w.a_ff[ramp, 0], 1.0, atol=1e-6)
    np.testing.assert_allclose(w.a_ff[hold, 0], 0.0, atol=1e-6)
    np.testing.assert_allclose(w.p0, f["p"][j[0]], atol=1e-12)
    assert meta[0]["start_s"] == pytest.approx(f["t_sp"][0] + 5.2, abs=0.006)  # first sample above 0.1 m/s (rounded)


def _fmt(name, fields):
    return _msg(b"F", f"{name}:{';'.join(fields)};".encode())


def test_ned_to_enu_swap_on_a_synthetic_leg(tmp_path):
    """The drone flies NORTH at 0.3 m/s (PX4 NED x) at a constant 2 m EAST (NED y), 1.5 m up (NED z = -1.5).
    In ENU that is x (east) = 2 constant, y (north) increasing, vy = 0.3, height 1.5."""
    S = _load_script()
    traj = ["uint64_t timestamp", "float[3] position", "float[3] velocity", "float[3] acceleration"]
    lp = ["uint64_t timestamp", "float x", "float y", "float z", "float vx", "float vy", "float ax", "float ay"]
    lps = ["uint64_t timestamp", "float x", "float y", "float vx", "float vy"]
    body = b"ULog\x01\x12\x35\x01" + struct.pack("<Q", 0)
    body += _fmt("trajectory_setpoint", traj) + _fmt("vehicle_local_position", lp)
    body += _fmt("vehicle_local_position_setpoint", lps)
    for mid, name in enumerate(("trajectory_setpoint", "vehicle_local_position", "vehicle_local_position_setpoint")):
        body += _msg(b"A", struct.pack("<BH", 0, mid) + name.encode())
    for k in range(20):
        ts = 100_000 * k
        n = 0.3 * k * 0.1
        body += _msg(b"D", struct.pack("<H", 0) + struct.pack("<Q9f", ts, n, 2.0, -1.5, 0.3, 0.0, 0.0, 0.1, 0.0, 0.0))
        body += _msg(b"D", struct.pack("<H", 1) + struct.pack("<Q7f", ts, n, 2.0, -1.5, 0.3, 0.0, 0.1, 0.0))
        body += _msg(b"D", struct.pack("<H", 2) + struct.pack("<Q4f", ts, n, 2.0, 0.3, 0.0))
    path = tmp_path / "leg.ulg"
    path.write_bytes(body)
    f = S.load_flight(path)
    for key in ("p", "p_sp", "p_lps"):
        np.testing.assert_allclose(f[key][:, 0], 2.0, atol=1e-6)               # east stays 2 m
        np.testing.assert_allclose(np.diff(f[key][:, 1]), 0.03, atol=1e-6)      # north grows 0.03 m per sample
    for key in ("v", "v_ff", "v_lps"):
        np.testing.assert_allclose(f[key], np.tile([0.0, 0.3], (20, 1)), atol=1e-6)
    np.testing.assert_allclose(f["a_ff_logged"], np.tile([0.0, 0.1], (20, 1)), atol=1e-6)
    np.testing.assert_allclose(f["a"], np.tile([0.0, 0.1], (20, 1)), atol=1e-6)
    np.testing.assert_allclose(f["height_m"], 1.5, atol=1e-6)
    np.testing.assert_allclose(f["t_lp"], 0.1 * np.arange(20), atol=1e-9)


def test_pid_d_term_acts_on_the_measured_acceleration():
    """Kp = 0, no attitude lag, a 1 m/s step in the speed setpoint. PX4: acc = P e + I int(e) - D a, so
    (1 + D) a = P e + I int(e): a second-order response with initial acceleration P / (1 + D), here 1.5 m/s^2.
    A D term with the wrong sign, or on the error's rate instead of the measurement, starts at P / (1 - D)."""
    from scipy.linalg import expm
    P, I, D = 1.8, 0.4, 0.2
    dt, n = 0.001, 4001
    p = m.TrajectoryParams(family="pid", kp_xy=0.0, tau_s=0.0, delay_s=0.0, acc_max_mps2=math.inf,
                           vel_p=P, vel_i=I, vel_d=D)
    v_ff = np.tile([1.0, 0.0], (n, 1))
    v, _ = m.simulate(np.zeros((n, 2)), v_ff, np.zeros((n, 2)), dt, p, p0=np.zeros(2), v0=np.zeros(2))
    A = np.array([[0.0, 1.0], [-I / (1 + D), -P / (1 + D)]])           # state (int e, e), e = 1 - v
    for t in (0.25, 0.5, 1.0, 2.0, 4.0):
        e = (expm(A * t) @ np.array([0.0, 1.0]))[1]
        assert v[int(round(t / dt)), 0] == pytest.approx(1.0 - e, abs=0.005)
    assert (v[10, 0] - v[0, 0]) / (10 * dt) == pytest.approx(P / (1 + D), rel=0.05)


def test_pid_anti_windup_at_the_acceleration_limit():
    """A 2 m/s step with a 0.5 m/s^2 limit saturates for about 4 s. PX4's tracking anti-windup keeps the
    integrator from charging, so the overshoot stays small. The model must match a 1-D transcription of
    PositionControl.cpp (v1.14.0, lines 140-201), and that same transcription WITHOUT anti-windup overshoots
    several times more (so the test fails if the anti-windup is lost or has the wrong sign)."""
    P, I, D, amax, tau, dt, n = 1.8, 0.4, 0.2, 0.5, 0.05, 0.01, 1500

    def reference(arw: bool):
        v = a = integ = 0.0
        out = [v]
        alpha = 1.0 - math.exp(-dt / tau)
        for _ in range(n - 1):
            e = 2.0 - v
            raw = P * e + integ - D * a
            sat = max(-amax, min(amax, raw))
            a += alpha * (sat - a)
            e_int = e - (2.0 / P) * (raw - sat) if (arw and abs(raw) > abs(sat)) else e
            integ += I * e_int * dt
            v += a * dt
            out.append(v)
        return np.array(out)

    p = m.TrajectoryParams(family="pid", kp_xy=0.0, tau_s=tau, delay_s=0.0, acc_max_mps2=amax,
                           vel_p=P, vel_i=I, vel_d=D)
    v, _ = m.simulate(np.zeros((n, 2)), np.tile([2.0, 0.0], (n, 1)), np.zeros((n, 2)), dt, p,
                      p0=np.zeros(2), v0=np.zeros(2))
    ref = reference(True)
    np.testing.assert_allclose(v[:, 0], ref, atol=1e-9)
    over_arw = ref.max() - 2.0
    over_none = reference(False).max() - 2.0
    assert over_arw < 0.05
    assert over_none > 3.0 * max(over_arw, 0.01)


def test_pid_position_gain_pulls_toward_the_setpoint():
    """pid family, no feed-forward, setpoint 1 m east: the drone moves east and settles on it."""
    n = 1200
    p = m.TrajectoryParams(family="pid", kp_xy=0.95, tau_s=0.05, delay_s=0.0, acc_max_mps2=math.inf)
    v, pos = m.simulate(np.tile([1.0, 0.0], (n, 1)), np.zeros((n, 2)), np.zeros((n, 2)), DT, p,
                        p0=np.zeros(2), v0=np.zeros(2))
    assert v[20, 0] > 0.0
    assert pos[-1, 0] == pytest.approx(1.0, abs=0.02)
    assert abs(pos[-1, 1]) < 1e-9


def test_flight_logs_live_inside_svg_training():
    """Owner, 17 Nov 2026: everything the pipeline reads lives inside the repository folder."""
    mod = _load_script()
    assert mod.FLIGHT_LOGS == ROOT / "data" / "flight_logs"
    assert all(p.is_relative_to(ROOT) for p in (mod.MAIN_LOG, *mod.CROSS_LOGS))
