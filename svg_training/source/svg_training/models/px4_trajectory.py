"""Real-drone response model (NumPy reference): PX4 trajectory setpoint (position + velocity) -> drone velocity.

What it stands for
------------------
On the real Starling the ground commander does not send a bare velocity. In teleop it sends ONE setpoint per
20 Hz tick with three parts (swarm_commander.py `publish_command`, trajectory output):

  * position  p_sp: the commander's reference point (where the drone was told to be), moved by the stick;
  * velocity  v_ff: the stick velocity after its acceleration ramp (the "feed-forward");
  * acceleration a_ff: the ramp's acceleration.

px4_interface turns that into a PX4 `trajectory_setpoint` with all three set, and PX4 1.14's position controller
(PositionControl.cpp `_positionControl`, `_velocityControl`) flies

    vel_sp = v_ff + Kp * (p_sp - p)                Kp = MPC_XY_P, |vel_sp| <= MPC_XY_VEL_MAX
    acc_sp = a_ff + P*(vel_sp - v) + I*int(vel_sp - v) - D*a         (MPC_XY_VEL_P/I/D_ACC)

and the attitude loop turns acc_sp into a tilt, with some lag. This module reproduces that law in the horizontal
plane (x, y, any world frame; the law is the same on both axes). Height and yaw are not modelled here.

Two families
------------
``lag1``  velocity tracking as one first-order lag:  dv = ff_gain*a_ff*dt + (1 - exp(-dt/tau)) * (vel_sp - v),
          with |dv| <= acc_max*dt. tau lumps the velocity PID and the attitude loop together.
``pid``   PX4's velocity PID with the gains as flown (vel_p, vel_i, vel_d, read from the log) and a first-order
          lag tau between the acceleration PX4 asks for and the one the drone gets (attitude loop and motors):
          acc_sp = ff_gain*a_ff + vel_p*e + int - vel_d*a, |acc_sp| <= acc_max; a += (1 - exp(-dt/tau))*(acc_sp - a);
          int += vel_i*e*dt (with PX4's anti-windup while acc_sp is capped); v += a*dt.
In both, ``delay_s`` shifts all three inputs later in time (transport over WiFi and DDS, plus any clock error).

Grid and indexing
-----------------
Inputs are sampled on a uniform grid t_k = t_0 + k*dt and held over [t_k, t_k + dt). ``simulate`` returns v[k] and
p[k] AT t_k, with v[0] = v0 and p[0] = p0. Position integrates the velocity by the trapezoid rule. Before t_0 a
delayed input holds its first value (the drone was already being sent it).

Shapes: (..., N, 2) for every time series; any leading batch dimensions are allowed and run together.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields, replace

import numpy as np
from scipy.optimize import least_squares

from svg_training.models.response import lag_alpha

FAMILIES = ("lag1", "pid")
FITTABLE = ("tau_s", "delay_s", "acc_max_mps2")
BOUNDS = {"tau_s": (0.01, 3.0), "delay_s": (0.0, 0.5), "acc_max_mps2": (0.2, 30.0)}
ONE_MINUS_INV_E = 1.0 - math.exp(-1.0)


@dataclass(frozen=True)
class TrajectoryParams:
    """Parameters of the trajectory-setpoint model; SI units, plain floats (TOML-friendly).

    kp_xy, vel_max_mps, vel_p, vel_i, vel_d are PX4 parameters read from the drone's log (never fitted).
    tau_s, delay_s, acc_max_mps2 are fitted. ff_gain weights the acceleration feed-forward (1 = as PX4 adds it).
    """

    family: str
    kp_xy: float                 # MPC_XY_P (1/s)
    tau_s: float                 # lag1: velocity lag; pid: acceleration (attitude) lag
    delay_s: float
    acc_max_mps2: float          # horizontal acceleration limit (norm); inf = none
    vel_max_mps: float = 3.0     # MPC_XY_VEL_MAX
    ff_gain: float = 1.0
    vel_p: float = 1.8           # MPC_XY_VEL_P_ACC (pid family)
    vel_i: float = 0.4           # MPC_XY_VEL_I_ACC
    vel_d: float = 0.2           # MPC_XY_VEL_D_ACC

    def __post_init__(self):
        if self.family not in FAMILIES:
            raise ValueError(f"family must be one of {FAMILIES}, got {self.family!r}")
        for f in fields(self):
            if f.name == "family":
                continue
            value = float(getattr(self, f.name))
            object.__setattr__(self, f.name, value)
            if math.isnan(value) or value < 0.0:
                raise ValueError(f"{f.name} must be >= 0, got {value}")
        for name in ("acc_max_mps2", "vel_max_mps"):
            if getattr(self, name) <= 0.0:
                raise ValueError(f"{name} must be > 0 (use inf for no limit)")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TrajectoryParams":
        unknown = set(d) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"unknown TrajectoryParams keys: {sorted(unknown)}")
        return cls(**d)


@dataclass
class Window:
    """One leg of flight data on a uniform grid.

    t_s (N,); p_sp, v_ff, a_ff (N, 2) the setpoint; p0, v0 (2,) the measured state at t_s[0]; meas_idx (M,) the
    grid indices where the velocity was measured; v_meas (M, 2) that velocity (NaN = no sample). a0 (2,) is the
    measured acceleration at t_s[0] (pid family; zeros when None).
    """

    t_s: np.ndarray
    p_sp: np.ndarray
    v_ff: np.ndarray
    a_ff: np.ndarray
    p0: np.ndarray
    v0: np.ndarray
    meas_idx: np.ndarray
    v_meas: np.ndarray
    label: str = ""
    a0: np.ndarray | None = None


# ------------------------------------------------------------------------------------------------- the law
def _cap_norm(x: np.ndarray, limit: float) -> np.ndarray:
    if not math.isfinite(limit):
        return x
    norm = np.linalg.norm(x, axis=-1, keepdims=True)
    return x * np.minimum(1.0, limit / np.maximum(norm, 1e-12))


def delay_signal(x: np.ndarray, dt_s: float, delay_s: float) -> np.ndarray:
    """(..., N, 2) -> the same signal delay_s later, by linear interpolation on the grid; holds x[0] before t_0."""
    x = np.asarray(x, dtype=float)
    if delay_s <= 0.0:
        return x
    d = delay_s / dt_s
    n = int(math.floor(d))
    f = d - n
    first = np.repeat(x[..., :1, :], n + 1, axis=-2)
    padded = np.concatenate([first, x], axis=-2)          # padded[j + n + 1] = x[j]
    big_n = x.shape[-2]
    a = padded[..., 1:big_n + 1, :]                       # x[k - n]
    b = padded[..., 0:big_n, :]                           # x[k - n - 1]
    return (1.0 - f) * a + f * b


def simulate(p_sp: np.ndarray, v_ff: np.ndarray, a_ff: np.ndarray, dt_s: float, params: TrajectoryParams,
             p0: np.ndarray, v0: np.ndarray, a0: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Velocity and position (..., N, 2) at the grid times for the setpoint (..., N, 2). See the module doc."""
    p_sp, v_ff, a_ff = (np.asarray(x, dtype=float) for x in (p_sp, v_ff, a_ff))
    if p_sp.shape[-1] != 2 or p_sp.shape != v_ff.shape or p_sp.shape != a_ff.shape:
        raise ValueError(f"p_sp, v_ff, a_ff must share a (..., N, 2) shape, got {p_sp.shape}, {v_ff.shape}, "
                         f"{a_ff.shape}")
    if not dt_s > 0.0:
        raise ValueError("dt_s must be > 0")
    P = delay_signal(p_sp, dt_s, params.delay_s)
    V = delay_signal(v_ff, dt_s, params.delay_s)
    A = delay_signal(a_ff, dt_s, params.delay_s) * params.ff_gain
    batch = p_sp.shape[:-2]
    n = p_sp.shape[-2]
    v = np.broadcast_to(np.asarray(v0, dtype=float), batch + (2,)).copy()
    p = np.broadcast_to(np.asarray(p0, dtype=float), batch + (2,)).copy()
    acc = (np.zeros(batch + (2,)) if a0 is None
           else np.broadcast_to(np.asarray(a0, dtype=float), batch + (2,)).copy())
    integ = np.zeros(batch + (2,))
    alpha = lag_alpha(dt_s, params.tau_s)
    kp, vmax, amax = params.kp_xy, params.vel_max_mps, params.acc_max_mps2
    out_v = np.empty(batch + (n, 2))
    out_p = np.empty(batch + (n, 2))
    out_v[..., 0, :] = v
    out_p[..., 0, :] = p
    lag1 = params.family == "lag1"
    for k in range(n - 1):
        vel_sp = _cap_norm(V[..., k, :] + kp * (P[..., k, :] - p), vmax)
        if lag1:
            dv = _cap_norm(A[..., k, :] * dt_s + alpha * (vel_sp - v), amax * dt_s)
            v_new = v + dv
        else:
            e = vel_sp - v
            raw = A[..., k, :] + params.vel_p * e + integ - params.vel_d * acc
            acc_sp = _cap_norm(raw, amax)
            acc = acc + alpha * (acc_sp - acc)
            # PX4's horizontal anti-windup (PositionControl.cpp, "tracking Anti-Windup"): while the acceleration
            # is saturated, the integrator sees the error minus (2 / vel_p) * (asked - produced).
            e_int = e - (2.0 / max(params.vel_p, 1e-9)) * (raw - acc_sp)
            integ = integ + params.vel_i * e_int * dt_s
            v_new = v + acc * dt_s
        p = p + 0.5 * (v + v_new) * dt_s
        v = v_new
        out_v[..., k + 1, :] = v
        out_p[..., k + 1, :] = p
    return out_v, out_p


