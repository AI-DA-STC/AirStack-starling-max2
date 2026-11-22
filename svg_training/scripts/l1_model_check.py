#!/usr/bin/env python
"""STE tasks L1.1, L1.1b and L1.2 on the GPU: the isaac-marked tests of the new physics path, then what the estimator
effect (L1.1b: correlated estimate error, white noise; no delay in the "on" arm) and the drag cost in throughput
(CODING_PRACTICES section 9 budget: at most 10 % at 4,096 games; INFO, not a gate).

    # after nvidia-smi and scripts/isaac_preflight.sh --approved-headless (exit 0), alone on the GPU:
    scripts/ste_job.py launch --task L1.1 --name ste_l1_model_check --run-dir runs/<date>_ste_l1_model_check \\
        --min-s 120 --gpu-h 0.2 -- <python> scripts/l1_model_check.py --run-dir runs/<date>_ste_l1_model_check \\
        --cap-h 0.2 --headless
    l1_model_check.py --smoke --headless --out <file.json>     # what tests/test_estimator_effect.py (isaac) runs:
                                                               # delay, white noise, correlated error, hover, agreement
    l1_model_check.py --run-dir runs/<dir> --cap-h 0.05 --dry-cpu     # tests only: the torch world on the CPU

Settings: ``configs/ste_l1/model_check.toml``. One parent process (no Isaac, no CUDA work) runs, in order, each part
not yet done (``points/<part>.json``; the same command resumes):

1. ``isaac_tests``: ``pytest -m isaac`` on ``tests/test_estimator_effect.py``, ``tests/test_drag.py`` and
   ``tests/test_isaac_world.py`` (the Isaac agreement smoke, rerun because the wrench and state path changed,
   CODING_PRACTICES section 2.3), with ``SVG_ISAAC_TESTS=1``; log ``isaac_tests.log``.
2. ``tier2_isaac``: one child with Isaac Lab, the L0.2 game (``configs/ste_l011/base.toml``, backend "physics") at
   3v3 x 4,096 games, random actions; on ONE world, games with the effects off (``params/starling_physics_v1.toml``)
   and on (a copy with ``[effects_on]`` written in, ``params_on.toml``) alternate, ``repeats`` times each.
3. ``tier2_torch``: the same on the PyTorch reference world on the GPU (the torch twin; no Isaac).
4. ``tier1``: the fitted backend, effects OFF only: tier 1 has no delay, noise or drag until L1.7, so its row is the
   baseline L1.7 will compare against, and its "on" arm is reported as not built.

``results.json`` and ``results.md``: game-steps/s per arm and repeat, cost = 1 - mean(on) / mean(off) per world, upsets
and non-finite counts per arm (the "on" arm's values are made up: upsets there are a finding, not a crash). The game
arms seed the estimator noise with the game seed (``PhysicsLayer``, L1.1b).
Contract (``ste/run_contract.py``): exit 0 done; 2 refused (bad arguments, run folder busy, --cap-h != the launcher's
--gpu-h); 3 cap (the running child is stopped, its part redone on resume); 4 stopped on request; 6 the isaac tests
failed (the throughput parts still run). Observed in the training simulator; nothing here is a flight result.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import platform
import re
import signal
import subprocess
import sys
import time
import tomllib
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

SETTINGS = ROOT / "configs" / "ste_l1" / "model_check.toml"
HOUR_S = 3600.0
POINTS_DIR = "points"
PARTS = ("isaac_tests", "tier2_isaac", "tier2_torch", "tier1")
ISAAC_TEST_FILES = ("tests/test_estimator_effect.py", "tests/test_drag.py", "tests/test_isaac_world.py")
POLL_S = 1.0
KILL_WAIT_S = 60.0


def say(text: str) -> None:
    print(f"[l1-model] {text}", flush=True)


def load_settings(path: Path = SETTINGS) -> dict:
    return tomllib.loads(path.read_text())


def write_json(path: Path, obj) -> None:
    from svg_training.ste import atomic
    atomic.write_text(path, json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


# ================================================================================================ checks (both worlds)
def _spy_cascade(drone, world, log: list) -> None:
    """Record, at every cascade call, its four state inputs (NED / FRD, as the drone passes them) and the world's
    true state at that instant (ENU / FLU)."""
    real = drone.cascade.step

    def step(p_sp, v_ff, a_ff, yaw_sp, yaw_ff, pos, vel, r, omega):
        log.append(((pos.clone(), vel.clone(), r.clone(), omega.clone()), tuple(x.clone() for x in world.state())))
        return real(p_sp, v_ff, a_ff, yaw_sp, yaw_ff, pos, vel, r, omega)

    drone.cascade.step = step


def _starts(n: int, m: int, device) -> "object":
    import torch
    x = torch.arange(m, dtype=torch.float32, device=device) * 1.5
    pos = torch.zeros(n, m, 3, device=device)
    pos[..., 0] = x
    pos[..., 1] = torch.arange(n, dtype=torch.float32, device=device)[:, None] * 0.5
    pos[..., 2] = 1.2
    return pos


def _ned_inputs(pos, quat, vel, ang):
    """The four cascade inputs PhysicsDrone makes from a state (the same calls, models/physics_drone.py)."""
    import torch

    from svg_training.models.frames import quat_wxyz_to_rotmat, rot_enu_flu_to_ned_frd, vec_enu_to_ned
    return (vec_enu_to_ned(pos), vec_enu_to_ned(vel), rot_enu_flu_to_ned_frd(quat_wxyz_to_rotmat(quat)),
            torch.stack((ang[..., 0], -ang[..., 1], -ang[..., 2]), dim=-1))


def _effects_off() -> dict:
    """Every estimator and drag key at 0 (the delay too)."""
    from svg_training.models.physics_params import EFFECT_KEYS
    return {k: 0.0 for k in EFFECT_KEYS}


def delay_check(world, params, delay_steps: int, ticks: int, device) -> dict:
    """Fly a step setpoint with a residual state delay of ``delay_steps`` physics steps (no noise, no error, no drag) and
    compare every cascade input with the inputs the true state makes: position and velocity of ``delay_steps`` steps
    earlier (the reset state before that), attitude and body rates of the same step (never delayed, L1.1b). Returns the
    largest absolute difference (0.0 = exact)."""
    import torch

    from svg_training.models.physics_drone import PhysicsDrone
    p = dataclasses.replace(params, **{**_effects_off(), "state_delay_s": delay_steps * params.physics_dt_s})
    n, m = world.num_games, world.drones
    d = PhysicsDrone(world, p, device)
    start = _starts(n, m, device)
    d.reset(torch.ones(n, m, dtype=torch.bool, device=device), start, torch.zeros(n, m, device=device))
    log: list = []
    _spy_cascade(d, world, log)
    sp = start + torch.tensor([0.6, -0.4, 0.2], device=device)
    zero3 = torch.zeros(n, m, 3, device=device)
    for _ in range(ticks):
        d.step_setpoint(sp, zero3, zero3, torch.zeros(n, m, device=device), torch.zeros(n, m, device=device))
    worst = 0.0
    for j, (inputs, _truth) in enumerate(log):
        lagged = log[max(j - delay_steps, 0)][1]
        now = log[j][1]
        want = _ned_inputs(lagged[0], now[1], lagged[2], now[3])
        for a, b in zip(inputs, want):
            worst = max(worst, float((a - b).abs().max()))
    moved = float((log[-1][1][0] - log[0][1][0]).norm(dim=-1).max())
    return {"delay_steps": p.state_delay_steps(), "substeps_checked": len(log), "max_err": worst, "moved_m": moved,
            "world": getattr(world, "label", "?")}


def _rotvec_small(r_a, r_b):
    """Rotation vector of r_a^T r_b (vee of the skew part; exact to O(angle^3))."""
    e = r_a.transpose(-1, -2) @ r_b
    import torch
    return 0.5 * torch.stack((e[..., 2, 1] - e[..., 1, 2], e[..., 0, 2] - e[..., 2, 0], e[..., 1, 0] - e[..., 0, 1]),
                             dim=-1)


def noise_check(world, params, ticks: int, device, sigma: dict | None = None, seed: int | None = None) -> dict:
    """Hover with state noise only (made-up sigmas, default ``[effects_on]``) and return, per quantity, the mean and
    standard deviation of (cascade input - the inputs the true state makes), pooled over axes, drones and steps."""
    import torch

    from svg_training.models.physics_drone import PhysicsDrone
    on = load_settings()["effects_on"]
    sigma = sigma or {"pos": on["state_noise_pos_m"], "vel": on["state_noise_vel_mps"],
                      "att": on["state_noise_att_rad"], "rate": on["state_noise_rate_rad_s"]}
    p = dataclasses.replace(params, **{**_effects_off(), "state_noise_pos_m": sigma["pos"],
                                       "state_noise_vel_mps": sigma["vel"], "state_noise_att_rad": sigma["att"],
                                       "state_noise_rate_rad_s": sigma["rate"]})
    n, m = world.num_games, world.drones
    seed = load_settings()["run"]["noise_seed"] if seed is None else seed
    d = PhysicsDrone(world, p, device, noise_seed=seed)
    start = _starts(n, m, device)
    d.reset(torch.ones(n, m, dtype=torch.bool, device=device), start, torch.zeros(n, m, device=device))
    log: list = []
    _spy_cascade(d, world, log)
    zero3 = torch.zeros(n, m, 3, device=device)
    for _ in range(ticks):
        d.step_setpoint(start, zero3, zero3, torch.zeros(n, m, device=device), torch.zeros(n, m, device=device))
    err = {"pos": [], "vel": [], "att": [], "rate": []}
    for inputs, truth in log:
        want = _ned_inputs(*truth)
        err["pos"].append(inputs[0] - want[0])
        err["vel"].append(inputs[1] - want[1])
        err["att"].append(_rotvec_small(want[2], inputs[2]))
        err["rate"].append(inputs[3] - want[3])
    out = {}
    for k, xs in err.items():
        x = torch.stack(xs).double().flatten()
        out[k] = {"sigma": float(sigma[k]), "mean": float(x.mean()), "std": float(x.std()), "count": int(x.numel())}
    return out


def error_check(world, params, ticks: int, device, tau_s: float, sigma: dict | None = None,
                seed: int | None = None) -> dict:
    """Hover with the correlated estimate error only (L1.1b; sigmas default ``[effects_on]``, one MADE-UP correlation
    time ``tau_s`` for all three, short so that a few seconds hold many independent samples) and return, per quantity,
    the mean, standard deviation and lag-1 autocorrelation (one physics step) of (cascade input - the inputs the true
    state makes), with the expected autocorrelation a = exp(-dt / tau) and the effective sample size n (1 - a) / (1 + a)
    the tolerances need."""
    import torch

    from svg_training.models.physics_drone import PhysicsDrone
    on = load_settings()["effects_on"]
    sigma = sigma or {"pos": on["state_error_pos_m"], "vel": on["state_error_vel_mps"], "att": on["state_error_att_rad"]}
    unit = {"pos": "m", "vel": "mps", "att": "rad"}
    p = dataclasses.replace(params, **{**_effects_off(),
                                       **{f"state_error_{q}_{unit[q]}": sigma[q] for q in unit},
                                       **{f"state_error_{q}_tau_s": tau_s for q in unit}})
    n, m = world.num_games, world.drones
    seed = load_settings()["run"]["noise_seed"] if seed is None else seed
    d = PhysicsDrone(world, p, device, noise_seed=seed)
    start = _starts(n, m, device)
    d.reset(torch.ones(n, m, dtype=torch.bool, device=device), start, torch.zeros(n, m, device=device))
    log: list = []
    _spy_cascade(d, world, log)
    zero3 = torch.zeros(n, m, 3, device=device)
    for _ in range(ticks):
        d.step_setpoint(start, zero3, zero3, torch.zeros(n, m, device=device), torch.zeros(n, m, device=device))
    err = {"pos": [], "vel": [], "att": []}
    for inputs, truth in log:                       # one entry per physics step, in order
        want = _ned_inputs(*truth)
        err["pos"].append(inputs[0] - want[0])
        err["vel"].append(inputs[1] - want[1])
        err["att"].append(_rotvec_small(want[2], inputs[2]))
    a = math.exp(-p.physics_dt_s / tau_s)
    out = {}
    for k, xs in err.items():
        x = torch.stack(xs).double()                # [steps, N, M, 3]
        x0, x1 = x[:-1].flatten(), x[1:].flatten()
        out[k] = {"sigma": float(sigma[k]), "tau_s": float(tau_s), "a_expected": a, "mean": float(x.mean()),
                  "std": float(x.std()), "rho1": float((x0 * x1).sum() / (x0 * x0).sum()), "count": int(x.numel()),
                  "n_eff": float(x.numel() * (1 - a) / (1 + a))}
    return out


def hover_check(world, params, ticks: int, device, seed: int | None = None) -> dict:
    """Hold a hover setpoint for ``ticks`` ticks with ``params`` as given (the effects it carries) and return how far the
    TRUE drones stray: 3-D RMS and largest distance from the hover point over every drone and tick end, the largest
    tilt, upsets and non-finite counts."""
    import torch

    from svg_training.models.physics_drone import PhysicsDrone
    from svg_training.models.physics_params import ERROR_KEYS
    n, m = world.num_games, world.drones
    seed = load_settings()["run"]["noise_seed"] if seed is None else seed
    d = PhysicsDrone(world, params, device, noise_seed=seed)
    start = _starts(n, m, device)
    d.reset(torch.ones(n, m, dtype=torch.bool, device=device), start, torch.zeros(n, m, device=device))
    zero3 = torch.zeros(n, m, 3, device=device)
    dist = []
    for _ in range(ticks):
        d.step_setpoint(start, zero3, zero3, torch.zeros(n, m, device=device), torch.zeros(n, m, device=device))
        dist.append((d.pos_m - start).norm(dim=-1))
    r = torch.stack(dist).double()
    return {"rms_m": float(r.pow(2).mean().sqrt()), "max_m": float(r.max()), "max_tilt_rad": float(d.max_tilt_rad.max()),
            "upsets": int(d.upset.sum()), "nonfinite": int(d.nonfinite_count), "ticks": ticks, "drones": n * m,
            "error_on": list(d.estimator.correlated), "noise_seed": seed,
            "state_error": {k: getattr(params, k) for k in ERROR_KEYS}}


def hover_params(params) -> "object":
    """``params`` with the ``[hover]`` table's MADE-UP exploratory error values (and nothing else on)."""
    h = load_settings()["hover"]
    return dataclasses.replace(params, **{**_effects_off(), **{k: v for k, v in h.items() if k.startswith("state_")}})


