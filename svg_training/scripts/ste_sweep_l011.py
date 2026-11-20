#!/usr/bin/env python
"""STE task L0.11 Screening sweep (INFO): scripted Guards against scripted Strikes, tier 1 with the safety filter on.

    ste_sweep_l011.py --run-dir runs/<date>_ste_l011_screen --cap-h <GPU-h> [--gates configs/ste_l011/gates.toml]
                      [--expect-gates-sha256 <hex>]
    ste_sweep_l011.py --pilot --run-dir runs/<date>_ste_l011_pilot --cap-h <GPU-h>

Launch it through ``scripts/ste_job.py launch --task L0.11 ... --gpu-h <H> -- <this command> --cap-h <H>`` (the same H:
the driver refuses a run folder whose job.json asks for other hours, or a GPU job on the CPU). The run contract
(``ste/run_contract.py``): the same command resumes; SIGINT or SIGTERM stops at the next tick, discards the unfinished
batch and checkpoints; the cap is effective seconds (wall clock less the owner's pauses of this process) = --cap-h x
3600. Exit codes: 0 done; 2 refused (bad gate file, a game file or the gate file changed since the first launch, cap
or device mismatch, run folder busy); 3 stopped at the cap; 4 stopped on request; 5 a player produced a non-finite
action; 6 CONTROL_FAILED (a control with a known answer failed: terminal, never retried; the same command on the same
folder ends with 6 again).

What it does (the gate file's order; ``source/svg_training/ste/sweep.py`` holds the logic):
1. copies the gate file into the run folder and pins its sha256 (``gates.sha256``); every game file must match the
   sha256 the gate file pins;
2. plays the groups in run order, batch by batch (``cells_per_batch`` cells side by side, paired starts); each finished
   batch is written to ``cells/<group>__bNN.json`` (one row per cell) and ``.npz`` (per-game arrays), then the
   checkpoint lists it: the record of finished cells a relaunch resumes from;
3. checks the controls after every batch (``controls.json``; a failure stops the run when ``stop_on_fail``);
4. at each group boundary projects the time left and cuts whole sweep groups from the end of the run order if they
   would not fit the cap (``[cut]``);
5. at the end writes ``results.json`` and ``results.md`` (controls first), the shortlist by the gate file's rule, the
   figures (``scripts/make_ste_l011_figures.py``) and the replay clips (``videos/``, STANDARDS section 8).

``--pilot``: no sweep; measures game-steps per second and GPU memory per team size and batch size (``[pilot]``), and
projects the full grid for each batch size against the cap (``pilot.json``, ``pilot.md``). Training simulator, tier 1:
results are "observed in the training simulator"."""
from __future__ import annotations

import argparse
import json
import math
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from svg_training.ste import atomic  # noqa: E402
from svg_training.ste import sweep  # noqa: E402
from svg_training.ste.run_contract import (EXIT_CONTROL_FAILED, EXIT_DONE, EXIT_FOR_STOP,  # noqa: E402
                                           EXIT_NONFINITE, EXIT_REFUSED,
                                           STOP_CAP, RunBusyError, RunGuard)

HOUR_S = 3600.0
PINNED_SHA = "gates.sha256"
GATES_COPY = "gates.toml"
CELLS_DIR = "cells"
CONTROLS_FILE = "controls.json"
CODE_FILE = "code.json"           # QC M-2: the code a run folder was started with
PASS, FAIL, PENDING = "PASS", "FAIL", "PENDING"
SIMULATOR = ("training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, "
             "fitted PX4 response, exploratory)")


def say(text: str) -> None:
    print(f"[l011] {text}", flush=True)


def parse(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--gates", type=Path, default=sweep.GATES_FILE)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--cap-h", type=float, required=True, help="cap in effective hours (= the launcher's --gpu-h)")
    ap.add_argument("--expect-gates-sha256", help="refuse unless the gate file has this sha256")
    ap.add_argument("--pilot", action="store_true", help="measure rate and memory per size and batch size only")
    ap.add_argument("--no-clips", action="store_true", help="skip the replay clips (tests only)")
    ap.add_argument("--allow-code-change", action="store_true",
                    help="resume although the code differs from the first launch's (recorded in code.json and results)")
    ap.add_argument("--sleep-between-batches-s", type=float, default=0.0, help=argparse.SUPPRESS)   # tests only
    return ap.parse_args(argv)


