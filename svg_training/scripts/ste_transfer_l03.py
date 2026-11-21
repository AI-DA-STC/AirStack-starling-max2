#!/usr/bin/env python
"""STE task L0.3 STE Guard policy in tier 2 without retraining (INFO; PLAN.md section 4, DISCUSSION P3): T41's hold
rate against S20 on the Isaac Lab physics drone (Phase 4 row 6), on T41's own 1,000 paired starts, beside tier 1 and the
parked Guard. The games and checks: ``source/svg_training/ste/transfer.py``; settings: ``configs/ste_l03/gates.toml``.

Two parts, two run folders, two jobs (the CPU part holds no GPU time):

    # part 1, CPU (control C-1 and the tier 1 arm the tier 2 games are paired with):
    scripts/ste_job.py launch --task L0.3 --name ste_l03_cpu --run-dir runs/<date>_ste_l03_cpu --min-s 300 --gpu-h 0 -- \\
        <python> scripts/ste_transfer_l03.py --part cpu --run-dir runs/<date>_ste_l03_cpu --cap-h 1.0
    # part 2, GPU, alone, after nvidia-smi and scripts/isaac_preflight.sh --approved-headless (exit 0):
    scripts/ste_job.py launch --task L0.3 --name ste_l03_isaac --run-dir runs/<date>_ste_l03_transfer --min-s 600 \\
        --gpu-h 1.5 -- <python> scripts/ste_transfer_l03.py --part isaac --run-dir runs/<date>_ste_l03_transfer \\
        --cpu-run runs/<date>_ste_l03_cpu --cap-h 1.5 --headless
    ste_transfer_l03.py --part record --run-dir runs/<date>_ste_l03_transfer --cpu-run runs/<date>_ste_l03_cpu

Part "cpu": arm t1_cpu_t41 (T41 v S20, row 5, CPU, 4 threads) and control C-1 (T45's 831 holds and every outcome).
Part "isaac" refuses unless C-1 passed in the CPU run folder; then one Isaac world of 1,000 games x 6 drones: C-0 (the
two games differ only in the drone), C-3 (Isaac against the PyTorch reference world, 64 games x 20 ticks), arm t2_parked
and C-2 (ParkedGuard v S20 through T24's path, reaches in T24's band), arm t2_t41 (the result), arm t1_cuda_t41 (INFO:
tier 1 on this GPU against T41's 829), the 2-D clips of every arm (``videos/``; 3-D clips: VID-1, pending; the key games
for it are listed), then ``results.json`` and ``results.md``.

Run contract (``ste/run_contract.py``): the same command resumes (finished arms are files ``arms/<arm>.json`` + ``.npz``);
SIGINT or SIGTERM stops before the next tick, discards the unfinished arm and exits 4; the cap (effective hours = --cap-h)
exits 3. Exit codes: 0 done; 2 refused (gate file or a pinned file changed, cap mismatch, no --headless, C-1 not passed,
run folder busy); 3 cap; 4 stopped; 5 a non-finite action; 6 CONTROL_FAILED (terminal; a new run needs a new folder).
Observed in the training simulator; nothing here is a flight result."""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

HOUR_S = 3600.0
GATES_COPY = "gates.toml"
PINNED_SHA = "gates.sha256"
ARMS = "arms"
CONTROLS_FILE = "controls.json"
TERMINAL_FILE = "terminal.json"   # written at exit 5: the run folder is ABORTED for good (LEAD CALL QC L02-3)
INFO_FILE = "info.json"           # INFO comparisons (C-3b), never controls
REQUIRED_CONTROLS = ("C-0", "C-1", "C-2", "C-3")   # every record needs all four (LEAD CALL QC L02-6)
CPU_ARM = "t1_cpu_t41"
GPU_ARMS = ("t2_parked", "t2_t41", "t1_cuda_t41")


def say(text: str) -> None:
    print(f"[l03] {text}", flush=True)


