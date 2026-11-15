#!/usr/bin/env python3
"""S2b agreement run: the Isaac Lab world against the PyTorch reference world, same forces, same cascade.

    scripts/isaac_preflight.sh
    docker/run.sh 'svg-isaaclab -p scripts/physics_agreement.py --headless --gates configs/s2b.toml --name <date>_s2b_agreement'
    docker/run.sh 'svg-isaaclab -p scripts/physics_agreement.py --headless --smoke --out /tmp/smoke.json'   # tests
    python scripts/physics_agreement.py --figure-from runs/<name> [--figure-out docs/figures/s2b_agreement.png]  # no Isaac

One process holds both worlds side by side, games x drones from ``[agreement]`` of the gates file (64 x 3), on the GPU.
Both worlds get the same start poses (seeded) and the same body wrench every physics step; any difference comes
from the integrator (PhysX's against ``models/rigid_body.TorchRigidBodyWorld``). Phases:

  readback     what PhysX holds: mass, inertia (diagonal and off-diagonal), centre of mass, rigid-body settings
               (gyroscopic forces, damping, sleeping, max angular velocity, collider) read back from the stage;
  hover        2 s of the hover wrench from rest (drift, body rates);
  body_frame   level, nose turned 90 deg (north), a +x body force: the world acceleration must point +y;
  write_check  a random state written to half the drones in both worlds, one free step, the two compared;
  open_loop    GATE (2): 1 s of a constant wrench (thrust 1.1 x weight, torque (2e-4, -1e-4, 5e-5) N m) from hover,
               random headings; position and attitude gaps over every step; roll, pitch, yaw of game 0 drone 0
               logged every step in both worlds;
  roll_check   INFO: the S2b spike's 0.2 s, 1 % roll differential (the spike saw an unexplained 0.007 deg gap);
  tumble       INFO: 2 s of free tumbling from fast body rates, PhysX against both torch gyroscopic options;
  closed_loop  GATE (3), full run only: the ``[step_tests]`` steps through ``PhysicsDrone`` (PX4 cascade, rotor
               model, motor lag) on both worlds. Setpoints without the commander: p_sp ramps at the step speed with
               v_ff = the step speed; ``then_mps`` (if given) is flown during the release time, otherwise the
               setpoint stops. 0.5 s of hold before each step.

Full run: copies the gates file to ``runs/<name>/gates.toml`` first, writes ``results.json`` and ``closed_loop.npz``
there, the figure ``docs/figures/s2b_agreement.png``, the record ``records/<name>_record.md`` and the next free T row
of ``records/LEDGER.md``. Smoke (``--smoke``): 4 games x 3 drones, no closed loop, writes only ``--out``.
Exit 0 when the run finished (PASS or FAIL is in the files), 1 on a crash, 2 on bad arguments.
"""
from __future__ import annotations

import argparse
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

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

SMOKE_GAMES = 4
HOVER_S = 2.0
BODY_FRAME_S = 0.2
BODY_FRAME_ACC_MPS2 = 1.0                  # +x body force = mass x 1 m/s^2
OPEN_LOOP_S = 1.0
OPEN_LOOP_THRUST_X_WEIGHT = 1.1
OPEN_LOOP_TORQUE_NM = (2.0e-4, -1.0e-4, 5.0e-5)
ROLL_CHECK_S = 0.2
ROLL_CHECK_FRAC = 0.01
TUMBLE_S = 2.0
TUMBLE_RATES_RAD_S = ((2.0, -1.0, 1.5), (math.radians(130.0), -math.radians(130.0), math.radians(150.0)))
LEAD_S = 0.5                               # hold before each closed-loop step
FIRST_LINE = ("Simulator: observed in the training simulator (tier 2, Isaac Lab) against its PyTorch reference "
              "world; no real drone")
FIGURE = ROOT / "docs" / "figures" / "s2b_agreement.png"


# --------------------------------------------------------------------------------------------- helpers (no Isaac)
def gpu_used_mib() -> int | None:
    """Device-wide used GPU memory from nvidia-smi, or None."""
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=20).stdout
        return int(out.split()[0])
    except Exception:
        return None


