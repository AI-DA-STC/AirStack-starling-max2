# tools/tests/synth_yaw.py
"""Synthetic PX4 yaw data in the schema `tools/live/ulog_yaw_dump.py` writes (sim-only test fixture).

A pulse turns the drone at `rate_dps` from onset to release; after release the heading error to the held heading
(= heading at release, as the commander's trajectory route adopts it) rings down as a second-order response
e'' + 2 zeta wn e' + wn^2 e = 0 with e(0) = 0, e'(0) = turn rate. Shared by Task 3's and Task 4's tests.
"""
import math

import numpy as np

COLUMNS = "t_s,heading_ned_deg,x_ned,y_ned,yaw_rate_dps,ff_dps,yawspeed_sp_dps,yaw_sp_ned_deg"
HEADER_GAINS = {"MC_YAW_P": 2.8, "MC_YAWRATE_P": 0.07, "MC_YAWRATE_I": 0.5, "MC_YAWRATE_D": 0.0, "MC_YAWRATE_K": 1.0}


def ring_down(tau, rate_dps=57.3, zeta=0.2, wn=2 * math.pi * 0.8):
    """Heading error (deg, along the turn direction) `tau` s after release; tau < 0 -> 0."""
    tau = np.asarray(tau, dtype=float)
    if zeta < 1.0:
        wd = wn * math.sqrt(1.0 - zeta * zeta)
        e = rate_dps / wd * np.exp(-zeta * wn * tau) * np.sin(wd * tau)
    else:                                    # critically damped
        e = rate_dps * tau * np.exp(-wn * tau)
    return np.where(tau < 0, 0.0, e)


def _enu_heading(t, pulses, start_heading_enu_deg, rate_dps):
    """Unwrapped ENU heading (deg) at every t, and the ENU commanded rate (deg/s) at every t."""
    h = np.full_like(t, float(start_heading_enu_deg))
    cmd = np.zeros_like(t)
    base = float(start_heading_enu_deg)
    for i, p in enumerate(pulses):
        on, dur, sg = float(p["onset"]), p.get("dur"), int(p["sign"])
        r = float(p.get("rate", rate_dps))   # per-pulse rate (deg/s), e.g. the slower patch-0007 turn
        nxt = float(pulses[i + 1]["onset"]) if i + 1 < len(pulses) else math.inf
        zeta, wn = float(p.get("zeta", 0.2)), 2 * math.pi * float(p.get("f_hz", 0.8))
        rel = math.inf if dur is None else on + float(dur)
        turn = (t >= on) & (t < rel)
        h[turn] = base + sg * r * (t[turn] - on)
        cmd[turn] = sg * r
        if dur is None:                      # never released: keeps turning to the end of the data
            break
        hold = base + sg * r * (rel - on)
        after = (t >= rel) & (t < nxt)
        h[after] = hold + sg * ring_down(t[after] - rel, r, zeta, wn)
        base = hold + sg * float(ring_down(nxt - rel, r, zeta, wn)) if nxt < math.inf else hold
    return h, cmd


def _held(t, cmd, hz):
    """Sample cmd at `hz` and hold the previous value onto the clock t (what a slower PX4 topic looks like)."""
    ts = np.arange(t[0], t[-1] + 1e-9, 1.0 / hz)
    vs = np.array([cmd[np.searchsorted(t, s, side="right") - 1] for s in ts])
    idx = np.searchsorted(ts, t, side="right") - 1
    return vs[np.clip(idx, 0, len(vs) - 1)]


