#!/usr/bin/env python3
"""Vehicle-time yaw analysis of one PX4 drone (SIM ONLY, CLAUDE.md iron rule 9: nothing measured here is ported).

Pure Python (stdlib + numpy; no pyulog, no rclpy). Reads the CSV `ulog_yaw_dump.py` writes from a PX4 ulog:
`# key=value` header (source, sysid, MC_YAW_P, MC_YAWRATE_P/I/D/K, arm_s, disarm_s) and the columns
    t_s,heading_ned_deg,x_ned,y_ned,yaw_rate_dps,ff_dps,yawspeed_sp_dps,yaw_sp_ned_deg
on the vehicle_local_position clock, t_s = PX4 vehicle seconds since boot (never wall time: the sim ran 0.36x
real time in the 10-30 sessions and 1.32x in ledger #17-#19, so every time here is vehicle time).

Frames: PX4 is NED (heading 0 = north, clockwise positive); the commander's teleop `angular.z` is ENU
(counter-clockwise positive). Pulse sign +1 = the commander's +angular.z = ENU CCW = NED feed-forward NEGATIVE.
Headings are converted to ENU (`ned_to_enu_deg`) and unwrapped (`unwrap_deg`) before any difference is taken.

A pulse that never released (setpoint non-zero to the end of the data) is returned with released=False and every
post-release number None: the caller must report it UNVERIFIED, never PASS and never skip it.
"""
import math
import os
import sys
from collections import namedtuple

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metrics_core import CsvLineParser  # noqa: E402  the one CSV line parser

GAIN_KEYS = ("MC_YAW_P", "MC_YAWRATE_P", "MC_YAWRATE_I", "MC_YAWRATE_D", "MC_YAWRATE_K")
COLUMNS = ("t_s", "heading_ned_deg", "x_ned", "y_ned", "yaw_rate_dps", "ff_dps", "yawspeed_sp_dps", "yaw_sp_ned_deg")
RING_HYST_DEG = 0.5          # a ring crossing counts only once (h - h_final) passes this far to the other side

Pulse = namedtuple("Pulse", "onset_s release_s sign plateau_dps released")


# ------------------------------------------------------------------------------------------------ reading
def read_px4_csv(path):
    """(meta dict, column list, float array rows x cols); raises FileNotFoundError / ValueError, never returns empty
    for a missing file (a missing ulog CSV must end as UNVERIFIED in the caller, not as 'no pulses')."""
    parser = CsvLineParser(strict=True, source=str(path))
    with open(path) as fh:
        for raw in fh:
            parser.feed(raw)
    if parser.columns is None:
        raise ValueError("%s: no column line" % path)
    missing = [c for c in COLUMNS if c not in parser.columns]
    if missing:
        raise ValueError("%s: missing columns %s" % (path, ",".join(missing)))
    data = np.array(parser.rows, dtype=float).reshape(len(parser.rows), len(parser.columns))
    return parser.meta, parser.columns, data


def read_changes(path):
    """`t_s name value` lines (vehicle time) -> [(t_s, name, value)]; '#' lines and blanks ignored."""
    out = []
    with open(path) as fh:
        for line in fh:
            parts = line.split()
            if len(parts) != 3 or parts[0].startswith("#"):
                continue
            try:
                out.append((float(parts[0]), parts[1], float(parts[2])))
            except ValueError:
                continue
    return out


# ------------------------------------------------------------------------------------------------ frames
def ned_to_enu_deg(h_ned_deg):
    """NED heading (0 = north, clockwise +) -> ENU yaw (0 = east, counter-clockwise +), degrees, not wrapped."""
    return 90.0 - np.asarray(h_ned_deg, dtype=float) if np.ndim(h_ned_deg) else 90.0 - float(h_ned_deg)


