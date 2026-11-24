#!/usr/bin/env python3
"""INFO held-out check of tier 1's drone model against one continuous real-flight mission (the 24 Nov figure eight). No refit.

Usage (from svg_training/):
    python scripts/fig8_check.py \
        --bag ~/AirStack-starling-max2/svg_training/flight_logs/starlingmax2/bags/svg_20261124_073433 \
        --params params/real_exploratory_v0.toml --out records/evidence/2026-11-24_fig8_heldout

What it does (it reuses scripts/bag_check.py: its bag reader, its setpoint-to-grid rules, its baselines and its shift
search; bag_check itself is unchanged)
  1. Reads the bag read-only with bag_check.load_bag: per drone the trajectory setpoint PX4 received
     (/drone_N/fmu/in/trajectory_setpoint: position, velocity, acceleration) and PX4's own estimate
     (/drone_N/fmu/out/vehicle_local_position), NED -> ENU. Time zero is bag_check's: the first message of those topics
     (not the bag's first message; on 24 Nov that is 0.39 s later than /rosout).
  2. Window: the mission, from the first /svg/commander_status whose last command is "start" to the first after it whose
     last command is "hold" (--start-command / --end-command), or --window-s A B in bag_check seconds.
  3. Primary replay = bag_check's own method, so the numbers sit beside the 12 Nov check: setpoint held onto a 0.01 s
     grid, acceleration feed-forward derived from the held speed setpoint, the model (px4_trajectory.simulate, [px4]
     table of the parameter file AS WRITTEN) started once from the measured position and speed at the window start and
     flown across the whole window (one open-loop window, not short restarted legs). Horizontal only (x east, y north):
     the reference model has no fitted vertical channel. Estimate error (STE L1.7) off: the replay is deterministic.
  4. Each measured sample is labelled with the latest /svg/cbf_active message (20 Hz; comma-separated drone names): the
     drone is "filter on" when its own name is listed, "filter off" when not; a sample with no message in the last
     0.25 s is "unknown" (in "all" only). The setpoint is the commander's output after the filter in both classes, so the
     split tests PX4's response to filter-shaped setpoints, not the filter.
  5. Per subset (all, filter_on, filter_off): RMS of model - measured per axis and both axes together (bag_check's
     convention: sqrt of the mean over both components); baselines (the setpoint speed, and the same 0.15 s later); best
     extra shift of the model in bag_check's range [-0.10, 0.30] s and the RMS after it; information: the same search
     over [-0.30, 0.80] s. Reading words per pre-registered metric against the 12 Nov record (REF_12NOV).
  6. Information-only variants, named before the run: the logged acceleration field instead of the derived one (what
     PX4 received), the setpoint joined by lines (as the S1 fit), and the model restarted every 5 s from the measured
     state (1 s run-in, unscored), like bag_check's short legs.
  7. Writes <out>/metrics.json and <out>/fig8_heldout.png. No record, no ledger row (written by hand), nothing under
     params/.
Exit codes: 0 done; 1 unreadable input or no mission window; 2 bad arguments.
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import tomllib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bag_check as bc  # noqa: E402
from svg_training.logs.mcap_reader import iter_messages, list_topics  # noqa: E402
from svg_training.models import px4_trajectory as m  # noqa: E402

STATUS_TOPIC, CBF_TOPIC = "/svg/commander_status", "/svg/cbf_active"
DT_S = bc.DT_S
SHIFTS_S = bc.SHIFTS_S                                          # [-0.10, 0.30] s, bag_check's search
WIDE_SHIFTS_S = np.round(np.arange(-0.30, 0.8001, 0.01), 2)     # information only
CBF_STALE_S = 0.25
SEGMENT_S, RUN_IN_S = 5.0, 1.0
FIT_RANGE_MPS = 0.5                                             # the fit's (13 Nov) and the 12 Nov check's top speed
SUBSETS = ("all", "filter_on", "filter_off")

# The 12 Nov held-out check (records/2026-11-15_s2_bag_check_record.md, Results): the lowest and highest number its
# record gives for each metric across drone_1 (1 leg) and drone_2 (4 legs). Pre-registered 24 Nov 2026, before the run.
REF_12NOV = {
    "model_rms_mps": (0.029, 0.120),          # pooled 0.029 (drone_1), 0.093 (drone_2); worst leg 0.120 (drone_2)
    "best_shift_s": (-0.10, 0.06),            # drone_2 -0.10 (search edge), drone_1 +0.06
    "rms_after_shift_mps": (0.028, 0.085),    # drone_1 0.028, drone_2 0.085
    "model_over_setpoint": (0.78, 1.03),      # pooled model / pooled setpoint-speed RMS: 0.029/0.037, 0.093/0.090
}
READING_METRICS = {                           # results key -> REF_12NOV key
    "model.rms_both_mps": "model_rms_mps", "model.rms_x_mps": "model_rms_mps", "model.rms_y_mps": "model_rms_mps",
    "best_shift_s": "best_shift_s", "rms_after_shift_mps": "rms_after_shift_mps",
    "model_over_setpoint": "model_over_setpoint",
}


def reading_word(x: float, rng: tuple[float, float]) -> str:
    if x is None or not math.isfinite(x):
        return "no number"
    lo, hi = rng
    if lo - 1e-9 <= x <= hi + 1e-9:
        return "inside the 12 Nov check's range"
    return f"outside the 12 Nov check's range ({'below' if x < lo else 'above'})"


# ------------------------------------------------------------------------------------------------ reading the bag
def ros_string(data: bytes) -> str:
    """std_msgs/String CDR payload -> text (4-byte encapsulation header, uint32 length with the NUL, bytes)."""
    n = struct.unpack_from("<I", data, 4)[0]
    return data[8:8 + max(n - 1, 0)].decode(errors="replace")


def bag_zero_ns(mcap_path: Path) -> int:
    """bag_check.load_bag's time zero: the first message of any of its setpoint and local-position topics."""
    topics = list_topics(mcap_path)
    wanted = {f"/{d}/fmu/{k}" for d in bc.DRONES for k in ("in/trajectory_setpoint", "out/vehicle_local_position")}
    wanted &= set(topics)
    first: dict[str, int] = {}
    for msg in iter_messages(mcap_path, wanted):
        first.setdefault(msg.topic, msg.log_time_ns)
        if len(first) == len(wanted):
            break
    if not first:
        raise ValueError("no setpoint or local-position topic in the bag")
    return min(first.values())


