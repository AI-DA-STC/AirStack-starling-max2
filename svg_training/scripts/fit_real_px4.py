#!/usr/bin/env python3
"""Exploratory fit of the real-drone response model (models/px4_trajectory.py) to the real Starling's own PX4 logs.

Usage (from svg_training/):
    fit_real_px4.py [--ulog <main log>] [--cross <log> ...] [--sim-extract runs/s1_extract_check]
                    [--out-dir runs/2026-11-15_s1_real_px4_exploratory] [--fig-prefix docs/figures/s1_real]
                    [--accel-ff derived|logged|none]   (all three are fitted; the kept one is chosen on training legs)

Exploratory, not a run of record: no gates, no ledger row, no parameter file under params/.

What it does, in order
  1. Reads the ulog (read-only; a small ULog reader below, pyulog is not installed): `trajectory_setpoint`
     (position, velocity, acceleration; logged at 5 Hz), `vehicle_local_position` (10 Hz),
     `vehicle_local_position_setpoint` (PX4's own velocity setpoint after its position P term, 10 Hz) and the
     parameter section. PX4's NED axes are turned into ENU (x east = NED y, y north = NED x).
  2. Fixes the PX4 parameters the drone flew: MPC_XY_P (Kp), MPC_XY_VEL_P/I/D_ACC, MPC_XY_VEL_MAX, MPC_ACC_HOR.
  3. Two checks from the log alone: the position law (PX4's logged velocity setpoint against v_ff + K (p_sp - p),
     K by least squares) and the commander's clock (how far the reference point moved against the integral of
     the velocity setpoint, per leg: 1.0 = the commander's 0.05 s tick matches PX4's real time).
  4. Legs: spans where the horizontal speed setpoint is above 0.1 m/s (models.px4_trajectory.find_legs), in time
     order, each in a window from 1.0 s before to 2.5 s after, cut at the midpoint to its neighbours (windows never
     overlap). Split FIXED BEFORE FITTING: even legs train, odd legs held out (split_alternate). The split is
     written to split.json before the first fit.
  5. Fits two families on the training legs (Kp and the PID gains fixed from the log): lag1 (tau, delay,
     acceleration limit free) and pid (attitude lag, delay free; acceleration limit fixed at MPC_ACC_HOR), each with
     three sources of the feed-forward acceleration (derived, logged, none). Keeps the combination with the lowest
     TRAINING RMS; held-out RMS is only reported (fix round 1). Naive baselines (the drone flies the setpoint's
     speed, with no lag, and the same delayed by the fitted delay) are scored on the same legs, over the whole
     windows and over the active span (leg start to leg end + 1 s).
  6. Times to 63 % of each change (start and stop of every leg with a plateau of at least 0.2 m/s), for the
     setpoint, the measured velocity and the model.
  7. Cross-check: the kept parameters, with each other log's own PX4 parameters, scored on every leg of each
     --cross log (no refit), plus a refit on that log's even legs for comparison.
  8. Simulator comparison: the AirStack simulator's teleop pushes from --sim-extract (bag_to_csv.py output of
     sim_teleop_frame_run1: teleop_command, velocity_command, odometry; wall clock), as fractions of the command.
  9. Figures <fig-prefix>_held_out.png, _model_error.png, _sim_vs_real.png, _position_law.png; results.json and
     real_exploratory.toml in --out-dir. Refuses to overwrite nothing: it is exploratory and re-runnable.
Exit codes: 0 done; 1 unreadable input; 2 bad arguments or no legs.
"""
from __future__ import annotations

import argparse
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
sys.path.insert(0, str(ROOT / "source"))

from svg_training.models import px4_trajectory as m  # noqa: E402
from svg_training.models.response import body_to_world  # noqa: E402

FLIGHT_LOGS = Path.home() / "flight_logs"
MAIN_LOG = FLIGHT_LOGS / "2026-11-13/ulog_drone_2/log103.ulg"
CROSS_LOGS = (FLIGHT_LOGS / "2026-11-13/two_drone_teleop/drone_2/log105.ulg",
              FLIGHT_LOGS / "2026-11-13/two_drone_teleop/drone_1_candidates/08_47_58.ulg")
SIM_EXTRACT = ROOT / "runs/s1_extract_check"
DT_S = 0.01
PRE_S, POST_S = 1.0, 2.5
AIRBORNE_M = 0.3
PLATEAU_MIN_MPS = 0.2
PX4_PARAMS = ("MPC_XY_P", "MPC_XY_VEL_P_ACC", "MPC_XY_VEL_I_ACC", "MPC_XY_VEL_D_ACC", "MPC_XY_VEL_MAX",
              "MPC_ACC_HOR", "MPC_ACC_HOR_MAX", "MPC_TILTMAX_AIR", "MPC_XY_TRAJ_P", "MPC_POS_MODE", "MAV_SYS_ID")
TOPICS = ("trajectory_setpoint", "vehicle_local_position", "vehicle_local_position_setpoint", "vehicle_status")

# Palette and style() copied from scripts/make_s0_figures.py (dataviz reference slots 1-6, fixed order).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"


