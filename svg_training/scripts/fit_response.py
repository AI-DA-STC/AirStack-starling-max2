#!/usr/bin/env python3
"""Fit the response model (teleop command -> measured velocity) to one session recorded in the AirStack simulator.

Usage (from svg_training/):
    fit_response.py --csv-dir runs/<extract> (--ulog <drone ulog> | --time-scale <float>) --name <YYYY-MM-DD>_s1_fit_v<k>
                    --gates configs/s1.toml [--steps-json <file>] [--family lag1|lag2|best] [--dt-s 0.01]
                    [--speed-cap-mps 2.0] [--out-root <dir>]

Reads teleop_command.csv, odometry.csv (and manifest.json, commander_status.csv when present) written by
bag_to_csv.py. Steps:
  1. Time scale (vehicle s per wall s). --ulog: the PX4 flight span (takeoff -> touchdown, height threshold, inside
     the ulog's arm -> disarm) over the same span in the bag's odometry (wall). The ULog is read by the small reader
     below (pyulog is not on the host); the arm/disarm logic is ported from tools/hover_step_timescale.py and the
     span ratio from tools/hover_step_analysis.py (compute_time_scale). --time-scale injects a value (tests).
     Either way it is cross-checked against the position-derivative gain (d position / d wall time against the
     world-frame odometry velocity); a difference above 5 % stops the run (exit 3) before anything is written.
  2. Odometry velocity is BODY frame: rotated with response.body_to_world before fitting.
  3. fit.to_vehicle_time (same scale and t0 for both streams), fit.resample_uniform, fit.step_data segments.
     Split: even segments train, odd held out (fit.split_alternate). --steps-json (virtual_stick.py plan) only
     labels the segments and must match their number.
  4. Both families fitted on the training steps, scored on the held-out steps; --family best keeps the one with the
     lower held-out velocity RMS (worst step, the gated metric).
  5. Gates from [fit_gates], judged on the kept family. Writes params/airstack_sim_v<k>.toml, records/<name>_record.md,
     one row of records/LEDGER.md (T<n>) and docs/figures/s1_t<n>_held_out_step_<i>.png + s1_t<n>_all_steps.png
     (docs/, not runs/: runs/ is git-ignored and the record links the figures). Refuses to overwrite any of them.

SIM ONLY: parameters fitted here never go to the drone (repository iron rule 9).
Exit codes: 0 written (PASS or FAIL); 1 refused to overwrite or unreadable input; 2 bad arguments or the data cannot
be fitted (steps-json mismatch, fewer than two steps); 3 time scale disagrees with the position-derivative gain.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import struct
import sys
import tomllib
from datetime import datetime
from pathlib import Path

# One BLAS thread: the fit's matrices are small and a threaded BLAS spins 16 cores for nothing (measured: a lag1 fit
# took minutes threaded, 7 s single-threaded). Set before numpy loads; a caller's own setting wins.
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "source"))

from svg_training.bench.rows import code_sha  # noqa: E402
from svg_training.models import fit as fitmod  # noqa: E402
from svg_training.models.response import FAMILIES, ResponseParams, body_to_world, simulate  # noqa: E402

FIRST_LINE = "Simulator: AirStack simulator (Isaac Sim + Pegasus + PX4 SITL in lockstep), one drone"
SCALE_TOLERANCE = 0.05          # |time scale / position-derivative gain - 1| above this stops the run
HEIGHT_THRESHOLD_M = 0.2        # takeoff / touchdown = height above ground crosses this (both logs)
MOVING_MPS = 0.2                # derivative gain uses samples whose world speed is at least this
NOT_IDENTIFIED_MPS = 2e-3       # a +25 % change of the parameter moves the training-window model less than this
TOOL_SOURCES = ("tools/hover_step_timescale.py", "tools/hover_step_analysis.py")


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
    """Top-level scalar primitive fields of a format: {field: (byte offset, struct char)}."""
    out, off = {}, 0
    for t, field in formats[name]:
        base, n = _split_type(t)
        size = struct.calcsize("<" + _PRIM[base]) if base in _PRIM else _size(formats, base)
        if base in _PRIM and n == 1 and base != "char":
            out[field] = (off, _PRIM[base])
        off += n * size
    return out


def read_ulog(path, names) -> dict:
    """{topic: {field: (N,) array}} of the scalar fields of the first instance (multi_id 0) of each named topic.

    Minimal PX4 ULog reader (file format v1: header, then messages of uint16 size + uint8 type). Reads only format
    (F), add-logged (A) and data (D) messages; everything else is skipped. Raises ValueError on a non-ULog file.
    """
    buf = Path(path).read_bytes()
    if buf[:7] != b"ULog\x01\x12\x35":
        raise ValueError(f"{path}: not a ULog file")
    wanted = set(names)
    formats, subs, raw = {}, {}, {n: [] for n in wanted}
    pos, end = 16, len(buf)
    while pos + 3 <= end:
        size, kind = struct.unpack_from("<HB", buf, pos)
        body = pos + 3
        if body + size > end:
            break                                   # truncated last message
        if kind == 0x46:                            # F: "name:type field;type field;..."
            text = buf[body:body + size].decode("ascii", "replace")
            fname, fields = text.split(":", 1)
            formats[fname] = [tuple(f.split(" ", 1)) for f in fields.split(";") if f]
        elif kind == 0x41:                          # A: multi_id, msg_id, name
            multi, mid = struct.unpack_from("<BH", buf, body)
            subs[mid] = (buf[body + 3:body + size].decode("ascii", "replace"), multi)
        elif kind == 0x44:                          # D: msg_id, payload
            mid = struct.unpack_from("<H", buf, body)[0]
            sub = subs.get(mid)
            if sub is not None and sub[1] == 0 and sub[0] in wanted:
                raw[sub[0]].append(buf[body + 2:body + size])
        pos = body + size
    out = {}
    for name, msgs in raw.items():
        if name not in formats:
            continue
        lay = _layout(formats, name)
        out[name] = {f: np.array([struct.unpack_from("<" + c, m, off)[0] for m in msgs])
                     for f, (off, c) in lay.items()}
    return out


# Ported (logic unchanged) from tools/hover_step_timescale.py: arming_transitions.
ARMING_STATE_DISARMED = 1  # PX4 vehicle_status.arming_state
ARMING_STATE_ARMED = 2


def arming_transitions(timestamps_us, arming_state):
    """First 1->2 (arm) and the first subsequent 2->1 (disarm) transition, in seconds; either may be None."""
    arm_s = None
    disarm_s = None
    prev = None
    for ts, st in zip(timestamps_us, arming_state):
        st = int(st)
        if prev is not None:
            if arm_s is None and prev == ARMING_STATE_DISARMED and st == ARMING_STATE_ARMED:
                arm_s = ts / 1e6
            elif arm_s is not None and prev == ARMING_STATE_ARMED and st == ARMING_STATE_DISARMED:
                disarm_s = ts / 1e6
                break
        prev = st
    return arm_s, disarm_s


# Ported (logic unchanged) from tools/hover_step_analysis.py: compute_time_scale.
def compute_time_scale(px4_start_s, px4_end_s, bag_start_s, bag_end_s) -> float:
    """Vehicle seconds per bag (wall) second = PX4 interval / bag interval of the same two events."""
    px4 = px4_end_s - px4_start_s
    bag = bag_end_s - bag_start_s
    if px4 <= 1.0 or bag <= 1.0:
        raise ValueError(f"interval too short: px4 {px4:.3f} s, bag {bag:.3f} s (need > 1.0 s each)")
    return px4 / bag


def _flight_span(t, height_m, threshold_m=HEIGHT_THRESHOLD_M):
    """(takeoff, touchdown): first and last sample above ground + threshold; ground = median of the first 50 samples."""
    h = np.asarray(height_m, dtype=float)
    above = np.flatnonzero(h > np.median(h[:50]) + threshold_m)
    if above.size == 0:
        raise ValueError(f"no sample is {threshold_m} m above the ground: no flight in this log")
    return float(t[above[0]]), float(t[above[-1]])


def ulog_time_scale(ulog_path, t_odom_wall_s, z_odom_m) -> dict:
    """Time scale from the flight span: PX4 takeoff -> touchdown (vehicle_local_position, inside arm -> disarm) over
    the bag odometry's takeoff -> touchdown (wall), same height threshold on both sides."""
    d = read_ulog(ulog_path, ["vehicle_status", "vehicle_local_position"])
    if "vehicle_status" not in d or "vehicle_local_position" not in d:
        raise ValueError(f"{ulog_path}: vehicle_status or vehicle_local_position missing")
    st = d["vehicle_status"]
    arm_s, disarm_s = arming_transitions(st["timestamp"], st["arming_state"])
    if arm_s is None or disarm_s is None:
        raise ValueError(f"{ulog_path}: no arm -> disarm pair (arm {arm_s}, disarm {disarm_s})")
    lp = d["vehicle_local_position"]
    t_v = lp["timestamp"] / 1e6
    m = (t_v >= arm_s - 5.0) & (t_v <= disarm_s)
    up_v, down_v = _flight_span(t_v[m], -lp["z"][m])
    up_w, down_w = _flight_span(np.asarray(t_odom_wall_s, float), z_odom_m)
    return {"scale": compute_time_scale(up_v, down_v, up_w, down_w), "arm_s": arm_s, "disarm_s": disarm_s,
            "takeoff_vehicle_s": up_v, "touchdown_vehicle_s": down_v, "takeoff_wall_s": up_w,
            "touchdown_wall_s": down_w, "span_vehicle_s": down_v - up_v, "span_wall_s": down_w - up_w}


