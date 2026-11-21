#!/usr/bin/env python
"""STE task L0.2 Tier 2 speed in contested play (INFO; PLAN.md section 4, DISCUSSION P3): game-steps per second on
tier 2 (Isaac Lab physics drone) and tier 1 (fitted Starling response), with a learner in the loop and both teams
playing, per team size and games at once; the largest games-at-once that fits the GPU. What is timed:
``source/svg_training/ste/speed.py`` (module docstring); the points, settings and controls: ``configs/ste_l02/gates.toml``.

    # after nvidia-smi and scripts/isaac_preflight.sh --approved-headless (exit 0), alone on the GPU:
    scripts/ste_job.py launch --task L0.2 --name ste_l02_speed --run-dir runs/<date>_ste_l02_speed --min-s 600 \\
        --gpu-h 1.5 -- <python> scripts/ste_speed_l02.py --run-dir runs/<date>_ste_l02_speed --cap-h 1.5 --headless
    ste_speed_l02.py --record-only --run-dir <run>      # results.json / results.md again from the point rows

One parent process (this command: no Isaac, no CUDA work) runs one CHILD process per point (``--child <id>``; an Isaac
world is n games x m drones for its whole process), in the gate file's run order, and keeps the run contract
(``ste/run_contract.py``): the same command resumes (finished points are the files ``points/<id>.json``); SIGINT or
SIGTERM stops the running child, discards its point and exits 4; the cap (effective hours = --cap-h) stops the child
and exits 3; before each point the unprotected points that would not fit the time left are cut from the end of the
run order (``cuts.json``). A child that runs out of GPU memory writes its row as "did_not_fit" (torch's error, or an
out-of-memory line in its log when it died without a row); any other death is "crashed", with its exit code and log
tail: the run carries on either way. Exit codes: 0 done; 2 refused (bad gate file, the gate or game file changed, cap or
device mismatch, no --headless with tier 2 points, run folder busy); 3 cap; 4 stopped on request; 5 a non-finite action
or loss; 6 CONTROL_FAILED (``[controls]`` or C-3: a protected point at its tier's smallest games did not run; terminal).

Videos (STANDARDS section 8): 2-D top-down clips of the ``[clips]`` points' own games in ``videos/`` (viz/replay.py
as on this branch: the height panel arrives with L0.12's replay change; 3-D clips: VID-1, pending). Observed in the
training simulator; nothing here is a flight result."""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import re
import shutil
import signal
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
POINTS_DIR = "points"
CONTROLS_FILE = "controls.json"
CUTS_FILE = "cuts.json"
POLL_S = 1.0
KILL_WAIT_S = 60.0
LOG_TAIL_LINES = 30
OOM_PATTERNS = (r"cuda out of memory", r"outofmemoryerror", r"cuda_error_out_of_memory", r"cudaerrormemoryallocation",
                r"out of (device|gpu) memory", r"pxg\w*memoryallocator\W.*fail")   # LEAD CALL QC L02-4: real CUDA / PhysX OOM only
TERMINAL_FILE = "terminal.json"    # written at exit 5: the run folder is ABORTED for good (LEAD CALL QC L02-3)
SUSPECT = "suspect"                # a row whose attempt log shows an allocation failure (PhysX may print it without raising)
CRASHED = "crashed"
EXIT_CHILD_OOM_NO_ROW = 7          # child only: never a job's exit code (the parent maps it to a did_not_fit row)


def say(text: str) -> None:
    print(f"[l02] {text}", flush=True)


