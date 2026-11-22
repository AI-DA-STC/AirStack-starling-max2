#!/usr/bin/env python3
"""STE L1.3: fit EKF2's estimate-error statistics (sigma, tau per quantity) from real PX4 logs with mocap fused.

Usage (from svg_training/):
    fit_estimate_error.py [--logs <ulg> ...] [--main <ulg>] [--out-dir runs/2026-11-23_ste_l13_fit] [--no-figures]

Exploratory, not a run of record: no gate, no ledger row, no change to any file under params/. It writes a PROPOSED
block for params/starling_physics_v1.toml into the out-dir; the lead decides whether it goes in.

What it fits. models/estimator_effect.py gives the cascade the true state plus a first-order Gauss-Markov error per
quantity (position, velocity, attitude as a small body rotation): stationary standard deviation sigma, correlation time
tau. On the drone the cascade flies on EKF2's output (vehicle_local_position, vehicle_attitude); EKF2 fuses the mocap
(vehicle_visual_odometry). The nearest thing to the truth in the log is that mocap, so the error is
estimate - mocap, per axis:
  - position: EKF2 position minus the mocap position interpolated to EKF2's sample time;
  - velocity: EKF2 velocity minus a velocity DERIVED from the mocap position (a local quadratic over +-3 mocap samples,
    about +-0.1 s: the mocap message carries no velocity, the fields are NaN);
  - attitude: the body rotation from the mocap attitude to EKF2's, rot = 2 vec(q_mocap^-1 (x) q_est) (the model's own
    convention, q_est = q (x) dq), its constant part reported as a bias (rigid-body alignment) and removed.
Axes: position and velocity in ENU (x east, y north, z up), as the trainer; attitude in body axes (roll, pitch, yaw).

How sigma and tau are fitted (fit_gm). The error is resampled onto a uniform grid inside contiguous segments; the
autocorrelation rho(k) is pooled over segments (never across a gap). The measured error is the correlated EKF2 error
plus white noise (mocap noise, interpolation), so rho(k) = A exp(-k dt / tau) for k >= 1 is fitted (least squares on
log rho over the lags where rho stays above RHO_FLOOR); sigma_gm = sqrt(A) std is the correlated part, sqrt(1 - A) std
the white remainder. If rho falls below RHO_FLOOR within two lags, tau is UNRESOLVED (at or below the sample interval:
10 Hz position and velocity, 20 Hz attitude in these logs) and no sigma_gm is given. If the free intercept comes out
above 1 (smoother than first order), A is held at 1 (no white part) and tau refitted through the origin. Effective
sample count about duration / (2 tau).

Tau rule for the proposal (fix round 1, settled AFTER seeing the real logs; one rule for every quantity): the 1/e
crossing of rho (log-interpolated), with the A = 1 through-origin fit beside it as a cross-check, both reported. The free
log-domain fit down to RHO_FLOOR overweights the tail when the error has two time scales (attitude). A white part makes
the 1/e crossing a little short. INFO: a damped second-order autocorrelation is also fitted to 6 s (fit_second_order);
the logged position and velocity errors swing back, which a first-order error never does.

Scope: L1.3's estimate-error statistics only. Drag and the stage-1 limits remain; WORK_BREAKDOWN's
scripts/fit_physics_delay.py is replaced by this script for the error part.

Which samples (fixed before the first fit; exploratory scans of log103 had been run: error spread, hover
fraction at 0.1 m/s, time shifts). Airborne: not landed and more than 0.3 m up, 1 s trimmed off
each end of every airborne span. Hover: airborne, EKF2 horizontal speed under 0.1 m/s and vertical under 0.1 m/s, in
runs of at least 3 s. Moving: airborne, horizontal speed above 0.2 m/s. The model's error does not depend on motion, so
the proposal comes from hover only; moving segments are reported apart (at the stamps as logged and at the time shift
that best lines up the positions) because there the error also holds speed x any timing mismatch.

Proposal rule (fixed). From the --main log, hover, pooled over the three axes (the model takes one sigma and one tau per
quantity): sigma = sigma_gm, tau = tau_s. A quantity stays OPEN when its tau is unresolved, or when the reference's own
noise floor (the mocap noise, or for velocity the noise of the derived velocity) is half its sigma_gm or more (then the
fit is an upper bound). Other logs are cross-checks, not pooled.

Mocap timing (the flight panel's question). The log cannot see the mocap's capture time: vehicle_visual_odometry has
timestamp_sample = timestamp, and both equal the time the logger wrote it to within a few ms (write order against
high-rate topics), so the sample is stamped on arrival at PX4. What the log does give: (1) the mocap's age at that
stamp, from the lag that best lines up the mocap roll and pitch with EKF2's (EKF2 does not fuse mocap roll or pitch
with EKF2_EV_CTRL 11; its tilt comes from the gyro and runs at current time through the output predictor), so it is
measured against the IMU; (2) EKF2_EV_DELAY, the age EKF2 assumes; (3) how far behind current time EKF2's fusion
horizon runs (estimator_innovations timestamp - timestamp_sample). A capture stamp from the mocap PC on a synced clock
would measure the age directly.

Outputs in --out-dir: results.json, results.md, proposed_starling_physics_v1.toml, and (unless --no-figures)
estimate_error_acf.png, estimate_error_hover.png. Exit codes: 0 done; 1 unreadable log; 2 bad arguments or no hover.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import struct
import sys
from pathlib import Path

for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("fit_real_px4", ROOT / "scripts" / "fit_real_px4.py")
_frp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_frp)
read_ulog_full = _frp.read_ulog_full                 # the ULog reader (read-only; pyulog is not installed)

FLIGHT_LOGS = Path.home() / "flight_logs" / "2026-11-13"
DEFAULT_LOGS = (FLIGHT_LOGS / "ulog_drone_2/log103.ulg",
                FLIGHT_LOGS / "two_drone_teleop/drone_2/log105.ulg",
                FLIGHT_LOGS / "two_drone_teleop/drone_1_candidates/08_47_58.ulg")
OUT_DIR = ROOT / "runs" / "2026-11-23_ste_l13_fit"
TOPICS = ("vehicle_visual_odometry", "vehicle_local_position", "vehicle_attitude", "vehicle_land_detected",
          "estimator_innovations")
MEAS_TOPIC = "vehicle_visual_odometry"
WRITE_REF_TOPICS = ("sensor_combined", "vehicle_angular_velocity", "esc_status", "estimator_innovations")
EKF2_KEYS = ("EKF2_EV_CTRL", "EKF2_EV_DELAY", "EKF2_HGT_REF", "EKF2_EVP_NOISE", "EKF2_EVA_NOISE", "EKF2_RNG_CTRL",
             "EKF2_BARO_CTRL", "EKF2_GPS_CTRL", "EKF2_MAG_TYPE")
EV_CTRL_BITS = ("horizontal position", "vertical position", "velocity", "yaw")     # PX4 1.14 EKF2_EV_CTRL bits 0..3

# Fixed before the first fit (exploratory scans of log103 had been run first: error spread, hover fraction, shifts).
AIRBORNE_M = 0.3
TRIM_S = 1.0
HOVER_HSPEED, HOVER_VSPEED, HOVER_MIN_S = 0.1, 0.1, 3.0
MOVING_HSPEED, MOVING_MIN_S = 0.2, 0.5
MAX_MEAS_GAP_S = 0.1          # no mocap sample within this of the instant: no error sample there
SLOPE_HALF = 3                # mocap samples each side for the derived velocity and the noise floor
RHO_FLOOR = 0.15
MAX_LAG_S = 6.0               # the autocorrelation is kept to 6 s (the second-order INFO fit uses all of it)
LAG_GRID = np.round(np.arange(-0.100, 0.2001, 0.001), 6)
FLOOR_SHARE = 0.5             # reference noise floor >= this x sigma_gm: the fit is an upper bound, keep OPEN
QUANTITIES = (("pos", "m", ("x", "y", "z")), ("vel", "mps", ("x", "y", "z")), ("att", "rad", ("roll", "pitch", "yaw")))
V1_KEYS = {"pos": ("state_error_pos_m", "state_error_pos_tau_s"),
           "vel": ("state_error_vel_mps", "state_error_vel_tau_s"),
           "att": ("state_error_att_rad", "state_error_att_tau_s")}


# ----------------------------------------------------------------------------------------------- statistics
def segments_of(t, mask, min_len_s, max_gap_s):
    """[(a, b)] index ranges (b exclusive) of runs where mask holds and no time step exceeds max_gap_s, kept when they
    last at least min_len_s."""
    t, mask = np.asarray(t, float), np.asarray(mask, bool)
    out, a = [], None
    for i in range(t.size + 1):
        ok = i < t.size and mask[i] and (a is None or t[i] - t[i - 1] <= max_gap_s)
        if a is not None and not ok:
            if t[i - 1] - t[a] >= min_len_s:
                out.append((a, i))
            a = None
        if a is None and i < t.size and mask[i]:
            a = i
    return out


def resample(t, x, dt):
    """(grid, x on it): a uniform grid of step dt from t[0] to t[-1], x linearly interpolated."""
    t = np.asarray(t, float)
    n = int(math.floor((t[-1] - t[0]) / dt + 1e-9)) + 1
    g = t[0] + dt * np.arange(n)
    return g, np.interp(g, t, np.asarray(x, float))


def _rho(segments, max_lag):
    """Pooled autocovariance of zero-mean segments: (c[0..max_lag], pairs per lag)."""
    c, npair = np.zeros(max_lag + 1), np.zeros(max_lag + 1)
    for s in segments:
        for k in range(min(max_lag, s.size - 1) + 1):
            c[k] += np.dot(s[:s.size - k], s[k:])
            npair[k] += s.size - k
    with np.errstate(invalid="ignore", divide="ignore"):
        return c / np.where(npair > 0, npair, np.nan), npair


def fit_gm(segments, dt, mean=None, max_lag_s=MAX_LAG_S, rho_floor=RHO_FLOOR):
    """First-order Gauss-Markov plus white floor fitted to segments (1-D arrays on a uniform grid of step dt).

    mean: removed from every segment (default: the mean of all their samples). Returns n, n_segments, duration_s,
    mean, std, rho (to max_lag_s), A, A_fit, tau_s, tau_resolved, sigma_gm, sigma_white, tau_efold_s, tau_ar1_s, n_eff,
    fit_lags, tau_origin_s (A = 1, through the origin over the same lags), shape (zero_cross_s, rho_min,
    lag_rho_min_s) and second_order (INFO, fit_second_order)."""
    segs = [np.asarray(s, float) for s in segments if np.asarray(s).size > 0]
    allx = np.concatenate(segs)
    m = float(allx.mean()) if mean is None else float(mean)
    z = [s - m for s in segs]
    max_lag = max(2, int(round(max_lag_s / dt)))
    c, npair = _rho(z, max_lag)
    var = float(c[0])
    rho = c / var if var > 0 else np.full_like(c, np.nan)
    out = {"n": int(allx.size), "n_segments": len(segs), "duration_s": float(allx.size * dt), "dt_s": float(dt),
           "mean": m, "std": math.sqrt(max(var, 0.0)), "rho": [None if not np.isfinite(r) else float(r)
                                                             for r in rho],
           "A": None, "A_fit": None, "tau_s": None, "tau_resolved": False, "sigma_gm": None, "sigma_white": None,
           "tau_efold_s": None, "tau_ar1_s": None, "n_eff": None, "fit_lags": 0,
           "zero_cross_s": None, "rho_min": None, "lag_rho_min_s": None, "tau_origin_s": None,
           "second_order": None}
    fin = np.isfinite(rho)
    if fin.sum() > 1:                                              # shape: a first-order process never goes negative
        k_min = int(np.nanargmin(np.where(fin, rho, np.inf)))
        out.update(rho_min=float(rho[k_min]), lag_rho_min_s=float(k_min * dt))
        neg = np.nonzero(fin & (rho < 0))[0]
        if neg.size:
            out["zero_cross_s"] = float(neg[0] * dt)
    r1 = rho[1] if rho.size > 1 else np.nan
    if np.isfinite(r1) and 0 < r1 < 1:
        out["tau_ar1_s"] = float(-dt / math.log(r1))
    for k in range(1, rho.size):                                   # 1/e crossing, log-interpolated
        if not np.isfinite(rho[k]):
            break
        if rho[k] < 1 / math.e:
            r0 = rho[k - 1]
            frac = ((math.log(r0) + 1) / (math.log(r0) - math.log(rho[k])) if rho[k] > 0
                    else (r0 - 1 / math.e) / (r0 - rho[k]))
            out["tau_efold_s"] = float(dt * (k - 1 + frac))
            break
    L = 0
    while L + 1 < rho.size and np.isfinite(rho[L + 1]) and rho[L + 1] > rho_floor:
        L += 1
    out["fit_lags"] = L
    if L >= 2:
        k = np.arange(1, L + 1)
        slope, icpt = np.polyfit(k * dt, np.log(rho[1:L + 1]), 1)
        lag = k * dt
        to = -np.dot(lag, lag) / np.dot(lag, np.log(rho[1:L + 1]))
        out["tau_origin_s"] = float(to) if to > 0 else None
        if slope < 0:
            out["A_fit"] = float(math.exp(icpt))
            if out["A_fit"] <= 1.0:
                A, tau = out["A_fit"], float(-1.0 / slope)
                white = math.sqrt(1 - A) * out["std"]
            else:   # smoother than first order at short lags: no white part to separate; A held at 1, tau refitted
                A, white = 1.0, None  # through the origin. Added after the first look at the real logs.
                tau = out["tau_origin_s"]
            out.update(A=A, tau_s=tau, tau_resolved=True, sigma_gm=math.sqrt(A) * out["std"], sigma_white=white)
            t_n = out["tau_efold_s"] or tau
            out["n_eff"] = float(allx.size * dt / (2 * t_n))
    if out["tau_efold_s"] is not None:
        out["second_order"] = fit_second_order(rho, dt, out["tau_efold_s"])
    return out


def rho_second_order(t, zeta, wn):
    """Autocorrelation of x'' + 2 zeta wn x' + wn^2 x = white noise (any damping)."""
    t = np.asarray(t, float)
    s = zeta * wn
    if zeta < 1.0 - 1e-6:                                          # under-damped: swings back
        wd = wn * math.sqrt(1.0 - zeta * zeta)
        return np.exp(-s * t) * (np.cos(wd * t) + s / wd * np.sin(wd * t))
    if zeta > 1.0 + 1e-6:                                          # over-damped: two decaying exponentials
        a = wn * math.sqrt(zeta * zeta - 1.0)
        return 0.5 * ((1 + s / a) * np.exp((a - s) * t) + (1 - s / a) * np.exp(-(a + s) * t))
    return np.exp(-wn * t) * (1 + wn * t)