# ----------------------------------------------------------------------------------------------- ULog (read-only)
_PRIM = {"int8_t": "b", "uint8_t": "B", "int16_t": "h", "uint16_t": "H", "int32_t": "i", "uint32_t": "I",
         "int64_t": "q", "uint64_t": "Q", "float": "f", "double": "d", "bool": "?", "char": "c"}


def _split_type(t: str) -> tuple[str, int]:
    if t.endswith("]"):
        base, n = t[:-1].split("[")
        return base, int(n)
    return t, 1


def _size(formats: dict, name: str) -> int:
    total = 0
    for t, _ in formats[name]:
        base, n = _split_type(t)
        total += n * (struct.calcsize("<" + _PRIM[base]) if base in _PRIM else _size(formats, base))
    return total


def _layout(formats: dict, name: str) -> dict:
    """{field: (byte offset, struct char)} for the primitive fields of a format; arrays as field[i]."""
    out, off = {}, 0
    for t, field in formats[name]:
        base, n = _split_type(t)
        size = struct.calcsize("<" + _PRIM[base]) if base in _PRIM else _size(formats, base)
        if base in _PRIM and base != "char" and not field.startswith("_padding"):
            if n == 1:
                out[field] = (off, _PRIM[base])
            else:
                for i in range(n):
                    out[f"{field}[{i}]"] = (off + i * size, _PRIM[base])
        off += n * size
    return out


def read_ulog_full(path, names):
    """(data, params, changes) from a PX4 ULog (format v1), read-only.

    data = {topic: {field: (N,) float array}} for the first instance (multi_id 0) of each named topic; array fields
    appear as `field[i]`; a field cut off the end of a message (PX4 drops trailing padding) reads NaN.
    params = {name: value} as last set (int32 parameters as int). changes = [(name, old, new)] for parameters
    changed after logging started. Unlike scripts/fit_response.py's reader, this one reads arrays and parameters.
    """
    buf = Path(path).read_bytes()
    if buf[:7] != b"ULog\x01\x12\x35":
        raise ValueError(f"{path}: not a ULog file")
    wanted = set(names)
    formats, subs, raw, params, changes = {}, {}, {n: [] for n in wanted}, {}, []
    pos, end, logging = 16, len(buf), False
    while pos + 3 <= end:
        size, kind = struct.unpack_from("<HB", buf, pos)
        body = pos + 3
        if body + size > end:
            break
        if kind == 0x46:                                    # F
            text = buf[body:body + size].decode("ascii", "replace")
            fname, flds = text.split(":", 1)
            formats[fname] = [tuple(f.split(" ", 1)) for f in flds.split(";") if f]
        elif kind == 0x41:                                  # A
            logging = True
            multi, mid = struct.unpack_from("<BH", buf, body)
            subs[mid] = (buf[body + 3:body + size].decode("ascii", "replace"), multi)
        elif kind == 0x44:                                  # D
            mid = struct.unpack_from("<H", buf, body)[0]
            sub = subs.get(mid)
            if sub is not None and sub[1] == 0 and sub[0] in wanted:
                raw[sub[0]].append(buf[body + 2:body + size])
        elif kind == 0x50:                                  # P
            klen = buf[body]
            typ, pname = buf[body + 1:body + 1 + klen].decode("ascii", "replace").split(" ", 1)
            val = buf[body + 1 + klen:body + size]
            value = struct.unpack("<i", val)[0] if typ == "int32_t" else struct.unpack("<f", val)[0]
            if logging and pname in params and params[pname] != value:
                changes.append((pname, params[pname], value))
            params[pname] = value
        pos = body + size
    data = {}
    for name, msgs in raw.items():
        if name not in formats or not msgs:
            continue
        cols = {}
        for f, (off, c) in _layout(formats, name).items():
            w = struct.calcsize("<" + c)
            cols[f] = np.array([struct.unpack_from("<" + c, msg, off)[0] if off + w <= len(msg) else np.nan
                                for msg in msgs], dtype=float)
        data[name] = cols
    return data, params, changes


# ----------------------------------------------------------------------------------------------- flight data
def _enu(north, east):
    """NED (x north, y east) -> ENU (x east, y north), stacked (N, 2)."""
    return np.stack([np.asarray(east, float), np.asarray(north, float)], axis=-1)


def load_flight(path: Path) -> dict:
    data, params, changes = read_ulog_full(path, TOPICS)
    ts, lp, sp = data["trajectory_setpoint"], data["vehicle_local_position"], data["vehicle_local_position_setpoint"]
    t0 = lp["timestamp"][0]
    sec = lambda a: (np.asarray(a) - t0) / 1e6                                          # noqa: E731
    return {
        "path": str(path), "params": params, "param_changes": changes,
        "t_sp": sec(ts["timestamp"]),
        "p_sp": _enu(ts["position[0]"], ts["position[1]"]),
        "v_ff": _enu(ts["velocity[0]"], ts["velocity[1]"]),
        "a_ff_logged": _enu(ts["acceleration[0]"], ts["acceleration[1]"]),
        "t_lp": sec(lp["timestamp"]),
        "p": _enu(lp["x"], lp["y"]), "v": _enu(lp["vx"], lp["vy"]), "a": _enu(lp["ax"], lp["ay"]),
        "height_m": -np.asarray(lp["z"], float),
        "t_lps": sec(sp["timestamp"]), "p_lps": _enu(sp["x"], sp["y"]), "v_lps": _enu(sp["vx"], sp["vy"]),
        "duration_s": float(sec(lp["timestamp"][-1])),
    }