def parser(isaac: bool = False) -> argparse.ArgumentParser:
    """The command line; ``isaac`` leaves out --headless (Isaac Lab's launcher adds its own, with --device)."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--part", choices=("cpu", "isaac", "record"), required=True)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--cpu-run", type=Path, help="part isaac / record: the CPU part's run folder")
    ap.add_argument("--gates", type=Path, default=None)
    ap.add_argument("--cap-h", type=float)
    if not isaac:
        ap.add_argument("--headless", action="store_true")
    ap.add_argument("--dry-cpu", action="store_true", help="tests only: part isaac on the CPU, PyTorch reference world as "
                    "the physics world; never of record")
    ap.add_argument("--games", type=int, help="tests only: fewer games (stamped; the controls' known answers then "
                    "do not apply and are reported as not checked)")
    ap.add_argument("--max-steps", type=int, help="tests only: cap the ticks per arm (stamped)")
    return ap


def refuse(text: str) -> int:
    print(f"refused: {text}", file=sys.stderr, flush=True)
    return 2


def write_json(path: Path, obj) -> None:
    from svg_training.ste import atomic
    atomic.write_text(path, json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def smoke(args) -> bool:
    return bool(args.dry_cpu or args.games or args.max_steps)


# ================================================================================================ shared steps
def load_and_pin(args, part_cap_key: str):
    """(gates, reason to refuse or None): the run folder's copy if pinned, else --gates / the committed file; the
    pins, the cap and the job's hours checked."""
    from svg_training.ste import transfer as T
    src = args.run_dir / GATES_COPY if (args.run_dir / GATES_COPY).is_file() else (args.gates or T.GATES_FILE)
    try:
        gates = T.load_gates(src)
    except (OSError, ValueError) as err:
        return None, f"gate file {src}: {err}"
    pinned = args.run_dir / PINNED_SHA
    if args.gates is not None and pinned.is_file() and T.sha256_file(args.gates) != pinned.read_text().strip():
        return None, "--gates differs from the run folder's pinned copy: a new limit means a new run folder"
    problems = T.pin_problems(gates)
    if problems:
        return None, "pinned files differ: " + "; ".join(problems)
    if args.cap_h is None or not (math.isfinite(args.cap_h) and args.cap_h > 0):
        return None, f"--cap-h must be a finite number of hours above 0, got {args.cap_h!r}"
    if not smoke(args) and abs(args.cap_h - float(gates["run"][part_cap_key])) > 1e-9:
        return None, f"--cap-h {args.cap_h} differs from the gate file's [run] {part_cap_key} {gates['run'][part_cap_key]}"
    job = args.run_dir / "job.json"
    if job.is_file():
        asked = float(json.loads(job.read_text()).get("gpu_h", 0))
        want = 0.0 if part_cap_key == "cpu_cap_h" else args.cap_h
        if abs(asked - want) > 1e-9:
            return None, f"the launcher asked for {asked} GPU-h; this part needs {want}"
    return gates, None


def first_pin(args, gates) -> None:
    from svg_training.ste import atomic
    if not (args.run_dir / PINNED_SHA).is_file():
        args.run_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(gates["path"], args.run_dir / GATES_COPY)
        atomic.write_text(args.run_dir / PINNED_SHA, gates["sha256"] + "\n")


def read_controls(run_dir: Path) -> dict:
    f = run_dir / CONTROLS_FILE
    return json.loads(f.read_text()) if f.is_file() else {}


def save_control(run_dir: Path, name: str, result: dict) -> dict:
    c = read_controls(run_dir)
    c[name] = result
    write_json(run_dir / CONTROLS_FILE, c)
    say(f"control {name}: {'PASS' if result['pass'] else 'FAIL'} {json.dumps({k: v for k, v in result.items() if k != 'pass'}, default=str)[:300]}")
    return c


def failed(run_dir: Path) -> list[str]:
    return [k for k, v in read_controls(run_dir).items() if not v.get("pass", False) and not v.get("not_checked")]


def control_summary(controls: dict) -> dict:
    """Every required control present and passed (a smoke run's "not checked" counts as present)."""
    missing = [c for c in REQUIRED_CONTROLS if c not in controls]
    bad = [k for k, v in controls.items() if not v.get("pass", False)]
    return {"controls_all_pass": not missing and not bad, "controls_missing": missing, "controls_failed": bad}


def terminal(run_dir: Path | None) -> dict | None:
    f = None if run_dir is None else run_dir / TERMINAL_FILE
    return json.loads(f.read_text()) if f is not None and f.is_file() else None


def mark_terminal(run_dir: Path, why: str) -> None:
    write_json(run_dir / TERMINAL_FILE, {"exit": 5, "why": why, "time": time.time()})