def fit_second_order(rho, dt, tau_first):
    """INFO: least-squares fit of rho_second_order to rho over lags 1..end (A = 1), against the first-order
    exp(-t / tau_first): zeta, wn_rad_s, sse of each, their ratio, and rho at one lag (observed, first, second order)."""
    from scipy.optimize import least_squares
    rho = np.asarray(rho, float)
    k = np.nonzero(np.isfinite(rho))[0]
    k = k[k >= 1]
    if k.size < 4:
        return None
    t, y = k * dt, rho[k]
    t_min = t[int(np.argmin(y))]
    best = None
    for z0 in (0.2, 0.5, 0.9, 1.5):
        for w0 in (math.pi / max(t_min, 2 * dt), 1.0 / tau_first):
            r = least_squares(lambda p: rho_second_order(t, p[0], p[1]) - y, x0=[z0, w0],
                              bounds=([0.01, 0.01], [5.0, 50.0]))
            if best is None or r.cost < best.cost:
                best = r
    zeta, wn = (float(v) for v in best.x)
    sse2 = float(np.sum((rho_second_order(t, zeta, wn) - y) ** 2))
    sse1 = float(np.sum((np.exp(-t / tau_first) - y) ** 2))
    return {"zeta": zeta, "wn_rad_s": wn, "lags_to_s": float(t[-1]), "sse_second": sse2, "sse_first": sse1,
            "sse_ratio_first_over_second": sse1 / sse2 if sse2 > 0 else None,
            "rho_one_lag": {"lag_s": float(dt), "observed": float(rho[1]), "first_order": math.exp(-dt / tau_first),
                            "second_order": float(rho_second_order(np.array([dt]), zeta, wn)[0])}}