def px4_params(f: dict) -> dict:
    return {k: (float(f["params"][k]) if k in f["params"] else None) for k in PX4_PARAMS}


def base_params(px: dict, family: str) -> m.TrajectoryParams:
    acc = px["MPC_ACC_HOR"] if px["MPC_ACC_HOR"] else math.inf
    return m.TrajectoryParams(family=family, kp_xy=px["MPC_XY_P"], tau_s=0.3, delay_s=0.05, acc_max_mps2=acc,
                              vel_max_mps=px["MPC_XY_VEL_MAX"] or 3.0, vel_p=px["MPC_XY_VEL_P_ACC"],
                              vel_i=px["MPC_XY_VEL_I_ACC"], vel_d=px["MPC_XY_VEL_D_ACC"])


def _trapz(y, x) -> float:
    """Trapezoid integral (numpy 1.26 has trapz, numpy 2 trapezoid)."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    return float(np.sum(0.5 * (y[1:] + y[:-1]) * np.diff(x)))


def _interp2(t, tp, xp):
    return np.stack([np.interp(t, tp, xp[:, 0]), np.interp(t, tp, xp[:, 1])], axis=-1)


def setpoint_on_grid(f: dict, t: np.ndarray, accel_ff: str):
    """p_sp, v_ff, a_ff (N, 2) on grid t. p_sp, v_ff: linear interpolation of the 5 Hz log. a_ff: 'derived' = slope
    of the interpolated v_ff (its integral equals the logged change of v_ff), 'logged' = the logged acceleration
    held (aliased: the commander's ramp lasts 0.1 s, the log samples every 0.2 s), 'none' = zeros."""
    p_sp = _interp2(t, f["t_sp"], f["p_sp"])
    v_ff = _interp2(t, f["t_sp"], f["v_ff"])
    if accel_ff == "derived":
        a_ff = np.gradient(v_ff, t, axis=0)
    elif accel_ff == "logged":
        idx = np.clip(np.searchsorted(f["t_sp"], t, side="right") - 1, 0, len(f["t_sp"]) - 1)
        a_ff = f["a_ff_logged"][idx]
    else:
        a_ff = np.zeros_like(v_ff)
    return p_sp, v_ff, a_ff


def make_windows(f: dict, accel_ff: str):
    """Legs (time order) and one model Window per leg; legs not airborne for the whole window are dropped."""
    legs = m.find_legs(f["t_sp"], f["v_ff"], on_mps=0.1, min_len_s=0.6, merge_gap_s=1.0)
    keep = []
    for s, e in legs:
        a, b = s - PRE_S, e + POST_S
        inside = (f["t_lp"] >= a) & (f["t_lp"] <= b)
        if inside.any() and f["height_m"][inside].min() > AIRBORNE_M and a > f["t_sp"][0] and b < f["t_sp"][-1]:
            keep.append((s, e))
    windows, meta = [], []
    for i, (s, e) in enumerate(keep):
        lo = s - PRE_S if i == 0 else max(s - PRE_S, 0.5 * (keep[i - 1][1] + s))
        hi = e + POST_S if i == len(keep) - 1 else min(e + POST_S, 0.5 * (e + keep[i + 1][0]))
        j = np.flatnonzero((f["t_lp"] >= lo) & (f["t_lp"] <= hi))
        t0 = f["t_lp"][j[0]]
        n = int(round((f["t_lp"][j[-1]] - t0) / DT_S)) + 1
        t = t0 + np.arange(n) * DT_S
        p_sp, v_ff, a_ff = setpoint_on_grid(f, t, accel_ff)
        idx = np.clip(np.round((f["t_lp"][j] - t0) / DT_S).astype(int), 0, n - 1)
        windows.append(m.Window(t_s=t, p_sp=p_sp, v_ff=v_ff, a_ff=a_ff, p0=f["p"][j[0]].copy(),
                                v0=f["v"][j[0]].copy(), meas_idx=idx, v_meas=f["v"][j].copy(),
                                label=f"leg {i}", a0=f["a"][j[0]].copy()))
        meta.append({"leg": i, "start_s": round(s, 2), "end_s": round(e, 2), "window_s": [round(lo, 2), round(hi, 2)]})
    return windows, meta


# ----------------------------------------------------------------------------------------------- checks
def position_law_check(f: dict, kp: float) -> dict:
    """PX4's logged velocity setpoint against v_ff + K (p_sp - p): K by least squares over the airborne flight."""
    t = f["t_lps"]
    ok = (t > f["t_sp"][0]) & (t < f["t_sp"][-1]) & np.isfinite(f["v_lps"]).all(axis=1)
    ok &= np.interp(t, f["t_lp"], f["height_m"]) > AIRBORNE_M
    v_ff = _interp2(t[ok], f["t_sp"], f["v_ff"])
    err = f["p_lps"][ok] - _interp2(t[ok], f["t_lp"], f["p"])
    r = f["v_lps"][ok] - v_ff
    k_ls = float(np.sum(err * r) / np.sum(err * err))
    return {"k_least_squares": k_ls, "mpc_xy_p": kp, "samples": int(ok.sum()),
            "rms_residual_at_mpc_xy_p_mps": float(np.sqrt(np.mean((r - kp * err) ** 2))),
            "rms_without_p_term_mps": float(np.sqrt(np.mean(r ** 2))),
            "_err": err, "_r": r}


def clock_ratio(f: dict, legs_meta) -> dict:
    """Per leg: reference-point travel over the integral of the velocity setpoint, along the leg (1.0 = sigma 1)."""
    ratios = []
    for leg in legs_meta:
        a, b = leg["start_s"] - 0.6, leg["end_s"] + 0.6
        t = np.arange(a, b, DT_S)
        v = _interp2(t, f["t_sp"], f["v_ff"])
        u = v.mean(axis=0)
        if np.linalg.norm(u) < 0.05:
            continue
        u = u / np.linalg.norm(u)
        p = _interp2(np.array([a, b]), f["t_sp"], f["p_sp"])
        travel = float((p[1] - p[0]) @ u)
        integral = float(_trapz(v @ u, t))
        if integral > 0.2:
            ratios.append(travel / integral)
    return {"per_leg": [round(r, 3) for r in ratios], "median": float(np.median(ratios)) if ratios else math.nan}


# ----------------------------------------------------------------------------------------------- step metrics
def leg_changes(w: m.Window, v_model: np.ndarray) -> list[dict]:
    """t63 for the start and the stop of a leg along its main direction: setpoint, measured, model."""
    t = w.t_s
    u = w.v_ff.mean(axis=0)
    if np.linalg.norm(u) < 1e-6:
        return []
    u = u / np.linalg.norm(u)
    sp = w.v_ff @ u
    peak = sp.max()
    on = np.flatnonzero(sp > 0.5 * peak)
    if peak < PLATEAU_MIN_MPS or on.size == 0:
        return []
    plateau = float(np.median(sp[on]))
    t_meas = t[w.meas_idx]
    meas = w.v_meas @ u
    mod = v_model @ u
    rows = []
    # start: from the last time the setpoint was below 5 % of the plateau before the leg
    k_on = int(np.flatnonzero(sp[:on[0] + 1] < 0.05 * plateau)[-1]) if (sp[:on[0] + 1] < 0.05 * plateau).any() else 0
    before = t_meas <= t[k_on]
    level0 = float(np.mean(meas[before][-3:])) if before.any() else 0.0
    # stop: from the last time the setpoint was above 95 % of the plateau
    k_off = int(on[-1])
    hi = np.flatnonzero(sp[:k_off + 1] > 0.95 * plateau)
    k_off = int(hi[-1]) if hi.size else k_off
    held = (t_meas >= t[k_off] - 0.5) & (t_meas <= t[k_off])
    level_held = float(np.mean(meas[held])) if held.any() else plateau
    for kind, k0, l0, l1 in (("start", k_on, level0, plateau), ("stop", k_off, level_held, 0.0)):
        t_on = t[k0]
        row = {"change": kind, "from_mps": round(l0, 3), "to_mps": round(l1, 3),
               "t63_setpoint_s": m.time_to_63pct(t, sp, l0, l1, t_on),
               "t63_measured_s": m.time_to_63pct(t_meas, meas, l0, l1, t_on),
               "t63_model_s": m.time_to_63pct(t, mod, l0, l1, t_on)}
        rows.append(row)
    return rows


def leg_rms(params, windows):
    return [m.velocity_rms(params, [w]) for w in windows]


def sensitivity(params, windows, names):
    """Change of the training RMS (m/s) when each fitted parameter is raised by 25 % (time parameters by at least
    0.05 s, so a value at its lower bound is still probed by a step that matters)."""
    base = m.velocity_rms(params, windows)
    out = {}
    for n in names:
        v = getattr(params, n)
        bumped = m.replace(params, **{n: max(v * 1.25, v + 0.05) if n.endswith("_s") else v * 1.25})
        out[n] = m.velocity_rms(bumped, windows) - base
    return out


# ----------------------------------------------------------------------------------------------- simulator data
def _csv(path: Path) -> dict:
    with open(path) as fh:
        head = fh.readline().strip().split(",")
    arr = np.loadtxt(path, delimiter=",", skiprows=1, ndmin=2)
    return {h: arr[:, i] for i, h in enumerate(head)}


def sim_pushes(extract: Path) -> list[dict]:
    """AirStack simulator teleop pushes (wall clock), each as fractions of its stick along the push direction."""
    tc, vc, od = (_csv(extract / f"{n}.csv") for n in ("teleop_command", "velocity_command", "odometry"))
    stick = np.stack([tc["vx"], tc["vy"]], axis=1)
    v_body = np.stack([od["vx"], od["vy"], od["vz"]], axis=1)
    q = np.stack([od["qw"], od["qx"], od["qy"], od["qz"]], axis=1)
    v_world = body_to_world(v_body, q)[:, :2]
    legs = m.find_legs(tc["t_wall_s"], stick, on_mps=0.1, min_len_s=0.6, merge_gap_s=0.5)
    out = []
    for s, e in legs:
        on = (tc["t_wall_s"] >= s) & (tc["t_wall_s"] <= e)
        u = stick[on].mean(axis=0)
        mag = float(np.linalg.norm(u))
        u = u / mag
        t_rel = lambda a: a - s                                                            # noqa: E731
        win = lambda a: (a >= s - 1.0) & (a <= e + 4.0)                                    # noqa: E731
        k_od, k_vc, k_tc = win(od["t_wall_s"]), win(vc["t_wall_s"]), win(tc["t_wall_s"])
        meas = v_world[k_od] @ u / mag
        t_od = t_rel(od["t_wall_s"][k_od])
        held = (t_od >= 0) & (t_od <= e - s)
        after = t_od > e - s
        out.append({"t_od": t_od, "v": meas,
                    "t_vc": t_rel(vc["t_wall_s"][k_vc]),
                    "u_cmd": np.stack([vc["vx"], vc["vy"]], axis=1)[k_vc] @ u / mag,
                    "t_tc": t_rel(tc["t_wall_s"][k_tc]), "stick": stick[k_tc] @ u / mag,
                    "hold_s": e - s, "stick_mps": mag,
                    "peak": float(meas[held].max()), "at_release": float(np.interp(e - s, t_od, meas)),
                    "min_after": float(meas[after].min()),
                    "moved_m": float((np.array([od["x"][k_od][-1], od["y"][k_od][-1]])
                                      - np.array([od["x"][k_od][0], od["y"][k_od][0]])) @ u),
                    "stick_x_time_m": float(mag * (e - s))})
    return out


def real_leg_fractions(w: m.Window, v_model: np.ndarray) -> dict:
    u = w.v_ff.mean(axis=0)
    u = u / np.linalg.norm(u)
    sp = w.v_ff @ u
    plateau = float(np.median(sp[sp > 0.5 * sp.max()]))
    on = np.flatnonzero(sp > 0.5 * plateau)
    t_start = w.t_s[on[0]]
    t_stop = w.t_s[on[-1]]
    t_meas = w.t_s[w.meas_idx] - t_start
    meas = (w.v_meas @ u) / plateau
    held = (t_meas >= 0) & (t_meas <= t_stop - t_start)
    after = t_meas > t_stop - t_start
    before = t_meas < 0
    return {"start_level": float(np.mean(meas[before][-3:])) if before.any() else math.nan,
            "t": w.t_s - t_start, "sp": sp / plateau, "t_meas": t_meas, "meas": meas,
            "model": (v_model @ u) / plateau, "plateau_mps": plateau, "hold_s": float(t_stop - t_start),
            "peak": float(meas[held].max()), "at_release": float(np.interp(t_stop - t_start, t_meas, meas)),
            "min_after": float(meas[after].min()) if after.any() else math.nan,
            "model_peak": float(((v_model @ u) / plateau)[w.meas_idx][held].max()),
            "model_min_after": float(((v_model @ u) / plateau)[w.meas_idx][after].min()) if after.any() else math.nan}


# ----------------------------------------------------------------------------------------------- figures
def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def style(ax, title, xlabel, ylabel):
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=10)
    ax.set_xlabel(xlabel, color=INK2)
    ax.set_ylabel(ylabel, color=INK2)
    ax.grid(True, which="major", color=GRID, linewidth=0.8)
    ax.tick_params(colors=INK2)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)


