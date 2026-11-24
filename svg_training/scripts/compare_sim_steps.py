#!/usr/bin/env python3
"""STE task L1.5: tier 2 (Isaac Lab drone) against the AirStack simulator's velocity steps, the simulator's own airframe.

INFO only, no gate. Spec and the reading words fixed before the run: ``ste_learning/drafts/L1_5_SPEC.md``. Tests:
``tests/test_compare_sim_steps.py``. SIM-ONLY values (owner's ruling R21, 24 Nov 2026): ``params/
airstack_sim_physics_v0.toml`` is read here and nowhere else; nothing here is a training set, a drone value or an
AirStack change (repository iron rule 9). Observed in the training simulator against the AirStack simulator; nothing
here is a flight result.

    # 1. CPU, no Isaac: the AirStack steps from the L1.4 session (bag + PX4 log), per step aligned to PX4's clock
    python scripts/compare_sim_steps.py extract --l14-run runs/2026-11-24_ste_l14_steps_r3 --run-dir runs/<name>
    # 2. tier 2 replays them, three arms (off, delay, error), batched over steps x replicas in one world
    #    (after nvidia-smi and scripts/isaac_preflight.sh --approved-headless; the lead launches GPU work)
    python scripts/compare_sim_steps.py replay --run-dir runs/<name> --world isaac --replicas 4 --headless
    #    the same on the CPU in the PyTorch reference world (a dry run, never of record)
    python scripts/compare_sim_steps.py replay --run-dir runs/<name> --world torch --device cpu --replicas 1
    # 3. re-score from the run's own files (CPU)
    python scripts/compare_sim_steps.py report --run-dir runs/<name>
    # tests: cut the small recorded fixture from the session
    python scripts/compare_sim_steps.py fixture --l14-run runs/2026-11-24_ste_l14_steps_r3 --steps 1,17,18 \\
        --out tests/data/l15_steps_fixture.npz

What is compared (the spec says why): the velocity setpoint PX4 itself received (``/<drone>/interface/mavros/
setpoint_raw/local``: velocity and yaw rate only, type mask 1479), on PX4's own clock, and PX4's estimate of the
velocity (ULog ``vehicle_local_position``). Replaying PX4's input on PX4's clock measures and aligns out two
confounds: the simulator's PX4 clock running faster than the commander's wall clock (measured per step here, about 2.5x
in this session; onset uncertainty up to 0.075 s, which enters AirStack's times one for one), and the commander's
reference-point sag that clock causes. The alignment matches setpoint to setpoint, so it cannot absorb a response lag;
it does remove any commander -> PX4 link delay. PX4's own log shows no position setpoint in any step window. The speed-only route is emulated in tier 2 by
zeroing its two position gains (``MPC_XY_P``, ``MPC_Z_P``): PX4 with a NaN position setpoint flies v_ff, while tier 2's
``PhysicsDrone`` holds a position setpoint over each tick (its docstring), which pulls back about K_p v dt / 2. The
PX4 1.16.1 cascade (simulator) against the 1.14 port (tier 2) cannot be removed; it is named.

Clock alignment (per step): the bag's 20 Hz setpoints are on the wall clock; PX4 logs the setpoint it holds
(``vehicle_local_position_setpoint``, 10 Hz) on its own clock. For each step an affine map t_px4 = a + s (t_wall - t_on)
is fitted by a grid search that matches the bag's held setpoint to PX4's logged one (coarse then fine); the residual
and the spread of near-optimal onsets are reported. The first guess comes from the flight span (takeoff -> touchdown
in the bag's odometry against the PX4 log; ``fit_response.ulog_time_scale``), which drifts by up to about 3 s.

Tier 2 input: the AirStack setpoint at each tick's midpoint (vehicle time), held over the 0.05 s tick (so a setpoint
change reaches tier 2 within +-0.025 s); the drone starts at the AirStack drone's estimated position, velocity and
heading 2 s before the onset, level and with fresh integrators. State after tick k is at t0 + (k + 1) * 0.05 s.
Arms: ``off`` (the SIM-ONLY file as flown), ``delay`` (L1.1's residual delay at its FIXED 0.05 s limit), ``error``
(L1.1b's estimate error at T63's nominal values, ``params/starling_physics_v1_nominal.toml``); each over the same
steps x replicas batch (game g = step g // R, replica g % R).

The trace scored for tier 2 is its ESTIMATE (``PhysicsDrone.est_vel_mps``, what its cascade saw), because the
AirStack trace is PX4's EKF2 estimate: with the delay or the error on, tier 2's truth and estimate differ (the true
velocity is kept beside it, INFO). With the route's position gains at 0, ``state_error_pos_*`` acts on nothing: the
error arm tests the velocity and attitude errors only.

Metrics (per step, the speed along the command, onset-aligned; levels shared by every trace of the step, taken from
the input): level0 = input mean over the last 1 s before the onset; level_peak = the input's extreme in the first
2.5 s (the delivered setpoint peaks then sags, so it is not a step). delay_s = the trace's 10 % crossing minus the
input's; rise_s = 10 % -> 90 % (NaN if 90 % is never reached before the hold ends); rise_own_s = 10 % -> 90 % of
the trace's own extreme in the hold (added after the CPU dry run: in x and y the response never reaches 90 % of
the input's peak, so rise_s is NaN there for every trace); t63_s; overshoot_pct = (the
trace's extreme in the hold - level_peak) / |level_peak - level0|; ss_error_mps = mean(trace - input) over the last
1 s of the hold (positive = faster than sent); lag_s = the shift in [-0.10, 0.60] s of the input that minimises the
RMS to the trace from 0.5 s before the onset to the hold's end.

Exit codes: 0 done; 1 unreadable input or a crash; 2 refused (bad arguments, an existing result, missing files).
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime
import glob
import hashlib
import json
import math
import os
import struct
import sys
import time
import tomllib
import traceback
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

from svg_training.models.physics_params import ERROR_KEYS, STATE_DELAY_MAX_S  # noqa: E402  (PyTorch-free)
from svg_training.models.px4_trajectory import time_to_63pct  # noqa: E402  (numpy only)

SIM_PARAMS = ROOT / "params" / "airstack_sim_physics_v0.toml"
NOMINAL_ERROR_PARAMS = ROOT / "params" / "starling_physics_v1_nominal.toml"
SIM_ONLY_HEADER = "# SIM-ONLY"
TICK_S = 0.05                       # one game tick (core.game_config.TICK_S)
PRE_S = 2.0                         # vehicle s flown before each onset (start state from the AirStack drone)
POST_S = 2.5                        # vehicle s kept after the hold ends (the release)
LEVEL0_S = 1.0                      # input mean over this long before the onset = level0
PEAK_WINDOW_S = 2.5                 # the input's extreme in this long after the onset = level_peak
SETTLE_S = 1.0                      # the last this-long of the hold = the steady-state window
LAG_SHIFTS_S = np.round(np.arange(-0.10, 0.6001, 0.01), 2)
VELOCITY_ONLY_MASK = 0x7 | 0x1C0 | 0x400     # IGNORE_PX|PY|PZ, IGNORE_AFX|AFY|AFZ, IGNORE_YAW (mavros PositionTarget)
DELAY_ARM_S = STATE_DELAY_MAX_S     # L1.1's residual delay at its FIXED limit, 0.05 s
ARMS = ("off", "delay", "error")
SLOTS = 2                           # drones per game: slot 0 flies the step, slot 1 holds still out of the way
FAR_SLOT_M = (-15.0, -15.0, 0.0)    # slot 1 from slot 0's start: > 15 m from any point a step reaches (<= 11.3 m on one
                                    # axis); with Isaac Lab's 40 m game spacing, > 8 m from the neighbouring games' drones
METRICS = ("delay_s", "rise_s", "rise_own_s", "t63_s", "overshoot_pct", "ss_error_mps", "lag_s")
# Floors (spec section 5, fixed before the Isaac run). Times: the honest time resolution of this comparison, about
# 0.1 s = the clock alignment's onset uncertainty (worst 0.075 s; it enters AirStack's delay_s one for one) plus tier 2's
# +-0.025 s input quantisation; it is above the 0.05 s delay arm, so the time metrics cannot see that arm by design.
# Overshoot and steady state: sized from the CPU dry run on the real AirStack data (set after seeing data).
FLOORS = {"delay_s": 0.1, "rise_s": 0.1, "rise_own_s": 0.1, "t63_s": 0.1, "lag_s": 0.1,
          "overshoot_pct": 5.0, "ss_error_mps": 0.02}
MOST_CELLS = 7                      # "most cells" = at least 7 of the 9 (spec section 5)
RMS_CHANGE_MPS = 0.005              # trace RMS: an arm differs from off only if the paired mean difference over steps
RMS_SIGN_STEPS = 24                 # is above this AND has the same sign in at least this many of the 35 steps
ALIGN_COARSE = (0.05, 0.02)         # (onset step s, scale step) of the coarse grid
ALIGN_FINE = (0.005, 0.002)
ALIGN_HALF_S = 4.0                  # coarse onset search: guess +- this
ALIGN_SCALES = (1.5, 3.5)           # coarse scale search range
OBSERVED = "observed in the training simulator (tier 2) against the AirStack simulator; not a flight result"
PX4_INFO_PARAMS = ("EKF2_GPS_CTRL", "EKF2_HGT_REF", "EKF2_EV_CTRL", "THR_MDL_FAC", "MPC_USE_HTE", "MPC_POS_MODE")


# =================================================================================================== bag decoding
def _header(data: bytes) -> tuple[float, int]:
    """std_msgs/Header at the start of a CDR message: (stamp s, offset after it, counted from the 4-byte encapsulation)."""
    if data[:2] != b"\x00\x01":
        raise NotImplementedError(f"only little-endian CDR (00 01) is supported, got {data[:2].hex()}")
    sec, nsec, n = struct.unpack_from("<iII", data, 4)
    return sec + nsec * 1e-9, 12 + n


def _align(off: int, width: int) -> int:
    return (off + width - 1) // width * width


def decode_twist_stamped(data: bytes) -> tuple[float, tuple, tuple]:
    """geometry_msgs/TwistStamped -> (stamp s, linear xyz, angular xyz)."""
    stamp, off = _header(data)
    v = struct.unpack_from("<6d", data, 4 + _align(off, 8))
    return stamp, v[:3], v[3:]


def decode_position_target(data: bytes) -> dict:
    """mavros_msgs/PositionTarget -> stamp, coordinate_frame, type_mask, position, velocity, acceleration, yaw, yaw_rate."""
    stamp, off = _header(data)
    frame = data[4 + off]
    off = _align(off + 1, 2)
    mask = struct.unpack_from("<H", data, 4 + off)[0]
    off = _align(off + 2, 8)
    v = struct.unpack_from("<9d", data, 4 + off)
    yaw, rate = struct.unpack_from("<2f", data, 4 + off + 72)
    return {"stamp": stamp, "coordinate_frame": frame, "type_mask": mask, "position": v[0:3], "velocity": v[3:6],
            "acceleration": v[6:9], "yaw": yaw, "yaw_rate": rate}


def decode_odometry_position(data: bytes) -> tuple[float, tuple]:
    """nav_msgs/Odometry -> (stamp s, position xyz)."""
    stamp, off = _header(data)
    off = _align(off, 4)
    n = struct.unpack_from("<I", data, 4 + off)[0]                       # child_frame_id
    off = _align(off + 4 + n, 8)
    return stamp, struct.unpack_from("<3d", data, 4 + off)


def is_velocity_only(type_mask: int) -> bool:
    """True when the setpoint carries velocity (and at most yaw rate) only: the speed-only MAVROS route."""
    return (int(type_mask) & VELOCITY_ONLY_MASK) == VELOCITY_ONLY_MASK and not (int(type_mask) & 0x38)


# =================================================================================================== frames
def ned_to_enu(v: np.ndarray) -> np.ndarray:
    """[..., 3] NED (north, east, down) -> ENU (east, north, up)."""
    v = np.asarray(v, dtype=float)
    return np.stack([v[..., 1], v[..., 0], -v[..., 2]], axis=-1)


def heading_ned_to_enu(h: np.ndarray) -> np.ndarray:
    """PX4 heading (rad from north, clockwise) -> ENU yaw (rad from east, anticlockwise), wrapped to (-pi, pi]."""
    a = math.pi / 2 - np.asarray(h, dtype=float)
    return np.arctan2(np.sin(a), np.cos(a))


# =================================================================================================== reading the session
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def load_streams(l14_run: Path) -> dict:
    """Everything extraction needs from an L1.4 run folder (read only): bag streams on the wall clock, PX4 log streams
    on PX4's clock, the plan and the flown steps, and the first-guess clock map."""
    from svg_training.logs.mcap_reader import iter_messages

    from fit_real_px4 import read_ulog_full
    import fit_response

    l14_run = Path(l14_run)
    plan = json.loads((l14_run / "steps.json").read_text())
    flown = json.loads((l14_run / "steps_flown.json").read_text())
    drone = flown["drone"]
    mcaps = sorted(glob.glob(str(l14_run / "svg_s1_*" / "*.mcap")))
    ulogs = sorted(glob.glob(str(l14_run / f"{drone}_*.ulg")))
    if len(mcaps) != 1 or len(ulogs) != 1:
        raise FileNotFoundError(f"{l14_run}: expected one bag (.mcap) and one {drone} PX4 log, found {mcaps} {ulogs}")
    topics = {f"/svg/{drone}/teleop_command": "teleop", f"/{drone}/interface/mavros/setpoint_raw/local": "sp",
              f"/{drone}/odometry_conversion/odometry": "odom"}
    rows: dict[str, list] = {k: [] for k in topics.values()}
    for msg in iter_messages(mcaps[0], set(topics)):
        kind, t = topics[msg.topic], msg.log_time_ns * 1e-9
        if kind == "teleop":
            rows[kind].append((t, *decode_twist_stamped(msg.data)[1]))
        elif kind == "sp":
            m = decode_position_target(msg.data)
            rows[kind].append((t, *m["velocity"], m["type_mask"]))
        else:
            rows[kind].append((t, *decode_odometry_position(msg.data)[1]))
    arr = {k: np.asarray(v, dtype=float) for k, v in rows.items()}
    data, params, changes = read_ulog_full(ulogs[0], ["vehicle_local_position", "vehicle_local_position_setpoint",
                                                      "trajectory_setpoint"])
    tsp = data["trajectory_setpoint"]
    lp, sp = data["vehicle_local_position"], data["vehicle_local_position_setpoint"]
    lpsp_v = ned_to_enu(np.stack([sp["vx"], sp["vy"], sp["vz"]], 1))
    ok = np.isfinite(lpsp_v).all(1)
    ts = fit_response.ulog_time_scale(ulogs[0], arr["odom"][:, 0], arr["odom"][:, 3])
    return {
        "teleop_t": arr["teleop"][:, 0], "teleop_v": arr["teleop"][:, 1:4],
        "sp_t": arr["sp"][:, 0], "sp_v": arr["sp"][:, 1:4], "sp_mask": arr["sp"][:, 4].astype(int),
        "lp_t": lp["timestamp"] * 1e-6, "lp_pos": ned_to_enu(np.stack([lp["x"], lp["y"], lp["z"]], 1)),
        "lp_vel": ned_to_enu(np.stack([lp["vx"], lp["vy"], lp["vz"]], 1)), "lp_heading": heading_ned_to_enu(lp["heading"]),
        "lpsp_t": sp["timestamp"][ok] * 1e-6, "lpsp_v": lpsp_v[ok],
        "tsp_t": tsp["timestamp"] * 1e-6,                       # what offboard handed PX4: NaN position = speed only
        "tsp_pos": np.stack([tsp["position[0]"], tsp["position[1]"], tsp["position[2]"]], 1),
        "plan": plan["steps"], "flown": flown["steps"],
        "guess": {"wall_ref": ts["takeoff_wall_s"], "px4_ref": ts["takeoff_vehicle_s"], "scale": ts["scale"],
                  "method": "fit_response.ulog_time_scale (takeoff -> touchdown)"},
        "px4_params": {k: params.get(k) for k in PX4_INFO_PARAMS}, "px4_param_changes": len(changes),
        "source": {"run": str(l14_run), "bag": mcaps[0], "ulog": ulogs[0], "drone": drone,
                   "steps_json_sha256": _sha256(l14_run / "steps.json"),
                   "steps_flown_sha256": _sha256(l14_run / "steps_flown.json")},
    }