def parser(isaac: bool = False) -> argparse.ArgumentParser:
    """The command line; ``isaac`` leaves out --headless (Isaac Lab's launcher adds its own, with --device)."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--gates", type=Path, default=None, help="gate file (default configs/ste_l02/gates.toml; a resume "
                    "reads the run folder's copy)")
    ap.add_argument("--cap-h", type=float, help="cap in effective hours (= the launcher's --gpu-h = [run] cap_h)")
    ap.add_argument("--child", help=argparse.SUPPRESS)                     # one point, in its own process
    ap.add_argument("--dry-cpu", action="store_true", help="tests only: CPU, tier 2 on the PyTorch reference world, "
                    "never a run of record")
    ap.add_argument("--record-only", action="store_true", help="rewrite results.json / results.md from the rows")
    ap.add_argument("--allow-code-change", action="store_true",
                    help="resume although the code differs from the first launch's (recorded in code.json)")
    if not isaac:
        ap.add_argument("--headless", action="store_true", help="required when a tier 2 point is planned (Isaac Lab)")
    return ap


def refuse(text: str) -> int:
    from svg_training.ste.run_contract import EXIT_REFUSED
    print(f"refused: {text}", file=sys.stderr, flush=True)
    return EXIT_REFUSED


def write_json(path: Path, obj) -> None:
    from svg_training.ste import atomic
    atomic.write_text(path, json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


# ================================================================================================ the child: one point
def nvidia_smi_mib(pid: int) -> dict:
    """This process's used GPU memory (MiB, as nvidia-smi lists it: PhysX's buffers included) and the GPU's used and
    total memory; None where nvidia-smi is missing or does not list the process."""
    out = {"process_mib": None, "gpu_used_mib": None, "gpu_total_mib": None}
    try:
        apps = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True, timeout=30).stdout
        for line in apps.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) == 2 and parts[0] == str(pid):
                out["process_mib"] = float(parts[1])
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=30).stdout.splitlines()
        if gpu:
            used, total = (float(x) for x in gpu[0].split(","))
            out["gpu_used_mib"], out["gpu_total_mib"] = used, total
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return out


def isaac_world_factory(n: int, m: int, params, device: str):
    """IsaacWorld of n games x m drones (Isaac Sim already started), as scripts/train_standin.py."""
    from svg_training.compat import isaaclab_232 as isaac
    sim = isaac.make_physics_sim(params.physics_dt_s, device)
    world = isaac.IsaacWorld(sim, n, m, params.airframe, params.physics_dt_s)
    isaac.physics_play(sim, world)
    return world


def torch_world_factory(n: int, m: int, params, device: str):
    from svg_training.models.rigid_body import TorchRigidBodyWorld
    return TorchRigidBodyWorld(n, m, params.airframe, params.physics_dt_s, device)


def run_child(args: argparse.Namespace) -> int:
    """Measure one point and write ``points/<id>.json`` (status fit or did_not_fit). Exit 0 with a row, 5 when the row
    holds a non-finite action, 2 refused."""
    import torch

    from svg_training.ste import speed
    from svg_training.ste.run_contract import EXIT_DONE, EXIT_NONFINITE
    gates = speed.load_gates(args.run_dir / GATES_COPY)
    point = gates.point(args.child)
    device = "cpu" if args.dry_cpu else gates.run["device"]
    torch.set_num_threads(int(gates.run["threads"]))
    factory = torch_world_factory if args.dry_cpu else isaac_world_factory
    out = args.run_dir / POINTS_DIR / f"{point.id}.json"
    t0 = time.time()

    def clips(game, cfg, p):
        if p.id not in gates.clips["points"]:
            return []
        return make_clips(gates, game, cfg, p, device, args.run_dir)

    try:
        row = speed.run_point(gates, point, device, world_factory=factory,
                              torch_world_factory=torch_world_factory, clip_hook=clips)
    except torch.OutOfMemoryError as err:
        row = {"id": point.id, "tier": point.tier, "size": point.size, "games": point.games, "drones": point.drones,
               "status": speed.DID_NOT_FIT, "error": f"torch.OutOfMemoryError: {str(err).splitlines()[0]}",
               "device": device, "controls": {}}
    row["nvidia_smi"] = nvidia_smi_mib(os.getpid()) if device != "cpu" else None
    row.update({"pid": os.getpid(), "machine": platform.node(), "torch": torch.__version__,
                "process_s": time.time() - t0, "dry_cpu": bool(args.dry_cpu)})
    write_json(out, row)
    say(f"{point.id}: {row['status']}" + (f", train {row['learner']['train_game_steps_per_s']:.0f} game-steps/s, "
                                           f"reference {row['reference']['game_steps_per_s']:.0f}"
                                           if row["status"] == speed.FIT else ""))
    if nonfinite_in(row):
        return EXIT_NONFINITE
    return EXIT_DONE


def make_clips(gates, game, cfg, point, device: str, run_dir: Path) -> list[str]:
    """Record the clip games of a point (untimed) and render at most one hold and one reach as GIFs."""
    from svg_training.core.game_config import TICK_S
    from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
    from svg_training.ste import speed
    from svg_training.viz.replay import render_replay
    c = gates.clips
    recs = speed.record_clips(gates, game, cfg, point, device, int(gates.run["seed"]))
    out = []
    for kind, want in (("hold", GUARD_WIN), ("reach", STRIKE_WIN)):
        rec = next((r for r in recs if r.outcome == want), None)
        if rec is None:
            out.append(f"{point.id}: no {kind} among the first {c['games']} games within {c['max_ticks']} ticks")
            continue
        path = render_replay(rec, run_dir / "videos" / f"{point.id}_{kind}_game{rec.game_index}.gif",
                             speed=int(c["speed"]), fps=int(c["fps"]), dpi=int(c["dpi"]),
                             playback_label=f"{int(c['speed']) * int(c['fps']) * TICK_S:g}x real time")
        out.append(f"videos/{path.name}: {rec.guard_name} v {rec.strike_name}, {kind} at {rec.end_time_s:.1f} s")
    return out


# ================================================================================================ the parent
def nonfinite_in(row: dict) -> int:
    """Non-finite drone-steps a measured row reports: the learner's and the scripted reference's (QC L02-3)."""
    if "learner" not in row or "reference" not in row:      # a row with no measurement (did not fit, crashed)
        return 0                                              # QC R3: "suspect" rows are measured rows: read them
    return int(row["learner"].get("nonfinite", 0)) + int(row["reference"].get("nonfinite", 0))


def attempt_log(run_dir: Path, pid: str) -> Path:
    """The latest attempt's log of a point (``points/<id>.attempt<k>.log``); attempt 1 when none exists."""
    folder = run_dir / POINTS_DIR
    have = sorted(folder.glob(f"{pid}.attempt*.log"), key=lambda f: int(f.stem.rsplit("attempt", 1)[1]))
    return have[-1] if have else folder / f"{pid}.attempt1.log"


