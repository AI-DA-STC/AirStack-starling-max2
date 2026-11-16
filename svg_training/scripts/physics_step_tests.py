#!/usr/bin/env python3
"""S2b step tests: the physics drone against the tier 1 Starling layer and against the real drone's flight log.

    # 1. host, CPU, no Isaac: the six held-out legs of log103 (S1's windows), saved for the run
    python scripts/physics_step_tests.py --phase windows --name <date>_s2b_step_tests
    # 2. Isaac Lab, headless, after scripts/isaac_preflight.sh (host: the conda env_isaaclab python)
    python scripts/physics_step_tests.py --phase run --headless --gates configs/s2b.toml --name <date>_s2b_step_tests
    #    the same without Isaac (PyTorch reference world; a dry run, never a run of record)
    python scripts/physics_step_tests.py --phase run --world torch --device cpu --name <dry> --windows runs/<n>/windows.npz
    # 3. no Isaac: figures, the record and the next free T row of records/LEDGER.md, from the run's own files
    python scripts/physics_step_tests.py --phase record --name <date>_s2b_step_tests

What the run phase does, in one process and one world of N games x 2 drone slots (N = 6):

  steps   the ``[step_tests]`` steps through the FULL layers, as the game would fly them: the commander copy and
          the safety filter (every pair, ``configs/s2_game.toml`` settings, committed neutral values, no local file),
          then the drone model. Each game is a 1v1 layout: slot 0 is the drone that is commanded, slot 1 stands still
          10 m away (-10 m in x), so the filter never acts. First 10 s of hover from rest (every game, every slot),
          then each game flies one step (game g flies step g mod 5; game 5 repeats x_strike): 0.5 s of hold, the
          command for ``push_s``, then ``then_mps`` (if given) or zero for ``release_s``. The same commands go to
          (a) the physics drone in the world (Isaac Lab), (b) the tier 1 Starling layer (fitted, exploratory drone
          model) in the same process on the same device, (c) the physics drone with drone_1's 30 deg tilt limit
          (D11, INFO) and (d) on an Isaac run, the physics drone in the PyTorch reference world (INFO). The game's
          rules (walls, height band, zone, resets) are NOT in the loop: the layers are driven directly.
  replay  the six held-out legs of log103 at setpoint level: the logged trajectory setpoint (position, speed,
          acceleration feed-forward ``derived`` as S1 kept it, height, yaw and yaw rate) is sampled at the 0.05 s
          game tick, as the commander sends it, and held over the tick; it goes straight into ``PhysicsDrone`` (no
          commander, no filter). Game i flies leg i from the leg's measured position, speed and heading, level.
          Timing (pinned by tests/test_step_tests.py::test_replay_tick_timing): the setpoint held during tick k is
          the window's setpoint at t0 + k * 0.05 s; the state after tick k is at t0 + (k + 1) * 0.05 s.

Scoring (the same definitions as S1):
  real log   per leg: RMS over the leg's measured samples of the 2-D speed error |v_model - v_logged| (S1
             ``[fit_gates]``, ``models/fit.evaluate``: "RMS over each held-out step window", the worst leg is gated);
             t63 per change (start and stop of each leg, ``fit_real_px4.leg_changes``, levels from the logged
             speed): |t63_model - t63_logged|, inf if either never gets there, the worst change is gated. INFO beside
             it: S1's pooled per-axis RMS, the same scores for tier 1 (the S1 drone model, ``simulate_window``) and the
             extra delay in [-0.10, 0.30] s that minimises the pooled RMS (D7: reported, never applied; computed by
             shifting the physics trace in time, not by flying it again).
  tier 1     per gated step (every step whose name does not end in "_info"): ``step_metrics`` of the speed along the
             command, physics against tier 1, over the step (hold + push + release); t63 at the push and at the
             release with the command's levels for both traces; the largest RMS and the largest t63 gap are gated.
  hover      drift = largest 3-D distance from the start position over the 10 s, every game and slot; tilt spread =
             per drone standard deviation of the tilt (tick samples, 20 Hz) over the last 5 s, the largest is gated;
             the largest tilt seen at any physics step is reported beside it.
  peak tilt and upsets: every phase of the physics drone in the world with the 45 deg limit (hover, steps, replay);
             the 30 deg variant and the PyTorch world are INFO.
Verdict (``step_verdict``): FAIL if any judged gate fails (NaN, inf or a missing value fails); else INFO if fewer
than ``real_min_windows`` legs were found (the real-log gates are then not judged); else PASS.

Exit codes: 0 done (PASS / FAIL / INFO is in the files); 1 crash; 2 bad arguments, wrong or missing log, a run that
exists already. The run phase writes ``gates.toml`` (copied before the run), ``arrays.npz`` and ``results.json``;
the record phase writes ``docs/figures/s2b_steps.png``, ``docs/figures/s2b_real_replay.png``, the record and the
ledger row (the T number is read when the row is appended).
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime
import hashlib
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import tomllib
import traceback

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))
from svg_training.models.px4_trajectory import time_to_63pct  # noqa: E402  (numpy only)

TICK_S = 0.05                              # one game tick (core.game_config.TICK_S)
LEAD_S = 0.5                               # hold before each step's push
FAR_OFFSET_M = (-10.0, 0.0, 0.0)           # slot 1: the other drone of the 1v1 layout, still, 10 m away
DRONES = 2
ACCEL_FF = "derived"                       # S1's kept feed-forward source (runs/2026-11-15_s1_real_px4_exploratory)
S1_RUN = ROOT / "runs" / "2026-11-15_s1_real_px4_exploratory"
TIER1_PARAMS = ROOT / "params" / "real_exploratory_v0.toml"
DELAYS_S = tuple(round(-0.10 + 0.01 * i, 2) for i in range(41))      # D7 INFO: -0.10 ... 0.30 s
FIRST_LINE = ("Simulator: observed in the training simulator (tier 2, Isaac Lab) and tier 1, against real flight logs "
              "(13 November 2026, drone_2)")
FIG_STEPS = ROOT / "docs" / "figures" / "s2b_steps.png"
FIG_REPLAY = ROOT / "docs" / "figures" / "s2b_real_replay.png"
REAL_GATES = ("real_vel_rms_max_mps", "real_t63_err_max_s")
MIN_GATES = ("real_min_windows",)          # "value >= limit"; every other gate is "value <= limit"


# =================================================================================================== metrics (CPU)
def step_metrics(t_s: "np.ndarray", v_a: "np.ndarray", v_b: "np.ndarray", t_change_s: list[float],
                 levels_mps: "list[tuple[float, float]] | None" = None) -> dict:
    """Compare two speed traces v_a, v_b (T,) (m/s, e.g. along the command) on the time grid t_s (T,) (s).

    rms_mps: RMS of v_a - v_b over every finite sample. At every change time in t_change_s: the time to 63 % of the
    change (``px4_trajectory.time_to_63pct``) for each trace, looking only inside that change's segment (up to the
    next change), with ONE level pair shared by both traces: ``levels_mps[i]`` = (from, to) if given (the command's
    levels), else b's value at the change and b's last value in the segment. NaN where a trace never gets there.
    t63_gap_s[i] = |t63_a - t63_b| (NaN if either is NaN). peak_a_mps / peak_b_mps = largest |speed|.
    """
    t, a, b = (np.asarray(x, dtype=float) for x in (t_s, v_a, v_b))
    d = a - b
    ok = np.isfinite(d)
    out = {"rms_mps": float(np.sqrt(np.mean(d[ok] ** 2))) if ok.any() else math.nan,
           "t63_a_s": [], "t63_b_s": [], "t63_gap_s": [], "levels_mps": [],
           "peak_a_mps": float(np.nanmax(np.abs(a))) if np.isfinite(a).any() else math.nan,
           "peak_b_mps": float(np.nanmax(np.abs(b))) if np.isfinite(b).any() else math.nan}
    for i, t_on in enumerate(t_change_s):
        t_next = t_change_s[i + 1] if i + 1 < len(t_change_s) else math.inf
        seg = (t >= t_on - 1e-9) & (t < t_next - 1e-9)
        if levels_mps is not None:
            l0, l1 = (float(x) for x in levels_mps[i])
        else:
            l0 = float(np.interp(t_on, t, b))
            l1 = float(b[seg][-1]) if seg.any() else math.nan
        ta = time_to_63pct(t[seg], a[seg], l0, l1, t_on) if seg.any() else math.nan
        tb = time_to_63pct(t[seg], b[seg], l0, l1, t_on) if seg.any() else math.nan
        out["t63_a_s"].append(ta)
        out["t63_b_s"].append(tb)
        out["t63_gap_s"].append(abs(ta - tb) if math.isfinite(ta) and math.isfinite(tb) else math.nan)
        out["levels_mps"].append((l0, l1))
    return out


def _judged_ok(v, limit, kind: str) -> bool:
    if v is None or isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return False
    return v >= limit if kind == ">=" else v <= limit


def gate_rows(measured: dict, gates: dict) -> list[dict]:
    """One row per ``[step_gates]`` entry, in the file's order: gate, limit, kind ("<=" or ">="), value, result.

    result: PASS / FAIL, or INFO for ``real_min_windows`` when fewer legs were found and for the real-log gates then
    (not judged). A NaN, inf or missing value fails its gate."""
    windows = measured.get("real_min_windows")
    short = not _judged_ok(windows, gates.get("real_min_windows", 0), ">=")
    rows = []
    for key, limit in gates.items():
        kind = ">=" if key in MIN_GATES else "<="
        v = measured.get(key)
        if key in MIN_GATES:
            result = "PASS" if not short else "INFO"
        elif key in REAL_GATES and short:
            result = "INFO"
        else:
            result = "PASS" if _judged_ok(v, limit, kind) else "FAIL"
        rows.append({"gate": key, "limit": limit, "kind": kind, "value": v, "result": result})
    return rows


def step_verdict(results: dict, gates: dict) -> str:
    """"PASS" | "FAIL" | "INFO" from results["measured"] ({gate name: value}) against ``[step_gates]``:
    FAIL if any judged gate fails; else INFO if fewer windows than ``real_min_windows`` (real-log gates not judged);
    else PASS."""
    res = [r["result"] for r in gate_rows(results["measured"], gates)]
    return "FAIL" if "FAIL" in res else ("INFO" if "INFO" in res else "PASS")


def model_on_grid(t_grid_s: "np.ndarray", t_model_s: "np.ndarray", v_model: "np.ndarray") -> "np.ndarray":
    """A model trace v_model (K, k) at times t_model_s (K,), linearly interpolated onto t_grid_s (T,) -> (T, k)."""
    v = np.asarray(v_model, dtype=float)
    return np.stack([np.interp(t_grid_s, t_model_s, v[:, j]) for j in range(v.shape[1])], axis=-1)


def window_rms_mps(v_grid: "np.ndarray", meas_idx: "np.ndarray", v_meas: "np.ndarray") -> float:
    """S1 [fit_gates] definition: sqrt(mean over the measured samples of |v_model - v_meas|^2) (error-vector norm)."""
    e = v_grid[np.asarray(meas_idx)] - np.asarray(v_meas)
    ok = np.isfinite(e).all(axis=-1)
    return float(np.sqrt(np.mean(np.sum(e[ok] ** 2, axis=-1)))) if ok.any() else math.nan


def _t63_err(model_s, meas_s) -> float:
    """|t63_model - t63_logged|; inf if either never gets there (models/fit.evaluate)."""
    if model_s is None or meas_s is None or not (math.isfinite(model_s) and math.isfinite(meas_s)):
        return math.inf
    return abs(model_s - meas_s)


# =================================================================================================== the log windows
def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tier1_px4_params():
    """The S1 drone model (tier 1's exploratory PX4 response) as px4_trajectory.TrajectoryParams."""
    from svg_training.models import px4_trajectory as m

    px4 = dict(tomllib.loads(TIER1_PARAMS.read_text())["px4"])
    px4.pop("model_dt_s", None)
    return m.TrajectoryParams.from_dict(px4)


def _interp_finite(t, tp, xp, fill: float) -> "np.ndarray":
    ok = np.isfinite(xp)
    return np.interp(t, tp[ok], xp[ok]) if ok.any() else np.full_like(np.asarray(t, float), fill)


def _hold(t, tp, xp, fill: float) -> "np.ndarray":
    """Zero-order hold: the last logged sample at or before each t; NaN (PX4: "not set") and before the first sample
    -> fill."""
    idx = np.searchsorted(tp, t, side="right") - 1
    v = np.where(idx >= 0, np.asarray(xp, float)[np.clip(idx, 0, len(xp) - 1)], np.nan)
    return np.where(np.isfinite(v), v, fill)


def build_windows(log: pathlib.Path) -> tuple[list[dict], dict]:
    """Rebuild S1's windows from the log (``load_flight`` + ``make_windows``, feed-forward ``derived``), keep the
    held-out legs (odd indices, ``split_alternate``) and add height, yaw and the start state for the physics drone,
    plus the tier 1 (S1 model) prediction of each leg. Returns (windows, meta)."""
    import fit_real_px4 as frp
    from svg_training.models import px4_trajectory as m

    f = frp.load_flight(log)
    windows, legs = frp.make_windows(f, ACCEL_FF)
    train, held = m.split_alternate(len(windows))
    meta = {"log": str(log), "accel_ff": ACCEL_FF, "legs_found": len(windows), "held_out": list(held),
            "train": list(train), "legs": legs}
    split = S1_RUN / "split.json"
    if split.exists():
        s1 = json.loads(split.read_text())
        meta["matches_s1_split"] = bool(s1["held_out"] == list(held) and s1["legs"] == legs)
    data, _p, _c = frp.read_ulog_full(log, ("trajectory_setpoint", "vehicle_local_position"))
    ts, lp = data["trajectory_setpoint"], data["vehicle_local_position"]
    t0 = lp["timestamp"][0]                                         # the same zero as load_flight
    t_sp = (np.asarray(ts["timestamp"]) - t0) / 1e6
    t_lp = (np.asarray(lp["timestamp"]) - t0) / 1e6
    z_sp = -np.asarray(ts["position[2]"], float)                   # NED down -> ENU up
    vz_ff = -np.asarray(ts["velocity[2]"], float)
    yaw_ned = np.asarray(ts["yaw"], float)
    yaw_rate_ned = np.asarray(ts["yawspeed"], float)
    z = -np.asarray(lp["z"], float)
    vz = -np.asarray(lp["vz"], float)
    heading_ned = np.asarray(lp["heading"], float)
    ok = np.isfinite(yaw_ned)
    yaw_unwrapped = np.full_like(yaw_ned, np.nan)
    yaw_unwrapped[ok] = np.unwrap(yaw_ned[ok])
    params = tier1_px4_params()
    s1_rms = {}
    if (S1_RUN / "results.json").exists():
        s1_rms = {int(r["leg"]): float(r["rms_mps"]) for r in json.loads((S1_RUN / "results.json").read_text())["legs"]}
    out, checks = [], []
    for i in held:
        w = windows[i]
        t = w.t_s
        j0 = int(np.argmin(np.abs(t_lp - t[0])))
        h0 = float(z[j0])
        zs = _interp_finite(t, t_sp, z_sp, h0)
        vzs = _interp_finite(t, t_sp, vz_ff, 0.0)
        head0_enu = math.pi / 2 - float(heading_ned[j0]) if math.isfinite(heading_ned[j0]) else 0.0
        yaw_enu = math.pi / 2 - _hold(t, t_sp, yaw_unwrapped, math.pi / 2 - head0_enu)   # held, as PX4 holds it
        yaw_rate_enu = -_hold(t, t_sp, yaw_rate_ned, 0.0)                                 # NaN = no feed-forward
        v_t1 = m.simulate_window(params, w)
        rms_t1_axis = m.velocity_rms(params, [w])
        if i in s1_rms:
            checks.append(abs(round(rms_t1_axis, 4) - s1_rms[i]))
        out.append({
            "leg": int(i), "t_s": t,
            "p_sp": np.column_stack([w.p_sp, zs]), "v_ff": np.column_stack([w.v_ff, vzs]),
            "a_ff": np.column_stack([w.a_ff, np.gradient(vzs, t)]),
            "yaw_sp": yaw_enu, "yaw_rate": yaw_rate_enu,
            "p0": np.array([w.p0[0], w.p0[1], h0]), "v0": np.array([w.v0[0], w.v0[1], float(vz[j0])]),
            "heading0": head0_enu, "meas_idx": np.asarray(w.meas_idx), "v_meas": np.asarray(w.v_meas),
            "v_tier1": v_t1, "a0": np.asarray(w.a0) if w.a0 is not None else np.zeros(2),
        })
    meta["windows"] = len(out)
    meta["tier1_rms_reproduces_s1_max_abs_diff_mps"] = max(checks) if checks else None
    meta["tier1_params"] = str(TIER1_PARAMS.relative_to(ROOT))
    return out, meta


WIN_KEYS = ("t_s", "p_sp", "v_ff", "a_ff", "yaw_sp", "yaw_rate", "p0", "v0", "meas_idx", "v_meas", "v_tier1", "a0")


def save_windows(path: pathlib.Path, wins: list[dict], meta: dict) -> None:
    arrays = {f"w{k}_{key}": np.asarray(w[key]) for k, w in enumerate(wins) for key in WIN_KEYS}
    arrays.update({f"w{k}_heading0": np.asarray(w["heading0"]) for k, w in enumerate(wins)})
    arrays.update({f"w{k}_leg": np.asarray(w["leg"]) for k, w in enumerate(wins)})
    np.savez(path, **arrays)
    path.with_suffix(".json").write_text(json.dumps(meta, indent=1))


def load_windows(path: pathlib.Path) -> tuple[list[dict], dict]:
    """The windows saved by the windows phase; each also gets ``window`` (px4_trajectory.Window, 2-D, for
    ``fit_real_px4.leg_changes``)."""
    from svg_training.models import px4_trajectory as m

    d = np.load(path)
    meta = json.loads(path.with_suffix(".json").read_text())
    wins = []
    for k in range(int(meta["windows"])):
        w = {key: d[f"w{k}_{key}"] for key in WIN_KEYS}
        w["heading0"] = float(d[f"w{k}_heading0"])
        w["leg"] = int(d[f"w{k}_leg"])
        w["window"] = m.Window(t_s=w["t_s"], p_sp=w["p_sp"][:, :2], v_ff=w["v_ff"][:, :2], a_ff=w["a_ff"][:, :2],
                               p0=w["p0"][:2], v0=w["v0"][:2], meas_idx=w["meas_idx"], v_meas=w["v_meas"],
                               label=f"leg {w['leg']}", a0=w["a0"])
        wins.append(w)
    return wins, meta


def windows_phase(args) -> int:
    gates_cfg = tomllib.loads(_gates_path(args).read_text())
    st = gates_cfg["step_tests"]
    log = pathlib.Path(args.log or os.path.expanduser(st["real_log"]))
    if not log.is_file():
        print(f"refused: no flight log at {log}", file=sys.stderr)
        return 2
    sha = sha256_file(log)
    if not sha.startswith(st["real_log_sha256_prefix"]):
        print(f"refused: {log} has sha256 {sha[:16]}..., the config expects {st['real_log_sha256_prefix']}...",
              file=sys.stderr)
        return 2
    wins, meta = build_windows(log)
    meta["sha256"] = sha
    run_dir = pathlib.Path(args.runs_dir) / args.name
    run_dir.mkdir(parents=True, exist_ok=True)
    save_windows(run_dir / "windows.npz", wins, meta)
    print(f"{meta['legs_found']} legs found, held out {meta['held_out']}; matches S1's split: "
          f"{meta.get('matches_s1_split')}; tier 1 RMS reproduces S1 within "
          f"{meta['tier1_rms_reproduces_s1_max_abs_diff_mps']} m/s; wrote {run_dir / 'windows.npz'}")
    return 0


# =================================================================================================== flying (torch)
def replay(drone, wins: list[dict], device) -> dict:
    """Fly the windows at setpoint level through ``drone`` (PhysicsDrone, N games x 2 slots; game g flies window
    g mod len(wins); slot 1 holds still 10 m away). Timing in the module docstring. Returns numpy arrays:
    t_rel_s (K+1,), vel_mps / pos_m (K+1, N, 2, 3) (sample 0 = the start state), ticks per window (to cover its
    window), max_tilt_deg (N, 2), upsets, nonfinite."""
    import torch

    n, m = int(drone.pos_m.shape[0]), int(drone.pos_m.shape[1])
    ticks = [int(math.ceil((w["t_s"][-1] - w["t_s"][0]) / TICK_S - 1e-9)) for w in wins]
    k_max = max(ticks)
    far = np.asarray(FAR_OFFSET_M)
    p_sp = np.zeros((k_max, n, m, 3))
    v_ff = np.zeros((k_max, n, m, 3))
    a_ff = np.zeros((k_max, n, m, 3))
    yaw = np.zeros((k_max, n, m))
    rate = np.zeros((k_max, n, m))
    pos0, vel0, yaw0 = np.zeros((n, m, 3)), np.zeros((n, m, 3)), np.zeros((n, m))
    for g in range(n):
        w = wins[g % len(wins)]
        dt_grid = float(w["t_s"][1] - w["t_s"][0])
        idx = np.clip(np.round(np.arange(k_max) * TICK_S / dt_grid).astype(int), 0, len(w["t_s"]) - 1)
        p_sp[:, g, 0], v_ff[:, g, 0], a_ff[:, g, 0] = w["p_sp"][idx], w["v_ff"][idx], w["a_ff"][idx]
        yaw[:, g, 0], rate[:, g, 0] = w["yaw_sp"][idx], w["yaw_rate"][idx]
        pos0[g, 0], vel0[g, 0], yaw0[g] = w["p0"], w["v0"], w["heading0"]
        pos0[g, 1] = w["p0"] + far
        p_sp[:, g, 1] = pos0[g, 1]
        yaw[:, g, 1] = w["heading0"]
    t = lambda x: torch.as_tensor(x, dtype=torch.float32, device=device)       # noqa: E731
    mask = torch.ones(n, m, dtype=torch.bool, device=device)
    drone.reset(mask, t(pos0), t(yaw0))
    drone.write_clamped(mask, t(pos0), t(vel0))                                   # start with the leg's speed, level
    vel, pos = [drone.vel_mps.clone()], [drone.pos_m.clone()]
    sp = [t(x) for x in (p_sp, v_ff, a_ff, yaw, rate)]
    for k in range(k_max):
        drone.step_setpoint(sp[0][k], sp[1][k], sp[2][k], sp[3][k], sp[4][k])
        vel.append(drone.vel_mps.clone())
        pos.append(drone.pos_m.clone())
    return {"t_rel_s": np.arange(k_max + 1) * TICK_S, "vel_mps": torch.stack(vel).cpu().numpy(),
            "pos_m": torch.stack(pos).cpu().numpy(), "ticks": ticks,
            "max_tilt_deg": torch.rad2deg(drone.max_tilt_rad).cpu().numpy(), "upsets": int(drone.upset.sum()),
            "nonfinite": int(drone.nonfinite_count)}


def step_schedule(steps: list[dict], n: int) -> tuple["np.ndarray", list[dict]]:
    """Commands [T, N, 3] (game g flies step g mod len(steps), padded with zero) and per-game timing."""
    lead = round(LEAD_S / TICK_S)
    info, total = [], []
    for g in range(n):
        s = steps[g % len(steps)]
        push, rel = round(float(s["push_s"]) / TICK_S), round(float(s["release_s"]) / TICK_S)
        info.append({"step": s["name"], "lead": lead, "push": push, "release": rel})
        total.append(lead + push + rel)
    cmd = np.zeros((max(total), n, 3))
    for g, i in enumerate(info):
        s = steps[g % len(steps)]
        cmd[i["lead"]:i["lead"] + i["push"], g] = s["cmd_mps"]
        cmd[i["lead"] + i["push"]:i["lead"] + i["push"] + i["release"], g] = s.get("then_mps", [0.0, 0.0, 0.0])
        i["ticks"] = total[g]
    return cmd, info


def run_steps(layer, steps: list[dict], n: int, device, hover_s: float, height_m: float, physics: bool) -> dict:
    """Hover from rest for hover_s, then each game's step (``step_schedule``), through ``layer`` (PhysicsLayer or
    StarlingLayer) with slot 0 commanded and slot 1 still. Returns numpy arrays."""
    import torch

    m = DRONES
    pos0 = torch.zeros(n, m, 3, device=device)
    pos0[..., 2] = height_m
    pos0[:, 1] += torch.tensor(FAR_OFFSET_M, device=device)
    alive = torch.ones(n, m, dtype=torch.bool, device=device)
    layer.reset(alive, pos0, torch.zeros(n, m, device=device))
    if hasattr(layer, "flush"):
        layer.flush()
    pos = pos0.clone()
    zero = torch.zeros(n, m, 3, device=device)
    log = {"hover_pos": [pos0.clone()], "hover_vel": [], "hover_tilt": [], "step_vel": [], "step_pos": [],
           "step_tilt": []}

    def tilt():
        return layer.drone.tilt_rad.clone() if physics else torch.zeros(n, m, device=device)

    for _ in range(round(hover_s / TICK_S)):
        pos, vel, _c = layer.step(zero, pos, alive)
        log["hover_pos"].append(pos.clone())
        log["hover_vel"].append(vel.clone())
        log["hover_tilt"].append(tilt())
    out = {}
    if physics:
        out["hover_max_tilt_deg"] = torch.rad2deg(layer.drone.max_tilt_rad).cpu().numpy()
        out["hover_upsets"] = int(layer.drone.upset.sum())
    log["step_vel"].append(vel.clone())                     # sample 0 of each step: the state at its start
    log["step_pos"].append(pos.clone())
    log["step_tilt"].append(tilt())
    sched, info = step_schedule(steps, n)
    sched_t = torch.as_tensor(sched, dtype=torch.float32, device=device)
    for k in range(sched.shape[0]):
        c = zero.clone()
        c[:, 0] = sched_t[k]
        pos, vel, _c = layer.step(c, pos, alive)
        log["step_vel"].append(vel.clone())
        log["step_pos"].append(pos.clone())
        log["step_tilt"].append(tilt())
    for key, v in log.items():
        out[key] = torch.stack(v).cpu().numpy()
    out["cmd"] = sched
    out["schedule"] = info
    if physics:
        out["max_tilt_deg"] = torch.rad2deg(layer.drone.max_tilt_rad).cpu().numpy()
        out["upsets"] = int(layer.drone.upset.sum())
        out["nonfinite"] = int(layer.drone.nonfinite_count)
    return out


# =================================================================================================== analysis (CPU)
def along(vel: "np.ndarray", cmd) -> tuple["np.ndarray", "np.ndarray"]:
    """Speed along the step's command (vel [..., 3]) and the unit axis."""
    axis = np.asarray(cmd, dtype=float)
    axis = axis / np.linalg.norm(axis)
    return vel @ axis, axis


def analyse_steps(arr: dict, steps: list[dict], gates_cfg: dict) -> dict:
    """Hover and step metrics from the arrays of ``run_steps`` (keys prefixed by the variant)."""
    st = gates_cfg["step_tests"]
    hover_s = float(st["hover_s"])
    out: dict = {"hover": {}, "steps": [], "tilt30": {}, "torch": {}}
    hp = arr["physics_hover_pos"]                                                  # [T+1, N, M, 3]
    drift = np.linalg.norm(hp - hp[:1], axis=-1)
    tilt = np.degrees(arr["physics_hover_tilt"])                                   # [T, N, M]
    last = tilt[-round(5.0 / TICK_S):]
    out["hover"] = {"drift_max_m": float(drift.max()), "tilt_std_max_deg": float(last.std(axis=0).max()),
                    "tilt_max_tick_deg": float(tilt.max()),
                    "tilt_max_physics_step_deg": float(arr["physics_hover_max_tilt_deg"].max()),
                    "upsets": int(arr["physics_hover_upsets"]), "seconds": hover_s,
                    "tier1_drift_max_m": float(np.linalg.norm(arr["tier1_hover_pos"] - arr["tier1_hover_pos"][:1],
                                                              axis=-1).max())}
    n = arr["physics_step_vel"].shape[1]
    sched = json.loads(str(arr["schedule"]))
    t_all = np.arange(arr["physics_step_vel"].shape[0]) * TICK_S
    for g in range(n):
        s = steps[g % len(steps)]
        info = sched[g]
        lead_s, push_s = info["lead"] * TICK_S, info["push"] * TICK_S
        end = info["ticks"] + 1
        t = t_all[:end]
        cmd = np.asarray(s["cmd_mps"], float)
        then = np.asarray(s.get("then_mps", [0.0, 0.0, 0.0]), float)
        level = float(np.linalg.norm(cmd))
        vp, axis = along(arr["physics_step_vel"][:end, g, 0], cmd)
        v1, _ = along(arr["tier1_step_vel"][:end, g, 0], cmd)
        levels = [(0.0, level), (level, float(then @ axis))]
        mt = step_metrics(t, vp, v1, [lead_s, lead_s + push_s], levels)
        row = {"game": g, "name": s["name"], "gated": not s["name"].endswith("_info"), "cmd_mps": s["cmd_mps"],
               "then_mps": s.get("then_mps"), "rms_vs_tier1_mps": mt["rms_mps"],
               "t63_physics_s": mt["t63_a_s"], "t63_tier1_s": mt["t63_b_s"], "t63_gap_s": mt["t63_gap_s"],
               "peak_physics_mps": mt["peak_a_mps"], "peak_tier1_mps": mt["peak_b_mps"],
               "max_tilt_deg_physics": float(np.degrees(arr["physics_step_tilt"][:end, g, 0]).max()),
               # INFO: wobble after the step (the hover gate's question, after an excitation): last 2 s of release
               "release_tail_tilt_std_deg": float(np.degrees(arr["physics_step_tilt"][max(end - 40, 0):end, g, 0]).std()),
               "cross_axis_max_mps": float(np.linalg.norm(arr["physics_step_vel"][:end, g, 0]
                                                          - np.outer(vp, axis), axis=-1).max())}
        for var in ("tilt30", "torch"):
            if f"{var}_step_vel" in arr:
                vv, _ = along(arr[f"{var}_step_vel"][:end, g, 0], cmd)
                row[f"rms_vs_{var}_mps"] = float(np.sqrt(np.mean((vp - vv) ** 2)))
                row[f"max_abs_diff_vs_{var}_mps"] = float(np.abs(vp - vv).max())
        out["steps"].append(row)
    first = {}
    for r in out["steps"]:
        first.setdefault(r["name"], r)
    dup = [r for r in out["steps"] if first[r["name"]] is not r]
    out["duplicate_games_max_diff_mps"] = max(
        (float(np.abs(along(arr["physics_step_vel"][:, r["game"], 0], r["cmd_mps"])[0]
                      - along(arr["physics_step_vel"][:, first[r["name"]]["game"], 0], r["cmd_mps"])[0]).max())
         for r in dup), default=None)
    gated = [r for r in out["steps"] if r["gated"] and first[r["name"]] is r]
    out["tier1_vel_rms_max_mps"] = max(r["rms_vs_tier1_mps"] for r in gated)
    gaps = [x for r in gated for x in r["t63_gap_s"]]
    out["tier1_t63_gap_max_s"] = math.inf if any(not math.isfinite(x) for x in gaps) else max(gaps)
    for var in ("tilt30", "torch"):
        if f"{var}_step_vel" in arr:
            out[var] = {"steps_rms_max_mps": max(r[f"rms_vs_{var}_mps"] for r in out["steps"]),
                        "steps_max_abs_diff_mps": max(r[f"max_abs_diff_vs_{var}_mps"] for r in out["steps"])}
            if f"{var}_max_tilt_deg" in arr:
                out[var]["peak_tilt_deg"] = float(arr[f"{var}_max_tilt_deg"].max())
                out[var]["upsets"] = int(arr[f"{var}_upsets"])
    return out


def score_replay(wins: list[dict], t_rel: "np.ndarray", vel: "np.ndarray") -> dict:
    """Score a replay (vel [K+1, N, M, 3], game g = window g) against the logged speed, S1's definitions; the
    tier 1 (S1 model) scores beside it; the D7 delay INFO."""
    import fit_real_px4 as frp

    legs, all_err_model, all_err_t1 = [], [], []
    for g, w in enumerate(wins):
        t = w["t_s"]
        vg = model_on_grid(t, t[0] + t_rel, vel[:, g, 0, :2])
        changes_p = frp.leg_changes(w["window"], vg)
        changes_t = frp.leg_changes(w["window"], w["v_tier1"])
        e_m = vg[w["meas_idx"]] - w["v_meas"]
        e_t = w["v_tier1"][w["meas_idx"]] - w["v_meas"]
        all_err_model.append(e_m[np.isfinite(e_m)])
        all_err_t1.append(e_t[np.isfinite(e_t)])
        legs.append({
            "leg": w["leg"], "game": g, "seconds": float(t[-1] - t[0]),
            "rms_physics_mps": window_rms_mps(vg, w["meas_idx"], w["v_meas"]),
            "rms_tier1_mps": window_rms_mps(w["v_tier1"], w["meas_idx"], w["v_meas"]),
            "changes": [{"change": cp["change"], "from_mps": cp["from_mps"], "to_mps": cp["to_mps"],
                         "t63_logged_s": cp["t63_measured_s"], "t63_setpoint_s": cp["t63_setpoint_s"],
                         "t63_physics_s": cp["t63_model_s"], "t63_tier1_s": ct["t63_model_s"],
                         "err_physics_s": _t63_err(cp["t63_model_s"], cp["t63_measured_s"]),
                         "err_tier1_s": _t63_err(ct["t63_model_s"], ct["t63_measured_s"])}
                        for cp, ct in zip(changes_p, changes_t)]})
    pooled = lambda errs: float(np.sqrt(np.mean(np.concatenate(errs) ** 2)))   # noqa: E731  S1 exploratory, per axis
    errs = [c["err_physics_s"] for leg in legs for c in leg["changes"]]
    errs_t1 = [c["err_tier1_s"] for leg in legs for c in leg["changes"]]
    out = {"legs": legs, "windows": len(wins),
           "vel_rms_worst_mps": max(leg["rms_physics_mps"] for leg in legs),
           "t63_err_worst_s": max(errs) if errs else math.inf, "t63_changes": len(errs),
           "pooled_axis_rms_mps": pooled(all_err_model),
           "tier1_vel_rms_worst_mps": max(leg["rms_tier1_mps"] for leg in legs),
           "tier1_t63_err_worst_s": max(errs_t1) if errs_t1 else math.inf,
           "tier1_pooled_axis_rms_mps": pooled(all_err_t1)}
    sweep = []
    for d in DELAYS_S:                          # D7 INFO: the physics trace shifted later by d (post hoc)
        worst, pool = [], []
        for g, w in enumerate(wins):
            vg = model_on_grid(w["t_s"], w["t_s"][0] + t_rel + d, vel[:, g, 0, :2])
            worst.append(window_rms_mps(vg, w["meas_idx"], w["v_meas"]))
            e = vg[w["meas_idx"]] - w["v_meas"]
            pool.append(e[np.isfinite(e)])
        sweep.append({"delay_s": d, "pooled_axis_rms_mps": pooled(pool), "vel_rms_worst_mps": max(worst)})
    best = min(sweep, key=lambda r: r["pooled_axis_rms_mps"])
    out["delay_sweep"] = sweep
    out["delay_best"] = best
    return out


def analyse(arr: dict, wins: list[dict], wmeta: dict, steps: list[dict], gates_cfg: dict) -> dict:
    res = {"steps": analyse_steps(arr, steps, gates_cfg)}
    res["replay"] = score_replay(wins, arr["physics_replay_t_rel_s"], arr["physics_replay_vel"])
    for var in ("tilt30", "torch"):
        if f"{var}_replay_vel" in arr:
            sc = score_replay(wins, arr[f"{var}_replay_t_rel_s"], arr[f"{var}_replay_vel"])
            res[f"replay_{var}"] = {k: sc[k] for k in ("vel_rms_worst_mps", "t63_err_worst_s",
                                                       "pooled_axis_rms_mps")}
            res[f"replay_{var}"]["max_abs_diff_vs_physics_mps"] = float(
                np.abs(arr[f"{var}_replay_vel"][:, :len(wins), 0] - arr["physics_replay_vel"][:, :len(wins), 0]).max())
    peak = max(float(arr["physics_max_tilt_deg"].max()), float(arr["physics_hover_max_tilt_deg"].max()),
               float(arr["physics_replay_max_tilt_deg"].max()))
    upsets = int(arr["physics_upsets"]) + int(arr["physics_replay_upsets"])
    s = res["steps"]
    res["measured"] = {
        "hover_drift_max_m": s["hover"]["drift_max_m"], "hover_tilt_std_max_deg": s["hover"]["tilt_std_max_deg"],
        "peak_tilt_max_deg": peak, "upsets_max": upsets, "real_min_windows": int(wmeta["windows"]),
        "real_vel_rms_max_mps": res["replay"]["vel_rms_worst_mps"],
        "real_t63_err_max_s": res["replay"]["t63_err_worst_s"],
        "tier1_vel_rms_max_mps": s["tier1_vel_rms_max_mps"], "tier1_t63_gap_max_s": s["tier1_t63_gap_max_s"]}
    res["nonfinite"] = int(arr["physics_nonfinite"]) + int(arr["physics_replay_nonfinite"])
    return res


# =================================================================================================== the run phase
def _gates_path(args) -> pathlib.Path:
    p = pathlib.Path(args.gates)
    return p if p.is_absolute() else (ROOT / p).resolve()


def gpu_compute_apps() -> str:
    try:
        return subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory,process_name",
                               "--format=csv,noheader"], capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return "nvidia-smi failed"