def agreement(iw, tw, params, ticks: int, step_m, delay_s: float, device, seed: int | None = None) -> dict:
    """The same effects-on flight (residual delay ``delay_s``, ``[effects_on]`` error, noise and drag, the same noise
    seed) on two
    worlds of the same size on the same device; the largest position gap at the end of each tick and the RMS velocity
    gap, as configs/s2b.toml [agreement_gates] closed-loop measures."""
    import torch

    from svg_training.models.physics_drone import PhysicsDrone
    on = load_settings()["effects_on"]
    p = dataclasses.replace(params, **{**on, "state_delay_s": delay_s})
    n, m = iw.num_games, iw.drones
    seed = load_settings()["run"]["noise_seed"] if seed is None else seed
    drones = [PhysicsDrone(w, p, device, noise_seed=seed) for w in (iw, tw)]
    start = _starts(n, m, device)
    for d in drones:
        d.reset(torch.ones(n, m, dtype=torch.bool, device=device), start, torch.zeros(n, m, device=device))
    sp = start + torch.tensor(step_m, device=device)
    zero3 = torch.zeros(n, m, 3, device=device)
    gap, sq, count = 0.0, 0.0, 0
    for _ in range(ticks):
        for d in drones:
            d.step_setpoint(sp, zero3, zero3, torch.zeros(n, m, device=device), torch.zeros(n, m, device=device))
        a, b = drones
        gap = max(gap, float((a.pos_m - b.pos_m).norm(dim=-1).max()))
        sq += float(((a.vel_mps - b.vel_mps) ** 2).sum(-1).sum())
        count += n * m
    return {"pos_max_m": gap, "vel_rms_mps": math.sqrt(sq / count), "ticks": ticks,
            "nonfinite": int(drones[0].nonfinite_count) + int(drones[1].nonfinite_count),
            "upsets": int(drones[0].upset.sum()) + int(drones[1].upset.sum()), "params": {**on, "state_delay_s": delay_s}}