def unwrap_deg(a):
    """Unwrap a degree series across the +-180 seam; NaN samples stay NaN and do not break the unwrap."""
    a = np.asarray(a, dtype=float).copy()
    ok = ~np.isnan(a)
    if ok.any():
        a[ok] = np.degrees(np.unwrap(np.radians(a[ok])))
    return a


def _wrap180(d):
    return (d + 180.0) % 360.0 - 180.0


# ------------------------------------------------------------------------------------------------ pulses
def find_pulses(t, ff, min_plateau_dps=20.0, quiet_s=2.0):
    """Yaw pulses in an ENU-signed rate setpoint `ff` (deg/s, + = CCW). Onset = first sample with |ff| >= min_plateau
    after >= quiet_s of |ff| < min_plateau/2 (NaN is not quiet); release = first later sample with |ff| below half the
    pulse's running peak. A pulse still on at the end of the data: released=False, release_s=None."""
    t = np.asarray(t, dtype=float); ff = np.asarray(ff, dtype=float)
    a = np.abs(ff)
    quiet = (a < min_plateau_dps / 2.0) & ~np.isnan(ff)
    pulses, quiet_since, i, n = [], None, 0, len(t)
    while i < n:
        if quiet[i]:
            quiet_since = t[i] if quiet_since is None else quiet_since
            i += 1
            continue
        if quiet_since is not None and a[i] >= min_plateau_dps and t[i] - quiet_since >= quiet_s:
            on, peak, j = i, a[i], i + 1
            while j < n and not (a[j] < 0.5 * peak):        # NaN never releases
                peak = max(peak, a[j]) if not np.isnan(a[j]) else peak
                j += 1
            seg = a[on:j]
            plateau = float(np.nanmedian(seg)) if np.any(~np.isnan(seg)) else float("nan")
            sign = 1 if ff[on] > 0 else -1
            if j < n:
                pulses.append(Pulse(float(t[on]), float(t[j]), sign, plateau, True))
            else:
                pulses.append(Pulse(float(t[on]), None, sign, plateau, False))
            i = j
            quiet_since = None
            continue
        quiet_since = None
        i += 1
    return pulses


def _ring(t, e, t_from, hyst):
    """Crossings of e through 0 with hysteresis, counted from t_from; returns (count, zero-crossing times)."""
    m = t >= t_from
    tt, ee = t[m], e[m]
    if len(tt) == 0:
        return 0, []
    side = 1 if ee[0] >= 0 else -1
    last_zero, times = None, []
    for k in range(1, len(tt)):
        if np.isnan(ee[k]):
            continue
        if np.sign(ee[k]) != np.sign(ee[k - 1]) and not np.isnan(ee[k - 1]):
            last_zero = tt[k - 1] + (tt[k] - tt[k - 1]) * (0.0 - ee[k - 1]) / (ee[k] - ee[k - 1]) if ee[k] != ee[k - 1] else tt[k]
        if side * ee[k] < -hyst:
            times.append(last_zero if last_zero is not None else tt[k])
            side = -side
    return len(times), times