def fig_held_out(windows, held, params, out):
    plt = _plt()
    cols = 3
    rows = math.ceil(len(held) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(13, 3.4 * rows), dpi=150, squeeze=False)
    for ax in axes.flat[len(held):]:
        ax.set_visible(False)
    for ax, i in zip(axes.flat, held):
        w = windows[i]
        u = w.v_ff.mean(axis=0)
        u = u / np.linalg.norm(u)
        t = w.t_s - w.t_s[0]
        ax.plot(t, w.v_ff @ u, color=SERIES[3], linewidth=1.6, label="setpoint velocity (5 Hz log, joined)")
        ax.plot(t[w.meas_idx], w.v_meas @ u, "o", color=SERIES[0], markersize=3.5, label="measured (10 Hz)")
        ax.plot(t, m.simulate_window(params, w) @ u, color=SERIES[1], linewidth=1.8, label="model")
        rms = m.velocity_rms(params, [w])
        style(ax, f"{w.label} (held out): RMS {rms:.3f} m/s", "time in window (s)", "speed along the leg (m/s)")
    axes.flat[0].legend(frameon=False, fontsize=8, loc="upper right", labelcolor=INK)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_model_error(windows, train, held, params, out):
    plt = _plt()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.6), dpi=150, gridspec_kw={"width_ratios": [1.6, 1]})
    for n, i in enumerate(held):
        w = windows[i]
        err = m.simulate_window(params, w)[w.meas_idx] - w.v_meas
        t = w.t_s[w.meas_idx] - w.t_s[0]
        a1.plot(t, np.linalg.norm(err, axis=1), color=SERIES[n % len(SERIES)], linewidth=1.3, label=w.label)
    style(a1, "Held-out legs: size of the model's velocity error", "time in window (s)", "|model - measured| (m/s)")
    a1.legend(frameon=False, fontsize=8, ncol=2, labelcolor=INK)
    rms = leg_rms(params, windows)
    colours = [SERIES[0] if i in train else SERIES[1] for i in range(len(windows))]
    a2.bar(range(len(windows)), rms, color=colours)
    a2.set_xticks(range(len(windows)), [str(i) for i in range(len(windows))])
    style(a2, "RMS per leg (blue = training, orange = held out)", "leg", "velocity RMS per axis (m/s)")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_position_law(check, out):
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.4, 5.2), dpi=150)
    e, r = check["_err"].ravel(), check["_r"].ravel()
    ax.plot(e, r, "o", color=SERIES[0], markersize=2.2, alpha=0.5, label="logged, both axes (10 Hz)")
    x = np.linspace(e.min(), e.max(), 2)
    ax.plot(x, check["mpc_xy_p"] * x, color=SERIES[1], linewidth=2,
            label=f"MPC_XY_P = {check['mpc_xy_p']:.2f} (from the log)")
    style(ax, "PX4's position law, seen in the log", "position setpoint - position (m)",
          "PX4 velocity setpoint - feed-forward (m/s)")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_sim_vs_real(real, sims, out):
    plt = _plt()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.8), dpi=150, sharey=True)
    a1.plot(real["t"], real["sp"], color=SERIES[3], linewidth=1.6, label="setpoint velocity (ramped stick)")
    a1.plot(real["t_meas"], real["meas"], "o", color=SERIES[0], markersize=3.5, label="measured")
    a1.plot(real["t"], real["model"], color=SERIES[1], linewidth=1.8, label="model (held out)")
    style(a1, f"Real drone, trajectory route, PX4 1.14: {real['plateau_mps']:.2f} m/s", "time since the push (s)",
          "velocity / commanded speed")
    a1.legend(frameon=False, fontsize=8, labelcolor=INK)
    s = sims[0]
    a2.step(s["t_tc"], s["stick"], where="post", color=SERIES[3], linewidth=1.6, label="stick (policy's command)")
    a2.plot(s["t_vc"], s["u_cmd"], color=SERIES[4], linewidth=1.4, label="commander output to PX4")
    a2.plot(s["t_od"], s["v"], color=SERIES[0], linewidth=1.6, label="measured")
    style(a2, f"AirStack simulator, velocity-only route, PX4 1.16.1: {s['stick_mps']:.2f} m/s",
          "wall-clock time since the push (s)", "")
    a2.legend(frameon=False, fontsize=8, labelcolor=INK)
    for ax in (a1, a2):
        ax.axhline(0, color=INK2, linewidth=0.8)
        ax.set_xlim(-1, 6)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