def load_events(mcap_path: Path, zero_ns: int) -> dict:
    """{"commands": [(t_s, name)], "cbf_t": (K,), "cbf_names": [frozenset]} in bag_check seconds."""
    topics = set(list_topics(mcap_path))
    cmds, cbf_t, cbf = [], [], []
    last = None
    for msg in iter_messages(mcap_path, {STATUS_TOPIC, CBF_TOPIC} & topics):
        t = (msg.log_time_ns - zero_ns) * 1e-9
        text = ros_string(msg.data)
        if msg.topic == STATUS_TOPIC:
            try:
                lc = json.loads(text).get("last_command") or {}
            except (json.JSONDecodeError, AttributeError):
                continue
            key = (lc.get("seq"), lc.get("name"))
            if lc.get("name") and key != last:
                cmds.append((t, lc["name"]))
                last = key
        else:
            cbf_t.append(t)
            cbf.append(frozenset(x.strip() for x in text.split(",") if x.strip()))
    order = np.argsort(cbf_t, kind="stable")
    return {"commands": sorted(cmds), "cbf_t": np.asarray(cbf_t, float)[order], "cbf_names": [cbf[i] for i in order]}


def mission_window(events: dict, start_cmd: str, end_cmd: str) -> tuple[float, float]:
    starts = [t for t, n in events["commands"] if n == start_cmd]
    if not starts:
        raise ValueError(f"no '{start_cmd}' command in {STATUS_TOPIC}")
    ends = [t for t, n in events["commands"] if n == end_cmd and t > starts[0]]
    if not ends:
        raise ValueError(f"no '{end_cmd}' command after '{start_cmd}' in {STATUS_TOPIC}")
    return starts[0], ends[0]