ARRAY_KEYS = ("teleop_t", "teleop_v", "sp_t", "sp_v", "sp_mask", "lp_t", "lp_pos", "lp_vel", "lp_heading", "lpsp_t",
              "lpsp_v", "tsp_t", "tsp_pos")
META_KEYS = ("plan", "flown", "guess", "px4_params", "px4_param_changes", "source")


def guess_px4_time(streams: dict, t_wall: float) -> float:
    g = streams["guess"]
    return g["px4_ref"] + g["scale"] * (t_wall - g["wall_ref"])


def cut_fixture(streams: dict, indices: list[int], out: Path) -> int:
    """The streams around the listed steps only, values as float32 (times float64): a small recorded test fixture."""
    flown = {f["index"]: f for f in streams["flown"]}
    wall_keep = np.zeros(len(streams["sp_t"]), bool)
    tel_keep = np.zeros(len(streams["teleop_t"]), bool)
    lp_keep = np.zeros(len(streams["lp_t"]), bool)
    sp_keep = np.zeros(len(streams["lpsp_t"]), bool)
    tsp_keep = np.zeros(len(streams["tsp_t"]), bool)
    for i in indices:
        f = flown[i]
        lo, hi = f["onset_unix_s"] - 6.0, f["end_unix_s"] + 6.0      # the alignment reads up to ~5 s wall around
        wall_keep |= (streams["sp_t"] >= lo) & (streams["sp_t"] <= hi)
        tel_keep |= (streams["teleop_t"] >= lo) & (streams["teleop_t"] <= hi)
        plo = guess_px4_time(streams, f["onset_unix_s"]) - ALIGN_HALF_S - PRE_S - 3.0
        phi = guess_px4_time(streams, f["end_unix_s"]) + ALIGN_HALF_S + POST_S + 3.0
        lp_keep |= (streams["lp_t"] >= plo) & (streams["lp_t"] <= phi)
        sp_keep |= (streams["lpsp_t"] >= plo) & (streams["lpsp_t"] <= phi)
        tsp_keep |= (streams["tsp_t"] >= plo) & (streams["tsp_t"] <= phi)
    keep = {"teleop": tel_keep, "sp": wall_keep, "lp": lp_keep, "lpsp": sp_keep, "tsp": tsp_keep}
    arrays = {}
    for k in ARRAY_KEYS:
        mask = keep[k.split("_")[0]]
        a = np.asarray(streams[k])[mask]
        arrays[k] = a if (k.endswith("_t") or k == "sp_mask") else a.astype(np.float32)
    meta = {k: streams[k] for k in META_KEYS}
    meta["plan"] = [s for s in streams["plan"] if s["index"] in indices]
    meta["flown"] = [f for f in streams["flown"] if f["index"] in indices]
    meta["source"] = {**streams["source"], "fixture_steps": list(indices)}
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, meta=np.asarray(json.dumps(meta)), **arrays)
    return out.stat().st_size