# ================================================================================================ throughput
def params_on_file(run_dir: Path, settings: dict) -> Path:
    """``params_on.toml`` in the run folder: the base parameter file with each ``[effects_on]`` key's line replaced."""
    text = (ROOT / settings["run"]["params_base"]).read_text()
    for key, val in settings["effects_on"].items():
        text, k = re.subn(rf"(?m)^{key} = .*$", f"{key} = {float(val)!r}   # L1 model check: MADE UP, not a drone value",
                          text)
        if k != 1:
            raise ValueError(f"{key} is not a [model] line of {settings['run']['params_base']}")
    out = run_dir / "params_on.toml"
    out.write_text(text)
    return out


def measure_part(part: str, settings: dict, run_dir: Path, device: str, dry_cpu: bool, world_factory=None) -> dict:
    """One throughput part (``tier2_isaac``, ``tier2_torch`` or ``tier1``): the rates of each arm, alternated."""
    import torch

    from svg_training.bench.timing import measure
    from svg_training.core.game import SvgGame
    from svg_training.core.game_config import load_game_cfg
    run, timing = settings["run"], dict(settings["timing"])
    games, repeats = run["games"], run["repeats"]
    if dry_cpu:
        games, repeats = settings["dry_cpu"]["games"], settings["dry_cpu"]["repeats"]
        timing.update({k: settings["dry_cpu"][k] for k in ("warmup_steps", "timed_steps", "min_warmup_s", "min_timed_s")})
    g, s = run["guards"], run["strikes"]
    base, prov = load_game_cfg(ROOT / run["game_file"], use_local=False)
    world = None
    if part == "tier1":
        arms = {"off": base}
    else:
        tier2 = base.replace(**{"starling.backend": "physics", "starling.physics_params": run["params_base"]})
        arms = {"off": tier2,
                "on": tier2.replace(**{"starling.physics_params": str(params_on_file(run_dir, settings))})}
        world = world_factory(games, g + s)
    rows = {a: [] for a in arms}
    info = {a: {"upsets": 0, "nonfinite": 0} for a in arms}
    for rep in range(repeats):
        for arm, cfg in arms.items():
            torch.manual_seed(run["seed"] + rep)
            game = SvgGame(cfg, games, g, s, device=device, seed=run["seed"], world=world)
            if arm == "on":                    # the effects really are on in this game's drone
                drone = game._starling.drone
                info[arm]["delay_steps"] = drone.estimator.delay_steps
                info[arm]["noise"] = list(drone.estimator.noisy)
                info[arm]["error"] = list(drone.estimator.correlated)
                info[arm]["drag"] = drone.drag_coeff is not None
                info[arm]["noise_seed"] = drone.noise_seed          # the game seed (PhysicsLayer, L1.1b)
            upsets = torch.zeros((), dtype=torch.long, device=device)

            def step(game=game):
                nonlocal upsets
                a = {"guard": torch.rand(games, g, 4, device=device) * 2 - 1,
                     "strike": torch.rand(games, s, 4, device=device) * 2 - 1}
                out = game.step(a)
                if "upset" in out.info:
                    upsets = upsets + (out.info["upset"] & out.done).sum()
                return {"pos": game.pos_m, "vel": game.vel_mps}

            r = measure(step, int(timing["warmup_steps"]), int(timing["timed_steps"]), device,
                        float(timing["min_warmup_s"]), float(timing["min_timed_s"]))
            rows[arm].append({"repeat": rep, "game_steps_per_s": r["steps_per_s"] * games,
                              "timed_steps": r["timed_steps"], "timed_s": r["timed_s"], "nan_count": r["nan_count"],
                              "peak_mem_mb": r.get("peak_mem_mb")})
            info[arm]["upsets"] += int(upsets)
            if part != "tier1":
                info[arm]["nonfinite"] += int(game._starling.drone.nonfinite_count)
            game = step = None
    mean = {a: sum(x["game_steps_per_s"] for x in v) / len(v) for a, v in rows.items()}
    cost = 1.0 - mean["on"] / mean["off"] if "on" in mean else None
    return {"part": part, "world": getattr(world, "label", "none (tier 1, fitted response)"), "games": games,
            "size": f"{g}v{s}", "device": device, "arms": rows, "mean_game_steps_per_s": mean, "cost_fraction": cost,
            "on_arm": "not built: tier 1 gets the effects in L1.7" if part == "tier1" else info["on"],
            "off_arm": info["off"], "max_cost_fraction": run["max_cost_fraction"],
            "game_file": run["game_file"], "game_sha256": prov.game_sha256, "dry_cpu": dry_cpu,
            "timing": timing, "torch": torch.__version__, "machine": platform.node(),
            "gpu": torch.cuda.get_device_name(0) if device.startswith("cuda") else None}