def filter_state(events: dict, drone: str, t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(on, known) per time: the latest /svg/cbf_active message at or before t lists `drone` (exact name match)."""
    ct = events["cbf_t"]
    if ct.size == 0:
        return np.zeros(t.shape, bool), np.zeros(t.shape, bool)
    idx = np.searchsorted(ct, t, side="right") - 1
    known = (idx >= 0) & (t - ct[np.clip(idx, 0, None)] <= CBF_STALE_S)
    on = np.array([drone in events["cbf_names"][i] if i >= 0 else False for i in idx], bool)
    return on & known, known


def runs_of(t: np.ndarray, on: np.ndarray) -> dict:
    """Count and lengths (s) of the stretches where `on` is true."""
    if not on.any():
        return {"count": 0, "lengths_s": []}
    edges = np.diff(np.r_[0, on.astype(int), 0])
    s, e = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1) - 1
    lengths = [float(t[b] - t[a]) for a, b in zip(s, e)]
    return {"count": int(len(s)), "lengths_s": [round(x, 2) for x in lengths],
            "median_s": round(float(np.median(lengths)), 2), "max_s": round(max(lengths), 2)}


# ------------------------------------------------------------------------------------------------ windows
def build_window(f: dict, lo: float, hi: float, setpoint: str = "hold", accel: str = "derived"):
    """(Window, measured times, measured positions) for [lo, hi] (bag_check seconds); None if too few samples or outside
    the setpoint stream."""
    ok = np.isfinite(f["t_lp"]) & np.isfinite(f["p"]).all(axis=1) & np.isfinite(f["v"]).all(axis=1)
    t_lp, p_lp, v_lp = f["t_lp"][ok], f["p"][ok], f["v"][ok]
    j = np.flatnonzero((t_lp >= lo) & (t_lp <= hi))
    if j.size < bc.MIN_MEAS or not (lo >= f["t_sp"][0] and hi <= f["t_sp"][-1] + 0.5):
        return None
    t0 = t_lp[j[0]]
    n = int(round((t_lp[j[-1]] - t0) / DT_S)) + 1
    t = t0 + np.arange(n) * DT_S
    to_grid = bc.hold_to_grid if setpoint == "hold" else bc.interp_to_grid
    p_sp = to_grid(f["t_sp"], f["p_sp"], t)
    v_ff = to_grid(f["t_sp"], np.nan_to_num(f["v_ff"], nan=0.0), t)
    if accel == "derived":
        a_ff = np.gradient(v_ff, t, axis=0)
    else:
        a_ff = to_grid(f["t_sp"], np.nan_to_num(f["a_ff_logged"], nan=0.0), t)
    if not np.isfinite(p_sp).all():
        return None
    idx = np.clip(np.round((t_lp[j] - t0) / DT_S).astype(int), 0, n - 1)
    w = m.Window(t_s=t, p_sp=p_sp, v_ff=v_ff, a_ff=a_ff, p0=p_lp[j[0]].copy(), v0=v_lp[j[0]].copy(), meas_idx=idx,
                 v_meas=v_lp[j].copy())
    return w, t_lp[j], p_lp[j].copy()


def _predelayed(w: m.Window, tm: np.ndarray, pm: np.ndarray, t_start: float, delay_s: float):
    """The window from the first measurement at or after t_start, with its setpoint already delayed by delay_s on the
    longer grid (so the delayed inputs at the start carry their true history, not a held first value); simulate it with
    delay 0. Same law, same inputs as one long run."""
    j0 = int(np.searchsorted(tm, t_start - 1e-9))
    k0 = int(w.meas_idx[j0])
    d = lambda x: m.delay_signal(x, DT_S, delay_s)[k0:]                              # noqa: E731
    w2 = m.Window(t_s=w.t_s[k0:], p_sp=d(w.p_sp), v_ff=d(w.v_ff), a_ff=d(w.a_ff), p0=pm[j0].copy(),
                  v0=w.v_meas[j0].copy(), meas_idx=w.meas_idx[j0:] - k0, v_meas=w.v_meas[j0:])
    return w2, tm[j0:]


def make_parts(f: dict, lo: float, hi: float, variant: str, delay_s: float = 0.0) -> list[tuple]:
    """[(Window, measured times, scored mask, predelayed)] for a variant: primary / accel_logged / setpoint_linear (one
    window over [lo, hi]) or restarted_5s (a window every 5 s, each started 1 s early from the measured state, that 1 s
    unscored; its setpoint is delayed by delay_s on a grid that starts 0.5 s earlier still, see _predelayed)."""
    setpoint = "linear" if variant == "setpoint_linear" else "hold"
    accel = "logged" if variant == "accel_logged" else "derived"
    if variant != "restarted_5s":
        got = build_window(f, lo, hi, setpoint, accel)
        return [] if got is None else [(got[0], got[1], np.ones(got[1].shape, bool), False)]
    parts = []
    for a in np.arange(lo, hi, SEGMENT_S):
        got = build_window(f, max(a - RUN_IN_S - 0.5, f["t_sp"][0]), min(a + SEGMENT_S, hi), setpoint, accel)
        if got is None:
            continue
        w, tm = _predelayed(*got, max(a - RUN_IN_S, f["t_sp"][0]), delay_s)
        parts.append((w, tm, (tm >= a) & (tm < min(a + SEGMENT_S, hi) + 1e-9), True))
    return parts


# ------------------------------------------------------------------------------------------------ scoring
def _rms_axes(e: np.ndarray) -> dict:
    return {"rms_x_mps": bc._rms(e[:, 0]), "rms_y_mps": bc._rms(e[:, 1]), "rms_both_mps": bc._rms(e)}


def score_parts(parts: list[tuple], params: m.TrajectoryParams, on_known) -> dict:
    """Errors pooled over the parts' scored samples, per subset. on_known(t) -> (on, known)."""
    no_delay = m.replace(params, delay_s=0.0)
    vms = [m.simulate_window(no_delay if pre else params, w) for w, _tm, _sc, pre in parts]
    rows = {k: [] for k in ("model", "sp", "sp_delayed", "meas", "t", "on", "known")}
    shifted = {float(s): [] for s in np.union1d(SHIFTS_S, WIDE_SHIFTS_S)}
    for (w, tm, sc, _pre), vm in zip(parts, vms):
        meas = w.v_meas[sc]
        tq = tm[sc]
        rows["model"].append(bc._at(w.t_s, vm, tq) - meas)
        rows["sp"].append(bc._at(w.t_s, w.v_ff, tq) - meas)
        rows["sp_delayed"].append(bc._at(w.t_s, m.delay_signal(w.v_ff, DT_S, bc.DELAY_BASELINE_S), tq) - meas)
        rows["meas"].append(meas)
        rows["t"].append(tq)
        on, known = on_known(tq)
        rows["on"].append(on)
        rows["known"].append(known)
        for s in shifted:
            shifted[s].append(bc._at(w.t_s, vm, tq - s) - meas)
    if not parts:
        return {k: {"n_samples": 0} for k in SUBSETS}
    cat = {k: np.concatenate(v) for k, v in rows.items()}
    sh = {s: np.concatenate(v) for s, v in shifted.items()}
    masks = {"all": np.ones(cat["t"].shape, bool), "filter_on": cat["on"] & cat["known"],
             "filter_off": ~cat["on"] & cat["known"]}
    out = {}
    for name, mk in masks.items():
        if not mk.any():
            out[name] = {"n_samples": 0}
            continue
        r = {"n_samples": int(mk.sum()), "model": _rms_axes(cat["model"][mk]), "sp": _rms_axes(cat["sp"][mk]),
             "sp_delayed": _rms_axes(cat["sp_delayed"][mk])}
        r["model_over_setpoint"] = r["model"]["rms_both_mps"] / r["sp"]["rms_both_mps"]
        for key, grid in (("", SHIFTS_S), ("wide_", WIDE_SHIFTS_S)):
            by = {float(s): bc._rms(sh[float(s)][mk]) for s in grid}
            best = min(by, key=by.get)
            r[f"{key}best_shift_s"] = best
            r[f"{key}rms_after_shift_mps"] = by[best]
            r[f"{key}best_shift_at_edge"] = best in (float(grid[0]), float(grid[-1]))
            if not key:
                r["after_shift_axes"] = _rms_axes(sh[best][mk])
        speed = np.linalg.norm(cat["meas"][mk], axis=1)
        r["measured_speed_median_mps"] = float(np.median(speed))
        r["measured_speed_max_mps"] = float(speed.max())
        out[name] = r
    return out


def model_limits(w: m.Window, params: m.TrajectoryParams) -> dict:
    """Information: share of grid steps where the model sits on its acceleration limit or its speed cap."""
    v, p = m.simulate(w.p_sp, w.v_ff, w.a_ff, DT_S, params, p0=w.p0, v0=w.v0)
    P = m.delay_signal(w.p_sp, DT_S, params.delay_s)
    V = m.delay_signal(w.v_ff, DT_S, params.delay_s)
    vel_sp = V[:-1] + params.kp_xy * (P[:-1] - p[:-1])
    dv = np.linalg.norm(np.diff(v, axis=0), axis=1)
    return {"share_on_acc_limit": float(np.mean(dv >= 0.999 * params.acc_max_mps2 * DT_S)),
            "share_on_speed_cap": float(np.mean(np.linalg.norm(vel_sp, axis=1) >= 0.999 * params.vel_max_mps)),
            "acc_limit_mps2": params.acc_max_mps2, "speed_cap_mps": params.vel_max_mps}


def accel_stats(f: dict, lo: float, hi: float) -> dict:
    """Information: horizontal acceleration of the measured speed (slope over 0.1 s) and of the logged setpoint field."""
    sel = (f["t_lp"] >= lo) & (f["t_lp"] <= hi)
    t, v = f["t_lp"][sel], f["v"][sel]
    if t.size < 20:
        return {}
    tg = np.arange(t[0], t[-1], 0.1)
    vg = np.stack([np.interp(tg, t, v[:, 0]), np.interp(tg, t, v[:, 1])], axis=-1)
    a = np.linalg.norm(np.diff(vg, axis=0) / 0.1, axis=1)
    s = (f["t_sp"] >= lo) & (f["t_sp"] <= hi)
    a_sp = np.linalg.norm(np.nan_to_num(f["a_ff_logged"][s]), axis=1)
    return {"measured_acc_p50_mps2": float(np.percentile(a, 50)), "measured_acc_p95_mps2": float(np.percentile(a, 95)),
            "setpoint_acc_logged_p95_mps2": float(np.percentile(a_sp, 95)) if a_sp.size else math.nan,
            "setpoint_acc_logged_max_mps2": float(a_sp.max()) if a_sp.size else math.nan}


def reading(prim: dict) -> dict:
    out = {}
    for sub in SUBSETS:
        r = prim["subsets"].get(sub, {})
        if not r.get("n_samples"):
            continue
        for key, ref in READING_METRICS.items():
            x = r
            for part in key.split("."):
                x = x[part]
            out[f"{sub}.{key}"] = {"value": x, "range_12nov": list(REF_12NOV[ref]),
                                   "word": reading_word(x, REF_12NOV[ref])}
    return out


def score_drone(f: dict, params: m.TrajectoryParams, events: dict, drone: str, lo: float, hi: float) -> dict:
    on_known = lambda t: filter_state(events, drone, t)                               # noqa: E731
    res = {}
    for variant in ("primary", "accel_logged", "setpoint_linear", "restarted_5s"):
        parts = make_parts(f, lo, hi, variant, params.delay_s)
        res[variant] = {"windows": len(parts), "subsets": score_parts(parts, params, on_known)}
    prim_parts = make_parts(f, lo, hi, "primary")
    out = {"primary": res.pop("primary"), "variants": res}
    out["reading"] = reading(out["primary"])
    if prim_parts:
        w, tm, _, _ = prim_parts[0]
        on, known = on_known(tm)
        out["filter_runs"] = runs_of(tm, on)
        out["filter_share"] = float(on.mean())
        out["unknown_share"] = float((~known).mean())
        out["model_limits"] = model_limits(w, params)
        sp = np.linalg.norm(w.v_ff, axis=1)
        meas = np.linalg.norm(w.v_meas, axis=1)
        out["speeds"] = {"fit_range_mps": FIT_RANGE_MPS, "setpoint_max_mps": float(sp.max()),
                         "setpoint_median_mps": float(np.median(sp)), "measured_max_mps": float(meas.max()),
                         "measured_median_mps": float(np.median(meas)),
                         "share_measured_above_fit_range": float(np.mean(meas > FIT_RANGE_MPS)),
                         "above_fit_range": bool(meas.max() > FIT_RANGE_MPS)}
        out["accel"] = accel_stats(f, lo, hi)
    else:
        out["filter_runs"] = {"count": 0, "lengths_s": []}
    return out


# ------------------------------------------------------------------------------------------------ figure
def make_figure(flights: dict, params: m.TrajectoryParams, events: dict, lo: float, hi: float, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from make_s0_figures import INK, INK2, SERIES, style
    drones = [d for d in bc.DRONES if d in flights and make_parts(flights[d], lo, hi, "primary")]
    fig = plt.figure(figsize=(14, 3.4 * max(len(drones), 1) + 0.8), dpi=110)
    if not drones:
        fig.text(0.02, 0.5, "no mission window found", color=INK2)
    for r, d in enumerate(drones):
        w, tm, _, _ = make_parts(flights[d], lo, hi, "primary")[0]
        vm = m.simulate_window(params, w)
        on, _known = filter_state(events, d, tm)
        mid = lo + 0.5 * (hi - lo)
        for c, (xlim, comp, label) in enumerate((((lo, hi), None, "speed"), ((mid - 5, mid + 5), 0, "east speed"))):
            ax = fig.add_subplot(len(drones), 2, 2 * r + c + 1)
            for a, b in zip(*_spans(tm, on)):
                ax.axvspan(a, b, color=SERIES[4], alpha=0.13, linewidth=0)
            f_sp = (lambda x: np.linalg.norm(x, axis=1)) if comp is None else (lambda x: x[:, comp])  # noqa: E731
            ax.plot(w.t_s, f_sp(w.v_ff), color=SERIES[3], linewidth=1.1, label="setpoint speed")
            ax.plot(tm, f_sp(w.v_meas), color=SERIES[0], linewidth=1.0, label="real drone (PX4 estimate)")
            ax.plot(w.t_s, f_sp(vm), color=SERIES[1], linewidth=1.1, label="tier 1 model")
            ax.set_xlim(*xlim)
            style(ax, f"{d}: {label}" + (" (shaded: filter lists this drone)" if c == 0 else ", 10 s zoom"),
                  "bag time (s)", "m/s")
            ax.title.set_fontsize(10)
            if r == 0 and c == 0:
                ax.legend(frameon=False, fontsize=8, loc="lower right", labelcolor=INK)
    fig.suptitle("24 Nov figure eight: tier 1 model (not refitted) against the real drones, start to hold",
                 fontsize=11, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)


def _spans(t: np.ndarray, on: np.ndarray):
    edges = np.diff(np.r_[0, on.astype(int), 0])
    s, e = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1) - 1
    return t[s], t[e]


# ------------------------------------------------------------------------------------------------ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bag", type=Path, required=True)
    ap.add_argument("--params", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True, help="evidence folder: metrics.json and fig8_heldout.png")
    ap.add_argument("--window-s", type=float, nargs=2, metavar=("FROM", "TO"),
                    help="window in bag_check seconds (default: the start and hold commands)")
    ap.add_argument("--start-command", default="start")
    ap.add_argument("--end-command", default="hold")
    a = ap.parse_args(argv)
    try:
        cfg = tomllib.loads(a.params.read_text())
        params = m.TrajectoryParams.from_dict({k: v for k, v in cfg["px4"].items() if k != "model_dt_s"})
    except (OSError, KeyError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"bad parameter file: {exc}", file=sys.stderr)
        return 2
    try:
        mcap_path = bc.find_mcap(a.bag)
        flights = bc.load_bag(mcap_path)
        zero_ns = bag_zero_ns(mcap_path)
        events = load_events(mcap_path, zero_ns)
        if a.window_s:
            lo, hi = map(float, a.window_s)
            source = "--window-s"
        else:
            lo, hi = mission_window(events, a.start_command, a.end_command)
            source = f"commands {a.start_command} -> {a.end_command}"
    except (OSError, ValueError, KeyError) as exc:
        print(f"cannot read {a.bag}: {exc}", file=sys.stderr)
        return 1
    drones = {d: score_drone(flights[d], params, events, d, lo, hi) for d in bc.DRONES if d in flights}
    results = {"what": "INFO held-out check, no refit, no gates; observed in flight logs",
               "bag": mcap_path.name, "bag_sha256": bc.sha256_of(mcap_path),
               "bag_mb": round(mcap_path.stat().st_size / 1e6, 1),
               "params_file": str(a.params.name), "params_sha256": bc.sha256_of(a.params), "params": params.to_dict(),
               "time_zero_log_ns": zero_ns, "window_s": [round(lo, 3), round(hi, 3)],
               "window_epoch_s": [round(zero_ns * 1e-9 + lo, 3), round(zero_ns * 1e-9 + hi, 3)],
               "window_source": source, "commands": [[round(t, 3), n] for t, n in events["commands"]],
               "method": {"setpoint": "held on 0.01 s grid", "accel_ff": "derived (slope of held speed setpoint)",
                          "start": "measured position and speed at window start, one window",
                          "shift_search_s": [float(SHIFTS_S[0]), float(SHIFTS_S[-1])],
                          "wide_shift_search_s": [float(WIDE_SHIFTS_S[0]), float(WIDE_SHIFTS_S[-1])],
                          "estimate_error": "off", "axes": "horizontal (x east, y north)",
                          "rms_both": "sqrt of mean over both components (bag_check)",
                          "cbf_stale_s": CBF_STALE_S},
               "ref_12nov": {k: list(v) for k, v in REF_12NOV.items()},
               "drones": drones}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "metrics.json").write_text(json.dumps(bc._clean(results), indent=1))
    make_figure(flights, params, events, lo, hi, a.out / "fig8_heldout.png")
    brief = {d: {s: {k: r[s].get(k) for k in ("n_samples", "model", "best_shift_s", "rms_after_shift_mps",
                                              "model_over_setpoint")}
                 for s in SUBSETS for r in [x["primary"]["subsets"]]} for d, x in drones.items()}
    print(json.dumps(bc._clean({"window_s": [lo, hi], "source": source, **brief}), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