def new_attempt_log(run_dir: Path, pid: str) -> Path:
    """A fresh log for this attempt (earlier attempts' lines never classify this one: QC L02-4)."""
    last = attempt_log(run_dir, pid)
    k = int(last.stem.rsplit("attempt", 1)[1]) + (1 if last.is_file() else 0)
    path = run_dir / POINTS_DIR / f"{pid}.attempt{k}.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


def child_command(args: argparse.Namespace, point) -> list[str]:
    cmd = [sys.executable, str(Path(__file__).resolve()), "--run-dir", str(args.run_dir), "--child", point.id]
    if args.dry_cpu:
        cmd.append("--dry-cpu")
    elif point.tier == 2:
        cmd.append("--headless")
    return cmd


def launch_child(args: argparse.Namespace, point, guard) -> tuple[int | None, str]:
    """Run one child to its end, its output appended to points/<id>.log. Returns (exit code, why it stopped early:
    "" or the run contract's stop reason). A stop or the cap during the child terminates it."""
    log = attempt_log(args.run_dir, point.id)
    env = {**os.environ}
    if args.dry_cpu:
        env["CUDA_VISIBLE_DEVICES"] = ""
    with open(log, "a") as fh:
        proc = subprocess.Popen(child_command(args, point), stdout=fh, stderr=subprocess.STDOUT, env=env, cwd=str(ROOT))
        while True:
            try:
                return proc.wait(timeout=POLL_S), ""
            except subprocess.TimeoutExpired:
                reason = guard.stop_reason()
                if reason:
                    proc.send_signal(signal.SIGTERM)
                    try:
                        proc.wait(timeout=KILL_WAIT_S)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                    return None, reason