def simulate_window(params: TrajectoryParams, w: Window) -> np.ndarray:
    """Model velocity (N, 2) on the window's grid, started from its measured state."""
    dt = float(w.t_s[1] - w.t_s[0])
    v, _p = simulate(w.p_sp, w.v_ff, w.a_ff, dt, params, p0=w.p0, v0=w.v0, a0=w.a0)
    return v


# ------------------------------------------------------------------------------------------------- data helpers
def split_alternate(n: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Legs in time order: even indices train, odd indices held out. Depends on the count only."""
    return tuple(range(0, n, 2)), tuple(range(1, n, 2))


def find_legs(t_s: np.ndarray, v_xy: np.ndarray, on_mps: float = 0.1, min_len_s: float = 0.6,
              merge_gap_s: float = 1.0) -> list[tuple[float, float]]:
    """Spans [(t_start, t_end)] where the horizontal speed |v_xy| (N, 2) is above on_mps.

    Runs closer than merge_gap_s are merged first; runs shorter than min_len_s (first to last sample above the
    threshold) are then dropped.
    """
    t_s = np.asarray(t_s, dtype=float)
    on = np.linalg.norm(np.asarray(v_xy, dtype=float), axis=-1) > on_mps
    runs = []
    k = 0
    while k < len(on):
        if on[k]:
            j = k
            while j + 1 < len(on) and on[j + 1]:
                j += 1
            runs.append([t_s[k], t_s[j]])
            k = j + 1
        else:
            k += 1
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] < merge_gap_s:
            merged[-1][1] = r[1]
        else:
            merged.append(list(r))
    return [(float(a), float(b)) for a, b in merged if b - a >= min_len_s]


def time_to_63pct(t_s: np.ndarray, v: np.ndarray, level0: float, level1: float, t_onset: float) -> float:
    """Time from t_onset until v first reaches 63 % of the change level0 -> level1 (linear interpolation).

    Only samples at or after t_onset count. NaN if never reached.
    """
    t_s, v = np.asarray(t_s, dtype=float), np.asarray(v, dtype=float)
    keep = t_s >= t_onset
    t_s, v = t_s[keep], v[keep]
    thr = level0 + ONE_MINUS_INV_E * (level1 - level0)
    y = math.copysign(1.0, level1 - level0) * (v - thr)
    hit = np.flatnonzero(y >= 0.0)
    if hit.size == 0:
        return math.nan
    j = int(hit[0])
    if j == 0:
        return float(t_s[0] - t_onset)
    frac = -y[j - 1] / (y[j] - y[j - 1])
    return float(t_s[j - 1] + frac * (t_s[j] - t_s[j - 1]) - t_onset)


# ------------------------------------------------------------------------------------------------- scoring
def simulate_windows(params: TrajectoryParams, windows: list[Window]) -> list[np.ndarray]:
    """simulate_window for every window, run as one batch (padded to the longest; each window's own grid step
    must be the same). Returns one (N_i, 2) array per window, identical to simulate_window."""
    if not windows:
        return []
    dts = {round(float(w.t_s[1] - w.t_s[0]), 9) for w in windows}
    if len(dts) != 1:
        return [simulate_window(params, w) for w in windows]
    dt = dts.pop()
    n = max(len(w.t_s) for w in windows)

    def pad(x):
        x = np.asarray(x, dtype=float)
        return np.concatenate([x, np.repeat(x[-1:], n - len(x), axis=0)]) if len(x) < n else x

    stack = lambda attr: np.stack([pad(getattr(w, attr)) for w in windows])          # noqa: E731
    a0 = np.stack([np.zeros(2) if w.a0 is None else np.asarray(w.a0, dtype=float) for w in windows])
    v, _p = simulate(stack("p_sp"), stack("v_ff"), stack("a_ff"), dt, params,
                     p0=np.stack([w.p0 for w in windows]), v0=np.stack([w.v0 for w in windows]), a0=a0)
    return [v[i, :len(w.t_s)] for i, w in enumerate(windows)]


def _errors(params: TrajectoryParams, windows: list[Window]) -> np.ndarray:
    out = []
    for w, v in zip(windows, simulate_windows(params, windows)):
        err = v[np.asarray(w.meas_idx)] - w.v_meas
        out.append(err[np.isfinite(err)])
    return np.concatenate(out) if out else np.zeros(0)


def velocity_rms(params: TrajectoryParams, windows: list[Window]) -> float:
    """RMS of the velocity error over every measured sample and both axes (m/s, per axis)."""
    err = _errors(params, windows)
    return float(np.sqrt(np.mean(err ** 2))) if err.size else math.nan


# ------------------------------------------------------------------------------------------------- the fit
def _with(params: TrajectoryParams, names, x) -> TrajectoryParams:
    return replace(params, **{n: float(v) for n, v in zip(names, x)})


_LOG = ("tau_s", "acc_max_mps2")     # fitted on a log scale (positive, spans a decade); delay_s on a linear one


def _to_x(name, value):
    return math.log(value) if name in _LOG else value


def _from_x(name, x):
    return math.exp(x) if name in _LOG else x


def _solve(windows, params, names, max_nfev):
    lo = [_to_x(n, BOUNDS[n][0]) for n in names]
    hi = [_to_x(n, BOUNDS[n][1]) for n in names]
    x0 = [min(max(_to_x(n, getattr(params, n)), lo[i] + 1e-6), hi[i] - 1e-6) for i, n in enumerate(names)]

    def unpack(x):
        return _with(params, names, [_from_x(n, xi) for n, xi in zip(names, x)])

    res = least_squares(lambda x: _errors(unpack(x), windows), x0, bounds=(lo, hi), method="trf",
                        diff_step=1e-3, max_nfev=max_nfev)
    return unpack(res.x), float(2.0 * res.cost), int(res.nfev)


ACC_STARTS_MPS2 = (1.0, 10.0)


def _solve_multi(windows, params, names, max_nfev):
    """_solve from each acc_max start in ACC_STARTS_MPS2 when acc_max is free, keeping the best.

    A limit that does not bind has zero gradient, and from there the solver trades it for a slow lag and stays;
    a start where it binds avoids that, a start where it does not covers the case of no limit.
    """
    if "acc_max_mps2" not in names:
        return _solve(windows, params, names, max_nfev)
    best, total = None, 0
    for a in ACC_STARTS_MPS2:
        got, sse, k = _solve(windows, replace(params, acc_max_mps2=a), names, max_nfev)
        total += k
        if best is None or sse < best[1]:
            best = (got, sse)
    return best[0], best[1], total


def fit(windows: list[Window], start: TrajectoryParams, free=FITTABLE,
        delay_grid_s=tuple(np.round(np.arange(0.0, 0.401, 0.05), 3)), max_nfev: int = 60):
    """Least-squares fit of the `free` parameters on `windows` (the training legs only); the rest stay as in `start`.

    Only tau_s, delay_s and acc_max_mps2 may be free: Kp and the velocity-PID gains are the drone's own PX4
    parameters and are fixed. When delay_s is free it is first scanned on `delay_grid_s` (the other free parameters
    fitted at each point), then everything is refined together from the best point: a delay is easily caught in a
    local minimum. A free acc_max_mps2 starts from each of ACC_STARTS_MPS2 (see _solve_multi). Deterministic.
    Returns (params, info) with info = {train_rms_mps, nfev, delay_profile [(delay_s, sse)]}.
    """
    names = tuple(free)
    bad = [n for n in names if n not in FITTABLE]
    if bad:
        raise ValueError(f"only {FITTABLE} may be fitted, got {bad}")
    if not windows:
        raise ValueError("no training windows")
    params = start
    nfev = 0
    profile = []
    if "delay_s" in names and delay_grid_s:
        inner = tuple(n for n in names if n != "delay_s")
        best = None
        for d in delay_grid_s:
            trial = replace(params, delay_s=float(d))
            if inner:
                trial, sse, k = _solve_multi(windows, trial, inner, max_nfev)
                nfev += k
            else:
                sse = float(np.sum(_errors(trial, windows) ** 2))
                nfev += 1
            profile.append((float(d), sse))
            if best is None or sse < best[1]:
                best = (trial, sse)
        params = best[0]
    params, _sse, k = (_solve(windows, params, names, max_nfev) if profile
                       else _solve_multi(windows, params, names, max_nfev))
    nfev += k
    return params, {"train_rms_mps": velocity_rms(params, windows), "nfev": nfev, "delay_profile": profile}