def px4_csv(path, pulses, hz=84, sign_flip=False, seam=False, start_heading_enu_deg=None, rate_dps=57.3,
            ff_hz=20, sp_hz=5, ff_zero=False, tail_s=15.0, header=None, xy_ramp_mps=(0.0, 0.0), nan_window=None,
            xy_moves=()):
    """Write a CSV in the dumper's schema; returns `path`. pulses = [dict(onset, dur (None = never released), sign,
    zeta, f_hz)]. sign +1 = commander +angular.z = ENU CCW = NED ff negative. sign_flip writes the heading with the
    wrong sign (a frame bug); seam=True starts at 211.5 deg ENU so the first pulse's overshoot crosses ENU 270 deg =
    the NED +-180 seam the ulog wraps at. tail_s = data after the last release. xy_ramp_mps = constant NED
    (vx, vy) drift over the whole run. nan_window = (t0, t1) in the pulses' time base: heading and yaw rate NaN there
    (a gap, as metrics.csv has). A pulse may carry its own "rate" (deg/s). xy_moves = [(t0, t1, ve, vn)] in the
    pulses' time base: a room-frame move at ENU (east, north) m/s, e.g. the patch-0007 forward tap (east = NED +y)."""
    if start_heading_enu_deg is None:
        start_heading_enu_deg = 211.5 if seam else 0.0
    last = pulses[-1] if pulses else {"onset": 10.0, "dur": 0.0}
    t_end = float(last["onset"]) + float(last.get("dur") or 0.0) + tail_s
    t = np.arange(0.0, t_end, 1.0 / hz) + 100.0           # vehicle time since PX4 boot, never 0-based in a real ulog
    shifted = [dict(p, onset=float(p["onset"]) + 100.0) for p in pulses]
    h_enu, cmd_enu = _enu_heading(t, shifted, start_heading_enu_deg, rate_dps)
    h_ned = (h_enu - 90.0) if sign_flip else (90.0 - h_enu)
    h_ned_wrapped = (h_ned + 180.0) % 360.0 - 180.0
    rate_ned = np.gradient(-h_enu if not sign_flip else h_enu, t)
    ff_ned = -_held(t, cmd_enu, ff_hz)
    if ff_zero:
        ff_ned = np.zeros_like(t)
    sp_ned = -_held(t, cmd_enu, sp_hz)
    yaw_sp = h_ned_wrapped.copy()
    x_ned, y_ned = xy_ramp_mps[0] * (t - t[0]), xy_ramp_mps[1] * (t - t[0])
    for t0, t1, ve, vn in xy_moves:
        dt = np.clip(t - (t0 + 100.0), 0.0, t1 - t0)
        x_ned, y_ned = x_ned + vn * dt, y_ned + ve * dt
    if nan_window is not None:
        gap = (t >= nan_window[0] + 100.0) & (t < nan_window[1] + 100.0)
        h_ned_wrapped = h_ned_wrapped.copy(); h_ned_wrapped[gap] = np.nan; rate_ned = rate_ned.copy(); rate_ned[gap] = np.nan
    g = dict(HEADER_GAINS, **(header or {}))
    with open(path, "w") as fh:
        fh.write("# source=synthetic\n# sysid=2\n")
        for k, v in g.items():
            fh.write("# %s=%s\n" % (k, v))
        fh.write("# arm_s=%.6f\n# disarm_s=%.6f\n" % (t[0] + 1.0, t[-1] - 1.0))
        fh.write(COLUMNS + "\n")
        for row in zip(t, h_ned_wrapped, x_ned, y_ned, rate_ned, ff_ned, sp_ned, yaw_sp):
            fh.write(",".join("%.6f" % v for v in row) + "\n")
    return path


def wall_stamps(pulses, scale, wall0=1_800_000_000.0):
    """[(onset_wall_s, release_wall_s)] for analysed pulses when the sim ran at `scale` x real time (vehicle s per
    wall s): wall = wall0 + t_vehicle / scale."""
    out = []
    for p in pulses:
        rel = p.get("release_s")
        out.append((wall0 + p["onset_s"] / scale, None if rel is None else wall0 + rel / scale))
    return out


# ------------------------------------------------------------------------------------- Task 4: the run folder side
def enu_heading_at(t_vehicle, pulses, rate_dps=57.3, start_heading_enu_deg=0.0):
    """Unwrapped ENU heading (deg) of the same synthetic flight at vehicle times `t_vehicle` (the +100 s boot offset
    included, as in px4_csv)."""
    shifted = [dict(p, onset=float(p["onset"]) + 100.0) for p in pulses]
    return _enu_heading(np.asarray(t_vehicle, dtype=float), shifted, start_heading_enu_deg, rate_dps)