def measure_pulse(p, t, h_enu_deg, rate_dps, x, y, t_end, band_deg=2.0, ring_hyst_deg=RING_HYST_DEG):
    """Numbers of one pulse, vehicle time. h_enu_deg must already be unwrapped. Post-release keys are None for an
    unreleased pulse. overshoot = max of sign*(h - h_final) after release (continued turning past the hold);
    undershoot = max of -sign*(h - h_final) (swing back); h_final = mean over the last 1.0 s of [release, t_end]."""
    t = np.asarray(t, dtype=float)
    on_i = int(np.searchsorted(t, p.onset_s))
    w = (t >= p.onset_s) & (t <= t_end)
    dx, dy = x[w] - x[on_i], y[w] - y[on_i]
    drift = float(np.nanmax(np.hypot(dx, dy))) if w.any() else float("nan")
    out = dict(onset_s=p.onset_s, release_s=p.release_s, sign=p.sign, plateau_dps=p.plateau_dps, released=p.released,
               xy_drift_m=drift, t_end_s=float(t_end))
    post_keys = ("turn_deg", "overshoot_deg", "undershoot_deg", "settle_s", "ring_crossings", "ring_hz",
                 "peak_rate_dps", "peak_rate_abs_dps", "plateau_meas_dps", "window_s", "h_final_enu_deg")
    if not p.released:
        out.update({k: None for k in post_keys})
        return out
    rel_i = int(np.searchsorted(t, p.release_s))
    out["turn_deg"] = float(h_enu_deg[min(rel_i, len(t) - 1)] - h_enu_deg[on_i])
    pl = (t >= p.onset_s + 0.3) & (t <= p.release_s)
    out["plateau_meas_dps"] = float(np.nanmedian(np.abs(rate_dps[pl]))) if pl.any() else float("nan")
    # rate_dps is PX4 body z (FRD ~ NED, clockwise +). peak_rate_dps = the fastest swing BACK (against the turn) in
    # [release, release + 3 s]: max |rate| there always includes the ~plateau rate the drone still has at release,
    # which is the stop itself, not a bounce. peak_rate_abs_dps keeps that plain max for the INFO table.
    pr = (t >= p.release_s) & (t <= p.release_s + 3.0)
    back = p.sign * rate_dps[pr]                                  # ENU rate = -NED rate; against the turn = -sign*ENU
    out["peak_rate_dps"] = float(max(0.0, np.nanmax(back))) if pr.any() else float("nan")
    out["peak_rate_abs_dps"] = float(np.nanmax(np.abs(rate_dps[pr]))) if pr.any() else float("nan")
    post = (t >= p.release_s) & (t <= t_end)
    tp, hp = t[post], h_enu_deg[post]
    fin = tp >= t_end - 1.0
    h_final = float(np.nanmean(hp[fin])) if fin.any() else float(hp[-1])
    e = hp - h_final
    out["overshoot_deg"] = float(max(0.0, np.nanmax(p.sign * e)))
    out["undershoot_deg"] = float(max(0.0, np.nanmax(-p.sign * e)))
    out["h_final_enu_deg"] = h_final
    outside = np.abs(e) > band_deg
    if outside[-1]:
        out["settle_s"] = None                                   # still out of the band at the end of the window
    elif not outside.any():
        out["settle_s"] = 0.0
    else:
        k = int(np.nonzero(outside)[0][-1]) + 1
        out["settle_s"] = float(tp[k] - p.release_s)
    inside = np.nonzero(~outside)[0]
    if len(inside):
        n, times = _ring(tp, e, tp[inside[0]], ring_hyst_deg)
    else:
        n, times = 0, []
    out["ring_crossings"] = n
    out["ring_hz"] = float((n - 1) / (2.0 * (times[-1] - times[0]))) if n >= 3 and times[-1] > times[0] else float("nan")
    out["window_s"] = float(t_end - p.release_s)
    return out


# ------------------------------------------------------------------------------------------------ gains
def gains_in_force(changes, t, header):
    """{MC_YAW*: value} at vehicle time t: the last change strictly before t, else the ulog header's value."""
    g = {k: header.get(k) for k in GAIN_KEYS}
    for ts, name, val in sorted(changes, key=lambda c: c[0]):
        if ts < t and name in g:
            g[name] = val
    return g


def group_by_gains(pulses_with_gains):
    """[(gains tuple, [pulses])] in order of first appearance; gains tuple = sorted (name, value) pairs."""
    groups = []
    for p in pulses_with_gains:
        key = tuple(sorted(p["gains"].items()))
        for k, members in groups:
            if k == key:
                members.append(p)
                break
        else:
            groups.append((key, [p]))
    return groups


