#!/usr/bin/env python3
"""Held-out check of the exploratory drone model against the 12 November real-flight rosbag. No refit.

Usage (from svg_training/):
    python scripts/bag_check.py --bag ~/flight_logs/2026-11-12/svg_20261112_094546 \
        --params params/real_exploratory_v0.toml --gates configs/s2.toml --name 2026-11-15_s2_bag_check

What it does
  1. Reads, from the bag's mcap file (read-only, pure-Python reader in svg_training.logs), for drone_1 and drone_2:
     /drone_N/fmu/in/trajectory_setpoint (position, velocity, acceleration; what the commander sent) and
     /drone_N/fmu/out/vehicle_local_position (x, y, vx, vy; what PX4 measured). The message layouts are compiled from
     the schemas stored in the bag itself. PX4's NED axes become ENU (x east = NED y, y north = NED x), as in
     scripts/fit_real_px4.py.
  2. Time base: the bag's own log time. The measured velocity crosses the WiFi to the laptop before it is logged, so
     its apparent delay includes one network leg; the setpoint is logged on the laptop as it is sent.
  3. Legs: spans where the setpoint speed is above 0.1 m/s (px4_trajectory.find_legs); each in a window from 1.0 s
     before to 2.5 s after, cut at the midpoint to its neighbours (as the S1 fit). The setpoint is held onto a
     0.01 s grid; the acceleration feed-forward is derived from the speed setpoint ("derived", as the model was
     fitted). As in the S1 fit, a leg counts only if the drone stays above 0.3 m for the whole window (takeoff,
     landing and legs on the ground are not flights); the result with every leg is reported beside it, information
     only (results.json "all_legs_sensitivity").
  4. The model is px4_trajectory.simulate_windows with the [px4] table of the parameter file AS WRITTEN. Nothing is
     fitted anywhere in this script.
  5. Per leg: RMS velocity error over the active span (leg start to leg end + 1 s), error of the time to 63 % of the
     change at the start and at the stop of the leg, and two baselines (the setpoint speed itself, and the same
     0.15 s later). Information only: the extra shift in [-0.10, 0.30] s that would minimise the RMS.
  6. Gates (configs/s2.toml [bag_check_gates]) apply to drone_2; drone_1 is reported. Fewer legs than min_legs = INFO.
  7. Writes runs/<name>/results.json (and gates.toml, params copy), docs/figures/s2_bag_check.png, a record
     records/<name>_record.md and a row in records/LEDGER.md (next free T number).
Exit codes: 0 done; 1 unreadable input; 2 bad arguments.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import re
import shutil
import sys
import tomllib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from svg_training.logs.cdr import compile_ros2msg, decode  # noqa: E402
from svg_training.logs.mcap_reader import iter_messages, list_topics  # noqa: E402
from svg_training.models import px4_trajectory as m  # noqa: E402

DT_S = 0.01
PRE_S, POST_S = 1.0, 2.5
ACTIVE_AFTER_S = 1.0
DELAY_BASELINE_S = 0.15
SHIFTS_S = np.round(np.arange(-0.10, 0.3001, 0.01), 2)
MIN_MEAS = 10
SP_FIELDS = ("position", "velocity", "acceleration")
LP_FIELDS = ("x", "y", "z", "vx", "vy")
AIRBORNE_M = 0.3                      # S1 fit rule: a leg counts only if the drone is above this the whole window
DRONES = ("drone_1", "drone_2")
CAPTION_MAX = 400


def _enu(north, east) -> np.ndarray:
    """NED (x north, y east) -> ENU (x east, y north), stacked (N, 2)."""
    return np.stack([np.asarray(east, float), np.asarray(north, float)], axis=-1)


def find_mcap(bag: Path) -> Path:
    if bag.is_file():
        return bag
    files = sorted(bag.glob("*.mcap"))
    if len(files) != 1:
        raise FileNotFoundError(f"{bag}: expected exactly one .mcap file, found {len(files)}")
    return files[0]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


# ------------------------------------------------------------------------------------------------ reading the bag
def load_bag(mcap_path: Path) -> dict:
    """{drone: {t_sp, p_sp, v_ff, a_ff_logged, t_lp, p, v, height_m}} in bag seconds (ENU); drones without both topics are
    left out. t = 0 is the first message of any of the topics read."""
    topics = list_topics(mcap_path)
    wanted, layouts = {}, {}
    for d in DRONES:
        for kind, topic in (("sp", f"/{d}/fmu/in/trajectory_setpoint"), ("lp", f"/{d}/fmu/out/vehicle_local_position")):
            if topic in topics:
                wanted[topic] = (d, kind)
                layouts[topic] = compile_ros2msg(topics[topic][1])
    raw: dict[tuple[str, str], list] = {}
    for msg in iter_messages(mcap_path, set(wanted)):
        d, kind = wanted[msg.topic]
        fields = SP_FIELDS if kind == "sp" else LP_FIELDS
        got = decode(layouts[msg.topic], msg.data, fields)
        row = ([got["position"][:2], got["velocity"][:2], got["acceleration"][:2]] if kind == "sp"
               else [(got["x"], got["y"]), (got["vx"], got["vy"]), (-got["z"], 0.0)])
        raw.setdefault((d, kind), []).append((msg.log_time_ns, row))
    if not raw:
        return {}
    t_ref = min(rows[0][0] for rows in raw.values())
    out: dict[str, dict] = {}
    for d in DRONES:
        if (d, "sp") not in raw or (d, "lp") not in raw:
            continue
        sp, lp = raw[(d, "sp")], raw[(d, "lp")]
        t_sp = np.array([(t - t_ref) * 1e-9 for t, _ in sp])
        t_lp = np.array([(t - t_ref) * 1e-9 for t, _ in lp])
        col = lambda rows, i: np.array([r[i] for _, r in rows], dtype=float)           # noqa: E731
        out[d] = {"t_sp": t_sp,
                  "p_sp": _enu(col(sp, 0)[:, 0], col(sp, 0)[:, 1]),
                  "v_ff": _enu(col(sp, 1)[:, 0], col(sp, 1)[:, 1]),
                  "a_ff_logged": _enu(col(sp, 2)[:, 0], col(sp, 2)[:, 1]),
                  "t_lp": t_lp,
                  "p": _enu(col(lp, 0)[:, 0], col(lp, 0)[:, 1]),
                  "v": _enu(col(lp, 1)[:, 0], col(lp, 1)[:, 1]),
                  "height_m": col(lp, 2)[:, 0]}
    return out


# ------------------------------------------------------------------------------------------------ windows
def hold_to_grid(t_sp: np.ndarray, x: np.ndarray, t: np.ndarray) -> np.ndarray:
    """x (N, 2) at message times t_sp, held (zero-order) onto the grid t: the latest message at or before t."""
    idx = np.clip(np.searchsorted(t_sp, t, side="right") - 1, 0, len(t_sp) - 1)
    return x[idx]


def interp_to_grid(t_sp: np.ndarray, x: np.ndarray, t: np.ndarray) -> np.ndarray:
    """x (N, 2) at message times t_sp, joined linearly onto the grid t (what the S1 fit did with its 5 Hz log)."""
    return np.stack([np.interp(t, t_sp, x[:, 0]), np.interp(t, t_sp, x[:, 1])], axis=-1)


def make_windows(f: dict, airborne_only: bool = True, setpoint: str = "hold") -> tuple[list[m.Window], list[dict], list[np.ndarray], int]:
    """(windows, legs meta, exact measurement times per window, legs skipped). Feed-forward acceleration derived.

    setpoint: "hold" (the brief and the run of record: the latest message held on the grid) or "linear" (messages
    joined by straight lines, as the S1 fit did; information only).
    airborne_only (the S1 fit's rule, scripts/fit_real_px4.py make_windows): a leg is kept only if the drone's
    height stays above AIRBORNE_M for the whole window and the window lies inside the setpoint stream. Takeoff,
    landing and legs flown on the ground are then not scored against a flight model."""
    v_speed = np.nan_to_num(f["v_ff"], nan=0.0)
    legs = m.find_legs(f["t_sp"], v_speed, on_mps=0.1, min_len_s=0.6, merge_gap_s=1.0)
    ok = (np.isfinite(f["t_lp"]) & np.isfinite(f["p"]).all(axis=1) & np.isfinite(f["v"]).all(axis=1)
          & np.isfinite(f["height_m"]))
    t_lp, p_lp, v_lp, h_lp = f["t_lp"][ok], f["p"][ok], f["v"][ok], f["height_m"][ok]
    windows, meta, times, skipped = [], [], [], 0
    for i, (s, e) in enumerate(legs):
        lo = s - PRE_S if i == 0 else max(s - PRE_S, 0.5 * (legs[i - 1][1] + s))
        hi = e + POST_S if i == len(legs) - 1 else min(e + POST_S, 0.5 * (e + legs[i + 1][0]))
        j = np.flatnonzero((t_lp >= lo) & (t_lp <= hi))
        if j.size < MIN_MEAS:
            skipped += 1
            continue
        if airborne_only and not (h_lp[j].min() > AIRBORNE_M and lo > f["t_sp"][0] and hi < f["t_sp"][-1]):
            skipped += 1
            continue
        t0 = t_lp[j[0]]
        n = int(round((t_lp[j[-1]] - t0) / DT_S)) + 1
        t = t0 + np.arange(n) * DT_S
        to_grid = hold_to_grid if setpoint == "hold" else interp_to_grid
        p_sp = to_grid(f["t_sp"], f["p_sp"], t)
        v_ff = to_grid(f["t_sp"], v_speed, t)
        if not np.isfinite(p_sp).all():
            skipped += 1
            continue
        a_ff = np.gradient(v_ff, t, axis=0)
        idx = np.clip(np.round((t_lp[j] - t0) / DT_S).astype(int), 0, n - 1)
        windows.append(m.Window(t_s=t, p_sp=p_sp, v_ff=v_ff, a_ff=a_ff, p0=p_lp[j[0]].copy(), v0=v_lp[j[0]].copy(),
                                meas_idx=idx, v_meas=v_lp[j].copy(), label=f"leg {len(windows)}"))
        meta.append({"leg": len(windows) - 1, "start_s": round(s, 2), "end_s": round(e, 2),
                     "window_s": [round(lo, 2), round(hi, 2)]})
        times.append(t_lp[j])
    return windows, meta, times, skipped


# ------------------------------------------------------------------------------------------------ scoring
def _at(t_grid: np.ndarray, v: np.ndarray, t_query: np.ndarray) -> np.ndarray:
    """v (N, 2) on t_grid evaluated at t_query by linear interpolation (ends held)."""
    return np.stack([np.interp(t_query, t_grid, v[:, 0]), np.interp(t_query, t_grid, v[:, 1])], axis=-1)


def _rms(err: np.ndarray) -> float:
    err = err[np.isfinite(err)]
    return float(np.sqrt(np.mean(err ** 2))) if err.size else math.nan


def _t63_error(row: dict) -> float:
    a, b = row["t63_measured_s"], row["t63_model_s"]
    fa, fb = a is not None and math.isfinite(a), b is not None and math.isfinite(b)
    if fa and fb:
        return abs(b - a)
    return math.nan if not fa and not fb else math.inf      # the model or the drone never reached 63 %


def score_drone(f: dict, params: m.TrajectoryParams, gates: dict, airborne_only: bool = True,
                setpoint: str = "hold") -> dict:
    from fit_real_px4 import leg_changes                      # t63 of a leg's start and stop (same code as S1)
    windows, meta, times, skipped = make_windows(f, airborne_only, setpoint)
    v_models = m.simulate_windows(params, windows)
    legs, pooled = [], {"measured": [], "model": [], "sp": [], "sp_delayed": []}
    shift_err = {float(s): [] for s in SHIFTS_S}
    for w, mt, tm, vm in zip(windows, meta, times, v_models):
        v_sp = w.v_ff
        v_spd = m.delay_signal(v_sp, DT_S, DELAY_BASELINE_S)
        active = (tm >= mt["start_s"]) & (tm <= mt["end_s"] + ACTIVE_AFTER_S)
        meas = w.v_meas
        err = {"model": _at(w.t_s, vm, tm) - meas, "sp": _at(w.t_s, v_sp, tm) - meas,
               "sp_delayed": _at(w.t_s, v_spd, tm) - meas}
        for k, e in err.items():
            pooled.setdefault(k, [])
            pooled[k].append(e[active])
        by_shift = {float(s): _rms(_at(w.t_s, vm, tm[active] - s) - meas[active]) for s in SHIFTS_S}
        for s in SHIFTS_S:
            shift_err[float(s)].append(_at(w.t_s, vm, tm[active] - s) - meas[active])
        best = min(by_shift, key=lambda s: (by_shift[s] if math.isfinite(by_shift[s]) else math.inf))
        rows = []
        for r in leg_changes(w, vm):
            e = _t63_error(r)
            rows.append({"change": r["change"], "from_mps": r["from_mps"], "to_mps": r["to_mps"],
                         "t63_setpoint_s": r["t63_setpoint_s"], "t63_measured_s": r["t63_measured_s"],
                         "t63_model_s": r["t63_model_s"], "t63_error_s": e})
        legs.append({**mt, "peak_setpoint_mps": float(np.linalg.norm(v_sp, axis=1).max()),
                     "measured_samples": int(active.sum()),
                     "rms_mps": _rms(err["model"][active]),
                     "baseline_setpoint_rms_mps": _rms(err["sp"][active]),
                     "baseline_setpoint_delayed_rms_mps": _rms(err["sp_delayed"][active]),
                     "t63": rows, "best_extra_shift_s": best, "best_extra_shift_rms_mps": by_shift[best]})
    pooled_rms = {k: _rms(np.concatenate(v)) if v else math.nan for k, v in pooled.items() if k != "measured"}
    shift_rms = {s: (_rms(np.concatenate(v)) if v else math.nan) for s, v in shift_err.items()}
    finite = {s: r for s, r in shift_rms.items() if math.isfinite(r)}
    best_shift = min(finite, key=finite.get) if finite else math.nan
    t63_errors = [r["t63_error_s"] for lg in legs for r in lg["t63"] if not math.isnan(r["t63_error_s"])]
    worst_rms = max((lg["rms_mps"] for lg in legs), default=math.nan)
    worst_t63 = max(t63_errors, default=math.nan)
    n_legs = len(legs)
    if n_legs < int(gates["min_legs"]):
        verdict = "INFO"
    else:
        ok = worst_rms <= gates["vel_rms_max_mps"] and (not t63_errors or worst_t63 <= gates["t63_err_max_s"])
        verdict = "PASS" if ok else "FAIL"
    return {"legs": legs, "n_legs": n_legs, "legs_skipped": skipped, "verdict": verdict,
            "worst_leg_rms_mps": worst_rms, "worst_t63_error_s": worst_t63, "t63_pairs": len(t63_errors),
            "pooled_rms_mps": pooled_rms,
            "best_extra_shift_s": best_shift, "best_extra_shift_rms_mps": finite.get(best_shift, math.nan),
            "rms_at_zero_shift_mps": shift_rms.get(0.0, math.nan)}


# ------------------------------------------------------------------------------------------------ figure
def make_figure(flights: dict, params: m.TrajectoryParams, scores: dict, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from make_s0_figures import INK, INK2, SERIES, style
    drones = [d for d in DRONES if d in scores and scores[d]["n_legs"]]
    cols = 4
    per = {d: make_windows(flights[d]) for d in drones}
    rows_per = {d: math.ceil(len(per[d][0]) / cols) for d in drones}
    if not drones:
        fig = plt.figure(figsize=(8, 2), dpi=130)
        fig.text(0.02, 0.5, "no flight legs found in the bag", color=INK2)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out)
        plt.close(fig)
        return
    fig = plt.figure(figsize=(14, 3.0 * sum(rows_per.values()) + 0.8), dpi=130)
    gs = fig.add_gridspec(sum(rows_per.values()), cols)
    r0 = 0
    for d in drones:
        windows, meta, times, _ = per[d]
        vms = m.simulate_windows(params, windows)
        for k, (w, mt, tm, vm) in enumerate(zip(windows, meta, times, vms)):
            ax = fig.add_subplot(gs[r0 + k // cols, k % cols])
            t = w.t_s - mt["start_s"]
            ax.axvspan(0, mt["end_s"] + ACTIVE_AFTER_S - mt["start_s"], color=SERIES[3], alpha=0.10, linewidth=0)
            ax.plot(t, np.linalg.norm(w.v_ff, axis=1), color=SERIES[3], linewidth=1.5, label="setpoint speed")
            ax.plot(tm - mt["start_s"], np.linalg.norm(w.v_meas, axis=1), "o", color=SERIES[0], markersize=2.4,
                    label="measured")
            ax.plot(t, np.linalg.norm(vm, axis=1), color=SERIES[1], linewidth=1.6, label="model")
            lg = scores[d]["legs"][k]
            style(ax, f"{d} leg {k}: RMS {lg['rms_mps']:.3f} m/s", "s since leg start", "speed (m/s)")
            ax.title.set_fontsize(9)
            if r0 == 0 and k == 0:
                ax.legend(frameon=False, fontsize=7, loc="upper right", labelcolor=INK)
        r0 += rows_per[d]
    fig.suptitle("12 November bag: measured, model and setpoint speed per leg (shaded = scored span; model not refitted)",
                 fontsize=11, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)


# ------------------------------------------------------------------------------------------------ record
def _f(x, nd=3):
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def next_t_number(ledger: Path) -> int:
    nums = [int(x) for x in re.findall(r"^\| T(\d+) \|", ledger.read_text(), flags=re.M)]
    return max(nums, default=0) + 1


def caption_for(res: dict, g: dict) -> str:
    s = res["drone_2"] if "drone_2" in res else {}
    txt = (f"Speed of the setpoint (amber), the real drone (blue dots) and the model (orange), one panel per leg. "
           f"Shaded: the span scored. Drone_2: worst leg RMS {_f(s.get('worst_leg_rms_mps'))} m/s against "
           f"{g['vel_rms_max_mps']:.2f}; worst 63 % time error {_f(s.get('worst_t63_error_s'))} s against "
           f"{g['t63_err_max_s']:.2f}.")
    assert len(txt) <= CAPTION_MAX, len(txt)
    return txt


def write_record(path: Path, ctx: dict) -> None:
    res, g, p = ctx["results"], ctx["gates"], ctx["params"]
    d2 = res.get("drone_2", {})
    result = res["result"]
    L = ["Observed in flight logs: real drone, 12 November 2026 rosbag; the training simulator's drone model checked, "
         "not refitted", "",
         f"# {ctx['name']} record", "", f"Result: **{result}** (gates on drone_2). Ledger row {ctx['t_id']}.", "",
         "## Purpose", "",
         "Check the training simulator's drone model (`params/real_exploratory_v0.toml`, fitted to the 13 November "
         "PX4 logs of drone_2) against a different recording it never saw: the 12 November two-drone flight, "
         "recorded as a rosbag at the full 19 Hz command rate. Nothing is refitted; the parameter file is read "
         "as written. This answers one question: does the model, fitted at one speed in one log, still describe "
         "the real drone's velocity in another flight? Observed in flight logs; it says nothing about how a "
         "trained strategy will fly.", "",
         "## Commit", "",
         f"Repository HEAD `{ctx['head']}`, this task's files uncommitted (the lead commits). Code fingerprint "
         f"(sha256 over `source/`, `scripts/`, `configs/`): `{ctx['code_sha']}`. The bag is read-only: "
         f"`{ctx['bag_name']}`, sha256 `{ctx['bag_sha'][:16]}`, {ctx['bag_mb']:.0f} MB.", "",
         "## Config", "",
         f"`python scripts/bag_check.py --bag <bag dir> --params params/real_exploratory_v0.toml --gates "
         f"configs/s2.toml --name {ctx['name']}`. Gates (`[bag_check_gates]`, copied to "
         f"`runs/{ctx['name']}/gates.toml` before the run, approved before any result): drone `{g['drone']}`; "
         f"velocity RMS at most {g['vel_rms_max_mps']:.2f} m/s on every leg (leg start to leg end + 1 s); worst time "
         f"to 63 % of a change (start or stop) off by at most {g['t63_err_max_s']:.2f} s; at least "
         f"{g['min_legs']} legs, otherwise INFO with no verdict.", "",
         "How the numbers are made: the setpoint (what the commander sent, 18.8 Hz) is held onto a 0.01 s grid; "
         "each leg is a stretch where the setpoint speed is above 0.1 m/s, with a window from 1.0 s before to "
         "2.5 s after (cut halfway to the next leg). As in the S1 fit, a leg counts only if the drone stays above "
         "0.3 m for the whole window; takeoffs, landings and setpoints followed on the ground are not flights. "
         f"{d2.get('legs_skipped', 0)} such legs were left out of drone_2's count (the result with every leg is "
         "given under Results). The model starts each window from the measured position "
         "and velocity and flies the setpoint. Time is the bag's own log time: the measured velocity crosses the "
         "WiFi before it is logged, so its delay includes one network leg.", "",
         "## Model parameter set", "",
         f"`params/real_exploratory_v0.toml` (sha256 `{ctx['params_sha'][:12]}`), `[px4]` table, family "
         f"{p.family}: delay {p.delay_s:.4f} s, lag {p.tau_s:.4f} s, acceleration limit {p.acc_max_mps2:.4f} m/s^2, "
         f"Kp {p.kp_xy:.2f}. Exploratory.", "",
         "## Seeds", "", "None: no random numbers.", "",
         "## Machine", "", "CPU only, this laptop; no GPU, no simulator.", "",
         "## Games at once", "", "Not applicable.", "",
         "## Steps per second", "", "Not applicable (not a speed run).", "",
         "## Gates", "",
         "| Gate | Limit | drone_2 (gated) | Result |", "|---|---|---|---|"]
    if d2:
        enough = d2["n_legs"] >= g["min_legs"]
        L.append(f"| legs found | at least {g['min_legs']} | {d2['n_legs']} | {'PASS' if enough else 'INFO'} |")
        L.append(f"| worst leg velocity RMS | {g['vel_rms_max_mps']:.2f} m/s | {_f(d2['worst_leg_rms_mps'])} m/s | "
                 f"{('PASS' if d2['worst_leg_rms_mps'] <= g['vel_rms_max_mps'] else 'FAIL') if enough else 'INFO'} |")
        L.append(f"| worst 63 % time error | {g['t63_err_max_s']:.2f} s | {_f(d2['worst_t63_error_s'])} s "
                 f"({d2['t63_pairs']} start/stop pairs) | "
                 f"{('PASS' if (d2['worst_t63_error_s'] <= g['t63_err_max_s'] or d2['t63_pairs'] == 0) else 'FAIL') if enough else 'INFO'} |")
    else:
        L.append("| (no drone_2 data in the bag) | | | INFO |")
    L += ["", "## Results", "",
          "RMS over every leg's scored span, both axes together (m/s). Baselines: the drone flies the setpoint "
          "speed exactly, and the same 0.15 s later.", "",
          "| Drone | Legs | Worst leg RMS | Pooled RMS, model | Pooled, setpoint speed | Pooled, setpoint 0.15 s later | "
          "Best extra shift (info) | Verdict if gated |", "|---|---|---|---|---|---|---|---|"]
    for d in DRONES:
        s = res.get(d)
        if not s:
            continue
        pr = s["pooled_rms_mps"]
        L.append(f"| {d}{' (gated)' if d == g['drone'] else ' (reported)'} | {s['n_legs']} | "
                 f"{_f(s['worst_leg_rms_mps'])} | {_f(pr.get('model'))} | {_f(pr.get('sp'))} | "
                 f"{_f(pr.get('sp_delayed'))} | {_f(s['best_extra_shift_s'], 2)} s "
                 f"(RMS {_f(s['best_extra_shift_rms_mps'])} vs {_f(s['rms_at_zero_shift_mps'])}) | {s['verdict']} |")
    sens = res.get("all_legs_sensitivity", {})
    if sens.get(g["drone"]):
        a = sens[g["drone"]]
        L += ["", f"Information only, every leg including those on the ground or in takeoff and landing "
              f"({g['drone']}): {a['n_legs']} legs, worst leg RMS {_f(a['worst_leg_rms_mps'])} m/s, "
              f"pooled model RMS {_f(a['pooled_rms_mps'].get('model'))} m/s against "
              f"{_f(a['pooled_rms_mps'].get('sp'))} m/s for the setpoint speed itself; verdict it would give: "
              f"{a['verdict']}. It moves no verdict here."]
    lin = res.get("linear_setpoint_sensitivity", {}).get(g["drone"])
    if lin:
        e = [lg["rms_mps"] for lg in lin["legs"]]
        L += ["", "Information only, a different reading of the setpoint. The run above holds each 19 Hz message "
              "until the next one, as this check was specified. The model's acceleration feed-forward is the slope of the "
              "speed setpoint, and a held setpoint makes that slope a sharp spike that the model's acceleration "
              "limit mostly cuts off. The S1 fit instead joined its setpoint messages by straight lines. "
              f"Joined by lines ({g['drone']}, same legs): leg RMS {', '.join(_f(x) for x in e)} m/s, worst "
              f"63 % time error {_f(lin['worst_t63_error_s'])} s, verdict it would give: {lin['verdict']}. "
              "This does not change the result above; a run with that reading would be a new, separately "
              "decided run."]
    L += ["", "Per leg (drone_2):", "", "| Leg | Start (bag s) | Peak setpoint (m/s) | RMS (m/s) | t63 error start (s) | "
          "t63 error stop (s) |", "|---|---|---|---|---|---|"]
    for lg in d2.get("legs", []):
        e = {r["change"]: r["t63_error_s"] for r in lg["t63"]}
        L.append(f"| {lg['leg']} | {lg['start_s']:.1f} | {lg['peak_setpoint_mps']:.2f} | {_f(lg['rms_mps'])} | "
                 f"{_f(e.get('start', math.nan))} | {_f(e.get('stop', math.nan))} |")
    L += ["", f"![bag check: measured, model and setpoint speed per leg](../docs/figures/s2_bag_check.png)", "",
          f"*{ctx['caption']}*", "",
          "## What this result can and cannot change", "",
          f"A {result} here does not touch `params/`: the model file stays as it is, and the model of record still "
          "waits on the planned-push flight (designed pushes at several speeds, which the logs so far lack). "
          "A PASS would say the model also holds on a second flight at the same low speed; it would not say it "
          "holds at 2 m/s or above. A FAIL would say the model, fitted on one log, misses another by more than the "
          "approved limits; it would be a reason to refit on more data, not a number to loosen. Exploratory: the "
          "bag has only the goal flights (speeds up to 0.5 m/s, no stick), so it cannot give the eight legs "
          "of S1's own fit gates.", "",
          "## Limits", "",
          "- Same low-speed regime as the fit (setpoint at most 0.5 m/s); the simulator's 2 to 6 m/s are untested.",
          "- Measured velocity is PX4's estimate after the WiFi; its delay includes one network leg, so a model "
          "delay larger than the 13 November PX4-log fit is expected and is not by itself an error.",
          "- The acceleration feed-forward is derived from the held speed setpoint, as in the fit.",
          "- The best extra shift is information only and moved no gate.", ""]
    path.write_text("\n".join(L))


# ------------------------------------------------------------------------------------------------ main
def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if not math.isfinite(float(x)) else round(float(x), 5)
    if isinstance(x, np.integer):
        return int(x)
    return x


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bag", type=Path, required=True)
    ap.add_argument("--params", type=Path, required=True)
    ap.add_argument("--gates", type=Path, required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--runs-dir", type=Path, default=ROOT / "runs")
    ap.add_argument("--fig", type=Path, default=ROOT / "docs/figures/s2_bag_check.png")
    ap.add_argument("--records-dir", type=Path, default=ROOT / "records")
    ap.add_argument("--no-record", action="store_true", help="skip the record and the ledger row (tests)")
    a = ap.parse_args(argv)
    try:
        gates = tomllib.loads(a.gates.read_text())["bag_check_gates"]
        cfg = tomllib.loads(a.params.read_text())
        px = {k: v for k, v in cfg["px4"].items() if k != "model_dt_s"}
        params = m.TrajectoryParams.from_dict(px)
    except (OSError, KeyError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"bad parameter or gate file: {exc}", file=sys.stderr)
        return 2
    if gates.get("accel_ff") != "derived":
        print("only accel_ff = 'derived' is implemented", file=sys.stderr)
        return 2
    try:
        mcap_path = find_mcap(a.bag)
        flights = load_bag(mcap_path)
    except (OSError, ValueError, KeyError) as exc:
        print(f"cannot read {a.bag}: {exc}", file=sys.stderr)
        return 1
    run_dir = a.runs_dir / a.name
    run_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(a.gates, run_dir / "gates.toml")                     # copied before any scoring
    shutil.copyfile(a.params, run_dir / "params_used.toml")
    scores = {d: score_drone(flights[d], params, gates) for d in DRONES if d in flights}
    # information only: every leg, ground legs included (the brief's literal reading); it moves no verdict
    sens = {d: {k: v for k, v in score_drone(flights[d], params, gates, airborne_only=False).items() if k != "legs"}
            for d in DRONES if d in flights}
    # information only: the setpoint joined by straight lines (as the S1 fit did) instead of held on the grid
    lin = {d: score_drone(flights[d], params, gates, setpoint="linear") for d in DRONES if d in flights}
    gated = scores.get(gates["drone"])
    result = gated["verdict"] if gated else "INFO"
    results = {"name": a.name, "result": result, "gated_drone": gates["drone"], "bag": str(mcap_path),
               "params": params.to_dict(), "gates": gates, "time_base": "bag log time (measured velocity crosses WiFi)",
               **scores, "all_legs_sensitivity": sens, "linear_setpoint_sensitivity": lin}
    (run_dir / "results.json").write_text(json.dumps(_clean(results), indent=1))
    make_figure(flights, params, scores, a.fig)
    print(json.dumps(_clean({"result": result, **{d: {k: v for k, v in s.items() if k != "legs"}
                                                    for d, s in scores.items()}}), indent=1))
    if not a.no_record:
        ledger = a.records_dir / "LEDGER.md"
        t_id = f"T{next_t_number(ledger)}"
        sys.path.insert(0, str(ROOT / "source"))
        from svg_training.bench.rows import code_sha
        import subprocess
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        now = datetime.datetime.now().astimezone().replace(microsecond=0)
        caption = caption_for(results, gates)
        ctx = {"results": results, "gates": gates, "params": params, "name": a.name, "t_id": t_id, "head": head,
               "code_sha": code_sha(), "bag_name": mcap_path.name, "bag_sha": sha256_of(mcap_path),
               "bag_mb": mcap_path.stat().st_size / 1e6, "params_sha": sha256_of(a.params), "caption": caption}
        rec = a.records_dir / f"{a.name}_record.md"
        write_record(rec, ctx)
        row = (f"| {t_id} | {now.isoformat()} | observed in flight logs (12 November rosbag; drone model checked, "
               f"not refitted) | {a.name} | S2 drone-model held-out check on the 12 November bag, drone_2 gated, "
               f"{gated['n_legs'] if gated else 0} legs | {result} | records/{rec.name} |\n")
        text = ledger.read_text()
        ledger.write_text(text if text.endswith("\n") else text + "\n")
        with open(ledger, "a") as fh:
            fh.write(row)
        print(f"record {rec}; ledger row {t_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