def load_fixture(path: Path) -> dict:
    z = np.load(path, allow_pickle=False)
    s = {k: np.asarray(z[k], dtype=np.int64 if k == "sp_mask" else np.float64) for k in ARRAY_KEYS}
    s.update(json.loads(str(z["meta"])))
    return s


# =================================================================================================== clock alignment
def _held(t_src: np.ndarray, v_src: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Zero-order hold of v_src [N, 3] (times t_src, sorted) at times t (any shape): the last sample at or before t."""
    i = np.clip(np.searchsorted(t_src, t, side="right") - 1, 0, len(t_src) - 1)
    return v_src[i]


def _align_costs(t_w, v_w, t_p, v_p, t_on, offsets, scales):
    """Mean squared setpoint mismatch [len(offsets), len(scales)] of the map t_px4 = a + s (t_wall - t_on)."""
    a = np.asarray(offsets)[:, None, None]
    s = np.asarray(scales)[None, :, None]
    t_wall = t_on + (t_p[None, None, :] - a) / s                                  # [A, S, P]
    d = _held(t_w, v_w, t_wall) - v_p[None, None, :, :]
    return np.mean(np.sum(d * d, axis=-1), axis=-1)


def align_step(t_wall: np.ndarray, v_bag: np.ndarray, t_px4: np.ndarray, v_px4: np.ndarray, t_on_wall: float,
               hold_wall_s: float, guess_offset_s: float, guess_scale: float) -> dict:
    """Fit t_px4 = offset + scale (t_wall - t_on_wall) for one step: the bag's held setpoint (wall clock) against the
    setpoint PX4 logged (its clock). Coarse grid (onset guess +- ALIGN_HALF_S, scale in ALIGN_SCALES), then fine.
    Returns offset_s (PX4 time of the onset), scale, residual_rms_mps, onset_spread_s (range of onsets whose cost is
    within 10 % of the best, plus 1e-6 m^2/s^2: how sharply the data pin the onset), samples."""
    lo = guess_offset_s - ALIGN_HALF_S - 1.0
    hi = guess_offset_s + ALIGN_HALF_S + guess_scale * hold_wall_s + 3.0
    keep = (t_px4 >= lo) & (t_px4 <= hi)
    t_p, v_p = t_px4[keep], v_px4[keep]
    if t_p.size < 20:
        raise ValueError(f"only {t_p.size} PX4 setpoint samples around the onset guess {guess_offset_s:.2f} s")
    offs = np.arange(guess_offset_s - ALIGN_HALF_S, guess_offset_s + ALIGN_HALF_S + 1e-9, ALIGN_COARSE[0])
    scales = np.arange(ALIGN_SCALES[0], ALIGN_SCALES[1] + 1e-9, ALIGN_COARSE[1])
    cost = np.concatenate([_align_costs(t_wall, v_bag, t_p, v_p, t_on_wall, offs[i:i + 20], scales)
                           for i in range(0, len(offs), 20)])
    i, j = np.unravel_index(np.argmin(cost), cost.shape)
    offs_f = offs[i] + np.arange(-2 * ALIGN_COARSE[0], 2 * ALIGN_COARSE[0] + 1e-9, ALIGN_FINE[0])
    scales_f = scales[j] + np.arange(-2 * ALIGN_COARSE[1], 2 * ALIGN_COARSE[1] + 1e-9, ALIGN_FINE[1])
    fine = _align_costs(t_wall, v_bag, t_p, v_p, t_on_wall, offs_f, scales_f)
    best = float(fine.min())
    # a held setpoint sampled at 10 Hz leaves a flat minimum: take its centre (the grid points tied at the minimum)
    ti, tj = np.nonzero(fine <= best + 1e-9)
    near = np.flatnonzero((fine <= best * 1.1 + 1e-6).any(axis=1))
    return {"offset_s": float(offs_f[ti].mean()), "scale": float(scales_f[tj].mean()), "residual_rms_mps": math.sqrt(best),
            "onset_spread_s": float(offs_f[near].max() - offs_f[near].min()),
            "scale_spread": float(scales_f[tj].max() - scales_f[tj].min()), "samples": int(t_p.size)}


# =================================================================================================== metrics
def _first_cross(t, x, level, sgn, interp: bool) -> float:
    y = sgn * (x - level)
    hit = np.flatnonzero(y >= 0.0)
    if hit.size == 0:
        return math.nan
    j = int(hit[0])
    if not interp or j == 0:
        return float(t[j])
    return float(t[j - 1] + (-y[j - 1]) / (y[j] - y[j - 1]) * (t[j] - t[j - 1]))


def response_metrics(t: np.ndarray, v: np.ndarray, sp: np.ndarray, hold_end_s: float, onset_s: float = 0.0) -> dict:
    """The module docstring's metrics of trace v against the input sp (both (T,) on grid t, m/s along the command).

    The input is a held (staircase) signal: its crossings are the first sample that reaches the level; the trace's
    are linearly interpolated. NaN where a level is never reached before hold_end_s."""
    t, v, sp = (np.asarray(x, dtype=float) for x in (t, v, sp))
    pre = (t >= onset_s - LEVEL0_S) & (t < onset_s)
    l0 = float(sp[pre].mean()) if pre.any() else float(sp[0])
    win = (t >= onset_s) & (t <= min(onset_s + PEAK_WINDOW_S, hold_end_s))
    k = int(np.argmax(np.abs(sp[win] - l0)))
    lpk = float(sp[win][k])
    change = lpk - l0
    sgn = math.copysign(1.0, change) if change != 0 else 1.0
    seg = (t >= onset_s) & (t <= hold_end_s)
    ts, vs, sps = t[seg], v[seg], sp[seg]
    t10_in = _first_cross(ts, sps, l0 + 0.1 * change, sgn, interp=False)
    t10 = _first_cross(ts, vs, l0 + 0.1 * change, sgn, interp=True)
    t90 = _first_cross(ts, vs, l0 + 0.9 * change, sgn, interp=True)
    own = float(np.max(sgn * (vs - l0)))                     # the trace's own extreme in the hold (along sgn)
    own10 = _first_cross(ts, vs, l0 + 0.1 * sgn * own, sgn, interp=True) if own > 0 else math.nan
    own90 = _first_cross(ts, vs, l0 + 0.9 * sgn * own, sgn, interp=True) if own > 0 else math.nan
    settle = (t >= hold_end_s - SETTLE_S) & (t < hold_end_s)
    lag_win = (t >= onset_s - 0.5) & (t <= hold_end_s)
    rms = [float(np.sqrt(np.mean((v[lag_win] - np.interp(t[lag_win] - s, t, sp)) ** 2))) for s in LAG_SHIFTS_S]
    return {"level0_mps": l0, "level_peak_mps": lpk,
            "delay_s": t10 - t10_in,
            "rise_s": t90 - t10,
            "rise_own_s": own90 - own10,
            "t63_s": time_to_63pct(ts, vs, l0, lpk, onset_s) if abs(change) > 0 else math.nan,
            "overshoot_pct": 100.0 * (float(np.max(sgn * (vs - l0))) - abs(change)) / abs(change) if change else math.nan,
            "ss_error_mps": sgn * float(np.mean(v[settle] - sp[settle])) if settle.any() else math.nan,
            "lag_s": float(LAG_SHIFTS_S[int(np.argmin(rms))])}


# =================================================================================================== extraction
def _interp3(t_src, x_src, t):
    return np.stack([np.interp(t, t_src, x_src[:, i]) for i in range(3)], axis=-1)


def _position_setpoint_check(streams: dict, t0: float, t1: float) -> dict:
    """The speed-only route, checked on PX4's side: the trajectory setpoints PX4 logged in [t0, t1] (its clock) and how
    many carried a finite position (0 = PX4 flew velocity only, as tier 2's zero position gains emulate)."""
    m = (streams["tsp_t"] >= t0) & (streams["tsp_t"] <= t1)
    return {"samples": int(m.sum()), "finite_position": int(np.isfinite(streams["tsp_pos"][m]).any(axis=1).sum())}


def extract_from_streams(streams: dict) -> dict:
    """Per flown step: the clock map, the input and response on the vehicle-time grid, the start state, the AirStack
    metrics. Steps the session skipped are listed in ``skipped``."""
    plan = {s["index"]: s for s in streams["plan"]}
    steps, skipped = [], []
    for f in streams["flown"]:
        if f.get("skipped") or f.get("onset_unix_s") is None:
            skipped.append(int(f["index"]))
            continue
        s = plan[f["index"]]
        t_on, hold_w = float(f["onset_unix_s"]), float(f["end_unix_s"]) - float(f["onset_unix_s"])
        guess = guess_px4_time(streams, t_on)
        al = align_step(streams["sp_t"], streams["sp_v"], streams["lpsp_t"], streams["lpsp_v"], t_on, hold_w, guess,
                        streams["guess"]["scale"])
        a, sc = al["offset_s"], al["scale"]
        hold_v = sc * hold_w
        n_ticks = int(math.ceil((PRE_S + hold_v + POST_S) / TICK_S - 1e-9))
        t = -PRE_S + TICK_S * np.arange(n_ticks + 1)                         # vehicle s from the onset
        wall = lambda tv: t_on + np.asarray(tv) / sc                          # noqa: E731
        u = np.asarray(s["velocity_enu_mps"], float)
        u = u / np.linalg.norm(u)
        sp_grid = _held(streams["sp_t"], streams["sp_v"], wall(t))
        sp_tick = _held(streams["sp_t"], streams["sp_v"], wall(t[:-1] + TICK_S / 2))
        resp = _interp3(streams["lp_t"], streams["lp_vel"], a + t)
        in_win = (streams["sp_t"] >= t_on - 1.0) & (streams["sp_t"] <= t_on + hold_w + 1.0)
        tel = (streams["teleop_t"] >= t_on + 0.2) & (streams["teleop_t"] < t_on + hold_w - 0.1)
        settle = (t >= hold_v - SETTLE_S) & (t < hold_v)
        k0 = int(np.argmin(np.abs(streams["lp_t"] - (a - PRE_S))))
        row = {"index": int(s["index"]), "axis": s["axis"], "sign": int(s["sign"]), "speed_mps": float(s["speed_mps"]),
               "cmd_unit": u.tolist(), "hold_wall_s": hold_w, "hold_end_s": hold_v,
               "clock_scale": sc, "onset_px4_s": a, "guess_error_s": a - guess,
               "align_residual_rms_mps": al["residual_rms_mps"], "align_onset_spread_s": al["onset_spread_s"],
               "align_samples": al["samples"],
               "px4_position_setpoint": _position_setpoint_check(streams, a - PRE_S, a + hold_v + POST_S),
               "setpoint_velocity_only": bool(np.all([is_velocity_only(m) for m in streams["sp_mask"][in_win]])),
               "teleop_level_mps": float(np.mean(streams["teleop_v"][tel] @ u)) if tel.any() else math.nan,
               "setpoint_settled_mps": float(np.mean(sp_grid[settle] @ u)),
               "t_s": t, "setpoint_mps": sp_grid, "setpoint_tick_mps": sp_tick, "response_mps": resp,
               "pos0_m": _interp3(streams["lp_t"], streams["lp_pos"], np.array([a - PRE_S]))[0],
               "vel0_mps": _interp3(streams["lp_t"], streams["lp_vel"], np.array([a - PRE_S]))[0],
               "yaw0_rad": float(streams["lp_heading"][k0]),
               "pos_end_m": _interp3(streams["lp_t"], streams["lp_pos"], np.array([a + hold_v]))[0]}
        row["metrics"] = {"airstack": response_metrics(t, resp @ u, sp_grid @ u, hold_v),
                          "setpoint": response_metrics(t, sp_grid @ u, sp_grid @ u, hold_v)}
        steps.append(row)
    return {"steps": steps, "skipped": skipped, "guess": streams["guess"], "source": streams["source"],
            "px4_params": streams["px4_params"], "px4_param_changes": streams["px4_param_changes"]}


# =================================================================================================== parameters and arms
def load_sim_only_params(path: Path):
    """The SIM-ONLY comparison file: header and label checked, its [sim_only] table dropped (the table is what makes
    the trainer's loader refuse the file), the rest loaded with ``load_physics_params`` from a copy in a temporary
    folder that is deleted at once (no loadable copy without the guard is left anywhere). Returns (PhysicsParams,
    provenance)."""
    import tempfile

    from svg_training.models.physics_params import load_physics_params

    raw = Path(path).read_bytes()
    text = raw.decode()
    if not text.startswith(SIM_ONLY_HEADER):
        raise ValueError(f"{path}: must start with {SIM_ONLY_HEADER!r}")
    data = tomllib.loads(text)
    label = str(data.get("sim_only", {}).get("label", ""))
    if "SIM-ONLY" not in label:
        raise ValueError(f"{path}: its [sim_only] label must say SIM-ONLY")
    keep, skipping = [], False
    for line in text.splitlines(keepends=True):
        if line.strip().startswith("["):
            skipping = line.strip() == "[sim_only]"
        if not skipping:
            keep.append(line)
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "airstack_sim_physics_loaded.toml"
        copy.write_text("".join(keep))
        p = load_physics_params(copy)
    try:
        rel = str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        rel = str(path)
    p = dataclasses.replace(p, source={**p.source, "sim_only": label})       # every reader of p can see it
    return p, {"file": rel, "sha256": hashlib.sha256(raw).hexdigest(), "label": label}


def arm_params(base) -> dict:
    """{arm: PhysicsParams}. Every arm flies the speed-only route (position gains 0, module docstring); ``delay`` adds
    the residual state delay at its FIXED limit; ``error`` the six state_error_* of T63's nominal proposal."""
    from svg_training.models.physics_params import load_physics_params

    off = dataclasses.replace(base, gains=dataclasses.replace(base.gains, mpc_xy_p=0.0, mpc_z_p=0.0))
    nominal = load_physics_params(NOMINAL_ERROR_PARAMS)
    return {"off": off,
            "delay": dataclasses.replace(off, state_delay_s=DELAY_ARM_S),
            "error": dataclasses.replace(off, **{k: getattr(nominal, k) for k in ERROR_KEYS})}


# =================================================================================================== tier 2
def batch_inputs(steps: list[dict], replicas: int) -> tuple[dict, dict]:
    """One batch for every arm: game g flies step g // replicas. sp_mps [K, N, 3] (zero after a step's own end),
    pos0_m / vel0_mps [N, 3], yaw0_rad [N]."""
    n = len(steps) * replicas
    k_max = max(len(s["setpoint_tick_mps"]) for s in steps)
    sp = np.zeros((k_max, n, 3))
    pos0, vel0, yaw0 = np.zeros((n, 3)), np.zeros((n, 3)), np.zeros(n)
    for i, s in enumerate(steps):
        g = slice(i * replicas, (i + 1) * replicas)
        k = len(s["setpoint_tick_mps"])
        sp[:k, g] = np.asarray(s["setpoint_tick_mps"])[:, None, :]
        pos0[g], vel0[g], yaw0[g] = s["pos0_m"], s["vel0_mps"], s["yaw0_rad"]
    layout = {"games": n, "steps": len(steps), "replicas": replicas, "ticks": k_max,
              "step_index": [int(s["index"]) for s in steps]}
    return {"sp_mps": sp, "pos0_m": pos0, "vel0_mps": vel0, "yaw0_rad": yaw0}, layout


def fly(world, params, inputs: dict, device, seed: int) -> dict:
    """Fly the batch through one PhysicsDrone on ``world`` (N games x 2 slots, the layout of every other tier-2 script:
    slot 0 flies the step, slot 1 holds still at ``FAR_SLOT_M`` from slot 0's start). Per tick: a velocity setpoint,
    position setpoint = the drone's own position (inert with the route's zero position gains), heading held, no
    feed-forward acceleration. Returns numpy, slot 0 only: est_vel_mps (what the cascade saw: tier 2's counterpart of
    PX4's EKF2 estimate, the primary trace), true_vel_mps and pos_m [K+1, N, 3] (sample 0 = the start),
    max_tilt_deg [N], upsets and nonfinite (both slots)."""
    import torch

    from svg_training.models.physics_drone import PhysicsDrone

    dev = torch.device(device)
    tt = lambda x: torch.as_tensor(np.asarray(x), dtype=torch.float32, device=dev)       # noqa: E731
    if world.drones != SLOTS:
        raise ValueError(f"the world holds {world.drones} drones per game; this script flies {SLOTS}")
    drone = PhysicsDrone(world, params, dev, noise_seed=seed)
    n = world.num_games
    mask = torch.ones(n, SLOTS, dtype=torch.bool, device=dev)
    p0 = tt(inputs["pos0_m"])
    pos0 = torch.stack([p0, p0 + tt(FAR_SLOT_M)], dim=1)                                 # [N, 2, 3]
    yaw0 = tt(inputs["yaw0_rad"])[:, None].expand(n, SLOTS).contiguous()
    vel0 = torch.stack([tt(inputs["vel0_mps"]), torch.zeros(n, 3, device=dev)], dim=1)
    drone.reset(mask, pos0, yaw0)
    drone.write_clamped(mask, pos0, vel0)
    sp_all = torch.zeros(tt(inputs["sp_mps"]).shape[0], n, SLOTS, 3, device=dev)
    sp_all[:, :, 0] = tt(inputs["sp_mps"])                                              # [K, N, 2, 3]; slot 1: zero
    zero3 = torch.zeros(n, SLOTS, 3, device=dev)
    zero1 = torch.zeros(n, SLOTS, device=dev)
    est, true, pos = [drone.est_vel_mps.clone()], [drone.vel_mps.clone()], [drone.pos_m.clone()]
    for k in range(sp_all.shape[0]):                 # ticks; every game of the batch at once
        drone.step_setpoint(drone.pos_m.clone(), sp_all[k], zero3, yaw0, zero1)
        est.append(drone.est_vel_mps.clone())
        true.append(drone.vel_mps.clone())
        pos.append(drone.pos_m.clone())
    s0 = lambda xs: torch.stack(xs)[:, :, 0].cpu().numpy()                              # noqa: E731
    return {"est_vel_mps": s0(est), "true_vel_mps": s0(true), "pos_m": s0(pos),
            "max_tilt_deg": torch.rad2deg(drone.max_tilt_rad)[:, 0].cpu().numpy(),
            "upsets": int(drone.upset.sum()), "nonfinite": int(drone.nonfinite_count)}


def fly_arms(world_factory, arms: dict, inputs: dict, device, seed: int) -> dict:
    """Every arm in turn on ``world_factory(params)`` (the Isaac factory hands back one world for all arms)."""
    out = {}
    for name, p in arms.items():
        t0 = time.time()
        out[name] = fly(world_factory(p), p, inputs, device, seed)
        print(f"arm {name}: {time.time() - t0:.1f} s", flush=True)
    return out


# =================================================================================================== analysis
def reading(value: float, airstack: list[float], floor: float) -> str:
    """The spec's words: tier 2's value against the AirStack range widened by the metric's resolution floor."""
    a = np.asarray(airstack, dtype=float)
    a_ok = a[np.isfinite(a)]
    if not math.isfinite(value):
        return "within" if a_ok.size == 0 else "not reached"
    if a_ok.size == 0:
        return "outside (AirStack not reached)"
    if value > a_ok.max() + floor:
        return "outside (above)"
    if value < a_ok.min() - floor:
        return "outside (below)"
    return "within"


def rms_change(rms_arm: list[float], rms_off: list[float]) -> dict:
    """The trace RMS reading (spec section 5): per step, RMS(arm) - RMS(off), paired. "closer" / "further" only if the
    mean difference is beyond RMS_CHANGE_MPS AND at least RMS_SIGN_STEPS steps share its sign; else "no change"."""
    d = np.asarray(rms_arm, float) - np.asarray(rms_off, float)
    mean = float(d.mean())
    same = int((np.sign(d) == np.sign(mean)).sum()) if mean else 0
    need = math.ceil(RMS_SIGN_STEPS / 35 * len(d))          # 24 of the session's 35 steps (scaled for a subset)
    word = ("further" if mean > 0 else "closer") if abs(mean) > RMS_CHANGE_MPS and same >= need else "no change"
    return {"mean_diff_mps": mean, "steps_same_sign": same, "steps": int(len(d)), "word": word}


def arm_change(dist_arm: float, dist_off: float, floor: float) -> str:
    """An arm against ``off``: the distance of its cell value to the AirStack cell median, against off's."""
    if not (math.isfinite(dist_arm) and math.isfinite(dist_off)):
        return "not comparable"
    if dist_arm < dist_off - floor:
        return "closer"
    if dist_arm > dist_off + floor:
        return "further"
    return "no change (within the floor)"


def cell_table(steps: list[dict], metrics_by_source: dict) -> dict:
    """{(axis, speed): {"steps": [index...], "values": {source: {metric: [value per step]}}}}; both signs pooled (the
    metrics are along the command)."""
    cells: dict = {}
    for i, s in enumerate(steps):
        c = cells.setdefault((s["axis"], s["speed_mps"]), {"steps": [], "values": {}})
        c["steps"].append(s["index"])
        for src, rows in metrics_by_source.items():
            for m in METRICS:
                c["values"].setdefault(src, {}).setdefault(m, []).append(rows[i][m])
    return cells


def _nanmean(x) -> float:
    a = np.asarray(x, dtype=float)
    return float(np.nanmean(a)) if np.isfinite(a).any() else math.nan


def analyse(ext: dict, out: dict, layout: dict) -> dict:
    """Per-step metrics of every arm (replica mean and range) beside AirStack's, the cells with their reading words,
    each arm against off, and the confounds with their measured sizes."""
    steps, reps = ext["steps"], layout["replicas"]
    rows, tier2_rows = [], {arm: [] for arm in out}
    for i, s in enumerate(steps):
        t, u, hold = np.asarray(s["t_s"]), np.asarray(s["cmd_unit"]), float(s["hold_end_s"])
        sp_u, as_u = np.asarray(s["setpoint_mps"]) @ u, np.asarray(s["response_mps"]) @ u
        row = {k: s[k] for k in ("index", "axis", "sign", "speed_mps", "clock_scale", "teleop_level_mps",
                                 "setpoint_settled_mps", "align_residual_rms_mps", "align_onset_spread_s")}
        # re-scored from the stored traces, so a report always uses this file's metric definitions
        row["airstack"], row["setpoint"] = response_metrics(t, as_u, sp_u, hold), response_metrics(t, sp_u, sp_u, hold)
        row["tier2"] = {}
        for arm, res in out.items():
            vel = res["est_vel_mps"][: len(t), i * reps:(i + 1) * reps]                 # [T, R, 3] the estimate
            true = res["true_vel_mps"][: len(t), i * reps:(i + 1) * reps]               # INFO: the true state
            per = [response_metrics(t, vel[:, r] @ u, sp_u, hold) for r in range(reps)]
            mean = {m: _nanmean([p[m] for p in per]) for m in METRICS}
            mean.update({f"{m}_range": [float(np.nanmin([p[m] for p in per])) if np.isfinite([p[m] for p in per]).any()
                                        else math.nan,
                                        float(np.nanmax([p[m] for p in per])) if np.isfinite([p[m] for p in per]).any()
                                        else math.nan] for m in METRICS})
            mean["reached_90pct"] = sum(math.isfinite(p["rise_s"]) for p in per)
            mean["rms_vs_airstack_mps"] = float(np.sqrt(np.mean((vel @ u - as_u[:, None]) ** 2)))
            mean["rms_true_vs_airstack_mps"] = float(np.sqrt(np.mean((true @ u - as_u[:, None]) ** 2)))
            mean["replica_spread_max_mps"] = float(np.max(np.ptp(vel, axis=1))) if reps > 1 else 0.0
            row["tier2"][arm] = mean
            tier2_rows[arm].append(mean)
        rows.append(row)
    cells = cell_table(steps, {"airstack": [r["airstack"] for r in rows], **tier2_rows})
    cell_rows, dist = [], {arm: {m: [] for m in METRICS} for arm in out}
    for (axis, speed), c in sorted(cells.items(), key=lambda kv: ("xyz".index(kv[0][0]), kv[0][1])):
        a = c["values"]["airstack"]
        cr = {"axis": axis, "speed_mps": speed, "steps": c["steps"],
              "airstack_range": {m: [_nanmin(a[m]), _nanmax(a[m])] for m in METRICS},
              "tier2": {}, "reading": {}}
        for arm in out:
            vals = {m: _nanmean(c["values"][arm][m]) for m in METRICS}
            cr["tier2"][arm] = vals
            cr["reading"][arm] = {m: reading(vals[m], a[m], FLOORS[m]) for m in METRICS}
            for m in METRICS:
                med = float(np.nanmedian(a[m])) if np.isfinite(a[m]).any() else math.nan
                dist[arm][m].append(abs(vals[m] - med) if math.isfinite(vals[m]) and math.isfinite(med) else math.nan)
        cell_rows.append(cr)
    summary = {}
    for arm in out:
        summary[arm] = {m: {"within": sum(c["reading"][arm][m] == "within" for c in cell_rows), "cells": len(cell_rows),
                            "mean_abs_diff_to_airstack_median": _nanmean(dist[arm][m])} for m in METRICS}
        for key in ("rms_vs_airstack_mps", "rms_true_vs_airstack_mps"):              # trace against trace
            vals = [r["tier2"][arm][key] for r in rows]
            summary[arm][key] = {"mean": _nanmean(vals), "max": _nanmax(vals)}
    change = {arm: {m: arm_change(summary[arm][m]["mean_abs_diff_to_airstack_median"],
                                  summary["off"][m]["mean_abs_diff_to_airstack_median"], FLOORS[m]) for m in METRICS}
              for arm in out if arm != "off"} if "off" in out else {}
    for arm in change:
        change[arm]["trace_rms"] = rms_change([r["tier2"][arm]["rms_vs_airstack_mps"] for r in rows],
                                              [r["tier2"]["off"]["rms_vs_airstack_mps"] for r in rows])
    most = {arm: {m: summary[arm][m]["within"] >= MOST_CELLS for m in METRICS} for arm in out}
    return {"steps": rows, "cells": cell_rows, "summary": summary, "arm_change": change, "within_most_cells": most,
            "confounds": confounds(ext), "health": health(rows, out)}


def health(rows: list[dict], out: dict) -> dict:
    """Reported, not gated (spec section 5): upsets, non-finite counts and the largest tilt per arm; the replicas'
    largest spread per arm (in ``off`` and ``delay``: a determinism check); the clock alignment per step."""
    h = {arm: {"upsets": r["upsets"], "nonfinite": r["nonfinite"], "max_tilt_deg": float(np.max(r["max_tilt_deg"])),
               "replica_spread_max_mps": max(row["tier2"][arm]["replica_spread_max_mps"] for row in rows)}
         for arm, r in out.items()}
    h["alignment"] = {"residual_rms_max_mps": max(r["align_residual_rms_mps"] for r in rows),
                      "onset_spread_max_s": max(r["align_onset_spread_s"] for r in rows),
                      "per_step": {r["index"]: [r["align_residual_rms_mps"], r["align_onset_spread_s"]] for r in rows}}
    return h


def _nanmin(x) -> float:
    a = np.asarray(x, dtype=float)
    return float(np.nanmin(a)) if np.isfinite(a).any() else math.nan


def _nanmax(x) -> float:
    a = np.asarray(x, dtype=float)
    return float(np.nanmax(a)) if np.isfinite(a).any() else math.nan


def confounds(ext: dict) -> dict:
    """The named confounds with what this session measured of each."""
    steps = ext["steps"]
    sc = np.array([s["clock_scale"] for s in steps])
    by_speed = {}
    for s in steps:
        by_speed.setdefault(s["speed_mps"], []).append(s["setpoint_settled_mps"] / s["teleop_level_mps"])
    px = ext.get("px4_params", {})
    vo = sum(bool(s["setpoint_velocity_only"]) for s in steps)
    return {
        "px4_version": "PX4 v1.16.1 SITL in the AirStack simulator; tier 2 flies a port of PX4 v1.14.0's cascade "
                       "(models/px4_cascade.py). Not removable here: named.",
        "route": f"the speed-only MAVROS route: {vo} of {len(steps)} steps sent velocity (and yaw rate) only (type mask "
                 "1479). Tier 2 emulates it with its two position gains at 0; the real drone's trajectory-setpoint route "
                 "(position + velocity + acceleration) is not part of this comparison.",
        "clock": {"text": "the simulator's PX4 clock against the commander's wall clock, per step (fitted); removed by "
                          "replaying the setpoint PX4 received on PX4's clock. Its size at the policy's level: the "
                          "settled setpoint PX4 got over the teleop command, per speed.",
                  "scale_min": float(sc.min()), "scale_median": float(np.median(sc)), "scale_max": float(sc.max()),
                  "settled_over_teleop": {str(k): [float(min(v)), float(max(v))] for k, v in sorted(by_speed.items())}},
        "estimator_source": f"the simulator's EKF2 fuses simulated GPS (EKF2_GPS_CTRL {px.get('EKF2_GPS_CTRL')}, "
                            f"EKF2_HGT_REF {px.get('EKF2_HGT_REF')}, EKF2_EV_CTRL {px.get('EKF2_EV_CTRL')}); the drone "
                            "fuses mocap. The error arm's values (T63) are the real drone_2's EKF2 against mocap, not "
                            "this EKF2's error.",
        "plant": f"not matched by tier 2: THR_MDL_FAC {px.get('THR_MDL_FAC')} (tier 2 linear), the hover-thrust "
                 f"estimator (MPC_USE_HTE {px.get('MPC_USE_HTE')}), Pegasus's input scaling 1350 against omega_max 1450, "
                 "the USD's inertia (not read; v1's values used), PhysX scene and solver settings of each simulator.",
    }


# =================================================================================================== files
def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, np.ndarray):
        return _jsonable(x.tolist())
    if isinstance(x, (np.floating, float)):
        return None if not math.isfinite(float(x)) else float(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


def _unjson_steps(steps: list[dict]) -> list[dict]:
    for s in steps:
        for k in ("t_s", "setpoint_mps", "setpoint_tick_mps", "response_mps", "pos0_m", "vel0_mps", "pos_end_m",
                  "cmd_unit"):
            s[k] = np.asarray(s[k], dtype=float)
        for src in s["metrics"].values():
            for m, v in src.items():
                src[m] = math.nan if v is None else v
    return steps


def save_extract(ext: dict, run_dir: Path) -> Path:
    path = run_dir / "extract.json"
    path.write_text(json.dumps(_jsonable(ext)))
    return path


def load_extract(run_dir: Path) -> dict:
    ext = json.loads((run_dir / "extract.json").read_text())
    ext["steps"] = _unjson_steps(ext["steps"])
    return ext


def _f(x, nd=3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def results_md(res: dict, meta: dict) -> str:
    """The run's own summary page (runs/, not a record): the cells side by side with their words."""
    lines = [f"# L1.5 tier 2 against the AirStack simulator ({meta['world']}, {meta['replicas']} replicas)", "",
             OBSERVED + ".", "", "## Cells (both signs pooled; AirStack range widened by the floor)", ""]
    for c in res["cells"]:
        lines.append(f"### {c['axis']} {c['speed_mps']:g} m/s (steps {c['steps']})")
        lines.append("| metric | AirStack range | " + " | ".join(f"tier 2 {a}" for a in c["tier2"]) + " |")
        lines.append("|---|---|" + "---|" * len(c["tier2"]))
        for m in METRICS:
            lo, hi = c["airstack_range"][m]
            cells = [f"{_f(c['tier2'][a][m])} ({c['reading'][a][m]})" for a in c["tier2"]]
            lines.append(f"| {m} | {_f(lo)} to {_f(hi)} | " + " | ".join(cells) + " |")
        lines.append("")
    lines += ["## Each arm against off", "", "| arm | " + " | ".join(METRICS) + " |", "|---|" + "---|" * len(METRICS)]
    for arm, d in res["arm_change"].items():
        lines.append(f"| {arm} | " + " | ".join(d[m] for m in METRICS) + " |")
    lines += ["", "Trace RMS against off (paired over steps; the only read that can see the delay arm):", ""]
    for arm, d in res["arm_change"].items():
        r = d["trace_rms"]
        lines.append(f"- {arm}: {r['word']} (mean difference {_f(r['mean_diff_mps'], 4)} m/s, same sign in "
                     f"{r['steps_same_sign']} of {r['steps']} steps; counts beyond {RMS_CHANGE_MPS} m/s with the sign "
                     f"in {RMS_SIGN_STEPS} of 35)")
    lines += ["", f"Within in most cells (at least {MOST_CELLS} of 9): " + "; ".join(
        f"{arm}: " + ", ".join(m for m, ok in d.items() if ok) for arm, d in res["within_most_cells"].items())]
    lines += ["", "## Trace against trace (INFO): RMS of tier 2 - AirStack along the command, over each step's window",
              "(tier 2's estimate, the primary trace; its true state beside it, INFO)", "",
              "| arm | mean over steps (m/s) | worst step (m/s) | true state: mean | true state: worst |",
              "|---|---|---|---|---|"]
    for arm, d in res["summary"].items():
        e, tr = d["rms_vs_airstack_mps"], d["rms_true_vs_airstack_mps"]
        lines.append(f"| {arm} | {_f(e['mean'])} | {_f(e['max'])} | {_f(tr['mean'])} | {_f(tr['max'])} |")
    lines += ["", "## Health (reported, not gated)", "", "```", json.dumps(_jsonable(
        {k: v for k, v in res["health"].items() if k != "alignment"}), indent=1),
        json.dumps(_jsonable({k: v for k, v in res["health"]["alignment"].items() if k != "per_step"})), "```"]
    lines += ["", "## Confounds", ""]
    for k, v in res["confounds"].items():
        lines.append(f"- **{k}**: {v['text'] if isinstance(v, dict) else v}")
        if isinstance(v, dict):
            lines.append(f"  - {json.dumps({kk: vv for kk, vv in v.items() if kk != 'text'})}")
    return "\n".join(lines) + "\n"


def figure(ext: dict, res: dict, out: dict, layout: dict, path: Path) -> None:
    """One panel per cell (first step of the cell): input, AirStack, tier 2 per arm (replica mean), along the command."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    first = {}
    for i, s in enumerate(ext["steps"]):
        first.setdefault((s["axis"], s["speed_mps"]), i)
    keys = sorted(first, key=lambda k: ("xyz".index(k[0]), k[1]))
    fig, axes = plt.subplots(3, 3, figsize=(15, 10), squeeze=False)
    colors = {"off": "#eb6834", "delay": "#1baf7a", "error": "#e87ba4"}
    for ax in axes.flat:
        ax.set_visible(False)
    for (axis, speed) in keys:
        i = first[(axis, speed)]
        s = ext["steps"][i]
        ax = axes["xyz".index(axis)][[0.5, 1.0, 2.0].index(speed) if speed in (0.5, 1.0, 2.0) else 0]
        ax.set_visible(True)
        t, u = s["t_s"], s["cmd_unit"]
        ax.step(t, s["setpoint_mps"] @ u, where="post", color="#52514e", lw=1, label="setpoint PX4 got")
        ax.plot(t, s["response_mps"] @ u, color="#2a78d6", lw=2, label="AirStack (EKF2 estimate)")
        for arm, r in out.items():
            v = r["est_vel_mps"][: len(t), i * layout["replicas"]:(i + 1) * layout["replicas"]] @ u
            ax.plot(t, v.mean(axis=1), color=colors.get(arm, "k"), lw=1.2, label=f"tier 2 {arm} (estimate)")
        ax.axvline(0, color="#e4e3df")
        ax.axvline(s["hold_end_s"], color="#e4e3df")
        ax.set_title(f"step {s['index']}: {axis} {s['sign']:+d} x {speed:g} m/s (clock x{s['clock_scale']:.2f})")
        ax.set_xlabel("PX4 time from onset (s)")
        ax.set_ylabel("speed along command (m/s)")
    axes.flat[0].legend(fontsize=7)
    fig.suptitle("L1.5: " + OBSERVED, fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


# =================================================================================================== phases
def git_state() -> str:
    import subprocess
    try:
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short=12", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", "."], capture_output=True,
                               text=True, check=True).stdout.strip()
        return head + (" (dirty)" if dirty else "")
    except Exception:  # noqa: BLE001
        return "unknown"


def extract_phase(args) -> int:
    run_dir = Path(args.run_dir).resolve()
    if (run_dir / "extract.json").exists():
        print(f"refused: {run_dir}/extract.json exists (a new run needs a new folder)", file=sys.stderr)
        return 2
    run_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    streams = load_streams(Path(args.l14_run).resolve())
    ext = extract_from_streams(streams)
    ext["source"].update(bag_sha256=_sha256(Path(ext["source"]["bag"])),
                         ulog_sha256=_sha256(Path(ext["source"]["ulog"])))
    ext["meta"] = {"date": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "commit": git_state(),
                   "wall_s": round(time.time() - t0, 1), "command": " ".join(sys.argv)}
    save_extract(ext, run_dir)
    sc = [s["clock_scale"] for s in ext["steps"]]
    print(f"extracted {len(ext['steps'])} steps (skipped {ext['skipped']}); clock scale {min(sc):.3f} to {max(sc):.3f}; "
          f"worst alignment residual {max(s['align_residual_rms_mps'] for s in ext['steps']):.4f} m/s; "
          f"worst onset spread {max(s['align_onset_spread_s'] for s in ext['steps']):.3f} s -> {run_dir}/extract.json")
    return 0


def fixture_phase(args) -> int:
    streams = load_streams(Path(args.l14_run).resolve())
    size = cut_fixture(streams, [int(x) for x in args.steps.split(",")], Path(args.out))
    print(f"fixture {args.out}: {size} bytes")
    return 0 if size < 1_000_000 else 1


def _world_factory(args, airframe, dt):
    cache = {}

    def make(p):
        if args.world == "torch":
            from svg_training.models.rigid_body import TorchRigidBodyWorld
            return TorchRigidBodyWorld(make.n, SLOTS, p.airframe, p.physics_dt_s, args.device)
        if "w" not in cache:
            from svg_training.compat import isaaclab_232 as isaac
            sim = isaac.make_physics_sim(dt, args.device)
            cache["w"] = isaac.IsaacWorld(sim, make.n, SLOTS, airframe, dt)
            isaac.physics_play(sim, cache["w"])
        return cache["w"]
    return make


def replay_phase(args) -> int:
    import torch

    run_dir = Path(args.run_dir).resolve()
    if (run_dir / "results.json").exists():
        print(f"refused: {run_dir}/results.json exists (a new run needs a new folder)", file=sys.stderr)
        return 2
    if not (run_dir / "extract.json").is_file():
        print(f"refused: no {run_dir}/extract.json (run the extract phase first)", file=sys.stderr)
        return 2
    t0 = time.time()
    ext = load_extract(run_dir)
    base, prov = load_sim_only_params(SIM_PARAMS)
    arms = arm_params(base)
    inputs, layout = batch_inputs(ext["steps"], args.replicas)
    torch.manual_seed(0)
    make = _world_factory(args, base.airframe, base.physics_dt_s)
    make.n = layout["games"]
    out = fly_arms(make, arms, inputs, args.device, seed=args.seed)
    np.savez_compressed(run_dir / "tier2.npz", layout=np.asarray(json.dumps(layout)),
                        **{f"{a}_{k}": np.asarray(v) for a, r in out.items() for k, v in r.items()})
    meta = {"world": args.world, "device": str(args.device), "replicas": args.replicas, "seed": args.seed,
            "games": layout["games"], "drones_per_game": SLOTS, "ticks": layout["ticks"], "params": prov,
            "arms": {a: {"state_delay_s": p.state_delay_s, **{k: getattr(p, k) for k in ERROR_KEYS},
                         "mpc_xy_p": p.gains.mpc_xy_p, "mpc_z_p": p.gains.mpc_z_p} for a, p in arms.items()},
            "gpu": torch.cuda.get_device_name() if str(args.device).startswith("cuda") else "cpu",
            "wall_s": round(time.time() - t0, 1), "commit": git_state(),
            "date": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "command": " ".join(sys.argv),
            "of_record": args.world == "isaac"}
    (run_dir / "replay_meta.json").write_text(json.dumps(_jsonable(meta), indent=1))
    return report(run_dir, ext, out, layout, meta)


def _load_tier2(run_dir: Path) -> tuple[dict, dict]:
    z = np.load(run_dir / "tier2.npz", allow_pickle=False)
    layout = json.loads(str(z["layout"]))
    out: dict = {}
    for k in z.files:
        if k == "layout":
            continue
        arm, key = k.split("_", 1)
        v = z[k]
        out.setdefault(arm, {})[key] = v if v.ndim else v.item()
    return {a: out[a] for a in ARMS if a in out}, layout


def report(run_dir: Path, ext: dict, out: dict, layout: dict, meta: dict) -> int:
    res = analyse(ext, out, layout)
    res["meta"] = meta
    res["observed"] = OBSERVED
    (run_dir / "results.json").write_text(json.dumps(_jsonable(res), indent=1))
    (run_dir / "results.md").write_text(results_md(res, meta))
    try:
        figure(ext, res, out, layout, run_dir / "l15_steps.png")
    except ImportError:
        print("no matplotlib: figure skipped", file=sys.stderr)
    for arm, d in res["summary"].items():
        print(f"{arm}: " + ", ".join(f"{m} {d[m]['within']}/{d[m]['cells']} within" for m in METRICS))
    print(f"health: {res['health']}")
    print(f"written {run_dir}/results.json, results.md, l15_steps.png")
    return 0


def report_phase(args) -> int:
    run_dir = Path(args.run_dir).resolve()
    ext = load_extract(run_dir)
    out, layout = _load_tier2(run_dir)
    meta = json.loads((run_dir / "replay_meta.json").read_text())
    return report(run_dir, ext, out, layout, meta)


def parser(isaac: bool = False) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("phase", choices=("extract", "fixture", "replay", "report"))
    ap.add_argument("--l14-run", help="extract / fixture: the L1.4 run folder (bag, PX4 log, steps.json, steps_flown.json)")
    ap.add_argument("--run-dir", help="this comparison's folder (extract.json, tier2.npz, results)")
    ap.add_argument("--steps", default="1,17,18", help="fixture: step indices")
    ap.add_argument("--out", help="fixture: the .npz to write")
    ap.add_argument("--world", choices=("torch", "isaac"), default="torch")
    ap.add_argument("--replicas", type=int, default=4, help="games per step (the error arm's seeds)")
    ap.add_argument("--seed", type=int, default=0, help="the estimate error's noise seed")
    if not isaac:
        ap.add_argument("--device", default="cpu")
        ap.add_argument("--headless", action="store_true", help="required with --world isaac")
    return ap


def _isaac_main() -> int:
    """Isaac Sim starts headless before torch is imported; the process leaves through os._exit."""
    code = 1
    try:
        from _isaac_app import start_headless
        args, _app = start_headless(parser(isaac=True))
        args.device = getattr(args, "device", None) or "cuda:0"
        code = replay_phase(args)
    except KeyboardInterrupt:
        code = 4
    except SystemExit as ex:
        code = ex.code if isinstance(ex.code, int) else 2
    except BaseException:  # noqa: BLE001
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)          # never simulation_app.close() (it swallows exit codes)
    return code


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.phase in ("extract", "fixture") and not args.l14_run:
            print("refused: --l14-run is needed", file=sys.stderr)
            return 2
        if args.phase == "fixture":
            if not args.out:
                print("refused: --out is needed", file=sys.stderr)
                return 2
            return fixture_phase(args)
        if not args.run_dir:
            print("refused: --run-dir is needed", file=sys.stderr)
            return 2
        if args.phase == "extract":
            return extract_phase(args)
        if args.phase == "replay":
            if args.world == "isaac":
                print("refused: --world isaac starts Isaac Lab: run with --headless", file=sys.stderr)
                return 2
            return replay_phase(args)
        return report_phase(args)
    except (FileNotFoundError, ValueError) as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if "replay" in sys.argv[1:] and "isaac" in sys.argv[1:]:
        if "--headless" not in sys.argv[1:]:
            print("refused: this starts Isaac Lab: --headless", file=sys.stderr)
            sys.exit(2)
        _isaac_main()
    sys.exit(main())
