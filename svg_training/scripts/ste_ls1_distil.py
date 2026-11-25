#!/usr/bin/env python
"""STE route 3, stage LS1, jobs LS1.0 and LS1.1: the distillation of one team's scripts into its skill network,
under the run contract (task LS1-M2-T4; plan ste_learning/drafts/LS1_TASK_PLAN.md, merge M2).

    ste_ls1_distil.py --gates configs/ste_ls1/distil_gates.toml --side guard|strike --run-dir runs/<date>_ste_ls1_<side>
                      --cap-h <H> [--expect-gates-sha256 <hex>] [--smoke] [--no-clips] [--allow-code-change]

Launch: LS1.1 (GPU) ``scripts/ste_job.py launch --task LS1.1 --gpu-h <H> ... -- <this command> --cap-h <H>`` (the same
H; ``[run] device``, cuda on the committed file); LS1.0, the smoke (CPU, not of record) ``scripts/ste_job.py launch
--task LS1.0 --gpu-h 0 ... -- <this command> --smoke`` on the same committed file (``[smoke] device``, which must be
"cpu"; sizes by ``ste/distil.SMOKE_RULE``). The driver does not compare ``[run] task`` with the launched task (as
``scripts/ste_exploit_l012.py``, it compares the GPU-hours and the device only), so LS1.0 runs LS1.1's file.

A run (``ste/distil.py``, tasks LS1-M2-T2 and T3): per relabelling round r (``[dagger] script_share``, the first
``[smoke] rounds`` entries under --smoke) two checkpointed steps, step = 2r + phase:
* phase 0, collected (``distil.round_rows``): the round's collection (the round r-1 network flies the share
  1 - script_share[r] of the games), weighted by that network's error, kept; the control ``ctl_labels_are_the_scripts``
  on every kept row; the kept rows written to ``data/round_<r>.pt`` (atomic; their sha256 in the checkpoint);
* phase 1, fitted (``distil.refit``): a fresh network from ``[fit] seed`` fitted on every round's kept rows so far (read
  back from ``data/`` on a resume); its weights (normaliser included) in the checkpoint.
Then the final read (``distil.final_report``: fresh, unweighted, net-flown, ``[report] seed``), the network file
``skill_net_<side>.pt`` (C3; ``provenance``: the gate file repository-relative and its sha256, rounds, ``[data] seed``,
the git commit, ``of_record``), the clips (CPU), ``results.md`` and ``fit_report.json`` last (``rounds``, ``final``,
``gates_sha256``, ``net_sha256``, ``of_record``, ``complete: true`` last). A network goes to the read (LS1.2) only from
a complete, of-record report: ``of_record`` is false under --smoke and under --no-clips (STANDARDS section 8: videos in
every run of record).

The control ``ctl_labels_are_the_scripts`` (``controls.json``): each kept row's labels equal every script's command on
that row alone at its slot of a zero team tensor (the isolation check of M2-T2's test; the scripts are row-wise), on
the collection's device, each channel within ``[data] label_check_atol`` (not bit for bit: the batch layout moves the
last bits, plan constraint 8; the rows not bit-equal and the largest difference are written too). It checks every kept
row (batched in chunks), so it needs no sample size or seed. A row that differs: FAIL, exit 6, the round's data not
written (terminal).

The clips (2-D, the height panel; ``videos/<side>_<code>_g<game>_{net,scripts}.gif``): each ``[clips] codes`` code of
the side flown by the network (``cells.fixed_team`` on a ``skills.NetTwoLevelDispatch`` of the saved file, hold 1, C6)
beside the same starts flown by the code's script, against the skills gate file's maximin script of the other team for
its base variant (``exploit.opponent_of(skills_gates, "base", side)``; the rule of the design check, no gate key).
The starts are drawn once (``replay.cpu_starts``, ``[clips] seed``) and given to both arms. ``[clips] games`` starts,
at most ``max_ticks`` ticks; of the starts finished in both arms, the first ``keep`` are kept, those whose outcome
differs between the two arms before the others, then in start order. A code with no start finished in both arms has
no clip (said in results.md). Under --smoke: ``[smoke] games`` and ``ticks``, the first code only. On the CPU.

The run contract (``ste/run_contract.py``): the same command resumes from the last step saved; SIGINT or SIGTERM stops
before the next tick of a collection, the next epoch of a fit or the next frame of a clip game (the partial step is
redone, seeded by seed and round: same rows, same net) with the last checkpoint saved again (exit 4); the cap is
effective seconds = --cap-h x 3600 (exit 3). The final read runs to its end once started (``distil.final_report`` takes
no stop); a stop is seen after it. A done folder (a complete ``fit_report.json``) exits 0 at once.

Exit codes: 0 done; 2 refused, nothing written (a schema error; the owner's ``FILL_`` keys outside --smoke; the gate
file off --expect-gates-sha256; a pin off: the skills gate file, cells.toml, opponents/scripted.py, the game file, the
reference whose seed the scoring starts use; a seed of the file equal to the scoring starts' seed; job.json against the
device or the cap; cuda asked and absent; the gate file, side, --smoke or --no-clips changed since the first launch;
another process in the folder; a data file whose sha256 differs on a resume); 3 cap; 4 stopped on request; 5 a
non-finite value (a loss, a report number: nothing is saved over the last good checkpoint; a relaunch exits 5 again);
6 a control failed (terminal).

Training simulator, tier 1; observed in the training simulator. Not for flight."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

import torch  # noqa: E402

import ste_sweep_l011 as l011  # noqa: E402  (code pinning: the L0.11 driver's own helper)
from svg_training.core.observations import OBS_DIM  # noqa: E402
from svg_training.opponents.scripted import make_strategy  # noqa: E402
from svg_training.ste import atomic, cells, distil, exploit, scoring, skill_net, skills, sweep  # noqa: E402
from svg_training.ste.run_contract import (EXIT_CONTROL_FAILED, EXIT_DONE, EXIT_FOR_STOP, EXIT_NONFINITE,  # noqa: E402
                                           EXIT_REFUSED, STOP_INTERRUPTED, NonFiniteError, RunBusyError, RunGuard)
from svg_training.viz import replay  # noqa: E402

HOUR_S = 3600.0
GPU_H_TOLERANCE = 1e-9            # job.json's GPU-hours against --cap-h (as scripts/ste_exploit_l012.py)
PINNED_SHA, GATES_COPY, RUN_FILE = "gates.sha256", "gates.toml", "run.json"
CONTROLS_FILE, FIT_REPORT, RESULTS_MD = "controls.json", "fit_report.json", "results.md"
DATA_DIR, VIDEOS_DIR, JOB_FILE = "data", "videos", "job.json"
SCRIPTED = ROOT / "source" / "svg_training" / "opponents" / "scripted.py"
PASS, FAIL, NONFINITE = scoring.PASS, scoring.FAIL, scoring.NONFINITE
CTL_LABELS = "ctl_labels_are_the_scripts"
NONFINITE_KEY = "no_nonfinite_values"
COLLECTED, FITTED = 0, 1          # a round's two steps; checkpoint step = STEPS_PER_ROUND * round + phase
STEPS_PER_ROUND = 2
NO_STEP = -1                      # the step of a run folder with no step done yet
ARMS = ("net", "scripts")         # the two clips of a kept start


def say(text: str) -> None:
    print(f"[ls1 distil] {text}", flush=True)


def refuse(text: str) -> int:
    print(f"refused: {text}", file=sys.stderr, flush=True)
    return EXIT_REFUSED


def parse(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--gates", type=Path, required=True)
    ap.add_argument("--side", choices=cells.SIDES, required=True)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--cap-h", type=float, required=True, help="cap in effective hours (= the launcher's --gpu-h)")
    ap.add_argument("--expect-gates-sha256", help="refuse unless the gate file has this sha256")
    ap.add_argument("--smoke", action="store_true", help="job LS1.0: [smoke] sizes on [smoke] device, not of record")
    ap.add_argument("--no-clips", action="store_true", help="skip the clips (tests only; not of record)")
    ap.add_argument("--allow-code-change", action="store_true",
                    help="resume although the code differs from the first launch's (recorded in code.json)")
    ap.add_argument("--stop-after-step", type=int, default=None, help=argparse.SUPPRESS)   # tests only (CA-2)
    return ap.parse_args(argv)


def _resolve(path: str) -> Path:
    """A path of the gate file: relative from the ``svg_training/`` root, absolute as is (``distil``'s rule)."""
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def rel(path: Path | str) -> str:
    """``path`` repository-relative; outside the repository its name only (no machine or user name in a file)."""
    p = Path(path).resolve()
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return f"(outside svg_training)/{p.name}"


def write_json(path: Path, obj) -> None:
    atomic.write_text(path, json.dumps(obj, indent=1, allow_nan=False) + "\n")


# ================================================================================================ pre-flight
@dataclass
class Ctx:
    """What a run needs once every check has passed."""
    args: argparse.Namespace
    g: distil.DistilGates
    side: str
    smoke: bool
    device: str
    of_record: bool
    sizes: dict


def _job_problem(args: argparse.Namespace, device: str) -> str | None:
    """job.json (written by ``ste_job.py launch``) against the device and the cap (``scripts/ste_exploit_l012.py``)."""
    path = args.run_dir / JOB_FILE
    cuda = str(device).startswith("cuda")
    if path.is_file():
        gpu_h = json.loads(path.read_text()).get("gpu_h", 0)
        if args.smoke and gpu_h != 0:
            return f"--smoke is the CPU job LS1.0: launch it at --gpu-h 0, not {gpu_h}"
        if gpu_h > 0:
            if abs(gpu_h - args.cap_h) > GPU_H_TOLERANCE:
                return f"the launcher asked for {gpu_h} GPU-h, --cap-h is {args.cap_h}: keep the two equal"
            if not cuda:
                return f"a GPU job (--gpu-h {gpu_h}) with device {device!r}"
        elif cuda:
            return f"the gate file plays on {device} but the launcher asked for 0 GPU-h (a CPU job)"
    if cuda and not torch.cuda.is_available():
        return f"the gate file plays on {device} and PyTorch sees no GPU"
    return None


def _run_problem(args: argparse.Namespace, g: distil.DistilGates) -> str | None:
    """Why this command may not resume the run folder: its gate file, side, --smoke or --no-clips differ."""
    pinned = args.run_dir / PINNED_SHA
    if pinned.is_file() and pinned.read_text().strip() != g.sha256:
        return (f"the gate file changed since the first launch in {args.run_dir} (pinned {pinned.read_text().strip()}, "
                f"now {g.sha256}): a changed file needs a new run folder")
    path = args.run_dir / RUN_FILE
    if path.is_file():
        was = json.loads(path.read_text())
        now = run_record(args, g)
        differ = [f"{k} {was.get(k)!r} (this command: {now[k]!r})" for k in ("side", "smoke", "no_clips")
                  if was.get(k) != now[k]]
        if differ:
            return f"{path} was started as another run: {'; '.join(differ)}; start a new run folder"
    return None


def run_record(args: argparse.Namespace, g: distil.DistilGates) -> dict:
    return {"side": args.side, "smoke": bool(args.smoke), "no_clips": bool(args.no_clips), "cap_h": args.cap_h,
            "gates_file": rel(args.gates), "gates_sha256": g.sha256}


def prepare(args: argparse.Namespace) -> tuple[Ctx | None, str | None]:
    """Every check before anything is written: (the run's context, None) or (None, why it is refused)."""
    try:
        g = distil.load_distil_gates(args.gates)
    except (OSError, ValueError) as err:
        return None, f"gate file {args.gates}: {err}"
    if args.expect_gates_sha256 and args.expect_gates_sha256 != g.sha256:
        return None, f"the gate file has sha256 {g.sha256}, expected {args.expect_gates_sha256}"
    src, sg = g.source, g.skills_gates
    for key, path, what in (("skills_gates_sha256", _resolve(src["skills_gates"]), "skills gate file"),
                            ("cells_sha256", _resolve(src["cells"]), "cells file"),
                            ("scripted_sha256", SCRIPTED, "opponents/scripted.py"),
                            ("game_sha256", _resolve(src["game_file"]), "game file")):
        problem = scoring.sha_problem(path, src[key], what)
        if problem:
            return None, f"[source] {key}: {problem}"
    problems = exploit.game_file_problems(sg)
    if problems:
        return None, "the skills gate file's game file(s) differ: " + "; ".join(problems)
    if not args.smoke:
        todo = distil.unfilled_limits(g)
        if todo:
            return None, (f"the owner's keys are not filled yet ({', '.join(todo)}): a run of record needs them (R38); "
                          f"--smoke runs without them, not of record")
    ref_file = ROOT / sg.reference["file"]
    problem = scoring.sha_problem(ref_file, sg.reference["sha256"], "the scoring starts' reference")
    if problem:
        return None, problem
    t44_seed = int(exploit.load_reference(ref_file).meta["seed"])
    seeds = {"[data] seed": g.data["seed"], "[data] pool_seed": g.data["pool_seed"], "[fit] seed": g.fit["seed"],
             "[report] seed": g.report["seed"], "[clips] seed": g.clips["seed"]}
    same = [k for k, v in seeds.items() if int(v) == t44_seed]
    if same:
        return None, (f"{', '.join(same)} is the scoring starts' seed {t44_seed} (T44): the distillation plays other "
                      f"starts")
    if not (math.isfinite(args.cap_h) and args.cap_h > 0):
        return None, f"--cap-h must be a finite number of hours above 0, got {args.cap_h!r}"
    device = g.smoke["device"] if args.smoke else g.run["device"]
    if args.smoke and device != "cpu":
        return None, f"[smoke] device must be \"cpu\" (LS1.0 is a CPU job at 0 GPU-h), got {device!r}"
    problem = _job_problem(args, device) or _run_problem(args, g)
    if problem:
        return None, problem
    return Ctx(args=args, g=g, side=args.side, smoke=bool(args.smoke), device=device,
               of_record=not (args.smoke or args.no_clips), sizes=distil.run_sizes(g, bool(args.smoke))), None


def done(run_dir: Path) -> bool:
    path = run_dir / FIT_REPORT
    return path.is_file() and json.loads(path.read_text()).get("complete") is True


def main(argv: list[str] | None = None) -> int:
    args = parse(list(sys.argv[1:] if argv is None else argv))
    ctx, why = prepare(args)
    if why:
        return refuse(why)
    if done(args.run_dir):
        say(f"this run folder is done ({args.run_dir / FIT_REPORT}): nothing to do")
        return EXIT_DONE
    controls_file = args.run_dir / CONTROLS_FILE
    if controls_file.is_file():
        code = scoring.ending(json.loads(controls_file.read_text()))
        if code is not None:
            print(f"[ls1 distil] a control is not PASS in this run folder ({controls_file}): read it; a new run needs "
                  f"a new run folder (exit {code})", file=sys.stderr, flush=True)
            return code
    args.run_dir.mkdir(parents=True, exist_ok=True)
    try:
        with RunGuard(args.run_dir, cap_s=args.cap_h * HOUR_S, dump=torch.save,
                      load=lambda p: torch.load(p, weights_only=False)) as guard:
            changed = l011.pin_code(args)
            if changed:
                return refuse(changed)
            if not (args.run_dir / PINNED_SHA).is_file():
                atomic.write_text(args.run_dir / GATES_COPY, args.gates.read_text())
                atomic.write_text(args.run_dir / PINNED_SHA, ctx.g.sha256 + "\n")
            if not (args.run_dir / RUN_FILE).is_file():
                write_json(args.run_dir / RUN_FILE, run_record(args, ctx.g))
            return run(ctx, guard)
    except RunBusyError as err:
        return refuse(str(err))


# ================================================================================================ the steps
def data_file(run_dir: Path, round_index: int) -> Path:
    return run_dir / DATA_DIR / f"round_{round_index}.pt"


def save_rows(path: Path, rows: distil.Rows) -> str:
    """Write the kept rows (every ``distil.ROW_FIELDS`` tensor and ``team_size``) atomically; their sha256."""
    buffer = io.BytesIO()
    torch.save({**{name: getattr(rows, name) for name in distil.ROW_FIELDS}, "team_size": rows.team_size}, buffer)
    raw = buffer.getvalue()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = atomic.temporary_path(path)
    try:
        temporary.write_bytes(raw)
        atomic.commit(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return hashlib.sha256(raw).hexdigest()


def load_rows(path: Path) -> distil.Rows:
    data = torch.load(path, weights_only=True)
    return distil.Rows(**{name: data[name] for name in distil.ROW_FIELDS}, team_size=int(data["team_size"]))


def label_check(rows: distil.Rows, cfg, spec: cells.CellSpec, side: str, device, atol: float) -> dict:
    """The control ``ctl_labels_are_the_scripts`` on every kept row: the row alone at its slot of a zero team tensor
    [B, M, OBS_DIM], every script k of the side once on it, its command at the row's slot against ``label[:, k]`` (all
    4 channels). Returns ``checked`` (rows), ``differ`` (rows with a channel off by more than ``atol``, the gate file's
    ``[data] label_check_atol``: the control fails on any), ``not_bit_equal`` (rows not equal to the last bit) and
    ``max_abs_diff``. Not bit for bit: the same script on the same row gives other last bits in another batch layout
    (plan constraint 8; measured 26 Nov 2026: ``guard_parked_ring`` on one game alone against the same game among 64
    differed by 3.9e-7, the isolation itself changed nothing; at most 7.2e-7 over about 8.7 million rows of both
    teams, 8.3e-7 in one smoke round of 4,858 rows; not measured on CUDA). An absolute tolerance: the commands are
    unitless in [-1, 1]. Batched over the rows in chunks of ``distil.EVAL_ROWS`` (memory
    only); the loop runs over the K scripts."""
    dev = torch.device(device)
    r, differ, not_equal, worst = rows.obs.shape[0], 0, 0, 0.0
    for start in range(0, r, distil.EVAL_ROWS):
        obs = rows.obs[start:start + distil.EVAL_ROWS].to(dev)
        slot = rows.slot[start:start + distil.EVAL_ROWS].to(dev)
        label = rows.label[start:start + distil.EVAL_ROWS].to(dev)
        b = obs.shape[0]
        row = torch.arange(b, device=dev)
        team = obs.new_zeros(b, spec.drones, OBS_DIM)
        team[row, slot] = obs
        close = torch.ones(b, dtype=torch.bool, device=dev)
        equal = torch.ones(b, dtype=torch.bool, device=dev)
        for k, name in enumerate(spec.players):
            want = make_strategy(name, side, cfg, b, str(dev), 0).act(team)[row, slot]
            close &= ((want - label[:, k]).abs() <= atol).all(dim=-1)
            equal &= (want == label[:, k]).all(dim=-1)
            worst = max(worst, float((want - label[:, k]).abs().max())) if b else worst
        differ += int((~close).sum())
        not_equal += int((~equal).sum())
    return {"checked": r, "differ": differ, "not_bit_equal": not_equal, "max_abs_diff": worst}


def _controls(run_dir: Path) -> dict:
    path = run_dir / CONTROLS_FILE
    return json.loads(path.read_text()) if path.is_file() else {}


def note_labels(run_dir: Path, round_index: int, check: dict) -> str:
    """Fold one round's label check into ``controls.json`` (one entry over the run; FAIL once any round fails)."""
    controls = _controls(run_dir)
    prev = controls.get(CTL_LABELS, {"status": PASS, "detail": ""})
    text = (f"round {round_index}: {check['differ']} of {check['checked']} kept rows differ from the scripts by more "
            f"than [data] label_check_atol ({check['not_bit_equal']} not bit-equal, largest |difference| "
            f"{check['max_abs_diff']:.3g})")
    status = PASS if prev["status"] == PASS and check["differ"] == 0 else FAIL
    controls[CTL_LABELS] = {"status": status, "detail": "; ".join(t for t in (prev["detail"], text) if t),
                            "phase": "collection"}
    write_json(run_dir / CONTROLS_FILE, controls)
    return status


def note_nonfinite(run_dir: Path, where: str, err: Exception) -> None:
    controls = _controls(run_dir)
    controls[NONFINITE_KEY] = {"status": NONFINITE, "detail": f"{where}: {err}", "phase": where}
    write_json(run_dir / CONTROLS_FILE, controls)


def _cpu_state(net) -> dict:
    return {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}


def rebuild_net(ctx: Ctx, state_dict: dict):
    """The fitted net of a checkpoint: ``distil.initial_net``'s shape, the saved weights and normaliser, on the run's
    device, flying (``eval()``, no gradients), as ``distil.fit`` leaves it."""
    g = ctx.g
    net = distil.initial_net(g.specs[ctx.side], exploit.variant_cfg(g.skills_gates, distil.VARIANT), g.net,
                             g.fit["seed"])
    net.load_state_dict(state_dict)
    return net.to(torch.device(ctx.device)).eval().requires_grad_(False)


def fresh_state(ctx: Ctx) -> dict:
    return {"side": ctx.side, "smoke": ctx.smoke, "gates_sha256": ctx.g.sha256, "data_sha256": [], "stats": [],
            "summaries": [], "net_state": None}


def run(ctx: Ctx, guard: RunGuard) -> int:
    run_dir, g, side = ctx.args.run_dir, ctx.g, ctx.side
    rounds = len(ctx.sizes["script_share"])
    found = guard.load_latest()
    state, last = (found.state, found.step) if found is not None else (fresh_state(ctx), NO_STEP)
    for r, sha in enumerate(state["data_sha256"]):
        path = data_file(run_dir, r)
        got = exploit.sha256_file(path) if path.is_file() else "missing"
        if got != sha:
            return refuse(f"{path} is {got}, the checkpoint pins {sha}: the kept rows changed; start a new run folder")
    kept = [load_rows(data_file(run_dir, r)) for r in range(len(state["data_sha256"]))]
    net = rebuild_net(ctx, state["net_state"]) if state["net_state"] is not None else None
    if found is not None:
        say(f"resumed at step {last} (rounds collected {len(kept)}, fitted {len(state['summaries'])})")

    def should_stop() -> bool:
        return guard.stop_reason() is not None

    def stop(reason: str) -> int:
        guard.save(last, state)                      # the last checkpoint again: the effective seconds carried on
        say(f"stopped ({reason}) after step {last}; checkpoint saved; the same command resumes")
        return EXIT_FOR_STOP[reason]

    where = "collection"
    try:
        for step in range(last + 1, STEPS_PER_ROUND * rounds):
            reason = guard.stop_reason()
            if reason:
                return stop(reason)
            r, phase = divmod(step, STEPS_PER_ROUND)
            if phase == COLLECTED:
                where = f"round {r} collection"
                rows, stats = distil.round_rows(g, side, r, net, ctx.device, smoke=ctx.smoke, should_stop=should_stop)
                check = label_check(rows, exploit.variant_cfg(g.skills_gates, distil.VARIANT), g.specs[side], side,
                                    ctx.device, g.data["label_check_atol"])
                if note_labels(run_dir, r, check) != PASS:
                    say(f"CONTROL FAILED: {CTL_LABELS}, round {r}: {check['differ']} of {check['checked']} kept rows "
                        f"(exit {EXIT_CONTROL_FAILED}, terminal)")
                    return EXIT_CONTROL_FAILED
                state["data_sha256"].append(save_rows(data_file(run_dir, r), rows))
                state["stats"].append(stats)
                kept.append(rows)
                say(f"round {r}: {stats['rows']} rows collected, {stats['kept']} kept ({stats['seconds']:.1f} s)")
            else:
                where = f"round {r} fit"
                started = time.monotonic()
                net, out = distil.refit(g, side, kept, ctx.device, should_stop=should_stop, check=guard.check_finite)
                seconds = state["stats"][r]["seconds"] + time.monotonic() - started
                state["summaries"].append(distil.round_summary(state["stats"][r], out["loss"], seconds))
                state["net_state"] = _cpu_state(net)
                say(f"round {r}: fitted, last epoch loss {out['loss'][-1]:.6g}")
            guard.save(step, state)
            last = step
            if ctx.args.stop_after_step is not None and step == ctx.args.stop_after_step:
                os.kill(os.getpid(), signal.SIGTERM)     # the real handler sets the stop (tests only, CA-2)
        reason = guard.stop_reason()
        if reason:
            return stop(reason)
        where = "final read"
        return finish(ctx, guard, state, net, should_stop, rounds)
    except (sweep.SweepStopped, replay.RecordingStopped):
        return stop(guard.stop_reason() or STOP_INTERRUPTED)
    except NonFiniteError as err:
        note_nonfinite(run_dir, where, err)
        say(f"NON-FINITE at {where}: {err}; the last good checkpoint (step {last}) is kept (exit {EXIT_NONFINITE})")
        return EXIT_NONFINITE


# ================================================================================================ the end of a run
def net_meta(ctx: Ctx, rounds: int) -> dict:
    """The caller's part of the network file's meta (C3, ``skill_net.META_KEYS``)."""
    g, sg = ctx.g, ctx.g.skills_gates
    cfg = exploit.variant_cfg(sg, distil.VARIANT)
    guards, strikes = sweep.parse_size(sg.run["size"])
    return {"guards": guards, "strikes": strikes, "std_floor": g.net["std_floor"],
            "scripted_sha256": skill_net.scripted_sha256(), "game_file": g.source["game_file"],
            "game_sha256": g.source["game_sha256"], "game_constants": skill_net.game_constants(cfg),
            "provenance": {"distil_gates_file": rel(ctx.args.gates), "distil_gates_sha256": g.sha256,
                           "rounds": rounds, "seed": g.data["seed"], "git_commit": l011.code_identity()["commit"],
                           "of_record": ctx.of_record}}


def finish(ctx: Ctx, guard: RunGuard, state: dict, net, should_stop, rounds: int) -> int:
    """The final read, the network file, the clips, results.md, then fit_report.json (``complete`` last)."""
    run_dir, side = ctx.args.run_dir, ctx.side
    final = distil.final_report(ctx.g, side, net, ctx.device, smoke=ctx.smoke)
    guard.check_finite(final=final)
    reason = guard.stop_reason()
    if reason:
        raise sweep.SweepStopped(reason)
    net_file = run_dir / f"skill_net_{side}.pt"
    net_sha = skill_net.save_skill_net(net_file, net, net_meta(ctx, rounds))
    clip_lines = ["clips skipped (--no-clips)"] if ctx.args.no_clips else clips(ctx, net_file, net_sha, should_stop)
    report = {"rounds": state["summaries"], "final": final, "gates_sha256": ctx.g.sha256, "net_sha256": net_sha,
              "of_record": ctx.of_record, "complete": True}
    atomic.write_text(run_dir / RESULTS_MD, results_md(ctx, report, net_file, clip_lines))
    write_json(run_dir / FIT_REPORT, report)
    guard.save(STEPS_PER_ROUND * rounds, state)
    say(f"done: {rel(net_file)} sha256 {net_sha}; {FIT_REPORT} written (of_record {ctx.of_record})")
    return EXIT_DONE


def clips(ctx: Ctx, net_file: Path, net_sha: str, should_stop) -> list[str]:
    """The clips (module docstring), on the CPU; one line per code for results.md."""
    g, side = ctx.g, ctx.side
    sg, spec, c = g.skills_gates, g.specs[side], g.clips
    cfg = exploit.variant_cfg(sg, distil.VARIANT)
    guards, strikes = sweep.parse_size(sg.run["size"])
    games, ticks = (g.smoke["games"], g.smoke["ticks"]) if ctx.smoke else (c["games"], c["max_ticks"])
    codes = list(c["codes"][side])[:1] if ctx.smoke else list(c["codes"][side])
    opponent = exploit.opponent_of(sg, distil.VARIANT, side)
    net, _ = skill_net.load_skill_net(net_file, team=side, skills=list(spec.players), cfg=cfg, device="cpu",
                                      file_sha256=net_sha)
    choices = {ch["script"]: ch for ch in cells.fixed_choices(spec)}
    starts = replay.cpu_starts(cfg, games, guards, strikes, c["seed"])
    out_dir = ctx.args.run_dir / VIDEOS_DIR
    lines = []
    for code in codes:
        dispatch = skills.NetTwoLevelDispatch(side, list(spec.players), list(spec.team_strategies),
                                              list(spec.drone_skills), cfg, games, "cpu", c["seed"], net, net_sha)
        players = {"net": cells.fixed_team(spec, choices[code], dispatch, cells.NET_PREFIX + code), "scripts": code}
        recs = {}
        for arm in ARMS:
            g_spec, s_spec = cells.cell_of(side, players[arm], opponent)
            recs[arm] = {rec.game_index: rec for rec in
                         replay.record_games(cfg, guards, strikes, g_spec, s_spec, num_games=games, seed=c["seed"],
                                             max_steps=ticks, device="cpu", should_stop=should_stop, starts=starts)}
        both = sorted(set(recs["net"]) & set(recs["scripts"]),
                      key=lambda i: (recs["net"][i].outcome == recs["scripts"][i].outcome, i))
        picked = both[:c["keep"]]
        for i in picked:
            for arm in ARMS:
                replay.render_replay(recs[arm][i], out_dir / f"{side}_{code}_g{i}_{arm}.gif", speed=c["speed"],
                                     fps=c["fps"], dpi=c["dpi"], height_panel=True)
        lines.append(f"{code} v {opponent}: {len(both)} of {games} starts finished in both arms within {ticks} ticks; "
                     f"kept {', '.join(f'g{i}' for i in picked) or 'none (no clip)'}")
    return lines


def _f(v, digits: int = 4) -> str:
    return "-" if v is None else f"{v:.{digits}g}"


def results_md(ctx: Ctx, report: dict, net_file: Path, clip_lines: list[str]) -> str:
    final, g = report["final"], ctx.g
    out = [f"# LS1 distillation, {ctx.side} team ({'smoke, LS1.0' if ctx.smoke else 'LS1.1'})", "",
           f"Training simulator, tier 1; observed in the training simulator. of_record: {report['of_record']}.", "",
           f"- gate file: {rel(ctx.args.gates)} (sha256 {report['gates_sha256']})",
           f"- network: {rel(net_file)} (sha256 {report['net_sha256']}), hidden {g.net['hidden']}, device {ctx.device}",
           f"- sizes: {ctx.sizes}", "", "## Rounds", "",
           "| round | rows | kept | uniform / mix / random | absent | near switch | prev net RMSE | last loss | s |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in report["rounds"]:
        mix = " / ".join(_f(r["shares_by_mode"][m], 3) for m in distil.MODES)
        out.append(f"| {r['round']} | {r['rows']} | {r['kept']} | {mix} | {_f(r['absent_share'], 3)} | "
                   f"{_f(r['near_switch_share'], 3)} | {_f(r['prev_net_rmse'])} | {_f(r['loss'][-1])} | "
                   f"{r['seconds']:.1f} |")
    out += ["", "## Final read (fresh, unweighted, net-flown)", "", "| skill | RMSE per channel (active *) | p99 abs |",
            "|---|---|---|"]
    for name, s in final["per_skill"].items():
        rmse = ", ".join(_f(v) + ("*" if a else "") for v, a in zip(s["rmse"], s["active"]))
        p99 = ", ".join(_f(v) for v in s["p99_abs"]) if s["p99_abs"] is not None else "-"
        out.append(f"| {name} | {rmse} | {p99} |")
    out += ["", f"- zero-command skill: {final['zero_skill']}",
            f"- RMSE by live drones: {final['rmse_by_n_live']}",
            f"- RMSE by hold bin (ticks): {final['rmse_by_hold_bin']}",
            f"- mean tick-to-tick command change: {final['delta_cmd']}",
            f"- game-steps per second (the report's collection): {_f(final['game_steps_per_s'])}",
            "", "## Clips", ""] + [f"- {line}" for line in clip_lines]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    sys.exit(main())
