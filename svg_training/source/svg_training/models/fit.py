"""Fit the response model (models/response.py) to velocity steps recorded at the plug-in point.

Pipeline (Task 6 drives it; this module takes arrays, not files):
  1. `to_vehicle_time` on BOTH the command and the odometry stamps, with the same scale and t0. Bag stamps
     are wall time; the AirStack simulator runs about 1.33 x faster than the wall clock (PX4 lockstep), so a
     fit on wall stamps gives a delay and time constants `scale` times too small (Review Focus 1).
  2. Odometry twist is body frame (see response.py): `response.body_to_world(v_body, q)` first.
  3. `resample_uniform` onto one grid (dt 0.01 s of vehicle time by default):
       command  -> zero-order hold, CELL-AVERAGED: grid value k = mean of the held command over
                   [t_k, t_k + dt). A switch inside a cell becomes a fractional value, so the switch time is
                   kept to first order (plain sampling would make every step late by 0 to dt, dt/2 on
                   average, and bias the fitted delay low by about dt/2).
       velocity -> linear interpolation of the odometry at t_k (odometry is ~45-60 Hz wall, 3-4 grid cells).
  4. `segment_steps` -> one window per step; `split_alternate` -> even indices train, odd held out.
  5. `fit` (least squares on the training windows only) and `evaluate` (held-out windows only).

The command must be the teleop command (`teleop_command`), i.e. what a policy sends, before the commander's
ramp / P term / CBF. `setpoint_raw` and `velocity_command` are after that shaping: fitting them would model
PX4 alone and drop the commander from the trainer's drone (Review Focus 2). `fit` and `step_data` refuse them.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares

from .response import FAMILIES, ResponseParams, cap_speed, simulate

ONE_MINUS_INV_E = 1.0 - math.exp(-1.0)        # 0.632...: the "t63" level of a step
AXES = ("x", "y", "z")
TELEOP = "teleop_command"
# Parameter vector of the optimiser, bounds and default starts. The bounds are deliberately wider than the
# fit gates (delay 0..0.40 s) so the gate check stays meaningful; a value at a bound is flagged in the report.
LAG1_NAMES = ("delay_s", "tau_xy_s", "tau_z_s", "acc_max_xy_mps2", "acc_max_z_mps2")
LAG1_LOWER = (0.0, 0.02, 0.02, 0.2, 0.2)
LAG1_UPPER = (1.0, 5.0, 5.0, 30.0, 30.0)
# Starts begin with LOW acceleration limits on purpose: an acceleration limit that never binds has zero
# gradient, so a start above the true limit can stall there (seen: start 5.0 m/s^2 stuck at 5.0, true 3.0).
LAG1_STARTS = ((0.10, 0.40, 0.40, 1.5, 1.5), (0.25, 1.00, 1.00, 1.0, 1.0), (0.05, 0.25, 0.25, 4.0, 4.0))
TAU2_LOWER, TAU2_UPPER, TAU2_STARTS = 0.0, 2.0, (0.05, 0.20, 0.10)


@dataclass(frozen=True)
class StepData:
    """One recording on a uniform vehicle-time grid: t_s (T,), cmd_mps (T, 3), vel_mps (T, 3) world ENU,
    windows = [(start, end)] grid indices of each step (end exclusive)."""

    t_s: np.ndarray
    cmd_mps: np.ndarray
    vel_mps: np.ndarray
    windows: list

    @property
    def dt_s(self) -> float:
        return float(self.t_s[1] - self.t_s[0])


# ---------------------------------------------------------------- inputs

def check_command_source(label: str) -> str:
    """Return "teleop_command" if `label` (column/file/topic name) names the teleop command; else raise."""
    name = str(label).strip().rstrip("/").split("/")[-1]
    if name.endswith(".csv"):
        name = name[:-4]
    if name != TELEOP:
        raise ValueError(
            f"command source {label!r} refused: the response model is fitted from the {TELEOP} (what the policy "
            "sends, before the commander's ramp, P term and CBF); setpoint_raw / velocity_command are after "
            "that shaping and would model PX4 alone")
    return TELEOP


def to_vehicle_time(t_wall_s: np.ndarray, scale: float, t0_wall_s: float = 0.0) -> np.ndarray:
    """Vehicle time (T,) = (t_wall_s - t0_wall_s) * scale. Use the SAME scale and t0 for every stream."""
    if not scale > 0.0:
        raise ValueError(f"scale must be > 0, got {scale}")
    return (np.asarray(t_wall_s, dtype=float) - t0_wall_s) * scale


def resample_uniform(t_cmd_s: np.ndarray, cmd_mps: np.ndarray, t_odom_s: np.ndarray, vel_mps: np.ndarray,
                     dt_s: float = 0.01):
    """Put command (Tc, 3) and velocity (To, 3) on one grid; returns (t_s (T,), cmd (T, 3), vel (T, 3)).

    All stamps must already be vehicle time. Grid: from the later first stamp, cells [t_k, t_k + dt) that end
    no later than the earlier last stamp. Command: cell average of its zero-order hold. Velocity: linear
    interpolation at t_k.
    """
    tc = np.asarray(t_cmd_s, dtype=float)
    c = np.asarray(cmd_mps, dtype=float)[:, :3]
    to = np.asarray(t_odom_s, dtype=float)
    v = np.asarray(vel_mps, dtype=float)[:, :3]
    for name, t in (("command", tc), ("odometry", to)):
        if t.ndim != 1 or t.size < 2 or np.any(np.diff(t) <= 0.0):
            raise ValueError(f"{name} stamps must be strictly increasing (got {t.size} stamps)")
    t_start, t_end = max(tc[0], to[0]), min(tc[-1], to[-1])
    n = int(math.floor((t_end - t_start) / dt_s + 1e-9))
    if n < 2:
        raise ValueError("command and odometry stamps overlap by less than two grid cells")
    t = t_start + np.arange(n) * dt_s
    # integral of the held command: F(tc[j]) = sum_{i<j} c_i * (tc[i+1] - tc[i])
    f_at = np.concatenate([np.zeros((1, 3)), np.cumsum(c[:-1] * np.diff(tc)[:, None], axis=0)], axis=0)

    def integral(x):
        j = np.clip(np.searchsorted(tc, x, side="right") - 1, 0, tc.size - 1)
        return f_at[j] + c[j] * (x - tc[j])[:, None]

    cmd_grid = (integral(t + dt_s) - integral(t)) / dt_s
    vel_grid = np.stack([np.interp(t, to, v[:, a]) for a in range(3)], axis=1)
    return t, cmd_grid, vel_grid


def segment_steps(cmd: np.ndarray, t: np.ndarray, min_jump_mps: float = 0.2, tail_s: float = 2.0) -> list:
    """Step windows [(start, end)] (end exclusive) of a command (T, 3) on stamps (T,).

    A step starts where the command leaves rest: |cmd[k-1]| < min_jump_mps <= |cmd[k]|. Changes between
    non-rest levels inside a hold belong to the same step. The window runs through the hold and the release
    (first return to rest) and ends `tail_s` after the release, or at the next step's start, or at the end
    of the record, whichever comes first.
    """
    cmd = np.asarray(cmd, dtype=float)
    t = np.asarray(t, dtype=float)
    rest = np.linalg.norm(cmd, axis=-1) < min_jump_mps
    starts = [k for k in range(1, len(cmd)) if rest[k - 1] and not rest[k]]
    windows = []
    for i, s in enumerate(starts):
        nxt = starts[i + 1] if i + 1 < len(starts) else len(cmd)
        released = np.flatnonzero(rest[s:nxt])
        if released.size == 0:
            end = nxt
        else:
            r = s + int(released[0])
            end = min(nxt, int(np.searchsorted(t, t[r] + tail_s - 1e-9, side="left")))
        windows.append((s, end))
    return windows


def split_alternate(n_steps: int):
    """Deterministic split: (train = even indices, held_out = odd indices)."""
    return list(range(0, n_steps, 2)), list(range(1, n_steps, 2))


def step_data(cmd: np.ndarray, vel: np.ndarray, t_vehicle_s: np.ndarray, *, source: str,
              min_jump_mps: float = 0.2, tail_s: float = 2.0) -> StepData:
    """Check the inputs (teleop source, shapes, uniform grid) and segment the steps."""
    check_command_source(source)
    t = np.asarray(t_vehicle_s, dtype=float)
    cmd = np.asarray(cmd, dtype=float)
    vel = np.asarray(vel, dtype=float)
    if t.ndim != 1 or t.size < 3 or cmd.shape != (t.size, 3) or vel.shape != (t.size, 3):
        raise ValueError(f"need t (T,), cmd (T, 3), vel (T, 3); got {t.shape}, {cmd.shape}, {vel.shape}")
    dt = (t[-1] - t[0]) / (t.size - 1)
    if not dt > 0.0 or np.max(np.abs(np.diff(t) - dt)) > 1e-6:
        raise ValueError("t_vehicle_s must be a uniform grid (use resample_uniform on vehicle-time stamps)")
    return StepData(t, cmd, vel, segment_steps(cmd, t, min_jump_mps, tail_s))


# ---------------------------------------------------------------- metrics

def _t63(v_axis: np.ndarray, t: np.ndarray, level0: float, level1: float, t_onset: float) -> float:
    """Time from t_onset until v_axis first reaches 63 % of the step level0 -> level1 (linear interp.); nan if never."""
    thr = level0 + ONE_MINUS_INV_E * (level1 - level0)
    y = math.copysign(1.0, level1 - level0) * (v_axis - thr)
    hit = np.flatnonzero(y >= 0.0)
    if hit.size == 0:
        return math.nan
    j = int(hit[0])
    if j == 0:
        return float(t[0] - t_onset)
    frac = -y[j - 1] / (y[j] - y[j - 1])
    return float(t[j - 1] + frac * (t[j] - t[j - 1]) - t_onset)


def _step_row(index: int, data: StepData, model: np.ndarray, cmd_capped: np.ndarray, min_jump_mps: float) -> dict:
    s, e = data.windows[index]
    t, vel = data.t_s, data.vel_mps
    err = model[s:e] - vel[s:e]
    vel_rms = float(np.sqrt(np.mean(np.sum(err * err, axis=1))))
    rest = np.flatnonzero(np.linalg.norm(data.cmd_mps[s:e], axis=-1) < min_jump_mps)
    r = s + int(rest[0]) if rest.size else e                       # release (end of the hold)
    level0 = cmd_capped[max(s - 2, 0)]                             # before the step (skips a partial cell)
    level1 = np.median(cmd_capped[s:r], axis=0)                    # the held level
    axis = int(np.argmax(np.abs(level1 - level0)))
    l0, l1 = float(level0[axis]), float(level1[axis])
    t63_meas = _t63(vel[s:r, axis], t[s:r], l0, l1, t[s])
    t63_model = _t63(model[s:r, axis], t[s:r], l0, l1, t[s])
    t63_err = abs(t63_model - t63_meas)
    return {"index": index, "start_s": float(t[s]), "end_s": float(t[e - 1]), "axis": AXES[axis],
            "step_mps": l1 - l0, "vel_rms_mps": vel_rms, "t63_meas_s": t63_meas, "t63_model_s": t63_model,
            "t63_err_s": t63_err if math.isfinite(t63_err) else math.inf}


def evaluate(p: ResponseParams, segments: StepData, held_out_idx, min_jump_mps: float = 0.2) -> dict:
    """Score `p` on the held-out step windows ONLY.

    The model is simulated over the whole record from the first measured velocity (it never sees the
    measurements after that), then each held-out window is scored:
      vel_rms_mps  per step: sqrt(mean over the window of |v_model - v_meas|^2) (3-D error norm);
                   reported value = worst held-out step
      t63_err_s    per step: |t63_model - t63_meas|, t63 = time from the step's first grid cell until the
                   step axis reaches 63 % of the commanded change; inf if either never gets there;
                   reported value = worst held-out step
    Returns {"vel_rms_mps", "t63_err_s", "held_out_idx", "steps": [per-step rows]}.
    """
    held = [int(i) for i in held_out_idx]
    if not held:
        raise ValueError("evaluate needs at least one held-out step")
    if min(held) < 0 or max(held) >= len(segments.windows):
        raise ValueError(f"held-out index out of range (have {len(segments.windows)} steps)")
    model = simulate(segments.cmd_mps, segments.dt_s, p, v0_mps=segments.vel_mps[0])
    capped = cap_speed(segments.cmd_mps, p.speed_cap_mps)
    rows = [_step_row(i, segments, model, capped, min_jump_mps) for i in held]
    return {"vel_rms_mps": max(r["vel_rms_mps"] for r in rows), "t63_err_s": max(r["t63_err_s"] for r in rows),
            "held_out_idx": held, "steps": rows}


# ---------------------------------------------------------------- fit

def _params(x: np.ndarray, family: str, speed_cap_mps: float) -> ResponseParams:
    kw = dict(zip(LAG1_NAMES, (float(v) for v in x[:5])))
    return ResponseParams(**kw, speed_cap_mps=speed_cap_mps, family=family,
                          tau2_s=float(x[5]) if family == "lag2" else 0.0)


def fit(cmd: np.ndarray, vel: np.ndarray, t_vehicle_s: np.ndarray, family: str, train_idx, *, source: str,
        speed_cap_mps: float = 2.0, starts=None, min_jump_mps: float = 0.2, tail_s: float = 2.0):
    """Least-squares fit of the response model on the TRAINING step windows; returns (ResponseParams, report).

    cmd (T, 3) teleop command and vel (T, 3) world-frame measured velocity on the uniform VEHICLE-time grid
    t_vehicle_s (T,) (see `resample_uniform`). `source` names the command column/file/topic and must be the
    teleop command. `speed_cap_mps` is not fitted (the designed steps stay at or below it): the commander's
    `teleop_max_speed_mps`, 2.0 in `teleop_single_ours.yaml`.

    Residual: model minus measured velocity, all 3 axes, every grid sample of every training window,
    concatenated, unweighted (the model is simulated over the whole record from vel[0]).
    Free parameters: delay_s, tau_xy_s, tau_z_s, acc_max_xy_mps2, acc_max_z_mps2 (+ tau2_s for lag2).
    Solver: scipy.optimize.least_squares, method "trf", linear loss, x_scale "jac", 2-point Jacobian with
    diff_step 1e-6, ftol = xtol = gtol = 1e-10, max_nfev 3000, from each start in `starts` (default: three, LAG1_STARTS);
    the start with the lowest cost wins.
    """
    if family not in FAMILIES:
        raise ValueError(f"family must be one of {FAMILIES}, got {family!r}")
    data = step_data(cmd, vel, t_vehicle_s, source=source, min_jump_mps=min_jump_mps, tail_s=tail_s)
    train = [int(i) for i in train_idx]
    if not train or min(train) < 0 or max(train) >= len(data.windows):
        raise ValueError(f"train_idx must index the {len(data.windows)} step windows, got {train}")
    sel = np.concatenate([np.arange(*data.windows[i]) for i in train])
    meas = data.vel_mps[sel]
    dt = data.dt_s
    v0 = data.vel_mps[0]
    lower = np.array(LAG1_LOWER + ((TAU2_LOWER,) if family == "lag2" else ()))
    upper = np.array(LAG1_UPPER + ((TAU2_UPPER,) if family == "lag2" else ()))
    if starts is None:
        starts = [s + ((t2,) if family == "lag2" else ()) for s, t2 in zip(LAG1_STARTS, TAU2_STARTS)]

    def residual(x):
        model = simulate(data.cmd_mps, dt, _params(x, family, speed_cap_mps), v0_mps=v0)
        return (model[sel] - meas).ravel()

    runs = []
    for x0 in starts:
        x0 = np.clip(np.asarray(x0, dtype=float), lower, upper)
        r = least_squares(residual, x0, bounds=(lower, upper), method="trf", loss="linear", x_scale="jac",
                          diff_step=1e-6, ftol=1e-10, xtol=1e-10, gtol=1e-10, max_nfev=3000)
        runs.append((r, x0))
    best = min(range(len(runs)), key=lambda i: runs[i][0].cost)
    r = runs[best][0]
    p = _params(r.x, family, speed_cap_mps)
    names = LAG1_NAMES + (("tau2_s",) if family == "lag2" else ())
    span = upper - lower
    at_bound = [n for n, x, lo, hi, sp in zip(names, r.x, lower, upper, span)
                if x - lo < 1e-6 * sp or hi - x < 1e-6 * sp]
    train_eval = evaluate(p, data, train, min_jump_mps)
    report = {
        "family": family, "source": TELEOP, "dt_s": dt, "n_steps": len(data.windows),
        "windows": [list(w) for w in data.windows], "train_idx": train, "speed_cap_mps": float(speed_cap_mps),
        "params": p.to_dict(), "free_params": list(names), "lower": lower.tolist(), "upper": upper.tolist(),
        "at_bound": at_bound,
        "optimizer": {"method": "trf", "loss": "linear", "chosen_start": best,
                      "status": int(r.status), "message": str(r.message), "success": bool(r.success),
                      "nfev": int(r.nfev), "cost": float(r.cost),
                      "rms_train_mps": float(np.sqrt(2.0 * r.cost / r.fun.size))},
        "starts": [{"x0": x0.tolist(), "x": rr.x.tolist(), "cost": float(rr.cost), "status": int(rr.status),
                    "nfev": int(rr.nfev)} for rr, x0 in runs],
        "train_steps": train_eval["steps"],
        "train_vel_rms_mps": train_eval["vel_rms_mps"], "train_t63_err_s": train_eval["t63_err_s"],
    }
    return p, report