def log_tail(path: Path) -> tuple[list[str], list[str]]:
    """(last lines, lines that look like an out-of-memory message) of a child's log."""
    if not path.is_file():
        return [], []
    lines = path.read_text(errors="replace").splitlines()
    oom = [ln for ln in lines if any(re.search(m, ln.lower()) for m in OOM_PATTERNS)]
    return lines[-LOG_TAIL_LINES:], oom[-LOG_TAIL_LINES:]


def row_without_file(point, code: int | None, log: Path) -> dict:
    """The row the parent writes when a child ended without one: did_not_fit if the log shows an out-of-memory message,
    else crashed."""
    from svg_training.ste import speed
    tail, oom = log_tail(log)
    return {"id": point.id, "tier": point.tier, "size": point.size, "games": point.games, "drones": point.drones,
            "status": speed.DID_NOT_FIT if oom else CRASHED, "exit_code": code, "oom_lines": oom, "log_tail": tail,
            "controls": {}, "written_by": "parent"}


def read_rows(run_dir: Path) -> dict[str, dict]:
    folder = run_dir / POINTS_DIR
    return {p.stem: json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))} if folder.is_dir() else {}


REQUIRED_POINT_CONTROLS = {"agree_point": "physics_agreement", "learner_update_point": "learner_update"}


def control_failures(gates, rows: dict[str, dict], finished: bool = False) -> dict[str, str]:
    """{control: why} for every failed or missing control (LEAD CALLS 21 Nov 2026, QC L02-5 and L02-6): the rows'
    [controls]; C-3, a protected point at the smallest games of its tier that did not fit, and any protected point that
    crashed (not out of memory); the named controls of the agree and learner points, required once their rows exist
    and, at the end of a run, required at all."""
    from svg_training.ste import speed
    bad = {}
    for pid, row in rows.items():
        for name in speed.failed_controls(row):
            bad[f"{pid}:{name}"] = json.dumps(row["controls"][name], default=str)
    for key, name in REQUIRED_POINT_CONTROLS.items():
        pid = gates.controls[key]
        row = rows.get(pid)
        if row is None:
            if finished:
                bad[f"{pid}:{name}"] = "missing: the point has no row at the end of the run"
        elif row["status"] == speed.FIT and name not in row.get("controls", {}):
            bad[f"{pid}:{name}"] = "missing from the point's row"
    for tier in speed.TIERS:
        pts = [p for p in gates.points if p.tier == tier and p.protected]
        if not pts:
            continue
        small = min(p.games for p in pts)
        for p in pts:
            if p.id not in rows:
                continue
            if p.games == small and rows[p.id]["status"] != speed.FIT:
                bad[f"{p.id}:C-3"] = f"status {rows[p.id]['status']} at the smallest protected games of tier {tier}"
            elif rows[p.id]["status"] == CRASHED:
                bad[f"{p.id}:C-3"] = "a protected point crashed (not out of memory)"
    return bad


def largest_fit(rows: dict[str, dict], tier: int, protected: set[str], size: str = "3v3") -> int | None:
    """Largest games at once that fitted, walking up the sizes; it stops at the first PROTECTED point that did not fit
    (LEAD CALL QC L02-5), so a later fit above a failure is not claimed."""
    best = None
    for pid, r in sorted(((k, v) for k, v in rows.items() if v["tier"] == tier and v["size"] == size),
                         key=lambda kv: kv[1]["games"]):
        if r["status"] == "fit":
            best = r["games"]
        elif pid in protected:
            break
    return best