def save_info(run_dir: Path, name: str, result: dict) -> None:
    f = run_dir / INFO_FILE
    info = json.loads(f.read_text()) if f.is_file() else {}
    info[name] = result
    write_json(f, info)


def save_arm(run_dir: Path, name: str, res, extras, meta: dict, team: str = "guard") -> dict:
    import numpy as np

    from svg_training.ste import transfer as T
    pg = T.per_game(res)
    folder = run_dir / ARMS
    folder.mkdir(parents=True, exist_ok=True)
    np.savez(folder / f"{name}.npz", **pg)
    video = extras.get("video") if isinstance(extras, dict) else None
    if video is not None:
        np.savez(folder / f"{name}__video.npz", video=video.numpy(), outcome=pg["outcome"], end_step=pg["end_step"],
                 closest_cross_m=pg["closest_cross_m"], steps_played=int(res.steps_played))
    out = {"arm": name, **meta, "summary": T.summary(pg, team), "steps_played": int(res.steps_played)}
    write_json(folder / f"{name}.json", out)
    s = out["summary"]
    say(f"arm {name}: {s['count']} {s['counted']} of {s['games']} (Wilson {s['ci']}), {meta.get('seconds', 0):.0f} s")
    return out


def arm_done(run_dir: Path, name: str) -> bool:
    return (run_dir / ARMS / f"{name}.json").is_file() and (run_dir / ARMS / f"{name}.npz").is_file()


def machine(device: str) -> dict:
    import torch
    return {"machine": platform.node(), "device": device, "torch": torch.__version__, "threads": torch.get_num_threads(),
            "gpu": torch.cuda.get_device_name(0) if device.startswith("cuda") and torch.cuda.is_available() else None,
            "commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain", "--", "."))}


# ================================================================================================ part cpu
def part_cpu(args) -> int:
    import torch

    from svg_training.ste import transfer as T
    from svg_training.ste.run_contract import (EXIT_CONTROL_FAILED, EXIT_DONE, EXIT_FOR_STOP, EXIT_NONFINITE,
                                               RunBusyError, RunGuard)
    gates, why = load_and_pin(args, "cpu_cap_h")
    if why:
        return refuse(why)
    if terminal(args.run_dir):
        return refuse(f"this run folder ended with a non-finite value ({TERMINAL_FILE}): ABORTED; a new run needs a new folder")
    if failed(args.run_dir):
        return EXIT_CONTROL_FAILED
    torch.set_num_threads(int(gates["run"]["threads"]))
    try:
        with RunGuard(args.run_dir, cap_s=args.cap_h * HOUR_S) as guard:
            first_pin(args, gates)
            guard.load_latest()
            if not arm_done(args.run_dir, CPU_ARM):
                w5, _ = T.worlds(gates)
                t0 = time.perf_counter()
                try:
                    res, extras = T.play_t41(gates, w5, "cpu", games=args.games, max_steps=args.max_steps,
                                             should_stop=lambda: guard.stop_reason() is not None)
                except T.Stopped:
                    reason = guard.stop_reason()
                    guard.save(0, {"done": []})
                    return EXIT_FOR_STOP[reason]
                out = save_arm(args.run_dir, CPU_ARM, res, extras, {"tier": 1, "row": gates["run"]["fitted_row"],
                                                                    "smoke": smoke(args), "seconds": time.perf_counter() - t0,
                                                                    **machine("cpu")})
                guard.save(1, {"done": [CPU_ARM]})
                if out["summary"]["nonfinite_actions"]:
                    mark_terminal(args.run_dir, f"{CPU_ARM}: non-finite actions")
                    return EXIT_NONFINITE
            import numpy as np
            pg = dict(np.load(args.run_dir / ARMS / f"{CPU_ARM}.npz"))
            if smoke(args):
                save_control(args.run_dir, "C-1", {"pass": True, "not_checked": "smoke run: fewer games or ticks"})
            else:
                save_control(args.run_dir, "C-1", T.check_t45(gates, pg))
            return EXIT_CONTROL_FAILED if failed(args.run_dir) else EXIT_DONE
    except RunBusyError as err:
        return refuse(str(err))


# ================================================================================================ part isaac
def isaac_world_factory(n: int, m: int, params, device: str):
    from svg_training.compat import isaaclab_232 as isaac
    sim = isaac.make_physics_sim(params.physics_dt_s, device)
    world = isaac.IsaacWorld(sim, n, m, params.airframe, params.physics_dt_s)
    isaac.physics_play(sim, world)
    return world


