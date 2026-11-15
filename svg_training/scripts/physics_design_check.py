#!/usr/bin/env python3
"""S2b Task 3 design check: is the PX4 1.14 cascade with the drone's real gains stable on the physics drone, and
does the 200 Hz physics step (dt 0.005 s) give the same answer as 1 kHz?

Usage (from svg_training/, CPU, no Isaac):
    PYTHONPATH=source python scripts/physics_design_check.py --out runs/<date>_s2b_design_check/

Development check: no ledger row, no gates file; the table goes in the task report. One drone in the PyTorch
reference world (``models/rigid_body.py``, the test oracle), the rotor model (``models/starling_airframe.py``) and
the cascade (``models/px4_cascade.py``). Variants: plant rotor geometry {cad, params} x motor lag {on, off} x
dt {0.005, 0.001} s. Gains are the drone's own (``params/starling_physics_v0.toml``), never tuned.

Measured per variant
  hover   10 s from a small upset (roll 2 deg, pitch -1 deg, rates (0.1, -0.1, 0.05) rad/s) at the setpoint:
          tilt spread = standard deviation of the tilt over the last 5 s (deg), peak-to-peak tilt over the same
          5 s (INFO), drift = largest distance from the setpoint over the last 5 s (m).
  step    setpoint-level +x (east) 0.5 m/s step from hover: the position setpoint moves at 0.5 m/s with the velocity
          feed-forward (0.5, 0, 0), 4 s: t63 of the east speed (s), overshoot (% of 0.5 m/s), peak tilt (deg).
  rate    the rate loop alone (outer loops skipped): roll-rate setpoint +1 rad/s for 0.3 s from hover, then
          -1 rad/s for 0.3 s: t63 (s) and overshoot (%) of the first step.
  options INFO (fix round 2): yaw options A-C, and D with --info-yaw-rate-pid P I D (see yaw_options).
  yaw     INFO (fix round 1, not a gate): hover yaw std and peak-to-peak (last 5 s of the hover above), and a
          +0.5 rad yaw setpoint jump from hover for 10 s: t63, overshoot, peak-to-peak after 5 s, final error. Also
          for the default plant with the yaw torque filter off (upstream v1.14.0 has none; px4_cascade note C).
Decision rules (S2b plan, Task 3, fixed before the run)
  (a) default (cad, lag on, 0.005) hover tilt spread > 1.0 deg -> BLOCKED (D5).
  (b) default at 0.005 against default at 0.001: RMS of |v_0.005(t) - v_0.001(t)| over the +x step > 0.02 m/s
      -> use [physics] fallback_physics_dt_s (0.0025) and record it.
Outputs in --out: table.md, results.json. Exit 0 = rules (a) and (b) both clear; 3 = rule (a) fired (BLOCKED);
4 = rule (b) fired (fallback dt); 2 = bad arguments.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys
import tomllib
from pathlib import Path
from typing import Callable

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.models.frames import (quat_wxyz_to_rotmat, rot_enu_flu_to_ned_frd, tilt_rad,  # noqa: E402
                                        vec_enu_to_ned, yaw_enu_to_ned)
from svg_training.models.physics_params import PhysicsParams, load_physics_params  # noqa: E402
from svg_training.models.px4_cascade import Px4Cascade  # noqa: E402
from svg_training.models.rigid_body import TorchRigidBodyWorld  # noqa: E402
from svg_training.models.starling_airframe import RotorModel, body_wrench_flu  # noqa: E402

S2B = ROOT / "configs" / "s2b.toml"
TILT_SPREAD_MAX_DEG = 1.0          # rule (a): [step_gates] hover_tilt_std_max_deg, D5
STEP_RMS_MAX_MPS = 0.02            # rule (b)
HOVER_S, STEP_S, STEP_MPS = 10.0, 4.0, 0.5
YAW_STEP_RAD, YAW_STEP_S = 0.5, 10.0   # INFO (fix round 1): yaw step size and length

# setpoint(t) -> (p_sp ENU [N, M, 3], v_ff ENU, a_ff ENU, yaw ENU [N, M], yaw rate ENU [N, M])
SetpointFn = Callable[[float], tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]]


def load_params(geometry: str = "cad", motor_lag: bool = True, dt_s: float = 0.005) -> PhysicsParams:
    """The drone's parameter file with the configs/s2b.toml [physics] settings, then the variant's overrides."""
    physics = tomllib.loads(S2B.read_text())["physics"]
    p = load_physics_params(physics["params"], physics)
    return dataclasses.replace(p, rotor_geometry=geometry, motor_lag=motor_lag, physics_dt_s=dt_s)


def fly(p: PhysicsParams, duration_s: float, setpoint: SetpointFn, *, n: int = 1, m: int = 1,
        pos0: torch.Tensor | None = None, quat0: torch.Tensor | None = None, ang_vel0: torch.Tensor | None = None,
        rate_sp: Callable[[float], torch.Tensor] | None = None, tilt_max_deg: float | None = None,
        dtype: torch.dtype = torch.float32, yaw_cutoff_hz: float | None = None) -> dict[str, torch.Tensor]:
    """Closed loop on the CPU: cascade -> rotor model -> body wrench -> torch world, one physics step at a time.

    Setpoints are ENU (the game's frame) and cross into NED here, as Task 4's physics drone will do. With
    ``rate_sp`` (t -> FRD rate setpoint [N, M, 3]) the outer loops are skipped and the hover collective is held.
    Returns time series [T, N, M, ...]: t_s [T], pos_m, vel_mps (ENU), quat_wxyz, ang_vel_b (FLU), tilt_deg,
    pitch_frd_deg, yaw_enu_deg, u, rates_sp (FRD), collective.
    """
    dt = p.physics_dt_s
    steps = int(round(duration_s / dt))
    world = TorchRigidBodyWorld(n, m, p.airframe, dt, "cpu", dtype=dtype)
    rotors = RotorModel(n, m, p.airframe, p.motor_lag, dt, "cpu")
    cascade = Px4Cascade(n, m, p.gains, dt, "cpu", tilt_max_deg=tilt_max_deg, dtype=dtype,
                         yaw_torque_cutoff_hz=yaw_cutoff_hz)
    everyone = torch.ones(n, m, dtype=torch.bool)
    q0 = quat0 if quat0 is not None else torch.tensor([1.0, 0.0, 0.0, 0.0], dtype=dtype).expand(n, m, 4)
    p0 = pos0 if pos0 is not None else torch.zeros(n, m, 3, dtype=dtype)
    w0 = ang_vel0 if ang_vel0 is not None else torch.zeros(n, m, 3, dtype=dtype)
    world.write_state(everyone, p0.to(dtype), q0.to(dtype), torch.zeros(n, m, 3, dtype=dtype), w0.to(dtype))
    hover_c = torch.full((n, m), p.gains.mpc_thr_hover, dtype=dtype)
    log: dict[str, list[torch.Tensor]] = {k: [] for k in ("pos_m", "vel_mps", "quat_wxyz", "ang_vel_b", "u",
                                                            "rates_sp", "collective")}
    for k in range(steps):
        t = k * dt
        pos, quat, vel, ang = world.state()
        r_ned_frd = rot_enu_flu_to_ned_frd(quat_wxyz_to_rotmat(quat))
        omega_frd = torch.stack((ang[..., 0], -ang[..., 1], -ang[..., 2]), dim=-1)
        if rate_sp is None:
            p_sp, v_ff, a_ff, yaw, yaw_rate = setpoint(t)
            u = cascade.step(vec_enu_to_ned(p_sp.to(dtype)), vec_enu_to_ned(v_ff.to(dtype)),
                             vec_enu_to_ned(a_ff.to(dtype)), yaw_enu_to_ned(yaw.to(dtype)), -yaw_rate.to(dtype),
                             vec_enu_to_ned(pos), vec_enu_to_ned(vel), r_ned_frd, omega_frd)
        else:
            u = cascade.rate_step(rate_sp(t).to(dtype), omega_frd, hover_c)
        thrust = rotors.step(u.float()).to(dtype)
        force, torque = body_wrench_flu(thrust, p.airframe, p.rotor_geometry)
        world.apply_wrench_b(force, torque)
        world.step()
        pos, quat, vel, ang = world.state()
        for key, val in (("pos_m", pos), ("vel_mps", vel), ("quat_wxyz", quat), ("ang_vel_b", ang), ("u", u),
                         ("rates_sp", cascade.rates_sp), ("collective", cascade.collective)):
            log[key].append(val.clone())
    out = {k: torch.stack(v) for k, v in log.items()}
    out["t_s"] = (torch.arange(1, steps + 1, dtype=torch.float64) * dt)
    q = out["quat_wxyz"]
    out["tilt_deg"] = torch.rad2deg(tilt_rad(q))
    r = rot_enu_flu_to_ned_frd(quat_wxyz_to_rotmat(q))
    out["pitch_frd_deg"] = torch.rad2deg(torch.asin((-r[..., 2, 0]).clamp(-1.0, 1.0)))
    rq = quat_wxyz_to_rotmat(q)
    out["yaw_enu_deg"] = torch.rad2deg(torch.atan2(rq[..., 1, 0], rq[..., 0, 0]))
    return out


def hold(pos: torch.Tensor) -> SetpointFn:
    """Setpoint = a fixed ENU position [N, M, 3], nose east, no feed-forward."""
    z = torch.zeros_like(pos)
    zy = torch.zeros(pos.shape[:-1], dtype=pos.dtype)
    return lambda t: (pos, z, z, zy, zy)


def ramp_x(pos0: torch.Tensor, speed_mps: float, t0_s: float = 0.0) -> SetpointFn:
    """Setpoint moving +x (east) at ``speed_mps`` from ``t0_s`` with the matching velocity feed-forward."""
    zy = torch.zeros(pos0.shape[:-1], dtype=pos0.dtype)

    def f(t: float):
        run = max(t - t0_s, 0.0)
        p = pos0.clone()
        p[..., 0] += speed_mps * run
        v = torch.zeros_like(pos0)
        v[..., 0] = speed_mps if t >= t0_s else 0.0
        return p, v, torch.zeros_like(pos0), zy, zy
    return f


def upset_quat(roll_deg: float, pitch_deg: float) -> torch.Tensor:
    """WXYZ [1, 1, 4] for a small roll then pitch about the FLU body axes (ENU world, nose east)."""
    r, p = math.radians(roll_deg) / 2, math.radians(pitch_deg) / 2
    qr = torch.tensor([math.cos(r), math.sin(r), 0.0, 0.0])
    qp = torch.tensor([math.cos(p), 0.0, math.sin(p), 0.0])
    w1, x1, y1, z1 = qr
    w2, x2, y2, z2 = qp
    q = torch.stack((w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2))
    return q.view(1, 1, 4)


def t63(t: torch.Tensor, y: torch.Tensor, target: float, t0: float = 0.0) -> float:
    """First time after ``t0`` (relative to it) at which ``y`` [T] reaches 63.2 % of ``target``; nan if never."""
    hit = ((y >= 0.632 * target) & (t >= t0)).nonzero()
    return float(t[hit[0, 0]] - t0) if len(hit) else float("nan")


def hover_metrics(p: PhysicsParams, yaw_cutoff_hz: float | None = None) -> dict:
    pos0 = torch.tensor([[[0.0, 0.0, 1.0]]])
    out = fly(p, HOVER_S, hold(pos0), pos0=pos0, quat0=upset_quat(2.0, -1.0),
              ang_vel0=torch.tensor([[[0.1, -0.1, 0.05]]]), yaw_cutoff_hz=yaw_cutoff_hz)
    last = out["t_s"] > HOVER_S - 5.0
    tilt = out["tilt_deg"][last, 0, 0]
    dist = (out["pos_m"][last, 0, 0] - pos0[0, 0]).norm(dim=-1)
    finite = bool(torch.isfinite(out["pos_m"]).all())
    yaw = out["yaw_enu_deg"][last, 0, 0]
    return {"tilt_spread_deg": float(tilt.std()), "tilt_p2p_deg": float(tilt.max() - tilt.min()),
            "tilt_max_last5_deg": float(tilt.max()), "drift_m": float(dist.max()), "finite": finite,
            "yaw_spread_deg": float(yaw.std()), "yaw_p2p_deg": float(yaw.max() - yaw.min())}


def yaw_step_run(p: PhysicsParams, duration_s: float = YAW_STEP_S,
                 yaw_cutoff_hz: float | None = None) -> dict[str, torch.Tensor]:
    """Hover at rest, then the yaw setpoint jumps to +YAW_STEP_RAD (ENU, nose turning left) at t = 0, no feed-forward."""
    pos0 = torch.tensor([[[0.0, 0.0, 1.0]]])
    z = torch.zeros(1, 1, 3)
    yaw = torch.full((1, 1), YAW_STEP_RAD)
    zy = torch.zeros(1, 1)
    return fly(p, duration_s, lambda t: (pos0, z, z, yaw, zy), pos0=pos0, yaw_cutoff_hz=yaw_cutoff_hz)


def yaw_step_metrics(out: dict[str, torch.Tensor]) -> dict:
    """INFO: t63 of the yaw (s), peak-to-peak after 5 s (deg), final error (deg), largest overshoot (deg)."""
    yaw = out["yaw_enu_deg"][:, 0, 0]
    target = math.degrees(YAW_STEP_RAD)
    late = out["t_s"] > 5.0
    return {"t63_s": t63(out["t_s"], yaw, target), "p2p_after_5s_deg": float(yaw[late].max() - yaw[late].min()),
            "final_err_deg": float(yaw[-1] - target), "overshoot_deg": float(yaw.max() - target)}


def step_run(p: PhysicsParams, yaw_cutoff_hz: float | None = None) -> dict[str, torch.Tensor]:
    pos0 = torch.tensor([[[0.0, 0.0, 1.0]]])
    return fly(p, STEP_S, ramp_x(pos0, STEP_MPS), pos0=pos0, yaw_cutoff_hz=yaw_cutoff_hz)


def yaw_options(yaw_rate_pid: tuple[float, float, float] | None) -> tuple[list[dict], list[str]]:
    """INFO (fix round 2): the yaw options put to the owner, all on the default plant (CAD arms) at dt 0.005.

    A drone gains, yaw filter, motor lag on (the code default); B the same with the yaw filter off; C motor lag off;
    D (only with ``yaw_rate_pid``) yaw-rate P / I / D from the command line, filter and lag on. D's numbers are
    never written in this file: the AirStack simulator's yaw-rate gains are SIM-ONLY (iron rule 9), so they are
    passed on the command line for a one-off INFO comparison and labelled so in the output.
    Returns result rows and table lines; the last column is the RMS of the +x step's velocity difference to A.
    """
    base = load_params("cad", True, 0.005)
    cases = [("A drone gains, 15 Hz yaw filter, lag on (default)", base, None),
             ("B drone gains, yaw filter off, lag on", base, 0.0),
             ("C drone gains, 15 Hz yaw filter, lag off", load_params("cad", False, 0.005), None)]
    if yaw_rate_pid is not None:
        yp, yi, yd = yaw_rate_pid
        sim = dataclasses.replace(base, gains=dataclasses.replace(base.gains, mc_yawrate_p=yp, mc_yawrate_i=yi,
                                                                  mc_yawrate_d=yd))
        cases.append((f"D SIM-ONLY yaw-rate P/I/D {yp:g}/{yi:g}/{yd:g} (command line), 15 Hz filter, lag on", sim,
                      None))
    out, ref = [], None
    for name, p, cut in cases:
        h = hover_metrics(p, cut)
        y = yaw_step_metrics(yaw_step_run(p, yaw_cutoff_hz=cut))
        run = step_run(p, cut)
        ref = run if ref is None else ref
        out.append({"case": name, "hover": h, "yaw_step": y, "step": step_metrics(run),
                    "step_rms_vs_A_mps": speed_rms_diff(run, ref)})
        print(f"option {name}: done", flush=True)
    lines = ["", "INFO, yaw options for the owner (default plant, dt 0.005; not gates):", "",
             "| case | hover yaw std (deg) | hover tilt spread (deg) | yaw step t63 (s) | yaw p2p after 5 s (deg) | "
             "yaw final error (deg) | +x t63 (s) | +x overshoot (%) | +x velocity RMS vs A (m/s) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in out:
        h, y, s = r["hover"], r["yaw_step"], r["step"]
        lines.append(f"| {r['case']} | {h['yaw_spread_deg']:.3f} | {h['tilt_spread_deg']:.4f} | {y['t63_s']:.3f} | "
                     f"{y['p2p_after_5s_deg']:.2f} | {y['final_err_deg']:.2f} | {s['t63_s']:.3f} | "
                     f"{s['overshoot_pct']:.1f} | {r['step_rms_vs_A_mps']:.5f} |")
    return out, lines


def step_metrics(out: dict[str, torch.Tensor]) -> dict:
    vx = out["vel_mps"][:, 0, 0, 0]
    return {"t63_s": t63(out["t_s"], vx, STEP_MPS), "overshoot_pct": float((vx.max() - STEP_MPS) / STEP_MPS * 100),
            "peak_tilt_deg": float(out["tilt_deg"][:, 0, 0].max()),
            "final_x_m": float(out["pos_m"][-1, 0, 0, 0]),
            "max_abs_y_m": float(out["pos_m"][:, 0, 0, 1].abs().max()),
            "max_abs_dz_m": float((out["pos_m"][:, 0, 0, 2] - 1.0).abs().max())}


def rate_metrics(p: PhysicsParams) -> dict:
    def sp(t: float) -> torch.Tensor:
        roll = 1.0 if t < 0.3 else -1.0
        return torch.tensor([[[roll, 0.0, 0.0]]])
    out = fly(p, 0.6, hold(torch.zeros(1, 1, 3)), rate_sp=sp)
    roll_frd = out["ang_vel_b"][:, 0, 0, 0]                     # FLU x = FRD x
    first = out["t_s"] < 0.3
    return {"t63_s": t63(out["t_s"], roll_frd, 1.0),
            "overshoot_pct": float((roll_frd[first].max() - 1.0) * 100)}


def speed_rms_diff(a: dict[str, torch.Tensor], b: dict[str, torch.Tensor]) -> float:
    """RMS of |v_a(t) - v_b(t)| (ENU, 3-D) on a's time grid; b (the finer run) is sampled at the same times."""
    stride = int(round(float(a["t_s"][0] / b["t_s"][0])))
    vb = b["vel_mps"][stride - 1::stride][: len(a["t_s"])]
    return float((a["vel_mps"] - vb).norm(dim=-1).pow(2).mean().sqrt())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True, help="output folder, e.g. runs/2026-11-16_s2b_design_check/")
    ap.add_argument("--info-yaw-rate-pid", type=float, nargs=3, metavar=("P", "I", "D"), default=None,
                    help="INFO only: also fly the default plant with these yaw-rate gains (labelled SIM-ONLY)")
    args = ap.parse_args(argv)
    out_dir = Path(args.out)
    out_dir = out_dir if out_dir.is_absolute() else ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)

    rows, steps = [], {}
    for geometry in ("cad", "params"):
        for lag in (True, False):
            for dt in (0.005, 0.001):
                p = load_params(geometry, lag, dt)
                h = hover_metrics(p)
                run = step_run(p)
                steps[(geometry, lag, dt)] = run
                s = step_metrics(run)
                r = rate_metrics(p)
                y = yaw_step_metrics(yaw_step_run(p))
                rows.append({"geometry": geometry, "motor_lag": lag, "dt_s": dt, "hover": h, "step": s, "rate": r,
                             "yaw_step": y})
                print(f"{geometry:6s} lag={'on ' if lag else 'off'} dt={dt}: tilt spread {h['tilt_spread_deg']:.4f} "
                      f"deg, drift {h['drift_m']:.4f} m, step t63 {s['t63_s']:.3f} s, overshoot "
                      f"{s['overshoot_pct']:.1f} %, peak tilt {s['peak_tilt_deg']:.2f} deg, rate t63 "
                      f"{r['t63_s'] * 1000:.0f} ms, rate overshoot {r['overshoot_pct']:.1f} %; hover yaw std "
                      f"{h['yaw_spread_deg']:.3f} deg, yaw step p2p after 5 s {y['p2p_after_5s_deg']:.2f} deg",
                      flush=True)
    # INFO: the same yaw checks with the yaw torque filter off (upstream v1.14.0 has none; note C of px4_cascade)
    no_filter = []
    for lag in (True, False):
        p = load_params("cad", lag, 0.005)
        no_filter.append({"geometry": "cad", "motor_lag": lag, "dt_s": 0.005, "hover": hover_metrics(p, 0.0),
                          "yaw_step": yaw_step_metrics(yaw_step_run(p, yaw_cutoff_hz=0.0))})

    default = next(r for r in rows if r["geometry"] == "cad" and r["motor_lag"] and r["dt_s"] == 0.005)
    rule_a = default["hover"]["tilt_spread_deg"] > TILT_SPREAD_MAX_DEG or not default["hover"]["finite"]
    rms = {f"{g}_{'lag' if lag else 'nolag'}": speed_rms_diff(steps[(g, lag, 0.005)], steps[(g, lag, 0.001)])
           for g in ("cad", "params") for lag in (True, False)}
    rule_b = rms["cad_lag"] > STEP_RMS_MAX_MPS

    lines = ["| geometry | motor lag | dt (s) | hover tilt spread (deg) | hover tilt p2p (deg) | hover drift (m) | "
             "+x step t63 (s) | overshoot (%) | peak tilt (deg) | roll-rate t63 (ms) | roll-rate overshoot (%) |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        h, s, rr = r["hover"], r["step"], r["rate"]
        lines.append(f"| {r['geometry']} | {'on' if r['motor_lag'] else 'off'} | {r['dt_s']} | "
                     f"{h['tilt_spread_deg']:.4f} | {h['tilt_p2p_deg']:.4f} | {h['drift_m']:.4f} | {s['t63_s']:.3f} | "
                     f"{s['overshoot_pct']:.1f} | {s['peak_tilt_deg']:.2f} | {rr['t63_s'] * 1000:.0f} | "
                     f"{rr['overshoot_pct']:.1f} |")
    yaw_cut = Px4Cascade(1, 1, load_params().gains, 0.005, "cpu").yaw_cutoff_hz
    lines += ["", f"INFO, yaw (not a gate). Yaw torque filter {yaw_cut:g} Hz unless marked off. Hover yaw = last 5 s "
              f"of the hover above; yaw step = +{YAW_STEP_RAD} rad setpoint jump from hover, {YAW_STEP_S:g} s.",
              "", "| geometry | motor lag | dt (s) | yaw filter | hover yaw std (deg) | hover yaw p2p (deg) | "
              "yaw step t63 (s) | yaw overshoot (deg) | yaw p2p after 5 s (deg) | yaw final error (deg) |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for r, cut in [(r, f"{yaw_cut:g} Hz") for r in rows] + [(r, "off") for r in no_filter]:
        h, y = r["hover"], r["yaw_step"]
        lines.append(f"| {r['geometry']} | {'on' if r['motor_lag'] else 'off'} | {r['dt_s']} | {cut} | "
                     f"{h['yaw_spread_deg']:.3f} | {h['yaw_p2p_deg']:.3f} | {y['t63_s']:.3f} | "
                     f"{y['overshoot_deg']:.2f} | {y['p2p_after_5s_deg']:.2f} | {y['final_err_deg']:.2f} |")
    lines += ["", "| +x step, dt 0.005 vs 0.001: RMS of the velocity difference (m/s) | value |", "|---|---|"]
    lines += [f"| {k} | {v:.5f} |" for k, v in rms.items()]
    lines += ["", f"Rule (a) default hover tilt spread {default['hover']['tilt_spread_deg']:.4f} deg "
              f"(limit {TILT_SPREAD_MAX_DEG}): {'FIRED -> BLOCKED' if rule_a else 'clear'}.",
              f"Rule (b) default dt RMS {rms['cad_lag']:.5f} m/s (limit {STEP_RMS_MAX_MPS}): "
              f"{'FIRED -> fallback_physics_dt_s' if rule_b else 'clear'}."]
    options, option_lines = yaw_options(tuple(args.info_yaw_rate_pid) if args.info_yaw_rate_pid else None)
    lines += option_lines
    (out_dir / "table.md").write_text("\n".join(lines) + "\n")
    (out_dir / "results.json").write_text(json.dumps(
        {"rows": rows, "yaw_options": options, "yaw_filter_off_rows": no_filter, "yaw_cutoff_hz": yaw_cut, "dt_rms_mps": rms, "rule_a_fired": rule_a, "rule_b_fired": rule_b,
         "params_source": load_params().source}, indent=2) + "\n")
    print("\n".join(lines))
    return 3 if rule_a else (4 if rule_b else 0)


if __name__ == "__main__":
    sys.exit(main())