def fit_pooled(groups, dt, **kw):
    """One fit over several groups (axes, drones): each group's own mean is removed, then all segments are pooled."""
    segs = []
    for g in groups:
        g = [np.asarray(s, float) for s in g if np.asarray(s).size > 0]
        if not g:
            continue
        m = np.concatenate(g).mean()
        segs += [s - m for s in g]
    return fit_gm(segs, dt, mean=0.0, **kw)


def fit_axes(series, dt, **kw):
    """Pooled fit over whole series (one per axis or per drone), each with its own mean removed."""
    return fit_pooled([[s] for s in series], dt, **kw)


# ----------------------------------------------------------------------------------------------- geometry
def quat_mul(a, b):
    """Hamilton product of WXYZ quaternions, (N, 4)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    w1, x1, y1, z1 = np.moveaxis(a, -1, 0)
    w2, x2, y2, z2 = np.moveaxis(b, -1, 0)
    return np.stack([w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2], -1)


def small_angle(q_ref, q_est):
    """Body rotation from q_ref to q_est, (N, 3) rad: 2 vec(q_ref^-1 (x) q_est), sign fixed (w >= 0)."""
    q_ref = np.asarray(q_ref, float)
    conj = q_ref * np.array([1.0, -1.0, -1.0, -1.0])
    dq = quat_mul(conj, q_est)
    dq = dq * np.where(dq[..., :1] < 0, -1.0, 1.0)
    return 2.0 * dq[..., 1:]


def _continuous(q):
    q = np.array(q, float)
    for i in range(1, len(q)):
        if np.dot(q[i], q[i - 1]) < 0:
            q[i] = -q[i]
    return q


def interp_quat(t_src, q_src, t):
    """Quaternions at t: component-wise linear interpolation after a sign-continuity pass, normalised."""
    q = _continuous(q_src)
    out = np.stack([np.interp(t, t_src, q[:, i]) for i in range(4)], -1)
    return out / np.linalg.norm(out, axis=-1, keepdims=True)


def _local_quadratic(t, x, half):
    """Per centre sample i (half <= i < n - half): coefficients (c0, c1, c2) of x ~ c0 + c1 s + c2 s^2, s = t - t[i],
    over samples i - half .. i + half; and the centre's leverage. NaN at the edges."""
    t, x = np.asarray(t, float), np.asarray(x, float)
    n = t.size
    coef, lev = np.full((n, 3), np.nan), np.full(n, np.nan)
    if n < 2 * half + 1:
        return coef, lev
    idx = np.arange(n - 2 * half)[:, None] + np.arange(2 * half + 1)[None]
    s = t[idx] - t[idx[:, half]][:, None]
    V = np.stack([np.ones_like(s), s, s * s], -1)                        # (m, w, 3)
    VtV = np.einsum("mwi,mwj->mij", V, V)
    inv = np.linalg.inv(VtV)
    c = np.einsum("mij,mwj,mw->mi", inv, V, x[idx])
    coef[half:n - half] = c
    lev[half:n - half] = inv[:, 0, 0]                                     # the centre's row is (1, 0, 0)
    return coef, lev


def local_slope(t, x, half=SLOPE_HALF):
    """dx/dt at each sample from a local quadratic over +-half samples (exact for a quadratic, any stamps)."""
    return _local_quadratic(t, x, half)[0][:, 1]


def noise_floor(t, x, mask, half=SLOPE_HALF):
    """White-noise standard deviation of x: residual of each centre sample from a local quadratic over +-half samples,
    corrected for the fit's leverage, over windows lying wholly inside mask."""
    coef, lev = _local_quadratic(t, x, half)
    mask = np.asarray(mask, bool)
    full = np.zeros(mask.size, bool)
    if mask.size >= 2 * half + 1:
        win = np.lib.stride_tricks.sliding_window_view(mask, 2 * half + 1).all(-1)
        full[half:mask.size - half] = win
    r = np.asarray(x, float) - coef[:, 0]
    ok = full & np.isfinite(r)
    if ok.sum() < 10:
        return None
    return float(math.sqrt(np.mean(r[ok] ** 2 / (1 - lev[ok]))))


def _interp_guarded(t_src, x_src, t):
    """Linear interpolation of x_src (N, k) at t; NaN where no source sample lies within MAX_MEAS_GAP_S on both sides."""
    t_src = np.asarray(t_src, float)
    j = np.searchsorted(t_src, t)
    lo, hi = np.clip(j - 1, 0, t_src.size - 1), np.clip(j, 0, t_src.size - 1)
    bad = (j <= 0) | (j >= t_src.size) | (t - t_src[lo] > MAX_MEAS_GAP_S) | (t_src[hi] - t > MAX_MEAS_GAP_S)
    x_src = np.asarray(x_src, float).reshape(t_src.size, -1)
    out = np.stack([np.interp(t, t_src, x_src[:, i]) for i in range(x_src.shape[1])], -1)
    out[bad] = np.nan
    return out


def best_lag(t_eval, est, t_meas, meas, lags=LAG_GRID):
    """(lag, [(lag, rms)]): the shift that minimises the spread (mean removed, summed over columns) of
    est(t) - meas(t + lag); parabolic refinement between grid points. A positive lag = the measurement describes the
    instant `lag` seconds before its stamp."""
    est = np.asarray(est, float).reshape(len(t_eval), -1)
    curve = []
    for lag in lags:
        d = est - _interp_guarded(t_meas, meas, np.asarray(t_eval) + lag)
        d = d[np.isfinite(d).all(-1)]
        curve.append(float(np.sqrt(((d - d.mean(0)) ** 2).sum(-1).mean())) if len(d) > 10 else np.inf)
    c = np.array(curve)
    i = int(np.argmin(c))
    lag = float(lags[i])
    if 0 < i < len(c) - 1 and np.all(np.isfinite(c[i - 1:i + 2])):
        den = c[i - 1] - 2 * c[i] + c[i + 1]
        if den > 0:
            lag += 0.5 * (c[i - 1] - c[i + 1]) / den * float(lags[1] - lags[0])
    return lag, list(zip([float(x) for x in lags], curve))


def tilt_lag(t_att, q_est, t_m, q_m, lags=LAG_GRID):
    """The mocap's age at its stamp, against EKF2's gyro-driven tilt: the lag minimising the spread of the roll and
    pitch parts of the rotation from mocap(t + lag) to estimate(t)."""
    curve = []
    for lag in lags:
        qm = interp_quat(t_m, q_m, t_att + lag)
        rot = small_angle(qm, q_est)[:, :2]
        ok = (t_att + lag > t_m[0]) & (t_att + lag < t_m[-1]) & np.isfinite(rot).all(-1)
        d = rot[ok]
        curve.append(float(np.sqrt(((d - d.mean(0)) ** 2).sum(-1).mean())) if len(d) > 10 else np.inf)
    c = np.array(curve)
    i = int(np.argmin(c))
    lag = float(lags[i])
    if 0 < i < len(c) - 1:
        den = c[i - 1] - 2 * c[i] + c[i + 1]
        if den > 0:
            lag += 0.5 * (c[i - 1] - c[i + 1]) / den * float(lags[1] - lags[0])
    return lag, list(zip([float(x) for x in lags], curve))