def torch_world_factory(n: int, m: int, params, device: str):
    from svg_training.models.rigid_body import TorchRigidBodyWorld
    return TorchRigidBodyWorld(n, m, params.airframe, params.physics_dt_s, device)


def part_isaac(args, world_factory=isaac_world_factory) -> int:
    import torch

    from svg_training.core.physics_layer import load_game_physics_params
    from svg_training.ste import transfer as T
    from svg_training.ste.run_contract import (EXIT_CONTROL_FAILED, EXIT_DONE, EXIT_FOR_STOP, EXIT_NONFINITE,
                                               RunBusyError, RunGuard)
    gates, why = load_and_pin(args, "cap_h")
    if why:
        return refuse(why)
    if not (args.headless or args.dry_cpu):
        return refuse("part isaac starts Isaac Lab: add --headless (after scripts/isaac_preflight.sh --approved-headless)")
    if args.cpu_run is None or not arm_done(args.cpu_run, CPU_ARM):
        return refuse("give --cpu-run, the CPU part's finished run folder (arm t1_cpu_t41)")
    c1 = read_controls(args.cpu_run).get("C-1", {})
    if not c1.get("pass") or (c1.get("not_checked") and not smoke(args)):
        return refuse(f"control C-1 has not passed in {args.cpu_run}: the CPU path must reproduce T45 first")
    if (args.cpu_run / PINNED_SHA).read_text().strip() != gates["sha256"]:
        return refuse("the CPU part ran another gate file")
    if terminal(args.run_dir) or terminal(args.cpu_run):
        return refuse(f"a run folder ended with a non-finite value ({TERMINAL_FILE}): ABORTED; a new run needs a new folder")
    if failed(args.run_dir):
        return EXIT_CONTROL_FAILED
    device = "cpu" if args.dry_cpu else gates["run"]["device"]
    if device.startswith("cuda") and not torch.cuda.is_available():
        return refuse("the gate file plays on cuda and PyTorch sees no GPU")
    torch.set_num_threads(int(gates["run"]["threads"]))
    n = int(args.games or gates["run"]["games"])
    try:
        with RunGuard(args.run_dir, cap_s=args.cap_h * HOUR_S) as guard:
            first_pin(args, gates)
            guard.load_latest()
            stop = lambda: guard.stop_reason() is not None               # noqa: E731
            w5, w6 = T.worlds(gates)
            controls = read_controls(args.run_dir)
            if "C-0" not in controls:
                save_control(args.run_dir, "C-0", T.check_rows(gates, w5, w6))
                if failed(args.run_dir):
                    return EXIT_CONTROL_FAILED
            t0 = time.perf_counter()
            physics = world_factory(n, w6.guards + w6.strikes, load_game_physics_params(w6.cfg), device)
            say(f"world: {type(physics).__name__} of {n} games x {w6.guards + w6.strikes} drones ({time.perf_counter() - t0:.0f} s)")
            done = []
            try:
                if "C-3" not in read_controls(args.run_dir):
                    c3, c3b = T.agreement(gates, w6, device, physics, torch_world_factory, games=n)
                    save_info(args.run_dir, "C-3b", c3b)
                    save_control(args.run_dir, "C-3", c3)
                    if failed(args.run_dir):
                        return EXIT_CONTROL_FAILED
                for arm in GPU_ARMS:
                    if not arm_done(args.run_dir, arm):
                        t0 = time.perf_counter()
                        if arm == "t2_parked":
                            res, extras = T.play_parked(gates, w6, device, physics, games=n, should_stop=stop,
                                                        max_steps=args.max_steps)
                            team = "strike"
                        elif arm == "t2_t41":
                            res, extras = T.play_t41(gates, w6, device, physics, games=n, max_steps=args.max_steps,
                                                     should_stop=stop)
                            team = "guard"
                        else:
                            res, extras = T.play_t41(gates, w5, device, None, games=n, max_steps=args.max_steps,
                                                     should_stop=stop)
                            team = "guard"
                        if device.startswith("cuda"):
                            torch.cuda.synchronize()
                        seconds = time.perf_counter() - t0
                        meta = {"tier": 1 if arm.startswith("t1") else 2,
                                "row": gates["run"]["fitted_row" if arm.startswith("t1") else "physics_row"],
                                "smoke": smoke(args), "seconds": seconds,
                                "game_steps_per_s": n * int(res.steps_played) / seconds if seconds > 0 else None,
                                "world": type(physics).__name__ if arm.startswith("t2") else None, **machine(device)}
                        save_arm(args.run_dir, arm, res, extras, meta, team)
                    done.append(arm)
                    guard.save(len(done), {"done": done})
                    if arm == "t2_parked" and "C-2" not in read_controls(args.run_dir):   # also on a resume
                        import numpy as np
                        pg = dict(np.load(args.run_dir / ARMS / f"{arm}.npz"))
                        result = T.check_parked(gates, pg) if not smoke(args) else {"pass": True, "not_checked": "smoke run"}
                        save_control(args.run_dir, "C-2", result)
                    out = json.loads((args.run_dir / ARMS / f"{arm}.json").read_text())
                    if out["summary"]["nonfinite_actions"]:          # after C-2, so exit 5 never skips it
                        mark_terminal(args.run_dir, f"{arm}: non-finite actions")
                        write_results(args, gates, stopped="nonfinite")
                        return EXIT_NONFINITE
                    if failed(args.run_dir):
                        write_results(args, gates, stopped="control_failed")
                        return EXIT_CONTROL_FAILED
            except T.Stopped:
                reason = guard.stop_reason()
                guard.save(len(done), {"done": done})
                write_results(args, gates, stopped=reason)
                return EXIT_FOR_STOP[reason]
            write_results(args, gates, stopped=None, clips=True)
            return EXIT_DONE
    except RunBusyError as err:
        return refuse(str(err))