def derivative_check(t_wall_s, pos_m, v_body_mps, q_wxyz) -> dict:
    """Position-derivative gain d(pos)/d(wall t) against the world velocity, and the frame check (mean cosines)."""
    v_w = body_to_world(v_body_mps, q_wxyz)
    dp = np.gradient(np.asarray(pos_m, float), np.asarray(t_wall_s, float), axis=0)
    m = np.linalg.norm(v_w, axis=1) >= MOVING_MPS
    if m.sum() < 10:
        raise ValueError("fewer than 10 moving odometry samples: no position-derivative gain")

    def cos(a, b):
        return float(np.mean(np.sum(a * b, 1) / np.maximum(np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1), 1e-12)))

    return {"gain": float(np.sum(dp[m] * v_w[m]) / np.sum(v_w[m] * v_w[m])), "n_samples": int(m.sum()),
            "cos_rotated": cos(dp[m], v_w[m]), "cos_as_published": cos(dp[m], np.asarray(v_body_mps)[m])}


# ----------------------------------------------------------------------------------------------- helpers
def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_blob(path: Path) -> str:
    """Git blob id of a file's current bytes (what `git hash-object` prints), computed without git."""
    if not path.is_file():
        return "file not found"
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _read_csv(path: Path) -> dict:
    with open(path) as f:
        header = f.readline().strip().split(",")
    arr = np.loadtxt(path, delimiter=",", skiprows=1, ndmin=2)
    return {h: arr[:, i] for i, h in enumerate(header)}


def _increasing(t: np.ndarray) -> np.ndarray:
    """Indices that keep the stamps strictly increasing (drop repeated or backward receive stamps)."""
    keep, last = [], -math.inf
    for i, x in enumerate(t):
        if x > last:
            keep.append(i)
            last = x
    return np.array(keep, dtype=int)


def _commander_span(path: Path):
    """Wall stamps of the first ARMING entry and the first IDLE after it (drone 0), from commander_status.csv."""
    if not path.is_file():
        return None
    import csv
    arm = idle = None
    prev = None
    with open(path) as f:
        for row in csv.DictReader(f):
            try:
                state = json.loads(row["data"])["drones"][0]["state"]
            except (ValueError, KeyError, IndexError):
                continue
            t = float(row["t_wall_s"])
            if arm is None and state == "ARMING" and prev != "ARMING":
                arm = t
            elif arm is not None and state == "IDLE" and prev != "IDLE":
                idle = t
                break
            prev = state
    return (arm, idle) if arm is not None and idle is not None else None