def commit() -> str:
    c = os.environ.get("SVG_COMMIT")
    if c:
        return c
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, timeout=20).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def sha256_12(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def next_ledger_number(ledger_text: str) -> int:
    """Next free T number of the training ledger."""
    nums = [int(x) for x in re.findall(r"^\|\s*T(\d+)\s*\|", ledger_text, re.M)]
    return max(nums, default=0) + 1


def gate_rows(res: dict, gates: dict) -> list[dict]:
    """The [agreement_gates] against the measured values; every gate is "value <= limit"."""
    cl = res.get("closed_loop", {}).get("steps", [])
    vals = {
        "mass_inertia_rel_err_max": max(res["readback"]["mass_rel_err"], res["readback"]["inertia_rel_err"]),
        "open_loop_pos_max_m": res["open_loop"]["pos_max_m"],
        "open_loop_angle_max_deg": res["open_loop"]["angle_max_deg"],
        "closed_loop_vel_rms_max_mps": max((s["vel_rms_max_mps"] for s in cl), default=float("nan")),
        "closed_loop_pos_max_m": max((s["pos_end_max_m"] for s in cl), default=float("nan")),
        "nan_max": res["nan"],
    }
    rows = []
    for key, limit in gates.items():
        v = vals[key]
        rows.append({"gate": key, "limit": limit, "value": v, "pass": bool(v <= limit)})
    return rows


# --------------------------------------------------------------------------------------------- figure (no Isaac)
def make_figure(run_dir: str | pathlib.Path, out: str | pathlib.Path = FIGURE) -> None:
    """Per closed-loop step: speed along the command, Isaac Lab world against the torch world (top), and the largest
    speed gap between the two worlds over all drones (bottom). Read from run_dir/closed_loop.npz and results.json."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from make_s0_figures import INK2, SERIES, style

    run_dir = pathlib.Path(run_dir)
    res = json.loads((run_dir / "results.json").read_text())
    data = np.load(run_dir / "closed_loop.npz")
    steps = res["closed_loop"]["steps"]
    fig, axes = plt.subplots(2, len(steps), figsize=(3.4 * len(steps), 6.4), dpi=150, sharex="col",
                             gridspec_kw={"height_ratios": [3, 2]}, squeeze=False)
    print("step, peak speed isaac / torch (m/s), vel RMS max (m/s), end pos gap max (m)")
    for j, s in enumerate(steps):
        name = s["name"]
        t = data[f"{name}_t"]
        top, bot = axes[0, j], axes[1, j]
        top.plot(t, data[f"{name}_cmd"], color=INK2, linewidth=1.2, linestyle=":", label="setpoint speed")
        top.plot(t, data[f"{name}_v_isaac"], color=SERIES[0], linewidth=2.0, label="Isaac Lab world")
        top.plot(t, data[f"{name}_v_torch"], color=SERIES[1], linewidth=1.2, linestyle="--",
                 label="PyTorch reference world")
        style(top, name, "", "speed along the command (m/s)" if j == 0 else "")
        bot.plot(t, np.maximum(data[f"{name}_gap"], 1e-9), color=SERIES[2], linewidth=1.5)
        bot.set_yscale("log")
        style(bot, f"RMS max {s['vel_rms_max_mps']:.1e} m/s", "time (s)",
              "largest speed gap, all drones (m/s)" if j == 0 else "")
        bot.title.set_fontsize(9)
        print(f"{name}, {float(np.max(np.abs(data[name + '_v_isaac']))):.4f} / "
              f"{float(np.max(np.abs(data[name + '_v_torch']))):.4f}, {s['vel_rms_max_mps']:.3e}, "
              f"{s['pos_end_max_m']:.3e}")
    axes[0, 0].legend(loc="lower right", fontsize=8, frameon=False)
    games, drones = res["meta"]["games"], res["meta"]["drones_per_game"]
    fig.suptitle(f"Isaac Lab world against the PyTorch reference world, same PX4 cascade, {games} games x {drones} "
                 f"drones (mean over drones, top)", x=0.01, ha="left", color=INK2, fontsize=11)
    fig.tight_layout()
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    print("figure:", out)


# --------------------------------------------------------------------------------------------- the run (Isaac)
def run(args, gates_cfg: dict) -> dict:
    import torch

    from svg_training.compat import isaaclab_232 as isaac
    from svg_training.models.frames import quat_from_yaw_enu, quat_mul_wxyz, quat_wxyz_to_rotmat
    from svg_training.models.physics_drone import PhysicsDrone
    from svg_training.models.physics_params import G_MPS2, load_physics_params
    from svg_training.models.rigid_body import TorchRigidBodyWorld
    from svg_training.models.starling_airframe import body_wrench_flu

    t_start = time.time()
    agree, gates, phys = gates_cfg["agreement"], gates_cfg["agreement_gates"], gates_cfg["physics"]
    p = load_physics_params(ROOT / phys["params"], overrides=phys)
    a, dt = p.airframe, p.physics_dt_s
    n = SMOKE_GAMES if args.smoke else int(agree["games"])
    m = int(agree["drones_per_game"])
    dev = torch.device(args.device)
    torch.manual_seed(int(agree["seed"]))
    gen = torch.Generator().manual_seed(int(agree["seed"]))
    allm = torch.ones(n, m, dtype=torch.bool, device=dev)
    weight_n = a.mass_kg * G_MPS2
    res: dict = {"meta": {"games": n, "drones_per_game": m, "physics_dt_s": dt, "seed": int(agree["seed"]),
                          "smoke": bool(args.smoke), "device": str(dev), "motor_lag": p.motor_lag,
                          "rotor_geometry": p.rotor_geometry, "torch_gyro": "momentum_preserving"}}
    nan_total = 0

    sim = isaac.make_physics_sim(dt, args.device)
    t0 = time.time()
    iw = isaac.IsaacWorld(sim, n, m, a, dt)
    isaac.physics_play(sim, iw, rel_err_max=None)
    tw = TorchRigidBodyWorld(n, m, a, dt, dev)
    res["meta"]["scene_build_s"] = round(time.time() - t0, 2)
    res["meta"]["worlds"] = [iw.label, tw.label]

    # ---------------------------------------------------------------------------------------- readback
    mass, inertia = iw.mass_inertia_readback()
    want_i = torch.tensor(a.inertia_kgm2, dtype=torch.float32)
    res["readback"] = {
        "mass_kg_want": a.mass_kg, "inertia_kgm2_want": list(a.inertia_kgm2),
        "mass_kg_got": [float(mass.min()), float(mass.max())],
        "inertia_kgm2_got_min": inertia.reshape(-1, 3).min(0).values.tolist(),
        "inertia_kgm2_got_max": inertia.reshape(-1, 3).max(0).values.tolist(),
        "mass_rel_err": float(((mass - a.mass_kg).abs() / a.mass_kg).max()),
        "inertia_rel_err": float(((inertia - want_i).abs() / want_i).max()),
        "inertia_offdiag_max_kgm2": iw.inertia_offdiag_max(),
        "com_offset_max_m": iw.com_offset_max_m(),
        "body_settings": iw.body_settings()}
    print("readback", json.dumps(res["readback"]), flush=True)

    # ---------------------------------------------------------------------------------------- helpers
    def both_write(mask, pos, quat, lin, ang):
        for w in (iw, tw):
            w.write_state(mask, pos, quat, lin, ang)

    def both_reset(pos, quat):
        for w in (iw, tw):
            w.reset(allm, pos, quat)

    def both_step(force, torque):
        for w in (iw, tw):
            w.apply_wrench_b(force, torque)
            w.step()

    def finite_bad(w) -> "torch.Tensor":
        return sum((~torch.isfinite(x)).sum() for x in w.state())

    def rpy_deg(q):
        w_, x, y, z = q.unbind(-1)
        roll = torch.atan2(2 * (w_ * x + y * z), 1 - 2 * (x * x + y * y))
        pitch = torch.asin((2 * (w_ * y - z * x)).clamp(-1.0, 1.0))
        yaw = torch.atan2(2 * (w_ * z + x * y), 1 - 2 * (y * y + z * z))
        return torch.rad2deg(torch.stack((roll, pitch, yaw), dim=-1))

    def angle_gap_deg(q1, q2):
        """Rotation angle between two attitudes (deg), in float64: 2 atan2(|v|, |w|) of q1^-1 q2."""
        q1, q2 = q1.double(), q2.double()
        c = torch.cat((q1[..., :1], -q1[..., 1:]), dim=-1)
        r = quat_mul_wxyz(c, q2)
        return torch.rad2deg(2 * torch.atan2(r[..., 1:].norm(dim=-1), r[..., 0].abs()))

    def start_poses(yaw_mode: str):
        pos = torch.empty(n, m, 3)
        pos[..., 0].uniform_(-3.0, 3.0, generator=gen)
        pos[..., 1].uniform_(-3.0, 3.0, generator=gen)
        pos[..., 2].uniform_(1.5, 3.0, generator=gen)
        yaw = torch.full((n, m), math.pi / 2) if yaw_mode == "north" else (
            torch.zeros(n, m) if yaw_mode == "east" else (torch.rand(n, m, generator=gen) * 2 - 1) * math.pi)
        return pos.to(dev), yaw.to(dev), quat_from_yaw_enu(yaw.to(dev))

    zeros3 = torch.zeros(n, m, 3, device=dev)

    def body_force(fx=0.0, fz=0.0):
        f = torch.zeros(n, m, 3, device=dev)
        f[..., 0], f[..., 2] = fx, fz
        return f

    # ---------------------------------------------------------------------------------------- first step
    # the very first physics step after play: a roll torque from rest, one step; body rates must match the torch world
    pos0, _, q0 = start_poses("east")
    both_reset(pos0, q0)
    tq = torch.zeros(n, m, 3, device=dev)
    tq[..., 0] = -0.007
    both_step(body_force(fz=weight_n), tq)
    ri, rt = iw.state()[3][..., 0], tw.state()[3][..., 0]
    res["first_step"] = {"roll_rate_isaac_rad_s": float(ri.mean()), "roll_rate_torch_rad_s": float(rt.mean()),
                         "ratio_max_err": float((ri / rt - 1).abs().max())}
    res["first_step_ratio_err"] = res["first_step"]["ratio_max_err"]

    # ---------------------------------------------------------------------------------------- hover
    pos0, _, q0 = start_poses("random")
    both_reset(pos0, q0)
    hover_f = body_force(fz=weight_n)
    for _ in range(round(HOVER_S / dt)):
        both_step(hover_f, zeros3)
    for w, key in ((iw, "isaac"), (tw, "torch")):
        pos, quat, lin, ang = w.state()
        res.setdefault("hover", {})[key] = {"drift_max_m": float((pos - pos0).norm(dim=-1).max()),
                                            "rate_max_rad_s": float(ang.norm(dim=-1).max())}
    nan_total += int(finite_bad(iw))
    res["hover_drift_max_m"] = res["hover"]["isaac"]["drift_max_m"]
    res["hover_rate_max_rad_s"] = res["hover"]["isaac"]["rate_max_rad_s"]

    # ---------------------------------------------------------------------------------------- body frame
    pos0, _, q0 = start_poses("north")
    both_reset(pos0, q0)
    f = body_force(fx=a.mass_kg * BODY_FRAME_ACC_MPS2, fz=weight_n)
    k = round(BODY_FRAME_S / dt)
    for _ in range(k):
        both_step(f, zeros3)
    acc = {}
    for w, key in ((iw, "isaac"), (tw, "torch")):
        lin = w.state()[2]
        acc[key] = (lin / (k * dt)).reshape(-1, 3).mean(0).tolist()
    res["body_frame"] = {"yaw_enu_deg": 90.0, "force_b_n": [a.mass_kg * BODY_FRAME_ACC_MPS2, 0.0, weight_n],
                         "acc_mps2": acc, "acc_want_mps2": BODY_FRAME_ACC_MPS2}
    res["body_frame_acc_mps2"], res["body_frame_acc_want_mps2"] = acc["isaac"], BODY_FRAME_ACC_MPS2
    nan_total += int(finite_bad(iw))

    # ---------------------------------------------------------------------------------------- write check
    pos0, _, q0 = start_poses("random")
    both_reset(pos0, q0)
    half = torch.zeros(n, m, dtype=torch.bool)
    half[:, ::2] = True
    half = half.to(dev)
    qr = torch.randn(n, m, 4, generator=gen)
    qr = (qr / qr.norm(dim=-1, keepdim=True)).to(dev)
    lin_r = (torch.rand(n, m, 3, generator=gen) * 2 - 1).to(dev)
    ang_r = (torch.rand(n, m, 3, generator=gen) * 4 - 2).to(dev)
    pos_r = pos0 + (torch.rand(n, m, 3, generator=gen) - 0.5).to(dev)
    both_write(half, pos_r, qr, lin_r, ang_r)
    both_step(zeros3, zeros3)
    si, st = iw.state(), tw.state()
    qgap = torch.minimum((si[1] - st[1]).abs().amax(-1), (si[1] + st[1]).abs().amax(-1))   # q and -q are one attitude
    errs = [(si[0] - st[0]).abs().amax(-1), qgap, (si[2] - st[2]).abs().amax(-1), (si[3] - st[3]).abs().amax(-1)]
    res["write_check"] = {"pos_max_m": float(errs[0].max()), "quat_max": float(errs[1].max()),
                          "lin_vel_max_mps": float(errs[2].max()), "ang_vel_max_rad_s": float(errs[3].max())}
    res["write_readback_max_err"] = max(res["write_check"].values())
    nan_total += int(finite_bad(iw))

    # ---------------------------------------------------------------------------------------- open loop (gate 2)
    pos0, _, q0 = start_poses("random")
    both_reset(pos0, q0)
    f = body_force(fz=OPEN_LOOP_THRUST_X_WEIGHT * weight_n)
    tq = torch.zeros(n, m, 3, device=dev)
    tq[...] = torch.tensor(OPEN_LOOP_TORQUE_NM, device=dev)
    pos_gap, ang_gap, rpy_i, rpy_t = [], [], [], []
    for _ in range(round(OPEN_LOOP_S / dt)):
        both_step(f, tq)
        si, st = iw.state(), tw.state()
        pos_gap.append((si[0] - st[0]).norm(dim=-1).amax())
        ang_gap.append(angle_gap_deg(si[1], st[1]).amax())
        rpy_i.append(rpy_deg(si[1][0, 0]))
        rpy_t.append(rpy_deg(st[1][0, 0]))
    pos_gap, ang_gap = torch.stack(pos_gap).cpu(), torch.stack(ang_gap).cpu()
    si, st = iw.state(), tw.state()
    res["open_loop"] = {
        "seconds": OPEN_LOOP_S, "thrust_x_weight": OPEN_LOOP_THRUST_X_WEIGHT, "torque_nm": list(OPEN_LOOP_TORQUE_NM),
        "pos_max_m": float(pos_gap.max()), "angle_max_deg": float(ang_gap.max()),
        "pos_end_max_m": float(pos_gap[-1]), "angle_end_max_deg": float(ang_gap[-1]),
        "travel_mean_m": float((si[0] - pos0).norm(dim=-1).mean()),
        "tilt_end_mean_deg": float(angle_gap_deg(si[1], q0).mean()),
        "per_step": {"pos_gap_max_m": pos_gap.tolist(), "angle_gap_max_deg": ang_gap.tolist(),
                     "rpy_deg_game0_drone0_isaac": torch.stack(rpy_i).cpu().tolist(),
                     "rpy_deg_game0_drone0_torch": torch.stack(rpy_t).cpu().tolist()}}
    res["open_loop_pos_max_m"], res["open_loop_angle_max_deg"] = res["open_loop"]["pos_max_m"], \
        res["open_loop"]["angle_max_deg"]
    nan_total += int(finite_bad(iw))
    print("open_loop", {k_: v for k_, v in res["open_loop"].items() if k_ != "per_step"}, flush=True)

    # ---------------------------------------------------------------------------------------- roll check (INFO)
    pos0, _, q0 = start_poses("east")
    both_reset(pos0, q0)
    hover_rotor_n = weight_n / 4.0
    right = torch.tensor([1.0 if xy[1] > 0 else -1.0 for xy in a.rotor_xy_cad_m], device=dev)  # FRD y > 0
    thrust = torch.full((n, m, 4), hover_rotor_n, device=dev) * (1.0 + ROLL_CHECK_FRAC * right)
    f, tq = body_wrench_flu(thrust, a, p.rotor_geometry)
    roll_i, roll_t = [], []
    for _ in range(round(ROLL_CHECK_S / dt)):
        both_step(f, tq)
        roll_i.append(rpy_deg(iw.state()[1])[..., 0].mean())
        roll_t.append(rpy_deg(tw.state()[1])[..., 0].mean())
    tau_x = float(tq[0, 0, 0])
    k = round(ROLL_CHECK_S / dt)
    res["roll_check"] = {
        "torque_x_nm": tau_x, "seconds": ROLL_CHECK_S,
        "roll_exact_deg": math.degrees(0.5 * tau_x / a.inertia_kgm2[0] * ROLL_CHECK_S ** 2),
        "roll_semi_implicit_formula_deg": math.degrees(tau_x / a.inertia_kgm2[0] * dt * dt * k * (k + 1) / 2),
        "roll_rate_want_rad_s": tau_x / a.inertia_kgm2[0] * ROLL_CHECK_S,
        "roll_rate_isaac_rad_s": float(iw.state()[3][..., 0].mean()),
        "roll_rate_torch_rad_s": float(tw.state()[3][..., 0].mean()),
        "roll_isaac_deg": float(roll_i[-1]), "roll_torch_deg": float(roll_t[-1]),
        "per_step_roll_isaac_deg": torch.stack(roll_i).cpu().tolist(),
        "per_step_roll_torch_deg": torch.stack(roll_t).cpu().tolist()}
    nan_total += int(finite_bad(iw))
    print("roll_check", {k_: v for k_, v in res["roll_check"].items() if not k_.startswith("per_step")}, flush=True)

    # ---------------------------------------------------------------------------------------- tumble (INFO)
    te = TorchRigidBodyWorld(n, m, a, dt, dev, gyro="explicit")
    pos0, _, q0 = start_poses("random")
    rates = torch.zeros(n, m, 3)
    rates[:, ::2] = torch.tensor(TUMBLE_RATES_RAD_S[0])
    rates[:, 1::2] = torch.tensor(TUMBLE_RATES_RAD_S[1])
    rates = rates.to(dev)
    inert = torch.tensor(a.inertia_kgm2, device=dev)
    worlds = {"isaac": iw, "torch_momentum_preserving": tw, "torch_explicit": te}
    for w in worlds.values():
        w.reset(allm, pos0, q0)
        w.write_state(allm, pos0, q0, zeros3, rates)

    def energy_and_l(w):
        ang = w.state()[3].double()
        return 0.5 * (inert.double() * ang * ang).sum(-1), (inert.double() * ang).norm(dim=-1)

    e0, l0 = energy_and_l(iw)
    for _ in range(round(TUMBLE_S / dt)):
        for w in worlds.values():
            w.apply_wrench_b(zeros3, zeros3)
            w.step()
    tum = {"seconds": TUMBLE_S, "start_rates_rad_s": [list(r) for r in TUMBLE_RATES_RAD_S], "worlds": {}}
    for key, w in worlds.items():
        e, l_ = energy_and_l(w)
        tum["worlds"][key] = {"energy_drift_rel_mean": float((e / e0 - 1).mean()),
                              "energy_drift_rel_max": float((e / e0 - 1).abs().max()),
                              "momentum_drift_rel_max": float((l_ / l0 - 1).abs().max())}
    for key in ("torch_momentum_preserving", "torch_explicit"):
        w = worlds[key]
        tum["worlds"][key]["attitude_gap_to_isaac_max_deg"] = float(angle_gap_deg(iw.state()[1], w.state()[1]).max())
        tum["worlds"][key]["rate_gap_to_isaac_max_rad_s"] = float((iw.state()[3] - w.state()[3]).norm(dim=-1).max())
    res["tumble"] = tum
    nan_total += int(finite_bad(iw))
    print("tumble", json.dumps(tum), flush=True)
    del te

    # ---------------------------------------------------------------------------------------- closed loop (gate 3)
    if not args.smoke:
        res["closed_loop"] = closed_loop(gates_cfg["step_tests"]["steps"], iw, tw, p, dev, start_poses, allm)
        nan_total += res["closed_loop"]["nonfinite_total"]
    res["nan"] = int(nan_total) + int(finite_bad(iw))
    res["meta"]["wall_s"] = round(time.time() - t_start, 1)
    return res


def closed_loop(steps: list[dict], iw, tw, p, dev, start_poses, allm) -> dict:
    """The step set through PhysicsDrone on both worlds; per step the per-tick speeds and the gaps."""
    import numpy as np
    import torch

    from svg_training.models.physics_drone import GAME_TICK_S, PhysicsDrone

    drones = {"isaac": PhysicsDrone(iw, p, dev), "torch": PhysicsDrone(tw, p, dev)}
    out: dict = {"setpoints": "p_sp ramps at the step speed, v_ff = step speed, a_ff = 0; yaw held at the start "
                              "heading; then_mps flown during the release time, else the setpoint stops",
                 "lead_s": LEAD_S, "yaw_torque_cutoff_hz": drones["isaac"].cascade.yaw_cutoff_hz,
                 "steps": []}
    arrays = {}
    nonfinite = 0
    for s in steps:
        name = s["name"]
        cmd = torch.tensor(s["cmd_mps"], dtype=torch.float32, device=dev)
        then = torch.tensor(s.get("then_mps", [0.0, 0.0, 0.0]), dtype=torch.float32, device=dev)
        axis = cmd / cmd.norm()
        pos0, yaw0, _ = start_poses("random")
        for d in drones.values():
            d.reset(allm, pos0, yaw0)
        phases = [(LEAD_S, torch.zeros(3, device=dev)), (float(s["push_s"]), cmd), (float(s["release_s"]), then)]
        p_sp = pos0.clone()
        zero_rate = torch.zeros_like(yaw0)
        v_log = {"isaac": [], "torch": []}
        p_log = {"isaac": [], "torch": []}
        cmd_log, ends = [], []
        for dur, v in phases:
            for _ in range(round(dur / GAME_TICK_S)):
                p_sp = p_sp + v * GAME_TICK_S
                v_ff = v.expand_as(pos0)
                for key, d in drones.items():
                    d.step_setpoint(p_sp, v_ff, torch.zeros_like(pos0), yaw0, zero_rate)
                    v_log[key].append(d.vel_mps.clone())
                    p_log[key].append(d.pos_m.clone())
                cmd_log.append(float((v * axis).sum()))
            ends.append(len(cmd_log) - 1)
        vi, vt = torch.stack(v_log["isaac"]), torch.stack(v_log["torch"])          # [T, N, M, 3]
        pi_, pt = torch.stack(p_log["isaac"]), torch.stack(p_log["torch"])
        dv = (vi - vt).norm(dim=-1)                                                  # [T, N, M]
        rms = dv.pow(2).mean(0).sqrt()                                               # [N, M]
        pgap = (pi_ - pt).norm(dim=-1)
        nf = int(sum(int(dd.nonfinite_count) for dd in drones.values()))
        nf += int((~torch.isfinite(vi)).sum() + (~torch.isfinite(pi_)).sum())
        nonfinite += nf
        row = {"name": name, "cmd_mps": s["cmd_mps"], "then_mps": s.get("then_mps"), "push_s": s["push_s"],
               "release_s": s["release_s"], "ticks": len(cmd_log),
               "vel_rms_max_mps": float(rms.max()), "vel_rms_mean_mps": float(rms.mean()),
               "vel_gap_peak_mps": float(dv.max()),
               "pos_end_max_m": float(pgap[-1].max()), "pos_end_push_max_m": float(pgap[ends[1]].max()),
               "pos_gap_peak_m": float(pgap.max()),
               "peak_speed_along_isaac_mps": float((vi * axis).sum(-1).abs().max()),
               "peak_speed_along_torch_mps": float((vt * axis).sum(-1).abs().max()),
               "max_tilt_deg_isaac": float(torch.rad2deg(drones["isaac"].max_tilt_rad).max()),
               "max_tilt_deg_torch": float(torch.rad2deg(drones["torch"].max_tilt_rad).max()),
               "upsets_isaac": int(drones["isaac"].upset.sum()), "upsets_torch": int(drones["torch"].upset.sum()),
               "nonfinite": nf}
        out["steps"].append(row)
        print("closed_loop", json.dumps(row), flush=True)
        t = (np.arange(len(cmd_log)) + 1) * GAME_TICK_S
        arrays[f"{name}_t"] = t
        arrays[f"{name}_cmd"] = np.array(cmd_log)
        arrays[f"{name}_v_isaac"] = (vi * axis).sum(-1).mean(dim=(1, 2)).cpu().numpy()
        arrays[f"{name}_v_torch"] = (vt * axis).sum(-1).mean(dim=(1, 2)).cpu().numpy()
        arrays[f"{name}_gap"] = dv.amax(dim=(1, 2)).cpu().numpy()
    out["nonfinite_total"] = nonfinite
    out["_arrays"] = arrays
    return out


# --------------------------------------------------------------------------------------------- record and ledger
def write_record(name: str, res: dict, rows: list[dict], verdict: str, t_number: int, date: str,
                 gates_path: pathlib.Path) -> pathlib.Path:
    rb, ol, rc, tum = res["readback"], res["open_loop"], res["roll_check"], res["tumble"]
    meta = res["meta"]
    bs = rb["body_settings"]
    lines = [FIRST_LINE, "", f"# {date} {name} record", "",
             f"Result: **{verdict}** against `[agreement_gates]` of `{gates_path.relative_to(ROOT)}`. Ledger row "
             f"T{t_number}. Observed in the training simulator; nothing here is a flight result.", "",
             "## Purpose", "",
             "S2b flies the S2 game on rigid-body Starlings. Two worlds can move those bodies: Isaac Lab (PhysX, the "
             "one training will use) and a small PyTorch world written to the same equations, which the CPU tests "
             "use. This run gives both worlds the same forces, then the same PX4 control cascade, and measures how "
             "far apart they end up. If they agree, everything checked on the PyTorch world also holds in Isaac Lab, "
             "and the Isaac Lab body is the one we specified (mass, inertia, no damping, no collider).", "",
             "## Commit", "", f"`{meta['commit']}`, code fingerprint `{meta['code_sha']}`.", "",
             "## Config", "",
             f"- Gates: `{gates_path.relative_to(ROOT)}` (sha256 `{meta['gates_sha256']}`), tables `[agreement]` and "
             f"`[agreement_gates]`, copied to `runs/{name}/gates.toml` before the run.",
             f"- Physics: `{meta['params']}` (sha256 `{meta['params_sha256']}`), physics step {meta['physics_dt_s']} s, "
             f"plant rotor positions `{meta['rotor_geometry']}`, motor lag {'on' if meta['motor_lag'] else 'off'}.",
             f"- Cascade: the drone's own PX4 gains, yaw torque filter {res.get('closed_loop', {}).get('yaw_torque_cutoff_hz')} Hz "
             "(the drone's `MC_YAW_CUTOFF`), allocator saturation feedback on. The same cascade drives both worlds; "
             "the yaw-gain question that is open with the owner does not change this comparison.",
             f"- PyTorch world: `TorchRigidBodyWorld`, gyroscopic step `{meta['torch_gyro']}` (PhysX's own).",
             f"- PhysX solver type {bs['solver_type']} (Isaac Lab default, TGS); one `RigidObjectCollection` of all "
             "drone slots; wrench set as one body-frame force and torque per drone per physics step.",
             f"- Command: `{meta['command']}`.", "",
             "## Model parameter set", "",
             f"Rigid-body Starling `{meta['params']}`: mass {rb['mass_kg_want']} kg, inertia "
             f"{rb['inertia_kgm2_want']} kg m², CMU system identification; gains copied from the drone's file.", "",
             "## Seeds", "", f"Start poses and headings: torch generator seeded {meta['seed']} (`[agreement] seed`).", "",
             "## Machine", "",
             f"{meta.get('gpu', 'GPU unknown')}; Isaac Sim 5.1.0 / Isaac Lab 2.3.2 in the container "
             f"`svg-training:isaaclab-2.3.2`, headless. GPU memory in use before launch (nvidia-smi): "
             f"{meta.get('nvsmi_before_mib')} MiB. Wall time {meta['wall_s']} s.", "",
             "## Games at once", "",
             f"{meta['games']} games x {meta['drones_per_game']} drones = {meta['games'] * meta['drones_per_game']} "
             "bodies in each world, side by side in one process.", "",
             "## Steps per second", "", "Not measured here (Task 7 measures throughput).", "",
             "## Gates", "", "| Gate | Limit | Measured | Result |", "|---|---|---|---|"]
    for r in rows:
        lines.append(f"| `{r['gate']}` | {r['limit']:g} | {r['value']:.3g} | {'PASS' if r['pass'] else 'FAIL'} |")
    lines += ["", "## The body PhysX holds (read back)", "",
              f"- Mass {rb['mass_kg_got'][0]:.6g}–{rb['mass_kg_got'][1]:.6g} kg; inertia diagonal "
              f"{[round(x, 7) for x in rb['inertia_kgm2_got_min']]} to {[round(x, 7) for x in rb['inertia_kgm2_got_max']]} "
              f"kg m²; largest off-diagonal entry {rb['inertia_offdiag_max_kgm2']:.2g}; centre of mass at most "
              f"{rb['com_offset_max_m']:.2g} m from the body origin.",
              f"- Rigid-body settings on the stage (`{bs['prim']}`): gyroscopic forces "
              f"{'on' if bs['enable_gyroscopic_forces'] else 'OFF'}, damping {bs['linear_damping']} / "
              f"{bs['angular_damping']}, sleep threshold {bs['sleep_threshold']}, max angular velocity "
              f"{bs['max_angular_velocity_deg_s']:g} deg/s, collider {'yes' if bs['has_collider'] else 'none'}.", "",
              "## Checks without the cascade", "",
              "| Check | Isaac Lab world | PyTorch world |", "|---|---|---|",
              f"| Hover 2 s: drift (m) | {res['hover']['isaac']['drift_max_m']:.2e} | "
              f"{res['hover']['torch']['drift_max_m']:.2e} |",
              f"| Hover 2 s: largest body rate (rad/s) | {res['hover']['isaac']['rate_max_rad_s']:.2e} | "
              f"{res['hover']['torch']['rate_max_rad_s']:.2e} |",
              f"| Nose north, +x body force of {res['body_frame']['acc_want_mps2']} m/s²: world acceleration (m/s²) | "
              f"{[round(x, 4) for x in res['body_frame']['acc_mps2']['isaac']]} | "
              f"{[round(x, 4) for x in res['body_frame']['acc_mps2']['torch']]} |", "",
              "State write check: a random state written to every other drone in both worlds, then one free step: "
              f"largest gaps {res['write_check']['pos_max_m']:.1e} m, {res['write_check']['quat_max']:.1e} "
              f"(quaternion), {res['write_check']['lin_vel_max_mps']:.1e} m/s, "
              f"{res['write_check']['ang_vel_max_rad_s']:.1e} rad/s.", "",
              f"First step after the start (a roll torque from rest): roll rate {res['first_step']['roll_rate_isaac_rad_s']:.6f} "
              f"rad/s in Isaac Lab, {res['first_step']['roll_rate_torch_rad_s']:.6f} in the PyTorch world.", "",
              f"Open loop (gate 2): {ol['seconds']} s of thrust {ol['thrust_x_weight']} x weight and torque "
              f"{ol['torque_nm']} N m from hover, random headings. The drones moved {ol['travel_mean_m']:.3f} m on "
              f"average and tilted {ol['tilt_end_mean_deg']:.2f} deg. Largest gap between the worlds over every step: "
              f"{ol['pos_max_m']:.2e} m and {ol['angle_max_deg']:.2e} deg. Roll, pitch and yaw of game 0, drone 0 "
              "are in `results.json` for every step in both worlds.", "",
              f"Roll check (INFO, the S2b spike's test): after {rc['seconds']} s of a 1 % roll differential the roll "
              f"angle is {rc['roll_isaac_deg']:.4f} deg in Isaac Lab and {rc['roll_torch_deg']:.4f} deg in the PyTorch "
              f"world (exact formula {rc['roll_exact_deg']:.4f}, semi-implicit Euler formula "
              f"{rc['roll_semi_implicit_formula_deg']:.4f}); roll rate {rc['roll_rate_isaac_rad_s']:.5f} / "
              f"{rc['roll_rate_torch_rad_s']:.5f} rad/s (want {rc['roll_rate_want_rad_s']:.5f}).", "",
              f"Tumble (INFO): {tum['seconds']} s of free tumbling, half the drones from body rates (2, -1, 1.5) rad/s, half "
              "from the cascade's rate limits (130, -130, 150 deg/s).", "",
              "| World | energy change, mean | angular momentum change, largest | attitude gap to Isaac (deg) | "
              "rate gap to Isaac (rad/s) |", "|---|---|---|---|---|"]
    names = {"isaac": "Isaac Lab (PhysX)", "torch_momentum_preserving": "PyTorch, PhysX's gyroscopic step (default)",
             "torch_explicit": "PyTorch, the plan's explicit gyroscopic step"}
    for key, v in tum["worlds"].items():
        gap_a = f"{v['attitude_gap_to_isaac_max_deg']:.3g}" if "attitude_gap_to_isaac_max_deg" in v else "—"
        gap_r = f"{v['rate_gap_to_isaac_max_rad_s']:.3g}" if "rate_gap_to_isaac_max_rad_s" in v else "—"
        lines.append(f"| {names.get(key, key)} | {v['energy_drift_rel_mean']:+.2e} | {v['momentum_drift_rel_max']:.2e} | "
                     f"{gap_a} | {gap_r} |")
    cl = res.get("closed_loop")
    if cl:
        lines += ["", "## Closed loop (gate 3)", "",
                  f"Setpoints: {cl['setpoints']}; {cl['lead_s']} s of hold first. Speeds are world velocities.", "",
                  "| Step | speed RMS gap, largest drone (m/s) | position gap at the end (m) | at the end of the push (m) | "
                  "peak speed Isaac / torch (m/s) | largest tilt Isaac / torch (deg) | upsets | non-finite |",
                  "|---|---|---|---|---|---|---|---|"]
        for s in cl["steps"]:
            lines.append(f"| {s['name']} | {s['vel_rms_max_mps']:.2e} | {s['pos_end_max_m']:.2e} | "
                         f"{s['pos_end_push_max_m']:.2e} | {s['peak_speed_along_isaac_mps']:.4f} / "
                         f"{s['peak_speed_along_torch_mps']:.4f} | {s['max_tilt_deg_isaac']:.2f} / "
                         f"{s['max_tilt_deg_torch']:.2f} | {s['upsets_isaac']} / {s['upsets_torch']} | "
                         f"{s['nonfinite']} |")
        lines += ["", f"![Isaac Lab world against the PyTorch world, per step](../docs/figures/{FIGURE.name})", "",
                  "*Speed along the command for each step, averaged over all drones: Isaac Lab world (solid) and "
                  "PyTorch reference world (dashed) under the same PX4 cascade. Below, the largest speed gap between "
                  "the two worlds over all drones, log scale. Made by `scripts/physics_agreement.py --figure-from`.*"]
    lines += ["", "## Files", "", f"`runs/{name}/`: `gates.toml`, `results.json`, `closed_loop.npz`, `run.log`.", ""]
    out = ROOT / "records" / f"{name}_record.md"
    out.write_text("\n".join(lines))
    return out


def append_ledger(name: str, verdict: str, date: str, res: dict) -> int:
    ledger = ROOT / "records" / "LEDGER.md"
    text = ledger.read_text()
    t = next_ledger_number(text)
    meta = res["meta"]
    row = (f"| T{t} | {date} | training simulator, tier 2 (Isaac Lab) against its PyTorch reference world "
           f"(rigid-body Starlings, PX4 1.14 cascade with the drone's gains) | {name} | S2b agreement: "
           f"{meta['games']} games x {meta['drones_per_game']} drones, mass/inertia read-back, 1 s open-loop wrench, "
           f"{len(res.get('closed_loop', {}).get('steps', []))} closed-loop steps | {verdict} | "
           f"records/{name}_record.md |")
    if not text.endswith("\n"):
        text += "\n"
    ledger.write_text(text + row + "\n")
    return t


# --------------------------------------------------------------------------------------------- main
def make_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gates", default="configs/s2b.toml")
    ap.add_argument("--name", help="run name, e.g. 2026-11-16_s2b_agreement (full run)")
    ap.add_argument("--smoke", action="store_true", help="4 games, no closed loop, writes only --out")
    ap.add_argument("--out", help="smoke: where to write the JSON")
    return ap


def main() -> int:
    if "--figure-from" in sys.argv:                      # no Isaac: redraw the figure from a run's files
        ap = argparse.ArgumentParser()
        ap.add_argument("--figure-from", required=True)
        ap.add_argument("--figure-out", default=str(FIGURE))
        a = ap.parse_args()
        make_figure(a.figure_from, a.figure_out)
        return 0
    if "--record-from" in sys.argv:                      # no Isaac: rewrite the record from a run's files (ledger untouched)
        ap = argparse.ArgumentParser()
        ap.add_argument("--record-from", required=True)
        ap.add_argument("--ledger-number", type=int, required=True, help="the run's existing T number")
        a = ap.parse_args()
        run_dir = pathlib.Path(a.record_from).resolve()
        res = json.loads((run_dir / "results.json").read_text())
        write_record(run_dir.name, res, res["gates"], res["verdict"], a.ledger_number, res["meta"]["date"],
                     ROOT / "configs" / "s2b.toml")
        return 0
    nvsmi_before = gpu_used_mib()
    from _isaac_app import start_headless
    args, _app = start_headless(make_parser())
    code = 1
    try:
        code = main_after_launch(args, nvsmi_before)
    except BaseException:
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)


def main_after_launch(args, nvsmi_before: int | None) -> int:
    gates_path = (ROOT / args.gates).resolve() if not os.path.isabs(args.gates) else pathlib.Path(args.gates)
    gates_cfg = tomllib.loads(gates_path.read_text())
    if args.smoke:
        if not args.out:
            print("--smoke needs --out", file=sys.stderr)
            return 2
    elif not args.name:
        print("a full run needs --name", file=sys.stderr)
        return 2
    run_dir = None
    if not args.smoke:
        run_dir = ROOT / "runs" / args.name
        if (run_dir / "results.json").exists():
            print(f"refused: {run_dir}/results.json exists (a new run needs a new name)", file=sys.stderr)
            return 2
        run_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(gates_path, run_dir / "gates.toml")
    date = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    import torch

    from svg_training.bench.rows import code_sha
    res = run(args, gates_cfg)
    params = ROOT / gates_cfg["physics"]["params"]
    res["meta"].update(commit=commit(), code_sha=code_sha(), date=date, gates_sha256=sha256_12(gates_path),
                       params=str(params.relative_to(ROOT)), params_sha256=sha256_12(params),
                       nvsmi_before_mib=nvsmi_before, gpu=torch.cuda.get_device_name(),
                       command="svg-isaaclab -p scripts/physics_agreement.py " + " ".join(sys.argv[1:]))
    rows = gate_rows(res, gates_cfg["agreement_gates"]) if not args.smoke else []
    verdict = ("PASS" if all(r["pass"] for r in rows) else "FAIL") if rows else "SMOKE"
    res["gates"], res["verdict"] = rows, verdict
    arrays = res.get("closed_loop", {}).pop("_arrays", None)
    res["mass_rel_err"], res["inertia_rel_err"] = res["readback"]["mass_rel_err"], res["readback"]["inertia_rel_err"]
    res["com_offset_max_m"], res["body_settings"] = res["readback"]["com_offset_max_m"], res["readback"]["body_settings"]
    if args.smoke:
        pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.out).write_text(json.dumps(res, indent=1))
        print("smoke written:", args.out)
        return 0
    import numpy as np
    np.savez(run_dir / "closed_loop.npz", **arrays)
    (run_dir / "results.json").write_text(json.dumps(res, indent=1))
    try:
        make_figure(run_dir, FIGURE)
    except Exception:                                    # the figure can be redrawn on the host with --figure-from
        traceback.print_exc()
        print("figure not drawn here: run scripts/physics_agreement.py --figure-from", run_dir)
    t_number = append_ledger(args.name, verdict, date, res)
    rec = write_record(args.name, res, rows, verdict, t_number, date, gates_path)
    print(f"VERDICT {verdict}  ledger T{t_number}  record {rec.relative_to(ROOT)}")
    for r in rows:
        print(f"  {r['gate']}: {r['value']:.4g} <= {r['limit']:g}  {'PASS' if r['pass'] else 'FAIL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