def preflight(args: argparse.Namespace, gates) -> str | None:
    from svg_training.ste import speed
    problem = speed.game_problem(gates)
    if problem:
        return problem
    pinned = args.run_dir / PINNED_SHA
    if pinned.is_file() and pinned.read_text().strip() != gates.sha256:
        return f"the gate file changed since the first launch in {args.run_dir}: a new limit means a new run folder"
    if (args.run_dir / TERMINAL_FILE).is_file():
        return (f"this run folder ended with a non-finite value ({TERMINAL_FILE}): ABORTED for good; a new run needs a "
                "new run folder")
    if args.cap_h is None or not (math.isfinite(args.cap_h) and args.cap_h > 0):
        return f"--cap-h must be a finite number of hours above 0, got {args.cap_h!r}"
    if not args.dry_cpu and abs(args.cap_h - float(gates.run["cap_h"])) > 1e-9:
        return f"--cap-h {args.cap_h} differs from the gate file's [run] cap_h {gates.run['cap_h']}"
    job_file = args.run_dir / "job.json"
    if job_file.is_file():
        job = json.loads(job_file.read_text())
        if abs(float(job.get("gpu_h", 0)) - args.cap_h) > 1e-9 and not args.dry_cpu:
            return f"the launcher asked for {job.get('gpu_h')} GPU-h, --cap-h is {args.cap_h}: keep the two equal"
    if any(p.tier == 2 for p in gates.points) and not (args.headless or args.dry_cpu):
        return "tier 2 points start Isaac Lab: add --headless (after scripts/isaac_preflight.sh --approved-headless exits 0)"
    if not args.dry_cpu:
        import torch
        if not torch.cuda.is_available():
            return "the gate file plays on cuda and PyTorch sees no GPU"
    return None