# ================================================================================================ results and clips
def make_clips(args, gates, w5, w6) -> list[str]:
    """2-D top-down clips (STANDARDS section 8) of every arm from its kept video slots (``nus/pilot`` path: first hold,
    first Strike win), MP4 in ``videos/``."""
    import numpy as np
    import torch

    from svg_training.core.play import MatchResult
    from svg_training.nus import pilot as P
    out = []
    for run, arm, world, g_name in ((args.cpu_run, CPU_ARM, w5, "T41"), (args.run_dir, "t2_t41", w6, "T41"),
                                    (args.run_dir, "t2_parked", w6, gates["controls"]["parked_guard"]),
                                    (args.run_dir, "t1_cuda_t41", w5, "T41")):
        f = run / ARMS / f"{arm}__video.npz"
        if not f.is_file():
            out.append(f"{arm}: no kept video slots")
            continue
        d = np.load(f)
        k = d["video"].shape[1]
        t = lambda a: torch.from_numpy(np.asarray(a)[:k])                # noqa: E731
        z = torch.zeros(k)
        res = MatchResult(t(d["outcome"]), t(d["end_step"]), z.long(), t(d["closest_cross_m"]), z, z.bool(), z, z.bool(),
                          steps_played=int(d["steps_played"]))
        clips = P.eval_clips(res, {"video": torch.from_numpy(d["video"])}, world)
        paths = P.render_clips(clips, args.run_dir / "videos", arm, int(gates["clips"]["per_arm"]), world, g_name,
                               gates["run"]["opponent"], int(gates["run"]["eval_seed"]))
        out += [f"videos/{p.name}" for p in paths]
    return out