# ----------------------------------------------------------------------------------------------- the log
def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stamp_vs_write(path):
    """Write time of each mocap message (the largest timestamp among high-rate topics written before it in the file)
    minus its timestamp_sample, in ms: percentiles 5, 50, 95. About 0 = stamped on arrival at PX4."""
    buf = Path(path).read_bytes()
    pos, subs, runmax, out = 16, {}, 0, []
    names = set()
    while pos + 3 <= len(buf):
        size, kind = struct.unpack_from("<HB", buf, pos)
        body = pos + 3
        if body + size > len(buf):
            break
        if kind == 0x41:
            multi, mid = struct.unpack_from("<BH", buf, body)
            subs[mid] = (buf[body + 3:body + size].decode("ascii", "replace"), multi)
            names.add(subs[mid][0])
        pos = body + size
    ref = set(WRITE_REF_TOPICS) & names or names - {MEAS_TOPIC}
    pos = 16
    while pos + 3 <= len(buf):
        size, kind = struct.unpack_from("<HB", buf, pos)
        body = pos + 3
        if body + size > len(buf):
            break
        if kind == 0x44:
            mid = struct.unpack_from("<H", buf, body)[0]
            name, multi = subs.get(mid, ("", 1))
            if multi == 0 and name in ref:
                runmax = max(runmax, struct.unpack_from("<Q", buf, body + 2)[0])
            elif multi == 0 and name == MEAS_TOPIC and runmax > 0:
                out.append(runmax - struct.unpack_from("<Q", buf, body + 10)[0])
        pos = body + size
    if not out:
        return None
    p = np.percentile(np.array(out, float) / 1e3, [5, 50, 95])
    return {"p5": float(p[0]), "median": float(p[1]), "p95": float(p[2]), "n": len(out), "reference": sorted(ref)}


def _enu(x, y, z):
    return np.stack([np.asarray(y, float), np.asarray(x, float), -np.asarray(z, float)], -1)


def _intervals(t, segs):
    return [(float(t[a]), float(t[b - 1])) for a, b in segs]


def _inside(t, intervals):
    m = np.zeros(np.asarray(t).size, bool)
    for a, b in intervals:
        m |= (t >= a) & (t <= b)
    return m


def _per_interval(t, x, intervals, dt):
    """{axis: [segment on a uniform grid]} of x (N, 3) over each interval (NaN samples split the interval)."""
    out = [[] for _ in range(x.shape[1])]
    for a, b in intervals:
        sel = (t >= a) & (t <= b) & np.isfinite(x).all(-1)
        for c, d in segments_of(t[sel] if sel.any() else np.array([]), np.ones(sel.sum(), bool), 1.0, 2.5 * dt):
            tt = t[sel][c:d]
            for k in range(x.shape[1]):
                out[k].append(resample(tt, x[sel][c:d, k], dt)[1])
    return out


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not math.isfinite(float(o)) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def _fit_class(t, x, intervals, dt, names):
    """Per-axis and pooled fits of x (N, 3) over the intervals, plus a split-half check of the pooled fit."""
    per = _per_interval(t, x, intervals, dt)
    if not any(per):
        return None
    res = {"axes": {n: fit_gm(per[k], dt) for k, n in enumerate(names) if per[k]},
           "pooled": fit_pooled(per, dt)}
    dur = np.cumsum([b - a for a, b in intervals])                # split where half the hover time is reached
    i = int(np.searchsorted(dur, dur[-1] / 2))
    mid = intervals[i][1] - (dur[i] - dur[-1] / 2)
    halves = {}
    for h, cut in (("first", lambda a, b: (a, min(b, mid))), ("second", lambda a, b: (max(a, mid), b))):
        iv = [c for c in (cut(a, b) for a, b in intervals) if c[1] - c[0] >= HOVER_MIN_S]
        p = _per_interval(t, x, iv, dt)
        halves[h] = {k: v for k, v in fit_pooled(p, dt).items() if k in ("n", "std", "sigma_gm", "tau_s",
                                                                                   "tau_efold_s", "tau_origin_s")} \
            if iv and any(p) else None
    res["split_half"] = halves
    return res


def _spread(x, names):
    ok = np.isfinite(x).all(-1)
    return {"n": int(ok.sum()), **{n: {"mean": float(x[ok, k].mean()), "std": float(x[ok, k].std())}
                                   for k, n in enumerate(names)}} if ok.sum() > 10 else None