def run_parent(args: argparse.Namespace, launch=launch_child) -> int:
    from svg_training.ste import atomic, speed
    from svg_training.ste.run_contract import (EXIT_CONTROL_FAILED, EXIT_DONE, EXIT_FOR_STOP, EXIT_NONFINITE,
                                               RunBusyError, RunGuard)
    from ste_sweep_l011 import code_identity
    src = args.run_dir / GATES_COPY if (args.run_dir / GATES_COPY).is_file() else (args.gates or speed.GATES_FILE)
    try:
        gates = speed.load_gates(src)
    except (OSError, ValueError) as err:
        return refuse(f"gate file {src}: {err}")
    if args.gates is not None and (args.run_dir / GATES_COPY).is_file() and speed.sha256_file(args.gates) != gates.sha256:
        return refuse(f"--gates {args.gates} differs from the run folder's pinned copy: a new limit means a new run folder")
    reason = preflight(args, gates)
    if reason:
        return refuse(reason)
    controls_file = args.run_dir / CONTROLS_FILE
    if controls_file.is_file() and json.loads(controls_file.read_text()).get("failed"):
        print(f"a control failed in this run folder ({controls_file}): terminal; a new run needs a new run folder",
              file=sys.stderr, flush=True)
        return EXIT_CONTROL_FAILED
    args.run_dir.mkdir(parents=True, exist_ok=True)
    try:
        with RunGuard(args.run_dir, cap_s=args.cap_h * HOUR_S) as guard:
            code_file = args.run_dir / "code.json"
            now = code_identity()
            if code_file.is_file():
                first = json.loads(code_file.read_text())
                last = first["changes"][-1] if first["changes"] else first["first"]
                if {k: last[k] for k in ("commit", "diff_sha256")} != now:
                    if not args.allow_code_change:
                        return refuse("the code changed since this run folder was started: start a new run folder, "
                                      "or pass --allow-code-change (recorded)")
                    first["changes"].append({**now, "allowed": True, "time": time.time()})
                    write_json(code_file, first)
            else:
                write_json(code_file, {"first": now, "changes": []})
            if not (args.run_dir / PINNED_SHA).is_file():
                shutil.copyfile(src, args.run_dir / GATES_COPY)
                atomic.write_text(args.run_dir / PINNED_SHA, gates.sha256 + "\n")
            resumed = guard.load_latest()
            state = resumed.state if resumed else {"cuts": []}
            step = resumed.step if resumed else 0
            for point in gates.points:
                rows = read_rows(args.run_dir)
                if point.id in rows or point.id in state["cuts"]:
                    continue
                ok = speed.runnable(point, rows)
                if ok is not True:
                    state["cuts"].append(point.id)
                    write_json(args.run_dir / CUTS_FILE, {"cuts": state["cuts"], "why": {
                        point.id: "its condition is not met" if ok is False else "the point it depends on did not run"}})
                    continue
                reason = guard.stop_reason()
                if reason:
                    guard.save(step, state)
                    write_results(args.run_dir, gates, stopped=reason)
                    return EXIT_FOR_STOP[reason]
                todo = [p for p in gates.points if p.id not in rows and p.id not in state["cuts"]
                        and gates.points.index(p) >= gates.points.index(point)]
                cuts = speed.plan_cuts(gates, todo, rows, args.cap_h * HOUR_S - guard.effective_s())
                if cuts:
                    state["cuts"] += cuts
                    write_json(args.run_dir / CUTS_FILE, {"cuts": state["cuts"], "why": {c: "projected over the cap"
                                                                                       for c in cuts}})
                    say(f"cut to fit the cap: {', '.join(cuts)}")
                    if point.id in cuts:
                        continue
                say(f"point {point.id}: tier {point.tier}, {point.size}, {point.games} games")
                log = new_attempt_log(args.run_dir, point.id)
                code, stopped = launch(args, point, guard)
                row_file = args.run_dir / POINTS_DIR / f"{point.id}.json"
                if not stopped and not row_file.is_file():
                    stopped = guard.stop_reason() or ""      # the stop reached the child first (gpu_pause.sh, Ctrl-C)
                if stopped:
                    guard.save(step, state)
                    write_results(args.run_dir, gates, stopped=stopped)
                    return EXIT_FOR_STOP[stopped]
                if not row_file.is_file():
                    write_json(row_file, row_without_file(point, code, log))
                else:                                        # QC L02-4: a row with an allocation failure in its log
                    row = json.loads(row_file.read_text())
                    _tail, oom = log_tail(log)
                    if oom and row["status"] == speed.FIT:
                        row.update(status=SUSPECT, oom_lines=oom, note="an out-of-memory message in this attempt's log")
                        write_json(row_file, row)
                step += 1
                guard.save(step, state)
                rows = read_rows(args.run_dir)
                failed = control_failures(gates, rows)
                write_json(controls_file, {"failed": failed, "checked_after": point.id})
                if failed:
                    say(f"CONTROL_FAILED: {failed}")
                    write_results(args.run_dir, gates, stopped="control_failed")
                    return EXIT_CONTROL_FAILED
                if code == EXIT_NONFINITE or nonfinite_in(rows[point.id]):
                    write_json(args.run_dir / TERMINAL_FILE, {"exit": EXIT_NONFINITE, "point": point.id, "time": time.time()})
                    write_results(args.run_dir, gates, stopped="nonfinite")
                    return EXIT_NONFINITE
            failed = control_failures(gates, read_rows(args.run_dir), finished=True)
            write_json(controls_file, {"failed": failed, "checked_after": "end of run"})
            if failed:
                write_results(args.run_dir, gates, stopped="control_failed")
                return EXIT_CONTROL_FAILED
            write_results(args.run_dir, gates, stopped=None)
            return EXIT_DONE
    except RunBusyError as err:
        return refuse(str(err))