# ================================================================================================ children
def isaac_world_factory(params, device: str):
    def make(n: int, m: int):
        from svg_training.compat import isaaclab_232 as isaac
        sim = isaac.make_physics_sim(params.physics_dt_s, device)
        world = isaac.IsaacWorld(sim, n, m, params.airframe, params.physics_dt_s)
        isaac.physics_play(sim, world)
        return world
    return make


def torch_world_factory(params, device: str):
    def make(n: int, m: int):
        from svg_training.models.rigid_body import TorchRigidBodyWorld
        return TorchRigidBodyWorld(n, m, params.airframe, params.physics_dt_s, device)
    return make


def _base_params():
    from svg_training.models.physics_params import load_physics_drone_params
    return load_physics_drone_params(load_settings()["run"]["params_base"])


def run_child(args) -> int:
    settings = load_settings()
    device = "cpu" if args.dry_cpu else args.device_name
    p = _base_params()
    if args.child == "tier2_isaac" and not args.dry_cpu:      # --dry-cpu: the torch world stands in
        factory = isaac_world_factory(p, device)
    else:
        factory = torch_world_factory(p, device)
    row = measure_part(args.child, settings, args.run_dir, device, args.dry_cpu, factory)
    row["pid"] = os.getpid()
    write_json(args.run_dir / POINTS_DIR / f"{args.child}.json", row)
    say(f"{args.child}: " + ", ".join(f"{a} {v:,.0f}" for a, v in row["mean_game_steps_per_s"].items()) +
        (f" game-steps/s, cost {row['cost_fraction']:.3f}" if row["cost_fraction"] is not None else " game-steps/s"))
    return 0