def analyse_log(path):
    path = Path(path)
    data, params, _ = read_ulog_full(path, TOPICS)
    for need in ("vehicle_local_position", "vehicle_attitude", MEAS_TOPIC):
        if need not in data:
            raise ValueError(f"{path}: topic {need} is not in the log")
    vo, lp, at = data[MEAS_TOPIC], data["vehicle_local_position"], data["vehicle_attitude"]
    t0 = lp["timestamp_sample"][0]
    sec = lambda a: (np.asarray(a, float) - t0) / 1e6                                       # noqa: E731
    t_m = sec(vo["timestamp_sample"])
    p_m = _enu(vo["position[0]"], vo["position[1]"], vo["position[2]"])
    q_m = np.stack([vo[f"q[{i}]"] for i in range(4)], -1)
    okm = np.isfinite(p_m).all(-1) & np.isfinite(q_m).all(-1)
    order = np.argsort(t_m[okm], kind="stable")
    t_m, p_m, q_m = t_m[okm][order], p_m[okm][order], q_m[okm][order]
    keep = np.r_[True, np.diff(t_m) > 0]
    t_m, p_m, q_m = t_m[keep], p_m[keep], q_m[keep]
    meas_vel_logged = bool("velocity[0]" in vo and np.isfinite(vo["velocity[0]"]).any())

    t_l = sec(lp["timestamp_sample"])
    p_l = _enu(lp["x"], lp["y"], lp["z"])
    v_l = _enu(lp["vx"], lp["vy"], lp["vz"])
    t_a = sec(at["timestamp_sample"])
    q_a = np.stack([at[f"q[{i}]"] for i in range(4)], -1)
    dt_l = round(float(np.median(np.diff(t_l))), 3)
    dt_a = round(float(np.median(np.diff(t_a))), 3)

    # airborne / hover / moving, on EKF2's samples
    if "vehicle_land_detected" in data:
        ld = data["vehicle_land_detected"]
        t_ld = sec(ld["timestamp"])
        j = np.clip(np.searchsorted(t_ld, t_l, side="right") - 1, 0, t_ld.size - 1)
        landed = ld["landed"][j] > 0.5
    else:
        landed = np.zeros(t_l.size, bool)
    up = (~landed) & (p_l[:, 2] > AIRBORNE_M)
    air_iv = [(a + TRIM_S, b - TRIM_S) for a, b in _intervals(t_l, segments_of(t_l, up, 2 * TRIM_S + 0.5, 0.5))]
    air = _inside(t_l, air_iv)
    hs, vs = np.hypot(v_l[:, 0], v_l[:, 1]), np.abs(v_l[:, 2])
    hover_iv = _intervals(t_l, segments_of(t_l, air & (hs < HOVER_HSPEED) & (vs < HOVER_VSPEED), HOVER_MIN_S,
                                           2.5 * dt_l))
    move_iv = _intervals(t_l, segments_of(t_l, air & (hs > MOVING_HSPEED), MOVING_MIN_S, 2.5 * dt_l))

    # errors
    e_pos = p_l - _interp_guarded(t_m, p_m, t_l)
    v_m = np.stack([local_slope(t_m, p_m[:, k]) for k in range(3)], -1)
    okv = np.isfinite(v_m).all(-1)
    e_vel = v_l - _interp_guarded(t_m[okv], v_m[okv], t_l)
    qm_a = interp_quat(t_m, q_m, t_a)
    rot = small_angle(qm_a, q_a)
    rot[np.isnan(_interp_guarded(t_m, p_m[:, :1], t_a)).any(-1)] = np.nan
    hov_a = _inside(t_a, hover_iv)
    att_bias = np.nanmean(rot[hov_a], 0) if hov_a.any() else np.nanmean(rot[_inside(t_a, air_iv)], 0)
    e_att = rot - att_bias

    names = {q: n for q, _, n in QUANTITIES}
    hover = {"pos": _fit_class(t_l, e_pos, hover_iv, dt_l, names["pos"]),
             "vel": _fit_class(t_l, e_vel, hover_iv, dt_l, names["vel"]),
             "att": _fit_class(t_a, e_att, hover_iv, dt_a, names["att"])}
    hover_s = float(sum(b - a for a, b in hover_iv))

    # the mocap's own noise (white), during hover; and still on the ground before take-off
    hov_m = _inside(t_m, hover_iv)
    pos_floor = {n: noise_floor(t_m, p_m[:, k], hov_m) for k, n in enumerate(names["pos"])}
    rot_m = small_angle(np.tile(q_m[hov_m][0] if hov_m.any() else q_m[0], (t_m.size, 1)), q_m)
    att_floor = {n: noise_floor(t_m, rot_m[:, k], hov_m) for k, n in enumerate(names["att"])}
    rms = lambda d: (float(math.sqrt(np.mean([v ** 2 for v in d.values()])))                   # noqa: E731
                     if all(v is not None for v in d.values()) else None)
    rng = np.random.default_rng(0)
    white = rng.standard_normal(t_m.size)
    gain = local_slope(t_m, white)
    vel_gain = float(np.sqrt(np.nanmean(gain[hov_m] ** 2))) if hov_m.any() else None
    pos_noise = rms(pos_floor)
    ground = np.zeros(t_m.size, bool)
    if landed.size and landed[0]:
        lift = t_l[np.argmax(~landed)] if (~landed).any() else t_l[-1]       # first not-landed sample
        ground = t_m < lift - 1.0
    still = None
    if ground.sum() > 30:
        still = {n: float(np.std(p_m[ground, k] - np.polyval(np.polyfit(t_m[ground], p_m[ground, k], 1),
                                                                     t_m[ground])))
                 for k, n in enumerate(names["pos"])}
    mocap = {"rate_hz": float(1 / np.median(np.diff(t_m))), "n": int(t_m.size), "velocity_logged": meas_vel_logged,
             "pos_noise_m": pos_noise, "pos_noise_axes_m": pos_floor,
             "att_noise_rad": rms(att_floor), "att_noise_axes_rad": att_floor,
             "derived_vel_noise_mps": (pos_noise * vel_gain) if (pos_noise is not None and vel_gain) else None,
             "still_on_ground_pos_std_m": still, "att_bias_rad": {n: float(att_bias[k])
                                                                  for k, n in enumerate(names["att"])}}

    # moving: spread at the stamps as logged and at the best position shift
    mov_l = _inside(t_l, move_iv) & np.isfinite(e_pos).all(-1)
    moving = None
    if mov_l.sum() > 20:
        shift, _ = best_lag(t_l[mov_l], p_l[mov_l], t_m, p_m)
        e_shift = p_l - _interp_guarded(t_m, p_m, t_l + shift)
        mov_a = _inside(t_a, move_iv)
        moving = {"duration_s": float(sum(b - a for a, b in move_iv)), "n_segments": len(move_iv),
                  "pos": _spread(e_pos[mov_l], names["pos"]), "pos_best_shift_s": shift,
                  "pos_at_best_shift": _spread(e_shift[mov_l], names["pos"]),
                  "vel": _spread(e_vel[mov_l], names["vel"]),
                  "att": _spread(e_att[mov_a], names["att"])}

    # timing
    air_a = _inside(t_a, air_iv)
    lag, curve = tilt_lag(t_a[air_a], q_a[air_a], t_m, q_m) if air_a.sum() > 50 else (None, [])
    innov = data.get("estimator_innovations")
    horizon = (float(np.median(innov["timestamp"] - innov["timestamp_sample"]) / 1e3)
               if innov is not None and "timestamp_sample" in innov else None)
    innov_change, ekf_dt = None, None
    if innov is not None and "ev_hpos[0]" in innov:
        ev = np.stack([innov["ev_hpos[0]"], innov["ev_hpos[1]"], innov["ev_vpos"]], -1)
        innov_change = float(np.mean(np.any(np.diff(ev, axis=0) != 0, axis=1)))
        ekf_dt = float(np.median(np.diff(innov["timestamp"])) / 1e3)
    ev_ctrl = params.get("EKF2_EV_CTRL")
    ekf2 = {k: params.get(k) for k in EKF2_KEYS}
    ekf2["ev_fuses"] = [b for i, b in enumerate(EV_CTRL_BITS) if ev_ctrl is not None and int(ev_ctrl) >> i & 1]
    sw = stamp_vs_write(path)
    latency = {"tilt_lag_s": lag, "tilt_lag_curve": [(a, b) for a, b in curve[::10]],
               "ekf2_ev_delay_s": None if params.get("EKF2_EV_DELAY") is None else params["EKF2_EV_DELAY"] / 1e3,
               "fusion_horizon_behind_now_ms": horizon, "innov_ev_change_fraction": innov_change,
               "ekf_update_ms": ekf_dt,
               "stamp_minus_write_ms": sw,
               "stamp_equals_timestamp_ms": float(np.median(vo["timestamp"] - vo["timestamp_sample"]) / 1e3)}
    return {"path": str(path), "name": path.name, "sha256": sha256(path), "duration_s": float(t_l[-1]),
            "topics": {"estimate_position": "vehicle_local_position", "estimate_attitude": "vehicle_attitude",
                       "measurement": MEAS_TOPIC, "landed": "vehicle_land_detected",
                       "innovations": "estimator_innovations" if innov is not None else None},
            "ekf2": ekf2, "sample_dt_s": {"pos_vel": dt_l, "att": dt_a},
            "airborne_s": float(sum(b - a for a, b in air_iv)), "hover_s": hover_s, "hover_segments": len(hover_iv),
            "hover": hover, "moving": moving, "mocap": mocap, "latency": latency,
            "_series": {"t_l": t_l, "e_pos": e_pos, "e_vel": e_vel, "t_a": t_a, "e_att": e_att,
                        "hover_iv": hover_iv, "move_iv": move_iv}}


# ----------------------------------------------------------------------------------------------- proposal and report
def _sig(x, n=2):
    return float(f"{x:.{n}g}")


def proposal(res):
    """{quantity: dict(value, tau, status, why)} from one log's hover fits (the rule in the module docstring)."""
    floors = {"pos": res["mocap"]["pos_noise_m"], "vel": res["mocap"]["derived_vel_noise_mps"],
              "att": res["mocap"]["att_noise_rad"]}
    out = {}
    for q, _, _ in QUANTITIES:
        f = (res["hover"].get(q) or {}).get("pooled")
        if f is None or not f["tau_resolved"] or f["tau_efold_s"] is None:
            out[q] = {"status": "OPEN", "why": "tau unresolved (at or below the sample interval)" if f else "no hover"}
            continue
        floor = floors[q]
        # tau rule (fix round 1, settled AFTER seeing the real logs; one rule for every quantity): the 1/e crossing of
        # the autocorrelation; the A = 1 through-origin fit is reported beside it as a cross-check.
        entry = {"sigma": _sig(f["sigma_gm"]), "tau_s": _sig(f["tau_efold_s"]),
                 "tau_origin_s": None if f["tau_origin_s"] is None else _sig(f["tau_origin_s"]),
                 "tau_free_fit_s": f["tau_s"], "floor": floor, "n": f["n"], "n_eff": f["n_eff"]}
        if floor is not None and floor >= FLOOR_SHARE * f["sigma_gm"]:
            entry.update(status="OPEN", why=f"reference noise floor {floor:.3g} is >= {FLOOR_SHARE} x sigma_gm "
                                            f"{f['sigma_gm']:.3g}: an upper bound only")
        else:
            entry.update(status="PROPOSED", why="hover, pooled over three axes")
        # flags (added after the first look at the real logs; they never change the status, they qualify it)
        notes = []
        sh = (res["hover"][q] or {}).get("split_half") or {}
        taus = [h["tau_efold_s"] for h in sh.values() if h and h.get("tau_efold_s")]
        if len(taus) == 2 and max(taus) > 2 * min(taus):
            notes.append(f"tau weakly determined (split-half {taus[0]:.2g} / {taus[1]:.2g} s)")
        if f["rho_min"] is not None and f["rho_min"] < -0.2:
            notes.append(f"error oscillates: autocorrelation {f['rho_min']:.2f} at {f['lag_rho_min_s']:.1f} s "
                         "(a first-order process never goes below 0)")
        if f["A_fit"] is not None and f["A_fit"] > 1.0:
            notes.append(f"smoother than first order at short lags (free fit A {f['A_fit']:.2f} > 1)")
        if floor is not None and FLOOR_SHARE * 0.8 <= floor / f["sigma_gm"] < FLOOR_SHARE:
            notes.append(f"reference floor {floor:.2g} is {floor / f['sigma_gm']:.2f} x sigma (the OPEN cut is "
                         f"{FLOOR_SHARE}): close to the cut")
        if q == "att":
            notes.append("UPPER BOUND: roll and pitch are compared with a mocap tilt EKF2 does not fuse; slow errors "
                         "of that reference (ground-plane level, turning with yaw) land in the correlated part")
        entry["notes"] = notes
        out[q] = entry
    return out