# ================================================================================================ results
def write_results(run_dir: Path, gates, stopped: str | None) -> dict:
    """results.json (rows, cuts, controls, settings) and results.md (one table per tier and the memory table)."""
    from svg_training.ste import speed
    rows = read_rows(run_dir)
    cuts = json.loads((run_dir / CUTS_FILE).read_text()) if (run_dir / CUTS_FILE).is_file() else {"cuts": [], "why": {}}
    failed = control_failures(gates, rows, finished=stopped is None)
    order = [p.id for p in gates.points]
    res = {"task": "L0.2", "verdict": gates.run["verdict"], "stopped": stopped, "gates_sha256": gates.sha256,
           "game_file": gates.run["game_file"], "rows": [rows[i] for i in order if i in rows], "cuts": cuts,
           "controls_failed": failed, "controls_all_pass": not failed,
           "not_run": [i for i in order if i not in rows],
           "largest_fit": {str(t): largest_fit(rows, t, {p.id for p in gates.points if p.protected}) for t in speed.TIERS},
           "terminal": json.loads((run_dir / TERMINAL_FILE).read_text()) if (run_dir / TERMINAL_FILE).is_file() else None,
           "dry_cpu": any(r.get("dry_cpu") for r in rows.values())}
    write_json(run_dir / "results.json", res)
    (run_dir / "results.md").write_text(render_md(res, gates))
    return res


def _f(v, fmt="{:,.0f}") -> str:
    return "n/a" if v is None else fmt.format(v)