def _pyulog_arm_disarm(ulog: Path):
    """arm_s / disarm_s written by sim.sh's pyulog dump (px4_drone_1.csv next to the ulog), if present."""
    p = ulog.parent / "px4_drone_1.csv"
    if not p.is_file():
        return None
    vals = {}
    with open(p) as f:
        for line in f:
            if not line.startswith("#"):
                break
            k, _, v = line[1:].strip().partition("=")
            vals[k] = v
    try:
        return float(vals["arm_s"]), float(vals["disarm_s"])
    except (KeyError, ValueError):
        return None


def _labels(data, min_jump=0.2) -> list[dict]:
    out = []
    for s, e in data.windows:
        rest = np.flatnonzero(np.linalg.norm(data.cmd_mps[s:e], axis=1) < min_jump)
        r = s + int(rest[0]) if rest.size else e
        level = np.median(data.cmd_mps[s:r], axis=0)
        a = int(np.argmax(np.abs(level)))
        out.append({"axis": "xyz"[a], "sign": 1 if level[a] > 0 else -1, "speed_mps": float(abs(level[a])),
                    "start_s": float(data.t_s[s]), "hold_s": float(data.t_s[r - 1] - data.t_s[s] + data.dt_s),
                    "repeat": None})
    return out


def _sensitivity(p: ResponseParams, data, train, names) -> dict:
    """RMS change (m/s) of the model over the training windows when each free parameter is raised by 25 %."""
    sel = np.concatenate([np.arange(*data.windows[i]) for i in train])
    base = simulate(data.cmd_mps, data.dt_s, p, v0_mps=data.vel_mps[0])[sel]
    out = {}
    for n in names:
        d = p.to_dict()
        d[n] = d[n] * 1.25 if d[n] > 0.04 else d[n] + 0.05
        m = simulate(data.cmd_mps, data.dt_s, ResponseParams.from_dict(d), v0_mps=data.vel_mps[0])[sel]
        out[n] = float(np.sqrt(np.mean(np.sum((m - base) ** 2, axis=1))))
    return out


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        v = float(v)
        return "inf" if v == math.inf else repr(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    return json.dumps(str(v))


def _toml(tables: dict, header: str) -> str:
    lines = [header, ""]
    for name, table in tables.items():
        lines.append(f"[{name}]")
        lines += [f"{k} = {_toml_value(v)}" for k, v in table.items()]
        lines.append("")
    return "\n".join(lines)


def _f(x, nd=3) -> str:
    if x is None:
        return "-"
    if isinstance(x, float) and not math.isfinite(x):
        return "never" if math.isnan(x) else "inf"
    return f"{x:.{nd}f}"


# ----------------------------------------------------------------------------------------------- plots
def step_fractions(data, labels, model=None) -> list[dict]:
    """Per step, the measured speed along the step axis as a fraction of the command: highest value during the hold
    (peak), last value of the hold (at_release), lowest value after the release (after_min, nan if none); and the
    model's peak (model_peak) when a model (T, 3) is given."""
    out = []
    for k, (s, e) in enumerate(data.windows):
        lab = labels[k]
        a = "xyz".index(lab["axis"])
        sgn = (1.0 if lab["sign"] > 0 else -1.0) / max(lab["speed_mps"], 1e-9)
        v = sgn * data.vel_mps[s:e, a]
        rest = np.flatnonzero(np.linalg.norm(data.cmd_mps[s:e], axis=1) < 0.2)
        r = max(int(rest[0]) if rest.size else e - s, 1)
        out.append({"peak": float(np.max(v[:r])), "at_release": float(v[r - 1]),
                    "after_min": float(np.min(v[r:])) if r < e - s else math.nan,
                    "model_peak": float(np.max(sgn * model[s:s + r, a])) if model is not None else math.nan})
    return out


def _figs():
    """make_s0_figures (palette, style()) from this folder's scripts/; it selects the Agg backend on import."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import make_s0_figures as figs
    import matplotlib.pyplot as plt
    return figs, plt


def _plots(out_dir: Path, prefix: str, data, models: dict, kept: str, held, rows: dict, labels, train) -> list[dict]:
    """One figure per held-out step (response on the step axis + 3-D error of each family) and one overview of every
    step (measured vs the kept family). Returns [{"file", "caption"}] in the order the record shows them."""
    figs, plt = _figs()
    color = {f: figs.SERIES[i] for i, f in enumerate(FAMILIES)}
    out_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for i in held:
        s, e = data.windows[i]
        t = data.t_s[s:e] - data.t_s[s]
        lab = labels[i]
        a = "xyz".index(lab["axis"])
        sign = "+" if lab["sign"] > 0 else "-"
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6.4), dpi=150, sharex=True, height_ratios=[3, 2])
        ax1.step(t, data.cmd_mps[s:e, a], where="post", color=figs.INK2, lw=1.5, ls="--", label="teleop command")
        ax1.plot(t, data.vel_mps[s:e, a], color=figs.INK, lw=2, label="measured")
        for fam, mod in models.items():
            ax1.plot(t, mod[s:e, a], color=color[fam], lw=2.5 if fam == kept else 1.5,
                     label=f"{fam} model{' (kept)' if fam == kept else ''}")
            err = np.linalg.norm(mod[s:e] - data.vel_mps[s:e], axis=1)
            ax2.plot(t, err, color=color[fam], lw=2 if fam == kept else 1.5,
                     label=f"{fam}: RMS {rows[fam][i]['vel_rms_mps']:.3f} m/s")
        figs.style(ax1, f"Held-out step {i}: {lab['axis']} {sign}{lab['speed_mps']:.2f} m/s", "",
                   f"v_{lab['axis']} (m/s)")
        figs.style(ax2, "Model error, all three axes", "vehicle time from step start (s)", "|model - measured| (m/s)")
        ax1.legend(frameon=False, fontsize=9, labelcolor=figs.INK, loc="best")
        ax2.legend(frameon=False, fontsize=9, labelcolor=figs.INK, loc="upper left")
        fig.tight_layout()
        name = f"{prefix}held_out_step_{i}.png"
        fig.savefig(out_dir / name)
        plt.close(fig)
        r = rows[kept][i]
        hold = np.flatnonzero(np.linalg.norm(data.cmd_mps[s:e], axis=1) >= 0.2)
        peak = float(np.max(np.abs(data.vel_mps[s:e, a][hold]))) if hold.size else math.nan
        out.append({"file": name, "caption": (
            f"Held-out step {i}: the policy commands {sign}{lab['speed_mps']:.2f} m/s along {lab['axis']}. "
            f"The measured speed peaks at {peak:.2f} m/s; it reaches 63 % of the command after "
            f"{_f(r['t63_meas_s'], 2)} s against {_f(r['t63_model_s'], 2)} s for the {kept} model. "
            f"The lower panel is the model error the velocity gate scores (RMS {r['vel_rms_mps']:.3f} m/s, "
            "limit 0.10).")})
    n = len(data.windows)
    ncol = min(n, 4)
    nrow = math.ceil(n / ncol)
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.4 * ncol, 2.6 * nrow + 0.4), dpi=150, sharey=True, squeeze=False)
    for k, ax in enumerate(axes.flat):
        if k >= n:
            ax.set_visible(False)
            continue
        s, e = data.windows[k]
        t = data.t_s[s:e] - data.t_s[s]
        lab = labels[k]
        a = "xyz".index(lab["axis"])
        sgn = 1.0 if lab["sign"] > 0 else -1.0
        level = max(lab["speed_mps"], 1e-9)
        ax.step(t, sgn * data.cmd_mps[s:e, a] / level, where="post", color=figs.INK2, lw=1.2, ls="--")
        ax.plot(t, sgn * data.vel_mps[s:e, a] / level, color=figs.INK, lw=1.8, label="measured")
        ax.plot(t, sgn * models[kept][s:e, a] / level, color=color[kept], lw=1.8, label=f"{kept} model")
        figs.style(ax, f"{k}: {lab['axis']} {'+' if sgn > 0 else '-'}{lab['speed_mps']:.2f} m/s, "
                       f"{'train' if k in train else 'held out'}", "vehicle s", "v / command" if k % ncol == 0 else "")
        ax.title.set_fontsize(10)
    handles, names = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, names, frameon=False, fontsize=9, labelcolor=figs.INK, loc="upper right", ncol=2)
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.35 / (2.6 * nrow + 0.4)))
    fig.savefig(out_dir / f"{prefix}all_steps.png")
    plt.close(fig)
    fr = step_fractions(data, labels, models[kept])
    peaks = [x["peak"] for x in fr]
    at_release = [x["at_release"] for x in fr]
    after = [x["after_min"] for x in fr]
    out.append({"file": f"{prefix}all_steps.png", "caption": (
        f"Every detected step, train and held out, as a fraction of the commanded speed (dashed); black is measured, "
        f"colour is the kept {kept} model fitted on the train steps only. The measured speed peaks at {min(peaks):.0%} "
        f"to {max(peaks):.0%} of the command and is at {min(at_release):.0%} to {max(at_release):.0%} when the command "
        f"is released. After the release its lowest value is {np.nanmin(after):.0%} to {np.nanmax(after):.0%} of the "
        "command (below zero means it moves back the other way).")})
    return out


# ----------------------------------------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv-dir", required=True)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--ulog", help="the drone's PX4 ulog of the session (read-only): time scale from its flight span")
    src.add_argument("--time-scale", type=float, help="inject the time scale (vehicle s per wall s), e.g. for tests")
    ap.add_argument("--name", required=True, help="<YYYY-MM-DD>_s1_fit_v<k>; writes params/airstack_sim_v<k>.toml")
    ap.add_argument("--gates", required=True, help="configs/s1.toml ([fit_gates])")
    ap.add_argument("--steps-json", help="virtual_stick.py plan: labels the segments (must match their number)")
    ap.add_argument("--family", choices=[*FAMILIES, "best"], default="best")
    ap.add_argument("--dt-s", type=float, default=0.01, help="vehicle-time grid of the fit (s)")
    ap.add_argument("--speed-cap-mps", type=float, default=2.0, help="FIXED: teleop_max_speed_mps of the session")
    ap.add_argument("--out-root", default=str(ROOT), help="folder holding params/, records/, docs/figures/ (default svg_training)")
    a = ap.parse_args(argv)

    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})_s1_fit_v(\d+)", a.name)
    if not m:
        print(f"--name must be <YYYY-MM-DD>_s1_fit_v<k>, got {a.name!r}", file=sys.stderr)
        return 2
    version = int(m.group(2))
    out_root = Path(a.out_root)
    params_path = out_root / "params" / f"airstack_sim_v{version}.toml"
    record_path = out_root / "records" / f"{a.name}_record.md"
    ledger_path = out_root / "records" / "LEDGER.md"
    fig_dir = out_root / "docs" / "figures"
    try:
        ledger_text = ledger_path.read_text()
    except OSError as e:
        print(f"unreadable input: {e}", file=sys.stderr)
        return 1
    tn = max((int(x) for x in re.findall(r"^\| T(\d+) \|", ledger_text, flags=re.M)), default=0) + 1
    prefix = f"s1_t{tn}_"
    for p in (params_path, record_path, *sorted(fig_dir.glob(f"{prefix}*"))):
        if p.exists():
            print(f"refusing to overwrite {p}", file=sys.stderr)
            return 1

    csv_dir = Path(a.csv_dir)
    try:
        gates_bytes = Path(a.gates).read_bytes()
        gates = tomllib.loads(gates_bytes.decode())["fit_gates"]
        cmd_csv = _read_csv(csv_dir / f"{fitmod.TELEOP}.csv")
        od = _read_csv(csv_dir / "odometry.csv")
        manifest = json.loads((csv_dir / "manifest.json").read_text()) if (csv_dir / "manifest.json").is_file() else {}
        plan = json.loads(Path(a.steps_json).read_text())["steps"] if a.steps_json else None
    except (OSError, ValueError, KeyError) as e:
        print(f"unreadable input: {e}", file=sys.stderr)
        return 1

    # ---- odometry: strictly increasing stamps, body -> world
    keep = _increasing(od["t_wall_s"])
    dropped = len(od["t_wall_s"]) - keep.size
    t_od = od["t_wall_s"][keep]
    pos = np.stack([od[c][keep] for c in ("x", "y", "z")], axis=1)
    v_body = np.stack([od[c][keep] for c in ("vx", "vy", "vz")], axis=1)
    q = np.stack([od[c][keep] for c in ("qw", "qx", "qy", "qz")], axis=1)
    v_world = body_to_world(v_body, q)
    kc = _increasing(cmd_csv["t_wall_s"])
    t_cmd = cmd_csv["t_wall_s"][kc]
    cmd = np.stack([cmd_csv[c][kc] for c in ("vx", "vy", "vz")], axis=1)

    # ---- time scale and its cross-check
    try:
        deriv = derivative_check(t_od, pos, v_body, q)
    except ValueError as e:
        print(f"no position-derivative cross-check: {e}", file=sys.stderr)
        return 2
    ts = {"derivative": deriv, "commander": _commander_span(csv_dir / "commander_status.csv")}
    if a.ulog:
        try:
            u = ulog_time_scale(a.ulog, t_od, pos[:, 2])
        except (OSError, ValueError) as e:
            print(f"cannot read the time scale from {a.ulog}: {e}", file=sys.stderr)
            return 1
        scale = u["scale"]
        ts.update(ulog=u, source=f"ulog {a.ulog}", pyulog=_pyulog_arm_disarm(Path(a.ulog)),
                  method=f"PX4 vehicle_local_position takeoff -> touchdown (height > ground + {HEIGHT_THRESHOLD_M} m, "
                         "inside the ulog's arm -> disarm) over the same events in the bag odometry (wall)")
    else:
        scale = float(a.time_scale)
        ts.update(ulog=None, source="injected (--time-scale)", pyulog=None, method="given on the command line")
    ts["value"] = scale
    ts["rel_diff"] = scale / deriv["gain"] - 1.0
    if not abs(ts["rel_diff"]) <= SCALE_TOLERANCE:
        print(f"time scale {scale:.4f} ({ts['source']}) and position-derivative gain {deriv['gain']:.4f} differ by "
              f"{100 * ts['rel_diff']:+.1f} % (limit {100 * SCALE_TOLERANCE:.0f} %): stopped, nothing fitted or written",
              file=sys.stderr)
        return 3

    # ---- grid, segments, split
    t0 = float(t_cmd[0])
    t, c_grid, v_grid = fitmod.resample_uniform(fitmod.to_vehicle_time(t_cmd, scale, t0), cmd,
                                                fitmod.to_vehicle_time(t_od, scale, t0), v_world, dt_s=a.dt_s)
    data = fitmod.step_data(c_grid, v_grid, t, source=fitmod.TELEOP)
    n = len(data.windows)
    labels = _labels(data)
    if plan is not None:
        if len(plan) != n:
            print(f"--steps-json has {len(plan)} steps but {n} were detected: stopped", file=sys.stderr)
            return 2
        for lab, s in zip(labels, plan):
            lab.update(axis=s["axis"], sign=int(s["sign"]), speed_mps=float(s["speed_mps"]), repeat=s.get("repeat"))
    if n < 2:
        print(f"{n} step(s) detected: need at least 2 (one train, one held out)", file=sys.stderr)
        return 2
    train, held = fitmod.split_alternate(n)

    # ---- fit both families, score held out
    fits = {}
    for fam in FAMILIES:
        p, rep = fitmod.fit(c_grid, v_grid, t, fam, train, source=fitmod.TELEOP, speed_cap_mps=a.speed_cap_mps)
        ev = fitmod.evaluate(p, data, held)
        pooled = float(np.sqrt(np.mean(np.concatenate(
            [np.sum((simulate(data.cmd_mps, data.dt_s, p, v0_mps=data.vel_mps[0])[s:e] - data.vel_mps[s:e]) ** 2, 1)
             for s, e in (data.windows[i] for i in held)]))))
        fits[fam] = {"p": p, "rep": rep, "ev": ev, "pooled_rms": pooled,
                     "sens": _sensitivity(p, data, train, rep["free_params"])}
    kept = min(FAMILIES, key=lambda f: fits[f]["ev"]["vel_rms_mps"]) if a.family == "best" else a.family
    k = fits[kept]
    p, ev = k["p"], k["ev"]
    not_identified = [nm for nm, v in k["sens"].items() if v < NOT_IDENTIFIED_MPS]

    lo, hi = gates["delay_range_s"]
    g = {
        "vel_rms_max_mps": (gates["vel_rms_max_mps"], ev["vel_rms_mps"], ev["vel_rms_mps"] <= gates["vel_rms_max_mps"]),
        "t63_err_max_s": (gates["t63_err_max_s"], ev["t63_err_s"], ev["t63_err_s"] <= gates["t63_err_max_s"]),
        "delay_range_s": ([lo, hi], p.delay_s, lo <= p.delay_s <= hi),
        "min_held_out_steps": (gates["min_held_out_steps"], len(held), len(held) >= gates["min_held_out_steps"]),
    }
    verdict = "PASS" if all(x[2] for x in g.values()) else "FAIL"
    date = datetime.now().astimezone().isoformat(timespec="seconds")
    sha = code_sha()
    bag = manifest.get("bag", "unknown")

    # ---- write: plots, parameter file, record, ledger (last)
    models = {f: simulate(data.cmd_mps, data.dt_s, fits[f]["p"], v0_mps=data.vel_mps[0]) for f in FAMILIES}
    rows = {f: {r["index"]: r for r in fits[f]["ev"]["steps"]} for f in FAMILIES}
    pngs = _plots(fig_dir, prefix, data, models, kept, held, rows, labels, train)

    ulog_sha = _sha256(a.ulog) if a.ulog else None
    params_tables = {
        "params": p.to_dict(),
        "fit": {"name": a.name, "date": date, "family": kept, "family_choice": a.family, "verdict": verdict,
                "train_steps": len(train), "held_out_steps": len(held),
                "held_out_vel_rms_worst_mps": ev["vel_rms_mps"], "held_out_t63_err_worst_s": ev["t63_err_s"],
                "code_sha": sha, "grid_dt_s": data.dt_s, "fixed_not_fitted": ["speed_cap_mps"],
                "not_identified": not_identified, "at_bound": k["rep"]["at_bound"],
                "record": f"records/{a.name}_record.md"},
        "source": {"simulator": "AirStack simulator (Isaac Sim + Pegasus + PX4 SITL)", "bag": bag,
                   "csv_dir": str(csv_dir), "ulog": str(a.ulog) if a.ulog else "none",
                   "ulog_sha256": ulog_sha or "none"},
        "time_scale": {"value": scale, "source": ts["source"], "method": ts["method"],
                       "derivative_gain": deriv["gain"], "rel_diff_vs_derivative": ts["rel_diff"],
                       "ported_from": [f"{s} (git blob {_git_blob(REPO / s)})" for s in TOOL_SOURCES]},
    }
    header = (f"# Response model airstack_sim_v{version}: fitted to the AirStack simulator. SIM ONLY: never for the real "
              "drone (repository iron rule 9).\n# Load with ResponseParams.from_dict(tomllib.load(f)[\"params\"]). "
              f"Verdict {verdict}: see {params_tables['fit']['record']}.")
    params_path.parent.mkdir(parents=True, exist_ok=True)
    params_path.write_text(_toml(params_tables, header))

    record = _record(a, version, date, sha, gates_bytes, bag, manifest, csv_dir, ulog_sha, ts, dropped, data, labels,
                     train, held, fits, kept, g, verdict, not_identified, pngs, fig_dir, out_root, params_path)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(record)
    row = (f"| T{tn} | {date} | AirStack simulator, one drone | {a.name} | S1 response fit v{version} "
           f"({kept}, {len(held)} held-out steps) | {verdict} | records/{a.name}_record.md |")
    if not ledger_text.endswith("\n"):
        ledger_text += "\n"
    ledger_path.write_text(ledger_text + row + "\n")
    print(f"wrote {params_path}, {record_path}, {len(pngs)} plots; ledger T{tn}; kept {kept}; overall {verdict}")
    return 0


TERMS = [
    "- **Time scale**: how many seconds pass on the simulated drone's own clock (vehicle time) for each second of "
    "wall-clock time. The simulator runs faster than the wall clock, and the recording is stamped in wall time.",
    "- **lag1 and lag2** (the two model shapes, or families): lag1 is a short wait (the delay) followed by one smooth "
    "catch-up curve towards the asked-for speed (a first-order lag with time constant tau). lag2 adds a second smooth "
    "catch-up stage after the first (time constant tau2).",
    "- **Train and held out**: train steps are the ones the fit sees. Held-out steps are kept aside and never used for "
    "fitting; the gates are judged on them only.",
    "- **RMS** (root mean square): the typical size of the gap between the model's speed and the measured speed over a "
    "step, in m/s.",
    "- **t63**: the time to reach 63 % of the change in speed after a step starts. The gate compares the model's t63 "
    "with the measured one."]
PARAM_WORDS = ("Parameters: delay_s is the wait before the drone reacts; tau_xy_s and tau_z_s are the time constants of "
               "the catch-up curve, sideways and up/down; tau2_s is lag2's second stage; acc_max_* is the largest "
               "acceleration the model allows; speed_cap_mps caps the asked-for speed.")
GATE_WORDS = {"vel_rms_max_mps": "typical speed error, worst held-out step (m/s)",
              "t63_err_max_s": "t63 error, worst held-out step (s)",
              "delay_range_s": "fitted delay (s)",
              "min_held_out_steps": "number of held-out steps"}


def _axes(labels, idx) -> str:
    axes = sorted({labels[i]["axis"] for i in idx})
    if not axes:
        return "no axis"
    return axes[0] if len(axes) == 1 else ", ".join(axes[:-1]) + " and " + axes[-1]


def _split_sentence(labels, train, held) -> str:
    """Which axes the split put in training and in the held-out set; flags a held-out set that misses an axis."""
    s = (f"This put the {len(train)} training steps on {_axes(labels, train)} and the {len(held)} held-out steps on "
         f"{_axes(labels, held)}")
    missing = sorted({lab["axis"] for lab in labels} - {labels[i]["axis"] for i in held})
    if missing:
        s += f", so the held-out result does not test {' or '.join(missing)}"
    return s + "."


def _optimiser_words(opt: dict) -> str:
    st, n = opt["status"], opt["nfev"]
    if st == 0:
        return f"stopped at its {n:,}-evaluation limit, not converged (status 0)"
    if st < 0:
        return f"failed after {n:,} evaluations (status {st})"
    return f"converged after {n:,} evaluations (status {st})"


def _reading(data, labels, train, fits, kept) -> list[str]:
    """Measured facts only: the speed reached per step as a fraction of the command, and the optimiser outcome."""
    fr = step_fractions(data, labels, simulate(data.cmd_mps, data.dt_s, fits[kept]["p"], v0_mps=data.vel_mps[0]))
    L = ["Measured speed along each step's axis as a fraction of the command (100 % = the asked-for speed; below "
         f"zero = moving the other way), next to the kept {kept} model's peak.", "",
         f"| # | Split | Measured peak | At release | Lowest after release | {kept} model peak |", "|---|---|---|---|---|---|"]
    for k, x in enumerate(fr):
        after = "-" if math.isnan(x["after_min"]) else f"{x['after_min']:.0%}"
        L.append(f"| {k} | {'train' if k in train else 'held out'} | {x['peak']:.0%} | {x['at_release']:.0%} | "
                 f"{after} | {x['model_peak']:.0%} |")
    not_conv = [f for f in FAMILIES if fits[f]["rep"]["optimizer"]["status"] <= 0]
    facts = (f"Across the {len(fr)} steps the measured peak is {min(x['peak'] for x in fr):.0%} to "
             f"{max(x['peak'] for x in fr):.0%} of the command and the value at release is "
             f"{min(x['at_release'] for x in fr):.0%} to {max(x['at_release'] for x in fr):.0%}.")
    opt = (f" The optimiser did not converge for {' and '.join(not_conv)} (see the fit table)." if not_conv else
           " The optimiser converged for both families.")
    delay = fits[kept]["p"].delay_s
    dl = (f" The kept model's delay is {delay:.4f} s, close to zero, so the delay check says little about the true "
          "delay." if delay < 0.01 else "")
    return L + ["", facts + opt + dl]


def _record(a, version, date, sha, gates_bytes, bag, manifest, csv_dir, ulog_sha, ts, dropped, data, labels, train,
            held, fits, kept, g, verdict, not_identified, pngs, fig_dir, out_root, params_path) -> str:
    session = Path(bag).name if bag != "unknown" else str(csv_dir)
    d = ts["derivative"]
    L = [f"{FIRST_LINE}; session {session}", "", f"# {date} {a.name} record", "", "## Purpose", "",
         "Fit a simple model of how the drone's speed follows the speed a policy asks for (the response model: teleop "
         "command -> measured velocity) to one session observed in the AirStack simulator. Two model shapes were fitted "
         f"and the {'better' if a.family == 'best' else 'requested'} one was judged against the fixed gates. "
         f"Overall result: **{verdict}**."]
    failed = [n for n, x in g.items() if not x[2]]
    if verdict == "FAIL":
        L += ["", f"Failed gates: {', '.join(failed)}. The parameter file is written all the same: "
              f"`airstack_sim_v{version}` is a parameter set fitted to the AirStack simulator. It has not passed the fit "
              "gates, and it has not been compared with the placeholder model."]
    L += ["", "## Terms used here", "", *TERMS]
    L += ["", "## Code version", "", f"code_sha (first 12 hex of a sha256 over source/, scripts/, configs/): `{sha}`", "",
          "## Config", "", f"`{a.gates}` `[fit_gates]` (FIXED, approved), sha256 `{hashlib.sha256(gates_bytes).hexdigest()}`", "",
          "## Inputs", "",
          f"- Bag: `{bag}` (extracted by {manifest.get('script', '?')}, sha256 `{manifest.get('script_sha256', '?')}`)",
          f"- CSVs: `{csv_dir}`; command = `{fitmod.TELEOP}` (what a policy sends); {dropped} odometry rows dropped "
          "(repeated or backward stamps)",
          f"- Ulog: `{a.ulog}` (read-only), sha256 `{ulog_sha}`" if a.ulog else "- Ulog: none (time scale injected)",
          f"- Grid: {data.dt_s:.3f} s of vehicle time; speed cap {fits[kept]['p'].speed_cap_mps} m/s (FIXED, not fitted)",
          "", "## Time scale — MEASURED", "",
          "Vehicle seconds per wall second (bag stamps are wall time).", "",
          "| Method | Value | Detail |", "|---|---|---|"]
    u = ts["ulog"]
    if u:
        L.append(f"| ulog flight span (USED) | {ts['value']:.4f} | PX4 takeoff -> touchdown {u['span_vehicle_s']:.2f} s "
                 f"(vehicle {u['takeoff_vehicle_s']:.2f} -> {u['touchdown_vehicle_s']:.2f}) over bag "
                 f"{u['span_wall_s']:.2f} s (wall); height threshold {HEIGHT_THRESHOLD_M} m |")
        arm_span = u["disarm_s"] - u["arm_s"]
        if ts["commander"]:
            ca, ci = ts["commander"]
            L.append(f"| ulog arm -> disarm over commander ARMING -> IDLE (coarse, not used) | {arm_span / (ci - ca):.4f} | "
                     f"PX4 {u['arm_s']:.3f} -> {u['disarm_s']:.3f} s = {arm_span:.2f} s; commander states at 5 Hz, "
                     f"{ci - ca:.2f} s wall; ARMING starts before PX4 arms |")
        if ts["pyulog"]:
            pa, pd_ = ts["pyulog"]
            L.append(f"| reader check | - | pyulog dump next to the ulog: arm {pa:.6f}, disarm {pd_:.6f}; this reader: "
                     f"{u['arm_s']:.6f}, {u['disarm_s']:.6f} |")
    else:
        L.append(f"| injected (USED) | {ts['value']:.4f} | --time-scale |")
    L += [f"| position-derivative gain (cross-check) | {d['gain']:.4f} | d(position)/d(wall t) against the rotated "
          f"velocity, {d['n_samples']} samples moving >= {MOVING_MPS} m/s |", "",
          f"Used / derivative gain - 1 = {100 * ts['rel_diff']:+.2f} % (stop limit ±{100 * SCALE_TOLERANCE:.0f} %). "
          f"Ported logic: {', '.join(TOOL_SOURCES)} (git blobs in the parameter file); ULog read by the reader in "
          "scripts/fit_response.py (pyulog is not on the host).", "",
          "## Odometry frame — MEASURED", "",
          "The odometry twist is in the body frame; it is rotated to world ENU with the odometry attitude before fitting. "
          f"Mean cosine with d(position)/dt over moving samples: rotated {d['cos_rotated']:.3f}, "
          f"as published {d['cos_as_published']:.3f}.", "",
          "## Segments", "",
          "Detected where the teleop command leaves rest (|cmd| >= 0.2 m/s); split: even train, odd held out. "
          + _split_sentence(labels, train, held), "",
          "| # | Axis | Sign | Speed (m/s) | Start (vehicle s) | Hold (vehicle s) | Split |", "|---|---|---|---|---|---|---|"]
    for i, lab in enumerate(labels):
        L.append(f"| {i} | {lab['axis']} | {'+' if lab['sign'] > 0 else '-'} | {lab['speed_mps']:.2f} | "
                 f"{lab['start_s']:.2f} | {lab['hold_s']:.2f} | {'train' if i in train else 'held out'} |")
    L += ["", "## Fit, both families — MEASURED (fitted)", "",
          "| Parameter | " + " | ".join(f + (" (kept)" if f == kept else "") for f in FAMILIES) + " |",
          "|---|" + "---|" * len(FAMILIES)]
    for nm in ("delay_s", "tau_xy_s", "tau_z_s", "acc_max_xy_mps2", "acc_max_z_mps2", "tau2_s", "speed_cap_mps"):
        cells = []
        for f in FAMILIES:
            fr = fits[f]
            v = fr["p"].to_dict()[nm]
            flag = []
            if nm in fr["rep"]["at_bound"]:
                flag.append("at bound")
            if nm in fr["sens"] and fr["sens"][nm] < NOT_IDENTIFIED_MPS:
                flag.append("not identified")
            if nm == "tau2_s" and f == "lag1":
                cells.append("- (lag1)")
            else:
                cells.append(f"{v:.4g}" + (f" ({', '.join(flag)})" if flag else ""))
        L.append(f"| {nm} | " + " | ".join(cells) + " |")
    for label, key in (("held-out velocity RMS, worst step (m/s)", "vel_rms_mps"),
                       ("held-out t63 error, worst step (s)", "t63_err_s")):
        L.append(f"| {label} | " + " | ".join(_f(fits[f]["ev"][key]) for f in FAMILIES) + " |")
    L.append("| held-out velocity RMS, pooled (m/s) | " + " | ".join(_f(fits[f]["pooled_rms"]) for f in FAMILIES) + " |")
    L.append("| training velocity RMS (m/s) | " + " | ".join(_f(fits[f]["rep"]["optimizer"]["rms_train_mps"])
                                                            for f in FAMILIES) + " |")
    L.append("| optimiser | " + " | ".join(_optimiser_words(fits[f]["rep"]["optimizer"]) for f in FAMILIES) + " |")
    rms = {f: fits[f]["ev"]["vel_rms_mps"] for f in FAMILIES}
    if a.family != "best":
        why = f"Kept: **{kept}** (requested)."
    elif len({f"{v:.3f}" for v in rms.values()}) == 1:
        why = (f"Kept: **{kept}**. The two families tie on held-out RMS to 3 decimals ({rms[kept]:.3f} m/s), so the "
               "choice between them is arbitrary here.")
    else:
        why = f"Kept: **{kept}** (lower held-out RMS)."
    L += ["", PARAM_WORDS, "", why + " 'Not identified': raising "
          f"the parameter by 25 % moves the model over the training windows by less than {NOT_IDENTIFIED_MPS} m/s RMS, "
          "so the session does not determine it; its value is the optimiser's start.", "",
          f"## Gates — limits FIXED, observed MEASURED ({kept}, held-out steps only, vehicle time)", "",
          "| Gate | Limit | Observed | Result |", "|---|---|---|---|"]
    for nm, (lim, obs, ok) in g.items():
        o = str(obs) if isinstance(obs, int) else _f(obs, 4 if nm == "delay_range_s" else 3)
        lim_s = (f"[{lim[0]:.2f}, {lim[1]:.2f}]" if isinstance(lim, list) else
                 str(lim) if isinstance(lim, int) else f"{lim:.2f}")
        L.append(f"| {nm}: {GATE_WORDS.get(nm, nm)} | {lim_s} | {o} | {'PASS' if ok else 'FAIL'} |")
    L += ["", "## Reading", "", *_reading(data, labels, train, fits, kept)]
    L += ["", "## Held-out steps", "",
          "| # | Axis | Step (m/s) | " + " | ".join(f"{f} RMS (m/s)" for f in FAMILIES) +
          " | t63 measured (s) | " + " | ".join(f"{f} t63 (s)" for f in FAMILIES) + " | Plot |",
          "|---|---|---|" + "---|" * (2 * len(FAMILIES) + 2)]
    rows = {f: {r["index"]: r for r in fits[f]["ev"]["steps"]} for f in FAMILIES}
    for i, png in zip(held, pngs):
        r0 = rows[kept][i]
        link = f"../{fig_dir.relative_to(out_root).as_posix()}/{png['file']}"
        L.append(f"| {i} | {r0['axis']} | {r0['step_mps']:+.2f} | " +
                 " | ".join(_f(rows[f][i]["vel_rms_mps"]) for f in FAMILIES) + f" | {_f(r0['t63_meas_s'])} | " +
                 " | ".join(_f(rows[f][i]["t63_model_s"]) for f in FAMILIES) +
                 f" | [{png['file']}]({link}) |")
    L += ["", "## Figures", "", "Made by this run from its own data (measured odometry, rotated to world, against the "
          "fitted models on the same vehicle-time grid).", ""]
    for k, png in enumerate(pngs, 1):
        L += [f"![Figure {k}](../{fig_dir.relative_to(out_root).as_posix()}/{png['file']})", "",
              f"*Figure {k}.* {png['caption']}", ""]
    L += ["## Outputs", "", f"- Parameter file: `{params_path.relative_to(out_root)}`",
          f"- Figures: `{fig_dir.relative_to(out_root).as_posix()}/` ({', '.join(x['file'] for x in pngs)})", "",
          "## Limits of this record", "",
          "- Numbers were observed in the AirStack simulator; nothing here is a flight result. The parameters are "
          "simulator parameters and never go to the drone (repository iron rule 9).",
          "- One time scale for the whole session (constant-rate assumption; drift within the session is not measured "
          "here). The model has no commander P term on the leashed reference and no up/down asymmetry.",
          "- The held-out split is fixed (alternate segments), not chosen after seeing the results. "
          + _split_sentence(labels, train, held)]
    if not_identified:
        L.append(f"- Not identified by this session ({kept}): {', '.join(not_identified)}.")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())