# ----------------------------------------------------------------------------------------------- main
def _clean(x):
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items() if not str(k).startswith("_")}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if not math.isfinite(float(x)) else round(float(x), 4)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, m.TrajectoryParams):
        return _clean(x.to_dict())
    return x


def setpoint_as_speed(w: m.Window, delay_s: float) -> np.ndarray:
    """Naive baseline (N, 2): the drone flies exactly the feed-forward speed of its setpoint, delay_s later."""
    return m.delay_signal(w.v_ff, float(w.t_s[1] - w.t_s[0]), delay_s)


def active_mask(w: m.Window, leg: dict, after_s: float = 1.0) -> np.ndarray:
    """Measurement samples between the leg's start and its end + after_s (the pre-roll and the tail dropped)."""
    t = w.t_s[w.meas_idx]
    return (t >= leg["start_s"]) & (t <= leg["end_s"] + after_s)


def rms_of(preds, windows, masks=None) -> float:
    """RMS per axis of preds[i][meas_idx] - v_meas over the windows (optionally only where masks[i])."""
    errs = []
    for i, (p, w) in enumerate(zip(preds, windows)):
        e = p[w.meas_idx] - w.v_meas
        if masks is not None:
            e = e[masks[i]]
        errs.append(e[np.isfinite(e)])
    e = np.concatenate(errs)
    return float(np.sqrt(np.mean(e ** 2))) if e.size else math.nan