def git_state() -> str:
    try:
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, timeout=20).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", "."], capture_output=True,
                               text=True, timeout=20).stdout.strip()
        return f"{head}{'-dirty' if dirty else ''}" if head else "unknown"
    except Exception:
        return "unknown"


def _jsonable(x):
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.floating, float)):
        x = float(x)
        return x if math.isfinite(x) else ("inf" if x > 0 else ("-inf" if x < 0 else "nan"))
    if isinstance(x, np.integer):
        return int(x)
    return x


def _unjson(x):
    if isinstance(x, dict):
        return {k: _unjson(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_unjson(v) for v in x]
    if x in ("inf", "-inf", "nan"):
        return float(x)
    return x


def fly_all(args, world, world_label: str, gates_cfg: dict, wins: list[dict], device) -> tuple[dict, dict]:
    """Every phase on one world: physics (45 deg), physics (30 deg, INFO), tier 1, and on an Isaac run the PyTorch
    reference world (INFO). Returns (arrays, meta)."""
    import torch

    from svg_training.core.game_config import load_game_cfg
    from svg_training.core.physics_layer import PhysicsLayer, load_game_physics_params
    from svg_training.core.starling_layer import StarlingLayer
    from svg_training.models.physics_drone import PhysicsDrone
    from svg_training.models.physics_params import yaw_gains_text
    from svg_training.models.rigid_body import TorchRigidBodyWorld

    st = gates_cfg["step_tests"]
    steps = list(st["steps"])
    base, prov = load_game_cfg(use_local=False)                     # committed neutral values only
    cfg_p = base.replace(**{"starling.enabled": True, "starling.backend": "physics"})
    cfg_f = base.replace(**{"starling.enabled": True, "starling.backend": "fitted"})
    p = load_game_physics_params(cfg_p)
    p30 = dataclasses.replace(p, gains=dataclasses.replace(p.gains, mpc_tiltmax_air=float(st["tilt_info_deg"])))
    n = world.num_games
    hover_s, h = float(st["hover_s"]), float(base.arena.start_height_m)
    arr: dict = {}

    def put(prefix: str, d: dict) -> None:
        for k, v in d.items():
            if k == "schedule":
                arr["schedule"] = np.asarray(json.dumps(v))
            elif k == "t_rel_s" or k == "ticks":
                arr[f"{prefix}_{k}"] = np.asarray(v)
            else:
                arr[f"{prefix}_{k}"] = np.asarray(v)

    def phase(name: str, fn):
        t0 = time.time()
        r = fn()
        print(f"phase {name}: {time.time() - t0:.1f} s", flush=True)
        return r

    layer = PhysicsLayer(cfg_p, n, 1, 1, device, world)
    put("physics", phase("physics steps", lambda: run_steps(layer, steps, n, device, hover_s, h, True)))
    rp = phase("physics replay", lambda: replay(layer.drone, wins, device))
    put("physics_replay", {"t_rel_s": rp["t_rel_s"], "vel": rp["vel_mps"], "pos": rp["pos_m"], "ticks": rp["ticks"],
                           "max_tilt_deg": rp["max_tilt_deg"], "upsets": rp["upsets"], "nonfinite": rp["nonfinite"]})
    layer30 = PhysicsLayer(cfg_p, n, 1, 1, device, world)
    layer30.drone, layer30.params = PhysicsDrone(world, p30, device), p30
    put("tilt30", phase("tilt 30 steps", lambda: run_steps(layer30, steps, n, device, hover_s, h, True)))
    rp = phase("tilt 30 replay", lambda: replay(layer30.drone, wins, device))
    put("tilt30_replay", {"t_rel_s": rp["t_rel_s"], "vel": rp["vel_mps"], "max_tilt_deg": rp["max_tilt_deg"],
                          "upsets": rp["upsets"]})
    tier1 = StarlingLayer(cfg_f, n, 1, 1, device)
    put("tier1", phase("tier 1 steps", lambda: run_steps(tier1, steps, n, device, hover_s, h, False)))
    if world_label != "torch":
        tw = TorchRigidBodyWorld(n, DRONES, p.airframe, p.physics_dt_s, device)
        tl = PhysicsLayer(cfg_p, n, 1, 1, device, tw)
        put("torch", phase("torch steps", lambda: run_steps(tl, steps, n, device, hover_s, h, True)))
        rp = phase("torch replay", lambda: replay(tl.drone, wins, device))
        put("torch_replay", {"t_rel_s": rp["t_rel_s"], "vel": rp["vel_mps"], "max_tilt_deg": rp["max_tilt_deg"],
                             "upsets": rp["upsets"]})
    meta = {"games": n, "drones_per_game": DRONES, "world": world_label, "device": str(device),
            "physics_dt_s": p.physics_dt_s, "motor_lag": p.motor_lag, "rotor_geometry": p.rotor_geometry,
            "yaw_rate_gains": yaw_gains_text(p), "tilt_max_deg": p.gains.mpc_tiltmax_air,
            "tilt_info_deg": float(st["tilt_info_deg"]), "game_config": prov.game_file,
            "game_config_sha256": prov.game_sha256, "local_file": prov.local_file or "none",
            "filter_iterations": cfg_p.starling.filter_iterations,
            "filter_check_every": cfg_p.starling.filter_check_every, "preset": cfg_p.preset,
            "start_height_m": h, "far_offset_m": list(FAR_OFFSET_M), "lead_s": LEAD_S,
            "tier1_params": cfg_f.starling.params, "physics_params": cfg_p.starling.physics_params,
            "torch_float": str(torch.float32)}
    return arr, meta


def run_phase(args, nvsmi_before: str) -> int:
    import torch

    from svg_training.bench.rows import code_sha

    gates_path = _gates_path(args)
    gates_cfg = tomllib.loads(gates_path.read_text())
    run_dir = pathlib.Path(args.runs_dir) / args.name
    if (run_dir / "results.json").exists():
        print(f"refused: {run_dir}/results.json exists (a new run needs a new name)", file=sys.stderr)
        return 2
    wpath = pathlib.Path(args.windows) if args.windows else run_dir / "windows.npz"
    if not wpath.is_file():
        print(f"refused: no windows at {wpath} (run --phase windows on the host first)", file=sys.stderr)
        return 2
    run_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(gates_path, run_dir / "gates.toml")
    wins, wmeta = load_windows(wpath)
    date = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    t_start = time.time()
    device = torch.device(args.device)
    steps = list(gates_cfg["step_tests"]["steps"])
    n = max(len(wins), len(steps) + 1)
    from svg_training.core.game_config import load_game_cfg
    from svg_training.core.physics_layer import load_game_physics_params

    p = load_game_physics_params(load_game_cfg(use_local=False)[0].replace(
        **{"starling.enabled": True, "starling.backend": "physics"}))
    extent = None
    if args.world == "isaac":
        from svg_training.compat import isaaclab_232 as isaac

        sim = isaac.make_physics_sim(p.physics_dt_s, args.device)
        world = isaac.IsaacWorld(sim, n, DRONES, p.airframe, p.physics_dt_s)
        isaac.physics_play(sim, world)
        label = world.label
        extent = float(world.origins.norm(dim=-1).max()) + 10.0 + 2.0
    else:
        from svg_training.models.rigid_body import TorchRigidBodyWorld

        world = TorchRigidBodyWorld(n, DRONES, p.airframe, p.physics_dt_s, device)
        label = "torch"
    torch.manual_seed(0)
    arr, meta = fly_all(args, world, label, gates_cfg, wins, device)
    np.savez(run_dir / "arrays.npz", **arr)
    res = analyse(dict(np.load(run_dir / "arrays.npz")), wins, wmeta, steps, gates_cfg)
    rows = gate_rows(res["measured"], gates_cfg["step_gates"])
    verdict = step_verdict(res, gates_cfg["step_gates"])
    meta.update(date=date, commit=git_state(), code_sha=code_sha(), gates_sha256=sha256_file(gates_path)[:12],
                params_sha256=sha256_file(ROOT / meta["physics_params"])[:12],
                windows=str(wpath), windows_meta=wmeta, nvsmi_apps_before=nvsmi_before,
                nvsmi_apps_after=gpu_compute_apps(),
                gpu=torch.cuda.get_device_name() if device.type == "cuda" else "cpu",
                wall_s=round(time.time() - t_start, 1), host="host (conda env_isaaclab), not the container",
                float32_extent_m=extent,
                float32_spacing_at_extent_m=float(np.spacing(np.float32(extent))) if extent else None,
                command="python scripts/physics_step_tests.py " + " ".join(sys.argv[1:]))
    res.update(meta=meta, gates=rows, verdict=verdict)
    (run_dir / "results.json").write_text(json.dumps(_jsonable(res), indent=1))
    print(f"VERDICT {verdict} (results in {run_dir}/results.json; record: --phase record --name {args.name})")
    for r in rows:
        print(f"  {r['gate']}: {r['value']} {r['kind']} {r['limit']}  {r['result']}")
    return 0


# =================================================================================================== record
def next_ledger_number(text: str) -> int:
    return max((int(x) for x in re.findall(r"^\|\s*T(\d+)\s*\|", text, re.M)), default=0) + 1


def _f(x, nd=3) -> str:
    if x is None:
        return "—"
    if isinstance(x, str):
        return x
    if isinstance(x, (int, np.integer)) and not isinstance(x, bool):
        return str(x)
    if not math.isfinite(x):
        return "never (inf)" if x > 0 else str(x)
    return f"{x:.{nd}f}"


def record_phase(args) -> int:
    run_dir = pathlib.Path(args.runs_dir) / args.name
    res = _unjson(json.loads((run_dir / "results.json").read_text()))
    if res["meta"]["world"] == "torch":
        print("refused: a PyTorch-world dry run gets no record or ledger row", file=sys.stderr)
        return 2
    rec = ROOT / "records" / f"{args.name}_record.md"
    if rec.exists():
        print(f"refused: {rec} exists", file=sys.stderr)
        return 2
    import make_s2b_figures as figs

    figs.steps(str(FIG_STEPS), str(run_dir))
    figs.real_replay(str(FIG_REPLAY), str(run_dir))
    ledger = ROOT / "records" / "LEDGER.md"
    text = ledger.read_text()
    t = next_ledger_number(text)
    row = (f"| T{t} | {res['meta']['date']} | training simulator, tier 2 (Isaac Lab: rigid-body Starling, PX4 1.14 "
           f"cascade, SIM-ONLY yaw-rate gains) and tier 1 (Starling layer, exploratory drone model), against real "
           f"flight log log103 (13 Nov, drone_2) | {args.name} | S2b step tests: hover 10 s, "
           f"{len(res['steps']['steps']) - 1} steps through the full layers (physics vs tier 1), "
           f"{res['replay']['windows']} held-out legs of log103 replayed at setpoint level; 30 deg tilt and PyTorch "
           f"world INFO | {res['verdict']} | records/{args.name}_record.md |")
    rec.write_text(record_text(args.name, res, t, run_dir))
    ledger.write_text(text + ("" if text.endswith("\n") else "\n") + row + "\n")
    print(f"wrote {rec.relative_to(ROOT)} and ledger row T{t}")
    return 0


def record_text(name: str, res: dict, t_number: int, run_dir: pathlib.Path) -> str:
    meta, s, rp = res["meta"], res["steps"], res["replay"]
    wm = meta["windows_meta"]
    gates = {r["gate"]: r for r in res["gates"]}
    L = [FIRST_LINE, "", f"# {meta['date']} {name} record", "",
         f"Result: **{res['verdict']}** against `[step_gates]` of `configs/s2b.toml`. Ledger row T{t_number}. Observed "
         "in the training simulator; nothing here is a flight result.", "",
         "## Purpose", "",
         "S2b flies the game on rigid-body Starlings in Isaac Lab, under a copy of PX4 1.14's control cascade with the "
         "drone's own gains, except the SIM-ONLY yaw-rate gains of the owner's ruling (the physics drone). This run asks two questions. First: does the physics drone answer a "
         "stick command like the real drone did? Its speed is compared with the real drone's on six legs of a real "
         "flight (log103, 13 November 2026, drone_2), feeding it the setpoints PX4 logged. Second: does it answer like "
         "tier 1's drone model, the fast PyTorch model the game used until now? The same stick commands go through "
         "the same commander copy and safety filter to both.", "",
         "Reading rule (written before the run, from the plan): if the physics drone passes against the real log and "
         "fails against tier 1, the exploratory tier 1 model is the one that differs from the real drone (in the game "
         "its time to 63 % is about 0.6 s at the start of a push and 0.9 s at the stop). If it fails against the real "
         "log, the physics drone differs from the real drone, and the gates say by how much.", "",
         "## Gates", "", "| Gate | Limit | Measured | Result |", "|---|---|---|---|"]
    for r in res["gates"]:
        L.append(f"| `{r['gate']}` | {r['kind']} {r['limit']} | {_f(r['value'], 4)} | {r['result']} |")
    L += ["", "## Hover (10 s from rest, every game and both drones)", "",
          f"- Largest drift from the start: {_f(s['hover']['drift_max_m'], 4)} m (tier 1: "
          f"{_f(s['hover']['tier1_drift_max_m'], 4)} m).",
          f"- Tilt spread over the last 5 s (largest per-drone standard deviation, 20 Hz samples): "
          f"{_f(s['hover']['tilt_std_max_deg'], 4)} deg. Largest tilt: {_f(s['hover']['tilt_max_tick_deg'], 3)} deg in the "
          f"20 Hz samples, {_f(s['hover']['tilt_max_physics_step_deg'], 3)} deg at any physics step (200 Hz).", "",
          "## Steps: physics drone against tier 1, same stick commands", "",
          "Each step: 0.5 s of hold, the stick command for the push time, then the release command. Speeds are along the "
          "command. t63 = time from the change of command until the speed covers 63 % of the change, the command's "
          "levels for both drones.", "",
          "| Step | gated | speed RMS gap (m/s) | t63 push physics / tier 1 (s) | t63 release physics / tier 1 (s) | "
          "peak speed physics / tier 1 (m/s) | largest tilt (deg) |", "|---|---|---|---|---|---|---|"]
    seen = set()
    for r in s["steps"]:
        if r["name"] in seen:
            continue
        seen.add(r["name"])
        L.append(f"| {r['name']} | {'yes' if r['gated'] else 'INFO'} | {_f(r['rms_vs_tier1_mps'], 4)} | "
                 f"{_f(r['t63_physics_s'][0])} / {_f(r['t63_tier1_s'][0])} | {_f(r['t63_physics_s'][1])} / "
                 f"{_f(r['t63_tier1_s'][1])} | {_f(r['peak_physics_mps'])} / {_f(r['peak_tier1_mps'])} | "
                 f"{_f(r['max_tilt_deg_physics'], 2)} |")
    L += ["", "![Speed per step: physics drone, tier 1 and the command](../docs/figures/s2b_steps.png)", "",
          "*Speed along the stick command for each step: the physics drone in Isaac Lab, tier 1's drone model, and the "
          "command. Both drones get the same commands through the same commander copy and safety filter. Made by "
          "`scripts/make_s2b_figures.py steps` from this run's `arrays.npz`.*", "",
          "## Real flight log: six held-out legs replayed at setpoint level", "",
          f"Log `{wm['log']}`, sha256 `{wm['sha256'][:16]}…`. {wm['legs_found']} legs found; held out (odd legs, as S1): "
          f"{wm['held_out']}; same legs and split as S1's `split.json`: {wm.get('matches_s1_split')}. Tier 1 here is "
          f"the S1 drone model fed the same setpoints; its per-leg RMS reproduces S1's within "
          f"{_f(wm.get('tier1_rms_reproduces_s1_max_abs_diff_mps'), 4)} m/s.", "",
          "| Leg | seconds | speed RMS physics / tier 1 (m/s) | t63 start logged / physics / tier 1 (s) | "
          "t63 stop logged / physics / tier 1 (s) |", "|---|---|---|---|---|"]
    for leg in rp["legs"]:
        ch = {c["change"]: c for c in leg["changes"]}
        cells = []
        for k in ("start", "stop"):
            c = ch.get(k)
            cells.append(f"{_f(c['t63_logged_s'])} / {_f(c['t63_physics_s'])} / {_f(c['t63_tier1_s'])}" if c else "—")
        L.append(f"| {leg['leg']} | {leg['seconds']:.1f} | {_f(leg['rms_physics_mps'], 4)} / "
                 f"{_f(leg['rms_tier1_mps'], 4)} | {cells[0]} | {cells[1]} |")
    db = rp["delay_best"]
    L += ["", f"- Worst leg speed RMS: physics {_f(rp['vel_rms_worst_mps'], 4)} m/s, tier 1 "
              f"{_f(rp['tier1_vel_rms_worst_mps'], 4)} m/s (gate 0.10, physics only). Pooled over all legs, per axis "
              f"(S1's exploratory number): physics {_f(rp['pooled_axis_rms_mps'], 4)}, tier 1 "
              f"{_f(rp['tier1_pooled_axis_rms_mps'], 4)} m/s.",
          f"- Worst t63 error over {rp['t63_changes']} changes: physics {_f(rp['t63_err_worst_s'])} s, tier 1 "
          f"{_f(rp['tier1_t63_err_worst_s'])} s (gate 0.10 s, physics only).",
          f"- INFO (D7, not applied): shifting the physics drone's speed later by {db['delay_s']:+.2f} s would give the "
          f"lowest pooled RMS, {_f(db['pooled_axis_rms_mps'], 4)} m/s (worst leg {_f(db['vel_rms_worst_mps'], 4)}).", "",
          "![Six held-out legs: logged, physics drone, tier 1](../docs/figures/s2b_real_replay.png)", "",
          "*The six held-out legs of the 13 November flight (drone_2): the speed the drone logged, the physics drone "
          "and tier 1's drone model, each fed PX4's logged setpoints, along each leg's direction. Made by "
          "`scripts/make_s2b_figures.py real_replay` from this run's files.*", "",
          "## INFO variants", ""]
    t30 = s.get("tilt30", {})
    if t30:
        L.append(f"- drone_1's 30 deg tilt limit (D11): steps differ from the 45 deg drone by at most "
                 f"{_f(t30['steps_max_abs_diff_mps'], 5)} m/s; largest tilt {_f(t30.get('peak_tilt_deg'), 2)} deg; "
                 f"replay worst-leg RMS {_f(res.get('replay_tilt30', {}).get('vel_rms_worst_mps'), 4)} m/s.")
    tt = s.get("torch", {})
    if tt:
        L.append(f"- PyTorch reference world, same layers: steps differ from Isaac Lab by at most "
                 f"{_f(tt['steps_max_abs_diff_mps'], 5)} m/s (RMS {_f(tt['steps_rms_max_mps'], 5)}); replay by at most "
                 f"{_f(res.get('replay_torch', {}).get('max_abs_diff_vs_physics_mps'), 5)} m/s.")
    tails = [r for r in s["steps"] if "release_tail_tilt_std_deg" in r]
    if tails:
        L.append("- Wobble after a step (the hover gate's question, after an excitation): tilt spread over the last 2 s "
                 "of each release, " + ", ".join(f"{r['name']} {r['release_tail_tilt_std_deg']:.3f}" for r in tails[:5])
                 + " deg.")
    if s.get("duplicate_games_max_diff_mps") is not None:
        L.append(f"- Game 5 repeats x_strike in another game slot: largest speed difference to game 0 "
                 f"{_f(s['duplicate_games_max_diff_mps'], 6)} m/s.")
    if meta.get("float32_extent_m"):
        L.append(f"- Float32 positions: the farthest drone sits about {meta['float32_extent_m']:.0f} m from the world "
                 f"origin, where float32 steps by {meta['float32_spacing_at_extent_m']:.1e} m. (At training scale, "
                 "4,096 games at 40 m spacing, about 2.5 km, the step is about 2.4e-4 m; not measured here.)")
    L += ["", "## What is not modelled", "",
          "- The drone's `THR_MDL_FAC` 0.9 and the hover-thrust estimator (`MPC_USE_HTE` 1): the physics drone has a "
          "fixed hover thrust and a linear motor (plan, known differences for Task 7).",
          "- No transport delay and no estimator: the cascade reads the true state (D7).",
          f"- Yaw-rate gains: {meta['yaw_rate_gains']}. Owner's ruling of 16 November 2026 (T10 FAIL accepted, the "
          "SIM-ONLY yaw gains used for the physics drone); never a drone value.",
          "- The replay feeds PX4's logged setpoint with S1's `derived` acceleration feed-forward (the slope of the 5 Hz "
          "logged speed), sampled at the 0.05 s tick; on the drone PX4 received the commander's own 20 Hz setpoint.",
          "- The game's rules (walls, height band, zone, resets) are not in the loop in the step tests: the layers are "
          "driven directly, one commanded drone and one still drone 10 m away.", "",
          "## Commit", "", f"`{meta['commit']}`, code fingerprint `{meta['code_sha']}`.", "",
          "## Config", "",
          f"- Gates: `configs/s2b.toml` (sha256 `{meta['gates_sha256']}`), `[step_tests]` and `[step_gates]`, copied to "
          f"`runs/{name}/gates.toml` before the run.",
          f"- Game: `{pathlib.Path(meta['game_config']).name}` (sha256 `{meta['game_config_sha256'][:12]}`), committed "
          f"neutral values, local file: {meta['local_file']}; preset {meta['preset']}; safety filter on every pair, "
          f"{meta['filter_iterations']} sweeps, early stop every {meta['filter_check_every']}.",
          f"- Physics drone: `{meta['physics_params']}`, physics step {meta['physics_dt_s']} s, rotor positions "
          f"{meta['rotor_geometry']}, motor lag {'on' if meta['motor_lag'] else 'off'}, tilt limit "
          f"{meta['tilt_max_deg']:g} deg.",
          f"- Tier 1: Starling layer, `{meta['tier1_params']}` (exploratory).",
          f"- Command: `{meta['command']}`.", "",
          "## Model parameter set", "",
          "Rigid-body Starling `params/starling_physics_v0.toml` (drone's gains) with the SIM-ONLY yaw-rate gains of "
          "`params/sim_only_yaw_v0.toml`; tier 1 `params/real_exploratory_v0.toml` (exploratory).", "",
          "## Seeds", "", "None drawn: every start, command and setpoint is fixed (torch seeded 0).", "",
          "## Machine", "",
          f"{meta['gpu']}; Isaac Sim 5.1.0 / Isaac Lab 2.3.2 on the HOST (conda `env_isaaclab`), not the container: the "
          f"container mounts only `svg_training/`, and the flight log is host-only (plan D13). Headless. GPU compute "
          f"processes before launch: `{(meta['nvsmi_apps_before'] or 'none').replace(chr(10), '; ')}`. Wall time {meta['wall_s']} s.", "",
          "## Games at once", "",
          f"{meta['games']} games x {meta['drones_per_game']} drones (slot 0 commanded, slot 1 still 10 m away).", "",
          "## Steps per second", "", "Not measured here (the throughput record measures it).", "",
          "## Files", "",
          f"`runs/{name}/`: `gates.toml`, `windows.npz` + `windows.json` (from `--phase windows` on the host), "
          "`arrays.npz`, `results.json`, `run.log`, `preflight.txt`.", ""]
    return "\n".join(L)


# =================================================================================================== main
def make_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--phase", choices=("windows", "run", "record"), required=True)
    ap.add_argument("--name", required=True, help="run name, e.g. 2026-11-16_s2b_step_tests")
    ap.add_argument("--gates", default="configs/s2b.toml")
    ap.add_argument("--log", default=None, help="windows phase: the flight log (default [step_tests] real_log)")
    ap.add_argument("--runs-dir", default=str(ROOT / "runs"))
    ap.add_argument("--windows", default=None, help="run phase: windows.npz (default runs/<name>/windows.npz)")
    ap.add_argument("--world", choices=("isaac", "torch"), default="isaac",
                    help="run phase: Isaac Lab (run of record) or the PyTorch reference world (dry run)")
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--phase" in argv and argv[argv.index("--phase") + 1:argv.index("--phase") + 2] == ["run"] \
            and "torch" not in argv:
        nvsmi = gpu_compute_apps()
        from _isaac_app import start_headless
        sys.argv = [sys.argv[0], *argv]
        args, _app = start_headless(make_parser())
        code = 1
        try:
            code = run_phase(args, nvsmi)
        except BaseException:
            traceback.print_exc()
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(code)
    ap = make_parser()
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args(argv)
    if args.phase == "windows":
        return windows_phase(args)
    if args.phase == "record":
        return record_phase(args)
    try:
        return run_phase(args, gpu_compute_apps())
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