def write_results(args, gates, stopped: str | None, clips: bool = False) -> dict:
    import numpy as np

    from svg_training.ste import transfer as T
    arms = {}
    for run, arm in ((args.cpu_run, CPU_ARM), *((args.run_dir, a) for a in GPU_ARMS)):
        if run is not None and arm_done(run, arm):
            arms[arm] = {"meta": json.loads((run / ARMS / f"{arm}.json").read_text()),
                         "outcome": np.load(run / ARMS / f"{arm}.npz")["outcome"]}
    res = {"task": "L0.3", "verdict": gates["run"]["verdict"], "stopped": stopped, "gates_sha256": gates["sha256"],
           "smoke": smoke(args), "arms": {k: v["meta"] for k, v in arms.items()},
           "controls": {**(read_controls(args.cpu_run) if args.cpu_run else {}), **read_controls(args.run_dir)},
           "references": gates["references"]}
    res.update(control_summary(res["controls"]))
    res["info"] = json.loads((args.run_dir / INFO_FILE).read_text()) if (args.run_dir / INFO_FILE).is_file() else {}
    res["terminal"] = terminal(args.run_dir) or terminal(args.cpu_run)
    if res["terminal"]:
        res["controls_all_pass"] = False
    if CPU_ARM in arms and "t2_t41" in arms:
        res["t2_v_t1_cpu"] = T.paired(arms[CPU_ARM]["outcome"], arms["t2_t41"]["outcome"])
        key = (res["t2_v_t1_cpu"]["lost_slots"][: int(gates["clips"]["key_games"]) // 2]
               + res["t2_v_t1_cpu"]["gained_slots"][: int(gates["clips"]["key_games"]) // 2])
        res["vid1_key_games"] = {"arm": "t2_t41 against t1_cpu_t41", "slots": key,
                                 "note": "3-D Isaac Lab clips (VID-1) pending: these paired starts first"}
    if "t1_cuda_t41" in arms and CPU_ARM in arms:
        res["t1_cuda_v_t1_cpu"] = T.paired(arms[CPU_ARM]["outcome"], arms["t1_cuda_t41"]["outcome"])
    if clips:
        try:
            w5, w6 = T.worlds(gates)
            res["clips"] = make_clips(args, gates, w5, w6)
        except Exception as err:  # noqa: BLE001  (a clip must never lose the numbers)
            res["clips"] = [f"clips failed: {err!r}"]
    write_json(args.run_dir / "results.json", res)
    (args.run_dir / "results.md").write_text(render_md(res))
    return res


def render_md(res: dict) -> str:
    ref = res["references"]
    void = not res["controls_all_pass"]
    banner = (["**CONTROLS FAILED — rates void.** Failed: " + (", ".join(res.get("controls_failed", [])) or "none")
               + "; missing: " + (", ".join(res.get("controls_missing", [])) or "none")
               + (f"; terminal: {res['terminal']['why']}" if res.get("terminal") else "") + ". A diagnostic, not a result.", ""]
              if void else [])
    lines = ["# L0.3 STE Guard policy in tier 2 without retraining: results (INFO; observed in the training simulator)", "",
             *banner,
             ("**SMOKE (fewer games or ticks): not of record.** " if res["smoke"] else "")
             + f"Controls: {'every control PASS' if res['controls_all_pass'] else 'NOT ALL PASS'}; stopped: "
               f"{res['stopped'] or 'no (finished)'}.", "",
             "| Arm | Tier, row | Machine, device | Counted | k / n | Rate | Wilson 95 % | Closest 3-D min / median m | "
             "Filter share | Rule breach share | Upset games | game-steps/s |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    def f(v, fmt="{:.3f}"):
        return "n/a" if v is None else fmt.format(v)
    for name, m in res["arms"].items():
        s = m["summary"]
        ci = s["ci"] or [None, None]
        lines.append(f"| {name}{' (VOID)' if void else ''} | {m['tier']}, row {m['row']} | {m.get('gpu') or m['device']} | {s['counted']} | {s['count']} / "
                     f"{s['games']} | {f(s['rate'])} | [{f(ci[0])}, {f(ci[1])}] | {f(s['closest_3d_min_m'], '{:.2f}')} / "
                     f"{f(s['closest_3d_median_m'], '{:.2f}')} | {f(s['filter_share'])} | {f(s['rule_breach_share'])} | "
                     f"{s['upset_games']} | {f(m.get('game_steps_per_s'), '{:,.0f}')} |")
    lines += ["", f"References: T41 {ref['t41_holds']} / {ref['t41_games']} holds (tier 1, home RTX 5090); T24 parked "
                  f"Guard {ref['t24_parked_reaches']} reaches (row 6); T23 parked Guard {ref['t23_parked_holds']} holds "
                  f"(row 5).", ""]
    p = res.get("t2_v_t1_cpu")
    if p:
        lines.append(f"Tier 2 against tier 1 (CPU), paired by start: held in both {p['both_hold']}, lost on tier 2 "
                     f"{p['lost_here']}, gained on tier 2 {p['gained_here']}, lost in both {p['both_lost']}; sign test "
                     f"p = {p['sign_test_p']:.3g}.")
    q = res.get("t1_cuda_v_t1_cpu")
    if q:
        lines.append(f"Tier 1 on this GPU against tier 1 on the CPU: {q['outcomes_differ']} games differ.")
    lines += ["", "| Control | Result |", "|---|---|"]
    for k, v in res["controls"].items():
        lines.append(f"| {k} | {'not checked (' + v['not_checked'] + ')' if v.get('not_checked') else ('PASS' if v['pass'] else 'FAIL')}: "
                     f"{json.dumps({a: b for a, b in v.items() if a not in ('pass', 'not_checked')}, default=str)[:300]} |")
    for k, v in res.get("info", {}).items():
        lines.append(f"| {k} (INFO, not gated) | {json.dumps({a: b for a, b in v.items() if a != 'info'}, default=str)[:400]} |")
    lines += ["", "Clips: " + "; ".join(res.get("clips", ["not made yet"])) + ". 3-D clips: pending (VID-1); key games "
              f"{res.get('vid1_key_games', {}).get('slots', [])}.", ""]
    return "\n".join(lines)


# ================================================================================================ entry
def main(argv: list[str] | None = None, world_factory=isaac_world_factory) -> int:
    args = parser().parse_args(argv)
    return dispatch(args, world_factory)


def dispatch(args, world_factory=isaac_world_factory) -> int:
    args.run_dir = args.run_dir.resolve()
    if args.cpu_run is not None:
        args.cpu_run = args.cpu_run.resolve()
    runs = (ROOT / "runs").resolve()
    if runs not in args.run_dir.parents:
        return refuse(f"{args.run_dir} is not under {runs}")
    if args.part == "cpu":
        return part_cpu(args)
    if args.part == "record":
        from svg_training.ste import transfer as T
        old = args.run_dir / "results.json"
        before = json.loads(old.read_text()).get("stopped") if old.is_file() else "no results before --part record"
        write_results(args, T.load_gates(args.run_dir / GATES_COPY), stopped=before, clips=True)
        return 0
    if args.dry_cpu:
        return part_isaac(args, torch_world_factory)
    return part_isaac(args, world_factory)


def _isaac_cli() -> int:
    """Part isaac: Isaac Sim starts headless before torch is imported; Ctrl-C during the start exits 4 (QC L02-10)."""
    code = 1
    try:
        from _isaac_app import start_headless
        args, _app = start_headless(parser(isaac=True))
        code = dispatch(args)
    except KeyboardInterrupt:
        code = 4
    except SystemExit as ex:                      # start_headless refuses with SystemExit(2)
        code = ex.code if isinstance(ex.code, int) else 2
    except BaseException:  # noqa: BLE001
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)          # never simulation_app.close() (it swallows exit codes)
    return code


def pre_isaac_problem(argv: list[str]) -> str | None:
    """Standard library only, before Isaac Sim starts (CODING_PRACTICES section 8): the reason to refuse part isaac, or
    None. --headless, a --cpu-run whose control C-1 passed (or was not checked in a smoke run), no failed control in
    the run folder."""
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--run-dir", type=Path)
    pre.add_argument("--cpu-run", type=Path)
    pre.add_argument("--games", type=int)
    pre.add_argument("--max-steps", type=int)
    known, _ = pre.parse_known_args(argv)
    if "--headless" not in argv:
        return "part isaac starts Isaac Lab: --headless (after scripts/isaac_preflight.sh --approved-headless)"
    if known.cpu_run is None or not (known.cpu_run / CONTROLS_FILE).is_file():
        return "give --cpu-run, the CPU part's finished run folder"
    c1 = json.loads((known.cpu_run / CONTROLS_FILE).read_text()).get("C-1", {})
    if not c1.get("pass") or (c1.get("not_checked") and not (known.games or known.max_steps)):
        return f"control C-1 has not passed in {known.cpu_run}"
    for folder in (known.run_dir, known.cpu_run):
        if folder is not None and (folder / TERMINAL_FILE).is_file():
            return f"{folder} ended with a non-finite value ({TERMINAL_FILE}): ABORTED; a new run needs a new folder"
    if known.run_dir is not None and (known.run_dir / CONTROLS_FILE).is_file():
        bad = [k for k, v in json.loads((known.run_dir / CONTROLS_FILE).read_text()).items()
               if not v.get("pass", False)]
        if bad:
            return f"control(s) {bad} failed in {known.run_dir}: terminal, a new run needs a new folder"
    return None


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "isaac" in argv and "--dry-cpu" not in argv:
        problem = pre_isaac_problem(argv)
        if problem:
            print(f"refused: {problem}", file=sys.stderr)
            sys.exit(2)
        _isaac_cli()
    sys.exit(main())