def metrics_csv(path, series, pulses, scale=1.32, wall0=1_800_000_000.0, hz=40, rate_dps=57.3, heading_gain=1.0,
                yaw_rate=True, tail_s=15.0, land_s=5.0, offsets=(0.0, 0.0, 0.0)):
    """The live metrics.csv of the same flight (metrics_core.csv_header / format_row), wall time: a vehicle instant
    t_v is the wall instant wall0 + t_v / scale; t0_unix = wall0 + 100 / scale (vehicle time 100 s = data start).
    Phase 2 from the start to the end of the pulses + tail_s, then land_s of phase 3. heading_gain scales the live
    heading (a live/ulog mismatch); yaw_rate=False writes 0 deg/s (odometry without angular.z, U5)."""
    import metrics_core as M
    last = pulses[-1] if pulses else {"onset": 10.0, "dur": 0.0}
    t_v_end = 100.0 + float(last["onset"]) + float(last.get("dur") or 0.0) + tail_s
    t0_unix = wall0 + 100.0 / scale
    tw = np.arange(0.0, (t_v_end - 100.0) / scale + land_s, 1.0 / hz)
    tv = 100.0 + tw * scale
    h, _ = enu_heading_at(tv, pulses, rate_dps)
    rel = heading_gain * (h - h[0])
    rate = np.gradient(rel, tw) if yaw_rate else np.zeros_like(tw)
    names = [s.name for s in series]
    cols = M.csv_columns(series)
    meta = {"offsets": list(offsets), "t0_unix": repr(t0_unix), "trigger": "drone_1", "drones": "drone_1",
            "refs": "ref_band_plus:2.0;ref_band_minus:-2.0;ref_overshoot_gate:3.0"}
    with open(path, "w") as fh:
        fh.write(M.csv_header(series, meta))
        for k, t in enumerate(tw):
            phase = 2 if tv[k] <= t_v_end else 3
            vals = {"heading_rel_deg": float(rel[k]), "heading_deg": float((h[k] + 180.0) % 360.0 - 180.0),
                    "yaw_rate_dps": float(rate[k]), "xy_drift_m": 0.0, "fence_breached": 0.0, "emergency": 0.0}
            fh.write(M.format_row(float(t), phase, {n: vals.get(n, float("nan")) for n in names}, cols) + "\n")
    return t0_unix


def stdout_log(path, pulses, scale=1.32, wall0=1_800_000_000.0, groups=None, rate_rad_s=1.0, extra=()):
    """test_stdout.log stamp lines in fly.sh's format for `pulses` (pulse k/i onset sign=+1 rate=1.000 / release).
    groups[i] = sweep set of pulse i (default 0). A pulse dict with kind="turn" prints `turn onset/release` instead.
    extra = [(t_vehicle_in_pulse_base, text)] lines (e.g. the tap). dur=None prints the release anyway (fly.sh thought
    it released; the ulog says otherwise)."""
    w = lambda tp: wall0 + (float(tp) + 100.0) / scale
    lines, idx = [], {}
    for i, p in enumerate(pulses):
        on, dur = float(p["onset"]), p.get("dur")
        rel = on + float(dur if dur is not None else 1.0)
        if p.get("kind") == "turn":
            lines.append((w(on), "turn onset sign=%+d rate=%.3f" % (p["sign"], float(p.get("rate", 28.65)) / 57.29578)))
            lines.append((w(rel), "turn release"))
            continue
        k = (groups or [0] * len(pulses))[i]
        idx[k] = idx.get(k, 0) + 1
        lines.append((w(on), "pulse %d/%d onset sign=%+d rate=%.3f" % (k, idx[k], p["sign"], rate_rad_s)))
        lines.append((w(rel), "pulse %d/%d release" % (k, idx[k])))
    for tp, text in extra:
        lines.append((w(tp), text))
    lines.sort()
    with open(path, "w") as fh:
        fh.write("[12:00:00] takeoff: success=True, message='ok'\n[12:00:10] start: success=True, message='ok'\n")
        for t, text in lines:
            fh.write("[%.6f] %s\n" % (t, text))
        fh.write("[12:05:00] land: success=True, message='ok'\n[12:05:15] landed: name: drone_1 state: IDLE\n")
    return path