def smoke_checks(iw, tw, p, device) -> dict:
    """The smoke's checks (``[smoke]``) on the world under test ``iw`` (IsaacWorld in --smoke; a second torch world in
    the CPU test), and the agreement flight on ``iw`` and the torch world ``tw`` (same size, same device)."""
    import torch
    s = load_settings()["smoke"]
    delay_steps = round(s["state_delay_s"] / p.physics_dt_s)
    return {"world": getattr(iw, "label", type(iw).__name__), "device": device, "games": iw.num_games,
            "drones": iw.drones,
            "delay": delay_check(iw, p, delay_steps, s["ticks"] // 4, device),
            "delay_torch": delay_check(tw, p, delay_steps, s["ticks"] // 4, device),
            "noise": noise_check(iw, p, s["noise_ticks"], device),
            "error": error_check(iw, p, s["error_ticks"], device, tau_s=s["error_tau_s"]),
            "hover": hover_check(iw, hover_params(p), s["hover_ticks"], device),
            "agreement": agreement(iw, tw, p, s["ticks"], s["step_m"], s["state_delay_s"], device),
            "torch": torch.__version__}


def run_smoke(args) -> int:
    """Isaac Lab already started: the checks on IsaacWorld, and the agreement flight on IsaacWorld and the torch
    world on the same device. Writes --out only (no run folder, no lock)."""
    s = load_settings()["smoke"]
    device = args.device_name
    p = _base_params()
    n, m = s["games"], 3
    iw = isaac_world_factory(p, device)(n, m)
    tw = torch_world_factory(p, device)(n, m)
    res = smoke_checks(iw, tw, p, device)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(res, indent=2) + "\n")
    say(f"smoke written: {args.out}")
    return 0


# ================================================================================================ parent
def _signal_group(proc: subprocess.Popen, number: int) -> None:
    try:
        os.killpg(proc.pid, number)           # the child's whole session: pytest's own Isaac children too
    except ProcessLookupError:
        pass


def _terminate(proc: subprocess.Popen) -> None:
    """Stop the child and everything it started (it runs in its own session): SIGTERM, then SIGKILL after
    KILL_WAIT_S. Isaac children of the isaac-marked tests are grandchildren: a signal to the child alone would leave
    them holding the GPU."""
    if proc.poll() is None:
        _signal_group(proc, signal.SIGTERM)
        try:
            proc.wait(KILL_WAIT_S)
        except subprocess.TimeoutExpired:
            _signal_group(proc, signal.SIGKILL)
            proc.wait()


def _run_watched(cmd: list[str], log: Path, env: dict, guard) -> tuple[int | None, str | None]:
    """Run cmd (output to log), polling the guard; (returncode, stop reason or None)."""
    with open(log, "a") as fh:
        fh.write(f"\n# {time.strftime('%Y-%m-%d %H:%M:%S')} {' '.join(cmd)}\n")
        fh.flush()
        proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
        while proc.poll() is None:
            reason = guard.stop_reason()
            if reason:
                _terminate(proc)
                return None, reason
            time.sleep(POLL_S)
    return proc.returncode, None


def _tail(path: Path, lines: int = 3) -> str:
    text = path.read_text(errors="replace").strip().splitlines() if path.is_file() else []
    return "\n".join(text[-lines:])


def write_results(run_dir: Path, stopped: str | None) -> dict:
    pts = {p: json.loads((run_dir / POINTS_DIR / f"{p}.json").read_text())
           for p in PARTS if (run_dir / POINTS_DIR / f"{p}.json").is_file()}
    res = {"parts": pts, "stopped": stopped, "settings": str(SETTINGS.relative_to(ROOT)),
           "settings_text": SETTINGS.read_text()}
    write_json(run_dir / "results.json", res)
    lines = ["Simulator: training simulator, tier 2 (Isaac Lab physics drone and its PyTorch twin) and tier 1. Observed "
             "in the training simulator; not a flight result.", "", "# L1.1 / L1.2 model check", ""]
    t = pts.get("isaac_tests")
    lines.append(f"Isaac-marked tests: {'exit ' + str(t['returncode']) + ': ' + t['last_line'] if t else 'not run'}.")
    lines += ["", "| Part | World | Games | Off game-steps/s | On game-steps/s | Cost | Budget |", "|---|---|---|---|---|---|---|"]
    for p in PARTS[1:]:
        r = pts.get(p)
        if not r or r.get("status") == "crashed":
            lines.append(f"| {p} | {'crashed (exit ' + str(r['returncode']) + ', see ' + p + '.log)' if r else 'not run'}"
                         " | | | | | |")
            continue
        mean = r["mean_game_steps_per_s"]
        on = f"{mean['on']:,.0f}" if "on" in mean else "not built (L1.7)"
        cost = f"{100 * r['cost_fraction']:.1f} %" if r["cost_fraction"] is not None else "—"
        lines.append(f"| {p} | {r['world']} | {r['games']:,} | {mean['off']:,.0f} | {on} | {cost} | "
                     f"{100 * r['max_cost_fraction']:.0f} % (INFO) |")
    lines += ["", f"Stopped: {stopped or 'no'}.", ""]
    (run_dir / "results.md").write_text("\n".join(lines))
    return res


def run_parent(args) -> int:
    from svg_training.ste.run_contract import (EXIT_CONTROL_FAILED, EXIT_DONE, EXIT_FOR_STOP, EXIT_REFUSED, RunBusyError,
                                               RunGuard)
    if args.cap_h is None or not (math.isfinite(args.cap_h) and args.cap_h > 0):
        print(f"refused: --cap-h must be a finite number of hours above 0, got {args.cap_h!r}", file=sys.stderr)
        return EXIT_REFUSED
    if not args.dry_cpu and not args.headless:
        print("refused: tier 2 starts Isaac Lab: --headless", file=sys.stderr)
        return EXIT_REFUSED
    job_file = args.run_dir / "job.json"
    if job_file.is_file() and not args.dry_cpu:
        job = json.loads(job_file.read_text())
        if abs(float(job.get("gpu_h", 0)) - args.cap_h) > 1e-9:
            print(f"refused: the launcher asked for {job.get('gpu_h')} GPU-h, --cap-h is {args.cap_h}: keep the two "
                  "equal", file=sys.stderr)
            return EXIT_REFUSED
    (args.run_dir / POINTS_DIR).mkdir(parents=True, exist_ok=True)
    tests_failed = False
    try:
        with RunGuard(args.run_dir, cap_s=args.cap_h * HOUR_S) as guard:
            resumed = guard.load_latest()                  # carries the run folder's effective seconds (one cap)
            step = resumed.step if resumed else 0

            def stop(reason: str) -> int:
                guard.save(step, {"parts_done": step})
                write_results(args.run_dir, reason)
                return EXIT_FOR_STOP[reason]

            for part in PARTS:
                out = args.run_dir / POINTS_DIR / f"{part}.json"
                if out.is_file():
                    tests_failed |= part == "isaac_tests" and json.loads(out.read_text())["returncode"] != 0
                    continue
                reason = guard.stop_reason()
                if reason:
                    return stop(reason)
                env = dict(os.environ, PYTHONPATH=str(ROOT / "source"))
                if args.dry_cpu:
                    env["CUDA_VISIBLE_DEVICES"] = ""
                if part == "isaac_tests":
                    if args.dry_cpu:
                        write_json(out, {"returncode": 0, "last_line": "skipped: --dry-cpu", "dry_cpu": True})
                        continue
                    env["SVG_ISAAC_TESTS"] = "1"
                    log = args.run_dir / "isaac_tests.log"
                    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-m", "isaac",
                           *ISAAC_TEST_FILES]
                    say("isaac-marked tests ...")
                    code, reason = _run_watched(cmd, log, env, guard)
                    if reason:
                        return stop(reason)
                    write_json(out, {"returncode": code, "last_line": _tail(log, 1), "files": list(ISAAC_TEST_FILES)})
                    tests_failed |= code != 0
                    say(f"isaac-marked tests: exit {code}: {_tail(log, 1)}")
                    step += 1
                    guard.save(step, {"parts_done": step})
                    continue
                cmd = [sys.executable, str(Path(__file__).resolve()), "--run-dir", str(args.run_dir), "--child", part]
                if args.dry_cpu:
                    cmd.append("--dry-cpu")
                if part == "tier2_isaac" and not args.dry_cpu:
                    cmd.append("--headless")
                say(f"{part} ...")
                code, reason = _run_watched(cmd, args.run_dir / f"{part}.log", env, guard)
                if reason:
                    return stop(reason)
                if code != 0 or not out.is_file():
                    write_json(out, {"part": part, "status": "crashed", "returncode": code,
                                     "log_tail": _tail(args.run_dir / f"{part}.log", 30), "mean_game_steps_per_s": {},
                                     "cost_fraction": None})
                step += 1
                guard.save(step, {"parts_done": step})
            res = write_results(args.run_dir, None)
    except RunBusyError as e:
        print(f"refused: {e}", file=sys.stderr)
        return EXIT_REFUSED
    crashed = [p for p, r in res["parts"].items() if r.get("status") == "crashed"]
    say("done" + (f"; crashed parts: {crashed}" if crashed else "") + (", isaac tests FAILED" if tests_failed else ""))
    return EXIT_CONTROL_FAILED if tests_failed else (1 if crashed else EXIT_DONE)