def refuse(text: str) -> int:
    print(f"refused: {text}", file=sys.stderr, flush=True)
    return EXIT_REFUSED


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def code_identity() -> dict:
    """The code a run plays: the commit, and the sha256 of the uncommitted changes under svg_training/ (empty diff = the
    sha256 of nothing)."""
    import hashlib
    try:
        diff = subprocess.run(["git", "-C", str(ROOT), "diff", "HEAD", "--", "."], capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        diff = b"unknown"
    return {"commit": _git("rev-parse", "HEAD"), "diff_sha256": hashlib.sha256(diff).hexdigest()}


def pin_code(args: argparse.Namespace) -> str | None:
    """QC M-2: pin the code at the first launch; on a resume refuse other code unless --allow-code-change (recorded)."""
    path = args.run_dir / CODE_FILE
    now = code_identity()
    if not path.is_file():
        write_json(path, {"first": now, "changes": []})
        return None
    pinned = json.loads(path.read_text())
    last = pinned["changes"][-1] if pinned["changes"] else pinned["first"]
    if {k: last[k] for k in ("commit", "diff_sha256")} == now:
        return None
    if not args.allow_code_change:
        return (f"the code changed since this run folder was started (pinned commit {last['commit'][:12]}, diff "
                f"{last['diff_sha256'][:12]}; now {now['commit'][:12]}, {now['diff_sha256'][:12]}): batches from two code "
                f"versions would mix; start a new run folder, or pass --allow-code-change (recorded)")
    pinned["changes"].append({**now, "allowed": True, "time": time.time()})
    write_json(path, pinned)
    say(f"code changed since the first launch: allowed by --allow-code-change and recorded in {CODE_FILE}")
    return None


def write_json(path: Path, obj) -> None:
    atomic.write_text(path, json.dumps(obj, indent=1, default=_jsonable) + "\n")


def _jsonable(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"not JSON: {type(value).__name__}")


def batch_file(run_dir: Path, batch_id: str, suffix: str) -> Path:
    return run_dir / CELLS_DIR / (batch_id.replace("/", "__") + suffix)


# ================================================================================================ pre-flight
def preflight(args: argparse.Namespace, gates: sweep.Gates) -> str | None:
    """The reason to refuse, or None."""
    problems = sweep.game_file_problems(gates)
    if problems:
        return "game file(s) differ from the gate file: " + "; ".join(problems)
    if args.expect_gates_sha256 and args.expect_gates_sha256 != gates.sha256:
        return f"the gate file has sha256 {gates.sha256}, expected {args.expect_gates_sha256}"
    pinned = args.run_dir / PINNED_SHA
    if pinned.is_file() and pinned.read_text().strip() != gates.sha256:
        return (f"the gate file changed since the first launch in {args.run_dir} (pinned {pinned.read_text().strip()}, "
                f"now {gates.sha256}): a new limit means a new run folder")
    if not (math.isfinite(args.cap_h) and args.cap_h > 0):
        return f"--cap-h must be a finite number of hours above 0, got {args.cap_h!r}"
    device = gates.run["device"]
    job_file = args.run_dir / "job.json"
    if job_file.is_file():
        job = json.loads(job_file.read_text())
        if job.get("gpu_h", 0) > 0:
            if abs(job["gpu_h"] - args.cap_h) > 1e-9:
                return f"the launcher asked for {job['gpu_h']} GPU-h, --cap-h is {args.cap_h}: keep the two equal"
            if not str(device).startswith("cuda"):
                return f"a GPU job (--gpu-h {job['gpu_h']}) with device {device!r} in the gate file"
        elif str(device).startswith("cuda"):
            return "the gate file plays on cuda but the launcher asked for 0 GPU-h (a CPU job)"
    table = gates.projection["seconds_per_batch_tick"]
    sizes = {sweep.group_game(gates, g)[1] for g in gates.groups}
    if gates.run["require_projection"] and not args.pilot and not sizes <= set(table):
        return (f"the gate file requires [projection.seconds_per_batch_tick] for every planned size {sorted(sizes)}, it "
                f"holds {sorted(table)}: fill it from the pilot (QC I3)")
    if str(device).startswith("cuda") and not torch.cuda.is_available():
        return "the gate file plays on cuda and PyTorch sees no GPU"
    return None


def failed_controls(args: argparse.Namespace) -> list[str]:
    """Controls recorded as FAIL in the run folder (a sweep folder only)."""
    controls = args.run_dir / CONTROLS_FILE
    if args.pilot or not controls.is_file():
        return []
    return [k for k, v in json.loads(controls.read_text()).items() if v["status"] == FAIL]


def main(argv: list[str] | None = None) -> int:
    args = parse(argv)
    try:
        gates = sweep.load_gates(args.gates)
    except (OSError, ValueError) as err:
        return refuse(f"gate file {args.gates}: {err}")
    reason = preflight(args, gates)
    if reason:
        return refuse(reason)
    failed = failed_controls(args)
    if failed:                     # CONTROL_FAILED is terminal: the same command on the same folder ends with it again
        print(f"control(s) {failed} failed in this run folder ({args.run_dir / CONTROLS_FILE}): read them; a new run "
              f"needs a new run folder (exit {EXIT_CONTROL_FAILED}, CONTROL_FAILED)", file=sys.stderr, flush=True)
        return EXIT_CONTROL_FAILED
    args.run_dir.mkdir(parents=True, exist_ok=True)
    try:
        with RunGuard(args.run_dir, cap_s=args.cap_h * HOUR_S) as guard:
            changed = pin_code(args)
            if changed:
                return refuse(changed)
            if not (args.run_dir / PINNED_SHA).is_file():
                shutil.copyfile(args.gates, args.run_dir / GATES_COPY)
                atomic.write_text(args.run_dir / PINNED_SHA, gates.sha256 + "\n")
            return pilot(gates, args, guard) if args.pilot else run_sweep(gates, args, guard)
    except RunBusyError as err:
        return refuse(str(err))


# ================================================================================================ the sweep
def setting_of(cfg, size: str, dz_m: float) -> str:
    """The start setting of a game: cells with the same one must share their starts (control paired_starts)."""
    side = cfg.arena.bands_m["lab"][0]
    return (f"{size} side {side} m disc {cfg.starts.guard_disc_m} m ring {cfg.starts.strike_ring_m} m"
            f"{f' Strikes {dz_m} m up' if dz_m else ''}")


def evaluate_controls(gates: sweep.Gates, plan: list, run_dir: Path, done: set[str]) -> dict:
    """Every control's status from the finished batches: PASS, FAIL or PENDING (its cells are not all played yet)."""
    out: dict[str, dict] = {}
    shas: dict[str, set] = {}
    bound_bad, nonfinite = [], 0
    by_name = {p.spec.name: p for p in plan}
    for p in plan:
        game, size = sweep.group_game(gates, p.spec)
        cfg = sweep.variant_cfg(gates, game)
        g, s = sweep.parse_size(size)
        ids = [p.batch_id(i) for i in range(len(p.batches))]
        rows = []
        for bid in ids:
            if bid in done:
                data = json.loads(batch_file(run_dir, bid, ".json").read_text())
                rows += data["rows"]
                nonfinite += data["nonfinite_actions"]
                shas.setdefault(setting_of(cfg, size, p.spec.strike_start_dz_m or 0), set()).update(data["start_sha256"])
        for r in rows:                                 # QC I1: the one-for-one invariant, every game of every cell
            if r["one_for_one_bad_games"] or r["removed_bad_games"]:
                bound_bad.append(f"{p.spec.name} {r['guard']} v {r['strike']}: {r['one_for_one_bad_games']} games Guards "
                                 f"tagged != Strikes tagged, {r['removed_bad_games']} games Guards removed != Strikes tagged")
        if p.spec.role != sweep.ROLE_CONTROL:
            continue
        complete = all(bid in done for bid in ids)
        if not complete:
            out[p.spec.name] = {"status": PENDING, "control": p.spec.control, "detail": "cells not all played"}
            continue
        if p.spec.control in (sweep.TAG_FIRES, sweep.REACH_FIRES):        # QC C1: known non-zero answers, per game
            per = [dict(np.load(batch_file(run_dir, bid, ".npz"))) for bid in ids]
            pg = {k: np.concatenate([x[k] for x in per]) for k in per[0]}
            ok, detail = (sweep.check_tag_fires(pg, g, s) if p.spec.control == sweep.TAG_FIRES
                          else sweep.check_reach_fires(pg))
        elif p.spec.control == sweep.SAME_SEED:
            source = by_name[p.spec.of_group].batch_id(p.spec.of_batch)
            a = dict(np.load(batch_file(run_dir, source, ".npz")))
            b = dict(np.load(batch_file(run_dir, ids[0], ".npz")))
            tol = 0.0 if gates.run["device"] == "cpu" else float(gates.controls["same_seed_closest_tol_m"])
            ok, detail = sweep.check_same_seed(a, b, tol)
        elif p.spec.control == sweep.STAND_STILL:
            reaches = sum(r["reaches"] for r in rows)
            ok = reaches == 0
            detail = f"{reaches} reaches in {sum(r['games'] + r['unfinished'] for r in rows)} games"
        else:                                          # zero_tags and stand_still_zero_tags
            tags = sum(r["tags_total_all"] for r in rows)
            ok = tags == 0
            detail = f"{tags} tags in {sum(r['games'] + r['unfinished'] for r in rows)} games"
        out[p.spec.name] = {"status": PASS if ok else FAIL, "control": p.spec.control, "detail": detail}
    checks = gates.controls["global_checks"]
    if "tags_one_for_one" in checks:
        out["tags_one_for_one"] = {"status": FAIL if bound_bad else PASS, "control": "global",
                                   "detail": "; ".join(bound_bad) or "every played game one for one"}
    if "paired_starts" in checks:
        ok, detail = sweep.check_paired_starts(shas)
        out["paired_starts"] = {"status": PASS if ok else FAIL, "control": "global", "detail": detail}
    if "no_nonfinite_actions" in checks:
        out["no_nonfinite_actions"] = {"status": PASS if nonfinite == 0 else FAIL, "control": "global",
                                       "detail": f"{nonfinite} non-finite actions"}
    return out


def timed(spec: sweep.GroupSpec) -> bool:
    """QC I2: only full-length sweep and sensitivity batches feed the projection, never the controls (still drones, an
    idle filter, a few ticks)."""
    return spec.role != sweep.ROLE_CONTROL and spec.ticks is None


def seconds_per_tick(size: str, state: dict, gates: sweep.Gates) -> float | None:
    """Seconds per batch tick for ``size``: measured in this run on full-length sweep batches, else the gate file's pilot
    value, else the slowest known size scaled by the drone count; None when nothing is known."""
    timing = state["timing"]
    if timing.get(size):
        return float(np.mean(timing[size]))
    table = gates.projection["seconds_per_batch_tick"]
    if size in table:
        return float(table[size])
    known = {k: float(np.mean(v)) for k, v in timing.items() if v}
    known.update({k: float(v) for k, v in table.items() if k not in known})
    if not known:
        return None
    ref = max(known, key=known.get)
    return known[ref] * sum(sweep.parse_size(size)) / sum(sweep.parse_size(ref))


class ProtectedDoNotFit(RuntimeError):
    """The protected groups alone cannot fit the cap left (QC I3, H6)."""


def project_cuts(gates: sweep.Gates, plan: list, start: int, state: dict, left_s: float) -> tuple[list[str], float | None]:
    """Groups to cut (from the END of the run order, sweep groups not started and not protected) so that the projected
    seconds of the groups from ``start`` on, times the safety factor, fit ``left_s``. Returns (cuts, projection)."""
    done, cut = set(state["done"]), set(state["cut"])
    protected = set(gates.cut["protected"])

    def projected(skip: set[str]) -> float | None:
        total = 0.0
        for p in plan[start:]:
            if p.spec.name in cut | skip:
                continue
            spt = seconds_per_tick(sweep.group_game(gates, p.spec)[1], state, gates)
            if spt is None:
                return None
            total += spt * p.spec.ticks_cap(gates.run) * sum(1 for i in range(len(p.batches)) if p.batch_id(i) not in done)
        return total * float(gates.cut["safety_factor"]) + float(gates.clips["reserve_s"])

    skip: list[str] = []
    cuttable_all = {p.spec.name for p in plan[start:] if p.spec.role != sweep.ROLE_CONTROL and p.spec.name not in protected
                    and not any(p.batch_id(i) in done for i in range(len(p.batches)))}
    floor = projected(cuttable_all)              # QC I3: the protected groups (and started ones) alone
    if floor is not None and floor > left_s:
        raise ProtectedDoNotFit(f"the protected groups alone project to {floor:.0f} s (x {gates.cut['safety_factor']} "
                                f"+ {gates.clips['reserve_s']} s clip reserve), the cap left is {left_s:.0f} s: H6, "
                                f"no launch (QC I3)")
    estimate = projected(set())
    while estimate is not None and estimate > left_s:
        cuttable = [p.spec.name for p in plan[start:] if p.spec.role != sweep.ROLE_CONTROL and p.spec.name not in protected
                    and p.spec.name not in cut | set(skip)
                    and not any(p.batch_id(i) in done for i in range(len(p.batches)))]
        if not cuttable:
            break
        skip.append(cuttable[-1])
        estimate = projected(set(skip))
    return skip, estimate


def run_sweep(gates: sweep.Gates, args: argparse.Namespace, guard: RunGuard) -> int:
    run_dir = args.run_dir
    (run_dir / CELLS_DIR).mkdir(exist_ok=True)
    plan = sweep.build_plan(gates)
    resumed = guard.load_latest()
    state = resumed.state if resumed is not None else {"done": [], "cut": [], "timing": {}, "projections": []}
    if resumed is not None:                            # the batches a resume must not replay (smoke check B.8)
        state.setdefault("resumes", []).append({"time": time.time(), "done": list(state["done"])})
    say(f"{'resumed: ' + str(len(state['done'])) + ' batches done' if resumed else 'fresh start'}; gate sha256 "
        f"{gates.sha256[:12]}; {sum(len(p.batches) for p in plan)} batches, {sum(len(p.cells) for p in plan)} cells")
    every = int(gates.run["cap_check_every_ticks"])
    ticks_seen = [0]

    def should_stop() -> bool:
        if guard.stop_requested:
            return True
        ticks_seen[0] += 1
        return ticks_seen[0] % every == 0 and guard.cap_reached()

    def stop(reason: str) -> int:
        guard.save(len(state["done"]), state)
        state["stopped"] = reason                     # the played cells are written for the ABORTED record
        controls = evaluate_controls(gates, plan, run_dir, set(state["done"]))
        write_json(run_dir / CONTROLS_FILE, controls)
        write_results(gates, plan, args, guard, state, controls)
        state.pop("stopped")
        say(f"stopped ({reason}) with {len(state['done'])} batches done; checkpoint saved; the same command resumes")
        return EXIT_FOR_STOP.get(reason, EXIT_NONFINITE)

    for index, p in enumerate(plan):
        name = p.spec.name
        if name in state["cut"]:
            continue
        ids = [p.batch_id(i) for i in range(len(p.batches))]
        if not any(b in state["done"] for b in ids):
            try:
                cuts, estimate = project_cuts(gates, plan, index, state, guard.cap_s - guard.effective_s())
            except ProtectedDoNotFit as err:
                guard.save(len(state["done"]), state)
                return refuse(str(err))
        if p.spec.role != sweep.ROLE_CONTROL and not any(b in state["done"] for b in ids):
            state["projections"].append({"before": name, "projected_s": estimate, "cap_left_s": guard.cap_s - guard.effective_s(),
                                         "cut": cuts})
            if cuts:
                state["cut"] += cuts
                say(f"projection {estimate:.0f} s does not fit the cap left: cut {cuts} (gate file [cut])")
                guard.save(len(state["done"]), state)
            if name in state["cut"]:
                continue
        game, size = sweep.group_game(gates, p.spec)
        cfg = sweep.variant_cfg(gates, game)
        for i, cells in enumerate(p.batches):
            bid = ids[i]
            if bid in state["done"]:
                continue
            reason = guard.stop_reason()
            if reason:
                return stop(reason)
            try:
                res = sweep.play_batch(cfg, size, cells, dict(gates.run, ticks_cap=p.spec.ticks_cap(gates.run)),
                                       should_stop=should_stop, strike_start_dz_m=p.spec.strike_start_dz_m or 0)
            except sweep.SweepStopped:
                return stop(guard.stop_reason() or STOP_CAP)
            if res.nonfinite_actions:
                say(f"{bid}: {res.nonfinite_actions} non-finite actions: a player produced NaN or inf; nothing of "
                    f"this batch is kept")
                stop("non-finite")
                return EXIT_NONFINITE
            n = int(gates.run["games_per_cell"])
            for k, row in enumerate(res.rows):
                part = res.per_game["tags"][k * n:(k + 1) * n]
                row.update(group=name, tags_max_all=int(part.max()), tags_total_all=int(part.sum()))
            np.savez_compressed(batch_file(run_dir, bid, ".tmp.npz"), **res.per_game)
            atomic.commit(batch_file(run_dir, bid, ".tmp.npz"), batch_file(run_dir, bid, ".npz"))
            write_json(batch_file(run_dir, bid, ".json"), {
                "batch": bid, "group": name, "game": game, "size": size, "cells": [list(c) for c in cells],
                "rows": res.rows, "start_sha256": res.start_sha256, "seconds": res.seconds,
                "steps_played": res.steps_played, "games": res.games, "game_steps_per_s": res.game_steps_per_s,
                "peak_allocated_bytes": res.peak_allocated_bytes, "peak_reserved_bytes": res.peak_reserved_bytes,
                "nonfinite_actions": res.nonfinite_actions})
            state["done"].append(bid)
            if timed(p.spec):
                state["timing"].setdefault(size, []).append(res.seconds / max(res.steps_played, 1))
            controls = evaluate_controls(gates, plan, run_dir, set(state["done"]))
            write_json(run_dir / CONTROLS_FILE, controls)
            guard.save(len(state["done"]), state)
            mem = f", peak {res.peak_reserved_bytes / 2**30:.2f} GiB reserved" if res.peak_reserved_bytes else ""
            say(f"{bid}: {len(cells)} cells x {n} games, {res.steps_played} ticks, {res.seconds:.1f} s, "
                f"{res.game_steps_per_s:,.0f} game-steps/s{mem}")
            failed = [k for k, v in controls.items() if v["status"] == FAIL]
            if failed and gates.controls["stop_on_fail"]:
                say(f"CONTROL FAILED: {failed}: {[controls[k]['detail'] for k in failed]}; the run stops (gate file "
                    f"[controls] stop_on_fail); results.md is written for the record")
                state["stopped"] = "control failed"
                write_results(gates, plan, args, guard, state, controls)
                return EXIT_CONTROL_FAILED
            if args.sleep_between_batches_s:
                time.sleep(args.sleep_between_batches_s)
    controls = evaluate_controls(gates, plan, run_dir, set(state["done"]))
    write_json(run_dir / CONTROLS_FILE, controls)
    write_results(gates, plan, args, guard, state, controls)
    figures(run_dir)
    left_s = guard.cap_s - guard.effective_s()
    if args.no_clips:
        state["clips"] = ["clips not made: --no-clips (tests only)"]
    elif left_s < float(gates.clips["reserve_s"]):
        state["clips"] = [f"clips not made: {left_s:.0f} s of the cap left, less than the {gates.clips['reserve_s']} s "
                          f"reserve (gate file [clips])"]
        say(state["clips"][0])
    else:
        state["clips"] = make_clips(gates, run_dir, should_stop=lambda: guard.stop_requested)
        if guard.stop_requested:                      # QC M-5: a stop during the clips is honoured
            write_results(gates, plan, args, guard, state, controls)
            guard.save(len(state["done"]), state)
            say("stopped (interrupted) during the clips; cells, results and figures are written")
            return EXIT_FOR_STOP["interrupted"]
    write_results(gates, plan, args, guard, state, controls)
    guard.save(len(state["done"]), state)
    say(f"done: {len(state['done'])} batches; results in {run_dir / 'results.md'}")
    return EXIT_DONE


# ================================================================================================ results
def metas_of(gates: sweep.Gates, plan: list) -> dict:
    out = {}
    for p in plan:
        if p.spec.role != sweep.ROLE_SWEEP and p.spec.name not in gates.shortlist["info_reference"]:
            continue
        cfg = sweep.variant_cfg(gates, p.spec.game)
        side = cfg.arena.bands_m["lab"][0]
        out[p.spec.name] = {"name": p.spec.name, "arena_side_m": side, "zone_radius_m": cfg.arena.zone_radius_frac[0] * side,
                            "tag_radius_m": cfg.tag.radius_m if cfg.tag.mode != "off" else math.inf,
                            "survive": cfg.tag.guard_survives_tag_prob, "size": p.spec.size}
    return out


def collect(gates: sweep.Gates, plan: list, run_dir: Path, done: set[str]) -> tuple[dict, list]:
    rows, batches = {}, []
    for p in plan:
        rows[p.spec.name] = []
        for i in range(len(p.batches)):
            bid = p.batch_id(i)
            if bid in done:
                data = json.loads(batch_file(run_dir, bid, ".json").read_text())
                rows[p.spec.name] += data["rows"]
                batches.append({k: data[k] for k in ("batch", "size", "games", "steps_played", "seconds",
                                                     "game_steps_per_s", "peak_allocated_bytes", "peak_reserved_bytes")})
    return rows, batches


def _pct(rate, ci) -> str:
    return "n/a" if rate is None else f"{100 * rate:.1f} % ({100 * ci[0]:.1f}–{100 * ci[1]:.1f})"


def _m(v) -> str:
    return "n/a" if v is None else f"{v:.2f}"


def write_results(gates: sweep.Gates, plan: list, args, guard: RunGuard, state: dict, controls: dict) -> None:
    run_dir = args.run_dir
    rows, batches = collect(gates, plan, run_dir, set(state["done"]))
    metas = metas_of(gates, plan)
    planned = {p.spec.name: p.cells for p in plan}
    order = [p.spec.name for p in plan]
    rule = gates.shortlist
    controls_ok = all(v["status"] == PASS for v in controls.values())
    main_list = sweep.shortlist(rows, metas, rule, order, expected_cells=planned)
    no_z = sweep.shortlist(rows, metas, rule, order, expected_cells=planned,
                           exclude_strikes=tuple(gates.players["z_up_info"]))
    meta = {"task": gates.run["task"], "kind": gates.run["kind"], "simulator": SIMULATOR,
            "gates_file": str(args.gates), "gates_sha256": gates.sha256,
            "games": {k: {"file": v.file, "sha256": v.sha256} for k, v in gates.games.items()},
            "commit": _git("rev-parse", "HEAD"), "dirty": bool(_git("status", "--porcelain", "--", ".")),
            "device": gates.run["device"], "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() and
            str(gates.run["device"]).startswith("cuda") else None, "torch": torch.__version__,
            "python": platform.python_version(), "host": platform.node(), "cap_h": args.cap_h,
            "effective_s": guard.effective_s(), "seed": gates.run["seed"], "games_per_cell": gates.run["games_per_cell"],
            "cells_per_batch": gates.run["cells_per_batch"], "ticks_cap": gates.run["ticks_cap"],
            "z_up_label": gates.players["z_up_label"], "z_up_info": list(gates.players["z_up_info"]),
            "multi_guard_labels": dict(gates.players["multi_guard_labels"]),
            "code": json.loads((args.run_dir / CODE_FILE).read_text()) if (args.run_dir / CODE_FILE).is_file() else None,
            "confounds": gates.confounds}
    groups = []
    for p in plan:
        s = p.spec
        groups.append({"name": s.name, "role": s.role, "factor": s.factor, "level": s.level, "control": s.control,
                       "game": sweep.group_game(gates, s)[0], "size": sweep.group_game(gates, s)[1],
                       "cells_planned": len(p.cells), "skipped_duplicates": [list(c) for c in p.skipped],
                       "cut": s.name in state["cut"], "strike_start_dz_m": s.strike_start_dz_m, "rows": rows[s.name]})
    result = {"meta": meta, "stopped": state.get("stopped"), "controls": controls, "controls_all_pass": controls_ok,
              "cut": state["cut"],
              "projections": state["projections"], "groups": groups, "batches": batches, "shortlist": main_list,
              "shortlist_without_z_up": no_z, "clips": state.get("clips", [])}
    write_json(run_dir / "results.json", result)
    atomic.write_text(run_dir / "results.md", render_md(result, gates))


def label(meta: dict, guard: str, multi: bool) -> str:
    """QC M-10: a Guard script's label in a table (with 2+ Guards guard_parked_centre holds its starts)."""
    return meta["multi_guard_labels"].get(guard, guard) if multi else guard


def shortlist_md(sl: dict, result: dict, meta: dict, z: set, gates: sweep.Gates) -> list[str]:
    lines = ["## Shortlist for L0.12 (rule: gate file [shortlist])", "",
             f"Shortlist: **{', '.join(sl['shortlist']) or 'none eligible'}**. Without the "
             f"{', '.join(sorted(z))} columns ({meta['z_up_label']}): "
             f"{', '.join(result['shortlist_without_z_up']['shortlist']) or 'none eligible'}"
             f"{' (differs)' if sl['shortlist'] != result['shortlist_without_z_up']['shortlist'] else ' (same)'}.", "",
             "| Variant | H: best Guard's worst hold | g* | R: best Strike's worst reach | s* | d (games) | eligible | rank |",
             "|---|---|---|---|---|---|---|---|"]
    for v in sl["variants"] + sl["report_only"] + sl.get("info_reference", []):
        rank = ("reference" if v.get("reference") else "INFO, never shortlisted" if v.get("info") else
                v.get("rank", "—") if v["variant"] in gates.shortlist["candidates"] else "report only")
        name = f"{v['label']} (INFO; {v['variant']})" if v.get("info") else v["variant"]
        lines.append(f"| {name} | {_m(v['H'])} | {v['g_star']} | {_m(v['R'])} | {v['s_star']} | "
                     f"{_m(v['d'])} ({v.get('d_games', 'n/a')}) | {v['reason']} | {rank} |")
    return lines + [""]


def render_md(result: dict, gates: sweep.Gates) -> str:
    meta = result["meta"]
    z = set(gates.players["z_up_info"])
    lines = [f"# L0.11 Screening sweep (INFO): results", "", f"Simulator: {meta['simulator']}. Observed in the training "
             f"simulator; nothing here is a flight result.", "",
             f"- Gate file `{meta['gates_file']}`, sha256 `{meta['gates_sha256']}`; commit `{meta['commit'][:12]}`"
             f"{' (working tree not clean)' if meta['dirty'] else ''}; device {meta['device']}"
             f"{' (' + meta['gpu'] + ')' if meta['gpu'] else ''}; seed {meta['seed']}; {meta['games_per_cell']} games "
             f"per cell, {meta['cells_per_batch']} cells per batch; effective {meta['effective_s']:.0f} s of a "
             f"{meta['cap_h']} h cap.", "",
             "Run notes: **Never suspend the machine during a GPU job** (a suspend counts in full against the cap and is "
             "billed as GPU-hours; tooling task L07-SUSPEND). **Finding L011-F1**: the scripted players decide every tick "
             "(0.05 s), not at the sheet's 0.6 s decision period; this sweep measures scripted play at 0.05 s; L0.12's "
             "trainers must fix their decision period explicitly (T41's recipe used 12 ticks = 0.6 s).", "",
             "## Controls (read these first)", "",
             "| Control | Kind | Status | Detail |", "|---|---|---|---|"]
    for name, c in result["controls"].items():
        lines.append(f"| {name} | {c['control']} | **{c['status']}** | {c['detail']} |")
    lines += ["", ("Every control holds." if result["controls_all_pass"] else
                   "**A control failed or is pending: no result below may be read.**"), ""]
    if result["stopped"]:
        lines += [f"**The run stopped ({result['stopped']}) before every cell was played: ABORTED; the cells below are "
                  f"partial and prove nothing.**", ""]
    if result["cut"]:
        lines += [f"**Cut by the projection (gate file [cut]):** {', '.join(result['cut'])}.", ""]
    sl = result["shortlist"]
    if result["controls_all_pass"] and not result["stopped"]:
        lines += shortlist_md(sl, result, meta, z, gates)
    else:                                              # QC I4: no shortlist numbers from a run that cannot be read
        failed = [k for k, c in result["controls"].items() if c["status"] != "PASS"]
        why = "; ".join(([f"control(s) {', '.join(failed)} not PASS"] if failed else [])
                        + ([f"the run stopped ({result['stopped']})"] if result["stopped"] else []))
        lines += ["## Shortlist for L0.12", "", f"Shortlist not read: {why}. No H, R or d is shown.", ""]
    groups = {g["name"]: g for g in result["groups"]}
    for g in result["groups"]:
        if g["role"] != sweep.ROLE_SENSITIVITY or g["cut"] or not g["rows"]:
            continue
        lines += [f"## Sensitivity: every Strike drone starts {1000 * g['strike_start_dz_m']:g} mm higher", "",
                  f"INFO, group `{g['name']}` against the base cells of the same pairs (paired starts, only the Strike "
                  f"start height differs). {meta['z_up_label']}: a change here is a tier-1 effect (T13: on the physics "
                  f"drone a 1 mm offset flips over/under outcomes).", "",
                  "| Guard | Strike | hold, base (95 %) | hold, offset (95 %) | difference |", "|---|---|---|---|---|"]
        base_rows = {(r["guard"], r["strike"]): r for r in groups.get("base", {"rows": []})["rows"]}
        for r in g["rows"]:
            b = base_rows.get((r["guard"], r["strike"]))
            diff = ("n/a" if b is None or b["hold_rate"] is None or r["hold_rate"] is None
                    else f"{100 * (r['hold_rate'] - b['hold_rate']):+.1f} points")
            lines.append(f"| {label(meta, r['guard'], True)} | {r['strike']} | {_pct(b['hold_rate'], b['hold_ci']) if b else 'n/a'} | "
                         f"{_pct(r['hold_rate'], r['hold_ci'])} | {diff} |")
        lines.append("")
    for g in result["groups"]:
        lines += [f"## {g['name']}: {g['factor'] or 'control ' + str(g['control'])}"
                  f"{', ' + g['level'] if g['level'] else ''} ({g['size']}, game `{g['game']}`)", ""]
        if g["cut"]:
            lines += ["Cut (not played).", ""]
            continue
        if g["skipped_duplicates"]:
            lines += [f"Not played (with one Strike drone they fly as strike_straight): "
                      f"{', '.join(f'{a} v {b}' for a, b in g['skipped_duplicates'])}.", ""]
        multi = sweep.parse_size(g["size"])[0] >= 2
        lines += ["| Guard | Strike | games | hold (95 %) | reach (95 %) | time-out | all Strikes tagged | tags/game "
                  "(max) | start miss | start team-close games | closest 3-D min / p05 / p50 (m; among drones still in the "
                  "game after the tag step) | closest horiz. min (m) | holds leaving no Guard | Guards left in holds (mean) | "
                  "length median / p90 (s) |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in g["rows"]:
            strike = r["strike"] + (f" ({meta['z_up_label']})" if r["strike"] in z else "")
            lines.append(
                f"| {label(meta, r['guard'], multi)} | {strike} | {r['games']}{' (+' + str(r['unfinished']) + ' unfinished)' if r['unfinished'] else ''} | "
                f"{_pct(r['hold_rate'], r['hold_ci'])} | {_pct(r['reach_rate'], r['reach_ci'])} | "
                f"{_pct(r['timeout_rate'], r['timeout_ci'])} | {_pct(r['elimination_rate'], r['elimination_ci'])} | "
                f"{_m(r['tags_mean'])} ({r['tags_max']}) | {r['start_miss_games']} | {r['start_team_close_games']} | "
                f"{_m(r.get('closest_cross_3d_m'))} / {_m(r.get('closest_cross_3d_p05_m'))} / "
                f"{_m(r.get('closest_cross_3d_p50_m'))} | {_m(r.get('closest_cross_m'))} | "
                f"{r.get('holds_no_guard_left', 'n/a')} of {r['holds']} | {_m(r.get('guards_left_mean_in_holds'))} | "
                f"{_m(r.get('length_median_s'))} / {_m(r.get('length_p90_s'))} |")
        lines.append("")
    lines += ["## Batches (speed and memory)", "", "| Batch | size | games | ticks | s | game-steps/s | peak reserved (GiB) |",
              "|---|---|---|---|---|---|---|"]
    for b in result["batches"]:
        mem = "n/a" if b["peak_reserved_bytes"] is None else f"{b['peak_reserved_bytes'] / 2**30:.2f}"
        lines.append(f"| {b['batch']} | {b['size']} | {b['games']} | {b['steps_played']} | {b['seconds']:.1f} | "
                     f"{b['game_steps_per_s']:,.0f} | {mem} |")
    if result["clips"]:
        lines += ["", "## Clips (videos/)", ""] + [f"- {c}" for c in result["clips"]]
    lines += ["", "Confounds stated before the run: " + "; ".join(f"{k}: {v}" for k, v in meta["confounds"].items()
                                                                  if isinstance(v, str)), ""]
    return "\n".join(lines)


def figures(run_dir: Path) -> None:
    import make_ste_l011_figures
    code = make_ste_l011_figures.main(["--run-dir", str(run_dir)])
    say(f"figures: exit {code}")


def make_clips(gates: sweep.Gates, run_dir: Path, should_stop=None) -> list[str]:
    """STANDARDS section 8: small replay GIFs of the clip cells (viz/replay.py, CPU), into <run>/videos/."""
    from svg_training.viz.replay import record_games, render_replay
    c = gates.clips
    spec = gates.group(c["group"])
    game, size = sweep.group_game(gates, spec)
    cfg = sweep.variant_cfg(gates, game)
    g, s = sweep.parse_size(size)
    out = []
    for guard_spec, strike_spec in c["cells"]:
        if should_stop is not None and should_stop():
            out.append("clips stopped: a stop was asked (SIGINT or SIGTERM)")
            break
        started = time.time()
        recs = record_games(cfg, g, s, guard_spec, strike_spec, int(c["games"]), seed=int(c["seed"]), band=0,
                            max_steps=int(c["max_ticks"]))
        if not recs:
            out.append(f"{guard_spec} v {strike_spec}: no recorded game finished within {c['max_ticks']} ticks: no clip")
            continue
        rec = recs[0]
        path = render_replay(rec, run_dir / "videos" / f"{guard_spec}_v_{strike_spec}.gif", speed=int(c["speed"]),
                             fps=int(c["fps"]), dpi=int(c["dpi"]),
                             playback_label=f"{int(c['speed']) * int(c['fps']) * 0.05:g}x real time")
        out.append(f"videos/{path.name}: {guard_spec} v {strike_spec}, game {rec.game_index}, outcome "
                   f"{'reach' if rec.outcome == sweep.STRIKE_WIN else 'hold'} at {rec.end_time_s:.1f} s "
                   f"({path.stat().st_size / 1e6:.2f} MB, {time.time() - started:.0f} s to make)")
        say(out[-1])
    return out


# ================================================================================================ the pilot
def pilot(gates: sweep.Gates, args: argparse.Namespace, guard: RunGuard) -> int:
    """Rate and memory per team size and batch size; the projection of the full grid per batch size."""
    p = gates.pilot
    run, device = gates.run, gates.run["device"]
    cfg = sweep.variant_cfg(gates, gates.group("base").game)
    every = pilot_cells(gates)
    points = []
    for size in p["sizes"]:
        g, s = sweep.parse_size(size)
        for cpb in p["cells_per_batch"]:
            reason = guard.stop_reason()
            if reason:                                 # QC M-6: a stopped pilot still writes its table
                write_json(args.run_dir / "pilot.json", {"points": points, "stopped": reason})
                atomic.write_text(args.run_dir / "pilot.md", f"# L0.11 pilot: stopped ({reason}) after {len(points)} "
                                  f"points; do not read partial points (relaunch with a larger cap in a new folder)\n\n"
                                  + render_pilot(points, project_grid(gates, points), gates))
                return EXIT_FOR_STOP[reason]
            cells = tuple(every[:cpb])
            n = int(run["games_per_cell"])
            point = {"size": size, "cells": len(cells), "games": len(cells) * n}
            try:
                game = sweep.SweepGame(cfg, len(cells), n, g, s, device, int(run["seed"]))
                gp = sweep.split_players(cells, "guard", cfg, n, device, int(run["seed"]))
                sp = sweep.split_players(cells, "strike", cfg, n, device, int(run["seed"]))
                if str(device).startswith("cuda"):
                    torch.cuda.reset_peak_memory_stats()
                obs = game.reset()
                everyone = torch.ones(game.num_games, dtype=torch.bool, device=device)
                gp.reset(everyone)
                sp.reset(everyone)
                t0 = time.perf_counter()
                for k in range(int(p["warmup_ticks"]) + int(p["ticks"])):
                    if k == int(p["warmup_ticks"]):
                        sweep._sync(device)
                        t0 = time.perf_counter()
                    out = game.step({"guard": gp.act(obs["guard"]), "strike": sp.act(obs["strike"])})
                    gp.reset(out.done)
                    sp.reset(out.done)
                    obs = out.obs
                sweep._sync(device)
                timed = time.perf_counter() - t0
                spt = timed / int(p["ticks"])
                point.update(seconds_per_tick=spt, game_steps_per_s=point["games"] / spt,
                             drone_steps_per_s=point["games"] * (g + s) / spt,
                             peak_allocated_bytes=torch.cuda.max_memory_allocated() if str(device).startswith("cuda") else None,
                             peak_reserved_bytes=torch.cuda.max_memory_reserved() if str(device).startswith("cuda") else None)
            except torch.cuda.OutOfMemoryError as err:
                point.update(error=f"out of memory: {err}".splitlines()[0])
            finally:
                game = gp = sp = obs = out = None
                if str(device).startswith("cuda"):
                    torch.cuda.empty_cache()
            points.append(point)
            say(f"pilot {size} x {point['cells']} cells ({point['games']} games): "
                + (f"{point['seconds_per_tick'] * 1e3:.1f} ms/tick, {point['game_steps_per_s']:,.0f} game-steps/s"
                   if "seconds_per_tick" in point else point["error"]))
    projections = project_grid(gates, points)
    write_json(args.run_dir / "pilot.json", {"points": points, "projections": projections, "cap_h": gates_cap_h(gates),
                                             "gates_sha256": gates.sha256, "device": device,
                                             "gpu": torch.cuda.get_device_name(0) if str(device).startswith("cuda") else None})
    atomic.write_text(args.run_dir / "pilot.md", render_pilot(points, projections, gates))
    guard.save(len(points), {"points": len(points)})
    say(f"pilot done: {args.run_dir / 'pilot.md'}")
    return EXIT_DONE


def pilot_cells(gates: sweep.Gates) -> list[tuple[str, str]]:
    """QC M-10: every Strike script against the Guard scripts in [pilot] guard_order (moving Guards first), so a point of
    1, 4 or 10 cells does not time still Guards alone."""
    order = [g for g in gates.pilot["guard_order"] if g in gates.players["guards"]]
    return [(gg, ss) for ss in gates.players["strikes"] for gg in order]


def gates_cap_h(gates: sweep.Gates | None = None) -> float:
    """The L0.11 task cap of configs/ste_learning.toml (GPU-h)."""
    from svg_training.ste.config import load_ste_learning
    return float(load_ste_learning()[0].budget.cap_gpu_h("L0.11"))


def project_grid(gates: sweep.Gates, points: list[dict]) -> list[dict]:
    """For each pilot batch size: the full plan's worst-case seconds = sum over batches of ticks_cap x seconds per tick
    of the pilot point with that size and that batch size (a smaller last batch is charged as a full one)."""
    import dataclasses
    out = []
    for cpb in gates.pilot["cells_per_batch"]:
        trial = dataclasses.replace(gates, run=dict(gates.run, cells_per_batch=cpb))
        plan = sweep.build_plan(trial)
        total, missing = 0.0, set()
        per_size = {pt["size"]: pt.get("seconds_per_tick") for pt in points if pt["cells"] == cpb}
        for p in plan:
            size = sweep.group_game(trial, p.spec)[1]
            spt = per_size.get(size)
            if spt is None:
                missing.add(size)
                continue
            total += len(p.batches) * p.spec.ticks_cap(trial.run) * spt
        margin = total * float(gates.cut["safety_factor"]) + float(gates.clips["reserve_s"])
        out.append({"cells_per_batch": cpb, "batches": sum(len(p.batches) for p in plan),
                    "projected_s": None if missing else total, "projected_gpu_h": None if missing else total / HOUR_S,
                    "with_margin_gpu_h": None if missing else margin / HOUR_S,
                    "missing_sizes": sorted(missing),
                    "toml_lines": [f'"{k}" = {v:.6g}' for k, v in per_size.items() if v is not None]})
    return out


def render_pilot(points: list[dict], projections: list[dict], gates: sweep.Gates) -> str:
    cap = gates_cap_h(gates)
    lines = ["# L0.11 pilot: rate and memory per team size and batch size", "", f"Simulator: {SIMULATOR}.", "",
             "| size | cells | games | ms per tick | game-steps/s | drone-steps/s | peak reserved (GiB) |",
             "|---|---|---|---|---|---|---|"]
    for pt in points:
        if "error" in pt:
            lines.append(f"| {pt['size']} | {pt['cells']} | {pt['games']} | {pt['error']} | | | |")
            continue
        mem = "n/a" if pt["peak_reserved_bytes"] is None else f"{pt['peak_reserved_bytes'] / 2**30:.2f}"
        lines.append(f"| {pt['size']} | {pt['cells']} | {pt['games']} | {pt['seconds_per_tick'] * 1e3:.1f} | "
                     f"{pt['game_steps_per_s']:,.0f} | {pt['drone_steps_per_s']:,.0f} | {mem} |")
    lines += ["", f"Projection of the full plan (worst case: every batch plays {gates.run['ticks_cap']} ticks), against the "
              f"L0.11 cap of {cap} GPU-h (less the pilot's own hours):", "",
              "| cells per batch | batches | projected GPU-h | with safety factor and clip reserve | fits | "
              "[projection.seconds_per_batch_tick] lines |",
              "|---|---|---|---|---|---|"]
    for pr in projections:
        h = pr["projected_gpu_h"]
        hm = pr["with_margin_gpu_h"]
        lines.append(f"| {pr['cells_per_batch']} | {pr['batches']} | {'n/a (missing ' + ', '.join(pr['missing_sizes']) + ')' if h is None else f'{h:.2f}'} | "
                     f"{'n/a' if hm is None else f'{hm:.2f}'} | {'n/a' if hm is None else ('yes' if hm <= cap else 'NO')} | "
                     f"{'; '.join(pr['toml_lines'])} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