def fit_family(windows, train, held, px, family, accel_ff):
    start = base_params(px, family)
    if accel_ff == "none":
        start = m.replace(start, ff_gain=0.0)
    free = ("tau_s", "delay_s", "acc_max_mps2") if family == "lag1" else ("tau_s", "delay_s")
    got, info = m.fit([windows[i] for i in train], start, free=free)
    return {"params": got, "free": free, "train_rms_mps": info["train_rms_mps"],
            "held_out_rms_mps": m.velocity_rms(got, [windows[i] for i in held]),
            "delay_profile": info["delay_profile"], "nfev": info["nfev"],
            "sensitivity_mps": sensitivity(got, [windows[i] for i in train], free)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ulog", type=Path, default=MAIN_LOG)
    ap.add_argument("--cross", type=Path, nargs="*", default=list(CROSS_LOGS))
    ap.add_argument("--sim-extract", type=Path, default=SIM_EXTRACT)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "runs/2026-11-15_s1_real_px4_exploratory")
    ap.add_argument("--fig-prefix", default=str(ROOT / "docs/figures/s1_real"))
    ap.add_argument("--accel-ff", choices=("derived", "logged", "none"), default="derived",
                    help="windows built first; the source actually kept is chosen on the training legs")
    a = ap.parse_args(argv)
    try:
        f = load_flight(a.ulog)
    except (OSError, ValueError, KeyError) as exc:
        print(f"cannot read {a.ulog}: {exc}", file=sys.stderr)
        return 1
    a.out_dir.mkdir(parents=True, exist_ok=True)
    px = px4_params(f)
    windows, meta = make_windows(f, a.accel_ff)
    if len(windows) < 2:
        print("fewer than two legs", file=sys.stderr)
        return 2
    train, held = m.split_alternate(len(windows))
    (a.out_dir / "split.json").write_text(json.dumps({"log": str(a.ulog), "legs": meta, "train": train,
                                                      "held_out": held}, indent=1))
    print(f"{len(windows)} legs; train {train}; held out {held} (split written before fitting)")

    law = position_law_check(f, px["MPC_XY_P"])
    clock = clock_ratio(f, meta)
    # Every choice (family, feed-forward source, variants) is made on the TRAINING legs only; held-out RMS is
    # reported beside it, never used to choose (fix round 1, review item I5).
    by_ff = {a.accel_ff: (windows, meta)}
    for ff in ("derived", "logged", "none"):
        by_ff.setdefault(ff, make_windows(f, ff))
    combos = {(fam, ff): fit_family(by_ff[ff][0], train, held, px, fam, ff)
              for fam in m.FAMILIES for ff in ("derived", "logged", "none")}
    kept, kept_ff = min(combos, key=lambda k: combos[k]["train_rms_mps"])
    windows, meta = by_ff[kept_ff]
    fits = {fam: combos[(fam, kept_ff)] for fam in m.FAMILIES}
    best = fits[kept]["params"]
    variants = {f"{fam}, accel_ff={ff}": {"params": r["params"], "train_rms_mps": r["train_rms_mps"],
                                           "held_out_rms_mps": r["held_out_rms_mps"]}
                for (fam, ff), r in combos.items()}
    for name, acc in (("no acceleration limit", math.inf), ("acceleration limit = MPC_ACC_HOR", px["MPC_ACC_HOR"])):
        alt = m.replace(best, acc_max_mps2=acc)
        variants[name] = {"params": alt, "train_rms_mps": m.velocity_rms(alt, [windows[i] for i in train]),
                          "held_out_rms_mps": m.velocity_rms(alt, [windows[i] for i in held])}
    for tau in (0.05, 0.1):
        alt = m.replace(best, tau_s=tau)
        variants[f"tau_s = {tau} (delay kept)"] = {
            "params": alt, "train_rms_mps": m.velocity_rms(alt, [windows[i] for i in train]),
            "held_out_rms_mps": m.velocity_rms(alt, [windows[i] for i in held])}
    wt, wh = [windows[i] for i in train], [windows[i] for i in held]
    mh = [active_mask(windows[i], meta[i]) for i in held]
    mt = [active_mask(windows[i], meta[i]) for i in train]
    candidates = {f"model ({kept}, kept)": lambda w: m.simulate_window(best, w),
                  "baseline: setpoint speed, no lag": lambda w: setpoint_as_speed(w, 0.0),
                  f"baseline: setpoint speed, {best.delay_s:.3f} s later": lambda w: setpoint_as_speed(w, best.delay_s)}
    for fam in m.FAMILIES:
        if fam != kept:
            candidates[f"model ({fam}, not kept)"] = (lambda p: lambda w: m.simulate_window(p, w))(fits[fam]["params"])
    scores = {}
    for name, fn in candidates.items():
        pt, ph = [fn(w) for w in wt], [fn(w) for w in wh]
        scores[name] = {"train_rms_mps": rms_of(pt, wt), "held_out_rms_mps": rms_of(ph, wh),
                        "held_out_active_rms_mps": rms_of(ph, wh, mh), "train_active_rms_mps": rms_of(pt, wt, mt)}
    sims = sim_pushes(a.sim_extract) if (a.sim_extract / "teleop_command.csv").exists() else []

    changes = []
    for i, w in enumerate(windows):
        for row in leg_changes(w, m.simulate_window(best, w)):
            changes.append({"leg": i, "held_out": i in held, **row})
    t63 = {}
    for kind in ("start", "stop"):
        rows = [c for c in changes if c["change"] == kind and c["held_out"]]
        for key in ("t63_setpoint_s", "t63_measured_s", "t63_model_s"):
            vals = [c[key] for c in rows if c[key] is not None and math.isfinite(c[key])]
            t63[f"{kind}_{key}_median"] = float(np.median(vals)) if vals else math.nan
        lag = [c["t63_measured_s"] - c["t63_setpoint_s"] for c in rows]
        t63[f"{kind}_drone_behind_setpoint_s_median"] = float(np.nanmedian(lag)) if lag else math.nan
        t63[f"{kind}_count"] = len(rows)
    leg_table = [{"leg": i, "held_out": i in held, **meta[i], "rms_mps": r}
                 for i, r in enumerate(leg_rms(best, windows))]

    cross = []
    for path in a.cross:
        try:
            g = load_flight(path)
        except (OSError, ValueError, KeyError) as exc:
            cross.append({"log": str(path), "error": str(exc)})
            continue
        gx = px4_params(g)
        wg, mg = make_windows(g, kept_ff)
        if not wg:
            cross.append({"log": str(path), "px4": gx, "legs": 0})
            continue
        transfer = m.replace(best, kp_xy=gx["MPC_XY_P"], vel_p=gx["MPC_XY_VEL_P_ACC"],
                             vel_i=gx["MPC_XY_VEL_I_ACC"], vel_d=gx["MPC_XY_VEL_D_ACC"])
        tr2, _h2 = m.split_alternate(len(wg))
        refit = fit_family(wg, tr2, _h2, gx, kept, kept_ff) if len(wg) >= 2 else None
        cross.append({"log": str(path), "px4": gx, "legs": len(wg), "leg_spans": mg,
                      "rms_kept_params_all_legs_mps": m.velocity_rms(transfer, wg),
                      "rms_per_leg_mps": leg_rms(transfer, wg),
                      "refit_even_legs": None if refit is None else {
                          "params": refit["params"], "train_rms_mps": refit["train_rms_mps"],
                          "held_out_rms_mps": refit["held_out_rms_mps"]},
                      "position_law": position_law_check(g, gx["MPC_XY_P"])})

    # the real leg shown beside the simulator: the held-out leg with the highest plateau and the longest hold
    cands = [(i, real_leg_fractions(windows[i], m.simulate_window(best, windows[i]))) for i in held]
    held_fractions = [{"leg": i, **{k: v for k, v in c.items() if not isinstance(v, np.ndarray)}} for i, c in cands]
    cands = [c for c in cands if c[1]["plateau_mps"] >= 0.4 and abs(c[1]["start_level"]) < 0.15] or cands
    show_i, show = max(cands, key=lambda c: (round(c[1]["plateau_mps"], 1), c[1]["hold_s"]))
    ws = windows[show_i]
    u = ws.v_ff.mean(axis=0) / np.linalg.norm(ws.v_ff.mean(axis=0))
    ends = _interp2(ws.t_s[[0, -1]], f["t_lp"], f["p"])
    show["moved_m"] = float((ends[1] - ends[0]) @ u)
    show["setpoint_integral_m"] = _trapz(ws.v_ff @ u, ws.t_s)

    pre = a.fig_prefix
    Path(pre).parent.mkdir(parents=True, exist_ok=True)
    fig_held_out(windows, held, best, f"{pre}_held_out.png")
    fig_model_error(windows, train, held, best, f"{pre}_model_error.png")
    fig_position_law(law, f"{pre}_position_law.png")
    if sims:
        fig_sim_vs_real(show, sims, f"{pre}_sim_vs_real.png")

    results = {
        "log": str(a.ulog), "duration_s": f["duration_s"], "px4_parameters": px,
        "param_changes_in_flight": f["param_changes"],
        "position_law": law, "clock_ratio": clock, "legs": leg_table, "split": {"train": train, "held_out": held},
        "fits": fits, "kept_family": kept, "kept_accel_ff": kept_ff, "selection": "lowest training RMS",
        "scores": scores, "held_out_fractions": held_fractions, "variants": variants, "changes_t63": changes, "t63_held_out_summary": t63, "cross_check": cross,
        "sim_vs_real": {"real_leg": show_i, "real": {k: v for k, v in show.items() if not isinstance(v, np.ndarray)},
                        "sim_pushes": [{k: v for k, v in s.items() if not isinstance(v, np.ndarray)}
                                       for s in sims]},
    }
    (a.out_dir / "results.json").write_text(json.dumps(_clean(results), indent=1))
    lines = ["# Exploratory, not a run of record: no gates applied, no ledger row.",
             f"# Real-drone response model ({kept}), fitted by scripts/fit_real_px4.py to {a.ulog}", "[params]"]
    lines += [f"{k} = {json.dumps(_clean(v))}" for k, v in best.to_dict().items()]
    (a.out_dir / "real_exploratory.toml").write_text("\n".join(lines).replace("null", "inf") + "\n")

    print(json.dumps(_clean({"px4": px, "position_law": law, "clock": clock,
                             "fits": {k: {kk: v[kk] for kk in ("params", "train_rms_mps", "held_out_rms_mps",
                                                               "sensitivity_mps", "delay_profile")}
                                      for k, v in fits.items()},
                             "kept": kept, "kept_ff": kept_ff, "scores": scores,
                             "held_fractions": held_fractions, "variants": variants, "t63": t63,
                             "cross": [{k: c.get(k) for k in ("log", "legs", "rms_kept_params_all_legs_mps",
                                                               "refit_even_legs")} for c in cross],
                             "sim_vs_real": results["sim_vs_real"]}), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