# ================================================================================================ entry
def parser(isaac: bool = False) -> argparse.ArgumentParser:
    """The command line; ``isaac`` leaves out --headless and --device (Isaac Lab's launcher adds its own)."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-dir", type=Path)
    ap.add_argument("--cap-h", type=float, help="cap in effective hours (= the launcher's --gpu-h)")
    ap.add_argument("--dry-cpu", action="store_true", help="tests only: CPU, the torch world, no Isaac tests")
    ap.add_argument("--child", choices=PARTS[1:], help=argparse.SUPPRESS)
    ap.add_argument("--smoke", action="store_true", help="the isaac test's run: both worlds, writes --out only")
    ap.add_argument("--out", help="--smoke: the JSON to write")
    if not isaac:
        ap.add_argument("--headless", action="store_true", help="required for anything that starts Isaac Lab")
    return ap


def _needs_isaac(argv: list[str]) -> bool:
    return "--smoke" in argv or ("--child" in argv and "tier2_isaac" in argv and "--dry-cpu" not in argv)


def _isaac_main() -> int:
    """Isaac Sim starts headless before torch is imported; the process leaves through os._exit."""
    code = 1
    try:
        from _isaac_app import start_headless
        args, _app = start_headless(parser(isaac=True))
        args.device_name = getattr(args, "device", None) or "cuda:0"
        if args.smoke:
            if not args.out:
                print("refused: --smoke needs --out", file=sys.stderr)
                code = 2
            else:
                code = run_smoke(args)
        else:
            args.run_dir = args.run_dir.resolve()
            code = run_child(args)
    except KeyboardInterrupt:
        code = 4
    except SystemExit as ex:
        code = ex.code if isinstance(ex.code, int) else 2
    except BaseException:  # noqa: BLE001  (the parent reads the log)
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)          # never simulation_app.close() (it swallows exit codes)
    return code


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.run_dir is None:
        print("refused: --run-dir is needed (or --smoke --headless --out <file>)", file=sys.stderr)
        return 2
    args.run_dir = args.run_dir.resolve()
    if (ROOT / "runs").resolve() not in args.run_dir.parents:
        print(f"refused: {args.run_dir} is not under {ROOT / 'runs'}", file=sys.stderr)
        return 2
    if args.child:
        args.device_name = "cpu" if args.dry_cpu else "cuda:0"
        return run_child(args)
    return run_parent(args)


if __name__ == "__main__":
    if _needs_isaac(sys.argv[1:]):
        if "--headless" not in sys.argv[1:]:
            print("refused: this starts Isaac Lab: --headless", file=sys.stderr)
            sys.exit(2)
        _isaac_main()
    sys.exit(main())