def render_md(res: dict, gates) -> str:
    void = not res["controls_all_pass"] or bool(res.get("terminal"))
    lines = ["# L0.2 Tier 2 speed in contested play: results (INFO; observed in the training simulator)", "",
             *([f"**CONTROLS FAILED — rates void.** Failed: {', '.join(res['controls_failed']) or 'none'}"
                + (f"; non-finite (terminal) at {res['terminal'].get('point')}" if res.get("terminal") else "")
                + ". A diagnostic of the run folder, not a result (LEAD CALL QC L02-7).", ""] if void else []),
             f"Game file `{res['game_file']}`; learner team {gates.run['learner_team']} (T41 recipe, one decision per "
             f"{gates.trainer['decision_ticks']} ticks, {gates.trainer['rollouts']} decisions + 1 PPO update of "
             f"{gates.trainer['learning_epochs']} x {gates.trainer['mini_batches']}); opponent and scripted reference "
             f"{gates.run['guard_script']} v {gates.run['strike_script']}."
             + (" **DRY CPU RUN (tests): not of record.**" if res["dry_cpu"] else ""), "",
             f"Controls: {'every control PASS' if res['controls_all_pass'] else 'FAILED: ' + ', '.join(res['controls_failed'])}"
             f"; stopped: {res['stopped'] or 'no (finished)'}.", "",
             "| Point | Tier | Size | Games | Status | Reference (scripted) game-steps/s | Rollout (learner forward) "
             "game-steps/s | Training game-steps/s | Drone-steps/s (training) | PPO update s | GPU MiB (process, nvidia-smi) "
             "| torch peak MiB |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in res["rows"]:
        if r["status"] != "fit":
            lines.append(f"| {r['id']} | {r['tier']} | {r['size']} | {r['games']:,} | **{r['status'].replace('_', ' ')}**"
                         f"{' (VOID)' if void else ''} "
                         "| | | | | | | |")
            continue
        lr, rf, nv = r["learner"], r["reference"], r.get("nvidia_smi") or {}
        tr = lr["train_game_steps_per_s"]
        lines.append(f"| {r['id']} | {r['tier']} | {r['size']} | {r['games']:,} | fit{' (VOID)' if void else ''} | "
                     f"{_f(rf['game_steps_per_s'])} | "
                     f"{_f(lr['rollout_game_steps_per_s'])} | {_f(tr)} | {_f(tr * r['drones'] if tr else None)} | "
                     f"{_f(lr['update_s_each'], '{:.1f}')} | {_f(nv.get('process_mib'))} | "
                     f"{_f(r.get('torch_peak_reserved_mib'))} |")
    lines += ["", f"Largest 3v3 games at once that fitted: tier 1 {res['largest_fit']['1']}, tier 2 "
                  f"{res['largest_fit']['2']}.", f"Not run: {', '.join(res['not_run']) or 'none'}; cuts: "
                  f"{json.dumps(res['cuts'].get('why', {}))}.", ""]
    for r in res["rows"]:
        a = r.get("controls", {}).get("physics_agreement")
        if a:
            lines.append(f"C-1a PHYSICS (gated), bare worlds, the same recorded inputs: {a.get('games')} games x "
                         f"{a.get('drones')} drones x {a.get('ticks')} ticks, largest gap {_f(a.get('max_gap_m'), '{:.5f}')}"
                         f" m (limit {a.get('limit_m')} m): {'PASS' if a.get('pass') else 'FAIL'}.")
        b = r.get("info", {}).get("game_agreement")
        if b:
            lines.append(f"C-1b GAME (INFO, not gated): first in/out difference at tick {b['first_divergence_tick']}, "
                         f"{b['differing_alive_drone_ticks']} drone-ticks differ, largest gap while both in the game "
                         f"{b['max_gap_alive_before_divergence_m']:.5f} m; ended / reaches / tags {b['world']['ended']} / "
                         f"{b['world']['reaches']} / {b['world']['tags']} (world) v {b['reference']['ended']} / "
                         f"{b['reference']['reaches']} / {b['reference']['tags']} (reference).")
    clips = [c for r in res["rows"] for c in r.get("clips", [])]
    lines += ["", "Clips: " + ("; ".join(clips) if clips else "none recorded") + ". 3-D clips: pending (VID-1).", ""]
    return "\n".join(lines)


# ================================================================================================ entry
def main(argv: list[str] | None = None, launch=launch_child) -> int:
    args = parser().parse_args(argv)
    args.run_dir = args.run_dir.resolve()
    if (ROOT / "runs").resolve() not in args.run_dir.parents:
        return refuse(f"{args.run_dir} is not under {ROOT / 'runs'}")
    if args.child:
        return run_child(args)
    if args.record_only:
        from svg_training.ste import speed
        old = args.run_dir / "results.json"
        before = json.loads(old.read_text()).get("stopped") if old.is_file() else "no results before --record-only"
        write_results(args.run_dir, speed.load_gates(args.run_dir / GATES_COPY), stopped=before)
        return 0
    return run_parent(args, launch)


def _child_isaac() -> int:
    """A tier 2 child: Isaac Sim starts headless before torch is imported; the process leaves through os._exit. Ctrl-C
    (or the parent's SIGTERM turned into KeyboardInterrupt) during the start or the point exits 4 without a row."""
    code = 1
    try:
        from _isaac_app import start_headless
        args, _app = start_headless(parser(isaac=True))
        args.run_dir = args.run_dir.resolve()
        code = run_child(args)
    except KeyboardInterrupt:
        code = 4
    except SystemExit as ex:                       # start_headless refuses with SystemExit(2)
        code = ex.code if isinstance(ex.code, int) else 2
    except BaseException:  # noqa: BLE001  (any failure: the parent writes the row from the log)
        traceback.print_exc()
        tail = "".join(traceback.format_exc()).lower()
        code = EXIT_CHILD_OOM_NO_ROW if any(re.search(m, tail) for m in OOM_PATTERNS) else 1
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)          # never simulation_app.close() (it swallows exit codes)
    return code


def _point_tier(argv: list[str]) -> int | None:
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--child")
    pre.add_argument("--run-dir", type=Path)
    pre.add_argument("--dry-cpu", action="store_true")
    known, _ = pre.parse_known_args(argv)
    if not known.child or known.dry_cpu or known.run_dir is None:
        return None
    import tomllib
    gates = tomllib.loads((known.run_dir / GATES_COPY).read_text())
    return next((int(p["tier"]) for p in gates["point"] if p["id"] == known.child), None)


if __name__ == "__main__":
    argv = sys.argv[1:]
    if _point_tier(argv) == 2:
        if "--headless" not in argv:
            print("refused: a tier 2 point starts Isaac Lab: --headless", file=sys.stderr)
            sys.exit(2)
        _child_isaac()
    sys.exit(main())