def proposal_toml(res, prop, date="2026-11-23"):
    lines = [f"# PROPOSED values for params/starling_physics_v1.toml [model], STE L1.3 ({date}). EXPLORATORY: one real",
             f"# flight log, {res['name']} (sha256 {res['sha256'][:16]}...), {res['hover_s']:.0f} s of hover in "
             f"{res['hover_segments']} segments;",
             "# error = EKF2 estimate minus the mocap it fuses (the mocap stands in for the truth). Source:",
             "# scripts/fit_estimate_error.py, results.md beside this file. v1 itself is NOT changed: the lead decides.",
             "# A key left OPEN keeps 0 in v1 (reason given)."]
    for q, unit, _ in QUANTITIES:
        k_sig, k_tau = V1_KEYS[q]
        p = prop[q]
        if p["status"] == "PROPOSED":
            lines.append(f"{k_sig} = {p['sigma']!r}".ljust(42) + f"# PROPOSED, EXPLORATORY: {p['why']}; "
                         f"n {p['n']}, about {p['n_eff']:.0f} independent")
            lines.append(f"{k_tau} = {p['tau_s']!r}".ljust(42) + "# PROPOSED, EXPLORATORY: 1/e crossing of the "
                         f"error's autocorrelation (A = 1 fit through the origin: {p['tau_origin_s']} s)"
                         + "".join(f"; {n}" for n in p.get("notes", [])))
        else:
            val = f" (fit gave sigma {p['sigma']}, tau {p['tau_s']} s)" if "sigma" in p else ""
            lines.append(f"{k_sig} = 0.0".ljust(42) + f"# OPEN: {p['why']}{val}")
            lines.append(f"{k_tau} = 0.0".ljust(42) + "# OPEN")
    return "\n".join(lines) + "\n"


def _f(x, d=4):
    return "—" if x is None else f"{x:.{d}f}"