# ------------------------------------------------------------------------------------------------ patch-0007 tap
def tap_check(t, x_ned, y_ned, h_enu_deg, t0, t1):
    """Room-frame forward tap: angle between the xy displacement over [t0, t1] and room +x (ENU east = NED +y), and
    the heading change over the same window. ~90 deg direction error = the body-frame-velocity orbit symptom."""
    t = np.asarray(t, dtype=float)
    i0 = int(np.clip(np.searchsorted(t, t0), 0, len(t) - 1)); i1 = int(np.clip(np.searchsorted(t, t1, side="right") - 1, 0, len(t) - 1))
    e, n = y_ned[i1] - y_ned[i0], x_ned[i1] - x_ned[i0]
    h = unwrap_deg(h_enu_deg)
    return dict(direction_err_deg=abs(float(_wrap180(math.degrees(math.atan2(n, e))))),
                heading_change_deg=float(h[i1] - h[i0]), displacement_m=float(math.hypot(e, n)))


# ------------------------------------------------------------------------------------------------ the whole run
def _header_gains(meta):
    g = {}
    for k in GAIN_KEYS:
        try:
            g[k] = float(meta[k])
        except (KeyError, ValueError):
            g[k] = None
    return g


def analyse(csv_path, changes_path=None, wall_stamps=None, band_deg=2.0, min_plateau_dps=20.0, quiet_s=2.0):
    """Every pulse of one drone's ulog CSV, vehicle time. wall_stamps = optional [(onset_wall_s, release_wall_s)]
    per pulse (index-paired) -> time_scale[i] = vehicle / wall duration (INFO only; NaN when not given)."""
    meta, cols, data = read_px4_csv(csv_path)
    c = {name: data[:, cols.index(name)] for name in COLUMNS}
    t = c["t_s"]
    h_enu = unwrap_deg(ned_to_enu_deg(c["heading_ned_deg"]))
    marker = "ff_dps"
    ff = c["ff_dps"]
    if not np.any(np.nan_to_num(np.abs(ff)) >= min_plateau_dps / 2.0):      # U3: no feed-forward -> trajectory_setpoint
        marker, ff = "yawspeed_sp_dps", c["yawspeed_sp_dps"]
    pulses = find_pulses(t, -ff, min_plateau_dps, quiet_s)                  # NED -> ENU sign
    hdr = _header_gains(meta)
    changes = read_changes(changes_path) if changes_path and os.path.exists(str(changes_path)) else []
    rows = []
    for i, p in enumerate(pulses):
        nxt = pulses[i + 1].onset_s - 0.5 if i + 1 < len(pulses) else math.inf
        t_end = min(nxt, (p.release_s if p.released else t[-1]) + 12.0, float(t[-1]))
        r = measure_pulse(p, t, h_enu, c["yaw_rate_dps"], c["x_ned"], c["y_ned"], t_end, band_deg)
        r["gains"] = gains_in_force(changes, p.onset_s, hdr)
        rows.append(r)
    scale = []
    for i, r in enumerate(rows):
        s = float("nan")
        if wall_stamps and i < len(wall_stamps) and r["released"]:
            ow, rw = wall_stamps[i]
            if ow is not None and rw is not None and rw > ow:
                s = (r["release_s"] - r["onset_s"]) / (rw - ow)
        r["time_scale"] = s
        scale.append(s)
    return dict(meta=meta, marker=marker, header_gains=hdr, changes=changes, pulses=rows,
                groups=group_by_gains(rows), time_scale=scale, samples=int(len(t)),
                span_s=float(t[-1] - t[0]) if len(t) else 0.0)


if __name__ == "__main__":
    import json
    if len(sys.argv) < 2:
        print("usage: yaw_core.py <px4_drone_1.csv> [px4_param_changes.txt]", file=sys.stderr)
        sys.exit(2)
    res = analyse(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    res["groups"] = [[dict(k), [p["onset_s"] for p in m]] for k, m in res["groups"]]
    print(json.dumps(res, indent=1, default=str))
