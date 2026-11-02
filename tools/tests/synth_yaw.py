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
        nxt = float(pulses[i + 1]["onset"]) if i + 1 < len(pulses) else math.inf
        zeta, wn = float(p.get("zeta", 0.2)), 2 * math.pi * float(p.get("f_hz", 0.8))
        rel = math.inf if dur is None else on + float(dur)
        turn = (t >= on) & (t < rel)
        h[turn] = base + sg * rate_dps * (t[turn] - on)
        cmd[turn] = sg * rate_dps
        if dur is None:                      # never released: keeps turning to the end of the data
            break
        hold = base + sg * rate_dps * (rel - on)
        after = (t >= rel) & (t < nxt)
        h[after] = hold + sg * ring_down(t[after] - rel, rate_dps, zeta, wn)
        base = hold + sg * float(ring_down(nxt - rel, rate_dps, zeta, wn)) if nxt < math.inf else hold
    return h, cmd


def _held(t, cmd, hz):
    """Sample cmd at `hz` and hold the previous value onto the clock t (what a slower PX4 topic looks like)."""
    ts = np.arange(t[0], t[-1] + 1e-9, 1.0 / hz)
    vs = np.array([cmd[np.searchsorted(t, s, side="right") - 1] for s in ts])
    idx = np.searchsorted(ts, t, side="right") - 1
    return vs[np.clip(idx, 0, len(vs) - 1)]


def px4_csv(path, pulses, hz=84, sign_flip=False, seam=False, start_heading_enu_deg=None, rate_dps=57.3,
            ff_hz=20, sp_hz=5, ff_zero=False, tail_s=15.0, header=None):
    """Write a CSV in the dumper's schema; returns `path`. pulses = [dict(onset, dur (None = never released), sign,
    zeta, f_hz)]. sign +1 = commander +angular.z = ENU CCW = NED ff negative. sign_flip writes the heading with the
    wrong sign (a frame bug); seam=True starts at 160 deg ENU so the first pulse crosses +-180."""
    if start_heading_enu_deg is None:
        start_heading_enu_deg = 160.0 if seam else 0.0
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
    yaw_sp = h_ned_wrapped
    g = dict(HEADER_GAINS, **(header or {}))
    with open(path, "w") as fh:
        fh.write("# source=synthetic\n# sysid=2\n")
        for k, v in g.items():
            fh.write("# %s=%s\n" % (k, v))
        fh.write("# arm_s=%.6f\n# disarm_s=%.6f\n" % (t[0] + 1.0, t[-1] - 1.0))
        fh.write(COLUMNS + "\n")
        for row in zip(t, h_ned_wrapped, np.zeros_like(t), np.zeros_like(t), rate_ned, ff_ned, sp_ned, yaw_sp):
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