def report_md(results, main_name, prop):
    L = ["# STE L1.3: EKF2 estimate error fitted from real flight logs (EXPLORATORY)", "",
         "Made by `scripts/fit_estimate_error.py` (method in its docstring). Error = EKF2's estimate minus the mocap "
         "it fuses, which stands in for the truth: it holds the mocap's own noise too (white, separated by the fit; "
         "sizes below). Hover only for sigma and tau. Position and velocity in ENU, attitude in body axes.", "",
         "## Proposed values (from " + main_name + ", hover, pooled over axes)", "",
         "| Quantity | sigma | tau (s) | Status | Why |", "|---|---|---|---|---|"]
    for q, unit, _ in QUANTITIES:
        p = prop[q]
        why = "; ".join([p["why"]] + p.get("notes", []))
        L.append(f"| {q} ({unit}) | {p.get('sigma', '—')} | {p.get('tau_s', '—')} | {p['status']} | {why} |")
    L += ["", "## Per log: hover fits", "",
          "sigma_gm = correlated part; white = the rest (— where the error is smoother than first order and none can be "
          "separated); n = samples on the uniform grid; n_eff = duration / (2 tau) (pooled rows count the three axes, "
          "which are not independent of one another). "
          "Split-half = pooled fit on the first and second half of the hover time (stationarity check). "
          "Tau rule (settled after seeing these logs, fix round 1, one rule for every quantity): the 1/e crossing of the "
          "autocorrelation; the A = 1 fit through the origin is the cross-check. With a white part (attitude) the 1/e "
          "crossing comes out a little short.", "",
          "| Log | Quantity | Axis | n | std | sigma_gm | white | tau 1/e (s, the rule) | tau A=1 fit (s) | "
          "tau free fit (s) | AR(1) tau | n_eff | mean |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        for q, unit, names in QUANTITIES:
            h = r["hover"].get(q)
            if not h:
                continue
            for ax, f in list(h["axes"].items()) + [("pooled", h["pooled"])]:
                L.append(f"| {r['name']} | {q} | {ax} | {f['n']} | {_f(f['std'])} | {_f(f['sigma_gm'])} | "
                         f"{_f(f['sigma_white'])} | {_f(f['tau_efold_s'], 2)} | {_f(f['tau_origin_s'], 2)} | "
                         f"{_f(f['tau_s'], 2)} | {_f(f['tau_ar1_s'], 2)} | {_f(f['n_eff'], 0)} | {_f(f['mean'])} |")
            sh = h["split_half"]
            L.append(f"| {r['name']} | {q} | split-half | " + " / ".join(
                "—" if sh[k] is None else f"sigma {_f(sh[k]['sigma_gm'])}, tau 1/e {_f(sh[k]['tau_efold_s'], 2)}"
                for k in ("first", "second")) + " | | | | | | | | | |")
    L += ["", "## Per log: samples, the mocap's own limits, timing", "",
          "| Log | Duration (s) | Airborne (s) | Hover (s, segments) | Mocap rate (Hz) | Mocap pos noise (m) | "
          "Derived vel noise (m/s) | Mocap att noise (rad) | Att bias roll/pitch/yaw (rad) | Tilt lag (s) | "
          "EKF2_EV_DELAY (s) | Fusion horizon behind now (ms) | Stamp vs write, median (ms) | EV fuses |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        m, lt = r["mocap"], r["latency"]
        b = m["att_bias_rad"]
        sw = lt["stamp_minus_write_ms"]
        L.append(f"| {r['name']} | {r['duration_s']:.0f} | {r['airborne_s']:.0f} | {r['hover_s']:.0f}, "
                 f"{r['hover_segments']} | {m['rate_hz']:.1f} | {_f(m['pos_noise_m'], 5)} | "
                 f"{_f(m['derived_vel_noise_mps'], 4)} | {_f(m['att_noise_rad'], 5)} | "
                 f"{_f(b['roll'])} / {_f(b['pitch'])} / {_f(b['yaw'])} | {_f(lt['tilt_lag_s'], 3)} | "
                 f"{_f(lt['ekf2_ev_delay_s'], 3)} | {_f(lt['fusion_horizon_behind_now_ms'], 1)} | "
                 f"{'—' if sw is None else _f(sw['median'], 1)} | {', '.join(r['ekf2']['ev_fuses'])} |")
    L += ["", "## Per log: moving segments (not used for the proposal)", "",
          "| Log | Moving (s, segments) | pos std x/y/z at stamps (m) | best position shift (s) | pos std at shift (m) | "
          "vel std x/y/z (m/s) | att std r/p/y (rad) |", "|---|---|---|---|---|---|---|"]
    for r in results:
        mv = r["moving"]
        if mv is None:
            L.append(f"| {r['name']} | none | | | | | |")
            continue
        s3 = lambda d, ns: " / ".join(_f(d[n]["std"]) for n in ns) if d else "—"           # noqa: E731
        L.append(f"| {r['name']} | {mv['duration_s']:.0f}, {mv['n_segments']} | {s3(mv['pos'], 'xyz')} | "
                 f"{_f(mv['pos_best_shift_s'], 3)} | {s3(mv['pos_at_best_shift'], 'xyz')} | {s3(mv['vel'], 'xyz')} | "
                 f"{s3(mv['att'], ('roll', 'pitch', 'yaw'))} |")
    L += second_order_md(results)
    L += caveats_md(results)
    L += guidance_md(results, prop)
    return "\n".join(L) + "\n"


def second_order_md(results):
    L = ["", "## INFO: a second-order (damped oscillator) error fits better", "",
         "No model change: models/estimator_effect.py stays first order; a second-order error is a follow-up (L1.1c). "
         "Fit of the autocorrelation of x'' + 2 zeta wn x' + wn^2 x = white noise to every lag up to 6 s, hover, "
         "against the first-order exp(-t / tau 1/e). sse ratio = first-order squared misfit / second-order. "
         "rho at one lag: observed / first order / second order (a first-order error is rougher step to step).", "",
         "| Log | Quantity | Axis | sigma (std) | zeta | wn (rad/s) | period 2 pi / wn (s) | sse ratio | "
         "rho at one lag (obs / 1st / 2nd) |", "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        for q, unit, _ in QUANTITIES:
            h = r["hover"].get(q)
            if not h:
                continue
            for ax, f in list(h["axes"].items()) + [("pooled", h["pooled"])]:
                so = f.get("second_order")
                if not so:
                    L.append(f"| {r['name']} | {q} | {ax} | {_f(f['std'])} | — | — | — | — | — |")
                    continue
                o = so["rho_one_lag"]
                if so["zeta"] >= 4.99:                              # the fit ran to the damping bound
                    zs, ws, per = "at bound (no swing-back)", "—", "—"
                else:
                    zs, ws, per = f"{so['zeta']:.2f}", f"{so['wn_rad_s']:.2f}", f"{2 * math.pi / so['wn_rad_s']:.1f}"
                L.append(f"| {r['name']} | {q} | {ax} | {_f(f['std'])} | {zs} | {ws} | {per} | "
                         f"{_f(so['sse_ratio_first_over_second'], 1)} | "
                         f"{o['observed']:.3f} / {o['first_order']:.3f} / {o['second_order']:.3f} at "
                         f"{o['lag_s']:.2f} s |")
    return L


def guidance_md(results, prop):
    r = results[0]
    mv = [x["moving"] for x in results if x["moving"]]
    mv_max = max((d[q]["std"] for x in mv for q in ("x", "y", "z") for d in (x["pos"],) if d), default=None)
    lead = (r["moving"]["pos_best_shift_s"] - r["latency"]["tilt_lag_s"]) if r["moving"] and \
        r["latency"]["tilt_lag_s"] is not None else None
    ages = [x["latency"]["tilt_lag_s"] for x in results if x["latency"]["tilt_lag_s"] is not None]
    cons = {q: (None if prop[q].get("sigma") is None else _sig(2 * prop[q]["sigma"], 2)) for q in prop}
    return ["", "## For the flight panel: how to use these numbers", "",
            f"- **Nominal arm** = the proposal above (position {prop['pos'].get('sigma')} m / "
            f"{prop['pos'].get('tau_s')} s, velocity {prop['vel'].get('sigma')} m/s / {prop['vel'].get('tau_s')} s, "
            f"attitude {prop['att'].get('sigma')} rad / {prop['att'].get('tau_s')} s, an upper bound).",
            f"- **Conservative arm** = about 2 x sigma (2 x sigma = {cons['pos']} m, {cons['vel']} m/s, "
            f"{cons['att']} rad; the panel's figures: position 0.02 m, velocity 0.05 m/s, attitude 0.005 rad), each at "
            "tau 1.3 s and at 0.5 s. One flight log is thin (STANDARDS §5).",
            f"- **Moving is worse than hover.** In moving segments the position error's spread per axis reaches "
            f"{_f(mv_max, 3)} m, and EKF2's position leads the drone by about speed x {_f(lead, 3)} s "
            f"(EKF2_EV_DELAY {_f(r['latency']['ekf2_ev_delay_s'], 3)} s against a measured mocap age of "
            f"{_f(min(ages) if ages else None, 3)}–{_f(max(ages) if ages else None, 3)} s; a hypothesis). Do not "
            "quote a hover number as the in-flight error.",
            "- **The mocap is the reference**, so errors it shares with EKF2 (mocap calibration, the marker centre "
            "against the IMU: EKF2_EV_POS_* are 0) are invisible here.",
            "", "## What the NEAR-962 recording needs to settle these", "",
            "- the mocap capture time on a clock synced with PX4 (so the age at arrival is measured, not inferred);",
            "- ulog at the highest rate for vehicle_local_position, vehicle_attitude, vehicle_visual_odometry and "
            "estimator_innovations (here 10, 20, 34 and 100 Hz);",
            "- an independent reference if possible (a second mocap body or tracker the drone does not fuse);",
            "- hovers of at least 5 min on both drones (here 81 s in 9 pieces);",
            "- moving legs at known speeds (to measure the speed-dependent lead);",
            "- in the record: each log's sha256 and EKF2_EV_DELAY / EKF2_EV_CTRL.",
            "", "## Scope", "",
            "This covers L1.3's estimate-error statistics (state_error_*). Drag and the stage-1 limits (held-out RMS, "
            "t63 error) remain open. WORK_BREAKDOWN names scripts/fit_physics_delay.py; this script replaces it for the "
            "error part."]


def caveats_md(results):
    """Plain-language limits, with the numbers of each log."""
    r = results[0]
    m, lt, h = r["mocap"], r["latency"], r["hover"]
    lags = ", ".join(f"{x['name']} {_f(x['latency']['tilt_lag_s'], 3)} s" for x in results)
    shifts = ", ".join(f"{x['name']} {_f(x['moving']['pos_best_shift_s'], 3)} s ({x['moving']['duration_s']:.0f} s "
                       "moving)" for x in results if x["moving"])
    pos_share = (100 * m["pos_noise_m"] / h["pos"]["pooled"]["std"]) if m["pos_noise_m"] and h.get("pos") else None
    att_white = h["att"]["pooled"]["sigma_white"] if h.get("att") else None
    lead = (r["moving"]["pos_best_shift_s"] - lt["tilt_lag_s"]) if r["moving"] and lt["tilt_lag_s"] is not None \
        else None
    shape = "; ".join(f"{q} {_f(h[q]['pooled']['rho_min'], 2)} at {_f(h[q]['pooled']['lag_rho_min_s'], 1)} s"
                      for q, _, _ in QUANTITIES if h.get(q))
    return ["", "## What the numbers mean, and their limits", "",
            f"- **The mocap stands in for the truth.** Its own white noise, measured as the scatter about a smooth local "
            f"fit during hover, is {_f(m['pos_noise_m'], 5)} m in position and {_f(m['att_noise_rad'], 4)} rad in "
            f"attitude ({r['name']}; logged at {m['rate_hz']:.0f} Hz). Position: {_f(pos_share, 1)} % of the error's "
            "spread, so the position error is EKF2's own, measured against the mocap frame. Attitude: the white part "
            f"the fit separates ({_f(att_white, 4)} rad) is about the size of this floor, so the correlated part is "
            "EKF2's. Errors the mocap shares with EKF2 (calibration, the marker centre against "
            "the IMU: EKF2_EV_POS_* are 0) cannot be seen here.",
            f"- **Attitude.** EKF2 fuses mocap yaw only (EKF2_EV_CTRL 11), so roll and pitch are an independent "
            "comparison. A constant offset (the mocap rigid body against the IMU, "
            f"{_f(m['att_bias_rad']['roll'], 3)} / {_f(m['att_bias_rad']['pitch'], 3)} rad roll / pitch) is removed "
            "as a bias. Any tilt of the mocap's ground plane turns with yaw and is not removed: it adds slow error.",
            f"- **Velocity** is compared with a velocity derived from the mocap position (the message has none); the "
            f"derived velocity's own noise is about {_f(m['derived_vel_noise_mps'], 4)} m/s, small against the error.",
            f"- **Shape.** The model is a first-order Gauss-Markov error, whose autocorrelation decays and never goes "
            f"below 0. The logged errors swing back: autocorrelation minimum {shape}. Position and velocity errors "
            "oscillate over a few seconds in hover, so sigma and tau match the size and the first decay only. "
            "A second-order (damped oscillator) error fits better (INFO table above); a follow-up (L1.1c).",
            f"- **Samples.** {r['hover_s']:.0f} s of hover in {r['hover_segments']} segments in {r['name']}; about "
            f"{_f(h['pos']['pooled']['n_eff'], 0)} independent samples for position, "
            f"{_f(h['att']['pooled']['n_eff'], 0)} for attitude (three axes pooled; about a third per axis). The split-half rows show how much sigma and tau move "
            "within one flight; the other logs (shorter) are cross-checks, not pooled.",
            "- **Position and velocity errors are linked on the drone** (similar tau and the same swing-back), while the "
            "model draws them independently.",
            "- **Hover only.** In moving segments the position error is larger and depends on speed (table above): the "
            "model's error does not, so moving segments are not in the proposal.",
            "", "## Mocap timing (how it was measured)", "",
            "- The log has no capture time from the mocap PC: vehicle_visual_odometry has timestamp_sample = timestamp, "
            "and both match the time the logger wrote the message (median "
            f"{_f(lt['stamp_minus_write_ms']['median'] if lt['stamp_minus_write_ms'] else None, 1)} ms, "
            "against high-rate topics written just before it). So each sample is stamped on arrival at PX4.",
            f"- **Age of a mocap sample at its arrival stamp (indirect, a few ms uncertain): {lags}.** Measured by shifting the mocap roll and pitch "
            "in time until they best match EKF2's (1 ms steps). EKF2's tilt is driven by the gyro at current time (its "
            "output predictor) and EKF2 does not fuse mocap tilt (only slowly through position), so this is the mocap's age against the IMU: capture, Motive, network and bridge together.",
            f"- EKF2 is told the mocap is {_f(lt['ekf2_ev_delay_s'], 3)} s old (EKF2_EV_DELAY); its fusion horizon runs "
            f"{_f(lt['fusion_horizon_behind_now_ms'], 0)} ms behind current time (estimator_innovations timestamp - "
            "timestamp_sample). The measured age is far below the assumed one.",
            "- **Stamp to use is not measured directly.** The mocap innovation (estimator_innovations ev_hpos) changes "
            f"in {_f(None if lt['innov_ev_change_fraction'] is None else 100 * lt['innov_ev_change_fraction'], 0)} % "
            f"of EKF2's updates (every {_f(lt['ekf_update_ms'], 1)} ms), more often than the logged mocap rate, so the "
            "instants a sample is fused cannot be picked out (the logger may keep only some of the mocap messages, or the "
            "innovation is refreshed every update). Inferred from the numbers above (not observed): a sample arriving "
            "at t is labelled t - EKF2_EV_DELAY, already older than the fusion horizon, so EKF2 takes it at its next "
            "update, within about one update interval of arrival, and treats it as about one horizon old.",
            f"- HYPOTHESIS (not reviewed against a flight test): with the assumed age too large, EKF2 places each mocap "
            f"sample too early and its position runs ahead of the drone while it moves. The position shift that best "
            f"lines up estimate and mocap while moving: {shifts}; minus the age above, the estimate leads by about "
            f"{_f(lead, 3)} s in {r['name']} (an error of speed x lead while moving). A capture stamp from the mocap PC on a synced clock would measure "
            "the age directly."]


def figures(results, out_dir):
    plt = _frp._plt()
    colors = _frp.SERIES
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6))
    for ax, (q, unit, _) in zip(axes, QUANTITIES):
        for i, r in enumerate(results):
            f = (r["hover"].get(q) or {}).get("pooled")
            if not f:
                continue
            rho = np.array([np.nan if v is None else v for v in f["rho"]])
            lag = np.arange(rho.size) * f["dt_s"]
            ax.plot(lag, rho, "o", ms=3, color=colors[i], label=r["name"])
            if f["tau_resolved"]:
                ax.plot(lag[1:], f["A"] * np.exp(-lag[1:] / f["tau_s"]), "-", color=colors[i], lw=1.2)
        _frp.style(ax, f"{q}: hover error autocorrelation", "lag (s)", "rho")
        ax.set_xlim(0, 3)
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "estimate_error_acf.png", dpi=130)
    plt.close(fig)
    r = results[0]
    s = r["_series"]
    fig, axes = plt.subplots(3, 1, figsize=(12, 7), sharex=True)
    for ax, (q, unit, names), t, e in zip(axes, QUANTITIES, (s["t_l"], s["t_l"], s["t_a"]),
                                          (s["e_pos"], s["e_vel"], s["e_att"])):
        for a, b in s["hover_iv"]:
            ax.axvspan(a, b, color="#e4e3df", lw=0)
        for k, n in enumerate(names):
            ax.plot(t, e[:, k], lw=0.7, color=colors[k], label=n)
        _frp.style(ax, f"{r['name']}: {q} error, estimate minus mocap (grey = hover)", "", unit)
        ax.legend(frameon=False, fontsize=8, ncol=3)
    axes[-1].set_xlabel("time since log start (s)")
    fig.tight_layout()
    fig.savefig(out_dir / "estimate_error_hover.png", dpi=130)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--logs", nargs="+", type=Path, default=list(DEFAULT_LOGS))
    ap.add_argument("--main", type=Path, default=None, help="the log the proposal comes from (default: the first)")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--no-figures", action="store_true")
    a = ap.parse_args(argv)
    logs = [p for p in a.logs]
    main_log = a.main or logs[0]
    if main_log not in logs:
        logs = [main_log] + logs
    logs = [main_log] + [p for p in logs if p != main_log]
    missing = [str(p) for p in logs if not Path(p).is_file()]
    if missing:
        print(f"missing log(s): {missing}", file=sys.stderr)
        return 1
    results = []
    for p in logs:
        try:
            results.append(analyse_log(p))
        except (ValueError, KeyError) as exc:
            print(f"{p}: unreadable: {exc}", file=sys.stderr)
            return 1
        print(f"read {p}: hover {results[-1]['hover_s']:.0f} s in {results[-1]['hover_segments']} segments")
    if not results[0]["hover_segments"]:
        print("the main log has no hover segment", file=sys.stderr)
        return 2
    prop = proposal(results[0])
    a.out_dir.mkdir(parents=True, exist_ok=True)
    body = {"script": "scripts/fit_estimate_error.py", "status": "EXPLORATORY", "main_log": results[0]["name"],
            "rules": {"airborne_m": AIRBORNE_M, "trim_s": TRIM_S, "hover_hspeed_mps": HOVER_HSPEED,
                      "hover_vspeed_mps": HOVER_VSPEED, "hover_min_s": HOVER_MIN_S, "moving_hspeed_mps": MOVING_HSPEED,
                      "rho_floor": RHO_FLOOR, "max_lag_s": MAX_LAG_S, "floor_share": FLOOR_SHARE,
                      "slope_half_samples": SLOPE_HALF, "max_meas_gap_s": MAX_MEAS_GAP_S},
            "proposal": prop, "logs": [{k: v for k, v in r.items() if k != "_series"} for r in results]}
    (a.out_dir / "results.json").write_text(json.dumps(_clean(body), indent=1))
    (a.out_dir / "proposed_starling_physics_v1.toml").write_text(proposal_toml(results[0], prop))
    (a.out_dir / "results.md").write_text(report_md(results, results[0]["name"], prop))
    if not a.no_figures:
        figures(results, a.out_dir)
    print(f"wrote {a.out_dir}")
    for q, p in prop.items():
        print(f"  {q}: {p['status']} sigma {p.get('sigma')} tau {p.get('tau_s')} ({p['why']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
